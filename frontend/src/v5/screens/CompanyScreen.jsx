/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import * as api from '../../api';

// company.jsx — Company Graph / Operating Context screen

// localStorage key where Onboarding persists the created company id so this
// screen can load the real graph. (Shared literal — see OnboardingScreen.jsx.)
export const COMPANY_ID_KEY = 'v5_company_id';

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
            {data.industry ? ` · ${data.industry}` : ''}{data.since ? ` · since ${data.since}` : ''}
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
  const storedId = (() => { try { return localStorage.getItem(COMPANY_ID_KEY); } catch { return null; } })();
  const [companies, setCompanies] = React.useState([]);
  const [selectedCompanyId, setSelectedCompanyId] = React.useState(storedId || '');
  const [company, setCompany] = React.useState(null);
  const [graph, setGraph] = React.useState(null);
  const [specialists, setSpecialists] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [loadingCompany, setLoadingCompany] = React.useState(false);
  const [error, setError] = React.useState(null);
  const [activeTab, setActiveTab] = React.useState('overview');
  const tabs = ['overview', 'systems', 'specialists', 'priorities'];
  const mounted = React.useRef(true);
  React.useEffect(() => () => { mounted.current = false; }, []);

  // Load company list on mount
  React.useEffect(() => {
    (async () => {
      try {
        const { data } = await api.listCompanies();
        if (!mounted.current) return;
        const list = data.companies || [];
        setCompanies(list);
        // Auto-select: prefer stored company, then first company, else empty
        if (!selectedCompanyId && list.length > 0) {
          const match = storedId ? list.find(c => c.id === storedId) : null;
          const id = match ? match.id : list[0].id;
          setSelectedCompanyId(id);
          try { localStorage.setItem(COMPANY_ID_KEY, id); } catch {}
        }
        if (list.length === 0) setLoading(false);
      } catch (e) {
        // Fall back to stored company ID if listing fails
        if (storedId) setSelectedCompanyId(storedId);
        setLoading(false);
      }
    })();
    // Mount-only auto-select; re-trigger not desired.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load selected company details
  React.useEffect(() => {
    if (!selectedCompanyId) { setLoading(false); return; }
    (async () => {
      setLoadingCompany(true); setError(null);
      try {
        const { data } = await api.getCompany(selectedCompanyId);
        if (!mounted.current) return;
        setCompany(data.company || data);
        setGraph(data.graph || null);
        // Persist selection
        try { localStorage.setItem(COMPANY_ID_KEY, selectedCompanyId); } catch {}
        try {
          const sp = await api.listSpecialists(selectedCompanyId);
          if (mounted.current) setSpecialists(sp.data?.specialists || (Array.isArray(sp.data) ? sp.data : []));
        } catch { /* specialists are optional */ }
      } catch (e) {
        if (!mounted.current) return;
        const detail = e?.response?.data?.detail;
        setError(detail ? api.fmtErr(detail) : (e?.message || 'Could not load the company graph.'));
      } finally {
        if (mounted.current) { setLoadingCompany(false); setLoading(false); }
      }
    })();
  }, [selectedCompanyId]);

  // Build the view-model from real backend data only (no preview fallback).
  const displayName = (company?.name || 'Company').replace(/^www\./i, '');
  const d = company ? {
    name: displayName,
    domain: company.domain || '',
    industry: company.business_category || company.industry || '',
    since: '',
    systems: [
      ...(graph?.systems || []).map(sys => ({
        name: sys.name || sys.system_type || 'System',
        category: sys.category || sys.system_type || 'Platform',
        status: sys.status || 'connected',
        icon: sys.icon || '⚙',
      })),
      ...(graph?.detected_systems || []).map(ds => ({
        name: ds.name || 'Detected System',
        category: ds.system_type || 'Platform',
        status: ds.is_active ? 'connected' : 'inactive',
        icon: '🔍',
      })),
    ],
    repos: (graph?.repos || company.repos || []).map(r => ({
      name: r.name || r.full_name || r.url || 'repo',
      branch: r.default_branch || r.branch || 'main',
      updated: r.updated || '—',
      prs: r.prs || 0,
    })),
    environments: company.domain ? [{ name: 'Production', url: company.domain, status: 'healthy' }] : [],
    specialists: specialists.map(s => ({
      name: s.name || s.role || 'Specialist',
      status: s.status || 'idle',
      lastRun: s.last_used_at || s.lastRun || '—',
      icon: s.icon || '🤖',
    })),
    priorities: company.goals || company.priorities || [],
  } : null;

  // Company selector handler
  const handleCompanyChange = (id) => {
    setSelectedCompanyId(id);
  };

  // Loading / empty / error states
  if (loading && companies.length === 0) {
    return (
      <div style={{ padding: '20px 16px 48px', maxWidth: 960, margin: '0 auto' }}>
        <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 10 }}>Company Graph</div>
        <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: 14 }}>Loading companies...</div>
      </div>
    );
  }
  if (!selectedCompanyId && companies.length === 0) {
    return (
      <div style={{ padding: '20px 16px 48px', maxWidth: 960, margin: '0 auto' }}>
        <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 10 }}>Company Graph</div>
        <div style={{ padding: '32px', textAlign: 'center', borderRadius: 18, border: '1px dashed rgba(255,255,255,0.14)', color: 'var(--text-tertiary)' }}>
          <div style={{ fontSize: 30, marginBottom: 10 }}>🏢</div>
          <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>No companies found</div>
          <div style={{ fontSize: 13, lineHeight: 1.6, maxWidth: 420, margin: '0 auto' }}>Complete the <strong>Onboarding</strong> flow to scan your site and build your company graph. It will show up here once created.</div>
        </div>
      </div>
    );
  }
  if (error || (!d && !loadingCompany)) {
    return (
      <div style={{ padding: '20px 16px 48px', maxWidth: 960, margin: '0 auto' }}>
        <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 10 }}>Company Graph</div>
        <div style={{ padding: '28px', textAlign: 'center', borderRadius: 18, border: '1px solid rgba(255,107,125,0.20)', background: 'rgba(255,107,125,0.05)', color: '#ff6b7d' }}>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 6 }}>Could not load the company graph</div>
          <div style={{ fontSize: 13, lineHeight: 1.6, color: 'var(--text-tertiary)' }}>{error || 'The company could not be found.'}</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px 16px 48px', maxWidth: 960, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10, marginBottom: 12 }}>
        <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', letterSpacing: '0.18em', textTransform: 'uppercase' }}>Company Graph</div>
        {/* Company selector */}
        {companies.length > 1 && (
          <select
            value={selectedCompanyId}
            onChange={(e) => handleCompanyChange(e.target.value)}
            style={{
              padding: '6px 12px', borderRadius: 10, fontSize: 12, fontWeight: 600,
              background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)',
              color: 'var(--text-primary)', fontFamily: 'var(--font-main)', cursor: 'pointer',
              outline: 'none', maxWidth: 280,
            }}
          >
            {companies.map(c => (
              <option key={c.id} value={c.id}>{c.name || c.domain || c.id}</option>
            ))}
          </select>
        )}
      </div>

      {loadingCompany && <div style={{ padding: '20px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>Loading company data...</div>}

      {!loadingCompany && <CompanyHeader data={d} isPreview={false}/>}

      {/* Tabs — gated behind !loadingCompany to prevent stale data flash */}
      {!loadingCompany && (
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
      )}

      {!loadingCompany && activeTab === 'overview' && (
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

      {!loadingCompany && activeTab === 'specialists' && (
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

      {!loadingCompany && activeTab === 'systems' && (
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

      {!loadingCompany && activeTab === 'priorities' && (
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
