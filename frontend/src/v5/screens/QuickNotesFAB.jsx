/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import { Icon } from '../AppShell';
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
    queued:     { color: 'var(--accent)', bg: 'color-mix(in oklab, var(--accent) 10%, transparent)', label: 'Queued' },
    processing: { color: 'var(--warning)', bg: 'color-mix(in oklab, var(--warning) 10%, transparent)', label: 'In progress', pulse: true },
    done:       { color: 'var(--success)', bg: 'color-mix(in oklab, var(--success) 8%, transparent)',  label: 'Done' },
    failed:     { color: 'var(--danger)', bg: 'color-mix(in oklab, var(--danger) 10%, transparent)', label: 'Failed' },
  };
  const s = map[status] || map.queued;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize:13, fontVariantNumeric:'tabular-nums',
      padding: '2px 7px', borderRadius: 999, color: s.color, background: s.bg,
      border: `1px solid color-mix(in oklab, ${s.color} 16%, transparent)`,
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
  const [ghConnected, setGhConnected] = React.useState(false);
  const textareaRef = React.useRef(null);
  // BUG-17: mounted guard so setTimeout(() => setSent(false), ...) doesn't
  // update state after QuickNotes unmounts (e.g. user closes the FAB).
  const mountedRef = React.useRef(true);
  React.useEffect(() => () => { mountedRef.current = false; }, []);

  // Check if GitHub is connected (enables full implement→PR→merge pipeline)
  const checkGh = React.useCallback(async () => {
    try {
      const { data } = await api.getGithubStatus();
      setGhConnected(data?.connected || false);
    } catch {
      setGhConnected(false);
    }
  }, []);

  // Load recent quick-note tasks from the backend
  const loadNotes = React.useCallback(async () => {
    try {
      // Try the quick-notes endpoint first, fall back to tasks
      try {
        const { data } = await api.listQuickNotes();
        const raw = data.notes || [];
        if (raw.length > 0) {
          setNotes(raw.map(n => ({
            id:     n.note_id || n.id,
            text:   n.url || n.instruction || '(no text)',
            type:   'url',
            status: n.status === 'done' ? 'done' : n.status === 'processing' ? 'processing' : n.status === 'failed' ? 'failed' : 'queued',
            ago:    n.added_at ? _relTime(n.added_at) : 'recently',
          })));
          return;
        }
      } catch { /* fall through to tasks */ }

      const { data } = await api.listTasks({ tag: 'quick_note', limit: 10 });
      const raw = data.tasks || data.items || (Array.isArray(data) ? data : []);
      setNotes(raw.map(t => ({
        id:     t.id || t._id,
        text:   t.description || t.title || '(no text)',
        type:   /^https?:\/\//.test(t.description || t.title || '') ? 'url' : 'text',
        status: t.status === 'done' ? 'done' : t.status === 'in_progress' ? 'processing' : t.status === 'failed' ? 'failed' : 'queued',
        ago:    t.created_at ? _relTime(t.created_at) : 'recently',
      })));
    } catch {
      // Silently fall back — don't break the UI
      setNotes(QUEUED_NOTES);
    }
  }, []);

  React.useEffect(() => {
    checkGh();
    loadNotes();
    setTimeout(() => textareaRef.current?.focus(), 100);
  }, [loadNotes, checkGh]);

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
      if (ghConnected && isUrl(input)) {
        // GitHub connected + URL → create GH issue for full implement→PR→merge pipeline
        const { data } = await api.createQuickNote({
          url: input.trim(),
          instruction: input.trim(),
        });
        if (data.channel === 'github' || data.channel === 'local') {
          setInput('');
          setSent(true);
          setTimeout(() => { if (mountedRef.current) setSent(false); }, 3000);
        }
      } else {
        // Plain-text idea, or no GitHub → create internal task
        const text = input.trim();
        await api.createTask({
          title: text.length > 120 ? `${text.slice(0, 117)}...` : text,
          description: text,
          tags: ['quick_note'],
          priority: 'medium',
        });
        setInput('');
        setSent(true);
        setTimeout(() => { if (mountedRef.current) setSent(false); }, 2000);
      }
      await loadNotes();
    } catch (e) {
      setSubmitErr(api.fmtErr(e?.response?.data?.detail) || e.message || 'Could not save note.');
    } finally { setSending(false); }
  };

  const handleKey = e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); submit(); } };

  return (
    <div className="shell-popover" role="dialog" aria-label="Quick notes">
      <div className="shell-popover-head">
        <div style={{ minWidth: 0 }}>
          <div className="shell-popover-title">Quick notes</div>
          <div style={{ fontSize:14, color: 'var(--text-muted)', lineHeight: 1.4 }}>
            {ghConnected ? 'Each note becomes a GitHub issue your agents build, review and merge.' : 'Jot an idea or paste a link. Your developer agent picks it up.'}
          </div>
        </div>
        <button type="button" className="shell-icon-btn" aria-label="Close quick notes" onClick={onClose}>
          <Icon name="X" size={18}/>
        </button>
      </div>

      {/* Composer */}
      <div style={{ padding: '12px 14px', borderBottom: '1px solid color-mix(in oklab, var(--ink) 7%, transparent)' }}>
        <div style={{
          display: 'flex', alignItems: 'flex-end', gap: 8,
          padding: '10px 12px',
          background: 'color-mix(in oklab, var(--ink) 4%, transparent)', border: '1px solid color-mix(in oklab, var(--ink) 10%, transparent)',
          borderRadius: 14, transition: 'border-color 0.2s',
        }}>
          <textarea ref={textareaRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKey}
            aria-label="New note" placeholder="Paste a link or describe an idea…"
            rows={2}
            style={{
              flex: 1, background: 'transparent', border: 'none', outline: 'none', resize: 'none', padding: 0, boxShadow: 'none',
              fontSize: 15, color: 'var(--text-primary)', fontFamily: 'var(--font-main)', lineHeight: 1.5,
            }}
          />
          <button type="button" aria-label="Send note" onClick={submit} disabled={!input.trim() || sending} style={{
            width: 36, height: 36, borderRadius: 8, flexShrink: 0,
            background: input.trim() && !sending ? 'var(--accent)' : 'color-mix(in oklab, var(--ink) 8%, transparent)',
            border: 'none', cursor: input.trim() && !sending ? 'pointer' : 'not-allowed',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 0.2s ease',
          }}>
            {sending
              ? <div style={{ width: 12, height: 12, borderRadius: '50%', border: '2px solid color-mix(in oklab, var(--ink) 20%, transparent)', borderTopColor:'currentColor', animation: 'spin 0.8s linear infinite' }}/>
              : <Icon name="ArrowUp" size={16} style={{ color: input.trim() ? 'var(--on-accent)' : 'var(--text-muted)' }}/>
            }
          </button>
        </div>
        {sent && (
          <div style={{ marginTop: 8, fontSize:13, color: 'var(--success)', fontVariantNumeric:'tabular-nums', animation: 'fadeSlideUp 0.2s ease-out' }}>
            {ghConnected ? 'GitHub issue created — agents will implement, review, and auto-merge when green.' : 'Queued — Dev Agent will implement this shortly.'}
          </div>
        )}
        <div style={{ marginTop: 7, fontSize:13, fontVariantNumeric:'tabular-nums', color: 'var(--text-muted)', display: 'flex', justifyContent: 'space-between' }}>
          <span>Also works from an iPhone Shortcut</span>
          <span>Enter to send</span>
        </div>
      </div>

      {/* Queue */}
      <div style={{ maxHeight: 220, overflowY: 'auto' }} className="scrollbar-hide">
        <div style={{ padding: '8px 14px 4px', fontSize:13, color: 'var(--text-muted)' }}>Queue ({notes.length})</div>
        {notes.map(note => (
          <div key={note.id} style={{
            display: 'flex', alignItems: 'flex-start', gap: 8, padding: '9px 14px',
            borderBottom: '1px solid color-mix(in oklab, var(--ink) 4%, transparent)',
          }}>
            <Icon name={note.type === 'url' ? 'Link' : 'NotePen'} size={15} style={{ flexShrink: 0, marginTop: 2, color: 'var(--text-muted)' }}/>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize:13, color: note.status === 'done' ? 'var(--text-muted)' : 'var(--text-secondary)',
                lineHeight: 1.4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                textDecoration: note.status === 'done' ? 'line-through' : 'none',
              }}>{note.text}</div>
              <div style={{ fontSize:13, fontVariantNumeric:'tabular-nums', color: 'var(--text-muted)', marginTop: 2 }}>{note.ago}</div>
            </div>
            <NoteStatusPill status={note.status}/>
          </div>
        ))}
      </div>
    </div>
  );
}

// Header trigger; the panel opens as a popover under the header.
function QuickNotesFAB({ visible }) {
  const [open, setOpen] = React.useState(false);
  if (!visible) return null;
  return (
    <>
      {open && <QuickNotes onClose={() => setOpen(false)}/>}
      <button type="button" className="shell-icon-btn" onClick={() => setOpen(o => !o)}
        aria-expanded={open} aria-haspopup="dialog" aria-label="Quick notes" title="Quick notes">
        <Icon name="NotePen" size={20}/>
      </button>
    </>
  );
}

export { QuickNotesFAB, QuickNotes };
export default QuickNotesFAB;
