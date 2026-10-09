import React from 'react';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import App from '../App';

vi.mock('../pages/AuthCallback', () => ({ default: () => <div>Auth callback</div> }));
vi.mock('../pages/SetupWizardPage', () => ({ default: () => <div>Setup wizard</div> }));
vi.mock('../v5/V5App', () => ({ default: () => <div>V5 shell</div> }));

vi.mock('../AuthContext', () => ({
  AuthProvider: ({ children }) => <>{children}</>,
  useAuth: () => ({
    user: false,
    loading: false,
    login: vi.fn(),
    logout: vi.fn(),
    checkAuth: vi.fn(),
  }),
}));

vi.mock('../api', async () => {
  const actual = await vi.importActual('../api');
  return {
    ...actual,
    getBackendUrl: vi.fn(() => ''),
    getSetupState: vi.fn(() => Promise.resolve({ data: { completed: false } })),
  };
});

describe('GitHub Pages app routing', () => {
  test('unknown deep link falls back to the login page without crashing', async () => {
    render(
      <MemoryRouter basename="/local-llm-server" initialEntries={['/local-llm-server/workspace-mobile']}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByTestId('login-page')).toBeInTheDocument();
    expect(screen.getByText(/need to connect a backend first/i)).toBeInTheDocument();
  });
});
