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

function healthColor(score) {
  return score >= 80 ? '#46d9a4' : score >= 60 ? '#ffbd66' : '#ff6b7d';
}

const PRIORITY_COLOR = { high: '#ff6b7d', medium: '#ffbd66', low: '#8aa0b6' };

// SEO / GEO / AIO audit panel — runs a real crawl, shows the health score,
// pillar scores, revenue-at-risk (model estimate, clearly labelled), the full
// findings table, downloadable exports, and a one-click delegate-to-task-board.
function SeoAuditPanel({ companyId, defaultUrl }) {
  const [url, setUrl] = React.useState(defaultUrl || '');
  const [fetchMode, setFetchMode] = React.useState('auto');
  const [revenue, setRevenue] = React.useState('');
  const [maxPages, setMaxPages] = React.useState(50);
  const [report, setReport] = React.useState(null);
  const [running, setRunning] = React.useState(false);
  const [err, setErr] = React.useState(null);
  const [msg, setMsg] = React.useState(null);
  const mounted = React.useRef(true);
  React.useEffect(() => () => { mounted.current = false; }, []);
  React.useEffect(() => { setUrl(u => u || defaultUrl || ''); }, [defaultUrl]);

  const loadAudits = React.useCallback(async () => {
    if (!companyId) return;
    try {
      const { data } = await api.listSeoAudits(companyId);
      const list = data.audits || (Array.isArray(data) ? data : []);
      if (mounted.current && list.length) {
        const full = await api.getSeoAudit(companyId, list[0].audit_id);
        if (mounted.current) setReport(full.data);
      }
    } catch { /* no audits stored yet */ }
  }, [companyId]);
  React.useEffect(() => { loadAudits(); }, [loadAudits]);

  const run = async () => {
    setErr(null); setMsg(null); setRunning(true);
    try {
      const body = { website_url: url, fetch_mode: fetchMode, max_pages: Number(maxPages) || 50 };
      if (Number(revenue) > 0) body.monthly_organic_revenue = Number(revenue);
      const { data } = await api.runSeoAudit(companyId, body);
      if (!mounted.current) return;
      setReport(data);
      if (data.status !== 'success') setErr(data.error || `Audit finished with status: ${data.status}`);
    } catch (e) {
      setErr(api.fmtErr(e?.response?.data?.detail) || e?.message || 'Audit failed.');
    } finally { if (mounted.current) setRunning(false); }
  };

  const download = async (fmt) => {
    try { await api.downloadSeoExport(companyId, report.audit_id, fmt); }
    catch (e) { setErr('Download failed: ' + (api.fmtErr(e?.response?.data?.detail) || e?.message || '')); }
  };

  const delegate = async () => {
    setErr(null); setMsg(null);
    try {
      const { data } = await api.delegateSeoFindings(companyId, report.audit_id, { min_priority: 'medium' });
      setMsg(`Created ${data.created} prioritized task(s) on the board.`);
    } catch (e) { setErr('Delegate failed: ' + (api.fmtErr(e?.response?.data?.detail) || e?.message || '')); }
  };

  const rows = report?.rows || [];
  const pillars = report?.pillar_scores || {};
  const baseline = report?.monthly_organic_revenue || 0;
  const loss = report?.estimated_monthly_revenue_loss || 0;
  const sharePct = baseline > 0 ? (loss / baseline * 100) : 0;
  const inputStyle = {
    padding: '8px 10px', borderRadius: 8, fontSize: 12,
    background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.10)',
    color: 'var(--text-primary)', outline: 'none',
  };
  const dlBtn = {
    padding: '6px 12px', borderRadius: 8, fontSize: 11, fontWeight: 600, cursor: 'pointer',
    background: 'rgba(93,162,255,0.10)', border: '1px solid rgba(93,162,255,0.22)', color: 'var(--accent)',
  };

  return (
    <div style={{ animation: 'fadeSlideUp 0.3s ease-out', display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Run controls */}
      <Card>
        <SectionHeader label="Run SEO / GEO / AIO Audit" icon="🔍"/>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'flex-end' }}>
          <div style={{ flex: '2 1 240px', display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>WEBSITE URL</label>
            <input value={url} onChange={e => setUrl(e.target.value)} placeholder="https://www.example.com" style={inputStyle}/>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <label style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>FETCH MODE</label>
            <select value={fetchMode} onChange={e => setFetchMode(e.target.value)} style={inputStyle}>
              <option value="auto">auto (browser on block)</option>
              <option value="http">http (fast)</option>
              <option value="browser">browser (bot-bypass)</option>
            </select>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, width: 110 }}>
            <label style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>MAX PAGES</label>
            <input type="number" value={maxPages} onChange={e => setMaxPages(e.target.value)} style={inputStyle}/>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, width: 170 }}>
            <label style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>MONTHLY ORGANIC $ (opt.)</label>
            <input type="number" value={revenue} onChange={e => setRevenue(e.target.value)} placeholder="e.g. 1000000" style={inputStyle}/>
          </div>
          <button onClick={run} disabled={running || !url || !companyId} style={{
            padding: '9px 18px', borderRadius: 8, fontSize: 12, fontWeight: 700,
            cursor: running ? 'wait' : 'pointer',
            background: running ? 'rgba(93,162,255,0.20)' : 'var(--accent)',
            border: '1px solid rgba(93,162,255,0.40)', color: running ? 'var(--accent)' : '#04101f',
            opacity: (!url || !companyId) ? 0.5 : 1,
          }}>{running ? 'Crawling…' : '▶ Run Audit'}</button>
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 8, lineHeight: 1.5 }}>
          Bot-protected sites (Akamai/Cloudflare) need <b>browser</b> or <b>auto</b> mode (real Chromium via
          browser-use/Playwright). The dollar figure is a transparent <b>model estimate</b>, not a measured loss.
        </div>
        {err && <div style={{ marginTop: 8, fontSize: 12, color: '#ff6b7d' }}>{err}</div>}
        {msg && <div style={{ marginTop: 8, fontSize: 12, color: '#46d9a4' }}>{msg}</div>}
      </Card>

      {!report && !running && (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: '10px 0' }}>
          No audit yet — run one above to see findings, scores and downloadable reports.
        </div>
      )}

      {report && (
        <>
          {/* Scores + revenue */}
          <Card>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 18, alignItems: 'center' }}>
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 34, fontWeight: 800, color: healthColor(report.health_score), lineHeight: 1 }}>{report.health_score}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>HEALTH / 100</div>
              </div>
              <div style={{ height: 40, width: 1, background: 'rgba(255,255,255,0.10)' }}/>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                <div><b style={{ color: '#fff' }}>{report.pages_crawled}</b> pages crawled · <b style={{ color: '#fff' }}>{report.total_issues}</b> issue occurrences</div>
                <div style={{ marginTop: 3 }}>Status: <b style={{ color: report.status === 'success' ? '#46d9a4' : '#ffbd66' }}>{report.status}</b> · {report.website_url}</div>
              </div>
              {baseline > 0 && (
                <div style={{ marginLeft: 'auto', textAlign: 'right' }}>
                  <div style={{ fontSize: 22, fontWeight: 800, color: '#ffbd66' }}>${Number(loss).toLocaleString()}/mo</div>
                  <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>est. revenue at risk · {sharePct.toFixed(1)}% of baseline (model)</div>
                </div>
              )}
            </div>
            {/* Pillar scores */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(90px, 1fr))', gap: 8, marginTop: 14 }}>
              {Object.entries(pillars).map(([p, s]) => (
                <div key={p} style={{ padding: '8px 10px', borderRadius: 10, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)', textAlign: 'center' }}>
                  <div style={{ fontSize: 16, fontWeight: 700, color: healthColor(s) }}>{s}</div>
                  <div style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', textTransform: 'uppercase' }}>{p}</div>
                </div>
              ))}
            </div>
            {baseline > 0 && (
              <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 10, lineHeight: 1.5 }}>
                ⓘ Revenue-at-risk is the supplied ${Number(baseline).toLocaleString()}/mo baseline × an at-risk share
                derived from finding severity, type and page-coverage via a diminishing-returns curve (35% cap).
                It is a prioritisation signal — not a guaranteed amount.
              </div>
            )}
            {/* Downloads + delegate */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 14 }}>
              <button style={dlBtn} onClick={() => download('csv')}>⬇ CSV (findings)</button>
              <button style={dlBtn} onClick={() => download('issues')}>⬇ CSV (issues)</button>
              <button style={dlBtn} onClick={() => download('urls')}>⬇ CSV (URLs)</button>
              <button style={dlBtn} onClick={() => download('markdown')}>⬇ Markdown report</button>
              <button style={dlBtn} onClick={() => download('json')}>⬇ JSON</button>
              <button style={{ ...dlBtn, marginLeft: 'auto', background: 'rgba(70,217,164,0.10)', borderColor: 'rgba(70,217,164,0.25)', color: '#46d9a4' }} onClick={delegate}>→ Delegate to task board</button>
            </div>
          </Card>

          {/* Findings table */}
          <Card>
            <SectionHeader label={`Findings (${rows.length} types)`} icon="◈"/>
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
                <thead>
                  <tr style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', textAlign: 'left' }}>
                    <th style={{ padding: '6px 8px' }}>Priority</th>
                    <th style={{ padding: '6px 8px' }}>Issue</th>
                    <th style={{ padding: '6px 8px' }}>Pillar</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right' }}>URLs</th>
                    <th style={{ padding: '6px 8px', textAlign: 'right' }}>%</th>
                    {baseline > 0 && <th style={{ padding: '6px 8px', textAlign: 'right' }}>$/mo</th>}
                    <th style={{ padding: '6px 8px' }}>Fix</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, 60).map((r, i) => (
                    <tr key={i} style={{ borderTop: '1px solid rgba(255,255,255,0.06)' }}>
                      <td style={{ padding: '6px 8px' }}>
                        <span style={{ color: PRIORITY_COLOR[r.issue_priority] || 'var(--text-muted)', fontWeight: 700, textTransform: 'capitalize' }}>{r.issue_priority}</span>
                      </td>
                      <td style={{ padding: '6px 8px', color: 'var(--text-secondary)' }}>{r.issue_name}</td>
                      <td style={{ padding: '6px 8px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{r.pillar}</td>
                      <td style={{ padding: '6px 8px', textAlign: 'right', color: 'var(--text-secondary)' }}>{r.urls_affected}</td>
                      <td style={{ padding: '6px 8px', textAlign: 'right', color: 'var(--text-muted)' }}>{r.percent_of_total}%</td>
                      {baseline > 0 && <td style={{ padding: '6px 8px', textAlign: 'right', color: '#ffbd66' }}>{Number(r.estimated_monthly_revenue_loss || 0).toLocaleString()}</td>}
                      <td style={{ padding: '6px 8px' }}>{r.auto_fixable ? <span style={{ color: '#46d9a4' }}>auto</span> : <span style={{ color: 'var(--text-muted)' }}>—</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {rows.length > 60 && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 8 }}>Showing top 60 of {rows.length}. Download CSV/Markdown for the full report.</div>}
              {rows.length === 0 && <div style={{ fontSize: 12, color: 'var(--text-muted)', textAlign: 'center', padding: '10px 0' }}>No findings recorded.</div>}
            </div>
          </Card>
        </>
      )}
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
  const tabs = ['overview', 'systems', 'specialists', 'priorities', 'seo'];
  const tabLabel = (t) => (t === 'seo' ? 'SEO Audit' : t);
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
      ...(graph?.systems || []).map((sys, i) => ({
        id: sys.id || `sys-${i}`,
        name: sys.name || sys.system_type || 'System',
        category: sys.category || sys.system_type || 'Platform',
        status: sys.status || 'connected',
        icon: sys.icon || '⚙',
      })),
      ...(graph?.detected_systems || []).map((ds, i) => ({
        id: ds.id || `det-${i}`,
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
            }}>{tabLabel(t)}</button>
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
                <div key={sys.id} style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
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
            <div key={sys.id} style={{
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
                <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{sys.status === 'inactive' ? 'Inactive' : 'Connected'} · Last synced: 5 min ago</div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                <StatusDotC status={sys.status}/>
                <span style={{ fontSize: 11, color: sys.status === 'inactive' ? '#ff6b7d' : '#46d9a4' }}>{sys.status === 'inactive' ? 'Inactive' : 'Connected'}</span>
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

      {!loadingCompany && activeTab === 'seo' && (
        <SeoAuditPanel companyId={selectedCompanyId} defaultUrl={d.domain ? (/^https?:\/\//i.test(d.domain) ? d.domain : `https://${d.domain}`) : ''}/>
      )}
    </div>
  );
}

export { CompanyScreen };
export default CompanyScreen;
