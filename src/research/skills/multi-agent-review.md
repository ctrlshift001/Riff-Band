# 多智能体审稿

独立审计最终研究输出。

## 阶段协议

步骤：`multi_agent_review`

目标：
- 审查证据质量、逻辑、新颖性、完整性、表达清晰度和引用真实性。
- 产出具体修复建议和最终建议。

输入：
- 最终报告正文、findings、papers、claims、大纲、辩论记录、scratchpad 和导出的参考文献。

推荐工具：
- `citation_audit`：检查引用和必需章节。
- `review_research_report`：生成证据、观点和完整性审查产物。
- `read_findings`、`read_papers`、`read_research_claims`、`read_scratchpad`：读取审查上下文。
- `novelty_check`：检查看起来证据不足或过度声称的观点。
- `write_report_section`：写入本步骤报告章节。

执行步骤：
1. 读取报告和结构化产物。
2. 审计必需章节、引用 URL、findings 覆盖和观点证据。
3. 从证据、逻辑、新颖性、完整性、清晰度和局限性等角度审查。
4. 按严重程度分类问题。
5. 使用 `review_research_report` 写入审查产物。
6. 写入报告章节：`多视角审稿意见`。

必须产出：
- 按严重程度分组的审查发现。
- 引用和证据问题。
- 最终建议：accept、revise 或 blocked。

质量门：
- `accept` 要求没有阻塞性的引用、章节或证据问题。
- `revise` 必须包含具体修复项。
- `blocked` 必须解释阻塞原因和需要的外部输入。

人工检查点：
- 建议作为最终检查点。人工可以接受报告、要求修改或停止导出。
