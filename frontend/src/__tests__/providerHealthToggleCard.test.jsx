/**
 * ProviderHealthToggleCard — the operator's per-provider on/off switch.
 *
 * What a regression here would cost: the card is the only place the operator can
 * see WHY a provider went offline and turn it back on. So this pins
 *  - the three statuses (ONLINE / OFF / COOLDOWN) and the auto-disable reason,
 *  - the toggle actually calling the API and re-reading the list afterwards,
 *  - the warning shown when the switch state is not durable — without it, an
 *    operator on an ephemeral disk sees their switches silently reset on deploy
 *    and has no way to learn why,
 *  - a failed load surfacing an error instead of a misleading empty table.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

jest.mock('../api', () => ({
  getBrainProviders: jest.fn(),
  setBrainProviderEnabled: jest.fn(),
}));

import * as api from '../api';
import ProviderHealthToggleCard from '../v5/components/ProviderHealthToggleCard';

const row = (over = {}) => ({
  id: 'groq', name: 'Groq', tier: 'free', default_model: 'llama-3.3-70b-versatile',
  enabled: true, healthy: true, online: true, disabled_reason: '',
  auto_disabled: false, total_calls: 12, total_failures: 0, last_error: '',
  ...over,
});

function respond({ providers, durable = true }) {
  api.getBrainProviders.mockResolvedValue({
    data: {
      providers,
      online_count: providers.filter((p) => p.online).length,
      total_count: providers.length,
      state_durable: durable,
    },
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  api.setBrainProviderEnabled.mockResolvedValue({ data: {} });
});

describe('ProviderHealthToggleCard', () => {
  it('renders each provider with its status and call counts', async () => {
    respond({ providers: [row(), row({ id: 'zhipu', name: 'ZhipuAI' })] });
    render(<ProviderHealthToggleCard />);

    await waitFor(() => expect(screen.getByText('Groq')).toBeInTheDocument());
    expect(screen.getByText('ZhipuAI')).toBeInTheDocument();
    expect(screen.getByText('2 of 2 online')).toBeInTheDocument();
    expect(screen.getAllByText('ONLINE')).toHaveLength(2);
  });

  it('shows OFF with the auto-disable reason so the operator knows what to fix', async () => {
    respond({
      providers: [row({
        enabled: false, online: false, auto_disabled: true,
        disabled_reason: 'auto: 401 invalid or expired API key',
        total_failures: 3,
      })],
    });
    render(<ProviderHealthToggleCard />);

    // Both the status pill and the switch read "OFF" for a disabled provider.
    await waitFor(() => expect(screen.getAllByText('OFF')).toHaveLength(2));
    expect(screen.getByRole('button', { name: /Enable Groq/i })).toBeInTheDocument();
    expect(screen.getByText(/401 invalid or expired API key/)).toBeInTheDocument();
    expect(screen.getByText('(auto)')).toBeInTheDocument();
  });

  it('distinguishes a rate-limit cooldown from an operator switch-off', async () => {
    // Enabled but unhealthy = the breaker is open. This must NOT read as OFF:
    // a cooldown recovers on its own, an OFF provider needs a human.
    respond({ providers: [row({ healthy: false, online: false })] });
    render(<ProviderHealthToggleCard />);

    await waitFor(() => expect(screen.getByText('COOLDOWN')).toBeInTheDocument());
    expect(screen.queryByText('OFF')).not.toBeInTheDocument();
  });

  it('toggles a provider off and re-reads the list', async () => {
    respond({ providers: [row()] });
    render(<ProviderHealthToggleCard />);
    await waitFor(() => expect(screen.getByText('Groq')).toBeInTheDocument());

    await userEvent.click(screen.getByRole('button', { name: /Disable Groq/i }));

    await waitFor(() =>
      expect(api.setBrainProviderEnabled).toHaveBeenCalledWith('groq', false));
    expect(api.getBrainProviders).toHaveBeenCalledTimes(2);
  });

  it('warns when the switch state will not survive a deploy', async () => {
    respond({ providers: [row()], durable: false });
    render(<ProviderHealthToggleCard />);

    await waitFor(() =>
      expect(screen.getByText(/reset on the next deploy/)).toBeInTheDocument());
    expect(screen.getByText(/STORAGE_BACKEND=mongo/)).toBeInTheDocument();
  });

  it('shows no durability warning when the state is durable', async () => {
    respond({ providers: [row()], durable: true });
    render(<ProviderHealthToggleCard />);

    await waitFor(() => expect(screen.getByText('Groq')).toBeInTheDocument());
    expect(screen.queryByText(/reset on the next deploy/)).not.toBeInTheDocument();
  });

  it('surfaces a failed load instead of an empty table', async () => {
    api.getBrainProviders.mockRejectedValue({
      response: { data: { detail: 'Not authenticated' } },
    });
    render(<ProviderHealthToggleCard />);

    await waitFor(() =>
      expect(screen.getByText('Not authenticated')).toBeInTheDocument());
    expect(screen.queryByText(/No providers configured/)).not.toBeInTheDocument();
  });

  it('tells the operator when nothing is configured', async () => {
    respond({ providers: [] });
    render(<ProviderHealthToggleCard />);

    await waitFor(() =>
      expect(screen.getByText(/No providers configured/)).toBeInTheDocument());
  });
});
