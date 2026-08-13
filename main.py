if __name__ == "__main__":
    import uvicorn
    # Khởi chạy server FastAPI từ tầng infrastructure của Clean Architecture
    uvicorn.run("app.infrastructure.webserver.entrypoint:app", host="127.0.0.1", port=8000, reload=True)
