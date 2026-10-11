import React from 'react';
import { APP_NAME } from '../version';
import { SamFace } from './components/SamAvatar';
import { useAuth } from '../AuthContext';
import EphemeralBanner from './screens/EphemeralBanner';
import { getThemePreference, setThemePreference } from '../theme';


// Six destinations, organised around what the user is doing. The former
// 20-item sidebar mirrored the backend (WORKSPACE/AGENCY/INFRASTRUCTURE/…);
// everything it listed still exists, as tabs inside these hubs — see the
// ALIASES map in V5App.jsx for the old-id → new-destination mapping.

const NAV_ITEMS = [
  { id:'home',      label:'Home',      icon:'Home',          desc:'What needs you, and what happened', section:'MAIN' },
  { id:'assistant', label:'Assistant', icon:'MessageSquare', desc:'Ask your team anything',            section:'MAIN' },
  { id:'work',      label:'Work',      icon:'CheckSquare',   desc:'Tasks, routines and plans',         section:'MAIN' },
  { id:'company',   label:'Company',   icon:'Building2',     desc:'Your business and your team',       section:'MAIN' },
  { id:'insights',  label:'Insights',  icon:'TrendingUp',    desc:'Activity, market and site health',  section:'MAIN' },
  { id:'settings',  label:'Settings',  icon:'Sliders',       desc:'Connections, rules and access',     section:'SYSTEM' },
];

// All five everyday destinations fit the bottom bar — no "More" sheet hiding
// 15 screens behind a second tap. Settings stays reachable via the top-bar menu.
const MOBILE_PRIMARY = ['home', 'assistant', 'work', 'company', 'insights'];

function Icon({ name, size=18, style={} }) {
  const s = size;
  const paths = {
    Home:            <><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M9 22V12h6v10"/></>,
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
    RefreshCw:       <><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M3 21v-5h5"/></>,
    Activity:        <><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></>,
    Building2:       <><path d="M6 22V4a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2v18Z"/><path d="M6 12H4a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2h2"/><path d="M18 9h2a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-2"/><path d="M10 6h4"/><path d="M10 10h4"/><path d="M10 14h4"/><path d="M10 18h4"/></>,
    Sparkles:        <><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M3 5h4"/><path d="M19 17v4"/><path d="M17 19h4"/></>,
    Stethoscope:     <><path d="M4.8 2.3A.3.3 0 1 0 5 2H4a2 2 0 0 0-2 2v5a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6V4a2 2 0 0 0-2-2h-1a.2.2 0 1 0 .3.3"/><path d="M8 15v1a6 6 0 0 0 6 6v0a6 6 0 0 0 6-6v-4"/><circle cx="20" cy="10" r="2"/></>,
    Shield:          <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></>,
    // Shield + check — Governance. Deliberately distinct from `Shield`
    // (Admin): these sit next to each other in the SYSTEM section, and this
    // map has no fallback worth having (an unknown name silently renders a
    // plain circle), so reusing one icon for both would read as a bug.
    ShieldCheck:     <><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 11.5 2 2 4-4"/></>,
    GitBranch:       <><line x1="6" y1="3" x2="6" y2="15"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M18 9a9 9 0 0 1-9 9"/></>,
    Cpu:             <><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M15 2v2M15 20v2M9 2v2M9 20v2M2 15h2M2 9h2M20 15h2M20 9h2"/></>,
    LogOut:          <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></>,
    Mic:             <><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></>,
    // Three labelled sliders — Platform Controls. The `paths` map has no
    // meaningful fallback (an unknown name renders a plain circle), so a nav
    // item without its own entry here would silently look broken.
    Sliders:         <><line x1="4" y1="7" x2="20" y2="7"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="17" x2="20" y2="17"/><circle cx="9" cy="7" r="2"/><circle cx="16" cy="12" r="2"/><circle cx="7" cy="17" r="2"/></>,
    Menu:            <><line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></>,
    X:               <><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></>,
    MoreHorizontal:  <><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></>,
    Bell:            <><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/></>,
    NotePen:         <><path d="M13.4 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-7.4"/><path d="M2 6h4"/><path d="M2 10h4"/><path d="M2 14h4"/><path d="M2 18h4"/><path d="M21.4 5.6a2.12 2.12 0 0 0-3-3L13 8l-1 4 4-1Z"/></>,
    ArrowUp:         <><path d="m5 12 7-7 7 7"/><path d="M12 19V5"/></>,
    Link:            <><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></>,
    Check:           <><path d="M20 6 9 17l-5-5"/></>,
    AlertCircle:     <><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></>,
    ChevronRight:    <><path d="m9 18 6-6-6-6"/></>,
    Clock:           <><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></>,
    Plus:            <><path d="M5 12h14"/><path d="M12 5v14"/></>,
  };
  return (
    <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" style={style} aria-hidden="true" focusable="false">
      {paths[name] || <circle cx="12" cy="12" r="5"/>}
    </svg>
  );
}

const THEME_OPTIONS = [
  { id: 'system', label: 'Auto' },
  { id: 'light', label: 'Light' },
  { id: 'dark', label: 'Dark' },
];

function ThemeSwitch() {
  const [pref, setPref] = React.useState(getThemePreference);
  const choose = (id) => { setPref(id); setThemePreference(id); };
  return (
    <div className="shell-theme" role="radiogroup" aria-label="Colour theme">
      {THEME_OPTIONS.map(o => (
        <button key={o.id} type="button" role="radio" aria-checked={pref === o.id}
          className={pref === o.id ? 'is-on' : ''} onClick={() => choose(o.id)}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

function AgentStatus({ running }) {
  return (
    <div className={`shell-status ${running ? 'is-on' : ''}`} role="status">
      <span className="shell-status-dot" aria-hidden="true"/>
      {running ? 'Your team is working' : 'Your team is idle'}
    </div>
  );
}

function SidebarNav({ activeScreen, onNavigate, onClose, agentRunning, isAdmin, user, onLogout }) {
  const visible = NAV_ITEMS.filter(n => !n.adminOnly || isAdmin);
  const main = visible.filter(n => n.section === 'MAIN');
  const system = visible.filter(n => n.section !== 'MAIN');
  const name = user?.name || user?.email || 'You';
  const item = (n) => {
    const active = activeScreen === n.id;
    return (
      <li key={n.id}>
        <button type="button" className={`shell-nav-item ${active ? 'is-active' : ''}`}
          aria-current={active ? 'page' : undefined}
          onClick={() => { onNavigate(n.id); onClose && onClose(); }}>
          <Icon name={n.icon} size={19} style={{ flexShrink: 0 }}/>
          <span className="shell-nav-text">
            <span className="shell-nav-label">{n.label}</span>
            <span className="shell-nav-desc">{n.desc}</span>
          </span>
        </button>
      </li>
    );
  };
  return (
    <div className="shell-sidebar-inner">
      <div className="shell-brand">
        <span className="shell-brand-mark" aria-hidden="true"><SamFace size={30}/></span>
        <span className="shell-brand-name">{APP_NAME}</span>
      </div>
      <AgentStatus running={agentRunning}/>

      <nav aria-label="Main" className="shell-nav">
        <ul>{main.map(item)}</ul>
        {system.length > 0 && <ul className="shell-nav-system">{system.map(item)}</ul>}
      </nav>

      <div className="shell-foot">
        <ThemeSwitch/>
        <div className="shell-user">
          <span className="shell-avatar" aria-hidden="true">{name[0].toUpperCase()}</span>
          <span className="shell-user-text">
            <span className="shell-user-name">
              {name}
              {isAdmin && <span className="shell-role">Admin</span>}
            </span>
            {user?.email && user?.name && <span className="shell-user-mail">{user.email}</span>}
          </span>
          <button type="button" className="shell-icon-btn" aria-label="Sign out" title="Sign out" onClick={onLogout}>
            <Icon name="LogOut" size={17}/>
          </button>
        </div>
      </div>
    </div>
  );
}

function MobileBottomNav({ activeScreen, onNavigate }) {
  const primaryItems = NAV_ITEMS.filter(n => MOBILE_PRIMARY.includes(n.id));
  return (
    <nav className="shell-bottomnav" aria-label="Main">
      {primaryItems.map(item => {
        const active = activeScreen === item.id;
        return (
          <button key={item.id} type="button" onClick={() => onNavigate(item.id)}
            className={active ? 'is-active' : ''} aria-current={active ? 'page' : undefined}>
            <Icon name={item.icon} size={22}/>
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

function MobileDrawer({ open, onClose, children }) {
  const panelRef = React.useRef(null);
  React.useEffect(() => {
    if (!open) return undefined;
    const prev = document.activeElement;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', onKey);
    panelRef.current?.querySelector('button')?.focus();
    return () => { document.removeEventListener('keydown', onKey); prev && prev.focus && prev.focus(); };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="shell-drawer" onClick={onClose}>
      <div ref={panelRef} className="shell-drawer-panel" role="dialog" aria-modal="true" aria-label="Menu"
        onClick={e => e.stopPropagation()}>
        <button type="button" className="shell-icon-btn shell-drawer-close" aria-label="Close menu" onClick={onClose}>
          <Icon name="X" size={20}/>
        </button>
        {children}
      </div>
    </div>
  );
}

function AppShell({ children, activeScreen, onNavigate, agentRunning, isAdmin, headerActions = null }) {
  const { user: authUser, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = React.useState(false);
  const closeDrawer = React.useCallback(() => setSidebarOpen(false), []);
  const navItem = NAV_ITEMS.find(n => n.id === activeScreen) || NAV_ITEMS[0];
  const mainRef = React.useRef(null);

  // A new destination starts at the top, and screen-reader users hear where they are.
  React.useEffect(() => { mainRef.current?.scrollTo?.(0, 0); }, [activeScreen]);

  const nav = (onClose) => (
    <SidebarNav activeScreen={activeScreen} onNavigate={onNavigate} onClose={onClose}
      agentRunning={agentRunning} isAdmin={isAdmin} user={authUser} onLogout={logout}/>
  );

  return (
    <div className="shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <aside className="shell-sidebar">{nav()}</aside>
      <MobileDrawer open={sidebarOpen} onClose={closeDrawer}>{nav(closeDrawer)}</MobileDrawer>

      <div className="shell-body">
        <header className="shell-header">
          <button type="button" className="shell-icon-btn shell-menu-btn" aria-label="Open menu"
            aria-expanded={sidebarOpen} onClick={() => setSidebarOpen(true)}>
            <Icon name="Menu" size={20}/>
          </button>
          <div className="shell-header-title">
            <span className="shell-header-label">{navItem.label}</span>
            <span className="shell-header-desc">{navItem.desc}</span>
          </div>
          <div className="shell-header-actions">{headerActions}</div>
        </header>
        <main id="main-content" ref={mainRef} className="shell-main" tabIndex={-1} aria-label={navItem.label}>
          {children}
        </main>
        <MobileBottomNav activeScreen={activeScreen} onNavigate={onNavigate}/>
      </div>
      <EphemeralBanner isAdmin={isAdmin}/>
    </div>
  );
}

export { AppShell, Icon, NAV_ITEMS };
