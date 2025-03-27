from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
import sys
import traceback

# 設置環境變量，確保在程序開始時就有正確的設定
os.environ["PYTHONIOENCODING"] = "utf-8"
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "mongodb://Volticar:REMOVED_PASSWORD@59.126.6.46:27017/?authSource=admin&ssl=false"

# 先初始化app實例
app = FastAPI(
    title="電動汽車充電站API",
    description="用於管理電動汽車充電站和用戶充電記錄的API",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允許所有來源，生產環境應限制
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局異常處理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_detail = f"{type(exc).__name__}: {str(exc)}"
    print(f"全局異常捕獲: {error_detail}")
    print(f"異常產生於: {request.url.path}")
    traceback.print_exc()
    
    return JSONResponse(
        status_code=500,
        content={"message": "伺服器內部錯誤", "detail": error_detail},
    )

# 根路由
@app.get("/")
async def root():
    return {
        "message": "歡迎使用電動汽車充電站API",
        "version": "1.0.0",
        "docs_url": "/docs"
    }

# 健康檢查端點
@app.get("/health")
async def health_check():
    # 檢查數據庫連接
    from app.database.mongodb import client, volticar_db
    
    db_status = "正常" if client is not None and volticar_db is not None else "無法連接"
    
    return {
        "status": "healthy", 
        "message": "API服務正常運行中",
        "database": db_status,
        "environment": os.getenv("API_ENV", "development")
    }

# 在這之後再導入API路由，這樣可以使用前面初始化的app
try:
    from app.api import api_router
    # 包含API路由
    app.include_router(api_router)
    print("API路由已成功載入")
except Exception as e:
    print(f"載入API路由時出錯: {str(e)}")
    traceback.print_exc()

# 直接運行應用程序
if __name__ == "__main__":
    try:
        host = os.getenv("API_HOST", "0.0.0.0")
        port = int(os.getenv("API_PORT", 22000))
        
        print(f"啟動API服務於 https://{host}:{port}")
        print(f"API文檔位於 https://{host}:{port}/docs")

        ssl_keyfile = os.environ.get("SSL_KEYFILE", "C:\\Certbot\\live\\volticar.dynns.com\\privkey.pem")
        ssl_certfile = os.environ.get("SSL_CERTFILE", "C:\\Certbot\\live\\volticar.dynns.com\\fullchain.pem")

        uvicorn.run(app, host=host, port=port, ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile)
    except Exception as e:
        print(f"啟動服務時發生錯誤: {str(e)}")
        traceback.print_exc()
        sys.exit(1)
