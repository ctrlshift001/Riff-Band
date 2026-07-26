# AI4MS 文档

这里保存当前产品的正式文档。文档只描述现行产品、代码和交付方式；历史规划、临时审计、调研工作包和已被实现替代的 Starter 不再保留。

## 文档地图

| 文档 | 用途 |
|---|---|
| [PRODUCT.md](PRODUCT.md) | 产品定位、S0-S9 工作流、用户价值、可信边界和验收标准 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | 当前代码架构、状态模型、AOrchestra、数据流和 API 边界 |
| [DEVELOPMENT.md](DEVELOPMENT.md) | 本地开发、目录职责、测试、协作和仓库卫生 |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Docker GUI 构建、启动、配置、持久化和提交前检查 |
| [PROMPT_ENGINEERING.md](PROMPT_ENGINEERING.md) | S0-S9 提示词、结构化输出契约和修改规则 |
| [RUNNER.md](RUNNER.md) | `.dta` 资产、Stata Local Runner、后台任务和 Result Bundle |
| [competition/AI4MS_AGENT_APPLICATION_DESIGN.html](competition/AI4MS_AGENT_APPLICATION_DESIGN.html) | 面向比赛评委的智能体应用设计文档，可直接打印为 PDF |

## 信息优先级

出现冲突时按以下顺序判断：

1. 当前代码、Pydantic 契约和自动化测试；
2. 本目录中的正式工程文档；
3. 评委版设计文档中的产品级概括。

## 维护规则

- 产品范围或阶段语义变化：更新 `PRODUCT.md`。
- API、目录、状态机或数据流变化：更新 `ARCHITECTURE.md`。
- 命令、测试、分支和协作方式变化：更新 `DEVELOPMENT.md`。
- Docker、环境变量或持久化变化：更新 `DEPLOYMENT.md`。
- 提示词 ID、版本或输出契约变化：更新 `PROMPT_ENGINEERING.md`。
- Stata、Result Bundle 或后台任务变化：更新 `RUNNER.md`。
- 对外能力、架构、验证结论或比赛交付形态变化：同步更新评委版 HTML。
- 不为一次性排查、某日测试结果或短期 DDL 新建长期文档；这类信息进入 Issue、PR 或提交记录。
