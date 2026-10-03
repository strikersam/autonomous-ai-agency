/**
 * SamAvatar — the floating SAM creature.
 *
 * Pins: hidden unless the server says so (SAM_AVATAR_ENABLED is off by
 * default), a failed config call keeps it hidden, it talks to the same
 * /agent/sam/chat as the voice screen, and only admins get orchestration chips.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

jest.mock('../api', () => ({
  samAvatarConfig: jest.fn(),
  samChat: jest.fn(),
}));

import * as api from '../api';
import SamAvatar from '../v5/components/SamAvatar';

beforeEach(() => jest.clearAllMocks());

test('stays hidden when the toggle is off', async () => {
  api.samAvatarConfig.mockResolvedValue({ data: { enabled: false, can_orchestrate: true } });
  render(<SamAvatar />);
  await waitFor(() => expect(api.samAvatarConfig).toHaveBeenCalled());
  expect(screen.queryByRole('button', { name: /open sam/i })).toBeNull();
});

test('stays hidden when the config call fails', async () => {
  api.samAvatarConfig.mockRejectedValue(new Error('401'));
  render(<SamAvatar />);
  await waitFor(() => expect(api.samAvatarConfig).toHaveBeenCalled());
  expect(screen.queryByRole('button', { name: /open sam/i })).toBeNull();
});

test('admin opens SAM, uses an orchestration chip, sees the reply', async () => {
  api.samAvatarConfig.mockResolvedValue({ data: { enabled: true, can_orchestrate: true } });
  api.samChat.mockResolvedValue({ data: { text: 'The CEO loop is running.' } });
  render(<SamAvatar />);
  await userEvent.click(await screen.findByRole('button', { name: /open sam/i }));
  await userEvent.click(screen.getByRole('button', { name: 'Brief me' }));
  expect(api.samChat).toHaveBeenCalledWith('Brief me', 'sam-avatar');
  expect(await screen.findByText('The CEO loop is running.')).toBeInTheDocument();
});

test('non-admin gets no orchestration chips', async () => {
  api.samAvatarConfig.mockResolvedValue({ data: { enabled: true, can_orchestrate: false } });
  render(<SamAvatar />);
  await userEvent.click(await screen.findByRole('button', { name: /open sam/i }));
  expect(screen.queryByRole('button', { name: 'Triage the queue' })).toBeNull();
  expect(screen.getByRole('button', { name: 'What alerts do I have?' })).toBeInTheDocument();
});

test('appears without a reload when the toggle is flipped on (re-checks on focus)', async () => {
  api.samAvatarConfig
    .mockResolvedValueOnce({ data: { enabled: false, can_orchestrate: true } })
    .mockResolvedValue({ data: { enabled: true, can_orchestrate: true } });
  render(<SamAvatar />);
  await waitFor(() => expect(api.samAvatarConfig).toHaveBeenCalledTimes(1));
  expect(screen.queryByRole('button', { name: /open sam/i })).toBeNull();

  window.dispatchEvent(new Event('focus'));
  expect(await screen.findByRole('button', { name: /open sam/i })).toBeInTheDocument();
});
