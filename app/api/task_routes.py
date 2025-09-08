from fastapi import APIRouter, HTTPException, status, Depends, Body, Path
from typing import List, Optional, Any, Dict
from datetime import datetime
# from bson import ObjectId # ObjectId might not be needed directly in routes if using custom IDs

from app.models.user import User
from app.models.game_models import TaskDefinition, PlayerTask, BaseModel # BaseModel for AcceptTaskRequest
from app.database import mongodb as db_provider # Renamed for clarity
from app.utils.auth import get_current_user
import uuid # For validating UUIDs if needed

task_definition_router = APIRouter(prefix="/tasks", tags=["任務定義 (Game Tasks Definitions)"])
player_task_router = APIRouter(prefix="/player/tasks", tags=["玩家任務 (Player Tasks)"])

# --- 任務定義相關 API ---

@task_definition_router.get("/", response_model=List[TaskDefinition])
async def list_available_tasks(
    type: Optional[str] = None,
):
    """
    獲取當前可供選擇的任務列表。
    """
    if db_provider.task_definitions_collection is None: 
        raise HTTPException(status_code=503, detail="任務定義資料庫服務未初始化")

    query: Dict[str, Any] = {"is_active": True}
    if type:
        query["type"] = type
    
    now = datetime.now()
    query["$or"] = [
        {"availability_start_date": {"$lte": now}, "availability_end_date": {"$gte": now}},
        {"availability_start_date": {"$lte": now}, "availability_end_date": None},
        {"availability_start_date": None, "availability_end_date": {"$gte": now}},
        {"availability_start_date": None, "availability_end_date": None}
    ]

    tasks_cursor = db_provider.task_definitions_collection.find(query)
    tasks_list = await tasks_cursor.to_list(length=None)
    
    return [TaskDefinition(**task) for task in tasks_list]

# --- 玩家任務相關 API ---

class AcceptTaskRequest(BaseModel):
    task_id: str # This is TaskDefinition.task_id (UUID string)

@player_task_router.post("/", response_model=PlayerTask, status_code=status.HTTP_201_CREATED)
async def accept_task(
    request_body: AcceptTaskRequest = Body(...),
    current_user: User = Depends(get_current_user)
):
    """
    允許玩家接受一個任務。
    如果任務定義了 `pickup_items`，會將這些道具添加到玩家的倉庫中。
    """
    if db_provider.task_definitions_collection is None or \
       db_provider.player_tasks_collection is None or \
       db_provider.player_warehouse_items_collection is None:
        raise HTTPException(status_code=503, detail="資料庫服務未初始化")

    task_definition_uuid_to_accept = request_body.task_id

    task_def_doc = await db_provider.task_definitions_collection.find_one({
        "task_id": task_definition_uuid_to_accept,
        "is_active": True
    })
    if not task_def_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任務不存在或不可用")

    task_def_model = TaskDefinition(**task_def_doc)

    now = datetime.now()
    if (task_def_model.availability_start_date and task_def_model.availability_start_date > now) or \
       (task_def_model.availability_end_date and task_def_model.availability_end_date < now):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="任務不在可用時間範圍內")

    if current_user.level < task_def_model.requirements.required_player_level:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"需要等級 {task_def_model.requirements.required_player_level} 才能接受此任務")

    existing_player_task = await db_provider.player_tasks_collection.find_one({
        "user_id": current_user.user_id, # Changed from player_id
        "task_id": task_definition_uuid_to_accept, 
        "status": {"$in": ["accepted", "in_progress_linked_to_session"]}
    })
    if existing_player_task:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任務已被接受且未完成")

    if not task_def_model.is_repeatable:
        completed_task = await db_provider.player_tasks_collection.find_one({
            "user_id": current_user.user_id, # Changed from player_id
            "task_id": task_definition_uuid_to_accept,
            "status": "completed"
        })
        if completed_task:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="此任務不可重複且已完成")

    # --- Add pickup items to warehouse ---
    if task_def_model.pickup_items:
        for item_to_pickup in task_def_model.pickup_items:
            await db_provider.player_warehouse_items_collection.update_one(
                {"user_id": current_user.user_id, "item_id": item_to_pickup.item_id},
                {
                    "$inc": {"quantity": item_to_pickup.quantity},
                    "$setOnInsert": {
                        "player_warehouse_item_id": str(uuid.uuid4()),
                        "user_id": current_user.user_id,
                        "item_id": item_to_pickup.item_id,
                    },
                    "$set": {"last_updated_at": datetime.now()}
                },
                upsert=True
            )

    # Check for an existing "abandoned" task for this user and task_definition to reuse
    abandoned_task_to_reuse = await db_provider.player_tasks_collection.find_one({
        "user_id": current_user.user_id,
        "task_id": task_definition_uuid_to_accept,
        "status": "abandoned"
    })

    if abandoned_task_to_reuse:
        # If an abandoned task exists, reuse it by updating its status and relevant fields.
        # This applies to both repeatable and non-repeatable (if not yet completed).
        update_fields = {
            "status": "accepted",
            "accepted_at": datetime.now(),
            "last_updated_at": datetime.now(),
            "progress": {},  # Reset progress
            "linked_game_session_id": None,
            "completed_at": None,
            "failed_at": None
            # "abandoned_at": None # Removed from $set to avoid conflict with $unset
        }
        await db_provider.player_tasks_collection.update_one(
            {"_id": abandoned_task_to_reuse["_id"]},
            {"$set": update_fields, "$unset": {"abandoned_at": ""}} # $unset will remove the field
        )
        reused_task_doc = await db_provider.player_tasks_collection.find_one({"_id": abandoned_task_to_reuse["_id"]})
        if not reused_task_doc: # Should not happen
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="重用已放棄任務時出錯")
        return PlayerTask(**reused_task_doc)
    
    # If no abandoned task to reuse (or if specific logic prevented reuse), create a new PlayerTask record.
    new_player_task_instance = PlayerTask(
        user_id=current_user.user_id, 
        task_id=task_definition_uuid_to_accept, 
        status="accepted",
        accepted_at=datetime.now(),
        last_updated_at=datetime.now(),
        progress={} 
    )
    new_player_task_data = new_player_task_instance.dict(by_alias=True, exclude_none=True)
    
    insert_result = await db_provider.player_tasks_collection.insert_one(new_player_task_data)
    created_task_doc = await db_provider.player_tasks_collection.find_one({"_id": insert_result.inserted_id})
    
    if not created_task_doc: 
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="接受新任務失敗，無法讀取已創建的記錄")
        
    return PlayerTask(**created_task_doc)


@player_task_router.delete("/{player_task_uuid}", status_code=status.HTTP_200_OK)
async def abandon_task(
    player_task_uuid: str = Path(..., description="要放棄的玩家任務的 player_task_id (UUID)"),
    current_user: User = Depends(get_current_user)
):
    """
    允許玩家放棄一個任務。
    如果任務在接受時給予了 `pickup_items`，這些道具將從玩家倉庫中移除。
    """
    if db_provider.player_tasks_collection is None or \
       db_provider.task_definitions_collection is None or \
       db_provider.player_warehouse_items_collection is None:
        raise HTTPException(status_code=503, detail="資料庫服務未初始化")

    try:
        uuid.UUID(player_task_uuid)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="無效的玩家任務 ID 格式")

    player_task_doc = await db_provider.player_tasks_collection.find_one({
        "player_task_id": player_task_uuid,
        "user_id": current_user.user_id
    })

    if not player_task_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的玩家任務記錄")

    if player_task_doc["status"] not in ["accepted", "in_progress_linked_to_session"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"任務狀態為 {player_task_doc['status']}，無法放棄")

    # --- Remove pickup items from warehouse ---
    task_def_doc = await db_provider.task_definitions_collection.find_one({"task_id": player_task_doc["task_id"]})
    if task_def_doc:
        task_def_model = TaskDefinition(**task_def_doc)
        if task_def_model.pickup_items:
            for item_to_remove in task_def_model.pickup_items:
                # Decrease the quantity. This might result in a negative quantity if the player used the item,
                # which could be a valid state (e.g., player owes the item).
                # The logic here simply removes the quantity that was given.
                await db_provider.player_warehouse_items_collection.update_one(
                    {"user_id": current_user.user_id, "item_id": item_to_remove.item_id},
                    {"$inc": {"quantity": -item_to_remove.quantity}}
                )
                # Optional: Add logic here to delete the warehouse item if quantity <= 0

    # Mark the task as abandoned
    update_result = await db_provider.player_tasks_collection.update_one(
        {"player_task_id": player_task_uuid, "user_id": current_user.user_id},
        {"$set": {"status": "abandoned", "abandoned_at": datetime.now(), "last_updated_at": datetime.now()}}
    )

    if update_result.modified_count == 0:
        # This could happen if the document was modified between the find and update, but it's unlikely here.
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="放棄任務失敗 (可能已被修改或不存在)")

    return {"message": "任務已成功放棄"}


@player_task_router.get("/", response_model=List[PlayerTask])
async def list_player_accepted_tasks(
    status_filter: Optional[str] = None, 
    current_user: User = Depends(get_current_user)
):
    if db_provider.player_tasks_collection is None:
        raise HTTPException(status_code=503, detail="資料庫服務未初始化")

    query: Dict[str, Any] = {"user_id": current_user.user_id} # Changed from player_id
    if status_filter:
        if status_filter not in ["accepted", "in_progress_linked_to_session", "completed", "failed", "abandoned"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="無效的狀態篩選器")
        query["status"] = status_filter
    
    player_tasks_cursor = db_provider.player_tasks_collection.find(query)
    player_tasks_list = await player_tasks_cursor.to_list(length=None)
    
    return [PlayerTask(**pt) for pt in player_tasks_list]
