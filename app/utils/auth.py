from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Optional, Dict, Any
from app.database.mongodb import users_collection
import os

# 安全密鑰配置
SECRET_KEY = os.getenv("SECRET_KEY", "REMOVED_SECRET_KEY")
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
def get_user_by_email(email: str) -> Dict[str, Any]:
    user = users_collection.find_one({"email": email})
    if user:
        user["_id"] = str(user["_id"])
        return user
    return None

# 根據用戶名獲取用戶
def get_user_by_username(username: str) -> Dict[str, Any]:
    user = users_collection.find_one({"username": username})
    if user:
        user["_id"] = str(user["_id"])
        return user
    return None

# 根據用戶ID獲取用戶
def get_user_by_id(user_id: str) -> Dict[str, Any]:
    user = users_collection.find_one({"user_id": user_id})
    if user:
        user["_id"] = str(user["_id"])
        return user
    return None

# 根據手機號獲取用戶
def get_user_by_phone(phone: str) -> Dict[str, Any]:
    user = users_collection.find_one({"phone": phone})
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

# 獲取當前用戶 (基於 JWT)
async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict[str, Any]:
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
    user = get_user_by_id(user_id)
    if user is None:
        # 如果找不到用戶
        raise credentials_exception
    # 返回用戶數據字典
    return user

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
