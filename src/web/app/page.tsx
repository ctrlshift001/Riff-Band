"use client";

import { useEffect, useMemo, useState } from "react";

import {
  ApiError,
  createProject,
  createStageDraft,
  decideStage,
  getProject,
  listProjects,
  saveStage,
  type ApprovalDecision,
  type Project,
  type ProjectStage,
  type ProjectSummary,
  type StageStatus,
} from "@/lib/api";

type ViewKey = "journey" | "evidence" | "methods" | "runs" | "approvals";
type SuggestionState = "pending" | "accepted" | "modified" | "rejected";
type DetailPanel = {
  eyebrow: string;
  title: string;
  description: string;
  rows?: { label: string; value: string }[];
  bullets?: string[];
  code?: string;
};
type ChatMessage = {
  id: number;
  role: "user" | "assistant";
  text: string;
  time: string;
};

const stages = [
  { key: "problem", id: "S0", name: "问题识别", agent: "Topic Agent", gate: "G0", output: "课题简报与已有研究报告", decision: "确认边界、改写问题或暂停课题", check: "候选空白完成反向检索" },
  { key: "literature", id: "S1", name: "文献综述", agent: "Literature Agent", gate: "覆盖检查", output: "检索协议、论文卡与证据流派", decision: "修改检索式并决定纳入/排除", check: "核心结论全部可回溯" },
  { key: "theory", id: "S2", name: "理论构建", agent: "Theory Agent", gate: "G1 前置", output: "理论图、研究问题与竞争解释", decision: "选择理论并确认贡献边界", check: "问题可证伪且存在竞争解释" },
  { key: "design", id: "S3", name: "研究设计", agent: "Design Agent", gate: "G1", output: "研究协议、设计备忘录与假设表", decision: "选择主备设计、接受风险并送审", check: "estimand、识别假设和停止条件完整" },
  { key: "data", id: "S4", name: "数据与变量", agent: "Data Agent", gate: "G2", output: "数据合同、变量表与伦理清单", decision: "确认数据权限、代理变量和运行位置", check: "许可、隐私和关键口径通过" },
  { key: "identification", id: "S5", name: "识别与检验", agent: "Analysis Plan Agent", gate: "G3", output: "分析计划、模型卡与代码计划", decision: "逐项修改并冻结主次分析", check: "计划与代码逐项对应" },
  { key: "analysis", id: "S6", name: "结果分析", agent: "Stata Analyst", gate: "G3 后运行", output: "do-file、运行日志与结果产物", decision: "审代码、批准运行和选择重跑分支", check: "获批代码与数据签名一致" },
  { key: "robustness", id: "S7", name: "稳健性检验", agent: "Robustness Agent", gate: "G4 前置", output: "稳健性矩阵与复现报告", decision: "追加检验或接受失败影响", check: "关键失败项不可被隐藏" },
  { key: "evidence", id: "S8", name: "机制与异质性", agent: "Evidence Agent", gate: "G4", output: "主张、证据边与解释备忘录", decision: "改写、降级或撤回主张", check: "每条主张连接结果与反证" },
  { key: "delivery", id: "S9", name: "结论与政策含义", agent: "Writing Agent", gate: "G5", output: "论文草稿、答复信与发布包", decision: "重写、披露并批准发布", check: "引用、数字与复现包一致" },
] as const;

const agentProfiles = [
  { mission: "收敛研究边界、验证问题价值并形成可执行的选题简报。", skills: ["研究空白", "反向检索", "可行性"], starters: ["帮我缩小研究边界", "检查这个问题是否已有充分研究", "给出三个可证伪的问题版本"] },
  { mission: "构建可复核检索协议，整理文献流派、分歧与证据缺口。", skills: ["检索式", "论文卡", "研究流派"], starters: ["生成中英文检索式", "总结主要研究流派", "寻找可能推翻当前结论的文献"] },
  { mission: "连接理论机制、竞争解释与可检验假设。", skills: ["理论机制", "竞争解释", "假设"], starters: ["比较三个候选理论", "把机制写成可检验假设", "指出当前理论链条的薄弱点"] },
  { mission: "把研究问题转化为 estimand、识别策略和可执行研究协议。", skills: ["研究设计", "识别假设", "变量口径"], starters: ["比较固定效应与双重差分", "检查识别假设", "完善主设计与备选设计"] },
  { mission: "设计数据合同、变量字典、数据质量与伦理检查。", skills: ["数据源", "变量字典", "许可伦理"], starters: ["列出可用数据来源", "设计核心变量口径", "检查数据许可与隐私风险"] },
  { mission: "把研究设计冻结为分析计划、模型公式与代码任务。", skills: ["分析计划", "模型公式", "功效检验"], starters: ["生成分析计划目录", "检查模型与假设是否对应", "列出必须预注册的检验"] },
  { mission: "协作编写和审查 Stata do-file，解释日志与运行产物。", skills: ["Stata", "do-file", "结果诊断"], starters: ["生成基准回归 do-file", "解释这段 Stata 日志", "检查聚类标准误设置"] },
  { mission: "建立稳健性矩阵，主动暴露失败检验和结论边界。", skills: ["稳健性", "安慰剂", "敏感性"], starters: ["生成稳健性检验矩阵", "设计安慰剂检验", "如何解释失败的稳健性结果"] },
  { mission: "把主张连接到文献、模型结果、反证与适用边界。", skills: ["证据图谱", "机制检验", "异质性"], starters: ["检查每条主张的证据链", "规划机制检验", "识别需要降级的结论"] },
  { mission: "协作形成论文、审稿回复与可复现发布包。", skills: ["论文写作", "引用核查", "发布复现"], starters: ["生成论文结构", "改写贡献表述", "检查数字与引用一致性"] },
] as const;

const navItems: { key: ViewKey; label: string; short: string }[] = [
  { key: "journey", label: "Research Journey", short: "研究旅程" },
  { key: "evidence", label: "Evidence Library", short: "证据库" },
  { key: "methods", label: "Methods", short: "方法库" },
  { key: "runs", label: "Runs", short: "分析运行" },
  { key: "approvals", label: "Approvals", short: "审批" },
];

const initialSuggestions = [
  {
    id: 1,
    title: "将因变量口径从数量改为质量",
    reason: "专利申请数容易受到防御性申请影响，授权且被引的发明专利更接近创新质量。",
    before: "专利申请数量 · ln(1+count)",
    after: "发明专利授权被引数 · ln(1+count)",
  },
  {
    id: 2,
    title: "将时间窗口扩展至 2016—2024",
    reason: "增加处理前观测期，可更充分检查共同趋势与提前反应。",
    before: "样本窗口 · 2018—2024",
    after: "样本窗口 · 2016—2024",
  },
  {
    id: 3,
    title: "增加企业与年份双向固定效应",
    reason: "控制不随时间变化的企业异质性与共同年份冲击。",
    before: "固定效应 · 企业固定效应",
    after: "固定效应 · 企业 + 年份固定效应",
  },
];

const evidenceRows = [
  { id: "H1", claim: "生成式 AI 工具采用可提升企业创新产出。", source: "Bessen (2018); Brynjolfsson et al. (2023)", state: "supported", note: "多项实证研究一致支持" },
  { id: "H2", claim: "工具采用对创新提升的效应具有滞后性。", source: "Aghion et al. (2019)", state: "pending", note: "需进一步检验动态效应" },
  { id: "H3", claim: "效应在高研发强度企业中更为显著。", source: "Huang & Rust (2021)", state: "pending", note: "异质性证据有限" },
  { id: "H4", claim: "同时采用其他数字化技术会削弱生成式 AI 的边际效应。", source: "Li et al. (2024)", state: "conflict", note: "存在相反结论" },
];

const libraryEvidence = [
  { title: "The Productivity J-Curve", authors: "Brynjolfsson, Rock & Syverson", year: 2021, stream: "通用技术与生产率", method: "企业面板", status: "已核验" },
  { title: "Artificial Intelligence and Innovation", authors: "Aghion, Jones & Jones", year: 2019, stream: "AI 与创新机制", method: "理论模型", status: "已核验" },
  { title: "Competing in the Age of AI", authors: "Iansiti & Lakhani", year: 2020, stream: "组织转型", method: "案例综合", status: "摘要级" },
  { title: "The Simple Economics of Machine Intelligence", authors: "Agrawal, Gans & Goldfarb", year: 2018, stream: "预测技术经济学", method: "理论分析", status: "已核验" },
  { title: "AI Adoption and Firm Performance", authors: "Representative evidence card", year: 2024, stream: "企业采用与绩效", method: "双重差分", status: "待全文" },
];

const methods = [
  { id: "M01", name: "面板固定效应", family: "实证解释", fit: 92, goal: "估计企业内部变化与创新结果的关系", assumptions: ["组内变异充分", "无随时间变化的遗漏混杂", "聚类层级正确"], engine: "Stata · xtreg" },
  { id: "M02", name: "双重差分", family: "因果识别", fit: 84, goal: "利用采用事件与对照组识别平均处理效应", assumptions: ["平行趋势", "无提前反应", "处理组间无溢出"], engine: "Stata · treatment effects" },
  { id: "M03", name: "工具变量 / 2SLS", family: "因果识别", fit: 61, goal: "缓解 AI 采用的内生选择问题", assumptions: ["工具相关", "排除限制", "单调性"], engine: "Stata · ivregress" },
  { id: "M04", name: "事件研究", family: "动态效应", fit: 78, goal: "展示采用前后的动态路径与提前趋势", assumptions: ["可靠处理时点", "基准期明确", "异质处理适当"], engine: "Stata · event study" },
];

const gateCards = [
  { id: "G0", title: "选题与已有研究", owner: "研究者 + 导师", status: "approved", time: "07-17 16:42", asset: "TopicBrief v3 · 报告 v2" },
  { id: "G1", title: "理论与研究设计", owner: "导师 + 方法审核者", status: "draft", time: "等待提交", asset: "ResearchProtocol v4" },
  { id: "G2", title: "数据、伦理与许可", owner: "数据负责人", status: "blocked", time: "等待 G1", asset: "DataContract 草稿" },
  { id: "G3", title: "分析计划与代码", owner: "方法审核者", status: "locked", time: "等待 G2", asset: "AnalysisPlan · do-file" },
  { id: "G4", title: "结果与核心主张", owner: "PI + 方法审核者", status: "locked", time: "等待正式运行", asset: "Runs · Claims" },
  { id: "G5", title: "成稿与发布", owner: "通讯作者", status: "locked", time: "等待 G4", asset: "Manuscript · Repro package" },
];

function StateBadge({ state }: { state: string }) {
  const labels: Record<string, string> = {
    supported: "已支持",
    pending: "待补证",
    review: "待审批",
    conflict: "有冲突",
    approved: "已批准",
    draft: "待提交",
    locked: "未解锁",
    succeeded: "运行成功",
    running: "正在运行",
    not_started: "未解锁",
    in_progress: "进行中",
    needs_review: "待审批",
    blocked: "已阻塞",
  };
  return <span className={`state-badge state-${state}`}>{labels[state] ?? state}</span>;
}

function DetailModal({ detail, onClose }: { detail: DetailPanel | null; onClose: () => void }) {
  if (!detail) return null;
  return (
    <div className="modal-backdrop detail-backdrop" role="presentation" onMouseDown={(event) => event.currentTarget === event.target && onClose()}>
      <section className="detail-modal" role="dialog" aria-modal="true" aria-labelledby="detail-title">
        <header className="detail-modal-header">
          <div><p className="eyebrow">{detail.eyebrow}</p><h2 id="detail-title">{detail.title}</h2></div>
          <button className="modal-close" onClick={onClose} aria-label="关闭详情">×</button>
        </header>
        <p className="detail-lede">{detail.description}</p>
        {detail.rows && <dl className="detail-facts">{detail.rows.map((row) => <div key={row.label}><dt>{row.label}</dt><dd>{row.value}</dd></div>)}</dl>}
        {detail.bullets && <ul className="detail-bullets">{detail.bullets.map((item) => <li key={item}>{item}</li>)}</ul>}
        {detail.code && <pre className="detail-code"><code>{detail.code}</code></pre>}
        <footer className="detail-modal-actions"><button className="primary-action" onClick={onClose}>完成查看</button></footer>
      </section>
    </div>
  );
}

function AgentChatDrawer({
  open,
  agentIndex,
  messages,
  busy,
  onClose,
  onSelectAgent,
  onSend,
  onCapture,
}: {
  open: boolean;
  agentIndex: number;
  messages: ChatMessage[];
  busy: boolean;
  onClose: () => void;
  onSelectAgent: (index: number) => void;
  onSend: (text: string) => void;
  onCapture: (text: string) => void;
}) {
  const [draft, setDraft] = useState("");
  if (!open) return null;
  const stage = stages[agentIndex];
  const profile = agentProfiles[agentIndex];
  const submit = () => {
    const value = draft.trim();
    if (!value || busy) return;
    onSend(value);
    setDraft("");
  };
  return (
    <div className="chat-backdrop" role="presentation" onMouseDown={(event) => event.currentTarget === event.target && onClose()}>
      <section className="agent-chat-shell" role="dialog" aria-modal="true" aria-labelledby="agent-chat-title">
        <header className="agent-chat-header">
          <div><p className="eyebrow">Research copilot workspace</p><h2 id="agent-chat-title">与科研智能体协作</h2></div>
          <div className="chat-human-badge"><span>人</span>关键决定仍由你审批</div>
          <button className="modal-close" onClick={onClose} aria-label="关闭智能体对话">×</button>
        </header>
        <div className="agent-chat-layout">
          <nav className="agent-directory" aria-label="选择科研智能体">
            <div className="agent-directory-label">10 个阶段智能体</div>
            {stages.map((item, index) => (
              <button className={index === agentIndex ? "is-active" : ""} onClick={() => onSelectAgent(index)} key={item.id}>
                <span>{item.id}</span><div><strong>{item.agent}</strong><small>{item.name}</small></div>
              </button>
            ))}
          </nav>
          <section className="chat-conversation">
            <div className="chat-agent-summary">
              <div className="chat-agent-avatar">AI</div>
              <div><p className="eyebrow">{stage.id} · {stage.name}</p><h3>{stage.agent}</h3><p>{profile.mission}</p></div>
            </div>
            <div className="chat-skill-row">{profile.skills.map((skill) => <span key={skill}>{skill}</span>)}</div>
            <div className="chat-messages" aria-live="polite">
              <article className="chat-message is-assistant">
                <div className="message-role">{stage.agent}</div>
                <p>我已读取当前阶段目标和交付要求。你可以让我解释、比较方案或形成一份可人工修改的草稿。</p>
              </article>
              {messages.map((message) => (
                <article className={`chat-message is-${message.role}`} key={message.id}>
                  <div className="message-role">{message.role === "user" ? "你" : stage.agent}<time>{message.time}</time></div>
                  <p>{message.text}</p>
                  {message.role === "assistant" && <button className="message-capture" onClick={() => onCapture(message.text)}>加入阶段记录</button>}
                </article>
              ))}
              {busy && <article className="chat-message is-assistant is-typing"><div className="message-role">{stage.agent}</div><p><span /><span /><span /> 正在整理回答</p></article>}
            </div>
            <div className="chat-starters" aria-label="快捷提问">{profile.starters.map((prompt) => <button onClick={() => onSend(prompt)} disabled={busy} key={prompt}>{prompt}</button>)}</div>
            <div className="chat-composer">
              <textarea
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    submit();
                  }
                }}
                placeholder={`向 ${stage.agent} 提问，Enter 发送，Shift+Enter 换行`}
                aria-label="智能体聊天输入"
              />
              <button className="primary-action" onClick={submit} disabled={!draft.trim() || busy}>发送</button>
            </div>
          </section>
          <aside className="chat-context">
            <p className="eyebrow">Current context</p>
            <h3>本次对话上下文</h3>
            <dl>
              <div><dt>阶段</dt><dd>{stage.id} · {stage.name}</dd></div>
              <div><dt>审批门</dt><dd>{stage.gate}</dd></div>
              <div><dt>主要交付</dt><dd>{stage.output}</dd></div>
              <div><dt>需要人工决定</dt><dd>{stage.decision}</dd></div>
            </dl>
            <div className="context-notice"><strong>协作边界</strong><p>智能体可以提出建议和草稿，但不能替你接受风险、批准阶段或启动正式分析。</p></div>
          </aside>
        </div>
      </section>
    </div>
  );
}

function ProgressNodes({ activeIndex, stageStates }: { activeIndex: number; stageStates: ProjectStage[] }) {
  return (
    <div className="progress-nodes" aria-label={`研究进度，第 ${activeIndex + 1} 阶段，共 10 阶段`}>
      {stages.map((stage, index) => {
        const isDone = stageStates[index]?.status === "approved";
        return (
        <div className={`progress-node ${isDone ? "is-done" : ""} ${index === activeIndex ? "is-current" : ""}`} key={stage.id}>
          <span>{isDone ? "✓" : ""}</span>
          <small>{stage.id}</small>
        </div>
      )})}
    </div>
  );
}

function StageRail({ activeIndex, stageStates, onSelect }: { activeIndex: number; stageStates: ProjectStage[]; onSelect: (index: number) => void }) {
  return (
    <aside className="stage-rail" aria-label="科研阶段导航">
      <div className="stage-rail-label">科研阶段</div>
      <div className="stage-list">
        {stages.map((stage, index) => {
          const state = stageStates[index]?.status;
          const isDone = state === "approved";
          return (
          <button
            className={`stage-item ${isDone ? "is-done" : ""} ${state === "not_started" ? "is-locked" : ""} ${index === activeIndex ? "is-active" : ""}`}
            key={stage.id}
            onClick={() => onSelect(index)}
            aria-current={index === activeIndex ? "step" : undefined}
          >
            <span className="stage-dot">{isDone ? "✓" : stage.id.replace("S", "")}</span>
            <span className="stage-id">{stage.id}</span>
            <span className="stage-name">{stage.name}</span>
          </button>
        )})}
      </div>
      <div className="rail-footer">
        <span className="rail-lock">人</span>
        <div><strong>Human in control</strong><small>关键决定只能由人批准</small></div>
      </div>
    </aside>
  );
}

function AgentPanel({
  stageIndex,
  suggestionStates,
  onDecision,
  onSubmit,
  onOpenChat,
  canSubmit,
  busy,
}: {
  stageIndex: number;
  suggestionStates: Record<number, SuggestionState>;
  onDecision: (id: number, state: SuggestionState) => void;
  onSubmit: () => void;
  onOpenChat: () => void;
  canSubmit: boolean;
  busy: boolean;
}) {
  const stage = stages[stageIndex];
  const stageSuggestions = stageIndex === 3
    ? initialSuggestions
    : [
        { id: 11, title: `补全 ${stage.output}`, reason: `依据当前已批准上游资产，${stage.agent} 发现 2 个待确认字段。`, before: "字段状态 · 待确认", after: "字段状态 · 已补充候选值" },
        { id: 12, title: "增加一条反向证据检查", reason: "主动寻找可能推翻当前判断的证据，降低确认偏误。", before: "反向检查 · 0 条", after: "反向检查 · 1 条候选" },
        { id: 13, title: "记录本阶段人工决定", reason: "下一阶段需要知道研究者接受了什么风险以及为什么。", before: "决定理由 · 空", after: "决定理由 · 等待人工填写" },
      ];

  return (
    <aside className="agent-panel" aria-label={`${stage.agent} 协作建议`}>
      <button className="agent-profile-button" onClick={onOpenChat} aria-label={`打开与 ${stage.agent} 的对话`}>
        <div>
          <p className="eyebrow">本阶段协作智能体</p>
          <h2>{stage.agent}</h2>
          <span>点击进入完整对话工作区 →</span>
        </div>
        <span className="agent-avatar">AI</span>
      </button>
      <div className="agent-live"><span />正在协作 · 只提交建议，不会替你批准</div>

      <div className="suggestion-list">
        {stageSuggestions.map((suggestion, index) => {
          const state = suggestionStates[suggestion.id] ?? "pending";
          return (
            <article className={`suggestion-card suggestion-${state}`} key={suggestion.id}>
              <div className="suggestion-title"><span>{index + 1}</span><strong>{suggestion.title}</strong></div>
              <p>{suggestion.reason}</p>
              <div className="diff-block">
                <div className="diff-before"><b>−</b>{suggestion.before}</div>
                <div className="diff-after"><b>+</b>{suggestion.after}</div>
              </div>
              {state === "pending" ? (
                <div className="suggestion-actions" aria-label="处理建议">
                  <button className="button-accept" onClick={() => onDecision(suggestion.id, "accepted")}>接受</button>
                  <button onClick={() => onDecision(suggestion.id, "modified")}>修改</button>
                  <button onClick={() => onDecision(suggestion.id, "rejected")}>拒绝</button>
                </div>
              ) : (
                <div className={`decision-result result-${state}`}>
                  {state === "accepted" && "✓ 已接受并生成新版本"}
                  {state === "modified" && "✎ 已转为人工编辑版本"}
                  {state === "rejected" && "× 已拒绝，保留决定记录"}
                  <button onClick={() => onDecision(suggestion.id, "pending")}>撤销</button>
                </div>
              )}
            </article>
          );
        })}
      </div>
      <div className="agent-submit-wrap">
        <div className="submit-readiness"><span>{Object.values(suggestionStates).filter((s) => s !== "pending").length}</span> 条建议已处理</div>
        <button className="primary-action" onClick={onSubmit} disabled={!canSubmit || busy}>{busy ? "正在同步…" : `提交 ${stage.gate} 审批`} <span>→</span></button>
      </div>
    </aside>
  );
}

function DesignWorkspace({
  question,
  setQuestion,
  selectedDesign,
  setSelectedDesign,
  onCompareMethods,
}: {
  question: string;
  setQuestion: (value: string) => void;
  selectedDesign: string;
  setSelectedDesign: (value: string) => void;
  onCompareMethods: () => void;
}) {
  return (
    <div className="design-workspace">
      <section className="content-card question-card">
        <div className="card-heading"><h2>研究问题</h2><span className="editable-mark">可人工编辑</span></div>
        <textarea aria-label="研究问题" value={question} onChange={(event) => setQuestion(event.target.value)} />
        <div className="field-meta"><span>版本 v4 · 由研究者最后修改</span><span>已连接 12 条文献证据</span></div>
      </section>

      <section className="content-card">
        <div className="card-heading"><h2>设计选择</h2><button className="text-button" onClick={onCompareMethods}>比较方法卡</button></div>
        <div className="design-options" role="radiogroup" aria-label="研究设计选择">
          <label className={`design-option ${selectedDesign === "fe" ? "is-selected" : ""}`}>
            <input type="radio" name="design" value="fe" checked={selectedDesign === "fe"} onChange={() => setSelectedDesign("fe")} />
            <span className="radio-ui" />
            <div className="design-copy">
              <div><strong>面板固定效应</strong><span className="recommend-mark">当前主设计</span></div>
              <p><span>单位：企业（上市公司）</span><span>处理：生成式 AI 工具采用</span><span>结果：发明专利授权被引数</span><span>窗口：2016—2024</span></p>
            </div>
            <span className="fit-score">适配 92</span>
          </label>
          <label className={`design-option ${selectedDesign === "did" ? "is-selected" : ""}`}>
            <input type="radio" name="design" value="did" checked={selectedDesign === "did"} onChange={() => setSelectedDesign("did")} />
            <span className="radio-ui" />
            <div className="design-copy">
              <div><strong>双重差分</strong><span className="backup-mark">备选设计</span></div>
              <p><span>单位：企业（上市公司）</span><span>事件：首次实际采用</span><span>结果：创新质量</span><span>关键：共同趋势</span></p>
            </div>
            <span className="fit-score">适配 84</span>
          </label>
        </div>
      </section>

      <section className="content-card evidence-card">
        <div className="card-heading"><h2>关键假设与证据状态</h2><span className="evidence-count">4 条假设 · 1 条冲突</span></div>
        <div className="evidence-table-wrap">
          <table className="evidence-table">
            <thead><tr><th>编号</th><th>假设</th><th>证据来源</th><th>状态</th><th>备注</th></tr></thead>
            <tbody>
              {evidenceRows.map((row) => (
                <tr key={row.id}><td>{row.id}</td><td>{row.claim}</td><td>{row.source}</td><td><StateBadge state={row.state} /></td><td>{row.note}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function GenericStage({
  stageIndex,
  onOpenDraft,
  onOpenDecision,
  onRunCheck,
}: {
  stageIndex: number;
  onOpenDraft: () => void;
  onOpenDecision: () => void;
  onRunCheck: () => void;
}) {
  const stage = stages[stageIndex];
  return (
    <div className="generic-stage">
      <section className="stage-hero-card">
        <div className="stage-hero-index">{stage.id}</div>
        <div><p className="eyebrow">本阶段目标</p><h2>{stage.name}</h2><p>与 {stage.agent} 协作形成一份可审阅资产，所有建议都先作为草稿，由研究者决定是否接受。</p></div>
      </section>
      <div className="stage-summary-grid">
        <article><span>01</span><p className="eyebrow">主要交付</p><h3>{stage.output}</h3><button onClick={onOpenDraft}>打开当前草稿 →</button></article>
        <article><span>02</span><p className="eyebrow">需要你决定</p><h3>{stage.decision}</h3><button onClick={onOpenDecision}>查看待决定项 →</button></article>
        <article><span>03</span><p className="eyebrow">退出检查</p><h3>{stage.check}</h3><button onClick={onRunCheck}>运行一致性检查 →</button></article>
      </div>
      <section className="stage-handoff-card">
        <div><p className="eyebrow">Handoff readiness</p><h3>进入下一阶段还缺 2 项人工确认</h3></div>
        <div className="readiness-track"><span style={{ width: `${42 + stageIndex * 4}%` }} /></div>
        <strong>{42 + stageIndex * 4}%</strong>
      </section>
    </div>
  );
}

function StageAssetEditor({
  stage,
  busy,
  onSave,
  onDraft,
  onDecision,
}: {
  stage?: ProjectStage;
  busy: boolean;
  onSave: (content: Record<string, unknown>, reason: string) => Promise<void>;
  onDraft: (instruction: string) => Promise<void>;
  onDecision: (decision: ApprovalDecision, reason: string) => Promise<void>;
}) {
  const [contentText, setContentText] = useState(() => JSON.stringify(stage?.content ?? {}, null, 2));
  const [changeReason, setChangeReason] = useState("人工更新阶段资产");
  const [instruction, setInstruction] = useState("");
  const [decisionReason, setDecisionReason] = useState("");
  const [editorError, setEditorError] = useState("");

  const locked = !stage || stage.status === "not_started";

  async function submitSave() {
    try {
      const parsed = JSON.parse(contentText) as unknown;
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("阶段资产必须是 JSON 对象");
      }
      setEditorError("");
      await onSave(parsed as Record<string, unknown>, changeReason);
    } catch (error) {
      if (error instanceof SyntaxError || (error instanceof Error && error.message.includes("JSON"))) {
        setEditorError(error instanceof Error ? error.message : "JSON 格式不正确");
        return;
      }
      throw error;
    }
  }

  return (
    <section className="content-card asset-editor">
      <div className="card-heading">
        <div><p className="eyebrow">FastAPI stage asset</p><h2>阶段资产</h2></div>
        {stage ? <StateBadge state={stage.status} /> : <StateBadge state="locked" />}
      </div>
      <div className="asset-meta">
        <span>{stage?.artifact_type ?? "尚未连接项目"}</span>
        <span>Revision {stage?.revision ?? 0}</span>
        <span>{stage?.content_hash ? `SHA-256 ${stage.content_hash.slice(0, 10)}…` : "尚无内容哈希"}</span>
      </div>
      <textarea
        className="asset-json"
        aria-label="阶段资产 JSON"
        value={contentText}
        onChange={(event) => setContentText(event.target.value)}
        disabled={locked || busy}
        spellCheck={false}
      />
      {editorError && <p className="form-error">{editorError}</p>}
      {locked ? (
        <div className="locked-notice">前一阶段批准后，本阶段将自动解锁。</div>
      ) : (
        <>
          <div className="asset-control-row">
            <label><span>草稿生成要求</span><input value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="例如：补齐研究对象、边界和反向检索字段" /></label>
            <button className="outline-compact" onClick={() => onDraft(instruction)} disabled={busy}>生成结构草稿</button>
          </div>
          <div className="asset-control-row">
            <label><span>版本变更说明</span><input value={changeReason} onChange={(event) => setChangeReason(event.target.value)} /></label>
            <button className="primary-action" onClick={submitSave} disabled={busy}>保存新 revision</button>
          </div>
          <div className="decision-row">
            <label><span>审批意见</span><input value={decisionReason} onChange={(event) => setDecisionReason(event.target.value)} placeholder="退回或阻塞时说明原因" /></label>
            <button onClick={() => onDecision("request_changes", decisionReason)} disabled={busy || !stage.revision}>退回修改</button>
            <button className="danger-button" onClick={() => onDecision("reject", decisionReason)} disabled={busy || !stage.revision}>阻塞阶段</button>
          </div>
        </>
      )}
    </section>
  );
}

function NewProjectModal({
  open,
  busy,
  onClose,
  onCreate,
}: {
  open: boolean;
  busy: boolean;
  onClose: () => void;
  onCreate: (title: string, idea: string) => Promise<void>;
}) {
  const [title, setTitle] = useState("");
  const [idea, setIdea] = useState("");

  if (!open) return null;
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.currentTarget === event.target && !busy && onClose()}>
      <section className="approval-modal project-modal" role="dialog" aria-modal="true" aria-labelledby="new-project-title">
        <button className="modal-close" onClick={onClose} disabled={busy} aria-label="关闭创建课题窗口">×</button>
        <p className="eyebrow">New research project</p>
        <h2 id="new-project-title">创建科研课题</h2>
        <label className="modal-field"><span>课题名称</span><input value={title} onChange={(event) => setTitle(event.target.value)} maxLength={160} autoFocus /></label>
        <label className="modal-field"><span>初始科学问题</span><textarea value={idea} onChange={(event) => setIdea(event.target.value)} maxLength={4000} /></label>
        <div className="modal-actions"><button onClick={onClose} disabled={busy}>取消</button><button className="primary-action" disabled={busy || !title.trim() || !idea.trim()} onClick={() => onCreate(title.trim(), idea.trim())}>{busy ? "正在创建…" : "创建并进入 S0"}</button></div>
      </section>
    </div>
  );
}

function EvidenceLibrary({ onOpenDetail, onToast }: { onOpenDetail: (detail: DetailPanel) => void; onToast: (message: string) => void }) {
  const [query, setQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState("全部");
  const [searchOpen, setSearchOpen] = useState(false);
  const [draftQuery, setDraftQuery] = useState("");
  const filtered = libraryEvidence.filter((item) => {
    const haystack = `${item.title} ${item.authors} ${item.stream} ${item.method}`.toLowerCase();
    const queryTerms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const matchesQuery = queryTerms.length === 0 || queryTerms.some((term) => haystack.includes(term));
    const matchesFilter = activeFilter === "全部" || item.stream === activeFilter;
    return matchesQuery && matchesFilter;
  });
  return (
    <div className="library-view page-view">
      <header className="view-header"><div><p className="eyebrow">Evidence Library</p><h1>证据库</h1><p>检索、筛选并核查每一条进入研究结论的文献与运行证据。</p></div><button className="primary-compact" onClick={() => setSearchOpen((open) => !open)}>＋ 新建检索</button></header>
      <div className="metric-strip">
        <div><strong>100</strong><span>设计语料论文</span></div><div><strong>12</strong><span>当前课题核心文献</span></div><div><strong>4</strong><span>研究流派</span></div><div><strong>92%</strong><span>核心主张可追溯</span></div>
      </div>
      {searchOpen && <section className="search-composer" aria-label="新建文献检索"><div><p className="eyebrow">New search</p><h2>创建可复核检索</h2><p>输入主题、变量或方法；本次条件会保留在检索记录中。</p></div><label><span>检索问题</span><input value={draftQuery} onChange={(event) => setDraftQuery(event.target.value)} placeholder="例如：生成式 AI 企业创新 双重差分" autoFocus /></label><label><span>来源范围</span><select defaultValue="all"><option value="all">顶刊与工作论文</option><option value="journal">仅同行评审期刊</option><option value="working">包含工作论文</option></select></label><div><button onClick={() => setSearchOpen(false)}>取消</button><button className="primary-action" onClick={() => { if (!draftQuery.trim()) { onToast("请先输入检索问题"); return; } setQuery(draftQuery.trim()); setSearchOpen(false); onToast(`已运行检索：${draftQuery.trim()}`); }}>运行检索</button></div></section>}
      <section className="content-card library-panel">
        <div className="library-tools">
          <label className="search-field"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索题名、作者、方法或流派" aria-label="搜索证据库" /></label>
          <div className="filter-chips" aria-label="研究流派筛选">
            {["全部", "通用技术与生产率", "AI 与创新机制", "组织转型"].map((filter) => <button className={activeFilter === filter ? "is-active" : ""} onClick={() => setActiveFilter(filter)} key={filter}>{filter}</button>)}
          </div>
        </div>
        <div className="library-table-wrap">
          <table className="library-table"><thead><tr><th>论文</th><th>研究流派</th><th>年份</th><th>方法</th><th>证据等级</th><th /></tr></thead><tbody>
            {filtered.map((item) => <tr key={item.title}><td><strong>{item.title}</strong><span>{item.authors}</span></td><td>{item.stream}</td><td>{item.year}</td><td>{item.method}</td><td><span className={`source-level ${item.status === "已核验" ? "verified" : ""}`}>{item.status}</span></td><td><button className="row-action" onClick={() => onOpenDetail({ eyebrow: "Evidence card", title: item.title, description: "论文卡展示进入当前研究结论的来源、方法和核验状态。任何主张都应能够回溯到原始证据。", rows: [{ label: "作者", value: item.authors }, { label: "年份", value: String(item.year) }, { label: "研究流派", value: item.stream }, { label: "方法", value: item.method }, { label: "证据等级", value: item.status }], bullets: ["核查研究对象、样本与变量是否和当前课题可比", "记录支持性证据，同时保留冲突和无效结果", "全文未核验前，不允许直接进入核心主张"] })}>打开论文卡</button></td></tr>)}
          </tbody></table>
          {filtered.length === 0 && <div className="empty-state">没有匹配的证据，试试调整关键词或流派。</div>}
        </div>
      </section>
    </div>
  );
}

function MethodsView({ onOpenDetail, onAdd }: { onOpenDetail: (detail: DetailPanel) => void; onAdd: (methodId: string) => void }) {
  const [selected, setSelected] = useState(methods[0].id);
  const activeMethod = methods.find((method) => method.id === selected) ?? methods[0];
  const formulaByMethod: Record<string, string> = {
    M01: "Y_it = βD_it + γX_it + α_i + λ_t + ε_it",
    M02: "Y_it = α + β(Treat_i × Post_t) + γ_i + λ_t + ε_it",
    M03: "D_it = πZ_it + γX_it + u_it\nY_it = βD̂_it + γX_it + ε_it",
    M04: "Y_it = α_i + λ_t + Σₖ≠₋₁ βₖ 1[t-T_i=k] + ε_it",
  };
  return (
    <div className="methods-view page-view">
      <header className="view-header"><div><p className="eyebrow">Method & Formula Studio</p><h1>方法库</h1><p>不按“模型更复杂”推荐，而是比较目标、数据、假设和失败条件。</p></div><button className="outline-compact" onClick={() => onOpenDetail({ eyebrow: "Formula library · 4 / 47", title: "当前课题推荐公式卡", description: "公式卡同时记录 estimand、识别假设、适用数据和 Stata 实现，不把公式复杂度等同于研究质量。", rows: methods.map((method) => ({ label: method.name, value: `${formulaByMethod[method.id]} · ${method.engine}` })), bullets: ["先明确估计目标，再选择模型", "主模型、稳健性模型和探索性模型必须分层", "每个模型都要对应失败条件与诊断结果"] })}>查看 47 张公式卡</button></header>
      <div className="methods-layout">
        <section className="method-card-grid" aria-label="候选方法">
          {methods.map((method) => <button className={`method-card ${selected === method.id ? "is-selected" : ""}`} onClick={() => setSelected(method.id)} key={method.id}><div><span>{method.id}</span><span>{method.family}</span></div><h2>{method.name}</h2><p>{method.goal}</p><div className="method-fit"><span><i style={{ width: `${method.fit}%` }} /></span><strong>{method.fit}% 适配</strong></div><small>{method.engine}</small></button>)}
        </section>
        <aside className="method-detail">
          <p className="eyebrow">当前比较</p><h2>{activeMethod.name}</h2><div className="method-score-ring"><strong>{activeMethod.fit}</strong><span>设计适配度</span></div>
          <h3>进入设计前必须确认</h3><ul>{activeMethod.assumptions.map((item) => <li key={item}><span>!</span>{item}</li>)}</ul>
          <div className="method-warning"><strong>方法边界</strong><p>推荐分数只是决策辅助；假设未通过时，平台会阻塞而不是自动换成更复杂模型。</p></div>
          <button className="primary-action" onClick={() => onAdd(activeMethod.id)}>加入研究设计</button>
        </aside>
      </div>
    </div>
  );
}

function RunsView({ onOpenDetail, onToast }: { onOpenDetail: (detail: DetailPanel) => void; onToast: (message: string) => void }) {
  const tabs = ["分析计划", "Do-file", "运行前检查", "正式运行", "结果审阅"];
  const defaultDoFile = [
    "version 18.0",
    "set more off",
    "use \"input/firm_panel.dta\", clear",
    "datasignature",
    "xtset firm_id year",
    "",
    "* G3-approved main analysis",
    "xtreg innovation_quality ai_adoption controls i.year, ///",
    "  fe vce(cluster firm_id)",
    "",
    "estimates store baseline_fe",
    "etable, estimates(baseline_fe) showstars",
    "collect export \"output/main_results.xlsx\", replace",
  ].join("\n");
  const [tab, setTab] = useState(2);
  const [runState, setRunState] = useState<"ready" | "running" | "succeeded">("ready");
  const [editingCode, setEditingCode] = useState(false);
  const [doFile, setDoFile] = useState(defaultDoFile);
  function startRun() {
    setRunState("running");
    window.setTimeout(() => { setRunState("succeeded"); onToast("Stata 运行完成，14 项产物已回收"); }, 1600);
  }
  return (
    <div className="runs-view page-view">
      <header className="view-header"><div><p className="eyebrow">Stata Workbench</p><h1>可审批、可复现的分析运行</h1><p>在机构已授权环境运行。代码、数据签名、日志与结果保持同一条血缘。</p></div><div className="runner-status"><span /> Institution Runner · 在线 <b>1 / 4 席位</b></div></header>
      <div className="run-gate-banner"><div><span>G3</span><div><strong>分析计划与代码已冻结</strong><small>AnalysisPlan v3 · analysis.do SHA-256 9f5a…4c21 · 方法审核者已批准</small></div></div><button onClick={() => onOpenDetail({ eyebrow: "G3 approval package", title: "分析计划与代码审批包", description: "本次正式运行只能使用已批准的分析计划、数据签名和 do-file revision。", rows: [{ label: "分析计划", value: "AnalysisPlan v3" }, { label: "代码版本", value: "analysis.do · revision 7" }, { label: "代码哈希", value: "SHA-256 9f5a…4c21" }, { label: "批准角色", value: "方法审核者" }], bullets: ["主模型与研究协议逐项对应", "数据签名、许可和运行环境已核验", "代码变化将自动使 G3 之后的审批失效"] })}>查看审批包</button></div>
      <div className="workbench-shell">
        <nav className="workbench-tabs" aria-label="Stata 工作台步骤">{tabs.map((item, index) => <button className={tab === index ? "is-active" : ""} onClick={() => setTab(index)} key={item}><span>{index + 1}</span>{item}</button>)}</nav>
        <section className="workbench-content">
          {tab === 0 && <div className="plan-grid"><article><p className="eyebrow">Primary estimand</p><h3>生成式 AI 采用对企业创新质量的平均处理效应</h3><dl><div><dt>样本</dt><dd>2016—2024 中国 A 股上市公司</dd></div><div><dt>固定效应</dt><dd>企业 + 年份</dd></div><div><dt>标准误</dt><dd>企业层级聚类</dd></div><div><dt>主要结果</dt><dd>发明专利授权被引数 ln(1+x)</dd></div></dl></article><article><p className="eyebrow">Robustness matrix</p><ul className="check-list"><li>✓ 替换采用测量</li><li>✓ 排除同期数字化政策</li><li>○ 安慰剂采用年份</li><li>○ 事件窗口敏感性</li></ul></article></div>}
          {tab === 1 && <div className="code-pane"><div className="code-toolbar"><span>analysis.do · revision 7</span><div><button onClick={() => onOpenDetail({ eyebrow: "Code diff", title: "Revision 6 → 7", description: "当前版本只增加年份固定效应并锁定企业层级聚类标准误。", code: "- xtreg innovation_quality ai_adoption controls, fe\n+ xtreg innovation_quality ai_adoption controls i.year, fe vce(cluster firm_id)", bullets: ["模型变化已映射到 AnalysisPlan v3", "正式运行仍需人工启动"] })}>比较版本</button><button onClick={() => { if (editingCode) onToast("人工编辑已保留在当前草稿，保存 revision 后才会进入审批"); setEditingCode((editing) => !editing); }}>{editingCode ? "完成编辑" : "人工编辑"}</button></div></div>{editingCode ? <textarea className="code-editor" value={doFile} onChange={(event) => setDoFile(event.target.value)} aria-label="编辑 Stata do-file" spellCheck={false} /> : <pre><code>{doFile}</code></pre>}</div>}
          {tab === 2 && <div className="preflight-layout"><div className="preflight-score"><div className="score-circle"><strong>8/8</strong><span>检查通过</span></div><h3>可以提交正式运行</h3><p>输入、许可、审批、路径与代码策略均与获批版本一致。</p></div><div className="preflight-checks">{["G3 revision/hash 有效", "Stata MP 19 · 许可席位可用", "输入数据签名一致", "面板键 firm_id × year 唯一", "所需变量全部存在", "未发现 shell / 网络 / 动态安装", "ado manifest 已锁定", "输出路径与资源上限合规"].map((item) => <div key={item}><span>✓</span>{item}</div>)}</div></div>}
          {tab === 3 && <div className="run-console"><div className="console-status"><div className={`run-state-icon state-${runState}`}>{runState === "ready" ? "▶" : runState === "running" ? "…" : "✓"}</div><div><p className="eyebrow">Formal run</p><h3>{runState === "ready" ? "等待人工启动" : runState === "running" ? "正在机构 Runner 中执行" : "运行成功并完成产物回收"}</h3><p>{runState === "ready" ? "AI 无权自行启动正式主分析。" : runState === "running" ? "正在执行 baseline_fe，已完成数据审计。" : "Exit code 0 · 14 项产物 · manifest 已生成"}</p></div></div><button className="primary-action" onClick={startRun} disabled={runState === "running"}>{runState === "ready" ? "人工确认并启动" : runState === "running" ? "正在运行…" : "创建重跑分支"}</button><div className="run-log"><span>[09:42:01] AI4MS_RUN_ID=run_20260719_001</span><span>[09:42:02] datasignature: 1843:2489(...)</span><span>[09:42:04] xtset firm_id year · strongly balanced</span><span className={runState === "succeeded" ? "log-success" : ""}>[{runState === "succeeded" ? "09:42:11" : "--:--:--"}] {runState === "succeeded" ? "AI4MS_COMPLETED · exit 0" : "waiting…"}</span></div></div>}
          {tab === 4 && <div className="results-grid"><article><p className="eyebrow">Primary result</p><h3>AI 采用与创新质量呈正相关</h3><strong className="result-number">+8.4%</strong><span>95% CI [3.1%, 13.7%]</span><small>解释仍需 G4 人工审批</small></article><article><p className="eyebrow">Diagnostics</p><ul className="check-list"><li>✓ 共同趋势未拒绝</li><li>✓ 聚类标准误已应用</li><li>! 异质性结果待复核</li><li>○ 安慰剂检验待追加</li></ul></article><article><p className="eyebrow">Artifacts</p><ul className="artifact-list"><li>main_results.xlsx <span>已签名</span></li><li>event_study.png <span>已签名</span></li><li>analysis.log <span>原始</span></li><li>run_manifest.json <span>完整</span></li></ul></article></div>}
        </section>
      </div>
    </div>
  );
}

function ApprovalsView({ project, onOpen, onOpenDetail }: { project: Project | null; onOpen: (stageIndex: number) => void; onOpenDetail: (detail: DetailPanel) => void }) {
  const gateStageIndices = [0, 3, 4, 5, 8, 9];
  const cards = gateCards.map((gate, index) => {
    const stageIndex = gateStageIndices[index];
    const stage = project?.stages[stageIndex];
    const status = !stage || stage.status === "not_started"
      ? "locked"
      : stage.status === "needs_review"
        ? "review"
        : stage.status === "in_progress"
          ? "draft"
          : stage.status;
    return {
      ...gate,
      status,
      stageIndex,
      asset: stage ? `${stage.artifact_type} · revision ${stage.revision}` : gate.asset,
      time: stage?.updated_at ? new Date(stage.updated_at).toLocaleString("zh-CN") : "等待前置阶段",
      disabled: !stage || stage.status === "not_started" || stage.revision < 1,
    };
  });
  const approved = project?.stages.filter((stage) => stage.status === "approved").length ?? 0;
  const pending = project?.stages.filter((stage) => stage.status === "needs_review").length ?? 0;
  const blocked = project?.stages.filter((stage) => stage.status === "blocked").length ?? 0;
  const returned = project?.approvals.filter((event) => event.decision === "request_changes").length ?? 0;
  return (
    <div className="approvals-view page-view">
      <header className="view-header"><div><p className="eyebrow">Human Approval Center</p><h1>人工审批中心</h1><p>批准的是确定版本和哈希。上游语义变化会使受影响的下游审批自动失效。</p></div><button className="outline-compact" onClick={() => onOpenDetail({ eyebrow: "Approval policy", title: "人工审批与失效规则", description: "智能体不能成为批准人。平台冻结 revision 和内容哈希，并在上游语义变化时使受影响的下游审批失效。", rows: [{ label: "G0", value: "选题价值与已有研究" }, { label: "G1", value: "理论与研究设计" }, { label: "G2", value: "数据、伦理与许可" }, { label: "G3", value: "分析计划与代码" }, { label: "G4", value: "结果与核心主张" }, { label: "G5", value: "成稿与发布" }], bullets: ["课题边界变化：G0–G5 失效", "主设计变化：G1–G5 失效", "主模型或 do-file 变化：G3–G5 失效", "纯排版变化：仅重查 G5 输出"] })}>查看审批规则</button></header>
      <div className="approval-summary"><div><strong>{approved}</strong><span>已批准阶段</span></div><div><strong>{pending}</strong><span>待审批</span></div><div><strong>{blocked}</strong><span>已阻塞</span></div><div><strong>{returned}</strong><span>退回记录</span></div></div>
      <div className="approval-layout">
        <section className="gate-list">{cards.map((gate) => <button className={`gate-card gate-${gate.status}`} onClick={() => gate.disabled ? onOpenDetail({ eyebrow: `${gate.id} approval gate`, title: gate.title, description: "当前审批门尚未解锁。你仍然可以查看所需资产和前置条件。", rows: [{ label: "审批资产", value: gate.asset }, { label: "批准人", value: gate.owner }, { label: "当前状态", value: gate.time }], bullets: ["完成前置阶段并冻结当前 revision", "核查证据限制、风险与变更说明", "由指定人工角色完成批准"] }) : onOpen(gate.stageIndex)} aria-disabled={gate.disabled} key={gate.id}><span className="gate-code">{gate.id}</span><div><h2>{gate.title}</h2><p>{gate.asset}</p><small>批准人：{gate.owner}</small></div><div className="gate-state"><StateBadge state={gate.status} /><small>{gate.time}</small></div><span className="gate-arrow">→</span></button>)}</section>
        <aside className="approval-rule-card"><p className="eyebrow">Four-eyes policy</p><h2>关键决定至少经过两种角色</h2><div className="reviewer-stack"><span>研</span><span>导</span><span>法</span></div><p>研究者提交，导师或 PI 与方法审核者分别确认价值和方法。Agent 永远不能成为批准人。</p><hr /><h3>上游变化会发生什么？</h3><ul><li>课题边界变化 → G0–G5 失效</li><li>主设计变化 → G1–G5 失效</li><li>主模型或 do-file 变化 → G3–G5 失效</li><li>纯排版变化 → 仅重查 G5 输出</li></ul></aside>
      </div>
    </div>
  );
}

function ApprovalModal({
  open,
  stageIndex,
  stageState,
  busy,
  onClose,
  onConfirm,
}: {
  open: boolean;
  stageIndex: number;
  stageState?: ProjectStage;
  busy: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => Promise<void>;
}) {
  const [checked, setChecked] = useState([true, true, false]);
  const [reason, setReason] = useState("已检查本阶段资产、证据限制和未解决风险，同意批准当前 revision。");
  if (!open) return null;
  const stage = stages[stageIndex];
  const allChecked = checked.every(Boolean);
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.currentTarget === event.target && onClose()}>
      <section className="approval-modal" role="dialog" aria-modal="true" aria-labelledby="approval-title">
        <button className="modal-close" onClick={onClose} aria-label="关闭审批窗口">×</button>
        <p className="eyebrow">Human approval · {stage.gate}</p>
        <h2 id="approval-title">批准“{stage.name}”当前版本</h2>
        <p>本次操作会批准确定的 revision 和内容哈希，并解锁下一阶段。后续修改本阶段会自动使下游状态失效。</p>
        <div className="review-packet"><div><span>审批对象</span><strong>{stageState?.artifact_type ?? stage.output}</strong></div><div><span>当前版本</span><strong>Revision {stageState?.revision ?? 0} · {stageState?.content_hash?.slice(0, 10) ?? "尚无哈希"}…</strong></div><div><span>执行角色</span><strong>Human reviewer</strong></div></div>
        <h3>提交前由研究者确认</h3>
        <div className="modal-checks">
          {["我已检查研究问题、变量口径和主设计", "我已阅读冲突证据与当前覆盖限制", "我理解批准后再修改主设计会使下游审批失效"].map((item, index) => <label key={item}><input type="checkbox" checked={checked[index]} onChange={() => setChecked((current) => current.map((value, itemIndex) => itemIndex === index ? !value : value))} /><span>{item}</span></label>)}
        </div>
        <label className="reason-field"><span>审批说明</span><textarea value={reason} onChange={(event) => setReason(event.target.value)} /></label>
        <div className="modal-actions"><button onClick={onClose} disabled={busy}>继续修改</button><button className="primary-action" disabled={!allChecked || busy || !stageState?.revision} onClick={() => onConfirm(reason)}>{busy ? "正在批准…" : "确认批准并推进"}</button></div>
      </section>
    </div>
  );
}

export default function Home() {
  const [view, setView] = useState<ViewKey>("journey");
  const [activeStage, setActiveStage] = useState(0);
  const [selectedDesign, setSelectedDesign] = useState("fe");
  const [question, setQuestion] = useState("生成式 AI 的引入是否显著提升了企业创新产出？其作用机制与边界条件是什么？");
  const [suggestionStates, setSuggestionStates] = useState<Record<number, SuggestionState>>({});
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [newProjectOpen, setNewProjectOpen] = useState(false);
  const [projectMenu, setProjectMenu] = useState(false);
  const [userMenu, setUserMenu] = useState(false);
  const [detail, setDetail] = useState<DetailPanel | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatAgent, setChatAgent] = useState(0);
  const [chatMessages, setChatMessages] = useState<Record<number, ChatMessage[]>>({});
  const [chatBusy, setChatBusy] = useState(false);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [connectionState, setConnectionState] = useState<"loading" | "ready" | "error">("loading");
  const [apiError, setApiError] = useState("");
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState("");
  const activeStageData = stages[activeStage];
  const activeStageState = project?.stages[activeStage];
  const pendingApprovals = project?.stages.filter((stage) => stage.status === "needs_review").length ?? 0;
  const pageTitle = useMemo(() => navItems.find((item) => item.key === view)?.short ?? "研究旅程", [view]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const availableProjects = await listProjects();
        if (cancelled) return;
        setProjects(availableProjects);
        if (availableProjects.length > 0) {
          const loadedProject = await getProject(availableProjects[0].project_id);
          if (cancelled) return;
          setProject(loadedProject);
          const currentIndex = stages.findIndex((stage) => stage.key === loadedProject.current_stage);
          setActiveStage(currentIndex >= 0 ? currentIndex : 0);
          syncDesignFields(loadedProject);
        }
        setConnectionState("ready");
      } catch (error) {
        if (cancelled) return;
        setConnectionState("error");
        setApiError(readError(error));
      }
    }
    void load();
    return () => { cancelled = true; };
  }, []);

  function readError(error: unknown) {
    if (error instanceof ApiError) return error.message;
    if (error instanceof Error) return error.message;
    return "无法连接 FastAPI 服务";
  }

  function syncDesignFields(nextProject: Project) {
    const design = nextProject.stages.find((stage) => stage.key === "design");
    const researchQuestion = design?.content.research_question;
    const primaryMethod = design?.content.primary_method;
    if (typeof researchQuestion === "string" && researchQuestion) setQuestion(researchQuestion);
    if (typeof primaryMethod === "string" && primaryMethod) setSelectedDesign(primaryMethod);
  }

  function applyProject(nextProject: Project, followCurrent = false) {
    setProject(nextProject);
    syncDesignFields(nextProject);
    const summary: ProjectSummary = {
      project_id: nextProject.project_id,
      title: nextProject.title,
      initial_idea: nextProject.initial_idea,
      status: nextProject.status,
      current_stage: nextProject.current_stage,
      created_at: nextProject.created_at,
      updated_at: nextProject.updated_at,
    };
    setProjects((current) => [summary, ...current.filter((item) => item.project_id !== summary.project_id)]);
    if (followCurrent) {
      const nextIndex = stages.findIndex((stage) => stage.key === nextProject.current_stage);
      if (nextIndex >= 0) setActiveStage(nextIndex);
    }
  }

  function showToast(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(""), 2400);
  }

  function handleError(error: unknown) {
    setApiError(readError(error));
    if (!(error instanceof ApiError)) setConnectionState("error");
  }

  async function openProject(projectId: string) {
    setBusy(true);
    setApiError("");
    try {
      const loadedProject = await getProject(projectId);
      applyProject(loadedProject, true);
      setProjectMenu(false);
      setConnectionState("ready");
    } catch (error) {
      handleError(error);
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateProject(title: string, idea: string) {
    setBusy(true);
    setApiError("");
    try {
      const created = await createProject(title, idea);
      applyProject(created, true);
      setNewProjectOpen(false);
      setProjectMenu(false);
      setView("journey");
      setConnectionState("ready");
      showToast("课题已创建，S0 问题识别已开始");
    } catch (error) {
      handleError(error);
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveStage(content: Record<string, unknown>, reason: string) {
    if (!project) return;
    setBusy(true);
    setApiError("");
    try {
      const finalContent = activeStageData.key === "design"
        ? { ...content, research_question: question, primary_method: selectedDesign }
        : content;
      const updated = await saveStage(project.project_id, activeStageData.key, finalContent, reason);
      applyProject(updated);
      showToast(`${activeStageData.id} 已保存为 revision ${updated.stages[activeStage].revision}`);
    } catch (error) {
      handleError(error);
    } finally {
      setBusy(false);
    }
  }

  async function handleCreateDraft(instruction: string) {
    if (!project) return;
    setBusy(true);
    setApiError("");
    try {
      const updated = await createStageDraft(project.project_id, activeStageData.key, instruction);
      applyProject(updated);
      showToast(`${activeStageData.id} 结构草稿已写入 FastAPI`);
    } catch (error) {
      handleError(error);
    } finally {
      setBusy(false);
    }
  }

  async function handleStageDecision(decision: ApprovalDecision, reason: string) {
    if (!project) return;
    setBusy(true);
    setApiError("");
    try {
      const updated = await decideStage(project.project_id, activeStageData.key, decision, reason);
      applyProject(updated, decision === "approve");
      if (decision === "approve") setApprovalOpen(false);
      const message = decision === "approve" ? "已由人工批准并解锁下一阶段" : decision === "request_changes" ? "已退回修改" : "已阻塞本阶段";
      showToast(`${activeStageData.gate} ${message}`);
    } catch (error) {
      handleError(error);
    } finally {
      setBusy(false);
    }
  }

  function decideSuggestion(id: number, state: SuggestionState) {
    setSuggestionStates((current) => ({ ...current, [id]: state }));
    const verb = state === "accepted" ? "接受" : state === "modified" ? "转为人工修改" : state === "rejected" ? "拒绝" : "撤销处理";
    showToast(`已${verb}建议，请在阶段资产中保存最终内容`);
  }

  function selectStage(index: number) {
    setActiveStage(index);
    setView("journey");
  }
  function openAgentChat(index = activeStage) {
    setChatAgent(index);
    setChatOpen(true);
  }
  function sendAgentMessage(text: string) {
    const index = chatAgent;
    const time = new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
    const userMessage: ChatMessage = { id: Date.now(), role: "user", text, time };
    setChatMessages((current) => ({ ...current, [index]: [...(current[index] ?? []), userMessage] }));
    setChatBusy(true);
    window.setTimeout(() => {
      const stage = stages[index];
      const profile = agentProfiles[index];
      const reply: ChatMessage = {
        id: Date.now() + 1,
        role: "assistant",
        time: new Date().toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" }),
        text: `围绕“${text.slice(0, 48)}${text.length > 48 ? "…" : ""}”，我建议先确认 ${profile.skills[0]} 与 ${profile.skills[1]}，再形成“候选方案—证据依据—失败条件—需要人工决定”四部分记录。本阶段输出应落到：${stage.output}。`,
      };
      setChatMessages((current) => ({ ...current, [index]: [...(current[index] ?? []), reply] }));
      setChatBusy(false);
    }, 520);
  }
  function addMethodToDesign(methodId: string) {
    setSelectedDesign(methodId === "M02" ? "did" : methodId === "M01" ? "fe" : methodId);
    setActiveStage(3);
    setView("journey");
    showToast("方法已加入研究设计草稿，请人工检查假设后保存 revision");
  }
  function openStageDraft() {
    document.querySelector(".asset-editor")?.scrollIntoView({ behavior: "smooth", block: "start" });
    showToast("已定位到阶段资产编辑器");
  }
  function runStageCheck() {
    setDetail({ eyebrow: "Consistency check", title: `${activeStageData.id} 一致性检查结果`, description: "已完成结构、证据、人工决定和下游交接字段检查。", rows: [{ label: "当前 revision", value: String(activeStageState?.revision ?? 0) }, { label: "结构完整度", value: activeStageState?.revision ? "8 / 10" : "尚无可检查版本" }, { label: "证据可追溯", value: activeStageState?.content_hash ? "通过" : "等待保存" }, { label: "人工决定", value: "还缺 2 项" }], bullets: ["补充当前阶段的决定理由", "确认一个失败条件及其处理方式", "完成后再提交人工审批"] });
  }

  function openApproval(stageIndex = activeStage) {
    const stage = project?.stages[stageIndex];
    if (!stage || stage.status === "not_started" || stage.revision < 1) {
      showToast("该阶段尚未解锁或没有可审批的 revision");
      return;
    }
    setActiveStage(stageIndex);
    setApprovalOpen(true);
  }

  const stageStatusLabels: Record<StageStatus, string> = {
    not_started: "未解锁",
    in_progress: "进行中",
    needs_review: "待人工审批",
    approved: "已批准",
    blocked: "已阻塞",
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={() => setView("journey")} aria-label="返回研究旅程"><span>AI</span>4MS</button>
        <nav className="topnav" aria-label="主导航">
          {navItems.map((item) => <button className={view === item.key ? "is-active" : ""} onClick={() => setView(item.key)} key={item.key}><span>{item.label}</span><small>{item.short}</small>{item.key === "approvals" && pendingApprovals > 0 && <i>{pendingApprovals}</i>}</button>)}
        </nav>
        <div className="topbar-actions">
          <div className="project-switcher-wrap"><button className="project-switcher" onClick={() => setProjectMenu((open) => !open)} aria-expanded={projectMenu}><span>当前项目</span><strong>{project?.title ?? (connectionState === "loading" ? "正在连接 FastAPI…" : "尚未创建课题")}</strong><b>⌄</b></button>{projectMenu && <div className="project-menu">{projects.map((item) => { const stage = stages.find((candidate) => candidate.key === item.current_stage); return <button className={item.project_id === project?.project_id ? "is-current" : ""} onClick={() => void openProject(item.project_id)} disabled={busy} key={item.project_id}><span>{item.title.slice(0, 1)}</span><div><strong>{item.title}</strong><small>{stage?.id ?? "S0"} · {stage?.name ?? "问题识别"}</small></div>{item.project_id === project?.project_id && <b>✓</b>}</button>; })}<hr /><button className="new-project" onClick={() => setNewProjectOpen(true)}>＋ 创建新课题</button></div>}</div>
          <button className="icon-button" onClick={() => { setView("approvals"); showToast(pendingApprovals > 0 ? `有 ${pendingApprovals} 个阶段等待人工审批` : "当前没有待审批阶段"); }} aria-label="待审批通知">●{pendingApprovals > 0 && <i>{pendingApprovals}</i>}</button>
          <div className="user-menu-wrap">
            <button className="user-button" onClick={() => setUserMenu((open) => !open)} aria-expanded={userMenu} aria-label="用户菜单">N</button>
            {userMenu && <div className="user-menu-popover">
              <strong>研究者工作区</strong><span>Human reviewer</span>
              <button onClick={() => { setUserMenu(false); openAgentChat(); }}>打开当前智能体</button>
              <button onClick={() => { setUserMenu(false); setDetail({ eyebrow: "Workspace guide", title: "如何使用 AI4MS", description: "按 S0–S9 推进科研，每个阶段与专属智能体协作，阶段资产由人修改并在关键审批门确认。", bullets: ["智能体只提出建议和草稿", "所有查看按钮均打开对应内容或状态", "正式分析、接受风险和发布必须由人批准"] }); }}>使用说明</button>
              <button onClick={() => { setUserMenu(false); showToast("界面偏好已保存"); }}>保存界面偏好</button>
            </div>}
          </div>
        </div>
      </header>

      {(connectionState !== "ready" || apiError) && <div className={`connection-banner connection-${connectionState}`}><strong>{connectionState === "loading" ? "正在连接 FastAPI" : connectionState === "error" ? "FastAPI 连接失败" : "操作未完成"}</strong><span>{apiError || "正在读取项目与阶段状态…"}</span>{connectionState === "error" && <button onClick={() => window.location.reload()}>重新连接</button>}</div>}

      <main className={`main-shell view-${view}`}>
        {view === "journey" && <StageRail activeIndex={activeStage} stageStates={project?.stages ?? []} onSelect={selectStage} />}
        <div className="main-content">
          {!project && connectionState === "ready" && <section className="empty-project"><p className="eyebrow">Workspace ready</p><h1>从一个科学问题开始</h1><p>创建课题后，S0-S9 的资产、版本和人工审批会持久化到 FastAPI 与 SQLite。</p><button className="primary-action" onClick={() => setNewProjectOpen(true)}>创建第一个课题</button></section>}
          {view === "journey" && (
            <>
              <header className="journey-header">
                <div><p className="eyebrow">Research Journey · {activeStageData.agent}</p><h1>{activeStageData.name}</h1><p><strong>{activeStage + 1}/10</strong> 阶段 <span>·</span> <b>{activeStageData.gate} {activeStageState ? stageStatusLabels[activeStageState.status] : "等待创建课题"}</b></p></div>
                <ProgressNodes activeIndex={activeStage} stageStates={project?.stages ?? []} />
              </header>
              <div className="journey-grid">
                <section className="stage-content stage-content-stack">
                  {activeStage === 3
                    ? <DesignWorkspace question={question} setQuestion={setQuestion} selectedDesign={selectedDesign} setSelectedDesign={setSelectedDesign} onCompareMethods={() => setView("methods")} />
                    : <GenericStage stageIndex={activeStage} onOpenDraft={openStageDraft} onOpenDecision={() => openAgentChat()} onRunCheck={runStageCheck} />}
                  <StageAssetEditor key={`${activeStageState?.key ?? "empty"}-${activeStageState?.revision ?? 0}`} stage={activeStageState} busy={busy} onSave={handleSaveStage} onDraft={handleCreateDraft} onDecision={handleStageDecision} />
                </section>
                <AgentPanel stageIndex={activeStage} suggestionStates={suggestionStates} onDecision={decideSuggestion} onSubmit={() => openApproval()} onOpenChat={() => openAgentChat()} canSubmit={Boolean(activeStageState && activeStageState.status !== "not_started" && activeStageState.status !== "approved" && activeStageState.revision > 0)} busy={busy} />
              </div>
            </>
          )}
          {view === "evidence" && <EvidenceLibrary onOpenDetail={setDetail} onToast={showToast} />}
          {view === "methods" && <MethodsView onOpenDetail={setDetail} onAdd={addMethodToDesign} />}
          {view === "runs" && <RunsView onOpenDetail={setDetail} onToast={showToast} />}
          {view === "approvals" && <ApprovalsView project={project} onOpen={openApproval} onOpenDetail={setDetail} />}
        </div>
      </main>

      <ApprovalModal open={approvalOpen} stageIndex={activeStage} stageState={activeStageState} busy={busy} onClose={() => setApprovalOpen(false)} onConfirm={(reason) => handleStageDecision("approve", reason)} />
      {newProjectOpen && <NewProjectModal open busy={busy} onClose={() => setNewProjectOpen(false)} onCreate={handleCreateProject} />}
      <DetailModal detail={detail} onClose={() => setDetail(null)} />
      <AgentChatDrawer open={chatOpen} agentIndex={chatAgent} messages={chatMessages[chatAgent] ?? []} busy={chatBusy} onClose={() => setChatOpen(false)} onSelectAgent={setChatAgent} onSend={sendAgentMessage} onCapture={() => showToast("智能体回答已加入当前阶段记录草稿")} />
      {toast && <div className="toast" role="status"><span>✓</span>{toast}</div>}
      <div className="screen-reader-status" aria-live="polite">当前页面：{pageTitle}</div>
    </div>
  );
}
