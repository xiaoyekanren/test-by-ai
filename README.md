# 服务器管理与工作流平台

一个基于 Flask + 原生前端的服务器管理系统，提供本机与远程服务器监控、服务器资产管理，以及可视化工作流编排与执行。

## 功能概览

- 实时监控：CPU / 内存 / 磁盘 / 网络信息
- 进程管理：查看进程详情与终止进程
- 服务器管理：增删改查、连接测试、标签分组
- SSH 远程采集：通过 SSH 代理采集远程主机数据
- 工作流编辑器：拖拽节点、连线、保存/加载与并发执行

## 页面入口

- `/` 首页概览
- `/integrated` 集成监控面板（多主机）
- `/servers` 服务器管理
- `/workflow` 工作流编辑器

## 快速开始

### 环境要求

- Python 3.8+
- pip

### 安装依赖

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
python app.py
```

或使用脚本：

```bash
./run.sh
```

Windows:

```bash
run.bat
```

启动后访问：

```
http://localhost:5001
```

## 核心 API（节选）

### 本机监控

- `GET /api/server/status` 获取 CPU/内存/磁盘信息
- `GET /api/server/processes?limit=20&sort_by=memory` 获取进程列表
- `GET /api/server/network` 获取网络信息
- `GET /api/server/disk` 获取磁盘分区

### 进程管理

- `GET /api/process/<pid>` 获取进程详情
- `POST /api/process/<pid>/kill` 终止进程

### 服务器管理

- `GET /api/servers` 列表
- `POST /api/servers` 新增
- `GET /api/servers/<id>` 详情
- `PUT /api/servers/<id>` 更新
- `DELETE /api/servers/<id>` 删除
- `POST /api/servers/<id>/test` 连接测试

### 远程代理（SSH）

- `GET /api/servers/<id>/proxy/server/status`
- `GET /api/servers/<id>/proxy/server/processes`
- `POST /api/servers/<id>/proxy/server/process/<pid>/kill`
- `GET /api/servers/<id>/proxy/server/network`
- `GET /api/servers/<id>/proxy/server/disk`

### 工作流

- `GET /api/workflows`
- `POST /api/workflows`
- `GET /api/workflows/<id>`
- `PUT /api/workflows/<id>`
- `DELETE /api/workflows/<id>`

## 技术栈

- 后端：Flask、SQLite、psutil、paramiko
- 前端：原生 HTML/CSS/JavaScript

## 项目结构

```
program/
├── app.py
├── requirements.txt
├── run.sh
├── run.bat
├── servers.db
├── templates/
├── static/
│   ├── css/
│   └── js/
└── README.md
```
