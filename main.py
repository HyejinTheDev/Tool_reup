import sys
import asyncio

if __name__ == "__main__":
    import uvicorn
    
    # Thiết lập ProactorEventLoopPolicy trên Windows để hỗ trợ subprocesses (nodriver)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
    # Tắt reload=True vì reload sẽ ép uvcorn dùng SelectorEventLoop (không hỗ trợ chạy trình duyệt)
    uvicorn.run("app.infrastructure.webserver.entrypoint:app", host="127.0.0.1", port=8000, reload=False)
