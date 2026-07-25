import React from 'react';
import * as api from '../../api';

// ProviderHealthToggleCard — per-provider on/off switch driven by live health.
//
// Why this exists: a provider whose key is invalid or whose account is out of
// credit fails identically forever, and leaving it in the rotation costs a wasted
// attempt on every call while burying the providers that do work. The backend
// auto-disables exactly those states (401/403, 402, billing-shaped 4xx, and
// "no accessible model") and requires a manual re-enable, because only a human
// can fix them. Transient states (429, 5xx, network) are NOT auto-disabled —
// they self-heal, and switching off on a rate-limit burst would take the whole
// free tier offline.
//
// "Online" therefore means enabled AND the circuit breaker is closed.

const REFRESH_MS = 15000;

function StatusPill({ row }) {
  const [bg, fg, label] = row.online
    ? ['rgba(16,185,129,.15)', '#10b981', 'ONLINE']
    : !row.enabled
      ? ['rgba(239,68,68,.15)', '#ef4444', 'OFF']
      : ['rgba(245,158,11,.15)', '#f59e0b', 'COOLDOWN'];
  return (
    <span style={{
      background: bg, color: fg, fontSize: 10, fontWeight: 700,
      padding: '2px 8px', borderRadius: 999, letterSpacing: '.04em',
      whiteSpace: 'nowrap',
    }}>{label}</span>
  );
}

export default function ProviderHealthToggleCard() {
  const [rows, setRows]       = React.useState([]);
  const [counts, setCounts]   = React.useState({ online: 0, total: 0 });
  const [error, setError]     = React.useState('');
  const [busy, setBusy]       = React.useState('');   // provider id being toggled
  const [loaded, setLoaded]   = React.useState(false);

  const load = React.useCallback(async () => {
    try {
      const { data } = await api.getBrainProviders();
      setRows(data.providers || []);
      setCounts({ online: data.online_count || 0, total: data.total_count || 0 });
      setError('');
    } catch (e) {
      // Surface the failure instead of rendering a misleading empty list.
      setError(e?.response?.data?.detail || e?.message || 'Could not load providers');
    } finally {
      setLoaded(true);
    }
  }, []);

  React.useEffect(() => {
    load();
    const t = setInterval(load, REFRESH_MS);
    return () => clearInterval(t);
  }, [load]);

  const toggle = async (row) => {
    setBusy(row.id);
    try {
      await api.setBrainProviderEnabled(row.id, !row.enabled);
      await load();
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || `Could not toggle ${row.id}`);
    } finally {
      setBusy('');
    }
  };

  return (
    <div style={{
      border: '1px solid var(--border, #2a2a35)', borderRadius: 12,
      padding: 16, marginTop: 16, background: 'var(--panel, #16161d)',
    }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>Provider health</h3>
        <span style={{ fontSize: 12, color: 'var(--text-muted, #8b8b9a)' }}>
          {loaded ? `${counts.online} of ${counts.total} online` : 'loading…'}
        </span>
      </div>
      <p style={{ fontSize: 12, color: 'var(--text-muted, #8b8b9a)', margin: '6px 0 12px' }}>
        Providers with an invalid key, no credit, or no accessible model are switched
        off automatically and stay off until you turn them back on. Rate limits and
        server errors are not switched off — they recover on their own.
      </p>

      {error && (
        <div style={{
          fontSize: 12, color: '#ef4444', background: 'rgba(239,68,68,.1)',
          border: '1px solid rgba(239,68,68,.3)', borderRadius: 8,
          padding: '8px 10px', marginBottom: 12,
        }}>{error}</div>
      )}

      {loaded && !error && rows.length === 0 && (
        <div style={{ fontSize: 12, color: 'var(--text-muted, #8b8b9a)' }}>
          No providers configured — set at least one provider API key.
        </div>
      )}

      <div style={{ overflowX: 'auto' }}>
        {rows.length > 0 && (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ textAlign: 'left', color: 'var(--text-muted, #8b8b9a)' }}>
                <th style={{ padding: '6px 8px' }}>Provider</th>
                <th style={{ padding: '6px 8px' }}>Status</th>
                <th style={{ padding: '6px 8px' }}>Why</th>
                <th style={{ padding: '6px 8px', textAlign: 'right' }}>Calls</th>
                <th style={{ padding: '6px 8px', textAlign: 'right' }}>Switch</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id} style={{ borderTop: '1px solid var(--border, #2a2a35)' }}>
                  <td style={{ padding: '8px' }}>
                    <div style={{ fontWeight: 600 }}>{row.name || row.id}</div>
                    <div style={{ color: 'var(--text-muted, #8b8b9a)', fontSize: 11 }}>
                      {row.tier} · {row.default_model}
                    </div>
                  </td>
                  <td style={{ padding: '8px' }}><StatusPill row={row} /></td>
                  <td style={{ padding: '8px', maxWidth: 320 }}>
                    <span style={{ color: 'var(--text-muted, #8b8b9a)' }}>
                      {row.disabled_reason || row.last_error || '—'}
                    </span>
                    {row.auto_disabled && (
                      <span style={{ marginLeft: 6, fontSize: 10, color: '#f59e0b' }}>
                        (auto)
                      </span>
                    )}
                  </td>
                  <td style={{ padding: '8px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
                    {row.total_calls}
                    {row.total_failures > 0 && (
                      <span style={{ color: '#ef4444' }}> / {row.total_failures} failed</span>
                    )}
                  </td>
                  <td style={{ padding: '8px', textAlign: 'right' }}>
                    <button
                      type="button"
                      onClick={() => toggle(row)}
                      disabled={busy === row.id}
                      aria-label={`${row.enabled ? 'Disable' : 'Enable'} ${row.name || row.id}`}
                      style={{
                        cursor: busy === row.id ? 'wait' : 'pointer',
                        background: row.enabled ? 'rgba(16,185,129,.15)' : 'transparent',
                        color: row.enabled ? '#10b981' : 'var(--text-muted, #8b8b9a)',
                        border: `1px solid ${row.enabled ? '#10b981' : 'var(--border, #2a2a35)'}`,
                        borderRadius: 999, padding: '4px 12px', fontSize: 11,
                        fontWeight: 700, minWidth: 56,
                      }}
                    >
                      {busy === row.id ? '…' : row.enabled ? 'ON' : 'OFF'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
