/* eslint-disable jsx-a11y/anchor-is-valid -- ported design prototype; hardened when wired to live data */
import React from 'react';
import { useSafeData } from '../hooks/useSafeData';
import * as api from '../../api';

// agents.jsx — Agent Roster V5.0

function relTime(iso) {
  if (!iso) return '—';
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
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

// ── Built-in agent definitions (static catalog — these are real system agents) ─
const BUILTIN_AGENT_DEFS = [
  { id:'ceo',      name:'CEO Agent',      role:'Orchestrator',  icon:'◎', color:'#c4b5fd', runtime:'hermes',   model:'—', specializations:['orchestration','assessment','directives'],    costPolicy:'local_first', desc:'Orchestrates the agency cycle — reads improvement state and issues directives to specialist agents.' },
  { id:'dev',      name:'Dev Agent',      role:'Engineer',      icon:'⚙', color:'#5da2ff', runtime:'opencode', model:'—', specializations:['code_generation','repo_editing','test_fixing'], costPolicy:'local_first', desc:'Fixes tests, applies code patches, opens PRs.' },
  { id:'security', name:'Security Agent', role:'Security',      icon:'🔒',color:'#ffbd66', runtime:'hermes',   model:'—', specializations:['sast','cve_audit','secret_detection'],           costPolicy:'local_only',  desc:'Remediates bandit/CVE/secret findings. Runs on directive.' },
  { id:'reviewer', name:'Reviewer Agent', role:'Code Review',   icon:'◈', color:'#46d9a4', runtime:'hermes',   model:'—', specializations:['code_review','reasoning','council_review'],       costPolicy:'local_first', desc:'Performs council review on significant changes.' },
  { id:'release',  name:'Release Agent',  role:'Release Mgmt',  icon:'◉', color:'#7c9dff', runtime:'hermes',   model:'—', specializations:['changelog','version_bump','readiness_check'],     costPolicy:'local_only',  desc:'Weekly readiness check, changelog, and version bumping.' },
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
function CEOCyclePanel({ directives, loading }) {
  return (
    <div style={{ borderRadius:20, padding:'16px 18px', background:'linear-gradient(135deg,rgba(196,181,253,0.08),rgba(10,12,15,0.95) 60%)', border:'1px solid rgba(196,181,253,0.18)', marginBottom:18 }}>
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:12, flexWrap:'wrap', marginBottom:12 }}>
        <div style={{ display:'flex', alignItems:'center', gap:8 }}>
          <div style={{ width:30, height:30, borderRadius:9, background:'rgba(196,181,253,0.15)', border:'1px solid rgba(196,181,253,0.25)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:14 }}>◎</div>
          <div>
            <div style={{ fontSize:14, fontWeight:800, color:'#fff', letterSpacing:'-0.02em' }}>CEO Agent</div>
            <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'#c4b5fd' }}>Orchestrator · recent activity from backend</div>
          </div>
        </div>
      </div>
      {loading && <div style={{ fontSize:12, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>Loading activity…</div>}
      {!loading && directives.length === 0 && (
        <div style={{ fontSize:12, color:'var(--text-muted)', padding:'8px 0' }}>No recent agent activity logged. Activity will appear here once agents run tasks.</div>
      )}
      <div style={{ display:'flex', flexDirection:'column', gap:5 }}>
        {directives.map((d,i) => {
          const sc = statusCfg('active');
          return (
            <div key={i} style={{ display:'flex', alignItems:'center', gap:9, padding:'7px 10px', borderRadius:9, background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.07)' }}>
              <span style={{ width:5, height:5, borderRadius:'50%', background:sc.color, flexShrink:0 }}/>
              <span style={{ fontSize:12, color:'var(--text-secondary)', flex:1 }}>{d.action}</span>
              <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'rgba(196,181,253,0.7)', flexShrink:0 }}>→ {d.to}</span>
              <span style={{ fontSize:9, fontFamily:'var(--font-mono)', letterSpacing:'0.10em', textTransform:'uppercase', color:'var(--text-muted)', padding:'1px 6px', borderRadius:5, background:'rgba(255,255,255,0.05)', flexShrink:0 }}>{d.ago}</span>
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
function NewAgentForm({ onCreate, onClose }) {
  const [name, setName]           = React.useState('');
  const [role, setRole]           = React.useState('');
  const [runtime, setRuntime]     = React.useState('hermes');
  const [costPolicy]                = React.useState('local_first');
  const [specs, setSpecs]         = React.useState([]);
  const [prompt, setPrompt]       = React.useState('');
  const [busy, setBusy]           = React.useState(false);
  const [error, setError]         = React.useState(null);
  const ALL_SPECS = ['code_generation','repo_editing','code_review','sast','reasoning','scheduled','shopify','contentful','seo','ga4','support'];

  const submit = async () => {
    if (!name.trim() || busy) return;
    setBusy(true); setError(null);
    try {
      // Persist to the backend agent store (POST /api/agents/). Field names match
      // AgentCreateRequest (agents/store.py): name, role, description, model,
      // system_prompt, preferred_runtime, task_specializations, cost_policy, tags.
      await onCreate({
        name: name.trim(),
        role: role || 'General',
        description: prompt || `Custom agent: ${name.trim()}`,
        model: '',
        system_prompt: prompt || '',
        preferred_runtime: runtime,
        task_specializations: specs,
        cost_policy: costPolicy,
        tags: ['custom'],
      });
      onClose();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      setError(detail ? api.fmtErr(detail) : (e?.message || 'Failed to create agent.'));
      setBusy(false);
    }
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

      {error && <div style={{ marginBottom:10, padding:'8px 12px', borderRadius:10, background:'rgba(255,107,125,0.10)', border:'1px solid rgba(255,107,125,0.25)', color:'#ff6b7d', fontSize:12 }}>{error}</div>}
      <div style={{ display:'flex', gap:8 }}>
        <button onClick={submit} disabled={busy} style={{ flex:1, padding:'10px', borderRadius:12, background:'linear-gradient(135deg,#6CB0FF,#4F93FF)', color:'#06111f', fontSize:13, fontWeight:800, border:'none', cursor:busy?'wait':'pointer', opacity:busy?0.7:1 }}>{busy ? 'Creating…' : '+ Create Agent'}</button>
        <button onClick={onClose} disabled={busy} style={{ padding:'10px 18px', borderRadius:12, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-muted)', fontSize:13, cursor:'pointer' }}>Cancel</button>
      </div>
    </div>
  );
}

// ── Agent card ────────────────────────────────────────────────────────────────
function AgentCard({ agent, onChat, onRun }) {
  const sc = statusCfg(agent.status);
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
        {agent.model && agent.model !== '—' && (
          <span style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'2px 7px', borderRadius:999, color:'var(--text-muted)', background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.09)', maxWidth:180, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', textTransform:'uppercase', letterSpacing:'0.09em' }}>◈ {agent.model}</span>
        )}
      </div>

      <div style={{ display:'flex', gap:8 }}>
        <button onClick={() => onRun && onRun(agent)} style={{ flex:1, padding:'8px', borderRadius:10, fontSize:12, fontWeight:800, cursor:'pointer', background:'linear-gradient(135deg,#6CB0FF,#4F93FF)', color:'#06111f', border:'none', transition:'all 0.15s ease' }}>
          ▶ Run task
        </button>
        <button onClick={() => onChat && onChat(agent)} style={{ flex:1, padding:'8px', borderRadius:10, fontSize:12, fontWeight:700, cursor:'pointer', background:`${agent.color}10`, border:`1px solid ${agent.color}22`, color:agent.color, transition:'all 0.15s ease' }}
          onMouseEnter={e=>e.currentTarget.style.background=`${agent.color}20`}
          onMouseLeave={e=>e.currentTarget.style.background=`${agent.color}10`}>
          → Chat
        </button>
      </div>
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

// ── Run-task modal ────────────────────────────────────────────────────────────
// Dispatches a task to the autonomous agent pipeline via the real chat API
// (agent_mode=true → HTTP 202 { job_id }) and streams the job to completion.
// ── Run-task modal ─────────────────────────────────────────────────────────────────────
// Creates a tracked task in the Tasks board, then dispatches it through the
// task pipeline (POST /api/tasks → POST /api/tasks/{id}/run). The task appears
// in both the Agents screen (live execution) and the Tasks board (persistent).
function RunTaskModal({ agent, onClose, onViewInTasks }) {
  const [task, setTask]     = React.useState('');
  const [status, setStatus] = React.useState('idle'); // idle | starting | running | done | error
  const [phase, setPhase]   = React.useState(null);
  const [result, setResult] = React.useState(null);
  const [error, setError]   = React.useState(null);
  const [taskId, setTaskId] = React.useState(null);
  const mounted = React.useRef(true);
  React.useEffect(() => () => { mounted.current = false; }, []);

  const poll = async (tid) => {
    setPhase('queued');
    for (let i = 0; i < 240; i++) {
      await new Promise(r => setTimeout(r, 1500));
      if (!mounted.current) return;
      let snap;
      try { const { data } = await api.getTask(tid); snap = data.task || data; }
      catch { if (mounted.current) { setStatus('error'); setError('Lost connection — the task may still be running on the server.'); } return; }
      if (!mounted.current) return;
      const st = snap?.status;
      setPhase(st || 'in_progress');
      if (st === 'done') {
        setStatus('done');
        setResult(snap?.result || snap?.error_message || 'Task completed.');
        return;
      }
      if (st === 'failed') {
        setStatus('error');
        setError(snap?.error_message || 'Task execution failed.');
        return;
      }
    }
    if (mounted.current) { setStatus('error'); setError('Task exceeded 6 min timeout — check the Tasks board for its status.'); }
  };

  const run = async () => {
    if (!task.trim() || status === 'starting' || status === 'running') return;
    setStatus('starting'); setError(null); setResult(null); setPhase(null);
    try {
      // 1. Create a persistent task in the Tasks board
      const taskPayload = {
        title: task.trim().substring(0, 80),
        description: task.trim(),
        prompt: task.trim(),
        agent_id: agent.id,
        runtime_id: agent.runtime || 'hermes',
        priority: 'medium',
        task_type: agent.specializations?.[0]?.replace(/_/g, ' ') || 'general',
        tags: [agent.id, agent.origin || 'builtin'],
      };
      const { data: taskData } = await api.createTask(taskPayload);
      if (!mounted.current) return;
      const tid = taskData?.task?.task_id;
      if (!tid) throw new Error('Task created but no ID returned');
      setTaskId(tid);

      // 2. Trigger execution via the task pipeline
      await api.runTask(tid);
      if (!mounted.current) return;
      setStatus('running');

      // 3. Poll for completion
      await poll(tid);
    } catch (e) {
      if (!mounted.current) return;
      const detail = e?.response?.data?.detail;
      setStatus('error');
      setError(detail ? api.fmtErr(detail) : (e?.message || 'Failed to start the task.'));
    }
  };

  const busy = status === 'starting' || status === 'running';

  return (
    <div onClick={onClose} style={{ position:'fixed', inset:0, zIndex:2000, background:'rgba(2,3,4,0.7)', display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}>
      <div onClick={e=>e.stopPropagation()} style={{ width:'100%', maxWidth:560, maxHeight:'88vh', overflowY:'auto', borderRadius:18, border:'1px solid rgba(93,162,255,0.20)', background:'var(--bg-surface)', padding:'20px' }}>
        <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:6 }}>
          <div style={{ fontSize:15, fontWeight:800, color:'#fff' }}>Run a task · {agent.name}</div>
          <button onClick={onClose} style={{ background:'none', border:'none', color:'var(--text-muted)', fontSize:20, cursor:'pointer' }}>×</button>
        </div>
        <div style={{ fontSize:12, color:'var(--text-muted)', marginBottom:12, lineHeight:1.5 }}>Creates a tracked task in the <strong style={{ color:'var(--text-tertiary)' }}>Tasks board</strong>, then dispatches it through the <strong style={{ color:'var(--text-tertiary)' }}>{agent.name}</strong> pipeline. Monitor progress here or find the full lifecycle in Tasks.</div>
        <textarea value={task} onChange={e=>setTask(e.target.value)} disabled={busy} placeholder="Describe the task…  e.g. 'Audit the checkout flow for SEO regressions and open a PR'" rows={4}
          style={{ width:'100%', padding:'10px 12px', borderRadius:10, resize:'vertical', background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, fontFamily:'var(--font-main)', outline:'none', marginBottom:12 }}/>
        {busy && (
          <div style={{ marginBottom:12, padding:'10px 12px', borderRadius:10, background:'rgba(93,162,255,0.06)', border:'1px solid rgba(93,162,255,0.16)', fontSize:12, color:'var(--text-secondary)', display:'flex', alignItems:'center', gap:8 }}>
            <span style={{ width:7, height:7, borderRadius:'50%', background:'var(--accent)', animation:'pulse 1.4s infinite' }}/>
            {status === 'starting' ? 'Creating task…' : `Running · ${phase || 'in_progress'}…`}
          </div>
        )}
        {taskId && status === 'running' && (
          <div style={{ marginBottom:12, padding:'8px 12px', borderRadius:10, background:'rgba(93,162,255,0.06)', border:'1px solid rgba(93,162,255,0.14)', display:'flex', alignItems:'center', justifyContent:'space-between', gap:8 }}>
            <span style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)' }}>
              Task #{taskId} · <span style={{ color:'var(--text-muted)' }}>running in Tasks board</span>
            </span>
            {onViewInTasks && (
              <button onClick={onViewInTasks} style={{
                fontSize:10, fontFamily:'var(--font-mono)', fontWeight:700,
                padding:'4px 10px', borderRadius:7, cursor:'pointer',
                background:'rgba(93,162,255,0.12)', border:'1px solid rgba(93,162,255,0.28)',
                color:'var(--accent)', letterSpacing:'0.08em', textTransform:'uppercase',
              }}>View in Tasks →</button>
            )}
          </div>
        )}
        {status === 'done' && result && (
          <div style={{ marginBottom:12, padding:'12px', borderRadius:10, background:'rgba(70,217,164,0.07)', border:'1px solid rgba(70,217,164,0.20)', fontSize:13, color:'var(--text-secondary)', whiteSpace:'pre-wrap', lineHeight:1.55 }}>
            <div style={{ marginBottom:8, display:'flex', alignItems:'center', justifyContent:'space-between', flexWrap:'wrap', gap:6 }}>
              <span style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--success)', letterSpacing:'0.08em', textTransform:'uppercase' }}>✓ Completed</span>
              <div style={{ display:'flex', gap:5 }}>
                <span style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'2px 7px', borderRadius:999, color:'#5da2ff', background:'rgba(93,162,255,0.10)', border:'1px solid rgba(93,162,255,0.20)', textTransform:'uppercase', letterSpacing:'0.08em' }}>{agent.name}</span>
                {taskId && <span style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'2px 7px', borderRadius:999, color:'var(--text-muted)', background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.09)', textTransform:'uppercase', letterSpacing:'0.08em' }}>Task #{taskId}</span>}
              </div>
            </div>
            {result}
          </div>
        )}
        {(error || (status === 'error')) && (
          <div style={{ marginBottom:12, padding:'10px 12px', borderRadius:10, background:'rgba(255,107,125,0.10)', border:'1px solid rgba(255,107,125,0.25)', display:'flex', alignItems:'center', justifyContent:'space-between', gap:8 }}>
            <span style={{ fontSize:12, color:'#ff6b7d' }}>{error || 'Task execution failed.'}</span>
            {taskId && onViewInTasks && (
              <button onClick={onViewInTasks} style={{
                fontSize:10, fontFamily:'var(--font-mono)', fontWeight:700,
                padding:'4px 10px', borderRadius:7, cursor:'pointer',
                background:'rgba(255,107,125,0.10)', border:'1px solid rgba(255,107,125,0.25)',
                color:'#ff6b7d', letterSpacing:'0.08em', textTransform:'uppercase',
              }}>View in Tasks →</button>
            )}
          </div>
        )}
        <div style={{ display:'flex', gap:8 }}>
          <button onClick={run} disabled={busy || !task.trim()} style={{ flex:1, padding:'10px', borderRadius:12, background:'linear-gradient(135deg,#6CB0FF,#4F93FF)', color:'#06111f', fontSize:13, fontWeight:800, border:'none', cursor:busy?'wait':'pointer', opacity:(busy||!task.trim())?0.6:1 }}>{busy ? 'Running…' : '▶ Run task'}</button>
          <button onClick={onClose} style={{ padding:'10px 18px', borderRadius:12, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-muted)', fontSize:13, cursor:'pointer' }}>Close</button>
        </div>
      </div>
    </div>
  );
}

// Map a backend agent record (AgentDefinition) to the card view-model.
function mapBackendAgent(a, agentTaskStats = {}) {
  const id = a.agent_id || a.id;
  const builtin = BUILTIN_AGENT_DEFS.find(b => b.id === id || b.name.toLowerCase() === (a.name || '').toLowerCase());
  const tags = a.tags || [];
  const origin = (tags.includes('onboarding') || tags.includes('specialist')) ? 'onboarding'
               : builtin ? 'builtin' : 'custom';
  return {
    id,
    name: a.name || 'Agent',
    role: a.role || 'Agent',
    icon: builtin?.icon || '◎',
    color: builtin?.color || '#5da2ff',
    status: a.status || 'idle',
    currentTask: null,
    runtime: a.preferred_runtime || a.runtime_id || 'hermes',
    model: a.model || '—',
    specializations: a.task_specializations || [],
    origin,
    tasksWeek: agentTaskStats.weekTotal || a.use_count || 0,
    avgMs: agentTaskStats.avgMs || 0,
    lastRun: a.last_used_at ? relTime(a.last_used_at) : '—',
    costPolicy: a.cost_policy || 'local_first',
    desc: a.description || builtin?.desc || '',
  };
}

// ── Main screen ───────────────────────────────────────────────────────────────
function AgentsScreen({ onNavigateToChat, onNavigateToTasks }) {
  const [showForm, setShowForm]         = React.useState(false);
  const [filter, setFilter]             = React.useState('all');
  const [runAgent, setRunAgent]         = React.useState(null);

  const [data, states, refetch] = useSafeData(null, {
    activity:  '/api/activity?limit=30',
    providers: '/api/providers',
    agents:    '/api/agents/',
    taskCounts: '/api/tasks/counts',
  }, { refreshMs: 30000 });

  // Derive last-run hints from activity feed per built-in agent name keyword
  const agentLastRun = React.useMemo(() => {
    const logs = data.activity?.logs || data.activity?.events || data.activity?.activity || [];
    const map = {};
    logs.forEach(log => {
      const text = ((log.message || '') + ' ' + (log.event_type || '')).toLowerCase();
      BUILTIN_AGENT_DEFS.forEach(a => {
        if (!map[a.id] && (text.includes(a.id) || text.includes(a.name.split(' ')[0].toLowerCase()))) {
          map[a.id] = relTime(log.created_at || log.timestamp);
        }
      });
    });
    return map;
  }, [data.activity]);

  // Wire real task counts per agent from /api/tasks/counts
  const agentTaskStats = React.useMemo(() => {
    const counts = data.taskCounts?.counts || {};
    return {
      weekDone:   counts.done_this_week   || 0,
      weekTodo:   counts.todo_this_week   || 0,
      weekTotal:  (counts.done_this_week  || 0) + (counts.in_progress_this_week || 0),
      avgMs:      counts.avg_task_ms      || 0,
      total:      counts.total            || 0,
    };
  }, [data.taskCounts]);

  // Derive CEO directive list from recent activity
  const ceoCycleData = React.useMemo(() => {
    const logs = data.activity?.logs || data.activity?.events || data.activity?.activity || [];
    return logs
      .filter(l => {
        const t = ((l.event_type || '') + ' ' + (l.message || '')).toLowerCase();
        return t.includes('agent') || t.includes('task') || t.includes('job');
      })
      .slice(0, 5)
      .map(l => ({
        to: (l.event_type || 'System').replace(/_/g, ' '),
        action: l.message || l.event_type || 'Activity',
        ago: relTime(l.created_at || l.timestamp),
      }));
  }, [data.activity]);

  // Real roster from the backend agent store (GET /api/agents/) merged with the
  // built-in catalog. Built-ins are shown only when the backend doesn't already
  // return an equivalent agent (matched by id or name).
  const backendAgents = React.useMemo(() => {
    const list = data.agents?.agents || (Array.isArray(data.agents) ? data.agents : []);
    return list.map(a => mapBackendAgent(a, agentTaskStats));
  }, [data.agents, agentTaskStats]);

  const agents = React.useMemo(() => {
    const seenIds   = new Set(backendAgents.map(a => a.id));
    const seenNames = new Set(backendAgents.map(a => (a.name || '').toLowerCase()));
    const builtins = BUILTIN_AGENT_DEFS
      .filter(b => !seenIds.has(b.id) && !seenNames.has(b.name.toLowerCase()))
      .map(a => ({ ...a, status:'idle', currentTask:null, tasksWeek: agentTaskStats.weekTotal || 0, avgMs: agentTaskStats.avgMs || 0, lastRun: agentLastRun[a.id] || '—', origin:'builtin' }));
    return [...builtins, ...backendAgents];
  }, [backendAgents, agentLastRun, agentTaskStats]);

  // Navigate to Tasks board
  const handleViewTasks = () => onNavigateToTasks && onNavigateToTasks();

  const handleCreate = async (payload) => {
    await api.createAgent(payload);
    refetch();
  };

  const builtIn  = agents.filter(a => a.origin === 'builtin' && a.id !== 'ceo');
  const custom   = agents.filter(a => a.origin === 'custom' || a.origin === 'onboarding');

  const filtered = filter === 'all'     ? agents.filter(a => a.id !== 'ceo')
                 : filter === 'builtin' ? builtIn
                 : custom;

  return (
    <div style={{ padding:'20px 16px 48px', maxWidth:1100, margin:'0 auto' }}>
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:6 }}>Autonomous Agency</div>
      <div style={{ display:'flex', alignItems:'flex-end', justifyContent:'space-between', flexWrap:'wrap', gap:10, marginBottom:18 }}>
        <div>
          <h1 style={{ fontSize:26, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', lineHeight:1.1, marginBottom:4 }}>Agent Roster</h1>
          <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.5, maxWidth:480 }}>Built-in specialist agents + any custom agents you create. Complete onboarding to provision company-specific specialists.</p>
        </div>
        <button onClick={() => setShowForm(true)} style={{ display:'inline-flex', alignItems:'center', gap:7, padding:'10px 20px', borderRadius:999, fontSize:13, fontWeight:800, cursor:'pointer', background:'linear-gradient(135deg,#6CB0FF,#4F93FF)', color:'#06111f', border:'none', boxShadow:'0 6px 20px rgba(93,162,255,0.22)' }}>+ New agent</button>
      </div>

      <CEOCyclePanel directives={ceoCycleData} loading={states.activity?.loading}/>
      <PipelinePanel/>
      <RuntimesBar/>

      {showForm && <NewAgentForm onCreate={handleCreate} onClose={() => setShowForm(false)}/>}
      {runAgent && <RunTaskModal agent={runAgent} onClose={() => setRunAgent(null)} onViewInTasks={handleViewTasks}/>}

      {states.agents?.error && (
        <div style={{ padding:'10px 14px', borderRadius:12, background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.20)', marginBottom:12, fontSize:12, color:'#ff6b7d' }}>
          Couldn't load the live agent roster ({states.agents.error}). Showing the built-in catalog only.
        </div>
      )}

      {/* Filter tabs */}
      <div style={{ display:'flex', gap:6, marginBottom:14, flexWrap:'wrap' }}>
        {[
          { id:'all',     label:`All (${agents.filter(a=>a.id!=='ceo').length})` },
          { id:'builtin', label:`Built-in (${builtIn.length})` },
          { id:'custom',  label:`Custom (${custom.length})` },
        ].map(f => (
          <button key={f.id} onClick={() => setFilter(f.id)} style={{ padding:'5px 14px', borderRadius:999, fontSize:12, fontWeight:600, cursor:'pointer', background:filter===f.id?'rgba(93,162,255,0.15)':'rgba(255,255,255,0.04)', border:`1px solid ${filter===f.id?'rgba(93,162,255,0.35)':'rgba(255,255,255,0.09)'}`, color:filter===f.id?'#fff':'var(--text-muted)', transition:'all 0.15s' }}>{f.label}</button>
        ))}
      </div>

      {/* Honest callout: provisioned specialists need onboarding */}
      {(filter === 'all' || filter === 'builtin') && (
        <div style={{ padding:'10px 14px', borderRadius:12, background:'rgba(93,162,255,0.05)', border:'1px solid rgba(93,162,255,0.12)', marginBottom:12, fontSize:12, color:'var(--text-muted)', lineHeight:1.5 }}>
          Company-specific specialists (Commerce, Content, Analytics…) appear here after you complete the Onboarding flow for your site.
        </div>
      )}

      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(280px,1fr))', gap:14 }}>
        {filtered.map(agent => (
          <AgentCard key={agent.id} agent={agent} onChat={() => onNavigateToChat && onNavigateToChat(agent)} onRun={() => setRunAgent(agent)}/>
        ))}
        {filtered.length === 0 && (
          <div style={{ gridColumn:'1/-1', padding:'32px 0', textAlign:'center', fontSize:13, color:'var(--text-muted)' }}>
            No agents yet. Create one using the button above.
          </div>
        )}
      </div>
    </div>
  );
}

export { AgentsScreen };
export default AgentsScreen;
