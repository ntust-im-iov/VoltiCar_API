import os
from typing import List, Any, Dict, Optional
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates # type: ignore
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.database import mongodb as db_provider
from app.utils.auth import verify_password, get_password_hash
import secrets
from datetime import datetime

# 建立一個 FastAPI 實例來掛載 admin app
admin_api = FastAPI()

# Templates 配置
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "admin_templates"))

# HTTP Basic Auth
security = HTTPBasic()

async def get_current_admin(credentials: HTTPBasicCredentials = Depends(security)):
    """
    驗證管理員身份
    """
    if db_provider.volticar_db is None:
        raise HTTPException(status_code=503, detail="Database service not available")

    admin_collection = db_provider.volticar_db["admins"]
    admin = await admin_collection.find_one({"username": credentials.username})
    
    if not admin or not verify_password(credentials.password, admin["password"]):
        raise HTTPException(
            status_code=401,
            detail="Invalid admin credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# --- 管理界面路由 ---

@admin_api.get("/", response_class=HTMLResponse)
async def admin_dashboard(request: Request, admin: str = Depends(get_current_admin)):
    """
    管理界面首頁
    """
    if db_provider.volticar_db is None:
        raise HTTPException(status_code=503, detail="Database service not available")

    # 獲取統計數據
    stats = {
        "users_count": await db_provider.users_collection.count_documents({}),
        "vehicles_count": await db_provider.vehicle_definitions_collection.count_documents({}),
        "items_count": await db_provider.item_definitions_collection.count_documents({}),
        "tasks_count": await db_provider.task_definitions_collection.count_documents({}),
        "destinations_count": await db_provider.destinations_collection.count_documents({}),
        "game_events_count": await db_provider.volticar_db["GameEvents"].count_documents({}),
        "shop_items_count": await db_provider.volticar_db["ShopItems"].count_documents({}),
        "player_data_count": await db_provider.players_collection.count_documents({}),
    }
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "admin": admin,
        "stats": stats
    })

@admin_api.get("/users", response_class=HTMLResponse)
async def list_users(request: Request, admin: str = Depends(get_current_admin)):
    """
    用戶列表
    """
    if db_provider.users_collection is None:
        raise HTTPException(status_code=503, detail="Database service not available")
    users_cursor = db_provider.users_collection.find().limit(100)
    users = await users_cursor.to_list(length=100)
    
    # 轉換 ObjectId 為字串
    for user in users:
        user["_id"] = str(user["_id"])
    
    return templates.TemplateResponse("list.html", {
        "request": request,
        "admin": admin,
        "title": "用戶管理",
        "items": users,
        "collection": "users"
    })

@admin_api.get("/player-data", response_class=HTMLResponse)
async def list_player_data(request: Request, admin: str = Depends(get_current_admin)):
    """
    玩家資料列表
    """
    if db_provider.players_collection is None:
        raise HTTPException(status_code=503, detail="Database service not available")
    player_data_cursor = db_provider.players_collection.find().limit(100)
    player_data = await player_data_cursor.to_list(length=100)
    
    # 轉換 ObjectId 為字串
    for data in player_data:
        data["_id"] = str(data["_id"])
    
    return templates.TemplateResponse("list.html", {
        "request": request,
        "admin": admin,
        "title": "玩家資料",
        "items": player_data,
        "collection": "player-data"
    })


@admin_api.get("/vehicles", response_class=HTMLResponse)
async def list_vehicles(request: Request, admin: str = Depends(get_current_admin)):
    """
    車輛定義列表
    """
    if db_provider.vehicle_definitions_collection is None:
        raise HTTPException(status_code=503, detail="Database service not available")
    vehicles_cursor = db_provider.vehicle_definitions_collection.find().limit(100)
    vehicles = await vehicles_cursor.to_list(length=100)
    
    # 轉換 ObjectId 為字串
    for vehicle in vehicles:
        vehicle["_id"] = str(vehicle["_id"])
    
    return templates.TemplateResponse("list.html", {
        "request": request,
        "admin": admin,
        "title": "車輛定義",
        "items": vehicles,
        "collection": "vehicles"
    })

@admin_api.get("/items", response_class=HTMLResponse)
async def list_items(request: Request, admin: str = Depends(get_current_admin)):
    """
    物品定義列表
    """
    if db_provider.item_definitions_collection is None:
        raise HTTPException(status_code=503, detail="Database service not available")
    items_cursor = db_provider.item_definitions_collection.find().limit(100)
    items = await items_cursor.to_list(length=100)
    
    # 轉換 ObjectId 為字串
    for item in items:
        item["_id"] = str(item["_id"])
    
    return templates.TemplateResponse("list.html", {
        "request": request,
        "admin": admin,
        "title": "物品定義",
        "items": items,
        "collection": "items"
    })

@admin_api.get("/tasks", response_class=HTMLResponse)
async def list_tasks(request: Request, admin: str = Depends(get_current_admin)):
    """
    任務定義列表
    """
    if db_provider.task_definitions_collection is None:
        raise HTTPException(status_code=503, detail="Database service not available")
    tasks_cursor = db_provider.task_definitions_collection.find().limit(100)
    tasks = await tasks_cursor.to_list(length=100)
    
    # 轉換 ObjectId 為字串
    for task in tasks:
        task["_id"] = str(task["_id"])
    
    return templates.TemplateResponse("list.html", {
        "request": request,
        "admin": admin,
        "title": "任務定義",
        "items": tasks,
        "collection": "tasks"
    })

@admin_api.get("/destinations", response_class=HTMLResponse)
async def list_destinations(request: Request, admin: str = Depends(get_current_admin)):
    """
    目的地列表
    """
    if db_provider.destinations_collection is None:
        raise HTTPException(status_code=503, detail="Database service not available")
    destinations_cursor = db_provider.destinations_collection.find().limit(100)
    destinations = await destinations_cursor.to_list(length=100)
    
    # 轉換 ObjectId 為字串
    for destination in destinations:
        destination["_id"] = str(destination["_id"])
    
    return templates.TemplateResponse("list.html", {
        "request": request,
        "admin": admin,
        "title": "目的地",
        "items": destinations,
        "collection": "destinations"
    })

@admin_api.get("/vehicles/add", response_class=HTMLResponse)
async def add_vehicle_form(request: Request, admin: str = Depends(get_current_admin)):
    """
    顯示新增車輛定義的表單
    """
    return templates.TemplateResponse("add_vehicle.html", {
        "request": request,
        "admin": admin,
        "title": "新增車輛定義"
    })

@admin_api.post("/vehicles/add", response_class=HTMLResponse)
async def create_vehicle(
    request: Request,
    admin: str = Depends(get_current_admin),
    name: str = Form(...),
    type: str = Form(...),
    description: Optional[str] = Form(None),
    max_load_weight: float = Form(...),
    max_load_volume: float = Form(...),
    base_price: Optional[int] = Form(None),
    rental_price_per_session: Optional[int] = Form(None),
    availability_type: str = Form(...),
    required_level_to_unlock: int = Form(1),
    icon_url: Optional[str] = Form(None),
    image_url: Optional[str] = Form(None),
):
    """
    處理新增車輛定義的表單提交
    """
    if db_provider.vehicle_definitions_collection is None:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        new_vehicle_data = {
            "name": name,
            "type": type,
            "description": description,
            "max_load_weight": max_load_weight,
            "max_load_volume": max_load_volume,
            "base_price": base_price,
            "rental_price_per_session": rental_price_per_session,
            "availability_type": availability_type,
            "required_level_to_unlock": required_level_to_unlock,
            "icon_url": icon_url,
            "image_url": image_url,
        }
        
        # Pydantic validation
        from app.models.game_models import VehicleDefinition
        vehicle = VehicleDefinition(**new_vehicle_data)
        
        # Insert into MongoDB
        await db_provider.vehicle_definitions_collection.insert_one(vehicle.model_dump(by_alias=True, exclude_none=True))
        
        return RedirectResponse(url="/admin/vehicles", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("add_vehicle.html", {
            "request": request,
            "admin": admin,
            "title": "新增車輛定義",
            "error": str(e),
            "form_data": new_vehicle_data # Pass back form data to pre-fill
        })

@admin_api.get("/items/add", response_class=HTMLResponse)
async def add_item_form(request: Request, admin: str = Depends(get_current_admin)):
    """
    顯示新增物品定義的表單
    """
    return templates.TemplateResponse("add_item.html", {
        "request": request,
        "admin": admin,
        "title": "新增物品定義"
    })

@admin_api.post("/items/add", response_class=HTMLResponse)
async def create_item(
    request: Request,
    admin: str = Depends(get_current_admin),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    category: str = Form(...),
    weight_per_unit: float = Form(...),
    volume_per_unit: float = Form(...),
    base_value_per_unit: int = Form(...),
    is_fragile: bool = Form(False),
    is_perishable: bool = Form(False),
    spoil_duration_hours: Optional[int] = Form(None),
    required_permit_type: Optional[str] = Form(None),
    icon_url: Optional[str] = Form(None),
):
    """
    處理新增物品定義的表單提交
    """
    if db_provider.item_definitions_collection is None:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        new_item_data = {
            "name": name,
            "description": description,
            "category": category,
            "weight_per_unit": weight_per_unit,
            "volume_per_unit": volume_per_unit,
            "base_value_per_unit": base_value_per_unit,
            "is_fragile": is_fragile,
            "is_perishable": is_perishable,
            "spoil_duration_hours": spoil_duration_hours,
            "required_permit_type": required_permit_type,
            "icon_url": icon_url,
        }
        
        # Pydantic validation
        from app.models.game_models import ItemDefinition
        item = ItemDefinition(**new_item_data)
        
        # Insert into MongoDB
        await db_provider.item_definitions_collection.insert_one(item.model_dump(by_alias=True, exclude_none=True))
        
        return RedirectResponse(url="/admin/items", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("add_item.html", {
            "request": request,
            "admin": admin,
            "title": "新增物品定義",
            "error": str(e),
            "form_data": new_item_data # Pass back form data to pre-fill
        })

@admin_api.get("/tasks/add", response_class=HTMLResponse)
async def add_task_form(request: Request, admin: str = Depends(get_current_admin)):
    """
    顯示新增任務定義的表單
    """
    return templates.TemplateResponse("add_task.html", {
        "request": request,
        "admin": admin,
        "title": "新增任務定義"
    })

@admin_api.post("/tasks/add", response_class=HTMLResponse)
async def create_task(
    request: Request,
    admin: str = Depends(get_current_admin),
    title: str = Form(...),
    description: str = Form(...),
    mode: str = Form(...),
    required_player_level: int = Form(1),
    required_vehicle_type: Optional[str] = Form(None),
    time_limit_seconds: Optional[int] = Form(None),
    pickup_location_id: Optional[str] = Form(None),
    destination_id: Optional[str] = Form(None),
    min_cargo_value: Optional[int] = Form(None),
    deliver_items: Optional[str] = Form(None),
    experience_points: int = Form(...),
    currency: int = Form(0),
    reward_items: Optional[str] = Form(None),
    is_repeatable: bool = Form(False),
    repeat_cooldown_hours: Optional[int] = Form(None),
    is_active: bool = Form(True),
):
    """
    處理新增任務定義的表單提交
    """
    if db_provider.task_definitions_collection is None:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # 解析 deliver_items
        deliver_items_list = []
        if deliver_items:
            import json
            deliver_items_data = json.loads(deliver_items)
            for item in deliver_items_data:
                deliver_items_list.append({
                    "item_id": item["item_id"],
                    "quantity": item["quantity"]
                })

        # 解析 reward_items
        reward_items_list = []
        if reward_items:
            import json
            reward_items_data = json.loads(reward_items)
            for item in reward_items_data:
                reward_items_list.append({
                    "item_id": item["item_id"],
                    "quantity": item["quantity"]
                })

        # 建立任務需求
        requirements = {
            "required_player_level": required_player_level,
            "deliver_items": deliver_items_list if deliver_items_list else None,
            "pickup_location_id": pickup_location_id,
            "destination_id": destination_id,
            "required_vehicle_type": required_vehicle_type,
            "time_limit_seconds": time_limit_seconds,
            "min_cargo_value": min_cargo_value,
        }

        # 建立任務獎勵
        rewards = {
            "experience_points": experience_points,
            "currency": currency,
            "item_rewards": reward_items_list if reward_items_list else None,
        }

        new_task_data = {
            "title": title,
            "description": description,
            "mode": mode,
            "requirements": requirements,
            "rewards": rewards,
            "is_repeatable": is_repeatable,
            "repeat_cooldown_hours": repeat_cooldown_hours,
            "is_active": is_active,
        }
        
        # Pydantic validation
        from app.models.game_models import TaskDefinition
        task = TaskDefinition(**new_task_data)
        
        # Insert into MongoDB
        await db_provider.task_definitions_collection.insert_one(task.model_dump(by_alias=True, exclude_none=True))
        
        return RedirectResponse(url="/admin/tasks", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("add_task.html", {
            "request": request,
            "admin": admin,
            "title": "新增任務定義",
            "error": str(e),
        })

@admin_api.get("/destinations/add", response_class=HTMLResponse)
async def add_destination_form(request: Request, admin: str = Depends(get_current_admin)):
    """
    顯示新增目的地的表單
    """
    return templates.TemplateResponse("add_destination.html", {
        "request": request,
        "admin": admin,
        "title": "新增目的地"
    })

@admin_api.post("/destinations/add", response_class=HTMLResponse)
async def create_destination(
    request: Request,
    admin: str = Depends(get_current_admin),
    name: str = Form(...),
    region: str = Form(...),
    description: Optional[str] = Form(None),
    latitude: float = Form(...),
    longitude: float = Form(...),
    is_unlocked_by_default: bool = Form(True),
    required_player_level: Optional[int] = Form(None),
    available_services: Optional[str] = Form(None),
    icon_url: Optional[str] = Form(None),
):
    """
    處理新增目的地的表單提交
    """
    if db_provider.destinations_collection is None:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # 解析服務列表
        services_list = []
        if available_services:
            import json
            services_list = json.loads(available_services)

        # 建立座標
        coordinates = {
            "type": "Point",
            "coordinates": [longitude, latitude]
        }

        # 建立解鎖需求
        unlock_requirements = None
        if not is_unlocked_by_default:
            unlock_requirements = {
                "required_player_level": required_player_level,
            }

        new_destination_data = {
            "name": name,
            "description": description,
            "region": region,
            "coordinates": coordinates,
            "is_unlocked_by_default": is_unlocked_by_default,
            "unlock_requirements": unlock_requirements,
            "available_services": services_list if services_list else None,
            "icon_url": icon_url,
        }
        
        # Pydantic validation
        from app.models.game_models import Destination
        destination = Destination(**new_destination_data)
        
        # Insert into MongoDB
        await db_provider.destinations_collection.insert_one(destination.model_dump(by_alias=True, exclude_none=True))
        
        return RedirectResponse(url="/admin/destinations", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("add_destination.html", {
            "request": request,
            "admin": admin,
            "title": "新增目的地",
            "error": str(e),
        })

@admin_api.get("/game-events", response_class=HTMLResponse)
async def list_game_events(request: Request, admin: str = Depends(get_current_admin)):
    """
    遊戲事件列表
    """
    try:
        if db_provider.volticar_db is None:
            raise HTTPException(status_code=503, detail="Database service not available")
            
        game_events_collection = db_provider.volticar_db["GameEvents"]
        events_cursor = game_events_collection.find().limit(100)
        events = await events_cursor.to_list(length=100)
        
        # 轉換 ObjectId 為字串
        for event in events:
            event["_id"] = str(event["_id"])
            
        print(f"Found {len(events)} game events")  # Debug log
        
    except Exception as e:
        print(f"Error fetching game events: {e}")  # Debug log
        events = []
    
    return templates.TemplateResponse("list.html", {
        "request": request,
        "admin": admin,
        "title": "遊戲事件",
        "items": events,
        "collection": "game-events"
    })

@admin_api.get("/game-events/add", response_class=HTMLResponse)
async def add_game_event_form(request: Request, admin: str = Depends(get_current_admin)):
    """
    顯示新增遊戲事件的表單
    """
    return templates.TemplateResponse("add_game_event.html", {
        "request": request,
        "admin": admin,
        "title": "新增遊戲事件"
    })

@admin_api.post("/game-events/add", response_class=HTMLResponse)
async def create_game_event(
    request: Request,
    admin: str = Depends(get_current_admin),
    name: str = Form(...),
    description: str = Form(...),
    choices: str = Form(...),
    trigger_probability: Optional[int] = Form(10),
    event_category: Optional[str] = Form("隨機"),
    is_active: bool = Form(True),
):
    """
    處理新增遊戲事件的表單提交
    """
    try:
        if db_provider.volticar_db is None:
            raise HTTPException(status_code=503, detail="Database service not available")
            
        import json
        choices_list = json.loads(choices)
        
        new_event_data = {
            "name": name,
            "description": description,
            "choices": choices_list,
        }
        
        # Pydantic validation
        from app.models.game_models import GameEvent
        event = GameEvent(**new_event_data)
        
        # Insert into MongoDB
        game_events_collection = db_provider.volticar_db["GameEvents"]
        await game_events_collection.insert_one(event.model_dump(by_alias=True, exclude_none=True))
        
        return RedirectResponse(url="/admin/game-events", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("add_game_event.html", {
            "request": request,
            "admin": admin,
            "title": "新增遊戲事件",
            "error": str(e),
        })

@admin_api.get("/shop-items", response_class=HTMLResponse)
async def list_shop_items(request: Request, admin: str = Depends(get_current_admin)):
    """
    商店物品列表
    """
    try:
        if db_provider.volticar_db is None:
            raise HTTPException(status_code=503, detail="Database service not available")
            
        shop_items_collection = db_provider.volticar_db["ShopItems"]
        items_cursor = shop_items_collection.find().limit(100)
        items = await items_cursor.to_list(length=100)
        
        # 轉換 ObjectId 為字串
        for item in items:
            item["_id"] = str(item["_id"])
            
        print(f"Found {len(items)} shop items")  # Debug log
        
    except Exception as e:
        print(f"Error fetching shop items: {e}")  # Debug log
        items = []
    
    return templates.TemplateResponse("list.html", {
        "request": request,
        "admin": admin,
        "title": "商店物品",
        "items": items,
        "collection": "shop-items"
    })

@admin_api.get("/shop-items/add", response_class=HTMLResponse)
async def add_shop_item_form(request: Request, admin: str = Depends(get_current_admin)):
    """
    顯示新增商店物品的表單
    """
    return templates.TemplateResponse("add_shop_item.html", {
        "request": request,
        "admin": admin,
        "title": "新增商店物品"
    })

@admin_api.post("/shop-items/add", response_class=HTMLResponse)
async def create_shop_item(
    request: Request,
    admin: str = Depends(get_current_admin),
    name: str = Form(...),
    description: str = Form(...),
    price: int = Form(...),
    category: str = Form(...),
    discount_price: Optional[int] = Form(None),
    effect_data: Optional[str] = Form(None),
    required_level: int = Form(1),
    daily_limit: Optional[int] = Form(None),
    stack_limit: int = Form(1),
    is_featured: bool = Form(False),
    is_available: bool = Form(True),
    icon_url: Optional[str] = Form(None),
):
    """
    處理新增商店物品的表單提交
    """
    try:
        if db_provider.volticar_db is None:
            raise HTTPException(status_code=503, detail="Database service not available")
            
        new_item_data = {
            "name": name,
            "description": description,
            "price": price,
            "category": category,
            "discount_price": discount_price,
            "effect_data": effect_data,
            "required_level": required_level,
            "daily_limit": daily_limit,
            "stack_limit": stack_limit,
            "is_featured": is_featured,
            "is_available": is_available,
            "icon_url": icon_url,
        }
        
        # Pydantic validation
        from app.models.game_models import ShopItem
        item = ShopItem(**new_item_data)
        
        # Insert into MongoDB
        shop_items_collection = db_provider.volticar_db["ShopItems"]
        await shop_items_collection.insert_one(item.model_dump(by_alias=True, exclude_none=True))
        
        return RedirectResponse(url="/admin/shop-items", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("add_shop_item.html", {
            "request": request,
            "admin": admin,
            "title": "新增商店物品",
            "error": str(e),
        })

# 刪除功能路由
@admin_api.delete("/vehicles/{vehicle_id}/delete")
async def delete_vehicle(vehicle_id: str, admin: str = Depends(get_current_admin)):
    """刪除車輛定義"""
    try:
        from bson import ObjectId
        result = await db_provider.vehicle_definitions_collection.delete_one({"_id": ObjectId(vehicle_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        return {"status": "success", "message": "Vehicle deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_api.delete("/items/{item_id}/delete")
async def delete_item(item_id: str, admin: str = Depends(get_current_admin)):
    """刪除物品定義"""
    try:
        from bson import ObjectId
        result = await db_provider.item_definitions_collection.delete_one({"_id": ObjectId(item_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Item not found")
        return {"status": "success", "message": "Item deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_api.delete("/tasks/{task_id}/delete")
async def delete_task(task_id: str, admin: str = Depends(get_current_admin)):
    """刪除任務定義"""
    try:
        from bson import ObjectId
        result = await db_provider.task_definitions_collection.delete_one({"_id": ObjectId(task_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"status": "success", "message": "Task deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_api.delete("/destinations/{destination_id}/delete")
async def delete_destination(destination_id: str, admin: str = Depends(get_current_admin)):
    """刪除目的地"""
    try:
        from bson import ObjectId
        if db_provider.destinations_collection is None:
            raise HTTPException(status_code=503, detail="Database service not available")
        result = await db_provider.destinations_collection.delete_one({"_id": ObjectId(destination_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Destination not found")
        return {"status": "success", "message": "Destination deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_api.delete("/game-events/{event_id}/delete")
async def delete_game_event(event_id: str, admin: str = Depends(get_current_admin)):
    """刪除遊戲事件"""
    try:
        from bson import ObjectId
        if db_provider.volticar_db is None:
            raise HTTPException(status_code=503, detail="Database service not available")
        game_events_collection = db_provider.volticar_db["GameEvents"]
        result = await game_events_collection.delete_one({"_id": ObjectId(event_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Game event not found")
        return {"status": "success", "message": "Game event deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_api.delete("/shop-items/{shop_item_id}/delete")
async def delete_shop_item(shop_item_id: str, admin: str = Depends(get_current_admin)):
    """刪除商店物品"""
    try:
        from bson import ObjectId
        if db_provider.volticar_db is None:
            raise HTTPException(status_code=503, detail="Database service not available")
        shop_items_collection = db_provider.volticar_db["ShopItems"]
        result = await shop_items_collection.delete_one({"_id": ObjectId(shop_item_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Shop item not found")
        return {"status": "success", "message": "Shop item deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 編輯功能路由
@admin_api.get("/vehicles/{vehicle_id}/edit", response_class=HTMLResponse)
async def edit_vehicle_form(vehicle_id: str, request: Request, admin: str = Depends(get_current_admin)):
    """顯示編輯車輛定義的表單"""
    try:
        from bson import ObjectId
        if db_provider.vehicle_definitions_collection is None:
            raise HTTPException(status_code=503, detail="Database service not available")
        
        vehicle = await db_provider.vehicle_definitions_collection.find_one({"_id": ObjectId(vehicle_id)})
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        
        # 轉換 ObjectId 為字串
        vehicle["_id"] = str(vehicle["_id"])
        
        return templates.TemplateResponse("add_vehicle.html", {
            "request": request,
            "admin": admin,
            "title": "編輯車輛定義",
            "form_data": vehicle,
            "edit_mode": True,
            "item_id": vehicle_id
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_api.post("/vehicles/{vehicle_id}/edit", response_class=HTMLResponse)
async def update_vehicle(
    vehicle_id: str,
    request: Request,
    admin: str = Depends(get_current_admin),
    name: str = Form(...),
    type: str = Form(...),
    description: Optional[str] = Form(None),
    max_load_weight: float = Form(...),
    max_load_volume: float = Form(...),
    base_price: Optional[int] = Form(None),
    rental_price_per_session: Optional[int] = Form(None),
    availability_type: str = Form(...),
    required_level_to_unlock: int = Form(1),
    icon_url: Optional[str] = Form(None),
    image_url: Optional[str] = Form(None),
):
    """處理編輯車輛定義的表單提交"""
    try:
        from bson import ObjectId
        if db_provider.vehicle_definitions_collection is None:
            raise HTTPException(status_code=503, detail="Database service not available")

        update_data = {
            "name": name,
            "type": type,
            "description": description,
            "max_load_weight": max_load_weight,
            "max_load_volume": max_load_volume,
            "base_price": base_price,
            "rental_price_per_session": rental_price_per_session,
            "availability_type": availability_type,
            "required_level_to_unlock": required_level_to_unlock,
            "icon_url": icon_url,
            "image_url": image_url,
        }
        
        # Pydantic validation
        from app.models.game_models import VehicleDefinition
        vehicle = VehicleDefinition(**update_data)
        
        # Update in MongoDB
        result = await db_provider.vehicle_definitions_collection.update_one(
            {"_id": ObjectId(vehicle_id)},
            {"$set": vehicle.model_dump(by_alias=True, exclude_none=True)}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        
        return RedirectResponse(url="/admin/vehicles", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("add_vehicle.html", {
            "request": request,
            "admin": admin,
            "title": "編輯車輛定義",
            "error": str(e),
            "form_data": update_data,
            "edit_mode": True,
            "item_id": vehicle_id
        })

@admin_api.get("/items/{item_id}/edit", response_class=HTMLResponse)
async def edit_item_form(item_id: str, request: Request, admin: str = Depends(get_current_admin)):
    """顯示編輯物品定義的表單"""
    try:
        from bson import ObjectId
        if db_provider.item_definitions_collection is None:
            raise HTTPException(status_code=503, detail="Database service not available")
        
        item = await db_provider.item_definitions_collection.find_one({"_id": ObjectId(item_id)})
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        # 轉換 ObjectId 為字串
        item["_id"] = str(item["_id"])
        
        return templates.TemplateResponse("add_item.html", {
            "request": request,
            "admin": admin,
            "title": "編輯物品定義",
            "form_data": item,
            "edit_mode": True,
            "item_id": item_id
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_api.post("/items/{item_id}/edit", response_class=HTMLResponse)
async def update_item(
    item_id: str,
    request: Request,
    admin: str = Depends(get_current_admin),
    name: str = Form(...),
    category: str = Form(...),
    description: Optional[str] = Form(None),
    weight_per_unit: float = Form(...),
    volume_per_unit: float = Form(...),
    base_value_per_unit: int = Form(...),
    is_fragile: bool = Form(False),
    is_perishable: bool = Form(False),
    spoil_duration_hours: Optional[int] = Form(None),
    required_permit_type: Optional[str] = Form(None),
    icon_url: Optional[str] = Form(None),
):
    """處理編輯物品定義的表單提交"""
    try:
        from bson import ObjectId
        if db_provider.item_definitions_collection is None:
            raise HTTPException(status_code=503, detail="Database service not available")

        update_data = {
            "name": name,
            "category": category,
            "description": description,
            "weight_per_unit": weight_per_unit,
            "volume_per_unit": volume_per_unit,
            "base_value_per_unit": base_value_per_unit,
            "is_fragile": is_fragile,
            "is_perishable": is_perishable,
            "spoil_duration_hours": spoil_duration_hours,
            "required_permit_type": required_permit_type,
            "icon_url": icon_url,
        }
        
        # Pydantic validation
        from app.models.game_models import ItemDefinition
        item = ItemDefinition(**update_data)
        
        # Update in MongoDB
        result = await db_provider.item_definitions_collection.update_one(
            {"_id": ObjectId(item_id)},
            {"$set": item.model_dump(by_alias=True, exclude_none=True)}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Item not found")
        
        return RedirectResponse(url="/admin/items", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("add_item.html", {
            "request": request,
            "admin": admin,
            "title": "編輯物品定義",
            "error": str(e),
            "form_data": update_data,
            "edit_mode": True,
            "item_id": item_id
        })

@admin_api.get("/destinations/{destination_id}/edit", response_class=HTMLResponse)
async def edit_destination_form(destination_id: str, request: Request, admin: str = Depends(get_current_admin)):
    """顯示編輯目的地的表單"""
    try:
        from bson import ObjectId
        if db_provider.destinations_collection is None:
            raise HTTPException(status_code=503, detail="Database service not available")
        
        destination = await db_provider.destinations_collection.find_one({"_id": ObjectId(destination_id)})
        if not destination:
            raise HTTPException(status_code=404, detail="Destination not found")
        
        # 轉換 ObjectId 為字串
        destination["_id"] = str(destination["_id"])
        
        return templates.TemplateResponse("add_destination.html", {
            "request": request,
            "admin": admin,
            "title": "編輯目的地",
            "form_data": destination,
            "edit_mode": True,
            "item_id": destination_id
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_api.post("/destinations/{destination_id}/edit", response_class=HTMLResponse)  
async def update_destination(
    destination_id: str,
    request: Request,
    admin: str = Depends(get_current_admin),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    region: str = Form(...),
    latitude: float = Form(...),
    longitude: float = Form(...),
    is_unlocked_by_default: bool = Form(False),
    unlock_requirements: Optional[str] = Form(None),
    available_services: Optional[str] = Form(None),
    icon_url: Optional[str] = Form(None),
):
    """處理編輯目的地的表單提交"""
    try:
        from bson import ObjectId
        if db_provider.destinations_collection is None:
            raise HTTPException(status_code=503, detail="Database service not available")

        # 處理座標
        coordinates = {
            "type": "Point",
            "coordinates": [longitude, latitude]  # GeoJSON 格式: [longitude, latitude]
        }
        
        # 處理服務列表
        services_list = []
        if available_services:
            services_list = [service.strip() for service in available_services.split(',') if service.strip()]

        update_data = {
            "name": name,
            "description": description,
            "region": region,
            "coordinates": coordinates,
            "is_unlocked_by_default": is_unlocked_by_default,
            "unlock_requirements": unlock_requirements,
            "available_services": services_list if services_list else None,
            "icon_url": icon_url,
        }
        
        # Pydantic validation
        from app.models.game_models import Destination
        destination = Destination(**update_data)
        
        # Update in MongoDB
        result = await db_provider.destinations_collection.update_one(
            {"_id": ObjectId(destination_id)},
            {"$set": destination.model_dump(by_alias=True, exclude_none=True)}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Destination not found")
        
        return RedirectResponse(url="/admin/destinations", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("add_destination.html", {
            "request": request,
            "admin": admin,
            "title": "編輯目的地",
            "error": str(e),
            "form_data": update_data,
            "edit_mode": True,
            "item_id": destination_id
        })

@admin_api.get("/shop-items/{shop_item_id}/edit", response_class=HTMLResponse)
async def edit_shop_item_form(shop_item_id: str, request: Request, admin: str = Depends(get_current_admin)):
    """顯示編輯商店物品的表單"""
    try:
        from bson import ObjectId
        if db_provider.volticar_db is None:
            raise HTTPException(status_code=503, detail="Database service not available")
        
        shop_items_collection = db_provider.volticar_db["ShopItems"]
        shop_item = await shop_items_collection.find_one({"_id": ObjectId(shop_item_id)})
        
        if not shop_item:
            raise HTTPException(status_code=404, detail="Shop item not found")
        
        shop_item["_id"] = str(shop_item["_id"])
        
        return templates.TemplateResponse("add_shop_item.html", {
            "request": request,
            "admin": admin,
            "title": "編輯商店物品",
            "form_data": shop_item,
            "edit_mode": True,
            "item_id": shop_item_id
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_api.post("/shop-items/{shop_item_id}/edit", response_class=HTMLResponse)
async def update_shop_item(
    shop_item_id: str,
    request: Request,
    admin: str = Depends(get_current_admin),
    name: str = Form(...),
    description: str = Form(...),
    price: int = Form(...),
    category: str = Form(...),
    discount_price: Optional[int] = Form(None),
    effect_data: Optional[str] = Form(None),
    required_level: int = Form(1),
    daily_limit: Optional[int] = Form(None),
    stack_limit: int = Form(1),
    is_featured: bool = Form(False),
    is_available: bool = Form(True),
    icon_url: Optional[str] = Form(None),
):
    """處理編輯商店物品的表單提交"""
    try:
        from bson import ObjectId
        if db_provider.volticar_db is None:
            raise HTTPException(status_code=503, detail="Database service not available")

        update_data = {
            "name": name,
            "description": description,
            "price": price,
            "category": category,
            "discount_price": discount_price,
            "effect_data": effect_data,
            "required_level": required_level,
            "daily_limit": daily_limit,
            "stack_limit": stack_limit,
            "is_featured": is_featured,
            "is_available": is_available,
            "icon_url": icon_url,
        }
        
        from app.models.game_models import ShopItem
        item = ShopItem(**update_data)
        
        shop_items_collection = db_provider.volticar_db["ShopItems"]
        result = await shop_items_collection.update_one(
            {"_id": ObjectId(shop_item_id)},
            {"$set": item.model_dump(by_alias=True, exclude_none=True)}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Shop item not found")
        
        return RedirectResponse(url="/admin/shop-items", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("add_shop_item.html", {
            "request": request,
            "admin": admin,
            "title": "編輯商店物品",
            "error": str(e),
            "form_data": update_data,
            "edit_mode": True,
            "item_id": shop_item_id
        })

@admin_api.get("/game-events/{event_id}/edit", response_class=HTMLResponse)
async def edit_game_event_form(event_id: str, request: Request, admin: str = Depends(get_current_admin)):
    """顯示編輯遊戲事件的表單"""
    try:
        from bson import ObjectId
        if db_provider.volticar_db is None:
            raise HTTPException(status_code=503, detail="Database service not available")
        
        game_events_collection = db_provider.volticar_db["GameEvents"]
        game_event = await game_events_collection.find_one({"_id": ObjectId(event_id)})
        
        if not game_event:
            raise HTTPException(status_code=404, detail="Game event not found")
        
        game_event["_id"] = str(game_event["_id"])
        
        import json
        game_event["choices"] = json.dumps(game_event.get("choices", []), ensure_ascii=False, indent=4)
        
        return templates.TemplateResponse("add_game_event.html", {
            "request": request,
            "admin": admin,
            "title": "編輯遊戲事件",
            "form_data": game_event,
            "edit_mode": True,
            "item_id": event_id
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_api.post("/game-events/{event_id}/edit", response_class=HTMLResponse)
async def update_game_event(
    event_id: str,
    request: Request,
    admin: str = Depends(get_current_admin),
    name: str = Form(...),
    description: str = Form(...),
    choices: str = Form(...),
    trigger_probability: Optional[int] = Form(10),
    event_category: Optional[str] = Form("隨機"),
    is_active: bool = Form(True),
):
    """處理編輯遊戲事件的表單提交"""
    try:
        from bson import ObjectId
        if db_provider.volticar_db is None:
            raise HTTPException(status_code=503, detail="Database service not available")
            
        import json
        choices_list = json.loads(choices)
        
        update_data = {
            "name": name,
            "description": description,
            "choices": choices_list,
        }
        
        from app.models.game_models import GameEvent
        event = GameEvent(**update_data)
        
        game_events_collection = db_provider.volticar_db["GameEvents"]
        result = await game_events_collection.update_one(
            {"_id": ObjectId(event_id)},
            {"$set": event.model_dump(by_alias=True, exclude_none=True)}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Game event not found")
        
        return RedirectResponse(url="/admin/game-events", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("add_game_event.html", {
            "request": request,
            "admin": admin,
            "title": "編輯遊戲事件",
            "error": str(e),
            "form_data": update_data,
            "edit_mode": True,
            "item_id": event_id
        })

@admin_api.get("/tasks/{task_id}/edit", response_class=HTMLResponse)
async def edit_task_form(task_id: str, request: Request, admin: str = Depends(get_current_admin)):
    """顯示編輯任務定義的表單"""
    try:
        from bson import ObjectId
        if db_provider.task_definitions_collection is None:
            raise HTTPException(status_code=503, detail="Database service not available")
        
        task = await db_provider.task_definitions_collection.find_one({"_id": ObjectId(task_id)})
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        task["_id"] = str(task["_id"])
        
        import json
        if "requirements" in task and task["requirements"] and "deliver_items" in task["requirements"]:
            task["deliver_items_json"] = json.dumps(task["requirements"]["deliver_items"], ensure_ascii=False, indent=4)
        if "rewards" in task and task["rewards"] and "item_rewards" in task["rewards"]:
            task["reward_items_json"] = json.dumps(task["rewards"]["item_rewards"], ensure_ascii=False, indent=4)
            
        return templates.TemplateResponse("add_task.html", {
            "request": request,
            "admin": admin,
            "title": "編輯任務定義",
            "form_data": task,
            "edit_mode": True,
            "item_id": task_id
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_api.post("/tasks/{task_id}/edit", response_class=HTMLResponse)
async def update_task(
    task_id: str,
    request: Request,
    admin: str = Depends(get_current_admin),
    title: str = Form(...),
    description: str = Form(...),
    mode: str = Form(...),
    required_player_level: int = Form(1),
    required_vehicle_type: Optional[str] = Form(None),
    time_limit_seconds: Optional[int] = Form(None),
    pickup_location_id: Optional[str] = Form(None),
    destination_id: Optional[str] = Form(None),
    min_cargo_value: Optional[int] = Form(None),
    deliver_items: Optional[str] = Form(None),
    experience_points: int = Form(...),
    currency: int = Form(0),
    reward_items: Optional[str] = Form(None),
    is_repeatable: bool = Form(False),
    repeat_cooldown_hours: Optional[int] = Form(None),
    is_active: bool = Form(True),
):
    """處理編輯任務定義的表單提交"""
    try:
        from bson import ObjectId
        if db_provider.task_definitions_collection is None:
            raise HTTPException(status_code=503, detail="Database service not available")

        import json
        deliver_items_list = json.loads(deliver_items) if deliver_items else []
        reward_items_list = json.loads(reward_items) if reward_items else []

        requirements = {
            "required_player_level": required_player_level,
            "deliver_items": deliver_items_list,
            "pickup_location_id": pickup_location_id,
            "destination_id": destination_id,
            "required_vehicle_type": required_vehicle_type,
            "time_limit_seconds": time_limit_seconds,
            "min_cargo_value": min_cargo_value,
        }

        rewards = {
            "experience_points": experience_points,
            "currency": currency,
            "item_rewards": reward_items_list,
        }

        update_data = {
            "title": title,
            "description": description,
            "mode": mode,
            "requirements": requirements,
            "rewards": rewards,
            "is_repeatable": is_repeatable,
            "repeat_cooldown_hours": repeat_cooldown_hours,
            "is_active": is_active,
        }
        
        from app.models.game_models import TaskDefinition
        task = TaskDefinition(**update_data)
        
        result = await db_provider.task_definitions_collection.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": task.model_dump(by_alias=True, exclude_none=True)}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return RedirectResponse(url="/admin/tasks", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("add_task.html", {
            "request": request,
            "admin": admin,
            "title": "編輯任務定義",
            "error": str(e),
            "form_data": update_data,
            "edit_mode": True,
            "item_id": task_id
        })

@admin_api.get("/users/{user_id}/edit", response_class=HTMLResponse)
async def edit_user_form(user_id: str, request: Request, admin: str = Depends(get_current_admin)):
    """顯示編輯用戶的表單"""
    try:
        from bson import ObjectId
        if db_provider.users_collection is None:
            raise HTTPException(status_code=503, detail="Database service not available")
        
        user = await db_provider.users_collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user["_id"] = str(user["_id"])
        
        return templates.TemplateResponse("add_user.html", {
            "request": request,
            "admin": admin,
            "title": "編輯用戶",
            "form_data": user,
            "edit_mode": True,
            "item_id": user_id
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_api.post("/users/{user_id}/edit", response_class=HTMLResponse)
async def update_user(
    user_id: str,
    request: Request,
    admin: str = Depends(get_current_admin),
    username: str = Form(...),
    email: str = Form(...),
    phone: Optional[str] = Form(None),
    role: str = Form("user"),
    is_active: bool = Form(True),
):
    """處理編輯用戶的表單提交"""
    try:
        from bson import ObjectId
        if db_provider.users_collection is None:
            raise HTTPException(status_code=503, detail="Database service not available")

        update_data = {
            "username": username,
            "email": email,
            "phone": phone,
            "role": role,
            "is_active": is_active,
            "updated_at": datetime.now()
        }
        
        result = await db_provider.users_collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        return RedirectResponse(url="/admin/users", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("add_user.html", {
            "request": request,
            "admin": admin,
            "title": "編輯用戶",
            "error": str(e),
            "form_data": update_data,
            "edit_mode": True,
            "item_id": user_id
        })

@admin_api.delete("/users/{user_id}/delete")
async def delete_user(user_id: str, admin: str = Depends(get_current_admin)):
    """刪除用戶"""
    try:
        from bson import ObjectId
        result = await db_provider.users_collection.delete_one({"_id": ObjectId(user_id)})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        return {"status": "success", "message": "User deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 測試資料路由（僅用於開發測試）

@admin_api.get("/player-data/{player_id}/edit", response_class=HTMLResponse)
async def edit_player_data_form(player_id: str, request: Request, admin: str = Depends(get_current_admin)):
    """顯示編輯玩家資料的表單"""
    try:
        from bson import ObjectId
        if db_provider.players_collection is None:
            raise HTTPException(status_code=503, detail="Database service not available")
        
        player = await db_provider.players_collection.find_one({"_id": ObjectId(player_id)})
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        
        player["_id"] = str(player["_id"])
        
        return templates.TemplateResponse("add_player_data.html", {
            "request": request,
            "admin": admin,
            "title": "編輯玩家資料",
            "form_data": player,
            "edit_mode": True,
            "item_id": player_id
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_api.post("/player-data/{player_id}/edit", response_class=HTMLResponse)
async def update_player_data(
    player_id: str,
    request: Request,
    admin: str = Depends(get_current_admin),
    display_name: str = Form(...),
    level: int = Form(...),
    experience: int = Form(...),
    currency: int = Form(...),
):
    """處理編輯玩家資料的表單提交"""
    try:
        from bson import ObjectId
        if db_provider.players_collection is None:
            raise HTTPException(status_code=503, detail="Database service not available")

        update_data = {
            "display_name": display_name,
            "level": level,
            "experience": experience,
            "currency": currency,
            "updated_at": datetime.now(),
        }
        
        result = await db_provider.players_collection.update_one(
            {"_id": ObjectId(player_id)},
            {"$set": update_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Player not found")
        
        return RedirectResponse(url="/admin/player-data", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("add_player_data.html", {
            "request": request,
            "admin": admin,
            "title": "編輯玩家資料",
            "error": str(e),
            "form_data": update_data,
            "edit_mode": True,
            "item_id": player_id
        })

@admin_api.post("/test/create-sample-data")
async def create_sample_data(admin: str = Depends(get_current_admin)):
    """創建一些示例資料用於測試"""
    try:
        if db_provider.volticar_db is None:
            raise HTTPException(status_code=503, detail="Database service not available")
        
        # 創建示例遊戲事件
        game_events_collection = db_provider.volticar_db["game_events"]
        sample_events = [
            {
                "name": "隨機路檢",
                "description": "在運送過程中遇到警察路檢",
                "choices": [
                    {"text": "配合檢查", "effect": "延遲10分鐘，但獲得聲望+1"},
                    {"text": "快速通過", "effect": "有30%機率被罰款200元"}
                ]
            },
            {
                "name": "交通堵塞",
                "description": "前方發生交通事故造成堵塞",
                "choices": [
                    {"text": "等待疏通", "effect": "延遲15分鐘"},
                    {"text": "繞道而行", "effect": "增加5公里距離，消耗額外燃料"}
                ]
            }
        ]
        
        for event in sample_events:
            existing = await game_events_collection.find_one({"name": event["name"]})
            if not existing:
                await game_events_collection.insert_one(event)
        
        # 創建示例商店物品
        shop_items_collection = db_provider.volticar_db["shop_items"]
        sample_shop_items = [
            {
                "name": "加速卡",
                "description": "使用後可讓車輛速度提升20%，持續1小時",
                "price": 100,
                "category": "道具",
                "required_level": 1,
                "stack_limit": 5,
                "is_featured": True,
                "is_available": True
            },
            {
                "name": "經驗值加倍卡",
                "description": "使用後下一個任務獲得的經驗值翻倍",
                "price": 150,
                "category": "道具", 
                "required_level": 5,
                "stack_limit": 3,
                "is_featured": False,
                "is_available": True
            },
            {
                "name": "保險卡",
                "description": "保護車輛免受意外損傷，持續24小時",
                "price": 200,
                "category": "保險",
                "required_level": 10,
                "stack_limit": 1,
                "is_featured": True,
                "is_available": True
            }
        ]
        
        for item in sample_shop_items:
            existing = await shop_items_collection.find_one({"name": item["name"]})
            if not existing:
                await shop_items_collection.insert_one(item)
        
        return {"status": "success", "message": "Sample data created successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@admin_api.on_event("startup")
async def startup():
    """
    Initialize admin.
    """
    if db_provider.volticar_db is None:
        print("Admin startup skipped: MongoDB client is not available.")
        return
    
    # Create default admin user if not exists
    try:
        admin_collection = db_provider.volticar_db["admins"]
        admin_count = await admin_collection.count_documents({})
        if admin_count == 0:
            # Create default admin user
            default_admin_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "Volticar123")
            default_admin = {
                "username": "Volticar",
                "password": get_password_hash(default_admin_password)
            }
            await admin_collection.insert_one(default_admin)
            print(f"已創建預設管理員用戶: Volticar/{default_admin_password}")
    except Exception as e:
        print(f"Admin startup error: {e}")
        
    # Ensure admin_templates directory exists
    admin_templates_dir = os.path.join(os.path.dirname(__file__), "admin_templates")
    if not os.path.exists(admin_templates_dir):
        os.makedirs(admin_templates_dir)
