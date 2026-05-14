# 文献检索

收集真实、可验证、可引用的论文候选和证据点，为最终生成 `paper.tex` 和 `references.bib` 服务。不得编造论文元数据。

## 阶段协议

步骤：`literature_search`

目标：
- 建立足够大的合格论文池，标准深度目标不少于 30 篇 `papers.jsonl` 记录，深度综述目标不少于 50 篇。
- 覆盖核心主题、相邻主题、综述论文、方法论文、应用论文和挑战/局限论文。
- 形成可供后续知识综合使用的证据表和来源缺口说明。

输入：
- scratchpad 中的研究线索、关键词、纳入/排除标准。
- 本地来源、用户指定来源和当前主题约束。

推荐工具：
- `arxiv_search`、`semantic_scholar_search`：主力学术检索工具。优先使用英文同义查询和缩写查询，例如 RIS、ISAC、reconfigurable intelligent surface、integrated sensing and communication。
- `crossref_lookup`、`dblp_lookup`：当 arXiv 或 Semantic Scholar 超时/429/结果不足时补充元数据。
- `web_search`、`web_fetch`、`read_url`：发现综述、期刊页面、PDF 页面和机构报告。
- `local_pdf_extract`：读取本地 PDF 材料。
- `record_paper`：每篇合格论文都要记录题名、作者、年份、venue、URL/DOI、摘要或相关性说明。
- `record_paper_note`：对高相关论文基于摘要、网页或 PDF 记录轻量结构化阅读笔记。
- `record_finding`：每条关键结论都要记录 source_url 或明确 evidence。
- `write_scratchpad_note`：记录检索覆盖、失败工具、替代查询和证据缺口。
- `write_report_section`：写入 `文献检索与证据表`。

执行步骤：
1. 先根据 Step 1 的关键词生成中英文查询组，至少覆盖核心组合、缩写组合和宽泛补充组合。
2. 对每个查询优先调用 `semantic_scholar_search(limit=20~50)` 和 `arxiv_search(max_results=20~50)`。
3. 如果某个工具超时、429 或连续失败，不要原样重试；改用更宽/更窄查询，或切换 `crossref_lookup`、`dblp_lookup`、`web_search`。
4. 对每篇合格论文调用 `record_paper`，避免只把论文留在工具返回结果里。
5. 对高相关论文调用 `record_paper_note`，至少抽取 problem、method、scenario、main_findings、limitations、relevance_to_topic 和 evidence_source；如果只读到摘要，必须把 evidence_source 标为 `abstract`。
6. 对关键发现调用 `record_finding`，并关联来源 URL。
7. 如果论文数量仍不足，继续用相邻关键词补充综述论文、方法论文和应用论文，并在 scratchpad 说明缺口。
8. 写入报告章节 `文献检索与证据表`，列出检索渠道、论文数量、主题覆盖和剩余缺口。

必须产出：
- `papers.jsonl` 中的合格论文记录，标准深度目标不少于 30 篇。
- `paper_notes.jsonl` 中至少若干篇高相关论文的轻量阅读笔记；如果工具限制导致无法补足，明确说明。
- 多条有来源支撑的 findings。
- 按研究线索分组的证据表。
- 工具失败、来源缺口和不确定性说明。

质量门：
- 不得编造引用、作者、年份、期刊、会议或链接。
- 论文池必须优先服务最终 `.tex` 文献综述和 `references.bib`。
- 若无法达到论文数量目标，返回 `partial` 并明确失败工具、已尝试查询和缺失来源类型。
