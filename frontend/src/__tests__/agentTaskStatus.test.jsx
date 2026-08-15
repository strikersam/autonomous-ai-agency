import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import AgentTaskStatus, { TASK_STATUS_META } from '../components/AgentTaskStatus.jsx';

describe('AgentTaskStatus', () => {
  const tasks = [
    { task_id: 't1', title: 'Fix login bug', status: 'in_progress', agent_id: 'agent_impl', updated_at: '2026-08-15T10:00:00.000Z' },
    { task_id: 't2', title: 'Write docs', status: 'done', updated_at: '2026-08-14T09:00:00.000Z' },
    { task_id: 't3', title: 'Broken deploy', status: 'failed', updated_at: '2026-08-13T08:00:00.000Z' },
  ];
  const counts = { in_progress: 2, failed: 1, done: 5, todo: 0 };

  it('renders a summary chip per non-zero status and skips zero counts', () => {
    render(<AgentTaskStatus counts={counts} tasks={tasks} />);
    expect(screen.getByTestId('task-status-chip-in_progress')).toHaveTextContent('2');
    expect(screen.getByTestId('task-status-chip-failed')).toHaveTextContent('1');
    expect(screen.getByTestId('task-status-chip-done')).toHaveTextContent('5');
    // todo has a zero count → no chip
    expect(screen.queryByTestId('task-status-chip-todo')).toBeNull();
  });

  it('orders summary chips with active/attention statuses first', () => {
    render(<AgentTaskStatus counts={counts} tasks={tasks} />);
    const chips = screen.getByTestId('task-status-summary').querySelectorAll('[data-testid^="task-status-chip-"]');
    const order = Array.from(chips).map((c) => c.getAttribute('data-testid'));
    expect(order).toEqual([
      'task-status-chip-in_progress',
      'task-status-chip-failed',
      'task-status-chip-done',
    ]);
  });

  it('renders a row per task with title and humanized status label', () => {
    render(<AgentTaskStatus counts={counts} tasks={tasks} />);
    expect(screen.getByTestId('task-row-t1')).toHaveTextContent('Fix login bug');
    expect(screen.getByTestId('task-row-t1')).toHaveTextContent('Running'); // in_progress label
    expect(screen.getByTestId('task-row-t3')).toHaveTextContent('Failed');
  });

  it('limits rows to maxRows', () => {
    render(<AgentTaskStatus counts={counts} tasks={tasks} maxRows={2} />);
    expect(screen.getByTestId('task-row-t1')).toBeInTheDocument();
    expect(screen.getByTestId('task-row-t2')).toBeInTheDocument();
    expect(screen.queryByTestId('task-row-t3')).toBeNull();
  });

  it('shows an empty state when there are no tasks', () => {
    render(<AgentTaskStatus counts={{}} tasks={[]} />);
    expect(screen.getByText('No agent tasks yet')).toBeInTheDocument();
  });

  it('fires onSelectTask and onViewAll', async () => {
    const onSelectTask = jest.fn();
    const onViewAll = jest.fn();
    render(<AgentTaskStatus counts={counts} tasks={tasks} onSelectTask={onSelectTask} onViewAll={onViewAll} />);
    await userEvent.click(screen.getByTestId('task-row-t1'));
    expect(onSelectTask).toHaveBeenCalledWith(tasks[0]);
    await userEvent.click(screen.getByText('View all'));
    expect(onViewAll).toHaveBeenCalled();
  });

  it('status meta stays in sync with the backend TaskStatus vocabulary', () => {
    // Mirrors tasks/models.py::TaskStatus — a drift here means the dashboard
    // would render an unknown status with a fallback label.
    expect(Object.keys(TASK_STATUS_META).sort()).toEqual(
      ['blocked', 'done', 'failed', 'in_progress', 'in_review', 'needs_clarification', 'todo'].sort()
    );
  });
});
