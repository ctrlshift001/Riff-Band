# 多 Agent Coordinator 与长生命周期 Worker 改造日志

## 1. 改造背景

项目原有执行链路是：

```text
run_agents.py
  -> build_project_by_mode(...)
    -> 根据 mode 选择 single / multi
      -> SingleAgentProject 或 AgentProject
```

在最初的多 Agent 实现中，`MainOrchestratorAgent` 通过 `delegate_task` 或 `delegate_tasks` 将任务分配给 `ResearchSubAgent`。子 Agent 每次都是临时创建、执行、返回结果，然后被丢弃。

这种方式适合一次性研究任务，但存在几个明显限制：

- 子 Agent 无法跨多轮保留自己的 memory。
- 后续任务只能依赖 trace summary 或 finish result，还原上下文成本较高。
- 主 Agent 无法查看、选择、关闭已创建的子 Agent。
- 并行任务只能共享最终产物，例如 `findings.jsonl`，不能共享长期 worker 状态。
- 项目启动前就要决定 single / multi，而 worker 是否必要，很多时候更适合由 coordinator 在运行时判断。

本次改造的方向是：保留现有 `mode=single`、`mode=multi`、`mode=auto` 的使用方式，但让 `multi` 内部逐步演进为类似 ClaudeCode 的 coordinator + worker 架构。

## 2. 三种 Mode 的定位

当前推荐只暴露三种用户可见模式：

```text
mode=single
mode=multi
mode=auto
```

三者含义如下：

```text
single = 强制单 Agent 执行
multi  = 强制多 Agent，即 MainOrchestratorAgent + worker
auto   = 自动根据任务内容选择 single 或 multi
```


mode=auto时由 `ModeRouter` 根据任务内容自动选择：

```text
简单任务 -> single
复杂任务 -> multi
```

当前 `build_project_by_mode()` 的语义可以概括为：

```text
mode=single:
  build_single_agent_project(...)

mode=multi:
  build_agent_project(...)

mode=auto:
  ModeRouter.decide(brief_text)
    -> selected_mode=single 或 multi
```

说明：旧的 `task` / `route` 隐式别名已移除。空字符串会被规范化为 `auto`，其他非法 mode 会直接报错。

## 4. 三种 Mode 的推荐使用方式

### 4.1 mode=single

适合简单、短链路、低成本任务，例如：

- 文本改写
- 简单摘要
- 格式转换
- 单文件读取和提取重点
- 明确的一步式问答
- 不需要证据链、报告、交叉验证的任务

特点：

- 延迟低。
- 成本低。
- 逻辑简单。
- 不使用 worker 池。

### 4.2 mode=multi

适合复杂、可拆解、需要协作的任务，例如：

- 行业研究报告
- 政策、公司、技术路线对比
- 多来源证据收集
- 需要 findings / scratchpad / report 的任务
- 需要研究、写作、验证三阶段推进
- 需要并行探索多个方向
- 需要长生命周期 worker 连续推进某个子任务

特点：

- 启动 `MainOrchestratorAgent`。
- 主 Agent 作为 coordinator 拆解任务。
- 可创建、继续、查看、关闭 worker。
- 支持 parallel research、scratchpad、artifact verification。

### 4.3 mode=auto

适合默认 CLI 或普通用户入口。

用户不需要提前判断任务该走单 Agent 还是多 Agent，只需要提交任务。系统通过 `ModeRouter` 自动判断：

```text
短任务、单步任务、无证据链 -> single
长任务、多步骤、研究/报告/验证 -> multi
```

推荐默认配置：

```yaml
mode: auto
```

调试或强需求时再显式覆盖：

```yaml
mode: single
```

或：

```yaml
mode: multi
```

## 5. mode=auto 的核心挑战

保留 `mode=auto` 的前提是：路由能力要足够可靠。

如果路由过度倾向 `single`，复杂任务会缺少 worker 拆解、证据收集和验证。

如果路由过度倾向 `multi`，简单任务会产生不必要的延迟和成本。

因此 `ModeRouter` 应该清晰区分：

```text
执行形态:
  single
  multi

选择策略:
  auto
```

`ModeRouter` 的输出不应该是 `auto`，而应该是最终执行模式：

```text
single 或 multi
```

## 6. 借鉴 ClaudeCode 的 Mode 思路

参考仓库：

- `https://github.com/kdxsydq/ClaudeCode`
- `src/coordinator/coordinatorMode.ts`

ClaudeCode 的 coordinator 机制不是简单做一个 `single/multi` 二分类 UI，而是通过功能开关和环境变量进入 coordinator 模式。

关键点包括：

- 通过 `COORDINATOR_MODE` feature gate 和 `CLAUDE_CODE_COORDINATOR_MODE` 环境变量判断是否进入 coordinator 模式。
- 进入 coordinator 模式后，主 Claude 被定位为 coordinator。
- coordinator 有明确工具：创建 worker、继续 worker、停止 worker。
- worker 适合执行 research、implementation、verification。
- coordinator 仍然被要求：能直接回答的简单问题就直接回答，不要把简单工作委派给 worker。
- coordinator 会把任务拆成 Research、Synthesis、Implementation、Verification 等阶段。
- 独立任务尽量并行启动 worker。
- 同一个 worker 已经有上下文时，优先继续该 worker，而不是重新开一个。
- scratchpad 用于跨 worker 的持久知识共享。

这对本项目的启发是：

`auto` 不应该被理解成“永远先启动复杂多 Agent 系统”。更合适的设计是：

```text
auto:
  先判断任务是否简单
  简单任务直接 single
  复杂任务进入 multi
```

进入 `multi` 后，也不意味着每一步都要创建 worker。`MainOrchestratorAgent` 仍应遵守：

```text
能直接判断的事情，自己判断。
需要研究、写作、验证、并行探索、长期上下文的事情，再交给 worker。
```

这样既借鉴了 ClaudeCode 的 coordinator 思想，又保留了本项目 `single / multi / auto` 的清晰配置模型。

## 7. 建议的 auto 路由规则

建议清理 `ModeRouter`，围绕稳定、可解释的规则判断。

### 7.1 倾向 single 的信号

任务满足以下特征时，优先走 `single`：

- 文本较短。
- 没有多步骤要求。
- 没有显式 research / analyze / compare / report / verify 等信号。
- 不要求来源、证据、引用、findings。
- 不需要生成完整报告。
- 不需要并行探索。
- 不需要跨文件或跨资料整合。
- 用户要求 quick / brief / one step。

示例：

```text
把这段话改成正式语气。
总结下面这段文字。
读取这个文件并列出三个重点。
```

### 7.2 倾向 multi 的信号

任务满足以下特征时，优先走 `multi`：

- 任务较长。
- 包含多个子问题。
- 明确要求 research / analyze / compare / evaluate。
- 明确要求 report / recommendations / findings。
- 明确要求 evidence / sources / citations。
- 明确要求 verify / validation / cross-check。
- 明确要求 parallel / multi-agent / 多 Agent。
- 需要读取多个资料、多个文件、多个主题。
- 需要先研究、再写作、再验证。
- 需要长期 worker 连续推进同一任务线。

示例：

```text
调研某行业政策、公司格局和投资风险，并输出带证据的报告。
比较三个技术方案，给出适用场景和风险。
阅读这些资料，提取 findings，写成结构化分析报告。
```

### 7.3 auto 判断流程

建议 `ModeRouter` 采用规则优先、LLM 辅助的方式：

```text
1. 先做硬规则判断
   - 明确要求多 Agent / 并行 / 报告 / 证据 / 验证 -> multi
   - 极短且无复杂信号 -> single

2. 再做软规则评分
   - 多步骤数量
   - 任务长度
   - research / analyze / compare / report 等关键词
   - findings / evidence / sources 等交付要求

3. 对边界任务再调用 LLM 辅助判断
   - 输出只能是 single 或 multi
   - 不输出 auto
```

这样可以控制成本，同时提高 `auto` 的准确性。

## 8. 已完成的 Worker 改造

本项目已经加入了长生命周期 worker 基础能力。

### 8.1 可继续 Worker Session

`delegate_task` 创建任务后会返回 `session_id`。

`continue_task` 可以继续同一个 session，并复用该 worker 的上下文。

session 中记录：

- `session_id`
- worker 状态
- 原始任务描述
- 模型
- 工具集
- result schema
- retained `ResearchSubAgent`
- retained environment
- round history
- latest finish result

### 8.2 Worker Memory 保留

`ResearchSubAgent` 新增：

```python
preserve_memory_on_reset: bool
```

继续同一 worker 时，该值为 `True`，runner 调用 `reset()` 也不会清空 memory。

这让 `continue_task` 从“摘要续跑”升级为真正的长生命周期 worker 续跑。

### 8.3 Worker 管理工具

新增工具：

```text
list_worker_sessions
inspect_worker_session
close_worker_session
```

作用：

- `list_worker_sessions`: 查看当前 worker 池。
- `inspect_worker_session`: 查看某个 worker 的 memory 和历史轮次。
- `close_worker_session`: 关闭不再需要的 worker，并释放保留的 Agent 对象。

### 8.4 共享 session_store

所有 worker 管理工具必须共享同一个 `session_store`。

由于 Pydantic 可能复制构造函数传入的 mutable dict，`build_project.py` 中采用实例化后显式赋值的方式，确保以下工具共享同一个 worker 池：

- `DelegateTaskTool`
- `DelegateTasksTool`
- `ContinueTaskTool`
- `ListWorkerSessionsTool`
- `InspectWorkerSessionTool`
- `CloseWorkerSessionTool`

## 9. 三阶段 Coordinator 协议

`multi` 模式下，`MainOrchestratorAgent` 按照三阶段协议工作：

```text
Research -> Synthesis -> Verification
```

阶段含义：

- `Research`: 收集证据、记录 findings、写 scratchpad。
- `Synthesis`: 整合 findings 和 scratchpad，生成报告 section。
- `Verification`: 检查 report、findings、scratchpad，修复缺口后再 complete。

这个协议借鉴了 ClaudeCode 中 coordinator 负责综合、worker 负责研究/执行/验证的思想。

## 10. Scratchpad 与 Verification

新增 scratchpad 工具：

```text
write_scratchpad_note
read_scratchpad
```

默认路径：

```text
workspace/output/scratchpad/shared.md
```

用途：

- 保存 worker 中间结论。
- 保存 handoff 信息。
- 保存 open questions。
- 在研究和写作之间共享上下文。

新增 verification 工具：

```text
verify_artifacts
```

检查内容：

- report 是否存在且非空。
- required sections 是否齐全。
- findings 数量是否满足 `min_findings`。
- findings 是否包含 evidence / source_url。
- report 是否包含显式来源链接。
- scratchpad 是否存在且非空。

## 11. 当前项目最终执行模型

当前保留三种 mode：

```text
single
multi
auto
```

最终执行链路：

```text
mode=single
  -> SingleAgentProject

mode=multi
  -> AgentProject
  -> MainOrchestratorAgent
  -> delegate / continue / inspect / close workers

mode=auto
  -> ModeRouter.decide(...)
    -> single 或 multi
``` 


`auto` 路由能力采用三层策略：

```text
1. hard rule
   明确并行、多 Agent、报告+证据、验证+证据、三步以上任务，直接 multi。
   短文本、单步、无证据/报告/验证/拆解信号，直接 single。

2. soft score
   根据任务长度、关键词、步骤数、问题数、证据要求、报告要求等计算 multi_score 和 single_score。

3. LLM assist
   只对边界任务调用 LLM 辅助判断。
   LLM 只能返回 single 或 multi，不能返回 auto。
```

这样可以避免 `auto` 完全依赖 LLM，也避免简单任务误走多 Agent。

## 12. 通用 Agent 工具路由改造

为将项目从研究报告型 Agent 进一步改造成通用 Agent，本轮将工具路由从“任务 profile 固定工具包”转向更接近 ClaudeCode 的方式。

改造前：

```text
task_instruction
  -> _infer_profile(...)
    -> subtask_toolkits[profile]
      -> allowed_tools
```

这种方式适合固定研究/报告任务，但不适合通用 Agent。通用任务可能同时需要读取、搜索、记录、写作、验证等多种能力，过早按 profile 限制工具会降低 worker 自主性。

改造后：

```text
worker 默认获得 default_worker_tools
coordinator 负责写清楚任务目标、上下文、产出格式和完成标准
worker 在标准工具集内自主选择工具
runtime policy 负责安全限制
```

新增运行时策略：

```text
default_worker_tools:
  通用 worker 默认工具全集

parallel_forbidden_tools:
  并行模式下禁止的工具，例如 write_report_section
```

现在 `_apply_delegate_defaults()` 的职责从“profile -> toolkit”变为：

```text
1. 如果 MainAgent 没有显式传 tools，则使用 default_worker_tools。
2. 如果是并行任务，则移除 parallel_forbidden_tools。
3. 根据 profile 继续选择默认模型。
4. 保留 worker_profile 作为历史记录和阶段判断信息。
```

`Subtask toolkit hints` 仍保留在 profile / meta 中作为兼容数据，但已从 MainAgent prompt 中移除，避免继续暗示 profile 固定工具包。

MainAgent prompt 也做了调整：

- 不再要求每个 delegate_task 手工列 tools。
- 默认省略 tools，让 runtime 提供标准 worker 工具集。
- 只有需要限制或覆盖 worker 权限时才显式传 tools。
- MainAgent 更关注 worker prompt 质量：目标、上下文、artifact path、输出格式和 done criteria。

这更接近 ClaudeCode 的职责分离：

```text
Coordinator:
  负责任务拆解、spawn/continue/close worker、综合和验收。

Worker:
  拥有标准工具集，自主选择工具执行任务。

Runtime:
  负责安全边界和并发写入限制。
```

当前仍保留 `ScopedEnvironment`，用于在需要限制工具时做运行时强约束。也就是说，本项目并不是完全放开所有工具，而是采用：

```text
ClaudeCode 式 worker 自主工具选择
+ 项目级安全策略限制
```

## 13. SubAgent 命名约定

为避免直接照搬 ClaudeCode 的 `worker` 说法，本项目在 prompt 和文档层统一采用：

```text
sub-agent
sub-agent session
sub-agent capabilities
```

推荐概念分层：

```text
MainOrchestratorAgent:
  主协调器，负责拆解、调度、综合和验收。

Execution SubAgent:
  执行型子 Agent，负责具体任务执行和工具调用。

SubAgent Session:
  可继续的子 Agent 会话，保存 memory、历史轮次和状态。
```

当前代码层仍保留部分历史工具名，例如：

```text
list_worker_sessions
inspect_worker_session
close_worker_session
```

这些名称暂时作为兼容接口保留，后续可以再逐步增加 `list_subagent_sessions` 等别名。

同时，MainAgent prompt 不再列出完整工具 schema，而是改为简短的 `Sub-agent capabilities` 摘要。完整工具 schema 仍由 SubAgent 的 action space 提供给真正执行工具调用的子 Agent。
