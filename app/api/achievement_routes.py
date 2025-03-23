from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any, List
from datetime import datetime

from app.models.user import Achievement
from app.database.mongodb import volticar_db

router = APIRouter(prefix="/achievements", tags=["成就系統"])

# 初始化集合
achievements_collection = volticar_db["Achievements"]
users_collection = volticar_db["Users"]

# 獲取用戶的成就列表
@router.get("/", response_model=Dict[str, Any])
async def get_achievements(user_uuid: str):
    # 檢查用戶是否存在
    user = users_collection.find_one({"user_uuid": user_uuid})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 獲取所有成就
    all_achievements = list(achievements_collection.find({}))
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
@router.post("/update", response_model=Dict[str, Any])
async def update_achievement(user_uuid: str, achievement_id: str, progress: int):
    # 檢查用戶是否存在
    user = users_collection.find_one({"user_uuid": user_uuid})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 檢查成就是否存在
    achievement = achievements_collection.find_one({"_id": achievement_id})
    if not achievement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="成就不存在"
        )
    
    # 獲取成就完成所需的目標進度
    target_progress = achievement.get("target_progress", 100)
    
    # 判斷成就是否已解鎖
    unlocked = progress >= target_progress
    
    # 更新用戶的成就進度
    user_achievement_key = f"achievements.{achievement_id}"
    users_collection.update_one(
        {"user_uuid": user_uuid},
        {"$set": {
            f"{user_achievement_key}.progress": progress,
            f"{user_achievement_key}.unlocked": unlocked,
            f"{user_achievement_key}.last_updated": datetime.now()
        }}
    )
    
    # 如果成就剛剛解鎖，給予獎勵
    if unlocked and (
        "achievements" not in user or 
        achievement_id not in user["achievements"] or 
        not user["achievements"][achievement_id].get("unlocked", False)
    ):
        reward = achievement.get("reward", {})
        if "carbon_credits" in reward:
            users_collection.update_one(
                {"user_uuid": user_uuid},
                {"$inc": {"carbon_credits": reward["carbon_credits"]}}
            )
    
    return {
        "status": "success",
        "msg": "成就進度更新成功",
        "progress": progress,
        "unlocked": unlocked
    } 