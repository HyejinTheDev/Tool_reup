import asyncio
import os
from datetime import datetime
from typing import List, Callable, Tuple, Dict, Any
from app.adapters.repositories.base_repository import BaseRepository
from app.domain.video import Video
from app.infrastructure.automation.base_driver import BaseDriver
from app.infrastructure.automation.youtube_driver import YoutubeDriver
from app.infrastructure.automation.tiktok_driver import TiktokDriver
from app.infrastructure.automation.facebook_driver import FacebookDriver

class PublishVideoUseCase:
    def __init__(self, repository: BaseRepository):
        self.repository = repository

    async def _publish_single_account(
        self, 
        video: Video, 
        account_id: str, 
        chrome_path: str, 
        headless: bool, 
        send_sse_log_func: Callable[[str, str], None],
        shared_browser: Any,
        page: Any
    ) -> Tuple[str, Dict[str, Any]]:
        accounts = self.repository.get_accounts()
        account = next((acc for acc in accounts if acc.id == account_id), None)
        if not account:
            await send_sse_log_func(f"Không tìm thấy tài khoản ID: {account_id}", "ERROR")
            return account_id, {
                "success": False, 
                "url": "", 
                "error": "Account not found", 
                "timestamp": datetime.now().isoformat()
            }
            
        platform = account.platform
        profile_name = account.profile_name
        
        await send_sse_log_func(f"Đang tự động hóa trên thẻ Tab {platform.upper()} (Tài khoản: {account.name})...", "INFO")
        
        def log_cb(msg):
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(send_sse_log_func(msg, "INFO"))
            except RuntimeError:
                pass

        driver = None
        if platform == "youtube":
            driver = YoutubeDriver(account_id, profile_name, chrome_path, headless, log_cb, browser=shared_browser, page=page)
        elif platform == "tiktok":
            driver = TiktokDriver(account_id, profile_name, chrome_path, headless, log_cb, browser=shared_browser, page=page)
        elif platform == "facebook":
            driver = FacebookDriver(account_id, profile_name, chrome_path, headless, log_cb, browser=shared_browser, page=page)
            
        if not driver:
            await send_sse_log_func(f"Nền tảng {platform} chưa được hỗ trợ uploader.", "ERROR")
            return account_id, {
                "success": False, 
                "url": "", 
                "error": f"Platform {platform} not supported", 
                "timestamp": datetime.now().isoformat()
            }
            
        success = False
        result_url = ""
        error_msg = ""
        
        publish_type = video.publish_settings.get(platform, "default")
        try:
            await driver.start_browser()
            result_url = await driver.upload(video.filepath, video.title, video.description, publish_type=publish_type)
            success = True
            await send_sse_log_func(f"Đăng thành công lên {platform.upper()} ({account.name})! URL: {result_url}", "SUCCESS")
        except Exception as e:
            import traceback
            error_msg = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            await send_sse_log_func(f"Đăng thất bại lên {platform.upper()} ({account.name}): {error_msg}", "ERROR")
        finally:
            await driver.close_browser()
            
        return account_id, {
            "success": success,
            "url": result_url,
            "error": error_msg,
            "timestamp": datetime.now().isoformat()
        }

    async def execute(self, video_id: str, account_ids: List[str], send_sse_log_func: Callable[[str, str], None]) -> None:
        videos = self.repository.get_videos()
        video = next((v for v in videos if v.id == video_id), None)
        if not video:
            await send_sse_log_func(f"Không tìm thấy video ID: {video_id}", "ERROR")
            return
            
        settings = self.repository.get_settings()
        chrome_path = settings.get("chrome_path", "")
        headless = settings.get("headless", False)
        
        # Mark video as uploading
        video.status = "uploading"
        video.results = {}
        self.repository.save_videos(videos)
        
        await send_sse_log_func(f"Khởi chạy 1 CỬA SỔ CHROME DUY NHẤT để đăng video '{video.title}' cho {len(account_ids)} tài khoản...", "INFO")
        
        def master_log_cb(msg):
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(send_sse_log_func(msg, "INFO"))
            except RuntimeError:
                pass

        # 1. Launch ONE single Chrome browser instance
        master_driver = BaseDriver("shared_master", "profile_shared_all_platforms", chrome_path, headless, master_log_cb)
        await master_driver.start_browser()
        shared_browser = master_driver.browser
        
        try:
            # 2. Create a Tab for each account
            tasks = []
            for i, acc_id in enumerate(account_ids):
                if i == 0:
                    page = shared_browser.main_tab
                else:
                    page = await shared_browser.get("about:blank", new_tab=True)
                    
                tasks.append(
                    self._publish_single_account(
                        video, acc_id, chrome_path, headless, send_sse_log_func, shared_browser, page
                    )
                )
                
            # 3. Run all tabs in parallel concurrently
            account_results = await asyncio.gather(*tasks)
            
            # Consolidate results into database
            videos = self.repository.get_videos()
            for v in videos:
                if v.id == video_id:
                    for acc_id, res in account_results:
                        v.results[acc_id] = res
                    
                    results = v.results
                    if len(results) == len(account_ids) and all(r.get("success", False) for r in results.values()):
                        v.status = "completed"
                    elif any(r.get("success", False) for r in results.values()):
                        v.status = "partial"
                    else:
                        v.status = "failed"
                    break
            self.repository.save_videos(videos)
            await send_sse_log_func("Hoàn thành tác vụ đăng video song song đa nền tảng trên 1 trình duyệt.", "INFO")
        finally:
            await master_driver.close_browser()

