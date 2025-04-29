from fastapi import APIRouter, HTTPException, status, Depends, Body, Form # Added Form
from typing import List, Dict, Any, Optional # Added Optional
from datetime import datetime
from pydantic import BaseModel # Added BaseModel

from app.models.user import VehicleCreate, VehicleUpdate # Removed VehicleBase
from app.database.mongodb import volticar_db
# Removed get_current_user
from app.utils.helpers import handle_mongo_data

router = APIRouter(prefix="/vehicles", tags=["車輛"])

# 新增 Pydantic 模型用於更新電池信息
class VehicleBatteryUpdate(BaseModel):
    battery_level: int
    battery_health: int
    lastcharge_mileage: int

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

    # 使用 handle_mongo_data 處理 ObjectId
    processed_vehicle = handle_mongo_data(vehicle)

    # 返回處理後的結果
    return {
        "status": "success",
        "msg": "獲取車輛信息成功",
        # Return the processed data, accessing fields safely
        "vehicle_info": processed_vehicle # Return the whole processed document
        # Example of accessing specific fields if needed:
        # "vehicle_info": {
        #     "vehicle_name": processed_vehicle.get("vehicle_name", ""),
        #     "battery_level": processed_vehicle.get("battery_level", 0),
        #     "battery_health": processed_vehicle.get("battery_health", 100),
        #     "mileage": processed_vehicle.get("mileage", 0)
        # }
    }


# 添加/註冊新車輛
@router.post("/", response_model=Dict[str, Any])
async def register_vehicle(
    user_id: str = Form(..., description="用戶ID"),
    vehicle_id: str = Form(..., description="車輛ID"),
    vehicle_name: Optional[str] = Form(None, description="車輛名稱 (可選)")
):
    """
    註冊新車輛 (使用表單欄位)

    - **user_id**: 用戶ID
    - **vehicle_id**: 車輛ID
    - **vehicle_name**: 車輛名稱 (可選)
    """
    # 檢查車輛是否已經註冊
    existing_vehicle = vehicles_collection.find_one({
        "user_id": user_id,
        "vehicle_id": vehicle_id
    })
    
    if existing_vehicle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="此車輛已經註冊"
        )
    
    # 準備車輛數據
    vehicle_data = {
        "user_id": user_id,
        "vehicle_id": vehicle_id,
        "vehicle_name": vehicle_name or "", # Use Form parameter
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
        "user_id": user_id,
        "vehicle_id": vehicle_id
    }

# 更新車輛電池信息 (使用表單欄位)
@router.put("/{vehicle_id}/battery", response_model=Dict[str, Any]) # Changed to PUT for update
async def update_battery_info(
    vehicle_id: str,
    battery_level: int = Form(..., description="電池電量百分比"),
    battery_health: int = Form(..., description="電池健康度百分比"),
    lastcharge_mileage: int = Form(..., description="上次充電時的里程數")
):
    """
    更新車輛電池資訊 (使用表單欄位)

    - **vehicle_id**: 車輛ID
    - **battery_level**: 電池電量百分比
    - **battery_health**: 電池健康度百分比
    - **lastcharge_mileage**: 上次充電時的里程數
    """
    # 直接嘗試更新數據，移除 find_one 檢查
    result = vehicles_collection.update_one(
        {"vehicle_id": vehicle_id},
        {"$set": {
            "battery_level": battery_level,
            "battery_health": battery_health,
            "lastcharge_mileage": lastcharge_mileage,
            "last_updated": datetime.now()
        }}
    )

    # 如果 modified_count 為 0，表示未找到車輛或數據未變更
    if result.modified_count == 0:
        # 檢查文檔是否存在以區分 404 和無變更
        if vehicles_collection.count_documents({"vehicle_id": vehicle_id}) == 0:
             raise HTTPException(
                 status_code=status.HTTP_404_NOT_FOUND,
                 detail="找不到指定車輛"
             )
        # else: # 如果文檔存在但未修改，可以選擇返回成功或特定訊息
        #     return {"status": "success", "msg": "車輛電池信息無變更"}

    return {
        "status": "success",
        "msg": "車輛電池信息更新成功"
    }

# 更新車輛資訊
@router.put("/{vehicle_id}", response_model=Dict[str, Any])
async def update_vehicle(
    vehicle_id: str,
    vehicle_name: Optional[str] = Form(None, description="新的車輛名稱 (可選)"),
    mileage: Optional[int] = Form(None, description="新的里程數 (可選)")
):
    """
    更新車輛基本資訊 (使用表單欄位)

    - **vehicle_id**: 車輛ID
    - **vehicle_name**: 新的車輛名稱 (可選)
    - **mileage**: 新的里程數 (可選)
    """
    # 準備更新數據
    update_data = {}
    if vehicle_name is not None:
        update_data["vehicle_name"] = vehicle_name
    if mileage is not None:
        update_data["mileage"] = mileage
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="沒有提供有效的更新數據"
        )
    
    update_data["last_updated"] = datetime.now()

    # 直接嘗試更新數據，移除 find_one 檢查
    result = vehicles_collection.update_one(
        {"vehicle_id": vehicle_id},
        {"$set": update_data}
    )

    # 如果 modified_count 為 0，表示未找到車輛或數據未變更
    if result.modified_count == 0:
         # 檢查文檔是否存在以區分 404 和無變更
        if vehicles_collection.count_documents({"vehicle_id": vehicle_id}) == 0:
             raise HTTPException(
                 status_code=status.HTTP_404_NOT_FOUND,
                 detail="找不到指定車輛"
             )
        # else: # 如果文檔存在但未修改，可以選擇返回成功或特定訊息
        #     return {"status": "success", "msg": "車輛資訊無變更"}

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
