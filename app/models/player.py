from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from uuid import UUID, uuid4

class PlayerWarehouseItem(BaseModel):
    item_id: UUID
    quantity: int

class PlayerTask(BaseModel):
    player_task_uuid: UUID = Field(default_factory=uuid4)
    task_id: UUID
    status: str  # e.g., "accepted", "completed", "abandoned"
    progress: Optional[Dict] = None

class GameSession(BaseModel):
    vehicle_id: Optional[UUID] = None
    destination_id: Optional[UUID] = None
    cargo: List[PlayerWarehouseItem] = []
    active: bool = False

class Player(BaseModel):
    user_id: UUID = Field(...)
    display_name: str
    level: int = 1
    experience: int = 0
    currency: int = 0
    game_session: GameSession = Field(default_factory=GameSession)
    active_game_session_id: Optional[UUID] = None  # 目前進行中的遊戲會話ID，遊戲開始時設為 game_session_id，結束時清空
    
    class Config:
        collection = "Player"
