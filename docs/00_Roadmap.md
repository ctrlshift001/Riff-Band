## 目标
将 RiffBand 从"可运行原型"升级为"轻量级多 Agent 编排引擎 + 科研模式"。

## 当前状态
已完成：TUI 交互式 Shell、流式消息协议、会话持久化、ContentPart 流式文本、Crash 中断、工作区配置、首次引导、Slash 命令。

## 阶段一：研究模式落地（7 天冲刺）

### Day 1-2: 研究流程内核 + Skills
- 实现 `src/research/` 固定流程状态机（Phase 1-4，每步闸门校验）
- 编写 8 个核心 skill MD 文件（文献检索、知识综合、假设生成、跨模型辩论、大纲、撰写、审稿）
- `/research` slash 命令集成

### Day 3-4: 多 Agent 并行 + 输出格式
- Step 4 多 Agent 并行假设生成（复用 delegate_tasks）
- Step 5 跨模型交叉辩论
- LaTeX 输出模板 + HTML 报告模板

### Day 5-6: MCP 集成
- MCP Server 入口 + 研究流程 tool 封装
- Claude Code / Codex 对接测试

### Day 7: 收尾
- 端到端验证 + 文档 + demo

## 阶段二：质量提升（中期）
1. 扩展证据链与引用管理  
2. 强化质量门禁（一致性检查、证据匹配）  
3. 联网检索容错与 fallback  

## 阶段三：产品化（中长期）
1. 人机协同工作流  
2. 任务历史与项目管理  
3. 成本与权限治理  

## 建议优先级
`研究模式内核 -> MCP 集成 -> 质量门禁增强 -> 检索容错 -> 产品化`
