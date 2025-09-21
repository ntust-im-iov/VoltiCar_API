from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List
from datetime import datetime
import httpx
import uuid
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
    LoadCargoPayload,
    CargoItemSnapshot,
    GameStateResponse,
    GameProgress,
    VehicleStatus,
    PendingEvent,
    PendingEventChoice,
    GameSession as GameSessionModel,
    ResolveEventResponse,
    EventOutcome,
    GameCompletionResponse,
    OutcomeSummary,
    RewardSummary,
    PenaltySummary,
    TotalEarnedSummary,
    PlayerUpdate,
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

@router.post("/game-session/{session_id}/resolve-event", response_model=ResolveEventResponse, summary="解決一個遊戲事件")
async def resolve_game_event(
    session_id: str,
    payload: ResolveEventPayload,
    current_user: User = Depends(get_current_user)
):
    """
    玩家對一個待處理的事件做出選擇，並根據選擇計算後果。
    """
    # 1. 獲取遊戲會話
    session_doc = await db_provider.game_sessions_collection.find_one({
        "game_session_id": session_id,
        "user_id": current_user.user_id
    })
    if not session_doc:
        raise HTTPException(status_code=404, detail="Game session not found.")
    
    game_session = GameSessionModel.model_validate(session_doc)

    # 2. 驗證事件和選擇
    if game_session.status != "event_pending" or not game_session.pending_event:
        raise HTTPException(status_code=400, detail="No pending event to resolve.")
    
    if game_session.pending_event.event_id != payload.event_id:
        raise HTTPException(status_code=400, detail="Event ID mismatch.")

    valid_choice_ids = [c.choice_id for c in game_session.pending_event.choices]
    if payload.choice_id not in valid_choice_ids:
        raise HTTPException(status_code=400, detail="Invalid choice for this event.")

    # 3. 處理後果
    outcome_message = ""
    time_penalty = 0
    distance_increase = 0.0
    item_consumed = None

    # 簡易後果邏輯
    if "wait" in payload.choice_id:
        time_penalty = random.randint(30, 120)
        outcome_message = f"你選擇了耐心等待，多花了 {time_penalty} 秒。"
    elif "detour" in payload.choice_id:
        time_penalty = random.randint(10, 60)
        distance_increase = round(random.uniform(0.5, 3.0), 2)
        outcome_message = f"你選擇了繞路，多走了 {distance_increase} 公里，多花了 {time_penalty} 秒。"
    elif "use_item" in payload.choice_id:
        if not payload.item_id:
            raise HTTPException(status_code=400, detail="item_id is required for this choice.")
        
        # 檢查並扣除物品
        update_result = await db_provider.player_warehouse_items_collection.update_one(
            {"user_id": current_user.user_id, "item_id": payload.item_id, "quantity": {"$gt": 0}},
            {"$inc": {"quantity": -1}}
        )
        if update_result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Item not found or not enough quantity.")
        
        item_consumed = payload.item_id
        outcome_message = "你使用了一個道具，成功化解了危機！"

    # 4. 更新遊戲會話狀態
    game_session.estimated_duration_seconds += time_penalty
    game_session.total_distance_km += distance_increase
    game_session.status = "in_progress"
    game_session.pending_event = None
    game_session.last_updated_at = datetime.now()

    await db_provider.game_sessions_collection.update_one(
        {"game_session_id": session_id},
        {"$set": game_session.model_dump(exclude={"id"})}
    )

    # 5. 準備並返回回應
    event_outcome = EventOutcome(
        time_penalty_seconds=time_penalty,
        distance_increase_km=distance_increase,
        item_consumed=item_consumed,
        message=outcome_message
    )
    
    next_state = GameStateResponse(
        session_id=game_session.game_session_id,
        status=game_session.status,
        progress=game_session.progress,
        vehicle_status=game_session.vehicle_status,
        pending_event=game_session.pending_event
    )

    return ResolveEventResponse(
        message=outcome_message,
        outcome=event_outcome,
        next_state=next_state
    )

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

@router.post("/game-session/{session_id}/load-cargo", summary="將物品從倉庫裝載到車輛")
async def load_cargo_to_vehicle(
    session_id: str,
    payload: LoadCargoPayload,
    current_user: User = Depends(get_current_user)
):
    """
    將玩家倉庫中的物品裝載到進行中的遊戲會話的車輛上。
    - 驗證遊戲會話是否存在且屬於當前玩家。
    - 驗證玩家倉庫中是否有足夠的物品。
    - 檢查裝載後是否會超過車輛的載重和容積限制。
    - 從倉庫扣除物品並將其添加到遊戲會話的 `cargo_snapshot` 中。
    """
    # 1. 獲取遊戲會話
    game_session = await db_provider.game_sessions_collection.find_one({
        "game_session_id": session_id,
        "user_id": current_user.user_id
    })
    if not game_session:
        raise HTTPException(status_code=404, detail="Game session not found.")
    if game_session['status'] != 'in_progress':
        raise HTTPException(status_code=400, detail="Cargo can only be loaded in 'in_progress' sessions.")

    # 2. 獲取車輛定義以檢查限制
    vehicle_instance = await db_provider.player_owned_vehicles_collection.find_one({
        "instance_id": game_session["used_vehicle_id"],
        "user_id": current_user.user_id
    })
    if not vehicle_instance:
        raise HTTPException(status_code=404, detail="Vehicle used in session not found.")
        
    vehicle_definition = await db_provider.vehicle_definitions_collection.find_one({
        "vehicle_id": vehicle_instance["vehicle_id"]
    })
    if not vehicle_definition:
        raise HTTPException(status_code=404, detail="Vehicle definition not found.")

    max_weight = vehicle_definition['max_load_weight']
    max_volume = vehicle_definition['max_load_volume']

    # 3. 計算當前貨物總重和總體積
    current_weight = sum(item['quantity'] * item['weight_per_unit'] for item in game_session.get('cargo_snapshot', []))
    current_volume = sum(item['quantity'] * item['volume_per_unit'] for item in game_session.get('cargo_snapshot', []))

    items_to_add_snapshot = []
    
    for item_to_load in payload.items:
        # 4. 獲取物品定義
        item_def = await db_provider.item_definitions_collection.find_one({"item_id": item_to_load.item_id})
        if not item_def:
            raise HTTPException(status_code=404, detail=f"Item with ID {item_to_load.item_id} not found.")

        # 5. 檢查倉庫庫存
        warehouse_item = await db_provider.player_warehouse_items_collection.find_one({
            "user_id": current_user.user_id,
            "item_id": item_to_load.item_id
        })
        if not warehouse_item or warehouse_item['quantity'] < item_to_load.quantity:
            raise HTTPException(status_code=400, detail=f"Not enough quantity for item {item_def['name']}. Warehouse has {warehouse_item.get('quantity', 0)}.")

        # 6. 檢查負重和容積
        additional_weight = item_to_load.quantity * item_def['weight_per_unit']
        additional_volume = item_to_load.quantity * item_def['volume_per_unit']

        if current_weight + additional_weight > max_weight:
            raise HTTPException(status_code=400, detail=f"Loading item {item_def['name']} exceeds vehicle's max weight.")
        if current_volume + additional_volume > max_volume:
            raise HTTPException(status_code=400, detail=f"Loading item {item_def['name']} exceeds vehicle's max volume.")

        current_weight += additional_weight
        current_volume += additional_volume

        # 7. 從倉庫扣除物品
        new_quantity = warehouse_item['quantity'] - item_to_load.quantity
        if new_quantity > 0:
            await db_provider.player_warehouse_items_collection.update_one(
                {"_id": warehouse_item['_id']},
                {"$set": {"quantity": new_quantity}}
            )
        else:
            await db_provider.player_warehouse_items_collection.delete_one({"_id": warehouse_item['_id']})
        
        # 準備要加入 cargo_snapshot 的物品
        snapshot = CargoItemSnapshot(
            item_id=item_def['item_id'],
            name=item_def['name'],
            quantity=item_to_load.quantity,
            weight_per_unit=item_def['weight_per_unit'],
            volume_per_unit=item_def['volume_per_unit'],
            base_value_per_unit=item_def['base_value_per_unit']
        )
        items_to_add_snapshot.append(snapshot.model_dump())

    # 8. 更新遊戲會話的 cargo_snapshot
    if items_to_add_snapshot:
        await db_provider.game_sessions_collection.update_one(
            {"game_session_id": session_id},
            {"$push": {"cargo_snapshot": {"$each": items_to_add_snapshot}}}
        )

    updated_session = await db_provider.game_sessions_collection.find_one({"game_session_id": session_id})

    return {
        "message": "Cargo loaded successfully.",
        "game_session_id": session_id,
        "updated_cargo": updated_session.get('cargo_snapshot', [])
    }

@router.get("/game-session/{session_id}/state", response_model=GameStateResponse, summary="獲取遊戲會話的即時狀態")
async def get_game_session_state(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    獲取當前遊戲會話的即時狀態，用於前端輪詢以驅動遊戲進程。
    - 如果沒有待處理事件，則推進遊戲進度。
    - 有一定機率觸發新的隨機事件。
    """
    # 1. 獲取遊戲會話
    session_doc = await db_provider.game_sessions_collection.find_one({
        "game_session_id": session_id,
        "user_id": current_user.user_id
    })
    if not session_doc:
        raise HTTPException(status_code=404, detail="Game session not found.")

    game_session = GameSessionModel.model_validate(session_doc)

    # 如果會話已完成或已有待處理事件，直接返回當前狀態
    if game_session.status in ["completed", "event_pending"]:
        return GameStateResponse(
            session_id=game_session.game_session_id,
            status=game_session.status,
            progress=game_session.progress,
            vehicle_status=game_session.vehicle_status,
            pending_event=game_session.pending_event
        )

    # --- 遊戲進度推進 ---
    time_now = datetime.now()
    time_since_last_update = (time_now - game_session.last_updated_at).total_seconds()
    
    # 假設速度為 60 km/h (1 km/min or 1/60 km/s)
    speed_km_per_second = 60 / 3600
    distance_increment = time_since_last_update * speed_km_per_second
    
    game_session.progress.distance_traveled_km += distance_increment
    
    if game_session.total_distance_km > 0:
        game_session.progress.percentage = min(
            (game_session.progress.distance_traveled_km / game_session.total_distance_km) * 100,
            100
        )
    
    time_left = game_session.estimated_duration_seconds - (time_now - game_session.start_time).total_seconds()
    game_session.progress.estimated_time_left_seconds = max(0, int(time_left))

    # --- 車輛狀態更新 (簡易模擬) ---
    game_session.vehicle_status.battery_level = max(0, game_session.vehicle_status.battery_level - (time_since_last_update * 0.01))

    # --- 隨機事件觸發 ---
    EVENT_TRIGGER_PROBABILITY = 0.15 # 15% 機率
    if random.random() < EVENT_TRIGGER_PROBABILITY:
        all_events = await db_provider.volticar_db["GameEvents"].find().to_list(length=100)
        if all_events:
            chosen_event_doc = random.choice(all_events)
            
            # 假設 choices 在 DB 中是像 ["wait", "detour"] 的格式
            # 我們需要轉換成 API 需要的格式
            choices_for_api = []
            for choice_text in chosen_event_doc.get("choices", []):
                 choices_for_api.append(PendingEventChoice(choice_id=choice_text.lower().replace(" ", "_"), text=choice_text))

            pending_event = PendingEvent(
                event_id=chosen_event_doc["event_id"],
                name=chosen_event_doc["name"],
                description=chosen_event_doc["description"],
                choices=choices_for_api
            )
            game_session.pending_event = pending_event
            game_session.status = "event_pending"

    # --- 檢查遊戲是否完成 ---
    if game_session.progress.percentage >= 100:
        game_session.status = "completed"
        game_session.end_time = time_now

    game_session.last_updated_at = time_now

    # --- 更新資料庫 ---
    await db_provider.game_sessions_collection.update_one(
        {"game_session_id": session_id},
        {"$set": game_session.model_dump(exclude={"id"})}
    )

    return GameStateResponse(
        session_id=game_session.game_session_id,
        status=game_session.status,
        progress=game_session.progress,
        vehicle_status=game_session.vehicle_status,
        pending_event=game_session.pending_event
    )

@router.post("/game-session/{session_id}/complete", response_model=GameCompletionResponse, summary="結束遊戲會話並進行結算")
async def complete_game_session(
    session_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    結束一個遊戲會話，計算最終獎勵與懲罰，並更新玩家資料。
    """
    # 1. 獲取遊戲會話
    session_doc = await db_provider.game_sessions_collection.find_one({
        "game_session_id": session_id,
        "user_id": current_user.user_id
    })
    if not session_doc:
        raise HTTPException(status_code=404, detail="Game session not found.")
    
    game_session = GameSessionModel.model_validate(session_doc)

    # 2. 驗證遊戲是否真的可以完成
    if game_session.status != "completed":
         # 允許手動完成，但進度必須是100%
        if game_session.progress.percentage < 100:
            raise HTTPException(status_code=400, detail=f"Game session is not yet completed. Progress: {game_session.progress.percentage:.2f}%")
        game_session.status = "completed"
        if not game_session.end_time:
            game_session.end_time = datetime.now()

    # 3. 計算結算結果
    time_taken = int((game_session.end_time - game_session.start_time).total_seconds())
    
    # 簡易獎勵計算邏輯
    base_exp = int(game_session.total_distance_km * 10)
    base_currency = int(game_session.total_distance_km * 50)
    
    time_bonus_exp = max(0, int((game_session.estimated_duration_seconds - time_taken) * 0.1))
    
    # 假設車輛健康度直接影響貨物損壞
    cargo_damage = round(100 - game_session.vehicle_status.current_health, 2)
    no_damage_bonus_currency = 100 if cargo_damage <= 1 else 0
    
    damage_penalty_currency = int(base_currency * (cargo_damage / 100))

    total_exp = base_exp + time_bonus_exp
    total_currency = base_currency + no_damage_bonus_currency - damage_penalty_currency

    # 4. 更新玩家資料
    player_doc = await db_provider.users_collection.find_one({"user_id": current_user.user_id})
    if not player_doc:
        raise HTTPException(status_code=404, detail="Player data not found for the user.")

    # 假設玩家等級/經驗等資訊存在 users collection
    current_level = player_doc.get("level", 1)
    current_exp = player_doc.get("experience", 0)
    current_currency = player_doc.get("currency_balance", 0)

    new_exp = current_exp + total_exp
    new_currency = current_currency + total_currency
    
    # 簡易升級邏輯: 每 1000 經驗升一級
    exp_for_next_level = 1000
    while new_exp >= exp_for_next_level:
        new_exp -= exp_for_next_level
        current_level += 1
        exp_for_next_level = int(exp_for_next_level * 1.5) # 升級所需經驗增加

    await db_provider.users_collection.update_one(
        {"user_id": current_user.user_id},
        {"$set": {
            "level": current_level,
            "experience": new_exp,
            "currency_balance": new_currency
        }}
    )
    
    # 5. 準備回應
    outcome = OutcomeSummary(
        distance_traveled_km=round(game_session.progress.distance_traveled_km, 2),
        time_taken_seconds=time_taken,
        cargo_damage_percentage=cargo_damage,
        base_reward=RewardSummary(experience=base_exp, currency=base_currency),
        bonus=RewardSummary(experience=time_bonus_exp, currency=no_damage_bonus_currency),
        penalties=PenaltySummary(damage_penalty=damage_penalty_currency),
        total_earned=TotalEarnedSummary(experience=total_exp, currency=total_currency)
    )
    
    player_update = PlayerUpdate(
        level=current_level,
        experience=new_exp,
        currency_balance=new_currency
    )

    return GameCompletionResponse(
        message="任務完成！成功將電力運送到目的地。",
        outcome_summary=outcome,
        player_update=player_update
    )
