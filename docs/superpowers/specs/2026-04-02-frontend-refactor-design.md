# IoTDB 测试自动化平台 - 前端重构设计文档

**日期：** 2026-04-02
**状态：** 待审核

---

## 1. 项目概述

### 1.1 项目定位

从"服务器管理系统"升级为 **IoTDB 测试自动化平台**，核心功能：
- 通过可视化工作流设计 IoTDB 测试流程
- 自动执行配置修改、部署、启动、CLI 操作、日志分析
- 支持多种 Linux 操作来判断测试用例执行结果

### 1.2 重构目标

| 目标 | 描述 |
|------|------|
| 提升可维护性 | 组件化架构，代码清晰可扩展 |
| 提升开发效率 | Vue 3 + TypeScript，减少重复代码 |
| 提升用户体验 | 流畅交互，实时执行进度，可视化编辑器 |
| 现代化技术栈 | FastAPI + Vue 3 + Vue Flow |

---

## 2. 技术选型

| 层级 | 技术 | 版本 | 理由 |
|------|------|------|------|
| **后端框架** | FastAPI | 0.100+ | 异步支持、类型安全、自动文档 |
| **数据验证** | Pydantic | 2.x | 与 FastAPI 深度集成 |
| **数据库** | SQLAlchemy + SQLite | 2.x | ORM 支持，保持轻量 |
| **SSH/SFTP** | paramiko | 3.x | 已验证可用，继承现有方案 |
| **前端框架** | Vue 3 | 3.4+ | 组合式 API，国内生态好 |
| **状态管理** | Pinia | 2.x | Vue 3 官方推荐 |
| **路由** | Vue Router | 4.x | SPA 路由管理 |
| **流程图** | Vue Flow | 1.x | Vue 3 专用，拖拽连线内置 |
| **构建工具** | Vite | 5.x | 快速热更新 |
| **语言** | TypeScript | 5.x | 类型安全 |

---

## 3. 项目架构

```
test-by-ai/
├── backend/                          # FastAPI 后端
│   ├── app/
│   │   ├── main.py                   # FastAPI 入口
│   │   ├── config.py                 # 配置管理
│   │   ├── api/                      # API 路由层
│   │   │   ├── router.py             # 总路由聚合
│   │   │   ├── servers.py            # 服务器管理 API
│   │   │   ├── workflows.py          # 工作流 CRUD API
│   │   │   ├── executions.py         # 执行引擎 API
│   │   │   └── monitoring.py         # 监控 API
│   │   ├── services/                 # 业务逻辑层
│   │   │   ├── server_service.py
│   │   │   ├── workflow_service.py
│   │   │   ├── execution_engine.py   # 核心：工作流执行引擎
│   │   │   ├── ssh_service.py
│   │   │   └── monitoring_service.py
│   │   ├── models/                   # SQLAlchemy 数据模型
│   │   │   ├── server.py
│   │   │   ├── workflow.py
│   │   │   ├── execution.py
│   │   │   └── node_execution.py
│   │   ├── schemas/                  # Pydantic 数据验证
│   │   │   ├── server.py
│   │   │   ├── workflow.py
│   │   │   ├── execution.py
│   │   │   └── node.py               # 节点类型定义
│   │   └── utils/
│   │       └── iotdb.py              # IoTDB 专用工具
│   ├── alembic/                      # 数据库迁移
│   └── requirements.txt
│
├── frontend/                         # Vue 3 前端
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.vue
│   │   ├── router/index.ts
│   │   ├── stores/                   # Pinia 状态管理
│   │   │   ├── servers.ts
│   │   │   ├── workflows.ts
│   │   │   ├── executions.ts
│   │   │   └── monitoring.ts
│   │   ├── views/                    # 页面视图
│   │   │   ├── HomeView.vue
│   │   │   ├── ServersView.vue
│   │   │   ├── WorkflowEditorView.vue
│   │   │   ├── ExecutionView.vue
│   │   │   └── MonitoringView.vue
│   │   ├── components/
│   │   │   ├── common/               # 基础组件
│   │   │   │   ├── Sidebar.vue
│   │   │   │   ├── TopBar.vue
│   │   │   │   ├── Modal.vue
│   │   │   │   └── Toast.vue
│   │   │   ├── servers/
│   │   │   ├── workflow/
│   │   │   │   ├── FlowEditor.vue    # Vue Flow 编辑器
│   │   │   │   ├── NodePalette.vue
│   │   │   │   ├── nodes/            # 自定义节点组件
│   │   │   │   │   ├── ShellNode.vue
│   │   │   │   │   ├── IoTDBNode.vue
│   │   │   │   │   ├── ConditionNode.vue
│   │   │   │   │   ├── LoopNode.vue
│   │   │   │   │   └── AssertNode.vue
│   │   │   │   └── ExecutionPanel.vue
│   │   │   └── monitoring/
│   │   ├── composables/              # 组合式函数
│   │   │   ├── useApi.ts
│   │   │   ├── usePolling.ts
│   │   │   ├── useToast.ts
│   │   │   └── useWebSocket.ts
│   │   ├── api/                      # API 客户端
│   │   ├── types/                    # TypeScript 类型定义
│   │   └── styles/
│   ├── vite.config.ts
│   └── package.json
│
├── workflows/                        # YAML 工作流模板
│   ├── templates/
│   └── user/
│
├── data/
│   ├── app.db
│   ├── logs/
│   └── reports/
│
└── docker-compose.yml
```

---

## 4. 数据模型设计

### 4.1 服务器表 (servers)

```python
class Server(Base):
    id: int (PK)
    name: str (unique)
    host: str
    port: int (default 22)
    username: str
    password: str (encrypted)
    description: str
    tags: str (comma separated)
    role: str  # 'test_node' | 'target_node' | 'both'
    status: str  # 'online' | 'offline'
    created_at: datetime
    updated_at: datetime
```

### 4.2 工作流表 (workflows)

```python
class Workflow(Base):
    id: int (PK)
    name: str (unique)
    description: str
    nodes: JSON  # 节点定义列表
    edges: JSON  # 连接关系列表
    variables: JSON  # 全局变量定义
    created_at: datetime
    updated_at: datetime
```

### 4.3 执行记录表 (executions)

```python
class Execution(Base):
    id: int (PK)
    workflow_id: int (FK)
    status: str  # 'pending' | 'running' | 'paused' | 'completed' | 'failed'
    trigger_type: str  # 'manual' | 'scheduled' | 'api'
    triggered_by: str
    started_at: datetime
    finished_at: datetime
    duration: int  # seconds
    result: str  # 'passed' | 'failed' | 'partial'
    summary: JSON  # 统计信息
    created_at: datetime
```

### 4.4 节点执行记录表 (node_executions)

```python
class NodeExecution(Base):
    id: int (PK)
    execution_id: int (FK)
    node_id: str
    node_type: str
    status: str  # 'pending' | 'running' | 'success' | 'failed' | 'skipped'
    started_at: datetime
    finished_at: datetime
    duration: int
    input_data: JSON
    output_data: JSON
    log_path: str  # 日志文件路径
    error_message: str
    retry_count: int
```

---

## 5. 工作流节点类型

### 5.1 基础节点

| 类型 | 节点 ID | 功能 | 配置参数 |
|------|---------|------|----------|
| Shell 执行 | `shell` | 执行 Shell 命令 | `command`, `server_id`, `timeout`, `retry` |
| 文件上传 | `upload` | SFTP 上传文件 | `local_path`, `remote_path`, `server_id` |
| 文件下载 | `download` | SFTP 下载文件 | `remote_path`, `local_path`, `server_id` |
| 配置修改 | `config` | 替换配置变量 | `file_path`, `replacements`, `server_id` |
| 日志查看 | `log_view` | 查看日志内容 | `file_path`, `lines`, `server_id` |

### 5.2 IoTDB 专用节点

| 类型 | 节点 ID | 功能 | 配置参数 |
|------|---------|------|----------|
| IoTDB 部署 | `iotdb_deploy` | 部署 IoTDB | `version`, `install_path`, `server_id`, `config_template` |
| IoTDB 启动 | `iotdb_start` | 启动服务 | `server_id`, `wait_port`, `timeout` |
| IoTDB 停止 | `iotdb_stop` | 停止服务 | `server_id`, `graceful` |
| IoTDB CLI | `iotdb_cli` | 执行 CLI 命令 | `commands`, `server_id`, `timeout` |
| 配置模板 | `iotdb_config` | 应用配置模板 | `template_name`, `server_id` |

### 5.3 测试控制节点

| 类型 | 节点 ID | 功能 | 配置参数 |
|------|---------|------|----------|
| 条件判断 | `condition` | if/else 分支 | `expression`, `true_branch`, `false_branch` |
| 循环执行 | `loop` | for/while 循环 | `loop_type`, `iterations`, `condition` |
| 等待轮询 | `wait` | 等待条件满足 | `condition`, `timeout`, `interval` |
| 并行执行 | `parallel` | 并行执行节点 | `nodes`, `max_concurrent` |
| 断言检查 | `assert` | 检查条件 | `assert_type`, `params`, `expected` |

断言类型：
- `log_contains`: 日志包含关键词
- `port_open`: 端口是否监听
- `process_running`: 进程是否存在
- `file_exists`: 文件是否存在
- `command_output`: 命令输出匹配

### 5.4 结果节点

| 类型 | 节点 ID | 功能 | 配置参数 |
|------|---------|------|----------|
| 测试报告 | `report` | 生成测试报告 | `format`, `include_logs` |
| 结果汇总 | `summary` | 汇总断言结果 | 无 |
| 通知发送 | `notify` | 发送通知 | `type`, `recipient`, `template` |

---

## 6. 执行引擎设计

### 6.1 核心流程

```
┌─────────────┐
│  接收请求   │
└──────┬──────┘
       │
┌──────▼──────┐
│ 解析工作流  │
└──────┬──────┘
       │
┌──────▼──────┐
│ 构建执行图  │ ← DAG 依赖分析
└──────┬──────┘
       │
┌──────▼──────┐
│ 初始化状态  │
└──────┬──────┘
       │
┌──────▼──────┐
│ 执行节点    │ ← 异步并发执行
│ (并行独立)  │
└──────┬──────┘
       │
┌──────▼──────┐
│ 收集结果    │
└──────┬──────┘
       │
┌──────▼──────┐
│ 生成报告    │
└──────┬──────┘
       │
┌──────▼──────┐
│ 推送通知    │
└─────────────┘
```

### 6.2 并发控制

- 使用 `asyncio` 执行节点
- DAG 分析确定节点依赖关系
- 独立节点并行执行
- 可配置最大并发数（默认 5）
- 支持节点级超时设置

### 6.3 状态推送

- WebSocket 连接实时推送进度
- 推送内容：节点状态变化、日志片段、错误信息
- 前端实时更新执行面板

### 6.4 错误处理策略

| 策略 | 描述 |
|------|------|
| `retry` | 失败后重试 N 次 |
| `skip` | 失败后跳过，继续执行 |
| `stop` | 失败后立即停止工作流 |
| `continue` | 失败后继续执行，记录失败 |

---

## 7. API 设计

### 7.1 服务器管理 API

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/servers` | 服务器列表 |
| POST | `/api/servers` | 添加服务器 |
| GET | `/api/servers/{id}` | 服务器详情 |
| PUT | `/api/servers/{id}` | 更新服务器 |
| DELETE | `/api/servers/{id}` | 删除服务器 |
| POST | `/api/servers/{id}/test` | 测试连接 |
| POST | `/api/servers/{id}/execute` | 执行命令 |
| POST | `/api/servers/batch-test` | 批量测试连接 |

### 7.2 工作流 API

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/workflows` | 工作流列表 |
| POST | `/api/workflows` | 创建工作流 |
| GET | `/api/workflows/{id}` | 工作流详情 |
| PUT | `/api/workflows/{id}` | 更新工作流 |
| DELETE | `/api/workflows/{id}` | 删除工作流 |
| POST | `/api/workflows/import` | 导入 YAML |
| GET | `/api/workflows/{id}/export` | 导出 YAML |

### 7.3 执行 API

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | `/api/executions` | 创建执行 |
| GET | `/api/executions/{id}` | 执行详情 |
| POST | `/api/executions/{id}/pause` | 暂停执行 |
| POST | `/api/executions/{id}/resume` | 恢复执行 |
| POST | `/api/executions/{id}/stop` | 停止执行 |
| GET | `/api/executions/{id}/logs` | 执行日志 |
| GET | `/api/executions/{id}/report` | 测试报告 |
| GET | `/api/executions/history` | 执行历史 |

### 7.4 WebSocket

| 路径 | 描述 |
|------|------|
| `/ws/executions/{id}` | 执行进度实时推送 |

---

## 8. 前端路由设计

| 路径 | 页面 | 描述 |
|------|------|------|
| `/` | HomeView | 首页概览 |
| `/servers` | ServersView | 服务器管理 |
| `/workflows` | WorkflowsListView | 工作流列表 |
| `/workflows/:id/edit` | WorkflowEditorView | 工作流编辑器 |
| `/executions` | ExecutionsListView | 执行历史列表 |
| `/executions/:id` | ExecutionDetailView | 执行详情 |
| `/monitoring` | MonitoringView | 实时监控 |
| `/settings` | SettingsView | 系统设置 |

---

## 9. 功能清单

### 9.1 继承功能（11 项）

- 服务器列表/CRUD/连接测试/文件上传/远程命令/标签分组
- 本机监控/多主机监控/进程管理/自动刷新

### 9.2 新增功能（50+ 项）

**工作流编辑器：**
- 可视化编辑、节点连线、配置面板、缩放平移
- 保存/加载、导入导出 YAML、复制粘贴
- 撤销重做、节点搜索、画布快照

**工作流节点：**
- 5 种基础节点 + 5 种 IoTDB 专用节点
- 5 种测试控制节点 + 3 种结果节点

**执行引擎：**
- 后端驱动、并发控制、状态追踪
- 执行日志、错误处理、暂停恢复
- 变量传递、执行历史、实时进度

**测试报告：**
- 执行历史、详细日志、HTML 报告
- 断言结果、性能统计、报告导出

**系统功能：**
- 深色模式、API 文档、Docker 部署

---

## 10. 迁移策略

由于选择"一步到位"方案，迁移策略如下：

### Phase 1: 后端重构
1. 创建 FastAPI 项目骨架
2. 迁移服务器管理 API
3. 迁移监控 API
4. 实现工作流 CRUD API
5. 实现执行引擎

### Phase 2: 前端重构
1. 创建 Vue 3 项目骨架
2. 实现基础组件（Sidebar、TopBar、Modal）
3. 实现服务器管理页面
4. 实现监控页面
5. 实现工作流编辑器（Vue Flow）

### Phase 3: 集成测试
1. 前后端联调
2. 功能测试
3. IoTDB 测试场景验证

### Phase 4: 清理部署
1. 删除旧代码
2. Docker 部署配置
3. 文档完善

---

## 11. 开发优先级

| 优先级 | 模块 | 理由 |
|--------|------|------|
| P0 | 工作流编辑器 | 核心功能，最复杂 |
| P0 | 执行引擎 | 核心功能，最复杂 |
| P1 | 服务器管理 | 基础设施，快速迁移 |
| P1 | IoTDB 专用节点 | 业务核心 |
| P2 | 监控页面 | 功能稳定，迁移简单 |
| P2 | 测试报告 | 结果呈现 |
| P3 | 深色模式 | 体验优化 |
| P3 | Docker 部署 | 部署便利 |