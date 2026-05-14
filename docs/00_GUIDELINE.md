# 操作指南

> 仅含操作步骤，不讲原理。面向初次运行本项目的开发者。

---

## 1. 环境要求

- Python 3.10+
- pip

## 2. 安装

```bash
pip install -r requirements.txt
```

## 3. 配置

```bash
cp .env.example .env
cp aorchestra.yaml.example aorchestra.yaml
```

### .env 必填项

```env
LLM_API_KEY=sk-xxx
SERPER_API_KEY=xxx
```

### aorchestra.yaml 示例

```yaml
main_model: gemini-2.5-flash
sub_models:
  - gemini-2.5-flash
  - deepseek-v4-pro
sources_dir: workspace/sources
workspace_dir: workspace
mode: auto
profile_name: generic
```

## 4. 启动

### 4.1 CLI 交互模式

```bash
# 首次：在项目目录安装为全局命令
pip install -e .

# 之后任何目录一行启动
riffband
```

进入 TUI 后：

```text
# 普通对话（单/多 Agent 自动路由）
帮我分析一下低空经济

# 切换执行模式
/mode single          # 单 Agent 模式
/mode multi           # 多 Agent 模式
/mode auto            # 自动选择

# 查看状态
/status
/session
```

### 4.2 研究模式

```bash
# 启动研究（默认 academic 模式）
/research 粤港澳大湾区低空经济发展现状

# 学术文献综述，LaTeX 输出（默认行为）
/research 通信感知一体化技术进展 --mode=academic --depth=deep --format=latex

# 通用研究 + 视觉 HTML 报告
/research 2026年AI行业趋势 --mode=visual --depth=deep --format=html

# 快速模式（适合测试）
/research 量子计算最新进展 --mode=academic --depth=quick
```

研究参数：

| 参数 | 值 | 默认 |
|------|-----|------|
| `--mode` | `academic` `visual` | `academic` |
| `--depth` | `quick` `standard` `deep` | `standard` |
| `--format` | `markdown` `latex` `html` `json` | academic: `latex`, visual: `html` |

## 5. MCP 模式（供外部 Agent 调用）

### 5.1 配置方式

在你的 MCP client 配置中加：

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

### 5.2 调用参数

```json
{
  "topic": "研究主题",
  "mode": "academic",
  "depth": "standard",
  "output_format": "latex",
  "sources": [],
  "constraints": ""
}
```

### 5.3 返回结果

```json
{
  "status": "done",
  "summary": "...",
  "report_path": "workspace/output/.../paper.tex",
  "artifacts": [...],
  "steps": [...],
  "open_issues": [...]
}
```

进度通知：研究执行期间，MCP server 会持续发送 `notifications/progress` 事件。

取消：调用 `cancel_research` tool 可中断正在运行的研究。

## 6. 运行测试

```bash
# 全量
pytest tests/

# 仅研究模块
pytest tests/test_research_visual.py -v

# 仅 MCP
pytest tests/test_mcp_server.py -v

# 按关键字
pytest tests/ -k "visual"
```

## 7. 产出物位置

### 普通模式

```
workspace/output/session_<id>/turn_<N>/
```

### 研究模式

```
workspace/
├── output/                          ← 只放最终报告
│   ├── 20260514_120000_topic_paper.tex
│   ├── 20260514_120000_topic_references.bib
│   ├── 20260514_120000_topic_report.html
│   └── 20260514_120000_topic_visual.html
└── research/20260514_120000_topic/  ← 内部工作文件
    ├── research_report.md
    ├── findings.jsonl
    ├── papers.jsonl / sources.jsonl
    ├── paper_notes.jsonl / material_notes.jsonl
    ├── claims.jsonl / insights.jsonl
    ├── debate_log.md / review_notes.md
    ├── outline.md
    ├── review_report.md
    ├── scratchpad/
    └── manifest.json
```

## 8. 常见问题

**Q: 跑 `/research` 只生成 scaffold 没有真实结果？**

A: 检查 `.env` 里 LLM API key 是否正确配置，以及 `aorchestra.yaml` 里的 `main_model` 是否可用。没有 LLM 时 pipeline 只生成空模板。

**Q: MCP server 连不上？**

A: 确认 `cwd` 路径正确指向 `src/`，且 `--config` 路径可解析。

**Q: 测试报 import 错误？**

A: 确认在项目根目录执行 `pytest`，且 `src/` 在 `sys.path` 中。
