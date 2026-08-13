import os
import asyncio
from app.infrastructure.automation.base_driver import BaseDriver
from app.adapters.gateways.uploader_gateway import UploaderGateway

class FacebookDriver(BaseDriver, UploaderGateway):
    async def upload(self, video_path: str, title: str, description: str) -> str:
        """
        Uploads a video to Facebook Reels via Meta Business Suite.
        Uses description as the caption.
        Returns a confirmation message/URL if successful.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found at: {video_path}")

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
                    self.log("Waiting for Meta Business Suite Reels Composer to load...")
                    await self.delay(5)

        if not is_logged_in:
            raise TimeoutError("Login timeout: User did not login to Meta Business Suite within 5 minutes.")

        # 2. Select File
        self.log(f"Uploading file: {video_path}")
        file_input = await self.wait_for_element("input[type='file']")
        if not file_input:
            raise Exception("Could not find file input element on Facebook Reels Composer page.")

        await file_input.set_file_input([os.path.abspath(video_path)])
        self.log("Video file selected. Waiting for upload and processing (may take 15-30 seconds)...")
        await self.delay(20)

        # 3. Fill Description/Caption (using description)
        self.log("Entering caption...")
        caption_box = await self.wait_for_element("div[contenteditable='true']")
        if not caption_box:
            caption_box = await self.wait_for_element("textarea")
            
        if caption_box:
            await caption_box.click()
            await self.delay(1)
            await caption_box.send_keys(description)
            self.log(f"Caption set: {description}")
        else:
            self.log("Warning: Caption input not found, skipping caption edit", "WARN")

        # 4. Navigate Steps (Next -> Next -> Share)
        for step in range(2):
            self.log(f"Clicking Next button (Step {step+1}/2)...")
            next_btn = await self.wait_for_text("Tiếp", timeout=5, log_err=False)
            if not next_btn:
                next_btn = await self.wait_for_text("Next", timeout=5, log_err=False)
            if not next_btn:
                buttons = await self.page.select_all("button")
                for btn in buttons:
                    if btn.text and ("Next" in btn.text or "Tiếp" in btn.text):
                        next_btn = btn
                        break
            
            if next_btn:
                await next_btn.click()
                await self.delay(3)
            else:
                self.log(f"Next button not found in step {step+1}, attempting to proceed...", "WARN")

        # 5. Share/Publish Reel
        self.log("Locating Share/Publish button...")
        share_btn = await self.wait_for_text("Chia sẻ", timeout=5, log_err=False)
        if not share_btn:
            share_btn = await self.wait_for_text("Share", timeout=5, log_err=False)
        if not share_btn:
            share_btn = await self.wait_for_text("Đăng", timeout=5, log_err=False)
        if not share_btn:
            share_btn = await self.wait_for_text("Publish", timeout=5, log_err=False)
            
        if not share_btn:
            buttons = await self.page.select_all("button")
            for btn in buttons:
                if btn.text and any(x in btn.text for x in ["Chia sẻ", "Share", "Publish", "Đăng"]):
                    share_btn = btn
                    break

        if not share_btn:
            raise Exception("Could not locate the 'Share'/'Chia sẻ' button.")

        self.log("Clicking Share button...")
        await share_btn.click()
        
        self.log("Waiting for post to complete...")
        await self.delay(10)

        self.log("Facebook Reels upload finished successfully!")
        return "https://business.facebook.com/latest/reels"
