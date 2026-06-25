import { useEffect, useMemo, useState } from "react";
import {
  adminCreateProvider,
  adminCreateWorkspace,
  adminDeleteProvider,
  adminDeleteWorkspace,
  adminGetBrainPolicy,
  adminGetProviderRoleTags,
  adminListProviders,
  adminListWorkspaces,
  adminLogin,
  adminReorderProviders,
  adminRunCommand,
  adminSyncWorkspace,
  adminUpdateProvider,
  ApiError,
  Provider,
  ProviderRoleTag,
  BrainPolicy,
} from "../api";
import { getLocal, removeLocal, setLocal } from "../storage";

const LS_ADMIN_TOKEN = "lls_admin_token";

function splitCmd(raw: string): string[] {
  return raw
    .trim()
    .split(/\s+/g)
    .filter(Boolean);
}

export default function AdminApp() {
  const [token, setToken] = useState(getLocal(LS_ADMIN_TOKEN) ?? "");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [providers, setProviders] = useState<any[]>([]);
  const [workspaces, setWorkspaces] = useState<any[]>([]);
  // Role badges + brain policy — sourced from the canonical brain resolver, NOT
  // from the webui JsonConfigStore. Keeping the role surface aligned with the
  // brain decision prevents the UI from claiming a provider is the “brain” when
  // routing picked something else.
  const [roleTags, setRoleTags] = useState<Record<string, ProviderRoleTag>>({});
  const [brainPolicy, setBrainPolicy] = useState<BrainPolicy | null>(null);

  const [newProv, setNewProv] = useState({
    name: "",
    base_url: "",
    api_key: "",
    default_model: "",
    default_temperature: "0.2",
    priority: "0",
  });
  const [newWs, setNewWs] = useState({
    name: "",
    kind: "local",
    path: "",
    git_url: "",
    git_ref: "",
  });

  const [cmdWorkspace, setCmdWorkspace] = useState("ws_current");
  const [cmdRaw, setCmdRaw] = useState("git status");
  const [cmdOut, setCmdOut] = useState<any>(null);

  const authed = token.trim().length > 0;

  useEffect(() => {
    if (authed) setLocal(LS_ADMIN_TOKEN, token);
  }, [authed, token]);

  function handleAuthFailure(e: unknown) {
    if (e instanceof ApiError && (e.status === 401 || e.status === 403)) {
      removeLocal(LS_ADMIN_TOKEN);
      setToken("");
      setErr("Session expired — please log in again.");
      return true;
    }
    return false;
  }

  async function refresh() {
    if (!authed) return;
    setErr(null);
    try {
      const [p, w, tags, pol] = await Promise.all([
        adminListProviders(token),
        adminListWorkspaces(token),
        adminGetProviderRoleTags(token).catch(() => ({ role_tags: {} })),
        adminGetBrainPolicy(token).catch(() => null),
      ]);
      setProviders(p.providers ?? []);
      setWorkspaces(w.workspaces ?? []);
      setRoleTags((tags as any).role_tags ?? {});
      setBrainPolicy(pol as BrainPolicy | null);
      if (w.workspaces?.[0]?.workspace_id) setCmdWorkspace(w.workspaces[0].workspace_id);
    } catch (e: any) {
      if (handleAuthFailure(e)) return;
      setErr(e?.message ?? String(e));
    }
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authed]);

  async function doLogin() {
    setBusy(true);
    setErr(null);
    try {
      const out = await adminLogin(username, password);
      setToken(out.token);
      setLocal(LS_ADMIN_TOKEN, out.token);
    } catch (e: any) {
      setErr(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    setToken("");
    removeLocal(LS_ADMIN_TOKEN);
  }

  async function createProvider() {
    setBusy(true);
    setErr(null);
    try {
      await adminCreateProvider(token, {
        name: newProv.name,
        base_url: newProv.base_url,
        api_key: newProv.api_key || null,
        default_model: newProv.default_model || null,
        default_temperature: Number(newProv.default_temperature || "0.2"),
        kind: "openai_compat",
        priority: Number(newProv.priority || "0"),
      });
      setNewProv({ name: "", base_url: "", api_key: "", default_model: "", default_temperature: "0.2", priority: "0" });
      await refresh();
    } catch (e: any) {
      if (handleAuthFailure(e)) return;
      setErr(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  function moveProviderInList(idx: number, dir: -1 | 1) {
    const arr = [...providers];
    const j = idx + dir;
    if (j < 0 || j >= arr.length) return;
    [arr[idx], arr[j]] = [arr[j], arr[idx]];
    setProviders(arr);
  }

  async function commitReorder() {
    if (!authed || providers.length === 0) return;
    setBusy(true);
    setErr(null);
    try {
      // Send the displayed array AS-IS, in the order the user arranged it
      // (top = highest). The render sort steps are display-only — sending the
      // re-sorted array would discard every up/down click.
      await adminReorderProviders(token, providers.map((p: any) => p.provider_id));
      await refresh();
    } catch (e: any) {
      if (handleAuthFailure(e)) return;
      setErr(`Reorder failed: ${e?.message ?? String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  // Debounced per-provider priority edits — typing the priority integer fires
  // onChange for every digit, which would otherwise issue a PATCH per keystroke.
  const [pendingPriority, setPendingPriority] = useState<Record<string, number>>({});
  async function flushPendingPriority(providerId: string) {
    const v = pendingPriority[providerId];
    if (v === undefined) return;
    setBusy(true);
    setErr(null);
    try {
      await adminUpdateProvider(token, providerId, { priority: v });
    } catch (e: any) {
      if (handleAuthFailure(e)) return;
      setErr(`Set priority failed: ${e?.message ?? String(e)}`);
    } finally {
      // Always clear the pending edit. On success, refresh() restores the
      // authoritative value from the server. On failure, the displayed
      // number reverts to whatever the server last confirmed.
      setPendingPriority((prev) => {
        const next = { ...prev };
        delete next[providerId];
        return next;
      });
      setBusy(false);
    }
    await refresh();
  }

  // Role badges key on backend provider_ids (Mongo store) which DO NOT overlap
  // with the webui JsonConfigStore ids. Build a lookup by normalized base_url
  // AND by name so operators' locally-added providers get their badge too.
  const roleForWebui = useMemo(() => {
    const map: Record<string, ProviderRoleTag> = {};
    const norm = (u: string) => (u || "").trim().replace(/\/+$/, "").toLowerCase();
    const byBase = new Map<string, ProviderRoleTag>();
    const byName = new Map<string, ProviderRoleTag>();
    for (const tag of Object.values(roleTags)) {
      if (tag.base_url) byBase.set(norm(tag.base_url), tag);
      if (tag.name) byName.set(tag.name.toLowerCase(), tag);
    }
    for (const p of providers as any[]) {
      const match =
        (p.base_url && byBase.get(norm(p.base_url))) ||
        (p.name && byName.get(String(p.name).toLowerCase()));
      if (match) map[p.provider_id] = match;
    }
    return map;
  }, [roleTags, providers]);

  function roleBadge(tag: ProviderRoleTag | undefined): { className: string; label: string; title: string } {
    if (!tag) return { className: "badge-muted", label: "—", title: "Role not yet resolved" };
    switch (tag.role) {
      case "brain":
        return { className: "badge-brain", label: "BRAIN", title: tag.reason };
      case "fallback":
        return { className: "badge-fallback", label: "PAID FALLBACK", title: tag.reason };
      case "sub-agent":
        return { className: "badge-sub-agent", label: "BACKUP", title: tag.reason };
      case "unconfigured":
        return { className: "badge-unconfigured", label: "UNCONFIGURED", title: tag.reason };
      default:
        return { className: "badge-muted", label: tag.role.toUpperCase(), title: tag.reason };
    }
  }

  async function createWorkspace() {
    setBusy(true);
    setErr(null);
    try {
      const body: any = { name: newWs.name, kind: newWs.kind };
      if (newWs.kind === "local") body.path = newWs.path;
      if (newWs.kind === "git") {
        body.git_url = newWs.git_url;
        if (newWs.git_ref) body.git_ref = newWs.git_ref;
      }
      await adminCreateWorkspace(token, body);
      setNewWs({ name: "", kind: "local", path: "", git_url: "", git_ref: "" });
      await refresh();
    } catch (e: any) {
      if (handleAuthFailure(e)) return;
      setErr(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  async function runCmd() {
    setBusy(true);
    setErr(null);
    setCmdOut(null);
    try {
      const out = await adminRunCommand(token, cmdWorkspace, splitCmd(cmdRaw));
      setCmdOut(out.result);
    } catch (e: any) {
      if (handleAuthFailure(e)) return;
      setErr(e?.message ?? String(e));
    } finally {
      setBusy(false);
    }
  }

  async function deleteProvider(providerId: string, providerName: string) {
    if (!window.confirm(`Delete provider "${providerName}"? This cannot be undone.`)) return;
    setBusy(true);
    setErr(null);
    try {
      await adminDeleteProvider(token, providerId);
      await refresh();
    } catch (e: any) {
      if (handleAuthFailure(e)) return;
      setErr(`Delete provider failed: ${e?.message ?? String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function deleteWorkspace(workspaceId: string, workspaceName: string) {
    if (!window.confirm(`Delete workspace "${workspaceName}"? This cannot be undone.`)) return;
    setBusy(true);
    setErr(null);
    try {
      await adminDeleteWorkspace(token, workspaceId);
      await refresh();
    } catch (e: any) {
      if (handleAuthFailure(e)) return;
      setErr(`Delete workspace failed: ${e?.message ?? String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  async function syncWorkspace(workspaceId: string) {
    setBusy(true);
    setErr(null);
    try {
      await adminSyncWorkspace(token, workspaceId);
      await refresh();
    } catch (e: any) {
      if (handleAuthFailure(e)) return;
      setErr(`Sync failed: ${e?.message ?? String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  const workspaceOptions = useMemo(
    () =>
      workspaces.map((w: any) => (
        <option key={w.workspace_id} value={w.workspace_id}>
          {w.name}
        </option>
      )),
    [workspaces]
  );

  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column" }}>
      <div className="topbar">
        <div className="brand">Autonomous AI Agency • Admin</div>
        <div className="muted">/admin/app</div>
        <a href="/app" className="pill">
          Back to app
        </a>
        <a href="/admin/ui/login" className="pill">
          Legacy admin UI
        </a>
        {authed ? (
          <button className="danger" onClick={logout}>
            Logout
          </button>
        ) : null}
        {busy ? <div className="pill">Working…</div> : null}
        {err ? <div className="pill" style={{ borderColor: "rgba(255,107,107,0.45)" }}>{err}</div> : null}
      </div>

      {!authed ? (
        <div className="stack" style={{ maxWidth: 720 }}>
          <div className="sectionTitle">Admin login</div>
          <div className="muted">
            Uses the server’s configured admin auth (`ADMIN_SECRET` or Windows auth when enabled).
          </div>
          <form
            className="row wrap"
            onSubmit={(e) => { e.preventDefault(); if (!busy && password.trim().length > 0) doLogin(); }}
          >
            <label htmlFor="lls-admin-username" className="sr-only">Username</label>
            <input
              id="lls-admin-username"
              placeholder="Username (optional)"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
            <label htmlFor="lls-admin-password" className="sr-only">Password</label>
            <input
              id="lls-admin-password"
              placeholder="Password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button
              className="primary"
              type="submit"
              disabled={busy || password.trim().length === 0}
            >
              Login
            </button>
          </form>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, padding: 14, overflow: "auto" }}>
          <div className="panel" style={{ gridColumn: "1 / span 2", borderRadius: 14, border: "1px solid var(--border)" }}>
            <div className="stack">
              <div className="sectionTitle">Brain &amp; Paid-Models policy</div>
              <div className="muted">
                Shows the CEO brain the agency picks right now, plus the global paid-models policy.
                Paid providers (Anthropic / Bedrock) are only used as the brain when this is enabled.
                Drag-and-drop below reorders the chat-provider picker; backend-seeded brain priority is
 configured in the server env (e.g. NVIDIA_DEFAULT_MODEL) or via the backend provider store.
              </div>
              <div className="row wrap">
                <span
                  className={`pill ${brainPolicy?.allow_paid_brain ? "badge-fallback" : "badge-brain"}`}
                  title={brainPolicy?.allow_paid_brain
                    ? "ALLOW_PAID_BRAIN=true \u2014 paid providers may be picked when no free alternative is configured"
                    : "ALLOW_PAID_BRAIN unset \u2014 free-first is enforced (default)"}
                >
                  Paid models allowed: {brainPolicy?.allow_paid_brain ? "YES" : "no"}
                </span>
                {brainPolicy?.resolution ? (
                  <span className="pill mono" title="The brain the next agent run will use">
                    Brain: {brainPolicy.resolution.provider_id}
                    {brainPolicy.resolution.model ? ` (${brainPolicy.resolution.model})` : ""}
                    {" \u2014 "}
                    {brainPolicy.resolution.role}
                    {brainPolicy.resolution.free_tier ? " \u2022 free" : " \u2022 paid"}
                  </span>
                ) : (
                  <span className="pill mono muted">brain policy not resolved yet</span>
                )}
                <span
                  className="pill mono muted"
                  title={brainPolicy?.hint ?? "Set ALLOW_PAID_BRAIN=true in the server environment to enable paid providers."}
                >
                  env: {brainPolicy?.env_var ?? "ALLOW_PAID_BRAIN"}
                </span>
              </div>
              {!brainPolicy?.allow_paid_brain ? (
                <div className="muted" style={{ fontSize: 12 }}>
                  Free-first is enforced. Set <code>ALLOW_PAID_BRAIN=true</code> on the server (Render env var / .env) and restart to enable paid models \u2014 changes here WILL incur costs.
                </div>
              ) : null}
            </div>
          </div>

          <div className="panel" style={{ borderRadius: 14, border: "1px solid var(--border)" }}>
            <div className="stack">
              <div className="sectionTitle">Providers</div>
              <div className="muted">
                OpenAI-compatible endpoints (secrets stay server-side).
                Drag with the arrows to reorder priority \u2014 highest = top = first brain candidate.
              </div>
              <div
                className="list"
                role="list"
                aria-label="Providers ordered by priority (top first)"
              >
                {[...providers]
                  .sort((a: any, b: any) => (Number(b?.priority ?? 0)) - (Number(a?.priority ?? 0)))
                  .map((p: any, idx: number, arr: any[]) => {
                  const badge = roleBadge(roleForWebui[p.provider_id]);
                  return (
                    <div className="item" key={p.provider_id} role="listitem">
                      <div className="row wrap">
                        <div className="row" style={{ alignItems: "center", gap: 4 }}>
                          <button
                            className="btn-sm"
                            aria-label={`Move ${p.name} up`}
                            onClick={() => moveProviderInList(providers.findIndex((x: any) => x.provider_id === p.provider_id), -1)}
                            disabled={busy || idx === 0}
                            title="Higher priority"
                          >\u2191</button>
                          <button
                            className="btn-sm"
                            aria-label={`Move ${p.name} down`}
                            onClick={() => moveProviderInList(providers.findIndex((x: any) => x.provider_id === p.provider_id), 1)}
                            disabled={busy || idx === arr.length - 1}
                            title="Lower priority"
                          >\u2193</button>
                          <input
                            className="mono"
                            style={{ width: 60 }}
                            type="number"
                            aria-label={`Priority for ${p.name}`}
                            value={
                              pendingPriority[p.provider_id] !== undefined
                                ? pendingPriority[p.provider_id]
                                : Number(p.priority ?? 0)
                            }
                            min={-1000}
                            max={1000}
                            onChange={(e) => {
                              const v = Number(e.target.value);
                              if (Number.isFinite(v)) setPendingPriority((prev) => ({ ...prev, [p.provider_id]: v }));
                            }}
                            onBlur={() => flushPendingPriority(p.provider_id)}
                            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); flushPendingPriority(p.provider_id); } }}
                            disabled={busy}
                          />
                        </div>
                        <div className="grow">
                          <div className="row" style={{ alignItems: "center", gap: 6 }}>
                            <span style={{ fontWeight: 600 }}>{p.name}</span>
                            <span
                              className={`role-badge ${badge.className}`}
                              title={badge.title}
                            >{badge.label}</span>
                          </div>
                          <div className="muted mono">{p.base_url}</div>
                          <div className="muted mono">id: {p.provider_id}</div>
                        </div>
                        <button
                          className="danger"
                          onClick={() => deleteProvider(p.provider_id, p.name)}
                          disabled={busy}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
              <div className="row">
                <button
                  className="primary"
                  onClick={commitReorder}
                  disabled={busy || providers.length === 0}
                  aria-label="Save order"
                >
                  Save order
                </button>
                <span className="muted" style={{ fontSize: 12 }}>
                  Click Save order to persist the displayed ordering.
                </span>
              </div>

              <div className="sectionTitle" id="add-provider-title">Add provider</div>
              <div className="row wrap" role="group" aria-labelledby="add-provider-title">
                <input
                  placeholder="Name"
                  aria-label="Provider name"
                  value={newProv.name}
                  onChange={(e) => setNewProv({ ...newProv, name: e.target.value })}
                />
                <input
                  placeholder="Base URL (e.g. https://api.openai.com)"
                  aria-label="Provider base URL"
                  value={newProv.base_url}
                  onChange={(e) => setNewProv({ ...newProv, base_url: e.target.value })}
                  style={{ width: 320 }}
                />
              </div>
              <div className="row wrap">
                <input
                  placeholder="API key (stored server-side)"
                  aria-label="Provider API key"
                  type="password"
                  autoComplete="off"
                  value={newProv.api_key}
                  onChange={(e) => setNewProv({ ...newProv, api_key: e.target.value })}
                  style={{ width: 320 }}
                />
                <input
                  placeholder="Default model (optional)"
                  aria-label="Provider default model"
                  value={newProv.default_model}
                  onChange={(e) => setNewProv({ ...newProv, default_model: e.target.value })}
                />
                <input
                  className="mono"
                  placeholder="Temp"
                  aria-label="Provider default temperature"
                  inputMode="decimal"
                  value={newProv.default_temperature}
                  onChange={(e) => setNewProv({ ...newProv, default_temperature: e.target.value })}
                  style={{ width: 90 }}
                />
                <input
                  className="mono"
                  placeholder="Priority"
                  aria-label="Provider priority"
                  inputMode="numeric"
                  type="number"
                  value={newProv.priority}
                  onChange={(e) => setNewProv({ ...newProv, priority: e.target.value })}
                  style={{ width: 90 }}
                />
                <button
                  className="primary"
                  onClick={createProvider}
                  disabled={busy || !newProv.name.trim() || !newProv.base_url.trim()}
                >
                  Create
                </button>
              </div>
            </div>
          </div>

          <div className="panel" style={{ borderRadius: 14, border: "1px solid var(--border)" }}>
            <div className="stack">
              <div className="sectionTitle">Workspaces</div>
              <div className="muted">
                The agent can read/search/apply diffs within the selected workspace root.
              </div>
              <div className="list">
                {workspaces.map((w: any) => (
                  <div className="item" key={w.workspace_id}>
                    <div className="row wrap">
                      <div className="grow">
                        <div style={{ fontWeight: 600 }}>
                          {w.name} <span className="muted">({w.kind})</span>
                        </div>
                        <div className="muted mono">{w.path}</div>
                        {w.git_url ? <div className="muted mono">{w.git_url}</div> : null}
                        <div className="muted mono">id: {w.workspace_id}</div>
                      </div>
                      {w.kind === "git" ? (
                        <button
                          onClick={() => syncWorkspace(w.workspace_id)}
                          disabled={busy}
                        >
                          Sync
                        </button>
                      ) : null}
                      <button
                        className="danger"
                        onClick={() => deleteWorkspace(w.workspace_id, w.name)}
                        disabled={busy}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              <div className="sectionTitle" id="add-workspace-title">Add workspace</div>
              <div className="row wrap" role="group" aria-labelledby="add-workspace-title">
                <input
                  placeholder="Name"
                  aria-label="Workspace name"
                  value={newWs.name}
                  onChange={(e) => setNewWs({ ...newWs, name: e.target.value })}
                />
                <select
                  aria-label="Workspace kind"
                  value={newWs.kind}
                  onChange={(e) => setNewWs({ ...newWs, kind: e.target.value })}
                >
                  <option value="local">local path</option>
                  <option value="git">git clone</option>
                </select>
              </div>
              {newWs.kind === "local" ? (
                <div className="row wrap">
                  <input
                    placeholder="Absolute path on server"
                    aria-label="Workspace absolute path"
                    value={newWs.path}
                    onChange={(e) => setNewWs({ ...newWs, path: e.target.value })}
                    style={{ width: 420 }}
                  />
                </div>
              ) : (
                <div className="row wrap">
                  <input
                    placeholder="Git URL (https://...)"
                    aria-label="Workspace git URL"
                    value={newWs.git_url}
                    onChange={(e) => setNewWs({ ...newWs, git_url: e.target.value })}
                    style={{ width: 420 }}
                  />
                  <input
                    placeholder="Branch/ref (optional)"
                    aria-label="Workspace git branch or ref"
                    value={newWs.git_ref}
                    onChange={(e) => setNewWs({ ...newWs, git_ref: e.target.value })}
                  />
                </div>
              )}
              <div className="row wrap">
                <button
                  className="primary"
                  onClick={createWorkspace}
                  disabled={
                    busy ||
                    !newWs.name.trim() ||
                    (newWs.kind === "local" ? !newWs.path.trim() : !newWs.git_url.trim())
                  }
                >
                  Create
                </button>
              </div>

              <div className="sectionTitle" id="cmd-runner-title">Command runner</div>
              <div className="muted mono">Allowlist: `pytest`, `rg`, `git status|diff|log|show|rev-parse`, `ls`, `cat`.</div>
              <div className="row wrap" role="group" aria-labelledby="cmd-runner-title">
                <select
                  aria-label="Command runner workspace"
                  value={cmdWorkspace}
                  onChange={(e) => setCmdWorkspace(e.target.value)}
                >
                  {workspaceOptions}
                </select>
                <input
                  className="mono grow"
                  placeholder="git status"
                  aria-label="Command to run"
                  value={cmdRaw}
                  onChange={(e) => setCmdRaw(e.target.value)}
                />
                <button className="primary" onClick={runCmd} disabled={busy || splitCmd(cmdRaw).length === 0}>
                  Run
                </button>
              </div>
              {cmdOut ? (
                <pre
                  className="codebox mono"
                  role="region"
                  aria-label="Command output"
                  aria-live="polite"
                >
                  exit={cmdOut.exit_code}
                  {"\n"}
                  {cmdOut.stdout}
                  {cmdOut.stderr ? `\n[stderr]\n${cmdOut.stderr}` : ""}
                </pre>
              ) : null}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
