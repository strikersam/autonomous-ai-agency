/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import * as api from '../../api';


// skills.jsx — Agentic Skills & Workflow Builder
// Commerce-focused skills with plain-English explanations

// ── Concept explainer component ───────────────────────────────────────────────
function Explain({ term, children }) {
  const [show, setShow] = React.useState(false);
  return (
    <span style={{ position:'relative', display:'inline-flex', alignItems:'center', gap:4 }}>
      {term}
      <button onClick={()=>setShow(o=>!o)} style={{
        width:15, height:15, borderRadius:'50%', fontSize:9, fontWeight:700,
        background:show?'rgba(93,162,255,0.20)':'rgba(255,255,255,0.10)',
        border:'1px solid rgba(255,255,255,0.20)', color:'var(--text-muted)',
        cursor:'pointer', display:'inline-flex', alignItems:'center', justifyContent:'center',
        transition:'all 0.15s', flexShrink:0,
      }}>?</button>
      {show && (
        <div style={{
          position:'absolute', bottom:'calc(100% + 6px)', left:0, zIndex:99,
          background:'rgba(12,15,20,0.98)', border:'1px solid rgba(93,162,255,0.25)',
          borderRadius:12, padding:'10px 12px', minWidth:220, maxWidth:'min(280px, calc(100vw - 24px))',
          fontSize:12, color:'var(--text-secondary)', lineHeight:1.6,
          boxShadow:'0 12px 32px rgba(0,0,0,0.55)', animation:'fadeSlideUp 0.15s ease-out',
        }}>
          <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--accent)', marginBottom:4, letterSpacing:'0.10em', textTransform:'uppercase' }}>{term}</div>
          {children}
          <div style={{ position:'absolute', bottom:-5, left:14, width:8, height:8, background:'rgba(12,15,20,0.98)', border:'1px solid rgba(93,162,255,0.25)', borderTop:'none', borderLeft:'none', transform:'rotate(45deg)' }}/>
        </div>
      )}
    </span>
  );
}

// ── Pre-built commerce skills ─────────────────────────────────────────────────
const COMMERCE_SKILLS = [
  {
    id:'abandoned-cart', category:'Revenue Recovery', icon:'🛒', color:'#ff6b7d',
    name:'Abandoned Cart Recovery',
    tagline:'Automatically win back customers who left without buying',
    what:'When a shopper adds items to their cart but doesn\'t complete checkout, this skill notices and sends a personalised reminder — with the right timing, tone, and offer.',
    how:'Checks cart data from Shopify every 30 min → scores intent to return → generates a personalised email via Klaviyo → optionally adds a discount if basket value exceeds threshold.',
    agent:'Commerce Agent', trigger:'Shopify cart abandoned > 1 hour', output:'Klaviyo email + optional discount code',
    impact:'Average 15% cart recovery rate', effort:'low', enabled:true,
    config:{ waitHours:1, discountThreshold:50, discountPct:10 },
  },
  {
    id:'dynamic-pricing', category:'Pricing', icon:'💰', color:'#ffbd66',
    name:'Dynamic Pricing Monitor',
    tagline:'Keep your prices competitive without checking manually every day',
    what:'Watches competitor prices for your key products and suggests (or automatically applies) price changes to stay competitive while protecting margin.',
    how:'Scrapes competitor URLs daily → compares to your Shopify prices → flags when you\'re more than 10% above market → suggests a repriced range and submits for approval.',
    agent:'Commerce Agent', trigger:'Daily at 06:00', output:'Pricing report + optional Shopify price update',
    impact:'Keeps you within 5% of market', effort:'medium', enabled:false,
    config:{ threshold:10, autoApply:false },
  },
  {
    id:'seo-content', category:'SEO & Content', icon:'📝', color:'#5da2ff',
    name:'SEO Content Generator',
    tagline:'Publish SEO-optimised product descriptions automatically',
    what:'Takes your product catalogue and generates or improves product descriptions, meta titles, and alt text so your products rank higher in Google.',
    how:'Reads Shopify catalogue → checks current SEO scores via GA4 → generates improved copy for low-performing products → creates a Contentful draft for review.',
    agent:'Content Agent', trigger:'Weekly Monday + on new product', output:'Contentful draft pages for review',
    impact:'Up to 40% organic traffic lift on optimised pages', effort:'low', enabled:true,
    config:{ autoPublish:false, minWordCount:150 },
  },
  {
    id:'stock-alert', category:'Inventory', icon:'📦', color:'#46d9a4',
    name:'Low Stock Alert & Reorder',
    tagline:'Never run out of your best sellers',
    what:'Watches your inventory levels and alerts you (or auto-drafts a purchase order) when a product is running low, based on your average daily sales velocity.',
    how:'Polls Shopify inventory daily → calculates days-of-stock remaining → sends Slack/email alert when below threshold → optionally creates a draft purchase order.',
    agent:'Commerce Agent', trigger:'Daily at 07:00', output:'Slack alert + optional draft PO',
    impact:'Reduces stockouts by ~80%', effort:'low', enabled:true,
    config:{ daysThreshold:14, autoCreatePO:false },
  },
  {
    id:'review-response', category:'Customer Experience', icon:'⭐', color:'#c4b5fd',
    name:'Review Response Agent',
    tagline:'Respond to every review — especially negative ones — before they hurt your brand',
    what:'Monitors new customer reviews and drafts personalised responses. Escalates 1–2 star reviews immediately for human review.',
    how:'Polls Shopify/Gorgias for new reviews daily → classifies sentiment → drafts a response using your brand voice → routes to queue for approval before posting.',
    agent:'Support Agent', trigger:'Daily + on new review', output:'Draft responses in Gorgias queue',
    impact:'4.2x faster response time', effort:'low', enabled:false,
    config:{ escalateBelow:3, autoPost:false },
  },
  {
    id:'campaign-perf', category:'Marketing', icon:'📊', color:'#7c9dff',
    name:'Campaign Performance Monitor',
    tagline:'Understand what\'s working before you waste budget',
    what:'Pulls your GA4 and campaign data daily, identifies which campaigns, channels, and products are driving revenue, and flags anything underperforming.',
    how:'Reads GA4 + Klaviyo data → compares to previous period → generates a plain-English performance summary → highlights quick wins and budget-wasting campaigns.',
    agent:'Analytics Agent', trigger:'Daily at 08:00 + on request', output:'Slack/email summary report',
    impact:'Saves 3–5 hrs/week on manual reporting', effort:'low', enabled:true,
    config:{ compareWeeks:4, threshold:20 },
  },
  {
    id:'flash-sale', category:'Revenue Recovery', icon:'⚡', color:'#ff6b7d',
    name:'Flash Sale Orchestrator',
    tagline:'Plan and execute time-limited offers without the manual scramble',
    what:'Coordinates a flash sale end-to-end: sets up discount codes, sends the campaign email, monitors performance in real time, and cleans up automatically when it ends.',
    how:'You set the products, discount, and time window → agent sets up Shopify discounts → queues Klaviyo email → monitors hourly GMV → sends final report → removes codes at end.',
    agent:'Commerce Agent', trigger:'Manual / scheduled', output:'Full sale execution + performance report',
    impact:'Average 3× normal daily revenue', effort:'medium', enabled:false,
    config:{ requireApproval:true },
  },
  {
    id:'personalisation', category:'Conversion', icon:'🎯', color:'#46d9a4',
    name:'Personalised Recommendation Engine',
    tagline:'Show each customer the products they\'re most likely to buy',
    what:'Analyses purchase history and browsing behaviour to recommend relevant products in emails, on your homepage, and in post-purchase flows.',
    how:'Reads Shopify order history → clusters customers by behaviour → generates recommendation lists per segment → feeds into Klaviyo flows and Contentful homepage slots.',
    agent:'Commerce Agent + Content Agent', trigger:'Weekly refresh + real-time signals', output:'Recommendation sets per segment',
    impact:'18–35% higher AOV', effort:'high', enabled:false,
    config:{ segments:5, requireApproval:false },
  },
];

const WORKFLOW_STEPS = [
  { id:'trigger',  label:'Trigger',  icon:'⚡', desc:'What starts this workflow', color:'#ffbd66' },
  { id:'check',    label:'Check',    icon:'◎',  desc:'Condition that must be true', color:'#5da2ff' },
  { id:'generate', label:'Generate', icon:'◈',  desc:'AI creates content or analysis', color:'#c4b5fd' },
  { id:'approve',  label:'Review',   icon:'◉',  desc:'Human checks before action', color:'#ff9d66' },
  { id:'act',      label:'Act',      icon:'⊕',  desc:'Send, post, update, or notify', color:'#46d9a4' },
];

const CATEGORY_COLORS = {
  'Revenue Recovery': '#ff6b7d',
  'Pricing': '#ffbd66',
  'SEO & Content': '#5da2ff',
  'Inventory': '#46d9a4',
  'Customer Experience': '#c4b5fd',
  'Marketing': '#7c9dff',
  'Conversion': '#46d9a4',
};

const effortLabel = { low:'Easy to set up', medium:'Some config needed', high:'Requires setup time' };
const effortColor = { low:'#46d9a4', medium:'#ffbd66', high:'#ff6b7d' };

function SkillCard({ skill, onToggle, onConfigure }) {
  const [expanded, setExpanded] = React.useState(false);
  const catColor = CATEGORY_COLORS[skill.category] || 'var(--text-muted)';

  return (
    <div style={{
      borderRadius:18, border:`1px solid ${skill.enabled ? `${skill.color}28` : 'rgba(255,255,255,0.08)'}`,
      background: skill.enabled ? `${skill.color}05` : 'rgba(255,255,255,0.025)',
      transition:'all 0.2s ease', overflow:'hidden',
    }}>
      <div style={{ padding:'14px 16px' }}>
        {/* Header */}
        <div style={{ display:'flex', alignItems:'flex-start', gap:10, marginBottom:10 }}>
          <div style={{ width:38, height:38, borderRadius:12, flexShrink:0, background:`${skill.color}15`, border:`1px solid ${skill.color}28`, display:'flex', alignItems:'center', justifyContent:'center', fontSize:18 }}>{skill.icon}</div>
          <div style={{ flex:1, minWidth:0 }}>
            <div style={{ display:'flex', alignItems:'center', gap:7, flexWrap:'wrap', marginBottom:2 }}>
              <span style={{ fontSize:13, fontWeight:800, color:'#fff', letterSpacing:'-0.02em' }}>{skill.name}</span>
              <span style={{ fontSize:9, fontFamily:'var(--font-mono)', letterSpacing:'0.10em', textTransform:'uppercase', padding:'2px 7px', borderRadius:999, color:catColor, background:`${catColor}12`, border:`1px solid ${catColor}22` }}>{skill.category}</span>
            </div>
            <div style={{ fontSize:12, color:'var(--text-tertiary)', lineHeight:1.4, fontStyle:'italic' }}>{skill.tagline}</div>
          </div>
          {/* Toggle */}
          <button onClick={()=>onToggle(skill.id)} style={{ width:40, height:22, borderRadius:999, padding:3, cursor:'pointer', background:skill.enabled?skill.color:'rgba(255,255,255,0.10)', border:`1px solid ${skill.enabled?skill.color+'80':'rgba(255,255,255,0.15)'}`, transition:'all 0.2s', display:'flex', alignItems:'center', justifyContent:skill.enabled?'flex-end':'flex-start', flexShrink:0 }}>
            <div style={{ width:16, height:16, borderRadius:'50%', background:'#fff', boxShadow:'0 1px 4px rgba(0,0,0,0.3)' }}/>
          </button>
        </div>

        {/* What it does — plain English */}
        <div style={{ fontSize:13, color:'var(--text-secondary)', lineHeight:1.65, marginBottom:10 }}>{skill.what}</div>

        {/* Meta row */}
        <div style={{ display:'flex', gap:8, flexWrap:'wrap', alignItems:'center', marginBottom:10 }}>
          <div style={{ display:'flex', alignItems:'center', gap:4, padding:'3px 9px', borderRadius:999, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.09)' }}>
            <span style={{ fontSize:10 }}>🤖</span>
            <span style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{skill.agent}</span>
          </div>
          <div style={{ display:'flex', alignItems:'center', gap:4, padding:'3px 9px', borderRadius:999, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.09)' }}>
            <span style={{ fontSize:10 }}>⚡</span>
            <span style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{skill.trigger}</span>
          </div>
          <div style={{ display:'flex', alignItems:'center', gap:4, padding:'3px 9px', borderRadius:999, background:`${effortColor[skill.effort]}10`, border:`1px solid ${effortColor[skill.effort]}22` }}>
            <span style={{ fontSize:11, color:effortColor[skill.effort] }}>{effortLabel[skill.effort]}</span>
          </div>
        </div>

        {/* Impact */}
        <div style={{ padding:'8px 12px', borderRadius:10, background:'rgba(70,217,164,0.06)', border:'1px solid rgba(70,217,164,0.14)', marginBottom:10 }}>
          <span style={{ fontSize:11, color:'#46d9a4' }}>✦ Expected impact: </span>
          <span style={{ fontSize:12, color:'var(--text-secondary)' }}>{skill.impact}</span>
        </div>

        {/* Expand button */}
        <button onClick={()=>setExpanded(o=>!o)} style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', background:'none', border:'none', cursor:'pointer', display:'flex', alignItems:'center', gap:4 }}>
          {expanded ? '▲ Less detail' : '▼ How it works'}
        </button>
      </div>

      {expanded && (
        <div style={{ padding:'0 16px 14px', animation:'fadeSlideUp 0.2s ease-out' }}>
          {/* Step by step */}
          <div style={{ padding:'12px 14px', borderRadius:12, background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.08)', marginBottom:10 }}>
            <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.10em', textTransform:'uppercase', marginBottom:8 }}>Step-by-step</div>
            <div style={{ fontSize:12, color:'var(--text-secondary)', lineHeight:1.8 }}>
              {skill.how.split(' → ').map((step, i, arr) => (
                <div key={i} style={{ display:'flex', gap:8, alignItems:'flex-start' }}>
                  <span style={{ fontSize:11, color:'var(--accent)', width:18, flexShrink:0, paddingTop:1 }}>{i+1}.</span>
                  <span style={{ flex:1 }}>{step}{i < arr.length-1 ? '' : ''}</span>
                </div>
              ))}
            </div>
          </div>
          <div style={{ display:'flex', gap:7 }}>
            <button style={{ flex:1, padding:'8px', borderRadius:10, fontSize:12, fontWeight:700, cursor:'pointer', background:`${skill.color}15`, border:`1px solid ${skill.color}28`, color:skill.color, transition:'all 0.15s' }}>⚙ Configure</button>
            <button style={{ padding:'8px 14px', borderRadius:10, fontSize:12, cursor:'pointer', background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-muted)' }}>View runs</button>
          </div>
        </div>
      )}
    </div>
  );
}

function WorkflowVisual() {
  const [active, setActive] = React.useState('generate');
  return (
    <div style={{ padding:'14px', borderRadius:16, background:'rgba(255,255,255,0.025)', border:'1px solid rgba(255,255,255,0.09)' }}>
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.12em', textTransform:'uppercase', marginBottom:12 }}>How every skill works — the 5-step pattern</div>
      <div style={{ display:'flex', alignItems:'center', gap:0, overflowX:'auto' }} className="scrollbar-hide">
        {WORKFLOW_STEPS.map((step, i) => (
          <React.Fragment key={step.id}>
            <button onClick={()=>setActive(step.id)} style={{
              display:'flex', flexDirection:'column', alignItems:'center', gap:5,
              padding:'10px 14px', borderRadius:12, cursor:'pointer', flexShrink:0,
              background:active===step.id?`${step.color}15`:'transparent',
              border:`1px solid ${active===step.id?`${step.color}35`:'transparent'}`,
              transition:'all 0.2s',
            }}>
              <div style={{ width:36, height:36, borderRadius:11, background:`${step.color}18`, border:`1px solid ${step.color}30`, display:'flex', alignItems:'center', justifyContent:'center', fontSize:17 }}>{step.icon}</div>
              <span style={{ fontSize:12, fontWeight:700, color:active===step.id?'#fff':'var(--text-muted)' }}>{step.label}</span>
              <span style={{ fontSize:10, color:'var(--text-muted)', textAlign:'center', maxWidth:80, lineHeight:1.4 }}>{step.desc}</span>
            </button>
            {i < WORKFLOW_STEPS.length-1 && (
              <div style={{ width:24, height:2, background:'rgba(255,255,255,0.10)', flexShrink:0, margin:'0 -2px', marginBottom:30 }}/>
            )}
          </React.Fragment>
        ))}
      </div>
      {active && (
        <div style={{ marginTop:10, padding:'10px 12px', borderRadius:10, background:'rgba(93,162,255,0.06)', border:'1px solid rgba(93,162,255,0.14)', fontSize:12, color:'var(--text-secondary)', animation:'fadeSlideUp 0.2s ease-out' }}>
          {active==='trigger' && 'A skill starts automatically — on a schedule, on a user action (like placing an order), or when a threshold is crossed (like stock going below 10 units).'}
          {active==='check' && 'Before doing anything, the agent checks a condition: "Is this cart worth recovering?" or "Has the price dropped by more than 10%?" This prevents noise and false alarms.'}
          {active==='generate' && 'The AI creates something: a personalised email, a repriced product list, a performance report, or a purchase order. Everything is human-readable before it goes anywhere.'}
          {active==='approve' && 'For anything that touches customers or money, the agent pauses here and asks a human to confirm. You can set certain skills to skip this step for low-risk actions.'}
          {active==='act' && 'The final step: send the email via Klaviyo, update Shopify prices, post the Contentful draft, or fire the Slack notification. The result is recorded in your Knowledge Base.'}
        </div>
      )}
    </div>
  );
}

function SkillsScreen() {
  const [skills,      setSkills]      = React.useState(COMMERCE_SKILLS);
  const [liveSkills,  setLiveSkills]  = React.useState(null);   // null = loading
  const [remoteSkills, setRemoteSkills] = React.useState(null);  // null = not loaded
  const [recommended, setRecommended] = React.useState([]);
  const [techStack,   setTechStack]   = React.useState([]);
  const [wfTypes,     setWfTypes]     = React.useState([]);
  const [refreshing,  setRefreshing]  = React.useState(false);
  const [filter,      setFilter]      = React.useState('all');
  const [search,      setSearch]      = React.useState('');
  const [tab,         setTab]         = React.useState('catalogue'); // 'catalogue' | 'recommended' | 'registry'
  const userPickedTab = React.useRef(false); // becomes true once the user clicks a tab
  const [companyId,   setCompanyId]   = React.useState(null);

  // Resolve current company ID from the companies list.
  // listCompanies() is NOT a single-company API — admins get every company and
  // a normal user can own several — so only auto-select when there is exactly
  // one company. With multiple, leave it unset (the user picks) rather than
  // silently loading recommendations for an arbitrary tenant.
  React.useEffect(() => {
    const resolve = async () => {
      try {
        const { data } = await api.listCompanies();
        const companies = data.companies || [];
        if (companies.length === 1) {
          setCompanyId(companies[0].id);
        }
      } catch { /* silent */ }
    };
    resolve();
  }, []);

  // Load auto-recommendations and registry skills from company skill APIs
  React.useEffect(() => {
    const load = async () => {
      // Load recommended skills from company skill API
      try {
        const { data } = companyId
          ? await api.autoRecommendCompanySkills(companyId)
          : await api.autoRecommendCompanySkills();
        const recs = data.recommendations || [];
        setRecommended(recs);
        setTechStack(data.tech_stack || []);
        if (data.workflow_types) setWfTypes(data.workflow_types);
        // Domain-aware default: if we have real recommendations and the user hasn't
        // manually chosen a tab, show them instead of the commerce demo catalogue.
        if (!userPickedTab.current && recs.length > 0) setTab('recommended');
      } catch { /* non-critical */ }
      // Load registry skills from company skill API
      try {
        const { data } = await api.listCompanySkills();
        if ((data.skills || []).length > 0) setLiveSkills(data.skills);
      } catch { /* non-critical */ }
      // Load remote registry skills from GitHub repos (BUG-28)
      try {
        const { data } = await api.discoverRemoteSkills();
        if ((data.skills || []).length > 0) setRemoteSkills(data.skills);
      } catch { /* non-critical */ }
    };
    load();
  }, [companyId]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const [{ data: companyData }, { data: remoteData }] = await Promise.all([
        api.listCompanySkills(),
        api.discoverRemoteSkills().catch(() => ({ data: { skills: [] } })),
      ]);
      setLiveSkills(companyData.skills || []);
      if ((remoteData.skills || []).length > 0) setRemoteSkills(remoteData.skills);
      const recPromise = companyId
        ? api.autoRecommendCompanySkills(companyId)
        : api.autoRecommendCompanySkills();
      const { data: rec } = await recPromise;
      setRecommended(rec.recommendations || []);
    } catch { /* ignore */ }
    finally { setRefreshing(false); }
  };

  // Persist toggle to localStorage (backend skills are read-only registry entries)
  const [enabled, setEnabled] = React.useState(() => {
    try { return JSON.parse(localStorage.getItem('skills_enabled') || '{}'); } catch { return {}; }
  });
  const toggle = (id) => {
    const next = { ...enabled, [id]: !enabled[id] };
    setEnabled(next);
    // BUG-06: wrap localStorage.setItem in try/catch so a blocked or
    // quota-exceeded storage doesn't crash the React component tree.
    try { localStorage.setItem('skills_enabled', JSON.stringify(next)); } catch {}
  };

  const effectiveSkills = skills.map(s => ({ ...s, enabled: enabled[s.id] !== undefined ? enabled[s.id] : s.enabled }));
  const categories = ['all', ...new Set(COMMERCE_SKILLS.map(s => s.category))];
  const filtered = effectiveSkills.filter(s => {
    const matchesCat    = filter==='all' || s.category===filter;
    const matchesSearch = !search || s.name.toLowerCase().includes(search.toLowerCase()) || s.tagline.toLowerCase().includes(search.toLowerCase());
    return matchesCat && matchesSearch;
  });

  const enabledCount = effectiveSkills.filter(s=>s.enabled).length;

  return (
    <div style={{ padding:'20px 16px 48px', maxWidth:960, margin:'0 auto' }}>
      {/* Header with plain-language intro */}
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:6 }}>Agentic Commerce · Preview</div>
      <div style={{ display:'flex', alignItems:'flex-end', justifyContent:'space-between', flexWrap:'wrap', gap:10, marginBottom:14 }}>
        <div>
          <h1 style={{ fontSize:26, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', lineHeight:1.1, marginBottom:6 }}>
            <Explain term="Skills & Workflows">A "skill" is a pre-built task that an AI agent runs automatically — like sending a cart recovery email or monitoring competitor prices. You turn them on and the agent does the rest.</Explain>
          </h1>
          <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.6, maxWidth:560 }}>
            These are ready-made automations for your Shopify store. Each one is a complete workflow — from the trigger that starts it, to the AI that handles the work, to the action it takes. <strong style={{ color:'var(--text-secondary)' }}>No code needed.</strong> Turn on what you need, leave off what you don't.
          </p>
        </div>
        <div style={{ padding:'10px 16px', borderRadius:14, background:'rgba(70,217,164,0.06)', border:'1px solid rgba(70,217,164,0.15)', textAlign:'center' }}>
          <div style={{ fontSize:22, fontWeight:800, color:'#46d9a4', letterSpacing:'-0.03em' }}>{enabledCount}</div>
          <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.10em' }}>Toggled on</div>
        </div>
      </div>

      {/* Honest preview notice — templates are illustrative; registry comes from the backend */}
      {tab === 'catalogue' && (
        <div style={{ padding:'10px 14px', borderRadius:12, background:'rgba(93,162,255,0.06)', border:'1px solid rgba(93,162,255,0.18)', marginBottom:16, fontSize:12, color:'var(--text-secondary)', lineHeight:1.5 }}>
          <strong style={{ color:'var(--accent)' }}>Catalogue.</strong> The commerce skill templates are <strong>illustrative examples</strong> — toggling is session-only. The <strong>Recommended</strong> and <strong>Registry</strong> tabs call live backend APIs and reflect real specialist skill bindings.
        </div>
      )}

      {/* Tab switcher — without this the Recommended/Registry (live, domain-aware)
          skills were unreachable and users only ever saw the commerce demo catalogue. */}
      <div style={{ display:'flex', gap:8, marginBottom:16, flexWrap:'wrap' }}>
        {[
          { id:'recommended', label:'Recommended' },
          { id:'registry', label:'Registry' },
          { id:'catalogue', label:'Catalogue (demo)' },
        ].map(t => (
          <button key={t.id} onClick={()=>{ userPickedTab.current = true; setTab(t.id); }} style={{
            padding:'6px 14px', borderRadius:999, fontSize:12, fontWeight:600, cursor:'pointer',
            fontFamily:'var(--font-mono)', letterSpacing:'0.04em',
            background: tab===t.id ? 'rgba(93,162,255,0.14)' : 'rgba(255,255,255,0.04)',
            border:`1px solid ${tab===t.id ? 'rgba(93,162,255,0.40)' : 'rgba(255,255,255,0.12)'}`,
            color: tab===t.id ? '#fff' : 'var(--text-secondary)', transition:'all 0.15s',
          }}>{t.label}</button>
        ))}
      </div>

      {/* How it works visual */}
      <WorkflowVisual/>

      {/* Recommended tab */}
      {tab === 'recommended' && (
        <div style={{ marginBottom:16 }}>
          {recommended.length === 0 ? (
            <div style={{ padding:'32px', textAlign:'center', color:'var(--text-muted)', fontSize:13 }}>
              No scan data yet — run a website or repo scan in Company Graph to get personalised skill recommendations.
            </div>
          ) : (
            <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
              {recommended.map(skill => (
                <div key={skill.skill_id} style={{ padding:'14px 16px', borderRadius:16, background:'rgba(93,162,255,0.04)', border:'1px solid rgba(93,162,255,0.15)' }}>
                  <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', gap:10 }}>
                    <div style={{ flex:1 }}>
                      <div style={{ fontSize:14, fontWeight:700, color:'#fff', marginBottom:3 }}>{skill.name}</div>
                      <div style={{ fontSize:12, color:'var(--text-secondary)', lineHeight:1.5, marginBottom:5 }}>{skill.description}</div>
                      <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
                        {(skill.reasons || []).map(r => (
                          <span key={r} style={{ fontSize:10, padding:'2px 7px', borderRadius:999, background:'rgba(70,217,164,0.08)', border:'1px solid rgba(70,217,164,0.18)', color:'#46d9a4', fontFamily:'var(--font-mono)' }}>{r}</span>
                        ))}
                        <span style={{ fontSize:10, padding:'2px 7px', borderRadius:999, background:'rgba(93,162,255,0.08)', border:'1px solid rgba(93,162,255,0.18)', color:'var(--accent)', fontFamily:'var(--font-mono)' }}>score: {skill.score}</span>
                      </div>
                    </div>
                    {skill.url && (
                      <a href={skill.url} target="_blank" rel="noreferrer" style={{ padding:'6px 12px', borderRadius:10, background:'rgba(93,162,255,0.10)', border:'1px solid rgba(93,162,255,0.22)', color:'var(--accent)', fontSize:11, textDecoration:'none', whiteSpace:'nowrap' }}>View →</a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Registry tab */}
      {tab === 'registry' && (
        <div style={{ marginBottom:16 }}>
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:10 }}>
            <span style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.10em', textTransform:'uppercase' }}>
              {liveSkills ? `${liveSkills.length} bound · ` : ''}{remoteSkills ? `${remoteSkills.length} remote` : ''}
            </span>
            <button onClick={handleRefresh} disabled={refreshing} style={{
              padding:'4px 12px', borderRadius:999, fontSize:11, fontWeight:600, cursor:'pointer',
              background:'rgba(93,162,255,0.10)', border:'1px solid rgba(93,162,255,0.22)',
              color:'var(--accent)', fontFamily:'var(--font-mono)', letterSpacing:'0.04em',
            }}>{refreshing ? 'Refreshing…' : 'Refresh registry'}</button>
          </div>
          {!liveSkills && !remoteSkills ? (
            <div style={{ padding:'32px', textAlign:'center', color:'var(--text-muted)', fontSize:13 }}>Click "Refresh registry" to fetch skills from bound specialists and GitHub registries.</div>
          ) : (
            <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
              {(liveSkills || []).map(skill => (
                <div key={skill.skill_id} style={{ padding:'12px 14px', borderRadius:14, background:'rgba(255,255,255,0.025)', border:'1px solid rgba(255,255,255,0.08)' }}>
                  <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:8 }}>
                    <div style={{ flex:1 }}>
                      <div style={{ fontSize:13, fontWeight:700, color:'#fff', marginBottom:2 }}>{skill.name}</div>
                      <div style={{ fontSize:11, color:'var(--text-tertiary)', lineHeight:1.5, marginBottom:4 }}>{skill.description}</div>
                      <div style={{ display:'flex', gap:5, flexWrap:'wrap' }}>
                        <span style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'1px 6px', borderRadius:4, background:'rgba(255,255,255,0.05)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.09em' }}>{skill.source || 'bound'}</span>
                        {(skill.tech_relevance || []).slice(0,3).map(t => (
                          <span key={t} style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'1px 6px', borderRadius:4, background:'rgba(93,162,255,0.06)', color:'var(--accent)', border:'1px solid rgba(93,162,255,0.15)' }}>{t}</span>
                        ))}
                        {skill.calls_last_24h != null && (
                          <span style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'1px 6px', borderRadius:4, background:'rgba(70,217,164,0.06)', color:'#46d9a4', border:'1px solid rgba(70,217,164,0.15)' }}>{skill.calls_last_24h} calls/24h</span>
                        )}
                      </div>
                    </div>
                    {skill.url && (
                      <a href={skill.url} target="_blank" rel="noreferrer" style={{ fontSize:11, color:'var(--accent)', textDecoration:'none', flexShrink:0, paddingTop:2 }}>→</a>
                    )}
                  </div>
                </div>
              ))}
              {(remoteSkills || []).filter(rs => !(liveSkills || []).some(ls => ls.skill_id === rs.skill_id)).map(skill => (
                <div key={skill.skill_id} style={{ padding:'12px 14px', borderRadius:14, background:'rgba(255,255,255,0.02)', border:'1px dashed rgba(255,255,255,0.06)' }}>
                  <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:8 }}>
                    <div style={{ flex:1 }}>
                      <div style={{ fontSize:13, fontWeight:700, color:'var(--text-secondary)', marginBottom:2 }}>{skill.name}</div>
                      <div style={{ fontSize:11, color:'var(--text-tertiary)', lineHeight:1.5, marginBottom:4 }}>{skill.description}</div>
                      <div style={{ display:'flex', gap:5, flexWrap:'wrap' }}>
                        <span style={{ fontSize:9, fontFamily:'var(--font-mono)', padding:'1px 6px', borderRadius:4, background:'rgba(255,255,255,0.04)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.09em' }}>remote · {skill.source || 'github'}</span>
                      </div>
                    </div>
                    {skill.url && (
                      <a href={skill.url} target="_blank" rel="noreferrer" style={{ fontSize:11, color:'var(--accent)', textDecoration:'none', flexShrink:0, paddingTop:2 }}>→</a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Filter + search — only shown for catalogue tab */}
      {tab === 'catalogue' && <>
        <div style={{ display:'flex', gap:8, marginTop:18, marginBottom:14, flexWrap:'wrap', alignItems:'center' }}>
          <div style={{ display:'flex', gap:5, flexWrap:'wrap' }}>
            {categories.map(cat => {
              const c = CATEGORY_COLORS[cat] || 'var(--text-muted)';
              return (
                <button key={cat} onClick={()=>setFilter(cat)} style={{
                  padding:'5px 13px', borderRadius:999, fontSize:11, fontWeight:600, cursor:'pointer',
                  background:filter===cat?'rgba(93,162,255,0.12)':'rgba(255,255,255,0.04)',
                  border:`1px solid ${filter===cat?'rgba(93,162,255,0.32)':'rgba(255,255,255,0.09)'}`,
                  color:filter===cat?'#fff':'var(--text-muted)', textTransform:'capitalize', transition:'all 0.15s',
                }}>{cat==='all'?'All skills':cat}</button>
              );
            })}
          </div>
          <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search skills…"
            style={{ flex:1, minWidth:140, padding:'7px 12px', borderRadius:10, background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-main)' }}
            onFocus={e=>e.target.style.borderColor='rgba(93,162,255,0.45)'} onBlur={e=>e.target.style.borderColor='rgba(255,255,255,0.10)'}/>
        </div>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(320px,1fr))', gap:14 }}>
          {filtered.map(skill => <SkillCard key={skill.id} skill={skill} onToggle={toggle} onConfigure={()=>{}}/>)}
        </div>
      </>}
    </div>
  );
}

export { SkillsScreen, Explain };
export default SkillsScreen;
