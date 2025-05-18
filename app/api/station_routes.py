from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any, Optional
from bson import ObjectId
import logging

from app.models.station import ChargeStation, ChargeStationCreate
from app.database.mongodb import get_charge_station_collection
from app.utils.helpers import handle_mongo_data
from app.utils.auth import get_current_user

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("volticar-charging-station-api")

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
    "連江縣": "LienchiangCounty",
}

# 支援的城市集合列表，從 CITY_MAPPING 取值
CITY_COLLECTIONS = list(CITY_MAPPING.values())


# 按城市查詢充電站
@router.get("/city/{city}", response_model=List[Dict[str, Any]])
async def get_stations_by_city(city: str):
    collection_name = CITY_MAPPING.get(city, city)
    logger.info(f"查詢城市: {city}, 映射到集合: {collection_name}")
    logger.info(f"充電站資訊加載中...")

    try:
        # 檢查城市名稱是否在支援列表中
        if collection_name not in CITY_COLLECTIONS and collection_name not in list(
            CITY_MAPPING.values()
        ):
            # 嘗試查找相近的城市
            matching_cities = [
                c for c in CITY_COLLECTIONS if collection_name.lower() in c.lower()
            ]
            if matching_cities:
                logger.info(
                    f"未找到確切城市 {collection_name}，使用相近城市 {matching_cities[0]}"
                )
                collection_name = matching_cities[0]

        # 通過 mongodb.py 獲取城市集合
        city_collection = get_charge_station_collection(collection_name)
        if city_collection is None:
            # 如果集合不存在，直接返回 404
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到城市 '{city}' 的充電站資料",
            )

        # 使用獲取的集合進行查詢
        stations = list(city_collection.find())
        logger.info(f"在集合 {collection_name} 中找到 {len(stations)} 個充電站")
        logger.info(f"充電站資訊加載完成")

        # 添加城市標識
        for station in stations:
            station["city_collection"] = collection_name

        return handle_mongo_data(stations)

    except HTTPException as http_exc:
        # 重新拋出已知的 HTTP 異常
        raise http_exc
    except Exception as e:
        # 捕獲其他潛在錯誤
        logger.error(f"查詢城市 '{city}' 充電站時發生錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢充電站時發生內部錯誤",
        )


# 根據ID獲取充電站
@router.get("/{station_id}", response_model=Dict[str, Any])
async def get_station(station_id: str):
    logger.info(f"查詢充電站ID: {station_id}")
    logger.info(f"充電站資訊加載中...")

    try:
        # 通過 mongodb.py 獲取所有城市的集合名
        city_collections = get_charge_station_collection()

        # 在每個城市集合中查找匹配的station_id
        for city in city_collections:
            try:
                # 通過 mongodb.py 獲取特定城市的集合
                city_collection = get_charge_station_collection(city)

                # 嘗試使用StationID字段查找
                station = city_collection.find_one({"StationID": station_id})
                if station:
                    station = handle_mongo_data(station)
                    station["city_collection"] = city
                    logger.info(f"在 {city} 找到充電站 {station_id}")
                    logger.info(f"充電站資訊加載完成")
                    return station

                # 如果未找到，嘗試使用MongoDB的_id字段查找
                if len(station_id) == 24:  # ObjectId長度為24
                    try:
                        station = city_collection.find_one(
                            {"_id": ObjectId(station_id)}
                        )
                        if station:
                            station = handle_mongo_data(station)
                            station["city_collection"] = city
                            logger.info(
                                f"在 {city} 找到充電站 {station_id} (使用ObjectId)"
                            )
                            logger.info(f"充電站資訊加載完成")
                            return station
                    except:
                        pass
            except Exception as e:
                logger.error(f"在城市 {city} 中搜索站點 {station_id} 時出錯: {e}")

        # 如果所有集合都未找到匹配的記錄
        logger.warning(f"在所有城市集合中都找不到充電站 ID: {station_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="充電站未找到"
        )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"查詢失敗: {str(e)}"
        )


# 獲取所有充電站
@router.get("/", response_model=List[Dict[str, Any]])
async def get_all_stations():
    try:
        logger.info("充電站資訊加載中...")
        # 通過 mongodb.py 獲取所有城市的集合名
        city_collections = get_charge_station_collection()

        # 從每個城市集合中獲取充電站
        all_stations = []
        total_count = 0

        # 獲取各城市的充電站並添加到列表中
        for city in city_collections:
            try:
                # 通過 mongodb.py 獲取特定城市的集合
                city_collection = get_charge_station_collection(city)

                # 獲取充電站列表
                stations = list(city_collection.find())
                count = len(stations)
                total_count += count

                # 添加城市標識
                for station in stations:
                    station["city_collection"] = city

                all_stations.extend(stations)
                logger.info(f"從 {city} 獲取了 {count} 個充電站")
            except Exception as e:
                logger.error(f"獲取 {city} 充電站時發生錯誤: {e}")

        logger.info(f"充電站資訊加載完成，總共有 {total_count} 個充電站")

        # 返回充電站列表，保持前端期望的格式
        return handle_mongo_data(all_stations)
    except Exception as e:
        logger.error(f"獲取充電站時發生錯誤: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取充電站失敗: {str(e)}",
        )


# 創建新充電站
@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_station(
    station: ChargeStationCreate, current_user: Dict = Depends(get_current_user)
):
    try:
        city = station.Location.Address.City
        collection_name = CITY_MAPPING.get(city, city)  # 使用映射關係

        # 通過 mongodb.py 獲取對應城市的集合
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
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"創建充電站失敗: {str(e)}"
        )
