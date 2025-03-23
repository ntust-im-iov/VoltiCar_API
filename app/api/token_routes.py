from fastapi import APIRouter, HTTPException, status
from typing import Dict, Any
from datetime import datetime, timedelta

from app.utils.auth import create_access_token, get_password_hash
from app.database.mongodb import volticar_db

router = APIRouter(prefix="/tokens", tags=["令牌"])

# 初始化集合
tokens_collection = volticar_db["Tokens"]
users_collection = volticar_db["Users"]

# 獲取令牌
@router.post("/get", response_model=Dict[str, Any])
async def get_token(token_data: Dict[str, Any]):
    token = token_data.get("token")
    device = token_data.get("device")
    user_uuid = token_data.get("user_uuid")
    
    # 檢查必要參數
    if not user_uuid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少用戶ID"
        )
    
    # 檢查用戶是否存在
    user = users_collection.find_one({"user_uuid": user_uuid})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 檢查是否有現有令牌
    existing_token = tokens_collection.find_one({
        "user_uuid": user_uuid,
        "device": device,
        "expires_at": {"$gt": datetime.now()}
    })
    
    if existing_token and token:
        # 如果提供了令牌，驗證它是否有效
        if existing_token["token"] == token:
            return {
                "status": "success",
                "msg": "令牌有效",
                "token": token
            }
    
    # 生成新令牌
    access_token_expires = timedelta(days=30)  # 令牌30天有效
    new_token = create_access_token(
        data={"sub": user_uuid, "device": device},
        expires_delta=access_token_expires
    )
    
    # 存儲令牌信息
    token_info = {
        "user_uuid": user_uuid,
        "device": device,
        "token": new_token,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + access_token_expires
    }
    
    # 如果有現有令牌，更新它；否則創建新記錄
    if existing_token:
        tokens_collection.update_one(
            {"_id": existing_token["_id"]},
            {"$set": token_info}
        )
    else:
        tokens_collection.insert_one(token_info)
    
    return {
        "status": "success",
        "msg": "獲取令牌成功",
        "token": new_token
    }

# 保存令牌
@router.post("/save", response_model=Dict[str, Any])
async def save_token(token_data: Dict[str, Any]):
    token = token_data.get("token")
    device = token_data.get("device")
    user_uuid = token_data.get("user_uuid")
    
    # 檢查必要參數
    if not all([token, device, user_uuid]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="缺少必要參數"
        )
    
    # 檢查用戶是否存在
    user = users_collection.find_one({"user_uuid": user_uuid})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )
    
    # 檢查令牌是否有效
    existing_token = tokens_collection.find_one({
        "user_uuid": user_uuid,
        "token": token
    })
    
    if not existing_token:
        # 如果令牌不存在，創建一個新的
        token_info = {
            "user_uuid": user_uuid,
            "device": device,
            "token": token,
            "created_at": datetime.now(),
            "expires_at": datetime.now() + timedelta(days=30)  # 30天有效
        }
        
        tokens_collection.insert_one(token_info)
    else:
        # 如果令牌存在，更新設備和過期時間
        tokens_collection.update_one(
            {"_id": existing_token["_id"]},
            {"$set": {
                "device": device,
                "expires_at": datetime.now() + timedelta(days=30)
            }}
        )
    
    return {
        "status": "success",
        "msg": "令牌保存成功"
    } 