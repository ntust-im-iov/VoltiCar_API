import os
import time
from pymongo import MongoClient, ASCENDING
from pymongo.errors import ConnectionFailure, DuplicateKeyError, ServerSelectionTimeoutError

# 從環境變量獲取MongoDB連接URL和資料庫名稱
DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://Volticar:REMOVED_PASSWORD@59.126.6.46:27017/?authSource=admin&ssl=false")
VOLTICAR_DB = os.getenv("VOLTICAR_DB", "Volticar")
CHARGE_STATION_DB = os.getenv("CHARGE_STATION_DB", "charge_station")

# 創建MongoDB客戶端和數據庫連接 - 添加重試機制
max_retries = 3
retry_delay = 3  # 秒

print(f"正在連接MongoDB: {DATABASE_URL.split('@')[-1]}")

# 重試連接邏輯
for retry in range(max_retries):
    try:
        # 最簡單的連接方式，不使用SSL/TLS
        client = MongoClient(DATABASE_URL, serverSelectionTimeoutMS=5000)
        
        # 執行簡單的ping命令檢查連接
        client.admin.command('ping')
        print(f"MongoDB連接成功! 伺服器版本: {client.server_info()['version']}")
        break
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        if retry < max_retries - 1:
            print(f"MongoDB連接失敗，嘗試 {retry + 1}/{max_retries}，等待 {retry_delay} 秒後重試... 錯誤: {str(e)}")
            time.sleep(retry_delay)
        else:
            print(f"MongoDB連接失敗，達到最大重試次數 ({max_retries})。錯誤: {str(e)}")
            print("繼續執行，但資料庫功能將不可用...")
            # 使用空的客戶端，讓程序能夠啟動但資料庫功能不可用
            client = None

# 安全地創建索引的輔助函數
def safely_create_index(collection, field_name, unique=False, ascending=True):
    try:
        # 檢查索引是否已存在
        existing_indexes = collection.index_information()
        index_name = f"{field_name}_1" if ascending else f"{field_name}_-1"
        
        if index_name in existing_indexes:
            print(f"  索引 {index_name} 已存在，跳過創建")
            return
        
        # 創建索引，如果是唯一索引，添加sparse=True避免null值問題
        direction = ASCENDING if ascending else -1
        if unique:
            collection.create_index([(field_name, direction)], unique=True, sparse=True)
            print(f"  創建唯一索引(sparse): {index_name}")
        else:
            collection.create_index([(field_name, direction)])
            print(f"  創建索引: {index_name}")
    except Exception as e:
        print(f"  創建索引 {field_name} 時出錯: {str(e)}")

# 處理可能存在的重複null值問題，特別處理google_id
def handle_null_duplicates(collection, field_name):
    try:
        # 計算指定字段為null的文檔數量
        null_count = collection.count_documents({field_name: None})
        
        if null_count > 1:
            print(f"  發現 {null_count} 個 {field_name} 為null的文檔，開始處理...")
            
            # 取得所有字段為null的文檔
            null_docs = list(collection.find({field_name: None}))
            
            # 保留第一個文檔，為其餘文檔設置默認值以避免重複
            for i, doc in enumerate(null_docs[1:], 1):
                # 更新文檔，將字段設置為特殊值或刪除該字段
                collection.update_one(
                    {"_id": doc["_id"]},
                    {"$unset": {field_name: ""}}  # 完全移除該字段
                )
                
            print(f"  成功處理 {len(null_docs) - 1} 個 {field_name} 為null的文檔")
    except Exception as e:
        print(f"  處理 {field_name} 的null值時出錯: {str(e)}")

# 遷移登入類型欄位的函數，為現有用戶添加login_type
def migrate_login_type_field(collection):
    try:
        # 檢查有多少文檔沒有login_type欄位
        missing_login_type = collection.count_documents({"login_type": {"$exists": False}})
        
        if missing_login_type > 0:
            print(f"  發現 {missing_login_type} 個文檔沒有login_type欄位，開始遷移...")
            
            # 更新所有沒有login_type的文檔，判斷登入類型
            # 如果有google_id且不等於user_id，設為'google'，否則設為'normal'
            collection.update_many(
                {
                    "login_type": {"$exists": False},
                    "google_id": {"$exists": True},
                    "$expr": {"$ne": ["$google_id", "$user_id"]}  # google_id不等於user_id時
                },
                {"$set": {"login_type": "google"}}
            )
            
            # 其他所有用戶設為normal類型，並將google_id設為user_id
            collection.update_many(
                {"login_type": {"$exists": False}},
                {"$set": {"login_type": "normal"}}
            )
            
            # 檢查更新後還有多少文檔沒有login_type
            remaining = collection.count_documents({"login_type": {"$exists": False}})
            print(f"  ✓ 已為 {missing_login_type - remaining} 個文檔添加login_type欄位")
        
        # 檢查有多少文檔沒有google_id欄位
        missing_google_id = collection.count_documents({"google_id": {"$exists": False}})
        if missing_google_id > 0:
            print(f"  發現 {missing_google_id} 個文檔沒有google_id欄位，開始添加...")
            
            # 先創建欄位
            collection.update_many(
                {"google_id": {"$exists": False}},
                {"$set": {"google_id": ""}}
            )
            
            # 對於一般用戶，設置google_id為user_id
            collection.update_many(
                {"google_id": "", "login_type": "normal"},
                [{"$set": {"google_id": "$user_id"}}]
            )
            
            remaining = collection.count_documents({"google_id": {"$exists": False}})
            print(f"  ✓ 已為 {missing_google_id - remaining} 個文檔添加google_id欄位")
            
            # 檢查空字符串的google_id
            empty_google_id = collection.count_documents({"google_id": ""})
            if empty_google_id > 0:
                collection.update_many(
                    {"google_id": ""},
                    [{"$set": {"google_id": "$user_id"}}]
                )
                print(f"  ✓ 已修復 {empty_google_id} 個空的google_id")
                
    except Exception as e:
        print(f"  遷移login_type欄位時出錯: {str(e)}")

# 如果連接成功，設置數據庫和集合
if client is not None:
    try:
        # 獲取數據庫
        volticar_db = client[VOLTICAR_DB]
        charge_station_db = client[CHARGE_STATION_DB]
        
        # 獲取集合
        users_collection = volticar_db["Users"]
        login_records_collection = volticar_db["LoginRecords"]
        otp_records_collection = volticar_db["OTPRecords"]
        stations_collection = charge_station_db["Stations"]
        vehicles_collection = volticar_db["Vehicles"]
        tasks_collection = volticar_db["Tasks"]
        achievements_collection = volticar_db["Achievements"]
        rewards_collection = volticar_db["Rewards"]
        
        # 遷移login_type欄位
        print("開始遷移login_type欄位...")
        migrate_login_type_field(users_collection)
        
        # 先處理可能存在的null值重複問題
        print("檢查並處理可能的null值重複問題...")
        handle_null_duplicates(users_collection, "phone")
        
        # 使用安全的索引創建方法
        print("正在檢查並創建所需的MongoDB索引...")
        
        # 用戶集合索引
        print("用戶集合索引:")
        safely_create_index(users_collection, "user_id", unique=True)
        safely_create_index(users_collection, "email", unique=True)
        safely_create_index(users_collection, "username", unique=True)
        safely_create_index(users_collection, "phone", unique=True)
        safely_create_index(users_collection, "google_id", unique=True)  # google_id使用一般的唯一索引
        safely_create_index(users_collection, "login_type")  # 添加login_type索引
        
        # 登入記錄索引
        print("登入記錄索引:")
        safely_create_index(login_records_collection, "user_id")
        safely_create_index(login_records_collection, "login_timestamp")
        
        # OTP記錄索引
        print("OTP記錄索引:")
        safely_create_index(otp_records_collection, "user_id")
        safely_create_index(otp_records_collection, "expires_at")
        
        # 車輛索引
        print("車輛索引:")
        safely_create_index(vehicles_collection, "vehicle_id", unique=True)
        safely_create_index(vehicles_collection, "user_id")
        
        # 任務索引
        print("任務索引:")
        safely_create_index(tasks_collection, "task_id", unique=True)
        
        # 成就索引
        print("成就索引:")
        safely_create_index(achievements_collection, "achievement_id", unique=True)
        
        # 獎勵索引
        print("獎勵索引:")
        safely_create_index(rewards_collection, "item_id", unique=True)
        
        print("MongoDB索引檢查完成!")
    
    except Exception as e:
        print(f"設置數據庫及集合時發生錯誤: {e}")
        # 如果出現錯誤，創建空對象以免引發屬性錯誤
        volticar_db = None
        charge_station_db = None
        users_collection = None
        login_records_collection = None
        otp_records_collection = None
        stations_collection = None
        vehicles_collection = None
        tasks_collection = None
        achievements_collection = None
        rewards_collection = None
else:
    # 連接失敗時，創建空對象以免引發屬性錯誤
    volticar_db = None
    charge_station_db = None
    users_collection = None
    login_records_collection = None
    otp_records_collection = None
    stations_collection = None
    vehicles_collection = None
    tasks_collection = None
    achievements_collection = None
    rewards_collection = None
    
    print("警告: 無法連接到MongoDB，API將在無數據庫模式下運行")

# 打印連接信息以便調試
if volticar_db is not None:
    print(f"已連接到數據庫: {VOLTICAR_DB}")
    print(f"可用的集合: {', '.join(volticar_db.list_collection_names())}")
if charge_station_db is not None:
    try:
        cities = charge_station_db.list_collection_names()
        print(f"充電站數據庫中可用的城市: {', '.join(cities)}")
    except Exception as e:
        print(f"無法獲取充電站集合列表: {str(e)}")

# 由於charge_station是一個獨立的數據庫，我們需要基於城市名獲取對應的集合
def get_charge_station_collection(city=None):
    """
    獲取充電站集合。如果指定了城市，返回該城市的集合；否則返回所有集合
    """
    try:
        if city:
            return charge_station_db[city]
        else:
            # 獲取所有集合名
            return charge_station_db.list_collection_names()
    except Exception as e:
        print(f"獲取充電站集合失敗: {str(e)}")
        # 返回空數組或空集合，避免應用崩潰
        return [] if not city else None 