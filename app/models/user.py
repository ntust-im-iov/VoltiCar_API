from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from bson import ObjectId

# --- PyObjectId Helper Type (Pydantic V1 compatible with schema modification) ---
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v): # Pydantic V1 signature
        if isinstance(v, ObjectId):
            return v
        if ObjectId.is_valid(v):
            return ObjectId(v)
        try:
            if isinstance(v, str) and ObjectId.is_valid(v):
                return ObjectId(v)
        except TypeError:
            pass
        raise ValueError(f"Not a valid ObjectId: {v}")

    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]):
        # Pydantic V1 method to modify the schema for this type
        # We want ObjectId to be represented as a string in the OpenAPI schema
        field_schema.update(type="string", example="60d5ec49e73e82f8e0e2f8b8")


# --- Game Session Setup ---
class CurrentGameSessionSetupItem(BaseModel):
    item_id: str 
    quantity: int
    class Config:
        from_attributes = True # Pydantic V1: orm_mode = True

class CurrentGameSessionSetup(BaseModel):
    selected_vehicle_id: Optional[str] = None
    selected_cargo: Optional[List[CurrentGameSessionSetupItem]] = None
    selected_destination_id: Optional[str] = None
    last_updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True

# --- User Model ---
class User(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True, description="Custom unique user ID (UUID string)")
    email: EmailStr
    username: str
    phone: Optional[str] = None
    hashed_password: Optional[str] = None
    google_id: Optional[str] = None
    login_type: str = "normal"
    
    experience_points: int = Field(default=0)
    level: int = Field(default=1)
    currency_balance: int = Field(default=0)
    current_game_session_setup: Optional[CurrentGameSessionSetup] = None
    active_game_session_id: Optional[str] = None

    reset_password_token: Optional[str] = None
    reset_password_token_expires_at: Optional[datetime] = None
    last_login_at: Optional[datetime] = None

    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    class Config:
        from_attributes = True
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: lambda o: str(o), 
            PyObjectId: lambda o: str(o) 
        }
        schema_extra = {
            "example": {
                "_id": "60d5ec49e73e82f8e0e2f8b8",
                "user_id": "uuid-generated-user-id",
                "email": "user@example.com",
                "username": "username",
            }
        }

# --- LoginRecord Model ---
class LoginRecord(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    login_record_id: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True, description="Custom unique login record ID (UUID string)")
    user_id: str 
    login_method: str
    ip_address: str
    device_info: str
    created_at: datetime = Field(default_factory=datetime.now)
    login_timestamp: datetime = Field(default_factory=datetime.now)

    class Config:
        from_attributes = True
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: lambda o: str(o), PyObjectId: lambda o: str(o)}
        schema_extra = {
            "example": {
                "_id": "60d5ec49e73e82f8e0e2f8b9",
                "login_record_id": "uuid-login-record-id",
                "user_id": "uuid-user-id",
                "login_method": "password",
            }
        }

# --- Request/Response Models ---
class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    login_type: str = "normal"

class UserLogin(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    password: str

class EmailVerificationRequest(BaseModel):
    email: EmailStr

class CompleteRegistrationRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    phone: Optional[str] = None

class BindRequest(BaseModel):
    type: str
    value: str

class VerifyBindingRequest(BaseModel):
    type: str
    value: str
    otp_code: str

class VehicleCreate(BaseModel):
    user_id: str 
    vehicle_definition_id: str 
    nickname: Optional[str] = None 

class VehicleUpdate(BaseModel): 
    nickname: Optional[str] = None

class FCMTokenUpdate(BaseModel):
    user_id: str 
    fcm_token: str
    device_info: Optional[str] = None
    class Config: 
        schema_extra = {
             "example": {
                "user_id": "uuid-user-id",
                "fcm_token": "fGDrT5XAQwetGg...",
                "device_info": "iPhone 13 Pro, iOS 15.4"
            }
        }

class FriendAction(BaseModel):
    user_id: str 
    friend_id: str 
    action: str

class GoogleLoginRequest(BaseModel):
    google_id: Optional[str] = None
    email: Optional[str] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    login_type: str = "google"
    class Config: 
        schema_extra = {
            "example": {
                "google_id": "109554286477309922371",
                "email": "user@gmail.com",
                "name": "User Name",
                "picture": "https://lh3.googleusercontent.com/a/profile_picture",
                "login_type": "google"
            }
        }
