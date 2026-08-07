//
// GovernanceScreen — the visible face of the agent governance layer.
//
// The governance layer (packages/governance) ships in `observe` mode: every
// agent action is evaluated against policy and audited, but nothing is
// blocked. That default is deliberate — you cannot know a rule is correct
// until you have seen what it would have caught — but it only works if
// somebody can actually see the verdicts. Until this screen existed the only
// way to read them was an authenticated curl, which made the observe phase
// unusable for anyone not at a terminal.
//
// So the job of this screen is narrow and specific: answer "is it safe to
// turn on enforcement yet?" That question reduces to one number —
// `would_block` — plus the list of decisions behind it. Everything here is
// arranged around that.
//
// Data sources (all admin-only, all read-only except the approval buttons):
//   GET  /api/governance/status     backend + isolation posture
//   GET  /api/governance/metrics    would_block, decision counters, budgets
//   GET  /api/governance/audit      recent decisions, newest first
//   GET  /api/governance/approvals  pending human-in-the-loop requests
//   POST /api/governance/approvals/{id}/approve|deny
import React from 'react';
import * as api from '../../api';

const DECISION_COLOR = {
  allow: '#46d9a4',
  require_approval: '#ffbd66',
  deny: '#ff6b7d',
};

// Isolation strength, honestly ranked. `local` is red on purpose: a dashboard
// that renders "no isolation" in a calm neutral grey is a dashboard that lets
// an operator believe agents are contained when they are not.
const BACKEND_META = {
  e2b:    { color: '#46d9a4', label: 'E2B micro-VM',   hint: 'Firecracker micro-VM — per-sandbox kernel' },
  docker: { color: '#7ed957', label: 'Docker',          hint: 'Shared kernel, hardened per profile' },
  local:  { color: '#ff6b7d', label: 'None (in-process)', hint: 'No hard boundary — in-process policy only' },
  unknown:{ color: '#6e7786', label: 'Unknown',         hint: 'Backend probe did not complete' },
};

function Badge({ children, color, title }) {
  return (
    <span title={title} style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 999,
      fontSize: 10, fontWeight: 700, fontFamily: 'var(--font-mono)',
      color, background: `${color}1a`, border: `1px solid ${color}33`,
      whiteSpace: 'nowrap',
    }}>{children}</span>
  );
}

function relTime(iso) {
  if (!iso) return '—';
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return '—';
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

// ── The headline: mode, would-block, isolation ───────────────────────────
function PostureHeader({ status, metrics }) {
  // `enforcing` is the backend's own resolved answer rather than a re-read of
  // `mode`, so the UI cannot disagree with the engine about whether verdicts
  // are being acted on.
  const enforcing = status?.enforcing === true;
  const wouldBlock = metrics?.audit?.would_block ?? 0;
  const backendId = status?.sandbox?.backend || 'unknown';
  const backend = BACKEND_META[backendId] || BACKEND_META.unknown;
  const modeColor = enforcing ? '#46d9a4' : '#ffbd66';

  return (
    <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 18 }}>
      {/* Mode */}
      <div style={{
        borderRadius: 16, border: `1px solid ${modeColor}40`, background: `${modeColor}0d`,
        padding: '18px 22px', minWidth: 170,
      }}>
        <div style={{ fontSize: 26, fontWeight: 900, color: modeColor, lineHeight: 1.1 }}>
          {enforcing ? 'ENFORCING' : 'OBSERVE'}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 6 }}>
          {enforcing ? 'verdicts are acted on' : 'nothing is blocked'}
        </div>
      </div>

      {/* would_block — the number that decides when enforce is safe */}
      <div
        title="Decisions that blocked, or would have blocked in enforce mode. Sustained zero means the rules only catch what you meant them to catch."
        style={{
          borderRadius: 16, border: '1px solid var(--border)',
          background: 'rgba(255,255,255,0.02)', padding: '18px 22px', minWidth: 170,
        }}
      >
        <div style={{
          fontSize: 34, fontWeight: 900, lineHeight: 1,
          color: wouldBlock > 0 ? '#ffbd66' : '#46d9a4',
        }}>{wouldBlock}</div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 6 }}>
          would-block {enforcing ? '(blocked)' : '(if enforcing)'}
        </div>
      </div>

      {/* Sandbox isolation — reported honestly, including "none" */}
      <div style={{
        flex: 1, minWidth: 260, borderRadius: 16,
        border: `1px solid ${backend.color}33`, background: 'rgba(255,255,255,0.02)',
        padding: '14px 18px',
      }}>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
          Sandbox isolation
        </div>
        <div style={{ marginTop: 6, marginBottom: 6 }}>
          <Badge color={backend.color} title={backend.hint}>{backend.label}</Badge>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', lineHeight: 1.5 }}>
          {backend.hint}
          {backendId === 'local' && (
            // Say what to do, not the same sentence again — the line above
            // already states there is no boundary.
            <div style={{ color: '#ff6b7d', marginTop: 4, fontWeight: 700 }}>
              Set E2B_ENABLED + E2B_API_KEY, or run a Docker daemon, to get one.
            </div>
          )}
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 8 }}>
          policy v{status?.policy_version ?? '—'} · {status?.groups?.length ?? 0} groups
          {status?.auto_approve ? ' · ⚠ auto-approve ON' : ''}
        </div>
      </div>
    </div>
  );
}

// ── Pending approvals ────────────────────────────────────────────────────
function Approvals({ approvals, onResolve, busyId }) {
  if (!approvals.length) return null;
  return (
    <div style={{ marginBottom: 20 }}>
      <h2 style={{ fontSize: 14, fontWeight: 800, marginBottom: 8 }}>
        Awaiting your decision ({approvals.length})
      </h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {approvals.map((a) => (
          <div key={a.approval_id} style={{
            borderRadius: 12, border: '1px solid rgba(255,189,102,0.30)',
            background: 'rgba(255,189,102,0.06)', padding: '12px 14px',
            display: 'flex', gap: 12, alignItems: 'center', flexWrap: 'wrap',
          }}>
            <div style={{ flex: 1, minWidth: 220 }}>
              <div style={{ fontWeight: 700, fontSize: 13 }}>
                {a.agent_id} → <code style={{ fontFamily: 'var(--font-mono)' }}>{a.action}</code>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
                {a.reason}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 3 }}>
                rule {a.rule_id} · expires in {Math.round(a.seconds_remaining)}s
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => onResolve(a.approval_id, true)}
                disabled={busyId === a.approval_id}
                style={{
                  padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                  background: 'rgba(70,217,164,0.12)', border: '1px solid rgba(70,217,164,0.35)',
                  color: '#46d9a4', cursor: busyId === a.approval_id ? 'default' : 'pointer',
                }}
              >Approve</button>
              <button
                onClick={() => onResolve(a.approval_id, false)}
                disabled={busyId === a.approval_id}
                style={{
                  padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                  background: 'rgba(255,107,125,0.12)', border: '1px solid rgba(255,107,125,0.35)',
                  color: '#ff6b7d', cursor: busyId === a.approval_id ? 'default' : 'pointer',
                }}
              >Deny</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Audit trail ──────────────────────────────────────────────────────────
function AuditTable({ events, filter, onFilter }) {
  const FILTERS = [
    { id: '', label: 'All' },
    { id: 'deny', label: 'Denied' },
    { id: 'require_approval', label: 'Approval' },
    { id: 'allow', label: 'Allowed' },
  ];
  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 8, flexWrap: 'wrap', gap: 8 }}>
        <h2 style={{ fontSize: 14, fontWeight: 800 }}>Recent decisions</h2>
        <div style={{ display: 'flex', gap: 6 }}>
          {FILTERS.map((f) => (
            <button key={f.id || 'all'} onClick={() => onFilter(f.id)} style={{
              padding: '4px 10px', borderRadius: 7, fontSize: 11, fontWeight: 700,
              background: filter === f.id ? 'rgba(93,162,255,0.14)' : 'transparent',
              border: `1px solid ${filter === f.id ? 'rgba(93,162,255,0.35)' : 'var(--border)'}`,
              color: filter === f.id ? 'var(--accent)' : 'var(--text-muted)', cursor: 'pointer',
            }}>{f.label}</button>
          ))}
        </div>
      </div>

      {events.length === 0 ? (
        <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
          No decisions recorded yet. Agent activity will appear here as it happens.
        </div>
      ) : (
        <div className="scroll-x" style={{ borderRadius: 16, border: '1px solid var(--border)' }}>
          <div style={{ minWidth: 700 }}>
            <div style={{
              display: 'grid', gridTemplateColumns: '0.8fr 1.3fr 1.6fr 1.4fr 0.7fr',
              gap: 8, padding: '10px 14px', background: 'rgba(255,255,255,0.03)',
              fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
              textTransform: 'uppercase', letterSpacing: '0.08em',
            }}>
              <div>Verdict</div><div>Agent</div><div>Action</div><div>Rule</div><div>When</div>
            </div>
            {events.map((e) => {
              const color = DECISION_COLOR[e.decision] || '#6e7786';
              return (
                <div key={e.event_id} style={{
                  display: 'grid', gridTemplateColumns: '0.8fr 1.3fr 1.6fr 1.4fr 0.7fr',
                  gap: 8, padding: '10px 14px', alignItems: 'center',
                  borderTop: '1px solid var(--border-soft)', fontSize: 12,
                }}>
                  <div><Badge color={color}>{e.decision}</Badge></div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 700, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {e.display_name || e.agent_id}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                      {e.policy_group}
                    </div>
                  </div>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {e.tool ? `${e.tool} · ` : ''}{e.action}
                    </div>
                    <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{e.surface}</div>
                  </div>
                  <div title={e.reason} style={{
                    fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)',
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  }}>{e.rule_id}</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                    {relTime(e.timestamp)}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

export default function GovernanceScreen() {
  const [status, setStatus]       = React.useState(null);
  const [metrics, setMetrics]     = React.useState(null);
  const [events, setEvents]       = React.useState([]);
  const [approvals, setApprovals] = React.useState([]);
  const [filter, setFilter]       = React.useState('');
  const [loading, setLoading]     = React.useState(true);
  const [error, setError]         = React.useState(null);
  const [busyId, setBusyId]       = React.useState(null);

  const load = React.useCallback(async () => {
    setLoading(true); setError(null);
    // Promise.allSettled, not Promise.all: a single failing endpoint must not
    // blank the whole screen. The sandbox probe in particular can be slow or
    // fail on its own without the audit trail being affected.
    const [s, m, a, ap] = await Promise.allSettled([
      api.getGovernanceStatus(),
      api.getGovernanceMetrics(),
      api.getGovernanceAudit({ limit: 100, ...(filter ? { decision: filter } : {}) }),
      api.getGovernanceApprovals(),
    ]);
    if (s.status === 'fulfilled') setStatus(s.value.data); else setStatus(null);
    if (m.status === 'fulfilled') setMetrics(m.value.data); else setMetrics(null);
    if (a.status === 'fulfilled') setEvents(a.value.data?.events || []); else setEvents([]);
    if (ap.status === 'fulfilled') setApprovals(ap.value.data?.approvals || []); else setApprovals([]);

    if (s.status === 'rejected') {
      const code = s.reason?.response?.status;
      setError(code === 403
        ? 'Admin access required to view governance.'
        : (s.reason?.message || 'Could not reach the governance API.'));
    }
    setLoading(false);
  }, [filter]);

  React.useEffect(() => { load(); }, [load]);

  // Poll while approvals are pending — an agent is blocked waiting on one, and
  // its request expires into a denial, so a stale list costs real work.
  React.useEffect(() => {
    if (!approvals.length) return undefined;
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [approvals.length, load]);

  const resolve = React.useCallback(async (id, approved) => {
    setBusyId(id);
    try {
      if (approved) await api.approveGovernanceRequest(id);
      else await api.denyGovernanceRequest(id);
      await load();
    } catch (e) {
      setError(e?.message || 'Could not record the decision.');
    } finally {
      setBusyId(null);
    }
  }, [load]);

  return (
    <div style={{ padding: '22px 26px', height: '100%', overflowY: 'auto' }} className="scrollbar-hide">
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 6, flexWrap: 'wrap', gap: 8 }}>
        <h1 style={{ fontSize: 22, fontWeight: 900, letterSpacing: '-0.02em' }}>Governance</h1>
        <button onClick={load} disabled={loading} style={{
          padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700,
          background: 'rgba(93,162,255,0.10)', border: '1px solid rgba(93,162,255,0.30)',
          color: 'var(--accent)', cursor: loading ? 'default' : 'pointer',
        }}>{loading ? '…' : '↻ Refresh'}</button>
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-tertiary)', marginBottom: 18, maxWidth: 720, lineHeight: 1.6 }}>
        Identity, policy, approvals, and the audit trail for every agent action. Policy lives in
        <code> config/agent_policy.yaml</code> and is reviewed in git — there is no endpoint that edits it.
        Watch <b>would-block</b> until it only counts things you want stopped, then switch the policy to
        <code> enforce</code>.
      </p>

      {error && (
        <div style={{
          padding: 14, borderRadius: 12, border: '1px solid rgba(255,107,125,0.30)',
          background: 'rgba(255,107,125,0.06)', color: '#ff6b7d', fontSize: 13, marginBottom: 16,
        }}>{error}</div>
      )}

      {loading && !status && (
        <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading governance state…</div>
      )}

      {status && <PostureHeader status={status} metrics={metrics} />}

      <Approvals approvals={approvals} onResolve={resolve} busyId={busyId} />

      {status && <AuditTable events={events} filter={filter} onFilter={setFilter} />}
    </div>
  );
}
