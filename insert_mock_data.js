// Javascript in MongoDB shell doesn't have a built-in uuid library.
// We can use the UUID() constructor available in the mongo shell.
// This script is designed to be run directly in the mongo shell.

print("--- Dropping old collections to ensure a clean slate ---");
db.VehicleDefinitions.drop();
db.ItemDefinitions.drop();
db.Destinations.drop();
db.TaskDefinitions.drop();
// Also drop the old, wrongly named collections if they exist
db.vehicles.drop();
db.items.drop();
db.destinations.drop();
db.tasks.drop();

print("--- Starting to insert mock data with proper UUIDs and collection names ---");

// --- Define UUIDs first for cross-referencing ---
const vehicle1_uuid = UUID();
const vehicle2_uuid = UUID();
const item1_uuid = UUID();
const item2_uuid = UUID();
const dest1_uuid = UUID();
const dest2_uuid = UUID();
const task1_uuid = UUID();
const task2_uuid = UUID();

// --- 2.2 VehicleDefinitions collection ---
print("Inserting into VehicleDefinitions...");
db.VehicleDefinitions.insertOne({
    "vehicle_id": vehicle1_uuid,
    "name": "輕型貨卡 Mark I",
    "type": "pickup_truck",
    "description": "基礎型輕型貨卡，適合新手上路。",
    "max_load_weight": 1500,
    "max_load_volume": 5,
    "base_price": 25000,
    "rental_price_per_session": 200,
    "availability_type": "purchasable_rentable",
    "required_level_to_unlock": 1,
    "icon_url": "/icons/pickup_m1.png",
    "image_url": "/images/pickup_m1.jpg"
});

db.VehicleDefinitions.insertOne({
    "vehicle_id": vehicle2_uuid,
    "name": "中型廂式貨車",
    "type": "van",
    "description": "容量適中，適合多種城市運輸任務。",
    "max_load_weight": 3500,
    "max_load_volume": 12,
    "base_price": 60000,
    "availability_type": "purchasable",
    "required_level_to_unlock": 5,
    "icon_url": "/icons/van_std.png",
    "image_url": "/images/van_std.jpg"
});
print("VehicleDefinitions inserted: " + db.VehicleDefinitions.countDocuments());

// --- 2.4 ItemDefinitions collection ---
print("Inserting into ItemDefinitions...");
db.ItemDefinitions.insertOne({
    "item_id": item1_uuid,
    "name": "鐵礦石",
    "description": "未經加工的基礎工業原料。",
    "category": "原料",
    "weight_per_unit": 100,
    "volume_per_unit": 0.05,
    "base_value_per_unit": 20,
    "is_fragile": false,
    "is_perishable": false,
    "icon_url": "/icons/iron_ore.png"
});

db.ItemDefinitions.insertOne({
    "item_id": item2_uuid,
    "name": "精密電子零件",
    "description": "用於高科技產品製造的敏感電子元件。",
    "category": "電子產品",
    "weight_per_unit": 5,
    "volume_per_unit": 0.01,
    "base_value_per_unit": 300,
    "is_fragile": true,
    "is_perishable": false,
    "icon_url": "/icons/electronics.png"
});
print("ItemDefinitions inserted: " + db.ItemDefinitions.countDocuments());

// --- 2.8 Destinations collection ---
print("Inserting into Destinations...");
db.Destinations.insertOne({
    "destination_id": dest1_uuid,
    "name": "東區倉庫",
    "description": "位於城市東部的大型物流中心。",
    "region": "東區",
    "coordinates": { "type": "Point", "coordinates": [121.5654, 25.0330] },
    "is_unlocked_by_default": true,
    "available_services": ["cargo_pickup", "cargo_dropoff"],
    "icon_url": "/icons/warehouse_east.png"
});

db.Destinations.insertOne({
    "destination_id": dest2_uuid,
    "name": "高科技園區",
    "description": "眾多科技公司總部的所在地。",
    "region": "南港區",
    "coordinates": { "type": "Point", "coordinates": [121.6151, 25.0557] },
    "is_unlocked_by_default": false,
    "unlock_requirements": { "required_player_level": 5 },
    "available_services": ["cargo_dropoff", "repair_shop"],
    "icon_url": "/icons/tech_park.png"
});
print("Destinations inserted: " + db.Destinations.countDocuments());

// --- 2.6 TaskDefinitions collection ---
print("Inserting into TaskDefinitions...");
db.TaskDefinitions.insertOne({
    "task_id": task1_uuid,
    "title": "新手教學：首次運輸",
    "description": "將10單位鐵礦石運送到東區倉庫，熟悉基本操作。",
    "mode": "story",
    "requirements": {
      "required_player_level": 1,
      "deliver_items": [{ "item_id": item1_uuid, "quantity": 10 }],
      "destination_id": dest1_uuid
    },
    "rewards": {
      "experience_points": 100,
      "currency": 500
    },
    "is_repeatable": false,
    "is_active": true,
    "prerequisite_task_ids": []
});

db.TaskDefinitions.insertOne({
    "task_id": task2_uuid,
    "title": "緊急訂單：園區的零件",
    "description": "將50單位精密電子零件緊急運送到高科技園區。",
    "mode": "daily",
    "requirements": {
      "required_player_level": 5,
      "deliver_items": [{ "item_id": item2_uuid, "quantity": 50 }],
      "destination_id": dest2_uuid,
      "time_limit_seconds": 3600
    },
    "rewards": {
      "experience_points": 350,
      "currency": 2000,
      "item_rewards": [{ "item_id": item1_uuid, "quantity": 20 }]
    },
    "is_repeatable": true,
    "repeat_cooldown_hours": 24,
    "is_active": true,
    "prerequisite_task_ids": [task1_uuid]
});
print("TaskDefinitions inserted: " + db.TaskDefinitions.countDocuments());

print("--- Mock data synchronization complete ---");
