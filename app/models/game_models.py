from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from bson import ObjectId

# --- PyObjectId Helper Type (Pydantic V1 compatible with schema modification) ---
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v): # Pydantic V1 signature
        if isinstance(v, ObjectId):
            return v
        if ObjectId.is_valid(v):
            return ObjectId(v)
        try:
            if isinstance(v, str) and ObjectId.is_valid(v):
                return ObjectId(v)
        except TypeError:
            pass
        raise ValueError(f"Not a valid ObjectId: {v}")

    @classmethod
    def __modify_schema__(cls, field_schema: Dict[str, Any]):
        field_schema.update(type="string", example="60d5ec49e73e82f8e0e2f8b8")

# Common Config class for Pydantic V1 models
class CommonConfig:
    from_attributes = True 
    populate_by_name = True
    arbitrary_types_allowed = True
    json_encoders = {
        ObjectId: lambda o: str(o),
        PyObjectId: lambda o: str(o)
    }

# --- Vehicle Models ---
class VehicleDefinition(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    vehicle_id: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True, description="Custom unique vehicle definition ID (UUID string)")
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
    Config = CommonConfig

class PlayerOwnedVehicle(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    instance_id: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True, description="Custom unique ID for this owned vehicle instance (UUID string)")
    user_id: str # Refers to User.user_id (UUID string)
    vehicle_id: str # Foreign key to VehicleDefinition.vehicle_id (UUID string)
    # Renaming nickname back to vehicle_name
    vehicle_name: Optional[str] = None # User's custom name for this vehicle
    
    # Adding fields from user's screenshot/expectation
    battery_level: int = Field(default=100)
    battery_health: int = Field(default=100)
    mileage: int = Field(default=0)
    lastcharge_mileage: Optional[int] = Field(default=0) # Or None if not charged yet
    
    purchase_date: datetime = Field(default_factory=datetime.now) # Was in model
    current_condition: float = Field(default=1.0) # Was in model
    is_in_active_session: bool = Field(default=False) # Was in model
    
    created_at: datetime = Field(default_factory=datetime.now) # From screenshot
    last_updated: datetime = Field(default_factory=datetime.now) # From screenshot

    Config = CommonConfig

# --- Item Models ---
class ItemDefinition(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    item_id: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True, description="Custom unique item definition ID (UUID string)")
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
    Config = CommonConfig

class PlayerWarehouseItem(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    player_warehouse_item_id: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True, description="Custom unique ID for this warehouse item instance (UUID string)")
    user_id: str # Changed from player_id
    item_id: str 
    quantity: int
    last_updated_at: datetime = Field(default_factory=datetime.now)
    Config = CommonConfig

# --- Task Models ---
class TaskRequirementDeliverItem(BaseModel):
    item_id: str 
    quantity: int
    Config = CommonConfig

class TaskRequirements(BaseModel):
    required_player_level: int = Field(default=1)
    deliver_items: Optional[List[TaskRequirementDeliverItem]] = None
    pickup_location_id: Optional[str] = None 
    destination_id: Optional[str] = None 
    required_vehicle_type: Optional[str] = None 
    time_limit_seconds: Optional[int] = None
    min_cargo_value: Optional[int] = None
    Config = CommonConfig

class TaskRewardItem(BaseModel):
    item_id: str 
    quantity: int
    Config = CommonConfig

class TaskRewards(BaseModel):
    experience_points: int
    currency: Optional[int] = 0
    item_rewards: Optional[List[TaskRewardItem]] = None
    unlock_vehicle_ids: Optional[List[str]] = None 
    unlock_destination_ids: Optional[List[str]] = None
    Config = CommonConfig

class TaskPickupItem(BaseModel):
    item_id: str
    quantity: int
    Config = CommonConfig

class TaskDefinition(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True, description="Custom unique task definition ID (UUID string)")
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
    prerequisite_task_ids: Optional[List[str]] = None 
    is_active: bool = Field(default=True)
    Config = CommonConfig

class PlayerTaskProgressItem(BaseModel):
    item_id: str 
    delivered_quantity: int
    Config = CommonConfig

class PlayerTaskProgress(BaseModel):
    items_delivered_count: Optional[List[PlayerTaskProgressItem]] = None
    distance_traveled_for_task: Optional[float] = None
    Config = CommonConfig

class PlayerTask(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    player_task_id: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True, description="Custom unique ID for this player task instance (UUID string)")
    user_id: str # Changed from player_id
    task_id: str 
    # ... (rest of PlayerTask fields)
    status: str
    accepted_at: datetime = Field(default_factory=datetime.now)
    linked_game_session_id: Optional[str] = None 
    progress: Optional[PlayerTaskProgress] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    abandoned_at: Optional[datetime] = None
    last_updated_at: datetime = Field(default_factory=datetime.now)
    Config = CommonConfig

# --- Destination Models ---
class GeoCoordinates(BaseModel):
    type: str = Field(default="Point")
    coordinates: List[float]
    Config = CommonConfig

class DestinationUnlockRequirements(BaseModel):
    required_player_level: Optional[int] = None
    required_completed_task_id: Optional[str] = None 
    Config = CommonConfig

class Destination(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    destination_id: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True, description="Custom unique destination ID (UUID string)")
    name: str
    # ... (rest of Destination fields)
    description: Optional[str] = None
    region: str
    coordinates: GeoCoordinates
    is_unlocked_by_default: bool = Field(default=True)
    unlock_requirements: Optional[DestinationUnlockRequirements] = None
    available_services: Optional[List[str]] = None
    icon_url: Optional[str] = None
    Config = CommonConfig

# --- Game Session Models ---
class VehicleSnapshot(BaseModel):
    name: str
    type: str
    max_load_weight: float
    max_load_volume: float
    Config = CommonConfig

class CargoItemSnapshot(BaseModel):
    item_id: str 
    name: str
    quantity: int
    weight_per_unit: float
    volume_per_unit: float
    base_value_per_unit: int
    Config = CommonConfig

class DestinationSnapshot(BaseModel):
    name: str
    region: str
    Config = CommonConfig

class GameSessionOutcomeSummary(BaseModel):
    distance_traveled_km: Optional[float] = None
    time_taken_seconds: Optional[int] = None
    # ... (rest of GameSessionOutcomeSummary fields)
    cargo_delivered_value: Optional[int] = None
    cargo_damage_percentage: Optional[float] = None
    earned_experience: Optional[int] = None
    earned_currency: Optional[int] = None
    penalties: Optional[int] = None
    Config = CommonConfig

class GameSession(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    game_session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True, description="Custom unique game session ID (UUID string)")
    user_id: str # Changed from player_id
    used_vehicle_id: str # This should refer to PlayerOwnedVehicle.instance_id (the custom UUID)
    # ... (rest of GameSession fields)
    vehicle_snapshot: VehicleSnapshot
    cargo_snapshot: List[CargoItemSnapshot]
    total_cargo_weight_at_start: float
    total_cargo_volume_at_start: float
    destination_id: str 
    destination_snapshot: DestinationSnapshot
    associated_player_task_ids: Optional[List[str]] = None 
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    status: str
    outcome_summary: Optional[GameSessionOutcomeSummary] = None
    last_updated_at: datetime = Field(default_factory=datetime.now)
    Config = CommonConfig

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
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True)
    station_id: str
    title: str
    description: str
    reward_points: int
    required_kwh: int
    destination_station_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = True
    Config = CommonConfig

class GameEvent(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True)
    name: str
    description: str
    choices: List[str]
    Config = CommonConfig

class ResolveEventPayload(BaseModel):
    event_id: str
    choice: str
    item_id: Optional[str] = None

class ShopItem(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    item_id: str = Field(default_factory=lambda: str(uuid.uuid4()), unique=True)
    name: str
    description: str
    price: int
    category: str
    icon_url: Optional[str] = None
    Config = CommonConfig

class PurchasePayload(BaseModel):
    item_id: str
    quantity: int

class VehicleUpgradePayload(BaseModel):
    upgrade_type: str
