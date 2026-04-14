# 文档中心

本目录集中存放 IoTDB Test Automation Platform 的说明、设计、计划、测试和待办文档。仓库根目录 `README.md` 仅保留项目入口和快速开始信息。

## 文档导航

| 分类 | 文档 | 内容 |
|------|------|------|
| 开发规范 | [../CLAUDE.md](../CLAUDE.md) | Claude Code 调用的项目规范入口，保留在仓库根目录 |
| 设计文档 | [design/README.md](design/README.md) | 按页面入口组织的设计索引，包含共享架构和调研文档 |
| 测试文档 | [testing/backend-tests-summary.md](testing/backend-tests-summary.md) | 后端测试文件和覆盖范围汇总 |
| 待办事项 | [todos/workflow-editor.md](todos/workflow-editor.md) | 工作流编辑器交互、逻辑和可靠性待办 |
| 待办事项 | [todos/iotdb-cli.md](todos/iotdb-cli.md) | IoTDB CLI、终端体验和日志分屏待办 |
| 待办事项 | [todos/frontend-build.md](todos/frontend-build.md) | 前端构建 chunk size 警告和优化建议 |
| 实施计划 | [superpowers/plans/](superpowers/plans/) | 历史实施计划和任务拆解 |
| 规格设计 | [superpowers/specs/](superpowers/specs/) | 历史规格与 UI/功能设计稿 |

## 目录结构

```text
docs/
├── README.md
├── design/
│   ├── pages/
│   │   ├── app-shell/
│   │   ├── iotdb/
│   │   ├── monitoring/
│   │   ├── servers/
│   │   └── workflows/
│   ├── research/
│   ├── shared/
│   └── README.md
├── testing/
│   └── backend-tests-summary.md
├── todos/
│   ├── frontend-build.md
│   ├── iotdb-cli.md
│   └── workflow-editor.md
└── superpowers/
    ├── plans/
    └── specs/
```

## 维护规则

- 新增页面相关设计文档放入 `docs/design/pages/{page}/`，跨页面架构放入 `docs/design/shared/`，调研对照放入 `docs/design/research/`，并同步更新 [design/README.md](design/README.md)。
- 新增测试说明放入 `docs/testing/`。
- 新增待办记录放入 `docs/todos/`。
- 新增实施计划或规格文档放入 `docs/superpowers/plans/` 或 `docs/superpowers/specs/`。
- 除仓库根目录 `README.md` 作为项目入口、`CLAUDE.md` 作为 Claude Code 调用入口外，新增 Markdown 文档默认放在 `docs/` 下。

---

最后更新: 2026-04-15
