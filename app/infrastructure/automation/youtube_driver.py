import os
import asyncio
from app.infrastructure.automation.base_driver import BaseDriver
from app.adapters.gateways.uploader_gateway import UploaderGateway

class YoutubeDriver(BaseDriver, UploaderGateway):
    async def upload(self, video_path: str, title: str, description: str, publish_type: str = "shorts") -> str:
        """
        Uploads a video to YouTube Shorts / Videos.
        Returns the video URL if successful.
        """
        if not os.path.exists(video_path):
            raise FileNotFoundError(f"Video file not found at: {video_path}")

        self.log("Navigating to YouTube Studio...")
        await self.page.get("https://studio.youtube.com")
        await self.delay(3)

        # 1. Login verification & wait loop
        is_logged_in = False
        self.log("Checking login status...")
        
        # Wait up to 5 minutes (300 seconds) for manual login if not logged in
        for i in range(60):
            current_url = self.page.url
            if "accounts.google.com" in current_url:
                self.log(f"Not logged in. Current URL: {current_url}. Waiting for manual login in the browser (attempt {i+1}/60)...", "WARN")
                await self.delay(5)
            elif "studio.youtube.com" in current_url:
                # Check if dashboard loaded
                create_btn = await self.wait_for_element("#create-icon", timeout=3, log_err=False)
                if create_btn:
                    is_logged_in = True
                    self.log("Successfully detected logged-in session!")
                    break
                else:
                    self.log("On Studio page, waiting for dashboard to load...")
                    await self.delay(5)
            else:
                self.log(f"Unknown page: {current_url}. Waiting...")
                await self.delay(5)

        if not is_logged_in:
            raise TimeoutError("Login timeout: User did not login to YouTube Studio within 5 minutes.")

        # 2. Open Upload Dialog
        self.log("Clicking 'Create' button...")
        create_btn = await self.wait_for_element("#create-icon")
        await create_btn.click()
        await self.delay(1)

        self.log("Clicking 'Upload videos'...")
        upload_btn = await self.wait_for_element("#upload-button")
        if not upload_btn:
            upload_btn = await self.wait_for_text("Tải video lên", timeout=5, log_err=False)
        if not upload_btn:
            upload_btn = await self.wait_for_text("Upload videos", timeout=5)
            
        await upload_btn.click()
        await self.delay(2)

        # 3. Select File
        self.log(f"Uploading file: {video_path}")
        file_input = await self.wait_for_element("input[type='file'][name='Filedata']")
        if not file_input:
            file_input = await self.wait_for_element("input[type='file']")
            
        if not file_input:
            raise Exception("Could not find file input element on YouTube upload dialog.")

        # Set file input
        await file_input.set_file_input([os.path.abspath(video_path)])
        self.log("Video file selected. Waiting for upload form to initialize...")
        await self.delay(5)

        # 4. Fill Metadata (Details Step)
        self.log("Filling title and description...")
        
        # Title input
        title_box = await self.wait_for_element("div#title-textarea div#textbox")
        if title_box:
            await title_box.click()
            await title_box.send_keys(title)
        else:
            self.log("Warning: Title input not found, skipping title edit", "WARN")

        # Description input
        desc_box = await self.wait_for_element("div#description-textarea div#textbox")
        if desc_box:
            await desc_box.click()
            await desc_box.send_keys(description)

        # Audience: 'Not made for kids' radio button
        self.log("Selecting audience option 'Not made for kids'...")
        kids_radio = await self.wait_for_element('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MADE_FOR_KIDS"]')
        if kids_radio:
            await kids_radio.click()
        else:
            kids_radio = await self.wait_for_text("Không, đây không phải nội dung dành cho trẻ em", timeout=5, log_err=False)
            if not kids_radio:
                kids_radio = await self.wait_for_text("No, it's not made for kids", timeout=5)
            if kids_radio:
                await kids_radio.click()

        await self.delay(2)

        # 5. Navigate through steps (Click Next)
        self.log("Navigating Details -> Video Elements...")
        next_btn = await self.wait_for_element("#next-button")
        await next_btn.click()
        await self.delay(2)

        self.log("Navigating Video Elements -> Checks...")
        next_btn = await self.wait_for_element("#next-button")
        await next_btn.click()
        await self.delay(2)

        self.log("Navigating Checks -> Visibility...")
        next_btn = await self.wait_for_element("#next-button")
        await next_btn.click()
        await self.delay(2)

        # 6. Publish / Visibility Step
        self.log("Setting visibility to Public...")
        public_radio = await self.wait_for_element('tp-yt-paper-radio-button[name="PUBLIC"]')
        if public_radio:
            await public_radio.click()
        else:
            public_radio = await self.wait_for_text("Công khai", timeout=5, log_err=False)
            if not public_radio:
                public_radio = await self.wait_for_text("Public", timeout=5)
            if public_radio:
                await public_radio.click()

        await self.delay(2)

        # 7. Get Video Link before publishing
        video_url = ""
        try:
            url_elem = await self.wait_for_element("a.style-scope.ytd-video-share-url", timeout=10, log_err=False)
            if url_elem:
                video_url = url_elem.text
                self.log(f"Found YouTube Video URL: {video_url}")
        except Exception:
            pass

        # 8. Click Done / Publish
        self.log("Clicking Publish/Done button...")
        done_btn = await self.wait_for_element("#done-button")
        if done_btn:
            await done_btn.click()
        else:
            done_btn = await self.wait_for_text("Xuất bản", timeout=5, log_err=False)
            if not done_btn:
                done_btn = await self.wait_for_text("Publish", timeout=5)
            if done_btn:
                await done_btn.click()

        self.log("Waiting for publish completion dialog...")
        await self.delay(7)

        # Double check if we can get the URL if we didn't get it before
        if not video_url:
            try:
                link_elem = await self.wait_for_element("span.style-scope.ytcp-video-info", timeout=5, log_err=False)
                if link_elem:
                    video_url = link_elem.text
            except Exception:
                pass

        self.log("YouTube upload finished successfully!")
        return video_url or "https://youtube.com/studio"
