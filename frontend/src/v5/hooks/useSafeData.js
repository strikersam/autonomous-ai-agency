/**
 * useSafeData — resilient multi-fetch hook built on Promise.allSettled.
 *
 * A single failing API endpoint never blanks the whole screen.
 * Each fetch slot gets its own loading / error / data state.
 *
 * Usage:
 *   const [data, states, reload] = useSafeData(API, {
 *     doctor:   '/api/doctor',
 *     runtimes: '/runtimes/list',
 *   });
 *   // data.doctor   → response JSON (or null on error)
 *   // states.doctor → { loading, error }
 *   // reload()      → re-runs all fetches
 *
 * Options (third arg):
 *   refreshMs  — auto-refresh interval ms (0 = off, default 0)
 *   transform  — per-key transform fn map: { key: rawJson => transformed }
 *   auth       — if true (default), sends Authorization: Bearer <token>
 */
import { useState, useEffect, useCallback, useRef } from 'react';

const _TOKEN_KEY = 'auth_token';
function _getToken() {
  try { return localStorage.getItem(_TOKEN_KEY) || ''; } catch { return ''; }
}

export function useSafeData(baseUrl, endpoints = {}, options = {}) {
  const { refreshMs = 0, transform = {}, auth = true } = options;
  const keys = Object.keys(endpoints);

  const [data, setData]     = useState(() => Object.fromEntries(keys.map(k => [k, null])));
  const [states, setStates] = useState(() =>
    Object.fromEntries(keys.map(k => [k, { loading: true, error: null }]))
  );
  const timerRef   = useRef(null);
  const mountedRef = useRef(true);

  // Stable key so fetchAll is only recreated when baseUrl or endpoint set changes.
  const endpointKey = keys.map(k => `${k}:${endpoints[k]}`).join(',');

  const fetchAll = useCallback(async () => {
    if (!mountedRef.current) return;
    setStates(prev => Object.fromEntries(keys.map(k => [k, { loading: true, error: prev[k]?.error || null }])));

    const token = auth ? _getToken() : '';
    const headers = token ? { Authorization: `Bearer ${token}` } : {};

    const results = await Promise.allSettled(
      keys.map(k =>
        fetch(`${baseUrl}${endpoints[k]}`, { headers })
          .then(r => { if (!r.ok) throw new Error(`${r.status} ${r.statusText}`); return r.json(); })
      )
    );

    if (!mountedRef.current) return;

    const nextData   = {};
    const nextStates = {};
    keys.forEach((k, i) => {
      const res = results[i];
      if (res.status === 'fulfilled') {
        nextData[k]   = transform[k] ? transform[k](res.value) : res.value;
        nextStates[k] = { loading: false, error: null };
      } else {
        nextData[k]   = null;
        nextStates[k] = { loading: false, error: res.reason?.message || 'Request failed' };
      }
    });
    setData(nextData);
    setStates(nextStates);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseUrl, endpointKey, auth]);

  useEffect(() => {
    mountedRef.current = true;
    fetchAll();
    if (refreshMs > 0) { timerRef.current = setInterval(fetchAll, refreshMs); }
    return () => {
      mountedRef.current = false;
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [fetchAll, refreshMs]);

  return [data, states, fetchAll];
}
