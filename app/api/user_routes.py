from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta, datetime
from typing import List, Dict, Any

from app.models.user import User, UserCreate, UserInDB, Token, ChargingRequest, UserLogin
from app.utils.auth import authenticate_user, create_access_token, get_current_user, get_password_hash
from app.database.mongodb import users_collection
from app.utils.helpers import handle_mongo_data

router = APIRouter(prefix="/users", tags=["用户"])

# 创建新用户
@router.post("/", response_model=User, status_code=status.HTTP_201_CREATED)
async def create_user(user: UserCreate):
    # 检查邮箱是否已被注册
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此邮箱已被注册"
        )
    
    # 生成密码哈希
    hashed_password = get_password_hash(user.password)
    
    # 准备用户数据
    user_dict = user.model_dump()
    user_dict["password"] = hashed_password
    user_dict["carbon_credits"] = 100  # 初始碳积分
    user_dict["charging_history"] = []
    
    # 插入数据库
    result = users_collection.insert_one(user_dict)
    created_user = users_collection.find_one({"_id": result.inserted_id})
    
    # 处理ObjectId并返回
    return User(**handle_mongo_data(created_user))

# 登录获取令牌
@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码不正确",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # 创建访问令牌
    access_token = create_access_token(
        data={"sub": user.email}
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

# 获取当前用户信息
@router.get("/me", response_model=User)
async def read_users_me(current_user: UserInDB = Depends(get_current_user)):
    return current_user

# 获取指定用户信息
@router.get("/{user_id}", response_model=User)
async def read_user(user_id: str):
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户未找到"
        )
    
    # 处理ObjectId并返回
    user_data = handle_mongo_data(user)
    return User(**{k: v for k, v in user_data.items() if k != "password"})

# 添加充电记录
@router.post("/{user_id}/charge", response_model=User)
async def add_charging_record(user_id: str, request: ChargingRequest):
    # 检查用户是否存在
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户未找到"
        )
    
    # 获取充电站信息 - 避免循环导入
    from app.api.station_routes import get_station
    station = await get_station(request.station_id)
    
    # 创建充电记录
    charging_record = {
        "station_id": request.station_id,
        "station_name": station["StationName"]["Zh_tw"],
        "charging_time": request.charging_time,
        "timestamp": datetime.utcnow()
    }
    
    # 更新用户充电历史和碳积分
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
            detail="更新失败"
        )
    
    # 获取更新后的用户信息
    updated_user = users_collection.find_one({"user_id": user_id})
    user_data = handle_mongo_data(updated_user)
    
    return User(**{k: v for k, v in user_data.items() if k != "password"}) 