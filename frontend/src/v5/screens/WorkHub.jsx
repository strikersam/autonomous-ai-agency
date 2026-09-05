import React from 'react';
import HubTabs from '../components/ui/HubTabs';
import Spinner from '../components/ui/Spinner';

const TaskBoardScreen = React.lazy(() => import('./TaskBoardScreen'));
const SchedulesScreen = React.lazy(() => import('./SchedulesScreen'));
const PortfolioScreen = React.lazy(() => import('./PortfolioScreen'));
const WorkflowScreen = React.lazy(() => import('./WorkflowScreen'));

const TABS = [
  { id: 'now', label: 'Happening now' },
  { id: 'autopilot', label: 'On autopilot' },
  { id: 'roadmap', label: 'Planned' },
  { id: 'workflows', label: 'Workflows' },
];

/**
 * WorkHub — everything the agency is doing, in one destination.
 * Absorbs the former Tasks, Schedules and Portfolio nav items.
 */
export default function WorkHub({ initialTab }) {
  const [tab, setTab] = React.useState(TABS.some(t => t.id === initialTab) ? initialTab : 'now');
  return (
    <div>
      <HubTabs tabs={TABS} active={tab} onChange={setTab} />
      <React.Suspense fallback={<Spinner center />}>
        {tab === 'now' && <TaskBoardScreen />}
        {tab === 'autopilot' && <SchedulesScreen />}
        {tab === 'roadmap' && <PortfolioScreen />}
        {tab === 'workflows' && <WorkflowScreen />}
      </React.Suspense>
    </div>
  );
}
