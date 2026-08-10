/**
 * Providers → "Brain & local-runtime controls" links across to the Controls
 * screen, because the two surfaces own different halves of the brain settings
 * and write different stores.
 *
 * Pinned because the target is exactly the kind of thing that silently rots:
 * the same link was previously written as `/controls`, which React Router
 * resolves against the site root, and the catch-all redirected it to /v5 — so
 * it pointed at nothing while still looking like a working link.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

jest.mock('../v5/hooks/useSafeData', () => ({
  useSafeData: () => [{ providers: [] }, { providers: 'ready' }, jest.fn()],
}));
// The section is rendered by the providers tab; the child cards each fetch on
// mount and are not what this test is about.
jest.mock('../v5/components/BrainCard', () => () => <div>brain card</div>);
jest.mock('../v5/components/LocalBrainToggleCard', () => () => <div>local brain</div>);
jest.mock('../v5/components/ProviderHealthToggleCard', () => () => <div>provider health</div>);
jest.mock('../v5/components/ProviderConsole', () => () => <div>console</div>);
jest.mock('../v5/components/McpCard', () => () => <div>mcp card</div>);
jest.mock('../api', () => ({
  fmtErr: (d) => (typeof d === 'string' ? d : ''),
  getProviderPolicy: jest.fn(() => Promise.resolve({ data: {} })),
  updateProviderPolicy: jest.fn(),
  listModels: jest.fn(() => Promise.resolve({ data: {} })),
  listMcpServers: jest.fn(() => Promise.resolve({ data: {} })),
  createProvider: jest.fn(),
  updateProvider: jest.fn(),
  deleteProvider: jest.fn(),
  testProvider: jest.fn(),
}));

const ProvidersScreen = require('../v5/screens/ProvidersScreen').default;

test('the cross-link points at the v5 Controls route, not the site root', async () => {
  render(<MemoryRouter><ProvidersScreen /></MemoryRouter>);

  const link = await waitFor(() => screen.getByText(/Controls → Brain & Model Routing/));

  expect(link.closest('a')).toHaveAttribute('href', '/v5/controls');
});
