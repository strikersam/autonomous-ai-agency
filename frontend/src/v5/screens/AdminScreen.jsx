/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import AdminOnboardingPanel from './AdminOnboardingPanel';
import * as api from '../../api';
import { useSafeData } from '../hooks/useSafeData';

// admin.jsx — V5.0 Admin Panel
// Users (onboarding allow-list + roles), API keys, instance activation.
// Wired to the real backend: GET /api/activation/users, POST .../role,
// PUT .../onboarding, and the /api/keys CRUD.

function errText(e, fallback) {
  const detail = e?.response?.data?.detail;
  return detail ? api.fmtErr(detail) : (e?.message || fallback);
}

function relTime(epochSeconds) {
  if (!epochSeconds) return '—';
  const ms = typeof epochSeconds === 'number' ? epochSeconds * 1000 : new Date(epochSeconds).getTime();
  if (isNaN(ms)) return '—';
  const diff = Math.floor((Date.now() - ms) / 1000);
  if (diff < 0) return 'just now';
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}

const roleConfig = {
  admin:      { color:'#ff6b7d', bg:'rgba(255,107,125,0.10)', border:'rgba(255,107,125,0.22)', label:'Admin' },
  power_user: { color:'#7c9dff', bg:'rgba(124,157,255,0.10)', border:'rgba(124,157,255,0.22)', label:'Power User' },
  user:       { color:'#46d9a4', bg:'rgba(70,217,164,0.08)',  border:'rgba(70,217,164,0.18)',  label:'User' },
};

function RoleBadge({ role }) {
  if (!role) return <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>role n/a</span>;
  const rc = roleConfig[role] || roleConfig.user;
  return <span style={{ fontSize:10, fontFamily:'var(--font-mono)', letterSpacing:'0.10em', textTransform:'uppercase', padding:'2px 8px', borderRadius:999, color:rc.color, background:rc.bg, border:`1px solid ${rc.border}` }}>{rc.label}</span>;
}

function ActivationPanel() {
  // Delegated to the server-backed AdminOnboardingPanel (activation_api.py).
  return <AdminOnboardingPanel />;
}

// ── User row ───────────────────────────────────────────────────────────────────
function UserRow({ user, onRoleChange, onToggleOnboarding, busy }) {
  const [roleOpen, setRoleOpen] = React.useState(false);
  const allowed = !!user.onboarding_allowed;
  const name = user.user_id || '—';
  return (
    <div style={{ display:'flex', alignItems:'center', gap:12, padding:'11px 16px', borderBottom:'1px solid rgba(255,255,255,0.05)', transition:'background 0.15s' }}>
      <div style={{ width:32, height:32, borderRadius:'50%', background:'linear-gradient(135deg,var(--accent),#3a7fe8)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:12, fontWeight:800, color:'#06111f', flexShrink:0 }}>
        {(name[0] || '?').toUpperCase()}
      </div>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ display:'flex', alignItems:'center', gap:6, flexWrap:'wrap', marginBottom:1 }}>
          <span style={{ fontSize:13, fontWeight:600, color:'var(--text-primary)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', maxWidth:240 }}>{name}</span>
          <RoleBadge role={user.role}/>
        </div>
        <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>
          {user.updated_at ? `updated ${relTime(user.updated_at)}${user.updated_by ? ` by ${user.updated_by}` : ''}` : 'no changes yet'}
        </div>
      </div>
      {/* Onboarding toggle */}
      <div style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:3, flexShrink:0 }}>
        <button onClick={()=>onToggleOnboarding(user.user_id, !allowed)} disabled={busy} style={{
          width:36, height:20, borderRadius:999, padding:3, cursor:busy?'wait':'pointer', opacity:busy?0.6:1,
          background:allowed?'#46d9a4':'rgba(255,255,255,0.10)',
          border:`1px solid ${allowed?'rgba(70,217,164,0.5)':'rgba(255,255,255,0.15)'}`,
          transition:'all 0.2s', display:'flex', alignItems:'center', justifyContent:allowed?'flex-end':'flex-start',
        }}>
          <div style={{ width:14, height:14, borderRadius:'50%', background:'#fff', boxShadow:'0 1px 3px rgba(0,0,0,0.3)' }}/>
        </button>
        <span style={{ fontSize:9, fontFamily:'var(--font-mono)', color:allowed?'#46d9a4':'var(--text-muted)', letterSpacing:'0.08em', textTransform:'uppercase', whiteSpace:'nowrap' }}>Onboarding</span>
      </div>
      {/* Role menu */}
      <div style={{ position:'relative', flexShrink:0 }}>
        <button onClick={()=>setRoleOpen(o=>!o)} style={{ padding:'5px 10px', borderRadius:8, fontSize:11, cursor:'pointer', background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.12)', color:'var(--text-muted)' }}>Set role ⋯</button>
        {roleOpen && (
          <div style={{ position:'absolute', right:0, top:'100%', marginTop:4, zIndex:20, background:'rgba(14,17,22,0.98)', border:'1px solid rgba(255,255,255,0.12)', borderRadius:12, padding:6, minWidth:140, boxShadow:'0 12px 32px rgba(0,0,0,0.5)', animation:'fadeSlideUp 0.15s ease-out' }}>
            {['admin','power_user','user'].map(r=>{
              const rc=roleConfig[r];
              return <button key={r} onClick={()=>{onRoleChange(user.user_id,r);setRoleOpen(false);}} style={{ display:'block',width:'100%',padding:'7px 12px',borderRadius:8,textAlign:'left',background:user.role===r?`${rc.color}12`:'transparent',border:'none',cursor:'pointer',fontSize:12,color:user.role===r?rc.color:'var(--text-tertiary)',fontFamily:'var(--font-main)',transition:'all 0.12s' }}>{rc.label}</button>;
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ── API key create form ─────────────────────────────────────────────────────────
function NewKeyForm({ onCreate, onClose }) {
  const [email, setEmail] = React.useState('');
  const [label, setLabel] = React.useState('');
  const [department, setDepartment] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState(null);

  const submit = async () => {
    if (!email.trim() || busy) return;
    setBusy(true); setError(null);
    try {
      await onCreate({ email: email.trim(), label: label.trim(), department: department.trim() });
      onClose();
    } catch (e) { setError(errText(e, 'Could not create key.')); setBusy(false); }
  };
  const fld = { padding:'9px 12px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', fontSize:13, outline:'none', fontFamily:'var(--font-main)' };
  return (
    <div style={{ padding:'14px', borderRadius:14, background:'rgba(93,162,255,0.05)', border:'1px solid rgba(93,162,255,0.18)', marginBottom:12 }}>
      <div style={{ fontSize:12, fontWeight:700, color:'var(--text-secondary)', marginBottom:10 }}>Issue API key</div>
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginBottom:8 }}>
        <input value={email} onChange={e=>setEmail(e.target.value)} placeholder="Owner email *" style={{ ...fld, fontFamily:'var(--font-mono)' }}/>
        <input value={label} onChange={e=>setLabel(e.target.value)} placeholder="Label (e.g. Cursor)" style={fld}/>
      </div>
      <input value={department} onChange={e=>setDepartment(e.target.value)} placeholder="Department (optional)" style={{ ...fld, width:'100%', marginBottom:10 }}/>
      {error && <div style={{ marginBottom:8, padding:'8px 12px', borderRadius:10, background:'rgba(255,107,125,0.10)', border:'1px solid rgba(255,107,125,0.25)', color:'#ff6b7d', fontSize:12 }}>{error}</div>}
      <div style={{ display:'flex', gap:8 }}>
        <button onClick={submit} disabled={busy} style={{ padding:'9px 16px', borderRadius:10, background:'var(--accent)', color:'#06111f', fontSize:12, fontWeight:800, border:'none', cursor:busy?'wait':'pointer', opacity:busy?0.7:1 }}>{busy ? 'Creating…' : 'Create key'}</button>
        <button onClick={onClose} disabled={busy} style={{ padding:'9px 14px', borderRadius:10, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-muted)', fontSize:12, cursor:'pointer' }}>Cancel</button>
      </div>
    </div>
  );
}


// ── Companies cleanup panel ──────────────────────────────────────────────────
function CompaniesPanel({ onActionError }) {
  const [companies, setCompanies] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [busy, setBusy] = React.useState(null);
  const [confirmDelete, setConfirmDelete] = React.useState(null);

  const load = React.useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.listCompanies({ limit: 200 });
      setCompanies(data?.companies || []);
    } catch (e) {
      onActionError(api.fmtErr(e?.response?.data?.detail) || e?.message || 'Failed to load companies.');
    } finally { setLoading(false); }
  }, [onActionError]);

  React.useEffect(() => { load(); }, [load]);

  const handleDelete = async (companyId, name) => {
    setBusy(companyId);
    try {
      await api.deleteCompany(companyId);
      setCompanies(c => c.filter(x => x.id !== companyId));
      setConfirmDelete(null);
    } catch (e) {
      onActionError(api.fmtErr(e?.response?.data?.detail) || e?.message || `Failed to delete ${name}.`);
    } finally { setBusy(null); }
  };

  if (loading) return <div style={{ padding:'20px 16px', fontSize:13, color:'var(--text-muted)' }}>Loading companies…</div>;

  return (
    <div>
      <p style={{ fontSize:13, color:'var(--text-muted)', lineHeight:1.6, marginBottom:14 }}>
        Review and manage all companies. Deleting a company removes all associated specialists, scans, workflows, and graph data permanently.
      </p>
      {companies.length === 0 ? (
        <div style={{ padding:'20px 16px', fontSize:13, color:'var(--text-muted)' }}>No companies found.</div>
      ) : (
        <div style={{ borderRadius:14, border:'1px solid rgba(255,255,255,0.09)', overflow:'hidden' }}>
          {companies.map((c, i) => (
            <div key={c.id} style={{ display:'flex', alignItems:'center', gap:12, padding:'12px 16px', borderBottom:i<companies.length-1?'1px solid rgba(255,255,255,0.05)':'none', background: confirmDelete===c.id?'rgba(255,107,125,0.05)':'transparent', transition:'background 0.2s' }}>
              <div style={{ width:32, height:32, borderRadius:10, background:'linear-gradient(135deg,rgba(93,162,255,0.20),rgba(93,162,255,0.05))', border:'1px solid rgba(93,162,255,0.25)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:14, flexShrink:0 }}>🏢</div>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ fontSize:13, fontWeight:600, color:'var(--text-primary)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{c.name}</div>
                <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{c.domain || '—'}{' · '}{c.business_category || 'other'}{' · '}{c.id?.slice(0,8) || '—'}</div>
              </div>
              {confirmDelete === c.id ? (
                <div style={{ display:'flex', gap:6, flexShrink:0 }}>
                  <button onClick={() => handleDelete(c.id, c.name)} disabled={busy===c.id} style={{ padding:'5px 12px', borderRadius:8, background:'rgba(255,107,125,0.15)', border:'1px solid rgba(255,107,125,0.30)', color:'#ff6b7d', fontSize:11, fontWeight:700, cursor:'pointer', opacity:busy===c.id?0.5:1 }}>
                    {busy===c.id?'Deleting…':'Confirm delete'}
                  </button>
                  <button onClick={() => setConfirmDelete(null)} style={{ padding:'5px 10px', borderRadius:8, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', color:'var(--text-muted)', fontSize:11, cursor:'pointer' }}>Cancel</button>
                </div>
              ) : (
                <button onClick={() => setConfirmDelete(c.id)} style={{ padding:'5px 10px', borderRadius:8, background:'rgba(255,107,125,0.06)', border:'1px solid rgba(255,107,125,0.18)', color:'#ff6b7d', fontSize:11, cursor:'pointer', flexShrink:0 }}>Delete</button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main AdminScreen ───────────────────────────────────────────────────────────
function AdminScreen() {
  const [tab, setTab] = React.useState('users');
  const [busyUser, setBusyUser] = React.useState(null);
  const [actionErr, setActionErr] = React.useState(null);
  const [roleNote, setRoleNote] = React.useState(null);
  const [showNewKey, setShowNewKey] = React.useState(false);
  const [newKeyPlain, setNewKeyPlain] = React.useState(null);

  const [data, states, refetch] = useSafeData(null, {
    users: '/api/activation/users',
    keys:  '/api/keys',
  }, { refreshMs: 0 });

  const users = Array.isArray(data.users) ? data.users : (data.users?.users || []);
  const keys  = data.keys?.keys || [];
  const allowedCount = users.filter(u => u.onboarding_allowed).length;

  const handleToggleOnboarding = async (userId, val) => {
    setBusyUser(userId); setActionErr(null);
    try { await api.setUserOnboarding(userId, val); await refetch(); }
    catch (e) { setActionErr(errText(e, 'Could not update onboarding flag.')); }
    finally { setBusyUser(null); }
  };
  const handleRoleChange = async (userId, role) => {
    setBusyUser(userId); setActionErr(null); setRoleNote(null);
    try {
      await api.changeUserRole(userId, role);
      setRoleNote(`Set ${userId} → ${role}.`);
      await refetch();
    } catch (e) { setActionErr(errText(e, 'Could not change role.')); }
    finally { setBusyUser(null); }
  };
  const handleCreateKey = async (payload) => {
    const { data: res } = await api.createApiKey(payload);
    setNewKeyPlain(res?.api_key || null);
    await refetch();
  };
  const handleRevokeKey = async (keyId) => {
    if (!window.confirm('Revoke this API key? Applications using it will stop working.')) return;
    setActionErr(null);
    try { await api.deleteApiKey(keyId); await refetch(); }
    catch (e) { setActionErr(errText(e, 'Could not revoke key.')); }
  };

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', overflow:'hidden' }}>
      {/* Header */}
      <div style={{ padding:'18px 20px 0', flexShrink:0 }}>
        <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'#ff6b7d', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:4 }}>Admin Only</div>
        <div style={{ display:'flex', alignItems:'flex-end', justifyContent:'space-between', flexWrap:'wrap', gap:10, marginBottom:14 }}>
          <div>
            <h1 style={{ fontSize:24, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', lineHeight:1.1, marginBottom:3 }}>Admin Panel</h1>
            <p style={{ fontSize:13, color:'var(--text-tertiary)', lineHeight:1.5 }}>Instance activation, per-user onboarding approvals, roles, and API keys.</p>
          </div>
          <div style={{ display:'flex', gap:8 }}>
            {[
              { label:'Users', value:users.length, color:'var(--accent)' },
              { label:'Onboarding', value:allowedCount, color:'#46d9a4' },
              { label:'API keys', value:keys.length, color:'#c4b5fd' },
              { label:'Companies', value:'—', color:'#ffbd66' },
            ].map(s=>(
              <div key={s.label} style={{ padding:'7px 12px', borderRadius:11, background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.08)', textAlign:'center' }}>
                <div style={{ fontSize:18, fontWeight:800, color:s.color, letterSpacing:'-0.03em' }}>{s.value}</div>
                <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.10em' }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
        <div style={{ display:'flex', gap:4 }}>
          {['activation','users','companies','api-keys'].map(t=>(
            <button key={t} onClick={()=>{ setTab(t); setActionErr(null); setRoleNote(null); }} style={{ padding:'7px 16px', borderRadius:'10px 10px 0 0', fontSize:12, fontWeight:600, cursor:'pointer', textTransform:'capitalize', transition:'all 0.15s', background:tab===t?'rgba(10,12,15,0.90)':'rgba(255,255,255,0.03)', border:`1px solid ${tab===t?'rgba(255,255,255,0.10)':'rgba(255,255,255,0.06)'}`, borderBottom:tab===t?'1px solid rgba(10,12,15,0.90)':'1px solid rgba(255,255,255,0.06)', color:tab===t?'#fff':'var(--text-muted)' }}>
              {t==='api-keys'?'API Keys':t==='activation'?'🔐 Activation':t==='companies'?'🏢 Companies':'Users'}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div style={{ flex:1, minHeight:0, overflow:'hidden', background:'rgba(10,12,15,0.90)', borderTop:'1px solid rgba(255,255,255,0.08)' }}>
        {tab === 'activation' && (
          <div style={{ padding:'16px', overflowY:'auto', height:'100%' }}>
            <ActivationPanel/>
          </div>
        )}

        {tab === 'users' && (
          <div style={{ padding:'14px 16px', overflowY:'auto', height:'100%' }} className="scrollbar-hide">
            {actionErr && <div style={{ marginBottom:10, padding:'8px 12px', borderRadius:10, background:'rgba(255,107,125,0.10)', border:'1px solid rgba(255,107,125,0.25)', color:'#ff6b7d', fontSize:12 }}>{actionErr}</div>}
            {roleNote && <div style={{ marginBottom:10, padding:'8px 12px', borderRadius:10, background:'rgba(70,217,164,0.08)', border:'1px solid rgba(70,217,164,0.22)', color:'#46d9a4', fontSize:12 }}>{roleNote}</div>}
            <div style={{ fontSize:11, color:'var(--text-muted)', marginBottom:8, lineHeight:1.5 }}>
              The onboarding allow-list comes from <code style={{ fontFamily:'var(--font-mono)' }}>/api/activation/users</code>. It tracks each user's onboarding flag; role changes are applied to the user record (the list reflects flags, not roles).
            </div>
            <div style={{ borderRadius:14, border:'1px solid rgba(255,255,255,0.09)', overflow:'hidden' }}>
              {states.users?.loading && users.length === 0 ? (
                <div style={{ padding:'20px 16px', fontSize:13, color:'var(--text-muted)' }}>Loading users…</div>
              ) : states.users?.error ? (
                <div style={{ padding:'18px 16px', fontSize:13, color:'#ff6b7d' }}>Couldn't load users: {states.users.error}</div>
              ) : users.length === 0 ? (
                <div style={{ padding:'20px 16px', fontSize:13, color:'var(--text-muted)' }}>No users in the onboarding allow-list yet.</div>
              ) : (
                users.map(u => (
                  <UserRow key={u.user_id} user={u} onRoleChange={handleRoleChange} onToggleOnboarding={handleToggleOnboarding} busy={busyUser===u.user_id}/>
                ))
              )}
            </div>
          </div>
        )}

        
        {tab === 'companies' && (
          <div style={{ padding:'14px 16px', overflowY:'auto', height:'100%' }} className="scrollbar-hide">
            <CompaniesPanel onActionError={(e)=>setActionErr(e)}/>
          </div>
        )}


        {tab === 'api-keys' && (
          <div style={{ padding:'14px', overflowY:'auto', height:'100%' }}>
            <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:10 }}>
              <button onClick={()=>{ setShowNewKey(o=>!o); setNewKeyPlain(null); }} style={{ padding:'7px 14px', borderRadius:9, fontSize:12, fontWeight:700, cursor:'pointer', background:'rgba(93,162,255,0.12)', border:'1px solid rgba(93,162,255,0.25)', color:'var(--accent)' }}>+ Issue key</button>
            </div>
            {showNewKey && <NewKeyForm onCreate={handleCreateKey} onClose={()=>setShowNewKey(false)}/>}
            {newKeyPlain && (
              <div style={{ marginBottom:12, padding:'10px 14px', borderRadius:12, background:'rgba(70,217,164,0.07)', border:'1px solid rgba(70,217,164,0.22)' }}>
                <div style={{ fontSize:11, color:'#46d9a4', marginBottom:4, fontWeight:700 }}>Copy this key now — it won't be shown again:</div>
                <code style={{ fontSize:12, fontFamily:'var(--font-mono)', color:'#fff', wordBreak:'break-all' }}>{newKeyPlain}</code>
              </div>
            )}
            {actionErr && <div style={{ marginBottom:10, padding:'8px 12px', borderRadius:10, background:'rgba(255,107,125,0.10)', border:'1px solid rgba(255,107,125,0.25)', color:'#ff6b7d', fontSize:12 }}>{actionErr}</div>}
            <div style={{ borderRadius:14, border:'1px solid rgba(255,255,255,0.09)', overflow:'hidden' }}>
              {states.keys?.loading && keys.length === 0 ? (
                <div style={{ padding:'20px 16px', fontSize:13, color:'var(--text-muted)' }}>Loading keys…</div>
              ) : states.keys?.error ? (
                <div style={{ padding:'18px 16px', fontSize:13, color:'#ff6b7d' }}>Couldn't load keys: {states.keys.error}</div>
              ) : keys.length === 0 ? (
                <div style={{ padding:'20px 16px', fontSize:13, color:'var(--text-muted)' }}>No API keys issued yet.</div>
              ) : (
                keys.map((key,i)=>(
                  <div key={key.key_id || key._id} style={{ display:'flex', alignItems:'center', gap:12, padding:'12px 16px', borderBottom:i<keys.length-1?'1px solid rgba(255,255,255,0.05)':'none' }}>
                    <div style={{ flex:1, minWidth:0 }}>
                      <div style={{ display:'flex', alignItems:'center', gap:7, marginBottom:2, flexWrap:'wrap' }}>
                        <span style={{ fontSize:13, fontWeight:600, color:'var(--text-primary)' }}>{key.label || key.key_id}</span>
                        {key.email && <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{key.email}</span>}
                        {key.department && <span style={{ fontSize:9, fontFamily:'var(--font-mono)', color:'var(--text-muted)', background:'rgba(255,255,255,0.05)', padding:'1px 6px', borderRadius:5 }}>{key.department}</span>}
                      </div>
                      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{key.prefix || key.key_id} · created {relTime(key.created_at)}</div>
                    </div>
                    <button onClick={()=>handleRevokeKey(key.key_id)} style={{ padding:'5px 10px', borderRadius:8, fontSize:11, cursor:'pointer', background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.20)', color:'#ff6b7d', flexShrink:0 }}>Revoke</button>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export { AdminScreen };
export default AdminScreen;
