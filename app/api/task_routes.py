from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any
from datetime import datetime

from app.models.user import Task
from app.database.mongodb import volticar_db

router = APIRouter(prefix="/tasks", tags=["任務"])

# 初始化集合
tasks_collection = volticar_db["Tasks"]
users_collection = volticar_db["Users"]

# 獲取每日任務
@router.get("/daily", response_model=Dict[str, Any])
async def get_daily_tasks(user_uuid: str):
    # 檢查用戶是否存在
    user = users_collection.find_one({"user_uuid": user_uuid})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 獲取今日的任務
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    daily_tasks = list(tasks_collection.find({
        "type": "daily",
        "available_from": {"$lte": datetime.now()},
        "available_to": {"$gte": datetime.now()}
    }))
    
    # 格式化任務
    formatted_tasks = []
    for task in daily_tasks:
        # 查詢用戶的任務進度
        progress = 0
        if "tasks" in user and str(task["_id"]) in user["tasks"]:
            progress = user["tasks"][str(task["_id"])].get("progress", 0)
        
        formatted_tasks.append({
            "task_id": str(task["_id"]),
            "description": task.get("description", ""),
            "progress": progress,
            "reward": task.get("reward", {})
        })
    
    return {
        "status": "success",
        "msg": "獲取每日任務成功",
        "tasks": formatted_tasks
    } 