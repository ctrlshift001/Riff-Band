# ignis 参考笔记

仓库地址：<https://github.com/igniscloud/ignis>

## 1. 项目介绍

Ignis / IgnisCloud 不是一个单纯“让 agent 更会聊天”的工具，而是一套更偏工程系统的 agent-native 应用底座。

从公开资料和源码结构来看，它的核心思路是：

- agent 不应该只是对话层能力
- agent 应该被放回服务系统里
- 服务有边界，任务有状态，输出有 schema，依赖有图，运行时有隔离，平台有部署链路

它大致分成两部分：

- `ignis`
  - 偏开发者侧与框架侧
  - 负责 project / service 开发、manifest、SDK、运行时、TaskPlan 等能力
- `IgnisCloud`
  - 偏平台侧与托管侧
  - 负责发布、部署、节点激活、内部服务发现、agent 容器、对象存储、job/schedule、计费等能力

一句话理解：

> Ignis 不是只给 agent 写 prompt 的工具，而是一套把 agent 当成服务系统一等公民来设计的工程底座。

## 2. 为什么值得我们参考（简析）

它和我们项目最相关的地方，不是具体技术栈，而是“怎么看待 agent 系统”。

我们现在也在从论文 / benchmark 体系向更通用的 Agent 系统推进，而 Ignis 很明确地回答了一个关键问题：

> agent 系统不应该只是一个聊天界面，而应该是一个可以组合、调度、部署和恢复的工程系统。

这和我们当前的方向有明显交集，尤其体现在：

- 单 Agent 与多 Agent 如何共存
- 多 Agent 协作如何变得可管理
- 任务计划如何摆脱纯自然语言
- agent 如何和 service、job、数据库、前端放在同一工程体系中

所以它对我们的价值主要在于：

- 提供了一套更工程化的 agent 系统视角
- 给了我们多 Agent 协作从“prompt 逻辑”走向“系统设计”的参考

## 3. 可以参考的点

### 3.1 把 agent 当成服务，而不是当成一段对话

Ignis 最大的启发之一是：

- agent 应该有边界
- agent 应该有输入输出
- agent 应该有能力描述
- agent 应该能被发现、调用和替换

这对我们后续做“通用型 Agent 系统”很重要。

我们现在也在强调：

- 单 Agent 常规模式
- 动态多 Agent 模式
- profile 化能力

后续完全可以继续往“agent/service 统一建模”的方向走，而不是把所有能力都继续塞进单个大对话上下文。

### 3.2 TaskPlan 这种“计划即数据”的思路

这是 Ignis 最值得借鉴的一块。

它没有把协作停留在一句“帮我规划一下”的 prompt 上，而是把计划变成了结构化数据：

- TaskPlan
- TaskSpec
- TaskDependency
- OutputBinding
- TaskState

这对我们非常关键，因为我们现在已经在讨论：

- 动态多 Agent
- 并行子任务
- 后续升级到 DAG 调度

如果继续往前做，我们也需要把“任务拆解”从自然语言上升到结构化计划。

这类设计的价值在于：

- 任务依赖是显式的
- 状态是可存储、可恢复的
- 输出可以校验
- 上下游数据绑定可以脱离 prompt 记忆

简单说：

> 我们最值得借的，不是 Ignis 的平台，而是它把多 Agent 协作从 prompt 提升为数据模型的做法。

### 3.3 coordinator 和 executor 分离

Ignis 里一个很重要的工程化思想是：

- coordinator 负责判断和表达计划
- executor 负责真正调度、记录状态、推进依赖、恢复任务

这和“让 agent 自己记住全部上下文、全部计划、全部状态”是两种路线。

对我们来说，这个分离很有意义，因为它可以帮助我们：

- 降低上下文污染
- 减少 agent 对历史状态的依赖
- 让失败恢复、重试和审计更容易实现

这对动态多 Agent 模式尤其重要。

### 3.4 service discovery / metadata 的思路

Ignis 里服务不是随便互相找，而是有明确的 service identity、metadata 和内部调用方式。

我们不一定要照搬它的 `.svc` 模型，但很值得参考这种思路：

- 每个 agent service 都应该有描述
- coordinator 应该能拿到可用 agent 列表
- 子 agent 的分配应该尽量基于能力描述，而不是写死在 prompt 里

这和我们现在想做的“动态多 Agent + profile 化路由”其实是同方向的。

### 3.5 project manifest 的工程视角

Ignis 用 `ignis.hcl` 把 project、service、jobs、schedules 放在一个中心 manifest 里。

这给我们的启发是：

- 一个 agent 系统最后一定需要“项目级配置中心”
- 不能只靠散落的 Python 脚本和 yaml 路径维持复杂系统

我们后续不一定用 HCL，但很可能也需要自己的项目 manifest，用来描述：

- 模式
- services
- profiles
- jobs
- runtime 配置
- 输出和存储策略

## 4. 结论

Ignis 很值得参考，但参考方式应该克制。

它对我们的主要帮助，不在于 Wasm、云平台或部署链路，而在于它提供了一套更成熟的工程抽象：

- agent 是服务，不只是对话
- 计划要结构化，不只存在上下文里
- 多 Agent 协作要有状态、依赖和输出校验
- coordinator 和 executor 最好分离
- 一个 agent-native application 需要 project 级组织方式

因此，对我们最有价值的借鉴方向是：

- 借它的抽象和边界
- 借它的 TaskPlan 思路
- 借它的 service / manifest 视角

而不必急着借它的平台、Wasm 技术栈或完整云侧实现。
