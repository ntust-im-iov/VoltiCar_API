from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import api_router
import os

# 创建FastAPI应用实例
app = FastAPI(
    title="电动汽车充电站API",
    description="用于管理电动汽车充电站和用户充电记录的API",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有来源，生产环境应限制
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
        "message": "欢迎使用电动汽车充电站API",
        "version": "1.0.0",
        "docs_url": "/docs"
    }

# 健康检查端点
@app.get("/health")
async def health_check():
    return {"status": "ok", "environment": os.getenv("API_ENV", "development")}

# 启动服务器
if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run("main:app", host=host, port=port, reload=True) 