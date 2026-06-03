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
    <div style={{ height:3, borderRadius:999, background:'rgba(255,255,255,0.08)', width:60, flexShrink:0 }}>
      <div style={{ height:'100%', borderRadius:999, background:color, width:`${Math.min((value/max)*100,100)}%`, transition:'width 0.4s ease' }}/>
    </div>
  );
}

function ActivityRow({ entry }) {
  const isError   = entry.level === 'error' || entry.event_type === 'error';
  const statusColor = isError ? '#ff6b7d' : '#46d9a4';
  const model     = entry.model || entry.model_used || entry.metadata?.model || '—';
  const provider  = entry.provider || entry.metadata?.provider || '—';
  const tokens    = entry.tokens || entry.tokens_used || entry.metadata?.tokens || 0;
  const latencyMs = entry.latency_ms || entry.metadata?.latency_ms || 0;
  const sessionId = entry.session_id || entry.job_id || entry.source_run_id || '—';
  const agent     = entry.actor || entry.agent_id || entry.metadata?.agent || null;
  const ts        = entry.created_at || entry.timestamp;

  return (
    <div style={{ display:'flex', alignItems:'center', gap:10, padding:'10px 16px', borderBottom:'1px solid rgba(255,255,255,0.04)', transition:'background 0.15s' }}
    onMouseEnter={e => e.currentTarget.style.background='rgba(255,255,255,0.02)'}
    onMouseLeave={e => e.currentTarget.style.background='transparent'}>
      <span style={{ width:6, height:6, borderRadius:'50%', background:statusColor, flexShrink:0 }}/>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:12, fontWeight:600, color:'var(--text-primary)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
          {model !== '—' ? model : (entry.message || entry.event_type || 'Activity')}
          {agent && <span style={{ marginLeft:6, fontSize:10, fontFamily:'var(--font-mono)', color:'var(--accent)' }}>@{agent}</span>}
        </div>
        <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', lineHeight:1.4, display:'-webkit-box', WebkitLineClamp:2, WebkitBoxOrient:'vertical', overflow:'hidden' }}>{provider} · {sessionId}</div>
      </div>
      {latencyMs > 0 && <SparkBar value={latencyMs} max={20000} color={latencyMs > 10000 ? '#ffbd66' : '#46d9a4'}/>}
      <div style={{ textAlign:'right', flexShrink:0, minWidth:80 }}>
        {tokens > 0 && <div style={{ fontSize:11, fontWeight:600, color:'var(--text-secondary)' }}>{tokens.toLocaleString()} tok</div>}
        {latencyMs > 0 && <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{latencyMs < 1000 ? `${latencyMs}ms` : `${(latencyMs/1000).toFixed(1)}s`}</div>}
      </div>
      <div style={{ textAlign:'right', flexShrink:0 }}>
        <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{relTime(ts)}</div>
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
      background:severity==='error'?'rgba(255,107,125,0.06)':'rgba(255,189,102,0.06)',
      border:`1px solid ${severity==='error'?'rgba(255,107,125,0.20)':'rgba(255,189,102,0.18)'}`,
      opacity:isResolved?0.55:1, marginBottom:10,
    }}>
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
        <span style={{ fontSize:11, color:severity==='error'?'#ff6b7d':'#ffbd66', fontFamily:'var(--font-mono)', letterSpacing:'0.10em', textTransform:'uppercase' }}>{severity}</span>
        {isResolved && <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'#46d9a4', padding:'1px 6px', borderRadius:999, background:'rgba(70,217,164,0.10)', border:'1px solid rgba(70,217,164,0.20)' }}>resolved</span>}
        <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', marginLeft:'auto' }}>{relTime(ts)}</span>
      </div>
      <div style={{ fontSize:12, color:'var(--text-secondary)', lineHeight:1.5 }}>{entry.message || entry.event_type}</div>
    </div>
  );
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
  const langfuseUrl = data.dashUrl?.url || null;

  const totalTokens = metrics.total_tokens || metrics.tokens_24h || 0;
  const totalCost   = metrics.total_cost   || metrics.cost_24h   || 0;
  const avgLatency  = metrics.avg_latency_ms || 0;
  const errorCount  = errors.length;

  const loading  = states.activity?.loading;
  const actError = states.activity?.error;

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', overflow:'hidden' }}>
      {/* Header */}
      <div style={{ padding:'20px 20px 0', flexShrink:0 }}>
        <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:6 }}>Observability</div>
        <div style={{ display:'flex', alignItems:'flex-end', justifyContent:'space-between', flexWrap:'wrap', gap:10, marginBottom:14 }}>
          <div>
            <h1 style={{ fontSize:26, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', lineHeight:1.1, marginBottom:4 }}>Logs & Activity</h1>
            <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.5, maxWidth:480 }}>Backend activity log and metrics. Full Langfuse traces in the Langfuse dashboard.</p>
          </div>
          <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
            {[
              { label:'Tokens', value:totalTokens > 0 ? totalTokens.toLocaleString() : '—', color:'var(--accent)' },
              { label:'Avg latency', value:avgLatency > 0 ? `${avgLatency}ms` : '—', color:'#46d9a4' },
              { label:'Cost', value:totalCost > 0 ? `$${totalCost.toFixed(3)}` : '—', color:totalCost>0?'#ffbd66':'#46d9a4' },
              { label:'Errors', value:errorCount, color:errorCount>0?'#ff6b7d':'#46d9a4' },
            ].map(s => (
              <div key={s.label} style={{ padding:'8px 12px', borderRadius:12, background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.08)', textAlign:'center' }}>
                <div style={{ fontSize:18, fontWeight:800, color:s.color, letterSpacing:'-0.03em' }}>{s.value}</div>
                <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.10em' }}>{s.label}</div>
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
              padding:'7px 18px', borderRadius:'10px 10px 0 0', fontSize:12, fontWeight:600, cursor:'pointer',
              transition:'all 0.15s',
              background:tab===t.id?'rgba(10,12,15,0.90)':'rgba(255,255,255,0.03)',
              border:`1px solid ${tab===t.id?'rgba(255,255,255,0.10)':'rgba(255,255,255,0.06)'}`,
              borderBottom:tab===t.id?'1px solid rgba(10,12,15,0.90)':'1px solid rgba(255,255,255,0.06)',
              color:tab===t.id?'#fff':'var(--text-muted)',
            }}>
              {t.label}
              {t.badge > 0 && <span style={{ marginLeft:6, fontSize:9, padding:'1px 5px', borderRadius:999, background:'rgba(255,107,125,0.20)', color:'#ff6b7d' }}>{t.badge}</span>}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex:1, overflow:'auto', background:'rgba(10,12,15,0.90)', borderTop:'1px solid rgba(255,255,255,0.08)' }}>
        {loading && (
          <div style={{ padding:'24px 16px', fontSize:12, color:'var(--text-muted)', fontFamily:'var(--font-mono)' }}>Loading activity…</div>
        )}
        {!loading && actError && (
          <div style={{ padding:'16px', margin:'12px', borderRadius:10, background:'rgba(255,107,125,0.07)', border:'1px solid rgba(255,107,125,0.18)', fontSize:12, color:'#ff6b7d' }}>
            Could not load activity log: {actError}
          </div>
        )}

        {tab === 'activity' && !loading && (
          <>
            <div style={{ padding:'8px 16px', display:'flex', justifyContent:'space-between', borderBottom:'1px solid rgba(255,255,255,0.06)', fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.12em' }}>
              <span>Event · Actor · Session</span><span>Tokens · Latency · Time</span>
            </div>
            {logs.length === 0 && !actError && (
              <div style={{ padding:'32px', textAlign:'center', color:'var(--text-muted)', fontSize:13 }}>
                No activity logged yet. Activity entries appear here as the backend processes requests and agent jobs.
              </div>
            )}
            {logs.map((entry, i) => <ActivityRow key={entry._id || entry.id || i} entry={entry}/>)}
            {langfuseUrl && (
              <div style={{ padding:'12px 16px' }}>
                <a href={langfuseUrl} target="_blank" rel="noreferrer" style={{ fontSize:12, color:'var(--accent)', fontFamily:'var(--font-mono)', display:'inline-flex', alignItems:'center', gap:5 }}>
                  Open full trace explorer in Langfuse →
                </a>
              </div>
            )}
          </>
        )}

        {tab === 'errors' && !loading && (
          <div style={{ padding:'16px' }}>
            {errors.length === 0 && (
              <div style={{ padding:'32px', textAlign:'center', color:'#46d9a4', fontSize:13 }}>
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
