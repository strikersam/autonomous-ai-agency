/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import AdminOnboardingPanel from './AdminOnboardingPanel';


// admin.jsx — V5.0 Admin Panel
// Users, roles, API keys, per-user onboarding approval, instance activation system

// ── Instance activation (3-layer anti-bypass model) ──────────────────────────
//
// Layer 1: UI gate — checks localStorage for valid token (easily removed, but obvious)
// Layer 2: HMAC token validation — token is signed with author's private key.
//           Without the signing key, no valid token can be generated.
//           Token format: LLR-{instanceId}-{expiry}-{quota}-{hmac_hex}
//           The HMAC covers instanceId+expiry+quota. Any tampering breaks it.
// Layer 3: Canary heartbeat — on every agent provisioning, runtime POSTs to
//           strikersam.com/relay/heartbeat?id=INSTANCE&v=5.0
//           Unregistered heartbeats = bypassed instance = author is notified.
//           This call is woven into agent runtime startup — not one standalone check.
//
// Even if a developer removes the UI check and crafts a token manually, the
// canary exposes them. Removing the canary too requires understanding both layers.

// Legacy HMAC helpers removed — server-backed activation in activation_api.py

// ── Mock data (stub until wired to live API in a future session) ──────────────
const INITIAL_USERS = [
  { id:'u-1', name:'Sam Striker',  email:'admin@llmrelay.local', role:'admin',      status:'active',  lastActive:'2m ago',  sessions:142, apiKeys:2, onboardingAllowed:true,  onboardingDone:true },
  { id:'u-2', name:'Alex Chen',    email:'alex@acme-store.com',  role:'power_user', status:'active',  lastActive:'1h ago',  sessions:67,  apiKeys:1, onboardingAllowed:true,  onboardingDone:true },
  { id:'u-3', name:'Jordan Kim',   email:'jordan@acme-store.com',role:'user',       status:'active',  lastActive:'3d ago',  sessions:18,  apiKeys:1, onboardingAllowed:false, onboardingDone:false },
  { id:'u-4', name:'Casey Morgan', email:'casey@acme-store.com', role:'user',       status:'pending', lastActive:'never',   sessions:0,   apiKeys:0, onboardingAllowed:false, onboardingDone:false },
];

const INITIAL_REQUESTS = [
  { id:'req-1', from:'Jordan Kim',   email:'jordan@acme-store.com', ts:'1h ago', message:'I manage our Shopify store — would like to connect it for AI automation.', status:'pending' },
  { id:'req-2', from:'Casey Morgan', email:'casey@acme-store.com',  ts:'2h ago', message:'New to the team. Would love to set up our marketing stack.', status:'pending' },
];

const INITIAL_KEYS = [
  { id:'k-1', label:'Claude Code (dev)',  key:'sk-relay-dev-••••••••', userId:'u-1', created:'2026-01-12', lastUsed:'2m ago', requests:14211 },
  { id:'k-2', label:'Cursor integration', key:'sk-relay-cur-••••••••', userId:'u-1', created:'2026-02-03', lastUsed:'1h ago', requests:8842 },
  { id:'k-3', label:'Alex dev key',       key:'sk-relay-alx-••••••••', userId:'u-2', created:'2026-03-08', lastUsed:'1h ago', requests:3201 },
];

const roleConfig = {
  admin:      { color:'#ff6b7d', bg:'rgba(255,107,125,0.10)', border:'rgba(255,107,125,0.22)', label:'Admin' },
  power_user: { color:'#7c9dff', bg:'rgba(124,157,255,0.10)', border:'rgba(124,157,255,0.22)', label:'Power User' },
  user:       { color:'#46d9a4', bg:'rgba(70,217,164,0.08)',  border:'rgba(70,217,164,0.18)',  label:'User' },
};

function RoleBadge({ role }) {
  const rc = roleConfig[role] || roleConfig.user;
  return <span style={{ fontSize:10, fontFamily:'var(--font-mono)', letterSpacing:'0.10em', textTransform:'uppercase', padding:'2px 8px', borderRadius:999, color:rc.color, background:rc.bg, border:`1px solid ${rc.border}` }}>{rc.label}</span>;
}

// setUserOnboardingFlag — stub retained for AdminScreen state updates;
// real persistence goes through AdminOnboardingPanel → activation_api.py
function setUserOnboardingFlag(userId, val) {  // eslint-disable-line no-unused-vars
  // TODO(next-session): call PUT /api/activation/users/{userId}/onboarding
  console.log('setUserOnboardingFlag', userId, val);
}

function ActivationPanel() {
  // Delegated to server-backed AdminOnboardingPanel (activation_api.py)
  // Replaces the old client-side HMAC implementation.
  return <AdminOnboardingPanel />;
}
// ── Onboarding Requests Panel ──────────────────────────────────────────────────
function OnboardingRequests({ requests, onApprove, onDecline }) {
  const pending = requests.filter(r=>r.status==='pending');
  if (pending.length === 0) return (
    <div style={{ padding:'10px 14px', borderRadius:12, background:'rgba(70,217,164,0.04)', border:'1px solid rgba(70,217,164,0.14)', fontSize:12, color:'#46d9a4', marginBottom:14 }}>
      ✓ No pending onboarding requests.
    </div>
  );
  return (
    <div style={{ marginBottom:16 }}>
      <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:10 }}>
        <span style={{ fontSize:13, fontWeight:700, color:'#fff' }}>Onboarding Requests</span>
        <span style={{ fontSize:10, fontFamily:'var(--font-mono)', padding:'2px 7px', borderRadius:999, background:'rgba(255,189,102,0.12)', color:'#ffbd66', border:'1px solid rgba(255,189,102,0.25)' }}>{pending.length} pending</span>
      </div>
      <div style={{ display:'flex', flexDirection:'column', gap:9 }}>
        {pending.map(req=>(
          <div key={req.id} style={{ padding:'12px 14px', borderRadius:14, background:'rgba(255,189,102,0.05)', border:'1px solid rgba(255,189,102,0.18)', animation:'fadeSlideUp 0.3s ease-out' }}>
            <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:10, marginBottom:8, flexWrap:'wrap' }}>
              <div>
                <div style={{ fontSize:13, fontWeight:700, color:'#fff', marginBottom:1 }}>{req.from}</div>
                <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--accent)' }}>{req.email}</div>
                <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', marginTop:1 }}>{req.ts}</div>
              </div>
              <div style={{ display:'flex', gap:7, flexShrink:0 }}>
                <button onClick={()=>onApprove(req)} style={{ padding:'7px 16px', borderRadius:9, fontSize:12, fontWeight:700, cursor:'pointer', background:'rgba(70,217,164,0.12)', border:'1px solid rgba(70,217,164,0.28)', color:'#46d9a4', transition:'all 0.15s' }}
                  onMouseEnter={e=>e.currentTarget.style.background='rgba(70,217,164,0.20)'}
                  onMouseLeave={e=>e.currentTarget.style.background='rgba(70,217,164,0.12)'}>
                  ✓ Approve + allow onboarding
                </button>
                <button onClick={()=>onDecline(req)} style={{ padding:'7px 12px', borderRadius:9, fontSize:12, cursor:'pointer', background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.20)', color:'#ff6b7d' }}>
                  Decline
                </button>
              </div>
            </div>
            <div style={{ fontSize:12, color:'var(--text-secondary)', lineHeight:1.55, padding:'8px 10px', borderRadius:8, background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.07)', fontStyle:'italic' }}>
              "{req.message}"
            </div>
            <div style={{ marginTop:6, fontSize:11, color:'var(--text-muted)', fontFamily:'var(--font-mono)' }}>Approving will email {req.email} and set their onboarding flag to allowed.</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── User row ───────────────────────────────────────────────────────────────────
function UserRow({ user, onRoleChange, onToggleOnboarding, selected, onSelect }) {
  const [roleOpen, setRoleOpen] = React.useState(false);
  return (
    <div style={{ display:'flex', alignItems:'center', gap:12, padding:'11px 16px', borderBottom:'1px solid rgba(255,255,255,0.05)', cursor:'pointer', background:selected?'rgba(93,162,255,0.05)':'transparent', transition:'background 0.15s' }}
    onClick={()=>onSelect(user.id)}
    onMouseEnter={e=>{if(!selected)e.currentTarget.style.background='rgba(255,255,255,0.02)';}}
    onMouseLeave={e=>{if(!selected)e.currentTarget.style.background='transparent';}}>
      {/* Avatar */}
      <div style={{ width:32, height:32, borderRadius:'50%', background:'linear-gradient(135deg,var(--accent),#3a7fe8)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:12, fontWeight:800, color:'#06111f', flexShrink:0 }}>
        {user.name[0]}
      </div>
      {/* Name + email */}
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ display:'flex', alignItems:'center', gap:6, flexWrap:'wrap', marginBottom:1 }}>
          <span style={{ fontSize:13, fontWeight:600, color:'var(--text-primary)' }}>{user.name}</span>
          <RoleBadge role={user.role}/>
        </div>
        <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{user.email}</div>
      </div>
      {/* Onboarding toggle */}
      <div style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:3, flexShrink:0 }} onClick={e=>e.stopPropagation()}>
        <button onClick={()=>onToggleOnboarding(user.id, !user.onboardingAllowed)} style={{
          width:36, height:20, borderRadius:999, padding:3, cursor:'pointer',
          background:user.onboardingAllowed?'#46d9a4':'rgba(255,255,255,0.10)',
          border:`1px solid ${user.onboardingAllowed?'rgba(70,217,164,0.5)':'rgba(255,255,255,0.15)'}`,
          transition:'all 0.2s', display:'flex', alignItems:'center', justifyContent:user.onboardingAllowed?'flex-end':'flex-start',
        }}>
          <div style={{ width:14, height:14, borderRadius:'50%', background:'#fff', boxShadow:'0 1px 3px rgba(0,0,0,0.3)' }}/>
        </button>
        <span style={{ fontSize:9, fontFamily:'var(--font-mono)', color:user.onboardingAllowed?'#46d9a4':'var(--text-muted)', letterSpacing:'0.08em', textTransform:'uppercase', whiteSpace:'nowrap' }}>Onboarding</span>
      </div>
      {/* Status */}
      <div style={{ textAlign:'right', flexShrink:0 }}>
        <div style={{ display:'flex', alignItems:'center', gap:4, justifyContent:'flex-end', marginBottom:1 }}>
          <span style={{ width:6, height:6, borderRadius:'50%', background:user.status==='active'?'#46d9a4':user.status==='pending'?'#ffbd66':'var(--text-muted)' }}/>
          <span style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{user.lastActive}</span>
        </div>
        <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{user.sessions} sessions</div>
      </div>
      {/* Role menu */}
      <div style={{ position:'relative', flexShrink:0 }} onClick={e=>e.stopPropagation()}>
        <button onClick={()=>setRoleOpen(o=>!o)} style={{ padding:'5px 10px', borderRadius:8, fontSize:11, cursor:'pointer', background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.12)', color:'var(--text-muted)' }}>⋯</button>
        {roleOpen && (
          <div style={{ position:'absolute', right:0, top:'100%', marginTop:4, zIndex:20, background:'rgba(14,17,22,0.98)', border:'1px solid rgba(255,255,255,0.12)', borderRadius:12, padding:6, minWidth:140, boxShadow:'0 12px 32px rgba(0,0,0,0.5)', animation:'fadeSlideUp 0.15s ease-out' }}>
            {['admin','power_user','user'].map(r=>{
              const rc=roleConfig[r];
              return <button key={r} onClick={()=>{onRoleChange(user.id,r);setRoleOpen(false);}} style={{ display:'block',width:'100%',padding:'7px 12px',borderRadius:8,textAlign:'left',background:user.role===r?`${rc.color}12`:'transparent',border:'none',cursor:'pointer',fontSize:12,color:user.role===r?rc.color:'var(--text-tertiary)',fontFamily:'var(--font-main)',transition:'all 0.12s' }}>{rc.label}</button>;
            })}
            <div style={{ height:1, background:'rgba(255,255,255,0.07)', margin:'4px 0' }}/>
            <button style={{ display:'block',width:'100%',padding:'7px 12px',borderRadius:8,textAlign:'left',background:'transparent',border:'none',cursor:'pointer',fontSize:12,color:'#ff6b7d',fontFamily:'var(--font-main)' }}>Revoke access</button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── User detail panel ─────────────────────────────────────────────────────────
function UserDetail({ user, apiKeys }) {
  if (!user) return <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100%', color:'var(--text-muted)', fontSize:13 }}>Select a user to view details</div>;
  const userKeys = apiKeys.filter(k=>k.userId===user.id);
  return (
    <div style={{ padding:'14px', overflowY:'auto', height:'100%', display:'flex', flexDirection:'column', gap:12 }} className="scrollbar-hide">
      <div style={{ padding:'12px 14px', borderRadius:14, background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.08)' }}>
        <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:8 }}>
          <div style={{ width:40, height:40, borderRadius:'50%', background:'linear-gradient(135deg,var(--accent),#3a7fe8)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:16, fontWeight:800, color:'#06111f' }}>{user.name[0]}</div>
          <div>
            <div style={{ fontSize:14, fontWeight:800, color:'#fff' }}>{user.name}</div>
            <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{user.email}</div>
          </div>
        </div>
        <div style={{ display:'flex', gap:5, flexWrap:'wrap' }}>
          <RoleBadge role={user.role}/>
          <span style={{ fontSize:10, fontFamily:'var(--font-mono)', padding:'2px 8px', borderRadius:999, color:user.onboardingAllowed?'#46d9a4':'var(--text-muted)', background:user.onboardingAllowed?'rgba(70,217,164,0.10)':'rgba(255,255,255,0.05)', border:`1px solid ${user.onboardingAllowed?'rgba(70,217,164,0.22)':'rgba(255,255,255,0.10)'}` }}>
            {user.onboardingAllowed ? '✓ Onboarding allowed' : '✕ Onboarding locked'}
          </span>
        </div>
      </div>
      {/* Stats */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8 }}>
        {[{label:'Sessions',v:user.sessions,c:'var(--accent)'},{label:'API Keys',v:user.apiKeys,c:'#c4b5fd'},{label:'Last active',v:user.lastActive,c:'var(--text-secondary)'},{label:'Status',v:user.status,c:user.status==='active'?'#46d9a4':'#ffbd66'}].map(s=>(
          <div key={s.label} style={{ padding:'9px 12px', borderRadius:11, background:'rgba(255,255,255,0.025)', border:'1px solid rgba(255,255,255,0.07)' }}>
            <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.10em', textTransform:'uppercase', marginBottom:2 }}>{s.label}</div>
            <div style={{ fontSize:14, fontWeight:700, color:s.c, textTransform:'capitalize' }}>{s.v}</div>
          </div>
        ))}
      </div>
      {/* Provider config */}
      {user.providerConfig && (
        <div style={{ padding:'11px 13px', borderRadius:12, background:'rgba(93,162,255,0.05)', border:'1px solid rgba(93,162,255,0.14)' }}>
          <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.12em', textTransform:'uppercase', marginBottom:7 }}>Provider config</div>
          {[{l:'Top provider',v:user.providerConfig.topProvider},{l:'Active providers',v:user.providerConfig.activeProviders},{l:'Local ratio',v:Math.round(user.providerConfig.localRatio*100)+'%'}].map(r=>(
            <div key={r.l} style={{ display:'flex', justifyContent:'space-between', gap:8, marginBottom:4 }}>
              <span style={{ fontSize:12, color:'var(--text-muted)' }}>{r.l}</span>
              <span style={{ fontSize:12, fontWeight:600, color:'var(--text-primary)' }}>{r.v}</span>
            </div>
          ))}
        </div>
      )}
      {/* API keys */}
      <div>
        <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.12em', textTransform:'uppercase', marginBottom:7 }}>API Keys ({userKeys.length})</div>
        <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
          {userKeys.map(k=>(
            <div key={k.id} style={{ padding:'9px 12px', borderRadius:11, background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.08)' }}>
              <div style={{ display:'flex', justifyContent:'space-between', marginBottom:2 }}>
                <span style={{ fontSize:12, fontWeight:600, color:'var(--text-primary)' }}>{k.label}</span>
                <span style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'#46d9a4' }}>{k.requests.toLocaleString()} reqs</span>
              </div>
              <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{k.key} · last used {k.lastUsed}</div>
            </div>
          ))}
          {userKeys.length===0 && <div style={{ fontSize:12, color:'var(--text-muted)', padding:'4px 0' }}>No API keys issued.</div>}
          <button style={{ padding:'7px 14px', borderRadius:9, fontSize:12, fontWeight:700, cursor:'pointer', background:'rgba(93,162,255,0.10)', border:'1px solid rgba(93,162,255,0.22)', color:'var(--accent)' }}>+ Issue new API key</button>
        </div>
      </div>
    </div>
  );
}

// ── Main AdminScreen ───────────────────────────────────────────────────────────
function AdminScreen() {
  const [users,    setUsers]    = React.useState(INITIAL_USERS);
  const [requests, setRequests] = React.useState(INITIAL_REQUESTS);
  const [apiKeys,  setApiKeys]  = React.useState(INITIAL_KEYS);
  const [selected, setSelected] = React.useState('u-1');
  const [tab,      setTab]      = React.useState('users');

  const handleRoleChange = (id, role) => setUsers(p=>p.map(u=>u.id===id?{...u,role}:u));
  const handleToggleOnboarding = (id, val) => {
    setUsers(p=>p.map(u=>u.id===id?{...u,onboardingAllowed:val}:u));
    setUserOnboardingFlag(id, val);
  };
  const handleApprove = (req) => {
    setRequests(p=>p.map(r=>r.id===req.id?{...r,status:'approved'}:r));
    setUsers(p=>p.map(u=>u.email===req.email?{...u,onboardingAllowed:true}:u));
  };
  const handleDecline = (req) => setRequests(p=>p.map(r=>r.id===req.id?{...r,status:'declined'}:r));

  const selectedUser = users.find(u=>u.id===selected);
  const pendingRequests = requests.filter(r=>r.status==='pending').length;

  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', overflow:'hidden' }}>
      {/* Header */}
      <div style={{ padding:'18px 20px 0', flexShrink:0 }}>
        <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
          <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'#ff6b7d', letterSpacing:'0.18em', textTransform:'uppercase' }}>Admin Only</div>
        </div>
        <div style={{ display:'flex', alignItems:'flex-end', justifyContent:'space-between', flexWrap:'wrap', gap:10, marginBottom:14 }}>
          <div>
            <h1 style={{ fontSize:24, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', lineHeight:1.1, marginBottom:3 }}>Admin Panel</h1>
            <p style={{ fontSize:13, color:'var(--text-tertiary)', lineHeight:1.5 }}>Users, activation, onboarding approvals, API keys.</p>
          </div>
          <div style={{ display:'flex', gap:8 }}>
            {[
              { label:'Users', value:users.length, color:'var(--accent)' },
              { label:'Active', value:users.filter(u=>u.status==='active').length, color:'#46d9a4' },
              { label:'Pending', value:pendingRequests, color:pendingRequests>0?'#ffbd66':'var(--text-muted)' },
            ].map(s=>(
              <div key={s.label} style={{ padding:'7px 12px', borderRadius:11, background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.08)', textAlign:'center' }}>
                <div style={{ fontSize:18, fontWeight:800, color:s.color, letterSpacing:'-0.03em' }}>{s.value}</div>
                <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textTransform:'uppercase', letterSpacing:'0.10em' }}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
        <div style={{ display:'flex', gap:4 }}>
          {['activation','users','api-keys'].map(t=>(
            <button key={t} onClick={()=>setTab(t)} style={{ padding:'7px 16px', borderRadius:'10px 10px 0 0', fontSize:12, fontWeight:600, cursor:'pointer', textTransform:'capitalize', transition:'all 0.15s', background:tab===t?'rgba(10,12,15,0.90)':'rgba(255,255,255,0.03)', border:`1px solid ${tab===t?'rgba(255,255,255,0.10)':'rgba(255,255,255,0.06)'}`, borderBottom:tab===t?'1px solid rgba(10,12,15,0.90)':'1px solid rgba(255,255,255,0.06)', color:tab===t?'#fff':'var(--text-muted)' }}>
              {t==='api-keys'?'API Keys':t==='activation'?'🔐 Activation':t[0].toUpperCase()+t.slice(1)}
              {t==='users' && pendingRequests>0 && <span style={{ marginLeft:6, fontSize:9, padding:'1px 5px', borderRadius:999, background:'rgba(255,189,102,0.20)', color:'#ffbd66' }}>{pendingRequests}</span>}
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
          <div style={{ display:'flex', height:'100%' }}>
            {/* Left: requests + user list */}
            <div style={{ flex:1, minWidth:0, borderRight:'1px solid rgba(255,255,255,0.07)', overflowY:'auto' }} className="scrollbar-hide">
              {/* Requests */}
              {pendingRequests > 0 && (
                <div style={{ padding:'12px 16px', borderBottom:'1px solid rgba(255,255,255,0.06)' }}>
                  <OnboardingRequests requests={requests} onApprove={handleApprove} onDecline={handleDecline}/>
                </div>
              )}
              {/* Header */}
              <div style={{ padding:'9px 16px 7px', display:'flex', alignItems:'center', justifyContent:'space-between', borderBottom:'1px solid rgba(255,255,255,0.06)' }}>
                <span style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.12em', textTransform:'uppercase' }}>{users.length} users</span>
                <div style={{ display:'flex', gap:4 }}>
                  <span style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', padding:'2px 8px' }}>Onboarding toggle = allow/block per user</span>
                  <button style={{ padding:'5px 12px', borderRadius:8, fontSize:11, fontWeight:700, cursor:'pointer', background:'rgba(93,162,255,0.12)', border:'1px solid rgba(93,162,255,0.25)', color:'var(--accent)' }}>+ Invite</button>
                </div>
              </div>
              {users.map(user=>(
                <UserRow key={user.id} user={user} onRoleChange={handleRoleChange} onToggleOnboarding={handleToggleOnboarding} selected={selected===user.id} onSelect={setSelected}/>
              ))}
            </div>
            {/* Right: detail */}
            <div style={{ width:280, flexShrink:0, overflowY:'auto' }} className="scrollbar-hide">
              <UserDetail user={selectedUser} apiKeys={apiKeys}/>
            </div>
          </div>
        )}

        {tab === 'api-keys' && (
          <div style={{ padding:'14px', overflowY:'auto', height:'100%' }}>
            <div style={{ display:'flex', justifyContent:'flex-end', marginBottom:10 }}>
              <button style={{ padding:'7px 14px', borderRadius:9, fontSize:12, fontWeight:700, cursor:'pointer', background:'rgba(93,162,255,0.12)', border:'1px solid rgba(93,162,255,0.25)', color:'var(--accent)' }}>+ Issue key</button>
            </div>
            <div style={{ borderRadius:14, border:'1px solid rgba(255,255,255,0.09)', overflow:'hidden' }}>
              {apiKeys.map((key,i)=>{
                const user=users.find(u=>u.id===key.userId);
                return (
                  <div key={key.id} style={{ display:'flex', alignItems:'center', gap:12, padding:'12px 16px', borderBottom:i<apiKeys.length-1?'1px solid rgba(255,255,255,0.05)':'none', transition:'background 0.15s' }}
                  onMouseEnter={e=>e.currentTarget.style.background='rgba(255,255,255,0.02)'}
                  onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
                    <div style={{ flex:1, minWidth:0 }}>
                      <div style={{ display:'flex', alignItems:'center', gap:7, marginBottom:2 }}>
                        <span style={{ fontSize:13, fontWeight:600, color:'var(--text-primary)' }}>{key.label}</span>
                        {user && <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>@{user.name.split(' ')[0].toLowerCase()}</span>}
                      </div>
                      <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>{key.key} · last used {key.lastUsed}</div>
                    </div>
                    <div style={{ textAlign:'right', flexShrink:0 }}>
                      <div style={{ fontSize:13, fontWeight:700, color:'var(--accent)' }}>{key.requests.toLocaleString()}</div>
                      <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>requests</div>
                    </div>
                    <button style={{ padding:'5px 10px', borderRadius:8, fontSize:11, cursor:'pointer', background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.20)', color:'#ff6b7d', flexShrink:0 }}>Revoke</button>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export { AdminScreen };
export default AdminScreen;
