import React from 'react';
import * as api from '../../api';
import Spinner from '../components/ui/Spinner';
import RunDetail from './RunDetail';
import { age, costText, doingText, stateLabel, stateTone, whereText } from './runsModel';

const STATES = ['', 'running', 'queued', 'waiting_for_approval', 'retrying', 'recovering', 'failed', 'succeeded', 'cancelled'];
const th = { textAlign: 'left', fontSize: 12, color: 'var(--text-muted)', fontWeight: 600, padding: '8px 10px' };
const td = { padding: '10px', fontSize: 13, borderTop: '1px solid var(--border-soft)', verticalAlign: 'top' };

/** Runs: what is running, by whom, in which state, at what cost (GET /api/runs). */
export default function RunsScreen() {
  const [runs, setRuns] = React.useState(null);
  const [error, setError] = React.useState('');
  const [filter, setFilter] = React.useState('');
  const [selected, setSelected] = React.useState(null);

  const load = React.useCallback(async () => {
    try {
      const { data } = await api.listRuns(filter ? { state: filter, limit: 100 } : { limit: 100 });
      setRuns(data.runs || []);
      setError('');
    } catch {
      setError('Could not load runs.');
      setRuns((r) => r || []);
    }
  }, [filter]);

  React.useEffect(() => { load(); }, [load]);

  if (selected) {
    return (
      <div style={{ padding: '16px' }}>
        <RunDetail runId={selected} onBack={() => { setSelected(null); load(); }} onChanged={load} />
      </div>
    );
  }
  return (
    <div style={{ display: 'grid', gap: 12, padding: '16px' }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <h2 style={{ margin: 0, fontSize: 18 }}>Runs</h2>
        <label style={{ fontSize: 13 }}>
          State{' '}
          <select value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter by state">
            {STATES.map((s) => <option key={s} value={s}>{s ? stateLabel(s) : 'all'}</option>)}
          </select>
        </label>
        <button onClick={load} style={{ padding: '4px 12px', borderRadius: 8, border: '1px solid var(--border-strong)',
          background: 'var(--bg-elevated)', color: 'var(--text-primary)', cursor: 'pointer' }}>Refresh</button>
      </div>
      {error && <div role="alert">{error}</div>}
      {runs === null ? <Spinner center /> : runs.length === 0 ? (
        <div style={{ color: 'var(--text-muted)' }}>No runs yet.</div>
      ) : (
        <div style={{ overflowX: 'auto', border: '1px solid var(--border)', borderRadius: 10, background: 'var(--bg-surface)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 760 }}>
            <thead>
              <tr>{['Run', 'State', 'Agent', 'Owner', 'Attempt', 'Cost / budget', 'Age'].map((h) => <th key={h} style={th}>{h}</th>)}</tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.run_id}>
                  <td style={td}>
                    <button onClick={() => setSelected(r.run_id)} aria-label={`Open run ${r.run_id}`}
                      style={{ background: 'none', border: 0, padding: 0, cursor: 'pointer', color: 'var(--accent)',
                        fontFamily: 'var(--font-mono)', fontSize: 13 }}>
                      {r.run_id.slice(0, 12)}
                    </button>
                    <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>{whereText(r)} · {doingText(r)}</div>
                  </td>
                  <td style={{ ...td, color: stateTone(r.state), fontWeight: 700 }}>{stateLabel(r.state)}</td>
                  <td style={td}>{r.agent_id || '—'}</td>
                  <td style={td}>{r.owner_id || '—'}</td>
                  <td style={td}>{r.attempt}</td>
                  <td style={td}>{costText(r)}</td>
                  <td style={td}>{age(r.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
