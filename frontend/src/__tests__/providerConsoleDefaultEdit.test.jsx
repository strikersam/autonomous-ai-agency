/**
 * Provider console — "Make default" and inline Edit.
 *
 * The operator could not change the default provider (no control called the
 * handler) and Edit rendered its form at the bottom of the page, so on a phone
 * it looked like nothing happened. This pins:
 *  - the default row sits directly under the serving one,
 *  - "Make default" appears on non-default stored rows and calls the handler,
 *  - the edit form renders inside the row being edited.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

jest.mock('../api', () => ({
  getLlmStatus: jest.fn(),
  getLlmProviders: jest.fn(),
  fmtErr: (d) => String(d || ''),
}));

import * as api from '../api';
import ProviderConsole, { mergeProviders } from '../v5/components/ProviderConsole';

const stored = [
  { provider_id: 'zai-glm', name: 'Glm-5.2', base_url: 'https://api.z.ai/v1', type: 'openai-compatible', is_default: true },
  { provider_id: 'nvidia-nim', name: 'Nvidia NIM (Free)', base_url: 'https://integrate.api.nvidia.com', type: 'openai-compatible', is_default: false },
];
const routed = [
  { id: 'nvidia', tier: 'free', health: { state: 'closed', success_rate: 1, total_requests: 9 } },
  { id: 'groq', tier: 'free', health: { state: 'closed', success_rate: 0.99, total_requests: 9 } },
];

beforeEach(() => {
  api.getLlmStatus.mockResolvedValue({ data: {} });
  api.getLlmProviders.mockResolvedValue({ data: { providers: routed } });
});

test('the default provider sits directly under the serving one', () => {
  const rows = mergeProviders({ routed, stored, catalogue: [] });
  expect(rows[0].id).toBe('nvidia');
  expect(rows[0].state).toBe('serving');
  expect(rows[1].id).toBe('zai-glm');
  expect(rows[1].isDefault).toBe(true);
});

test('Make default calls the handler for a non-default stored provider', async () => {
  const onSetDefault = jest.fn();
  render(<ProviderConsole storedProviders={stored} onSetDefault={onSetDefault} onEditProvider={() => {}} onDeleteProvider={() => {}} onTestProvider={jest.fn()} />);
  await waitFor(() => expect(screen.getByText('Nvidia NIM (Free)')).toBeInTheDocument());
  await userEvent.click(screen.getByText('Nvidia NIM (Free)'));
  await userEvent.click(await screen.findByRole('button', { name: 'Make default' }));
  expect(onSetDefault).toHaveBeenCalledWith('nvidia-nim');
});

test('the edit form renders inside the row being edited', async () => {
  render(
    <ProviderConsole
      storedProviders={stored}
      editingId="zai-glm"
      renderEditor={(prov) => <div>Editing {prov.provider_id}</div>}
      onEditProvider={() => {}} onDeleteProvider={() => {}} onTestProvider={jest.fn()}
    />,
  );
  expect(await screen.findByText('Editing zai-glm')).toBeInTheDocument();
});
