# 系统监控设计

## 概述

系统监控模块提供本地和远程服务器的 CPU、内存、磁盘监控，以及进程管理功能。

## 技术架构

### MonitoringService 类

```python
class MonitoringService:
    def __init__(self):
        self.ssh_service = SSHService()
    
    # 本地监控
    def get_status() -> Dict[str, Any]
    def get_processes(limit, sort_by) -> List[Dict[str, Any]]
    def kill_process(pid) -> Dict[str, Any]
    
    # 远程监控
    def get_remote_status(host, username, password, port, server_id, server_name) -> Dict
    def get_remote_processes(host, username, password, port, limit, sort_by, server_id, server_name) -> Dict
```

### API 路由

| 路径 | 功能 |
|------|------|
| `/api/monitoring/local/status` | 本地服务器状态 |
| `/api/monitoring/local/processes` | 本地进程列表 |
| `/api/monitoring/local/process/{pid}/kill` | 杀死本地进程 |
| `/api/monitoring/remote/{server_id}/status` | 远程服务器状态 |
| `/api/monitoring/remote/{server_id}/processes` | 远程进程列表 |

## 数据流

### 本地监控

```
┌─────────────┐
│ psutil      │
│ cpu_percent │
│ virtual_memory│
│ disk_usage  │
└─────────────┘
      │
      ▼
┌─────────────┐
│ get_status  │
└─────────────┘
      │
      ▼
┌─────────────┐
│ API Response│
│ {           │
│   cpu_percent│
│   memory: { │
│     percent │
│     used    │
│     total   │
│   }         │
│   disk: {   │
│     percent │
│     used    │
│     total   │
│   }         │
│ }           │
└─────────────┘
```

### 远程监控

```
┌─────────────┐
│  SSH连接     │
└─────────────┘
      │
      ▼
┌─────────────┐
│ 执行组合命令 │
│ top + free  │
│ + df        │
└─────────────┘
      │
      ▼
┌─────────────┐
│ 解析输出     │
│ ===CPU===   │
│ ===MEM===   │
│ ===DISK===  │
└─────────────┘
      │
      ▼
┌─────────────┐
│ API Response│
│ + server_id │
│ + server_name│
│ + host      │
└─────────────┘
```

## 本地监控实现

### CPU

```python
cpu_percent = psutil.cpu_percent(interval=0.1)
```

### 内存

```python
memory = psutil.virtual_memory()
memory_info = {
    "total": memory.total,
    "available": memory.available,
    "percent": memory.percent,
    "used": memory.used,
    "free": memory.free
}
```

### 磁盘

```python
disk = psutil.disk_usage('/')
disk_info = {
    "total": disk.total,
    "used": disk.used,
    "free": disk.free,
    "percent": disk.percent
}
```

### 进程列表

```python
processes = []
for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
    processes.append({
        "pid": proc.info['pid'],
        "name": proc.info['name'],
        "cpu_percent": proc.info['cpu_percent'] or 0.0,
        "memory_percent": proc.info['memory_percent'] or 0.0
    })
# 按 CPU 或内存排序
processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
```

## 远程监控实现

### 组合命令

一次 SSH 调用获取所有信息：

```bash
echo "===CPU==="
top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1
echo "===MEM==="
free -b | grep Mem | awk '{print $2,$3,$4,$7}'
echo "===DISK==="
df -B1 / | tail -1 | awk '{print $2,$3,$4,$5}'
```

### 进程列表

```bash
ps aux --sort=-pcpu | head -n {limit+1} | tail -n {limit}
```

## 前端实现

### MonitorView 页面

**功能**:
- 本地服务器 + 远程服务器列表
- CPU/内存/磁盘进度条显示
- 进程管理 Drawer
- Grafana/Prometheus 外部链接

### MonitoringStore

**状态**:
- `localStatus` - 本地状态
- `remoteStatuses` - 远程状态缓存

**操作**:
- `fetchLocalStatus()` - 获取本地状态
- `fetchLocalProcesses(limit, sort_by)` - 获取本地进程
- `killProcess(pid)` - 杀死本地进程
- `fetchRemoteStatus(server_id)` - 获取远程状态
- `fetchRemoteProcesses(server_id, limit, sort_by)` - 获取远程进程

### 自动刷新

**配置**: 系统设置中配置刷新间隔（默认 5 秒）

**实现**:
```typescript
const refreshInterval = ref<ReturnType<typeof setInterval> | null>(null)

onMounted(() => {
  const intervalMs = settingsStore.settings.monitor.refreshInterval * 1000
  refreshInterval.value = setInterval(refreshData, intervalMs)
})

onUnmounted(() => {
  if (refreshInterval.value) {
    clearInterval(refreshInterval.value)
  }
})
```

## 设计决策

### 本地 vs 远程分离

**决策**: API 分离 `/local` 和 `/remote` 路径。

**原因**:
- 本地监控无需 SSH 连接
- 远程监控需要服务器配置
- 前端可独立请求本地/远程

### 组合命令策略

**决策**: 远程监控使用组合命令一次获取所有信息。

**原因**:
- 减少 SSH 连接次数
- 降低网络延迟影响
- 提高响应速度

### 进程列表限制

**决策**: 默认返回 50 个进程，最多 500 个。

**原因**:
- 大量进程影响渲染性能
- 用户通常关注高占用进程
- 可配置 limit 参数

### 远程进程杀死

**决策**: 前端仅支持本地进程杀死，远程暂不支持。

**原因**:
- 远程杀死需要额外权限验证
- 安全风险较高
- 后续可扩展

---

最后更新: 2026-04-13