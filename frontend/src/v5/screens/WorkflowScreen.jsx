/* eslint-disable no-unused-vars */
//
// WorkflowScreen — the visible face of the CRISPY workflow engine.
//
// The engine (workflow/) runs a plan→execute→verify workflow that pauses at a
// hard `awaiting_approval` gate before any code is written. Its API existed with
// 13 endpoints but was unmounted and had no UI; PR2 mounted it admin-gated at
// /api/workflow, and this screen surfaces it: start a run, watch the phase
// timeline, and lift or fail the approval gate.
//
// Data source: GET /api/workflow/ (list), GET /api/workflow/{id} (detail),
// POST .../build | .../approve | .../reject | .../cancel. All admin-only.
import React from 'react';
import * as api from '../../api';

const STATUS_COLOR = {
  pending: '#6e7786', context: '#8fb6ff', research: '#8fb6ff', investigate: '#8fb6ff',
  structure: '#8fb6ff', plan: '#8fb6ff', awaiting_approval: '#ffbd66',
  executing: '#7ed957', reviewing: '#7ed957', verifying: '#7ed957',
  done: '#46d9a4', failed: '#ff6b7d', cancelled: '#6e7786',
};

const PHASE_STATUS_COLOR = {
  pending: '#6e7786', running: '#8fb6ff', done: '#46d9a4', failed: '#ff6b7d', skipped: '#6e7786',
};

const TERMINAL = new Set(['done', 'failed', 'cancelled']);

function Badge({ children, color, title }) {
  return (
    <span title={title} style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 999,
      fontSize: 10, fontWeight: 700, fontFamily: 'var(--font-mono)',
      color, background: `${color}1a`, border: `1px solid ${color}33`, whiteSpace: 'nowrap',
    }}>{children}</span>
  );
}

function StatusBadge({ status }) {
  const color = STATUS_COLOR[status] || '#6e7786';
  return <Badge color={color} title={status}>{String(status).replace(/_/g, ' ')}</Badge>;
}

const btn = (color, disabled) => ({
  padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700,
  background: `${color}1a`, border: `1px solid ${color}55`, color,
  cursor: disabled ? 'default' : 'pointer', opacity: disabled ? 0.5 : 1,
});

function BuildForm({ onBuilt }) {
  const [open, setOpen] = React.useState(false);
  const [request, setRequest] = React.useState('');
  const [title, setTitle] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [err, setErr] = React.useState(null);

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      await api.buildWorkflow({ request, title: title || undefined });
      setRequest(''); setTitle(''); setOpen(false);
      onBuilt && onBuilt();
    } catch (e) {
      setErr(api.fmtErr(e?.response?.data?.detail) || e?.message || 'Build failed.');
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button onClick={() => setOpen(true)} style={btn('#5da2ff', false)}>+ New workflow</button>
    );
  }
  return (
    <div style={{
      borderRadius: 12, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.02)',
      padding: 14, marginBottom: 16, display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <input
        value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title (optional)"
        style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-primary)', fontSize: 13 }}
      />
      <textarea
        value={request} onChange={(e) => setRequest(e.target.value)} rows={4}
        placeholder="Describe the task (min 10 characters). The run pauses for your approval before any code is written."
        style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-primary)', fontSize: 13, resize: 'vertical' }}
      />
      {err && <div style={{ color: '#ff6b7d', fontSize: 12 }}>{err}</div>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={submit} disabled={busy || request.trim().length < 10} style={btn('#46d9a4', busy || request.trim().length < 10)}>
          {busy ? 'Starting…' : 'Start workflow'}
        </button>
        <button onClick={() => { setOpen(false); setErr(null); }} disabled={busy} style={btn('#6e7786', busy)}>Cancel</button>
      </div>
    </div>
  );
}

function RunDetail({ runId, onChanged }) {
  const [run, setRun] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [acting, setActing] = React.useState(false);

  const load = React.useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const { data } = await api.getWorkflowRun(runId);
      setRun(data);
    } catch (e) {
      setError(e?.message || 'Could not load run.');
    } finally {
      setLoading(false);
    }
  }, [runId]);

  React.useEffect(() => { load(); }, [load]);

  const act = async (fn) => {
    setActing(true);
    try { await fn(); await load(); onChanged && onChanged(); }
    catch (e) { setError(api.fmtErr(e?.response?.data?.detail) || e?.message || 'Action failed.'); }
    finally { setActing(false); }
  };

  if (loading) return <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading run…</div>;
  if (error) return <div style={{ color: '#ff6b7d', fontSize: 13 }}>{error}</div>;
  if (!run) return null;

  const phases = run.phases || [];
  const canApprove = run.status === 'awaiting_approval';
  const canCancel = !TERMINAL.has(run.status);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <StatusBadge status={run.status} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{run.run_id}</span>
      </div>

      {canApprove && (
        <div style={{ padding: 12, borderRadius: 10, border: '1px solid rgba(255,189,102,0.35)', background: 'rgba(255,189,102,0.07)', display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: '#ffbd66', fontWeight: 700 }}>🔒 Awaiting approval — no code has been written yet.</span>
          <button disabled={acting} onClick={() => act(() => api.approveWorkflow(run.run_id, 'admin'))} style={btn('#46d9a4', acting)}>Approve</button>
          <button disabled={acting} onClick={() => {
            const reason = window.prompt('Reason for rejecting this plan?');
            if (reason) act(() => api.rejectWorkflow(run.run_id, reason, 'admin'));
          }} style={btn('#ff6b7d', acting)}>Reject</button>
        </div>
      )}

      <div>
        <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 6 }}>Phase timeline</div>
        {phases.length === 0 && <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>No phases yet.</div>}
        {phases.map((p) => (
          <div key={p.phase_id || p.name} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '6px 0', borderTop: '1px solid var(--border-soft)' }}>
            <span style={{ minWidth: 110, fontSize: 12, color: 'var(--text-primary)', fontWeight: 600 }}>{p.name}</span>
            <Badge color={PHASE_STATUS_COLOR[p.status] || '#6e7786'}>{p.status}</Badge>
            {p.agent_role && <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{p.agent_role}</span>}
            {p.error && <span style={{ fontSize: 11, color: '#ff6b7d' }} title={p.error}>⚠</span>}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        {canCancel && (
          <button disabled={acting} onClick={() => act(() => api.cancelWorkflow(run.run_id))} style={btn('#6e7786', acting)}>Cancel run</button>
        )}
        <button disabled={acting} onClick={load} style={btn('#5da2ff', acting)}>↻ Refresh</button>
      </div>
    </div>
  );
}

export default function WorkflowScreen() {
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const [selected, setSelected] = React.useState(null);

  const load = React.useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const { data } = await api.getWorkflowRuns();
      setData(data);
    } catch (e) {
      setError(e?.message || 'Could not load workflow runs.');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { load(); }, [load]);

  const runs = (data && data.runs) || [];

  return (
    <div style={{ padding: '22px 26px', height: '100%', overflowY: 'auto' }} className="scrollbar-hide">
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 6, flexWrap: 'wrap', gap: 8 }}>
        <h1 style={{ fontSize: 22, fontWeight: 900, letterSpacing: '-0.02em' }}>Workflows</h1>
        <button onClick={load} disabled={loading} style={btn('#5da2ff', loading)}>{loading ? '…' : '↻ Refresh'}</button>
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-tertiary)', marginBottom: 16, maxWidth: 760 }}>
        The CRISPY plan→execute→verify workflow engine. Every run pauses at a hard
        <code> awaiting_approval</code> gate before any code is written — you approve or reject
        the plan here. Admin-only. Source: <code>workflow/</code>, API <code>/api/workflow</code>.
      </p>

      <div style={{ marginBottom: 16 }}>
        <BuildForm onBuilt={load} />
      </div>

      {loading && <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading workflow runs…</div>}

      {!loading && error && (
        <div style={{ padding: 14, borderRadius: 12, border: '1px solid rgba(255,107,125,0.30)', background: 'rgba(255,107,125,0.06)', color: '#ff6b7d', fontSize: 13, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {!loading && !error && runs.length === 0 && (
        <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No workflow runs yet. Start one above.</div>
      )}

      {!loading && runs.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 1fr) minmax(280px, 1.2fr)', gap: 16, alignItems: 'start' }}>
          <div style={{ borderRadius: 16, border: '1px solid var(--border)', overflow: 'hidden' }}>
            {runs.map((r) => {
              const isSel = selected === r.run_id;
              return (
                <button key={r.run_id} onClick={() => setSelected(r.run_id)} style={{
                  display: 'block', width: '100%', textAlign: 'left', padding: '12px 14px',
                  borderTop: '1px solid var(--border-soft)', background: isSel ? 'rgba(93,162,255,0.08)' : 'transparent',
                  cursor: 'pointer', border: 'none', borderLeft: isSel ? '3px solid var(--accent)' : '3px solid transparent',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: 13, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.title || r.run_id}</span>
                    <StatusBadge status={r.status} />
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>{r.created_at || ''}</div>
                </button>
              );
            })}
          </div>
          <div style={{ borderRadius: 16, border: '1px solid var(--border)', padding: 16, minHeight: 120 }}>
            {selected
              ? <RunDetail runId={selected} onChanged={load} />
              : <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Select a run to see its phases and approval gate.</div>}
          </div>
        </div>
      )}
    </div>
  );
}
