/* eslint-disable jsx-a11y/anchor-is-valid */
import React from 'react';
import { Icon } from '../AppShell';
import * as api from '../../api';

const POLL_MS = 30_000; // refresh every 30 seconds

const priorityConfig = {
  P1: { color:'var(--danger)', bg:'color-mix(in oklab, var(--danger) 10%, transparent)', border:'color-mix(in oklab, var(--danger) 25%, transparent)', icon:'🔴', label:'Critical' },
  P2: { color:'var(--warning)', bg:'color-mix(in oklab, var(--warning) 10%, transparent)', border:'color-mix(in oklab, var(--warning) 22%, transparent)', icon:'🟡', label:'High' },
  P3: { color:'var(--accent)', bg:'color-mix(in oklab, var(--accent) 8%, transparent)',  border:'color-mix(in oklab, var(--accent) 18%, transparent)',  icon:'🔵', label:'Info' },
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
      background: alert.read ? 'color-mix(in oklab, var(--ink) 2%, transparent)' : pc.bg,
      border:`1px solid ${alert.read ? 'color-mix(in oklab, var(--ink) 7%, transparent)' : pc.border}`,
      transition:'all 0.2s ease', cursor:'pointer',
    }}
    onClick={() => onRead(alert.id)}>
      <div style={{ display:'flex', alignItems:'flex-start', gap:9, marginBottom:6 }}>
        <span style={{ fontSize:14, flexShrink:0, marginTop:1 }}>{typeIcon[alert.type] || '◎'}</span>
        <div style={{ flex:1, minWidth:0 }}>
          <div style={{ display:'flex', alignItems:'center', gap:6, marginBottom:3, flexWrap:'wrap' }}>
            <span style={{ fontSize:14, fontWeight:700, color:alert.read?'var(--text-secondary)':'var(--text-primary)' }}>{alert.title}</span>
            <span style={{
              fontSize:13, fontVariantNumeric:'tabular-nums',
              padding:'1px 6px', borderRadius:999,
              color: pc.color, background:`color-mix(in oklab, ${pc.color} 8%, transparent)`, border:`1px solid color-mix(in oklab, ${pc.color} 16%, transparent)`,
            }}>{alert.priority}</span>
            {!alert.read && <span style={{ width:6, height:6, borderRadius:'50%', background:pc.color, display:'inline-block' }}/>}
          </div>
          <div style={{ fontSize:13, color:'var(--text-muted)', lineHeight:1.5 }}>{alert.body}</div>
        </div>
        <div style={{ display:'flex', flexDirection:'column', alignItems:'flex-end', gap:4, flexShrink:0 }}>
          <span style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--text-muted)' }}>{alert.ts}</span>
          <button onClick={e => { e.stopPropagation(); onDismiss(alert.id); }} style={{
            width:20, height:20, borderRadius:6, display:'flex', alignItems:'center', justifyContent:'center',
            background:'transparent', border:'none', cursor:'pointer', fontSize:13, color:'var(--text-muted)',
          }}
          onMouseEnter={e => { e.currentTarget.style.background='color-mix(in oklab, var(--danger) 12%, transparent)'; e.currentTarget.style.color='#ff6b7d'; }}
          onMouseLeave={e => { e.currentTarget.style.background='transparent'; e.currentTarget.style.color='var(--text-muted)'; }}>✕</button>
        </div>
      </div>
      {alert.action && (
        <button onClick={e => { e.stopPropagation(); onAction(alert); }} style={{
          marginTop:4, padding:'5px 12px', borderRadius:8, fontSize:13, fontWeight:700, cursor:'pointer',
          background:`color-mix(in oklab, ${pc.color} 8%, transparent)`, border:`1px solid color-mix(in oklab, ${pc.color} 15%, transparent)`, color:pc.color,
        }}
        onMouseEnter={e => e.currentTarget.style.background=`color-mix(in oklab, ${pc.color} 15%, transparent)`}
        onMouseLeave={e => e.currentTarget.style.background=`color-mix(in oklab, ${pc.color} 8%, transparent)`}>
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
      {open && <div style={{ position:'fixed', inset:0, zIndex:'calc(var(--z-modal) - 1)' }} onClick={() => setOpen(false)}/>}
      <button type="button" className="shell-icon-btn" onClick={() => setOpen(o => !o)}
        aria-expanded={open} aria-haspopup="dialog"
        aria-label={unreadCount > 0 ? `Alerts, ${unreadCount} unread` : 'Alerts'} title="Alerts">
        <Icon name="Bell" size={20}/>
        {unreadCount > 0 && (
          <span className={`shell-badge ${p1Count > 0 ? 'is-urgent' : ''}`} aria-hidden="true">{unreadCount > 9 ? '9+' : unreadCount}</span>
        )}
      </button>

      {open && (
        <div className="shell-popover" role="dialog" aria-label="Alerts">
          <div className="shell-popover-head">
            <span className="shell-popover-title">
              Alerts{unreadCount > 0 && <span style={{ fontWeight:500, color:'var(--text-muted)' }}> · {unreadCount} unread</span>}
            </span>
            <div style={{ display:'flex', alignItems:'center', gap:4 }}>
              {unreadCount > 0 && (
                <button type="button" className="app-button-ghost" style={{ minHeight:36, padding:'6px 10px', fontSize:14 }} onClick={markAllRead}>Mark all read</button>
              )}
              <button type="button" className="shell-icon-btn" aria-label="Close alerts" onClick={() => setOpen(false)}>
                <Icon name="X" size={18}/>
              </button>
            </div>
          </div>
          <div style={{ flex:1, overflowY:'auto', padding:'10px 12px', display:'flex', flexDirection:'column', gap:8 }} className="scrollbar-hide">
            {alerts.length === 0 ? (
              <div style={{ padding:'32px', textAlign:'center', color:'var(--text-muted)', fontSize:14 }}>All clear. Nothing needs you right now.</div>
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
