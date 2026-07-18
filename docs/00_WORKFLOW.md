# AI4MS 协作与提交规范

## 1. 分支职责

- `ai4s`：AI4MS 产品改造集成分支；
- `dev`：RiffBand 现有能力的对照基线；
- `feature/*`：独立功能开发；
- `fix/*`：缺陷修复；
- `docs/*`：文档和 Schema 整理；
- `experiment/*`：不保证进入产品的验证代码。

不要直接把未完成的大型重构长期堆在 `ai4s`。从 `ai4s` 创建短生命周期分支，通过小型 PR 回收。

## 2. 推荐 PR 顺序

改造按以下边界拆分，避免把基础设施、产品功能和前端同时揉进一个提交：

1. 测试、开发依赖、锁文件和 CI；
2. DomainProfile 与去领域硬编码；
3. ResearchProtocol 与 legacy adapter；
4. 多源检索并集、快照和 provenance；
5. PaperCard v2；
6. Artifact Manifest v2；
7. Gate Registry；
8. Topic Scout 结构对象；
9. Revision 与 Approval；
10. Stata Runner；
11. FastAPI、PostgreSQL 和 Web。

每个 PR 应对应验收矩阵中的一个或一组明确 ID。

## 3. 目录边界

目标结构遵守以下职责：

- `src/base`、`src/core`、`src/agents`：通用 Agent Runtime；
- `src/orchestration_tools`：委派、权限、任务和并发；
- `src/domains`：DomainProfile 与学科规则；
- `src/protocols`：ResearchProtocol 和 legacy adapter；
- `src/artifacts_v2`：manifest、hash 和 lineage；
- `src/research`：阶段流水线与兼容入口；
- `src/api`、`src/services`、`src/db`：平台服务层，建立后再启用；
- `docs/refer/AI4MS-DevPack_v0.3`：只作为调研和规格参考，不由运行时写入。

新增代码应先匹配现有目录边界。只有职责已经稳定时才创建新顶层包。

## 4. Commit

一个 commit 只完成一种可解释的变化。标题使用英文：

```text
type: short summary
```

常用类型：

- `feat`：新能力；
- `fix`：缺陷修复；
- `refactor`：不改变外部行为的结构调整；
- `docs`：文档或契约更新；
- `test`：测试与 fixture；
- `chore`：依赖、CI 和维护。

示例：

```text
refactor: add management science domain profile
feat: union literature results across providers
feat: add immutable research asset revisions
test: add cross-domain protocol fixtures
docs: establish AI4MS documentation baseline
```

## 5. PR 描述

PR 至少说明：

- 背景和目标；
- 修改的对象、接口和行为；
- 对旧 CLI/MCP 的兼容影响；
- 对 Gate、审批和数据治理的影响；
- 执行的测试与验收 ID；
- 已知限制和回滚方式。

Schema 变更必须同时列出迁移策略和旧数据读取方式。

## 6. Review 重点

- 是否把某个课题关键词重新写进通用层；
- LLM 是否被用于本应确定性执行的权限、hash、统计或状态判断；
- Agent 是否可能绕过人工审批或修改不可变产物；
- 上游 revision 变化是否正确影响下游 Gate；
- 检索结果是否保存来源、查询、日期、错误和快照；
- 摘要证据是否被错误提升为全文结论；
- HTML 报告是否与底层结构对象和证据一致；
- Licensed/Sensitive/Restricted 数据是否进入不允许的模型或日志；
- 新功能是否有失败、取消、重试和审计路径。

## 7. 仓库卫生

提交前检查：

```powershell
git status --short
git diff --check
pytest -q -p no:cacheprovider
```

禁止提交：

- `.env`、API key、许可证序列号和授权码；
- `workspace/`、运行日志、缓存和临时输出；
- 受限论文全文和无权再分发的数据；
- Stata 安装包、许可证和未经批准的第三方 ado；
- 从本机生成的绝对路径和用户标识。

## 8. 文档同步

以下变化不能只改代码：

- 产品范围变化：更新 `00_PRODUCT.md`；
- 阶段和排期变化：更新 `00_ROADMAP.md`；
- API/Schema/SQL 变化：同步 DevPack 契约或其正式迁移版本；
- 命令与配置变化：更新根 README 和 `00_GUIDELINE.md`；
- 新风险或许可边界：更新风险登记和治理文档。

仓库中只保留一套当前产品定位。历史方案通过 Git 追溯，不再以平行文档长期保留。
