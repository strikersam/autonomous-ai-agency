import React from 'react';
import * as api from '../../api';

// portfolio.jsx — Agentic Portfolio Management
// WSJF prioritisation · Now/Next/Later roadmap · capacity · sprint health.
// Reads the live /api/portfolio/board payload (agents/portfolio_api.py).

const HEALTH = {
  on_track:  { label: 'On track',  color: '#46d9a4' },
  at_risk:   { label: 'At risk',   color: '#ffbd66' },
  off_track: { label: 'Off track', color: '#ff6b7d' },
  complete:  { label: 'Complete',  color: '#5da2ff' },
};

const STATUS_COLOR = {
  proposed:    '#a8b3c2',
  approved:    '#5da2ff',
  in_progress: '#46d9a4',
  done:        '#7c9dff',
  cancelled:   '#6e7786',
};

const HORIZONS = [
  { id: 'now',  label: 'Now',  hint: 'Committed this increment',  color: '#46d9a4' },
  { id: 'next', label: 'Next', hint: 'Up next as capacity frees', color: '#5da2ff' },
  { id: 'later',label: 'Later',hint: 'On the radar',              color: '#c4b5fd' },
];

// Provenance — where each auto-generated initiative came from.
const SOURCE = {
  bug:      { label: 'Bug',      icon: '🐞', color: '#ff6b7d' },
  pr:       { label: 'Open PR',  icon: '🔀', color: '#46d9a4' },
  roadmap:  { label: 'Roadmap',  icon: '🗺️', color: '#5da2ff' },
  sprint:   { label: 'Sprint',   icon: '🏃', color: '#7c9dff' },
  research: { label: 'Research', icon: '🔬', color: '#c4b5fd' },
  manual:   { label: 'Manual',   icon: '✎',  color: '#a8b3c2' },
};

function SourceBadge({ source, title }) {
  const s = SOURCE[source] || SOURCE.manual;
  return (
    <span title={title || ''} style={{ fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 999, color: s.color, background: `${s.color}14`, border: `1px solid ${s.color}30`, whiteSpace: 'nowrap' }}>
      {s.icon} {s.label}
    </span>
  );
}

function timeAgo(ts) {
  if (!ts) return 'never';
  const secs = Math.max(0, Math.floor(Date.now() / 1000 - ts));
  if (secs < 90) return 'just now';
  if (secs < 3600) return `${Math.round(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.round(secs / 3600)}h ago`;
  return `${Math.round(secs / 86400)}d ago`;
}

function StatChip({ label, value, accent = 'var(--accent)' }) {
  return (
    <div style={{ flex: '1 1 140px', minWidth: 130, padding: '12px 14px', borderRadius: 14, background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.09)' }}>
      <div style={{ fontSize: 24, fontWeight: 800, color: accent, letterSpacing: '-0.03em', lineHeight: 1.1 }}>{value}</div>
      <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.10em', marginTop: 4 }}>{label}</div>
    </div>
  );
}

function StatusPill({ status }) {
  const c = STATUS_COLOR[status] || 'var(--text-muted)';
  return (
    <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 999, color: c, background: `${c}14`, border: `1px solid ${c}28`, whiteSpace: 'nowrap' }}>
      {String(status).replace('_', ' ')}
    </span>
  );
}

function WsjfBar({ value, max }) {
  const pct = max > 0 ? Math.max(4, Math.round((value / max) * 100)) : 0;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, height: 6, borderRadius: 999, background: 'rgba(255,255,255,0.07)', overflow: 'hidden', minWidth: 50 }}>
        <div style={{ width: `${pct}%`, height: '100%', borderRadius: 999, background: 'linear-gradient(90deg,#3a7fe8,#5da2ff)' }} />
      </div>
      <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#fff', width: 38, textAlign: 'right' }}>{value.toFixed(2)}</span>
    </div>
  );
}

function InitiativeCard({ init }) {
  const c = STATUS_COLOR[init.status] || 'var(--text-muted)';
  return (
    <div style={{ padding: '11px 13px', borderRadius: 13, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', borderLeft: `2px solid ${c}` }}>
      <div style={{ fontSize: 13, fontWeight: 700, color: '#fff', lineHeight: 1.35, marginBottom: 7 }}>{init.title}</div>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <SourceBadge source={init.source} title={init.rationale} />
          <StatusPill status={init.status} />
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          <span title="Job size (effort)">⏱ {init.job_size}</span>
          <span title="WSJF score" style={{ color: 'var(--accent)', fontWeight: 700 }}>WSJF {init.wsjf.toFixed(2)}</span>
        </div>
      </div>
    </div>
  );
}

function SprintHealthCard({ sprint }) {
  const h = HEALTH[sprint.health] || { label: sprint.health, color: 'var(--text-muted)' };
  const pct = Math.min(100, Math.round(sprint.completion_percentage));
  return (
    <div style={{ padding: '14px 16px', borderRadius: 16, background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.09)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 10 }}>
        <div style={{ fontSize: 14, fontWeight: 800, color: '#fff' }}>{sprint.name}</div>
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', padding: '3px 9px', borderRadius: 999, color: h.color, background: `${h.color}14`, border: `1px solid ${h.color}30` }}>
          {h.label}
        </span>
      </div>
      <div style={{ height: 8, borderRadius: 999, background: 'rgba(255,255,255,0.07)', overflow: 'hidden', marginBottom: 8 }}>
        <div style={{ width: `${pct}%`, height: '100%', borderRadius: 999, background: h.color, transition: 'width 0.4s ease' }} />
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
        <span><span style={{ color: 'var(--text-secondary)' }}>{sprint.completed_points}</span>/{sprint.total_points} pts</span>
        <span>{pct}% done</span>
        {sprint.scope_added > 0 && <span style={{ color: '#ffbd66' }}>+{sprint.scope_added} scope creep</span>}
        <span>{sprint.days_remaining}d left</span>
      </div>
    </div>
  );
}

export default function PortfolioScreen() {
  const [board, setBoard] = React.useState(null);   // null = loading
  const [error, setError] = React.useState('');
  const [refreshing, setRefreshing] = React.useState(false);

  const load = React.useCallback(async () => {
    try {
      const { data } = await api.getPortfolioBoard();
      setBoard(data);
      setError('');
    } catch (e) {
      setError(api.fmtErr?.(e?.response?.data?.detail) || 'Could not load the portfolio board.');
    }
  }, []);

  React.useEffect(() => { load(); }, [load]);

  const refresh = async () => {
    setRefreshing(true);
    try { const { data } = await api.refreshPortfolio(); setBoard(data); setError(''); }
    catch { /* ignore */ }
    finally { setRefreshing(false); }
  };

  if (board === null && !error) {
    return <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13, fontFamily: 'var(--font-mono)' }}>Loading portfolio…</div>;
  }
  if (error && !board) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <div style={{ color: 'var(--danger)', fontSize: 14, marginBottom: 12 }}>{error}</div>
        <button onClick={load} style={btnStyle}>Retry</button>
      </div>
    );
  }

  const m = board.metrics;
  const ranked = board.ranked || [];
  const maxWsjf = ranked.reduce((mx, i) => Math.max(mx, i.wsjf), 0);
  const roadmap = board.roadmap || {};
  const unscheduled = roadmap.unscheduled || [];
  const alloc = board.allocation || {};
  const sprints = board.sprints || [];

  return (
    <div style={{ padding: '20px 16px 48px', maxWidth: 1040, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 6 }}>Agentic Portfolio · WSJF</div>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10, marginBottom: 16 }}>
        <div>
          <h1 style={{ fontSize: 26, fontWeight: 800, color: '#fff', letterSpacing: '-0.04em', lineHeight: 1.1, marginBottom: 6 }}>Portfolio &amp; Roadmap</h1>
          <p style={{ fontSize: 14, color: 'var(--text-tertiary)', lineHeight: 1.6, maxWidth: 640 }}>
            Initiatives <strong style={{ color: 'var(--text-secondary)' }}>auto-discovered</strong> from your roadmap backlog, open bugs, in-flight PRs and research trends — ranked by <strong style={{ color: 'var(--text-secondary)' }}>WSJF</strong> (Cost of Delay ÷ Job Size) and allocated to <strong style={{ color: 'var(--text-secondary)' }}>Now / Next / Later</strong>.
          </p>
        </div>
        <div style={{ textAlign: 'right' }}>
          <button onClick={refresh} disabled={refreshing} style={{ ...btnStyle, opacity: refreshing ? 0.6 : 1 }}>
            {refreshing ? 'Researching…' : '↻ Refresh intelligence'}
          </button>
          <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 6 }}>updated {timeAgo(board.generated_at)}</div>
        </div>
      </div>

      {/* Sources legend — provenance of the auto-generated initiatives */}
      {Object.keys(board.sources || {}).length > 0 && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
          {Object.entries(board.sources).map(([src, n]) => {
            const s = SOURCE[src] || SOURCE.manual;
            return (
              <span key={src} style={{ fontSize: 11, fontFamily: 'var(--font-mono)', padding: '4px 10px', borderRadius: 999, color: s.color, background: `${s.color}10`, border: `1px solid ${s.color}26` }}>
                {s.icon} {n} from {s.label.toLowerCase()}
              </span>
            );
          })}
        </div>
      )}

      {/* Metrics strip */}
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 22 }}>
        <StatChip label="Initiatives" value={m.total_initiatives} />
        <StatChip label="Active" value={m.active_initiatives} accent="#46d9a4" />
        <StatChip label="Avg WSJF" value={m.average_wsjf.toFixed(2)} accent="#5da2ff" />
        <StatChip label="Total Cost of Delay" value={m.total_cost_of_delay} accent="#ffbd66" />
        <StatChip label="Increment capacity" value={`${alloc.committed_job_size}/${alloc.capacity}`} accent="#c4b5fd" />
      </div>

      {ranked.length === 0 && (
        <div style={{ padding: '28px 20px', borderRadius: 16, background: 'rgba(255,255,255,0.025)', border: '1px dashed rgba(255,255,255,0.12)', textAlign: 'center', marginBottom: 22 }}>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>No initiatives discovered yet</div>
          <div style={{ fontSize: 13, color: 'var(--text-muted)', lineHeight: 1.6, maxWidth: 460, margin: '0 auto' }}>
            The portfolio auto-builds from your roadmap backlog, open bugs, in-flight PRs and research trends. Connect GitHub or add backlog items, then hit <strong style={{ color: 'var(--accent)' }}>Refresh intelligence</strong>.
          </div>
        </div>
      )}

      {/* Roadmap board */}
      <SectionLabel>Roadmap — Now / Next / Later</SectionLabel>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(240px,1fr))', gap: 12, marginBottom: 14 }}>
        {HORIZONS.map(h => {
          const items = roadmap[h.id] || [];
          const colLoad = items.reduce((s, i) => s + i.job_size, 0);
          return (
            <div key={h.id} style={{ borderRadius: 16, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)', overflow: 'hidden' }}>
              <div style={{ padding: '11px 14px', borderBottom: '1px solid rgba(255,255,255,0.07)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ width: 8, height: 8, borderRadius: '50%', background: h.color }} />
                  <span style={{ fontSize: 13, fontWeight: 800, color: '#fff' }}>{h.label}</span>
                </div>
                <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{colLoad}/{board.horizon_capacity} pts</span>
              </div>
              <div style={{ padding: 10, display: 'flex', flexDirection: 'column', gap: 8, minHeight: 60 }}>
                {items.length === 0
                  ? <div style={{ fontSize: 11, color: 'var(--text-muted)', textAlign: 'center', padding: '14px 0', fontFamily: 'var(--font-mono)' }}>{h.hint}</div>
                  : items.map(i => <InitiativeCard key={i.initiative_id} init={i} />)}
              </div>
            </div>
          );
        })}
      </div>
      {unscheduled.length > 0 && (
        <div style={{ marginBottom: 24, padding: '12px 14px', borderRadius: 14, background: 'rgba(255,255,255,0.02)', border: '1px dashed rgba(255,255,255,0.12)' }}>
          <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.10em', marginBottom: 8 }}>Backlog — beyond current capacity ({unscheduled.length})</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
            {unscheduled.map(i => (
              <span key={i.initiative_id} style={{ fontSize: 12, padding: '5px 10px', borderRadius: 999, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.10)', color: 'var(--text-secondary)' }}>
                {i.title} <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 10 }}>· {i.wsjf.toFixed(2)}</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* WSJF priority table */}
      <SectionLabel>WSJF priority ranking</SectionLabel>
      <div style={{ borderRadius: 16, border: '1px solid rgba(255,255,255,0.08)', overflow: 'hidden', marginBottom: 24 }}>
        <div style={{ overflowX: 'auto' }} className="scrollbar-hide">
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 620 }}>
            <thead>
              <tr style={{ background: 'rgba(255,255,255,0.03)' }}>
                {['#', 'Initiative', 'Source', 'Status', 'BV', 'TC', 'RR', 'CoD', 'Size', 'WSJF'].map((h, i) => (
                  <th key={h} style={{ ...thStyle, textAlign: i <= 1 ? 'left' : 'center' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ranked.map((i, idx) => (
                <tr key={i.initiative_id} style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                  <td style={{ ...tdStyle, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{idx + 1}</td>
                  <td style={{ ...tdStyle, color: '#fff', fontWeight: 600, textAlign: 'left' }}>{i.title}</td>
                  <td style={tdStyle}><SourceBadge source={i.source} title={i.rationale} /></td>
                  <td style={tdStyle}><StatusPill status={i.status} /></td>
                  <td style={tdNum}>{i.business_value}</td>
                  <td style={tdNum}>{i.time_criticality}</td>
                  <td style={tdNum}>{i.risk_reduction}</td>
                  <td style={{ ...tdNum, color: '#ffbd66', fontWeight: 700 }}>{i.cost_of_delay}</td>
                  <td style={tdNum}>{i.job_size}</td>
                  <td style={{ ...tdStyle, minWidth: 130 }}><WsjfBar value={i.wsjf} max={maxWsjf} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Sprint health */}
      {sprints.length > 0 && (
        <>
          <SectionLabel>Sprint health — rolled up from agentic-agile</SectionLabel>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(260px,1fr))', gap: 12 }}>
            {sprints.map(s => <SprintHealthCard key={s.sprint_id} sprint={s} />)}
          </div>
        </>
      )}

      <div style={{ marginTop: 22, padding: '10px 14px', borderRadius: 12, background: 'rgba(93,162,255,0.05)', border: '1px solid rgba(93,162,255,0.15)', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
        <strong style={{ color: 'var(--accent)' }}>How ranking works.</strong> WSJF = (Business Value + Time Criticality + Risk Reduction) ÷ Job Size — the SAFe economic model. Higher WSJF is scheduled sooner; the roadmap greedily fills each horizon to capacity by priority.
      </div>
    </div>
  );
}

function SectionLabel({ children }) {
  return <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.12em', textTransform: 'uppercase', margin: '4px 0 12px', fontWeight: 700 }}>{children}</div>;
}

const btnStyle = { padding: '8px 16px', borderRadius: 10, fontSize: 13, fontWeight: 700, cursor: 'pointer', background: 'rgba(93,162,255,0.12)', border: '1px solid rgba(93,162,255,0.30)', color: 'var(--accent)', fontFamily: 'var(--font-main)' };
const thStyle = { padding: '10px 12px', fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', fontWeight: 700 };
const tdStyle = { padding: '11px 12px', fontSize: 13, color: 'var(--text-secondary)', textAlign: 'center', verticalAlign: 'middle' };
const tdNum = { ...tdStyle, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' };
