# 文档中心

本目录集中存放 IoTDB Test Automation Platform 的说明、设计、测试和待办文档。仓库根目录 `README.md` 仅保留项目介绍和快速开始信息。

## 文档导航

| 分类 | 文档 | 内容 |
|------|------|------|
| 开发规范 | [../CLAUDE.md](../CLAUDE.md) | Claude Code 调用的项目规范入口，保留在仓库根目录 |
| 项目说明 | [project-overview.md](project-overview.md) | 项目详细介绍、技术栈、API 文档、节点类型等 |
| 设计文档 | [design/README.md](design/README.md) | 按页面入口组织的设计索引，包含共享架构和调研文档 |
| 测试文档 | [testing/backend-tests-summary.md](testing/backend-tests-summary.md) | 后端测试文件和覆盖范围汇总 |
| 待办事项 | [todos/workflow-editor.md](todos/workflow-editor.md) | 工作流编辑器交互、逻辑和可靠性待办 |
| 待办事项 | [todos/iotdb-cli.md](todos/iotdb-cli.md) | IoTDB CLI、终端体验和日志分屏待办 |
| 待办事项 | [todos/frontend-build.md](todos/frontend-build.md) | 前端构建 chunk size 警告和优化建议 |

## 目录结构

```text
docs/
├── README.md                      # 文档导航索引
├── project-overview.md            # 项目详细说明（从根 README.md 迁移）
├── design/
│   ├── README.md                  # 设计文档索引
│   ├── pages/                     # 页面相关设计
│   │   ├── app-shell/
│   │   ├── iotdb/
│   │   ├── monitoring/
│   │   ├── servers/
│   │   └── workflows/
│   ├── research/                  # 调研文档
│   └── shared/                    # 共享架构设计
├── testing/
│   └── backend-tests-summary.md
└── todos/
    ├── frontend-build.md
    ├── iotdb-cli.md
    └── workflow-editor.md
```

## 维护规则

- 新增页面相关设计文档放入 `docs/design/pages/{page}/`，跨页面架构放入 `docs/design/shared/`，调研对照放入 `docs/design/research/`，并同步更新 [design/README.md](design/README.md)。
- 新增测试说明放入 `docs/testing/`。
- 新增待办记录放入 `docs/todos/`。
- 除仓库根目录 `README.md` 作为项目入口、`CLAUDE.md` 作为 Claude Code 调用入口外，新增 Markdown 文档默认放在 `docs/` 下。

---

最后更新: 2026-04-20