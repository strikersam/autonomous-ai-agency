/* eslint-disable jsx-a11y/anchor-is-valid */
import React from 'react';
import { useSafeData } from '../hooks/useSafeData';

const API = process.env.REACT_APP_BACKEND_URL || '';

// ── status helpers ────────────────────────────────────────────────────────────
function statusStyle(s) {
  if (s === 'pass') return { icon: '✓', color: '#46d9a4', bg: 'rgba(70,217,164,0.08)', border: 'rgba(70,217,164,0.18)' };
  if (s === 'warn') return { icon: '⚠', color: '#ffbd66', bg: 'rgba(255,189,102,0.08)', border: 'rgba(255,189,102,0.20)' };
  return               { icon: '✕', color: '#ff6b7d',  bg: 'rgba(255,107,125,0.08)', border: 'rgba(255,107,125,0.18)' };
}

// ── skeleton ──────────────────────────────────────────────────────────────────
function Skeleton({ h = 56 }) {
  return (
    <div style={{
      height: h, borderRadius: 12, marginBottom: 8,
      background: 'linear-gradient(90deg,rgba(255,255,255,0.04) 25%,rgba(255,255,255,0.08) 50%,rgba(255,255,255,0.04) 75%)',
      backgroundSize: '200% 100%', animation: 'shimmer 1.6s infinite',
    }}/>
  );
}

// ── single check row ──────────────────────────────────────────────────────────
function CheckRow({ check, expanded, onToggle, onSetup }) {
  const st = statusStyle(check.status);
  return (
    <div style={{ borderRadius: 14, border: `1px solid ${st.border}`, background: st.bg, overflow: 'hidden' }}>
      <button onClick={onToggle} style={{
        width: '100%', display: 'flex', alignItems: 'flex-start', gap: 12,
        padding: '13px 16px', background: 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left',
      }}>
        <div style={{
          width: 28, height: 28, borderRadius: 8, flexShrink: 0, marginTop: 1,
          background: `${st.color}20`, border: `1px solid ${st.color}35`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 13, color: st.color, fontWeight: 700,
        }}>{st.icon}</div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap', marginBottom: 3 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#fff' }}>{check.label}</span>
            <span style={{
              fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', textTransform: 'uppercase',
              padding: '2px 7px', borderRadius: 999, color: 'var(--text-muted)',
              background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.10)',
            }}>{check.category}</span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)', lineHeight: 1.5 }}>{check.detail}</div>
        </div>

        {check.explanation && (
          <span style={{ fontSize: 14, color: 'var(--text-muted)', transform: expanded ? 'rotate(90deg)' : 'none', display: 'inline-block', transition: 'transform 0.2s' }}>›</span>
        )}
      </button>

      {expanded && (check.explanation || onSetup) && (
        <div style={{ padding: '0 16px 14px 56px' }}>
          {check.explanation && (
            <div style={{ padding: '12px 14px', borderRadius: 12, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 6 }}>
                Plain-language explanation
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.65 }}>{check.explanation}</div>
            </div>
          )}
          {onSetup && (
            <button onClick={(e) => { e.stopPropagation(); onSetup(); }} style={{
              marginTop: 8, padding: '8px 16px', borderRadius: 10, fontSize: 12, fontWeight: 700,
              background: 'rgba(93,162,255,0.15)', border: '1px solid rgba(93,162,255,0.30)',
              color: 'var(--accent)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
            }}>
              ⚙ Setup GitHub →
            </button>
          )}
        </div>
      )}
    </div>
  );
}

// ── error banner shown when the whole /api/doctor call fails ──────────────────
function ErrorBanner({ message, onRetry }) {
  return (
    <div style={{
      padding: '14px 18px', borderRadius: 14,
      background: 'rgba(255,107,125,0.08)', border: '1px solid rgba(255,107,125,0.20)',
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, marginBottom: 16,
    }}>
      <div>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#ff6b7d', marginBottom: 2 }}>Doctor report unavailable</div>
        <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{message}</div>
      </div>
      <button onClick={onRetry} style={{
        padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer',
        background: 'rgba(255,107,125,0.15)', border: '1px solid rgba(255,107,125,0.30)', color: '#ff6b7d',
      }}>Retry</button>
    </div>
  );
}

// ── main screen ───────────────────────────────────────────────────────────────
export default function DoctorScreen({ onNavigate }) {
  const [data, states, reload] = useSafeData(API, { report: '/api/doctor' }, { refreshMs: 60_000 });
  const [expanded, setExpanded] = React.useState(null);

  const report  = data.report;
  const loading = states.report?.loading;
  const error   = states.report?.error;

  const checks    = report?.checks  || [];
  const passCount = checks.filter(c => c.status === 'pass').length;
  const warnCount = checks.filter(c => c.status === 'warn').length;
  const failCount = checks.filter(c => c.status === 'fail').length;

  const runAt = report?.run_at ? new Date(report.run_at).toLocaleTimeString() : null;

  return (
    <div style={{ padding: '20px 16px 48px', maxWidth: 780, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 22 }}>
        <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 6 }}>Diagnostics</div>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
          <div>
            <h1 style={{ fontSize: 26, fontWeight: 800, color: '#fff', letterSpacing: '-0.04em', lineHeight: 1.1, marginBottom: 4 }}>Doctor</h1>
            <p style={{ fontSize: 14, color: 'var(--text-tertiary)', lineHeight: 1.5 }}>Live preflight checks, runtime health, and configuration diagnostics.</p>
          </div>
          <button onClick={reload} disabled={loading} style={{
            display: 'inline-flex', alignItems: 'center', gap: 7,
            padding: '10px 20px', borderRadius: 999, fontSize: 13, fontWeight: 700, cursor: loading ? 'default' : 'pointer',
            background: loading ? 'rgba(93,162,255,0.08)' : 'rgba(93,162,255,0.15)',
            border: '1px solid rgba(93,162,255,0.30)', color: loading ? 'var(--text-muted)' : 'var(--accent)',
          }}>
            {loading
              ? <><div style={{ width: 12, height: 12, border: '2px solid rgba(93,162,255,0.2)', borderTopColor: 'var(--accent)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }}/> Running…</>
              : <>↺ Refresh</>}
          </button>
        </div>
      </div>

      {/* Error banner (one failed endpoint — not the whole screen) */}
      {error && <ErrorBanner message={error} onRetry={reload}/>}

      {/* Score bar */}
      {!error && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px',
          borderRadius: 14, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
          marginBottom: 16, flexWrap: 'wrap',
        }}>
          {loading
            ? <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Running checks…</div>
            : <>
                {[
                  { label: 'Passing',  count: passCount, color: '#46d9a4' },
                  { label: 'Warnings', count: warnCount, color: '#ffbd66' },
                  { label: 'Failing',  count: failCount, color: '#ff6b7d' },
                ].map((s, i) => (
                  <React.Fragment key={s.label}>
                    {i > 0 && <span style={{ color: 'rgba(255,255,255,0.15)' }}>·</span>}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                      <span style={{ width: 7, height: 7, borderRadius: '50%', background: s.color }}/>
                      <span style={{ fontSize: 13, fontWeight: 700, color: s.color }}>{s.count}</span>
                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{s.label}</span>
                    </div>
                  </React.Fragment>
                ))}
                {runAt && <span style={{ marginLeft: 'auto', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>Last run: {runAt}</span>}
              </>}
        </div>
      )}

      {/* Checks */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 22 }}>
        {loading
          ? [1,2,3,4].map(i => <Skeleton key={i} h={64}/>)
          : checks.map(check => (
              <CheckRow
                key={check.id}
                check={check}
                expanded={expanded === check.id}
                onToggle={() => setExpanded(expanded === check.id ? null : check.id)}
                onSetup={check.status !== 'pass' && /github/i.test(check.label) && onNavigate ? () => onNavigate('github') : undefined}
              />
            ))}
        {!loading && !error && checks.length === 0 && (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: 13, padding: 32 }}>No checks available.</div>
        )}
      </div>

      {/* Summary */}
      {report && (
        <div style={{
          padding: '14px 18px', borderRadius: 14,
          background: report.ready ? 'rgba(70,217,164,0.06)' : 'rgba(255,107,125,0.06)',
          border: `1px solid ${report.ready ? 'rgba(70,217,164,0.18)' : 'rgba(255,107,125,0.18)'}`,
          fontSize: 13, color: report.ready ? '#46d9a4' : '#ff6b7d',
        }}>
          {report.ready ? '✓ ' : '✕ '}{report.summary}
        </div>
      )}
    </div>
  );
}

export { DoctorScreen };
