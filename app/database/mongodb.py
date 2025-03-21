from pymongo import MongoClient
import os
import time
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

# 数据库连接信息
DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://Volticar:REMOVED_PASSWORD@59.126.6.46:27017/?authSource=admin")
VOLTICAR_DB = os.getenv("VOLTICAR_DB", "Volticar")
CHARGE_STATION_DB = os.getenv("CHARGE_STATION_DB", "charge_station")

# 创建MongoDB客户端和数据库连接 - 添加重试机制
max_retries = 5
retry_delay = 5  # 秒

for retry in range(max_retries):
    try:
        client = MongoClient(DATABASE_URL, serverSelectionTimeoutMS=10000)
        # 验证连接
        client.admin.command('ping')
        print(f"MongoDB连接成功！URL: {DATABASE_URL.split('@')[1]}")
        break
    except (ConnectionFailure, ServerSelectionTimeoutError) as e:
        if retry < max_retries - 1:
            print(f"MongoDB连接失败，{retry + 1}/{max_retries}次尝试，等待{retry_delay}秒后重试... 错误: {str(e)}")
            time.sleep(retry_delay)
        else:
            print(f"MongoDB连接失败，已达到最大重试次数 ({max_retries})。请检查MongoDB服务是否可用。")
            # 使用一个默认客户端，这样程序可以启动但功能受限
            client = MongoClient()

# 获取数据库
volticar_db = client[VOLTICAR_DB]
charge_station_db = client[CHARGE_STATION_DB]

# 打印连接信息以便调试
print(f"已连接到数据库: {VOLTICAR_DB} 和 {CHARGE_STATION_DB}")
print(f"可用的集合: {', '.join(volticar_db.list_collection_names())}")
try:
    print(f"充电站数据库中可用的城市: {', '.join(charge_station_db.list_collection_names())}")
except Exception as e:
    print(f"无法获取充电站集合列表: {str(e)}")

# 定义集合
users_collection = volticar_db["Users"]

# 由于charge_station是一个独立的数据库，我们需要基于城市名获取对应的集合
def get_charge_station_collection(city=None):
    """
    获取充电站集合。如果指定了城市，返回该城市的集合；否则返回所有集合
    """
    try:
        if city:
            return charge_station_db[city]
        else:
            # 获取所有集合名
            return charge_station_db.list_collection_names()
    except Exception as e:
        print(f"获取充电站集合失败: {str(e)}")
        # 返回空数组或空集合，避免应用崩溃
        return [] if not city else None 