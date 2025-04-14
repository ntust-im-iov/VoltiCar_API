from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any # Added Any back
from datetime import datetime
from bson import ObjectId # Import ObjectId if task_id is expected to be an ObjectId string

# Removed Task import from app.models.user
from app.database.mongodb import volticar_db

router = APIRouter(prefix="/tasks", tags=["任務"])

# 初始化集合
tasks_collection = volticar_db["Tasks"]
users_collection = volticar_db["Users"]

# 獲取每日任務
@router.get("/daily", response_model=Dict[str, Any])
async def get_daily_tasks(user_id: str):
    """
    獲取用戶當日可完成的任務
    - user_id: 用戶ID
    """
    # 檢查用戶是否存在
    user = users_collection.find_one({"user_id": user_id})
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
            "target": task.get("target", 100),
            "reward": task.get("reward", {})
        })
    
    return {
        "status": "success",
        "msg": "獲取每日任務成功",
        "tasks": formatted_tasks
    }

# 完成任務
@router.post("/complete", response_model=Dict[str, Any])
async def complete_task(user_id: str, task_id: str, progress: int):
    """
    更新任務完成進度
    - user_id: 用戶ID
    - task_id: 任務ID
    - progress: 當前進度值
    """
    # 檢查用戶是否存在
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 檢查任務是否存在 (假設 task_id 是 ObjectId 字符串)
    try:
        task = tasks_collection.find_one({"_id": ObjectId(task_id)})
    except Exception: # Handle invalid ObjectId format
        task = None

    if not task:
        # Optionally, try finding by a 'task_id' field if it exists and is different from _id
        # task = tasks_collection.find_one({"task_id": task_id})
        # if not task:
        raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="任務不存在"
            )
    
    # 獲取任務完成目標
    target = task.get("target", 100)
    
    # 判斷任務是否已完成
    completed = progress >= target
    
    # 更新用戶的任務進度
    task_key = f"tasks.{str(task['_id'])}"
    result = users_collection.update_one(
        {"user_id": user_id},
        {"$set": {
            f"{task_key}.progress": progress,
            f"{task_key}.completed": completed,
            f"{task_key}.last_updated": datetime.now()
        }}
    )
    
    # 如果任務剛完成，給予獎勵
    reward_given = False
    if completed and (
        "tasks" not in user or 
        str(task["_id"]) not in user["tasks"] or 
        not user["tasks"][str(task["_id"])].get("completed", False)
    ):
        reward = task.get("reward", {})
        if "carbon_credits" in reward and reward["carbon_credits"] > 0:
            users_collection.update_one(
                {"user_id": user_id},
                {"$inc": {"carbon_credits": reward["carbon_credits"]}}
            )
            reward_given = True
    
    return {
        "status": "success",
        "msg": "任務進度更新成功",
        "progress": progress,
        "completed": completed,
        "reward_given": reward_given
    }

# 獲取所有任務
@router.get("/", response_model=Dict[str, Any])
async def get_all_tasks():
    """
    獲取系統中所有可用的任務列表（管理用）
    """
    # 獲取所有任務
    all_tasks = list(tasks_collection.find())
    
    # 格式化任務
    formatted_tasks = []
    for task in all_tasks:
        formatted_tasks.append({
            "task_id": str(task["_id"]),
            "description": task.get("description", ""),
            "type": task.get("type", "regular"),
            "target": task.get("target", 100),
            "reward": task.get("reward", {})
        })
    
    return {
        "status": "success",
        "msg": "獲取所有任務成功",
        "total": len(formatted_tasks),
        "tasks": formatted_tasks
    }
