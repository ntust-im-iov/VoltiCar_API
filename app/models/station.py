from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# 地址模型 (重命名為 LocationAddress)
class LocationAddress(BaseModel):
    City: Optional[str] = None
    Town: Optional[str] = None
    Road: Optional[str] = None
    No: Optional[str] = None

# 連接器模型
class Connector(BaseModel):
    Type: int
    Power: int
    Quantity: int
    Description: Optional[str] = None

# 位置模型
class Location(BaseModel):
    Address: Optional[LocationAddress] = None # 更新類型引用

# 參考模型
class Reference(BaseModel):
    CarPark: Dict[str, Any]

# 充電站名稱模型
class StationName(BaseModel):
    Zh_tw: str

# 充電站完整模型
class ChargeStation(BaseModel):
    StationID: str
    StationName: StationName
    ChargingPoints: int
    ChargingRate: str
    Connectors: List[Connector]
    Floors: str
    Location: Location
    OperationType: int
    OperatorID: str
    ParkingRate: str
    PhotoURLs: List[str] = []
    PositionLat: float
    PositionLon: float
    Reference: Reference
    Telephone: str

    model_config = {
        "from_attributes": True
    }

# 充電站創建請求模型
class ChargeStationCreate(BaseModel):
    StationID: str
    StationName: Dict[str, str]
    ChargingPoints: int
    ChargingRate: str
    Connectors: List[Dict[str, Any]]
    Floors: str
    Location: Dict[str, Any]
    OperationType: int
    OperatorID: str
    ParkingRate: str
    PhotoURLs: List[str] = []
    PositionLat: float
    PositionLon: float
    Reference: Dict[str, Any]
    Telephone: str

# 充電站摘要模型 (用於列表端點) - 根據用戶反饋重命名並簡化
class StationSummary(BaseModel):
    StationID: str
    StationName: Optional[str] = None
    PositionLat: float
    PositionLon: float
    Address: Optional[LocationAddress] = Field(default=None) # 使用 LocationAddress 並採納 Field(default=None)

    model_config = {
        "from_attributes": True
    }
