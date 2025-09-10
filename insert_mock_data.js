// --- 連接到 Volticar 資料庫 ---
// use Volticar;

// --- 清除 Volticar 中舊的模擬資料 ---
db.ShopItems.deleteMany({});
db.PlayerOwnedVehicles.deleteMany({"vehicle_name": /測試車輛/});
db.GameTasks.deleteMany({});
db.GameEvents.deleteMany({});
db.PlayerItems.deleteMany({});


// --- 新增商店範例商品 ---
db.ShopItems.insertMany([
  {
    "item_id": "tire_repair_kit",
    "name": "輪胎修理包",
    "description": "一個可以在運送過程中快速修理爆胎的工具包。",
    "price": 150,
    "category": "消耗品",
    "icon_url": "https://example.com/icons/tire_kit.png"
  },
  {
    "item_id": "coffee_boost",
    "name": "提神咖啡",
    "description": "減少因「疲勞」事件所導致的時間懲罰。",
    "price": 50,
    "category": "消耗品",
    "icon_url": "https://example.com/icons/coffee.png"
  }
]);

// --- 新增玩家擁有的範例車輛 ---
db.PlayerOwnedVehicles.insertOne({
    "instance_id": "test_vehicle_01",
    "user_id": "a_test_user_uuid",
    "vehicle_id": "base_electric_van",
    "vehicle_name": "測試車輛一號",
    "battery_level": 88,
    "battery_health": 95,
    "mileage": 12345,
    "purchase_date": new Date(),
    "current_condition": 0.9,
    "created_at": new Date(),
    "last_updated": new Date()
});

// --- 新增遊戲任務範例 ---
db.GameTasks.insertMany([
    {
        "task_id": "task_001",
        "station_id": "33029464-STP6360001", // 中山國中站
        "title": "醫院緊急電力輸送",
        "description": "將 25 kWh 的電力運送到市立醫院的備用電源。",
        "reward_points": 100,
        "required_kwh": 25,
        "destination_station_id": "33029464-STP6410001", // 林森公園站
        "created_at": new Date(),
        "is_active": true
    }
]);

// --- 新增遊戲事件範例 ---
db.GameEvents.insertMany([
    {
        "event_id": "event_traffic_jam",
        "name": "交通堵塞",
        "description": "您被困在嚴重的車陣中。",
        "choices": ["等待", "使用道具"]
    }
]);

print("已成功新增所有遊戲模擬資料。");
