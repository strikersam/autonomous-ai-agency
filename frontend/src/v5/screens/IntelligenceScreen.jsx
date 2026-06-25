/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import * as api from '../../api';
import { COMPANY_ID_KEY } from './CompanyScreen';

// intelligence.jsx — Commerce Intelligence
// Competitor monitoring + trend scanning with live AI analysis via /api/chat/send

const TRACK_OPTIONS = ['pricing','campaigns','new-arrivals','features','tech-stack','seo','social'];
const trackColors   = { pricing:'#ffbd66', campaigns:'#ff6b7d', 'new-arrivals':'#46d9a4', features:'#5da2ff', 'tech-stack':'#c4b5fd', seo:'#7c9dff', social:'#f97316' };

// ── Reusable Explain tooltip (imported from skills.jsx via window) ─────────────
function TipBubble({ label, children }) {
  const [open, setOpen] = React.useState(false);
  return (
    <span style={{ position:'relative', display:'inline-flex', alignItems:'center', gap:4 }}>
      <button onClick={()=>setOpen(o=>!o)} style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', background:'rgba(93,162,255,0.10)', border:'1px solid rgba(93,162,255,0.22)', borderRadius:999, padding:'2px 9px', cursor:'pointer', transition:'all 0.15s' }}>
        {label} ?
      </button>
      {open && (
        <div style={{ position:'absolute', bottom:'calc(100% + 6px)', left:0, zIndex:99, background:'rgba(12,15,20,0.98)', border:'1px solid rgba(93,162,255,0.25)', borderRadius:12, padding:'10px 12px', minWidth:240, maxWidth:'min(300px, calc(100vw - 24px))', fontSize:12, color:'var(--text-secondary)', lineHeight:1.6, boxShadow:'0 12px 32px rgba(0,0,0,0.55)', animation:'fadeSlideUp 0.15s ease-out' }}
          onClick={e=>e.stopPropagation()}>
          {children}
          <button onClick={()=>setOpen(false)} style={{ display:'block', marginTop:8, fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', background:'none', border:'none', cursor:'pointer' }}>Close ✕</button>
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

      const { data } = await api.chatSend(prompt, null, null, null, null, false);
      const result = data?.response || '';
      if (!result) throw new Error('No response from AI.');
      setAnalysis(result);
      setGenerated(true);
    } catch (e) {
      const errMsg = e?.response?.data?.detail ? api.fmtErr(e.response.data.detail) : (e?.message || 'Unknown error');
      setError('Could not generate analysis: ' + errMsg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ borderRadius:18, border:'1px solid rgba(196,181,253,0.20)', background:'rgba(196,181,253,0.04)', padding:'16px', marginBottom:20 }}>
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:12, flexWrap:'wrap', marginBottom:12 }}>
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:7, marginBottom:4 }}>
            <span style={{ fontSize:16 }}>🧠</span>
            <span style={{ fontSize:14, fontWeight:800, color:'#fff', letterSpacing:'-0.02em' }}>AI Intelligence Briefing</span>
            <TipBubble label="What is this?">
              This uses live AI to analyse your competitors and the trends you're tracking, then gives you specific recommendations for your store — updated on demand.
            </TipBubble>
          </div>
          <div style={{ fontSize:13, color:'var(--text-tertiary)' }}>Real-time analysis of your competitors and market trends, applied to {company}.</div>
        </div>
        <button onClick={runAnalysis} disabled={loading} style={{
          display:'inline-flex', alignItems:'center', gap:7, padding:'9px 18px', borderRadius:999,
          fontSize:13, fontWeight:800, cursor:'pointer',
          background: loading ? 'rgba(196,181,253,0.06)' : 'rgba(196,181,253,0.16)',
          border:'1px solid rgba(196,181,253,0.32)', color:loading?'var(--text-muted)':'#c4b5fd',
          transition:'all 0.2s ease', whiteSpace:'nowrap', flexShrink:0,
        }}>
          {loading
            ? <><div style={{ width:12,height:12,border:'2px solid rgba(196,181,253,0.2)',borderTopColor:'#c4b5fd',borderRadius:'50%',animation:'spin 0.8s linear infinite' }}/>Analysing…</>
            : generated ? '↺ Refresh' : '▶ Run analysis'
          }
        </button>
      </div>

      {error && <div style={{ padding:'10px 12px', borderRadius:10, background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.20)', fontSize:12, color:'#ff6b7d', marginBottom:10 }}>{error}</div>}

      {!analysis && !loading && (
        <div style={{ padding:'24px', textAlign:'center', color:'var(--text-muted)', fontSize:13, lineHeight:1.7 }}>
          Hit "Run analysis" to get a live AI briefing on what your competitors are doing and what trends apply to your store.
          <br/><span style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'rgba(93,162,255,0.5)', marginTop:6, display:'block' }}>Powered by Claude · results in ~10 seconds</span>
        </div>
      )}

      {loading && (
        <div style={{ padding:'16px', display:'flex', flexDirection:'column', gap:10 }}>
          {[85,65,75,55,80].map((w,i) => (
            <div key={i} style={{ height:12, borderRadius:6, width:`${w}%`, background:'linear-gradient(90deg,rgba(196,181,253,0.06) 25%,rgba(196,181,253,0.12) 50%,rgba(196,181,253,0.06) 75%)', backgroundSize:'200% 100%', animation:'shimmer 1.6s infinite' }}/>
          ))}
        </div>
      )}

      {analysis && (
        <div style={{ padding:'14px', borderRadius:12, background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.08)', animation:'fadeSlideUp 0.35s ease-out' }}>
          <div style={{ fontSize:13, color:'var(--text-secondary)', lineHeight:1.8, whiteSpace:'pre-wrap' }}>{analysis}</div>
          <div style={{ marginTop:10, fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', display:'flex', justifyContent:'space-between' }}>
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
    <div style={{ borderRadius:16, border:'1px solid rgba(255,255,255,0.09)', background:'rgba(255,255,255,0.03)', padding:'14px', transition:'all 0.2s ease' }}>
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:8, marginBottom:10 }}>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ fontSize:14, fontWeight:700, color:'#fff', marginBottom:2 }}>{comp.name}</div>
          <a href="#" style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', textDecoration:'none' }}>{comp.url}</a>
          <div style={{ fontSize:11, color:'var(--text-muted)', marginTop:2 }}>{comp.industry}</div>
        </div>
        <div style={{ display:'flex', gap:5, flexShrink:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:4, padding:'3px 8px', borderRadius:999, background:'rgba(70,217,164,0.08)', border:'1px solid rgba(70,217,164,0.18)' }}>
            <span style={{ width:5, height:5, borderRadius:'50%', background:'#46d9a4', animation:'pulse 2s infinite' }}/>
            <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'#46d9a4' }}>{comp.lastScan}</span>
          </div>
          <button onClick={()=>onRemove(comp.id)} style={{ padding:'3px 8px', borderRadius:8, fontSize:11, cursor:'pointer', background:'rgba(255,107,125,0.07)', border:'1px solid rgba(255,107,125,0.18)', color:'#ff6b7d' }}>✕</button>
        </div>
      </div>

      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.10em', textTransform:'uppercase', marginBottom:7 }}>What to track</div>
      <div style={{ display:'flex', gap:5, flexWrap:'wrap' }}>
        {TRACK_OPTIONS.map(opt => {
          const on = comp.tracked.includes(opt);
          const c  = trackColors[opt] || 'var(--text-muted)';
          return (
            <button key={opt} onClick={()=>onToggleTrack(comp.id,opt)} style={{
              padding:'4px 10px', borderRadius:999, fontSize:10, fontFamily:'var(--font-mono)', cursor:'pointer',
              background:on?`${c}15`:'rgba(255,255,255,0.04)',
              border:`1px solid ${on?`${c}35`:'rgba(255,255,255,0.09)'}`,
              color:on?c:'var(--text-muted)', textTransform:'capitalize', transition:'all 0.15s', letterSpacing:'0.08em',
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
    <div style={{ padding:'14px', borderRadius:14, background:'rgba(93,162,255,0.05)', border:'1px solid rgba(93,162,255,0.18)', marginBottom:12, animation:'fadeSlideUp 0.2s ease-out' }}>
      <div style={{ fontSize:12, fontWeight:700, color:'var(--text-secondary)', marginBottom:10 }}>Track a competitor</div>
      <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8 }}>
          {[
            { value:name, onChange:setName, placeholder:'Company name' },
            { value:industry, onChange:setInd, placeholder:'Industry (e.g. Fashion)' },
          ].map((f,i) => (
            <input key={i} value={f.value} onChange={e=>f.onChange(e.target.value)} placeholder={f.placeholder}
              style={{ padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-main)', transition:'border-color 0.2s' }}
              onFocus={e=>e.target.style.borderColor='rgba(93,162,255,0.45)'} onBlur={e=>e.target.style.borderColor='rgba(255,255,255,0.10)'}/>
          ))}
        </div>
        <input value={url} onChange={e=>setUrl(e.target.value)} placeholder="Website URL (e.g. competitor.com)"
          style={{ padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-mono)', transition:'border-color 0.2s' }}
          onFocus={e=>e.target.style.borderColor='rgba(93,162,255,0.45)'} onBlur={e=>e.target.style.borderColor='rgba(255,255,255,0.10)'}/>
        <div>
          <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.10em', textTransform:'uppercase', marginBottom:6 }}>Track</div>
          <div style={{ display:'flex', gap:5, flexWrap:'wrap' }}>
            {TRACK_OPTIONS.map(opt => {
              const on = tracked.includes(opt); const c = trackColors[opt]||'var(--text-muted)';
              return <button key={opt} onClick={()=>toggle(opt)} style={{ padding:'4px 10px', borderRadius:999, fontSize:10, fontFamily:'var(--font-mono)', cursor:'pointer', background:on?`${c}15`:'rgba(255,255,255,0.04)', border:`1px solid ${on?`${c}35`:'rgba(255,255,255,0.09)'}`, color:on?c:'var(--text-muted)', textTransform:'capitalize', transition:'all 0.15s', letterSpacing:'0.08em' }}>{opt.replace('-',' ')}</button>;
            })}
          </div>
        </div>
        <div style={{ display:'flex', gap:8 }}>
          <button onClick={()=>{ if(name&&url){ onAdd({id:`c-${Date.now()}`,name,url,industry,tracked,lastScan:'never',status:'active'}); onClose(); }}} style={{ flex:1, padding:'9px', borderRadius:10, background:'var(--accent)', color:'#06111f', fontSize:13, fontWeight:800, border:'none', cursor:'pointer' }}>Add</button>
          <button onClick={onClose} style={{ padding:'9px 14px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-muted)', fontSize:13, cursor:'pointer' }}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

// ── Trend keyword row ─────────────────────────────────────────────────────────
function KeywordRow({ kw, onToggle, onRemove }) {
  const catColors = { 'Tech Trends':'#5da2ff','AI & Commerce':'#c4b5fd','Conversion':'#46d9a4','Market Intel':'#ffbd66','Retention':'#ff9d66' };
  const c = catColors[kw.category] || 'var(--text-muted)';
  return (
    <div style={{ display:'flex', alignItems:'center', gap:10, padding:'10px 14px', borderRadius:12, background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.08)', marginBottom:7 }}>
      <button onClick={()=>onToggle(kw.id)} style={{ width:28, height:16, borderRadius:999, padding:2, cursor:'pointer', background:kw.tracked?'var(--accent)':'rgba(255,255,255,0.10)', border:`1px solid ${kw.tracked?'rgba(93,162,255,0.5)':'rgba(255,255,255,0.15)'}`, transition:'all 0.2s', display:'flex', alignItems:'center', justifyContent:kw.tracked?'flex-end':'flex-start', flexShrink:0 }}>
        <div style={{ width:12, height:12, borderRadius:'50%', background:'#fff', boxShadow:'0 1px 3px rgba(0,0,0,0.3)' }}/>
      </button>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:13, fontWeight:600, color:'var(--text-primary)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{kw.keyword}</div>
      </div>
      <span style={{ fontSize:10, fontFamily:'var(--font-mono)', padding:'2px 8px', borderRadius:999, color:c, background:`${c}12`, border:`1px solid ${c}22`, flexShrink:0 }}>{kw.category}</span>
      <button onClick={()=>onRemove(kw.id)} style={{ width:22, height:22, borderRadius:7, display:'flex', alignItems:'center', justifyContent:'center', background:'transparent', border:'none', cursor:'pointer', color:'var(--text-muted)', fontSize:12, flexShrink:0 }}
        onMouseEnter={e=>{e.currentTarget.style.background='rgba(255,107,125,0.10)';e.currentTarget.style.color='#ff6b7d';}}
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
  const companyId = React.useMemo(() => { try { return localStorage.getItem(COMPANY_ID_KEY); } catch { return null; } }, []);

  // Storage helpers — backend when company exists, localStorage fallback
  const save = React.useCallback(async (comps, kws) => {
    try {
      localStorage.setItem('intel_competitors', JSON.stringify(comps));
      localStorage.setItem('intel_keywords',    JSON.stringify(kws));
      if (companyId) {
        await api.updateCompany ? api.updateCompany(companyId, { intelligence_competitors: comps, intelligence_keywords: kws })
                                : Promise.resolve();
      }
    } catch { /* non-critical */ }
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
            setKeywords(co.intelligence_keywords || []);
            return;
          }
        } catch { /* fall through to localStorage */ }
      }
      // localStorage fallback
      try {
        const comps = JSON.parse(localStorage.getItem('intel_competitors') || '[]');
        const kws   = JSON.parse(localStorage.getItem('intel_keywords')    || '[]');
        if (comps.length) setCompetitors(comps);
        if (kws.length)   setKeywords(kws);
      } catch { /* ignore */ }
    };
    loadData();
  }, [companyId]);

  const removeComp   = id => { const next = competitors.filter(c => c.id !== id); setCompetitors(next); save(next, keywords); };
  const toggleTrack  = (cid, opt) => { const next = competitors.map(c => c.id===cid ? {...c, tracked: c.tracked.includes(opt) ? c.tracked.filter(x=>x!==opt) : [...c.tracked,opt]} : c); setCompetitors(next); save(next, keywords); };
  const toggleKw     = id => { const next = keywords.map(k => k.id===id ? {...k,tracked:!k.tracked} : k); setKeywords(next); save(competitors, next); };
  const removeKw     = id => { const next = keywords.filter(k => k.id !== id); setKeywords(next); save(competitors, next); };
  const addKw        = () => { if(newKw.trim()){ const next = [...keywords, {id:`k-${Date.now()}`,keyword:newKw.trim(),category:newKwCat,tracked:true}]; setKeywords(next); save(competitors, next); setNewKw(''); }};

  return (
    <div style={{ padding:'20px 16px 48px', maxWidth:960, margin:'0 auto' }}>
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:6 }}>Market Intelligence</div>
      <div style={{ marginBottom:16 }}>
        <h1 style={{ fontSize:26, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', lineHeight:1.1, marginBottom:6 }}>Commerce Intelligence</h1>
        <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.65, maxWidth:580 }}>
          Track what your competitors are doing, monitor the latest trends in your market, and get AI-generated recommendations tailored specifically to <strong style={{ color:'var(--text-secondary)' }}>your company</strong>. No manual research — the agents do it automatically.
        </p>
      </div>

      {/* Tabs */}
      <div style={{ display:'flex', gap:4, marginBottom:16 }}>
        {['briefing','competitors','trends'].map(t => (
          <button key={t} onClick={()=>setTab(t)} style={{ padding:'7px 18px', borderRadius:999, fontSize:12, fontWeight:600, cursor:'pointer', textTransform:'capitalize', transition:'all 0.15s', background:tab===t?'rgba(93,162,255,0.15)':'rgba(255,255,255,0.04)', border:`1px solid ${tab===t?'rgba(93,162,255,0.35)':'rgba(255,255,255,0.08)'}`, color:tab===t?'#fff':'var(--text-muted)' }}>
            {t==='briefing'?'🧠 AI Briefing':t==='competitors'?'👁 Competitors':'📈 Trend Keywords'}
          </button>
        ))}
      </div>

      {tab === 'briefing' && (
        <div style={{ animation:'fadeSlideUp 0.3s ease-out' }}>
          <AIInsightsPanel company={companyName} competitors={competitors} keywords={keywords} onNavigate={onNavigate}/>

          {/* What to do with insights */}
          <div style={{ padding:'14px 16px', borderRadius:16, background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.08)' }}>
            <div style={{ fontSize:13, fontWeight:700, color:'var(--text-secondary)', marginBottom:10 }}>What to do with these insights</div>
            <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(220px,1fr))', gap:10 }}>
              {[
                { icon:'⚙', label:'Turn on a skill', desc:'If a competitor is running flash sales, enable the Flash Sale Orchestrator skill.', screen:'skills', color:'#5da2ff' },
                { icon:'📅', label:'Add a schedule', desc:'Set up a weekly Competitor Pricing scan to stay ahead automatically.', screen:'schedules', color:'#46d9a4' },
                { icon:'✅', label:'Create a task', desc:'Turn a specific recommendation into a tracked task for your team.', screen:'tasks', color:'#c4b5fd' },
                { icon:'💬', label:'Ask an agent', desc:'Open chat and paste the insight — an agent will plan the response.', screen:'chat', color:'#ffbd66' },
              ].map(a => (
                <div key={a.label} onClick={() => onNavigate && onNavigate(a.screen)} style={{ padding:'11px 13px', borderRadius:13, background:`${a.color}07`, border:`1px solid ${a.color}20`, cursor:'pointer', transition:'all 0.15s' }}
                  onMouseEnter={e=>{e.currentTarget.style.background=`${a.color}12`;}}
                  onMouseLeave={e=>{e.currentTarget.style.background=`${a.color}07`;}}>
                  <div style={{ fontSize:16, marginBottom:5 }}>{a.icon}</div>
                  <div style={{ fontSize:12, fontWeight:700, color:'#fff', marginBottom:3 }}>{a.label}</div>
                  <div style={{ fontSize:11, color:'var(--text-muted)', lineHeight:1.5 }}>{a.desc}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {tab === 'competitors' && (
        <div style={{ animation:'fadeSlideUp 0.3s ease-out' }}>
          <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:12 }}>
            <div style={{ fontSize:13, color:'var(--text-tertiary)' }}>
              Track competitor sites. Agents scan them regularly and flag changes in pricing, campaigns, and new features.
            </div>
            <button onClick={()=>setShowAddComp(o=>!o)} style={{ padding:'8px 16px', borderRadius:10, fontSize:12, fontWeight:700, cursor:'pointer', background:'rgba(93,162,255,0.12)', border:'1px solid rgba(93,162,255,0.25)', color:'var(--accent)', flexShrink:0, marginLeft:10 }}>+ Add competitor</button>
          </div>
          {showAddComp && <AddCompetitorForm onAdd={c=>{setCompetitors(p=>[...p,c]);setShowAddComp(false);}} onClose={()=>setShowAddComp(false)}/>}
          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(280px,1fr))', gap:12 }}>
            {competitors.map(comp => <CompetitorCard key={comp.id} comp={comp} onRemove={removeComp} onToggleTrack={toggleTrack}/>)}
          </div>
          {competitors.length === 0 && (
            <div style={{ padding:'40px', textAlign:'center', color:'var(--text-muted)', fontSize:13 }}>No competitors tracked yet. Add one to start monitoring.</div>
          )}
        </div>
      )}

      {tab === 'trends' && (
        <div style={{ animation:'fadeSlideUp 0.3s ease-out' }}>
          <div style={{ fontSize:13, color:'var(--text-tertiary)', marginBottom:14, lineHeight:1.6 }}>
            These keywords are scanned regularly across news, blogs, and social media. When there's a relevant development, the AI Briefing incorporates it into recommendations for your store.
          </div>

          {/* Add keyword */}
          <div style={{ display:'flex', gap:8, marginBottom:14 }}>
            <input value={newKw} onChange={e=>setNewKw(e.target.value)} placeholder="e.g. TikTok commerce UK trends" onKeyDown={e=>e.key==='Enter'&&addKw()}
              style={{ flex:1, padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-main)', transition:'border-color 0.2s' }}
              onFocus={e=>e.target.style.borderColor='rgba(93,162,255,0.45)'} onBlur={e=>e.target.style.borderColor='rgba(255,255,255,0.12)'}/>
            <select value={newKwCat} onChange={e=>setNewKwCat(e.target.value)} style={{ padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-main)' }}>
              {['Tech Trends','AI & Commerce','Conversion','Market Intel','Retention','SEO','Competitor'].map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <button onClick={addKw} style={{ padding:'9px 16px', borderRadius:10, background:'rgba(93,162,255,0.15)', border:'1px solid rgba(93,162,255,0.30)', color:'var(--accent)', fontSize:12, fontWeight:700, cursor:'pointer', whiteSpace:'nowrap' }}>+ Add</button>
          </div>

          {keywords.map(kw => <KeywordRow key={kw.id} kw={kw} onToggle={toggleKw} onRemove={removeKw}/>)}

          <div style={{ marginTop:14, padding:'10px 14px', borderRadius:12, background:'rgba(93,162,255,0.05)', border:'1px solid rgba(93,162,255,0.14)', fontSize:12, color:'var(--text-muted)', lineHeight:1.6 }}>
            <strong style={{ color:'var(--text-tertiary)' }}>💡 Tip:</strong> Add keywords for your product categories, marketing channels, and competitor names. The more specific, the better the briefing.
          </div>
        </div>
      )}
    </div>
  );
}

export { IntelligenceScreen };
export default IntelligenceScreen;
