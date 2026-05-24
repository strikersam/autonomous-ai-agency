/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';


// login.jsx — LLM Relay V5.0 Sign In

function LoginScreen({ onLogin }) {
  const [email, setEmail]       = React.useState('admin@llmrelay.local');
  const [password, setPassword] = React.useState('');
  const [loading, setLoading]   = React.useState(false);
  const [error, setError]       = React.useState('');

  const handleSubmit = (e) => {
    e && e.preventDefault();
    if (!email.trim() || !password.trim()) { setError('Enter your email and password.'); return; }
    setLoading(true); setError('');
    setTimeout(() => { setLoading(false); onLogin && onLogin({ email, role: 'admin', name: 'Sam Striker' }); }, 900);
  };

  return (
    <div style={{
      minHeight: '100dvh', display: 'flex', flexDirection: 'column',
      background: 'radial-gradient(circle at top center, rgba(93,162,255,0.13), transparent 40%), linear-gradient(180deg,#050608 0%,#020304 100%)',
      alignItems: 'center', justifyContent: 'center', padding: '24px 16px',
      position: 'relative', overflow: 'hidden',
    }}>
      {/* Background grid */}
      <div style={{ position:'absolute',inset:0,pointerEvents:'none',opacity:0.03,backgroundImage:'linear-gradient(rgba(255,255,255,0.12) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,0.12) 1px,transparent 1px)',backgroundSize:'28px 28px' }}/>

      {/* Card */}
      <div style={{
        width: '100%', maxWidth: 400,
        background: 'rgba(10,12,15,0.90)',
        border: '1px solid rgba(255,255,255,0.10)',
        borderRadius: 24, padding: '36px 32px',
        boxShadow: '0 32px 80px rgba(0,0,0,0.5)',
        backdropFilter: 'blur(20px)',
        animation: 'fadeSlideUp 0.4s ease-out',
      }}>
        {/* Logo */}
        <div style={{ display:'flex', flexDirection:'column', alignItems:'center', marginBottom:28 }}>
          <div style={{
            width:52, height:52, borderRadius:16, marginBottom:14,
            background:'linear-gradient(135deg,#6CB0FF 0%,#3A7FE8 100%)',
            boxShadow:'0 8px 28px rgba(93,162,255,0.32)',
            display:'flex', alignItems:'center', justifyContent:'center',
          }}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/>
              <path d="M15 2v2M15 20v2M9 2v2M9 20v2M2 15h2M2 9h2M20 15h2M20 9h2"/>
            </svg>
          </div>
          <div style={{ fontSize:22, fontWeight:900, color:'#fff', letterSpacing:'-0.04em', lineHeight:1 }}>LLM Relay</div>
          <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.18em', textTransform:'uppercase', marginTop:4 }}>V5.0 · Agency Core</div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display:'flex', flexDirection:'column', gap:14 }}>
          {error && (
            <div style={{ padding:'9px 12px', borderRadius:10, background:'rgba(255,107,125,0.08)', border:'1px solid rgba(255,107,125,0.22)', fontSize:12, color:'#ff6b7d', animation:'fadeSlideUp 0.2s ease-out' }}>
              {error}
            </div>
          )}

          <div>
            <label style={{ display:'block', fontSize:11, fontWeight:600, color:'var(--text-tertiary)', marginBottom:6, letterSpacing:'0.05em' }}>Email</label>
            <input type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="admin@llmrelay.local"
              style={{ width:'100%', padding:'11px 14px', borderRadius:12, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff', fontSize:14, outline:'none', fontFamily:'var(--font-main)', transition:'border-color 0.2s' }}
              onFocus={e => e.target.style.borderColor='rgba(93,162,255,0.55)'}
              onBlur={e => e.target.style.borderColor='rgba(255,255,255,0.12)'}/>
          </div>

          <div>
            <label style={{ display:'block', fontSize:11, fontWeight:600, color:'var(--text-tertiary)', marginBottom:6, letterSpacing:'0.05em' }}>Password</label>
            <input type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••••"
              style={{ width:'100%', padding:'11px 14px', borderRadius:12, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff', fontSize:14, outline:'none', fontFamily:'var(--font-main)', transition:'border-color 0.2s' }}
              onFocus={e => e.target.style.borderColor='rgba(93,162,255,0.55)'}
              onBlur={e => e.target.style.borderColor='rgba(255,255,255,0.12)'}/>
          </div>

          <button type="submit" disabled={loading} style={{
            marginTop:4, padding:'13px', borderRadius:14, fontSize:14, fontWeight:800, cursor:'pointer',
            background:'linear-gradient(135deg,#6CB0FF 0%,#4F93FF 100%)',
            color:'#06111f', border:'none', boxShadow:'0 8px 24px rgba(93,162,255,0.28)',
            opacity: loading ? 0.7 : 1, transition:'all 0.2s ease',
            display:'flex', alignItems:'center', justifyContent:'center', gap:8,
          }}>
            {loading ? <><div style={{ width:14,height:14,border:'2px solid rgba(0,0,0,0.2)',borderTopColor:'#06111f',borderRadius:'50%',animation:'spin 0.8s linear infinite' }}/>Signing in…</> : 'Sign in →'}
          </button>
        </form>

        {/* Divider */}
        <div style={{ display:'flex', alignItems:'center', gap:10, margin:'20px 0 16px' }}>
          <div style={{ flex:1, height:1, background:'rgba(255,255,255,0.08)' }}/>
          <span style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)' }}>or continue with</span>
          <div style={{ flex:1, height:1, background:'rgba(255,255,255,0.08)' }}/>
        </div>

        {/* Social */}
        <div style={{ display:'flex', gap:8 }}>
          {[
            { label:'GitHub', icon:'⎇' },
            { label:'Google', icon:'◎' },
            { label:'SSO',    icon:'◈' },
          ].map(s => (
            <button key={s.label} style={{
              flex:1, padding:'10px 8px', borderRadius:12, fontSize:12, fontWeight:600, cursor:'pointer',
              background:'rgba(255,255,255,0.04)', border:'1px solid rgba(255,255,255,0.10)',
              color:'var(--text-secondary)', display:'flex', alignItems:'center', justifyContent:'center', gap:5,
              transition:'all 0.15s ease',
            }}
            onMouseEnter={e => { e.currentTarget.style.background='rgba(255,255,255,0.08)'; e.currentTarget.style.color='#fff'; }}
            onMouseLeave={e => { e.currentTarget.style.background='rgba(255,255,255,0.04)'; e.currentTarget.style.color='var(--text-secondary)'; }}>
              <span style={{ fontSize:13 }}>{s.icon}</span>{s.label}
            </button>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div style={{ marginTop:20, fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', textAlign:'center', lineHeight:1.8 }}>
        <span style={{ color:'rgba(93,162,255,0.7)' }}>LLM Relay V5.0</span> · Self-hosted · Your data stays yours<br/>
        <a href="#" style={{ color:'var(--text-muted)', textDecoration:'none' }}>Docs</a>
        {' · '}
        <a href="#" style={{ color:'var(--text-muted)', textDecoration:'none' }}>GitHub</a>
      </div>
    </div>
  );
}

export { LoginScreen };
export default LoginScreen;
