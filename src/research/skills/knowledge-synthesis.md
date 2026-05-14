# 知识综合

将收集到的证据转化为主题、共识、争议和研究空白。

## 阶段协议

步骤：`knowledge_synthesis`

目标：
- 将 findings 和 papers 聚类成研究图景。
- 区分共识、争议、方法限制和开放问题。
- 为后续观点生成准备有证据支撑的材料。

输入：
- `findings.jsonl`、`papers.jsonl`、`paper_notes.jsonl` 和前序 scratchpad 笔记。

推荐工具：
- `read_findings`、`read_papers`：读取结构化证据和文献记录。
- `read_paper_notes`：读取轻量论文阅读笔记，优先使用其中的 problem、method、main_findings、limitations。
- `read_scratchpad`：读取课题拆解和检索笔记。
- `synthesize_findings`：保存主题、共识、争议、空白和证据质量说明。
- `write_scratchpad_note`：记录可复用的综合笔记。
- `write_report_section`：写入本步骤报告章节。

执行步骤：
1. 读取已记录的 findings、papers 和 paper_notes。
2. 优先基于 paper_notes 聚类；如果 paper_notes 不足，再退回摘要和 findings。
3. 按方法、理论、应用场景、证据类型和局限性聚类。
4. 识别共识、争议、矛盾和缺失证据。
5. 评估来源强度和证据质量。
6. 使用 `synthesize_findings` 固化综合结果。
7. 写入报告章节：`知识综合与研究空白`。

必须产出：
- 3-6 个综合主题。
- 共识与争议对照。
- 带证据依据的研究空白分析。
- 证据质量说明。

质量门：
- 每个研究空白都必须回指到 papers/findings，或明确说明证据不足。
- 本步骤不要生成最终观点，只为下一步准备材料。

人工检查点：
- 对高风险研究建议启用。如果综合结果出现多条互斥方向，应在 `open_issues` 中标出需要人工选择的方向。
