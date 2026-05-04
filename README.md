# AOrchestra

A general-purpose multi-agent system built on the [AOrchestra](https://arxiv.org/abs/2602.03786) paper, with three operating modes.

## Core Concept

The system models a sub-agent as a configurable four-tuple `(I, C, T, M)`:

| | | |
|---|---|---|
| **I** | Instruction | What the sub-agent should do |
| **C** | Context | Background information and constraints |
| **T** | Tools | The action space available to the sub-agent |
| **M** | Model | The LLM assigned to this sub-agent |

A main orchestrator agent dynamically creates sub-agents with different `(I, C, T, M)` combinations, coordinating their execution and merging results.

> The original paper and benchmark code are preserved in the `aorchestra/` directory. For details, see the [paper repository](https://github.com/franknobox/AOrchestra-Agent).

## Three Modes

### 1. `single` — Single-Agent Mode

For lightweight, straightforward tasks. A single agent executes directly, no orchestrator overhead.

Best for:
- Quick Q&A and summarization
- Simple search and file processing
- Low-cost, low-latency scenarios

### 2. `multi` — Multi-Agent Mode

For complex, decomposable tasks. A main orchestrator dynamically synthesizes sub-agents, assigning each a distinct instruction, context, tool set, and model. Sub-agents run in parallel where possible, with results merged after completion.

Best for:
- Multi-step research and analysis
- Tasks requiring multiple tools
- Evidence collection and structured report generation

### 3. `auto` — Automatic Routing Mode

The system analyzes the task text and selects the appropriate mode:
- Short, simple tasks → `single`
- Multi-step, evidence-heavy, report-oriented tasks → `multi`

The decision uses a three-tier strategy: hard rules (keyword matching) → LLM assist (ambiguous tasks) → soft rules (scoring).

## Current Focus

Industry research is the first deeply optimized profile, covering:

- Policy research
- Company analysis
- Supply-chain assessment
- News and signal collection
- Structured report generation

These tasks are naturally parallel and evidence-driven, making them a strong proving ground for dynamic multi-agent orchestration. The system itself is general-purpose — industry research is simply the first target.

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure
cp .env.example .env          # fill in LLM API key + Serper key
cp aorchestra.yaml.example aorchestra.yaml

# 3. Run interactive shell
python shell.py --config aorchestra.yaml
```

## Configuration

| File | Purpose |
|------|---------|
| `.env` | API keys (LLM, Serper, proxy) |
| `aorchestra.yaml` | Agent strategy (mode, model, profile, limits) |

See `.env.example` and `aorchestra.yaml.example` for templates.

## Shell Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/mode <single\|multi\|auto>` | Switch execution mode |
| `/model <name>` | Switch LLM model |
| `/status` | Show agent state |
| `/session` | Show session info |
| `/sessions` | List saved sessions |
| `/resume <id>` | Resume a previous session |
| `/clear` | Clear screen |
| `/exit` | Exit |

## Project Layout

```
src/
  agents/               # MainAgent, SubAgent
  core/                 # Runner, message protocol, session persistence
  environments/         # Task execution environment
  orchestration_tools/  # Delegate, complete, task plan
  project/              # Project assembly, prompts, tools
  modes/                # Mode router (single / multi / auto)
  ui/                   # Interactive shell + Rich renderer
aorchestra/             # Original paper & benchmark (legacy)
```

## Citation

```bibtex
@misc{ruan2026aorchestraautomatingsubagentcreation,
      title={AOrchestra: Automating Sub-Agent Creation for Agentic Orchestration},
      author={Jianhao Ruan and Zhihao Xu and Yiran Peng and Fashen Ren and
              Zhaoyang Yu and Xinbing Liang and Jinyu Xiang and Bang Liu and
              Chenglin Wu and Yuyu Luo and Jiayi Zhang},
      year={2026},
      eprint={2602.03786},
      archivePrefix={arXiv},
      primaryClass={cs.AI},
      url={https://arxiv.org/abs/2602.03786},
}

## License

This project is based on [AOrchestra](https://github.com/franknobox/AOrchestra-Agent), originally licensed under Apache 2.0. The original LICENSE file is preserved. Modifications and new code are copyright 2026 franknobox.

```
