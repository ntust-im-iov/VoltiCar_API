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
    create_password_reset_otp_email_content, # 引入 OTP 模板函數
    create_binding_otp_email_content
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
    current_user: User = Depends(get_current_user)
):
    if db_provider.users_collection is None or db_provider.otp_records_collection is None:
        raise HTTPException(status_code=503, detail="資料庫服務未初始化")

    bind_type = type
    bind_value = value
    now = datetime.now()

    if bind_type not in ["phone", "email"]:
        raise HTTPException(status_code=400, detail="無效的綁定類型")

    # 檢查目標 email/phone 是否已被其他已驗證用戶綁定
    query_field = "email" if bind_type == "email" else "phone"
    existing_user_doc = await db_provider.users_collection.find_one({query_field: bind_value})

    if existing_user_doc and existing_user_doc["user_id"] != current_user.user_id:
        is_verified_field = "is_email_verified" if bind_type == "email" else "is_phone_verified"
        if existing_user_doc.get(is_verified_field, False):
            raise HTTPException(status_code=400, detail=f"此 {bind_type} 已被其他帳號驗證綁定")

    # 產生 OTP
    otp_code = "".join([str(random.randint(0, 9)) for _ in range(6)])
    otp_expires_at = now + timedelta(minutes=10) # OTP 10 分鐘後過期

    otp_record = {
        "user_id": current_user.user_id,
        "target_identifier": bind_value,
        "type": bind_type,
        "otp_code": otp_code,
        "created_at": now,
        "expires_at": otp_expires_at,
        "is_used": False
    }
    await db_provider.otp_records_collection.insert_one(otp_record)
    print(f"[綁定請求] OTP 記錄已創建: UserID {current_user.user_id}, Type {bind_type}, Target {bind_value}")

    if bind_type == "email":
        email_subject = "Volticar 帳號綁定驗證碼"
        # 使用 current_user.username 或 current_user.email 作為問候語中的名字
        username_or_email = current_user.username if current_user.username else current_user.email
        html_content = create_binding_otp_email_content(username_or_email, otp_code, "電子郵件")
        email_sent = await send_email_async(bind_value, email_subject, html_content)
        if email_sent:
            return {"status": "success", "msg": f"驗證碼已發送至 {bind_value}，請查收。"}
        else:
            # 即使郵件發送失敗，OTP 記錄也已創建，用戶仍可嘗試（例如，如果他們知道 OTP 或郵件延遲）
            # 但應提示用戶郵件發送可能存在問題
            print(f"警告：為 Email {bind_value} 發送綁定 OTP 郵件失敗。")
            raise HTTPException(status_code=500, detail="發送驗證郵件失敗，但您的請求已記錄。請稍後再試或聯繫客服。")
    elif bind_type == "phone":
        # 目前 SMS 功能未實現
        print(f"[綁定請求] 手機綁定 OTP: {otp_code} (SMS 功能待實現)")
        return {"status": "success", "msg": "手機綁定請求已收到 (SMS 功能暫未啟用，請使用測試驗證碼 123456，或後端日誌中的OTP)"}

    return {"status": "error", "msg": "未知的綁定類型處理錯誤"} # 理論上不會執行到這裡

@router.post("/verify-bind", response_model=Dict[str, Any])
async def verify_binding(
    type: str = Form(..., description="'phone' 或 'email'"),
    value: str = Form(..., description="手機號碼或電子郵件地址"),
    otp_code: str = Form(..., description="收到的驗證碼"),
    current_user: User = Depends(get_current_user)
):
    if db_provider.users_collection is None or db_provider.otp_records_collection is None:
        raise HTTPException(status_code=503, detail="資料庫服務未初始化")

    bind_type = type
    bind_value = value
    now = datetime.now()

    if bind_type not in ["phone", "email"]:
        raise HTTPException(status_code=400, detail="無效的綁定類型")

    # 測試模式：如果 OTP 是 123456 且類型是 phone (因為 SMS 未發送)
    if bind_type == "phone" and otp_code == "123456":
        print(f"警告：手機綁定使用測試驗證碼 123456 進行。")
        # 模擬 OTP 記錄查找成功
        otp_valid = True
    else:
        # 從 OTPRecords 查找有效的 OTP
        otp_record = await db_provider.otp_records_collection.find_one({
            "user_id": current_user.user_id,
            "target_identifier": bind_value,
            "type": bind_type,
            "otp_code": otp_code,
            "is_used": False,
            "expires_at": {"$gt": now}
        })
        otp_valid = otp_record is not None

    if not otp_valid:
        raise HTTPException(status_code=400, detail="驗證碼錯誤、已失效或不存在。")

    # 更新使用者資料
    update_data = {"updated_at": now}
    if bind_type == "email":
        update_data["email"] = bind_value
        update_data["is_email_verified"] = True
    elif bind_type == "phone":
        update_data["phone"] = bind_value
        update_data["is_phone_verified"] = True # 假設此欄位存在

    update_result = await db_provider.users_collection.update_one(
        {"user_id": current_user.user_id},
        {"$set": update_data}
    )

    if update_result.modified_count == 0:
        # 可能是用戶不存在或資料無變化，但前者不太可能因為 current_user 已驗證
        print(f"警告：更新用戶 {current_user.user_id} 的 {bind_type} 綁定資訊時，modified_count 為 0。")
        # 即使如此，OTP 仍應標記為已使用
        # raise HTTPException(status_code=500, detail="更新用戶綁定資訊失敗。")

    # 將 OTP 標記為已使用 (僅在非測試手機綁定情況下，或測試手機綁定也應模擬此操作)
    if not (bind_type == "phone" and otp_code == "123456"): # 如果不是測試手機碼
        await db_provider.otp_records_collection.update_one(
            {"_id": otp_record["_id"]}, # otp_record 來自上面 find_one
            {"$set": {"is_used": True}}
        )
    
    print(f"用戶 {current_user.user_id} 的 {bind_type} ({bind_value}) 已成功驗證並綁定。")
    return {"status": "success", "msg": f"{bind_type.capitalize()} 已成功綁定。"}

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

    # 1. 檢查 Email 的驗證狀態
    pending_record = await db_provider.pending_verifications_collection.find_one({"email": email})

    if not pending_record:
        #情況1：在 pending_verifications 中完全找不到此 email 的記錄
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此電子郵件尚未請求驗證，請先獲取驗證郵件。"
        )
    
    if not pending_record.get("is_verified", False):
        #情況2：在 pending_verifications 中找到記錄，但 is_verified 不是 true
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="電子郵件尚未完成驗證，請檢查您的收件匣並點擊驗證連結。"
        )

    # 到這裡表示 pending_record 存在且 is_verified 是 true

    if await db_provider.users_collection.find_one({"email": email}): # await
        # 理論上，如果 email 已在 users_collection，它不應該還在 pending_verifications 且 is_verified=true
        # 但作為雙重檢查，如果真的發生，則優先處理已註冊的情況
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
async def get_user_profile(current_user: User = Depends(get_current_user)): # Changed type hint to User
    # Access attributes directly from the Pydantic User model instance
    user_info = {
        "username": current_user.username,
        "user_id": current_user.user_id, # This is the custom UUID
        "email": current_user.email,
        "phone": current_user.phone,
        # "_id": str(current_user.id) if current_user.id else None # If you also want to return MongoDB _id
    }
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

@router.get("/tasks", response_model=Dict[str, Any]) # This path might be /user/tasks or /player/tasks based on other routes
async def get_user_tasks(user_id: str): # user_id here is the custom UUID string
    # Ensure correct collection names are used as defined in db_provider (mongodb.py)
    if db_provider.users_collection is None or db_provider.task_definitions_collection is None or db_provider.player_tasks_collection is None:
        raise HTTPException(status_code=503, detail="任務或用戶資料庫服務未初始化")
    
    user = await db_provider.users_collection.find_one({"user_id": user_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用戶不存在")

    # This endpoint seems to intend to list tasks a user has interacted with,
    # or all available tasks with user-specific progress.
    # Let's assume it's about tasks the player has accepted (from PlayerTasks)
    # and then enrich with TaskDefinition details.

    player_tasks_cursor = db_provider.player_tasks_collection.find({"player_id": user_id})
    player_tasks_list = await player_tasks_cursor.to_list(length=None)

    enriched_tasks = []
    for pt_doc in player_tasks_list:
        player_task = PlayerTask(**pt_doc) # player_task.task_id is the TaskDefinition.task_id (UUID)
        
        task_def = await db_provider.task_definitions_collection.find_one({"task_id": player_task.task_id})
        if task_def:
            enriched_tasks.append({
                "player_task_id": player_task.player_task_id, # Custom UUID of the PlayerTask instance
                "task_definition_id": player_task.task_id, # Custom UUID of the TaskDefinition
                "title": task_def.get("title", "N/A"),
                "description": task_def.get("description", ""),
                "status": player_task.status,
                "progress": player_task.progress.dict() if player_task.progress else {}, # Convert progress model to dict
                "rewards": task_def.get("rewards", {}) # From TaskDefinition
            })
        else:
            # Handle case where task definition is not found for an accepted player task
            enriched_tasks.append({
                "player_task_id": player_task.player_task_id,
                "task_definition_id": player_task.task_id,
                "title": "任務定義未找到",
                "description": "相關任務定義已不存在。",
                "status": player_task.status,
                "progress": player_task.progress.dict() if player_task.progress else {},
                "rewards": {}
            })
            
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
                    # If the email is already associated with a Google account,
                    # ensure the google_id matches or update it if it's missing for this specific google_id.
                    # This case implies the user might be trying to log in with a Google account
                    # that has the same email but perhaps a different underlying Google profile ID,
                    # or the google_id was not stored previously for this specific user.
                    if email_user.get("google_id") and email_user.get("google_id") != google_id:
                        # This is a rare case: same email, different google_id.
                        # Could be an attempt to link a different Google account to an existing Volticar Google account via email.
                        # Or, the user somehow has two Google accounts with the same primary email.
                        # For now, treat as a conflict if google_ids don't match.
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail="此電子郵件已與另一個Google帳號關聯。"
                        )
                    # If google_id matches or was missing and now we can set it:
                    await db_provider.users_collection.update_one(
                        {"_id": email_user["_id"]},
                        {"$set": {"google_id": google_id, "last_login": datetime.now()}}
                    )
                elif email_user.get("login_type") == "normal":
                    # Email is registered as a normal account, guide user to bind.
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT, # 409 Conflict is more appropriate
                        detail={
                            "code": "ACCOUNT_EXISTS_NORMAL_LOGIN_REQUIRED_FOR_BINDING",
                            "msg": "此 Email 已被一般帳號註冊。若要將 Google 帳號與其綁定，請先用該 Email 和密碼登入後，再從帳號設定中進行綁定。"
                        }
                    )
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

# --- 新增：檢查使用者名稱是否已使用 ---
@router.get("/check-username/{username}", response_model=Dict[str, Any])
async def check_username_exists(username: str):
    """
    檢查使用者名稱是否已被使用。
    """
    if db_provider.users_collection is None:
        print("錯誤：check_username_exists - users_collection 未初始化。")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="用戶資料庫服務未初始化"
        )

    print(f"檢查使用者名稱是否存在：{username}")
    if not username or not username.strip():
        return {"status": "error", "msg": "使用者名稱不可為空", "exists": False}

    user_exists = await db_provider.users_collection.find_one({"username": username}) is not None
    print(f"使用者名稱 {username} 是否已存在: {user_exists}")

    if user_exists:
        return {"status": "success", "msg": "使用者名稱已被使用", "exists": True}
    else:
        return {"status": "success", "msg": "使用者名稱可使用", "exists": False}

# --- 新增：帳號綁定相關端點 ---

class LinkGoogleAccountRequest(BaseModel):
    google_id: str
    google_email: EmailStr # Email from Google to check against existing accounts

@router.post("/link-google-account", response_model=Dict[str, Any], summary="將現有帳號綁定Google帳號")
async def link_google_account(
    request_data: LinkGoogleAccountRequest,
    current_user: User = Depends(get_current_user)
):
    if db_provider.users_collection is None:
        raise HTTPException(status_code=503, detail="用戶資料庫服務未初始化")

    google_id_to_link = request_data.google_id
    google_email_to_link = request_data.google_email

    # 1. 檢查此 google_id 是否已被其他帳號綁定
    existing_google_user = await db_provider.users_collection.find_one({"google_id": google_id_to_link})
    if existing_google_user and existing_google_user["user_id"] != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="此 Google 帳號已被其他 Volticar 帳號綁定。"
        )

    # 2. 檢查此 Google Email 是否已被一個不同的 "normal" 帳號註冊
    # (如果 Google Email 和當前用戶的 Email 相同，則此檢查無關緊要)
    if google_email_to_link != current_user.email:
        other_user_with_google_email = await db_provider.users_collection.find_one({"email": google_email_to_link})
        if other_user_with_google_email and \
           other_user_with_google_email["user_id"] != current_user.user_id and \
           other_user_with_google_email.get("login_type") == "normal" and \
           not other_user_with_google_email.get("google_id"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"電子郵件 {google_email_to_link} 已被另一個一般帳號註冊。如果您擁有該帳號，請先登入該帳號再嘗試綁定不同的 Google 帳號。"
            )
            
    # 3. 如果當前用戶已有 google_id，且與要綁定的不同，則提示錯誤
    if current_user.google_id and current_user.google_id != google_id_to_link:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="您的帳號已綁定另一個 Google 帳號。"
        )

    # 4. 更新當前用戶的 google_id
    #    同時，如果用戶的 login_type 是 "normal"，可以考慮是否要更新，或保持不變允許雙重登入。
    #    為了簡單起見，這裡只更新 google_id。如果 email 也需要更新以匹配 Google email，需額外處理。
    update_result = await db_provider.users_collection.update_one(
        {"user_id": current_user.user_id},
        {"$set": {"google_id": google_id_to_link, "updated_at": datetime.now()}}
    )

    if update_result.modified_count == 0 and not current_user.google_id == google_id_to_link : # No change if already linked to same google_id
        print(f"警告：嘗試為用戶 {current_user.user_id} 綁定 Google ID {google_id_to_link} 時，modified_count 為 0。")
        # 這可能是因為 current_user.user_id 不存在，但 Depends(get_current_user) 應該已經處理了
        raise HTTPException(status_code=500, detail="綁定 Google 帳號失敗，請稍後再試。")

    return {"status": "success", "msg": "Google 帳號已成功綁定。"}


class SetLoginPasswordRequest(BaseModel):
    new_password: str = Form(..., min_length=8)

@router.post("/set-login-password", response_model=Dict[str, Any], summary="為Google登入用戶設定登入密碼")
async def set_login_password(
    request_data: SetLoginPasswordRequest,
    current_user: User = Depends(get_current_user)
):
    if db_provider.users_collection is None:
        raise HTTPException(status_code=503, detail="用戶資料庫服務未初始化")

    # 此功能主要針對 login_type="google" 且尚未設定密碼的用戶
    # 但也可以允許任何已登入用戶設定或更改其密碼（如果他們忘記了舊密碼，應走忘記密碼流程）
    # 這裡簡化為：任何已登入用戶都可以透過此端點設定/更新其密碼
    # if current_user.login_type != "google" and current_user.password_hash:
    #     raise HTTPException(status_code=400, detail="此帳號已有密碼，若需更改請使用修改密碼功能。")

    hashed_password = get_password_hash(request_data.new_password)
    
    update_fields = {
        "password_hash": hashed_password,
        "updated_at": datetime.now()
    }
    
    # 如果原先是純 Google 帳號，設定密碼後，login_type 可能需要調整
    # 例如，可以保持 login_type="google"，但客戶端和 /login 端點需要知道
    # password_hash 非空表示也可以用密碼登入。
    # 或者，可以新增一個 login_type 如 "google_and_normal" 或 "hybrid"。
    # 暫時不更改 login_type，依賴 password_hash 是否存在來判斷。
    # if current_user.login_type == "google" and not current_user.password_hash:
    #    update_fields["login_type"] = "google_with_password" # 示例性修改

    update_result = await db_provider.users_collection.update_one(
        {"user_id": current_user.user_id},
        {"$set": update_fields}
    )

    if update_result.modified_count == 0:
        # 可能是密碼未改變，或者用戶不存在（不太可能）
        print(f"警告：為用戶 {current_user.user_id} 設定密碼時，modified_count 為 0。")
        # 如果密碼與舊密碼相同，modified_count 也可能為0，這不一定是錯誤
        # return {"status": "info", "msg": "新密碼與舊密碼相同，未做更改。"}

    return {"status": "success", "msg": "登入密碼已成功設定/更新。"}
