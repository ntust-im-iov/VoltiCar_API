from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime # Changed import
from bson import ObjectId

# 用戶模型 (Users 集合) - 代表資料庫中的完整用戶文檔結構
class User(BaseModel):
    id: Optional[str] = None  # MongoDB ObjectId (_id)
    user_id: str  # 應用程式生成的唯一 ID
    email: EmailStr
    username: str
    phone: Optional[str] = None
    password_hash: Optional[str] = None # Google 登入用戶可能沒有密碼
    google_id: Optional[str] = None
    login_type: str = "normal"
    reset_password_token: Optional[str] = None
    reset_password_token_expires_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    # 其他可能的用戶欄位，例如 fcm_token, achievements, tasks, friends, carbon_credits 等
    # 這些可以在需要時添加到模型中，或者保持 User 模型只包含核心身份信息

    model_config = {
        "from_attributes": True, # 允許從 ORM 對象或其他屬性創建模型
        "json_schema_extra": {
            "example": {
                "user_id": "uuid-generated-id",
                "email": "user@example.com",
                "username": "username",
                "phone": "0912345678",
                "login_type": "normal",
                "google_id": None,
            }
        }
    }

# --- Request/Response Models Used in Routes ---

# 登入記錄模型 (LoginRecords 集合) - Used implicitly by user_routes.py/get_login_records
class LoginRecord(BaseModel):
    id: Optional[str] = None
    user_id: str
    login_method: str
    ip_address: str
    device_info: str
    created_at: datetime = Field(default_factory=datetime.now)
    login_timestamp: datetime = Field(default_factory=datetime.now)

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "user_id": "user123",
                "login_method": "password",
                "ip_address": "192.168.1.1",
                "device_info": "Chrome/Windows"
            }
        }
    }

# 創建用戶請求模型 - Used by user_routes.py/register_user
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    login_type: str = "normal"

# 登錄請求模型 - Used by user_routes.py/login_user
class UserLogin(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    # phone: Optional[str] = None # 移除 phone 欄位，登入只用 username 或 email
    password: str

# --- 新增：Email 驗證請求模型 ---
class EmailVerificationRequest(BaseModel):
    email: EmailStr

# --- 新增：完成註冊請求模型 ---
class CompleteRegistrationRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    phone: Optional[str] = None

# 綁定請求模型 - Used by user_routes.py/request_bind
class BindRequest(BaseModel):
    type: str
    value: str

# 驗證綁定請求模型 - Used by user_routes.py/verify_binding
class VerifyBindingRequest(BaseModel):
    type: str
    value: str
    otp_code: str

# 車輛創建模型 - Used by vehicle_routes.py/register_vehicle
class VehicleCreate(BaseModel):
    vehicle_id: str
    user_id: str
    vehicle_name: Optional[str] = None

# 車輛更新模型 - Used by vehicle_routes.py/update_vehicle
class VehicleUpdate(BaseModel):
    vehicle_name: Optional[str] = None
    mileage: Optional[int] = None

# FCM令牌更新模型 - Used by user_routes.py/update_fcm_token
class FCMTokenUpdate(BaseModel):
    user_id: str
    fcm_token: str
    device_info: Optional[str] = None

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "user123",
                "fcm_token": "fGDrT5XAQwetGg...",
                "device_info": "iPhone 13 Pro, iOS 15.4"
            }
        }
    }

# 好友操作模型 - Used by user_routes.py/manage_friends
class FriendAction(BaseModel):
    user_id: str
    friend_id: str
    action: str

# Google登入請求模型 - Used by user_routes.py/login_with_google
class GoogleLoginRequest(BaseModel):
    google_id: Optional[str] = None # Made Optional as per usage
    email: Optional[str] = None # Made Optional as per usage
    name: Optional[str] = None # Made Optional as per usage
    picture: Optional[str] = None # Made Optional as per usage
    login_type: str = "google"

    model_config = { # Changed from Config to model_config
        "json_schema_extra": {
            "example": {
                "google_id": "109554286477309922371",
                "email": "user@gmail.com",
                "name": "User Name",
                "picture": "https://lh3.googleusercontent.com/a/profile_picture",
                "login_type": "google"
            }
        }
    } # Add missing closing brace
