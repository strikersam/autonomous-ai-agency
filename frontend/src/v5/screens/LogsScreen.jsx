/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import { useSafeData } from '../hooks/useSafeData';

// logs.jsx — Observability: activity log, metrics, error feed

function relTime(val) {
  if (!val) return '—';
  const ts = typeof val === 'number' ? val * 1000 : new Date(val).getTime();
  if (isNaN(ts)) return '—';
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}

function SparkBar({ value, max, color = 'var(--accent)' }) {
  return (
    <div style={{ height:3, borderRadius:999, background:'color-mix(in oklab, var(--ink) 8%, transparent)', width:60, flexShrink:0 }}>
      <div style={{ height:'100%', borderRadius:999, background:color, width:`${Math.min((value/max)*100,100)}%`, transition:'width 0.4s ease' }}/>
    </div>
  );
}

function ActivityRow({ entry }) {
  const isError   = entry.level === 'error' || entry.event_type === 'error';
  const statusColor = isError ? 'var(--danger)' : 'var(--success)';
  const model     = entry.model || entry.model_used || entry.metadata?.model || '—';
  const provider  = entry.provider || entry.metadata?.provider || '—';
  const tokens    = entry.tokens || entry.tokens_used || entry.metadata?.tokens || 0;
  const latencyMs = entry.latency_ms || entry.metadata?.latency_ms || 0;
  const sessionId = entry.session_id || entry.job_id || entry.source_run_id || '—';
  const agent     = entry.actor || entry.agent_id || entry.metadata?.agent || null;
  const ts        = entry.created_at || entry.timestamp;
  const [expanded, setExpanded] = React.useState(false);
  const messageText = entry.message || '';
  const hasLongMessage = messageText.length > 80 || messageText.includes('\n');

  return (
    <div style={{ display:'flex', alignItems:'flex-start', gap:10, padding:'10px 16px', borderBottom:'1px solid color-mix(in oklab, var(--ink) 4%, transparent)', transition:'background 0.15s', cursor: hasLongMessage ? 'pointer' : 'default' }}
    onClick={hasLongMessage ? () => setExpanded(e => !e) : undefined}
    onMouseEnter={e => e.currentTarget.style.background='color-mix(in oklab, var(--ink) 2%, transparent)'}
    onMouseLeave={e => e.currentTarget.style.background='transparent'}>
      <span style={{ width:6, height:6, borderRadius:'50%', background:statusColor, flexShrink:0, marginTop:7 }}/>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:13, fontWeight:600, color:'var(--text-primary)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace: expanded ? 'normal' : 'nowrap' }}>
          {model !== '—' ? model : humanize(entry.event_type) || 'Activity'}
          {agent && <span style={{ marginLeft:6, fontSize:13, fontFamily:'var(--font-mono)', color:'var(--accent)' }}>@{agent}</span>}
        </div>
        {messageText && (
          <div style={{ fontSize:13, color:'var(--text-tertiary)', lineHeight:1.5, wordBreak:'break-word', whiteSpace: expanded ? 'pre-wrap' : 'nowrap', overflow:'hidden', textOverflow:'ellipsis', marginTop:2 }}>
            {expanded ? messageText : (hasLongMessage ? messageText.slice(0, 80) + '…' : messageText)}
          </div>
        )}
        {hasLongMessage && !expanded && (
          <div style={{ fontSize:13, color:'var(--accent)', marginTop:3 }}>Show more</div>
        )}
        {(provider !== '—' || sessionId !== '—') && (
          <div style={{ fontSize:13, fontFamily:'var(--font-mono)', color:'var(--text-muted)', lineHeight:1.4, whiteSpace: expanded ? 'normal' : 'nowrap', overflow:'hidden', textOverflow:'ellipsis' }}>{[provider, sessionId].filter(v => v !== '—').join(' · ')}</div>
        )}
      </div>
      {latencyMs > 0 && <SparkBar value={latencyMs} max={20000} color={latencyMs > 10000 ? 'var(--warning)' : 'var(--success)'}/>}
      <div style={{ textAlign:'right', flexShrink:0, minWidth:80, marginTop:2 }}>
        {tokens > 0 && <div style={{ fontSize:13, fontWeight:600, color:'var(--text-secondary)' }}>{tokens.toLocaleString()} tok</div>}
        {latencyMs > 0 && <div style={{ fontSize:13, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{latencyMs < 1000 ? `${latencyMs}ms` : `${(latencyMs/1000).toFixed(1)}s`}</div>}
      </div>
      <div style={{ textAlign:'right', flexShrink:0, marginTop:2 }}>
        <div style={{ fontSize:13, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{relTime(ts)}</div>
      </div>
    </div>
  );
}

function ErrorRow({ entry }) {
  const severity   = entry.level === 'error' ? 'error' : 'warn';
  const isResolved = !!(entry.resolved);
  const ts         = entry.created_at || entry.timestamp;
  return (
    <div style={{
      padding:'12px 14px', borderRadius:14,
      background:severity==='error'?'color-mix(in oklab, var(--danger) 6%, transparent)':'color-mix(in oklab, var(--warning) 6%, transparent)',
      border:`1px solid ${severity==='error'?'color-mix(in oklab, var(--danger) 20%, transparent)':'color-mix(in oklab, var(--warning) 18%, transparent)'}`,
      opacity:isResolved?0.55:1, marginBottom:10,
    }}>
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
        <span style={{ fontSize:13, color:severity==='error'?'var(--danger)':'var(--warning)' }}>{severity}</span>
        {isResolved && <span style={{ fontSize:13, fontFamily:'var(--font-mono)', color:'var(--success)', padding:'1px 6px', borderRadius:999, background:'color-mix(in oklab, var(--success) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--success) 20%, transparent)' }}>resolved</span>}
        <span style={{ fontSize:13, fontFamily:'var(--font-mono)', color:'var(--text-muted)', marginLeft:'auto' }}>{relTime(ts)}</span>
      </div>
      <div style={{ fontSize:13, color:'var(--text-secondary)', lineHeight:1.5 }}>{entry.message || entry.event_type}</div>
    </div>
  );
}

// "task_event" -> "Task", "provider_failover" -> "Provider failover"
function humanize(key) {
  if (!key) return '';
  const t = String(key).replace(/_event$/, '').replace(/[_-]+/g, ' ').trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function LogsScreen() {
  const [tab, setTab] = React.useState('activity');

  const [data, states] = useSafeData(null, {
    activity: '/api/activity?limit=50',
    metrics:  '/api/observability/metrics',
    dashUrl:  '/api/observability/dashboard-url',
  }, { refreshMs: 30000 });

  const logs     = data.activity?.logs || data.activity?.activity || [];
  const errors   = logs.filter(e => e.level === 'error' || e.event_type === 'error');
  const metrics  = data.metrics || {};
  const langfuseUrl = data.dashUrl?.configured === false ? null : (data.dashUrl?.url || null);

  const summary24h  = metrics.summary_24h || {};
  const latencies   = (metrics.recent_traces || []).map(t => Number(t.latency_ms)).filter(n => n > 0);
  const totalTokens = summary24h.total_tokens || metrics.total_tokens || 0;
  const totalCost   = summary24h.total_savings_usd || metrics.total_cost || 0;
  const avgLatency  = latencies.length ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length) : (metrics.avg_latency_ms || 0);
  const errorCount  = errors.length;

  const loading  = states.activity?.loading;
  const actError = states.activity?.error;

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', overflow:'hidden' }}>
      {/* Header */}
      <div style={{ padding:'20px 20px 0', flexShrink:0 }}>
        <div style={{ display:'flex', alignItems:'flex-end', justifyContent:'space-between', flexWrap:'wrap', gap:10, marginBottom:14 }}>
          <div>
            <h1 style={{ fontSize:26, fontWeight:700, color:'var(--text-primary)', letterSpacing:'-0.04em', lineHeight:1.1, marginBottom:4 }}>Logs & activity</h1>
            <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.5, maxWidth:480 }}>Backend activity log and metrics. Full Langfuse traces in the Langfuse dashboard.</p>
          </div>
          <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
            {[
              { label:'Tokens', value:totalTokens > 0 ? totalTokens.toLocaleString() : '—', color:'var(--accent)' },
              { label:'Avg latency', value:avgLatency > 0 ? `${avgLatency}ms` : '—', color:'var(--success)' },
              { label:'Cost', value:totalCost > 0 ? `$${totalCost.toFixed(3)}` : '—', color:totalCost>0?'var(--warning)':'var(--success)' },
              { label:'Errors', value:errorCount, color:errorCount>0?'var(--danger)':'var(--success)' },
            ].map(s => (
              <div key={s.label} style={{ padding:'8px 12px', borderRadius:12, background:'color-mix(in oklab, var(--ink) 4%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)', textAlign:'center' }}>
                <div style={{ fontSize:18, fontWeight:700, color:s.color, letterSpacing:'-0.03em' }}>{s.value}</div>
                <div style={{ fontSize:13, color:'var(--text-muted)' }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
        <div style={{ display:'flex', gap:4, marginBottom:0 }}>
          {[
            { id:'activity', label:'Activity' },
            { id:'errors',   label:'Errors', badge: errorCount },
          ].map(t => (
            <button key={t.id} onClick={() => setTab(t.id)} style={{
              padding:'7px 18px', borderRadius:'10px 10px 0 0', fontSize:13, fontWeight:600, cursor:'pointer',
              transition:'all 0.15s',
              background:tab===t.id?'color-mix(in oklab, var(--bg-surface) 90%, transparent)':'color-mix(in oklab, var(--ink) 3%, transparent)',
              border:`1px solid ${tab===t.id?'color-mix(in oklab, var(--ink) 10%, transparent)':'color-mix(in oklab, var(--ink) 6%, transparent)'}`,
              borderBottom:tab===t.id?'1px solid color-mix(in oklab, var(--bg-surface) 90%, transparent)':'1px solid color-mix(in oklab, var(--ink) 6%, transparent)',
              color:tab===t.id?'var(--text-primary)':'var(--text-muted)',
            }}>
              {t.label}
              {t.badge > 0 && <span style={{ marginLeft:6, fontSize:13, padding:'1px 5px', borderRadius:999, background:'color-mix(in oklab, var(--danger) 20%, transparent)', color:'var(--danger)' }}>{t.badge}</span>}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex:1, overflow:'auto', background:'color-mix(in oklab, var(--bg-surface) 90%, transparent)', borderTop:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)' }}>
        {loading && (
          <div style={{ padding:'24px 16px', fontSize:13, color:'var(--text-muted)', fontFamily:'var(--font-mono)' }}>Loading activity…</div>
        )}
        {!loading && actError && (
          <div style={{ padding:'16px', margin:'12px', borderRadius:10, background:'color-mix(in oklab, var(--danger) 7%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 18%, transparent)', fontSize:13, color:'var(--danger)' }}>
            Could not load activity log: {actError}
          </div>
        )}

        {tab === 'activity' && !loading && (
          <>
            <div style={{ padding:'8px 16px', display:'flex', justifyContent:'space-between', borderBottom:'1px solid color-mix(in oklab, var(--ink) 6%, transparent)', fontSize:13, color:'var(--text-muted)' }}>
              <span>Event · Actor · Session</span><span>Tokens · Latency · Time</span>
            </div>
            {logs.length === 0 && !actError && (
              <div style={{ padding:'32px', textAlign:'center', color:'var(--text-muted)', fontSize:14 }}>
                No activity logged yet. Activity entries appear here as the backend processes requests and agent jobs.
              </div>
            )}
            {logs.map((entry, i) => <ActivityRow key={entry._id || entry.id || i} entry={entry}/>)}
            {langfuseUrl && (
              <div style={{ padding:'12px 16px' }}>
                <a href={langfuseUrl} target="_blank" rel="noreferrer" style={{ fontSize:13, color:'var(--accent)', fontFamily:'var(--font-mono)', display:'inline-flex', alignItems:'center', gap:5 }}>
                  Open full trace explorer in Langfuse →
                </a>
              </div>
            )}
          </>
        )}

        {tab === 'errors' && !loading && (
          <div style={{ padding:'16px' }}>
            {errors.length === 0 && (
              <div style={{ padding:'32px', textAlign:'center', color:'var(--success)', fontSize:14 }}>
                No errors in the activity log.
              </div>
            )}
            {errors.map((entry, i) => <ErrorRow key={entry._id || entry.id || i} entry={entry}/>)}
          </div>
        )}
      </div>
    </div>
  );
}

export { LogsScreen };
export default LogsScreen;
