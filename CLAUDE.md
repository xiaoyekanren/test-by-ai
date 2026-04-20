# 项目开发规范

本文件为 Claude Code 调用入口，定义开发规范和工作流程。

## 文档更新规定

**每次更新代码时，必须同步更新相关文档：**

1. **说明文档** - 功能说明、使用方法等，放在 `docs/` 目录
2. **设计文档** - 架构设计、技术决策等，放在 `docs/design/` 目录

### 文档位置

| 文档类型 | 位置 | 说明 |
|----------|------|------|
| 项目入口 | `README.md` | 项目介绍、快速开始、打包命令 |
| 项目详情 | `docs/project-overview.md` | 技术栈、API、节点类型等详细说明 |
| 设计文档 | `docs/design/` | 按页面组织的设计索引 |
| 开发规范 | `CLAUDE.md` | 本文件，Claude Code 调用入口 |

### 更新检查清单

每次代码提交前检查：

- [ ] 代码修改是否涉及新功能？
- [ ] 说明文档是否需要更新？
- [ ] 设计文档是否需要更新？

## 测试执行偏好

不做默认全量测试。优先针对性局部验证；仅用户明确要求、改动风险高或发布前确认时运行全量测试。

## 项目结构要点

```
backend/
  app/api/      # API 路由
  app/models/   # SQLAlchemy 模型
  app/schemas/  # Pydantic 数据模型
  app/services/ # 业务逻辑
  tests/        # pytest 测试

frontend/
  src/views/    # 页面视图
  src/components/workflow/  # 工作流编辑器组件
  src/stores/   # Pinia 状态管理
  src/types/    # TypeScript 类型定义
```

## 关键设计文档

| 功能 | 文档 |
|------|------|
| 区域调度 | `docs/design/pages/servers/region-scheduling.md` |
| 工作流编辑器 | `docs/design/pages/workflows/editor.md` |
| 执行引擎 | `docs/design/pages/workflows/execution-engine.md` |
| 后端架构 | `docs/design/shared/backend-architecture.md` |
| 前端架构 | `docs/design/shared/frontend-architecture.md` |

## 常用命令

```bash
# 后端测试
cd backend && pytest tests/ -v

# 前端类型检查
cd frontend && npm run typecheck

# 前端构建
cd frontend && npm run build

# 发布打包
python3.12 release.py
```

---

此规范自 2026-04-10 起生效，于 2026-04-20 更新。