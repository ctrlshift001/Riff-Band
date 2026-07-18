# AI4MS ROADMAP

## 总体目标

在 `ai4s` 分支上把 RiffBand 改造为可供真实管理科学课题试用的小型产品。目标不是一次完成大平台，而是依次证明三件事：

1. 现有研究内核可以跨课题、跨方法工作，不再出现领域硬编码；
2. 一句研究想法可以生成真实来源、可追溯、明确限制的已有研究报告；
3. 已批准选题可以进入 Research Protocol、受控分析、证据审查和可复现交付。

详细任务和指标见：

- [24 周 Roadmap](refer/AI4MS-DevPack_v0.3/05_roadmap/ROADMAP_24_WEEKS.md)
- [Sprint 0](refer/AI4MS-DevPack_v0.3/05_roadmap/SPRINT_0_14_DAYS.md)
- [Sprint 1 Topic Scout](refer/AI4MS-DevPack_v0.3/05_roadmap/SPRINT_1_TOPIC_SCOUT_14_DAYS.md)
- [Sprint 2 Stata 与 HITL](refer/AI4MS-DevPack_v0.3/05_roadmap/SPRINT_2_STATA_HITL_14_DAYS.md)
- [验收矩阵](refer/AI4MS-DevPack_v0.3/05_roadmap/ACCEPTANCE_TESTS.md)

## 当前冲刺：14 天比赛型 MVP

时间：2026-07-18 至 2026-07-31，共 14 个自然日。

团队只有两名开发者，DevPack 的 80 项 Backlog 中仅 P0 就有 64 项、估算约 230 人日，因此本轮不尝试完成完整平台。当前唯一目标是跑通以下比赛型竖切：

```text
一句研究想法
  -> 查询规划
  -> 多源文献检索
  -> 去重与 PaperCard
  -> 可追溯智能综述
  -> 候选研究空白与科研建议
  -> HTML 可视化报告
```

本轮必须保留真实来源、检索快照、证据关联、失败原因和 `partial` 状态，不以静态样例或无来源长文本代替真实执行。

### 双人分工

| 角色 | 负责人 | 主责 | 代码边界 |
|---|---|---|---|
| 技术负责人 | 项目工程负责人 | 架构、核心流水线、检索后端、数据模型、测试、CI、集成与发布 | `src/research/`、`src/project/tools/`、公共 Schema、核心测试和工程配置 |
| 产品与科研负责人 | 项目设计负责人 | 产品规则、领域 Profile、提示词、基准题、报告结构、视觉体验与演示叙事 | Skills/Prompt、Profile 配置、fixtures、HTML/CSS/JS、示例和产品文档 |
| 联合验收 | 两人 | 错误文献复核、每日端到端验收、比赛材料与最终演示 | 通过 PR 合流，不直接并行修改同一核心文件 |

产品与科研负责人可以使用 Vibecoding 完成低耦合、高可见模块，但生成代码合并前必须人工通读，并至少附带一个测试或固定样例。并发、持久化、错误恢复、公共协议和安全边界由技术负责人最终审核。

### 每日 DDL

| 日期 | 当日目标 | 技术负责人 | 产品与科研负责人 | 完成标准 |
|---|---|---|---|---|
| 7 月 18 日 D1 | 冻结范围 | 整理并提交当前 AI4MS 文档；建立 Issue 和开发分支 | 确定三个演示课题、目标用户流程和演示脚本 | MVP、禁止项、负责人和验收口径确定 |
| 7 月 19 日 D2 | 工程基线 | 修复两项 MCP 基线测试；配置 CI 和最小 smoke test | 编写基准题、种子论文、相邻术语和伪空白 | 测试转绿，benchmark fixture v1 可离线运行 |
| 7 月 20 日 D3 | 领域解耦 | 实现 `DomainProfile`，移除通信课题硬编码 | 编写管理科学 Profile、taxonomy 和筛选规则 | 三个课题无 RIS/ISAC/beamforming 串扰 |
| 7 月 21 日 D4 | 输入与查询 | 实现精简 `TopicBrief` 和 Query Planner 接口 | 设计中英文概念块、同义词、排除词和澄清问题 | 查询计划可查看、修改、保存和重放 |
| 7 月 22 日 D5 | 多源检索 | 并发接入 OpenAlex、Crossref、Semantic Scholar | 核查相关性、来源信息和错误提示 | 任一后端失败时其他后端仍产出并记录 provenance |
| 7 月 23 日 D6 | 快照与去重 | 实现 DOI、题名、作者、年份去重及版本关系 | 制作重复论文、预印本/终版和错误标识样本 | fixture 去重准确率不低于 98% |
| 7 月 24 日 D7 | PaperCard v2 | 实现结构化字段、证据等级、locator 和置信度 | 调整抽取 Prompt，人工核查至少 15 篇 | 摘要信息不标为全文证据，缺失字段保持 unknown |
| 7 月 25 日 D8 | 智能综述 | 实现流派、共识、争议和未知的数据对象 | 设计综合规则、代表论文和可读表述 | 核心陈述全部绑定 evidence ID |
| 7 月 26 日 D9 | 科研建议 | 实现六类 Gap、反向查询和候选课题卡 | 评估新颖性、可行性、可证伪性和伪空白 | 输出 2-3 个有依据且有限制说明的候选课题 |
| 7 月 27 日 D10 | HTML 报告 | 打通结构化对象到报告的数据接口 | 完成响应式 HTML、表格、ECharts 和来源交互 | 报告包含真实链接、图表和检索附录，无占位内容 |
| 7 月 28 日 D11 | 审计与闭环 | 实现 Artifact Manifest、引用审计和 `partial` 状态 | 完成精简 G0 确认和 Protocol 草案展示 | 选中候选课题后可生成不虚构缺失字段的 Protocol |
| 7 月 29 日 D12 | 集成验收 | 运行三个完整课题、故障注入和性能修复 | 完成人工质量评测和一个跨领域 smoke test | 三个主课题连续端到端成功，错误均可解释 |
| 7 月 30 日 D13 | 功能冻结 | 只修 P0/P1 缺陷，生成候选版本 | 完成讲解稿、录屏流程、截图和备用报告 | 完整演示至少连续通过两次，无人工救场 |
| 7 月 31 日 D14 | 发布提交 | 打版本 tag，备份配置、产物和静态报告 | 完成参赛简介、演示材料和答辩内容 | 源码、演示包和 HTML 报告均可独立检查 |

### 里程碑

| 里程碑 | DDL | 验收结果 |
|---|---|---|
| M0 基线冻结 | 7 月 19 日 | 测试转绿、范围和 benchmark 冻结 |
| M1 检索竖切 | 7 月 24 日 | 真实多源检索稳定产出可追溯 PaperCard |
| M2 产品竖切 | 7 月 27 日 | 综述、科研建议和 HTML 报告完整可见 |
| M3 发布候选 | 7 月 29 日 | 三个课题稳定运行并通过故障测试 |
| M4 比赛版本 | 7 月 31 日 | 演示、源码、报告和答辩材料完成 |

### 当前范围冻结

两周内不开发 Stata Runner、完整 S0-S9、复杂 Web 平台、PostgreSQL 全量迁移、OIDC/RBAC、知识图谱动画、付费全文抓取、复杂向量数据库或自动论文写作。用户界面只保证可用的演示入口和高质量 HTML 可视化报告。

### 协作与合并规则

- `ai4s` 只作为集成分支，个人工作使用 `feat/core-*` 和 `feat/product-*`；
- 先冻结 Schema 和示例，再并行开发实现；
- 每个 PR 聚焦一个可验收模块，禁止把重构、功能和文档混为一个大提交；
- 每天至少合并并运行一次端到端流程，不把集成推迟到最后三天；
- 引用虚构、核心结论无证据、报告空白、失败被误报为成功均为发布阻塞问题；
- D13 后停止增加功能，只处理影响演示和结论可信度的缺陷。

## 长期产品路线

## Phase 0：内核清理与基线

时间：W1-W2。

交付：

- 记录基线 commit、环境、测试和示例运行；
- 增加 dev 依赖、锁文件和 CI；
- 建立三个跨题型 benchmark fixtures；
- 实现 DomainProfile 与 Management Science Profile；
- 清除 RIS、ISAC、beamforming 等领域硬编码；
- 实现 ResearchProtocol v0.1 和 legacy adapter；
- 引入 Artifact Manifest v2 与 Gate Registry 基础。

退出条件：旧 CLI/MCP 兼容；三个 fixture 无领域串扰；现有测试基线可解释并逐步转绿。

## Phase 1：Topic Scout 竖切

时间：W3-W6。

交付：

- TopicBrief、SearchProtocol、TopicScoutRun 和 RelatedResearchReport；
- OpenAlex、Crossref、Semantic Scholar、arXiv 多源并集；
- DOI/题名/作者/年份去重与预印本关系；
- PaperCard v2、字段证据等级、locator 和人工队列；
- 三层检索、研究流派、共识/争议/未知和六类 Gap；
- 2-3 个候选课题及数据方法可行性；
- G0 人工审批并转为 Research Protocol 草案；
- Markdown、JSON 和 HTML 可视化报告。

核心指标：

- 专家种子论文 Recall@50 >= 0.90；
- 去重准确率 >= 98%；
- DOI/外部标识准确率 >= 99%；
- 虚构文献为 0；
- 核心结论 100% 可追溯；
- 绝对原创表述为 0。

## Phase 2：方法、证据与审批

时间：W7-W10。

交付：

- 导入 28 种方法、47 张公式卡和 40 个数据源；
- Design Advisor、Assumption Registry 和五泳道 Gate Registry；
- Claim-Evidence-Assumption 数据层；
- S0-S9 Stage Agent Registry；
- ResearchAsset、AssetRevision、patch、diff 和审批收件箱；
- G0-G3、single reviewer、four-eyes、多人会签和审批失效。

退出条件：Agent 自批、过期 revision 审批和错误失效均为 0；核心 Claim 的证据覆盖规则可以强制执行。

## Phase 3：受控计算与 Stata

时间：W11-W14。

交付：

- Python OCI sandbox、任务队列、取消和事件流；
- DuckDB/Polars 数据层与首批开放数据连接器；
- OLS、FE、DiD、ML baseline、LP/MILP 模板；
- BYOL Stata local/institution batch Runner；
- do-file Studio、预检、许可席位、日志和 manifest；
- 敏感数据不出本地的 local-runner POC。

退出条件：固定输入、代码、环境和 seed 的复现率 >= 95%；危险命令、网络、路径、许可和无 G3 测试全部被阻塞。

## Phase 4：稳健性、写作和可视化交付

时间：W15-W18。

交付：

- 因果、优化和预测泳道诊断与稳健性矩阵；
- Repro Auditor 与 Skeptical Reviewer；
- 只从批准 Claim 生成大纲和正文；
- DOI、引用蕴含和数值-表图一致性审计；
- G4/G5 审批；
- Markdown、LaTeX、DOCX、BibTeX、HTML 报告和研究包导出。

退出条件：注入的设计/代码错误至少 90% 被发现；成稿核心结论 100% 可回到证据或 Run。

## Phase 5：协作、治理与试点

时间：W19-W24。

交付：

- OIDC、组织/项目 RBAC、审计、配额和删除；
- 团队筛选冲突、评论、任务和通知；
- 模型调用、成本和延迟可观测性；
- 六个跨泳道真实课题试点，其中至少三个使用 Stata；
- 安全、隐私、性能、恢复和发布评审。

Go/No-Go：P0 缺陷为 0；引文错误率 < 1%；复现率 >= 95%；核心门禁不可绕过；至少 4/6 试点愿意继续使用。

## 当前优先顺序

近期只按以下顺序推进：

```text
测试与基线
  -> DomainProfile 去硬编码
  -> ResearchProtocol + Legacy Adapter
  -> 多源检索并集
  -> PaperCard v2
  -> Artifact Manifest v2
  -> Gate Registry
  -> Topic Scout
  -> Revision / Approval
  -> Stata Runner
  -> Web/API 平台化
```

在 Topic Scout、证据追溯和人工审批竖切通过前，不建设复杂知识图动画、通用算力平台或大规模多 Agent 网络。
