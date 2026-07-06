/**
 * DoctorScreen runtime health panel — N2 acceptance test.
 *
 * Verifies the Doctor screen surfaces runtime health from GET /runtimes/health,
 * showing online/offline badges + version per runtime. The screen must:
 *  - render Hermes as "online" with its version when health reports available=true
 *  - render an offline runtime with its error hint
 *  - never crash when the runtime-health fetch fails (degrades to a warning,
 *    the rest of the screen still renders)
 *  - never crash when the runtime-health list is empty
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

// Stub the useSafeData hook so we control both /api/doctor/diagnostics and
// /runtimes/health responses without spinning up a real backend. The Doctor
// screen destructures [data, states, reload] from this hook.
jest.mock('../v5/hooks/useSafeData', () => ({
  useSafeData: jest.fn(),
}));

// Stub the API base — DoctorScreen reads it at module-eval time, but it never
// makes a real fetch because useSafeData is mocked.
jest.mock('../api', () => ({
  API: { get: jest.fn() },
}));

import { useSafeData } from '../v5/hooks/useSafeData';
import { DoctorScreen } from '../v5/screens/DoctorScreen';

function setHookData({ report = null, runtimes = null, reportError = null, runtimesError = null, loading = false }) {
  useSafeData.mockReturnValue([
    {
      report,
      runtimes: runtimes === null ? null : { health: runtimes },
    },
    {
      report: { loading, error: reportError },
      runtimes: { loading, error: runtimesError },
    },
    jest.fn(),  // reload
  ]);
}

describe('DoctorScreen runtime health panel (N2)', () => {
  beforeEach(() => {
    useSafeData.mockReset();
  });

  test('shows Hermes online with version when health reports available', async () => {
    setHookData({
      report: { ready: true, summary: 'healthy', checks: [], run_at: '2026-06-27T07:00:00Z' },
      runtimes: [
        { runtime_id: 'hermes', available: true, version: '0.4.2', latency_ms: 12 },
        { runtime_id: 'internal_agent', available: true, version: null, latency_ms: 3 },
      ],
    });

    render(<DoctorScreen onNavigate={() => {}} />);

    expect(screen.getByText('Hermes Agent')).toBeInTheDocument();
    // Both runtimes are online, so there are two "online" badges.
    expect(screen.getAllByText('online')).toHaveLength(2);
    expect(screen.getByText('v0.4.2')).toBeInTheDocument();
    expect(screen.getByText('Internal Agent')).toBeInTheDocument();
  });

  test('shows offline runtime with error hint when not available', async () => {
    setHookData({
      report: { ready: true, summary: 'healthy', checks: [], run_at: '2026-06-27T07:00:00Z' },
      runtimes: [
        {
          runtime_id: 'hermes',
          available: false,
          version: null,
          error: 'Hermes sidecar not running at http://localhost:8100.',
        },
      ],
    });

    render(<DoctorScreen onNavigate={() => {}} />);

    expect(screen.getByText('Hermes Agent')).toBeInTheDocument();
    expect(screen.getByText('offline')).toBeInTheDocument();
    // The error hint is rendered as a clipped span with the message in its title attr.
    const hint = screen.getByTitle(/Hermes sidecar not running/);
    expect(hint).toBeInTheDocument();
  });

  test('never crashes when runtime health fetch fails — shows a warning instead', async () => {
    setHookData({
      report: { ready: true, summary: 'healthy', checks: [], run_at: '2026-06-27T07:00:00Z' },
      runtimes: [],
      runtimesError: '503 Service Unavailable',
    });

    render(<DoctorScreen onNavigate={() => {}} />);

    // The Doctor title and report summary still render.
    expect(screen.getByRole('heading', { name: /Doctor/i })).toBeInTheDocument();
    expect(screen.getByText(/healthy/)).toBeInTheDocument();
    // The runtime health fetch failure shows an inline warning, not a crash.
    expect(screen.getByText(/Couldn't load runtime health/i)).toBeInTheDocument();
    expect(screen.getByText(/503 Service Unavailable/i)).toBeInTheDocument();
  });

  test('shows a helpful hint when no runtimes are registered', async () => {
    setHookData({
      report: { ready: true, summary: 'healthy', checks: [], run_at: '2026-06-27T07:00:00Z' },
      runtimes: [],
    });

    render(<DoctorScreen onNavigate={() => {}} />);

    expect(screen.getByText(/No runtimes registered/i)).toBeInTheDocument();
    expect(screen.getByText(/RUNTIME_HERMES_ENABLED=true/i)).toBeInTheDocument();
  });
});
