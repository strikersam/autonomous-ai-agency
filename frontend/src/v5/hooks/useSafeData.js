/**
 * useSafeData — resilient multi-fetch hook built on Promise.allSettled.
 *
 * A single failing API endpoint never blanks the whole screen.
 * Each fetch slot gets its own loading / error / data state.
 */
import { useState, useEffect, useCallback, useRef } from 'react';

function _getBackendUrl() {
  try {
    const stored = localStorage.getItem('backend_url');
    if (stored) return stored.replace(/\/$/, '');
    if (typeof window !== 'undefined' && window.location?.origin) {
      return window.location.origin;
    }
  } catch {
    // Fallback if localStorage or window is not accessible
  }
  return '';
}

function _getToken() {
  try {
    return localStorage.getItem('access_token') || '';
  } catch {
    return '';
  }
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

  // Fallback to reading the latest stored backend URL if no baseUrl was provided.
  const activeBaseUrl = baseUrl || _getBackendUrl();

  // Stable key so fetchAll is only recreated when activeBaseUrl or endpoint set changes.
  const endpointKey = keys.map(k => `${k}:${endpoints[k]}`).join(',');

  const fetchAll = useCallback(async () => {
    if (!mountedRef.current) return;
    setStates(prev => Object.fromEntries(keys.map(k => [k, { loading: true, error: prev[k]?.error || null }])));

    const token = auth ? _getToken() : '';
    const headers = { 'Content-Type': 'application/json' };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const results = await Promise.allSettled(
      keys.map(k =>
        fetch(`${activeBaseUrl}${endpoints[k]}`, { headers })
          .then(r => { 
            if (!r.ok) throw new Error(`${r.status} ${r.statusText}`); 
            return r.json(); 
          })
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
  }, [activeBaseUrl, endpointKey, auth]);

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
