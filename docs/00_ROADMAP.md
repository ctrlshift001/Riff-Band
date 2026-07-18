# AI4MS ROADMAP

## 1. 交付目标

截止时间：2026-07-26。

团队在最后 6 个开发日内，把 RiffBand 改造成一个可运行、可操作、可演示的 **管理科学（Management Science, MS）垂直 AI 科研工作台**。产品形态借鉴玻尔将检索、阅读、研究和计算放在同一工作区的思路，但聚焦管理科学的研究设计、数据方法、Stata、证据审查和人工决策。

本轮不再只交付文献报告，也不按 24/36 周阶段路线拆目标。介绍书中的九个用户步骤都必须在同一个产品中有入口、状态、结构化产物和人工动作。

## 2. 九步产品闭环

| 步骤 | 用户看到的工作区 | 必须产出的对象 | 人工动作 |
|---|---|---|---|
| 1. 说出想法 | 项目创建、澄清问题、研究边界 | `TopicBrief` | 确认想法与待确认项 |
| 2. 查看已有研究 | 查询规划、多源状态、论文列表、研究版图 | `SearchRun`、`PaperCard`、`RelatedResearchReport` | 纳入、排除或标记不确定 |
| 3. 选择课题 | Gap 反向检索、2-3 张候选课题卡 | `GapCandidate`、`TopicCandidate` | G0 选择、修改或拒绝 |
| 4. 理论与设计 | 理论机制、研究问题、识别/求解思路、关键假设 | `ResearchProtocol`、`DesignPlan` | G1 确认设计 |
| 5. 数据与合规 | 数据源、变量、许可、隐私、方法与公式建议 | `DataPlan`、`MethodPlan` | G2 确认数据与合规 |
| 6. 分析计划与代码 | 分析步骤、变量表、模型式、可编辑 do-file | `AnalysisPlan`、`CodeRevision` | G3 冻结分析计划和代码 |
| 7. 运行与稳健性 | Runner 状态、日志、表图、诊断和复现信息 | `RunArtifact`、`RobustnessCheck` | 接受结果或要求重跑 |
| 8. 证据与解释 | Claim-Evidence 表、支持/反证/限制和结果解释 | `Claim`、`EvidenceLink` | G4 确认结论边界 |
| 9. 写作与交付 | 大纲、报告、引用、HTML 可视化和研究包 | `Manuscript`、`VisualReport`、`ResearchPackage` | G5 确认发布与导出 |

每一步必须支持“生成草稿、人工编辑、批准/退回、查看依据、进入下一步”。AI 不能替用户批准自己的输出。

## 3. 六天产品架构

### Web 科研工作台

- 首屏直接进入项目工作台，不建设营销落地页；
- 左侧固定九步导航，显示 `not_started/in_progress/needs_review/approved/blocked`；
- 中间显示当前步骤的结构化编辑区、AI 建议和运行结果；
- 右侧或抽屉显示来源、差异、Gate 问题和下一步；
- HTML 可视化报告作为步骤 2、8、9 的统一审阅与交付视图。

### API 与服务层

- 使用 FastAPI 提供本地 API 和静态 Web 工作台；
- `ProjectService` 管理项目、阶段状态和当前资产；
- `ResearchService` 复用现有 RiffBand Agent Runtime 和 research pipeline；
- `LiteratureService` 执行多源并集检索、规范化、去重和 provenance；
- `KnowledgeService` 加载 DevPack 的方法、公式和数据源 Registry；
- `ApprovalService` 实现本地单人 G0-G5 决定与审计；
- `RunnerService` 提供 Stata BYOL preflight/submit/collect 和明确 blocked 状态；
- `ExportService` 生成 HTML、Markdown、JSON 和研究包。

### 数据与资产

- SQLite 保存项目、阶段、资产 revision、审批和运行索引；
- `workspace/projects/<project_id>/` 保存检索快照、报告、代码、日志和导出包；
- 每个资产至少包含 ID、类型、版本、作者类型、时间和内容 hash；
- 原始论文元数据、运行日志和结果只追加，不静默覆盖；
- 六天版本为单用户本地产品，不实现组织级登录与多租户。

### Docker 交付边界

- 最终交付单镜像 `ai4ms-workbench:<version>`，同一容器提供 Web GUI 和 HTTP API；
- 容器监听 `0.0.0.0:8000`，`/` 为九步工作台，`/api/v1` 为远程调用接口，`/docs` 为 OpenAPI 文档，`/healthz` 为健康检查；
- SQLite、项目资产和导出报告写入 `/app/data`，通过 Docker volume 持久化；
- 模型和检索 Key 通过 `--env-file` 或运行时环境变量注入，禁止写入镜像；
- 容器允许访问已配置的模型和开放检索服务；断网时仍能打开已保存项目和静态报告；
- Stata 安装、许可证和受限数据不进入镜像，容器通过 `RunnerService` 连接用户或机构提供的外部 Runner；
- 同时提供 `Dockerfile`、`.dockerignore`、`docker-compose.yml`、部署说明、API 调用示例和 smoke test。

### Stata 外部依赖

当前开发机未检测到 Stata 可执行文件。D1 必须确认一台具有合法 Stata 许可的演示 Runner；若没有，产品仍需完整实现 BYOL Runner 发现、do-file 编辑、策略预检和 `blocked:no_runner` 状态，但不得宣称已经完成真实 Stata 执行。

## 4. 双人分工

| 负责人 | 产品角色 | 主责 | 主要代码边界 |
|---|---|---|---|
| 工程负责人 | Tech Lead / Integrator | 架构、API、SQLite、九步状态机、检索、Runner、测试、发布 | `src/api/`、`src/services/`、`src/db/`、`src/research/`、核心测试和工程配置 |
| 产品设计负责人 | Product & Research Lead | 九步交互、MS 规则、Prompt、方法数据内容、报告与演示 | `src/web/`、`src/research/skills/`、`src/domains/`、templates、fixtures 和产品文档 |

产品设计负责人可以 Vibecoding，但公共 Schema、状态迁移、Runner、权限和持久化由工程负责人审核。两人不得同时修改同一个核心文件；接口和示例先冻结，再并行实现。

## 5. 每日 DDL

| 日期 | 工程负责人 | 产品设计负责人 | 当日完成标准 |
|---|---|---|---|
| 7 月 21 日 D1 | 建立 FastAPI/Web 壳、SQLite ProjectStore、九步状态机和公共 Schema；验证豆包；移除通信硬编码 | 完成九步线框、字段、按钮、空/错/加载状态；冻结三个主演示课题和验收样例 | 能创建项目、切换九步、保存编辑和审批；模型真实可调用 |
| 7 月 22 日 D2 | 打通步骤 1-3：TopicBrief、多源并集检索、去重、PaperCard、Gap 和最小 G0 | 完成检索/论文/流派/候选课题界面及 Prompt，人工核查种子论文 | 从一句想法生成真实来源报告，并能人工选择课题 |
| 7 月 23 日 D3 | 打通步骤 4-5：Protocol、设计方案、方法/公式/数据 Registry、G1/G2 | 完成理论机制、设计、数据、方法、许可和风险编辑界面 | 获选课题能形成可编辑、可审批的数据方法与研究设计 |
| 7 月 24 日 D4 | 打通步骤 6-7：AnalysisPlan、do-file revision、Stata preflight/Runner、日志、诊断和复现元数据 | 完成代码 diff、运行状态、结果表图和稳健性工作区 | 有 Runner 时真实运行；无 Runner 时准确阻塞且完整展示准备结果 |
| 7 月 25 日 D5 | 打通步骤 8-9；完成 Dockerfile/Compose、健康检查、volume、API 示例和容器端到端 smoke | 完成证据中心、报告视觉、演示稿、录屏和容器内置示例项目 | Docker 启动后九步 GUI/API 完整走通两次，功能冻结 |
| 7 月 26 日 D6 | 构建固定 tag 镜像，复核部署说明、调用示例、数据迁移、测试和提交包，禁止临时开发 | 复核视频、截图、介绍、答辩和提交表单 | 中午前形成镜像与部署包，至少预留 4 小时上传和纠错 |

## 6. 产品验收

### 九步完整性

- 一个项目可以从步骤 1 走到步骤 9，并在重启后恢复；
- 每一步均有可编辑资产、AI 草稿、人工决定、状态和下一步；
- 未批准上一步时，下一关键步骤不能静默进入正式状态；
- 所有失败显示为 `blocked/partial/failed`，不能伪装为完成。

### 科研可信度

- 三个主演示课题不出现 RIS/ISAC/beamforming 串扰；
- 报告论文和外部链接真实，演示集中虚构引用为 0；
- 核心综合结论、Gap 和 Claim 均能回到论文、数据或 Run；
- “本次未检索到”与“证明不存在”严格区分；
- 摘要级证据不标记为全文证据；
- 数据或方法不可行时允许返回缩小、改题或暂停。

### 产品体验

- 首屏是实际工作台，九步状态清晰；
- 用户能在 10 分钟内找到当前任务、证据、风险和下一步；
- HTML 报告包含目录、真实来源、论文表、至少一个图表和决策摘要；
- 断网、模型失败或无 Stata Runner 时仍可打开已保存项目和报告。

### Docker 与远程调用

- `docker compose up` 或一条 `docker run` 命令可以启动产品；
- 浏览器访问 `/` 能使用完整 GUI，不依赖宿主机 Python 环境；
- `/healthz` 返回健康状态，`/docs` 能查看并试调 API；
- API 至少支持创建项目、读取项目、执行阶段、保存编辑、审批、查询任务和导出报告；
- 重启容器后，挂载卷中的项目、审批和报告仍然存在；
- 镜像历史和日志不包含 API Key、Stata 许可证或用户受限数据。

## 7. 六天范围边界

九个产品步骤不能删除，但每一步采用最小实现。以下生产级能力不在本轮建设：组织级 OIDC/RBAC、多租户、四眼/多人会签、复杂审批失效矩阵、付费数据库连接器、受限全文抓取、云端 Stata 托管、复杂知识图谱、实时协同编辑、Kubernetes、Neo4j 和大规模任务队列。

这不是用静态页面代替功能：检索、AI 生成、编辑、审批、持久化、Runner 状态、证据关联和导出都必须有真实代码路径。

## 8. 协作规则

- `ai4s` 是集成分支，个人分支使用 `feat/core-workbench-*` 和 `feat/product-workbench-*`；
- 每天至少两次合流，D4 起每天跑完整九步 smoke；
- 每个 Vibecoding PR 必须人工通读并带测试或固定样例；
- 引用虚构、状态丢失、AI 自批、运行结果可编辑、失败误报成功均为发布阻塞问题；
- D5 下午停止增加功能；D6 只处理提交阻塞问题。

详细调研、Schema 和原始规划仍保留在 [AI4MS DevPack v0.3](refer/AI4MS-DevPack_v0.3/README.md)，但不再作为当前六天交付节奏。
