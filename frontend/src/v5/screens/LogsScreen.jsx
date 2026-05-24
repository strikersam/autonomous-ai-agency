/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';


// logs.jsx — Observability: request logs, Langfuse traces, error feed

const MOCK_REQUESTS = [
  { id:'r-1', model:'nemotron-3-super-120b', provider:'NVIDIA NIM', tokens:1842, latencyMs:142, cost:0.000, status:'ok',  ts:'2m ago',  session:'chat-4a2', agent:null },
  { id:'r-2', model:'qwen3-coder:30b',       provider:'Ollama',     tokens:4210, latencyMs:8400,cost:0.000, status:'ok',  ts:'8m ago',  session:'job-1842', agent:'Dev Agent' },
  { id:'r-3', model:'deepseek-r1:32b',       provider:'Ollama',     tokens:2100, latencyMs:19200,cost:0.000,status:'ok',  ts:'14m ago', session:'job-1843', agent:'Reviewer Agent' },
  { id:'r-4', model:'groq/llama-3.3-70b',   provider:'Groq',       tokens:890,  latencyMs:310,  cost:0.000, status:'ok',  ts:'1h ago',  session:'chat-3f1', agent:null },
  { id:'r-5', model:'claude-opus-4-5',       provider:'Anthropic',  tokens:3120, latencyMs:4100, cost:0.031, status:'ok',  ts:'2h ago',  session:'job-1840', agent:'Dev Agent' },
  { id:'r-6', model:'nemotron-3-super-120b', provider:'NVIDIA NIM', tokens:540,  latencyMs:98,   cost:0.000, status:'error',ts:'3h ago', session:'chat-2c9', agent:null },
];

const MOCK_TRACES = [
  { id:'t-1', session:'job-1842', name:'Fix checkout null-check', spans:12, duration:'18.4s', tokens:4210, cost:0.000, status:'ok',   ts:'8m ago',  agent:'Dev Agent' },
  { id:'t-2', session:'job-1843', name:'Council review — v5.0 changes', spans:8, duration:'24.1s', tokens:2100, cost:0.000, status:'ok',ts:'14m ago', agent:'Reviewer Agent' },
  { id:'t-3', session:'chat-4a2', name:'Direct chat — checkout query', spans:3, duration:'0.3s',  tokens:1842, cost:0.000, status:'ok',   ts:'2m ago',  agent:null },
  { id:'t-4', session:'job-1840', name:'Schema migration planning', spans:15, duration:'41.2s', tokens:3120, cost:0.031, status:'ok',   ts:'2h ago',  agent:'Dev Agent' },
  { id:'t-5', session:'chat-2c9', name:'Routing error — fallback triggered', spans:2, duration:'4.1s',tokens:540, cost:0.000, status:'error',ts:'3h ago', agent:null },
];

const MOCK_ERRORS = [
  { id:'e-1', msg:'NVIDIA NIM: rate limit hit on request (429)', severity:'warn',  count:1, ts:'3h ago', resolved:true },
  { id:'e-2', msg:'Langfuse: connection refused on port 3100',    severity:'error', count:14,ts:'1d ago', resolved:false },
  { id:'e-3', msg:'Ollama: qwen3-coder:235b not found locally',  severity:'warn',  count:3, ts:'2d ago', resolved:false },
];

function SparkBar({ value, max, color = 'var(--accent)' }) {
  return (
    <div style={{ height:3, borderRadius:999, background:'rgba(255,255,255,0.08)', width:60, flexShrink:0 }}>
      <div style={{ height:'100%', borderRadius:999, background:color, width:`${Math.min((value/max)*100,100)}%`, transition:'width 0.4s ease' }}/>
    </div>
  );
}

function RequestRow({ req }) {
  const statusColor = req.status === 'ok' ? '#46d9a4' : '#ff6b7d';
  return (
    <div style={{ display:'flex', alignItems:'center', gap:10, padding:'10px 16px', borderBottom:'1px solid rgba(255,255,255,0.04)', transition:'background 0.15s' }}
    onMouseEnter={e => e.currentTarget.style.background='rgba(255,255,255,0.02)'}
    onMouseLeave={e => e.currentTarget.style.background='transparent'}>
      <span style={{ width:6, height:6, borderRadius:'50%', background:statusColor, flexShrink:0 }}/>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:12, fontWeight:600, color:'var(--text-primary)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
          {req.model}
          {req.agent && <span style={{ marginLeft:6, fontSize:10, fontFamily:'var(--font-mono)', color:'var(--accent)' }}>@{req.agent}</span>}
        </div>
        <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{req.provider} · {req.session}</div>
      </div>
      <SparkBar value={req.latencyMs} max={20000} color={req.latencyMs > 10000 ? '#ffbd66' : '#46d9a4'}/>
      <div style={{ textAlign:'right', flexShrink:0, minWidth:80 }}>
        <div style={{ fontSize:11, fontWeight:600, color:'var(--text-secondary)' }}>{req.tokens.toLocaleString()} tok</div>
        <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{req.latencyMs < 1000 ? `${req.latencyMs}ms` : `${(req.latencyMs/1000).toFixed(1)}s`}</div>
      </div>
      <div style={{ textAlign:'right', flexShrink:0 }}>
        <div style={{ fontSize:11, fontWeight:700, color:req.cost > 0 ? '#ffbd66' : '#46d9a4' }}>{req.cost > 0 ? `$${req.cost.toFixed(4)}` : 'free'}</div>
        <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{req.ts}</div>
      </div>
    </div>
  );
}

function TraceRow({ trace }) {
  const [expanded, setExpanded] = React.useState(false);
  return (
    <div style={{ borderBottom:'1px solid rgba(255,255,255,0.04)' }}>
      <button onClick={() => setExpanded(o=>!o)} style={{
        width:'100%', display:'flex', alignItems:'center', gap:10, padding:'11px 16px',
        background:'transparent', border:'none', cursor:'pointer', textAlign:'left',
        transition:'background 0.15s',
      }}
      onMouseEnter={e => e.currentTarget.style.background='rgba(255,255,255,0.02)'}
      onMouseLeave={e => e.currentTarget.style.background='transparent'}>
        <span style={{ width:6, height:6, borderRadius:'50%', background:trace.status==='ok'?'#46d9a4':'#ff6b7d', flexShrink:0 }}/>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ fontSize:12, fontWeight:600, color:'var(--text-primary)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{trace.name}</div>
          <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>
            {trace.agent ? `@${trace.agent}` : 'direct'} · {trace.spans} spans · {trace.session}
          </div>
        </div>
        <div style={{ textAlign:'right', flexShrink:0 }}>
          <div style={{ fontSize:11, fontWeight:600, color:'var(--text-secondary)' }}>{trace.duration}</div>
          <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{trace.tokens.toLocaleString()} tok</div>
        </div>
        <div style={{ textAlign:'right', flexShrink:0 }}>
          <div style={{ fontSize:11, fontWeight:700, color:trace.cost>0?'#ffbd66':'#46d9a4' }}>{trace.cost>0?`$${trace.cost.toFixed(4)}`:'free'}</div>
          <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{trace.ts}</div>
        </div>
        <span style={{ fontSize:12, color:'var(--text-muted)', transform:expanded?'rotate(90deg)':'none', transition:'transform 0.2s', flexShrink:0 }}>›</span>
      </button>
      {expanded && (
        <div style={{ padding:'0 16px 12px 32px', animation:'fadeSlideUp 0.2s ease-out' }}>
          <div style={{ padding:'10px 12px', borderRadius:10, background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.07)' }}>
            <div style={{ display:'flex', gap:0, flexDirection:'column' }}>
              {Array.from({length: Math.min(trace.spans, 5)}).map((_, i) => {
                const spanNames = ['system_prompt','user_message','tool_call: read_file','tool_call: write_file','assistant_response'];
                const w = [20, 10, 35, 25, 10][i] || 15;
                return (
                  <div key={i} style={{ display:'flex', alignItems:'center', gap:8, marginBottom:5 }}>
                    <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', width:140, flexShrink:0 }}>{spanNames[i] || `span_${i+1}`}</span>
                    <div style={{ flex:1, height:6, borderRadius:999, background:'rgba(255,255,255,0.06)', overflow:'hidden' }}>
                      <div style={{ height:'100%', borderRadius:999, background:'var(--accent)', width:`${w}%`, opacity:0.7, marginLeft:`${i*4}%` }}/>
                    </div>
                    <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', flexShrink:0 }}>{(w/100*parseFloat(trace.duration)).toFixed(1)}s</span>
                  </div>
                );
              })}
            </div>
            {trace.spans > 5 && <div style={{ fontSize:10, color:'var(--text-muted)', marginTop:4, fontFamily:'var(--font-mono)' }}>+{trace.spans-5} more spans · <a href="#" style={{ color:'var(--accent)' }}>Open in Langfuse →</a></div>}
          </div>
        </div>
      )}
    </div>
  );
}

function LogsScreen() {
  const [tab, setTab] = React.useState('requests');

  const totalTokens = MOCK_REQUESTS.reduce((s,r)=>s+r.tokens,0);
  const totalCost   = MOCK_REQUESTS.reduce((s,r)=>s+r.cost,0);
  const avgLatency  = Math.round(MOCK_REQUESTS.reduce((s,r)=>s+r.latencyMs,0)/MOCK_REQUESTS.length);
  const errorCount  = MOCK_ERRORS.filter(e=>!e.resolved).length;

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', overflow:'hidden' }}>
      {/* Header */}
      <div style={{ padding:'20px 20px 0', flexShrink:0 }}>
        <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:6 }}>Observability</div>
        <div style={{ display:'flex', alignItems:'flex-end', justifyContent:'space-between', flexWrap:'wrap', gap:10, marginBottom:14 }}>
          <div>
            <h1 style={{ fontSize:26, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', lineHeight:1.1, marginBottom:4 }}>Logs & Traces</h1>
            <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.5, maxWidth:480 }}>Request log, Langfuse traces, error feed. Every token, every millisecond.</p>
          </div>
          <div style={{ display:'flex', gap:10, flexWrap:'wrap' }}>
            {[
              { label:'Tokens today', value:totalTokens.toLocaleString(), color:'var(--accent)' },
              { label:'Avg latency',  value:`${avgLatency}ms`,            color:'#46d9a4' },
              { label:'Cost today',   value:`$${totalCost.toFixed(3)}`,   color:totalCost>0?'#ffbd66':'#46d9a4' },
              { label:'Open errors',  value:errorCount,                    color:errorCount>0?'#ff6b7d':'#46d9a4' },
            ].map(s => (
              <div key={s.label} style={{ padding:'8px 12px', borderRadius:12, background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.08)', textAlign:'center' }}>
                <div style={{ fontSize:18, fontWeight:800, color:s.color, letterSpacing:'-0.03em' }}>{s.value}</div>
                <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.10em' }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
        <div style={{ display:'flex', gap:4, marginBottom:0 }}>
          {['requests','traces','errors'].map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              padding:'7px 18px', borderRadius:'10px 10px 0 0', fontSize:12, fontWeight:600, cursor:'pointer',
              textTransform:'capitalize', transition:'all 0.15s',
              background:tab===t?'rgba(10,12,15,0.90)':'rgba(255,255,255,0.03)',
              border:`1px solid ${tab===t?'rgba(255,255,255,0.10)':'rgba(255,255,255,0.06)'}`,
              borderBottom:tab===t?'1px solid rgba(10,12,15,0.90)':'1px solid rgba(255,255,255,0.06)',
              color:tab===t?'#fff':'var(--text-muted)',
            }}>
              {t}
              {t === 'errors' && errorCount > 0 && <span style={{ marginLeft:6, fontSize:9, padding:'1px 5px', borderRadius:999, background:'rgba(255,107,125,0.20)', color:'#ff6b7d' }}>{errorCount}</span>}
            </button>
          ))}
        </div>
      </div>

      <div style={{ flex:1, overflow:'auto', background:'rgba(10,12,15,0.90)', borderTop:'1px solid rgba(255,255,255,0.08)' }}>
        {tab === 'requests' && (
          <>
            <div style={{ padding:'8px 16px', display:'flex', justifyContent:'space-between', borderBottom:'1px solid rgba(255,255,255,0.06)', fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.12em' }}>
              <span>Model · Provider · Session</span><span>Latency · Tokens · Cost</span>
            </div>
            {MOCK_REQUESTS.map(req => <RequestRow key={req.id} req={req}/>)}
          </>
        )}
        {tab === 'traces' && (
          <>
            <div style={{ padding:'8px 16px', display:'flex', justifyContent:'space-between', borderBottom:'1px solid rgba(255,255,255,0.06)', fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.12em' }}>
              <span>Trace name · Agent · Session</span><span>Duration · Tokens · Cost</span>
            </div>
            {MOCK_TRACES.map(trace => <TraceRow key={trace.id} trace={trace}/>)}
            <div style={{ padding:'12px 16px' }}>
              <a href="#" style={{ fontSize:12, color:'var(--accent)', fontFamily:'var(--font-mono)', display:'inline-flex', alignItems:'center', gap:5 }}>
                Open full trace explorer in Langfuse →
              </a>
            </div>
          </>
        )}
        {tab === 'errors' && (
          <div style={{ padding:'16px', display:'flex', flexDirection:'column', gap:10 }}>
            {MOCK_ERRORS.map(err => (
              <div key={err.id} style={{
                padding:'12px 14px', borderRadius:14,
                background:err.severity==='error'?'rgba(255,107,125,0.06)':'rgba(255,189,102,0.06)',
                border:`1px solid ${err.severity==='error'?'rgba(255,107,125,0.20)':'rgba(255,189,102,0.18)'}`,
                opacity:err.resolved?0.55:1,
              }}>
                <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
                  <span style={{ fontSize:11, color:err.severity==='error'?'#ff6b7d':'#ffbd66', fontFamily:'var(--font-mono)', letterSpacing:'0.10em', textTransform:'uppercase' }}>{err.severity}</span>
                  {err.resolved && <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'#46d9a4', padding:'1px 6px', borderRadius:999, background:'rgba(70,217,164,0.10)', border:'1px solid rgba(70,217,164,0.20)' }}>resolved</span>}
                  <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', marginLeft:'auto' }}>{err.count}× · {err.ts}</span>
                </div>
                <div style={{ fontSize:12, color:'var(--text-secondary)', lineHeight:1.5 }}>{err.msg}</div>
                {!err.resolved && (
                  <div style={{ display:'flex', gap:8, marginTop:10 }}>
                    <button style={{ padding:'5px 12px', borderRadius:8, fontSize:11, fontWeight:700, cursor:'pointer', background:'rgba(93,162,255,0.10)', border:'1px solid rgba(93,162,255,0.22)', color:'var(--accent)' }}>Fix automatically</button>
                    <button style={{ padding:'5px 12px', borderRadius:8, fontSize:11, cursor:'pointer', background:'transparent', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-muted)' }}>Mark resolved</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export { LogsScreen };
export default LogsScreen;
