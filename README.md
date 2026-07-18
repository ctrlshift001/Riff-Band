# AI4MS / RiffBand

An AI research workbench vertically integrated for management science, from research ideas and literature to analysis, evidence, and delivery.

> The `ai4s` branch is transforming RiffBand into a complete single-user AI4MS workbench. The existing CLI, MCP server, agent runtime, research pipeline, and visual HTML report are the engineering foundation. The nine-step web workspace, persistent project state, approvals, method/data planning, Stata integration, evidence review, and delivery surfaces are under active implementation. Planned capabilities are not presented here as already shipped.

[中文](README.zh-CN.md) | [Documentation](docs/README.md) | [Product](docs/00_PRODUCT.md) | [Roadmap](docs/00_ROADMAP.md)

## Product Direction

AI4MS is not an automatic paper generator. It organizes the decisions, evidence, assumptions, revisions, approvals, and reproducibility records required to move from an early research idea to a defensible research output.

Its product shape can be understood as a lightweight, management-science vertical counterpart to Bohrium: literature, research workflow, method/data planning, scientific computing, and delivery live in one workbench, with deeper support for research design, Stata, evidence boundaries, and human decisions. This comparison describes product direction only; AI4MS is not affiliated with Bohrium and does not claim access to its non-public capabilities.

```text
Research idea
  -> 1. State the idea
  -> 2. Review existing research
  -> 3. Select a worthwhile topic
  -> 4. Confirm theory and research design
  -> 5. Confirm data and compliance
  -> 6. Prepare analysis plans and Stata code
  -> 7. Run, diagnose, and reproduce
  -> 8. Review evidence and interpretation
  -> 9. Write, approve, and deliver
```

All nine steps live in one project workbench. Each step exposes the current task, an AI draft, structured editing, supporting evidence or run artifacts, approve/return actions, and a clear handoff. Topic Scout supplies real multi-source retrieval, research landscapes, counter-search, and candidate topics; later workspaces continue through design, data, methods, code, diagnostics, Claim-Evidence review, and delivery.

The six-day competition build is a local single-user web product backed by SQLite and file artifacts. Every step has a real code path; organization login, multi-party approval, and cloud compute are deployment enhancements rather than substitutes for the product workflow.

## Human-in-the-Loop Research

The target workflow uses ten stages (S0-S9) and six human gates (G0-G5). Agents create drafts, patches, issues, and recommendations; they cannot approve their own work.

Editable assets use immutable revisions. Approvals bind a specific revision and SHA-256 hash. Material upstream changes invalidate affected downstream approvals without deleting the historical decision record.

## Cross-Disciplinary Design

AI4MS starts with management science while keeping the research kernel domain-neutral. Research Protocol, DomainProfile, method registries, and gate registries support empirical and causal research, analytical and optimization models, predictive and computational work, behavioral and qualitative studies, and evidence synthesis or design science.

Domain-specific behavior belongs in profiles and registries rather than hard-coded topic terms, allowing the same infrastructure to expand into additional scientific disciplines.

## Visual HTML Reports

RiffBand already exports standalone visual HTML reports with responsive layout, navigation, tables, and ECharts visualizations. AI4MS retains this capability as a first-class product surface for research landscapes, evidence tables, candidate gaps, counter-search results, feasibility, decisions, and audit history.

## Engineering Foundation

RiffBand builds on [AOrchestra: Automating Sub-Agent Creation for Agentic Orchestration](https://arxiv.org/abs/2602.03786), which models a dynamically created agent as:

```text
<Instruction, Context, Tools, Model>
```

RiffBand extends that foundation with fixed research pipelines, tool scoping, parallel delegation, CLI/MCP entry points, structured artifacts, and HTML reporting. AI4MS reuses this runtime while replacing topic-specific research logic with protocol-driven domain services.

## Current Compatibility Entry Points

```powershell
pip install -e .
Copy-Item .env.example .env
Copy-Item aorchestra.yaml.example aorchestra.yaml
riffband
```

Current research commands remain available during migration:

```text
/research AI adoption and firm innovation --depth=deep
/research low-carbon logistics optimization --mode=visual --depth=deep --format=html
```

These CLI/MCP parameters are compatibility interfaces, not the final AI4MS information architecture.

## Competition Delivery

The competition build will be delivered as a Dockerized web product with a browser GUI. One container exposes:

- `/` for the nine-step management-science workbench;
- `/api/v1` for remote invocation;
- `/docs` for OpenAPI documentation;
- `/healthz` for deployment health checks.

SQLite, project artifacts, and HTML reports persist through a Docker volume. Model and search credentials are injected at runtime. Stata remains an external bring-your-own-license runner and is never bundled into the image.

## Documentation

- [Documentation index and source-of-truth policy](docs/README.md)
- [AI4MS product definition](docs/00_PRODUCT.md)
- [AI4MS roadmap](docs/00_ROADMAP.md)
- [Development guide](docs/00_GUIDELINE.md)
- [Contribution workflow](docs/00_WORKFLOW.md)
- [AI4MS DevPack v0.3](docs/refer/AI4MS-DevPack_v0.3/README.md)
- [Engineering baseline](docs/ai4ms/BASELINE.md)

## Product Boundaries

- No claims of guaranteed originality.
- No fabricated papers, identifiers, data, estimates, experiments, or reviews.
- No bypassing paywalls, copyright, data licenses, privacy controls, or software licenses.
- No automatic conversion of correlation, significance, or model complexity into causality or contribution.
- No agent self-approval at topic, design, data, analysis, claim, or release gates.
- No hiding failed diagnostics, negative results, or counter-evidence in generated writing.

## License and Citation

The original Apache 2.0 `LICENSE` is preserved. When using the orchestration foundation, cite:

```bibtex
@misc{ruan2026aorchestra,
  title={AOrchestra: Automating Sub-Agent Creation for Agentic Orchestration},
  author={Jianhao Ruan and Zhihao Xu and Yiran Peng and Fashen Ren and
          Zhaoyang Yu and Xinbing Liang and Jinyu Xiang and Yongru Chen and
          Bang Liu and Chenglin Wu and Yuyu Luo and Jiayi Zhang},
  year={2026},
  eprint={2602.03786},
  archivePrefix={arXiv},
  primaryClass={cs.AI},
  url={https://arxiv.org/abs/2602.03786}
}
```
