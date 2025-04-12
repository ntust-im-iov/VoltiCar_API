from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any, Optional
from bson import ObjectId

from app.models.station import ChargeStation, ChargeStationCreate
from app.database.mongodb import get_charge_station_collection
from app.utils.helpers import handle_mongo_data
from app.utils.auth import get_current_user

router = APIRouter(prefix="/stations", tags=["充電站"])

# 城市名稱到 MongoDB 集合名稱的映射
CITY_MAPPING = {
    "台北市": "Taipei",
    "新北市": "NewTaipei",
    "桃園市": "Taoyuan",
    "台中市": "Taichung",
    "台南市": "Tainan",
    "高雄市": "Kaohsiung",
    "基隆市": "Keelung",
    "新竹市": "Hsinchu",
    "嘉義市": "Chiayi",
    "新竹縣": "HsinchuCounty",
    "苗栗縣": "MiaoliCounty",
    "彰化縣": "ChanghuaCounty",
    "南投縣": "NantouCounty",
    "雲林縣": "YunlinCounty",
    "嘉義縣": "ChiayiCounty",
    "屏東縣": "PingtungCounty",
    "宜蘭縣": "YilanCounty",
    "花蓮縣": "HualienCounty",
    "台東縣": "TaitungCounty",
    "金門縣": "KinmenCounty",
    "澎湖縣": "PenghuCounty",
    "連江縣": "LienchiangCounty"
}

# 獲取所有充電站
@router.get("/", response_model=List[Dict[str, Any]])
async def get_all_stations():
    try:
        # 獲取所有城市的集合名
        city_collections = get_charge_station_collection()
        
        # 從每個城市集合中獲取充電站
        all_stations = []
        for city in city_collections:
            city_collection = get_charge_station_collection(city)
            stations = list(city_collection.find())
            all_stations.extend(stations)
        
        return handle_mongo_data(all_stations)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取充電站失敗: {str(e)}"
        )

# 根據ID獲取充電站
@router.get("/{station_id}", response_model=Dict[str, Any])
async def get_station(station_id: str):
    try:
        # 獲取所有城市的集合名
        city_collections = get_charge_station_collection()
        
        # 在每個城市集合中查找匹配的station_id
        for city in city_collections:
            city_collection = get_charge_station_collection(city)
            
            # 嘗試使用StationID字段查找
            station = city_collection.find_one({"StationID": station_id})
            if station:
                return handle_mongo_data(station)
            
            # 如果未找到，嘗試使用MongoDB的_id字段查找
            if len(station_id) == 24:  # ObjectId長度為24
                try:
                    station = city_collection.find_one({"_id": ObjectId(station_id)})
                    if station:
                        return handle_mongo_data(station)
                except:
                    pass
        
        # 如果所有集合都未找到匹配的記錄
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="充電站未找到"
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"查詢失敗: {str(e)}"
        )

# 按城市查詢充電站
@router.get("/city/{city}", response_model=List[Dict[str, Any]])
async def get_stations_by_city(city: str):
    collection_name = CITY_MAPPING.get(city, city)
    print(f"查詢城市: {city}, 映射到集合: {collection_name}")

    try:
        city_collection = get_charge_station_collection(collection_name)
        if city_collection is None:
            # 如果集合不存在，直接返回 404
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到城市 '{city}' 的充電站資料"
            )

        stations = list(city_collection.find())
        print(f"在集合 {collection_name} 中找到 {len(stations)} 個充電站")

        # 即使找到的列表為空，也返回空列表而不是 404，表示該城市有記錄但目前無站點
        # if not stations:
        #     raise HTTPException(
        #         status_code=status.HTTP_404_NOT_FOUND,
        #         detail=f"城市 '{city}' 目前沒有充電站記錄"
        #     )

        return handle_mongo_data(stations)

    except HTTPException as http_exc:
        # 重新拋出已知的 HTTP 異常
        raise http_exc
    except Exception as e:
        # 捕獲其他潛在錯誤
        print(f"查詢城市 '{city}' 充電站時發生錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢充電站時發生內部錯誤"
        )

# 創建新充電站
@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_station(station: ChargeStationCreate, current_user: Dict = Depends(get_current_user)): # Added type hint for current_user
    try:
        city = station.Location.Address.City
        collection_name = CITY_MAPPING.get(city, city) # Use the constant mapping

        # 獲取對應城市的集合
        city_collection = get_charge_station_collection(collection_name)
        
        # 轉換為字典並插入
        station_dict = station.model_dump()
        result = city_collection.insert_one(station_dict)
        
        # 獲取插入後的記錄
        created_station = city_collection.find_one({"_id": result.inserted_id})
        
        # 處理ObjectId並返回
        return handle_mongo_data(created_station)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"創建充電站失敗: {str(e)}"
        )
