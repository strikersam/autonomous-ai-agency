/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';


// chat.jsx — V5.0 Chat with history sidebar, agent picker, context assignment

const CHAT_PHASES = [
  { id:'planning',  label:'Planning',  icon:'◎', color:'#7c9dff' },
  { id:'editing',   label:'Editing',   icon:'⊕', color:'#5da2ff' },
  { id:'testing',   label:'Testing',   icon:'⊙', color:'#46d9a4' },
  { id:'verifying', label:'Verifying', icon:'◈', color:'#ffbd66' },
  { id:'pr',        label:'PR open',   icon:'◉', color:'#46d9a4' },
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

const CONTEXT_CHIPS_DEFAULT = [
  { id:'co-1', label:'acme-corp', icon:'🏢', type:'company' },
  { id:'co-2', label:'main',      icon:'⎇', type:'branch' },
  { id:'co-3', label:'sprint-42', icon:'◈', type:'task' },
];

const CHAT_HISTORY = [
  { id:'h-1', title:'Fix checkout null-pointer',       preview:'Done. PR #1842 opened.', ts:'2m ago',  agent:'dev',      screen:'final' },
  { id:'h-2', title:'Security scan auth module',        preview:'Bandit clean. 0 issues.', ts:'8m ago',  agent:'security', screen:'final' },
  { id:'h-3', title:'Explain agent pipeline modes',     preview:'Here is how each mode works…', ts:'1h ago',  agent:'ceo',      screen:'final' },
  { id:'h-4', title:'Contentful publishing workflow',   preview:'I can automate that for you.', ts:'3h ago',  agent:'content',  screen:'final' },
  { id:'h-5', title:'Cart abandonment analysis',        preview:'Based on your GA4 data…', ts:'1d ago',  agent:'analytics',screen:'final' },
  { id:'h-6', title:'Dependency audit v5.0',            preview:'14 safe upgrades found.', ts:'3d ago',  agent:'release',  screen:'final' },
];

const SUGGESTIONS = [
  'Fix the failing tests and open a PR',
  'Review the last 5 agent decisions',
  'What\'s blocking the current sprint?',
  'Scan for security issues in the auth module',
  'Run the weekly dependency audit',
];

const SAMPLE_RESULT = {
  summary:'Fixed 3 failing tests in `cart/checkout.test.ts` by correcting a null-check on the discount coupon field. All 47 suite tests now pass.',
  diff:['- if (coupon.code) {', '+ if (coupon && coupon.code) {'],
  pr:{ title:'fix: null-check coupon in checkout', url:'#pr-1842', number:'#1842', branch:'fix/checkout-null-coupon' },
  testRun:{ passed:47, failed:0, duration:'4.2s' },
};

// ── Sub-components ────────────────────────────────────────────────────────────

function AgentPicker({ selected, onSelect }) {
  const [open, setOpen] = React.useState(false);
  const ag = AVAILABLE_AGENTS.find(a => a.id === selected) || AVAILABLE_AGENTS[0];
  return (
    <div style={{ position:'relative' }}>
      <button onClick={()=>setOpen(o=>!o)} style={{
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
            position:'absolute', bottom:'calc(100% + 6px)', left:0, zIndex:50,
            background:'rgba(12,15,20,0.98)', border:'1px solid rgba(255,255,255,0.12)',
            borderRadius:16, padding:8, minWidth:240,
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

function ContextChip({ chip, onRemove }) {
  return (
    <div style={{ display:'inline-flex', alignItems:'center', gap:5, padding:'4px 8px 4px 10px', borderRadius:999, border:'1px solid rgba(255,255,255,0.10)', background:'rgba(255,255,255,0.04)', fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-tertiary)' }}>
      <span style={{ fontSize:12 }}>{chip.icon}</span>
      <span>{chip.label}</span>
      <button onClick={()=>onRemove(chip.id)} style={{ background:'none', border:'none', cursor:'pointer', color:'var(--text-muted)', fontSize:11, display:'flex', alignItems:'center', padding:0 }}>✕</button>
    </div>
  );
}

function AgentProgressPanel({ phase, elapsed }) {
  const phaseObj = CHAT_PHASES.find(p=>p.id===phase)||CHAT_PHASES[0];
  const phaseIdx = CHAT_PHASES.findIndex(p=>p.id===phase);
  const progress = ((phaseIdx+1)/CHAT_PHASES.length)*100;
  const events = [
    { time:'0s',  text:'Checked out branch fix/checkout-null-coupon', ok:true },
    { time:'2s',  text:'Ran pytest cart/ — 3 failures found',          ok:true },
    { time:'8s',  text:'Identified root cause in checkout.test.ts:142',ok:true },
    { time:'12s', text:'Applied null-check fix to CartService.discount',ok:phaseIdx>1 },
    { time:'18s', text:'Re-running test suite…',                       ok:false, pending:phaseIdx<=2 },
  ];
  return (
    <div style={{ margin:'8px 0', padding:'12px 14px', borderRadius:14, border:'1px solid rgba(93,162,255,0.15)', background:'rgba(93,162,255,0.04)', animation:'fadeSlideUp 0.3s ease-out' }}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:8 }}>
        <div style={{ display:'flex', alignItems:'center', gap:7 }}>
          <div style={{ width:7, height:7, borderRadius:'50%', background:phaseObj.color, animation:'pulse 1.5s infinite' }}/>
          <span style={{ fontSize:12, fontWeight:600, color:'#fff' }}>{phaseObj.label}</span>
        </div>
        <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{elapsed}s</span>
      </div>
      <div style={{ height:3, borderRadius:999, background:'rgba(255,255,255,0.08)', marginBottom:10 }}>
        <div style={{ height:'100%', borderRadius:999, background:`linear-gradient(90deg,var(--accent),${phaseObj.color})`, width:`${progress}%`, transition:'width 0.6s ease' }}/>
      </div>
      <div style={{ display:'flex', alignItems:'center', gap:4, flexWrap:'wrap', marginBottom:10 }}>
        {CHAT_PHASES.map((p,i)=>{
          const done=i<phaseIdx; const active=i===phaseIdx;
          return <React.Fragment key={p.id}>
            <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:done?'#46d9a4':active?p.color:'var(--text-muted)', padding:'2px 7px', borderRadius:5, background:active?`${p.color}12`:'transparent', border:active?`1px solid ${p.color}30`:'1px solid transparent' }}>
              {done?'✓ ':''}{p.label}
            </span>
            {i<CHAT_PHASES.length-1 && <span style={{ color:'rgba(255,255,255,0.15)', fontSize:10 }}>›</span>}
          </React.Fragment>;
        })}
      </div>
      <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
        {events.map((ev,i)=>(
          <div key={i} style={{ display:'flex', alignItems:'flex-start', gap:7, opacity:ev.pending?0.4:1 }}>
            <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', width:22, flexShrink:0 }}>{ev.time}</span>
            <span style={{ fontSize:11, color:'var(--text-tertiary)', flex:1 }}>{ev.text}</span>
            {ev.ok&&!ev.pending && <span style={{ fontSize:10, color:'#46d9a4' }}>✓</span>}
            {ev.pending && <span style={{ fontSize:10, color:'var(--text-muted)', animation:'blink 1.2s infinite' }}>…</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

function FinalResultCard({ result }) {
  return (
    <div style={{ margin:'8px 0', display:'flex', flexDirection:'column', gap:10, animation:'fadeSlideUp 0.4s ease-out' }}>
      <div style={{ padding:'12px 14px', borderRadius:12, background:'rgba(70,217,164,0.06)', border:'1px solid rgba(70,217,164,0.15)' }}>
        <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'#46d9a4', letterSpacing:'0.12em', textTransform:'uppercase', marginBottom:6 }}>Summary</div>
        <div style={{ fontSize:13, color:'var(--text-secondary)', lineHeight:1.6 }}>{result.summary}</div>
      </div>
      <div style={{ padding:'12px 14px', borderRadius:12, background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.08)' }}>
        <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.12em', textTransform:'uppercase', marginBottom:8 }}>Diff</div>
        <div style={{ fontFamily:'var(--font-mono)', fontSize:12, display:'flex', flexDirection:'column', gap:2 }}>
          {result.diff.map((line,i)=>(
            <div key={i} style={{ padding:'2px 8px', borderRadius:4, background:line.startsWith('+')?'rgba(70,217,164,0.10)':'rgba(255,107,125,0.10)', color:line.startsWith('+')?'#46d9a4':'#ff6b7d' }}>{line}</div>
          ))}
        </div>
      </div>
      <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
        <a href="#" style={{ display:'inline-flex', alignItems:'center', gap:5, padding:'8px 14px', borderRadius:10, background:'rgba(93,162,255,0.10)', border:'1px solid rgba(93,162,255,0.22)', fontSize:12, fontWeight:600, color:'var(--accent)', textDecoration:'none' }}>
          ⤷ PR {result.pr.number} — {result.pr.title}
        </a>
        <div style={{ display:'inline-flex', alignItems:'center', gap:5, padding:'8px 14px', borderRadius:10, background:'rgba(70,217,164,0.08)', border:'1px solid rgba(70,217,164,0.18)', fontSize:12, color:'#46d9a4' }}>
          ✓ {result.testRun.passed} tests · {result.testRun.duration}
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ msg, agentPhase, agentElapsed }) {
  const isUser = msg.role === 'user';
  const ag = AVAILABLE_AGENTS.find(a => a.id === msg.agent) || AVAILABLE_AGENTS[1];
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
      }}>
        {msg.content}
      </div>
      {msg.phase && <AgentProgressPanel phase={agentPhase||msg.phase} elapsed={agentElapsed||14}/>}
      {msg.isFinal && msg.result && <FinalResultCard result={msg.result}/>}
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
        <div style={{ fontSize:14, color:'var(--text-tertiary)', maxWidth:360, lineHeight:1.6 }}>Fix bugs, run tests, open PRs, monitor campaigns, or answer any question about your stack.</div>
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
function HistorySidebar({ activeId, onSelect, onClose }) {
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
        {CHAT_HISTORY.map(h => {
          const ag = AVAILABLE_AGENTS.find(a=>a.id===h.agent)||AVAILABLE_AGENTS[1];
          const active = activeId === h.id;
          return (
            <button key={h.id} onClick={()=>{ onSelect(h); onClose(); }} style={{
              display:'block', width:'100%', padding:'9px 10px', borderRadius:11, textAlign:'left', cursor:'pointer',
              background:active?'rgba(93,162,255,0.10)':'transparent',
              border:`1px solid ${active?'rgba(93,162,255,0.22)':'transparent'}`,
              marginBottom:3, transition:'all 0.15s',
            }}
            onMouseEnter={e=>{if(!active){e.currentTarget.style.background='rgba(255,255,255,0.04)';e.currentTarget.style.borderColor='rgba(255,255,255,0.08)';}}}
            onMouseLeave={e=>{if(!active){e.currentTarget.style.background='transparent';e.currentTarget.style.borderColor='transparent';}}}>
              <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:3 }}>
                <span style={{ fontSize:12 }}>{ag.icon}</span>
                <span style={{ fontSize:12, fontWeight:600, color:active?'#fff':'var(--text-secondary)', flex:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{h.title}</span>
                <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', flexShrink:0 }}>{h.ts}</span>
              </div>
              <div style={{ fontSize:11, color:'var(--text-muted)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', paddingLeft:18 }}>{h.preview}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ── Main ChatScreen ───────────────────────────────────────────────────────────
function ChatScreen({ chatState }) {
  const [input,      setInput]     = React.useState('');
  const [messages,   setMessages]  = React.useState([]);
  const [sending,    setSending]   = React.useState(false);
  const [agentPhase, setPhase]     = React.useState(null);
  const [elapsed,    setElapsed]   = React.useState(0);
  const [agent,      setAgent]     = React.useState('auto');
  const [chips,      setChips]     = React.useState(CONTEXT_CHIPS_DEFAULT);
  const [showHistory,setShowHistory] = React.useState(false);
  const [activeChat, setActiveChat]  = React.useState(null);
  const messagesEndRef = React.useRef(null);
  const textareaRef    = React.useRef(null);

  const currentAgent = AVAILABLE_AGENTS.find(a=>a.id===agent)||AVAILABLE_AGENTS[1];

  React.useEffect(() => {
    if (chatState === 'idle')      { setMessages([{ role:'assistant', agent:'auto', content:'Good morning. I\'m monitoring 3 scheduled jobs and 2 open tasks. Nothing needs attention right now.\n\nWhat would you like to work on?' }]); }
    else if (chatState === 'executing') {
      setMessages([
        { role:'user', content:'Fix the failing checkout tests in the cart module and open a PR when done.' },
        { role:'assistant', agent:'dev', content:'On it. I\'ll run the failing tests, identify the root cause, apply the fix, and open a PR once the suite is green.', phase:'planning' }
      ]);
      setPhase('editing'); setSending(true); setElapsed(14);
    }
    else if (chatState === 'final') {
      setMessages([
        { role:'user', content:'Fix the failing checkout tests in the cart module and open a PR when done.' },
        { role:'assistant', agent:'dev', content:'Done. Here\'s what happened:', isFinal:true, result:SAMPLE_RESULT }
      ]);
    }
  }, [chatState]);

  React.useEffect(() => {
    if (messagesEndRef.current) {
      const el = messagesEndRef.current;
      el.parentElement.scrollTop = el.parentElement.scrollHeight;
    }
  }, [messages, sending]);

  const handleSend = () => {
    if (!input.trim() || sending) return;
    const text = input.trim(); setInput('');
    const selectedAg = agent === 'auto' ? 'dev' : agent;
    setMessages(prev => [...prev, { role:'user', content:text }]);
    setSending(true); setPhase('planning'); setElapsed(0);
    const phases = ['planning','editing','testing','verifying','pr'];
    let i = 0;
    const timer = setInterval(() => {
      i++;
      if (i < phases.length) { setPhase(phases[i]); setElapsed(i*8); }
      else {
        clearInterval(timer); setSending(false); setPhase(null);
        setMessages(prev => [...prev, { role:'assistant', agent:selectedAg, content:'Done. Here\'s what happened:', isFinal:true, result:SAMPLE_RESULT }]);
      }
    }, 1800);
  };

  const handleKey = e => { if (e.key==='Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); } };
  const adjustTextarea = () => {
    if (!textareaRef.current) return;
    textareaRef.current.style.height = '0';
    textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight,160)+'px';
  };

  const loadHistoryChat = (h) => {
    if (!h) { setMessages([]); setActiveChat(null); return; }
    setActiveChat(h.id);
    setMessages([
      { role:'user', content:h.title },
      { role:'assistant', agent:h.agent, content:h.preview + '\n\n(This is a previous conversation. You can continue from here or start a new chat.)', isFinal:h.screen==='final', result:h.screen==='final'?SAMPLE_RESULT:undefined }
    ]);
  };

  return (
    <div style={{ display:'flex', height:'100%', background:'var(--bg-base)' }}>
      {/* History sidebar */}
      {showHistory && (
        <HistorySidebar activeId={activeChat} onSelect={loadHistoryChat} onClose={()=>setShowHistory(false)}/>
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
          <AgentPicker selected={agent} onSelect={setAgent}/>

          <div style={{ width:1, height:16, background:'rgba(255,255,255,0.10)', flexShrink:0 }}/>

          {/* Context chips */}
          <div style={{ display:'flex', alignItems:'center', gap:5, overflowX:'auto', flex:1 }} className="scrollbar-hide">
            <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', flexShrink:0 }}>Context:</span>
            {chips.map(chip => <ContextChip key={chip.id} chip={chip} onRemove={id=>setChips(p=>p.filter(c=>c.id!==id))}/>)}
            <button onClick={()=>{
              const labels = ['sprint-43','PR-1843','v5.1-release','staging','cve-2025'];
              const icons  = ['◈','⎇','◉','🌐','🔒'];
              const i = chips.length % labels.length;
              setChips(p=>[...p,{id:'c-'+Date.now(),label:labels[i],icon:icons[i],type:'context'}]);
            }} style={{ display:'inline-flex', alignItems:'center', gap:3, padding:'4px 8px', borderRadius:999, border:'1px dashed rgba(255,255,255,0.12)', background:'transparent', fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', cursor:'pointer', flexShrink:0 }}>
              + Add
            </button>
          </div>
        </div>

        {/* Agent context tip */}
        {agent !== 'auto' && (
          <div style={{ margin:'8px 14px 0', padding:'7px 12px', borderRadius:10, background:`${currentAgent.color}08`, border:`1px solid ${currentAgent.color}20`, fontSize:12, color:'var(--text-tertiary)', display:'flex', alignItems:'center', gap:8 }}>
            <span style={{ fontSize:14 }}>{currentAgent.icon}</span>
            <span>Chatting directly with <strong style={{ color:'#fff' }}>{currentAgent.name}</strong> — {currentAgent.desc}. <button style={{ background:'none', border:'none', cursor:'pointer', color:'var(--accent)', fontSize:12 }} onClick={()=>setAgent('auto')}>Switch to Auto →</button></span>
          </div>
        )}

        {/* Messages */}
        <div style={{ flex:1, overflowY:'auto', padding:'18px 16px 8px' }} className="scrollbar-hide">
          {messages.length === 0
            ? <EmptyState onSuggest={t=>{setInput(t); textareaRef.current?.focus();}}/>
            : <>
              {messages.map((msg,i)=>(
                <MessageBubble key={i} msg={msg} agentPhase={agentPhase} agentElapsed={elapsed}/>
              ))}
              {sending && (
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
              placeholder={agent==='auto' ? 'Ask anything — I\'ll pick the right agent…' : `Ask ${currentAgent.name} anything…`}
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
              {agent === 'auto' ? 'Agent selected automatically · you can override above' : `Direct chat with ${currentAgent.name} · context: ${chips.map(c=>c.label).join(', ') || 'none'}`}
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
