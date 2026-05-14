# AINode 工作流节点设计

## 概述

AINode 工作流节点支持在工作流中编排 IoTDB AINode 的部署、启动、停止和健康检查。四种节点类型对应 AINode 的完整生命周期，可与 IoTDB 集群节点串联使用。

## 节点类型

| 节点类型 | 功能 | Handler |
|----------|------|---------|
| `iotdb_ainode_deploy` | 上传安装包、解压、写入配置 | `_execute_iotdb_ainode_deploy_node` |
| `iotdb_ainode_start` | daemon 模式启动 + 端口探测等待就绪 | `_execute_iotdb_ainode_start_node` |
| `iotdb_ainode_stop` | 执行 stop 脚本，可指定 remove target | `_execute_iotdb_ainode_stop_node` |
| `iotdb_ainode_check` | 通过 DataNode CLI 执行 `show ainodes` | `_execute_iotdb_ainode_check_node` |

## 技术架构

### Deploy 节点

1. 调用 `_deploy_package_to_server` 将安装包上传并解压到目标目录
2. 校验目标目录包含 `conf/iotdb-ainode.properties`、`sbin/start-ainode.sh`、`sbin/stop-ainode.sh`、`lib/ainode`
3. 调用 `_build_ainode_replacements` 构建配置项，包含：
   - `cluster_name`、`ain_seed_config_node`（来自 config_nodes 第一个节点）
   - `ain_rpc_address`、`ain_rpc_port`
   - `ain_cluster_ingress_address`、`ain_cluster_ingress_port`（来自 data_nodes 第一个节点）
   - `ain_cluster_ingress_username`、`ain_cluster_ingress_password`
   - 用户自定义 `config_items`
4. 调用 `_apply_config_file_to_server` 写入 `conf/iotdb-ainode.properties`

### Start 节点

```
bash sbin/start-ainode.sh -d
→ 不检查 exit code
→ 循环端口探测 /dev/tcp/{host}/{port}
→ 端口通则返回 exit_status=0
→ 超时则返回 exit_status=-1
```

### Stop 节点

执行 `bash sbin/stop-ainode.sh`，可通过 `remove_target` 参数指定 `-t host:port`。

### Check 节点

解析 `data_nodes` 列表取第一个 DataNode，通过其 CLI 执行 `show ainodes` + 用户自定义 `validation_sqls`。

## 上下文传递

AINode 节点在执行引擎上下文中传递以下字段：

| 字段 | 来源 | 用途 |
|------|------|------|
| `ainode_home` | deploy 输出 | start/stop 定位安装目录 |
| `ainode_conf_path` | deploy 输出 | 配置文件路径 |
| `ain_rpc_address` | deploy 输出 | start 端口探测地址 |
| `ain_rpc_port` | deploy 输出 | start 端口探测端口 |
| `ain_seed_config_node` | deploy 输出 | 配置信息透传 |
| `ain_cluster_ingress_address` | deploy 输出 | DataNode 入口地址 |
| `ain_cluster_ingress_port` | deploy 输出 | DataNode 入口端口 |

## 前端配置继承

工作流编辑器中 AINode 节点的字段继承链：

```
iotdb_cluster_deploy → iotdb_ainode_deploy → iotdb_ainode_start → iotdb_ainode_stop
                                           → iotdb_ainode_check
```

- `iotdb_ainode_deploy` 从集群部署节点继承 `cluster_name`、`config_nodes`、`data_nodes`
- `iotdb_ainode_start` 从 deploy 继承 `ainode_home`、`ain_rpc_address`、`ain_rpc_port`
- `iotdb_ainode_stop` 从 start 继承 `ainode_home`、`ain_rpc_port`
- `iotdb_ainode_check` 从集群节点继承 `config_nodes`、`data_nodes`

## 设计决策

### 启动不依赖脚本 exit code

**决策**：start-ainode.sh 执行后不检查 exit code，统一用端口探测判断就绪。

**原因**：AINode 启动脚本 fork 后台 Java 进程后，SSH channel 的 `recv_exit_status` 经常阻塞到超时返回 -1，与 IoTDB ConfigNode/DataNode 启动遇到的问题相同。端口探测是判断服务就绪的最可靠方式。

### Check 节点使用 DataNode CLI

**决策**：`iotdb_ainode_check` 通过 DataNode 的 CLI 执行 `show ainodes`，而非直接连接 AINode。

**原因**：AINode 没有独立的交互式 CLI，集群拓扑信息需要通过 DataNode 查询。

---

文档更新日期：2026-05-14
