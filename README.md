# RiffBand

A lightweight agent engine purpose-built for research tasks, based on [AOrchestra](https://arxiv.org/abs/2602.03786). TUI-native and callable via MCP.

## Core Concept

The system models a sub-agent as a configurable four-tuple `(I, C, T, M)`:

| | | |
|---|---|---|
| **I** | Instruction | What the sub-agent should do |
| **C** | Context | Background information and constraints |
| **T** | Tools | The action space available to the sub-agent |
| **M** | Model | The LLM assigned to this sub-agent |

A main orchestrator agent dynamically creates sub-agents with different `(I, C, T, M)` combinations, coordinating their execution and merging results.

> Based on [AOrchestra](https://arxiv.org/abs/2602.03786). Original paper code available in the [fork](https://github.com/franknobox/AOrchestra-Agent).

## Current Focus

Research task automation via a structured workflow of literature search, multi-agent hypothesis debate, and report generation. Accessible through the built-in TUI shell or as an MCP tool callable by external agents.

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
| `/research <topic>` | Start research mode |
| `/setup` | Re-run onboarding wizard |
| `/status` | Show agent state |
| `/session` | Show session info |
| `/sessions` | List saved sessions |
| `/resume <id>` | Resume a previous session |
| `/clear` | Clear screen |
| `/exit` | Exit |

## MCP Integration

RiffBand can be called by external agents (Claude Code, Codex, Gemini CLI) via MCP:

```json
{
  "mcpServers": {
    "riffband": {
      "command": "python",
      "args": ["-m", "riffband.mcp"]
    }
  }
}
```

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
