import React from 'react';
import { AlertCircle, CheckCircle, Clock, Loader, ListChecks } from 'lucide-react';

// ── Single source of truth for how a TaskStatus renders ──────────────────────
// Keys mirror backend tasks/models.py::TaskStatus exactly. Everything that
// shows a task status on the dashboard reads this map, so the vocabulary stays
// consistent instead of each panel inventing its own colours/labels.
export const TASK_STATUS_META = {
  todo:                { label: 'To do',      color: 'var(--text-tertiary)' },
  in_progress:         { label: 'Running',    color: 'var(--accent)' },
  in_review:           { label: 'In review',  color: 'var(--info)' },
  blocked:             { label: 'Blocked',    color: 'var(--warning)' },
  needs_clarification: { label: 'Needs input', color: 'var(--warning)' },
  done:                { label: 'Completed',  color: 'var(--success)' },
  failed:              { label: 'Failed',     color: 'var(--danger)' },
};

// Display order for the summary chips — active/attention states first so the
// most operationally relevant numbers lead.
const SUMMARY_ORDER = [
  'in_progress', 'needs_clarification', 'blocked', 'in_review', 'failed', 'done', 'todo',
];

function statusMeta(status) {
  return TASK_STATUS_META[status] || { label: status || 'Unknown', color: 'var(--text-tertiary)' };
}

function formatWhen(iso) {
  if (!iso) return '';
  // Match the Recent Activity feed's compact "YYYY-MM-DD HH:MM:SS" rendering.
  return String(iso).replace('T', ' ').split('.')[0];
}

function StatusPill({ status }) {
  const meta = statusMeta(status);
  return (
    <span
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[0.75rem] font-medium whitespace-nowrap"
      style={{ color: meta.color, background: `${meta.color}14`, border: `1px solid ${meta.color}33` }}
    >
      <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: meta.color }} />
      {meta.label}
    </span>
  );
}

/**
 * AgentTaskStatus — a compact, information-dense view of agent task state.
 *
 * Presentational only: the parent fetches `counts` (from getTaskCounts) and
 * `tasks` (from listTasks) and passes them in, so this stays trivially
 * testable and reusable across screens. It deliberately does NOT stream live
 * events — that is AgentActivityFeed's job — it summarises the durable task
 * board so the dashboard answers "what are the agents working on / stuck on /
 * done with" at a glance without duplicating the chat-scoped feed.
 */
export default function AgentTaskStatus({
  counts = {},
  tasks = [],
  loading = false,
  onSelectTask,
  onViewAll,
  maxRows = 6,
  className = '',
}) {
  const total = Object.values(counts).reduce((sum, n) => sum + (Number(n) || 0), 0);
  const summary = SUMMARY_ORDER
    .filter((status) => (counts[status] || 0) > 0)
    .map((status) => ({ status, count: counts[status] }));
  const rows = tasks.slice(0, maxRows);

  return (
    <div className={`space-y-3 ${className}`} data-testid="agent-task-status">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-[1.15rem] font-semibold text-[var(--text-primary)]">
          <ListChecks size={16} className="text-[var(--accent)]" />
          Agent Tasks
          {total > 0 && (
            <span className="text-[0.85rem] font-normal text-[var(--text-tertiary)]">({total})</span>
          )}
        </h2>
        {onViewAll && (
          <button
            onClick={onViewAll}
            className="text-[0.9rem] font-medium text-[var(--accent)] hover:text-[var(--accent-hover)]"
          >
            View all
          </button>
        )}
      </div>

      {/* Status summary chips — one number per active status */}
      {summary.length > 0 && (
        <div className="flex flex-wrap gap-2" data-testid="task-status-summary">
          {summary.map(({ status, count }) => {
            const meta = statusMeta(status);
            return (
              <div
                key={status}
                data-testid={`task-status-chip-${status}`}
                className="inline-flex items-center gap-2 px-2.5 py-1 rounded-lg text-[0.85rem]"
                style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)' }}
              >
                <span className="w-2 h-2 rounded-full shrink-0" style={{ background: meta.color }} />
                <span className="font-semibold text-[var(--text-primary)]">{count}</span>
                <span className="text-[var(--text-secondary)]">{meta.label}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Recent task rows */}
      <div className="bg-[var(--bg-surface)] border border-[var(--border)] rounded-xl overflow-hidden">
        <div className="divide-y divide-[var(--border)]">
          {loading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center gap-3 px-4 py-3">
                <div className="skeleton h-2 w-2/3" />
              </div>
            ))
          ) : rows.length > 0 ? (
            rows.map((task) => {
              const id = task.task_id || task.id;
              const when = formatWhen(task.updated_at || task.created_at);
              return (
                <button
                  key={id}
                  data-testid={`task-row-${id}`}
                  onClick={onSelectTask ? () => onSelectTask(task) : undefined}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-[var(--bg-elevated)] transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-[0.9rem] text-[var(--text-primary)] truncate">{task.title}</div>
                    <div className="flex items-center gap-2 mt-0.5 text-[0.78rem] text-[var(--text-tertiary)]">
                      {task.agent_id && <span className="font-mono truncate max-w-[10rem]">{task.agent_id}</span>}
                      {when && (
                        <span className="flex items-center gap-1 font-mono">
                          <Clock size={8} />{when}
                        </span>
                      )}
                    </div>
                  </div>
                  <StatusPill status={task.status} />
                </button>
              );
            })
          ) : (
            <div className="px-6 py-8 text-center">
              <ListChecks size={18} className="text-[var(--text-tertiary)] mx-auto mb-3" />
              <p className="text-[0.9rem] text-[var(--text-tertiary)]">No agent tasks yet</p>
              <p className="text-[0.85rem] font-mono text-[var(--text-muted)] mt-2">
                Tasks appear here as agents pick up work
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Tiny status icon helpers exported for reuse/consistency elsewhere.
export const STATUS_ICON = { done: CheckCircle, failed: AlertCircle, in_progress: Loader };
