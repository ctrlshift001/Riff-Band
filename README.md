# RiffBand

A lightweight agent engine purpose-built for research tasks, based on [AOrchestra](https://arxiv.org/abs/2602.03786). CLI-native and callable via MCP.

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

## Modes

RiffBand operates at two levels: **Normal Mode** for general agent tasks, and **Research Mode** for structured multi-step research pipelines.

### Normal Mode

General-purpose agent orchestration. Type any task in the CLI and the MainAgent plans, delegates to SubAgents, and synthesizes results. Supports single-agent (`/mode single`) and multi-agent (`/mode multi`) execution.

### Research Mode

A fixed-pipeline orchestrator built on top of the same agent runtime. It drives the agents through a predefined sequence of research steps with built-in quality gates, skill files, and structured artifact management.

Two sub-modes:

| Mode | Steps | Output | Use Case |
|------|-------|--------|----------|
| `academic` (default) | 9 steps | `paper.tex` + `references.bib` | Literature review |
| `visual` | 10 steps | `report_visual.html` | General research with visual report |

The pipeline owns step order, artifact paths, and quality gates. Agents are used as **executors** for each step rather than as the source of control flow.

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Configure
cp .env.example .env          # fill in LLM API key + Serper key
cp aorchestra.yaml.example aorchestra.yaml

# 3. Run interactive CLI
python shell.py --config aorchestra.yaml
```

## Configuration

| File | Purpose |
|------|---------|
| `.env` | API keys (LLM, Serper, proxy) |
| `aorchestra.yaml` | Agent strategy (mode, model, profile, limits) |

See `.env.example` and `aorchestra.yaml.example` for templates.

## CLI Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/mode <single\|multi\|auto>` | Switch execution mode |
| `/model <name>` | Switch LLM model |
| `/research <topic>` | Start research mode (default academic) |
| `/research <topic> --mode=visual --depth=deep --format=html` | Visual research with custom flags |
| `/setup` | Re-run onboarding wizard |
| `/status` | Show agent state |
| `/session` | Show session info |
| `/sessions` | List saved sessions |
| `/resume <id>` | Resume a previous session |
| `/clear` | Clear screen |
| `/exit` | Exit |

Research flags:
- `--mode=academic|visual` — Pipeline mode (default: academic)
- `--depth=quick|standard|deep` — Research depth (default: standard)
- `--format=markdown|latex|html|json` — Output format (academic defaults to latex, visual defaults to html)

## MCP Integration

RiffBand can be called by external agents (Claude Code, Codex, Gemini CLI) via MCP:

```json
{
  "mcpServers": {
    "riffband": {
      "command": "python",
      "args": ["mcp_server.py", "--config", "aorchestra.yaml"]
    }
  }
}
```

The MCP server exposes a single `research` tool:

```json
{
  "name": "research",
  "inputSchema": {
    "properties": {
      "topic": {},
      "mode": { "enum": ["academic", "visual"], "default": "academic" },
      "depth": { "enum": ["quick", "standard", "deep"], "default": "standard" },
      "output_format": { "enum": ["markdown", "latex", "html", "json"], "default": "latex" },
      "sources": {},
      "constraints": {}
    },
    "required": ["topic"]
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
  project/              # Project assembly, prompts, tools (shared by all modes)
  modes/                # Mode router (single / multi / auto)
  research/             # Research mode pipeline
    schema.py           # Request/result models, mode enum
    steps.py            # RESEARCH_STEPS (9) + VISUAL_STEPS (10)
    skills.py           # Skill registry with mode routing
    skills/             # Markdown skill files (prompts per step)
      *.md              # Academic mode skills (9 files, untouched)
      visual/           # Visual mode skills (10 files)
    pipeline.py         # Pipeline orchestrator
    gates.py            # Quality gates (per-step + final)
    prompts.py          # MainAgent/SubAgent prompt builders
    artifacts.py        # File layout, export (LaTeX, HTML, Visual HTML)
    runner.py           # Entry boundary (CLI + MCP)
  ui/                   # Interactive CLI + Rich renderer
  mcp_server.py         # MCP stdio server
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
```

## License

This project is based on [AOrchestra](https://github.com/franknobox/AOrchestra-Agent), originally licensed under Apache 2.0. The original LICENSE file is preserved. Modifications and new code are copyright 2026 franknobox.
