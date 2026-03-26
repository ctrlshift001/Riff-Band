# AOrchestra 工程化划分建议与并发 SubAgent 路线图

## 1. 背景

当前仓库更像论文代码与 benchmark 适配代码的集合，而不是一个面向长期演进的应用工程项目。  
这不是坏事，说明它已经完成了研究验证阶段的核心目标；但如果后续要持续做“粤港澳大湾区产业研究 Agent”，目录结构、模块边界和调度能力都需要进一步工程化。

本路线图聚焦两件事：

1. 给出更适合后续产品化的目录划分建议
2. 规划“单任务内多 SubAgent 并发执行”的第一阶段实现方案

本阶段采用的方案是：

- MainAgent 负责产业研究任务拆解与总控
- MainAgent 一次生成多个研究子任务
- 多个 SubAgent 在隔离环境中并发执行
- 最终由汇总阶段统一生成研究报告
- 接口层面预留未来升级为 DAG 调度的空间

---

## 2. 当前目录存在的主要问题

### 2.1 研究代码、框架代码、应用代码混在一起

当前仓库里同时存在：

- benchmark 适配层
- 通用 agent 框架
- demo
- CLI 入口
- 实验性脚本

这会导致几个问题：

- 新功能应该改哪里，不够直观
- benchmark 代码和产品代码边界不清
- demo 代码容易反向污染核心框架
- 后续扩展应用场景时，目录语义不够稳定

### 2.2 “应用层”还没有成为一级概念

如果未来主线是“产业研究 Agent”，那应用层能力应该显式存在，例如：

- 研究任务规划
- 子任务模板
- 报告汇总
- 研究结果结构化存储
- 工作区隔离

当前这些能力没有独立分层，后续会越来越难维护。

### 2.3 调度能力还偏 benchmark-style

现在的主调度链路更偏：

- 生成一个 action
- 执行一个工具
- 再进入下一轮

这适合单 SubAgent 串行委派，但不适合“多个研究员并行调研”的产品场景。

---

## 3. 推荐的目录划分思路

本阶段不建议一口气大重构，而是建议按“新增应用层，再逐步迁移”的方式推进。

### 3.1 目标结构

建议中期演进为类似下面的结构：

```text
.
├── aorchestra/                 # 核心编排框架
│   ├── core/                   # MainAgent、SubAgent、通用调度抽象
│   ├── orchestration/          # 任务规划、并发调度、状态管理
│   ├── tools/                  # 通用工具封装
│   ├── prompts/                # 通用 prompt
│   ├── runtime/                # workspace、结果、执行上下文管理
│   └── config/                 # 核心框架配置
│
├── benchmarks/                 # benchmark 相关逻辑
│   ├── gaia/
│   ├── swebench/
│   ├── terminalbench/
│   └── common/
│
├── apps/                       # 应用层
│   └── industry_research/
│       ├── planner/            # 产业研究任务拆解
│       ├── prompts/            # 产业研究专用 prompt
│       ├── schemas/            # 子任务/结果/report schema
│       ├── agents/             # 政策、公司、财务、新闻等模板
│       ├── aggregator/         # 报告汇总
│       ├── connectors/         # 政策/企业/新闻/财报等数据源
│       └── cli/                # 产业研究应用入口
│
├── demo/                       # 演示代码
├── docs/                       # 文档与 roadmap
├── config/                     # 项目级配置
└── scripts/                    # 辅助脚本
```

### 3.2 现实可落地的第一步

当前不必马上大改目录。第一阶段更建议：

- 保留现有 `aorchestra/`
- 保留现有 `benchmark/`
- 新增 `apps/industry_research/`
- 把产业研究方向的逻辑尽量放进 `apps/industry_research/`
- 尽量避免继续把应用逻辑直接塞进 `demo/` 或 `aorchestra/tools/`

### 3.3 第一阶段新增目录建议

第一阶段可以先引入：

```text
apps/
└── industry_research/
    ├── __init__.py
    ├── planner/
    ├── prompts/
    ├── schemas/
    ├── runtime/
    ├── aggregator/
    └── cli/
```

其中建议职责如下：

- `planner/`
  - 负责让 MainAgent 生成研究子任务
  - 负责定义扇出式子任务结构

- `prompts/`
  - 放产业研究编排器 prompt
  - 放政策、公司、产业链、新闻、财务等子任务 prompt 模板

- `schemas/`
  - 定义 `ResearchSubtask`
  - 定义 `ResearchSubtaskResult`
  - 定义 `ResearchReport`

- `runtime/`
  - 管理每个 SubAgent 的独立 workspace
  - 管理任务运行目录、输出路径、结果索引

- `aggregator/`
  - 负责最终汇总
  - 负责 markdown 报告生成

- `cli/`
  - 提供面向产业研究应用的入口

---

## 4. 并发 SubAgent 的目标形态

### 4.1 本阶段目标

本阶段希望支持这样的工作流：

1. 用户输入一个产业研究任务
2. MainAgent 作为“产业研究 AI 编排器”生成多个子任务
3. 系统并发创建多个 SubAgent
4. 每个 SubAgent 在独立上下文与独立 workspace 中执行
5. 全部结果收集完成后，由汇总阶段生成最终报告

### 4.2 为什么先做 Fan-out / Fan-in

当前最适合的实现路线是：

- 先做并发扇出 Fan-out
- 再做结果汇总 Fan-in

原因是：

- 改动范围可控
- 非常契合产业研究场景
- 容易验证
- 容易演示
- 后续升级为 DAG 调度时可以复用数据结构

---

## 5. 第一阶段功能设计

### 5.1 MainAgent 新角色

建议将 MainAgent 的系统角色明确为：

> 你是一个专注粤港澳大湾区产业研究的 AI 编排器。你的职责是拆解研究任务、为每个子任务分配上下文、工具和模型，并组织最终报告。

MainAgent 第一阶段不再只输出单个 `delegate_task`，而是优先支持输出一组结构化子任务。

### 5.2 子任务结构

建议第一阶段就把结构设计成可演进的 schema：

```json
{
  "id": "policy_research",
  "title": "政策研究",
  "instruction": "调研近两年粤港澳大湾区机器人与智能制造相关政策",
  "context": "聚焦深圳、广州、东莞、珠海等核心城市",
  "tools": ["GoogleSearchAction", "ExtractUrlContentAction", "ReadFile", "WriteFile"],
  "model": "openai/gpt-4o-mini",
  "workspace": "runs/<run_id>/policy_research",
  "output_schema": "research_note",
  "depends_on": []
}
```

建议字段：

- `id`
- `title`
- `instruction`
- `context`
- `tools`
- `model`
- `workspace`
- `output_schema`
- `depends_on`

说明：

- 当前阶段 `depends_on` 一律允许为空
- 但这个字段必须保留，为 DAG 升级做准备

### 5.3 并发调度层

建议新增一个“研究任务运行器”，负责：

- 接收 MainAgent 生成的 `subtasks`
- 为每个 subtask 构造独立运行上下文
- 并发执行
- 收集结果
- 交给汇总层

第一阶段可采用：

- `asyncio.create_task`
- `asyncio.gather`
- 可选 `Semaphore` 控制最大并发数

### 5.4 子 Agent 隔离策略

并发要成立，隔离必须先做好。

至少需要三层隔离：

#### 上下文隔离

每个 SubAgent 只拿自己的：

- `instruction`
- `context`
- 必要的原始任务背景

不能共享一个不断被覆盖的全局 instruction。

#### workspace 隔离

每个 SubAgent 写入单独目录，例如：

```text
demo/workspace/runs/<run_id>/policy_research/
demo/workspace/runs/<run_id>/company_research/
demo/workspace/runs/<run_id>/news_research/
```

这样可以避免：

- 文件互相覆盖
- 输出混乱
- 调试困难

#### 环境实例隔离

当前 `delegate.py` 里存在临时修改 `env.instruction` 的逻辑，这在并发下是不安全的。  
因此第一阶段必须改成：

- 每个 SubAgent 拥有独立 env 实例
- 或者 env 变为无共享状态的 task-scoped runtime

结论是：

> 第一阶段不要让多个 SubAgent 复用同一个可变 env。

### 5.5 结构化结果输出

每个 SubAgent 不应只返回自由文本，而应返回结构化结果，例如：

```json
{
  "subtask_id": "policy_research",
  "status": "done",
  "summary": "完成政策梳理",
  "key_findings": [
    "深圳在机器人产业支持上更强调场景落地",
    "东莞偏制造业升级和装备智能化"
  ],
  "sources": [
    "https://...",
    "https://..."
  ],
  "artifacts": [
    "runs/<run_id>/policy_research/policy_report.md"
  ]
}
```

这样后续汇总层会稳定很多。

---

## 6. 建议的实现拆分

### 阶段 0：准备层

目标：

- 不改原 benchmark 主链路
- 在应用层新增独立实现

建议动作：

- 新增 `apps/industry_research/`
- 新增并发调度 schema
- 新增独立 workspace 运行目录方案

### 阶段 1：子任务规划

目标：

- 让 MainAgent 一次生成多个子任务

建议动作：

- 新增产业研究主 prompt
- 输出结构改为 `subtasks[]`
- 支持 4 到 6 个标准研究维度

推荐首批维度：

- 政策
- 公司
- 产业链
- 新闻舆情
- 财务与指标
- 汇总结论

### 阶段 2：并发执行器

目标：

- 多个 SubAgent 并发运行

建议动作：

- 新增 `ParallelSubtaskRunner`
- 用 `asyncio.gather` 并发调度
- 支持 `max_concurrency`
- 每个 subtask 独立 env / workspace

### 阶段 3：结果汇总

目标：

- 将多个结果整合成报告

建议动作：

- 新增 `ReportAggregator`
- 汇总结构化结果
- 输出 markdown 报告
- 记录引用来源和产出文件

### 阶段 4：兼容 DAG 的接口预留

目标：

- 当前还是 Fan-out / Fan-in
- 但为 DAG 升级留钩子

建议动作：

- 保留 `depends_on`
- 保留 `status`
- 保留 `result_ref`
- 调度器抽象为：
  - `plan_subtasks()`
  - `run_subtasks()`
  - `aggregate_results()`

这样未来只需要把 `run_subtasks()` 的内部调度逻辑从“全量并发”替换成“按依赖调度”。

---

## 7. 代码层建议改动点

### 7.1 尽量新增，不要硬改死旧逻辑

为了不破坏现有 benchmark 链路，建议采用“新增应用层模块”的方式，而不是直接把现有 `delegate_task` 改成只服务产业研究。

### 7.2 推荐新增的核心模块

建议新增如下模块：

```text
apps/industry_research/schemas/subtask.py
apps/industry_research/planner/main_orchestrator.py
apps/industry_research/runtime/workspace_manager.py
apps/industry_research/runtime/subtask_env_factory.py
apps/industry_research/runtime/parallel_runner.py
apps/industry_research/aggregator/report_aggregator.py
apps/industry_research/cli/main.py
```

### 7.3 第一阶段尽量少碰的模块

尽量避免第一阶段直接大改：

- benchmark 层
- benchmark runner 主逻辑
- 通用 benchmark env

第一阶段更适合：

- 在应用层复用现有能力
- 必要时给 `aorchestra/` 做小范围抽象补丁

### 7.4 可能需要最小改动的旧模块

以下旧模块可能需要少量改造：

- `aorchestra/main_agent.py`
  - 支持批量子任务规划模式

- `aorchestra/tools/delegate.py`
  - 抽离出可复用的 SubAgent 创建逻辑
  - 不再依赖共享 env 的临时 instruction 覆盖

- `demo/demo_real_env.py`
  - 改造成可指定 workspace 的任务级 env

- `demo/demo_real_terminal.py`
  - 适配产业研究场景入口

---

## 8. 第一阶段里程碑

### Milestone 1：规划可跑通

验收标准：

- 输入一个产业研究任务
- MainAgent 能生成多个结构化子任务

### Milestone 2：并发可跑通

验收标准：

- 至少 3 个 SubAgent 能并发执行
- 各自输出到独立 workspace
- 不发生输出互相覆盖

### Milestone 3：汇总可交付

验收标准：

- 能自动生成一份 markdown 报告
- 报告含各维度小节
- 报告可附带来源和子任务产物路径

### Milestone 4：为 DAG 升级留好接口

验收标准：

- schema 中保留 `depends_on`
- 调度器接口不写死为“固定并发”

---

## 9. 推荐结论

如果目标是尽快把项目推进到“粤港澳大湾区产业研究 Agent”的第一版可演示原型，那么推荐策略是：

1. 不先做大重构，先新增 `apps/industry_research/`
2. MainAgent 先升级成“产业研究 AI 编排器”
3. 第一阶段采用 Fan-out / Fan-in 并发模式
4. 每个 SubAgent 严格上下文隔离、workspace 隔离、env 隔离
5. 用结构化结果做汇总
6. 在 schema 和调度器接口上预留 DAG 升级空间

一句话总结：

> 先把“多个研究员并发调研、统一汇总出报告”的主路径跑通，再把调度器从批量并发升级为依赖驱动的 DAG 工作流。
