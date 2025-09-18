from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional, Any, Dict
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId

from app.models.game_models import TaskDefinition
from app.database import mongodb as db_provider

from app.utils.auth import get_current_user
from app.models.user import User as UserModel
from app.models.game_models import PlayerTask, TaskDefinition, PlayerWarehouseItem

class TaskCompletionRequest(BaseModel):
    player_task_id: str

task_definition_router = APIRouter(prefix="/tasks", tags=["任務定義 (Game Tasks Definitions)"])

@task_definition_router.get("/", response_model=List[TaskDefinition], summary="列出所有可用的任務定義")
async def list_available_tasks(
    mode: Optional[str] = None,
):
    """
    獲取當前所有處於活躍狀態且在可用時間範圍內的任務定義列表。
    - `mode`: (可選) 根據遊戲模式篩選任務，例如 "cargo_transport"。
    """
    if db_provider.task_definitions_collection is None: 
        raise HTTPException(status_code=503, detail="任務定義資料庫服務未初始化")

    query: Dict[str, Any] = {"is_active": True}
    if mode:
        query["mode"] = mode
    
    now = datetime.now()
    query["$or"] = [
        {"availability_start_date": {"$lte": now}, "availability_end_date": {"$gte": now}},
        {"availability_start_date": {"$lte": now}, "availability_end_date": None},
        {"availability_start_date": None, "availability_end_date": {"$gte": now}},
        {"availability_start_date": None, "availability_end_date": None}
    ]

    tasks_cursor = db_provider.task_definitions_collection.find(query)
    tasks_list = await tasks_cursor.to_list(length=None)
    
    return [TaskDefinition.model_validate(task) for task in tasks_list]


@task_definition_router.post("/complete", summary="完成一項玩家任務")
async def complete_task(
    completion_request: TaskCompletionRequest,
    current_user: UserModel = Depends(get_current_user)
):
    """
    標記一個玩家任務為完成狀態，並分發獎勵。

    - **player_task_id**: 玩家任務的唯一識別碼。
    """
    if not db_provider.player_tasks_collection or not db_provider.task_definitions_collection or not db_provider.players_collection:
        raise HTTPException(status_code=503, detail="一個或多個資料庫服務未初始化")

    # 1. 查找玩家任務
    player_task = await db_provider.player_tasks_collection.find_one({
        "user_id": current_user.user_id,
        "_id": ObjectId(completion_request.player_task_id) # Assuming player_task_id is the MongoDB _id
    })

    if not player_task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到指定的玩家任務")

    player_task_obj = PlayerTask.model_validate(player_task)

    # 2. 驗證任務狀態
    if player_task_obj.status != "accepted":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"任務狀態為 {player_task_obj.status}，無法完成。")

    # 3. 查找任務定義以獲取獎勵
    task_definition = await db_provider.task_definitions_collection.find_one({"task_id": player_task_obj.task_id})
    if not task_definition:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="找不到相關的任務定義")
    
    task_def_obj = TaskDefinition.model_validate(task_definition)

    # 4. 更新任務狀態
    update_result = await db_provider.player_tasks_collection.update_one(
        {"_id": player_task_obj.id},
        {"$set": {"status": "completed", "completed_at": datetime.now()}}
    )

    if update_result.modified_count == 0:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="無法更新任務狀態")

    # 5. 分發獎勵
    rewards = task_def_obj.rewards
    player_update = {"$inc": {}}
    
    if rewards.experience_points > 0:
        player_update["$inc"]["experience"] = rewards.experience_points
    if rewards.currency > 0:
        player_update["$inc"]["currency"] = rewards.currency # Assuming a 'currency' field on the player model

    # 更新玩家經驗和貨幣
    if player_update["$inc"]:
        await db_provider.players_collection.update_one(
            {"user_id": current_user.user_id},
            player_update
        )

    # 處理物品獎勵
    if rewards.item_rewards:
        for item_reward in rewards.item_rewards:
            # Update or insert item in player's warehouse
            # The collection has two unique indexes: ('player_id', 'item_id') and ('user_id', 'item_id').
            # To satisfy both during an upsert, we must provide both fields.
            # We'll use the authenticated user's ID for both.
            # With the problematic index removed, we only need to query by user_id and item_id.
            await db_provider.player_warehouse_items_collection.update_one(
                {"user_id": current_user.user_id, "item_id": item_reward.item_id},
                {"$inc": {"quantity": item_reward.quantity}},
                upsert=True
            )
            
    # Here you could add logic to handle level-ups based on new experience.

    return {"message": "任務成功完成", "player_task_id": completion_request.player_task_id}
