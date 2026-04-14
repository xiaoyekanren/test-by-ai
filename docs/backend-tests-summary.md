# 后端测试文件汇总

本文档记录 `backend/tests/` 目录下所有测试文件的详细信息。

## 测试文件列表

| 文件 | 测试数量 | 测试内容 |
|------|---------|----------|
| `conftest.py` | - | 测试配置 fixture |
| `test_schemas.py` | 4 | Pydantic Schema 验证 |
| `test_ssh_service.py` | 4 | SSH Service 类和方法检查 |
| `test_models.py` | 4 | SQLAlchemy Model 实例化 |
| `test_main.py` | 2 | FastAPI app 和健康检查端点 |
| `test_monitoring_api.py` | 13 | 监控服务和 API 端点 |
| `test_executions_api.py` | 6 | 执行 API 端点 |
| `test_servers_api.py` | 17 | 服务器 API 端点 |
| `test_workflows_api.py` | 6 | 工作流 API 端点 |
| `test_db_setup.py` | 8 | 数据库初始化和表结构验证 |
| `test_server_region.py` | 6 | Server Region 字段和 is_busy（2026-04-14 新增）|
| `test_execution_engine_region.py` | 31 | 执行引擎区域调度逻辑（2026-04-14 新增）|

**总计：103 tests**

---

## 各文件详细内容

### 1. `conftest.py` - 测试配置

**作用：** 提供测试 fixtures，配置内存数据库。

**Fixtures：**
- `db_session` - 每个 test function 的独立数据库 session，使用 transaction rollback
- `client` - FastAPI TestClient，自动注入 db_session

**数据库：**
- 使用内存 SQLite：`sqlite:///file:test_db?mode=memory&cache=shared&uri=true`
- 表结构在 module level 创建一次

---

### 2. `test_schemas.py` - Pydantic Schema 验证 (4 tests)

| Test | 验证内容 |
|------|----------|
| `test_server_create_schema` | ServerCreate 默认值验证 (port=22) |
| `test_server_create_requires_name_host` | 必填字段 ValidationError |
| `test_workflow_create_schema` | WorkflowCreate nodes/edges 结构 |
| `test_execution_create_schema` | ExecutionCreate workflow_id |

---

### 3. `test_ssh_service.py` - SSH Service (4 tests)

| Test | 验证内容 |
|------|----------|
| `test_ssh_service_exists` | SSHService 可实例化 |
| `test_ssh_service_has_run_command` | 有 run_command 方法 |
| `test_ssh_service_has_upload` | 有 upload_file 方法 |
| `test_ssh_result_structure` | SSHResult (exit_status, stdout, stderr) |

---

### 4. `test_models.py` - SQLAlchemy Models (4 tests)

| Test | 验证内容 |
|------|----------|
| `test_server_model` | Server model 实例化 (name, host, port) |
| `test_workflow_model` | Workflow model JSON nodes/edges |
| `test_execution_model` | Execution model (workflow_id, status) |
| `test_node_execution_model` | NodeExecution model (node_id, node_type) |

---

### 5. `test_main.py` - FastAPI App (2 tests)

| Test | 验证内容 |
|------|----------|
| `test_app_exists` | FastAPI app 可导入 |
| `test_health_endpoint` | GET /health 返回 {"status": "ok"} |

---

### 6. `test_monitoring_api.py` - 监控服务 (13 tests)

**MonitoringService 类测试 (6 tests):**
- `test_get_status_returns_system_info` - CPU/memory/disk 信息结构
- `test_get_processes_returns_list` - 进程列表结构
- `test_get_processes_sort_by_cpu` - 按 CPU 降序排序
- `test_get_processes_sort_by_memory` - 按 memory 降序排序
- `test_kill_process_success` - psutil.terminate 调用
- `test_kill_process_not_found` - NoSuchProcess 异常处理

**Monitoring API 端点测试 (7 tests):**
- `test_get_local_status` - GET /api/monitoring/local/status
- `test_get_local_processes` - GET /api/monitoring/local/processes
- `test_get_local_processes_with_limit` - ?limit=5 参数
- `test_get_local_processes_with_sort` - ?sort_by=memory 参数
- `test_kill_local_process` - POST /api/monitoring/local/process/{pid}/kill
- `test_kill_local_process_failed` - kill 返回 {"success": false}
- `test_get_remote_status_server_not_found` - 远程监控服务器 404
- `test_get_remote_processes_server_not_found` - 远程进程服务器 404
- `test_get_remote_status_success` - SSH 远程监控成功
- `test_get_remote_processes_success` - SSH 远程进程列表

---

### 7. `test_executions_api.py` - 执行 API (6 tests)

| Test | 验证内容 |
|------|----------|
| `test_create_execution` | POST /api/executions 创建 pending 执行 |
| `test_get_execution` | GET /api/executions/{id} 获取执行状态 |
| `test_list_executions` | GET /api/executions 列表 |
| `test_stop_execution` | POST /api/executions/{id}/stop |
| `test_delete_execution` | DELETE /api/executions/{id} + 级联删除 NodeExecution |
| `test_delete_execution_not_found` | 404 响应 |

---

### 8. `test_servers_api.py` - 服务器 API (17 tests)

| Test | 验证内容 |
|------|----------|
| `test_list_servers_empty` | GET /api/servers 空列表 [] |
| `test_create_server` | POST /api/servers 201 |
| `test_create_server_with_all_fields` | 所有字段创建 |
| `test_create_duplicate_server` | 重名返回 400 "already exists" |
| `test_get_server` | GET /api/servers/{id} |
| `test_get_server_not_found` | 404 |
| `test_update_server` | PUT /api/servers/{id} 更新 host |
| `test_update_server_name_conflict` | 名字冲突 400 |
| `test_update_server_not_found` | 404 |
| `test_delete_server` | DELETE /api/servers/{id} 204 |
| `test_delete_server_not_found` | 404 |
| `test_list_servers` | 多服务器列表 |
| `test_test_connection_not_found` | POST /api/servers/{id}/test 404 |
| `test_test_connection_marks_server_offline_on_failure` | SSH 失败标记 offline |
| `test_execute_command_not_found` | POST /api/servers/{id}/execute 404 |
| `test_execute_command_missing_command` | 缺少 command 400 |

---

### 9. `test_workflows_api.py` - 工作流 API (6 tests)

| Test | 验证内容 |
|------|----------|
| `test_list_workflows_empty` | GET /api/workflows [] |
| `test_create_workflow` | POST /api/workflows + nodes |
| `test_get_workflow` | GET /api/workflows/{id} |
| `test_update_workflow_nodes` | PUT 更新 nodes |
| `test_delete_workflow` | DELETE 204 |
| `test_delete_workflow_with_executions` | 删除 workflow + executions 级联 |

---

### 10. `test_db_setup.py` - 数据库初始化 (8 tests)

| Test | 验证内容 |
|------|----------|
| `test_data_directory_exists` | backend/data 目录存在 |
| `test_database_file_created_on_init` | init_db 创建 SQLite 文件 |
| `test_all_tables_created` | servers/workflows/executions/node_executions 表 |
| `test_servers_table_columns` | servers 字段: id, name, host, port, username, password, description, tags, status, **region**, created_at, updated_at |
| `test_workflows_table_columns` | workflows 字段: id, name, description, nodes, edges, variables, created_at, updated_at |
| `test_executions_table_columns` | executions 字段: id, workflow_id, status, trigger_type, triggered_by, started_at, finished_at, duration, result, summary, created_at |
| `test_node_executions_table_columns` | node_executions 字段: id, execution_id, node_id, node_type, status, started_at, finished_at, duration, input_data, output_data, log_path, error_message, retry_count |
| `test_init_db_idempotent` | 多次调用 init_db 安全 |

---

### 11. `test_server_region.py` - Region 字段 (6 tests)

**新增日期：** 2026-04-14

| Test | 验证内容 |
|------|----------|
| `test_server_region_field` | Server model region 默认值 "私有云" |
| `test_server_region_valid_values` | 6 个合法 region 值通过 |
| `test_server_create_schema_region` | ServerCreate/ServerUpdate/ServerResponse schema |
| `test_server_list_is_busy` | is_busy 基于 running node_executions 计算 |
| `test_create_server_returns_is_busy_false` | 新建服务器 is_busy=False |
| `test_get_server_returns_is_busy` | get_server 返回 is_busy |

---

### 12. `test_execution_engine_region.py` - 区域调度 (31 tests)

**新增日期：** 2026-04-14

**TestResolveServerWithRegion (8 tests):**
- `test_resolve_server_explicit_server_id_in_config` - config.server_id 优先
- `test_resolve_server_explicit_server_id_in_context` - context.server_id fallback
- `test_resolve_server_explicit_region_in_config` - config.region 区域选择
- `test_resolve_server_region_from_context` - context.region fallback
- `test_resolve_server_default_region` - 默认 "私有云"
- `test_resolve_server_no_idle_servers` - 无空闲返回 None
- `test_resolve_server_excludes_busy_servers` - 排除繁忙服务器
- 其他边界场景

**TestComputeBusyServerIds (4 tests):**
- `test_compute_busy_server_ids_no_running` - 无运行执行返回 []
- `test_compute_busy_server_ids_single_execution` - 单执行
- `test_compute_busy_server_ids_multiple_executions` - 多执行
- `test_compute_busy_server_ids_no_server_id_in_input_data` - 无 server_id 忽略

**TestNodeRequiresServer (12 tests):**
- shell, upload, download, config, log_view 需要 server
- iotdb_deploy, iotdb_start, iotdb_stop, iotdb_cli, iotdb_config 需要 server
- iotdb_cluster_* 需要 server
- condition, loop, wait, parallel, assert, report, summary, notify 不需要 server

**TestRequireServer (3 tests):**
- 有服务器返回 Server
- 无服务器抛 ValueError
- context 参数传递

**TestBuildContextUpdates (2 tests):**
- server_id/host/region 写入 context
- result.region 复制到 context

**TestMergeConfigWithContext (2 tests):**
- region 作为 fallback key

---

## 运行测试

```bash
cd backend
.venv/bin/python -m pytest tests/ -v
```

## 测试覆盖范围

- ✅ Schema 验证
- ✅ Model 实例化
- ✅ API 端点 CRUD
- ✅ 服务类方法
- ✅ 数据库初始化和迁移
- ✅ 区域调度逻辑
- ✅ 繁忙状态计算

---

*文档更新日期：2026-04-14*