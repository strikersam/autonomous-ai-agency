/**
 * Both dashboard shells are code-split. The legacy shell was made lazy to get
 * ~24 unused screens out of the boot bundle — every visitor was downloading the
 * whole v4 dashboard before the v5 chunk could start, including phones that are
 * redirected straight to /v5. That is only safe if /legacy/* still resolves and
 * the root still lands on v5, which is what these pin.
 *
 * The boundary itself is pinned by making the mocked legacy shell suspend on
 * first render (throwing a promise) rather than resolve instantly. A plain
 * module mock resolves without ever suspending, so it leaves the boundary
 * untested — deleting the boundary kept those tests green, which is what
 * prompted this. With the gate below, a missing boundary fails the render.
 */
import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

jest.mock('../AuthContext', () => ({
  AuthProvider: ({ children }) => <>{children}</>,
  useAuth: () => ({ user: { role: 'admin', email: 'a@b.c' }, loading: false, logout: jest.fn() }),
}));
jest.mock('../api', () => ({
  getSetupState: jest.fn(() => Promise.resolve({ data: { completed: true } })),
  getBackendUrl: jest.fn(() => ''),
}));
// Suspends until `mockGate.open()`, so the route's Suspense fallback is
// actually exercised. Jest hoists this factory above the file, hence the
// `mock` prefix the hoist-checker requires on anything it closes over.
const mockGate = (() => {
  let release;
  const promise = new Promise((r) => { release = r; });
  return { promise, ready: false, open() { this.ready = true; release(); } };
})();

jest.mock('../pages/DashboardLayout', () => () => {
  if (!mockGate.ready) throw mockGate.promise;
  return <div>LEGACY SHELL</div>;
});
jest.mock('../v5/V5App', () => () => <div>V5 SHELL</div>);
jest.mock('../pages/LoginPage', () => () => <div>login</div>);
jest.mock('../pages/AuthCallback', () => () => <div>callback</div>);
jest.mock('../pages/SetupWizardPage', () => () => <div>setup</div>);

const App = require('../App').default;

test('/legacy/* shows the fallback while the chunk loads, then the shell', async () => {
  render(<MemoryRouter initialEntries={['/legacy/tasks']}><App /></MemoryRouter>);

  // Proves the boundary exists: without it, a suspending child throws here.
  expect(await screen.findByText('Loading the legacy dashboard')).toBeInTheDocument();

  await act(async () => { mockGate.open(); });

  await waitFor(() => expect(screen.getByText('LEGACY SHELL')).toBeInTheDocument());
});

test('/v5 resolves', async () => {
  render(<MemoryRouter initialEntries={['/v5/controls']}><App /></MemoryRouter>);

  await waitFor(() => expect(screen.getByText('V5 SHELL')).toBeInTheDocument());
});

test('an authenticated user landing at the root is sent to v5, not the legacy shell', async () => {
  render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>);

  await waitFor(() => expect(screen.getByText('V5 SHELL')).toBeInTheDocument());
  expect(screen.queryByText('LEGACY SHELL')).not.toBeInTheDocument();
});
