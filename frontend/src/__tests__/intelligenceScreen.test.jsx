/**
 * IntelligenceScreen — competitor + trend-keyword persistence.
 *
 * Regressions pinned: adding a competitor never reached the backend, the
 * keyword tab started empty, and sync failures were swallowed silently.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import IntelligenceScreen from '../v5/screens/IntelligenceScreen';

jest.mock('../api', () => ({
  fmtErr: (d) => (typeof d === 'string' ? d : ''),
  chatSend: jest.fn(),
  getCompany: jest.fn(),
  updateCompany: jest.fn(),
}));
jest.mock('../v5/screens/CompanyScreen', () => ({ COMPANY_ID_KEY: 'company_id_test' }));

const api = require('../api');

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('company_id_test', 'co-1');
  api.getCompany.mockResolvedValue({ data: { company: { name: 'Acme', intelligence_competitors: [], intelligence_keywords: [] } } });
  api.updateCompany.mockReset();
});

test('trend keywords tab is seeded when nothing is stored', async () => {
  render(<IntelligenceScreen />);
  fireEvent.click(screen.getByText(/Trend Keywords/));
  expect(await screen.findByText('AI shopping assistants')).toBeInTheDocument();
});

test('adding a competitor persists it to the company', async () => {
  api.updateCompany.mockResolvedValue({});
  render(<IntelligenceScreen />);
  fireEvent.click(screen.getByText(/Competitors/));
  fireEvent.click(screen.getByText('+ Add competitor'));
  fireEvent.change(screen.getByPlaceholderText('Company name'), { target: { value: 'Rival' } });
  fireEvent.change(screen.getByPlaceholderText(/Website URL/), { target: { value: 'rival.com' } });
  fireEvent.click(screen.getByText('Add'));
  await waitFor(() => expect(api.updateCompany).toHaveBeenCalled());
  const [id, body] = api.updateCompany.mock.calls[0];
  expect(id).toBe('co-1');
  expect(body.intelligence_competitors[0]).toMatchObject({ name: 'Rival', url: 'rival.com' });
  expect(await screen.findByRole('link', { name: 'rival.com' })).toHaveAttribute('href', 'https://rival.com/');
});

test('a failed sync is surfaced, not swallowed', async () => {
  api.updateCompany.mockRejectedValue(new Error('boom'));
  render(<IntelligenceScreen />);
  fireEvent.click(screen.getByText(/Trend Keywords/));
  fireEvent.change(screen.getByPlaceholderText(/TikTok/), { target: { value: 'new kw' } });
  fireEvent.click(screen.getByText('+ Add'));
  expect(await screen.findByText(/could not sync/)).toBeInTheDocument();
});

test('briefing request is bounded and a timeout shows an error', async () => {
  api.chatSend.mockRejectedValue(Object.assign(new Error('timeout of 95000ms exceeded'), { code: 'ECONNABORTED' }));
  render(<IntelligenceScreen />);
  fireEvent.click(screen.getByRole('button', { name: /Run analysis/ }));
  expect(await screen.findByText(/took too long/)).toBeInTheDocument();
  const cfg = api.chatSend.mock.calls[0][10];
  expect(cfg.timeout).toBeGreaterThan(0);
  expect(cfg.timeout).toBeLessThan(100000);
});
