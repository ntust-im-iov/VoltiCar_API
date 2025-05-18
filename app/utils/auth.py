from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Optional, Dict, Any
# from app.database.mongodb import users_collection # Remove direct import
from app.database import mongodb as db_provider # Import the module itself
import os

# 安全密鑰配置
SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24小時

# 密碼加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2認證 - 更新 tokenUrl 指向實際的登入端點
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/users/login") # Changed tokenUrl

# 驗證密碼
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# 生成密碼哈希
def get_password_hash(password):
    return pwd_context.hash(password)

# 根據郵箱獲取用戶
async def get_user_by_email(email: str) -> Dict[str, Any]: # async
    if db_provider.users_collection is None:
        # Or handle this error more gracefully depending on application needs
        raise HTTPException(status_code=503, detail="用戶資料庫服務未初始化 (auth)")
    user = await db_provider.users_collection.find_one({"email": email}) # await
    if user:
        user["_id"] = str(user["_id"])
        return user
    return None

# 根據用戶名獲取用戶
async def get_user_by_username(username: str) -> Dict[str, Any]: # async
    if db_provider.users_collection is None:
        raise HTTPException(status_code=503, detail="用戶資料庫服務未初始化 (auth)")
    user = await db_provider.users_collection.find_one({"username": username}) # await
    if user:
        user["_id"] = str(user["_id"])
        return user
    return None

# 根據用戶ID獲取用戶
async def get_user_by_id(user_id: str) -> Dict[str, Any]: # async
    if db_provider.users_collection is None:
        # This function is critical for get_current_user, so an uninitialized DB is a major issue.
        # Raising 503 might be too aggressive if called outside request context,
        # but in get_current_user context, it's a server-side problem.
        print("CRITICAL: users_collection is None in get_user_by_id") # Add logging
        return None # Or raise an appropriate exception if this function can be called early
    user = await db_provider.users_collection.find_one({"user_id": user_id}) # await
    if user:
        user["_id"] = str(user["_id"])
        return user
    return None

# 根據手機號獲取用戶
async def get_user_by_phone(phone: str) -> Dict[str, Any]: # async
    if db_provider.users_collection is None:
        raise HTTPException(status_code=503, detail="用戶資料庫服務未初始化 (auth)")
    user = await db_provider.users_collection.find_one({"phone": phone}) # await
    if user:
        user["_id"] = str(user["_id"])
        return user
    return None

# 驗證用戶
def authenticate_user(user: Dict[str, Any], password: str, password_field: str = "password_hash") -> bool:
    if not user:
        return False
    if not verify_password(password, user[password_field]):
        return False
    return True

# 創建訪問令牌
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

from app.models.user import User as UserModel # Import User Pydantic model

# 獲取當前用戶 (基於 JWT)
async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserModel: # Changed return type to UserModel
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="無法驗證憑證",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # 解碼 JWT 令牌
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # 從 payload 中獲取用戶標識符 (假設存儲在 'sub' 欄位)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        # 如果解碼失敗或令牌無效
        raise credentials_exception

    # 使用 user_id 從數據庫獲取用戶
    user_dict = await get_user_by_id(user_id) # await, returns a dict
    if user_dict is None:
        # 如果找不到用戶
        raise credentials_exception
    
    # 將字典轉換為 User Pydantic 模型實例
    try:
        # Pydantic V1 style: User(**user_dict)
        # Pydantic V2 style: User.model_validate(user_dict)
        # Assuming Pydantic V1 for now.
        # The User model uses ObjectIdStr for 'id', which should handle conversion from str(ObjectId).
        # get_user_by_id already converts _id to str and assigns to "id" if alias is not used,
        # or directly to "_id" if alias is used.
        # User model has `id: Optional[ObjectIdStr] = Field(default=None, alias="_id")`
        # So, if user_dict has "_id": "some_string_oid", it should map to user_model.id
        
        # Ensure that the dictionary passed to UserModel has keys that match the model fields
        # or aliases. get_user_by_id returns a dict where _id is already str(ObjectId).
        # If 'id' is not in user_dict but '_id' is, Pydantic's alias should handle it.
        # If user_dict['_id'] is an ObjectId object, ObjectIdStr should handle it.
        # get_user_by_id returns: user["_id"] = str(user["_id"])
        # So user_dict will have {"_id": "string_oid", ...}
        # The User model has `id: Optional[ObjectIdStr] = Field(default=None, alias="_id")`
        # This means Pydantic will look for "_id" in the input dict and assign its value to `id` field.
        # The ObjectIdStr validator will then process this string.
        user_model = UserModel(**user_dict)
        return user_model
    except Exception as e: # Catch Pydantic ValidationError or other conversion errors
        # Log the detailed error for debugging
        # import traceback
        # print(f"Error converting user_dict to UserModel in get_current_user: {e}\n{traceback.format_exc()}")
        # For the client, just return the standard credentials exception
        raise credentials_exception

# 備註：原來的 Firebase 驗證邏輯已被移除
# async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
#     try:
#         user = verify_firebase_id_token(token) # This function is not defined
#         if not user:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="無效的 Firebase ID Token",
#                 headers={"WWW-Authenticate": "Bearer"},
#             )
#         if not user.get("email_verified"):
#             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email 未驗證")
#         return user
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail=f"Firebase ID Token 驗證失敗: {str(e)}",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
