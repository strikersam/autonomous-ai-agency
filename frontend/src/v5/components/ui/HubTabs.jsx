import React from 'react';

/**
 * HubTabs — the tab strip every hub screen shares.
 *
 * The 20-screen sidebar collapsed into 6 destinations; the screens that used
 * to be top-level nav items now live as tabs inside a hub. One tab strip
 * keeps them visually identical. Arrow keys move between tabs (WAI-ARIA
 * tablist pattern); on a phone the strip scrolls sideways instead of wrapping.
 */
export default function HubTabs({ tabs, active, onChange, label = 'Sections' }) {
  const refs = React.useRef({});
  const listRef = React.useRef(null);
  // Bring the active tab into view on a phone by scrolling the strip itself.
  // Not scrollIntoView(): Chrome moves its Tab starting point to the element,
  // so the first Tab after a deep link skipped the "Skip to content" link.
  React.useEffect(() => {
    const list = listRef.current;
    const el = refs.current[active];
    if (!list || !el) return;
    const left = el.offsetLeft - list.offsetLeft;
    if (left < list.scrollLeft || left + el.offsetWidth > list.scrollLeft + list.clientWidth) {
      list.scrollLeft = Math.max(0, left - 16);
    }
  }, [active]);
  const onKey = (e, i) => {
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
    const jump = e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 : null;
    if (!step && jump === null) return;
    e.preventDefault();
    const next = tabs[jump ?? (i + step + tabs.length) % tabs.length];
    onChange(next.id);
    refs.current[next.id]?.focus();
  };
  return (
    <div className="hub-tabs-wrap">
      <div ref={listRef} className="hub-tabs scrollbar-hide" role="tablist" aria-label={label}>
        {tabs.map((t, i) => {
          const on = active === t.id;
          return (
            <button
              key={t.id}
              ref={el => { refs.current[t.id] = el; }}
              type="button"
              role="tab"
              aria-selected={on}
              tabIndex={on ? 0 : -1}
              className={`hub-tab ${on ? 'is-on' : ''}`}
              onClick={() => onChange(t.id)}
              onKeyDown={e => onKey(e, i)}
            >
              {t.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export { HubTabs };
