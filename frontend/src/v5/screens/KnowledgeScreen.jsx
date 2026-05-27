/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';


// knowledge.jsx — Knowledge Base
// Records everything: docs, sources, agent activity, quick notes, GitHub context

const KB_DOCS = [
  { id:'d-1', title:'API Surface Map',          slug:'api-surface',       updated:'2h ago',  author:'Dev Agent',    words:1240, tags:['api','docs'] },
  { id:'d-2', title:'Checkout Flow Overview',   slug:'checkout-flow',     updated:'1d ago',  author:'Sam Striker',  words:840,  tags:['commerce','checkout'] },
  { id:'d-3', title:'Agent Orchestration Guide',slug:'agent-orch',        updated:'3d ago',  author:'CEO Agent',    words:2100, tags:['agents','architecture'] },
  { id:'d-4', title:'Security Hardening Notes', slug:'security-notes',    updated:'5d ago',  author:'Security Agent',words:680, tags:['security'] },
  { id:'d-5', title:'Deployment Runbook',       slug:'deploy-runbook',    updated:'1w ago',  author:'Sam Striker',  words:1560, tags:['ops','deploy'] },
];

const KB_SOURCES = [
  { id:'s-1', type:'github', label:'strikersam/local-llm-server', url:'https://github.com/strikersam/local-llm-server', status:'synced', indexed:1842, updated:'2h ago' },
  { id:'s-2', type:'github', label:'strikersam/acme-store',        url:'https://github.com/strikersam/acme-store',        status:'synced', indexed:4210, updated:'3h ago' },
  { id:'s-3', type:'url',    label:'acme-store.com/docs',          url:'https://acme-store.com/docs',                     status:'synced', indexed:312,  updated:'1d ago' },
  { id:'s-4', type:'url',    label:'Shopify Partner Docs',         url:'https://shopify.dev/docs',                        status:'partial',indexed:88,   updated:'2d ago' },
  { id:'s-5', type:'file',   label:'architecture.pdf',             url:null,                                              status:'synced', indexed:420,  updated:'3d ago' },
];

const KB_ACTIVITY = [
  { id:'a-1', type:'agent',  actor:'Dev Agent',      action:'Opened PR #1842 — fix null-check in checkout',        ts:'2m ago',   tag:'pr' },
  { id:'a-2', type:'agent',  actor:'Security Agent', action:'Completed bandit scan — 0 issues found in auth/',     ts:'8m ago',   tag:'scan' },
  { id:'a-3', type:'human',  actor:'Sam Striker',    action:'Approved PR #1842 and merged to main',               ts:'14m ago',  tag:'merge' },
  { id:'a-4', type:'note',   actor:'Sam Striker',    action:'Quick note: "Add skeleton loading to dashboard"',     ts:'2h ago',   tag:'note' },
  { id:'a-5', type:'agent',  actor:'CEO Agent',      action:'Issued 3 directives in assessment cycle #1344',       ts:'14m ago',  tag:'directive' },
  { id:'a-6', type:'agent',  actor:'Release Agent',  action:'Bumped version to v5.0 in CHANGELOG.md',             ts:'1h ago',   tag:'release' },
  { id:'a-7', type:'human',  actor:'Alex Chen',      action:'Added Contentful source to knowledge base',          ts:'3h ago',   tag:'source' },
  { id:'a-8', type:'agent',  actor:'Dev Agent',      action:'Fixed 3 failing tests in cart/checkout.test.ts',     ts:'4h ago',   tag:'fix' },
];

const tagColors = { pr:'#5da2ff', scan:'#ffbd66', merge:'#46d9a4', note:'#c4b5fd', directive:'#c4b5fd', release:'#46d9a4', source:'#7c9dff', fix:'#5da2ff' };
const actorColors = { 'Dev Agent':'#5da2ff', 'Security Agent':'#ffbd66', 'CEO Agent':'#c4b5fd', 'Release Agent':'#7c9dff', 'Sam Striker':'#46d9a4', 'Alex Chen':'#46d9a4' };

function SourceTypeIcon({ type }) {
  const icons = { github:'⎇', url:'🔗', file:'📄' };
  return <span style={{ fontSize:14 }}>{icons[type] || '◎'}</span>;
}

function Tag({ label, color }) {
  return <span style={{ fontSize:9, fontFamily:'var(--font-mono)', letterSpacing:'0.10em', textTransform:'uppercase', padding:'2px 7px', borderRadius:999, color: color || 'var(--text-muted)', background:`${color || '#fff'}12`, border:`1px solid ${color || '#fff'}22` }}>{label}</span>;
}

function DocCard({ doc }) {
  return (
    <button style={{
      padding:'12px 14px', borderRadius:14, textAlign:'left', cursor:'pointer',
      background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.09)',
      transition:'all 0.15s ease', width:'100%',
    }}
    onMouseEnter={e => { e.currentTarget.style.background='rgba(93,162,255,0.06)'; e.currentTarget.style.borderColor='rgba(93,162,255,0.20)'; }}
    onMouseLeave={e => { e.currentTarget.style.background='rgba(255,255,255,0.03)'; e.currentTarget.style.borderColor='rgba(255,255,255,0.09)'; }}>
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:6 }}>
        <span style={{ fontSize:13, fontWeight:700, color:'var(--text-primary)', lineHeight:1.4 }}>{doc.title}</span>
        <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', flexShrink:0, marginLeft:8 }}>{doc.updated}</span>
      </div>
      <div style={{ display:'flex', gap:5, flexWrap:'wrap', marginBottom:5 }}>
        {doc.tags.map(t => <Tag key={t} label={t} color='var(--accent)'/>)}
      </div>
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>
        {doc.words.toLocaleString()} words · by {doc.author}
      </div>
    </button>
  );
}

function ActivityRow({ item }) {
  const color = actorColors[item.actor] || 'var(--text-muted)';
  const tagColor = tagColors[item.tag] || 'var(--text-muted)';
  const typeIcon = item.type === 'human' ? '👤' : item.type === 'note' ? '📝' : '🤖';
  return (
    <div style={{ display:'flex', alignItems:'flex-start', gap:10, padding:'9px 0', borderBottom:'1px solid rgba(255,255,255,0.05)' }}>
      <span style={{ fontSize:14, flexShrink:0, marginTop:1 }}>{typeIcon}</span>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ display:'flex', alignItems:'center', gap:6, flexWrap:'wrap', marginBottom:2 }}>
          <span style={{ fontSize:11, fontWeight:700, color }}>{item.actor}</span>
          <Tag label={item.tag} color={tagColor}/>
        </div>
        <div style={{ fontSize:12, color:'var(--text-tertiary)', lineHeight:1.5 }}>{item.action}</div>
      </div>
      <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', flexShrink:0, marginTop:2 }}>{item.ts}</span>
    </div>
  );
}

function SourceRow({ source, onRemove }) {
  const statusColor = source.status === 'synced' ? '#46d9a4' : '#ffbd66';
  return (
    <div style={{ display:'flex', alignItems:'center', gap:10, padding:'11px 14px', borderRadius:12, background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.08)' }}>
      <SourceTypeIcon type={source.type}/>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:12, fontWeight:600, color:'var(--text-primary)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{source.label}</div>
        <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', marginTop:1 }}>{source.indexed.toLocaleString()} chunks indexed · {source.updated}</div>
      </div>
      <div style={{ display:'flex', alignItems:'center', gap:5, flexShrink:0 }}>
        <span style={{ width:6, height:6, borderRadius:'50%', background:statusColor }}/>
        <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:statusColor, textTransform:'uppercase', letterSpacing:'0.10em' }}>{source.status}</span>
      </div>
      <button onClick={() => onRemove(source.id)} style={{ width:26, height:26, borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', background:'transparent', border:'none', cursor:'pointer', color:'var(--text-muted)', fontSize:12, flexShrink:0 }}
        onMouseEnter={e => { e.currentTarget.style.background='rgba(255,107,125,0.10)'; e.currentTarget.style.color='#ff6b7d'; }}
        onMouseLeave={e => { e.currentTarget.style.background='transparent'; e.currentTarget.style.color='var(--text-muted)'; }}>✕</button>
    </div>
  );
}

function AddSourceForm({ onAdd, onClose }) {
  const [type, setType] = React.useState('github');
  const [url, setUrl]   = React.useState('');
  return (
    <div style={{ padding:'14px', borderRadius:14, background:'rgba(93,162,255,0.05)', border:'1px solid rgba(93,162,255,0.18)', marginBottom:12, animation:'fadeSlideUp 0.2s ease-out' }}>
      <div style={{ fontSize:11, fontWeight:700, color:'var(--text-secondary)', marginBottom:10 }}>Add source</div>
      <div style={{ display:'flex', gap:6, marginBottom:10 }}>
        {['github','url','file'].map(t => (
          <button key={t} onClick={() => setType(t)} style={{ padding:'5px 12px', borderRadius:999, fontSize:11, cursor:'pointer', background:type===t?'rgba(93,162,255,0.15)':'rgba(255,255,255,0.04)', border:`1px solid ${type===t?'rgba(93,162,255,0.35)':'rgba(255,255,255,0.09)'}`, color:type===t?'#fff':'var(--text-muted)', textTransform:'capitalize', transition:'all 0.15s' }}>{t}</button>
        ))}
      </div>
      <div style={{ display:'flex', gap:8 }}>
        <input value={url} onChange={e => setUrl(e.target.value)} placeholder={type==='github'?'github.com/org/repo':type==='url'?'https://docs.example.com':'Upload file…'}
          style={{ flex:1, padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-main)' }}
          onFocus={e => e.target.style.borderColor='rgba(93,162,255,0.45)'} onBlur={e => e.target.style.borderColor='rgba(255,255,255,0.10)'}/>
        <button onClick={() => { if(url.trim()) { onAdd({id:`s-${Date.now()}`,type,label:url.trim().replace('https://',''),url,status:'synced',indexed:0,updated:'just now'}); onClose(); }}} style={{ padding:'9px 16px', borderRadius:10, background:'var(--accent)', color:'#06111f', fontSize:12, fontWeight:800, border:'none', cursor:'pointer' }}>Add</button>
        <button onClick={onClose} style={{ padding:'9px 14px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-muted)', fontSize:12, cursor:'pointer' }}>Cancel</button>
      </div>
    </div>
  );
}

function KnowledgeScreen() {
  const [tab, setTab]           = React.useState('activity');
  const [sources, setSources]   = React.useState(KB_SOURCES);
  const [showAdd, setShowAdd]   = React.useState(false);
  const [search, setSearch]     = React.useState('');
  const [actFilter, setActFilter] = React.useState('all');

  const filteredActivity = KB_ACTIVITY.filter(a => actFilter === 'all' || a.type === actFilter);

  return (
    <div style={{ padding:'20px 16px 48px', maxWidth:900, margin:'0 auto' }}>
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:6 }}>Knowledge</div>
      <div style={{ display:'flex', alignItems:'flex-end', justifyContent:'space-between', flexWrap:'wrap', gap:10, marginBottom:16 }}>
        <div>
          <h1 style={{ fontSize:26, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', lineHeight:1.1, marginBottom:4 }}>Knowledge Base</h1>
          <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.5, maxWidth:480 }}>Everything agents and humans do is recorded here. Docs, sources, activity, quick notes — one searchable memory.</p>
        </div>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search knowledge…"
          style={{ padding:'9px 14px', borderRadius:12, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-main)', minWidth:200 }}
          onFocus={e => e.target.style.borderColor='rgba(93,162,255,0.45)'} onBlur={e => e.target.style.borderColor='rgba(255,255,255,0.10)'}/>
      </div>

      {/* Stats row */}
      <div style={{ display:'flex', gap:10, marginBottom:18, flexWrap:'wrap' }}>
        {[
          { label:'Docs', value:KB_DOCS.length, color:'var(--accent)' },
          { label:'Sources', value:sources.length, color:'#c4b5fd' },
          { label:'Chunks indexed', value:sources.reduce((s,x)=>s+x.indexed,0).toLocaleString(), color:'#46d9a4' },
          { label:'Activity events', value:KB_ACTIVITY.length, color:'#ffbd66' },
        ].map(s => (
          <div key={s.label} style={{ padding:'8px 14px', borderRadius:12, background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.08)' }}>
            <div style={{ fontSize:18, fontWeight:800, color:s.color, letterSpacing:'-0.03em' }}>{s.value}</div>
            <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.10em', textTransform:'uppercase' }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display:'flex', gap:4, marginBottom:16 }}>
        {['activity','docs','sources'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ padding:'7px 18px', borderRadius:999, fontSize:12, fontWeight:600, cursor:'pointer', textTransform:'capitalize', transition:'all 0.15s', background:tab===t?'rgba(93,162,255,0.15)':'rgba(255,255,255,0.04)', border:`1px solid ${tab===t?'rgba(93,162,255,0.35)':'rgba(255,255,255,0.08)'}`, color:tab===t?'#fff':'var(--text-muted)' }}>{t}</button>
        ))}
      </div>

      {tab === 'activity' && (
        <div style={{ animation:'fadeSlideUp 0.3s ease-out' }}>
          <div style={{ display:'flex', gap:6, marginBottom:12 }}>
            {['all','agent','human','note'].map(f => (
              <button key={f} onClick={() => setActFilter(f)} style={{ padding:'4px 12px', borderRadius:999, fontSize:11, cursor:'pointer', textTransform:'capitalize', background:actFilter===f?'rgba(93,162,255,0.12)':'rgba(255,255,255,0.04)', border:`1px solid ${actFilter===f?'rgba(93,162,255,0.30)':'rgba(255,255,255,0.08)'}`, color:actFilter===f?'#fff':'var(--text-muted)', transition:'all 0.15s' }}>{f}</button>
            ))}
          </div>
          <div style={{ background:'rgba(255,255,255,0.02)', border:'1px solid rgba(255,255,255,0.08)', borderRadius:16, padding:'0 16px' }}>
            {filteredActivity.map(item => <ActivityRow key={item.id} item={item}/>)}
          </div>
        </div>
      )}

      {tab === 'docs' && (
        <div style={{ animation:'fadeSlideUp 0.3s ease-out' }}>
          <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:10 }}>
            <button style={{ padding:'8px 16px', borderRadius:10, fontSize:12, fontWeight:700, cursor:'pointer', background:'rgba(93,162,255,0.12)', border:'1px solid rgba(93,162,255,0.25)', color:'var(--accent)' }}>+ New doc</button>
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(260px,1fr))', gap:10 }}>
            {KB_DOCS.filter(d => !search || d.title.toLowerCase().includes(search.toLowerCase())).map(doc => <DocCard key={doc.id} doc={doc}/>)}
          </div>
        </div>
      )}

      {tab === 'sources' && (
        <div style={{ animation:'fadeSlideUp 0.3s ease-out' }}>
          <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:10 }}>
            <button onClick={() => setShowAdd(true)} style={{ padding:'8px 16px', borderRadius:10, fontSize:12, fontWeight:700, cursor:'pointer', background:'rgba(93,162,255,0.12)', border:'1px solid rgba(93,162,255,0.25)', color:'var(--accent)' }}>+ Add source</button>
          </div>
          {showAdd && <AddSourceForm onAdd={s => setSources(p => [s,...p])} onClose={() => setShowAdd(false)}/>}
          <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
            {sources.map(s => <SourceRow key={s.id} source={s} onRemove={id => setSources(p => p.filter(x => x.id !== id))}/>)}
          </div>
        </div>
      )}
    </div>
  );
}

export { KnowledgeScreen };
export default KnowledgeScreen;
