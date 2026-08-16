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

            dashboard_loaded = False
            try:
                js_check = """
                (function() {
                    function hasEl(sel, node = document) {
                        if (node.querySelector(sel)) return true;
                        const all = node.querySelectorAll('*');
                        for (const child of all) {
                            if (child.shadowRoot && hasEl(sel, child.shadowRoot)) return true;
                        }
                        return false;
                    }
                    return hasEl('#create-icon') || hasEl('#upload-button') || hasEl('#menu-item-dashboard');
                })()
                """
                dashboard_loaded = await self.page.evaluate(js_check)
            except Exception:
                pass
                        
            if dashboard_loaded:
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
        self.log("Opening YouTube Upload Dialog...")
        current_url = self.page.url
        if "?d=ud" not in current_url and "&d=ud" not in current_url:
            upload_url = current_url + ("&d=ud" if "?" in current_url else "?d=ud")
            self.log(f"Navigating to upload trigger URL: {upload_url}")
            await self.page.get(upload_url)
            await self.delay(3)

        # Fallback click trigger if dialog isn't visible yet
        dialog = await self.wait_for_element_pierce("ytcp-uploads-dialog", timeout=3, log_err=False)
        if not dialog:
            self.log("Dialog not popped automatically by URL, attempting deep ShadowRoot button clicks...")
            js_trigger = """
            (function() {
                const createBtn = document.querySelector('#create-icon');
                if (createBtn) {
                    const inner = createBtn.shadowRoot ? createBtn.shadowRoot.querySelector('button, #button') : createBtn;
                    if (inner) inner.click();
                    return true;
                }
                const uploadBtn = document.querySelector('#upload-icon') || document.querySelector('#upload-button');
                if (uploadBtn) {
                    const inner = uploadBtn.shadowRoot ? uploadBtn.shadowRoot.querySelector('button, #button') : uploadBtn;
                    if (inner) inner.click();
                    return true;
                }
                return false;
            })()
            """
            try:
                await self.page.evaluate(js_trigger)
                await self.delay(2)
                await self.js_click("#upload-button", timeout=3)
            except Exception as e:
                self.log(f"Warning on JS trigger fallback: {e}", "WARN")

        # 3. Select File
        self.log(f"Uploading file: {video_path}")
        file_input = await self.wait_for_element_pierce("input[type='file']", timeout=15)
        if not file_input:
            raise Exception("Could not find file input element on YouTube upload dialog.")

        # Set file input
        await file_input.send_file(os.path.abspath(video_path))
        self.log("Video file selected. Waiting for upload form to initialize...")
        await self.delay(8)

        # 4. Fill Metadata (Details Step)
        self.log("Filling title and description...")
        
        # Title input
        title_typed = await self.js_type("#title-textarea #textbox", title)
        if not title_typed:
            self.log("Warning: Title input not found, skipping title edit", "WARN")

        # Description input
        await self.js_type("#description-textarea #textbox", description)

        # Chờ 3 giây để các sự kiện Polymer được liên kết hoàn toàn vào nút tròn
        await self.delay(3)

        # Audience: 'Not made for kids' radio button (dùng CDP mouse click thật)
        self.log("Selecting audience option 'Not made for kids' (CDP click)...")
        kids_clicked = await self.cdp_click('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]')
        if not kids_clicked:
            self.log("CDP click failed, falling back to JS click...", "WARN")
            kids_clicked = await self.js_click('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]')
        if not kids_clicked:
            kids_clicked = await self.js_click_text("No, it's not made for kids", timeout=5)
        if not kids_clicked:
            await self.js_click_text("Không, đây không phải nội dung dành cho trẻ em", timeout=5)

        await self.delay(2)

        # DIAGNOSTIC: Kiểm tra trạng thái radio sau khi click
        try:
            radio_status = await self.page.evaluate("""
                (function() {
                    function findElements(selector, startNode = document, results = []) {
                        const el = startNode.querySelector(selector);
                        if (el) results.push(el);
                        const all = startNode.querySelectorAll('*');
                        for (const node of all) {
                            if (node.shadowRoot) findElements(selector, node.shadowRoot, results);
                        }
                        return results;
                    }
                    function getStartNode() {
                        const dialogs = document.querySelectorAll('ytcp-uploads-dialog');
                        for (let i = dialogs.length - 1; i >= 0; i--) {
                            const d = dialogs[i];
                            if (d.offsetWidth || d.offsetHeight || d.getClientRects().length) {
                                return d.shadowRoot || d;
                            }
                        }
                        return document;
                    }
                    const startNode = getStartNode();
                    const matches = findElements('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]', startNode);
                    if (matches.length === 0) return 'NOT_FOUND';
                    const el = matches[matches.length - 1];
                    const checked = el.checked;
                    const ariaChecked = el.getAttribute('aria-checked');
                    const active = el.hasAttribute('active');
                    
                    // Also check Next button status
                    const nextBtns = findElements('#next-button', startNode);
                    let nextDisabled = 'unknown';
                    if (nextBtns.length > 0) {
                        const nb = nextBtns[nextBtns.length - 1];
                        nextDisabled = nb.disabled || nb.getAttribute('aria-disabled') === 'true';
                    }
                    
                    return 'checked=' + checked + ' aria-checked=' + ariaChecked + ' active=' + active + ' next-disabled=' + nextDisabled;
                })()
            """)
            self.log(f"DIAGNOSTIC: Radio button status after click: {radio_status}")
        except Exception as e:
            self.log(f"DIAGNOSTIC error: {e}", "WARN")

        # Nếu radio chưa được chọn, thử phương thức nodriver element.click()
        try:
            is_checked = await self.page.evaluate("""
                (function() {
                    function findElements(selector, startNode = document, results = []) {
                        const el = startNode.querySelector(selector);
                        if (el) results.push(el);
                        const all = startNode.querySelectorAll('*');
                        for (const node of all) {
                            if (node.shadowRoot) findElements(selector, node.shadowRoot, results);
                        }
                        return results;
                    }
                    function getStartNode() {
                        const dialogs = document.querySelectorAll('ytcp-uploads-dialog');
                        for (let i = dialogs.length - 1; i >= 0; i--) {
                            const d = dialogs[i];
                            if (d.offsetWidth || d.offsetHeight || d.getClientRects().length) return d.shadowRoot || d;
                        }
                        return document;
                    }
                    const matches = findElements('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]', getStartNode());
                    if (matches.length === 0) return false;
                    const el = matches[matches.length - 1];
                    return el.getAttribute('aria-checked') === 'true';
                })()
            """)
            if not is_checked:
                self.log("Radio NOT checked after all click attempts! Trying nodriver element.click()...", "WARN")
                element = await self.wait_for_element_pierce('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]', timeout=5)
                if element:
                    await element.click()
                    self.log("nodriver element.click() executed!")
                    await self.delay(2)
                else:
                    self.log("Could not find element via select_pierce!", "WARN")
            else:
                self.log("Radio IS checked - audience selection SUCCESSFUL!")
        except Exception as e:
            self.log(f"Fallback click error: {e}", "WARN")

        # 5. Navigate through steps (Click Next) - dùng CDP click cho nút Next
        self.log("Navigating Details -> Video Elements...")
        await self.cdp_click("#next-button", timeout=90)
        await self.delay(2)

        self.log("Navigating Video Elements -> Checks...")
        await self.cdp_click("#next-button", timeout=90)
        await self.delay(2)

        self.log("Navigating Checks -> Visibility...")
        await self.cdp_click("#next-button", timeout=90)
        await self.delay(2)

        # 6. Publish / Visibility Step (dùng CDP click cho radio button Public)
        self.log("Setting visibility to Public (CDP click)...")
        pub_clicked = await self.cdp_click('tp-yt-paper-radio-button[name="PUBLIC"]')
        if not pub_clicked:
            pub_clicked = await self.js_click('tp-yt-paper-radio-button[name="PUBLIC"]')
        if not pub_clicked:
            pub_clicked = await self.js_click_text("Public", timeout=5)
        if not pub_clicked:
            await self.js_click_text("Công khai", timeout=5)
        await self.delay(2)

        # 7. Get Video Link before publishing
        video_url = ""
        try:
            video_url = await self.page.evaluate("""
                (function() {
                    const el = document.querySelector('a.style-scope.ytd-video-share-url') || 
                               document.querySelector('span.style-scope.ytcp-video-info');
                    return el ? el.href || el.innerText : '';
                })()
            """)
            if video_url:
                self.log(f"Found YouTube Video URL: {video_url}")
        except Exception:
            pass

        # 8. Click Done / Publish (dùng CDP click)
        self.log("Clicking Publish/Done button (CDP click)...")
        done_clicked = await self.cdp_click("#done-button", timeout=90)
        if not done_clicked:
            done_clicked = await self.js_click("#done-button", timeout=90)
        if not done_clicked:
            done_clicked = await self.js_click_text("Publish", timeout=90)
        if not done_clicked:
            done_clicked = await self.js_click_text("Xuất bản", timeout=90)
        if not done_clicked:
            await self.cdp_click("ytcp-button#save-button", timeout=90)

        self.log("Waiting for publish completion dialog...")
        await self.delay(7)

        # Double check if we can get the URL if we didn't get it before
        if not video_url:
            try:
                video_url = await self.page.evaluate("""
                    (function() {
                        const el = document.querySelector('span.style-scope.ytcp-video-info') ||
                                   document.querySelector('a.style-scope.ytd-video-share-url');
                        return el ? el.innerText || el.href : '';
                    })()
                """)
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
