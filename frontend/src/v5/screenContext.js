// screenContext.js — which screen and tab the user is looking at, for SAM.
//
// The shell reports the hub (home, work, …) and each hub reports its own tab,
// stored per hub so a child effect running before the shell's cannot be wiped.
// Read at send time by SamAvatar; nothing re-renders on change.
import React from 'react';

let currentScreen = 'home';
const subByScreen = {};

export function setScreen(screen) {
  currentScreen = screen || 'home';
}

export function setSub(screen, sub) {
  if (screen) subByScreen[screen] = sub || '';
}

/** "work/roadmap", or just "home" when the hub has no tab. */
export function getScreenPath() {
  const sub = subByScreen[currentScreen];
  return sub ? `${currentScreen}/${sub}` : currentScreen;
}

/** Hubs call this with their active tab. */
export function useReportSub(screen, sub) {
  React.useEffect(() => { setSub(screen, sub); }, [screen, sub]);
}
