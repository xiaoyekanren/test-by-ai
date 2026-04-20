# 前端架构设计

## 概述

前端采用 Vue 3 + TypeScript + Vite 架构，使用 Element Plus 作为 UI 组件库，Vue Flow 实现可视化工作流编辑器。

浏览器页面标题由 `frontend/index.html` 配置，统一显示为 `TestFlow`。

## 技术架构

### 技术栈

| 组件 | 技术 | 用途 |
|------|------|------|
| 框架 | Vue 3 | 响应式 UI |
| 语言 | TypeScript | 类型安全 |
| 构建 | Vite | 开发与打包 |
| UI 库 | Element Plus | 组件库 |
| 工作流编辑 | Vue Flow | 拖拽式节点编辑 |
| 状态管理 | Pinia | 全局状态 |
| 路由 | Vue Router | 页面导航 |
| HTTP | Fetch | API 调用 |

### 目录结构

```
frontend/src/
├── main.ts           # 应用入口
├── App.vue           # 根组件
├── router/index.ts   # 路由配置
├── styles/main.css   # 全局样式 + Element Plus 主题覆盖
├── api/              # API 调用封装
│   └── index.ts      # servers/workflows/executions/monitoring/settings/iotdb
├── stores/           # Pinia 状态管理
│   ├── servers.ts    # 服务器管理状态
│   ├── workflows.ts  # 工作流 + 编辑器状态
│   ├── executions.ts # 执行管理状态
│   ├── monitoring.ts # 监控状态
│   ├── settings.ts   # 系统设置状态
│   └── iotdb.ts      # IoTDB 状态
├── views/            # 页面视图
│   ├── HomeView.vue      # 首页（脑图布局）
│   ├── ServersView.vue   # 服务器管理
│   ├── WorkflowsView.vue # 工作流列表
│   ├── WorkflowEditorView.vue # 工作流编辑器
│   ├── MonitorView.vue   # 系统监控
│   ├── IoTDBView.vue     # IoTDB 可视化
│   ├── ExecutionInsightsView.vue # 执行洞察
│   └── SettingsView.vue  # 系统设置
├── components/       # 可复用组件
│   ├── layout/       # 布局组件
│   │   ├── MainLayout.vue # 主布局框架
│   │   ├── Sidebar.vue    # 侧边栏导航
│   │   ├── TopBar.vue     # 顶部工具栏
│   └── workflow/     # 工作流编辑器组件
│       ├── NodePalette.vue     # 节点选择面板
│       ├── EditorToolbar.vue   # 编辑器工具栏
│       ├── NodeConfigPanel.vue # 节点配置面板
│       ├── ExecutionPanel.vue  # 执行状态面板
│       └── nodes/WorkflowNode.vue # 自定义节点渲染
└── types/            # TypeScript 类型定义
    └── index.ts      # Server/Workflow/Execution/NodeType 等
```

### 数据流

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    View     │────▶│    Store    │────▶│    API      │
│  (页面)     │     │   (Pinia)   │     │   (Fetch)   │
└─────────────┘     └─────────────┘     └─────────────┘
      │                   │                   │
      │                   │                   │
      ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  组件状态    │     │  全局状态    │     │   Backend   │
│  (局部响应)  │     │  (共享数据)  │     │  (FastAPI)  │
└─────────────┘     └─────────────┘     └─────────────┘
```

## 页面路由

| 路径 | 页面 | 描述 |
|------|------|------|
| `/` | HomeView | 首页脑图导航 |
| `/servers` | ServersView | 服务器管理 |
| `/workflows` | WorkflowsView | 工作流列表 |
| `/workflows/:id/edit` | WorkflowEditorView | 工作流编辑器 |
| `/executions` | ExecutionInsightsView | 执行洞察 |
| `/monitor` | MonitorView | 系统监控 |
| `/iotdb` | IoTDBView | IoTDB 可视化 |
| `/settings` | SettingsView | 系统设置 |

## 布局架构

### 主布局结构

```
┌─────────────────────────────────────────────────────┐
│ Sidebar │                 TopBar                    │
│ 180px   │──────────────────────────────────────────│
│/52px    │                 Main                      │
│(折叠)   │              (router-view)                │
│         │                                          │
└─────────────────────────────────────────────────────┘
```

### 高度计算

| 区域 | 高度 |
|------|------|
| TopBar | 56px |
| Main padding-top | 12px |
| Main padding-bottom | 12px |
| **总计占用** | 80px |

页面可用高度：`calc(100vh - 80px)`

## Store 设计

### ServersStore

**状态**:
- `servers: Server[]` - 服务器列表
- `loading: boolean` - 加载状态
- `testingServerIds: Set<number>` - 正在测试的服务器

**操作**:
- `fetchServers()` - 获取列表
- `addServer(data)` - 添加服务器
- `updateServer(id, data)` - 更新服务器
- `deleteServer(id)` - 删除服务器
- `testConnection(id)` - 测试连接
- `executeCommand(id, command)` - 执行命令

### WorkflowsStore

**状态**:
- `workflows: Workflow[]` - 工作流列表
- `editorNodes: FlowNode[]` - 编辑器节点
- `editorEdges: FlowEdge[]` - 编辑器连线
- `selectedNodeId` - 选中的节点
- `isDirty` - 是否有未保存更改
- `canUndo/canRedo` - 撤销/重做能力

**操作**:
- 工作流 CRUD
- 编辑器操作：`addNode`, `deleteNode`, `addEdge`, `deleteEdge`
- 节点配置：`updateNodeConfig`, `updateNodeLabel`
- 撤销/重做：`undo`, `redo`
- 保存：`saveWorkflowToBackend`

### ExecutionsStore

**状态**:
- `executions: Execution[]` - 执行列表
- `currentExecution` - 当前执行的详情
- `nodeExecutions` - 节点执行记录

**操作**:
- `createExecution(workflow_id)` - 创建执行
- `fetchExecution(id)` - 获取执行详情
- `stopExecution(id)` - 停止执行

## 设计决策

### 编辑器状态分离

**决策**: WorkflowsStore 同时管理列表和编辑器状态。

**原因**:
- 编辑器需要访问工作流数据
- 节点配置继承依赖服务器列表
- 避免跨 Store 数据同步

### 撤销/重做实现

**决策**: 使用历史数组记录状态快照。

**实现**:
```typescript
interface HistoryState {
  nodes: FlowNode[]
  edges: FlowEdge[]
}
const history = ref<HistoryState[]>([])
const historyIndex = ref(-1)
```

**限制**: 最多保存 50 个快照。

### 自动保存策略

**决策**: 编辑器支持自动保存（可开关）。

**实现**: 定时检查 `isDirty` 状态，触发保存。

### 配置继承机制

**决策**: 下游节点可继承上游节点的配置输出。

**示例**:
- `iotdb_deploy` 输出 `iotdb_home`
- `iotdb_start` 自动继承 `iotdb_home`

**实现**: `reapplyInheritedConfig()` 在连线变化时重新计算继承值。

## 组件设计

### Sidebar 侧边栏

**特性**:
- 可折叠（180px → 52px）
- 分组导航
- 动画过渡效果
- 响应式固定定位（移动端）

### WorkflowEditorView 编辑器

**核心功能**:
- Vue Flow 拖拽编辑
- 节点面板（拖入新节点）
- 工具栏（保存、撤销、重做、执行）
- 节点配置面板
- 执行状态面板

### MonitorView 监控页

**特性**:
- 本地 + 远程服务器监控
- 进程列表管理
- 自动刷新（可配置间隔）
- Grafana/Prometheus 集成链接

---

最后更新: 2026-04-17
