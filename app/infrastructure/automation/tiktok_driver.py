import os
import asyncio
from typing import Optional
from app.infrastructure.automation.base_driver import BaseDriver
from app.adapters.gateways.uploader_gateway import UploaderGateway

class TiktokDriver(BaseDriver, UploaderGateway):
    async def upload(self, video_path: str, title: str, description: str, publish_type: str = "default") -> str:
        """
        Uploads a video to TikTok Studio.
        Uses description as the caption.
        Returns a confirmation message/URL if successful.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found at: {video_path}")

        self.log("Navigating to TikTok Upload...")
        await self.page.get("https://www.tiktok.com/tiktokstudio/upload?lang=vi-VN")
        await self.delay(5)

        # 1. Login verification & wait loop
        is_logged_in = False
        self.log("Checking login status...")
        
        for i in range(60):
            current_url = self.page.url
            if "login" in current_url or "signup" in current_url:
                self.log(f"Not logged in. Current URL: {current_url}. Waiting for manual login in the browser (attempt {i+1}/60)...", "WARN")
                await self.delay(5)
            else:
                file_input = await self.wait_for_element("input[type='file']", timeout=3, log_err=False)
                if file_input:
                    is_logged_in = True
                    self.log("Successfully detected logged-in session!")
                    break
                else:
                    self.log("Waiting for TikTok Studio dashboard or upload page to load...")
                    await self.delay(5)

        if not is_logged_in:
            raise TimeoutError("Login timeout: User did not login to TikTok Studio within 5 minutes.")

        # Check for unsaved draft modal prompt
        try:
            discard_btn = await self.js_click_text("Discard", timeout=3)
            if not discard_btn:
                discard_btn = await self.js_click_text("Bỏ qua", timeout=3)
            if discard_btn:
                self.log("Dismissed unsaved draft modal by clicking 'Discard'.")
                await self.delay(2)
        except Exception:
            pass

        # 2. Select File
        self.log(f"Uploading file: {video_path}")
        file_input = await self.wait_for_element_pierce("input[type='file']", timeout=15)
        if not file_input:
            file_input = await self.wait_for_element("input[type='file']", timeout=5)
            
        if not file_input:
            raise Exception("Could not find file input element on TikTok upload page.")

        await file_input.send_file(os.path.abspath(video_path))
        self.log("Video file selected. Waiting for upload and processing (may take 15-30 seconds)...")
        await self.delay(15)

        # 3. Fill Caption (using description)
        self.log("Entering caption...")
        caption_box = await self.wait_for_element_pierce("div[contenteditable='true']", timeout=10)
        if not caption_box:
            caption_box = await self.wait_for_element_pierce(".public-DraftEditor-content", timeout=5)
            
        if caption_box:
            await self.js_type("div[contenteditable='true']", description, timeout=5)
            self.log(f"Caption set: {description}")
        else:
            self.log("Warning: Caption input not found, skipping caption edit", "WARN")

        # 4. Wait for upload processing completion
        self.log("Waiting for video upload to finish processing...")
        await self.delay(10)

        # 5. Click Post Button
        self.log("Locating Post button (CDP click)...")
        post_clicked = await self.cdp_click("button.btn-post", timeout=5)
        if not post_clicked:
            post_clicked = await self.js_click_text("Đăng", timeout=5)
        if not post_clicked:
            post_clicked = await self.js_click_text("Post", timeout=5)
            
        if not post_clicked:
            self.log("Warning: Could not click Post button automatically.", "WARN")
        else:
            self.log("Post button clicked successfully!")
        
        self.log("Waiting for post to complete...")
        await self.delay(10)

        self.log("TikTok upload finished successfully!")
        return "https://www.tiktok.com/tiktokstudio/posts"

    async def delete_post(self, title: str, post_url: Optional[str] = None) -> bool:
        """
        Automates deleting a video by searching for its caption/title in TikTok Studio posts page.
        """
        self.log("Navigating to TikTok Studio Posts list...")
        await self.page.get("https://www.tiktok.com/tiktokstudio/posts")
        await self.delay(5)

        # Wait for page load
        current_url = self.page.url
        if "login" in current_url:
            raise Exception("Please log in first to delete videos.")

        self.log(f"Searching for text snippet: '{title[:30]}'...")
        clean_title = title[:30]
        video_element = await self.wait_for_text(clean_title, timeout=15, log_err=False)
        
        if not video_element:
            self.log(f"Could not find any post with text: '{clean_title}'", "WARN")
            return False

        self.log("Found matching post element. Locating options/more button...")
        delete_btn = await self.wait_for_text("Xóa", timeout=5, log_err=False)
        if not delete_btn:
            delete_btn = await self.wait_for_text("Delete", timeout=5, log_err=False)
            
        if not delete_btn:
            options_btn = await self.wait_for_element("button[class*='more']", timeout=3, log_err=False)
            if not options_btn:
                options_btn = await self.wait_for_element("button[class*='action']", timeout=3, log_err=False)
            if options_btn:
                await options_btn.click()
                await self.delay(2)
                delete_btn = await self.wait_for_text("Xóa", timeout=5, log_err=False)
                if not delete_btn:
                    delete_btn = await self.wait_for_text("Delete", timeout=5)
        
        if not delete_btn:
            raise Exception("Could not find the Delete ('Xóa') action button for this post.")

        self.log("Clicking Delete action...")
        await delete_btn.click()
        await self.delay(2)

        self.log("Confirming deletion in dialog...")
        confirm_btn = await self.wait_for_text("Xác nhận", timeout=5, log_err=False)
        if not confirm_btn:
            confirm_btn = await self.wait_for_text("Confirm", timeout=5, log_err=False)
        if not confirm_btn:
            confirm_btn = await self.wait_for_element("button[class*='primary']", timeout=5, log_err=False)
            
        if confirm_btn:
            await confirm_btn.click()
        else:
            self.log("Warning: Confirm button not found in dialog.", "WARN")

        self.log("Waiting for deletion to finalize...")
        await self.delay(5)
        self.log("Post deleted successfully from TikTok.")
        return True
