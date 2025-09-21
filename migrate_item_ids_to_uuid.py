import asyncio
import uuid
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# !!! IMPORTANT !!!
# Please verify your database connection details before running this script.
DATABASE_URL = "mongodb://Volticar:REMOVED_PASSWORD@59.126.6.46:27017/?authSource=admin&ssl=false"
DB_NAME = "Volticar"

# A consistent namespace for generating UUIDs from string IDs
# This ensures that the same string always produces the same UUID
NAMESPACE = uuid.NAMESPACE_DNS

def get_uuid_from_string(id_string: str) -> uuid.UUID:
    """Generates a consistent UUID version 5 from a string."""
    if not id_string:
        return None
    try:
        # If it's already a valid UUID, just return it parsed.
        return uuid.UUID(id_string)
    except ValueError:
        # Otherwise, generate a new one based on the string content.
        return uuid.uuid5(NAMESPACE, id_string)

async def migrate_data():
    """
    Connects to the database and migrates all string-based item_ids to UUIDs.
    """
    client = None
    try:
        print(f"Connecting to MongoDB at {DATABASE_URL.split('@')[-1]}...")
        client = AsyncIOMotorClient(DATABASE_URL, serverSelectionTimeoutMS=5000, uuidRepresentation='standard')
        await client.admin.command("ping")
        db = client[DB_NAME]
        print(f"Successfully connected to database '{DB_NAME}'.")

        # --- 1. Migrate ItemDefinitions ---
        print("\n[1/6] Migrating 'ItemDefinitions' collection...")
        count = 0
        async for doc in db.ItemDefinitions.find({"item_id": {"$type": "string"}}):
            old_id = doc["item_id"]
            new_id = get_uuid_from_string(old_id)
            await db.ItemDefinitions.update_one({"_id": doc["_id"]}, {"$set": {"item_id": new_id}})
            print(f"  - Updated '{old_id}' to '{new_id}'")
            count += 1
        print(f"  Done. {count} documents updated in ItemDefinitions.")

        # --- 2. Migrate ShopItems ---
        print("\n[2/6] Migrating 'ShopItems' collection...")
        count = 0
        async for doc in db.ShopItems.find({"item_id": {"$type": "string"}}):
            old_id = doc["item_id"]
            new_id = get_uuid_from_string(old_id)
            await db.ShopItems.update_one({"_id": doc["_id"]}, {"$set": {"item_id": new_id}})
            print(f"  - Updated '{old_id}' to '{new_id}'")
            count += 1
        print(f"  Done. {count} documents updated in ShopItems.")

        # --- 3. Migrate PlayerWarehouseItems ---
        print("\n[3/6] Migrating 'PlayerWarehouseItems' collection...")
        count = 0
        async for doc in db.PlayerWarehouseItems.find({"item_id": {"$type": "string"}}):
            old_id = doc["item_id"]
            new_id = get_uuid_from_string(old_id)
            await db.PlayerWarehouseItems.update_one({"_id": doc["_id"]}, {"$set": {"item_id": new_id}})
            print(f"  - Updated item '{old_id}' for user '{doc.get('user_id')}'")
            count += 1
        print(f"  Done. {count} documents updated in PlayerWarehouseItems.")

        # --- 4. Migrate TaskDefinitions (nested) ---
        print("\n[4/6] Migrating 'TaskDefinitions' collection (nested fields)...")
        count = 0
        async for task_def in db.TaskDefinitions.find():
            modified = False
            
            # requirements.deliver_items
            if task_def.get("requirements", {}).get("deliver_items"):
                for item in task_def["requirements"]["deliver_items"]:
                    if isinstance(item.get("item_id"), str):
                        item["item_id"] = get_uuid_from_string(item["item_id"])
                        modified = True

            # rewards.item_rewards
            if task_def.get("rewards", {}).get("item_rewards"):
                for item in task_def["rewards"]["item_rewards"]:
                    if isinstance(item.get("item_id"), str):
                        item["item_id"] = get_uuid_from_string(item["item_id"])
                        modified = True
            
            # pickup_items
            if task_def.get("pickup_items"):
                for item in task_def["pickup_items"]:
                    if isinstance(item.get("item_id"), str):
                        item["item_id"] = get_uuid_from_string(item["item_id"])
                        modified = True

            if modified:
                await db.TaskDefinitions.update_one({"_id": task_def["_id"]}, {"$set": task_def})
                print(f"  - Updated nested item_ids in TaskDefinition '{task_def.get('title', task_def['_id'])}'")
                count += 1
        print(f"  Done. {count} documents updated in TaskDefinitions.")
        
        # --- 5. Migrate PlayerTasks (nested) ---
        print("\n[5/6] Migrating 'PlayerTasks' collection (nested fields)...")
        count = 0
        async for player_task in db.PlayerTasks.find({"progress.items_delivered_count": {"$exists": True}}):
            modified = False
            if player_task.get("progress", {}).get("items_delivered_count"):
                for item in player_task["progress"]["items_delivered_count"]:
                    if isinstance(item.get("item_id"), str):
                        item["item_id"] = get_uuid_from_string(item["item_id"])
                        modified = True
            if modified:
                await db.PlayerTasks.update_one({"_id": player_task["_id"]}, {"$set": player_task})
                print(f"  - Updated progress for PlayerTask '{player_task['_id']}'")
                count += 1
        print(f"  Done. {count} documents updated in PlayerTasks.")

        # --- 6. Migrate GameSessions (nested) ---
        print("\n[6/6] Migrating 'GameSessions' collection (nested fields)...")
        count = 0
        async for session in db.GameSessions.find({"cargo_snapshot": {"$exists": True}}):
            modified = False
            if session.get("cargo_snapshot"):
                for item in session["cargo_snapshot"]:
                    if isinstance(item.get("item_id"), str):
                        item["item_id"] = get_uuid_from_string(item["item_id"])
                        modified = True
            if modified:
                await db.GameSessions.update_one({"_id": session["_id"]}, {"$set": session})
                print(f"  - Updated cargo_snapshot for GameSession '{session['game_session_id']}'")
                count += 1
        print(f"  Done. {count} documents updated in GameSessions.")

        print("\n\nMigration script finished successfully!")

    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        if client:
            client.close()
            print("\nDatabase connection closed.")

if __name__ == "__main__":
    asyncio.run(migrate_data())