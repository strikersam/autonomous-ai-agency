/* eslint-disable jsx-a11y/anchor-is-valid */
import React from 'react';
import { useAuth } from '../../AuthContext';

// LoginScreen — wired to real /api/auth/login via AuthContext
function LoginScreen() {
  const { login } = useAuth();
  const [email, setEmail]       = React.useState('');
  const [password, setPassword] = React.useState('');
  const [loading, setLoading]   = React.useState(false);
  const [error, setError]       = React.useState('');

  const handleSubmit = async (e) => {
    e && e.preventDefault();
    if (!email.trim() || !password.trim()) { setError('Enter your email and password.'); return; }
    setLoading(true); setError('');
    try {
      await login(email.trim(), password);
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Login failed. Check your credentials.';
      setError(msg);
    } finally {
      setLoading(false);
    }
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
          <div style={{ fontSize:20, fontWeight:800, color:'#fff', letterSpacing:'-0.02em' }}>LLM Relay</div>
          <div style={{ fontSize:12, color:'rgba(255,255,255,0.4)', marginTop:3, fontFamily:'var(--font-mono)' }}>Agency Core v5</div>
        </div>

        <form onSubmit={handleSubmit} style={{ display:'flex', flexDirection:'column', gap:14 }}>
          <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
            <label style={{ fontSize:11, fontWeight:700, color:'rgba(255,255,255,0.5)', letterSpacing:'0.06em', textTransform:'uppercase' }}>Email</label>
            <input
              type="email" value={email} onChange={e => setEmail(e.target.value)}
              placeholder="you@yourcompany.com" autoComplete="email" autoFocus
              style={{ width:'100%', padding:'11px 14px', borderRadius:12, fontSize:14, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', outline:'none' }}
              onFocus={e => e.target.style.borderColor='rgba(93,162,255,0.5)'}
              onBlur={e => e.target.style.borderColor='rgba(255,255,255,0.10)'}
            />
          </div>
          <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
            <label style={{ fontSize:11, fontWeight:700, color:'rgba(255,255,255,0.5)', letterSpacing:'0.06em', textTransform:'uppercase' }}>Password</label>
            <input
              type="password" value={password} onChange={e => setPassword(e.target.value)}
              placeholder="••••••••" autoComplete="current-password"
              style={{ width:'100%', padding:'11px 14px', borderRadius:12, fontSize:14, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.10)', color:'#fff', outline:'none' }}
              onFocus={e => e.target.style.borderColor='rgba(93,162,255,0.5)'}
              onBlur={e => e.target.style.borderColor='rgba(255,255,255,0.10)'}
            />
          </div>

          {error && (
            <div style={{ padding:'10px 14px', borderRadius:10, background:'rgba(255,107,125,0.10)', border:'1px solid rgba(255,107,125,0.25)', color:'#ff6b7d', fontSize:13 }}>
              {error}
            </div>
          )}

          <button
            type="submit" disabled={loading}
            style={{
              width:'100%', padding:'13px', borderRadius:14, fontSize:14, fontWeight:700,
              background: loading ? 'rgba(93,162,255,0.3)' : 'linear-gradient(135deg,#6CB0FF 0%,#3A7FE8 100%)',
              border:'none', color:'#fff', cursor: loading ? 'not-allowed' : 'pointer',
              boxShadow: loading ? 'none' : '0 4px 18px rgba(93,162,255,0.35)',
              transition:'all 0.2s ease', marginTop:4,
            }}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </div>
    </div>
  );
}

export default LoginScreen;
