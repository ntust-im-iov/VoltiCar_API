# 電動汽車充電站 API

基於FastAPI的電動汽車充電站管理、用戶充電記錄系統，包含社交互動和獎勵機制。

## 功能

- **用戶管理**：註冊、登錄、認證
- **充電站管理**：查詢、創建充電站
- **車輛管理**：車輛註冊、電池狀態更新、車輛信息查詢
- **充電記錄**：記錄用戶充電活動並計算碳積分
- **社交系統**：好友添加/移除、排行榜競賽
- **任務與成就**：每日任務、成就解鎖、積分獎勵
- **虛擬物品**：積分兌換、物品庫管理
- **推播通知**：使用Firebase Cloud Messaging (FCM)向用戶發送推播通知

## 技術棧

- **FastAPI**：現代、高性能的Python Web框架
- **MongoDB**：NoSQL數據庫存儲用戶和充電站信息
- **JWT認證**：安全的基於令牌的認證系統
- **Pydantic**：數據驗證和設置管理
- **Docker**：容器化部署支持
- **Firebase Admin SDK**：推播通知服務

## 項目結構

```
volticar_api/
│
├── app/                    # 應用主目錄
│   ├── api/                # API路由
│   │   ├── __init__.py     # API路由初始化
│   │   ├── user_routes.py  # 用戶相關路由
│   │   ├── vehicle_routes.py # 車輛相關路由
│   │   ├── station_routes.py # 充電站相關路由
│   │   └── task_routes.py  # 任務相關路由
│   │
│   ├── database/           # 數據庫連接
│   │   └── mongodb.py      # MongoDB連接配置
│   │
│   ├── models/             # 數據模型
│   │   ├── user.py         # 用戶和功能模型
│   │   └── station.py      # 充電站模型
│   │
│   ├── services/           # 外部服務
│   │   └── firebase_service.py # Firebase推播服務
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
├── restart.bat             # Windows重啟腳本
├── start_api.bat           # Windows啟動腳本
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
# 使用啟動腳本(Windows)
start_api.bat

# 或直接使用Python
python main.py
```

### 使用Docker部署

1. 通過Docker Compose啟動應用：

```bash
docker-compose up -d
```

這將構建API鏡像並啟動API容器。API將連接到外部MongoDB數據庫。

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

或使用Windows環境的啟動腳本：

```bash
restart.bat
```

## 環境變量

在`.env`文件或Docker環境變量中配置：

- `DATABASE_URL`: MongoDB連接URL
- `VOLTICAR_DB`: Volticar數據庫名
- `CHARGE_STATION_DB`: 充電站數據庫名
- `SECRET_KEY`: JWT認證密鑰
- `API_HOST`: API主機地址
- `API_PORT`: API端口
- `API_ENV`: 環境類型（開發或生產）
- `FIREBASE_CREDENTIALS_PATH`: Firebase服務帳號金鑰文件路徑（用於FCM推播）
- `PYTHONIOENCODING`: Python I/O編碼設置（建議使用utf-8）

## API端點

### 用戶API

- `POST /users/register`：創建新用戶
- `POST /users/login`：用戶登錄獲取令牌
- `GET /users/profile`：獲取當前用戶信息
- `POST /users/send-otp`：發送OTP驗證碼
- `POST /users/verify-otp`：驗證OTP代碼
- `POST /users/update-fcm-token`：更新FCM令牌（用於推播通知）
- `GET /users/leaderboard`：獲取用戶積分排行榜
- `POST /users/friends`：管理好友關係（添加/刪除）
- `GET /users/tasks`：獲取用戶任務列表
- `GET /users/achievements`：獲取用戶成就列表
- `POST /users/redeem-reward`：兌換積分獎勵
- `GET /users/inventory`：獲取用戶物品庫
- `GET /users/charging-stations`：獲取附近充電站

### 車輛API

- `GET /vehicles/{user_id}/{vehicle_id}`：獲取指定車輛信息
- `POST /vehicles`：註冊新車輛
- `POST /vehicles/{vehicle_id}/battery`：更新車輛電池信息
- `PUT /vehicles/{vehicle_id}`：更新車輛基本信息
- `GET /vehicles/user/{user_id}`：獲取用戶的所有車輛

### 任務API

- `GET /tasks/daily`：獲取每日任務
- `POST /tasks/complete`：完成任務更新進度
- `GET /tasks`：獲取所有任務

### 充電站API

- `GET /stations`：獲取所有充電站
- `GET /stations/{station_id}`：獲取指定充電站
- `GET /stations/city/{city}`：獲取指定城市的充電站（支持中文城市名）
- `POST /stations`：創建新充電站

### 健康檢查

- `GET /health`: 檢查API服務狀態

## 社交互動功能

### 好友系統

好友系統允許用戶添加或移除好友關係，實現社交互動：

1. 添加好友：
   ```
   POST /users/friends
   {
     "user_id": "user123",
     "friend_id": "friend456",
     "action": "add"
   }
   ```

2. 移除好友：
   ```
   POST /users/friends
   {
     "user_id": "user123",
     "friend_id": "friend456",
     "action": "remove"
   }
   ```

### 排行榜競賽

用戶可以在不同時間範圍內查看碳積分排行榜，鼓勵環保行為：

```
GET /users/leaderboard?time_range=week
```

支持的時間範圍：`day`、`week`、`month`

## 任務與獎勵系統

### 每日任務

系統提供每日任務，用戶完成任務可獲得碳積分：

```
GET /tasks/daily?user_id=user123
```

### 獎勵兌換

用戶可以使用碳積分兌換虛擬物品：

```
POST /users/redeem-reward
{
  "user_id": "user123",
  "points": 100,
  "reward_id": "reward789"
}
```

### 物品庫

用戶可以查看已兌換的所有物品：

```
GET /users/inventory?user_id=user123
```

## 車輛管理功能

### 車輛註冊

用戶可以註冊多輛電動車：

```
POST /vehicles
{
  "user_id": "user123",
  "vehicle_id": "car456",
  "vehicle_name": "特斯拉Model 3"
}
```

### 電池狀態更新

定期更新車輛的電池狀態和里程：

```
POST /vehicles/car456/battery?battery_level=80&battery_health=95&lastcharge_mileage=150
```

## Firebase推播服務

> **重要提示：** FCM功能目前處於開發階段，尚未完全啟用。系統已完成相關模型和API接口設計，但尚未連接到實際的Firebase服務。推播功能將在後續版本中實現。

本系統整合了Firebase Cloud Messaging (FCM)用於向用戶發送推播通知，主要用於：

1. 發送OTP驗證碼
2. 系統通知
3. 活動與優惠提醒
4. 任務完成提醒
5. 好友互動通知

### 設置Firebase

1. 在Firebase控制台創建一個新項目
2. 生成服務帳號金鑰（JSON格式）
3. 將金鑰設置為環境變量或文件：
   ```
   FIREBASE_CREDENTIALS={"type":"service_account",...}
   ```
   或
   ```
   FIREBASE_CREDENTIALS_PATH=/path/to/firebase-credentials.json
   ```
4. 在生產環境中設置`API_ENV=production`以啟用FCM功能

### 使用FCM推播

1. 客戶端獲取FCM令牌並通過API更新：
   ```
   POST /users/update-fcm-token
   {
     "user_id": "user123",
     "fcm_token": "firebase-token",
     "device_info": "iPhone 13, iOS 15.4"
   }
   ```

2. 伺服器可以通過`firebase_service.py`中的函數發送推播

## 連接問題處理

### MongoDB連接問題

如果遇到MongoDB連接問題，尤其是SSL相關錯誤：

1. 檢查連接字符串中的SSL設置：
   ```
   DATABASE_URL=mongodb://username:password@hostname:port/?authSource=admin&ssl=false
   ```

2. 確保環境變量設置正確：
   ```
   PYTHONIOENCODING=utf-8
   ```

3. 使用`start_api.bat`直接啟動Python服務，避免Docker環境的額外複雜性

### 編碼問題

對於中文字符支持問題：

1. 確保所有Python腳本使用UTF-8編碼
2. 在Windows環境中，命令提示符添加：`chcp 65001`設置UTF-8編碼
3. 在Docker環境中設置環境變量：`PYTHONIOENCODING=utf-8`

## 開發注意事項

1. API文檔可在運行後訪問：`http://localhost:22000/docs`
2. MongoDB索引已被自動處理，使用`sparse=True`避免null值重複問題
3. 使用Windows環境中的`restart.bat`可一鍵重啟整個服務
4. 使用`start_api.bat`可直接啟動Python服務，不依賴Docker環境 