// Pure helpers for the Runs screens: state vocabulary, formatting, and the
// answers to the operator questions derived from one run record.

const TERMINAL = new Set(['succeeded', 'failed', 'cancelled', 'timed_out', 'dead_letter']);
const RETRYABLE = new Set(['failed', 'timed_out', 'dead_letter', 'cancelled']);
const CANCELLABLE = (s) => !TERMINAL.has(s);
const WAITING = new Set(['waiting_for_agent', 'waiting_for_approval', 'queued', 'retrying', 'recovering']);

export const isTerminal = (s) => TERMINAL.has(s);
export const canRetry = (s) => RETRYABLE.has(s);
export const canCancel = CANCELLABLE;
export const isBlocked = (s) => s === 'waiting_for_approval' || s === 'waiting_for_agent';

const TONE = {
  succeeded: 'var(--success)', failed: 'var(--danger)', dead_letter: 'var(--danger)',
  timed_out: 'var(--danger)', cancelled: 'var(--text-muted)', running: 'var(--accent)',
  starting: 'var(--accent)', verifying: 'var(--accent)', waiting_for_approval: 'var(--warning)',
  waiting_for_agent: 'var(--warning)', retrying: 'var(--warning)', recovering: 'var(--warning)',
  queued: 'var(--text-muted)', created: 'var(--text-muted)',
};

export const stateTone = (s) => TONE[s] || 'var(--text-muted)';
export const stateLabel = (s) => (s || 'unknown').replace(/_/g, ' ');

export function age(ts, now = Date.now() / 1000) {
  if (!ts) return '—';
  const s = Math.max(0, Math.floor(now - ts));
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : null);
const money = (v) => `$${v.toFixed(v < 1 ? 4 : 2)}`;

/** "$0.0420 / $1.00", "$0.0420", "budget $1.00" or "—". */
export function costText(run) {
  const spent = num(run?.usage?.cost_usd ?? run?.usage?.cost);
  const cap = num(run?.budget?.max_cost_usd ?? run?.budget?.cost_usd);
  if (spent != null && cap != null) return `${money(spent)} / ${money(cap)}`;
  if (spent != null) return money(spent);
  if (cap != null) return `budget ${money(cap)}`;
  return '—';
}

/** Where the run executes: runtime and model, whichever are known. */
export function whereText(run) {
  const parts = [run?.runtime_id, run?.resolved_model || run?.requested_model].filter(Boolean);
  return parts.length ? parts.join(' · ') : '—';
}

/** What the run is doing right now, in words. */
export function doingText(run) {
  if (!run) return '—';
  if (run.waiting_reason) return run.waiting_reason;
  if (run.failure_reason && isTerminal(run.state)) return run.failure_reason;
  if (run.phase) return run.phase;
  return WAITING.has(run.state) ? stateLabel(run.state) : (isTerminal(run.state) ? 'finished' : 'working');
}

/** Whether a crashed worker can be recovered, from /api/runs/capabilities. */
export function recoverText(caps, run) {
  if (run && isTerminal(run.state)) return canRetry(run.state) ? 'Retry available' : 'Finished';
  if (!caps) return 'Unknown';
  if (!caps.recovery_enabled || caps.recovery === 'none') return 'No automatic recovery';
  const where = caps.recovery === 'cross_host' ? 'on any host' : 'on this host';
  return `Recovers ${where}${caps.checkpoint_durable ? ', checkpointed' : ''}`;
}
