from fastapi import APIRouter, HTTPException, status, Depends, Request
from typing import List, Dict, Any, Optional
from bson import ObjectId
import logging
from main import limiter  # 從 main.py 匯入 limiter
from app.utils.cache import get_redis_connection, get_cache, set_cache, create_cache_key
from app.models.parking import (
    ParkingSpace,
    ParkingSpaceCreate,
    ParkingSummary,
    CarParkPosition,
)
from app.database import mongodb as db_provider  # Import the module itself
from app.utils.helpers import handle_mongo_data
from app.utils.auth import get_current_user

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("volticar-parking-api")

router = APIRouter(prefix="/parkings", tags=["停車場"])

# 城市名稱到 MongoDB 集合名稱的映射 (重用相同的城市映射)
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


# 按城市查詢停車場
@router.get("/city/{city}", response_model=List[ParkingSummary], summary="依城市查詢停車場")
@limiter.limit("10/minute")
async def get_parkings_by_city(
    request: Request, city: str, skip: int = 0, limit: int = 100
):
    """
    根據指定的城市名稱，分頁獲取該城市的停車場摘要列表。
    - **city**: 城市名稱 (例如, "台北市")。
    - **skip**: 跳過的記錄數，用於分頁。
    - **limit**: 每頁返回的最大記錄數。
    - 此端點有速率限制，並使用快取以提高效能。
    """
    redis = await get_redis_connection(request)
    cache_key_params = {"city": city, "skip": skip, "limit": limit}
    cache_key = create_cache_key("parkings_by_city", **cache_key_params)

    if redis:
        cached_data = await get_cache(redis, cache_key)
        if cached_data is not None:
            # 假設 cached_data 是 dict 列表，轉換為 ParkingSummary
            return [ParkingSummary.model_validate(p, from_attributes=True) for p in cached_data]

    collection_name = CITY_MAPPING.get(city, city)
    logger.info(
        f"查詢城市: {city}, 映射到集合: {collection_name}, 分頁: skip={skip}, limit={limit}"
    )
    logger.info(f"停車場資訊加載中...")

    try:
        if db_provider.parking_data is None:
            raise HTTPException(status_code=503, detail="停車場資料庫服務未初始化")

        if collection_name not in CITY_COLLECTIONS and collection_name not in list(
            CITY_MAPPING.values()
        ):
            all_collection_names = await db_provider.get_parking_collection()
            matching_cities = [
                c for c in all_collection_names if collection_name.lower() in c.lower()
            ]
            if matching_cities:
                logger.info(
                    f"未找到確切城市 {collection_name}，使用相近城市 {matching_cities[0]}"
                )
                collection_name = matching_cities[0]
            # else: 如果沒有匹配的，後面的 city_collection 會是 None

        city_collection = await db_provider.get_parking_collection(collection_name)
        if city_collection is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到城市 '{city}' 的停車場資料 (集合: {collection_name})",
            )

        parkings_cursor = city_collection.find().skip(skip).limit(limit)
        parkings_list = await parkings_cursor.to_list(length=limit)
        logger.info(
            f"在集合 {collection_name} 中找到 {len(parkings_list)} 個停車場 (分頁 skip={skip}, limit={limit})"
        )

        raw_parkings = handle_mongo_data(parkings_list)

        response_data = []
        for parking_data in raw_parkings:
            # 處理停車場名稱資料 (從 CarParkName.Zh_tw 提取)
            parking_name_data = parking_data.get("CarParkName")
            parking_name_str = None
            if isinstance(parking_name_data, dict):
                parking_name_str = parking_name_data.get("Zh_tw")
            elif isinstance(parking_name_data, str):
                parking_name_str = parking_name_data

            # 處理地址數據，兼容字典和純字串格式
            address_raw = parking_data.get("Address")
            address_input_for_summary = None
            if isinstance(address_raw, dict):
                address_input_for_summary = address_raw
            elif isinstance(address_raw, str):
                # 如果是純字串，將其包裝成 LocationAddress 期望的字典格式
                # 假設純字串地址對應到 Road 欄位
                address_input_for_summary = {"Road": address_raw}

            summary = ParkingSummary(
                CarParkID=parking_data.get("CarParkID"),
                CarParkName=parking_name_str,
                Address=address_input_for_summary,
                PositionLat=parking_data.get("CarParkPosition", {}).get("PositionLat"),
                PositionLon=parking_data.get("CarParkPosition", {}).get("PositionLon"),
                FareDescription=parking_data.get("FareDescription"),
            )
            response_data.append(summary)

        logger.info(f"停車場資訊加載完成並轉換為簡化摘要模型")

        if redis:
            await set_cache(
                redis, cache_key, [p.model_dump(by_alias=True, exclude_none=True) for p in response_data], expire=3600
            )

        return response_data

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"查詢城市 '{city}' 停車場時發生錯誤: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢停車場時發生內部錯誤",
        )


# 根據ID獲取停車場
@router.get("/id/{parking_id}", response_model=Dict[str, Any], summary="依ID獲取單一停車場的詳細資訊")
@limiter.limit("30/minute")
async def get_parking(request: Request, parking_id: str):
    """
    根據停車場的唯一 `CarParkID` 或資料庫 `_id`，獲取其完整的詳細資訊。
    - **parking_id**: 停車場的 ID。
    - 系統會先在優化的 `AllParkingSpaces` 集合中搜尋，如果找不到，會遍歷所有城市集合進行查找。
    """
    logger.info(f"查詢停車場ID: {parking_id}")
    logger.info(f"停車場資訊加載中...")

    try:
        if db_provider.parking_data is None:
            raise HTTPException(status_code=503, detail="停車場資料庫服務未初始化")

        optimized_collection = db_provider.parking_data["AllParkingSpaces"]

        search_query = {}
        is_object_id = False
        if len(parking_id) == 24:  # Basic check for ObjectId string length
            try:
                ObjectId(parking_id)  # Validate if it's a valid ObjectId
                is_object_id = True
            except Exception:  # Catch any exception from ObjectId validation
                pass  # is_object_id remains False

        if is_object_id:
            search_query = {"_id": ObjectId(parking_id)}
        else:
            search_query = {"CarParkID": parking_id}

        parking = await optimized_collection.find_one(search_query)

        if parking:
            parking_data = handle_mongo_data(parking)
            logger.info(f"在 AllParkingSpaces 集合找到停車場 {parking_id}")
            logger.info(f"停車場資訊加載完成")
            return parking_data

        logger.info(f"在 AllParkingSpaces 未找到 {parking_id}，嘗試遍歷城市集合...")
        # Ensure get_parking_collection without args returns all names
        city_collection_names = await db_provider.get_parking_collection()

        for city_name_iter in city_collection_names:
            if city_name_iter == "AllParkingSpaces":
                continue
            try:
                city_collection_iter = await db_provider.get_parking_collection(
                    city_name_iter
                )
                if city_collection_iter is None:
                    continue

                parking_in_city = await city_collection_iter.find_one(search_query)

                if parking_in_city:
                    parking_data = handle_mongo_data(parking_in_city)
                    parking_data["city_collection"] = city_name_iter
                    logger.info(f"在 {city_name_iter} 找到停車場 {parking_id}")
                    logger.info(f"停車場資訊加載完成")
                    return parking_data
            except Exception as e_city_search:
                logger.error(
                    f"在城市 {city_name_iter} 中搜索停車場 {parking_id} 時出錯: {e_city_search}",
                    exc_info=True,
                )

        logger.warning(f"在所有集合中都找不到停車場 ID: {parking_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="停車場未找到"
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"查詢停車場 {parking_id} 時發生錯誤: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查詢失敗: {str(e)}",
        )


# 獲取所有停車場 (優化地圖概覽)
@router.get("/overview", response_model=List[ParkingSummary], summary="獲取地圖概覽的停車場摘要")
@limiter.limit("10/minute")
async def get_all_parkings_overview(
    request: Request,
    min_lat: Optional[float] = None,
    min_lon: Optional[float] = None,
    max_lat: Optional[float] = None,
    max_lon: Optional[float] = None,
    skip: int = 0,
    limit: int = 1000,
):
    """
    為地圖視圖優化設計的端點，高效獲取停車場的摘要資訊。
    - **min_lat, min_lon, max_lat, max_lon**: (可選) 提供一個地理邊界框，只返回此區域內的停車場。必須同時提供四個參數。
    - **skip, limit**: 用於分頁。
    - 如果不提供地理邊界框，將返回所有停車場的摘要資訊 (有分頁限制)。
    - 此端點有速率限制，並使用快取以提高效能。
    """
    redis = await get_redis_connection(request)
    cache_key_params = {
        "min_lat": min_lat,
        "min_lon": min_lon,
        "max_lat": max_lat,
        "max_lon": max_lon,
        "skip": skip,
        "limit": limit,
    }
    # Filter out None values before creating cache key
    cache_key_params = {k: v for k, v in cache_key_params.items() if v is not None}
    cache_key = create_cache_key("parkings_overview", **cache_key_params)

    if redis:
        cached_data = await get_cache(redis, cache_key)
        if cached_data is not None:
            return [ParkingSummary.model_validate(p, from_attributes=True) for p in cached_data]

    try:
        query = {}
        log_message_parts = [
            f"全局地圖停車場概覽資訊加載中 (分頁 skip={skip}, limit={limit})"
        ]

        if all(v is not None for v in [min_lat, min_lon, max_lat, max_lon]):
            log_message_parts = [
                f"地圖停車場概覽資訊加載中，邊界框: ({min_lon},{min_lat}) 至 ({max_lon},{max_lat})",
                f"分頁: skip={skip}, limit={limit}",
            ]
            query = {
                "CarParkPosition.PositionLat": {"$gte": min_lat, "$lte": max_lat},
                "CarParkPosition.PositionLon": {"$gte": min_lon, "$lte": max_lon},
            }
        elif any(v is not None for v in [min_lat, min_lon, max_lat, max_lon]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="請提供完整的地理邊界框參數 (min_lat, min_lon, max_lat, max_lon) 或不提供任何地理參數以獲取所有停車場 (將套用預設分頁)。",
            )

        logger.info(", ".join(log_message_parts))

        if db_provider.parking_data is None:
            logger.error("parking_data 未初始化。")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="停車場資料庫服務暫時無法使用",
            )

        optimized_collection = db_provider.parking_data["AllParkingSpaces"]
        # Projection to optimize query
        projection = {
            "_id": 0,
            "CarParkID": 1,
            "CarParkName": 1,
            "Address": 1,
            "CarParkPosition": 1,
            "FareDescription": 1,
        }

        parkings_cursor = (
            optimized_collection.find(query, projection).skip(skip).limit(limit)
        )
        raw_overview_list = await parkings_cursor.to_list(length=limit)

        response_data = []
        for parking_data in raw_overview_list:
            # 處理停車場名稱資料 (從 CarParkName.Zh_tw 提取)
            parking_name_data = parking_data.get("CarParkName")
            parking_name_str = None
            if isinstance(parking_name_data, dict):
                parking_name_str = parking_name_data.get("Zh_tw")
            elif isinstance(parking_name_data, str):
                parking_name_str = parking_name_data

            # 處理地址數據，兼容字典和純字串格式
            address_raw = parking_data.get("Address")
            address_input_for_summary = None
            if isinstance(address_raw, dict):
                address_input_for_summary = address_raw
            elif isinstance(address_raw, str):
                # 如果是純字串，將其包裝成 LocationAddress 期望的字典格式
                # 假設純字串地址對應到 Road 欄位
                address_input_for_summary = {"Road": address_raw}

            summary = ParkingSummary(
                CarParkID=parking_data.get("CarParkID"),
                CarParkName=parking_name_str,
                Address=address_input_for_summary,
                PositionLat=parking_data.get("CarParkPosition", {}).get("PositionLat"),
                PositionLon=parking_data.get("CarParkPosition", {}).get("PositionLon"),
                FareDescription=parking_data.get("FareDescription"),
            )
            response_data.append(summary)

        count = len(response_data)
        logger.info(
            f"從 AllParkingSpaces 集合獲取了 {count} 個停車場的概覽資訊並轉換為簡化摘要 (分頁 skip={skip}, limit={limit})。"
        )

        if redis:
            await set_cache(
                redis, cache_key, [p.model_dump(by_alias=True, exclude_none=True) for p in response_data], expire=3600
            )

        return response_data

    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"獲取全局停車場概覽時發生錯誤: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取停車場概覽失敗: {str(e)}",
        )


# 創建新停車場
@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
async def create_parking(
    request: Request,
    parking: ParkingSpaceCreate,
    current_user: Dict = Depends(get_current_user),
):
    try:
        address = parking.Address  # This is Dict[str, Any] in ParkingSpaceCreate
        if address and not isinstance(address, dict):
            raise ValueError("Address must be a dictionary.")

        city = None
        if address:
            city = address.get("City")  # City within Address

        if not city:
            raise ValueError("City is required in Address.")

        collection_name = CITY_MAPPING.get(city, city)  # Use city for mapping

        if db_provider.parking_data is None:
            raise HTTPException(status_code=503, detail="停車場資料庫服務未初始化")

        city_collection = await db_provider.get_parking_collection(collection_name)
        if city_collection is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到城市 '{city}' 的停車場集合以創建新停車場 (集合: {collection_name})",
            )

        parking_dict = parking.model_dump()
        result = await city_collection.insert_one(parking_dict)

        created_parking = await city_collection.find_one({"_id": result.inserted_id})

        return handle_mongo_data(created_parking)
    except ValueError as ve:
        logger.error(f"創建停車場時發生數值錯誤: {str(ve)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(ve)
        )
    except HTTPException as http_exc:
        raise http_exc
    except Exception as e:
        logger.error(f"創建停車場時發生錯誤: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"創建停車場失敗: {str(e)}"
        )
