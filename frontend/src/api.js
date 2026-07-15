import axios from 'axios';

// The canonical production frontend is the Cloudflare Worker at
// autonomous-ai-agency.strikersam.workers.dev — it reverse-proxies every
// /api/* call to the Render backend (same-origin, no CORS). The GitHub Pages
// site at strikersam.github.io/autonomous-ai-agency/ is a secondary mirror
// and MUST point its API calls at the worker (not window.location.origin,
// which 404s on github.io). When REACT_APP_BACKEND_URL is unset at build
// time, we fall back to the worker URL so a stale-tenant GitHub Pages deploy
// still has working social-login buttons instead of 404ing on /api/auth/*.
const PRODUCTION_WORKER_URL = 'https://autonomous-ai-agency.strikersam.workers.dev';

function getDefaultBackendUrl() {
  if (process.env.REACT_APP_BACKEND_URL) {
    return process.env.REACT_APP_BACKEND_URL;
  }
  if (typeof window !== 'undefined' && window.location?.origin) {
    // Same-origin deploy (Cloudflare Worker, local dev, Render onboarding
    // running its own frontend) — /api/* is served by the same origin.
    // Detect github.io specifically because Pages does NOT proxy /api/* —
    // social login buttons would navigate to a 404.
    const host = window.location.host || '';
    const isGitHubPages = host.endsWith('.github.io');
    if (isGitHubPages) {
      return PRODUCTION_WORKER_URL;
    }
    return window.location.origin;
  }
  return '';
}

export function getBackendUrl() {
  return localStorage.getItem('backend_url') || getDefaultBackendUrl();
}

export function getAccessToken() {
  return localStorage.getItem('access_token') || '';
}

export function getAuthHeaders() {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function getPublicPath(path = '') {
  const base = (process.env.PUBLIC_URL || '').replace(/\/$/, '');
  if (!path) return base || '/';
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${base}${normalizedPath}` || normalizedPath;
}

function getApiUrl(path) {
  const base = getBackendUrl();
  return base ? `${base}${path}` : path;
}

export function setBackendUrl(url) {
  const cleaned = url.replace(/\/$/, '');
  localStorage.setItem('backend_url', cleaned);
  API.defaults.baseURL = cleaned;
}

export const API = axios.create({
  baseURL: getBackendUrl(),
  headers: { 'Content-Type': 'application/json' },
});

// Attach Bearer token and resolve dynamic backend URL on every request
API.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // Always use the latest stored backend URL (user may change it in setup wizard)
  if (!config.baseURL || config.baseURL === '') {
    config.baseURL = getBackendUrl();
  }
  return config;
});

// On network errors (CORS, connection refused, DNS failure), self-heal the
// backend URL.  Only clears the stored URL on specific connectivity errors
// (ECONNREFUSED, CORS, ERR_NETWORK) — NOT on transient timeouts or flaky DNS.
let isRefreshing = false;
let refreshQueue = [];
API.interceptors.response.use(
  (res) => res,
  async (error) => {
    const orig = error.config || {};

    // ── Self-heal on CORS / connection-refused errors ──────────────────────
    if (!error.response && !orig._corsHeal && !orig.url?.startsWith('http')) {
      const msg = (error.message || '').toLowerCase();
      const isConnectionError = (
        error.code === 'ERR_NETWORK' ||
        msg.includes('network error') ||
        msg.includes('cors') ||
        msg.includes('econnrefused') ||
        msg.includes('connection refused')
      );
      if (isConnectionError && localStorage.getItem('backend_url')) {
        orig._corsHeal = true;
        localStorage.removeItem('backend_url');
        API.defaults.baseURL = getDefaultBackendUrl();
        orig.baseURL = getDefaultBackendUrl();
        return API(orig);
      }
    }

    if (error.response?.status === 401 && !orig._retry && !orig.url?.includes('/auth/')) {
      orig._retry = true;
      const refresh = localStorage.getItem('refresh_token');
      if (!refresh) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = getPublicPath('/login');
        return Promise.reject(error);
      }
      if (isRefreshing) {
        // Queue this request to retry after the in-flight refresh completes
        return new Promise((resolve, reject) => {
          refreshQueue.push({ resolve, reject });
        }).then((token) => {
          orig.headers.Authorization = `Bearer ${token}`;
          return API(orig);
        });
      }
      isRefreshing = true;
      try {
        const { data } = await axios.post(
          getApiUrl('/api/auth/refresh'),
          { refresh_token: refresh },
        );
        localStorage.setItem('access_token', data.access_token);
        orig.headers.Authorization = `Bearer ${data.access_token}`;
        // Flush queued requests with the new token
        refreshQueue.forEach(({ resolve }) => resolve(data.access_token));
        refreshQueue = [];
        return API(orig);
      } catch {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        refreshQueue.forEach(({ reject }) => reject(error));
        refreshQueue = [];
        window.location.href = getPublicPath('/login');
      } finally {
        isRefreshing = false;
      }
    }
    return Promise.reject(error);
  }
);

export function fmtErr(detail) {
  // Return null (not a hardcoded string) when there's no detail to format —
  // every call site chains `api.fmtErr(...) || e?.message || 'fallback'`, and
  // a truthy placeholder here would always win that chain, permanently
  // hiding the more specific e.message (e.g. "timeout of 25000ms exceeded",
  // "Network Error") and the call site's own descriptive fallback text
  // behind a generic "Something went wrong."
  if (detail == null) return null;
  if (typeof detail === 'string') return detail;
  if (detail.message) return detail.message;
  if (Array.isArray(detail)) return detail.map(e => {
    const field = Array.isArray(e?.loc) ? e.loc[e.loc.length - 1] : null;
    const msg = e?.msg || JSON.stringify(e);
    return field && field !== 'body' ? `${field}: ${msg}` : msg;
  }).join('; ');
  return detail?.msg || String(detail);
}

// Auth
export const login = async (email, password) => {
  try {
    return await API.post('/api/auth/login', { email, password });
  } catch (error) {
    // Self-heal when a stale backend_url points to a dead/invalid endpoint.
    if (!error?.response && localStorage.getItem('backend_url')) {
      localStorage.removeItem('backend_url');
      API.defaults.baseURL = getDefaultBackendUrl();
      return API.post('/api/auth/login', { email, password });
    }
    throw error;
  }
};
export const logout = () => {
  localStorage.removeItem('access_token');
  localStorage.removeItem('refresh_token');
  return Promise.resolve();
};
export const getMe = () => API.get('/api/auth/me');

// Chat
export const chatSend = (content, sessionId, model, providerId, temperature, agentMode = false, allowCommercialFallbackOnce = false, context = null, repoUrl = null, repoRef = null) =>
  API.post('/api/chat/send', {
    content,
    session_id: sessionId,
    model: model || null,
    provider_id: providerId || null,
    temperature: temperature ?? null,
    agent_mode: agentMode,
    allow_commercial_fallback_once: allowCommercialFallbackOnce,
    ...(context ? { context } : {}),
    ...(repoUrl ? { repo_url: repoUrl } : {}),
    ...(repoRef ? { repo_ref: repoRef } : {}),
  });
export const getAgentChatJob = (jobId) => API.get(`/api/chat/agent-jobs/${jobId}`);
export const cancelAgentChatJob = (jobId) => API.post(`/api/chat/agent-jobs/${jobId}/cancel`);
export const resumeAgentChatJob = (sessionId, action, input = "") => API.post(`/api/chat/resume/${sessionId}`, { action, input });
export const listSessions = () => API.get('/api/chat/sessions');
export const getSession = (id) => API.get(`/api/chat/sessions/${id}`);
export const deleteSession = (id) => API.delete(`/api/chat/sessions/${id}`);

// Wiki
export const listWikiPages = (q) => API.get('/api/wiki/pages', { params: q ? { q } : {} });
export const getWikiPage = (slug) => API.get(`/api/wiki/pages/${slug}`);
export const createWikiPage = (data) => API.post('/api/wiki/pages', data);
export const updateWikiPage = (slug, data) => API.put(`/api/wiki/pages/${slug}`, data);
export const deleteWikiPage = (slug) => API.delete(`/api/wiki/pages/${slug}`);
export const lintWiki = () => API.post('/api/wiki/lint');

// Sources
export const ingestSource = (formData) => API.post('/api/sources/ingest', formData, { headers: { 'Content-Type': 'multipart/form-data' } });
export const listSources = () => API.get('/api/sources');
export const getSource = (id) => API.get(`/api/sources/${id}`);
export const deleteSource = (id) => API.delete(`/api/sources/${id}`);

// Activity & Stats
export const getActivity = (limit = 50) => API.get('/api/activity', { params: { limit } });
export const getStats = () => API.get('/api/stats');

// Providers
export const listProviders = () => API.get('/api/providers');
export const createProvider = (data) => API.post('/api/providers', data);
export const updateProvider = (id, data) => API.put(`/api/providers/${id}`, data);
export const deleteProvider = (id) => API.delete(`/api/providers/${id}`);
export const testProvider = (id) => API.post(`/api/providers/${id}/test`);
export const listProviderModels = (id) => API.get(`/api/providers/${encodeURIComponent(id)}/models`);

// Models
export const listModels = () => API.get('/api/models');
export const pullModel = (name) => API.post('/api/models/pull', { name });
export const deleteModel = (name) => API.delete(`/api/models/${encodeURIComponent(name)}`);

// API key management lives in the admin portal (AdminPortalPage) and talks
// to /admin/api/users/* directly. The legacy /api/keys helpers were removed
// when ApiKeysPage.js was consolidated into AdminPortalPage.

// Observability
export const getObservabilityStatus = () => API.get('/api/observability/status');
export const getObservabilityMetrics = () => API.get('/api/observability/metrics');
export const getObservabilityDashboard = () => API.get('/api/observability/dashboard-url');

// Platform
export const getPlatformInfo = () => API.get('/api/platform');
export const healthCheck = () => API.get('/api/health');

// GitHub Integration
export const githubStatus = () => API.get('/api/github/status');
export const getGithubStatus = githubStatus; // alias used by GitHubAccessSection
export const startGithubOAuth = (redirect = false) =>
  API.post('/api/github/oauth/start', null, redirect ? { params: { redirect: 'true' } } : {});
export const setGithubToken = (token) => API.put('/api/github/token', { token });
export const deleteGithubToken = () => API.delete('/api/github/token');
export const listGithubRepos = (q = '', page = 1) => API.get('/api/github/repos', { params: { q, page } });
export const listGithubBranches = (owner, repo) => API.get(`/api/github/repos/${owner}/${repo}/branches`);
export const getGithubTree = (owner, repo, ref = 'HEAD', path = '') =>
  API.get(`/api/github/repos/${owner}/${repo}/tree`, { params: { ref, path } });
export const readGithubFile = (owner, repo, path, ref = 'HEAD') =>
  API.get(`/api/github/repos/${owner}/${repo}/file`, { params: { path, ref } });
export const writeGithubFile = (owner, repo, data) =>
  API.put(`/api/github/repos/${owner}/${repo}/file`, data);
export const listGithubPulls = (owner, repo, state = 'open') =>
  API.get(`/api/github/repos/${owner}/${repo}/pulls`, { params: { state } });
export const createGithubPR = (owner, repo, data) =>
  API.post(`/api/github/repos/${owner}/${repo}/pulls`, data);
export const authorizeGithubRepos = (repoNames) => API.post('/api/github/authorize-repos', { repo_names: repoNames });

// ── Runtimes (v3) ─────────────────────────────────────────────────────────────
export const listRuntimes = () => API.get('/runtimes/');
export const getRuntime = (id) => API.get(`/runtimes/${id}`);
export const getRuntimeHealth = () => API.get('/runtimes/health');
export const refreshRuntimeHealth = () => API.post('/runtimes/health/refresh');
export const getRoutingPolicy = () => API.get('/runtimes/policy');
export const updateRoutingPolicy = (data) => API.put('/runtimes/policy', data);
export const getDecisionLog = (limit = 100) => API.get('/runtimes/decisions', { params: { limit } });
export const runTaskOnRuntime = (runtimeId, data) => API.post(`/runtimes/${runtimeId}/run`, data);
export const startRuntime = (runtimeId) => API.post(`/runtimes/${runtimeId}/start`);
export const stopRuntime = (runtimeId) => API.post(`/runtimes/${runtimeId}/stop`);
export const startAllRuntimes = () => API.post('/runtimes/start-all');
export const stopAllRuntimes = () => API.post('/runtimes/stop-all');

// E2B sandbox integration status (roadmap ★5). Backend endpoint at
// /runtimes/e2b/status returns {enabled, sdk_installed, healthy, template,
// timeout_sec, error}. Falls back gracefully (returns null) on network error.
export const getE2BStatus = async () => {
  try {
    const { data } = await API.get('/runtimes/e2b/status');
    return data;
  } catch (e) {
    return null;
  }
};

// ── Tasks (v3) ────────────────────────────────────────────────────────────────
export const listTasks = (params = {}) => API.get('/api/tasks/', { params });
export const createTask = (data) => API.post('/api/tasks/', data);
export const getTask = (id) => API.get(`/api/tasks/${id}`);
export const updateTask = (id, data) => API.patch(`/api/tasks/${id}`, data);
export const deleteTask = (id) => API.delete(`/api/tasks/${id}`);
export const retryTask = (id) => API.post(`/api/tasks/${id}/retry`);
export const escalateTask = (id) => API.post(`/api/tasks/${id}/escalate`);
export const runTask = (id) => API.post(`/api/tasks/${id}/run`);
export const addTaskComment = (id, data) => API.post(`/api/tasks/${id}/comments`, data);
export const approveTaskCheckpoint = (id, data) => API.post(`/api/tasks/${id}/approve`, data);
export const getTaskCounts = () => API.get('/api/tasks/counts');
export const getDueSoonTasks = (withinHours = 24) =>
  API.get('/api/tasks/due-soon', { params: { within_hours: withinHours } });
export const followUpTask = (id, data) => API.post(`/api/tasks/${id}/follow-up`, data);
export const clarifyTask = (id, data) => API.patch(`/api/tasks/${id}/clarify`, data);

// ── Agile sprints ─────────────────────────────────────────────────────────────
export const fetchSprints = () => API.get('/api/agile/sprints');
export const createSprint = (data) => API.post('/api/agile/sprints', data);
export const startSprint = (id, data = {}) => API.post(`/api/agile/sprints/${id}/start`, data);
export const completeSprint = (id) => API.post(`/api/agile/sprints/${id}/complete`);
export const fetchVelocity = () => API.get('/api/agile/velocity');

// ── Agents (v3) ───────────────────────────────────────────────────────────────
export const listAgents = () => API.get('/api/agents/');
export const createAgent = (data) => API.post('/api/agents/', data);
export const getAgent = (id) => API.get(`/api/agents/${id}`);
export const updateAgent = (id, data) => API.put(`/api/agents/${id}`, data);
export const deleteAgent = (id) => API.delete(`/api/agents/${id}`);

// ── Audit log (v3) ────────────────────────────────────────────────────────────
export const getAuditLog = (limit = 100) => API.get('/api/activation/audit-log', { params: { limit } });

// ── Hardware (v3.1) ───────────────────────────────────────────────────────────
export const getHardwareProfile = () => API.get('/api/hardware/profile');
export const refreshHardwareProfile = () => API.get('/api/hardware/profile/refresh');
export const checkModelCompatibility = (modelName) =>
  API.get(`/api/hardware/compatibility/${encodeURIComponent(modelName)}`);
export const batchModelCompatibility = (models) =>
  API.post('/api/hardware/compatibility/batch', { models });

// ── Secrets (v3.1) ────────────────────────────────────────────────────────────
export const listSecrets = () => API.get('/api/secrets/');
export const createSecret = (data) => API.post('/api/secrets/', data);
export const getSecretMeta = (id) => API.get(`/api/secrets/${id}`);
export const updateSecret = (id, data) => API.put(`/api/secrets/${id}`, data);
export const deleteSecret = (id) => API.delete(`/api/secrets/${id}`);

// ── Social auth (v3.1) ────────────────────────────────────────────────────────
export const listUsers = () => API.get('/api/activation/users');
export const changeUserRole = (userId, role) =>
  API.post(`/api/activation/users/${userId}/role`, { role });
export const setUserOnboarding = (userId, allowed) =>
  API.put(`/api/activation/users/${userId}/onboarding`, { allowed });

// Global onboarding-gate + ephemeral-company settings (admin)
export const getOnboardingSettings = () => API.get('/api/activation/settings');
export const updateOnboardingSettings = (data) =>
  API.put('/api/activation/settings', data);

// Lifecycle / ephemerality status for the current user's agencies (banner)
export const getAccountLifecycle = () => API.get('/api/company/account/lifecycle');

// ── API keys (admin) ──────────────────────────────────────────────────────────
export const listApiKeys = () => API.get('/api/keys');
export const createApiKey = (data) => API.post('/api/keys', data);
export const deleteApiKey = (keyId) => API.delete(`/api/keys/${keyId}`);

// ── Setup wizard (v3.1) ───────────────────────────────────────────────────────
export const getSetupState = () => API.get('/api/setup/state');
export const saveSetupStep = (step, data) => API.put(`/api/setup/step/${step}`, data);
export const completeSetup = () => API.post('/api/setup/complete');
export const detectHardwareForSetup = () => API.get('/api/setup/detect/hardware');
export const detectModelsForSetup = (ollamaUrl) =>
  API.get('/api/setup/detect/models', { params: { ollama_url: ollamaUrl } });

// ── Cost insights / observability (v3.1) ──────────────────────────────────────
export const getSavings = (period = 'month', bucket = 'day') =>
  API.get('/api/observability/savings', { params: { period, bucket } });
export const getUserSavings = (userId, period = 'month') =>
  API.get(`/api/observability/savings/${userId}`, { params: { period } });
export const getUsage = (period = 'month') =>
  API.get('/api/observability/usage', { params: { period } });

// ── GitHub workspace (v3.1) ───────────────────────────────────────────────────
export const listGithubReposV2 = () => API.get('/api/github/repos');
export const getGithubRepo = (owner, repo) => API.get(`/api/github/repos/${owner}/${repo}`);
export const listGithubBranchesV2 = (owner, repo) =>
  API.get(`/api/github/repos/${owner}/${repo}/branches`);
export const listGithubPRs = (owner, repo, state = 'open') =>
  API.get(`/api/github/repos/${owner}/${repo}/pulls`, { params: { state } });
export const initWorkspace = (owner, repo) =>
  API.post(`/api/github/repos/${owner}/${repo}/workspace/init`);
export const getWorkspaceStatus = (owner, repo) =>
  API.get(`/api/github/repos/${owner}/${repo}/workspace/status`);
export const getWorkspaceDiff = (owner, repo) =>
  API.get(`/api/github/repos/${owner}/${repo}/workspace/diff`);
export const commitWorkspace = (owner, repo, data) =>
  API.post(`/api/github/repos/${owner}/${repo}/workspace/commit`, data);

// ── Schedules (Control Plane) ────────────────────────────────────────────────
export const listSchedules = () => API.get('/api/schedules/');
export const createSchedule = (data) => API.post('/api/schedules/', data);
export const getSchedule = (id) => API.get(`/api/schedules/${id}`);
export const triggerSchedule = (id) => API.post(`/api/schedules/${id}/run`);
export const deleteSchedule = (id) => API.delete(`/api/schedules/${id}`);
export const pauseSchedule = (id) => API.patch(`/api/schedules/${id}`, { status: 'paused' });
export const resumeSchedule = (id) => API.patch(`/api/schedules/${id}`, { status: 'active' });

// ── Workspace sync (v3.1) ─────────────────────────────────────────────────────
export const getSyncStatus = () => API.get('/api/sync/status');
export const listSyncPeers = () => API.get('/api/sync/peers');
export const addSyncPeer = (data) => API.post('/api/sync/peers', data);
export const removeSyncPeer = (id) => API.delete(`/api/sync/peers/${id}`);
export const pushFolder = (folder) => API.post(`/api/sync/push/${folder}`);
export const pullFolder = (folder) => API.post(`/api/sync/pull/${folder}`);
export const listSyncConflicts = () => API.get('/api/sync/conflicts');
export const resolveConflict = (id) => API.post(`/api/sync/conflicts/${id}/resolve`);

// ── Company Graph & Onboarding (v5.0) ─────────────────────────────────────────
export const listCompanies = (params = {}) => API.get('/api/company', { params });
export const createCompany = (data) => API.post('/api/company', data);
export const getCompany = (id) => API.get(`/api/company/${id}`);
export const updateCompany = (id, data) => API.patch(`/api/company/${id}`, data);
export const getCompanyGraph = (id) => API.get(`/api/company/${id}/graph`);
export const syncCompanyGraph = (id) => API.post(`/api/company/${id}/graph/sync`);
export const scanWebsite = (id, url) => API.post(`/api/company/${id}/scan/website`, { website_url: url });
export const scanRepo = (id, url) => API.post(`/api/company/${id}/scan/repo`, { repo_url: url });
export const listSpecialists = (id) => API.get(`/api/company/${id}/specialists`);
export const provisionSpecialist = (id, data) => API.post(`/api/company/${id}/specialists`, data);
export const matchSpecialists = (id, systems) => API.post(`/api/company/${id}/specialists/match`, systems);
export const getOnboardingProgress = (id) => API.get(`/api/company/${id}/onboarding`);
export const startOnboarding = (id, data, config) => API.post(`/api/company/${id}/onboarding/start`, data, config);
export const submitOnboardingAnswers = (id, data) => API.post(`/api/company/${id}/onboarding/answers`, data);
export const pauseOnboarding = (id) => API.post(`/api/company/${id}/onboarding/pause`);
export const resumeOnboarding = (id) => API.post(`/api/company/${id}/onboarding/resume`);
export const cancelOnboarding = (id) => API.post(`/api/company/${id}/onboarding/cancel`);
export const deleteCompany = (id) => API.delete(`/api/company/${id}`);
export const getPublicDoctorReport = () => API.get('/api/company/doctor/public');

// ── SEO / GEO / AIO Audit (v5.1) ──────────────────────────────────────────────
export const getSeoChecks = () => API.get('/api/seo/checks');
export const runSeoAudit = (companyId, request) =>
  API.post(`/api/company/${companyId}/seo/audit`, request);
export const listSeoAudits = (companyId) =>
  API.get(`/api/company/${companyId}/seo/audits`);
export const getSeoAudit = (companyId, auditId) =>
  API.get(`/api/company/${companyId}/seo/audits/${auditId}`);
export const delegateSeoFindings = (companyId, auditId, data = {}) =>
  API.post(`/api/company/${companyId}/seo/audits/${auditId}/delegate`, data);
// Export endpoint returns text (csv/markdown/urls/issues) or JSON; fetch as blob.
export const exportSeoAudit = (companyId, auditId, fmt) =>
  API.get(`/api/company/${companyId}/seo/audits/${auditId}/export`, {
    params: { fmt },
    responseType: 'blob',
  });

// Trigger a browser download of an exported audit (csv / json / markdown / urls / issues).
export async function downloadSeoExport(companyId, auditId, fmt) {
  const resp = await exportSeoAudit(companyId, auditId, fmt);
  const ext = fmt === 'json' ? 'json' : (fmt === 'markdown' ? 'md' : 'csv');
  const url = window.URL.createObjectURL(new Blob([resp.data]));
  const a = document.createElement('a');
  a.href = url;
  a.download = `seo-audit-${auditId}-${fmt}.${ext}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  window.URL.revokeObjectURL(url);
}

// Wake company runtimes (Docker containers)
export const wakeCompanyRuntimes = (companyId = '') =>
  API.post('/runtimes/wake-company-runtimes', null, { params: companyId ? { company_id: companyId } : {} });

export default API;

// MCP Servers
export const listMcpServers   = ()         => API.get('/api/mcp/servers');
export const createMcpServer  = (data)     => API.post('/api/mcp/servers', data);
export const updateMcpServer  = (id, data) => API.patch(`/api/mcp/servers/${id}`, data);
export const deleteMcpServer  = (id)       => API.delete(`/api/mcp/servers/${id}`);

// Skills Registry
export const listSkills           = (params = {})  => API.get('/api/skills', { params });
export const refreshSkills        = ()              => API.post('/api/skills/refresh');
export const discoverRemoteSkills = ()              => API.get('/api/skills/discover');
export const recommendSkills      = (data)          => API.post('/api/skills/recommend', data);
export const autoRecommendSkills  = (params = {})   => API.get('/api/skills/recommend/auto', { params });
export const getSkill             = (skillId)       => API.get(`/api/skills/${encodeURIComponent(skillId)}`);

// Company Skills (v5 SkillBindings)
export const listCompanySkills    = (params = {})   => API.get('/api/company/skills', { params });
export const autoRecommendCompanySkills = (companyId) =>
  API.get('/api/company/skills/recommend/auto', { params: { company_id: companyId } });
export const getCompanySkill      = (skillId)       => API.get(`/api/company/skills/${encodeURIComponent(skillId)}`);
export const getSpecialistSkills  = (companyId, specialistId) =>
  API.get(`/api/company/${companyId}/specialists/${specialistId}/skills`);

// ── Portfolio + Agile board (v5.0) ────────────────────────────────────────────
export const getPortfolioBoard   = (horizonCapacity) =>
  API.get('/api/portfolio/board', { params: horizonCapacity ? { horizon_capacity: horizonCapacity } : {} });
export const addPortfolioInitiative = (data)         => API.post('/api/portfolio/initiatives', data);
export const removePortfolioInitiative = (id)        => API.delete(`/api/portfolio/initiatives/${encodeURIComponent(id)}`);
export const refreshPortfolio    = ()                => API.post('/api/portfolio/refresh');

// ── Quick Notes (iPhone Shortcut + FAB) ────────────────────────────────────
export const createQuickNote = (data) => API.post('/v1/quick-notes', data);
export const listQuickNotes = () => API.get('/v1/quick-notes');

// ── Agency Status ───────────────────────────────────────────────────────────
export const getAgencyStatus = () => API.get('/agent/agency/status');

// ── Provider Policy ─────────────────────────────────────────────────────────
export const getProviderPolicy    = ()     => API.get('/api/providers/policy');
export const updateProviderPolicy = (data) => API.put('/api/providers/policy', data);

// ── Brain config (DB-persisted, UI-switchable) ─────────────────────────────
// PR #824 follow-up: change the agency's brain (provider + planner/executor/
// verifier/judge models) from the admin UI in one click, persisted in the DB,
// with no redeploy. Hard constraint: PATCH probes each changed model for
// liveness before save and refuses (422) any that 404/410.
export const getBrainConfig       = ()                  => API.get('/admin/api/policy/brain');
export const patchBrainConfig     = (patch)             => API.patch('/admin/api/policy/brain', patch);
export const testBrainModel       = (provider, model, baseUrl) => API.post('/admin/api/policy/brain/test', { provider, model, base_url: baseUrl || null });

// ── Local GLM-5.2 brain toggle (cross-machine) ─────────────────────────
// Reads the operator's intent + the most recent local-daemon heartbeat
// from the cloud, and flips the toggle from the Cloudflare-deployed admin
// Providers page. ``scripts/local_controller.py`` polls every 30s and
// starts/stops llama-server.exe on the operator's machine accordingly.
// Auth: X-Service-Token (same SERVICE_TOKEN the local daemon carries).
export const getLocalBrainState   = ()       => API.get('/api/local-brain/state');
export const postLocalBrainToggle = (data)  => API.post('/api/local-brain/toggle', data);
// Heartbeat POST is for the local daemon, not the admin SPA; not exported.

// Loop Engineering fleet view — catalogued autonomous loops + loop-audit
// readiness score, loop-cost estimate, and drift status. Powers the Loops screen.
export const getLoops             = ()                  => API.get('/api/loops');

// ── SAM Voice Agent (issue #666) ──────────────────────────────────────────
export const samStatus = () => API.get('/agent/sam/status');
export const samChat   = (text, sessionId) => API.post('/agent/sam/chat', { text, session_id: sessionId || 'default' });
export const samSpeak  = (text) => API.post('/agent/sam/speak', { text });
