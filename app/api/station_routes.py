from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any, Optional
from bson import ObjectId
import logging

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
            if db_provider.charge_station_db is None:
                raise HTTPException(status_code=503, detail="充電站資料庫服務未初始化")
            all_collection_names = await db_provider.get_charge_station_collection() # await
            matching_cities = [
                c for c in all_collection_names if collection_name.lower() in c.lower()
            ]
            if matching_cities:
                logger.info(
                    f"未找到確切城市 {collection_name}，使用相近城市 {matching_cities[0]}"
                )
                collection_name = matching_cities[0]

        # 通過 mongodb.py 獲取城市集合
        if db_provider.charge_station_db is None: # Check again before specific city collection access
             raise HTTPException(status_code=503, detail="充電站資料庫服務未初始化")
        city_collection = await db_provider.get_charge_station_collection(collection_name) # await
        if city_collection is None:
            # 如果集合不存在，直接返回 404
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到城市 '{city}' 的充電站資料",
            )

        # 使用獲取的集合進行查詢
        stations_cursor = city_collection.find() # find returns a cursor
        stations = await stations_cursor.to_list(length=None) # await and to_list, length=None to get all
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
        if db_provider.charge_station_db is None:
            raise HTTPException(status_code=503, detail="充電站資料庫服務未初始化")
        # 通過 mongodb.py 獲取所有城市的集合名
        city_collection_names = await db_provider.get_charge_station_collection() # await

        # 在每個城市集合中查找匹配的station_id
        for city_name in city_collection_names:
            try:
                # 通過 mongodb.py 獲取特定城市的集合
                if db_provider.charge_station_db is None: # Check again
                    raise HTTPException(status_code=503, detail="充電站資料庫服務未初始化")
                city_collection = await db_provider.get_charge_station_collection(city_name) # await
                if city_collection is None:
                    continue

                # 嘗試使用StationID字段查找
                station = await city_collection.find_one({"StationID": station_id}) # await
                if station:
                    station = handle_mongo_data(station)
                    station["city_collection"] = city_name
                    logger.info(f"在 {city_name} 找到充電站 {station_id}")
                    logger.info(f"充電站資訊加載完成")
                    return station

                # 如果未找到，嘗試使用MongoDB的_id字段查找
                if len(station_id) == 24:  # ObjectId長度為24
                    try:
                        station = await city_collection.find_one( # await
                            {"_id": ObjectId(station_id)}
                        )
                        if station:
                            station = handle_mongo_data(station)
                            station["city_collection"] = city_name
                            logger.info(
                                f"在 {city_name} 找到充電站 {station_id} (使用ObjectId)"
                            )
                            logger.info(f"充電站資訊加載完成")
                            return station
                    except: # NOSONAR
                        pass
            except Exception as e:
                logger.error(f"在城市 {city_name} 中搜索站點 {station_id} 時出錯: {e}")

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


# 獲取所有充電站 (優化地圖概覽)
@router.get("/", response_model=List[Dict[str, Any]])
async def get_all_stations_overview():
    """
    高效獲取所有充電站的最小化信息，用於地圖概覽。
    從名為 'AllChargingStations' 的優化集合中查詢。
    """
    try:
        logger.info("全局地圖充電站概覽資訊加載中...")
        
        # 假設優化的單一集合名稱為 "AllChargingStations"
        # 這個集合應該在 charge_station_db 資料庫中
        # 您需要手動創建此集合並將所有城市的充電站數據合併進去
        # 並為 Location.Coordinates 創建 2dsphere 索引
        
        # 從 app.database.mongodb 獲取 charge_station_db
        from app.database.mongodb import charge_station_db
        if charge_station_db is None:
            logger.error("charge_station_db 未初始化。")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="充電站資料庫服務暫時無法使用"
            )

        optimized_collection = charge_station_db["AllChargingStations"]

        # 定義投影，只選擇必要的欄位
        # 根據您提供的圖片更新欄位名稱
        projection = {
            "_id": 0, 
            "StationID": 1,
            "PositionLat": 1, # 更新緯度欄位
            "PositionLon": 1, # 更新經度欄位
            # "Status": 1, # 暫時移除，因為圖片中沒有直接對應的單一狀態欄位
            "Connectors": 1, # 包含 Connectors 陣列，客戶端可從中提取插頭類型
            "ChargingPoints": 1, # 可以考慮加入充電點數量作為狀態參考
            "Spaces": 1 # 或者可用車位數量
        }

        stations_cursor = optimized_collection.find({}, projection)
        all_stations_overview = await stations_cursor.to_list(length=None) # 獲取所有文檔
        
        count = len(all_stations_overview)
        logger.info(f"從 AllChargingStations 集合獲取了 {count} 個充電站的概覽資訊。")

        # 由於投影已經處理了 ObjectId，這裡可能不需要 handle_mongo_data
        # 但如果 StationID 本身是 ObjectId，或者其他欄位需要轉換，則保留
        # 為了安全起見，暫時保留，但理想情況下投影後的數據應該是乾淨的
        
        # 直接返回列表，因為我們期望的是一個列表
        return all_stations_overview

    except Exception as e:
        logger.error(f"獲取全局充電站概覽時發生錯誤: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"獲取充電站概覽失敗: {str(e)}",
        )


# 創建新充電站
@router.post("/", response_model=Dict[str, Any], status_code=status.HTTP_201_CREATED)
async def create_station(
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
