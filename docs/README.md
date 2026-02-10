# 服务器管理网站

一个基于 Python Flask 和现代前端的服务器管理系统，提供实时的系统监控和管理功能。

## 功能特性

### 当前功能
- **集成监控面板**：一个页面集合了所有系统监控功能
  - 系统资源监控（CPU、内存、磁盘使用率）
  - 进程管理（查看和终止运行中的进程）
  - 网络监控（网络接口和流量统计）
- **服务器管理**：添加、编辑、删除和测试远程服务器连接
- **实时更新**：数据自动刷新，无需手动刷新

### 预留接口（为后续功能设计）
- 服务部署管理接口
- 程序启动/停止接口
- 日志查看接口
- 告警管理接口

## 项目结构

```
program/
├── app.py                    # Flask 后端应用
├── requirements.txt          # Python 依赖
├── run.bat                   # Windows 启动脚本
├── run.sh                    # macOS/Linux 启动脚本
├── templates/                # HTML 模板
│   ├── index.html           # 首页
│   ├── integrated.html       # 集成监控面板
│   └── servers.html         # 服务器管理
└── static/                   # 静态资源
    ├── css/
    │   └── style.css        # 样式表
    └── js/
        ├── api.js           # API 模块
        ├── index.js         # 首页脚本
        └── integrated.js    # 集成监控面板脚本
```

## 安装和运行

### 环境要求
- Python 3.7+
- pip（Python 包管理工具）

### 安装步骤

#### Windows 系统

1. 安装依赖并运行应用（双击运行）：
```bash
run.bat
```

或者手动运行：
```bash
pip install -r requirements.txt
python app.py
```

#### macOS / Linux 系统

1. 给脚本添加执行权限：
```bash
chmod +x run.sh
```

2. 运行启动脚本：
```bash
./run.sh
```

或者手动运行：
```bash
pip install -r requirements.txt
python3 app.py
```

3. 打开浏览器访问：
```
http://localhost:5001
```

### 常见问题

#### macOS 用户

1. **Python3 不可用**：
   - 如果您的系统上只有 Python 2，请先安装 Python 3
   - 使用 Homebrew：`brew install python3`
   - 然后使用 `python3` 替代 `python`

2. **权限问题**：
   - 如果无法执行 `run.sh`，运行：`chmod +x run.sh`

3. **端口被占用**：
   - 如果 5001 端口被占用，编辑 `app.py` 最后一行，改为其他端口号：
   ```python
   app.run(debug=True, host='0.0.0.0', port=8080)
   ```

#### Windows 用户

1. **运行脚本失败**：
   - 双击 `run.bat` 文件
   - 或在 cmd 中运行：`run.bat`

2. **Python 不可用**：
   - 确保 Python 已安装并添加到环境变量中
   - 检查：打开 cmd，输入 `python --version`

3. **pip 找不到**：
   - 如果 pip 不可用，使用：`python -m pip install -r requirements.txt`

## API 文档

### 系统信息接口

#### 获取服务器状态
- **URL**: `/api/server/status`
- **方法**: GET
- **返回**: CPU、内存、磁盘信息

```json
{
  "status": "success",
  "data": {
    "timestamp": "2026-02-07T10:30:00",
    "cpu": {
      "usage": 25.5,
      "count": 8
    },
    "memory": {
      "total": 16000000000,
      "used": 8000000000,
      "available": 8000000000,
      "percent": 50.0
    },
    "disk": {
      "total": 500000000000,
      "used": 250000000000,
      "free": 250000000000,
      "percent": 50.0
    }
  }
}
```

#### 获取进程列表
- **URL**: `/api/server/processes?limit=20&sort_by=memory`
- **方法**: GET
- **参数**:
  - `limit`: 返回进程数量（默认 20）
  - `sort_by`: 排序方式（memory 或 cpu，默认 memory）
- **返回**: 进程列表

#### 获取网络信息
- **URL**: `/api/server/network`
- **方法**: GET
- **返回**: 网络接口和流量统计

#### 获取磁盘分区
- **URL**: `/api/server/disk`
- **方法**: GET
- **返回**: 所有磁盘分区信息

### 进程管理接口

#### 获取进程详情
- **URL**: `/api/process/<pid>`
- **方法**: GET
- **返回**: 指定 PID 的进程详细信息

#### 终止进程
- **URL**: `/api/process/<pid>/kill`
- **方法**: POST
- **返回**: 操作结果

### 服务管理接口（预留）

#### 获取服务列表
- **URL**: `/api/services`
- **方法**: GET
- **返回**: 服务列表

#### 创建服务
- **URL**: `/api/services`
- **方法**: POST
- **请求体**: 服务配置信息
- **返回**: 操作结果

## 前端页面

### 首页 (/)
- 功能概览
- 系统快速统计信息

### 仪表板 (/dashboard)
- CPU 使用率图表
- 内存使用情况图表
- 详细的系统统计信息

### 进程管理 (/processes)
- 进程列表表格
- 按 CPU 或内存排序
- 终止进程功能

### 网络信息 (/network)
- 网络接口详细信息
- 网络流量统计
- 实时数据刷新

## 后续功能规划

该项目设计时已考虑可扩展性，以下功能可以通过添加新的 API 端点来实现：

1. **服务部署**：添加 `/api/services/deploy` 端点
2. **程序启动/停止**：添加 `/api/programs/*` 相关端点
3. **日志管理**：添加 `/api/logs/*` 相关端点
4. **告警管理**：添加 `/api/alerts/*` 相关端点
5. **用户认证**：集成认证模块保护接口
6. **数据库存储**：添加历史数据存储功能

## 技术栈

- **后端**: Flask、psutil
- **前端**: HTML5、CSS3、JavaScript、Chart.js
- **通信**: REST API、CORS

## 许可证

MIT
