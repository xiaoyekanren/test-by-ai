# 后端架构设计

## 概述

IoTDB 测试自动化平台后端采用 FastAPI + SQLAlchemy 架构，提供服务器管理、工作流编排、执行引擎、系统监控等核心功能。

## 技术架构

### 技术栈

| 组件 | 技术 | 版本要求 |
|------|------|----------|
| Web 框架 | FastAPI | - |
| ORM | SQLAlchemy | - |
| 数据库 | SQLite (aiosqlite) | - |
| SSH 连接 | Paramiko | - |
| 系统监控 | psutil | - |
| 数据验证 | Pydantic | - |

### 组件结构

```
backend/app/
├── main.py          # FastAPI 应用入口、路由注册、生命周期管理
├── config.py        # 配置管理（数据库路径）
├── dependencies.py  # 依赖注入（数据库会话）
├── api/             # API 路由层
│   ├── servers.py   # 服务器 CRUD + SSH 测试 + 命令执行
│   ├── workflows.py # 工作流 CRUD
│   ├── executions.py # 执行管理 + 后台任务
│   ├── monitoring.py # 本地/远程监控
│   ├── settings.py  # 系统设置
│   └── iotdb.py     # IoTDB 可视化（CLI/日志/配置）
├── models/          # 数据库模型
│   ├── database.py  # ORM 模型定义
│   └── setup.py     # 数据库初始化
├── schemas/         # Pydantic 数据模型
│   ├── server.py    # ServerCreate/Update/Response
│   ├── workflow.py  # WorkflowCreate/Update + Node/Edge 定义
│   ├── execution.py # Execution 相关 schema
│   └── settings.py  # 设置相关 schema
└── services/        # 业务逻辑层
    ├── ssh_service.py      # SSH 连接、命令执行、文件传输
    ├── execution_engine.py # 向后兼容 facade，导出 ExecutionEngine
    ├── execution/          # 工作流执行引擎实现（engine + mixins + handlers）
    │   ├── engine.py       # 核心编排、CRUD、execute_workflow
    │   ├── graph.py        # DAG 构建、拓扑排序、执行快照
    │   ├── node_dispatch.py # 节点分发、worker session
    │   ├── server_resolution.py # 区域调度、空闲服务器解析
    │   ├── context.py      # 上下文合并与传播
    │   ├── utils.py        # SSH 结果、路径和属性替换等工具
    │   └── handlers/       # 按节点域拆分的执行器
    └── monitoring_service.py # 系统监控服务
```

### 数据流

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Frontend  │────▶│   API层     │────▶│  Service层  │
│  (Vue 3)    │     │ (FastAPI)   │     │ (业务逻辑)   │
└─────────────┘     └─────────────┘     └─────────────┘
                          │                    │
                          ▼                    ▼
                    ┌─────────────┐     ┌─────────────┐
                    │  Schemas    │     │   Models    │
                    │ (Pydantic)  │     │ (SQLAlchemy)│
                    └─────────────┘     └─────────────┘
                                              │
                                              ▼
                                        ┌─────────────┐
                                        │   SQLite    │
                                        └─────────────┘
```

## 数据模型

### 核心实体

| 模型 | 描述 | 主要字段 |
|------|------|----------|
| Server | SSH 服务器配置 | id, name, host, port, username, password, status, tags |
| Workflow | 工作流定义 | id, name, nodes(JSON), edges(JSON), variables(JSON) |
| Execution | 执行记录 | id, workflow_id, status, trigger_type, duration, result |
| NodeExecution | 节点执行记录 | id, execution_id, node_id, status, output_data, error_message |
| SystemSetting | 系统设置 | id, key, value(JSON) |

### 实体关系

```
Workflow ──┬──▶ Execution (1:N)
           │
Execution ─┬──▶ NodeExecution (1:N)
           │
Server     ──── 独立实体（被节点配置引用）
```

## API 路由设计

### 路由前缀

| 路由前缀 | 功能模块 | 标签 |
|----------|----------|------|
| `/api/servers` | 服务器管理 | servers |
| `/api/workflows` | 工作流管理 | workflows |
| `/api/executions` | 执行管理 | executions |
| `/api/monitoring` | 系统监控 | monitoring |
| `/api/settings` | 系统设置 | settings |
| `/api/iotdb` | IoTDB 可视化 | iotdb |

### 服务器管理 API

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/` | 获取服务器列表 |
| POST | `/` | 创建服务器 |
| GET | `/{id}` | 获取单个服务器 |
| PUT | `/{id}` | 更新服务器 |
| DELETE | `/{id}` | 删除服务器 |
| POST | `/{id}/test` | SSH 连接测试 |
| POST | `/{id}/execute` | 执行远程命令 |

### 工作流管理 API

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/` | 获取工作流列表 |
| POST | `/` | 创建工作流 |
| GET | `/{id}` | 获取单个工作流 |
| PUT | `/{id}` | 更新工作流 |
| DELETE | `/{id}` | 删除工作流（含关联执行记录） |

### 执行管理 API

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/` | 获取执行列表（支持筛选） |
| POST | `/` | 创建执行并启动后台任务 |
| GET | `/{id}` | 获取执行详情 |
| POST | `/{id}/stop` | 停止执行 |
| DELETE | `/{id}` | 删除执行记录 |
| GET | `/{id}/nodes` | 获取节点执行记录 |

## 设计决策

### 异步执行策略

**决策**: 使用 FastAPI BackgroundTasks 执行工作流，而非独立进程池。

**原因**: 
- 简化部署，无需额外的进程管理
- 适合中小规模测试场景
- 执行状态通过数据库持久化

### SSH 连接管理

**决策**: 每次操作建立新连接，不维护连接池。

**原因**:
- 减少连接状态管理复杂度
- 适合间歇性操作场景
- 支持多端口尝试（22 + 配置端口）

### JSON 字段存储

**决策**: nodes、edges、variables 使用 JSON 字段存储。

**原因**:
- 灵活的节点类型扩展
- 无需预定义表结构
- SQLite 支持 JSON 查询

## 未来规划

- [ ] 添加执行日志持久化存储
- [ ] 支持定时执行（调度器）
- [ ] 添加 WebSocket 实时推送执行状态
- [ ] 支持分布式执行（多节点并发）

---

最后更新: 2026-04-20
