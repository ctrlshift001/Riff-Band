# 观点辩论

在撰写前从多视角压力测试候选观点。

## 阶段协议

步骤：`claim_debate`

目标：
- 批判性评估候选观点、研究空白、未来方向和研究问题。
- 决定每个重要观点是保留、修改、降级还是移除。

输入：
- `claims.jsonl`、`findings.jsonl`、`papers.jsonl` 和综合笔记。

推荐工具：
- `read_research_claims`、`read_findings`、`read_papers`：读取观点和证据。
- `read_scratchpad`：读取综合上下文。
- `novelty_check`：检查可能被过度声称的观点。
- `record_claim_debate`：记录 keep/revise/downgrade/remove 决策。
- `write_report_section`：写入本步骤报告章节。

执行步骤：
1. 读取候选观点和支撑证据。
2. 从证据覆盖、新颖性、相关性、方法可靠性、局限性和实际价值等角度审查每个观点。
3. 识别无支撑观点、过度泛化、引用缺口和较弱未来方向。
4. 为每个重要观点记录辩论决策。
5. 生成用于最终写作的观点优先级列表。
6. 写入报告章节：`观点辩论与优先级评估`。

必须产出：
- 结构化辩论记录。
- 观点级决策：keep、revise、downgrade 或 remove。
- 用于最终正文的优先级观点、空白和方向。

质量门：
- 每个 keep 决策必须有证据依据。
- 每个 revise/downgrade/remove 决策必须给出具体理由。

人工检查点：
- 建议启用。人工批准可避免最终报告围绕弱观点或不相关观点展开。
