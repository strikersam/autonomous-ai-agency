/**
 * Rule 49's proof on a task: the verifier's report is shown (checked / broken /
 * fixed / evidence, screenshots inline), and a person can pass or fail it.
 */
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import VerificationReport from '../v5/components/VerificationReport';

const report = {
  verdict: 'PASS',
  verifier: 'agent:judge',
  checked: ['Step 1 passed the step verifier'],
  defects_found: ['a.py: missing import'],
  fixed: ['a.py: fixed on retry'],
  evidence: ['https://example.com/after.png', 'Commit abc123'],
  notes: '',
};

test('shows what was checked, broken and fixed, with screenshots inline', () => {
  render(<VerificationReport task={{ status: 'done', verification: report }} />);
  expect(screen.getByText('Passed')).toBeInTheDocument();
  expect(screen.getByText('Step 1 passed the step verifier')).toBeInTheDocument();
  expect(screen.getByText('a.py: missing import')).toBeInTheDocument();
  expect(screen.getByText('a.py: fixed on retry')).toBeInTheDocument();
  expect(screen.getByAltText('Verification screenshot')).toHaveAttribute('src', 'https://example.com/after.png');
  expect(screen.getByText('Commit abc123')).toBeInTheDocument();
  expect(screen.getByText(/did not do the work/)).toBeInTheDocument();
});

test('a task waiting in review says nothing has confirmed it yet', () => {
  render(<VerificationReport task={{ status: 'in_review' }} onRecord={() => true} />);
  expect(screen.getByText('Waiting for an independent check')).toBeInTheDocument();
});

test('failing needs a reason and sends the defects', async () => {
  const onRecord = vi.fn(() => Promise.resolve(true));
  render(<VerificationReport task={{ status: 'in_review' }} onRecord={onRecord} />);
  fireEvent.click(screen.getByText('Something is wrong'));
  const send = screen.getByText('Send back for rework');
  expect(send).toBeDisabled();
  fireEvent.change(screen.getByLabelText(/What is wrong/), { target: { value: 'Totals wrong\nButton hidden' } });
  fireEvent.click(send);
  await waitFor(() => expect(onRecord).toHaveBeenCalledWith({ verdict: 'FAIL', defects_found: ['Totals wrong', 'Button hidden'], notes: '' }));
});

test('passing without notes records PASS', async () => {
  const onRecord = vi.fn(() => Promise.resolve(true));
  render(<VerificationReport task={{ status: 'in_review' }} onRecord={onRecord} />);
  fireEvent.click(screen.getByText('It works, pass it'));
  fireEvent.click(screen.getByText('Mark as verified'));
  await waitFor(() => expect(onRecord).toHaveBeenCalledWith(expect.objectContaining({ verdict: 'PASS' })));
});

test('after a FAIL re-opens the task, the failed findings stay visible', () => {
  const log = [{ event_type: 'verification_retired', metadata: { verification: { verdict: 'FAIL', verifier: 'priya@x.com', defects_found: ['Totals wrong'] } } }];
  render(<VerificationReport task={{ status: 'in_progress', execution_log: log }} />);
  expect(screen.getByText(/Last check failed/)).toBeInTheDocument();
  expect(screen.getByText('Totals wrong')).toBeInTheDocument();
});
