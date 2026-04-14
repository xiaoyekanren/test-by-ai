# IoTDB Test Automation Platform

一个用于 IoTDB 测试自动化平台，提供服务器管理、可视化工作流编排与执行、实时监控等功能。

## 功能概览

- **服务器管理**: 服务器增删改查、SSH 连接测试、标签分组
- **工作流编辑器**: 可视化拖拽节点、连线设计测试流程
- **工作流执行引擎**: 支持并发执行、实时状态追踪
- **实时监控**: CPU / 内存 / 磁盘 / 网络信息采集
- **SSH 远程执行**: 通过 SSH 在远程服务器执行测试任务
- **执行洞察**: 查看执行历史、日志、统计分析

## 页面入口

| 路径 | 功能 |
|------|------|
| `/servers` | 服务器管理 |
| `/workflows` | 工作流列表 |
| `/workflows/:id/edit` | 编辑工作流 |
| `/executions` | 执行洞察与历史 |
| `/monitor` | 实时监控面板 |
| `/iotdb` | IoTDB 可视化 |
| `/settings` | 系统设置 |

## 技术栈

### 后端

- **FastAPI** - 现代 Python Web 框架
- **SQLAlchemy + aiosqlite** - 异步 ORM 与 SQLite 数据库
- **Paramiko** - SSH 远程连接
- **psutil** - 系统监控数据采集
- **Pydantic** - 数据验证与序列化

### 前端

- **Vue 3** - 渐进式 JavaScript 框架
- **TypeScript** - 类型安全
- **Vite** - 快速构建工具
- **Element Plus** - UI 组件库
- **Vue Flow** - 工作流可视化编辑器
- **Pinia** - 状态管理
- **Vue Router** - 路由管理

## 项目结构

```
.
├── backend/
│   ├── app/
│   │   ├── api/           # API 路由 (servers, workflows, executions, monitoring, settings)
│   │   ├── models/        # 数据库模型
│   │   ├── schemas/       # Pydantic 数据模型
│   │   ├── services/      # 业务逻辑 (execution_engine, monitoring, ssh)
│   │   ├── config.py      # 配置
│   │   └── main.py        # FastAPI 应用入口
│   ├── tests/             # pytest 测试
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── api/           # API 调用封装
│   │   ├── components/    # UI 组件 (layout, workflow)
│   │   ├── stores/        # Pinia 状态管理
│   │   ├── views/         # 页面视图
│   │   ├── router/        # 路由配置
│   │   ├── types/         # TypeScript 类型定义
│   │   └── main.ts        # 应用入口
│   ├── package.json
│   └── vite.config.ts
│
├── docs/                         # 项目文档中心
└── README.md                     # 项目入口与快速开始
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+

### 启动服务

**Mac/Linux:**

```bash
./manage.sh install
./manage.sh start
```

**Windows:**

```bash
manage.bat start
```

首次部署建议先执行 `./manage.sh install` 检查 Python / Node.js 环境并安装依赖；之后执行 `./manage.sh start` 启动服务。`start` / `restart` 也会自动补齐缺失的后端和前端依赖。脚本会使用满足版本要求的 `python3` 或 `python` 创建虚拟环境，也可以通过 `PYTHON_BIN=/path/to/python ./manage.sh install` 指定 Python。

环境要求：

- Python 3.10+
- Node.js 18+（包含 npm）

### 管理命令

| 命令 | 描述 |
|------|------|
| `start` | 启动所有服务 |
| `stop` | 停止所有服务 |
| `restart` | 重启所有服务 |
| `status` | 查看服务状态 |
| `install` | 安装后端、前端依赖 |
| `check` | 检查环境、项目文件、依赖状态和端口占用 |

### 访问应用

启动成功后访问：

- 前端: `http://localhost:5173`
- API 文档: `http://localhost:8000/docs`

## 核心 API

### 服务器管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/servers` | 服务器列表 |
| POST | `/api/servers` | 新增服务器 |
| GET | `/api/servers/{id}` | 服务器详情 |
| PUT | `/api/servers/{id}` | 更新服务器 |
| DELETE | `/api/servers/{id}` | 删除服务器 |
| POST | `/api/servers/{id}/test` | SSH 连接测试 |

### 工作流管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/workflows` | 工作流列表 |
| POST | `/api/workflows` | 创建工作流 |
| GET | `/api/workflows/{id}` | 工作流详情 |
| PUT | `/api/workflows/{id}` | 更新工作流 |
| DELETE | `/api/workflows/{id}` | 删除工作流 |

### 执行管理

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/executions` | 执行列表 |
| POST | `/api/executions` | 创建执行 |
| GET | `/api/executions/{id}` | 执行详情 |
| GET | `/api/executions/{id}/logs` | 执行日志 |

### 监控

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/monitoring/status` | CPU/内存/磁盘信息 |
| GET | `/api/monitoring/processes` | 进程列表 |
| GET | `/api/monitoring/network` | 网络信息 |

### 设置

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/settings` | 获取设置 |
| PUT | `/api/settings` | 更新设置 |

## 工作流节点类型

工作流编辑器支持多种节点类型，用于构建测试自动化流程：

- **SSH 命令节点** - 在远程服务器执行命令
- **IoTDB 操作节点** - IoTDB 数据库操作
- **数据生成节点** - 生成测试数据
- **条件判断节点** - 根据条件分支执行
- **等待节点** - 延迟执行

## 开发与测试

### 运行后端测试

```bash
cd backend
pytest
```

### 前端构建

```bash
cd frontend
npm run build
```

## 开发规范

### 文档更新要求

**每次更新代码时，必须同步更新相关文档：**

1. **说明文档** - 更新功能说明、使用方法等（优先放在 `docs/` 目录；根 `README.md` 仅保留项目入口）
2. **设计文档** - 更新架构设计、技术决策等（`docs/design/` 目录，没有则创建）

详见 [CLAUDE.md](./CLAUDE.md) 和 [docs/README.md](./docs/README.md)。

## License

MIT
