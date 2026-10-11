/**
 * useSafeData — resilient multi-fetch hook.
 *
 * A single failing API endpoint never blanks the whole screen: each fetch
 * slot gets its own loading / error / data state.
 *
 * Fast by design, because every screen is built on it:
 *  - Each slot renders as soon as its own request returns; one slow endpoint
 *    no longer holds back the rest of the page.
 *  - Responses are kept in an in-memory cache (per URL, for this tab only, and
 *    cleared on sign-out). Opening a screen again shows the last data at once
 *    and refreshes it in the background, instead of a blank page and a spinner.
 *  - Background refreshes do not flip slots that already have data back to
 *    "loading", so polling never flashes skeletons.
 */
import { useState, useEffect, useCallback, useRef } from 'react';
import { API } from '../../api';

const cache = new Map(); // `${base}|${url}` -> response body (before transform)

/** Forget every cached response (called on sign-out). */
export function clearSafeDataCache() {
  cache.clear();
}

function cacheKey(base, url) {
  return `${base || ''}|${url}`;
}

export function useSafeData(baseUrl, endpoints = {}, options = {}) {
  const { refreshMs = 0, transform = {} } = options;
  const keys = Object.keys(endpoints);
  // An explicit baseUrl (string) overrides per request; otherwise the shared
  // API client resolves the backend URL itself (localStorage → env → origin).
  const baseOverride = baseUrl || undefined;

  const shape = (k, body) => (transform[k] ? transform[k](body) : body);
  const cached = (k) => cache.has(cacheKey(baseOverride, endpoints[k]));

  const [data, setData] = useState(() =>
    Object.fromEntries(keys.map(k => [k, cached(k) ? shape(k, cache.get(cacheKey(baseOverride, endpoints[k]))) : null]))
  );
  const [states, setStates] = useState(() =>
    Object.fromEntries(keys.map(k => [k, { loading: !cached(k), error: null }]))
  );
  const timerRef   = useRef(null);
  const mountedRef = useRef(true);
  const transformRef = useRef(transform);
  transformRef.current = transform;

  // Stable key so fetchAll is only recreated when baseUrl or endpoint set changes.
  const endpointKey = keys.map(k => `${k}:${endpoints[k]}`).join(',');

  const fetchAll = useCallback(async () => {
    if (!mountedRef.current) return;
    // Only slots with nothing to show go back to "loading".
    setStates(prev => Object.fromEntries(keys.map(k => [k, {
      loading: !cache.has(cacheKey(baseOverride, endpoints[k])),
      error: prev[k]?.error || null,
    }])));

    // Route through the shared axios instance so requests inherit the Bearer
    // token and the 401 → refresh-token retry flow from api.js interceptors.
    // Each fetch carries a per-request timeout so a hung backend endpoint
    // cannot leave the widget stuck in skeleton-loading forever (BUG-04).
    await Promise.allSettled(keys.map(async (k) => {
      const url = endpoints[k];
      let value = null;
      let state;
      try {
        const r = await API.get(url, {
          ...(baseOverride ? { baseURL: baseOverride } : {}),
          timeout: (refreshMs > 0 ? refreshMs : 30000),  // never exceed the poll interval
        });
        cache.set(cacheKey(baseOverride, url), r.data);
        const t = transformRef.current[k];
        value = t ? t(r.data) : r.data;
        state = { loading: false, error: null };
      } catch (e) {
        cache.delete(cacheKey(baseOverride, url));
        state = {
          loading: false,
          error: e?.response
            ? `${e.response.status} ${e.response.statusText || ''}`.trim()
            : (e?.message || 'Request failed'),
        };
      }
      if (!mountedRef.current) return;
      setData(prev => ({ ...prev, [k]: value }));
      setStates(prev => ({ ...prev, [k]: state }));
    }));
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
