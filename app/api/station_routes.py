from fastapi import APIRouter, HTTPException, status, Depends, Request
from typing import List, Dict, Any, Optional
from bson import ObjectId
import logging
from main import limiter # 從 main.py 匯入 limiter (保留)
from app.utils.cache import get_redis_connection, get_cache, set_cache, create_cache_key # (保留)
from app.models.station import ChargeStation, ChargeStationCreate, StationSummary # (保留 StationSummary)
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
    "高雄市": "Kaohsung",
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
@router.get("/city/{city}", response_model=List[StationSummary]) # 使用 StationSummary
@limiter.limit("10/minute") # 保留 limiter
async def get_stations_by_city(
    request: Request,
    city: str,
    skip: int = 0,
    limit: int = 100  # 預設每頁100筆
):
    redis = await get_redis_connection(request) # 保留 cache 邏輯
    cache_key_params = {"city": city, "skip": skip, "limit": limit}
    cache_key = create_cache_key("stations_by_city", **cache_key_params)

    if redis:
        cached_data = await get_cache(redis, cache_key)
        if cached_data is not None:
            # 假設 cached_data 是 dict 列表，轉換為 StationSummary
            return [StationSummary(**s) for s in cached_data]

    collection_name = CITY_MAPPING.get(city, city)
    logger.info(f"查詢城市: {city}, 映射到集合: {collection_name}, 分頁: skip={skip}, limit={limit}")
    logger.info(f"充電站資訊加載中...")

    try:
        if db_provider.charge_station_db is None:
            raise HTTPException(status_code=503, detail="充電站資料庫服務未初始化")
        
        # 假設 db_provider 的方法是 async
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
        
        raw_stations = handle_mongo_data(stations_list)
        
        response_data = []
        for station_data in raw_stations:
            station_name_data = station_data.get("StationName")
            station_name_str = None
            if isinstance(station_name_data, dict):
                station_name_str = station_name_data.get("Zh_tw")
            elif isinstance(station_name_data, str): 
                station_name_str = station_data.get("StationName") # 修正此處
            
            address_val_city = station_data.get("Location", {}).get("Address") if isinstance(station_data.get("Location"), dict) else None
            summary = StationSummary(
                StationID=station_data.get("StationID"),
                StationName=station_name_str,
                PositionLat=station_data.get("PositionLat"),
                PositionLon=station_data.get("PositionLon"),
                Address=address_val_city,
                # ChargingPoints is no longer in StationSummary
            )
            response_data.append(summary)
        
        logger.info(f"充電站資訊加載完成並轉換為簡化摘要模型")

        if redis: # 保留 cache 寫入
            await set_cache(redis, cache_key, [s.dict() for s in response_data]) # 存儲 dict 形式的 StationSummary
        
        return response_data

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"查詢城市 '{city}' 充電站時發生錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢充電站時發生內部錯誤",
        )

# 根據ID獲取充電站
@router.get("/id/{station_id}", response_model=Dict[str, Any]) 
@limiter.limit("30/minute") # 保留 limiter
async def get_station(request: Request, station_id: str):
    logger.info(f"查詢充電站ID: {station_id}")
    logger.info(f"充電站資訊加載中...")

    try:
        if db_provider.charge_station_db is None:
            raise HTTPException(status_code=503, detail="充電站資料庫服務未初始化")

        optimized_collection = db_provider.charge_station_db["AllChargingStations"]
        
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
            
        station = await optimized_collection.find_one(search_query) # async

        if station:
            station_data = handle_mongo_data(station)
            logger.info(f"在 AllChargingStations 集合找到充電站 {station_id}")
            logger.info(f"充電站資訊加載完成")
            return station_data

        logger.info(f"在 AllChargingStations 未找到 {station_id}，嘗試遍歷城市集合...")
        city_collection_names = await db_provider.get_charge_station_collection() # async

        for city_name_iter in city_collection_names: 
            if city_name_iter == "AllChargingStations": 
                continue
            try:
                city_collection_iter = await db_provider.get_charge_station_collection(city_name_iter) # async
                if city_collection_iter is None:
                    continue
                
                station_in_city = await city_collection_iter.find_one(search_query) # async
                
                if station_in_city:
                    station_data = handle_mongo_data(station_in_city)
                    station_data["city_collection"] = city_name_iter 
                    logger.info(f"在 {city_name_iter} 找到充電站 {station_id}")
                    logger.info(f"充電站資訊加載完成")
                    return station_data
            except Exception as e:
                logger.error(f"在城市 {city_name_iter} 中搜索站點 {station_id} 時出錯: {e}")

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
@router.get("/overview", response_model=List[StationSummary]) 
@limiter.limit("10/minute") # 保留 limiter
async def get_all_stations_overview(
    request: Request,
    min_lat: Optional[float] = None,
    min_lon: Optional[float] = None,
    max_lat: Optional[float] = None,
    max_lon: Optional[float] = None,
    skip: int = 0,
    limit: int = 1000  
):
    redis = await get_redis_connection(request) # 保留 cache
    cache_key_params = {
        "min_lat": min_lat, "min_lon": min_lon, 
        "max_lat": max_lat, "max_lon": max_lon,
        "skip": skip, "limit": limit
    }
    cache_key_params = {k: v for k, v in cache_key_params.items() if v is not None}
    cache_key = create_cache_key("stations_overview", **cache_key_params)

    if redis:
        cached_data = await get_cache(redis, cache_key)
        if cached_data is not None:
            return [StationSummary(**s) for s in cached_data] # 轉換為 StationSummary
            
    try:
        query = {}
        log_message = f"全局地圖充電站概覽資訊加載中 (分頁 skip={skip}, limit={limit})..."

        if all(v is not None for v in [min_lat, min_lon, max_lat, max_lon]):
            log_message = f"地圖充電站概覽資訊加載中，邊界框: ({min_lon},{min_lat}) 至 ({max_lon},{max_lat}), 分頁: skip={skip}, limit={limit}"
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
                detail="請提供完整的地理邊界框參數 (min_lat, min_lon, max_lat, max_lon) 或不提供任何地理參數以獲取所有站點 (將套用預設分頁)。"
            )
        
        logger.info(log_message)
        
        if db_provider.charge_station_db is None:
            logger.error("charge_station_db 未初始化。")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="充電站資料庫服務暫時無法使用"
            )

        optimized_collection = db_provider.charge_station_db["AllChargingStations"]
        projection = {
            "_id": 0, "StationID": 1, "PositionLat": 1, "PositionLon": 1, "StationName.Zh_tw": 1, "Location.Address": 1,
        }

        stations_cursor = optimized_collection.find(query, projection).skip(skip).limit(limit)
        raw_overview_list = await stations_cursor.to_list(length=limit) # async
        
        response_data = []
        for station_data in raw_overview_list:
            station_name_val = station_data.get("StationName", {}).get("Zh_tw") if isinstance(station_data.get("StationName"), dict) else None
            
            station_name_val = station_data.get("StationName", {}).get("Zh_tw") if isinstance(station_data.get("StationName"), dict) else None
            
            summary_init_data = {
                "StationID": station_data.get("StationID"),
                "StationName": station_name_val,
                "PositionLat": station_data.get("PositionLat"),
                "PositionLon": station_data.get("PositionLon"),
            }
            
            address_raw_data = station_data.get("Location", {}).get("Address")
            if isinstance(address_raw_data, dict):
                summary_init_data["Address"] = address_raw_data # 如果是有效字典，則添加
            else:
                # 如果 address_raw_data 不是字典 (包括 None 或其他類型)
                # 我們不將 Address 鍵添加到 summary_init_data 中
                # 這樣 StationSummary 的 default_factory=Address 將會生效
                if address_raw_data is not None: # 僅記錄非 None 的無效數據
                    logger.warning(
                        f"StationID {station_data.get('StationID')}: "
                        f"Address data from DB is not a dict (type: {type(address_raw_data)}, value: {repr(address_raw_data)}). "
                        f"Relying on default_factory for Address in StationSummary."
                    )
            
            summary = StationSummary(**summary_init_data)
            response_data.append(summary)

        count = len(response_data)
        logger.info(f"從 AllChargingStations 集合獲取了 {count} 個充電站的概覽資訊並轉換為簡化摘要 (分頁 skip={skip}, limit={limit})。")

        if redis: # 保留 cache 寫入
            await set_cache(redis, cache_key, [s.dict() for s in response_data]) # 存儲 dict
            
        return response_data

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
@limiter.limit("30/minute") # 保留 limiter
async def create_station(
    request: Request,
    station: ChargeStationCreate, current_user: Dict = Depends(get_current_user)
):
    try:
        location = station.Location
        if not isinstance(location, dict):
            raise ValueError("Location must be a dictionary.")
        address = location.get("Address")
        if not isinstance(address, dict):
            raise ValueError("Address must be a dictionary within Location.")
        city = address.get("City")
        if not city:
            raise ValueError("City is required in Address.")

        collection_name = CITY_MAPPING.get(city, city)

        if db_provider.charge_station_db is None:
            raise HTTPException(status_code=503, detail="充電站資料庫服務未初始化")
        
        city_collection = await db_provider.get_charge_station_collection(collection_name) # async
        if city_collection is None:
             raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到城市 '{city}' 的充電站集合以創建新站點",
            )

        station_dict = station.model_dump()
        result = await city_collection.insert_one(station_dict) # async

        created_station = await city_collection.find_one({"_id": result.inserted_id}) # async

        return handle_mongo_data(created_station)
    except ValueError as ve:
        logger.error(f"創建充電站時發生數值錯誤: {str(ve)}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve)
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        if isinstance(e, HTTPException): # 保留此檢查
            raise e
        logger.error(f"創建充電站時發生錯誤: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"創建充電站失敗: {str(e)}"
        )
