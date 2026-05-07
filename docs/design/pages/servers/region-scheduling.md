# 服务器区域调度设计文档

## 背景

工作流支持两种调度模式：

- **固定主机**（`fixed`）：每个节点必须显式选择服务器。
- **随机调度**（`random`）：节点不选服务器，由引擎在工作流指定区域内随机选择空闲且可调度的服务器。

两种模式互斥，不允许在同一个工作流中混用。

## 数据模型

### Server 模型

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| region | String(20) | 私有云 | 区域标识 |
| schedulable | Boolean | true | 是否允许被随机调度选中 |

`schedulable=false` 的服务器只能在固定主机模式下被手动选择，不会出现在随机调度的候选池中。

### Workflow 模型

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| schedule_mode | String(20) | fixed | 调度模式：`fixed` / `random` |
| schedule_region | String(20) | 私有云 | 随机调度的目标区域 |

### Region 允许值

- 私有云
- 公司-上层
- 公司
- Fit楼
- 公有云
- 异构

## 调度逻辑

### 固定主机模式（`schedule_mode=fixed`）

1. 每个需要服务器的节点必须配置 `server_id`
2. 集群节点的每个 `config_nodes` / `data_nodes` 条目也必须有 `server_id`
3. 引擎直接使用指定的服务器

### 随机调度模式（`schedule_mode=random`）

1. 节点不能配置 `server_id`
2. 引擎从 `schedule_region` 对应区域的空闲、可调度服务器中随机选择
3. 首次随机选中的服务器会绑定到调度角色，后续同角色节点复用

### 调度角色（Schedule Role）

随机调度引入角色隔离机制：

| 角色 | 适用节点 | 说明 |
|------|----------|------|
| `default` | shell、upload、download、config、iotdb_* 等 | 默认角色 |
| `benchmark` | iot_benchmark_deploy、iot_benchmark_start、iot_benchmark_wait | benchmark 独立角色 |

同角色的节点在同一链路中复用同一台随机选中的服务器。benchmark 节点使用独立角色，避免与 IoTDB 节点抢占同一台主机。

已随机出的服务器通过 `_scheduled_servers` 上下文传递：

```json
{
  "_scheduled_servers": {
    "default": {"server_id": 1, "host": "10.0.0.1", "region": "私有云"},
    "benchmark": {"server_id": 2, "host": "10.0.0.2", "region": "私有云"}
  }
}
```

### 空闲判定

服务器被判定为"繁忙"需满足：
- 存在 `status='running'` 的执行
- 该执行中存在 `status='running'` 的节点执行
- 该节点执行的 `input_data.server_id` 匹配该服务器

### 随机选择过滤条件

从候选池中排除：
- `schedulable=false` 的服务器
- 区域不匹配的服务器
- 当前繁忙的服务器

## API 校验

### 创建/更新工作流时的互斥校验

- `fixed` 模式：所有需要主机的节点必须有 `server_id`，否则返回 400
- `random` 模式：所有节点不能有 `server_id`，否则返回 400
- `random` 模式：必须指定 `schedule_region`，否则返回 400
- 对集群节点的 `config_nodes` / `data_nodes` 做同样校验

### Server API

新增字段：
- `region`: 服务器区域
- `schedulable`: 是否可被随机调度
- `is_busy`: 是否繁忙（计算字段）

## 前端变更

### ServersView

- 服务器列表按 Region 默认分组展示
- 表格新增"调度"列，显示"可调度"或"固定专用"标签
- 新增/编辑弹窗新增"随机调度"开关

### EditorToolbar

- 工具栏右侧新增调度模式下拉（固定主机 / 随机调度）
- 随机调度模式下显示区域选择器
- 切换到随机模式时自动清空所有节点的 server_id

### NodeConfigPanel

- 随机调度模式下隐藏 server_id 和 region 字段
- 固定模式下正常显示

### WorkflowEditorView

- 前端实时校验调度模式与节点配置的一致性
- 冲突时在节点上显示错误提示

## SQLite 迁移

`setup.py` 中的迁移函数自动为已有表添加新列：

- `servers` 表：`schedulable BOOLEAN DEFAULT 1`
- `workflows` 表：`schedule_mode VARCHAR(20) DEFAULT 'fixed'`、`schedule_region VARCHAR(20) DEFAULT '私有云'`

---

最后更新: 2026-05-07
