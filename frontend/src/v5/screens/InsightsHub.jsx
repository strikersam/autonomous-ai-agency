import React from 'react';
import HubTabs from '../components/ui/HubTabs';
import Spinner from '../components/ui/Spinner';

const LogsScreen = React.lazy(() => import('./LogsScreen'));
const IntelligenceScreen = React.lazy(() => import('./IntelligenceScreen'));

const TABS = [
  { id: 'activity', label: 'Activity' },
  { id: 'market', label: 'Your market' },
];

/**
 * InsightsHub — results and history in one destination.
 * Absorbs the former Logs and Intelligence nav items.
 */
export default function InsightsHub({ initialTab, onNavigate }) {
  const [tab, setTab] = React.useState(TABS.some(t => t.id === initialTab) ? initialTab : 'activity');
  return (
    <div>
      <HubTabs tabs={TABS} active={tab} onChange={setTab} />
      <React.Suspense fallback={<Spinner center />}>
        {tab === 'activity' && <LogsScreen />}
        {tab === 'market' && <IntelligenceScreen onNavigate={onNavigate} />}
      </React.Suspense>
    </div>
  );
}
