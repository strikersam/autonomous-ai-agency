/* eslint-disable jsx-a11y/anchor-is-valid */
import React from 'react';
import * as api from '../../api';

const POLL_MS = 30_000; // refresh every 30 seconds

const priorityConfig = {
  P1: { color:'#ff6b7d', bg:'rgba(255,107,125,0.10)', border:'rgba(255,107,125,0.25)', icon:'🔴', label:'Critical' },
  P2: { color:'#ffbd66', bg:'rgba(255,189,102,0.10)', border:'rgba(255,189,102,0.22)', icon:'🟡', label:'High' },
  P3: { color:'#5da2ff', bg:'rgba(93,162,255,0.08)',  border:'rgba(93,162,255,0.18)',  icon:'🔵', label:'Info' },
};

const typeIcon = { ci:'⚙', security:'🔒', approval:'◈', infra:'◎', note:'📝', task:'✓', agent:'🤖', error:'⚠' };

/** Map a raw activity record from /api/activity to our alert shape */
function activityToAlert(item) {
  const id = item.id || item._id || String(Math.random());
  const ts  = item.created_at || item.timestamp || '';
  const age = ts ? _relativeTime(ts) : '';

  // Determine priority from severity / type
  let priority = 'P3';
  const kind = (item.type || item.category || '').toLowerCase();
  if (item.severity === 'error' || kind === 'error' || kind === 'ci' || kind === 'security') priority = 'P1';
  else if (item.severity === 'warning' || kind === 'approval') priority = 'P2';

  return {
    id,
    priority,
    title: item.title || item.action || item.type || 'Activity',
    body:  item.description || item.detail || item.message || '',
    type:  kind || 'note',
    ts:    age,
    read:  false,
    action: item.screen ? { label: 'View', screen: item.screen } : null,
    _raw:  item,
  };
}

function _relativeTime(iso) {
  const diff = Date.now() - new Date(iso).getTime();
  if (diff < 60_000)  return `${Math.round(diff / 1000)}s ago`;
  if (diff < 3600_000) return `${Math.round(diff / 60_000)}m ago`;
  if (diff < 86400_000) return `${Math.round(diff / 3600_000)}h ago`;
  return `${Math.round(diff / 86400_000)}d ago`;
}

function AlertItem({ alert, onRead, onDismiss, onAction }) {
  const pc = priorityConfig[alert.priority] || priorityConfig.P3;
  return (
    <div style={{
      padding:'12px 14px', borderRadius:14,
      background: alert.read ? 'rgba(255,255,255,0.02)' : pc.bg,
      border:`1px solid ${alert.read ? 'rgba(255,255,255,0.07)' : pc.border}`,
      transition:'all 0.2s ease', cursor:'pointer',
    }}
    onClick={() => onRead(alert.id)}>
      <div style={{ display:'flex', alignItems:'flex-start', gap:9, marginBottom:6 }}>
        <span style={{ fontSize:13, flexShrink:0, marginTop:1 }}>{typeIcon[alert.type] || '◎'}</span>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:3, flexWrap:'wrap' }}>
            <span style={{ fontSize:13, fontWeight:700, color:alert.read?'var(--text-secondary)':'#fff' }}>{alert.title}</span>
            <span style={{
              fontSize:9, fontFamily:'var(--font-mono)', letterSpacing:'0.10em', textTransform:'uppercase',
              padding:'1px 6px', borderRadius:999,
              color: pc.color, background:`${pc.color}15`, border:`1px solid ${pc.color}28`,
            }}>{alert.priority}</span>
            {!alert.read && <span style={{ width:6, height:6, borderRadius:'50%', background:pc.color, display:'inline-block' }}/>}
          </div>
          <div style={{ fontSize:12, color:'var(--text-muted)', lineHeight:1.5 }}>{alert.body}</div>
        </div>
        <div style={{ display:'flex', flexDirection:'column', alignItems:'flex-end', gap:4, flexShrink:0 }}>
          <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{alert.ts}</span>
          <button onClick={e => { e.stopPropagation(); onDismiss(alert.id); }} style={{
            width:20, height:20, borderRadius:6, display:'flex', alignItems:'center', justifyContent:'center',
            background:'transparent', border:'none', cursor:'pointer', fontSize:10, color:'var(--text-muted)',
          }}
          onMouseEnter={e => { e.currentTarget.style.background='rgba(255,107,125,0.12)'; e.currentTarget.style.color='#ff6b7d'; }}
          onMouseLeave={e => { e.currentTarget.style.background='transparent'; e.currentTarget.style.color='var(--text-muted)'; }}>✕</button>
        </div>
      </div>
      {alert.action && (
        <button onClick={e => { e.stopPropagation(); onAction(alert); }} style={{
          marginTop:4, padding:'5px 12px', borderRadius:8, fontSize:11, fontWeight:700, cursor:'pointer',
          background:`${pc.color}15`, border:`1px solid ${pc.color}25`, color:pc.color,
        }}
        onMouseEnter={e => e.currentTarget.style.background=`${pc.color}25`}
        onMouseLeave={e => e.currentTarget.style.background=`${pc.color}15`}>
          → {alert.action.label}
        </button>
      )}
    </div>
  );
}

function AlertsBell({ onNavigate }) {
  const [open, setOpen]         = React.useState(false);
  const [alerts, setAlerts]     = React.useState([]);
  const [dismissed, setDismissed] = React.useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem('dismissed_alerts') || '[]')); }
    catch { return new Set(); }
  });
  const [readIds, setReadIds]   = React.useState(() => {
    try { return new Set(JSON.parse(localStorage.getItem('read_alerts') || '[]')); }
    catch { return new Set(); }
  });

  const fetchAlerts = React.useCallback(async () => {
    try {
      const { data } = await api.getActivity(30);
      const raw = Array.isArray(data) ? data : (data?.items || data?.activities || []);
      const mapped = raw
        .map(activityToAlert)
        .filter(a => !dismissed.has(a.id))
        .map(a => ({ ...a, read: readIds.has(a.id) }));
      setAlerts(mapped);
    } catch {
      // Silently fail — don't break the UI if activity is unavailable
    }
  }, [dismissed, readIds]);

  React.useEffect(() => {
    fetchAlerts();
    const timer = setInterval(fetchAlerts, POLL_MS);
    return () => clearInterval(timer);
  }, [fetchAlerts]);

  const unreadCount = alerts.filter(a => !a.read).length;
  const p1Count     = alerts.filter(a => a.priority === 'P1' && !a.read).length;

  const markRead = (id) => {
    const next = new Set([...readIds, id]);
    setReadIds(next);
    localStorage.setItem('read_alerts', JSON.stringify([...next]));
    setAlerts(p => p.map(a => a.id === id ? { ...a, read: true } : a));
  };

  const dismiss = (id) => {
    const next = new Set([...dismissed, id]);
    setDismissed(next);
    localStorage.setItem('dismissed_alerts', JSON.stringify([...next]));
    setAlerts(p => p.filter(a => a.id !== id));
  };

  const markAllRead = () => {
    const ids = alerts.map(a => a.id);
    const next = new Set([...readIds, ...ids]);
    setReadIds(next);
    localStorage.setItem('read_alerts', JSON.stringify([...next]));
    setAlerts(p => p.map(a => ({ ...a, read: true })));
  };

  const handleAction = (alert) => {
    markRead(alert.id);
    setOpen(false);
    onNavigate && onNavigate(alert.action.screen);
  };

  return (
    <>
      {open && <div style={{ position:'fixed', inset:0, zIndex:149 }} onClick={() => setOpen(false)}/>}
      <button onClick={() => setOpen(o => !o)} style={{
        position:'fixed', top:14, right:16, zIndex:150,
        width:38, height:38, borderRadius:12,
        background: p1Count>0 ? 'rgba(255,107,125,0.12)' : 'rgba(14,17,22,0.88)',
        border:`1px solid ${p1Count>0 ? 'rgba(255,107,125,0.35)' : 'rgba(255,255,255,0.12)'}`,
        boxShadow:'0 4px 16px rgba(0,0,0,0.35)', backdropFilter:'blur(12px)',
        display:'flex', alignItems:'center', justifyContent:'center',
        cursor:'pointer', transition:'all 0.2s ease',
      }} title="Alerts">
        <span style={{ fontSize:15 }}>🔔</span>
        {unreadCount > 0 && (
          <span style={{
            position:'absolute', top:-4, right:-4,
            width:16, height:16, borderRadius:'50%',
            background: p1Count>0 ? '#ff6b7d' : 'var(--accent)',
            fontSize:9, fontFamily:'var(--font-mono)', fontWeight:800, color:'#fff',
            display:'flex', alignItems:'center', justifyContent:'center',
            boxShadow:'0 2px 6px rgba(0,0,0,0.4)',
          }}>{unreadCount > 9 ? '9+' : unreadCount}</span>
        )}
      </button>

      {open && (
        <div style={{
          position:'fixed', top:60, right:16, zIndex:151,
          width:'min(380px, calc(100vw - 32px))',
          background:'rgba(10,13,18,0.97)',
          border:'1px solid rgba(255,255,255,0.12)',
          borderRadius:20, overflow:'hidden',
          boxShadow:'0 24px 60px rgba(0,0,0,0.55)',
          backdropFilter:'blur(20px)',
          maxHeight:'80vh', display:'flex', flexDirection:'column',
        }}>
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', padding:'14px 16px 12px', borderBottom:'1px solid rgba(255,255,255,0.08)', flexShrink:0 }}>
            <div style={{ display:'flex', alignItems:'center', gap:8 }}>
              <span style={{ fontSize:14 }}>🔔</span>
              <span style={{ fontSize:13, fontWeight:700, color:'#fff' }}>Alerts</span>
              {unreadCount > 0 && (
                <span style={{ fontSize:10, fontFamily:'var(--font-mono)', padding:'2px 7px', borderRadius:999, background:'rgba(93,162,255,0.15)', color:'var(--accent)', border:'1px solid rgba(93,162,255,0.25)' }}>
                  {unreadCount} unread
                </span>
              )}
            </div>
            <div style={{ display:'flex', gap:8 }}>
              {unreadCount > 0 && (
                <button onClick={markAllRead} style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', background:'none', border:'none', cursor:'pointer' }}
                onMouseEnter={e => e.currentTarget.style.color='var(--accent)'}
                onMouseLeave={e => e.currentTarget.style.color='var(--text-muted)'}>Mark all read</button>
              )}
              <button onClick={() => setOpen(false)} style={{ width:24, height:24, borderRadius:6, display:'flex', alignItems:'center', justifyContent:'center', background:'rgba(255,255,255,0.06)', border:'none', cursor:'pointer', color:'var(--text-muted)', fontSize:12 }}>✕</button>
            </div>
          </div>
          <div style={{ flex:1, overflowY:'auto', padding:'10px 12px', display:'flex', flexDirection:'column', gap:8 }} className="scrollbar-hide">
            {alerts.length === 0 ? (
              <div style={{ padding:'32px', textAlign:'center', color:'var(--text-muted)', fontSize:13 }}>All clear — no active alerts.</div>
            ) : (
              alerts.map(alert => (
                <AlertItem key={alert.id} alert={alert} onRead={markRead} onDismiss={dismiss} onAction={handleAction}/>
              ))
            )}
          </div>
        </div>
      )}
    </>
  );
}

export { AlertsBell };
export default AlertsBell;
