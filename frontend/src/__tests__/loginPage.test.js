import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from '../pages/LoginPage';

const mockLogin = jest.fn();
const mockGetBackendUrl = jest.fn();

jest.mock('../AuthContext', () => ({
  useAuth: () => ({ login: mockLogin }),
}));

jest.mock('../api', () => ({
  fmtErr: (value) => value?.message || String(value),
  getBackendUrl: () => mockGetBackendUrl(),
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  );
}

afterEach(() => {
  jest.clearAllMocks();
});

test('keeps GitHub and Google social login buttons wired to the configured backend', () => {
  mockGetBackendUrl.mockReturnValue('https://relay.example.com');

  renderPage();

  const githubLink = screen.getByText('GitHub').closest('a');
  const googleLink = screen.getByText('Google').closest('a');

  // Uses /api/auth/<provider>/start (not /login) to bypass the Cloudflare
  // CDN cache that served stale SPA HTML at the /login path.
  expect(githubLink.getAttribute('href')).toMatch(/\/api\/auth\/github\/start\/[a-z0-9]+$/);
  expect(googleLink.getAttribute('href')).toMatch(/\/api\/auth\/google\/start\/[a-z0-9]+$/);
  expect(githubLink).toHaveAttribute('aria-disabled', 'false');
  expect(googleLink).toHaveAttribute('aria-disabled', 'false');
});

test('shows disabled social login actions when no backend is configured', () => {
  mockGetBackendUrl.mockReturnValue('');

  renderPage();

  const githubLink = screen.getByText('GitHub').closest('a');
  const googleLink = screen.getByText('Google').closest('a');

  expect(githubLink).not.toHaveAttribute('href');
  expect(googleLink).not.toHaveAttribute('href');
  expect(githubLink).toHaveAttribute('aria-disabled', 'true');
  expect(googleLink).toHaveAttribute('aria-disabled', 'true');
});

test('hides the email/password form behind an "Admin sign-in" toggle by default', () => {
  mockGetBackendUrl.mockReturnValue('https://relay.example.com');

  renderPage();

  // Social login is the default, prominent path for general users.
  expect(screen.getByText('GitHub')).toBeInTheDocument();
  expect(screen.getByText('Google')).toBeInTheDocument();

  // Password sign-in (admin / admin-created users only) is collapsed by default.
  expect(screen.queryByTestId('email-input')).not.toBeInTheDocument();
  expect(screen.queryByTestId('password-input')).not.toBeInTheDocument();

  fireEvent.click(screen.getByTestId('toggle-admin-login'));

  expect(screen.getByTestId('email-input')).toBeInTheDocument();
  expect(screen.getByTestId('password-input')).toBeInTheDocument();
});
