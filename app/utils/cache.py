import json
import logging
from typing import Any, Optional
from fastapi import Request

logger = logging.getLogger(__name__)

async def get_redis_connection(request: Request):
    """安全地獲取 Redis 連線實例"""
    if hasattr(request.app.state, 'redis') and request.app.state.redis:
        return request.app.state.redis
    logger.warning("Redis connection not found in app state.")
    return None

async def get_cache(redis, key: str) -> Optional[Any]:
    """從 Redis 獲取快取數據"""
    if not redis:
        return None
    try:
        cached_data = await redis.get(key)
        if cached_data:
            logger.info(f"Cache HIT for key: {key}")
            return json.loads(cached_data)
        logger.info(f"Cache MISS for key: {key}")
        return None
    except Exception as e:
        logger.error(f"Error getting cache for key {key}: {e}")
        return None

async def set_cache(redis, key: str, data: Any, expire: int = 300): # 預設快取 5 分鐘
    """將數據設置到 Redis 快取"""
    if not redis:
        return
    try:
        await redis.set(key, json.dumps(data), ex=expire)
        logger.info(f"Cache SET for key: {key}, expire in {expire}s")
    except Exception as e:
        logger.error(f"Error setting cache for key {key}: {e}")

def create_cache_key(prefix: str, **kwargs) -> str:
    """
    根據前綴和參數創建一個標準化的快取鍵。
    例如: prefix="stations_city", city="Taipei", skip=0, limit=10
    會產生 "stations_city:city=Taipei&limit=10&skip=0" (參數按字母順序排列)
    """
    sorted_params = "&".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    return f"{prefix}:{sorted_params}"
