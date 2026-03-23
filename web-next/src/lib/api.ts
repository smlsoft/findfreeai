const PROXY = "/v1";
const API = "/api";

export async function fetchJSON<T = unknown>(url: string): Promise<T | null> {
  try {
    const r = await fetch(url + "?" + Date.now());
    return r.ok ? r.json() : null;
  } catch {
    return null;
  }
}

export async function postJSON<T = unknown>(url: string, body?: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  return r.json();
}

// Proxy APIs
export const getProxyInfo = () => fetchJSON(`${PROXY}/`);
export const getModels = () => fetchJSON<{ object: string; data: Model[] }>(`${PROXY}/models`);
export const getProviders = () => fetchJSON<{ providers: Provider[] }>(`${PROXY}/providers`);
export const getProxyLogs = () => fetchJSON<LogEntry[]>(`${PROXY}/logs`);
export const getSkills = () => fetchJSON(`${PROXY}/rag/skills`);
export const getSessions = () => fetchJSON(`${PROXY}/rag/sessions`);
export const reloadProviders = () => fetchJSON(`${PROXY}/reload`);
export const getConfig = () => fetchJSON(`${PROXY}/config`);
export const postConfig = (cfg: Record<string, unknown>) => postJSON(`${PROXY}/config`, cfg);
export const getCosts = () => fetchJSON(`${PROXY}/costs`);
export const getCache = () => fetchJSON(`${PROXY}/cache`);
export const clearCache = () => postJSON(`${PROXY}/cache/clear`);
export const getVirtualKeys = () => fetchJSON<{ keys: VirtualKey[] }>(`${PROXY}/virtual-keys`);
export const postVirtualKey = (body: Record<string, unknown>) => postJSON(`${PROXY}/virtual-keys`, body);

// Dashboard APIs
export const getKeys = () => fetchJSON<{ keys: Record<string, string>; count: number }>(`${API}/keys`);
export const testOneKey = (env_name: string, key?: string) =>
  postJSON<KeyTestResult>(`${API}/test-one-key`, { env_name, ...(key ? { key } : {}) });
export const startScan = () => postJSON(`${API}/scan`);
export const startTestKeys = () => postJSON(`${API}/test-keys`);
export const startBrain = () => postJSON(`${API}/brain`);
export const getDashLogs = () => fetchJSON<DashLog[]>(`${API}/logs`);
export const getBrainLogs = () => fetchJSON<BrainLog[]>(`${API}/brain/logs`);
export const getBrainRecs = () => fetchJSON(`${API}/brain/recommendations`);
export const getData = () => fetchJSON(`${API}/data`);
export const getStatus = () => fetchJSON<{ scanning: boolean }>(`${API}/status`);

// Chat
export async function chatCompletion(
  model: string,
  messages: ChatMessage[],
  sessionId: string,
  stream = false
) {
  return fetch(`${PROXY}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-ID": sessionId,
    },
    body: JSON.stringify({ model, messages, stream, max_tokens: 2048 }),
  });
}

// Types
export interface Provider {
  id: string;
  name: string;
  has_key: boolean;
  models: string[];
  default_model: string;
  priority: number;
  stats: {
    success: number;
    fail: number;
    avg_latency: number;
    last_error: string;
    last_ok: string;
    rpm_count: number;
  };
  max_rpm: number;
}

export interface Model {
  id: string;
  object: string;
  owned_by: string;
  provider?: string;
}

export interface LogEntry {
  time: string;
  provider: string;
  model: string;
  status: string;
  latency_ms: number;
  error: string;
  reason: string;
}

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface VirtualKey {
  id: string;
  name: string;
  daily_limit: number;
  rpm_limit: number;
  usage_today: number;
  active: boolean;
  created: string;
  expires: string;
}

export interface KeyTestResult {
  status: string;
  score?: number;
  message?: string;
}

export interface DashLog {
  time: string;
  msg: string;
  level: string;
}

export interface BrainLog {
  time: string;
  msg: string;
  level: string;
}
