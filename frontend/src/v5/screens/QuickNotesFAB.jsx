/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import * as api from '../../api';


// quicknotes.jsx — Floating Quick Notes capture (accessible from any screen)
// iPhone Shortcut → POST /v1/quick-notes → queue → Dev Agent implements → git push

const QUEUED_NOTES = [
  { id: 'qn-1', text: 'Add skeleton loading to the dashboard widgets', type: 'text', status: 'queued',     ago: '2h ago' },
  { id: 'qn-2', text: 'https://github.com/nicholasgasior/nextjs-starter',  type: 'url',  status: 'processing', ago: '4h ago' },
  { id: 'qn-3', text: 'Fix the mobile nav overlap on iPhone 14 safe area', type: 'text', status: 'done',       ago: '8h ago' },
];

function NoteStatusPill({ status }) {
  const map = {
    queued:     { color: '#7c9dff', bg: 'rgba(124,157,255,0.10)', label: 'Queued' },
    processing: { color: '#ffbd66', bg: 'rgba(255,189,102,0.10)', label: 'In progress', pulse: true },
    done:       { color: '#46d9a4', bg: 'rgba(70,217,164,0.08)',  label: 'Done' },
  };
  const s = map[status] || map.queued;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.10em', textTransform: 'uppercase',
      padding: '2px 7px', borderRadius: 999, color: s.color, background: s.bg,
      border: `1px solid ${s.color}28`,
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: s.color, animation: s.pulse ? 'pulse 1.5s infinite' : 'none' }}/>
      {s.label}
    </span>
  );
}

function QuickNotes({ onClose }) {
  const [input, setInput] = React.useState('');
  const [notes, setNotes] = React.useState([]);
  const [sending, setSending] = React.useState(false);
  const [sent, setSent] = React.useState(false);
  const [submitErr, setSubmitErr] = React.useState(null);
  const textareaRef = React.useRef(null);

  // Load recent quick-note tasks from the backend
  const loadNotes = React.useCallback(async () => {
    try {
      const { data } = await api.listTasks({ source: 'quick_note', limit: 10 });
      const raw = data.tasks || data.items || (Array.isArray(data) ? data : []);
      setNotes(raw.map(t => ({
        id:     t.id || t._id,
        text:   t.instruction || t.title || t.description || '(no text)',
        type:   /^https?:\/\//.test(t.instruction || '') ? 'url' : 'text',
        status: t.status === 'completed' ? 'done' : t.status === 'running' ? 'processing' : 'queued',
        ago:    t.created_at ? _relTime(t.created_at) : 'recently',
      })));
    } catch {
      // Silently fall back — don't break the UI
      setNotes(QUEUED_NOTES);
    }
  }, []);

  React.useEffect(() => {
    loadNotes();
    setTimeout(() => textareaRef.current?.focus(), 100);
  }, [loadNotes]);

  const _relTime = (iso) => {
    const d = Date.now() - new Date(iso).getTime();
    if (d < 60000)  return `${Math.round(d/1000)}s ago`;
    if (d < 3600000) return `${Math.round(d/60000)}m ago`;
    if (d < 86400000) return `${Math.round(d/3600000)}h ago`;
    return `${Math.round(d/86400000)}d ago`;
  };

  const isUrl = t => /^https?:\/\//.test(t.trim());

  const submit = async () => {
    if (!input.trim() || sending) return;
    setSending(true); setSubmitErr(null);
    try {
      await api.createTask({
        instruction: input.trim(),
        source: 'quick_note',
        priority: 'normal',
      });
      setInput('');
      setSent(true);
      setTimeout(() => setSent(false), 2000);
      await loadNotes();
    } catch (e) {
      setSubmitErr(e?.response?.data?.detail || e.message || 'Could not save note.');
    } finally { setSending(false); }
  };

  const handleKey = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } };

  return (
    <div style={{
      position: 'fixed', bottom: 80, right: 16, zIndex: 200,
      width: 'min(380px, calc(100vw - 32px))',
      borderRadius: 20,
      background: 'rgba(12,14,18,0.97)',
      border: '1px solid rgba(255,255,255,0.12)',
      boxShadow: '0 24px 60px rgba(0,0,0,0.5)',
      backdropFilter: 'blur(20px)',
      animation: 'fadeSlideUp 0.25s ease-out',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 16px 12px',
        borderBottom: '1px solid rgba(255,255,255,0.08)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{
            width: 26, height: 26, borderRadius: 8,
            background: 'linear-gradient(135deg, rgba(93,162,255,0.20), rgba(93,162,255,0.08))',
            border: '1px solid rgba(93,162,255,0.25)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13,
          }}>📝</div>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: '#fff' }}>Quick Notes</div>
            <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>iPhone Shortcut → Dev Agent → git push</div>
          </div>
        </div>
        <button onClick={onClose} style={{
          width: 28, height: 28, borderRadius: 8, display: 'flex', alignItems: 'center', justifyContent: 'center',
          background: 'rgba(255,255,255,0.05)', border: 'none', cursor: 'pointer', color: 'var(--text-muted)',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.10)'; e.currentTarget.style.color = '#fff'; }}
        onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; e.currentTarget.style.color = 'var(--text-muted)'; }}>
          ✕
        </button>
      </div>

      {/* Composer */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid rgba(255,255,255,0.07)' }}>
        <div style={{
          display: 'flex', alignItems: 'flex-end', gap: 8,
          padding: '10px 12px',
          background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.10)',
          borderRadius: 14, transition: 'border-color 0.2s',
        }}>
          <textarea ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Paste a URL or type an idea — Dev Agent will implement it…"
            rows={2}
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none', resize: 'none',
              fontSize: 13, color: '#fff', fontFamily: 'var(--font-main)', lineHeight: 1.5,
            }}
          />
          <button onClick={submit} disabled={!input.trim() || sending} style={{
            width: 30, height: 30, borderRadius: 9, flexShrink: 0,
            background: input.trim() && !sending ? 'var(--accent)' : 'rgba(255,255,255,0.08)',
            border: 'none', cursor: input.trim() && !sending ? 'pointer' : 'not-allowed',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 0.2s ease',
          }}>
            {sending
              ? <div style={{ width: 12, height: 12, borderRadius: '50%', border: '2px solid rgba(255,255,255,0.2)', borderTopColor: '#fff', animation: 'spin 0.8s linear infinite' }}/>
              : <span style={{ fontSize: 14, color: input.trim() ? '#06111f' : 'var(--text-muted)' }}>↑</span>
            }
          </button>
        </div>
        {sent && (
          <div style={{ marginTop: 8, fontSize: 11, color: '#46d9a4', fontFamily: 'var(--font-mono)', animation: 'fadeSlideUp 0.2s ease-out' }}>
            ✓ Queued — Dev Agent will implement this shortly.
          </div>
        )}
        <div style={{ marginTop: 7, fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
          <span>Also available via iPhone Shortcut → POST /v1/quick-notes</span>
          <span>⏎ send</span>
        </div>
      </div>

      {/* Queue */}
      <div style={{ maxHeight: 220, overflowY: 'auto' }} className="scrollbar-hide">
        <div style={{ padding: '8px 14px 4px', fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.12em', textTransform: 'uppercase' }}>Queue ({notes.length})</div>
        {notes.map(note => (
          <div key={note.id} style={{
            display: 'flex', alignItems: 'flex-start', gap: 8, padding: '9px 14px',
            borderBottom: '1px solid rgba(255,255,255,0.04)',
          }}>
            <span style={{ fontSize: 13, flexShrink: 0, marginTop: 1 }}>{note.type === 'url' ? '🔗' : '📝'}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: 12, color: note.status === 'done' ? 'var(--text-muted)' : 'var(--text-secondary)',
                lineHeight: 1.4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                textDecoration: note.status === 'done' ? 'line-through' : 'none',
              }}>{note.text}</div>
              <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: 2 }}>{note.ago}</div>
            </div>
            <NoteStatusPill status={note.status}/>
          </div>
        ))}
      </div>
    </div>
  );
}

// Floating trigger button — rendered outside AppShell so it's always on top
function QuickNotesFAB({ visible }) {
  const [open, setOpen] = React.useState(false);
  if (!visible) return null;
  return (
    <>
      {open && <QuickNotes onClose={() => setOpen(false)}/>}
      <button onClick={() => setOpen(o => !o)} style={{
        position: 'fixed', bottom: 88, right: 16, zIndex: 100,
        width: 44, height: 44, borderRadius: '50%',
        background: open ? 'rgba(93,162,255,0.25)' : 'rgba(14,17,22,0.92)',
        border: `1px solid ${open ? 'rgba(93,162,255,0.45)' : 'rgba(255,255,255,0.15)'}`,
        boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
        backdropFilter: 'blur(12px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        cursor: 'pointer', fontSize: 18, transition: 'all 0.2s ease',
        transform: open ? 'scale(1.05)' : 'scale(1)',
      }}
      title="Quick Notes"
      onMouseEnter={e => { if (!open) e.currentTarget.style.background = 'rgba(93,162,255,0.15)'; }}
      onMouseLeave={e => { if (!open) e.currentTarget.style.background = 'rgba(14,17,22,0.92)'; }}>
        {open ? <span style={{ fontSize: 14, color: 'var(--accent)' }}>✕</span> : '📝'}
      </button>
    </>
  );
}

export { QuickNotesFAB, QuickNotes };
export default QuickNotesFAB;
