# Workflow

## Goal

本仓库当前处在轻量级多 Agent 编排引擎产品化演进阶段，核心方向为 CLI 交互 + MCP 可插拔 + 科研模式。

因此，本 workflow 的目标不是增加复杂流程，而是确保下面三件事同时成立：

- 研究线、产品线和 demo 线边界清楚
- 日常提交可读、可 review、可回滚
- 尽量减少运行产物、缓存文件和误提交

## Branch Roles

当前仓库建议按以下分支职责协作：

- `dev`
  - 日常集成分支
  - 默认开发工作优先基于这条线展开
- `product`
  - 面向未来通用型 Agent 系统的主力产品线
  - 适合承接模式层、CLI、runtime、profile 化能力等持续演进工作
- `demo/exploration`
  - 演示与探索分支
  - 允许保留阶段性实验、验证和非最终方案
- `ref/upstream-main`
  - 原仓库参考线
  - 用于对照上游，不作为日常功能开发分支

## Branching

- 不要长期直接在共享分支上堆叠未完成改动。
- 每个相对独立的任务新开一个分支。
- 分支名使用英文短语，并带上类型前缀。

推荐格式：

```text
feature/<short-topic>
fix/<short-topic>
refactor/<short-topic>
docs/<short-topic>
test/<short-topic>
chore/<short-topic>
```

示例：

```text
feature/cli-mode-switching
refactor/benchmark-layout
docs/rewrite-readme
fix/terminalbench-path-resolution
```

## Scope Discipline

这个仓库当前最重要的规则之一，是不要把不同层次的改动混在一个提交里。

建议把改动按这几类分开：

- `aorchestra/`
  - 论文 / benchmark / 原始研究实现线（历史保留）
- `src/`
  - 新产品 / 核心引擎实现
- `docs/`
  - 定位、roadmap、设计与流程文档

如果一个任务同时涉及以上内容，尽量拆成多个 commit，而不是一次全部揉在一起。

## Commit

- 一个 commit 尽量只做一类事情。
- 提交前至少确认：
  - 代码没有明显语法错误
  - 关键入口没有被路径调整破坏
  - 没有把缓存、日志、运行产物和临时文件一起带进去

提交标题使用英文，简短明确。
如有必要，commit body 可以用中文补充说明。

推荐格式：

```text
type: short summary
```

常用 `type`：

- `feat`: 新功能
- `fix`: 缺陷修复
- `refactor`: 重构
- `docs`: 文档更新
- `test`: 测试调整
- `chore`: 杂项维护

示例：

```text
feat: add dynamic multi-agent industry workflow
refactor: move benchmark stack under aorchestra
docs: rewrite repository positioning
fix: resolve benchmark import paths
```

如果需要补充说明，建议在 body 中简单写清楚：

- 改了什么
- 为什么改
- 有没有已知限制

## Pull Request

- PR 标题与 commit 标题保持同样风格，使用英文。
- PR 描述建议用中文，写清楚背景和验证方式。
- 提交 PR 之前，至少自己过一遍 diff。

PR 描述建议包含：

- 背景：为什么要改
- 主要改动：改了哪些核心点
- 验证：跑了哪些命令、检查了哪些路径、做了哪些手动验证
- 风险：还有哪些未覆盖点

## Review Focus

Review 时优先看这些问题：

- 行为变化是否符合预期
- 路径重构后是否有导入或默认路径失效
- benchmark 线和产品线有没有被错误混合
- 运行产物、日志、缓存、临时文档是否误提交
- 文档是否和当前目录结构、命令入口一致

如果只是文案、注释、命名调整，可以简洁说明，不必过度展开。

## Merge

- 合并前确认目标分支是否正确。
- 如果分支已经明显落后，先同步再处理冲突。
- 不要把以下内容直接带着合并：
  - 已知报错
  - 调试代码
  - 路径迁移中断状态
  - 无关的 workspace / demo 产物

## Repo Hygiene

每次提交前都建议检查一遍仓库卫生。

重点关注：

- `workspace/`
- `demo/workspace/`
- 所有 `__pycache__/`
- `.env`
- 临时文档，例如草稿版 `00_*.md` 是否已经需要保留

原则：

- 运行产物不进版本库
- 密钥配置不进版本库
- 缓存文件不进版本库
- 临时草稿如果已经不再需要，应及时删除或改成正式命名

## Current Practical Rule

结合当前仓库阶段，最实用的一版规则如下：

1. 论文 / benchmark 相关改动优先收敛到 `aorchestra/`。
2. 新产品探索优先放在 `src/` 及相关入口，不要再往根目录散。
3. 每次目录重构后，至少检查 import、配置路径和 README 是否同步更新。
4. 不要提交 workspace、缓存、日志和无关 demo 产物。
5. 新任务开新分支，提交标题用英文，PR 描述用中文。

## Minimal Rule

如果只记最小版本，就记下面 5 条：

1. 新任务开新分支。
2. 一个 commit 只做一类事情。
3. `aorchestra/` 和 `src/` 的改动尽量不要混在同一个 commit。
4. 合并前先看 diff，确认没有缓存、日志、运行产物和临时文件。
5. PR 标题用英文，描述用中文写清背景、改动和验证。
