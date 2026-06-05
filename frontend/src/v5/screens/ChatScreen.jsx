/* eslint-disable no-unused-vars -- some agent metadata fields are kept for future wiring */
import React from 'react';
import * as api from '../../api';


// chat.jsx — V5.0 Chat with history sidebar, agent picker, context assignment
//
// Wired to the real backend:
//   POST /api/chat/send         → direct chat (agent_mode=false) returns { session_id, response }
//                                 agent mode (agent_mode=true) returns 202 { job_id } to poll
//   GET  /api/chat/agent-jobs/:id → AgentJobSnapshot { status, phase, progress_events, result, error }
//   GET  /api/chat/sessions     → { sessions: [...] } for the history sidebar
//   GET  /api/chat/sessions/:id → full session with messages[]

const CHAT_PHASES = [
  { id:'planning',     label:'Planning',     color:'#7c9dff' },
  { id:'editing',      label:'Editing',      color:'#5da2ff' },
  { id:'execution',    label:'Executing',    color:'#5da2ff' },
  { id:'testing',      label:'Testing',      color:'#46d9a4' },
  { id:'verifying',    label:'Verifying',    color:'#ffbd66' },
  { id:'verification', label:'Verifying',    color:'#ffbd66' },
  { id:'resuming',     label:'Resuming',     color:'#c4b5fd' },
  { id:'pr',           label:'PR open',      color:'#46d9a4' },
];

const AVAILABLE_AGENTS = [
  { id:'auto',      name:'Auto-select',    icon:'◎', color:'#5da2ff',  desc:'Best agent for the task is chosen automatically' },
  { id:'dev',       name:'Dev Agent',      icon:'⚙', color:'#5da2ff',  desc:'Code, tests, PRs — git-aware coding assistant' },
  { id:'ceo',       name:'CEO Agent',      icon:'◎', color:'#c4b5fd',  desc:'Orchestration, planning, assessment' },
  { id:'security',  name:'Security Agent', icon:'🔒', color:'#ffbd66', desc:'CVE scans, secrets, SAST' },
  { id:'release',   name:'Release Agent',  icon:'◉', color:'#7c9dff',  desc:'Changelog, versioning, readiness' },
  { id:'commerce',  name:'Commerce Agent', icon:'🛍', color:'#46d9a4', desc:'Shopify, checkout, inventory' },
  { id:'content',   name:'Content Agent',  icon:'📄', color:'#c4b5fd', desc:'Contentful, SEO, publishing' },
  { id:'analytics', name:'Analytics Agent',icon:'📊', color:'#5da2ff', desc:'GA4, GTM, dashboards' },
];

const SUGGESTIONS = [
  'Explain how the agent pipeline modes work',
  'What does the model router decide between?',
  'Summarise the repo architecture',
  'How do I add a new provider?',
  'Draft a changelog entry for the last change',
];

// ── Helpers ───────────────────────────────────────────────────────────────────

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

// ── Sub-components ────────────────────────────────────────────────────────────

function AgentPicker({ selected, onSelect, onOpen, forceClose }) {
  const [open, setOpen] = React.useState(false);
  const ag = AVAILABLE_AGENTS.find(a => a.id === selected) || AVAILABLE_AGENTS[0];
  const btnRef = React.useRef(null);
  // Viewport-aware placement so the menu is never clipped off-screen.
  const [placement, setPlacement] = React.useState({ up: true, maxH: 360 });
  // Close when another dropdown opens
  React.useEffect(() => { if (forceClose) setOpen(false); }, [forceClose]);
  const toggle = () => { setOpen(o => {
    const next = !o;
    if (next) {
      const r = btnRef.current?.getBoundingClientRect();
      if (r) {
        const below = window.innerHeight - r.bottom;
        const above = r.top;
        const up = above >= below;
        setPlacement({ up, maxH: Math.max(180, Math.min(360, (up ? above : below) - 16)) });
      }
      if (onOpen) onOpen();
    }
    return next;
  }); };
  return (
    <div style={{ position:'relative' }}>
      <button ref={btnRef} onClick={toggle} style={{
        display:'flex', alignItems:'center', gap:6, padding:'4px 10px',
        borderRadius:999, border:`1px solid ${open?'rgba(93,162,255,0.40)':'rgba(255,255,255,0.12)'}`,
        background:open?'rgba(93,162,255,0.10)':'rgba(255,255,255,0.04)',
        cursor:'pointer', transition:'all 0.15s', fontSize:11, color:'var(--text-secondary)',
        fontFamily:'var(--font-mono)', letterSpacing:'0.08em', whiteSpace:'nowrap',
      }}>
        <span style={{ fontSize:13 }}>{ag.icon}</span>
        <span>{ag.name}</span>
        <span style={{ fontSize:9, color:'var(--text-muted)' }}>▾</span>
      </button>
      {open && (
        <>
          <div style={{ position:'fixed', inset:0, zIndex:40 }} onClick={()=>setOpen(false)}/>
          <div style={{
            position:'absolute', left:0, zIndex:50,
            ...(placement.up ? { bottom:'calc(100% + 6px)' } : { top:'calc(100% + 6px)' }),
            background:'rgba(12,15,20,0.98)', border:'1px solid rgba(255,255,255,0.12)',
            borderRadius:16, padding:8, minWidth:240, maxHeight:placement.maxH, overflowY:'auto',
            boxShadow:'0 16px 40px rgba(0,0,0,0.55)', animation:'fadeSlideUp 0.18s ease-out',
          }}>
            <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.12em', textTransform:'uppercase', padding:'4px 10px 8px' }}>Chat with</div>
            {AVAILABLE_AGENTS.map(a => (
              <button key={a.id} onClick={()=>{onSelect(a.id); setOpen(false);}} style={{
                display:'flex', alignItems:'flex-start', gap:9, width:'100%', padding:'8px 10px',
                borderRadius:10, border:'none', background:selected===a.id?'rgba(93,162,255,0.10)':'transparent',
                cursor:'pointer', textAlign:'left', transition:'background 0.12s',
              }}
              onMouseEnter={e=>{if(selected!==a.id)e.currentTarget.style.background='rgba(255,255,255,0.04)';}}
              onMouseLeave={e=>{if(selected!==a.id)e.currentTarget.style.background='transparent';}}>
                <span style={{ fontSize:15, flexShrink:0, marginTop:1 }}>{a.icon}</span>
                <div>
                  <div style={{ fontSize:12, fontWeight:600, color:selected===a.id?'#fff':'var(--text-secondary)' }}>{a.name}</div>
                  <div style={{ fontSize:11, color:'var(--text-muted)', lineHeight:1.4 }}>{a.desc}</div>
                </div>
                {selected===a.id && <span style={{ marginLeft:'auto', fontSize:11, color:'var(--accent)', flexShrink:0 }}>✓</span>}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

// ── Repo URL quick-add input ──────────────────────────────────────────────
function RepoUrlInput({ onAdd }) {
  const [open, setOpen] = React.useState(false);
  const [url, setUrl] = React.useState('');
  const handleAdd = () => {
    const trimmed = url.trim();
    if (!trimmed) return;
    onAdd(trimmed);
    setUrl('');
    setOpen(false);
  };
  if (!open) return (
    <button onClick={() => setOpen(true)} title="Add repo URL for code tasks" style={{
      display:'inline-flex', alignItems:'center', gap:3, padding:'2px 7px', borderRadius:999,
      background:'rgba(255,255,255,0.04)', border:'1px dashed rgba(255,255,255,0.15)',
      cursor:'pointer', fontSize:10, color:'var(--text-muted)', fontFamily:'var(--font-mono)', flexShrink:0,
    }}>
      <span>+</span><span>repo</span>
    </button>
  );
  return (
    <div style={{ display:'inline-flex', alignItems:'center', gap:4, flexShrink:0 }}>
      <input value={url} onChange={e => setUrl(e.target.value)} onKeyDown={e => { if (e.key==='Enter') handleAdd(); if (e.key==='Escape') setOpen(false); }}
        placeholder="github.com/org/repo"
        autoFocus
        style={{ width:160, padding:'3px 8px', borderRadius:8, background:'rgba(255,255,255,0.06)', border:'1px solid rgba(93,162,255,0.30)', color:'#fff', fontSize:10, fontFamily:'var(--font-mono)', outline:'none' }}/>
      <button onClick={handleAdd} style={{ padding:'2px 6px', borderRadius:6, background:'rgba(93,162,255,0.15)', border:'1px solid rgba(93,162,255,0.30)', color:'var(--accent)', fontSize:10, cursor:'pointer', fontFamily:'var(--font-mono)' }}>✓</button>
      <button onClick={() => setOpen(false)} style={{ padding:'0 4px', background:'none', border:'none', color:'var(--text-muted)', fontSize:10, cursor:'pointer' }}>✕</button>
    </div>
  );
}

function ContextChip({ chip, onRemove }) {
  return (
    <div style={{ display:'inline-flex', alignItems:'center', gap:5, padding:'4px 8px 4px 10px', borderRadius:999, border:'1px solid rgba(255,255,255,0.10)', background:'rgba(255,255,255,0.04)', fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-tertiary)' }}>
      <span style={{ fontSize:12 }}>{chip.icon}</span>
      <span>{chip.label}</span>
      <button onClick={()=>onRemove(chip.id)} style={{ background:'none', border:'none', cursor:'pointer', color:'var(--text-muted)', fontSize:11, display:'flex', alignItems:'center', padding:0 }}>✕</button>
    </div>
  );
}

// Live agent-job progress, driven by the real progress_events stream.
function AgentProgressPanel({ phase, elapsed, events = [], agent }) {
  const phaseObj = CHAT_PHASES.find(p => p.id === phase);
  const label = phaseObj ? phaseObj.label : (phase ? phase.charAt(0).toUpperCase() + phase.slice(1) : 'Working');
  const color = phaseObj ? phaseObj.color : '#7c9dff';
  return (
    <div style={{ margin:'8px 0', padding:'12px 14px', borderRadius:14, border:'1px solid rgba(93,162,255,0.15)', background:'rgba(93,162,255,0.04)', animation:'fadeSlideUp 0.3s ease-out', maxWidth:'84%' }}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:10 }}>
        <div style={{ display:'flex', alignItems:'center', gap:7 }}>
          <div style={{ width:7, height:7, borderRadius:'50%', background:color, animation:'pulse 1.5s infinite' }}/>
          <span style={{ fontSize:12, fontWeight:600, color:'#fff' }}>{label}</span>
        </div>
        <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{elapsed}s</span>
      </div>
      <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
        {events.length === 0 && (
          <div style={{ fontSize:11, color:'var(--text-muted)', fontFamily:'var(--font-mono)' }}>Agent started — waiting for the first update…</div>
        )}
        {events.map((ev, i) => (
          <div key={i} style={{ display:'flex', alignItems:'flex-start', gap:8 }}>
            <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:color, width:64, flexShrink:0, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{ev.phase || '·'}</span>
            <span style={{ fontSize:11, color:'var(--text-tertiary)', flex:1, lineHeight:1.5 }}>{ev.message || ''}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ msg }) {
  const isUser = msg.role === 'user';
  const ag = AVAILABLE_AGENTS.find(a => a.id === msg.agent) || AVAILABLE_AGENTS[1];
  if (msg.isError) {
    return (
      <div style={{ display:'flex', flexDirection:'column', alignItems:'flex-start', marginBottom:18, animation:'fadeSlideUp 0.28s ease-out' }}>
        <div style={{
          maxWidth:'84%', padding:'12px 16px', borderRadius:'4px 16px 16px 16px',
          background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.25)',
          fontSize:13, color:'#ff9aa6', lineHeight:1.6,
        }}>
          <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'#ff6b7d', letterSpacing:'0.1em', textTransform:'uppercase', marginBottom:5 }}>Error</div>
          {msg.content}
        </div>
      </div>
    );
  }
  return (
    <div style={{ display:'flex', flexDirection:'column', alignItems:isUser?'flex-end':'flex-start', marginBottom:18, animation:'fadeSlideUp 0.28s ease-out' }}>
      {!isUser && (
        <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:5 }}>
          <div style={{ width:20, height:20, borderRadius:7, background:`${ag.color}20`, border:`1px solid ${ag.color}35`, display:'flex', alignItems:'center', justifyContent:'center', fontSize:11 }}>{ag.icon}</div>
          <span style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{ag.name}</span>
        </div>
      )}
      <div style={{
        maxWidth:'84%', padding:isUser?'10px 14px':'12px 16px',
        borderRadius:isUser?'16px 16px 4px 16px':'4px 16px 16px 16px',
        background:isUser?'linear-gradient(135deg,rgba(93,162,255,0.18),rgba(93,162,255,0.10))':'rgba(255,255,255,0.04)',
        border:`1px solid ${isUser?'rgba(93,162,255,0.22)':'rgba(255,255,255,0.08)'}`,
        fontSize:14, color:isUser?'var(--text-primary)':'var(--text-secondary)', lineHeight:1.65,
        whiteSpace:'pre-wrap', wordBreak:'break-word',
      }}>
        {msg.content}
      </div>
    </div>
  );
}

function EmptyState({ onSuggest }) {
  return (
    <div style={{ flex:1, display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', padding:'40px 24px', gap:28 }}>
      <div style={{ textAlign:'center' }}>
        <div style={{ width:52, height:52, borderRadius:18, margin:'0 auto 16px', background:'linear-gradient(135deg,rgba(93,162,255,0.15),rgba(93,162,255,0.05))', border:'1px solid rgba(93,162,255,0.2)', display:'flex', alignItems:'center', justifyContent:'center' }}>
          <span style={{ fontSize:22 }}>◎</span>
        </div>
        <div style={{ fontSize:20, fontWeight:800, color:'#fff', letterSpacing:'-0.03em', marginBottom:8 }}>How can I help?</div>
        <div style={{ fontSize:14, color:'var(--text-tertiary)', maxWidth:360, lineHeight:1.6 }}>Ask a question about your stack, or switch on a specific agent (⚙ Dev, 🔒 Security…) to run a real task.</div>
      </div>
      <div style={{ display:'flex', flexDirection:'column', gap:7, width:'100%', maxWidth:400 }}>
        {SUGGESTIONS.map((s,i)=>(
          <button key={i} onClick={()=>onSuggest(s)} style={{ padding:'10px 14px', borderRadius:12, textAlign:'left', background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.08)', fontSize:13, color:'var(--text-tertiary)', cursor:'pointer', transition:'all 0.15s', display:'flex', alignItems:'center', gap:9 }}
            onMouseEnter={e=>{e.currentTarget.style.background='rgba(93,162,255,0.06)';e.currentTarget.style.borderColor='rgba(93,162,255,0.20)';e.currentTarget.style.color='var(--text-secondary)';}}
            onMouseLeave={e=>{e.currentTarget.style.background='rgba(255,255,255,0.03)';e.currentTarget.style.borderColor='rgba(255,255,255,0.08)';e.currentTarget.style.color='var(--text-tertiary)';}}>
            <span style={{ color:'rgba(93,162,255,0.5)', flexShrink:0 }}>›</span>{s}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── History sidebar ───────────────────────────────────────────────────────────
function HistorySidebar({ sessions, loading, activeId, onSelect, onClose }) {
  return (
    <div style={{
      width:'min(280px, 85vw)', height:'100%', borderRight:'1px solid rgba(255,255,255,0.08)',
      background:'rgba(6,8,12,0.96)', display:'flex', flexDirection:'column', flexShrink:0,
    }}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'14px 16px 10px', borderBottom:'1px solid rgba(255,255,255,0.07)' }}>
        <span style={{ fontSize:13, fontWeight:700, color:'#fff' }}>Chat History</span>
        <button onClick={onClose} style={{ width:26, height:26, borderRadius:7, display:'flex', alignItems:'center', justifyContent:'center', background:'rgba(255,255,255,0.05)', border:'none', cursor:'pointer', color:'var(--text-muted)', fontSize:12 }}>✕</button>
      </div>
      <button onClick={()=>{ onSelect(null); onClose(); }} style={{ margin:'10px 10px 0', padding:'9px 14px', borderRadius:12, background:'rgba(93,162,255,0.12)', border:'1px solid rgba(93,162,255,0.25)', color:'var(--accent)', fontSize:12, fontWeight:700, cursor:'pointer', display:'flex', alignItems:'center', gap:7 }}>
        <span>＋</span> New chat
      </button>
      <div style={{ flex:1, overflowY:'auto', padding:'10px 8px' }} className="scrollbar-hide">
        <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.12em', textTransform:'uppercase', padding:'2px 8px 6px' }}>Recent</div>
        {loading && (
          <div style={{ fontSize:11, color:'var(--text-muted)', padding:'8px 10px', fontFamily:'var(--font-mono)' }}>Loading…</div>
        )}
        {!loading && sessions.length === 0 && (
          <div style={{ fontSize:11, color:'var(--text-muted)', padding:'8px 10px', lineHeight:1.5 }}>No conversations yet. Send a message to start one.</div>
        )}
        {!loading && sessions.map((s) => {
          const id = s._id || s.id;
          const active = activeId === id;
          return (
            <button key={id} onClick={()=>{ onSelect(s); onClose(); }} style={{
              display:'block', width:'100%', padding:'9px 10px', borderRadius:11, textAlign:'left', cursor:'pointer',
              background:active?'rgba(93,162,255,0.10)':'transparent',
              border:`1px solid ${active?'rgba(93,162,255,0.22)':'transparent'}`,
              marginBottom:3, transition:'all 0.15s',
            }}
            onMouseEnter={e=>{if(!active){e.currentTarget.style.background='rgba(255,255,255,0.04)';e.currentTarget.style.borderColor='rgba(255,255,255,0.08)';}}}
            onMouseLeave={e=>{if(!active){e.currentTarget.style.background='transparent';e.currentTarget.style.borderColor='transparent';}}}>
              <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:3 }}>
                <span style={{ fontSize:12 }}>◎</span>
                <span style={{ fontSize:12, fontWeight:600, color:active?'#fff':'var(--text-secondary)', flex:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{s.title || 'Untitled chat'}</span>
                <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', flexShrink:0 }}>{relTime(s.updated_at || s.created_at)}</span>
              </div>
              {s.model && <div style={{ fontSize:11, color:'var(--text-muted)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', paddingLeft:18 }}>{s.model}</div>}
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Main ChatScreen ───────────────────────────────────────────────────────────
function ModelPicker({ selected, onSelect, onOpen, forceClose }) {
  const [open, setOpen] = React.useState(false);
  const [providers, setProviders] = React.useState([]);
  const [models, setModels] = React.useState([]);
  const [loading, setLoading] = React.useState(false);
  const [selProvider, setSelProvider] = React.useState(selected?.provider || null);
  const btnRef = React.useRef(null);
  // Viewport-aware placement so the menu never gets clipped off-screen (it used to
  // always open downward and get cut off near the bottom of the screen).
  const [placement, setPlacement] = React.useState({ up: false, maxH: 360 });
  // Close when another dropdown opens
  React.useEffect(() => { if (forceClose) setOpen(false); }, [forceClose]);
  // Reset selProvider when dropdown opens to prevent stale state
  const toggle = () => {
    setOpen(o => {
      const next = !o;
      if (next) {
        setSelProvider(selected?.provider || null);
        const r = btnRef.current?.getBoundingClientRect();
        if (r) {
          const below = window.innerHeight - r.bottom;
          const above = r.top;
          const up = below < 340 && above > below;
          setPlacement({ up, maxH: Math.max(180, Math.min(360, (up ? above : below) - 16)) });
        }
        if (onOpen) onOpen();
      }
      return next;
    });
  };

  React.useEffect(() => {
    let alive = true;
    api.listProviders().then(({ data }) => {
      if (!alive) return;
      const list = data?.providers || [];
      setProviders(list.filter(p => p.status === 'configured' || p.is_default));
    }).catch(() => {});
    return () => { alive = false; };
  }, []);

  React.useEffect(() => {
    if (!selProvider) { setModels([]); return; }
    let alive = true;
    setLoading(true);
    api.listProviderModels(selProvider).then(({ data }) => {
      if (!alive) return;
      setModels(data?.models || []);
    }).catch(() => { if (alive) setModels([]); }).finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [selProvider]);

  const currentLabel = selected?.model ? `${selected.model.split('/').pop()} (${selected.provider || 'auto'})` : 'Auto-select';

  return (
    <div style={{ position:'relative' }}>
      <button ref={btnRef} onClick={toggle} style={{
        display:'flex', alignItems:'center', gap:6, padding:'4px 10px',
        borderRadius:999, border:`1px solid ${open ? 'rgba(93,162,255,0.40)' : 'rgba(255,255,255,0.12)'}`,
        background: open ? 'rgba(93,162,255,0.10)' : 'rgba(255,255,255,0.04)',
        cursor:'pointer', transition:'all 0.15s', fontSize:11, color:'var(--text-secondary)',
        fontFamily:'var(--font-mono)', letterSpacing:'0.08em', whiteSpace:'nowrap',
      }}>
        <span style={{ fontSize:13 }}>🤖</span>
        <span>{currentLabel}</span>
        <span style={{ fontSize:9, color:'var(--text-muted)' }}>▾</span>
      </button>
      {open && (
        <>
          <div style={{ position:'fixed', inset:0, zIndex:40 }} onClick={() => setOpen(false)} />
          <div style={{
            position:'absolute', left:0, zIndex:50,
            ...(placement.up ? { bottom:'calc(100% + 6px)' } : { top:'calc(100% + 6px)' }),
            background:'rgba(12,15,20,0.98)', border:'1px solid rgba(255,255,255,0.12)',
            borderRadius:16, padding:8, minWidth:280, maxHeight:placement.maxH, overflowY:'auto',
            boxShadow:'0 16px 40px rgba(0,0,0,0.55)', animation:'fadeSlideUp 0.18s ease-out',
          }}>
            <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.12em', textTransform:'uppercase', padding:'4px 10px 8px' }}>Model & Provider</div>
            <button onClick={() => { onSelect(null); setSelProvider(null); setOpen(false); }} style={{
              display:'flex', alignItems:'center', gap:9, width:'100%', padding:'8px 10px',
              borderRadius:10, border:'none', background: !selected?.model ? 'rgba(93,162,255,0.10)' : 'transparent',
              cursor:'pointer', textAlign:'left',
            }}>
              <span style={{ fontSize:13 }}>◎</span>
              <div style={{ fontSize:12, fontWeight:600, color: !selected?.model ? '#fff' : 'var(--text-secondary)' }}>Auto-select (backend picks best model)</div>
            </button>
            <div style={{ height:1, background:'rgba(255,255,255,0.08)', margin:'6px 0' }} />
            <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.08em', padding:'4px 10px 6px' }}>Provider</div>
            {providers.map(p => (
              <button key={p.provider_id} onClick={() => { setSelProvider(p.provider_id); }} style={{
                display:'flex', alignItems:'center', gap:8, width:'100%', padding:'7px 10px',
                borderRadius:8, border:'none',
                background: selProvider === p.provider_id ? 'rgba(93,162,255,0.10)' : 'transparent',
                cursor:'pointer', textAlign:'left', fontSize:12, color: selProvider === p.provider_id ? '#fff' : 'var(--text-secondary)',
              }}>
                <span style={{ fontSize:13 }}>{selProvider === p.provider_id ? '▼' : '▸'}</span>
                <span>{p.name || p.provider_id}</span>
              </button>
            ))}
            {selProvider && (
              <>
                <div style={{ height:1, background:'rgba(255,255,255,0.06)', margin:'4px 10px' }} />
                <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.08em', padding:'2px 10px 6px' }}>Models for {providers.find(p=>p.provider_id===selProvider)?.name || selProvider}</div>
                {loading && <div style={{ padding:'6px 16px', fontSize:11, color:'var(--text-muted)' }}>Loading models…</div>}
                {!loading && models.length === 0 && (
                  <button onClick={() => { onSelect({ provider: selProvider, model: '' }); setOpen(false); }} style={{
                    display:'block', width:'100%', padding:'7px 10px 7px 20px', borderRadius:8, border:'none',
                    background: selected?.provider === selProvider && !selected?.model ? 'rgba(93,162,255,0.10)' : 'transparent',
                    cursor:'pointer', textAlign:'left', fontSize:11, fontFamily:'var(--font-mono)',
                    color: selected?.provider === selProvider && !selected?.model ? '#fff' : 'var(--text-tertiary)',
                  }}>Default model</button>
                )}
                {!loading && models.slice(0, 10).map(m => (
                  <button key={m} onClick={() => { onSelect({ provider: selProvider, model: m }); setOpen(false); }} style={{
                    display:'block', width:'100%', padding:'6px 10px 6px 20px', borderRadius:8, border:'none',
                    background: selected?.model === m && selected?.provider === selProvider ? 'rgba(93,162,255,0.10)' : 'transparent',
                    cursor:'pointer', textAlign:'left', fontSize:11, fontFamily:'var(--font-mono)',
                    color: selected?.model === m && selected?.provider === selProvider ? '#fff' : 'var(--text-tertiary)',
                  }}>{m}</button>
                ))}
              </>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function ChatScreen() {
  const [input,       setInput]        = React.useState('');
  const [messages,    setMessages]     = React.useState([]);
  const [sending,     setSending]      = React.useState(false);
  const [agentPhase,  setPhase]        = React.useState(null);
  const [elapsed,     setElapsed]      = React.useState(0);
  const [progressEvents, setProgressEvents] = React.useState([]);
  const [agent,       setAgent]        = React.useState('auto');
  const [agentMode,   setAgentMode]    = React.useState(false);
  const [selectedModel, setSelectedModel] = React.useState(null); // { provider, model } or null
  const [chips,       setChips]        = React.useState([]);
  const [showHistory, setShowHistory]  = React.useState(false);
  const [sessions,    setSessions]     = React.useState([]);
  const [historyLoading, setHistoryLoading] = React.useState(false);
  const [sessionId,   setSessionId]    = React.useState(null);
  const [openDropdown, setOpenDropdown] = React.useState(null); // 'agent' | 'model' | null
  const messagesEndRef = React.useRef(null);
  const textareaRef    = React.useRef(null);
  const mountedRef     = React.useRef(true);

  // Load context chips from localStorage (company, wiki, sources, repo)
  React.useEffect(() => {
    const initial = [];
    try {
      const companyId = localStorage.getItem('v5_company_id');
      const companyName = localStorage.getItem('v5_company_name');
      if (companyId && companyName) initial.push({ id:'company', icon:'🏢', label:companyName });
      const savedRepoUrl = localStorage.getItem('v5_chat_repo_url');
      if (savedRepoUrl) initial.push({ id:'repo', icon:'📁', label: savedRepoUrl.replace(/^https?:\/\//i,'').replace(/^github\.com\//,'').replace(/^gitlab\.com\//,'').replace(/^bitbucket\.org\//,''), _rawUrl: savedRepoUrl });
    } catch { /* ignore */ }
    setChips(initial);
  }, []);

  const currentAgent = AVAILABLE_AGENTS.find(a=>a.id===agent)||AVAILABLE_AGENTS[1];
  // Picking a specific (non-auto) agent implies agent mode; "Auto-select" leaves
  // the explicit toggle in charge so the backend can auto-route the task.
  const selectAgent = (id) => { setAgent(id); if (id !== 'auto') setAgentMode(true); };

  React.useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  const loadSessions = React.useCallback(async () => {
    setHistoryLoading(true);
    try {
      const { data } = await api.listSessions();
      if (mountedRef.current) setSessions(Array.isArray(data?.sessions) ? data.sessions : []);
    } catch {
      if (mountedRef.current) setSessions([]);
    } finally {
      if (mountedRef.current) setHistoryLoading(false);
    }
  }, []);

  React.useEffect(() => { loadSessions(); }, [loadSessions]);

  React.useEffect(() => {
    if (messagesEndRef.current) {
      const el = messagesEndRef.current;
      el.parentElement.scrollTop = el.parentElement.scrollHeight;
    }
  }, [messages, sending, progressEvents]);

  // Poll a queued/running agent job until it reaches a terminal state.
  const pollAgentJob = async (jobId, selectedAg) => {
    const start = Date.now();
    const MAX_ATTEMPTS = 240; // ~6 min ceiling at 1.5s/poll
    for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
      await new Promise((r) => setTimeout(r, 1500));
      if (!mountedRef.current) return;
      let snap;
      try {
        const { data } = await api.getAgentChatJob(jobId);
        snap = data;
      } catch (err) {
        if (!mountedRef.current) return;
        setSending(false); setPhase(null);
        setMessages((prev) => [...prev, { role:'assistant', agent:selectedAg, content:'Lost connection to the agent job. It may still be running on the server.', isError:true }]);
        return;
      }
      if (!mountedRef.current) return;
      setPhase(snap.phase || 'running');
      setElapsed(Math.round((Date.now() - start) / 1000));
      setProgressEvents(Array.isArray(snap.progress_events) ? snap.progress_events : []);
      if (['succeeded', 'failed', 'cancelled'].includes(snap.status)) {
        setSending(false); setPhase(null); setProgressEvents([]);
        if (snap.status === 'succeeded') {
          setMessages((prev) => [...prev, { role:'assistant', agent:selectedAg, content: snap.result?.response || 'The agent finished but returned no message.' }]);
        } else if (snap.status === 'cancelled') {
          setMessages((prev) => [...prev, { role:'assistant', agent:selectedAg, content:'Agent job was cancelled.', isError:true }]);
        } else {
          setMessages((prev) => [...prev, { role:'assistant', agent:selectedAg, content: snap.error?.message || 'The agent job failed.', isError:true }]);
        }
        loadSessions();
        return;
      }
    }
    if (!mountedRef.current) return;
    setSending(false); setPhase(null); setProgressEvents([]);
    setMessages((prev) => [...prev, { role:'assistant', agent:selectedAg, content:'The agent job is taking longer than expected. Check the Tasks/Agents view for its status.', isError:true }]);
  };

  const handleSend = async () => {
    if (!input.trim() || sending) return;
    const text = input.trim();
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
    const selectedAg = agent === 'auto' ? 'dev' : agent;
    setMessages((prev) => [...prev, { role:'user', content:text }]);
    setSending(true);
    setProgressEvents([]);
    setElapsed(0);
    setPhase(agentMode ? 'planning' : null);
    try {
      // Build context payload from active chips (company, wiki, sources, repo)
      const repoChip = chips.find(c => c.id === 'repo');
      const repoUrl = repoChip?._rawUrl || (localStorage.getItem('v5_chat_repo_url') || null);
      const contextPayload = chips.length > 0 ? {
        company_id: localStorage.getItem('v5_company_id') || null,
        company_name: chips.find(c => c.id === 'company')?.label || localStorage.getItem('v5_company_name') || null,
        context_labels: chips.map(c => c.label),
      } : null;
      const { data } = await api.chatSend(text, sessionId, selectedModel?.model || null, selectedModel?.provider || null, null, agentMode, false, contextPayload, repoUrl);
      if (!mountedRef.current) return;
      if (data?.session_id) setSessionId(data.session_id);
      if (data?.job_id) {
        // Agent Mode: backend queued a job (HTTP 202). Poll for progress + result.
        await pollAgentJob(data.job_id, selectedAg);
      } else {
        // Direct chat: response is returned inline.
        setSending(false); setPhase(null);
        setMessages((prev) => [...prev, { role:'assistant', agent:selectedAg, content: data?.response || 'No response.' }]);
        loadSessions();
      }
    } catch (err) {
      if (!mountedRef.current) return;
      setSending(false); setPhase(null); setProgressEvents([]);
      setMessages((prev) => [...prev, { role:'assistant', agent:selectedAg, content: (api.fmtErr(err?.response?.data?.detail) || err?.message || 'Something went wrong.'), isError:true }]);
    }
  };

  const handleKey = e => { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } };
  const adjustTextarea = () => {
    if (!textareaRef.current) return;
    textareaRef.current.style.height = '0';
    textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight,160)+'px';
  };

  const loadHistoryChat = async (s) => {
    if (sending) return;
    if (!s) { setMessages([]); setSessionId(null); return; }
    const id = s._id || s.id;
    setSessionId(id);
    setMessages([]);
    try {
      const { data } = await api.getSession(id);
      if (!mountedRef.current) return;
      const msgs = (Array.isArray(data?.messages) ? data.messages : [])
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => ({
          role: m.role,
          content: m.content,
          agent: m.role === 'assistant' ? (agent === 'auto' ? 'dev' : agent) : undefined,
        }));
      setMessages(msgs);
    } catch {
      if (!mountedRef.current) return;
      setMessages([{ role:'assistant', content:'Could not load this conversation.', isError:true }]);
    }
  };

  return (
    <div style={{ display:'flex', height:'100%', background:'var(--bg-base)' }}>
      {/* History sidebar */}
      {showHistory && (
        <HistorySidebar
          sessions={sessions}
          loading={historyLoading}
          activeId={sessionId}
          onSelect={loadHistoryChat}
          onClose={()=>setShowHistory(false)}
        />
      )}

      <div style={{ flex:1, display:'flex', flexDirection:'column', minWidth:0 }}>
        {/* Top bar: history toggle + agent picker + context */}
        <div style={{ display:'flex', alignItems:'center', gap:8, padding:'9px 14px', borderBottom:'1px solid rgba(255,255,255,0.06)', flexShrink:0, flexWrap:'wrap', rowGap:6 }}>
          {/* History button */}
          <button onClick={()=>setShowHistory(o=>!o)} style={{
            display:'flex', alignItems:'center', gap:5, padding:'5px 11px', borderRadius:999,
            background:showHistory?'rgba(93,162,255,0.12)':'rgba(255,255,255,0.04)',
            border:`1px solid ${showHistory?'rgba(93,162,255,0.30)':'rgba(255,255,255,0.10)'}`,
            cursor:'pointer', transition:'all 0.15s', fontSize:11, color:showHistory?'var(--accent)':'var(--text-muted)', fontFamily:'var(--font-mono)', letterSpacing:'0.08em', flexShrink:0,
          }}>
            <span>⏱</span><span>History</span>
          </button>

          <div style={{ width:1, height:16, background:'rgba(255,255,255,0.10)', flexShrink:0 }}/>

          {/* Agent picker */}
          <AgentPicker selected={agent} onSelect={selectAgent} onOpen={() => setOpenDropdown('agent')} forceClose={openDropdown === 'model'}/>

          <div style={{ width:1, height:16, background:'rgba(255,255,255,0.10)', flexShrink:0 }}/>

          {/* Model picker */}
          <ModelPicker selected={selectedModel} onSelect={setSelectedModel} onOpen={() => setOpenDropdown('model')} forceClose={openDropdown === 'agent'}/>

          <div style={{ width:1, height:16, background:'rgba(255,255,255,0.10)', flexShrink:0 }}/>

          {/* Agent Mode toggle — explicit ON/OFF for running real tasks */}
          <button onClick={()=>setAgentMode(o=>!o)} title={agentMode ? 'Agent Mode is ON — messages run as real tasks' : 'Agent Mode is OFF — direct chat'} style={{
            display:'flex', alignItems:'center', gap:7, padding:'5px 11px', borderRadius:999, flexShrink:0, cursor:'pointer', transition:'all 0.15s',
            background:agentMode?'rgba(70,217,164,0.12)':'rgba(255,255,255,0.04)',
            border:`1px solid ${agentMode?'rgba(70,217,164,0.35)':'rgba(255,255,255,0.10)'}`,
            color:agentMode?'var(--success)':'var(--text-muted)', fontSize:11, fontFamily:'var(--font-mono)', letterSpacing:'0.08em',
          }}>
            <span style={{ width:26, height:15, borderRadius:999, padding:2, background:agentMode?'var(--success)':'rgba(255,255,255,0.12)', display:'flex', alignItems:'center', justifyContent:agentMode?'flex-end':'flex-start', transition:'all 0.2s' }}>
              <span style={{ width:11, height:11, borderRadius:'50%', background:'#fff' }}/>
            </span>
            <span>Agent Mode {agentMode ? 'ON' : 'OFF'}</span>
          </button>

          <div style={{ width:1, height:16, background:'rgba(255,255,255,0.10)', flexShrink:0 }}/>

          {/* Context chips */}
          <div style={{ display:'flex', alignItems:'center', gap:5, overflowX:'auto', flex:1 }} className="scrollbar-hide">
            <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', flexShrink:0 }}>Context:</span>
            {chips.map(chip => <ContextChip key={chip.id} chip={chip} onRemove={id=>{
              setChips(p=>p.filter(c=>c.id!==id));
              if (id === 'repo') { try { localStorage.removeItem('v5_chat_repo_url'); } catch {} }
            }}/>)}
            {chips.length === 0 && <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', flexShrink:0 }}>none</span>}
            {/* Repo URL quick-add input */}
            <RepoUrlInput onAdd={(repoUrl) => {
              try { localStorage.setItem('v5_chat_repo_url', repoUrl); } catch {}
              const shortLabel = repoUrl.replace(/^https?:\/\//i, '').replace(/^github\.com\//, '').replace(/^gitlab\.com\//, '').replace(/^bitbucket\.org\//, '');
              setChips(p => [...p.filter(c => c.id !== 'repo'), { id:'repo', icon:'📁', label: shortLabel, _rawUrl: repoUrl }]);
            }}/>
          </div>
        </div>

        {/* Agent context tip */}
        {agentMode && (
          <div style={{ margin:'8px 14px 0', padding:'7px 12px', borderRadius:10, background:`${currentAgent.color}08`, border:`1px solid ${currentAgent.color}20`, fontSize:12, color:'var(--text-tertiary)', display:'flex', alignItems:'center', gap:8 }}>
            <span style={{ fontSize:14 }}>{agent === 'auto' ? '◎' : currentAgent.icon}</span>
            <span>Agent Mode <strong style={{ color:'var(--success)' }}>ON</strong> — <strong style={{ color:'#fff' }}>{agent === 'auto' ? 'the best agent' : currentAgent.name}</strong> will plan and run a real task. <button style={{ background:'none', border:'none', cursor:'pointer', color:'var(--accent)', fontSize:12 }} onClick={()=>setAgentMode(false)}>Switch to direct chat →</button></span>
          </div>
        )}

        {/* Messages */}
        <div style={{ flex:1, overflowY:'auto', padding:'18px 16px 8px' }} className="scrollbar-hide">
          {messages.length === 0 && !sending
            ? <EmptyState onSuggest={t=>{setInput(t); textareaRef.current?.focus();}}/>
            : <>
              {messages.map((msg,i)=>(
                <MessageBubble key={i} msg={msg}/>
              ))}
              {sending && agentPhase && (
                <AgentProgressPanel phase={agentPhase} elapsed={elapsed} events={progressEvents} agent={currentAgent}/>
              )}
              {sending && !agentPhase && (
                <div style={{ display:'flex', alignItems:'flex-start', gap:8, marginBottom:18, animation:'fadeSlideUp 0.2s ease-out' }}>
                  <div style={{ width:20, height:20, borderRadius:7, background:`${currentAgent.color}20`, display:'flex', alignItems:'center', justifyContent:'center', fontSize:11, flexShrink:0, marginTop:4 }}>{currentAgent.icon}</div>
                  <div style={{ padding:'10px 14px', borderRadius:'4px 16px 16px 16px', background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.08)' }}>
                    <div style={{ display:'flex', gap:4 }}>
                      {[0,1,2].map(i=><div key={i} style={{ width:6, height:6, borderRadius:'50%', background:'var(--accent)', animation:`blink 1.4s ease-in-out ${i*0.2}s infinite` }}/>)}
                    </div>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef}/>
            </>
          }
        </div>

        {/* Composer */}
        <div style={{ padding:'10px 14px 12px', borderTop:'1px solid rgba(255,255,255,0.08)', background:'rgba(8,10,14,0.7)', backdropFilter:'blur(12px)', flexShrink:0 }}>
          <div style={{ display:'flex', alignItems:'flex-end', gap:9, padding:'10px 14px', background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.10)', borderRadius:18 }}>
            <textarea ref={textareaRef} value={input}
              onChange={e=>{setInput(e.target.value);adjustTextarea();}}
              onKeyDown={handleKey}
              placeholder={!agentMode ? 'Ask anything…' : (agent==='auto' ? 'Describe a task to run…' : `Tell ${currentAgent.name} what to do…`)}
              rows={1}
              style={{ flex:1, background:'transparent', border:'none', outline:'none', resize:'none', fontSize:14, color:'var(--text-primary)', fontFamily:'var(--font-main)', lineHeight:1.6, minHeight:24, padding:0, overflow:'hidden' }}/>
            <button onClick={handleSend} disabled={!input.trim()||sending} style={{ width:34, height:34, borderRadius:10, flexShrink:0, background:input.trim()&&!sending?'var(--accent)':'rgba(255,255,255,0.08)', border:'none', cursor:input.trim()&&!sending?'pointer':'not-allowed', display:'flex', alignItems:'center', justifyContent:'center', transition:'all 0.2s', boxShadow:input.trim()&&!sending?'0 4px 12px rgba(93,162,255,0.25)':'none' }}>
              {sending
                ? <div style={{ width:14,height:14,borderRadius:'50%',border:'2px solid rgba(255,255,255,0.3)',borderTopColor:'#fff',animation:'spin 0.8s linear infinite' }}/>
                : <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={input.trim()?'#06111f':'var(--text-muted)'} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
              }
            </button>
          </div>
          <div style={{ display:'flex', justifyContent:'space-between', marginTop:6 }}>
            <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>
              {!agentMode ? 'Direct chat · toggle Agent Mode to run a real task' : `Agent Mode · ${agent === 'auto' ? 'auto-select' : currentAgent.name}`}
            </span>
            <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>⌘↵</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export { ChatScreen };
export default ChatScreen;
