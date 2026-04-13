# IoTDB 可视化设计

## 概述

IoTDB 可视化模块提供远程 IoTDB 服务的 CLI 交互、日志查看、配置管理等功能。通过 SSH 连接远程服务器操作 IoTDB。

## 技术架构

### API 路由

| 路径 | 功能 |
|------|------|
| `/api/iotdb/cli/session` | WebSocket CLI 会话 |
| `/api/iotdb/logs/list` | 日志文件列表 |
| `/api/iotdb/logs/read` | 读取日志内容 |
| `/api/iotdb/logs/stream` | 实时日志流 |
| `/api/iotdb/configs/list` | 配置文件列表 |
| `/api/iotdb/configs/read` | 读取配置文件 |
| `/api/iotdb/configs/write` | 写入配置文件 |
| `/api/iotdb/restart` | 重启 IoTDB 服务 |

### IoTDBView 页面结构

```
┌─────────────────────────────────────────────────────┐
│                    Toolbar                          │
│ [服务器选择] [IoTDB_HOME] [刷新] [重启]             │
└─────────────────────────────────────────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   CLI Tab   │     │  Logs Tab   │     │ Config Tab  │
│ (WebSocket) │     │ (文件列表)   │     │ (配置编辑)  │
│             │     │             │     │             │
│ ┌─────────┐ │     │ ┌─────────┐ │     │ ┌─────────┐ │
│ │ Terminal│ │     │ │ Log File│ │     │ │ Config  │ │
│ │         │ │     │ │ Viewer  │ │     │ │ Editor  │ │
│ └─────────┘ │     │ └─────────┘ │     │ └─────────┘ │
└─────────────┘     └─────────────┘     └─────────────┘
```

## WebSocket CLI 会话

### 连接流程

```
1. 前端发送 CLISessionRequest
   {
     server_id: 1,
     iotdb_home: "/opt/iotdb",
     host: "127.0.0.1",
     rpc_port: 6667,
     username: "root",
     sql_dialect: "tree"
   }

2. 后端建立 SSH 连接

3. 后端执行 start-cli.sh

4. 双向数据流:
   - SSH → WebSocket: 输出推送
   - WebSocket → SSH: 命令发送
```

### 消息类型

| 类型 | 方向 | 描述 |
|------|------|------|
| ready | Server→Client | CLI 就绪 |
| output | Server→Client | CLI 输出 |
| exit | Server→Client | CLI 退出 |
| input | Client→Server | 用户输入 |
| command | Client→Server | SQL 命令 |
| resize | Client→Server | 终端大小调整 |
| disconnect | Client→Server | 断开连接 |
| error | Server→Client | 错误信息 |

### 安全措施

- 路径规范化（`posixpath.normpath`）
- 路径限制在 `logs/` 或 `conf/` 目录下
- Shell 参数安全转义（`SSHService.quote`）

## 日志管理

### 日志目录

默认路径：`${IOTDB_HOME}/logs`

### 日志列表

```python
@router.post("/logs/list")
def list_logs(request: LogsListRequest):
    # find 命令列出 *.log 文件
    # 返回 FileInfo 列表：name, path, size, modified
```

### 日志读取

```python
@router.post("/logs/read")
def read_log(request: LogReadRequest):
    # tail -n {lines} {path} | tail -c {MAX_LOG_READ_BYTES}
    # 限制：最多 256KB，最多 1000 行
```

### 日志流

```python
@router.post("/logs/stream")
def stream_log(request: LogStreamRequest):
    # tail -n {lines} -F {path}
    # StreamingResponse 实时推送
```

## 配置管理

### 配置目录

默认路径：`${IOTDB_HOME}/conf`

### 配置文件读写

```python
@router.post("/configs/read")
def read_config(request: ConfigReadRequest):
    # SSHService.read_file()

@router.post("/configs/write")
def write_config(request: ConfigWriteRequest):
    # SSHService.write_file()
```

### 配置文件类型

- `iotdb-system.properties` - 系统配置
- `iotdb-env.sh` - 环境变量
- 其他 `.properties` / `.xml` 文件

## 服务重启

### 重启范围

| scope | 脚本 |
|-------|------|
| all | stop-standalone.sh + start-standalone.sh |
| cn | stop-confignode.sh + start-confignode.sh |
| dn | stop-datanode.sh + start-datanode.sh |

### 重启流程

```python
@router.post("/restart")
def restart_iotdb(request: RestartRequest):
    # 1. 执行停止脚本
    # 2. 执行启动脚本
    # 3. 返回执行结果
```

## 前端实现

### IoTDBStore

**状态**:
- `selectedServerId` - 选中的服务器
- `iotdbHome` - IoTDB 安装路径
- `logs` - 日志文件列表
- `configs` - 配置文件列表
- `cliConnected` - CLI 连接状态

**操作**:
- `fetchLogs()` - 获取日志列表
- `fetchConfigs()` - 获取配置列表
- `readLog(path)` - 读取日志
- `readConfig(path)` - 读取配置
- `writeConfig(path, content)` - 写入配置
- `restartIotdb(scope)` - 重启服务

### 终端组件

使用 xterm.js 渲染 CLI 输出：

```vue
<template>
  <div ref="terminalContainer" class="terminal-container"></div>
</template>

<script setup>
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'

// WebSocket 连接 + xterm 渲染
</script>
```

## 设计决策

### WebSocket vs HTTP

**决策**: CLI 使用 WebSocket，其他操作使用 HTTP。

**原因**:
- CLI 需要双向实时通信
- 日志/配置操作是单次请求响应

### 路径安全

**决策**: 所有路径必须规范化并限制在允许目录下。

**实现**:
```python
def child_path_under(path: str, parent: str) -> str:
    normalized_path = normalize_remote_path(path)
    normalized_parent = normalize_remote_path(parent)
    if normalized_path != normalized_parent and not normalized_path.startswith(f"{normalized_parent}/"):
        raise HTTPException(status_code=400, detail="Path must be under parent")
    return normalized_path
```

### 日志大小限制

**决策**: 限制日志读取最多 256KB，1000 行。

**原因**:
- 防止内存溢出
- 大日志文件影响响应速度
- 用户通常只需查看末尾内容

---

最后更新: 2026-04-13