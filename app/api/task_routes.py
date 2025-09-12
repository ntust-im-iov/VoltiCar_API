from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional, Any, Dict
from datetime import datetime

from app.models.game_models import TaskDefinition
from app.database import mongodb as db_provider

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
    
    return [TaskDefinition.model_validate(task, from_attributes=True) for task in tasks_list]
