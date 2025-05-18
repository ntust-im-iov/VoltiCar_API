from fastapi import APIRouter, HTTPException, status, Form # Added Form
from typing import Dict, Any # Added Any back
from datetime import datetime
from bson import ObjectId # Import ObjectId if task_id is expected to be an ObjectId string

# Removed Task import from app.models.user
# from app.database.mongodb import volticar_db # Remove direct import of db
from app.database import mongodb as db_provider # Import the module itself

router = APIRouter(prefix="/tasks", tags=["任務"])

# 初始化集合 - These will be accessed via db_provider inside functions
# tasks_collection = volticar_db["Tasks"]
# users_collection = volticar_db["Users"]

# 獲取每日任務
@router.get("/daily", response_model=Dict[str, Any])
async def get_daily_tasks(user_id: str):
    """
    獲取用戶當日可完成的任務
    - user_id: 用戶ID
    """
    if db_provider.users_collection is None or db_provider.tasks_collection is None:
        raise HTTPException(status_code=503, detail="任務或用戶資料庫服務未初始化")

    # 檢查用戶是否存在
    user = await db_provider.users_collection.find_one({"user_id": user_id}) # await
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 獲取今日的任務
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    daily_tasks_cursor = db_provider.tasks_collection.find({ # find returns a cursor
        "type": "daily",
        "available_from": {"$lte": datetime.now()},
        "available_to": {"$gte": datetime.now()}
    })
    daily_tasks = await daily_tasks_cursor.to_list(length=None) # await and to_list
    
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
async def complete_task(
    user_id: str = Form(..., description="用戶ID"),
    task_id: str = Form(..., description="任務ID (ObjectId 字串)"),
    progress: int = Form(..., description="當前進度值")
):
    """
    更新任務完成進度 (使用表單欄位)

    - **user_id**: 用戶ID
    - **task_id**: 任務ID (ObjectId 字串)
    - **progress**: 當前進度值
    """
    # 參數直接從 Form 獲取
    if db_provider.users_collection is None or db_provider.tasks_collection is None:
        raise HTTPException(status_code=503, detail="任務或用戶資料庫服務未初始化")

    # 檢查用戶是否存在
    user = await db_provider.users_collection.find_one({"user_id": user_id}) # await
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 檢查任務是否存在 (假設 task_id 是 ObjectId 字符串)
    try:
        task = await db_provider.tasks_collection.find_one({"_id": ObjectId(task_id)}) # await
    except Exception: # Handle invalid ObjectId format
        task = None

    if not task:
        # Optionally, try finding by a 'task_id' field if it exists and is different from _id
        # task = await db_provider.tasks_collection.find_one({"task_id": task_id}) # await
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
    result = await db_provider.users_collection.update_one( # await
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
            await db_provider.users_collection.update_one( # await
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
    if db_provider.tasks_collection is None:
        raise HTTPException(status_code=503, detail="任務資料庫服務未初始化")
    # 獲取所有任務
    all_tasks_cursor = db_provider.tasks_collection.find({}) # find returns a cursor
    all_tasks = await all_tasks_cursor.to_list(length=None) # await and to_list
    
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
