
import asyncio
from getpass import getpass
from app.database.mongodb import connect_and_initialize_db, client, VOLTICAR_DB
from app.utils.auth import get_password_hash

async def create_admin_user():
    """
    Command-line script to create an admin user in the database.
    """
    print("--- 建立 VoltiCar 後台管理員帳號 ---")
    
    # 提示輸入管理員資訊
    username = input("請輸入管理員帳號 (username): ").strip()
    password = getpass("請輸入管理員密碼 (password): ").strip()
    email = input("請輸入管理員電子郵件 (email): ").strip()

    if not all([username, password, email]):
        print("錯誤：帳號、密碼和電子郵件為必填欄位。")
        return

    # 連接並初始化資料庫
    await connect_and_initialize_db()
    
    db = client[VOLTICAR_DB]
    users_collection = db["Users"]
    admins_collection = db["admins"] # fastapi-admin's collection

    # 檢查使用者是否已存在
    existing_user = await users_collection.find_one({"$or": [{"username": username}, {"email": email}]})
    if existing_user:
        print(f"錯誤：使用者名稱 '{username}' 或電子郵件 '{email}' 已存在。")
        await client.close()
        return
        
    existing_admin = await admins_collection.find_one({"username": username})
    if existing_admin:
        print(f"錯誤：管理員帳號 '{username}' 已在 fastapi-admin 中存在。")
        await client.close()
        return

    # 加密密碼
    hashed_password = get_password_hash(password)

    # 準備管理員資料
    admin_user_data = {
        "email": email,
        "username": username,
        "hashed_password": hashed_password,
        "role": "admin", # 關鍵欄位
        "login_type": "normal",
        # 其他 User model 中的預設值會由 Pydantic 或資料庫處理
    }
    
    # 為了 fastapi-admin 的認證，我們也需要在其 'admins' collection 中建立一筆記錄
    fastapi_admin_data = {
        "username": username,
        "password": hashed_password, # fastapi-admin 也需要加密後的密碼
    }

    try:
        # 寫入 Users collection
        user_insert_result = await users_collection.insert_one(admin_user_data)
        print(f"成功在 'Users' 集合中建立管理員，ID: {user_insert_result.inserted_id}")

        # 寫入 admins collection
        admin_insert_result = await admins_collection.insert_one(fastapi_admin_data)
        print(f"成功在 'admins' 集合中建立管理員記錄，ID: {admin_insert_result.inserted_id}")
        
        print("\n管理員帳號建立成功！現在您可以使用此帳號登入 /admin 後台。")

    except Exception as e:
        print(f"建立管理員時發生錯誤: {e}")
    finally:
        # 關閉資料庫連接
        await client.close()

if __name__ == "__main__":
    asyncio.run(create_admin_user())
