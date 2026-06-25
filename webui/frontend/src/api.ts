// When the frontend is deployed separately (e.g. GitHub Pages), set the
// VITE_API_BASE build-time env var to the backend URL (e.g. https://your-app.onrender.com).
// When served by the proxy itself (Render single-container, local dev), leave it
// empty — relative paths work automatically.

const API_BASE: string = (import.meta as any).env?.VITE_API_BASE ?? "";

export type Provider = {
  provider_id: string;
  name: string;
  base_url: string;
  default_model?: string | null;
  default_temperature?: number;
  has_api_key?: boolean;
  kind?: "openai_compat" | "anthropic";
  priority?: number;
};

export type ProviderRoleTag = {
  is_brain: boolean;
  role: "brain" | "sub-agent" | "fallback" | "unconfigured" | "available";
  reason: string;
  // Echoed back from brain_policy so the Admin SPA can match role tags to
  // operators' locally-defined webui provider records (which use a separate
  // provider_id namespace than the backend Mongo store).
  base_url?: string;
  name?: string;
};

export type BrainResolution = {
  provider_id: string;
  base_url: string;
  model: string | null;
  role: string;
  free_tier: boolean;
  source: string;
  priority: number;
} | null;

export type BrainPolicy = {
  resolution: BrainResolution;
  allow_paid_brain: boolean;
  env_var: "ALLOW_PAID_BRAIN";
  hint: string;
};

export type Workspace = {
  workspace_id: string;
  name: string;
  kind: "local" | "git";
  path: string;
  git_url?: string | null;
  git_ref?: string | null;
};

export type AgentSession = {
  session_id: string;
  title: string;
  provider_id?: string | null;
  workspace_id?: string | null;
  created_at: string;
  updated_at: string;
  history: { role: "user" | "assistant" | "system"; content: string }[];
  last_plan?: any;
  last_result?: any;
};

function authHeaders(apiKey: string | null): Record<string, string> {
  if (!apiKey) return {};
  return { Authorization: `Bearer ${apiKey}` };
}

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

async function apiError(r: Response): Promise<never> {
  const text = await r.text();
  let message = text || `HTTP ${r.status}`;
  try {
    const data = JSON.parse(text);
    if (typeof data.detail === "string") {
      message = data.detail;
    } else if (Array.isArray(data.detail)) {
      message = data.detail
        .map((e: any) => (typeof e === "string" ? e : e.msg ?? JSON.stringify(e)))
        .join("; ") || text;
    }
  } catch {
    // Non-JSON body — fall through to status-based message.
  }
  throw new ApiError(r.status, message);
}

export async function getBootstrap(): Promise<any> {
  const r = await fetch(`${API_BASE}/ui/api/bootstrap`);
  if (!r.ok) return apiError(r);
  return r.json();
}

export async function listProviders(apiKey: string): Promise<Provider[]> {
  const r = await fetch(`${API_BASE}/ui/api/providers`, { headers: authHeaders(apiKey) });
  if (!r.ok) return apiError(r);
  const data = await r.json();
  return data.providers;
}

export async function listProviderModels(apiKey: string, providerId: string): Promise<string[]> {
  const r = await fetch(`${API_BASE}/ui/api/providers/${encodeURIComponent(providerId)}/models`, {
    headers: authHeaders(apiKey),
  });
  if (!r.ok) return apiError(r);
  const data = await r.json();
  return data.models ?? [];
}

export async function listWorkspaces(apiKey: string): Promise<Workspace[]> {
  const r = await fetch(`${API_BASE}/ui/api/workspaces`, { headers: authHeaders(apiKey) });
  if (!r.ok) return apiError(r);
  const data = await r.json();
  return data.workspaces;
}

export async function listFiles(apiKey: string, workspaceId: string, path: string, limit = 200): Promise<string[]> {
  const base = API_BASE || window.location.origin;
  const u = new URL(`${API_BASE}/ui/api/workspaces/${encodeURIComponent(workspaceId)}/files`, base);
  u.searchParams.set("path", path);
  u.searchParams.set("limit", String(limit));
  const r = await fetch(u.toString(), { headers: authHeaders(apiKey) });
  if (!r.ok) return apiError(r);
  const data = await r.json();
  return data.files ?? [];
}

export async function readFile(apiKey: string, workspaceId: string, path: string): Promise<string> {
  const base = API_BASE || window.location.origin;
  const u = new URL(`${API_BASE}/ui/api/workspaces/${encodeURIComponent(workspaceId)}/file`, base);
  u.searchParams.set("path", path);
  const r = await fetch(u.toString(), { headers: authHeaders(apiKey) });
  if (!r.ok) return apiError(r);
  const data = await r.json();
  return data.content ?? "";
}

export async function searchCode(apiKey: string, workspaceId: string, query: string): Promise<any[]> {
  const r = await fetch(`${API_BASE}/ui/api/workspaces/${encodeURIComponent(workspaceId)}/search`, {
    method: "POST",
    headers: { ...authHeaders(apiKey), "Content-Type": "application/json" },
    body: JSON.stringify({ query, limit: 50 }),
  });
  if (!r.ok) return apiError(r);
  const data = await r.json();
  return data.matches ?? [];
}

export async function createAgentSession(apiKey: string, title: string, providerId: string, workspaceId: string) {
  const r = await fetch(`${API_BASE}/agent/sessions`, {
    method: "POST",
    headers: { ...authHeaders(apiKey), "Content-Type": "application/json" },
    body: JSON.stringify({ title, provider_id: providerId, workspace_id: workspaceId }),
  });
  if (!r.ok) return apiError(r);
  return (await r.json()) as AgentSession;
}

export async function getAgentSession(apiKey: string, sessionId: string) {
  const r = await fetch(`${API_BASE}/agent/sessions/${encodeURIComponent(sessionId)}`, { headers: authHeaders(apiKey) });
  if (!r.ok) return apiError(r);
  return (await r.json()) as AgentSession;
}

export async function runAgent(
  apiKey: string,
  sessionId: string,
  instruction: string,
  model: string | null,
  providerId?: string | null,
) {
  const body: Record<string, any> = { instruction, max_steps: 5 };
  if (model)      body.model       = model;
  if (providerId) body.provider_id = providerId;
  const r = await fetch(`${API_BASE}/agent/sessions/${encodeURIComponent(sessionId)}/run`, {
    method: "POST",
    headers: { ...authHeaders(apiKey), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) return apiError(r);
  return await r.json();
}

/**
 * Ask the proxy what model it would route a given message to in auto mode.
 * Returns { resolved_model, task_category, selection_source } — best-effort,
 * safe to ignore on error.
 */
export async function previewRoute(apiKey: string, text: string): Promise<{
  resolved_model: string;
  task_category: string;
  selection_source: string;
} | null> {
  try {
    const r = await fetch(`${API_BASE}/ui/api/route`, {
      method: "POST",
      headers: { ...authHeaders(apiKey), "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!r.ok) {
      if (r.status === 401 || r.status === 403) {
        throw new ApiError(r.status, `Route preview unauthorized (HTTP ${r.status})`);
      }
      return null;
    }
    return await r.json();
  } catch (err) {
    if (err instanceof ApiError) throw err;
    return null;
  }
}

// --- Admin API ---

export async function adminLogin(username: string, password: string) {
  const r = await fetch(`${API_BASE}/admin/api/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!r.ok) return apiError(r);
  return r.json();
}

function adminHeaders(adminToken: string): Record<string, string> {
  return { Authorization: `Bearer ${adminToken}` };
}

export async function adminListProviders(adminToken: string) {
  const r = await fetch(`${API_BASE}/admin/api/providers`, { headers: adminHeaders(adminToken) });
  if (!r.ok) return apiError(r);
  return r.json();
}

export async function adminCreateProvider(adminToken: string, body: any) {
  const r = await fetch(`${API_BASE}/admin/api/providers`, {
    method: "POST",
    headers: { ...adminHeaders(adminToken), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) return apiError(r);
  return r.json();
}

export async function adminDeleteProvider(adminToken: string, providerId: string) {
  const r = await fetch(`${API_BASE}/admin/api/providers/${encodeURIComponent(providerId)}`, {
    method: "DELETE",
    headers: adminHeaders(adminToken),
  });
  if (!r.ok) return apiError(r);
  return r.json();
}

/** PATCH a single provider; supports priority + fields. Returns the admin-shaped {provider, admin} envelope. */
export async function adminUpdateProvider(
  adminToken: string,
  providerId: string,
  body: Partial<{
    name: string;
    base_url: string;
    api_key: string | null;
    default_model: string | null;
    default_temperature: number;
    kind: "openai_compat" | "anthropic";
    priority: number;
  }>,
): Promise<{ provider: Provider; admin: { username: string; auth_source: string } }> {
  const r = await fetch(`${API_BASE}/admin/api/providers/${encodeURIComponent(providerId)}`, {
    method: "PATCH",
    headers: { ...adminHeaders(adminToken), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) return apiError(r);
  return r.json();
}

/** Reorder providers by the desired top-to-bottom priority list. */
export async function adminReorderProviders(
  adminToken: string,
  providerIds: string[],
): Promise<{ ok: boolean; providers: Provider[]; admin: { username: string; auth_source: string } }> {
  const r = await fetch(`${API_BASE}/admin/api/providers/reorder`, {
    method: "POST",
    headers: { ...adminHeaders(adminToken), "Content-Type": "application/json" },
    body: JSON.stringify({ provider_ids: providerIds }),
  });
  if (!r.ok) return apiError(r);
  return r.json();
}

/** Read the canonical brain-role badges (brain / fallback / sub-agent / unconfigured) from the brain resolver. */
export async function adminGetProviderRoleTags(
  adminToken: string,
): Promise<{ role_tags: Record<string, ProviderRoleTag>; admin: { username: string; auth_source: string } }> {
  const r = await fetch(`${API_BASE}/admin/api/providers/role-tags`, {
    headers: adminHeaders(adminToken),
  });
  if (!r.ok) return apiError(r);
  return r.json();
}

/** Read the resolved CEO brain + the ALLOW_PAID_BRAIN paid-models policy (read-only). */
export async function adminGetBrainPolicy(
  adminToken: string,
): Promise<{ resolution: BrainResolution; allow_paid_brain: boolean; env_var: "ALLOW_PAID_BRAIN"; hint: string; admin: { username: string; auth_source: string }; }> {
  const r = await fetch(`${API_BASE}/admin/api/policy/brain`, {
    headers: adminHeaders(adminToken),
  });
  if (!r.ok) return apiError(r);
  return r.json();
}

export async function adminListWorkspaces(adminToken: string) {
  const r = await fetch(`${API_BASE}/admin/api/workspaces`, { headers: adminHeaders(adminToken) });
  if (!r.ok) return apiError(r);
  return r.json();
}

export async function adminCreateWorkspace(adminToken: string, body: any) {
  const r = await fetch(`${API_BASE}/admin/api/workspaces`, {
    method: "POST",
    headers: { ...adminHeaders(adminToken), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) return apiError(r);
  return r.json();
}

export async function adminDeleteWorkspace(adminToken: string, workspaceId: string) {
  const r = await fetch(`${API_BASE}/admin/api/workspaces/${encodeURIComponent(workspaceId)}`, {
    method: "DELETE",
    headers: adminHeaders(adminToken),
  });
  if (!r.ok) return apiError(r);
  return r.json();
}

export async function adminSyncWorkspace(adminToken: string, workspaceId: string) {
  const r = await fetch(`${API_BASE}/admin/api/workspaces/${encodeURIComponent(workspaceId)}/sync`, {
    method: "POST",
    headers: adminHeaders(adminToken),
  });
  if (!r.ok) return apiError(r);
  return r.json();
}

export async function adminRunCommand(adminToken: string, workspaceId: string, command: string[]) {
  const r = await fetch(`${API_BASE}/admin/api/commands/run`, {
    method: "POST",
    headers: { ...adminHeaders(adminToken), "Content-Type": "application/json" },
    body: JSON.stringify({ workspace_id: workspaceId, command, timeout_sec: 120 }),
  });
  if (!r.ok) return apiError(r);
  return r.json();
}

