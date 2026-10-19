/**
 * OnboardingScreen tailored questions.
 *
 * The Tailor step used to render a hardcoded question set per site type, so a
 * dental clinic and a law firm on the same stack got identical questions, and
 * the priorities collected in the Details step never reached them. It now asks
 * the backend for questions built from the company's website, its stack and the
 * ranked priorities, and only falls back to the hardcoded set when that fails.
 */
import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

vi.mock('../api', () => ({
  getSetupState: vi.fn(),
  getOnboardingProgress: vi.fn(),
  generateOnboardingQuestions: vi.fn(),
  submitOnboardingAnswers: vi.fn(),
}));

import * as api from '../api';
import OnboardingScreen from '../v5/screens/OnboardingScreen';
import { COMPANY_ID_KEY } from '../v5/screens/CompanyScreen';

const PRIORITIES = ['Fill more appointment slots', 'Answer patient enquiries faster'];

function resumeAtQuestionsStep() {
  localStorage.setItem(COMPANY_ID_KEY, 'co_1');
  localStorage.setItem('v5_company_domain', 'brightsmile.example');
  localStorage.setItem('v5_onboarding_details', JSON.stringify({ goals: PRIORITIES }));
  api.getOnboardingProgress.mockResolvedValue({ data: { status: 'in_progress', completed_steps: 4 } });
}

describe('OnboardingScreen tailored questions', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    try { localStorage.clear(); } catch { /* noop */ }
  });

  test('sends the ranked priorities and renders the questions and understanding it gets back', async () => {
    resumeAtQuestionsStep();
    api.generateOnboardingQuestions.mockResolvedValue({ data: {
      source: 'ai',
      priorities: PRIORITIES,
      understanding: { industry: 'Dental care', summary: 'A family dentist in Leeds.' },
      profile: { read: true, name: 'Bright Smile Dental' },
      questions: [
        { id: 'empty_slots', label: 'Which weekdays have the most empty chairs?', type: 'freeform', priority_ref: 1, why: 'Priority 1 is filling slots' },
      ],
    } });

    render(<OnboardingScreen onComplete={() => {}} isAdmin={true} />);

    expect(await screen.findByText('Which weekdays have the most empty chairs?')).toBeInTheDocument();
    expect(screen.getByText('Priority 1')).toBeInTheDocument();
    expect(screen.getByText('A family dentist in Leeds.')).toBeInTheDocument();
    expect(screen.getByText(/Detected: Dental care/)).toBeInTheDocument();
    expect(screen.getByText('Answer patient enquiries faster')).toBeInTheDocument();
    expect(api.generateOnboardingQuestions).toHaveBeenCalledWith('co_1', expect.objectContaining({
      domain: 'brightsmile.example',
      priorities: PRIORITIES,
    }));
  });

  test('falls back to the built-in questions when the backend call fails', async () => {
    resumeAtQuestionsStep();
    api.generateOnboardingQuestions.mockRejectedValue(new Error('timeout of 60000ms exceeded'));

    render(<OnboardingScreen onComplete={() => {}} isAdmin={true} />);

    expect(await screen.findByText(/could not tailor questions right now/i)).toBeInTheDocument();
    expect(screen.getByText('How many people work at the company?')).toBeInTheDocument();
    expect(screen.queryByText(/engineering team/i)).not.toBeInTheDocument();
    await waitFor(() => expect(api.generateOnboardingQuestions).toHaveBeenCalledTimes(1));
  });

  test('the Details step sends the goals it saves as the ranked priorities', async () => {
    localStorage.setItem(COMPANY_ID_KEY, 'co_1');
    api.getOnboardingProgress.mockResolvedValue({ data: { status: 'in_progress', completed_steps: 3 } });
    api.submitOnboardingAnswers.mockResolvedValue({ data: {} });
    api.generateOnboardingQuestions.mockReturnValue(new Promise(() => {}));

    render(<OnboardingScreen onComplete={() => {}} isAdmin={true} />);

    const goal = await screen.findByPlaceholderText(/Priority 1:/);
    fireEvent.change(goal, { target: { value: 'Fill more appointment slots' } });
    fireEvent.click(screen.getByText('Continue →'));

    await waitFor(() => expect(api.submitOnboardingAnswers).toHaveBeenCalledWith('co_1', {
      answers: { goals: ['Fill more appointment slots'] },
      priorities: ['Fill more appointment slots'],
    }));
  });
});
