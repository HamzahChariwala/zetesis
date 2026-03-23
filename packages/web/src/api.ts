const BASE = '/api/v1';

export type RequestType = 'deep_dive' | 'literature_review' | 'idea_exploration' | 'fact_check';
export type RequestStatus = 'queued' | 'processing' | 'completed' | 'failed';
export type OutputStatus = 'unchecked' | 'approved' | 'deleted';
export type ReviewAction = 'approve' | 'comment' | 'follow_up' | 'delete';

export interface ResearchRequest {
  id: string;
  query: string;
  request_type: RequestType;
  tags: string[];
  context: string | null;
  priority: number;
  model_id: string | null;
  tools: string[];
  status: RequestStatus;
  parent_id: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
}

export interface ResearchOutput {
  id: string;
  request_id: string;
  content: string;
  model_id: string;
  status: OutputStatus;
  inference_time_ms: number | null;
  token_count: number | null;
  truncated: boolean;
  rating: number | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface Review {
  id: string;
  output_id: string;
  action: ReviewAction;
  comment: string | null;
  follow_up_request_id: string | null;
  created_at: string;
}

export interface SimilarOutput {
  output: ResearchOutput;
  score: number;
  query: string | null;
}

export interface ModelDownload {
  status: 'idle' | 'downloading' | 'complete' | 'failed';
  progress: number;
  error: string | null;
}

export interface ModelInfo {
  id: string;
  label: string;
  size_gb: number;
  downloaded: boolean;
  download: ModelDownload | null;
}

export interface ToolInfo {
  name: string;
  description: string;
}

export interface QueueStatus {
  queued: number;
  processing: number;
  completed: number;
  failed: number;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (res.status === 204) return undefined as T;
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

export const api = {
  requests: {
    create: (data: {
      query: string;
      request_type: RequestType;
      tags?: string[];
      context?: string;
      priority?: number;
      model_id?: string;
      tools?: string[];
    }) => request<ResearchRequest>('/requests', { method: 'POST', body: JSON.stringify(data) }),
    list: (params?: Record<string, string>) => {
      const qs = params ? '?' + new URLSearchParams(params).toString() : '';
      return request<ResearchRequest[]>(`/requests${qs}`);
    },
    get: (id: string) => request<ResearchRequest>(`/requests/${id}`),
    cancel: (id: string) => request<void>(`/requests/${id}`, { method: 'DELETE' }),
    retry: (id: string) => request<ResearchRequest>(`/requests/${id}/retry`, { method: 'POST' }),
  },
  outputs: {
    list: (params?: Record<string, string>) => {
      const qs = params ? '?' + new URLSearchParams(params).toString() : '';
      return request<ResearchOutput[]>(`/outputs${qs}`);
    },
    get: (id: string) => request<ResearchOutput>(`/outputs/${id}`),
    rate: (id: string, rating: number) => request<ResearchOutput>(`/outputs/${id}/rate`, {
      method: 'PATCH', body: JSON.stringify({ rating }),
    }),
  },
  reviews: {
    create: (outputId: string, data: {
      action: ReviewAction;
      comment?: string;
      follow_up_query?: string;
    }) => request<Review>(`/outputs/${outputId}/review`, { method: 'POST', body: JSON.stringify(data) }),
    list: (outputId: string) => request<Review[]>(`/outputs/${outputId}/reviews`),
  },
  knowledge: {
    search: (q: string, limit?: number) => {
      const params = new URLSearchParams({ q, limit: String(limit ?? 10) });
      return request<SimilarOutput[]>(`/knowledge/search?${params}`);
    },
    similar: (outputId: string, limit?: number) => {
      const params = limit ? `?limit=${limit}` : '';
      return request<SimilarOutput[]>(`/knowledge/${outputId}/similar${params}`);
    },
  },
  system: {
    health: () => request<{ status: string; database: boolean }>('/system/health'),
    queueStatus: () => request<QueueStatus>('/system/queue/status'),
    models: () => request<{ default: string; models: ModelInfo[] }>('/system/models'),
    tools: () => request<{ tools: ToolInfo[] }>('/system/tools'),
    downloadModel: (modelId: string) => request<{ status: string; model_id: string }>(
      '/system/models/download', { method: 'POST', body: JSON.stringify({ model_id: modelId }) }
    ),
  },
};
