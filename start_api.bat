@echo off
echo ===== Volticar API 啟動腳本 =====
echo 直接使用Python啟動API服務 (無需Docker)

REM 設置編碼為UTF-8
chcp 65001

echo [步驟1] 安裝所需依賴...
pip install -r requirements.txt
echo 安裝email-validator...
pip install email-validator

echo [步驟2] 啟動API服務...
echo.
echo API服務將在 http://localhost:22000 運行
echo API文檔: http://localhost:22000/docs
echo.
echo 正在啟動...按 Ctrl+C 可停止服務
echo.
python -m uvicorn main:app --host 0.0.0.0 --port 22000 --reload 