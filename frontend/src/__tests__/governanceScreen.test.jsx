/**
 * GovernanceScreen — the observe-phase console.
 *
 * The screen exists to answer one question: "is it safe to turn on
 * enforcement yet?" These tests pin the parts of that answer that would be
 * dangerous to get wrong:
 *
 *  - the would-block count is rendered (it is the whole decision input)
 *  - `observe` mode is labelled as not blocking, so nobody reads a green
 *    dashboard as "agents are contained"
 *  - a `local` sandbox backend is called out as having NO isolation rather
 *    than being rendered as just another value
 *  - pending approvals are actionable, and resolving one calls the right API
 *  - one failing endpoint never blanks the screen
 *  - a 403 produces a readable message rather than a crash
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

jest.mock('../api', () => ({
  getGovernanceStatus: jest.fn(),
  getGovernanceMetrics: jest.fn(),
  getGovernanceAudit: jest.fn(),
  getGovernanceApprovals: jest.fn(),
  approveGovernanceRequest: jest.fn(),
  denyGovernanceRequest: jest.fn(),
}));

import * as api from '../api';
import GovernanceScreen from '../v5/screens/GovernanceScreen';

const OBSERVE_STATUS = {
  enabled: true,
  mode: 'observe',
  enforcing: false,
  policy_version: 1,
  groups: ['default', 'research', 'coding'],
  auto_approve: false,
  sandbox: { backend: 'e2b', isolation: { kernel: 'per-sandbox (micro-VM)' } },
};

function mockAll({ status = OBSERVE_STATUS, metrics = { audit: { would_block: 0 } },
                   events = [], approvals = [] } = {}) {
  api.getGovernanceStatus.mockResolvedValue({ data: status });
  api.getGovernanceMetrics.mockResolvedValue({ data: metrics });
  api.getGovernanceAudit.mockResolvedValue({ data: { events, count: events.length } });
  api.getGovernanceApprovals.mockResolvedValue({ data: { approvals, count: approvals.length } });
}

beforeEach(() => jest.clearAllMocks());

test('renders the would-block count — the number that decides when enforce is safe', async () => {
  mockAll({ metrics: { audit: { would_block: 7 } } });
  render(<GovernanceScreen />);
  await waitFor(() => expect(screen.getByText('7')).toBeInTheDocument());
  // The intro prose also names "would-block", so match the stat-card label
  // specifically rather than the first occurrence on the page.
  expect(screen.getByText(/would-block \(if enforcing\)/i)).toBeInTheDocument();
});

test('observe mode is labelled as blocking nothing', async () => {
  mockAll();
  render(<GovernanceScreen />);
  await waitFor(() => expect(screen.getByText('OBSERVE')).toBeInTheDocument());
  expect(screen.getByText(/nothing is blocked/i)).toBeInTheDocument();
});

test('enforce mode is labelled distinctly', async () => {
  mockAll({ status: { ...OBSERVE_STATUS, mode: 'enforce', enforcing: true } });
  render(<GovernanceScreen />);
  await waitFor(() => expect(screen.getByText('ENFORCING')).toBeInTheDocument());
  expect(screen.getByText(/verdicts are acted on/i)).toBeInTheDocument();
});

test('a local sandbox backend is called out as having no hard boundary', async () => {
  // The most important assertion here. Rendering "local" as a neutral value
  // would let an operator believe agents are contained when nothing isolates
  // them at all.
  mockAll({ status: { ...OBSERVE_STATUS, sandbox: { backend: 'local' } } });
  render(<GovernanceScreen />);
  await waitFor(() => expect(screen.getByText(/None \(in-process\)/i)).toBeInTheDocument());
  // The badge hint states the absence; the warning line says what to do about
  // it. Both must be present — an operator needs the fact and the fix.
  expect(screen.getByText(/No hard boundary/i)).toBeInTheDocument();
  expect(screen.getByText(/E2B_ENABLED \+ E2B_API_KEY/i)).toBeInTheDocument();
});

test('an e2b backend is shown as micro-VM isolation', async () => {
  mockAll();
  render(<GovernanceScreen />);
  await waitFor(() => expect(screen.getByText(/E2B micro-VM/i)).toBeInTheDocument());
});

test('auto-approve being on is surfaced as a warning', async () => {
  mockAll({ status: { ...OBSERVE_STATUS, auto_approve: true } });
  render(<GovernanceScreen />);
  await waitFor(() => expect(screen.getByText(/auto-approve ON/i)).toBeInTheDocument());
});

test('audit rows show the verdict, the agent, and the rule that fired', async () => {
  mockAll({
    events: [{
      event_id: 'evt_1', decision: 'deny', agent_id: 'agent:research-bot',
      display_name: 'Research Bot', policy_group: 'research', surface: 'filesystem',
      action: '.env', tool: 'read_file', rule_id: 'baseline.filesystem.deny[.env]',
      reason: 'blocked by organization baseline rule', timestamp: new Date().toISOString(),
    }],
  });
  render(<GovernanceScreen />);
  await waitFor(() => expect(screen.getByText('Research Bot')).toBeInTheDocument());
  expect(screen.getByText('deny')).toBeInTheDocument();
  // The rule id is what makes a denial reviewable rather than mysterious.
  expect(screen.getByText('baseline.filesystem.deny[.env]')).toBeInTheDocument();
});

test('pending approvals render and approving calls the approve endpoint', async () => {
  api.approveGovernanceRequest.mockResolvedValue({ data: {} });
  mockAll({
    approvals: [{
      approval_id: 'apr_1', agent_id: 'agent:coder', action: 'github_merge_pr',
      reason: 'organization baseline requires human approval',
      rule_id: 'baseline.tool.require_approval[github_merge_pr]',
      seconds_remaining: 240,
    }],
  });
  render(<GovernanceScreen />);
  await waitFor(() => expect(screen.getByText(/Awaiting your decision/i)).toBeInTheDocument());
  expect(screen.getByText('github_merge_pr')).toBeInTheDocument();

  fireEvent.click(screen.getByText('Approve'));
  await waitFor(() => expect(api.approveGovernanceRequest).toHaveBeenCalledWith('apr_1'));
  expect(api.denyGovernanceRequest).not.toHaveBeenCalled();
});

test('denying an approval calls the deny endpoint', async () => {
  api.denyGovernanceRequest.mockResolvedValue({ data: {} });
  mockAll({
    approvals: [{
      approval_id: 'apr_2', agent_id: 'agent:coder', action: 'deploy_prod',
      reason: 'requires approval', rule_id: 'baseline.tool.require_approval[deploy_*]',
      seconds_remaining: 100,
    }],
  });
  render(<GovernanceScreen />);
  await waitFor(() => expect(screen.getByText('Deny')).toBeInTheDocument());
  fireEvent.click(screen.getByText('Deny'));
  await waitFor(() => expect(api.denyGovernanceRequest).toHaveBeenCalledWith('apr_2'));
});

test('one failing endpoint does not blank the screen', async () => {
  // The sandbox probe can be slow or fail on its own; the audit trail is
  // independent and must still render.
  mockAll({ events: [{
    event_id: 'evt_9', decision: 'allow', agent_id: 'agent:x', display_name: 'X',
    policy_group: 'default', surface: 'tool', action: 'read_file',
    rule_id: 'group.default.tool.default-allow', timestamp: new Date().toISOString(),
  }] });
  api.getGovernanceMetrics.mockRejectedValue(new Error('metrics down'));
  render(<GovernanceScreen />);
  await waitFor(() => expect(screen.getByText('X')).toBeInTheDocument());
  expect(screen.getByText('OBSERVE')).toBeInTheDocument();
});

test('a 403 renders a readable message instead of crashing', async () => {
  mockAll();
  api.getGovernanceStatus.mockRejectedValue({ response: { status: 403 } });
  render(<GovernanceScreen />);
  await waitFor(() =>
    expect(screen.getByText(/Admin access required/i)).toBeInTheDocument()
  );
});

test('an empty audit trail explains itself rather than looking broken', async () => {
  mockAll();
  render(<GovernanceScreen />);
  await waitFor(() =>
    expect(screen.getByText(/No decisions recorded yet/i)).toBeInTheDocument()
  );
});

test('filtering to denied re-queries the audit endpoint with that decision', async () => {
  mockAll();
  render(<GovernanceScreen />);
  await waitFor(() => expect(screen.getByText('Denied')).toBeInTheDocument());
  fireEvent.click(screen.getByText('Denied'));
  await waitFor(() =>
    expect(api.getGovernanceAudit).toHaveBeenCalledWith(
      expect.objectContaining({ decision: 'deny' })
    )
  );
});
