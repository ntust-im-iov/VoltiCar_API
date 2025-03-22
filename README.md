# 電動汽車充電站 API

基於FastAPI的電動汽車充電站管理和用戶充電記錄系統。

## 功能

- 用戶管理：註冊、登錄、認證
- 充電站管理：查詢、創建充電站
- 充電記錄：記錄用戶充電活動並計算碳積分

## 技術棧

- **FastAPI**：現代、高性能的Python Web框架
- **MongoDB**：NoSQL數據庫存儲用戶和充電站信息
- **JWT認證**：安全的基於令牌的認證系統
- **Pydantic**：數據驗證和設置管理
- **Docker**：容器化部署支持

## 項目結構

```
my_fastapi_project/
│
├── app/                    # 應用主目錄
│   ├── api/                # API路由
│   │   ├── __init__.py     # API路由初始化
│   │   ├── user_routes.py  # 用戶相關路由
│   │   └── station_routes.py # 充電站相關路由
│   │
│   ├── database/           # 數據庫連接
│   │   └── mongodb.py      # MongoDB連接配置
│   │
│   ├── models/             # 數據模型
│   │   ├── user.py         # 用戶模型
│   │   └── station.py      # 充電站模型
│   │
│   └── utils/              # 工具函數
│       ├── auth.py         # 認證工具
│       └── helpers.py      # 輔助函數
│
├── Dockerfile              # Docker構建文件
├── docker-compose.yml      # Docker Compose配置
├── docker-compose.production.yml # 生產環境配置
├── .env                    # 環境變量配置
├── main.py                 # 應用入口
└── requirements.txt        # 項目依賴
```

## 安裝與運行

### 本地運行

1. 安裝依賴：

```bash
pip install -r requirements.txt
```

2. 運行應用：

```bash
python main.py
```

### 使用Docker部署

1. 通過Docker Compose啟動應用：

```bash
docker-compose up -d
```

這將構建API鏡像並啟動API容器。API將連接到外部MongoDB數據庫（59.126.6.46:27017）。

2. 查看運行中的容器：

```bash
docker-compose ps
```

3. 停止服務：

```bash
docker-compose down
```

### 生產環境部署

使用生產環境配置文件啟動：

```bash
docker-compose -f docker-compose.production.yml up -d
```

或使用提供的啟動腳本：

```bash
./startup.sh production
```

## 環境變量

在`.env`文件或Docker環境變量中配置：

- `DATABASE_URL`: MongoDB連接URL（默認指向59.126.6.46:27017）
- `VOLTICAR_DB`: Volticar數據庫名
- `CHARGE_STATION_DB`: 充電站數據庫名
- `SECRET_KEY`: JWT認證密鑰
- `API_HOST`: API主機地址
- `API_PORT`: API端口

## API端點

### 用戶API

- `POST /users`：創建新用戶
- `POST /users/token`：用戶登錄獲取令牌
- `GET /users/me`：獲取當前用戶信息
- `GET /users/{user_id}`：獲取指定用戶信息
- `POST /users/{user_id}/charge`：記錄充電活動

### 充電站API

- `GET /stations`：獲取所有充電站
- `GET /stations/{station_id}`：獲取指定充電站
- `GET /stations/city/{city}`：獲取指定城市的充電站（支持中文城市名）
- `POST /stations`：創建新充電站

### 健康檢查

- `GET /health`: 檢查API服務狀態 