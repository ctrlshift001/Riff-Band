# GBA Industry Analysis 项目实现说明

## 1. 项目定位
该项目是一个面向粤港澳大湾区产业研究的多智能体执行框架。系统读取任务描述后，由主智能体进行任务分解，调用子智能体完成资料检索、证据记录与报告写作，并通过质量门禁后结束任务。

当前实现目标偏向“可运行的研究工作流原型”，重点在于：
- 动态任务委派（单任务/并行任务）
- 工具权限隔离
- 研究过程留痕（findings.jsonl + 日志）
- 报告最小质量检查

## 2. 当前架构与执行链路
核心链路如下：
`run_agents.py -> build_gba_analysis_project -> MainOrchestratorAgent -> delegate_task/delegate_tasks -> ResearchSubAgent -> Environment/Tools -> complete_task`

关键模块职责：
- `run_agents.py`：读取配置和终端输入，启动项目运行。
- `project/build_project.py`：组装环境、工具、主/子智能体与默认策略。
- `agents/main_agent.py`：负责决策下一步动作（继续委派或收敛完成）。
- `tools/delegate.py`：执行子任务委派，支持并行、工具限制和结果汇总。
- `agents/sub_agent.py`：执行具体研究子任务并调用工具。
- `project/tools.py`：本地检索、文件读取、联网搜索、证据记录、报告写入。
- `tools/complete_task.py`：执行收尾质量门禁。

## 3. 子任务编排机制（已实现）
项目使用 I/C/T/M（Instruction/Context/Tools/Model）思路做动态子任务配置，具体由主智能体在运行中确定。

当前已实现策略包括：
- 子任务画像推断：`policy_research/company_research/.../general_research`。
- 工具包默认分配：基于画像从 `subtask_toolkits` 选择工具。
- 模型路由：支持 `model_routing` 元数据；若不命中则回退到 `sub_models[0]`。
- 并行安全约束：并行阶段禁止 `write_report_section`，避免并发写报告冲突。

## 4. 并行执行机制（已实现）
`delegate_tasks` 通过 `asyncio.gather + Semaphore` 执行并发子任务，支持 `max_concurrency`。

为避免并行写同一输出文件导致冲突，当前实现做了隔离：
- 每个并行任务会创建独立环境副本与独立输出目录；
- 每个任务写入自己的 `findings.jsonl`；
- 任务结束后再合并回主 `findings.jsonl`（按 `dedup_key` 去重）。

日志层面已支持按 `task_x` 标识并行子任务，便于定位每条子任务日志来源。

## 5. 数据与工具链（已实现）
当前可用工具包括：
- 本地资料：`list_sources`、`search_sources`、`read_source`、`read_sources`
- 联网搜索：`web_search`（Serper，依赖 `SERPER_API_KEY`）
- 证据沉淀：`record_finding`（写入结构化 `findings.jsonl`）
- 报告生成：`write_report_section`（按章节写入/覆盖）

当前输入源以本地资料 + Serper 检索摘要为主，适合原型验证与中小规模研究任务。

## 6. 质量门禁（已实现）
`complete_task` 会在任务完成前执行检查，主要包括：
- 报告文件存在且非空；
- 二级标题数量下限；
- 必要章节是否齐全；
- findings 数量是否达到阈值；
- findings 证据覆盖率检查；
- 报告中是否包含显式链接（http/https）。

只有通过质量门禁后，主流程才会返回完成状态。

## 7. 当前已知问题（基于现状）
基于当前实现，主要问题集中在：
- 模型路由虽然支持配置，但默认策略仍倾向 `sub_models[0]`，多模型分工尚未充分发挥。
- 联网搜索目前单一依赖 Serper，缺少内建 fallback 与统一检索抽象层。
- 工具生态仍以通用检索/读写为主，行业数据库与结构化数据连接器不足。
- 报告质量门禁是“规则型最小检查”，缺少更强的一致性与证据链校验。
- 人机协同仍偏弱，当前主流程是一次输入后自动跑完，交互式审阅与中途干预能力有限。

