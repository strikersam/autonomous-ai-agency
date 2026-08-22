import React from 'react';

/**
 * HubTabs — the tab strip every hub screen shares.
 *
 * The 20-screen sidebar collapsed into 6 destinations; the screens that used
 * to be top-level nav items now live as tabs inside a hub. One tab strip
 * keeps them visually identical.
 */
export default function HubTabs({ tabs, active, onChange }) {
  return (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', padding: '14px 16px 0', maxWidth: 1000, margin: '0 auto' }}>
      {tabs.map(t => {
        const on = active === t.id;
        return (
          <button
            key={t.id}
            onClick={() => onChange(t.id)}
            style={{
              padding: '8px 18px', borderRadius: 999, fontSize: 13, fontWeight: 600, cursor: 'pointer',
              transition: 'all 0.15s', fontFamily: 'var(--font-main)',
              background: on ? 'rgba(93,162,255,0.15)' : 'rgba(255,255,255,0.04)',
              border: `1px solid ${on ? 'rgba(93,162,255,0.35)' : 'rgba(255,255,255,0.08)'}`,
              color: on ? '#fff' : 'var(--text-muted)',
            }}
          >
            {t.label}
          </button>
        );
      })}
    </div>
  );
}

export { HubTabs };
