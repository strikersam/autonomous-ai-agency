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
import Glyph from '../components/ui/Glyph';
import api, { fmtErr } from '../../api';

function CopyButton({ text, label }) {
  const [copied, setCopied] = React.useState(false);
  // BUG-18: mounted guard so setTimeout(() => setCopied(false), ...)
  // doesn't update state after CopyButton unmounts.
  const mountedRef = React.useRef(true);
  React.useEffect(() => () => { mountedRef.current = false; }, []);
  const handleCopy = () => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => { if (mountedRef.current) setCopied(false); }, 2000);
    }).catch(() => {
      // Fallback for non-HTTPS
      const el = document.createElement('textarea');
      el.value = text;
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
      setCopied(true);
      setTimeout(() => { if (mountedRef.current) setCopied(false); }, 2000);
    });
  };
  return (
    <button onClick={handleCopy}
      style={{ padding:'6px 14px', borderRadius:8, background: copied ? 'color-mix(in oklab, var(--success) 15%, transparent)' : 'color-mix(in oklab, var(--accent) 10%, transparent)', border:`1px solid ${copied ? 'color-mix(in oklab, var(--success) 40%, transparent)' : 'color-mix(in oklab, var(--accent) 30%, transparent)'}`, color: copied ? 'var(--success)' : 'var(--accent, var(--accent))', fontSize:13, fontFamily:'var(--font-mono, monospace)', cursor:'pointer', transition:'all 0.2s', flexShrink:0 }}>
      {copied ? '✓ Copied' : (label || 'Copy')}
    </button>
  );
}

function Step({ num, title, children, done }) {
  return (
    <div style={{ display:'flex', gap:14, marginBottom:20 }}>
      <div style={{ width:28, height:28, borderRadius:'50%', background: done ? 'color-mix(in oklab, var(--success) 15%, transparent)' : 'color-mix(in oklab, var(--accent) 12%, transparent)', border:`2px solid ${done ? 'color-mix(in oklab, var(--success) 50%, transparent)' : 'color-mix(in oklab, var(--accent) 40%, transparent)'}`, display:'flex', alignItems:'center', justifyContent:'center', fontSize:13, fontWeight:700, color: done ? 'var(--success)' : 'var(--accent)', flexShrink:0, marginTop:2 }}>
        {done ? '✓' : num}
      </div>
      <div style={{ flex:1 }}>
        <div style={{ fontSize:14, fontWeight:700, color:'var(--text-primary)', marginBottom:6 }}>{title}</div>
        {children}
      </div>
    </div>
  );
}

export default function ActivationGate({ children }) {
  // Instant paint: a previously confirmed activation renders children
  // immediately while the status revalidates in the background. Without this,
  // every fresh page load blocks on a full backend round trip (30-60s on a
  // cold Render dyno) showing nothing but a spinner on a dark screen.
  const cachedActivated = React.useMemo(() => {
    try { return localStorage.getItem('activation_ok') === '1'; } catch { return false; }
  }, []);
  const [status,   setStatus]   = React.useState(cachedActivated ? { activated: true } : null);   // null = loading
  const [statusError, setStatusError] = React.useState('');
  const [token,    setToken]    = React.useState('');
  const [error,    setError]    = React.useState('');
  const [loading,  setLoading]  = React.useState(false);
  const [success,  setSuccess]  = React.useState(false);

  React.useEffect(() => {
    api.get('/api/activation/status')
      .then(r => {
        setStatusError('');
        setStatus(r.data);
        try { localStorage.setItem('activation_ok', r.data?.activated ? '1' : '0'); } catch {}
      })
      .catch(e => {
        // Don't disguise an unreachable backend as "not activated" — surface it.
        // If we already painted from cache, keep the app usable rather than
        // downgrading to the activation wall on a transient network error.
        if (!cachedActivated) {
          setStatusError(fmtErr(e.response?.data?.detail) || 'Unable to reach the activation service. Is the backend running?');
          setStatus({ activated: false, instance_id: 'unknown', register_email: '' });
        }
      });
  }, [cachedActivated]);

  if (status === null) {
    return (
      <div style={{ minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'var(--on-accent)' }}>
        <div style={{ width:20, height:20, border:'2px solid color-mix(in oklab, var(--ink) 15%, transparent)', borderTopColor:'var(--accent)', borderRadius:'50%', animation:'spin 0.8s linear infinite' }}/>
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
      setError(fmtErr(e.response?.data?.detail) || 'Network error. Is the server running?');
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
    <div style={{ minHeight:'100vh', display:'flex', alignItems:'center', justifyContent:'center', background:'var(--on-accent)', padding:'24px 16px', fontFamily:'var(--font-main, system-ui)' }}>
      <div style={{ width:'100%', maxWidth:520 }}>
        {/* Header */}
        <div style={{ textAlign:'center', marginBottom:32 }}>
          <div style={{ fontSize:13, fontFamily:'var(--font-mono, monospace)', color:'color-mix(in oklab, var(--accent) 70%, transparent)', marginBottom:10 }}>
            Autonomous AI Agency — Instance Activation
          </div>
          <div style={{ width:52, height:52, borderRadius:16, background:'color-mix(in oklab, var(--accent) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 25%, transparent)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:24, margin:'0 auto 14px' }}><Glyph g="🔑"/></div>
          <h1 style={{ fontSize:26, fontWeight:700, color:'var(--text-primary)', letterSpacing:'-0.04em', margin:'0 0 8px' }}>Activate this instance</h1>
          <p style={{ fontSize:14, color:'color-mix(in oklab, var(--ink) 50%, transparent)', lineHeight:1.6, margin:0, maxWidth:400, marginLeft:'auto', marginRight:'auto' }}>
            This Autonomous AI Agency instance is not yet activated. Follow the three steps below to unlock onboarding and start using the platform.
          </p>
        </div>

        {statusError && (
          <div style={{ marginBottom:16, padding:'10px 14px', borderRadius:12, background:'color-mix(in oklab, var(--warning) 7%, transparent)', border:'1px solid color-mix(in oklab, var(--warning) 25%, transparent)', color:'var(--warning)', fontSize:13, lineHeight:1.5, textAlign:'center' }}>
            <Glyph g="⚠"/> {statusError}
          </div>
        )}

        {/* Card */}
        <div style={{ background:'color-mix(in oklab, var(--ink) 3%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)', borderRadius:14, padding:'28px 24px' }}>

          <Step num={1} title="Copy your instance ID">
            <div style={{ display:'flex', gap:8, alignItems:'center', padding:'10px 14px', borderRadius:12, background:'color-mix(in oklab, var(--shade) 25%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)', marginBottom:4 }}>
              <code style={{ flex:1, fontSize:13, fontFamily:'var(--font-mono, monospace)', color:'var(--text-tertiary)', wordBreak:'break-all', lineHeight:1.5 }}>{iid}</code>
              <CopyButton text={iid} label="Copy ID" />
            </div>
            <div style={{ fontSize:13, color:'color-mix(in oklab, var(--ink) 30%, transparent)', fontFamily:'var(--font-mono, monospace)' }}>Unique to this server installation</div>
          </Step>

          <Step num={2} title={`Email the Instance ID to ${contactEmail}`}>
            <p style={{ fontSize:14, color:'color-mix(in oklab, var(--ink) 50%, transparent)', lineHeight:1.6, margin:'0 0 10px' }}>
              Send your Instance ID to the repo owner. You'll receive a signed activation code by reply — usually within 24 hours.
            </p>
            <a href={`mailto:${contactEmail}?subject=${mailtoSubject}&body=${mailtoBody}`}
              style={{ display:'inline-flex', alignItems:'center', gap:7, padding:'8px 16px', borderRadius:10, background:'color-mix(in oklab, var(--accent) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 25%, transparent)', color:'var(--accent)', fontSize:14, fontWeight:600, textDecoration:'none', transition:'all 0.2s' }}>
              <Glyph g="✉️"/> Open email draft
            </a>
          </Step>

          <Step num={3} title="Paste the activation code">
            <textarea
              value={token}
              onChange={e => setToken(e.target.value)}
              rows={4}
              placeholder="Paste the signed activation code here…"
              style={{ width:'100%', padding:'12px 14px', borderRadius:12, background:'color-mix(in oklab, var(--shade) 20%, transparent)', border:`1px solid ${error ? 'color-mix(in oklab, var(--danger) 40%, transparent)' : 'color-mix(in oklab, var(--ink) 10%, transparent)'}`, color:'var(--text-primary)', fontSize:13, fontFamily:'var(--font-mono, monospace)', outline:'none', resize:'vertical', lineHeight:1.6, marginBottom:8, boxSizing:'border-box', transition:'border-color 0.2s' }}
              onFocus={e => e.target.style.borderColor = 'color-mix(in oklab, var(--accent) 45%, transparent)'}
              onBlur={e => e.target.style.borderColor = error ? 'color-mix(in oklab, var(--danger) 40%, transparent)' : 'color-mix(in oklab, var(--ink) 10%, transparent)'}
            />
            {error && (
              <div style={{ padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--danger) 7%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 22%, transparent)', color:'var(--danger)', fontSize:13, marginBottom:10, lineHeight:1.5 }}>
                <Glyph g="⚠"/> {error}
              </div>
            )}
            {success && (
              <div style={{ padding:'9px 12px', borderRadius:10, background:'color-mix(in oklab, var(--success) 8%, transparent)', border:'1px solid color-mix(in oklab, var(--success) 25%, transparent)', color:'var(--success)', fontSize:14, fontWeight:600, marginBottom:10 }}>
                ✓ Activation successful — reloading…
              </div>
            )}
            <button
              onClick={handleActivate}
              disabled={loading || !token.trim() || success}
              style={{ width:'100%', padding:'13px 0', borderRadius:12, background: success ? 'color-mix(in oklab, var(--success) 15%, transparent)' : 'linear-gradient(135deg,var(--accent),var(--accent))', color: success ? 'var(--success)' : 'var(--on-accent)', fontSize:14, fontWeight:700, border:'none', cursor: loading || !token.trim() || success ? 'not-allowed' : 'pointer', opacity: loading || !token.trim() ? 0.55 : 1, transition:'all 0.2s', display:'flex', alignItems:'center', justifyContent:'center', gap:8 }}>
              {loading ? (
                <><div style={{ width:14, height:14, border:'2px solid color-mix(in oklab, var(--shade) 20%, transparent)', borderTopColor:'var(--on-accent)', borderRadius:'50%', animation:'spin 0.8s linear infinite' }}/> Verifying…</>
              ) : success ? '✓ Activated' : '→ Activate instance'}
            </button>
          </Step>
        </div>

        {/* Owner / self-host note */}
        <div style={{ marginTop:16, padding:'12px 16px', borderRadius:12, background:'color-mix(in oklab, var(--success) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--success) 18%, transparent)' }}>
          <div style={{ fontSize:13, fontWeight:700, color:'var(--success)', marginBottom:4 }}>Own this instance? Activate it yourself.</div>
          <div style={{ fontSize:13, color:'color-mix(in oklab, var(--ink) 50%, transparent)', lineHeight:1.6 }}>
            Set <code style={{ fontFamily:'var(--font-mono, monospace)', color:'var(--text-tertiary)' }}>ACTIVATION_REQUIRED=false</code> in the backend
            environment to unlock onboarding, or run <code style={{ fontFamily:'var(--font-mono, monospace)', color:'var(--text-tertiary)' }}>python scripts/activate.py</code> to
            mint your own signed code. See <code style={{ fontFamily:'var(--font-mono, monospace)', color:'var(--text-tertiary)' }}>docs/runbooks/activation.md</code>.
          </div>
        </div>

        {/* Footer note */}
        <p style={{ textAlign:'center', fontSize:13, color:'color-mix(in oklab, var(--ink) 20%, transparent)', marginTop:20, lineHeight:1.6, fontFamily:'var(--font-mono, monospace)' }}>
          Activation is tied to this Instance ID. If you reinstall, you'll need a new code.<br/>
          Your code is cryptographically signed — it cannot be forged or reused across instances.
        </p>
      </div>
    </div>
  );
}
