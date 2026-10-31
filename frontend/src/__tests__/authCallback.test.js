import React from 'react';
import { render, waitFor } from '@testing-library/react';
import AuthCallback from '../pages/AuthCallback';

const mockNavigate = vi.fn();
const mockCheckAuth = vi.fn(() => Promise.resolve());
let mockSearch = '?token=social-jwt&provider=github';

vi.mock('react-router-dom', async () => ({
  ...(await vi.importActual('react-router-dom')),
  useNavigate: () => mockNavigate,
  useLocation: () => ({ search: mockSearch }),
}));

vi.mock('../AuthContext', () => ({
  useAuth: () => ({ checkAuth: mockCheckAuth }),
}));

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  mockNavigate.mockReset();
  mockCheckAuth.mockReset();
  mockCheckAuth.mockResolvedValue(undefined);
});

test('social login callback lands on the root dashboard after auth sync', async () => {
  sessionStorage.setItem('oauth_login_nonce', 'n0nce1');
  mockSearch = '?token=social-jwt&provider=github&nonce=n0nce1';

  render(<AuthCallback />);

  await waitFor(() => expect(mockCheckAuth).toHaveBeenCalled());
  await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true }));
  expect(localStorage.getItem('access_token')).toBe('social-jwt');
  expect(sessionStorage.getItem('access_token')).toBe('social-jwt');
});

test('legacy callback flow also returns to the root dashboard', async () => {
  sessionStorage.setItem('oauth_login_nonce', 'n0nce2');
  mockSearch = '?access_token=legacy-access&refresh_token=legacy-refresh&nonce=n0nce2';

  render(<AuthCallback />);

  await waitFor(() => expect(mockCheckAuth).toHaveBeenCalled());
  await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/', { replace: true }));
  expect(localStorage.getItem('access_token')).toBe('legacy-access');
  expect(localStorage.getItem('refresh_token')).toBe('legacy-refresh');
});

test('tokens from a link this tab did not start are refused (login CSRF)', async () => {
  localStorage.setItem('access_token', 'victim-session');
  mockSearch = '?access_token=attacker-access&refresh_token=attacker-refresh';

  render(<AuthCallback />);

  await waitFor(() => expect(mockNavigate).not.toHaveBeenCalled());
  expect(localStorage.getItem('access_token')).toBe('victim-session');
  expect(localStorage.getItem('refresh_token')).toBeNull();
});

test('a wrong nonce is refused even when one is pending', async () => {
  sessionStorage.setItem('oauth_login_nonce', 'mine');
  mockSearch = '?token=attacker-jwt&provider=github&nonce=theirs';

  render(<AuthCallback />);

  await waitFor(() => expect(mockCheckAuth).not.toHaveBeenCalled());
  expect(localStorage.getItem('access_token')).toBeNull();
});
