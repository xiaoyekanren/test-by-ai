# IoT Benchmark 异步节点

## 当前能力

工作流已提供两张 IoT Benchmark 节点卡片：

- `Start IoT Benchmark`：在远端后台启动一次 IoT Benchmark，然后立刻返回。
- `Wait IoT Benchmark`：从工作流上下文读取 `benchmark_run`，等待对应远端进程结束，并返回日志尾部与退出码。

第一版只支持单个 benchmark run。多 benchmark 的批量启动、并发等待和结果聚合放在后续扩展中处理。

## 推荐编排

benchmark 不属于 IoTDB 服务生命周期本身，更像是对“已经启动并验证过的 IoTDB 目标”发起一次测试。推荐顺序：

```text
IoTDB Deploy
-> IoTDB Config Override
-> IoTDB Start
-> IoTDB CLI / IoTDB Cluster Check
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
-> Start IoT Benchmark
-> Wait IoT Benchmark
```

## Start IoT Benchmark

职责：在远端服务器后台启动 benchmark，并把 run handle 写入工作流上下文。

主要配置：

| 字段 | 说明 |
|------|------|
| `server_id` | benchmark 运行在哪台服务器上 |
| `region` | 由 server 自动回填，也可用于调度 |
| `benchmark_home` | 已部署的 benchmark 目录，例如 `/opt/iot-benchmark-iotdb-2.0` |
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

执行流程：

```text
1. 解析 server_id / region，选定 benchmark 运行服务器
2. 创建远端运行目录：
   /tmp/iot-benchmark-runs/<execution_id>/<node_id>-<timestamp>
3. 复制 <benchmark_home>/conf 到运行目录
4. 修改运行目录里的 config.properties
5. 后台启动：
   bash ./benchmark.sh -cf <run_dir>/conf
6. 写出 benchmark.pid、benchmark.exit、benchmark.out
7. 返回 benchmark_run 并写入工作流 context
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
  "target_host": "127.0.0.1",
  "rpc_port": 6667
}
```

## Wait IoT Benchmark

职责：读取 `benchmark_run`，等待远端进程结束，返回退出码和日志尾部。

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
5. 如果 benchmark 退出码非 0，则 Wait 节点失败
6. 如果等待超时，则 Wait 节点失败；kill_on_timeout=true 时尝试 kill
```

## 配置继承

`Start IoT Benchmark` 从上游继承：

- `server_id`
- `region`
- `target_host`，来自上游输出的 `host`
- `rpc_port`

这里刻意使用 `target_host`，不复用 `host`。执行器中的 `host` 表示当前 SSH 服务器地址，会被 server 解析逻辑自动覆盖；`target_host` 才表示被测 IoTDB 的地址。

`Wait IoT Benchmark` 不要求用户重复配置服务器，默认从 `benchmark_run` 找到启动 benchmark 的服务器。

## 后续扩展

### 多 benchmark

线性编排不适合多 benchmark：

```text
Start A -> Start B -> Start C -> Wait A -> Wait B -> Wait C
```

如果 C 比 B 更早结束，线性 wait 仍会先卡在 B。更合适的扩展是批量节点：

```text
Start IoT Benchmarks
-> 其他节点
-> Wait IoT Benchmarks
-> Collect Benchmark Results
```

`Wait IoT Benchmarks` 内部维护 `benchmark_runs[]`，谁先结束就先记录，全部结束后节点完成。

### 通用异步节点

第一版保留 benchmark 专用节点。通用异步能力后续再抽象，避免过早把下列问题暴露给所有节点：

- 远端 pid 管理
- stdout、stderr、exit code 的持久化路径
- stop/cancel 语义
- 服务重启后的恢复
- 多服务器进程状态聚合
- 节点状态与工作流 context 的持久化边界
