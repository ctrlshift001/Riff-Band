import { api } from "/assets/api.js";

const state = { projects: [], project: null, stageKey: null, dirty: false };
const elements = Object.fromEntries(
  [
    "project-select", "new-project-button", "empty-create-button", "stage-list", "connection-dot",
    "connection-label", "project-kicker", "project-title", "project-status", "progress-text", "empty-state",
    "workspace-content", "stage-position", "stage-title", "stage-description", "stage-status", "draft-button",
    "save-button", "changes-button", "reject-button", "approve-button", "asset-editor", "revision-label",
    "artifact-type", "save-state", "gate-value", "approval-list", "contract-stage", "contract-artifact",
    "contract-api", "project-dialog", "project-form", "dialog-close", "dialog-cancel", "toast",
  ].map((id) => [id, document.getElementById(id)]),
);

const statusLabels = {
  not_started: "未开始",
  in_progress: "进行中",
  needs_review: "待审核",
  approved: "已批准",
  blocked: "已阻塞",
  active: "进行中",
  completed: "已完成",
  archived: "已归档",
};

function setConnection(connected) {
  elements["connection-dot"].dataset.connected = String(connected);
  elements["connection-label"].textContent = connected ? "服务正常" : "连接失败";
}

function setBadge(element, status) {
  element.className = `status-badge status-${status}`;
  element.textContent = statusLabels[status] || status;
}

function showToast(message, kind = "success") {
  elements.toast.textContent = message;
  elements.toast.classList.toggle("is-error", kind === "error");
  elements.toast.hidden = false;
  window.clearTimeout(showToast.timeoutId);
  showToast.timeoutId = window.setTimeout(() => {
    elements.toast.hidden = true;
  }, 2600);
}

async function loadProjects(preferredId = null) {
  const payload = await api.projects();
  state.projects = payload.items;
  renderProjectOptions();
  const selectedId = preferredId || state.project?.project_id || state.projects[0]?.project_id;
  if (selectedId) await selectProject(selectedId);
  else renderEmpty();
}

function renderProjectOptions() {
  elements["project-select"].replaceChildren();
  if (!state.projects.length) {
    const option = new Option("暂无项目", "");
    elements["project-select"].append(option);
    elements["project-select"].disabled = true;
    return;
  }
  elements["project-select"].disabled = false;
  state.projects.forEach((project) => elements["project-select"].append(new Option(project.title, project.project_id)));
}

async function selectProject(projectId) {
  state.project = await api.project(projectId);
  elements["project-select"].value = projectId;
  state.stageKey = state.stageKey && state.project.stages.some((stage) => stage.key === state.stageKey)
    ? state.stageKey
    : state.project.current_stage;
  state.dirty = false;
  renderWorkspace();
}

function renderEmpty() {
  state.project = null;
  elements["empty-state"].hidden = false;
  elements["workspace-content"].hidden = true;
  elements["project-kicker"].textContent = "尚未选择项目";
  elements["project-title"].textContent = "科研项目";
  elements["progress-text"].textContent = "0 / 9";
  setBadge(elements["project-status"], "not_started");
  elements["stage-list"].replaceChildren();
}

function renderWorkspace() {
  const project = state.project;
  if (!project) return renderEmpty();
  elements["empty-state"].hidden = true;
  elements["workspace-content"].hidden = false;
  elements["project-kicker"].textContent = project.project_id;
  elements["project-title"].textContent = project.title;
  elements["progress-text"].textContent = `${project.progress.approved} / ${project.progress.total}`;
  setBadge(elements["project-status"], project.status);
  renderStages();
  renderStageDetail();
}

function renderStages() {
  elements["stage-list"].replaceChildren();
  state.project.stages.forEach((stage) => {
    const item = document.createElement("li");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "stage-button";
    if (stage.key === state.stageKey) button.setAttribute("aria-current", "step");
    button.innerHTML = `<span class="stage-number">${String(stage.position).padStart(2, "0")}</span><strong class="stage-name"></strong><span class="stage-dot"></span>`;
    button.querySelector(".stage-name").textContent = stage.short_title;
    const marker = button.querySelector(".stage-dot");
    marker.classList.add(`status-${stage.status}`);
    marker.title = statusLabels[stage.status] || stage.status;
    button.addEventListener("click", () => {
      state.stageKey = stage.key;
      state.dirty = false;
      renderWorkspace();
    });
    item.append(button);
    elements["stage-list"].append(item);
  });
}

function currentStage() {
  return state.project.stages.find((stage) => stage.key === state.stageKey);
}

function renderStageDetail() {
  const stage = currentStage();
  elements["stage-position"].textContent = `步骤 ${stage.position} / 9`;
  elements["stage-title"].textContent = stage.title;
  elements["stage-description"].textContent = stage.description;
  setBadge(elements["stage-status"], stage.status);
  elements["revision-label"].textContent = `Revision ${stage.revision}`;
  elements["artifact-type"].textContent = stage.artifact_type;
  elements["asset-editor"].value = JSON.stringify(stage.content || {}, null, 2);
  elements["save-state"].textContent = "已同步";
  elements["gate-value"].textContent = stage.gate || "阶段确认";
  elements["contract-stage"].textContent = stage.key;
  elements["contract-artifact"].textContent = stage.artifact_type;
  elements["contract-api"].textContent = `PUT /stages/${stage.key}`;
  const locked = stage.status === "not_started";
  elements["draft-button"].disabled = locked;
  elements["save-button"].disabled = locked;
  elements["approve-button"].disabled = stage.revision < 1 || locked;
  elements["changes-button"].disabled = stage.revision < 1 || locked;
  elements["reject-button"].disabled = stage.revision < 1 || locked;
  renderApprovals(stage.key);
}

function renderApprovals(stageKey) {
  elements["approval-list"].replaceChildren();
  const approvals = state.project.approvals.filter((item) => item.stage_key === stageKey).slice(0, 4);
  if (!approvals.length) {
    const empty = document.createElement("div");
    empty.className = "muted-text";
    empty.textContent = "暂无决定";
    elements["approval-list"].append(empty);
    return;
  }
  approvals.forEach((approval) => {
    const row = document.createElement("div");
    row.className = "approval-row";
    const title = document.createElement("strong");
    title.textContent = approval.decision;
    const meta = document.createElement("span");
    meta.textContent = `R${approval.revision} · ${new Date(approval.created_at).toLocaleString()}`;
    row.append(title, meta);
    elements["approval-list"].append(row);
  });
}

async function saveStage() {
  let content;
  try {
    content = JSON.parse(elements["asset-editor"].value);
  } catch {
    showToast("结构化资产不是有效 JSON", "error");
    return;
  }
  const project = await api.saveStage(state.project.project_id, state.stageKey, {
    content,
    change_reason: "Updated in web workbench",
    author_type: "human",
  });
  state.project = project;
  state.dirty = false;
  showToast("修改已保存");
  renderWorkspace();
}

async function createDraft() {
  state.project = await api.createDraft(state.project.project_id, state.stageKey);
  showToast("结构草稿已生成");
  renderWorkspace();
}

async function decide(decision) {
  state.project = await api.decideStage(state.project.project_id, state.stageKey, decision);
  state.stageKey = state.project.current_stage;
  showToast(decision === "approve" ? "已批准并进入下一步" : "决定已记录");
  renderWorkspace();
}

function openProjectDialog() {
  elements["project-form"].reset();
  elements["project-dialog"].showModal();
  document.getElementById("project-name").focus();
}

elements["new-project-button"].addEventListener("click", openProjectDialog);
elements["empty-create-button"].addEventListener("click", openProjectDialog);
elements["dialog-close"].addEventListener("click", () => elements["project-dialog"].close());
elements["dialog-cancel"].addEventListener("click", () => elements["project-dialog"].close());
elements["project-select"].addEventListener("change", (event) => selectProject(event.target.value).catch(handleError));
elements["asset-editor"].addEventListener("input", () => {
  state.dirty = true;
  elements["save-state"].textContent = "有未保存修改";
});
elements["draft-button"].addEventListener("click", () => createDraft().catch(handleError));
elements["save-button"].addEventListener("click", () => saveStage().catch(handleError));
elements["approve-button"].addEventListener("click", () => decide("approve").catch(handleError));
elements["changes-button"].addEventListener("click", () => decide("request_changes").catch(handleError));
elements["reject-button"].addEventListener("click", () => decide("reject").catch(handleError));
elements["project-form"].addEventListener("submit", async (event) => {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  try {
    const project = await api.createProject({ title: form.get("title"), initial_idea: form.get("initial_idea") });
    elements["project-dialog"].close();
    await loadProjects(project.project_id);
    showToast("项目已创建");
  } catch (error) {
    handleError(error);
  }
});

function handleError(error) {
  console.error(error);
  showToast(error.message || "操作失败", "error");
}

async function initialize() {
  try {
    await Promise.all([fetch("/healthz").then((response) => {
      if (!response.ok) throw new Error("health check failed");
    }), api.stages()]);
    setConnection(true);
    await loadProjects();
  } catch (error) {
    setConnection(false);
    handleError(error);
    renderEmpty();
  }
}

initialize();
