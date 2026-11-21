import React from 'react';
import * as api from '../../api';
import Spinner from '../components/ui/Spinner';
import {
  age, canCancel, canRetry, costText, doingText, isBlocked, recoverText, stateLabel, stateTone,
  whereText,
} from './runsModel';

const card = {
  border: '1px solid var(--border)', borderRadius: 10, background: 'var(--bg-surface)', padding: 16,
};
const label = { fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, marginBottom: 2 };
const btn = {
  padding: '6px 14px', borderRadius: 8, border: '1px solid var(--border-strong)',
  background: 'var(--bg-elevated)', color: 'var(--text-primary)', fontWeight: 600, cursor: 'pointer',
};

function Fact({ q, children }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div style={label}>{q}</div>
      <div style={{ fontSize: 14, overflowWrap: 'anywhere' }}>{children}</div>
    </div>
  );
}

function Timeline({ events }) {
  if (!events.length) return <div style={{ color: 'var(--text-muted)' }}>No events yet.</div>;
  return (
    <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 6 }}>
      {events.map((e) => (
        <li key={e.event_id || e.seq} style={{ display: 'flex', gap: 10, fontSize: 13 }}>
          <span style={{ color: 'var(--text-muted)', width: 28, textAlign: 'right' }}>{e.seq}</span>
          <strong style={{ minWidth: 130 }}>{stateLabel(e.kind)}</strong>
          <span style={{ color: 'var(--text-secondary)', overflowWrap: 'anywhere' }}>
            {e.data && Object.keys(e.data).length ? JSON.stringify(e.data) : ''}
          </span>
        </li>
      ))}
    </ol>
  );
}

/** One run: the operator's questions answered from /api/runs/{id}, /events, /artifacts. */
export default function RunDetail({ runId, onBack, onChanged }) {
  const [state, setState] = React.useState({ loading: true });
  const [busy, setBusy] = React.useState(false);
  const [message, setMessage] = React.useState('');

  const load = React.useCallback(async () => {
    try {
      const [run, events, artifacts, caps] = await Promise.all([
        api.getRun(runId), api.getRunEvents(runId, { limit: 200 }), api.getRunArtifacts(runId),
        api.getRunCapabilities().catch(() => ({ data: null })),
      ]);
      setState({ run: run.data, events: events.data.events || [],
                 artifacts: artifacts.data.artifacts || [], caps: caps.data });
    } catch (err) {
      setState({ error: err?.response?.status === 404 ? 'Run not found.' : 'Could not load this run.' });
    }
  }, [runId]);

  React.useEffect(() => { setState({ loading: true }); load(); }, [load]);

  const act = async (fn, okText) => {
    setBusy(true); setMessage('');
    try {
      const { data } = await fn(runId);
      setMessage(okText(data));
      await load();
      if (onChanged) onChanged();
    } catch (err) {
      setMessage(err?.response?.status === 409 ? 'That run was already changed; refreshed.' : 'The action failed.');
      await load();
    } finally { setBusy(false); }
  };

  if (state.loading) return <Spinner center />;
  if (state.error) return <div role="alert">{state.error} <button style={btn} onClick={onBack}>Back</button></div>;
  const { run, events, artifacts, caps } = state;
  return (
    <div style={{ display: 'grid', gap: 14 }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <button style={btn} onClick={onBack}>Back to runs</button>
        <h2 style={{ margin: 0, fontSize: 18, fontFamily: 'var(--font-mono)' }}>{run.run_id}</h2>
        <span style={{ color: stateTone(run.state), fontWeight: 700 }}>{stateLabel(run.state)}</span>
        <span style={{ flex: 1 }} />
        {canCancel(run.state) && (
          <button style={btn} disabled={busy} onClick={() => act(api.cancelRun, (d) => (d.settled ? 'Run cancelled.' : 'Cancel requested.'))}>
            Cancel run
          </button>
        )}
        {canRetry(run.state) && (
          <button style={btn} disabled={busy} onClick={() => act(api.retryRun, (d) => `Retry queued as ${d.run_id}.`)}>
            Retry run
          </button>
        )}
      </div>
      {message && <div role="status" style={{ fontSize: 13 }}>{message}</div>}
      <section aria-label="Run summary" style={{ ...card, display: 'grid', gap: 14,
        gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))' }}>
        <Fact q="Which agent">{run.agent_id || '—'}</Fact>
        <Fact q="Where it runs">{whereText(run)}</Fact>
        <Fact q="Doing now">{doingText(run)}</Fact>
        <Fact q="Blocked">{isBlocked(run.state) ? (run.waiting_reason || stateLabel(run.state)) : 'No'}</Fact>
        <Fact q="Cost / budget">{costText(run)}</Fact>
        <Fact q="Can it recover">{recoverText(caps, run)}</Fact>
        <Fact q="Attempt">{run.attempt}</Fact>
        <Fact q="Age">{age(run.created_at)}</Fact>
      </section>
      <section aria-label="Completed events" style={card}>
        <div style={{ ...label, marginBottom: 8 }}>Completed events ({events.length})</div>
        <Timeline events={events} />
      </section>
      <section aria-label="Evidence" style={card}>
        <div style={{ ...label, marginBottom: 8 }}>Evidence ({artifacts.length})</div>
        {artifacts.length === 0 ? <div style={{ color: 'var(--text-muted)' }}>No artifacts recorded.</div> : (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {artifacts.map((a) => <li key={a} style={{ overflowWrap: 'anywhere' }}>{a}</li>)}
          </ul>
        )}
        {run.skill_versions && Object.keys(run.skill_versions).length > 0 && (
          <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text-muted)' }}>
            {Object.keys(run.skill_versions).length} skill versions pinned at start.
          </div>
        )}
      </section>
    </div>
  );
}
