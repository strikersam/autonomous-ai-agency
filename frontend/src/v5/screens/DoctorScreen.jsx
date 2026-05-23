/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';


// doctor.jsx — Doctor / Diagnostics screen

const CHECKS = [
  {
    id: 'runtime',
    category: 'Runtime',
    label: 'Agent runtime reachable',
    status: 'pass',
    detail: 'Hermes v2 responds in 38ms. Circuit breaker closed. 3 concurrent jobs.',
    action: null,
  },
  {
    id: 'github',
    category: 'GitHub',
    label: 'GitHub repo connected',
    status: 'pass',
    detail: 'strikersam/local-llm-server · branch master · last push 2h ago.',
    action: null,
  },
  {
    id: 'ci-parity',
    category: 'CI',
    label: 'CI / local test parity',
    status: 'warn',
    detail: 'Local: 47 pass, 0 fail. CI (GitHub Actions): 44 pass, 3 fail.\n3 tests pass locally but fail in CI — likely environment variable mismatch in ANTHROPIC_API_KEY.',
    action: { label: 'Run parity check', id: 'parity' },
    explanation: 'Why did CI fail but local pass? The CI runner doesn\'t have ANTHROPIC_API_KEY set in repository secrets. Tests that call the Anthropic API fall back to a null value and raise AuthenticationError. Set the secret in GitHub → Settings → Secrets and re-run.',
  },
  {
    id: 'dashboard-api',
    category: 'API',
    label: 'Dashboard API endpoints',
    status: 'pass',
    detail: '/v4/status · /v1/models · /v1/chat/completions all respond 200 OK.',
    action: null,
  },
  {
    id: 'langfuse',
    category: 'Observability',
    label: 'Langfuse traces connected',
    status: 'fail',
    detail: 'Connection refused on port 3100. Langfuse container not running or LANGFUSE_HOST misconfigured.',
    action: { label: 'Retry connection', id: 'langfuse' },
    explanation: 'Why isn\'t Langfuse available? LANGFUSE_HOST in your .env points to localhost:3100 but the container reports it isn\'t bound to that port. Check `docker compose ps` — if langfuse is unhealthy, restart with `docker compose restart langfuse`.',
  },
  {
    id: 'scheduler',
    category: 'Scheduler',
    label: 'Improvement loop running',
    status: 'pass',
    detail: '4 standing jobs active. Last CEO cycle: 14 min ago. Next scan in 5h 46m.',
    action: null,
  },
  {
    id: 'ollama',
    category: 'Models',
    label: 'Ollama local models available',
    status: 'warn',
    detail: '2 models pulled (qwen3-coder:7b, deepseek-r1:32b). qwen3-coder:30b is configured but not pulled yet.',
    action: { label: 'Pull missing models', id: 'ollama' },
    explanation: 'qwen3-coder:30b is referenced in MODEL_MAP but hasn\'t been pulled. Run `docker exec llm-server-ollama ollama pull qwen3-coder:30b` or use the Setup Wizard to pull it from the UI.',
  },
];

const QA_EXAMPLES = [
  { q: 'Why didn\'t this task run?', a: 'Task t-005 was classified but not queued — no agent matched its required capability "ratelimit_api". Assign it to Dev Agent and it will be picked up in the next CEO cycle (≈ 4 min).' },
  { q: 'Why did CI fail but local pass?', a: 'ANTHROPIC_API_KEY is missing from GitHub Actions secrets. 3 tests call the Anthropic API and fail with AuthenticationError in CI. Set the secret and re-run the workflow.' },
];

function statusIcon(s) {
  if (s === 'pass') return { icon: '✓', color: '#46d9a4', bg: 'rgba(70,217,164,0.08)', border: 'rgba(70,217,164,0.18)' };
  if (s === 'warn') return { icon: '⚠', color: '#ffbd66', bg: 'rgba(255,189,102,0.08)', border: 'rgba(255,189,102,0.20)' };
  return { icon: '✕', color: '#ff6b7d', bg: 'rgba(255,107,125,0.08)', border: 'rgba(255,107,125,0.18)' };
}

function CheckRow({ check, onRerun, expanded, onToggle }) {
  const st = statusIcon(check.status);
  const [running, setRunning] = React.useState(false);

  const handleRerun = (e) => {
    e.stopPropagation();
    setRunning(true);
    setTimeout(() => setRunning(false), 2200);
    onRerun && onRerun(check.id);
  };

  return (
    <div style={{ borderRadius: 14, border: `1px solid ${st.border}`, background: st.bg, overflow: 'hidden', transition: 'all 0.2s ease' }}>
      <button onClick={onToggle} style={{
        width: '100%', display: 'flex', alignItems: 'flex-start', gap: 12,
        padding: '13px 16px', background: 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left',
      }}>
        {/* Status badge */}
        <div style={{
          width: 28, height: 28, borderRadius: 8, flexShrink: 0,
          background: `${st.color}20`, border: `1px solid ${st.color}35`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 13, color: st.color, fontWeight: 700, marginTop: 1,
        }}>{running ? <div style={{ width: 12, height: 12, border: `2px solid ${st.color}40`, borderTopColor: st.color, borderRadius: '50%', animation: 'spin 0.8s linear infinite' }}/> : st.icon}</div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap', marginBottom: 2 }}>
            <span style={{ fontSize: 13, fontWeight: 700, color: '#fff' }}>{check.label}</span>
            <span style={{
              fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', textTransform: 'uppercase',
              padding: '2px 7px', borderRadius: 999,
              color: 'var(--text-muted)', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.10)',
            }}>{check.category}</span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)', lineHeight: 1.5, whiteSpace: 'pre-line' }}>{check.detail}</div>
        </div>

        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
          {check.action && (
            <button onClick={handleRerun} style={{
              padding: '5px 12px', borderRadius: 8, fontSize: 11, fontWeight: 600, cursor: 'pointer',
              background: `${st.color}18`, border: `1px solid ${st.color}35`, color: st.color,
              transition: 'all 0.15s ease', whiteSpace: 'nowrap',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = `${st.color}28`; }}
            onMouseLeave={e => { e.currentTarget.style.background = `${st.color}18`; }}>
              {running ? 'Running…' : check.action.label}
            </button>
          )}
          {check.explanation && (
            <span style={{ fontSize: 14, color: 'var(--text-muted)', transition: 'transform 0.2s', display: 'inline-block', transform: expanded ? 'rotate(90deg)' : 'none' }}>›</span>
          )}
        </div>
      </button>

      {/* Explanation panel */}
      {expanded && check.explanation && (
        <div style={{
          padding: '0 16px 14px 56px',
          animation: 'fadeSlideUp 0.2s ease-out',
        }}>
          <div style={{
            padding: '12px 14px', borderRadius: 12,
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
          }}>
            <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 6 }}>Plain-language explanation</div>
            <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.65 }}>{check.explanation}</div>
          </div>
        </div>
      )}
    </div>
  );
}

function QAPanel() {
  const [input, setInput] = React.useState('');
  const [answer, setAnswer] = React.useState(null);
  const [loading, setLoading] = React.useState(false);

  const askQuestion = (q) => {
    const found = QA_EXAMPLES.find(e => e.q === q);
    setLoading(true);
    setAnswer(null);
    setTimeout(() => {
      setLoading(false);
      setAnswer(found ? found.a : 'I don\'t have enough context to answer that yet. Run a full preflight check first to collect diagnostics.');
    }, 1000);
  };

  return (
    <div style={{ padding: '16px', borderRadius: 16, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 12 }}>Ask the Doctor</div>
      <div style={{ display: 'flex', gap: 8, marginBottom: 10, flexWrap: 'wrap' }}>
        {QA_EXAMPLES.map(qa => (
          <button key={qa.q} onClick={() => { setInput(qa.q); askQuestion(qa.q); }} style={{
            padding: '6px 12px', borderRadius: 8, fontSize: 12, cursor: 'pointer', textAlign: 'left',
            background: 'rgba(93,162,255,0.07)', border: '1px solid rgba(93,162,255,0.18)',
            color: 'var(--text-tertiary)', transition: 'all 0.15s ease',
          }}
          onMouseEnter={e => { e.currentTarget.style.color = '#fff'; }}
          onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-tertiary)'; }}>
            "{qa.q}"
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 8 }}>
        <input value={input} onChange={e => setInput(e.target.value)}
          placeholder="Ask why something failed…"
          onKeyDown={e => { if (e.key === 'Enter' && input.trim()) askQuestion(input); }}
          style={{
            flex: 1, padding: '10px 14px', borderRadius: 12,
            background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.10)',
            color: '#fff', fontSize: 13, outline: 'none', fontFamily: 'var(--font-main)',
          }}
          onFocus={e => e.target.style.borderColor = 'rgba(93,162,255,0.45)'}
          onBlur={e => e.target.style.borderColor = 'rgba(255,255,255,0.10)'}/>
        <button onClick={() => input.trim() && askQuestion(input)} style={{
          padding: '10px 16px', borderRadius: 12, fontSize: 13, fontWeight: 700, cursor: 'pointer',
          background: 'var(--accent)', color: '#06111f', border: 'none',
        }}>Ask</button>
      </div>

      {loading && (
        <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 8, color: 'var(--text-muted)', fontSize: 13 }}>
          <div style={{ width: 14, height: 14, border: '2px solid rgba(93,162,255,0.25)', borderTopColor: 'var(--accent)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }}/>
          Analyzing diagnostics…
        </div>
      )}
      {answer && !loading && (
        <div style={{
          marginTop: 12, padding: '12px 14px', borderRadius: 12,
          background: 'rgba(93,162,255,0.06)', border: '1px solid rgba(93,162,255,0.15)',
          fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.65,
          animation: 'fadeSlideUp 0.25s ease-out',
        }}>
          {answer}
        </div>
      )}
    </div>
  );
}

function DoctorScreen() {
  const [checks] = React.useState(CHECKS);
  const [expanded, setExpanded] = React.useState('ci-parity');
  const [running, setRunning] = React.useState(false);
  const [lastRun, setLastRun] = React.useState('2 min ago');

  const passCount = checks.filter(c => c.status === 'pass').length;
  const warnCount = checks.filter(c => c.status === 'warn').length;
  const failCount = checks.filter(c => c.status === 'fail').length;

  const runAll = () => {
    setRunning(true);
    setTimeout(() => { setRunning(false); setLastRun('just now'); }, 2800);
  };

  return (
    <div style={{ padding: '20px 16px 48px', maxWidth: 780, margin: '0 auto' }}>
      {/* Header */}
      <div style={{ marginBottom: 22 }}>
        <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 6 }}>Diagnostics</div>
        <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10 }}>
          <div>
            <h1 style={{ fontSize: 26, fontWeight: 800, color: '#fff', letterSpacing: '-0.04em', lineHeight: 1.1, marginBottom: 4 }}>Doctor</h1>
            <p style={{ fontSize: 14, color: 'var(--text-tertiary)', lineHeight: 1.5 }}>Preflight checks, health status, and plain-language diagnostics.</p>
          </div>
          <button onClick={runAll} disabled={running} style={{
            display: 'inline-flex', alignItems: 'center', gap: 7,
            padding: '10px 20px', borderRadius: 999, fontSize: 13, fontWeight: 700, cursor: 'pointer',
            background: running ? 'rgba(93,162,255,0.12)' : 'rgba(93,162,255,0.15)',
            border: '1px solid rgba(93,162,255,0.30)', color: running ? 'var(--text-muted)' : 'var(--accent)',
            transition: 'all 0.2s ease',
          }}>
            {running ? <div style={{ width: 12, height: 12, border: '2px solid rgba(93,162,255,0.2)', borderTopColor: 'var(--accent)', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }}/> : '↺'}
            {running ? 'Running checks…' : 'Run all checks'}
          </button>
        </div>
      </div>

      {/* Score bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px',
        borderRadius: 14, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)',
        marginBottom: 16, flexWrap: 'wrap',
      }}>
        {[
          { label: 'Passing', count: passCount, color: '#46d9a4' },
          { label: 'Warnings', count: warnCount, color: '#ffbd66' },
          { label: 'Failing', count: failCount, color: '#ff6b7d' },
        ].map((s, i) => (
          <React.Fragment key={s.label}>
            {i > 0 && <span style={{ color: 'rgba(255,255,255,0.15)', fontSize: 12 }}>·</span>}
            <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <span style={{ width: 7, height: 7, borderRadius: '50%', background: s.color }}/>
              <span style={{ fontSize: 13, fontWeight: 700, color: s.color }}>{s.count}</span>
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{s.label}</span>
            </div>
          </React.Fragment>
        ))}
        <span style={{ marginLeft: 'auto', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>Last run: {lastRun}</span>
      </div>

      {/* Checks */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 22 }}>
        {checks.map(check => (
          <CheckRow key={check.id} check={check}
            expanded={expanded === check.id}
            onToggle={() => setExpanded(expanded === check.id ? null : check.id)}
          />
        ))}
      </div>

      {/* Q&A */}
      <QAPanel/>
    </div>
  );
}

export { DoctorScreen };
export default DoctorScreen;
