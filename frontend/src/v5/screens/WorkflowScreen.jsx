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
import Glyph from '../components/ui/Glyph';
import * as api from '../../api';

const STATUS_COLOR = {
  pending: 'var(--text-muted)', context: 'var(--accent)', research: 'var(--accent)', investigate: 'var(--accent)',
  structure: 'var(--accent)', plan: 'var(--accent)', awaiting_approval: 'var(--warning)',
  executing: 'var(--success)', reviewing: 'var(--success)', verifying: 'var(--success)',
  done: 'var(--success)', failed: 'var(--danger)', cancelled: 'var(--text-muted)',
};

const PHASE_STATUS_COLOR = {
  pending: 'var(--text-muted)', running: 'var(--accent)', done: 'var(--success)', failed: 'var(--danger)', skipped: 'var(--text-muted)',
};

const TERMINAL = new Set(['done', 'failed', 'cancelled']);

function Badge({ children, color, title }) {
  return (
    <span title={title} style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: 999,
      fontSize:13, fontWeight: 700, fontVariantNumeric:'tabular-nums',
      color, background: `color-mix(in oklab, ${color} 10%, transparent)`, border: `1px solid color-mix(in oklab, ${color} 20%, transparent)`, whiteSpace: 'nowrap',
    }}>{children}</span>
  );
}

function StatusBadge({ status }) {
  const color = STATUS_COLOR[status] || 'var(--text-muted)';
  return <Badge color={color} title={status}>{String(status).replace(/_/g, ' ')}</Badge>;
}

const btn = (color, disabled) => ({
  padding: '6px 14px', borderRadius: 8, fontSize:13, fontWeight: 700,
  background: `color-mix(in oklab, ${color} 10%, transparent)`, border: `1px solid color-mix(in oklab, ${color} 33%, transparent)`, color,
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
      <button onClick={() => setOpen(true)} style={btn('var(--accent)', false)}>+ New workflow</button>
    );
  }
  return (
    <div style={{
      borderRadius: 12, border: '1px solid var(--border)', background: 'color-mix(in oklab, var(--ink) 2%, transparent)',
      padding: 14, marginBottom: 16, display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <input
        value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title (optional)"
        style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-primary)', fontSize:14 }}
      />
      <textarea
        value={request} onChange={(e) => setRequest(e.target.value)} rows={4}
        placeholder="Describe the task (min 10 characters). The run pauses for your approval before any code is written."
        style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-primary)', fontSize:14, resize: 'vertical' }}
      />
      {err && <div style={{ color: 'var(--danger)', fontSize:13 }}>{err}</div>}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={submit} disabled={busy || request.trim().length < 10} style={btn('var(--success)', busy || request.trim().length < 10)}>
          {busy ? 'Starting…' : 'Start workflow'}
        </button>
        <button onClick={() => { setOpen(false); setErr(null); }} disabled={busy} style={btn('var(--text-muted)', busy)}>Cancel</button>
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

  if (loading) return <div style={{ fontSize:14, color: 'var(--text-muted)' }}>Loading run…</div>;
  if (error) return <div style={{ color: 'var(--danger)', fontSize:14 }}>{error}</div>;
  if (!run) return null;

  const phases = run.phases || [];
  const canApprove = run.status === 'awaiting_approval';
  const canCancel = !TERMINAL.has(run.status);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <StatusBadge status={run.status} />
        <span style={{ fontFamily: 'var(--font-mono)', fontSize:13, color: 'var(--text-muted)' }}>{run.run_id}</span>
      </div>

      {canApprove && (
        <div style={{ padding: 12, borderRadius: 10, border: '1px solid color-mix(in oklab, var(--warning) 35%, transparent)', background: 'color-mix(in oklab, var(--warning) 7%, transparent)', display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
          <span style={{ fontSize:13, color: 'var(--warning)', fontWeight: 700 }}><Glyph g="🔒"/> Awaiting approval — no code has been written yet.</span>
          <button disabled={acting} onClick={() => act(() => api.approveWorkflow(run.run_id, 'admin'))} style={btn('var(--success)', acting)}>Approve</button>
          <button disabled={acting} onClick={() => {
            const reason = window.prompt('Reason for rejecting this plan?');
            if (reason) act(() => api.rejectWorkflow(run.run_id, reason, 'admin'));
          }} style={btn('var(--danger)', acting)}>Reject</button>
        </div>
      )}

      <div>
        <div style={{ fontSize:13, color: 'var(--text-muted)', marginBottom: 6 }}>Phase timeline</div>
        {phases.length === 0 && <div style={{ fontSize:13, color: 'var(--text-muted)' }}>No phases yet.</div>}
        {phases.map((p) => (
          <div key={p.phase_id || p.name} style={{ display: 'flex', gap: 10, alignItems: 'center', padding: '6px 0', borderTop: '1px solid var(--border-soft)' }}>
            <span style={{ minWidth: 110, fontSize:13, color: 'var(--text-primary)', fontWeight: 600 }}>{p.name}</span>
            <Badge color={PHASE_STATUS_COLOR[p.status] || 'var(--text-muted)'}>{p.status}</Badge>
            {p.agent_role && <span style={{ fontSize:13, color: 'var(--text-muted)', fontVariantNumeric:'tabular-nums' }}>{p.agent_role}</span>}
            {p.error && <span style={{ fontSize:13, color: 'var(--danger)' }} title={p.error}><Glyph g="⚠"/></span>}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        {canCancel && (
          <button disabled={acting} onClick={() => act(() => api.cancelWorkflow(run.run_id))} style={btn('var(--text-muted)', acting)}>Cancel run</button>
        )}
        <button disabled={acting} onClick={load} style={btn('var(--accent)', acting)}>↻ Refresh</button>
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
        <h1 style={{ fontSize: 22, fontWeight:700, letterSpacing: '-0.02em' }}>Workflows</h1>
        <button onClick={load} disabled={loading} style={btn('var(--accent)', loading)}>{loading ? '…' : '↻ Refresh'}</button>
      </div>
      <p style={{ fontSize:14, color: 'var(--text-tertiary)', marginBottom: 16, maxWidth: 760 }}>
        The CRISPY plan→execute→verify workflow engine. Every run pauses at a hard
        <code> awaiting_approval</code> gate before any code is written — you approve or reject
        the plan here. Admin-only. Source: <code>workflow/</code>, API <code>/api/workflow</code>.
      </p>

      <div style={{ marginBottom: 16 }}>
        <BuildForm onBuilt={load} />
      </div>

      {loading && <div style={{ fontSize:14, color: 'var(--text-muted)' }}>Loading workflow runs…</div>}

      {!loading && error && (
        <div style={{ padding: 14, borderRadius: 12, border: '1px solid color-mix(in oklab, var(--danger) 30%, transparent)', background: 'color-mix(in oklab, var(--danger) 6%, transparent)', color: 'var(--danger)', fontSize:14, marginBottom: 16 }}>
          {error}
        </div>
      )}

      {!loading && !error && runs.length === 0 && (
        <div style={{ fontSize:14, color: 'var(--text-muted)' }}>No workflow runs yet. Start one above.</div>
      )}

      {!loading && runs.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 1fr) minmax(280px, 1.2fr)', gap: 16, alignItems: 'start' }}>
          <div style={{ borderRadius: 16, border: '1px solid var(--border)', overflow: 'hidden' }}>
            {runs.map((r) => {
              const isSel = selected === r.run_id;
              return (
                <button key={r.run_id} onClick={() => setSelected(r.run_id)} style={{
                  display: 'block', width: '100%', textAlign: 'left', padding: '12px 14px',
                  borderTop: '1px solid var(--border-soft)', background: isSel ? 'color-mix(in oklab, var(--accent) 8%, transparent)' : 'transparent',
                  cursor: 'pointer', border: 'none', borderLeft: isSel ? '3px solid var(--accent)' : '3px solid transparent',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                    <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize:14, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.title || r.run_id}</span>
                    <StatusBadge status={r.status} />
                  </div>
                  <div style={{ fontSize:13, color: 'var(--text-muted)', fontVariantNumeric:'tabular-nums', marginTop: 4 }}>{r.created_at || ''}</div>
                </button>
              );
            })}
          </div>
          <div style={{ borderRadius: 16, border: '1px solid var(--border)', padding: 16, minHeight: 120 }}>
            {selected
              ? <RunDetail runId={selected} onChanged={load} />
              : <div style={{ fontSize:14, color: 'var(--text-muted)' }}>Select a run to see its phases and approval gate.</div>}
          </div>
        </div>
      )}
    </div>
  );
}
