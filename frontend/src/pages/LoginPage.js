import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { fmtErr, getBackendUrl } from '../api';
import { AlertCircle, GitFork as Github, CheckCircle, Bot, Database, ChevronDown, ShieldCheck } from 'lucide-react';

const GoogleIcon = () => (
  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" aria-hidden="true">
    <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
    <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
    <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/>
    <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/>
  </svg>
);

function FieldGroup({ label, htmlFor, children }) {
  return (
    <div className="login-field">
      <label htmlFor={htmlFor}>{label}</label>
      {children}
    </div>
  );
}

function TextInput({ id, type, value, onChange, placeholder, required, testId, autoComplete }) {
  return (
    <input
      id={id}
      type={type}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      required={required}
      autoComplete={autoComplete}
      data-testid={testId}
      className="app-input"
    />
  );
}

// Set by the backend when a social-login start URL is hit for a provider this
// server has no OAuth client for (it used to answer with a raw 503 page).
const OAUTH_ERRORS = {
  github_not_configured: "GitHub sign-in isn't set up on this server yet. Ask your admin, or use email & password if you have an account.",
  google_not_configured: "Google sign-in isn't set up on this server yet. Ask your admin, or use email & password if you have an account.",
};

function readOauthError() {
  try {
    return OAUTH_ERRORS[new URLSearchParams(window.location.search).get('oauth_error')] || '';
  } catch {
    return '';
  }
}

export default function LoginPage() {
  const { login } = useAuth();
  const backendUrl = getBackendUrl();
  const hasBackendConfig = Boolean(backendUrl);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [oauthError] = useState(readOauthError);
  const [loading, setLoading] = useState(false);
  const [socialLoading, setSocialLoading] = useState(null); // null | 'github' | 'google'
  // Email/password sign-in only works for the admin account and users an
  // admin has created directly (there is no public self-registration
  // endpoint). It's collapsed behind this toggle by default so general
  // users are funneled to social login instead of assuming they need a
  // password the platform never gave them.
  const [showAdminLogin, setShowAdminLogin] = useState(false);

  // Social login URLs use a per-click nonce path segment to bypass
  // Cloudflare's CDN cache. The CDN cached the SPA's index.html at
  // /api/auth/*/login and /api/auth/*/start for navigation requests
  // (sec-fetch-dest: document). By appending a unique nonce to the path
  // (/api/auth/<provider>/start/<random>), each click generates a URL the
  // CDN has never seen → the worker always proxies to the backend → the
  // backend returns the correct 307 redirect to GitHub/Google. The nonce
  // is ignored by the backend (it accepts /start/{nonce} as a path param).
  // This is a plain <a href> navigation — no fetch() needed, no CORS
  // opaqueredirect issues, works with JS disabled.
  const makeNonceHref = (provider) =>
    hasBackendConfig
      ? `${backendUrl}/api/auth/${provider}/start/${Date.now().toString(36)}${Math.random().toString(36).slice(2, 8)}`
      : undefined;
  const githubHref = makeNonceHref('github');
  const googleHref = makeNonceHref('google');

  // Click handler for social login buttons: shows immediate loading feedback
  // (spinner + disabled state) before the browser navigates away to the OAuth
  // provider. The navigation still happens via the <a href> — we just set
  // state first so the user sees feedback instantly. No e.preventDefault()
  // needed because the default <a> navigation is what we want.
  const handleSocialClick = (provider) => {
    if (!hasBackendConfig || socialLoading) return;
    setSocialLoading(provider);
    // The browser will navigate away shortly — no need to clear the state.
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
    } catch (err) {
      setError(fmtErr(err?.response?.data?.detail) || err?.message || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const socialButton = (provider, href, icon, label) => (
    <a
      href={href}
      aria-disabled={!hasBackendConfig || !!socialLoading}
      onClick={() => handleSocialClick(provider)}
      className="app-button-secondary login-social"
      style={{
        opacity: hasBackendConfig ? (socialLoading && socialLoading !== provider ? 0.5 : 1) : 0.6,
        pointerEvents: socialLoading ? 'none' : 'auto',
      }}
    >
      {socialLoading === provider ? (<><span className="login-spin" aria-hidden="true" /><span>Redirecting…</span></>) : (<>{icon}<span>{label}</span></>)}
    </a>
  );

  return (
    <main className="login" data-testid="login-page">
      <section className="login-story" aria-label="About the Agency">
        <div className="login-brand">
          <img src={`${process.env.PUBLIC_URL || ""}/logo.svg`} alt="" width="32" height="32" />
          <span>Autonomous AI Agency</span>
        </div>
        <div className="login-story-body">
          <h2 className="login-pitch">A small AI team that works for your business, on your own hardware.</h2>
          <ul className="login-points">
            <li>
              <Bot size={20} aria-hidden="true" />
              <span><strong>Hand off real work.</strong> A lead agent plans each job, gives the pieces to specialists and checks the result before it reaches you.</span>
            </li>
            <li>
              <CheckCircle size={20} aria-hidden="true" />
              <span><strong>Stay in charge.</strong> Anything that matters waits for your approval. You see every step they take.</span>
            </li>
            <li>
              <Database size={20} aria-hidden="true" />
              <span><strong>Keep your data.</strong> It runs on your own machines. If one AI provider goes down, work moves to the next.</span>
            </li>
          </ul>
        </div>
      </section>

      <section className="login-form-wrap">
        <div className="login-card">
          <div className="login-brand login-brand--mobile">
            <img src={`${process.env.PUBLIC_URL || ""}/logo.svg`} alt="" width="28" height="28" />
            <span>Autonomous AI Agency</span>
          </div>
          <div className="login-head">
            <h1>Sign in</h1>
            <p>Use your GitHub or Google account. Email and password are only for admins and people an admin added.</p>
          </div>

          {oauthError && (
            <div role="alert" className="login-alert">
              <AlertCircle size={18} aria-hidden="true" />
              <p>{oauthError}</p>
            </div>
          )}

          <div className="login-social-row">
            {socialButton('github', githubHref, <Github size={18} aria-hidden="true" />, 'GitHub')}
            {socialButton('google', googleHref, <GoogleIcon />, 'Google')}
          </div>

          <div className="login-divider"><span>or</span></div>

          <button
            type="button"
            onClick={() => setShowAdminLogin((v) => !v)}
            aria-expanded={showAdminLogin}
            aria-controls="admin-login-form"
            data-testid="toggle-admin-login"
            className="login-toggle"
          >
            <ShieldCheck size={16} aria-hidden="true" />
            <span>Admin sign-in</span>
            <ChevronDown size={16} aria-hidden="true" style={{ transform: showAdminLogin ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s ease' }} />
          </button>

          {showAdminLogin && (
            <div className="login-admin animate-fade-in" id="admin-login-form" data-testid="admin-login-form">
              <form onSubmit={handleSubmit} className="login-fields" noValidate={false}>
                <FieldGroup label="Email" htmlFor="login-email">
                  <TextInput
                    id="login-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="admin@llmrelay.local"
                    autoComplete="username"
                    required
                    testId="email-input"
                  />
                </FieldGroup>
                <FieldGroup label="Password" htmlFor="login-password">
                  <TextInput
                    id="login-password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete="current-password"
                    required
                    testId="password-input"
                  />
                </FieldGroup>

                {error && (
                  <div role="alert" className="login-alert">
                    <AlertCircle size={18} aria-hidden="true" />
                    <p>{error}</p>
                  </div>
                )}

                <button type="submit" disabled={loading} className="app-button-primary" style={{ width: '100%' }}>
                  {loading ? (<><span className="login-spin" aria-hidden="true" /><span>Signing in…</span></>) : (<span>Sign in</span>)}
                </button>
              </form>
            </div>
          )}

          {!hasBackendConfig && (
            <p className="login-foot">
              Need to connect a backend first?{' '}
              <Link to="/bootstrap">Open the setup wizard</Link>.
            </p>
          )}
        </div>
      </section>
    </main>
  );
}
