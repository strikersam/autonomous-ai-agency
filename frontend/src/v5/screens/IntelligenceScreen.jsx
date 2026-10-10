/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import Glyph from '../components/ui/Glyph';
import * as api from '../../api';
import { COMPANY_ID_KEY } from './CompanyScreen';

// intelligence.jsx — Commerce Intelligence
// Competitor monitoring + trend scanning with live AI analysis via /api/chat/send

// Stay under the ~100s hosted-edge cutoff so a stalled provider shows an error instead of spinning forever.
const BRIEFING_TIMEOUT_MS = 95000;

const DEFAULT_KEYWORDS = [
  { id:'k-default-1', keyword:'AI shopping assistants',   category:'AI & Commerce', tracked:true },
  { id:'k-default-2', keyword:'checkout conversion rate', category:'Conversion',    tracked:true },
  { id:'k-default-3', keyword:'customer retention email', category:'Retention',     tracked:true },
  { id:'k-default-4', keyword:'ecommerce market trends',  category:'Market Intel',  tracked:true },
];

// Accept "competitor.com" as well as full URLs; only http(s) is ever linked.
const safeHref = url => {
  const u = String(url || '').trim();
  if (!u) return null;
  const full = /^https?:\/\//i.test(u) ? u : `https://${u}`;
  try { const p = new URL(full); return /^https?:$/.test(p.protocol) ? p.href : null; } catch { return null; }
};

const TRACK_OPTIONS = ['pricing','campaigns','new-arrivals','features','tech-stack','seo','social'];
const trackColors   = { pricing:'var(--warning)', campaigns:'var(--danger)', 'new-arrivals':'var(--success)', features:'var(--accent)', 'tech-stack':'var(--violet)', seo:'var(--accent)', social:'var(--warning)' };

// ── Reusable Explain tooltip (imported from skills.jsx via window) ─────────────
function TipBubble({ label, children }) {
  const [open, setOpen] = React.useState(false);
  return (
    <span style={{ position:'relative', display:'inline-flex', alignItems:'center', gap:4 }}>
      <button onClick={()=>setOpen(o=>!o)} style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--accent)', background:'color-mix(in oklab, var(--accent) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 22%, transparent)', borderRadius:999, padding:'2px 9px', cursor:'pointer', transition:'all 0.15s' }}>
        {label} ?
      </button>
      {open && (
        <div style={{ position:'absolute', bottom:'calc(100% + 6px)', left:0, zIndex:99, background:'color-mix(in oklab, var(--bg-surface) 98%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 25%, transparent)', borderRadius:12, padding:'10px 12px', minWidth:240, maxWidth:'min(300px, calc(100vw - 24px))', fontSize:13, color:'var(--text-secondary)', lineHeight:1.6, boxShadow:'0 12px 32px color-mix(in oklab, var(--shade) 55%, transparent)', animation:'fadeSlideUp 0.15s ease-out' }}
          onClick={e=>e.stopPropagation()}>
          {children}
          <button onClick={()=>setOpen(false)} style={{ display:'block', marginTop:8, fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--text-muted)', background:'none', border:'none', cursor:'pointer' }}>Close ✕</button>
        </div>
      )}
    </span>
  );
}

// ── AI Analysis Panel ─────────────────────────────────────────────────────────
function AIInsightsPanel({ company, competitors, keywords, onNavigate }) {
  const [analysis,  setAnalysis]  = React.useState('');
  const [loading,   setLoading]   = React.useState(false);
  const [error,     setError]     = React.useState('');
  const [generated, setGenerated] = React.useState(false);

  const runAnalysis = async () => {
    setLoading(true); setError(''); setAnalysis('');
    try {
      const compList  = competitors.map(c => `${c.name} (${c.url})`).join(', ');
      const kwList    = keywords.filter(k=>k.tracked).map(k=>k.keyword).join(', ');
      const prompt = `You are a sharp e-commerce growth analyst. The company is "${company}" — a Shopify-based fashion/commerce store.

Tracked competitors: ${compList}
Monitored keywords: ${kwList}

Provide a concise, actionable intelligence briefing covering:
1. What tactics are competitors likely running right now based on their profiles (2-3 specific observations)
2. Which of the tracked keywords represent the biggest opportunity for this store (pick top 2)
3. Three concrete recommended actions the store should take this month — be specific and practical
4. One emerging trend in ecommerce they should watch

Keep it sharp, practical, and under 300 words. No fluff. Write in plain English for a non-technical founder.`;

      const { data } = await api.chatSend(prompt, null, null, null, null, false, false, null, null, null, { timeout: BRIEFING_TIMEOUT_MS });
      const result = data?.response || '';
      if (!result) throw new Error('No response from AI.');
      setAnalysis(result);
      setGenerated(true);
    } catch (e) {
      const errMsg = e?.code === 'ECONNABORTED'
        ? 'The AI provider took too long to answer. Try again in a moment.'
        : e?.response?.data?.detail ? api.fmtErr(e.response.data.detail) : (e?.message || 'Unknown error');
      setError('Could not generate analysis: ' + errMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ borderRadius:14, border:'1px solid color-mix(in oklab, var(--violet) 20%, transparent)', background:'color-mix(in oklab, var(--violet) 4%, transparent)', padding:'16px', marginBottom:20 }}>
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:12, flexWrap:'wrap', marginBottom:12 }}>
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:7, marginBottom:4 }}>
            <span style={{ fontSize:16 }}><Glyph g="🧠"/></span>
            <span style={{ fontSize:14, fontWeight:700, color:'var(--text-primary)', letterSpacing:'-0.02em' }}>AI Intelligence Briefing</span>
            <TipBubble label="What is this?">
              This uses live AI to analyse your competitors and the trends you're tracking, then gives you specific recommendations for your store — updated on demand.
            </TipBubble>
          </div>
          <div style={{ fontSize:14, color:'var(--text-tertiary)' }}>Real-time analysis of your competitors and market trends, applied to {company}.</div>
        </div>
        <button onClick={runAnalysis} disabled={loading} style={{
          display:'inline-flex', alignItems:'center', gap:7, padding:'9px 18px', borderRadius:999,
          fontSize:14, fontWeight:800, cursor:'pointer',
          background: loading ? 'color-mix(in oklab, var(--violet) 6%, transparent)' : 'color-mix(in oklab, var(--violet) 16%, transparent)',
          border:'1px solid color-mix(in oklab, var(--violet) 32%, transparent)', color:loading?'var(--text-muted)':'var(--violet)',
          transition:'all 0.2s ease', whiteSpace:'nowrap', flexShrink:0,
        }}>
          {loading
            ? <><div style={{ width:12,height:12,border:'2px solid color-mix(in oklab, var(--violet) 20%, transparent)',borderTopColor:'var(--violet)',borderRadius:'50%',animation:'spin 0.8s linear infinite' }}/>Analysing…</>
            : generated ? '↺ Refresh' : '▶ Run analysis'
          }
        </button>
      </div>

      {error && <div style={{ padding:'10px 12px', borderRadius:10, background:'color-mix(in oklab, var(--danger) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 20%, transparent)', fontSize:13, color:'var(--danger)', marginBottom:10 }}>{error}</div>}

      {!analysis && !loading && (
        <div style={{ padding:'24px', textAlign:'center', color:'var(--text-muted)', fontSize:14, lineHeight:1.7 }}>
          Hit "Run analysis" to get a live AI briefing on what your competitors are doing and what trends apply to your store.
          <br/><span style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:'color-mix(in oklab, var(--accent) 50%, transparent)', marginTop:6, display:'block' }}>Powered by Claude · results in ~10 seconds</span>
        </div>
      )}

      {loading && (
        <div style={{ padding:'16px', display:'flex', flexDirection:'column', gap:10 }}>
          {[85,65,75,55,80].map((w,i) => (
            <div key={i} style={{ height:12, borderRadius:6, width:`${w}%`, background:'linear-gradient(90deg,color-mix(in oklab, var(--violet) 6%, transparent) 25%,color-mix(in oklab, var(--violet) 12%, transparent) 50%,color-mix(in oklab, var(--violet) 6%, transparent) 75%)', backgroundSize:'200% 100%', animation:'shimmer 1.6s infinite' }}/>
          ))}
        </div>
      )}

      {analysis && (
        <div style={{ padding:'14px', borderRadius:12, background:'color-mix(in oklab, var(--ink) 3%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)', animation:'fadeSlideUp 0.35s ease-out' }}>
          <div style={{ fontSize:14, color:'var(--text-secondary)', lineHeight:1.8, whiteSpace:'pre-wrap' }}>{analysis}</div>
          <div style={{ marginTop:10, fontSize:13, fontFamily:'var(--font-mono)', color:'var(--text-muted)', display:'flex', justifyContent:'space-between' }}>
            <span>Generated just now · Claude AI</span>
            <span>Apply to <a href="#" onClick={e=>{e.preventDefault(); onNavigate && onNavigate('schedules');}} style={{ color:'var(--accent)', cursor:'pointer' }}>Schedules</a> or <a href="#" onClick={e=>{e.preventDefault(); onNavigate && onNavigate('tasks');}} style={{ color:'var(--accent)', cursor:'pointer' }}>Tasks</a></span>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Competitor card ───────────────────────────────────────────────────────────
function CompetitorCard({ comp, onRemove, onToggleTrack }) {
  return (
    <div style={{ borderRadius:16, border:'1px solid color-mix(in oklab, var(--ink) 9%, transparent)', background:'color-mix(in oklab, var(--ink) 3%, transparent)', padding:'14px', transition:'all 0.2s ease' }}>
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:8, marginBottom:10 }}>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ fontSize:14, fontWeight:700, color:'var(--text-primary)', marginBottom:2 }}>{comp.name}</div>
          <a href={safeHref(comp.url) || undefined} target="_blank" rel="noopener noreferrer" style={{ fontSize:13, fontFamily:'var(--font-mono)', color:'var(--accent)', textDecoration:'none' }}>{comp.url}</a>
          <div style={{ fontSize:13, color:'var(--text-muted)', marginTop:2 }}>{comp.industry}</div>
        </div>
        <div style={{ display:'flex', gap:5, flexShrink:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:4, padding:'3px 8px', borderRadius:999, background:'color-mix(in oklab, var(--success) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--success) 18%, transparent)' }}>
            <span style={{ width:5, height:5, borderRadius:'50%', background:'var(--success)', animation:'pulse 2s infinite' }}/>
            <span style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--success)' }}>{comp.lastScan || 'never'}</span>
          </div>
          <button onClick={()=>onRemove(comp.id)} style={{ padding:'3px 8px', borderRadius:8, fontSize:13, cursor:'pointer', background:'color-mix(in oklab, var(--danger) 7%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 18%, transparent)', color:'var(--danger)' }}>✕</button>
        </div>
      </div>

      <div style={{ fontSize:13, color:'var(--text-muted)', marginBottom:7 }}>What to track</div>
      <div style={{ display:'flex', gap:5, flexWrap:'wrap' }}>
        {TRACK_OPTIONS.map(opt => {
          const on = (comp.tracked || []).includes(opt);
          const c  = trackColors[opt] || 'var(--text-muted)';
          return (
            <button key={opt} onClick={()=>onToggleTrack(comp.id,opt)} style={{
              padding:'4px 10px', borderRadius:999, fontSize:13, fontVariantNumeric:'tabular-nums', cursor:'pointer',
              background:on?`color-mix(in oklab, ${c} 8%, transparent)`:'color-mix(in oklab, var(--ink) 4%, transparent)',
              border:`1px solid ${on?`color-mix(in oklab, ${c} 21%, transparent)`:'color-mix(in oklab, var(--ink) 9%, transparent)'}`,
              color:on?c:'var(--text-muted)', textTransform:'capitalize', transition:'all 0.15s',
            }}>{opt.replace('-',' ')}</button>
          );
        })}
      </div>
    </div>
  );
}

// ── Add competitor form ───────────────────────────────────────────────────────
function AddCompetitorForm({ onAdd, onClose }) {
  const [name, setName]     = React.useState('');
  const [url, setUrl]       = React.useState('');
  const [industry, setInd]  = React.useState('');
  const [tracked, setTracked] = React.useState(['pricing','campaigns']);

  const toggle = opt => setTracked(p => p.includes(opt) ? p.filter(x=>x!==opt) : [...p,opt]);

  return (
    <div style={{ padding:'14px', borderRadius:14, background:'color-mix(in oklab, var(--accent) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 18%, transparent)', marginBottom:12, animation:'fadeSlideUp 0.2s ease-out' }}>
      <div style={{ fontSize:13, fontWeight:700, color:'var(--text-secondary)', marginBottom:10 }}>Track a competitor</div>
      <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8 }}>
          {[
            { value:name, onChange:setName, placeholder:'Company name' },
            { value:industry, onChange:setInd, placeholder:'Industry (e.g. Fashion)' },
          ].map((f,i) => (
            <input key={i} value={f.value} onChange={e=>f.onChange(e.target.value)} placeholder={f.placeholder}
              style={{ padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 4%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:14, outline:'none', fontFamily:'var(--font-main)', transition:'border-color 0.2s' }}
              onFocus={e=>e.target.style.borderColor='color-mix(in oklab, var(--accent) 45%, transparent)'} onBlur={e=>e.target.style.borderColor='color-mix(in oklab, var(--ink) 10%, transparent)'}/>
          ))}
        </div>
        <input value={url} onChange={e=>setUrl(e.target.value)} placeholder="Website URL (e.g. competitor.com)"
          style={{ padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 4%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:14, outline:'none', fontFamily:'var(--font-mono)', transition:'border-color 0.2s' }}
          onFocus={e=>e.target.style.borderColor='color-mix(in oklab, var(--accent) 45%, transparent)'} onBlur={e=>e.target.style.borderColor='color-mix(in oklab, var(--ink) 10%, transparent)'}/>
        <div>
          <div style={{ fontSize:13, color:'var(--text-muted)', marginBottom:6 }}>Track</div>
          <div style={{ display:'flex', gap:5, flexWrap:'wrap' }}>
            {TRACK_OPTIONS.map(opt => {
              const on = tracked.includes(opt); const c = trackColors[opt]||'var(--text-muted)';
              return <button key={opt} onClick={()=>toggle(opt)} style={{ padding:'4px 10px', borderRadius:999, fontSize:13, fontVariantNumeric:'tabular-nums', cursor:'pointer', background:on?`color-mix(in oklab, ${c} 8%, transparent)`:'color-mix(in oklab, var(--ink) 4%, transparent)', border:`1px solid ${on?`color-mix(in oklab, ${c} 21%, transparent)`:'color-mix(in oklab, var(--ink) 9%, transparent)'}`, color:on?c:'var(--text-muted)', textTransform:'capitalize', transition:'all 0.15s' }}>{opt.replace('-',' ')}</button>;
            })}
          </div>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button onClick={()=>{ if(name.trim()&&url.trim()){ onAdd({id:`c-${Date.now()}`,name:name.trim(),url:url.trim(),industry:industry.trim(),tracked,lastScan:'never',status:'active'}); onClose(); }}} style={{ flex:1, padding:'9px', borderRadius:10, background:'var(--accent)', color:'var(--on-accent)', fontSize:14, fontWeight:700, border:'none', cursor:'pointer' }}>Add</button>
          <button onClick={onClose} style={{ padding:'9px 14px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-muted)', fontSize:14, cursor:'pointer' }}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

// ── Trend keyword row ─────────────────────────────────────────────────────────
function KeywordRow({ kw, onToggle, onRemove }) {
  const catColors = { 'Tech Trends':'var(--accent)','AI & Commerce':'var(--violet)','Conversion':'var(--success)','Market Intel':'var(--warning)','Retention':'var(--warning)' };
  const c = catColors[kw.category] || 'var(--text-muted)';
  return (
    <div style={{ display:'flex', alignItems:'center', gap:10, padding:'10px 14px', borderRadius:12, background:'color-mix(in oklab, var(--ink) 3%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)', marginBottom:7 }}>
      <button onClick={()=>onToggle(kw.id)} style={{ width:28, height:16, borderRadius:999, padding:2, cursor:'pointer', background:kw.tracked?'var(--accent)':'color-mix(in oklab, var(--ink) 10%, transparent)', border:`1px solid ${kw.tracked?'color-mix(in oklab, var(--accent) 50%, transparent)':'color-mix(in oklab, var(--ink) 15%, transparent)'}`, transition:'all 0.2s', display:'flex', alignItems:'center', justifyContent:kw.tracked?'flex-end':'flex-start', flexShrink:0 }}>
        <div style={{ width:12, height:12, borderRadius:'50%', background:'#fff', boxShadow:'0 1px 3px color-mix(in oklab, var(--shade) 30%, transparent)' }}/>
      </button>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:14, fontWeight:600, color:'var(--text-primary)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{kw.keyword}</div>
      </div>
      <span style={{ fontSize:13, fontVariantNumeric:'tabular-nums', padding:'2px 8px', borderRadius:999, color:c, background:`color-mix(in oklab, ${c} 7%, transparent)`, border:`1px solid color-mix(in oklab, ${c} 13%, transparent)`, flexShrink:0 }}>{kw.category}</span>
      <button onClick={()=>onRemove(kw.id)} style={{ width:22, height:22, borderRadius:7, display:'flex', alignItems:'center', justifyContent:'center', background:'transparent', border:'none', cursor:'pointer', color:'var(--text-muted)', fontSize:13, flexShrink:0 }}
        onMouseEnter={e=>{e.currentTarget.style.background='color-mix(in oklab, var(--danger) 10%, transparent)';e.currentTarget.style.color='#ff6b7d';}}
        onMouseLeave={e=>{e.currentTarget.style.background='transparent';e.currentTarget.style.color='var(--text-muted)';}}>✕</button>
    </div>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────
function IntelligenceScreen({ onNavigate }) {
  const [competitors, setCompetitors] = React.useState([]);
  const [keywords,    setKeywords]    = React.useState([]);
  const [companyName, setCompanyName] = React.useState('Your Store');
  const [showAddComp, setShowAddComp] = React.useState(false);
  const [newKw,       setNewKw]       = React.useState('');
  const [newKwCat,    setNewKwCat]    = React.useState('Tech Trends');
  const [tab,         setTab]         = React.useState('briefing');
  const [saveError,   setSaveError]   = React.useState('');
  const companyId = React.useMemo(() => { try { return localStorage.getItem(COMPANY_ID_KEY); } catch { return null; } }, []);

  // Storage helpers — backend when company exists, localStorage fallback
  const save = React.useCallback(async (comps, kws) => {
    try {
      localStorage.setItem('intel_competitors', JSON.stringify(comps));
      localStorage.setItem('intel_keywords',    JSON.stringify(kws));
      if (companyId) {
        await api.updateCompany(companyId, { intelligence_competitors: comps, intelligence_keywords: kws });
      }
      setSaveError('');
    } catch (e) {
      setSaveError('Saved on this device only — could not sync to your company: ' + (e?.response?.data?.detail ? api.fmtErr(e.response.data.detail) : (e?.message || 'unknown error')));
    }
  }, [companyId]);

  // Load on mount
  React.useEffect(() => {
    const loadData = async () => {
      // Try backend first
      if (companyId) {
        try {
          const { data } = await api.getCompany(companyId);
          const co = data.company || data;
          if (co.name) setCompanyName(co.name);
          if (Array.isArray(co.intelligence_competitors) && co.intelligence_competitors.length > 0) {
            setCompetitors(co.intelligence_competitors);
            setKeywords(co.intelligence_keywords?.length ? co.intelligence_keywords : DEFAULT_KEYWORDS);
            return;
          }
        } catch { /* fall through to localStorage */ }
      }
      // localStorage fallback
      try {
        const comps = JSON.parse(localStorage.getItem('intel_competitors') || '[]');
        const kws   = JSON.parse(localStorage.getItem('intel_keywords')    || '[]');
        if (comps.length) setCompetitors(comps);
        setKeywords(kws.length ? kws : DEFAULT_KEYWORDS);
      } catch { setKeywords(DEFAULT_KEYWORDS); }
    };
    loadData();
  }, [companyId]);

  const removeComp   = id => { const next = competitors.filter(c => c.id !== id); setCompetitors(next); save(next, keywords); };
  const toggleTrack  = (cid, opt) => { const next = competitors.map(c => c.id===cid ? {...c, tracked: c.tracked.includes(opt) ? c.tracked.filter(x=>x!==opt) : [...c.tracked,opt]} : c); setCompetitors(next); save(next, keywords); };
  const toggleKw     = id => { const next = keywords.map(k => k.id===id ? {...k,tracked:!k.tracked} : k); setKeywords(next); save(competitors, next); };
  const removeKw     = id => { const next = keywords.filter(k => k.id !== id); setKeywords(next); save(competitors, next); };
  const addKw        = () => { if(newKw.trim()){ const next = [...keywords, {id:`k-${Date.now()}`,keyword:newKw.trim(),category:newKwCat,tracked:true}]; setKeywords(next); save(competitors, next); setNewKw(''); }};

  return (
    <div style={{ padding:'20px 16px 48px', maxWidth:1200, margin:'0 auto' }}>
      <div style={{ marginBottom:16 }}>
        <h1 style={{ fontSize:26, fontWeight:700, color:'var(--text-primary)', letterSpacing:'-0.04em', lineHeight:1.1, marginBottom:6 }}>Commerce intelligence</h1>
        <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.65, maxWidth:580 }}>
          Track what your competitors are doing, monitor the latest trends in your market, and get AI-generated recommendations tailored specifically to <strong style={{ color:'var(--text-secondary)' }}>your company</strong>. No manual research — the agents do it automatically.
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display:'flex', gap:4, marginBottom:16 }}>
        {['briefing','competitors','trends'].map(t => (
          <button key={t} onClick={()=>setTab(t)} style={{ padding:'7px 18px', borderRadius:999, fontSize:13, fontWeight:600, cursor:'pointer', textTransform:'capitalize', transition:'all 0.15s', background:tab===t?'color-mix(in oklab, var(--accent) 15%, transparent)':'color-mix(in oklab, var(--ink) 4%, transparent)', border:`1px solid ${tab===t?'color-mix(in oklab, var(--accent) 35%, transparent)':'color-mix(in oklab, var(--ink) 8%, transparent)'}`, color:tab===t?'var(--text-primary)':'var(--text-muted)' }}>
            {t==='briefing'?'🧠 AI Briefing':t==='competitors'?'👁 Competitors':'📈 Trend Keywords'}
          </button>
        ))}
      </div>

      {saveError && <div style={{ padding:'8px 12px', borderRadius:10, background:'color-mix(in oklab, var(--warning) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--warning) 25%, transparent)', fontSize:13, color:'var(--warning)', marginBottom:12 }}>{saveError}</div>}

      {tab === 'briefing' && (
        <div style={{ animation:'fadeSlideUp 0.3s ease-out' }}>
          <AIInsightsPanel company={companyName} competitors={competitors} keywords={keywords} onNavigate={onNavigate}/>

          {/* What to do with insights */}
          <div style={{ padding:'14px 16px', borderRadius:16, background:'color-mix(in oklab, var(--ink) 3%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)' }}>
            <div style={{ fontSize:14, fontWeight:700, color:'var(--text-secondary)', marginBottom:10 }}>What to do with these insights</div>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(220px,1fr))', gap:10 }}>
              {[
                { icon:'⚙', label:'Turn on a skill', desc:'If a competitor is running flash sales, enable the Flash Sale Orchestrator skill.', screen:'skills', color:'var(--accent)' },
                { icon:'📅', label:'Add a schedule', desc:'Set up a weekly Competitor Pricing scan to stay ahead automatically.', screen:'schedules', color:'var(--success)' },
                { icon:'✅', label:'Create a task', desc:'Turn a specific recommendation into a tracked task for your team.', screen:'tasks', color:'var(--violet)' },
                { icon:'💬', label:'Ask an agent', desc:'Open chat and paste the insight — an agent will plan the response.', screen:'chat', color:'var(--warning)' },
              ].map(a => (
                <div key={a.label} onClick={() => onNavigate && onNavigate(a.screen)} style={{ padding:'11px 13px', borderRadius:13, background:`color-mix(in oklab, ${a.color} 3%, transparent)`, border:`1px solid color-mix(in oklab, ${a.color} 13%, transparent)`, cursor:'pointer', transition:'all 0.15s' }}
                  onMouseEnter={e=>{e.currentTarget.style.background=`color-mix(in oklab, ${a.color} 7%, transparent)`;}}
                  onMouseLeave={e=>{e.currentTarget.style.background=`color-mix(in oklab, ${a.color} 3%, transparent)`;}}>
                  <div style={{ fontSize:16, marginBottom:5 }}><Glyph g={a.icon}/></div>
                  <div style={{ fontSize:13, fontWeight:700, color:'var(--text-primary)', marginBottom:3 }}>{a.label}</div>
                  <div style={{ fontSize:13, color:'var(--text-muted)', lineHeight:1.5 }}>{a.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === 'competitors' && (
        <div style={{ animation:'fadeSlideUp 0.3s ease-out' }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12 }}>
            <div style={{ fontSize:14, color:'var(--text-tertiary)' }}>
              Track competitor sites. Agents scan them regularly and flag changes in pricing, campaigns, and new features.
            </div>
            <button onClick={()=>setShowAddComp(o=>!o)} style={{ padding:'8px 16px', borderRadius:10, fontSize:13, fontWeight:700, cursor:'pointer', background:'color-mix(in oklab, var(--accent) 12%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 25%, transparent)', color:'var(--accent)', flexShrink:0, marginLeft:10 }}>+ Add competitor</button>
          </div>
          {showAddComp && <AddCompetitorForm onAdd={c=>{const next=[...competitors,c];setCompetitors(next);save(next,keywords);setShowAddComp(false);}} onClose={()=>setShowAddComp(false)}/>}
          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(280px,1fr))', gap:12 }}>
            {competitors.map(comp => <CompetitorCard key={comp.id} comp={comp} onRemove={removeComp} onToggleTrack={toggleTrack}/>)}
          </div>
          {competitors.length === 0 && (
            <div style={{ padding:'40px', textAlign:'center', color:'var(--text-muted)', fontSize:14 }}>No competitors tracked yet. Add one to start monitoring.</div>
          )}
        </div>
      )}

      {tab === 'trends' && (
        <div style={{ animation:'fadeSlideUp 0.3s ease-out' }}>
          <div style={{ fontSize:14, color:'var(--text-tertiary)', marginBottom:14, lineHeight:1.6 }}>
            These keywords are scanned regularly across news, blogs, and social media. When there's a relevant development, the AI Briefing incorporates it into recommendations for your store.
          </div>

          {/* Add keyword */}
          <div style={{ display:'flex', gap:8, marginBottom:14 }}>
            <input value={newKw} onChange={e=>setNewKw(e.target.value)} placeholder="e.g. TikTok commerce UK trends" onKeyDown={e=>e.key==='Enter'&&addKw()}
              style={{ flex:1, padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 12%, transparent)', color:'var(--text-primary)', fontSize:14, outline:'none', fontFamily:'var(--font-main)', transition:'border-color 0.2s' }}
              onFocus={e=>e.target.style.borderColor='color-mix(in oklab, var(--accent) 45%, transparent)'} onBlur={e=>e.target.style.borderColor='color-mix(in oklab, var(--ink) 12%, transparent)'}/>
            <select value={newKwCat} onChange={e=>setNewKwCat(e.target.value)} style={{ padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 12%, transparent)', color:'var(--text-primary)', fontSize:14, outline:'none', fontFamily:'var(--font-main)' }}>
              {['Tech Trends','AI & Commerce','Conversion','Market Intel','Retention','SEO','Competitor'].map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <button onClick={addKw} style={{ padding:'9px 16px', borderRadius:10, background:'color-mix(in oklab, var(--accent) 15%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 30%, transparent)', color:'var(--accent)', fontSize:13, fontWeight:700, cursor:'pointer', whiteSpace:'nowrap' }}>+ Add</button>
          </div>

          {keywords.map(kw => <KeywordRow key={kw.id} kw={kw} onToggle={toggleKw} onRemove={removeKw}/>)}

          <div style={{ marginTop:14, padding:'10px 14px', borderRadius:12, background:'color-mix(in oklab, var(--accent) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 14%, transparent)', fontSize:13, color:'var(--text-muted)', lineHeight:1.6 }}>
            <strong style={{ color:'var(--text-tertiary)' }}><Glyph g="💡"/> Tip:</strong> Add keywords for your product categories, marketing channels, and competitor names. The more specific, the better the briefing.
          </div>
        </div>
      )}
    </div>
  );
}

export { IntelligenceScreen };
export default IntelligenceScreen;
