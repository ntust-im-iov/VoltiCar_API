from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta, datetime
from typing import List, Dict, Any

from app.models.user import User, UserCreate, UserInDB, Token, ChargingRequest, UserLogin
from app.utils.auth import authenticate_user, create_access_token, get_current_user, get_password_hash
from app.database.mongodb import users_collection
from app.utils.helpers import handle_mongo_data

router = APIRouter(prefix="/users", tags=["用戶"])

# 創建新用戶
@router.post("/", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate):
    # 檢查郵箱是否已被註冊
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此郵箱已被註冊"
        )
    
    # 生成密碼哈希
    hashed_password = get_password_hash(user.password)
    
    # 準備用戶數據
    user_dict = user.model_dump()
    user_dict["password"] = hashed_password
    user_dict["carbon_credits"] = 100  # 初始碳積分
    user_dict["charging_history"] = []
    
    # 插入數據庫
    result = users_collection.insert_one(user_dict)
    created_user = users_collection.find_one({"_id": result.inserted_id})
    
    # 處理ObjectId並返回
    return User(**handle_mongo_data(created_user))

# 登錄獲取令牌
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用戶名或密碼不正確",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 創建訪問令牌
    access_token = create_access_token(
        data={"sub": user.email}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# 獲取當前用戶信息
@router.get("/me", response_model=User)
async def read_users_me(current_user: UserInDB = Depends(get_current_user)):
    return current_user

# 獲取指定用戶信息
@router.get("/{user_id}", response_model=User)
async def read_user(user_id: str):
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶未找到"
        )
    
    # 處理ObjectId並返回
    user_data = handle_mongo_data(user)
    return User(**{k: v for k, v in user_data.items() if k != "password"})

# 添加充電記錄
@router.post("/{user_id}/charge", response_model=User)
async def add_charging_record(user_id: str, request: ChargingRequest):
    # 檢查用戶是否存在
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶未找到"
        )
    
    # 獲取充電站信息 - 避免循環導入
    from app.api.station_routes import get_station
    station = await get_station(request.station_id)
    
    # 創建充電記錄
    charging_record = {
        "station_id": request.station_id,
        "station_name": station["StationName"]["Zh_tw"],
        "charging_time": request.charging_time,
        "timestamp": datetime.utcnow()
    }
    
    # 更新用戶充電歷史和碳積分
    result = users_collection.update_one(
        {"user_id": user_id},
        {
            "$push": {"charging_history": charging_record},
            "$inc": {"carbon_credits": request.carbon_credits_earned}
        }
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新失敗"
        )
    
    # 獲取更新後的用戶信息
    updated_user = users_collection.find_one({"user_id": user_id})
    user_data = handle_mongo_data(updated_user)
    
    return User(**{k: v for k, v in user_data.items() if k != "password"}) 