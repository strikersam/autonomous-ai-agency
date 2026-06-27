/**
 * EphemeralBanner.jsx — floating notice for non-admin users.
 *
 * The platform runs on a free Render backend, so agencies created by signed-in
 * GitHub/Google users are temporary (24h by default). This dismissible floating
 * banner surfaces that, with a live countdown to expiry when available.
 *
 * Admins are persistent, so the banner renders nothing for them.
 */
import React from 'react';
import { getAccountLifecycle } from '../../api';

function formatRemaining(expiresAt) {
  if (!expiresAt) return null;
  const ms = new Date(expiresAt).getTime() - Date.now();
  if (Number.isNaN(ms)) return null;
  if (ms <= 0) return 'expiring now';
  const h = Math.floor(ms / 3_600_000);
  const m = Math.floor((ms % 3_600_000) / 60_000);
  if (h >= 1) return `${h}h ${m}m left`;
  return `${m}m left`;
}

export default function EphemeralBanner({ isAdmin }) {
  const [info, setInfo] = React.useState(null);
  const [dismissed, setDismissed] = React.useState(false);
  const [, force] = React.useReducer((x) => x + 1, 0);

  React.useEffect(() => {
    if (isAdmin) return undefined;
    let alive = true;
    let attempt = 0;
    let timer = null;
    // Retry transient failures with backoff so one flaky request doesn't
    // permanently hide the 24h warning for the rest of the session.
    const load = () => {
      getAccountLifecycle()
        .then((r) => { if (alive) setInfo(r.data); })
        .catch(() => {
          if (!alive || attempt >= 5) return;
          attempt += 1;
          timer = setTimeout(load, Math.min(30000, 2000 * attempt));
        });
    };
    load();
    return () => { alive = false; if (timer) clearTimeout(timer); };
  }, [isAdmin]);

  // Re-render once a minute so the countdown stays fresh.
  React.useEffect(() => {
    if (!info?.ephemeral) return undefined;
    const t = setInterval(force, 60_000);
    return () => clearInterval(t);
  }, [info]);

  if (isAdmin || dismissed || !info || !info.ephemeral) return null;

  const remaining = formatRemaining(info.expires_at);
  const hours = info.ttl_hours || 24;

  return (
    <div
      role="status"
      style={{
        position: 'fixed', left: '50%', transform: 'translateX(-50%)',
        bottom: 'calc(env(safe-area-inset-bottom, 0px) + 84px)', zIndex: 70,
        width: 'min(680px, calc(100vw - 24px))',
        display: 'flex', alignItems: 'flex-start', gap: 12,
        padding: '12px 14px', borderRadius: 14,
        background: 'rgba(28,20,10,0.96)', backdropFilter: 'blur(12px)',
        border: '1px solid rgba(255,189,102,0.35)',
        boxShadow: '0 10px 30px rgba(0,0,0,0.45)',
      }}
    >
      <span style={{ fontSize: 18, lineHeight: 1.2, flexShrink: 0 }}>⏳</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: '#ffce8a', marginBottom: 3 }}>
          Temporary agency{remaining ? ` — ${remaining}` : ''}
        </div>
        <div style={{ fontSize: 12, color: 'rgba(255,255,255,0.72)', lineHeight: 1.5 }}>
          {info.note || (
            `Running an agency beyond ${hours} hours needs real compute, and this ` +
            `platform is currently hosted on a free Render backend — so we can't ` +
            `keep your agency running forever. Companies created by signed-in ` +
            `GitHub/Google users are automatically removed after ${hours} hours. ` +
            `Ask an admin if you need a permanent agency.`
          )}
        </div>
      </div>
      <button
        onClick={() => setDismissed(true)}
        title="Dismiss"
        style={{
          flexShrink: 0, width: 26, height: 26, borderRadius: 8, cursor: 'pointer',
          background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)',
          color: 'rgba(255,255,255,0.7)', fontSize: 14, lineHeight: 1,
        }}
      >
        ×
      </button>
    </div>
  );
}
