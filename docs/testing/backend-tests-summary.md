# 后端测试文件汇总

本文档记录 `backend/tests/` 目录下的测试文件、覆盖范围和运行方式。

## 运行测试

```bash
cd backend
python3.13 -m pytest tests/ -v
```

只收集测试数量：

```bash
cd backend
python3.13 -m pytest --collect-only -q
```

最后收集结果：132 tests。

## 测试文件列表

| 文件 | 测试数量 | 测试内容 |
|------|---------:|----------|
| `conftest.py` | - | 测试配置 fixture，注入内存数据库和 FastAPI TestClient |
| `test_db_setup.py` | 9 | 数据库初始化、表结构和 legacy servers 表迁移 |
| `test_execution_engine_cluster.py` | 3 | IoTDB 集群部署节点、角色配置和必填角色校验 |
| `test_execution_engine_dag.py` | 4 | DAG 并发、join 等待、失败跳过、无边工作流兼容和 stop 请求阻止下游调度 |
| `test_control_nodes.py` | 15 | 控制节点：condition 分支/级联、loop 迭代/失败中断、parallel 透传、assert 命令构建、边标签 |
| `test_execution_engine_region.py` | 33 | 区域调度、繁忙服务器计算、节点 server 需求和上下文合并 |
| `test_executions_api.py` | 6 | 执行 API 创建、查询、列表、停止和删除 |
| `test_iotdb_deploy.py` | 2 | IoTDB 部署节点 package_url 下载和 local/url 互斥校验 |
| `test_main.py` | 2 | FastAPI app 导入和健康检查端点 |
| `test_models.py` | 5 | SQLAlchemy model 实例化和 aware UTC 时间字段 |
| `test_monitoring_api.py` | 16 | 本地/远程监控服务、进程列表和 kill API |
| `test_schemas.py` | 4 | Pydantic schema 默认值、必填字段和结构验证 |
| `test_server_region.py` | 6 | Server region 字段、合法值和 is_busy 返回 |
| `test_servers_api.py` | 17 | 服务器 API CRUD、重复校验、连接测试、命令执行参数和删除保护 |
| `test_ssh_service.py` | 4 | SSHService 方法和 SSHResult 结构 |
| `test_workflows_api.py` | 6 | 工作流 API CRUD、节点更新和级联删除 |

## 覆盖范围

| 能力 | 覆盖文件 |
|------|----------|
| Schema 验证 | `test_schemas.py` |
| Model 与时间字段 | `test_models.py` |
| 数据库初始化与迁移 | `test_db_setup.py` |
| 服务器管理 API | `test_servers_api.py`、`test_server_region.py` |
| 工作流 API | `test_workflows_api.py` |
| 执行 API | `test_executions_api.py` |
| 执行引擎 DAG | `test_execution_engine_dag.py` |
| 执行引擎停止 | `test_execution_engine_dag.py` |
| 控制节点 | `test_control_nodes.py` |
| 执行引擎区域调度 | `test_execution_engine_region.py` |
| IoTDB 集群节点 | `test_execution_engine_cluster.py` |
| IoTDB 部署节点 | `test_iotdb_deploy.py` |
| 监控服务和 API | `test_monitoring_api.py` |
| SSH 服务 | `test_ssh_service.py` |
| 应用入口 | `test_main.py` |

## 重点说明

### 测试数据库

`conftest.py` 使用内存 SQLite：`sqlite:///file:test_db?mode=memory&cache=shared&uri=true`。每个 test function 使用独立 session，并通过 dependency override 注入 FastAPI TestClient。

### 区域调度

区域调度测试覆盖以下行为：

- 显式 `server_id` 优先于 `region`
- `region` 可来自节点配置或 workflow context
- 默认 region 为 `私有云`
- running node execution 会让对应服务器进入 busy 集合
- shell、SFTP、IoTDB 和集群节点会按需解析服务器
- condition、loop、wait、parallel、assert、report、summary、notify 不需要服务器解析

### DAG 执行

DAG 测试覆盖 roots 并发执行、join 节点等待全部上游、上游失败时跳过 join，以及无 edges 工作流继续按旧顺序执行。

### 控制节点

控制节点测试覆盖以下行为：

- condition 节点根据 branch 结果跳过未命中的分支，跳过可级联到后代节点
- loop 节点按 iterations 配置重复执行子节点，循环体失败时提前终止
- parallel 节点透传执行，子节点由引擎并行调度
- assert handler 能正确构建 log_contains/file_exists/process_running/port_open/custom 命令
- 边标签 (edge_labels) 正确收集且无标签边不影响结果

### 集群部署

集群部署测试覆盖 ConfigNode/DataNode 角色配置写入、同机多角色配置合并，以及缺失必需角色时的错误处理。

### 监控

监控测试覆盖本地 psutil 状态、进程排序、kill 结果、远程服务器不存在的 404，以及通过 SSH 获取远程状态和进程列表。

## 更新规则

- 新增、删除或重命名测试文件时，更新“测试文件列表”。
- 新增核心业务能力测试时，更新“覆盖范围”和“重点说明”。
- 测试数量变化时，使用 `pytest --collect-only -q` 重新确认总数。

---

文档更新日期：2026-04-21
