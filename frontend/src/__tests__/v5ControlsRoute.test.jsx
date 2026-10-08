/**
 * Platform Controls has to be reachable from the shell users actually land in.
 *
 * After the 20→6 IA consolidation, Controls is no longer a top-level nav item —
 * it is a section inside the Settings hub, reached at /v5/settings or via the
 * back-compat alias /v5/controls. These pin the two things that keep it
 * reachable: the old deep link must still resolve to the Settings hub (which
 * renders the Controls section), and the nav must offer a way in.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { NAV_ITEMS } from '../v5/AppShell';
import { ALIASES } from '../v5/V5App';

vi.mock('../AuthContext', () => ({
  useAuth: () => ({ user: { role: 'admin', email: 'a@b.c' }, logout: vi.fn() }),
}));
// The eager assistant pulls in the whole chat stack; this suite is about
// routing, so the hubs are stubbed to keep it hermetic.
vi.mock('../v5/screens/AssistantHub', () => ({ default: () => <div>assistant</div> }));
vi.mock('../v5/screens/AlertsBell', () => ({ default: () => null }));
vi.mock('../v5/screens/QuickNotesFAB', () => ({ default: () => null }));
vi.mock('../v5/screens/ActivationGate', () => ({ default: ({ children }) => <>{children}</> }));
vi.mock('../v5/screens/SettingsHub', () => ({ default: ({ initialSection }) => <div>SETTINGS HUB: {initialSection}</div> }));
vi.mock('../v5/screens/DashboardScreen', () => ({ default: () => <div>HOME</div> }));

import V5App from '../v5/V5App';

test('/v5/controls aliases into the Settings hub on the controls section', async () => {
  render(<MemoryRouter initialEntries={['/v5/controls']}><V5App /></MemoryRouter>);

  // The hub is code-split, so it arrives after its chunk resolves.
  await waitFor(() => expect(screen.getByText('SETTINGS HUB: controls')).toBeInTheDocument());
});

test('an unknown deep link falls back to Home rather than a blank shell', async () => {
  render(<MemoryRouter initialEntries={['/v5/nope']}><V5App /></MemoryRouter>);

  await waitFor(() => expect(screen.getByText('HOME')).toBeInTheDocument());
});

test('the old controls id maps to the settings destination', () => {
  expect(ALIASES.controls).toEqual({ screen: 'settings', sub: 'controls' });
});

test('the sidebar offers Settings', () => {
  const item = NAV_ITEMS.find((n) => n.id === 'settings');
  expect(item).toBeDefined();
  expect(item.label).toBe('Settings');
});
