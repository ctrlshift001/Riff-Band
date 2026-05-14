# Design: Research Dual-Mode (Academic + Visual)

**Date:** 2026-05-14
**Status:** Draft — pending review

---

## 1. 背景与目标

当前 RiffBand 的研究流程是单一的学术文献综述模式（9-step fixed pipeline）。

本设计目标：在保持队友现有 academic 模式完全不受影响的前提下，新增 **visual** 子模式，支持通用研究+视觉报告生成。两种模式共享统一的编排骨架，但拥有独立的 steps、skills、gates、prompts 和产物模板。

---

## 2. 对外接口

### 2.1 MCP Tool Schema

```json
{
  "name": "research",
  "inputSchema": {
    "type": "object",
    "properties": {
      "topic": {"type": "string"},
      "mode": {"type": "string", "enum": ["academic", "visual"], "default": "academic"},
      "depth": {"type": "string", "enum": ["quick", "standard", "deep"], "default": "standard"},
      "output_format": {"type": "string", "enum": ["markdown", "latex", "html", "json"], "default": "latex"},
      "sources": {"type": "array", "items": {"type": "string"}, "default": []},
      "constraints": {"type": "string", "default": ""}
    },
    "required": ["topic"]
  }
}
```

- `mode` 决定内部流程和 skill 集合
- `output_format` 决定最终导出格式
- `academic` 默认 `output_format="latex"`，`visual` 默认 `output_format="html"`

### 2.2 CLI 用法

```bash
/research <topic> --mode=visual --depth=deep
```

不传 `--mode` 时默认 `academic`，完全兼容现有行为。

---

## 3. Steps 注册表

### 3.1 Academic Steps（现有，完全不动）

| # | Key | Title | Skill |
|---|-----|-------|-------|
| 1 | `decompose_topic` | Topic Decomposition | `decompose-topic` |
| 2 | `literature_search` | Literature Search | `literature-search` |
| 3 | `paper_enrichment` | Paper Enrichment | `paper-enrichment` |
| 4 | `knowledge_synthesis` | Knowledge Synthesis | `knowledge-synthesis` |
| 5 | `claim_generation` | Claim Generation | `claim-generation` |
| 6 | `claim_debate` | Claim Debate | `claim-debate` |
| 7 | `outline_build` | Outline Build | `outline-build` |
| 8 | `section_draft` | Section Draft | `section-draft` |
| 9 | `multi_agent_review` | Multi-Agent Review | `multi-agent-review` |

### 3.2 Visual Steps（新增）

| # | Key | Title | Skill | 说明 |
|---|-----|-------|-------|------|
| 1 | `decompose_topic` | Topic Decomposition | `decompose-topic` | 通用化表述，不限学术范围 |
| 2 | `information_search` | Information Search | `information-search` | 支持网页/新闻/社交媒体/本地资料 |
| 3 | `material_reading` | Material Reading | `material-reading` | 阅读并结构化抽取查到的文章/资料 |
| 4 | `knowledge_synthesis` | Knowledge Synthesis | `knowledge-synthesis` | 基于 findings + material notes 聚类 |
| 5 | `insight_generation` | Insight Generation | `insight-generation` | 生成洞察、结论、趋势判断 |
| 6 | `insight_review` | Insight Review | `insight-review` | 压力测试洞察的证据覆盖和逻辑 |
| 7 | `outline_build` | Outline Build | `outline-build` | 报告式章节结构 |
| 8 | `section_draft` | Section Draft | `section-draft` | 通用报告正文 |
| 9 | `visual_design` | Visual Design | `visual-design` | **新增**：图表生成、HTML 美化、响应式排版 |
| 10 | `quality_review` | Quality Review | `quality-review` | 最终质量检查 |

**关键差异：**
- visual 有 10 步（比 academic 多 1 步：`visual_design`）
- `paper_enrichment` 改名为 `material_reading`，通用化（不限学术论文，支持博客/新闻/报告等）
- `claim_generation` → `insight_generation`，`claim_debate` → `insight_review`，去除学术术语
- `multi_agent_review` → `quality_review`
- 检索步骤从 `literature_search` → `information_search`，扩大信息源范围

---

## 4. Skills 目录隔离（核心原则：只做加法，不移动现有文件）

**核心隔离原则**：队友现有的 9 个 skill 文件**完全不动**（不移动、不删除、不重命名），只新增 `visual/` 子目录。

```
src/research/skills/
├── claim-debate.md        ← 队友现有文件，完全不动
├── claim-generation.md    ← 完全不动
├── decompose-topic.md     ← 完全不动
├── knowledge-synthesis.md ← 完全不动
├── literature-search.md   ← 完全不动
├── multi-agent-review.md  ← 完全不动
├── outline-build.md       ← 完全不动
├── paper-enrichment.md    ← 完全不动
├── section-draft.md       ← 完全不动
└── visual/                ← 只新增这个目录
    ├── decompose-topic.md
    ├── information-search.md
    ├── material-reading.md
    ├── knowledge-synthesis.md
    ├── insight-generation.md
    ├── insight-review.md
    ├── outline-build.md
    ├── section-draft.md
    ├── visual-design.md
    └── quality-review.md
```

`ResearchSkillRegistry` 修改（向后兼容）：

```python
class ResearchSkillRegistry:
    def __init__(self, mode: str = "academic"):
        if mode == "visual":
            self.skills_dir = SKILLS_DIR / "visual"
        else:
            self.skills_dir = SKILLS_DIR  # 保持现有路径，队友文件不受影响
```

**结果**：队友的 skill 文件路径完全不变，她的任何开发和合并都不会受影响。

---

## 5. Gates 按 mode 分支

`ResearchGatekeeper` 构造函数加 `mode` 参数，内部 `check_step` 和 `check_final` 按 mode 分支检查。

### 5.1 `check_step` 差异

| Step | Academic Gate | Visual Gate |
|------|--------------|-------------|
| `literature_search` / `information_search` | `min_papers=30`, 检查 `papers.jsonl` | `min_sources=15`, 检查 `sources.jsonl` |
| `paper_enrichment` / `material_reading` | 检查 `paper_notes.jsonl` | 检查 `material_notes.jsonl` |
| `knowledge_synthesis` | 要求 `findings.jsonl` + `paper_notes.jsonl` | 要求 `findings.jsonl` + `material_notes.jsonl` |
| `claim_generation` / `insight_generation` | 检查 `claims.jsonl` | 检查 `insights.jsonl` |
| `claim_debate` / `insight_review` | 检查 `claims.jsonl` + `debate_log.md` | 检查 `insights.jsonl` + `review_notes.md` |
| `section_draft` | 检查 `outline.md` + `references.bib` | 检查 `outline.md` |
| `visual_design` | N/A | 检查 HTML 产物存在且含图表标记 |

### 5.2 `check_final` 差异

| 检查项 | Academic | Visual |
|--------|----------|--------|
| 报告文件 | `research_report.md` 非空 | `research_report.md` 非空 |
| 格式产物 | `paper.tex` + `references.bib` | `report_visual.html` 存在 |
| 必要章节 | 8 个学术章节 | 9 个通用章节（含视觉设计） |
| 引用检查 | `\cite{}` 或 `\url{}` | `https?://` 显式链接 |
| 图表检查 | N/A | HTML 中含 `data-chart` 或 `data-table` 标记 |
| findings 数量 | `min_findings` | `min_findings` |
| papers/sources 数量 | `min_papers` | `min_sources` |

---

## 6. Prompts 条件渲染

现有 `ResearchMainPromptBuilder` / `ResearchSubPromptBuilder`：

- 构造函数加 `mode` 参数
- Prompt 模板中用条件渲染区分学术变量和通用变量
- 不拆新类，避免重复代码

**关键差异：**
- Academic prompt 提及 `papers.jsonl`、`paper_notes.jsonl`、`references.bib`、LaTeX 语法
- Visual prompt 提及 `sources.jsonl`、`material_notes.jsonl`、`report_visual.html`、HTML/CSS/图表标记语法

---

## 7. Artifacts 产物系统

### 7.1 新增产物路径

```python
@dataclass(frozen=True)
class ResearchArtifacts:
    # ... 现有路径不变 ...
    # Visual 模式新增
    report_visual_html: Path      # 最终视觉报告
    sources: Path                 # 通用信息源记录（替代 papers.jsonl 的语义）
    material_notes: Path          # 材料阅读笔记（替代 paper_notes.jsonl）
    insights: Path                # 洞察记录（替代 claims.jsonl）
    review_notes: Path            # 洞察审校笔记（替代 debate_log.md）
```

### 7.2 `to_artifacts` 方法

```python
def to_artifacts(self, output_format: str, mode: str) -> list[ResearchArtifact]:
    items = [...]  # 基础产物
    if mode == "academic" and output_format == "latex":
        items.insert(0, ResearchArtifact(type="latex", path=str(self.paper_tex)))
        items.insert(1, ResearchArtifact(type="bibtex", path=str(self.references_bib)))
    elif mode == "visual" and output_format == "html":
        items.insert(0, ResearchArtifact(type="html", path=str(self.report_visual_html)))
    return items
```

### 7.3 `export_visual_html` 升级

当前 `export_html` 是极简 Markdown→HTML 转换。visual 模式下升级为**视觉报告模板**：

```python
def export_visual_html(
    markdown_path: Path,
    html_path: Path,
    title: str,
    artifacts: ResearchArtifacts,
) -> None:
    """
    1. 解析 markdown 中的特殊标记：
       ![chart](data:bar|...JSON...) → 渲染为 ECharts
       ![table](data:...JSON...) → 渲染为 styled HTML table
    2. 生成响应式单页 HTML，含：
       - 固定导航栏（TOC）
       - 卡片式章节布局
       - 渐变色 header
       - 暗/亮模式切换
    3. 内嵌 CSS + ECharts CDN（或内联JS）
    """
```

---

## 8. Pipeline 骨架变更

```python
class ResearchPipeline:
    def __init__(
        self,
        request: ResearchRequest,
        config: AgentConfig,
        options: ResearchPipelineOptions | None = None,
        progress_callback: Callable[[str], None] | None = None,
    ):
        self.request = request
        self.config = config
        self.mode = str(request.mode or "academic").strip().lower()
        self.options = options or ResearchPipelineOptions()
        self.progress_callback = progress_callback
        self.artifacts = ResearchArtifacts.create(
            config.workspace_dir.resolve(), request, mode=self.mode
        )
        self.skills = ResearchSkillRegistry(mode=self.mode)
        self.gates = ResearchGatekeeper(self.artifacts, mode=self.mode)
        self.step_results: list[ResearchStepResult] = []

    def _resolve_steps(self) -> tuple[ResearchStep, ...]:
        if self.mode == "visual":
            return VISUAL_STEPS
        return ACADEMIC_STEPS

    async def run(self) -> ResearchResult:
        steps = self._resolve_steps()
        # ... 其余 run loop 不变，只改 steps 来源 ...
```

**关键原则：** `run()` 主循环骨架不变，只改步骤来源和 gate/skills 初始化。

---

## 9. 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/research/schema.py` | 修改 | `ResearchRequest` 新增 `mode` 字段 |
| `src/research/steps.py` | 修改 | `RESEARCH_STEPS` 保留不动，新增 `VISUAL_STEPS` |
| `src/research/skills.py` | 修改 | `ResearchSkillRegistry` 构造函数加 `mode`（默认 academic，路径不变） |
| `src/research/skills/*.md` (现有 9 个) | 不动 | 队友文件，路径和内容完全保留 |
| `src/research/skills/visual/` | 新建目录 | 新增 10 个 visual skill |
| `src/research/pipeline.py` | 修改 | 按 `mode` 选择 steps/skills/gates/artifacts |
| `src/research/gates.py` | 修改 | `ResearchGatekeeper` 加 `mode` 参数，内部分支 |
| `src/research/prompts.py` | 修改 | `ResearchMain/SubPromptBuilder` 加 `mode` 条件渲染 |
| `src/research/artifacts.py` | 修改 | 新增 visual 产物路径，`export_visual_html` |
| `src/research/runner.py` | 修改 | `run_research` 透传 `mode` |
| `src/mcp_server.py` | 修改 | tool schema 新增 `mode` |
| `src/ui/shell.py` | 修改 | `/research` 命令支持 `--mode` |
| `tests/` | 新增 | 补充 visual mode 的测试用例 |

---

## 10. 兼容性保证

| 层面 | 保证 |
|------|------|
| 默认行为 | `mode` 默认 `"academic"`，现有调用完全兼容 |
| Academic 代码 | steps、gates、skills、prompts 零修改（现有 skill 文件完全不动，不移动、不删除、不重命名） |
| 产物路径 | academic 产物路径不变；visual 产物在独立 run_dir 中 |
| MCP schema | 新增可选字段 `mode`，不破坏现有 client |
| 测试 | 现有 46 个测试全部保留，新增 visual mode 测试 |

---

## 11. 待办

- [ ] 实现 `mode` 字段透传（schema → pipeline → gates/skills/prompts/artifacts）
- [ ] 编写 10 个 visual skill MD 文件
- [ ] 升级 `export_html` 为 `export_visual_html`
- [ ] 补充 visual mode 单元测试
- [ ] 端到端验证：CLI `/research --mode=visual` 和 MCP `mode=visual`
