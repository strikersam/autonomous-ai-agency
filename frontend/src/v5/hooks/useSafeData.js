/**
 * useSafeData — resilient multi-fetch hook built on Promise.allSettled.
 *
 * A single failing API endpoint never blanks the whole screen.
 * Each fetch slot gets its own loading / error / data state.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { API } from '../../api';

export function useSafeData(baseUrl, endpoints = {}, options = {}) {
  const { refreshMs = 0, transform = {} } = options;
  const keys = Object.keys(endpoints);

  const [data, setData]     = useState(() => Object.fromEntries(keys.map(k => [k, null])));
  const [states, setStates] = useState(() =>
    Object.fromEntries(keys.map(k => [k, { loading: true, error: null }]))
  );
  const timerRef   = useRef(null);
  const mountedRef = useRef(true);

  // An explicit baseUrl (string) overrides per request; otherwise the shared
  // API client resolves the backend URL itself (localStorage → env → origin).
  const baseOverride = baseUrl || undefined;

  // Stable key so fetchAll is only recreated when baseUrl or endpoint set changes.
  const endpointKey = keys.map(k => `${k}:${endpoints[k]}`).join(',');

  const fetchAll = useCallback(async () => {
    if (!mountedRef.current) return;
    setStates(prev => Object.fromEntries(keys.map(k => [k, { loading: true, error: prev[k]?.error || null }])));

    // Route through the shared axios instance so requests inherit the Bearer
    // token and the 401 → refresh-token retry flow from api.js interceptors.
    // Each fetch carries a per-request timeout so a hung backend endpoint
    // cannot leave the widget stuck in skeleton-loading forever (BUG-04).
    const results = await Promise.allSettled(
      keys.map(k => API.get(endpoints[k], {
        ...(baseOverride ? { baseURL: baseOverride } : {}),
        timeout: (refreshMs > 0 ? refreshMs : 30000),  // never exceed the poll interval
      }).then(r => r.data))
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
        const e = res.reason;
        nextData[k]   = null;
        nextStates[k] = {
          loading: false,
          error: e?.response
            ? `${e.response.status} ${e.response.statusText || ''}`.trim()
            : (e?.message || 'Request failed'),
        };
      }
    });
    setData(nextData);
    setStates(nextStates);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [baseOverride, endpointKey]);

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
