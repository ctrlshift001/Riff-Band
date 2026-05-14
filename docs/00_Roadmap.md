# Roadmap / 路线图

> 双语 | Bilingual · Last updated 2026-05-14

---

## 架构概览 Architecture Overview

RiffBand 当前有两条执行链路：

```
用户输入
├── CLI 任意文本 ──→ [普通模式] MainAgent/SubAgent 自由编排
│                        ├── /mode=single → build_single_agent_project
│                        └── /mode=multi  → build_agent_project
│
├── CLI /research   ──→ [研究模式] ResearchPipeline 固定状态机
│                        ├── mode=academic → RESEARCH_STEPS (9 步) → paper.tex
│                        └── mode=visual   → VISUAL_STEPS (10 步) → report_visual.html
│
└── MCP "research" tool ──→ 同上 ResearchPipeline（对外唯一接口）
```

普通模式是通用 Agent 对话。研究模式是**基于同一套 Agent 运行时的上层编排器**：Pipeline 按固定步骤表依次委派任务给 Agent，每步由 gates 检查质量，最后导出格式化产物。

---

## 已完成 Done

- [x] **Core Agent 运行时** — MainAgent/SubAgent，单/多 Agent 模式路由，会话持久化
- [x] **CLI Shell** — 基于 Rich 的交互式 TUI，slash 命令系统
- [x] **MCP Server** — JSON-RPC stdio 协议，`research` tool 可被外部 Agent 调用
- [x] **Research Mode v1 (academic)** — 9 步文献综述流水线：分解 → 检索 → 精读 → 综合 → 观点生成 → 辩论 → 大纲 → 草稿 → 多视角审校，产出 `paper.tex` + `references.bib`
- [x] **Research Mode v2 (visual)** — 10 步通用研究流水线：在 academic 基础上新增 `visual_design` 步骤，去除学术术语，支持图表标记（ECharts），产出响应式 HTML 视觉报告（暗/亮主题切换、TOC 导航、卡片布局）
- [x] **技能目录隔离** — `skills/visual/` 独立子目录，队友 9 个 academic skill 文件完全不受影响
- [x] **双模式 Gates/Prompts/Artifacts** — 门禁、提示词、产物系统均按 mode 分支，默认 100% 向后兼容
- [x] **测试** — 63 个单元测试全部通过，覆盖 academic/visual 双模式核心路径

---

## 进行中 In Progress

- [ ] **端到端验证** — CLI `/research --mode=visual` 完整流程 + MCP `mode=visual` 调用

---

## 计划中 Planned

### 短期 Short-term

- [ ] **Material reading skill 完善** — visual 模式 `material-reading` skill 目前为占位模板，需补齐为可用的阅读+抽取指令
- [ ] **Visual design skill 完善** — `visual-design` skill 需写入图表生成、HTML 排版的详细指引
- [ ] **Visual mode 产物工具扩展** — 增加 `record_source`、`record_insight` 等 visual 专用工具（当前复用 academic 工具）
- [ ] **Shell `/research` 自动补全** — tab 补全 mode/depth/format 参数
- [ ] **MCP 双向通信** — 研究进度实时推送给 MCP client（当前为一次性返回结果）

### 中期 Mid-term

- [ ] **Research 覆盖范围扩展** — 新增 mode=`market` 市场调研、mode=`policy` 政策分析等子模式
- [ ] **Pipeline 可观测性** — 步骤级耗时统计、失败重试策略、partially-run 产物恢复
- [ ] **多格式导出** — visual 模式下同时导出 `report_visual.html` + 独立 SVG/PNG 图表
- [ ] **跨 session 知识复用** — 同一 topic 多次 research 的 findings/papers 增量积累，避免重复检索

### 远期 Long-term

- [ ] **自定义 Step 注册表** — 用户可通过 YAML 配置自定义研究流水线步骤
- [ ] **Agent 多模态** — Pipeline 步骤支持图片生成、音频转录、视频分析
- [ ] **分布式 pipeline** — 多台机器并行执行不同 research step
