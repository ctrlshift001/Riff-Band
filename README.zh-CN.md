# AOrchestra

一个基于 [AOrchestra](https://arxiv.org/abs/2602.03786) 论文构建的通用多智能体系统，支持三种运行模式。

## 核心概念

系统将子 Agent 抽象为可配置的四元组 `(I, C, T, M)`：

| | | |
|---|---|---|
| **I** | Instruction | 子 Agent 的任务指令 |
| **C** | Context | 背景信息与约束 |
| **T** | Tools | 子 Agent 可用的工具集 |
| **M** | Model | 分配给子 Agent 的 LLM |

主编排 Agent 根据任务动态创建不同 `(I, C, T, M)` 组合的子 Agent，协调执行并合并结果。

> 原论文与 benchmark 代码保留在 `aorchestra/` 目录中。如需了解论文细节和评测体系，详见[论文原仓库](https://github.com/franknobox/AOrchestra-Agent)。

## 三种模式

### 1. `single` — 单 Agent 模式

面向轻量、直接的日常任务。一个 Agent 直接执行，不启动编排器。

适合：
- 日常问答与总结
- 简单搜索与文件处理
- 低成本、低延迟场景

### 2. `multi` — 多 Agent 模式

面向复杂、可拆分的任务。主编排 Agent 动态合成子 Agent，为每个子 Agent 分配不同的指令、上下文、工具和模型，支持并行执行并合并结果。

适合：
- 多步骤调研与分析
- 需要多工具协作的任务
- 需要并行化的证据收集与报告生成

### 3. `auto` — 自动路由模式

系统根据任务文本自动判断复杂度，选择合适的模式：
- 短文本、简单任务 → `single`
- 多步骤、需要证据/报告/并行 → `multi`

决策分三层：硬规则（关键词匹配）→ LLM 辅助（模糊任务）→ 软规则（综合评分）。

## 当前重点

产业研究是本仓库第一个重点优化的场景，尤其是：

- 政策研究
- 公司研究
- 产业链分析
- 新闻与信号收集
- 结构化报告生成

这些任务天然可拆分、多信息源、需要证据链，非常适合验证动态多 Agent 编排能力。但这不意味着系统仅限于产业研究——它是第一个深度打磨的 profile，系统设计本身是通用的。

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
| `/mode <single\|multi\|auto>` | 切换执行模式 |
| `/model <name>` | 切换 LLM 模型 |
| `/status` | 查看 Agent 状态 |
| `/session` | 查看当前会话 |
| `/sessions` | 列出历史会话 |
| `/resume <id>` | 恢复历史会话 |
| `/clear` | 清屏 |
| `/exit` | 退出 |

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
aorchestra/             # 原论文与 benchmark（历史保留）
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
