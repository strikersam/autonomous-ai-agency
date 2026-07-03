/* eslint-disable no-unused-vars */
//
// LoopsScreen — the visible face of the Loop Engineering governance layer.
//
// The repo runs ~30 autonomous loops (cron workflows + in-process daemons),
// catalogued in loops/registry.yaml and scored by agent/loop_registry.py.
// Until now that fleet was only observable via GET /api/autonomy/status's
// `loop_readiness` summary — invisible in the UI. This screen surfaces the
// full fleet: the loop-audit readiness score, the loop-cost estimate, the
// drift status, and every catalogued loop with its maturity / cadence / cost /
// self-heal / human-gate metadata.
//
// Data source: GET /api/loops (read-only, defensive on the backend).
import React from 'react';
import * as api from '../../api';

const GRADE_COLOR = {
  A: '#46d9a4', B: '#7ed957', C: '#ffbd66', D: '#ff9f43', F: '#ff6b7d',
};

const LEVEL_META = {
  L1: { label: 'L1 · reports', color: '#8fb6ff', hint: 'Observes & reports — a human still acts' },
  L2: { label: 'L2 · assisted', color: '#7ed957', hint: 'Acts with a human in the cadence' },
  L3: { label: 'L3 · unattended', color: '#46d9a4', hint: 'Runs itself end-to-end' },
};

const COST_COLOR = {
  free: '#46d9a4', low: '#7ed957', medium: '#ffbd66', high: '#ff9f43', very_high: '#ff6b7d',
};

const GATE_META = {
  none:     { label: 'no gate',  color: '#6e7786' },
  telegram: { label: '📱 telegram', color: '#8fb6ff' },
  human:    { label: '🔒 human',    color: '#ffbd66' },
};

function fmtTokens(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

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

function ReadinessHeader({ readiness, drift, estMonthlyTokens }) {
  if (!readiness) return null;
  const grade = readiness.grade || 'F';
  const gColor = GRADE_COLOR[grade] || '#ff6b7d';
  const dims = readiness.dimensions || {};
  return (
    <div style={{
      display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'stretch', marginBottom: 18,
    }}>
      {/* Score dial */}
      <div style={{
        borderRadius: 16, border: `1px solid ${gColor}40`, background: `${gColor}0d`,
        padding: '18px 22px', minWidth: 160, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
      }}>
        <div style={{ fontSize: 44, fontWeight: 900, color: gColor, lineHeight: 1 }}>{readiness.score}</div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
          readiness · grade <b style={{ color: gColor }}>{grade}</b>
        </div>
      </div>

      {/* Dimensions + fleet shape */}
      <div style={{
        flex: 1, minWidth: 280, borderRadius: 16, border: '1px solid var(--border)',
        background: 'rgba(255,255,255,0.02)', padding: '14px 18px',
      }}>
        <div style={{ display: 'flex', gap: 18, flexWrap: 'wrap', marginBottom: 10 }}>
          {Object.entries(dims).map(([k, v]) => (
            <div key={k} style={{ minWidth: 80 }}>
              <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-primary)' }}>{v}</div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                {k.replace(/_/g, '-')}
              </div>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'center' }}>
          {Object.entries(readiness.by_level || {}).map(([lvl, count]) => (
            <Badge key={lvl} color={(LEVEL_META[lvl] || {}).color || '#8fb6ff'} title={(LEVEL_META[lvl] || {}).hint}>
              {lvl}: {count}
            </Badge>
          ))}
          <Badge color={drift && drift.ok ? '#46d9a4' : '#ff6b7d'}
                 title={drift && drift.ok ? 'Registry matches reality on disk' : 'Registry drift detected'}>
            {drift && drift.ok ? '✓ no drift' : '✗ drift'}
          </Badge>
          <Badge color="#8fb6ff" title="loop-cost: estimated fleet token spend over 30 days">
            ~{fmtTokens(estMonthlyTokens)} tok/mo
          </Badge>
          <Badge color="#7ed957" title="Share of loops that detect & repair their own failures/drift">
            self-heal {Math.round((readiness.self_heal_coverage || 0) * 100)}%
          </Badge>
        </div>
      </div>
    </div>
  );
}

export default function LoopsScreen() {
  const [data, setData]       = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError]     = React.useState(null);

  const load = React.useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const { data } = await api.getLoops();
      if (!data || data.ok === false) {
        setError((data && data.error) || 'Loop registry unavailable.');
        setData(data || null);
      } else {
        setData(data);
      }
    } catch (e) {
      setError(e?.message || 'Could not load the loop fleet.');
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { load(); }, [load]);

  const loops = (data && data.loops) || [];

  return (
    <div style={{ padding: '22px 26px', height: '100%', overflowY: 'auto' }} className="scrollbar-hide">
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 6, flexWrap: 'wrap', gap: 8 }}>
        <h1 style={{ fontSize: 22, fontWeight: 900, letterSpacing: '-0.02em' }}>Loop Engineering</h1>
        <button onClick={load} disabled={loading} style={{
          padding: '6px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700,
          background: 'rgba(93,162,255,0.10)', border: '1px solid rgba(93,162,255,0.30)',
          color: 'var(--accent)', cursor: loading ? 'default' : 'pointer',
        }}>{loading ? '…' : '↻ Refresh'}</button>
      </div>
      <p style={{ fontSize: 13, color: 'var(--text-tertiary)', marginBottom: 18, maxWidth: 760 }}>
        The autonomous loop fleet — every recurring workflow and in-process daemon that keeps this
        repo up to date, learning, and self-healing. Scored by <code>loop-audit</code>, costed by
        <code> loop-cost</code>, and kept honest by drift detection. Source of truth:
        <code> loops/registry.yaml</code>.
      </p>

      {loading && (
        <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading the loop fleet…</div>
      )}

      {!loading && error && (
        <div style={{
          padding: 14, borderRadius: 12, border: '1px solid rgba(255,107,125,0.30)',
          background: 'rgba(255,107,125,0.06)', color: '#ff6b7d', fontSize: 13, marginBottom: 16,
        }}>
          {error}
        </div>
      )}

      {!loading && data && data.readiness && (
        <ReadinessHeader readiness={data.readiness} drift={data.drift} estMonthlyTokens={data.est_monthly_tokens} />
      )}

      {!loading && (data?.readiness?.notes || []).length > 0 && (
        <div style={{ marginBottom: 16, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {data.readiness.notes.map((n, i) => (
            <div key={i} style={{ fontSize: 12, color: '#ffbd66', fontFamily: 'var(--font-mono)' }}>⚠ {n}</div>
          ))}
        </div>
      )}

      {!loading && loops.length > 0 && (
        <div style={{ borderRadius: 16, border: '1px solid var(--border)', overflow: 'hidden' }}>
          <div style={{
            display: 'grid', gridTemplateColumns: '1.6fr 0.9fr 1fr 0.8fr 0.8fr 0.9fr',
            gap: 8, padding: '10px 14px', background: 'rgba(255,255,255,0.03)',
            fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
            textTransform: 'uppercase', letterSpacing: '0.08em',
          }}>
            <div>Loop</div><div>Maturity</div><div>Cadence</div><div>Cost</div><div>Self-heal</div><div>Gate</div>
          </div>
          {loops.map((l) => {
            const lvl = LEVEL_META[l.level] || { label: l.level, color: '#8fb6ff', hint: '' };
            return (
              <div key={l.id} style={{
                display: 'grid', gridTemplateColumns: '1.6fr 0.9fr 1fr 0.8fr 0.8fr 0.9fr',
                gap: 8, padding: '12px 14px', alignItems: 'center',
                borderTop: '1px solid var(--border-soft)', fontSize: 12,
              }}>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 700, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.name}</div>
                  <div title={l.purpose} style={{ fontSize: 11, color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{l.purpose || l.source}</div>
                </div>
                <div><Badge color={lvl.color} title={lvl.hint}>{lvl.label}</Badge></div>
                <div style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>{l.cadence}</div>
                <div><Badge color={COST_COLOR[l.cost] || '#6e7786'} title={`~${fmtTokens(l.est_monthly_tokens)} tokens/mo`}>{String(l.cost).replace('_', ' ')}</Badge></div>
                <div style={{ color: l.self_heal ? '#46d9a4' : '#6e7786', fontWeight: 700 }}>{l.self_heal ? '✓ yes' : '—'}</div>
                <div><Badge color={(GATE_META[l.gate] || GATE_META.none).color}>{(GATE_META[l.gate] || GATE_META.none).label}</Badge></div>
              </div>
            );
          })}
        </div>
      )}

      {!loading && !error && loops.length === 0 && (
        <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>No loops catalogued yet.</div>
      )}
    </div>
  );
}
