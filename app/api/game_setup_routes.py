from fastapi import APIRouter, HTTPException, status, Depends, Body, Path
from typing import List, Optional, Any, Dict
# from bson import ObjectId 
import uuid 
from datetime import datetime

from app.models.user import User, CurrentGameSessionSetup, CurrentGameSessionSetupItem
from app.models.game_models import (
    VehicleDefinition, PlayerOwnedVehicle, ItemDefinition, Destination, 
    GameSession, PlayerTask, TaskDefinition, # Removed BaseModel - import from pydantic instead
    GeoCoordinates, VehicleSnapshot, CargoItemSnapshot, DestinationSnapshot # Ensure all are imported
)
from pydantic import BaseModel  # BaseModel for request/response models
from app.database import mongodb as db_provider
from app.utils.auth import get_current_user 

game_setup_router = APIRouter(tags=["遊戲設定 (Game Setup)"])

# --- Define Response Models for Summary Endpoint First ---
class SessionSummaryVehicle(BaseModel):
    vehicle_id: str
    name: str
    max_load_weight: float
    max_load_volume: float

class SessionSummaryCargoItem(BaseModel):
    item_id: str
    name: str
    quantity: int
    weight_per_unit: float 
    volume_per_unit: float 
    # base_value_per_unit: int # Was in game_models.CargoItemSnapshot, add if needed in summary

class SessionSummaryCargo(BaseModel):
    items: List[SessionSummaryCargoItem]
    total_weight: float
    total_volume: float

class SessionSummaryDestination(BaseModel):
    destination_id: str
    name: str
    region: str

class SessionSummaryMain(BaseModel):
    selected_vehicle: Optional[SessionSummaryVehicle] = None
    selected_cargo: Optional[SessionSummaryCargo] = None
    selected_destination: Optional[SessionSummaryDestination] = None

class RelatedTaskSummary(BaseModel):
    player_task_id: str # PlayerTask.player_task_id (UUID)
    task_id: str # TaskDefinition.task_id (UUID)
    title: str
    status: str 
    is_completable_with_current_setup: bool
    completion_issues: List[str] = []

class GameSessionSummaryResponse(BaseModel):
    session_summary: SessionSummaryMain
    related_tasks: List[RelatedTaskSummary]
    can_start_game: bool
    start_game_warnings: List[str] = []


# --- Vehicle Selection ---
class PlayerVehicleResponseItem(BaseModel):
    vehicle_id: str 
    player_vehicle_id: Optional[str] = None 
    name: str
    type: str
    max_load_weight: float
    max_load_volume: float
    status: str 

@game_setup_router.get("/player/vehicles", response_model=List[PlayerVehicleResponseItem])
async def list_player_selectable_vehicles(
    availability: Optional[str] = "all", 
    current_user: User = Depends(get_current_user)
):
    if db_provider.vehicle_definitions_collection is None or \
       db_provider.player_owned_vehicles_collection is None:
        raise HTTPException(status_code=503, detail="車輛相關資料庫服務未初始化")

    player_owned_vehicle_docs = await db_provider.player_owned_vehicles_collection.find(
        {"user_id": current_user.user_id}  # Changed player_id to user_id
    ).to_list(length=None)
    
    owned_vehicle_map: Dict[str, PlayerOwnedVehicle] = {}  # Key: vehicle_id (definition's ID), Value: PlayerOwnedVehicle instance
    for pov_doc in player_owned_vehicle_docs:
        pov = PlayerOwnedVehicle.model_validate(pov_doc, from_attributes=True)
        # PlayerOwnedVehicle.vehicle_id is now the foreign key to VehicleDefinition.vehicle_id
        owned_vehicle_map[pov.vehicle_id] = pov

    all_vehicle_definitions_docs = await db_provider.vehicle_definitions_collection.find({}).to_list(length=None)
    
    response_vehicles: List[PlayerVehicleResponseItem] = []
    for vd_doc in all_vehicle_definitions_docs:
        vd = VehicleDefinition.model_validate(vd_doc, from_attributes=True) # vd.vehicle_id is the definition's unique ID
        vehicle_status = "unavailable"
        player_vehicle_instance_id: Optional[str] = None # This will be PlayerOwnedVehicle.instance_id

        # Check if the current VehicleDefinition's vehicle_id (definition ID) is a key in our map
        if vd.vehicle_id in owned_vehicle_map:
            owned_instance = owned_vehicle_map[vd.vehicle_id] # Get the PlayerOwnedVehicle instance
            player_vehicle_instance_id = owned_instance.instance_id # This is the ID of the player's specific vehicle instance
            vehicle_status = "in_use" if owned_instance.is_in_active_session else "owned"
        elif vd.availability_type == "rentable_per_session" or "purchasable_rentable" in vd.availability_type : 
            vehicle_status = "rentable"
        
        if availability == "all" or \
           (availability == "owned" and vehicle_status in ["owned", "in_use"]) or \
           (availability == "rentable" and vehicle_status == "rentable"):
            if vehicle_status != "unavailable":
                response_vehicles.append(
                    PlayerVehicleResponseItem(
                        vehicle_id=vd.vehicle_id, # This is the VehicleDefinition's ID
                        player_vehicle_id=player_vehicle_instance_id, # This is the PlayerOwnedVehicle's instance ID
                        name=vd.name, type=vd.type,
                        max_load_weight=vd.max_load_weight, max_load_volume=vd.max_load_volume,
                        status=vehicle_status
                    )
                )
    return response_vehicles

# --- Destination Selection ---
@game_setup_router.get("/player/destinations", response_model=List[Destination])
async def list_player_selectable_destinations(
    current_user: User = Depends(get_current_user)
):
    if db_provider.destinations_collection is None:
        raise HTTPException(status_code=503, detail="目的地資料庫服務未初始化")

    destinations_cursor = db_provider.destinations_collection.find({}) # Basic: find all
    all_destinations_list = await destinations_cursor.to_list(length=None)

    selectable_destinations: List[Destination] = []
    for dest_doc in all_destinations_list:
        dest = Destination.model_validate(dest_doc, from_attributes=True)
        unlocked = False
        if dest.is_unlocked_by_default:
            unlocked = True
        elif dest.unlock_requirements:
            if dest.unlock_requirements.required_player_level and \
               current_user.level >= dest.unlock_requirements.required_player_level:
                unlocked = True
            # TODO: Add logic for required_completed_task_id if needed
        
        if unlocked:
            selectable_destinations.append(dest)
            
    return selectable_destinations

# --- Cargo Selection ---
class PlayerWarehouseItemDetail(BaseModel): # Response item for listing warehouse contents
    item_id: str
    name: str
    description: Optional[str] = None
    category: str
    weight_per_unit: float
    volume_per_unit: float
    base_value_per_unit: int
    is_fragile: bool
    is_perishable: bool
    quantity_in_warehouse: int # From PlayerWarehouseItem

@game_setup_router.get("/player/warehouse/items", response_model=List[PlayerWarehouseItemDetail])
async def list_player_warehouse_items(current_user: User = Depends(get_current_user)):
    if db_provider.player_warehouse_items_collection is None or \
       db_provider.item_definitions_collection is None:
        raise HTTPException(status_code=503, detail="倉庫或物品定義資料庫服務未初始化")

    warehouse_item_docs = await db_provider.player_warehouse_items_collection.find(
        {"user_id": current_user.user_id} # Changed from player_id to user_id
    ).to_list(length=None)

    detailed_items: List[PlayerWarehouseItemDetail] = []
    if not warehouse_item_docs:
        return detailed_items

    item_ids_in_warehouse = [item_doc["item_id"] for item_doc in warehouse_item_docs]
    item_definitions_cursor = db_provider.item_definitions_collection.find(
        {"item_id": {"$in": item_ids_in_warehouse}}
    )
    item_definitions_map: Dict[str, ItemDefinition] = {
        item_def_doc["item_id"]: ItemDefinition.model_validate(item_def_doc, from_attributes=True)
        async for item_def_doc in item_definitions_cursor
    }

    for wh_item_doc in warehouse_item_docs:
        item_def = item_definitions_map.get(wh_item_doc["item_id"])
        if item_def:
            detailed_items.append(
                PlayerWarehouseItemDetail(
                    item_id=item_def.item_id,
                    name=item_def.name,
                    description=item_def.description,
                    category=item_def.category,
                    weight_per_unit=item_def.weight_per_unit,
                    volume_per_unit=item_def.volume_per_unit,
                    base_value_per_unit=item_def.base_value_per_unit,
                    is_fragile=item_def.is_fragile,
                    is_perishable=item_def.is_perishable,
                    quantity_in_warehouse=wh_item_doc["quantity"]
                )
            )
    return detailed_items

class CargoItemSelection(BaseModel):
    item_id: str
    quantity: int

class SelectCargoRequest(BaseModel):
    items: List[CargoItemSelection]

class SelectedCargoItemDetail(PlayerWarehouseItemDetail): # For response of selected cargo
    selected_quantity: int

class SelectedCargoSummary(BaseModel):
    items: List[SelectedCargoItemDetail]
    total_weight: float
    total_volume: float
    warnings: List[str] = []

class SelectCargoResponse(BaseModel):
    message: str
    selected_cargo_summary: SelectedCargoSummary

@game_setup_router.put("/player/game_session/cargo", response_model=SelectCargoResponse)
async def select_cargo_for_session(
    request_body: SelectCargoRequest = Body(...),
    current_user: User = Depends(get_current_user)
):
    if not all([db_provider.users_collection, 
                db_provider.player_warehouse_items_collection, 
                db_provider.item_definitions_collection,
                db_provider.vehicle_definitions_collection]):
        raise HTTPException(status_code=503, detail="一個或多個必要的資料庫服務未初始化")

    user_doc = await db_provider.users_collection.find_one({"user_id": current_user.user_id})
    if not user_doc: raise HTTPException(status_code=500, detail="無法獲取用戶數據")
    
    session_setup = CurrentGameSessionSetup.model_validate((user_doc.get("current_game_session_setup", from_attributes=True) or {}))
    if not session_setup.selected_vehicle_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="請先選擇車輛才能選擇貨物")
    
    vehicle_def_doc = await db_provider.vehicle_definitions_collection.find_one({"vehicle_id": session_setup.selected_vehicle_id})
    if not vehicle_def_doc: raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所選車輛定義無效")
    vehicle_def = VehicleDefinition.model_validate(vehicle_def_doc, from_attributes=True)

    selected_cargo_items_to_store: List[CurrentGameSessionSetupItem] = []
    response_cargo_details: List[SelectedCargoItemDetail] = []
    current_total_weight = 0.0
    current_total_volume = 0.0
    warnings: List[str] = []

    # Fetch all required item definitions and warehouse quantities in fewer queries
    requested_item_ids = [item.item_id for item in request_body.items]
    
    item_defs_cursor = db_provider.item_definitions_collection.find({"item_id": {"$in": requested_item_ids}})
    item_definitions_map: Dict[str, ItemDefinition] = {
        doc["item_id"]: ItemDefinition.model_validate(doc, from_attributes=True) async for doc in item_defs_cursor
    }
    
    warehouse_items_cursor = db_provider.player_warehouse_items_collection.find({
        "user_id": current_user.user_id, # Changed from player_id to user_id
        "item_id": {"$in": requested_item_ids}
    })
    warehouse_quantities_map: Dict[str, int] = {
        doc["item_id"]: doc["quantity"] async for doc in warehouse_items_cursor
    }

    for item_selection in request_body.items:
        if item_selection.quantity <= 0:
            warnings.append(f"物品 {item_selection.item_id} 的選擇數量必須為正。")
            continue

        item_def = item_definitions_map.get(item_selection.item_id)
        if not item_def:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"物品定義 {item_selection.item_id} 不存在。")

        quantity_in_warehouse = warehouse_quantities_map.get(item_selection.item_id, 0)
        if item_selection.quantity > quantity_in_warehouse:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                                detail=f"物品 {item_def.name} ({item_selection.item_id}) 倉庫數量不足 (需求: {item_selection.quantity}, 現有: {quantity_in_warehouse})。")

        selected_cargo_items_to_store.append(CurrentGameSessionSetupItem(item_id=item_def.item_id, quantity=item_selection.quantity))
        
        item_total_weight = item_def.weight_per_unit * item_selection.quantity
        item_total_volume = item_def.volume_per_unit * item_selection.quantity
        current_total_weight += item_total_weight
        current_total_volume += item_total_volume
        
        response_cargo_details.append(
            SelectedCargoItemDetail(
                item_id=item_def.item_id, name=item_def.name, description=item_def.description,
                category=item_def.category, weight_per_unit=item_def.weight_per_unit,
                volume_per_unit=item_def.volume_per_unit, base_value_per_unit=item_def.base_value_per_unit,
                is_fragile=item_def.is_fragile, is_perishable=item_def.is_perishable,
                quantity_in_warehouse=quantity_in_warehouse, # Show total in warehouse
                selected_quantity=item_selection.quantity # Show selected quantity
            )
        )

    if current_total_weight > vehicle_def.max_load_weight:
        warnings.append(f"貨物總重量 ({current_total_weight:.2f}) 超出車輛最大載重 ({vehicle_def.max_load_weight:.2f})。")
    if current_total_volume > vehicle_def.max_load_volume:
        warnings.append(f"貨物總體積 ({current_total_volume:.2f}) 超出車輛最大容積 ({vehicle_def.max_load_volume:.2f})。")

    session_setup.selected_cargo = selected_cargo_items_to_store
    session_setup.last_updated_at = datetime.now()

    await db_provider.users_collection.update_one(
        {"user_id": current_user.user_id},
        {"$set": {"current_game_session_setup": session_setup.dict(by_alias=True, exclude_none=True)}}
    )

    return SelectCargoResponse(
        message="貨物選擇已更新。" + (" " + " ".join(warnings) if warnings else ""),
        selected_cargo_summary=SelectedCargoSummary(
            items=response_cargo_details,
            total_weight=current_total_weight,
            total_volume=current_total_volume,
            warnings=warnings
        )
    )

class SelectVehicleRequest(BaseModel):
    vehicle_id: str 

class SelectVehicleResponse(BaseModel):
    message: str
    selected_vehicle: Dict[str, Any]
    cleared_cargo: bool

class SelectDestinationRequest(BaseModel):
    destination_id: str

class SelectDestinationResponse(BaseModel):
    message: str
    selected_destination: Dict[str, Any] # e.g., {"destination_id": "uuid", "name": "Dest Name", "region": "Region"}

@game_setup_router.put("/player/game_session/destination", response_model=SelectDestinationResponse)
async def select_destination_for_session(
    request_body: SelectDestinationRequest = Body(...),
    current_user: User = Depends(get_current_user)
):
    if db_provider.users_collection is None or \
       db_provider.destinations_collection is None:
        raise HTTPException(status_code=503, detail="資料庫服務未初始化")

    destination_uuid_to_select = request_body.destination_id
    
    dest_doc = await db_provider.destinations_collection.find_one({"destination_id": destination_uuid_to_select})
    if not dest_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="選擇的目的地不存在")
    destination = Destination.model_validate(dest_doc, from_attributes=True)

    # Verify player can select this destination (already done implicitly by list_player_selectable_destinations, but good to double check)
    can_select = False
    if destination.is_unlocked_by_default:
        can_select = True
    elif destination.unlock_requirements and \
         destination.unlock_requirements.required_player_level and \
         current_user.level >= destination.unlock_requirements.required_player_level:
        can_select = True
    
    if not can_select:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="玩家無權選擇此目的地")

    user_doc = await db_provider.users_collection.find_one({"user_id": current_user.user_id}) 
    if not user_doc: raise HTTPException(status_code=500, detail="無法獲取用戶數據") # Should not happen

    session_setup_data = user_doc.get("current_game_session_setup")
    current_session_setup = CurrentGameSessionSetup.model_validate(session_setup_data, from_attributes=True) if session_setup_data else CurrentGameSessionSetup()
    
    current_session_setup.selected_destination_id = destination.destination_id
    current_session_setup.last_updated_at = datetime.now()

    await db_provider.users_collection.update_one(
        {"user_id": current_user.user_id},
        {"$set": {"current_game_session_setup": current_session_setup.dict(by_alias=True, exclude_none=True)}}
    )
    return SelectDestinationResponse(
        message="目的地選擇成功。",
        selected_destination={ 
            "destination_id": destination.destination_id, 
            "name": destination.name, 
            "region": destination.region 
        }
    )

@game_setup_router.put("/player/game_session/vehicle", response_model=SelectVehicleResponse)
async def select_vehicle_for_session(
    request_body: SelectVehicleRequest = Body(...),
    current_user: User = Depends(get_current_user)
):
    if db_provider.users_collection is None or \
       db_provider.vehicle_definitions_collection is None or \
       db_provider.player_owned_vehicles_collection is None:
        raise HTTPException(status_code=503, detail="資料庫服務未初始化")

    vehicle_def_uuid_to_select = request_body.vehicle_id
    
    vehicle_def_doc = await db_provider.vehicle_definitions_collection.find_one({"vehicle_id": vehicle_def_uuid_to_select})
    if not vehicle_def_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="選擇的車輛定義不存在")
    vehicle_def = VehicleDefinition.model_validate(vehicle_def_doc, from_attributes=True)

    can_use_vehicle = False
    # Query PlayerOwnedVehicle using user_id and vehicle_id (which is the foreign key to VehicleDefinition)
    player_owned_vehicle_doc = await db_provider.player_owned_vehicles_collection.find_one({
        "user_id": current_user.user_id,      # Changed from player_id
        "vehicle_id": vehicle_def_uuid_to_select # Changed from definition_id, this now refers to VehicleDefinition.vehicle_id
    })

    if player_owned_vehicle_doc:
        owned_vehicle = PlayerOwnedVehicle.model_validate(player_owned_vehicle_doc, from_attributes=True)
        if not owned_vehicle.is_in_active_session: can_use_vehicle = True
        else: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="此車輛正在使用中")
    elif "rentable" in vehicle_def.availability_type: can_use_vehicle = True # Simplified
    
    if not can_use_vehicle:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="玩家無權使用此車輛")

    user_doc = await db_provider.users_collection.find_one({"user_id": current_user.user_id}) 
    if not user_doc: raise HTTPException(status_code=500, detail="無法獲取用戶數據")

    session_setup_data = user_doc.get("current_game_session_setup")
    current_session_setup = CurrentGameSessionSetup.model_validate(session_setup_data, from_attributes=True) if session_setup_data else CurrentGameSessionSetup()
    
    cleared_cargo_flag = bool(current_session_setup.selected_cargo)
    current_session_setup.selected_vehicle_id = vehicle_def.vehicle_id
    current_session_setup.selected_cargo = []
    current_session_setup.last_updated_at = datetime.now()

    await db_provider.users_collection.update_one(
        {"user_id": current_user.user_id},
        {"$set": {"current_game_session_setup": current_session_setup.dict(by_alias=True, exclude_none=True)}}
    )
    return SelectVehicleResponse(
        message="車輛選擇成功。任何先前選擇的貨物已被清除。",
        selected_vehicle={ "vehicle_id": vehicle_def.vehicle_id, "name": vehicle_def.name, 
                           "max_load_weight": vehicle_def.max_load_weight, "max_load_volume": vehicle_def.max_load_volume },
        cleared_cargo=cleared_cargo_flag
    )

# --- Cargo Selection ---
# ... (Assuming other cargo related classes and routes are defined here and reviewed for ID usage)

# --- Destination Selection ---
# ... (Assuming other destination related classes and routes are defined here and reviewed for ID usage)

# --- Final Confirmation & Start Game ---

@game_setup_router.get("/player/game_session/summary", response_model=GameSessionSummaryResponse) # No longer a string
async def get_game_session_summary(current_user: User = Depends(get_current_user)):
    required_db_collections = [
        db_provider.users_collection, 
        db_provider.vehicle_definitions_collection, 
        db_provider.item_definitions_collection, 
        db_provider.destinations_collection,
        db_provider.player_tasks_collection, 
        db_provider.task_definitions_collection # Corrected task collection name
    ]
    if any(coll is None for coll in required_db_collections):
        raise HTTPException(status_code=503, detail="一個或多個必要的資料庫服務未初始化")

    user_doc = await db_provider.users_collection.find_one({"user_id": current_user.user_id})
    if not user_doc: raise HTTPException(status_code=500, detail="無法獲取用戶數據")
    
    current_session_setup = CurrentGameSessionSetup.model_validate((user_doc.get("current_game_session_setup", from_attributes=True) or {}))
    summary_main = SessionSummaryMain()
    can_start_game_flag = True; warnings: List[str] = []

    if current_session_setup.selected_vehicle_id:
        vd_doc = await db_provider.vehicle_definitions_collection.find_one({"vehicle_id": current_session_setup.selected_vehicle_id})
        if vd_doc:
            vd = VehicleDefinition.model_validate(vd_doc, from_attributes=True)
            summary_main.selected_vehicle = SessionSummaryVehicle(
                vehicle_id=vd.vehicle_id, 
                name=vd.name, max_load_weight=vd.max_load_weight, max_load_volume=vd.max_load_volume
            )
        else: can_start_game_flag = False; warnings.append("選擇的車輛無效。")
    else: can_start_game_flag = False; warnings.append("尚未選擇車輛。")

    current_total_weight = 0.0; current_total_volume = 0.0
    summary_cargo_items: List[SessionSummaryCargoItem] = []
    if current_session_setup.selected_cargo:
        for cargo_item_setup in current_session_setup.selected_cargo:
            item_def_doc = await db_provider.item_definitions_collection.find_one({"item_id": cargo_item_setup.item_id})
            if item_def_doc:
                item_def = ItemDefinition.model_validate(item_def_doc, from_attributes=True)
                summary_cargo_items.append(SessionSummaryCargoItem(
                    item_id=item_def.item_id, 
                    name=item_def.name, quantity=cargo_item_setup.quantity,
                    weight_per_unit=item_def.weight_per_unit, volume_per_unit=item_def.volume_per_unit
                    # base_value_per_unit=item_def.base_value_per_unit # Add if needed
                ))
                current_total_weight += item_def.weight_per_unit * cargo_item_setup.quantity
                current_total_volume += item_def.volume_per_unit * cargo_item_setup.quantity
            else: warnings.append(f"貨物 {cargo_item_setup.item_id} 定義無效。"); can_start_game_flag = False
        summary_main.selected_cargo = SessionSummaryCargo(items=summary_cargo_items, total_weight=current_total_weight, total_volume=current_total_volume)
        if summary_main.selected_vehicle:
            if current_total_weight > summary_main.selected_vehicle.max_load_weight: can_start_game_flag = False; warnings.append("貨物超重")
            if current_total_volume > summary_main.selected_vehicle.max_load_volume: can_start_game_flag = False; warnings.append("貨物超容積")
    
    if current_session_setup.selected_destination_id:
        dest_doc = await db_provider.destinations_collection.find_one({"destination_id": current_session_setup.selected_destination_id})
        if dest_doc:
            dest = Destination.model_validate(dest_doc, from_attributes=True)
            summary_main.selected_destination = SessionSummaryDestination(destination_id=dest.destination_id, name=dest.name, region=dest.region)
        else: can_start_game_flag = False; warnings.append("選擇的目的地無效。")
    else: can_start_game_flag = False; warnings.append("尚未選擇目的地。")

    related_tasks_summary: List[RelatedTaskSummary] = []
    player_accepted_tasks_docs = await db_provider.player_tasks_collection.find({
        "user_id": current_user.user_id, "status": "accepted" # Changed player_id to user_id
    }).to_list(length=None)

    for pt_doc in player_accepted_tasks_docs:
        pt = PlayerTask.model_validate(pt_doc, from_attributes=True) 
        task_def_doc = await db_provider.task_definitions_collection.find_one({"task_id": pt.task_id})
        if not task_def_doc: continue
        task_def = TaskDefinition.model_validate(task_def_doc, from_attributes=True)
        related_tasks_summary.append(RelatedTaskSummary(
            player_task_id=pt.player_task_id, 
            task_id=pt.task_id, 
            title=task_def.title, status=pt.status,
            is_completable_with_current_setup=True, # Placeholder
            completion_issues=[] # Placeholder
        ))

    return GameSessionSummaryResponse(
        session_summary=summary_main, related_tasks=related_tasks_summary,
        can_start_game=can_start_game_flag, start_game_warnings=warnings
    )

class StartGameRequest(BaseModel):
    confirmed_player_task_ids: Optional[List[str]] = None 

class StartGameResponse(BaseModel):
    message: str
    game_session_id: str 
    status: str
    start_time: datetime

@game_setup_router.post("/player/game_session/start", response_model=StartGameResponse)
async def start_game_session(
    request_body: Optional[StartGameRequest] = Body(None), 
    current_user: User = Depends(get_current_user)
):
    if not all([db_provider.users_collection, db_provider.vehicle_definitions_collection, 
                db_provider.item_definitions_collection, db_provider.destinations_collection,
                db_provider.player_warehouse_items_collection, db_provider.game_sessions_collection,
                db_provider.player_tasks_collection, db_provider.player_owned_vehicles_collection,
                db_provider.task_definitions_collection]): 
        raise HTTPException(status_code=503, detail="一個或多個必要的資料庫服務未初始化")

    user_doc = await db_provider.users_collection.find_one({"user_id": current_user.user_id})
    if not user_doc: raise HTTPException(status_code=500, detail="無法獲取用戶數據")

    if user_doc.get("active_game_session_id"):
        active_session = await db_provider.game_sessions_collection.find_one({
            "game_session_id": user_doc["active_game_session_id"], 
            "status": "in_progress"
        })
        if active_session: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="玩家已有正在進行的遊戲會話")

    session_setup = CurrentGameSessionSetup.model_validate((user_doc.get("current_game_session_setup", from_attributes=True) or {}))
    if not session_setup.selected_vehicle_id or not session_setup.selected_destination_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="必須選擇車輛和目的地才能開始遊戲")

    vehicle_def_doc = await db_provider.vehicle_definitions_collection.find_one({"vehicle_id": session_setup.selected_vehicle_id})
    if not vehicle_def_doc: raise HTTPException(status_code=400, detail="選擇的車輛無效")
    vehicle_def = VehicleDefinition.model_validate(vehicle_def_doc, from_attributes=True)

    destination_def_doc = await db_provider.destinations_collection.find_one({"destination_id": session_setup.selected_destination_id})
    if not destination_def_doc: raise HTTPException(status_code=400, detail="選擇的目的地無效")
    destination_def = Destination.model_validate(destination_def_doc, from_attributes=True)
    
    cargo_snapshot_items_models: List[CargoItemSnapshot] = []
    # ... (Assume cargo processing populates cargo_snapshot_items_models correctly using custom item_ids)

    # Determine the correct used_vehicle_id for the session
    final_used_vehicle_id = vehicle_def.vehicle_id # Default to definition ID (e.g., for rentals)
    owned_vehicle_instance_doc = await db_provider.player_owned_vehicles_collection.find_one({
        "user_id": current_user.user_id,
        "vehicle_id": vehicle_def.vehicle_id # Querying PlayerOwnedVehicle by its foreign key to VehicleDefinition
    })
    if owned_vehicle_instance_doc:
        owned_vehicle = PlayerOwnedVehicle.model_validate(owned_vehicle_instance_doc, from_attributes=True)
        final_used_vehicle_id = owned_vehicle.instance_id # Use the specific instance_id if owned

    new_game_session_instance = GameSession(
        user_id=current_user.user_id, # Changed from player_id
        used_vehicle_id=final_used_vehicle_id, 
        vehicle_snapshot=VehicleSnapshot.model_validate(vehicle_def.dict(exclude={'id', 'vehicle_id'})), 
        cargo_snapshot=cargo_snapshot_items_models, 
        total_cargo_weight_at_start=0, # Placeholder
        total_cargo_volume_at_start=0, # Placeholder
        destination_id=destination_def.destination_id, 
        destination_snapshot=DestinationSnapshot.model_validate(destination_def.dict(include={'name', 'region'})),
        associated_player_task_ids=request_body.confirmed_player_task_ids if request_body else [], 
        start_time=datetime.now(), status="in_progress", last_updated_at=datetime.now()
    )
    new_game_session_data = new_game_session_instance.dict(by_alias=True, exclude_none=True)
    insert_session_res = await db_provider.game_sessions_collection.insert_one(new_game_session_data)
    
    created_session_doc = await db_provider.game_sessions_collection.find_one({"_id": insert_session_res.inserted_id})
    if not created_session_doc: raise HTTPException(500, "Failed to create game session")
    created_game_session = GameSession.model_validate(created_session_doc, from_attributes=True)

    await db_provider.users_collection.update_one(
        {"user_id": current_user.user_id},
        {"$set": {"active_game_session_id": created_game_session.game_session_id, "current_game_session_setup": None}}
    )

    return StartGameResponse(
        message="遊戲會話已成功開始！",
        game_session_id=created_game_session.game_session_id, 
        status="in_progress",
        start_time=created_game_session.start_time
    )

# No need for update_forward_refs() or model_rebuild() if classes are defined before use.
# If there were true circular dependencies needing string forward refs, 
# then update_forward_refs() would be called on each model at the end of the file.
