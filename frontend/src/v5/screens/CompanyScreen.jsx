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
              { label: `${(data.specialists || []).filter(s => {
                // BUG-27: count active/running specialists AND any specialist
                // with a last_used_at timestamp within the last 24 hours
                if (s.status === 'active' || s.status === 'running') return true;
                const last = s.last_used_at || s.lastRun;
                if (last && last !== '—') {
                  const ms = new Date(last).getTime();
                  if (ms > 0 && (Date.now() - ms) < 24 * 3600 * 1000) return true;
                }
                return false;
              }).length} agents active`, color: '#46d9a4' },
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
  const [downloadingFmt, setDownloadingFmt] = React.useState(null);
  const mounted = React.useRef(true);
  const pollRef = React.useRef(null);
  React.useEffect(() => () => {
    mounted.current = false;
    if (pollRef.current) clearInterval(pollRef.current);
  }, []);
  React.useEffect(() => { setUrl(u => u || defaultUrl || ''); }, [defaultUrl]);

  const loadAudits = React.useCallback(async () => {
    if (!companyId) return;
    try {
      const { data } = await api.listSeoAudits(companyId);
      const list = data.audits || (Array.isArray(data) ? data : []);
      // Skip stale pending audits from a previous session
      const completed = list.find(r => r.status !== 'pending' && r.status !== 'running');
      if (mounted.current && completed) {
        const full = await api.getSeoAudit(companyId, completed.audit_id);
        if (mounted.current) setReport(full.data);
      }
    } catch { /* no audits stored yet */ }
  }, [companyId]);
  React.useEffect(() => { loadAudits(); }, [loadAudits]);

  const _startPolling = (auditId) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const { data } = await api.getSeoAudit(companyId, auditId);
        if (!mounted.current) { clearInterval(pollRef.current); return; }
        if (data.status === 'pending' || data.status === 'running') return; // still going
        clearInterval(pollRef.current);
        pollRef.current = null;
        setRunning(false);
        setReport(data);
        if (data.status === 'success' || data.status === 'partial') {
          setMsg(`Audit complete — health score ${Math.round(data.health_score)}/100, ${data.total_issues} issue(s) found.`);
        } else {
          setErr(data.error || `Audit finished with status: ${data.status}`);
        }
      } catch { /* transient network error — keep polling */ }
    }, 10000);
  };

  const run = async () => {
    setErr(null); setMsg(null); setRunning(true);
    try {
      const body = { website_url: url, fetch_mode: fetchMode, max_pages: Number(maxPages) || 50 };
      if (Number(revenue) > 0) body.monthly_organic_revenue = Number(revenue);
      const { data } = await api.runSeoAudit(companyId, body);
      if (!mounted.current) return;
      // Endpoint now returns immediately with status='pending'.
      // Show the pending stub and start polling until the crawl finishes.
      setReport(data);
      if (data.status === 'pending' || data.status === 'running') {
        setMsg('Crawl started — results will appear automatically (browser crawls can take 3-10 min). You can navigate away and come back.');
        _startPolling(data.audit_id);
      } else {
        setRunning(false);
        if (data.status !== 'success' && data.status !== 'partial') {
          setErr(data.error || `Audit finished with status: ${data.status}`);
        }
      }
    } catch (e) {
      setRunning(false);
      setErr(api.fmtErr(e?.response?.data?.detail) || e?.message || 'Audit failed.');
    }
  };

  const download = async (fmt) => {
    setErr(null);
    setDownloadingFmt(fmt);
    try { await api.downloadSeoExport(companyId, report.audit_id, fmt); }
    catch (e) { setErr('Download failed: ' + (api.fmtErr(e?.response?.data?.detail) || e?.message || '')); }
    finally { if (mounted.current) setDownloadingFmt(null); }
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
          }}>{running ? '⏳ Crawling…' : '▶ Run Audit'}</button>
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 8, lineHeight: 1.5 }}>
          Bot-protected sites (Akamai/Cloudflare) need <b>browser</b> or <b>auto</b> mode (real Chromium via
          browser-use/Playwright). The dollar figure is a transparent <b>model estimate</b>, not a measured loss.
        </div>
        {err && (
          <div style={{ marginTop: 8, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 12, color: '#ff6b7d' }}>{err}</span>
            <button
              onClick={run}
              disabled={running || !url || !companyId}
              style={{ ...dlBtn, background: 'rgba(255,107,125,0.10)', borderColor: 'rgba(255,107,125,0.28)', color: '#ff9aa6' }}
            >↻ Retry</button>
          </div>
        )}
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
              <button
                style={{ ...dlBtn, background: 'rgba(255,189,102,0.14)', borderColor: 'rgba(255,189,102,0.35)', color: '#ffbd66', fontWeight: 700 }}
                onClick={() => download('pdf')}
                disabled={downloadingFmt != null}
                title="CTO-level PDF: executive summary, methodology, pillar deep-dives with $ recommendations, WSJF roadmap and worst-pages appendices"
              >
                {downloadingFmt === 'pdf' ? '⏳ Generating PDF…' : '📄 Generate PDF Report'}
              </button>
              <button style={dlBtn} onClick={() => download('csv')} disabled={downloadingFmt != null}>⬇ CSV (findings)</button>
              <button style={dlBtn} onClick={() => download('issues')} disabled={downloadingFmt != null}>⬇ CSV (issues)</button>
              <button style={dlBtn} onClick={() => download('urls')} disabled={downloadingFmt != null}>⬇ CSV (URLs)</button>
              <button style={dlBtn} onClick={() => download('markdown')} disabled={downloadingFmt != null}>⬇ Markdown report</button>
              <button style={dlBtn} onClick={() => download('json')} disabled={downloadingFmt != null}>⬇ JSON</button>
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

function exportSystemsCSV(systems, companyName) {
  const headers = ['Name', 'Category', 'Confidence', 'Detection Methods', 'Version'];
  const rows = (systems || []).map(s => [
    s.name || s.app_name || '',
    s.category || '',
    s.confidence ? `${Math.round(s.confidence * 100)}%` : '',
    Array.isArray(s.detectionMethods) ? s.detectionMethods.join('|') : (s.source || ''),
    s.version || ''
  ]);
  const csv = [headers, ...rows]
    .map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))
    .join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = `${companyName || 'scan'}-technologies.csv`;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}

function Skeleton({ width = '100%', height = 16, style = {} }) {
  return (
    <div style={{
      width, height, borderRadius: 6,
      background: 'linear-gradient(90deg, var(--color-surface-2, rgba(255,255,255,0.04)) 25%, var(--color-surface-3, rgba(255,255,255,0.08)) 50%, var(--color-surface-2, rgba(255,255,255,0.04)) 75%)',
      backgroundSize: '200% 100%',
      animation: 'shimmer 1.5s infinite',
      ...style
    }} />
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
        confidence: ds.confidence ?? null,
        detectionMethods: (ds.evidence || []).map(e => e.type).filter(Boolean),
        version: ds.version || null,
        isDetected: true,
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
      id: s.id || s.specialist_id || s.name || s.role,
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
        <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Skeleton height={32} width="40%" />
          <Skeleton height={16} />
          <Skeleton height={16} width="70%" />
          <Skeleton height={200} style={{ marginTop: 8 }} />
          <div style={{ display: 'flex', gap: 12 }}>
            <Skeleton height={120} style={{ flex: 1 }} />
            <Skeleton height={120} style={{ flex: 1 }} />
            <Skeleton height={120} style={{ flex: 1 }} />
          </div>
        </div>
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
              <div key={sp.id} style={{
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

      {!loadingCompany && activeTab === 'systems' && (() => {
        const allSystems = d.systems || [];
        // Group by category
        const grouped = {};
        allSystems.forEach(sys => {
          const cat = sys.category || 'Other';
          if (!grouped[cat]) grouped[cat] = [];
          grouped[cat].push(sys);
        });
        const cats = Object.keys(grouped).sort();
        const totalDetected = allSystems.filter(s => s.isDetected).length;
        const totalConnected = allSystems.filter(s => !s.isDetected).length;
        const catColorMap = {
          CMS: '#c4b5fd', CRM: '#5da2ff', analytics: '#46d9a4',
          payment_gateway: '#ffbd66', email_service: '#ff6b7d',
          marketing_automation: '#f97316', search: '#7c9dff',
          auth: '#46d9a4', api_gateway: '#5da2ff', shipping: '#ffbd66',
          OMS: '#c4b5fd', PIM: '#f97316', DAM: '#5da2ff',
          ERP: '#ffbd66', HRM: '#ff6b7d', LMS: '#7c9dff',
          support: '#46d9a4', chat: '#c4b5fd', ai_ml: '#5da2ff',
          database: '#ffbd66', cache: '#ff6b7d', billing: '#f97316',
        };
        function confidenceColor(c) {
          if (c == null) return 'var(--text-muted)';
          if (c >= 0.8) return '#46d9a4';
          if (c >= 0.5) return '#ffbd66';
          return '#ff6b7d';
        }
        function methodBadge(method) {
          const colors = { html: '#5da2ff', dns: '#46d9a4', ssl: '#c4b5fd', headers: '#ffbd66', script: '#f97316', cookie: '#ff6b7d', meta: '#7c9dff' };
          const c = colors[method] || 'var(--text-muted)';
          return (
            <span key={method} style={{ fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', textTransform: 'uppercase', padding: '1px 5px', borderRadius: 4, color: c, background: `${c}18`, border: `1px solid ${c}30` }}>{method}</span>
          );
        }
        return (
          <div style={{ animation: 'fadeSlideUp 0.3s ease-out' }}>
            {/* Summary bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14, flexWrap: 'wrap' }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: '#fff' }}>{allSystems.length} systems detected</span>
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>across {cats.length} categories</span>
              {totalDetected > 0 && (
                <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', padding: '2px 8px', borderRadius: 999, color: '#c4b5fd', background: 'rgba(196,181,253,0.10)', border: '1px solid rgba(196,181,253,0.20)' }}>
                  {totalDetected} auto-detected
                </span>
              )}
              {totalConnected > 0 && (
                <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', padding: '2px 8px', borderRadius: 999, color: '#46d9a4', background: 'rgba(70,217,164,0.10)', border: '1px solid rgba(70,217,164,0.20)' }}>
                  {totalConnected} connected
                </span>
              )}
              <button onClick={() => exportSystemsCSV(allSystems, d?.name)}
                style={{ marginLeft: 'auto', fontSize: 12, padding: '4px 10px', borderRadius: 6,
                  background: 'var(--accent)', color: '#fff', border: 'none', cursor: 'pointer' }}>
                Export CSV
              </button>
            </div>
            {/* Per-category groups */}
            {cats.map(cat => {
              const catColor = catColorMap[cat] || 'var(--accent)';
              const items = grouped[cat];
              return (
                <div key={cat} style={{ marginBottom: 16 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 8 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 2, background: catColor, flexShrink: 0 }}/>
                    <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: catColor, letterSpacing: '0.16em', textTransform: 'uppercase' }}>{cat.replace(/_/g, ' ')}</span>
                    <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>({items.length})</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {items.map(sys => (
                      <div key={sys.id} style={{
                        borderRadius: 12, border: '1px solid rgba(255,255,255,0.08)',
                        background: 'rgba(255,255,255,0.025)', padding: '10px 14px',
                        display: 'flex', alignItems: 'center', gap: 10,
                      }}>
                        <span style={{ fontSize: 18, flexShrink: 0 }}>{sys.icon || '⚙'}</span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginBottom: 3 }}>
                            <span style={{ fontSize: 13, fontWeight: 700, color: '#fff' }}>{sys.name}</span>
                            {sys.version && <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>v{sys.version}</span>}
                          </div>
                          {sys.isDetected && (sys.detectionMethods || []).length > 0 && (
                            <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                              {[...new Set(sys.detectionMethods)].slice(0, 5).map(m => methodBadge(m))}
                            </div>
                          )}
                        </div>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
                          {sys.confidence != null && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                              <div style={{ width: 40, height: 3, borderRadius: 999, background: 'rgba(255,255,255,0.08)', overflow: 'hidden' }}>
                                <div style={{ width: `${Math.round(sys.confidence * 100)}%`, height: '100%', background: confidenceColor(sys.confidence), borderRadius: 999 }}/>
                              </div>
                              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: confidenceColor(sys.confidence) }}>{Math.round(sys.confidence * 100)}%</span>
                            </div>
                          )}
                          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                            <StatusDotC status={sys.status}/>
                            <span style={{ fontSize: 10, color: sys.status === 'inactive' ? '#ff6b7d' : '#46d9a4' }}>{sys.status === 'inactive' ? 'Inactive' : sys.isDetected ? 'Detected' : 'Connected'}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
            {allSystems.length === 0 && (
              <div style={{ padding: '32px 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
                No systems detected. Run a scan from the company header to discover your tech stack.
              </div>
            )}
          </div>
        );
      })()}

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

export default CompanyScreen;
