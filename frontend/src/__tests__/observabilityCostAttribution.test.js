import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import ObservabilityPage from '../pages/ObservabilityPage';

jest.mock('../api', () => ({
  getSavings: jest.fn(),
  getUsage: jest.fn(),
  getCostAttribution: jest.fn(),
}));

const { getSavings, getUsage, getCostAttribution } = require('../api');

beforeEach(() => {
  getSavings.mockResolvedValue({
    data: {
      summary: {
        total_savings_usd: 0,
        total_tokens: 0,
        total_requests: 0,
        total_infra_cost_usd: 0,
        total_commercial_eq_usd: 0,
      },
      time_series: [],
    },
  });
  getUsage.mockResolvedValue({ data: { by_model: {} } });
});

test('renders spend-by-task-type table when the backend returns tagged data', async () => {
  getCostAttribution.mockResolvedValue({
    data: {
      models: {},
      by_tag: {
        code_generation: { calls: 4, total_tokens: 4000, estimated_cost_usd: 0.12 },
        reasoning: { calls: 1, total_tokens: 500, estimated_cost_usd: 0.01 },
      },
      totals: { calls: 5, estimated_cost_usd: 0.13 },
    },
  });

  render(<ObservabilityPage />);

  await waitFor(() => expect(screen.getByText(/Spend by Task Type/i)).toBeInTheDocument());
  expect(screen.getByText('code_generation')).toBeInTheDocument();
  expect(screen.getByText('reasoning')).toBeInTheDocument();
});

test('does not render the task-type table when there is no tagged data yet', async () => {
  getCostAttribution.mockResolvedValue({
    data: { models: {}, by_tag: {}, totals: { calls: 0, estimated_cost_usd: 0 } },
  });

  render(<ObservabilityPage />);

  await waitFor(() => expect(screen.queryByText(/Loading cost data/i)).not.toBeInTheDocument());
  expect(screen.queryByText(/Spend by Task Type/i)).not.toBeInTheDocument();
});

test('page still renders when the cost-attribution call fails', async () => {
  getCostAttribution.mockRejectedValue(new Error('unauthorized'));

  render(<ObservabilityPage />);

  await waitFor(() => expect(screen.queryByText(/Loading cost data/i)).not.toBeInTheDocument());
  expect(screen.queryByText(/Spend by Task Type/i)).not.toBeInTheDocument();
});
