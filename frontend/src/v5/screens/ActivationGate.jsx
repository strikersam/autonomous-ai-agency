/* eslint-disable no-unused-vars */
/**
 * ActivationGate.jsx — Instance activation wizard shown before any login.
 *
 * Flow:
 *   1. Fetch GET /api/activation/status  (public, no auth needed)
 *   2. If activated → render children (normal app)
 *   3. If not activated → show this screen:
 *        • Display instanceId
 *        • Explain the email-to-activate process
 *        • Input for pasting the activation token
 *        • POST /api/activation/activate on submit
 *        • On success → reload
 */
import React from 'react';
import api from '../../api';

function CopyButton({ text, label }) {
  const [copied, setCopied] = React.useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }).catch(() => {
      // Fallback for non-HTTPS
      const el = document.createElement('textarea');
      el.value = text;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <button onClick={handleCopy}
      style={{ padding:'6px 14px', borderRadius:8, background: copied ? 'rgba(70,217,164,0.15)' : 'rgba(93,162,255,0.10)', border:`1px solid ${copied ? 'rgba(70,217,164,0.40)' : 'rgba(93,162,255,0.30)'}`, color: copied ? '#46d9a4' : 'var(--accent, #6CB0FF)', fontSize:12, fontFamily:'var(--font-mono, monospace)', cursor:'pointer', transition:'all 0.2s', flexShrink:0 }}>
      {copied ? '✓ Copied' : (label || 'Copy')}
    </button>
  );
}

function Step({ num, title, children, done }) {
  return (
    <div style={{ display:'flex', gap:14, marginBottom:20 }}>
      <div style={{ width:28, height:28, borderRadius:'50%', background: done ? 'rgba(70,217,164,0.15)' : 'rgba(93,162,255,0.12)', border:`2px solid ${done ? 'rgba(70,217,164,0.50)' : 'rgba(93,162,255,0.40)'}`, display:'flex', alignItems:'center', justifyContent:'center', fontSize:12, fontWeight:800, color: done ? '#46d9a4' : '#6CB0FF', flexShrink:0, marginTop:2 }}>
        {done ? '✓' : num}
      </div>
      <div style={{ flex:1 }}>
        <div style={{ fontSize:14, fontWeight:700, color:'#fff', marginBottom:6 }}>{title}</div>
        {children}
      </div>
    </div>
  );
}

export default function ActivationGate({ children }) {
  const [status,   setStatus]   = React.useState(null);   // null = loading
  const [statusError, setStatusError] = React.useState('');
  const [token,    setToken]    = React.useState('');
  const [error,    setError]    = React.useState('');
  const [loading,  setLoading]  = React.useState(false);
  const [success,  setSuccess]  = React.useState(false);

  React.useEffect(() => {
    api.get('/api/activation/status')
      .then(r => { setStatusError(''); setStatus(r.data); })
      .catch(e => {
        // Don't disguise an unreachable backend as "not activated" — surface it.
        setStatusError(e.response?.data?.detail || 'Unable to reach the activation service. Is the backend running?');
        setStatus({ activated: false, instance_id: 'unknown', register_email: '' });
      });
  }, []);

  if (status === null) {
    return (
      <div style={{ minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'#06111f' }}>
        <div style={{ width:20, height:20, border:'2px solid rgba(255,255,255,0.15)', borderTopColor:'#6CB0FF', borderRadius:'50%', animation:'spin 0.8s linear infinite' }}/>
      </div>
    );
  }

  if (status.activated) return children;

  const handleActivate = async () => {
    if (!token.trim()) return;
    setLoading(true); setError('');
    try {
      const r = await api.post('/api/activation/activate', { token: token.trim() });
      if (r.data.success) {
        setSuccess(true);
        setTimeout(() => window.location.reload(), 1500);
      } else {
        setError(r.data.error || 'Activation failed. Check the token and try again.');
      }
    } catch (e) {
      setError(e.response?.data?.detail || 'Network error. Is the server running?');
    } finally {
      setLoading(false);
    }
  };

  const iid = status.instance_id || 'unknown';
  const contactEmail = status.register_email || 'strikersam@gmail.com';
  const mailtoSubject = encodeURIComponent('Autonomous AI Agency Activation Request');
  const mailtoBody = encodeURIComponent(
    `Hello,\n\nI'd like to activate my Autonomous AI Agency instance.\n\nInstance ID: ${iid}\n\nPlease send me an activation code.\n\nThank you.`
  );

  return (
    <div style={{ minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'#06111f', padding:'24px 16px', fontFamily:'var(--font-main, system-ui)' }}>
      <div style={{ width:'100%', maxWidth:520 }}>
        {/* Header */}
        <div style={{ textAlign:'center', marginBottom:32 }}>
          <div style={{ fontSize:11, fontFamily:'var(--font-mono, monospace)', color:'rgba(93,162,255,0.7)', letterSpacing:'0.18em', textTransform:'uppercase', marginBottom:10 }}>
            Autonomous AI Agency — Instance Activation
          </div>
          <div style={{ width:52, height:52, borderRadius:16, background:'rgba(93,162,255,0.10)', border:'1px solid rgba(93,162,255,0.25)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:24, margin:'0 auto 14px' }}>🔑</div>
          <h1 style={{ fontSize:26, fontWeight:800, color:'#fff', letterSpacing:'-0.04em', margin:'0 0 8px' }}>Activate this instance</h1>
          <p style={{ fontSize:14, color:'rgba(255,255,255,0.5)', lineHeight:1.6, margin:0, maxWidth:400, marginLeft:'auto', marginRight:'auto' }}>
            This Autonomous AI Agency instance is not yet activated. Follow the three steps below to unlock onboarding and start using the platform.
          </p>
        </div>

        {statusError && (
          <div style={{ marginBottom:16, padding:'10px 14px', borderRadius:12, background:'rgba(255,189,102,0.07)', border:'1px solid rgba(255,189,102,0.25)', color:'#ffbd66', fontSize:12, lineHeight:1.5, textAlign:'center' }}>
            ⚠ {statusError}
          </div>
        )}

        {/* Card */}
        <div style={{ background:'rgba(255,255,255,0.03)', border:'1px solid rgba(255,255,255,0.08)', borderRadius:20, padding:'28px 24px' }}>

          <Step num={1} title="Copy your Instance ID">
            <div style={{ display:'flex', gap:8, alignItems:'center', padding:'10px 14px', borderRadius:12, background:'rgba(0,0,0,0.25)', border:'1px solid rgba(255,255,255,0.08)', marginBottom:4 }}>
              <code style={{ flex:1, fontSize:12, fontFamily:'var(--font-mono, monospace)', color:'#a0b4d0', wordBreak:'break-all', lineHeight:1.5 }}>{iid}</code>
              <CopyButton text={iid} label="Copy ID" />
            </div>
            <div style={{ fontSize:11, color:'rgba(255,255,255,0.3)', fontFamily:'var(--font-mono, monospace)' }}>Unique to this server installation</div>
          </Step>

          <Step num={2} title={`Email the Instance ID to ${contactEmail}`}>
            <p style={{ fontSize:13, color:'rgba(255,255,255,0.5)', lineHeight:1.6, margin:'0 0 10px' }}>
              Send your Instance ID to the repo owner. You'll receive a signed activation code by reply — usually within 24 hours.
            </p>
            <a href={`mailto:${contactEmail}?subject=${mailtoSubject}&body=${mailtoBody}`}
              style={{ display:'inline-flex', alignItems:'center', gap:7, padding:'8px 16px', borderRadius:10, background:'rgba(93,162,255,0.10)', border:'1px solid rgba(93,162,255,0.25)', color:'#6CB0FF', fontSize:13, fontWeight:600, textDecoration:'none', transition:'all 0.2s' }}>
              ✉️ Open email draft
            </a>
          </Step>

          <Step num={3} title="Paste the activation code">
            <textarea
              value={token}
              onChange={e => setToken(e.target.value)}
              rows={4}
              placeholder="Paste the signed activation code here…"
              style={{ width:'100%', padding:'12px 14px', borderRadius:12, background:'rgba(0,0,0,0.20)', border:`1px solid ${error ? 'rgba(255,107,125,0.40)' : 'rgba(255,255,255,0.10)'}`, color:'#fff', fontSize:12, fontFamily:'var(--font-mono, monospace)', outline:'none', resize:'vertical', lineHeight:1.6, marginBottom:8, boxSizing:'border-box', transition:'border-color 0.2s' }}
              onFocus={e => e.target.style.borderColor = 'rgba(93,162,255,0.45)'}
              onBlur={e => e.target.style.borderColor = error ? 'rgba(255,107,125,0.40)' : 'rgba(255,255,255,0.10)'}
            />
            {error && (
              <div style={{ padding:'9px 12px', borderRadius:10, background:'rgba(255,107,125,0.07)', border:'1px solid rgba(255,107,125,0.22)', color:'#ff8a97', fontSize:12, marginBottom:10, lineHeight:1.5 }}>
                ⚠ {error}
              </div>
            )}
            {success && (
              <div style={{ padding:'9px 12px', borderRadius:10, background:'rgba(70,217,164,0.08)', border:'1px solid rgba(70,217,164,0.25)', color:'#46d9a4', fontSize:13, fontWeight:600, marginBottom:10 }}>
                ✓ Activation successful — reloading…
              </div>
            )}
            <button
              onClick={handleActivate}
              disabled={loading || !token.trim() || success}
              style={{ width:'100%', padding:'13px 0', borderRadius:12, background: success ? 'rgba(70,217,164,0.15)' : 'linear-gradient(135deg,#6CB0FF,#4F93FF)', color: success ? '#46d9a4' : '#06111f', fontSize:14, fontWeight:800, border:'none', cursor: loading || !token.trim() || success ? 'not-allowed' : 'pointer', opacity: loading || !token.trim() ? 0.55 : 1, transition:'all 0.2s', display:'flex', alignItems:'center', justifyContent:'center', gap:8 }}>
              {loading ? (
                <><div style={{ width:14, height:14, border:'2px solid rgba(0,0,0,0.2)', borderTopColor:'#06111f', borderRadius:'50%', animation:'spin 0.8s linear infinite' }}/> Verifying…</>
              ) : success ? '✓ Activated' : '→ Activate instance'}
            </button>
          </Step>
        </div>

        {/* Owner / self-host note */}
        <div style={{ marginTop:16, padding:'12px 16px', borderRadius:12, background:'rgba(70,217,164,0.05)', border:'1px solid rgba(70,217,164,0.18)' }}>
          <div style={{ fontSize:12, fontWeight:700, color:'#46d9a4', marginBottom:4 }}>Own this instance? Activate it yourself.</div>
          <div style={{ fontSize:12, color:'rgba(255,255,255,0.5)', lineHeight:1.6 }}>
            Set <code style={{ fontFamily:'var(--font-mono, monospace)', color:'#a0b4d0' }}>ACTIVATION_REQUIRED=false</code> in the backend
            environment to unlock onboarding, or run <code style={{ fontFamily:'var(--font-mono, monospace)', color:'#a0b4d0' }}>python scripts/activate.py</code> to
            mint your own signed code. See <code style={{ fontFamily:'var(--font-mono, monospace)', color:'#a0b4d0' }}>docs/runbooks/activation.md</code>.
          </div>
        </div>

        {/* Footer note */}
        <p style={{ textAlign:'center', fontSize:11, color:'rgba(255,255,255,0.2)', marginTop:20, lineHeight:1.6, fontFamily:'var(--font-mono, monospace)' }}>
          Activation is tied to this Instance ID. If you reinstall, you'll need a new code.<br/>
          Your code is cryptographically signed — it cannot be forged or reused across instances.
        </p>
      </div>
    </div>
  );
}
