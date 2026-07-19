# AI4MS 文档索引

本目录是 `ai4ms` 分支的产品与工程文档入口。当前唯一产品定位是：面向管理科学的垂直 AI 科研工作台，产品形态类似 MS 领域的轻量玻尔，并把介绍书的用户任务落到前端 S0-S9 十阶段中。

## 文档权威顺序

发生冲突时按以下顺序判断：

1. 当前代码与自动化测试决定“已经实现什么”；
2. `docs/00_*.md` 决定当前分支的产品定位、路线和协作规则；
3. `docs/refer/AI4MS-DevPack_v0.3/` 提供详细产品规格、调研语料、Schema、API 草案和开发参考；
4. 外部介绍材料只用于产品沟通，不能覆盖工程契约。

规划中的能力必须写为“目标、计划或待实现”，不能在 README 中描述成已上线功能。

## 核心文档

| 文档 | 用途 |
|---|---|
| [00_PRODUCT.md](00_PRODUCT.md) | AI4MS 产品定位、用户、核心对象与能力边界 |
| [00_ROADMAP.md](00_ROADMAP.md) | 7 月 26 日截止的双人六天 DDL、十阶段工作台架构、分工与验收 |
| [00_GUIDELINE.md](00_GUIDELINE.md) | 当前运行方式与 AI4MS 开发原则 |
| [00_WORKFLOW.md](00_WORKFLOW.md) | 分支、提交、评审和仓库卫生规则 |
| [DEPLOYMENT.md](DEPLOYMENT.md) | Docker GUI/API 部署契约、持久化、配置与验收 |
| [API_USAGE.md](API_USAGE.md) | 远程 API 调用流程和最小接口覆盖 |
| [ai4ms/BASELINE.md](ai4ms/BASELINE.md) | AI4MS 改造前工程基线 |

## AI4MS DevPack v0.3

[AI4MS-DevPack_v0.3](refer/AI4MS-DevPack_v0.3/README.md) 是本轮产品调研和开发设计的完整参考包，主要内容包括：

| 目录 | 内容 |
|---|---|
| `01_research_corpus` | 10 本期刊、100 篇平衡语料及研究范式分析 |
| `02_knowledge_bases` | 28 种方法、47 张公式卡、40 个数据源和 6 个 JSON Schema |
| `03_product` | PRD、Topic Scout、阶段智能体、审批、Stata、治理与技术架构 |
| `04_riffband_integration` | 当前仓库审计、迁移映射和目标目录 |
| `05_roadmap` | 24 周路线、三个 14 天 Sprint、验收矩阵和风险登记 |
| `06_developer_starter` | OpenAPI、PostgreSQL Schema、配置、示例和 Stata 契约 |
| `07_workbook` | 产品研究工作簿 |
| `08_nontechnical_intro` | 非技术产品介绍书 Markdown、DOCX 和 PDF |

## 当前版本口径

- 工程参考基线：AI4MS DevPack `v0.3`；
- 当前 Git 分支：`ai4ms`；
- 当前代码仍保留 RiffBand 兼容入口；
- 十阶段 Next.js/FastAPI/SQLite、不可变 revision、人工审批和 Docker 基础已经可运行；分阶段 Agent、Stata BYOL Runner、证据关联、导出和 Docker 单入口仍在六天冲刺中实现；
- 最终比赛交付为同时提供浏览器 GUI 和 `/api/v1` 的 Docker 镜像，部署与调用文档随实现补齐；
- HTML 可视化报告是保留并升级的现有能力，不属于待删除的旧产品资料。

## 维护规则

- 新的产品决策先更新 `00_PRODUCT.md`，再同步详细 PRD；
- 新的工程阶段先更新 `00_ROADMAP.md` 和验收编号；
- Schema、OpenAPI、SQL 和示例必须一起变更并通过校验；
- 语料、知识库和外部产品快照必须注明来源日期与证据等级；
- 不再新增与 AI4MS 定位平行、互相冲突的根级产品文档。
