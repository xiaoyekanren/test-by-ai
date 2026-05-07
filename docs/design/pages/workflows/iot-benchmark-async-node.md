# IoT Benchmark 异步节点

## 当前能力

工作流已提供三张 IoT Benchmark 节点卡片：

- `Deploy IoT Benchmark`：上传或下载 benchmark 包并解压到目标主机，输出 `benchmark_home`。
- `Start IoT Benchmark`：在远端后台启动一次 IoT Benchmark，然后立刻返回。
- `Wait IoT Benchmark`：从工作流上下文读取 `benchmark_run`，等待对应远端进程结束，并返回日志尾部、退出码和结构化摘要。

## 推荐编排

benchmark 不属于 IoTDB 服务生命周期本身，更像是对"已经启动并验证过的 IoTDB 目标"发起一次测试。推荐顺序：

```text
IoTDB Deploy
-> IoTDB Config Override
-> IoTDB Start
-> IoTDB CLI / IoTDB Cluster Check
-> Deploy IoT Benchmark
-> Start IoT Benchmark
-> 其他节点，例如 Log View / Monitor / CLI 检查
-> Wait IoT Benchmark
-> Download Benchmark Logs / Log View
-> IoTDB Stop
```

最小可用链路：

```text
IoTDB Start
-> IoTDB CLI
-> Deploy IoT Benchmark
-> Start IoT Benchmark
-> Wait IoT Benchmark
```

## Deploy IoT Benchmark

职责：将 benchmark 包部署到远端服务器，校验目录结构。

主要配置：

| 字段 | 说明 |
|------|------|
| `server_id` | benchmark 部署到哪台服务器上（固定模式）|
| `region` | 由 server 自动回填（固定模式）|
| `package_source` | `local`（上传本地包）或 `url`（远端下载）|
| `artifact_local_path` | 本地包路径（package_source=local 时）|
| `package_url` | 远端下载地址（package_source=url 时）|
| `remote_package_path` | 远端暂存路径 |
| `install_dir` | 安装目录，输出为 `benchmark_home` |
| `package_type` | `auto` / `zip` / `tar.gz` |
| `extract_subdir` | 可选，压缩包内的子目录名 |
| `overwrite` | 是否覆盖已有安装目录 |
| `timeout` | 部署超时秒数，默认 `600` |

执行流程：

```text
1. 解析 server_id / region，选定部署服务器
2. 如果 package_source=url，先 wget 下载到 remote_package_path
3. 如果 package_source=local，SFTP 上传到 remote_package_path
4. 解压到 install_dir
5. 校验 benchmark.sh 和 conf/config.properties 存在
6. 输出 benchmark_home = install_dir, benchmark_conf_path
```

输出示例：

```json
{
  "exit_status": 0,
  "server_id": 1,
  "host": "10.0.0.10",
  "region": "私有云",
  "benchmark_home": "/opt/iot-benchmark-iotdb-2.0-java8",
  "benchmark_conf_path": "/opt/iot-benchmark-iotdb-2.0-java8/conf/config.properties"
}
```

## Start IoT Benchmark

职责：在远端服务器后台启动 benchmark，并把 run handle 写入工作流上下文。

### 基础配置

| 字段 | 说明 |
|------|------|
| `server_id` | benchmark 运行在哪台服务器上 |
| `region` | 由 server 自动回填，也可用于调度 |
| `benchmark_home` | 已部署的 benchmark 目录，可从 Deploy 节点继承 |
| `target_host` | 被测 IoTDB host，可从上游 IoTDB 节点继承 |
| `rpc_port` | 被测 IoTDB RPC port，默认 `6667` |
| `db_switch` | 默认 `IoTDB-200-SESSION_BY_TABLET` |
| `dialect` | `tree` 或 `table` |
| `username` / `password` | IoTDB 登录信息 |
| `db_name` | benchmark 写入的数据库名 |
| `work_mode` | 默认 `testWithDefaultPath` |
| `loop` | 操作总次数 |
| `operation_proportion` | 操作比例，例如 `1:0:0:0:0:0:0:0:0:0:0:0` |
| `config_items` | 额外覆盖 `config.properties` 的键值 |
| `timeout` | 启动阶段超时，不代表 benchmark 总运行时长 |

### 读写参数映射

以下参数直接映射到 `config.properties`：

| config.properties 键 | 节点配置字段 | 说明 |
|---|---|---|
| `DEVICE_NUMBER` | `device_number` | 设备数 |
| `SENSOR_NUMBER` | `sensor_number` | 每设备传感器数 |
| `DATA_CLIENT_NUMBER` | `data_client_number` | 写入客户端数 |
| `SCHEMA_CLIENT_NUMBER` | `schema_client_number` | Schema 客户端数 |
| `BATCH_SIZE_PER_WRITE` | `batch_size_per_write` | 每次写入批大小 |
| `DEVICE_NUM_PER_WRITE` | `device_num_per_write` | 每次写入涉及设备数 |
| `CREATE_SCHEMA` | `create_schema` | 是否创建 Schema |
| `IS_DELETE_DATA` | `is_delete_data` | 运行前是否清理数据 |
| `POINT_STEP` | `point_step` | 时间步长 |
| `QUERY_SENSOR_NUM` | `query_sensor_num` | 查询涉及传感器数 |
| `QUERY_DEVICE_NUM` | `query_device_num` | 查询涉及设备数 |
| `QUERY_INTERVAL` | `query_interval` | 查询区间 |
| `WRITE_OPERATION_TIMEOUT_MS` | `write_operation_timeout_ms` | 写超时 |
| `READ_OPERATION_TIMEOUT_MS` | `read_operation_timeout_ms` | 读超时 |
| `TEST_MAX_TIME` | `test_max_time` | 测试最大运行时间 |
| `RESULT_PRINT_INTERVAL` | `result_print_interval` | 结果输出间隔 |
| `ENABLE_FIXED_QUERY` | `enable_fixed_query` | 固定查询模式 |
| `TEST_DATA_PERSISTENCE` | `test_data_persistence` | 结果持久化方式 |
| `CSV_OUTPUT` | `csv_output` | 是否输出 CSV |

布尔值参数自动转为 `true`/`false` 字符串。

### 集群目标自动生成

当上游连接了 IoTDB 集群节点时，`data_nodes` 会通过上下文继承传入。Start IoT Benchmark 会从 `data_nodes` 自动生成逗号分隔的 HOST 和 PORT 列表：

```text
data_nodes = [
  {"host": "10.0.0.21", "rpc_port": 6667},
  {"host": "10.0.0.22", "dn_rpc_port": 6668}
]
→ HOST = "10.0.0.21,10.0.0.22"
→ PORT = "6667,6668"
```

如果 `data_nodes` 为空或未传入，则回退到 `target_host` + `rpc_port` 单机模式。

### 执行流程

```text
1. 解析 server_id / region，选定 benchmark 运行服务器
2. 如果有 data_nodes，生成逗号分隔的 HOST/PORT
3. 创建远端运行目录：
   /tmp/iot-benchmark-runs/<execution_id>/<node_id>-<timestamp>
4. 复制 <benchmark_home>/conf 到运行目录
5. 修改运行目录里的 config.properties
6. 后台启动：
   bash ./benchmark.sh -cf <run_dir>/conf
7. 写出 benchmark.pid、benchmark.exit、benchmark.out
8. 返回 benchmark_run 并写入工作流 context
```

`benchmark_run` 示例：

```json
{
  "server_id": 1,
  "region": "私有云",
  "pid": "12345",
  "run_dir": "/tmp/iot-benchmark-runs/88/node-abc",
  "conf_dir": "/tmp/iot-benchmark-runs/88/node-abc/conf",
  "stdout_path": "/tmp/iot-benchmark-runs/88/node-abc/benchmark.out",
  "exit_path": "/tmp/iot-benchmark-runs/88/node-abc/benchmark.exit",
  "target_host": "10.0.0.21,10.0.0.22",
  "rpc_port": "6667,6668",
  "benchmark_home": "/opt/iot-benchmark-iotdb-2.0-java8"
}
```

## Wait IoT Benchmark

职责：读取 `benchmark_run`，等待远端进程结束，返回退出码、日志尾部和结构化摘要。

主要配置：

| 字段 | 说明 |
|------|------|
| `timeout_seconds` | 等待 benchmark 完成的最长时间，默认 `3600` |
| `poll_interval_seconds` | 轮询间隔，默认 `5` |
| `tail_lines` | 结束后读取日志尾部行数，默认 `200` |
| `kill_on_timeout` | 超时后是否尝试终止远端进程，默认 `false` |

执行流程：

```text
1. 从 context 读取 benchmark_run
2. 优先使用 benchmark_run.server_id 定位远端服务器
3. 周期性检查 ps -p <pid>
4. 进程结束后读取 benchmark.exit 和 benchmark.out tail
5. 对尾部日志做结构化摘要解析
6. 如果 benchmark 退出码非 0，则 Wait 节点失败
7. 如果等待超时，则 Wait 节点失败；kill_on_timeout=true 时尝试 kill
```

### 结构化摘要解析

Wait 节点会对 benchmark 日志尾部做正则匹配，提取以下指标到 `benchmark_result.summary`：

| 指标 | 匹配规则 |
|------|----------|
| `throughput` | 匹配 `throughput` 后的数值 |
| `avg_latency` | 匹配 `avg` / `average` 后的数值 |
| `p95_latency` | 匹配 `p95` 后的数值 |
| `p99_latency` | 匹配 `p99` 后的数值 |
| `ok_count` | 匹配 `ok` / `success` 后的数值 |
| `fail_count` | 匹配 `fail` / `error` 后的数值 |

同时识别操作类型行（INGESTION、PRECISE_QUERY、RANGE_QUERY 等），保存到 `operation_lines`。

## 配置继承

`Deploy IoT Benchmark` 从上游继承：

- `server_id`
- `region`

`Deploy IoT Benchmark` 向下游输出：

- `benchmark_home`（= `install_dir`）

`Start IoT Benchmark` 从上游继承：

- `server_id`
- `region`
- `benchmark_home`，来自 Deploy 节点
- `target_host`，来自上游输出的 `host`
- `rpc_port`
- `data_nodes`，来自上游集群节点

这里刻意使用 `target_host`，不复用 `host`。执行器中的 `host` 表示当前 SSH 服务器地址，会被 server 解析逻辑自动覆盖；`target_host` 才表示被测 IoTDB 的地址。

`Wait IoT Benchmark` 不要求用户重复配置服务器，默认从 `benchmark_run` 找到启动 benchmark 的服务器。

## 调度角色

随机调度模式下，benchmark 节点使用独立的 `benchmark` 调度角色，不复用 IoTDB/default 随机主机。同一条 benchmark 链路会复用 benchmark 角色已随机出的主机。详见 [region-scheduling.md](../servers/region-scheduling.md)。

---

最后更新: 2026-05-07
