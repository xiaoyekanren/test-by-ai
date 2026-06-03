# GitLab Webhook 设计

## 概述

GitLab Webhook 模块允许用户配置规则，当 GitLab 仓库发生 Push 事件时自动触发一个或多个工作流。支持 project / ref pattern 过滤、Secret Token 安全验证、事件记录和执行日志保留。

## API 路由

| 方法 | 路径 | 功能 |
|------|------|------|
| `GET` | `/api/webhooks/gitlab/rules` | 列出所有 webhook 规则 |
| `POST` | `/api/webhooks/gitlab/rules` | 创建规则 |
| `PUT` | `/api/webhooks/gitlab/rules/{id}` | 更新规则 |
| `DELETE` | `/api/webhooks/gitlab/rules/{id}` | 删除规则及其事件 |
| `GET` | `/api/webhooks/gitlab/events` | 查询触发事件记录 |
| `POST` | `/api/webhooks/gitlab/{rule_id}` | GitLab 回调入口 |

## 数据模型

### GitLabWebhookRule

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | 自增主键 |
| `name` | String(100) | 规则名称 |
| `enabled` | Boolean | 是否启用 |
| `workflow_ids` | JSON(List[int]) | 关联的工作流 ID 列表 |
| `project_id` | String(50) | GitLab project ID 过滤（可选） |
| `project_path` | String(300) | GitLab project path 过滤（可选） |
| `ref_patterns` | JSON(List[str]) | 分支匹配 pattern 列表（fnmatch glob） |
| `secret_hash` | String(100) | PBKDF2+salt 加密后的 Secret Token |
| `created_at` | UTCDateTime | 创建时间 |
| `updated_at` | UTCDateTime | 更新时间 |

### GitLabWebhookEvent

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Integer PK | 自增主键 |
| `rule_id` | Integer FK | 关联规则 |
| `event_uuid` | String(100) | GitLab 事件 UUID |
| `project_id` | String(50) | 推送来源项目 ID |
| `project_path` | String(300) | 推送来源项目路径 |
| `ref` | String(300) | 推送分支 |
| `before_sha` / `after_sha` | String(80) | 提交范围 |
| `user_name` / `user_username` | String(100) | 推送人 |
| `status` | String(30) | accepted / ignored / error |
| `execution_ids` | JSON(List[int]) | 触发的执行 ID |
| `error` | Text | 错误信息（过滤未通过或工作流缺失时） |
| `received_at` | UTCDateTime | 接收时间 |

## 安全机制

### Secret Token 验证

```
存储：PBKDF2-HMAC-SHA256 + 16 字节随机 salt，260,000 次迭代
格式：pbkdf2:{salt_hex}:{dk_hex}
验证：constant-time hmac.compare_digest
兼容：支持旧版 sha256:{hex} 格式
```

GitLab 在请求头 `X-Gitlab-Token` 中传递明文 token，后端用 `_verify_secret` 做恒定时间比对。

## 过滤逻辑

触发入口收到 Push Hook 后依次检查：

```
1. Secret Token 验证 → 401
2. X-Gitlab-Event == "Push Hook" → ignored
3. rule.enabled → ignored
4. project_id / project_path 匹配 → ignored
5. ref pattern 匹配（fnmatch glob，自动去除 refs/heads/ 前缀） → ignored
6. workflow_ids 中的工作流是否存在 → error
7. 全部通过 → 创建 Execution 并后台执行
```

一个规则可绑定多个工作流，命中时全部触发。

## 执行日志保留

Webhook 触发的工作流执行完成后：

1. 将 node execution 数据写入 `data/logs/executions/{execution_id}.jsonl`
2. 自动脱敏 password / secret / token 等敏感字段
3. 超长内容截断至 4000 字符
4. 清空 DB 中的 `input_data` / `output_data` 以节省数据库空间
5. 在 `execution.summary` 中记录 `webhook_log_path`

## 工作流执行后清理

所有工作流执行结束后（无论成功/失败/异常），引擎自动：

1. 收集启动节点输出中的 `managed_processes`
2. SSH 执行每个登记进程的 `stop_command`
3. 按 pid 或 `fallback_pattern` 兜底清理残留进程
4. 清理结果记入 `execution.summary.process_cleanup`

工作流开启 `process_resident` 时跳过自动清理，并在 `execution.summary.process_cleanup` 中记录原因。

## 前端管理

设置页面提供 Webhook 管理卡片：

- **规则列表**：ElTable 展示规则名称、启用状态、关联工作流、分支 pattern、Secret 状态
- **操作**：复制 Webhook URL、编辑、删除（二次确认）、启用/禁用切换
- **新建/编辑对话框**：规则名称、工作流选择、project 过滤、ref pattern、Secret Token
- **事件历史**：折叠面板中展示最近触发记录（时间、规则、分支、推送人、状态、执行 ID）

---

文档更新日期：2026-06-02
