/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import * as api from '../../api';
import { useSafeData } from '../hooks/useSafeData';

// knowledge.jsx — Knowledge Base
// Records everything: docs, sources, agent activity, quick notes, GitHub context

function relTime(val) {
  if (!val) return '—';
  const ts = typeof val === 'number' ? val * 1000 : new Date(val).getTime();
  if (isNaN(ts)) return '—';
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}

const tagColors = { pr:'#5da2ff', scan:'#ffbd66', merge:'#46d9a4', note:'#c4b5fd', directive:'#c4b5fd', release:'#46d9a4', source:'#7c9dff', fix:'#5da2ff' };
const actorColors = { 'Dev Agent':'#5da2ff', 'Security Agent':'#ffbd66', 'CEO Agent':'#c4b5fd', 'Release Agent':'#7c9dff', 'Sam Striker':'#46d9a4', 'Alex Chen':'#46d9a4' };

function SourceTypeIcon({ type }) {
  const icons = { github:'⎇', url:'🔗', file:'📄', text:'📝' };
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
      {Array.isArray(doc.tags) && doc.tags.length > 0 && (
        <div style={{ display:'flex', gap:5, flexWrap:'wrap', marginBottom:5 }}>
          {doc.tags.map(t => <Tag key={t} label={t} color='var(--accent)'/>)}
        </div>
      )}
      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>
        {doc.words > 0 ? `${doc.words.toLocaleString()} words` : '—'} · by {doc.author || '—'}
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

function SourceRow({ source, onRemove, busy }) {
  const st = source.status || 'pending';
  const statusColor = (st === 'processed' || st === 'synced') ? '#46d9a4' : st === 'failed' ? '#ff6b7d' : '#ffbd66';
  const label = source.title || source.url || 'Untitled source';
  const sub = source.summary || (source.url || '');
  return (
    <div style={{ display:'flex', alignItems:'center', gap:10, padding:'11px 14px', borderRadius:12, background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.08)' }}>
      <SourceTypeIcon type={source.type}/>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:12, fontWeight:600, color:'var(--text-primary)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{label}</div>
        <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', marginTop:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{sub ? `${sub} · ` : ''}{relTime(source.created_at)}</div>
      </div>
      <div style={{ display:'flex', alignItems:'center', gap:5, flexShrink:0 }}>
        <span style={{ width:6, height:6, borderRadius:'50%', background:statusColor }}/>
        <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:statusColor, textTransform:'uppercase', letterSpacing:'0.10em' }}>{st}</span>
      </div>
      <button onClick={() => onRemove(source._id || source.id)} disabled={busy} style={{ width:26, height:26, borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', background:'transparent', border:'none', cursor:busy?'wait':'pointer', color:'var(--text-muted)', fontSize:12, flexShrink:0 }}
        onMouseEnter={e => { e.currentTarget.style.background='rgba(255,107,125,0.10)'; e.currentTarget.style.color='#ff6b7d'; }}
        onMouseLeave={e => { e.currentTarget.style.background='transparent'; e.currentTarget.style.color='var(--text-muted)'; }}>✕</button>
    </div>
  );
}

function AddSourceForm({ onIngest, onClose }) {
  const [type, setType] = React.useState('url');
  const [url, setUrl]   = React.useState('');
  const [title, setTitle] = React.useState('');
  const [text, setText] = React.useState('');
  const [file, setFile] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState(null);

  const submit = async () => {
    if (busy) return;
    const fd = new FormData();
    if (title.trim()) fd.append('title', title.trim());
    if (type === 'file') {
      if (!file) { setError('Choose a file to ingest.'); return; }
      fd.append('file', file);
    } else if (type === 'text') {
      if (!text.trim()) { setError('Enter some text to ingest.'); return; }
      fd.append('content_text', text.trim());
    } else {
      if (!url.trim()) { setError('Enter a URL to ingest.'); return; }
      fd.append('url', url.trim());
    }
    setBusy(true); setError(null);
    try {
      await onIngest(fd);
      onClose();
    } catch (e) {
      const detail = e?.response?.data?.detail;
      setError(detail ? api.fmtErr(detail) : (e?.message || 'Could not ingest source.'));
      setBusy(false);
    }
  };

  return (
    <div style={{ padding:'14px', borderRadius:14, background:'rgba(93,162,255,0.05)', border:'1px solid rgba(93,162,255,0.18)', marginBottom:12, animation:'fadeSlideUp 0.2s ease-out' }}>
      <div style={{ fontSize:11, fontWeight:700, color:'var(--text-secondary)', marginBottom:10 }}>Add source</div>
      <div style={{ display:'flex', gap:6, marginBottom:10 }}>
        {['url','text','file'].map(t => (
          <button key={t} onClick={() => setType(t)} style={{ padding:'5px 12px', borderRadius:999, fontSize:11, cursor:'pointer', background:type===t?'rgba(93,162,255,0.15)':'rgba(255,255,255,0.04)', border:`1px solid ${type===t?'rgba(93,162,255,0.35)':'rgba(255,255,255,0.09)'}`, color:type===t?'#fff':'var(--text-muted)', textTransform:'capitalize', transition:'all 0.15s' }}>{t}</button>
        ))}
      </div>
      <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Title (optional)"
        style={{ width:'100%', padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-main)', marginBottom:8 }}/>
      {type === 'url' && (
        <input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://docs.example.com"
          style={{ width:'100%', padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-mono)', marginBottom:8 }}/>
      )}
      {type === 'text' && (
        <textarea value={text} onChange={e => setText(e.target.value)} placeholder="Paste content to index…" rows={3}
          style={{ width:'100%', padding:'9px 12px', borderRadius:10, resize:'vertical', background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-main)', marginBottom:8 }}/>
      )}
      {type === 'file' && (
        <input type="file" onChange={e => setFile(e.target.files?.[0] || null)}
          style={{ width:'100%', fontSize:12, color:'var(--text-secondary)', marginBottom:8 }}/>
      )}
      {error && <div style={{ marginBottom:8, padding:'8px 12px', borderRadius:10, background:'rgba(255,107,125,0.10)', border:'1px solid rgba(255,107,125,0.25)', color:'#ff6b7d', fontSize:12 }}>{error}</div>}
      <div style={{ display:'flex', gap:8 }}>
        <button onClick={submit} disabled={busy} style={{ padding:'9px 16px', borderRadius:10, background:'var(--accent)', color:'#06111f', fontSize:12, fontWeight:800, border:'none', cursor:busy?'wait':'pointer', opacity:busy?0.7:1 }}>{busy ? 'Ingesting…' : 'Add'}</button>
        <button onClick={onClose} disabled={busy} style={{ padding:'9px 14px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-muted)', fontSize:12, cursor:'pointer' }}>Cancel</button>
      </div>
    </div>
  );
}

// Map a raw activity log entry into the ActivityRow shape (no fabricated fields).
function mapActivity(log, index) {
  const et = (log.event_type || log.type || '').toString();
  return {
    id: log._id || log.id || `${et}-${log.created_at || log.timestamp || index}`,
    type: 'agent',
    actor: et ? et.replace(/_/g, ' ') : 'System',
    tag: (et.split('_')[0] || 'note'),
    action: log.message || log.detail || et || 'Activity',
    ts: relTime(log.created_at || log.timestamp),
  };
}

function KnowledgeScreen() {
  const [tab, setTab]           = React.useState('activity');
  const [showAdd, setShowAdd]   = React.useState(false);
  const [search, setSearch]     = React.useState('');
  const [actFilter, setActFilter] = React.useState('all');
  const [removingId, setRemovingId] = React.useState(null);
  const [actionErr, setActionErr]   = React.useState(null);

  const [data, states, refetch] = useSafeData(null, {
    pages:    '/api/wiki/pages',
    sources:  '/api/sources',
    activity: '/api/activity?limit=40',
  }, { refreshMs: 30000 });

  const pages   = data.pages?.pages || [];
  const sources = data.sources?.sources || [];
  const activityRaw = data.activity?.logs || data.activity?.events || data.activity?.activity || (Array.isArray(data.activity) ? data.activity : []);
  const activity = activityRaw.map((log, i) => mapActivity(log, i));

  const docs = pages.map(p => ({
    id: p._id || p.slug,
    title: p.title || p.slug || 'Untitled',
    updated: relTime(p.updated_at || p.created_at),
    tags: Array.isArray(p.tags) ? p.tags : [],
    words: typeof p.content === 'string' ? p.content.trim().split(/\s+/).filter(Boolean).length : 0,
    author: p.created_by || '—',
  }));

  const handleIngest = async (formData) => {
    await api.ingestSource(formData);
    await refetch();
  };
  const handleRemove = async (id) => {
    setRemovingId(id); setActionErr(null);
    try { await api.deleteSource(id); await refetch(); }
    catch (e) {
      const detail = e?.response?.data?.detail;
      setActionErr(detail ? api.fmtErr(detail) : (e?.message || 'Could not remove source.'));
    } finally { setRemovingId(null); }
  };

  const filteredActivity = activity.filter(a => actFilter === 'all' || a.type === actFilter);

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
          { label:'Docs', value:docs.length, color:'var(--accent)' },
          { label:'Sources', value:sources.length, color:'#c4b5fd' },
          { label:'Processed', value:sources.filter(s=>s.status==='processed').length, color:'#46d9a4' },
          { label:'Activity events', value:activity.length, color:'#ffbd66' },
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
            {states.activity?.loading && activity.length === 0 ? (
              <div style={{ padding:'18px 0', fontSize:13, color:'var(--text-muted)' }}>Loading activity…</div>
            ) : states.activity?.error ? (
              <div style={{ padding:'18px 0', fontSize:13, color:'#ff6b7d' }}>Couldn't load activity: {states.activity.error}</div>
            ) : filteredActivity.length === 0 ? (
              <div style={{ padding:'18px 0', fontSize:13, color:'var(--text-muted)' }}>No activity recorded yet.</div>
            ) : (
              filteredActivity.map(item => <ActivityRow key={item.id} item={item}/>)
            )}
          </div>
        </div>
      )}

      {tab === 'docs' && (
        <div style={{ animation:'fadeSlideUp 0.3s ease-out' }}>
          <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:10 }}>
            <button style={{ padding:'8px 16px', borderRadius:10, fontSize:12, fontWeight:700, cursor:'pointer', background:'rgba(93,162,255,0.12)', border:'1px solid rgba(93,162,255,0.25)', color:'var(--accent)' }}>+ New doc</button>
          </div>
          {states.pages?.loading && docs.length === 0 ? (
            <div style={{ padding:'18px 0', fontSize:13, color:'var(--text-muted)' }}>Loading docs…</div>
          ) : states.pages?.error ? (
            <div style={{ padding:'18px 0', fontSize:13, color:'#ff6b7d' }}>Couldn't load docs: {states.pages.error}</div>
          ) : docs.filter(d => !search || d.title.toLowerCase().includes(search.toLowerCase())).length === 0 ? (
            <div style={{ padding:'18px 0', fontSize:13, color:'var(--text-muted)' }}>No docs yet.</div>
          ) : (
            <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(260px,1fr))', gap:10 }}>
              {docs.filter(d => !search || d.title.toLowerCase().includes(search.toLowerCase())).map(doc => <DocCard key={doc.id} doc={doc}/>)}
            </div>
          )}
        </div>
      )}

      {tab === 'sources' && (
        <div style={{ animation:'fadeSlideUp 0.3s ease-out' }}>
          <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:10 }}>
            <button onClick={() => setShowAdd(true)} style={{ padding:'8px 16px', borderRadius:10, fontSize:12, fontWeight:700, cursor:'pointer', background:'rgba(93,162,255,0.12)', border:'1px solid rgba(93,162,255,0.25)', color:'var(--accent)' }}>+ Add source</button>
          </div>
          {showAdd && <AddSourceForm onIngest={handleIngest} onClose={() => setShowAdd(false)}/>}
          {actionErr && <div style={{ marginBottom:10, padding:'8px 12px', borderRadius:10, background:'rgba(255,107,125,0.10)', border:'1px solid rgba(255,107,125,0.25)', color:'#ff6b7d', fontSize:12 }}>{actionErr}</div>}
          {states.sources?.loading && sources.length === 0 ? (
            <div style={{ padding:'18px 0', fontSize:13, color:'var(--text-muted)' }}>Loading sources…</div>
          ) : states.sources?.error ? (
            <div style={{ padding:'18px 0', fontSize:13, color:'#ff6b7d' }}>Couldn't load sources: {states.sources.error}</div>
          ) : sources.length === 0 ? (
            <div style={{ padding:'18px 0', fontSize:13, color:'var(--text-muted)' }}>No sources yet. Add a URL, text, or file above to index it.</div>
          ) : (
            <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
              {sources.map(s => <SourceRow key={s._id || s.id} source={s} onRemove={handleRemove} busy={removingId===(s._id||s.id)}/>)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export { KnowledgeScreen };
export default KnowledgeScreen;
