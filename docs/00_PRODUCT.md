# AI4MS 产品定义

## 1. 一句话定位

AI4MS 是一套面向管理科学研究的 AI 科研工作平台，帮助研究者把一个早期想法转化为可审计、可人工批准、可追溯且可复现的研究项目。

它不是自动论文生成器，也不是只返回一段答案的通用聊天助手。产品管理的是长期研究项目中的对象、证据、版本、决定和运行记录。

## 2. 要解决的问题

现有科研工具分别覆盖检索、阅读、数据、统计、写作和协作，但研究决策通常散落在聊天记录、表格、本地文件和不同软件中，导致：

- 研究问题已经被相邻术语下的论文回答，却在后期才发现；
- “没有搜到”被误写成“从未有人研究”；
- 数据不可得、许可不允许或测量口径不成立；
- 方法形式正确，但不能支持目标结论；
- 代码、数据、表图和正文来自不同版本；
- 关键修改和审批没有记录，项目难以交接和复现。

AI4MS 的第一原则是：

> 先弄清别人已经做了什么，再决定我们真正值得做什么。

## 3. 核心对象链

```text
TopicBrief
  -> SearchProtocol / SearchRun
  -> Paper / PaperCard
  -> ResearchStream / EvidenceSynthesis / GapCandidate
  -> RelatedResearchReport / TopicCandidate
  -> ResearchAsset / AssetRevision / Approval
  -> ResearchProtocol
  -> DataContract / Method / Formula / Assumption
  -> Run / StataRun / Artifact
  -> Claim / Evidence / Assumption
  -> Manuscript / Visual HTML Report / Reproducible Package
```

对话只是操作这些对象的一种入口，不能成为项目事实的唯一载体。

## 4. 首要产品能力：Topic Scout

用户输入一句不成熟的研究想法后，Topic Scout 依次执行：

1. 地平线扫描：寻找经典研究、近年进展和相邻术语；
2. 系统扩展：扩展数据库、查询、引文和代表论文；
3. 空白反向复核：专门寻找最接近、可能推翻候选空白的研究。

输出的 RelatedResearchReport 包括：

- 课题边界和检索快照；
- 主要研究流派与时间脉络；
- 相对稳定的共识、争议、证据有限项和未知；
- 代表论文及字段级证据定位；
- 理论、情境、数据、方法、时间和实践六类候选空白；
- 数据、许可、方法、假设和计算可行性；
- 2-3 个候选课题、最近似研究、风险和停止条件；
- 参考文献、查询、筛选、模型调用和人工修改审计。

机器只能把空白标记为 `candidate`。完成反向查询、覆盖限制说明和人工审批后，才可以成为 `supported_gap`。

## 5. 阶段智能体与人工门禁

系统内部采用十个研究阶段：

| 阶段 | 主任务 |
|---|---|
| S0 | 课题与边界 |
| S1 | 文献与已有研究 |
| S2 | 理论与机制 |
| S3 | 研究设计 |
| S4 | 数据与合规 |
| S5 | 分析计划 |
| S6 | 代码与执行 |
| S7 | 诊断与稳健性 |
| S8 | 证据与主张 |
| S9 | 写作与交付 |

用户在每个阶段只面对一名主智能体。辅助智能体可以在内部执行检索、抽取或对抗审查，但不能直接修改已批准资产。

六个人工门禁分别控制：

| Gate | 人工决定 |
|---|---|
| G0 | 已有研究报告与选题 |
| G1 | 理论和研究设计 |
| G2 | 数据、伦理与许可 |
| G3 | 分析计划和代码冻结 |
| G4 | 结果解释和核心 Claim |
| G5 | 成稿、发布和研究包 |

Agent 没有 approve 权限。审批必须绑定对象 revision、内容 hash、检查清单、角色和时间。

## 6. 多学科泛用性

AI4MS 采用“一套共同母流程 + 多类方法泳道”：

- 实证与因果；
- 解析与优化；
- 预测与计算；
- 行为、实验与定性；
- 综述与设计科学。

共同母流程管理课题、协议、证据、版本、审批和复现。不同学科和方法的查询扩展、抽取字段、假设、诊断与门禁由 DomainProfile 和 Registry 提供，不写死在通用流水线中。

第一批跨题型基准至少覆盖企业 AI 采用、低碳车辆路径和平台信息共享，以验证系统不会再次出现单一领域串扰。

## 7. HTML 可视化报告

HTML 报告是 AI4MS 的主要交付与审阅界面之一，不只是 Markdown 的装饰性导出。它应从版本化结构对象生成，并允许用户从结论回到证据和审计记录。

首批可视化包括：

- 检索来源、命中、去重、筛选和纳入统计；
- 研究流派、时间脉络和代表论文；
- 共识、争议、反证和证据状态；
- Gap Map 与反向检索覆盖；
- 数据与方法可行性矩阵；
- 候选课题比较；
- Claim-Evidence-Assumption 表；
- Gate、revision 和审批历史。

视觉层不能重新计算、改写或隐藏底层数值和证据状态。

## 8. Stata 工作台

Stata 能力采用用户或机构自带许可的 local/institution Runner：

- AI 根据已批准分析计划提交可审阅的 do-file patch；
- 用户逐段接受、修改或拒绝；
- G3 绑定分析计划 revision、do-file hash、Data Contract 和 Runner 环境；
- Runner 默认无网络、只读输入、独立输出并限制资源；
- 保存 SMCL/text 日志、退出码、数据签名、版本、ado 清单和输出 hash；
- 原始运行数值不可编辑，变化只能来自新 Run；
- G4 由人批准结果解释和 Claim。

平台不包含、复制、转售或绕过 Stata 许可。

## 9. 信任与治理

- PostgreSQL 是结构化事实的权威来源，向量索引只负责候选召回；
- 论文、数据、日志和运行数值不可静默覆盖；
- 重要陈述必须连接到论文定位、数据结果或运行产物；
- `supported`、`contested`、`limited`、`not_found`、`inference` 和 `human_verified` 明确区分；
- Licensed、Sensitive 和 Restricted 数据默认不能发送到外部 LLM；
- 搜索、模型、工具、代码、环境、参数和 artifact 均保留版本及 provenance；
- 负结果、失败诊断和反证不能被写作智能体隐藏。

## 10. 当前与目标边界

当前仓库已经具备：

- AOrchestra 风格的 MainAgent/SubAgent Runtime；
- 工具权限、并发委派、取消和事件流；
- 固定研究流水线与 CLI/MCP 入口；
- 多个开放文献检索适配器；
- JSONL 研究产物、LaTeX/HTML 导出和可视化 HTML 报告。

AI4MS 改造需要补齐：

- DomainProfile 和 ResearchProtocol；
- 多源检索并集、去重、快照和 PaperCard v2；
- 不可变 Revision 与统一 Approval Service；
- Topic Scout、Evidence 层和方法/数据/公式 Registry；
- FastAPI、PostgreSQL、对象存储、队列与 Web 工作区；
- Python/Stata Runner、数据治理、RBAC 和复现审计。

## 11. 明确不做

- 不保证绝对原创；
- 不绕过付费全文、版权、数据或软件许可；
- 不用引用量或单一总分代替证据判断；
- 不把相关性、显著性或预测准确率自动写成因果贡献；
- 不允许 AI 自批或在未批准代码上运行正式主分析；
- 不以自动生成论文数量作为产品成功指标；
- MVP 不建设 Kubernetes 集群、独立图数据库或通用科研应用市场。
