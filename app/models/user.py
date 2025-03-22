from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import datetime

# 充電記錄模型
class ChargingRecord(BaseModel):
    station_id: str
    station_name: str
    charging_time: int
    timestamp: Optional[datetime.datetime] = None

# 用戶基礎模型
class UserBase(BaseModel):
    user_id: str
    username: str
    email: str

# 創建用戶請求模型
class UserCreate(UserBase):
    password: str

# 登錄請求模型
class UserLogin(BaseModel):
    email: str
    password: str

# 數據庫存儲的用戶模型
class UserInDB(UserBase):
    password: str
    carbon_credits: int = 0
    charging_history: List[dict] = []

# 響應中的用戶模型
class User(UserBase):
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