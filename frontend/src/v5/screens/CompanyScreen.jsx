/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import * as api from '../../api';

// company.jsx — Company Graph / Operating Context screen

const PREVIEW_COMPANY_DATA = {
  name: 'Acme Store',
  domain: 'acme-store.com',
  industry: 'E-commerce · Retail',
  since: 'May 2026',
  systems: [
    { name: 'Shopify',     category: 'Commerce',   status: 'connected', icon: '🛍' },
    { name: 'Contentful',  category: 'CMS',        status: 'connected', icon: '📄' },
    { name: 'GA4 + GTM',   category: 'Analytics',  status: 'connected', icon: '📊' },
    { name: 'Klaviyo',     category: 'CRM',        status: 'connected', icon: '📧' },
    { name: 'Gorgias',     category: 'Support',    status: 'connected', icon: '💬' },
    { name: 'Gatsby',      category: 'Frontend',   status: 'connected', icon: '⚛' },
  ],
  repos: [
    { name: 'acme-store',        branch: 'main', updated: '2h ago',  prs: 2 },
    { name: 'acme-content-utils',branch: 'main', updated: '3d ago',  prs: 0 },
  ],
  environments: [
    { name: 'Production',  url: 'acme-store.com',         status: 'healthy' },
    { name: 'Staging',     url: 'staging.acme-store.com', status: 'healthy' },
    { name: 'Preview',     url: 'preview.acme-store.com', status: 'warn' },
  ],
  specialists: [
    { name: 'Commerce Agent',  status: 'active',  lastRun: '8m ago',  icon: '🛍' },
    { name: 'Content Agent',   status: 'idle',    lastRun: '1h ago',  icon: '📄' },
    { name: 'Analytics Agent', status: 'idle',    lastRun: '3h ago',  icon: '📊' },
    { name: 'Support Agent',   status: 'idle',    lastRun: '6h ago',  icon: '💬' },
    { name: 'Dev Agent',       status: 'active',  lastRun: '14m ago', icon: '⚙' },
    { name: 'Security Agent',  status: 'running', lastRun: '2m ago',  icon: '🔒' },
  ],
  priorities: [
    'Improve checkout conversion (currently 2.3% — industry avg 3.1%)',
    'Speed up product page load (LCP 4.1s on mobile)',
    'Reduce cart abandonment rate',
    'Automate Contentful publishing workflow',
  ],
  quickActions: [
    { label: 'Audit checkout flow', icon: '◎', desc: 'Run a full conversion analysis' },
    { label: 'Scan for slow pages', icon: '⚡', desc: 'Identify LCP regressions' },
    { label: 'Pull support tickets', icon: '📥', desc: 'Sync latest Gorgias tickets' },
    { label: 'Check CI status',      icon: '✓',  desc: 'View latest test run results' },
  ],
};

function SectionHeader({ label, icon, style = {} }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10, ...style }}>
      {icon && <span style={{ fontSize: 14 }}>{icon}</span>}
      <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.15em', textTransform: 'uppercase' }}>{label}</span>
    </div>
  );
}

function Card({ children, style = {} }) {
  return (
    <div style={{
      borderRadius: 16, border: '1px solid rgba(255,255,255,0.09)',
      background: 'rgba(255,255,255,0.03)',
      padding: '14px 16px', ...style,
    }}>{children}</div>
  );
}

function StatusDotC({ status }) {
  const c = status === 'healthy' || status === 'connected' || status === 'active' ? '#46d9a4'
          : status === 'running' ? '#5da2ff'
          : status === 'warn'    ? '#ffbd66'
          : 'var(--text-muted)';
  return (
    <span style={{ width: 7, height: 7, borderRadius: '50%', background: c, display: 'inline-block', flexShrink: 0, animation: status === 'running' || status === 'active' ? 'pulse 2s infinite' : 'none' }}/>
  );
}

function CompanyHeader({ data, isPreview }) {
  return (
    <div style={{
      borderRadius: 20, padding: '20px 22px',
      background: 'linear-gradient(135deg, rgba(0,47,167,0.18), rgba(10,12,15,0.95) 55%)',
      border: '1px solid rgba(93,162,255,0.15)', marginBottom: 18,
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, flexWrap: 'wrap' }}>
        <div style={{
          width: 52, height: 52, borderRadius: 16, flexShrink: 0,
          background: 'linear-gradient(135deg, rgba(93,162,255,0.20), rgba(93,162,255,0.08))',
          border: '1px solid rgba(93,162,255,0.25)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 24,
        }}>🛍</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 4 }}>
            <h1 style={{ fontSize: 22, fontWeight: 800, color: '#fff', letterSpacing: '-0.04em' }}>{data.name}</h1>
            <span style={{
              fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', textTransform: 'uppercase',
              padding: '2px 8px', borderRadius: 999, color: isPreview ? '#ffbd66' : '#46d9a4',
              background: isPreview ? 'rgba(255,189,102,0.10)' : 'rgba(70,217,164,0.10)',
              border: isPreview ? '1px solid rgba(255,189,102,0.20)' : '1px solid rgba(70,217,164,0.20)',
            }}>{isPreview ? 'Preview Mode' : 'Active Graph'}</span>
          </div>
          <div style={{ fontSize: 13, color: 'var(--text-tertiary)', marginBottom: 10 }}>
            <a href="#" style={{ color: 'var(--accent)', textDecoration: 'none' }}>{data.domain}</a>
            {' · '}{data.industry}{' · since '}{data.since}
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            {[
              { label: `${(data.systems || []).length} systems`, color: 'var(--accent)' },
              { label: `${(data.repos || []).length} repos`, color: '#c4b5fd' },
              { label: `${(data.specialists || []).filter(s=>s.status==='active'||s.status==='running').length} agents active`, color: '#46d9a4' },
            ].map(b => (
              <span key={b.label} style={{
                fontSize: 11, fontFamily: 'var(--font-mono)', padding: '3px 10px', borderRadius: 999,
                color: b.color, background: `${b.color}12`, border: `1px solid ${b.color}28`,
              }}>{b.label}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function CompanyScreen() {
  const [company, setCompany] = React.useState(PREVIEW_COMPANY_DATA);
  const [isPreview, setIsPreview] = React.useState(true);
  const [loading, setLoading] = React.useState(false);
  const [activeTab, setActiveTab] = React.useState('overview');
  const tabs = ['overview', 'systems', 'specialists', 'priorities'];

  React.useEffect(() => {
    async function fetchLiveCompanyGraph() {
      setLoading(true);
      try {
        // Attempt to fetch first company or any active session info
        const sessionsRes = await api.listSessions();
        if (sessionsRes?.data?.length > 0) {
          // Let's retrieve matching company details
          const firstId = sessionsRes.data[0].id || 'co_1';
          const graphRes = await api.getCompanyGraph(firstId);
          if (graphRes?.data) {
            const liveData = graphRes.data;
            setCompany({
              name: liveData.company?.name || 'Live Enterprise',
              domain: liveData.company?.domain || 'enterprise.com',
              industry: liveData.company?.business_category || 'Technology',
              since: 'May 2026',
              systems: (liveData.systems || []).map(sys => ({
                name: sys.name,
                category: sys.category || 'Platform',
                status: 'connected',
                icon: sys.icon || '⚙'
              })),
              repos: (liveData.repos || []).map(r => ({
                name: r.name,
                branch: r.default_branch || 'main',
                updated: 'Just now',
                prs: 0
              })),
              environments: [
                { name: 'Production',  url: liveData.company?.domain || 'enterprise.com', status: 'healthy' }
              ],
              specialists: (liveData.specialists || []).map(s => ({
                name: s.name,
                status: s.status || 'idle',
                lastRun: '1m ago',
                icon: s.icon || '🤖'
              })),
              priorities: liveData.company?.goals || [
                'Analyze and optimize technological stack dependencies',
                'Establish isolated execution playbooks for specialists'
              ],
              quickActions: PREVIEW_COMPANY_DATA.quickActions
            });
            setIsPreview(false);
          }
        }
      } catch (err) {
        console.warn("Could not fetch live Company Graph from backend, operating in Offline-first Preview mode.", err);
      } finally {
        setLoading(false);
      }
    }
    fetchLiveCompanyGraph();
  }, []);

  const d = company;

  return (
    <div style={{ padding: '20px 16px 48px', maxWidth: 960, margin: '0 auto' }}>
      <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 10 }}>Company Graph</div>

      <CompanyHeader data={d} isPreview={isPreview}/>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 18, overflowX: 'auto', paddingBottom: 4 }} className="scrollbar-hide">
        {tabs.map(t => (
          <button key={t} onClick={() => setActiveTab(t)} style={{
            padding: '7px 16px', borderRadius: 999, fontSize: 12, fontWeight: 600, cursor: 'pointer',
            textTransform: 'capitalize', transition: 'all 0.15s ease', flexShrink: 0,
            background: activeTab === t ? 'rgba(93,162,255,0.15)' : 'rgba(255,255,255,0.04)',
            border: `1px solid ${activeTab === t ? 'rgba(93,162,255,0.35)' : 'rgba(255,255,255,0.08)'}`,
            color: activeTab === t ? '#fff' : 'var(--text-muted)',
          }}>{t}</button>
        ))}
      </div>

      {activeTab === 'overview' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 14, animation: 'fadeSlideUp 0.3s ease-out' }}>
          {/* Systems */}
          <Card>
            <SectionHeader label="Systems & Tools" icon="⚙"/>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {(d.systems || []).map(sys => (
                <div key={sys.name} style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
                  <span style={{ fontSize: 16, flexShrink: 0 }}>{sys.icon}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{sys.name}</div>
                    <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{sys.category}</div>
                  </div>
                  <StatusDotC status={sys.status}/>
                </div>
              ))}
              {(d.systems || []).length === 0 && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: '10px 0' }}>No systems connected.</div>
              )}
            </div>
          </Card>

          {/* Repos */}
          <Card>
            <SectionHeader label="Repositories" icon="⎇"/>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {(d.repos || []).map(r => (
                <div key={r.name} style={{ padding: '9px 12px', borderRadius: 10, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                    <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.name}</span>
                    {r.prs > 0 && <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--accent)', padding: '1px 6px', borderRadius: 999, background: 'rgba(93,162,255,0.10)', border: '1px solid rgba(93,162,255,0.20)', flexShrink: 0 }}>{r.prs} PRs</span>}
                  </div>
                  <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 2 }}>⎇ {r.branch} · {r.updated}</div>
                </div>
              ))}
              {(d.repos || []).length === 0 && (
                <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: '10px 0' }}>No repositories.</div>
              )}
            </div>

            <SectionHeader label="Environments" icon="🌐" style={{ marginTop: 14 }}/>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {(d.environments || []).map(env => (
                <div key={env.name} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <StatusDotC status={env.status}/>
                  <span style={{ fontSize: 12, fontWeight: 500, color: 'var(--text-secondary)', flex: 1 }}>{env.name}</span>
                  <a href="#" style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textDecoration: 'none' }}>{env.url}</a>
                </div>
              ))}
            </div>
          </Card>

          {/* Quick actions */}
          <Card>
            <SectionHeader label="Quick Actions" icon="⚡"/>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {(d.quickActions || []).map(qa => (
                <button key={qa.label} style={{
                  display: 'flex', alignItems: 'center', gap: 10,
                  padding: '9px 12px', borderRadius: 10, cursor: 'pointer', textAlign: 'left',
                  background: 'rgba(255,255,255,0.025)', border: '1px solid rgba(255,255,255,0.08)',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(93,162,255,0.07)'; e.currentTarget.style.borderColor = 'rgba(93,162,255,0.20)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.025)'; e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)'; }}>
                  <span style={{ fontSize: 16, flexShrink: 0 }}>{qa.icon}</span>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{qa.label}</div>
                    <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{qa.desc}</div>
                  </div>
                  <span style={{ marginLeft: 'auto', color: 'var(--text-muted)', fontSize: 12 }}>›</span>
                </button>
              ))}
            </div>
          </Card>

          {/* Priorities */}
          <Card>
            <SectionHeader label="Priorities" icon="◈"/>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {(d.priorities || []).map((p, i) => (
                <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
                  <span style={{
                    width: 20, height: 20, borderRadius: 6, flexShrink: 0,
                    background: 'rgba(93,162,255,0.12)', border: '1px solid rgba(93,162,255,0.20)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--accent)', fontWeight: 700,
                  }}>{i + 1}</span>
                  <span style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{p}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'specialists' && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 12, animation: 'fadeSlideUp 0.3s ease-out' }}>
          {(d.specialists || []).map(sp => {
            const statusColor = sp.status === 'active' || sp.status === 'running' ? '#5da2ff' : 'var(--text-muted)';
            return (
              <div key={sp.name} style={{
                borderRadius: 16, border: `1px solid ${sp.status !== 'idle' ? `${statusColor}25` : 'rgba(255,255,255,0.09)'}`,
                background: sp.status !== 'idle' ? `${statusColor}05` : 'rgba(255,255,255,0.03)',
                padding: '16px', cursor: 'pointer', transition: 'all 0.2s ease',
              }}
              onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-2px)'; }}
              onMouseLeave={e => { e.currentTarget.style.transform = 'none'; }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                  <div style={{
                    width: 38, height: 38, borderRadius: 12, flexShrink: 0,
                    background: `${statusColor}15`, border: `1px solid ${statusColor}25`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18,
                  }}>{sp.icon || '🤖'}</div>
                  <div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: '#fff' }}>{sp.name}</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginTop: 2 }}>
                      <StatusDotC status={sp.status}/>
                      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: statusColor, textTransform: 'uppercase', letterSpacing: '0.10em' }}>{sp.status}</span>
                    </div>
                  </div>
                </div>
                <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>Last active: {sp.lastRun || '1m ago'}</div>
                <button style={{
                  marginTop: 10, width: '100%', padding: '7px', borderRadius: 9,
                  background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.09)',
                  color: 'var(--text-tertiary)', fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  transition: 'all 0.15s ease',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(93,162,255,0.10)'; e.currentTarget.style.color = 'var(--accent)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.color = 'var(--text-tertiary)'; }}>
                  → Chat with agent
                </button>
              </div>
            );
          })}
        </div>
      )}

      {activeTab === 'systems' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10, animation: 'fadeSlideUp 0.3s ease-out' }}>
          {(d.systems || []).map(sys => (
            <div key={sys.name} style={{
              borderRadius: 14, border: '1px solid rgba(255,255,255,0.09)',
              background: 'rgba(255,255,255,0.03)', padding: '14px 16px',
              display: 'flex', alignItems: 'center', gap: 12,
            }}>
              <span style={{ fontSize: 24, flexShrink: 0 }}>{sys.icon || '⚙'}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 3 }}>
                  <span style={{ fontSize: 14, fontWeight: 700, color: '#fff' }}>{sys.name}</span>
                  <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 999, color: 'var(--text-muted)', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.10)' }}>{sys.category}</span>
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Connected · Last synced: 5 min ago</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                <StatusDotC status={sys.status}/>
                <span style={{ fontSize: 11, color: '#46d9a4' }}>Connected</span>
              </div>
            </div>
          ))}
        </div>
      )}

      {activeTab === 'priorities' && (
        <div style={{ maxWidth: 560, animation: 'fadeSlideUp 0.3s ease-out' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {(d.priorities || []).map((p, i) => (
              <div key={i} style={{
                display: 'flex', alignItems: 'flex-start', gap: 12,
                padding: '14px 16px', borderRadius: 14,
                background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.09)',
              }}>
                <span style={{
                  width: 28, height: 28, borderRadius: 8, flexShrink: 0,
                  background: 'rgba(93,162,255,0.12)', border: '1px solid rgba(93,162,255,0.22)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 13, fontFamily: 'var(--font-mono)', color: 'var(--accent)', fontWeight: 800,
                }}>{i + 1}</span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 8 }}>{p}</div>
                  <button style={{
                    padding: '5px 12px', borderRadius: 8, fontSize: 11, fontWeight: 600, cursor: 'pointer',
                    background: 'rgba(93,162,255,0.10)', border: '1px solid rgba(93,162,255,0.22)',
                    color: 'var(--accent)', transition: 'all 0.15s ease',
                  }}>→ Create task</button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export { CompanyScreen };
export default CompanyScreen;
