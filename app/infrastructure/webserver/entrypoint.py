import os
import json
import uuid
import asyncio
import logging
import shutil
from datetime import datetime
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

# Import Clean Architecture layers
from app.adapters.repositories.json_repository import JsonRepository
from app.domain.account import Account
from app.domain.video import Video
from app.use_cases.sync_gmail import SyncGmailUseCase
from app.use_cases.open_browser import OpenBrowserUseCase
from app.use_cases.publish_video import PublishVideoUseCase

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("video_uploader_webserver")

app = FastAPI(title="Multi-Platform Auto Video Uploader - Clean Architecture")

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi import Request

# No-Cache Middleware for Static Files
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Directories setup
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
STATIC_DIR = os.path.join(BASE_DIR, "static")
DATABASE_FILE = os.path.join(BASE_DIR, "database.json")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Global log queue for Server-Sent Events (SSE)
log_queue = asyncio.Queue()
active_browsers = {}

# Instantiate Repository
repository = JsonRepository(DATABASE_FILE)

async def send_sse_log(message: str, level: str = "INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {message}"
    await log_queue.put(log_line)

# --- FastAPI ENDPOINTS (Interface Controllers) ---

@app.get("/")
def get_dashboard():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(
            index_path,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return JSONResponse({"error": "Giao diện người dùng đang được xây dựng."}, status_code=503)

@app.get("/api/logs")
async def get_logs():
    async def sse_generator():
        while True:
            log_line = await log_queue.get()
            yield f"data: {log_line}\n\n"
    return StreamingResponse(sse_generator(), media_type="text/event-stream")

@app.get("/api/accounts")
def get_accounts():
    accounts = repository.get_accounts()
    return [acc.to_dict() for acc in accounts]

@app.post("/api/accounts")
def create_account(account_data: dict):
    # Generate unique ID if not exists
    acc_id = account_data.get("id") or f"acc_{uuid.uuid4().hex[:8]}"
    
    # Generate profile name based on name/platform
    name = account_data.get("name", "Unnamed")
    platform = account_data.get("platform", "youtube")
    clean_name = "".join(c for c in name if c.isalnum() or c in ("_", "-")).lower()
    
    new_account = Account(
        id=acc_id,
        name=name,
        platform=platform,
        profile_name=f"profile_{platform}_{clean_name}",
        email=account_data.get("email"),
        created_at=datetime.now().isoformat()
    )
    
    repository.add_account(new_account)
    return new_account.to_dict()

@app.delete("/api/accounts/{account_id}")
def delete_account(account_id: str):
    repository.delete_account(account_id)
    return {"success": True}

@app.post("/api/accounts/sync-gmail")
def sync_gmail_accounts():
    use_case = SyncGmailUseCase(repository)
    try:
        added_count = use_case.execute()
        return {"success": True, "added_count": added_count}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/accounts/{account_id}/open-browser")
async def open_account_browser(account_id: str, background_tasks: BackgroundTasks):
    if account_id in active_browsers:
        return {"success": False, "message": "Trình duyệt cho tài khoản này đã được mở."}
        
    use_case = OpenBrowserUseCase(repository)
    
    async def sse_logger(msg, lvl="INFO"):
        await send_sse_log(msg, lvl)

    background_tasks.add_task(
        use_case.execute, 
        account_id, 
        active_browsers, 
        sse_logger
    )
    return {"success": True, "message": "Đang mở trình duyệt..."}

@app.post("/api/accounts/{account_id}/close-browser")
async def close_account_browser(account_id: str):
    if account_id in active_browsers:
        browser = active_browsers.pop(account_id)
        try:
            await browser.stop()
            await send_sse_log(f"Đã chủ động đóng trình duyệt cho tài khoản {account_id}.", "INFO")
            return {"success": True}
        except Exception as e:
            return {"success": False, "message": f"Lỗi khi đóng: {str(e)}"}
    return {"success": False, "message": "Trình duyệt không chạy."}

@app.get("/api/videos")
def get_videos():
    videos = repository.get_videos()
    return [vid.to_dict() for vid in videos]

@app.post("/api/videos")
async def upload_video(
    video: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(...),
    platforms: str = Form(...),
    publish_type_youtube: str = Form("shorts"),
    publish_type_facebook: str = Form("reels")
):
    try:
        target_accounts = json.loads(platforms)
    except Exception:
        raise HTTPException(status_code=400, detail="Danh sách nền tảng không hợp lệ.")
        
    video_id = f"vid_{uuid.uuid4().hex[:8]}"
    file_ext = os.path.splitext(video.filename)[1] or ".mp4"
    filepath = os.path.join(UPLOADS_DIR, f"{video_id}{file_ext}")
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(video.file, buffer)
        
    new_video = Video(
        id=video_id,
        filename=video.filename,
        filepath=filepath,
        title=title,
        description=description,
        target_accounts=target_accounts,
        status="pending",
        publish_settings={
            "youtube": publish_type_youtube,
            "facebook": publish_type_facebook
        }
    )
    
    repository.add_video(new_video)
    return new_video.to_dict()

@app.post("/api/videos/{video_id}/publish")
async def publish_video(video_id: str, background_tasks: BackgroundTasks):
    videos = repository.get_videos()
    video = next((v for v in videos if v.id == video_id), None)
    if not video:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin video.")
        
    if video.status == "uploading":
        return {"success": False, "message": "Video này đang trong quá trình tải lên."}
        
    use_case = PublishVideoUseCase(repository)
    
    async def sse_logger(msg, lvl="INFO"):
        await send_sse_log(msg, lvl)

    background_tasks.add_task(
        use_case.execute, 
        video_id, 
        video.target_accounts, 
        sse_logger
    )
    return {"success": True, "message": "Đã bắt đầu tác vụ đăng video."}

@app.post("/api/videos/{video_id}/delete")
async def delete_video(video_id: str, payload: dict, background_tasks: BackgroundTasks):
    videos = repository.get_videos()
    video = next((v for v in videos if v.id == video_id), None)
    if not video:
        raise HTTPException(status_code=404, detail="Không tìm thấy thông tin video.")
        
    account_ids = payload.get("account_ids", [])
    delete_record = payload.get("delete_record", False)
    
    from app.use_cases.delete_video import DeletePublishedVideoUseCase
    use_case = DeletePublishedVideoUseCase(repository)
    
    async def sse_logger(msg, lvl="INFO"):
        await send_sse_log(msg, lvl)
        
    background_tasks.add_task(
        use_case.execute,
        video_id,
        account_ids,
        delete_record,
        sse_logger
    )
    return {"success": True, "message": "Đã bắt đầu tiến trình xóa video."}

@app.get("/api/settings")
def get_settings():
    return repository.get_settings()

@app.post("/api/settings")
def save_settings(settings: dict):
    repository.save_settings(settings)
    return {"success": True}
