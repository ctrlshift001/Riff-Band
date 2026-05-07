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

## 当前重点

通过结构化工作流实现研究任务自动化，涵盖文献检索、多 Agent 假设辩论与报告生成。可通过内置 TUI shell 使用，也可作为 MCP tool 被外部 Agent 调用。

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置
cp .env.example .env          # 填入 LLM API key 和 Serper key
cp aorchestra.yaml.example aorchestra.yaml

# 3. 启动交互式shell
python shell.py --config aorchestra.yaml
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
| `/mode single|multi|auto` | 切换执行模式 |
| `/model name` | 切换 LLM 模型 |
| `/research topic` | 启动研究模式 |
| `/setup` | 重新运行配置向导 |
| `/status` | 查看 Agent 状态 |
| `/session` | 查看当前会话 |
| `/sessions` | 列出历史会话 |
| `/resume id` | 恢复历史会话 |
| `/clear` | 清屏 |
| `/exit` | 退出 |

## MCP 集成

RiffBand 可通过 MCP 被外部 Agent（Claude Code、Codex、Gemini CLI 等）调用：

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

## 项目结构

```
src/
  agents/               # MainAgent、SubAgent
  core/                 # Runner、消息协议、会话持久化
  environments/         # 任务执行环境
  orchestration_tools/  # 委派、完成、任务计划
  project/              # 项目组装、prompt、工具集
  modes/                # 模式路由器 (single / multi / auto)
  ui/                   # 交互式 shell + Rich 渲染器
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

## 许可协议

本项目基于 [AOrchestra](https://github.com/franknobox/AOrchestra-Agent) 开发，原始代码使用 Apache 2.0 许可。原始 LICENSE 文件已保留。修改及新增代码版权归 franknobox 所有。

```
