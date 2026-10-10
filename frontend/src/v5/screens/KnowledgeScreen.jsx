/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import * as api from '../../api';
import { useSafeData } from '../hooks/useSafeData';
import { COMPANY_ID_KEY } from './CompanyScreen';

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

const tagColors = { pr:'var(--accent)', scan:'var(--warning)', merge:'var(--success)', note:'var(--violet)', directive:'var(--violet)', release:'var(--success)', source:'var(--accent)', fix:'var(--accent)' };
const actorColors = { 'Dev Agent':'var(--accent)', 'Security Agent':'var(--warning)', 'CEO Agent':'var(--violet)', 'Release Agent':'var(--accent)', 'Sam Striker':'var(--success)', 'Alex Chen':'var(--success)' };

function SourceTypeIcon({ type }) {
  const icons = { github:'⎇', url:'🔗', file:'📄', text:'📝' };
  return <span style={{ fontSize:14 }}>{icons[type] || '◎'}</span>;
}

function Tag({ label, color }) {
  return <span style={{ fontSize:13, padding:'2px 7px', borderRadius:999, color: color || 'var(--text-muted)', background:`color-mix(in oklab, ${color || 'var(--text-muted)'} 7%, transparent)`, border:`1px solid color-mix(in oklab, ${color || 'var(--text-muted)'} 13%, transparent)` }}>{label}</span>;
}

function DocCard({ doc }) {
  return (
    <button style={{
      padding:'12px 14px', borderRadius:14, textAlign:'left', cursor:'pointer',
      background:'color-mix(in oklab, var(--ink) 3%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 9%, transparent)',
      transition:'all 0.15s ease', width:'100%',
    }}
    onMouseEnter={e => { e.currentTarget.style.background='color-mix(in oklab, var(--accent) 6%, transparent)'; e.currentTarget.style.borderColor='color-mix(in oklab, var(--accent) 20%, transparent)'; }}
    onMouseLeave={e => { e.currentTarget.style.background='color-mix(in oklab, var(--ink) 3%, transparent)'; e.currentTarget.style.borderColor='color-mix(in oklab, var(--ink) 9%, transparent)'; }}>
      <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:6 }}>
        <span style={{ fontSize:14, fontWeight:700, color:'var(--text-primary)', lineHeight:1.4 }}>{doc.title}</span>
        <span style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--text-muted)', flexShrink:0, marginLeft:8 }}>{doc.updated}</span>
      </div>
      {Array.isArray(doc.tags) && doc.tags.length > 0 && (
        <div style={{ display:'flex', gap:5, flexWrap:'wrap', marginBottom:5 }}>
          {doc.tags.map(t => <Tag key={t} label={t} color='var(--accent)'/>)}
        </div>
      )}
      <div style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--text-muted)' }}>
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
    <div style={{ display:'flex', alignItems:'flex-start', gap:10, padding:'9px 0', borderBottom:'1px solid color-mix(in oklab, var(--ink) 5%, transparent)' }}>
      <span style={{ fontSize:14, flexShrink:0, marginTop:1 }}>{typeIcon}</span>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ display:'flex', alignItems:'center', gap:6, flexWrap:'wrap', marginBottom:2 }}>
          <span style={{ fontSize:13, fontWeight:700, color }}>{item.actor}</span>
          <Tag label={item.tag} color={tagColor}/>
        </div>
        <div style={{ fontSize:13, color:'var(--text-tertiary)', lineHeight:1.5 }}>{item.action}</div>
      </div>
      <span style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--text-muted)', flexShrink:0, marginTop:2 }}>{item.ts}</span>
    </div>
  );
}

function SourceRow({ source, onRemove, busy }) {
  const st = source.status || 'pending';
  const statusColor = (st === 'processed' || st === 'synced') ? 'var(--success)' : st === 'failed' ? 'var(--danger)' : 'var(--warning)';
  const label = source.title || source.url || 'Untitled source';
  const sub = source.summary || (source.url || '');
  return (
    <div style={{ display:'flex', alignItems:'center', gap:10, padding:'11px 14px', borderRadius:12, background:'color-mix(in oklab, var(--ink) 3%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)' }}>
      <SourceTypeIcon type={source.type}/>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:13, fontWeight:600, color:'var(--text-primary)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{label}</div>
        <div style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--text-muted)', marginTop:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{sub ? `${sub} · ` : ''}{relTime(source.created_at)}</div>
      </div>
      <div style={{ display:'flex', alignItems:'center', gap:5, flexShrink:0 }}>
        <span style={{ width:6, height:6, borderRadius:'50%', background:statusColor }}/>
        <span style={{ fontSize:13, color:statusColor }}>{st}</span>
      </div>
      <button onClick={() => onRemove(source._id || source.id)} disabled={busy} style={{ width:26, height:26, borderRadius:8, display:'flex', alignItems:'center', justifyContent:'center', background:'transparent', border:'none', cursor:busy?'wait':'pointer', color:'var(--text-muted)', fontSize:13, flexShrink:0 }}
        onMouseEnter={e => { e.currentTarget.style.background='color-mix(in oklab, var(--danger) 10%, transparent)'; e.currentTarget.style.color='#ff6b7d'; }}
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
    <div style={{ padding:'14px', borderRadius:14, background:'color-mix(in oklab, var(--accent) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 18%, transparent)', marginBottom:12, animation:'fadeSlideUp 0.2s ease-out' }}>
      <div style={{ fontSize:13, fontWeight:700, color:'var(--text-secondary)', marginBottom:10 }}>Add source</div>
      <div style={{ display:'flex', gap:6, marginBottom:10 }}>
        {['url','text','file'].map(t => (
          <button key={t} onClick={() => setType(t)} style={{ padding:'5px 12px', borderRadius:999, fontSize:13, cursor:'pointer', background:type===t?'color-mix(in oklab, var(--accent) 15%, transparent)':'color-mix(in oklab, var(--ink) 4%, transparent)', border:`1px solid ${type===t?'color-mix(in oklab, var(--accent) 35%, transparent)':'color-mix(in oklab, var(--ink) 9%, transparent)'}`, color:type===t?'var(--text-primary)':'var(--text-muted)', textTransform:'capitalize', transition:'all 0.15s' }}>{t}</button>
        ))}
      </div>
      <input value={title} onChange={e => setTitle(e.target.value)} placeholder="Title (optional)"
        style={{ width:'100%', padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:14, outline:'none', fontFamily:'var(--font-main)', marginBottom:8 }}/>
      {type === 'url' && (
        <input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://docs.example.com"
          style={{ width:'100%', padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:14, outline:'none', fontFamily:'var(--font-mono)', marginBottom:8 }}/>
      )}
      {type === 'text' && (
        <textarea value={text} onChange={e => setText(e.target.value)} placeholder="Paste content to index…" rows={3}
          style={{ width:'100%', padding:'9px 12px', borderRadius:10, resize:'vertical', background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:14, outline:'none', fontFamily:'var(--font-main)', marginBottom:8 }}/>
      )}
      {type === 'file' && (
        <input type="file" onChange={e => setFile(e.target.files?.[0] || null)}
          style={{ width:'100%', fontSize:13, color:'var(--text-secondary)', marginBottom:8 }}/>
      )}
      {error && <div style={{ marginBottom:8, padding:'8px 12px', borderRadius:10, background:'color-mix(in oklab, var(--danger) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 25%, transparent)', color:'var(--danger)', fontSize:13 }}>{error}</div>}
      <div style={{ display:'flex', gap:8 }}>
        <button onClick={submit} disabled={busy} style={{ padding:'9px 16px', borderRadius:10, background:'var(--accent)', color:'var(--on-accent)', fontSize:13, fontWeight:700, border:'none', cursor:busy?'wait':'pointer', opacity:busy?0.7:1 }}>{busy ? 'Ingesting…' : 'Add'}</button>
        <button onClick={onClose} disabled={busy} style={{ padding:'9px 14px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-muted)', fontSize:13, cursor:'pointer' }}>Cancel</button>
      </div>
    </div>
  );
}

// --- Company Graph tab ------------------------------------------------
// Renders the CompanyGraph (services/company_graph.py / models/company_graph.py)
// as a node-link diagram, scoped to whichever company the logged-in user can
// see (GET /api/company and GET /api/company/{id}/graph already enforce
// per-user access in backend/company_api.py). No graph-drawing dependency is
// added — a small concentric-ring SVG layout is enough for the node counts
// a single company graph produces.

const GRAPH_NODE_COLORS = {
  company: '#ffffff',
  website: 'var(--accent)',
  repo: 'var(--accent)',
  system: 'var(--warning)',
  specialist: 'var(--success)',
  workflow: 'var(--violet)',
  knowledge: 'var(--danger)',
  connector: '#66e0d0',
};

// The SVG canvas is GRAPH_SIZE square; nodes must stay inside it or they are clipped.
const GRAPH_SIZE = 600;
const GRAPH_MAX_RADIUS = GRAPH_SIZE / 2 - 24;   // leave room for the node circle + label
const GRAPH_NODE_SPACING = 18;                    // min arc length between neighbours on a ring

const GRAPH_CATEGORY_ORDER = ['website', 'repo', 'system', 'specialist', 'workflow', 'knowledge', 'connector'];

// Pure function: CompanyGraph JSON -> { nodes, edges } for the SVG layout below.
// Kept separate from rendering so it can be reasoned about (and unit-tested) on its own.
function buildGraphElements(graph) {
  if (!graph) return { nodes: [], edges: [] };

  const nodes = [];
  const edges = [];
  const companyId = 'company';
  nodes.push({ id: companyId, label: graph.company?.name || 'Company', type: 'company' });

  const byType = {
    website: graph.websites || [],
    repo: graph.repos || [],
    system: graph.systems || [],
    specialist: graph.specialists || [],
    workflow: graph.workflows || [],
    knowledge: graph.knowledge || [],
    connector: graph.connectors || [],
  };

  // Ring radius grows only for categories that actually have data, so a
  // company with just 2 systems doesn't render 5 empty rings. Each ring is at
  // least wide enough for its nodes not to overlap, then the whole set is
  // scaled down if it would not fit the canvas (7 categories used to put the
  // outer rings at radius 480 on a 300-radius canvas, clipping most nodes).
  const usedCategories = GRAPH_CATEGORY_ORDER.filter(t => (byType[t] || []).length > 0);
  const rawRadius = {};
  let prev = 40;
  usedCategories.forEach(t => {
    const needed = (byType[t].length * GRAPH_NODE_SPACING) / (2 * Math.PI);
    rawRadius[t] = Math.max(prev + 45, needed);
    prev = rawRadius[t];
  });
  const scale = Math.min(1, GRAPH_MAX_RADIUS / Math.max(prev, 1));
  const ringRadius = Object.fromEntries(usedCategories.map(t => [t, rawRadius[t] * scale]));

  usedCategories.forEach(type => {
    const items = byType[type];
    const radius = ringRadius[type];
    items.forEach((item, i) => {
      const angle = (2 * Math.PI * i) / items.length - Math.PI / 2;
      nodes.push({
        id: `${type}:${item.id}`,
        label: item.name || item.title || item.id,
        type,
        angle,
        radius,
      });
    });
  });

  // Direct-ownership edges: company -> website/repo/system (always company-owned).
  ['website', 'repo', 'system'].forEach(type => {
    (byType[type] || []).forEach(item => edges.push({ from: companyId, to: `${type}:${item.id}` }));
  });

  // Specialists connect to the systems they specialize in, else to the company.
  (byType.specialist || []).forEach(sp => {
    const specialized = sp.specialized_systems || [];
    const targets = specialized.filter(sysId => (byType.system || []).some(s => s.id === sysId));
    if (targets.length === 0) edges.push({ from: companyId, to: `specialist:${sp.id}` });
    else targets.forEach(sysId => edges.push({ from: `system:${sysId}`, to: `specialist:${sp.id}` }));
  });

  // Workflows connect to the systems they involve, else to the company.
  (byType.workflow || []).forEach(wf => {
    const sysIds = (wf.system_ids || []).filter(sysId => (byType.system || []).some(s => s.id === sysId));
    if (sysIds.length === 0) edges.push({ from: companyId, to: `workflow:${wf.id}` });
    else sysIds.forEach(sysId => edges.push({ from: `system:${sysId}`, to: `workflow:${wf.id}` }));
  });

  // Knowledge items connect to whatever systems/specialists they document, else the company.
  (byType.knowledge || []).forEach(k => {
    const sysIds = (k.related_systems || []).filter(sysId => (byType.system || []).some(s => s.id === sysId));
    const spIds = (k.related_specialists || []).filter(spId => (byType.specialist || []).some(s => s.id === spId));
    if (sysIds.length === 0 && spIds.length === 0) edges.push({ from: companyId, to: `knowledge:${k.id}` });
    else {
      sysIds.forEach(sysId => edges.push({ from: `system:${sysId}`, to: `knowledge:${k.id}` }));
      spIds.forEach(spId => edges.push({ from: `specialist:${spId}`, to: `knowledge:${k.id}` }));
    }
  });

  // Connectors attach to systems that share their system_type, else the company.
  (byType.connector || []).forEach(c => {
    const matches = (byType.system || []).filter(s => s.system_type === c.system_type);
    if (matches.length === 0) edges.push({ from: companyId, to: `connector:${c.id}` });
    else matches.forEach(s => edges.push({ from: `system:${s.id}`, to: `connector:${c.id}` }));
  });

  return { nodes, edges };
}

function CompanyGraphPanel() {
  const storedId = (() => { try { return localStorage.getItem(COMPANY_ID_KEY); } catch { return null; } })();
  const [companies, setCompanies] = React.useState([]);
  const [selectedCompanyId, setSelectedCompanyId] = React.useState(storedId || '');
  const [graph, setGraph] = React.useState(null);
  const [hoveredId, setHoveredId] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState(null);
  const mounted = React.useRef(true);
  React.useEffect(() => () => { mounted.current = false; }, []);

  // Companies the current user can see — backend scopes this by owner/admin
  // (see list_companies in backend/company_api.py), so no client-side filtering needed.
  // Mirrors CompanyScreen.jsx's stale-ID handling (PR #962): only fall back to
  // validating against this (paginated, default limit=100) list when there is
  // no stored ID to begin with. A stored ID is trusted here and instead
  // validated by the direct per-ID getCompanyGraph() lookup below, whose own
  // 404 handler self-heals — otherwise an admin/owner with more companies than
  // fit on one page would have a perfectly valid stored ID outside that page
  // wrongly treated as stale and silently replaced with list[0].
  React.useEffect(() => {
    (async () => {
      try {
        const { data } = await api.listCompanies();
        if (!mounted.current) return;
        const list = data.companies || [];
        setCompanies(list);
        if (!selectedCompanyId && list.length > 0) {
          const match = storedId ? list.find(c => c.id === storedId) : null;
          if (match) {
            setSelectedCompanyId(match.id);
          } else {
            if (storedId) { try { localStorage.removeItem(COMPANY_ID_KEY); } catch {} }
            setSelectedCompanyId(list[0].id);
            try { localStorage.setItem(COMPANY_ID_KEY, list[0].id); } catch {}
          }
        } else if (list.length === 0) {
          setLoading(false);
        }
      } catch (e) {
        if (storedId) setSelectedCompanyId(storedId);
        setLoading(false);
      }
    })();
    // Mount-only auto-select; re-trigger not desired.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  React.useEffect(() => {
    if (!selectedCompanyId) { setLoading(false); return; }
    // Guards the mount-time race with the company-list validation effect above:
    // if that effect corrects `selectedCompanyId` (stale ID -> a valid one)
    // while this invocation's getCompanyGraph(oldId) is still in flight, its
    // eventual 404 must not clear/overwrite the already-corrected selection.
    // React runs this cleanup before starting the next invocation for the new ID.
    let cancelled = false;
    (async () => {
      setLoading(true); setError(null);
      try {
        const { data } = await api.getCompanyGraph(selectedCompanyId);
        if (!mounted.current || cancelled) return;
        setGraph(data.graph || null);
        try { localStorage.setItem(COMPANY_ID_KEY, selectedCompanyId); } catch {}
      } catch (e) {
        if (!mounted.current || cancelled) return;
        // Self-heal on 404 instead of leaving the tab permanently broken: the
        // stored/selected company may have been deleted or the DB reset since
        // this ID was persisted (same class of bug as PR #962 on CompanyScreen).
        if (e?.response?.status === 404) {
          try { localStorage.removeItem(COMPANY_ID_KEY); } catch {}
          try {
            const { data: listData } = await api.listCompanies();
            if (cancelled) return;
            const list = listData.companies || [];
            if (mounted.current) setCompanies(list);
            const replacement = list.find(c => c.id !== selectedCompanyId);
            if (replacement) {
              setSelectedCompanyId(replacement.id);
              try { localStorage.setItem(COMPANY_ID_KEY, replacement.id); } catch {}
              return; // the selectedCompanyId change re-triggers this effect
            }
            // Listing succeeded but found no other company — genuinely empty, not an error.
            if (mounted.current) { setSelectedCompanyId(''); setGraph(null); setLoading(false); }
          } catch (listErr) {
            // The re-list itself failed (network/500/auth expiry) — surface it
            // instead of silently clearing state, so the user isn't left staring
            // at an empty graph with no explanation.
            if (!mounted.current || cancelled) return;
            const detail = listErr?.response?.data?.detail;
            setError(detail ? api.fmtErr(detail) : (listErr?.message || 'Company not found, and the company list could not be refreshed.'));
            setGraph(null);
            setLoading(false);
          }
          return;
        }
        const detail = e?.response?.data?.detail;
        setError(detail ? api.fmtErr(detail) : (e?.message || 'Could not load the company graph.'));
        setGraph(null);
      } finally {
        if (mounted.current && !cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [selectedCompanyId]);

  const { nodes, edges } = React.useMemo(() => buildGraphElements(graph), [graph]);

  if (loading && companies.length === 0) {
    return <div style={{ padding:'18px 0', fontSize:14, color:'var(--text-muted)' }}>Loading your companies…</div>;
  }
  if (companies.length === 0) {
    return <div style={{ padding:'18px 0', fontSize:14, color:'var(--text-muted)' }}>No companies found for your account yet — onboard one from the Company screen.</div>;
  }

  const size = GRAPH_SIZE;
  const center = size / 2;
  const pos = id => {
    const node = nodes.find(n => n.id === id);
    if (!node) return { x: center, y: center };
    if (node.type === 'company') return { x: center, y: center };
    return { x: center + node.radius * Math.cos(node.angle), y: center + node.radius * Math.sin(node.angle) };
  };
  const counts = GRAPH_CATEGORY_ORDER
    .map(type => ({ type, count: nodes.filter(n => n.type === type).length }))
    .filter(c => c.count > 0);

  return (
    <div style={{ animation:'fadeSlideUp 0.3s ease-out' }}>
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', flexWrap:'wrap', gap:10, marginBottom:12 }}>
        {companies.length > 1 ? (
          <select value={selectedCompanyId} onChange={e => setSelectedCompanyId(e.target.value)}
            style={{ padding:'8px 12px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:13, outline:'none' }}>
            {companies.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        ) : (
          <div style={{ fontSize:14, fontWeight:700, color:'var(--text-primary)' }}>{companies[0]?.name}</div>
        )}
        <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
          {counts.map(c => (
            <span key={c.type} style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:GRAPH_NODE_COLORS[c.type], textTransform:'capitalize', padding:'3px 9px', borderRadius:999, background:`color-mix(in oklab, ${GRAPH_NODE_COLORS[c.type]} 8%, transparent)`, border:`1px solid color-mix(in oklab, ${GRAPH_NODE_COLORS[c.type]} 19%, transparent)` }}>
              {c.type}s · {c.count}
            </span>
          ))}
        </div>
      </div>

      {error ? (
        <div style={{ padding:'18px 0', fontSize:14, color:'var(--danger)' }}>Couldn't load the company graph: {error}</div>
      ) : loading ? (
        <div style={{ padding:'18px 0', fontSize:14, color:'var(--text-muted)' }}>Loading company graph…</div>
      ) : nodes.length <= 1 ? (
        <div style={{ padding:'18px 0', fontSize:14, color:'var(--text-muted)' }}>This company's graph is empty so far — run onboarding to detect systems and provision specialists.</div>
      ) : (
        <div style={{ background:'color-mix(in oklab, var(--ink) 2%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)', borderRadius:16, padding:16, display:'flex', justifyContent:'center' }}>
          <svg viewBox={`0 0 ${size} ${size}`} style={{ width:'100%', maxWidth:560, height:'auto' }}>
            {edges.map((e, i) => {
              const a = pos(e.from), b = pos(e.to);
              const active = hoveredId && (e.from === hoveredId || e.to === hoveredId);
              return (
                <line key={i} x1={a.x} y1={a.y} x2={b.x} y2={b.y}
                  stroke={active ? 'color-mix(in oklab, var(--accent) 55%, transparent)' : 'color-mix(in oklab, var(--ink) 10%, transparent)'}
                  strokeWidth={active ? 1.5 : 1} />
              );
            })}
            {nodes.map(n => {
              const p = pos(n.id);
              const r = n.type === 'company' ? 14 : 8;
              const color = GRAPH_NODE_COLORS[n.type] || 'var(--text-muted)';
              return (
                <g key={n.id} onMouseEnter={() => setHoveredId(n.id)} onMouseLeave={() => setHoveredId(null)} style={{ cursor:'pointer' }}>
                  <circle cx={p.x} cy={p.y} r={r} fill={n.type === 'company' ? color : `color-mix(in oklab, ${color} 20%, transparent)`} stroke={color} strokeWidth={1.5} />
                  <title>{n.label}</title>
                  {(n.type === 'company' || hoveredId === n.id) && (
                    <text x={p.x} y={p.y + r + 12} textAnchor="middle" fontSize={10} fontFamily="var(--font-mono)" fill="#fff">
                      {n.label.length > 22 ? `${n.label.slice(0, 20)}…` : n.label}
                    </text>
                  )}
                </g>
              );
            })}
          </svg>
        </div>
      )}
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
  const [showNewDoc, setShowNewDoc] = React.useState(false);
  const [newDocTitle, setNewDocTitle] = React.useState('');
  const [newDocBody,  setNewDocBody]  = React.useState('');
  const [newDocSaving, setNewDocSaving] = React.useState(false);
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
  // Knowledge tab filters to knowledge-relevant events (docs, sources, wiki, intelligence, agent jobs)
  const knowledgeTypes = new Set(['wiki', 'source', 'source_ingest', 'intelligence', 'agent_job', 'task', 'skill', 'github', 'github_connect', 'auth']);
  const activity = activityRaw
    .filter(log => {
      const et = (log.event_type || log.type || '').toLowerCase();
      return !et || knowledgeTypes.has(et) || et.startsWith('wiki') || et.startsWith('source') || et.startsWith('agent');
    })
    .map((log, i) => mapActivity(log, i));

  const docs = pages.map(p => ({
    id: p._id || p.slug,
    title: p.title || p.slug || 'Untitled',
    updated: relTime(p.updated_at || p.created_at),
    tags: Array.isArray(p.tags) ? p.tags : [],
    // The list endpoint omits `content`; word_count is stored on save.
    words: typeof p.word_count === 'number'
      ? p.word_count
      : (typeof p.content === 'string' ? p.content.trim().split(/\s+/).filter(Boolean).length : 0),
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

  const handleCreateDoc = async (e) => {
    e && e.preventDefault();
    if (!newDocTitle.trim()) return;
    setNewDocSaving(true);
    try {
      await api.createWikiPage({
        title: newDocTitle.trim(),
        content: newDocBody,
        slug: newDocTitle.trim().toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
      });
      setShowNewDoc(false); setNewDocTitle(''); setNewDocBody('');
      refetch();
    } catch (err) {
      alert('Could not create doc: ' + (api.fmtErr(err?.response?.data?.detail) || err.message));
    } finally { setNewDocSaving(false); }
  };

  return (
    <div style={{ padding:'20px 16px 48px', maxWidth:1200, margin:'0 auto' }}>
      <div style={{ display:'flex', alignItems:'flex-end', justifyContent:'space-between', flexWrap:'wrap', gap:10, marginBottom:16 }}>
        <div>
          <h1 style={{ fontSize:26, fontWeight:700, color:'var(--text-primary)', letterSpacing:'-0.04em', lineHeight:1.1, marginBottom:4 }}>Knowledge base</h1>
          <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.5, maxWidth:480 }}>Everything agents and humans do is recorded here. Docs, sources, activity, quick notes — one searchable memory.</p>
        </div>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search knowledge…"
          style={{ padding:'9px 14px', borderRadius:12, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:14, outline:'none', fontFamily:'var(--font-main)', minWidth:200 }}
          onFocus={e => e.target.style.borderColor='color-mix(in oklab, var(--accent) 45%, transparent)'} onBlur={e => e.target.style.borderColor='color-mix(in oklab, var(--ink) 10%, transparent)'}/>
      </div>

      {/* Stats row */}
      <div style={{ display:'flex', gap:10, marginBottom:18, flexWrap:'wrap' }}>
        {[
          { label:'Docs', value:docs.length, color:'var(--accent)' },
          { label:'Sources', value:sources.length, color:'var(--violet)' },
          { label:'Processed', value:sources.filter(s=>s.status==='processed').length, color:'var(--success)' },
          { label:'Activity events', value:activity.length, color:'var(--warning)' },
        ].map(s => (
          <div key={s.label} style={{ padding:'8px 14px', borderRadius:12, background:'color-mix(in oklab, var(--ink) 3%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)' }}>
            <div style={{ fontSize:18, fontWeight:700, color:s.color, letterSpacing:'-0.03em' }}>{s.value}</div>
            <div style={{ fontSize:13, color:'var(--text-muted)' }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div style={{ display:'flex', gap:4, marginBottom:16 }}>
        {['activity','docs','sources','graph'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{ padding:'7px 18px', borderRadius:999, fontSize:13, fontWeight:600, cursor:'pointer', textTransform:'capitalize', transition:'all 0.15s', background:tab===t?'color-mix(in oklab, var(--accent) 15%, transparent)':'color-mix(in oklab, var(--ink) 4%, transparent)', border:`1px solid ${tab===t?'color-mix(in oklab, var(--accent) 35%, transparent)':'color-mix(in oklab, var(--ink) 8%, transparent)'}`, color:tab===t?'var(--text-primary)':'var(--text-muted)' }}>{t}</button>
        ))}
      </div>

      {tab === 'activity' && (
        <div style={{ animation:'fadeSlideUp 0.3s ease-out' }}>
          <div style={{ display:'flex', gap:6, marginBottom:12 }}>
            {['all','agent','human','note'].map(f => (
              <button key={f} onClick={() => setActFilter(f)} style={{ padding:'4px 12px', borderRadius:999, fontSize:13, cursor:'pointer', textTransform:'capitalize', background:actFilter===f?'color-mix(in oklab, var(--accent) 12%, transparent)':'color-mix(in oklab, var(--ink) 4%, transparent)', border:`1px solid ${actFilter===f?'color-mix(in oklab, var(--accent) 30%, transparent)':'color-mix(in oklab, var(--ink) 8%, transparent)'}`, color:actFilter===f?'var(--text-primary)':'var(--text-muted)', transition:'all 0.15s' }}>{f}</button>
            ))}
          </div>
          <div style={{ background:'color-mix(in oklab, var(--ink) 2%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)', borderRadius:16, padding:'0 16px' }}>
            {states.activity?.loading && activity.length === 0 ? (
              <div style={{ padding:'18px 0', fontSize:14, color:'var(--text-muted)' }}>Loading activity…</div>
            ) : states.activity?.error ? (
              <div style={{ padding:'18px 0', fontSize:14, color:'var(--danger)' }}>Couldn't load activity: {states.activity.error}</div>
            ) : filteredActivity.length === 0 ? (
              <div style={{ padding:'18px 0', fontSize:14, color:'var(--text-muted)' }}>No activity recorded yet.</div>
            ) : (
              filteredActivity.map(item => <ActivityRow key={item.id} item={item}/>)
            )}
          </div>
        </div>
      )}

      {tab === 'docs' && (
        <div style={{ animation:'fadeSlideUp 0.3s ease-out' }}>
          <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:10 }}>
            <button onClick={() => setShowNewDoc(true)} style={{ padding:'8px 16px', borderRadius:10, fontSize:13, fontWeight:700, cursor:'pointer', background:'color-mix(in oklab, var(--accent) 12%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 25%, transparent)', color:'var(--accent)' }}>+ New doc</button>
          </div>
          {states.pages?.loading && docs.length === 0 ? (
            <div style={{ padding:'18px 0', fontSize:14, color:'var(--text-muted)' }}>Loading docs…</div>
          ) : states.pages?.error ? (
            <div style={{ padding:'18px 0', fontSize:14, color:'var(--danger)' }}>Couldn't load docs: {states.pages.error}</div>
          ) : docs.filter(d => !search || d.title.toLowerCase().includes(search.toLowerCase())).length === 0 ? (
            <div style={{ padding:'18px 0', fontSize:14, color:'var(--text-muted)' }}>No docs yet.</div>
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
            <button onClick={() => setShowAdd(true)} style={{ padding:'8px 16px', borderRadius:10, fontSize:13, fontWeight:700, cursor:'pointer', background:'color-mix(in oklab, var(--accent) 12%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 25%, transparent)', color:'var(--accent)' }}>+ Add source</button>
          </div>
          {showAdd && <AddSourceForm onIngest={handleIngest} onClose={() => setShowAdd(false)}/>}

      {showNewDoc && (
        <div style={{ position:'fixed', inset:0, zIndex:200, background:'color-mix(in oklab, var(--shade) 70%, transparent)', display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}>
          <form onSubmit={handleCreateDoc} style={{ background:'color-mix(in oklab, var(--bg-surface) 98%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 12%, transparent)', borderRadius:14, padding:'28px 24px', width:'100%', maxWidth:480, display:'flex', flexDirection:'column', gap:14 }}>
            <div style={{ fontSize:15, fontWeight:700, color:'var(--text-primary)', marginBottom:4 }}>New document</div>
            <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
              <label style={{ fontSize:13, fontWeight:700, color:'color-mix(in oklab, var(--ink) 50%, transparent)' }}>Title</label>
              <input autoFocus value={newDocTitle} onChange={e => setNewDocTitle(e.target.value)} placeholder="e.g. API Reference" style={{ padding:'10px 14px', borderRadius:10, fontSize:14, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 12%, transparent)', color:'var(--text-primary)', outline:'none' }} />
            </div>
            <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
              <label style={{ fontSize:13, fontWeight:700, color:'color-mix(in oklab, var(--ink) 50%, transparent)' }}>Content (optional)</label>
              <textarea rows={5} value={newDocBody} onChange={e => setNewDocBody(e.target.value)} placeholder="Start writing in Markdown…" style={{ padding:'10px 14px', borderRadius:10, fontSize:14, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 12%, transparent)', color:'var(--text-primary)', outline:'none', resize:'vertical', fontFamily:'var(--font-mono)' }} />
            </div>
            <div style={{ display:'flex', gap:10, justifyContent:'flex-end', marginTop:4 }}>
              <button type="button" onClick={() => { setShowNewDoc(false); setNewDocTitle(''); setNewDocBody(''); }} style={{ padding:'9px 18px', borderRadius:10, fontSize:14, fontWeight:700, background:'color-mix(in oklab, var(--ink) 6%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-secondary)', cursor:'pointer' }}>Cancel</button>
              <button type="submit" disabled={!newDocTitle.trim() || newDocSaving} style={{ padding:'9px 18px', borderRadius:10, fontSize:14, fontWeight:700, background:newDocTitle.trim() && !newDocSaving ? 'linear-gradient(135deg,var(--accent),var(--accent))' : 'color-mix(in oklab, var(--accent) 20%, transparent)', border:'none', color:'var(--text-primary)', cursor: newDocTitle.trim() && !newDocSaving ? 'pointer' : 'not-allowed' }}>
                {newDocSaving ? 'Saving…' : 'Create doc'}
              </button>
            </div>
          </form>
        </div>
      )}
          {actionErr && <div style={{ marginBottom:10, padding:'8px 12px', borderRadius:10, background:'color-mix(in oklab, var(--danger) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 25%, transparent)', color:'var(--danger)', fontSize:13 }}>{actionErr}</div>}
          {states.sources?.loading && sources.length === 0 ? (
            <div style={{ padding:'18px 0', fontSize:14, color:'var(--text-muted)' }}>Loading sources…</div>
          ) : states.sources?.error ? (
            <div style={{ padding:'18px 0', fontSize:14, color:'var(--danger)' }}>Couldn't load sources: {states.sources.error}</div>
          ) : sources.length === 0 ? (
            <div style={{ padding:'18px 0', fontSize:14, color:'var(--text-muted)' }}>No sources yet. Add a URL, text, or file above to index it.</div>
          ) : (
            <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
              {sources.map(s => <SourceRow key={s._id || s.id} source={s} onRemove={handleRemove} busy={removingId===(s._id||s.id)}/>)}
            </div>
          )}
        </div>
      )}

      {tab === 'graph' && <CompanyGraphPanel/>}
    </div>
  );
}

export { KnowledgeScreen, buildGraphElements, GRAPH_SIZE };
export default KnowledgeScreen;
