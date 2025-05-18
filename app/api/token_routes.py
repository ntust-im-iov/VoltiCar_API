from fastapi import APIRouter, HTTPException, status, Body, Form
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.utils.auth import create_access_token
from app.database import mongodb as db_provider # Import the module itself

router = APIRouter(prefix="/tokens", tags=["令牌"])

# Pydantic 模型
class TokenRequest(BaseModel):
    token: Optional[str] = None
    device: str
    user_uuid: str

class TokenSaveRequest(BaseModel):
    token: str
    device: str
    user_uuid: str

# 獲取令牌
@router.post("/get", response_model=Dict[str, Any])
async def get_token(
    user_uuid: str = Form(..., description="用戶的 UUID"),
    device: str = Form(..., description="設備標識符"),
    token: Optional[str] = Form(None, description="現有令牌 (可選，用於驗證)")
):
    """
    獲取或驗證用戶令牌 (使用表單欄位)

    - **user_uuid**: 用戶的 UUID
    - **device**: 設備標識符
    - **token**: 現有令牌 (可選，用於驗證)
    """
    if db_provider.users_collection is None or db_provider.tokens_collection is None:
        raise HTTPException(status_code=503, detail="令牌或用戶資料庫服務未初始化")

    # 檢查用戶是否存在 (使用 user_uuid)
    user = await db_provider.users_collection.find_one({"user_uuid": user_uuid})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )

    # 檢查是否有現有令牌
    existing_token = await db_provider.tokens_collection.find_one({
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
    new_token_str = create_access_token( # Renamed to avoid conflict with token parameter
        data={"sub": user_uuid, "device": device},
        expires_delta=access_token_expires
    )

    # 存儲令牌信息
    token_info = {
        "user_uuid": user_uuid,
        "device": device,
        "token": new_token_str,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + access_token_expires
    }

    # 如果有現有令牌，更新它；否則創建新記錄
    if existing_token:
        await db_provider.tokens_collection.update_one(
            {"_id": existing_token["_id"]},
            {"$set": token_info}
        )
    else:
        await db_provider.tokens_collection.insert_one(token_info)

    return {
        "status": "success",
        "msg": "獲取令牌成功",
        "token": new_token_str
    }

# 保存令牌
@router.post("/save", response_model=Dict[str, Any])
async def save_token(
    user_uuid: str = Form(..., description="用戶的 UUID"),
    device: str = Form(..., description="設備標識符"),
    token: str = Form(..., description="要保存的令牌")
):
    """
    保存用戶令牌 (使用表單欄位)

    - **user_uuid**: 用戶的 UUID
    - **device**: 設備標識符
    - **token**: 要保存的令牌
    """
    if db_provider.users_collection is None or db_provider.tokens_collection is None:
        raise HTTPException(status_code=503, detail="令牌或用戶資料庫服務未初始化")

    # 檢查用戶是否存在 (使用 user_uuid)
    user = await db_provider.users_collection.find_one({"user_uuid": user_uuid})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )

    # 檢查令牌是否有效
    existing_token = await db_provider.tokens_collection.find_one({
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
        await db_provider.tokens_collection.insert_one(token_info)
    else:
        # 如果令牌存在，更新設備和過期時間
        await db_provider.tokens_collection.update_one(
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
