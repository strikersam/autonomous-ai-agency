import React from 'react';
import * as api from '../../api';
import { COMPANY_ID_KEY } from './CompanyScreen';

// ExecutiveAdvisoryScreen — ask the C-suite (agent/executive_advisory.py) a
// business question and see each executive's view plus one synthesised
// recommendation. Consulting is admin-only on the backend (it spends provider
// budget); non-admins can still see who is on the C-suite.

const MONO = 'var(--font-mono)';

function SectionHeader({ label, icon }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 10 }}>
      {icon && <span style={{ fontSize: 14 }}>{icon}</span>}
      <span style={{ fontSize: 11, fontFamily: MONO, color: 'var(--text-muted)', letterSpacing: '0.15em', textTransform: 'uppercase' }}>{label}</span>
    </div>
  );
}

function Card({ children, style = {} }) {
  return (
    <div style={{ borderRadius: 16, border: '1px solid rgba(255,255,255,0.09)', background: 'rgba(255,255,255,0.03)', padding: '14px 16px', ...style }}>
      {children}
    </div>
  );
}

export default function ExecutiveAdvisoryScreen({ isAdmin }) {
  const [execs, setExecs] = React.useState([]);
  const [question, setQuestion] = React.useState('');
  const [roles, setRoles] = React.useState([]);            // [] → auto-route
  const [ground, setGround] = React.useState(true);
  const [remember, setRemember] = React.useState(true);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState('');
  const [result, setResult] = React.useState(null);

  const companyId = React.useMemo(() => {
    try { return localStorage.getItem(COMPANY_ID_KEY); } catch { return null; }
  }, []);

  React.useEffect(() => {
    let alive = true;
    api.listExecutives()
      .then((r) => { if (alive) setExecs(r.data?.executives || []); })
      .catch(() => { /* persona list is best-effort */ });
    return () => { alive = false; };
  }, []);

  const toggleRole = (role) => {
    setRoles((prev) => prev.includes(role) ? prev.filter((r) => r !== role) : [...prev, role]);
  };

  const consult = React.useCallback(async () => {
    const q = question.trim();
    if (!q || loading) return;
    setLoading(true); setError(''); setResult(null);
    try {
      const payload = { question: q, ground, remember };
      if (companyId) payload.company_id = companyId;
      if (roles.length) payload.roles = roles;
      const r = await api.consultExecutives(payload);
      setResult(r.data);
    } catch (e) {
      setError(api.fmtErr(e?.response?.data?.detail) || e?.message || 'Consult failed');
    } finally {
      setLoading(false);
    }
  }, [question, ground, remember, companyId, roles, loading]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, maxWidth: 900 }}>
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 600, margin: 0 }}>C-Suite Advisory</h2>
        <p style={{ fontSize: 13, color: 'var(--text-muted)', margin: '4px 0 0' }}>
          Ask your executive team a business question. Answers are grounded in live web research and prior advice
          {companyId ? ', with this company’s profile as context' : ''}.
        </p>
      </div>

      {/* Personas */}
      <Card>
        <SectionHeader label="The C-Suite" icon="🏛️" />
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {execs.length === 0 && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Loading executives…</span>}
          {execs.map((e) => {
            const on = roles.includes(e.role);
            return (
              <button
                key={e.role}
                type="button"
                onClick={() => toggleRole(e.role)}
                title={e.focus}
                style={{
                  fontSize: 12, padding: '6px 10px', borderRadius: 10, cursor: 'pointer',
                  border: `1px solid ${on ? 'var(--accent)' : 'rgba(255,255,255,0.14)'}`,
                  background: on ? 'var(--accent)' : 'transparent',
                  color: on ? '#0b0b0f' : 'var(--text)',
                }}
              >
                {e.title}
              </button>
            );
          })}
        </div>
        <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '8px 0 0' }}>
          {roles.length ? `Consulting ${roles.length} selected.` : 'None selected — the question is auto-routed to the relevant executives.'}
        </p>
      </Card>

      {/* Ask */}
      <Card>
        <SectionHeader label="Ask" icon="💬" />
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. Should we raise prices on the pro tier, and how would competitors respond?"
          rows={3}
          style={{
            width: '100%', resize: 'vertical', borderRadius: 12, padding: '10px 12px',
            border: '1px solid rgba(255,255,255,0.14)', background: 'rgba(0,0,0,0.25)',
            color: 'var(--text)', fontSize: 14, fontFamily: 'inherit',
          }}
        />
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 14, marginTop: 10 }}>
          <label style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <input type="checkbox" checked={ground} onChange={(e) => setGround(e.target.checked)} /> Web research
          </label>
          <label style={{ fontSize: 12, display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer' }}>
            <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} /> Use memory
          </label>
          <div style={{ flex: 1 }} />
          <button
            type="button"
            onClick={consult}
            disabled={!isAdmin || loading || !question.trim()}
            style={{
              fontSize: 13, fontWeight: 600, padding: '8px 16px', borderRadius: 10,
              border: 'none', cursor: (!isAdmin || loading || !question.trim()) ? 'not-allowed' : 'pointer',
              background: (!isAdmin || loading || !question.trim()) ? 'rgba(255,255,255,0.12)' : 'var(--accent)',
              color: (!isAdmin || loading || !question.trim()) ? 'var(--text-muted)' : '#0b0b0f',
            }}
          >
            {loading ? 'Consulting…' : 'Consult the C-Suite'}
          </button>
        </div>
        {!isAdmin && (
          <p style={{ fontSize: 11, color: 'var(--text-muted)', margin: '8px 0 0' }}>
            Consulting requires an admin account — it starts real provider work.
          </p>
        )}
        {error && (
          <p style={{ fontSize: 12, color: '#ff8080', margin: '8px 0 0' }}>{error}</p>
        )}
      </Card>

      {/* Result */}
      {result && (
        <>
          {result.answer && (
            <Card style={{ borderColor: 'var(--accent)' }}>
              <SectionHeader label="Recommendation" icon="⭐" />
              <div style={{ fontSize: 14, lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>{result.answer}</div>
            </Card>
          )}

          <Card>
            <SectionHeader label={`Executive views (${result.opinions?.length || 0})`} icon="🧑‍💼" />
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {(result.opinions || []).map((o) => (
                <div key={o.role} style={{ borderTop: '1px solid rgba(255,255,255,0.07)', paddingTop: 10 }}>
                  <div style={{ fontSize: 12, fontFamily: MONO, color: 'var(--text-muted)', letterSpacing: '0.08em', marginBottom: 4 }}>{o.title}</div>
                  {o.error
                    ? <div style={{ fontSize: 12, color: '#ff8080' }}>Unavailable: {o.error}</div>
                    : <div style={{ fontSize: 13, lineHeight: 1.5, whiteSpace: 'pre-wrap' }}>{o.text}</div>}
                </div>
              ))}
            </div>
          </Card>

          {result.grounding?.sources?.length > 0 && (
            <Card>
              <SectionHeader label="Research sources" icon="🔎" />
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, lineHeight: 1.7 }}>
                {result.grounding.sources.map((u, i) => (
                  <li key={i}>
                    <a href={u} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>{u}</a>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
