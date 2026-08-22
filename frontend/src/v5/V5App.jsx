import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { AppShell } from './AppShell';
// The assistant is the eager path: AssistantHub imports ChatScreen eagerly so
// the common case paints in one round trip. Everything else is code-split.
import AlertsBell from './screens/AlertsBell';
import QuickNotesFAB from './screens/QuickNotesFAB';
import ActivationGate from './screens/ActivationGate';
import AssistantHub from './screens/AssistantHub';
import Spinner from './components/ui/Spinner';
const DashboardScreen = React.lazy(() => import('./screens/DashboardScreen'));
const WorkHub = React.lazy(() => import('./screens/WorkHub'));
const CompanyHub = React.lazy(() => import('./screens/CompanyHub'));
const InsightsHub = React.lazy(() => import('./screens/InsightsHub'));
const SettingsHub = React.lazy(() => import('./screens/SettingsHub'));

/* Structural styles only. All design tokens (colors, fonts, radii) come from
   the single :root block in index.css — this used to redeclare them, and the
   two copies drifted. */
const V5_THEME = `
.v5-root {
  position:fixed; inset:0; z-index:1000;
  background:radial-gradient(circle at top, rgba(93,162,255,0.10), transparent 30%), linear-gradient(180deg,#050608 0%,#020304 100%);
  color:var(--text-primary); font-family:var(--font-main); font-size:16px;
  overflow:hidden; -webkit-font-smoothing:antialiased;
}
.v5-root *, .v5-root *::before, .v5-root *::after { box-sizing:border-box; margin:0; padding:0; }
.v5-root button { touch-action:manipulation; font-family:inherit; }
.v5-root a { color:var(--accent); }
.v5-root .scrollbar-hide { -ms-overflow-style:none; scrollbar-width:none; }
.v5-root .scrollbar-hide::-webkit-scrollbar { display:none; }
.v5-root ::-webkit-scrollbar { width:5px; height:5px; }
.v5-root ::-webkit-scrollbar-track { background:transparent; }
.v5-root ::-webkit-scrollbar-thumb { background:rgba(255,255,255,0.12); border-radius:999px; }
`;

/**
 * Six destinations, organised around what the user is doing — not around the
 * backend. The 14 former top-level screens live on as tabs/sections inside
 * these hubs (see ALIASES), so every old deep link and every old `go(id)`
 * call from inside a screen still lands somewhere sensible.
 */
const V5_SCREENS = ['home', 'assistant', 'work', 'company', 'insights', 'settings'];

// old screen id -> new destination (+ the tab/section inside it)
const ALIASES = {
  chat: { screen: 'assistant' },
  sam: { screen: 'assistant', sub: 'voice' },
  dashboard: { screen: 'home' },
  tasks: { screen: 'work', sub: 'now' },
  schedules: { screen: 'work', sub: 'autopilot' },
  portfolio: { screen: 'work', sub: 'roadmap' },
  agents: { screen: 'company', sub: 'team' },
  knowledge: { screen: 'company', sub: 'knowledge' },
  onboarding: { screen: 'company', sub: 'setup' },
  logs: { screen: 'insights', sub: 'activity' },
  intelligence: { screen: 'insights', sub: 'market' },
  providers: { screen: 'settings', sub: 'providers' },
  controls: { screen: 'settings', sub: 'controls' },
  governance: { screen: 'settings', sub: 'governance' },
  admin: { screen: 'settings', sub: 'admin' },
  doctor: { screen: 'settings', sub: 'doctor' },
  github: { screen: 'settings', sub: 'github' },
  loops: { screen: 'settings', sub: 'loops' },
  skills: { screen: 'settings', sub: 'skills' },
};

// Any id — new, old, or garbage — resolves to a destination. Never throws.
function resolveTarget(id) {
  if (V5_SCREENS.includes(id)) return { screen: id };
  return ALIASES[id] || { screen: 'home' };
}

function segFromPath(pathname) {
  return (pathname.split('/')[2] || '').toLowerCase();
}

function ScreenLoading() {
  return <Spinner center />;
}

export default function V5App() {
  const location = useLocation();
  const navigate = useNavigate();
  // {screen, sub}: sub is the tab/section a hub should open on. It is only
  // set by navigation (aliases like /v5/controls), never synthesised, so a
  // plain visit to a hub keeps the hub's own default.
  const [current, setCurrent] = React.useState(() => resolveTarget(segFromPath(location.pathname) || 'home'));
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const agentRunning = true;

  const go = React.useCallback((id) => {
    const t = resolveTarget(id);
    setCurrent(t);
    navigate(`/v5/${t.screen === 'home' ? '' : t.screen}`, { replace: false });
  }, [navigate]);

  // Back/forward and external URL changes keep the screen in sync. Old ids
  // (/v5/chat, /v5/controls, …) are canonicalised to their new destination so
  // state and URL never disagree.
  React.useEffect(() => {
    const seg = segFromPath(location.pathname);
    if (seg === '' || V5_SCREENS.includes(seg)) {
      const screen = seg === '' ? 'home' : seg;
      setCurrent(c => (c.screen === screen ? c : { screen }));
    } else {
      const t = resolveTarget(seg);
      setCurrent(t);
      navigate(`/v5/${t.screen === 'home' ? '' : t.screen}`, { replace: true });
    }
  }, [location.pathname, navigate]);

  const screens = {
    home: <DashboardScreen dashboardState="healthy" />,
    assistant: <AssistantHub initialMode={current.sub === 'voice' ? 'voice' : 'chat'} />,
    work: <WorkHub initialTab={current.sub} />,
    company: <CompanyHub initialTab={current.sub} onNavigate={go} isAdmin={isAdmin} />,
    insights: <InsightsHub initialTab={current.sub} onNavigate={go} />,
    // People & access / controls / governance are gated per-section inside
    // the hub; a non-admin still reaches the open sections (Doctor, GitHub,
    // Loops, Skills). A direct link to an admin-only section falls back to
    // the first open section for them.
    settings: <SettingsHub initialSection={current.sub} isAdmin={isAdmin} onNavigate={go} />,
  };

  return (
    <ActivationGate>
      <div className="v5-root">
        <style>{V5_THEME}</style>
        <AppShell activeScreen={current.screen} onNavigate={go} agentRunning={agentRunning} isAdmin={isAdmin}>
          <React.Suspense fallback={<ScreenLoading />}>
            {/* keyed on the sub-target so /v5/schedules → Work opens the
                right tab even when Work is already mounted */}
            <div key={`${current.screen}:${current.sub || ''}`} style={{ height: '100%', minHeight: 0 }}>
              {screens[current.screen] || screens.home}
            </div>
          </React.Suspense>
        </AppShell>
        <AlertsBell onNavigate={go} />
        <QuickNotesFAB visible={true} />
      </div>
    </ActivationGate>
  );
}

export { ALIASES, V5_SCREENS };
