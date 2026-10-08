import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from '../pages/LoginPage';

vi.mock('../AuthContext', () => ({
  useAuth: () => ({
    login: vi.fn(),
  }),
}));

vi.mock('../api', () => ({
  fmtErr: vi.fn((value) => value ?? 'Something went wrong.'),
  getBackendUrl: vi.fn(() => ''),
}));

describe('LoginPage', () => {
  test('renders the setup wizard guidance when no backend is configured', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );

    expect(screen.getByText(/need to connect a backend first/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /open the setup wizard/i })).toHaveAttribute('href', '/bootstrap');
  });
});
