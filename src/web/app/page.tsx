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
  FormulaRecordPage,
  IssueRemediationPage,
  MethodRecordWorkspace,
  ProjectOverviewPage,
  ProjectWizard,
  StageDecisionsWorkspace,
  StageDraftWorkspace,
  type DeepRoute,
  type FormulaRecord,
  type MethodRecord,
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
type ChatSyncTarget = "content" | "summary" | "evidenceNote" | "decision";
type ChatSyncMode = "append" | "replace";
type InterfaceTheme = "graphite" | "blueprint" | "paper";
type DiagnosticRule = {
  id: string;
  family: string;
  name: string;
  appliesTo: string;
  trigger: string;
  evidence: string;
  action: string;
  level: "阻塞" | "警告" | "记录";
  stage: "S4" | "S5" | "S6" | "S7";
  implementation: string;
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

const agentToolProfiles = [
  { tools: ["OpenAlex / Crossref 检索", "选题新颖性扫描", "研究可行性评分"], rule: "先检索同义词与反向问题；没有来源时不得宣称研究空白。" },
  { tools: ["布尔检索式生成", "主动学习筛选", "全文证据提取"], rule: "纳入/排除理由逐条保存；摘要级证据不得直接支撑核心结论。" },
  { tools: ["理论实体抽取", "因果图编辑器", "竞争解释生成"], rule: "每条机制至少连接一个可检验结果和一个竞争解释。" },
  { tools: ["方法适配检索", "Estimand 构造器", "识别假设审计"], rule: "只推荐候选设计；选择主设计、接受风险必须由人确认。" },
  { tools: ["数据目录连接器", "变量字典生成", "许可与隐私扫描"], rule: "下载、上传或连接受限数据前必须通过 G2；默认最小权限。" },
  { tools: ["公式库", "功效与样本量", "分析计划编译器"], rule: "公式、变量、诊断与代码任务逐项映射；冻结前允许人工修改。" },
  { tools: ["Stata do-file 生成", "静态安全检查", "机构 Runner"], rule: "仅 G3 批准的哈希可正式运行；智能体不能自行启动或安装依赖。" },
  { tools: ["稳健性矩阵", "安慰剂与敏感性", "结果差异比较"], rule: "失败项不得隐藏；新增检验标记为探索性并触发人工解释。" },
  { tools: ["主张—证据图", "机制/异质性审计", "反证检索"], rule: "每条主张绑定结果、来源、反证与适用边界后才能送审。" },
  { tools: ["结构化写作", "数字与引用核验", "交付包导出"], rule: "对话内容先同步为可编辑正文；发布前必须通过 G5 人工批准。" },
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

const methods: MethodRecord[] = [
  { id: "M01", name: "面板固定效应", family: "计量与面板", fit: 92, goal: "估计同一研究对象随时间变化与结果之间的关系。", estimand: "组内变化的条件平均关联 / 处理效应", dataShape: "个体 × 时间面板", formula: "Y_it = βD_it + γX_it + α_i + λ_t + ε_it", assumptions: ["组内有效变异充分", "无随时间变化的遗漏混杂", "聚类层级与处理分配一致"], diagnostics: ["组内/组间变异分解", "序列相关与聚类层级", "高维固定效应吸收检查"], failureRule: "核心变量缺少组内变异或关键时变混杂无法处理时，停止因果表述。", engine: "Stata · xtreg / reghdfe", stata: "xtset firm_id year\nxtreg y treatment controls i.year, fe vce(cluster firm_id)", python: "PanelOLS.from_formula('y ~ treatment + controls + EntityEffects + TimeEffects', data)", tags: ["panel", "fixed effects", "cluster SE"], source: "statsmodels / linearmodels" },
  { id: "M02", name: "双重差分", family: "因果识别", fit: 86, goal: "利用处理发生前后与对照组差异识别平均处理效应。", estimand: "ATT / group-time ATT", dataShape: "处理组与对照组的重复横截面或面板", formula: "Y_it = α_i + λ_t + β(Treat_i × Post_t) + γX_it + ε_it", assumptions: ["条件平行趋势", "无提前反应", "处理组间无干扰或溢出已建模"], diagnostics: ["处理前动态系数", "分期处理异质性", "安慰剂时点与组别"], failureRule: "平行趋势或处理时点有效性被实质性否定时，不报告主因果效应。", engine: "Stata · xtdidregress / csdid", stata: "xtdidregress (y controls) (treated), group(id) time(year) vce(cluster id)", python: "model.identify_effect(); model.estimate_effect(...); model.refute_estimate(...)", tags: ["ATT", "policy evaluation", "staggered adoption"], source: "DoWhy / linearmodels" },
  { id: "M03", name: "工具变量 / 2SLS", family: "因果识别", fit: 64, goal: "借助外生工具变量处理选择偏差、反向因果或测量误差。", estimand: "LATE（在单调性条件下）", dataShape: "横截面、面板或时间序列", formula: "D = πZ + γX + u;   Y = βD̂ + γX + ε", assumptions: ["工具相关性", "排除限制", "工具独立性与单调性"], diagnostics: ["第一阶段强度", "弱工具稳健推断", "过度识别与排除限制论证"], failureRule: "弱工具或排除限制缺乏可信论证时，工具变量结果只能作为探索性证据。", engine: "Stata · ivregress / ivreghdfe", stata: "ivregress 2sls y controls (treatment = instrument), vce(cluster id)\nestat firststage", python: "IV2SLS.from_formula('y ~ 1 + controls + [treatment ~ instrument]', data).fit()", tags: ["endogeneity", "LATE", "weak IV"], source: "linearmodels / DoWhy" },
  { id: "M04", name: "事件研究", family: "动态效应", fit: 80, goal: "展示事件发生前后的动态路径、提前反应与效应持续性。", estimand: "相对事件时间的动态效应 β_k", dataShape: "具有可信事件时点的面板", formula: "Y_it = α_i + λ_t + Σ_{k≠-1} β_k 1[t-T_i=k] + ε_it", assumptions: ["事件时点可靠", "基准期与窗口预先定义", "分期处理异质性得到处理"], diagnostics: ["处理前联合检验", "事件窗口敏感性", "队列加权与组成变化"], failureRule: "事件前出现系统性趋势且无法解释时，动态因果路径不得进入核心结论。", engine: "Stata · eventstudyinteract", stata: "eventstudyinteract y lead* lag*, absorb(id year) cohort(first_treat) control_cohort(never)", python: "# cohort-specific event-time effects with explicit reference period", tags: ["dynamic effect", "pre-trend", "cohort"], source: "DoWhy / causal inference practice" },
  { id: "M05", name: "断点回归 RDD", family: "准实验", fit: 45, goal: "利用阈值附近的处理跳跃识别局部平均处理效应。", estimand: "阈值处 LATE", dataShape: "连续运行变量 + 明确阈值", formula: "τ = lim_{x↓c}E[Y|X=x] − lim_{x↑c}E[Y|X=x]", assumptions: ["阈值附近潜在结果连续", "运行变量不可精确操纵", "带宽与多项式阶数合理"], diagnostics: ["密度操纵检验", "协变量连续性", "带宽与核函数敏感性"], failureRule: "运行变量存在操纵或阈值同时触发其他制度变化时，停止局部因果解释。", engine: "Stata · rdrobust", stata: "rdrobust y running, c(cutoff) covs(controls)\nrddensity running, c(cutoff)", python: "# local polynomial fit on each side of cutoff", tags: ["threshold", "local effect", "bandwidth"], source: "DoWhy / rdrobust ecosystem" },
  { id: "M06", name: "倾向得分与加权", family: "选择校正", fit: 58, goal: "在可观测混杂条件下构造可比样本或加权总体。", estimand: "ATE / ATT / ATC", dataShape: "处理、结果与处理前协变量", formula: "ATE = E[DY/e(X) − (1-D)Y/(1-e(X))]", assumptions: ["条件可忽略性", "正值性 / 重叠", "协变量均为处理前变量"], diagnostics: ["重叠与极端权重", "加权后平衡", "未观测混杂敏感性"], failureRule: "严重违反重叠或关键混杂不可观测时，不将匹配/加权解释为已消除选择偏差。", engine: "Stata · teffects", stata: "teffects ipwra (y controls) (treated controls), atet\ntebalance summarize", python: "CausalModel(...).identify_effect(); model.estimate_effect(...)", tags: ["propensity score", "IPW", "balance"], source: "DoWhy / CausalML" },
  { id: "M07", name: "合成控制", family: "政策评估", fit: 52, goal: "以加权对照单元构造处理单元未受处理时的反事实路径。", estimand: "处理单元的时间路径效应", dataShape: "少量处理单元 + 长期面板 + donor pool", formula: "Y^N_{1t} ≈ Σ_{j=2}^{J+1} w_jY_{jt},  w_j≥0, Σw_j=1", assumptions: ["加权对照可逼近处理前路径", "无干扰与预期效应", "donor pool 未受同类冲击"], diagnostics: ["处理前 RMSPE", "空间与时间安慰剂", "剔除高权重单元"], failureRule: "处理前拟合质量不足或 donor pool 被污染时，停止反事实效应解释。", engine: "Stata · synth / sdid", stata: "synth y predictors, trunit(1) trperiod(2022) nested", python: "# optimize non-negative donor weights subject to sum(w)=1", tags: ["synthetic control", "policy", "counterfactual"], source: "optimization + causal inference practice" },
  { id: "M08", name: "动态面板 GMM", family: "计量与面板", fit: 47, goal: "处理含滞后因变量的动态面板与潜在内生解释变量。", estimand: "动态短期与长期参数", dataShape: "大 N、小 T 面板", formula: "Y_it = ρY_{i,t-1} + βD_it + α_i + ε_it", assumptions: ["误差序列相关结构符合矩条件", "工具变量集合有效", "工具数量受控"], diagnostics: ["AR(1)/AR(2)", "Hansen/Sargan", "工具数量与折叠策略"], failureRule: "AR(2) 或工具有效性失败、工具膨胀时，不报告 GMM 作为主结果。", engine: "Stata · xtabond2", stata: "xtabond2 y L.y treatment controls i.year, gmm(L.y treatment, collapse) iv(controls i.year) twostep robust", python: "# dynamic panel GMM with explicitly bounded instrument set", tags: ["dynamic panel", "GMM", "instrument proliferation"], source: "linearmodels / econometrics practice" },
  { id: "M09", name: "中介、调节与 SEM", family: "机制模型", fit: 70, goal: "检验理论机制、间接效应、边界条件与测量结构。", estimand: "直接效应、间接效应与条件效应", dataShape: "横截面、面板或潜变量测量数据", formula: "M = aX + e_M;   Y = c′X + bM + d(X×W) + e_Y", assumptions: ["因果顺序由理论与设计支持", "中介—结果混杂得到处理", "测量模型可接受"], diagnostics: ["Bootstrap 间接效应", "测量信效度与拟合", "替代因果顺序"], failureRule: "仅凭横截面相关或拟合指标不得宣称机制得到因果验证。", engine: "Stata · sem / gsem", stata: "sem (mediator <- treatment controls) (y <- mediator treatment controls), vce(robust)\nnlcom _b[mediator:treatment]*_b[y:mediator]", python: "# structural equations with bootstrap confidence intervals", tags: ["mediation", "moderation", "latent variable"], source: "statsmodels / SEM practice" },
  { id: "M10", name: "线性 / 混合整数规划", family: "优化与决策", fit: 76, goal: "在资源、容量和逻辑约束下最小化成本或最大化收益。", estimand: "最优目标值与决策变量", dataShape: "集合、参数、决策变量、约束", formula: "min cᵀx  s.t. Ax ≥ b,  x_j∈ℝ/ℤ/{0,1}", assumptions: ["目标与约束可线性表达", "参数口径一致", "求解容差与最优性差距已定义"], diagnostics: ["可行性与冲突约束", "MIP gap / bound", "影子价格与情景敏感性"], failureRule: "模型不可行或关键约束缺失时，不得将求解器输出称为可执行最优方案。", engine: "Pyomo / PuLP / OR-Tools", stata: "* Stata 用于估计输入参数；优化由受控 solver job 执行", python: "model = ConcreteModel(); model.x = Var(...); model.obj = Objective(...); model.cons = Constraint(...)", tags: ["LP", "MILP", "resource allocation"], source: "Pyomo / PuLP / OR-Tools" },
  { id: "M11", name: "鲁棒优化", family: "优化与决策", fit: 68, goal: "在参数处于不确定集合内时寻找最坏情形下仍可接受的方案。", estimand: "最坏情形目标与鲁棒决策", dataShape: "确定性骨架 + 不确定集合", formula: "min_x max_{u∈U} f(x,u)  s.t. g(x,u)≤0, ∀u∈U", assumptions: ["不确定集合有业务依据", "保守度参数可解释", "鲁棒对应可求解"], diagnostics: ["价格—稳健性曲线", "集合半径敏感性", "样本外压力测试"], failureRule: "不确定集合任意设定或保守成本未披露时，不输出政策建议。", engine: "Pyomo + robust counterpart", stata: "* 参数分布与区间可由 Stata 估计后冻结入模型", python: "# construct uncertainty set U and solve robust counterpart", tags: ["uncertainty set", "min-max", "stress test"], source: "Pyomo optimization ecosystem" },
  { id: "M12", name: "随机规划", family: "优化与决策", fit: 62, goal: "在未来情景与概率不确定性下共同优化当前和递延决策。", estimand: "期望目标、CVaR 与情景决策", dataShape: "场景树或抽样情景", formula: "min cᵀx + E_ξ[Q(x,ξ)]", assumptions: ["情景生成覆盖关键风险", "概率或样本权重可信", "非预见性约束正确"], diagnostics: ["样本平均逼近稳定性", "EVPI / VSS", "尾部风险与场景删减"], failureRule: "场景覆盖不足或概率假设未审计时，最优方案只能作为情景演示。", engine: "Pyomo / mpi-sppy", stata: "* 用 Stata 估计情景概率与输入分布；求解在隔离 solver 运行", python: "# first-stage x, scenario recourse y[s], non-anticipativity constraints", tags: ["stochastic programming", "scenario", "CVaR"], source: "Pyomo / mpi-sppy" },
  { id: "M13", name: "网络流、路径与调度", family: "运营研究", fit: 73, goal: "求解路由、分配、最短路、最大流、排程和容量决策。", estimand: "可行路径/排程及其成本、服务与碳排", dataShape: "节点、边、订单、资源与时间窗", formula: "min Σ_{(i,j)} c_{ij}x_{ij}  s.t. flow balance & capacity", assumptions: ["网络拓扑与成本可信", "时间窗/容量约束完整", "离散决策尺度可求解"], diagnostics: ["可行性与约束冲突", "最优性界与运行时", "扰动、需求与边成本敏感性"], failureRule: "遗漏业务硬约束或仅给出不可部署路线时，不进入实施建议。", engine: "OR-Tools · CP-SAT / Routing", stata: "* Stata 负责需求估计与结果统计检验", python: "routing = pywrapcp.RoutingModel(...); routing.AddDimension(...); solution = routing.SolveWithParameters(params)", tags: ["routing", "scheduling", "network flow"], source: "Google OR-Tools" },
  { id: "M14", name: "数据包络分析 DEA", family: "效率评价", fit: 55, goal: "比较多个决策单元在多投入多产出条件下的相对效率。", estimand: "效率前沿距离与松弛变量", dataShape: "DMU × 投入/产出", formula: "max_u,v uᵀy_o / vᵀx_o  s.t. uᵀy_j/vᵀx_j≤1", assumptions: ["投入产出同质且方向合理", "样本量足以支撑维度", "异常值与环境变量已处理"], diagnostics: ["规模报酬设定", "Bootstrap 偏差", "异常值与超效率敏感性"], failureRule: "DMU 不可比或维度相对样本过高时，不发布效率排名。", engine: "DEA solver / linear programming", stata: "* dea / teradial（需在 ado manifest 中锁定）", python: "# solve one LP per DMU with Pyomo/PuLP", tags: ["efficiency", "frontier", "benchmarking"], source: "Pyomo / PuLP modeling pattern" },
  { id: "M15", name: "仿真与蒙特卡洛", family: "仿真与预测", fit: 66, goal: "评估随机系统、策略情景和估计量在重复试验下的表现。", estimand: "输出分布、风险指标或策略差异", dataShape: "输入分布 + 状态转移/业务规则", formula: "θ̂_MC = (1/R)Σ_{r=1}^R h(X_r)", assumptions: ["输入分布与依赖结构有依据", "预热期与重复次数足够", "随机种子与版本可复现"], diagnostics: ["蒙特卡洛标准误", "收敛与方差缩减", "输入分布敏感性"], failureRule: "输入分布未经校准或仿真误差未量化时，不将场景差异解释为稳健政策效应。", engine: "Stata simulate / Python", stata: "simulate b=_b[treatment], reps(1000) seed(20260721): myprogram", python: "rng = np.random.default_rng(seed); results = [simulate(rng) for _ in range(R)]", tags: ["simulation", "Monte Carlo", "scenario"], source: "statsmodels / scientific simulation practice" },
  { id: "M16", name: "双重机器学习 / 因果森林", family: "因果机器学习", fit: 57, goal: "在高维控制变量下估计平均或异质处理效应。", estimand: "ATE / CATE / policy value", dataShape: "大样本、高维特征、处理与结果", formula: "Y-ĝ(X) = θ(X)(T-m̂(X)) + ε", assumptions: ["可忽略性或有效工具变量", "交叉拟合与正则化条件", "重叠与样本量充分"], diagnostics: ["交叉拟合稳定性", "重叠与校准", "异质性多重比较与策略验证"], failureRule: "仅发现异质性模式而缺乏样本外验证时，不将 CATE 排名写成确定性分群结论。", engine: "EconML / CausalML", stata: "* Stata 输出经批准的分析样本；CATE 在锁定 Python 环境运行", python: "est = CausalForestDML(...); est.fit(Y, T, X=X, W=W); est.effect(X)", tags: ["DML", "CATE", "causal forest"], source: "EconML / CausalML" },
];

const formulas: FormulaRecord[] = [
  { id: "F01", title: "双向固定效应", family: "计量", methodId: "M01", formula: "Y_it = βD_it + γX_it + α_i + λ_t + ε_it", purpose: "吸收个体不变异质性与共同时间冲击。", symbols: [{ symbol: "Y_it", meaning: "个体 i 在 t 期的结果变量" }, { symbol: "D_it", meaning: "核心解释或处理变量" }, { symbol: "X_it", meaning: "预先定义的时变控制变量" }, { symbol: "α_i", meaning: "个体固定效应" }, { symbol: "λ_t", meaning: "时间固定效应" }], assumptions: ["严格外生或可辩护的条件外生", "组内变异充分"], diagnostics: ["组内变异", "聚类标准误", "残差结构"], stata: "xtreg y d controls i.year, fe vce(cluster id)", source: "linearmodels / statsmodels" },
  { id: "F02", title: "双重差分 ATT", family: "因果", methodId: "M02", formula: "Y_it = α_i + λ_t + β(Treat_i×Post_t) + ε_it", purpose: "比较处理与对照组在处理前后的变化差异。", symbols: [{ symbol: "Treat_i", meaning: "处理组指示变量" }, { symbol: "Post_t", meaning: "处理后时期指示变量" }, { symbol: "β", meaning: "目标 ATT 参数" }], assumptions: ["平行趋势", "无提前反应", "无干扰"], diagnostics: ["事件研究前趋势", "组时异质性", "安慰剂"], stata: "xtdidregress (y controls) (treated), group(id) time(year)", source: "DoWhy causal workflow" },
  { id: "F03", title: "事件时间动态系数", family: "因果", methodId: "M04", formula: "Y_it = α_i + λ_t + Σ_{k≠-1}β_k·1[t-T_i=k] + ε_it", purpose: "估计处理前后各相对时期的动态效应。", symbols: [{ symbol: "T_i", meaning: "个体首次处理时点" }, { symbol: "k", meaning: "相对事件时间" }, { symbol: "β_k", meaning: "相对基准期的动态效应" }], assumptions: ["处理时点可靠", "基准期固定", "队列异质性已处理"], diagnostics: ["处理前联合检验", "窗口敏感性", "队列权重"], stata: "eventstudyinteract y lead* lag*, absorb(id year) cohort(first_treat)", source: "event-study practice" },
  { id: "F04", title: "两阶段最小二乘", family: "因果", methodId: "M03", formula: "D=πZ+γX+u;  Y=βD̂+γX+ε", purpose: "用工具变量诱导的外生处理变异估计局部效应。", symbols: [{ symbol: "Z", meaning: "工具变量" }, { symbol: "D̂", meaning: "第一阶段预测处理" }, { symbol: "β", meaning: "局部平均处理效应" }], assumptions: ["相关性", "排除限制", "独立性与单调性"], diagnostics: ["第一阶段 F", "弱工具稳健区间", "过度识别"], stata: "ivregress 2sls y controls (d=z), vce(cluster id)", source: "linearmodels / DoWhy" },
  { id: "F05", title: "局部断点效应", family: "准实验", methodId: "M05", formula: "τ = lim_{x↓c}E[Y|X=x] − lim_{x↑c}E[Y|X=x]", purpose: "估计阈值两侧结果函数的局部跳跃。", symbols: [{ symbol: "X", meaning: "运行变量" }, { symbol: "c", meaning: "处理阈值" }, { symbol: "τ", meaning: "阈值处局部处理效应" }], assumptions: ["潜在结果连续", "不可精确操纵"], diagnostics: ["密度检验", "协变量连续", "带宽敏感性"], stata: "rdrobust y running, c(cutoff)", source: "RDD practice" },
  { id: "F06", title: "IPW 加权均值", family: "选择校正", methodId: "M06", formula: "ATE = E[DY/e(X) − (1-D)Y/(1-e(X))]", purpose: "以处理概率倒数重构目标总体。", symbols: [{ symbol: "e(X)", meaning: "倾向得分 P(D=1|X)" }, { symbol: "D", meaning: "处理状态" }, { symbol: "Y", meaning: "观测结果" }], assumptions: ["条件可忽略性", "正值性"], diagnostics: ["平衡", "极端权重", "有效样本量"], stata: "teffects ipwra (y controls) (d controls), ate", source: "DoWhy / CausalML" },
  { id: "F07", title: "中介间接效应", family: "机制", methodId: "M09", formula: "Indirect = a×b;  Total = c′ + a×b", purpose: "分解处理经中介路径传递的间接效应。", symbols: [{ symbol: "a", meaning: "处理对中介的效应" }, { symbol: "b", meaning: "控制处理后中介对结果的效应" }, { symbol: "c′", meaning: "直接效应" }], assumptions: ["因果顺序可信", "无中介—结果未测混杂"], diagnostics: ["Bootstrap 区间", "替代顺序", "测量误差"], stata: "sem (m <- x controls) (y <- m x controls)\nnlcom _b[m:x]*_b[y:m]", source: "SEM / mediation practice" },
  { id: "F08", title: "线性 / 混合整数规划", family: "优化", methodId: "M10", formula: "min cᵀx  s.t. Ax≥b, x_j∈ℝ/ℤ/{0,1}", purpose: "将资源配置、选择与逻辑约束表达为可求解模型。", symbols: [{ symbol: "x", meaning: "决策变量向量" }, { symbol: "c", meaning: "目标系数" }, { symbol: "A,b", meaning: "约束矩阵与边界" }], assumptions: ["线性表达充分", "参数与单位一致"], diagnostics: ["可行性", "最优性 gap", "敏感性"], stata: "* 估计参数后导出 solver manifest", source: "Pyomo / PuLP / OR-Tools" },
  { id: "F09", title: "鲁棒最坏情形", family: "优化", methodId: "M11", formula: "min_x max_{u∈U} f(x,u)", purpose: "在不确定集合内控制最坏情形损失。", symbols: [{ symbol: "x", meaning: "鲁棒决策" }, { symbol: "u", meaning: "不确定参数" }, { symbol: "U", meaning: "经审计的不确定集合" }], assumptions: ["不确定集合有经验依据", "鲁棒对应可求解"], diagnostics: ["保守成本", "集合半径", "压力测试"], stata: "* estimate uncertainty bounds; freeze into solver input", source: "Pyomo ecosystem" },
  { id: "F10", title: "两阶段随机规划", family: "优化", methodId: "M12", formula: "min cᵀx + E_ξ[Q(x,ξ)]", purpose: "平衡当前决策与未来情景中的补救成本。", symbols: [{ symbol: "x", meaning: "第一阶段决策" }, { symbol: "ξ", meaning: "随机情景" }, { symbol: "Q", meaning: "情景补救价值函数" }], assumptions: ["情景覆盖充分", "非预见性约束正确"], diagnostics: ["VSS/EVPI", "场景稳定性", "尾部风险"], stata: "* scenario probability estimation only", source: "Pyomo / mpi-sppy" },
  { id: "F11", title: "网络流平衡", family: "运营研究", methodId: "M13", formula: "Σ_j x_{ji} − Σ_j x_{ij} = b_i", purpose: "保证每个节点的流入、流出与供需守恒。", symbols: [{ symbol: "x_ij", meaning: "边 i→j 上的流量" }, { symbol: "b_i", meaning: "节点供给或需求" }], assumptions: ["拓扑完整", "容量与单位一致"], diagnostics: ["不可行约束", "容量瓶颈", "边成本扰动"], stata: "* validate demand and post-solution outcomes", source: "Google OR-Tools" },
  { id: "F12", title: "双重机器学习残差式", family: "因果机器学习", methodId: "M16", formula: "Y-ĝ(X) = θ(X)(T-m̂(X)) + ε", purpose: "用正交化与交叉拟合降低高维干扰估计偏差。", symbols: [{ symbol: "ĝ(X)", meaning: "结果条件均值模型" }, { symbol: "m̂(X)", meaning: "处理条件均值模型" }, { symbol: "θ(X)", meaning: "条件处理效应" }], assumptions: ["混杂可由 X 控制", "交叉拟合", "重叠"], diagnostics: ["校准", "样本外稳定性", "策略价值"], stata: "* export approved analytic sample to locked Python runner", source: "EconML / CausalML" },
];

const diagnosticRules: DiagnosticRule[] = [
  { id: "D01", family: "数据质量", name: "关键字段缺失机制", appliesTo: "全部研究设计", trigger: "因变量、处理变量、时间或主键存在缺失", evidence: "按变量和组别报告缺失率、缺失模式及处理前后样本变化", action: "关键字段无法恢复且缺失具有系统性时，阻塞主分析并修改数据合同。", level: "阻塞", stage: "S4", implementation: "misstable summarize; misstable patterns" },
  { id: "D02", family: "数据质量", name: "主键唯一性与重复记录", appliesTo: "面板、事件与交易数据", trigger: "进入任何合并、面板设定或聚合步骤前", evidence: "报告主键重复数、重复来源和人工处理规则", action: "主键不唯一且无法解释时停止合并与估计。", level: "阻塞", stage: "S4", implementation: "isid firm_id year; duplicates report firm_id year" },
  { id: "D03", family: "数据质量", name: "单位、币种与时间口径", appliesTo: "多源数据与跨期比较", trigger: "变量来自不同数据库、年度或币种", evidence: "单位表、平减指数、汇率来源、时区和会计期间映射", action: "口径未统一时不得生成跨源指标。", level: "阻塞", stage: "S4", implementation: "assert unit_code != \"\"; codebook fiscal_year" },
  { id: "D04", family: "数据质量", name: "异常值与影响点", appliesTo: "回归、预测与效率评价", trigger: "连续变量进入估计或求解器参数", evidence: "分位数、箱线范围、影响统计与处理前后结果", action: "保留原始结果；缩尾或删除必须作为有依据的替代规格。", level: "警告", stage: "S4", implementation: "summarize, detail; predict cooksd, cooksd" },
  { id: "D05", family: "统计与面板", name: "组内有效变异", appliesTo: "固定效应与动态面板", trigger: "核心解释变量由个体固定效应识别", evidence: "组内/组间标准差、变化单位数及处理转换次数", action: "组内变异不足时停止将固定效应系数解释为主要证据。", level: "阻塞", stage: "S5", implementation: "xtsum treatment outcome" },
  { id: "D06", family: "统计与面板", name: "异方差与稳健标准误", appliesTo: "OLS、GLM 与面板模型", trigger: "误差方差可能随规模、组别或时间变化", evidence: "残差图、BP/White 检验及稳健标准误对照", action: "推断必须使用与数据生成结构匹配的稳健或聚类标准误。", level: "警告", stage: "S6", implementation: "estat hettest; regress y x, vce(robust)" },
  { id: "D07", family: "统计与面板", name: "聚类层级一致性", appliesTo: "面板、政策与实验数据", trigger: "处理在组、地区、机构或时间层级分配", evidence: "处理分配层级、聚类数和替代聚类结果", action: "聚类层级低于处理分配层级时阻塞显著性结论。", level: "阻塞", stage: "S5", implementation: "reghdfe y d x, absorb(id year) vce(cluster policy_cluster)" },
  { id: "D08", family: "统计与面板", name: "序列相关", appliesTo: "面板与时间序列回归", trigger: "同一对象跨期重复观测", evidence: "Wooldridge/残差自相关检验与修正规格", action: "存在序列相关时使用适当聚类、动态项或误差结构。", level: "警告", stage: "S6", implementation: "xtserial y x" },
  { id: "D09", family: "统计与面板", name: "横截面相关", appliesTo: "宏观、行业与大面板", trigger: "对象同时暴露于共同冲击", evidence: "Pesaran CD 或共同因子诊断", action: "显著相关时增加共同因子、时间效应或替代标准误。", level: "警告", stage: "S6", implementation: "xtcsd, pesaran abs" },
  { id: "D10", family: "统计与面板", name: "多重共线性", appliesTo: "回归、SEM 与预测模型", trigger: "多个高度相关构念或交互项同时进入模型", evidence: "VIF、条件数、相关矩阵与变量定义", action: "共线性影响解释时重构变量或降级单个系数结论。", level: "警告", stage: "S5", implementation: "estat vif" },
  { id: "D11", family: "统计与面板", name: "固定效应吸收检查", appliesTo: "高维固定效应模型", trigger: "核心变量可能在固定效应内不变化", evidence: "被吸收变量、有效样本与自由度变化", action: "核心变量被吸收后不得更换模型以追求可报告系数。", level: "阻塞", stage: "S5", implementation: "reghdfe y d x, absorb(id year) verbose(1)" },
  { id: "D12", family: "因果识别", name: "DID 平行趋势", appliesTo: "双重差分与事件研究", trigger: "处理前至少存在两个可比时期", evidence: "处理前动态系数、联合检验、图形与置信区间", action: "实质性预趋势无法解释时停止核心 ATT 表述。", level: "阻塞", stage: "S7", implementation: "estat ptrends; eventstudyinteract y lead* lag*" },
  { id: "D13", family: "因果识别", name: "提前反应与预期效应", appliesTo: "政策、采用与事件研究", trigger: "主体可能在正式处理前改变行为", evidence: "提前期系数、制度时间线和替代处理时点", action: "发现提前反应时重新定义处理窗口与 estimand。", level: "阻塞", stage: "S7", implementation: "testparm lead*" },
  { id: "D14", family: "因果识别", name: "分期处理异质性", appliesTo: "错位实施 DID", trigger: "不同组在不同时间首次受处理", evidence: "组时 ATT、队列权重及传统 TWFE 对照", action: "禁止仅用传统 TWFE 作为主结果。", level: "阻塞", stage: "S5", implementation: "csdid y x, ivar(id) time(year) gvar(first_treat)" },
  { id: "D15", family: "因果识别", name: "干扰与空间溢出", appliesTo: "政策、网络与平台研究", trigger: "对照组可能被邻近或网络处理影响", evidence: "暴露映射、距离/网络窗口和排除样本结果", action: "存在溢出时改写 estimand，不再称为无处理对照。", level: "阻塞", stage: "S5", implementation: "generate exposure = ...; reghdfe y treated exposure x, ..." },
  { id: "D16", family: "因果识别", name: "工具变量相关性", appliesTo: "IV / 2SLS", trigger: "工具变量进入第一阶段", evidence: "第一阶段系数、partial R²、F 或 Kleibergen–Paap 统计量", action: "弱工具时使用弱工具稳健推断或放弃 IV 主设计。", level: "阻塞", stage: "S6", implementation: "ivreg2 y x (d=z), first weakiv" },
  { id: "D17", family: "因果识别", name: "排除限制论证", appliesTo: "IV / 2SLS", trigger: "工具可能通过处理之外路径影响结果", evidence: "机制图、制度依据、负向结果与敏感性边界", action: "没有可信论证时仅报告相关性或探索性 IV。", level: "阻塞", stage: "S5", implementation: "* narrative evidence + negative-control specification" },
  { id: "D18", family: "因果识别", name: "过度识别与工具一致性", appliesTo: "多工具 IV / GMM", trigger: "排除工具数量超过内生变量数量", evidence: "Hansen/Sargan、逐个工具结果与工具来源", action: "检验失败或工具结论分裂时降级主张并调查工具。", level: "警告", stage: "S7", implementation: "estat overid" },
  { id: "D19", family: "准实验与加权", name: "RDD 密度操纵", appliesTo: "断点回归", trigger: "处理由运行变量阈值决定", evidence: "阈值附近密度图与 McCrary/rddensity 检验", action: "存在精确操纵时停止局部随机或连续性识别。", level: "阻塞", stage: "S6", implementation: "rddensity running, c(cutoff)" },
  { id: "D20", family: "准实验与加权", name: "RDD 协变量连续性", appliesTo: "断点回归", trigger: "处理前协变量在阈值处应连续", evidence: "每个预定协变量的跳跃估计与多重检验说明", action: "系统性不连续时调查制度共变并停止主解释。", level: "阻塞", stage: "S7", implementation: "rdrobust covariate running, c(cutoff)" },
  { id: "D21", family: "准实验与加权", name: "RDD 带宽与函数形式", appliesTo: "断点回归", trigger: "局部多项式估计完成后", evidence: "最优带宽、上下带宽、核函数与 donut 规格", action: "结果只在单一任意规格成立时标记为不稳健。", level: "警告", stage: "S7", implementation: "rdrobust y running, c(cutoff) all" },
  { id: "D22", family: "准实验与加权", name: "倾向得分重叠", appliesTo: "匹配、IPW、DML", trigger: "基于可观测协变量调整选择", evidence: "组别得分分布、共同支持范围与截尾样本", action: "严重无重叠时更改目标总体，不做外推 ATE。", level: "阻塞", stage: "S6", implementation: "teffects overlap" },
  { id: "D23", family: "准实验与加权", name: "加权后协变量平衡", appliesTo: "匹配、IPW、加权回归", trigger: "权重或匹配样本生成后", evidence: "标准化差异、方差比和平衡图", action: "关键协变量仍不平衡时重新设定处理模型。", level: "阻塞", stage: "S6", implementation: "tebalance summarize; tebalance density" },
  { id: "D24", family: "准实验与加权", name: "极端权重与有效样本量", appliesTo: "IPW、熵平衡与调查权重", trigger: "个别观测可能获得过大权重", evidence: "权重分位数、最大值、截尾规则和 ESS", action: "ESS 过低时改变目标总体或使用更稳定估计器。", level: "警告", stage: "S7", implementation: "summarize weight, detail; scalar ESS=(sum_w^2)/sum_w2" },
  { id: "D25", family: "准实验与加权", name: "合成控制处理前拟合", appliesTo: "合成控制", trigger: "供体权重求解完成后", evidence: "处理前 RMSPE、路径图与预测变量平衡", action: "处理前拟合差时不得解释处理后差距为反事实效应。", level: "阻塞", stage: "S6", implementation: "synth y predictors, trunit() trperiod()" },
  { id: "D26", family: "准实验与加权", name: "合成控制供体敏感性", appliesTo: "合成控制", trigger: "少数供体权重集中或可能受溢出", evidence: "leave-one-out、空间安慰剂和 RMSPE 比率", action: "结论依赖单一不合格供体时撤回主结果。", level: "警告", stage: "S7", implementation: "* loop donor exclusions and placebo units" },
  { id: "D27", family: "动态模型", name: "GMM 二阶序列相关", appliesTo: "差分/系统 GMM", trigger: "动态面板 GMM 估计后", evidence: "Arellano–Bond AR(1) 与 AR(2) 检验", action: "AR(2) 显著时矩条件无效，阻塞 GMM 主结果。", level: "阻塞", stage: "S6", implementation: "estat abond; xtabond2 ..., robust" },
  { id: "D28", family: "动态模型", name: "GMM 工具膨胀", appliesTo: "差分/系统 GMM", trigger: "工具数量接近或超过组数", evidence: "工具数量、滞后范围、collapse 前后结果", action: "压缩工具集合；不可用高 Hansen p 值掩盖膨胀。", level: "阻塞", stage: "S6", implementation: "xtabond2 ..., gmm(..., lag(2 3) collapse)" },
  { id: "D29", family: "机制与测量", name: "测量信度与聚合效度", appliesTo: "SEM、量表与潜变量", trigger: "构念由多个测量题项形成", evidence: "α/ω、因子载荷、AVE 与题项处理记录", action: "测量不成立时停止解释结构路径。", level: "阻塞", stage: "S5", implementation: "sem ...; estat framework, fitted" },
  { id: "D30", family: "机制与测量", name: "区分效度与竞争模型", appliesTo: "SEM、PLS-SEM", trigger: "多个理论构念高度相关", evidence: "HTMT/Fornell–Larcker、交叉载荷与竞争模型", action: "构念不可区分时合并、重定义或撤回差异化机制。", level: "阻塞", stage: "S7", implementation: "* compare constrained and unconstrained measurement models" },
  { id: "D31", family: "机制与测量", name: "中介因果顺序", appliesTo: "中介与机制检验", trigger: "间接效应被表述为因果机制", evidence: "时间顺序、DAG、中介—结果混杂和替代顺序", action: "横截面或顺序不明时只表述为机制一致性证据。", level: "阻塞", stage: "S5", implementation: "sem (m <- x c) (y <- m x c); bootstrap" },
  { id: "D32", family: "优化与运营", name: "可行性与冲突约束", appliesTo: "LP、MILP、路由与调度", trigger: "求解器返回 infeasible 或无解", evidence: "IIS/冲突约束、单位检查和最小可复现实例", action: "不可行时禁止报告最优值，先修复模型或业务规则。", level: "阻塞", stage: "S6", implementation: "solver IIS / conflict refiner; validate units" },
  { id: "D33", family: "优化与运营", name: "最优性差距与运行时", appliesTo: "MILP、CP-SAT 与组合优化", trigger: "在时间或资源上限内停止求解", evidence: "incumbent、bound、MIP gap、运行时与硬件环境", action: "未证明最优时必须报告为当前最好可行解。", level: "警告", stage: "S6", implementation: "record objective, best_bound, mip_gap, wall_time" },
  { id: "D34", family: "优化与运营", name: "鲁棒半径与保守成本", appliesTo: "鲁棒与分布鲁棒优化", trigger: "不确定集合或半径由研究者设定", evidence: "半径来源、价格—稳健性曲线和样本外违约率", action: "半径任意或保守成本未披露时不输出政策建议。", level: "阻塞", stage: "S7", implementation: "solve over epsilon grid; out-of-sample stress test" },
  { id: "D35", family: "优化与运营", name: "随机情景稳定性", appliesTo: "随机规划与仿真优化", trigger: "情景抽样、删减或概率设定完成后", evidence: "不同种子、样本量、VSS/EVPI 与尾部风险", action: "方案随情景剧烈变化时标记不稳定并增加样本外验证。", level: "警告", stage: "S7", implementation: "repeat SAA; report VSS, EVPI, CVaR" },
  { id: "D36", family: "因果机器学习", name: "交叉拟合、校准与策略外推", appliesTo: "DML、因果森林与 CATE", trigger: "报告平均或异质处理效应前", evidence: "重叠、nuisance 误差、校准、honest split 与 holdout 策略价值", action: "未通过样本外验证时不得把 CATE 排名转成确定性分群政策。", level: "阻塞", stage: "S7", implementation: "cross-fit folds; calibration; policy_value on holdout" },
];

const interfaceThemes: { id: InterfaceTheme; name: string; description: string; colors: string[]; note: string }[] = [
  { id: "graphite", name: "石墨极简", description: "黑白灰、低阴影、最克制的 Apple 工作台。", colors: ["#101114", "#f5f5f7", "#d2d2d7"], note: "适合长时间阅读与正式汇报" },
  { id: "blueprint", name: "冷蓝研究", description: "低饱和蓝灰、清晰状态色、轻量层次。", colors: ["#315f87", "#eef3f7", "#aebdca"], note: "适合证据、方法和运行监控" },
  { id: "paper", name: "论文纸张", description: "暖白纸色、深墨文字、学术编辑感。", colors: ["#2f2d29", "#f5f1e8", "#b8aa91"], note: "适合写作、评审和打印阅读" },
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
      syncHistory: Array.isArray(content.syncHistory) ? content.syncHistory.filter((item): item is string => typeof item === "string") : base.syncHistory,
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

function PreferencesModal({
  open,
  value,
  onSelect,
  onClose,
}: {
  open: boolean;
  value: InterfaceTheme;
  onSelect: (theme: InterfaceTheme) => void;
  onClose: () => void;
}) {
  if (!open) return null;
  const selectedTheme = interfaceThemes.find((theme) => theme.id === value) ?? interfaceThemes[0];
  return (
    <div className="modal-backdrop preferences-backdrop" role="presentation" onMouseDown={(event) => event.currentTarget === event.target && onClose()}>
      <section className="preferences-modal" role="dialog" aria-modal="true" aria-labelledby="preferences-title">
        <header className="detail-modal-header">
          <div><p className="eyebrow">Appearance preferences</p><h2 id="preferences-title">界面偏好</h2></div>
          <button className="modal-close" onClick={onClose} aria-label="关闭界面偏好">×</button>
        </header>
        <p className="detail-lede">选择最适合当前工作方式的颜色与排版。设置只保存在此浏览器，不会影响研究内容或协作者。</p>
        <div className="theme-choice-grid" role="radiogroup" aria-label="界面风格">
          {interfaceThemes.map((theme) => (
            <button
              type="button"
              role="radio"
              aria-checked={theme.id === value}
              className={`theme-choice ${theme.id === value ? "is-selected" : ""}`}
              onClick={() => onSelect(theme.id)}
              key={theme.id}
            >
              <span className="theme-choice-check">{theme.id === value ? "✓" : ""}</span>
              <span className="theme-swatches" aria-hidden="true">{theme.colors.map((color) => <i style={{ background: color }} key={color} />)}</span>
              <strong>{theme.name}</strong>
              <small>{theme.description}</small>
              <em>{theme.note}</em>
            </button>
          ))}
        </div>
        <footer className="preferences-actions"><span>当前：{selectedTheme.name} · 已自动保存</span><button className="primary-action" onClick={onClose}>完成</button></footer>
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
  onCapture: (text: string, target: ChatSyncTarget, mode: ChatSyncMode) => void;
}) {
  const [draft, setDraft] = useState("");
  const [syncCandidate, setSyncCandidate] = useState("");
  const [syncTarget, setSyncTarget] = useState<ChatSyncTarget>("content");
  const [syncMode, setSyncMode] = useState<ChatSyncMode>("append");
  const [syncConfirmed, setSyncConfirmed] = useState(false);
  if (!open) return null;
  const stage = stages[agentIndex];
  const profile = agentProfiles[agentIndex];
  const toolProfile = agentToolProfiles[agentIndex];
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
              <button className={index === agentIndex ? "is-active" : ""} onClick={() => { onSelectAgent(index); setSyncCandidate(""); setSyncConfirmed(false); }} key={item.id}>
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
                  {message.role === "assistant" && <button className="message-capture" onClick={() => { setSyncCandidate(message.text); setSyncTarget("content"); setSyncMode("append"); setSyncConfirmed(false); }}>同步到交付正文</button>}
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
            <div className="agent-tool-mini"><strong>本阶段可调用工具</strong>{toolProfile.tools.map((tool) => <span key={tool}>{tool}</span>)}<p>{toolProfile.rule}</p></div>
            {syncCandidate && <div className="chat-sync-panel"><div className="chat-sync-title"><span>SYNC</span><strong>同步到阶段资产</strong></div><p>同步前可选择目标和写入方式；确认后仍可在草稿中人工修改。</p><label><span>目标位置</span><select value={syncTarget} onChange={(event) => setSyncTarget(event.target.value as ChatSyncTarget)}><option value="content">交付正文</option><option value="summary">阶段摘要</option><option value="evidenceNote">证据说明</option><option value="decision">决定记录草稿</option></select></label><label><span>写入方式</span><select value={syncMode} onChange={(event) => setSyncMode(event.target.value as ChatSyncMode)}><option value="append">追加并保留原文</option><option value="replace">替换目标内容</option></select></label><div className="sync-preview">{syncCandidate}</div><div className="chat-sync-actions"><button onClick={() => setSyncCandidate("")}>取消</button><button className="primary-action" disabled={syncConfirmed} onClick={() => { onCapture(syncCandidate, syncTarget, syncMode); setSyncConfirmed(true); }}>{syncConfirmed ? "已同步" : "人工确认并同步"}</button></div>{syncConfirmed && <small>已生成同步记录，可到“当前草稿”继续修改。</small>}</div>}
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

function MethodsView({ onOpenMethod, onOpenFormula, onAdd, onToast }: { onOpenMethod: (methodId: string) => void; onOpenFormula: (formulaId: string) => void; onAdd: (methodId: string) => void; onToast: (message: string) => void }) {
  const [tab, setTab] = useState<"methods" | "formulas" | "diagnostics" | "design">("methods");
  const [selected, setSelected] = useState(methods[0].id);
  const [query, setQuery] = useState("");
  const [family, setFamily] = useState("全部");
  const [compare, setCompare] = useState<string[]>(["M01", "M02"]);
  const [expandedDiagnostic, setExpandedDiagnostic] = useState<string | null>("D01");
  const families = ["全部", ...Array.from(new Set((tab === "diagnostics" ? diagnosticRules.map((rule) => rule.family) : methods.map((method) => method.family))))];
  const filteredMethods = methods.filter((method) => (family === "全部" || method.family === family) && `${method.name} ${method.goal} ${method.tags.join(" ")}`.toLowerCase().includes(query.trim().toLowerCase()));
  const filteredFormulas = formulas.filter((formula) => (family === "全部" || formula.family.includes(family) || methods.find((method) => method.id === formula.methodId)?.family === family) && `${formula.title} ${formula.formula} ${formula.purpose}`.toLowerCase().includes(query.trim().toLowerCase()));
  const filteredDiagnostics = diagnosticRules.filter((rule) => (family === "全部" || rule.family === family) && `${rule.id} ${rule.family} ${rule.name} ${rule.appliesTo} ${rule.trigger} ${rule.evidence} ${rule.action} ${rule.implementation}`.toLowerCase().includes(query.trim().toLowerCase()));
  const activeMethod = filteredMethods.find((method) => method.id === selected) ?? filteredMethods[0] ?? methods.find((method) => method.id === selected) ?? methods[0];
  const toggleCompare = (methodId: string) => setCompare((current) => current.includes(methodId) ? current.filter((item) => item !== methodId) : current.length < 3 ? [...current, methodId] : [...current.slice(1), methodId]);
  const changeTab = (next: typeof tab) => { setTab(next); setQuery(""); setFamily("全部"); };
  return <div className="methods-view page-view method-studio">
    <header className="view-header method-studio-header"><div><p className="eyebrow">Method & Formula Studio · versioned registry</p><h1>方法与公式库</h1><p>从研究目标和数据结构出发，连接公式、假设、诊断、代码与人工选择记录。</p></div><div className="studio-metrics"><div><strong>{methods.length}</strong><span>核心方法</span></div><div><strong>47</strong><span>公式模板</span></div><div><strong>36</strong><span>诊断规则</span></div></div></header>
    <nav className="studio-tabs" aria-label="方法工作台分区">{[["methods", "方法库"], ["formulas", "公式库"], ["diagnostics", "诊断规则"], ["design", "当前研究设计"]].map(([key, label]) => <button className={tab === key ? "is-active" : ""} onClick={() => changeTab(key as typeof tab)} key={key}>{label}<span>{key === "methods" ? methods.length : key === "formulas" ? 47 : key === "diagnostics" ? diagnosticRules.length : compare.length}</span></button>)}</nav>
    <section className="studio-toolbar"><label className="search-field"><span>⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={tab === "diagnostics" ? "搜索规则、适用方法、触发条件或 Stata 命令" : "搜索目标、方法、公式、诊断或标签"} aria-label="搜索方法、公式与诊断规则" /></label><select value={family} onChange={(event) => setFamily(event.target.value)} aria-label="筛选知识家族">{families.map((item) => <option key={item}>{item}</option>)}</select><button onClick={() => { setQuery(""); setFamily("全部"); }}>清除筛选</button></section>

    {tab === "methods" && <div className="method-library-shell"><section className="method-library-list" aria-label="候选方法">{filteredMethods.map((method) => <article className={`method-library-row ${selected === method.id ? "is-selected" : ""}`} key={method.id}><button className="method-row-main" onClick={() => setSelected(method.id)}><span className="method-code">{method.id}</span><div><div><b>{method.family}</b><small>{method.dataShape}</small></div><h2>{method.name}</h2><p>{method.goal}</p><div className="method-tag-row">{method.tags.slice(0, 3).map((tag) => <span key={tag}>{tag}</span>)}</div></div><strong className="method-row-fit">{method.fit}<small>%</small></strong></button><div className="method-row-actions"><button className={compare.includes(method.id) ? "is-active" : ""} onClick={() => toggleCompare(method.id)}>{compare.includes(method.id) ? "已加入比较" : "加入比较"}</button><button onClick={() => onOpenMethod(method.id)}>完整方法卡 →</button></div></article>)}{filteredMethods.length === 0 && <div className="empty-state">没有匹配的方法，请调整关键词或方法家族。</div>}</section><aside className="method-detail method-studio-detail"><p className="eyebrow">Selected method</p><div className="selected-method-title"><div><span>{activeMethod.id}</span><h2>{activeMethod.name}</h2></div><strong>{activeMethod.fit}%</strong></div><pre>{activeMethod.formula}</pre><dl><div><dt>目标</dt><dd>{activeMethod.estimand}</dd></div><div><dt>数据</dt><dd>{activeMethod.dataShape}</dd></div><div><dt>实现</dt><dd>{activeMethod.engine}</dd></div></dl><h3>关键假设</h3><ul>{activeMethod.assumptions.map((item) => <li key={item}><span>!</span>{item}</li>)}</ul><div className="method-warning"><strong>失败规则</strong><p>{activeMethod.failureRule}</p></div><div className="method-detail-actions"><button onClick={() => onOpenMethod(activeMethod.id)}>审阅完整方法卡</button><button className="primary-action" onClick={() => onAdd(activeMethod.id)}>加入研究设计</button></div></aside></div>}

    {tab === "formulas" && <section className="formula-library-grid">{filteredFormulas.map((formula) => <article className="formula-library-card" key={formula.id}><header><span>{formula.id}</span><b>{formula.family}</b></header><h2>{formula.title}</h2><p>{formula.purpose}</p><pre>{formula.formula}</pre><div className="formula-card-meta"><span>{formula.symbols.length} 个符号</span><span>{formula.assumptions.length} 项假设</span><span>{formula.diagnostics.length} 项诊断</span></div><footer><button onClick={() => { void navigator.clipboard?.writeText(formula.formula); onToast(`${formula.id} 公式已复制`); }}>复制公式</button><button className="primary-action" onClick={() => onOpenFormula(formula.id)}>打开公式卡 →</button></footer></article>)}<article className="formula-library-card formula-coming-card"><span>+35</span><h2>已策划扩展模板</h2><p>时间序列、离散选择、生存分析、多层模型、多目标优化、排队与博弈模型将在后端注册表中版本化上线。</p><button onClick={() => onToast("扩展公式目录已加入产品 Roadmap")}>查看上线规则</button></article></section>}

    {tab === "diagnostics" && <section className="diagnostic-registry"><header><div><p className="eyebrow">Diagnostic policy registry · 36 / 36</p><h2>诊断不是附录，是方法的退出条件</h2><p>每条规则都包含适用方法、触发时点、所需证据、失败动作和实现提示。</p></div><div><span>当前显示 <strong>{filteredDiagnostics.length}</strong> / {diagnosticRules.length}</span><button onClick={() => onToast(`${filteredDiagnostics.length} 条诊断规则已加入 S5–S7 分析计划检查清单`)}>加入当前结果</button></div></header><div className="diagnostic-rule-grid">{filteredDiagnostics.map((rule) => { const expanded = expandedDiagnostic === rule.id; return <article className={`diagnostic-rule-card level-${rule.level} ${expanded ? "is-expanded" : ""}`} key={rule.id}><header><span>{rule.id}</span><b>{rule.level}</b><small>{rule.stage}</small></header><div className="diagnostic-rule-family">{rule.family}</div><h3>{rule.name}</h3><p>{rule.appliesTo}</p><dl><div><dt>触发</dt><dd>{rule.trigger}</dd></div>{expanded && <><div><dt>证据</dt><dd>{rule.evidence}</dd></div><div><dt>失败动作</dt><dd>{rule.action}</dd></div></>}</dl>{expanded && <div className="diagnostic-implementation"><span>实现提示</span><code>{rule.implementation}</code></div>}<footer><button onClick={() => onToast(`${rule.id} ${rule.name} 已加入当前分析计划`)}>加入计划</button><button className="primary-action" onClick={() => setExpandedDiagnostic(expanded ? null : rule.id)}>{expanded ? "收起规则" : "查看完整规则"}</button></footer></article>; })}{filteredDiagnostics.length === 0 && <div className="empty-state">没有匹配的诊断规则，请清除筛选或更换关键词。</div>}</div></section>}

    {tab === "design" && <section className="current-design-board"><header><div><p className="eyebrow">Research design bundle</p><h2>当前候选方法比较</h2><p>最多同时比较 3 个候选；确定主模型前必须记录未采用理由。</p></div><button className="primary-action" disabled={!compare.length} onClick={() => { if (compare[0]) onAdd(compare[0]); }}>将首项设为主方案草稿</button></header><div className="design-compare-grid">{compare.map((methodId, index) => { const method = methods.find((item) => item.id === methodId); if (!method) return null; return <article key={method.id}><div><span>{index === 0 ? "PRIMARY CANDIDATE" : `ALTERNATIVE ${index}`}</span><button onClick={() => toggleCompare(method.id)}>移除</button></div><h2>{method.name}</h2><pre>{method.formula}</pre><dl><div><dt>估计 / 决策目标</dt><dd>{method.estimand}</dd></div><div><dt>数据结构</dt><dd>{method.dataShape}</dd></div><div><dt>失败规则</dt><dd>{method.failureRule}</dd></div></dl><button onClick={() => onOpenMethod(method.id)}>打开方法卡核对</button></article>; })}{!compare.length && <div className="empty-state">从“方法库”加入 1–3 个候选方法进行比较。</div>}</div></section>}
  </div>;
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
  const [preferencesOpen, setPreferencesOpen] = useState(false);
  const [interfaceTheme, setInterfaceTheme] = useState<InterfaceTheme>("graphite");
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
    const saved = window.localStorage.getItem("ai4ms-interface-theme");
    const frame = window.requestAnimationFrame(() => {
      if (saved === "graphite" || saved === "blueprint" || saved === "paper") setInterfaceTheme(saved);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

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
  function selectInterfaceTheme(theme: InterfaceTheme) {
    setInterfaceTheme(theme);
    window.localStorage.setItem("ai4ms-interface-theme", theme);
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
  function syncAgentOutput(text: string, target: ChatSyncTarget, mode: ChatSyncMode) {
    const stageIndex = chatAgent;
    const draft = getDraft(stageIndex);
    const stage = stages[stageIndex];
    const targetLabels: Record<ChatSyncTarget, string> = { content: "交付正文", summary: "阶段摘要", evidenceNote: "证据说明", decision: "决定记录草稿" };
    const stamp = new Date().toLocaleString("zh-CN", { hour12: false });
    const block = `【${stage.agent} 协作建议 · ${stamp} · 待人工审阅】\n${text}`;
    const currentValue = draft[target];
    const nextValue = mode === "replace" ? block : `${currentValue.trim()}\n\n${block}`.trim();
    saveDraft(stageIndex, { ...draft, [target]: nextValue, savedAt: "刚刚由研究者确认同步", syncHistory: [`${stamp} · ${stage.agent} → ${targetLabels[target]}（${mode === "replace" ? "替换" : "追加"}）`, ...draft.syncHistory] }, `已同步到 ${stage.id} ${targetLabels[target]}，可继续人工修改`);
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
      const draft = getDraft(deepRoute.stageIndex);
      return <StageDraftWorkspace key={`${draft.version}:${draft.savedAt}:${draft.syncHistory.length}`} stage={stage} project={activeProject} draft={draft} onBack={backDeep} onSave={(nextDraft, message) => saveDraft(deepRoute.stageIndex, nextDraft, message)} onOpenCheck={() => openDeep({ kind: "stage-check", stageIndex: deepRoute.stageIndex })} onOpenDecisions={() => openDeep({ kind: "stage-decisions", stageIndex: deepRoute.stageIndex })} onOpenChat={() => openAgentChat(deepRoute.stageIndex)} onOpenEvidence={() => navigateView("evidence")} />;
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
      return <MethodRecordWorkspace method={method} onBack={backDeep} onAdd={() => addMethodToDesign(method.id)} onSave={showToast} />;
    }
    if (deepRoute.kind === "formula-record") {
      const formula = formulas.find((item) => item.id === deepRoute.formulaId) ?? formulas[0];
      return <FormulaRecordPage formula={formula} onBack={backDeep} onAdd={() => addMethodToDesign(formula.methodId)} onSave={showToast} />;
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
    <div className="app-shell" data-interface-theme={interfaceTheme}>
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
              <button onClick={() => { setUserMenu(false); window.open("/ai4ms-user-guide.html", "_blank", "noopener,noreferrer"); }}>使用说明</button>
              <button onClick={() => { setUserMenu(false); setPreferencesOpen(true); }}>界面偏好</button>
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
          {view === "methods" && <MethodsView onOpenMethod={(methodId) => openDeep({ kind: "method-record", methodId })} onOpenFormula={(formulaId) => openDeep({ kind: "formula-record", formulaId })} onAdd={addMethodToDesign} onToast={showToast} />}
          {view === "runs" && <RunsView project={activeProject} onOpenDetail={setDetail} onOpenGate={(gateId) => openDeep({ kind: "approval-gate", gateId })} onToast={showToast} />}
          {view === "approvals" && <ApprovalsView project={activeProject} submittedGates={submittedGates} onOpenGate={(gateId) => openDeep({ kind: "approval-gate", gateId })} onOpenDetail={setDetail} />}
          </>}
        </div>
      </main>

      <ApprovalModal key={`${activeProject.id}:${activeStageData.gate}:${approvalOpen}`} open={approvalOpen} stageIndex={activeStage} onClose={() => setApprovalOpen(false)} onConfirm={confirmApproval} />
      <DetailModal detail={detail} onClose={() => setDetail(null)} />
      <PreferencesModal open={preferencesOpen} value={interfaceTheme} onSelect={selectInterfaceTheme} onClose={() => setPreferencesOpen(false)} />
      <AgentChatDrawer open={chatOpen} agentIndex={chatAgent} messages={chatMessages[chatAgent] ?? []} busy={chatBusy} onClose={() => setChatOpen(false)} onSelectAgent={setChatAgent} onSend={sendAgentMessage} onCapture={syncAgentOutput} />
      {toast && <div className="toast" role="status"><span>✓</span>{toast}</div>}
      <div className="screen-reader-status" aria-live="polite">当前页面：{pageTitle}</div>
    </div>
  );
}
