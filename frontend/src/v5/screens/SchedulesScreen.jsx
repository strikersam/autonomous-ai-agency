/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import Glyph from '../components/ui/Glyph';
import * as api from '../../api';
import { useSafeData } from '../hooks/useSafeData';


// schedules.jsx — Schedules V5.0 with smart pre-built git action templates

// Relative-time helper for ISO timestamps (last_run). Returns '—' for null/invalid.
function relTime(iso) {
  if (!iso) return '—';
  const t = new Date(iso).getTime();
  // BUG-09: guard against epoch 0 / invalid dates that produce absurd diffs (> 50 years)
  if (Number.isNaN(t) || t <= 0 || t < new Date('2024-01-01').getTime()) return '—';
  const diff = Math.floor((Date.now() - t) / 1000);
  if (diff < 0) return 'just now';
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

// Normalise a raw backend schedule into the shape the rows/stats render against.
// Derives fields the backend does not provide (category from tags, builtIn from a tag).
function normalizeJob(s) {
  const tags = Array.isArray(s.tags) ? s.tags : [];
  const category = (tags[0] || 'general');
  return {
    id: s.id ?? s.job_id,
    name: s.name || s.job_id || 'Untitled schedule',
    cron: s.cron || s.schedule || '—',
    category: CAT_CONFIG[category] ? category : 'general',
    status: s.status || (s.enabled === false ? 'paused' : 'active'),
    runs: s.run_count ?? 0,
    fails: s.failures ?? s.fail_count ?? 0,
    lastRun: relTime(s.last_run),
    approvalGate: s.approval_gate ?? s.requires_approval ?? false,
    builtIn: tags.includes('built-in') || tags.includes('builtin'),
    description: s.description || '',
    tags,
  };
}

function errText(e, fallback) {
  const detail = e?.response?.data?.detail;
  return detail ? api.fmtErr(detail) : (e?.message || fallback);
}

// `cron` is the human-readable cadence shown in the UI; `cronExpr` is the real
// cron expression sent to the backend. Event-driven templates (webhook/commit/
// CI triggers) have cronExpr:null and can't be added as cron schedules yet.
const SMART_TEMPLATES = [
  // Security
  { id:'tmpl-cve',      cat:'security', icon:'🔒', name:'CVE Dependency Audit',         cron:'Weekly Mon 02:00', cronExpr:'0 2 * * 1',   desc:'pip/npm audit for known vulnerabilities. Auto-creates fix tasks.', gate:false },
  { id:'tmpl-sast',     cat:'security', icon:'🔒', name:'SAST Code Scan (Bandit)',       cron:'On push + daily',  cronExpr:null,          desc:'Static analysis across all Python. Raises P2 alerts on findings.', gate:false },
  { id:'tmpl-secrets',  cat:'security', icon:'🔒', name:'Secret Detection Scan',         cron:'On every commit',  cronExpr:null,          desc:'Grep for leaked API keys, tokens, and passwords in git history.', gate:false },
  // Quality
  { id:'tmpl-tests',    cat:'quality',  icon:'⚙', name:'Daily Test Run + Auto-Fix',    cron:'Daily 03:00 UTC',  cronExpr:'0 3 * * *',   desc:'Full pytest suite. Failing tests become P1 fix tasks automatically.', gate:false },
  { id:'tmpl-coverage', cat:'quality',  icon:'⚙', name:'Test Coverage Report',          cron:'Weekly Wed 06:00', cronExpr:'0 6 * * 3',   desc:'Find modules with <80% coverage. Generate missing test stubs.', gate:false },
  { id:'tmpl-lint',     cat:'quality',  icon:'⚙', name:'Code Quality & Lint Check',    cron:'On PR + daily',    cronExpr:null,          desc:'Ruff/ESLint/Prettier across all changed files. Auto-fix safe issues.', gate:false },
  { id:'tmpl-todo',     cat:'quality',  icon:'⚙', name:'FIXME / TODO Cleanup',          cron:'Weekly Wed 06:00', cronExpr:'0 6 * * 3',   desc:'Resolve FIXME, TODO:FIX, and HACK:URGENT markers automatically.', gate:true },
  // SEO & Performance
  { id:'tmpl-seo',      cat:'seo',      icon:'🔍', name:'SEO Health Audit',             cron:'Weekly Mon 06:00', cronExpr:'0 6 * * 1',   desc:'Check meta tags, Open Graph, sitemap freshness, and broken links.', gate:false },
  { id:'tmpl-perf',     cat:'perf',     icon:'⚡', name:'Lighthouse Performance Scan',  cron:'Daily 06:00 UTC',  cronExpr:'0 6 * * *',   desc:'Core Web Vitals, LCP, CLS, FID on key pages. Alert on regressions.', gate:false },
  { id:'tmpl-bundle',   cat:'perf',     icon:'⚡', name:'Bundle Size Check',            cron:'On every PR',      cronExpr:null,          desc:'Warn if JS bundle grows >5%. Block merge if >20% regression.', gate:false },
  // Release
  { id:'tmpl-dep',      cat:'release',  icon:'◉', name:'Dependency Upgrade (safe)',    cron:'Weekly Mon 04:00', cronExpr:'0 4 * * 1',   desc:'Safe minor/patch upgrades only. Opens PR with full test run.', gate:true },
  { id:'tmpl-changelog',cat:'release',  icon:'◉', name:'Daily Changelog Check',        cron:'Daily 05:00 UTC',  cronExpr:'0 5 * * *',   desc:'Verify CHANGELOG.md is up to date with merged PRs.', gate:false },
  // Monitoring
  { id:'tmpl-errors',   cat:'ops',      icon:'◎', name:'Error Log Monitor',            cron:'Every 15 min',     cronExpr:'*/15 * * * *',desc:'Tail server logs for ERROR/CRITICAL. Auto-creates self-healing tasks.', gate:false },
  { id:'tmpl-uptime',   cat:'ops',      icon:'◎', name:'Uptime & API Health Check',    cron:'Every 5 min',      cronExpr:'*/5 * * * *', desc:'Ping all registered environments. Alert on 3 consecutive failures.', gate:false },
  { id:'tmpl-regression',cat:'ops',     icon:'◎', name:'Regression Test on Merge',     cron:'On merge to main', cronExpr:null,          desc:'Full integration test suite on every merge to main.', gate:false },
  // Incident
  { id:'tmpl-ci-fail',  cat:'ops',      icon:'◎', name:'CI Failure Auto-Fix',          cron:'On CI failure',    cronExpr:null,          desc:'GitHub Actions webhook → Dev Agent investigates and fixes.', gate:true },
];

const CAT_CONFIG = {
  security: { color:'var(--warning)', label:'Security',    icon:'🔒', bg:'color-mix(in oklab, var(--warning) 8%, transparent)' },
  quality:  { color:'var(--accent)', label:'Quality',     icon:'⚙', bg:'color-mix(in oklab, var(--accent) 7%, transparent)' },
  seo:      { color:'var(--success)', label:'SEO',         icon:'🔍', bg:'color-mix(in oklab, var(--success) 7%, transparent)' },
  perf:     { color:'var(--violet)', label:'Performance', icon:'⚡', bg:'color-mix(in oklab, var(--violet) 7%, transparent)' },
  release:  { color:'var(--accent)', label:'Release',     icon:'◉', bg:'color-mix(in oklab, var(--accent) 7%, transparent)' },
  ops:      { color:'var(--text-muted)', label:'Ops', icon:'◎', bg:'color-mix(in oklab, var(--ink) 3%, transparent)' },
  agency:   { color:'var(--violet)', label:'Agency',      icon:'◎', bg:'color-mix(in oklab, var(--violet) 7%, transparent)' },
  dev:      { color:'var(--accent)', label:'Dev',         icon:'⚙', bg:'color-mix(in oklab, var(--accent) 7%, transparent)' },
};

function ScheduleRow({ job, onToggle, onRunNow, busy, justRan }) {
  const cat = CAT_CONFIG[job.category] || CAT_CONFIG.ops;
  const isActive = job.status === 'active';
  const running = !!justRan;
  const handleRun = () => { onRunNow && onRunNow(job.id); };

  return (
    <div style={{ display:'flex', alignItems:'center', gap:10, padding:'11px 16px', borderBottom:'1px solid color-mix(in oklab, var(--ink) 5%, transparent)', transition:'background 0.15s' }}
    onMouseEnter={e=>e.currentTarget.style.background='color-mix(in oklab, var(--ink) 2%, transparent)'}
    onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
      <div style={{ width:28, height:28, borderRadius:9, flexShrink:0, background:cat.bg, display:'flex', alignItems:'center', justifyContent:'center', fontSize:14 }}><Glyph g={cat.icon}/></div>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:1, flexWrap:'wrap' }}>
          <span style={{ fontSize:13, fontWeight:600, color:isActive?'var(--text-primary)':'var(--text-muted)' }}>{job.name}</span>
          {job.builtIn && <span style={{ fontSize:13, padding:'1px 5px', borderRadius:999, color:'var(--text-muted)', background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 9%, transparent)' }}>built-in</span>}
          {job.approvalGate && <span style={{ fontSize:13, padding:'1px 5px', borderRadius:999, color:'var(--warning)', background:'color-mix(in oklab, var(--warning) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--warning) 20%, transparent)' }}>approval</span>}
          {job.tags.includes('run-once') && <span style={{ fontSize:13, padding:'1px 5px', borderRadius:999, color:'var(--violet)', background:'color-mix(in oklab, var(--violet) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--violet) 20%, transparent)' }}>run-once</span>}
          {job.tags.includes('agency') && <span style={{ fontSize:13, padding:'1px 5px', borderRadius:999, color:'var(--accent)', background:'color-mix(in oklab, var(--accent) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 20%, transparent)' }}>agency</span>}
          {job.tags.includes('company-agency') && <span style={{ fontSize:13, padding:'1px 5px', borderRadius:999, color:'var(--success)', background:'color-mix(in oklab, var(--success) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--success) 20%, transparent)' }}>company</span>}
        </div>
        {job.description && (
          <div style={{ fontSize:13, color:'var(--text-muted)', marginBottom:2, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', maxWidth:'100%' }}>{job.description}</div>
        )}
        <div style={{ display:'flex', gap:7, fontSize:13, fontFamily:'var(--font-mono)', color:'var(--text-muted)', flexWrap:'wrap' }}>
          <span>{job.cron}</span><span>·</span>
          <span>Last: <span style={{ color:'var(--text-muted)' }}>{job.lastRun}</span></span><span>·</span>
          <span>{job.runs} runs · <span style={{ color:job.fails>0?'var(--danger)':'var(--text-muted)' }}>{job.fails} fails</span></span>
        </div>
      </div>
      <button onClick={()=>onToggle&&onToggle(job)} disabled={busy} style={{ width:34, height:20, borderRadius:999, padding:3, cursor:busy?'wait':'pointer', opacity:busy?0.6:1, background:isActive?'var(--accent)':'color-mix(in oklab, var(--ink) 10%, transparent)', border:`1px solid ${isActive?'color-mix(in oklab, var(--accent) 50%, transparent)':'color-mix(in oklab, var(--ink) 15%, transparent)'}`, transition:'all 0.2s', display:'flex', alignItems:'center', justifyContent:isActive?'flex-end':'flex-start', flexShrink:0 }}>
        <div style={{ width:14, height:14, borderRadius:'50%', background:'#fff', boxShadow:'0 1px 3px color-mix(in oklab, var(--shade) 30%, transparent)' }}/>
      </button>
      <button onClick={handleRun} disabled={running} style={{ padding:'4px 10px', borderRadius:8, fontSize:13, fontWeight:600, cursor:running?'wait':'pointer', background:running?'color-mix(in oklab, var(--accent) 6%, transparent)':'color-mix(in oklab, var(--accent) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 22%, transparent)', color:running?'var(--text-muted)':'var(--accent)', transition:'all 0.15s', whiteSpace:'nowrap', flexShrink:0 }}>
        {running ? <span style={{ display:'flex', alignItems:'center', gap:4 }}><div style={{ width:9,height:9,border:'2px solid color-mix(in oklab, var(--accent) 20%, transparent)',borderTopColor:'var(--accent)',borderRadius:'50%',animation:'spin 0.8s linear infinite' }}/>triggered</span> : '↺ Run'}
      </button>
    </div>
  );
}

function TemplateCard({ tmpl, onAdd, added }) {
  const cat = CAT_CONFIG[tmpl.cat] || CAT_CONFIG.ops;
  return (
    <div style={{ borderRadius:14, border:`1px solid ${added?'color-mix(in oklab, var(--success) 22%, transparent)':'color-mix(in oklab, var(--ink) 8%, transparent)'}`, background:added?'color-mix(in oklab, var(--success) 5%, transparent)':'color-mix(in oklab, var(--ink) 2.5%, transparent)', padding:'12px 14px', transition:'all 0.2s ease' }}
    onMouseEnter={e=>{ if(!added){e.currentTarget.style.borderColor='color-mix(in oklab, var(--accent) 20%, transparent)'; e.currentTarget.style.background='color-mix(in oklab, var(--accent) 4%, transparent)'; }}}
    onMouseLeave={e=>{ if(!added){e.currentTarget.style.borderColor='color-mix(in oklab, var(--ink) 8%, transparent)'; e.currentTarget.style.background='color-mix(in oklab, var(--ink) 2.5%, transparent)'; }}}>
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:8, marginBottom:6 }}>
        <div style={{ display:'flex', gap:8, alignItems:'flex-start' }}>
          <span style={{ fontSize:16, flexShrink:0 }}><Glyph g={tmpl.icon}/></span>
          <div>
            <div style={{ fontSize:13, fontWeight:700, color:added?'var(--success)':'var(--text-primary)', marginBottom:2 }}>{tmpl.name}</div>
            <span style={{ fontSize:13, padding:'2px 6px', borderRadius:999, color:cat.color, background:`color-mix(in oklab, ${cat.color} 7%, transparent)`, border:`1px solid color-mix(in oklab, ${cat.color} 13%, transparent)` }}>{cat.label}</span>
          </div>
        </div>
        {added
          ? <span style={{ fontSize:13, color:'var(--success)', flexShrink:0 }}>✓ Added</span>
          : <button onClick={()=>onAdd(tmpl)} style={{ padding:'4px 12px', borderRadius:8, fontSize:13, fontWeight:700, cursor:'pointer', background:'color-mix(in oklab, var(--accent) 12%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 25%, transparent)', color:'var(--accent)', flexShrink:0, whiteSpace:'nowrap', transition:'all 0.15s' }}>+ Add</button>
        }
      </div>
      <div style={{ fontSize:13, color:'var(--text-muted)', lineHeight:1.5, marginBottom:5 }}>{tmpl.desc}</div>
      <div style={{ display:'flex', alignItems:'center', gap:8 }}>
        <span style={{ fontSize:13, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}><Glyph g="⏱"/> {tmpl.cron}</span>
        {tmpl.gate && <span style={{ fontSize:13, padding:'1px 6px', borderRadius:999, color:'var(--warning)', background:'color-mix(in oklab, var(--warning) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--warning) 18%, transparent)' }}>approval gate</span>}
      </div>
    </div>
  );
}

function NewJobForm({ onClose, onCreate }) {
  const [name, setName] = React.useState('');
  const [cron, setCron] = React.useState('0 9 * * *');
  const [inst, setInst] = React.useState('');
  const [gate, setGate] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState(null);
  // Backend expects a real cron expression (ScheduleCreateRequest.cron, min len 9).
  const presets = [
    { label:'Every 15 min', cron:'*/15 * * * *' },
    { label:'Hourly',       cron:'0 * * * *' },
    { label:'Daily 09:00',  cron:'0 9 * * *' },
    { label:'Weekdays 09:00', cron:'0 9 * * 1-5' },
    { label:'Weekly Mon',   cron:'0 9 * * 1' },
  ];
  const submit = async () => {
    if (!name.trim() || busy) return;
    setBusy(true); setError(null);
    try {
      await onCreate({ name:name.trim(), cron, instruction:inst.trim(), approval_gate:gate });
      onClose();
    } catch (e) {
      setError(errText(e, 'Could not create schedule (check the cron expression).'));
      setBusy(false);
    }
  };
  return (
    <div style={{ padding:'14px', borderRadius:14, background:'color-mix(in oklab, var(--accent) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 18%, transparent)', marginBottom:14, animation:'fadeSlideUp 0.25s ease-out' }}>
      <div style={{ fontSize:13, fontWeight:700, color:'var(--text-secondary)', marginBottom:10 }}>Custom schedule</div>
      <div style={{ display:'flex', flexDirection:'column', gap:9 }}>
        <input value={name} onChange={e=>setName(e.target.value)} placeholder="Schedule name"
          style={{ padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 4%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:14, outline:'none', fontFamily:'var(--font-main)' }}
          onFocus={e=>e.target.style.borderColor='color-mix(in oklab, var(--accent) 45%, transparent)'} onBlur={e=>e.target.style.borderColor='color-mix(in oklab, var(--ink) 10%, transparent)'}/>
        <textarea value={inst} onChange={e=>setInst(e.target.value)} placeholder="What should the agent do? (plain English)" rows={2}
          style={{ padding:'9px 12px', borderRadius:10, resize:'none', background:'color-mix(in oklab, var(--ink) 4%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:14, outline:'none', fontFamily:'var(--font-main)' }}
          onFocus={e=>e.target.style.borderColor='color-mix(in oklab, var(--accent) 45%, transparent)'} onBlur={e=>e.target.style.borderColor='color-mix(in oklab, var(--ink) 10%, transparent)'}/>
        <div style={{ display:'flex', gap:5, flexWrap:'wrap' }}>
          {presets.map(p => <button key={p.cron} onClick={()=>setCron(p.cron)} style={{ padding:'4px 10px', borderRadius:999, fontSize:13, cursor:'pointer', background:cron===p.cron?'color-mix(in oklab, var(--accent) 15%, transparent)':'color-mix(in oklab, var(--ink) 4%, transparent)', border:`1px solid ${cron===p.cron?'color-mix(in oklab, var(--accent) 35%, transparent)':'color-mix(in oklab, var(--ink) 9%, transparent)'}`, color:cron===p.cron?'var(--text-primary)':'var(--text-muted)', transition:'all 0.15s' }}>{p.label}</button>)}
        </div>
        <input value={cron} onChange={e=>setCron(e.target.value)} placeholder="cron expression (e.g. 0 9 * * *)"
          style={{ padding:'8px 12px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 4%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:13, fontFamily:'var(--font-mono)', outline:'none' }}/>
        <label style={{ display:'flex', alignItems:'center', gap:7, fontSize:13, color:'var(--text-tertiary)', cursor:'pointer' }}>
          <input type="checkbox" checked={gate} onChange={e=>setGate(e.target.checked)} style={{ accentColor:'var(--accent)' }}/>
          Require approval before execution
        </label>
        {error && <div style={{ padding:'8px 12px', borderRadius:10, background:'color-mix(in oklab, var(--danger) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 25%, transparent)', color:'var(--danger)', fontSize:13 }}>{error}</div>}
        <div style={{ display:'flex', gap:8 }}>
          <button onClick={submit} disabled={busy} style={{ flex:1, padding:'9px', borderRadius:10, background:'var(--accent)', color:'var(--on-accent)', fontSize:14, fontWeight:700, border:'none', cursor:busy?'wait':'pointer', opacity:busy?0.7:1 }}>{busy ? 'Creating…' : 'Create'}</button>
          <button onClick={onClose} disabled={busy} style={{ padding:'9px 16px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-muted)', fontSize:14, cursor:'pointer' }}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

function SchedulesScreen() {
  const [showForm, setShowForm]       = React.useState(false);
  const [showTemplates, setShowTmpl]  = React.useState(false);
  const [addedTmpls, setAddedTmpls]   = React.useState(new Set());
  const [tmplCat, setTmplCat]         = React.useState('all');
  const [busyId, setBusyId]           = React.useState(null);
  const [justRan, setJustRan]         = React.useState(null);
  const [actionErr, setActionErr]     = React.useState(null);
  // BUG-16: mounted guard so runNow setTimeout doesn't update state after unmount
  const mountedRef = React.useRef(true);
  const runNowTimerRef = React.useRef(null);
  React.useEffect(() => () => {
    mountedRef.current = false;
    if (runNowTimerRef.current) clearTimeout(runNowTimerRef.current);
  }, []);

  const [data, states, refetch] = useSafeData(null, { schedules: '/api/schedules/' }, { refreshMs: 30000 });
  const jobs = (data.schedules?.schedules || []).map(normalizeJob);

  const toggle = async (job) => {
    setBusyId(job.id); setActionErr(null);
    try {
      if (job.status === 'active') await api.pauseSchedule(job.id);
      else await api.resumeSchedule(job.id);
      await refetch();
    } catch (e) { setActionErr(errText(e, 'Could not update the schedule.')); }
    finally { setBusyId(null); }
  };

  const runNow = async (id) => {
    setJustRan(id); setActionErr(null);
    try { await api.triggerSchedule(id); await refetch(); }
    catch (e) { setActionErr(errText(e, 'Could not trigger the schedule.')); }
    finally {
      if (runNowTimerRef.current) clearTimeout(runNowTimerRef.current);
      runNowTimerRef.current = setTimeout(() => { if (mountedRef.current) setJustRan(null); }, 1500);
    }
  };

  const createSchedule = async (payload) => {
    await api.createSchedule(payload);
    await refetch();
  };
  const addTmpl = async (tmpl) => {
    setActionErr(null);
    // Event-driven templates (no cron expression) can't be added as cron schedules yet.
    if (!tmpl.cronExpr) {
      setActionErr(`"${tmpl.name}" runs on an event trigger (${tmpl.cron}) — webhook/event schedules aren't supported yet.`);
      return;
    }
    try {
      await createSchedule({ name: tmpl.name, cron: tmpl.cronExpr, instruction: tmpl.desc, approval_gate: tmpl.gate, tags: [tmpl.cat] });
      setAddedTmpls(p => new Set([...p, tmpl.id]));
    } catch (e) {
      setActionErr(errText(e, `Could not add "${tmpl.name}".`));
    }
  };

  const totalFails = jobs.reduce((s,j)=>s+j.fails,0);

  return (
    <div style={{ padding:'20px 16px 48px', maxWidth:1200, margin:'0 auto' }}>
      <div style={{ display:'flex', alignItems:'flex-end', justifyContent:'space-between', flexWrap:'wrap', gap:10, marginBottom:16 }}>
        <div>
          <h1 style={{ fontSize:26, fontWeight:700, color:'var(--text-primary)', letterSpacing:'-0.04em', lineHeight:1.1, marginBottom:4 }}>Schedules</h1>
          <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.5, maxWidth:460 }}>
            Autopilot jobs that keep your codebase healthy. Add from the smart template library or write your own in plain English.
          </p>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button onClick={()=>setShowTmpl(o=>!o)} style={{ padding:'10px 18px', borderRadius:999, fontSize:14, fontWeight:700, cursor:'pointer', background:'color-mix(in oklab, var(--success) 12%, transparent)', border:'1px solid color-mix(in oklab, var(--success) 28%, transparent)', color:'var(--success)' }}>
            {showTemplates ? 'Hide templates' : '✦ Template library'}
          </button>
          <button onClick={()=>setShowForm(true)} style={{ padding:'10px 18px', borderRadius:999, fontSize:14, fontWeight:700, cursor:'pointer', background:'linear-gradient(135deg,var(--accent),var(--accent))', color:'var(--on-accent)', border:'none', boxShadow:'0 6px 20px color-mix(in oklab, var(--accent) 22%, transparent)' }}>+ Custom</button>
        </div>
      </div>

      {/* Stats */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fit,minmax(150px,1fr))', gap:10, marginBottom:16 }}>
        {[
          { label:'Active', value:jobs.filter(j=>j.status==='active').length, color:'var(--success)' },
          { label:'Total runs', value:jobs.reduce((s,j)=>s+j.runs,0).toLocaleString(), color:'var(--accent)' },
          { label:'Failures', value:totalFails, color:totalFails>0?'var(--danger)':'var(--text-muted)' },
        ].map(s => (
          <div key={s.label} style={{ padding:'10px 14px', borderRadius:12, background:'color-mix(in oklab, var(--ink) 3%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)' }}>
            <div style={{ fontSize:20, fontWeight:700, color:s.color, letterSpacing:'-0.03em' }}>{s.value}</div>
            <div style={{ fontSize:13, color:'var(--text-muted)', marginTop:2 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Template library */}
      {showTemplates && (
        <div style={{ borderRadius:14, border:'1px solid color-mix(in oklab, var(--success) 18%, transparent)', background:'color-mix(in oklab, var(--success) 3%, transparent)', padding:'16px', marginBottom:16, animation:'fadeSlideUp 0.25s ease-out' }}>
          <div style={{ fontSize:14, fontWeight:700, color:'var(--success)', marginBottom:4 }}><Glyph g="✦"/> Smart Template Library</div>
          <div style={{ fontSize:13, color:'var(--text-muted)', marginBottom:12 }}>{SMART_TEMPLATES.length} pre-built schedules for security, quality, SEO, performance, ops, and release workflows.</div>
          <div style={{ display:'flex', gap:6, marginBottom:12, flexWrap:'wrap' }}>
            {['all','security','quality','seo','perf','release','ops'].map(c => {
              const cc = CAT_CONFIG[c];
              return <button key={c} onClick={()=>setTmplCat(c)} style={{ padding:'4px 12px', borderRadius:999, fontSize:13, cursor:'pointer', background:tmplCat===c?'color-mix(in oklab, var(--accent) 15%, transparent)':'color-mix(in oklab, var(--ink) 4%, transparent)', border:`1px solid ${tmplCat===c?'color-mix(in oklab, var(--accent) 32%, transparent)':'color-mix(in oklab, var(--ink) 9%, transparent)'}`, color:tmplCat===c?'var(--text-primary)':'var(--text-muted)', textTransform:'capitalize', transition:'all 0.15s' }}>{c==='all'?'All':cc?.label||c}</button>;
            })}
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(260px,1fr))', gap:8 }}>
            {SMART_TEMPLATES.filter(t=>tmplCat==='all'||t.cat===tmplCat).map(tmpl => (
              <TemplateCard key={tmpl.id} tmpl={tmpl} onAdd={addTmpl} added={addedTmpls.has(tmpl.id)||jobs.some(j=>j.name===tmpl.name)}/>
            ))}
          </div>
        </div>
      )}

      {showForm && <NewJobForm onClose={()=>setShowForm(false)} onCreate={createSchedule}/>}

      {actionErr && <div style={{ marginBottom:12, padding:'9px 13px', borderRadius:10, background:'color-mix(in oklab, var(--danger) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 25%, transparent)', color:'var(--danger)', fontSize:13 }}>{actionErr}</div>}

      {/* Active jobs */}
      <div style={{ borderRadius:16, border:'1px solid color-mix(in oklab, var(--ink) 9%, transparent)', background:'color-mix(in oklab, var(--ink) 2.5%, transparent)', overflow:'hidden' }}>
        <div style={{ padding:'10px 16px', borderBottom:'1px solid color-mix(in oklab, var(--ink) 6%, transparent)', fontSize:13, color:'var(--text-muted)' }}>Scheduled jobs ({jobs.length})</div>
        {states.schedules?.loading && jobs.length === 0 ? (
          <div style={{ padding:'24px 16px', fontSize:14, color:'var(--text-muted)' }}>Loading schedules…</div>
        ) : states.schedules?.error ? (
          <div style={{ padding:'18px 16px', fontSize:14, color:'var(--danger)' }}>Couldn't load schedules: {states.schedules.error}</div>
        ) : jobs.length === 0 ? (
          <div style={{ padding:'24px 16px', fontSize:14, color:'var(--text-muted)' }}>No schedules configured yet. Add one from the template library or create a custom job.</div>
        ) : (
          jobs.map(job => <ScheduleRow key={job.id} job={job} onToggle={toggle} onRunNow={runNow} busy={busyId===job.id} justRan={justRan===job.id}/>)
        )}
      </div>
    </div>
  );
}

export { SchedulesScreen };
export default SchedulesScreen;
