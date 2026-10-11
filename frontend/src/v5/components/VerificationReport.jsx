import React from 'react';
import { Icon } from '../AppShell';

/**
 * VerificationReport — rule 49's proof, shown on every task.
 *
 * A task is done only when a verifier that did not do the work returns PASS
 * or PASS+NOTES. This shows that verifier's report (what was checked, what
 * was broken, what got fixed, the evidence) and lets a person record their
 * own verdict. Image evidence (screenshots) renders inline.
 */

const TONE = { PASS: 'var(--success)', 'PASS+NOTES': 'var(--warning)', FAIL: 'var(--danger)' };
const LABEL = { PASS: 'Passed', 'PASS+NOTES': 'Passed with notes', FAIL: 'Failed' };
const IMAGE = /^https?:\/\/\S+\.(png|jpe?g|gif|webp|avif)(\?\S*)?$/i;

function List({ title, items, tone }) {
  if (!items || items.length === 0) return null;
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>
        {title} <span style={{ color: 'var(--text-muted)', fontWeight: 500 }}>({items.length})</span>
      </div>
      <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
        {items.map((it, i) => (
          <li key={i} style={{ display: 'flex', gap: 8, fontSize: 14, lineHeight: 1.45, color: 'var(--text-primary)' }}>
            <span aria-hidden="true" style={{ width: 6, height: 6, borderRadius: '50%', background: tone, flexShrink: 0, marginTop: 8 }} />
            <span style={{ overflowWrap: 'anywhere' }}>{it}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Evidence({ items }) {
  if (!items || items.length === 0) return null;
  const images = items.filter(e => IMAGE.test(e));
  const rest = items.filter(e => !IMAGE.test(e));
  return (
    <div style={{ marginTop: 12 }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 6 }}>Evidence</div>
      {images.length > 0 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 8, marginBottom: 8 }}>
          {images.map(src => (
            <a key={src} href={src} target="_blank" rel="noreferrer noopener" title="Open screenshot">
              <img src={src} alt="Verification screenshot" loading="lazy"
                style={{ width: '100%', aspectRatio: '16 / 10', objectFit: 'cover', borderRadius: 8, border: '1px solid var(--border)' }} />
            </a>
          ))}
        </div>
      )}
      <List title="Records" items={rest} tone="var(--text-muted)" />
    </div>
  );
}

export default function VerificationReport({ task, onRecord, busy = false }) {
  const v = task?.verification;
  const [mode, setMode] = React.useState(null); // null | 'PASS' | 'FAIL'
  const [notes, setNotes] = React.useState('');
  const waiting = !v && task?.status === 'in_review';
  // A FAIL is retired when the work re-opens; keep its findings visible.
  const lastFail = !v ? [...(task?.execution_log || [])].reverse()
    .find(e => e.event_type === 'verification_retired' && e.metadata?.verification?.verdict === 'FAIL')
    ?.metadata.verification : null;

  const submit = async () => {
    const lines = notes.split('\n').map(s => s.trim()).filter(Boolean);
    const ok = await onRecord(mode === 'FAIL'
      ? { verdict: 'FAIL', defects_found: lines, notes: '' }
      : { verdict: lines.length ? 'PASS+NOTES' : 'PASS', checked: ['Reviewed the result myself'], notes: lines.join('\n') });
    if (ok !== false) { setMode(null); setNotes(''); }
  };

  return (
    <section aria-labelledby="verification-title" style={{ padding: '14px 20px', borderTop: '1px solid var(--border-soft)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <h3 id="verification-title" style={{ fontSize: 15, fontWeight: 650 }}>Verification</h3>
        {v ? (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 14, fontWeight: 600, color: TONE[v.verdict] }}>
            <Icon name={v.verdict === 'FAIL' ? 'AlertCircle' : 'Check'} size={16} />
            {LABEL[v.verdict] || v.verdict}
          </span>
        ) : (
          <span style={{ fontSize: 14, color: 'var(--text-muted)' }}>{waiting ? 'Waiting for an independent check' : 'Not verified yet'}</span>
        )}
      </div>
      {lastFail && (
        <div style={{ marginTop: 8, padding: '10px 12px', borderRadius: 8, background: 'color-mix(in oklab, var(--danger) 8%, transparent)' }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>Last check failed ({lastFail.verifier}). Being reworked; it will be checked again.</div>
          <List title="What was broken" items={lastFail.defects_found} tone="var(--danger)" />
        </div>
      )}
      {v && (
        <p style={{ fontSize: 13, color: 'var(--text-muted)', marginTop: 2 }}>
          Checked by {v.verifier === 'agent:judge' ? 'the reviewing agent (it did not do the work)' : v.verifier}
        </p>
      )}
      {waiting && (
        <p style={{ fontSize: 14, color: 'var(--text-tertiary)', marginTop: 6, maxWidth: '62ch' }}>
          Your team finished this, but nothing has confirmed it works yet. Check the result, then pass or fail it.
        </p>
      )}
      {v && (
        <>
          <List title="What was checked" items={v.checked} tone="var(--accent)" />
          <List title="What was broken" items={v.defects_found} tone="var(--danger)" />
          <List title="What got fixed" items={v.fixed} tone="var(--success)" />
          <Evidence items={v.evidence} />
          {v.notes && <p style={{ marginTop: 10, fontSize: 14, color: 'var(--text-tertiary)', whiteSpace: 'pre-wrap' }}>{v.notes}</p>}
        </>
      )}

      {onRecord && (mode === null ? (
        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          <button type="button" className="app-button-secondary" disabled={busy} onClick={() => setMode('PASS')}>It works, pass it</button>
          <button type="button" className="app-button-ghost" disabled={busy} onClick={() => setMode('FAIL')}>Something is wrong</button>
        </div>
      ) : (
        <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <label htmlFor="verify-notes" style={{ fontSize: 14, fontWeight: 600 }}>
            {mode === 'FAIL' ? 'What is wrong? One problem per line.' : 'Notes (optional, one per line)'}
          </label>
          <textarea id="verify-notes" rows={3} value={notes} onChange={e => setNotes(e.target.value)} />
          <div style={{ display: 'flex', gap: 8 }}>
            <button type="button" className="app-button-primary" disabled={busy || (mode === 'FAIL' && !notes.trim())} onClick={submit}>
              {mode === 'FAIL' ? 'Send back for rework' : 'Mark as verified'}
            </button>
            <button type="button" className="app-button-ghost" onClick={() => { setMode(null); setNotes(''); }}>Cancel</button>
          </div>
        </div>
      ))}
    </section>
  );
}

export { VerificationReport };
