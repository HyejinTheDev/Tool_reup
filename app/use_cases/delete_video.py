import os
import asyncio
from typing import List, Callable
from app.adapters.repositories.base_repository import BaseRepository
from app.infrastructure.automation.youtube_driver import YoutubeDriver
from app.infrastructure.automation.tiktok_driver import TiktokDriver
from app.infrastructure.automation.facebook_driver import FacebookDriver

class DeletePublishedVideoUseCase:
    def __init__(self, repository: BaseRepository):
        self.repository = repository

    async def execute(self, video_id: str, account_ids: List[str], delete_record: bool, send_sse_log_func: Callable[[str, str], None]) -> None:
        videos = self.repository.get_videos()
        video = next((v for v in videos if v.id == video_id), None)
        if not video:
            await send_sse_log_func(f"Không tìm thấy video ID: {video_id}", "ERROR")
            return
            
        settings = self.repository.get_settings()
        chrome_path = settings.get("chrome_path", "")
        headless = settings.get("headless", False)

        await send_sse_log_func(f"Bắt đầu tác vụ xóa bài đăng '{video.title}' trên các kênh chỉ định...", "INFO")

        for account_id in account_ids:
            accounts = self.repository.get_accounts()
            account = next((acc for acc in accounts if acc.id == account_id), None)
            if not account:
                await send_sse_log_func(f"Không tìm thấy tài khoản ID: {account_id}", "ERROR")
                continue
                
            platform = account.platform
            profile_name = account.profile_name
            
            await send_sse_log_func(f"Đang chuẩn bị xóa bài trên {platform.upper()} (Tài khoản: {account.name})...", "INFO")
            
            # Setup logging callback
            def log_cb(msg):
                asyncio.run_coroutine_threadsafe(
                    send_sse_log_func(msg, "INFO"), 
                    asyncio.get_event_loop()
                )

            # Resolve driver
            driver = None
            if platform == "youtube":
                driver = YoutubeDriver(account_id, profile_name, chrome_path, headless, log_cb)
            elif platform == "tiktok":
                driver = TiktokDriver(account_id, profile_name, chrome_path, headless, log_cb)
            elif platform == "facebook":
                driver = FacebookDriver(account_id, profile_name, chrome_path, headless, log_cb)
                
            if not driver:
                await send_sse_log_func(f"Nền tảng {platform} chưa hỗ trợ robot xóa.", "ERROR")
                continue

            success = False
            try:
                await driver.start_browser()
                # YouTube search queries title, others search caption/description
                search_query = video.title if platform == "youtube" else video.description
                success = await driver.delete_post(search_query)
                if success:
                    await send_sse_log_func(f"Đã xóa thành công bài viết trên {platform.upper()}!", "SUCCESS")
                else:
                    await send_sse_log_func(f"Không tìm thấy bài viết trên {platform.upper()} để xóa.", "WARN")
            except Exception as e:
                await send_sse_log_func(f"Lỗi khi xóa bài trên {platform.upper()}: {str(e)}", "ERROR")
            finally:
                await driver.close_browser()

            if success:
                # Remove this account from the video's successful results
                # Reload list to avoid race conditions
                videos = self.repository.get_videos()
                for v in videos:
                    if v.id == video_id:
                        if account_id in v.results:
                            v.results.pop(account_id)
                        break
                self.repository.save_videos(videos)

        # After finishing social deletions, check if we should delete the local database record
        if delete_record:
            # Reload list
            videos = self.repository.get_videos()
            video = next((v for v in videos if v.id == video_id), None)
            if video:
                # Delete video file from uploads directory
                if os.path.exists(video.filepath):
                    try:
                        os.remove(video.filepath)
                        await send_sse_log_func("Đã xóa tệp video vật lý trong thư mục uploads.", "INFO")
                    except Exception as e:
                        await send_sse_log_func(f"Không thể xóa tệp tin video vật lý: {str(e)}", "WARN")

                # Remove from database list
                videos = [v for v in videos if v.id != video_id]
                self.repository.save_videos(videos)
                await send_sse_log_func(f"Đã xóa bản ghi video ID: {video_id} khỏi cơ sở dữ liệu.", "SUCCESS")
        else:
            # Update status if some results were deleted
            videos = self.repository.get_videos()
            for v in videos:
                if v.id == video_id:
                    results = v.results
                    if len(results) == 0:
                        v.status = "pending"
                    elif all(r.get("success", False) for r in results.values()):
                        v.status = "completed"
                    else:
                        v.status = "partial"
                    break
            self.repository.save_videos(videos)
            
        await send_sse_log_func("Hoàn thành tác vụ xóa video.", "INFO")
