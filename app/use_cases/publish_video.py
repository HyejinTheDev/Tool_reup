import asyncio
from datetime import datetime
from typing import List, Callable
from app.adapters.repositories.base_repository import BaseRepository
from app.domain.video import Video
from app.infrastructure.automation.youtube_driver import YoutubeDriver
from app.infrastructure.automation.tiktok_driver import TiktokDriver
from app.infrastructure.automation.facebook_driver import FacebookDriver

class PublishVideoUseCase:
    def __init__(self, repository: BaseRepository):
        self.repository = repository

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
        
        await send_sse_log_func(f"Bắt đầu tác vụ đăng video '{video.title}' lên các tài khoản...", "INFO")
        
        for account_id in account_ids:
            accounts = self.repository.get_accounts()
            account = next((acc for acc in accounts if acc.id == account_id), None)
            if not account:
                await send_sse_log_func(f"Không tìm thấy tài khoản ID: {account_id}", "ERROR")
                continue
                
            platform = account.platform
            profile_name = account.profile_name
            
            await send_sse_log_func(f"Đang chuẩn bị đăng lên {platform.upper()} (Tài khoản: {account.name})...", "INFO")
            
            # Setup logging callback to forward to SSE logs
            def log_cb(msg):
                asyncio.run_coroutine_threadsafe(
                    send_sse_log_func(msg, "INFO"), 
                    asyncio.get_event_loop()
                )

            # Resolve driver based on platform
            driver = None
            if platform == "youtube":
                driver = YoutubeDriver(account_id, profile_name, chrome_path, headless, log_cb)
            elif platform == "tiktok":
                driver = TiktokDriver(account_id, profile_name, chrome_path, headless, log_cb)
            elif platform == "facebook":
                driver = FacebookDriver(account_id, profile_name, chrome_path, headless, log_cb)
                
            if not driver:
                await send_sse_log_func(f"Nền tảng {platform} chưa được hỗ trợ uploader.", "ERROR")
                continue
                
            success = False
            result_url = ""
            error_msg = ""
            
            try:
                await driver.start_browser()
                result_url = await driver.upload(video.filepath, video.title, video.description)
                success = True
                await send_sse_log_func(f"Đăng thành công lên {platform.upper()}! URL: {result_url}", "SUCCESS")
            except Exception as e:
                error_msg = str(e)
                await send_sse_log_func(f"Đăng thất bại lên {platform.upper()}: {error_msg}", "ERROR")
            finally:
                await driver.close_browser()
                
            # Update results
            # Reload list to avoid race conditions
            videos = self.repository.get_videos()
            for v in videos:
                if v.id == video_id:
                    v.results[account_id] = {
                        "success": success,
                        "url": result_url,
                        "error": error_msg,
                        "timestamp": datetime.now().isoformat()
                    }
                    break
            self.repository.save_videos(videos)

        # Finalize video status
        videos = self.repository.get_videos()
        for v in videos:
            if v.id == video_id:
                results = v.results
                if len(results) == len(account_ids) and all(r.get("success", False) for r in results.values()):
                    v.status = "completed"
                elif any(r.get("success", False) for r in results.values()):
                    v.status = "partial"
                else:
                    v.status = "failed"
                break
        self.repository.save_videos(videos)
        await send_sse_log_func("Hoàn thành tác vụ đăng video đa nền tảng.", "INFO")
