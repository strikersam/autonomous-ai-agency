/**
 * WorkflowScreen — the UI over the CRISPY workflow engine (/api/workflow).
 *
 * Guards the two behaviours that matter:
 *   1. a run at `awaiting_approval` shows Approve/Reject and the click lifts the
 *      hard gate via POST /api/workflow/{id}/approve with the approver identity;
 *   2. starting a run sends { request, title } to POST /api/workflow/build.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

jest.mock('../api', () => ({
  __esModule: true,
  getWorkflowRuns: jest.fn(),
  getWorkflowRun: jest.fn(),
  buildWorkflow: jest.fn(),
  approveWorkflow: jest.fn(),
  rejectWorkflow: jest.fn(),
  cancelWorkflow: jest.fn(),
  fmtErr: (d) => (typeof d === 'string' ? d : JSON.stringify(d)),
}));

import * as api from '../api';
import WorkflowScreen from '../v5/screens/WorkflowScreen';

beforeEach(() => jest.clearAllMocks());

test('approving an awaiting_approval run lifts the gate with the approver identity', async () => {
  api.getWorkflowRuns.mockResolvedValue({
    data: { runs: [{ run_id: 'wf_abc123', title: 'Add a health endpoint', status: 'awaiting_approval', created_at: '2026-09-05T00:00:00Z' }], count: 1 },
  });
  api.getWorkflowRun.mockResolvedValue({
    data: {
      run_id: 'wf_abc123', title: 'Add a health endpoint', status: 'awaiting_approval',
      phases: [{ phase_id: 'p1', name: 'plan', status: 'done', agent_role: 'architect' }],
      slices: [], created_at: '2026-09-05T00:00:00Z',
    },
  });
  api.approveWorkflow.mockResolvedValue({ data: { status: 'executing' } });

  render(<WorkflowScreen />);

  fireEvent.click(await screen.findByText('Add a health endpoint'));
  fireEvent.click(await screen.findByText('Approve'));

  await waitFor(() =>
    expect(api.approveWorkflow).toHaveBeenCalledWith('wf_abc123', 'admin')
  );
});

test('starting a workflow posts { request, title } to build', async () => {
  api.getWorkflowRuns.mockResolvedValue({ data: { runs: [], count: 0 } });
  api.buildWorkflow.mockResolvedValue({ data: { run_id: 'wf_new' } });

  render(<WorkflowScreen />);

  fireEvent.click(await screen.findByText('+ New workflow'));
  fireEvent.change(screen.getByPlaceholderText(/Title \(optional\)/i), { target: { value: 'My run' } });
  fireEvent.change(screen.getByPlaceholderText(/Describe the task/i), { target: { value: 'Do the thing thoroughly' } });
  fireEvent.click(screen.getByText('Start workflow'));

  await waitFor(() =>
    expect(api.buildWorkflow).toHaveBeenCalledWith({ request: 'Do the thing thoroughly', title: 'My run' })
  );
});
