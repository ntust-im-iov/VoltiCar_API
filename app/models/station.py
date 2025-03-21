from pydantic import BaseModel
from typing import List, Dict, Any, Optional

# 地址模型
class Address(BaseModel):
    City: str
    Town: str
    Road: str
    No: str

# 连接器模型
class Connector(BaseModel):
    Type: int
    Power: int
    Quantity: int
    Description: str

# 位置模型
class Location(BaseModel):
    Address: Address

# 参考模型
class Reference(BaseModel):
    CarPark: Dict[str, Any]

# 充电站名称模型
class StationName(BaseModel):
    Zh_tw: str

# 充电站完整模型
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
    PhotoURLs: List = []
    PositionLat: float
    PositionLon: float
    Reference: Reference
    Telephone: str

    model_config = {
        "from_attributes": True
    }

# 充电站创建请求模型
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
    PhotoURLs: List = []
    PositionLat: float
    PositionLon: float
    Reference: Dict[str, Any]
    Telephone: str