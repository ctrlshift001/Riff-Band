"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ApiError,
  createProject as createApiProject,
  getProject as getApiProject,
  listProjects as listApiProjects,
  saveStage as saveApiStage,
  type Project as ApiProject,
  type ProjectSummary as ApiProjectSummary,
} from "@/lib/api";
import {
  ApprovalGatePage,
  AssetVersionPage,
  ConsistencyCheckWorkspace,
  createCheckIssues,
  createStageDraft as createLocalStageDraft,
  EvidenceRecordPage,
  IssueRemediationPage,
  MethodRecordPage,
  ProjectOverviewPage,
  ProjectWizard,
  StageDecisionsWorkspace,
  StageDraftWorkspace,
  type DeepRoute,
  type ResearchProject,
  type StageDraft,
} from "./deep-workspaces";

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
  { key: "problem", id: "S0", name: "问题识别", agent: "Topic Agent", gate: "G0", status: "done", output: "课题简报与已有研究报告", decision: "确认边界、改写问题或暂停课题", check: "候选空白完成反向检索" },
  { key: "literature", id: "S1", name: "文献综述", agent: "Literature Agent", gate: "覆盖检查", status: "done", output: "检索协议、论文卡与证据流派", decision: "修改检索式并决定纳入/排除", check: "核心结论全部可回溯" },
  { key: "theory", id: "S2", name: "理论构建", agent: "Theory Agent", gate: "G1 前置", status: "done", output: "理论图、研究问题与竞争解释", decision: "选择理论并确认贡献边界", check: "问题可证伪且存在竞争解释" },
  { key: "design", id: "S3", name: "研究设计", agent: "Design Agent", gate: "G1", status: "active", output: "研究协议、设计备忘录与假设表", decision: "选择主备设计、接受风险并送审", check: "estimand、识别假设和停止条件完整" },
  { key: "data", id: "S4", name: "数据与变量", agent: "Data Agent", gate: "G2", status: "todo", output: "数据合同、变量表与伦理清单", decision: "确认数据权限、代理变量和运行位置", check: "许可、隐私和关键口径通过" },
  { key: "identification", id: "S5", name: "识别与检验", agent: "Analysis Plan Agent", gate: "G3", status: "todo", output: "分析计划、模型卡与代码计划", decision: "逐项修改并冻结主次分析", check: "计划与代码逐项对应" },
  { key: "analysis", id: "S6", name: "结果分析", agent: "Stata Analyst", gate: "G3 后运行", status: "todo", output: "do-file、运行日志与结果产物", decision: "审代码、批准运行和选择重跑分支", check: "获批代码与数据签名一致" },
  { key: "robustness", id: "S7", name: "稳健性检验", agent: "Robustness Agent", gate: "G4 前置", status: "todo", output: "稳健性矩阵与复现报告", decision: "追加检验或接受失败影响", check: "关键失败项不可被隐藏" },
  { key: "evidence", id: "S8", name: "机制与异质性", agent: "Evidence Agent", gate: "G4", status: "todo", output: "主张、证据边与解释备忘录", decision: "改写、降级或撤回主张", check: "每条主张连接结果与反证" },
  { key: "delivery", id: "S9", name: "结论与政策含义", agent: "Writing Agent", gate: "G5", status: "todo", output: "论文草稿、答复信与发布包", decision: "重写、披露并批准发布", check: "引用、数字与复现包一致" },
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

function projectGateCards(project: ResearchProject, submittedGates: Record<string, boolean>) {
  const stage = project.stageIndex;
  const submitted = (gateId: string) => Boolean(submittedGates[`${project.id}:${gateId}`]);
  return gateCards.map((gate) => {
    if (gate.id === "G0") return { ...gate, status: stage > 0 ? "approved" : submitted("G0") ? "review" : "draft", time: stage > 0 ? "已批准并锁定" : submitted("G0") ? "等待研究者与导师会签" : "等待选题提交" };
    if (gate.id === "G1") {
      if (stage > 3) return { ...gate, status: "approved", time: "已批准并锁定" };
      if (stage === 3) return { ...gate, status: submitted("G1") ? "review" : "draft", time: submitted("G1") ? "等待 2 人会签" : "等待提交" };
      return { ...gate, status: "locked", time: "等待完成 S2" };
    }
    if (gate.id === "G2") {
      if (stage > 4) return { ...gate, status: "approved", time: "已批准并锁定" };
      if (stage === 4) return { ...gate, status: submitted("G2") ? "review" : "draft", time: submitted("G2") ? "等待数据负责人会签" : "等待数据负责人提交" };
      return { ...gate, status: stage === 3 ? "blocked" : "locked", time: stage === 3 ? "等待 G1" : "等待进入 S4" };
    }
    if (gate.id === "G3") {
      if (stage > 5) return { ...gate, status: "approved", time: "已批准并锁定" };
      if (stage === 5) return { ...gate, status: submitted("G3") ? "review" : "draft", time: submitted("G3") ? "等待方法审核者会签" : "等待分析计划提交" };
      return { ...gate, status: "locked", time: "等待 G2 与 S5" };
    }
    if (gate.id === "G4") {
      if (stage > 8) return { ...gate, status: "approved", time: "已批准并锁定" };
      if (stage === 8) return { ...gate, status: submitted("G4") ? "review" : "draft", time: submitted("G4") ? "等待 PI 与方法审核者会签" : "等待结果主张提交" };
      return { ...gate, status: "locked", time: "等待正式运行与稳健性检查" };
    }
    if (gate.id === "G5") return { ...gate, status: stage === 9 ? submitted("G5") ? "review" : "draft" : "locked", time: stage === 9 ? submitted("G5") ? "等待通讯作者会签" : "等待发布包提交" : "等待 G4" };
    return gate;
  });
}

const initialProjects: ResearchProject[] = [
  {
    id: "project-ai-innovation",
    name: "生成式 AI 与企业创新",
    code: "GENAI-INNO",
    icon: "企",
    discipline: "创新与战略管理",
    question: "生成式 AI 的引入是否显著提升了企业创新产出？其作用机制与边界条件是什么？",
    objective: "识别生成式 AI 工具采用对企业创新质量的影响，并解释组织互补与研发能力的作用机制。",
    boundary: "中国 A 股非金融上市公司；排除 ST、关键变量严重缺失和异常处理年份样本。",
    sampleWindow: "2016—2024",
    keywords: "生成式 AI, 企业创新, 组织互补, 数字化转型",
    dataSources: ["CSMAR / Wind", "CNRDS", "WIPO / 国家知识产权局", "上市公司年报"],
    owner: "当前研究者",
    reviewers: "导师 + 方法审核者",
    stageIndex: 3,
    status: "active",
    createdAt: "2026/7/17",
  },
  {
    id: "project-low-carbon",
    name: "低碳物流路径优化",
    code: "LC-LOGISTICS",
    icon: "碳",
    discipline: "运营与供应链",
    question: "多重不确定性下，低碳物流路径如何实现成本、时效与碳排放的协同优化？",
    objective: "构建可解释的多目标优化框架，并评估不同政策约束下的路径调整策略。",
    boundary: "长三角干线与城市配送网络；聚焦道路运输与可获得的企业运营数据。",
    sampleWindow: "2021—2026",
    keywords: "低碳物流, 路径优化, 多目标决策",
    dataSources: ["企业调研或实验", "国家统计局"],
    owner: "当前研究者",
    reviewers: "导师 + 领域专家",
    stageIndex: 1,
    status: "active",
    createdAt: "2026/7/12",
  },
  {
    id: "project-platform-governance",
    name: "平台治理与商家韧性",
    code: "PLATFORM-RES",
    icon: "平",
    discipline: "信息系统",
    question: "平台规则透明度如何影响中小商家的经营韧性与创新投入？",
    objective: "识别平台治理机制、商家适应行为与长期韧性之间的关系。",
    boundary: "中国数字平台上的中小商家，研究范围和可用数据仍待 S0 收敛。",
    sampleWindow: "待确认",
    keywords: "平台治理, 中小商家, 经营韧性",
    dataSources: ["企业调研或实验", "自建网络公开数据"],
    owner: "当前研究者",
    reviewers: "导师 + 方法审核者",
    stageIndex: 0,
    status: "draft",
    createdAt: "2026/7/19",
  },
];

function apiStageIndex(currentStage: string) {
  const index = stages.findIndex((stage) => stage.key === currentStage || stage.id === currentStage);
  return index >= 0 ? index : 0;
}

function mapApiProject(summary: ApiProjectSummary | ApiProject, existing?: ResearchProject): ResearchProject {
  const full = "stages" in summary ? summary : undefined;
  const designContent = full?.stages.find((stage) => stage.key === "design")?.content;
  const question = typeof designContent?.research_question === "string" ? designContent.research_question : summary.initial_idea;
  const objective = typeof designContent?.research_objective === "string" ? designContent.research_objective : existing?.objective ?? "围绕当前研究问题形成可复核、可审批、可复现的管理科学研究。";
  return {
    id: summary.project_id,
    name: summary.title,
    code: existing?.code ?? summary.project_id.slice(0, 12).toUpperCase(),
    icon: existing?.icon ?? (summary.title.trim().slice(0, 1) || "研"),
    discipline: existing?.discipline ?? "管理科学研究",
    question,
    objective,
    boundary: existing?.boundary ?? "研究对象、地区、行业与排除范围待在 S0 由研究者确认。",
    sampleWindow: existing?.sampleWindow ?? "待确认",
    keywords: existing?.keywords ?? "",
    dataSources: existing?.dataSources ?? [],
    owner: existing?.owner ?? "当前研究者",
    reviewers: existing?.reviewers ?? "导师 + 方法审核者",
    stageIndex: apiStageIndex(summary.current_stage),
    status: summary.status === "active" ? "active" : "paused",
    createdAt: new Date(summary.created_at).toLocaleDateString("zh-CN"),
  };
}

function mapApiDrafts(project: ApiProject, localProject: ResearchProject) {
  const mapped: Record<string, StageDraft> = {};
  project.stages.forEach((remoteStage) => {
    const index = stages.findIndex((stage) => stage.key === remoteStage.key);
    if (index < 0) return;
    const base = createLocalStageDraft(stages[index], localProject);
    const content = remoteStage.content;
    const text = (key: "title" | "summary" | "objective" | "content" | "scope" | "evidenceNote" | "decision" | "risk" | "handoff") => typeof content[key] === "string" ? String(content[key]) : base[key];
    mapped[`${localProject.id}:${index}`] = {
      title: text("title"),
      summary: text("summary"),
      objective: text("objective"),
      content: text("content"),
      scope: text("scope"),
      evidenceNote: text("evidenceNote"),
      decision: text("decision"),
      risk: text("risk"),
      handoff: text("handoff"),
      humanConfirmed: typeof content.humanConfirmed === "boolean" ? content.humanConfirmed : base.humanConfirmed,
      version: remoteStage.revision || base.version,
      savedAt: remoteStage.revision_created_at ? new Date(remoteStage.revision_created_at).toLocaleString("zh-CN") : base.savedAt,
    };
  });
  return mapped;
}

function StateBadge({ state }: { state: string }) {
  const labels: Record<string, string> = {
    supported: "已支持",
    pending: "待补证",
    review: "待审批",
    conflict: "有冲突",
    approved: "已批准",
    draft: "待提交",
    blocked: "前置阻塞",
    locked: "未解锁",
    succeeded: "运行成功",
    running: "正在运行",
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

function ProgressNodes({ activeIndex }: { activeIndex: number }) {
  return (
    <div className="progress-nodes" aria-label={`研究进度，第 ${activeIndex + 1} 阶段，共 10 阶段`}>
      {stages.map((stage, index) => (
        <div className={`progress-node ${index < activeIndex ? "is-done" : ""} ${index === activeIndex ? "is-current" : ""}`} key={stage.id}>
          <span>{index < activeIndex ? "✓" : ""}</span>
          <small>{stage.id}</small>
        </div>
      ))}
    </div>
  );
}

function StageRail({ activeIndex, onSelect }: { activeIndex: number; onSelect: (index: number) => void }) {
  return (
    <aside className="stage-rail" aria-label="科研阶段导航">
      <div className="stage-rail-label">科研阶段</div>
      <div className="stage-list">
        {stages.map((stage, index) => (
          <button
            className={`stage-item ${index < activeIndex ? "is-done" : ""} ${index === activeIndex ? "is-active" : ""}`}
            key={stage.id}
            onClick={() => onSelect(index)}
            aria-current={index === activeIndex ? "step" : undefined}
          >
            <span className="stage-dot">{index < activeIndex ? "✓" : stage.id.replace("S", "")}</span>
            <span className="stage-id">{stage.id}</span>
            <span className="stage-name">{stage.name}</span>
          </button>
        ))}
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
}: {
  stageIndex: number;
  suggestionStates: Record<number, SuggestionState>;
  onDecision: (id: number, state: SuggestionState) => void;
  onSubmit: () => void;
  onOpenChat: () => void;
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
        <button className="primary-action" onClick={onSubmit}>提交 {stage.gate} 审批 <span>→</span></button>
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

function EvidenceLibrary({ onOpenRecord, onToast }: { onOpenRecord: (title: string) => void; onToast: (message: string) => void }) {
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
            {filtered.map((item) => <tr key={item.title}><td><strong>{item.title}</strong><span>{item.authors}</span></td><td>{item.stream}</td><td>{item.year}</td><td>{item.method}</td><td><span className={`source-level ${item.status === "已核验" ? "verified" : ""}`}>{item.status}</span></td><td><button className="row-action" onClick={() => onOpenRecord(item.title)}>打开论文卡</button></td></tr>)}
          </tbody></table>
          {filtered.length === 0 && <div className="empty-state">没有匹配的证据，试试调整关键词或流派。</div>}
        </div>
      </section>
    </div>
  );
}

function MethodsView({ onOpenDetail, onOpenMethod, onAdd }: { onOpenDetail: (detail: DetailPanel) => void; onOpenMethod: (methodId: string) => void; onAdd: (methodId: string) => void }) {
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
          <div className="method-detail-actions"><button onClick={() => onOpenMethod(activeMethod.id)}>打开完整方法卡</button><button className="primary-action" onClick={() => onAdd(activeMethod.id)}>加入研究设计</button></div>
        </aside>
      </div>
    </div>
  );
}

function RunsView({ project, onOpenDetail, onOpenGate, onToast }: { project: ResearchProject; onOpenDetail: (detail: DetailPanel) => void; onOpenGate: (gateId: string) => void; onToast: (message: string) => void }) {
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
  const runLocked = project.stageIndex < 6;
  function startRun() {
    if (runLocked) {
      onToast("需先完成 S5 分析计划并通过 G3 人工审批");
      return;
    }
    setRunState("running");
    window.setTimeout(() => { setRunState("succeeded"); onToast("Stata 运行完成，14 项产物已回收"); }, 1600);
  }
  return (
    <div className="runs-view page-view">
      <header className="view-header"><div><p className="eyebrow">Stata Workbench</p><h1>可审批、可复现的分析运行</h1><p>在机构已授权环境运行。代码、数据签名、日志与结果保持同一条血缘。</p></div><div className={`runner-status ${runLocked ? "is-waiting" : ""}`}><span /> {runLocked ? "Runner 等待审批" : <>Institution Runner · 在线 <b>1 / 4 席位</b></>}</div></header>
      <div className={`run-gate-banner ${runLocked ? "is-locked" : ""}`}><div><span>G3</span><div><strong>{runLocked ? "正式运行尚未解锁" : "分析计划与代码已冻结"}</strong><small>{runLocked ? `当前项目位于 S${project.stageIndex}；需完成 S5 分析计划并通过 G3 人工审批` : "AnalysisPlan v3 · analysis.do SHA-256 9f5a…4c21 · 方法审核者已批准"}</small></div></div><button onClick={() => onOpenGate("G3")}>{runLocked ? "查看解锁条件" : "查看审批包"}</button></div>
      <div className="workbench-shell">
        <nav className="workbench-tabs" aria-label="Stata 工作台步骤">{tabs.map((item, index) => <button className={tab === index ? "is-active" : ""} onClick={() => setTab(index)} key={item}><span>{index + 1}</span>{item}</button>)}</nav>
        <section className="workbench-content">
          {tab === 0 && <div className="plan-grid"><article><p className="eyebrow">Primary estimand</p><h3>生成式 AI 采用对企业创新质量的平均处理效应</h3><dl><div><dt>样本</dt><dd>2016—2024 中国 A 股上市公司</dd></div><div><dt>固定效应</dt><dd>企业 + 年份</dd></div><div><dt>标准误</dt><dd>企业层级聚类</dd></div><div><dt>主要结果</dt><dd>发明专利授权被引数 ln(1+x)</dd></div></dl></article><article><p className="eyebrow">Robustness matrix</p><ul className="check-list"><li>✓ 替换采用测量</li><li>✓ 排除同期数字化政策</li><li>○ 安慰剂采用年份</li><li>○ 事件窗口敏感性</li></ul></article></div>}
          {tab === 1 && <div className="code-pane"><div className="code-toolbar"><span>analysis.do · revision 7</span><div><button onClick={() => onOpenDetail({ eyebrow: "Code diff", title: "Revision 6 → 7", description: "当前版本只增加年份固定效应并锁定企业层级聚类标准误。", code: "- xtreg innovation_quality ai_adoption controls, fe\n+ xtreg innovation_quality ai_adoption controls i.year, fe vce(cluster firm_id)", bullets: ["模型变化已映射到 AnalysisPlan v3", "正式运行仍需人工启动"] })}>比较版本</button><button onClick={() => { if (editingCode) onToast("人工编辑已保留在当前草稿，保存 revision 后才会进入审批"); setEditingCode((editing) => !editing); }}>{editingCode ? "完成编辑" : "人工编辑"}</button></div></div>{editingCode ? <textarea className="code-editor" value={doFile} onChange={(event) => setDoFile(event.target.value)} aria-label="编辑 Stata do-file" spellCheck={false} /> : <pre><code>{doFile}</code></pre>}</div>}
          {tab === 2 && (runLocked ? <div className="locked-workbench-state"><span>G3</span><div><p className="eyebrow">Preflight blocked</p><h3>运行前检查尚不能通过</h3><p>当前项目还没有获批的 AnalysisPlan、do-file 哈希和数据签名。先完成 S5，再由方法审核者批准 G3。</p><ul><li>完成 S4 数据合同与许可审批</li><li>完成 S5 分析计划、公式和失败条件</li><li>冻结 do-file revision 并通过 G3</li></ul></div><button onClick={() => onOpenGate("G3")}>查看 G3 条件</button></div> : <div className="preflight-layout"><div className="preflight-score"><div className="score-circle"><strong>8/8</strong><span>检查通过</span></div><h3>可以提交正式运行</h3><p>输入、许可、审批、路径与代码策略均与获批版本一致。</p></div><div className="preflight-checks">{["G3 revision/hash 有效", "Stata MP 19 · 许可席位可用", "输入数据签名一致", "面板键 firm_id × year 唯一", "所需变量全部存在", "未发现 shell / 网络 / 动态安装", "ado manifest 已锁定", "输出路径与资源上限合规"].map((item) => <div key={item}><span>✓</span>{item}</div>)}</div></div>)}
          {tab === 3 && <div className={`run-console ${runLocked ? "is-locked" : ""}`}><div className="console-status"><div className={`run-state-icon state-${runLocked ? "locked" : runState}`}>{runLocked ? "锁" : runState === "ready" ? "▶" : runState === "running" ? "…" : "✓"}</div><div><p className="eyebrow">Formal run</p><h3>{runLocked ? "等待 G3 人工批准" : runState === "ready" ? "等待人工启动" : runState === "running" ? "正在机构 Runner 中执行" : "运行成功并完成产物回收"}</h3><p>{runLocked ? "智能体不能绕过审批生成正式结果。" : runState === "ready" ? "AI 无权自行启动正式主分析。" : runState === "running" ? "正在执行 baseline_fe，已完成数据审计。" : "Exit code 0 · 14 项产物 · manifest 已生成"}</p></div></div><button className="primary-action" onClick={startRun} disabled={runLocked || runState === "running"}>{runLocked ? "等待 G3 批准" : runState === "ready" ? "人工确认并启动" : runState === "running" ? "正在运行…" : "创建重跑分支"}</button><div className="run-log"><span>{runLocked ? "[blocked] no approved AnalysisPlan revision" : "[09:42:01] AI4MS_RUN_ID=run_20260719_001"}</span><span>{runLocked ? "[blocked] data signature unavailable" : "[09:42:02] datasignature: 1843:2489(...)"}</span><span>{runLocked ? "[blocked] G3 human approval required" : "[09:42:04] xtset firm_id year · strongly balanced"}</span>{!runLocked && <span className={runState === "succeeded" ? "log-success" : ""}>[{runState === "succeeded" ? "09:42:11" : "--:--:--"}] {runState === "succeeded" ? "AI4MS_COMPLETED · exit 0" : "waiting…"}</span>}</div></div>}
          {tab === 4 && (runLocked ? <div className="locked-results-state"><span>∅</span><h3>尚无正式运行结果</h3><p>结果页只显示由获批代码和已签名数据生成的产物。探索性草稿不会混入正式结果。</p><button onClick={() => setTab(0)}>返回分析计划</button></div> : <div className="results-grid"><article><p className="eyebrow">Primary result</p><h3>AI 采用与创新质量呈正相关</h3><strong className="result-number">+8.4%</strong><span>95% CI [3.1%, 13.7%]</span><small>解释仍需 G4 人工审批</small></article><article><p className="eyebrow">Diagnostics</p><ul className="check-list"><li>✓ 共同趋势未拒绝</li><li>✓ 聚类标准误已应用</li><li>! 异质性结果待复核</li><li>○ 安慰剂检验待追加</li></ul></article><article><p className="eyebrow">Artifacts</p><ul className="artifact-list"><li>main_results.xlsx <span>已签名</span></li><li>event_study.png <span>已签名</span></li><li>analysis.log <span>原始</span></li><li>run_manifest.json <span>完整</span></li></ul></article></div>)}
        </section>
      </div>
    </div>
  );
}

function ApprovalsView({ project, submittedGates, onOpenGate, onOpenDetail }: { project: ResearchProject; submittedGates: Record<string, boolean>; onOpenGate: (gateId: string) => void; onOpenDetail: (detail: DetailPanel) => void }) {
  const cards = projectGateCards(project, submittedGates);
  const countByStatus = (status: string) => cards.filter((gate) => gate.status === status).length;
  return (
    <div className="approvals-view page-view">
      <header className="view-header"><div><p className="eyebrow">Human Approval Center</p><h1>人工审批中心</h1><p>批准的是确定版本和哈希。上游语义变化会使受影响的下游审批自动失效。</p></div><button className="outline-compact" onClick={() => onOpenDetail({ eyebrow: "Approval policy", title: "人工审批与失效规则", description: "智能体不能成为批准人。平台冻结 revision 和内容哈希，并在上游语义变化时使受影响的下游审批失效。", rows: [{ label: "G0", value: "选题价值与已有研究" }, { label: "G1", value: "理论与研究设计" }, { label: "G2", value: "数据、伦理与许可" }, { label: "G3", value: "分析计划与代码" }, { label: "G4", value: "结果与核心主张" }, { label: "G5", value: "成稿与发布" }], bullets: ["课题边界变化：G0–G5 失效", "主设计变化：G1–G5 失效", "主模型或 do-file 变化：G3–G5 失效", "纯排版变化：仅重查 G5 输出"] })}>查看审批规则</button></header>
      <div className="approval-summary"><div><strong>{countByStatus("approved")}</strong><span>已批准</span></div><div><strong>{countByStatus("review")}</strong><span>待审批</span></div><div><strong>{countByStatus("blocked")}</strong><span>前置阻塞</span></div><div><strong>0</strong><span>失效待复核</span></div></div>
      <div className="approval-layout">
        <section className="gate-list">{cards.map((gate) => <button className={`gate-card gate-${gate.status}`} onClick={() => onOpenGate(gate.id)} key={gate.id}><span className="gate-code">{gate.id}</span><div><h2>{gate.title}</h2><p>{gate.asset}</p><small>批准人：{gate.owner}</small></div><div className="gate-state"><StateBadge state={gate.status} /><small>{gate.time}</small></div><span className="gate-arrow">→</span></button>)}</section>
        <aside className="approval-rule-card"><p className="eyebrow">Four-eyes policy</p><h2>关键决定至少经过两种角色</h2><div className="reviewer-stack"><span>研</span><span>导</span><span>法</span></div><p>研究者提交，导师或 PI 与方法审核者分别确认价值和方法。Agent 永远不能成为批准人。</p><hr /><h3>上游变化会发生什么？</h3><ul><li>课题边界变化 → G0–G5 失效</li><li>主设计变化 → G1–G5 失效</li><li>主模型或 do-file 变化 → G3–G5 失效</li><li>纯排版变化 → 仅重查 G5 输出</li></ul></aside>
      </div>
    </div>
  );
}

function ApprovalModal({
  open,
  stageIndex,
  onClose,
  onConfirm,
}: {
  open: boolean;
  stageIndex: number;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const [checked, setChecked] = useState([true, true, false]);
  if (!open) return null;
  const stage = stages[stageIndex];
  const approvalCopy: Record<string, { owner: string; checks: string[]; note: string }> = {
    G0: { owner: "研究者 + 导师", checks: ["我已检查研究问题、研究边界与已有研究报告", "我已阅读相似课题、冲突证据与当前创新性限制", "我理解选题修改会使后续阶段资产与审批失效"], note: "请重点审核课题价值、研究边界、已有研究覆盖与可行性。" },
    G1: { owner: "导师 + 方法审核者", checks: ["我已检查研究问题、变量口径和主设计", "我已阅读冲突证据与当前覆盖限制", "我理解批准后再修改主设计会使下游审批失效"], note: "主设计、备选设计与识别边界已经人工复核，请重点审核关键假设与失败条件。" },
    G2: { owner: "数据负责人", checks: ["我已核验数据许可、隐私要求与运行位置", "我已检查变量字典、样本口径和数据血缘", "我理解数据口径变化会使 G2 之后的审批失效"], note: "请审核数据许可、关键变量口径、伦理限制与受控运行方案。" },
    G3: { owner: "方法审核者", checks: ["我已逐项核对 AnalysisPlan 与 do-file", "我已检查数据签名、软件版本、失败条件和输出路径", "我理解正式运行只能由人启动，智能体不能绕过冻结版本"], note: "请审核主次分析、代码哈希、诊断计划和正式运行边界。" },
    G4: { owner: "PI + 方法审核者", checks: ["我已审阅完整结果、失败检验与重跑记录", "我已检查每条核心主张的证据边和适用范围", "我理解证据不足的结论必须降级、改写或撤回"], note: "请审核核心结果、失败项、稳健性与主张强度是否匹配。" },
    G5: { owner: "通讯作者", checks: ["我已核对正文数字、图表、引用与结果资产", "我已检查限制披露、伦理说明和复现包", "我确认当前版本可以进入最终发布流程"], note: "请完成发布前的引用、数字、披露与复现包最终核验。" },
  };
  const copy = approvalCopy[stage.gate] ?? approvalCopy.G1;
  const allChecked = checked.every(Boolean);
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={(event) => event.currentTarget === event.target && onClose()}>
      <section className="approval-modal" role="dialog" aria-modal="true" aria-labelledby="approval-title">
        <button className="modal-close" onClick={onClose} aria-label="关闭审批窗口">×</button>
        <p className="eyebrow">Human approval · {stage.gate}</p>
        <h2 id="approval-title">提交“{stage.name}”审批</h2>
        <p>本次提交将冻结当前 revision。审批人会看到与上一批准版的差异、证据状态和未解决风险。</p>
        <div className="review-packet"><div><span>审批对象</span><strong>{stage.output}</strong></div><div><span>当前版本</span><strong>Revision 4 · 7c91…ae20</strong></div><div><span>默认批准人</span><strong>{copy.owner}</strong></div></div>
        <h3>提交前由研究者确认</h3>
        <div className="modal-checks">
          {copy.checks.map((item, index) => <label key={item}><input type="checkbox" checked={checked[index]} onChange={() => setChecked((current) => current.map((value, itemIndex) => itemIndex === index ? !value : value))} /><span>{item}</span></label>)}
        </div>
        <label className="reason-field"><span>提交说明</span><textarea key={stage.gate} defaultValue={copy.note} /></label>
        <div className="modal-actions"><button onClick={onClose}>继续修改</button><button className="primary-action" disabled={!allChecked} onClick={onConfirm}>确认提交人工审批</button></div>
      </section>
    </div>
  );
}

export default function Home() {
  const [view, setView] = useState<ViewKey>("journey");
  const [projects, setProjects] = useState<ResearchProject[]>(initialProjects);
  const [activeProjectId, setActiveProjectId] = useState(initialProjects[0].id);
  const [activeStage, setActiveStage] = useState(3);
  const [selectedDesign, setSelectedDesign] = useState("fe");
  const [question, setQuestion] = useState(initialProjects[0].question);
  const [deepStack, setDeepStack] = useState<DeepRoute[]>([]);
  const [stageDrafts, setStageDrafts] = useState<Record<string, StageDraft>>({});
  const [resolvedIssues, setResolvedIssues] = useState<Record<string, boolean>>({});
  const [suggestionStates, setSuggestionStates] = useState<Record<number, SuggestionState>>({});
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [submittedGates, setSubmittedGates] = useState<Record<string, boolean>>({});
  const [apiProjectIds, setApiProjectIds] = useState<Record<string, boolean>>({});
  const [apiMode, setApiMode] = useState<"loading" | "connected" | "fallback">("loading");
  const [apiBusy, setApiBusy] = useState(false);
  const [apiError, setApiError] = useState("");
  const [projectMenu, setProjectMenu] = useState(false);
  const [userMenu, setUserMenu] = useState(false);
  const [detail, setDetail] = useState<DetailPanel | null>(null);
  const [chatOpen, setChatOpen] = useState(false);
  const [chatAgent, setChatAgent] = useState(3);
  const [chatMessages, setChatMessages] = useState<Record<number, ChatMessage[]>>({});
  const [chatBusy, setChatBusy] = useState(false);
  const [toast, setToast] = useState("");
  const activeProject = projects.find((project) => project.id === activeProjectId) ?? projects[0];
  const activeStageData = stages[activeStage];
  const deepRoute = deepStack[deepStack.length - 1];
  const g1Submitted = Boolean(submittedGates[`${activeProject.id}:G1`]);
  const activeSubmittedCount = Object.keys(submittedGates).filter((key) => key.startsWith(`${activeProject.id}:`) && submittedGates[key]).length;
  const pageTitle = useMemo(() => navItems.find((item) => item.key === view)?.short ?? "研究旅程", [view]);

  useEffect(() => {
    let cancelled = false;
    async function loadApiProjects() {
      try {
        const summaries = await listApiProjects();
        if (cancelled) return;
        setApiMode("connected");
        setApiError("");
        setApiProjectIds(Object.fromEntries(summaries.map((item) => [item.project_id, true])));
        if (!summaries.length) return;
        const mapped = summaries.map((item) => mapApiProject(item));
        setProjects(mapped);
        setActiveProjectId(mapped[0].id);
        setActiveStage(mapped[0].stageIndex);
        setQuestion(mapped[0].question);
        try {
          const full = await getApiProject(mapped[0].id);
          if (cancelled) return;
          const hydrated = mapApiProject(full, mapped[0]);
          setProjects((current) => current.map((item) => item.id === hydrated.id ? hydrated : item));
          setStageDrafts((current) => ({ ...current, ...mapApiDrafts(full, hydrated) }));
          setActiveStage(hydrated.stageIndex);
          setQuestion(hydrated.question);
        } catch (error) {
          if (!cancelled) setApiError(readApiError(error));
        }
      } catch (error) {
        if (cancelled) return;
        setApiMode("fallback");
        setApiError(readApiError(error));
      }
    }
    void loadApiProjects();
    return () => { cancelled = true; };
  }, []);

  function readApiError(error: unknown) {
    if (error instanceof ApiError) return error.message;
    if (error instanceof Error) return error.message;
    return "无法连接 FastAPI 服务";
  }

  function showToast(message: string) {
    setToast(message);
    window.setTimeout(() => setToast(""), 2400);
  }
  function decideSuggestion(id: number, state: SuggestionState) {
    setSuggestionStates((current) => ({ ...current, [id]: state }));
    const verb = state === "accepted" ? "接受" : state === "modified" ? "转为人工修改" : state === "rejected" ? "拒绝" : "撤销处理";
    showToast(`已${verb}建议，决定记录已保存`);
  }
  function confirmApproval() {
    setApprovalOpen(false);
    if (/^G[0-5]$/.test(activeStageData.gate)) {
      setSubmittedGates((current) => ({ ...current, [`${activeProject.id}:${activeStageData.gate}`]: true }));
    }
    showToast(`${activeStageData.gate} 审批包已提交，AI 无法自行通过`);
  }
  function navigateView(nextView: ViewKey) {
    setView(nextView);
    setDeepStack([]);
    setProjectMenu(false);
    setUserMenu(false);
  }
  function openDeep(route: DeepRoute) {
    setDeepStack((current) => [...current, route]);
    setProjectMenu(false);
    setUserMenu(false);
  }
  function replaceDeep(route: DeepRoute) {
    setDeepStack([route]);
    setProjectMenu(false);
  }
  function backDeep() {
    setDeepStack((current) => current.slice(0, -1));
  }
  function selectStage(index: number) {
    setActiveStage(index);
    navigateView("journey");
  }
  function activateProject(projectId: string) {
    const project = projects.find((item) => item.id === projectId);
    if (!project) return;
    setActiveProjectId(project.id);
    setActiveStage(project.stageIndex);
    setQuestion(project.question);
    setSuggestionStates({});
    navigateView("journey");
    showToast(`已切换到项目：${project.name}`);
    if (apiProjectIds[project.id]) {
      setApiBusy(true);
      void getApiProject(project.id).then((full) => {
        const hydrated = mapApiProject(full, project);
        setProjects((current) => current.map((item) => item.id === hydrated.id ? hydrated : item));
        setStageDrafts((current) => ({ ...current, ...mapApiDrafts(full, hydrated) }));
        setActiveStage(hydrated.stageIndex);
        setQuestion(hydrated.question);
        setApiError("");
      }).catch((error) => setApiError(readApiError(error))).finally(() => setApiBusy(false));
    }
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
    setDeepStack([]);
    showToast("方法已加入研究设计草稿，请人工检查假设后保存");
  }
  function draftKey(stageIndex: number) {
    return `${activeProject.id}:${stageIndex}`;
  }
  function getDraft(stageIndex: number) {
    const key = draftKey(stageIndex);
    return stageDrafts[key] ?? createLocalStageDraft(stages[stageIndex], activeProject);
  }
  function saveDraft(stageIndex: number, draft: StageDraft, message: string) {
    const key = draftKey(stageIndex);
    const projectId = activeProject.id;
    setStageDrafts((current) => ({ ...current, [key]: draft }));
    showToast(message);
    if (apiProjectIds[projectId]) {
      setApiBusy(true);
      void saveApiStage(projectId, stages[stageIndex].key, { ...draft }, message).then((updated) => {
        const existing = projects.find((item) => item.id === projectId);
        const hydrated = mapApiProject(updated, existing);
        setProjects((current) => current.map((item) => item.id === projectId ? hydrated : item));
        setApiError("");
        showToast(`${stages[stageIndex].id} 已同步到 FastAPI revision`);
      }).catch((error) => {
        setApiError(readApiError(error));
        showToast("本地草稿已保存，后端同步待重试");
      }).finally(() => setApiBusy(false));
    }
  }
  function openStageDraft() {
    openDeep({ kind: "stage-draft", stageIndex: activeStage });
  }
  function runStageCheck() {
    openDeep({ kind: "stage-check", stageIndex: activeStage });
  }
  function completeProject(project: ResearchProject) {
    const exists = projects.some((item) => item.id === project.id);
    setProjects((current) => exists ? current.map((item) => item.id === project.id ? project : item) : [...current, project]);
    setActiveProjectId(project.id);
    setActiveStage(project.stageIndex);
    setQuestion(project.question);
    setView("journey");
    replaceDeep({ kind: "project-overview", projectId: project.id });
    showToast(exists ? "项目设置已保存" : "新项目已创建并加入项目列表");
    if (!exists && apiMode === "connected") {
      setApiBusy(true);
      void createApiProject(project.name, project.question).then((created) => {
        const hydrated = mapApiProject(created, { ...project, id: created.project_id });
        setProjects((current) => current.map((item) => item.id === project.id ? hydrated : item));
        setApiProjectIds((current) => ({ ...current, [created.project_id]: true }));
        setActiveProjectId(created.project_id);
        replaceDeep({ kind: "project-overview", projectId: created.project_id });
        setApiError("");
        showToast("新项目已创建并同步到 FastAPI");
      }).catch((error) => {
        setApiError(readApiError(error));
        showToast("项目已保存在前端，后端创建待重试");
      }).finally(() => setApiBusy(false));
    }
  }
  function applyIssueFix(stageIndex: number, issueId: string, value: string, resolve: boolean) {
    const draft = getDraft(stageIndex);
    const issue = createCheckIssues(stages[stageIndex], draft).find((item) => item.id === issueId);
    if (!issue) return;
    saveDraft(stageIndex, { ...draft, [issue.field]: value, savedAt: "刚刚由研究者整改" }, resolve ? "整改内容已写入草稿并标记完成" : "修改已保存到草稿，检查项仍保持待处理");
    if (resolve) setResolvedIssues((current) => ({ ...current, [`${draftKey(stageIndex)}:${issueId}`]: true }));
    backDeep();
  }

  function renderDeepPage() {
    if (!deepRoute) return null;
    if (deepRoute.kind === "stage-draft") {
      const stage = stages[deepRoute.stageIndex];
      return <StageDraftWorkspace stage={stage} project={activeProject} draft={getDraft(deepRoute.stageIndex)} onBack={backDeep} onSave={(draft, message) => saveDraft(deepRoute.stageIndex, draft, message)} onOpenCheck={() => openDeep({ kind: "stage-check", stageIndex: deepRoute.stageIndex })} onOpenDecisions={() => openDeep({ kind: "stage-decisions", stageIndex: deepRoute.stageIndex })} onOpenChat={() => openAgentChat(deepRoute.stageIndex)} onOpenEvidence={() => navigateView("evidence")} />;
    }
    if (deepRoute.kind === "stage-check") {
      const stage = stages[deepRoute.stageIndex];
      const issues = createCheckIssues(stage, getDraft(deepRoute.stageIndex));
      const resolved = Object.fromEntries(issues.map((issue) => [issue.id, Boolean(resolvedIssues[`${draftKey(deepRoute.stageIndex)}:${issue.id}`])]));
      return <ConsistencyCheckWorkspace stage={stage} project={activeProject} issues={issues} resolved={resolved} onBack={backDeep} onOpenIssue={(issueId) => openDeep({ kind: "stage-issue", stageIndex: deepRoute.stageIndex, issueId })} onOpenDraft={() => openDeep({ kind: "stage-draft", stageIndex: deepRoute.stageIndex })} onRunAgain={() => showToast("一致性检查已重新运行，结果已更新")} />;
    }
    if (deepRoute.kind === "stage-issue") {
      const stage = stages[deepRoute.stageIndex];
      const draft = getDraft(deepRoute.stageIndex);
      const issue = createCheckIssues(stage, draft).find((item) => item.id === deepRoute.issueId) ?? createCheckIssues(stage, draft)[0];
      return <IssueRemediationPage stage={stage} project={activeProject} issue={issue} resolved={Boolean(resolvedIssues[`${draftKey(deepRoute.stageIndex)}:${issue.id}`])} onBack={backDeep} onApply={(value, resolve) => applyIssueFix(deepRoute.stageIndex, issue.id, value, resolve)} />;
    }
    if (deepRoute.kind === "stage-decisions") {
      const stage = stages[deepRoute.stageIndex];
      const draft = getDraft(deepRoute.stageIndex);
      return <StageDecisionsWorkspace stage={stage} project={activeProject} draft={draft} onBack={backDeep} onSave={(decision) => saveDraft(deepRoute.stageIndex, { ...draft, decision, humanConfirmed: true, savedAt: "刚刚保存人工决定" }, "人工决定记录已保存")} onOpenChat={() => openAgentChat(deepRoute.stageIndex)} onOpenDraft={() => openDeep({ kind: "stage-draft", stageIndex: deepRoute.stageIndex })} />;
    }
    if (deepRoute.kind === "project-wizard") {
      const initial = deepRoute.projectId ? projects.find((project) => project.id === deepRoute.projectId) : undefined;
      return <ProjectWizard initial={initial} onBack={backDeep} onComplete={completeProject} />;
    }
    if (deepRoute.kind === "project-overview") {
      const project = projects.find((item) => item.id === deepRoute.projectId) ?? activeProject;
      return <ProjectOverviewPage project={project} onBack={backDeep} onStart={() => activateProject(project.id)} onEdit={() => openDeep({ kind: "project-wizard", projectId: project.id })} onNew={() => openDeep({ kind: "project-wizard" })} />;
    }
    if (deepRoute.kind === "evidence-record") {
      const record = libraryEvidence.find((item) => item.title === deepRoute.title) ?? libraryEvidence[0];
      return <EvidenceRecordPage record={record} onBack={backDeep} onSave={showToast} />;
    }
    if (deepRoute.kind === "method-record") {
      const method = methods.find((item) => item.id === deepRoute.methodId) ?? methods[0];
      return <MethodRecordPage method={method} onBack={backDeep} onAdd={() => addMethodToDesign(method.id)} onSave={showToast} />;
    }
    if (deepRoute.kind === "approval-gate") {
      const cards = projectGateCards(activeProject, submittedGates);
      const gate = cards.find((item) => item.id === deepRoute.gateId) ?? cards[0];
      const gateStage: Record<string, number> = { G0: 0, G1: 3, G2: 4, G3: 5, G4: 8, G5: 9 };
      return <ApprovalGatePage gate={gate} onBack={backDeep} onOpenAsset={() => openDeep({ kind: "asset-version", gateId: gate.id })} onSubmit={() => { setActiveStage(gateStage[gate.id] ?? activeStage); setApprovalOpen(true); }} />;
    }
    if (deepRoute.kind === "asset-version") {
      const cards = projectGateCards(activeProject, submittedGates);
      const gate = cards.find((item) => item.id === deepRoute.gateId) ?? cards[0];
      return <AssetVersionPage gate={gate} onBack={backDeep} onSave={showToast} />;
    }
    return null;
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={() => navigateView("journey")} aria-label="返回研究旅程"><span>AI</span>4MS</button>
        <nav className="topnav" aria-label="主导航">
          {navItems.map((item) => <button className={view === item.key ? "is-active" : ""} onClick={() => navigateView(item.key)} key={item.key}><span>{item.label}</span><small>{item.short}</small>{item.key === "approvals" && activeSubmittedCount > 0 && <i>{activeSubmittedCount}</i>}</button>)}
        </nav>
        <div className="topbar-actions">
          <div className="project-switcher-wrap">
            <button className="project-switcher" onClick={() => setProjectMenu((open) => !open)} aria-expanded={projectMenu}><span>当前项目</span><strong>{activeProject.name}</strong><b>⌄</b></button>
            {projectMenu && <div className="project-menu">
              <div className="project-menu-label">项目列表 · {projects.length}</div>
              {projects.map((project) => <button className={project.id === activeProject.id ? "is-current" : ""} onClick={() => activateProject(project.id)} key={project.id}><span>{project.icon}</span><div><strong>{project.name}</strong><small>S{project.stageIndex} · {stages[project.stageIndex].name}</small></div>{project.id === activeProject.id && <b>✓</b>}</button>)}
              <div className={`project-api-state state-${apiMode}`} title={apiError || "FastAPI connection ready"}><span /><div><strong>{apiBusy ? "正在同步" : apiMode === "connected" ? "FastAPI 已连接" : apiMode === "loading" ? "正在连接项目服务" : "前端演示数据模式"}</strong><small>{apiMode === "fallback" ? "恢复后端后可继续同步" : "项目与阶段 revision 保持一致"}</small></div></div>
              <hr />
              <button className="project-center-link" onClick={() => { setView("journey"); replaceDeep({ kind: "project-overview", projectId: activeProject.id }); }}>查看当前项目中心 <span>→</span></button>
              <button className="new-project" onClick={() => { setView("journey"); replaceDeep({ kind: "project-wizard" }); }}>＋ 创建新课题</button>
            </div>}
          </div>
          <button className="icon-button" onClick={() => { navigateView("approvals"); showToast("已打开人工审批中心"); }} aria-label="通知">●<i>2</i></button>
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

      <main className={`main-shell view-${view} ${deepRoute ? "view-deep" : ""}`}>
        {view === "journey" && !deepRoute && <StageRail activeIndex={activeStage} onSelect={selectStage} />}
        <div className="main-content">
          {deepRoute ? renderDeepPage() : <>
          {view === "journey" && (
            <>
              <header className="journey-header">
                <div><p className="eyebrow">Research Journey · {activeStageData.agent}</p><h1>{activeStageData.name}</h1><p><strong>{activeStage + 1}/10</strong> 阶段 <span>·</span> <b>{activeStageData.gate} {activeStage === 3 && g1Submitted ? "审批中" : "待确认"}</b></p></div>
                <ProgressNodes activeIndex={activeStage} />
              </header>
              <div className="journey-grid">
                <section className="stage-content">
                  <nav className="stage-action-strip" aria-label="阶段工作入口"><div><span>{activeStageData.id}</span><strong>阶段工作资产</strong><small>草稿、人工决定与检查结果均可继续修改</small></div><button onClick={openStageDraft}>打开当前草稿</button><button onClick={() => openDeep({ kind: "stage-decisions", stageIndex: activeStage })}>待决定项</button><button className="is-primary" onClick={runStageCheck}>一致性检查</button></nav>
                  {activeStage === 3
                    ? <DesignWorkspace question={question} setQuestion={setQuestion} selectedDesign={selectedDesign} setSelectedDesign={setSelectedDesign} onCompareMethods={() => setView("methods")} />
                    : <GenericStage stageIndex={activeStage} onOpenDraft={openStageDraft} onOpenDecision={() => openDeep({ kind: "stage-decisions", stageIndex: activeStage })} onRunCheck={runStageCheck} />}
                </section>
                <AgentPanel stageIndex={activeStage} suggestionStates={suggestionStates} onDecision={decideSuggestion} onSubmit={() => setApprovalOpen(true)} onOpenChat={() => openAgentChat()} />
              </div>
            </>
          )}
          {view === "evidence" && <EvidenceLibrary onOpenRecord={(title) => openDeep({ kind: "evidence-record", title })} onToast={showToast} />}
          {view === "methods" && <MethodsView onOpenDetail={setDetail} onOpenMethod={(methodId) => openDeep({ kind: "method-record", methodId })} onAdd={addMethodToDesign} />}
          {view === "runs" && <RunsView project={activeProject} onOpenDetail={setDetail} onOpenGate={(gateId) => openDeep({ kind: "approval-gate", gateId })} onToast={showToast} />}
          {view === "approvals" && <ApprovalsView project={activeProject} submittedGates={submittedGates} onOpenGate={(gateId) => openDeep({ kind: "approval-gate", gateId })} onOpenDetail={setDetail} />}
          </>}
        </div>
      </main>

      <ApprovalModal key={`${activeProject.id}:${activeStageData.gate}:${approvalOpen}`} open={approvalOpen} stageIndex={activeStage} onClose={() => setApprovalOpen(false)} onConfirm={confirmApproval} />
      <DetailModal detail={detail} onClose={() => setDetail(null)} />
      <AgentChatDrawer open={chatOpen} agentIndex={chatAgent} messages={chatMessages[chatAgent] ?? []} busy={chatBusy} onClose={() => setChatOpen(false)} onSelectAgent={setChatAgent} onSend={sendAgentMessage} onCapture={() => showToast("智能体回答已加入当前阶段记录草稿")} />
      {toast && <div className="toast" role="status"><span>✓</span>{toast}</div>}
      <div className="screen-reader-status" aria-live="polite">当前页面：{pageTitle}</div>
    </div>
  );
}
