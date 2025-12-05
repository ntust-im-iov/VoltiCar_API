import os
import ssl
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pydantic import EmailStr
from dotenv import load_dotenv

# 載入環境變數 (如果有的話)
load_dotenv()

# 從環境變數讀取 SMTP 設定
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587)) # 預設使用 587 (TLS)
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", SMTP_USER) # 預設寄件者為登入用戶

async def send_email_async(recipient_email: EmailStr, subject: str, html_content: str):
    """
    異步發送電子郵件

    Args:
        recipient_email: 收件者 Email 地址
        subject: 郵件主旨
        html_content: 郵件內容 (HTML 格式)
    """
    if not all([SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SENDER_EMAIL]):
        print("錯誤：SMTP 設定不完整，無法發送郵件。請檢查環境變數。")
        # 在實際應用中，這裡可能需要拋出異常或記錄錯誤
        # raise ValueError("SMTP configuration is incomplete.")
        return False # 暫時返回 False 表示失敗

    message = MIMEMultipart("alternative")
    message["From"] = SENDER_EMAIL
    message["To"] = recipient_email
    message["Subject"] = subject

    # 同時提供純文字和 HTML 版本 (可選，但建議)
    # text_part = MIMEText(f"Please view this email in an HTML-compatible client.\n\n{html_content}", "plain")
    html_part = MIMEText(html_content, "html")

    # message.attach(text_part)
    message.attach(html_part)

    try:
        # 根據端口決定連線方式
        use_ssl = SMTP_PORT == 465
        use_starttls = SMTP_PORT == 587 # 假設 587 使用 STARTTLS
        use_plain_smtp = SMTP_PORT == 25 # 假設 25 是非加密

        # 建立 SMTP 連線
        # 注意：aiosmtplib 的 use_tls 參數實際上控制是否在連接後立即啟動 TLS (類似 SSL)
        # 對於 STARTTLS (port 587)，我們需要先建立非加密連接，然後手動調用 starttls()
        # 對於 port 25，我們不需要 TLS 或 STARTTLS
        # 對於 port 25，我們不需要 TLS 或 STARTTLS
        # Revert use_tls to depend on use_ssl (True for port 465)

        # 為了處理開發環境中 host.docker.internal 的 SSL 憑證問題，
        # 我們建立一個自訂的 SSL context。
        tls_context = None
        if use_ssl or use_starttls:
            # 我們使用系統預設的信任 CA 庫來驗證伺服器憑證，
            # 但需要停用主機名稱驗證，因為我們是透過 'host.docker.internal' 連接，
            # 而憑證的 CN (Common Name) 是我們設定的 SSL_DOMAIN。
            ssl_domain = os.getenv("SSL_DOMAIN")
            if not ssl_domain:
                 print("警告: 未設定 SSL_DOMAIN 環境變數，SSL 驗證可能會失敗。")
            print(f"正在建立自訂 SSL Context 以進行伺服器驗證 (CN: {ssl_domain})...")
            tls_context = ssl.create_default_context()
            # 停用主機名稱驗證
            tls_context.check_hostname = False
            # 仍然要求驗證伺服器憑證，但使用系統的信任庫
            tls_context.verify_mode = ssl.CERT_REQUIRED
            print("SSL Context 建立完成：已停用主機名稱檢查，但會驗證憑證鏈。")


        async with aiosmtplib.SMTP(
            hostname=SMTP_HOST, 
            port=SMTP_PORT, 
            use_tls=use_ssl, 
            tls_context=tls_context
        ) as smtp:
            print(f"正在連接 SMTP 伺服器: {SMTP_HOST}:{SMTP_PORT} (SSL: {use_ssl}, STARTTLS: {use_starttls})")

            # 如果需要 STARTTLS (例如 port 587)
            if use_starttls:
                # 在某些伺服器上，可能需要先發送 EHLO
                # await smtp.ehlo() # 取消註解如果需要
                await smtp.starttls()
                print("已啟用 STARTTLS")
                # STARTTLS 後通常需要重新 EHLO
                # await smtp.ehlo() # 取消註解如果需要

            # 登入 SMTP 伺服器 (如果不是完全開放的 relay)
            # 對於 port 25 的本機連接，根據 hMailServer IP Ranges 設定，可能不需要登入
            # 但為了通用性，我們仍然嘗試登入
            if SMTP_USER and SMTP_PASSWORD:
                 await smtp.login(SMTP_USER, SMTP_PASSWORD)
                 print(f"已使用帳號 {SMTP_USER} 登入 SMTP")
            else:
                 print("警告：未提供 SMTP 使用者名稱或密碼，嘗試匿名發送。")


            # 發送郵件
            print(f"已使用帳號 {SMTP_USER} 登入 SMTP")

            # 發送郵件
            await smtp.send_message(message)
            print(f"郵件已成功發送至 {recipient_email}")
            return True

    except aiosmtplib.SMTPException as e:
        print(f"發送郵件至 {recipient_email} 時發生 SMTP 錯誤: {e}")
        # 可以在這裡加入更詳細的錯誤處理或重試邏輯
        return False
    except Exception as e:
        print(f"發送郵件時發生未知錯誤: {e}")
        return False

# --- 郵件內容模板 ---

def create_verification_email_content(email: str, verification_link: str) -> str: # 改為接收 email
    """建立帳號驗證郵件的 HTML 內容"""
    # 使用 email 或通用稱呼
    greeting_name = email # 或者 "使用者"
    # 郵件內容模板
    # 使用 email 或通用稱呼
    # 修改提示文字
    # 修改提示文字
    return f"""
    <html>
    <body>
        <p>您好 {greeting_name},</p>
        <p>歡迎使用 Volticar！請點擊以下連結來驗證您的電子郵件地址，以便完成註冊：</p>
        <p><a href="{verification_link}">驗證我的 Email</a></p>
        <p>如果您沒有請求註冊 Volticar，請忽略此郵件。</p>
        <p>謝謝,<br>Volticar 團隊</p>
    </body>
    </html>
    """

def create_password_reset_email_content(username: str, reset_link: str) -> str:
    """建立密碼重設郵件的 HTML 內容"""
    return f"""
    <html>
    <body>
        <p>您好 {username},</p>
        <p>我們收到了您的密碼重設請求。請點擊以下連結來設定您的新密碼：</p>
        <p><a href="{reset_link}">重設我的密碼</a></p>
        <p>這個連結將在 1 小時後失效。</p>
        <p>如果您沒有請求重設密碼，請忽略此郵件。</p>
        <p>謝謝,<br>Volticar 團隊</p>
    </body>
    </html>
    """

def create_password_reset_otp_email_content(username: str, otp_code: str) -> str:
    """建立包含 OTP 的密碼重設郵件 HTML 內容"""
    return f"""
    <html>
    <body>
        <p>您好 {username},</p>
        <p>我們收到了您的密碼重設請求。請在 APP 中輸入以下驗證碼來設定您的新密碼：</p>
        <p style="font-size: 24px; font-weight: bold; letter-spacing: 5px; margin: 20px 0;">{otp_code}</p>
        <p>這個驗證碼將在 10 分鐘後失效。</p>
        <p>如果您沒有請求重設密碼，請忽略此郵件。</p>
        <p>謝謝,<br>Volticar 團隊</p>
    </body>
    </html>
    """

def create_binding_otp_email_content(username_or_email: str, otp_code: str, binding_target_type: str) -> str:
    """建立包含 OTP 的綁定郵件 HTML 內容"""
    # binding_target_type 會是 "電子郵件" 或 "手機號碼" 之類的文字
    return f"""
    <html>
    <body>
        <p>您好 {username_or_email},</p>
        <p>我們收到了您綁定{binding_target_type}的請求。請在 APP 中輸入以下驗證碼來完成綁定：</p>
        <p style="font-size: 24px; font-weight: bold; letter-spacing: 5px; margin: 20px 0;">{otp_code}</p>
        <p>這個驗證碼將在 10 分鐘後失效。</p>
        <p>如果您沒有請求此操作，請忽略此郵件。</p>
        <p>謝謝,<br>Volticar 團隊</p>
    </body>
    </html>
    """

# --- 測試區塊 ---
if __name__ == "__main__":
    import asyncio

    # --- 請修改以下測試參數 ---
    TEST_RECIPIENT = "hancechin08@gmail.com" # 將此處改為您想測試接收的 Email 地址
    TEST_SUBJECT = "hMailServer 測試郵件"
    TEST_USERNAME = "測試使用者"
    # --- 測試參數結束 ---

    # 建立測試郵件內容 (使用驗證信模板)
    # 這裡的連結僅為示例
    verification_link_example = f"http://{SMTP_HOST}/verify?code=123456" # 實際應用中應產生真實連結
    # 傳遞 Email 給更新後的函數
    test_html_content = create_verification_email_content(TEST_RECIPIENT, verification_link_example)

    print(f"準備發送測試郵件至: {TEST_RECIPIENT}")
    print(f"使用設定: Host={SMTP_HOST}, Port={SMTP_PORT}, User={SMTP_USER}")

    # 執行異步發送
    async def main():
        success = await send_email_async(TEST_RECIPIENT, TEST_SUBJECT, test_html_content)
        if success:
            print("測試郵件發送請求完成。請檢查收件匣。")
        else:
            print("測試郵件發送失敗。請檢查 hMailServer 日誌和 .env 設定。")

    asyncio.run(main())
