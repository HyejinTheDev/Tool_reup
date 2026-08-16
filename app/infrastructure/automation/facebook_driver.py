import os
import json
import asyncio
from typing import Optional
from app.infrastructure.automation.base_driver import BaseDriver
from app.adapters.gateways.uploader_gateway import UploaderGateway

class FacebookDriver(BaseDriver, UploaderGateway):
    async def upload(self, video_path: str, title: str, description: str, publish_type: str = "reels") -> str:
        """
        Uploads a video to Facebook.
        Supports:
        - publish_type = "reels": Uploads to Facebook Reels via Reels Composer.
        - publish_type = "video": Uploads as a normal Page Video via Meta Business Suite Composer.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found at: {video_path}")

        if publish_type == "video":
            self.log("Navigating to Facebook Regular Post Composer...")
            await self.page.get("https://business.facebook.com/latest/composer?media_type=video")
        else:
            self.log("Navigating to Facebook Reels Composer...")
            await self.page.get("https://business.facebook.com/latest/reels_composer")
            
        await self.delay(5)

        # 1. Login verification & wait loop
        is_logged_in = False
        self.log("Checking login status...")
        
        for i in range(60):
            current_url = ""
            try:
                current_url = await self.page.evaluate("window.location.href")
            except Exception:
                current_url = self.page.url or ""
                
            if "login" in current_url or "facebook.com/login" in current_url:
                self.log(f"Not logged in. Current URL: {current_url}. Waiting for manual login in the browser (attempt {i+1}/60)...", "WARN")
                await self.delay(5)
            else:
                if "reels_composer" in current_url or "composer" in current_url:
                    is_logged_in = True
                    self.log("Successfully detected logged-in session!")
                    break
                else:
                    self.log("Waiting for Composer page to load...")
                    await self.delay(3)

        if not is_logged_in:
            raise TimeoutError("Login timeout: User did not login to Meta Business Suite within 5 minutes.")

        # 2. Click "Thêm video" button first, then find file input
        self.log("Looking for 'Thêm video' / 'Add video' button...")
        
        # First, try to click "Thêm video" button using precise JS
        click_add_video_js = """
        (function() {
            // Find all spans containing exact text "Thêm video" or "Add video"
            const allSpans = document.querySelectorAll('span');
            for (const span of allSpans) {
                const text = span.textContent.trim();
                if (text === 'Thêm video' || text === 'Add video') {
                    // Click the closest clickable parent (div[role='button'] or the span itself)
                    const clickTarget = span.closest('[role="button"]') || span.closest('button') || span;
                    clickTarget.click();
                    return 'clicked:' + text;
                }
            }
            return 'not_found';
        })()
        """
        try:
            click_result = await self.page.evaluate(click_add_video_js)
            self.log(f"'Thêm video' button JS result: {click_result}")
        except Exception as e:
            self.log(f"JS click 'Thêm video' failed: {e}", "WARN")
            # Fallback to CDP click
            await self.cdp_click_text("Thêm video", timeout=5)
        
        await self.delay(3)
        
        # 3. Now find the file input and set file
        self.log(f"Uploading file: {video_path}")
        
        # Strategy A: Use CDP set_file_via_cdp (most reliable)
        file_set = await self.set_file_via_cdp("input[type='file'][accept*='video']", video_path)
        
        if not file_set:
            self.log("Video-specific file input not found, trying generic file input...", "WARN")
            file_set = await self.set_file_via_cdp("input[type='file']", video_path)
        
        if not file_set:
            # Strategy B: Try nodriver's native page.select (no pierce needed on Facebook)
            self.log("CDP file set failed, trying nodriver native select...", "WARN")
            try:
                file_input = await self.page.select("input[type='file']")
                if file_input:
                    await file_input.send_file(os.path.abspath(video_path))
                    file_set = True
                    self.log("File set via nodriver native select.")
            except Exception as e:
                self.log(f"Nodriver native select failed: {e}", "WARN")
        
        if not file_set:
            raise Exception("Could not find or set file on Facebook Composer page after all attempts.")
        
        self.log("Video file selected. Waiting for upload and processing (may take 15-30 seconds)...")
        await self.delay(20)

        # 4. Fill Description/Caption (using description)
        self.log("Entering caption...")
        caption_set = False
        
        # Try contenteditable div first (Reels composer)
        try:
            caption_js = """
            (function() {
                const editors = document.querySelectorAll('div[contenteditable="true"]');
                for (const ed of editors) {
                    if (ed.offsetParent !== null) {
                        ed.focus();
                        ed.textContent = '';
                        document.execCommand('insertText', false, %s);
                        return true;
                    }
                }
                return false;
            })()
            """ % json.dumps(description)
            caption_set = await self.page.evaluate(caption_js)
        except Exception as e:
            self.log(f"Caption via contenteditable failed: {e}", "WARN")
        
        if not caption_set:
            await self.js_type("div[contenteditable='true']", description, timeout=5)
            await self.js_type("textarea", description, timeout=5)
        
        self.log(f"Caption set: {description}")

        # 5. Navigate Steps (Next -> Next -> Share/Publish)
        for step in range(3):
            self.log(f"Attempting step navigation (Step {step+1}/3)...")
            clicked = False
            for btn_text in ["Tiếp", "Next", "Chia sẻ", "Share", "Đăng", "Publish"]:
                if not clicked:
                    clicked = await self.cdp_click_text(btn_text, timeout=3)
                    if clicked:
                        self.log(f"Clicked '{btn_text}' (Step {step+1}). Waiting...")
                        break
                
            if clicked:
                await self.delay(4)
            else:
                self.log("No further navigation or publish button found.", "INFO")
                break

        self.log("Waiting for post to complete...")
        await self.delay(10)

        self.log("Facebook upload finished successfully!")
        return "https://business.facebook.com/latest/reels" if publish_type == "reels" else "https://business.facebook.com/latest/posts"

    async def delete_post(self, title: str, post_url: Optional[str] = None) -> bool:
        """
        Automates deleting a video post by searching for its title/caption in Meta Business Suite Content posts page.
        """
        self.log("Navigating to Meta Business Suite Content page...")
        await self.page.get("https://business.facebook.com/latest/posts")
        await self.delay(5)

        # Wait for page load
        current_url = self.page.url
        if "login" in current_url:
            raise Exception("Please log in first to delete videos.")

        self.log("Searching for post title...")
        search_box = await self.wait_for_element("input[placeholder*='Tìm kiếm']")
        if not search_box:
            search_box = await self.wait_for_element("input[placeholder*='Search']")
        if not search_box:
            search_box = await self.wait_for_element("input[type='text']")

        if search_box:
            await search_box.click()
            await self.delay(1)
            await search_box.send_keys(title)
            await self.delay(4)
        else:
            self.log("Warning: Search box not found, attempting to find post text directly.", "WARN")

        self.log(f"Searching for text: '{title[:30]}'...")
        post_element = await self.wait_for_text(title[:30], timeout=15, log_err=False)
        if not post_element:
            self.log(f"Could not find any post with text snippet: '{title[:30]}'", "WARN")
            return False

        self.log("Found matching post. Clicking options/three-dots menu...")
        options_btn = await self.wait_for_element("button[aria-label*='Khác']", timeout=3, log_err=False)
        if not options_btn:
            options_btn = await self.wait_for_element("button[aria-label*='More']", timeout=3, log_err=False)
        if not options_btn:
            options_btn = await self.wait_for_element("div[role='button'] i[class*='ellipsis']", timeout=3, log_err=False)
            
        if options_btn:
            await options_btn.click()
            await self.delay(2)

        self.log("Clicking 'Xóa' (Delete)...")
        delete_btn = await self.wait_for_text("Xóa bài viết", timeout=5, log_err=False)
        if not delete_btn:
            delete_btn = await self.wait_for_text("Xóa thước phim", timeout=5, log_err=False)
        if not delete_btn:
            delete_btn = await self.wait_for_text("Xóa", timeout=5, log_err=False)
        if not delete_btn:
            delete_btn = await self.wait_for_text("Delete", timeout=5)

        if not delete_btn:
            raise Exception("Could not find Delete ('Xóa') action button in options menu.")

        await delete_btn.click()
        await self.delay(2)

        self.log("Confirming deletion in dialog...")
        confirm_btn = await self.wait_for_text("Xóa", timeout=5, log_err=False)
        if not confirm_btn:
            confirm_btn = await self.wait_for_text("Delete", timeout=5, log_err=False)
        if not confirm_btn:
            confirm_btn = await self.wait_for_element("button[class*='primary']", timeout=5, log_err=False)

        if confirm_btn:
            await confirm_btn.click()
        else:
            self.log("Warning: Confirm delete button not found in dialog.", "WARN")

        self.log("Waiting for deletion to finalize...")
        await self.delay(5)
        self.log("Post deleted successfully from Facebook.")
        return True
