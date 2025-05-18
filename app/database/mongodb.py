import os
import asyncio # Added asyncio for motor
import time # time is still used for retry delays
from motor.motor_asyncio import AsyncIOMotorClient # Replaced MongoClient with AsyncIOMotorClient
from pymongo import ASCENDING # ASCENDING is still used for index creation
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# 從環境變量獲取MongoDB連接URL和資料庫名稱
DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://Volticar:REMOVED_PASSWORD@59.126.6.46:27017/?authSource=admin&ssl=false")
VOLTICAR_DB = os.getenv("VOLTICAR_DB", "Volticar")
CHARGE_STATION_DB = os.getenv("CHARGE_STATION_DB", "charge_station")

# 創建MongoDB客戶端和數據庫連接 - 添加重試機制
max_retries = 3
retry_delay = 3  # 秒

print(f"正在連接MongoDB: {DATABASE_URL.split('@')[-1]}")

client: AsyncIOMotorClient = None # Initialize client as None

async def connect_to_mongo():
    global client
    for retry in range(max_retries):
        try:
            # 使用 AsyncIOMotorClient
            client = AsyncIOMotorClient(DATABASE_URL, serverSelectionTimeoutMS=5000)
            
            # 執行簡單的ping命令檢查連接
            await client.admin.command('ping')
            server_info = await client.server_info()
            print(f"MongoDB連接成功! 伺服器版本: {server_info['version']}")
            return client # Return the client on successful connection
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            if retry < max_retries - 1:
                print(f"MongoDB連接失敗，嘗試 {retry + 1}/{max_retries}，等待 {retry_delay} 秒後重試... 錯誤: {str(e)}")
                await asyncio.sleep(retry_delay) # Use asyncio.sleep
            else:
                print(f"MongoDB連接失敗，達到最大重試次數 ({max_retries})。錯誤: {str(e)}")
                print("繼續執行，但資料庫功能將不可用...")
                client = None # Ensure client is None if connection fails
                return None # Return None on failure
        except Exception as e: # Catch any other potential errors during connection
            print(f"連接 MongoDB 時發生未預期錯誤: {e}")
            client = None
            return None
    return None # Should not be reached if logic is correct, but as a fallback

# 在事件循環中運行連接函數
# This part will be tricky as the script is executed globally.
# We might need to adjust how this is called or ensure an event loop is running.
# For now, let's define it and assume it's handled by FastAPI startup.

# 安全地創建索引的輔助函數 - Motor's collection objects have sync-like methods for management
async def safely_create_index(collection, field_name, unique=False, ascending=True):
    try:
        # 檢查索引是否已存在
        existing_indexes = await collection.index_information() # Use await
        index_name = f"{field_name}_1" if ascending else f"{field_name}_-1"
        
        if index_name in existing_indexes:
            print(f"  索引 {index_name} 已存在，跳過創建")
            return
        
        # 創建索引，如果是唯一索引，添加sparse=True避免null值問題
        direction = ASCENDING if ascending else -1
        if unique:
            await collection.create_index([(field_name, direction)], unique=True, sparse=True) # Use await
            print(f"  創建唯一索引(sparse): {index_name}")
        else:
            await collection.create_index([(field_name, direction)]) # Use await
            print(f"  創建索引: {index_name}")
    except Exception as e:
        print(f"  創建索引 {field_name} 時出錯: {str(e)}")

# 處理可能存在的重複null值問題，特別處理google_id
async def handle_null_duplicates(collection, field_name): # Make async
    try:
        # 計算指定字段為null的文檔數量
        null_count = await collection.count_documents({field_name: None}) # Use await
        
        if null_count > 1:
            print(f"  發現 {null_count} 個 {field_name} 為null的文檔，開始處理...")
            
            # 取得所有字段為null的文檔
            null_docs_cursor = collection.find({field_name: None}) # find returns a cursor
            null_docs = await null_docs_cursor.to_list(length=null_count) # Use await and to_list
            
            # 保留第一個文檔，為其餘文檔設置默認值以避免重複
            for i, doc in enumerate(null_docs[1:], 1):
                # 更新文檔，將字段設置為特殊值或刪除該字段
                await collection.update_one( # Use await
                    {"_id": doc["_id"]},
                    {"$unset": {field_name: ""}}  # 完全移除該字段
                )
                
            print(f"  成功處理 {len(null_docs) - 1} 個 {field_name} 為null的文檔")
    except Exception as e:
        print(f"  處理 {field_name} 的null值時出錯: {str(e)}")

# 遷移登入類型欄位的函數，為現有用戶添加login_type
async def migrate_login_type_field(collection): # Make async
    try:
        # 檢查有多少文檔沒有login_type欄位
        missing_login_type = await collection.count_documents({"login_type": {"$exists": False}}) # Use await
        
        if missing_login_type > 0:
            print(f"  發現 {missing_login_type} 個文檔沒有login_type欄位，開始遷移...")
            
            # 更新所有沒有login_type的文檔，判斷登入類型
            # 如果有google_id且不等於user_id，設為'google'，否則設為'normal'
            await collection.update_many( # Use await
                {
                    "login_type": {"$exists": False},
                    "google_id": {"$exists": True},
                    "$expr": {"$ne": ["$google_id", "$user_id"]}  # google_id不等於user_id時
                },
                {"$set": {"login_type": "google"}}
            )
            
            # 其他所有用戶設為normal類型，並將google_id設為user_id
            await collection.update_many( # Use await
                {"login_type": {"$exists": False}},
                {"$set": {"login_type": "normal"}}
            )
            
            # 檢查更新後還有多少文檔沒有login_type
            remaining = await collection.count_documents({"login_type": {"$exists": False}}) # Use await
            print(f"  ✓ 已為 {missing_login_type - remaining} 個文檔添加login_type欄位")
        
        # 檢查有多少文檔沒有google_id欄位
        missing_google_id = await collection.count_documents({"google_id": {"$exists": False}}) # Use await
        if missing_google_id > 0:
            print(f"  發現 {missing_google_id} 個文檔沒有google_id欄位，開始添加...")
            
            # 先創建欄位
            await collection.update_many( # Use await
                {"google_id": {"$exists": False}},
                {"$set": {"google_id": ""}}
            )

            # 對於一般用戶，將空的 google_id 設為 None
            update_result_none = await collection.update_many( # Use await
                {"google_id": "", "login_type": "normal"},
                {"$set": {"google_id": None}} # 將 google_id 設為 None
            )
            print(f"  ✓ 已將 {update_result_none.modified_count} 個一般用戶的空 google_id 設為 None")

            remaining = await collection.count_documents({"google_id": {"$exists": False}}) # Use await
            print(f"  ✓ 已為 {missing_google_id - remaining} 個文檔添加 google_id 欄位")

            # 檢查並處理 login_type 為 normal 但 google_id 等於 user_id 的舊數據
            old_logic_users = await collection.count_documents({ # Use await
                "login_type": "normal",
                "$expr": {"$eq": ["$google_id", "$user_id"]}
            })
            if old_logic_users > 0:
                print(f"  發現 {old_logic_users} 個一般用戶的 google_id 等於 user_id (舊邏輯)，開始修正...")
                fix_result = await collection.update_many( # Use await
                    {
                        "login_type": "normal",
                        "$expr": {"$eq": ["$google_id", "$user_id"]}
                    },
                    {"$set": {"google_id": None}} # 將 google_id 設為 None
                )
                print(f"  ✓ 已修正 {fix_result.modified_count} 個一般用戶的 google_id")

            # 檢查仍然是空字符串的 google_id (可能 login_type 不是 normal)
            # 這些可能是異常數據，暫時也設為 None
            empty_google_id = await collection.count_documents({"google_id": ""}) # Use await
            if empty_google_id > 0:
                 fix_empty_result = await collection.update_many( # Use await
                     {"google_id": ""},
                     {"$set": {"google_id": None}}
                 )
                 print(f"  ✓ 已將 {fix_empty_result.modified_count} 個剩餘的空 google_id 設為 None")
                
    except Exception as e:
        print(f"  遷移login_type欄位時出錯: {str(e)}")

# Global database and collection variables
volticar_db = None
charge_station_db = None
users_collection = None
login_records_collection = None
vehicles_collection = None
tasks_collection = None
achievements_collection = None
rewards_collection = None
pending_verifications_collection = None

async def initialize_db_and_collections():
    global client, volticar_db, charge_station_db, users_collection, login_records_collection
    global vehicles_collection, tasks_collection, achievements_collection, rewards_collection
    global pending_verifications_collection

    if client is None: # Ensure client is connected
        print("MongoDB client is not connected. Aborting initialization.")
        return

    try:
        # 獲取數據庫
        volticar_db = client[VOLTICAR_DB]
        charge_station_db = client[CHARGE_STATION_DB]
        
        # 獲取集合
        users_collection = volticar_db["Users"]
        login_records_collection = volticar_db["LoginRecords"]
        vehicles_collection = volticar_db["Vehicles"]
        tasks_collection = volticar_db["Tasks"]
        achievements_collection = volticar_db["Achievements"]
        rewards_collection = volticar_db["Rewards"]
        pending_verifications_collection = volticar_db["PendingVerifications"]
        
        # 遷移login_type欄位
        print("開始遷移login_type欄位...")
        await migrate_login_type_field(users_collection)
        
        # 先處理可能存在的null值重複問題
        print("檢查並處理可能的null值重複問題...")
        await handle_null_duplicates(users_collection, "phone")
        
        # 使用安全的索引創建方法
        print("正在檢查並創建所需的MongoDB索引...")
        
        # 用戶集合索引
        print("用戶集合索引:")
        await safely_create_index(users_collection, "user_id", unique=True)
        await safely_create_index(users_collection, "email", unique=True)
        await safely_create_index(users_collection, "username", unique=True)
        await safely_create_index(users_collection, "google_id", unique=True)
        await safely_create_index(users_collection, "login_type")

        # 登入記錄索引
        print("登入記錄索引:")
        await safely_create_index(login_records_collection, "user_id")
        await safely_create_index(login_records_collection, "login_timestamp")

        # 車輛索引
        print("車輛索引:")
        await safely_create_index(vehicles_collection, "vehicle_id", unique=True)
        await safely_create_index(vehicles_collection, "user_id")
        
        # 任務索引
        print("任務索引:")
        await safely_create_index(tasks_collection, "task_id", unique=True)
        
        # 成就索引
        print("成就索引:")
        await safely_create_index(achievements_collection, "achievement_id", unique=True)
        
        # 獎勵索引
        print("獎勵索引:")
        await safely_create_index(rewards_collection, "item_id", unique=True)

        # 待驗證集合索引
        print("待驗證集合索引:")
        await safely_create_index(pending_verifications_collection, "email")
        await safely_create_index(pending_verifications_collection, "token", unique=True)
        
        print("MongoDB索引檢查完成!")

    except Exception as e:
        print(f"設置數據庫、集合或執行索引/遷移時發生錯誤: {e}")
        # Reset collections to None if initialization fails
        volticar_db = None
        charge_station_db = None
        users_collection = None
        login_records_collection = None
        vehicles_collection = None
        tasks_collection = None
        achievements_collection = None
        rewards_collection = None
        pending_verifications_collection = None
        pass

# This block needs to be called within an async context, e.g., FastAPI startup event
# async def startup_db_client():
# global client
# client = await connect_to_mongo()
# if client:
# await initialize_db_and_collections()
# else:
# print("警告: 無法連接到MongoDB，API將在無數據庫模式下運行")

# async def shutdown_db_client():
# global client
# if client:
# client.close()
# print("MongoDB 連線已關閉")

# The global script execution makes direct async calls problematic here.
# These functions (startup_db_client, shutdown_db_client) should be registered
# with FastAPI's startup and shutdown events in main.py.

# 打印連接信息以便調試 - This will need to be async or called after connection
async def print_connection_info():
    if volticar_db is not None:
        print(f"已連接到數據庫: {VOLTICAR_DB}")
        collections = await volticar_db.list_collection_names() # Use await
        print(f"可用的集合: {', '.join(collections)}")
    if charge_station_db is not None:
        try:
            cities = await charge_station_db.list_collection_names() # Use await
            print(f"充電站數據庫中可用的城市: {', '.join(cities)}")
        except Exception as e:
            print(f"無法獲取充電站集合列表: {str(e)}")

# 由於charge_station是一個獨立的數據庫，我們需要基於城市名獲取對應的集合
async def get_charge_station_collection(city=None): # Make async
    """
    獲取充電站集合。如果指定了城市，返回該城市的集合；否則返回所有集合
    """
    if charge_station_db is None: # Check if db connection exists
        print("Charge station DB not initialized.")
        return [] if not city else None

    try:
        if city:
            return charge_station_db[city] # Collection access is sync
        else:
            # 獲取所有集合名
            return await charge_station_db.list_collection_names() # Use await
    except Exception as e:
        print(f"獲取充電站集合失敗: {str(e)}")
        # 返回空數組或空集合，避免應用崩潰
        return [] if not city else None

# To be called by FastAPI startup event
async def connect_and_initialize_db():
    global client
    client = await connect_to_mongo()
    if client:
        await initialize_db_and_collections()
        await print_connection_info() # Print info after successful initialization
    else:
        # Ensure all global collection variables are None if connection fails
        global volticar_db, charge_station_db, users_collection, login_records_collection
        global vehicles_collection, tasks_collection, achievements_collection, rewards_collection
        global pending_verifications_collection
        volticar_db = None
        charge_station_db = None
        users_collection = None
        login_records_collection = None
        vehicles_collection = None
        tasks_collection = None
        achievements_collection = None
        rewards_collection = None
        pending_verifications_collection = None
        print("警告: 無法連接到MongoDB，API將在無數據庫模式下運行")

# To be called by FastAPI shutdown event
async def close_mongo_connection():
    global client
    if client:
        client.close()
        print("MongoDB 連線已關閉")
