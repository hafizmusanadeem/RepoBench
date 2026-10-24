// Client for the RepoBench backend (backend/main.py). Move this file from
// src/api.ts to src/lib/api.ts -- every page already imports "../lib/api".

export type RunStatus = "queued" | "running" | "success" | "error";
export type RunResult = "PASS" | "FAIL";
export type ToolStatus = "Success" | "Failed";
export type TaskKind = "feature" | "bug" | "failing_test" | "refactor";

export type TaskSummary = { id: string; title: string; category: string; difficulty: string; repository: string };
export type AgentInfo = { id: string; label: string; kind: string; model: string; available: boolean; reason: string | null };

export type Profile = {
  language: string;
  packageManager: string;
  baseImage: string;
  installCommand: string;
  testCommand: string;
  buildCommand: string;
  lintCommand: string;
  notes: string[];
};

export type Repo = {
  id: string;
  url: string;
  ref: string | null;
  commit: string | null;
  status: "cloning" | "ready" | "error";
  errorMessage: string | null;
  profile: Profile | null;
  createdAt: string;
};

export type ToolCall = {
  id: string;
  step: number;
  /** "bash", "text_editor", "think", "submit", ... or "assistant_message" */
  tool: string;
  status: ToolStatus;
  duration: string;
  arguments: Record<string, unknown>;
  output: string | null;
  error: string | null;
};

export type RunSummary = {
  id: string;
  evaluationId: string | null;
  taskId: string;
  taskTitle: string;
  agent: string;
  epoch: number | null;
  status: RunStatus;
  result: RunResult | null;
  toolCallCount: number | null;
  failedToolCalls: number | null;
  duration: string | null;
  durationSeconds: number | null;
  tokens: number | null;
  costUsd: number | null;
  filesChanged: number | null;
  additions: number | null;
  deletions: number | null;
  regressions: number | null;
  baselineTestsOk: boolean | null;
  baselineVerifyOk: boolean | null;
  createdAt: string;
  completedAt: string | null;
  errorMessage: string | null;
};

export type RunDetail = RunSummary & { transcript: ToolCall[]; patch: string | null };

export type EvaluationSummary = {
  id: string;
  repoId: string | null;
  repoUrl: string | null;
  repoCommit: string | null;
  benchmarkTaskId: string | null;
  kind: string;
  title: string;
  description: string;
  agents: string[];
  epochs: number;
  status: "building" | "running" | "complete" | "error";
  errorMessage: string | null;
  createdAt: string;
  runCount: number;
  doneCount: number;
};

export type EvaluationDetail = EvaluationSummary & {
  verifyCommand: string;
  testCommand: string;
  errorLog: string;
  runs: RunSummary[];
};

export type AgentStats = {
  agent: string;
  n: number;
  passes: number;
  errors: number;
  successRate: number;
  ciLow: number;
  ciHigh: number;
  medianDurationS: number | null;
  medianCostUsd: number | null;
  medianTokens: number | null;
  regressionRate: number;
  wins: number;
  losses: number;
  ties: number;
  score: number;
};

export type Recommendation = {
  bestAgent: string | null;
  confidence: "none" | "low" | "medium" | "high";
  summary: string;
  stats: AgentStats[];
  weights: Record<string, number>;
};

export type DashboardMetrics = {
  total: number;
  passed: number;
  failed: number;
  running: number;
  errored: number;
  successRate: number;
  byAgent: { agent: string; passed: number; failed: number; errored: number }[];
};

export type CreateEvaluationInput = {
  repoId?: string;
  benchmarkTaskId?: string;
  kind: TaskKind;
  title: string;
  description: string;
  errorLog: string;
  verifyCommand: string;
  agents: string[];
  epochs: number;
  maxToolCalls: number;
  judge: boolean;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!response.ok) {
    let detail = "";
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? "");
    } catch {
      // not JSON; fall back to the status text
    }
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const post = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "POST", body: JSON.stringify(body) });

export const listTasks = () => request<TaskSummary[]>("/tasks");
export const listAgents = () => request<string[]>("/agents");
export const listAgentInfo = () => request<AgentInfo[]>("/agents/info");

export const createRepo = (input: { url: string; ref?: string }) => post<Repo>("/repos", input);
export const getRepo = (id: string) => request<Repo>(`/repos/${id}`);
export const updateRepoProfile = (id: string, profile: Profile) =>
  request<Repo>(`/repos/${id}/profile`, { method: "PUT", body: JSON.stringify(profile) });

export const createEvaluation = (input: CreateEvaluationInput) =>
  post<EvaluationSummary>("/evaluations", input);
export const listEvaluations = () => request<EvaluationSummary[]>("/evaluations");
export const getEvaluation = (id: string) => request<EvaluationDetail>(`/evaluations/${id}`);
export const getRecommendation = (id: string, w: { success: number; cost: number; time: number }) =>
  request<Recommendation>(
    `/evaluations/${id}/recommendation?w_success=${w.success}&w_cost=${w.cost}&w_time=${w.time}`,
  );
export const createVote = (evaluationId: string, vote: { runA: string; runB: string; winner: "a" | "b" | "tie" }) =>
  post<{ id: string }>(`/evaluations/${evaluationId}/votes`, vote);

export const listRuns = () => request<RunSummary[]>("/runs");
export const getRun = (runId: string) => request<RunDetail>(`/runs/${runId}`);
export const getDashboardMetrics = () => request<DashboardMetrics>("/dashboard/metrics");
