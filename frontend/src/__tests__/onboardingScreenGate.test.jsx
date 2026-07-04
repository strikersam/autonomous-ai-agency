/**
 * OnboardingScreen non-admin access gate.
 *
 * Regression test: when an admin turns the global onboarding gate OFF (or
 * allow-lists a specific user) via PUT /api/activation/settings, non-admin
 * (social-login) users must be able to run the setup wizard. Previously the
 * screen blocked every non-admin unconditionally (`if (!isAdmin) return
 * <NonAdminGate/>`), ignoring the backend's resolved
 * `_activation.onboarding_allowed` flag from GET /api/setup/state entirely.
 */
import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';

jest.mock('../api', () => ({
  getSetupState: jest.fn(),
  getOnboardingProgress: jest.fn(),
}));

import * as api from '../api';
import OnboardingScreen from '../v5/screens/OnboardingScreen';

describe('OnboardingScreen access gate for non-admin users', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    try { localStorage.clear(); } catch { /* noop */ }
  });

  test('admins skip the access check entirely and see the wizard', async () => {
    render(<OnboardingScreen onComplete={() => {}} isAdmin={true} />);

    expect(await screen.findByText(/Enter your production URL/i)).toBeInTheDocument();
    expect(api.getSetupState).not.toHaveBeenCalled();
  });

  test('non-admin user is allowed in once the onboarding gate is off', async () => {
    api.getSetupState.mockResolvedValue({ data: { _activation: { onboarding_allowed: true } } });

    render(<OnboardingScreen onComplete={() => {}} isAdmin={false} />);

    expect(await screen.findByText(/Enter your production URL/i)).toBeInTheDocument();
    expect(screen.queryByText(/Admin setup required/i)).not.toBeInTheDocument();
  });

  test('non-admin user is still blocked when onboarding is not allowed', async () => {
    api.getSetupState.mockResolvedValue({ data: { _activation: { onboarding_allowed: false } } });

    render(<OnboardingScreen onComplete={() => {}} isAdmin={false} />);

    expect(await screen.findByText(/Admin setup required/i)).toBeInTheDocument();
    expect(screen.queryByText(/Enter your production URL/i)).not.toBeInTheDocument();
  });

  test('non-admin user is blocked (fail closed) when the access check errors', async () => {
    api.getSetupState.mockRejectedValue(new Error('network error'));

    render(<OnboardingScreen onComplete={() => {}} isAdmin={false} />);

    expect(await screen.findByText(/Admin setup required/i)).toBeInTheDocument();
  });
});
