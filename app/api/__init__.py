from fastapi import APIRouter
from app.api.user_routes import router as user_router
from app.api.station_routes import router as station_router
from app.api.vehicle_routes import router as vehicle_router
from app.api.task_routes import router as task_router
from app.api.token_routes import router as token_router
from app.api.achievement_routes import router as achievement_router

api_router = APIRouter()

api_router.include_router(user_router)
api_router.include_router(station_router)
api_router.include_router(vehicle_router)
api_router.include_router(task_router)
api_router.include_router(token_router)
api_router.include_router(achievement_router)