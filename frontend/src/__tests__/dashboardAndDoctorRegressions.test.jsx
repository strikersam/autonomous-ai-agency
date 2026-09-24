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
import { render, screen } from '@testing-library/react';

jest.mock('../v5/hooks/useSafeData', () => ({
  useSafeData: jest.fn(),
}));

jest.mock('../api', () => ({
  API: { get: jest.fn() },
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
      jest.fn(),
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
      jest.fn(),
    ]);

    render(<DoctorScreen onNavigate={() => {}} />);

    expect(screen.getByText('NVIDIA key')).toBeInTheDocument();
    expect(screen.queryByText(/Fix all/)).not.toBeInTheDocument();
  });
});
