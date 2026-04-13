# SSH 服务设计

## 概述

SSH 服务模块负责与远程服务器建立 SSH 连接，执行命令，传输文件。采用 Paramiko 库实现。

## 技术架构

### SSHService 类

```python
class SSHService:
    def run_command(host, username, password, command, port, timeout) -> SSHResult
    def upload_file(host, username, password, local_path, remote_path, port, timeout) -> dict
    def download_file(host, username, password, remote_path, local_path, port, timeout) -> dict
    def read_file(host, username, password, remote_path, port, timeout) -> dict
    def write_file(host, username, password, remote_path, content, port, timeout) -> dict
    def quote(value: str) -> str  # Shell 命令参数安全转义
```

### SSHResult 数据结构

```python
@dataclass
class SSHResult:
    exit_status: int      # 命令退出状态码
    stdout: str           # 标准输出
    stderr: str           # 标准错误
    error: Optional[str]  # 连接/执行错误信息
    ssh_port: Optional[int] # 实际连接的端口
```

## 数据流

```
┌─────────────┐
│   API调用    │
└─────────────┘
      │
      ▼
┌─────────────┐     尝试端口: [22, 配置端口]
│ _connect_client│──────────────────────▶
└─────────────┘     依次尝试直到成功
      │
      ▼
┌─────────────┐
│ 执行操作     │  (命令/SFTP)
└─────────────┘
      │
      ▼
┌─────────────┐
│  返回结果    │
└─────────────┘
      │
      ▼
┌─────────────┐
│  关闭连接    │
└─────────────┘
```

## 接口设计

### run_command

执行远程 shell 命令。

**参数**:
- `host`: 服务器地址
- `username`: SSH 用户名
- `password`: SSH 密码
- `command`: 要执行的命令
- `port`: SSH 端口（默认 22）
- `timeout`: 连接超时时间（默认 30s）

**返回**:
```python
SSHResult(
    exit_status=0,    # 0 表示成功
    stdout="...",     # 命令输出
    stderr="",        # 错误输出
    error=None,       # 无错误
    ssh_port=22       # 实际连接端口
)
```

### upload_file / download_file

通过 SFTP 传输文件。

**特性**:
- 自动创建远程目录（upload）
- 自动创建本地目录（download）
- 返回操作状态和实际端口

### read_file / write_file

通过 SFTP 读写远程文件内容。

**特性**:
- 直接返回文件内容（read）
- 直接写入字符串内容（write）
- UTF-8 编码，忽略解码错误

## 设计决策

### 多端口尝试策略

**决策**: 连接时依次尝试端口 22 和配置端口。

**原因**:
- 某些服务器可能使用非标准 SSH 端口
- 提高连接成功率
- 记录实际成功端口供后续操作使用

### 连接不复用

**决策**: 每次操作建立新连接，操作完成后立即关闭。

**原因**:
- 简化代码，无需管理连接池状态
- 避免长时间空闲连接被服务器断开
- 支持并发操作，无连接竞争问题

### Shell 参数安全转义

**决策**: 提供 `quote()` 方法对 shell 参数进行安全转义。

**实现**:
```python
def quote(value: str) -> str:
    escaped = value.replace("'", "'\"'\"'")
    return f"'{escaped}'"
```

**用途**: 防止命令注入，确保参数安全传递。

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 连接失败 | 返回 `SSHResult(exit_status=-1, error=str(exc))` |
| 命令执行异常 | 捕获异常，返回错误信息 |
| SFTP 操作失败 | 返回 `{"status": "error", "message": str(exc)}` |
| 端口尝试失败 | 返回最后尝试的错误 |

## 调用示例

```python
# 服务器连接测试
ssh_service = SSHService()
result = ssh_service.run_command(
    host="192.168.1.100",
    username="root",
    password="password",
    command="echo 'Connection test successful'",
    timeout=10
)
if result.error:
    server.status = "offline"
else:
    server.status = "online"

# 执行远程命令
result = ssh_service.run_command(
    host=server.host,
    command="ls -la /opt/iotdb",
    timeout=30
)

# 读取远程文件
result = ssh_service.read_file(
    host=server.host,
    remote_path="/opt/iotdb/conf/iotdb-system.properties"
)
```

---

最后更新: 2026-04-13