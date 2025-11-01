"""
CAN Log 解析與充電數據 API
處理充電監控、減碳量計算、點數轉換等功能
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, AsyncGenerator
import cantools
import asyncio
import json
import os
from pathlib import Path

from app.utils.auth import get_current_user
from app.models.user import User
from app.database.mongodb import get_db

router = APIRouter(prefix="/api/can", tags=["CAN充電數據"])

# 配置 CAN 數據檔案路徑
# 支援多種檔案位置：
# 1. 環境變數 CAN_DATA_DIR (建議在 Docker Compose 中設定並 mount)
# 2. 專案根目錄下的 can_data/ 資料夾
# 3. 工作目錄下的 can_data/
# 4. 常見的本機路徑 C:/tesla 或 /tesla
def find_can_data_dir():
    """找到 CAN 資料目錄"""
    env_dir = os.getenv("CAN_DATA_DIR")
    candidates = []
    if env_dir:
        candidates.append(Path(env_dir))
    # 推上層到專案根 (app/api -> project root)
    try:
        project_root = Path(__file__).resolve().parents[2]  # app/api -> app -> root
        candidates.append(project_root / "can_data")
    except Exception:
        pass
    candidates.append(Path.cwd() / "can_data")
    candidates.append(Path("/app/can_data"))  # Docker 容器內的路徑
    candidates.append(Path("C:/tesla"))
    candidates.append(Path("/tesla"))

    for d in candidates:
        if d and d.exists():
            dbc = d / "tesla.dbc"
            if dbc.exists():
                return d, dbc
    
    # 都沒找到，回傳第一個 candidate 的路徑作為預設
    first = candidates[0] if candidates else Path(".")
    return first, first / "tesla.dbc"


# 檢查並決定要使用的資料目錄
CAN_DATA_DIR, DBC_FILE_PATH = find_can_data_dir()

# 可用的 LOG 檔案列表
AVAILABLE_LOG_FILES = {
    "charge": "Model3Log2019-01-13LowTempDriveCharge.asc",
    "supercharge": "Model3Log2019-01-19supercharge.asc", 
    "supercharge_end": "Model3Log2019-01-19superchargeend.asc",
}


def get_log_file_path(log_name: str = "charge") -> Path:
    """
    根據名稱取得 LOG 檔案路徑
    
    Args:
        log_name: LOG 檔案名稱 (charge, supercharge, supercharge_end)
    
    Returns:
        LOG 檔案的完整路徑
    """
    filename = AVAILABLE_LOG_FILES.get(log_name, AVAILABLE_LOG_FILES["charge"])
    return CAN_DATA_DIR / filename

# 減碳係數設定
CARBON_FACTOR_KG_PER_KWH = 0.494  # 每 kWh 減碳 0.494 kg
CARBON_TO_POINTS_RATE = 10.0  # 每公斤減碳轉換為 10 點數


# ==================== Request/Response Models ====================

class SaveCarbonReductionRequest(BaseModel):
    """儲存減碳量的請求"""
    total_kwh: float = Field(..., gt=0, description="充電總電量 (kWh)")


class SaveCarbonPointsRequest(BaseModel):
    """儲存減碳點數的請求"""
    carbon_kg: float = Field(..., gt=0, description="減碳量 (公斤)")


class CarbonReductionResponse(BaseModel):
    """減碳量響應"""
    total_carbon_reduction_kg: float = Field(..., description="累計減碳量 (公斤)")


class CarbonPointsResponse(BaseModel):
    """減碳點數響應"""
    carbon_reward_points: float = Field(..., description="累計減碳點數")


# ==================== Helper Functions ====================

def parse_charge_status(state_value) -> str:
    """
    解析 PCS_chgMainState 的充電狀態
    根據 Tesla Model 3 的實際狀態碼進行映射
    state_value 可能是字串（枚舉值）或整數
    """
    # 如果是字串枚舉值
    if isinstance(state_value, str):
        status_map = {
            'PCS_CHG_STATE_IDLE': "待機中",
            'PCS_CHG_STATE_CHARGING': "充電中",
            'PCS_CHG_STATE_DONE': "充電完成",
            'PCS_CHG_STATE_PAUSED': "充電暫停",
            'PCS_CHG_STATE_ERROR': "充電錯誤",
            'PCS_CHG_STATE_READY': "充電準備中",
        }
        return status_map.get(state_value, f"未知狀態 ({state_value})")
    
    # 如果是整數
    status_map = {
        0: "待機中",
        1: "充電中",
        2: "充電完成",
        3: "充電暫停",
        4: "充電錯誤",
        5: "充電準備中",
    }
    return status_map.get(state_value, f"未知狀態 ({state_value})")


async def generate_charge_monitor_stream(
    log_name: str = "charge", 
    skip_idle: bool = True,
    max_duration: float = None
) -> AsyncGenerator[str, None]:
    """
    非同步產生器：逐行讀取 CAN log 並流式傳輸充電狀態
    
    Args:
        log_name: LOG 檔案名稱 (charge, supercharge, supercharge_end)
        skip_idle: 是否跳過初始的待機階段（IDLE），直接從充電開始讀取
        max_duration: 最大處理時長(秒)，None表示處理完整個LOG檔案
    """
    try:
        # 取得指定的 LOG 檔案路徑
        log_file_path = get_log_file_path(log_name)
        
        # 檢查檔案是否存在
        if not DBC_FILE_PATH.exists():
            yield f"data: {json.dumps({'error': f'DBC 檔案不存在: {DBC_FILE_PATH}'}, ensure_ascii=False)}\n\n"
            return
        
        if not log_file_path.exists():
            available = list(AVAILABLE_LOG_FILES.keys())
            yield f"data: {json.dumps({'error': f'LOG 檔案不存在: {log_file_path}', 'available_logs': available}, ensure_ascii=False)}\n\n"
            return

        # 載入 DBC 檔案
        db = cantools.database.load_file(str(DBC_FILE_PATH))
        
        # 初始化追蹤變數 - 0x204 充電狀態
        current_status = "初始化中"
        instant_ac_power = 0.0  # PCS_chgInstantAcPowerAvailable (即時AC功率 kW)
        
        # 0x292 SOC 資料
        soc_ui = 0.0  # SOCUI292 (儀表板顯示 %)
        soc_min = 0.0  # SOCmin292 (最低模組 %)
        soc_max = 0.0  # SOCmax292 (最高模組 %)
        initial_soc = None
        
        # 0x352 電池能量狀態
        initial_kwh = None
        final_kwh = None
        energy_to_charge_complete = 0.0  # BMS_energyToChargeComplete (充滿所需 kWh)
        
        message_count = 0
        skipped_lines = 0
        is_charging = False  # 是否已進入充電狀態
        last_energy_to_charge_complete = None
        log_start_time = None  # LOG 開始時間戳
        duration_exceeded = False  # 是否超過時間限制
        
        # 開啟並讀取 log 檔案
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as log_file:
            for line in log_file:
                message_count += 1
                
                try:
                    # 跳過註釋和標題行
                    if line.startswith('//') or line.startswith('date') or line.startswith('base') or line.startswith('internal'):
                        continue
                    
                    # 解析 .asc 格式 (Vector CANalyzer/CANoe)
                    # 範例: 0.00503 1  545  Rx   d 8 14 00 3F F0 AB BF CA C1
                    parts = line.strip().split()
                    if len(parts) < 7:
                        continue
                    
                    # 提取時間戳並檢查是否超過時間限制
                    try:
                        current_timestamp = float(parts[0])
                        if log_start_time is None:
                            log_start_time = current_timestamp
                        
                        # 檢查是否超過時間限制
                        if max_duration is not None:
                            elapsed_time = current_timestamp - log_start_time
                            if elapsed_time > max_duration:
                                duration_exceeded = True
                                break
                    except (ValueError, IndexError):
                        pass
                    
                    # 檢查是否為有效的 CAN 訊息行 (包含 'Rx' 或 'Tx' 和 'd')
                    if 'Rx' not in parts and 'Tx' not in parts:
                        continue
                    if 'd' not in parts:
                        continue
                    
                    # 提取 CAN ID (第3個欄位，十六進制)
                    try:
                        can_id_hex = parts[2]
                        can_id = int(can_id_hex, 16)
                    except (ValueError, IndexError):
                        continue
                    
                    # 找到 'd' 之後的數據長度和數據
                    try:
                        d_index = parts.index('d')
                        if d_index + 1 >= len(parts):
                            continue
                        data_len = int(parts[d_index + 1])
                        
                        # 提取數據字節 (從 d_index + 2 開始)
                        data_start = d_index + 2
                        data_hex_list = parts[data_start:data_start + data_len]
                        
                        if len(data_hex_list) < data_len:
                            continue
                        
                        # 將十六進制字串轉換為 bytes
                        can_data_hex = ''.join(data_hex_list)
                        can_data = bytes.fromhex(can_data_hex)
                    except (ValueError, IndexError):
                        continue
                    
                    # 嘗試解碼訊息
                    try:
                        message = db.get_message_by_frame_id(can_id)
                        decoded = message.decode(can_data)
                        
                        # 處理不同的 CAN ID
                        if can_id == 0x204:  # 充電狀態 (10Hz)
                            # PCS_chgMainState: 充電主狀態
                            if 'PCS_chgMainState' in decoded:
                                state_value = decoded['PCS_chgMainState']
                                state_str = str(state_value)
                                current_status = parse_charge_status(state_value)

                                # 如果 state 明確為充電相關狀態，視為充電開始
                                if not is_charging and (state_str == 'PCS_CHG_STATE_CHARGING' or state_str == 'PCS_CHG_STATE_READY' or state_str == 'PCS_CHG_STATE_ENABLE'):
                                    is_charging = True

                            # PCS_chgInstantAcPowerAvailable: 即時AC功率 (kW)
                            if 'PCS_chgInstantAcPowerAvailable' in decoded:
                                try:
                                    instant_ac_power = float(decoded['PCS_chgInstantAcPowerAvailable'])
                                except Exception:
                                    instant_ac_power = 0.0
                                # 若偵測到即時功率 > 0，視為正在充電
                                if instant_ac_power > 0 and not is_charging:
                                    is_charging = True

                        elif can_id == 0x292:  # SOC 百分比 (10Hz)
                            # SOCUI292: 儀表板顯示的電量百分比
                            if 'SOCUI292' in decoded:
                                soc_ui = float(decoded['SOCUI292'])
                                if initial_soc is None and is_charging:
                                    initial_soc = soc_ui
                            
                            # SOCmin292 / SOCmax292: 電池模組最低/最高 SOC
                            if 'SOCmin292' in decoded:
                                soc_min = float(decoded['SOCmin292'])
                            if 'SOCmax292' in decoded:
                                soc_max = float(decoded['SOCmax292'])

                        elif can_id == 0x352:  # 電池能量狀態 (1Hz)
                            # BMS_energyToChargeComplete: 充滿所需能量 (kWh)
                            if 'BMS_energyToChargeComplete' in decoded:
                                try:
                                    energy_to_charge_complete = float(decoded['BMS_energyToChargeComplete'])
                                except Exception:
                                    energy_to_charge_complete = 0.0
                                # 若之前有記錄且現在減少，視為正在充電
                                if last_energy_to_charge_complete is not None:
                                    if energy_to_charge_complete < last_energy_to_charge_complete and not is_charging:
                                        is_charging = True
                                last_energy_to_charge_complete = energy_to_charge_complete

                            # BMS_nominalEnergyRemaining: 剩餘能量 (kWh)
                            if 'BMS_nominalEnergyRemaining' in decoded:
                                try:
                                    energy_kwh = float(decoded['BMS_nominalEnergyRemaining'])
                                except Exception:
                                    energy_kwh = None

                                # 只處理合理範圍的數據 (10-120 kWh),過濾異常值
                                if energy_kwh is not None and 10 <= energy_kwh <= 120:
                                    # 只在進入充電狀態後記錄初始值
                                    if initial_kwh is None and (not skip_idle or is_charging):
                                        initial_kwh = energy_kwh
                                    # 追蹤最大值而非最後一筆,避免LOG結尾異常數據(如12.4kWh)
                                    if final_kwh is None or energy_kwh > final_kwh:
                                        final_kwh = energy_kwh
                    
                    except (KeyError, ValueError) as e:
                        # 此 CAN ID 不在 DBC 中定義或解碼失敗，跳過
                        pass
                    
                    # 如果啟用 skip_idle 且尚未進入充電狀態，跳過此行不計數
                    if skip_idle and not is_charging:
                        skipped_lines += 1
                        continue
                    
                    # 每處理 1000 條訊息,流式傳輸一次狀態 (降低頻率以提升效能)
                    if message_count % 1000 == 0:
                        # 使用有序字典確保 JSON 輸出順序一致
                        from collections import OrderedDict
                        data = OrderedDict([
                            ("status", current_status),
                            # 0x204 充電狀態
                            ("instant_ac_power_kw", round(instant_ac_power, 2)),
                            # 0x292 SOC 資料
                            ("soc_ui_percent", round(soc_ui, 2)),
                            ("soc_min_percent", round(soc_min, 2)),
                            ("soc_max_percent", round(soc_max, 2)),
                            # 0x352 電池能量
                            ("initial_kwh", round(initial_kwh, 2) if initial_kwh else 0),
                            ("current_kwh", round(final_kwh, 2) if final_kwh else 0),
                            ("energy_to_charge_complete_kwh", round(energy_to_charge_complete, 2)),
                            # 處理統計
                            ("messages_processed", message_count),
                        ])
                        
                        # 如果有跳過閒置期的行數,加入資訊
                        if skip_idle and skipped_lines > 0:
                            data["skipped_idle_lines"] = skipped_lines
                            if is_charging:
                                data["charging_started"] = True
                        
                        yield f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
                        await asyncio.sleep(0.01)  # 避免過載
                
                except Exception as parse_error:
                    # 單行解析錯誤，記錄但繼續處理
                    continue
        
        # 計算充電總量
        if initial_kwh is not None and final_kwh is not None:
            total_kwh_charged = final_kwh - initial_kwh
        else:
            total_kwh_charged = 0.0
        
        # 計算減碳量與點數
        carbon_reduction_kg = total_kwh_charged * 0.494  # kWh × 0.494 kg CO₂/kWh
        reward_points = carbon_reduction_kg * 10  # kg CO₂ × 10 點
        
        # 傳送最終結果
        from collections import OrderedDict
        final_data = OrderedDict([
            ("status", "finished"),
            ("log_file", log_name),
            # 充電資料
            ("initial_kwh", round(initial_kwh, 2) if initial_kwh else 0),
            ("final_kwh", round(final_kwh, 2) if final_kwh else 0),
            ("total_kwh_charged", round(total_kwh_charged, 2)),
            # SOC 資料
            ("initial_soc_percent", round(initial_soc, 2) if initial_soc else 0.0),
            ("final_soc_ui_percent", round(soc_ui, 2)),
            ("final_soc_min_percent", round(soc_min, 2)),
            ("final_soc_max_percent", round(soc_max, 2)),
            ("battery_balance_percent", round(soc_max - soc_min, 2)),  # 電池均衡度
            # 減碳與點數
            ("carbon_reduction_kg", round(carbon_reduction_kg, 2)),
            ("reward_points", round(reward_points, 2)),
            # 統計
            ("total_messages", message_count),
        ])
        
        # 如果跳過了閒置期,加入相關資訊
        if skip_idle:
            final_data["skip_idle_enabled"] = True
            final_data["skipped_idle_lines"] = skipped_lines
        
        # 如果有時間限制且已超過,加入資訊
        if max_duration is not None:
            final_data["duration_limit_seconds"] = max_duration
            final_data["duration_exceeded"] = duration_exceeded
            if log_start_time is not None:
                actual_duration = (current_timestamp if 'current_timestamp' in locals() else 0) - log_start_time
                final_data["actual_duration_seconds"] = round(actual_duration, 2)
        
        yield f"data: {json.dumps(final_data, ensure_ascii=False)}\n\n"
    
    except Exception as e:
        error_data = {
            "error": f"充電監控發生錯誤: {str(e)}",
            "status": "error"
        }
        yield f"data: {json.dumps(error_data)}\n\n"


# ==================== API Endpoints ====================

@router.get(
    "/charge-monitor",
    summary="充電監控 (流式傳輸)",
    description="即時監控充電狀態，使用 Server-Sent Events (SSE) 流式傳輸數據。可透過 log 參數選擇不同的充電記錄檔案。",
    response_class=StreamingResponse,
)
async def charge_monitor(
    log: str = "charge",
    skip_idle: bool = True,
    duration: float = None
):
    """
    流式傳輸充電監控數據
    
    參數:
    - log: LOG 檔案名稱，可選值:
      - "charge" (預設): Model3Log2019-01-13LowTempDriveCharge.asc - 低溫充電記錄
      - "supercharge": Model3Log2019-01-19supercharge.asc - 超充記錄
      - "supercharge_end": Model3Log2019-01-19superchargeend.asc - 超充結束記錄
    - skip_idle: 是否跳過初始的待機階段 (預設: true)，設為 false 可查看完整記錄
    - duration: 處理時長限制(秒)，None表示處理完整LOG。例如 duration=300 表示只處理前5分鐘
    
    前端接收範例:
    ```javascript
    // 使用預設 log
    const eventSource = new EventSource('/api/can/charge-monitor');
    
    // 或選擇特定 log
    const eventSource = new EventSource('/api/can/charge-monitor?log=supercharge');
    
    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        console.log(data);
        
        if (data.status === 'finished') {
            const totalKwh = data.total_kwh_charged;
            // 呼叫儲存減碳量 API
            eventSource.close();
        }
    };
    ```
    """
    # 驗證 log 參數
    if log not in AVAILABLE_LOG_FILES:
        available = list(AVAILABLE_LOG_FILES.keys())
        return StreamingResponse(
            iter([f"data: {json.dumps({'error': f'無效的 log 參數: {log}', 'available_logs': available}, ensure_ascii=False)}\n\n"]),
            media_type="text/event-stream",
        )
    
    return StreamingResponse(
        generate_charge_monitor_stream(log, skip_idle, duration),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 Nginx 緩衝
        }
    )


@router.post(
    "/carbon-reduction/save",
    response_model=CarbonReductionResponse,
    summary="儲存減碳量",
    description="接收充電電量，計算並累加減碳量到用戶帳戶",
)
async def save_carbon_reduction(
    request: SaveCarbonReductionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    儲存減碳量
    
    - 接收前端傳來的 total_kwh
    - 計算減碳量 (kg) = total_kwh × 0.494
    - 累加到用戶的 total_carbon_reduction_kg
    """
    try:
        # 計算減碳量
        carbon_kg = request.total_kwh * CARBON_FACTOR_KG_PER_KWH
        
        # 更新資料庫
        db = await get_db()
        users_collection = db["Users"]
        
        result = await users_collection.update_one(
            {"user_id": str(current_user.user_id)},
            {"$inc": {"total_carbon_reduction_kg": carbon_kg}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新減碳量失敗"
            )
        
        # 讀取更新後的值
        updated_user = await users_collection.find_one({"user_id": str(current_user.user_id)})
        new_total = updated_user.get("total_carbon_reduction_kg", 0.0)
        
        return CarbonReductionResponse(total_carbon_reduction_kg=new_total)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"儲存減碳量時發生錯誤: {str(e)}"
        )


@router.get(
    "/carbon-reduction",
    response_model=CarbonReductionResponse,
    summary="讀取累計減碳量",
    description="取得當前用戶的累計減碳量",
)
async def get_carbon_reduction(current_user: User = Depends(get_current_user)):
    """
    讀取用戶的累計減碳量
    """
    return CarbonReductionResponse(
        total_carbon_reduction_kg=current_user.total_carbon_reduction_kg
    )


@router.post(
    "/carbon-points/save",
    response_model=CarbonPointsResponse,
    summary="儲存減碳點數",
    description="接收減碳量，轉換為點數並累加到用戶帳戶",
)
async def save_carbon_points(
    request: SaveCarbonPointsRequest,
    current_user: User = Depends(get_current_user)
):
    """
    儲存減碳點數
    
    - 接收減碳量 (kg)
    - 計算點數 = carbon_kg × 轉換係數 (預設 10.0)
    - 累加到用戶的 carbon_reward_points
    """
    try:
        # 計算點數
        points_earned = request.carbon_kg * CARBON_TO_POINTS_RATE
        
        # 更新資料庫
        db = await get_db()
        users_collection = db["Users"]
        
        result = await users_collection.update_one(
            {"user_id": str(current_user.user_id)},
            {"$inc": {"carbon_reward_points": points_earned}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="更新減碳點數失敗"
            )
        
        # 讀取更新後的值
        updated_user = await users_collection.find_one({"user_id": str(current_user.user_id)})
        new_total = updated_user.get("carbon_reward_points", 0.0)
        
        return CarbonPointsResponse(carbon_reward_points=new_total)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"儲存減碳點數時發生錯誤: {str(e)}"
        )


@router.get(
    "/carbon-points",
    response_model=CarbonPointsResponse,
    summary="讀取累計減碳點數",
    description="取得當前用戶的累計減碳點數",
)
async def get_carbon_points(current_user: User = Depends(get_current_user)):
    """
    讀取用戶的累計減碳點數
    """
    return CarbonPointsResponse(
        carbon_reward_points=current_user.carbon_reward_points
    )


@router.get(
    "/config",
    summary="取得 CAN 設定資訊",
    description="取得當前 CAN 數據檔案的配置資訊和係數設定",
)
async def get_can_config():
    """
    取得 CAN 設定資訊（不需登入）
    """
    # 檢查所有 LOG 檔案的存在狀態
    log_files_status = {}
    for key, filename in AVAILABLE_LOG_FILES.items():
        filepath = CAN_DATA_DIR / filename
        log_files_status[key] = {
            "filename": filename,
            "path": str(filepath),
            "exists": filepath.exists(),
        }
    
    return {
        "dbc_file": str(DBC_FILE_PATH),
        "dbc_exists": DBC_FILE_PATH.exists(),
        "can_data_dir": str(CAN_DATA_DIR),
        "available_logs": log_files_status,
        "carbon_factor_kg_per_kwh": CARBON_FACTOR_KG_PER_KWH,
        "carbon_to_points_rate": CARBON_TO_POINTS_RATE,
    }
