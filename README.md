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
- **車輛管理**：車輛註冊、電池狀態更新、車輛信息查詢 (`/vehicles`相關路由)。
- **充電記錄**：記錄用戶充電活動並計算碳積分 (相關邏輯整合在其他服務中)。
- **社群系統**：
    - `POST /users/friends`: 添加/移除好友。
    - `GET /users/leaderboard`: 查看積分排行榜。
- **任務與成就**：
    - `GET /users/tasks`: 獲取用戶任務列表。
    - `GET /users/achievements`: 獲取用戶成就列表。
    - `POST /tasks/complete`: 更新任務進度。
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
│   │   ├── user_routes.py  # 用戶、認證、社群、任務、獎勵等
│   │   ├── vehicle_routes.py # 車輛管理
│   │   ├── station_routes.py # 充電站管理
│   │   ├── task_routes.py  # 任務定義 (可能與 user_routes 整合)
│   │   └── token_routes.py # JWT Token 相關 (可能與 user_routes 整合)
│   │   └── achievement_routes.py # 成就定義 (可能與 user_routes 整合)
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
- `GET /users/tasks`: 任務列表
- `GET /users/achievements`: 成就列表
- `POST /users/redeem-reward`: 兌換獎勵
- `GET /users/inventory`: 物品庫
- `GET /vehicles/user/{user_id}`: 獲取用戶車輛
- `POST /vehicles`: 註冊車輛
- `POST /vehicles/{vehicle_id}/battery`: 更新電池狀態
- `GET /stations`: 獲取充電站
- `POST /stations`: 創建充電站
- `GET /health`: 健康檢查

## Firebase 推播服務 (開發中)

系統計劃整合 Firebase Cloud Messaging (FCM) 以實現推播通知功能，例如 OTP、系統通知、活動提醒等。相關 API (`/users/update-fcm-token`) 和服務模塊 (`app/services/firebase_service.py`) 已初步建立，但完整功能待後續開發和 Firebase 項目配置。

## 注意事項

- **安全性**: 確保 `SECRET_KEY` 的安全，不要硬編碼敏感信息。生產環境建議使用更安全的配置管理方式。
- **錯誤處理**: API 包含詳細的錯誤處理和 HTTP 狀態碼，客戶端應妥善處理。
- **異步處理**: 大量使用了 Python 的 `async/await` 語法，確保 I/O 操作 (如數據庫查詢、郵件發送) 不會阻塞事件循環。
- **數據庫索引**: `app/database/mongodb.py` 中會自動創建必要的索引以優化查詢性能。
