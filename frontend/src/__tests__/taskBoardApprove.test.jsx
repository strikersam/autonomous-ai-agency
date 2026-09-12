/**
 * TaskBoardScreen — the board-level "Approve & release" button.
 *
 * Regression for the bug where clicking "→ Approve & release" on an in_review
 * card POSTed `{ approved: true, reason }` to /api/tasks/{id}/approve. That
 * endpoint validates against ApprovalRequest, which requires `checkpoint_id`
 * and `approve`, so every click 422'd with
 * "checkpoint_id: Field required; approve: Field required".
 *
 * The fix routes the click by what the task actually carries:
 *   - a task with pending approval checkpoints → approve each one with the
 *     canonical { checkpoint_id, approve, reason } body;
 *   - a reviewed task with no checkpoints → PATCH it straight to `done`.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

jest.mock('../api', () => {
  const API = { get: jest.fn() };
  return {
    __esModule: true,
    API,
    approveTaskCheckpoint: jest.fn(),
    updateTask: jest.fn(),
    fetchSprints: jest.fn(),
    fmtErr: (d) => (typeof d === 'string' ? d : JSON.stringify(d)),
  };
});

import * as api from '../api';
import TaskBoardScreen from '../v5/screens/TaskBoardScreen';

function mockBoard(tasks, gated = []) {
  api.API.get.mockImplementation((url) => {
    if (url === '/api/tasks/') return Promise.resolve({ data: { tasks } });
    // awaiting-approval (pre-execution gate) list.
    return Promise.resolve({ data: { tasks: gated } });
  });
}

beforeEach(() => jest.clearAllMocks());

test('approving a reviewed task with a pending checkpoint sends the canonical body', async () => {
  api.approveTaskCheckpoint.mockResolvedValue({ data: {} });
  mockBoard([{
    task_id: 'task_abc',
    title: 'Ship the thing',
    status: 'in_review',
    priority: 'medium',
    approval_checkpoints: [
      { checkpoint_id: 'chk_1', required: true, approved: null },
    ],
  }]);

  render(<TaskBoardScreen />);
  const btn = await screen.findByText(/Approve & release/i);
  fireEvent.click(btn);

  await waitFor(() =>
    expect(api.approveTaskCheckpoint).toHaveBeenCalledWith('task_abc', {
      checkpoint_id: 'chk_1',
      approve: true,
      reason: 'Approved via board',
    })
  );
  // The old malformed { approved: true } body must never be sent again.
  expect(api.approveTaskCheckpoint).not.toHaveBeenCalledWith(
    'task_abc', expect.objectContaining({ approved: true })
  );
  expect(api.updateTask).not.toHaveBeenCalled();
});

test('a gated task renders once — in the gate lane, not also in its lifecycle column', async () => {
  // Regression: awaiting-approval tasks are runnable (status todo/in_progress),
  // so before the fix they showed in BOTH the "To be approved" GateColumn and
  // the "To Do" lifecycle column — the duplicate-task complaint on the board.
  const gatedTask = {
    task_id: 'task_gated',
    title: 'Gated portfolio fix',
    status: 'todo',
    priority: 'high',
    requires_approval: true,
    approval_checkpoints: [],
  };
  mockBoard([gatedTask], [gatedTask]);

  render(<TaskBoardScreen />);
  await waitFor(() =>
    expect(screen.getAllByText('Gated portfolio fix')).toHaveLength(1)
  );
});

test('approving a reviewed task with no checkpoints releases it to done', async () => {
  api.updateTask.mockResolvedValue({ data: {} });
  mockBoard([{
    task_id: 'task_xyz',
    title: 'No-checkpoint review',
    status: 'in_review',
    priority: 'high',
    approval_checkpoints: [],
  }]);

  render(<TaskBoardScreen />);
  const btn = await screen.findByText(/Approve & release/i);
  fireEvent.click(btn);

  await waitFor(() =>
    expect(api.updateTask).toHaveBeenCalledWith('task_xyz', { status: 'done' })
  );
  expect(api.approveTaskCheckpoint).not.toHaveBeenCalled();
});
