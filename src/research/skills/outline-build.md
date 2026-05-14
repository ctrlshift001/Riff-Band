# 结构化论文大纲构建

将已批准的观点、证据和文献池转换为面向 LaTeX 文献综述的论文大纲。

## 阶段协议

步骤：`outline_build`

目标：
- 生成一篇文献综述论文的结构化大纲，而不是普通任务报告大纲。
- 将主要观点映射到证据、论文来源和计划引用。

输入：
- 已排序观点、辩论决策、findings、papers 和综合笔记。

推荐工具：
- `read_research_claims`、`read_findings`、`read_papers`、`read_claim_debate_log`、`read_scratchpad`：构建大纲前读取材料。
- `build_research_outline`：写入结构化大纲和观点-证据映射。
- `write_report_section`：写入本步骤报告章节。

执行步骤：
1. 读取已排序观点、证据和文献池。
2. 构建论文式章节：Abstract、Introduction、Background、Related Work、Literature Synthesis、Research Gaps、Future Directions、Conclusion。
3. 为每个章节列出需要使用的 papers/findings/claims。
4. 为主要论断附上 source_url 或计划 citation key。
5. 列出会影响最终 `paper.tex` 质量的缺失材料。
6. 写入报告章节：`结构化论文大纲`，并调用 `build_research_outline` 写入 `outline.md`。

必须产出：
- 层级化论文大纲。
- 观点-证据-引用映射。
- 缺失材料列表。
- `outline.md` 大纲产物。

质量门：
- 主要章节都应有证据或计划引用支撑。
- 本步骤不撰写最终正文。
