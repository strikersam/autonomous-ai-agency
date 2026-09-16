/**
 * ExecutiveAdvisoryScreen — the C-Suite advisory console.
 *
 * Pins the behaviour that matters:
 *  - the personas load and render
 *  - an admin can consult, and the payload carries the question + flags
 *  - the synthesised recommendation, per-executive views, and sources render
 *  - a non-admin cannot consult (the route spends provider budget)
 *  - a failed consult shows a readable error instead of crashing
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

jest.mock('../api', () => ({
  listExecutives: jest.fn(),
  consultExecutives: jest.fn(),
  fmtErr: (d) => (typeof d === 'string' ? d : ''),
}));
// Avoid loading the heavy CompanyScreen; we only need the shared key.
jest.mock('../v5/screens/CompanyScreen', () => ({ COMPANY_ID_KEY: 'v5_company_id' }));

import * as api from '../api';
import ExecutiveAdvisoryScreen from '../v5/screens/ExecutiveAdvisoryScreen';

const EXECS = [
  { role: 'cfo', title: 'Chief Financial Officer', focus: 'money' },
  { role: 'cso', title: 'Chief Strategy Officer', focus: 'strategy' },
];

beforeEach(() => {
  jest.clearAllMocks();
  try { localStorage.clear(); } catch { /* ignore */ }
  api.listExecutives.mockResolvedValue({ data: { executives: EXECS } });
});

test('loads and renders the personas', async () => {
  render(<ExecutiveAdvisoryScreen isAdmin={true} />);
  expect(await screen.findByText('Chief Financial Officer')).toBeInTheDocument();
  expect(screen.getByText('Chief Strategy Officer')).toBeInTheDocument();
});

test('admin consult sends the question and flags, and renders the result', async () => {
  api.consultExecutives.mockResolvedValue({
    data: {
      question: 'raise prices?',
      consulted: ['cfo'],
      opinions: [{ role: 'cfo', title: 'Chief Financial Officer', text: 'Yes, to $49', error: '' }],
      answer: 'Raise to $49 next quarter.',
      grounding: { text: 'x', sources: ['https://src.test'] },
    },
  });
  render(<ExecutiveAdvisoryScreen isAdmin={true} />);
  await screen.findByText('Chief Financial Officer');

  fireEvent.change(screen.getByPlaceholderText(/raise prices/i), {
    target: { value: 'raise prices?' },
  });
  fireEvent.click(screen.getByRole('button', { name: /consult the c-suite/i }));

  await waitFor(() => expect(api.consultExecutives).toHaveBeenCalledTimes(1));
  const payload = api.consultExecutives.mock.calls[0][0];
  expect(payload.question).toBe('raise prices?');
  expect(payload.ground).toBe(true);
  expect(payload.remember).toBe(true);
  expect(payload.roles).toBeUndefined(); // none selected → auto-route

  expect(await screen.findByText('Raise to $49 next quarter.')).toBeInTheDocument();
  expect(screen.getByText('Yes, to $49')).toBeInTheDocument();
  expect(screen.getByText('https://src.test')).toBeInTheDocument();
});

test('selecting a persona scopes the consult to that role', async () => {
  api.consultExecutives.mockResolvedValue({
    data: { question: 'q', consulted: ['cso'], opinions: [], answer: '', grounding: { sources: [] } },
  });
  render(<ExecutiveAdvisoryScreen isAdmin={true} />);
  await screen.findByText('Chief Strategy Officer');

  fireEvent.click(screen.getByRole('button', { name: 'Chief Strategy Officer' }));
  fireEvent.change(screen.getByPlaceholderText(/raise prices/i), { target: { value: 'q' } });
  fireEvent.click(screen.getByRole('button', { name: /consult the c-suite/i }));

  await waitFor(() => expect(api.consultExecutives).toHaveBeenCalledTimes(1));
  expect(api.consultExecutives.mock.calls[0][0].roles).toEqual(['cso']);
});

test('non-admin cannot consult', async () => {
  render(<ExecutiveAdvisoryScreen isAdmin={false} />);
  await screen.findByText('Chief Financial Officer');
  fireEvent.change(screen.getByPlaceholderText(/raise prices/i), { target: { value: 'q' } });
  const btn = screen.getByRole('button', { name: /consult the c-suite/i });
  expect(btn).toBeDisabled();
  expect(screen.getByText(/requires an admin account/i)).toBeInTheDocument();
});

test('a failed consult shows a readable error', async () => {
  api.consultExecutives.mockRejectedValue({ response: { data: { detail: 'Advisory failed' } } });
  render(<ExecutiveAdvisoryScreen isAdmin={true} />);
  await screen.findByText('Chief Financial Officer');
  fireEvent.change(screen.getByPlaceholderText(/raise prices/i), { target: { value: 'q' } });
  fireEvent.click(screen.getByRole('button', { name: /consult the c-suite/i }));
  expect(await screen.findByText('Advisory failed')).toBeInTheDocument();
});
