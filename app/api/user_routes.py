from fastapi import APIRouter, Depends, HTTPException, status, Body, Request
from fastapi.responses import HTMLResponse # Import HTMLResponse
from datetime import timedelta, datetime
from typing import Dict, Any, Optional
import uuid
import os
import sys # Import sys module
import secrets
import random # 引入 random 模組生成 OTP
from pydantic import EmailStr, BaseModel
from fastapi import Query, Form # 引入 Form

from app.models.user import (
    User, UserCreate, UserLogin, # LoginRecord is imported but not used as type hint/response model
    FCMTokenUpdate, FriendAction, GoogleLoginRequest, BindRequest, VerifyBindingRequest
) # Removed LoginRecord model import
from app.utils.auth import authenticate_user, create_access_token, get_current_user, get_password_hash
# Import the email service from the app/services directory
from app.services.email_service import ( # Updated import path
    send_email_async,
    create_verification_email_content,
    # create_password_reset_email_content, # 改用 OTP 模板
    create_password_reset_otp_email_content # 引入 OTP 模板函數
)
from app.database import mongodb as db_provider # Import the module itself
from app.models.user import EmailVerificationRequest, CompleteRegistrationRequest # 引入新的 Pydantic 模型

router = APIRouter(prefix="/users", tags=["用戶"])

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days

# --- 舊的 /register 路由已移除 ---

# --- 新增：請求 Email 驗證 ---
@router.post("/request-verification", response_model=Dict[str, Any], status_code=status.HTTP_200_OK)
async def request_email_verification(email: EmailStr = Form(...)):
    """
    請求發送 Email 驗證信 (使用表單欄位)

    - **email**: 要驗證的電子郵件地址
    """
    if db_provider.users_collection is None or db_provider.pending_verifications_collection is None:
        print("錯誤：request_email_verification - 資料庫集合未初始化。")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="資料庫服務暫時無法使用，請稍後再試"
        )

    now = datetime.now()

    if await db_provider.users_collection.find_one({"email": email}):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此電子郵件已被註冊"
        )

    pending_record = await db_provider.pending_verifications_collection.find_one({"email": email})
    if pending_record and not pending_record.get("is_verified", False):
        last_requested = pending_record.get("requested_at")
        if last_requested and (now - last_requested) < timedelta(minutes=5):
             print(f"Email {email} 請求過於頻繁，提示用戶檢查信箱。")
             raise HTTPException(
                 status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                 detail="請求過於頻繁，請檢查您的收件匣或稍後再試。"
             )
        print(f"Email {email} 已有待驗證記錄，但已超過時間限制，更新 token 並準備重發。")
        verification_token = secrets.token_urlsafe(32)
        verification_token_expires_at = now + timedelta(hours=1)
        await db_provider.pending_verifications_collection.update_one(
            {"email": email},
            {"$set": {
                "token": verification_token,
                "expires_at": verification_token_expires_at,
                "is_verified": False,
                "requested_at": now
            }}
        )
    else:
        verification_token = secrets.token_urlsafe(32)
        verification_token_expires_at = now + timedelta(hours=1)
        await db_provider.pending_verifications_collection.update_one(
            {"email": email},
            {"$set": {
                "token": verification_token,
                "expires_at": verification_token_expires_at,
                "is_verified": False,
                "requested_at": now
            }},
            upsert=True
        )
        print(f"已為 Email {email} 產生待驗證記錄。")

    api_base_url = os.getenv("API_BASE_URL", "https://volticar.dynns.com:22000")
    if api_base_url == "https://volticar.dynns.com:22000":
         print(f"警告：未設定 API_BASE_URL 環境變數，使用預設值: {api_base_url}")

    verification_link = f"{api_base_url}/users/verify-email?token={verification_token}"
    html_content = create_verification_email_content(email, verification_link)

    email_sent = await send_email_async(email, "Volticar 帳號驗證", html_content)
    if not email_sent:
        print(f"錯誤：為 Email {email} 發送驗證郵件失敗。")
        raise HTTPException(status_code=500, detail="發送驗證郵件失敗，請稍後再試")

    print(f"已向 Email {email} 發送驗證郵件。")
    return {"status": "success", "msg": "驗證郵件已發送，請檢查您的收件匣。"}

# 用戶登入
@router.post("/login", response_model=Dict[str, Any])
async def login_user(
    request: Request,
    username: Optional[str] = Form(None),
    email: Optional[EmailStr] = Form(None),
    password: str = Form(...)
):
    if db_provider.users_collection is None:
        print("錯誤：login_user - users_collection 未初始化。")
        raise HTTPException(status_code=503, detail="用戶資料庫服務未初始化")
    if db_provider.login_records_collection is None:
        print("錯誤：login_user - login_records_collection 未初始化。")
        raise HTTPException(status_code=503, detail="登入記錄資料庫服務未初始化")

    query = {}
    if username:
        query["username"] = username
    elif email:
        query["email"] = email
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="請提供用戶名或電子郵件"
        )

    user = await db_provider.users_collection.find_one(query)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用戶不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.get("login_type") == "google":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "GOOGLE_AUTH_REQUIRED",
                "msg": "此帳號是透過 Google 註冊，請使用 Google 登入"
            }
        )

    authenticated = authenticate_user(user, password, password_field="password_hash")
    if not authenticated:
        if user.get("password_hash") is None:
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

    client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or \
                  request.headers.get("X-Real-IP", "") or \
                  request.client.host
    user_agent = request.headers.get("user-agent", "unknown")
    now = datetime.now()

    login_record = {
        "user_id": user["user_id"],
        "login_method": "normal",
        "ip_address": client_ip,
        "device_info": user_agent,
        "created_at": now,
        "login_timestamp": now
    }
    await db_provider.login_records_collection.insert_one(login_record)

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
@router.post("/request-bind", response_model=Dict[str, Any])
async def request_bind(
    type: str = Form(..., description="'phone' 或 'email'"),
    value: str = Form(..., description="手機號碼或電子郵件地址"),
    current_user: Dict = Depends(get_current_user)
):
    if db_provider.users_collection is None:
        raise HTTPException(status_code=503, detail="用戶資料庫服務未初始化")
    bind_type = type
    bind_value = value
    if bind_type not in ["phone", "email"]:
        raise HTTPException(status_code=400, detail="無效的綁定類型")
    existing_user = await db_provider.users_collection.find_one({bind_type: bind_value})
    if existing_user and existing_user["user_id"] != current_user["user_id"]:
        raise HTTPException(status_code=400, detail=f"此 {bind_type} 已被其他帳號綁定")
    print(f"[綁定請求] 類型: {bind_type}, 值: {bind_value}, 用戶ID: {current_user['user_id']}")
    return {"status": "success", "msg": "綁定請求已收到 (OTP功能暫未啟用，請使用測試驗證碼)"}

@router.post("/verify-bind", response_model=Dict[str, Any])
async def verify_binding(
    type: str = Form(..., description="'phone' 或 'email'"),
    value: str = Form(..., description="手機號碼或電子郵件地址"),
    otp_code: str = Form(..., description="收到的驗證碼"),
    current_user: Dict = Depends(get_current_user)
):
    bind_type = type
    bind_value = value
    if bind_type not in ["phone", "email"]:
        raise HTTPException(status_code=400, detail="無效的綁定類型")
    print(f"[驗證綁定] 類型: {bind_type}, 值: {bind_value}, 驗證碼: {otp_code}, 用戶ID: {current_user['user_id']}")
    if otp_code != "123456":
         raise HTTPException(status_code=400, detail="驗證碼錯誤 (測試模式，請使用 123456)")
    print(f"驗證成功 (測試模式)，用戶 {current_user['user_id']} 的 {bind_type} ({bind_value}) 未實際更新資料庫。")
    return {"status": "success", "msg": f"{bind_type} 驗證成功 (測試模式)"}

# --- Email 驗證端點 (使用 pending_verifications) ---
@router.get("/verify-email", response_class=HTMLResponse, summary="驗證電子郵件地址 (返回 HTML)")
async def verify_email_html(token: str = Query(...)):
    if db_provider.pending_verifications_collection is None:
        print("錯誤：verify_email_html - pending_verifications_collection 未初始化。")
        raise HTTPException(status_code=503, detail="驗證資料庫服務未初始化")
    now = datetime.now()
    success_html = """<!DOCTYPE html><html><head><title>Email 驗證成功</title></head><body><h1>驗證成功！</h1><p>您的電子郵件地址已成功驗證。請返回 APP 完成註冊。</p></body></html>"""
    already_verified_html = """<!DOCTYPE html><html><head><title>Email 已驗證</title></head><body><h1>操作完成</h1><p>您的電子郵件地址先前已經驗證過了。請返回 APP 完成註冊。</p></body></html>"""
    error_html = """<!DOCTYPE html><html><head><title>Email 驗證失敗</title></head><body><h1>驗證失敗</h1><p>驗證連結無效或已過期。請返回 APP 重新請求驗證。</p></body></html>"""
    print(f"收到驗證請求，Token: {token}")
    pending_record = await db_provider.pending_verifications_collection.find_one({
        "token": token,
        "expires_at": {"$gt": now}
    })
    if not pending_record:
        print(f"驗證失敗：在 pending_verifications 中找不到對應 Token 或 Token 已過期 (Token: {token})")
        return HTMLResponse(content=error_html, status_code=400)
    if pending_record.get("is_verified", False):
         print(f"Token {token} 對應的 Email {pending_record.get('email')} 已被標記為驗證。")
         return HTMLResponse(content=already_verified_html, status_code=200)
    update_result = await db_provider.pending_verifications_collection.update_one(
        {"_id": pending_record["_id"], "token": token},
        {"$set": {"is_verified": True, "verified_at": now, "token": None, "expires_at": None}}
    )
    if update_result.modified_count == 0:
        print(f"錯誤：嘗試更新 Email {pending_record.get('email')} 的驗證狀態失敗 (可能已被驗證或 token 失效)。")
        current_record = await db_provider.pending_verifications_collection.find_one({"_id": pending_record["_id"]})
        if current_record and current_record.get("is_verified"):
             print(f"確認 Email {pending_record.get('email')} 確實已被驗證。")
             return HTMLResponse(content=already_verified_html, status_code=200)
        else:
             print(f"確認 Email {pending_record.get('email')} 未被驗證，返回錯誤。")
             return HTMLResponse(content=error_html, status_code=400)
    print(f"Email {pending_record.get('email')} 已成功標記為驗證。")
    return HTMLResponse(content=success_html, status_code=200)

# --- Password Reset Endpoints ---
class ForgotPasswordRequest(BaseModel):
    identifier: str
class ResetPasswordRequest(BaseModel):
    confirmation_token: str
    new_password: str
class VerifyOtpRequest(BaseModel):
    identifier: str
    otp_code: str
class VerifyOtpResponse(BaseModel):
    status: str = "success"
    msg: str = "驗證碼正確"
    confirmation_token: str

@router.post("/forgot-password", response_model=Dict[str, Any])
async def forgot_password(identifier: str = Form(..., description="用戶的電子郵件或手機號碼")):
    if db_provider.users_collection is None:
        raise HTTPException(status_code=503, detail="用戶資料庫服務未初始化")
    now = datetime.now()
    otp_expires_delta = timedelta(minutes=10)
    otp_expires_at = now + otp_expires_delta
    user = await db_provider.users_collection.find_one({"$or": [{"email": identifier}, {"phone": identifier}]})
    if not user:
        print(f"請求重設密碼 OTP，但找不到用戶: {identifier}")
        return {"status": "success", "msg": "如果您的帳戶存在，重設密碼的驗證碼將很快發送。"}
    if user.get("login_type") == "google":
        print(f"用戶 {identifier} 是 Google 登入用戶，無法請求密碼重設 OTP。")
        return {"status": "success", "msg": "如果您的帳戶存在，重設密碼的驗證碼將很快發送。"}
    otp_code = "".join([str(random.randint(0, 9)) for _ in range(6)])
    update_result = await db_provider.users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "reset_otp_code": otp_code,
            "reset_otp_expires_at": otp_expires_at,
            "updated_at": now,
            "reset_password_token": None,
            "reset_password_token_expires_at": None
        }}
    )
    if update_result.modified_count == 0:
         print(f"錯誤：無法為用戶 {identifier} 更新 OTP。")
         raise HTTPException(status_code=500, detail="無法生成密碼重設驗證碼，請稍後再試。")
    email_sent_status = False
    if "@" in identifier and identifier == user.get("email"):
        html_content = create_password_reset_otp_email_content(user.get("username", "用戶"), otp_code)
        email_sent_status = await send_email_async(user["email"], "Volticar 密碼重設驗證碼", html_content)
        if email_sent_status:
            print(f"已向郵箱 {user['email']} 發送密碼重設 OTP。")
        else:
            print(f"錯誤：為郵箱 {user['email']} 生成了 OTP，但郵件發送失敗。")
    elif identifier == user.get("phone"):
        print(f"收到手機號碼 {identifier} 的重設密碼請求，OTP: {otp_code} (SMS 功能待實現)")
    else:
         print(f"請求的 identifier {identifier} 與找到的用戶 {user['user_id']} 的 Email/Phone 不匹配")
    return {"status": "success", "msg": "如果您的帳戶存在且符合重設條件，驗證碼將很快發送。"}

@router.post("/verify-reset-otp", response_model=VerifyOtpResponse)
async def verify_reset_otp(
    identifier: EmailStr = Form(..., description="用戶的電子郵件"),
    otp_code: str = Form(..., min_length=6, max_length=6, description="從郵件收到的 6 位驗證碼")
):
    if db_provider.users_collection is None:
        raise HTTPException(status_code=503, detail="用戶資料庫服務未初始化")
    now = datetime.now()
    user = await db_provider.users_collection.find_one({
        "email": identifier,
        "reset_otp_code": otp_code,
        "reset_otp_expires_at": {"$gt": now}
    })
    if not user:
        print(f"OTP 驗證失敗：無效的 Email、OTP 或 OTP 已過期 (Identifier: {identifier}, OTP: {otp_code})")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="驗證碼無效或已過期")
    confirmation_token = secrets.token_urlsafe(32)
    confirmation_token_expires_at = now + timedelta(minutes=5)
    update_result = await db_provider.users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "reset_confirmation_token": confirmation_token,
            "reset_confirmation_expires_at": confirmation_token_expires_at,
            "updated_at": now,
            "reset_otp_code": None,
            "reset_otp_expires_at": None
        }}
    )
    if update_result.modified_count == 0:
        print(f"錯誤：無法為用戶 {identifier} 更新確認權杖。")
        raise HTTPException(status_code=500, detail="驗證處理失敗，請稍後再試。")
    print(f"用戶 {identifier} OTP 驗證成功，已生成確認權杖。")
    return VerifyOtpResponse(confirmation_token=confirmation_token)

@router.post("/reset-password", response_model=Dict[str, Any])
async def reset_password(
    confirmation_token: str = Form(..., description="從 /verify-reset-otp 獲取的短期權杖"),
    new_password: str = Form(..., min_length=8, description="新密碼 (至少 8 位)")
):
    if db_provider.users_collection is None:
        raise HTTPException(status_code=503, detail="用戶資料庫服務未初始化")
    now = datetime.now()
    user = await db_provider.users_collection.find_one({
        "reset_confirmation_token": confirmation_token,
        "reset_confirmation_expires_at": {"$gt": now}
    })
    if not user:
        print(f"重設密碼失敗：無效或已過期的確認權杖 (Token: {confirmation_token})")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="重設密碼請求無效或已過期，請重新操作。")
    if user.get("login_type") == "google":
        print(f"錯誤：Google 登入用戶 {user.get('email')} 嘗試使用確認權杖重設密碼。")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google 帳號無法透過此方式重設密碼。")
    if len(new_password) < 8:
         raise HTTPException(status_code=400, detail="新密碼長度至少需要 8 位")
    hashed_password = get_password_hash(new_password)
    update_result = await db_provider.users_collection.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "password_hash": hashed_password,
            "updated_at": now,
            "reset_confirmation_token": None,
            "reset_confirmation_expires_at": None
        }}
    )
    if update_result.modified_count == 0:
        print(f"錯誤：更新用戶 {user.get('email')} 密碼時失敗 (使用確認權杖)。")
        raise HTTPException(status_code=500, detail="重設密碼失敗，請稍後再試。")
    print(f"用戶 {user['user_id']} ({user.get('email')}) 已成功使用確認權杖重設密碼")
    return {"status": "success", "msg": "密碼已成功重設"}

# --- 新增：完成註冊 ---
@router.post("/complete-registration", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def complete_registration(
    email: EmailStr = Form(..., description="已驗證的電子郵件"),
    username: str = Form(..., description="用戶名稱"),
    password: str = Form(..., min_length=8, description="密碼 (至少 8 位)"),
    phone: Optional[str] = Form(None, description="手機號碼 (可選)")
):
    if db_provider.pending_verifications_collection is None: # Corrected NameError by using db_provider
        print("錯誤：complete_registration - pending_verifications_collection 未初始化。")
        raise HTTPException(status_code=503, detail="驗證資料庫服務未初始化")
    if db_provider.users_collection is None:
        print("錯誤：complete_registration - users_collection 未初始化。")
        raise HTTPException(status_code=503, detail="用戶資料庫服務未初始化")

    now = datetime.now()
    pending_record = await db_provider.pending_verifications_collection.find_one({ # await
        "email": email,
        "is_verified": True
    })
    if not pending_record:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="電子郵件尚未驗證或驗證記錄不存在")
    if await db_provider.users_collection.find_one({"email": email}): # await
        await db_provider.pending_verifications_collection.delete_one({"email": email}) # await
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="此電子郵件已被註冊")
    if await db_provider.users_collection.find_one({"username": username}): # await
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="此用戶名已被使用")
    if phone and await db_provider.users_collection.find_one({"phone": phone}): # await
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="此手機號已被註冊")

    hashed_password = get_password_hash(password)
    user_id = str(uuid.uuid4())
    user_dict = {
        "user_id": user_id, "email": email, "username": username,
        "password_hash": hashed_password, "phone": phone if phone else None,
        "login_type": "normal", "created_at": now, "updated_at": now,
        "is_email_verified": True, "google_id": None
    }
    result = await db_provider.users_collection.insert_one(user_dict) # await
    if not result.inserted_id:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="創建用戶失敗")
    delete_result = await db_provider.pending_verifications_collection.delete_one({"email": email}) # await
    if delete_result.deleted_count == 0:
        print(f"警告：用戶 {user_id} ({email}) 註冊成功，但未能從 pending_verifications 刪除記錄。")
    print(f"用戶 {user_id} ({email}) 已成功完成註冊。")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user_id}, expires_delta=access_token_expires)
    return {"status": "success", "msg": "用戶註冊成功", "user_id": user_id, "access_token": access_token, "token_type": "bearer"}

# --- Other Endpoints ---
@router.get("/profile", response_model=Dict[str, Any])
async def get_user_profile(current_user: Dict = Depends(get_current_user)):
    user_info = {"username": current_user.get("username", ""), "user_id": current_user.get("user_id", ""), "email": current_user.get("email", ""), "phone": current_user.get("phone", "")}
    return {"status": "success", "msg": "獲取用戶資訊成功", "user_info": user_info}

@router.post("/update-fcm-token", response_model=Dict[str, Any])
async def update_fcm_token(
    user_id: str = Form(..., description="用戶ID"),
    fcm_token: str = Form(..., description="FCM令牌"),
    device_info: Optional[str] = Form(None, description="設備信息 (選填)")
):
    if db_provider.users_collection is None:
        raise HTTPException(status_code=503, detail="用戶資料庫服務未初始化")
    print(f"更新FCM令牌，使用者ID: {user_id}")
    result = await db_provider.users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"fcm_token": fcm_token, "device_info": device_info, "token_updated_at": datetime.now()}}
    )
    if result.modified_count == 0:
        user_exists = await db_provider.users_collection.find_one({"user_id": user_id})
        if not user_exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="使用者不存在")
    return {"status": "success", "msg": "FCM令牌已更新"}

@router.get("/check-phone/{phone}", response_model=Dict[str, Any])
async def check_phone_exists(phone: str):
    if db_provider.users_collection is None:
        raise HTTPException(status_code=503, detail="用戶資料庫服務未初始化")
    print(f"檢查手機號碼是否存在：{phone}")
    if not phone or not (phone.startswith('09') and len(phone) == 10):
        return {"status": "error", "msg": "手機號碼格式不正確，應為台灣手機號碼格式（09開頭，共10位數）", "exists": False}
    user_exists = await db_provider.users_collection.find_one({"phone": phone}) is not None
    print(f"手機號碼 {phone} 是否已存在: {user_exists}")
    return {"status": "success", "msg": "檢查完成", "exists": user_exists}

@router.get("/leaderboard", response_model=Dict[str, Any])
async def get_leaderboard(time_range: str = "week"):
    if db_provider.users_collection is None:
        raise HTTPException(status_code=503, detail="用戶資料庫服務未初始化")
    if time_range == "day":
        start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    elif time_range == "week":
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_time = today - timedelta(days=today.weekday())
    elif time_range == "month":
        start_time = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="無效的時間範圍，應為 day、week 或 month")
    leaderboard_cursor = db_provider.users_collection.find(
        {"last_login": {"$gte": start_time}},
        {"user_id": 1, "username": 1, "carbon_credits": 1}
    ).sort("carbon_credits", -1).limit(10)
    leaderboard = await leaderboard_cursor.to_list(length=10)
    result_list = [] # Renamed from result to avoid conflict
    for i, user_doc in enumerate(leaderboard): # Renamed user to user_doc
        result_list.append({"rank": i + 1, "user_id": user_doc.get("user_id", ""), "username": user_doc.get("username", "Unknown"), "score": user_doc.get("carbon_credits", 0)})
    return {"status": "success", "msg": "獲取排行榜成功", "leaderboard": result_list}

@router.post("/friends", response_model=Dict[str, Any])
async def manage_friends(
    user_id: str = Form(..., description="用戶自己的 ID"),
    friend_id: str = Form(..., description="要添加/刪除的好友 ID"),
    action: str = Form(..., description="操作類型 ('add' 或 'remove')")
):
    if db_provider.users_collection is None:
        raise HTTPException(status_code=503, detail="用戶資料庫服務未初始化")
    user = await db_provider.users_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用戶不存在")
    friend = await db_provider.users_collection.find_one({"user_id": friend_id})
    if not friend:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="好友不存在")
    if action == "add":
        if "friends" in user and friend_id in user["friends"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="已經是好友")
        await db_provider.users_collection.update_one({"user_id": user_id}, {"$addToSet": {"friends": friend_id}})
        await db_provider.users_collection.update_one({"user_id": friend_id}, {"$addToSet": {"friends": user_id}})
        return {"status": "success", "msg": "添加好友成功"}
    elif action == "remove":
        if "friends" not in user or friend_id not in user["friends"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不是好友")
        await db_provider.users_collection.update_one({"user_id": user_id}, {"$pull": {"friends": friend_id}})
        await db_provider.users_collection.update_one({"user_id": friend_id}, {"$pull": {"friends": user_id}})
        return {"status": "success", "msg": "移除好友成功"}
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="無效的操作，應為 'add' 或 'remove'")

@router.get("/tasks", response_model=Dict[str, Any])
async def get_user_tasks(user_id: str):
    if db_provider.users_collection is None or db_provider.tasks_collection is None:
        raise HTTPException(status_code=503, detail="任務或用戶資料庫服務未初始化")
    user = await db_provider.users_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用戶不存在")
    all_tasks_cursor = db_provider.tasks_collection.find({})
    all_tasks = await all_tasks_cursor.to_list(length=None)
    user_tasks = []
    for task in all_tasks:
        progress = 0
        if "user_tasks" in user and str(task["_id"]) in user["user_tasks"]:
            progress = user["user_tasks"][str(task["_id"])]["progress"]
        user_tasks.append({"task_id": str(task["_id"]), "description": task.get("description", ""), "progress": progress, "reward": task.get("reward", {})})
    return {"status": "success", "msg": "獲取任務列表成功", "tasks": user_tasks}

@router.get("/achievements", response_model=Dict[str, Any])
async def get_user_achievements(user_id: str):
    if db_provider.users_collection is None or db_provider.achievements_collection is None:
        raise HTTPException(status_code=503, detail="成就或用戶資料庫服務未初始化")
    user = await db_provider.users_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用戶不存在")
    all_achievements_cursor = db_provider.achievements_collection.find({})
    all_achievements = await all_achievements_cursor.to_list(length=None)
    user_achievements = []
    for achievement in all_achievements:
        unlocked = False
        progress = 0
        if "achievements" in user and str(achievement["_id"]) in user["achievements"]:
            user_achievement = user["achievements"][str(achievement["_id"])]
            unlocked = user_achievement.get("unlocked", False)
            progress = user_achievement.get("progress", 0)
        user_achievements.append({"achievement_id": str(achievement["_id"]), "description": achievement.get("description", ""), "progress": progress, "unlocked": unlocked})
    return {"status": "success", "msg": "獲取成就列表成功", "achievements": user_achievements}

@router.post("/redeem-reward", response_model=Dict[str, Any])
async def redeem_reward(
    user_id: str = Form(..., description="用戶ID"),
    points: int = Form(..., description="兌換所需積分"),
    reward_id: str = Form(..., description="獎勵ID")
):
    if db_provider.users_collection is None or db_provider.rewards_collection is None:
        raise HTTPException(status_code=503, detail="獎勵或用戶資料庫服務未初始化")
    user = await db_provider.users_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用戶不存在")
    if user.get("carbon_credits", 0) < points:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="積分不足")
    reward = await db_provider.rewards_collection.find_one({"_id": reward_id})
    if not reward:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="獎勵項目不存在")
    await db_provider.users_collection.update_one({"user_id": user_id}, {"$inc": {"carbon_credits": -points}})
    await db_provider.users_collection.update_one({"user_id": user_id}, {"$push": {"inventory": reward_id}})
    return {"status": "success", "msg": "兌換獎勵成功", "reward_item": reward.get("name", "")}

@router.get("/inventory", response_model=Dict[str, Any])
async def get_user_inventory(user_id: str):
    if db_provider.users_collection is None or db_provider.rewards_collection is None:
        raise HTTPException(status_code=503, detail="獎勵或用戶資料庫服務未初始化")
    user = await db_provider.users_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用戶不存在")
    inventory_ids = user.get("inventory", [])
    inventory_items = []
    if inventory_ids:
        for item_id in inventory_ids:
            item = await db_provider.rewards_collection.find_one({"_id": item_id})
            if item:
                inventory_items.append({"item_id": str(item["_id"]), "name": item.get("name", ""), "description": item.get("description", "")})
    return {"status": "success", "msg": "獲取物品庫成功", "inventory": {"owned_items": inventory_items}}

@router.get("/charging-stations", response_model=Dict[str, Any])
async def get_charging_stations(user_id: str, location: str):
    try:
        lat, lng = map(float, location.split(","))
    except:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="位置格式錯誤，應為\"緯度,經度\"")
    stations = [{"station_id": "station1", "name": "充電站1", "distance": 0.5, "availability": True}, {"station_id": "station2", "name": "充電站2", "distance": 1.2, "availability": False}]
    return {"status": "success", "msg": "獲取充電站信息成功", "stations": stations}

@router.post("/login/google", summary="使用Google帳號登入")
async def login_with_google(
    google_id: Optional[str] = Form(None, description="Google 用戶 ID"),
    email: Optional[EmailStr] = Form(None, description="Google 提供的 Email"),
    name: Optional[str] = Form(None, description="Google 提供的名稱"),
    picture: Optional[str] = Form(None, description="Google 提供的頭像 URL (可選)")
):
    if db_provider.users_collection is None:
        raise HTTPException(status_code=503, detail="用戶資料庫服務未初始化")
    try:
        if not google_id or not google_id.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="無效的Google ID")
        existing_user = await db_provider.users_collection.find_one({"google_id": google_id, "login_type": "google"})
        if existing_user:
            await db_provider.users_collection.update_one({"_id": existing_user["_id"]}, {"$set": {"last_login": datetime.now()}})
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(data={"sub": existing_user["user_id"]}, expires_delta=access_token_expires)
            return {"status": "success", "msg": "Google登入成功", "user_id": existing_user["user_id"], "access_token": access_token, "token_type": "bearer"}
        else:
            if not email:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="缺少電子郵件資訊")
            email_user = await db_provider.users_collection.find_one({"email": email})
            if email_user:
                if email_user.get("login_type") == "google":
                    await db_provider.users_collection.update_one({"_id": email_user["_id"]}, {"$set": {"google_id": google_id, "last_login": datetime.now()}})
                elif email_user.get("login_type") == "normal":
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="此郵箱已使用其他登入方式註冊，請使用原登入方式或聯繫客服綁定帳號")
                access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
                access_token = create_access_token(data={"sub": email_user["user_id"]}, expires_delta=access_token_expires)
                return {"status": "success", "msg": "Google登入成功", "user_id": email_user["user_id"], "access_token": access_token, "token_type": "bearer"}
            else:
                user_id = str(uuid.uuid4())
                username = name or f"user_{uuid.uuid4().hex[:8]}"
                if await db_provider.users_collection.find_one({"username": username}):
                    username = f"user_{uuid.uuid4().hex[:8]}"
                new_user = {
                    "user_id": user_id, "email": email, "username": username, "google_id": google_id,
                    "login_type": "google", "created_at": datetime.now(), "updated_at": datetime.now(),
                    "last_login": datetime.now(), "password_hash": None, "is_active": True,
                    "carbon_points": 0, "phone": None
                }
                print(f"Attempting to insert new Google user: {new_user}")
                result = await db_provider.users_collection.insert_one(new_user)
                if not result.inserted_id:
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="創建用戶失敗")
                access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
                access_token = create_access_token(data={"sub": user_id}, expires_delta=access_token_expires)
                return {"status": "success", "msg": "Google登入成功，已創建新帳號", "user_id": user_id, "access_token": access_token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Google登入失敗: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Google登入失敗: {str(e)}")
