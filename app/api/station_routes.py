from fastapi import APIRouter, HTTPException, status, Depends, Request
from typing import List, Dict, Any, Optional
from bson import ObjectId
import logging
from main import limiter # 從 main.py 匯入 limiter
from app.utils.cache import get_redis_connection, get_cache, set_cache, create_cache_key

from app.models.station import ChargeStation, ChargeStationCreate
# from app.database.mongodb import get_charge_station_collection # Will be accessed via db_provider
from app.database import mongodb as db_provider # Import the module itself
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
@limiter.limit("10/minute")
async def get_stations_by_city(
    request: Request, 
    city: str,
    skip: int = 0,
    limit: int = 100  # 預設每頁100筆
):
    redis = await get_redis_connection(request)
    cache_key_params = {"city": city, "skip": skip, "limit": limit}
    cache_key = create_cache_key("stations_by_city", **cache_key_params)

    if redis:
        cached_stations = await get_cache(redis, cache_key)
        if cached_stations is not None:
            return cached_stations

    collection_name = CITY_MAPPING.get(city, city)
    logger.info(f"查詢城市: {city}, 映射到集合: {collection_name}, 分頁: skip={skip}, limit={limit}")
    logger.info(f"充電站資訊加載中...")

    try:
        if db_provider.charge_station_db is None:
            raise HTTPException(status_code=503, detail="充電站資料庫服務未初始化")
        
        # 檢查城市名稱是否在支援列表中 (這部分邏輯可以考慮是否也快取城市列表)
        if collection_name not in CITY_COLLECTIONS and collection_name not in list(
            CITY_MAPPING.values()
        ):
            all_collection_names = await db_provider.get_charge_station_collection()
            matching_cities = [
                c for c in all_collection_names if collection_name.lower() in c.lower()
            ]
            if matching_cities:
                logger.info(
                    f"未找到確切城市 {collection_name}，使用相近城市 {matching_cities[0]}"
                )
                collection_name = matching_cities[0]

        city_collection = await db_provider.get_charge_station_collection(collection_name)
        if city_collection is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到城市 '{city}' 的充電站資料",
            )

        stations_cursor = city_collection.find().skip(skip).limit(limit)
        stations_list = await stations_cursor.to_list(length=limit)
        logger.info(f"在集合 {collection_name} 中找到 {len(stations_list)} 個充電站 (分頁 skip={skip}, limit={limit})")
        
        processed_stations = handle_mongo_data(stations_list)
        # 添加城市標識
        for station_data in processed_stations:
            station_data["city_collection"] = collection_name
        
        logger.info(f"充電站資訊加載完成")

        if redis:
            await set_cache(redis, cache_key, processed_stations)
        
        return processed_stations

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"查詢城市 '{city}' 充電站時發生錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢充電站時發生內部錯誤",
        )


# 根據ID獲取充電站
@router.get("/id/{station_id}", response_model=Dict[str, Any]) # 將路徑改為 /id/{station_id} 以避免衝突
@limiter.limit("30/minute")
async def get_station(request: Request, station_id: str):
    logger.info(f"查詢充電站ID: {station_id}")
    logger.info(f"充電站資訊加載中...")

    try:
        if db_provider.charge_station_db is None:
            raise HTTPException(status_code=503, detail="充電站資料庫服務未初始化")

        # 優先從 AllChargingStations 集合查詢
        optimized_collection = db_provider.charge_station_db["AllChargingStations"]
        # 假設 AllChargingStations 集合中的 StationID 是唯一的，並且已索引
        # 或者如果 station_id 是 MongoDB ObjectId，則按 _id 查詢
        
        search_query = {}
        is_object_id = False
        if len(station_id) == 24:
            try:
                ObjectId(station_id)
                is_object_id = True
            except:
                pass
        
        if is_object_id:
            search_query = {"_id": ObjectId(station_id)}
        else:
            search_query = {"StationID": station_id}
            
        station = await optimized_collection.find_one(search_query)

        if station:
            station_data = handle_mongo_data(station)
            # 注意：從 AllChargingStations 返回的數據可能沒有 city_collection 欄位
            # 如果需要，可能要額外邏輯來確定或標記來源
            logger.info(f"在 AllChargingStations 集合找到充電站 {station_id}")
            logger.info(f"充電站資訊加載完成")
            return station_data

        # 如果在 AllChargingStations 中未找到，再嘗試遍歷各城市集合 (備用邏輯)
        logger.info(f"在 AllChargingStations 未找到 {station_id}，嘗試遍歷城市集合...")
        city_collection_names = await db_provider.get_charge_station_collection() 

        for city_name in city_collection_names:
            if city_name == "AllChargingStations": # 避免重複查詢
                continue
            try:
                city_collection = await db_provider.get_charge_station_collection(city_name)
                if city_collection is None:
                    continue

                # 重新使用 search_query
                station_in_city = await city_collection.find_one(search_query)
                
                if station_in_city:
                    station_data = handle_mongo_data(station_in_city)
                    station_data["city_collection"] = city_name # 標記來源城市集合
                    logger.info(f"在 {city_name} 找到充電站 {station_id}")
                    logger.info(f"充電站資訊加載完成")
                    return station_data
            except Exception as e:
                logger.error(f"在城市 {city_name} 中搜索站點 {station_id} 時出錯: {e}")

        logger.warning(f"在所有集合中都找不到充電站 ID: {station_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="充電站未找到"
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"查詢充電站 {station_id} 時發生錯誤: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"查詢失敗: {str(e)}"
        )


# 獲取所有充電站 (優化地圖概覽)
@router.get("/overview", response_model=List[Dict[str, Any]]) # 將路徑改為 /overview
@limiter.limit("10/minute")
async def get_all_stations_overview(
    request: Request,
    min_lat: Optional[float] = None,
    min_lon: Optional[float] = None,
    max_lat: Optional[float] = None,
    max_lon: Optional[float] = None
):
    """
    高效獲取所有充電站的最小化信息，用於地圖概覽。
    可選的地理邊界框參數用於進行地理空間查詢。
    從名為 'AllChargingStations' 的優化集合中查詢。
    假設該集合中有一個名為 'location_geo' 的 GeoJSON Point 欄位，並已建立 2dsphere 索引。
    例如: location_geo: { type: "Point", coordinates: [longitude, latitude] }
    """
    redis = await get_redis_connection(request)
    cache_key_params = {
        "min_lat": min_lat, "min_lon": min_lon, 
        "max_lat": max_lat, "max_lon": max_lon
    }
    # 移除值為 None 的參數，以確保快取鍵的一致性
    cache_key_params = {k: v for k, v in cache_key_params.items() if v is not None}
    cache_key = create_cache_key("stations_overview", **cache_key_params)

    if redis:
        cached_overview = await get_cache(redis, cache_key)
        if cached_overview is not None:
            return cached_overview
            
    try:
        query = {}
        log_message = "全局地圖充電站概覽資訊加載中..."

        if all(v is not None for v in [min_lat, min_lon, max_lat, max_lon]):
            log_message = f"地圖充電站概覽資訊加載中，邊界框: ({min_lon},{min_lat}) 至 ({max_lon},{max_lat})"
            query = {
                "location_geo": {
                    "$geoWithin": {
                        "$box": [
                            [min_lon, min_lat],
                            [max_lon, max_lat]
                        ]
                    }
                }
            }
        elif any(v is not None for v in [min_lat, min_lon, max_lat, max_lon]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="請提供完整的地理邊界框參數 (min_lat, min_lon, max_lat, max_lon) 或不提供任何參數以獲取所有站點。"
            )
        
        logger.info(log_message)
        
        from app.database.mongodb import charge_station_db
        if charge_station_db is None:
            logger.error("charge_station_db 未初始化。")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="充電站資料庫服務暫時無法使用"
            )

        optimized_collection = charge_station_db["AllChargingStations"]
        projection = {
            "_id": 0, "StationID": 1, "PositionLat": 1, "PositionLon": 1,
            "Connectors": 1, "ChargingPoints": 1, "Spaces": 1,
        }

        stations_cursor = optimized_collection.find(query, projection)
        all_stations_overview_list = await stations_cursor.to_list(length=None)
        
        count = len(all_stations_overview_list)
        logger.info(f"從 AllChargingStations 集合獲取了 {count} 個充電站的概覽資訊。")

        if redis:
            await set_cache(redis, cache_key, all_stations_overview_list)
            
        return all_stations_overview_list

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"獲取全局充電站概覽時發生錯誤: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取充電站概覽失敗: {str(e)}",
        )


# 創建新充電站
@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_station(
    request: Request,
    station: ChargeStationCreate, current_user: Dict = Depends(get_current_user) # Make sure get_current_user is async if it does IO
):
    try:
        city = station.Location.Address.City
        collection_name = CITY_MAPPING.get(city, city)  # 使用映射關係

        # 通過 mongodb.py 獲取對應城市的集合
        if db_provider.charge_station_db is None:
            raise HTTPException(status_code=503, detail="充電站資料庫服務未初始化")
        city_collection = await db_provider.get_charge_station_collection(collection_name) # await
        if city_collection is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到城市 '{city}' 的充電站集合以創建新站點",
            )

        # 轉換為字典並插入
        station_dict = station.model_dump()
        result = await city_collection.insert_one(station_dict) # await

        # 獲取插入後的記錄
        created_station = await city_collection.find_one({"_id": result.inserted_id}) # await

        # 處理ObjectId並返回
        return handle_mongo_data(created_station)
    except Exception as e:
        if isinstance(e, HTTPException): # Re-raise HTTPException
            raise e
        logger.error(f"創建充電站時發生錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"創建充電站失敗: {str(e)}"
        )
