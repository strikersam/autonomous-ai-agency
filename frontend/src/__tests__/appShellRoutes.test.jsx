/**
 * Both dashboard shells are code-split. The legacy shell was made lazy to get
 * ~24 unused screens out of the boot bundle — every visitor was downloading the
 * whole v4 dashboard before the v5 chunk could start, including phones that are
 * redirected straight to /v5. That is only safe if /legacy/* still resolves and
 * the root still lands on v5, which is what these pin.
 *
 * Deliberately NOT claimed: that the route's Suspense boundary is present. The
 * shells are mocked here, so `React.lazy` resolves without ever suspending —
 * verified by deleting the boundary and watching these still pass. The boundary
 * matters in the real bundle (a lazy component without one throws), so it has
 * to be held by review, not by this file.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

jest.mock('../AuthContext', () => ({
  AuthProvider: ({ children }) => <>{children}</>,
  useAuth: () => ({ user: { role: 'admin', email: 'a@b.c' }, loading: false, logout: jest.fn() }),
}));
jest.mock('../api', () => ({
  getSetupState: jest.fn(() => Promise.resolve({ data: { completed: true } })),
  getBackendUrl: jest.fn(() => ''),
}));
jest.mock('../pages/DashboardLayout', () => () => <div>LEGACY SHELL</div>);
jest.mock('../v5/V5App', () => () => <div>V5 SHELL</div>);
jest.mock('../pages/LoginPage', () => () => <div>login</div>);
jest.mock('../pages/AuthCallback', () => () => <div>callback</div>);
jest.mock('../pages/SetupWizardPage', () => () => <div>setup</div>);

const App = require('../App').default;

test('/legacy/* still resolves once the shell is code-split', async () => {
  render(<MemoryRouter initialEntries={['/legacy/tasks']}><App /></MemoryRouter>);

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
