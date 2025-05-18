// MongoDB Script to Insert Mock Data (Revised for ObjectId _id and Custom UUID Business IDs)
// Version 4: Does NOT delete Users and LoginRecords collections.
// =======================================================================================
print("Starting to insert mock data (v4 - ObjectId _id, clean custom UUID strings, preserves Users/LoginRecords)...");
print("==========================================================================================================");

// Ensure you are on the 'Volticar' database
// In mongo shell, you might need to run: use Volticar;

// --- Helper function to generate UUIDs ---
function generateCustomUUIDString() {
    var d = new Date().getTime();
    if (typeof performance !== 'undefined' && typeof performance.now === 'function'){
        d += performance.now(); 
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        var r = (d + Math.random() * 16) % 16 | 0;
        d = Math.floor(d / 16);
        return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
}
print("Custom UUID string generator function defined.");

// Store generated custom UUIDs to use in references
var generated_ids = {};

// 1. VehicleDefinitions
// ---------------------
print("\nClearing and inserting mock data for VehicleDefinitions...");
try {
    db.VehicleDefinitions.deleteMany({});
    generated_ids.vehicleDef1_id = generateCustomUUIDString();
    generated_ids.vehicleDef2_id = generateCustomUUIDString();
    db.VehicleDefinitions.insertMany([
        {
            vehicle_id: generated_ids.vehicleDef1_id, 
            name: "輕型貨卡 Mark I (v4)",
            type: "pickup_truck",
            description: "基礎型輕型貨卡，適合新手上路。",
            max_load_weight: 1500.0,
            max_load_volume: 5.0,
            base_price: 25000,
            rental_price_per_session: 200,
            availability_type: "purchasable_rentable",
            required_level_to_unlock: 1,
            icon_url: "/icons/pickup_m1_v4.png",
            image_url: "/images/pickup_m1_v4.jpg"
        },
        {
            vehicle_id: generated_ids.vehicleDef2_id,
            name: "中型廂式貨車 (v4)",
            type: "van",
            description: "容量適中，適合多種城市運輸任務。",
            max_load_weight: 3500.0,
            max_load_volume: 12.0,
            base_price: 60000,
            availability_type: "purchasable",
            required_level_to_unlock: 5,
            icon_url: "/icons/van_std_v4.png",
            image_url: "/images/van_std_v4.jpg"
        }
    ]);
    print(`Inserted mock data into VehicleDefinitions. Custom vehicle_ids: ${generated_ids.vehicleDef1_id}, ${generated_ids.vehicleDef2_id}`);
} catch (e) {
    print(`Error processing VehicleDefinitions: ${e}`);
}

// 2. ItemDefinitions
// ------------------
print("\nClearing and inserting mock data for ItemDefinitions...");
try {
    db.ItemDefinitions.deleteMany({});
    generated_ids.itemDef1_id = generateCustomUUIDString();
    generated_ids.itemDef2_id = generateCustomUUIDString();
    db.ItemDefinitions.insertMany([
        {
            item_id: generated_ids.itemDef1_id,
            name: "鐵礦石 (v4)",
            description: "未加工的鐵礦石，用於工業生產。",
            category: "原材料",
            weight_per_unit: 100.0,
            volume_per_unit: 0.05,
            base_value_per_unit: 20,
            is_fragile: false,
            is_perishable: false,
            icon_url: "/icons/iron_ore_v4.png"
        },
        {
            item_id: generated_ids.itemDef2_id,
            name: "精密電子零件 (v4)",
            description: "高價值的電子組件，易碎。",
            category: "高科技產品",
            weight_per_unit: 5.0,
            volume_per_unit: 0.01,
            base_value_per_unit: 250,
            is_fragile: true,
            is_perishable: false,
            icon_url: "/icons/electronics_v4.png"
        }
    ]);
    print(`Inserted mock data into ItemDefinitions. Custom item_ids: ${generated_ids.itemDef1_id}, ${generated_ids.itemDef2_id}`);
} catch (e) {
    print(`Error processing ItemDefinitions: ${e}`);
}

// 3. Destinations
// ---------------
print("\nClearing and inserting mock data for Destinations...");
try {
    db.Destinations.deleteMany({});
    generated_ids.dest1_id = generateCustomUUIDString();
    generated_ids.dest2_id = generateCustomUUIDString();
    db.Destinations.insertMany([
        {
            destination_id: generated_ids.dest1_id,
            name: "東區倉庫 (v4)",
            description: "位於城市東部的大型物流倉儲中心。",
            region: "東區",
            coordinates: { type: "Point", coordinates: [121.5654, 25.0330] },
            is_unlocked_by_default: true,
            available_services: ["cargo_pickup", "cargo_dropoff", "fuel_station"],
            icon_url: "/icons/warehouse_east_v4.png"
        },
        {
            destination_id: generated_ids.dest2_id,
            name: "西港碼頭 (v4)",
            description: "繁忙的貨運港口，處理進出口貨物。",
            region: "西區",
            coordinates: { type: "Point", coordinates: [121.5000, 25.0479] },
            is_unlocked_by_default: false,
            unlock_requirements: { required_player_level: 10 },
            available_services: ["cargo_pickup", "cargo_dropoff", "repair_shop", "customs_office"],
            icon_url: "/icons/port_west_v4.png"
        }
    ]);
    print(`Inserted mock data into Destinations. Custom destination_ids: ${generated_ids.dest1_id}, ${generated_ids.dest2_id}`);
} catch (e) {
    print(`Error processing Destinations: ${e}`);
}

// 4. TaskDefinitions
// -----------------------------------
print("\nClearing and inserting mock data for TaskDefinitions...");
try {
    db.TaskDefinitions.deleteMany({});
    generated_ids.taskDef1_id = generateCustomUUIDString();
    
    var task_item_ref_id = generated_ids.itemDef1_id; 
    var task_dest_ref_id = generated_ids.dest1_id;

    if (!task_item_ref_id) print("TaskDefinitions: Warning, generated_ids.itemDef1_id is missing for task item reference.");
    if (!task_dest_ref_id) print("TaskDefinitions: Warning, generated_ids.dest1_id is missing for task destination reference.");

    db.TaskDefinitions.insertOne(
        {
            task_id: generated_ids.taskDef1_id,
            title: "新手教學：首次運輸 (v4)",
            description: "將10單位鐵礦石 (v4)運送到東區倉庫 (v4)，熟悉基本操作。",
            type: "story",
            requirements: {
                required_player_level: 1,
                deliver_items: [{ item_id: task_item_ref_id, quantity: 10 }], 
                destination_id: task_dest_ref_id  
            },
            rewards: {
                experience_points: 100,
                currency: 500
            },
            is_repeatable: false,
            is_active: true,
            availability_start_date: null,
            availability_end_date: null,
            prerequisite_task_ids: []
        }
    );
    print(`Inserted mock data into TaskDefinitions. Custom task_id: ${generated_ids.taskDef1_id}`);
} catch (e) {
    print(`Error processing TaskDefinitions: ${e}`);
}

// Users and LoginRecords collections are NO LONGER cleared by this script.
print("\nSkipping clearing of Users and LoginRecords collections as per user request.");

print("\n=====================================================================");
print("Mock data insertion script (v4) COMPLETED.");
print("Your existing Users and LoginRecords data should be preserved.");
print("Please ensure your existing Users data conforms to the new Pydantic model (ObjectId _id and a custom user_id UUID string).");
print("Test your application with existing users and this new mock data.");
