/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';


// dashboard.jsx — Resilient Dashboard with per-widget loading/error states

const MOCK_HEALTH = {
  provider: { name: 'NVIDIA NIM', model: 'nemotron-3-super-120b', status: 'healthy', latency: 42, queue: 0 },
  runtime: { name: 'Hermes v2', status: 'healthy', uptime: '14d 3h', jobs: 3 },
  mongo: true, ollama: true, langfuse: false, scheduler: true,
};
const MOCK_JOBS = [
  { id: 'j-1', title: 'Fix checkout null-pointer', status: 'completed', phase: 'pr', ago: '2m', agent: 'Dev Agent', pr: '#1842' },
  { id: 'j-2', title: 'Security scan — auth module', status: 'running',   phase: 'verifying', ago: '8m', agent: 'Security Agent' },
  { id: 'j-3', title: 'Dependency audit', status: 'queued',    phase: 'queued', ago: '12m', agent: 'Release Agent' },
  { id: 'j-4', title: 'Weekly changelog check', status: 'completed', phase: 'done', ago: '1h', agent: 'Release Agent' },
];
const MOCK_TASKS = [
  { id: 't-1', title: 'Migrate DB schema to v3', status: 'in_progress', priority: 'high', pr: null },
  { id: 't-2', title: 'Add rate limiting to /api/chat', status: 'todo', priority: 'medium', pr: null },
  { id: 't-3', title: 'Fix mobile layout on dashboard', status: 'blocked', priority: 'urgent', pr: '#1840' },
];
const MOCK_COST = { month: '$0.00', saved: '$214.80', requests: 4812, tokens: '2.1M', localRatio: 0.87 };
const MOCK_SIGNALS = [
  { label: 'Error rate', value: '0.2%', ok: true },
  { label: 'Avg latency', value: '148ms', ok: true },
  { label: 'CI status', value: 'Passing', ok: true },
  { label: 'Langfuse', value: 'Disconnected', ok: false },
];

// Widget wrapper with per-widget loading/error states
function Widget({ title, action, actionLabel, loading, error, errorSeverity = 'warning', children, span = 1 }) {
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

function ProviderHealthWidget({ data, loading, error }) {
  return (
    <Widget title="Provider & Runtime" loading={loading} error={error} errorSeverity="warning">
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {/* Provider */}
        <div style={{ padding: '12px 14px', borderRadius: 12, background: 'rgba(93,162,255,0.05)', border: '1px solid rgba(93,162,255,0.12)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
              <StatusDot ok={true} pulse/>
              <span style={{ fontSize: 13, fontWeight: 700, color: '#fff' }}>{data.provider.name}</span>
              <Pill label="Priority 0" color="#7c9dff" bg="rgba(124,157,255,0.10)" border="rgba(124,157,255,0.20)"/>
            </div>
            <span style={{ fontSize: 11, color: '#46d9a4', fontFamily: 'var(--font-mono)' }}>{data.provider.latency}ms</span>
          </div>
          <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{data.provider.model}</div>
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
          <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>Up {data.runtime.uptime}</div>
        </div>
      </div>
    </Widget>
  );
}

function RecentJobsWidget({ jobs, loading, error }) {
  const statusConfig = {
    completed: { color: '#46d9a4', label: 'Done', bg: 'rgba(70,217,164,0.08)' },
    running:   { color: '#5da2ff', label: 'Running', bg: 'rgba(93,162,255,0.08)' },
    queued:    { color: 'var(--text-muted)', label: 'Queued', bg: 'rgba(255,255,255,0.04)' },
    failed:    { color: '#ff6b7d', label: 'Failed', bg: 'rgba(255,107,125,0.08)' },
  };
  return (
    <Widget title="Recent Jobs" loading={loading} error={error}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {jobs.map(job => {
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

function TasksWidget({ tasks, loading, error }) {
  const priorityColor = { urgent: '#ff6b7d', high: '#ffbd66', medium: 'var(--text-muted)' };
  const statusColor = { in_progress: '#5da2ff', todo: 'var(--text-muted)', blocked: '#ff6b7d' };
  return (
    <Widget title="Open Tasks" loading={loading} error={error}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
        {tasks.map(t => (
          <div key={t.id} style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px',
            borderRadius: 11, background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.07)',
            cursor: 'pointer', transition: 'background 0.15s',
          }}
          onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.045)'}
          onMouseLeave={e => e.currentTarget.style.background = 'rgba(255,255,255,0.025)'}>
            <span style={{ width: 6, height: 6, borderRadius: '50%', background: statusColor[t.status], flexShrink: 0 }}/>
            <span style={{ flex: 1, fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.title}</span>
            <Pill label={t.priority} color={priorityColor[t.priority]}/>
          </div>
        ))}
      </div>
    </Widget>
  );
}

function CostWidget({ data, loading, error }) {
  const barW = `${Math.round(data.localRatio * 100)}%`;
  return (
    <Widget title="Cost & Usage" loading={loading} error={error}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
        {[
          { label: 'This month', value: data.month, color: 'var(--text-primary)' },
          { label: 'Cost saved', value: data.saved, color: '#46d9a4' },
          { label: 'Requests', value: data.requests.toLocaleString(), color: 'var(--accent)' },
          { label: 'Tokens', value: data.tokens, color: '#c4b5fd' },
        ].map(m => (
          <div key={m.label} style={{ padding: '10px 12px', borderRadius: 10, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)' }}>
            <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 4 }}>{m.label}</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: m.color, letterSpacing: '-0.03em' }}>{m.value}</div>
          </div>
        ))}
      </div>
      {/* Local ratio bar */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Local / free ratio</span>
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: '#46d9a4', fontWeight: 700 }}>{barW}</span>
        </div>
        <div style={{ height: 6, borderRadius: 999, background: 'rgba(255,255,255,0.08)' }}>
          <div style={{ height: '100%', borderRadius: 999, width: barW, background: 'linear-gradient(90deg, #46d9a4, #5da2ff)', transition: 'width 0.8s ease' }}/>
        </div>
      </div>
    </Widget>
  );
}

function MonitoringWidget({ signals, loading, error }) {
  return (
    <Widget title="Monitoring" loading={loading} error={error}>
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

function SystemHealthWidget({ health, loading, error }) {
  const services = [
    { label: 'MongoDB', ok: health.mongo },
    { label: 'Ollama', ok: health.ollama },
    { label: 'Langfuse', ok: health.langfuse },
    { label: 'Scheduler', ok: health.scheduler },
  ];
  return (
    <Widget title="System Health" loading={loading} error={error} errorSeverity="warning">
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {services.map(s => (
          <div key={s.label} style={{
            display: 'flex', alignItems: 'center', gap: 6,
            padding: '6px 12px', borderRadius: 999,
            background: s.ok ? 'rgba(70,217,164,0.07)' : 'rgba(255,189,102,0.07)',
            border: `1px solid ${s.ok ? 'rgba(70,217,164,0.18)' : 'rgba(255,189,102,0.22)'}`,
          }}>
            <StatusDot ok={s.ok}/>
            <span style={{ fontSize: 12, color: s.ok ? 'var(--text-secondary)' : '#ffbd66' }}>{s.label}</span>
          </div>
        ))}
      </div>
      <div style={{ marginTop: 10, padding: '8px 12px', borderRadius: 10, background: 'rgba(255,189,102,0.05)', border: '1px solid rgba(255,189,102,0.12)' }}>
        <div style={{ fontSize: 11, color: '#ffbd66', lineHeight: 1.5 }}>
          ⚠ Langfuse traces unavailable — observability data is limited. <a href="#" style={{ color: '#ffbd66', textDecoration: 'underline' }}>Configure →</a>
        </div>
      </div>
    </Widget>
  );
}

function DashboardScreen({ dashboardState }) {
  const isPartialFailure = dashboardState === 'partial';
  const [widgetLoading] = React.useState(false);

  return (
    <div style={{ padding: '20px 16px 32px', maxWidth: 1200, margin: '0 auto' }}>
      {/* Page header */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <span style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            padding: '3px 10px', borderRadius: 999, fontSize: 10,
            fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', textTransform: 'uppercase',
            background: 'rgba(70,217,164,0.10)', border: '1px solid rgba(70,217,164,0.20)', color: '#46d9a4',
          }}>
            <span style={{ width: 5, height: 5, borderRadius: '50%', background: '#46d9a4', animation: 'pulse 2s infinite' }}/>
            {isPartialFailure ? 'Partial failure' : 'System healthy'}
          </span>
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>May 22, 2026</span>
        </div>
        <h1 style={{ fontSize: 'clamp(22px,4vw,32px)', fontWeight: 800, color: '#fff', letterSpacing: '-0.04em', lineHeight: 1.1, marginBottom: 6 }}>Dashboard</h1>
        <p style={{ fontSize: 14, color: 'var(--text-tertiary)', maxWidth: 520, lineHeight: 1.6 }}>
          Agency Core command center — 3 active agents, 4 scheduled jobs, 87% local routing.
        </p>
        {isPartialFailure && (
          <div style={{
            display: 'flex', alignItems: 'flex-start', gap: 8, marginTop: 12,
            padding: '10px 14px', borderRadius: 12,
            background: 'rgba(255,189,102,0.07)', border: '1px solid rgba(255,189,102,0.20)',
          }}>
            <span style={{ color: '#ffbd66', flexShrink: 0, marginTop: 1 }}>⚠</span>
            <div style={{ fontSize: 12, color: '#ffbd66', lineHeight: 1.5 }}>
              <strong>Partial data available.</strong> Langfuse is unreachable — usage data and traces may be incomplete.
              Cost metrics are estimated from local logs. Affected widgets show a warning inline.
            </div>
          </div>
        )}
      </div>

      {/* Widget grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
        gap: 14,
      }}>
        <ProviderHealthWidget
          data={MOCK_HEALTH}
          loading={widgetLoading}
          error={null}
        />
        <RecentJobsWidget
          jobs={MOCK_JOBS}
          loading={widgetLoading}
          error={null}
        />
        <TasksWidget
          tasks={MOCK_TASKS}
          loading={widgetLoading}
          error={null}
        />
        <CostWidget
          data={MOCK_COST}
          loading={widgetLoading}
          error={isPartialFailure ? 'Langfuse disconnected — cost data estimated from local logs.' : null}
          errorSeverity="warning"
        />
        <MonitoringWidget
          signals={MOCK_SIGNALS}
          loading={widgetLoading}
          error={null}
        />
        <SystemHealthWidget
          health={MOCK_HEALTH}
          loading={widgetLoading}
          error={isPartialFailure ? 'Langfuse service unreachable. Other services nominal.' : null}
          errorSeverity="warning"
        />
      </div>
    </div>
  );
}

export { DashboardScreen };
export default DashboardScreen;
