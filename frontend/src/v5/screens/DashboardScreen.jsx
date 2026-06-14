/* eslint-disable jsx-a11y/anchor-is-valid -- nav links wired later */
import React from 'react';
import { useSafeData } from '../hooks/useSafeData';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { Donut, Sparkline } from '../components/Charts';

// dashboard.jsx — Resilient Dashboard wired to the real backend
// Each widget fetches independently via useSafeData (Promise.allSettled) so a
// single failed endpoint never blanks the whole screen.

const STATUS_ALIASES = {
  in_progress: 'in_progress', running: 'in_progress', active: 'in_progress',
  todo: 'todo', pending: 'todo', queued: 'todo', open: 'todo',
  in_review: 'in_review', review: 'in_review', awaiting_review: 'in_review',
  blocked: 'blocked', stuck: 'blocked',
  done: 'done', completed: 'done', closed: 'done', resolved: 'done',
  failed: 'failed', error: 'failed', cancelled: 'failed', canceled: 'failed',
};

const normalizeStatus = (s) => STATUS_ALIASES[(s || '').toLowerCase()] || 'todo';

const STATUS_COLORS = {
  done: '#46d9a4', in_progress: '#5da2ff', todo: '#6e7786',
  in_review: '#ffbd66', blocked: '#ff6b7d', failed: '#ff6b7d',
};

function relTime(iso) {
  if (!iso) return '';
  const t = typeof iso === 'number' ? iso : Date.parse(iso);
  if (!t || Number.isNaN(t)) return '';
  const s = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function fmtTokens(n) {
  if (!n) return '0';
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}k`;
  return String(n);
}

// Widget wrapper with per-widget loading/error states
function Widget({ title, action, actionLabel, loading, error, errorSeverity = 'warning', onRetry, children, span = 1 }) {
  return (
    <div style={{
      borderRadius: 18, border: '1px solid var(--border)',
      background: 'rgba(10,12,15,0.80)',
      overflow: 'hidden', gridColumn: `span ${span}`,
    }}>
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 18px 0',
      }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>{title}</span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {onRetry && error && (
            <button onClick={onRetry} style={{
              fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.15em', textTransform: 'uppercase',
              color: 'var(--accent)', background: 'rgba(93,162,255,0.10)', border: '1px solid rgba(93,162,255,0.20)',
              borderRadius: 6, cursor: 'pointer', padding: '2px 8px',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(93,162,255,0.18)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'rgba(93,162,255,0.10)'; }}>
              Retry
            </button>
          )}
          {action && (
            <button onClick={action} style={{
              fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.15em', textTransform: 'uppercase',
              color: 'var(--text-muted)', background: 'none', border: 'none', cursor: 'pointer',
            }}
            onMouseEnter={e => e.currentTarget.style.color = 'var(--accent)'}
            onMouseLeave={e => e.currentTarget.style.color = 'var(--text-muted)'}>
              {actionLabel || 'View all →'}
            </button>
          )}
        </div>
      </div>
      <div style={{ padding: '12px 18px 16px' }}>
        {error && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10,
            padding: '7px 10px', borderRadius: 8,
            background: errorSeverity === 'warning' ? 'rgba(255,189,102,0.08)' : 'rgba(255,107,125,0.08)',
            border: `1px solid ${errorSeverity === 'warning' ? 'rgba(255,189,102,0.20)' : 'rgba(255,107,125,0.20)'}`,
            fontSize: 11, color: errorSeverity === 'warning' ? '#ffbd66' : '#ff6b7d',
          }}>
            <span>⚠</span><span>{error}</span>
          </div>
        )}
        {loading ? <SkeletonBlock/> : children}
      </div>
    </div>
  );
}

function SkeletonBlock() {
  const shimmer = {
    background: 'linear-gradient(90deg, rgba(255,255,255,0.04) 25%, rgba(255,255,255,0.08) 50%, rgba(255,255,255,0.04) 75%)',
    backgroundSize: '200% 100%',
    animation: 'shimmer 1.6s infinite',
    borderRadius: 8,
  };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ height: 16, width: '65%', ...shimmer }}/>
      <div style={{ height: 12, width: '85%', ...shimmer }}/>
      <div style={{ height: 12, width: '50%', ...shimmer }}/>
    </div>
  );
}

function StatusDot({ ok, pulse }) {
  return (
    <span style={{
      display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
      background: ok ? '#46d9a4' : ok === false ? '#ff6b7d' : '#ffbd66',
      flexShrink: 0,
      animation: pulse && ok ? 'pulse 2s ease-in-out infinite' : 'none',
    }}/>
  );
}

function Pill({ label, color = 'var(--text-muted)', bg = 'rgba(255,255,255,0.06)', border = 'rgba(255,255,255,0.10)' }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      padding: '2px 8px', borderRadius: 999, fontSize: 9,
      fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', textTransform: 'uppercase',
      color, background: bg, border: `1px solid ${border}`, whiteSpace: 'nowrap',
    }}>{label}</span>
  );
}

function ProviderHealthWidget({ data, loading, error, onRetry }) {
  return (
    <Widget title="Provider & Runtime" loading={loading} error={error} errorSeverity="warning" onRetry={onRetry}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* Provider */}
        <div style={{ padding: '12px 14px', borderRadius: 12, background: 'rgba(93,162,255,0.05)', border: '1px solid rgba(93,162,255,0.12)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <StatusDot ok={true} pulse/>
              <span style={{ fontSize: 13, fontWeight: 700, color: '#fff' }}>{data.provider.name}</span>
              <Pill label="Priority 0" color="#7c9dff" bg="rgba(124,157,255,0.10)" border="rgba(124,157,255,0.20)"/>
            </div>
            {data.provider.latency != null && <span style={{ fontSize: 11, color: '#46d9a4', fontFamily: 'var(--font-mono)' }}>{data.provider.latency}ms</span>}
          </div>
          <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{data.provider.model || '—'}</div>
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            <Pill label="Queue 0" color="var(--text-muted)"/>
            <Pill label="Healthy" color="#46d9a4" bg="rgba(70,217,164,0.08)" border="rgba(70,217,164,0.18)"/>
          </div>
        </div>
        {/* Runtime */}
        <div style={{ padding: '10px 14px', borderRadius: 12, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <StatusDot ok={true} pulse/>
              <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>{data.runtime.name}</span>
            </div>
            <Pill label={`${data.runtime.jobs} jobs`} color="var(--text-tertiary)"/>
          </div>
          {data.runtime.uptime && <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>Up {data.runtime.uptime}</div>}
        </div>
      </div>
    </Widget>
  );
}

function RecentJobsWidget({ jobs, loading, error, onRetry }) {
  const statusConfig = {
    completed: { color: '#46d9a4', label: 'Done', bg: 'rgba(70,217,164,0.08)' },
    running:   { color: '#5da2ff', label: 'Running', bg: 'rgba(93,162,255,0.08)' },
    queued:    { color: 'var(--text-muted)', label: 'Queued', bg: 'rgba(255,255,255,0.04)' },
    failed:    { color: '#ff6b7d', label: 'Failed', bg: 'rgba(255,107,125,0.08)' },
  };
  return (
    <Widget title="Recent Activity" loading={loading} error={error} onRetry={onRetry}>
      {(!jobs || jobs.length === 0) && !loading && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>No activity yet.</div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {(jobs || []).map(job => {
          const sc = statusConfig[job.status] || statusConfig.queued;
          return (
            <div key={job.id} style={{
              display: 'flex', alignItems: 'flex-start', gap: 10,
              padding: '10px 12px', borderRadius: 12,
              background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.07)',
              cursor: 'pointer', transition: 'background 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.045)'}
            onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.025)'}>
              <div style={{ marginTop: 2 }}><StatusDot ok={job.status === 'completed' ? true : job.status === 'failed' ? false : null} pulse={job.status === 'running'}/></div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 160 }}>{job.title}</span>
                  {job.pr && <Pill label={job.pr} color="var(--accent)" bg="rgba(93,162,255,0.08)" border="rgba(93,162,255,0.20)"/>}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 3 }}>
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{job.agent}</span>
                  <span style={{ color: 'rgba(255,255,255,0.15)' }}>·</span>
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{job.ago}</span>
                </div>
              </div>
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.10em', textTransform: 'uppercase', color: sc.color, padding: '2px 8px', borderRadius: 6, background: sc.bg, flexShrink: 0 }}>{sc.label}</span>
            </div>
          );
        })}
      </div>
    </Widget>
  );
}

function TasksWidget({ tasks, loading, error, onRetry, title = 'Open Tasks' }) {
  const priorityColor = { urgent: '#ff6b7d', high: '#ffbd66', medium: 'var(--text-muted)' };
  const statusColor = { in_progress: '#5da2ff', todo: 'var(--text-muted)', in_review: '#ffbd66', blocked: '#ff6b7d' };
  return (
    <Widget title={title} loading={loading} error={error} onRetry={onRetry}>
      {(!tasks || tasks.length === 0) && !loading && !error && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', lineHeight: 1.6 }}>
          No tasks. Use the Tasks screen to manage background jobs.
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        {(tasks || []).map(t => (
          <div key={t.id} style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px',
            borderRadius: 11, background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.07)',
            cursor: 'pointer', transition: 'background 0.15s',
          }}
          onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.045)'}
          onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.025)'}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: statusColor[t.status] || 'var(--text-muted)', flexShrink: 0 }}/>
            <span style={{ flex: 1, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.title}</span>
            <Pill label={t.priority} color={priorityColor[t.priority]}/>
          </div>
        ))}
      </div>
    </Widget>
  );
}

function CostWidget({ data, loading, error, onRetry }) {
  const hasRatio = data.localRatio != null;
  const barW = `${Math.round((data.localRatio || 0) * 100)}%`;
  const trend = data.trend || [];
  const hasTrend = trend.length >= 2;
  return (
    <Widget title="Cost & Usage" loading={loading} error={error} onRetry={onRetry}>
      {/* Request-volume trend sparkline — real time-series from observability metrics */}
      {hasTrend && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Request volume</span>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>{trend.length} buckets</span>
          </div>
          <Sparkline values={trend} height={48} />
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: hasRatio ? 12 : 0 }}>
        {[
          { label: 'Cost saved (24h)', value: data.saved, color: '#46d9a4' },
          { label: 'Requests (24h)', value: (data.requests || 0).toLocaleString(), color: 'var(--accent)' },
          { label: 'Tokens (24h)', value: data.tokens, color: '#c4b5fd' },
          { label: 'Avg tokens/req', value: data.avgTokens, color: 'var(--text-primary)' },
        ].map(m => (
          <div key={m.label} style={{ padding: '10px 12px', borderRadius: 10, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)' }}>
            <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 4 }}>{m.label}</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: m.color, letterSpacing: '-0.03em' }}>{m.value}</div>
          </div>
        ))}
      </div>
      {/* Local ratio bar — only when the backend supplies the split */}
      {hasRatio && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
            <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Local / free ratio</span>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: '#46d9a4', fontWeight: 700 }}>{barW}</span>
          </div>
          <div style={{ height: 6, borderRadius: 999, background: 'rgba(255,255,255,0.08)' }}>
            <div style={{ height: '100%', borderRadius: 999, width: barW, background: 'linear-gradient(90deg, #46d9a4, #5da2ff)', transition: 'width 0.8s ease' }}/>
          </div>
        </div>
      )}
    </Widget>
  );
}

function MonitoringWidget({ signals, loading, error, onRetry }) {
  return (
    <Widget title="Monitoring" loading={loading} error={error} onRetry={onRetry}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {signals.map(s => (
          <div key={s.label} style={{
            padding: '10px 12px', borderRadius: 11,
            background: s.ok ? 'rgba(70,217,164,0.05)' : 'rgba(255,189,102,0.06)',
            border: `1px solid ${s.ok ? 'rgba(70,217,164,0.14)' : 'rgba(255,189,102,0.18)'}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 4 }}>
              <StatusDot ok={s.ok ? true : false}/>
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.10em', textTransform: 'uppercase' }}>{s.label}</span>
            </div>
            <div style={{ fontSize: 15, fontWeight: 800, color: s.ok ? 'var(--text-primary)' : '#ffbd66', letterSpacing: '-0.02em' }}>{s.value}</div>
          </div>
        ))}
      </div>
    </Widget>
  );
}

function TaskDistributionWidget({ breakdown, total, loading, error, onRetry }) {
  return (
    <Widget title="Task Distribution" loading={loading} error={error} onRetry={onRetry}>
      {total === 0 && !loading && !error ? (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', lineHeight: 1.6 }}>
          No tasks tracked yet — create one from the Tasks screen to see the breakdown.
        </div>
      ) : (
        <Donut data={breakdown} centerLabel="tasks" />
      )}
    </Widget>
  );
}

function SystemHealthWidget({ health, loading, error, onRetry }) {
  const services = [
    { label: 'MongoDB',  ok: health.mongo  ?? null },
    { label: 'Ollama',   ok: health.ollama_relevant ? (health.ollama ?? null) : null, skip: !health.ollama_relevant },
    { label: 'Langfuse', ok: health.langfuse ?? null },
  ].filter(s => !s.skip);
  return (
    <Widget title="System Health" loading={loading} error={error} errorSeverity="warning" onRetry={onRetry}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {services.map(s => (
          <div key={s.label} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 12px', borderRadius: 999,
            background: s.ok === true ? 'rgba(70,217,164,0.07)' : s.ok === false ? 'rgba(255,189,102,0.07)' : 'rgba(255,255,255,0.04)',
            border: `1px solid ${s.ok === true ? 'rgba(70,217,164,0.18)' : s.ok === false ? 'rgba(255,189,102,0.22)' : 'rgba(255,255,255,0.10)'}`,
          }}>
            <StatusDot ok={s.ok}/>
            <span style={{ fontSize: 12, color: s.ok === true ? 'var(--text-secondary)' : s.ok === false ? '#ffbd66' : 'var(--text-muted)' }}>{s.label}</span>
          </div>
        ))}
      </div>
      {health.langfuse === false && (
        <div style={{ marginTop: 10, padding: '8px 12px', borderRadius: 10, background: 'rgba(255,189,102,0.05)', border: '1px solid rgba(255,189,102,0.12)' }}>
          <div style={{ fontSize: 11, color: '#ffbd66', lineHeight: 1.5 }}>
            ⚠ Langfuse not configured — observability traces unavailable. Set <code>LANGFUSE_SECRET_KEY</code> / <code>LANGFUSE_PUBLIC_KEY</code> on the backend.
          </div>
        </div>
      )}
    </Widget>
  );
}


// ─── AgentActivityWidget ─────────────────────────────────────────────────────
function AgentActivityWidget({ donutData, sparklineData, totalTasks, activeAgents, loading, error, onRetry }) {
  return (
    <Widget title="Agent Activity" loading={loading} error={error} errorSeverity="warning" onRetry={onRetry}>
      {!loading && !error && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{totalTasks} total tasks</span>
            {activeAgents > 0 && (
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', padding: '2px 8px', borderRadius: 999, color: '#46d9a4', background: 'rgba(70,217,164,0.10)', border: '1px solid rgba(70,217,164,0.20)' }}>
                {activeAgents} agent{activeAgents === 1 ? '' : 's'} running
              </span>
            )}
          </div>
          <Donut data={donutData} size={100} thickness={12} centerLabel="tasks" />
          <div style={{ marginTop: 14 }}>
            <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.14em', textTransform: 'uppercase', marginBottom: 6 }}>7-day activity</div>
            <Sparkline values={sparklineData} height={44} />
          </div>
        </div>
      )}
    </Widget>
  );
}

function DashboardScreen() {
  const [data, states, fetchAll] = useSafeData(null, {
    health:    '/api/health',
    stats:     '/api/stats',
    activity:  '/api/activity?limit=8',
    metrics:   '/api/observability/metrics',
    providers: '/api/providers',
    tasks:     '/api/tasks/',
    agents:    '/api/agents/',
  }, { refreshMs: 30000 });

  // Map /api/tasks/ to the Open Tasks widget (exclude finished/failed).
  // Status is normalized so backend variants ("running" / "in_progress",
  // "pending" / "todo") collapse to the same bucket — keeps the colors stable
  // regardless of which vocabulary the dispatcher uses today.
  const openTasks = React.useMemo(() => {
    const all = data.tasks?.tasks || [];
    return all
      .map(t => ({ id: t.task_id || t.id, title: t.title, status: normalizeStatus(t.status), priority: t.priority }))
      .filter(t => t.status !== 'done' && t.status !== 'failed')
      .slice(0, 6);
  }, [data.tasks]);

  // Build task status distribution for the AgentActivityWidget donut.
  const taskDonutData = React.useMemo(() => {
    const all = data.tasks?.tasks || [];
    const counts = { done: 0, in_progress: 0, todo: 0, in_review: 0, blocked: 0, failed: 0 };
    all.forEach(t => {
      const s = normalizeStatus(t.status);
      counts[s] = (counts[s] || 0) + 1;
    });
    return Object.entries(counts)
      .filter(([, v]) => v > 0)
      .map(([k, v]) => ({ label: k.replace(/_/g, ' '), value: v, color: STATUS_COLORS[k] || 'var(--accent)' }));
  }, [data.tasks]);

  // Build last-7-day agent activity sparkline from /api/activity
  const agentActivitySparkline = React.useMemo(() => {
    const logs = data.activity?.logs || data.activity?.events || [];
    // Bucket activity entries into 7 day slots (most recent last)
    const buckets = Array(7).fill(0);
    const now = Date.now();
    logs.forEach(log => {
      const ts = log.created_at || log.timestamp;
      if (!ts) return;
      const age = now - Date.parse(ts);
      const dayIdx = Math.floor(age / 86400000);
      if (dayIdx >= 0 && dayIdx < 7) buckets[6 - dayIdx]++;
    });
    return buckets;
  }, [data.activity]);

  // Map /api/health + /api/providers into ProviderHealthWidget shape
  const providerData = React.useMemo(() => {
    const h = data.health || {};
    const stats = data.stats || {};
    const raw = data.providers;
    const provList = Array.isArray(raw?.providers) ? raw.providers : (Array.isArray(raw) ? raw : []);
    const active = provList.find(p => p.is_default) || provList[0] || null;
    return {
      provider: {
        name: active?.name || stats.llm_provider || h.provider || 'No provider',
        model: active?.default_model || '—',
        status: h.status === 'ok' ? 'healthy' : 'degraded',
        latency: null,
        queue: 0,
      },
      runtime: {
        name: 'Agent Runtime',
        status: 'healthy',
        uptime: null,
        jobs: 0,
      },
      mongo: h.mongo ?? null,
      ollama: h.ollama ?? null,
      ollama_relevant: h.ollama_relevant ?? false,
      langfuse: stats.langfuse_configured ?? false,
    };
  }, [data.health, data.stats, data.providers]);

  // Map /api/activity to jobs list
  const activityJobs = React.useMemo(() => {
    const logs = data.activity?.logs || data.activity?.events || [];
    return logs.slice(0, 6).map((log, i) => ({
      id: log._id || String(i),
      title: log.message || log.event_type || 'System event',
      status: 'completed',
      phase: 'done',
      ago: relTime(log.created_at || log.timestamp),
      agent: log.event_type ? log.event_type.replace(/_/g, ' ') : 'System',
      pr: null,
    }));
  }, [data.activity]);

  // Active agents count
  const activeAgents = React.useMemo(() => {
    const agentList = data.agents?.agents || (Array.isArray(data.agents) ? data.agents : []);
    return agentList.filter(a => a.status === 'running' || a.status === 'active').length;
  }, [data.agents]);

  // Map /api/observability/metrics to CostWidget shape.
  // Backend exposes a 24h window only (total_requests/tokens/savings); there is
  // no monthly spend figure and no cloud/local split, so we don't fabricate them.
  const costData = React.useMemo(() => {
    const m = data.metrics || {};
    const s = m.summary_24h || m.summary || {};
    const saved = s.total_savings_usd || 0;
    const requests = s.total_requests || 0;
    const tokens = s.total_tokens || 0;
    // Real time-series for the request-volume sparkline (observability metrics
    // expose `time_series` / `buckets`; fall back gracefully if absent).
    const series = m.time_series || m.buckets || [];
    const trend = Array.isArray(series) ? series.map((b) => Number(b.requests) || 0) : [];
    return {
      saved: `$${saved.toFixed(2)}`,
      requests,
      tokens: fmtTokens(tokens),
      avgTokens: requests ? fmtTokens(Math.round(tokens / requests)) : '—',
      localRatio: null, // no cloud/local split in metrics yet — bar hidden
      trend,
    };
  }, [data.metrics]);

  // Task status breakdown for the distribution donut.
  const taskBreakdown = React.useMemo(() => {
    const all = data.tasks?.tasks || [];
    const buckets = {
      in_progress: { label: 'In progress', value: 0, color: '#5da2ff' },
      todo: { label: 'To do', value: 0, color: '#6e7786' },
      in_review: { label: 'In review', value: 0, color: '#ffbd66' },
      done: { label: 'Done', value: 0, color: '#46d9a4' },
      blocked: { label: 'Blocked', value: 0, color: '#ff6b7d' },
      failed: { label: 'Failed', value: 0, color: '#ff6b7d' },
    };
    all.forEach((t) => {
      const s = normalizeStatus(t.status);
      const b = buckets[s] || buckets.todo;
      b.value += 1;
    });
    const rows = Object.values(buckets).filter((b) => b.value > 0);
    return { rows, total: all.length };
  }, [data.tasks]);

  // Map /api/health + /api/stats to MonitoringWidget signals
  const monitoringSignals = React.useMemo(() => {
    const h = data.health || {};
    const s = data.stats || {};
    return [
      { label: 'Backend',  value: h.status === 'ok' ? 'Healthy' : h.status || 'Unknown', ok: h.status === 'ok' },
      { label: 'MongoDB',  value: h.mongo === true ? 'Connected' : h.mongo === false ? 'Down' : '—', ok: h.mongo ?? null },
      { label: 'Sessions', value: (s.chat_sessions ?? '—').toLocaleString(), ok: true },
      { label: 'Langfuse', value: s.langfuse_configured ? 'Configured' : 'Not set', ok: !!s.langfuse_configured },
    ];
  }, [data.health, data.stats]);

  const systemOk = data.health?.status === 'ok';
  const anyLoading = states.health?.loading || states.stats?.loading;
  const today = new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });

  return (
    <div style={{ padding: '20px 16px 32px', maxWidth: 1200, margin: '0 auto' }}>
      {/* Page header */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: '3px 10px', borderRadius: 999, fontSize: 10,
            fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', textTransform: 'uppercase',
            background: systemOk ? 'rgba(70,217,164,0.10)' : 'rgba(255,189,102,0.10)',
            border: `1px solid ${systemOk ? 'rgba(70,217,164,0.20)' : 'rgba(255,189,102,0.25)'}`,
            color: systemOk ? '#46d9a4' : '#ffbd66',
          }}>
            <span style={{ width: 5, height: 5, borderRadius: '50%', background: systemOk ? '#46d9a4' : '#ffbd66', animation: 'pulse 2s infinite' }}/>
            {anyLoading ? 'Loading…' : systemOk ? 'System healthy' : 'Degraded'}
          </span>
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{today}</span>
        </div>
        <h1 style={{ fontSize: 'clamp(22px,4vw,32px)', fontWeight: 800, color: '#fff', letterSpacing: '-0.04em', lineHeight: 1.1, marginBottom: 6 }}>Dashboard</h1>
        <p style={{ fontSize: 14, color: 'var(--text-tertiary)', maxWidth: 520, lineHeight: 1.6 }}>
          {data.stats
            ? `${data.stats.chat_sessions || 0} chat sessions · ${data.stats.wiki_pages || 0} wiki pages · ${data.stats.providers || 0} provider${(data.stats.providers || 0) === 1 ? '' : 's'} configured`
            : 'Loading platform stats…'}
        </p>
      </div>

      {/* Widget grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
        gap: 14,
      }}>
        <ErrorBoundary onRetry={fetchAll} resetKey={String(states.health?.error || states.providers?.error || '')}>
          <ProviderHealthWidget
            data={providerData}
            loading={states.health?.loading || states.providers?.loading}
            error={states.health?.error || states.providers?.error}
            onRetry={fetchAll}
          />
        </ErrorBoundary>
        <ErrorBoundary onRetry={fetchAll} resetKey={String(states.activity?.error || '')}>
          <RecentJobsWidget
            jobs={activityJobs}
            loading={states.activity?.loading}
            error={states.activity?.error}
            onRetry={fetchAll}
          />
        </ErrorBoundary>
        <ErrorBoundary onRetry={fetchAll} resetKey={String(states.tasks?.error || '')}>
          <TasksWidget
            tasks={openTasks}
            loading={states.tasks?.loading}
            error={states.tasks?.error}
            onRetry={fetchAll}
          />
        </ErrorBoundary>
        <ErrorBoundary onRetry={fetchAll} resetKey={String(states.tasks?.error || '')}>
          <TaskDistributionWidget
            breakdown={taskBreakdown.rows}
            total={taskBreakdown.total}
            loading={states.tasks?.loading}
            error={states.tasks?.error}
            onRetry={fetchAll}
          />
        </ErrorBoundary>
        <ErrorBoundary onRetry={fetchAll} resetKey={String(states.metrics?.error || '')}>
          <CostWidget
            data={costData}
            loading={states.metrics?.loading}
            error={states.metrics?.error}
            errorSeverity="warning"
            onRetry={fetchAll}
          />
        </ErrorBoundary>
        <ErrorBoundary onRetry={fetchAll} resetKey={String((states.health?.error || '') + (states.stats?.error || ''))}>
          <MonitoringWidget
            signals={monitoringSignals}
            loading={states.health?.loading || states.stats?.loading}
            error={states.health?.error || states.stats?.error}
            onRetry={fetchAll}
          />
        </ErrorBoundary>
        <ErrorBoundary onRetry={fetchAll} resetKey={String((states.health?.error || '') + (states.stats?.error || ''))}>
          <SystemHealthWidget
            health={providerData}
            loading={states.health?.loading || states.stats?.loading}
            error={states.health?.error || states.stats?.error}
            errorSeverity="warning"
            onRetry={fetchAll}
          />
        </ErrorBoundary>
        <ErrorBoundary onRetry={fetchAll} resetKey={String(states.tasks?.error || states.activity?.error || '')}>
          <AgentActivityWidget
            donutData={taskDonutData}
            sparklineData={agentActivitySparkline}
            totalTasks={(data.tasks?.tasks || []).length}
            activeAgents={activeAgents}
            loading={states.tasks?.loading || states.activity?.loading}
            error={states.tasks?.error || states.activity?.error}
            onRetry={fetchAll}
          />
        </ErrorBoundary>
      </div>
    </div>
  );
}

export { DashboardScreen };
export default DashboardScreen;
