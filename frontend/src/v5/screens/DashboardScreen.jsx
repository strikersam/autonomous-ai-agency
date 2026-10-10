/* eslint-disable jsx-a11y/anchor-is-valid -- nav links wired later */
import React from 'react';
import Glyph from '../components/ui/Glyph';
import { useSafeData } from '../hooks/useSafeData';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { Sparkline, Donut, BarChart } from '../components/Charts';
import { Icon } from '../AppShell';

// dashboard.jsx — Resilient Dashboard wired to the real backend
// Each widget fetches independently via useSafeData (Promise.allSettled) so a
// single failed endpoint never blanks the whole screen.

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
    <section className="dash-widget" style={{ gridColumn: `span ${span}` }} aria-label={title}>
      <div className="dash-widget-head">
        <h3 className="dash-widget-title">{title}</h3>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {onRetry && error && (
            <button type="button" className="dash-link" onClick={onRetry}>Retry</button>
          )}
          {action && (
            <button type="button" className="dash-link" onClick={action}>{actionLabel || 'View all'}</button>
          )}
        </div>
      </div>
      <div className="dash-widget-body">
        {error && (
          <div role="alert" className={`dash-note ${errorSeverity === 'warning' ? 'is-warn' : 'is-bad'}`}>
            <Icon name="AlertCircle" size={16} style={{ flexShrink: 0, marginTop: 2 }}/><span>{error}</span>
          </div>
        )}
        {loading ? <SkeletonBlock/> : children}
      </div>
    </section>
  );
}

function SkeletonBlock() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }} aria-hidden="true">
      <div className="skeleton" style={{ height: 16, width: '65%' }}/>
      <div className="skeleton" style={{ height: 12, width: '85%' }}/>
      <div className="skeleton" style={{ height: 12, width: '50%' }}/>
    </div>
  );
}

function StatusDot({ ok, pulse }) {
  return (
    <span style={{
      display: 'inline-block', width: 7, height: 7, borderRadius: '50%',
      background: ok ? 'var(--success)' : ok === false ? 'var(--danger)' : 'var(--warning)',
      flexShrink: 0,
      animation: pulse && ok ? 'pulse 2s ease-in-out infinite' : 'none',
    }}/>
  );
}

function Pill({ label, color = 'var(--text-muted)', bg = 'color-mix(in oklab, var(--ink) 6%, transparent)', border = 'color-mix(in oklab, var(--ink) 10%, transparent)' }) {
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
      padding: '2px 7px', borderRadius: 6, fontSize:13, fontWeight: 500,
      fontVariantNumeric:'tabular-nums', textTransform: 'capitalize',
      color, background: bg, border: `1px solid ${border}`, whiteSpace: 'nowrap',
    }}>{label}</span>
  );
}

function ProviderHealthWidget({ data, loading, error, onRetry }) {
  return (
    <Widget title="AI provider and runtime" loading={loading} error={error} errorSeverity="warning" onRetry={onRetry}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* Provider */}
        <div style={{ padding: '12px 14px', borderRadius: 12, background: 'color-mix(in oklab, var(--accent) 5%, transparent)', border: '1px solid color-mix(in oklab, var(--accent) 12%, transparent)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <StatusDot ok={true} pulse/>
              <span style={{ fontSize:14, fontWeight: 700, color:'var(--text-primary)' }}>{data.provider.name}</span>
              <Pill label="Priority 0" color="#7c9dff" bg="color-mix(in oklab, var(--accent) 10%, transparent)" border="color-mix(in oklab, var(--accent) 20%, transparent)"/>
            </div>
            {data.provider.latency != null && <span style={{ fontSize:13, color: 'var(--success)', fontVariantNumeric:'tabular-nums' }}>{data.provider.latency}ms</span>}
          </div>
          <div style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color: 'var(--text-muted)' }}>{data.provider.model || '—'}</div>
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            <Pill label="Queue 0" color="var(--text-muted)"/>
            <Pill label="Healthy" color="#46d9a4" bg="color-mix(in oklab, var(--success) 8%, transparent)" border="color-mix(in oklab, var(--success) 18%, transparent)"/>
          </div>
        </div>
        {/* Runtime */}
        <div style={{ padding: '10px 14px', borderRadius: 12, background: 'color-mix(in oklab, var(--ink) 3%, transparent)', border: '1px solid color-mix(in oklab, var(--ink) 8%, transparent)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <StatusDot ok={true} pulse/>
              <span style={{ fontSize:13, fontWeight: 600, color: 'var(--text-secondary)' }}>{data.runtime.name}</span>
            </div>
            <Pill label={`${data.runtime.jobs} jobs`} color="var(--text-tertiary)"/>
          </div>
          {data.runtime.uptime && <div style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color: 'var(--text-muted)' }}>Up {data.runtime.uptime}</div>}
        </div>
      </div>
    </Widget>
  );
}

function RecentJobsWidget({ jobs, loading, error, onRetry }) {
  const statusConfig = {
    completed: { color: 'var(--success)', label: 'Done', bg: 'color-mix(in oklab, var(--success) 8%, transparent)' },
    running:   { color: 'var(--accent)', label: 'Running', bg: 'color-mix(in oklab, var(--accent) 8%, transparent)' },
    queued:    { color: 'var(--text-muted)', label: 'Queued', bg: 'color-mix(in oklab, var(--ink) 4%, transparent)' },
    failed:    { color: 'var(--danger)', label: 'Failed', bg: 'color-mix(in oklab, var(--danger) 8%, transparent)' },
  };
  return (
    <Widget title="Recent activity" loading={loading} error={error} onRetry={onRetry}>
      {(!jobs || jobs.length === 0) && !loading && (
        <p style={{ color: 'var(--text-muted)' }}>Nothing yet. When your team starts working, each step shows up here.</p>
      )}
      <ul className="dash-mini">
        {(jobs || []).map(job => {
          const sc = statusConfig[job.status] || statusConfig.queued;
          return (
            <li key={job.id}>
              <StatusDot ok={job.status === 'completed' ? true : job.status === 'failed' ? false : null} pulse={job.status === 'running'}/>
              <span className="dash-mini-main">
                <span className="dash-mini-title">{job.title}</span>
                <span className="dash-mini-sub">{job.agent} · {job.ago}{job.pr ? ` · ${job.pr}` : ''}</span>
              </span>
              {job.status !== 'completed' && <span style={{ fontSize:14, color: sc.color, flexShrink: 0 }}>{sc.label}</span>}
            </li>
          );
        })}
      </ul>
    </Widget>
  );
}

function TasksWidget({ tasks, loading, error, onRetry, title = 'Open tasks' }) {
  const priorityColor = { urgent: 'var(--danger)', high: 'var(--warning)', medium: 'var(--text-muted)' };
  const statusColor = { in_progress: 'var(--accent)', todo: 'var(--text-muted)', in_review: 'var(--warning)', blocked: 'var(--danger)' };
  return (
    <Widget title={title} loading={loading} error={error} onRetry={onRetry}>
      {(!tasks || tasks.length === 0) && !loading && !error && (
        <p style={{ color: 'var(--text-muted)' }}>No open tasks. New work you or your agents create shows up here.</p>
      )}
      <ul className="dash-mini">
        {(tasks || []).map(t => (
          <li key={t.id}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: statusColor[t.status] || 'var(--text-muted)', flexShrink: 0 }} aria-hidden="true"/>
            <span className="dash-mini-main"><span className="dash-mini-title">{t.title}</span></span>
            {t.priority && <Pill label={t.priority} color={priorityColor[t.priority]}/>}
          </li>
        ))}
      </ul>
    </Widget>
  );
}

function CostWidget({ data, loading, error, onRetry }) {
  const hasRatio = data.localRatio != null;
  const barW = `${Math.round((data.localRatio || 0) * 100)}%`;
  const trend = data.trend || [];
  const hasTrend = trend.length >= 2;
  return (
    <Widget title="Cost and usage" loading={loading} error={error} onRetry={onRetry}>
      {/* Request-volume trend sparkline — real time-series from observability metrics */}
      {hasTrend && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 4 }}>
            <span style={{ fontSize:13, color: 'var(--text-muted)' }}>Request volume</span>
            <span style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color: 'var(--text-tertiary)' }}>{trend.length} buckets</span>
          </div>
          <Sparkline values={trend} height={48} />
        </div>
      )}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: hasRatio ? 12 : 0 }}>
        {[
          { label: 'Cost saved (24h)', value: data.saved, color: 'var(--success)' },
          { label: 'Requests (24h)', value: (data.requests || 0).toLocaleString(), color: 'var(--accent)' },
          { label: 'Tokens (24h)', value: data.tokens, color: 'var(--violet)' },
          { label: 'Avg tokens/req', value: data.avgTokens, color: 'var(--text-primary)' },
        ].map(m => (
          <div key={m.label} style={{ padding: '10px 12px', borderRadius: 10, background: 'color-mix(in oklab, var(--ink) 3%, transparent)', border: '1px solid color-mix(in oklab, var(--ink) 7%, transparent)' }}>
            <div style={{ fontSize:13, color: 'var(--text-muted)', marginBottom: 4 }}>{m.label}</div>
            <div style={{ fontSize: 18, fontWeight:700, color: m.color, letterSpacing: '-0.03em' }}>{m.value}</div>
          </div>
        ))}
      </div>
      {/* Local ratio bar — only when the backend supplies the split */}
      {hasRatio && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
            <span style={{ fontSize:13, color: 'var(--text-muted)' }}>Local / free ratio</span>
            <span style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color: 'var(--success)', fontWeight: 700 }}>{barW}</span>
          </div>
          <div style={{ height: 6, borderRadius: 999, background: 'color-mix(in oklab, var(--ink) 8%, transparent)' }}>
            <div style={{ height: '100%', borderRadius: 999, width: barW, background: 'linear-gradient(90deg, var(--success), var(--accent))', transition: 'width 0.8s ease' }}/>
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
            background: s.ok ? 'color-mix(in oklab, var(--success) 5%, transparent)' : 'color-mix(in oklab, var(--warning) 6%, transparent)',
            border: `1px solid ${s.ok ? 'color-mix(in oklab, var(--success) 14%, transparent)' : 'color-mix(in oklab, var(--warning) 18%, transparent)'}`,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 4 }}>
              <StatusDot ok={s.ok ? true : false}/>
              <span style={{ fontSize:13, color: 'var(--text-muted)' }}>{s.label}</span>
            </div>
            <div style={{ fontSize: 15, fontWeight:700, color: s.ok ? 'var(--text-primary)' : 'var(--warning)', letterSpacing: '-0.02em' }}>{s.value}</div>
          </div>
        ))}
      </div>
    </Widget>
  );
}

function TaskDistributionWidget({ breakdown, total, loading, error, onRetry }) {
  return (
    <Widget title="Tasks by status" loading={loading} error={error} onRetry={onRetry}>
      {total === 0 && !loading && !error ? (
        <div style={{ fontSize:13, color: 'var(--text-muted)', fontVariantNumeric:'tabular-nums', lineHeight: 1.6 }}>
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
    <Widget title="System health" loading={loading} error={error} errorSeverity="warning" onRetry={onRetry}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {services.map(s => (
          <div key={s.label} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 12px', borderRadius: 999,
            background: s.ok === true ? 'color-mix(in oklab, var(--success) 7%, transparent)' : s.ok === false ? 'color-mix(in oklab, var(--warning) 7%, transparent)' : 'color-mix(in oklab, var(--ink) 4%, transparent)',
            border: `1px solid ${s.ok === true ? 'color-mix(in oklab, var(--success) 18%, transparent)' : s.ok === false ? 'color-mix(in oklab, var(--warning) 22%, transparent)' : 'color-mix(in oklab, var(--ink) 10%, transparent)'}`,
          }}>
            <StatusDot ok={s.ok}/>
            <span style={{ fontSize:13, color: s.ok === true ? 'var(--text-secondary)' : s.ok === false ? 'var(--warning)' : 'var(--text-muted)' }}>{s.label}</span>
          </div>
        ))}
      </div>
      {health.langfuse === false && (
        <div style={{ marginTop: 10, padding: '8px 12px', borderRadius: 10, background: 'color-mix(in oklab, var(--warning) 5%, transparent)', border: '1px solid color-mix(in oklab, var(--warning) 12%, transparent)' }}>
          <div style={{ fontSize:13, color: 'var(--warning)', lineHeight: 1.5 }}>
            <Glyph g="⚠"/> Langfuse not configured — observability traces unavailable. Set <code>LANGFUSE_SECRET_KEY</code> / <code>LANGFUSE_PUBLIC_KEY</code> on the backend.
          </div>
        </div>
      )}
    </Widget>
  );
}

function RateLimiterWidget({ providers, loading, error, onRetry }) {
  const entries = Object.entries(providers || {});
  return (
    <Widget title="Rate-limit pacing" loading={loading} error={error} errorSeverity="warning" onRetry={onRetry}>
      {entries.length === 0 && !loading && !error && (
        <div style={{ fontSize:13, color: 'var(--text-muted)', fontVariantNumeric:'tabular-nums', lineHeight: 1.6 }}>
          No provider has reported rate-limit headers yet. Proactive pacing engages automatically the moment one does.
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {entries.map(([id, q]) => {
          const pct = q.limit_requests ? Math.round(((q.remaining_requests ?? q.limit_requests) / q.limit_requests) * 100) : null;
          const low = pct != null && pct <= 15;
          return (
            <div key={id} style={{ padding: '9px 12px', borderRadius: 11, background: 'color-mix(in oklab, var(--ink) 2.5%, transparent)', border: '1px solid color-mix(in oklab, var(--ink) 7%, transparent)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: pct != null ? 5 : 0 }}>
                <span style={{ fontSize:13, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'capitalize' }}>{id}</span>
                {pct != null
                  ? <Pill label={`${pct}% left`} color={low ? 'var(--danger)' : 'var(--success)'} bg={low ? 'color-mix(in oklab, var(--danger) 8%, transparent)' : 'color-mix(in oklab, var(--success) 8%, transparent)'} border={low ? 'color-mix(in oklab, var(--danger) 20%, transparent)' : 'color-mix(in oklab, var(--success) 18%, transparent)'} />
                  : <Pill label="tracking" />}
              </div>
              {pct != null && (
                <div style={{ height: 5, borderRadius: 999, background: 'color-mix(in oklab, var(--ink) 8%, transparent)' }}>
                  <div style={{ height: '100%', borderRadius: 999, width: `${pct}%`, background: low ? 'var(--danger)' : 'linear-gradient(90deg,var(--success),var(--accent))', transition: 'width 0.8s ease' }} />
                </div>
              )}
              <div style={{ display: 'flex', gap: 10, marginTop: 5, fontSize:13, fontVariantNumeric:'tabular-nums', color: 'var(--text-muted)' }}>
                {q.reset_requests_in_s != null && <span>reset in {q.reset_requests_in_s}s</span>}
                <span>updated {q.updated_s_ago}s ago</span>
              </div>
            </div>
          );
        })}
      </div>
    </Widget>
  );
}

function SelfHealWidget({ data, loading, error, onRetry }) {
  const stateColor = {
    detected: 'var(--warning)', fixing: 'var(--accent)', verifying: 'var(--violet)',
    resolved: 'var(--success)', regressed: 'var(--warning)', awaiting_human: 'var(--danger)',
  };
  const events = data.events || [];
  return (
    <Widget title="Self-healing" loading={loading} error={error} errorSeverity="warning" onRetry={onRetry}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2,1fr)', gap: 8, marginBottom: 12 }}>
        {[
          { label: 'Active', value: data.active_count ?? 0, color: 'var(--accent)' },
          { label: 'Resolved', value: data.resolved_count ?? 0, color: 'var(--success)' },
          { label: 'Awaiting human', value: data.awaiting_human_count ?? 0, color: 'var(--danger)' },
          { label: 'Fix tasks', value: data.log_monitor?.tasks_created ?? 0, color: 'var(--violet)' },
        ].map(m => (
          <div key={m.label} style={{ padding: '8px 10px', borderRadius: 10, background: 'color-mix(in oklab, var(--ink) 3%, transparent)', border: '1px solid color-mix(in oklab, var(--ink) 7%, transparent)' }}>
            <div style={{ fontSize: 16, fontWeight:700, color: m.color }}>{m.value}</div>
            <div style={{ fontSize:13, color: 'var(--text-muted)' }}>{m.label}</div>
          </div>
        ))}
      </div>
      {events.length === 0 && !loading && !error && (
        <div style={{ fontSize:13, color: 'var(--text-muted)', fontVariantNumeric:'tabular-nums', lineHeight: 1.6 }}>
          No errors captured yet — the log monitor is watching in real time.
        </div>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {events.slice(0, 5).map(e => (
          <div key={e.event_id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '7px 10px', borderRadius: 9, background: 'color-mix(in oklab, var(--ink) 2%, transparent)', border: '1px solid color-mix(in oklab, var(--ink) 6%, transparent)' }}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: stateColor[e.state] || 'var(--text-muted)', flexShrink: 0 }} />
            <span style={{ flex: 1, fontSize:13, color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{e.title}</span>
            <span style={{ fontSize:13, color: stateColor[e.state] || 'var(--text-muted)', flexShrink: 0 }}>{e.state}</span>
          </div>
        ))}
      </div>
    </Widget>
  );
}

function CostBreakdownWidget({ data, loading, error, onRetry }) {
  const tagColors = ['var(--accent)', 'var(--success)', 'var(--violet)', 'var(--warning)', 'var(--warning)', 'var(--danger)', 'var(--accent)'];
  const tagged = Object.entries(data.by_tag || {}).filter(([, v]) => (v.calls || 0) > 0);
  // Free-tier models cost $0, which would flatten every bar to the chart's
  // minimum height and make the widget look empty. Chart call volume instead.
  const hasSpend = tagged.some(([, v]) => (v.estimated_cost_usd || 0) > 0);
  const metric = hasSpend ? 'estimated_cost_usd' : 'calls';
  const rows = tagged
    .sort((a, b) => (b[1][metric] || 0) - (a[1][metric] || 0))
    .slice(0, 6)
    .map(([tag, v], i) => ({
      label: tag.replace(/_/g, ' '),
      value: hasSpend ? Number((v.estimated_cost_usd || 0).toFixed(4)) : (v.calls || 0),
      color: tagColors[i % tagColors.length],
    }));
  const total = data.totals || {};
  return (
    <Widget title={hasSpend || rows.length === 0 ? 'Spend by task type' : 'Calls by task type'} loading={loading} error={error} onRetry={onRetry}>
      {rows.length === 0 && !loading && !error && (
        <div style={{ fontSize:13, color: 'var(--text-muted)', fontVariantNumeric:'tabular-nums', lineHeight: 1.6 }}>
          No tagged LLM calls recorded yet since the last restart.
        </div>
      )}
      {rows.length > 0 && <BarChart data={rows} height={100} />}
      {rows.length > 0 && (
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 10, fontSize:13, fontVariantNumeric:'tabular-nums', color: 'var(--text-muted)' }}>
          <span>{total.calls ?? 0} calls tracked</span>
          <span>{hasSpend ? `$${(total.estimated_cost_usd ?? 0).toFixed(4)} est. spend` : 'free tier · $0.00 spend'}</span>
        </div>
      )}
    </Widget>
  );
}

// Mirrors the terminal members of TaskStatus in tasks/models.py.
const TERMINAL_TASK_STATUSES = new Set(['done', 'failed', 'wont_do']);
const NEEDS_HUMAN = new Set(['in_review', 'review', 'needs_clarification', 'blocked', 'awaiting_approval']);
const NEEDS_LABEL = { in_review: 'Ready for review', review: 'Ready for review', needs_clarification: 'Has a question', blocked: 'Stuck', awaiting_approval: 'Needs approval' };

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
}

function DashboardScreen({ onNavigate } = {}) {
  const [data, states, fetchAll] = useSafeData(null, {
    health:    '/api/health',
    stats:     '/api/stats',
    activity:  '/api/activity?limit=8',
    metrics:   '/api/observability/metrics',
    // /metrics has no time series; the daily request buckets live on /savings.
    usageTrend: '/api/observability/savings?period=week&bucket=day',
    providers: '/api/providers',
    tasks:     '/api/tasks/',
    rateLimits: '/api/metrics/rate-limits',
    selfHeal:  '/api/metrics/self-heal',
    costByTag: '/api/metrics/cost-attribution',
  }, { refreshMs: 30000 });

  // Map /api/tasks/ to the Open Tasks widget (exclude finished/failed)
  const openTasks = React.useMemo(() => {
    const all = data.tasks?.tasks || [];
    return all
      // Tasks waiting on a person are listed under "Needs you" instead.
      .filter(t => !TERMINAL_TASK_STATUSES.has(t.status) && !NEEDS_HUMAN.has(t.status) && !t.requires_approval)
      .slice(0, 6)
      .map(t => ({ id: t.task_id || t.id, title: t.title, status: t.status, priority: t.priority }));
  }, [data.tasks]);

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
      agent: log.event_type ? log.event_type.replace(/_event$/, '').replace(/_/g, ' ').replace(/^./, c => c.toUpperCase()) : 'System',
      pr: null,
    }));
  }, [data.activity]);

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
    const t = data.usageTrend || {};
    const series = t.time_series || t.buckets || m.time_series || m.buckets || [];
    const trend = Array.isArray(series) ? series.map((b) => Number(b.requests) || 0) : [];
    return {
      saved: `$${saved.toFixed(2)}`,
      requests,
      tokens: fmtTokens(tokens),
      avgTokens: requests ? fmtTokens(Math.round(tokens / requests)) : '—',
      localRatio: null, // no cloud/local split in metrics yet — bar hidden
      trend,
    };
  }, [data.metrics, data.usageTrend]);

  // Task status breakdown for the distribution donut.
  const taskBreakdown = React.useMemo(() => {
    const all = data.tasks?.tasks || [];
    const buckets = {
      in_progress: { label: 'In progress', value: 0, color: 'var(--accent)' },
      todo: { label: 'To do', value: 0, color: 'var(--text-muted)' },
      in_review: { label: 'In review', value: 0, color: 'var(--warning)' },
      done: { label: 'Done', value: 0, color: 'var(--success)' },
      blocked: { label: 'Blocked', value: 0, color: 'var(--danger)' },
      needs_clarification: { label: 'Needs input', value: 0, color: 'var(--violet)' },
      failed: { label: 'Failed', value: 0, color: 'var(--danger)' },
      wont_do: { label: "Won't do", value: 0, color: 'var(--text-muted)' },
    };
    all.forEach((t) => {
      const b = buckets[t.status] || buckets.todo;
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
  const today = new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' });

  // Tasks waiting on a person come first: they are the reason to open Home.
  const needsYou = React.useMemo(() => {
    const all = data.tasks?.tasks || [];
    return all
      .filter(t => NEEDS_HUMAN.has(t.status) || t.requires_approval)
      .slice(0, 5)
      .map(t => ({ id: t.task_id || t.id, title: t.title, status: t.status }));
  }, [data.tasks]);

  const [detailsOpen, setDetailsOpen] = React.useState(() => {
    try { return localStorage.getItem('home_details_open') === '1'; } catch { return false; }
  });
  const onToggleDetails = (e) => {
    const open = e.currentTarget.open;
    setDetailsOpen(open);
    try { localStorage.setItem('home_details_open', open ? '1' : '0'); } catch { /* storage blocked */ }
  };

  const statusLine = anyLoading
    ? 'Checking on your team…'
    : !systemOk
      ? 'Some systems are not responding. Your team may be slower than usual.'
      : needsYou.length
        ? `Everything is running. ${needsYou.length === 1 ? 'One thing needs' : `${needsYou.length} things need`} your decision.`
        : 'Everything is running. Nothing needs you right now.';

  return (
    <div className="dash">
      <header className="dash-hero">
        <p className="dash-date">{today}</p>
        <h1 className="dash-title">{greeting()}</h1>
        <p className="dash-status" role="status">
          <span className={`dash-status-dot ${anyLoading ? '' : systemOk ? 'is-ok' : 'is-warn'}`} aria-hidden="true"/>
          {statusLine}
        </p>
      </header>

      <section className="dash-section" aria-labelledby="needs-you">
        <h2 id="needs-you" className="dash-h2">Needs you</h2>
        {needsYou.length === 0 ? (
          <p className="dash-empty">
            <Icon name="Check" size={18} style={{ color: 'var(--success)', flexShrink: 0 }}/>
            You are all caught up. Approvals and questions from your team will appear here.
          </p>
        ) : (
          <ul className="dash-list">
            {needsYou.map(t => (
              <li key={t.id}>
                <button type="button" className="dash-row" onClick={() => onNavigate && onNavigate('tasks')}>
                  <span className="dash-row-mark is-warn" aria-hidden="true"/>
                  <span className="dash-row-text">{t.title}</span>
                  <span className="dash-row-meta">{NEEDS_LABEL[t.status] || 'Needs approval'}</span>
                  <Icon name="ChevronRight" size={18} style={{ color: 'var(--text-muted)', flexShrink: 0 }}/>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="dash-pair">
        <ErrorBoundary onRetry={fetchAll} resetKey={String(states.tasks?.error || '')}>
          <TasksWidget
            title="In progress"
            tasks={openTasks}
            loading={states.tasks?.loading}
            error={states.tasks?.error}
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
      </div>

      <details className="dash-details" open={detailsOpen} onToggle={onToggleDetails}>
        <summary>
          <span>
            <span className="dash-h2">System details</span>
            <span className="dash-summary-sub">
              {data.stats
                ? `${data.stats.chat_sessions || 0} conversations · ${data.stats.wiki_pages || 0} knowledge pages · ${data.stats.providers || 0} AI provider${(data.stats.providers || 0) === 1 ? '' : 's'}`
                : 'Providers, costs, health and self-repair'}
            </span>
          </span>
          <Icon name="ChevronRight" size={18} style={{ color: 'var(--text-muted)' }}/>
        </summary>
      <div className="dash-grid">
        <ErrorBoundary onRetry={fetchAll} resetKey={String(states.health?.error || states.providers?.error || '')}>
          <ProviderHealthWidget
            data={providerData}
            loading={states.health?.loading || states.providers?.loading}
            error={states.health?.error || states.providers?.error}
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
        <ErrorBoundary onRetry={fetchAll} resetKey={String(states.rateLimits?.error || '')}>
          <RateLimiterWidget
            providers={data.rateLimits?.providers}
            loading={states.rateLimits?.loading}
            error={states.rateLimits?.error}
            onRetry={fetchAll}
          />
        </ErrorBoundary>
        <ErrorBoundary onRetry={fetchAll} resetKey={String(states.selfHeal?.error || '')}>
          <SelfHealWidget
            data={data.selfHeal || {}}
            loading={states.selfHeal?.loading}
            error={states.selfHeal?.error}
            onRetry={fetchAll}
          />
        </ErrorBoundary>
        <ErrorBoundary onRetry={fetchAll} resetKey={String(states.costByTag?.error || '')}>
          <CostBreakdownWidget
            data={data.costByTag || {}}
            loading={states.costByTag?.loading}
            error={states.costByTag?.error}
            onRetry={fetchAll}
          />
        </ErrorBoundary>
      </div>
      </details>
    </div>
  );
}

export { DashboardScreen };
export default DashboardScreen;
