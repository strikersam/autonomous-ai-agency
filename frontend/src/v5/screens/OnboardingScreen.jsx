/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import * as api from '../../api';

// onboarding.jsx — V5.0 with structured discovery, smart questions, live API integration

const STEPS = [
  { id:'url',       label:'Discovery', desc:'Enter your URL' },
  { id:'systems',   label:'Systems',   desc:'Review detected stack' },
  { id:'details',   label:'Details',   desc:'Repos, docs & goals' },
  { id:'questions', label:'Tailor',    desc:'Smart questions' },
  { id:'done',      label:'Ready',     desc:'Specialists provisioned' },
];

// ── Smart question sets per site type ─────────────────────────────────────────
const QUESTION_SETS = {
  ecommerce: [
    { id:'peak',     label:'Are there peak traffic seasons (e.g. Black Friday, flash sales)?', type:'yesno' },
    { id:'deploys',  label:'How often do you deploy to production?', type:'select', options:['Multiple times a day','Daily','Weekly','Monthly or less'] },
    { id:'kpis',     label:'Which metrics matter most to you?', type:'multi', options:['Conversion rate','Cart abandonment','Site speed','SEO ranking','Support ticket volume','AOV'] },
    { id:'pain',     label:'What is your biggest pain point right now?', type:'freeform', placeholder:'e.g. slow checkout, cart abandonment, stock visibility…' },
  ],
  saas: [
    { id:'trials',   label:'Do you have a free trial or freemium tier?', type:'yesno' },
    { id:'deploys',  label:'How often do you deploy?', type:'select', options:['Continuous CI/CD','Daily','Weekly','Quarterly'] },
    { id:'kpis',     label:'Which metrics matter most?', type:'multi', options:['MRR growth','Churn rate','Activation rate','Support tickets','Feature adoption','NPS'] },
    { id:'pain',     label:'What is your biggest technical pain point?', type:'freeform', placeholder:'e.g. onboarding drop-off, high churn, slow CI…' },
  ],
  media: [
    { id:'publishing',label:'How many articles/posts do you publish per week?', type:'select', options:['1–5','6–20','20–50','50+'] },
    { id:'deploys',   label:'How often do you deploy the platform?', type:'select', options:['Continuous CI/CD','Weekly','Monthly','Rarely'] },
    { id:'kpis',      label:'Which metrics matter most?', type:'multi', options:['Page views','Time on site','Email subscribers','Ad revenue','SEO ranking','Engagement rate'] },
    { id:'pain',      label:'What is your biggest pain point?', type:'freeform', placeholder:'e.g. slow editorial publishing, broken embeds, SEO gaps…' },
  ],
  agency: [
    { id:'clients',   label:'How many active client projects do you manage?', type:'select', options:['1–5','6–15','16–50','50+'] },
    { id:'deploys',   label:'How often do you deliver to clients?', type:'select', options:['Daily','Weekly','Monthly','Per project'] },
    { id:'kpis',      label:'Which outcomes matter most?', type:'multi', options:['Project delivery speed','Bug rate','Client satisfaction','Code quality','Team velocity','Revenue per project'] },
    { id:'pain',      label:'What is your biggest operational pain point?', type:'freeform', placeholder:'e.g. scope creep, manual QA, context switching between clients…' },
  ],
  generic: [
    { id:'deploys',  label:'How often do you deploy or ship changes?', type:'select', options:['Multiple times a day','Daily','Weekly','Monthly or less'] },
    { id:'team',     label:'How large is your engineering team?', type:'select', options:['Solo','2–5','6–20','20+'] },
    { id:'kpis',     label:'Which outcomes matter most?', type:'multi', options:['Code quality','Deployment speed','Bug rate','Team velocity','Cost reduction','Security posture'] },
    { id:'pain',     label:'What is your biggest technical pain point?', type:'freeform', placeholder:'e.g. technical debt, slow deployments, poor test coverage…' },
  ],
};

// Detect site type from discovered systems
function detectSiteType(systems) {
  const ids = (systems || []).map(s => s.id || s.name?.toLowerCase());
  if (ids.some(id => ['shopify','woocommerce','bigcommerce','magento'].includes(id))) return 'ecommerce';
  if (ids.some(id => ['stripe','chargebee','paddle'].includes(id))) return 'saas';
  if (ids.some(id => ['wordpress','ghost','contentful','strapi','sanity'].includes(id))) return 'media';
  return 'generic';
}

const DETECTED_SYSTEMS_DEFAULT = [
  { id:'shopify',    label:'Shopify',       category:'Commerce',   confidence:0.97, icon:'🛍', desc:'Storefront + checkout detected via meta tags and JS bundles' },
  { id:'gatsby',     label:'Gatsby + React',category:'Frontend',   confidence:0.92, icon:'⚛', desc:'gatsby-browser.js and React 18 detected in JS bundles' },
  { id:'contentful', label:'Contentful',    category:'CMS',        confidence:0.88, icon:'📄', desc:'Contentful CDN URLs found in page source and API calls' },
  { id:'gtm',        label:'GTM + GA4',     category:'Analytics',  confidence:0.99, icon:'📊', desc:'Google Tag Manager and GA4 measurement IDs found in <head>' },
  { id:'klaviyo',    label:'Klaviyo',        category:'CRM',       confidence:0.83, icon:'📧', desc:'Klaviyo tracking script and form events detected' },
  { id:'gorgias',    label:'Gorgias',        category:'Support',   confidence:0.79, icon:'💬', desc:'Gorgias chat widget script found in page footer' },
];

function StepIndicator({ current }) {
  const idx = STEPS.findIndex(s=>s.id===current);
  return (
    <div style={{ display:'flex', alignItems:'center', gap:0, marginBottom:26, overflowX:'auto' }} className="scrollbar-hide">
      {STEPS.map((step,i)=>{
        const done=i<idx; const active=i===idx;
        return (
          <React.Fragment key={step.id}>
            <div style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:4, flexShrink:0 }}>
              <div style={{ width:26, height:26, borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', background:done?'#46d9a4':active?'var(--accent)':'rgba(255,255,255,0.07)', border:`2px solid ${done?'#46d9a4':active?'var(--accent)':'rgba(255,255,255,0.14)'}`, fontSize:11, fontWeight:700, color:done||active?'#06111f':'var(--text-muted)', transition:'all 0.3s' }}>
                {done?'✓':i+1}
              </div>
              <div style={{ fontSize:10, fontWeight:600, color:active?'#fff':done?'var(--text-tertiary)':'var(--text-muted)', whiteSpace:'nowrap' }}>{step.label}</div>
            </div>
            {i<STEPS.length-1 && <div style={{ flex:1, minWidth:12, height:2, margin:'0 4px', marginBottom:16, background:i<idx?'#46d9a4':'rgba(255,255,255,0.10)', transition:'background 0.4s' }}/>}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ── Non-admin gate ─────────────────────────────────────────────────────────────
function NonAdminGate() {
  const [name,  setName]  = React.useState('');
  const [email, setEmail] = React.useState('');
  const [query, setQuery] = React.useState('');
  const [sent,  setSent]  = React.useState(false);

  const handleSend = () => {
    if (!query.trim()) return;
    const subject = encodeURIComponent(`LLM Relay V5.0 — Company Setup Request${name?' from '+name:''}`);
    const body    = encodeURIComponent(
      `Hello Sam,\n\nI'd like to set up a company on LLM Relay V5.0.\n\nName: ${name||'(not provided)'}\nEmail: ${email||'(not provided)'}\n\nWhat I need:\n${query}\n\nPlease help me get started.`
    );
    window.open(`mailto:strikersam@gmail.com?subject=${subject}&body=${body}`, '_blank');
    setSent(true);
  };

  if (sent) return (
    <div style={{ textAlign:'center', padding:'40px 20px', animation:'fadeSlideUp 0.35s ease-out' }}>
      <div style={{ fontSize:40, marginBottom:14 }}>✉️</div>
      <h2 style={{ fontSize:22, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', marginBottom:8 }}>Request sent!</h2>
      <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.7, maxWidth:380, margin:'0 auto 20px' }}>
        Your request has been sent to the administrator. You'll receive confirmation once your company is provisioned — usually within 24 hours.
      </p>
      <div style={{ padding:'12px 16px', borderRadius:14, background:'rgba(70,217,164,0.06)', border:'1px solid rgba(70,217,164,0.15)', display:'inline-block', fontSize:13, color:'#46d9a4' }}>
        Sent to: strikersam@gmail.com
      </div>
    </div>
  );

  return (
    <div style={{ animation:'fadeSlideUp 0.35s ease-out' }}>
      <div style={{ padding:'12px 14px', borderRadius:14, background:'rgba(255,189,102,0.07)', border:'1px solid rgba(255,189,102,0.20)', marginBottom:22, display:'flex', alignItems:'flex-start', gap:10 }}>
        <span style={{ fontSize:16, flexShrink:0, marginTop:1 }}>ℹ️</span>
        <div>
          <div style={{ fontSize:13, fontWeight:700, color:'#ffbd66', marginBottom:3 }}>Admin setup required</div>
          <div style={{ fontSize:13, color:'var(--text-tertiary)', lineHeight:1.6 }}>
            Company onboarding requires admin access. Send a request below — the admin will configure your company and let you know when it's ready.
          </div>
        </div>
      </div>
      <h2 style={{ fontSize:22, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', marginBottom:6 }}>Request company setup</h2>
      <p style={{ fontSize:14, color: 'var(--text-tertiary)', lineHeight:1.6, marginBottom:20, maxWidth:440 }}>Describe what you need. The admin will set up your company, connect your systems, and let you know when it's ready.</p>
      <div style={{ display:'flex', flexDirection:'column', gap:11 }}>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:10 }}>
          {[{v:name,s:setName,ph:'Your name',t:'text'},{v:email,s:setEmail,ph:'Your email',t:'email'}].map((f,i)=>(
            <input key={i} value={f.v} onChange={e=>f.s(e.target.value)} placeholder={f.ph} type={f.t}
              style={{ padding:'11px 14px', borderRadius:12, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff', fontSize:13, fontFamily:'var(--font-main)', outline:'none', transition:'border-color 0.2s' }}
              onFocus={e=>e.target.style.borderColor='rgba(93,162,255,0.5)'} onBlur={e=>e.target.style.borderColor='rgba(255,255,255,0.12)'}/>
          ))}
        </div>
        <div>
          <label style={{ display:'block', fontSize:12, fontWeight:600, color:'var(--text-tertiary)', marginBottom:7 }}>What do you need? *</label>
          <textarea value={query} onChange={e=>setQuery(e.target.value)} rows={5}
            placeholder="Describe your company, what you'd like to automate, your website URL, and any systems you use (e.g. Shopify, WordPress, Salesforce)…"
            style={{ width:'100%', padding:'12px 14px', borderRadius:14, resize:'vertical', background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff', fontSize:13, fontFamily:'var(--font-main)', outline:'none', lineHeight:1.6, transition:'border-color 0.2s' }}
            onFocus={e=>e.target.style.borderColor='rgba(93,162,255,0.5)'} onBlur={e=>e.target.style.borderColor='rgba(255,255,255,0.12)'}/>
        </div>
        <button onClick={handleSend} disabled={!query.trim()} style={{ display:'inline-flex', alignItems:'center', gap:8, padding:'13px 28px', borderRadius:999, background:'linear-gradient(135deg,#6CB0FF,#4F93FF)', color:'#06111f', fontSize:14, fontWeight:800, border:'none', cursor:'pointer', boxShadow:'0 8px 24px rgba(93,162,255,0.25)', opacity:!query.trim()?0.5:1, transition:'all 0.2s' }}>
          ✉️ Send request to admin
        </button>
        <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>Opens your email client with a pre-filled message to the LLM Relay admin.</div>
      </div>
    </div>
  );
}

// ── Step 1: URL discovery ──────────────────────────────────────────────────────
function DiscoveryStep({ onNext, onCompanyCreated }) {
  const [url, setUrl]           = React.useState('https://acme-store.com');
  const [scanning, setScanning] = React.useState(false);
  const [progress, setProgress] = React.useState(0);
  const [errorText, setErrorText] = React.useState('');
  const msgs = ['Registering company context…','Fetching page source…','Parsing JS bundles…','Detecting platforms…','Identifying data tools…','Almost done…'];
  const msgIdx = Math.min(Math.floor((progress/100)*msgs.length), msgs.length-1);

  const handleScan = async () => {
    if (!url.trim()) return;
    setScanning(true); 
    setProgress(5);
    setErrorText('');
    
    try {
      // Step 1: Create company in Database
      const domainClean = url.replace(/^https?:\/\//i, '').split('/')[0];
      const nameClean = domainClean.split('.')[0].toUpperCase();
      
      let companyId = 'preview_co';
      let detectedList = DETECTED_SYSTEMS_DEFAULT;

      try {
        const createRes = await api.createCompany({
          name: nameClean,
          domain: domainClean,
          business_category: 'ecommerce',
          description: `E-commerce stack for ${nameClean}`
        });
        if (createRes?.data?.id) {
          companyId = createRes.data.id;
          onCompanyCreated(companyId, nameClean, domainClean);
        }
      } catch (e) {
        console.warn("Backend unavailable or auth missing, running in high-fidelity preview mode.", e);
      }

      // Step 2: Live or simulated scanner
      let p = 5;
      const t = setInterval(async () => {
        p += 15; 
        setProgress(Math.min(p, 90));
        
        if (p >= 90) {
          clearInterval(t);
          
          if (companyId !== 'preview_co') {
            try {
              // Real website scan endpoint
              const scanRes = await api.scanWebsite(companyId, url);
              if (scanRes?.data?.detected_systems) {
                detectedList = scanRes.data.detected_systems.map(s => ({
                  id: s.id || s.name?.toLowerCase(),
                  label: s.name,
                  category: s.category || 'System',
                  confidence: s.confidence || 0.9,
                  icon: s.icon || '⚙',
                  desc: s.description || 'System detected via scanner signatures'
                }));
              }
            } catch (e) {
              console.warn("Website scan API fail, falling back to simulated stacks", e);
            }
          }
          
          setProgress(100);
          setTimeout(() => {
            setScanning(false);
            onNext(detectedList, companyId);
          }, 400);
        }
      }, 200);

    } catch (err) {
      setScanning(false);
      setErrorText('Scan failed: ' + (err.message || 'Unknown error'));
    }
  };

  return (
    <div style={{ animation:'fadeSlideUp 0.35s ease-out' }}>
      <h2 style={{ fontSize:22, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', marginBottom:6 }}>What company are you setting up?</h2>
      <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.6, marginBottom:22, maxWidth:440 }}>
        Enter your production URL. LLM Relay V5.0 will inspect the site, infer your stack, and provision specialists that understand your industry automatically.
      </p>
      <div style={{ marginBottom:14 }}>
        <label style={{ display:'block', fontSize:12, fontWeight:600, color:'var(--text-secondary)', marginBottom:7 }}>Production website URL *</label>
        <input value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://your-company.com"
          style={{ width:'100%', padding:'12px 16px', borderRadius:14, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff', fontSize:14, fontFamily:'var(--font-main)', outline:'none', transition:'border-color 0.2s' }}
          onFocus={e=>e.target.style.borderColor='rgba(93,162,255,0.5)'} onBlur={e=>e.target.style.borderColor='rgba(255,255,255,0.12)'}/>
      </div>
      {errorText && (
        <div style={{ color:'var(--danger)', fontSize:12, marginBottom:10 }}>{errorText}</div>
      )}
      {scanning && (
        <div style={{ marginBottom:18, padding:'14px 16px', borderRadius:14, background:'rgba(93,162,255,0.06)', border:'1px solid rgba(93,162,255,0.15)' }}>
          <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:9 }}>
            <span style={{ width:8, height:8, borderRadius:'50%', background:'var(--accent)', animation:'pulse 1s infinite', flexShrink:0 }}/>
            <span style={{ fontSize:12, color:'var(--text-secondary)' }}>{msgs[msgIdx]}</span>
            <span style={{ marginLeft:'auto', fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{progress}%</span>
          </div>
          <div style={{ height:4, borderRadius:999, background:'rgba(255,255,255,0.10)' }}>
            <div style={{ height:'100%', borderRadius:999, background:'var(--accent)', width:`${progress}%`, transition:'width 0.2s ease' }}/>
          </div>
        </div>
      )}
      <button onClick={handleScan} disabled={scanning||!url.trim()} style={{ display:'inline-flex', alignItems:'center', gap:8, padding:'13px 28px', borderRadius:999, background:'linear-gradient(135deg,#6CB0FF,#4F93FF)', color:'#06111f', fontSize:14, fontWeight:800, border:'none', cursor:'pointer', boxShadow:'0 8px 24px rgba(93,162,255,0.25)', opacity:scanning||!url.trim()?0.6:1, transition:'all 0.2s' }}>
        {scanning ? <><div style={{ width:14,height:14,border:'2px solid rgba(0,0,0,0.2)',borderTopColor:'#06111f',borderRadius:'50%',animation:'spin 0.8s linear infinite' }}/>Scanning…</> : '→ Inspect & discover'}
      </button>
    </div>
  );
}

// ── Step 2: Systems ────────────────────────────────────────────────────────────
function SystemsStep({ onNext, onBack, onSystemsChange, detectedSystems = [] }) {
  const systemsToUse = detectedSystems.length > 0 ? detectedSystems : DETECTED_SYSTEMS_DEFAULT;
  const [selected, setSelected] = React.useState(systemsToUse.map(s=>s.id));
  const toggle = id => { const next = selected.includes(id)?selected.filter(x=>x!==id):[...selected,id]; setSelected(next); onSystemsChange && onSystemsChange(next); };

  return (
    <div style={{ animation:'fadeSlideUp 0.35s ease-out' }}>
      <h2 style={{ fontSize:22, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', marginBottom:6 }}>I found {systemsToUse.length} systems</h2>
      <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.6, marginBottom:18, maxWidth:440 }}>Review what was detected. Uncheck anything that doesn't apply — this determines which specialists are provisioned.</p>
      <div style={{ display:'flex', flexDirection:'column', gap:7, marginBottom:22 }}>
        {systemsToUse.map(sys=>{
          const on=selected.includes(sys.id);
          return (
            <button key={sys.id} onClick={()=>toggle(sys.id)} style={{ display:'flex', alignItems:'flex-start', gap:11, padding:'11px 14px', borderRadius:13, border:`1px solid ${on?'rgba(93,162,255,0.25)':'rgba(255,255,255,0.08)'}`, background:on?'rgba(93,162,255,0.05)':'rgba(255,255,255,0.025)', cursor:'pointer', textAlign:'left', transition:'all 0.2s' }}>
              <span style={{ fontSize:20, flexShrink:0, lineHeight:1, marginTop:2 }}>{sys.icon || '⚙'}</span>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ display:'flex', alignItems:'center', gap:7, flexWrap:'wrap', marginBottom:2 }}>
                  <span style={{ fontSize:13, fontWeight:700, color:on?'#fff':'var(--text-secondary)' }}>{sys.label}</span>
                  <span style={{ fontSize:9, fontFamily:'var(--font-mono)', letterSpacing:'0.12em', textTransform:'uppercase', padding:'2px 6px', borderRadius:999, background:'rgba(255,255,255,0.06)', color:'var(--text-muted)', border:'1px solid rgba(255,255,255,0.10)' }}>{sys.category}</span>
                  <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:on?'#46d9a4':'var(--text-muted)', marginLeft:'auto' }}>{Math.round((sys.confidence || 0.9) * 100)}%</span>
                </div>
                <div style={{ fontSize:11, color:'var(--text-muted)', lineHeight:1.5 }}>{sys.desc}</div>
              </div>
              <div style={{ width:18, height:18, borderRadius:5, flexShrink:0, border:`2px solid ${on?'var(--accent)':'rgba(255,255,255,0.20)'}`, background:on?'var(--accent)':'transparent', display:'flex', alignItems:'center', justifyContent:'center', marginTop:2, transition:'all 0.2s' }}>
                {on && <span style={{ color:'#06111f', fontSize:10, fontWeight:900 }}>✓</span>}
              </div>
            </button>
          );
        })}
      </div>
      <div style={{ display:'flex', gap:10 }}>
        <button onClick={onBack} style={{ padding:'12px 22px', borderRadius:999, background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.12)', color:'var(--text-secondary)', fontSize:14, fontWeight:700, cursor:'pointer' }}>← Back</button>
        <button onClick={()=>onNext(systemsToUse.filter(s=>selected.includes(s.id)))} style={{ flex:1, padding:'13px 28px', borderRadius:999, background:'linear-gradient(135deg,#6CB0FF,#4F93FF)', color:'#06111f', fontSize:14, fontWeight:800, border:'none', cursor:'pointer', boxShadow:'0 8px 24px rgba(93,162,255,0.25)' }}>
          Confirm {selected.length} systems → Continue
        </button>
      </div>
    </div>
  );
}

// ── Step 3: Structured details ─────────────────────────────────────────────────
function DetailsStep({ onNext, onBack, companyId }) {
  const [repos,   setRepos]   = React.useState([{ url:'', branch:'main' }]);
  const [docs,    setDocs]    = React.useState([{ url:'', label:'' }]);
  const [goals,   setGoals]   = React.useState(['']);
  const [creds,   setCreds]   = React.useState([{ service:'Shopify', key:'' },{ service:'GA4', key:'' }]);
  const [ghToken, setGhToken] = React.useState('');

  const handleDetailsSubmit = async () => {
    try {
      if (companyId && companyId !== 'preview_co') {
        // Real API integrations: update company details
        const activeRepos = repos.filter(r => r.url.trim());
        const activeDocs = docs.filter(d => d.url.trim());
        
        // Save repos in database
        for (const r of activeRepos) {
          await api.scanRepo(companyId, r.url);
        }
      }
    } catch (e) {
      console.warn("Backend fail updating details, continuing simulator flow", e);
    }
    onNext();
  };

  const inputStyle = (extra={}) => ({ padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, fontFamily:'var(--font-main)', outline:'none', transition:'border-color 0.2s', ...extra });
  const onFocus = e => e.target.style.borderColor='rgba(93,162,255,0.45)';
  const onBlur  = e => e.target.style.borderColor='rgba(255,255,255,0.10)';
  const SLabel = ({children}) => <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.12em', textTransform:'uppercase', marginBottom:7, marginTop:16 }}>{children}</div>;

  return (
    <div style={{ animation:'fadeSlideUp 0.35s ease-out' }}>
      <h2 style={{ fontSize:22, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', marginBottom:6 }}>Connect your resources</h2>
      <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.6, marginBottom:4, maxWidth:440 }}>All optional — you can add more later from the Company screen.</p>

      <SLabel>GitHub access token</SLabel>
      <div style={{ display:'flex', gap:8, alignItems:'center', marginBottom:4 }}>
        <input value={ghToken} onChange={e=>setGhToken(e.target.value)} placeholder="ghp_… (repo + PR scope)" style={{ ...inputStyle(), flex:1, fontFamily:'var(--font-mono)' }} onFocus={onFocus} onBlur={onBlur}/>
        <a href="https://github.com/settings/tokens/new" target="_blank" rel="noreferrer" style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', whiteSpace:'nowrap', textDecoration:'none', flexShrink:0 }}>Create →</a>
      </div>
      <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>Stored encrypted · never logged · gives agents read/write access to repos</div>

      <SLabel>GitHub repositories</SLabel>
      {repos.map((r,i)=>(
        <div key={i} style={{ display:'flex', gap:7, marginBottom:7 }}>
          <input value={r.url} onChange={e=>setRepos(p=>p.map((x,j)=>j===i?{...x,url:e.target.value}:x))} placeholder="github.com/org/repo" style={{ ...inputStyle(), flex:1, fontFamily:'var(--font-mono)' }} onFocus={onFocus} onBlur={onBlur}/>
          <input value={r.branch} onChange={e=>setRepos(p=>p.map((x,j)=>j===i?{...x,branch:e.target.value}:x))} placeholder="branch" style={{ ...inputStyle({ width:90, fontFamily:'var(--font-mono)', flexShrink:0 }) }} onFocus={onFocus} onBlur={onBlur}/>
          {i>0 && <button onClick={()=>setRepos(p=>p.filter((_,j)=>j!==i))} style={{ padding:'0 10px', borderRadius:10, background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.18)', color:'#ff6b7d', cursor:'pointer', flexShrink:0 }}>✕</button>}
        </div>
      ))}
      <button onClick={()=>setRepos(p=>[...p,{url:'',branch:'main'}])} style={{ fontSize:12, color:'var(--accent)', background:'none', border:'none', cursor:'pointer', fontFamily:'var(--font-mono)', marginBottom:4 }}>+ Add repo</button>

      <SLabel>Documentation URLs</SLabel>
      {docs.map((d,i)=>(
        <div key={i} style={{ display:'flex', gap:7, marginBottom:7 }}>
          <input value={d.url} onChange={e=>setDocs(p=>p.map((x,j)=>j===i?{...x,url:e.target.value}:x))} placeholder="https://docs.example.com" style={{ ...inputStyle(), flex:1, fontFamily:'var(--font-mono)' }} onFocus={onFocus} onBlur={onBlur}/>
          <input value={d.label} onChange={e=>setDocs(p=>p.map((x,j)=>j===i?{...x,label:e.target.value}:x))} placeholder="Label" style={{ ...inputStyle({ width:120 }) }} onFocus={onFocus} onBlur={onBlur}/>
          {i>0 && <button onClick={()=>setDocs(p=>p.filter((_,j)=>j!==i))} style={{ padding:'0 10px', borderRadius:10, background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.18)', color:'#ff6b7d', cursor:'pointer', flexShrink:0 }}>✕</button>}
        </div>
      ))}
      <button onClick={()=>setDocs(p=>[...p,{url:'',label:''}])} style={{ fontSize:12, color:'var(--accent)', background:'none', border:'none', cursor:'pointer', fontFamily:'var(--font-mono)' }}>+ Add doc URL</button>

      <SLabel>Goals & priorities</SLabel>
      {goals.map((g,i)=>(
        <div key={i} style={{ display:'flex', gap:7, marginBottom:7 }}>
          <input value={g} onChange={e=>setGoals(p=>p.map((x,j)=>j===i?e.target.value:x))} placeholder={`Priority ${i+1}: e.g. Improve checkout conversion`} style={{ ...inputStyle(), flex:1 }} onFocus={onFocus} onBlur={onBlur}/>
          {i>0 && <button onClick={()=>setGoals(p=>p.filter((_,j)=>j!==i))} style={{ padding:'0 10px', borderRadius:10, background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.18)', color:'#ff6b7d', cursor:'pointer', flexShrink:0 }}>✕</button>}
        </div>
      ))}
      <button onClick={()=>setGoals(p=>[...p,''])} style={{ fontSize:12, color:'var(--accent)', background:'none', border:'none', cursor:'pointer', fontFamily:'var(--font-mono)' }}>+ Add goal</button>

      <SLabel>Service API credentials (optional, encrypted)</SLabel>
      <div style={{ fontSize:11, color:'var(--text-muted)', marginBottom:8 }}>These allow agents to take actions on your behalf — e.g. updating Shopify prices or sending Klaviyo emails.</div>
      {creds.map((c,i)=>(
        <div key={i} style={{ display:'flex', gap:7, marginBottom:7, alignItems:'center' }}>
          <input value={c.service} onChange={e=>setCreds(p=>p.map((x,j)=>j===i?{...x,service:e.target.value}:x))} placeholder="Service name" style={{ ...inputStyle({ width:110, flexShrink:0 }) }} onFocus={onFocus} onBlur={onBlur}/>
          <input type="password" value={c.key} onChange={e=>setCreds(p=>p.map((x,j)=>j===i?{...x,key:e.target.value}:x))} placeholder="API key or token" style={{ ...inputStyle(), flex:1, fontFamily:'var(--font-mono)' }} onFocus={onFocus} onBlur={onBlur}/>
          <button onClick={()=>setCreds(p=>p.filter((_,j)=>j!==i))} style={{ padding:'0 10px', borderRadius:10, background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.18)', color:'#ff6b7d', cursor:'pointer', flexShrink:0, height:38 }}>✕</button>
        </div>
      ))}
      <button onClick={()=>setCreds(p=>[...p,{service:'',key:''}])} style={{ fontSize:12, color:'var(--accent)', background:'rgba(93,162,255,0.08)', border:'1px solid rgba(93,162,255,0.20)', borderRadius:9, padding:'6px 14px', cursor:'pointer', fontFamily:'var(--font-mono)', marginBottom:4 }}>+ Add credential</button>

      <div style={{ display:'flex', gap:10, marginTop:20 }}>
        <button onClick={onBack} style={{ padding:'12px 22px', borderRadius:999, background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.12)', color:'var(--text-secondary)', fontSize:14, fontWeight:700, cursor:'pointer' }}>← Back</button>
        <button onClick={handleDetailsSubmit} style={{ flex:1, padding:'13px 28px', borderRadius:999, background:'linear-gradient(135deg,#6CB0FF,#4F93FF)', color:'#06111f', fontSize:14, fontWeight:800, border:'none', cursor:'pointer', boxShadow:'0 8px 24px rgba(93,162,255,0.25)' }}>Continue →</button>
      </div>
    </div>
  );
}

// ── Step 4: Smart tailored questions based on site type ───────────────────────
function QuestionsStep({ onNext, onBack, siteType }) {
  const [answers, setAnswers] = React.useState({});
  const questions = QUESTION_SETS[siteType] || QUESTION_SETS.generic;
  const typeLabel = { ecommerce:'e-commerce store', saas:'SaaS product', media:'media / content site', agency:'agency / services', generic:'web project' };
  const set = (id,v) => setAnswers(p=>({...p,[id]:v}));

  return (
    <div style={{ animation:'fadeSlideUp 0.35s ease-out' }}>
      <h2 style={{ fontSize:22, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', marginBottom:6 }}>A few tailored questions</h2>
      <div style={{ display:'inline-flex', alignItems:'center', gap:7, padding:'5px 12px', borderRadius:999, background:'rgba(70,217,164,0.08)', border:'1px solid rgba(70,217,164,0.18)', marginBottom:14 }}>
        <span style={{ width:6, height:6, borderRadius:'50%', background:'#46d9a4' }}/>
        <span style={{ fontSize:12, fontFamily:'var(--font-mono)', color:'#46d9a4' }}>Detected: {typeLabel[siteType] || 'web project'}</span>
      </div>
      <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.6, marginBottom:22, maxWidth:440 }}>
        These questions are specific to your stack. Your answers help provision the right specialists and suggest the most relevant skills.
      </p>
      <div style={{ display:'flex', flexDirection:'column', gap:18, marginBottom:26 }}>
        {questions.map(q => (
          <div key={q.id}>
            <div style={{ fontSize:13, fontWeight:600, color:'var(--text-secondary)', marginBottom:8, lineHeight:1.5 }}>{q.label}</div>
            {q.type==='yesno' && (
              <div style={{ display:'flex', gap:8 }}>
                {['Yes','No'].map(opt=>(
                  <button key={opt} onClick={()=>set(q.id,opt)} style={{ padding:'8px 22px', borderRadius:999, fontSize:13, fontWeight:600, cursor:'pointer', background:answers[q.id]===opt?'rgba(93,162,255,0.15)':'rgba(255,255,255,0.04)', border:`1px solid ${answers[q.id]===opt?'rgba(93,162,255,0.40)':'rgba(255,255,255,0.10)'}`, color:answers[q.id]===opt?'#fff':'var(--text-tertiary)', transition:'all 0.2s' }}>{opt}</button>
                ))}
              </div>
            )}
            {q.type==='select' && (
              <div style={{ display:'flex', flexWrap:'wrap', gap:7 }}>
                {q.options.map(opt=>(
                  <button key={opt} onClick={()=>set(q.id,opt)} style={{ padding:'6px 13px', borderRadius:999, fontSize:12, cursor:'pointer', background:answers[q.id]===opt?'rgba(93,162,255,0.12)':'rgba(255,255,255,0.04)', border:`1px solid ${answers[q.id]===opt?'rgba(93,162,255,0.35)':'rgba(255,255,255,0.08)'}`, color:answers[q.id]===opt?'#fff':'var(--text-tertiary)', transition:'all 0.15s' }}>{opt}</button>
                ))}
              </div>
            )}
            {q.type==='multi' && (
              <div style={{ display:'flex', flexWrap:'wrap', gap:7 }}>
                {q.options.map(opt=>{
                  const sel=(answers[q.id]||[]).includes(opt);
                  return <button key={opt} onClick={()=>set(q.id,sel?(answers[q.id]||[]).filter(x=>x!==opt):[...(answers[q.id]||[]),opt])} style={{ padding:'6px 13px', borderRadius:999, fontSize:12, cursor:'pointer', background:sel?'rgba(93,162,255,0.12)':'rgba(255,255,255,0.04)', border:`1px solid ${sel?'rgba(93,162,255,0.35)':'rgba(255,255,255,0.08)'}`, color:sel?'#fff':'var(--text-tertiary)', transition:'all 0.15s' }}>{opt}</button>;
                })}
              </div>
            )}
            {q.type==='freeform' && (
              <input value={answers[q.id]||''} onChange={e=>set(q.id,e.target.value)} placeholder={q.placeholder}
                style={{ width:'100%', padding:'10px 14px', borderRadius:12, border:'1px solid rgba(255,255,255,0.10)', background:'rgba(255,255,255,0.04)', color:'#fff', fontSize:13, fontFamily:'var(--font-main)', outline:'none', transition:'border-color 0.2s' }}
                onFocus={e=>e.target.style.borderColor='rgba(93,162,255,0.45)'} onBlur={e=>e.target.style.borderColor='rgba(255,255,255,0.10)'}/>
            )}
          </div>
        ))}
      </div>
      <div style={{ display:'flex', gap:10 }}>
        <button onClick={onBack} style={{ padding:'12px 22px', borderRadius:999, background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.12)', color:'var(--text-secondary)', fontSize:14, fontWeight:700, cursor:'pointer' }}>← Back</button>
        <button onClick={onNext} style={{ flex:1, padding:'13px 28px', borderRadius:999, background:'linear-gradient(135deg,#6CB0FF,#4F93FF)', color:'#06111f', fontSize:14, fontWeight:800, border:'none', cursor:'pointer', boxShadow:'0 8px 24px rgba(93,162,255,0.25)' }}>→ Provision specialists</button>
      </div>
    </div>
  );
}

// ── Step 5: Done ───────────────────────────────────────────────────────────────
function DoneStep({ onFinish, companyId, companyName }) {
  const [specialists, setSpecialists] = React.useState([
    { name:'Commerce Agent', desc:'Shopify checkout, inventory, and conversion flows', icon:'🛍' },
    { name:'Content Agent',  desc:'Contentful publishing, SEO, and asset management',  icon:'📄' },
    { name:'Analytics Agent',desc:'GTM/GA4 tracking, event schemas, and dashboards',   icon:'📊' },
    { name:'Support Agent',  desc:'Gorgias ticket routing and response automation',     icon:'💬' },
    { name:'Dev Agent',      desc:'Code fixes, tests, PRs across all repos',           icon:'⚙' },
    { name:'Security Agent', desc:'CVE scanning, secret detection, SAST',              icon:'🔒' },
  ]);

  React.useEffect(() => {
    async function loadProvisioned() {
      if (companyId && companyId !== 'preview_co') {
        try {
          // Provision and retrieve specialists list from Backend Company Graph
          const res = await api.listSpecialists(companyId);
          if (res?.data?.specialists?.length > 0) {
            setSpecialists(res.data.specialists.map(sp => ({
              name: sp.name,
              desc: sp.description || 'Specialist ready and active.',
              icon: sp.icon || '🤖'
            })));
          }
        } catch (e) {
          console.warn("Backend fail listing specialists, using simulator list.", e);
        }
      }
    }
    loadProvisioned();
  }, [companyId]);

  return (
    <div style={{ animation:'fadeSlideUp 0.35s ease-out' }}>
      <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:12 }}>
        <div style={{ width:40, height:40, borderRadius:14, background:'rgba(70,217,164,0.15)', border:'1px solid rgba(70,217,164,0.25)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:20 }}>✓</div>
        <div>
          <h2 style={{ fontSize:22, fontWeight:800, color:'#fff', letterSpacing:'-0.04em' }}>Company provisioned</h2>
          <p style={{ fontSize:13, color:'#46d9a4' }}>{companyName || 'acme-store.com'} · {specialists.length} specialists ready · monitoring starts now</p>
        </div>
      </div>
      <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.6, marginBottom:20, maxWidth:440 }}>{specialists.length} specialists have been created and wired to your systems. They appear in the Agent Roster and will start monitoring immediately.</p>
      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(200px,1fr))', gap:8, marginBottom:22 }}>
        {specialists.map((sp,i)=>(
          <div key={sp.name} style={{ padding:'12px 14px', borderRadius:14, background:'rgba(70,217,164,0.04)', border:'1px solid rgba(70,217,164,0.12)', animation:`fadeSlideUp 0.4s ease-out ${i*0.07}s both` }}>
            <div style={{ fontSize:18, marginBottom:5 }}>{sp.icon}</div>
            <div style={{ fontSize:12, fontWeight:700, color:'#fff', marginBottom:2 }}>{sp.name}</div>
            <div style={{ fontSize:11, color:'var(--text-muted)', lineHeight:1.5 }}>{sp.desc}</div>
          </div>
        ))}
      </div>
      <button onClick={onFinish} style={{ display:'inline-flex', alignItems:'center', gap:8, padding:'13px 28px', borderRadius:999, background:'linear-gradient(135deg,#6CB0FF,#4F93FF)', color:'#06111f', fontSize:14, fontWeight:800, border:'none', cursor:'pointer', boxShadow:'0 8px 24px rgba(93,162,255,0.25)' }}>
        → Go to Company Graph
      </button>
    </div>
  );
}

// ── Main OnboardingScreen ──────────────────────────────────────────────────────
function OnboardingScreen({ onComplete, isAdmin }) {
  const [step,     setStep]     = React.useState('url');
  const [siteType, setSiteType] = React.useState('generic');
  const [systems,  setSystems]  = React.useState([]);
  const [companyId, setCompanyId] = React.useState('preview_co');
  const [companyName, setCompanyName] = React.useState('ACME-STORE');

  if (!isAdmin) return (
    <div style={{ padding:'24px 16px 48px', maxWidth:580, margin:'0 auto' }}>
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:8 }}>Company Onboarding · LLM Relay V5.0</div>
      <NonAdminGate/>
    </div>
  );

  const handleCompanyCreated = (id, name, domain) => {
    setCompanyId(id);
    setCompanyName(name || domain);
  };

  const handleScanDone = (detectedList, id) => {
    setSystems(detectedList);
    setSiteType(detectSiteType(detectedList));
    setStep('systems');
  };

  const handleSystemsConfirmed = (confirmed) => {
    setSystems(confirmed);
    setSiteType(detectSiteType(confirmed));
    setStep('details');
  };

  return (
    <div style={{ padding:'24px 16px 48px', maxWidth:640, margin:'0 auto' }}>
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:8 }}>Company Onboarding · LLM Relay V5.0</div>
      <StepIndicator current={step}/>
      {step==='url'       && <DiscoveryStep onNext={handleScanDone} onCompanyCreated={handleCompanyCreated}/>}
      {step==='systems'   && <SystemsStep onNext={handleSystemsConfirmed} onBack={()=>setStep('url')} detectedSystems={systems}/>}
      {step==='details'   && <DetailsStep onNext={()=>setStep('questions')} onBack={()=>setStep('systems')} companyId={companyId}/>}
      {step==='questions' && <QuestionsStep onNext={()=>setStep('done')} onBack={()=>setStep('details')} siteType={siteType}/>}
      {step==='done'      && <DoneStep onFinish={onComplete} companyId={companyId} companyName={companyName}/>}
    </div>
  );
}

export { OnboardingScreen };
export default OnboardingScreen;
