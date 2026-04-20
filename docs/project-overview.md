# TestFlow 详细说明

本文档包含项目的完整技术说明，从根目录 `README.md` 迁移。根目录 README 保留入口级信息，详细运行、API、节点和发布说明集中维护在这里。

## 技术栈

### 后端

| 组件 | 技术 | 说明 |
|------|------|------|
| Web 框架 | FastAPI | 现代 Python Web 框架，异步支持 |
| ORM | SQLAlchemy + aiosqlite | 异步 ORM 与 SQLite 数据库 |
| SSH 连接 | Paramiko | SSH 远程连接 |
| 系统监控 | psutil | CPU/内存/磁盘信息采集 |
| 数据验证 | Pydantic | 数据验证与序列化 |

### 前端

| 组件 | 技术 | 说明 |
|------|------|------|
| 框架 | Vue 3 | 组合式 API |
| 类型 | TypeScript | 类型安全 |
| 构建 | Vite | 快速构建工具 |
| UI | Element Plus | UI 组件库 |
| 工作流编辑 | Vue Flow | 可视化拖拽编辑器 |
| 状态管理 | Pinia | Vue 3 官方推荐 |
| 路由 | Vue Router | SPA 路由管理 |

## 项目结构

```
.
├── backend/
│   ├── app/
│   │   ├── api/           # API 路由 (servers, workflows, executions, monitoring, settings, iotdb)
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
├── docs/                  # 项目文档中心
├── manage.sh              # Mac/Linux 启动脚本
├── manage.bat             # Windows 启动脚本
├── manage.py              # 服务管理和发布包构建脚本
└── README.md              # 项目入口
```

## 运行管理

### 环境要求

- Python 3.10+
- Node.js 18+（包含 npm）

### 启动服务

Mac/Linux:

```bash
./manage.sh install
./manage.sh start
./manage.sh status
```

Windows:

```bat
manage.bat install
manage.bat start
manage.bat status
```

首次部署建议先执行 `install` 检查 Python / Node.js 环境并安装依赖。之后执行 `start` 启动服务；`start` 和 `restart` 会自动补齐缺失的后端和前端依赖。

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

### 基础节点

| 类型 | 功能 | 配置参数 |
|------|------|----------|
| shell | 执行 Shell 命令 | command, server_id, timeout, retry |
| upload | SFTP 上传文件 | local_path, remote_path, server_id |
| download | SFTP 下载文件 | remote_path, local_path, server_id |
| config | 替换配置变量 | file_path, replacements, server_id |
| log_view | 查看日志内容 | file_path, lines, server_id |

### IoTDB 专用节点

| 类型 | 功能 | 配置参数 |
|------|------|----------|
| iotdb_deploy | 部署 IoTDB | version, install_path, server_id, config_template |
| iotdb_start | 启动服务 | server_id, wait_port, timeout |
| iotdb_stop | 停止服务 | server_id, graceful |
| iotdb_cli | 执行 CLI 命令 | commands, server_id, timeout |
| iotdb_config | 应用配置模板 | template_name, server_id |

### 集群节点

| 类型 | 功能 |
|------|------|
| iotdb_cluster_deploy | 集群部署 |
| iotdb_cluster_start | 集群启动 |
| iotdb_cluster_check | 集群检查 |
| iotdb_cluster_stop | 集群停止 |

### 控制节点

| 类型 | 功能 | 配置参数 |
|------|------|----------|
| condition | if/else 分支 | expression, true_branch, false_branch |
| loop | for/while 循环 | loop_type, iterations, condition |
| wait | 等待条件满足 | condition, timeout, interval |
| parallel | 并行执行节点 | nodes, max_concurrent |
| assert | 检查条件 | assert_type, params, expected |

### 断言类型

- `log_contains`: 日志包含关键词
- `port_open`: 端口是否监听
- `process_running`: 进程是否存在
- `file_exists`: 文件是否存在
- `command_output`: 命令输出匹配

### 结果节点

| 类型 | 功能 | 配置参数 |
|------|------|----------|
| report | 生成测试报告 | format, include_logs |
| summary | 汇总断言结果 | 无 |
| notify | 发送通知 | type, recipient, template |

## 设计文档

详细设计文档位于 `docs/design/`：

| 文档 | 内容 |
|------|------|
| [pages/app-shell/ui-layout.md](design/pages/app-shell/ui-layout.md) | 主布局、页面高度、首页 UI |
| [pages/servers/region-scheduling.md](design/pages/servers/region-scheduling.md) | Region 字段、区域调度 |
| [pages/workflows/editor.md](design/pages/workflows/editor.md) | Vue Flow 编辑器、节点类型 |
| [pages/workflows/execution-engine.md](design/pages/workflows/execution-engine.md) | ExecutionEngine、状态管理 |
| [pages/workflows/iot-benchmark-async-node.md](design/pages/workflows/iot-benchmark-async-node.md) | IoT Benchmark 异步节点 |
| [pages/iotdb/visualization.md](design/pages/iotdb/visualization.md) | IoTDB CLI、日志和配置 |
| [pages/monitoring/service.md](design/pages/monitoring/service.md) | 本地/远程监控服务 |
| [shared/backend-architecture.md](design/shared/backend-architecture.md) | FastAPI 架构 |
| [shared/frontend-architecture.md](design/shared/frontend-architecture.md) | Vue 3 架构 |
| [shared/ssh-service.md](design/shared/ssh-service.md) | SSH 连接、执行和文件传输 |
| [shared/release-runtime.md](design/shared/release-runtime.md) | 发布包结构和跨平台运行脚本 |

## 开发与测试

### 后端测试

```bash
cd backend
.venv/bin/python -m pytest tests/ -v
```

测试覆盖详情见 [testing/backend-tests-summary.md](testing/backend-tests-summary.md)。

### 前端构建

```bash
cd frontend
npm run build
```

## 发布打包

如果你希望基于当前代码生成一个可交付目录，可以执行：

```bash
./manage.sh release
```

Windows 可执行：

```bat
manage.bat release
```

命令会先执行前端构建，再把运行所需文件收集到 `release/仓库-版本/` 下，并生成带同名顶层文件夹的 `release/仓库-版本.zip`。默认版本基于最近 Git tag 生成，例如最近版本为 `0.2` 时生成 `test-by-ai-0.2-snapshot-20260420`；如需生成正式版本，可执行：

```bash
./manage.sh release --version 0.1.0
```

发布包默认包含：

- `backend/app/` 与 `backend/requirements.txt`
- 构建后的前端产物 `backend/app/frontend_dist/`
- 发布包专用的 `manage.py`、`manage.sh`、`manage.bat`
- `README.md`
- `RELEASE_INFO.txt`
- `data/app.db`

发布包默认不包含：

- `venv/`
- `frontend/src/` 和前端配置文件
- `frontend/node_modules/`
- `data/logs/` 里的运行日志

---

最后更新: 2026-04-20
