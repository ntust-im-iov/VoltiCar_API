from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from datetime import timedelta, datetime
from typing import List, Dict, Any, Optional
import uuid
import random
import string

from app.models.user import (
    User, UserCreate, UserInDB, Token, UserLogin, PhoneVerification, 
    VerifyCodeRequest, Task, Achievement, LeaderboardItem, RewardItem, Inventory, FriendAction
)
from app.utils.auth import authenticate_user, create_access_token, get_current_user, get_password_hash
from app.database.mongodb import volticar_db
from app.utils.helpers import handle_mongo_data

router = APIRouter(prefix="/users", tags=["用戶"])

# 初始化集合
users_collection = volticar_db["Users"]
tasks_collection = volticar_db["Tasks"]
achievements_collection = volticar_db["Achievements"]
rewards_collection = volticar_db["Rewards"]
verify_codes_collection = volticar_db["VerifyCodes"]

# 訪問令牌的過期時間（以分鐘為單位）
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7天過期

# 創建新用戶 (註冊)
@router.post("/register", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate):
    # 檢查郵箱是否已被註冊
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此郵箱已被註冊"
        )
    
    # 檢查帳號是否已被使用
    if users_collection.find_one({"account": user.account}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此帳號已被使用"
        )
    
    # 檢查手機號是否已被註冊
    if users_collection.find_one({"phone": user.phone}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此手機號已被註冊"
        )
    
    # 生成密碼哈希
    hashed_password = get_password_hash(user.password)
    
    # 生成用戶UUID
    user_uuid = str(uuid.uuid4())
    
    # 準備用戶數據
    user_dict = {
        "account": user.account,
        "email": user.email,
        "password": hashed_password,
        "phone": user.phone,
        "name": user.name,
        "user_uuid": user_uuid,
        "carbon_credits": 100,  # 初始碳積分
        "created_at": datetime.now(),
        "last_login": datetime.now(),
        "vehicles": [],
        "tasks": [],
        "achievements": [],
        "inventory": []
    }
    
    # 插入到數據庫
    result = users_collection.insert_one(user_dict)
    
    if not result.inserted_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="創建用戶失敗"
        )
    
    return {
        "status": "success",
        "msg": "用戶註冊成功",
        "user_uuid": user_uuid
    }

# 用戶登入
@router.post("/login", response_model=Dict[str, Any])
async def login(user_login: UserLogin):
    # 確定使用哪個字段進行登錄驗證
    query = {}
    if user_login.email:
        query["email"] = user_login.email
    elif user_login.account:
        query["account"] = user_login.account
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請提供帳號或郵箱"
        )
    
    # 查詢用戶
    user = users_collection.find_one(query)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用戶不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 驗證密碼
    authenticated = authenticate_user(user, user_login.password)
    
    if not authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="密碼錯誤",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 更新最後登錄時間
    users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {"last_login": datetime.now()}}
    )
    
    # 創建訪問令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["user_uuid"]},
        expires_delta=access_token_expires
    )
    
    return {
        "status": "success",
        "msg": "登入成功",
        "user_uuid": user["user_uuid"],
        "access_token": access_token,
        "token_type": "bearer"
    }

# 獲取個人資料
@router.get("/profile", response_model=Dict[str, Any])
async def get_user_profile(current_user: Dict = Depends(get_current_user)):
    user_info = {
        "user_name": current_user.get("name", ""),
        "user_id": current_user.get("user_uuid", ""),
        "email": current_user.get("email", ""),
        "phone": current_user.get("phone", ""),
        "carbon_credits": current_user.get("carbon_credits", 0)
    }
    
    return {
        "status": "success",
        "msg": "獲取用戶資訊成功",
        "user_info": user_info
    }

# 發送驗證碼
@router.post("/verify-code", response_model=Dict[str, Any])
async def send_verification_code(request: VerifyCodeRequest):
    # 生成6位數驗證碼
    verify_code = ''.join(random.choices(string.digits, k=6))
    
    # 存儲驗證碼（實際應用中應該發送短信）
    verify_data = {
        "phone": request.phone,
        "code": verify_code,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(minutes=10)  # 驗證碼10分鐘後過期
    }
    
    # 刪除舊的驗證碼
    verify_codes_collection.delete_many({"phone": request.phone})
    
    # 插入新的驗證碼
    verify_codes_collection.insert_one(verify_data)
    
    # 實際應用中，這裡應該調用SMS API發送驗證碼
    # 在此示例中，我們直接返回驗證碼（測試用途）
    return {
        "status": "success",
        "msg": "驗證碼發送成功",
        "verify_code": verify_code  # 實際應用中不應返回此值
    }

# 驗證手機號
@router.post("/verify-phone", response_model=Dict[str, Any])
async def verify_phone(verification: PhoneVerification):
    # 檢查驗證碼是否有效
    verify_record = verify_codes_collection.find_one({
        "phone": verification.phone,
        "expires_at": {"$gt": datetime.now()}
    })
    
    if not verify_record or verify_record["code"] != verification.verify_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="驗證碼無效或已過期"
        )
    
    # 驗證成功，刪除驗證碼記錄
    verify_codes_collection.delete_one({"_id": verify_record["_id"]})
    
    return {
        "status": "success",
        "msg": "手機號驗證成功"
    }

# 獲取充電站信息
@router.get("/charging-stations", response_model=Dict[str, Any])
async def get_charging_stations(user_uuid: str, location: str):
    # 解析位置字符串為經緯度坐標
    try:
        lat, lng = map(float, location.split(","))
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="位置格式錯誤，應為\"緯度,經度\""
        )
    
    # 這裡應該調用充電站服務獲取附近的充電站
    # 示例中，我們返回模擬數據
    stations = [
        {
            "station_id": "station1",
            "name": "充電站1",
            "distance": 0.5,
            "availability": True
        },
        {
            "station_id": "station2",
            "name": "充電站2",
            "distance": 1.2,
            "availability": False
        }
    ]
    
    return {
        "status": "success",
        "msg": "獲取充電站信息成功",
        "stations": stations
    }

# 獲取任務列表
@router.get("/tasks", response_model=Dict[str, Any])
async def get_user_tasks(user_uuid: str):
    # 查詢用戶的任務
    user = users_collection.find_one({"user_uuid": user_uuid})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 獲取可用任務
    all_tasks = list(tasks_collection.find({}))
    user_tasks = []
    
    for task in all_tasks:
        # 計算任務完成進度（實際應用中應有更複雜的邏輯）
        progress = 0
        if "user_tasks" in user and task["_id"] in user["user_tasks"]:
            progress = user["user_tasks"][task["_id"]]["progress"]
        
        user_tasks.append({
            "task_id": str(task["_id"]),
            "description": task.get("description", ""),
            "progress": progress,
            "reward": task.get("reward", {})
        })
    
    return {
        "status": "success",
        "msg": "獲取任務列表成功",
        "tasks": user_tasks
    }

# 獲取排行榜
@router.get("/leaderboard", response_model=Dict[str, Any])
async def get_leaderboard(time_range: str = "week"):
    # 根據時間範圍設置查詢條件
    if time_range == "day":
        start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    elif time_range == "week":
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_time = today - timedelta(days=today.weekday())
    elif time_range == "month":
        start_time = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無效的時間範圍，應為 day、week 或 month"
        )
    
    # 聚合查詢獲取排行榜
    # 實際應用中應該有更複雜的計分邏輯
    leaderboard = list(users_collection.find(
        {"last_login": {"$gte": start_time}},
        {"user_uuid": 1, "name": 1, "carbon_credits": 1}
    ).sort("carbon_credits", -1).limit(10))
    
    # 格式化結果
    result = []
    for i, user in enumerate(leaderboard):
        result.append({
            "rank": i + 1,
            "user_uuid": user["user_uuid"],
            "name": user.get("name", "Unknown"),
            "score": user.get("carbon_credits", 0)
        })
    
    return {
        "status": "success",
        "msg": "獲取排行榜成功",
        "leaderboard": result
    }

# 兌換獎勵
@router.post("/redeem-reward", response_model=Dict[str, Any])
async def redeem_reward(user_uuid: str, points: int = Body(...), reward_id: str = Body(...)):
    # 查詢用戶
    user = users_collection.find_one({"user_uuid": user_uuid})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 檢查積分是否足夠
    if user.get("carbon_credits", 0) < points:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="積分不足"
        )
    
    # 查詢獎勵
    reward = rewards_collection.find_one({"_id": reward_id})
    if not reward:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="獎勵項目不存在"
        )
    
    # 扣除積分
    users_collection.update_one(
        {"user_uuid": user_uuid},
        {"$inc": {"carbon_credits": -points}}
    )
    
    # 添加獎勵到用戶物品庫
    users_collection.update_one(
        {"user_uuid": user_uuid},
        {"$push": {"inventory": reward_id}}
    )
    
    return {
        "status": "success",
        "msg": "兌換獎勵成功",
        "reward_item": reward.get("name", "")
    }

# 獲取用戶物品庫
@router.get("/inventory", response_model=Dict[str, Any])
async def get_user_inventory(user_uuid: str):
    # 查詢用戶
    user = users_collection.find_one({"user_uuid": user_uuid})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 獲取物品庫
    inventory_ids = user.get("inventory", [])
    inventory_items = []
    
    # 如果有物品，查詢每個物品的詳細信息
    if inventory_ids:
        for item_id in inventory_ids:
            item = rewards_collection.find_one({"_id": item_id})
            if item:
                inventory_items.append({
                    "item_id": str(item["_id"]),
                    "name": item.get("name", ""),
                    "description": item.get("description", "")
                })
    
    return {
        "status": "success",
        "msg": "獲取物品庫成功",
        "inventory": {"owned_items": inventory_items}
    }

# 獲取用戶成就
@router.get("/achievements", response_model=Dict[str, Any])
async def get_user_achievements(user_uuid: str):
    # 查詢用戶
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

# 添加/刪除好友
@router.post("/friends", response_model=Dict[str, Any])
async def manage_friends(friend_action: FriendAction):
    # 檢查用戶是否存在
    user = users_collection.find_one({"user_uuid": friend_action.user_uuid})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 檢查好友是否存在
    friend = users_collection.find_one({"user_uuid": friend_action.friend_uuid})
    if not friend:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="好友不存在"
        )
    
    # 處理添加好友
    if friend_action.action == "add":
        # 檢查是否已經是好友
        if "friends" in user and friend_action.friend_uuid in user["friends"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="已經是好友"
            )
        
        # 添加好友關係（雙向）
        users_collection.update_one(
            {"user_uuid": friend_action.user_uuid},
            {"$addToSet": {"friends": friend_action.friend_uuid}}
        )
        
        users_collection.update_one(
            {"user_uuid": friend_action.friend_uuid},
            {"$addToSet": {"friends": friend_action.user_uuid}}
        )
        
        return {
            "status": "success",
            "msg": "添加好友成功"
        }
    
    # 處理刪除好友
    elif friend_action.action == "remove":
        # 檢查是否真的是好友
        if "friends" not in user or friend_action.friend_uuid not in user["friends"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不是好友"
            )
        
        # 移除好友關係（雙向）
        users_collection.update_one(
            {"user_uuid": friend_action.user_uuid},
            {"$pull": {"friends": friend_action.friend_uuid}}
        )
        
        users_collection.update_one(
            {"user_uuid": friend_action.friend_uuid},
            {"$pull": {"friends": friend_action.user_uuid}}
        )
        
        return {
            "status": "success",
            "msg": "移除好友成功"
        }
    
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無效的操作，應為 'add' 或 'remove'"
        ) 