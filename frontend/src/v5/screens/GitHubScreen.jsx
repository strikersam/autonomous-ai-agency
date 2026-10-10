import React from 'react';
import * as api from '../../api';

// github.jsx — V5.0 GitHub integration: connect a token, view status, browse repos.
// Wires the previously-unused api.githubStatus / setGithubToken / deleteGithubToken
// / listGithubRepos helpers into the v5 app so the captured token is actually used.

function errText(e, fallback) {
  const detail = e?.response?.data?.detail;
  return detail ? api.fmtErr(detail) : (e?.message || fallback);
}

export default function GitHubScreen() {
  const [status, setStatus]         = React.useState(null);
  const [statusErr, setStatusErr]   = React.useState(null);
  const [loading, setLoading]       = React.useState(true);
  const [token, setToken]           = React.useState('');
  const [saving, setSaving]         = React.useState(false);
  const [actionErr, setActionErr]   = React.useState(null);
  const [repos, setRepos]           = React.useState([]);
  const [reposErr, setReposErr]     = React.useState(null);
  const [reposLoading, setReposLoading] = React.useState(false);
  const [q, setQ]                   = React.useState('');
  const mounted = React.useRef(true);
  React.useEffect(() => () => { mounted.current = false; }, []);

  const loadStatus = React.useCallback(async () => {
    setLoading(true); setStatusErr(null);
    try {
      const { data } = await api.githubStatus();
      if (mounted.current) setStatus(data);
    } catch (e) {
      if (mounted.current) setStatusErr(errText(e, 'Could not load GitHub status.'));
    } finally {
      if (mounted.current) setLoading(false);
    }
  }, []);

  const loadRepos = React.useCallback(async (query = '') => {
    setReposLoading(true); setReposErr(null);
    try {
      const { data } = await api.listGithubRepos(query);
      if (mounted.current) {
        setRepos(data?.repos || (Array.isArray(data) ? data : []));
        if (data?.error) setReposErr(data.error);
      }
    } catch (e) {
      if (mounted.current) setReposErr(errText(e, 'Could not load repositories.'));
    } finally {
      if (mounted.current) setReposLoading(false);
    }
  }, []);

  React.useEffect(() => { loadStatus(); }, [loadStatus]);

  const connected = !!status?.connected;
  React.useEffect(() => { if (connected) loadRepos(''); }, [connected, loadRepos]);

  const connect = async () => {
    if (!token.trim() || saving) return;
    setSaving(true); setActionErr(null);
    try {
      await api.setGithubToken(token.trim());
      if (!mounted.current) return;
      setToken('');
      await loadStatus();
    } catch (e) {
      if (mounted.current) setActionErr(errText(e, 'Could not save the token — check its scope.'));
    } finally {
      if (mounted.current) setSaving(false);
    }
  };

  const disconnect = async () => {
    if (saving) return;
    setSaving(true); setActionErr(null);
    try {
      await api.deleteGithubToken();
      if (!mounted.current) return;
      setRepos([]);
      await loadStatus();
    } catch (e) {
      if (mounted.current) setActionErr(errText(e, 'Could not disconnect.'));
    } finally {
      if (mounted.current) setSaving(false);
    }
  };

  const login = status?.login || status?.github_login;
  const authorized = status?.authorized_repos || [];

  return (
    <div style={{ padding:'20px 16px 48px', maxWidth:880, margin:'0 auto' }}>
      <h1 style={{ fontSize:26, fontWeight:700, color:'var(--text-primary)', letterSpacing:'-0.04em', lineHeight:1.1, marginBottom:4 }}>GitHub</h1>
      <p style={{ fontSize:14, color:'var(--text-tertiary)', lineHeight:1.5, maxWidth:520, marginBottom:20 }}>Connect a personal access token (repo + PR scope) so agents can read repositories and open pull requests on your behalf.</p>

      {/* Connection status / token entry */}
      <div style={{ borderRadius:14, border:'1px solid color-mix(in oklab, var(--ink) 9%, transparent)', background:'color-mix(in oklab, var(--ink) 3%, transparent)', padding:'16px 18px', marginBottom:18 }}>
        {loading ? (
          <div style={{ fontSize:14, color:'var(--text-muted)' }}>Loading GitHub status…</div>
        ) : statusErr ? (
          <div style={{ fontSize:14, color:'var(--danger)' }}>Couldn't load status: {statusErr}</div>
        ) : connected ? (
          <div>
            <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', gap:12, flexWrap:'wrap' }}>
              <div style={{ display:'flex', alignItems:'center', gap:10 }}>
                <span style={{ width:9, height:9, borderRadius:'50%', background:'var(--success)' }}/>
                <div>
                  <div style={{ fontSize:14, fontWeight:700, color:'var(--text-primary)' }}>Connected{login ? ` · ${login}` : ''}</div>
                  <div style={{ fontSize:13, color:'var(--text-muted)' }}>{status?.oauth_enabled ? 'OAuth available' : 'Personal access token'}{authorized.length ? ` · ${authorized.length} authorized repo${authorized.length===1?'':'s'}` : ''}</div>
                </div>
              </div>
              <button onClick={disconnect} disabled={saving} style={{ padding:'9px 16px', borderRadius:10, background:'color-mix(in oklab, var(--danger) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 25%, transparent)', color:'var(--danger)', fontSize:14, fontWeight:700, cursor:saving?'wait':'pointer' }}>{saving ? 'Working…' : 'Disconnect'}</button>
            </div>
          </div>
        ) : (
          <div>
            <div style={{ fontSize:14, fontWeight:700, color:'var(--text-primary)', marginBottom:10 }}>Not connected</div>
            <div style={{ display:'flex', gap:8, alignItems:'center', flexWrap:'wrap' }}>
              <input value={token} onChange={e=>setToken(e.target.value)} type="password" placeholder="ghp_… (repo + PR scope)"
                style={{ flex:1, minWidth:220, padding:'10px 12px', borderRadius:10, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:14, fontVariantNumeric:'tabular-nums', outline:'none' }}/>
              <button onClick={connect} disabled={saving || !token.trim()} style={{ padding:'10px 18px', borderRadius:10, background:'linear-gradient(135deg,var(--accent),var(--accent))', color:'var(--on-accent)', fontSize:14, fontWeight:700, border:'none', cursor:(saving||!token.trim())?'not-allowed':'pointer', opacity:(saving||!token.trim())?0.6:1 }}>{saving ? 'Saving…' : 'Connect'}</button>
              <a href="https://github.com/settings/tokens/new" target="_blank" rel="noreferrer" style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--accent)', textDecoration:'none', whiteSpace:'nowrap' }}>Create token →</a>
            </div>
          </div>
        )}
        {actionErr && <div style={{ marginTop:12, padding:'8px 12px', borderRadius:10, background:'color-mix(in oklab, var(--danger) 10%, transparent)', border:'1px solid color-mix(in oklab, var(--danger) 25%, transparent)', color:'var(--danger)', fontSize:13 }}>{actionErr}</div>}
      </div>

      {/* Repositories */}
      {connected && (
        <div style={{ borderRadius:14, border:'1px solid color-mix(in oklab, var(--ink) 9%, transparent)', background:'color-mix(in oklab, var(--ink) 3%, transparent)', padding:'16px 18px' }}>
          <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between', gap:10, marginBottom:12, flexWrap:'wrap' }}>
            <div style={{ fontSize:14, fontWeight:700, color:'var(--text-primary)' }}>Repositories</div>
            <form onSubmit={e=>{ e.preventDefault(); loadRepos(q); }} style={{ display:'flex', gap:7 }}>
              <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search repos…"
                style={{ padding:'7px 11px', borderRadius:9, background:'color-mix(in oklab, var(--ink) 5%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 10%, transparent)', color:'var(--text-primary)', fontSize:13, fontVariantNumeric:'tabular-nums', outline:'none' }}/>
              <button type="submit" disabled={reposLoading} style={{ padding:'7px 14px', borderRadius:9, background:'color-mix(in oklab, var(--accent) 12%, transparent)', border:'1px solid color-mix(in oklab, var(--accent) 30%, transparent)', color:'var(--accent)', fontSize:13, fontWeight:600, cursor:'pointer' }}>{reposLoading ? '…' : 'Search'}</button>
            </form>
          </div>
          {reposLoading ? (
            <div style={{ fontSize:14, color:'var(--text-muted)', padding:'12px 0' }}>Loading repositories…</div>
          ) : reposErr ? (
            <div style={{ fontSize:14, color:'var(--danger)', padding:'12px 0' }}>{reposErr}</div>
          ) : repos.length === 0 ? (
            <div style={{ fontSize:14, color:'var(--text-muted)', padding:'12px 0' }}>No repositories found.</div>
          ) : (
            <div style={{ display:'flex', flexDirection:'column', gap:7, maxHeight:'52vh', overflowY:'auto' }}>
              {repos.map(r => (
                <a key={r.full_name || r.id} href={r.html_url || '#'} target="_blank" rel="noreferrer"
                  style={{ display:'flex', alignItems:'center', gap:10, padding:'10px 12px', borderRadius:11, background:'color-mix(in oklab, var(--ink) 3%, transparent)', border:'1px solid color-mix(in oklab, var(--ink) 8%, transparent)', textDecoration:'none' }}>
                  <div style={{ flex:1, minWidth:0 }}>
                    <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                      <span style={{ fontSize:14, color:'var(--text-primary)', fontVariantNumeric:'tabular-nums', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{r.full_name || r.name}</span>
                      {r.private && <span style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--text-muted)', background:'color-mix(in oklab, var(--ink) 6%, transparent)', padding:'1px 6px', borderRadius:5 }}>PRIVATE</span>}
                      {r.language && <span style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color:'var(--text-muted)' }}>{r.language}</span>}
                    </div>
                    {r.description && <div style={{ fontSize:13, color:'var(--text-muted)', overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', marginTop:2 }}>{r.description}</div>}
                  </div>
                  <span style={{ color:'var(--text-muted)', fontSize:14, flexShrink:0 }}>→</span>
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export { GitHubScreen };
