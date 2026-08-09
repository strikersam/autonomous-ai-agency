/**
 * PlatformControlsPage — the dashboard screen that replaces editing feature
 * switches in the Render environment.
 *
 * The behaviours worth pinning are the ones an operator would be misled by:
 * the source of each value must be visible, a restart-required change must say
 * so rather than implying it already landed, and Apply must send the pending
 * edits (not the whole catalogue) so an unrelated control is never rewritten.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import PlatformControlsPage from '../pages/PlatformControlsPage';

jest.mock('../api', () => ({
  fmtErr: (d) => (typeof d === 'string' ? d : ''),
  getPlatformControls: jest.fn(),
  setPlatformControls: jest.fn(),
  resetPlatformControl: jest.fn(),
}));

const { getPlatformControls, setPlatformControls, resetPlatformControl } = require('../api');

const secondGroup = {
  id: 'governance',
  label: 'Governance & Safety',
  help: 'Policy evaluation and sandboxing.',
  controls: [
    {
      key: 'GOVERNANCE_ENABLED',
      label: 'Governance layer',
      group: 'governance',
      kind: 'toggle',
      default: 'true',
      help: 'Evaluate and audit agent actions.',
      options: [],
      live: true,
      risk: 'medium',
      requires: [],
      minimum: null,
      maximum: null,
      value: 'true',
      source: 'default',
      env_value: null,
      override_value: null,
      missing_requirements: [],
    },
  ],
};

const snapshot = (overrides = {}) => ({
  control_count: 4,
  override_count: 1,
  groups: [
    {
      id: 'agent_runtime',
      label: 'Agent Runtimes',
      help: 'Which execution backend runs agent work.',
      controls: [
        {
          key: 'RUNTIME_DEFAULT',
          label: 'Default runtime',
          group: 'agent_runtime',
          kind: 'choice',
          default: 'internal_agent',
          help: 'Runtime the router prefers.',
          options: [
            { value: 'internal_agent', label: 'Internal Agent', help: '' },
            { value: 'hermes', label: 'Hermes', help: '' },
          ],
          live: true,
          risk: 'medium',
          requires: [],
          minimum: null,
          maximum: null,
          value: 'internal_agent',
          source: 'environment',
          env_value: 'internal_agent',
          override_value: null,
          missing_requirements: [],
        },
        {
          key: 'RUNTIME_HERMES_ENABLED',
          label: 'Hermes runtime',
          group: 'agent_runtime',
          kind: 'toggle',
          default: 'true',
          help: 'Register the Hermes adapter.',
          options: [],
          live: false,
          risk: 'low',
          requires: [],
          minimum: null,
          maximum: null,
          value: 'true',
          source: 'override',
          env_value: null,
          override_value: 'true',
          missing_requirements: [],
        },
        {
          key: 'RUNTIME_E2B_ENABLED',
          label: 'E2B sandbox runtime',
          group: 'agent_runtime',
          kind: 'toggle',
          default: 'false',
          help: 'Register the E2B adapter.',
          options: [],
          live: false,
          risk: 'low',
          requires: ['E2B_API_KEY'],
          minimum: null,
          maximum: null,
          value: 'false',
          source: 'default',
          env_value: null,
          override_value: null,
          missing_requirements: ['E2B_API_KEY'],
        },
      ],
    },
    secondGroup,
  ],
  ...overrides,
});

beforeEach(() => {
  jest.clearAllMocks();
  getPlatformControls.mockResolvedValue({ data: snapshot() });
});

test('renders each control with where its value came from', async () => {
  render(<PlatformControlsPage />);

  await waitFor(() => expect(screen.getByText('Default runtime')).toBeInTheDocument());
  expect(screen.getByText('Render env')).toBeInTheDocument();
  expect(screen.getByText('Dashboard')).toBeInTheDocument();
  expect(screen.getByText('Code default')).toBeInTheDocument();
});

test('flags controls whose dependency secret is missing', async () => {
  render(<PlatformControlsPage />);

  await waitFor(() => expect(screen.getByText('E2B sandbox runtime')).toBeInTheDocument());
  expect(screen.getByText(/Inactive until E2B_API_KEY is set/)).toBeInTheDocument();
});

test('marks controls that only take effect after a restart', async () => {
  render(<PlatformControlsPage />);

  await waitFor(() => expect(screen.getByText('Hermes runtime')).toBeInTheDocument());
  expect(screen.getAllByText('Restart required').length).toBe(2);
});

test('Apply sends only the edited controls', async () => {
  setPlatformControls.mockResolvedValue({
    data: { ...snapshot(), changed: ['RUNTIME_DEFAULT'], restart_required: [] },
  });
  render(<PlatformControlsPage />);

  await waitFor(() => expect(screen.getByText('Default runtime')).toBeInTheDocument());
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'hermes' } });

  expect(await screen.findByText('1 unsaved change')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', { name: /Apply/ }));

  await waitFor(() => expect(setPlatformControls).toHaveBeenCalledWith({ RUNTIME_DEFAULT: 'hermes' }));
});

test('surfaces the restart notice returned by a save', async () => {
  setPlatformControls.mockResolvedValue({
    data: {
      ...snapshot(),
      changed: ['RUNTIME_HERMES_ENABLED'],
      restart_required: ['RUNTIME_HERMES_ENABLED'],
    },
  });
  render(<PlatformControlsPage />);

  await waitFor(() => expect(screen.getByText('Hermes runtime')).toBeInTheDocument());
  fireEvent.click(screen.getByRole('switch', { name: 'Hermes runtime' }));
  fireEvent.click(await screen.findByRole('button', { name: /Apply/ }));

  expect(await screen.findByText(/restart the backend/)).toBeInTheDocument();
});

test('reset hands a control back to the environment', async () => {
  resetPlatformControl.mockResolvedValue({
    data: { ...snapshot(), changed: [], restart_required: [] },
  });
  render(<PlatformControlsPage />);

  await waitFor(() => expect(screen.getByText('Hermes runtime')).toBeInTheDocument());
  const row = screen.getByTestId('control-RUNTIME_HERMES_ENABLED');
  const resetButton = row.querySelector('button[title*="Drop the dashboard override"]');
  fireEvent.click(resetButton);

  await waitFor(() => expect(resetPlatformControl).toHaveBeenCalledWith('RUNTIME_HERMES_ENABLED'));
});

test('reset is disabled for a control that has no override', async () => {
  render(<PlatformControlsPage />);

  await waitFor(() => expect(screen.getByText('Default runtime')).toBeInTheDocument());
  const row = screen.getByTestId('control-RUNTIME_DEFAULT');
  expect(row.querySelector('button[title*="Drop the dashboard override"]')).toBeDisabled();
});

test('search narrows the catalogue', async () => {
  render(<PlatformControlsPage />);

  await waitFor(() => expect(screen.getByText('Default runtime')).toBeInTheDocument());
  fireEvent.change(screen.getByPlaceholderText('Search settings…'), { target: { value: 'e2b' } });

  expect(screen.getByText('E2B sandbox runtime')).toBeInTheDocument();
  expect(screen.queryByText('Default runtime')).not.toBeInTheDocument();
});


test('groups past the first are collapsed until opened', async () => {
  render(<PlatformControlsPage />);

  await waitFor(() => expect(screen.getByText('Default runtime')).toBeInTheDocument());
  expect(screen.queryByText('Governance layer')).not.toBeInTheDocument();

  fireEvent.click(screen.getByText('Governance & Safety'));
  expect(screen.getByText('Governance layer')).toBeInTheDocument();
});

test('a search hit inside a collapsed group is still shown', async () => {
  render(<PlatformControlsPage />);

  await waitFor(() => expect(screen.getByText('Default runtime')).toBeInTheDocument());
  expect(screen.queryByText('Governance layer')).not.toBeInTheDocument();

  fireEvent.change(screen.getByPlaceholderText('Search settings…'), {
    target: { value: 'governance' },
  });

  expect(screen.getByText('Governance layer')).toBeInTheDocument();
  expect(screen.queryByText('Default runtime')).not.toBeInTheDocument();
});
