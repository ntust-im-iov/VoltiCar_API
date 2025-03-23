from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import datetime
from bson import ObjectId

# 用戶模型 (Users 集合)
class User(BaseModel):
    id: Optional[str] = None  # ObjectId 作為主鍵
    user_id: str  # 使用者唯一識別碼 (由MongoDB自動生成)
    email: EmailStr  # 使用者電子信箱 (唯一)
    username: str  # 使用者名稱 (唯一)
    phone: Optional[str] = None  # 使用者電話號碼 (唯一，可選)
    password_hash: str  # 使用者密碼雜湊
    google_id: Optional[str] = None  # 若使用Google登入，儲存Google ID
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)  # 註冊時間
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.now)  # 更新時間

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "email": "user@example.com",
                "username": "username",
                "phone": "0912345678",
                "password_hash": "hashed_password",
                "google_id": "google123456789"
            }
        }
    }

# 登入記錄模型 (LoginRecords 集合)
class LoginRecord(BaseModel):
    id: Optional[str] = None  # ObjectId 作為主鍵
    user_id: str  # 關聯到Users集合的user_id
    login_method: str  # 登入方式 (帳號密碼/Google等)
    ip_address: str  # 使用者登入IP位址
    device_info: str  # 裝置資訊 (如瀏覽器+手機型號)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)  # 創建時間
    login_timestamp: datetime.datetime = Field(default_factory=datetime.datetime.now)  # 登入時間戳

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

# OTP驗證碼模型 (OTPRecords 集合)
class OTPRecord(BaseModel):
    id: Optional[str] = None  # ObjectId 作為主鍵
    user_id: str  # 關聯到Users集合的user_id
    otp_code: str  # 產生的OTP驗證碼 (加密存儲)
    expires_at: datetime.datetime  # 驗證碼過期時間
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)  # 產生時間

    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "user_id": "user123",
                "otp_code": "123456",
                "expires_at": "2023-03-23T10:20:30Z"
            }
        }
    }

# 創建用戶請求模型
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    phone: str

# 登錄請求模型
class UserLogin(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: str

# 令牌模型
class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str

# OTP請求模型
class OTPRequest(BaseModel):
    phone: str
    
# OTP驗證模型
class OTPVerification(BaseModel):
    phone: str
    otp_code: str

# 車輛基本模型
class VehicleBase(BaseModel):
    vehicle_id: str

# 車輛創建模型
class VehicleCreate(BaseModel):
    vehicle_id: str
    user_id: str
    vehicle_name: Optional[str] = None

# 車輛更新模型
class VehicleUpdate(BaseModel):
    vehicle_name: Optional[str] = None
    mileage: Optional[int] = None

# 任務模型
class Task(BaseModel):
    task_id: str
    description: str
    progress: int = 0
    reward: Dict[str, Any] = {}

# 成就模型
class Achievement(BaseModel):
    achievement_id: str
    description: str
    progress: int = 0
    unlocked: bool = False

# 排行榜項目模型
class LeaderboardItem(BaseModel):
    user_id: str
    score: int

# 獎勵項目模型
class RewardItem(BaseModel):
    item_id: str
    name: str
    description: Optional[str] = None
    price: int = 0

# 物品庫模型
class Inventory(BaseModel):
    owned_items: List[Dict[str, Any]] = []

# FCM令牌更新模型
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

# 好友操作模型
class FriendAction(BaseModel):
    user_id: str
    friend_id: str
    action: str  # "add" 或 "remove"

# 充電站模型
class Station(BaseModel):
    station_id: str
    name: str
    address: str
    city: str
    latitude: float
    longitude: float
    available: bool = True
    distance: Optional[float] = None

# 數據庫存儲的用戶模型
class UserInDB(UserCreate):
    user_id: str
    password_hash: str
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.now) 