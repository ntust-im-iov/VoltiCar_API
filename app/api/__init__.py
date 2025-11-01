from fastapi import APIRouter
import traceback
import sys

# 創建API路由器
api_router = APIRouter()

# 使用try-except包裝路由器導入，以捕獲任何可能的錯誤
try:
    # 嘗試導入所有路由模塊
    from app.api.user_routes import router as user_router

    api_router.include_router(user_router)
    print("✓ 用戶API路由已載入")
except Exception as e:
    print(f"✗ 載入用戶API路由時出錯: {str(e)}")
    traceback.print_exc(file=sys.stdout)

try:
    from app.api.station_routes import router as station_router

    api_router.include_router(station_router)
    print("✓ 充電站API路由已載入")
except Exception as e:
    print(f"✗ 載入充電站API路由時出錯: {str(e)}")
    traceback.print_exc(file=sys.stdout)

try:
    from app.api.parking_routes import router as parking_router

    api_router.include_router(parking_router)
    print("✓ 停車場API路由已載入")
except Exception as e:
    print(f"✗ 載入停車場API路由時出錯: {str(e)}")
    traceback.print_exc(file=sys.stdout)

try:
    from app.api.vehicle_routes import router as vehicle_router

    api_router.include_router(vehicle_router)
    print("✓ 車輛API路由已載入")
except Exception as e:
    print(f"✗ 載入車輛API路由時出錯: {str(e)}")
    traceback.print_exc(file=sys.stdout)

try:
    # Modified import for new task routers
    from app.api.task_routes import task_definition_router

    api_router.include_router(
        task_definition_router, prefix="/api/v1"
    )  # Add prefix here or in main.py
    print("✓ 任務定義API路由已載入 (task_definition_router)")
except Exception as e:
    print(f"✗ 載入任務相關API路由時出錯: {str(e)}")
    traceback.print_exc(file=sys.stdout)


try:
    from app.api.token_routes import router as token_router

    api_router.include_router(
        token_router
    )  # Assuming this router does not need /api/v1 prefix or handles it internally
    print("✓ 令牌API路由已載入")
except Exception as e:
    print(f"✗ 載入令牌API路由時出錯: {str(e)}")
    traceback.print_exc(file=sys.stdout)

try:
    from app.api.achievement_routes import router as achievement_router

    api_router.include_router(achievement_router)
    print("✓ 成就API路由已載入")
except Exception as e:
    print(f"✗ 載入成就API路由時出錯: {str(e)}")
    traceback.print_exc(file=sys.stdout)

try:
    from app.api.github_webhook_routes import router as github_webhook_router

    api_router.include_router(github_webhook_router, prefix="/github")
    print("✓ GitHub Webhook API路由已載入")
except Exception as e:
    print(f"✗ 載入 GitHub Webhook API 路由時出錯: {str(e)}")
    traceback.print_exc(file=sys.stdout)

try:
    from app.api.player_routes import router as player_router

    api_router.include_router(player_router)
    print("✓ 玩家API路由已載入")
except Exception as e:
    print(f"✗ 載入玩家API路由時出錯: {str(e)}")
    traceback.print_exc(file=sys.stdout)

try:
    from app.api.can_routes import router as can_router

    api_router.include_router(can_router)
    print("✓ CAN充電數據API路由已載入")
except Exception as e:
    print(f"✗ 載入 CAN API 路由時出錯: {str(e)}")
    traceback.print_exc(file=sys.stdout)
