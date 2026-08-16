import asyncio
import os
from app.adapters.repositories.base_repository import BaseRepository

class OpenBrowserUseCase:
    def __init__(self, repository: BaseRepository):
        self.repository = repository

    async def execute(self, account_id: str, active_browsers: dict, send_sse_log_func) -> None:
        accounts = self.repository.get_accounts()
        account = next((acc for acc in accounts if acc.id == account_id), None)
        if not account:
            raise ValueError("Không tìm thấy tài khoản.")
            
        settings = self.repository.get_settings()
        chrome_path = settings.get("chrome_path", "")
        
        await send_sse_log_func(f"Đang mở trình duyệt ở chế độ hiển thị cho tài khoản {account_id}...", "INFO")
        
        target_url = "https://studio.youtube.com"
        if account.platform == "tiktok":
            target_url = "https://www.tiktok.com/tiktokstudio/upload?lang=vi-VN"
        elif account.platform == "facebook":
            target_url = "https://business.facebook.com/latest/reels_composer"
            
        import nodriver as uc
        
        # Determine profile directory - use the account's Chrome profile
        project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        profiles_dir = os.path.join(project_dir, "chrome_profiles")
        
        if os.path.isabs(account.profile_name) or "\\" in account.profile_name or "/" in account.profile_name:
            profile_path = os.path.abspath(account.profile_name)
        else:
            profile_path = os.path.join(profiles_dir, account.profile_name)
            
        try:
            browser = await uc.start(
                browser_executable_path=chrome_path if os.path.exists(chrome_path) else None,
                user_data_dir=profile_path,
                headless=False,
                browser_args=["--start-maximized", "--no-first-run", "--no-default-browser-check"]
            )
            
            active_browsers[account_id] = browser
            await send_sse_log_func("Đã mở trình duyệt thành công. Vui lòng đăng nhập và đóng trình duyệt khi hoàn thành.", "INFO")
            
            page = browser.main_tab
            await page.get(target_url)
            
            # Keep process alive until browser stops or is closed
            while account_id in active_browsers:
                await asyncio.sleep(2)
                
        except Exception as e:
            await send_sse_log_func(f"Lỗi khi mở trình duyệt đăng nhập: {str(e)}", "ERROR")
            raise e
        finally:
            if account_id in active_browsers:
                active_browsers.pop(account_id, None)
            await send_sse_log_func(f"Đã đóng trình duyệt cho tài khoản {account_id}.", "INFO")
