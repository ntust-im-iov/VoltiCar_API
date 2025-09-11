# 遊戲 API 與資料庫設計

## 1. API 端點設計列表 (RESTful風格)

**基礎路徑:** `/api/v1`

**認證:** 除非特別說明，所有需要操作玩家特定數據的 API 都需要用戶認證 (例如通過 JWT Token)。

---

### 1.1 任務選擇 (Task Selection)

*   **1.1.1 獲取任務列表**
    *   **HTTP 方法:** `GET`
    *   **路徑:** `/api/v1/tasks`
    *   **用途:** 獲取當前可供玩家選擇的任務列表（例如每日任務、特殊任務）。
    *   **請求參數:**
        *   `status` (查詢參數, 可選, string): 篩選任務狀態，例如 `available` (預設), `accepted` (需要配合玩家認證)。
        *   `mode` (查詢參數, 可選, string): 篩選任務模式，例如 `daily`, `story`。
    *   **請求體:** 無
    *   **回應體 (成功: 200 OK):**
        ```json
        {
          "tasks": [
            {
              "task_id": "string (ObjectId)",
              "title": "string",
              "description": "string",
              "rewards": {
                "experience": "integer",
                "currency": "integer"
              },
              "requirements": "object", // 例如：特定貨物、目的地等
              "mode": "string", // daily, story
              "expiry_date": "string (ISO 8601 DateTime, 可選)"
            }
            // ... 其他任務
          ]
        }
        ```
    *   **回應體 (錯誤):**
        *   `401 Unauthorized`: 若請求 `status=accepted` 但未認證。
        *   `500 Internal Server Error`: 伺服器錯誤。
    *   **用戶認證:** 獲取 `available` 任務時可選，獲取 `accepted` 任務時需要。

*   **1.1.2 接受任務**
    *   **HTTP 方法:** `POST`
    *   **路徑:** `/api/v1/player/tasks`
    *   **用途:** 允許玩家接受一個任務。
    *   **請求參數:** 無
    *   **請求體:**
        ```json
        {
          "task_id": "string (ObjectId)" // 要接受的任務 ID
        }
        ```
    *   **回應體 (成功: 201 Created):**
        ```json
        {
          "message": "Task accepted successfully.",
          "player_task": {
            "player_task_id": "string (ObjectId)",
            "player_id": "string (ObjectId)",
            "task_id": "string (ObjectId)",
            "status": "accepted", // accepted, completed, abandoned
            "accepted_at": "string (ISO 8601 DateTime)",
            "progress": "object" // 任務進度詳情
          }
        }
        ```
    *   **回應體 (錯誤):**
        *   `400 Bad Request`: 請求無效 (例如任務不存在、任務已接受、不滿足接受條件)。
        *   `401 Unauthorized`: 未認證。
        *   `404 Not Found`: 任務 ID 不存在。
        *   `409 Conflict`: 任務已被其他玩家接受（如果任務是唯一的）或玩家已接受過此可重複任務且未完成。
        *   `500 Internal Server Error`: 伺服器錯誤。
    *   **用戶認證:** 需要

*   **1.1.3 放棄任務**
    *   **HTTP 方法:** `DELETE`
    *   **路徑:** `/api/v1/player/tasks/{player_task_id}`
    *   **用途:** 允許玩家放棄一個已接受的任務。
    *   **請求參數:**
        *   `player_task_id` (路徑參數, string (ObjectId)): 玩家任務記錄的 ID。
    *   **請求體:** 無
    *   **回應體 (成功: 200 OK):**
        ```json
        {
          "message": "Task abandoned successfully."
        }
        ```
    *   **回應體 (錯誤):**
        *   `401 Unauthorized`: 未認證或無權操作該任務。
        *   `403 Forbidden`: 任務狀態不允許放棄 (例如已完成或遊戲會話進行中關聯此任務)。
        *   `404 Not Found`: 玩家任務記錄 ID 不存在。
        *   `500 Internal Server Error`: 伺服器錯誤。
    *   **用戶認證:** 需要

---

### 1.2 車輛選擇 (Vehicle Selection)

*   **1.2.1 獲取可選車輛列表**
    *   **HTTP 方法:** `GET`
    *   **路徑:** `/api/v1/player/vehicles`
    *   **用途:** 獲取玩家可選用的車輛列表（已擁有、可租用等）。
    *   **請求參數:**
        *   `availability` (查詢參數, 可選, string): 篩選車輛可用性，例如 `owned` (預設), `rentable`, `all`。
    *   **請求體:** 無
    *   **回應體 (成功: 200 OK):**
        ```json
        {
          "vehicles": [
            {
              "vehicle_id": "string (ObjectId)", // vehicles 集合的 ID
              "player_owned_vehicle_id": "string (ObjectId, 可選)", // player_owned_vehicles 集合的 ID, 如果是 owned
              "name": "string",
              "type": "string",
              "max_load_weight": "float", // 最大載重 (公斤)
              "max_load_volume": "float", // 最大容積 (立方米)
              "status": "string" // owned, rentable, in_use (如果 owned 且在其他會話中)
            }
            // ... 其他車輛
          ]
        }
        ```
    *   **回應體 (錯誤):**
        *   `401 Unauthorized`: 未認證。
        *   `500 Internal Server Error`: 伺服器錯誤。
    *   **用戶認證:** 需要

*   **1.2.2 選擇/更換遊戲會話車輛**
    *   **HTTP 方法:** `PUT`
    *   **路徑:** `/api/v1/player/game_session/vehicle`
    *   **用途:** 允許玩家為當前準備的遊戲會話選擇或更換車輛。此操作會清空已選貨物。
    *   **請求參數:** 無
    *   **請求體:**
        ```json
        {
          "vehicle_id": "string (ObjectId)" // 要選擇的 vehicles 集合的 ID
        }
        ```
    *   **回應體 (成功: 200 OK):**
        ```json
        {
          "message": "Vehicle selected for game session. Any previously selected cargo has been cleared.",
          "selected_vehicle": {
            "vehicle_id": "string (ObjectId)",
            "name": "string",
            "max_load_weight": "float",
            "max_load_volume": "float"
          },
          "cleared_cargo": "boolean" // 指示是否清空了貨物 (true)
        }
        ```
    *   **回應體 (錯誤):**
        *   `400 Bad Request`: 請求無效 (例如車輛 ID 不存在或玩家不擁有/無法租用該車輛)。
        *   `401 Unauthorized`: 未認證。
        *   `404 Not Found`: 車輛 ID 不存在於 `vehicles` 集合。
        *   `403 Forbidden`: 玩家無權使用該車輛 (例如等級不夠，或車輛正被用於其他活躍會話)。
        *   `500 Internal Server Error`: 伺服器錯誤。
    *   **用戶認證:** 需要

---

### 1.3 貨物選擇 (Cargo Selection)

*   **1.3.1 獲取玩家倉庫貨物列表**
    *   **HTTP 方法:** `GET`
    *   **路徑:** `/api/v1/player/warehouse/items`
    *   **用途:** 獲取玩家倉庫中的物品/貨物列表。
    *   **請求參數:**
        *   `category` (查詢參數, 可選, string): 篩選貨物類別。
        *   `sort_by` (查詢參數, 可選, string): 排序欄位，例如 `name`, `quantity`。預設 `name`。
        *   `order` (查詢參數, 可選, string): `asc` (預設) 或 `desc`。
    *   **請求體:** 無
    *   **回應體 (成功: 200 OK):**
        ```json
        {
          "items": [
            {
              "item_id": "string (ObjectId)", // 物品定義 ID (items._id)
              "name": "string",
              "description": "string",
              "weight_per_unit": "float", // 每單位重量
              "volume_per_unit": "float", // 每單位體積
              "quantity_in_warehouse": "integer" // 倉庫中數量
            }
            // ... 其他物品
          ]
        }
        ```
    *   **回應體 (錯誤):**
        *   `401 Unauthorized`: 未認證。
        *   `500 Internal Server Error`: 伺服器錯誤。
    *   **用戶認證:** 需要

*   **1.3.2 選擇/修改遊戲會話貨物**
    *   **HTTP 方法:** `PUT`
    *   **路徑:** `/api/v1/player/game_session/cargo`
    *   **用途:** 允許玩家為當前準備的遊戲會話選擇或修改要運輸的貨物組合。需先選擇車輛。
    *   **請求參數:** 無
    *   **請求體:**
        ```json
        {
          "selected_cargo": [ // 選擇的貨物列表
            {
              "item_id": "string (ObjectId)", // 物品定義 ID (items._id)
              "quantity": "integer" // 選擇的數量
            }
            // ... 其他選擇的貨物
          ]
        }
        ```
    *   **回應體 (成功: 200 OK):**
        ```json
        {
          "message": "Cargo selection updated for game session.",
          "current_cargo_summary": {
            "total_weight": "float",
            "total_volume": "float",
            "items_count": "integer"
          },
          "validation_status": { // 基於當前選擇的車輛
            "vehicle_selected": "boolean",
            "weight_ok": "boolean", // true 如果未超重或未選車
            "volume_ok": "boolean", // true 如果未超容積或未選車
            "exceeds_weight_by": "float", // 如果超重 (正數)
            "exceeds_volume_by": "float"  // 如果超容積 (正數)
          },
          "items_validation": [ // 每個物品的校驗結果
            {
                "item_id": "string (ObjectId)",
                "requested_quantity": "integer",
                "available_in_warehouse": "integer",
                "sufficient_quantity": "boolean"
            }
          ]
        }
        ```
    *   **回應體 (錯誤):**
        *   `400 Bad Request`: 請求無效 (例如物品 ID 不存在、選擇的數量超過倉庫存量、未先選擇車輛)。
        *   `401 Unauthorized`: 未認證。
        *   `404 Not Found`: 某個物品 ID 不存在。
        *   `409 Conflict`: 嚴重衝突，例如嘗試在未選擇車輛時添加貨物（雖然成功回應中也包含此信息，但如果前端未處理，後端可直接拒絕）。
        *   `500 Internal Server Error`: 伺服器錯誤。
    *   **用戶認證:** 需要

---

### 1.4 目的地選擇 (Destination Selection)

*   **1.4.1 獲取可選目的地列表**
    *   **HTTP 方法:** `GET`
    *   **路徑:** `/api/v1/destinations`
    *   **用途:** 獲取可選擇的遊戲目的地列表。
    *   **請求參數:**
        *   `region` (查詢參數, 可選, string): 篩選特定區域的目的地。
        *   `min_distance` (查詢參數, 可選, float): 基於玩家當前位置（如果有的話）的最小距離。
        *   `unlocked_only` (查詢參數, 可選, boolean): `true` (預設) 只顯示玩家已解鎖的, `false` 顯示所有（可能包含未解鎖標記）。
    *   **請求體:** 無
    *   **回應體 (成功: 200 OK):**
        ```json
        {
          "destinations": [
            {
              "destination_id": "string (ObjectId)",
              "name": "string",
              "region": "string",
              "coordinates": { "lat": "float", "lon": "float" },
              "description": "string",
              "is_unlocked": "boolean" // 根據 unlocked_only 和玩家狀態決定
            }
            // ... 其他目的地
          ]
        }
        ```
    *   **回應體 (錯誤):**
        *   `401 Unauthorized`: 如果 `unlocked_only=true` 但未認證。
        *   `500 Internal Server Error`: 伺服器錯誤。
    *   **用戶認證:** `unlocked_only=true` 時需要，否則可選。

*   **1.4.2 選擇遊戲會話目的地**
    *   **HTTP 方法:** `PUT`
    *   **路徑:** `/api/v1/player/game_session/destination`
    *   **用途:** 允許玩家為當前準備的遊戲會話選擇目的地。
    *   **請求參數:** 無
    *   **請求體:**
        ```json
        {
          "destination_id": "string (ObjectId)" // 要選擇的目的地 ID
        }
        ```
    *   **回應體 (成功: 200 OK):**
        ```json
        {
          "message": "Destination selected for game session.",
          "selected_destination": {
            "destination_id": "string (ObjectId)",
            "name": "string",
            "region": "string"
          }
        }
        ```
    *   **回應體 (錯誤):**
        *   `400 Bad Request`: 請求無效 (例如目的地 ID 不存在或玩家未解鎖該目的地)。
        *   `401 Unauthorized`: 未認證。
        *   `403 Forbidden`: 玩家未解鎖該目的地。
        *   `404 Not Found`: 目的地 ID 不存在。
        *   `500 Internal Server Error`: 伺服器錯誤。
    *   **用戶認證:** 需要

---

### 1.5 最終確認與開始遊戲 (Final Confirmation & Start Game)

*   **1.5.1 獲取遊戲會話設定總覽與任務確認**
    *   **HTTP 方法:** `GET`
    *   **路徑:** `/api/v1/player/game_session/summary`
    *   **用途:** 獲取當前所有已選設定（車輛、貨物、目的地）的摘要，並列出相關的任務及其狀態。
    *   **請求參數:** 無
    *   **請求體:** 無
    *   **回應體 (成功: 200 OK):**
        ```json
        {
          "session_summary": {
            "selected_vehicle": { // 可能為 null
              "vehicle_id": "string (ObjectId)",
              "name": "string",
              "max_load_weight": "float",
              "max_load_volume": "float"
            },
            "selected_cargo": { // items 數組可能為空
              "items": [
                {
                  "item_id": "string (ObjectId)",
                  "name": "string",
                  "quantity": "integer",
                  "weight_per_unit": "float",
                  "volume_per_unit": "float"
                }
              ],
              "total_weight": "float",
              "total_volume": "float"
            },
            "selected_destination": { // 可能為 null
              "destination_id": "string (ObjectId)",
              "name": "string",
              "region": "string"
            }
          },
          "related_tasks": [ // 基於當前設定，篩選出相關的已接受任務
            {
              "player_task_id": "string (ObjectId)",
              "task_id": "string (ObjectId)",
              "title": "string",
              "status": "accepted", // 或 "pending_confirmation"
              "is_completable_with_current_setup": "boolean", // 根據當前設定判斷任務是否可完成
              "completion_issues": ["string"] // 如果不可完成，列出原因，例如 "貨物不足: 鐵礦石", "目的地不符"
            }
          ],
          "can_start_game": "boolean", // 綜合判斷是否滿足開始遊戲的基本條件 (例如：已選車輛、目的地，貨物不超載)
          "start_game_warnings": ["string"] // 例如 "部分任務因當前配置無法完成"
        }
        ```
    *   **回應體 (錯誤):**
        *   `401 Unauthorized`: 未認證。
        *   `404 Not Found`: 玩家沒有進行中的遊戲會話設定 (例如，`players.current_game_session_setup` 為空或不存在)。
        *   `500 Internal Server Error`: 伺服器錯誤。
    *   **用戶認證:** 需要

*   **1.5.2 開始遊戲**
    *   **HTTP 方法:** `POST`
    *   **路徑:** `/api/v1/player/game_session/start`
    *   **用途:** 玩家最終確認所有設定後，正式開始遊戲。
    *   **請求參數:** 無
    *   **請求體:** (可選，如果需要前端再次確認某些事項，例如明確哪些任務要帶入本次會話)
        ```json
        {
          "confirmed_player_task_ids": ["string (ObjectId)"] // 玩家確認要在此次遊戲中執行的 player_task_id 列表
        }
        ```
    *   **回應體 (成功: 200 OK):**
        ```json
        {
          "message": "Game session started successfully!",
          "game_session_id": "string (ObjectId)", // 新創建的正式遊戲會話 ID
          "status": "in_progress",
          "start_time": "string (ISO 8601 DateTime)"
        }
        ```
    *   **回應體 (錯誤):**
        *   `400 Bad Request`: 最終校驗失敗 (例如未選擇車輛/目的地、貨物超載、倉庫貨物不足以扣減、選擇的任務與當前設定衝突)。
        *   `401 Unauthorized`: 未認證。
        *   `409 Conflict`: 玩家已有正在進行的遊戲會話 (`players.active_game_session_id` 已存在)。
        *   `500 Internal Server Error`: 伺服器錯誤。
    *   **用戶認證:** 需要

---

## 2. 資料庫集合與欄位設計 (MongoDB風格)

### 2.1 `players` 集合
*   **用途:** 存儲玩家基本信息及遊戲前設定的臨時選擇。
*   **欄位:**
    *   `_id`: ObjectId (主鍵)
    *   `username`: String (玩家用戶名，唯一，索引)
    *   `email`: String (玩家郵箱，唯一，索引)
    *   `hashed_password`: String (加密後的密碼)
    *   `created_at`: DateTime (帳號創建時間)
    *   `updated_at`: DateTime (帳號信息更新時間)
    *   `last_login_at`: DateTime (上次登錄時間)
    *   `experience_points`: Integer (經驗值, 預設 0)
    *   `level`: Integer (等級, 根據經驗值計算, 可冗餘存儲)
    *   `currency_balance`: Integer (貨幣餘額, 預設 0)
    *   `current_game_session_setup`: Embedded Object (遊戲前設定的臨時選擇, 可為 null)
        *   `selected_vehicle_id`: ObjectId (參照 `vehicles._id`, 可選)
        *   `selected_cargo`: Array of Embedded Objects (可選, 結構: `{ item_id: ObjectId, quantity: Integer }`)
            *   `item_id`: ObjectId (參照 `items._id`)
            *   `quantity`: Integer
        *   `selected_destination_id`: ObjectId (參照 `destinations._id`, 可選)
        *   `last_updated_at`: DateTime (此設定的最後更新時間)
    *   `active_game_session_id`: ObjectId (參照 `game_sessions._id`, 如果玩家正在遊戲中, 可選, 唯一索引（允許null）可防止一個玩家同時有多個活躍會話)

### 2.2 `vehicles` 集合 (車輛定義)
*   **用途:** 存儲遊戲中所有車輛的靜態定義。
*   **欄位:**
    *   `_id`: ObjectId (主鍵)
    *   `name`: String (車輛名稱, 唯一)
    *   `type`: String (車輛類型，例如：卡車、貨車、拖車)
    *   `description`: String (車輛描述)
    *   `max_load_weight`: Float (最大載重，單位：公斤)
    *   `max_load_volume`: Float (最大容積，單位：立方米)
    *   `base_price`: Integer (購買價格，如果可購買)
    *   `rental_price_per_session`: Integer (每次會話租賃價格，如果可租賃)
    *   `availability_type`: String (例如：`purchasable`, `rentable_per_session`, `event_specific`, `level_unlock`)
    *   `required_level_to_unlock`: Integer (解鎖所需玩家等級, 可選, 預設 1)
    *   `icon_url`: String (車輛圖標URL, 可選)
    *   `image_url`: String (車輛大圖URL, 可選)

### 2.3 `player_owned_vehicles` 集合
*   **用途:** 記錄玩家擁有的車輛實例。如果車輛無需實例化（例如所有同型號車輛屬性一致），此集合可省略，直接通過 `players` 內數組記錄擁有的 `vehicle_id`。此處假設車輛可實例化。
*   **欄位:**
    *   `_id`: ObjectId (主鍵)
    *   `player_id`: ObjectId (參照 `players._id`, 索引)
    *   `vehicle_definition_id`: ObjectId (參照 `vehicles._id`)
    *   `nickname`: String (玩家給車輛取的暱稱, 可選)
    *   `purchase_date`: DateTime (購買日期)
    *   `last_used_time`: DateTime (上次使用時間, 可選)
    *   `current_condition`: Float (車輛當前狀況, 0.0 - 1.0, 可選, 預設 1.0)
    *   `is_in_active_session`: Boolean (是否正在活躍的遊戲會話中使用, 預設 false)

### 2.4 `items` 集合 (貨物定義)
*   **用途:** 存儲遊戲中所有物品/貨物的靜態定義。
*   **欄位:**
    *   `_id`: ObjectId (主鍵)
    *   `name`: String (物品名稱, 唯一)
    *   `description`: String (物品描述)
    *   `category`: String (物品類別，例如：電子產品、建材、食品、貴重品)
    *   `weight_per_unit`: Float (每單位重量，單位：公斤)
    *   `volume_per_unit`: Float (每單位體積，單位：立方米)
    *   `base_value_per_unit`: Integer (每單位基礎價值，用於計算獎勵或售價)
    *   `is_fragile`: Boolean (是否易碎, 預設 false)
    *   `is_perishable`: Boolean (是否易腐爛, 預設 false)
        *   `spoil_duration_hours`: Integer (腐爛時長（小時）, 如果 `is_perishable` 為 true, 可選)
    *   `required_permit_type`: String (運輸所需許可證類型, 可選)
    *   `icon_url`: String (物品圖標URL, 可選)

### 2.5 `player_warehouse_items` 集合 (玩家倉庫)
*   **用途:** 記錄玩家倉庫中擁有的物品及其數量。
*   **欄位:**
    *   `_id`: ObjectId (主鍵)
    *   `player_id`: ObjectId (參照 `players._id`)
    *   `item_id`: ObjectId (參照 `items._id`)
    *   `quantity`: Integer (擁有數量, 必須 >= 0)
    *   `last_updated_at`: DateTime (上次更新時間)
    *   **索引:** (`player_id`, `item_id`) 應為唯一複合索引。

### 2.6 `tasks` 集合 (任務定義)
*   **用途:** 存儲遊戲中所有任務的靜態定義。
*   **欄位:**
    *   `_id`: ObjectId (主鍵)
    *   `title`: String (任務標題, 唯一)
    *   `description`: String (任務詳細描述)
    *   `mode`: String (任務模式，例如：`daily`, `story`, `special_event`)
    *   `requirements`: Embedded Object (任務完成條件)
        *   `required_player_level`: Integer (最低玩家等級, 可選, 預設 1)
        *   `deliver_items`: Array of Embedded Objects (需要運送的特定物品, 可選)
            *   `item_id`: ObjectId (參照 `items._id`)
            *   `quantity`: Integer
        *   `pickup_location_id`: ObjectId (取貨地點, 參照 `destinations._id`, 可選)
        *   `destination_id`: ObjectId (必須送達的目的地, 參照 `destinations._id`, 可選)
        *   `required_vehicle_type`: String (需要使用的特定車輛類型, 可選, 參照 `vehicles.type`)
        *   `time_limit_seconds`: Integer (限時（秒）, 可選)
        *   `min_cargo_value`: Integer (最低貨物總價值, 可選)
    *   `rewards`: Embedded Object (任務獎勵)
        *   `experience_points`: Integer
        *   `currency`: Integer
        *   `item_rewards`: Array of Embedded Objects (物品獎勵, 可選)
            *   `item_id`: ObjectId (參照 `items._id`)
            *   `quantity`: Integer
        *   `unlock_vehicle_ids`: Array of ObjectId (解鎖車輛, 參照 `vehicles._id`, 可選)
        *   `unlock_destination_ids`: Array of ObjectId (解鎖目的地, 參照 `destinations._id`, 可選)
    *   `is_repeatable`: Boolean (是否可重複, 預設 false)
        *   `repeat_cooldown_hours`: Integer (如果可重複，冷卻時間（小時）, 可選)
    *   `availability_start_date`: DateTime (任務可用開始時間, 可選)
    *   `availability_end_date`: DateTime (任務可用結束時間, 可選, 用於限時任務)
    *   `prerequisite_task_ids`: Array of ObjectId (前置任務ID列表, 參照 `tasks._id`, 可選)
    *   `is_active`: Boolean (任務是否啟用, 預設 true)

### 2.7 `player_tasks` 集合 (玩家任務記錄)
*   **用途:** 記錄玩家接受的任務及其狀態和進度。
*   **欄位:**
    *   `_id`: ObjectId (主鍵)
    *   `player_id`: ObjectId (參照 `players._id`, 索引)
    *   `task_id`: ObjectId (參照 `tasks._id`, 索引)
    *   `status`: String (任務狀態，例如：`accepted`, `in_progress_linked_to_session`, `completed`, `failed`, `abandoned`)
    *   `accepted_at`: DateTime (接受任務時間)
    *   `linked_game_session_id`: ObjectId (如果任務與某個遊戲會話關聯, 參照 `game_sessions._id`, 可選)
    *   `progress`: Embedded Object (任務進度詳情, 結構依賴任務類型, 可選)
        *   `items_delivered_count`: Array of Embedded Objects (`{ item_id: ObjectId, delivered_quantity: Integer }`)
        *   `distance_traveled_for_task`: Float
    *   `completed_at`: DateTime (完成任務時間, 可選)
    *   `failed_at`: DateTime (失敗時間, 可選)
    *   `abandoned_at`: DateTime (放棄時間, 可選)
    *   `last_updated_at`: DateTime (記錄更新時間)
    *   **索引:** (`player_id`, `task_id`, `status`) 可考慮，用於快速查詢玩家特定狀態的任務。

### 2.8 `destinations` 集合 (地點定義)
*   **用途:** 存儲遊戲中所有可選的目的地/地點。
*   **欄位:**
    *   `_id`: ObjectId (主鍵)
    *   `name`: String (地點名稱, 唯一)
    *   `description`: String (地點描述)
    *   `region`: String (所屬區域/城市)
    *   `coordinates`: Embedded Object (地理坐標, GeoJSON Point 格式更佳)
        *   `type`: String (固定為 "Point")
        *   `coordinates`: Array of Float (`[longitude, latitude]`)
    *   `is_unlocked_by_default`: Boolean (是否默認解鎖, 預設 true)
    *   `unlock_requirements`: Embedded Object (解鎖條件, 如果 `is_unlocked_by_default` 為 false, 可選)
        *   `required_player_level`: Integer
        *   `required_completed_task_id`: ObjectId (參照 `tasks._id`)
    *   `available_services`: Array of String (地點提供的服務, 例如：`fuel_station`, `repair_shop`, `market`, `cargo_pickup`, `cargo_dropoff`)
    *   `icon_url`: String (地點圖標URL, 可選)

### 2.9 `game_sessions` 集合 (正式遊戲會話)
*   **用途:** 存儲玩家正式開始的遊戲會話記錄。
*   **欄位:**
    *   `_id`: ObjectId (主鍵)
    *   `player_id`: ObjectId (參照 `players._id`, 索引)
    *   `used_vehicle_id`: ObjectId (參照 `vehicles._id` 或 `player_owned_vehicles._id`，取決於車輛管理方式)
    *   `vehicle_snapshot`: Embedded Object (車輛信息快照)
        *   `name`: String
        *   `type`: String
        *   `max_load_weight`: Float
        *   `max_load_volume`: Float
    *   `cargo_snapshot`: Array of Embedded Objects (開始遊戲時的貨物快照)
        *   `item_id`: ObjectId (參照 `items._id`)
        *   `name`: String (物品名稱快照)
        *   `quantity`: Integer
        *   `weight_per_unit`: Float
        *   `volume_per_unit`: Float
        *   `base_value_per_unit`: Integer
    *   `total_cargo_weight_at_start`: Float
    *   `total_cargo_volume_at_start`: Float
    *   `destination_id`: ObjectId (參照 `destinations._id`, 本次會話的目的地)
    *   `destination_snapshot`: Embedded Object (目的地信息快照)
        *   `name`: String
        *   `region`: String
    *   `associated_player_task_ids`: Array of ObjectId (本次會話關聯的玩家任務記錄ID, 參照 `player_tasks._id`)
    *   `start_time`: DateTime (遊戲會話開始時間)
    *   `end_time`: DateTime (遊戲會話結束時間, 可選)
    *   `status`: String (會話狀態，例如：`in_progress`, `completed_success`, `completed_failed_cargo_lost`, `completed_failed_time_out`, `abandoned_by_player`)
    *   `outcome_summary`: Embedded Object (遊戲結果詳情, 會話結束時填寫, 可選)
        *   `distance_traveled_km`: Float
        *   `time_taken_seconds`: Integer
        *   `cargo_delivered_value`: Integer
        *   `cargo_damage_percentage`: Float (0.0 - 1.0)
        *   `earned_experience`: Integer
        *   `earned_currency`: Integer
        *   `penalties`: Integer (罰款)
    *   `last_updated_at`: DateTime (記錄更新時間)

---

### 欄位間參照關係與索引建議:

*   **`players`**:
    *   索引: `username`, `email`, `active_game_session_id` (unique, sparse if allowing null)
*   **`player_owned_vehicles`**:
    *   索引: `player_id`, (`player_id`, `vehicle_definition_id`)
*   **`player_warehouse_items`**:
    *   索引: (`player_id`, `item_id`) (unique)
*   **`tasks`**:
    *   索引: `mode`, `is_active`
*   **`player_tasks`**:
    *   索引: `player_id`, `task_id`, (`player_id`, `status`), `linked_game_session_id`
*   **`destinations`**:
    *   索引: `region`, `coordinates` (2dsphere for geo-queries)
*   **`game_sessions`**:
    *   索引: `player_id`, (`player_id`, `status`)

---

此設計旨在提供一個相對完整且嚴謹的基礎，您可以根據實際的遊戲複雜度和特定需求進行調整和擴展。
