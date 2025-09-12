from fastapi import APIRouter, HTTPException, status, Body, Form # Added Form
from typing import Dict, Any # Removed List
from datetime import datetime
from bson import ObjectId # Import ObjectId
from pydantic import BaseModel # Added BaseModel

# Removed Achievement import
# from app.database.mongodb import volticar_db # Remove direct import of db
from app.database import mongodb as db_provider # Import the module itself

router = APIRouter(prefix="/achievements", tags=["成就系統"])

# Pydantic 模型用於更新成就進度
class AchievementUpdate(BaseModel):
    user_uuid: str
    achievement_id: str
    progress: int

# 初始化集合 - These will be accessed via db_provider inside functions
# achievements_collection = volticar_db["Achievements"]
# users_collection = volticar_db["Users"]

# 獲取用戶的成就列表
@router.get("/", response_model=Dict[str, Any], summary="獲取用戶的成就列表")
async def get_achievements(user_uuid: str):
    """
    獲取指定用戶的全部成就狀態列表，包括已解鎖和未解鎖的。
    - **user_uuid**: 要查詢的用戶的唯一標識符 (UUID)。
    """
    if db_provider.users_collection is None or db_provider.achievements_collection is None:
        raise HTTPException(status_code=503, detail="成就或用戶資料庫服務未初始化")

    # 檢查用戶是否存在
    user = await db_provider.users_collection.find_one({"user_uuid": user_uuid}) # await
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 獲取所有成就
    all_achievements_cursor = db_provider.achievements_collection.find({}) # find returns a cursor
    all_achievements = await all_achievements_cursor.to_list(length=None) # await and to_list
    user_achievements = []
    
    for achievement in all_achievements:
        # 檢查用戶是否解鎖了此成就
        unlocked = False
        progress = 0
        
        if "achievements" in user and str(achievement["_id"]) in user["achievements"]:
            user_achievement = user["achievements"][str(achievement["_id"])]
            unlocked = user_achievement.get("unlocked", False)
            progress = user_achievement.get("progress", 0)
        
        user_achievements.append({
            "achievement_id": str(achievement["_id"]),
            "description": achievement.get("description", ""),
            "progress": progress,
            "unlocked": unlocked
        })
    
    return {
        "status": "success",
        "msg": "獲取成就列表成功",
        "achievements": user_achievements
    }

# 更新成就進度
@router.post("/update", response_model=Dict[str, Any], summary="更新指定用戶的成就進度")
async def update_achievement(
    user_uuid: str = Form(..., description="用戶的 UUID"),
    achievement_id: str = Form(..., description="成就的 ID (字串格式)"),
    progress: int = Form(..., description="新的進度值")
):
    """
    更新特定用戶某個成就的進度。
    - 如果進度達到或超過目標，會自動將該成就標記為「已解鎖」。
    - 如果成就是首次解鎖，將會發放定義在該成就中的獎勵（例如，碳積分）。
    """
    # 參數直接從 Form 獲取
    achievement_id_str = achievement_id # Rename to avoid conflict with ObjectId

    if db_provider.users_collection is None or db_provider.achievements_collection is None:
        raise HTTPException(status_code=503, detail="成就或用戶資料庫服務未初始化")

    # 檢查用戶是否存在
    user = await db_provider.users_collection.find_one({"user_uuid": user_uuid}) # await
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )

    # 檢查成就是否存在 (使用 ObjectId)
    try:
        achievement_oid = ObjectId(achievement_id_str)
        achievement = await db_provider.achievements_collection.find_one({"_id": achievement_oid}) # await
    except Exception: # Handles invalid ObjectId format
        achievement = None

    if not achievement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="成就不存在或ID格式錯誤"
        )

    # 獲取成就完成所需的目標進度
    target_progress = achievement.get("target_progress", 100)
    
    # 判斷成就是否已解鎖
    unlocked = progress >= target_progress

    # 更新用戶的成就進度 (使用 achievement_id_str 作為 key)
    user_achievement_key = f"achievements.{achievement_id_str}"
    await db_provider.users_collection.update_one( # await
        {"user_uuid": user_uuid},
        {"$set": {
            f"{user_achievement_key}.progress": progress,
            f"{user_achievement_key}.unlocked": unlocked,
            f"{user_achievement_key}.last_updated": datetime.now()
        }}
    )
    
    # 如果成就剛剛解鎖，給予獎勵 (使用 achievement_id_str 作為 key)
    if unlocked and (
        "achievements" not in user or
        achievement_id_str not in user["achievements"] or
        not user["achievements"][achievement_id_str].get("unlocked", False)
    ):
        reward = achievement.get("reward", {})
        if "carbon_credits" in reward:
            await db_provider.users_collection.update_one( # await
                {"user_uuid": user_uuid},
                {"$inc": {"carbon_credits": reward["carbon_credits"]}}
            )
    
    return {
        "status": "success",
        "msg": "成就進度更新成功",
        "progress": progress,
        "unlocked": unlocked
    }
