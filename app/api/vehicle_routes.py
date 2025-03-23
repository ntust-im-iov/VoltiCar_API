from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any
from datetime import datetime

from app.models.user import VehicleBase, VehicleCreate, VehicleUpdate
from app.database.mongodb import volticar_db
from app.utils.auth import get_current_user
from app.utils.helpers import handle_mongo_data

router = APIRouter(prefix="/vehicles", tags=["車輛"])

# 初始化集合
vehicles_collection = volticar_db["Vehicles"]

# 獲取車輛資料
@router.get("/{user_id}/{vehicle_id}", response_model=Dict[str, Any])
async def get_vehicle_info(user_id: str, vehicle_id: str):
    """
    獲取指定用戶的車輛資訊
    - user_id: 用戶ID
    - vehicle_id: 車輛ID
    """
    # 查詢數據庫獲取車輛信息
    vehicle = vehicles_collection.find_one({"user_id": user_id, "vehicle_id": vehicle_id})
    
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到指定車輛"
        )
    
    # 處理ObjectId並返回結果
    return {
        "status": "success",
        "msg": "獲取車輛信息成功",
        "vehicle_info": {
            "vehicle_name": vehicle.get("vehicle_name", ""),
            "battery_level": vehicle.get("battery_level", 0),
            "battery_health": vehicle.get("battery_health", 100),
            "mileage": vehicle.get("mileage", 0)
        }
    }

# 添加/註冊新車輛
@router.post("/", response_model=Dict[str, Any])
async def register_vehicle(vehicle: VehicleCreate):
    """
    註冊新車輛
    - user_id: 用戶ID
    - vehicle_id: 車輛ID
    """
    # 檢查車輛是否已經註冊
    existing_vehicle = vehicles_collection.find_one({
        "user_id": vehicle.user_id,
        "vehicle_id": vehicle.vehicle_id
    })
    
    if existing_vehicle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此車輛已經註冊"
        )
    
    # 準備車輛數據
    vehicle_data = {
        "user_id": vehicle.user_id,
        "vehicle_id": vehicle.vehicle_id,
        "vehicle_name": vehicle.vehicle_name if hasattr(vehicle, 'vehicle_name') else "",
        "battery_level": 0,
        "battery_health": 100,
        "mileage": 0,
        "created_at": datetime.now(),
        "last_updated": datetime.now()
    }
    
    # 插入數據庫
    result = vehicles_collection.insert_one(vehicle_data)
    
    if not result.inserted_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="車輛註冊失敗"
        )
    
    return {
        "status": "success",
        "msg": "車輛註冊成功",
        "user_id": vehicle.user_id,
        "vehicle_id": vehicle.vehicle_id
    }

# 更新車輛電池信息
@router.post("/{vehicle_id}/battery", response_model=Dict[str, Any])
async def update_battery_info(vehicle_id: str, battery_level: int, battery_health: int, lastcharge_mileage: int):
    """
    更新車輛電池資訊
    - vehicle_id: 車輛ID
    - battery_level: 電池電量 (0-100)
    - battery_health: 電池健康度 (0-100)
    - lastcharge_mileage: 上次充電後的里程
    """
    # 檢查車輛是否存在
    vehicle = vehicles_collection.find_one({"vehicle_id": vehicle_id})
    
    if not vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到指定車輛"
        )
    
    # 更新數據
    result = vehicles_collection.update_one(
        {"vehicle_id": vehicle_id},
        {"$set": {
            "battery_level": battery_level,
            "battery_health": battery_health,
            "lastcharge_mileage": lastcharge_mileage,
            "last_updated": datetime.now()
        }}
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新車輛信息失敗"
        )
    
    return {
        "status": "success",
        "msg": "車輛電池信息更新成功"
    }

# 更新車輛資訊
@router.put("/{vehicle_id}", response_model=Dict[str, Any])
async def update_vehicle(vehicle_id: str, vehicle: VehicleUpdate):
    """
    更新車輛基本資訊
    - vehicle_id: 車輛ID
    - vehicle_name: 車輛名稱
    - mileage: 總里程
    """
    # 檢查車輛是否存在
    existing_vehicle = vehicles_collection.find_one({"vehicle_id": vehicle_id})
    
    if not existing_vehicle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="找不到指定車輛"
        )
    
    # 準備更新數據
    update_data = {}
    if vehicle.vehicle_name is not None:
        update_data["vehicle_name"] = vehicle.vehicle_name
    if vehicle.mileage is not None:
        update_data["mileage"] = vehicle.mileage
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="沒有提供有效的更新數據"
        )
    
    update_data["last_updated"] = datetime.now()
    
    # 更新數據
    result = vehicles_collection.update_one(
        {"vehicle_id": vehicle_id},
        {"$set": update_data}
    )
    
    if result.modified_count == 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新車輛信息失敗"
        )
    
    return {
        "status": "success",
        "msg": "車輛資訊更新成功"
    }

# 獲取用戶的所有車輛
@router.get("/user/{user_id}", response_model=Dict[str, Any])
async def get_user_vehicles(user_id: str):
    """
    獲取用戶的所有車輛列表
    - user_id: 用戶ID
    """
    # 查詢用戶的所有車輛
    vehicles = list(vehicles_collection.find({"user_id": user_id}))
    
    # 處理數據格式
    formatted_vehicles = []
    for vehicle in vehicles:
        formatted_vehicles.append({
            "vehicle_id": vehicle["vehicle_id"],
            "vehicle_name": vehicle.get("vehicle_name", ""),
            "battery_level": vehicle.get("battery_level", 0),
            "battery_health": vehicle.get("battery_health", 100),
            "mileage": vehicle.get("mileage", 0),
            "last_updated": vehicle.get("last_updated", datetime.now()).isoformat()
        })
    
    return {
        "status": "success",
        "msg": "獲取用戶車輛列表成功",
        "vehicles": formatted_vehicles
    } 