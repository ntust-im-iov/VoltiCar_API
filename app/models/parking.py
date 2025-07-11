from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

# 重用 station.py 中的地址模型
from .station import LocationAddress


# 停車場名稱模型 (類似 StationName)
class CarParkName(BaseModel):
    Zh_tw: str


# 停車場位置模型
class CarParkPosition(BaseModel):
    PositionLat: Optional[float] = None
    PositionLon: Optional[float] = None


# 停車場完整模型
class ParkingSpace(BaseModel):
    CarParkID: str
    CarParkName: CarParkName
    Address: Optional[LocationAddress] = None
    CarParkPosition: Optional["CarParkPosition"] = None
    FareDescription: Optional[str] = None

    model_config = {"from_attributes": True}


# 停車場創建請求模型
class ParkingSpaceCreate(BaseModel):
    CarParkID: str
    CarParkName: Dict[str, str]  # 接受 {"Zh_tw": "停車場名稱"} 格式
    Address: Optional[Dict[str, Any]] = None
    CarParkPosition: Optional[Dict[str, Any]] = None
    FareDescription: Optional[str] = None


# 停車場摘要模型 (用於列表端點)
class ParkingSummary(BaseModel):
    CarParkID: str
    CarParkName: Optional[str] = None  # 這裡直接返回中文名稱字串
    Address: Optional[str] = None  # 修改為接受字符串格式的地址
    CarParkPosition: Optional["CarParkPosition"] = None
    FareDescription: Optional[str] = None

    model_config = {"from_attributes": True}
