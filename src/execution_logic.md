# AOrchestra-Agent 执行逻辑说明

本文档说明当前项目在通用 Agent 场景下的主流程、MainAgent 三阶段控制、子 Agent 会话复用、并发委派和日志约定。

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

- `delegate_tasks`：一次性并发委派多个子任务。适合研究阶段拆分城市、行业、政策、市场等独立维度。
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
