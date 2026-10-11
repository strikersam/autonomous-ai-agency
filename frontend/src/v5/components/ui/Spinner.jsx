import React from 'react';

/**
 * Spinner — the one loading indicator.
 *
 * Replaces the per-file "rotating border circle" variants (App.js
 * LoadingScreen, V5App ScreenLoading, ad-hoc inline spinners). Relies on the
 * global `spin` keyframes from index.css.
 */
export default function Spinner({ size = 22, center = false, label }) {
  const el = (
    <span
      role="status"
      aria-label={label || 'Loading'}
      style={{
        display: 'inline-block', width: size, height: size,
        border: '2px solid color-mix(in oklab, var(--ink) 15%, transparent)', borderTopColor: 'var(--accent)',
        borderRadius: '50%', animation: 'spin 0.8s linear infinite', flexShrink: 0,
      }}
    />
  );
  if (!center) return el;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 10, height: '60vh' }}>
      {el}
      {label && <span style={{ fontSize:13, color: 'var(--text-muted)' }}>{label}</span>}
    </div>
  );
}

export { Spinner };
