import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../AuthContext';
import { AppShell } from './AppShell';
import ChatScreen from './screens/ChatScreen';
import DashboardScreen from './screens/DashboardScreen';
import TaskBoardScreen from './screens/TaskBoardScreen';
import AgentsScreen from './screens/AgentsScreen';
import SchedulesScreen from './screens/SchedulesScreen';
import SkillsScreen from './screens/SkillsScreen';
import PortfolioScreen from './screens/PortfolioScreen';
import IntelligenceScreen from './screens/IntelligenceScreen';
import KnowledgeScreen from './screens/KnowledgeScreen';
import ProvidersScreen from './screens/ProvidersScreen';
import LoopsScreen from './screens/LoopsScreen';
import GitHubScreen from './screens/GitHubScreen';
import LogsScreen from './screens/LogsScreen';
import CompanyScreen from './screens/CompanyScreen';
import OnboardingScreen from './screens/OnboardingScreen';
import DoctorScreen from './screens/DoctorScreen';
import AdminScreen from './screens/AdminScreen';
import SamVoiceScreen from './screens/SamVoiceScreen';
import AlertsBell from './screens/AlertsBell';
import QuickNotesFAB from './screens/QuickNotesFAB';
import ActivationGate from './screens/ActivationGate';

const V5_THEME = `
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800;900&family=IBM+Plex+Mono:wght@400;500;600&display=swap');
.v5-root {
  --bg-base:#020304; --bg-surface:#0a0c0f;
  --text-primary:#f7f9fc; --text-secondary:#d9e0ea; --text-tertiary:#a8b3c2; --text-muted:#6e7786;
  --border:rgba(255,255,255,0.09); --border-soft:rgba(255,255,255,0.05);
  --accent:#5da2ff; --accent-hover:#7ab1ff; --danger:#ff6b7d; --warning:#ffbd66; --success:#46d9a4;
  --font-main:'Manrope','SF Pro Display','Segoe UI',sans-serif;
  --font-mono:'IBM Plex Mono','SFMono-Regular',monospace;
  --text-icon-inactive:#616b79;
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

function AdminLocked() {
  return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100%', flexDirection:'column', gap:12 }}>
      <div style={{ fontSize:36 }}>🔒</div>
      <div style={{ fontSize:15, fontWeight:700, color:'var(--text-secondary)' }}>Admin access required</div>
    </div>
  );
}

const V5_SCREENS = [
  'chat', 'dashboard', 'tasks', 'agents', 'schedules', 'skills', 'portfolio',
  'intelligence', 'knowledge', 'providers', 'loops', 'github', 'logs', 'company',
  'onboarding', 'doctor', 'admin', 'sam',
];

function screenFromPath(pathname) {
  // "/v5/doctor" -> "doctor"; unknown or missing segment -> "chat"
  const seg = (pathname.split('/')[2] || '').toLowerCase();
  return V5_SCREENS.includes(seg) ? seg : 'chat';
}

export default function V5App() {
  const location = useLocation();
  const navigate = useNavigate();
  // Deep links: derive the initial screen from the URL so /v5/doctor opens
  // Doctor (previously always opened Chat regardless of path).
  const [screen, setScreen] = React.useState(() => screenFromPath(location.pathname));
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin';
  const agentRunning = true;
  const go = React.useCallback((s) => {
    // Normalize: unknown/invalid targets fall back to chat so state and URL
    // never disagree (e.g. a stale nav id would otherwise produce /v5/<bogus>
    // while the shell renders the chat fallback).
    const target = V5_SCREENS.includes(s) ? s : 'chat';
    setScreen(target);
    navigate(`/v5/${target === 'chat' ? '' : target}`, { replace: false });
  }, [navigate]);
  // Back/forward buttons and external URL changes keep the screen in sync.
  React.useEffect(() => {
    setScreen(screenFromPath(location.pathname));
  }, [location.pathname]);
  const screens = {
    chat:         <ChatScreen />,
    dashboard:    <DashboardScreen dashboardState="healthy" />,
    tasks:        <TaskBoardScreen />,
    agents:       <AgentsScreen onNavigateToChat={() => go('chat')} onNavigateToTasks={() => go('tasks')} />,
    schedules:    <SchedulesScreen />,
    skills:       <SkillsScreen />,
    portfolio:    <PortfolioScreen />,
    intelligence: <IntelligenceScreen onNavigate={go} />,
    knowledge:    <KnowledgeScreen />,
    providers:    <ProvidersScreen />,
    loops:        <LoopsScreen />,
    github:       <GitHubScreen />,
    logs:         <LogsScreen />,
    company:      <CompanyScreen />,
    onboarding:   <OnboardingScreen onComplete={() => go('company')} isAdmin={isAdmin} />,
    doctor:       <DoctorScreen onNavigate={go} />,
    admin:        isAdmin ? <AdminScreen /> : <AdminLocked />,
    sam:          <SamVoiceScreen />,
  };
  return (
    <ActivationGate>
      <div className="v5-root">
        <style>{V5_THEME}</style>
        <AppShell activeScreen={screen} onNavigate={go} agentRunning={agentRunning} isAdmin={isAdmin}>
          {screens[screen] || screens.chat}
        </AppShell>
        <AlertsBell onNavigate={go} />
        <QuickNotesFAB visible={true} />
      </div>
    </ActivationGate>
  );
}
