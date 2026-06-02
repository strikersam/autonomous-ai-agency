// NOTE: localStorage is used intentionally for UI state persistence.
// Never store passwords, API keys, or auth tokens here; those go through
// the backend secrets store (/api/secrets). This module stores ONLY
// UI preferences (theme, layout, last-selected workspace, etc.).
export function getLocal(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function setLocal(key: string, value: string) {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // ignore
  }
}

export function removeLocal(key: string) {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // ignore
  }
}

