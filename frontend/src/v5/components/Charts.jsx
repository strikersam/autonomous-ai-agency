/*
 * Charts.jsx — dependency-free SVG data visualizations for the v5 dashboard.
 *
 * Deliberately zero-dependency (no recharts/d3): the bundle stays small and the
 * charts inherit the design-system CSS variables so they theme automatically.
 * Each chart is defensive — empty/short/all-zero data renders a graceful
 * placeholder rather than throwing.
 */
import React from 'react';

const ACCENT = 'var(--accent)';

function EmptyChart({ height = 64, label = 'No data yet' }) {
  return (
    <div
      style={{
        height,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 11,
        fontFamily: 'var(--font-mono)',
        color: 'var(--text-muted)',
        border: '1px dashed rgba(255,255,255,0.08)',
        borderRadius: 10,
      }}
    >
      {label}
    </div>
  );
}

/**
 * Sparkline — a compact filled area + line for a single numeric series.
 * @param {number[]} values
 */
export function Sparkline({ values = [], height = 56, stroke = ACCENT, fill = 'rgba(93,162,255,0.16)', strokeWidth = 1.75 }) {
  const data = (values || []).filter((v) => Number.isFinite(v));
  if (data.length < 2) return <EmptyChart height={height} />;

  const W = 100; // viewBox width (responsive via preserveAspectRatio none)
  const H = height;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const stepX = W / (data.length - 1);
  const pts = data.map((v, i) => {
    const x = i * stepX;
    const y = H - ((v - min) / range) * (H - 6) - 3;
    return [x, y];
  });
  const line = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(2)},${y.toFixed(2)}`).join(' ');
  const area = `${line} L${W},${H} L0,${H} Z`;
  const [lastX, lastY] = pts[pts.length - 1];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" width="100%" height={H} role="img" aria-label="trend sparkline">
      <path d={area} fill={fill} stroke="none" />
      <path d={line} fill="none" stroke={stroke} strokeWidth={strokeWidth} strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      <circle cx={lastX} cy={lastY} r={2.4} fill={stroke} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

/**
 * BarChart — labelled vertical bars. Each datum: { label, value, color? }.
 */
export function BarChart({ data = [], height = 120, accent = ACCENT }) {
  const rows = (data || []).filter((d) => d && Number.isFinite(d.value));
  if (rows.length === 0) return <EmptyChart height={height} />;
  const max = Math.max(...rows.map((d) => d.value), 1);

  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, height, padding: '4px 0' }}>
      {rows.map((d, i) => {
        const pct = Math.max(2, Math.round((d.value / max) * 100));
        return (
          <div key={d.label ?? i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, minWidth: 0 }}>
            <div style={{ flex: 1, width: '100%', display: 'flex', alignItems: 'flex-end' }}>
              <div
                title={`${d.label}: ${d.value}`}
                style={{
                  width: '100%',
                  height: `${pct}%`,
                  borderRadius: '6px 6px 2px 2px',
                  background: d.color || `linear-gradient(180deg, ${accent}, rgba(93,162,255,0.35))`,
                  transition: 'height 0.6s ease',
                }}
              />
            </div>
            <span
              style={{
                fontSize: 9,
                fontFamily: 'var(--font-mono)',
                color: 'var(--text-muted)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                maxWidth: '100%',
              }}
            >
              {d.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/**
 * Donut — proportional ring. Each datum: { label, value, color }.
 * Renders a center total and a compact legend.
 */
export function Donut({ data = [], size = 116, thickness = 14, centerLabel }) {
  const rows = (data || []).filter((d) => d && Number.isFinite(d.value) && d.value > 0);
  const total = rows.reduce((s, d) => s + d.value, 0);
  if (total === 0) return <EmptyChart height={size} label="Nothing to chart" />;

  const r = (size - thickness) / 2;
  const cx = size / 2;
  const cy = size / 2;
  const circ = 2 * Math.PI * r;
  let offset = 0;

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="distribution donut">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={thickness} />
        {rows.map((d, i) => {
          const frac = d.value / total;
          const dash = frac * circ;
          const seg = (
            <circle
              key={d.label ?? i}
              cx={cx}
              cy={cy}
              r={r}
              fill="none"
              stroke={d.color || ACCENT}
              strokeWidth={thickness}
              strokeDasharray={`${dash} ${circ - dash}`}
              strokeDashoffset={-offset}
              strokeLinecap="butt"
              transform={`rotate(-90 ${cx} ${cy})`}
              style={{ transition: 'stroke-dasharray 0.6s ease' }}
            />
          );
          offset += dash;
          return seg;
        })}
        <text x={cx} y={cy - 2} textAnchor="middle" style={{ fontSize: 20, fontWeight: 800, fill: 'var(--text-primary)' }}>
          {total}
        </text>
        <text x={cx} y={cy + 14} textAnchor="middle" style={{ fontSize: 9, fontFamily: 'var(--font-mono)', fill: 'var(--text-muted)', letterSpacing: '0.1em' }}>
          {(centerLabel || 'TOTAL').toUpperCase()}
        </text>
      </svg>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, minWidth: 90 }}>
        {rows.map((d, i) => (
          <div key={d.label ?? i} style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
            <span style={{ width: 9, height: 9, borderRadius: 3, background: d.color || ACCENT, flexShrink: 0 }} />
            <span style={{ fontSize: 11, color: 'var(--text-secondary)', flex: 1 }}>{d.label}</span>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{d.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * ExecutionTimeline — a Gantt-style bar showing agent phase durations.
 * @param {Array<{phase: string, duration_ms: number}>} log
 */
export function ExecutionTimeline({ log = [] }) {
  const phases = (log || []).filter(e => e.phase && e.duration_ms > 0);
  if (!phases.length) return null;
  const total = phases.reduce((s, e) => s + e.duration_ms, 0) || 1;
  const colors = { plan: '#3b82f6', execute: '#22c55e', verify: '#a855f7', failed: '#ef4444' };
  return (
    <div style={{ marginTop: 8 }}>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 4, fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.08em' }}>Execution timeline</div>
      <div style={{ display: 'flex', height: 20, borderRadius: 4, overflow: 'hidden', gap: 1 }}>
        {phases.map((e, i) => (
          <div key={i}
            title={`${e.phase}: ${(e.duration_ms/1000).toFixed(1)}s`}
            style={{
              flex: e.duration_ms / total,
              background: colors[e.phase] || '#6b7280',
              minWidth: 3,
              transition: 'flex 0.3s'
            }} />
        ))}
      </div>
      <div style={{ display: 'flex', gap: 12, marginTop: 4, flexWrap: 'wrap' }}>
        {phases.map((e, i) => (
          <span key={i} style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            <span style={{ display:'inline-block', width:8, height:8, borderRadius:2, background: colors[e.phase]||'#6b7280', marginRight:3 }} />
            {e.phase} {(e.duration_ms/1000).toFixed(1)}s
          </span>
        ))}
      </div>
    </div>
  );
}

const Charts = { Sparkline, BarChart, Donut, ExecutionTimeline };
export default Charts;
