/* eslint-disable jsx-a11y/anchor-is-valid, no-unused-vars -- ported design prototype; hardened when wired to live data */
import React from 'react';


// taskboard.jsx — Task / Job Lifecycle Board

const LIFECYCLE_STAGES = [
  { id: 'classify',  label: 'Classify',  color: '#6e7786', desc: 'Type detected' },
  { id: 'clarify',   label: 'Clarify',   color: '#7c9dff', desc: 'Scope confirmed' },
  { id: 'plan',      label: 'Plan',      color: '#c4b5fd', desc: 'Steps outlined' },
  { id: 'execute',   label: 'Execute',   color: '#5da2ff', desc: 'Agent running' },
  { id: 'verify',    label: 'Verify',    color: '#ffbd66', desc: 'Tests pass' },
  { id: 'judge',     label: 'Review',    color: '#ff9d66', desc: 'Release gate' },
  { id: 'monitor',   label: 'Monitor',   color: '#46d9a4', desc: 'Live / closed' },
];

const BOARD_TASKS = [
  {
    id: 't-001', title: 'Fix null-check in checkout service', stage: 'monitor',
    priority: 'high', type: 'bug', agent: 'Dev Agent',
    evidence: { pr: '#1842', tests: '47 passed', issue: '#312' },
    updated: '2m ago', trusted: true,
  },
  {
    id: 't-002', title: 'Security scan — auth module CVE', stage: 'verify',
    priority: 'urgent', type: 'security', agent: 'Security Agent',
    evidence: { tests: 'Bandit clean', issue: '#315' },
    updated: '8m ago', trusted: false,
  },
  {
    id: 't-003', title: 'Migrate cart DB schema to v3', stage: 'execute',
    priority: 'high', type: 'task', agent: 'Dev Agent',
    evidence: {},
    updated: '14m ago', trusted: false,
  },
  {
    id: 't-004', title: 'Weekly dep audit — 4 upgrades', stage: 'plan',
    priority: 'medium', type: 'task', agent: 'Release Agent',
    evidence: {},
    updated: '1h ago', trusted: false,
  },
  {
    id: 't-005', title: 'Add rate limiting to /api/chat', stage: 'clarify',
    priority: 'medium', type: 'task', agent: null,
    evidence: {},
    updated: '2h ago', trusted: false,
  },
  {
    id: 't-006', title: 'Fix mobile layout regression', stage: 'classify',
    priority: 'high', type: 'bug', agent: null,
    evidence: { issue: '#318' },
    updated: '3h ago', trusted: false,
  },
  {
    id: 't-007', title: 'Changelog audit — v4.1 release', stage: 'judge',
    priority: 'medium', type: 'task', agent: 'Release Agent',
    evidence: { pr: '#1845', tests: '100% pass' },
    updated: '45m ago', trusted: false,
  },
];

const priorityColors = { urgent: '#ff6b7d', high: '#ffbd66', medium: '#7c9dff', low: 'var(--text-muted)' };
const typeColors = { bug: '#ff6b7d', security: '#ffbd66', task: 'var(--accent)' };

function StageColumn({ stage, tasks, onApprove }) {
  return (
    <div style={{
      minWidth: 220, maxWidth: 260, flexShrink: 0,
      display: 'flex', flexDirection: 'column', gap: 8,
    }}>
      {/* Column header */}
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

      {/* Cards */}
      {tasks.map(task => (
        <TaskCard key={task.id} task={task} stageColor={stage.color} onApprove={onApprove}/>
      ))}
    </div>
  );
}

function TaskCard({ task, stageColor, onApprove }) {
  const hasEvidence = Object.keys(task.evidence).length > 0;

  return (
    <div style={{
      borderRadius: 14, border: `1px solid ${task.trusted ? 'rgba(70,217,164,0.20)' : 'rgba(255,255,255,0.09)'}`,
      background: task.trusted ? 'rgba(70,217,164,0.04)' : 'rgba(255,255,255,0.03)',
      padding: '12px 14px', cursor: 'pointer',
      transition: 'all 0.18s ease',
      animation: 'fadeSlideUp 0.3s ease-out',
    }}
    onMouseEnter={e => { e.currentTarget.style.background = task.trusted ? 'rgba(70,217,164,0.07)' : 'rgba(255,255,255,0.055)'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
    onMouseLeave={e => { e.currentTarget.style.background = task.trusted ? 'rgba(70,217,164,0.04)' : 'rgba(255,255,255,0.03)'; e.currentTarget.style.transform = 'none'; }}>
      {/* Top row */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6, marginBottom: 6 }}>
        <span style={{ width: 6, height: 6, borderRadius: '50%', background: priorityColors[task.priority] || 'var(--text-muted)', flexShrink: 0, marginTop: 4 }}/>
        <span style={{ fontSize: 12, fontWeight: 600, color: task.trusted ? '#a7f3d0' : 'var(--text-primary)', lineHeight: 1.5, flex: 1 }}>{task.title}</span>
      </div>

      {/* Type + priority badges */}
      <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 8 }}>
        <span style={{
          fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', textTransform: 'uppercase',
          padding: '2px 7px', borderRadius: 999, color: typeColors[task.type],
          background: `${typeColors[task.type]}15`, border: `1px solid ${typeColors[task.type]}30`,
        }}>{task.type}</span>
        <span style={{
          fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.12em', textTransform: 'uppercase',
          padding: '2px 7px', borderRadius: 999, color: priorityColors[task.priority],
          background: `${priorityColors[task.priority]}12`, border: `1px solid ${priorityColors[task.priority]}28`,
        }}>{task.priority}</span>
        {task.trusted && (
          <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.10em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 999, color: '#46d9a4', background: 'rgba(70,217,164,0.12)', border: '1px solid rgba(70,217,164,0.25)' }}>verified ✓</span>
        )}
      </div>

      {/* Evidence chips */}
      {hasEvidence && (
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginBottom: 8 }}>
          {task.evidence.pr && <a href="#" onClick={e => e.stopPropagation()} style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--accent)', textDecoration: 'none', padding: '2px 7px', borderRadius: 5, background: 'rgba(93,162,255,0.10)', border: '1px solid rgba(93,162,255,0.20)' }}>PR {task.evidence.pr}</a>}
          {task.evidence.issue && <a href="#" onClick={e => e.stopPropagation()} style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textDecoration: 'none', padding: '2px 7px', borderRadius: 5, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.10)' }}>Issue {task.evidence.issue}</a>}
          {task.evidence.tests && <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: '#46d9a4', padding: '2px 7px', borderRadius: 5, background: 'rgba(70,217,164,0.08)', border: '1px solid rgba(70,217,164,0.18)' }}>✓ {task.evidence.tests}</span>}
        </div>
      )}

      {/* Footer */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 }}>
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          {task.agent ? `@${task.agent}` : 'Unassigned'}
        </span>
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{task.updated}</span>
      </div>

      {/* Approve button for judge stage */}
      {task.stage === 'judge' && (
        <button onClick={e => { e.stopPropagation(); onApprove(task.id); }} style={{
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
    </div>
  );
}

function TaskBoardScreen() {
  const [tasks, setTasks] = React.useState(BOARD_TASKS);
  const [filter, setFilter] = React.useState('all');

  const handleApprove = (id) => {
    setTasks(prev => prev.map(t => t.id === id ? { ...t, stage: 'monitor', trusted: true, updated: 'just now' } : t));
  };

  const filtered = filter === 'all' ? tasks : tasks.filter(t => t.priority === filter || t.type === filter);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden' }}>
      {/* Header */}
      <div style={{ padding: '20px 20px 0', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 10, marginBottom: 14 }}>
          <div>
            <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--accent)', letterSpacing: '0.18em', textTransform: 'uppercase', marginBottom: 4 }}>Task Lifecycle</div>
            <h1 style={{ fontSize: 22, fontWeight: 800, color: '#fff', letterSpacing: '-0.04em', lineHeight: 1.1 }}>Job Board</h1>
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {['all', 'urgent', 'bug', 'security'].map(f => (
              <button key={f} onClick={() => setFilter(f)} style={{
                padding: '5px 14px', borderRadius: 999, fontSize: 11, fontWeight: 600, cursor: 'pointer',
                background: filter === f ? 'rgba(93,162,255,0.15)' : 'rgba(255,255,255,0.05)',
                border: `1px solid ${filter === f ? 'rgba(93,162,255,0.35)' : 'rgba(255,255,255,0.10)'}`,
                color: filter === f ? '#fff' : 'var(--text-muted)',
                textTransform: 'capitalize', transition: 'all 0.15s ease',
              }}>{f}</button>
            ))}
          </div>
        </div>

        {/* Stage legend */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, overflowX: 'auto', paddingBottom: 6, flexWrap: 'nowrap' }} className="scrollbar-hide">
          {LIFECYCLE_STAGES.map((s, i) => (
            <React.Fragment key={s.id}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}>
                <span style={{ width: 6, height: 6, borderRadius: '50%', background: s.color, display: 'inline-block' }}/>
                <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>{s.label}</span>
              </div>
              {i < LIFECYCLE_STAGES.length - 1 && <span style={{ color: 'rgba(255,255,255,0.15)', fontSize: 10, flexShrink: 0 }}>›</span>}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Board */}
      <div style={{ flex: 1, overflowX: 'auto', overflowY: 'auto', padding: '14px 20px 32px', display: 'flex', gap: 14 }} className="scrollbar-hide">
        {LIFECYCLE_STAGES.map(stage => {
          const stageTasks = filtered.filter(t => t.stage === stage.id);
          return <StageColumn key={stage.id} stage={stage} tasks={stageTasks} onApprove={handleApprove}/>;
        })}
      </div>
    </div>
  );
}

export { TaskBoardScreen };
export default TaskBoardScreen;
