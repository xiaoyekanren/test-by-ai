# 工作流执行引擎设计

## 概述

工作流执行引擎负责按 DAG 依赖关系调度工作流中的节点，记录执行状态和结果，支持手动、API 和定时触发。

## 技术架构

### ExecutionEngine 结构

```python
class ExecutionEngine:
    def __init__(self, db: Session)
    
    # 执行管理
    def create_execution(workflow_id, trigger_type, triggered_by) -> Execution
    def get_execution(execution_id) -> Execution | None
    def list_executions(workflow_id, status, limit) -> List[Execution]
    def stop_execution(execution_id) -> Execution | None
    
    # 核心执行逻辑
    def execute_workflow(execution_id) -> None
```

当前实现已拆分为 `backend/app/services/execution/` 包：

- `engine.py`: 执行生命周期、CRUD、线程池调度
- `graph.py`: DAG 构建、拓扑辅助、workflow_state 快照
- `node_dispatch.py`: 节点注册表分发、独立 session worker
- `server_resolution.py`: 固定/随机调度、角色隔离与空闲服务器选择
- `context.py`: 父节点上下文合并、成功结果向下游传播
- `utils.py`: SSH 结果转换、路径与配置工具
- `handlers/basic.py`: shell/upload/download/config/log_view
- `handlers/iotdb.py`: deploy/start/cli/stop + SQL
- `handlers/cluster.py`: 集群 deploy/start/check/stop
- `handlers/benchmark.py`: benchmark deploy/start/wait/collect
- `handlers/control.py`: condition/loop/wait/parallel/assert

`backend/app/services/execution_engine.py` 仅保留为向后兼容导出层，现有 import 路径无需修改。

### 执行状态流转

```
┌─────────────┐
│   pending   │  创建执行记录
└─────────────┘
      │
      ▼ start
┌─────────────┐
│   running   │  正在执行节点
└─────────────┘
      │
      ├──────────────▶ completed (全部节点成功)
      │
      ├──────────────▶ failed (节点失败)
      ├──────────────▶ stopped (手动停止)
      │
```

## 数据流

```
┌─────────────────────────────────────────────────────────────┐
│                     execute_workflow                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────┐     ┌─────────────┐     ┌────────────────┐
│ 加载Workflow│────▶│ 更新状态    │────▶│ 构建 DAG 图     │
│ 和节点列表   │     │ 为 running  │     │ parents/children│
└─────────────┘     └─────────────┘     └────────────────┘
                                                  │
                                                  ▼
                           ┌────────────────────────────────────┐
                           │ 计算 ready / blocked / pending 节点 │
                           └────────────────────────────────────┘
                                                  │
                         ┌────────────────────────┴────────────────────────┐
                         ▼                                                 ▼
               ┌────────────────┐                               ┌────────────────┐
               │ ready 节点提交到│                               │ blocked 节点写入│
               │ ThreadPoolExecutor│                             │ skipped 记录    │
               └────────────────┘                               └────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ worker 创建独立 DB 会话│
              │ 并按注册表分发处理器   │
              └──────────────────────┘
                         │
                         ▼
              ┌──────────────────────┐
              │ success -> 累积 context│
              │ failed  -> 下游跳过    │
              └──────────────────────┘
                         │
                         ▼
                 ┌─────────────┐
                 │ finally 清理 │
                 │ 启动的进程   │
                 └─────────────┘
                         │
                         ▼
                 ┌─────────────┐
                 │ 更新Execution│
                 │ summary/result│
                 └─────────────┘
```

## 节点类型执行

### 支持的节点类型

| 类型 | 描述 | 执行方式 |
|------|------|----------|
| shell | 执行 shell 命令 | SSH 远程执行 |
| upload | 上传文件 | SFTP |
| download | 下载文件 | SFTP |
| config | 通用配置文件替换 | SSH + 配置文件写入 |
| iotdb_deploy | 部署 IoTDB | SSH + 配置生成 |
| iotdb_start | 启动 IoTDB | SSH 执行启动脚本 |
| iotdb_stop | 停止 IoTDB | SSH 执行停止脚本 |
| iotdb_cli | IoTDB CLI 操作 | SSH 执行 CLI 命令 |
| iotdb_config | 配置 IoTDB | SSH + 配置文件写入 |
| log_view | 查看日志内容 | SSH 读取远端日志文件 |
| iotdb_cluster_deploy | 集群部署 | 多节点 SSH 部署 + 角色配置 |
| iotdb_cluster_start | 集群启动 | 按角色顺序启动 |
| iotdb_cluster_check | 集群检查 | CLI 查询集群状态 |
| iotdb_cluster_stop | 集群停止 | 按角色顺序停止 |
| iot_benchmark_deploy | 部署 IoT Benchmark | SSH 上传/下载并解压 benchmark 包 |
| iot_benchmark_start | 启动 IoT Benchmark | SSH 后台启动，返回 benchmark_run |
| iot_benchmark_wait | 等待 IoT Benchmark | 轮询远端进程，返回结果摘要 |
| condition | 条件分支 (if/else) | 执行 shell 表达式，exit 0 → True 分支，非零 → False 分支 |
| loop | 循环执行 | for 循环 N 次迭代，自动重复执行子节点 |
| wait | 等待条件满足 | 轮询执行 shell 命令直到 exit 0 或超时 |
| parallel | 并行网关 | 透传节点，引擎已原生并行调度 |
| assert | 断言检查 | SSH 检查日志/文件/进程/端口/自定义命令 |
| report | 生成测试报告 | 输出格式化报告 |
| summary | 汇总断言结果 | 聚合上游断言 |
| notify | 发送通知 | 触发通知渠道 |

### _execute_node 实现

当前通过节点类型注册表分发执行逻辑，而不是 if/elif 长链：

```python
self._node_handlers = {
    "shell": self._execute_shell_node,
    "upload": self._execute_upload_node,
    "download": self._execute_download_node,
    "config": self._execute_config_node,
    "iotdb_config": self._execute_iotdb_config_node,
    ...
}
```

未知节点当前仍会返回默认成功结果，不产生副作用。

### 执行结果结构

```python
{
    "exit_status": 0,        # 命令退出状态
    "stdout": "...",         # 标准输出
    "stderr": "...",         # 标准错误
    "error": None,           # 错误信息
    "managed_processes": [], # 启动节点登记的清理目标
    # 节点特定输出...
}
```

## 设计决策

### 后台任务执行

**决策**: 使用 FastAPI BackgroundTasks 异步执行工作流。

**实现**:
```python
@router.post("", response_model=ExecutionResponse)
def create_execution(execution_data, background_tasks, db):
    execution = engine.create_execution(...)
    background_tasks.add_task(engine.execute_workflow, execution.id)
    return execution
```

**原因**:
- API 立即返回，不阻塞请求
- 执行状态通过数据库持久化
- 前端通过轮询获取进度

### DAG 调度策略

**决策**: 节点按 `edges` 构建依赖图，所有上游成功后才可执行；上游失败或跳过时，下游标记为 `skipped`。

**控制流扩展**:
- **条件分支**: condition 节点完成后根据 `branch` 结果（true/false），匹配边标签（True/False），未命中的分支及其后代自动跳过
- **循环迭代**: loop 节点完成后，引擎追踪循环体（所有后代节点）。每次迭代完成后，若仍有剩余次数，清除循环体状态并重新入队
- **边标签**: `_build_execution_graph` 同时返回 `edge_labels` 字典，格式为 `{(from_id, to_id): label}`

**原因**:
- 运行时行为与编辑器连线一致
- 允许独立分支并发执行
- 能显式表示失败传播和不可达节点

### 执行上下文传递

**决策**: 使用 context 字典在父子节点间传递运行时结果。

**实现**: 仅成功节点更新 context；下游节点合并所有父节点 context 后执行。`_scheduled_servers` 在合并时做深合并而非覆盖，确保不同角色的调度结果不丢失。

**示例**:
```python
context = {}
# iotdb_deploy 节点输出 iotdb_home
context['iotdb_home'] = '/opt/iotdb'
# iotdb_start 节点读取 iotdb_home
iotdb_home = context.get('iotdb_home')
```

### 工作流调度模式

**决策**: 工作流支持固定主机（`fixed`）和随机调度（`random`）两种互斥模式。

**实现**:
- 工作流级别的 `schedule_mode` 和 `schedule_region` 通过 `workflow_context` 注入每个节点的执行上下文
- 固定模式要求每个节点显式配置 `server_id`
- 随机模式由引擎从目标区域的空闲、可调度服务器中随机选择
- benchmark 节点使用独立的 `benchmark` 调度角色，不与 IoTDB 节点共享随机主机

**原因**:
- 避免固定和随机混用导致资源冲突
- 角色隔离确保 benchmark 不会被分配到 IoTDB 所在主机

详见 [region-scheduling.md](../servers/region-scheduling.md)。

### 启动进程清理

**决策**: 工作流默认清理本次由平台启动的远端进程；只有工作流显式打开 `process_resident=true` 时才跳过清理。

**实现**:
- `Workflow.process_resident` 默认 `false`，前端显示为“进程常驻”开关。
- `iotdb_start`、`iotdb_ainode_start`、`iotdb_cluster_start` 和 `iot_benchmark_start` 在成功启动或启动后等待失败时返回 `managed_processes`。
- `execute_workflow` 使用 `finally` 调用 `_cleanup_execution_processes`，覆盖 completed、failed、stopped 和异常路径。
- 清理优先使用 `managed_processes.stop_command`，随后按 pid、受限 `fallback_pattern` 或登记 `home` 的 `/proc/<pid>/cwd` 目录匹配做兜底终止。
- fallback 和 cwd 兜底都会按 `managed_processes.kind` 过滤命令行：IoTDB 仅匹配 DataNode/ConfigNode/IoTDB 主类或启动形态，AINode 仅匹配 AINode，IoT Benchmark 仅匹配 benchmark 启动形态。
- cwd 兜底用于覆盖 IoTDB 启动失败但 Java 进程仍残留的场景；例如 DataNode 还未监听 RPC 端口，且命令行只包含 `sbin/..` 相对路径时，自带 stop 脚本和 `pgrep -f /opt/iotdb` 都可能漏掉它。
- 清理结果写入 `Execution.summary.process_cleanup`。

`managed_processes` 示例：

```json
[
  {
    "kind": "iotdb",
    "server_id": 1,
    "host": "10.0.0.1",
    "node_id": "node-1",
    "node_type": "iotdb_start",
    "home": "/opt/iotdb",
    "role": "datanode",
    "stop_command": "cd /opt/iotdb && bash sbin/stop-datanode.sh -f",
    "fallback_pattern": "/opt/iotdb"
  }
]
```

**边界**:
- 普通 `shell` 节点中用户手写 `nohup xxx &` 不会自动登记，平台无法可靠识别任意后台进程。
- 没有 `managed_processes` 的节点不会被自动清理，新增启动型节点必须显式登记清理目标。
- 如果同一台机器上多个工作流或人工操作共用同一个安装目录启动同类进程，一个工作流结束时仍会把同目录下的同类进程视为本次清理目标。需要保留这类进程时，应使用独立安装目录或打开 `process_resident`。

**不兼容点**:
- 新版工作流表需要 `process_resident` 列；既有 SQLite 数据库不会自动迁移。
- 进程清理摘要从 `summary.cleanup` 改为 `summary.process_cleanup`。
- 旧的按 `input_data` 安装目录推断并扫描进程的兼容清理路径已移除。

## 执行记录持久化

### Execution 记录

| 字段 | 描述 |
|------|------|
| workflow_id | 关联的工作流 |
| status | pending/running/paused/completed/failed/stopped |
| trigger_type | manual/scheduled/api |
| started_at | 开始时间 |
| finished_at | 结束时间 |
| duration | 执行耗时（秒） |
| result | passed/failed/partial |
| summary | {"total": 10, "passed": 8, "failed": 2} |

`summary.process_cleanup` 记录进程清理结果。常驻模式下写入 `{ "skipped": true, "reason": "workflow_process_resident" }`。

### NodeExecution 记录

| 字段 | 描述 |
|------|------|
| execution_id | 关联的执行 |
| node_id | 节点 ID |
| node_type | 节点类型 |
| status | pending/running/success/failed/skipped |
| input_data | 输入配置 |
| output_data | 输出结果 |
| error_message | 错误信息 |
| retry_count | 重试次数 |

---

最后更新: 2026-06-02
