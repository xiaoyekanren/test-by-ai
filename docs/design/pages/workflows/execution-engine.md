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
- `server_resolution.py`: `server_id` / `region` 解析与空闲服务器选择
- `context.py`: 父节点上下文合并、成功结果向下游传播
- `utils.py`: SSH 结果转换、路径与配置工具
- `handlers/basic.py`: shell/upload/download/config/log_view
- `handlers/iotdb.py`: deploy/start/cli/stop + SQL
- `handlers/cluster.py`: 集群 deploy/start/check/stop
- `handlers/benchmark.py`: benchmark start/wait/collect

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
      ├──────────────▶ failed (节点失败或手动停止)
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

**原因**:
- 运行时行为与编辑器连线一致
- 允许独立分支并发执行
- 能显式表示失败传播和不可达节点

### 执行上下文传递

**决策**: 使用 context 字典在父子节点间传递运行时结果。

**实现**: 仅成功节点更新 context；下游节点合并所有父节点 context 后执行。显式 `region` 可阻止继承 `server_id` / `host`，避免跨区域复用旧服务器。

**示例**:
```python
context = {}
# iotdb_deploy 节点输出 iotdb_home
context['iotdb_home'] = '/opt/iotdb'
# iotdb_start 节点读取 iotdb_home
iotdb_home = context.get('iotdb_home')
```

## 执行记录持久化

### Execution 记录

| 字段 | 描述 |
|------|------|
| workflow_id | 关联的工作流 |
| status | pending/running/completed/failed |
| trigger_type | manual/scheduled/api |
| started_at | 开始时间 |
| finished_at | 结束时间 |
| duration | 执行耗时（秒） |
| result | passed/failed/partial |
| summary | {"total": 10, "passed": 8, "failed": 2} |

### NodeExecution 记录

| 字段 | 描述 |
|------|------|
| execution_id | 关联的执行 |
| node_id | 节点 ID |
| node_type | 节点类型 |
| status | running/success/failed/skipped |
| input_data | 输入配置 |
| output_data | 输出结果 |
| error_message | 错误信息 |
| retry_count | 重试次数 |

---

最后更新: 2026-04-20
