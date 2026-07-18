# AI4MS / RiffBand

面向管理科学研究的可审计、可审批、可复现 AI 科研工作平台。

> 当前 `ai4s` 分支正在把 RiffBand 从通用研究编排原型改造为 AI4MS 产品。仓库中已经存在的 CLI、MCP、Agent Runtime、研究流水线和 HTML 可视化报告仍可使用；课题侦察、研究协议、人工审批、证据链和 Stata 工作台正在按路线图建设。

[English](README.md) | [文档索引](docs/README.md) | [产品定义](docs/00_PRODUCT.md) | [开发路线](docs/00_ROADMAP.md)

## 产品定位

AI4MS 不是自动论文生成器。它更像一名严谨的科研项目经理和研究助理，帮助研究者从一个不成熟的想法出发，完成已有研究检索、选题判断、研究设计、数据与方法规划、分析管理、证据核查、可视化报告和复现交付。

核心工作流：

```text
研究想法
  -> 课题简报 TopicBrief
  -> 已有研究与选题建议报告 RelatedResearchReport
  -> G0 人工确认选题
  -> 研究协议 ResearchProtocol
  -> 理论、数据、方法与分析
  -> Claim-Evidence-Assumption
  -> 写作、HTML 可视化报告与复现包
```

## 首个产品竖切

第一阶段优先交付“课题侦察与已有研究报告”：

- 将模糊研究想法拆成概念块、同义词、排除词和相邻学科术语；
- 对多个学术来源执行地平线扫描、系统扩展和空白反向检索；
- 形成研究流派、代表论文、共识、争议和未知；
- 从理论、情境、数据、方法、时间和实践六类识别候选空白；
- 连接数据可得性、方法适配、关键假设和停止条件；
- 生成 2-3 个候选课题，由研究者或导师完成 G0 审批。

“本次没有检索到”不会被写成“绝对不存在”。机器只能提出候选空白，不能自行确认原创性。

## 人机协作

研究过程由 S0-S9 十个阶段组织，并设置 G0-G5 六个人工门禁。AI 只能创建草稿、patch、问题和建议，不能批准自己的输出。

所有可编辑研究资产都产生不可变 revision；审批绑定具体 revision 和 SHA-256。上游选题、设计、数据或分析计划发生语义变化时，受影响的下游审批自动失效，但历史决定不会被删除。

## 多学科泛用性

AI4MS 首先服务管理科学，但不会把某一课题或某一种方法写死在流程里。统一 Research Protocol 与 DomainProfile 支持以下研究泳道：

- 实证与因果研究；
- 解析建模与优化；
- 预测与计算研究；
- 行为、实验与定性研究；
- 系统综述与设计科学。

领域差异通过 profile、方法卡、数据卡和 Gate Registry 注入，通用 Agent Runtime、资产版本、审批和证据模型保持稳定，为后续扩展到更多科研学科保留接口。

## HTML 可视化报告

现有 RiffBand 已支持独立 HTML 研究报告、响应式排版、目录、表格和 ECharts 图表。AI4MS 将保留并升级这项能力，使 HTML 报告直接展示：

- 检索范围和来源覆盖；
- 研究流派与时间脉络；
- 共识、争议和反向证据；
- 候选空白及其覆盖限制；
- 数据与方法可行性；
- 候选课题、人工决定和审计记录。

## 工程基础

RiffBand 基于论文 [AOrchestra: Automating Sub-Agent Creation for Agentic Orchestration](https://arxiv.org/abs/2602.03786) 的动态子智能体思想开发。AOrchestra 将智能体抽象为四元组：

```text
<Instruction, Context, Tools, Model>
```

中央编排器根据任务动态构造四元组并委派给子智能体。RiffBand 在此基础上增加了固定研究流水线、工具权限、并发委派、CLI/MCP 接口、结构化产物和 HTML 报告。AI4MS 将继续复用这些底层能力，并重构研究领域层。

## 当前可用入口

安装：

```bash
pip install -e .
```

创建本地配置：

```powershell
Copy-Item .env.example .env
Copy-Item aorchestra.yaml.example aorchestra.yaml
```

启动 CLI：

```bash
riffband
```

当前兼容研究命令：

```text
/research 企业采用生成式AI对创新绩效的影响 --depth=deep
/research 低碳物流与供应链优化 --mode=visual --depth=deep --format=html
```

当前 CLI/MCP 参数是迁移期兼容接口，不代表 AI4MS 最终的产品信息架构。

## 文档

- [文档索引与版本口径](docs/README.md)
- [AI4MS 产品定义](docs/00_PRODUCT.md)
- [AI4MS 开发路线](docs/00_ROADMAP.md)
- [开发与运行指南](docs/00_GUIDELINE.md)
- [协作与提交规范](docs/00_WORKFLOW.md)
- [AI4MS DevPack v0.3](docs/refer/AI4MS-DevPack_v0.3/README.md)
- [当前工程基线](docs/ai4ms/BASELINE.md)

## 边界

- 不承诺自动发现绝对原创课题；
- 不伪造论文、DOI、数据、统计量或审稿记录；
- 不绕过付费数据库、版权、数据许可和软件许可；
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
