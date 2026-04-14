# Node-RED 差距分析

## 概述

本文档记录当前 IoTDB Test Automation Platform 与 Node-RED 的主要能力差距，用于后续规划工作流编辑器、执行引擎、节点体系和安全能力。

当前平台更接近面向 IoTDB 和服务器测试自动化的专用工作流平台，而不是通用的 Node-RED 替代品。平台已经具备可视化工作流编辑、节点配置、自动保存、撤销/重做、执行历史、SSH/SFTP、IoTDB 部署与集群操作、服务器监控等垂直能力。

## 当前已有能力

| 能力 | 当前状态 |
|------|----------|
| 可视化编辑器 | 基于 Vue Flow，支持节点拖拽、连线、缩放、配置弹窗 |
| 节点面板 | 已有 Shell、文件传输、IoTDB、控制、结果类节点定义 |
| 配置面板 | 支持按节点类型展示不同字段，包含服务器、区域、SQL、JSON、键值配置等输入 |
| 配置继承 | 下游节点可继承上游节点的 server_id、region、iotdb_home、cluster_nodes 等字段 |
| 保存机制 | 支持工作流 CRUD、自动保存、脏状态提示 |
| 编辑历史 | 前端已有撤销/重做历史栈 |
| 执行记录 | 后端持久化 Execution 和 NodeExecution，前端可查看执行状态与节点输出 |
| SSH/SFTP 执行 | 支持远程命令执行、上传、下载、远程文件读写 |
| IoTDB 专用节点 | 支持部署、启动、停止、CLI、配置写入、集群部署/启动/检查/停止 |
| 监控能力 | 支持本地和远程 CPU、内存、磁盘、网络、进程信息 |

## 主要差距

### 1. 真正的事件流和 DAG 运行时

当前执行引擎主要按 `workflow.nodes` 数组顺序执行节点，失败后停止。`edges` 目前更多用于编辑器展示和配置继承，并没有成为运行时调度和消息路由的核心依据。

Node-RED 的核心模型是消息沿连线在节点之间传递，节点可以通过不同输出端口把消息送到不同分支。要接近 Node-RED，需要执行引擎从顺序遍历升级为基于图拓扑、端口和消息队列的 DAG 运行时。

建议补齐：

- 基于 `edges` 的拓扑排序和运行调度。
- 多输出端口路由，例如 condition 的 true/false 分支。
- 节点输入依赖处理，例如等待所有上游完成或任一上游触发。
- 循环和并行的运行时语义。
- 循环检测、孤立节点检测、不可达节点检测。

### 2. 统一消息模型和数据变换体系

当前节点之间主要通过 `context` 字典和节点输出字段传递数据，缺少统一的消息协议。Node-RED 以 `msg` 对象为核心，常见字段包括 `payload`、`topic`、`_msgid`，并围绕消息提供 Function、Change、Switch、Template、JSONata 等数据处理能力。

建议补齐：

- 定义平台统一消息结构，例如 `payload`、`meta`、`context`、`error`、`trace_id`。
- 区分工作流级变量、执行级上下文、节点输入消息、节点输出消息。
- 增加字段映射和表达式节点，避免所有逻辑都写进 Shell 或后端硬编码节点。
- 增加可视化的消息检查和节点输出预览。

### 3. 控制流节点真实执行

前端已经定义 `condition`、`loop`、`wait`、`parallel`、`assert`、`report`、`summary`、`notify` 等节点，但执行引擎对部分节点尚无真实执行逻辑，未知节点会走默认成功返回。

建议补齐：

- `condition`: 根据表达式结果选择 true/false 输出分支。
- `wait`: 支持固定延迟、轮询条件、超时失败。
- `loop`: 支持固定次数循环和条件循环，并设置最大迭代次数保护。
- `parallel`: 支持并发执行分支，并汇总成功/失败结果。
- `assert`: 支持对 stdout、stderr、SQL 结果、上下文字段进行断言。
- `report`/`summary`: 基于 NodeExecution 生成测试报告和摘要。
- `notify`: 支持邮件、Webhook 或企业 IM 通知，并处理通知失败策略。

### 4. 插件和节点生态

Node-RED 具备 Palette Manager 和自定义节点开发体系，可以安装、升级、禁用第三方节点。当前平台节点定义分散在前端类型、配置面板、后端执行器、schema 和测试里，新增节点需要跨多处修改。

建议补齐：

- 建立节点注册表，统一描述节点类型、端口、配置字段、默认值、校验规则和执行器。
- 让前端节点面板和配置面板从注册表生成，而不是大量硬编码。
- 后端执行器按节点类型注册和分发。
- 支持项目内自定义节点包，后续再考虑远程插件市场。
- 为节点包定义测试规范和兼容性版本。

### 5. 子流程和模板复用

Node-RED 支持 Subflow，把一段流程封装成可复用节点。当前平台还没有工作流片段、子流程或模板参数化概念。

建议补齐：

- 支持把一组节点保存为模板或子流程。
- 子流程暴露输入参数、输出结果和默认配置。
- 内置 IoTDB 常见模板，例如单机部署、集群部署、启动检查、压测前置准备、失败清理。
- 支持模板实例和模板定义解耦，便于升级模板而不破坏已有工作流。

### 6. 导入导出、版本控制和项目化

Node-RED 支持 flow 导入导出和 Projects，Projects 可配合 Git 管理 flows、credentials、依赖和提交历史。当前平台主要把工作流保存在数据库里，缺少可迁移、可审查、可协作的项目模型。

建议补齐：

- 工作流 JSON 导入/导出。
- 工作流版本快照和变更 diff。
- 工作流发布状态，例如 draft、active、archived。
- 项目级目录和依赖声明。
- Git 集成或至少支持将工作流导出为可提交的文件格式。

### 7. 安全、凭证和权限

Node-RED 支持编辑器/Admin API 鉴权、用户权限、OAuth/OpenID、自定义认证和 HTTPS 配置。当前平台已有服务器模型和 SSH 密码字段，但还缺少完整安全体系。

建议补齐：

- 用户登录和会话管理。
- 角色权限，例如查看、编辑、执行、管理服务器、管理系统设置。
- SSH 密码、数据库密码、Token 等凭证加密存储。
- 凭证引用机制，工作流中只引用 credential id，不直接保存明文。
- 执行审计日志，记录谁在何时执行了哪个工作流、使用了哪些服务器。
- 敏感输出脱敏，例如日志中隐藏密码、token、连接串。

### 8. 调试和运行观测

当前平台有执行历史和节点执行记录，但缺少类似 Node-RED Debug sidebar、节点状态、错误定位、Catch/Status 节点这类按消息追踪的调试体验。

建议补齐：

- 节点级实时日志流，而不是只通过轮询查看最终输出。
- 执行 trace，记录消息经过哪些节点、每步输入输出是什么。
- 点击执行记录定位到编辑器中的对应节点。
- 节点状态标识，例如 running、success、failed、skipped、waiting、retrying。
- Debug 节点或调试面板，用于查看中间消息。

### 9. 错误处理流

当前失败策略以失败即停止为主，缺少分支化错误处理。Node-RED 支持 Catch 节点处理可捕获错误，Status 节点监听节点状态。

建议补齐：

- 失败分支，例如节点失败后走 error 输出端口。
- 重试策略真实执行，包括次数、间隔、退避、只对特定错误重试。
- continue on error。
- cleanup/finally 节点，用于失败后清理远程环境。
- 人工审批暂停和恢复。
- 超时分支和取消执行的可靠实现。

### 10. 触发器和外部入口

当前执行模型支持 `manual`、`scheduled`、`api` 这类触发类型字段，但还缺少完整的调度器和事件入口管理。Node-RED 常见入口包括 Inject、HTTP、MQTT、Webhook 等。

建议补齐：

- 定时调度器和调度配置页面。
- API/Webhook trigger，并支持鉴权、参数映射和执行记录关联。
- 手动触发时的参数输入。
- 事件源节点，例如 HTTP、MQTT、文件变化、监控告警。
- 防重入策略，例如同一工作流是否允许并发执行。

## 推荐优先级

| 优先级 | 方向 | 原因 |
|--------|------|------|
| P0 | 基于 `edges` 的 DAG/消息运行时 | 这是从“顺序任务列表”升级为“真正流程编排”的底座 |
| P0 | 控制流节点真实执行 | 当前前端已有节点定义，但运行时语义不完整，容易造成用户误解 |
| P1 | 节点注册表 | 降低新增节点成本，为后续插件化铺路 |
| P1 | 凭证加密和权限 | SSH 与服务器执行是高风险能力，需要尽早补安全边界 |
| P1 | 调试和执行 trace | 复杂流程排障必须依赖可观测性 |
| P2 | 子流程和模板 | 对 IoTDB 测试场景复用价值高 |
| P2 | 导入导出和版本快照 | 支持协作、迁移和审查 |
| P2 | 调度器和 Webhook trigger | 扩展自动化入口 |
| P3 | 完整插件市场 | 价值高，但应在注册表和节点包格式稳定后再做 |

## 近期里程碑建议

### M1: 图执行底座

- 执行引擎使用 `edges` 构建 DAG。
- 支持 condition true/false 分支。
- 支持 skipped 状态和不可达节点标记。
- 执行前做拓扑校验和必填参数校验。

### M2: 消息与调试

- 引入统一消息结构。
- 节点执行记录保存 input message 和 output message。
- 前端在执行面板展示节点输入、输出、错误和 trace。
- 支持点击节点查看最近一次执行详情。

### M3: 控制流与可靠性

- 实现 wait、loop、parallel、assert。
- 实现 retry、timeout、continue on error。
- 增加 cleanup/finally 或失败分支。
- 补齐相关后端测试。

### M4: 安全与复用

- 增加用户和角色权限。
- 凭证加密存储，工作流引用凭证 ID。
- 增加工作流模板/子流程能力。
- 支持导入导出和版本快照。

## 参考资料

- Node-RED User Guide: https://nodered.org/docs/user-guide/
- Node-RED Messages: https://nodered.org/docs/user-guide/messages
- Node-RED Context: https://nodered.org/docs/user-guide/context
- Node-RED Core Nodes: https://nodered.org/docs/user-guide/nodes
- Node-RED Palette Manager: https://nodered.org/docs/user-guide/editor/palette/manager
- Node-RED Projects: https://nodered.org/docs/user-guide/projects/
- Node-RED Security: https://nodered.org/docs/user-guide/runtime/securing-node-red
- Node-RED Handling Errors: https://nodered.org/docs/user-guide/handling-errors

---

最后更新: 2026-04-14
