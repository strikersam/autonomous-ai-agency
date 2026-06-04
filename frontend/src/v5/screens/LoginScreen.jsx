/* eslint-disable jsx-a11y/anchor-is-valid */
import React from 'react';
import { useAuth } from '../../AuthContext';

// Responsive helper — switch between side-by-side and stacked layouts
// without CSS media queries (this screen is styled inline).
function useIsWide(breakpoint = 920) {
  const get = () => (typeof window !== 'undefined' ? window.innerWidth >= breakpoint : true);
  const [wide, setWide] = React.useState(get);
  React.useEffect(() => {
    const onResize = () => setWide(window.innerWidth >= breakpoint);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [breakpoint]);
  return wide;
}

// What the agency does — shown as plain-language chips so a first-time
// visitor instantly understands the breadth without reading docs.
const AGENT_CHIPS = [
  'Writes & ships code', 'Opens & reviews PRs', 'Runs tests & CI',
  'Agile sprints', 'Portfolio planning', 'Design & UX',
  'SEO & content', 'E-commerce ops', 'Support & CRM', 'Keeps docs in sync',
];

const STEPS = [
  { n: '1', t: 'Onboard with one URL', d: 'Paste your company website. That’s the whole setup.' },
  { n: '2', t: 'It studies the business', d: 'Scans the site, detects your stack & systems, builds a living Company Graph.' },
  { n: '3', t: 'It hires the right team', d: 'A CEO agent provisions specialists — dev, design, agile, portfolio, SEO, ops…' },
  { n: '4', t: 'You ask in plain English', d: 'Agents plan, do the work, and return evidence. You approve anything that matters.' },
];


function HeroPanel({ compact }) {
  return (
    <div style={{
      flex: compact ? 'none' : '1.05',
      maxWidth: compact ? 440 : 560,
      width: '100%',
      color: '#fff',
      padding: compact ? '4px 4px 8px' : '8px 24px',
    }}>
      <div style={{
        display: 'inline-flex', alignItems: 'center', gap: 8,
        padding: '5px 12px', borderRadius: 999, marginBottom: 18,
        background: 'rgba(93,162,255,0.12)', border: '1px solid rgba(93,162,255,0.28)',
        fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase',
        color: '#9ecbff', fontFamily: 'var(--font-mono)',
      }}>
        <span style={{ width: 7, height: 7, borderRadius: 99, background: '#5da2ff', boxShadow: '0 0 10px #5da2ff' }} />
        Agency Core v5 · Self-hosted · Private
      </div>

      <h1 style={{
        fontSize: compact ? 28 : 40, lineHeight: 1.08, fontWeight: 850,
        letterSpacing: '-0.03em', margin: '0 0 14px',
      }}>
        Your autonomous<br />
        <span style={{ background: 'linear-gradient(135deg,#6CB0FF,#3A7FE8)', WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' }}>
          AI agency.
        </span>
      </h1>

      <p style={{ fontSize: compact ? 15 : 17, lineHeight: 1.5, color: 'rgba(255,255,255,0.72)', margin: '0 0 22px', maxWidth: 480 }}>
        Onboard a company with <strong style={{ color: '#fff' }}>one URL</strong> — and a CEO agent plus a fleet of
        specialists run the work: shipping code, reviewing PRs, planning sprints,
        managing the portfolio, design, SEO, content, and operations. With your
        approval on anything that matters, and your data never leaving your server.
      </p>

      {/* How it works */}
      <div style={{ display: 'grid', gap: 10, marginBottom: 22 }}>
        {STEPS.map((s) => (
          <div key={s.n} style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
            <div style={{
              flexShrink: 0, width: 26, height: 26, borderRadius: 8,
              background: 'rgba(93,162,255,0.15)', border: '1px solid rgba(93,162,255,0.3)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 13, fontWeight: 800, color: '#9ecbff', fontFamily: 'var(--font-mono)',
            }}>{s.n}</div>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: '#fff' }}>{s.t}</div>
              <div style={{ fontSize: 13, color: 'rgba(255,255,255,0.55)', lineHeight: 1.45 }}>{s.d}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Capability chips */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7 }}>
        {AGENT_CHIPS.map((c) => (
          <span key={c} style={{
            fontSize: 11.5, padding: '5px 10px', borderRadius: 999,
            background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.10)',
            color: 'rgba(255,255,255,0.7)',
          }}>{c}</span>
        ))}
      </div>
    </div>
  );
}


// LoginScreen — wired to real /api/auth/login via AuthContext
function LoginScreen() {
  const { login } = useAuth();
  const wide = useIsWide();
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

      <div style={{
        position: 'relative', zIndex: 1, width: '100%', maxWidth: wide ? 1080 : 440,
        display: 'flex', flexDirection: wide ? 'row' : 'column',
        alignItems: 'center', justifyContent: 'center',
        gap: wide ? 48 : 28,
      }}>
        <HeroPanel compact={!wide} />

        {/* Sign-in card */}
        <div style={{
          width: '100%', maxWidth: 400, flexShrink: 0,
          background: 'rgba(10,12,15,0.90)',
          border: '1px solid rgba(255,255,255,0.10)',
          borderRadius: 24, padding: '36px 32px',
          boxShadow: '0 32px 80px rgba(0,0,0,0.5)',
          backdropFilter: 'blur(20px)',
        }}>
          {/* Logo */}
          <div style={{ display:'flex', flexDirection:'column', alignItems:'center', marginBottom:24 }}>
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
            <div style={{ fontSize:20, fontWeight:800, color:'#fff', letterSpacing:'-0.02em' }}>Agency Core</div>
            <div style={{ fontSize:12, color:'rgba(255,255,255,0.4)', marginTop:3, fontFamily:'var(--font-mono)' }}>Sign in to your agency</div>
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

            <p style={{ fontSize:11.5, color:'rgba(255,255,255,0.4)', textAlign:'center', margin:'6px 0 0', lineHeight:1.5 }}>
              New here? After signing in, onboard a company with just its website URL
              and your AI agency provisions itself.
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}

export default LoginScreen;
