# 待办事项汇总

> 最后更新: 2026-04-21
>
> 优先级：P1 紧急 / P2 重要 / P3 一般 / P4 低优

## IoTDB 可视化

### P3 集群日志分屏视图

- 当前日志查看仅支持单节点，缺少"全节点分屏"模式。
- 目标：增加日志视图模式切换（当前节点 / 全节点分屏），方便集群排障时并排对比多节点日志。

### P3 IoTDBView 组件拆分

- `IoTDBView.vue` 已膨胀到 2,687 行，承担了 CLI、日志、配置、重启等全部职责。
- 目标：拆分为 `IoTDBCliPanel`、`IoTDBLogsPanel`、`IoTDBConfigPanel`、`IoTDBRestartPanel` 等子组件。

### P1 IoTDB 接口路径校验

- `iotdb.py` 中 `readLog`、`readConfig` 等接口的 `path` 参数未做路径遍历校验，存在安全隐患。
- 目标：使用 `pathlib.Path.resolve()` 限制路径在允许目录内。

---

## 工作流编辑器

### P4 Minimap 小地图

- 工作流节点较多时缺少全局导航辅助。
- 目标：接入 `@vue-flow/minimap`。

### P3 新增逻辑节点

- condition / loop / wait 节点已实现。
- 待补充：延时节点（delay）和审批节点（approval / 人工确认）。

### P2 执行日志持久化

- 当前执行日志仅存于内存，页面刷新即丢失。
- 目标：将运行日志持久化（后端存储或 localStorage），支持刷新后回看。

### P2 Stop 终止远端运行命令

- 当前 Stop 已能阻止后续节点继续调度，但已开始执行的 SSH 命令或远端进程无法被真正终止。
- 目标：为 shell / IoTDB / benchmark 等执行节点记录远端进程组或 PID，并在 Stop 时发送终止信号，必要时支持超时后强制 kill。

### P2 执行前参数校验

- 目前可以在缺少必填参数的情况下直接启动执行。
- 目标：启动前校验各节点参数，缺失时高亮提示并阻止执行。

### P3 NodeConfigPanel 组件拆分

- `NodeConfigPanel.vue`（1,281 行）将所有节点类型的配置混在一个组件内。
- 目标：按节点类型拆分为独立配置面板。

### P3 report / summary / notify 节点缺少 handler

- 前端 `NodeType` 定义了 `report`、`summary`、`notify` 三种节点类型，但后端 `_node_handlers` 中没有注册对应 handler，执行时走默认空操作（无实际效果）。
- 目标：决定这些节点的实际行为并实现 handler，或者从 `NodeType` 中移除未实现的类型。

### P3 parallel 节点 max_concurrent 未实际生效

- `parallel` 节点返回了 `max_concurrent` 参数，但执行引擎并未读取该值来限制后续并发数，实际并发由全局 `ThreadPoolExecutor(max_workers=8)` 控制。
- 目标：引擎在执行 parallel 节点的下游分支时，使用其 `max_concurrent` 值做并发限制。

### P2 工作流变量（variables）未被使用

- `Workflow` 模型和 schema 中定义了 `variables` 字段，前端也有编辑入口，但执行引擎中完全没有读取和替换逻辑。节点 config 中无法通过 `${var}` 引用工作流变量。
- 目标：实现变量替换机制，在节点执行前将 config 中的 `${variable_name}` 替换为实际值。

### P3 节点失败重试机制

- `NodeExecution` 模型中有 `retry_count` 字段，但引擎中没有任何重试逻辑，节点失败后直接标记 failed。
- 目标：支持节点级 `retry` 配置，失败后按次数自动重试。

---

## 后端

### P2 异常处理规范化

- `iotdb.py`、`ssh_service.py`、`monitoring_service.py` 中存在多处 `except Exception: pass`，静默吞掉错误。
- 目标：替换为具体异常类型，并记录日志。

### P1 命令执行接口校验

- `servers.py` 的 `execute_command` 接受原始 `dict`，无 Pydantic schema 校验。
- 目标：创建 `CommandExecuteRequest` schema，限制可执行命令范围。

### P1 服务器密码明文存储

- `database.py` 中密码以 `String(100)` 明文存储。
- 目标：接入加密存储（如 `cryptography.fernet`），写入加密、读取解密。

### P3 执行记录分页

- `executions.py` 查询硬编码 `limit=100`，无分页参数。
- 目标：支持 `offset`、`limit`、日期范围筛选。

### P4 数据库索引

- `workflow_id`、`status`、`created_at` 等高频查询字段缺少索引。
- 目标：在 SQLAlchemy 模型中添加 `index=True`。

### P4 数据库迁移

- 没有使用 Alembic 等迁移工具，schema 变更依赖手动重建。
- 目标：接入 Alembic，生成迁移脚本，支持增量 schema 变更。

---

## 测试

### P3 后端测试覆盖补全

- 缺少测试的模块：
  - `services/execution/handlers/` — 各 handler 无单元测试（仅有 control_nodes 和 iotdb_deploy 的 2-15 个用例）
  - `services/execution/server_resolution.py` — 无测试
  - `services/execution/context.py` — 无测试
  - `services/monitoring_service.py` — 仅有 API 层测试，缺少 service 层单测
- `test_executions_api.py` 仅 6 个基础用例，缺少错误场景（404/400/500）、并发执行、超时等覆盖。

### P4 前端测试

- 当前无任何 Vue 组件或 Store 测试。
- 目标：接入 Vitest，优先覆盖 `stores/workflows.ts` 和关键业务组件。

---

## 前端构建

### P4 Element Plus 按需导入

- `vendor-ui` chunk（element-plus）仍为 896 KB，超过 500 KB 阈值。
- 目标：通过 `unplugin-vue-components` 实现按需导入，减小 chunk 体积。

---

## CORS 与认证

### P2 CORS 收窄

- `main.py` 中 `allow_origins=["*"]`，生产环境应限制为前端域名。

### P1 认证机制

- 当前所有 API 无认证/鉴权，任何人可访问和修改资源。
- 目标：按需引入 API Key 或 OAuth2 认证（视部署场景决定优先级）。

---

## 测试用例转工作流

### 进行中：磁盘空间占用统计

- 来源：`data/2026-04-08 v2091 统计数据的磁盘空间占用 测试用例.xlsx`（25 条用例，按前置条件分为 6 个工作流）
- 工作流 1-5 待实施，工作流 6 用例不完整
