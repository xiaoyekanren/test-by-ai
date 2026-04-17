# 发布运行脚本设计

最后更新: 2026-04-17

## 目标

最终发布包用于交付一个不包含前端源码和 `node_modules/` 的可运行目录。发布包内的 `manage.py`、`manage.sh`、`manage.bat` 只负责安装后端依赖、启动已打包的前端静态资源和查看运行状态。

## 发布包结构

`release.py` 生成 `release/test-by-ai-release-时间戳/`，核心内容如下：

- `backend/app/`：后端应用代码。
- `backend/app/frontend_dist/`：已构建的前端静态产物。
- `backend/requirements.txt`：发布运行所需的 Python 依赖。
- `data/app.db`：从示例数据库复制得到的初始运行数据库。
- `manage.py`：发布包内的运行入口。
- `manage.sh`：Linux/macOS 启动包装脚本。
- `manage.bat`：Windows 启动包装脚本。
- `README.md` 和 `RELEASE_INFO.txt`：发布说明和构建元数据。

## Windows 运行流程

Windows 用户在发布包目录中执行：

```bat
manage.bat install
manage.bat start
```

`install`、`start` 和 `restart` 会先确保 `venv/Scripts/python.exe` 存在。若虚拟环境不存在，脚本会查找满足 Python 3.10+ 的解释器，并执行 `python -m venv venv`。

## Batch 变量展开约束

Windows batch 会在进入括号代码块前提前展开 `%VAR%`。因此如果在同一个括号块中先调用子程序设置变量，再使用 `%PYTHON_CMD%`，实际执行时可能仍是空值，导致命令变成 `"" -m venv ...`。

为避免该问题，`manage.bat` 启用 `setlocal EnableExtensions EnableDelayedExpansion`，并在括号块内使用 `!PYTHON_CMD!` 读取 `:find_python` 子程序刚写入的值。括号块外仍可继续使用普通 `%PYTHON_CMD%` 展开。

## 维护要求

- 修改源码根目录 `manage.bat` 的 Python 查找或 venv 创建逻辑时，应同步检查 `release.py` 中的 `RELEASE_RUNTIME_BAT`。
- 修改发布包运行行为时，应同步更新 `write_release_readme()` 生成的发布包 README。
- 若仓库中保留了示例发布包，需要同步修复示例发布包内的 `manage.bat` 和 `README.md`，避免复现已修复问题。
