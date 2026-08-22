import React from 'react';
import HubTabs from '../components/ui/HubTabs';
import Spinner from '../components/ui/Spinner';

const CompanyScreen = React.lazy(() => import('./CompanyScreen'));
const AgentsScreen = React.lazy(() => import('./AgentsScreen'));
const KnowledgeScreen = React.lazy(() => import('./KnowledgeScreen'));
const OnboardingScreen = React.lazy(() => import('./OnboardingScreen'));

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'team', label: 'Your team' },
  { id: 'knowledge', label: 'Knowledge' },
  { id: 'setup', label: 'Setup' },
];

/**
 * CompanyHub — one company context.
 *
 * Absorbs the former Company, Agents, Knowledge and Onboarding nav items:
 * the same business, its systems, its specialist team and its knowledge were
 * spread over four destinations (with the company selector and graph
 * duplicated between them). Setup is a tab here, not a permanent nav entry.
 */
export default function CompanyHub({ initialTab, onNavigate, isAdmin }) {
  const [tab, setTab] = React.useState(TABS.some(t => t.id === initialTab) ? initialTab : 'overview');
  return (
    <div>
      <HubTabs tabs={TABS} active={tab} onChange={setTab} />
      <React.Suspense fallback={<Spinner center />}>
        {tab === 'overview' && <CompanyScreen />}
        {tab === 'team' && (
          <AgentsScreen
            onNavigateToChat={() => onNavigate('assistant')}
            onNavigateToTasks={() => onNavigate('work')}
          />
        )}
        {tab === 'knowledge' && <KnowledgeScreen />}
        {tab === 'setup' && <OnboardingScreen onComplete={() => setTab('overview')} isAdmin={isAdmin} />}
      </React.Suspense>
    </div>
  );
}
