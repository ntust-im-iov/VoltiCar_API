from pymongo import MongoClient
import os
import time
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# 數據庫連接信息
DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://Volticar:RJW1128@59.126.6.46:27017/?authSource=admin")
VOLTICAR_DB = os.getenv("VOLTICAR_DB", "Volticar")
CHARGE_STATION_DB = os.getenv("CHARGE_STATION_DB", "charge_station")

# 創建MongoDB客戶端和數據庫連接 - 添加重試機制
max_retries = 5
retry_delay = 5  # 秒

for retry in range(max_retries):
    try:
        client = MongoClient(DATABASE_URL, serverSelectionTimeoutMS=10000)
        # 驗證連接
        client.admin.command('ping')
        print(f"MongoDB連接成功！URL: {DATABASE_URL.split('@')[1]}")
        break
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        if retry < max_retries - 1:
            print(f"MongoDB連接失敗，{retry + 1}/{max_retries}次嘗試，等待{retry_delay}秒後重試... 錯誤: {str(e)}")
            time.sleep(retry_delay)
        else:
            print(f"MongoDB連接失敗，已達到最大重試次數 ({max_retries})。請檢查MongoDB服務是否可用。")
            # 使用一個默認客戶端，這樣程序可以啟動但功能受限
            client = MongoClient()

# 獲取數據庫
volticar_db = client[VOLTICAR_DB]
charge_station_db = client[CHARGE_STATION_DB]

# 打印連接信息以便調試
print(f"已連接到數據庫: {VOLTICAR_DB} 和 {CHARGE_STATION_DB}")
print(f"可用的集合: {', '.join(volticar_db.list_collection_names())}")
try:
    print(f"充電站數據庫中可用的城市: {', '.join(charge_station_db.list_collection_names())}")
except Exception as e:
    print(f"無法獲取充電站集合列表: {str(e)}")

# 定義集合
users_collection = volticar_db["Users"]

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