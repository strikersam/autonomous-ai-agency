import React from 'react';
import { AppShell } from './AppShell';
import ChatScreen from './screens/ChatScreen';

/**
 * V5App — entry point for the "Agency Core" (V5.0) frontend redesign.
 * Ported from the Claude Design handoff (Agency Core.html). Incremental: the Chat
 * screen is live; the remaining screens are ported in later parts of the redesign PR.
 * Mounted at /v5 so it can be reviewed without disturbing the existing dashboard.
 */
function ComingSoon({ screen }) {
  return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', height:'100%', flexDirection:'column', gap:12, padding:24, textAlign:'center' }}>
      <div style={{ width:52, height:52, borderRadius:16, background:'linear-gradient(135deg,rgba(93,162,255,0.15),rgba(93,162,255,0.05))', border:'1px solid rgba(93,162,255,0.2)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:22 }}>✦</div>
      <div style={{ fontSize:16, fontWeight:800, color:'#fff', letterSpacing:'-0.03em', textTransform:'capitalize' }}>{screen}</div>
      <div style={{ fontSize:13, color:'var(--text-muted)', fontFamily:'var(--font-mono)', maxWidth:340, lineHeight:1.6 }}>This Agency Core screen is being ported from the design in a later part of the redesign PR.</div>
    </div>
  );
}

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

export default function V5App() {
  const [screen, setScreen] = React.useState('chat');
  // isAdmin / agentRunning will be wired to AuthContext + live status in a later part;
  // defaults mirror the design preview.
  const isAdmin = true;
  const agentRunning = true;

  return (
    <div className="v5-root">
      <style>{V5_THEME}</style>
      <AppShell activeScreen={screen} onNavigate={setScreen} agentRunning={agentRunning} isAdmin={isAdmin}>
        {screen === 'chat'
          ? <ChatScreen chatState="idle" />
          : <ComingSoon screen={screen} />}
      </AppShell>
    </div>
  );
}
