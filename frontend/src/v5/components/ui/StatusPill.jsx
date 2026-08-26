import React from 'react';

/**
 * StatusPill — the one status indicator for the whole app.
 *
 * Replaces the ~16 local variants that grew across screens (Badge, StatusDot,
 * StatusBadge, Pill, NoteStatusPill, …), each with its own colors and shape.
 * The vocabulary lives in STATUS_META (the pattern proven by the old
 * AgentTaskStatus TASK_STATUS_META); screens map their domain states onto
 * these keys instead of inventing new colors.
 */

const C = {
  success: 'var(--success)',
  accent: 'var(--accent)',
  warning: 'var(--warning)',
  danger: 'var(--danger)',
  info: 'var(--info)',
  muted: 'var(--text-muted)',
};

export const STATUS_META = {
  // lifecycle
  done:      { label: 'Done',           color: C.success },
  running:   { label: 'Working',        color: C.accent  },
  pending:   { label: 'Pending',        color: C.muted   },
  scheduled: { label: 'Scheduled',      color: C.info    },
  approval:  { label: 'Needs approval', color: C.warning },
  failed:    { label: 'Failed',         color: C.danger  },
  idle:      { label: 'Idle',           color: C.muted   },
  // connectivity
  connected:    { label: 'Connected',    color: C.success },
  degraded:     { label: 'Degraded',     color: C.warning },
  unavailable:  { label: 'Unavailable',  color: C.danger  },
  unconfigured: { label: 'Not set up',   color: C.muted   },
};

const TONE_BG = (color) => `color-mix(in srgb, ${color} 10%, transparent)`;
const TONE_BORDER = (color) => `color-mix(in srgb, ${color} 24%, transparent)`;

/**
 * @param {string}  status   key into STATUS_META (unknown keys render muted)
 * @param {string=} label    override the meta label (e.g. "Working · 70%")
 * @param {string=} color    override the meta color (escape hatch for domain
 *                           tones not in the vocabulary — use sparingly)
 * @param {boolean=} dot     show the leading dot (default true)
 * @param {'sm'|'md'=} size  sm for table cells, md (default) elsewhere
 */
export default function StatusPill({ status, label, color, dot = true, size = 'md', style = {} }) {
  const meta = STATUS_META[status] || { label: status || '—', color: C.muted };
  const c = color || meta.color;
  const text = label ?? meta.label;
  const sm = size === 'sm';
  return (
    <span
      style={{
        display: 'inline-flex', alignItems: 'center', gap: sm ? 5 : 7,
        fontSize: sm ? 11 : 12.5, fontWeight: 700, lineHeight: 1,
        padding: sm ? '4px 9px' : '5px 11px', borderRadius: 999,
        color: c, background: TONE_BG(c), border: `1px solid ${TONE_BORDER(c)}`,
        whiteSpace: 'nowrap',
        ...style,
      }}
    >
      {dot && <span style={{ width: sm ? 6 : 7, height: sm ? 6 : 7, borderRadius: '50%', background: c, flexShrink: 0 }} />}
      {text}
    </span>
  );
}

export { StatusPill };
