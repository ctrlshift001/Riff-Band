# AOrchestra-Agent

[![Arxiv](https://img.shields.io/badge/2602.03786-arXiv-red)](https://arxiv.org/abs/2602.03786)

AOrchestra-Agent is a development project built on top of the original **AOrchestra** paper and codebase.

This repository is not just a reproduction of the paper results. Our goal is to evolve the research prototype into a better **general-purpose agent system** with:

- a usable **TUI-first** product form
- a standard **single-agent mode** for everyday tasks
- a distinctive **dynamic multi-agent mode** for complex tasks
- task-specific optimization profiles, with **industry research** as the first focus area

## Relationship to the Original Paper

This project is based on the ideas introduced in:

> **AOrchestra: Automating Sub-Agent Creation for Agentic Orchestration**  
> Jianhao Ruan, Zhihao Xu, Yiran Peng, Fashen Ren, Zhaoyang Yu, Xinbing Liang, Jinyu Xiang, Bang Liu, Chenglin Wu, Yuyu Luo, Jiayi Zhang  
> arXiv:2602.03786

The original work models a sub-agent as a configurable four-tuple:

- `I`: Instruction
- `C`: Context
- `T`: Tools
- `M`: Model

That four-tuple remains the conceptual foundation of this repository. What changes here is the product direction: instead of stopping at benchmark-oriented orchestration research, we want to build a stronger general agent system around the same core abstraction.

## Current Direction

The current direction of this repository is:

> Build a TUI-based general-purpose agent system that supports both single-agent execution and dynamic multi-agent orchestration, while applying deeper optimization to industry research tasks.

In practice, this means:

- keeping the original research and benchmark stack available
- continuing to explore a product-oriented runtime in parallel
- treating industry research as the first optimized profile, not the only use case
- prioritizing TUI over GUI in the current stage

## Why This Direction

We think the original AOrchestra idea is stronger than a single benchmark story.

The dynamic creation of sub-agents is useful not only for GAIA, SWE-bench, or TerminalBench, but also for real-world complex tasks such as:

- research and analysis
- multi-step information gathering
- evidence collection and report generation
- long-horizon problem solving

So this repository is moving toward a system with two clear operating modes.

## Two Modes

### 1. Single-Agent Mode

This is the standard mode for lightweight tasks.

Use it when we want:

- lower cost
- lower latency
- simpler execution
- a more assistant-like workflow

### 2. Dynamic Multi-Agent Mode

This is the distinctive mode of the project.

Use it when tasks are:

- decomposable
- multi-step
- tool-heavy
- better solved through specialization and coordination

In this mode, a main agent can dynamically synthesize sub-agents with different instructions, contexts, tools, and models, then coordinate their execution and merge results.

## TUI Instead of GUI

At this stage, we are intentionally building around **TUI / CLI**, not GUI.

Why:

- it matches the current state of the codebase
- it is better for fast iteration on orchestration and runtime design
- it exposes execution flow, logs, and agent coordination more clearly
- it is a better fit for developer and research workflows

The long-term product goal is not “a chat page,” but a capable terminal-first agent workspace.

## Repository Structure

This repository currently contains two major lines of work.

### 1. Research / Benchmark Line

The original paper-oriented implementation is now centered under [aorchestra/](./aorchestra):

```text
aorchestra/
  benchmark/      # benchmark adapters, datasets, benchmark-specific utilities
  runners/        # benchmark runners
  subagents/      # research-oriented subagent implementations
  tools/          # orchestration tools
  scripts/        # benchmark entrypoints
```

This line is mainly for:

- the original research setup
- benchmark evaluation
- legacy orchestration components

### 2. Product / Application Line

The newer application-oriented work currently lives mainly under [src/](./src) and related files:

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

This line is where we are exploring:

- general runtime ideas
- application workflows
- profile-specific optimizations
- the path toward a TUI-based general agent system

At the moment, this application line still leans heavily toward the **industry research** profile, but the long-term goal is broader than that single scenario.

## Current Focus: Industry Research as the First Profile

The first heavily optimized profile in this repository is **industry research**, especially structured research workflows such as:

- policy research
- company research
- supply-chain analysis
- news and signal collection
- report drafting

We consider this a very suitable proving ground for dynamic multi-agent orchestration because these tasks are naturally parallelizable and require evidence-backed output.

Important: this does **not** mean the repository is permanently limited to an industry-research-only product. It means industry research is the first deep optimization target.

## Quick Start

### Install

```bash
conda create -n orchestra python=3.13
conda activate orchestra
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
cp config/example/model_config.yaml config/
cp -r config/example/benchmarks config/
```

Then fill in:

- `.env`
- `config/model_config.yaml`

## Run the Current Application Prototype

The current application entrypoint is:

```bash
python run_agents.py --config config/gba_analysis.yaml
```

This currently runs an industry-analysis-oriented workflow from terminal input and writes outputs to `workspace/output/`.

## Run the Research / Benchmark Stack

Benchmark entrypoints are now under `aorchestra.scripts`:

```bash
python -m aorchestra.scripts.bench_aorchestra_gaia --config config/benchmarks/aorchestra_gaia.yaml
python -m aorchestra.scripts.bench_aorchestra_swebench --config config/benchmarks/aorchestra_swebench.yaml
python -m aorchestra.scripts.bench_aorchestra_terminalbench --config config/benchmarks/aorchestra_terminalbench.yaml
```

## Dataset Setup

| Benchmark | Download | Put it here |
|---|---|---|
| **GAIA** | https://huggingface.co/datasets/gaia-benchmark/GAIA | `aorchestra/benchmark/gaia/data/Gaia/` |
| **TerminalBench** | https://www.tbench.ai/leaderboard/terminal-bench/2.0 | `aorchestra/benchmark/terminalbench/terminal-bench/` |
| **SWE-bench** | Use Hugging Face dataset config | See `config/benchmarks/aorchestra_swebench.yaml` |

Recommended commands:

```bash
huggingface-cli download gaia-benchmark/GAIA --repo-type dataset --local-dir aorchestra/benchmark/gaia/data/Gaia
git clone --depth=1 https://github.com/laude-institute/terminal-bench-2.git aorchestra/benchmark/terminalbench/terminal-bench
```

## API Keys

Typical keys used in this repository include:

- `JINA_API_KEY`
- `SERPER_API_KEY`
- `E2B_API_KEY`
- `DAYTONA_API_KEY`
- model keys configured in `config/model_config.yaml`

## Status

This repository is in a transitional stage.

What is already true:

- the original paper/benchmark stack is preserved
- benchmark-related code has been consolidated under `aorchestra/`
- a newer application line exists and is actively being reshaped
- the product direction has shifted toward a general agent system

What is still in progress:

- unifying the runtime structure
- making the two modes explicit in code structure
- building a stronger TUI workflow
- generalizing beyond the first industry-research profile

## Citation

If you use the original AOrchestra research idea, please cite the original paper:

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
