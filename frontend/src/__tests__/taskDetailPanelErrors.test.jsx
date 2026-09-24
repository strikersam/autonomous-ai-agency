/**
 * TaskDetailPanel regressions from the 2026-09 QA pass.
 *
 *  - A wont_do task opened with its status picker showing "todo": the option
 *    list omitted wont_do, so React fell back to the first option.
 *  - Failed updates showed axios's "Request failed with status code 400"
 *    instead of the backend's reason, and a 422 detail (an array of objects)
 *    was put straight into state, which React cannot render.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

jest.mock('../api', () => ({
  getTask: jest.fn(),
  updateTask: jest.fn(),
  fetchSprints: jest.fn(),
  fmtErr: jest.requireActual('../api').fmtErr,
}));
jest.mock('../v5/components/Charts', () => ({ ExecutionTimeline: () => null }));

import * as api from '../api';
import TaskDetailPanel from '../v5/screens/TaskDetailPanel';

beforeEach(() => {
  api.fetchSprints.mockResolvedValue({ data: { data: [] } });
});

function task(over = {}) {
  return {
    task_id: 't1', title: 'Probe', description: '', status: 'todo', priority: 'medium',
    comments: [], execution_log: [], created_at: 0, updated_at: 0, ...over,
  };
}

test('a wont_do task shows wont_do in its status picker', async () => {
  api.getTask.mockResolvedValue({ data: { task: task({ status: 'wont_do' }) } });
  render(<TaskDetailPanel taskId="t1" onClose={() => {}} />);
  const picker = await screen.findByDisplayValue('wont do');
  expect(picker.value).toBe('wont_do');
});

test('a rejected transition shows the backend reason', async () => {
  api.getTask.mockResolvedValue({ data: { task: task() } });
  api.updateTask.mockRejectedValue({
    message: 'Request failed with status code 400',
    response: { data: { detail: 'Cannot transition task from todo to done' } },
  });
  render(<TaskDetailPanel taskId="t1" onClose={() => {}} />);
  fireEvent.change(await screen.findByDisplayValue('todo'), { target: { value: 'done' } });
  expect(await screen.findByText(/Cannot transition task from todo to done/)).toBeInTheDocument();
});

test('a 422 detail array renders as text instead of crashing', async () => {
  api.getTask.mockResolvedValue({ data: { task: task() } });
  api.updateTask.mockRejectedValue({
    message: 'Request failed with status code 422',
    response: { data: { detail: [{ loc: ['body', 'priority'], msg: 'Input should be low' }] } },
  });
  render(<TaskDetailPanel taskId="t1" onClose={() => {}} />);
  fireEvent.change(await screen.findByDisplayValue('medium'), { target: { value: 'low' } });
  await waitFor(() => expect(screen.getByText(/priority: Input should be low/)).toBeInTheDocument());
});
