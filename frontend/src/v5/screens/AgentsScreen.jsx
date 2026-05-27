/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';


// agents.jsx — Agent Roster V5.0
// Onboarding-provisioned agents clearly labelled. Create new agents. Runtime selector.

// ── Resolve top-priority model from providers config ──────────────────────────
function resolveAgentModel(hint) {
  try {
    const cfg = window.__getProviderConfig ? window.__getProviderConfig() : {};
    const all = window.__getAllProviders   ? window.__getAllProviders()   : [];
    const sorted = [...all].sort((a,b) => (cfg[a.id]?.priority ?? a.defaultPriority) - (cfg[b.id]?.priority ?? b.defaultPriority));
    const top = sorted.find(p => cfg[p.id]?.enabled !== false);
    return top ? (cfg[top.id]?.model || top.defaultModel) : hint;
  } catch { return hint; }
}
function resolveAgentProvider() {
  try {
    const cfg = window.__getProviderConfig ? window.__getProviderConfig() : {};
    const all = window.__getAllProviders   ? window.__getAllProviders()   : [];
    const sorted = [...all].sort((a,b) => (cfg[a.id]?.priority ?? a.defaultPriority) - (cfg[b.id]?.priority ?? b.defaultPriority));
    return sorted.find(p => cfg[p.id]?.enabled !== false) || sorted[0];
  } catch { return null; }
}

// ── Runtime catalogue (from README) ──────────────────────────────────────────
const RUNTIMES = [
  { id:'hermes',    label:'Hermes',      desc:'Default agentic runtime. Plan/Execute/Verify pipeline.',  status:'online', tier:'recommended' },
  { id:'opencode',  label:'OpenCode',    desc:'Code-first runtime. Deep repo editing + test running.',   status:'online', tier:'code' },
  { id:'aider',     label:'Aider',       desc:'AI pair programmer. Fast file edits, git-aware.',          status:'online', tier:'code' },
  { id:'goose',     label:'Goose',       desc:'Multi-step reasoning with tool use. Great for research.',  status:'online', tier:'reasoning' },
  { id:'openhands', label:'OpenHands',   desc:'Full sandboxed execution environment (Docker).',           status:'online', tier:'execution' },
  { id:'claude-code',label:'Claude Code',desc:'Anthropic\'s agentic coding assistant (external CLI).',    status:'external',tier:'external' },
];
const RUNTIME_TIER_COLOR = { recommended:'#46d9a4', code:'#5da2ff', reasoning:'#c4b5fd', execution:'#ffbd66', external:'var(--text-muted)' };

// ── CEO cycle data ────────────────────────────────────────────────────────────
const CEO_CYCLE = {
  lastRun:'14 min ago', nextRun:'1 min', status:'idle',
  lastDirectives:[
    { to:'Dev Agent',      action:'Fix 3 failing pytest tests',     status:'completed', ago:'14m' },
    { to:'Security Agent', action:'Run bandit scan on auth/',        status:'running',   ago:'8m' },
    { to:'Release Agent',  action:'Audit changelog for v5.0',        status:'queued',    ago:'14m' },
  ],
};

// ── Default roster (mix of built-in + onboarding-provisioned) ────────────────
const DEFAULT_AGENTS = [
  { id:'ceo',       name:'CEO Agent',       role:'Orchestrator',   icon:'◎', color:'#c4b5fd', status:'idle',    runtime:'hermes',    model:'nemotron-3-super-120b', specializations:['orchestration','assessment','directives'],    origin:'builtin',  currentTask:null,           tasksWeek:28, avgMs:3200,  lastRun:'14m ago', costPolicy:'local_first', desc:'Runs every 15 min. Reads improvement state, issues directives.' },
  { id:'dev',       name:'Dev Agent',       role:'Engineer',       icon:'⚙', color:'#5da2ff', status:'active',  runtime:'opencode',  model:'qwen3-coder:30b',       specializations:['code_generation','repo_editing','test_fixing'], origin:'builtin',  currentTask:'Migrate DB schema to v3', tasksWeek:41, avgMs:18400, lastRun:'14m ago', costPolicy:'local_first', desc:'Fixes tests, applies code patches, opens PRs.' },
  { id:'security',  name:'Security Agent',  role:'Security',       icon:'🔒',color:'#ffbd66', status:'running', runtime:'hermes',    model:'qwen3-coder:7b',        specializations:['sast','cve_audit','secret_detection'],           origin:'builtin',  currentTask:'Bandit scan — auth module', tasksWeek:7, avgMs:9100, lastRun:'8m ago',  costPolicy:'local_only', desc:'Remediates bandit/CVE/secret findings. Runs weekly + on directive.' },
  { id:'reviewer',  name:'Reviewer Agent',  role:'Code Review',    icon:'◈', color:'#46d9a4', status:'idle',    runtime:'goose',     model:'deepseek-r1:32b',       specializations:['code_review','reasoning','council_review'],       origin:'builtin',  currentTask:null,           tasksWeek:4,  avgMs:24000, lastRun:'3h ago',  costPolicy:'local_first', desc:'Council review every 4th CEO cycle.' },
  { id:'release',   name:'Release Agent',   role:'Release Mgmt',   icon:'◉', color:'#7c9dff', status:'active',  runtime:'hermes',    model:'qwen3-coder:7b',        specializations:['changelog','version_bump','readiness_check'],     origin:'builtin',  currentTask:'Changelog audit — v5.0', tasksWeek:3, avgMs:11200, lastRun:'45m ago', costPolicy:'local_only', desc:'Weekly readiness check, changelog, and version bumping.' },
  // Onboarding-provisioned specialists
  { id:'commerce',  name:'Commerce Agent',  role:'Shopify Specialist',icon:'🛍',color:'#46d9a4',status:'active', runtime:'opencode', model:'qwen3-coder:30b',        specializations:['shopify','checkout','inventory','conversion'],    origin:'onboarding',currentTask:'Audit checkout conversion rate', tasksWeek:12, avgMs:14200, lastRun:'20m ago', costPolicy:'local_first', desc:'Shopify checkout, inventory, and conversion optimisation.' },
  { id:'content',   name:'Content Agent',   role:'CMS Specialist',  icon:'📄',color:'#c4b5fd', status:'idle',   runtime:'hermes',   model:'gemini-2.0-flash',       specializations:['contentful','seo','publishing','assets'],         origin:'onboarding',currentTask:null,           tasksWeek:6,  avgMs:8100,  lastRun:'2h ago',  costPolicy:'local_first', desc:'Contentful publishing, SEO, and asset management.' },
  { id:'analytics', name:'Analytics Agent', role:'GA4 Specialist',  icon:'📊',color:'#5da2ff', status:'idle',   runtime:'hermes',   model:'nemotron-3-super-120b',  specializations:['gtm','ga4','tracking','dashboards'],              origin:'onboarding',currentTask:null,           tasksWeek:3,  avgMs:5400,  lastRun:'4h ago',  costPolicy:'local_first', desc:'GTM/GA4 tracking, event schemas, and dashboard setup.' },
];

// ── Pipeline modes ────────────────────────────────────────────────────────────
const PIPELINE_MODES = [
  { id:'direct',    label:'Direct',         desc:'Single agent responds. Fastest.',                    flow:['Agent'] },
  { id:'plan-exec', label:'Plan → Execute', desc:'Planner outlines steps, Executor runs them.',        flow:['Planner','Executor'] },
  { id:'full',      label:'Full Council',   desc:'Planner → Executor → Judge → Reviewer. Most reliable.', flow:['Planner','Executor','Judge','Reviewer'] },
  { id:'swarm',     label:'Swarm',          desc:'Multiple agents work in parallel, results merged.',   flow:['Agent A','Agent B','Agent C','Merger'] },
];

function statusCfg(s) {
  if (s==='running') return { color:'#5da2ff', bg:'rgba(93,162,255,0.10)', pulse:true,  label:'Running' };
  if (s==='active')  return { color:'#46d9a4', bg:'rgba(70,217,164,0.10)', pulse:true,  label:'Active' };
  if (s==='error')   return { color:'#ff6b7d', bg:'rgba(255,107,125,0.10)',pulse:false, label:'Error' };
  return               { color:'var(--text-muted)', bg:'rgba(255,255,255,0.05)', pulse:false, label:'Idle' };
}

// ── CEO cycle panel ───────────────────────────────────────────────────────────
function CEOCyclePanel({ cycle }) {
  const [running, setRunning] = React.useState(false);
  const run = () => { setRunning(true); setTimeout(()=>setRunning(false), 2500); };
  return (
    <div style={{ borderRadius:20, padding:'16px 18px', background:'linear-gradient(135deg,rgba(196,181,253,0.08),rgba(10,12,15,0.95) 60%)', border:'1px solid rgba(196,181,253,0.18)', marginBottom:18 }}>
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:12, flexWrap:'wrap', marginBottom:12 }}>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <div style={{ width:30, height:30, borderRadius:9, background:'rgba(196,181,253,0.15)', border:'1px solid rgba(196,181,253,0.25)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:14 }}>◎</div>
          <div>
            <div style={{ fontSize:14, fontWeight:800, color:'#fff', letterSpacing:'-0.02em' }}>CEO Agent</div>
            <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'#c4b5fd' }}>Orchestrator · every 15 min · Last: {cycle.lastRun} · Next: {cycle.nextRun}</div>
          </div>
        </div>
        <button onClick={run} disabled={running} style={{ display:'inline-flex', alignItems:'center', gap:6, padding:'7px 14px', borderRadius:999, fontSize:11, fontWeight:700, cursor:'pointer', background:'rgba(196,181,253,0.12)', border:'1px solid rgba(196,181,253,0.28)', color:running?'var(--text-muted)':'#c4b5fd', transition:'all 0.2s ease', whiteSpace:'nowrap' }}>
          {running ? <><div style={{ width:10,height:10,border:'2px solid rgba(196,181,253,0.2)',borderTopColor:'#c4b5fd',borderRadius:'50%',animation:'spin 0.8s linear infinite' }}/>Running…</> : '↺ Run cycle now'}
        </button>
      </div>
      <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
        {cycle.lastDirectives.map((d,i) => {
          const sc = statusCfg(d.status==='completed'?'active':d.status);
          return (
            <div key={i} style={{ display:'flex', alignItems:'center', gap:9, padding:'7px 10px', borderRadius:9, background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.07)' }}>
              <span style={{ width:5, height:5, borderRadius:'50%', background:sc.color, flexShrink:0, animation:sc.pulse?'pulse 2s infinite':'none' }}/>
              <span style={{ fontSize:12, color:'var(--text-secondary)', flex:1 }}>{d.action}</span>
              <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'rgba(196,181,253,0.7)', flexShrink:0 }}>→ {d.to}</span>
              <span style={{ fontSize:9, fontFamily:'var(--font-mono)', letterSpacing:'0.10em', textTransform:'uppercase', color:sc.color, padding:'1px 6px', borderRadius:5, background:sc.bg, flexShrink:0 }}>{d.status==='completed'?'done':d.status}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Pipeline config panel ─────────────────────────────────────────────────────
function PipelinePanel() {
  const [mode, setMode] = React.useState('plan-exec');
  const [enabled, setEnabled] = React.useState(true);
  const current = PIPELINE_MODES.find(p => p.id === mode);

  return (
    <div style={{ borderRadius:18, border:'1px solid rgba(255,255,255,0.09)', background:'rgba(255,255,255,0.03)', padding:'14px 16px', marginBottom:20 }}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:12 }}>
        <div>
          <div style={{ fontSize:13, fontWeight:700, color:'#fff', marginBottom:2 }}>Agent Pipeline</div>
          <div style={{ fontSize:11, color:'var(--text-muted)' }}>How agents collaborate on each task. Can be overridden per-task.</div>
        </div>
        <button onClick={() => setEnabled(o=>!o)} style={{ width:40, height:22, borderRadius:999, padding:3, cursor:'pointer', background:enabled?'var(--accent)':'rgba(255,255,255,0.10)', border:`1px solid ${enabled?'rgba(93,162,255,0.5)':'rgba(255,255,255,0.15)'}`, transition:'all 0.2s', display:'flex', alignItems:'center', justifyContent:enabled?'flex-end':'flex-start' }}>
          <div style={{ width:16, height:16, borderRadius:'50%', background:'#fff', boxShadow:'0 1px 3px rgba(0,0,0,0.3)' }}/>
        </button>
      </div>
      {enabled && (
        <>
          <div style={{ display:'flex', gap:6, flexWrap:'wrap', marginBottom:12 }}>
            {PIPELINE_MODES.map(pm => (
              <button key={pm.id} onClick={() => setMode(pm.id)} style={{
                padding:'6px 14px', borderRadius:999, fontSize:12, fontWeight:600, cursor:'pointer',
                background:mode===pm.id?'rgba(93,162,255,0.15)':'rgba(255,255,255,0.04)',
                border:`1px solid ${mode===pm.id?'rgba(93,162,255,0.35)':'rgba(255,255,255,0.09)'}`,
                color:mode===pm.id?'#fff':'var(--text-muted)', transition:'all 0.15s',
              }}>{pm.label}</button>
            ))}
          </div>
          {current && (
            <div style={{ display:'flex', alignItems:'center', gap:8, padding:'10px 12px', borderRadius:11, background:'rgba(93,162,255,0.05)', border:'1px solid rgba(93,162,255,0.14)' }}>
              <div style={{ display:'flex', alignItems:'center', gap:5, flexWrap:'wrap', flex:1 }}>
                {current.flow.map((step, i) => (
                  <React.Fragment key={step}>
                    <span style={{ fontSize:11, fontWeight:700, color:'var(--accent)', padding:'3px 10px', borderRadius:7, background:'rgba(93,162,255,0.12)', border:'1px solid rgba(93,162,255,0.22)' }}>{step}</span>
                    {i < current.flow.length-1 && <span style={{ color:'rgba(255,255,255,0.25)', fontSize:12 }}>→</span>}
                  </React.Fragment>
                ))}
              </div>
              <div style={{ fontSize:12, color:'var(--text-muted)', maxWidth:200, flexShrink:0 }}>{current.desc}</div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── New agent form ────────────────────────────────────────────────────────────
function NewAgentForm({ onAdd, onClose }) {
  const [name, setName]           = React.useState('');
  const [role, setRole]           = React.useState('');
  const [runtime, setRuntime]     = React.useState('hermes');
  const [costPolicy, setCostPolicy] = React.useState('local_first');
  const [specs, setSpecs]         = React.useState([]);
  const [prompt, setPrompt]       = React.useState('');
  const ALL_SPECS = ['code_generation','repo_editing','code_review','sast','reasoning','scheduled','shopify','contentful','seo','ga4','support'];

  const submit = () => {
    if (!name.trim()) return;
    onAdd({
      id:`agent-${Date.now()}`, name:name.trim(), role:role||'General', icon:'◎', color:'#5da2ff',
      status:'idle', runtime, model:resolveAgentModel('qwen3-coder:30b'),
      specializations:specs, origin:'custom', currentTask:null,
      tasksWeek:0, avgMs:0, lastRun:'never', costPolicy, desc:prompt||`Custom agent: ${name}`,
    });
    onClose();
  };

  return (
    <div style={{ borderRadius:18, border:'1px solid rgba(93,162,255,0.20)', background:'rgba(93,162,255,0.04)', padding:'18px', marginBottom:18, animation:'fadeSlideUp 0.25s ease-out' }}>
      <div style={{ fontSize:13, fontWeight:800, color:'#fff', marginBottom:14 }}>New Agent Profile</div>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10, marginBottom:12 }}>
        <div>
          <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.10em', marginBottom:5 }}>Name *</div>
          <input value={name} onChange={e=>setName(e.target.value)} placeholder="e.g. SEO Agent"
            style={{ width:'100%', padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-main)' }}
            onFocus={e=>e.target.style.borderColor='rgba(93,162,255,0.45)'} onBlur={e=>e.target.style.borderColor='rgba(255,255,255,0.10)'}/>
        </div>
        <div>
          <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.10em', marginBottom:5 }}>Role</div>
          <input value={role} onChange={e=>setRole(e.target.value)} placeholder="e.g. SEO Specialist"
            style={{ width:'100%', padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-main)' }}
            onFocus={e=>e.target.style.borderColor='rgba(93,162,255,0.45)'} onBlur={e=>e.target.style.borderColor='rgba(255,255,255,0.10)'}/>
        </div>
      </div>

      <div style={{ marginBottom:12 }}>
        <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.10em', marginBottom:5 }}>Runtime</div>
        <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
          {RUNTIMES.map(rt => (
            <button key={rt.id} onClick={() => setRuntime(rt.id)} style={{
              padding:'5px 12px', borderRadius:999, fontSize:11, fontWeight:600, cursor:'pointer',
              background:runtime===rt.id?`${RUNTIME_TIER_COLOR[rt.tier]}15`:'rgba(255,255,255,0.04)',
              border:`1px solid ${runtime===rt.id?`${RUNTIME_TIER_COLOR[rt.tier]}40`:'rgba(255,255,255,0.09)'}`,
              color:runtime===rt.id?RUNTIME_TIER_COLOR[rt.tier]:'var(--text-muted)', transition:'all 0.15s',
            }}>{rt.label}</button>
          ))}
        </div>
        {RUNTIMES.find(r=>r.id===runtime) && <div style={{ fontSize:11, color:'var(--text-muted)', marginTop:5 }}>{RUNTIMES.find(r=>r.id===runtime).desc}</div>}
      </div>

      <div style={{ marginBottom:12 }}>
        <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.10em', marginBottom:5 }}>Specializations</div>
        <div style={{ display:'flex', gap:5, flexWrap:'wrap' }}>
          {ALL_SPECS.map(s => {
            const on = specs.includes(s);
            return <button key={s} onClick={()=>setSpecs(p=>on?p.filter(x=>x!==s):[...p,s])} style={{ padding:'4px 10px', borderRadius:999, fontSize:10, fontFamily:'var(--font-mono)', cursor:'pointer', background:on?'rgba(93,162,255,0.15)':'rgba(255,255,255,0.04)', border:`1px solid ${on?'rgba(93,162,255,0.35)':'rgba(255,255,255,0.09)'}`, color:on?'#fff':'var(--text-muted)', transition:'all 0.15s', textTransform:'uppercase', letterSpacing:'0.08em' }}>{s}</button>;
          })}
        </div>
      </div>

      <div style={{ marginBottom:12 }}>
        <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.10em', marginBottom:5 }}>System prompt (optional)</div>
        <textarea value={prompt} onChange={e=>setPrompt(e.target.value)} placeholder="You are an expert SEO agent…" rows={3}
          style={{ width:'100%', padding:'9px 12px', borderRadius:10, resize:'none', background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:12, fontFamily:'var(--font-mono)', outline:'none' }}
          onFocus={e=>e.target.style.borderColor='rgba(93,162,255,0.45)'} onBlur={e=>e.target.style.borderColor='rgba(255,255,255,0.10)'}/>
      </div>

      <div style={{ display:'flex', gap:8 }}>
        <button onClick={submit} style={{ flex:1, padding:'10px', borderRadius:12, background:'linear-gradient(135deg,#6CB0FF,#4F93FF)', color:'#06111f', fontSize:13, fontWeight:800, border:'none', cursor:'pointer' }}>+ Create Agent</button>
        <button onClick={onClose} style={{ padding:'10px 18px', borderRadius:12, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-muted)', fontSize:13, cursor:'pointer' }}>Cancel</button>
      </div>
    </div>
  );
}

// ── Agent card ────────────────────────────────────────────────────────────────
function AgentCard({ agent, onChat }) {
  const sc = statusCfg(agent.status);
  const resolvedModel   = resolveAgentModel(agent.model);
  const topProvider     = resolveAgentProvider();
  const modelChanged    = resolvedModel !== agent.model;
  const originConfig    = {
    builtin:    { color:'#5da2ff',  label:'Built-in',    desc:'Core agency agent' },
    onboarding: { color:'#46d9a4',  label:'Provisioned', desc:'Created from onboarding discovery' },
    custom:     { color:'#c4b5fd',  label:'Custom',      desc:'Manually created' },
  }[agent.origin] || { color:'var(--text-muted)', label:'Custom', desc:'' };
  const rt = RUNTIMES.find(r => r.id === agent.runtime);

  return (
    <div style={{
      borderRadius:18, border:`1px solid ${agent.status!=='idle'?`${sc.color}22`:'rgba(255,255,255,0.09)'}`,
      background:agent.status!=='idle'?`${sc.color}04`:'rgba(255,255,255,0.03)',
      padding:'15px', transition:'all 0.2s ease',
    }}
    onMouseEnter={e=>{ e.currentTarget.style.transform='translateY(-2px)'; e.currentTarget.style.boxShadow=`0 8px 24px ${sc.color}10`; }}
    onMouseLeave={e=>{ e.currentTarget.style.transform='none'; e.currentTarget.style.boxShadow='none'; }}>

      {/* Origin badge + status */}
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:8 }}>
        <span style={{ fontSize:9, fontFamily:'var(--font-mono)', letterSpacing:'0.10em', textTransform:'uppercase', padding:'2px 8px', borderRadius:999, color:originConfig.color, background:`${originConfig.color}12`, border:`1px solid ${originConfig.color}25` }}>
          {originConfig.label}
          {agent.origin==='onboarding' && ' · from discovery'}
        </span>
        <div style={{ display:'flex', alignItems:'center', gap:5 }}>
          <span style={{ width:6, height:6, borderRadius:'50%', background:sc.color, animation:sc.pulse?'pulse 2s infinite':'none' }}/>
          <span style={{ fontSize:10, fontFamily:'var(--font-mono)', letterSpacing:'0.09em', textTransform:'uppercase', color:sc.color }}>{sc.label}</span>
        </div>
      </div>

      {/* Name + icon */}
      <div style={{ display:'flex', alignItems:'flex-start', gap:10, marginBottom:8 }}>
        <div style={{ width:36, height:36, borderRadius:12, flexShrink:0, background:`${agent.color}15`, border:`1px solid ${agent.color}28`, display:'flex', alignItems:'center', justifyContent:'center', fontSize:16 }}>{agent.icon}</div>
        <div style={{ flex:1 }}>
          <div style={{ fontSize:14, fontWeight:800, color:'#fff', letterSpacing:'-0.02em' }}>{agent.name}</div>
          <div style={{ fontSize:11, color:'var(--text-muted)', fontFamily:'var(--font-mono)' }}>{agent.role}</div>
        </div>
      </div>

      {/* Current task */}
      {agent.currentTask && (
        <div style={{ marginBottom:8, padding:'7px 10px', borderRadius:9, background:`${sc.color}08`, border:`1px solid ${sc.color}18`, fontSize:11, color:'var(--text-secondary)', lineHeight:1.5, display:'flex', alignItems:'flex-start', gap:5 }}>
          <span style={{ color:sc.color, flexShrink:0, animation:'blink 1.4s infinite' }}>▸</span>
          {agent.currentTask}
        </div>
      )}

      <div style={{ fontSize:12, color:'var(--text-muted)', lineHeight:1.5, marginBottom:8 }}>{agent.desc}</div>

      {/* Specializations */}
      <div style={{ display:'flex', gap:4, flexWrap:'wrap', marginBottom:10 }}>
        {agent.specializations.slice(0,4).map(s => (
          <span key={s} style={{ fontSize:9, fontFamily:'var(--font-mono)', letterSpacing:'0.09em', textTransform:'uppercase', padding:'2px 6px', borderRadius:999, color:agent.color, background:`${agent.color}10`, border:`1px solid ${agent.color}20` }}>{s.replace(/_/g,' ')}</span>
        ))}
      </div>

      {/* Stats */}
      <div style={{ display:'flex', gap:10, padding:'8px 0', borderTop:'1px solid rgba(255,255,255,0.06)', borderBottom:'1px solid rgba(255,255,255,0.06)', marginBottom:10 }}>
        {[
          { label:'Week', value:agent.tasksWeek||0 },
          { label:'Avg', value:agent.avgMs>=1000?`${(agent.avgMs/1000).toFixed(1)}s`:`${agent.avgMs}ms` },
          { label:'Last', value:agent.lastRun },
        ].map(m => (
          <div key={m.label} style={{ flex:1 }}>
            <div style={{ fontSize:9, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.10em', textTransform:'uppercase', marginBottom:2 }}>{m.label}</div>
            <div style={{ fontSize:12, fontWeight:700, color:'var(--text-primary)' }}>{m.value}</div>
          </div>
        ))}
      </div>

      {/* Runtime + model */}
      <div style={{ display:'flex', gap:5, flexWrap:'wrap', marginBottom:10 }}>
        <span style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'2px 7px', borderRadius:999, color:rt?RUNTIME_TIER_COLOR[rt.tier]:'var(--text-muted)', background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.09)', textTransform:'uppercase', letterSpacing:'0.09em' }}>⚙ {agent.runtime}</span>
        <span style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'2px 7px', borderRadius:999, color:modelChanged?'#46d9a4':'var(--text-muted)', background:modelChanged?'rgba(70,217,164,0.08)':'rgba(255,255,255,0.05)', border:`1px solid ${modelChanged?'rgba(70,217,164,0.20)':'rgba(255,255,255,0.09)'}`, maxWidth:180, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', textTransform:'uppercase', letterSpacing:'0.09em' }}>◈ {resolvedModel}{modelChanged?' ↑':''}</span>
        {topProvider && modelChanged && <span style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'2px 7px', borderRadius:999, color:topProvider.color||'var(--accent)', background:`${topProvider.color||'#fff'}10`, border:`1px solid ${topProvider.color||'#fff'}22`, textTransform:'uppercase', letterSpacing:'0.09em' }}>via {topProvider.name}</span>}
      </div>

      <button onClick={() => onChat && onChat(agent)} style={{ width:'100%', padding:'8px', borderRadius:10, fontSize:12, fontWeight:700, cursor:'pointer', background:`${agent.color}10`, border:`1px solid ${agent.color}22`, color:agent.color, transition:'all 0.15s ease' }}
        onMouseEnter={e=>e.currentTarget.style.background=`${agent.color}20`}
        onMouseLeave={e=>e.currentTarget.style.background=`${agent.color}10`}>
        → Chat with {agent.name.split(' ')[0]}
      </button>
    </div>
  );
}

// ── Runtimes status bar ───────────────────────────────────────────────────────
function RuntimesBar() {
  return (
    <div style={{ borderRadius:16, border:'1px solid rgba(255,255,255,0.09)', background:'rgba(255,255,255,0.025)', padding:'12px 16px', marginBottom:20 }}>
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.12em', textTransform:'uppercase', marginBottom:10 }}>Agent Runtimes</div>
      <div style={{ display:'flex', gap:8, flexWrap:'wrap' }}>
        {RUNTIMES.map(rt => {
          const tc = RUNTIME_TIER_COLOR[rt.tier];
          return (
            <div key={rt.id} style={{ display:'flex', alignItems:'center', gap:7, padding:'6px 12px', borderRadius:10, background:`${tc}0a`, border:`1px solid ${tc}22` }}>
              <span style={{ width:6, height:6, borderRadius:'50%', background:rt.status==='online'?'#46d9a4':rt.status==='external'?'#ffbd66':'#ff6b7d', animation:rt.status==='online'?'pulse 2s infinite':'none' }}/>
              <span style={{ fontSize:12, fontWeight:600, color:'#fff' }}>{rt.label}</span>
              {rt.tier==='recommended' && <span style={{ fontSize:9, fontFamily:'var(--font-mono)', color:'#46d9a4', padding:'1px 5px', borderRadius:4, background:'rgba(70,217,164,0.10)' }}>default</span>}
              {rt.status==='external' && <span style={{ fontSize:9, fontFamily:'var(--font-mono)', color:'#ffbd66' }}>external</span>}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────
function AgentsScreen({ onNavigateToChat }) {
  const [agents, setAgents]     = React.useState(DEFAULT_AGENTS);
  const [showForm, setShowForm] = React.useState(false);
  const [filter, setFilter]     = React.useState('all');

  const builtIn     = agents.filter(a => a.origin==='builtin' && a.id!=='ceo');
  const provisioned = agents.filter(a => a.origin==='onboarding');
  const custom      = agents.filter(a => a.origin==='custom');
  const activeCount = agents.filter(a => a.status!=='idle').length;

  const filtered = filter==='all' ? agents.filter(a=>a.id!=='ceo')
                 : filter==='provisioned' ? provisioned
                 : filter==='builtin' ? builtIn
                 : custom;

  return (
    <div style={{ padding:'20px 16px 48px', maxWidth:1100, margin:'0 auto' }}>
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:6 }}>Autonomous Agency</div>
      <div style={{ display:'flex', alignItems:'flex-end', justifyContent:'space-between', flexWrap:'wrap', gap:10, marginBottom:18 }}>
        <div>
          <h1 style={{ fontSize:26, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', lineHeight:1.1, marginBottom:4 }}>Agent Roster</h1>
          <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.5, maxWidth:480 }}>CEO + built-in specialists + agents provisioned from your onboarding discovery. All use your configured model priority.</p>
        </div>
        <div style={{ display:'flex', gap:10, alignItems:'center', flexWrap:'wrap' }}>
          <div style={{ padding:'8px 14px', borderRadius:12, background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.09)', textAlign:'center' }}>
            <div style={{ fontSize:20, fontWeight:800, color:'#46d9a4', letterSpacing:'-0.03em' }}>{activeCount}</div>
            <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.10em' }}>Active now</div>
          </div>
          <button onClick={() => setShowForm(true)} style={{ display:'inline-flex', alignItems:'center', gap:7, padding:'10px 20px', borderRadius:999, fontSize:13, fontWeight:800, cursor:'pointer', background:'linear-gradient(135deg,#6CB0FF,#4F93FF)', color:'#06111f', border:'none', boxShadow:'0 6px 20px rgba(93,162,255,0.22)' }}>+ New agent</button>
        </div>
      </div>

      <CEOCyclePanel cycle={CEO_CYCLE}/>
      <PipelinePanel/>
      <RuntimesBar/>

      {showForm && <NewAgentForm onAdd={a => { setAgents(p=>[...p,a]); setShowForm(false); }} onClose={() => setShowForm(false)}/>}

      {/* Filter tabs */}
      <div style={{ display:'flex', gap:6, marginBottom:14, flexWrap:'wrap' }}>
        {[
          { id:'all',         label:`All (${agents.filter(a=>a.id!=='ceo').length})` },
          { id:'builtin',     label:`Built-in (${builtIn.length})` },
          { id:'provisioned', label:`From onboarding (${provisioned.length})` },
          { id:'custom',      label:`Custom (${custom.length})` },
        ].map(f => (
          <button key={f.id} onClick={() => setFilter(f.id)} style={{ padding:'5px 14px', borderRadius:999, fontSize:12, fontWeight:600, cursor:'pointer', background:filter===f.id?'rgba(93,162,255,0.15)':'rgba(255,255,255,0.04)', border:`1px solid ${filter===f.id?'rgba(93,162,255,0.35)':'rgba(255,255,255,0.09)'}`, color:filter===f.id?'#fff':'var(--text-muted)', transition:'all 0.15s' }}>{f.label}</button>
        ))}
      </div>

      {/* Onboarding callout for provisioned agents */}
      {(filter==='all'||filter==='provisioned') && provisioned.length > 0 && (
        <div style={{ padding:'10px 14px', borderRadius:12, background:'rgba(70,217,164,0.05)', border:'1px solid rgba(70,217,164,0.15)', marginBottom:12, fontSize:12, color:'#46d9a4', lineHeight:1.5 }}>
          ✦ {provisioned.length} specialists were auto-provisioned during company onboarding (acme-store.com). They know your Shopify, Contentful, and GA4 stack.
        </div>
      )}

      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(280px,1fr))', gap:14 }}>
        {filtered.map(agent => (
          <AgentCard key={agent.id} agent={agent} onChat={() => onNavigateToChat && onNavigateToChat(agent)}/>
        ))}
      </div>
    </div>
  );
}

export { AgentsScreen };
export default AgentsScreen;
