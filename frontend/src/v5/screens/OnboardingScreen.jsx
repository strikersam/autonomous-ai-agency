/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import * as api from '../../api';
import { COMPANY_ID_KEY } from './CompanyScreen';

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
    { id:'pain',     label:'What is your biggest pain point right now?', type:'freeform', placeholder:'e.g. slow checkout, cart abandonment, stock visibility...' },
  ],
  saas: [
    { id:'trials',   label:'Do you have a free trial or freemium tier?', type:'yesno' },
    { id:'deploys',  label:'How often do you deploy?', type:'select', options:['Continuous CI/CD','Daily','Weekly','Quarterly'] },
    { id:'kpis',     label:'Which metrics matter most?', type:'multi', options:['MRR growth','Churn rate','Activation rate','Support tickets','Feature adoption','NPS'] },
    { id:'pain',     label:'What is your biggest technical pain point?', type:'freeform', placeholder:'e.g. onboarding drop-off, high churn, slow CI...' },
  ],
  media: [
    { id:'publishing',label:'How many articles/posts do you publish per week?', type:'select', options:['1-5','6-20','20-50','50+'] },
    { id:'deploys',   label:'How often do you deploy the platform?', type:'select', options:['Continuous CI/CD','Weekly','Monthly','Rarely'] },
    { id:'kpis',      label:'Which metrics matter most?', type:'multi', options:['Page views','Time on site','Email subscribers','Ad revenue','SEO ranking','Engagement rate'] },
    { id:'pain',      label:'What is your biggest pain point?', type:'freeform', placeholder:'e.g. slow editorial publishing, broken embeds, SEO gaps...' },
  ],
  agency: [
    { id:'clients',   label:'How many active client projects do you manage?', type:'select', options:['1-5','6-15','16-50','50+'] },
    { id:'deploys',   label:'How often do you deliver to clients?', type:'select', options:['Daily','Weekly','Monthly','Per project'] },
    { id:'kpis',      label:'Which outcomes matter most?', type:'multi', options:['Project delivery speed','Bug rate','Client satisfaction','Code quality','Team velocity','Revenue per project'] },
    { id:'pain',      label:'What is your biggest operational pain point?', type:'freeform', placeholder:'e.g. scope creep, manual QA, context switching between clients...' },
  ],
  generic: [
    { id:'deploys',  label:'How often do you deploy or ship changes?', type:'select', options:['Multiple times a day','Daily','Weekly','Monthly or less'] },
    { id:'team',     label:'How large is your engineering team?', type:'select', options:['Solo','2-5','6-20','20+'] },
    { id:'kpis',     label:'Which outcomes matter most?', type:'multi', options:['Code quality','Deployment speed','Bug rate','Team velocity','Cost reduction','Security posture'] },
    { id:'pain',     label:'What is your biggest technical pain point?', type:'freeform', placeholder:'e.g. technical debt, slow deployments, poor test coverage...' },
  ],
};

// Detect site type from discovered systems — checks both system_type and name independently
function detectSiteType(systems) {
  const vals = (systems || []).flatMap(s => [s.system_type, s.name].filter(Boolean).map(v => v.toLowerCase()));
  if (vals.some(n => ['shopify','woocommerce','bigcommerce','magento','ecommerce'].includes(n))) return 'ecommerce';
  if (vals.some(n => ['stripe','chargebee','paddle','saas'].includes(n))) return 'saas';
  if (vals.some(n => ['wordpress','ghost','contentful','strapi','sanity','cms','media'].includes(n))) return 'media';
  return 'generic';
}

// Detect business category from discovered systems — checks both system_type and name independently
function detectBusinessCategory(systems) {
  const vals = (systems || []).flatMap(s => [s.system_type, s.name].filter(Boolean).map(v => v.toLowerCase()));
  if (vals.some(n => ['shopify','woocommerce','bigcommerce','magento','ecommerce'].includes(n))) return 'ecommerce';
  if (vals.some(n => ['stripe','chargebee','paddle'].includes(n))) return 'saas';
  if (vals.some(n => ['wordpress','ghost','contentful','strapi','sanity','cms'].includes(n))) return 'media';
  if (vals.some(n => ['salesforce','hubspot'].includes(n))) return 'agency';
  return 'other';
}

const ONBOARDING_ANSWERS_KEY = 'v5_onboarding_answers';

// extractErr removed — use api.fmtErr() consistently across all screens
function isUnauth(err) {
  return err?.response?.status === 401 || err?.response?.status === 403;
}

function StepIndicator({ current, onStepClick }) {
  const idx = STEPS.findIndex(s=>s.id===current);
  return (
    <div style={{ display:'flex', alignItems:'center', gap:0, marginBottom:26, overflowX:'auto' }} className="scrollbar-hide">
      {STEPS.map((step,i)=>{
        const done=i<idx; const active=i===idx; const clickable = done && onStepClick;
        return (
          <React.Fragment key={step.id}>
            <button
              onClick={clickable ? () => onStepClick(step.id) : undefined}
              disabled={!clickable}
              style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:4, flexShrink:0, background:'none', border:'none', cursor:clickable?'pointer':'default', padding:0, font:'inherit', opacity: clickable ? 1 : 0.7 }}
              title={clickable ? `Go back to ${step.label}` : (active ? `Current: ${step.label}` : '')}
            >
              <div style={{ width:26, height:26, borderRadius:'50%', display:'flex', alignItems:'center', justifyContent:'center', background:done?'#46d9a4':active?'var(--accent)':'rgba(255,255,255,0.07)', border:`2px solid ${done?'#46d9a4':active?'var(--accent)':'rgba(255,255,255,0.14)'}`, fontSize:11, fontWeight:700, color:done||active?'#06111f':'var(--text-muted)', transition:'all 0.3s' }}>
                {done?'✓':i+1}
              </div>
              <div style={{ fontSize:10, fontWeight:600, color:active?'#fff':done?'var(--text-tertiary)':'var(--text-muted)', whiteSpace:'nowrap' }}>{step.label}</div>
            </button>
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
        Your request has been sent to the administrator. You will receive confirmation once your company is provisioned — usually within 24 hours.
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
            Company onboarding requires admin access. Send a request below — the admin will configure your company and let you know when it is ready.
          </div>
        </div>
      </div>
      <h2 style={{ fontSize:22, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', marginBottom:6 }}>Request company setup</h2>
      <p style={{ fontSize:14, color: 'var(--text-tertiary)', lineHeight:1.6, marginBottom:20, maxWidth:440 }}>Describe what you need. The admin will set up your company, connect your systems, and let you know when it is ready.</p>
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
            placeholder="Describe your company, what you would like to automate, your website URL, and any systems you use (e.g. Shopify, WordPress, Salesforce)..."
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

// Maps the backend scanner's SystemType to a human label + icon for display.
const SYSTEM_TYPE_META = {
  CMS: { category: 'CMS & Content', icon: '📄' },
  CRM: { category: 'CRM & Sales', icon: '💼' },
  OMS: { category: 'Commerce & Orders', icon: '🛍' },
  PIM: { category: 'Product Info', icon: '🏷' },
  DAM: { category: 'Digital Assets', icon: '🖼' },
  ERP: { category: 'ERP', icon: '🏢' },
  HRM: { category: 'People & HR', icon: '👥' },
  LMS: { category: 'Learning', icon: '🎓' },
  analytics: { category: 'Analytics & Tracking', icon: '📊' },
  payment_gateway: { category: 'Payments & Invoicing', icon: '💳' },
  shipping: { category: 'Shipping & Logistics', icon: '📦' },
  tax: { category: 'Tax', icon: '🧾' },
  inventory: { category: 'Inventory', icon: '📋' },
  marketing_automation: { category: 'Marketing', icon: '🎯' },
  email_service: { category: 'Email & Comms', icon: '✉️' },
  search: { category: 'Search', icon: '🔍' },
  database: { category: 'Data & Storage', icon: '🗄' },
  cache: { category: 'Performance & Caching', icon: '⚡' },
  cdc: { category: 'Data Pipelines', icon: '🔁' },
  message_queue: { category: 'Messaging', icon: '📨' },
  api_gateway: { category: 'API Gateway', icon: '🔀' },
  auth: { category: 'Identity & Auth', icon: '🔒' },
  billing: { category: 'Billing', icon: '💰' },
  support: { category: 'Support & Helpdesk', icon: '💬' },
  chat: { category: 'Live Chat', icon: '💬' },
  video: { category: 'Media & Video', icon: '🎬' },
  voice: { category: 'Voice', icon: '📞' },
  iot: { category: 'IoT', icon: '📡' },
  ai_ml: { category: 'AI & ML', icon: '🧠' },
  custom: { category: 'Infrastructure & Other', icon: '⚙' },
};

function DiscoveryStep({ onNext, onCompanyCreated }) {
  const [url, setUrl]           = React.useState('');
  const [scanning, setScanning] = React.useState(false);
  const [progress, setProgress] = React.useState(0);
  const [errorText, setErrorText] = React.useState('');
  const mountedRef = React.useRef(true);
  const progressTimerRef = React.useRef(null);
  // BUG-15: guard the progressTimer interval so it doesn't keep running
  // after the DiscoveryStep unmounts mid-scan. The ref tracks the interval
  // ID so the cleanup can clear it; without this the interval ticks every
  // 300ms forever even though mountedRef blocks setState.
  React.useEffect(() => () => {
    mountedRef.current = false;
    if (progressTimerRef.current) {
      clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;
    }
  }, []);
  const msgs = ['Registering company context...','Fetching page source...','Parsing JS bundles...','Detecting platforms...','Identifying data tools...','Almost done...'];
  const msgIdx = Math.min(Math.floor((progress/100)*msgs.length), msgs.length-1);

  const handleScan = async () => {
    if (!url.trim()) return;
    // Defensive: clear any orphaned interval from a previous scan (e.g. if
    // the component remounts mid-scan or the disabled guard is removed).
    if (progressTimerRef.current) {
      clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;
    }
    setScanning(true);
    setProgress(5);
    setErrorText('');

    const domainClean = url.replace(/^https?:\/\//i, '').split('/')[0];
    const nameClean = domainClean.replace(/^www\./i, '').split('.')[0].toUpperCase();
    const displayDomain = domainClean.replace(/^www\./i, '');

    // Step 1: Scan website first to detect systems, then create company with detected category.
    // This ensures business_category reflects the real scan results, not a hardcoded guess.
    let detectedSystems = [];
    let businessCategory = 'other';

    try {
      // Create a temporary company first (needed for the scan endpoint)
      const createRes = await api.createCompany({
        name: nameClean,
        domain: domainClean,
        business_category: 'other',
        description: `Technology stack for ${nameClean}`,
      });
      const companyId = createRes?.data?.company?.id || createRes?.data?.id;
      if (!companyId) throw new Error('Company created but no ID returned.');
      onCompanyCreated(companyId, nameClean, displayDomain);
    } catch (e) {
      setScanning(false);
      setProgress(0);
      if (isUnauth(e)) {
        setErrorText('You must be logged in to set up a company. Please log in and try again.');
      } else {
        setErrorText('Could not create company: ' + (api.fmtErr(e?.response?.data?.detail) || e?.message || 'Something went wrong.'));
      }
      return;
    }

    // Step 2: Animate progress while the real scan runs.
    let p = 5;
    progressTimerRef.current = setInterval(() => {
      if (!mountedRef.current) return;
      p = Math.min(p + 12, 88);
      setProgress(p);
    }, 300);

    try {
      // Re-read companyId from localStorage (set by onCompanyCreated above)
      const cid = (() => { try { return localStorage.getItem(COMPANY_ID_KEY); } catch { return null; } })();
      if (!cid) { setScanning(false); setErrorText('Company ID not found after creation.'); return; }

      const scanRes = await api.scanWebsite(cid, url);
      clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;

      const rawSystems = Array.isArray(scanRes?.data?.detected_systems)
        ? scanRes.data.detected_systems
        : [];

      detectedSystems = rawSystems;
      businessCategory = detectBusinessCategory(rawSystems);

      // Update company with detected business category if different from default
      if (businessCategory !== 'other') {
        try {
          await api.updateCompany(cid, { business_category: businessCategory });
        } catch { /* best-effort update */ }
      }

      const detectedList = rawSystems.map(s => {
        const meta = SYSTEM_TYPE_META[s.system_type] || SYSTEM_TYPE_META.custom;
        const ev = Array.isArray(s.evidence) && s.evidence.length ? s.evidence[0] : null;
        return {
          id: s.id || (s.name || '').toLowerCase().replace(/\s+/g, '-') || String(Math.random()),
          system_type: s.system_type,
          name: s.name,
          label: s.name,
          category: meta.category,
          confidence: s.confidence || 0.9,
          icon: meta.icon,
          desc: ev ? `Detected via ${ev.type}: ${ev.value}` : 'Detected via scanner signatures',
        };
      });

      setProgress(100);
      setTimeout(() => {
        setScanning(false);
        onNext(detectedList, cid);
      }, 350);
    } catch (e) {
      clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;
      setScanning(false);
      setProgress(0);
      setErrorText('Website scan failed: ' + (api.fmtErr(e?.response?.data?.detail) || e?.message || 'Something went wrong.'));
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
        {scanning ? <><div style={{ width:14,height:14,border:'2px solid rgba(0,0,0,0.2)',borderTopColor:'#06111f',borderRadius:'50%',animation:'spin 0.8s linear infinite' }}/>Scanning...</> : '→ Inspect & discover'}
      </button>
    </div>
  );
}

// ── Step 2: Systems ────────────────────────────────────────────────────────────
function SystemsStep({ onNext, onBack, onSystemsChange, detectedSystems = [] }) {
  const systemsToUse = detectedSystems;
  const [selected, setSelected] = React.useState(systemsToUse.map(s=>s.id));
  const toggle = id => { const next = selected.includes(id)?selected.filter(x=>x!==id):[...selected,id]; setSelected(next); onSystemsChange && onSystemsChange(next); };

  return (
    <div style={{ animation:'fadeSlideUp 0.35s ease-out' }}>
      <h2 style={{ fontSize:22, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', marginBottom:6 }}>
        {systemsToUse.length > 0 ? `I found ${systemsToUse.length} system${systemsToUse.length === 1 ? '' : 's'}` : 'No systems detected — try scanning with a different URL or check that the site is accessible'}
      </h2>
      <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.6, marginBottom:18, maxWidth:440 }}>
        {systemsToUse.length > 0
          ? 'Review what was detected. Uncheck anything that does not apply — this determines which specialists are provisioned.'
          : 'The scanner could not identify any recognisable systems on this URL. You can continue anyway — specialists will be set up based on your goals.'}
      </p>
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
  const [saving,  setSaving]  = React.useState(false);
  const [saveError, setSaveError] = React.useState(null);

  const handleDetailsSubmit = async () => {
    if (saving) return;
    setSaving(true); setSaveError(null);

    // GitHub token — persist via PUT /api/github/token
    if (ghToken.trim()) {
      try {
        await api.setGithubToken(ghToken.trim());
      } catch (e) {
        const detail = e?.response?.data?.detail;
        setSaveError(detail ? api.fmtErr(detail) : (e?.message || 'GitHub token could not be saved — check the token scope and try again.'));
        setSaving(false);
        return;
      }
    }

    // Service API credentials — persist via secrets store (BUG-25)
    const validCreds = creds.filter(c => c.service.trim() && c.key.trim());
    for (const c of validCreds) {
      try {
        await api.API.post('/api/setup/secret', {
          name: `onboarding_${c.service.trim().toLowerCase().replace(/\s+/g, '_')}`,
          value: c.key.trim(),
          description: `API credential for ${c.service.trim()} (entered during onboarding)`,
        });
      } catch (e) {
        console.warn('Credential save failed during onboarding (non-blocking)', c.service, e);
      }
    }

    // Repo scans — always attempt (no preview_co guard)
    try {
      if (companyId) {
        for (const r of repos.filter(r => r.url.trim())) {
          await api.scanRepo(companyId, r.url);
        }
      }
    } catch (e) {
      console.warn('Repo scan failed during onboarding (non-blocking)', e);
    }

    // Save goals to localStorage AND send to company (BUG-25)
    const cleanGoals = goals.filter(g => g.trim());
    try {
      if (cleanGoals.length > 0) {
        const stored = JSON.parse(localStorage.getItem('v5_onboarding_details') || '{}');
        stored.goals = cleanGoals;
        localStorage.setItem('v5_onboarding_details', JSON.stringify(stored));
        // Also send goals to the backend so they become part of the company profile
        if (companyId) {
          await api.updateCompany(companyId, {
            description: cleanGoals.slice(0, 3).join('; '),
          }).catch(() => {});
        }
      }
    } catch {}

    setSaving(false);
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
        <input value={ghToken} onChange={e=>setGhToken(e.target.value)} placeholder="ghp_... (repo + PR scope)" style={{ ...inputStyle(), flex:1, fontFamily:'var(--font-mono)' }} onFocus={onFocus} onBlur={onBlur}/>
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

      {saveError && <div style={{ marginTop:16, padding:'10px 14px', borderRadius:10, background:'rgba(255,107,125,0.10)', border:'1px solid rgba(255,107,125,0.25)', color:'#ff6b7d', fontSize:12 }}>{saveError}</div>}
      <div style={{ display:'flex', gap:10, marginTop:20 }}>
        <button onClick={onBack} disabled={saving} style={{ padding:'12px 22px', borderRadius:999, background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.12)', color:'var(--text-secondary)', fontSize:14, fontWeight:700, cursor:'pointer' }}>← Back</button>
        <button onClick={handleDetailsSubmit} disabled={saving} style={{ flex:1, padding:'13px 28px', borderRadius:999, background:'linear-gradient(135deg,#6CB0FF,#4F93FF)', color:'#06111f', fontSize:14, fontWeight:800, border:'none', cursor:saving?'wait':'pointer', opacity:saving?0.7:1, boxShadow:'0 8px 24px rgba(93,162,255,0.25)' }}>{saving ? 'Saving...' : 'Continue →'}</button>
      </div>
    </div>
  );
}

// ── Step 4: Smart tailored questions based on site type ───────────────────────
function QuestionsStep({ onNext, onBack, siteType }) {
  const [answers, setAnswers] = React.useState(() => {
    // Restore previously saved answers for this site type
    try {
      const saved = JSON.parse(localStorage.getItem(ONBOARDING_ANSWERS_KEY) || '{}');
      return saved[siteType] || {};
    } catch { return {}; }
  });
  const questions = QUESTION_SETS[siteType] || QUESTION_SETS.generic;
  const typeLabel = { ecommerce:'e-commerce store', saas:'SaaS product', media:'media / content site', agency:'agency / services', generic:'web project' };
  const set = (id,v) => {
    setAnswers(p => {
      const next = {...p, [id]:v};
      // Persist answers to localStorage so they survive tab switches
      try {
        const saved = JSON.parse(localStorage.getItem(ONBOARDING_ANSWERS_KEY) || '{}');
        saved[siteType] = next;
        localStorage.setItem(ONBOARDING_ANSWERS_KEY, JSON.stringify(saved));
      } catch {}
      return next;
    });
  };

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
function DoneStep({ onFinish, onRestart, onBack, companyId, companyName }) {
  const [specialists, setSpecialists] = React.useState(null); // null = loading
  const [specsError, setSpecsError]   = React.useState('');

  React.useEffect(() => {
    if (!companyId) { setSpecialists([]); return; }

    let settled = false;
    const finish = (list, err) => {
      if (settled) return;
      settled = true;
      setSpecialists(list);
      if (err) setSpecsError(err);
    };

    // Load whatever specialists exist for the company. This is the single
    // source of truth for the loading state — it runs regardless of whether
    // provisioning succeeds, hangs, or errors, so the UI never sticks on
    // "Loading specialists..." forever.
    const loadSpecialists = (errPrefix) =>
      api.listSpecialists(companyId)
        .then(res => {
          const list = Array.isArray(res?.data?.specialists) ? res.data.specialists : [];
          finish(list.map(sp => ({
            name: sp.name,
            desc: sp.description || 'Specialist ready and active.',
            icon: sp.icon || '🤖',
          })), errPrefix || '');
        })
        .catch(e => {
          finish([], (errPrefix ? errPrefix + ' ' : '') +
            (api.fmtErr(e?.response?.data?.detail) || e?.message || 'Something went wrong.'));
        });

    // Hard safety net: if neither provisioning nor listing settle within
    // 30s (e.g. the backend onboarding lock is held by a stuck scan), stop
    // showing the spinner and surface a recoverable message.
    const watchdog = setTimeout(() => {
      finish([], 'Provisioning is taking longer than expected. Your specialists may still ' +
        'be created in the background — check the Agent Roster shortly.');
    }, 30000);

    // Trigger specialist provisioning from scans already saved, then list
    // results. Bound the provisioning request itself so a hung backend call
    // cannot block the listing fallback.
    api.startOnboarding(companyId, {
      skip_website_scan: true,
      skip_repo_scan: true,
      auto_provision_specialists: true,
    }, { timeout: 25000 })
      .then(() => loadSpecialists())
      .catch((e) => {
        const prefix = 'Specialist provisioning reported an issue: ' +
          (e?.response?.data?.detail?.message || e?.message || 'Unknown error. Check that your LLM providers are reachable.');
        // Still try to list — provisioning may have partially succeeded.
        loadSpecialists(prefix);
      })
      .finally(() => clearTimeout(watchdog));
  }, [companyId]);

  return (
    <div style={{ animation:'fadeSlideUp 0.35s ease-out' }}>
      <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:12 }}>
        <div style={{ width:40, height:40, borderRadius:14, background:'rgba(70,217,164,0.15)', border:'1px solid rgba(70,217,164,0.25)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:20 }}>✓</div>
        <div>
          <h2 style={{ fontSize:22, fontWeight:800, color:'#fff', letterSpacing:'-0.04em' }}>Company provisioned</h2>
          <p style={{ fontSize:13, color:'#46d9a4' }}>
            {companyName || 'Your company'} · {specialists === null ? 'Loading specialists...' : `${specialists.length} specialist${specialists.length === 1 ? '' : 's'} ready`} · monitoring starts now
          </p>
        </div>
      </div>
      <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.6, marginBottom:20, maxWidth:440 }}>
        {specialists !== null && specialists.length > 0
          ? `${specialists.length} specialists have been created and wired to your systems. They appear in the Agent Roster and will start monitoring immediately.`
          : 'Your company is set up. Specialists will appear in the Agent Roster once provisioned.'}
      </p>
      {specsError && (
        <div style={{ marginBottom:14, padding:'10px 14px', borderRadius:12, background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.22)', fontSize:12, color:'#ff9aa6' }}>
          Could not load specialists: {specsError}
        </div>
      )}
      {specialists === null && (
        <div style={{ fontSize:12, fontFamily:'var(--font-mono)', color:'var(--text-muted)', marginBottom:18 }}>Loading specialists...</div>
      )}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(200px,1fr))', gap:8, marginBottom:22 }}>
        {(specialists || []).map((sp,i)=>(
          <div key={sp.name} style={{ padding:'12px 14px', borderRadius:14, background:'rgba(70,217,164,0.04)', border:'1px solid rgba(70,217,164,0.12)', animation:`fadeSlideUp 0.4s ease-out ${i*0.07}s both` }}>
            <div style={{ fontSize:18, marginBottom:5 }}>{sp.icon}</div>
            <div style={{ fontSize:12, fontWeight:700, color:'#fff', marginBottom:2 }}>{sp.name}</div>
            <div style={{ fontSize:11, color:'var(--text-muted)', lineHeight:1.5 }}>{sp.desc}</div>
          </div>
        ))}
      </div>
      <div style={{ display:'flex', gap:10 }}>
        <button onClick={onBack} style={{ padding:'12px 22px', borderRadius:999, background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.12)', color:'var(--text-secondary)', fontSize:14, fontWeight:700, cursor:'pointer' }}>← Back</button>
        <button onClick={onRestart} style={{ padding:'12px 22px', borderRadius:999, background:'rgba(255,189,102,0.08)', border:'1px solid rgba(255,189,102,0.22)', color:'#ffbd66', fontSize:13, fontWeight:700, cursor:'pointer' }}>↺ Restart</button>
        <button onClick={onFinish} style={{ flex:1, display:'inline-flex', alignItems:'center', justifyContent:'center', gap:8, padding:'13px 28px', borderRadius:999, background:'linear-gradient(135deg,#6CB0FF,#4F93FF)', color:'#06111f', fontSize:14, fontWeight:800, border:'none', cursor:'pointer', boxShadow:'0 8px 24px rgba(93,162,255,0.25)' }}>
          → Go to Company Graph
        </button>
      </div>
    </div>
  );
}

// ── Main OnboardingScreen ──────────────────────────────────────────────────────
function OnboardingScreen({ onComplete, isAdmin }) {
  const [step,     setStep]     = React.useState('url');
  const [siteType, setSiteType] = React.useState('generic');
  const [systems,  setSystems]  = React.useState([]);
  const [companyId, setCompanyId] = React.useState(null);
  const [companyName, setCompanyName] = React.useState('');
  const [checkingProgress, setCheckingProgress] = React.useState(true);
  // Non-admins may still onboard once an admin turns the global onboarding
  // gate off (or allow-lists this user specifically) — see
  // activation_api.is_user_onboarding_allowed(). Admins always have access
  // and skip this check. Defaults to blocked (not `isAdmin`) so a slow/failed
  // fetch doesn't briefly show the wizard to someone who isn't allowed in.
  const [checkingAccess, setCheckingAccess] = React.useState(!isAdmin);
  const [onboardingAllowed, setOnboardingAllowed] = React.useState(isAdmin);

  React.useEffect(() => {
    if (isAdmin) { setCheckingAccess(false); return undefined; }
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.getSetupState();
        if (!cancelled) setOnboardingAllowed(Boolean(data?._activation?.onboarding_allowed));
      } catch {
        if (!cancelled) setOnboardingAllowed(false);
      } finally {
        if (!cancelled) setCheckingAccess(false);
      }
    })();
    return () => { cancelled = true; };
  }, [isAdmin]);

  // On mount, check if there is already an in-progress onboarding to resume
  React.useEffect(() => {
    const storedId = (() => { try { return localStorage.getItem(COMPANY_ID_KEY); } catch { return null; } })();
    if (!storedId) { setCheckingProgress(false); return; }

    (async () => {
      try {
        const { data } = await api.getOnboardingProgress(storedId);
        const status = data.status;
        if (status === 'completed') {
          // Already done — show the done step but allow restart via breadcrumb or restart button
          setCompanyId(storedId);
          setStep('done');
        } else if (status === 'in_progress' || status === 'paused') {
          // Resume from current progress — skip URL step since company exists
          setCompanyId(storedId);
          try {
            const name = localStorage.getItem('v5_company_name');
            if (name) setCompanyName(name);
          } catch {}
          // Jump to later step based on completed progress
          const completed = data.completed_steps || 0;
          if (completed >= 4) setStep('questions');
          else if (completed >= 3) setStep('details');
          else if (completed >= 2) setStep('systems');
          else setStep('url');
        }
      } catch {
        // Could not fetch progress — proceed normally
      }
      setCheckingProgress(false);
    })();
  }, []);

  if (!isAdmin && checkingAccess) return (
    <div style={{ padding:'24px 16px 48px', maxWidth:640, margin:'0 auto', textAlign:'center' }}>
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:8 }}>Company Onboarding · LLM Relay V5.0</div>
      <div style={{ padding:'40px 0', color:'var(--text-muted)', fontSize:14 }}>Checking onboarding access...</div>
    </div>
  );

  if (!isAdmin && !onboardingAllowed) return (
    <div style={{ padding:'24px 16px 48px', maxWidth:580, margin:'0 auto' }}>
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:8 }}>Company Onboarding · LLM Relay V5.0</div>
      <NonAdminGate/>
    </div>
  );

  if (checkingProgress) return (
    <div style={{ padding:'24px 16px 48px', maxWidth:640, margin:'0 auto', textAlign:'center' }}>
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:8 }}>Company Onboarding · LLM Relay V5.0</div>
      <div style={{ padding:'40px 0', color:'var(--text-muted)', fontSize:14 }}>Checking onboarding status...</div>
    </div>
  );

  const handleCompanyCreated = (id, name, domain) => {
    setCompanyId(id);
    setCompanyName(name || domain);
    // Persist so the Company screen can load this company's graph after onboarding.
    try {
      if (id) {
        localStorage.setItem(COMPANY_ID_KEY, id);
        localStorage.setItem('v5_company_domain', domain || '');
        localStorage.setItem('v5_company_name', name || '');
      }
    } catch { /* storage unavailable */ }
  };

  const handleRestartOnboarding = () => {
    // Clear all onboarding state and start fresh
    setStep('url');
    setSystems([]);
    setSiteType('generic');
    setCompanyId(null);
    setCompanyName('');
    try {
      localStorage.removeItem(COMPANY_ID_KEY);
      localStorage.removeItem('v5_company_domain');
      localStorage.removeItem('v5_company_name');
      localStorage.removeItem(ONBOARDING_ANSWERS_KEY);
      localStorage.removeItem('v5_onboarding_details');
    } catch { /* storage unavailable */ }
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
      <StepIndicator current={step} onStepClick={(s) => {
        // When jumping back to URL step via breadcrumb, reset company state
        // so the old company doesn't linger and cause duplicate creation.
        if (s === 'url' && step !== 'url') {
          setCompanyId(null);
          setCompanyName('');
          setSystems([]);
          setSiteType('generic');
        }
        setStep(s);
      }}/>
      {step==='url'       && <DiscoveryStep onNext={handleScanDone} onCompanyCreated={handleCompanyCreated}/>}
      {step==='systems'   && <SystemsStep onNext={handleSystemsConfirmed} onBack={()=>setStep('url')} detectedSystems={systems}/>}
      {step==='details'   && <DetailsStep onNext={()=>setStep('questions')} onBack={()=>setStep('systems')} companyId={companyId}/>}
      {step==='questions' && <QuestionsStep onNext={()=>setStep('done')} onBack={()=>setStep('details')} siteType={siteType}/>}
      {step==='done'      && <DoneStep onFinish={onComplete} onRestart={handleRestartOnboarding} onBack={()=>setStep('questions')} companyId={companyId} companyName={companyName}/>}
    </div>
  );
}

export { OnboardingScreen };
export default OnboardingScreen;
