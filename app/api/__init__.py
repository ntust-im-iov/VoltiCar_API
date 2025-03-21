from fastapi import APIRouter
from app.api.user_routes import router as user_router
from app.api.station_routes import router as station_router

api_router = APIRouter()

api_router.include_router(user_router)
api_router.include_router(station_router) 