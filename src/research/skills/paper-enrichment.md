# 论文轻量阅读与结构化抽取

在正式知识综合前，把检索到的论文元数据和摘要转成可写作的结构化阅读笔记。本阶段是轻量实现，不要求完整向量库。

## 阶段协议

步骤：`paper_enrichment`

目标：
- 从 `papers.jsonl` 中选择高相关论文，优先处理综述论文、高引用论文、核心方法论文和主题强相关论文。
- 基于摘要、网页正文、本地 PDF 或元数据抽取轻量 paper note。
- 为后续知识综合、观点生成和 LaTeX 写作提供比标题/摘要更稳定的材料。

输入：
- `papers.jsonl`、`findings.jsonl`、scratchpad 中的研究计划和检索记录。

推荐工具：
- `read_papers`：读取候选论文。
- `read_findings`：读取已有证据点，避免重复抽取。
- `web_fetch` / `read_url`：读取论文页面、arXiv 页面或 DOI 页面。
- `local_pdf_extract`：读取本地 PDF。
- `record_paper_note`：记录结构化阅读笔记。
- `record_finding`：把重要结论追加为证据点。
- `write_scratchpad_note`：记录覆盖情况和仍需全文阅读的论文。
- `write_report_section`：写入 `论文阅读笔记与结构化抽取`。

执行步骤：
1. 读取 `papers.jsonl`，按相关性、摘要可用性、年份、venue、citation_count 选择优先处理论文。
2. 对每篇优先论文，先使用已有 abstract；如果 source_url 可读，再用 `read_url` 或 `web_fetch` 补充。
3. 如果本地有 PDF，再用 `local_pdf_extract` 补充。
4. 对每篇处理过的论文调用 `record_paper_note`，字段至少包括：
   - problem
   - method
   - scenario
   - main_findings
   - limitations
   - relevance_to_topic
   - evidence_source
5. 若只能基于摘要抽取，`evidence_source` 必须为 `abstract`，不要声称已阅读全文。
6. 对影响综述主线的发现调用 `record_finding`。
7. 写入报告章节：`论文阅读笔记与结构化抽取`，说明已处理论文数量、证据深度和缺口。

必须产出：
- `paper_notes.jsonl` 中的结构化阅读笔记。
- 摘要级、网页级或 PDF 级证据来源标记。
- 仍需全文阅读或无法访问的论文清单。

质量门：
- 不得根据标题编造方法、实验或结论。
- 没有摘要/网页/PDF 支撑时，只能记录为 metadata/uncertain。
- 本阶段不进行最终综合，只为 Step 3 准备材料。
