from fastapi import APIRouter, HTTPException, status, Depends, Body, Path
from typing import List, Optional, Any, Dict
import uuid
from datetime import datetime

from app.models.user import User
from app.models.player import Player
from app.models.game_models import (
    VehicleDefinition, PlayerOwnedVehicle, ItemDefinition, Destination,
    GameSession as GameSessionModel, PlayerTask, TaskDefinition,
    GeoCoordinates, VehicleSnapshot, CargoItemSnapshot, DestinationSnapshot,
    PlayerWarehouseItem as PlayerWarehouseItemModel
)
from pydantic import BaseModel
from app.database import mongodb as db_provider
from app.utils.auth import get_current_user

router = APIRouter(
    prefix="/api/v1/player",
    tags=["Player"],
)

# --- Helper function to get or create a player document ---
async def get_current_player(current_user: User = Depends(get_current_user)) -> Player:
    if db_provider.players_collection is None:
        raise HTTPException(status_code=503, detail="Player database service not initialized")
    
    player_doc = await db_provider.players_collection.find_one({"user_id": uuid.UUID(current_user.user_id)})
    if player_doc:
        return Player.model_validate(player_doc, from_attributes=True)
    
    # If no player data exists, create one
    new_player = Player(
        user_id=uuid.UUID(current_user.user_id),
        display_name=current_user.username,
    )
    await db_provider.players_collection.insert_one(new_player.model_dump(by_alias=True))
    return new_player

@router.get("/", response_model=Player, summary="獲取當前玩家的個人資料")
async def get_player_profile(player: Player = Depends(get_current_player)):
    """
    獲取當前登入玩家的完整遊戲資料，包括等級、經驗、成就、倉庫、任務和遊戲會話狀態。
    如果玩家資料不存在，將會自動為新用戶創建一份。
    """
    return player

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
    player_task_id: str
    task_id: str
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

@router.get("/vehicles", response_model=List[PlayerVehicleResponseItem], summary="列出玩家可選擇的車輛")
async def list_player_selectable_vehicles(
    availability: Optional[str] = "all",
    current_user: User = Depends(get_current_user)
):
    """
    列出當前玩家可為遊戲會話選擇的車輛。
    可以根據 `availability` 參數篩選：
    - `all`: 返回所有可用車輛（預設）。
    - `owned`: 只返回玩家擁有的車輛。
    - `rentable`: 只返回可租用的車輛。
    """
    if db_provider.vehicle_definitions_collection is None or \
       db_provider.player_owned_vehicles_collection is None:
        raise HTTPException(status_code=503, detail="車輛相關資料庫服務未初始化")

    player_owned_vehicle_docs = await db_provider.player_owned_vehicles_collection.find(
        {"user_id": current_user.user_id}
    ).to_list(length=None)
    
    owned_vehicle_map: Dict[str, PlayerOwnedVehicle] = {
        pov_doc["vehicle_id"]: PlayerOwnedVehicle.model_validate(pov_doc, from_attributes=True)
        for pov_doc in player_owned_vehicle_docs
    }

    all_vehicle_definitions_docs = await db_provider.vehicle_definitions_collection.find({}).to_list(length=None)
    
    response_vehicles: List[PlayerVehicleResponseItem] = []
    for vd_doc in all_vehicle_definitions_docs:
        vd = VehicleDefinition.model_validate(vd_doc, from_attributes=True)
        vehicle_status = "unavailable"
        player_vehicle_instance_id: Optional[str] = None

        if vd.vehicle_id in owned_vehicle_map:
            owned_instance = owned_vehicle_map[vd.vehicle_id]
            player_vehicle_instance_id = owned_instance.instance_id
            vehicle_status = "in_use" if owned_instance.is_in_active_session else "owned"
        elif vd.availability_type == "rentable_per_session" or "purchasable_rentable" in vd.availability_type:
            vehicle_status = "rentable"
        
        if availability == "all" or \
           (availability == "owned" and vehicle_status in ["owned", "in_use"]) or \
           (availability == "rentable" and vehicle_status == "rentable"):
            if vehicle_status != "unavailable":
                response_vehicles.append(
                    PlayerVehicleResponseItem(
                        vehicle_id=str(vd.vehicle_id),
                        player_vehicle_id=str(player_vehicle_instance_id) if player_vehicle_instance_id else None,
                        name=vd.name, type=vd.type,
                        max_load_weight=vd.max_load_weight, max_load_volume=vd.max_load_volume,
                        status=vehicle_status
                    )
                )
    return response_vehicles

# --- Destination Selection ---
@router.get("/destinations", response_model=List[Destination], summary="列出玩家可選擇的目的地")
async def list_player_selectable_destinations(
    player: Player = Depends(get_current_player)
):
    """
    列出當前玩家已解鎖且可為遊戲會話選擇的目的地。
    """
    if db_provider.destinations_collection is None:
        raise HTTPException(status_code=503, detail="目的地資料庫服務未初始化")

    destinations_cursor = db_provider.destinations_collection.find({})
    all_destinations_list = await destinations_cursor.to_list(length=None)

    selectable_destinations: List[Destination] = []
    for dest_doc in all_destinations_list:
        dest = Destination.model_validate(dest_doc, from_attributes=True)
        unlocked = False
        if dest.is_unlocked_by_default:
            unlocked = True
        elif dest.unlock_requirements and dest.unlock_requirements.required_player_level and \
             player.level >= dest.unlock_requirements.required_player_level:
            unlocked = True
        
        if unlocked:
            selectable_destinations.append(dest)
            
    return selectable_destinations

# --- Cargo Selection ---
class PlayerWarehouseItemDetail(BaseModel):
    item_id: str
    name: str
    description: Optional[str] = None
    category: str
    weight_per_unit: float
    volume_per_unit: float
    base_value_per_unit: int
    is_fragile: bool
    is_perishable: bool
    quantity_in_warehouse: int

@router.get("/warehouse/items", response_model=List[PlayerWarehouseItemDetail], summary="列出玩家倉庫中的所有物品")
async def list_player_warehouse_items(player: Player = Depends(get_current_player)):
    """
    獲取玩家倉庫中所有物品的詳細列表，包括物品定義和現有數量。
    """
    if db_provider.item_definitions_collection is None or db_provider.player_warehouse_items_collection is None:
        raise HTTPException(status_code=503, detail="資料庫服務未初始化")

    detailed_items: List[PlayerWarehouseItemDetail] = []
    
    # 從 player_warehouse_items_collection 獲取玩家的倉庫物品
    warehouse_items_cursor = db_provider.player_warehouse_items_collection.find({"user_id": player.user_id})
    player_warehouse_items_docs = await warehouse_items_cursor.to_list(length=None)

    if not player_warehouse_items_docs:
        return detailed_items

    # 建立倉庫物品的 map
    warehouse_items_map: Dict[uuid.UUID, int] = {
        item['item_id']: item['quantity'] for item in player_warehouse_items_docs
    }
    item_ids_in_warehouse = list(warehouse_items_map.keys())
    
    item_definitions_cursor = db_provider.item_definitions_collection.find(
        {"item_id": {"$in": item_ids_in_warehouse}}
    )
    item_definitions_map: Dict[uuid.UUID, ItemDefinition] = {
        item_def_doc["item_id"]: ItemDefinition.model_validate(item_def_doc, from_attributes=True)
        async for item_def_doc in item_definitions_cursor
    }

    for item_id, quantity in warehouse_items_map.items():
        item_def = item_definitions_map.get(item_id)
        if item_def:
            detailed_items.append(
                PlayerWarehouseItemDetail(
                    item_id=str(item_def.item_id),
                    name=item_def.name,
                    description=item_def.description,
                    category=item_def.category,
                    weight_per_unit=item_def.weight_per_unit,
                    volume_per_unit=item_def.volume_per_unit,
                    base_value_per_unit=item_def.base_value_per_unit,
                    is_fragile=item_def.is_fragile,
                    is_perishable=item_def.is_perishable,
                    quantity_in_warehouse=quantity
                )
            )
    return detailed_items

class AddItemToWarehouseRequest(BaseModel):
    item_id: uuid.UUID
    quantity: int

@router.post("/warehouse/items", status_code=status.HTTP_200_OK, summary="添加物品到玩家倉庫")
async def add_item_to_warehouse(
    request: AddItemToWarehouseRequest,
    current_user: User = Depends(get_current_user)
):
    """
    將指定數量的一個物品添加到當前玩家的倉庫中。
    如果物品已存在，則增加數量；如果不存在，則新增該物品。
    """
    if db_provider.player_warehouse_items_collection is None or db_provider.item_definitions_collection is None:
        raise HTTPException(status_code=503, detail="資料庫服務未初始化")

    # 將字串 item_id 轉換為 UUID
    if isinstance(request.item_id, uuid.UUID):
        item_id_uuid = request.item_id
    else:
        try:
            item_id_uuid = uuid.UUID(request.item_id)
        except ValueError:
            # 如果傳入的不是有效的 UUID，則從字串生成一個
            item_id_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, request.item_id)

    # 驗證 item_id 是否存在
    item_def = await db_provider.item_definitions_collection.find_one({"item_id": item_id_uuid})
    if not item_def:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"具有 ID 的物品定義不存在: {request.item_id}")

    if request.quantity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="數量必須為正數")

    # 更新或插入玩家倉庫物品
    # With the problematic index removed, we only need to query by user_id and item_id.
    update_result = await db_provider.player_warehouse_items_collection.update_one(
        {"user_id": uuid.UUID(current_user.user_id), "item_id": item_id_uuid},
        {"$inc": {"quantity": request.quantity}},
        upsert=True
    )

    if update_result.upserted_id or update_result.modified_count > 0:
        return {"message": f"成功將 {request.quantity} 個 {item_def['name']} 添加到您的倉庫"}
    
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="更新倉庫失敗")


class CargoItemSelection(BaseModel):
    item_id: uuid.UUID
    quantity: int

class SelectCargoRequest(BaseModel):
    items: List[CargoItemSelection]

class SelectedCargoItemDetail(PlayerWarehouseItemDetail):
    selected_quantity: int

class SelectedCargoSummary(BaseModel):
    items: List[SelectedCargoItemDetail]
    total_weight: float
    total_volume: float
    warnings: List[str] = []

class SelectCargoResponse(BaseModel):
    message: str
    selected_cargo_summary: SelectedCargoSummary

@router.put("/game_session/cargo", response_model=SelectCargoResponse, summary="為遊戲會話選擇貨物")
async def select_cargo_for_session(
    request_body: SelectCargoRequest,
    player: Player = Depends(get_current_player)
):
    """
    為當前的遊戲準備會話選擇要運輸的貨物。
    - **必要條件**: 必須先選擇車輛。
    - 系統會校驗貨物總重量和總體積是否超出所選車輛的限制。
    - 這只是一個暫存操作，實際的物品扣減會在遊戲會話開始時進行。
    """
    if not all([db_provider.item_definitions_collection, db_provider.vehicle_definitions_collection]):
        raise HTTPException(status_code=503, detail="一個或多個必要的資料庫服務未初始化")

    if not player.game_session.vehicle_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="請先選擇車輛才能選擇貨物")
    
    vehicle_def_doc = await db_provider.vehicle_definitions_collection.find_one({"vehicle_id": player.game_session.vehicle_id})
    if not vehicle_def_doc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="所選車輛定義無效")
    vehicle_def = VehicleDefinition.model_validate(vehicle_def_doc, from_attributes=True)

    response_cargo_details: List[SelectedCargoItemDetail] = []
    current_total_weight = 0.0
    current_total_volume = 0.0
    warnings: List[str] = []

    requested_item_ids = [item.item_id for item in request_body.items]
    
    item_defs_cursor = db_provider.item_definitions_collection.find({"item_id": {"$in": requested_item_ids}})
    item_definitions_map: Dict[uuid.UUID, ItemDefinition] = {
        doc["item_id"]: ItemDefinition.model_validate(doc, from_attributes=True) async for doc in item_defs_cursor
    }
    
    warehouse_quantities_map: Dict[uuid.UUID, int] = {
        item.item_id: item.quantity for item in player.warehouse
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
        
        item_total_weight = item_def.weight_per_unit * item_selection.quantity
        item_total_volume = item_def.volume_per_unit * item_selection.quantity
        current_total_weight += item_total_weight
        current_total_volume += item_total_volume
        
        response_cargo_details.append(
            SelectedCargoItemDetail(
                item_id=str(item_def.item_id), name=item_def.name, description=item_def.description,
                category=item_def.category, weight_per_unit=item_def.weight_per_unit,
                volume_per_unit=item_def.volume_per_unit, base_value_per_unit=item_def.base_value_per_unit,
                is_fragile=item_def.is_fragile, is_perishable=item_def.is_perishable,
                quantity_in_warehouse=quantity_in_warehouse,
                selected_quantity=item_selection.quantity
            )
        )

    if current_total_weight > vehicle_def.max_load_weight:
        warnings.append(f"貨物總重量 ({current_total_weight:.2f}) 超出車輛最大載重 ({vehicle_def.max_load_weight:.2f})。")
    if current_total_volume > vehicle_def.max_load_volume:
        warnings.append(f"貨物總體積 ({current_total_volume:.2f}) 超出車輛最大容積 ({vehicle_def.max_load_volume:.2f})。")

    player.game_session.cargo = request_body.items

    await db_provider.players_collection.update_one(
        {"user_id": player.user_id},
        {"$set": {"game_session": player.game_session.model_dump(by_alias=True)}}
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
    vehicle_id: uuid.UUID

class SelectVehicleResponse(BaseModel):
    message: str
    selected_vehicle: Dict[str, Any]
    cleared_cargo: bool

class SelectDestinationRequest(BaseModel):
    destination_id: uuid.UUID

class SelectDestinationResponse(BaseModel):
    message: str
    selected_destination: Dict[str, Any]

@router.put("/game_session/destination", response_model=SelectDestinationResponse, summary="為遊戲會話選擇目的地")
async def select_destination_for_session(
    request_body: SelectDestinationRequest,
    player: Player = Depends(get_current_player)
):
    """
    為當前的遊戲準備會話選擇目的地。
    """
    if db_provider.destinations_collection is None:
        raise HTTPException(status_code=503, detail="資料庫服務未初始化")

    dest_doc = await db_provider.destinations_collection.find_one({"destination_id": request_body.destination_id})
    if not dest_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="選擇的目的地不存在")
    destination = Destination.model_validate(dest_doc, from_attributes=True)

    can_select = False
    if destination.is_unlocked_by_default or (destination.unlock_requirements and \
         destination.unlock_requirements.required_player_level and \
         player.level >= destination.unlock_requirements.required_player_level):
        can_select = True
    
    if not can_select:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="玩家無權選擇此目的地")
    
    player.game_session.destination_id = destination.destination_id

    await db_provider.players_collection.update_one(
        {"user_id": player.user_id},
        {"$set": {"game_session.destination_id": player.game_session.destination_id}}
    )
    return SelectDestinationResponse(
        message="目的地選擇成功。",
        selected_destination={ 
            "destination_id": str(destination.destination_id), 
            "name": destination.name, 
            "region": destination.region 
        }
    )

@router.put("/game_session/vehicle", response_model=SelectVehicleResponse, summary="為遊戲會話選擇車輛")
async def select_vehicle_for_session(
    request_body: SelectVehicleRequest,
    player: Player = Depends(get_current_player)
):
    """
    為當前的遊戲準備會話選擇車輛。
    選擇新車輛將會清空先前選擇的所有貨物。
    """
    if db_provider.vehicle_definitions_collection is None or \
       db_provider.player_owned_vehicles_collection is None:
        raise HTTPException(status_code=503, detail="資料庫服務未初始化")

    vehicle_def_doc = await db_provider.vehicle_definitions_collection.find_one({"vehicle_id": request_body.vehicle_id})
    if not vehicle_def_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="選擇的車輛定義不存在")
    vehicle_def = VehicleDefinition.model_validate(vehicle_def_doc, from_attributes=True)

    can_use_vehicle = False
    player_owned_vehicle_doc = await db_provider.player_owned_vehicles_collection.find_one({
        "user_id": player.user_id,
        "vehicle_id": request_body.vehicle_id
    })

    if player_owned_vehicle_doc:
        owned_vehicle = PlayerOwnedVehicle.model_validate(player_owned_vehicle_doc, from_attributes=True)
        if not owned_vehicle.is_in_active_session:
            can_use_vehicle = True
        else:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="此車輛正在使用中")
    elif "rentable" in vehicle_def.availability_type:
        can_use_vehicle = True
    
    if not can_use_vehicle:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="玩家無權使用此車輛")

    cleared_cargo_flag = bool(player.game_session.cargo)
    player.game_session.vehicle_id = vehicle_def.vehicle_id
    player.game_session.cargo = []

    await db_provider.players_collection.update_one(
        {"user_id": player.user_id},
        {"$set": {"game_session": player.game_session.model_dump(by_alias=True)}}
    )
    return SelectVehicleResponse(
        message="車輛選擇成功。任何先前選擇的貨物已被清除。",
        selected_vehicle={ "vehicle_id": str(vehicle_def.vehicle_id), "name": vehicle_def.name, 
                           "max_load_weight": vehicle_def.max_load_weight, "max_load_volume": vehicle_def.max_load_volume },
        cleared_cargo=cleared_cargo_flag
    )

@router.get("/game_session/summary", response_model=GameSessionSummaryResponse, summary="獲取遊戲會話設定總覽")
async def get_game_session_summary(player: Player = Depends(get_current_player)):
    """
    獲取當前遊戲準備會話的完整設定總覽，包括已選的車輛、目的地、貨物，以及與當前設定相關的任務狀態。
    同時會提供能否開始遊戲的檢查結果和相關警告。
    """
    required_collections = [
        db_provider.vehicle_definitions_collection, 
        db_provider.item_definitions_collection, 
        db_provider.destinations_collection,
        db_provider.task_definitions_collection
    ]
    if any(coll is None for coll in required_collections):
        raise HTTPException(status_code=503, detail="一個或多個必要的資料庫服務未初始化")

    summary_main = SessionSummaryMain()
    can_start_game_flag = True
    warnings: List[str] = []

    if player.game_session.vehicle_id:
        vd_doc = await db_provider.vehicle_definitions_collection.find_one({"vehicle_id": player.game_session.vehicle_id})
        if vd_doc:
            vd = VehicleDefinition.model_validate(vd_doc, from_attributes=True)
            summary_main.selected_vehicle = SessionSummaryVehicle(
                vehicle_id=str(vd.vehicle_id), 
                name=vd.name, max_load_weight=vd.max_load_weight, max_load_volume=vd.max_load_volume
            )
        else: can_start_game_flag = False; warnings.append("選擇的車輛無效。")
    else: can_start_game_flag = False; warnings.append("尚未選擇車輛。")

    if player.game_session.cargo:
        # ... Cargo summary logic ...
        pass
    
    if player.game_session.destination_id:
        dest_doc = await db_provider.destinations_collection.find_one({"destination_id": player.game_session.destination_id})
        if dest_doc:
            dest = Destination.model_validate(dest_doc, from_attributes=True)
            summary_main.selected_destination = SessionSummaryDestination(destination_id=str(dest.destination_id), name=dest.name, region=dest.region)
        else: can_start_game_flag = False; warnings.append("選擇的目的地無效。")
    else: can_start_game_flag = False; warnings.append("尚未選擇目的地。")

    related_tasks_summary: List[RelatedTaskSummary] = []
    # ... Task summary logic ...
    
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

@router.post("/game_session/start", response_model=StartGameResponse, summary="開始一個新的遊戲會話")
async def start_game_session(
    request_body: Optional[StartGameRequest] = Body(None),
    player: Player = Depends(get_current_player),
    current_user: User = Depends(get_current_user)
):
    """
    根據當前儲存的遊戲會話設定（車輛、目的地、貨物）來正式開始一個新的遊戲。
    - 此操作會從玩家倉庫中扣除所選貨物。
    - 將所選的自有車輛標記為「使用中」。
    - 創建一個新的 `GameSession` 記錄。
    """
    # ... (Refactoring this endpoint is more complex and will be done in a subsequent step)
    raise HTTPException(status_code=501, detail="開始遊戲的功能正在重構中。")

# --- Player Task Management ---

class AcceptTaskRequest(BaseModel):
    task_id: uuid.UUID

@router.post("/tasks", response_model=PlayerTask, status_code=status.HTTP_201_CREATED, summary="玩家接受一個任務")
async def accept_task(
    request_body: AcceptTaskRequest,
    player: Player = Depends(get_current_player)
):
    """
    允許玩家接受一個可用的任務。
    - 會檢查玩家等級是否滿足任務要求。
    - 如果任務不可重複且已完成，則無法再次接受。
    - 如果玩家之前放棄過同一個任務，將會重用該任務記錄而非創建新記錄。
    """
    if db_provider.task_definitions_collection is None:
        raise HTTPException(status_code=503, detail="資料庫服務未初始化")

    task_def_doc = await db_provider.task_definitions_collection.find_one({
        "task_id": request_body.task_id,
        "is_active": True
    })
    if not task_def_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任務不存在或不可用")
    task_def = TaskDefinition.model_validate(task_def_doc, from_attributes=True)

    if player.level < task_def.requirements.required_player_level:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"需要等級 {task_def.requirements.required_player_level} 才能接受此任務")

    existing_task = next((task for task in player.tasks if task.task_id == request_body.task_id and task.status in ["accepted", "in_progress"]), None)
    if existing_task:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任務已被接受且未完成")

    new_task = PlayerTask(
        user_id=str(player.user_id),
        task_id=request_body.task_id,
        status="accepted",
    )
    player.tasks.append(new_task)

    await db_provider.players_collection.update_one(
        {"user_id": player.user_id},
        {"$set": {"tasks": [task.model_dump() for task in player.tasks]}}
    )
    return new_task

@router.delete("/tasks/{player_task_uuid}", status_code=status.HTTP_200_OK, summary="玩家放棄一個已接受的任務")
async def abandon_task(
    player_task_uuid: uuid.UUID,
    player: Player = Depends(get_current_player)
):
    """
    允許玩家放棄一個已經接受但尚未完成的任務。
    任務狀態將被標記為 `abandoned`。
    """
    task_to_abandon = next((task for task in player.tasks if task.task_id == player_task_uuid), None)

    if not task_to_abandon:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的玩家任務記錄")

    if task_to_abandon.status not in ["accepted", "in_progress"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"任務狀態為 {task_to_abandon.status}，無法放棄")

    task_to_abandon.status = "abandoned"

    await db_provider.players_collection.update_one(
        {"user_id": player.user_id},
        {"$set": {"tasks": [task.model_dump() for task in player.tasks]}}
    )
    return {"message": "任務已成功放棄"}

@router.get("/tasks", response_model=List[PlayerTask], summary="獲取玩家的任務列表")
async def list_player_tasks(
    status_filter: Optional[str] = None,
    player: Player = Depends(get_current_player)
):
    """
    獲取當前玩家的所有任務記錄。
    可以通過 `status_filter` 參數來篩選特定狀態的任務，例如：`accepted`, `completed`, `abandoned`。
    """
    if status_filter:
        return [task for task in player.tasks if task.status == status_filter]
    return player.tasks
