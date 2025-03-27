from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from datetime import timedelta, datetime
from typing import List, Dict, Any, Optional
import uuid
import random
import string
import os

from app.models.user import (
    User, UserCreate, UserInDB, Token, UserLogin, OTPRequest, OTPVerification, OTPRecord,
    LoginRecord, Task, Achievement, LeaderboardItem, RewardItem, Inventory, FCMTokenUpdate,
    FriendAction, Station, GoogleLoginRequest, BindRequest, VerifyBindingRequest # Added BindRequest, VerifyBindingRequest
)
from app.utils.auth import authenticate_user, create_access_token, get_current_user, get_password_hash
from app.database.mongodb import (
    volticar_db, users_collection, login_records_collection, otp_records_collection,
    tasks_collection, achievements_collection, rewards_collection
)
# from app.services.otp_service import send_otp, verify_otp # Commented out OTP service import
from app.utils.helpers import handle_mongo_data

router = APIRouter(prefix="/users", tags=["用戶"])

# 訪問令牌的過期時間（以分鐘為單位）
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7天過期

# 創建新用戶 (註冊)
@router.post("/register", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate):
    """
    註冊新用戶
    - email: 用戶電子郵件 (必填，唯一)
    - username: 用戶名稱 (必填，唯一)
    - password: 用戶密碼 (必填)
    - phone: 手機號碼 (可選，唯一)
    - login_type: 登入類型 (預設為 'normal')
    """
    # 檢查郵箱是否已被註冊
    if users_collection.find_one({"email": user.email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此郵箱已被註冊"
        )

    # 檢查用戶名是否已被使用
    if users_collection.find_one({"username": user.username}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此用戶名已被使用"
        )

    # 檢查手機號是否已被註冊 (僅在提供手機號時檢查)
    if user.phone and users_collection.find_one({"phone": user.phone}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此手機號已被註冊"
        )

    # 生成密碼哈希
    hashed_password = get_password_hash(user.password)

    # 生成用戶ID
    user_id = str(uuid.uuid4())

    # 獲取當前時間
    now = datetime.now()

    # 準備用戶數據
    user_dict = {
        "user_id": user_id,
        "email": user.email,
        "username": user.username,
        "password_hash": hashed_password,
        "phone": user.phone, # Phone is now optional
        "login_type": user.login_type,  # 使用模型中的login_type
        "created_at": now,
        "updated_at": now
    }

    # 如果是一般註冊，將google_id設為user_id作為臨時值
    if user.login_type == "normal":
        user_dict["google_id"] = user_id  # 使用user_id作為臨時的google_id
    else:
        # 其他登入類型（如果有）可以處理google_id
        user_dict["google_id"] = None

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
        "user_id": user_id
    }

# 用戶登入
@router.post("/login", response_model=Dict[str, Any])
async def login_user(request: Request, user_login: UserLogin):
    """
    用戶登入
    - username: 用戶名稱 (與email二選一)
    - email: 電子郵件 (與username二選一)
    - password: 密碼 (必填)
    """
    # 準備查詢條件
    query = {}
    if user_login.username:
        query["username"] = user_login.username
    elif user_login.email:
        query["email"] = user_login.email
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請提供用戶名或郵箱"
        )

    # 查詢用戶
    user = users_collection.find_one(query)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用戶不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 驗證密碼 - 注意password_hash字段名更新
    authenticated = authenticate_user(user, user_login.password, password_field="password_hash")

    if not authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="密碼錯誤",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 嘗試獲取真實客戶端IP地址（考慮代理或轉發）
    client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    if not client_ip:
        client_ip = request.headers.get("X-Real-IP", "")
    if not client_ip:
        client_ip = request.client.host

    # 獲取用戶代理和設備信息
    user_agent = request.headers.get("user-agent", "unknown")

    # 取得正確的當前時間
    now = datetime.now()

    # 創建登入記錄
    login_record = {
        "user_id": user["user_id"],
        "login_method": "normal",
        "ip_address": client_ip,
        "device_info": user_agent,
        "created_at": now,
        "login_timestamp": now
    }
    print(f"保存登入記錄: {login_record}")  # 添加日誌輸出以便調試
    login_records_collection.insert_one(login_record)

    # 創建訪問令牌
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["user_id"]},
        expires_delta=access_token_expires
    )

    return {
        "status": "success",
        "msg": "登入成功",
        "user_id": user["user_id"],
        "access_token": access_token,
        "token_type": "bearer"
    }

# --- OTP and Binding Endpoints ---

# Request Binding (Phone or Email)
@router.post("/request-bind", response_model=Dict[str, Any])
async def request_bind(
    bind_request: BindRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    請求綁定手機號碼或電子郵件，發送驗證碼
    - type: 'phone' 或 'email'
    - value: 手機號碼或電子郵件地址
    """
    bind_type = bind_request.type
    bind_value = bind_request.value

    # 檢查綁定類型
    if bind_type not in ["phone", "email"]:
        raise HTTPException(status_code=400, detail="無效的綁定類型")

    # 檢查值是否已被其他用戶綁定
    existing_user = users_collection.find_one({bind_type: bind_value})
    if existing_user and existing_user["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=400, detail=f"此 {bind_type} 已被其他帳號綁定")

    # TODO: Uncomment when OTP service is ready
    # success, message = await send_otp(bind_value)
    # if not success:
    #     raise HTTPException(status_code=500, detail=f"發送驗證碼失敗: {message}")

    print(f"[綁定請求] 類型: {bind_type}, 值: {bind_value}, 用戶ID: {current_user['user_id']}")
    # Placeholder response since OTP is disabled
    return {"status": "success", "msg": "驗證碼請求已收到 (OTP功能暫未啟用)"}

# Verify Binding (Phone or Email)
@router.post("/verify-bind", response_model=Dict[str, Any])
async def verify_binding(
    verify_request: VerifyBindingRequest,
    current_user: Dict = Depends(get_current_user)
):
    """
    驗證綁定手機號碼或電子郵件的驗證碼
    - type: 'phone' 或 'email'
    - value: 手機號碼或電子郵件地址
    - otp_code: 收到的驗證碼
    """
    bind_type = verify_request.type
    bind_value = verify_request.value
    otp_code = verify_request.otp_code

    # 檢查綁定類型
    if bind_type not in ["phone", "email"]:
        raise HTTPException(status_code=400, detail="無效的綁定類型")

    # TODO: Uncomment when OTP service is ready
    # verified, message = await verify_otp(bind_value, otp_code)
    # if not verified:
    #     raise HTTPException(status_code=400, detail=f"驗證碼錯誤或已過期: {message}")

    # Placeholder verification logic
    print(f"[驗證綁定] 類型: {bind_type}, 值: {bind_value}, 驗證碼: {otp_code}, 用戶ID: {current_user['user_id']}")
    if otp_code != "123456": # Placeholder check
         raise HTTPException(status_code=400, detail="驗證碼錯誤 (測試模式)")

    # TODO: Uncomment when OTP service is ready
    # # Update user document in the database
    # update_result = users_collection.update_one(
    #     {"user_id": current_user["user_id"]},
    #     {"$set": {bind_type: bind_value, "updated_at": datetime.now()}}
    # )
    # if update_result.modified_count == 0:
    #      # Handle case where user might not exist or update failed
    #      pass # Or raise an error

    return {"status": "success", "msg": f"{bind_type} 綁定成功 (測試模式)"}


# --- Existing OTP Endpoints (Commented out for now) ---

# # 發送OTP驗證碼
# @router.post("/send-otp", response_model=Dict[str, Any])
# async def send_otp_endpoint(request: OTPRequest): # Renamed to avoid conflict
#     """
#     發送OTP驗證碼
#     - phone: 手機號碼 (必填，台灣格式09開頭)
#     """
#     print(f"收到發送OTP請求，手機號碼：{request.phone}")

#     # 檢查手機號碼格式是否正確（台灣手機號碼格式）
#     if not request.phone or not (request.phone.startswith('09') and len(request.phone) == 10):
#         print(f"手機號碼格式不正確：{request.phone}")
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="手機號碼格式不正確，應為台灣手機號碼格式（09開頭，共10位數）"
#         )

#     # 查詢該手機號對應的用戶
#     user = users_collection.find_one({"phone": request.phone})
#     user_id = user["user_id"] if user else f"unregistered_{request.phone}"

#     # 生成6位數驗證碼
#     otp_code = ''.join(random.choices(string.digits, k=6))
#     print(f"生成的OTP驗證碼：{otp_code} 將發送給 {request.phone}")

#     # 獲取當前時間
#     now = datetime.now()

#     # 存儲OTP驗證碼
#     otp_data = {
#         "user_id": user_id,
#         "otp_code": otp_code,
#         "created_at": now,
#         "expires_at": now + timedelta(minutes=10)  # 驗證碼10分鐘後過期
#     }

#     # 刪除舊的OTP驗證碼
#     delete_result = otp_records_collection.delete_many({"user_id": user_id})
#     print(f"刪除舊OTP驗證碼：{delete_result.deleted_count} 條記錄")

#     # 插入新的OTP驗證碼
#     otp_records_collection.insert_one(otp_data)
#     print(f"新的OTP驗證碼記錄已插入數據庫")

#     # FCM推播實現
#     # 如果在生產環境且找到用戶的FCM令牌，使用FCM發送驗證碼
#     if os.getenv("API_ENV") == "production" and user and "fcm_token" in user and user["fcm_token"]:
#         try:
#             # 使用FCM發送驗證碼
#             from app.services.firebase_service import send_verification_code_notification
#             fcm_result = await send_verification_code_notification(
#                 user["fcm_token"],
#                 otp_code,
#                 10  # 驗證碼有效期10分鐘
#             )

#             if fcm_result["success"]:
#                 print(f"驗證碼通過FCM成功發送到設備，消息ID: {fcm_result['message_id']}")
#                 return {
#                     "status": "success",
#                     "msg": "驗證碼已通過應用推播發送",
#                     "sent_via": "fcm"
#                 }
#             else:
#                 print(f"FCM發送失敗: {fcm_result.get('error')}")
#                 # FCM發送失敗，回退到測試模式
#         except Exception as e:
#             print(f"FCM發送異常: {str(e)}")
#             # 發生異常，回退到測試模式

#     # 測試環境或FCM發送失敗時，直接返回驗證碼
#     print(f"[測試環境] OTP驗證碼 {otp_code} 已生成，但未通過推播發送")
#     return {
#         "status": "success",
#         "msg": "驗證碼已生成",
#         "otp_code": otp_code,  # 測試環境返回驗證碼
#         "test_mode": True,
#         "sent_via": "api_response"
#     }

# # 驗證OTP
# @router.post("/verify-otp", response_model=Dict[str, Any])
# async def verify_otp_endpoint(verification: OTPVerification): # Renamed to avoid conflict
#     """
#     驗證OTP驗證碼
#     - phone: 手機號碼 (必填，台灣格式09開頭)
#     - otp_code: OTP驗證碼 (必填，6位數字)
#     """
#     print(f"收到OTP驗證請求，手機號碼：{verification.phone}，驗證碼：{verification.otp_code}")

#     # 檢查手機號碼格式是否正確
#     if not verification.phone or not (verification.phone.startswith('09') and len(verification.phone) == 10):
#         print(f"手機號碼格式不正確：{verification.phone}")
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="手機號碼格式不正確，應為台灣手機號碼格式（09開頭，共10位數）"
#         )

#     # 查詢該手機號對應的用戶
#     user = users_collection.find_one({"phone": verification.phone})
#     user_id = user["user_id"] if user else f"unregistered_{verification.phone}"

#     # 查詢最新的OTP記錄
#     otp_record = otp_records_collection.find_one(
#         {"user_id": user_id},
#         sort=[("created_at", -1)]
#     )

#     if not otp_record:
#         print(f"找不到用戶ID {user_id} 的OTP驗證碼記錄")
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="找不到驗證碼記錄，請重新發送驗證碼"
#         )

#     # 檢查驗證碼是否過期
#     if otp_record["expires_at"] < datetime.now():
#         print(f"OTP驗證碼已過期，過期時間: {otp_record['expires_at']}")
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="驗證碼已過期，請重新獲取"
#         )

#     # 檢查驗證碼是否正確
#     if otp_record["otp_code"] != verification.otp_code:
#         print(f"OTP驗證碼不匹配: 輸入 {verification.otp_code}, 預期 {otp_record['otp_code']}")
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="驗證碼不正確"
#         )

#     # 驗證成功，刪除OTP記錄
#     otp_records_collection.delete_one({"_id": otp_record["_id"]})
#     print(f"OTP驗證成功，已刪除驗證碼記錄 ID: {otp_record['_id']}")

#     return {
#         "status": "success",
#         "msg": "驗證碼驗證成功",
#         "verified": True,
#         "user_id": user["user_id"] if user else None
#     }

# --- Other Endpoints ---

# 獲取用戶資料
@router.get("/profile", response_model=Dict[str, Any])
async def get_user_profile(current_user: Dict = Depends(get_current_user)):
    """
    獲取當前登入用戶的個人資料
    - 需要授權令牌
    """
    user_info = {
        "username": current_user.get("username", ""),
        "user_id": current_user.get("user_id", ""),
        "email": current_user.get("email", ""),
        "phone": current_user.get("phone", "") # Phone might be None now
    }

    return {
        "status": "success",
        "msg": "獲取用戶資訊成功",
        "user_info": user_info
    }

# 測試OTP功能
@router.get("/test-otp/{phone}", response_model=Dict[str, Any])
async def test_otp(phone: str):
    """
    測試OTP功能 (僅開發環境使用)
    - phone: 手機號碼 (必填，台灣格式09開頭)
    """
    print(f"測試OTP功能，手機號碼：{phone}")

    # 檢查手機號碼格式
    if not phone or not (phone.startswith('09') and len(phone) == 10):
        return {
            "status": "error",
            "msg": "手機號碼格式不正確，應為台灣手機號碼格式（09開頭，共10位數）"
        }

    # 查詢該手機號對應的用戶
    user = users_collection.find_one({"phone": phone})
    user_id = user["user_id"] if user else f"unregistered_{phone}"

    # 查詢該用戶的最新OTP驗證碼
    otp_record = otp_records_collection.find_one(
        {"user_id": user_id},
        sort=[("created_at", -1)]
    )

    if not otp_record:
        return {
            "status": "error",
            "msg": "未找到OTP驗證碼記錄，請先發送驗證碼"
        }

    # 檢查驗證碼是否過期
    if otp_record["expires_at"] < datetime.now():
        return {
            "status": "error",
            "msg": "OTP驗證碼已過期",
            "expires_at": otp_record["expires_at"],
            "current_time": datetime.now()
        }

    return {
        "status": "success",
        "msg": "找到有效的OTP驗證碼",
        "phone": phone,
        "otp_code": otp_record["otp_code"],
        "created_at": otp_record["created_at"],
        "expires_at": otp_record["expires_at"],
        "current_time": datetime.now(),
        "is_expired": otp_record["expires_at"] < datetime.now(),
        "remaining_time": (otp_record["expires_at"] - datetime.now()).total_seconds() // 60
    }

# FCM令牌更新
@router.post("/update-fcm-token", response_model=Dict[str, Any])
async def update_fcm_token(token_update: FCMTokenUpdate):
    """
    更新FCM令牌 - 用於推播通知
    - user_id: 用戶ID (必填)
    - fcm_token: FCM令牌 (必填)
    - device_info: 設備信息 (選填)
    """
    print(f"更新FCM令牌，使用者ID: {token_update.user_id}")

    # 更新使用者FCM令牌
    result = users_collection.update_one(
        {"user_id": token_update.user_id},
        {"$set": {
            "fcm_token": token_update.fcm_token,
            "device_info": token_update.device_info,
            "token_updated_at": datetime.now()
        }}
    )

    if result.modified_count == 0:
        if not users_collection.find_one({"user_id": token_update.user_id}):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="使用者不存在"
            )

    return {
        "status": "success",
        "msg": "FCM令牌已更新"
    }

# 檢查手機號碼是否存在
@router.get("/check-phone/{phone}", response_model=Dict[str, Any])
async def check_phone_exists(phone: str):
    """
    檢查手機號碼是否已被註冊
    - phone: 手機號碼 (必填，台灣格式09開頭)
    """
    print(f"檢查手機號碼是否存在：{phone}")

    # 檢查手機號碼格式
    if not phone or not (phone.startswith('09') and len(phone) == 10):
        return {
            "status": "error",
            "msg": "手機號碼格式不正確，應為台灣手機號碼格式（09開頭，共10位數）",
            "exists": False
        }

    # 檢查手機號碼是否已註冊
    user_exists = users_collection.find_one({"phone": phone}) is not None
    print(f"手機號碼 {phone} 是否已存在: {user_exists}")

    return {
        "status": "success",
        "msg": "檢查完成",
        "exists": user_exists
    }

# 查詢登入記錄（測試用）
@router.get("/login-records", response_model=Dict[str, Any])
async def get_login_records(user_id: Optional[str] = None, limit: int = 10):
    """
    查詢登入記錄（僅用於測試）
    - user_id: 可選，指定用戶ID
    - limit: 限制返回記錄數量，默認10條
    """
    query = {}
    if user_id:
        query["user_id"] = user_id

    records = []
    cursor = login_records_collection.find(query).sort("login_timestamp", -1).limit(limit)

    for record in cursor:
        # 轉換ObjectId為字符串
        record["_id"] = str(record["_id"])

        # 簡單格式化時間戳為本地時間字符串
        if "login_timestamp" in record:
            record["login_timestamp_local"] = record["login_timestamp"].strftime("%Y-%m-%d %H:%M:%S")
            record["login_timestamp"] = record["login_timestamp"].isoformat()

        if "created_at" in record:
            record["created_at_local"] = record["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            record["created_at"] = record["created_at"].isoformat()

        records.append(record)

    return {
        "status": "success",
        "count": len(records),
        "system_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "records": records
    }

# 獲取排行榜
@router.get("/leaderboard", response_model=Dict[str, Any])
async def get_leaderboard(time_range: str = "week"):
    """
    獲取用戶積分排行榜
    - time_range: 時間範圍，可選值為 "day"、"week"、"month"
    """
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
    leaderboard = list(users_collection.find(
        {"last_login": {"$gte": start_time}},
        {"user_id": 1, "username": 1, "carbon_credits": 1}
    ).sort("carbon_credits", -1).limit(10))

    # 格式化結果
    result = []
    for i, user in enumerate(leaderboard):
        result.append({
            "rank": i + 1,
            "user_id": user.get("user_id", ""),
            "username": user.get("username", "Unknown"),
            "score": user.get("carbon_credits", 0)
        })

    return {
        "status": "success",
        "msg": "獲取排行榜成功",
        "leaderboard": result
    }

# 添加/刪除好友
@router.post("/friends", response_model=Dict[str, Any])
async def manage_friends(friend_action: FriendAction):
    """
    管理好友關係
    - user_id: 用戶ID
    - friend_id: 好友ID
    - action: 操作類型，可選值為 "add" 或 "remove"
    """
    # 檢查用戶是否存在
    user = users_collection.find_one({"user_id": friend_action.user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )

    # 檢查好友是否存在
    friend = users_collection.find_one({"user_id": friend_action.friend_id})
    if not friend:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="好友不存在"
        )

    # 處理添加好友
    if friend_action.action == "add":
        # 檢查是否已經是好友
        if "friends" in user and friend_action.friend_id in user["friends"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="已經是好友"
            )

        # 添加好友關係（雙向）
        users_collection.update_one(
            {"user_id": friend_action.user_id},
            {"$addToSet": {"friends": friend_action.friend_id}}
        )

        users_collection.update_one(
            {"user_id": friend_action.friend_id},
            {"$addToSet": {"friends": friend_action.user_id}}
        )

        return {
            "status": "success",
            "msg": "添加好友成功"
        }

    # 處理刪除好友
    elif friend_action.action == "remove":
        # 檢查是否真的是好友
        if "friends" not in user or friend_action.friend_id not in user["friends"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="不是好友"
            )

        # 移除好友關係（雙向）
        users_collection.update_one(
            {"user_id": friend_action.user_id},
            {"$pull": {"friends": friend_action.friend_id}}
        )

        users_collection.update_one(
            {"user_id": friend_action.friend_id},
            {"$pull": {"friends": friend_action.user_id}}
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

# 獲取任務列表
@router.get("/tasks", response_model=Dict[str, Any])
async def get_user_tasks(user_id: str):
    """
    獲取用戶任務列表
    - user_id: 用戶ID
    """
    # 查詢用戶的任務
    user = users_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用戶不存在"
        )

    # 獲取可用任務
    all_tasks = list(tasks_collection.find({}))
    user_tasks = []

    for task in all_tasks:
        # 計算任務完成進度
        progress = 0
        if "user_tasks" in user and str(task["_id"]) in user["user_tasks"]:
            progress = user["user_tasks"][str(task["_id"])]["progress"]

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

# 獲取用戶成就
@router.get("/achievements", response_model=Dict[str, Any])
async def get_user_achievements(user_id: str):
    """
    獲取用戶成就列表
    - user_id: 用戶ID
    """
    # 查詢用戶
    user = users_collection.find_one({"user_id": user_id})
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

# 兌換獎勵
@router.post("/redeem-reward", response_model=Dict[str, Any])
async def redeem_reward(user_id: str = Body(...), points: int = Body(...), reward_id: str = Body(...)):
    """
    兌換積分獎勵
    - user_id: 用戶ID
    - points: 兌換所需積分
    - reward_id: 獎勵ID
    """
    # 查詢用戶
    user = users_collection.find_one({"user_id": user_id})
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
        {"user_id": user_id},
        {"$inc": {"carbon_credits": -points}}
    )

    # 添加獎勵到用戶物品庫
    users_collection.update_one(
        {"user_id": user_id},
        {"$push": {"inventory": reward_id}}
    )

    return {
        "status": "success",
        "msg": "兌換獎勵成功",
        "reward_item": reward.get("name", "")
    }

# 獲取用戶物品庫
@router.get("/inventory", response_model=Dict[str, Any])
async def get_user_inventory(user_id: str):
    """
    獲取用戶物品庫
    - user_id: 用戶ID
    """
    # 查詢用戶
    user = users_collection.find_one({"user_id": user_id})
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

# 獲取充電站信息
@router.get("/charging-stations", response_model=Dict[str, Any])
async def get_charging_stations(user_id: str, location: str):
    """
    獲取附近的充電站信息
    - user_id: 用戶ID
    - location: 位置格式為 "緯度,經度"
    """
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

# 處理Gmail登入
@router.post("/login/google", summary="使用Google帳號登入")
async def login_with_google(google_data: GoogleLoginRequest):
    """
    使用Google帳號登入，成功返回JWT令牌
    """
    try:
        # 驗證Google ID令牌（簡化版示例，實際應用中應該調用Google API驗證令牌）
        # TODO: 實現完整的Google令牌驗證

        # 檢查此Google ID是否有效
        google_id = google_data.google_id
        existing_user = None

        # 必須確保google_id有效
        if not google_id or not google_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="無效的Google ID"
            )

        # 使用google_id查找用戶 (明確指定login_type為google)
        existing_user = users_collection.find_one({
            "google_id": google_id,
            "login_type": "google"
        })

        if existing_user:
            # 已存在的Google用戶，更新登入時間
            users_collection.update_one(
                {"_id": existing_user["_id"]},
                {"$set": {"last_login": datetime.now()}}
            )

            # 創建訪問令牌
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": existing_user["user_id"]},
                expires_delta=access_token_expires
            )

            return {
                "status": "success",
                "msg": "Google登入成功",
                "user_id": existing_user["user_id"],
                "access_token": access_token,
                "token_type": "bearer"
            }
        else:
            # 新Google用戶，檢查電子郵件是否已被使用
            email = google_data.email
            if not email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="缺少電子郵件資訊"
                )

            email_user = users_collection.find_one({"email": email})

            if email_user:
                # 用戶電子郵件已存在
                if email_user.get("login_type") == "google":
                    # 已經是Google用戶，但google_id不匹配，更新google_id
                    users_collection.update_one(
                        {"_id": email_user["_id"]},
                        {"$set": {
                            "google_id": google_id,
                            "last_login": datetime.now()
                        }}
                    )
                elif email_user.get("login_type") == "normal":
                    # 是一般註冊用戶，不提供自動綁定功能，避免安全問題
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="此郵箱已使用其他登入方式註冊，請使用原登入方式或聯繫客服綁定帳號"
                    )

                # 創建訪問令牌
                access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
                access_token = create_access_token(
                    data={"sub": email_user["user_id"]},
                    expires_delta=access_token_expires
                )

                return {
                    "status": "success",
                    "msg": "Google登入成功",
                    "user_id": email_user["user_id"],
                    "access_token": access_token,
                    "token_type": "bearer"
                }
            else:
                # 完全新用戶，創建新帳號
                user_id = str(uuid.uuid4())
                username = google_data.name or f"user_{uuid.uuid4().hex[:8]}"

                # 確保用戶名不重複
                if users_collection.find_one({"username": username}):
                    username = f"user_{uuid.uuid4().hex[:8]}"

                new_user = {
                    "user_id": user_id,
                    "email": email,
                    "username": username,
                    "google_id": google_id,
                    "login_type": "google",  # 明確設置為Google登入
                    "created_at": datetime.now(),
                    "updated_at": datetime.now(),
                    "last_login": datetime.now(),
                    "password_hash": None,  # Google用戶沒有密碼
                    "is_active": True,
                    "carbon_points": 0
                }

                # 插入新用戶
                result = users_collection.insert_one(new_user)

                if not result.inserted_id:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="創建用戶失敗"
                    )

                # 創建訪問令牌
                access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
                access_token = create_access_token(
                    data={"sub": user_id},
                    expires_delta=access_token_expires
                )

                return {
                    "status": "success",
                    "msg": "Google登入成功，已創建新帳號",
                    "user_id": user_id,
                    "access_token": access_token,
                    "token_type": "bearer"
                }

    except HTTPException:
        # 重新拋出HTTP異常
        raise
    except Exception as e:
        print(f"Google登入失敗: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google登入失敗: {str(e)}"
        )
