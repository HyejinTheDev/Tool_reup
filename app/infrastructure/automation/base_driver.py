import os
import asyncio
import logging
import nodriver as uc
from typing import Callable, Optional

# Setup standard logging
logger = logging.getLogger("base_driver")

class BaseDriver:
    def __init__(self, account_id: str, profile_name: str, chrome_path: Optional[str] = None, headless: bool = False, log_callback: Optional[Callable[[str], None]] = None):
        self.account_id = account_id
        self.profile_name = profile_name
        self.chrome_path = chrome_path
        self.headless = headless
        self.log_callback = log_callback
        self.browser = None
        self.page = None

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
        chrome_exe = self.find_chrome_executable()
        
        # Profile directory inside project workspace (root directory)
        project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        profiles_dir = os.path.join(project_dir, "chrome_profiles")
        os.makedirs(profiles_dir, exist_ok=True)
        
        if os.path.isabs(self.profile_name) or "\\" in self.profile_name or "/" in self.profile_name:
            profile_path = os.path.abspath(self.profile_name)
        else:
            profile_path = os.path.join(profiles_dir, self.profile_name)
            
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
                    "--no-first-run",
                    "--no-default-browser-check"
                ]
            )
            # nodriver starts with a default main tab
            self.page = self.browser.main_tab
            self.log("Browser started successfully.")
        except Exception as e:
            import traceback
            tb_str = traceback.format_exc()
            self.log(f"Failed to start browser. Exception: {type(e)} - {str(e)}\nTraceback:\n{tb_str}", "ERROR")
            raise e

    async def close_browser(self):
        """Close browser safely."""
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
            return findElement("{selector}");
        }})()
        """
        try:
            # 1. Evaluate to get remote object
            res_tuple = await self.page.send(runtime.evaluate(
                expression=js_code,
                return_by_value=False
            ))
            if not res_tuple or not res_tuple[0] or not res_tuple[0].object_id:
                return None
                
            remote_obj = res_tuple[0]
            
            # 2. Enable DOM and fetch document
            await self.page.send(dom.enable())
            await self.page.send(dom.get_document())
            
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
