from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from bson import ObjectId
from pydantic_core import core_schema

# --- PyObjectId Helper Type (Pydantic V2 compatible) ---
class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type, handler):
        """Pydantic v2 compatible schema generation"""
        return core_schema.with_info_before_validator_function(
            cls.validate,
            core_schema.any_schema(),
            serialization=core_schema.to_string_ser_schema()
        )

    @classmethod
    def validate(cls, v, info=None):
        """Pydantic V2 signature with info parameter"""
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str) and ObjectId.is_valid(v):
            return ObjectId(v)
        raise ValueError(f"Not a valid ObjectId: {v}")

    

# Common model configuration for Pydantic V2
COMMON_CONFIG = {
    "from_attributes": True,
    "populate_by_name": True,
    "arbitrary_types_allowed": True
}

# --- Vehicle Models ---
class VehicleDefinition(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    vehicle_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Custom unique vehicle definition ID (UUID)")
    name: str
    type: str
    description: Optional[str] = None
    max_load_weight: float
    max_load_volume: float
    base_price: Optional[int] = None
    rental_price_per_session: Optional[int] = None
    availability_type: str
    required_level_to_unlock: int = Field(default=1)
    icon_url: Optional[str] = None
    image_url: Optional[str] = None
    model_config = COMMON_CONFIG

class PlayerOwnedVehicle(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    instance_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Custom unique ID for this owned vehicle instance (UUID string)")
    user_id: uuid.UUID # Refers to User.user_id (UUID)
    vehicle_id: uuid.UUID # Foreign key to VehicleDefinition.vehicle_id (UUID)
    # Renaming nickname back to vehicle_name
    vehicle_name: Optional[str] = None # User's custom name for this vehicle
    
    # Adding fields from user's screenshot/expectation
    battery_level: int = Field(default=100)
    battery_health: int = Field(default=100)
    mileage: int = Field(default=0)
    last_recharge_mileage: Optional[int] = Field(default=0) # Or None if not charged yet
    
    purchase_date: datetime = Field(default_factory=datetime.now) # Was in model
    current_condition: float = Field(default=1.0) # Was in model
    is_in_active_session: bool = Field(default=False) # Was in model
    
    created_at: datetime = Field(default_factory=datetime.now) # From screenshot
    last_updated: datetime = Field(default_factory=datetime.now) # From screenshot

    model_config = COMMON_CONFIG

# --- Item Models ---
class ItemDefinition(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    item_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Custom unique item definition ID (UUID)")
    name: str
    # ... (rest of ItemDefinition fields)
    description: Optional[str] = None
    category: str
    weight_per_unit: float
    volume_per_unit: float
    base_value_per_unit: int
    is_fragile: bool = Field(default=False)
    is_perishable: bool = Field(default=False)
    spoil_duration_hours: Optional[int] = None
    required_permit_type: Optional[str] = None
    icon_url: Optional[str] = None
    model_config = COMMON_CONFIG

class PlayerWarehouseItem(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    player_warehouse_item_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Custom unique ID for this warehouse item instance (UUID string)")
    user_id: uuid.UUID # Changed from player_id
    item_id: uuid.UUID 
    quantity: int
    last_updated_at: datetime = Field(default_factory=datetime.now)
    model_config = COMMON_CONFIG

# --- Task Models ---
class TaskRequirementDeliverItem(BaseModel):
    item_id: uuid.UUID 
    quantity: int
    model_config = COMMON_CONFIG

class TaskRequirements(BaseModel):
    required_player_level: int = Field(default=1)
    deliver_items: Optional[List[TaskRequirementDeliverItem]] = None
    pickup_location_id: Optional[uuid.UUID] = None
    destination_id: Optional[uuid.UUID] = None 
    required_vehicle_type: Optional[str] = None 
    time_limit_seconds: Optional[int] = None
    min_cargo_value: Optional[int] = None
    model_config = COMMON_CONFIG

class TaskRewardItem(BaseModel):
    item_id: uuid.UUID 
    quantity: int
    model_config = COMMON_CONFIG

class TaskRewards(BaseModel):
    experience_points: int
    currency: Optional[int] = 0
    item_rewards: Optional[List[TaskRewardItem]] = None
    unlock_vehicle_ids: Optional[List[uuid.UUID]] = None
    unlock_destination_ids: Optional[List[uuid.UUID]] = None
    model_config = COMMON_CONFIG

class TaskPickupItem(BaseModel):
    item_id: uuid.UUID
    quantity: int
    model_config = COMMON_CONFIG

class TaskDefinition(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    task_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Custom unique task definition ID (UUID)")
    title: str
    # ... (rest of TaskDefinition fields)
    description: str
    mode: str
    requirements: TaskRequirements
    rewards: TaskRewards
    pickup_items: Optional[List[TaskPickupItem]] = Field(default=None, description="Items to be given to the player upon accepting the task")
    is_repeatable: bool = Field(default=False)
    repeat_cooldown_hours: Optional[int] = None
    availability_start_date: Optional[datetime] = None
    availability_end_date: Optional[datetime] = None
    prerequisite_task_ids: Optional[List[uuid.UUID]] = None
    is_active: bool = Field(default=True)
    model_config = COMMON_CONFIG

class PlayerTaskProgressItem(BaseModel):
    item_id: uuid.UUID
    delivered_quantity: int
    model_config = COMMON_CONFIG

class PlayerTaskProgress(BaseModel):
    items_delivered_count: Optional[List[PlayerTaskProgressItem]] = None
    distance_traveled_for_task: Optional[float] = None
    model_config = COMMON_CONFIG

class PlayerTask(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: uuid.UUID # Changed from player_id
    task_id: uuid.UUID 
    # ... (rest of PlayerTask fields)
    status: str
    accepted_at: datetime = Field(default_factory=datetime.now)
    linked_game_session_id: Optional[str] = None 
    progress: Optional[PlayerTaskProgress] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    abandoned_at: Optional[datetime] = None
    last_updated_at: datetime = Field(default_factory=datetime.now)
    model_config = COMMON_CONFIG

# --- Destination Models ---
class GeoCoordinates(BaseModel):
    type: str = Field(default="Point")
    coordinates: List[float]
    model_config = COMMON_CONFIG

class DestinationUnlockRequirements(BaseModel):
    required_player_level: Optional[int] = None
    required_completed_task_id: Optional[uuid.UUID] = None
    model_config = COMMON_CONFIG

class Destination(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    destination_id: uuid.UUID = Field(default_factory=uuid.uuid4, description="Custom unique destination ID (UUID)")
    name: str
    # ... (rest of Destination fields)
    description: Optional[str] = None
    region: str
    coordinates: GeoCoordinates
    is_unlocked_by_default: bool = Field(default=True)
    unlock_requirements: Optional[DestinationUnlockRequirements] = None
    available_services: Optional[List[str]] = None
    icon_url: Optional[str] = None
    model_config = COMMON_CONFIG

# --- Game Session Models ---
class VehicleSnapshot(BaseModel):
    name: str
    type: str
    max_load_weight: float
    max_load_volume: float
    model_config = COMMON_CONFIG

class CargoItemSnapshot(BaseModel):
    item_id: uuid.UUID 
    name: str
    quantity: int
    weight_per_unit: float
    volume_per_unit: float
    base_value_per_unit: int
    model_config = COMMON_CONFIG

class DestinationSnapshot(BaseModel):
    name: str
    region: str
    model_config = COMMON_CONFIG

class GameSessionOutcomeSummary(BaseModel):
    distance_traveled_km: Optional[float] = None
    time_taken_seconds: Optional[int] = None
    # ... (rest of GameSessionOutcomeSummary fields)
    cargo_delivered_value: Optional[int] = None
    cargo_damage_percentage: Optional[float] = None
    earned_experience: Optional[int] = None
    earned_currency: Optional[int] = None
    penalties: Optional[int] = None
    model_config = COMMON_CONFIG

# --- Models for Game State Endpoint ---
class GameProgress(BaseModel):
    percentage: float = 0.0
    distance_traveled_km: float = 0.0
    estimated_time_left_seconds: int = 0

class VehicleStatus(BaseModel):
    current_health: float = 100.0
    battery_level: float = 100.0

class PendingEventChoice(BaseModel):
    choice_id: str
    text: str

class PendingEvent(BaseModel):
    event_id: str
    name: str
    description: str
    choices: List[PendingEventChoice]

class GameStateResponse(BaseModel):
    session_id: str
    status: str
    progress: GameProgress
    vehicle_status: VehicleStatus
    pending_event: Optional[PendingEvent] = None
 
class Effect(BaseModel):
    time_penalty_seconds: Optional[int] = 0
    health_damage: Optional[float] = 0.0
    distance_increase_km: Optional[float] = 0.0

class GameEventChoice(BaseModel):
    choice_id: str
    text: str
    base_effects: Optional[Effect] = None

class GameEvent(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    choices: List[GameEventChoice]
    trigger_conditions: Optional[Dict[str, Any]] = None
    is_active: bool = True
    model_config = COMMON_CONFIG

class PendingEvent(BaseModel):
    event_id: str
    event_name: str
    description: str
    choices: List[GameEventChoice]
    triggered_at: Optional[datetime] = None

class GameSessionProgress(BaseModel):
    total_distance_km: float = 0.0
    distance_traveled_km: float = 0.0
    start_time: datetime = Field(default_factory=datetime.now)
    last_updated_at: datetime = Field(default_factory=datetime.now)
    estimated_total_seconds: int = 0

class RealtimeVehicleStatus(BaseModel):
    current_health: float = 1.0
    battery_level: float = 100.0

class GameSession(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    game_session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Custom unique game session ID (UUID string)")
    user_id: uuid.UUID
    vehicle_snapshot: Dict[str, Any]
    destination_snapshot: Dict[str, Any]
    cargo_snapshot: List[Dict[str, Any]]
    associated_player_task_ids: Optional[List[str]] = None

    status: str
    progress: GameSessionProgress = Field(default_factory=GameSessionProgress)
    realtime_vehicle_status: RealtimeVehicleStatus = Field(default_factory=RealtimeVehicleStatus)
    pending_event: Optional[PendingEvent] = None
    active_effects: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    event_history: Optional[List[Dict[str, Any]]] = Field(default_factory=list)

    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    outcome_summary: Optional[GameSessionOutcomeSummary] = None

    last_updated_at: datetime = Field(default_factory=datetime.now)
    model_config = COMMON_CONFIG

class LoadCargoItem(BaseModel):
    item_id: uuid.UUID
    quantity: int

class LoadCargoPayload(BaseModel):
    items: List[LoadCargoItem]

# --- New Game Loop Models ---

class ChargeSessionReport(BaseModel):
    vehicle_instance_id: str
    kwh_added: float

class CheckInPayload(BaseModel):
    station_id: str
    latitude: float
    longitude: float

class GameTask(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    station_id: str
    title: str
    description: str
    reward_points: int
    required_kwh: int
    destination_station_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = True
    model_config = COMMON_CONFIG

class GameEvent(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    choices: List[str]
    model_config = COMMON_CONFIG

class ResolveEventPayload(BaseModel):
    event_id: str
    choice_id: str
    item_id: Optional[uuid.UUID] = None

class EventOutcome(BaseModel):
    time_penalty_seconds: int = 0
    distance_increase_km: float = 0.0
    item_consumed: Optional[uuid.UUID] = None
    message: str

class ResolveEventResponse(BaseModel):
    message: str
    outcome: EventOutcome
    next_state: GameStateResponse

# --- Models for Game Completion Endpoint ---
class RewardSummary(BaseModel):
    experience: int
    currency: int

class PenaltySummary(BaseModel):
    damage_penalty: int

class TotalEarnedSummary(BaseModel):
    experience: int
    currency: int

class OutcomeSummary(BaseModel):
    distance_traveled_km: float
    time_taken_seconds: int
    cargo_damage_percentage: float
    base_reward: RewardSummary
    bonus: RewardSummary
    penalties: PenaltySummary
    total_earned: TotalEarnedSummary

class PlayerUpdate(BaseModel):
    level: int
    experience: int
    currency_balance: int

class GameCompletionResponse(BaseModel):
    message: str
    outcome_summary: OutcomeSummary
    player_update: PlayerUpdate

class ShopItem(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    item_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    description: str
    price: int
    category: str
    icon_url: Optional[str] = None
    model_config = {
        **COMMON_CONFIG,
        "json_encoders": {
            uuid.UUID: lambda u: str(u)
        }
    }

class PurchasePayload(BaseModel):
    item_id: str
    quantity: int

class VehicleUpgradePayload(BaseModel):
    upgrade_type: str
