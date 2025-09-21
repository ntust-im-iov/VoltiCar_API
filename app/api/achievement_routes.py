from fastapi import APIRouter, HTTPException, status, Body, Form # Added Form
from typing import Dict, Any # Removed List
from datetime import datetime
import uuid
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
    if db_provider.users_collection is None or db_provider.achievement_definitions_collection is None or db_provider.player_achievements_collection is None:
        raise HTTPException(status_code=503, detail="成就或用戶資料庫服務未初始化")

    # 檢查用戶是否存在
    user = await db_provider.users_collection.find_one({"user_id": uuid.UUID(user_uuid)}) # await
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 獲取所有成就定義
    all_achievements_cursor = db_provider.achievement_definitions_collection.find({})
    all_achievements = await all_achievements_cursor.to_list(length=None)
    
    # 獲取玩家已獲得的成就
    player_achievements_cursor = db_provider.player_achievements_collection.find({"user_id": uuid.UUID(user_uuid)})
    player_achievements_list = await player_achievements_cursor.to_list(length=None)
    player_achievements_map = {item['achievement_id']: item for item in player_achievements_list}
    
    user_achievements = []
    
    for achievement_def in all_achievements:
        achievement_id = achievement_def['achievement_id']
        unlocked = achievement_id in player_achievements_map
        completed_at = player_achievements_map.get(achievement_id, {}).get('completed_at')
        
        user_achievements.append({
            "achievement_id": achievement_id,
            "name": achievement_def.get("name", ""),
            "description": achievement_def.get("description", ""),
            "unlocked": unlocked,
            "completed_at": completed_at
        })
    
    return {
        "status": "success",
        "msg": "獲取成就列表成功",
        "achievements": user_achievements
    }

# 給予玩家成就
@router.post("/grant", response_model=Dict[str, Any], summary="給予玩家一個成就")
async def grant_achievement(
    user_uuid: str = Form(..., description="用戶的 UUID"),
    achievement_id: str = Form(..., description="成就的 ID")
):
    """
    直接給予特定用戶一個成就。
    - 如果玩家已擁有此成就，則不做任何事。
    """
    if db_provider.users_collection is None or db_provider.achievement_definitions_collection is None or db_provider.player_achievements_collection is None:
        raise HTTPException(status_code=503, detail="成就或用戶資料庫服務未初始化")

    # 檢查用戶是否存在
    user = await db_provider.users_collection.find_one({"user_id": uuid.UUID(user_uuid)})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )

    # 檢查成就是否存在
    try:
        achievement_uuid = uuid.UUID(achievement_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="無效的成就 ID 格式")

    achievement = await db_provider.achievement_definitions_collection.find_one({"achievement_id": achievement_uuid})
    if not achievement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="成就不存在"
        )
        
    # 檢查玩家是否已擁有此成就
    existing_achievement = await db_provider.player_achievements_collection.find_one({
        "user_id": uuid.UUID(user_uuid),
        "achievement_id": achievement_uuid
    })
    
    if existing_achievement:
        return {
            "status": "success",
            "msg": "玩家已擁有此成就"
        }

    # 新增成就記錄
    new_achievement = {
        "user_id": uuid.UUID(user_uuid),
        "achievement_id": achievement_uuid,
        "completed_at": datetime.now()
    }
    await db_provider.player_achievements_collection.insert_one(new_achievement)
    
    return {
        "status": "success",
        "msg": "成就已成功給予"
    }
