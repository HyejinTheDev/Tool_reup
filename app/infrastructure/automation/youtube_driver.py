import os
import asyncio
from typing import Optional
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
            current_url = ""
            try:
                current_url = await self.page.evaluate("window.location.href")
            except Exception:
                current_url = self.page.url or ""

            # Check if dashboard loaded (do it upfront to bypass any URL sync lag)
            create_btn = await self.wait_for_element_pierce("#create-icon", timeout=3)
            if create_btn:
                is_logged_in = True
                self.log("Successfully detected logged-in session!")
                break

            if "accounts.google.com" in current_url:
                self.log(f"Not logged in. Current URL: {current_url}. Waiting for manual login in the browser (attempt {i+1}/60)...", "WARN")
                await self.delay(5)
            elif "studio.youtube.com" in current_url:
                self.log("On Studio page, waiting for dashboard to load...")
                await self.delay(5)
            else:
                self.log(f"Unknown page: {current_url}. Waiting...")
                await self.delay(5)

        if not is_logged_in:
            raise TimeoutError("Login timeout: User did not login to YouTube Studio within 5 minutes.")

        # 2. Open Upload Dialog
        self.log("Clicking 'Create' button...")
        create_btn = await self.wait_for_element_pierce("#create-icon")
        await create_btn.click()
        await self.delay(1)

        self.log("Clicking 'Upload videos'...")
        upload_btn = await self.wait_for_element_pierce("#upload-button")
        if not upload_btn:
            upload_btn = await self.wait_for_text("Tải video lên", timeout=5, log_err=False)
        if not upload_btn:
            upload_btn = await self.wait_for_text("Upload videos", timeout=5)
            
        await upload_btn.click()
        await self.delay(2)

        # 3. Select File
        self.log(f"Uploading file: {video_path}")
        file_input = await self.wait_for_element_pierce("input[type='file'][name='Filedata']")
        if not file_input:
            file_input = await self.wait_for_element_pierce("input[type='file']")
            
        if not file_input:
            raise Exception("Could not find file input element on YouTube upload dialog.")

        # Set file input
        await file_input.set_file_input([os.path.abspath(video_path)])
        self.log("Video file selected. Waiting for upload form to initialize...")
        await self.delay(5)

        # 4. Fill Metadata (Details Step)
        self.log("Filling title and description...")
        
        # Title input
        title_box = await self.wait_for_element_pierce("div#title-textarea div#textbox")
        if title_box:
            await title_box.click()
            await title_box.send_keys(title)
        else:
            self.log("Warning: Title input not found, skipping title edit", "WARN")

        # Description input
        desc_box = await self.wait_for_element_pierce("div#description-textarea div#textbox")
        if desc_box:
            await desc_box.click()
            await desc_box.send_keys(description)

        # Audience: 'Not made for kids' radio button
        self.log("Selecting audience option 'Not made for kids'...")
        kids_radio = await self.wait_for_element_pierce('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MADE_FOR_KIDS"]')
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
        next_btn = await self.wait_for_element_pierce("#next-button")
        await next_btn.click()
        await self.delay(2)

        self.log("Navigating Video Elements -> Checks...")
        next_btn = await self.wait_for_element_pierce("#next-button")
        await next_btn.click()
        await self.delay(2)

        self.log("Navigating Checks -> Visibility...")
        next_btn = await self.wait_for_element_pierce("#next-button")
        await next_btn.click()
        await self.delay(2)

        # 6. Publish / Visibility Step
        self.log("Setting visibility to Public...")
        public_radio = await self.wait_for_element_pierce('tp-yt-paper-radio-button[name="PUBLIC"]')
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
            url_elem = await self.wait_for_element_pierce("a.style-scope.ytd-video-share-url", timeout=10)
            if url_elem:
                video_url = url_elem.text
                self.log(f"Found YouTube Video URL: {video_url}")
        except Exception:
            pass

        # 8. Click Done / Publish
        self.log("Clicking Publish/Done button...")
        done_btn = await self.wait_for_element_pierce("#done-button")
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
                link_elem = await self.wait_for_element_pierce("span.style-scope.ytcp-video-info", timeout=5)
                if link_elem:
                    video_url = link_elem.text
            except Exception:
                pass

        self.log("YouTube upload finished successfully!")
        return video_url or "https://youtube.com/studio"

    async def delete_post(self, title: str, post_url: Optional[str] = None) -> bool:
        """
        Automates deleting a video by searching for its title on YouTube Studio content page.
        """
        self.log("Navigating to YouTube Studio...")
        await self.page.get("https://studio.youtube.com")
        await self.delay(5)

        # Wait for channel uploads page to be active or redirect to it
        current_url = self.page.url
        if "studio.youtube.com" not in current_url:
            raise Exception("Please log in first to delete videos.")

        # Resolve direct channel content page URL
        if "/videos/upload" not in current_url:
            target_url = current_url.split("?")[0]
            if not target_url.endswith("/"):
                target_url += "/"
            await self.page.get(target_url + "videos/upload")
            await self.delay(5)

        self.log("On Content uploads page. Searching for video title...")
        search_box = await self.wait_for_element_pierce("input#search-input")
        if not search_box:
            search_box = await self.wait_for_element_pierce("input[placeholder*='Tìm kiếm']")
        if not search_box:
            search_box = await self.wait_for_element_pierce("input[placeholder*='Search']")

        if not search_box:
            raise Exception("Could not find search bar in YouTube Studio Content page.")

        await search_box.click()
        await self.delay(1)
        await search_box.send_keys(title)
        await self.delay(3) # Wait for filtering results

        self.log("Locating search result video row...")
        video_row = await self.wait_for_element_pierce("ytcp-video-row", timeout=10)
        if not video_row:
            self.log(f"No video found matching title: '{title}'", "WARN")
            return False

        self.log("Hovering over video row to reveal action buttons...")
        await video_row.click()
        await self.delay(1)

        options_btn = await self.wait_for_element_pierce("ytcp-icon-button[id='options-button']")
        if not options_btn:
            options_btn = await self.wait_for_element_pierce("ytcp-icon-button.style-scope.ytcp-video-row")
            
        if not options_btn:
            buttons = await video_row.select_all("ytcp-icon-button")
            for btn in buttons:
                if "options" in str(btn.attributes) or "options" in btn.id:
                    options_btn = btn
                    break

        if not options_btn:
            raise Exception("Could not locate the Options (three-dots) button on the video row.")

        self.log("Clicking Options button...")
        await options_btn.click()
        await self.delay(2)

        self.log("Clicking 'Delete forever' (Xóa vĩnh viễn)...")
        delete_option = await self.wait_for_text("Xóa vĩnh viễn", timeout=5, log_err=False)
        if not delete_option:
            delete_option = await self.wait_for_text("Delete forever", timeout=5)
            
        if not delete_option:
            raise Exception("Could not find 'Delete forever' item in the options menu.")

        await delete_option.click()
        await self.delay(2)

        self.log("Checking confirmation box...")
        confirm_checkbox = await self.wait_for_element_pierce("tp-yt-paper-checkbox#confirm-checkbox")
        if not confirm_checkbox:
            confirm_checkbox = await self.wait_for_element_pierce("tp-yt-paper-checkbox")
        if confirm_checkbox:
            await confirm_checkbox.click()
        else:
            self.log("Warning: Confirmation checkbox not found. Trying to proceed.", "WARN")

        await self.delay(1)

        self.log("Confirming deletion...")
        confirm_delete_btn = await self.wait_for_element_pierce("ytcp-button#delete-button")
        if not confirm_delete_btn:
            confirm_delete_btn = await self.wait_for_text("XÓA VĨNH VIỄN", timeout=5, log_err=False)
        if not confirm_delete_btn:
            confirm_delete_btn = await self.wait_for_text("DELETE FOREVER", timeout=5)
            
        if not confirm_delete_btn:
            raise Exception("Could not find confirm delete button in dialog.")

        await confirm_delete_btn.click()
        self.log("Waiting for deletion process to finish...")
        await self.delay(8)

        self.log("Video deleted successfully from YouTube.")
        return True
