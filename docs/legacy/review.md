# 代码审查：`9b0efc6` — single&multi agent

> 审查日期：2026-04-30
> 作者：Limlj-lillian
> 范围：34 个文件，+3730 / −378 行

---

## 概述

本次提交引入了四项重大架构变更：

1. **模式路由器** (`src/modes/router.py`) — 基于规则 + LLM 辅助的 single/multi 模式路由
2. **多进程子 Agent** (`src/workers/subagent_worker.py` + `src/orchestration_tools/worker_process.py`) — 通过 `SubAgentProcessManager` 实现进程隔离
3. **任务计划系统** (`src/orchestration_tools/taskplan.py`) — 基于 DAG 的任务规划，含状态机和 schema 校验
4. **长生命周期 Worker 会话** — 会话存储，支持 spawn / wait / inspect / continue / close 生命周期

整体方向正确。以下问题分为 **Bug**（行为错误，必须修复）和**不完善**（设计问题，建议修复）。

---

## Bug（必须修复）

### 1. 最终决策轮未拦截所有非 complete 操作

**文件：** `src/agents/main_agent.py` 第 257–273 行

```python
if forced_final_decision and action_name in {"delegate_task", "delegate_tasks", "continue_task"}:
    action_name = "complete_task"
```

只拦截了三种操作。LLM 仍可返回 `wait_worker_sessions`、`list_worker_sessions`、`inspect_worker_session` 或 `close_worker_session`。这些操作正常执行后循环结束，**没有 `final_result`** — `AgentProject.run()` 返回 `{"final_result": None}`。

**修复：** 将条件改为 `action_name != "complete_task"`，或在 `forced_final_decision` 为 true 时无条件覆盖整个决策。

---

### 2. `DelegateTasksTool` 并发限制未生效

**文件：** `src/orchestration_tools/delegate.py` 第 973–1004 行

```python
semaphore = asyncio.Semaphore(limit)

async def _run_with_session(idx, task):
    async with semaphore:
        result = await self._spawn_single(...)   # spawn 立即返回！
```

`_spawn_single` 启动后台进程后立即返回 `"running"`。信号量因此只限制了*启动速率*，而非实际的子 Agent 并发。无论 `max_concurrency` 设为多少，所有子进程都会并行执行。

此外 `asyncio.gather` 返回的所有结果中 `worker_state` 均为 `"running"`，因此 summary 中的 `done_count`、`partial_count`、`blocked_count` 始终为 0。

**修复：** (a) 在 `SubAgentProcessManager` 内部控制并发，或 (b) 保留信号量包装但改用 `_run_single`（调用 `asyncio.to_thread(process_manager.run_task, ...)`）阻塞等待每个子 Agent 完成。

---

### 3. 跨模块引用私有函数

**文件：** `src/workers/subagent_worker.py` 第 10 行

```python
from project.build_project import _build_runtime_components, _resolve_profile
```

`_build_runtime_components` 和 `_resolve_profile` 是 `build_project.py` 中以 `_` 前缀标记的模块私有函数。从外部模块导入会破坏封装 — `build_project.py` 的任何内部重构都可能静默破坏 worker。

**修复：** 去掉下划线前缀使其成为公开接口，或提取到共享模块（如 `src/project/runtime.py`）。

---

## 不完善（建议修复）

### 4. `_spawn_single` 声明为 `async` 但内部无 `await`

**文件：** `src/orchestration_tools/delegate.py` 第 558 行

`process_manager.spawn_task()` 是同步方法——它只创建了一个 `asyncio.Task`。该方法声明为 `async def` 会误导阅读。改为同步方法或添加说明注释。

### 5. `_tool_params` 过滤掉了 `_apply_delegate_defaults` 注入的字段

**文件：** `src/agents/main_agent.py` 第 202–215 行

`_apply_delegate_defaults` 向 params 中添加了 `worker_profile`，但 `_tool_params` 随后将其过滤掉（只保留 `task_instruction`、`context`、`model`、`tools`、`result_schema`）。虽然工具 schema 目前会拒绝未知字段所以不会报错，但如果未来工具层需要使用 `worker_profile`，将静默失败。

### 6. `self.attempt` 双重管理

**文件：** `src/agents/main_agent.py`

`AgentProject.run()` 设置 `self.main_agent.attempt = i`，然后 `main_agent.step()` 内部执行 `self.attempt += 1`，导致 attempt 计数器存在两个真相来源。在重构时容易出错。

### 7. `CompleteTaskTool` 不再要求 `report_path`

**文件：** `src/orchestration_tools/complete_task.py` 第 76 行

`report_path` 从 required 改为 optional。传空字符串时，所有报告文件检查（存在性、章节、来源链接）都会被跳过，`quality_gate_passed` 可能错误地返回 true。建议保持 `report_path` 为 required，或要求 `artifacts` 列表中至少包含一个类型为 `"report"` 的产物。

### 8. 关键路径缺少测试覆盖

- `SubAgentProcessManager` — spawn / timeout / collect 生命周期
- Worker 会话生命周期 — spawn → wait → inspect → continue → close
- `forced_final_decision` 对每种可能操作的行为

### 9. `WEB_SEARCH_HTTP_PROXY` 和 `WEB_SEARCH_HTTPS_PROXY` 未记录在文档中

`src/project/tools/web_search_tool.py` 现在会读取这两个环境变量，但 `.env.example` 中没有体现。

### 10. `src/update.md` 不应包含在此提交中

538 行 changelog / 开发笔记与代码改动混在一起。建议移入单独的文档提交或移到 `docs/` 目录。

---

## 做得好的地方

- 移除了硬编码代理 `os.environ["HTTP_PROXY"] = "代理端口"` — 改为使用环境变量
- 类名从 `GBAAnalysis*` 泛化为 `TaskExecution*` / `Agent*`，并保留了向后兼容别名
- `ModeRouter` 三层决策：硬规则 → LLM 辅助 → 软规则
- 任务计划 DAG 校验（环检测 + 拓扑排序）实现正确
- `RuntimeProfile` dataclass 替代了散落的 dict 配置
- Scratchpad 机制用于 Agent 间通信
- `VerifyArtifactsTool` 实现了进程内质量自查
- 新增了 `ModeRouter` 和 `TaskPlan` 的测试，是扎实的补充
