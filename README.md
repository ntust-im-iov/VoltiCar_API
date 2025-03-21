# 电动汽车充电站 API

基于FastAPI的电动汽车充电站管理和用户充电记录系统。

## 功能

- 用户管理：注册、登录、认证
- 充电站管理：查询、创建充电站
- 充电记录：记录用户充电活动并计算碳积分

## 技术栈

- **FastAPI**：现代、高性能的Python Web框架
- **MongoDB**：NoSQL数据库存储用户和充电站信息
- **JWT认证**：安全的基于令牌的认证系统
- **Pydantic**：数据验证和设置管理
- **Docker**：容器化部署支持

## 项目结构

```
my_fastapi_project/
│
├── app/                    # 应用主目录
│   ├── api/                # API路由
│   │   ├── __init__.py     # API路由初始化
│   │   ├── user_routes.py  # 用户相关路由
│   │   └── station_routes.py # 充电站相关路由
│   │
│   ├── database/           # 数据库连接
│   │   └── mongodb.py      # MongoDB连接配置
│   │
│   ├── models/             # 数据模型
│   │   ├── user.py         # 用户模型
│   │   └── station.py      # 充电站模型
│   │
│   └── utils/              # 工具函数
│       ├── auth.py         # 认证工具
│       └── helpers.py      # 辅助函数
│
├── Dockerfile              # Docker构建文件
├── docker-compose.yml      # Docker Compose配置
├── docker-compose.production.yml # 生产环境配置
├── .env                    # 环境变量配置
├── main.py                 # 应用入口
└── requirements.txt        # 项目依赖
```

## 安装与运行

### 本地运行

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 运行应用：

```bash
python main.py
```

### 使用Docker部署

1. 通过Docker Compose启动应用：

```bash
docker-compose up -d
```

这将构建API镜像并启动API容器。API将连接到外部MongoDB数据库（59.126.6.46:27017）。

2. 查看运行中的容器：

```bash
docker-compose ps
```

3. 停止服务：

```bash
docker-compose down
```

### 生产环境部署

使用生产环境配置文件启动：

```bash
docker-compose -f docker-compose.production.yml up -d
```

或使用提供的启动脚本：

```bash
./startup.sh production
```

## 环境变量

在`.env`文件或Docker环境变量中配置：

- `DATABASE_URL`: MongoDB连接URL（默认指向59.126.6.46:27017）
- `VOLTICAR_DB`: Volticar数据库名
- `CHARGE_STATION_DB`: 充电站数据库名
- `SECRET_KEY`: JWT认证密钥
- `API_HOST`: API主机地址
- `API_PORT`: API端口

## API端点

### 用户API

- `POST /users`：创建新用户
- `POST /users/token`：用户登录获取令牌
- `GET /users/me`：获取当前用户信息
- `GET /users/{user_id}`：获取指定用户信息
- `POST /users/{user_id}/charge`：记录充电活动

### 充电站API

- `GET /stations`：获取所有充电站
- `GET /stations/{station_id}`：获取指定充电站
- `GET /stations/city/{city}`：获取指定城市的充电站（支持中文城市名）
- `POST /stations`：创建新充电站

### 健康检查

- `GET /health`: 检查API服务状态 