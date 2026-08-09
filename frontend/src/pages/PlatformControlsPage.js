/**
 * PlatformControlsPage — dashboard surface for every operator-controllable
 * feature switch and multi-option setting.
 *
 * Replaces editing ~100 true/false rows in the Render environment and
 * redeploying. Each control shows where its current value comes from
 * (dashboard override, Render environment, or the code default) and whether a
 * change takes effect immediately or needs a restart.
 *
 * Backend: packages/config/control_registry.py + control_overrides.py.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronRight,
  Loader2,
  RefreshCw,
  RotateCcw,
  Search,
  ShieldAlert,
  SlidersHorizontal,
} from 'lucide-react';
import {
  fmtErr,
  getPlatformControls,
  resetPlatformControl,
  setPlatformControls,
} from '../api';

function cls(...parts) {
  return parts.filter(Boolean).join(' ');
}

const C = {
  surface: 'var(--bg-surface)',
  border: 'var(--border)',
  primary: 'var(--text-primary)',
  secondary: 'var(--text-secondary)',
  tertiary: 'var(--text-tertiary)',
  muted: 'var(--text-muted)',
};

const SOURCE_LABEL = {
  override: 'Dashboard',
  environment: 'Render env',
  default: 'Code default',
};

const SOURCE_STYLE = {
  override: 'border-[#002FA7]/40 bg-[#002FA7]/10 text-[#4477FF]',
  environment: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
  default: 'border-white/10 bg-white/5 text-[color:var(--text-muted)]',
};

const RISK_STYLE = {
  high: 'border-red-500/30 bg-red-500/10 text-red-400',
  medium: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
};

function isOn(value) {
  return String(value).trim().toLowerCase() === 'true';
}

/** Toggle switch. Controlled — the parent owns the pending value. */
function Toggle({ checked, disabled, onChange, label }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cls(
        'relative h-6 w-11 shrink-0 rounded-full border transition-colors',
        checked ? 'border-[#002FA7] bg-[#002FA7]' : 'border-white/15 bg-white/10',
        disabled && 'cursor-not-allowed opacity-50',
      )}
    >
      <span
        className={cls(
          'absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all',
          checked ? 'left-6' : 'left-0.5',
        )}
      />
    </button>
  );
}

/** One control row: label, help, current-source badge, and its editor. */
function ControlRow({ control, pending, onChange, onReset, busy }) {
  const dirty = pending !== undefined;
  const value = dirty ? pending : control.value;
  const riskStyle = RISK_STYLE[control.risk];
  const missing = control.missing_requirements || [];

  return (
    <div
      className={cls(
        'flex flex-col gap-3 border-t px-4 py-3.5 md:flex-row md:items-start md:gap-6',
        dirty && 'bg-[#002FA7]/5',
      )}
      style={{ borderColor: C.border }}
      data-testid={`control-${control.key}`}
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm font-medium" style={{ color: C.primary }}>
            {control.label}
          </span>
          <span
            className={cls('rounded border px-1.5 py-0.5 text-[10px] font-medium', SOURCE_STYLE[control.source])}
          >
            {SOURCE_LABEL[control.source] || control.source}
          </span>
          {riskStyle && (
            <span className={cls('rounded border px-1.5 py-0.5 text-[10px] font-medium', riskStyle)}>
              {control.risk === 'high' ? 'High impact' : 'Medium impact'}
            </span>
          )}
          {!control.live && (
            <span
              className="rounded border px-1.5 py-0.5 text-[10px]"
              style={{ borderColor: C.border, color: C.muted }}
              title="The code reads this value once at startup, so a change lands on the next restart."
            >
              Restart required
            </span>
          )}
        </div>
        {control.help && (
          <p className="mt-1 text-xs leading-relaxed" style={{ color: C.tertiary }}>
            {control.help}
          </p>
        )}
        <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
          <code className="text-[10px]" style={{ color: C.muted }}>
            {control.key}
          </code>
          {missing.length > 0 && (
            <span className="flex items-center gap-1 text-[10px] text-amber-400">
              <AlertTriangle size={11} />
              Inactive until {missing.join(', ')} is set
            </span>
          )}
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-2 md:w-72 md:justify-end">
        {control.kind === 'toggle' && (
          <Toggle
            checked={isOn(value)}
            disabled={busy}
            label={control.label}
            onChange={(next) => onChange(control.key, next ? 'true' : 'false')}
          />
        )}
        {control.kind === 'choice' && (
          <select
            value={value}
            disabled={busy}
            aria-label={control.label}
            onChange={(e) => onChange(control.key, e.target.value)}
            className="w-full rounded-lg border px-2.5 py-1.5 text-xs md:w-56"
            style={{ background: 'var(--bg-base)', borderColor: C.border, color: C.primary }}
          >
            {control.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
        {control.kind === 'number' && (
          <input
            type="number"
            value={value}
            disabled={busy}
            aria-label={control.label}
            min={control.minimum ?? undefined}
            max={control.maximum ?? undefined}
            onChange={(e) => onChange(control.key, e.target.value)}
            className="w-28 rounded-lg border px-2.5 py-1.5 text-xs"
            style={{ background: 'var(--bg-base)', borderColor: C.border, color: C.primary }}
          />
        )}
        <button
          type="button"
          onClick={() => onReset(control.key)}
          disabled={busy || control.source !== 'override'}
          title="Drop the dashboard override and follow the Render environment again"
          className="rounded-lg border p-1.5 transition-colors enabled:hover:bg-white/5 disabled:opacity-25"
          style={{ borderColor: C.border, color: C.secondary }}
        >
          <RotateCcw size={13} />
        </button>
      </div>
    </div>
  );
}

/** One collapsible group of related controls. */
function ControlGroup({ group, pending, onChange, onReset, busy, defaultOpen, forceOpen }) {
  const [collapsed, setCollapsed] = useState(!defaultOpen);
  // A search hit inside a collapsed group would otherwise be invisible, which
  // reads as "no results" rather than "collapsed".
  const open = forceOpen || !collapsed;
  const overrides = group.controls.filter((c) => c.source === 'override').length;

  return (
    <section
      className="overflow-hidden rounded-2xl border"
      style={{ background: C.surface, borderColor: C.border }}
    >
      <button
        type="button"
        onClick={() => setCollapsed((v) => !v)}
        className="flex w-full items-start gap-3 px-4 py-3.5 text-left transition-colors hover:bg-white/[0.02]"
      >
        {open ? <ChevronDown size={16} className="mt-0.5 shrink-0" style={{ color: C.muted }} />
              : <ChevronRight size={16} className="mt-0.5 shrink-0" style={{ color: C.muted }} />}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-semibold" style={{ color: C.primary }}>{group.label}</h2>
            <span className="text-[11px]" style={{ color: C.muted }}>
              {group.controls.length} setting{group.controls.length === 1 ? '' : 's'}
            </span>
            {overrides > 0 && (
              <span className="rounded border border-[#002FA7]/40 bg-[#002FA7]/10 px-1.5 py-0.5 text-[10px] text-[#4477FF]">
                {overrides} set here
              </span>
            )}
          </div>
          {group.help && (
            <p className="mt-1 text-xs leading-relaxed" style={{ color: C.tertiary }}>{group.help}</p>
          )}
        </div>
      </button>
      {open && group.controls.map((control) => (
        <ControlRow
          key={control.key}
          control={control}
          pending={pending[control.key]}
          onChange={onChange}
          onReset={onReset}
          busy={busy}
        />
      ))}
    </section>
  );
}

export default function PlatformControlsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [restartKeys, setRestartKeys] = useState([]);
  const [pending, setPending] = useState({});
  const [query, setQuery] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const r = await getPlatformControls();
      setData(r.data);
    } catch (e) {
      setError(fmtErr(e?.response?.data?.detail) || e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleChange = useCallback((key, value) => {
    setPending((prev) => ({ ...prev, [key]: value }));
  }, []);

  // Applying the server's fresh snapshot is what clears the dirty highlight —
  // the saved values become the new baseline, so nothing stays pending.
  const applyResult = useCallback((result) => {
    setData(result);
    setPending({});
    setRestartKeys(result.restart_required || []);
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const r = await setPlatformControls(pending);
      applyResult(r.data);
      const count = (r.data.changed || []).length;
      setNotice(count ? `Applied ${count} change${count === 1 ? '' : 's'}.` : 'No effective change.');
    } catch (e) {
      setError(fmtErr(e?.response?.data?.detail) || e.message);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async (key) => {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      const r = await resetPlatformControl(key);
      applyResult(r.data);
      setNotice(`${key} now follows the Render environment.`);
    } catch (e) {
      setError(fmtErr(e?.response?.data?.detail) || e.message);
    } finally {
      setSaving(false);
    }
  };

  const groups = useMemo(() => {
    const all = data?.groups || [];
    const needle = query.trim().toLowerCase();
    if (!needle) return all;
    return all
      .map((group) => ({
        ...group,
        controls: group.controls.filter(
          (c) =>
            c.label.toLowerCase().includes(needle) ||
            c.key.toLowerCase().includes(needle) ||
            (c.help || '').toLowerCase().includes(needle),
        ),
      }))
      .filter((group) => group.controls.length > 0);
  }, [data, query]);

  const pendingCount = Object.keys(pending).length;

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="animate-spin" size={22} style={{ color: C.muted }} />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 md:px-6">
      <header className="mb-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <SlidersHorizontal size={20} style={{ color: C.secondary }} />
            <div>
              <h1 className="text-lg font-semibold" style={{ color: C.primary }}>Platform Controls</h1>
              <p className="text-xs" style={{ color: C.tertiary }}>
                {data?.control_count ?? 0} settings · {data?.override_count ?? 0} set from this dashboard
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={load}
            disabled={saving}
            className="flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs transition-colors hover:bg-white/5 disabled:opacity-50"
            style={{ borderColor: C.border, color: C.secondary }}
          >
            <RefreshCw size={13} /> Refresh
          </button>
        </div>
        <p className="mt-3 text-xs leading-relaxed" style={{ color: C.tertiary }}>
          Values set here are stored in the database and re-applied on every boot, taking
          precedence over the Render environment. Reset a control to hand it back to Render.
          Secrets and connection URLs are deliberately not editable here.
        </p>
      </header>

      <div className="relative mb-4">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2" style={{ color: C.muted }} />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search settings…"
          className="w-full rounded-lg border py-2 pl-9 pr-3 text-xs"
          style={{ background: C.surface, borderColor: C.border, color: C.primary }}
        />
      </div>

      {error && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" /> {error}
        </div>
      )}
      {notice && !error && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-400">
          <Check size={14} className="mt-0.5 shrink-0" /> {notice}
        </div>
      )}
      {restartKeys.length > 0 && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-400">
          <ShieldAlert size={14} className="mt-0.5 shrink-0" />
          <span>
            Saved, but the running process already read {restartKeys.length === 1 ? 'this value' : 'these values'} at
            startup — restart the backend to pick {restartKeys.length === 1 ? 'it' : 'them'} up:{' '}
            <code>{restartKeys.join(', ')}</code>
          </span>
        </div>
      )}

      <div className="flex flex-col gap-3 pb-24">
        {groups.map((group, index) => (
          <ControlGroup
            key={group.id}
            group={group}
            pending={pending}
            onChange={handleChange}
            onReset={handleReset}
            busy={saving}
            defaultOpen={index === 0}
            forceOpen={Boolean(query)}
          />
        ))}
        {groups.length === 0 && (
          <p className="py-10 text-center text-xs" style={{ color: C.muted }}>
            No settings match “{query}”.
          </p>
        )}
      </div>

      {pendingCount > 0 && (
        <div
          className="fixed bottom-0 left-0 right-0 z-20 border-t px-4 py-3 lg:left-[280px]"
          style={{ background: C.surface, borderColor: C.border }}
        >
          <div className="mx-auto flex max-w-5xl items-center justify-between gap-3">
            <span className="text-xs" style={{ color: C.secondary }}>
              {pendingCount} unsaved change{pendingCount === 1 ? '' : 's'}
            </span>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setPending({})}
                disabled={saving}
                className="rounded-lg border px-3 py-1.5 text-xs transition-colors hover:bg-white/5 disabled:opacity-50"
                style={{ borderColor: C.border, color: C.secondary }}
              >
                Discard
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                className="flex items-center gap-1.5 rounded-lg bg-[#002FA7] px-4 py-1.5 text-xs font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {saving ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />}
                Apply
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
