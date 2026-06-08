/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars */
import React from 'react';
import * as api from '../../api';

const FIBONACCI = [1, 2, 3, 5, 8, 13];

const statusColors = {
  todo: '#6e7786', in_progress: '#5da2ff', in_review: '#ff9d66',
  blocked: '#ffbd66', needs_clarification: '#b57bee', done: '#46d9a4', failed: '#ff6b7d',
};
const priorityColors = { urgent: '#ff6b7d', high: '#ffbd66', medium: '#7c9dff', low: '#6e7786' };

function fmt(epoch) {
  if (!epoch) return '—';
  return new Date(epoch * 1000).toLocaleString();
}

function relTime(epoch) {
  if (!epoch) return '—';
  const diff = Math.floor((Date.now() / 1000) - epoch);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function CommentBubble({ comment, indent = false }) {
  const isAgent = comment.author?.startsWith('agent:');
  return (
    <div style={{
      marginLeft: indent ? 24 : 0,
      padding: '8px 12px',
      borderRadius: 10,
      background: isAgent ? 'rgba(255,255,255,0.04)' : 'rgba(93,162,255,0.07)',
      border: `1px solid ${isAgent ? 'rgba(255,255,255,0.08)' : 'rgba(93,162,255,0.18)'}`,
      marginBottom: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
        {isAgent ? (
          <span style={{ fontSize: 13 }}>🤖</span>
        ) : (
          <span style={{
            width: 20, height: 20, borderRadius: '50%',
            background: 'rgba(93,162,255,0.3)', color: '#fff',
            fontSize: 10, fontWeight: 700, display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
          }}>
            {(comment.author || 'U')[0].toUpperCase()}
          </span>
        )}
        <span style={{ fontSize: 11, fontWeight: 600, color: isAgent ? 'var(--text-secondary)' : '#7cb0ff' }}>
          {isAgent ? comment.author.replace('agent:', '') : comment.author}
        </span>
        <span style={{ fontSize: 10, color: 'var(--text-muted)', marginLeft: 'auto', fontFamily: 'var(--font-mono)' }}>
          {relTime(comment.created_at)}
        </span>
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
        {comment.body}
      </div>
    </div>
  );
}

function TaskDetailPanel({ taskId, onClose, onTaskUpdated }) {
  const [task, setTask] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const [sprints, setSprints] = React.useState([]);

  // Editable fields
  const [editTitle, setEditTitle] = React.useState('');
  const [editDesc, setEditDesc] = React.useState('');
  const [savingField, setSavingField] = React.useState('');

  // Comment form
  const [commentBody, setCommentBody] = React.useState('');
  const [submittingComment, setSubmittingComment] = React.useState(false);

  // Modals
  const [showFollowUp, setShowFollowUp] = React.useState(false);
  const [followUpMsg, setFollowUpMsg] = React.useState('');
  const [showEscalate, setShowEscalate] = React.useState(false);
  const [escalateReason, setEscalateReason] = React.useState('');
  const [showClarify, setShowClarify] = React.useState(false);
  const [clarifyReason, setClarifyReason] = React.useState('');

  // Approval
  const [rejectReason, setRejectReason] = React.useState({});
  const [showRejectInput, setShowRejectInput] = React.useState({});

  const [actionError, setActionError] = React.useState('');

  const fetchTask = React.useCallback(async () => {
    try {
      const res = await api.getTask(taskId);
      const t = res.data?.task;
      setTask(t);
      setEditTitle(t?.title || '');
      setEditDesc(t?.description || '');
    } catch (e) {
      setError(e?.response?.data?.detail || e?.message || 'Failed to load task');
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  React.useEffect(() => {
    fetchTask();
    api.fetchSprints().then(r => setSprints(r.data?.data || [])).catch(() => {});
  }, [fetchTask]);

  // Esc key to close
  React.useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  const patchTask = async (updates) => {
    await api.updateTask(taskId, updates);
    await fetchTask();
    if (onTaskUpdated) onTaskUpdated();
  };

  const saveTitle = async () => {
    if (editTitle.trim() === task?.title) return;
    setSavingField('title');
    try { await patchTask({ title: editTitle.trim() }); } catch (e) { setActionError(e?.message); }
    setSavingField('');
  };

  const saveDesc = async () => {
    if (editDesc === task?.description) return;
    setSavingField('desc');
    try { await patchTask({ description: editDesc }); } catch (e) { setActionError(e?.message); }
    setSavingField('');
  };

  const setStoryPoints = async (pts) => {
    try { await patchTask({ story_points: pts }); } catch (e) { setActionError(e?.message); }
  };

  const setSprint = async (sprintId) => {
    try { await patchTask({ sprint_id: sprintId || null }); } catch (e) { setActionError(e?.message); }
  };

  const setStatus = async (status) => {
    try { await patchTask({ status }); } catch (e) { setActionError(e?.message); }
  };

  const setPriority = async (priority) => {
    try { await patchTask({ priority }); } catch (e) { setActionError(e?.message); }
  };

  const submitComment = async () => {
    if (!commentBody.trim()) return;
    setSubmittingComment(true);
    try {
      await api.addTaskComment(taskId, { body: commentBody.trim() });
      setCommentBody('');
      await fetchTask();
    } catch (e) { setActionError(e?.response?.data?.detail || e?.message); }
    setSubmittingComment(false);
  };

  const submitFollowUp = async () => {
    if (!followUpMsg.trim()) return;
    try {
      await api.followUpTask(taskId, { message: followUpMsg.trim() });
      setShowFollowUp(false); setFollowUpMsg('');
      await fetchTask(); if (onTaskUpdated) onTaskUpdated();
    } catch (e) { setActionError(e?.response?.data?.detail || e?.message); }
  };

  const submitEscalate = async () => {
    try {
      await api.escalateTask(taskId);
      setShowEscalate(false); setEscalateReason('');
      await fetchTask(); if (onTaskUpdated) onTaskUpdated();
    } catch (e) { setActionError(e?.response?.data?.detail || e?.message); }
  };

  const submitClarify = async () => {
    if (!clarifyReason.trim()) return;
    try {
      await api.clarifyTask(taskId, { reason: clarifyReason.trim() });
      setShowClarify(false); setClarifyReason('');
      await fetchTask(); if (onTaskUpdated) onTaskUpdated();
    } catch (e) { setActionError(e?.response?.data?.detail || e?.message); }
  };

  const submitApproval = async (checkpointId, approve, reason = '') => {
    try {
      await api.approveTaskCheckpoint(taskId, { checkpoint_id: checkpointId, approve, reason });
      await fetchTask(); if (onTaskUpdated) onTaskUpdated();
    } catch (e) { setActionError(e?.response?.data?.detail || e?.message); }
  };

  if (loading) return (
    <PanelShell onClose={onClose}>
      <div style={{ padding: 24, color: 'var(--text-muted)', fontSize: 13 }}>Loading…</div>
    </PanelShell>
  );
  if (error || !task) return (
    <PanelShell onClose={onClose}>
      <div style={{ padding: 24, color: '#ff6b7d', fontSize: 13 }}>{error || 'Task not found'}</div>
    </PanelShell>
  );

  const statusColor = statusColors[task.status] || '#6e7786';
  const pendingCheckpoints = (task.approval_checkpoints || []).filter(c => c.approved === null || c.approved === undefined);

  // Build threaded comments: top-level first, then replies indented
  const topComments = (task.comments || []).filter(c => !c.reply_to);
  const replyMap = {};
  (task.comments || []).filter(c => c.reply_to).forEach(c => {
    replyMap[c.reply_to] = replyMap[c.reply_to] || [];
    replyMap[c.reply_to].push(c);
  });

  return (
    <>
      {/* Overlay */}
      <div onClick={onClose} style={{
        position: 'fixed', inset: 0, zIndex: 300, background: 'rgba(0,0,0,0.45)',
      }} />

      {/* Panel */}
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 301,
        width: 'min(560px, 100vw)',
        background: 'rgba(8,11,17,0.98)',
        borderLeft: '1px solid rgba(255,255,255,0.10)',
        display: 'flex', flexDirection: 'column',
        overflowY: 'auto',
        animation: 'slideInRight 0.22s ease-out',
      }}>
        {/* Header */}
        <div style={{ padding: '18px 20px 14px', borderBottom: '1px solid rgba(255,255,255,0.07)', flexShrink: 0 }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
            <input
              value={editTitle}
              onChange={e => setEditTitle(e.target.value)}
              onBlur={saveTitle}
              style={{
                flex: 1, fontSize: 15, fontWeight: 700, color: '#fff',
                background: 'transparent', border: 'none', outline: 'none',
                lineHeight: 1.4,
              }}
            />
            <span style={{
              padding: '3px 10px', borderRadius: 999, fontSize: 10, fontWeight: 700,
              fontFamily: 'var(--font-mono)', letterSpacing: '0.10em', textTransform: 'uppercase',
              background: `${statusColor}18`, border: `1px solid ${statusColor}40`, color: statusColor,
              flexShrink: 0,
            }}>{task.status.replace(/_/g, ' ')}</span>
            <button onClick={onClose} style={{
              background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer',
              fontSize: 18, lineHeight: 1, padding: '0 2px', flexShrink: 0,
            }}>✕</button>
          </div>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: 4 }}>
            {task.task_id} · created {relTime(task.created_at)} · updated {relTime(task.updated_at)}
          </div>
        </div>

        {/* Meta row */}
        <div style={{ padding: '12px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', flexWrap: 'wrap', gap: 8, flexShrink: 0 }}>
          {/* Status */}
          <select value={task.status} onChange={e => setStatus(e.target.value)} style={selectStyle}>
            {['todo','in_progress','in_review','blocked','needs_clarification','done','failed'].map(s => (
              <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
            ))}
          </select>
          {/* Priority */}
          <select value={task.priority} onChange={e => setPriority(e.target.value)} style={{ ...selectStyle, borderColor: `${priorityColors[task.priority] || '#6e7786'}40` }}>
            {['urgent','high','medium','low'].map(p => <option key={p} value={p}>{p}</option>)}
          </select>
          {/* Story points */}
          <div style={{ display: 'flex', gap: 3, alignItems: 'center' }}>
            <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginRight: 2 }}>SP</span>
            {[null, ...FIBONACCI].map(pts => (
              <button key={pts ?? '?'} onClick={() => setStoryPoints(pts)} style={{
                padding: '2px 7px', borderRadius: 6, fontSize: 10, fontWeight: 700, cursor: 'pointer',
                background: task.story_points === pts ? 'rgba(93,162,255,0.2)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${task.story_points === pts ? 'rgba(93,162,255,0.4)' : 'rgba(255,255,255,0.09)'}`,
                color: task.story_points === pts ? '#7cb0ff' : 'var(--text-muted)',
              }}>{pts ?? '?'}</button>
            ))}
          </div>
          {/* Sprint */}
          <select value={task.sprint_id || ''} onChange={e => setSprint(e.target.value)} style={selectStyle}>
            <option value="">No sprint</option>
            {sprints.map(s => <option key={s.sprint_id} value={s.sprint_id}>{s.name}</option>)}
          </select>
        </div>

        {/* Description */}
        <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6, textTransform: 'uppercase', letterSpacing: '0.10em' }}>Description</div>
          <textarea
            value={editDesc}
            onChange={e => setEditDesc(e.target.value)}
            onBlur={saveDesc}
            rows={3}
            placeholder="Add a description…"
            style={{
              width: '100%', boxSizing: 'border-box',
              padding: '10px 12px', borderRadius: 10, fontSize: 12, lineHeight: 1.6,
              background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.09)',
              color: 'var(--text-primary)', outline: 'none', resize: 'vertical',
              fontFamily: 'var(--font-main)',
            }}
          />
          {savingField === 'desc' && <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 4 }}>Saving…</div>}
        </div>

        {/* Approval checkpoints */}
        {pendingCheckpoints.length > 0 && (
          <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#ffbd66', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.10em' }}>Approval Required</div>
            {pendingCheckpoints.map(cp => (
              <div key={cp.checkpoint_id} style={{
                padding: '10px 14px', borderRadius: 10,
                background: 'rgba(255,189,102,0.05)', border: '1px solid rgba(255,189,102,0.18)',
                marginBottom: 8,
              }}>
                <div style={{ fontSize: 12, color: '#ffbd66', marginBottom: 8 }}>{cp.description}</div>
                {showRejectInput[cp.checkpoint_id] ? (
                  <div style={{ display: 'flex', gap: 6, flexDirection: 'column' }}>
                    <input
                      placeholder="Rejection reason…"
                      value={rejectReason[cp.checkpoint_id] || ''}
                      onChange={e => setRejectReason(prev => ({ ...prev, [cp.checkpoint_id]: e.target.value }))}
                      style={{ padding: '6px 10px', borderRadius: 8, fontSize: 12, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)', color: '#fff', outline: 'none' }}
                    />
                    <div style={{ display: 'flex', gap: 6 }}>
                      <button onClick={() => submitApproval(cp.checkpoint_id, false, rejectReason[cp.checkpoint_id] || '')} style={{ ...actionBtn('#ff6b7d') }}>Confirm Reject</button>
                      <button onClick={() => setShowRejectInput(prev => ({ ...prev, [cp.checkpoint_id]: false }))} style={{ ...actionBtn('#6e7786') }}>Cancel</button>
                    </div>
                  </div>
                ) : (
                  <div style={{ display: 'flex', gap: 6 }}>
                    <button onClick={() => submitApproval(cp.checkpoint_id, true)} style={{ ...actionBtn('#46d9a4') }}>Approve</button>
                    <button onClick={() => setShowRejectInput(prev => ({ ...prev, [cp.checkpoint_id]: true }))} style={{ ...actionBtn('#ff6b7d') }}>Reject</button>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Comment thread */}
        <div style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', flex: 1 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.10em' }}>
            Comments {task.comments?.length > 0 && `(${task.comments.length})`}
          </div>
          {topComments.length === 0 && (
            <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>No comments yet.</div>
          )}
          {topComments.map(c => (
            <React.Fragment key={c.comment_id}>
              <CommentBubble comment={c} />
              {(replyMap[c.comment_id] || []).map(r => (
                <CommentBubble key={r.comment_id} comment={r} indent />
              ))}
            </React.Fragment>
          ))}
          {/* Add comment */}
          <div style={{ marginTop: 8 }}>
            <textarea
              value={commentBody}
              onChange={e => setCommentBody(e.target.value)}
              rows={2}
              placeholder="Add a comment…"
              style={{
                width: '100%', boxSizing: 'border-box',
                padding: '8px 12px', borderRadius: 10, fontSize: 12,
                background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.10)',
                color: 'var(--text-primary)', outline: 'none', resize: 'none', fontFamily: 'var(--font-main)',
              }}
            />
            <button
              disabled={!commentBody.trim() || submittingComment}
              onClick={submitComment}
              style={{
                marginTop: 6, padding: '6px 16px', borderRadius: 8, fontSize: 12, fontWeight: 700,
                background: commentBody.trim() ? 'rgba(93,162,255,0.15)' : 'rgba(255,255,255,0.04)',
                border: `1px solid ${commentBody.trim() ? 'rgba(93,162,255,0.35)' : 'rgba(255,255,255,0.08)'}`,
                color: commentBody.trim() ? '#7cb0ff' : 'var(--text-muted)', cursor: commentBody.trim() ? 'pointer' : 'not-allowed',
              }}
            >{submittingComment ? 'Sending…' : 'Comment'}</button>
          </div>
        </div>

        {/* Execution log */}
        {task.execution_log?.length > 0 && (
          <details style={{ padding: '14px 20px', borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
            <summary style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.10em', cursor: 'pointer', listStyle: 'none', userSelect: 'none' }}>
              Execution Log ({task.execution_log.length} entries) ›
            </summary>
            <div style={{ marginTop: 10, maxHeight: 260, overflowY: 'auto' }}>
              {task.execution_log.slice().reverse().map((entry, i) => (
                <div key={i} style={{
                  display: 'flex', gap: 8, marginBottom: 6, fontSize: 11, fontFamily: 'var(--font-mono)',
                  color: entry.level === 'error' ? '#ff6b7d' : entry.level === 'warning' ? '#ffbd66' : 'var(--text-secondary)',
                }}>
                  <span style={{ color: 'var(--text-muted)', flexShrink: 0 }}>{fmt(entry.timestamp)}</span>
                  <span>{entry.message}</span>
                </div>
              ))}
            </div>
          </details>
        )}

        {/* Action error */}
        {actionError && (
          <div style={{
            margin: '0 20px 8px', padding: '8px 12px', borderRadius: 10,
            background: 'rgba(255,107,125,0.07)', border: '1px solid rgba(255,107,125,0.18)',
            fontSize: 12, color: '#ff6b7d', cursor: 'pointer',
          }} onClick={() => setActionError('')}>
            {actionError} <span style={{ fontSize: 10, opacity: 0.6 }}>(click to dismiss)</span>
          </div>
        )}

        {/* Actions footer */}
        <div style={{ padding: '14px 20px', flexShrink: 0, display: 'flex', gap: 8, borderTop: '1px solid rgba(255,255,255,0.07)' }}>
          <button onClick={() => setShowFollowUp(true)} style={{ ...footerBtn('#7c9dff') }}>Follow-up</button>
          <button onClick={() => setShowEscalate(true)} style={{ ...footerBtn('#ffbd66') }}>Escalate</button>
          <button onClick={() => setShowClarify(true)} style={{ ...footerBtn('#b57bee') }}>Request Clarification</button>
        </div>
      </div>

      {/* Follow-up modal */}
      {showFollowUp && (
        <Modal title="Follow-up instruction" onClose={() => setShowFollowUp(false)}>
          <textarea value={followUpMsg} onChange={e => setFollowUpMsg(e.target.value)} rows={4} placeholder="New guidance for the agent…" style={modalTextarea} autoFocus />
          <ModalActions onCancel={() => setShowFollowUp(false)} onConfirm={submitFollowUp} confirmLabel="Send" confirmDisabled={!followUpMsg.trim()} />
        </Modal>
      )}

      {/* Escalate modal */}
      {showEscalate && (
        <Modal title="Escalate task?" onClose={() => setShowEscalate(false)}>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12 }}>
            This will flag the task for immediate attention. Continue?
          </p>
          <ModalActions onCancel={() => setShowEscalate(false)} onConfirm={submitEscalate} confirmLabel="Escalate" confirmColor="#ffbd66" />
        </Modal>
      )}

      {/* Clarify modal */}
      {showClarify && (
        <Modal title="Request clarification" onClose={() => setShowClarify(false)}>
          <textarea value={clarifyReason} onChange={e => setClarifyReason(e.target.value)} rows={3} placeholder="What needs clarification?" style={modalTextarea} autoFocus />
          <ModalActions onCancel={() => setShowClarify(false)} onConfirm={submitClarify} confirmLabel="Request" confirmDisabled={!clarifyReason.trim()} confirmColor="#b57bee" />
        </Modal>
      )}
    </>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function PanelShell({ onClose, children }) {
  return (
    <>
      <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 300, background: 'rgba(0,0,0,0.45)' }} />
      <div style={{
        position: 'fixed', top: 0, right: 0, bottom: 0, zIndex: 301,
        width: 'min(560px, 100vw)', background: 'rgba(8,11,17,0.98)',
        borderLeft: '1px solid rgba(255,255,255,0.10)', display: 'flex', flexDirection: 'column',
      }}>
        {children}
      </div>
    </>
  );
}

function Modal({ title, onClose, children }) {
  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 400, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div style={{ background: 'rgba(10,13,18,0.99)', border: '1px solid rgba(255,255,255,0.12)', borderRadius: 16, padding: '22px 20px', width: '100%', maxWidth: 440 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: '#fff', marginBottom: 14 }}>{title}</div>
        {children}
      </div>
    </div>
  );
}

function ModalActions({ onCancel, onConfirm, confirmLabel, confirmDisabled, confirmColor = '#5da2ff' }) {
  return (
    <div style={{ display: 'flex', gap: 10, justifyContent: 'flex-end', marginTop: 14 }}>
      <button onClick={onCancel} style={{ padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 700, background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.10)', color: 'var(--text-secondary)', cursor: 'pointer' }}>Cancel</button>
      <button disabled={confirmDisabled} onClick={onConfirm} style={{
        padding: '8px 16px', borderRadius: 8, fontSize: 13, fontWeight: 700, cursor: confirmDisabled ? 'not-allowed' : 'pointer',
        background: confirmDisabled ? 'rgba(255,255,255,0.04)' : `${confirmColor}22`,
        border: `1px solid ${confirmDisabled ? 'rgba(255,255,255,0.08)' : `${confirmColor}55`}`,
        color: confirmDisabled ? 'var(--text-muted)' : confirmColor,
      }}>{confirmLabel}</button>
    </div>
  );
}

// ── Style helpers ───────────────────────────────────────────────────────────

const selectStyle = {
  padding: '4px 8px', borderRadius: 8, fontSize: 11, fontFamily: 'var(--font-mono)',
  background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)',
  color: '#fff', outline: 'none', cursor: 'pointer',
};

const actionBtn = (color) => ({
  padding: '5px 12px', borderRadius: 7, fontSize: 11, fontWeight: 700, cursor: 'pointer',
  background: `${color}12`, border: `1px solid ${color}35`, color, transition: 'all 0.15s ease',
});

const footerBtn = (color) => ({
  padding: '7px 14px', borderRadius: 8, fontSize: 12, fontWeight: 700, cursor: 'pointer',
  background: `${color}12`, border: `1px solid ${color}30`, color,
  flex: 1, transition: 'all 0.15s ease',
});

const modalTextarea = {
  width: '100%', boxSizing: 'border-box',
  padding: '10px 14px', borderRadius: 10, fontSize: 13,
  background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)',
  color: '#fff', outline: 'none', resize: 'vertical', fontFamily: 'var(--font-main)',
};

export default TaskDetailPanel;
