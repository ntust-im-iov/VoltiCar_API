from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any
from datetime import datetime

from app.models.user import VehicleBase, VehicleCreate
from app.database.mongodb import volticar_db
from app.utils.auth import get_current_user
from app.utils.helpers import handle_mongo_data

router = APIRouter(prefix="/vehicles", tags=["車輛"])

# 初始化集合
vehicles_collection = volticar_db["Vehicles"]

# 獲取車輛資料
@router.get("/{user_uuid}/{vehicle_id}", response_model=Dict[str, Any])
async def get_vehicle_info(user_uuid: str, vehicle_id: str):
    # 查詢數據庫獲取車輛信息
    vehicle = vehicles_collection.find_one({"user_uuid": user_uuid, "vehicle_id": vehicle_id})
    
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
    # 檢查車輛是否已經註冊
    existing_vehicle = vehicles_collection.find_one({
        "user_uuid": vehicle.user_uuid,
        "vehicle_id": vehicle.vehicle_id
    })
    
    if existing_vehicle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此車輛已經註冊"
        )
    
    # 準備車輛數據
    vehicle_data = {
        "user_uuid": vehicle.user_uuid,
        "vehicle_id": vehicle.vehicle_id,
        "vehicle_name": "",
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
        "user_uuid": vehicle.user_uuid,
        "vehicle_id": vehicle.vehicle_id
    }

# 更新車輛電池信息
@router.post("/{vehicle_id}/battery", response_model=Dict[str, Any])
async def update_battery_info(vehicle_id: str, battery_level: int, battery_health: int, lastcharge_mileage: int):
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