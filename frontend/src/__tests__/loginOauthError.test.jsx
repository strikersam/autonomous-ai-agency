/**
 * An unconfigured social provider used to land the user on a raw JSON 503.
 * The backend now redirects to /login?oauth_error=<provider>_not_configured
 * and the login page explains it.
 */
import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

jest.mock('../AuthContext', () => ({ useAuth: () => ({ login: jest.fn() }) }));
jest.mock('../api', () => ({ fmtErr: (d) => d, getBackendUrl: () => '' }));

import LoginPage from '../pages/LoginPage';

afterEach(() => window.history.replaceState({}, '', '/'));

test('shows why GitHub sign-in bounced back', () => {
  window.history.replaceState({}, '', '/login?oauth_error=github_not_configured');
  render(<MemoryRouter><LoginPage /></MemoryRouter>);
  expect(screen.getByRole('alert')).toHaveTextContent("GitHub sign-in isn't set up on this server yet");
});

test('ignores unknown oauth_error values', () => {
  window.history.replaceState({}, '', '/login?oauth_error=<script>');
  render(<MemoryRouter><LoginPage /></MemoryRouter>);
  expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
