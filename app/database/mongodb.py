import os
import asyncio
import time
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mongodb://Volticar:RJW1128@59.126.6.46:27017/?authSource=admin&ssl=false",
)
VOLTICAR_DB = os.getenv("VOLTICAR_DB", "Volticar")
CHARGE_STATION_DB = os.getenv("CHARGE_STATION_DB", "charge_station")
PARKING_DATA_DB = os.getenv("PARKING_DATA_DB", "parking_data")

max_retries = 3
retry_delay = 3  # 秒

print(f"正在連接MongoDB: {DATABASE_URL.split('@')[-1]}")

client: AsyncIOMotorClient = None


from bson.codec_options import CodecOptions
from bson.binary import UuidRepresentation

async def connect_to_mongo():
    global client
    for retry in range(max_retries):
        try:
            client = AsyncIOMotorClient(DATABASE_URL, serverSelectionTimeoutMS=5000)
            await client.admin.command("ping")
            server_info = await client.server_info()
            print(f"MongoDB連接成功! 伺服器版本: {server_info['version']}")
            return client
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            if retry < max_retries - 1:
                print(
                    f"MongoDB連接失敗，嘗試 {retry + 1}/{max_retries}，等待 {retry_delay} 秒後重試... 錯誤: {str(e)}"
                )
                await asyncio.sleep(retry_delay)
            else:
                print(
                    f"MongoDB連接失敗，達到最大重試次數 ({max_retries})。錯誤: {str(e)}"
                )
                print("繼續執行，但資料庫功能將不可用...")
                client = None
                return None
        except Exception as e:
            print(f"連接 MongoDB 時發生未預期錯誤: {e}")
            client = None
            return None
    return None


async def safely_create_index(collection, field_name, unique=False, ascending=True):
    try:
        existing_indexes = await collection.index_information()
        index_name = f"{field_name}_1" if ascending else f"{field_name}_-1"

        if index_name in existing_indexes:
            print(f"  索引 {index_name} 已存在，跳過創建")
            return

        direction = ASCENDING if ascending else -1
        if unique:
            await collection.create_index(
                [(field_name, direction)], unique=True, sparse=True
            )
            print(f"  創建唯一索引(sparse): {index_name}")
        else:
            await collection.create_index([(field_name, direction)])
            print(f"  創建索引: {index_name}")
    except Exception as e:
        print(f"  創建索引 {field_name} 時出錯: {str(e)}")


async def handle_null_duplicates(collection, field_name):
    try:
        null_count = await collection.count_documents({field_name: None})

        if null_count > 1:
            print(f"  發現 {null_count} 個 {field_name} 為null的文檔，開始處理...")
            null_docs_cursor = collection.find({field_name: None})
            null_docs = await null_docs_cursor.to_list(length=null_count)

            for i, doc in enumerate(null_docs[1:], 1):
                await collection.update_one(
                    {"_id": doc["_id"]}, {"$unset": {field_name: ""}}
                )
            print(f"  成功處理 {len(null_docs) - 1} 個 {field_name} 為null的文檔")
    except Exception as e:
        print(f"  處理 {field_name} 的null值時出錯: {str(e)}")


async def migrate_login_type_field(collection):
    try:
        missing_login_type = await collection.count_documents(
            {"login_type": {"$exists": False}}
        )

        if missing_login_type > 0:
            print(f"  發現 {missing_login_type} 個文檔沒有login_type欄位，開始遷移...")
            await collection.update_many(
                {
                    "login_type": {"$exists": False},
                    "google_id": {"$exists": True},
                    "$expr": {"$ne": ["$google_id", "$user_id"]},
                },
                {"$set": {"login_type": "google"}},
            )
            await collection.update_many(
                {"login_type": {"$exists": False}}, {"$set": {"login_type": "normal"}}
            )
            remaining = await collection.count_documents(
                {"login_type": {"$exists": False}}
            )
            print(f"  ✓ 已為 {missing_login_type - remaining} 個文檔添加login_type欄位")

        missing_google_id = await collection.count_documents(
            {"google_id": {"$exists": False}}
        )
        if missing_google_id > 0:
            print(f"  發現 {missing_google_id} 個文檔沒有google_id欄位，開始添加...")
            await collection.update_many(
                {"google_id": {"$exists": False}}, {"$set": {"google_id": ""}}
            )
            update_result_none = await collection.update_many(
                {"google_id": "", "login_type": "normal"}, {"$set": {"google_id": None}}
            )
            print(
                f"  ✓ 已將 {update_result_none.modified_count} 個一般用戶的空 google_id 設為 None"
            )
            remaining = await collection.count_documents(
                {"google_id": {"$exists": False}}
            )
            print(f"  ✓ 已為 {missing_google_id - remaining} 個文檔添加 google_id 欄位")
            old_logic_users = await collection.count_documents(
                {"login_type": "normal", "$expr": {"$eq": ["$google_id", "$user_id"]}}
            )
            if old_logic_users > 0:
                print(
                    f"  發現 {old_logic_users} 個一般用戶的 google_id 等於 user_id (舊邏輯)，開始修正..."
                )
                fix_result = await collection.update_many(
                    {
                        "login_type": "normal",
                        "$expr": {"$eq": ["$google_id", "$user_id"]},
                    },
                    {"$set": {"google_id": None}},
                )
                print(f"  ✓ 已修正 {fix_result.modified_count} 個一般用戶的 google_id")
            empty_google_id = await collection.count_documents({"google_id": ""})
            if empty_google_id > 0:
                fix_empty_result = await collection.update_many(
                    {"google_id": ""}, {"$set": {"google_id": None}}
                )
                print(
                    f"  ✓ 已將 {fix_empty_result.modified_count} 個剩餘的空 google_id 設為 None"
                )
    except Exception as e:
        print(f"  遷移login_type欄位時出錯: {str(e)}")


volticar_db = None
charge_station_db = None
parking_data = None
users_collection = None
players_collection = None
player_data_collection = None
login_records_collection = None
# vehicles_collection = None # This was ambiguous, replaced by player_owned_vehicles_collection
# tasks_collection = None # This was ambiguous, replaced by task_definitions_collection
player_achievements_collection = None
achievement_definitions_collection = None
rewards_collection = None
pending_verifications_collection = None
otp_records_collection = None  # Added for OTP records

player_tasks_collection = None
vehicle_definitions_collection = None  # Corrected spelling from previous state
player_owned_vehicles_collection = None
item_definitions_collection = None
player_warehouse_items_collection = None
destinations_collection = None
game_sessions_collection = None
task_definitions_collection = None


async def initialize_db_and_collections():
    global client, volticar_db, charge_station_db, parking_data, users_collection, players_collection, player_data_collection, login_records_collection
    # global vehicles_collection, tasks_collection, # Removed old ambiguous ones
    global player_achievements_collection, achievement_definitions_collection, rewards_collection, pending_verifications_collection, otp_records_collection
    global player_tasks_collection, vehicle_definitions_collection, player_owned_vehicles_collection
    global item_definitions_collection, player_warehouse_items_collection, destinations_collection
    global game_sessions_collection, task_definitions_collection
    global game_events_collection

    if client is None:
        print("MongoDB client is not connected. Aborting initialization.")
        return

    try:
        codec_options = CodecOptions(uuid_representation=UuidRepresentation.STANDARD)
        volticar_db = client.get_database(VOLTICAR_DB, codec_options=codec_options)
        charge_station_db = client[CHARGE_STATION_DB]
        parking_data = client[PARKING_DATA_DB]

        users_collection = volticar_db["Users"]
        players_collection = volticar_db["Player"]
        player_data_collection = volticar_db["PlayerData"]
        login_records_collection = volticar_db["LoginRecords"]

        # Explicitly define collections based on new Pydantic models and mock data script

        player_owned_vehicles_collection = volticar_db[
            "PlayerVehicles"
        ]  # Renamed from "Vehicles" to match schema

        player_achievements_collection = volticar_db["PlayerAchievements"]
        achievement_definitions_collection = volticar_db["DefinitionAchievements"]
        rewards_collection = volticar_db["Rewards"]
        pending_verifications_collection = volticar_db["PendingVerifications"]
        otp_records_collection = volticar_db[
            "OTPRecords"
        ]  # Initialize OTPRecords collection

        player_tasks_collection = volticar_db["PlayerTasks"]
        player_warehouse_items_collection = volticar_db["PlayerWarehouseItems"]
        game_sessions_collection = volticar_db["GameSessions"]
        task_definitions_collection = volticar_db["DefinitionTasks"]
        vehicle_definitions_collection = volticar_db["DefinitionVehicles"]
        item_definitions_collection = volticar_db["DefinitionItems"]
        destinations_collection = volticar_db["DefinitionDestinations"]
        game_events_collection = volticar_db["GameEvents"]

        print("所有集合引用已初始化。")

        print("開始遷移login_type欄位 (Users)...")
        await migrate_login_type_field(users_collection)

        print("檢查並處理可能的null值重複問題...")
        await handle_null_duplicates(users_collection, "phone")

        print("正在檢查並創建所需的MongoDB索引...")

        print("用戶集合索引:")
        await safely_create_index(users_collection, "user_id", unique=True)
        await safely_create_index(users_collection, "email", unique=True)
        # ... (other index creations remain the same) ...
        await safely_create_index(users_collection, "username", unique=True)
        await safely_create_index(users_collection, "google_id", unique=True)
        await safely_create_index(users_collection, "login_type")

        print("登入記錄索引:")
        await safely_create_index(
            login_records_collection, "user_id"
        )  # This should refer to User.user_id
        await safely_create_index(login_records_collection, "login_timestamp")

        # player_owned_vehicles_collection (points to "Vehicles")
        print("玩家擁有車輛 (Vehicles) 集合索引:")
        # Assuming player_vehicle_id is the custom UUID for PlayerOwnedVehicle instances
        # Correcting field name from player_vehicle_id to instance_id to match the model
        await safely_create_index(
            player_owned_vehicles_collection, "instance_id", unique=True
        )
        # Correcting field name from player_id to user_id to match the model
        await safely_create_index(player_owned_vehicles_collection, "user_id")


        print("成就 (Achievements) 集合索引:")
        await safely_create_index(
            player_achievements_collection, "achievement_id", unique=True
        )

        # Rewards collection might need an update if it refers to item_id (custom UUID)
        print("獎勵索引:")
        # await safely_create_index(rewards_collection, "item_id", unique=True) # If rewards have a main item_id

        print("待驗證集合索引:")
        await safely_create_index(pending_verifications_collection, "email")
        await safely_create_index(
            pending_verifications_collection, "token", unique=True
        )

        print("OTP 記錄集合索引:")
        await safely_create_index(otp_records_collection, "user_id")
        await safely_create_index(otp_records_collection, "target_identifier")
        await safely_create_index(otp_records_collection, "type")
        await safely_create_index(otp_records_collection, "otp_code")
        await safely_create_index(otp_records_collection, "expires_at")
        await safely_create_index(otp_records_collection, "is_used")

        print("MongoDB索引檢查完成!")

    except Exception as e:
        print(f"設置數據庫、集合或執行索引/遷移時發生錯誤: {e}")
        # Reset all to None
        volticar_db = charge_station_db = parking_data = users_collection = players_collection = player_data_collection = (
            login_records_collection
        ) = None
        player_achievements_collection = achievement_definitions_collection = rewards_collection = (
            pending_verifications_collection
        ) = otp_records_collection = None
        player_tasks_collection = vehicle_definitions_collection = (
            player_owned_vehicles_collection
        ) = None
        item_definitions_collection = player_warehouse_items_collection = (
            destinations_collection
        ) = None
        game_sessions_collection = task_definitions_collection = None
        pass

    try:
        print("為新遊戲集合創建索引...")
        print("玩家任務 (PlayerTasks) 集合索引:")
        await safely_create_index(
            player_tasks_collection, "player_task_id", unique=True
        )
        # Correcting field name from player_id to user_id to match the model
        await safely_create_index(player_tasks_collection, "user_id")
        await safely_create_index(player_tasks_collection, "task_id")
        await safely_create_index(player_tasks_collection, "status")
        await safely_create_index(player_tasks_collection, "linked_game_session_id")



        print("玩家倉庫 (PlayerWarehouseItems) 集合索引:")
        await player_warehouse_items_collection.create_index(
            [("user_id", ASCENDING), ("item_id", ASCENDING)], unique=True
        )
        print("  創建唯一複合索引: user_id_1_item_id_1")
        await safely_create_index(
            # This index might be redundant if the compound index is the primary way to look up items.
            player_warehouse_items_collection, "player_warehouse_item_id", unique=True
        )


        print("遊戲會話 (GameSessions) 集合索引:")
        await safely_create_index(
            game_sessions_collection, "game_session_id", unique=True
        )
        # Correcting field name from player_id to user_id to match the model
        await safely_create_index(game_sessions_collection, "user_id")
        await safely_create_index(game_sessions_collection, "status")

        print("新遊戲集合索引創建完成!")

        print("遊戲事件 (GameEvents) 集合索引:")
        await safely_create_index(game_events_collection, "event_id", unique=True)
        await safely_create_index(game_events_collection, "is_active")
    except Exception as e:
        print(f"為新遊戲集合創建索引時發生錯誤: {e}")
        pass


async def print_connection_info():
    if volticar_db is not None:
        print(f"已連接到數據庫: {VOLTICAR_DB}")
        collections = await volticar_db.list_collection_names()
        print(f"可用的集合: {', '.join(collections)}")
    if charge_station_db is not None:
        try:
            cities = await charge_station_db.list_collection_names()
            print(f"充電站數據庫中可用的城市: {', '.join(cities)}")
        except Exception as e:
            print(f"無法獲取充電站集合列表: {str(e)}")
    if parking_data is not None:
        try:
            parking_cities = await parking_data.list_collection_names()
            print(f"停車場數據庫中可用的城市: {', '.join(parking_cities)}")
        except Exception as e:
            print(f"無法獲取停車場集合列表: {str(e)}")


async def get_charge_station_collection(city=None):
    if charge_station_db is None:
        print("Charge station DB not initialized.")
        return [] if not city else None
    try:
        if city:
            return charge_station_db[city]
        else:
            return await charge_station_db.list_collection_names()
    except Exception as e:
        print(f"獲取充電站集合失敗: {str(e)}")
        return [] if not city else None


async def get_parking_collection(city=None):
    if parking_data is None:
        print("Parking data DB not initialized.")
        return [] if not city else None
    try:
        if city:
            return parking_data[city]
        else:
            return await parking_data.list_collection_names()
    except Exception as e:
        print(f"獲取停車場集合失敗: {str(e)}")
        return [] if not city else None


async def connect_and_initialize_db():
    global client
    # client = await connect_to_mongo() # Original line
    # Let connect_to_mongo handle setting the global client
    await connect_to_mongo()

    print(
        f"DEBUG: connect_and_initialize_db - client is {client} (type: {type(client)}) before if/else logic."
    )

    if client:
        print("DEBUG: connect_and_initialize_db - Entering 'if client:' block.")
        await initialize_db_and_collections()
        await print_connection_info()
        print(
            f"DEBUG: connect_and_initialize_db - client is {client} (type: {type(client)}) at the end of 'if client:' block."
        )
    else:
        print(
            f"DEBUG: connect_and_initialize_db - Entering 'else:' block because client is {client} (type: {type(client)})."
        )
        # Reset all global collection variables to None
        global volticar_db, charge_station_db, parking_data, users_collection, players_collection, player_data_collection, login_records_collection
        global player_achievements_collection, achievement_definitions_collection, rewards_collection, pending_verifications_collection, otp_records_collection
        global player_tasks_collection, vehicle_definitions_collection, player_owned_vehicles_collection
        global item_definitions_collection, player_warehouse_items_collection, destinations_collection
        global game_sessions_collection, task_definitions_collection

        volticar_db = charge_station_db = parking_data = users_collection = players_collection = player_data_collection = (
            login_records_collection
        ) = None
        player_achievements_collection = achievement_definitions_collection = rewards_collection = (
            pending_verifications_collection
        ) = otp_records_collection = None
        player_tasks_collection = vehicle_definitions_collection = (
            player_owned_vehicles_collection
        ) = None
        item_definitions_collection = player_warehouse_items_collection = (
            destinations_collection
        ) = None
        game_sessions_collection = task_definitions_collection = None
        print(
            "警告: 無法連接到MongoDB，API將在無數據庫模式下運行 (collections have been reset to None)."
        )


async def close_mongo_connection():
    global client
    if client:
        client.close()
        print("MongoDB 連線已關閉")

async def get_db():
    if volticar_db is None:
        raise Exception("Database is not initialized")
    return volticar_db
