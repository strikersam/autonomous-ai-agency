/**
 * Runs screens: the list (GET /api/runs), the detail view answering the operator's
 * questions, and the cancel / retry buttons. The api module is mocked.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react';

vi.mock('../api', () => ({
  __esModule: true,
  listRuns: vi.fn(),
  getRun: vi.fn(),
  getRunEvents: vi.fn(),
  getRunArtifacts: vi.fn(),
  getRunCapabilities: vi.fn(),
  cancelRun: vi.fn(),
  retryRun: vi.fn(),
}));

import * as api from '../api';
import RunsScreen from '../v5/screens/RunsScreen';
import { costText, recoverText, canCancel, canRetry } from '../v5/screens/runsModel';

const NOW = Date.now() / 1000;
const run = (over = {}) => ({
  run_id: 'run_aaaaaaaaaaaa1111', state: 'running', agent_id: 'coder', owner_id: 'u1', attempt: 2,
  created_at: NOW - 125, usage: { cost_usd: 0.042 }, budget: { max_cost_usd: 1 }, runtime_id: 'internal_agent',
  resolved_model: 'nemotron', phase: 'executing', skill_versions: { a: 'sha-1' }, artifact_refs: [], ...over,
});

function mockApi(r) {
  api.listRuns.mockResolvedValue({ data: { runs: [r] } });
  api.getRun.mockResolvedValue({ data: r });
  api.getRunEvents.mockResolvedValue({ data: { run_id: r.run_id, events: [
    { event_id: 'e1', seq: 1, kind: 'created', data: {} },
    { event_id: 'e2', seq: 2, kind: 'attempt_started', data: { attempt: 2 } },
  ], next_after_seq: 2 } });
  api.getRunArtifacts.mockResolvedValue({ data: { run_id: r.run_id, artifacts: ['s3://bucket/report.md'] } });
  api.getRunCapabilities.mockResolvedValue({ data: { backend: 'mongo', durable_lease: true,
    recovery: 'cross_host', recovery_enabled: true, ledger_enabled: true, checkpoint_durable: true } });
}

beforeEach(() => vi.clearAllMocks());

test('the list shows state, agent, owner, attempt, cost and age', async () => {
  mockApi(run());
  render(<RunsScreen />);
  const row = (await screen.findByRole('button', { name: /Open run run_aaaaaaaaaaaa1111/ })).closest('tr');
  const cells = within(row);
  expect(cells.getByText('running')).toBeInTheDocument();
  expect(cells.getByText('coder')).toBeInTheDocument();
  expect(cells.getByText('u1')).toBeInTheDocument();
  expect(cells.getByText('2')).toBeInTheDocument();
  expect(cells.getByText('$0.0420 / $1.00')).toBeInTheDocument();
  expect(cells.getByText('2m')).toBeInTheDocument();
});

test('an empty list and a failing list both render', async () => {
  api.listRuns.mockResolvedValue({ data: { runs: [] } });
  const { unmount } = render(<RunsScreen />);
  expect(await screen.findByText('No runs yet.')).toBeInTheDocument();
  unmount();
  api.listRuns.mockRejectedValue(new Error('x'));
  render(<RunsScreen />);
  expect(await screen.findByRole('alert')).toHaveTextContent('Could not load runs.');
});

test('the state filter is sent to the API', async () => {
  mockApi(run());
  render(<RunsScreen />);
  await screen.findByText('coder');
  fireEvent.change(screen.getByLabelText('Filter by state'), { target: { value: 'failed' } });
  await waitFor(() => expect(api.listRuns).toHaveBeenLastCalledWith({ state: 'failed', limit: 100 }));
});

test('the detail answers agent, where, doing, cost, recovery, events and evidence', async () => {
  mockApi(run());
  render(<RunsScreen />);
  fireEvent.click(await screen.findByRole('button', { name: /Open run/ }));
  const summary = await screen.findByRole('region', { name: 'Run summary' });
  expect(within(summary).getByText('coder')).toBeInTheDocument();
  expect(within(summary).getByText('internal_agent · nemotron')).toBeInTheDocument();
  expect(within(summary).getByText('executing')).toBeInTheDocument();
  expect(within(summary).getByText('$0.0420 / $1.00')).toBeInTheDocument();
  expect(within(summary).getByText('Recovers on any host, checkpointed')).toBeInTheDocument();
  expect(within(screen.getByRole('region', { name: 'Completed events' })).getByText('attempt started')).toBeInTheDocument();
  expect(within(screen.getByRole('region', { name: 'Evidence' })).getByText('s3://bucket/report.md')).toBeInTheDocument();
});

test('cancel calls the cancel endpoint for a live run', async () => {
  mockApi(run());
  api.cancelRun.mockResolvedValue({ data: { run_id: 'x', state: 'running', cancel_requested: true, settled: false } });
  render(<RunsScreen />);
  fireEvent.click(await screen.findByRole('button', { name: /Open run/ }));
  fireEvent.click(await screen.findByRole('button', { name: 'Cancel run' }));
  await waitFor(() => expect(api.cancelRun).toHaveBeenCalledWith('run_aaaaaaaaaaaa1111'));
  expect(await screen.findByText('Cancel requested.')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Retry run' })).toBeNull();
});

test('retry shows for a failed run and reports the new run', async () => {
  mockApi(run({ state: 'failed', failure_reason: 'boom' }));
  api.retryRun.mockResolvedValue({ data: { run_id: 'run_new', task_id: 't', state: 'queued', created: true } });
  render(<RunsScreen />);
  fireEvent.click(await screen.findByRole('button', { name: /Open run/ }));
  fireEvent.click(await screen.findByRole('button', { name: 'Retry run' }));
  await waitFor(() => expect(api.retryRun).toHaveBeenCalledWith('run_aaaaaaaaaaaa1111'));
  expect(await screen.findByText('Retry queued as run_new.')).toBeInTheDocument();
  expect(screen.queryByRole('button', { name: 'Cancel run' })).toBeNull();
});

test('a retry conflict is reported, not thrown', async () => {
  mockApi(run({ state: 'failed' }));
  api.retryRun.mockRejectedValue({ response: { status: 409 } });
  render(<RunsScreen />);
  fireEvent.click(await screen.findByRole('button', { name: /Open run/ }));
  fireEvent.click(await screen.findByRole('button', { name: 'Retry run' }));
  expect(await screen.findByText(/already changed/)).toBeInTheDocument();
});

test('model helpers', () => {
  expect(costText({})).toBe('—');
  expect(costText({ budget: { max_cost_usd: 2 } })).toBe('budget $2.00');
  expect(recoverText(null, run())).toBe('Unknown');
  expect(recoverText({ recovery: 'none', recovery_enabled: true }, run())).toBe('No automatic recovery');
  expect(canCancel('succeeded')).toBe(false);
  expect(canRetry('dead_letter')).toBe(true);
});
