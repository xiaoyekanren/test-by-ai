# 工作流执行引擎设计

## 概述

工作流执行引擎负责按顺序执行工作流中的节点，记录执行状态和结果，支持手动、API 和定时触发。

## 技术架构

### ExecutionEngine 类

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
      ▼
┌─────────────┐
│   paused    │  (暂未实现)
└─────────────┘
```

## 数据流

```
┌─────────────────────────────────────────────────────────────┐
│                     execute_workflow                         │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ 加载Workflow│────▶│ 更新状态    │────▶│ 初始化context│
│ 和节点列表   │     │ 为running   │     │ passed/failed│
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
      ┌────────────────────────────────────────────┐
      │          遍历节点顺序执行                    │
      └────────────────────────────────────────────┘
                           │
      ┌────────────────────┼────────────────────┐
      │                    │                    │
      ▼                    ▼                    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ 创建NodeExec │────▶│ _execute_node│────▶│ 更新NodeExec │
│ 记录         │     │ 执行节点     │     │ 状态和结果   │
└─────────────┘     └─────────────┘     └─────────────┘
                           │
                           ▼
                  ┌─────────────┐
                  │ success?    │
                  └─────────────┘
                      │       │
                 Yes  │       │ No
                      ▼       ▼
              ┌───────────┐  ┌───────────┐
              │ passed+=1 │  │ failed+=1 │
              │ continue  │  │ break     │
              └───────────┘  └───────────┘
                           │
                           ▼
                  ┌─────────────┐
                  │ 更新Execution│
                  │ 最终状态     │
                  └─────────────┘
```

## 节点类型执行

### 支持的节点类型

| 类型 | 描述 | 执行方式 |
|------|------|----------|
| shell | 执行 shell 命令 | SSH 远程执行 |
| upload | 上传文件 | SFTP |
| download | 下载文件 | SFTP |
| iotdb_deploy | 部署 IoTDB | SSH + 配置生成 |
| iotdb_start | 启动 IoTDB | SSH 执行启动脚本 |
| iotdb_stop | 停止 IoTDB | SSH 执行停止脚本 |
| iotdb_cli | IoTDB CLI 操作 | SSH 执行 CLI 命令 |
| iotdb_config | 配置 IoTDB | SSH + 配置文件写入 |
| condition | 条件判断 | 评估表达式 |
| wait | 等待 | sleep |
| parallel | 并行执行 | (暂未实现) |

### _execute_node 实现

根据节点类型调用对应执行逻辑：

```python
def _execute_node(node_type, config, context):
    if node_type == 'shell':
        return _execute_shell(config, context)
    elif node_type == 'iotdb_deploy':
        return _execute_iotdb_deploy(config, context)
    elif node_type == 'wait':
        return _execute_wait(config, context)
    # ...
```

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

### 顺序执行策略

**决策**: 节点按添加顺序执行，失败时立即停止。

**原因**:
- 简单可靠，易于理解
- 适合测试验证场景
- 后续可扩展为 DAG 拓扑执行

### 执行上下文传递

**决策**: 使用 context 字典在节点间传递数据。

**实现**: 成功节点的输出更新 context，后续节点可读取。

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
| status | pending/running/success/failed/skipped |
| input_data | 输入配置 |
| output_data | 输出结果 |
| error_message | 错误信息 |
| retry_count | 重试次数 |

---

最后更新: 2026-04-13