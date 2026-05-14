# 设计文档索引

本目录按“页面入口优先、共享能力补充、调研对照归档”的方式组织设计文档。页面文档描述具体交互和状态，共享文档描述跨页面架构、服务和运行机制。

## 页面设计

| 页面 | 文档 | 描述 | 最后更新 |
|------|------|------|----------|
| 应用框架 / 首页 | [pages/app-shell/ui-layout.md](pages/app-shell/ui-layout.md) | 主布局、页面高度、首页 UI 和全局 UI 规范 | 2026-04-13 |
| 服务器管理 | [pages/servers/region-scheduling.md](pages/servers/region-scheduling.md) | Region 字段、schedulable 属性、固定/随机调度模式和角色隔离 | 2026-05-07 |
| 工作流 | [pages/workflows/editor.md](pages/workflows/editor.md) | Vue Flow 编辑器、节点类型、配置继承、撤销/重做、调度模式控件 | 2026-05-07 |
| 工作流 | [pages/workflows/execution-engine.md](pages/workflows/execution-engine.md) | ExecutionEngine、节点执行、状态管理、上下文传递和工作流调度 | 2026-05-07 |
| 工作流 | [pages/workflows/iot-benchmark-async-node.md](pages/workflows/iot-benchmark-async-node.md) | IoT Benchmark deploy/start/wait、读写参数映射、集群目标和结果摘要 | 2026-05-07 |
| IoTDB 可视化 | [pages/iotdb/visualization.md](pages/iotdb/visualization.md) | WebSocket CLI、日志管理、配置编辑 | 2026-04-13 |
| 系统监控 | [pages/monitoring/service.md](pages/monitoring/service.md) | 本地/远程监控、进程管理、自动刷新 | 2026-04-13 |
| 工作流 | [pages/workflows/ainode-workflow-nodes.md](pages/workflows/ainode-workflow-nodes.md) | AINode deploy/start/stop/check 节点、配置继承和端口探测 | 2026-05-14 |
| Webhook | [pages/webhooks/gitlab-webhook.md](pages/webhooks/gitlab-webhook.md) | GitLab Push Hook 触发工作流、规则过滤、安全验证和日志保留 | 2026-05-14 |

## 共享能力

| 文档 | 描述 | 最后更新 |
|------|------|----------|
| [shared/frontend-architecture.md](shared/frontend-architecture.md) | Vue 3 + Pinia 架构、Store 设计、组件结构 | 2026-05-07 |
| [shared/backend-architecture.md](shared/backend-architecture.md) | FastAPI + SQLAlchemy 架构、API 路由、数据模型 | 2026-05-07 |
| [shared/ssh-service.md](shared/ssh-service.md) | SSHService 实现、连接管理、文件传输 | 2026-04-13 |
| [shared/release-runtime.md](shared/release-runtime.md) | 最终发布包结构、跨平台运行脚本和 Windows batch 变量展开约束 | 2026-04-17 |
| [shared/iotdb-testing-platform-roadmap.md](shared/iotdb-testing-platform-roadmap.md) | 平台演进设计：测试资产、环境模板、报告和调度模型 | 2026-04-20 |

## 设计覆盖矩阵

| 能力域 | 页面文档 | 共享文档 |
|--------|----------|----------|
| 应用壳和导航 | [pages/app-shell/ui-layout.md](pages/app-shell/ui-layout.md) | [shared/frontend-architecture.md](shared/frontend-architecture.md) |
| 服务器管理和调度 | [pages/servers/region-scheduling.md](pages/servers/region-scheduling.md) | [shared/ssh-service.md](shared/ssh-service.md)、[shared/backend-architecture.md](shared/backend-architecture.md) |
| 工作流编辑和执行 | [pages/workflows/editor.md](pages/workflows/editor.md)、[pages/workflows/execution-engine.md](pages/workflows/execution-engine.md) | [shared/backend-architecture.md](shared/backend-architecture.md)、[shared/frontend-architecture.md](shared/frontend-architecture.md) |
| IoTDB 和 Benchmark | [pages/iotdb/visualization.md](pages/iotdb/visualization.md)、[pages/workflows/iot-benchmark-async-node.md](pages/workflows/iot-benchmark-async-node.md)、[pages/workflows/ainode-workflow-nodes.md](pages/workflows/ainode-workflow-nodes.md) | [shared/ssh-service.md](shared/ssh-service.md) |
| Webhook 集成 | [pages/webhooks/gitlab-webhook.md](pages/webhooks/gitlab-webhook.md) | [shared/backend-architecture.md](shared/backend-architecture.md) |
| 发布交付 | - | [shared/release-runtime.md](shared/release-runtime.md) |
| 平台演进 | - | [shared/iotdb-testing-platform-roadmap.md](shared/iotdb-testing-platform-roadmap.md) |

## 调研与对照

| 文档 | 描述 | 最后更新 |
|------|------|----------|
| [research/node-red-gap-analysis.md](research/node-red-gap-analysis.md) | 对照 Node-RED 梳理工作流平台差距与路线图 | 2026-04-14 |

## 新文档归档规则

- 页面相关设计优先放入 `docs/design/pages/{page}/`。
- 跨页面通用架构、服务和工具能力放入 `docs/design/shared/`。
- 竞品分析、外部系统对照和路线调研放入 `docs/design/research/`。
- 新增或移动设计文档后同步更新本索引。
- 不再使用历史 AI 计划目录存放计划或规格；需要保留的长期信息应整理为设计文档、测试说明或待办文档。
- 仅当工具脚本仍受版本控制且有维护价值时，才为其新增设计说明；当前仓库没有受版本控制的 `tools/` 目录。

---

此目录自 2026-04-10 创建，于 2026-05-14 补充 AINode 和 Webhook 设计。
