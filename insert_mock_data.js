// --- 連接到 Volticar 資料庫 ---
// use Volticar;

// 此腳本現在完全基於 game_api_database_design.md 文件來建立模擬資料。
// 使用 replaceOne 和 upsert:true 來徹底替換文件，確保沒有多餘欄位。

print("--- 開始以 replaceOne 模式徹底同步模擬資料 ---");

// --- 2.2 vehicles 集合 (車輛定義) ---
db.vehicles.replaceOne(
  { "_id": ObjectId("68c12072dd4a88deabfa3350") },
  {
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
  },
  { upsert: true }
);

db.vehicles.replaceOne(
  { "_id": ObjectId("68c12072dd4a88deabfa3351") },
  {
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
  },
  { upsert: true }
);

// --- 2.4 items 集合 (貨物定義) ---
db.items.replaceOne(
  { "_id": ObjectId("68c12072dd4a88deabfa3352") },
  {
    "name": "鐵礦石",
    "description": "未經加工的基礎工業原料。",
    "category": "原料",
    "weight_per_unit": 100,
    "volume_per_unit": 0.05,
    "base_value_per_unit": 20,
    "is_fragile": false,
    "is_perishable": false,
    "icon_url": "/icons/iron_ore.png"
  },
  { upsert: true }
);

db.items.replaceOne(
  { "_id": ObjectId("68c12072dd4a88deabfa3353") },
  {
    "name": "精密電子零件",
    "description": "用於高科技產品製造的敏感電子元件。",
    "category": "電子產品",
    "weight_per_unit": 5,
    "volume_per_unit": 0.01,
    "base_value_per_unit": 300,
    "is_fragile": true,
    "is_perishable": false,
    "icon_url": "/icons/electronics.png"
  },
  { upsert: true }
);

// --- 2.8 destinations 集合 (地點定義) ---
db.destinations.replaceOne(
  { "_id": ObjectId("68c12072dd4a88deabfa3354") },
  {
    "name": "東區倉庫",
    "description": "位於城市東部的大型物流中心。",
    "region": "東區",
    "coordinates": { "type": "Point", "coordinates": [121.5654, 25.0330] },
    "is_unlocked_by_default": true,
    "available_services": ["cargo_pickup", "cargo_dropoff"],
    "icon_url": "/icons/warehouse_east.png"
  },
  { upsert: true }
);

db.destinations.replaceOne(
  { "_id": ObjectId("68c12072dd4a88deabfa3355") },
  {
    "name": "高科技園區",
    "description": "眾多科技公司總部的所在地。",
    "region": "南港區",
    "coordinates": { "type": "Point", "coordinates": [121.6151, 25.0557] },
    "is_unlocked_by_default": false,
    "unlock_requirements": { "required_player_level": 5 },
    "available_services": ["cargo_dropoff", "repair_shop"],
    "icon_url": "/icons/tech_park.png"
  },
  { upsert: true }
);

// --- 2.6 tasks 集合 (任務定義) ---
db.tasks.replaceOne(
  { "_id": ObjectId("68c12072dd4a88deabfa3356") },
  {
    "title": "新手教學：首次運輸",
    "description": "將10單位鐵礦石運送到東區倉庫，熟悉基本操作。",
    "mode": "story",
    "requirements": {
      "required_player_level": 1,
      "deliver_items": [{ "item_id": ObjectId("68c12072dd4a88deabfa3352"), "quantity": 10 }],
      "destination_id": ObjectId("68c12072dd4a88deabfa3354")
    },
    "rewards": {
      "experience_points": 100,
      "currency": 500
    },
    "is_repeatable": false,
    "is_active": true,
    "prerequisite_task_ids": []
  },
  { upsert: true }
);

db.tasks.replaceOne(
  { "_id": ObjectId("68c12072dd4a88deabfa3357") },
  {
    "title": "緊急訂單：園區的零件",
    "description": "將50單位精密電子零件緊急運送到高科技園區。",
    "mode": "daily",
    "requirements": {
      "required_player_level": 5,
      "deliver_items": [{ "item_id": ObjectId("68c12072dd4a88deabfa3353"), "quantity": 50 }],
      "destination_id": ObjectId("68c12072dd4a88deabfa3355"),
      "time_limit_seconds": 3600
    },
    "rewards": {
      "experience_points": 350,
      "currency": 2000,
      "item_rewards": [{ "item_id": ObjectId("68c12072dd4a88deabfa3352"), "quantity": 20 }]
    },
    "is_repeatable": true,
    "repeat_cooldown_hours": 24,
    "is_active": true,
    "prerequisite_task_ids": [ObjectId("68c12072dd4a88deabfa3356")]
  },
  { upsert: true }
);

// --- 2.3 player_owned_vehicles 集合 ---
db.player_owned_vehicles.replaceOne(
  { "_id": ObjectId("68c12072dd4a88deabfa3358") },
  {
    "player_id": ObjectId("68c12072dd4a88deabfa3359"), // 假設一個玩家ID
    "vehicle_definition_id": ObjectId("68c12072dd4a88deabfa3350"),
    "nickname": "我的第一台貨卡",
    "purchase_date": new Date("2023-01-15T10:00:00Z"),
    "last_used_time": new Date("2023-10-01T18:00:00Z"),
    "current_condition": 0.95,
    "is_in_active_session": false
  },
  { upsert: true }
);

print("--- 所有模擬資料已使用 replaceOne 模式同步完成 ---");
