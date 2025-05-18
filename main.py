from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles # Added import
from fastapi.responses import FileResponse, JSONResponse # Added FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
import sys
import traceback
import logging # 導入 logging
import signal # 導入 signal 模組
import time # 導入 time 模組
import datetime # 導入 datetime 模組

# 設置環境變量，確保在程序開始時就有正確的設定
os.environ["PYTHONIOENCODING"] = "utf-8"
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "mongodb://Volticar:RJW1128@59.126.6.46:27017/?authSource=admin&ssl=false"

# --- 設定日誌 ---
log_directory = "logs"
# 確保日誌目錄存在
os.makedirs(log_directory, exist_ok=True)

# 生成帶時間戳的日誌檔名
current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(log_directory, f"api_{current_time}.log")

# 獲取根 logger
logger = logging.getLogger()
logger.setLevel(logging.INFO) # 設置最低日誌級別

# 移除可能存在的舊 handlers (如果有的話)
for handler in logger.handlers[:]:
    logger.removeHandler(handler)

# 創建格式器
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 創建控制台 handler
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

# 創建檔案 handler (FileHandler)，使用帶時間戳的檔名
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# --- 配置 Uvicorn 日誌 ---
# 註解掉以下程式碼，讓 Uvicorn 使用預設的 access logger 設定
# uvicorn_access_logger = logging.getLogger("uvicorn.access")
# uvicorn_access_logger.handlers = logger.handlers # 使用與 root logger 相同的 handlers
# uvicorn_access_logger.propagate = False # 防止日誌重複輸出到 root logger

# --- Uvicorn 日誌配置結束 ---

logger.info(f"日誌系統已設定完成，本次啟動日誌將輸出到控制台和 {log_file}")
# --- 日誌設定結束 ---


# 先初始化app實例
app = FastAPI(
    title="電動汽車充電站API",
    description="用於管理電動汽車充電站和用戶充電記錄的API",
    version="1.0.0",
    swagger_ui_parameters={
        "docExpansion": "none",
        "defaultModelsExpandDepth": -1
    }
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
    # 使用 logger.exception 來記錄錯誤，它會包含 traceback
    logger.exception(f"全局異常捕獲於 {request.url.path}: {error_detail}") 
    
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


# --- Frontend Static Files Setup Removed ---
# Frontend serving logic has been removed as it's not needed for this API-only setup.

# Restore original root route
@app.get("/")
async def root():
    return {
        "message": "歡迎使用電動汽車充電站API",
        "version": "1.0.0",
        "docs_url": "/docs"
    }

# --- Catch-all route removed ---


# 應用程式啟動事件處理
@app.on_event("startup")
async def startup_event_handler():
    """
    應用程式啟動事件。
    """
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", 22000))
    logger.info(f"✅ Volticar API 已啟動於 https://{host}:{port}") # 改為寫入日誌
    # 強制刷新日誌緩衝區，確保訊息立即寫入檔案
    for handler in logger.handlers:
        # FileHandler 也有 flush 方法
        if isinstance(handler, logging.FileHandler):
            handler.flush()

# 應用程式關閉事件處理
@app.on_event("shutdown")
async def shutdown_event_handler():
    """
    應用程式關閉事件。
    """
    logger.info("🛑 Volticar API 已關閉。") # 改為寫入日誌
    # 強制刷新日誌緩衝區，確保訊息立即寫入檔案
    for handler in logger.handlers:
        # FileHandler 也有 flush 方法
        if isinstance(handler, logging.FileHandler):
            handler.flush()

# --- 訊號處理 ---
def handle_shutdown_signal(signum, frame):
    """處理 SIGINT 和 SIGTERM 訊號，確保關閉日誌被記錄"""
    # 記錄帶有時間戳的關閉訊息
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    shutdown_message = f"🛑 Volticar API 收到關閉訊號，正在關閉... (時間: {timestamp})"
    print(shutdown_message) # 確保控制台有輸出

    # 嘗試記錄到 logger
    try:
        logger.info(shutdown_message)
        # 強制刷新日誌緩衝區
        for handler in logger.handlers:
            # 檢查 handler 是否有 flush 方法 (TimedRotatingFileHandler 有)
            if hasattr(handler, 'flush'):
                handler.flush()
        print("日誌已嘗試刷新。")
    except Exception as e:
        print(f"關閉時刷新日誌出錯: {e}") # 如果 logger 出錯，至少控制台有記錄

    # 移除 sys.exit(0)
    # 讓 Uvicorn 繼續處理關閉流程，它會觸發 FastAPI 的 shutdown 事件
    print("訊號已處理，交由 Uvicorn/FastAPI 進行關閉...")

# --- 訊號處理結束 ---


# 直接運行應用程序
if __name__ == "__main__":
    # 註冊訊號處理器
    signal.signal(signal.SIGINT, handle_shutdown_signal) # 處理 Ctrl+C
    signal.signal(signal.SIGTERM, handle_shutdown_signal) # 處理 kill 或 docker stop

    try:
        host = os.getenv("API_HOST", "0.0.0.0")
        port = int(os.getenv("API_PORT", 22000))

        # 使用 logger 記錄啟動訊息
        logger.info(f"準備啟動 API 服務於 https://{host}:{port}")
        logger.info(f"API 文檔位於 https://{host}:{port}/docs")
        # 啟動時也刷新一次，確保準備啟動的訊息寫入
        for handler in logger.handlers:
            if hasattr(handler, 'flush'):
                handler.flush()

        ssl_keyfile = os.environ.get("SSL_KEYFILE", "C:\\Certbot\\live\\volticar.dynns.com\\privkey.pem")
        ssl_certfile = os.environ.get("SSL_CERTFILE", "C:\\Certbot\\live\\volticar.dynns.com\\fullchain.pem")

        uvicorn.run(app, host=host, port=port, ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile)
    except Exception as e:
        print(f"啟動服務時發生錯誤: {str(e)}")
        traceback.print_exc()
        sys.exit(1)
