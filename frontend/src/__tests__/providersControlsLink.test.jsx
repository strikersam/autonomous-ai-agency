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
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../v5/hooks/useSafeData', () => ({
  useSafeData: () => [{ providers: [] }, { providers: 'ready' }, vi.fn()],
}));
// The section is rendered by the providers tab; the child cards each fetch on
// mount and are not what this test is about.
vi.mock('../v5/components/BrainCard', () => ({ default: () => <div>brain card</div> }));
vi.mock('../v5/components/LocalBrainToggleCard', () => ({ default: () => <div>local brain</div> }));
vi.mock('../v5/components/ProviderHealthToggleCard', () => ({ default: () => <div>provider health</div> }));
vi.mock('../v5/components/ProviderConsole', () => ({ default: () => <div>console</div> }));
vi.mock('../v5/components/McpCard', () => ({ default: () => <div>mcp card</div> }));
vi.mock('../api', () => ({
  fmtErr: (d) => (typeof d === 'string' ? d : ''),
  getProviderPolicy: vi.fn(() => Promise.resolve({ data: {} })),
  updateProviderPolicy: vi.fn(),
  listModels: vi.fn(() => Promise.resolve({ data: {} })),
  listMcpServers: vi.fn(() => Promise.resolve({ data: {} })),
  createProvider: vi.fn(),
  updateProvider: vi.fn(),
  deleteProvider: vi.fn(),
  testProvider: vi.fn(),
  syncProviderToRender: vi.fn(),
}));

import ProvidersScreen from '../v5/screens/ProvidersScreen';

import * as api from '../api';

beforeEach(() => { window.location.hash = ''; api.getProviderPolicy.mockClear(); });

test('the cross-link points at the v5 Controls route, not the site root', async () => {
  render(<MemoryRouter><ProvidersScreen /></MemoryRouter>);
  await userEvent.click(screen.getByRole('tab', { name: 'Brain & Routing' }));

  const link = await waitFor(() => screen.getByText(/Controls → Brain & Model Routing/));

  expect(link.closest('a')).toHaveAttribute('href', '/v5/controls');
});

test('brain and runtime cards have their own tab and do not load on the Providers tab', async () => {
  render(<MemoryRouter><ProvidersScreen /></MemoryRouter>);
  expect(screen.getByRole('tab', { name: 'Providers' })).toHaveAttribute('aria-selected', 'true');
  expect(screen.queryByText('brain card')).not.toBeInTheDocument();
  expect(screen.queryByText('local brain')).not.toBeInTheDocument();

  await userEvent.click(screen.getByRole('tab', { name: 'Brain & Routing' }));
  expect(screen.getByText('brain card')).toBeInTheDocument();
  expect(screen.getByText('local brain')).toBeInTheDocument();
  expect(window.location.hash).toBe('#brain');
});

test('the provider policy is fetched once per load', async () => {
  render(<MemoryRouter><ProvidersScreen /></MemoryRouter>);
  await waitFor(() => expect(api.getProviderPolicy).toHaveBeenCalled());
  expect(api.getProviderPolicy).toHaveBeenCalledTimes(1);
});

test('a #brain link opens straight on the Brain & Routing tab', () => {
  window.location.hash = '#brain';
  render(<MemoryRouter><ProvidersScreen /></MemoryRouter>);
  expect(screen.getByRole('tab', { name: 'Brain & Routing' })).toHaveAttribute('aria-selected', 'true');
});
