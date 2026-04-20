# IoTDB Test Automation Platform

IoTDB 测试自动化平台，提供服务器管理、可视化工作流编排、远程执行等功能。

## 功能概览

- **服务器管理**: 服务器增删改查、SSH 连接测试、区域分组
- **工作流编辑器**: 可视化拖拽节点、连线设计测试流程
- **工作流执行**: 支持并发执行、实时状态追踪
- **实时监控**: CPU/内存/磁盘/网络信息采集
- **IoTDB 可视化**: CLI、日志、配置查看

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+

### Mac/Linux

```bash
./manage.sh install   # 安装依赖
./manage.sh start     # 启动服务
./manage.sh status    # 查看状态
```

### Windows

```bash
manage.bat start
```

### 访问

启动成功后访问：
- 前端: `http://localhost:5173`
- API 文档: `http://localhost:8000/docs`

## 打包发布

```bash
python3.12 release.py
```

生成可交付目录 `release/test-by-ai-release-{时间戳}/`。

## 更多信息

详细技术说明、API 文档、节点类型等见 [docs/project-overview.md](docs/project-overview.md)。

设计文档见 [docs/design/README.md](docs/design/README.md)。

---

MIT License