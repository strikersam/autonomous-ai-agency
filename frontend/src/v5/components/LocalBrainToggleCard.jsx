/* eslint-disable no-unused-vars, jsx-a11y/anchor-is-valid -- ported admin panel prototype */
import React from 'react';
import * as api from '../../api';

/**
 * LocalBrainToggleCard — UI for the cross-machine GLM 5.2 toggle.
 *
 * Background: the Cloudflare-deployed agency exposes /api/local-brain/{state,toggle,heartbeat}
 * via the existing service_token auth surface. Operators flip the toggle from
 * here; ``scripts/local_controller.py`` running on the local machine polls,
 * starts llama-server.exe with the GLM-5.2 GGUF, and POSTs back its heartbeat.
 *
 * The card surfaces four states an operator must distinguish:
 *   1. OFF + No heartbeat         → "Local brain off (last heartbeat: never)"
 *   2. OFF + Recent heartbeat     → "Local brain was recently up; turning off"
 *   3. ON + Healthy heartbeat     → "Local GLM-5.2 ready" (with port + lease machine)
 *   4. ON + Stale or unhealthy    → "Local brain failed: <err>" (with model listing?)
 *
 * Wiring:
 *   - state: GET /api/local-brain/state (every 5s while mounted)
 *   - toggle: POST /api/local-brain/toggle {desired_state: 'on'|'off'}
 *
 * Designed for the React/Vite admin SPA — pulled from ProvidersScreen.jsx
 * right under BrainCard so the operator sees "Brain = colibri [local]"
 * immediately above this card and the actual toggler immediately below.
 */
export default function LocalBrainToggleCard() {
  const [state, setState]           = React.useState(null);  // null = loading
  const [loadErr, setLoadErr]       = React.useState(null);
  const [busy, setBusy]             = React.useState(false);
  const [toggleErr, setToggleErr]   = React.useState(null);
  const [showLease, setShowLease]   = React.useState(false);

  const refresh = React.useCallback(async () => {
    try {
      const { data } = await api.getLocalBrainState();
      setState(data);
      setLoadErr(null);
    } catch (e) {
      setLoadErr(api.fmtErr(e?.response?.data?.detail) || 'Could not load local-brain state.');
      setState(null);
    }
  }, []);

  React.useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [refresh]);

  const toggle = async (next) => {
    if (busy || !state) return;
    setBusy(true); setToggleErr(null);
    try {
      const { data } = await api.postLocalBrainToggle({
        desired_state: next,
        desired_provider: next === 'on' ? 'colibri' : 'auto',
        actor: 'admin-spa:providers-page',
      });
      setState(data);
    } catch (e) {
      setToggleErr(api.fmtErr(e?.response?.data?.detail) || 'Could not update local-brain toggle.');
    } finally {
      setBusy(false);
    }
  };

  // ── Render helpers ─────────────────────────────────────────────────────

  const desired = state?.desired?.state ?? 'off';
  const last = state?.last_heartbeat || {};
  const lease = state?.lease || {};
  const healthy = last.status === 'ok' && last.port_state === 'listening' && last.models_has_glm52;
  const leaseOwned = lease.valid && lease.machine_id;

  // Heartbeat freshness: <60s = fresh, 60-300s = stale, >300s = dead.
  const hbAgeSec = last.at ? Math.max(0, (Date.now() - new Date(last.at).getTime()) / 1000) : Infinity;
  const hbFresh = hbAgeSec < 60;
  const hbStale = !hbFresh && hbAgeSec < 600;

  const pill = (() => {
    if (!state) return { color: 'var(--text-muted)', label: 'loading…' };
    if (desired === 'off') {
      if (last.at && hbFresh && last.status === 'ok') {
        return { color: 'var(--warning)', label: 'OFF (was up — still running)' };
      }
      return { color: 'var(--text-muted)', label: 'OFF' };
    }
    // desired === 'on'
    if (healthy && hbFresh)   return { color: 'var(--success)', label: 'ON — listening' };
    if (healthy && hbStale)   return { color: 'var(--warning)', label: 'ON — stale heartbeat' };
    if (last.status === 'starting') return { color: 'var(--accent)', label: 'ON — starting…' };
    if (last.error)           return { color: 'var(--danger)', label: `ON — error: ${last.error.slice(0, 36)}` };
    if (last.at)              return { color: 'var(--danger)', label: 'ON — unreachable' };
    return { color: 'var(--warning)', label: 'ON — waiting for first heartbeat' };
  })();

  return (
    <div style={{
      borderRadius: 16,
      border: `1px solid color-mix(in oklab, ${pill.color} 20%, transparent)`,
      background:  `color-mix(in oklab, ${pill.color} 3%, transparent)`,
      padding:    '14px 16px',
      marginBottom: 14,
      display:    'flex',
      alignItems: 'start',
      gap:        12,
      flexWrap:   'wrap',
    }}>
      {/* Status pill column */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, flex: '1 1 280px', minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span style={{ fontSize:14, fontWeight:700, color:'var(--text-primary)', letterSpacing: '-0.02em' }}>
            Local GLM-5.2 brain
          </span>
          <span style={{
            fontSize:13,
            fontVariantNumeric:'tabular-nums',
            padding: '2px 7px',
            borderRadius: 999,
            background: `color-mix(in oklab, ${pill.color} 13%, transparent)`,
            border:     `1px solid color-mix(in oklab, ${pill.color} 33%, transparent)`,
            color:       pill.color,
            fontWeight: 700,
            animation: pill.color === 'var(--success)' ? 'pulse 2s infinite' : 'none',
          }}>
            {pill.label}
          </span>
          {leaseOwned && (
            <span title={lease.acquired_at} style={{
              fontSize:13,
              fontVariantNumeric:'tabular-nums',
              padding: '2px 7px',
              borderRadius: 999,
              background: 'color-mix(in oklab, var(--success) 10%, transparent)',
              border:     '1px solid color-mix(in oklab, var(--success) 30%, transparent)',
              color:       'var(--success)',
            }}>
              leased: {(lease.machine_id || '').slice(0, 12)}…
            </span>
          )}
        </div>
        <div style={{ fontSize:13, color: 'var(--text-muted)', lineHeight: 1.6, maxWidth: 540 }}>
          Toggle <strong style={{ color: 'var(--success)' }}>on</strong> to run the agency's brain on{' '}
          <strong style={{ color: 'var(--text-secondary)' }}>this machine</strong> via{' '}
          <code style={{ fontFamily: 'var(--font-mono)' }}>llama-server.exe</code> serving{' '}
          <code style={{ fontFamily: 'var(--font-mono)' }}>glm-5.2</code> at port 8072. A daemon on the
          local box (see <code style={{ fontFamily: 'var(--font-mono)' }}>scripts/local_controller.py</code>)
          polls this toggle and starts the server. Works from any computer with the setup. Toggle{' '}
          <strong style={{ color: 'var(--danger)' }}>off</strong> to fall back to cloud providers (NVIDIA,
          GLM, Cerebras, Groq).
        </div>
        <div style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color: 'var(--text-tertiary)', display: 'grid', gridTemplateColumns: '1fr 1fr', rowGap: 3, columnGap: 12 }}>
          <span>desired: <span style={{ color:'var(--text-primary)' }}>{desired}</span> · provider: <span style={{ color:'var(--text-primary)' }}>{state?.desired?.provider || 'auto'}</span></span>
          <span>last heartbeat: <span style={{ color: hbFresh ? 'var(--success)' : hbStale ? 'var(--warning)' : 'var(--danger)' }}>
            {last.at ? `${last.at} (${Math.floor(hbAgeSec)}s ago)` : 'never'}
          </span></span>
          <span>port state: <span style={{ color:'var(--text-primary)' }}>{last.port_state || 'unknown'}</span></span>
          <span>machine: <span style={{ color:'var(--text-primary)' }}>{(last.machine_id || '—').slice(0, 16)}{(last.machine_id || '').length > 16 ? '…' : ''}</span></span>
        </div>
        {toggleErr && (
          <div style={{ fontSize:13, color: 'var(--danger)', fontVariantNumeric:'tabular-nums' }}>{toggleErr}</div>
        )}
        {loadErr && (
          <div style={{ fontSize:13, color: 'var(--danger)', fontVariantNumeric:'tabular-nums' }}>{loadErr}</div>
        )}
      </div>

      {/* Action column */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, flex: '0 0 auto', alignSelf: 'center' }}>
        {desired === 'off' ? (
          <button
            onClick={() => toggle('on')}
            disabled={busy}
            style={{
              padding:        '10px 22px',
              borderRadius:   12,
              fontSize:14,
              fontWeight:     800,
              cursor:         busy ? 'not-allowed' : 'pointer',
              background:     'linear-gradient(135deg, var(--success), var(--success))',
              color:          'var(--on-accent)',
              border:         'none',
              opacity:        busy ? 0.6 : 1,
              transition:     'all 0.15s',
              letterSpacing:  '-0.02em',
            }}
          >{busy ? '…' : 'Start local GLM-5.2'}</button>
        ) : (
          <button
            onClick={() => toggle('off')}
            disabled={busy}
            style={{
              padding:        '10px 22px',
              borderRadius:   12,
              fontSize:14,
              fontWeight:     800,
              cursor:         busy ? 'not-allowed' : 'pointer',
              background:     'linear-gradient(135deg, var(--danger), #e74c3c)',
              color:          'var(--on-accent)',
              border:         'none',
              opacity:        busy ? 0.6 : 1,
              transition:     'all 0.15s',
              letterSpacing:  '-0.02em',
            }}
          >{busy ? '…' : 'Stop local GLM-5.2'}</button>
        )}
        <button
          onClick={() => setShowLease(o => !o)}
          style={{
            padding:      '5px 12px',
            borderRadius: 9,
            fontSize:13,
            fontVariantNumeric:'tabular-nums',
            fontWeight:   600,
            cursor:       'pointer',
            background:   'color-mix(in oklab, var(--ink) 4%, transparent)',
            border:       '1px solid color-mix(in oklab, var(--ink) 10%, transparent)',
            color:        'var(--text-muted)',
          }}
        >{showLease ? 'hide details' : 'show details'}</button>
      </div>

      {showLease && (
        <div style={{
          width:        '100%',
          padding:      10,
          borderRadius: 8,
          background:   'color-mix(in oklab, var(--ink) 3%, transparent)',
          border:       '1px solid color-mix(in oklab, var(--ink) 6%, transparent)',
          fontSize:13,
          fontVariantNumeric:'tabular-nums',
          color:        'var(--text-muted)',
          lineHeight:   1.6,
        }}>
          <div style={{ marginBottom: 6, color:'var(--text-primary)', fontSize:13 }}>heartbeat payload</div>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
{JSON.stringify(state, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
