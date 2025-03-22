#!/bin/bash

# 設置顏色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}啟動Volticar電動汽車充電站API服務...${NC}"

# 檢查docker和docker-compose是否安裝
if ! command -v docker &> /dev/null; then
    echo -e "${RED}錯誤: docker未安裝，請先安裝docker${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}錯誤: docker-compose未安裝，請先安裝docker-compose${NC}"
    exit 1
fi

# 檢查環境
ENV=${1:-development}

if [ "$ENV" = "production" ]; then
    COMPOSE_FILE="docker-compose.production.yml"
    echo -e "${YELLOW}在生產環境中啟動服務...${NC}"
else
    COMPOSE_FILE="docker-compose.yml"
    echo -e "${YELLOW}在開發環境中啟動服務...${NC}"
fi

# 構建並啟動容器
echo -e "${YELLOW}構建和啟動容器...${NC}"
docker-compose -f $COMPOSE_FILE up -d --build

# 檢查容器狀態
echo -e "${YELLOW}檢查容器狀態...${NC}"
RUNNING=$(docker-compose -f $COMPOSE_FILE ps | grep "Up" | wc -l)

if [ $RUNNING -ge 1 ]; then
    echo -e "${GREEN}服務已成功啟動!${NC}"
    echo -e "${GREEN}本地訪問: http://localhost:22000${NC}"
    echo -e "${GREEN}外部訪問: http://59.126.6.46:22000 (需配置端口轉發)${NC}"
    echo -e "${GREEN}API文檔: http://localhost:22000/docs${NC}"
else
    echo -e "${RED}服務啟動失敗，請檢查日誌:${NC}"
    docker-compose -f $COMPOSE_FILE logs
fi 