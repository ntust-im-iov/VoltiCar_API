@echo off
echo ===== Volticar API 重啟腳本 =====

REM 設置編碼為UTF-8
chcp 65001

echo [步驟1] 安裝缺少的依賴...
pip install -r requirements.txt
pip install email-validator

echo [步驟2] 更新requirements.txt...
REM 確保email-validator在requirements.txt中
findstr "email-validator" requirements.txt > nul
if errorlevel 1 (
    echo email-validator^>=2.0.0 >> requirements.txt
    echo 已添加email-validator到requirements.txt
) else (
    echo requirements.txt已包含email-validator
)

echo [步驟3] 停止現有Docker容器...
docker-compose down

echo [步驟4] 重新構建Docker映像...
docker-compose build --no-cache

echo [步驟5] 重新啟動服務...
docker-compose up -d

echo [步驟6] 檢查服務狀態...
timeout /t 5 > nul
docker-compose ps

echo.
echo ===== 完成 =====
echo API服務現在應該在 http://localhost:22000 運行
echo 可通過 http://localhost:22000/docs 訪問API文檔

REM 等待用戶按任意鍵結束
pause 