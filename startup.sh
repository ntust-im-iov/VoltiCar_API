#!/bin/bash

# 设置颜色
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}启动Volticar电动汽车充电站API服务...${NC}"

# 检查docker和docker-compose是否安装
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: docker未安装，请先安装docker${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}错误: docker-compose未安装，请先安装docker-compose${NC}"
    exit 1
fi

# 检查环境
ENV=${1:-development}

if [ "$ENV" = "production" ]; then
    COMPOSE_FILE="docker-compose.production.yml"
    echo -e "${YELLOW}在生产环境中启动服务...${NC}"
else
    COMPOSE_FILE="docker-compose.yml"
    echo -e "${YELLOW}在开发环境中启动服务...${NC}"
fi

# 构建并启动容器
echo -e "${YELLOW}构建和启动容器...${NC}"
docker-compose -f $COMPOSE_FILE up -d --build

# 检查容器状态
echo -e "${YELLOW}检查容器状态...${NC}"
RUNNING=$(docker-compose -f $COMPOSE_FILE ps | grep "Up" | wc -l)

if [ $RUNNING -ge 1 ]; then
    echo -e "${GREEN}服务已成功启动!${NC}"
    echo -e "${GREEN}API服务运行在 http://localhost:8000${NC}"
    echo -e "${GREEN}API文档可在 http://localhost:8000/docs 查看${NC}"
else
    echo -e "${RED}服务启动失败，请检查日志:${NC}"
    docker-compose -f $COMPOSE_FILE logs
fi 