import React from 'react';
import { APP_NAME, APP_LABEL } from '../version';
import { useAuth } from '../AuthContext';


// nav.jsx — Agency Core navigation (clean, all screens)

const NAV_ITEMS = [
  { id:'chat',       label:'Chat',       icon:'MessageSquare',  desc:'Unified assistant',      section:'WORKSPACE' },
  { id:'dashboard',  label:'Dashboard',  icon:'LayoutDashboard',desc:'System overview',         section:'WORKSPACE' },
  { id:'tasks',      label:'Tasks',      icon:'CheckSquare',    desc:'Job lifecycle board',     section:'WORKSPACE' },
  { id:'agents',     label:'Agents',     icon:'Bot',            desc:'Autonomous agency team',  section:'AGENCY' },
  { id:'schedules',  label:'Schedules',  icon:'Calendar',       desc:'Autopilot jobs',          section:'AGENCY' },
  { id:'skills',      label:'Skills',      icon:'Zap',          desc:'Agentic commerce skills',  section:'AGENCY' },
  { id:'portfolio',   label:'Portfolio',   icon:'Target',       desc:'WSJF roadmap & sprints',   section:'AGENCY' },
  { id:'intelligence',label:'Intelligence',icon:'TrendingUp',   desc:'Competitor & trend intel', section:'AGENCY' },
  { id:'knowledge',  label:'Knowledge',  icon:'BookOpen',       desc:'Docs, sources, activity', section:'AGENCY' },
  { id:'providers',  label:'Providers',  icon:'Layers',         desc:'Models, Ollama, MCP',     section:'INFRASTRUCTURE' },
  { id:'logs',       label:'Logs',       icon:'Activity',       desc:'Traces & observability',  section:'INFRASTRUCTURE' },
  { id:'github',     label:'GitHub',     icon:'GitBranch',      desc:'Token, repos & PRs',      section:'INFRASTRUCTURE' },
  { id:'company',    label:'Company',    icon:'Building2',      desc:'Operating context',       section:'CONTEXT' },
  { id:'onboarding', label:'Onboarding', icon:'Sparkles',       desc:'Company setup wizard',    section:'CONTEXT' },
  { id:'doctor',     label:'Doctor',     icon:'Stethoscope',    desc:'Diagnostics',             section:'SYSTEM' },
  { id:'admin',      label:'Admin',      icon:'Shield',         desc:'Users & access',          section:'SYSTEM', adminOnly:true },
];

const MOBILE_PRIMARY = ['dashboard', 'agents', 'tasks', 'doctor'];
const MOBILE_MORE    = ['company', 'schedules', 'skills', 'portfolio', 'intelligence', 'knowledge', 'providers', 'github', 'logs', 'onboarding', 'admin'];

function Icon({ name, size=18, style={} }) {
  const s = size;
  const paths = {
    MessageSquare:   <><rect x="3" y="3" width="18" height="16" rx="3"/><path d="M8 20v-4"/><path d="M3 19l5-3h9"/></>,
    LayoutDashboard: <><rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/></>,
    CheckSquare:     <><path d="m9 11 3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></>,
    Bot:             <><rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><circle cx="8" cy="16" r="1" fill="currentColor"/><circle cx="16" cy="16" r="1" fill="currentColor"/></>,
    Calendar:        <><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></>,
    BookOpen:        <><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></>,
    Zap:             <><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></>,
    TrendingUp:      <><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></>,
    Target:          <><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1" fill="currentColor"/></>,
    Layers:          <><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></>,
    Activity:        <><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></>,
    Building2:       <><path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/></>,
    Sparkles:        <><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M3 5h4"/><path d="M19 17v4"/><path d="M17 19h4"/></>,
    Stethoscope:     <><path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3"/><path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4"/><circle cx="20" cy="10" r="2"/></>,
    Shield:          <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></>,
    GitBranch:       <><line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></>,
    Cpu:             <><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M15 2v2M15 20v2M9 2v2M9 20v2M2 15h2M2 9h2M20 15h2M20 9h2"/></>,
    LogOut:          <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></>,
    Menu:            <><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></>,
    X:               <><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>,
    MoreHorizontal:  <><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></>,
  };
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" style={style}>
      {paths[name] || <circle cx="12" cy="12" r="5"/>}
    </svg>
  );
}

function AgentStatus({ running }) {
  return (
    <div style={{ display:'inline-flex', alignItems:'center', gap:5, background:running?'rgba(70,217,164,0.10)':'rgba(255,255,255,0.04)', border:`1px solid ${running?'rgba(70,217,164,0.2)':'rgba(255,255,255,0.08)'}`, borderRadius:999, padding:'3px 9px', fontSize:10, fontFamily:'var(--font-mono)', letterSpacing:'0.12em', textTransform:'uppercase', color:running?'#46d9a4':'var(--text-muted)' }}>
      <span style={{ width:6, height:6, borderRadius:'50%', background:running?'#46d9a4':'var(--text-muted)', animation:running?'pulse 2s ease-in-out infinite':'none' }}/>
      {running ? 'Agency active' : 'Idle'}
    </div>
  );
}

function SidebarNav({ activeScreen, onNavigate, onClose, agentRunning, isAdmin, user, onLogout }) {
  const sections = [...new Set(NAV_ITEMS.map(n => n.section))];
  const visible  = NAV_ITEMS.filter(n => !n.adminOnly || isAdmin);
  return (
    <div style={{ display:'flex', flexDirection:'column', height:'100%', background:'rgba(5,6,8,0.98)', borderRight:'1px solid var(--border)' }}>
      {/* Logo */}
      <div style={{ padding:'18px 16px 14px', borderBottom:'1px solid rgba(255,255,255,0.08)' }}>
        <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:10 }}>
          <div style={{ width:34, height:34, borderRadius:10, background:'linear-gradient(135deg,#6CB0FF 0%,#3A7FE8 100%)', boxShadow:'0 4px 16px rgba(93,162,255,0.30)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
            <Icon name="Cpu" size={16} style={{ color:'#fff' }}/>
          </div>
          <div>
            <div style={{ fontSize:14, fontWeight:900, color:'#fff', letterSpacing:'-0.04em', lineHeight:1.1 }}>{APP_NAME}</div>
            <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.14em', textTransform:'uppercase', marginTop:2 }}>{APP_LABEL}</div>
          </div>
        </div>
        <AgentStatus running={agentRunning}/>
      </div>

      {/* Sectioned nav */}
      <nav style={{ flex:1, padding:'6px 0', overflowY:'auto' }}>
        {sections.map(section => {
          const items = visible.filter(n => n.section === section);
          if (!items.length) return null;
          return (
            <div key={section} style={{ marginBottom:2 }}>
              <div style={{ padding:'10px 18px 4px', fontSize:11, fontFamily:'var(--font-mono)', letterSpacing:'0.14em', textTransform:'uppercase', color:'var(--text-muted)', fontWeight:700 }}>{section}</div>
              {items.map(item => {
                const active = activeScreen === item.id;
                return (
                  <button key={item.id} onClick={() => { onNavigate(item.id); onClose&&onClose(); }} style={{ display:'flex', alignItems:'center', gap:12, width:'calc(100% - 16px)', margin:'2px 8px', padding:'10px 14px', borderRadius:12, border:'none', cursor:'pointer', background:active?'rgba(93,162,255,0.10)':'transparent', color:active?'#fff':'var(--text-tertiary)', fontFamily:'var(--font-main)', fontSize:15, fontWeight:active?600:500, textAlign:'left', transition:'all 0.15s ease', position:'relative' }}
                  onMouseEnter={e=>{ if(!active){e.currentTarget.style.background='rgba(255,255,255,0.04)'; e.currentTarget.style.color='var(--text-secondary)'; }}}
                  onMouseLeave={e=>{ if(!active){e.currentTarget.style.background='transparent'; e.currentTarget.style.color='var(--text-tertiary)'; }}}>
                    {active && <div style={{ position:'absolute', left:0, top:'50%', transform:'translateY(-50%)', width:3, height:20, background:'var(--accent)', borderRadius:999 }}/>}
                    <Icon name={item.icon} size={18} style={{ color:active?'var(--accent)':'var(--text-icon-inactive)', flexShrink:0 }}/>
                    <div style={{ flex:1, minWidth:0 }}>
                      <div style={{ fontSize:15 }}>{item.label}</div>
                      <div style={{ fontSize:11, color:active?'rgba(93,162,255,0.7)':'var(--text-muted)', marginTop:2, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{item.desc}</div>
                    </div>
                    {item.adminOnly && <span style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'#ff6b7d', padding:'2px 6px', borderRadius:4, background:'rgba(255,107,125,0.10)', border:'1px solid rgba(255,107,125,0.20)', flexShrink:0 }}>admin</span>}
                  </button>
                );
              })}
            </div>
          );
        })}
      </nav>

      {/* User footer */}
      <div style={{ padding:'10px 8px', borderTop:'1px solid rgba(255,255,255,0.08)' }}>
        <div style={{ display:'flex', alignItems:'center', gap:10, padding:'8px 10px', borderRadius:10, background:'rgba(255,255,255,0.03)' }}>
          <div style={{ width:28, height:28, borderRadius:'50%', background:'linear-gradient(135deg,var(--accent),#3a7fe8)', display:'flex', alignItems:'center', justifyContent:'center', fontSize:11, fontWeight:800, color:'#06111f', flexShrink:0 }}>
            {(user?.name || user?.email || '?')[0].toUpperCase()}
          </div>
          <div style={{ flex:1, minWidth:0 }}>
            <div style={{ display:'flex', alignItems:'center', gap:5 }}>
              <span style={{ fontSize:12, fontWeight:600, color:'var(--text-primary)' }}>{user?.name || user?.email || 'User'}</span>
              {isAdmin && <span style={{ fontSize:8, fontFamily:'var(--font-mono)', letterSpacing:'0.10em', textTransform:'uppercase', padding:'1px 5px', borderRadius:4, color:'#ff6b7d', background:'rgba(255,107,125,0.10)', border:'1px solid rgba(255,107,125,0.20)' }}>admin</span>}
            </div>
            <div style={{ fontSize:9, fontFamily:'var(--font-mono)', color:'var(--text-muted)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{user?.email || ''}</div>
          </div>
          <button
            title="Log out"
            onClick={onLogout}
            style={{ display:'flex', alignItems:'center', justifyContent:'center', width:26, height:26, borderRadius:8, background:'transparent', border:'none', cursor:'pointer', color:'var(--text-muted)', flexShrink:0 }}
            onMouseEnter={e=>{ e.currentTarget.style.color='var(--danger)'; e.currentTarget.style.background='rgba(255,107,125,0.10)'; }}
            onMouseLeave={e=>{ e.currentTarget.style.color='var(--text-muted)'; e.currentTarget.style.background='transparent'; }}>
            <Icon name="LogOut" size={12}/>
          </button>
        </div>
      </div>
    </div>
  );
}

function MobileMoreSheet({ activeScreen, onNavigate, onClose, isAdmin }) {
  const moreItems = NAV_ITEMS.filter(n => MOBILE_MORE.includes(n.id) && (!n.adminOnly || isAdmin));
  return (
    <>
      <div onClick={onClose} style={{ position:'fixed', inset:0, zIndex:55, background:'rgba(0,0,0,0.55)', backdropFilter:'blur(4px)' }}/>
      <div style={{ position:'fixed', bottom:0, left:0, right:0, zIndex:60, background:'rgba(10,12,16,0.98)', borderTop:'1px solid rgba(255,255,255,0.10)', borderRadius:'20px 20px 0 0', padding:'14px 16px', paddingBottom:'calc(env(safe-area-inset-bottom,0px) + 16px)', animation:'fadeSlideUp 0.2s ease-out' }}>
        <div style={{ display:'flex', justifyContent:'center', marginBottom:12 }}>
          <div style={{ width:36, height:4, borderRadius:999, background:'rgba(255,255,255,0.15)' }}/>
        </div>
        <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--text-muted)', letterSpacing:'0.12em', textTransform:'uppercase', marginBottom:12 }}>More screens</div>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:8 }}>
          {moreItems.map(item => {
            const active = activeScreen === item.id;
            return (
              <button key={item.id} onClick={() => { onNavigate(item.id); onClose(); }} style={{ display:'flex', alignItems:'center', gap:12, padding:'12px 14px', borderRadius:14, background:active?'rgba(93,162,255,0.10)':'rgba(255,255,255,0.04)', border:`1px solid ${active?'rgba(93,162,255,0.22)':'rgba(255,255,255,0.08)'}`, cursor:'pointer', textAlign:'left', transition:'all 0.15s ease' }}>
                <div style={{ width:36, height:36, borderRadius:10, background:active?'rgba(93,162,255,0.15)':'rgba(255,255,255,0.06)', display:'flex', alignItems:'center', justifyContent:'center', flexShrink:0 }}>
                  <Icon name={item.icon} size={18} style={{ color:active?'var(--accent)':'var(--text-muted)' }}/>
                </div>
                <div style={{ minWidth:0 }}>
                  <div style={{ fontSize:14, fontWeight:600, color:active?'#fff':'var(--text-secondary)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{item.label}</div>
                  <div style={{ fontSize:11, color:'var(--text-muted)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', marginTop:2 }}>{item.desc}</div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}

function MobileBottomNav({ activeScreen, onNavigate, isAdmin }) {
  const [moreOpen, setMoreOpen] = React.useState(false);
  const primaryItems = NAV_ITEMS.filter(n => MOBILE_PRIMARY.includes(n.id));
  return (
    <>
      {moreOpen && <MobileMoreSheet activeScreen={activeScreen} onNavigate={id=>{ onNavigate(id); setMoreOpen(false); }} onClose={()=>setMoreOpen(false)} isAdmin={isAdmin}/>}
      <nav style={{ position:'fixed', bottom:0, left:0, right:0, zIndex:50, background:'rgba(8,10,14,0.96)', backdropFilter:'blur(20px)', borderTop:'1px solid var(--border)', paddingBottom:'max(env(safe-area-inset-bottom,0px), 10px)', paddingTop:6 }}>
        <div style={{ display:'grid', gridTemplateColumns:'repeat(6,1fr)', gap:0, padding:'0 4px' }}>
          {primaryItems.slice(0,2).map(item => {
            const active = activeScreen === item.id;
            return (
              <button key={item.id} onClick={()=>onNavigate(item.id)} style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:4, padding:'8px 2px 6px', minHeight:60, border:'none', background:active?'rgba(93,162,255,0.10)':'transparent', borderRadius:12, cursor:'pointer', transition:'all 0.15s' }}>
                <Icon name={item.icon} size={22} style={{ color:active?'var(--accent)':'var(--text-muted)' }}/>
                <span style={{ fontSize:11, fontWeight:600, color:active?'var(--accent)':'var(--text-muted)' }}>{item.label}</span>
              </button>
            );
          })}
          {/* Chat FAB */}
          <button onClick={()=>onNavigate('chat')} style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:4, padding:'0 2px 6px', minHeight:60, border:'none', background:'transparent', cursor:'pointer', marginTop:-12 }}>
            <div style={{ width:50, height:50, borderRadius:'50%', background:activeScreen==='chat'?'var(--accent-hover)':'var(--accent)', boxShadow:'0 4px 20px rgba(93,162,255,0.40)', display:'flex', alignItems:'center', justifyContent:'center', transition:'all 0.15s' }}>
              <Icon name="MessageSquare" size={22} style={{ color:'#06111f' }}/>
            </div>
            <span style={{ fontSize:11, fontWeight:600, color:activeScreen==='chat'?'var(--accent)':'var(--text-muted)' }}>Chat</span>
          </button>
          {primaryItems.slice(2).map(item => {
            const active = activeScreen === item.id;
            return (
              <button key={item.id} onClick={()=>onNavigate(item.id)} style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:4, padding:'8px 2px 6px', minHeight:60, border:'none', background:active?'rgba(93,162,255,0.10)':'transparent', borderRadius:12, cursor:'pointer', transition:'all 0.15s' }}>
                <Icon name={item.icon} size={22} style={{ color:active?'var(--accent)':'var(--text-muted)' }}/>
                <span style={{ fontSize:11, fontWeight:600, color:active?'var(--accent)':'var(--text-muted)' }}>{item.label}</span>
              </button>
            );
          })}
          {/* More */}
          <button onClick={()=>setMoreOpen(true)} style={{ display:'flex', flexDirection:'column', alignItems:'center', justifyContent:'center', gap:4, padding:'8px 2px 6px', minHeight:60, border:'none', background:MOBILE_MORE.includes(activeScreen)?'rgba(93,162,255,0.10)':'transparent', borderRadius:12, cursor:'pointer', transition:'all 0.15s' }}>
            <Icon name="MoreHorizontal" size={22} style={{ color:MOBILE_MORE.includes(activeScreen)?'var(--accent)':'var(--text-muted)' }}/>
            <span style={{ fontSize:11, fontWeight:600, color:MOBILE_MORE.includes(activeScreen)?'var(--accent)':'var(--text-muted)' }}>More</span>
          </button>
        </div>
      </nav>
    </>
  );
}

function MobileTopBar({ title, subtitle, onMenuOpen }) {
  return (
    <div style={{ display:'flex', alignItems:'center', gap:12, padding:'12px 16px', paddingTop:'calc(env(safe-area-inset-top,0px) + 12px)', background:'rgba(8,10,14,0.92)', backdropFilter:'blur(20px)', borderBottom:'1px solid var(--border)', position:'sticky', top:0, zIndex:40 }}>
      <button onClick={onMenuOpen} style={{ width:44, height:44, borderRadius:12, border:'1px solid var(--border-soft)', background:'rgba(255,255,255,0.05)', display:'flex', alignItems:'center', justifyContent:'center', cursor:'pointer', color:'var(--text-secondary)', flexShrink:0 }}>
        <Icon name="Menu" size={18}/>
      </button>
      <div style={{ width:32, height:32, borderRadius:9, flexShrink:0, background:'linear-gradient(135deg,#6CB0FF 0%,#3A7FE8 100%)', display:'flex', alignItems:'center', justifyContent:'center' }}>
        <Icon name="Cpu" size={15} style={{ color:'#fff' }}/>
      </div>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:17, fontWeight:900, color:'#fff', letterSpacing:'-0.04em', lineHeight:1.1 }}>{APP_LABEL}</div>
        {subtitle && <div style={{ fontSize:12, fontFamily:'var(--font-mono)', color:'var(--accent)', letterSpacing:'0.10em', textTransform:'uppercase', marginTop:2 }}>{subtitle}</div>}
      </div>
    </div>
  );
}

function AppShell({ children, activeScreen, onNavigate, agentRunning, isAdmin }) {
  const { user: authUser, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  const navItem = NAV_ITEMS.find(n => n.id === activeScreen) || NAV_ITEMS[0];
  return (
    <div style={{ display:'flex', height:'100dvh', overflow:'hidden', background:'var(--bg-base)' }}>
      <div className="desktop-sidebar" style={{ width:252, flexShrink:0, height:'100%', flexDirection:'column' }}>
        <SidebarNav activeScreen={activeScreen} onNavigate={onNavigate} agentRunning={agentRunning} isAdmin={isAdmin} user={authUser} onLogout={logout}/>
      </div>
      {sidebarOpen && (
        <div style={{ position:'fixed', inset:0, zIndex:60, background:'rgba(0,0,0,0.65)', backdropFilter:'blur(4px)' }} onClick={()=>setSidebarOpen(false)}>
          <div style={{ position:'absolute', left:0, top:0, bottom:0, width:'min(84vw,280px)' }} onClick={e=>e.stopPropagation()}>
            <SidebarNav activeScreen={activeScreen} onNavigate={onNavigate} onClose={()=>setSidebarOpen(false)} agentRunning={agentRunning} isAdmin={isAdmin} user={authUser} onLogout={logout}/>
          </div>
        </div>
      )}
      <div style={{ flex:1, display:'flex', flexDirection:'column', minWidth:0, height:'100%', overflow:'hidden' }}>
        <div className="mobile-topbar">
          <MobileTopBar title={APP_LABEL} subtitle={navItem.label} onMenuOpen={()=>setSidebarOpen(true)}/>
        </div>
        <div className="main-scroll" style={{ flex:1, overflowY:'auto', overflowX:'hidden' }}>
          {children}
        </div>
        <div className="mobile-bottomnav">
          <MobileBottomNav activeScreen={activeScreen} onNavigate={onNavigate} isAdmin={isAdmin}/>
        </div>
      </div>
      <style>{`
        .desktop-sidebar  { display:none; flex-direction:column; }
        .mobile-topbar    { display:block; }
        .mobile-bottomnav { display:block; }
        .main-scroll      { padding-bottom: calc(env(safe-area-inset-bottom, 0px) + 72px); }
        @media (min-width:1024px) {
          .desktop-sidebar  { display:flex; }
          .mobile-topbar    { display:none; }
          .mobile-bottomnav { display:none; }
          .main-scroll      { padding-bottom: 0; }
        }
        @keyframes pulse       { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.5;transform:scale(.8)} }
        @keyframes spin        { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
        @keyframes fadeSlideUp { from{opacity:0;transform:translateY(10px)} to{opacity:1;transform:translateY(0)} }
        @keyframes shimmer     { 0%{background-position:-200% 0} 100%{background-position:200% 0} }
        @keyframes blink       { 0%,100%{opacity:1} 50%{opacity:.2} }
      `}</style>
    </div>
  );
}

export { AppShell, Icon, NAV_ITEMS };
