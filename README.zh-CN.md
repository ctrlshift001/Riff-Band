# RiffBand

一个为研究任务而生的轻量级 Agent 引擎，基于 [AOrchestra](https://arxiv.org/abs/2602.03786)。支持 TUI 交互与被 MCP 调用。

## 核心概念

系统将子 Agent 抽象为可配置的四元组 `(I, C, T, M)`：

| | | |
|---|---|---|
| **I** | Instruction | 子 Agent 的任务指令 |
| **C** | Context | 背景信息与约束 |
| **T** | Tools | 子 Agent 可用的工具集 |
| **M** | Model | 分配给子 Agent 的 LLM |

主编排 Agent 根据任务动态创建不同 `(I, C, T, M)` 组合的子 Agent，协调执行并合并结果。

> 基于 [AOrchestra](https://arxiv.org/abs/2602.03786)。原论文代码详见 [fork 仓库](https://github.com/franknobox/AOrchestra-Agent)。

## 模式体系

RiffBand 在两个层级运行：**普通模式**用于通用 Agent 任务，**研究模式**用于结构化多步研究流水线。

### 普通模式

通用的 Agent 编排。CLI 中输入任意任务，MainAgent 负责规划、委派 SubAgent、合并结果。支持单 Agent（`/mode single`）和多 Agent（`/mode multi`）执行。

### 研究模式

基于同一套 Agent 运行时的**固定流水线编排器**。按预设步骤序列驱动 Agent，内置质量门禁、技能文件和结构化产物管理。

两种子模式：

| 模式 | 步骤数 | 输出 | 适用场景 |
|------|--------|------|----------|
| `academic`（默认） | 9 步 | `paper.tex` + `references.bib` | 文献综述 |
| `visual` | 10 步 | `report_visual.html` | 通用研究 + 视觉报告 |

流水线掌管步骤顺序、产物路径和质量门禁，Agent 是每步的**执行者**而非控制流来源。

## 快速开始

```bash
# 1. 安装 + 一次性配置
pip install -e .
cp .env.example .env          # 填入 LLM API key 和 Serper key
cp aorchestra.yaml.example aorchestra.yaml

# 2. 任何目录一行启动
riffband
```

## 配置

| 文件 | 用途 |
|------|------|
| `.env` | API key（LLM、Serper、代理） |
| `aorchestra.yaml` | Agent 策略（模式、模型、profile、限制） |

模板见 `.env.example` 和 `aorchestra.yaml.example`。

## Shell 命令

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/mode single\|multi\|auto` | 切换执行模式 |
| `/model name` | 切换 LLM 模型 |
| `/research topic` | 启动研究模式（默认 academic） |
| `/research topic --mode=visual --depth=deep --format=html` | 可视化研究，自定义参数 |
| `/setup` | 重新运行配置向导 |
| `/status` | 查看 Agent 状态 |
| `/session` | 查看当前会话 |
| `/sessions` | 列出历史会话 |
| `/resume id` | 恢复历史会话 |
| `/clear` | 清屏 |
| `/exit` | 退出 |

Research 参数：
- `--mode=academic|visual` — 流水线模式（默认 academic）
- `--depth=quick|standard|deep` — 研究深度（默认 standard）
- `--format=markdown|latex|html|json` — 输出格式（academic 默认 latex，visual 默认 html）

## MCP 集成

RiffBand 可通过 MCP 被外部 Agent（Claude Code、Codex、Gemini CLI 等）调用：

```json
{
  "mcpServers": {
    "riffband": {
      "command": "riffband-mcp",
      "args": ["--config", "aorchestra.yaml"],
      "cwd": "/path/to/Riff-Band"
    }
  }
}
```

MCP server 暴露单个 `research` tool：

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

## 项目结构

```
src/
  agents/               # MainAgent、SubAgent
  core/                 # Runner、消息协议、会话持久化
  environments/         # 任务执行环境
  orchestration_tools/  # 委派、完成、任务计划
  project/              # 项目组装、prompt、工具集（所有模式共用）
  modes/                # 模式路由器 (single / multi / auto)
  research/             # 研究模式流水线
    schema.py           # 请求/结果模型、mode 枚举
    steps.py            # RESEARCH_STEPS (9 步) + VISUAL_STEPS (10 步)
    skills.py           # 技能注册表，按 mode 路由
    skills/             # Markdown 技能文件（每步的 prompt）
      *.md              # Academic 模式技能（9 个文件，完全不动）
      visual/           # Visual 模式技能（10 个文件）
    pipeline.py         # 流水线编排器
    gates.py            # 质量门禁（单步 + 最终）
    prompts.py          # MainAgent/SubAgent prompt 构建器
    artifacts.py        # 文件布局、导出（LaTeX、HTML、可视化 HTML）
    runner.py           # 入口边界（CLI + MCP 共用）
  ui/                   # 交互式 shell + Rich 渲染器
  mcp_server.py         # MCP stdio 服务器
pyproject.toml          # 包元数据 + 入口命令
```

## 引用

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

## 许可协议

本项目基于 [AOrchestra](https://github.com/franknobox/AOrchestra-Agent) 开发，原始代码使用 Apache 2.0 许可。原始 LICENSE 文件已保留。修改及新增代码版权归 franknobox 所有。
