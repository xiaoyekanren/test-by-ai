# 工作流编辑器设计

## 概述

工作流编辑器是基于 Vue Flow 的可视化拖拽编辑器，支持节点拖入、连线、配置编辑、执行预览等功能。

## 技术架构

### 核心组件

| 组件 | 描述 |
|------|------|
| WorkflowEditorView | 编辑器主视图 |
| NodePalette | 左侧节点选择面板 |
| EditorToolbar | 顶部工具栏 |
| NodeConfigPanel | 右侧节点配置面板 |
| ExecutionPanel | 执行状态面板 |
| WorkflowNode | 自定义节点渲染组件 |

### Vue Flow 集成

```typescript
import { VueFlow, useVueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
```

**使用的事件**:
- `onConnect` - 连线创建
- `onEdgeClick` - 边点击选择
- `onNodeDragStop` - 节点拖拽结束
- `onPaneReady` - 画布初始化完成
- `onPaneClick` - 空白区域点击

## 数据流

```
┌─────────────────────────────────────────────────────┐
│                  WorkflowEditorView                  │
└─────────────────────────────────────────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ NodePalette │     │   VueFlow   │     │EditorToolbar│
│ (拖入节点)   │────▶│ (拖拽编辑)  │────▶│ (保存/执行) │
└─────────────┘     └─────────────┘     └─────────────┘
                          │
                          ▼
                    ┌─────────────┐
                    │NodeConfigPanel│
                    │ (节点配置)    │
                    └─────────────┘
                          │
                          ▼
                    ┌─────────────┐
                    │WorkflowsStore│
                    │ (状态管理)    │
                    └─────────────┘
```

## 节点类型

### 支持的节点类型

| 分类 | 类型 | 描述 |
|------|------|------|
| 基础 | shell | 执行 shell 命令 |
| 基础 | upload | 上传文件 |
| 基础 | download | 下载文件 |
| IoTDB | iotdb_deploy | 部署 IoTDB |
| IoTDB | iotdb_start | 启动 IoTDB |
| IoTDB | iotdb_stop | 停止 IoTDB |
| IoTDB | iotdb_cli | IoTDB CLI |
| IoTDB | iotdb_config | 配置 IoTDB |
| 集群 | iotdb_cluster_deploy | 集群部署 |
| 集群 | iotdb_cluster_start | 集群启动 |
| 集群 | iotdb_cluster_check | 集群检查 |
| 集群 | iotdb_cluster_stop | 集群停止 |
| 控制 | condition | 条件判断 |
| 控制 | loop | 循环（暂未实现） |
| 控制 | wait | 等待 |
| 控制 | parallel | 并行（暂未实现） |

### 节点配置结构

```typescript
interface NodeDefinition {
  id: string
  type: NodeType
  config: Record<string, unknown>
  position?: { x: number, y: number }
}
```

### NODE_CONFIGS 定义

每种节点类型的配置模板：

```typescript
const NODE_CONFIGS: Record<NodeType, NodeConfig> = {
  shell: {
    label: 'Shell Command',
    category: 'basic',
    color: '#3b82f6',
    icon: 'Terminal',
    description: 'Execute shell command on remote server',
    defaultConfig: {
      server_id: null,
      command: '',
      timeout: 30
    },
    fields: [
      { key: 'server_id', type: 'server', label: 'Server' },
      { key: 'command', type: 'textarea', label: 'Command' },
      { key: 'timeout', type: 'number', label: 'Timeout (s)' }
    ]
  },
  // ...
}
```

## 配置继承机制

### 继承规则

节点可从上游节点继承特定配置字段：

```typescript
const INHERITED_FIELDS_BY_NODE_TYPE: Partial<Record<NodeType, string[]>> = {
  shell: ['server_id'],
  iotdb_start: ['server_id', 'iotdb_home', 'host', 'rpc_port'],
  iotdb_cli: ['server_id', 'iotdb_home', 'host', 'rpc_port'],
  // ...
}
```

### 继承计算流程

```
1. 遍历所有节点
2. 查找每个节点的入边
3. 从上游节点获取输出配置
4. 检查继承字段是否为空或已被继承值填充
5. 应用继承值或恢复默认值
```

### 示例

``┌─────────────┐──────▶┌─────────────┐``
│iotdb_deploy │       │ iotdb_start │
│ server_id=1 │       │ server_id=? │
│ install_dir │       │ iotdb_home=?│
│ /opt/iotdb  │       │             │
└─────────────┘       └─────────────┘

继承后：
iotdb_start 获得：
- server_id = 1 (继承)
- iotdb_home = /opt/iotdb (继承)
```

## 撤销/重做

### 实现方式

历史数组存储节点和边的快照：

```typescript
interface HistoryState {
  nodes: FlowNode[]
  edges: FlowEdge[]
}

const history = ref<HistoryState[]>([])
const historyIndex = ref(-1)
const maxHistorySize = 50
```

### 触发时机

- 添加节点
- 删除节点/边
- 更新节点配置
- 添加/删除连线
- 更新节点标签

### 操作

```typescript
function undo() {
  if (canUndo.value) {
    historyIndex.value--
    // 从历史恢复状态
  }
}

function redo() {
  if (canRedo.value) {
    historyIndex.value++
    // 从历史恢复状态
  }
}
```

## 键盘快捷键

| 快捷键 | 功能 |
|--------|------|
| Delete/Backspace | 删除选中的节点或连线 |
| Ctrl+Z | 撤销 |
| Ctrl+Y | 重做 |
| Ctrl+S | 保存 |

**注意**: 在输入框中时不触发快捷键。

## 自动保存

### 实现

```typescript
const autoSave = ref(true)
let autoSaveTimer: ReturnType<typeof setInterval> | null = null

// 定时检查 isDirty 并保存
```

### 状态标识

- `isDirty` - 是否有未保存更改
- `isSaving` - 正在保存中

## 执行预览

### ExecutionPanel

**显示内容**:
- 当前执行状态
- 节点执行进度
- 各节点状态列表

**数据来源**:
- `executionsStore.currentExecution`
- `executionsStore.nodeExecutions`

**轮询更新**: 执行开始后，每 2 秒获取最新状态。

---

最后更新: 2026-04-13