# IoTDB Test Automation Platform

IoTDB 测试自动化平台，提供服务器管理、可视化工作流编排、远程执行、实时监控和 IoTDB 可视化能力。

浏览器页面标题统一使用 `OpsCenter`。

## 功能概览

- **服务器管理**: 服务器增删改查、SSH 连接测试、区域分组和忙闲状态
- **工作流编辑器**: 可视化拖拽节点、连线编排、节点配置和执行面板
- **工作流执行**: 支持 DAG、并发执行、区域调度、执行历史和日志追踪
- **实时监控**: CPU、内存、磁盘、网络和进程信息采集
- **IoTDB 可视化**: CLI、日志、配置查看和操作入口

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+（包含 npm）

### Mac/Linux

```bash
./manage.sh install
./manage.sh start
./manage.sh status
```

### Windows

```bat
manage.bat install
manage.bat start
manage.bat status
```

启动成功后访问：

- 前端: `http://localhost:5173`
- API 文档: `http://localhost:8000/docs`

## 打包发布

```bash
./manage.sh release
```

Windows 可执行 `manage.bat release`。

命令会先执行前端构建，再生成可交付目录 `release/仓库-版本/` 和同名 zip 包。默认版本为 `snapshot-YYYY-MM-DD`，例如 `test-by-ai-snapshot-2026-04-20`；正式版本可通过 `--version` 指定。

## 文档入口

- [文档中心](docs/README.md)
- [项目详细说明](docs/project-overview.md)
- [设计文档](docs/design/README.md)
- [测试说明](docs/testing/backend-tests-summary.md)
- [开发规范](CLAUDE.md)

## License

MIT
