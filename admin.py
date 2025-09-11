import os
from typing import List, Any, Dict, Optional
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates # type: ignore
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from app.database import mongodb as db_provider
from app.utils.auth import verify_password, get_password_hash
import secrets

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
            default_admin = {
                "username": "Volticar",
                "password": get_password_hash("RJW1128")
            }
            await admin_collection.insert_one(default_admin)
            print("已創建預設管理員用戶: Volticar/RJW1128")
    except Exception as e:
        print(f"Admin startup error: {e}")
        
    # Ensure admin_templates directory exists
    admin_templates_dir = os.path.join(os.path.dirname(__file__), "admin_templates")
    if not os.path.exists(admin_templates_dir):
        os.makedirs(admin_templates_dir)


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
            default_admin = {
                "username": "Volticar",
                "password": get_password_hash("RJW1128")
            }
            await admin_collection.insert_one(default_admin)
            print("已創建預設管理員用戶: admin/admin123")
    except Exception as e:
        print(f"Admin startup error: {e}")
        
    # Ensure admin_templates directory exists
    admin_templates_dir = os.path.join(os.path.dirname(__file__), "admin_templates")
    if not os.path.exists(admin_templates_dir):
        os.makedirs(admin_templates_dir)
