/**
 * Regressions from the 2026-09 QA pass.
 *
 *  - Dashboard "Open Tasks" listed wont_do tasks (a terminal status in
 *    tasks/models.py) as open work, and the status donut filed wont_do and
 *    needs_clarification under "To do".
 *  - Doctor showed a "Fix all" button whenever a check was not passing; it
 *    POSTed to /api/doctor/fix-all, which does not exist, so it did nothing.
 */
import React from 'react';
import { render, screen, within } from '@testing-library/react';

vi.mock('../v5/hooks/useSafeData', () => ({
  useSafeData: vi.fn(),
}));

vi.mock('../api', () => ({
  API: { get: vi.fn() },
}));

import { useSafeData } from '../v5/hooks/useSafeData';
import { DashboardScreen } from '../v5/screens/DashboardScreen';
import { DoctorScreen } from '../v5/screens/DoctorScreen';

const idle = { loading: false, error: null };

describe('DashboardScreen open tasks', () => {
  test('excludes every terminal status, including wont_do', () => {
    const tasks = [
      { id: 't1', title: 'Still to do', status: 'todo' },
      { id: 't2', title: 'Waiting on a human', status: 'needs_clarification' },
      { id: 't3', title: 'Declined by owner', status: 'wont_do' },
      { id: 't4', title: 'Shipped already', status: 'done' },
      { id: 't5', title: 'Broke already', status: 'failed' },
    ];
    useSafeData.mockReturnValue([
      { tasks: { tasks } },
      new Proxy({}, { get: () => idle }),
      vi.fn(),
    ]);

    render(<DashboardScreen />);

    expect(screen.getByText('Still to do')).toBeInTheDocument();
    expect(screen.getByText('Waiting on a human')).toBeInTheDocument();
    expect(screen.queryByText('Declined by owner')).not.toBeInTheDocument();
    expect(screen.queryByText('Shipped already')).not.toBeInTheDocument();
    expect(screen.queryByText('Broke already')).not.toBeInTheDocument();
  });
});

describe('DoctorScreen', () => {
  test('offers no "Fix all" button backed by a nonexistent endpoint', () => {
    useSafeData.mockReturnValue([
      {
        report: {
          ready: false,
          summary: '1 check failing',
          checks: [{ id: 'nvidia', label: 'NVIDIA key', status: 'fail', detail: 'missing' }],
          run_at: '2026-09-23T00:00:00Z',
        },
        runtimes: { health: [] },
      },
      { report: idle, runtimes: idle },
      vi.fn(),
    ]);

    render(<DoctorScreen onNavigate={() => {}} />);

    expect(screen.getByText('NVIDIA key')).toBeInTheDocument();
    expect(screen.queryByText(/Fix all/)).not.toBeInTheDocument();
  });
});

describe('DashboardScreen spend-by-task-type widget', () => {
  const render_ = (costByTag) => {
    useSafeData.mockReturnValue([
      { costByTag },
      new Proxy({}, { get: () => idle }),
      vi.fn(),
    ]);
    render(<DashboardScreen />);
  };

  test('free-tier traffic ($0 spend) charts call counts instead of flat slivers', () => {
    render_({
      by_tag: {
        code_generation: { calls: 9, total_tokens: 900, estimated_cost_usd: 0 },
        fast_response: { calls: 3, total_tokens: 90, estimated_cost_usd: 0 },
      },
      totals: { calls: 12, estimated_cost_usd: 0 },
    });
    expect(screen.getByText('Calls by task type')).toBeInTheDocument();
    expect(screen.getByText(/free tier/)).toBeInTheDocument();
    // the biggest bucket is charted at its call count, not at a $0 minimum sliver
    expect(screen.getByTitle('code generation: 9')).toBeInTheDocument();
  });

  test('paid traffic still charts spend', () => {
    render_({
      by_tag: { reasoning: { calls: 2, total_tokens: 500, estimated_cost_usd: 0.0123 } },
      totals: { calls: 2, estimated_cost_usd: 0.0123 },
    });
    expect(screen.getByText('Spend by task type')).toBeInTheDocument();
    expect(screen.getByText(/\$0\.0123 est\. spend/)).toBeInTheDocument();
  });
});

describe('DashboardScreen request-volume trend', () => {
  test('draws the sparkline from /api/observability/savings daily buckets', () => {
    useSafeData.mockReturnValue([
      {
        // /metrics has no time series — only summary + traces
        metrics: { summary_24h: { total_requests: 9, total_tokens: 900, total_savings_usd: 0 }, recent_traces: [] },
        usageTrend: { time_series: [{ requests: 2 }, { requests: 5 }, { requests: 2 }] },
      },
      new Proxy({}, { get: () => idle }),
      vi.fn(),
    ]);
    render(<DashboardScreen />);
    expect(screen.getByText('3 buckets')).toBeInTheDocument();
  });
});

describe('DashboardScreen matches the Tasks board approval gate', () => {
  // The board treats a task as "To be approved" only while
  // /api/tasks/awaiting-approval returns it. Home keyed off the bare
  // requires_approval flag, so approved/running/done tasks stayed in
  // "Needs you" and gated tasks the board list missed never appeared.
  test('uses /awaiting-approval, not requires_approval, for "Needs you"', () => {
    const tasks = [
      { task_id: 'a1', title: 'Approved and running', status: 'in_progress', requires_approval: true, execution_approved: true },
      { task_id: 'a2', title: 'Approved and shipped', status: 'done', requires_approval: true, execution_approved: true },
      { task_id: 'g1', title: 'Parked at gate', status: 'todo', requires_approval: true },
    ];
    const gated = [
      { task_id: 'g1', title: 'Parked at gate', status: 'todo', requires_approval: true },
      { task_id: 'g2', title: 'Gated, off the first page', status: 'todo', requires_approval: true },
    ];
    useSafeData.mockReturnValue([
      { tasks: { tasks }, gated: { tasks: gated } },
      new Proxy({}, { get: () => idle }),
      vi.fn(),
    ]);

    render(<DashboardScreen />);

    const needsYou = screen.getByRole('region', { name: 'Needs you' });
    expect(within(needsYou).getByText('Parked at gate')).toBeInTheDocument();
    expect(within(needsYou).getByText('Gated, off the first page')).toBeInTheDocument();
    expect(within(needsYou).queryByText('Approved and running')).not.toBeInTheDocument();
    expect(within(needsYou).queryByText('Approved and shipped')).not.toBeInTheDocument();
    // The running task is open work, as on the board's Running column.
    expect(screen.getByText('Approved and running')).toBeInTheDocument();
    // A gated task is counted once, not also as To do.
    expect(screen.getAllByText('Parked at gate')).toHaveLength(1);
  });
});

describe('DashboardScreen task totals are not capped at one page', () => {
  test('the status donut counts from /api/tasks/counts, not the 50-row list', () => {
    useSafeData.mockReturnValue([
      {
        tasks: { tasks: [{ task_id: 'x', title: 'Only row on the page', status: 'done' }] },
        taskCounts: { counts: { done: 120, todo: 7 } },
        gated: { tasks: [] },
      },
      new Proxy({}, { get: () => idle }),
      vi.fn(),
    ]);

    render(<DashboardScreen />);

    // Donut center total = 127, not the single listed row.
    expect(screen.getByText('127')).toBeInTheDocument();
  });
});

describe('DashboardScreen gate totals beyond the 50-row gate list', () => {
  test('moves every gated task to "Awaiting approval", using the uncapped counts', () => {
    useSafeData.mockReturnValue([
      {
        tasks: { tasks: [] },
        // 60 todo in total, 55 of them gated; /awaiting-approval returned only 1.
        taskCounts: { counts: { todo: 60 }, awaiting_approval: { todo: 55 } },
        gated: { tasks: [{ task_id: 'g1', title: 'One listed gate', status: 'todo' }] },
      },
      new Proxy({}, { get: () => idle }),
      vi.fn(),
    ]);

    render(<DashboardScreen />);

    expect(screen.getByText('60')).toBeInTheDocument();          // donut total
    expect(screen.getByText(/Awaiting approval/)).toBeInTheDocument();
    expect(screen.getByText('55')).toBeInTheDocument();          // gate slice
    expect(screen.getByText('5')).toBeInTheDocument();           // remaining To do
  });
});
