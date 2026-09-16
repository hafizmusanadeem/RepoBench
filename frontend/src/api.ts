// Client for the RepoBench backend (see backend/main.py). Every response
// shape here mirrors backend/schemas.py field-for-field.

export type RunStatus = "running" | "success" | "error";
export type RunResult = "PASS" | "FAIL";
export type ToolStatus = "Success" | "Failed";

export type TaskSummary = {
  id: string;
  title: string;
  category: string;
  difficulty: string;
  repository: string;
};

export type ToolCall = {
  id: string;
  step: number;
  /** The tool's registered name: "bash", "text_editor", "think", "submit", ... */
  tool: string;
  status: ToolStatus;
  duration: string;
  arguments: Record<string, unknown>;
  output: string | null;
  error: string | null;
};

export type RunSummary = {
  id: string;
  taskId: string;
  taskTitle: string;
  agent: string;
  status: RunStatus;
  result: RunResult | null;
  toolCallCount: number | null;
  duration: string | null;
  createdAt: string;
  completedAt: string | null;
  errorMessage: string | null;
};

export type RunDetail = RunSummary & {
  transcript: ToolCall[];
};

export type DashboardMetrics = {
  total: number;
  passed: number;
  failed: number;
  running: number;
  successRate: number;
};

// In dev, Vite proxies /api to the backend (see vite.config.ts). In a
// production build, set VITE_API_BASE_URL to wherever the backend is
// actually hosted.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });

  if (!response.ok) {
    let detail = "";
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? "";
    } catch {
      // response wasn't JSON -- fall back to the status text below
    }
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function listTasks(): Promise<TaskSummary[]> {
  return request<TaskSummary[]>("/tasks");
}

export function listAgents(): Promise<string[]> {
  return request<string[]>("/agents");
}

export function listRuns(): Promise<RunSummary[]> {
  return request<RunSummary[]>("/runs");
}

export function getRun(runId: string): Promise<RunDetail> {
  return request<RunDetail>(`/runs/${runId}`);
}

export function getDashboardMetrics(): Promise<DashboardMetrics> {
  return request<DashboardMetrics>("/dashboard/metrics");
}

export function createRun(input: {
  taskId: string;
  agent: string;
  maxToolCalls: number;
}): Promise<RunSummary> {
  return request<RunSummary>("/runs", {
    method: "POST",
    body: JSON.stringify({
      taskId: input.taskId,
      agent: input.agent,
      maxToolCalls: input.maxToolCalls,
    }),
  });
}
