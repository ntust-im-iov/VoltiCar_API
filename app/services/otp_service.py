import os
from twilio.rest import Client
from typing import Tuple

# 初始化 Twilio 客戶端
account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
twilio_client = Client(account_sid, auth_token)
twilio_phone_number = os.getenv("TWILIO_PHONE_NUMBER")

async def send_otp(phone_number: str) -> Tuple[bool, str]:
    """發送 SMS OTP 驗證碼"""
    try:
        verification = twilio_client.verify \
            .v2 \
            .services(os.getenv("TWILIO_VERIFY_SID")) \
            .verifications \
            .create(to=phone_number, channel='sms')
        return True, verification.sid
    except Exception as e:
        return False, str(e)

async def verify_otp(phone_number: str, code: str) -> Tuple[bool, str]:
    """驗證 OTP 驗證碼"""
    try:
        verification_check = twilio_client.verify \
            .v2 \
            .services(os.getenv("TWILIO_VERIFY_SID")) \
            .verification_checks \
            .create(to=phone_number, code=code)
        return verification_check.status == 'approved', verification_check.status
    except Exception as e:
        return False, str(e)
