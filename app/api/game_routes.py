from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List
from datetime import datetime
import httpx
from geopy.distance import geodesic
from app.models.user import User
from app.utils.auth import get_current_user
from app.models.game_models import (
    ChargeSessionReport,
    CheckInPayload,
    GameTask,
    GameEvent,
    ResolveEventPayload,
    ShopItem,
    PurchasePayload,
    VehicleUpgradePayload,
)
from app.database.mongodb import get_db
from app.database import mongodb as db_provider # 引入 db_provider

router = APIRouter()

@router.post("/integrations/charge-session/report", status_code=201, summary="回報充電會話以獲得碳積分")
async def report_charge_session(
    report: ChargeSessionReport,
    current_user: User = Depends(get_current_user)
):
    """
    （模擬整合）接收來自充電樁的充電完成報告。
    - 根據充電量 (`kwh_added`) 計算並給予玩家碳積分。
    - 驗證回報的車輛實例是否屬於當前用戶。
    """
    # Find the vehicle to ensure it belongs to the current user
    vehicle = await db_provider.player_owned_vehicles_collection.find_one({
        "instance_id": report.vehicle_instance_id,
        "user_id": current_user.user_id
    })

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found or does not belong to the current user.")

    # Calculate carbon points, e.g., 1 kWh = 10 points
    carbon_points_earned = int(report.kwh_added * 10)

    # Update user's carbon points
    await db_provider.users_collection.update_one(
        {"user_id": current_user.user_id},
        {"$inc": {"carbon_points": carbon_points_earned}}
    )

    return {
        "message": "Charge session reported successfully.",
        "kwh_added": report.kwh_added,
        "carbon_points_earned": carbon_points_earned
    }

@router.post("/player/check-in", status_code=200, summary="在充電站簽到")
async def check_in_at_station(
    payload: CheckInPayload,
    current_user: User = Depends(get_current_user)
):
    """
    允許玩家在地理位置上靠近充電站時進行簽到。
    - 驗證玩家的座標是否在充電站的特定範圍內（例如 100 公尺）。
    - 簽到是領取該站點任務的前提條件。
    """
    if db_provider.charge_station_db is None:
        raise HTTPException(status_code=503, detail="Database service not initialized")
    stations_collection = db_provider.charge_station_db["Stations"]
    station = await stations_collection.find_one({"StationID": payload.station_id})
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    station_coords = (station['PositionLat'], station['PositionLon'])
    user_coords = (payload.latitude, payload.longitude)

    distance = geodesic(station_coords, user_coords).meters

    if distance > 100: # 100 meters
        raise HTTPException(status_code=400, detail=f"User is not within the station's range. Distance: {distance:.2f} meters.")

    # Record the check-in
    await db_provider.users_collection.update_one(
        {"user_id": current_user.user_id},
        {"$set": {"last_check_in": {
            "station_id": payload.station_id,
            "timestamp": datetime.now()
        }}}
    )

    return {"message": f"Successfully checked in at station {payload.station_id}"}

@router.get("/stations/{station_id}/tasks", response_model=List[GameTask], summary="獲取特定充電站的任務")
async def get_station_tasks(
    station_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    獲取玩家在特定充電站可以接取的任務。
    - **必要條件**: 玩家必須先在該充電站成功簽到。
    - 任務的生成可能有冷卻時間（例如，24 小時內只能為同一個玩家在同一個站點生成一次）。
    """
    # 1. Verify check-in
    if not current_user.last_check_in or current_user.last_check_in['station_id'] != station_id:
        raise HTTPException(status_code=403, detail="User must be checked in at this station to get tasks.")

    # 2. Check cooldown (假設 PlayerStationTasks 集合存在)
    if db_provider.volticar_db is None:
        raise HTTPException(status_code=503, detail="Database service not initialized")
    last_task_record = await db_provider.volticar_db["PlayerStationTasks"].find_one(
        {"user_id": current_user.user_id, "station_id": station_id},
        sort=[("generated_at", -1)]
    )

    if last_task_record and (datetime.now() - last_task_record['generated_at']).total_seconds() < 86400: # 24 hours
        raise HTTPException(status_code=429, detail="Tasks for this station are on cooldown.")

    # 3. Generate new tasks
    # For simplicity, we'll generate one sample task.
    new_task_data = {
        "station_id": station_id,
        "title": "Urgent Power Delivery",
        "description": "Deliver 10 kWh of power to a nearby station.",
        "reward_points": 50,
        "required_kwh": 10,
        "destination_station_id": "some_other_station_id", # This should be dynamically selected
    }
    new_task = GameTask(**new_task_data)
    
    if db_provider.volticar_db is None:
        raise HTTPException(status_code=503, detail="Database service not initialized")
    await db_provider.volticar_db["GameTasks"].insert_one(new_task.model_dump(by_alias=True))
    
    # Record task generation time for cooldown
    await db_provider.volticar_db["PlayerStationTasks"].insert_one({
        "user_id": current_user.user_id,
        "station_id": station_id,
        "generated_at": datetime.now()
    })

    return [new_task]

import random

@router.post("/game-session/{session_id}/trigger-event", response_model=GameEvent, summary="觸發一個隨機遊戲事件")
async def trigger_game_event(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    在一個正在進行的遊戲會話中觸發一個隨機事件（例如，交通堵塞、爆胎）。
    - 伺服器會從事件池中隨機選擇一個事件，並將其與當前的遊戲會話關聯。
    """
    # 1. Define an event pool
    event_pool = [
        {"name": "Traffic Jam", "description": "You are stuck in a heavy traffic jam.", "choices": ["wait", "use_item"]},
        {"name": "Flat Tire", "description": "Oh no, you have a flat tire!", "choices": ["repair", "call_for_help"]},
        {"name": "Police Check", "description": "A police officer is signaling you to pull over.", "choices": ["comply", "use_item"]},
    ]

    # 2. Randomly select an event
    selected_event_data = random.choice(event_pool)
    
    # 3. Create and store the event
    game_event = GameEvent(**selected_event_data)
    
    if db_provider.volticar_db is None:
        raise HTTPException(status_code=503, detail="Database service not initialized")
    await db_provider.volticar_db["GameEvents"].insert_one(game_event.model_dump(by_alias=True))

    # Associate event with the game session
    await db_provider.volticar_db["GameSessions"].update_one(
        {"game_session_id": session_id, "user_id": current_user.user_id},
        {"$push": {"events": game_event.model_dump(by_alias=True)}}
    )

    return game_event

@router.post("/game-session/{session_id}/resolve-event", summary="解決一個遊戲事件")
async def resolve_game_event(
    session_id: str,
    payload: ResolveEventPayload,
    current_user: User = Depends(get_current_user)
):
    """
    玩家對一個已觸發的遊戲事件做出選擇，以解決該事件。
    - **event_id**: 要解決的事件的 ID。
    - **choice**: 玩家做出的選擇。
    - 如果選擇是 `use_item`，則必須提供 `item_id`，系統會從玩家倉庫中扣除相應物品。
    """
    # 1. Find the game session and the specific event
    if db_provider.volticar_db is None:
        raise HTTPException(status_code=503, detail="Database service not initialized")
    game_session = await db_provider.volticar_db["GameSessions"].find_one({
        "game_session_id": session_id, 
        "user_id": current_user.user_id,
        "events.event_id": payload.event_id
    })
    if not game_session:
        raise HTTPException(status_code=404, detail="Game session or event not found.")

    # 2. Validate the choice
    event = next((e for e in game_session.get('events', []) if e['event_id'] == payload.event_id), None)
    if not event or payload.choice not in event['choices']:
        raise HTTPException(status_code=400, detail="Invalid choice for this event.")

    # 3. Handle item usage
    if payload.choice == "use_item":
        if not payload.item_id:
            raise HTTPException(status_code=400, detail="item_id is required when choice is 'use_item'.")
        
        # Check and deduct item from player's inventory
        if db_provider.volticar_db is None:
            raise HTTPException(status_code=503, detail="Database service not initialized")
        update_result = await db_provider.volticar_db["player_items"].update_one(
            {"user_id": current_user.user_id, "item_id": payload.item_id, "quantity": {"$gt": 0}},
            {"$inc": {"quantity": -1}}
        )
        if update_result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Item not found in inventory or quantity is zero.")

    # 4. Update game state based on choice (simplified logic)
    # Mark the event as resolved
    if db_provider.volticar_db is None:
        raise HTTPException(status_code=503, detail="Database service not initialized")
    await db_provider.volticar_db["GameSessions"].update_one(
        {"game_session_id": session_id, "events.event_id": payload.event_id},
        {"$set": {"events.$.resolved": True, "events.$.resolved_choice": payload.choice}}
    )

    return {"message": f"Event {payload.event_id} resolved with choice: {payload.choice}."}

@router.get("/shop/items", response_model=List[ShopItem], summary="獲取商店中的所有商品")
async def get_shop_items():
    """
    列出遊戲商店中所有可供購買的商品。
    """
    if db_provider.volticar_db is None:
        raise HTTPException(status_code=503, detail="Database service not initialized")
    items_cursor = db_provider.volticar_db["ShopItems"].find()
    items = await items_cursor.to_list(length=100) # Limit to 100 items
    return items

@router.post("/shop/purchase", summary="在商店購買商品")
async def purchase_shop_item(
    payload: PurchasePayload,
    current_user: User = Depends(get_current_user)
):
    """
    允許玩家使用碳積分在商店中購買商品。
    - 系統會檢查玩家的碳積分餘額是否足夠。
    - 購買成功後，會扣除相應的碳積分，並將商品添加到玩家的倉庫中。
    """
    if db_provider.volticar_db is None:
        raise HTTPException(status_code=503, detail="Database service not initialized")
    # 1. Find the item and its price
    item_to_purchase = await db_provider.volticar_db["ShopItems"].find_one({"item_id": payload.item_id})
    if not item_to_purchase:
        raise HTTPException(status_code=404, detail="Item not found.")

    total_cost = item_to_purchase['price'] * payload.quantity

    # 2. Check if user has enough points
    if current_user.carbon_points < total_cost:
        raise HTTPException(status_code=400, detail="Not enough carbon points.")

    # 3. Deduct points
    await db_provider.users_collection.update_one(
        {"user_id": current_user.user_id},
        {"$inc": {"carbon_points": -total_cost}}
    )

    # 4. Add item to player's inventory
    # Using upsert to either add a new item or increment the quantity of an existing one
    if db_provider.volticar_db is None:
        raise HTTPException(status_code=503, detail="Database service not initialized")
    await db_provider.volticar_db["PlayerItems"].update_one(
        {"user_id": current_user.user_id, "item_id": payload.item_id},
        {"$inc": {"quantity": payload.quantity}},
        upsert=True
    )

    return {"message": f"Successfully purchased {payload.quantity} of {item_to_purchase['name']}."}

@router.post("/vehicles/{instance_id}/upgrade", summary="升級玩家的車輛")
async def upgrade_vehicle(
    instance_id: str,
    payload: VehicleUpgradePayload,
    current_user: User = Depends(get_current_user)
):
    """
    允許玩家使用碳積分來升級他們擁有的車輛。
    - **instance_id**: 要升級的車輛實例的 ID。
    - **upgrade_type**: 要升級的屬性（例如，`tire_durability` 或 `battery_health`）。
    - 系統會檢查並扣除升級所需的碳積分。
    """
    # 1. Find the player-owned vehicle
    vehicle = await db_provider.player_owned_vehicles_collection.find_one({
        "instance_id": instance_id,
        "user_id": current_user.user_id
    })
    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found or does not belong to the current user.")

    # 2. Determine upgrade cost and effect
    upgrade_costs = {
        "tire_durability": 100,
        "battery_health": 200
    }
    upgrade_type = payload.upgrade_type
    if upgrade_type not in upgrade_costs:
        raise HTTPException(status_code=400, detail="Invalid upgrade type.")

    cost = upgrade_costs[upgrade_type]

    # 3. Check for enough points
    if current_user.carbon_points < cost:
        raise HTTPException(status_code=400, detail="Not enough carbon points for upgrade.")

    # 4. Deduct points and apply upgrade
    await db_provider.users_collection.update_one(
        {"user_id": current_user.user_id},
        {"$inc": {"carbon_points": -cost}}
    )

    update_field = {}
    if upgrade_type == "tire_durability":
        update_field = {"$inc": {"current_condition": 0.1}} # Increase condition by 10%
    elif upgrade_type == "battery_health":
        update_field = {"$inc": {"battery_health": 5}} # Increase battery health by 5%

    await db_provider.player_owned_vehicles_collection.update_one(
        {"instance_id": instance_id},
        update_field
    )

    return {"message": f"Vehicle {instance_id} upgraded successfully: {upgrade_type}."}

@router.get("/environment/weather", summary="獲取指定座標的當前天氣")
async def get_environment_weather(
    lat: float,
    lon: float
):
    """
    （模擬整合）從外部天氣 API (Open-Meteo) 獲取指定經緯度的當前天氣狀況。
    - 將天氣代碼簡化為 `sunny`, `cloudy`, `rainy` 等狀態。
    """
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()
            weather_code = data.get("current_weather", {}).get("weathercode", 0)
            
            # Simplified mapping of weather codes to conditions
            if weather_code in [0, 1]:
                condition = "sunny"
            elif weather_code in [2, 3]:
                condition = "cloudy"
            elif weather_code > 50:
                condition = "rainy"
            else:
                condition = "unknown"

            return {"weather": condition, "temperature": data.get("current_weather", {}).get("temperature")}
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=e.response.status_code, detail="Error fetching weather data.")
        except Exception:
            raise HTTPException(status_code=500, detail="Could not fetch weather data.")
