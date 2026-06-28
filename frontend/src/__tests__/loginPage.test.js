import React from 'react';
import { render, screen } from '@testing-library/react';
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

  // The href includes a cache-busting ?cb=<timestamp> param to bypass
  // Cloudflare's CDN cache (which can serve stale SPA HTML at /api/auth/*
  // URLs). The backend ignores the query param.
  expect(githubLink.getAttribute('href')).toMatch(/^https:\/\/relay\.example\.com\/api\/auth\/github\/login\?cb=\d+$/);
  expect(googleLink.getAttribute('href')).toMatch(/^https:\/\/relay\.example\.com\/api\/auth\/google\/login\?cb=\d+$/);
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
