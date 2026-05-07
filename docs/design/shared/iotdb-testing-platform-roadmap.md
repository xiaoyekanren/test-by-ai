# IoTDB 自动化测试平台演进设计

## 背景

当前 TestFlow 已具备以下能力：

- 服务器管理、SSH 执行、区域调度
- 工作流编辑器与 DAG 执行引擎
- IoTDB 部署、启停、CLI、集群、Benchmark 节点
- 执行记录、节点执行记录、监控和 IoTDB 可视化入口

这说明项目已经有“自动化执行平台”的底子，但离“自动化测试平台”还差几层关键抽象：

1. 还缺测试资产模型，工作流是底层执行描述，但不是完整测试对象。
2. 还缺环境模型，服务器和 region 解决了执行位置，没解决测试环境定义。
3. 还缺结果模型，执行记录能看过程，但还不足以支撑测试报告、趋势分析和质量门禁。
4. 还缺调度模型，BackgroundTasks 适合当前规模，但难以支撑回归批量任务和资源治理。

因此，后续设计目标不是推翻现有架构，而是在现有执行引擎之上补齐平台层。

## 目标

将项目演进为一个面向 IoTDB 生命周期的自动化测试平台，覆盖：

- 功能测试
- 集群测试
- 升级 / 回滚测试
- Benchmark / 性能测试
- 可靠性 / 故障恢复测试
- 定时回归与质量看板

## 设计原则

### 1. 保留工作流，向上补业务抽象

工作流继续作为底层执行编排模型，不直接废弃。

在其上新增：

- `WorkflowTemplate`：定义可复用的节点编排模板
- `TestCase`：描述一次测试的目标、参数、断言和依赖模板
- `TestSuite`：组织一组 TestCase，用于冒烟、回归、性能和兼容性场景

### 2. 环境与资源解耦

“部署什么”与“部署到哪”应拆开处理：

- 环境模板负责描述 IoTDB 版本、模式、角色、端口、依赖和制品来源
- 资源池负责提供符合约束的服务器集合
- 执行调度器在运行时做绑定

### 3. 结果必须结构化

测试平台不能只保存原始 stdout / stderr，还应沉淀：

- 用例结果
- 断言结果
- 性能指标
- 环境元数据
- 制品版本
- 失败归因标签

### 4. 先单机平台化，再考虑分布式执行

当前以 FastAPI + SQLite + BackgroundTasks 为主的实现仍可继续迭代，先把模型和流程闭环做完整，再评估是否需要：

- 外部调度器
- 消息队列
- 分布式 worker
- 独立时序 / 分析型存储

## 建议的核心对象

### 1. WorkflowTemplate

职责：

- 定义节点结构、默认变量和依赖关系
- 作为测试编排模板复用

建议字段：

- `id`
- `name`
- `category`
- `nodes`
- `edges`
- `default_variables`
- `version`
- `tags`

### 2. EnvironmentTemplate

职责：

- 定义测试环境目标形态，而不是具体机器

建议字段：

- `id`
- `name`
- `iotdb_version`
- `deploy_mode`（standalone / cluster / upgrade）
- `topology`
- `artifact_source`
- `default_config`
- `requirements`（CPU、内存、磁盘、区域、OS）

### 3. TestCase

职责：

- 描述一次可执行测试

建议字段：

- `id`
- `name`
- `template_id`
- `environment_template_id`
- `parameters`
- `assertions`
- `labels`
- `owner`
- `enabled`

### 4. TestSuite

职责：

- 批量组织 TestCase

建议字段：

- `id`
- `name`
- `type`（smoke / regression / performance / upgrade）
- `case_ids`
- `schedule`
- `quality_gate`

### 5. TestRun

职责：

- 对应一次测试执行实例

建议字段：

- `id`
- `suite_id`
- `case_id`
- `execution_id`
- `environment_binding`
- `artifact_version`
- `status`
- `result`
- `started_at`
- `finished_at`
- `summary`

### 6. TestReport

职责：

- 面向测试结果消费，而不是面向执行过程存储

建议字段：

- `id`
- `test_run_id`
- `assertion_results`
- `metrics`
- `error_classification`
- `attachments`
- `html_snapshot`

## 分层架构建议

### 1. 展示层

页面建议逐步围绕测试平台重组：

- 测试工作台
- 用例管理
- 套件管理
- 环境模板
- 资源池
- 执行中心
- 报告中心
- IoTDB 运维视图

其中现有页面可以平滑演进：

- `WorkflowsView` 逐步偏向模板管理
- `ExecutionInsightsView` 逐步偏向执行中心
- `IoTDBView` 保留为专家视图 / 运维辅助页

### 2. 应用层

建议增加以下服务边界：

- `TestCaseService`
- `TestSuiteService`
- `EnvironmentService`
- `SchedulerService`
- `ReportService`
- `ArtifactService`

现有 `ExecutionEngine` 继续作为底层执行内核。

### 3. 执行层

执行层继续沿用当前 DAG 模型，但要补齐这些能力：

- 参数矩阵展开
- 执行队列
- 资源占用与释放
- 节点重试策略
- 日志流与持久化
- 阶段恢复

### 4. 数据层

当前 SQLite 可继续承担开发期和轻量部署场景。

若后续出现以下情况，可以考虑升级：

- 执行数据增长较快
- 报告与趋势分析查询变重
- 定时任务和并发执行显著增多

可以逐步演进到：

- PostgreSQL：核心业务数据
- 对象存储 / 文件目录：日志与附件
- 时序或分析存储：性能指标与趋势数据

## 核心流程建议

### 流程 1：单次测试执行

1. 用户选择 `TestCase`
2. 绑定 `EnvironmentTemplate`
3. 调度器选择可用资源
4. 生成 `TestRun`
5. 展开到底层 `WorkflowTemplate`
6. 调用 `ExecutionEngine`
7. 收集日志、指标、断言结果
8. 生成 `TestReport`

### 流程 2：套件回归

1. 用户或定时器触发 `TestSuite`
2. 按策略展开多个 `TestCase`
3. 调度器控制并发与资源占用
4. 每个用例生成独立 `TestRun`
5. 汇总为 `SuiteReport`
6. 触发通知和质量门禁

### 流程 3：升级 / 回滚测试

1. 环境准备旧版本集群
2. 执行写数和基线检查
3. 执行升级模板
4. 运行升级后断言
5. 需要时执行回滚模板
6. 比较升级前后数据与性能指标

## 近期优先级建议

### 第一阶段：把平台底座补稳

优先落地：

- 认证 / 鉴权
- 凭据加密
- 路径和命令安全校验
- 执行日志持久化
- 执行分页与筛选
- 后端异常处理规范化

收益：

- 系统先可安全使用
- 执行记录可沉淀
- 后续做调度和报告时不需要返工

### 第二阶段：补测试平台核心对象

优先落地：

- `EnvironmentTemplate`
- `TestCase`
- `TestSuite`
- 报告中心
- IoTDB 专项断言

收益：

- 平台从“工作流运行器”升级为“测试资产平台”
- 可以支撑日常回归和版本测试

### 第三阶段：做规模化与质量闭环

优先落地：

- 定时执行
- 执行队列与资源池
- 参数矩阵
- Benchmark 趋势分析
- 通知与质量门禁
- 升级 / 回滚 / 故障注入模板

收益：

- 平台能支撑持续测试
- 结果可直接服务研发和发布决策

## 与现有代码的对应关系

当前代码中最值得保留和扩展的部分：

- `backend/app/services/execution/engine.py`
  - 继续作为底层 DAG 调度核心
- `backend/app/services/execution/handlers/`
  - 继续作为 IoTDB 节点能力扩展入口
- `backend/app/services/execution/server_resolution.py`
  - 可演进为资源调度器的一部分
- `frontend/src/views/ExecutionInsightsView.vue`
  - 可演进为执行中心 / 报告入口
- `frontend/src/views/IoTDBView.vue`
  - 可保留为专家操作页，不必承担平台首页职责

最需要新增而不是继续堆叠的部分：

- 测试资产模型
- 环境模板模型
- 报告与趋势模型
- 定时调度与资源治理

## 结论

这个项目的正确方向不是继续单点加节点、加页面，而是把现有能力抽象成三层：

1. 底层执行层：工作流、节点、SSH、DAG、执行记录
2. 平台编排层：测试用例、套件、环境模板、调度策略
3. 结果消费层：报告、趋势、告警、质量门禁

这样既能复用当前已有代码，也能让后续开发有明确边界，避免把所有业务继续塞进 `Workflow` 和大页面组件里。

---

最后更新: 2026-04-20
