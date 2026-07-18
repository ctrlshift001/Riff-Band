# AI4MS / RiffBand

面向管理科学（MS）的垂直 AI 科研工作台：从研究想法、文献和设计，到分析、证据与交付。

> 当前 `ai4s` 分支正在把 RiffBand 从通用研究编排原型改造为完整的单用户 AI4MS 工作台。现有 CLI、MCP、Agent Runtime、研究流水线和 HTML 报告是工程基础；九步 Web 工作区、项目状态、人工审批、方法数据、Stata、证据和成果交付正在六天冲刺中实现。README 不把规划能力冒充为已上线能力。

[English](README.md) | [文档索引](docs/README.md) | [产品定义](docs/00_PRODUCT.md) | [开发路线](docs/00_ROADMAP.md)

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

## 九步产品工作台

用户在一个项目中依次完成九步。每一步都有当前任务、AI 草稿、结构化编辑、来源或运行依据、批准/退回和下一步；项目重启后仍能恢复。课题侦察负责真实多源检索、研究版图、反向查询和候选题，后续工作区继续连接理论设计、数据方法、分析代码、运行诊断、Claim-Evidence 和成果导出。

六天比赛版本采用本地单用户 Web 工作台和 SQLite/文件资产，九步都提供真实代码路径；组织登录、多人会签和云端计算属于部署增强，不是用来替代产品闭环的前置工程。

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

## 最终交付形态

比赛版本将交付一个带浏览器 GUI 的 Docker 化 Web 产品。容器同时提供：

- `/`：九步 MS 科研工作台；
- `/api/v1`：远程调用接口；
- `/docs`：OpenAPI 文档；
- `/healthz`：部署健康检查。

SQLite、项目资产和 HTML 报告通过 Docker volume 持久化。模型与检索 Key 在运行时注入；Stata 使用外部自有许可 Runner，不进入镜像。

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
