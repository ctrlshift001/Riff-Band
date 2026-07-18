const API_ROOT = "/api/v1";

async function request(path, options = {}) {
  const response = await fetch(`${API_ROOT}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = payload?.error?.message || payload?.detail || `请求失败 (${response.status})`;
    throw new Error(message);
  }
  return payload;
}

export const api = {
  stages: () => request("/meta/stages"),
  projects: () => request("/projects"),
  project: (projectId) => request(`/projects/${projectId}`),
  createProject: (body) => request("/projects", { method: "POST", body: JSON.stringify(body) }),
  saveStage: (projectId, stageKey, body) => request(`/projects/${projectId}/stages/${stageKey}`, { method: "PUT", body: JSON.stringify(body) }),
  createDraft: (projectId, stageKey) => request(`/projects/${projectId}/stages/${stageKey}/draft`, { method: "POST", body: JSON.stringify({ instruction: "" }) }),
  decideStage: (projectId, stageKey, decision, reason = "") => request(`/projects/${projectId}/stages/${stageKey}/decisions`, {
    method: "POST",
    body: JSON.stringify({ decision, reason, actor_type: "human" }),
  }),
};
