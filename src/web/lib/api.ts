export type StageStatus =
  | "not_started"
  | "in_progress"
  | "needs_review"
  | "approved"
  | "blocked";

export type ApprovalDecision = "approve" | "request_changes" | "reject";

export interface ProjectSummary {
  project_id: string;
  title: string;
  initial_idea: string;
  status: "active" | "completed" | "archived";
  current_stage: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectStage {
  project_id: string;
  key: string;
  code: string;
  position: number;
  title: string;
  short_title: string;
  description: string;
  artifact_type: string;
  gate: string | null;
  status: StageStatus;
  revision: number;
  revision_id: string | null;
  content_hash: string | null;
  author_type: string | null;
  change_reason: string | null;
  revision_created_at: string | null;
  approved_at: string | null;
  updated_at: string;
  content: Record<string, unknown>;
}

export interface ApprovalEvent {
  approval_id: string;
  project_id: string;
  stage_key: string;
  revision: number;
  decision: ApprovalDecision;
  reason: string;
  actor_type: "human";
  created_at: string;
}

export interface Project extends ProjectSummary {
  stages: ProjectStage[];
  approvals: ApprovalEvent[];
  progress: { approved: number; total: number };
}

interface ApiErrorPayload {
  error?: { code?: string; message?: string };
  detail?: string | Array<{ msg?: string }>;
}

const API_ROOT = (process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code = "api_error",
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload;
    const validationMessage = Array.isArray(payload.detail)
      ? payload.detail.map((item) => item.msg).filter(Boolean).join("；")
      : payload.detail;
    throw new ApiError(
      payload.error?.message || validationMessage || `API 请求失败（${response.status}）`,
      response.status,
      payload.error?.code,
    );
  }
  return response.json() as Promise<T>;
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const response = await request<{ items: ProjectSummary[] }>("/projects");
  return response.items;
}

export function getProject(projectId: string): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(projectId)}`);
}

export function createProject(title: string, initialIdea: string): Promise<Project> {
  return request<Project>("/projects", {
    method: "POST",
    body: JSON.stringify({ title, initial_idea: initialIdea }),
  });
}

export function saveStage(
  projectId: string,
  stageKey: string,
  content: Record<string, unknown>,
  changeReason: string,
): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}`, {
    method: "PUT",
    body: JSON.stringify({ content, change_reason: changeReason, author_type: "human" }),
  });
}

export function createStageDraft(projectId: string, stageKey: string, instruction: string): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}/draft`, {
    method: "POST",
    body: JSON.stringify({ instruction }),
  });
}

export function decideStage(
  projectId: string,
  stageKey: string,
  decision: ApprovalDecision,
  reason: string,
): Promise<Project> {
  return request<Project>(`/projects/${encodeURIComponent(projectId)}/stages/${encodeURIComponent(stageKey)}/decisions`, {
    method: "POST",
    body: JSON.stringify({ decision, reason, actor_type: "human" }),
  });
}
