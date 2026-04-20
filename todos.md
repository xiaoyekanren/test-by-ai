# 待办事项汇总

> 最后更新: 2026-04-20
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

- `NodeConfigPanel.vue`（1,202 行）将所有节点类型的配置混在一个组件内。
- 目标：按节点类型拆分为独立配置面板。

---

## 后端

### P2 异常处理规范化

- `apiotdb.py`、`ssh_service.py`、`monitoring_service.py` 中存在多处 `except Exception: pass`，静默吞掉错误。
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

---

## 测试

### P3 后端测试覆盖补全

- 缺少测试的模块：
  - `services/execution/handlers/` — 各 handler 无单元测试
  - `services/execution/server_resolution.py` — 无测试
  - `services/execution/context.py` — 无测试
  - `services/monitoring_service.py` — 仅有 API 层测试，缺少 service 层单测
- `test_executions_api.py` 仅 2 个基础用例，缺少错误场景（404/400/500）覆盖。

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
