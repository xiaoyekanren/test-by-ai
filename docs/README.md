# 文档中心

本目录集中存放 IoTDB Test Automation Platform 的说明、设计、测试和待办文档。仓库根目录 `README.md` 仅保留项目入口、快速启动和关键链接；非核心说明统一迁移到本目录。

## 文档导航

| 分类 | 文档 | 内容 |
|------|------|------|
| 开发规范 | [../CLAUDE.md](../CLAUDE.md) | Claude Code 调用入口、文档更新要求、常用命令 |
| 项目说明 | [project-overview.md](project-overview.md) | 技术栈、页面入口、API、节点类型、运行和发布说明 |
| 设计文档 | [design/README.md](design/README.md) | 页面、共享能力和调研文档索引 |
| 运行发布 | [design/shared/release-runtime.md](design/shared/release-runtime.md) | 发布包结构、跨平台运行脚本和 Windows venv 创建注意事项 |
| 测试文档 | [testing/backend-tests-summary.md](testing/backend-tests-summary.md) | 后端测试文件、覆盖范围和运行方式 |
| 待办事项 | [todos/workflow-editor.md](todos/workflow-editor.md) | 工作流编辑器交互、逻辑和可靠性待办 |
| 待办事项 | [todos/iotdb-cli.md](todos/iotdb-cli.md) | IoTDB CLI、终端体验和日志分屏待办 |
| 待办事项 | [todos/frontend-build.md](todos/frontend-build.md) | 前端构建 chunk size 警告和优化建议 |

## 目录结构

```text
docs/
├── README.md                      # 文档导航索引
├── project-overview.md            # 项目详细说明
├── design/
│   ├── README.md                  # 设计文档索引
│   ├── pages/                     # 页面相关设计
│   │   ├── app-shell/
│   │   ├── iotdb/
│   │   ├── monitoring/
│   │   ├── servers/
│   │   └── workflows/
│   ├── research/                  # 调研文档
│   └── shared/                    # 共享架构、服务和发布设计
├── testing/
│   └── backend-tests-summary.md
└── todos/
    ├── frontend-build.md
    ├── iotdb-cli.md
    └── workflow-editor.md
```

## 运行与管理

首次部署建议先执行 `install` 检查 Python / Node.js 环境并安装依赖；之后执行 `start` 启动服务。`start` 和 `restart` 会自动补齐缺失的后端和前端依赖。Mac/Linux 可通过 `PYTHON_BIN=/path/to/python ./manage.sh install` 指定 Python。

| 命令 | 描述 |
|------|------|
| `start` | 启动所有服务 |
| `stop` | 停止所有服务 |
| `restart` | 重启所有服务 |
| `status` | 查看服务状态 |
| `install` | 安装后端、前端依赖 |
| `check` | 检查环境、项目文件、依赖状态和端口占用 |

## 发布说明

源码目录执行：

```bash
./manage.sh release
```

Windows 可执行：

```bat
manage.bat release
```

发布命令会先构建前端，再把运行所需文件收集到 `release/仓库-版本/`，并生成带同名顶层目录的 `release/仓库-版本.zip`。版本默认取最近的 Git tag；如需手动指定，可执行 `./manage.sh release --version 0.1.0`。

发布包默认包含：

- `backend/app/` 与 `backend/requirements.txt`
- 构建后的前端产物 `backend/app/frontend_dist/`
- 发布包专用的 `manage.py`、`manage.sh`、`manage.bat`
- `README.md`
- `RELEASE_INFO.txt`
- `data/app.db`

发布包默认不包含：

- `venv/`
- `frontend/src/` 和前端配置文件
- `frontend/node_modules/`
- `data/logs/` 里的运行日志

发布包目录和 zip 命名规则：

- 文件夹: `仓库-版本/`，例如 `test-by-ai-0.1/`
- zip 包: `仓库-版本.zip`，例如 `test-by-ai-0.1.zip`

发布包在 Windows 上使用 `manage.bat install` 创建 `venv/` 并安装后端依赖。脚本在括号代码块内使用延迟变量展开读取 Python 解析结果，避免首次创建虚拟环境时把 Python 命令提前展开为空。

## 清理结果

- 历史 AI 计划和规格文档已从版本控制中移除，文档索引不再引用旧目录。
- 当前没有受版本控制的 `tools/` 目录或 `tools/` 文件；无需保留额外工具说明。
- 本地生成目录、调试缓存、`release/`、`frontend/dist/` 和依赖缓存不属于文档中心内容，继续由 `.gitignore` 管理。

## 维护规则

- 根目录 `README.md` 只保留项目介绍、快速启动、发布命令和文档入口。
- 新增页面相关设计文档放入 `docs/design/pages/{page}/`，跨页面架构、服务和运行机制放入 `docs/design/shared/`，调研对照放入 `docs/design/research/`，并同步更新 [design/README.md](design/README.md)。
- 新增测试说明放入 `docs/testing/`。
- 新增待办记录放入 `docs/todos/`。
- 不再新增历史 AI 计划目录；阶段性计划若确需保留，优先整理为 `docs/todos/` 或对应设计文档。
- 除仓库根目录 `README.md` 作为项目入口、`CLAUDE.md` 作为 Claude Code 调用入口外，新增 Markdown 文档默认放在 `docs/` 下。

---

最后更新: 2026-04-20
