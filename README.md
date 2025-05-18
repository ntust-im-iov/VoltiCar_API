# Volticar API - 電動汽車智慧充電與社群平台

基於 FastAPI 的電動汽車充電站管理、用戶充電記錄、社群互動及獎勵系統 API。

## 主要功能

- **用戶管理**：
    - **Email 驗證註冊流程**:
        1. `POST /users/request-verification`: 請求發送驗證 Email。
        2. `GET /users/verify-email`: 透過 Email 中的連結驗證地址 (返回 HTML)。
        3. `POST /users/complete-registration`: 提供用戶名、密碼完成註冊。
    - **登入**:
        - `POST /users/login`: 使用 Email/用戶名和密碼登入。
        - `POST /users/login/google`: 使用 Google 帳號登入/註冊。
    - **密碼重設 (OTP)**:
        1. `POST /users/forgot-password`: 請求發送密碼重設 OTP 到 Email。
        2. `POST /users/verify-reset-otp`: 驗證收到的 OTP。
        3. `POST /users/reset-password`: 使用驗證後取得的短期權杖設定新密碼。
    - **個人資料**: `GET /users/profile` 獲取用戶資訊。
    - **FCM Token**: `POST /users/update-fcm-token` 更新用於推播通知的 Firebase Cloud Messaging Token。
- **充電站管理**：查詢、創建充電站 (`/stations`相關路由)。
- **車輛管理**：
    - 車輛註冊 (`POST /vehicles`)：註冊玩家擁有的車輛實例，實例的唯一ID (`instance_id`) 由服務端生成。請求時需提供基於哪個車輛定義的 `vehicle_id`。
    - 車輛信息查詢 (`GET /vehicles/user/{user_id}` 獲取用戶所有車輛, `GET /vehicles/{user_id}/{instance_id}` 獲取特定車輛實例信息)。
    - 車輛動態信息更新 (`PUT /vehicles/{instance_id}`)：如電池狀態、里程等。
- **遊戲設定/會話準備** (大部分端點位於 `/api/v1` 前綴下)：
    - **車輛選擇**:
        - `GET /api/v1/player/vehicles`: 列出玩家可選擇的車輛（包括自有車輛的實例ID和可租用車輛的定義ID）。
        - `PUT /api/v1/player/game_session/vehicle`: 玩家為當前遊戲會話選擇一個車輛定義。
    - **目的地選擇**:
        - `GET /api/v1/player/destinations`: 列出玩家可選擇的目的地。
        - `PUT /api/v1/player/game_session/destination`: 玩家為當前遊戲會話選擇目的地。
    - **貨物選擇**:
        - `GET /api/v1/player/warehouse/items`: 列出玩家倉庫中的物品及其數量。
        - `PUT /api/v1/player/game_session/cargo`: 玩家為當前會話選擇要運輸的貨物，系統會校驗貨物總量是否超出所選車輛的載重和容積限制。此為暫存選擇，非實際扣減倉庫物品。
    - **會話總覽與開始**:
        - `GET /api/v1/player/game_session/summary`: 獲取當前遊戲會話設定（已選車輛、貨物、目的地）的總覽。
        - `POST /api/v1/player/game_session/start`: 根據當前設定開始一個新的遊戲會話。
- **充電記錄**：記錄用戶充電活動並計算碳積分 (相關邏輯整合在其他服務中)。
- **社群系統**：
    - `POST /users/friends`: 添加/移除好友。
    - `GET /users/leaderboard`: 查看積分排行榜。
- **任務與成就** (玩家任務相關端點位於 `/api/v1` 前綴下)：
    - `GET /api/v1/tasks/`: 列出所有可用的任務定義。
    - `POST /api/v1/player/tasks/`: 玩家接受一個任務。如果玩家之前放棄過同一定義的任務，則會重用該記錄而非創建新記錄。
    - `DELETE /api/v1/player/tasks/{player_task_uuid}`: 玩家放棄一個已接受的任務（標記為已放棄）。
    - `GET /api/v1/player/tasks/`: 獲取特定玩家的任務列表（可按狀態篩選）。
    - `GET /users/achievements`: 獲取用戶成就列表。
- **獎勵系統**：
    - `POST /users/redeem-reward`: 使用積分兌換獎勵。
    - `GET /users/inventory`: 查看用戶物品庫。
- **推播通知**：使用 Firebase Cloud Messaging (FCM) 向用戶發送推播通知 (部分功能開發中)。

## 技術棧

- **FastAPI**: 現代、高性能的 Python Web 框架。
- **MongoDB**: NoSQL 數據庫，使用 `motor` 異步驅動。
- **Pydantic**: 數據驗證和模型定義。
- **JWT**: 用於安全的 API 認證。
- **Docker / Docker Compose**: 容器化部署與管理。
- **Email Service**: 使用 `aiohttp` (隱含於 FastAPI 背景任務或直接調用) 發送異步郵件。
- **Firebase Admin SDK**: 用於 FCM 推播通知 (開發中)。
- **Uvicorn**: ASGI 伺服器。

## 項目結構

```
volticar_api/
│
├── app/                    # 應用主目錄
│   ├── api/                # API路由模塊
│   │   ├── __init__.py
│   │   ├── user_routes.py  # 用戶核心、認證、社群、獎勵等 (多數在 /users 前綴下)
│   │   ├── vehicle_routes.py # 玩家擁有車輛實例管理 (prefix: /vehicles)
│   │   ├── station_routes.py # 充電站管理 (prefix: /stations)
│   │   ├── task_routes.py  # 任務定義與玩家任務實例 (prefixes: /api/v1/tasks, /api/v1/player/tasks)
│   │   ├── game_setup_routes.py # 遊戲會話準備流程 (prefix: /api/v1)
│   │   ├── token_routes.py # Token 相關 (prefix: /token)
│   │   └── achievement_routes.py # 成就相關 (prefix: /achievements)
│   │
│   ├── database/           # 數據庫連接
│   │   └── mongodb.py      # MongoDB 初始化與集合定義
│   │
│   ├── models/             # Pydantic 數據模型
│   │   ├── user.py         # 用戶相關模型 (包含註冊、登入、OTP、FCM等)
│   │   └── station.py      # 充電站模型
│   │
│   ├── services/           # 外部服務客戶端
│   │   └── email_service.py # 異步郵件發送服務
│   │   # └── firebase_service.py # Firebase 推播服務 (待完善)
│   │
│   └── utils/              # 工具函數
│       ├── auth.py         # 認證 (密碼哈希, JWT, 用戶依賴)
│       └── helpers.py      # 其他輔助函數
│
├── logs/                   # 日誌文件目錄 (由 logging 配置產生)
├── .dockerignore           # Docker 忽略文件
├── .gitignore              # Git 忽略文件
├── Dockerfile              # 應用 Docker 鏡像構建文件
├── docker-compose.yml      # 開發環境 Docker Compose 配置
├── docker-compose.production.yml # 生產環境 Docker Compose 配置
├── .env                    # 環境變量文件 (本地開發用)
├── env.example             # 環境變量範例
├── main.py                 # FastAPI 應用入口點
├── README.md               # 項目說明文件
└── requirements.txt        # Python 依賴列表
```
*(注意: `restart.bat` 和 `start_api.bat` 已從結構圖中移除，因為它們是特定於開發環境的輔助腳本)*

## 安裝與運行

### 環境準備

- Python 3.8+
- MongoDB 數據庫 (本地或遠程)
- Docker & Docker Compose (推薦)

### 本地開發

1.  **克隆倉庫**:
    ```bash
    git clone <repository_url>
    cd volticar_api
    ```
2.  **創建虛擬環境** (推薦):
    ```bash
    python -m venv venv
    source venv/bin/activate  # Linux/macOS
    # venv\Scripts\activate  # Windows
    ```
3.  **安裝依賴**:
    ```bash
    pip install -r requirements.txt
    ```
4.  **配置環境變量**:
    複製 `env.example` 為 `.env` 並填寫必要的配置 (數據庫連接、郵件服務器、JWT 密鑰等)。
5.  **運行應用**:
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 22000 --reload
    ```
    *   `--reload` 會在代碼變更時自動重啟服務，適合開發。

### 使用 Docker 部署

1.  **配置環境變量**:
    確保 `docker-compose.yml` 或 `docker-compose.production.yml` 中定義了必要的環境變量，或者使用 `.env` 文件 (Docker Compose 會自動加載)。
2.  **構建並啟動服務**:
    *   開發環境:
        ```bash
        docker-compose up --build -d
        ```
    *   生產環境 (通常包含反向代理如 Nginx):
        ```bash
        docker-compose -f docker-compose.production.yml up --build -d
        ```
3.  **查看日誌**:
    ```bash
    docker-compose logs -f <service_name>  # 例如: docker-compose logs -f volticar-api
    ```
4.  **停止服務**:
    ```bash
    docker-compose down
    ```
    或 (生產環境):
    ```bash
    docker-compose -f docker-compose.production.yml down
    ```

## 環境變量 (`.env`)

- `DATABASE_URL`: MongoDB 連接 URL (包含認證信息)。
- `VOLTICAR_DB`: Volticar 主數據庫名稱。
- `SECRET_KEY`: 用於 JWT 簽名的密鑰 (請使用強隨機字符串)。
- `ALGORITHM`: JWT 簽名算法 (預設: HS256)。
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Access Token 有效期 (分鐘)。
- `API_BASE_URL`: API 的基礎 URL，用於生成郵件中的驗證連結 (例如: `https://yourdomain.com` 或 `http://localhost:22000`)。
- `MAIL_USERNAME`: SMTP 伺服器用戶名。
- `MAIL_PASSWORD`: SMTP 伺服器密碼。
- `MAIL_FROM`: 發件人 Email 地址。
- `MAIL_PORT`: SMTP 伺服器端口 (例如: 465 for SSL, 587 for TLS)。
- `MAIL_SERVER`: SMTP 伺服器地址。
- `MAIL_STARTTLS`: 是否啟用 STARTTLS (True/False)。
- `MAIL_SSL_TLS`: 是否啟用 SSL/TLS (True/False)。
- `FIREBASE_CREDENTIALS_PATH`: (可選) Firebase Admin SDK 服務帳號金鑰 JSON 文件路徑。

## API 端點概覽

API 使用 FastAPI 自動生成交互式文檔。服務運行後，訪問 `/docs` (Swagger UI) 或 `/redoc` (ReDoc)。

**重要提示**: 許多端點現在使用 `application/x-www-form-urlencoded` 格式接收參數 (使用 `Form(...)`)，而不是 JSON。請參考 `/docs` 中的具體端點定義。

### 主要用戶流程

- **註冊**: `POST /users/request-verification` -> (Email) -> `GET /users/verify-email` -> `POST /users/complete-registration`
- **登入**: `POST /users/login` 或 `POST /users/login/google`
- **密碼重設**: `POST /users/forgot-password` -> (Email OTP) -> `POST /users/verify-reset-otp` -> `POST /users/reset-password`

### 其他端點 (部分列表)

- `GET /users/profile`: 獲取用戶資料
- `POST /users/update-fcm-token`: 更新 FCM Token
- `POST /users/friends`: 添加/刪除好友
- `GET /users/leaderboard`: 排行榜
- `GET /users/achievements`: 成就列表
- `POST /users/redeem-reward`: 兌換獎勵
- `GET /users/inventory`: 物品庫

- **車輛管理 (`/vehicles` prefix):**
    - `GET /vehicles/user/{user_id}`: 獲取指定用戶的所有車輛實例。
    - `POST /vehicles/`: 註冊一個新的玩家車輛實例 (實例ID由服務端生成)。
    - `GET /vehicles/{user_id}/{instance_id}`: 獲取特定車輛實例的詳細信息。
    - `PUT /vehicles/{instance_id}`: 更新特定車輛實例的動態信息 (如電池、里程)。
    - (注意: 原 `POST /vehicles/{vehicle_id}/battery` 端點功能已整合到 `PUT /vehicles/{instance_id}`)

- **遊戲設定/會話準備 (`/api/v1` prefix):**
    - `GET /api/v1/player/vehicles`: 列出玩家可選擇的車輛。
    - `PUT /api/v1/player/game_session/vehicle`: 選擇用於會話的車輛。
    - `GET /api/v1/player/destinations`: 列出可選目的地。
    - `PUT /api/v1/player/game_session/destination`: 選擇目的地。
    - `GET /api/v1/player/warehouse/items`: 列出玩家倉庫物品。
    - `PUT /api/v1/player/game_session/cargo`: 選擇貨物。
    - `GET /api/v1/player/game_session/summary`: 獲取會話設定總覽。
    - `POST /api/v1/player/game_session/start`: 開始遊戲會話。

- **任務系統 (`/api/v1` prefix):**
    - `GET /api/v1/tasks/`: 列出可用的任務定義。
    - `POST /api/v1/player/tasks/`: 玩家接受任務 (會重用已放棄的記錄)。
    - `DELETE /api/v1/player/tasks/{player_task_uuid}`: 玩家放棄任務。
    - `GET /api/v1/player/tasks/`: 獲取玩家的任務列表。

- **充電站 (`/stations` prefix):**
    - `GET /stations`: 獲取充電站列表 (支持按城市、地理範圍查詢及分頁)。
    - `POST /stations`: 創建充電站。
    - `GET /stations/overview`: 地圖概覽 API。
    - `GET /stations/city/{city}`: 按城市查詢 API。

- `GET /health`: 健康檢查

## 充電站地圖 API 優化與使用建議

為了提升充電站地圖功能的效能和使用者體驗，後端 API 進行了以下優化：

1.  **頻率限制 (Rate Limiting)**:
    *   對充電站相關的查詢 API (如 `/stations/overview`, `/stations/city/{city}`) 實施了頻率限制，以防止濫用和過載。預設限制為每分鐘數次請求，具體限制請參考 API 文件或錯誤回應。

2.  **地圖概覽 API (`GET /stations/overview`) 優化**:
    *   此端點設計用於高效獲取地圖可視區域內的充電站概覽資訊。
    *   **地理空間查詢**: 接受四個可選的地理邊界框查詢參數：`min_lat`, `min_lon`, `max_lat`, `max_lon`。
        *   前端應根據地圖當前可視區域的西南角和東北角經緯度傳遞這些參數。
        *   例如: `/stations/overview?min_lon=121.50&min_lat=25.00&max_lon=121.55&max_lat=25.05`
        *   如果未提供這些參數，API 將返回所有充電站的概覽資訊 (可能會非常多，不建議在生產環境中頻繁使用)。
        *   **重要**: 此功能依賴於後端 `AllChargingStations` MongoDB 集合中存在一個名為 `location_geo` 的 GeoJSON Point 欄位 (格式: `{ "type": "Point", "coordinates": [longitude, latitude] }`)，並且已為此欄位建立了 `2dsphere` 索引。請確保資料庫已按此方式設定。
    *   **前端使用建議**:
        *   **僅請求可視區域數據**: 務必根據地圖的可視範圍傳遞邊界框參數。
        *   **Debounce/Throttle**: 在地圖移動或縮放時，使用 Debounce 或 Throttle 機制來限制 API 呼叫的頻率，避免過於頻繁的請求。
        *   **前端快取**: 前端應實施自己的快取機制 (例如，使用瀏覽器的 `localStorage` 或記憶體快取)，以減少對相同區域數據的重複請求。

3.  **按城市查詢 API (`GET /stations/city/{city}`) 優化**:
    *   **分頁**: 此端點現在支援分頁參數 `skip` (跳過的記錄數，預設 0) 和 `limit` (每頁返回的記錄數，預設 100)。
        *   例如: `/stations/city/Taipei?skip=0&limit=50`
    *   **前端使用建議**:
        *   如果城市內的充電站數量較多，應實作分頁載入或無限滾動等 UI/UX 模式。
        *   **前端快取**: 同樣建議前端快取已載入的城市數據。

4.  **後端快取 (Redis)**:
    *   後端已整合 Redis 作為快取層，用於快取 `/stations/overview` 和 `/stations/city/{city}` 的查詢結果，以進一步提升回應速度並減輕資料庫負擔。
    *   **Redis 設定建議**:
        *   建議使用 Docker 運行 Redis 服務: `docker run -d -p 6379:6379 --name volticar-redis redis:latest`
        *   在應用程式的 `.env` 檔案中設定 Redis 連線資訊:
            ```env
            REDIS_HOST=localhost
            REDIS_PORT=6379
            ```
        *   如果 Redis 部署在不同主機或有密碼保護，請相應調整連線 URL。

5.  **資料庫索引建議**:
    *   為確保查詢效能，請檢查並確保以下 MongoDB 索引已建立：
        *   在 `AllChargingStations` 集合上：
            *   `location_geo` 欄位 (或您實際使用的 GeoJSON 地理位置欄位) 應有 `2dsphere` 索引。
            *   `StationID` 欄位應有唯一索引 (如果它是主要識別碼)。
        *   在各城市充電站集合 (如 `Taipei`, `NewTaipei` 等) 上：
            *   `StationID` 欄位應有索引。
            *   如果經常按其他欄位查詢，也應考慮為這些欄位建立索引。

透過以上後端優化和前端的配合，可以顯著提升充電站地圖功能的效能和穩定性。

## Firebase 推播服務 (開發中)

系統計劃整合 Firebase Cloud Messaging (FCM) 以實現推播通知功能，例如 OTP、系統通知、活動提醒等。相關 API (`/users/update-fcm-token`) 和服務模塊 (`app/services/firebase_service.py`) 已初步建立，但完整功能待後續開發和 Firebase 項目配置。

## 注意事項

- **安全性**: 確保 `SECRET_KEY` 的安全，不要硬編碼敏感信息。生產環境建議使用更安全的配置管理方式。
- **錯誤處理**: API 包含詳細的錯誤處理和 HTTP 狀態碼，客戶端應妥善處理。
- **異步處理**: 大量使用了 Python 的 `async/await` 語法，確保 I/O 操作 (如數據庫查詢、郵件發送) 不會阻塞事件循環。
- **數據庫索引**: `app/database/mongodb.py` 中會自動創建必要的索引以優化查詢性能。
