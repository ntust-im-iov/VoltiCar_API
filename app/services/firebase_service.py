"""
Firebase雲端訊息服務(FCM)用於發送推播通知給用戶
"""

import os
from typing import Dict, Any, Optional, Union
from fastapi import HTTPException

# Firebase Admin SDK - 需要先安裝: pip install firebase-admin
try:
    import firebase_admin
    from firebase_admin import credentials, messaging
except ImportError:
    # 在不需要FCM功能時可以忽略此導入錯誤
    pass

# Firebase初始化代碼
def initialize_firebase():
    """初始化Firebase Admin SDK"""
    if 'firebase_admin' not in globals():
        print("Firebase Admin SDK未安裝，FCM功能將不可用")
        return False
        
    if not firebase_admin._apps:
        # 檢查環境變數中是否有Firebase服務帳號金鑰
        cred_json = os.environ.get('FIREBASE_CREDENTIALS')
        cred_path = os.environ.get('FIREBASE_CREDENTIALS_PATH')
        
        try:
            if cred_json:
                # 從環境變數讀取認證信息
                cred = credentials.Certificate(cred_json)
            elif cred_path and os.path.exists(cred_path):
                # 從文件讀取認證信息
                cred = credentials.Certificate(cred_path)
            else:
                print("未找到Firebase認證信息，FCM功能將不可用")
                return False
                
            firebase_admin.initialize_app(cred)
            print("Firebase初始化成功")
            return True
        except Exception as e:
            print(f"Firebase初始化失敗: {str(e)}")
            return False
    return True

# 發送FCM通知
async def send_fcm_message(
    token: str, 
    title: str, 
    body: str, 
    data: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    發送Firebase雲端訊息(FCM)給特定設備
    
    參數:
        token: 用戶設備的FCM令牌
        title: 通知標題
        body: 通知內容
        data: 附加數據 (可選)
        
    返回:
        Dict: 包含發送狀態和訊息ID的字典
    """
    if not initialize_firebase():
        raise HTTPException(status_code=500, detail="FCM服務未啟用")
    
    # 創建消息
    message = messaging.Message(
        notification=messaging.Notification(
            title=title,
            body=body,
        ),
        data=data or {},
        token=token,
    )
    
    try:
        # 發送消息
        response = messaging.send(message)
        return {
            "success": True,
            "message_id": response,
            "message": "通知已成功發送"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "發送通知失敗"
        }

# 發送驗證碼通知
async def send_verification_code_notification(
    token: str, 
    code: str, 
    expires_in_minutes: int = 10
) -> Dict[str, Any]:
    """
    發送驗證碼通知給用戶
    
    參數:
        token: 用戶設備的FCM令牌
        code: 驗證碼
        expires_in_minutes: 驗證碼有效時間(分鐘)
        
    返回:
        Dict: 包含發送狀態和訊息ID的字典
    """
    title = "Volticar 驗證碼"
    body = f"您的驗證碼是: {code}，有效期{expires_in_minutes}分鐘"
    data = {
        "type": "verification_code",
        "code": code,
        "expires_in_minutes": str(expires_in_minutes)
    }
    
    return await send_fcm_message(token, title, body, data) 