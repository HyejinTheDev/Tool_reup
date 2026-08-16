import os
import asyncio
import logging
import json
import nodriver as uc
from typing import Callable, Optional

# Setup standard logging
logger = logging.getLogger("base_driver")

class BaseDriver:
    def __init__(self, account_id: str, profile_name: str, chrome_path: Optional[str] = None, headless: bool = False, log_callback: Optional[Callable[[str], None]] = None, browser = None, page = None):
        self.account_id = account_id
        self.profile_name = profile_name
        self.chrome_path = chrome_path
        self.headless = headless
        self.log_callback = log_callback
        self.browser = browser
        self.page = page
        self.is_shared_browser = browser is not None

    def log(self, message: str, level: str = "INFO"):
        formatted_message = f"[{level}] [{self.account_id}] {message}"
        logger.info(formatted_message)
        if self.log_callback:
            try:
                self.log_callback(formatted_message)
            except Exception as e:
                logger.error(f"Error calling log callback: {e}")

    def find_chrome_executable(self) -> str:
        """Find Chrome executable path on Windows."""
        if self.chrome_path and os.path.exists(self.chrome_path):
            return self.chrome_path

        standard_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
        ]

        for path in standard_paths:
            if os.path.exists(path):
                self.log(f"Found Chrome at: {path}")
                return path

        raise FileNotFoundError("Could not find Google Chrome installation. Please install Chrome or configure its path in settings.")

    async def start_browser(self):
        """Starts Chrome browser with account profile using nodriver."""
        if self.is_shared_browser and self.browser:
            self.log("Using shared Chrome browser window (multi-tab mode)...")
            if not self.page:
                self.page = await self.browser.get("about:blank", new_tab=True)
            import nodriver.cdp.dom as dom
            try:
                await self.page.send(dom.enable())
                await self.page.send(dom.get_document())
            except Exception as e:
                self.log(f"Warning syncing DOM on tab: {e}", "WARN")
            return

        chrome_exe = self.find_chrome_executable()
        
        # Profile directory inside project workspace (root directory)
        project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        profiles_dir = os.path.join(project_dir, "chrome_profiles")
        os.makedirs(profiles_dir, exist_ok=True)
        
        if os.path.isabs(self.profile_name) or "\\" in self.profile_name or "/" in self.profile_name:
            profile_path = os.path.abspath(self.profile_name)
        else:
            profile_path = os.path.join(profiles_dir, self.profile_name)
            
        # Dọn dẹp tệp khóa SingletonLock của Chrome từ các lần tắt đột ngột trước đó
        lock_file = os.path.join(profile_path, "SingletonLock")
        if os.path.exists(lock_file):
            try:
                os.remove(lock_file)
                self.log("Đã dọn dẹp tệp khóa SingletonLock của Chrome từ lần chạy trước.", "INFO")
            except Exception as e:
                self.log(f"Cảnh báo: Không thể xóa tệp khóa SingletonLock: {e}", "WARN")
            
        self.log(f"Starting browser with profile path: {profile_path} (Headless: {self.headless})")

        # Config nodriver start
        try:
            # nodriver start method
            self.browser = await uc.start(
                browser_executable_path=chrome_exe,
                user_data_dir=profile_path,
                headless=self.headless,
                browser_args=[
                    "--start-maximized",
                    "--window-size=1920,1080",
                    "--no-first-run",
                    "--no-default-browser-check"
                ]
            )
            # nodriver starts with a default main tab
            self.page = self.browser.main_tab
            
            # Close any other restored/background tabs to prevent "ghost tabs"
            try:
                for tab in list(self.browser.tabs):
                    if tab != self.page:
                        await tab.close()
            except Exception as e:
                self.log(f"Warning: Failed to close background tabs: {e}", "WARN")
                
            # Enable DOM domain and fetch document once at startup
            import nodriver.cdp.dom as dom
            await self.page.send(dom.enable())
            await self.page.send(dom.get_document())
            
            self.log("Browser started successfully.")
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            self.log(f"Failed to start browser. Exception: {type(e)} - {str(e)}\nTraceback:\n{tb_str}", "ERROR")
            raise e

    async def close_browser(self):
        """Close browser safely."""
        if self.is_shared_browser:
            self.log("Tác vụ hoàn thành trên thẻ Tab. Giữ nguyên Tab mở để theo dõi...")
            return

        if self.browser:
            self.log("Closing browser...")
            try:
                self.browser.stop()  # nodriver uses stop() to close browser
                self.log("Browser closed successfully.")
            except Exception as e:
                self.log(f"Error closing browser: {str(e)}", "WARN")
            finally:
                self.browser = None
                self.page = None

    async def wait_for_element(self, selector: str, timeout: float = 30.0, log_err: bool = True):
        """Helper to wait for selector with custom timeout, using nodriver's select method."""
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                element = await self.page.select(selector)
                if element:
                    return element
            except Exception:
                pass
            await asyncio.sleep(0.5)
        
        if log_err:
            self.log(f"Timeout waiting for element: {selector}", "WARN")
        return None

    async def wait_for_text(self, text: str, timeout: float = 30.0, log_err: bool = True):
        """Helper to wait for element containing text, using nodriver's find method."""
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                element = await self.page.find(text)
                if element:
                    return element
            except Exception:
                pass
            await asyncio.sleep(0.5)
        
        if log_err:
            self.log(f"Timeout waiting for text: '{text}'", "WARN")
        return None

    async def delay(self, seconds: float):
        """Standard delay helper."""
        await asyncio.sleep(seconds)

    async def select_pierce(self, selector: str):
        """Selects an element piercing all shadow roots natively, returning a nodriver Element."""
        import nodriver.cdp.runtime as runtime
        import nodriver.cdp.dom as dom
        from nodriver.core.element import Element
        
        safe_sel = json.dumps(selector)
        js_code = f"""
        (function() {{
            function findElement(selector, startNode = document) {{
                let el = startNode.querySelector(selector);
                if (el) return el;
                
                const all = startNode.querySelectorAll('*');
                for (const node of all) {{
                    if (node.shadowRoot) {{
                        el = findElement(selector, node.shadowRoot);
                        if (el) return el;
                    }}
                }}
                return null;
            }}
            return findElement({safe_sel});
        }})()
        """
        try:
            # 1. Sync DOM document tree (needed after page navigations/refreshes)
            await self.page.send(dom.get_document())

            # 2. Evaluate to get remote object
            res_tuple = await self.page.send(runtime.evaluate(
                expression=js_code,
                return_by_value=False
            ))
            if not res_tuple or not res_tuple[0] or not res_tuple[0].object_id:
                return None
                
            remote_obj = res_tuple[0]
            
            # 3. Resolve Node ID
            node_id = await self.page.send(dom.request_node(object_id=remote_obj.object_id))
            if not node_id:
                return None
                
            # 4. Describe node recursively to wrap it fully
            node_desc = await self.page.send(dom.describe_node(node_id=node_id, depth=-1))
            if not node_desc:
                return None
                
            # 5. Return wrapped Element
            return Element(node=node_desc, tab=self.page)
        except Exception as e:
            self.log(f"Error piercing shadow DOM for '{selector}': {e}", "DEBUG")
            return None

    async def wait_for_element_pierce(self, selector: str, timeout: float = 30.0, log_err: bool = True):
        """Waits for an element piercing shadow roots with custom timeout."""
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            el = await self.select_pierce(selector)
            if el:
                return el
            await asyncio.sleep(0.5)
        
        if log_err:
            self.log(f"Timeout waiting for element piercing shadow: '{selector}'", "WARN")
        return None

    async def js_click(self, selector: str, timeout: float = 30.0) -> bool:
        """Finds an element piercing shadow roots and clicks it in JS, waiting if necessary."""
        safe_sel = json.dumps(selector)
        js_code = f"""
        (function() {{
            function findElements(selector, startNode = document, results = []) {{
                const el = startNode.querySelector(selector);
                if (el) results.push(el);
                
                const all = startNode.querySelectorAll('*');
                for (const node of all) {{
                    if (node.shadowRoot) {{
                        findElements(selector, node.shadowRoot, results);
                    }}
                }}
                return results;
            }}
            function getStartNode() {{
                const dialogs = document.querySelectorAll('ytcp-uploads-dialog');
                for (let i = dialogs.length - 1; i >= 0; i--) {{
                    const d = dialogs[i];
                    if (d.offsetWidth || d.offsetHeight || d.getClientRects().length) {{
                        return d.shadowRoot || d;
                    }}
                }}
                return document;
            }}
            function isVisible(el) {{
                return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
            }}
            const startNode = getStartNode();
            const matches = findElements({safe_sel}, startNode);
            let el = null;
            if (matches.length > 0) {{
                for (let i = matches.length - 1; i >= 0; i--) {{
                    if (isVisible(matches[i])) {{
                        el = matches[i];
                        break;
                    }}
                }}
                if (!el) el = matches[matches.length - 1];
            }}
            if (el && isVisible(el) && !el.disabled && !el.getAttribute('disabled')) {{
                el.click();
                return true;
            }}
            return false;
        }})()
        """
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                res = await self.page.evaluate(js_code)
                if res:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
        self.log(f"Timeout trying to JS click: '{selector}'", "WARN")
        return False

    async def cdp_click(self, selector: str, timeout: float = 30.0) -> bool:
        """Finds element piercing shadow roots and performs a REAL CDP mouse click (isTrusted: true).
        
        Uses window globals to pass coordinates (avoids page.evaluate return type issues).
        Includes detailed logging for diagnostics.
        """
        from nodriver.cdp import input_ as cdp_input
        
        safe_sel = json.dumps(selector)
        # Step 1: JS to find element, scroll into view, store coords in window globals
        js_find = f"""
        (function() {{
            function findElements(selector, startNode = document, results = []) {{
                const el = startNode.querySelector(selector);
                if (el) results.push(el);
                const all = startNode.querySelectorAll('*');
                for (const node of all) {{
                    if (node.shadowRoot) {{
                        findElements(selector, node.shadowRoot, results);
                    }}
                }}
                return results;
            }}
            function getStartNode() {{
                const dialogs = document.querySelectorAll('ytcp-uploads-dialog');
                for (let i = dialogs.length - 1; i >= 0; i--) {{
                    const d = dialogs[i];
                    if (d.offsetWidth || d.offsetHeight || d.getClientRects().length) {{
                        return d.shadowRoot || d;
                    }}
                }}
                return document;
            }}
            function isVisible(el) {{
                return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
            }}
            const startNode = getStartNode();
            const matches = findElements({safe_sel}, startNode);
            let el = null;
            if (matches.length > 0) {{
                for (let i = matches.length - 1; i >= 0; i--) {{
                    if (isVisible(matches[i])) {{
                        el = matches[i];
                        break;
                    }}
                }}
                if (!el) el = matches[matches.length - 1];
            }}
            if (el && isVisible(el) && !el.disabled && !el.getAttribute('disabled')) {{
                el.scrollIntoView({{block: 'center'}});
                const rect = el.getBoundingClientRect();
                window.__cdp_x = rect.left + rect.width / 2;
                window.__cdp_y = rect.top + rect.height / 2;
                window.__cdp_tag = el.tagName;
                return true;
            }}
            window.__cdp_x = 0;
            window.__cdp_y = 0;
            window.__cdp_tag = '';
            return false;
        }})()
        """
        
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                # Step 1: Find element
                found = await self.page.evaluate(js_find)
                self.log(f"cdp_click '{selector}': found={found} (type={type(found).__name__})")
                
                if not found:
                    await asyncio.sleep(0.5)
                    continue
                
                # Step 2: Read coordinates (as separate numbers - guaranteed to work)
                x = await self.page.evaluate("window.__cdp_x")
                y = await self.page.evaluate("window.__cdp_y")
                tag = await self.page.evaluate("window.__cdp_tag")
                self.log(f"cdp_click '{selector}': coordinates x={x}, y={y}, tag={tag}")
                
                if not x or not y:
                    self.log(f"cdp_click '{selector}': invalid coordinates, retrying...", "WARN")
                    await asyncio.sleep(0.5)
                    continue
                
                x_val = float(x) if not isinstance(x, float) else x
                y_val = float(y) if not isinstance(y, float) else y
                
                # Step 3: Send CDP mouse events (isTrusted: true)
                self.log(f"cdp_click '{selector}': dispatching mousePressed at ({x_val}, {y_val})")
                await self.page.send(cdp_input.dispatch_mouse_event(
                    type_="mousePressed",
                    x=x_val, y=y_val,
                    button=cdp_input.MouseButton.LEFT,
                    click_count=1,
                    pointer_type="mouse"
                ))
                await asyncio.sleep(0.05)
                await self.page.send(cdp_input.dispatch_mouse_event(
                    type_="mouseReleased",
                    x=x_val, y=y_val,
                    button=cdp_input.MouseButton.LEFT,
                    click_count=1,
                    pointer_type="mouse"
                ))
                self.log(f"cdp_click '{selector}': CDP mouse events dispatched successfully!")
                return True
                
            except Exception as e:
                self.log(f"cdp_click '{selector}' error: {type(e).__name__}: {e}", "WARN")
            await asyncio.sleep(0.5)
        self.log(f"Timeout trying to CDP click: '{selector}'", "WARN")
        return False


    async def js_type(self, selector: str, text: str, timeout: float = 30.0) -> bool:
        """Finds an element piercing shadow roots and inputs text in JS, waiting if necessary."""
        safe_sel = json.dumps(selector)
        safe_txt = json.dumps(text)
        js_code = f"""
        (function() {{
            function findElements(selector, startNode = document, results = []) {{
                const el = startNode.querySelector(selector);
                if (el) results.push(el);
                
                const all = startNode.querySelectorAll('*');
                for (const node of all) {{
                    if (node.shadowRoot) {{
                        findElements(selector, node.shadowRoot, results);
                    }}
                }}
                return results;
            }}
            function getStartNode() {{
                const dialogs = document.querySelectorAll('ytcp-uploads-dialog');
                for (let i = dialogs.length - 1; i >= 0; i--) {{
                    const d = dialogs[i];
                    if (d.offsetWidth || d.offsetHeight || d.getClientRects().length) {{
                        return d.shadowRoot || d;
                    }}
                }}
                return document;
            }}
            function isVisible(el) {{
                return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
            }}
            const startNode = getStartNode();
            const matches = findElements({safe_sel}, startNode);
            let el = null;
            if (matches.length > 0) {{
                for (let i = matches.length - 1; i >= 0; i--) {{
                    if (isVisible(matches[i])) {{
                        el = matches[i];
                        break;
                    }}
                }}
                if (!el) el = matches[matches.length - 1];
            }}
            if (el && isVisible(el)) {{
                el.focus();
                el.innerText = {safe_txt};
                el.value = {safe_txt};
                el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return true;
            }}
            return false;
        }})()
        """
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                res = await self.page.evaluate(js_code)
                if res:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
        self.log(f"Timeout trying to JS type: '{selector}'", "WARN")
        return False

    async def cdp_click_text(self, text: str, timeout: float = 30.0) -> bool:
        """Finds an element containing specific text piercing shadow roots and clicks it via CDP."""
        from nodriver.cdp import input_ as cdp_input
        safe_txt = json.dumps(text)
        js_find = f"""
        (function() {{
            function collectMatches(txt, node = document, results = []) {{
                const all = node.querySelectorAll('*');
                for (const child of all) {{
                    const tagName = child.tagName.toLowerCase();
                    if ((tagName === 'button' || 
                         tagName === 'div' || 
                         tagName === 'span' || 
                         tagName === 'a' || 
                         tagName === 'ytcp-button' ||
                         tagName === 'tp-yt-paper-button' ||
                         tagName === 'tp-yt-paper-radio-button') && 
                        child.innerText) {{
                        const cleanText = child.innerText.trim().toLowerCase();
                        if (cleanText.includes(txt.toLowerCase()) && cleanText.length < txt.length + 15) {{
                            results.push(child);
                        }}
                    }}
                    if (child.shadowRoot) {{
                        collectMatches(txt, child.shadowRoot, results);
                    }}
                }}
                return results;
            }}
            function isVisible(el) {{
                return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
            }}
            const matches = collectMatches({safe_txt}, document);
            let el = null;
            if (matches.length > 0) {{
                for (let i = matches.length - 1; i >= 0; i--) {{
                    if (isVisible(matches[i])) {{
                        el = matches[i];
                        break;
                    }}
                }}
                if (!el) el = matches[matches.length - 1];
            }}
            if (el && isVisible(el)) {{
                el.scrollIntoView({{block: 'center'}});
                const rect = el.getBoundingClientRect();
                window.__cdp_x = rect.left + rect.width / 2;
                window.__cdp_y = rect.top + rect.height / 2;
                window.__cdp_tag = el.tagName;
                return true;
            }}
            window.__cdp_x = 0;
            window.__cdp_y = 0;
            window.__cdp_tag = '';
            return false;
        }})()
        """
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                found = await self.page.evaluate(js_find)
                if found:
                    x = await self.page.evaluate("window.__cdp_x")
                    y = await self.page.evaluate("window.__cdp_y")
                    if x and y:
                        x_val = float(x)
                        y_val = float(y)
                        await self.page.send(cdp_input.dispatch_mouse_event(
                            type_="mousePressed", x=x_val, y=y_val,
                            button=cdp_input.MouseButton.LEFT, click_count=1, pointer_type="mouse"
                        ))
                        await asyncio.sleep(0.05)
                        await self.page.send(cdp_input.dispatch_mouse_event(
                            type_="mouseReleased", x=x_val, y=y_val,
                            button=cdp_input.MouseButton.LEFT, click_count=1, pointer_type="mouse"
                        ))
                        return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
        return False

    async def js_click_text(self, text: str, timeout: float = 30.0) -> bool:
        """Finds an element containing specific text (piercing shadow roots) and clicks it."""
        safe_txt = json.dumps(text)
        js_code = f"""
        (function() {{
            function collectMatches(txt, node = document, results = []) {{
                const all = node.querySelectorAll('*');
                for (const child of all) {{
                    const tagName = child.tagName.toLowerCase();
                    if ((tagName === 'tp-yt-paper-radio-button' || 
                         tagName === 'ytcp-button' ||
                         tagName === 'tp-yt-paper-button' ||
                         tagName === 'button' ||
                         tagName === 'div' ||
                         tagName === 'a' ||
                         tagName === 'span') && 
                        child.innerText) {{
                        const cleanText = child.innerText.trim().toLowerCase();
                        if (cleanText.includes(txt.toLowerCase()) && cleanText.length < txt.length + 15) {{
                            results.push(child);
                        }}
                    }}
                    if (child.shadowRoot) {{
                        collectMatches(txt, child.shadowRoot, results);
                    }}
                }}
                return results;
            }}
            function getStartNode() {{
                const dialogs = document.querySelectorAll('ytcp-uploads-dialog');
                for (let i = dialogs.length - 1; i >= 0; i--) {{
                    const d = dialogs[i];
                    if (d.offsetWidth || d.offsetHeight || d.getClientRects().length) {{
                        return d.shadowRoot || d;
                    }}
                }}
                return document;
            }}
            function isVisible(el) {{
                return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
            }}
            const startNode = getStartNode();
            const matches = collectMatches({safe_txt}, startNode);
            let el = null;
            if (matches.length > 0) {{
                for (let i = matches.length - 1; i >= 0; i--) {{
                    if (isVisible(matches[i])) {{
                        el = matches[i];
                        break;
                    }}
                }}
                if (!el) el = matches[matches.length - 1];
            }}
            if (el && isVisible(el) && !el.disabled && !el.getAttribute('disabled')) {{
                el.click();
                return true;
            }}
            return false;
        }})()
        """
        start_time = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start_time < timeout:
            try:
                res = await self.page.evaluate(js_code)
                if res:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.5)
        self.log(f"Timeout trying to JS click by text: '{text}'", "WARN")
        return False
