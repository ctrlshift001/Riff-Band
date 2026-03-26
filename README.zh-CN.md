# AOrchestra：面向 Agent 编排的自动化 Sub-Agent 创建框架

[![Arxiv](https://img.shields.io/badge/2602.03786-arXiv-red)](https://arxiv.org/abs/2602.03786)

> 如果你在使用或复现代码时遇到问题，欢迎联系作者：[aurorra1123@gmail.com](mailto:aurorra1123@gmail.com)。

AOrchestra 是一个面向复杂任务的多智能体编排框架。在 GAIA、SWE-Bench、Terminal-Bench 三个具有挑战性的 benchmark 上，当搭配 Gemini-3-Flash 使用时，AOrchestra 相较最强基线取得了 16.28% 的相对提升。

<p align="center">
  <img src="figure/abs.png" width="75%">
</p>

现有长程多智能体系统中的 Sub-Agent 设计通常存在两类问题：

- 一类把 Sub-Agent 视作上下文隔离的线程或复制体，虽然可以缓解上下文腐化，但 Sub-Agent 的能力往往比较固定，专业化程度有限。
- 另一类依赖静态预设角色，例如 coder、searcher、writer 等，虽然具备一定专业分工，但灵活性不足，并且需要大量人工维护。

与之不同，AOrchestra 将一个 Sub-Agent 视作由四元组 `φ = <I, C, T, M>` 定义的可配置单元。

[![Diff](figure/diff.png)](figure/diff.pdf)

## 核心思想

![Introduction](figure/introduction.png)

我们的核心观点是：当任何一个（子）Agent 都可以被抽象为四元组接口 `<I, C, T, M>`，并由中心编排器在运行时动态具体化时，Agent 编排就会变得更加模块化、可控且可插拔。

这个抽象将“编排”和“执行”解耦：

- 编排器负责目标拆解与四元组合成，包括：
  - 编写可执行指令 `I`
  - 组织上下文 `C`
  - 选择工具 `T`
  - 选择模型 `M`
- 动态创建出的 Sub-Agent 则专注于执行被委派的子任务

因此，系统可以：

- 针对不同子任务动态专业化 Sub-Agent
- 显式控制上下文共享，缓解长程任务中的上下文退化
- 通过可配置的 `C`、`T`、`M` 在性能与成本之间进行权衡
- 避免依赖静态角色设计或完整上下文复制

## 仓库结构

```text
.
├── bench_aorchestra_gaia.py
├── bench_aorchestra_swebench.py
├── bench_aorchestra_terminalbench.py
├── aorchestra/                 # MainAgent / SubAgent 框架
├── benchmark/                  # Benchmark 适配层与数据集相关代码
├── config/example/benchmarks/  # Benchmark 配置模板
└── config/example/model_config.yaml
```

## 快速开始

```bash
# 1) 安装依赖
conda create -n orchestra python=3.13 && conda activate orchestra
pip install -r requirements.txt

# 2) 配置文件
cp .env.example .env
cp config/example/model_config.yaml config/
cp -r config/example/benchmarks config/

# 3) 填写 API Key
vim .env
vim config/model_config.yaml
```

## 数据集准备

| Benchmark | 下载地址 | 放置位置 |
|---|---|---|
| **GAIA** | https://huggingface.co/datasets/gaia-benchmark/GAIA | `benchmark/gaia/data/Gaia/`（配置默认读取 `benchmark/gaia/data/Gaia/2023/validation/metadata.jsonl`） |
| **TerminalBench** | https://www.tbench.ai/leaderboard/terminal-bench/2.0 | `benchmark/terminalbench/terminal-bench/`（默认配置为 `benchmark/terminalbench/terminal-bench/test`） |
| **SWE-bench** | 当前项目配置中已直接使用 | 使用 `config/benchmarks/aorchestra_swebench.yaml`（`dataset_name: princeton-nlp/SWE-bench_Verified`） |

推荐命令：

```bash
# GAIA（受限 Hugging Face 数据集，需要先申请访问权限并登录）
huggingface-cli download gaia-benchmark/GAIA --repo-type dataset --local-dir benchmark/gaia/data/Gaia

# TerminalBench（克隆任务仓库，确保 /test 可用）
git clone --depth=1 https://github.com/laude-institute/terminal-bench-2.git benchmark/terminalbench/terminal-bench
```

## API Key 配置

### 按 Benchmark 区分

| Benchmark | 必需 API Key | 可选 |
|---|---|---|
| **GAIA** | `JINA_API_KEY`、`SERPER_API_KEY`、以及 `config/model_config.yaml` 中的 LLM 配置 | - |
| **SWE-bench** | `config/model_config.yaml` 中的 LLM 配置、Docker | - |
| **TerminalBench** | `config/model_config.yaml` 中的 LLM 配置、Docker 或 `E2B_API_KEY` | `DAYTONA_API_KEY` |

### 按工具区分

| 工具 | 环境变量 | 用途 | 获取地址 |
|---|---|---|---|
| Jina | `JINA_API_KEY` | 网页内容抽取 | https://jina.ai/ |
| Serper | `SERPER_API_KEY` | Google 搜索 | https://serper.dev/ |
| E2B | `E2B_API_KEY` | 云端沙箱 | https://e2b.dev/ |
| Daytona | `DAYTONA_API_KEY` | 云端沙箱 | https://daytona.io/ |
| LLM | 配置在 `config/model_config.yaml` 中 | 模型调用 | OpenAI / Gemini / Claude 等 |

## 运行方式

| Benchmark | 命令 |
|---|---|
| **GAIA** | `python bench_aorchestra_gaia.py --config config/benchmarks/aorchestra_gaia.yaml` |
| **SWE-bench** | `python bench_aorchestra_swebench.py --config config/benchmarks/aorchestra_swebench.yaml` |
| **TerminalBench** | `python bench_aorchestra_terminalbench.py --config config/benchmarks/aorchestra_terminalbench.yaml` |

通用 CLI 参数：

```bash
--config config/benchmarks/xxx.yaml
--max_concurrency 5
--tasks task1,task2
```

各 Benchmark 特有参数：

- GAIA：`--skip_completed <path/to/results.csv>`
- SWE-bench：`--skip-completed`
- TerminalBench：`--skip_completed`

## 引用

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
