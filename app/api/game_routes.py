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

router = APIRouter()

# Dependency to get the database instance
async def get_database():
    return await get_db()

@router.post("/integrations/charge-session/report", status_code=201)
async def report_charge_session(
    report: ChargeSessionReport,
    db = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    # Find the vehicle to ensure it belongs to the current user
    vehicle = await db.PlayerOwnedVehicles.find_one({
        "instance_id": report.vehicle_instance_id,
        "user_id": current_user.user_id
    })

    if not vehicle:
        raise HTTPException(status_code=404, detail="Vehicle not found or does not belong to the current user.")

    # Calculate carbon points, e.g., 1 kWh = 10 points
    carbon_points_earned = int(report.kwh_added * 10)

    # Update user's carbon points
    await db.users.update_one(
        {"user_id": current_user.user_id},
        {"$inc": {"carbon_points": carbon_points_earned}}
    )

    return {
        "message": "Charge session reported successfully.",
        "kwh_added": report.kwh_added,
        "carbon_points_earned": carbon_points_earned
    }

@router.post("/player/check-in", status_code=200)
async def check_in_at_station(
    payload: CheckInPayload,
    db = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    station = await db.Stations.find_one({"StationID": payload.station_id})
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")

    station_coords = (station['PositionLat'], station['PositionLon'])
    user_coords = (payload.latitude, payload.longitude)

    distance = geodesic(station_coords, user_coords).meters

    if distance > 100: # 100 meters
        raise HTTPException(status_code=400, detail=f"User is not within the station's range. Distance: {distance:.2f} meters.")

    # Record the check-in
    await db.users.update_one(
        {"user_id": current_user.user_id},
        {"$set": {"last_check_in": {
            "station_id": payload.station_id,
            "timestamp": datetime.now()
        }}}
    )

    return {"message": f"Successfully checked in at station {payload.station_id}"}

@router.get("/stations/{station_id}/tasks", response_model=List[GameTask])
async def get_station_tasks(
    station_id: str,
    db = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    # 1. Verify check-in
    if not current_user.last_check_in or current_user.last_check_in['station_id'] != station_id:
        raise HTTPException(status_code=403, detail="User must be checked in at this station to get tasks.")

    # 2. Check cooldown
    last_task_record = await db.PlayerStationTasks.find_one(
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
    
    await db.GameTasks.insert_one(new_task.dict(by_alias=True))
    
    # Record task generation time for cooldown
    await db.PlayerStationTasks.insert_one({
        "user_id": current_user.user_id,
        "station_id": station_id,
        "generated_at": datetime.now()
    })

    return [new_task]

import random

@router.post("/game-session/{session_id}/trigger-event", response_model=GameEvent)
async def trigger_game_event(
    session_id: str,
    db = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
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
    
    await db.GameEvents.insert_one(game_event.dict(by_alias=True))

    # Associate event with the game session
    await db.GameSessions.update_one(
        {"game_session_id": session_id, "user_id": current_user.user_id},
        {"$push": {"events": game_event.dict(by_alias=True)}}
    )

    return game_event

@router.post("/game-session/{session_id}/resolve-event")
async def resolve_game_event(
    session_id: str,
    payload: ResolveEventPayload,
    db = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    # 1. Find the game session and the specific event
    game_session = await db.GameSessions.find_one({
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
        update_result = await db.player_items.update_one(
            {"user_id": current_user.user_id, "item_id": payload.item_id, "quantity": {"$gt": 0}},
            {"$inc": {"quantity": -1}}
        )
        if update_result.modified_count == 0:
            raise HTTPException(status_code=400, detail="Item not found in inventory or quantity is zero.")

    # 4. Update game state based on choice (simplified logic)
    # Mark the event as resolved
    await db.GameSessions.update_one(
        {"game_session_id": session_id, "events.event_id": payload.event_id},
        {"$set": {"events.$.resolved": True, "events.$.resolved_choice": payload.choice}}
    )

    return {"message": f"Event {payload.event_id} resolved with choice: {payload.choice}."}

@router.get("/shop/items", response_model=List[ShopItem])
async def get_shop_items(
    db = Depends(get_database)
):
    items_cursor = db.ShopItems.find()
    items = await items_cursor.to_list(length=100) # Limit to 100 items
    return items

@router.post("/shop/purchase")
async def purchase_shop_item(
    payload: PurchasePayload,
    db = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    # 1. Find the item and its price
    item_to_purchase = await db.ShopItems.find_one({"item_id": payload.item_id})
    if not item_to_purchase:
        raise HTTPException(status_code=404, detail="Item not found.")

    total_cost = item_to_purchase['price'] * payload.quantity

    # 2. Check if user has enough points
    if current_user.carbon_points < total_cost:
        raise HTTPException(status_code=400, detail="Not enough carbon points.")

    # 3. Deduct points
    await db.users.update_one(
        {"user_id": current_user.user_id},
        {"$inc": {"carbon_points": -total_cost}}
    )

    # 4. Add item to player's inventory
    # Using upsert to either add a new item or increment the quantity of an existing one
    await db.PlayerItems.update_one(
        {"user_id": current_user.user_id, "item_id": payload.item_id},
        {"$inc": {"quantity": payload.quantity}},
        upsert=True
    )

    return {"message": f"Successfully purchased {payload.quantity} of {item_to_purchase['name']}."}

@router.post("/vehicles/{instance_id}/upgrade")
async def upgrade_vehicle(
    instance_id: str,
    payload: VehicleUpgradePayload,
    db = Depends(get_database),
    current_user: User = Depends(get_current_user)
):
    # 1. Find the player-owned vehicle
    vehicle = await db.PlayerOwnedVehicles.find_one({
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
    await db.users.update_one(
        {"user_id": current_user.user_id},
        {"$inc": {"carbon_points": -cost}}
    )

    update_field = {}
    if upgrade_type == "tire_durability":
        update_field = {"$inc": {"current_condition": 0.1}} # Increase condition by 10%
    elif upgrade_type == "battery_health":
        update_field = {"$inc": {"battery_health": 5}} # Increase battery health by 5%

    await db.PlayerOwnedVehicles.update_one(
        {"instance_id": instance_id},
        update_field
    )

    return {"message": f"Vehicle {instance_id} upgraded successfully: {upgrade_type}."}

@router.get("/environment/weather")
async def get_environment_weather(
    lat: float,
    lon: float
):
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
