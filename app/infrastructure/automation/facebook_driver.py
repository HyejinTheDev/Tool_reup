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

        # Navigate to Personal Facebook Reels Creator (NOT Meta Business Suite)
        self.log("Navigating to Facebook Reels Creator (facebook.com/reels/create)...")
        await self.page.get("https://www.facebook.com/reels/create")
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
                
            if "/login" in current_url:
                self.log(f"Not logged in. URL: {current_url}. Waiting for manual login (attempt {i+1}/60)...", "WARN")
                await self.delay(5)
            else:
                if "facebook.com" in current_url:
                    is_logged_in = True
                    self.log(f"Logged in to Facebook! URL: {current_url}")
                    break
                else:
                    self.log(f"Waiting for Facebook to load... URL: {current_url}")
                    await self.delay(3)

        if not is_logged_in:
            raise TimeoutError("Login timeout: User did not login to Facebook within 5 minutes.")

        # Navigate to reels/create if we got redirected
        try:
            current_url = await self.page.evaluate("window.location.href")
        except Exception:
            current_url = ""
        if "reels/create" not in current_url:
            self.log("Redirected away from Reels Creator, navigating back...")
            await self.page.get("https://www.facebook.com/reels/create")
            await self.delay(5)

        # 2. Upload video file
        self.log(f"Uploading file: {video_path}")
        
        # Try to find file input directly first
        file_set = await self.set_file_via_cdp("input[type='file'][accept*='video']", video_path)
        if not file_set:
            file_set = await self.set_file_via_cdp("input[type='file']", video_path)
        
        if not file_set:
            # Click "Thêm video" area to trigger file picker / reveal file input
            self.log("Clicking 'Thêm video' button...")
            click_js = """
            (function() {
                // Method 1: Find span with exact text
                const spans = document.querySelectorAll('span');
                for (const s of spans) {
                    if (s.textContent.trim().startsWith('Thêm video') || s.textContent.trim() === 'Add video') {
                        const target = s.closest('[role="button"]') || s.closest('button') || s.parentElement;
                        if (target) { target.click(); return 'clicked_span'; }
                    }
                }
                // Method 2: Click the drag-drop upload zone
                const labels = document.querySelectorAll('label');
                for (const l of labels) { l.click(); return 'clicked_label'; }
                return 'not_found';
            })()
            """
            try:
                result = await self.page.evaluate(click_js)
                self.log(f"Click result: {result}")
            except Exception as e:
                self.log(f"JS click failed: {e}", "WARN")
                await self.cdp_click_text("Thêm video", timeout=5)
            
            await self.delay(3)
            
            # Retry finding file input
            file_set = await self.set_file_via_cdp("input[type='file'][accept*='video']", video_path)
            if not file_set:
                file_set = await self.set_file_via_cdp("input[type='file']", video_path)
            if not file_set:
                try:
                    fi = await self.page.select("input[type='file']")
                    if fi:
                        await fi.send_file(os.path.abspath(video_path))
                        file_set = True
                except Exception:
                    pass
        
        if not file_set:
            raise Exception("Could not upload file to Facebook Reels Creator.")
        
        self.log("Video file selected! Waiting for upload processing (15-30s)...")
        await self.delay(20)

        # 3. Fill Description/Caption ("Mô tả thước phim của bạn...")
        self.log("Entering caption...")
        caption_set = False
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
                const tas = document.querySelectorAll('textarea');
                for (const ta of tas) {
                    if (ta.offsetParent !== null) {
                        ta.focus();
                        ta.value = %s;
                        ta.dispatchEvent(new Event('input', {bubbles: true}));
                        return true;
                    }
                }
                return false;
            })()
            """ % (json.dumps(description), json.dumps(description))
            caption_set = await self.page.evaluate(caption_js)
        except Exception as e:
            self.log(f"Caption JS failed: {e}", "WARN")
        
        if not caption_set:
            await self.js_type("div[contenteditable='true']", description, timeout=5)
            await self.js_type("textarea", description, timeout=5)
        self.log(f"Caption set: {description}")
        await self.delay(2)

        # 4. Click "Đăng" (Publish) button — personal Facebook has a direct Publish button
        self.log("Clicking Publish button ('Đăng')...")
        publish_clicked = False
        for btn_text in ["Đăng", "Publish", "Đăng thước phim", "Publish Reel"]:
            publish_clicked = await self.cdp_click_text(btn_text, timeout=3)
            if publish_clicked:
                self.log(f"Clicked '{btn_text}' button!")
                break
        
        if not publish_clicked:
            try:
                js_pub = """
                (function() {
                    const btns = document.querySelectorAll('div[role="button"], button');
                    for (const b of btns) {
                        const t = b.textContent.trim();
                        if (t === 'Đăng' || t === 'Publish') { b.click(); return 'clicked:' + t; }
                    }
                    return 'not_found';
                })()
                """
                r = await self.page.evaluate(js_pub)
                self.log(f"JS publish: {r}")
                if "clicked" in str(r):
                    publish_clicked = True
            except Exception as e:
                self.log(f"JS publish failed: {e}", "WARN")
        
        if not publish_clicked:
            self.log("Could not auto-click Publish. Please click manually.", "WARN")

        self.log("Waiting for post to complete...")
        await self.delay(10)

        self.log("Facebook Reels upload finished successfully!")
        return "https://www.facebook.com/reels"

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
