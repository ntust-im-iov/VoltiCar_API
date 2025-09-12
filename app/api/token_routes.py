from fastapi import APIRouter, HTTPException, status, Body, Form, Query, Request
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from pydantic import BaseModel
import httpx # 使用 httpx 進行異步 HTTP 請求
import os
import json
import aiofiles # 用於異步檔案操作
import logging # 引入日誌模組

from app.utils.auth import create_access_token
from app.database import mongodb as db_provider # Import the module itself

router = APIRouter(prefix="/tokens", tags=["令牌"])
logger = logging.getLogger(__name__) # 獲取當前模組的 logger

DATA_DIR = "data"
USER_MAPPINGS_FILE = os.path.join(DATA_DIR, "user_github_mappings.json")

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
@router.post("/get", summary="獲取或驗證用戶令牌", response_model=Dict[str, Any])
async def get_token(
    user_uuid: str = Form(..., description="用戶的 UUID"),
    device: str = Form(..., description="設備標識符"),
    token: Optional[str] = Form(None, description="現有令牌 (可選，用於驗證)")
):
    """
    此端點用於為特定用戶和設備獲取或驗證一個長期有效的令牌。
    - 如果提供了 `token` 參數，將驗證其有效性。
    - 如果未提供 `token` 或現有令牌無效，將生成一個新的 30 天有效期的令牌。
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
@router.post("/save", summary="保存用戶令牌", response_model=Dict[str, Any])
async def save_token(
    user_uuid: str = Form(..., description="用戶的 UUID"),
    device: str = Form(..., description="設備標識符"),
    token: str = Form(..., description="要保存的令牌")
):
    """
    保存或更新指定用戶和設備的令牌記錄。
    - 如果令牌已存在，則更新其設備資訊和過期時間。
    - 如果令牌不存在，則創建一條新的令牌記錄。
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

# GitHub OAuth 回呼端點
@router.get("/github/callback", summary="GitHub OAuth 授權回呼", response_model=Dict[str, Any])
async def github_callback(
    code: Optional[str] = Query(None, description="GitHub 提供的臨時授權碼"),
    state: Optional[str] = Query(None, description="用於防止 CSRF 攻擊並傳遞用戶狀態的唯一字串")
):
    """
    處理 GitHub OAuth 2.0 流程的伺服器端回呼。
    1.  接收從 GitHub 重新導向來的 `code` 和 `state`。
    2.  使用 `code` 向 GitHub API 交換 `access_token`。
    3.  使用 `access_token` 獲取用戶的 GitHub 用戶名。
    4.  將 `state` 作為鍵，`access_token` 和 `github_username` 作為值，存儲在 `data/user_github_mappings.json` 檔案中，以供後續的 Bot 驗證流程使用。
    """
    if not code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未提供授權碼 (code)"
        )
    if not state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="未提供狀態參數 (state)"
        )

    client_id = os.getenv("GITHUB_CLIENT_ID")
    client_secret = os.getenv("GITHUB_CLIENT_SECRET")

    if not client_id or not client_secret:
        logger.error("GitHub OAuth Client ID 或 Secret 未在環境變數中設定。")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub OAuth Client ID 或 Secret 未設定"
        )
    logger.info("成功獲取 GitHub OAuth Client ID 和 Secret。")

    # 1. 用 code 交換 access token
    logger.info(f"準備使用 code 交換 access token。Code: {code[:10]}... (為安全截斷顯示)")
    token_url = "https://github.com/login/oauth/access_token"
    redirect_uri = os.getenv("GITHUB_CALLBACK_URL")
    if not redirect_uri:
        logger.error("GITHUB_CALLBACK_URL 未在環境變數中設定。")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GitHub 回呼 URL 未設定"
        )
    
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri
    }
    headers = {"Accept": "application/json"}

    access_token = None
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"向 {token_url} 發送 POST 請求以交換 token。")
            response = await client.post(token_url, data=payload, headers=headers)
            response.raise_for_status()
            token_data = response.json()
            access_token = token_data.get("access_token")
            if access_token:
                logger.info("成功從 GitHub 交換到 access_token。")
            else:
                logger.error(f"未能從 GitHub 獲取 access_token。收到的回應: {token_data}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"未能從 GitHub 獲取 access_token: {token_data}"
                )
    except httpx.HTTPStatusError as e:
        logger.error(f"交換 GitHub access token 失敗: {e.response.status_code} - {e.response.text}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"交換 GitHub access token 失敗: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"請求 GitHub access token 時發生網路錯誤: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"請求 GitHub access token 時發生錯誤: {str(e)}"
        )
    except json.JSONDecodeError as e:
        logger.error(f"解析 GitHub token 交換回應時 JSON 解碼失敗: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"解析 GitHub token 交換回應失敗: {str(e)}"
        )


    # 2. 用 access token 獲取使用者資訊
    logger.info("準備使用 access_token 獲取 GitHub 用戶資訊。")
    user_url = "https://api.github.com/user"
    auth_headers = {
        "Authorization": f"Bearer {access_token}", # Changed from "token" to "Bearer" for wider compatibility, though "token" also works.
        "Accept": "application/vnd.github.v3+json"
    }
    
    github_username = None
    try:
        async with httpx.AsyncClient() as client:
            logger.info(f"向 {user_url} 發送 GET 請求以獲取用戶資訊。")
            user_response = await client.get(user_url, headers=auth_headers)
            user_response.raise_for_status()
            user_info = user_response.json()
            github_username = user_info.get("login")
            if github_username:
                logger.info(f"成功從 GitHub 獲取用戶名: {github_username}")
            else:
                logger.error(f"未能從 GitHub 獲取用戶名。收到的用戶資訊: {user_info}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="未能從 GitHub 獲取用戶名"
                )
    except httpx.HTTPStatusError as e:
        logger.error(f"獲取 GitHub 用戶資訊失敗: {e.response.status_code} - {e.response.text}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取 GitHub 用戶資訊失敗: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error(f"請求 GitHub 用戶資訊時發生網路錯誤: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"請求 GitHub 用戶資訊時發生錯誤: {str(e)}"
        )
    except json.JSONDecodeError as e:
        logger.error(f"解析 GitHub 用戶資訊回應時 JSON 解碼失敗: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"解析 GitHub 用戶資訊回應失敗: {str(e)}"
        )

    # 3. 將 state, access_token, github_username 寫入 user_github_mappings.json
    logger.info(f"準備將映射資訊寫入 {USER_MAPPINGS_FILE}。State: {state}")
    
    # 確保 data 目錄存在
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        logger.info(f"目錄 {DATA_DIR} 已確認存在或已創建。")
    except OSError as e:
        logger.error(f"創建目錄 {DATA_DIR} 失敗: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"創建數據目錄失敗: {str(e)}"
        )

    mappings = {}
    try:
        logger.info(f"嘗試讀取現有的 {USER_MAPPINGS_FILE}...")
        async with aiofiles.open(USER_MAPPINGS_FILE, mode="r", encoding="utf-8") as f:
            content = await f.read()
            if content:
                mappings = json.loads(content)
                logger.info(f"成功讀取並解析 {USER_MAPPINGS_FILE}。")
            else:
                logger.info(f"{USER_MAPPINGS_FILE} 為空。")
    except FileNotFoundError:
        logger.info(f"{USER_MAPPINGS_FILE} 不存在，將會創建新檔案。")
    except json.JSONDecodeError as e:
        logger.error(f"解析 {USER_MAPPINGS_FILE} 時發生 JSONDecodeError: {str(e)}。檔案內容將被覆蓋。", exc_info=True)
    except Exception as e:
        logger.error(f"讀取 {USER_MAPPINGS_FILE} 時發生未知錯誤: {str(e)}", exc_info=True)

    mappings[state] = {
        "access_token": access_token,
        "github_username": github_username,
        "timestamp": datetime.now().isoformat()
    }

    try:
        logger.info(f"正在將更新後的映射寫入 {USER_MAPPINGS_FILE}...")
        async with aiofiles.open(USER_MAPPINGS_FILE, mode="w", encoding="utf-8") as f:
            await f.write(json.dumps(mappings, indent=4, ensure_ascii=False))
        logger.info(f"成功將映射寫入 {USER_MAPPINGS_FILE}。")
    except IOError as e:
        logger.error(f"寫入 {USER_MAPPINGS_FILE} 失敗: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"寫入 user_github_mappings.json 失敗: {str(e)}"
        )
    except Exception as e:
        logger.error(f"寫入 {USER_MAPPINGS_FILE} 時發生未知錯誤: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"寫入 user_github_mappings.json 時發生未知錯誤: {str(e)}"
        )
        
    logger.info(f"GitHub OAuth 回呼處理完成。State: {state}, GitHub Username: {github_username}")
    return {
        "status": "success",
        "message": "成功處理 GitHub OAuth 回呼並保存映射",
        "github_username": github_username,
        "state_key": state
    }
