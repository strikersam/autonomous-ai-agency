// Theme preference: 'system' (default), 'light' or 'dark'. The resolved
// choice lives on <html data-theme>, which index.css keys its tokens off.
// index.html applies the stored value before first paint to avoid a flash.
const KEY = 'theme';

export function getThemePreference() {
  try {
    const v = localStorage.getItem(KEY);
    return v === 'light' || v === 'dark' ? v : 'system';
  } catch {
    return 'system';
  }
}

export function setThemePreference(pref) {
  const root = document.documentElement;
  try {
    if (pref === 'light' || pref === 'dark') localStorage.setItem(KEY, pref);
    else localStorage.removeItem(KEY);
  } catch {
    /* storage blocked: the choice still applies for this page view */
  }
  if (pref === 'light' || pref === 'dark') root.setAttribute('data-theme', pref);
  else root.removeAttribute('data-theme');
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) {
    const bg = getComputedStyle(document.body).backgroundColor;
    if (bg) meta.setAttribute('content', bg);
  }
}
