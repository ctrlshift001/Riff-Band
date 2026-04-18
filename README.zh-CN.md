# AOrchestra-Agent

[![Arxiv](https://img.shields.io/badge/2602.03786-arXiv-red)](https://arxiv.org/abs/2602.03786)

AOrchestra-Agent 是一个建立在原始 **AOrchestra** 论文与代码基础上的开发项目。

这个仓库不只是单纯复现论文结果。我们当前的目标，是把论文中的多智能体编排思想继续往前推进，做成一个更好的**通用型 Agent 系统**。这个系统希望具备：

- 以 **TUI / CLI** 为核心的产品形态
- 面向日常任务的 **单 Agent 常规模式**
- 面向复杂任务的 **动态多 Agent 模式**
- 面向特定任务的优化 profile，其中**产业研究**是当前第一个重点打磨的方向

## 与原论文的关系

本仓库建立在以下工作之上：

> **AOrchestra: Automating Sub-Agent Creation for Agentic Orchestration**  
> Jianhao Ruan, Zhihao Xu, Yiran Peng, Fashen Ren, Zhaoyang Yu, Xinbing Liang, Jinyu Xiang, Bang Liu, Chenglin Wu, Yuyu Luo, Jiayi Zhang  
> arXiv:2602.03786

原论文的核心思想，是把一个子 Agent 抽象成四元组：

- `I`: Instruction
- `C`: Context
- `T`: Tools
- `M`: Model

这个四元组仍然是本仓库最重要的理论基础。不同的是，这个仓库的目标已经不再局限于 benchmark 导向的研究实现，而是希望在这个抽象之上继续发展出更实用的通用 Agent 系统。

## 当前项目的新方向

本仓库当前的定位可以概括为：

> 一个以 TUI 为主要交互形态的通用型 Agent 系统，支持单 Agent 常规模式与动态多 Agent 协作模式，并针对产业研究任务进行专项优化。

这意味着：

- 我们保留原有论文 / benchmark 体系
- 我们同时继续推进更偏产品化的应用主线
- 产业研究是第一个重点优化场景，但不是唯一场景
- 当前阶段明确坚持 TUI，不做 GUI

## 为什么要这样转向

我们认为，AOrchestra 的价值不应该只停留在论文 benchmark 上。

动态创建子 Agent 的能力，不仅能服务于 GAIA、SWE-bench、TerminalBench，也很适合真实复杂任务，例如：

- 调研与分析
- 多步骤检索与整理
- 证据收集与报告生成
- 长链路问题求解

因此，这个仓库正在往一个“双模式”的通用 Agent 系统演进。

## 两种模式

### 1. 单 Agent 常规模式

这个模式面向轻量、直接、低延迟任务。

适合：

- 日常问答
- 简单搜索与总结
- 基础文件处理
- 助手式工作流

它的目标是提供更稳定、更便宜、更直接的默认体验。

### 2. 动态多 Agent 模式

这是本项目最有特色的能力。

适合：

- 可拆解的复杂任务
- 多阶段任务
- 需要多工具协作的任务
- 需要并行化处理的任务

在这个模式下，主 Agent 会根据任务动态合成不同的子 Agent，并为它们分配不同的指令、上下文、工具和模型，再汇总结果完成整体任务。

## 为什么坚持 TUI，不做 GUI

当前阶段，我们明确选择 **TUI / CLI** 作为主要交互形态，而不是 GUI。

原因包括：

- 更符合当前代码基础
- 更适合快速迭代 runtime 与 orchestration
- 更容易展示任务执行过程、日志与 agent 协作链路
- 更适合开发者、研究者和高级用户的使用方式

所以这里的 TUI 不是 GUI 的临时替代，而是当前阶段的正式产品形态。

## 仓库结构

这个仓库目前主要有两条线。

### 1. 论文 / Benchmark / 研究实现线

原有的研究与 benchmark 相关内容，现在主要集中在 [aorchestra/](./aorchestra) 下：

```text
aorchestra/
  benchmark/      # benchmark 适配、数据集相关代码
  runners/        # benchmark runner
  subagents/      # 研究体系下的 subagent 实现
  tools/          # 编排工具
  scripts/        # benchmark 启动入口
```

这一部分主要用于：

- 保留原论文体系
- 运行 benchmark
- 承载 legacy orchestration 代码

### 2. 产品 / 应用探索线

较新的应用化探索，目前主要在 [src/](./src) 以及相关入口文件中：

```text
src/
  agents/
  base/
  core/
  environments/
  orchestration_tools/
  project/
run_agents.py
config/gba_analysis.yaml
```

这一部分主要用于探索：

- 更通用的 runtime 组织方式
- 应用任务工作流
- profile 化能力
- 面向 TUI 的通用 Agent 系统路线

目前这条应用线仍然更偏向**产业研究**场景，但长期目标并不局限于这一种任务。

## 当前重点：产业研究作为第一个优化 Profile

本仓库当前第一个重点优化的 profile 是**产业研究**，尤其是这类工作流：

- 政策研究
- 公司研究
- 产业链分析
- 新闻与信号收集
- 报告生成

我们认为这类任务特别适合动态多 Agent，因为它天然具备：

- 任务可拆分
- 信息源多样
- 需要证据链
- 需要结构化输出

但要强调的是：

这并不表示仓库的长期目标是“只做产业研究 Agent”，而是表示产业研究是第一个深度打磨的场景。

## 快速开始

### 安装

```bash
conda create -n orchestra python=3.13
conda activate orchestra
pip install -r requirements.txt
```

### 配置

```bash
cp .env.example .env
cp config/example/model_config.yaml config/
cp -r config/example/benchmarks config/
```

然后补充：

- `.env`
- `config/model_config.yaml`

## 运行当前应用原型

当前应用化入口是：

```bash
python run_agents.py --config config/gba_analysis.yaml
```

这个入口目前会从终端读取任务内容，运行一个面向产业分析的工作流，并将结果输出到 `workspace/output/`。

## 运行论文 / Benchmark 体系

benchmark 入口现在收在 `aorchestra.scripts` 下：

```bash
python -m aorchestra.scripts.bench_aorchestra_gaia --config config/benchmarks/aorchestra_gaia.yaml
python -m aorchestra.scripts.bench_aorchestra_swebench --config config/benchmarks/aorchestra_swebench.yaml
python -m aorchestra.scripts.bench_aorchestra_terminalbench --config config/benchmarks/aorchestra_terminalbench.yaml
```

## 数据集准备

| Benchmark | 下载地址 | 放置位置 |
|---|---|---|
| **GAIA** | https://huggingface.co/datasets/gaia-benchmark/GAIA | `aorchestra/benchmark/gaia/data/Gaia/` |
| **TerminalBench** | https://www.tbench.ai/leaderboard/terminal-bench/2.0 | `aorchestra/benchmark/terminalbench/terminal-bench/` |
| **SWE-bench** | 使用 Hugging Face 配置 | 见 `config/benchmarks/aorchestra_swebench.yaml` |

推荐命令：

```bash
huggingface-cli download gaia-benchmark/GAIA --repo-type dataset --local-dir aorchestra/benchmark/gaia/data/Gaia
git clone --depth=1 https://github.com/laude-institute/terminal-bench-2.git aorchestra/benchmark/terminalbench/terminal-bench
```

## API Key

本仓库常见会用到的 key 包括：

- `JINA_API_KEY`
- `SERPER_API_KEY`
- `E2B_API_KEY`
- `DAYTONA_API_KEY`
- `config/model_config.yaml` 中配置的模型 key

## 当前状态

这个仓库目前处在一个“研究实现向产品化演进”的过渡阶段。

已经明确的部分：

- 原论文 / benchmark 体系被保留下来
- benchmark 相关代码正在向 `aorchestra/` 内部收拢
- 新的应用主线已经存在，并在继续调整
- 项目方向已经明确转向通用型 Agent 系统

仍在推进中的部分：

- 统一 runtime 结构
- 在代码层明确 single-agent / dynamic-multi-agent 双模式
- 构建更强的 TUI 工作流
- 从第一个产业研究 profile 继续扩展到更通用的任务体系

## 引用

如果你使用的是原始 AOrchestra 研究思想，请引用原论文：

```bibtex
@misc{ruan2026aorchestraautomatingsubagentcreation,
      title={AOrchestra: Automating Sub-Agent Creation for Agentic Orchestration},
      author={Jianhao Ruan and Zhihao Xu and Yiran Peng and Fashen Ren and Zhaoyang Yu and Xinbing Liang and Jinyu Xiang and Bang Liu and Chenglin Wu and Yuyu Luo and Jiayi Zhang},
      year={2026},
      eprint={2602.03786},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2602.03786},
}
```
