from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any, Optional
from bson import ObjectId

from app.models.station import ChargeStation, ChargeStationCreate
from app.database.mongodb import get_charge_station_collection
from app.utils.helpers import handle_mongo_data
from app.utils.auth import get_current_user

router = APIRouter(prefix="/stations", tags=["充电站"])

# 获取所有充电站
@router.get("/", response_model=List[Dict[str, Any]])
async def get_all_stations():
    try:
        # 获取所有城市的集合名
        city_collections = get_charge_station_collection()
        
        # 从每个城市集合中获取充电站
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

# 根据ID获取充电站
@router.get("/{station_id}", response_model=Dict[str, Any])
async def get_station(station_id: str):
    try:
        # 获取所有城市的集合名
        city_collections = get_charge_station_collection()
        
        # 在每个城市集合中查找匹配的station_id
        for city in city_collections:
            city_collection = get_charge_station_collection(city)
            
            # 尝试使用StationID字段查找
            station = city_collection.find_one({"StationID": station_id})
            if station:
                return handle_mongo_data(station)
            
            # 如果未找到，尝试使用MongoDB的_id字段查找
            if len(station_id) == 24:  # ObjectId长度为24
                try:
                    station = city_collection.find_one({"_id": ObjectId(station_id)})
                    if station:
                        return handle_mongo_data(station)
                except:
                    pass
        
        # 如果所有集合都未找到匹配的记录
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

# 按城市查询充电站
@router.get("/city/{city}", response_model=List[Dict[str, Any]])
async def get_stations_by_city(city: str):
    try:
        # 转换城市名为集合名格式，这里假设集合名与city参数同名
        # 如果需要映射，可以添加映射字典
        city_mapping = {
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
        
        collection_name = city_mapping.get(city, city)
        print(f"查詢城市: {city}, 映射到集合: {collection_name}")
        
        # 获取该城市的集合
        try:
            city_collection = get_charge_station_collection(collection_name)
            if city_collection is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"查詢失敗: 404: 未找到{city}的充電站集合"
                )
                
            stations = list(city_collection.find())
            print(f"找到{len(stations)}個充電站")
            
            if not stations:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"查詢失敗: 404: 未找到{city}的充電站"
                )
            
            return handle_mongo_data(stations)
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            print(f"查詢城市充電站時出錯: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"查詢失敗: 404: 未找到{city}的充電站"
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"處理查詢城市充電站請求時出錯: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"查詢失敗: {str(e)}"
        )

# 创建新充电站
@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_station(station: ChargeStationCreate, current_user=Depends(get_current_user)):
    try:
        # 获取城市信息
        city = station.Location.Address.City
        city_mapping = {
            "台北市": "Taipei",
            "新北市": "NewTaipei",
            # 更多映射...
        }
        collection_name = city_mapping.get(city, city)
        
        # 获取对应城市的集合
        city_collection = get_charge_station_collection(collection_name)
        
        # 转换为字典并插入
        station_dict = station.model_dump()
        result = city_collection.insert_one(station_dict)
        
        # 获取插入后的记录
        created_station = city_collection.find_one({"_id": result.inserted_id})
        
        # 处理ObjectId并返回
        return handle_mongo_data(created_station)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"創建充電站失敗: {str(e)}"
        ) 