/**
 * The Agency (v5) is the only authenticated UI, and it is code-split to keep it
 * out of the boot bundle — every visitor used to download the whole dashboard
 * before anything could paint. That is only safe if the root still lands on v5
 * behind its Suspense boundary, which is what these pin.
 *
 * The boundary itself is pinned by making the mocked v5 shell suspend on first
 * render (throwing a promise) rather than resolve instantly. A plain module
 * mock resolves without ever suspending, so it would leave the boundary
 * untested — deleting it would keep those tests green. With the gate below, a
 * missing boundary fails the render.
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

jest.mock('../v5/V5App', () => () => {
  if (!mockGate.ready) throw mockGate.promise;
  return <div>V5 SHELL</div>;
});
jest.mock('../pages/LoginPage', () => () => <div>login</div>);
jest.mock('../pages/AuthCallback', () => () => <div>callback</div>);
jest.mock('../pages/SetupWizardPage', () => () => <div>setup</div>);

const App = require('../App').default;

test('/v5/* shows the fallback while the chunk loads, then the shell', async () => {
  render(<MemoryRouter initialEntries={['/v5/work']}><App /></MemoryRouter>);

  // Proves the boundary exists: without it, a suspending child throws here.
  expect(await screen.findByText('Loading the Agency')).toBeInTheDocument();

  await act(async () => { mockGate.open(); });

  await waitFor(() => expect(screen.getByText('V5 SHELL')).toBeInTheDocument());
});

test('an authenticated user landing at the root is sent into the Agency', async () => {
  mockGate.open();
  render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>);

  await waitFor(() => expect(screen.getByText('V5 SHELL')).toBeInTheDocument());
});
