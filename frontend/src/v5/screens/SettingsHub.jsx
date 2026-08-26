import React from 'react';
import HubTabs from '../components/ui/HubTabs';
import Spinner from '../components/ui/Spinner';

const ProvidersScreen = React.lazy(() => import('./ProvidersScreen'));
const ControlsScreen = React.lazy(() => import('./ControlsScreen'));
const GovernanceScreen = React.lazy(() => import('./GovernanceScreen'));
const AdminScreen = React.lazy(() => import('./AdminScreen'));
const DoctorScreen = React.lazy(() => import('./DoctorScreen'));
const GitHubScreen = React.lazy(() => import('./GitHubScreen'));
const LoopsScreen = React.lazy(() => import('./LoopsScreen'));
const SkillsScreen = React.lazy(() => import('./SkillsScreen'));

/**
 * SettingsHub — every technical surface behind one door.
 *
 * Absorbs eight former top-level nav items (Providers, Controls, Governance,
 * Admin, Doctor, GitHub, Loops, Skills). Everyday screens stay plain-language;
 * model IDs, config keys, tokens and policy live here only. Per-section access
 * matches what each screen enforced before the move: the four admin sections
 * were admin-gated as nav items, the other four were open to every user.
 */
const SECTIONS = [
  { id: 'providers', label: 'AI models & providers', adminOnly: true },
  { id: 'controls', label: 'Platform controls', adminOnly: true },
  { id: 'governance', label: 'Safety & approvals', adminOnly: true },
  { id: 'admin', label: 'People & access', adminOnly: true },
  { id: 'doctor', label: 'System health' },
  { id: 'github', label: 'Code & GitHub' },
  { id: 'loops', label: 'Automations' },
  { id: 'skills', label: 'Skills' },
];

export default function SettingsHub({ initialSection, isAdmin, onNavigate }) {
  const visible = SECTIONS.filter(s => !s.adminOnly || isAdmin);
  const fallback = isAdmin ? 'providers' : 'doctor';
  const [section, setSection] = React.useState(
    visible.some(s => s.id === initialSection) ? initialSection : fallback
  );
  return (
    <div>
      <div style={{ padding: '20px 16px 0', maxWidth: 1000, margin: '0 auto' }}>
        <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 4 }}>Settings &amp; Infrastructure</div>
        <p style={{ fontSize: 13, color: 'var(--text-tertiary)', lineHeight: 1.5, maxWidth: 560, margin: 0 }}>
          The technical side of your agency. Nothing here is needed day to day — the everyday screens run on these settings.
        </p>
      </div>
      <HubTabs tabs={visible} active={section} onChange={setSection} />
      <React.Suspense fallback={<Spinner center />}>
        {section === 'providers' && <ProvidersScreen />}
        {section === 'controls' && <ControlsScreen />}
        {section === 'governance' && <GovernanceScreen />}
        {section === 'admin' && <AdminScreen />}
        {section === 'doctor' && <DoctorScreen onNavigate={onNavigate} />}
        {section === 'github' && <GitHubScreen />}
        {section === 'loops' && <LoopsScreen />}
        {section === 'skills' && <SkillsScreen />}
      </React.Suspense>
    </div>
  );
}
