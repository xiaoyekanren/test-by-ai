# 设计文档索引

本目录按“页面入口优先、共享能力补充”的方式组织设计文档。

## 页面设计

| 页面 | 文档 | 描述 | 最后更新 |
|------|------|------|----------|
| 应用框架 / 首页 | [pages/app-shell/ui-layout.md](pages/app-shell/ui-layout.md) | 主布局、页面高度、首页 UI 和全局 UI 规范 | 2026-04-13 |
| 服务器管理 | [pages/servers/region-scheduling.md](pages/servers/region-scheduling.md) | Region 字段、服务器忙闲状态、区域调度和 Servers 页面交互 | 2026-04-15 |
| 工作流 | [pages/workflows/editor.md](pages/workflows/editor.md) | Vue Flow 编辑器、节点类型、配置继承、撤销/重做 | 2026-04-13 |
| 工作流 | [pages/workflows/execution-engine.md](pages/workflows/execution-engine.md) | ExecutionEngine、节点执行、状态管理和上下文传递 | 2026-04-13 |
| 工作流 | [pages/workflows/iot-benchmark-async-node.md](pages/workflows/iot-benchmark-async-node.md) | IoTDB 2.0 benchmark 异步启动、等待与后续扩展方案 | 2026-04-15 |
| IoTDB 可视化 | [pages/iotdb/visualization.md](pages/iotdb/visualization.md) | WebSocket CLI、日志管理、配置编辑 | 2026-04-13 |
| 系统监控 | [pages/monitoring/service.md](pages/monitoring/service.md) | 本地/远程监控、进程管理、自动刷新 | 2026-04-13 |

## 共享能力

| 文档 | 描述 | 最后更新 |
|------|------|----------|
| [shared/frontend-architecture.md](shared/frontend-architecture.md) | Vue 3 + Pinia 架构、Store 设计、组件结构 | 2026-04-13 |
| [shared/backend-architecture.md](shared/backend-architecture.md) | FastAPI + SQLAlchemy 架构、API 路由、数据模型 | 2026-04-13 |
| [shared/ssh-service.md](shared/ssh-service.md) | SSHService 实现、连接管理、文件传输 | 2026-04-13 |
| [shared/release-runtime.md](shared/release-runtime.md) | 最终发布包结构、跨平台运行脚本和 Windows batch 变量展开约束 | 2026-04-17 |

## 调研与对照

| 文档 | 描述 | 最后更新 |
|------|------|----------|
| [research/node-red-gap-analysis.md](research/node-red-gap-analysis.md) | 对照 Node-RED 梳理工作流平台差距与路线图 | 2026-04-14 |

## 新文档归档规则

- 页面相关设计优先放入 `docs/design/pages/{page}/`。
- 跨页面通用架构、服务和工具能力放入 `docs/design/shared/`。
- 竞品分析、外部系统对照和路线调研放入 `docs/design/research/`。
- 新增或移动设计文档后同步更新本索引。

---

此目录自 2026-04-10 创建，于 2026-04-17 补充发布运行脚本设计。
