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
import Glyph from '../components/ui/Glyph';
import api, { fmtErr } from '../../api';

function Badge({ children, color }) {
  const bg = color === 'green' ? 'color-mix(in oklab, var(--success) 10%, transparent)' : color === 'red' ? 'color-mix(in oklab, var(--danger) 10%, transparent)' : 'color-mix(in oklab, var(--ink) 6%, transparent)';
  const border = color === 'green' ? 'color-mix(in oklab, var(--success) 28%, transparent)' : color === 'red' ? 'color-mix(in oklab, var(--danger) 28%, transparent)' : 'color-mix(in oklab, var(--ink) 12%, transparent)';
  const text = color === 'green' ? 'var(--success)' : color === 'red' ? 'var(--danger)' : 'color-mix(in oklab, var(--ink) 45%, transparent)';
  return (
    <span style={{ padding:'2px 9px', borderRadius:999, background:bg, border:`1px solid ${border}`, color:text, fontSize:13, fontFamily:'var(--font-mono, monospace)', fontWeight:600 }}>
      {children}
    </span>
  );
}

function SectionCard({ title, icon, children, defaultOpen = true }) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <div style={{ background:'color-mix(in oklab, var(--ink) 3%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)', borderRadius:16, marginBottom:16, overflow:'hidden' }}>
      <button onClick={() => setOpen(v => !v)} style={{ width:'100%', display:'flex', alignItems:'center', gap:10, padding:'14px 18px', background:'none', border:'none', cursor:'pointer', textAlign:'left' }}>
        <span style={{ fontSize:16 }}><Glyph g={icon}/></span>
        <span style={{ flex:1, fontSize:14, fontWeight:700, color:'var(--text-primary)' }}>{title}</span>
        <span style={{ fontSize:13, color:'color-mix(in oklab, var(--ink) 30%, transparent)', fontFamily:'var(--font-mono, monospace)' }}>{open ? '▲' : '▼'}</span>
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
      .catch(e => setLoadErr(fmtErr(e.response?.data?.detail) || 'Unable to load activation status.'));
  };
  React.useEffect(load, []);

  const reActivate = async () => {
    if (!token.trim()) return;
    setLoading(true); setMsg(''); setErr('');
    try {
      const r = await api.post('/api/activation/activate', { token: token.trim() });
      if (r.data.success) { setMsg(`Activated for ${r.data.email}`); setToken(''); load(); }
      else setErr(r.data.error || 'Activation failed');
    } catch (e) { setErr(fmtErr(e.response?.data?.detail) || 'Error'); }
    finally { setLoading(false); }
  };

  if (!status) {
    if (loadErr) return (
      <div style={{ fontSize:14, color:'var(--danger)', padding:'8px 0' }}>
        <Glyph g="⚠"/> {loadErr}{' '}
        <button onClick={load} style={{ marginLeft:8, padding:'2px 10px', borderRadius:7, background:'color-mix(in oklab, var(--accent) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 25%, transparent)', color:'var(--accent)', fontSize:13, cursor:'pointer' }}>Retry</button>
      </div>
    );
    return <div style={{ fontSize:14, color:'color-mix(in oklab, var(--ink) 30%, transparent)', padding:'8px 0' }}>Loading…</div>;
  }

  return (
    <div>
      {/* Current status */}
      <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:14, padding:'12px 14px', borderRadius:12, background: status.activated ? 'color-mix(in oklab, var(--success) 5%, transparent)' : 'color-mix(in oklab, var(--danger) 5%, transparent)', border:`1px solid ${status.activated ? 'color-mix(in oklab, var(--success) 18%, transparent)' : 'color-mix(in oklab, var(--danger) 18%, transparent)'}` }}>
        <span style={{ fontSize:18 }}>{status.activated ? '✅' : '🔴'}</span>
        <div style={{ flex:1 }}>
          <div style={{ fontSize:14, fontWeight:700, color: status.activated ? 'var(--success)' : 'var(--danger)', marginBottom:2 }}>
            {status.activated ? `Activated — ${status.email}` : 'Not activated'}
          </div>
          {status.activated && status.issued_at && (
            <div style={{ fontSize:13, color:'color-mix(in oklab, var(--ink) 35%, transparent)', fontFamily:'var(--font-mono, monospace)' }}>
              Issued {new Date(status.issued_at * 1000).toLocaleDateString()}
              {status.expires_at ? ` · Expires ${new Date(status.expires_at * 1000).toLocaleDateString()}` : ' · No expiry'}
            </div>
          )}
          {!status.activated && (
            <div style={{ fontSize:13, color:'color-mix(in oklab, var(--ink) 35%, transparent)', fontFamily:'var(--font-mono, monospace)' }}>
              Onboarding locked until activated. Email {status.register_email} with the Instance ID below.
            </div>
          )}
        </div>
      </div>

      {/* Instance ID */}
      <div style={{ marginBottom:14 }}>
        <div style={{ fontSize:13, color:'color-mix(in oklab, var(--ink) 35%, transparent)', fontFamily:'var(--font-mono, monospace)', marginBottom:5 }}>INSTANCE ID</div>
        <div style={{ display:'flex', gap:8, alignItems:'center', padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--shade) 20%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)' }}>
          <code style={{ flex:1, fontSize:13, fontFamily:'var(--font-mono, monospace)', color:'var(--text-tertiary)', wordBreak:'break-all' }}>{status.instance_id}</code>
          <button onClick={() => navigator.clipboard?.writeText(status.instance_id)}
            style={{ padding:'4px 10px', borderRadius:7, background:'color-mix(in oklab, var(--accent) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 25%, transparent)', color:'var(--accent)', fontSize:13, cursor:'pointer', flexShrink:0, fontFamily:'var(--font-mono, monospace)' }}>
            Copy
          </button>
        </div>
      </div>

      {/* Re-activate */}
      <div style={{ fontSize:13, fontWeight:600, color:'color-mix(in oklab, var(--ink) 45%, transparent)', marginBottom:7 }}>
        {status.activated ? 'Replace activation token' : 'Enter activation token'}
      </div>
      <div style={{ display:'flex', gap:8 }}>
        <input value={token} onChange={e => setToken(e.target.value)} placeholder="Paste activation token…"
          style={{ flex:1, padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--shade) 20%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:13, fontFamily:'var(--font-mono, monospace)', outline:'none' }}/>
        <button onClick={reActivate} disabled={loading || !token.trim()}
          style={{ padding:'9px 18px', borderRadius:10, background:'color-mix(in oklab, var(--accent) 15%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 30%, transparent)', color:'var(--accent)', fontSize:14, fontWeight:700, cursor:'pointer', flexShrink:0, opacity: !token.trim() ? 0.45 : 1 }}>
          {loading ? '…' : 'Activate'}
        </button>
      </div>
      {msg && <div style={{ fontSize:13, color:'var(--success)', marginTop:8, fontFamily:'var(--font-mono, monospace)' }}>✓ {msg}</div>}
      {err && <div style={{ fontSize:13, color:'var(--danger)', marginTop:8, fontFamily:'var(--font-mono, monospace)' }}><Glyph g="⚠"/> {err}</div>}
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
    .catch(e => setLoadErr(fmtErr(e.response?.data?.detail) || 'Unable to load activation status.'));
  const loadUsers  = () => api.get('/api/activation/users').then(r => setUsers(r.data || []))
    .catch(e => setLoadErr(fmtErr(e.response?.data?.detail) || 'Unable to load users.'));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const reload = React.useCallback(() => { setLoadErr(''); loadStatus(); loadUsers(); }, []);
  React.useEffect(() => { reload(); }, [reload]);

  const toggle = async (userId, allowed) => {
    setLoading(p => ({ ...p, [userId]: true }));
    try {
      await api.put(`/api/activation/users/${encodeURIComponent(userId)}/onboarding`, { allowed });
      setUsers(u => u.map(x => x.user_id === userId ? { ...x, onboarding_allowed: allowed } : x));
    } catch(e) { alert(fmtErr(e.response?.data?.detail) || 'Error'); }
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
      <div style={{ padding:'12px 14px', borderRadius:12, background:'color-mix(in oklab, var(--danger) 6%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 18%, transparent)', fontSize:14, color:'var(--danger)' }}>
        <Glyph g="⚠"/> {loadErr}{' '}
        <button onClick={reload} style={{ marginLeft:8, padding:'2px 10px', borderRadius:7, background:'color-mix(in oklab, var(--accent) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 25%, transparent)', color:'var(--accent)', fontSize:13, cursor:'pointer' }}>Retry</button>
      </div>
    );
  }

  if (!activated) {
    return (
      <div style={{ padding:'12px 14px', borderRadius:12, background:'color-mix(in oklab, var(--warning) 6%, transparent)', border:'1px solid color-mix(in oklab, var(--warning) 18%, transparent)', fontSize:14, color:'var(--warning)' }}>
        <Glyph g="⚠"/> Instance must be activated before you can manage user onboarding.
      </div>
    );
  }

  return (
    <div>
      <p style={{ fontSize:14, color:'color-mix(in oklab, var(--ink) 45%, transparent)', lineHeight:1.6, marginBottom:14 }}>
        Toggle onboarding access per user. Users must be listed here and set to <Badge color="green">Allowed</Badge> before they can complete the setup wizard.
      </p>

      {/* Table */}
      {users.length === 0 ? (
        <div style={{ fontSize:14, color:'color-mix(in oklab, var(--ink) 30%, transparent)', padding:'14px 0' }}>No users added yet. Add a user ID below.</div>
      ) : (
        <div style={{ borderRadius:12, border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)', overflow:'hidden', marginBottom:16 }}>
          <div style={{ overflowX:'auto' }}>
          <table style={{ width:'100%', borderCollapse:'collapse' }}>
            <thead>
              <tr style={{ background:'color-mix(in oklab, var(--ink) 3%, transparent)' }}>
                {['User ID', 'Onboarding', 'Updated', 'By', 'Action'].map(h => (
                  <th key={h} style={{ padding:'9px 14px', textAlign:'left', fontSize:13, fontFamily:'var(--font-mono, monospace)', color:'color-mix(in oklab, var(--ink) 35%, transparent)', fontWeight:600 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.map((u, i) => (
                <tr key={u.user_id} style={{ borderTop:'1px solid color-mix(in oklab, var(--ink) 5%, transparent)', background: i % 2 === 0 ? 'transparent' : 'color-mix(in oklab, var(--ink) 1.5%, transparent)' }}>
                  <td style={{ padding:'10px 14px', fontSize:14, fontFamily:'var(--font-mono, monospace)', color:'var(--text-tertiary)', maxWidth:180, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{u.user_id}</td>
                  <td style={{ padding:'10px 14px' }}><Badge color={u.onboarding_allowed ? 'green' : 'red'}>{u.onboarding_allowed ? 'Allowed' : 'Blocked'}</Badge></td>
                  <td style={{ padding:'10px 14px', fontSize:13, color:'color-mix(in oklab, var(--ink) 30%, transparent)', fontFamily:'var(--font-mono, monospace)' }}>{u.updated_at ? new Date(u.updated_at * 1000).toLocaleString() : '—'}</td>
                  <td style={{ padding:'10px 14px', fontSize:13, color:'color-mix(in oklab, var(--ink) 30%, transparent)', fontFamily:'var(--font-mono, monospace)' }}>{u.updated_by || '—'}</td>
                  <td style={{ padding:'10px 14px' }}>
                    <button onClick={() => toggle(u.user_id, !u.onboarding_allowed)} disabled={!!loading[u.user_id]}
                      style={{ padding:'5px 12px', borderRadius:8, background: u.onboarding_allowed ? 'color-mix(in oklab, var(--danger) 10%, transparent)' : 'color-mix(in oklab, var(--success) 10%, transparent)', border:`1px solid ${u.onboarding_allowed ? 'color-mix(in oklab, var(--danger) 25%, transparent)' : 'color-mix(in oklab, var(--success) 25%, transparent)'}`, color: u.onboarding_allowed ? 'var(--danger)' : 'var(--success)', fontSize:13, fontWeight:600, cursor:'pointer', opacity: loading[u.user_id] ? 0.5 : 1, fontFamily:'var(--font-mono, monospace)' }}>
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
          style={{ flex:1, padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--shade) 20%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:14, fontFamily:'var(--font-mono, monospace)', outline:'none' }}/>
        <button onClick={addUser} disabled={!newUid.trim()}
          style={{ padding:'9px 18px', borderRadius:10, background:'color-mix(in oklab, var(--accent) 12%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 28%, transparent)', color:'var(--accent)', fontSize:14, fontWeight:700, cursor:'pointer', flexShrink:0, opacity: !newUid.trim() ? 0.45 : 1 }}>
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
      .catch(e => setLoadErr(fmtErr(e.response?.data?.detail) || 'Unable to load settings.'));
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
      setErr(fmtErr(e.response?.data?.detail) || 'Error');
      // On failure, snap the field back to the last known persisted value.
      if (settings) setTtlInput(String(settings.ephemeral_company_ttl_hours));
    }
    finally { setSaving(false); }
  };

  if (loadErr) return (
    <div style={{ fontSize:14, color:'var(--danger)', padding:'8px 0' }}>
      <Glyph g="⚠"/> {loadErr}{' '}
      <button onClick={load} style={{ marginLeft:8, padding:'2px 10px', borderRadius:7, background:'color-mix(in oklab, var(--accent) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 25%, transparent)', color:'var(--accent)', fontSize:13, cursor:'pointer' }}>Retry</button>
    </div>
  );
  if (!settings) return <div style={{ fontSize:14, color:'color-mix(in oklab, var(--ink) 30%, transparent)', padding:'8px 0' }}>Loading…</div>;

  const gateOff = settings.onboarding_gate_enabled === false;

  return (
    <div>
      <p style={{ fontSize:14, color:'color-mix(in oklab, var(--ink) 45%, transparent)', lineHeight:1.6, marginBottom:14 }}>
        Turn the gate <Badge color="red">off</Badge> to let <strong>every</strong> logged-in user run the
        setup wizard by default — no per-user allow-list entry needed. Keep it
        <Badge color="green">on</Badge> to require explicit approval per user (the table above).
      </p>

      {/* Gate toggle */}
      <div style={{ display:'flex', alignItems:'center', gap:12, padding:'12px 14px', borderRadius:12, background:'color-mix(in oklab, var(--shade) 20%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)', marginBottom:12 }}>
        <div style={{ flex:1 }}>
          <div style={{ fontSize:14, fontWeight:700, color:'var(--text-primary)' }}>Onboarding gate</div>
          <div style={{ fontSize:13, color:'color-mix(in oklab, var(--ink) 40%, transparent)', fontFamily:'var(--font-mono, monospace)', marginTop:2 }}>
            {gateOff ? 'OFF — all users may onboard by default' : 'ON — per-user approval required'}
          </div>
        </div>
        <button onClick={() => save({ onboarding_gate_enabled: gateOff })} disabled={saving}
          style={{ padding:'7px 16px', borderRadius:9, background: gateOff ? 'color-mix(in oklab, var(--success) 10%, transparent)' : 'color-mix(in oklab, var(--danger) 10%, transparent)', border:`1px solid ${gateOff ? 'color-mix(in oklab, var(--success) 28%, transparent)' : 'color-mix(in oklab, var(--danger) 28%, transparent)'}`, color: gateOff ? 'var(--success)' : 'var(--danger)', fontSize:14, fontWeight:700, cursor:'pointer', opacity: saving ? 0.5 : 1 }}>
          {saving ? '…' : gateOff ? 'Enable gate' : 'Disable gate'}
        </button>
      </div>

      {/* Ephemeral TTL */}
      <div style={{ display:'flex', alignItems:'center', gap:12, padding:'12px 14px', borderRadius:12, background:'color-mix(in oklab, var(--shade) 20%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)' }}>
        <div style={{ flex:1 }}>
          <div style={{ fontSize:14, fontWeight:700, color:'var(--text-primary)' }}>Ephemeral agency lifetime</div>
          <div style={{ fontSize:13, color:'color-mix(in oklab, var(--ink) 40%, transparent)', fontFamily:'var(--font-mono, monospace)', marginTop:2 }}>
            Non-admin (GitHub/Google) agencies are destroyed after this many hours. Admin companies persist forever.
          </div>
        </div>
        <input type="number" min="1" value={ttlInput}
          onChange={e => setTtlInput(e.target.value)}
          onBlur={e => { const v = parseInt(e.target.value, 10); if (v >= 1 && v !== settings.ephemeral_company_ttl_hours) save({ ephemeral_company_ttl_hours: v }); else setTtlInput(String(settings.ephemeral_company_ttl_hours)); }}
          style={{ width:72, padding:'7px 10px', borderRadius:9, background:'color-mix(in oklab, var(--shade) 30%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 12%, transparent)', color:'var(--text-primary)', fontSize:14, fontFamily:'var(--font-mono, monospace)', textAlign:'right', outline:'none' }}/>
        <span style={{ fontSize:13, color:'color-mix(in oklab, var(--ink) 45%, transparent)' }}>hours</span>
      </div>

      {msg && <div style={{ fontSize:13, color:'var(--success)', marginTop:8, fontFamily:'var(--font-mono, monospace)' }}>✓ {msg}</div>}
      {err && <div style={{ fontSize:13, color:'var(--danger)', marginTop:8, fontFamily:'var(--font-mono, monospace)' }}><Glyph g="⚠"/> {err}</div>}
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
      .catch(e => setLoadErr(fmtErr(e.response?.data?.detail) || 'Unable to load the audit log.'));
  };
  React.useEffect(load, []);

  if (loadErr) return (
    <div style={{ fontSize:14, color:'var(--danger)', padding:'8px 0' }}>
      <Glyph g="⚠"/> {loadErr}{' '}
      <button onClick={load} style={{ marginLeft:8, padding:'2px 10px', borderRadius:7, background:'color-mix(in oklab, var(--accent) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 25%, transparent)', color:'var(--accent)', fontSize:13, cursor:'pointer' }}>Retry</button>
    </div>
  );
  if (!log.length) return <div style={{ fontSize:14, color:'color-mix(in oklab, var(--ink) 30%, transparent)', padding:'8px 0' }}>No events yet.</div>;

  return (
    <div style={{ maxHeight:260, overflowY:'auto', overflowX:'auto', borderRadius:12, border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)' }}>
      <table style={{ width:'100%', borderCollapse:'collapse' }}>
        <thead>
          <tr style={{ background:'color-mix(in oklab, var(--ink) 3%, transparent)', position:'sticky', top:0 }}>
            {['Time', 'Event', 'User / Email', 'Result'].map(h => (
              <th key={h} style={{ padding:'8px 12px', textAlign:'left', fontSize:13, fontFamily:'var(--font-mono, monospace)', color:'color-mix(in oklab, var(--ink) 35%, transparent)', fontWeight:600 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {log.map((ev, i) => {
            const ok = ev.success || ev.allowed;
            return (
              <tr key={i} style={{ borderTop:'1px solid color-mix(in oklab, var(--ink) 5%, transparent)', background: i % 2 === 0 ? 'transparent' : 'color-mix(in oklab, var(--ink) 1.5%, transparent)' }}>
                <td style={{ padding:'8px 12px', fontSize:13, color:'color-mix(in oklab, var(--ink) 30%, transparent)', fontFamily:'var(--font-mono, monospace)', whiteSpace:'nowrap' }}>{new Date(ev.ts * 1000).toLocaleString()}</td>
                <td style={{ padding:'8px 12px', fontSize:13, fontFamily:'var(--font-mono, monospace)', color:'var(--text-tertiary)' }}>{ev.event}</td>
                <td style={{ padding:'8px 12px', fontSize:13, fontFamily:'var(--font-mono, monospace)', color:'color-mix(in oklab, var(--ink) 50%, transparent)' }}>{ev.email || ev.user_id || ev.by || '—'}</td>
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
      <div style={{ fontSize:13, fontFamily:'var(--font-mono, monospace)', color:'color-mix(in oklab, var(--accent) 70%, transparent)', marginBottom:16 }}>
        Activation & Onboarding Control
      </div>
      <SectionCard title="Instance activation" icon="🔑">
        <ActivationStatus />
      </SectionCard>
      <SectionCard title="Default onboarding gate" icon="🚪">
        <OnboardingGateSettings />
      </SectionCard>
      <SectionCard title="User onboarding access" icon="👥">
        <UserOnboardingTable />
      </SectionCard>
      <SectionCard title="Activation audit log" icon="📋" defaultOpen={false}>
        <AuditLog />
      </SectionCard>
    </div>
  );
}
