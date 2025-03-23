from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import datetime

# 充電記錄模型
class ChargingRecord(BaseModel):
    station_id: str
    station_name: str
    charging_time: int
    timestamp: Optional[datetime.datetime] = None

# 用戶基礎模型
class UserBase(BaseModel):
    username: str
    email: str
    phone: Optional[str] = None

# 創建用戶請求模型
class UserCreate(BaseModel):
    account: str 
    email: str
    password: str
    phone: str
    name: str
    user_uuid: Optional[str] = None

# 登錄請求模型
class UserLogin(BaseModel):
    account: Optional[str] = None
    email: Optional[str] = None
    password: str

# 數據庫存儲的用戶模型
class UserInDB(BaseModel):
    user_id: str
    username: str
    email: str
    password: str
    phone: Optional[str] = None
    carbon_credits: int = 0
    charging_history: List[dict] = []

# 響應中的用戶模型
class User(BaseModel):
    user_id: str
    username: str
    email: str
    phone: Optional[str] = None
    carbon_credits: int = 0
    charging_history: List[dict] = []

    model_config = {
        "from_attributes": True
    }

# 令牌模型
class Token(BaseModel):
    access_token: str
    token_type: str

# 充電請求模型
class ChargingRequest(BaseModel):
    station_id: str
    charging_time: int
    carbon_credits_earned: Optional[int] = 5

# 車輛基礎模型
class VehicleBase(BaseModel):
    vehicle_id: str
    vehicle_name: Optional[str] = None
    battery_level: Optional[int] = None
    battery_health: Optional[int] = None
    mileage: Optional[int] = None

# 車輛創建模型
class VehicleCreate(BaseModel):
    vehicle_id: str
    user_uuid: str

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
    user_uuid: str
    score: int

# 獎勵項目模型
class RewardItem(BaseModel):
    item_id: str
    name: str
    description: Optional[str] = None
    price: int = 0

# 用戶物品庫模型
class Inventory(BaseModel):
    owned_items: List[str] = []

# 充電站模型
class Station(BaseModel):
    station_id: str
    name: str
    location: Dict[str, float]
    distance: Optional[float] = None
    availability: bool = True

# 驗證碼模型
class VerifyCode(BaseModel):
    phone: str
    code: str

# 驗證碼請求模型
class VerifyCodeRequest(BaseModel):
    phone: str

# 手機驗證模型
class PhoneVerification(BaseModel):
    phone: str
    verify_code: str

# 好友操作模型
class FriendAction(BaseModel):
    user_uuid: str
    friend_uuid: str
    action: str  # "add" 或 "remove" 