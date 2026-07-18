# AI4MS / RiffBand

面向管理科学（MS）的垂直 AI 科研工作台：从研究想法、文献和设计，到分析、证据、HTML 可视化报告与成果交付。

> 当前 `ai4s` 分支已经提供可运行的九步浏览器工作台、FastAPI、SQLite 项目状态、不可变 revision、人工门禁、领域画像和 Docker 打包文件。现有 CLI、MCP、Agent Runtime、研究流水线和 HTML 报告继续作为工程基础；分阶段 AI、方法数据、Stata、证据和成果交付服务仍在六天冲刺中实现，本文档不把规划能力写成已上线能力。

[文档索引](docs/README.md) | [产品定义](docs/00_PRODUCT.md) | [开发路线](docs/00_ROADMAP.md) | [开发指南](docs/00_GUIDELINE.md)

## 产品定位

AI4MS 不是自动论文生成器。它更像一名严谨的科研项目经理和研究助理，帮助研究者从一个不成熟的想法出发，完成已有研究检索、选题判断、研究设计、数据与方法规划、分析管理、证据核查、可视化报告和复现交付。

产品形态可以理解为“MS 领域的轻量玻尔”：把文献、研究过程、方法数据、科研计算和成果组织在同一个工作台中，并针对管理科学强化研究设计、Stata、证据边界和人工决定。AI4MS 与玻尔不存在隶属关系，也不复制其未公开能力。

核心工作流：

```text
研究想法
  -> 1. 说出想法
  -> 2. 查看已有研究
  -> 3. 选择值得做的课题
  -> 4. 确认理论与研究设计
  -> 5. 确认数据与合规
  -> 6. 制定分析计划和 Stata 代码
  -> 7. 运行、稳健性检查和复现
  -> 8. 审核证据和结果解释
  -> 9. 写作、发布和交付
```

## 当前实现

九步已经进入同一个项目工作台，当前基础能力包括：

- 创建、读取和切换科研项目；
- 查看九步状态并逐步解锁；
- 编辑和保存结构化阶段资产；
- 为每次修改生成不可变 revision 和 SHA-256 hash；
- 人工执行批准、退回修改和阻塞决定；
- 上游修改后自动使下游状态失效，同时保留历史审批；
- 通过 SQLite 在重启后恢复项目；
- 通过浏览器 GUI、远程 API 和 OpenAPI 使用同一服务层。

当前“生成草稿”只生成明确标记为 `structure_template` 的结构模板，不伪装成模型研究结果。后续 Agent 服务继续复用同一 revision 和审批接口。

保留的研究引擎已经支持多来源文献检索、结构化研究产物和独立 HTML 可视化报告。课题侦察、研究设计、数据方法、Stata Runner、Claim-Evidence 审核和成果导出将在现有九步结构上继续接入。

## 人机协作

AI 只能创建草稿、patch、问题和建议，不能批准自己的输出。G0-G5 人工门禁必须由 `human` 身份执行。

所有可编辑研究资产都会产生不可变 revision；审批绑定具体 revision 和 hash。上游选题、设计、数据或分析计划发生变化时，受影响的下游审批自动失效，但历史决定不会被删除。

## 多学科泛用性

AI4MS 首先服务管理科学，但不会把某个课题或单一方法写死在通用流程里。统一 `DomainProfile` 支持以下研究泳道：

- 实证与因果研究；
- 解析建模与优化；
- 预测与计算研究；
- 行为、实验与定性研究；
- 系统综述与设计科学。

领域差异通过 profile、方法卡、数据卡和 Gate Registry 注入，通用 Agent Runtime、资产版本、审批和证据模型保持稳定，为后续扩展到其他科研学科保留接口。

## HTML 可视化报告

RiffBand 已支持独立 HTML 研究报告、响应式排版、目录、表格和 ECharts 图表。AI4MS 保留并升级这项能力，用于展示检索范围、研究流派、共识争议、候选空白、数据方法可行性、人工决定和审计记录。

HTML 报告是成果交付阶段的一等产物，不属于需要清理的旧工程内容。

## 工程基础

RiffBand 基于论文 [AOrchestra: Automating Sub-Agent Creation for Agentic Orchestration](https://arxiv.org/abs/2602.03786) 的动态子智能体思想开发。原论文将动态创建的智能体抽象为：

```text
<Instruction, Context, Tools, Model>
```

RiffBand 在此基础上增加了固定研究流水线、工具权限、并发委派、CLI/MCP 接口、结构化产物和 HTML 报告。AI4MS 继续复用这些底层能力，并把原有课题硬编码替换为领域画像和研究协议驱动的服务。

## 安装与运行

安装项目：

```powershell
pip install -e .
```

创建本地配置：

```powershell
Copy-Item .env.example .env
Copy-Item aorchestra.yaml.example aorchestra.yaml
```

启动九步浏览器工作台：

```powershell
ai4ms-web
```

打开以下地址：

- 工作台：`http://localhost:8000/`
- 远程 API：`http://localhost:8000/api/v1`
- OpenAPI：`http://localhost:8000/docs`
- 健康检查：`http://localhost:8000/healthz`

兼容 CLI 和 MCP 入口：

```powershell
riffband
riffband-mcp --config aorchestra.yaml
```

兼容研究命令：

```text
/research 企业采用生成式AI对创新绩效的影响 --depth=deep
/research 低碳物流与供应链优化 --mode=visual --depth=deep --format=html
```

## Docker 交付

比赛版本以带浏览器 GUI 的 Docker Web 产品交付：

```powershell
docker compose up --build
```

SQLite、项目资产和 HTML 报告通过 Docker volume 持久化。模型与检索 Key 在运行时注入；Stata 使用外部自有许可 Runner，不进入镜像。

详细说明见 [Docker 部署说明](docs/DEPLOYMENT.md) 和 [远程 API 调用说明](docs/API_USAGE.md)。

## 文档

- [文档索引与版本口径](docs/README.md)
- [AI4MS 产品定义](docs/00_PRODUCT.md)
- [AI4MS 开发路线](docs/00_ROADMAP.md)
- [开发与运行指南](docs/00_GUIDELINE.md)
- [协作与提交规范](docs/00_WORKFLOW.md)
- [AI4MS DevPack v0.3](docs/refer/AI4MS-DevPack_v0.3/README.md)
- [当前工程基线](docs/ai4ms/BASELINE.md)
- [前端交接说明](src/web/README.md)

## 产品边界

- 不承诺自动发现绝对原创课题；
- 不伪造论文、DOI、数据、统计量、实验或审稿记录；
- 不绕过付费数据库、版权、数据许可、隐私控制和软件许可；
- 不把相关性、显著性或模型复杂度自动等同于因果和贡献；
- 不让 AI 越过选题、设计、数据、分析、结论和发布审批；
- 不允许写作层隐藏失败诊断、负结果和反证。

## 许可证与引用

本项目保留原始 Apache 2.0 `LICENSE`。使用底层编排思想时，请引用原论文：

```bibtex
@misc{ruan2026aorchestra,
  title={AOrchestra: Automating Sub-Agent Creation for Agentic Orchestration},
  author={Jianhao Ruan and Zhihao Xu and Yiran Peng and Fashen Ren and
          Zhaoyang Yu and Xinbing Liang and Jinyu Xiang and Yongru Chen and
          Bang Liu and Chenglin Wu and Yuyu Luo and Jiayi Zhang},
  year={2026},
  eprint={2602.03786},
  archivePrefix={arXiv},
  primaryClass={cs.AI},
  url={https://arxiv.org/abs/2602.03786}
}
```
