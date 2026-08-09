/**
 * McpCard — the MCP section of the Providers screen.
 *
 * The behaviour worth pinning is the one an operator would be misled by: a
 * monitor that is connected and ticking looks healthy even when nothing is
 * fixing what it finds. The card must distinguish "watching" from "healing".
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import McpCard from '../v5/components/McpCard';

jest.mock('../api', () => ({
  fmtErr: (d) => (typeof d === 'string' ? d : ''),
  getRenderHealth: jest.fn(),
  getRenderOpsStatus: jest.fn(),
  runRenderOpsScan: jest.fn(),
}));

const api = require('../api');

const status = (over = {}) => ({
  enabled: true,
  configured: true,
  write_allowed: false,
  interval_seconds: 600,
  ticks: 12,
  findings_filed: 3,
  findings_dropped: 0,
  self_heal_ready: true,
  active_cooldowns: 1,
  last_tick_at: new Date().toISOString(),
  last_error: '',
  ...over,
});

const health = (over = {}) => ({
  configured: true, reachable: true, tool_count: 9, url: 'http://x/mcp', writes_allowed: false, ...over,
});

const view = () => render(<MemoryRouter><McpCard /></MemoryRouter>);

beforeEach(() => {
  jest.clearAllMocks();
  api.getRenderOpsStatus.mockResolvedValue({ data: status() });
  api.getRenderHealth.mockResolvedValue({ data: health() });
});

test('shows the full chain as healthy when detection and healing are both up', async () => {
  view();

  expect(await screen.findByText('Connected')).toBeInTheDocument();  // the pill, not a stage label
  expect(await screen.findByText(/Reachable · 9 tools/)).toBeInTheDocument();
  expect(screen.getByText(/schedules the repair task automatically/)).toBeInTheDocument();
});

test('calls out that nothing is healing when the improvement loop is down', async () => {
  api.getRenderOpsStatus.mockResolvedValue({ data: status({ self_heal_ready: false }) });
  view();

  await screen.findByText('Filed');
  expect(screen.getByText(/detected but nothing will fix them/)).toBeInTheDocument();
});

test('surfaces dropped findings rather than showing a silent zero', async () => {
  api.getRenderOpsStatus.mockResolvedValue({
    data: status({ self_heal_ready: false, findings_dropped: 4 }),
  });
  view();

  await screen.findByText('Filed');
  expect(screen.getByText(/4 findings detected but never/)).toBeInTheDocument();
});

test('says what is missing when Render is not configured', async () => {
  api.getRenderOpsStatus.mockResolvedValue({ data: status({ configured: false, enabled: true }) });
  api.getRenderHealth.mockResolvedValue({
    data: health({ configured: false, reachable: false, reason: 'RENDER_API_KEY not set' }),
  });
  view();

  await waitFor(() => expect(screen.getByText('Not configured')).toBeInTheDocument());
  expect(screen.getByText(/Set RENDER_API_KEY/)).toBeInTheDocument();
  // Health is a second request that resolves after the status one, so this
  // assertion has to wait for it rather than assume both landed together.
  expect(await screen.findByText(/RENDER_API_KEY not set/)).toBeInTheDocument();
});

test('scan is blocked until Render is configured', async () => {
  api.getRenderOpsStatus.mockResolvedValue({ data: status({ configured: false }) });
  view();

  await waitFor(() => expect(screen.getByText('Not configured')).toBeInTheDocument());
  expect(screen.getByRole('button', { name: /Scan now/ })).toBeDisabled();
  expect(api.runRenderOpsScan).not.toHaveBeenCalled();
});

test('a clean scan reports no failures rather than an empty list', async () => {
  api.runRenderOpsScan.mockResolvedValue({ data: { findings: [], count: 0, status: status() } });
  view();

  // The button stays disabled until the status fetch resolves — waiting on
  // rendered text alone would click it while it is still inert.
  await waitFor(() => expect(screen.getByRole('button', { name: /Scan now/ })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: /Scan now/ }));

  expect(await screen.findByText(/no platform failures right now/)).toBeInTheDocument();
});

test('a scan with findings lists them', async () => {
  api.runRenderOpsScan.mockResolvedValue({
    data: {
      count: 1,
      findings: [{
        signature: 'abc123',
        kind: 'error_logs',
        service_name: 'local-llm-server',
        severity: 'high',
        title: 'Render error-log spike on local-llm-server (18 in 20m)',
      }],
      status: status(),
    },
  });
  view();

  // The button stays disabled until the status fetch resolves — waiting on
  // rendered text alone would click it while it is still inert.
  await waitFor(() => expect(screen.getByRole('button', { name: /Scan now/ })).toBeEnabled());
  fireEvent.click(screen.getByRole('button', { name: /Scan now/ }));

  expect(await screen.findByText(/Render error-log spike/)).toBeInTheDocument();
  expect(screen.getByText(/error_logs · local-llm-server/)).toBeInTheDocument();
});

test('write permission is shown, since it is the difference between read-only and mutating', async () => {
  api.getRenderOpsStatus.mockResolvedValue({ data: status({ write_allowed: true }) });
  view();

  await waitFor(() => expect(screen.getByText('Writes allowed')).toBeInTheDocument());
});

test('reports the failure instead of rendering zeroes that look healthy', async () => {
  api.getRenderOpsStatus.mockRejectedValue({ response: { data: { detail: 'Admin role required' } } });
  view();

  expect(await screen.findByText('Admin role required')).toBeInTheDocument();
});


test('self-healing cannot be green while monitoring is stopped', async () => {
  // The backend can legitimately report self_heal_ready=true (the improvement
  // loop is up) while the ops loop is off. Showing that as healthy would claim
  // repairs are running with nothing producing findings to repair.
  api.getRenderOpsStatus.mockResolvedValue({
    data: status({ enabled: false, self_heal_ready: true }),
  });
  view();

  await screen.findByText('Filed');
  expect(screen.getByText(/Ops loop is off/)).toBeInTheDocument();
  expect(screen.getByText(/Nothing is being monitored, so there are no findings to repair/))
    .toBeInTheDocument();
  expect(screen.queryByText(/schedules the repair task automatically/)).not.toBeInTheDocument();
});
