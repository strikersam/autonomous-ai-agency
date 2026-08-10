/**
 * Platform Controls has to be reachable from the shell users actually land in.
 *
 * The previous home for this screen was the legacy dashboard, mounted only at
 * /legacy/*, while an authenticated user is redirected to /v5 — so the screen
 * existed, passed its own tests, and could not be opened. These tests pin the
 * two things that made it unreachable: the deep link must resolve, and the nav
 * must offer a way in.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { NAV_ITEMS } from '../v5/AppShell';

jest.mock('../AuthContext', () => ({
  useAuth: () => ({ user: { role: 'admin', email: 'a@b.c' }, logout: jest.fn() }),
}));
// The eager screens in V5App pull in the whole chat stack; this suite is about
// routing, so they are stubbed to keep it hermetic.
jest.mock('../v5/screens/ChatScreen', () => () => <div>chat</div>);
jest.mock('../v5/screens/AlertsBell', () => () => null);
jest.mock('../v5/screens/QuickNotesFAB', () => () => null);
jest.mock('../v5/screens/ActivationGate', () => ({ children }) => <>{children}</>);
jest.mock('../v5/screens/ControlsScreen', () => () => <div>CONTROLS SCREEN</div>);

const V5App = require('../v5/V5App').default;

test('/v5/controls opens Platform Controls', async () => {
  render(<MemoryRouter initialEntries={['/v5/controls']}><V5App /></MemoryRouter>);

  // The screen is code-split, so it arrives after its chunk resolves.
  await waitFor(() => expect(screen.getByText('CONTROLS SCREEN')).toBeInTheDocument());
});

test('an unknown deep link still falls back to chat rather than a blank shell', async () => {
  render(<MemoryRouter initialEntries={['/v5/nope']}><V5App /></MemoryRouter>);

  await waitFor(() => expect(screen.getByText('chat')).toBeInTheDocument());
});

test('the sidebar offers Controls, admin-only', () => {
  const item = NAV_ITEMS.find((n) => n.id === 'controls');

  expect(item).toBeDefined();
  expect(item.adminOnly).toBe(true);
  expect(item.label).toBe('Controls');
});
