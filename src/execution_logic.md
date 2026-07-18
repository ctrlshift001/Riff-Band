# AI4MS 兼容 Runtime 执行逻辑

本文档说明 AI4MS 当前复用的 RiffBand Runtime：MainAgent 三阶段控制、子 Agent 会话复用、并发委派和日志约定。它描述的是已经实现的执行层，不是用户直接面对的产品流程；MS 垂直工作台的九步 ProjectState、ResearchProtocol、G0-G5、Revision/Approval、Runner 和 Web 服务以 `docs/` 中的新文档为准。

## 1. 启动与配置

项目通常通过以下命令启动：

```bash
python run_agents.py --config aorchestra.yaml
```

`aorchestra.yaml` 提供主模型、候选 `sub_models`、最大并行子任务数、子任务最大步数、搜索工具、输出目录等运行参数。运行时会构建 `TaskExecutionEnvironment`，注册搜索、scratchpad、报告写入、验证、子任务委派等工具，然后由 MainAgent 负责规划和调度。

## 2. MainAgent 的三阶段

MainAgent 当前按任务状态推进，核心阶段为：

1. `research`：研究阶段。MainAgent 将用户问题拆成多个可并行的研究任务，通常通过 `delegate_tasks` 并发启动多个子 Agent。
2. `synthesis`：综合阶段。只有研究类子任务全部达到完成状态后才进入。该阶段汇总 findings、scratchpad、trace_digest 等信息，生成草稿或最终报告内容。
3. `verification`：校验阶段。只有综合/写作类任务完成后才进入。该阶段验证报告是否覆盖原始问题、证据是否充分、输出文件是否存在，以及是否还有阻塞问题。

阶段推进采用严格门禁：同一阶段内只要存在 `running`、`partial`、`failed` 或未收集结果的任务，MainAgent 都应继续停留在当前阶段，通过等待、续跑或重新委派来补齐任务，而不是提前进入下一阶段。

## 3. MainAgent 可执行动作

MainAgent 的动作主要包括：

- `delegate_tasks`：一次性并发委派多个子任务。适合拆分数据库检索、论文抽取、研究流派和对抗复核等相互独立的工作。
- `delegate_task`：委派单个子任务。适合补充研究、单独写作、单独验证。
- `continue_task`：继续已有子任务会话。用于子任务因为步数耗尽、超时或部分完成而未达成目标时，沿用原来的 `session_id`、记忆和上下文继续执行。
- `wait_worker_sessions`：等待一个或多个正在运行的子任务完成，并收集它们的 finish_result、trace_digest、findings 等结果。
- `list_worker_sessions`：查看当前子任务会话状态。
- `inspect_worker_session`：查看某个子任务会话的详细信息。
- `close_worker_session`：关闭不再需要的子任务会话。
- `complete_task`：在研究、综合和校验都满足完成条件后，提交最终结果。

## 4. 子 Agent 会话与 continue_task

每个被委派的子任务都会创建一个独立 session。session 中保存任务指令、模型、工具范围、运行轮次、latest_finish_result、trace_digest、隔离 findings 路径等信息。

如果一轮子 Agent 执行结束但状态是 `partial`，例如达到最大步数但没有正常调用 `finish`，MainAgent 不应把它当作新任务重新开始。正确做法是使用 `continue_task` 指定原 `session_id`，让子 Agent 继承原会话上下文继续执行。这样可以避免重复搜索、重复写入和上下文断裂。

只有当原会话不可恢复、任务拆分本身有问题，或需要补充一个新的独立视角时，才应该重新 `delegate_task` 或 `delegate_tasks`。

## 5. 并发与等待策略

`max_parallel_subtasks` 控制研究阶段允许同时运行的子任务数量。当前逻辑在 MainAgent 调用 `delegate_task`、`delegate_tasks` 或 `continue_task` 后，会等待对应运行中的 worker 完成或达到配置的等待超时，再进入下一轮 MainAgent 决策。

这样设计的目标是：既保留子任务并发执行的效率，又避免 MainAgent 连续空转多轮，导致子任务还没完成时主流程已经耗尽轮数。

## 6.上下文摘要处理

子 Agent 的完整 trace 可能包含大量搜索结果、工具输出和中间响应，为每个子任务生成 `trace_digest`。
`trace_digest` 保留 MainAgent 做下一步判断所需的信息，例如：

- 子任务总步数与使用过的工具；
- 搜索查询、搜索后端、是否成功；
- 失败原因和阻塞点；
- finish 状态、message、completed、issues；
- 关键产出摘要。

MainAgent 根据这些摘要判断是否继续研究、进入综合、进入校验，或对失败/部分完成任务调用 `continue_task`。


## 7. Research Mode 执行逻辑

Research Mode 是固定研究流程，不再由 MainAgent 自主决定“下一步做什么”。其入口是 `research.runner.run_research()`，内部创建 `ResearchPipeline`，由 `ResearchPipeline` 串通完整 research 流程。

当前边界如下：

- `ResearchPipeline`：负责研究流程顺序、每步产物路径、质量门禁和最终结果聚合。
- MainAgent：只在需要并行/委派的研究步骤内作为执行协调器使用。
- SubAgent：执行被 MainAgent 委派的具体搜索、综合、写作、审稿等子任务。
- Skill Markdown：为每个研究步骤提供具体 prompt 语义，MainAgent/SubAgent 按当前步骤 skill 执行。

也就是说，Research Mode 的控制权在程序状态机，而不是 MainAgent（mainagent控制下一步会出现跳步、长程任务容易出现漂移）：

```text
/research
  -> run_research(request, config)
  -> ResearchPipeline.run()
  -> for step in RESEARCH_STEPS:
       load step.skill
       build step brief
       execute step by single-agent or multi-agent project
       run step gate
  -> derive artifacts
  -> export latex/html if requested
  -> final gate
  -> ResearchResult
```

### 7.1 固定步骤

Research Mode 当前定义 8 个步骤：

1. `decompose_topic`：研究问题拆解，加载 `decompose-topic` skill，输出 `研究问题拆解`。
2. `literature_search`：文献检索与证据表，加载 `literature-search` skill，输出 `文献检索与证据表`。
3. `knowledge_synthesis`：知识综合与研究空白，加载 `knowledge-synthesis` skill，输出 `知识综合与研究空白`。
4. `claim_generation`：研究空白、未来方向与可检验问题生成，加载 `claim-generation` skill，输出 `研究空白、未来方向与可检验问题`。
5. `claim_debate`：观点辩论与优先级评估，加载 `claim-debate` skill，输出 `观点辩论与优先级评估`。
6. `outline_build`：结构化大纲，加载 `outline-build` skill，输出 `结构化大纲`。
7. `section_draft`：研究报告正文，加载 `section-draft` skill，输出 `研究报告正文`。
8. `multi_agent_review`：多视角审稿，加载 `multi-agent-review` skill，输出 `多视角审稿意见`。

其中 `literature_search`、`knowledge_synthesis`、`claim_generation`、`claim_debate`、`multi_agent_review` 带有 `parallel_hint=True`，由 `ResearchPipeline` 调用 `build_agent_project()`，使用 MainAgent + 多 SubAgent 执行。其余步骤调用 `build_single_agent_project()`，直接用单个 SubAgent 执行。

### 7.2 MainAgent 在 Research Mode 中的角色

Research Mode 中的 MainAgent 不负责阶段推进。它只在单个 research step 内负责：

- 根据当前 step brief 和 skill 拆分可并行子任务；
- 使用 `delegate_task` 或 `delegate_tasks` 创建 SubAgent；
- 使用 `wait_worker_sessions`、`inspect_worker_session` 收集执行结果；
- 必要时用 `continue_task` 续跑未完成子任务；
- 将结果综合到当前 step 要求的产物中。

每个 step 的 brief 会由 `ResearchPipeline._build_step_brief()` 构造，包含：

- 当前步骤名称和 key；
- 研究主题、深度、输出格式、约束；
- 统一产物路径，如 `report_path`、`findings_path`、`scratchpad_path`、`papers_path`、`claims_path`、`debate_log_path`；
- 当前步骤对应的 skill Markdown；
- 硬性要求：只执行当前步骤、写入指定 markdown 章节、记录带来源的 findings、不要编造来源。

因此 MainAgent 的 prompt 仍复用通用 `GenericMainPromptBuilder`，但研究步骤语义来自 `src/research/skills/*.md`。

### 7.3 SubAgent 在 Research Mode 中的角色

SubAgent 仍复用通用 `GenericSubPromptBuilder`。由于 step brief 中显式包含 `任务类型: research`，SubAgent 会按 research 策略执行：

- 搜索或读取本地资料；
- 使用 `record_finding` 记录结构化发现；
- 使用 `write_scratchpad_note` 留下可复用中间结论；
- 按当前 skill 要求写入或协助写入报告章节；
- 最后通过 `finish` 返回状态、完成事项、剩余问题和结果摘要。

Research Mode 当前还没有单独的 `ResearchMainAgent` 或 `ResearchSubAgent` 类。它的第一版实现是：**固定流程在 `src/research`，执行能力复用现有 Agent Runtime**。

### 7.4 产物与门禁

每次 Research Mode 会创建独立运行目录：

```text
workspace/output/research_<timestamp>_<topic>/
```

主要产物包括：

- `research_report.md`：canonical markdown 工作稿；
- `findings.jsonl`：结构化发现；
- `papers.jsonl`：文献记录；
- `claims.jsonl`：研究空白、未来方向、可检验问题和综述观点；
- `debate_log.md`：辩论记录；
- `outline.md`：结构化大纲；
- `review_report.md`：多视角审稿结果；
- `paper.tex`：LaTeX 导出；
- `report.html`：HTML 导出；
- `manifest.json`：步骤结果和产物清单。

`ResearchGatekeeper` 会在每个 step 后检查当前章节、scratchpad 和 findings 数量；最终再检查必需章节、来源链接、findings 数量和请求的导出格式是否存在。只有最终门禁通过，`ResearchResult.status` 才会是 `done`；否则返回 `partial` 并在 `open_issues` 中列出缺口。
