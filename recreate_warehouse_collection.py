import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING
from pymongo.errors import CollectionInvalid
import os
from dotenv import load_dotenv

# --- 環境變數設定 ---
# 載入 .env 檔案中的環境變數
load_dotenv()

# 從環境變數讀取 MongoDB 連線字串
# 優先使用 DATABASE_URL，如果不存在則回退到 MONGO_CONNECTION_STRING
CONNECTION_STRING = os.getenv("DATABASE_URL") or os.getenv("MONGO_CONNECTION_STRING")
DB_NAME = "Volticar"
COLLECTION_NAME = "PlayerWarehouseItems"

async def main():
    """
    主函數，用於重新創建 PlayerWarehouseItems 集合及其索引。
    """
    if not CONNECTION_STRING:
        print("錯誤: 找不到 DATABASE_URL 或 MONGO_CONNECTION_STRING 環境變數。")
        print("請確保您的 .env 檔案中已設定正確的資料庫連線字串。")
        return

    print(f"正在使用提供的連線字串連接到 MongoDB...")
    client = AsyncIOMotorClient(CONNECTION_STRING)
    db = client[DB_NAME]
    print(f"成功連接到資料庫: '{DB_NAME}'")

    # 1. 刪除現有的集合（如果存在）
    try:
        print(f"正在嘗試刪除舊的集合: '{COLLECTION_NAME}'...")
        await db.drop_collection(COLLECTION_NAME)
        print(f"成功刪除集合: '{COLLECTION_NAME}'")
    except Exception as e:
        print(f"刪除集合時發生錯誤 (可能是集合不存在，可以忽略): {e}")

    # 2. 重新創建集合
    try:
        await db.create_collection(COLLECTION_NAME)
        print(f"成功創建新集合: '{COLLECTION_NAME}'")
    except CollectionInvalid:
        print(f"集合 '{COLLECTION_NAME}' 已存在，將直接使用。")
    except Exception as e:
        print(f"創建集合時發生未知錯誤: {e}")
        client.close()
        return

    collection = db[COLLECTION_NAME]

    # 3. 創建正確的唯一複合索引
    try:
        print("正在創建 (user_id, item_id) 的唯一複合索引...")
        await collection.create_index(
            [("user_id", ASCENDING), ("item_id", ASCENDING)],
            name="user_id_1_item_id_1",
            unique=True
        )
        print("成功創建唯一索引 'user_id_1_item_id_1'")
    except Exception as e:
        print(f"創建索引時發生錯誤: {e}")

    # 4. (可選) 創建其他需要的索引
    # 如果 player_warehouse_item_id 也需要是唯一的，可以取消下面的註解
    # try:
    #     print("正在創建 player_warehouse_item_id 的唯一索引...")
    #     await collection.create_index(
    #         "player_warehouse_item_id",
    #         name="player_warehouse_item_id_1",
    #         unique=True,
    #         sparse=True  # 如果某些文件可能沒有此欄位
    #     )
    #     print("成功創建唯一索引 'player_warehouse_item_id_1'")
    # except Exception as e:
    #     print(f"創建 player_warehouse_item_id 索引時發生錯誤: {e}")

    print("\n腳本執行完畢。")
    client.close()

if __name__ == "__main__":
    # 在 Windows 上設定異步事件循環策略
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
