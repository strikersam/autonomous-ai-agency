import React from 'react';
import { useReportSub } from '../screenContext';
import HubTabs from '../components/ui/HubTabs';
import Spinner from '../components/ui/Spinner';
import { ErrorBoundary } from '../components/ErrorBoundary';

const TaskBoardScreen = React.lazy(() => import('./TaskBoardScreen'));
const SchedulesScreen = React.lazy(() => import('./SchedulesScreen'));
const PortfolioScreen = React.lazy(() => import('./PortfolioScreen'));
const WorkflowScreen = React.lazy(() => import('./WorkflowScreen'));

const TABS = [
  { id: 'now', label: 'Happening now' },
  { id: 'autopilot', label: 'On autopilot' },
  { id: 'roadmap', label: 'Planned' },
  { id: 'workflows', label: 'Workflows', adminOnly: true },
];

/**
 * WorkHub — everything the agency is doing, in one destination.
 * Absorbs the former Tasks, Schedules and Portfolio nav items.
 */
export default function WorkHub({ initialTab, isAdmin }) {
  // /api/workflow/* is admin-only, so non-admins don't get the tab.
  const tabs = TABS.filter(t => !t.adminOnly || isAdmin);
  const [tab, setTab] = React.useState(tabs.some(t => t.id === initialTab) ? initialTab : 'now');
  useReportSub('work', tab);
  return (
    <div>
      <HubTabs tabs={tabs} active={tab} onChange={setTab} />
      <ErrorBoundary resetKey={tab}>
      <React.Suspense fallback={<Spinner center />}>
        {tab === 'now' && <TaskBoardScreen />}
        {tab === 'autopilot' && <SchedulesScreen />}
        {tab === 'roadmap' && <PortfolioScreen />}
        {tab === 'workflows' && <WorkflowScreen />}
      </React.Suspense>
      </ErrorBoundary>
    </div>
  );
}
