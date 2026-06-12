import { useAuth } from "@clerk/nextjs";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AnalysisSnapshot,
  AgentRun,
  CreateProjectData,
  Pitch,
  Project,
  Task,
  UpdateTaskData,
  analysisApi,
  createApiClient,
  githubApi,
  pitchesApi,
  projectsApi,
  tasksApi,
} from "@/lib/api";

function useApiClient() {
  const { getToken } = useAuth();

  const getClient = async () => {
    const token = await getToken();
    return createApiClient(token);
  };

  return getClient;
}

// ─── Projects ────────────────────────────────────────────────────────────────

export function useProjects() {
  const getClient = useApiClient();
  return useQuery<Project[]>({
    queryKey: ["projects"],
    queryFn: async () => {
      const client = await getClient();
      const { data } = await projectsApi.list(client);
      return data;
    },
  });
}

export function useProject(id: string) {
  const getClient = useApiClient();
  return useQuery<Project>({
    queryKey: ["project", id],
    queryFn: async () => {
      const client = await getClient();
      const { data } = await projectsApi.get(client, id);
      return data;
    },
    enabled: !!id,
  });
}

export function useCreateProject() {
  const getClient = useApiClient();
  const queryClient = useQueryClient();
  return useMutation<Project, Error, CreateProjectData>({
    mutationFn: async (data) => {
      const client = await getClient();
      const { data: response } = await projectsApi.create(client, data);
      return response;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Project created successfully!");
    },
    onError: (error) => {
      toast.error(`Failed to create project: ${error.message}`);
    },
  });
}

export function useDeleteProject() {
  const getClient = useApiClient();
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: async (id) => {
      const client = await getClient();
      await projectsApi.delete(client, id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      toast.success("Project deleted");
    },
  });
}

// ─── Analysis ─────────────────────────────────────────────────────────────────

export function useTriggerAnalysis() {
  const getClient = useApiClient();
  const queryClient = useQueryClient();
  return useMutation<AgentRun, Error, string>({
    mutationFn: async (projectId) => {
      const client = await getClient();
      const { data } = await analysisApi.trigger(client, projectId);
      return data;
    },
    onSuccess: (_, projectId) => {
      queryClient.invalidateQueries({ queryKey: ["agent-runs", projectId] });
      toast.success("Analysis started! This will take 1-3 minutes.");
    },
    onError: (error) => {
      toast.error(`Failed to start analysis: ${error.message}`);
    },
  });
}

export function useAgentRuns(projectId: string) {
  const getClient = useApiClient();
  return useQuery<AgentRun[]>({
    queryKey: ["agent-runs", projectId],
    queryFn: async () => {
      const client = await getClient();
      const { data } = await analysisApi.getRuns(client, projectId);
      return data;
    },
    enabled: !!projectId,
    refetchInterval: (query) => {
      const runs = query.state.data;
      const hasRunning = runs?.some((r) => r.status === "running" || r.status === "queued");
      return hasRunning ? 5000 : false;
    },
  });
}

export function useLatestSnapshot(projectId: string) {
  const getClient = useApiClient();
  return useQuery<AnalysisSnapshot>({
    queryKey: ["snapshot", projectId],
    queryFn: async () => {
      const client = await getClient();
      const { data } = await analysisApi.getLatestSnapshot(client, projectId);
      return data;
    },
    enabled: !!projectId,
  });
}

// ─── Tasks ────────────────────────────────────────────────────────────────────

export function useTasks(projectId: string, filters?: Record<string, string>) {
  const getClient = useApiClient();
  return useQuery<Task[]>({
    queryKey: ["tasks", projectId, filters],
    queryFn: async () => {
      const client = await getClient();
      const { data } = await tasksApi.getByProject(client, projectId, filters);
      return data;
    },
    enabled: !!projectId,
  });
}

export function useUpdateTask() {
  const getClient = useApiClient();
  const queryClient = useQueryClient();
  return useMutation<Task, Error, { taskId: string; data: UpdateTaskData; projectId: string }>({
    mutationFn: async ({ taskId, data }) => {
      const client = await getClient();
      const { data: response } = await tasksApi.updateTask(client, taskId, data);
      return response;
    },
    onSuccess: (_, { projectId }) => {
      queryClient.invalidateQueries({ queryKey: ["tasks", projectId] });
      toast.success("Task updated");
    },
  });
}

// ─── Pitches ──────────────────────────────────────────────────────────────────

export function usePitches(projectId: string) {
  const getClient = useApiClient();
  return useQuery<Pitch[]>({
    queryKey: ["pitches", projectId],
    queryFn: async () => {
      const client = await getClient();
      const { data } = await pitchesApi.getByProject(client, projectId);
      return data;
    },
    enabled: !!projectId,
  });
}

export function useGeneratePitch() {
  const getClient = useApiClient();
  const queryClient = useQueryClient();
  return useMutation<void, Error, { projectId: string; pitchType: string }>({
    mutationFn: async ({ projectId, pitchType }) => {
      const client = await getClient();
      await pitchesApi.generate(client, projectId, pitchType);
    },
    onSuccess: (_, { projectId }) => {
      queryClient.invalidateQueries({ queryKey: ["pitches", projectId] });
      toast.success("Pitch generated!");
    },
    onError: (error) => {
      toast.error(`Failed to generate pitch: ${error.message}`);
    },
  });
}

// ─── GitHub ───────────────────────────────────────────────────────────────────

export function useRepoInfo(projectId: string, enabled: boolean = true) {
  const getClient = useApiClient();
  return useQuery({
    queryKey: ["repo-info", projectId],
    queryFn: async () => {
      const client = await getClient();
      const { data } = await githubApi.getRepoInfo(client, projectId);
      return data;
    },
    enabled: !!projectId && enabled,
    staleTime: 5 * 60 * 1000,
  });
}
