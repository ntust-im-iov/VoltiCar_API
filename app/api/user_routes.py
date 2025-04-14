from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from fastapi.responses import HTMLResponse # Import HTMLResponse
from datetime import timedelta, datetime
from typing import Dict, Any, Optional
import uuid
import os
import sys # Import sys module
import secrets
from pydantic import EmailStr, BaseModel
from fastapi import Query # Import Query for the new endpoint

from app.models.user import (
    User, UserCreate, UserLogin, # LoginRecord is imported but not used as type hint/response model
    FCMTokenUpdate, FriendAction, GoogleLoginRequest, BindRequest, VerifyBindingRequest
) # Removed LoginRecord model import
from app.utils.auth import authenticate_user, create_access_token, get_current_user, get_password_hash
# Import the email service from the app/services directory
from app.services.email_service import ( # Updated import path
    send_email_async,
    create_verification_email_content,
    create_password_reset_email_content
)
from app.database.mongodb import (
    volticar_db, users_collection, login_records_collection,
    tasks_collection, achievements_collection, rewards_collection, # Added missing collections back
    pending_verifications_collection # 新增：待驗證集合
)
from app.models.user import EmailVerificationRequest, CompleteRegistrationRequest # 引入新的 Pydantic 模型

router = APIRouter(prefix="/users", tags=["用戶"])

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days

# --- 舊的 /register 路由已移除 ---

# --- 新增：請求 Email 驗證 ---
@router.post("/request-verification", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def request_email_verification(request_data: EmailVerificationRequest):
    """
    請求發送 Email 驗證信
    - email: 要驗證的電子郵件地址
    """
    # --- 新增：檢查資料庫集合是否可用 ---
    if users_collection is None or pending_verifications_collection is None:
        print("錯誤：request_email_verification - 資料庫集合未初始化。")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="資料庫服務暫時無法使用，請稍後再試"
        )
    # --- 檢查結束 ---

    email = request_data.email
    now = datetime.now()

    # 1. 檢查 Email 是否已在正式用戶中註冊
    if users_collection.find_one({"email": email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此電子郵件已被註冊"
        )

    # 2. 檢查是否已有待驗證記錄 (避免重複發送太頻繁)
    pending_record = pending_verifications_collection.find_one({"email": email})
    if pending_record and not pending_record.get("is_verified", False):
        # 檢查上次請求時間，例如 5 分鐘內不重發
        last_requested = pending_record.get("requested_at")
        if last_requested and (now - last_requested) < timedelta(minutes=5):
             print(f"Email {email} 請求過於頻繁，提示用戶檢查信箱。")
             raise HTTPException(
                 status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                 detail="請求過於頻繁，請檢查您的收件匣或稍後再試。"
             )
        # 如果超過時間，則允許更新 token 並重發
        print(f"Email {email} 已有待驗證記錄，但已超過時間限制，更新 token 並準備重發。")
        verification_token = secrets.token_urlsafe(32)
        verification_token_expires_at = now + timedelta(hours=1) # 驗證有效期 1 小時
        pending_verifications_collection.update_one(
            {"email": email},
            {"$set": {
                "token": verification_token,
                "expires_at": verification_token_expires_at,
                "is_verified": False, # 確保是未驗證
                "requested_at": now # 更新請求時間
            }}
        )
    else:
        # 3. 產生新的驗證 token 和到期時間
        verification_token = secrets.token_urlsafe(32)
        verification_token_expires_at = now + timedelta(hours=1) # 驗證有效期 1 小時

        # 4. 儲存到 pending_verifications 集合
        pending_verifications_collection.update_one(
            {"email": email},
            {"$set": {
                "token": verification_token,
                "expires_at": verification_token_expires_at,
                "is_verified": False,
                "requested_at": now
            }},
            upsert=True # 如果記錄不存在則創建
        )
        print(f"已為 Email {email} 產生待驗證記錄。")

    # 5. 發送驗證郵件 (無論是新請求還是重發)
    api_base_url = os.getenv("API_BASE_URL", "https://volticar.dynns.com:22000") # 使用環境變數或預設值
    if api_base_url == "https://volticar.dynns.com:22000":
         print(f"警告：未設定 API_BASE_URL 環境變數，使用預設值: {api_base_url}")

    verification_link = f"{api_base_url}/users/verify-email?token={verification_token}"
    html_content = create_verification_email_content(email, verification_link) # 傳入 email

    email_sent = await send_email_async(email, "Volticar 帳號驗證", html_content)
    if not email_sent:
        print(f"錯誤：為 Email {email} 發送驗證郵件失敗。")
        # 即使發送失敗，也可能不告訴前端錯誤，避免洩露 Email 是否存在
        # 但後端需要記錄錯誤
        # 為了方便調試，暫時返回錯誤
        raise HTTPException(status_code=500, detail="發送驗證郵件失敗，請稍後再試")

    print(f"已向 Email {email} 發送驗證郵件。")
    return {"status": "success", "msg": "驗證郵件已發送，請檢查您的收件匣。"}

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

    # --- 新增檢查：如果用戶是透過 Google 註冊的，阻止密碼登入 ---
    if user.get("login_type") == "google":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "GOOGLE_AUTH_REQUIRED",
                "msg": "此帳號是透過 Google 註冊，請使用 Google 登入"
            }
        )
    # --- 檢查結束 ---

    # 只有非 Google 註冊用戶才進行密碼驗證
    authenticated = authenticate_user(user, user_login.password, password_field="password_hash")

    if not authenticated:
        # 確保密碼錯誤的提示仍然存在
        if user.get("password_hash") is None: # 處理可能沒有密碼的情況 (雖然理論上 normal 用戶應該有)
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="登入失敗，請檢查您的登入方式",
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
             raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="密碼錯誤",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # --- 移除 Email 驗證檢查 ---
    # (因為只有驗證過的 Email 才能完成註冊)

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
    print(f"保存登入記錄: {login_record}")
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

    # OTP sending logic removed as service is disabled
    print(f"[綁定請求] 類型: {bind_type}, 值: {bind_value}, 用戶ID: {current_user['user_id']}")
    return {"status": "success", "msg": "綁定請求已收到 (OTP功能暫未啟用，請使用測試驗證碼)"}

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

    # OTP verification logic removed as service is disabled
    # Placeholder verification logic using a fixed code
    print(f"[驗證綁定] 類型: {bind_type}, 值: {bind_value}, 驗證碼: {otp_code}, 用戶ID: {current_user['user_id']}")
    if otp_code != "123456": # Placeholder check for testing
         raise HTTPException(status_code=400, detail="驗證碼錯誤 (測試模式，請使用 123456)")

    # Database update logic removed as OTP is disabled
    # In a real scenario, update would happen here after successful verification
    print(f"驗證成功 (測試模式)，用戶 {current_user['user_id']} 的 {bind_type} ({bind_value}) 未實際更新資料庫。")

    return {"status": "success", "msg": f"{bind_type} 驗證成功 (測試模式)"}


# --- 修改：Email 驗證端點 (使用 pending_verifications) ---
@router.get("/verify-email", response_class=HTMLResponse, summary="驗證電子郵件地址 (返回 HTML)")
async def verify_email_html(token: str = Query(...)):
    """
    使用從郵件收到的權杖驗證用戶的電子郵件地址，直接返回 HTML 結果頁面。
    - token: 驗證權杖
    """
    now = datetime.now()
    success_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Email 驗證成功</title></head>
    <body><h1>驗證成功！</h1><p>您的電子郵件地址已成功驗證。請返回 APP 完成註冊。</p></body>
    </html>
    """
    already_verified_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Email 已驗證</title></head>
    <body><h1>操作完成</h1><p>您的電子郵件地址先前已經驗證過了。請返回 APP 完成註冊。</p></body>
    </html>
    """
    error_html = """
    <!DOCTYPE html>
    <html>
    <head><title>Email 驗證失敗</title></head>
    <body><h1>驗證失敗</h1><p>驗證連結無效或已過期。請返回 APP 重新請求驗證。</p></body>
    </html>
    """
    print(f"收到驗證請求，Token: {token}")

    # 在 pending_verifications 集合中尋找 token 且未過期
    pending_record = pending_verifications_collection.find_one({
        "token": token,
        "expires_at": {"$gt": now}
    })
    print(f"待驗證資料庫查詢結果 (Record found): {pending_record is not None}")

    if not pending_record:
        # 無效或過期權杖
        # 檢查是否是因為已經驗證過 (token 被清除了)
        # 注意：這裡無法直接判斷是過期還是已驗證，因為 token 已清除
        # 更好的做法是在 update 時檢查 modified_count
        print(f"驗證失敗：在 pending_verifications 中找不到對應 Token 或 Token 已過期 (Token: {token})")
        return HTMLResponse(content=error_html, status_code=400)

    # 檢查是否已經被標記為已驗證 (雖然理論上 token 應該被清除了)
    if pending_record.get("is_verified", False):
         print(f"Token {token} 對應的 Email {pending_record.get('email')} 已被標記為驗證。")
         return HTMLResponse(content=already_verified_html, status_code=200)

    # 更新 pending 記錄狀態為已驗證，並清除權杖
    update_result = pending_verifications_collection.update_one(
        {"_id": pending_record["_id"], "token": token}, # 加上 token 確保原子性
        {"$set": {
            "is_verified": True,
            "verified_at": now,
            "token": None, # 清除 token
            "expires_at": None # 清除過期時間
        }}
    )

    if update_result.modified_count == 0:
        # 可能在查詢和更新之間，記錄被修改或 token 已被使用
        print(f"錯誤：嘗試更新 Email {pending_record.get('email')} 的驗證狀態失敗 (可能已被驗證或 token 失效)。")
        # 再次檢查是否已經是 verified
        current_record = pending_verifications_collection.find_one({"_id": pending_record["_id"]})
        if current_record and current_record.get("is_verified"):
             print(f"確認 Email {pending_record.get('email')} 確實已被驗證。")
             return HTMLResponse(content=already_verified_html, status_code=200)
        else:
             print(f"確認 Email {pending_record.get('email')} 未被驗證，返回錯誤。")
             return HTMLResponse(content=error_html, status_code=400) # 返回通用錯誤

    print(f"Email {pending_record.get('email')} 已成功標記為驗證。")
    # 驗證成功
    return HTMLResponse(content=success_html, status_code=200)


# --- Password Reset Endpoints ---

class ForgotPasswordRequest(BaseModel):
    """忘記密碼請求模型"""
    identifier: str # 可以是 email 或 phone

class ResetPasswordRequest(BaseModel):
    """重設密碼請求模型"""
    token: str
    new_password: str

@router.post("/forgot-password", response_model=Dict[str, Any])
async def forgot_password(request_data: ForgotPasswordRequest):
    """
    請求重設密碼
    - identifier: 用戶的電子郵件或手機號碼
    """
    identifier = request_data.identifier
    now = datetime.now()
    expires_delta = timedelta(hours=1) # 權杖有效期 1 小時
    expires_at = now + expires_delta

    # 嘗試透過 email 或 phone 尋找用戶
    user = users_collection.find_one({"$or": [{"email": identifier}, {"phone": identifier}]})

    if not user:
        # 即使找不到用戶，也返回成功訊息以避免洩露用戶資訊
        print(f"請求重設密碼，但找不到用戶: {identifier}")
        return {"status": "success", "msg": "如果您的帳戶存在，重設密碼的指示已發送。"}

    # 生成安全的重設權杖
    reset_token = secrets.token_urlsafe(32)

    # 更新用戶資料庫，儲存權杖和到期時間
    update_result = users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "reset_password_token": reset_token,
            "reset_password_token_expires_at": expires_at,
            "updated_at": now
        }}
    )

    if update_result.modified_count == 0:
         raise HTTPException(status_code=500, detail="無法更新用戶重設密碼權杖")

    # 根據 identifier 類型決定發送方式
    email_sent_status = False
    if "@" in identifier and identifier == user.get("email"): # 確保是 email
        # *** 重要：讀取後端 API 的基礎 URL 來建立重設連結 ***
        # 建議在環境變數中設定 API_BASE_URL=https://yourdomain:port
        api_base_url = os.getenv("API_BASE_URL")
        if not api_base_url:
            api_base_url = "https://volticar.dynns.com:22000" # *** 請務必在生產環境中設定 API_BASE_URL ***
            print(f"警告：未設定 API_BASE_URL 環境變數，使用預設值: {api_base_url}")

        # 注意：密碼重設通常還是需要前端頁面來輸入新密碼。
        # 如果您也想簡化這個流程，可能需要一個能接收 token 和新密碼的後端端點，
        # 但這會降低安全性，因為連結本身不能直接包含新密碼。
        # 目前維持指向前端路徑，假設前端會有 /reset-password 頁面。
        # 如果您沒有前端，這個流程需要重新設計。
        # 暫時保留前端連結，但提醒您這個依賴。
        reset_link = f"{api_base_url}/reset-password?token={reset_token}" # 假設前端處理此路徑
        html_content = create_password_reset_email_content(user.get("username", "用戶"), reset_link)

        # 發送密碼重設郵件
        email_sent_status = await send_email_async(user["email"], "Volticar 密碼重設請求", html_content)

        if email_sent_status:
            print(f"已向郵箱 {user['email']} 發送密碼重設郵件。")
            # 即使郵件發送成功，也返回通用成功訊息
            return {"status": "success", "msg": "如果您的帳戶存在，重設密碼的指示已發送到您的電子郵件。"}
        else:
            print(f"錯誤：為郵箱 {user['email']} 生成了重設權杖，但郵件發送失敗。")
            # 即使郵件發送失敗，也返回通用成功訊息，避免洩露資訊
            # 但後台應記錄此錯誤
            return {"status": "success", "msg": "處理您的請求時發生錯誤，請稍後再試或聯繫客服。"}

    elif identifier == user.get("phone"): # 確保是 phone
        # 手機號碼處理 (目前僅記錄，待實現 SMS 服務)
        print(f"收到手機號碼 {identifier} 的重設密碼請求，權杖: {reset_token} (SMS 功能待實現)")
        # 在實際應用中，這裡應該觸發 SMS 發送
        return {"status": "success", "msg": "如果您的帳戶存在且綁定了此手機號，重設密碼的指示將發送給您 (目前 SMS 功能待實現)。"}
    else:
        # Identifier 不匹配用戶記錄中的 email 或 phone
         print(f"請求的 identifier {identifier} 與找到的用戶 {user['user_id']} 不匹配")
         # 仍然返回通用成功訊息
         return {"status": "success", "msg": "如果您的帳戶存在，重設密碼的指示將很快發送。"}


@router.post("/reset-password", response_model=Dict[str, Any])
async def reset_password(request_data: ResetPasswordRequest):
    """
    使用權杖重設密碼
    - token: 從郵件或簡訊收到的重設權杖
    - new_password: 新密碼
    """
    token = request_data.token
    new_password = request_data.new_password
    now = datetime.now()

    # 尋找使用此權杖且權杖未過期的用戶
    user = users_collection.find_one({
        "reset_password_token": token,
        "reset_password_token_expires_at": {"$gt": now}
    })

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="無效或已過期的重設密碼權杖"
        )

    # 驗證新密碼強度 (可選，但建議)
    if len(new_password) < 8:
         raise HTTPException(status_code=400, detail="新密碼長度至少需要8位")

    # 更新密碼
    hashed_password = get_password_hash(new_password)
    update_result = users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "password_hash": hashed_password,
            "updated_at": now,
            "reset_password_token": None, # 清除權杖
            "reset_password_token_expires_at": None # 清除到期時間
        }}
    )

    if update_result.modified_count == 0:
        raise HTTPException(status_code=500, detail="重設密碼失敗")

    print(f"用戶 {user['user_id']} 已成功重設密碼")
    return {"status": "success", "msg": "密碼已成功重設"}


# --- 新增：完成註冊 ---
@router.post("/complete-registration", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def complete_registration(registration_data: CompleteRegistrationRequest):
    """
    在 Email 驗證後，完成使用者註冊
    - email: 已驗證的電子郵件
    - username: 用戶名稱
    - password: 密碼
    - phone: 手機號碼 (可選)
    """
    email = registration_data.email
    username = registration_data.username
    password = registration_data.password
    phone = registration_data.phone
    now = datetime.now()

    # 1. 檢查 Email 是否在 pending 且已驗證
    pending_record = pending_verifications_collection.find_one({
        "email": email,
        "is_verified": True
    })
    if not pending_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="電子郵件尚未驗證或驗證記錄不存在"
        )

    # 2. 再次檢查 Email 是否已被正式註冊 (以防萬一)
    if users_collection.find_one({"email": email}):
        # 理論上不應該發生，因為 request-verification 會檢查
        # 但如果發生，可能需要清理 pending 記錄
        pending_verifications_collection.delete_one({"email": email})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此電子郵件已被註冊"
        )

    # 3. 檢查用戶名是否已被使用
    if users_collection.find_one({"username": username}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此用戶名已被使用"
        )

    # 4. 檢查手機號是否已被註冊 (僅在提供手機號時檢查)
    if phone and users_collection.find_one({"phone": phone}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此手機號已被註冊"
        )

    # 5. 產生密碼哈希
    hashed_password = get_password_hash(password)

    # 6. 產生用戶ID
    user_id = str(uuid.uuid4())

    # 7. 準備正式用戶數據
    user_dict = {
        "user_id": user_id,
        "email": email,
        "username": username,
        "password_hash": hashed_password,
        "phone": phone if phone else None,
        "login_type": "normal", # 驗證後註冊視為 normal
        "created_at": now,
        "updated_at": now,
        "is_email_verified": True, # 直接設為 True
        # 不再需要 email_verification_token 相關欄位
        "google_id": None
    }

    # 8. 插入到正式用戶數據庫
    result = users_collection.insert_one(user_dict)
    if not result.inserted_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="創建用戶失敗"
        )

    # 9. 從 pending_verifications 刪除記錄
    delete_result = pending_verifications_collection.delete_one({"email": email})
    if delete_result.deleted_count == 0:
        # 記錄一個警告，但不影響註冊成功
        print(f"警告：用戶 {user_id} ({email}) 註冊成功，但未能從 pending_verifications 刪除記錄。")

    print(f"用戶 {user_id} ({email}) 已成功完成註冊。")

    # 可以選擇返回 user_id 或直接產生 token 讓用戶登入
    # 產生 token:
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_id},
        expires_delta=access_token_expires
    )

    return {
        "status": "success",
        "msg": "用戶註冊成功",
        "user_id": user_id,
        "access_token": access_token, # 直接返回 token
        "token_type": "bearer"
    }


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
        "phone": current_user.get("phone", "")
    }

    return {
        "status": "success",
        "msg": "獲取用戶資訊成功",
        "user_info": user_info
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
                    "carbon_points": 0,
                    "phone": None  # 明確設置 phone 為 None
                }

                # --- DEBUGGING ---
                print(f"Attempting to insert new Google user: {new_user}")
                # --- END DEBUGGING ---

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
