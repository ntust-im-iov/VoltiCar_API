from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import api_router
import os

# 創建FastAPI應用實例
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

# 包含API路由
app.include_router(api_router)

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
    return {"status": "ok", "environment": os.getenv("API_ENV", "development")}

# 啟動服務器
if __name__ == "__main__":
    import uvicorn
    # 使用0.0.0.0綁定所有網絡介面，而不是固定IP
    host = "0.0.0.0"  # 綁定所有網絡介面
    port = int(os.getenv("API_PORT", "22000"))
    uvicorn.run("main:app", host=host, port=port, reload=True)