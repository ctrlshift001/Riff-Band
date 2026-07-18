# AI4MS 开发与运行指南

## 1. 当前状态

`ai4s` 分支处于 AI4MS 改造期。当前代码可以运行 RiffBand CLI/MCP 和既有研究流水线；DevPack 中的 Web/API、PostgreSQL、统一审批和 Stata Runner 是目标能力，不能当作已经上线。

工程基线见 [ai4ms/BASELINE.md](ai4ms/BASELINE.md)。

## 2. 环境

- Python 3.10+
- pip
- 可用的 OpenAI-compatible 或 Gemini 模型接口
- 可选的联网检索 key
- PostgreSQL、Redis、MinIO 和 Stata 暂不属于当前 CLI 基线的必需依赖

安装当前项目：

```powershell
pip install -e .
```

本地配置：

```powershell
Copy-Item .env.example .env
Copy-Item aorchestra.yaml.example aorchestra.yaml
```

密钥只能写入本地 `.env` 或受管 secret manager，不得提交到 Git、文档、日志、测试 fixture 或 prompt 示例。

## 3. 当前兼容入口

启动 CLI：

```powershell
riffband
```

示例：

```text
/research 企业生成式AI采用与创新绩效 --depth=deep
/research 低碳物流与供应链优化 --mode=visual --depth=deep --format=html
```

启动 MCP：

```powershell
riffband-mcp --config aorchestra.yaml
```

当前命令和参数在迁移期保持兼容。新的产品对象和 API 必须通过 legacy adapter 接入，不能直接破坏现有 `/research` 和 MCP 调用。

## 4. AI4MS 实现原则

### Protocol-first

研究步骤读取版本化 ResearchProtocol，不从历史聊天中猜测关键研究选择。未知字段保留为 `needs_input`，不得自动补全为用户决定。

### Evidence-first

重要陈述必须绑定 paper、data、run、artifact 或人工审查证据。向量检索和 LLM 输出只能产生候选，不能成为事实来源。

### Human approval

Agent 只能创建草稿、revision patch 和 issue。G0-G5 由独立 Approval Service 执行，批准绑定具体 revision 与 hash。

### Immutable revisions

研究资产通过新 revision 修改。论文元数据快照、原始数据、原始日志和运行数值不可直接编辑，只能更正来源、添加 annotation 或创建新 Run。

### Deterministic controls

DOI、权限、hash、schema、状态机、统计计算、许可证和代码策略使用确定性程序。LLM 只做需要语义判断的候选生成与解释。

### Reproducibility

Run 必须记录 protocol version、代码 commit、环境、参数、seed、输入输出 hash 和 lineage。固定输入、代码与环境的重放结果必须在约定容差内一致。

### Cross-disciplinary profiles

课题词、查询扩展、抽取字段、方法假设和 Gate 必须来自 DomainProfile 或 Registry。禁止在通用 pipeline 中加入某个具体课题的关键词加分和固定聚类。

### Visual report as a view

HTML 报告只能渲染结构化、版本化对象。图表和表格不得重新计算或覆盖底层数值，关键元素必须能回到 evidence、artifact、revision 和 approval。

## 5. Schema 与数据契约

第一批契约来自：

- `research_protocol.schema.json`
- `related_research_report.schema.json`
- `approval_record.schema.json`
- `artifact_manifest.schema.json`
- `claim_evidence.schema.json`
- `stata_run.schema.json`

位置：[02_knowledge_bases/schemas](refer/AI4MS-DevPack_v0.3/02_knowledge_bases/schemas)。

实现前必须先统一以下问题：

- ResearchProtocol 草案不能强制 `human_approved=true`；
- 统一 TopicBrief、Protocol 和 Report 的研究目标枚举；
- 只保留一个权威 Approval Service，避免 inline approval 绕过；
- Schema、Pydantic、OpenAPI、SQL 和示例对象使用同一状态与 ID 语义。

## 6. 测试

当前基线命令：

```powershell
pytest -q -p no:cacheprovider
```

AI4MS 新增测试至少覆盖：

- 三个跨题型 benchmark 无领域串扰；
- 任一检索后端失败时其他后端仍返回并保存 provenance；
- DOI、题名、作者、年份去重和版本关系；
- PaperCard 字段证据等级、locator 和 unknown；
- Agent 自批、过期 hash、缺少会签和越权工具被拒绝；
- 上游语义修改准确失效下游审批；
- 无 G3、危险 Stata 命令、越界路径和许可超额被阻塞；
- HTML 报告中的核心结论、图表和数字可以回溯。

验收编号和阈值见 [ACCEPTANCE_TESTS.md](refer/AI4MS-DevPack_v0.3/05_roadmap/ACCEPTANCE_TESTS.md)。

## 7. 暂不做

- 不先移动或重写整个 runtime；
- 不一次落地完整 Web 平台；
- 不把更多 Agent 数量当作质量提升；
- 不上 Kubernetes、Neo4j、Spark 或 JupyterHub；
- 不接入未明确许可的付费数据库和全文；
- 不在正式 Run 中动态安装任意包或 ado；
- 不把摘要抽取描述为全文证据。
