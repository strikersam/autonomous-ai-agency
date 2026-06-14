/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';
import * as api from '../../api';
import { useSafeData } from '../hooks/useSafeData';
import TaskDetailPanel from './TaskDetailPanel';

// taskboard.jsx — Task / Job Lifecycle Board

const LIFECYCLE_STAGES = [
  { id: 'todo',                 label: 'To Do',              color: '#6e7786', desc: 'Not started' },
  { id: 'in_progress',         label: 'Running',            color: '#5da2ff', desc: 'Agent executing' },
  { id: 'in_review',           label: 'Review',             color: '#ff9d66', desc: 'Needs approval' },
  { id: 'blocked',             label: 'Blocked',            color: '#ffbd66', desc: 'Waiting on input' },
  { id: 'needs_clarification', label: 'Needs Clarification', color: '#b57bee', desc: 'Awaiting context' },
  { id: 'done',                label: 'Done',               color: '#46d9a4', desc: 'Completed' },
  { id: 'failed',              label: 'Failed',             color: '#ff6b7d', desc: 'Error / retry' },
];

const HEALTH_COLORS = { on_track: '#46d9a4', at_risk: '#ffbd66', off_track: '#ff6b7d', complete: '#6e7786' };
const HEALTH_DOTS   = { on_track: '●', at_risk: '●', off_track: '●', complete: '●' };

function relTime(epoch) {
  if (!epoch) return '—';
  const diff = Math.floor((Date.now() / 1000) - epoch);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}

const priorityColors = { urgent: '#ff6b7d', high: '#ffbd66', medium: '#7c9dff', low: 'var(--text-muted)' };
const typeColors     = { bug: '#ff6b7d', security: '#ffbd66', task: 'var(--accent)', general: 'var(--accent)' };

function StageColumn({ stage, tasks, onApprove, onRetry, onCardClick }) {
  return (
    <div style={{
      minWidth: 'clamp(160px, 80vw, 220px)', maxWidth: 260, flexShrink: 0,
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      <div style={{
        padding: '8px 12px', borderRadius: 10,
        background: `${stage.color}0f`,
        border: `1px solid ${stage.color}22`,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: stage.color, display: 'inline-block', flexShrink: 0 }}/>
            <span style={{ fontSize: 12, fontWeight: 700, color: '#fff' }}>{stage.label}</span>
          </div>
          <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', background: 'rgba(255,255,255,0.06)', padding: '1px 6px', borderRadius: 999 }}>{tasks.length}</span>
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3, fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>{stage.desc}</div>
      </div>

      {tasks.map(task => (
        <TaskCard key={task.task_id} task={task} stageColor={stage.color} onApprove={onApprove} onRetry={onRetry} onCardClick={onCardClick}/>
      ))}

      {tasks.length === 0 && (
        <div style={{ padding: '16px 12px', borderRadius: 10, background: 'rgba(255,255,255,0.015)', border: '1px dashed rgba(255,255,255,0.07)', fontSize: 11, color: 'var(--text-muted)', textAlign: 'center', fontFamily: 'var(--font-mono)' }}>
          Empty
        </div>
      )}
    </div>
  );
}

function TaskCard({ task, stageColor, onApprove, onRetry, onCardClick }) {
  const isApproved    = task.status === 'done';
  const isClarify     = task.status === 'needs_clarification';
  const typeColor     = typeColors[task.task_type] || typeColors.general;
  const priorityColor = priorityColors[task.priority] || 'var(--text-muted)';

  return (
    <div
      onClick={() => onCardClick && onCardClick(task.task_id)}
      style={{
        borderRadius: 14,
        border: `1px solid ${isApproved ? 'rgba(70,217,164,0.20)' : isClarify ? 'rgba(181,123,238,0.22)' : 'rgba(255,255,255,0.09)'}`,
        background: isApproved ? 'rgba(70,217,164,0.04)' : isClarify ? 'rgba(181,123,238,0.04)' : 'rgba(255,255,255,0.03)',
        padding: '12px 14px', cursor: 'pointer',
        transition: 'all 0.18s ease',
        animation: 'fadeSlideUp 0.3s ease-out',
      }}
      onMouseEnter={e => { e.currentTarget.style.background = isApproved ? 'rgba(70,217,164,0.07)' : 'rgba(255,255,255,0.055)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
      onMouseLeave={e => { e.currentTarget.style.background = isApproved ? 'rgba(70,217,164,0.04)' : isClarify ? 'rgba(181,123,238,0.04)' : 'rgba(255,255,255,0.03)'; e.currentTarget.style.transform = 'none'; }}>

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6, marginBottom: 6 }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: priorityColor, flexShrink: 0, marginTop: 4 }}/>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.5, flex: 1 }}>{task.title}</span>
        {task.story_points != null && (
          <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', padding: '1px 6px', borderRadius: 6, background: 'rgba(93,162,255,0.12)', border: '1px solid rgba(93,162,255,0.25)', color: '#7cb0ff', flexShrink: 0 }}>{task.story_points}pt</span>
        )}
      </div>

      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 8 }}>
        <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 999, color: typeColor, background: `${typeColor}15`, border: `1px solid ${typeColor}30` }}>{task.task_type}</span>
        <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 999, color: priorityColor, background: `${priorityColor}12`, border: `1px solid ${priorityColor}28` }}>{task.priority}</span>
        {isClarify && (
          <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.10em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 999, color: '#b57bee', background: 'rgba(181,123,238,0.12)', border: '1px solid rgba(181,123,238,0.28)' }}>❓ Clarify</span>
        )}
        {isApproved && (
          <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.10em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 999, color: '#46d9a4', background: 'rgba(70,217,164,0.12)', border: '1px solid rgba(70,217,164,0.25)' }}>done ✓</span>
        )}
      </div>

      {task.tags && task.tags.length > 0 && (
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 8 }}>
          {task.tags.slice(0,3).map(t => (
            <span key={t} style={{ fontSize: 9, fontFamily: 'var(--font-mono)', padding: '1px 6px', borderRadius: 5, color: 'var(--text-muted)', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.09)' }}>{t}</span>
          ))}
        </div>
      )}

      {task.blocked_reason && (
        <div style={{ marginBottom: 8, padding: '6px 10px', borderRadius: 8, background: 'rgba(255,189,102,0.06)', border: '1px solid rgba(255,189,102,0.18)', fontSize: 11, color: '#ffbd66', lineHeight: 1.4 }}>
          ⚠ {task.blocked_reason}
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 }}>
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          {task.agent_id ? `@${task.agent_id}` : 'Unassigned'}
        </span>
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{relTime(task.updated_at)}</span>
      </div>

      {task.status === 'in_review' && (
        <button onClick={e => { e.stopPropagation(); onApprove(task.task_id); }} style={{
          marginTop: 10, width: '100%', padding: '7px', borderRadius: 8,
          background: 'rgba(70,217,164,0.12)', border: '1px solid rgba(70,217,164,0.28)',
          color: '#46d9a4', fontSize: 11, fontWeight: 700, cursor: 'pointer',
          transition: 'all 0.15s ease',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = 'rgba(70,217,164,0.20)'; }}
        onMouseLeave={e => { e.currentTarget.style.background = 'rgba(70,217,164,0.12)'; }}>
          → Approve & release
        </button>
      )}
      {task.status === 'failed' && (
        <button onClick={e => { e.stopPropagation(); onRetry(task.task_id); }} style={{
          marginTop: 10, width: '100%', padding: '7px', borderRadius: 8,
          background: 'rgba(255,107,125,0.10)', border: '1px solid rgba(255,107,125,0.25)',
          color: '#ff6b7d', fontSize: 11, fontWeight: 700, cursor: 'pointer',
          transition: 'all 0.15s ease',
        }}
        onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,107,125,0.18)'; }}
        onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,107,125,0.10)'; }}>
          ↺ Retry
        </button>
      )}
    </div>
  );
}

// Sprint-grouped view

function SprintSection({ sprint, tasks, onCardClick, onApprove, onRetry }) {
  const health = sprint?.metrics?.health || 'on_track';
  const healthColor = HEALTH_COLORS[health] || '#6e7786';
  const pct = sprint?.metrics?.completion_percentage ?? 0;
  const daysLeft = sprint?.metrics?.days_remaining ?? 0;

  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
        <span style={{ fontSize: 14, fontWeight: 700, color: '#fff' }}>{sprint?.name || 'No Sprint'}</span>
        {sprint && (
          <>
            <span style={{ fontSize: 12, color: healthColor, fontFamily: 'var(--font-mono)' }}>
              {HEALTH_DOTS[health]} {health.replace(/_/g, ' ')}
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
              {Math.round(pct)}% · {Math.round(daysLeft)}d left
            </span>
          </>
        )}
        <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', background: 'rgba(255,255,255,0.05)', padding: '1px 7px', borderRadius: 999 }}>{tasks.length}</span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
        {tasks.map(task => (
          <div key={task.task_id} style={{ width: 240 }}>
            <TaskCard task={task} stageColor={HEALTH_COLORS[health] || '#6e7786'} onApprove={onApprove} onRetry={onRetry} onCardClick={onCardClick} />
          </div>
        ))}
        {tasks.length === 0 && (
          <div style={{ padding: '12px 16px', borderRadius: 10, background: 'rgba(255,255,255,0.015)', border: '1px dashed rgba(255,255,255,0.07)', fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            No tasks in this sprint
          </div>
        )}
      </div>
    </div>
  );
}

function VelocityWidget() {
  const [velocity, setVelocity] = React.useState(null);
  React.useEffect(() => {
    api.fetchVelocity().then(r => setVelocity(r.data?.data)).catch(() => {});
  }, []);
  if (!velocity) return null;
  const history = (velocity.history || []).slice(-5);
  const maxVel = Math.max(...history.map(h => h.velocity), 1);
  return (
    <details style={{ marginTop: 16, padding: '14px 16px', borderRadius: 14, background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)' }}>
      <summary style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)', cursor: 'pointer', listStyle: 'none', userSelect: 'none' }}>
        Velocity — {velocity.predicted_velocity}pt predicted ({velocity.sprint_count} sprints) ›
      </summary>
      {history.length > 0 && (
        <div style={{ marginTop: 12, display: 'flex', alignItems: 'flex-end', gap: 8, height: 60 }}>
          {history.map(h => (
            <div key={h.sprint_id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4, flex: 1 }}>
              <div style={{ width: '100%', background: 'rgba(93,162,255,0.3)', borderRadius: 4, height: `${(h.velocity / maxVel) * 48}px`, minHeight: 4 }} />
              <span style={{ fontSize: 9, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', textAlign: 'center', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 56 }}>{h.name}</span>
              <span style={{ fontSize: 9, color: '#7cb0ff', fontFamily: 'var(--font-mono)' }}>{h.velocity}</span>
            </div>
          ))}
        </div>
      )}
      {history.length === 0 && (
        <div style={{ marginTop: 8, fontSize: 12, color: 'var(--text-muted)' }}>No completed sprints yet.</div>
      )}
    </details>
  );
}

function TaskBoardScreen() {
  const [filter, setFilter] = React.useState('all');
  const [viewMode, setViewMode] = React.useState('board'); // 'board' | 'sprint'
  const [pendingApprove, setPendingApprove] = React.useState(null);
  const [pendingRetry, setPendingRetry]     = React.useState(null);
  const [showNewTask, setShowNewTask] = React.useState(false);
  const [newTaskTitle, setNewTaskTitle] = React.useState('');
  const [newTaskDesc, setNewTaskDesc] = React.useState('');
  const [newTaskPriority, setNewTaskPriority] = React.useState('medium');
  const [newTaskType, setNewTaskType] = React.useState('task');
  const [newTaskPoints, setNewTaskPoints] = React.useState(null);
  const [newTaskSprint, setNewTaskSprint] = React.useState('');
  const [creatingTask, setCreatingTask] = React.useState(false);
  const [createError, setCreateError] = React.useState('');
  const [actionError, setActionError] = React.useState('');

  // Detail panel
  const [selectedTaskId, setSelectedTaskId] = React.useState(null);

  // Sprint management
  const [sprints, setSprints] = React.useState([]);
  const [showNewSprint, setShowNewSprint] = React.useState(false);
  const [newSprintName, setNewSprintName] = React.useState('');
  const [newSprintGoal, setNewSprintGoal] = React.useState('');
  const [creatingSprint, setCreatingSprint] = React.useState(false);

  const [data, states, fetchAll] = useSafeData(null, {
    tasks: '/api/tasks/',
  }, { refreshMs: 15000 });

  const rawTasks = data.tasks?.tasks || [];

  const fetchSprints = React.useCallback(() => {
    api.fetchSprints().then(r => setSprints(r.data?.data || [])).catch(() => {});
  }, []);

  React.useEffect(() => {
    if (viewMode === 'sprint') fetchSprints();
  }, [viewMode, fetchSprints]);

  const handleApprove = async (taskId) => {
    setActionError(''); setPendingApprove(taskId);
    try {
      await api.approveTaskCheckpoint(taskId, { approved: true, reason: 'Approved via UI' });
    } catch (e) {
      if (e?.response?.status !== 404 && e?.response?.status !== 400) {
        setActionError(api.fmtErr?.(e?.response?.data?.detail) || e?.message || 'Could not approve task.');
      }
    }
    setPendingApprove(null);
    fetchAll();
  };

  const handleRetry = async (taskId) => {
    setActionError(''); setPendingRetry(taskId);
    try {
      await api.retryTask(taskId);
    } catch (e) {
      setActionError(api.fmtErr?.(e?.response?.data?.detail) || e?.message || 'Could not retry task.');
    }
    setPendingRetry(null);
    fetchAll();
  };

  const handleCreateSprint = async () => {
    if (!newSprintName.trim()) return;
    setCreatingSprint(true);
    try {
      await api.createSprint({ name: newSprintName.trim(), goal: newSprintGoal.trim() });
      setShowNewSprint(false); setNewSprintName(''); setNewSprintGoal('');
      fetchSprints();
    } catch (e) {
      setActionError(e?.response?.data?.detail || e?.message || 'Could not create sprint.');
    }
    setCreatingSprint(false);
  };

  const filtered = filter === 'all' ? rawTasks
    : rawTasks.filter(t => t.priority === filter || t.task_type === filter);

  const loading = states.tasks?.loading;
  const error   = states.tasks?.error;

  // Sprint view: group tasks by sprint_id
  const sprintMap = {};
  filtered.forEach(t => {
    const key = t.sprint_id || '__none__';
    sprintMap[key] = sprintMap[key] || [];
    sprintMap[key].push(t);
  });
  const sprintById = Object.fromEntries(sprints.map(s => [s.sprint_id, s]));
  // Ordered: known sprints first, then "No Sprint"
  const sprintGroups = [
    ...sprints.filter(s => sprintMap[s.sprint_id]?.length > 0).map(s => ({ sprint: s, tasks: sprintMap[s.sprint_id] || [] })),
    ...(sprintMap['__none__']?.length > 0 ? [{ sprint: null, tasks: sprintMap['__none__'] }] : []),
  ];

  const FIBONACCI = [1, 2, 3, 5, 8, 13];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '20px 20px 0', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
          <div>
            <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 4 }}>Task Lifecycle</div>
            <h1 style={{ fontSize: 22, fontWeight: 800, color: '#fff', letterSpacing: '-0.04em', lineHeight: 1.1 }}>Job Board</h1>
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', alignItems: 'center' }}>
            {/* View toggle */}
            <div style={{ display: 'flex', borderRadius: 999, overflow: 'hidden', border: '1px solid rgba(255,255,255,0.10)' }}>
              {['board', 'sprint'].map(mode => (
                <button key={mode} onClick={() => setViewMode(mode)} style={{
                  padding: '5px 14px', fontSize: 11, fontWeight: 600, cursor: 'pointer',
                  background: viewMode === mode ? 'rgba(93,162,255,0.18)' : 'rgba(255,255,255,0.04)',
                  border: 'none',
                  color: viewMode === mode ? '#fff' : 'var(--text-muted)',
                  textTransform: 'capitalize',
                }}>{mode}</button>
              ))}
            </div>
            {/* Filter chips */}
            {['all', 'urgent', 'bug', 'security'].map(f => (
              <button key={f} onClick={() => setFilter(f)} style={{
                padding: '5px 14px', borderRadius: 999, fontSize: 11, fontWeight: 600, cursor: 'pointer',
                background: filter === f ? 'rgba(93,162,255,0.15)' : 'rgba(255,255,255,0.05)',
                border: `1px solid ${filter === f ? 'rgba(93,162,255,0.35)' : 'rgba(255,255,255,0.10)'}`,
                color: filter === f ? '#fff' : 'var(--text-muted)',
                textTransform: 'capitalize', transition: 'all 0.15s ease',
              }}>{f}</button>
            ))}
            {viewMode === 'sprint' && (
              <button onClick={() => setShowNewSprint(true)} style={{
                padding: '5px 14px', borderRadius: 999, fontSize: 11, fontWeight: 700, cursor: 'pointer',
                background: 'rgba(181,123,238,0.12)', border: '1px solid rgba(181,123,238,0.28)',
                color: '#b57bee', transition: 'all 0.15s ease',
              }}>New Sprint +</button>
            )}
            <button onClick={() => { setShowNewTask(true); setCreateError(''); }} style={{
              padding: '5px 14px', borderRadius: 999, fontSize: 11, fontWeight: 700, cursor: 'pointer',
              background: 'rgba(70,217,164,0.12)', border: '1px solid rgba(70,217,164,0.28)',
              color: '#46d9a4', transition: 'all 0.15s ease',
            }}>+ New task</button>
          </div>
        </div>

        {error && (
          <div style={{ marginBottom: 10, padding: '8px 12px', borderRadius: 10, background: 'rgba(255,107,125,0.07)', border: '1px solid rgba(255,107,125,0.18)', fontSize: 12, color: '#ff6b7d' }}>
            Could not load tasks: {error}
          </div>
        )}
        {actionError && (
          <div style={{ marginBottom: 10, padding: '8px 12px', borderRadius: 10, background: 'rgba(255,189,102,0.07)', border: '1px solid rgba(255,189,102,0.18)', fontSize: 12, color: '#ffbd66', cursor: 'pointer' }} onClick={() => setActionError('')}>
            {actionError} <span style={{ fontSize: 10, opacity: 0.6 }}>(click to dismiss)</span>
          </div>
        )}
        {loading && (
          <div style={{ marginBottom: 10, fontSize: 12, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>Loading tasks…</div>
        )}
      </div>

      {/* New Task Modal */}
      {showNewTask && (
        <div style={{ position:'fixed', inset:0, zIndex:200, background:'rgba(0,0,0,0.7)', display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}>
          <div style={{ background:'rgba(10,13,18,0.98)', border:'1px solid rgba(255,255,255,0.12)', borderRadius:20, padding:'28px 24px', width:'100%', maxWidth:480 }}>
            <div style={{ fontSize:15, fontWeight:700, color:'#fff', marginBottom:16 }}>Create new task</div>
            <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
              <input value={newTaskTitle} onChange={e => setNewTaskTitle(e.target.value)} placeholder="Task title"
                style={{ padding:'10px 14px', borderRadius:10, fontSize:13, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff', outline:'none' }} autoFocus />
              <textarea value={newTaskDesc} onChange={e => setNewTaskDesc(e.target.value)} placeholder="Description (optional)" rows={3}
                style={{ padding:'10px 14px', borderRadius:10, fontSize:13, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff', outline:'none', resize:'vertical', fontFamily:'var(--font-main)' }} />
              <div style={{ display:'flex', gap:8 }}>
                <select value={newTaskPriority} onChange={e => setNewTaskPriority(e.target.value)}
                  style={{ flex:1, padding:'9px 12px', borderRadius:10, fontSize:13, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff', outline:'none' }}>
                  {['urgent','high','medium','low'].map(p => <option key={p} value={p}>{p}</option>)}
                </select>
                <select value={newTaskType} onChange={e => setNewTaskType(e.target.value)}
                  style={{ flex:1, padding:'9px 12px', borderRadius:10, fontSize:13, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff', outline:'none' }}>
                  {['task','bug','security','general'].map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              {/* Story points */}
              <div style={{ display:'flex', alignItems:'center', gap:6 }}>
                <span style={{ fontSize:11, color:'var(--text-muted)', fontFamily:'var(--font-mono)', minWidth:72 }}>Story points</span>
                {[null, ...FIBONACCI].map(pts => (
                  <button key={pts ?? '?'} onClick={() => setNewTaskPoints(pts)} type="button" style={{
                    padding:'3px 9px', borderRadius:6, fontSize:11, fontWeight:700, cursor:'pointer',
                    background: newTaskPoints === pts ? 'rgba(93,162,255,0.2)' : 'rgba(255,255,255,0.04)',
                    border:`1px solid ${newTaskPoints === pts ? 'rgba(93,162,255,0.4)' : 'rgba(255,255,255,0.09)'}`,
                    color: newTaskPoints === pts ? '#7cb0ff' : 'var(--text-muted)',
                  }}>{pts ?? '?'}</button>
                ))}
              </div>
              {/* Sprint */}
              <select value={newTaskSprint} onChange={e => setNewTaskSprint(e.target.value)}
                style={{ padding:'9px 12px', borderRadius:10, fontSize:13, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff', outline:'none' }}>
                <option value="">No sprint</option>
                {sprints.map(s => <option key={s.sprint_id} value={s.sprint_id}>{s.name}</option>)}
              </select>
            </div>
            {createError && (
              <div style={{ marginTop:14, padding:'9px 12px', borderRadius:10, background:'rgba(255,107,125,0.07)', border:'1px solid rgba(255,107,125,0.18)', fontSize:12, color:'#ff6b7d', lineHeight:1.5 }}>
                {createError}
              </div>
            )}
            <div style={{ display:'flex', gap:10, justifyContent:'flex-end', marginTop:16 }}>
              <button onClick={() => { setShowNewTask(false); setNewTaskTitle(''); setNewTaskDesc(''); setCreateError(''); setNewTaskPoints(null); setNewTaskSprint(''); }}
                style={{ padding:'9px 18px', borderRadius:10, fontSize:13, fontWeight:700, background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-secondary)', cursor:'pointer' }}>Cancel</button>
              <button disabled={!newTaskTitle.trim() || creatingTask} onClick={async () => {
                setCreateError(''); setCreatingTask(true);
                try {
                  await api.createTask({
                    title: newTaskTitle.trim(), description: newTaskDesc.trim(),
                    priority: newTaskPriority, task_type: newTaskType,
                    story_points: newTaskPoints ?? undefined,
                    sprint_id: newTaskSprint || undefined,
                  });
                  setShowNewTask(false); setNewTaskTitle(''); setNewTaskDesc(''); setNewTaskPoints(null); setNewTaskSprint('');
                  fetchAll();
                } catch (e) { setCreateError(api.fmtErr?.(e?.response?.data?.detail) || e?.message || 'Could not create task. Check your connection and try again.'); }
                finally { setCreatingTask(false); }
              }}
                style={{ padding:'9px 18px', borderRadius:10, fontSize:13, fontWeight:700, background:newTaskTitle.trim() && !creatingTask ? 'linear-gradient(135deg,#6CB0FF,#3A7FE8)' : 'rgba(93,162,255,0.2)', border:'none', color:'#fff', cursor: newTaskTitle.trim() && !creatingTask ? 'pointer' : 'not-allowed' }}>
                {creatingTask ? 'Creating…' : 'Create task'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* New Sprint Modal */}
      {showNewSprint && (
        <div style={{ position:'fixed', inset:0, zIndex:200, background:'rgba(0,0,0,0.7)', display:'flex', alignItems:'center', justifyContent:'center', padding:16 }}>
          <div style={{ background:'rgba(10,13,18,0.98)', border:'1px solid rgba(255,255,255,0.12)', borderRadius:20, padding:'28px 24px', width:'100%', maxWidth:440 }}>
            <div style={{ fontSize:15, fontWeight:700, color:'#fff', marginBottom:16 }}>New Sprint</div>
            <div style={{ padding:'8px 12px', borderRadius:8, background:'rgba(181,123,238,0.06)', border:'1px solid rgba(181,123,238,0.15)', fontSize:11, color:'#b57bee', marginBottom:14 }}>
              Sprint planning is in-memory — restarts reset sprint data.
            </div>
            <div style={{ display:'flex', flexDirection:'column', gap:10 }}>
              <input value={newSprintName} onChange={e => setNewSprintName(e.target.value)} placeholder="Sprint name (e.g. Sprint 12)" autoFocus
                style={{ padding:'10px 14px', borderRadius:10, fontSize:13, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff', outline:'none' }} />
              <textarea value={newSprintGoal} onChange={e => setNewSprintGoal(e.target.value)} placeholder="Sprint goal (optional)" rows={2}
                style={{ padding:'10px 14px', borderRadius:10, fontSize:13, background:'rgba(255,255,255,0.05)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff', outline:'none', resize:'vertical', fontFamily:'var(--font-main)' }} />
            </div>
            <div style={{ display:'flex', gap:10, justifyContent:'flex-end', marginTop:16 }}>
              <button onClick={() => { setShowNewSprint(false); setNewSprintName(''); setNewSprintGoal(''); }}
                style={{ padding:'9px 18px', borderRadius:10, fontSize:13, fontWeight:700, background:'rgba(255,255,255,0.06)', border:'1px solid rgba(255,255,255,0.10)', color:'var(--text-secondary)', cursor:'pointer' }}>Cancel</button>
              <button disabled={!newSprintName.trim() || creatingSprint} onClick={handleCreateSprint}
                style={{ padding:'9px 18px', borderRadius:10, fontSize:13, fontWeight:700, background:newSprintName.trim() && !creatingSprint ? 'rgba(181,123,238,0.2)' : 'rgba(255,255,255,0.04)', border:`1px solid ${newSprintName.trim() ? 'rgba(181,123,238,0.4)' : 'rgba(255,255,255,0.08)'}`, color: newSprintName.trim() ? '#b57bee' : 'var(--text-muted)', cursor: newSprintName.trim() && !creatingSprint ? 'pointer' : 'not-allowed' }}>
                {creatingSprint ? 'Creating…' : 'Create sprint'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Board / Sprint view */}
      {viewMode === 'board' ? (
        <div style={{ flex: 1, overflowX: 'auto', overflowY: 'auto', padding: '14px 20px 32px', display: 'flex', gap: 14 }} className="scrollbar-hide task-board-columns">
          {!loading && !error && rawTasks.length === 0 ? (
            <div style={{ margin: 'auto', padding: '48px 32px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13, lineHeight: 1.8 }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>📋</div>
              <div style={{ fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>No tasks yet</div>
              <div>Create tasks via the backend API or the Chat screen by asking an agent to create a task for you.</div>
            </div>
          ) : (
            LIFECYCLE_STAGES.map(stage => {
              const stageTasks = filtered.filter(t => t.status === stage.id);
              return (
                <StageColumn
                  key={stage.id}
                  stage={stage}
                  tasks={stageTasks}
                  onApprove={handleApprove}
                  onRetry={handleRetry}
                  onCardClick={setSelectedTaskId}
                />
              );
            })
          )}
        </div>
      ) : (
        <div style={{ flex: 1, overflowY: 'auto', padding: '14px 20px 32px' }}>
          {sprintGroups.length === 0 && !loading && (
            <div style={{ padding: '48px 32px', textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
              <div style={{ fontSize: 32, marginBottom: 12 }}>🏃</div>
              <div style={{ fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 6 }}>No sprints yet</div>
              <div>Click "New Sprint +" to create your first sprint.</div>
            </div>
          )}
          {sprintGroups.map(({ sprint, tasks }) => (
            <SprintSection
              key={sprint?.sprint_id || '__none__'}
              sprint={sprint}
              tasks={tasks}
              onCardClick={setSelectedTaskId}
              onApprove={handleApprove}
              onRetry={handleRetry}
            />
          ))}
          {sprintGroups.length > 0 && <VelocityWidget />}
        </div>
      )}

      {/* Detail Panel */}
      {selectedTaskId && (
        <TaskDetailPanel
          taskId={selectedTaskId}
          onClose={() => setSelectedTaskId(null)}
          onTaskUpdated={fetchAll}
        />
      )}
    </div>
  );
}

export { TaskBoardScreen };
export default TaskBoardScreen;
