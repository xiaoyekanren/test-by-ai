# 项目开发规范

本文件是 Claude Code 调用入口，记录项目结构、文档维护、验证命令和协作约定。

## 项目定位

IoTDB Test Automation Platform 是一个面向 IoTDB 测试自动化的 OpsCenter，核心能力包括服务器管理、可视化工作流编排、远程 SSH 执行、监控、IoTDB 可视化和发布包交付。

## 文档更新规定

每次修改代码时，必须同步判断是否需要更新说明文档和设计文档。

| 文档类型 | 位置 | 说明 |
|----------|------|------|
| 项目入口 | `README.md` | 项目介绍、快速开始、打包命令、文档入口 |
| 文档中心 | `docs/README.md` | 运行管理、发布说明、文档导航和维护规则 |
| 项目详情 | `docs/project-overview.md` | 技术栈、页面入口、API、节点类型和项目结构 |
| 设计文档 | `docs/design/` | 页面设计、共享架构、服务设计、调研文档 |
| 测试文档 | `docs/testing/` | 测试文件、覆盖范围、运行方式 |
| 待办文档 | `docs/todos/` | 已知待办、优化建议和后续计划 |
| 开发规范 | `CLAUDE.md` | 本文件，Claude Code 调用入口 |

根目录 `README.md` 保持简洁；非核心说明迁移到 `docs/README.md` 或 `docs/project-overview.md`。历史 AI 计划目录不再作为项目文档入口。

## 项目结构要点

```text
backend/
  app/api/       # API 路由
  app/models/    # SQLAlchemy 模型
  app/schemas/   # Pydantic 数据模型
  app/services/  # execution_engine、monitoring、ssh 等业务逻辑
  tests/         # pytest 测试

frontend/
  src/views/     # 页面视图
  src/components/workflow/  # 工作流编辑器组件
  src/stores/    # Pinia 状态管理
  src/types/     # TypeScript 类型定义

docs/
  design/        # 设计文档
  testing/       # 测试说明
  todos/         # 待办记录
```

## 关键设计文档

| 功能 | 文档 |
|------|------|
| 应用框架和首页 | `docs/design/pages/app-shell/ui-layout.md` |
| 服务器区域调度 | `docs/design/pages/servers/region-scheduling.md` |
| 工作流编辑器 | `docs/design/pages/workflows/editor.md` |
| 工作流执行引擎 | `docs/design/pages/workflows/execution-engine.md` |
| IoT Benchmark 异步节点 | `docs/design/pages/workflows/iot-benchmark-async-node.md` |
| IoTDB 可视化 | `docs/design/pages/iotdb/visualization.md` |
| 监控服务 | `docs/design/pages/monitoring/service.md` |
| 后端架构 | `docs/design/shared/backend-architecture.md` |
| 前端架构 | `docs/design/shared/frontend-architecture.md` |
| SSH 服务 | `docs/design/shared/ssh-service.md` |
| 发布运行脚本 | `docs/design/shared/release-runtime.md` |

## 常用命令

```bash
# 安装依赖
./manage.sh install

# 启动服务
./manage.sh start

# 检查服务状态
./manage.sh status

# 后端测试
cd backend && .venv/bin/python -m pytest tests/ -v

# 收集测试数量
cd backend && .venv/bin/python -m pytest --collect-only -q

# 前端类型检查
cd frontend && npm run typecheck

# 前端构建
cd frontend && npm run build

# 发布打包
python3.12 release.py
```

## 测试执行偏好

不默认运行全量测试。优先做与改动相关的局部验证；只有用户明确要求、改动风险高、发布前确认或共享核心逻辑变更时，才运行全量测试。

文档类改动至少执行：

```bash
git diff --check
git status --short
```

## 提交前检查清单

- [ ] 根 README 是否仍然只保留入口级信息？
- [ ] 新增或迁移文档是否已更新 `docs/README.md` 或 `docs/design/README.md`？
- [ ] 设计变更是否落在 `docs/design/pages/`、`docs/design/shared/` 或 `docs/design/research/` 的合适位置？
- [ ] 测试变更是否更新 `docs/testing/backend-tests-summary.md`？
- [ ] 是否仍有历史 AI 计划文档或无用工具目录受版本控制？
- [ ] 是否检查过冲突标记和无效链接？

---

此规范自 2026-04-10 起生效，于 2026-04-20 更新。
