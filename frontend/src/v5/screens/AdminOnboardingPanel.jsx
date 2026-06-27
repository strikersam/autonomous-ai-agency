/* eslint-disable no-unused-vars */
/**
 * AdminOnboardingPanel.jsx — Admin panel sections for:
 *   1. Instance activation status + re-activation
 *   2. Per-user onboarding_allowed toggle
 *   3. Activation audit log
 *
 * Embedded inside AdminScreen.jsx as collapsible sections.
 */
import React from 'react';
import api from '../../api';

function Badge({ children, color }) {
  const bg = color === 'green' ? 'rgba(70,217,164,0.10)' : color === 'red' ? 'rgba(255,107,125,0.10)' : 'rgba(255,255,255,0.06)';
  const border = color === 'green' ? 'rgba(70,217,164,0.28)' : color === 'red' ? 'rgba(255,107,125,0.28)' : 'rgba(255,255,255,0.12)';
  const text = color === 'green' ? '#46d9a4' : color === 'red' ? '#ff8a97' : 'rgba(255,255,255,0.45)';
  return (
    <span style={{ padding:'2px 9px', borderRadius:999, background:bg, border:`1px solid ${border}`, color:text, fontSize:11, fontFamily:'var(--font-mono, monospace)', fontWeight:600 }}>
      {children}
    </span>
  );
}

function SectionCard({ title, icon, children, defaultOpen = true }) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <div style={{ background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.08)', borderRadius:16, marginBottom:16, overflow:'hidden' }}>
      <button onClick={() => setOpen(v => !v)} style={{ width:'100%', display:'flex', alignItems:'center', gap:10, padding:'14px 18px', background:'none', border:'none', cursor:'pointer', textAlign:'left' }}>
        <span style={{ fontSize:16 }}>{icon}</span>
        <span style={{ flex:1, fontSize:14, fontWeight:700, color:'#fff' }}>{title}</span>
        <span style={{ fontSize:12, color:'rgba(255,255,255,0.30)', fontFamily:'var(--font-mono, monospace)' }}>{open ? '▲' : '▼'}</span>
      </button>
      {open && <div style={{ padding:'4px 18px 18px' }}>{children}</div>}
    </div>
  );
}

// ── 1. Activation status ─────────────────────────────────────────────────────
function ActivationStatus() {
  const [status,  setStatus]  = React.useState(null);
  const [token,   setToken]   = React.useState('');
  const [loading, setLoading] = React.useState(false);
  const [msg,     setMsg]     = React.useState('');
  const [err,     setErr]     = React.useState('');
  const [loadErr, setLoadErr] = React.useState('');

  const load = () => {
    setLoadErr('');
    api.get('/api/activation/status')
      .then(r => setStatus(r.data))
      .catch(e => setLoadErr(e.response?.data?.detail || 'Unable to load activation status.'));
  };
  React.useEffect(load, []);

  const reActivate = async () => {
    if (!token.trim()) return;
    setLoading(true); setMsg(''); setErr('');
    try {
      const r = await api.post('/api/activation/activate', { token: token.trim() });
      if (r.data.success) { setMsg(`Activated for ${r.data.email}`); setToken(''); load(); }
      else setErr(r.data.error || 'Activation failed');
    } catch (e) { setErr(e.response?.data?.detail || 'Error'); }
    finally { setLoading(false); }
  };

  if (!status) {
    if (loadErr) return (
      <div style={{ fontSize:13, color:'#ff8a97', padding:'8px 0' }}>
        ⚠ {loadErr}{' '}
        <button onClick={load} style={{ marginLeft:8, padding:'2px 10px', borderRadius:7, background:'rgba(93,162,255,0.10)', border:'1px solid rgba(93,162,255,0.25)', color:'#6CB0FF', fontSize:12, cursor:'pointer' }}>Retry</button>
      </div>
    );
    return <div style={{ fontSize:13, color:'rgba(255,255,255,0.30)', padding:'8px 0' }}>Loading…</div>;
  }

  return (
    <div>
      {/* Current status */}
      <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:14, padding:'12px 14px', borderRadius:12, background: status.activated ? 'rgba(70,217,164,0.05)' : 'rgba(255,107,125,0.05)', border:`1px solid ${status.activated ? 'rgba(70,217,164,0.18)' : 'rgba(255,107,125,0.18)'}` }}>
        <span style={{ fontSize:18 }}>{status.activated ? '✅' : '🔴'}</span>
        <div style={{ flex:1 }}>
          <div style={{ fontSize:13, fontWeight:700, color: status.activated ? '#46d9a4' : '#ff8a97', marginBottom:2 }}>
            {status.activated ? `Activated — ${status.email}` : 'Not activated'}
          </div>
          {status.activated && status.issued_at && (
            <div style={{ fontSize:11, color:'rgba(255,255,255,0.35)', fontFamily:'var(--font-mono, monospace)' }}>
              Issued {new Date(status.issued_at * 1000).toLocaleDateString()}
              {status.expires_at ? ` · Expires ${new Date(status.expires_at * 1000).toLocaleDateString()}` : ' · No expiry'}
            </div>
          )}
          {!status.activated && (
            <div style={{ fontSize:11, color:'rgba(255,255,255,0.35)', fontFamily:'var(--font-mono, monospace)' }}>
              Onboarding locked until activated. Email {status.register_email} with the Instance ID below.
            </div>
          )}
        </div>
      </div>

      {/* Instance ID */}
      <div style={{ marginBottom:14 }}>
        <div style={{ fontSize:11, color:'rgba(255,255,255,0.35)', fontFamily:'var(--font-mono, monospace)', marginBottom:5 }}>INSTANCE ID</div>
        <div style={{ display:'flex', gap:8, alignItems:'center', padding:'9px 12px', borderRadius:10, background:'rgba(0,0,0,0.20)', border:'1px solid rgba(255,255,255,0.08)' }}>
          <code style={{ flex:1, fontSize:12, fontFamily:'var(--font-mono, monospace)', color:'#a0b4d0', wordBreak:'break-all' }}>{status.instance_id}</code>
          <button onClick={() => navigator.clipboard?.writeText(status.instance_id)}
            style={{ padding:'4px 10px', borderRadius:7, background:'rgba(93,162,255,0.10)', border:'1px solid rgba(93,162,255,0.25)', color:'#6CB0FF', fontSize:11, cursor:'pointer', flexShrink:0, fontFamily:'var(--font-mono, monospace)' }}>
            Copy
          </button>
        </div>
      </div>

      {/* Re-activate */}
      <div style={{ fontSize:12, fontWeight:600, color:'rgba(255,255,255,0.45)', marginBottom:7 }}>
        {status.activated ? 'Replace activation token' : 'Enter activation token'}
      </div>
      <div style={{ display:'flex', gap:8 }}>
        <input value={token} onChange={e => setToken(e.target.value)} placeholder="Paste activation token…"
          style={{ flex:1, padding:'9px 12px', borderRadius:10, background:'rgba(0,0,0,0.20)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:12, fontFamily:'var(--font-mono, monospace)', outline:'none' }}/>
        <button onClick={reActivate} disabled={loading || !token.trim()}
          style={{ padding:'9px 18px', borderRadius:10, background:'rgba(93,162,255,0.15)', border:'1px solid rgba(93,162,255,0.30)', color:'#6CB0FF', fontSize:13, fontWeight:700, cursor:'pointer', flexShrink:0, opacity: !token.trim() ? 0.45 : 1 }}>
          {loading ? '…' : 'Activate'}
        </button>
      </div>
      {msg && <div style={{ fontSize:12, color:'#46d9a4', marginTop:8, fontFamily:'var(--font-mono, monospace)' }}>✓ {msg}</div>}
      {err && <div style={{ fontSize:12, color:'#ff8a97', marginTop:8, fontFamily:'var(--font-mono, monospace)' }}>⚠ {err}</div>}
    </div>
  );
}

// ── 2. Per-user onboarding toggle ────────────────────────────────────────────
function UserOnboardingTable() {
  const [users,   setUsers]   = React.useState([]);
  const [newUid,  setNewUid]  = React.useState('');
  const [loading, setLoading] = React.useState({});
  const [status,  setStatus]  = React.useState(null);
  const [loadErr, setLoadErr] = React.useState('');

  const loadStatus = () => api.get('/api/activation/status').then(r => setStatus(r.data))
    .catch(e => setLoadErr(e.response?.data?.detail || 'Unable to load activation status.'));
  const loadUsers  = () => api.get('/api/activation/users').then(r => setUsers(r.data || []))
    .catch(e => setLoadErr(e.response?.data?.detail || 'Unable to load users.'));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const reload = React.useCallback(() => { setLoadErr(''); loadStatus(); loadUsers(); }, []);
  React.useEffect(() => { reload(); }, [reload]);

  const toggle = async (userId, allowed) => {
    setLoading(p => ({ ...p, [userId]: true }));
    try {
      await api.put(`/api/activation/users/${encodeURIComponent(userId)}/onboarding`, { allowed });
      setUsers(u => u.map(x => x.user_id === userId ? { ...x, onboarding_allowed: allowed } : x));
    } catch(e) { alert(e.response?.data?.detail || 'Error'); }
    finally { setLoading(p => ({ ...p, [userId]: false })); }
  };

  const addUser = async () => {
    if (!newUid.trim()) return;
    await toggle(newUid.trim(), false);
    setNewUid('');
    loadUsers();
  };

  const activated = status?.activated;

  if (loadErr) {
    return (
      <div style={{ padding:'12px 14px', borderRadius:12, background:'rgba(255,107,125,0.06)', border:'1px solid rgba(255,107,125,0.18)', fontSize:13, color:'#ff8a97' }}>
        ⚠ {loadErr}{' '}
        <button onClick={reload} style={{ marginLeft:8, padding:'2px 10px', borderRadius:7, background:'rgba(93,162,255,0.10)', border:'1px solid rgba(93,162,255,0.25)', color:'#6CB0FF', fontSize:12, cursor:'pointer' }}>Retry</button>
      </div>
    );
  }

  if (!activated) {
    return (
      <div style={{ padding:'12px 14px', borderRadius:12, background:'rgba(255,189,102,0.06)', border:'1px solid rgba(255,189,102,0.18)', fontSize:13, color:'#ffbd66' }}>
        ⚠ Instance must be activated before you can manage user onboarding.
      </div>
    );
  }

  return (
    <div>
      <p style={{ fontSize:13, color:'rgba(255,255,255,0.45)', lineHeight:1.6, marginBottom:14 }}>
        Toggle onboarding access per user. Users must be listed here and set to <Badge color="green">Allowed</Badge> before they can complete the setup wizard.
      </p>

      {/* Table */}
      {users.length === 0 ? (
        <div style={{ fontSize:13, color:'rgba(255,255,255,0.30)', padding:'14px 0' }}>No users added yet. Add a user ID below.</div>
      ) : (
        <div style={{ borderRadius:12, border:'1px solid rgba(255,255,255,0.08)', overflow:'hidden', marginBottom:16 }}>
          <div style={{ overflowX:'auto' }}>
          <table style={{ width:'100%', borderCollapse:'collapse' }}>
            <thead>
              <tr style={{ background:'rgba(255,255,255,0.03)' }}>
                {['User ID', 'Onboarding', 'Updated', 'By', 'Action'].map(h => (
                  <th key={h} style={{ padding:'9px 14px', textAlign:'left', fontSize:11, fontFamily:'var(--font-mono, monospace)', color:'rgba(255,255,255,0.35)', letterSpacing:'0.1em', textTransform:'uppercase', fontWeight:600 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((u, i) => (
                <tr key={u.user_id} style={{ borderTop:'1px solid rgba(255,255,255,0.05)', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                  <td style={{ padding:'10px 14px', fontSize:13, fontFamily:'var(--font-mono, monospace)', color:'#a0b4d0', maxWidth:180, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{u.user_id}</td>
                  <td style={{ padding:'10px 14px' }}><Badge color={u.onboarding_allowed ? 'green' : 'red'}>{u.onboarding_allowed ? 'Allowed' : 'Blocked'}</Badge></td>
                  <td style={{ padding:'10px 14px', fontSize:11, color:'rgba(255,255,255,0.30)', fontFamily:'var(--font-mono, monospace)' }}>{u.updated_at ? new Date(u.updated_at * 1000).toLocaleString() : '—'}</td>
                  <td style={{ padding:'10px 14px', fontSize:11, color:'rgba(255,255,255,0.30)', fontFamily:'var(--font-mono, monospace)' }}>{u.updated_by || '—'}</td>
                  <td style={{ padding:'10px 14px' }}>
                    <button onClick={() => toggle(u.user_id, !u.onboarding_allowed)} disabled={!!loading[u.user_id]}
                      style={{ padding:'5px 12px', borderRadius:8, background: u.onboarding_allowed ? 'rgba(255,107,125,0.10)' : 'rgba(70,217,164,0.10)', border:`1px solid ${u.onboarding_allowed ? 'rgba(255,107,125,0.25)' : 'rgba(70,217,164,0.25)'}`, color: u.onboarding_allowed ? '#ff8a97' : '#46d9a4', fontSize:12, fontWeight:600, cursor:'pointer', opacity: loading[u.user_id] ? 0.5 : 1, fontFamily:'var(--font-mono, monospace)' }}>
                      {loading[u.user_id] ? '…' : u.onboarding_allowed ? 'Revoke' : 'Allow'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      )}

      {/* Add user */}
      <div style={{ display:'flex', gap:8 }}>
        <input value={newUid} onChange={e => setNewUid(e.target.value)} placeholder="User ID or email to add…"
          onKeyDown={e => e.key === 'Enter' && addUser()}
          style={{ flex:1, padding:'9px 12px', borderRadius:10, background:'rgba(0,0,0,0.20)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, fontFamily:'var(--font-mono, monospace)', outline:'none' }}/>
        <button onClick={addUser} disabled={!newUid.trim()}
          style={{ padding:'9px 18px', borderRadius:10, background:'rgba(93,162,255,0.12)', border:'1px solid rgba(93,162,255,0.28)', color:'#6CB0FF', fontSize:13, fontWeight:700, cursor:'pointer', flexShrink:0, opacity: !newUid.trim() ? 0.45 : 1 }}>
          + Add user
        </button>
      </div>
    </div>
  );
}

// ── 2b. Global onboarding-gate default ───────────────────────────────────────
function OnboardingGateSettings() {
  const [settings, setSettings] = React.useState(null);
  const [ttlInput, setTtlInput] = React.useState('');
  const [saving,   setSaving]   = React.useState(false);
  const [msg,      setMsg]      = React.useState('');
  const [err,      setErr]      = React.useState('');
  const [loadErr,  setLoadErr]  = React.useState('');

  const load = () => {
    setLoadErr('');
    api.get('/api/activation/settings')
      .then(r => { setSettings(r.data); setTtlInput(String(r.data.ephemeral_company_ttl_hours)); })
      .catch(e => setLoadErr(e.response?.data?.detail || 'Unable to load settings.'));
  };
  React.useEffect(load, []);

  const save = async (patch) => {
    setSaving(true); setMsg(''); setErr('');
    try {
      const r = await api.put('/api/activation/settings', patch);
      setSettings(r.data);
      // Resync the controlled TTL field to the persisted value so a rejected or
      // failed edit can't leave the box showing a value that isn't saved.
      setTtlInput(String(r.data.ephemeral_company_ttl_hours));
      setMsg('Saved');
      setTimeout(() => setMsg(''), 2500);
    } catch (e) {
      setErr(e.response?.data?.detail || 'Error');
      // On failure, snap the field back to the last known persisted value.
      if (settings) setTtlInput(String(settings.ephemeral_company_ttl_hours));
    }
    finally { setSaving(false); }
  };

  if (loadErr) return (
    <div style={{ fontSize:13, color:'#ff8a97', padding:'8px 0' }}>
      ⚠ {loadErr}{' '}
      <button onClick={load} style={{ marginLeft:8, padding:'2px 10px', borderRadius:7, background:'rgba(93,162,255,0.10)', border:'1px solid rgba(93,162,255,0.25)', color:'#6CB0FF', fontSize:12, cursor:'pointer' }}>Retry</button>
    </div>
  );
  if (!settings) return <div style={{ fontSize:13, color:'rgba(255,255,255,0.30)', padding:'8px 0' }}>Loading…</div>;

  const gateOff = settings.onboarding_gate_enabled === false;

  return (
    <div>
      <p style={{ fontSize:13, color:'rgba(255,255,255,0.45)', lineHeight:1.6, marginBottom:14 }}>
        Turn the gate <Badge color="red">off</Badge> to let <strong>every</strong> logged-in user run the
        setup wizard by default — no per-user allow-list entry needed. Keep it
        <Badge color="green">on</Badge> to require explicit approval per user (the table above).
      </p>

      {/* Gate toggle */}
      <div style={{ display:'flex', alignItems:'center', gap:12, padding:'12px 14px', borderRadius:12, background:'rgba(0,0,0,0.20)', border:'1px solid rgba(255,255,255,0.08)', marginBottom:12 }}>
        <div style={{ flex:1 }}>
          <div style={{ fontSize:13, fontWeight:700, color:'#fff' }}>Onboarding gate</div>
          <div style={{ fontSize:11, color:'rgba(255,255,255,0.40)', fontFamily:'var(--font-mono, monospace)', marginTop:2 }}>
            {gateOff ? 'OFF — all users may onboard by default' : 'ON — per-user approval required'}
          </div>
        </div>
        <button onClick={() => save({ onboarding_gate_enabled: gateOff })} disabled={saving}
          style={{ padding:'7px 16px', borderRadius:9, background: gateOff ? 'rgba(70,217,164,0.10)' : 'rgba(255,107,125,0.10)', border:`1px solid ${gateOff ? 'rgba(70,217,164,0.28)' : 'rgba(255,107,125,0.28)'}`, color: gateOff ? '#46d9a4' : '#ff8a97', fontSize:13, fontWeight:700, cursor:'pointer', opacity: saving ? 0.5 : 1 }}>
          {saving ? '…' : gateOff ? 'Enable gate' : 'Disable gate'}
        </button>
      </div>

      {/* Ephemeral TTL */}
      <div style={{ display:'flex', alignItems:'center', gap:12, padding:'12px 14px', borderRadius:12, background:'rgba(0,0,0,0.20)', border:'1px solid rgba(255,255,255,0.08)' }}>
        <div style={{ flex:1 }}>
          <div style={{ fontSize:13, fontWeight:700, color:'#fff' }}>Ephemeral agency lifetime</div>
          <div style={{ fontSize:11, color:'rgba(255,255,255,0.40)', fontFamily:'var(--font-mono, monospace)', marginTop:2 }}>
            Non-admin (GitHub/Google) agencies are destroyed after this many hours. Admin companies persist forever.
          </div>
        </div>
        <input type="number" min="1" value={ttlInput}
          onChange={e => setTtlInput(e.target.value)}
          onBlur={e => { const v = parseInt(e.target.value, 10); if (v >= 1 && v !== settings.ephemeral_company_ttl_hours) save({ ephemeral_company_ttl_hours: v }); else setTtlInput(String(settings.ephemeral_company_ttl_hours)); }}
          style={{ width:72, padding:'7px 10px', borderRadius:9, background:'rgba(0,0,0,0.30)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff', fontSize:13, fontFamily:'var(--font-mono, monospace)', textAlign:'right', outline:'none' }}/>
        <span style={{ fontSize:12, color:'rgba(255,255,255,0.45)' }}>hours</span>
      </div>

      {msg && <div style={{ fontSize:12, color:'#46d9a4', marginTop:8, fontFamily:'var(--font-mono, monospace)' }}>✓ {msg}</div>}
      {err && <div style={{ fontSize:12, color:'#ff8a97', marginTop:8, fontFamily:'var(--font-mono, monospace)' }}>⚠ {err}</div>}
    </div>
  );
}

// ── 3. Audit log ─────────────────────────────────────────────────────────────
function AuditLog() {
  const [log, setLog] = React.useState([]);
  const [loadErr, setLoadErr] = React.useState('');
  const load = () => {
    setLoadErr('');
    api.get('/api/activation/audit-log?limit=50').then(r => setLog(r.data || []))
      .catch(e => setLoadErr(e.response?.data?.detail || 'Unable to load the audit log.'));
  };
  React.useEffect(load, []);

  if (loadErr) return (
    <div style={{ fontSize:13, color:'#ff8a97', padding:'8px 0' }}>
      ⚠ {loadErr}{' '}
      <button onClick={load} style={{ marginLeft:8, padding:'2px 10px', borderRadius:7, background:'rgba(93,162,255,0.10)', border:'1px solid rgba(93,162,255,0.25)', color:'#6CB0FF', fontSize:12, cursor:'pointer' }}>Retry</button>
    </div>
  );
  if (!log.length) return <div style={{ fontSize:13, color:'rgba(255,255,255,0.30)', padding:'8px 0' }}>No events yet.</div>;

  return (
    <div style={{ maxHeight:260, overflowY:'auto', overflowX:'auto', borderRadius:12, border:'1px solid rgba(255,255,255,0.08)' }}>
      <table style={{ width:'100%', borderCollapse:'collapse' }}>
        <thead>
          <tr style={{ background:'rgba(255,255,255,0.03)', position:'sticky', top:0 }}>
            {['Time', 'Event', 'User / Email', 'Result'].map(h => (
              <th key={h} style={{ padding:'8px 12px', textAlign:'left', fontSize:11, fontFamily:'var(--font-mono, monospace)', color:'rgba(255,255,255,0.35)', letterSpacing:'0.1em', textTransform:'uppercase', fontWeight:600 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {log.map((ev, i) => {
            const ok = ev.success || ev.allowed;
            return (
              <tr key={i} style={{ borderTop:'1px solid rgba(255,255,255,0.05)', background: i % 2 === 0 ? 'transparent' : 'rgba(255,255,255,0.015)' }}>
                <td style={{ padding:'8px 12px', fontSize:11, color:'rgba(255,255,255,0.30)', fontFamily:'var(--font-mono, monospace)', whiteSpace:'nowrap' }}>{new Date(ev.ts * 1000).toLocaleString()}</td>
                <td style={{ padding:'8px 12px', fontSize:12, fontFamily:'var(--font-mono, monospace)', color:'#a0b4d0' }}>{ev.event}</td>
                <td style={{ padding:'8px 12px', fontSize:12, fontFamily:'var(--font-mono, monospace)', color:'rgba(255,255,255,0.50)' }}>{ev.email || ev.user_id || ev.by || '—'}</td>
                <td style={{ padding:'8px 12px' }}>
                  {'success' in ev ? (
                    <Badge color={ev.success ? 'green' : 'red'}>{ev.success ? 'OK' : (ev.error || 'Fail')}</Badge>
                  ) : 'allowed' in ev ? (
                    <Badge color={ev.allowed ? 'green' : 'red'}>{ev.allowed ? 'Allowed' : 'Revoked'}</Badge>
                  ) : '—'}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Exported combined panel ───────────────────────────────────────────────────
export default function AdminOnboardingPanel() {
  return (
    <div>
      <div style={{ fontSize:11, fontFamily:'var(--font-mono, monospace)', color:'rgba(93,162,255,0.7)', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:16 }}>
        Activation & Onboarding Control
      </div>
      <SectionCard title="Instance Activation" icon="🔑">
        <ActivationStatus />
      </SectionCard>
      <SectionCard title="Default Onboarding Gate" icon="🚪">
        <OnboardingGateSettings />
      </SectionCard>
      <SectionCard title="User Onboarding Access" icon="👥">
        <UserOnboardingTable />
      </SectionCard>
      <SectionCard title="Activation Audit Log" icon="📋" defaultOpen={false}>
        <AuditLog />
      </SectionCard>
    </div>
  );
}
