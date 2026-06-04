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
function CheckRow({ check, expanded, onToggle, onNavigate, onFix }) {
  const st = statusStyle(check.status);
  const action = check.action;  // from backend: { label, hint, href }
  const hasExpandedContent = !!(check.explanation || action || check.detail);
  const [fixing, setFixing] = React.useState(false);
  const [fixError, setFixError] = React.useState(null);

  const handleFix = async (e) => {
    e.stopPropagation();
    if (!onFix || fixing) return;
    setFixing(true);
    setFixError(null);
    try {
      await onFix(check.id);
    } catch (err) {
      setFixError(err.message || 'Fix failed');
    } finally {
      setFixing(false);
    }
  };

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
            {check.status !== 'pass' && action && (
              <span style={{
                fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.10em', textTransform: 'uppercase',
                padding: '2px 7px', borderRadius: 999, color: st.color,
                background: `${st.color}15`, border: `1px solid ${st.color}30`,
              }}>needs attention</span>
            )}
            {check.status !== 'pass' && check.fixable && (
              <span style={{
                fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.10em', textTransform: 'uppercase',
                padding: '2px 7px', borderRadius: 999, color: st.color,
                background: `${st.color}15`, border: `1px solid ${st.color}30`,
              }}>fixable</span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)', lineHeight: 1.5 }}>{check.detail}</div>
        </div>

        <span style={{
          fontSize: 14, color: 'var(--text-muted)',
          transform: expanded ? 'rotate(90deg)' : 'none',
          display: 'inline-block', transition: 'transform 0.2s',
          opacity: hasExpandedContent ? 1 : 0.3,
        }}>›</span>
      </button>

      {expanded && (
        <div style={{ padding: '0 16px 14px 56px' }}>
          {check.explanation && (
            <div style={{ padding: '12px 14px', borderRadius: 12, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 6 }}>
                Plain-language explanation
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.65 }}>{check.explanation}</div>
            </div>
          )}
          {!check.explanation && check.detail && check.status !== 'pass' && (
            <div style={{ padding: '12px 14px', borderRadius: 12, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
              <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 6 }}>
                Details
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.65 }}>{check.detail}</div>
            </div>
          )}
          {(action || (check.status !== 'pass' && /github/i.test(check.label))) && (
            <div style={{ marginTop: 8, display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {((action && action.href) || (!action && /github/i.test(check.label))) && onNavigate && (
                <button onClick={(e) => { e.stopPropagation(); onNavigate(action?.href || 'github'); }} style={{
                  padding: '8px 16px', borderRadius: 10, fontSize: 12, fontWeight: 700,
                  background: 'rgba(93,162,255,0.15)', border: '1px solid rgba(93,162,255,0.30)',
                  color: 'var(--accent)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6,
                }}>
                  {action?.label || 'Setup GitHub'} →
                </button>
              )}
              {action && !action.href && action.hint && (
                <div style={{
                  padding: '10px 14px', borderRadius: 10, fontSize: 12, fontWeight: 600,
                  background: `${st.color}12`, border: `1px solid ${st.color}25`,
                  color: st.color, lineHeight: 1.6, flex: 1,
                }}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.10em', textTransform: 'uppercase', marginRight: 6, opacity: 0.7 }}>{action.label || 'Fix'}:</span>
                  {action.hint}
                </div>
              )}
            </div>
          )}
          {fixError && (
            <div style={{ marginTop: 8, padding: '8px 12px', borderRadius: 10, background: 'rgba(255,107,125,0.10)', border: '1px solid rgba(255,107,125,0.25)', fontSize: 12, color: '#ff6b7d' }}>
              Fix failed: {fixError}
            </div>
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
  // Authenticated diagnostics — includes the user-specific GitHub / workspace /
  // company-graph checks that drive the GitHub setup CTA on this screen. The
  // no-auth `/api/doctor/public` endpoint intentionally omits those, so using it
  // here would make the setup path unreachable. This screen is already gated
  // behind auth, so there is no 401 surprise.
  const [data, states, reload] = useSafeData(API, { report: '/api/doctor/diagnostics' }, { refreshMs: 60_000 });
  const [expanded, setExpanded] = React.useState(null);
  const [filter, setFilter]     = React.useState('all');  // 'all' | 'pass' | 'warn' | 'fail'

  const report  = data.report;
  const loading = states.report?.loading;
  const error   = states.report?.error;

  const checks    = report?.checks  || [];
  const passCount = checks.filter(c => c.status === 'pass').length;
  const warnCount = checks.filter(c => c.status === 'warn').length;
  const failCount = checks.filter(c => c.status === 'fail').length;

  const runAt = report?.run_at ? new Date(report.run_at).toLocaleTimeString() : null;

  // Navigation wrapper: handles both screen IDs and API paths from backend action.href.
  // Valid screen IDs in the app (must match V5App.jsx)
  const VALID_SCREENS = ['dashboard','tasks','agents','skills','intelligence','providers','github','settings','doctor'];
  // Map API path prefixes to their corresponding screen IDs
  const PATH_TO_SCREEN = { runtimes: 'agents', providers: 'providers', tasks: 'tasks' };

  function handleActionNav(href) {
    if (!href || !onNavigate) return;
    if (href.startsWith('/')) {
      const parts = href.split('/').filter(Boolean);
      const prefix = parts[0];
      const screenId = PATH_TO_SCREEN[prefix] || prefix;
      if (VALID_SCREENS.includes(screenId)) {
        onNavigate(screenId);
      }
      return;
    }
    // Direct screen ID — navigate within the SPA
    if (VALID_SCREENS.includes(href)) {
      onNavigate(href);
    }
  }

  // Fix a single check (calls POST /api/doctor/fix/{checkId})
  const handleFixOne = async (checkId) => {
    await API.post(`/api/doctor/fix/${checkId}`);
    reload();
  };

  // Fix all failing/warning checks (calls POST /api/doctor/fix-all)
  const handleFixAll = async () => {
    await API.post('/api/doctor/fix-all');
    reload();
  };

  const failingChecks = checks.filter(c => c.status !== 'pass');

  const DOT_CONFIG = [
    { label: 'Passing',  count: passCount, color: '#46d9a4', filter: 'pass' },
    { label: 'Warnings', count: warnCount, color: '#ffbd66', filter: 'warn' },
    { label: 'Failing',  count: failCount, color: '#ff6b7d', filter: 'fail' },
  ];

  const displayedChecks = checks.filter(c =>
    filter === 'all' ? true : c.status === filter
  );

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
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {failingChecks.length > 0 && (
              <button onClick={handleFixAll} style={{
                display: 'inline-flex', alignItems: 'center', gap: 7,
                padding: '10px 18px', borderRadius: 999, fontSize: 13, fontWeight: 800, cursor: 'pointer',
                background: 'rgba(70,217,164,0.15)', border: '1px solid rgba(70,217,164,0.30)',
                color: '#46d9a4',
              }}>
                ⚡ Fix all ({failingChecks.length})
              </button>
            )}
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
      </div>

      {/* Error banner (one failed endpoint — not the whole screen) */}
      {error && <ErrorBanner message={error} onRetry={reload}/>}        {/* Score bar */}
      {!error && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px',
          borderRadius: 14, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
          marginBottom: 16, flexWrap: 'wrap',
        }}>
          {loading
            ? <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Running checks…</div>
            : <>
                {DOT_CONFIG.map((s, i) => (
                  <React.Fragment key={s.label}>
                    {i > 0 && <span style={{ color: 'rgba(255,255,255,0.15)' }}>·</span>}
                    <button
                      onClick={() => setFilter(prev => prev === s.filter ? 'all' : s.filter)}
                      title={`Filter to ${s.label.toLowerCase()} checks`}
                      style={{
                        display: 'flex', alignItems: 'center', gap: 5,
                        background: filter === s.filter ? `${s.color}18` : 'transparent',
                        border: `1px solid ${filter === s.filter ? `${s.color}40` : 'transparent'}`,
                        borderRadius: 8, padding: '4px 8px', cursor: 'pointer',
                        transition: 'all 0.15s ease',
                      }}
                    >
                      <span style={{ width: 7, height: 7, borderRadius: '50%', background: s.color }}/>
                      <span style={{ fontSize: 13, fontWeight: 700, color: s.color }}>{s.count}</span>
                      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{s.label}</span>
                    </button>
                  </React.Fragment>
                ))}
                {filter !== 'all' && (
                  <button onClick={() => setFilter('all')} style={{
                    fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em',
                    padding: '2px 8px', borderRadius: 999, background: 'rgba(255,255,255,0.06)',
                    border: '1px solid rgba(255,255,255,0.10)', color: 'var(--text-muted)', cursor: 'pointer',
                  }}>Clear filter</button>
                )}
                {runAt && <span style={{ marginLeft: 'auto', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>Last run: {runAt}</span>}
              </>}
        </div>
      )}

      {/* Checks */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 22 }}>
        {loading
          ? [1,2,3,4].map(i => <Skeleton key={i} h={64}/>)
          : displayedChecks.map(check => (
              <CheckRow
                key={check.id}
                check={check}
                expanded={expanded === check.id}
                onToggle={() => setExpanded(expanded === check.id ? null : check.id)}
                onNavigate={handleActionNav}
                onFix={check.fixable ? handleFixOne : null}
              />
            ))}
        {!loading && !error && displayedChecks.length === 0 && filter !== 'all' && (
          <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: 13, padding: 32 }}>
            No {filter} checks.
          </div>
        )}
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
