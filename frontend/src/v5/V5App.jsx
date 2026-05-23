import React from 'react';
import { AppShell } from './AppShell';
import ChatScreen from './screens/ChatScreen';
import DashboardScreen from './screens/DashboardScreen';
import TaskBoardScreen from './screens/TaskBoardScreen';
import AgentsScreen from './screens/AgentsScreen';
import SchedulesScreen from './screens/SchedulesScreen';
import SkillsScreen from './screens/SkillsScreen';
import IntelligenceScreen from './screens/IntelligenceScreen';
import KnowledgeScreen from './screens/KnowledgeScreen';
import ProvidersScreen from './screens/ProvidersScreen';
import LogsScreen from './screens/LogsScreen';
import CompanyScreen from './screens/CompanyScreen';
import OnboardingScreen from './screens/OnboardingScreen';
import DoctorScreen from './screens/DoctorScreen';
import AdminScreen from './screens/AdminScreen';
import AlertsBell from './screens/AlertsBell';
import QuickNotesFAB from './screens/QuickNotesFAB';

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

export default function V5App() {
  const [screen, setScreen] = React.useState('chat');
  const isAdmin = true;
  const agentRunning = true;
  const go = (s) => setScreen(s);
  const screens = {
    chat:         <ChatScreen chatState="idle" />,
    dashboard:    <DashboardScreen dashboardState="healthy" />,
    tasks:        <TaskBoardScreen />,
    agents:       <AgentsScreen onNavigateToChat={() => go('chat')} />,
    schedules:    <SchedulesScreen />,
    skills:       <SkillsScreen />,
    intelligence: <IntelligenceScreen />,
    knowledge:    <KnowledgeScreen />,
    providers:    <ProvidersScreen />,
    logs:         <LogsScreen />,
    company:      <CompanyScreen />,
    onboarding:   <OnboardingScreen onComplete={() => go('company')} isAdmin={isAdmin} />,
    doctor:       <DoctorScreen />,
    admin:        isAdmin ? <AdminScreen /> : <AdminLocked />,
  };
  return (
    <div className="v5-root">
      <style>{V5_THEME}</style>
      <AppShell activeScreen={screen} onNavigate={go} agentRunning={agentRunning} isAdmin={isAdmin}>
        {screens[screen] || screens.chat}
      </AppShell>
      <AlertsBell onNavigate={go} />
      <QuickNotesFAB visible={true} />
    </div>
  );
}
