import os
import asyncio
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
        file_input = await self.wait_for_element("input[type='file']")
        if not file_input:
            raise Exception("Could not find file input element on Facebook Composer page.")

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

        # 4. Navigate Steps (Next -> Next -> Share/Publish)
        # Regular Page Video Composer may only need one "Publish" button click or "Next" -> "Publish"
        # We try up to 3 times to click "Tiếp"/"Next"/"Chia sẻ"/"Share"/"Đăng"/"Publish"
        for step in range(3):
            self.log(f"Attempting step navigation (Step {step+1}/3)...")
            
            # Look for publish or next buttons
            next_btn = await self.wait_for_text("Tiếp", timeout=3, log_err=False)
            if not next_btn:
                next_btn = await self.wait_for_text("Next", timeout=3, log_err=False)
            if not next_btn:
                next_btn = await self.wait_for_text("Chia sẻ", timeout=3, log_err=False)
            if not next_btn:
                next_btn = await self.wait_for_text("Share", timeout=3, log_err=False)
            if not next_btn:
                next_btn = await self.wait_for_text("Đăng", timeout=3, log_err=False)
            if not next_btn:
                next_btn = await self.wait_for_text("Publish", timeout=3, log_err=False)
                
            if not next_btn:
                # Search inside buttons
                buttons = await self.page.select_all("button")
                for btn in buttons:
                    if btn.text and any(x in btn.text for x in ["Chia sẻ", "Share", "Publish", "Đăng", "Next", "Tiếp"]):
                        next_btn = btn
                        break
                        
            if next_btn:
                self.log(f"Found navigation button: '{next_btn.text or 'Button'}'. Clicking it...")
                await next_btn.click()
                await self.delay(4)
            else:
                self.log("No further navigation or publish button found. It might have finished.", "INFO")
                break

        self.log("Waiting for post to complete...")
        await self.delay(10)

        self.log("Facebook upload finished successfully!")
        return "https://business.facebook.com/latest/reels" if publish_type == "reels" else "https://business.facebook.com/latest/posts"
