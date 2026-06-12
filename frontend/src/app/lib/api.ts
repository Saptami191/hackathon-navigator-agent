import axios, { AxiosInstance } from "axios";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function createApiClient(token: string | null): AxiosInstance {
  const client = axios.create({
    baseURL: `${API_BASE}/api/v1`,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    timeout: 30000,
  });

  client.interceptors.response.use(
    (response) => response,
    (error) => {
      const message =
        error.response?.data?.detail ||
        error.response?.data?.message ||
        error.message ||
        "An unexpected error occurred";
      return Promise.reject(new Error(message));
    }
  );

  return client;
}

// Project endpoints
export const projectsApi = {
  list: (client: AxiosInstance) => client.get("/projects/"),
  get: (client: AxiosInstance, id: string) => client.get(`/projects/${id}`),
  create: (client: AxiosInstance, data: CreateProjectData) => client.post("/projects/", data),
  update: (client: AxiosInstance, id: string, data: Partial<CreateProjectData>) =>
    client.patch(`/projects/${id}`, data),
  delete: (client: AxiosInstance, id: string) => client.delete(`/projects/${id}`),
};

// Analysis endpoints
export const analysisApi = {
  trigger: (client: AxiosInstance, projectId: string) =>
    client.post("/analysis/trigger", { project_id: projectId }),
  getRuns: (client: AxiosInstance, projectId: string) =>
    client.get(`/analysis/runs/${projectId}`),
  getRunStatus: (client: AxiosInstance, runId: string) =>
    client.get(`/analysis/runs/status/${runId}`),
  getLatestSnapshot: (client: AxiosInstance, projectId: string) =>
    client.get(`/analysis/latest/${projectId}`),
  getSnapshots: (client: AxiosInstance, projectId: string) =>
    client.get(`/analysis/snapshots/${projectId}`),
};

// Tasks endpoints
export const tasksApi = {
  getByProject: (client: AxiosInstance, projectId: string, params?: Record<string, string>) =>
    client.get(`/tasks/${projectId}`, { params }),
  updateTask: (client: AxiosInstance, taskId: string, data: UpdateTaskData) =>
    client.patch(`/tasks/${taskId}`, data),
};

// Pitches endpoints
export const pitchesApi = {
  getByProject: (client: AxiosInstance, projectId: string) =>
    client.get(`/pitches/${projectId}`),
  generate: (client: AxiosInstance, projectId: string, pitchType: string) =>
    client.post("/pitches/generate", { project_id: projectId, pitch_type: pitchType }),
};

// GitHub endpoints
export const githubApi = {
  getRepoInfo: (client: AxiosInstance, projectId: string) =>
    client.get(`/github/repo-info/${projectId}`),
};

// Types
export interface CreateProjectData {
  name: string;
  description?: string;
  github_repo_url?: string;
  hackathon_theme?: string;
  submission_deadline?: string;
  judging_criteria?: string[];
  project_goals?: string[];
  devpost_url?: string;
}

export interface UpdateTaskData {
  status?: string;
  priority?: string;
  assignee?: string;
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  github_repo_url?: string;
  hackathon_theme?: string;
  submission_deadline?: string;
  judging_criteria: string[];
  project_goals: string[];
  tech_stack: string[];
  devpost_url?: string;
  is_active: boolean;
  last_analyzed_at?: string;
  created_at: string;
}

export interface Task {
  id: string;
  project_id: string;
  title: string;
  description?: string;
  status: string;
  priority: string;
  estimated_hours?: number;
  is_blocker: boolean;
  is_ai_generated: boolean;
  impact_score?: number;
  category?: string;
  assignee?: string;
  created_at: string;
}

export interface AgentRun {
  id: string;
  project_id: string;
  agent_type: string;
  status: string;
  trigger?: string;
  output_data?: Record<string, unknown>;
  error_message?: string;
  duration_seconds?: number;
  tokens_used?: number;
  created_at: string;
}

export interface AnalysisSnapshot {
  id: string;
  project_id: string;
  architecture_summary?: string;
  tech_stack_detected?: string[];
  open_issues_count?: number;
  open_prs_count?: number;
  completion_percentage?: number;
  risk_level?: string;
  estimated_hours_remaining?: number;
  recommendations?: string[];
  created_at: string;
}

export interface Pitch {
  id: string;
  project_id: string;
  pitch_type: string;
  content: string;
  version: number;
  is_latest: boolean;
  created_at: string;
}
