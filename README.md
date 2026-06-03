# TestFlow

IoTDB 测试自动化平台，通过可视化拖拽工作流的方式测试 IoTDB，支持服务器管理、工作流编排、远程执行、实时监控和测试用例管理。

## 功能概览

- **服务器管理**: 服务器增删改查、SSH 连接测试、区域分组和忙闲状态
- **工作流编辑器**: 可视化拖拽节点、连线编排、节点配置和执行面板
- **工作流执行**: 支持 DAG、并发执行、区域调度、执行历史和日志追踪
- **实时监控**: CPU、内存、磁盘、网络和进程信息采集
- **IoTDB 可视化**: CLI、日志、配置查看和操作入口

## 快速开始

### 环境要求

- Python 3.11+（最低 3.11，推荐 3.12 / 3.13）
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
- API 文档: `http://localhost:5173/docs`

## 打包发布

```bash
./manage.sh release
```

Windows 可执行 `manage.bat release`。

命令会先执行前端构建，再生成可交付目录 `release/仓库-版本/` 和同名 zip 包。默认版本基于最近 Git tag 生成，格式为 `<tag>-snapshot-YYYYMMDD`（例如 `testflow-0.3-snapshot-20260515`）。正式发布请通过 `--version` 指定纯版本号，例如 `./manage.sh release --version 0.3` 会生成 `release/testflow-0.3.zip`。

## 工作流进程清理

工作流默认会在执行结束时清理本次启动的远端进程，覆盖 IoTDB、IoTDB AINode、IoTDB 集群和 IoT Benchmark 启动节点。清理会先调用登记的停止命令，再按 PID、命令行和登记安装目录下的进程 cwd 做兜底，避免启动失败但进程未监听端口时残留。需要保留进程时，可在工作流编辑器顶部打开“进程常驻”选项。

## 文档入口

- [文档中心](docs/README.md)
- [项目详细说明](docs/project-overview.md)
- [设计文档](docs/design/README.md)
- [测试说明](docs/testing/backend-tests-summary.md)
- [项目开发规范](#项目开发规范)
- [Claude 开发协作说明](CLAUDE.md)

## 项目开发规范

本文档记录项目的开发规范和工作流程要求。

### 文档更新规定

**每次更新代码时，必须同步更新相关文档：**

1. **说明文档** - 更新功能说明、使用方法等
2. **设计文档** - 更新架构设计、技术决策等（如果没有则需创建）

#### 文档位置

- 说明文档: 优先放在 `docs/` 目录；根目录 `README.md` 作为项目入口和开发规范入口
- 设计文档: `docs/design/` 目录

#### 文档命名规范

设计文档统一放在 `docs/design/` 目录下，命名格式：

- `docs/design/{模块名}.md` - 模块设计文档
- `docs/design/{功能名}.md` - 功能设计文档

例如：

- `docs/design/workflow-engine.md` - 工作流引擎设计文档
- `docs/design/ssh-executor.md` - SSH 执行器设计文档

#### 更新检查清单

每次代码提交前检查：

- [ ] 代码修改是否涉及新功能？
- [ ] 说明文档是否需要更新？
- [ ] 设计文档是否需要更新？
- [ ] 是否需要创建新的设计文档？

### 测试执行偏好

本仓库后续无论是计划、设计还是快速代码调整，都无需默认执行全量测试。优先做有针对性的局部验证；只有用户明确要求、改动风险很高或发布前需要确认时，才运行全量测试。

### 兼容性策略

项目开发默认不为旧数据、旧 API、旧配置、旧导入导出格式或旧运行时行为做兼容适配。发生破坏性变更时，应在相关说明文档、设计文档或发布说明中标记不兼容点、影响范围和需要用户手动处理的事项。

此规范自 2026-04-10 起生效。

## License

MIT
