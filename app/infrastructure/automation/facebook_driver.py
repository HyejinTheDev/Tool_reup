import os
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
            current_url = self.page.url
            if "login" in current_url or "facebook.com/login" in current_url:
                self.log(f"Not logged in. Current URL: {current_url}. Waiting for manual login in the browser (attempt {i+1}/60)...", "WARN")
                await self.delay(5)
            else:
                file_input = await self.wait_for_element("input[type='file']", timeout=3, log_err=False)
                if file_input:
                    is_logged_in = True
                    self.log("Successfully detected logged-in session!")
                    break
                else:
                    self.log("Waiting for Composer to load...")
                    await self.delay(5)

        if not is_logged_in:
            raise TimeoutError("Login timeout: User did not login to Meta Business Suite within 5 minutes.")

        # 2. Select File
        self.log(f"Uploading file: {video_path}")
        file_input = await self.wait_for_element_pierce("input[type='file']", timeout=10)
        if not file_input:
            # Try clicking 'Thêm video' / 'Add video' button to reveal file input
            self.log("Clicking 'Thêm video' / 'Add video' button (CDP click)...")
            await self.cdp_click_text("Thêm video", timeout=3)
            await self.cdp_click_text("Add video", timeout=3)
            await self.delay(2)
            file_input = await self.wait_for_element_pierce("input[type='file']", timeout=10)
            
        if not file_input:
            file_input = await self.wait_for_element("input[type='file']", timeout=5)
            
        if not file_input:
            raise Exception("Could not find file input element on Facebook Composer page.")

        await file_input.send_file(os.path.abspath(video_path))
        self.log("Video file selected. Waiting for upload and processing (may take 15-30 seconds)...")
        await self.delay(20)

        # 3. Fill Description/Caption (using description)
        self.log("Entering caption...")
        await self.js_type("div[contenteditable='true']", description, timeout=5)
        await self.js_type("textarea", description, timeout=5)
        self.log(f"Caption set: {description}")

        # 4. Navigate Steps (Next -> Next -> Share/Publish)
        for step in range(3):
            self.log(f"Attempting step navigation (Step {step+1}/3)...")
            clicked = await self.cdp_click_text("Tiếp", timeout=3)
            if not clicked:
                clicked = await self.cdp_click_text("Next", timeout=3)
            if not clicked:
                clicked = await self.cdp_click_text("Chia sẻ", timeout=3)
            if not clicked:
                clicked = await self.cdp_click_text("Share", timeout=3)
            if not clicked:
                clicked = await self.cdp_click_text("Đăng", timeout=3)
            if not clicked:
                clicked = await self.cdp_click_text("Publish", timeout=3)
                
            if clicked:
                self.log(f"Navigation button clicked (Step {step+1}). Waiting...")
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
