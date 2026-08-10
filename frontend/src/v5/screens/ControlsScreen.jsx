/**
 * ControlsScreen — every operator-controllable feature switch and multi-option
 * setting, on the v5 dashboard.
 *
 * Replaces editing ~100 true/false rows in the Render environment and
 * redeploying. Each control shows where its current value comes from
 * (dashboard override, Render environment, or the code default) and whether a
 * change takes effect immediately or needs a restart.
 *
 * Written with inline styles rather than Tailwind utilities, like every other
 * v5 screen: `.v5-root *` in V5App's theme sets `margin:0; padding:0` at equal
 * specificity to a Tailwind spacing utility and is injected after the CSS
 * bundle, so `px-4` inside this shell loses the cascade and renders flush.
 *
 * Backend: packages/config/control_registry.py + control_overrides.py.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  fmtErr,
  getPlatformControls,
  resetPlatformControl,
  setPlatformControls,
} from '../../api';

const SOURCE_LABEL = {
  override: 'Dashboard',
  environment: 'Render env',
  default: 'Code default',
};

const SOURCE_STYLE = {
  override: { border: '1px solid rgba(93,162,255,0.40)', background: 'rgba(93,162,255,0.10)', color: '#7ab1ff' },
  environment: { border: '1px solid rgba(255,189,102,0.30)', background: 'rgba(255,189,102,0.10)', color: '#ffbd66' },
  default: { border: '1px solid rgba(255,255,255,0.10)', background: 'rgba(255,255,255,0.04)', color: 'var(--text-muted)' },
};

const RISK_STYLE = {
  high: { border: '1px solid rgba(255,107,125,0.30)', background: 'rgba(255,107,125,0.10)', color: '#ff6b7d' },
  medium: { border: '1px solid rgba(255,189,102,0.30)', background: 'rgba(255,189,102,0.10)', color: '#ffbd66' },
};

const PILL = {
  borderRadius: 6, padding: '2px 6px', fontSize: 10, fontWeight: 600,
  fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap',
};

const FIELD = {
  borderRadius: 10, padding: '7px 10px', fontSize: 12, outline: 'none',
  background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.10)',
  color: 'var(--text-primary)', fontFamily: 'var(--font-main)',
};

const BANNER = (tone) => ({
  display: 'flex', alignItems: 'flex-start', gap: 8, marginBottom: 14,
  padding: '9px 12px', borderRadius: 10, fontSize: 12, lineHeight: 1.55,
  background: `rgba(${tone},0.08)`, border: `1px solid rgba(${tone},0.22)`,
});

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
      style={{
        position: 'relative', height: 24, width: 44, flexShrink: 0, borderRadius: 999,
        cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
        transition: 'background 0.15s, border-color 0.15s',
        background: checked ? 'var(--accent)' : 'rgba(255,255,255,0.10)',
        border: `1px solid ${checked ? 'var(--accent)' : 'rgba(255,255,255,0.15)'}`,
      }}
    >
      <span style={{
        position: 'absolute', top: 2, left: checked ? 22 : 2, height: 16, width: 16,
        borderRadius: '50%', background: '#fff', transition: 'left 0.15s',
      }}/>
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
      data-testid={`control-${control.key}`}
      style={{
        display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', gap: 14,
        padding: '13px 15px', borderTop: '1px solid var(--border)',
        background: dirty ? 'rgba(93,162,255,0.05)' : 'transparent',
      }}
    >
      <div style={{ flex: '1 1 260px', minWidth: 0 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 7 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{control.label}</span>
          <span style={{ ...PILL, ...(SOURCE_STYLE[control.source] || SOURCE_STYLE.default) }}>
            {SOURCE_LABEL[control.source] || control.source}
          </span>
          {riskStyle && (
            <span style={{ ...PILL, ...riskStyle }}>
              {control.risk === 'high' ? 'High impact' : 'Medium impact'}
            </span>
          )}
          {!control.live && (
            <span
              title="The code reads this value once at startup, so a change lands on the next restart."
              style={{ ...PILL, border: '1px solid var(--border)', color: 'var(--text-muted)' }}
            >
              Restart required
            </span>
          )}
        </div>
        {control.help && (
          <p style={{ marginTop: 4, fontSize: 12, lineHeight: 1.55, color: 'var(--text-tertiary)' }}>
            {control.help}
          </p>
        )}
        <div style={{ marginTop: 5, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '3px 12px' }}>
          <code style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
            {control.key}
          </code>
          {missing.length > 0 && (
            <span style={{ fontSize: 10, color: 'var(--warning)' }}>
              ⚠ Inactive until {missing.join(', ')} is set
            </span>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginLeft: 'auto' }}>
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
            style={{ ...FIELD, minWidth: 180 }}
          >
            {control.options.map((option) => (
              <option key={option.value} value={option.value} style={{ background: 'var(--bg-surface)' }}>
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
            style={{ ...FIELD, width: 104, fontFamily: 'var(--font-mono)' }}
          />
        )}
        <button
          type="button"
          onClick={() => onReset(control.key)}
          disabled={busy || control.source !== 'override'}
          title="Drop the dashboard override and follow the Render environment again"
          style={{
            borderRadius: 9, padding: '6px 9px', fontSize: 12, lineHeight: 1,
            border: '1px solid var(--border)', background: 'transparent',
            color: 'var(--text-secondary)',
            cursor: busy || control.source !== 'override' ? 'not-allowed' : 'pointer',
            opacity: busy || control.source !== 'override' ? 0.25 : 1,
          }}
        >
          ↺
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
    <section style={{
      overflow: 'hidden', borderRadius: 16, background: 'var(--bg-surface)',
      border: '1px solid var(--border)',
    }}>
      <button
        type="button"
        onClick={() => setCollapsed((v) => !v)}
        style={{
          display: 'flex', width: '100%', alignItems: 'flex-start', gap: 11,
          padding: '13px 15px', textAlign: 'left', cursor: 'pointer',
          background: 'transparent', border: 'none', color: 'inherit',
        }}
      >
        <span style={{ marginTop: 1, fontSize: 11, color: 'var(--text-muted)' }}>{open ? '▾' : '▸'}</span>
        <span style={{ flex: 1, minWidth: 0 }}>
          <span style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{group.label}</h2>
            <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
              {group.controls.length} setting{group.controls.length === 1 ? '' : 's'}
            </span>
            {overrides > 0 && (
              <span style={{ ...PILL, ...SOURCE_STYLE.override }}>{overrides} set here</span>
            )}
          </span>
          {group.help && (
            <p style={{ marginTop: 4, fontSize: 12, lineHeight: 1.55, color: 'var(--text-tertiary)' }}>
              {group.help}
            </p>
          )}
        </span>
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

export default function ControlsScreen() {
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
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh' }}>
        <div style={{
          width: 22, height: 22, borderRadius: '50%',
          border: '2px solid rgba(255,255,255,0.15)', borderTopColor: 'var(--accent)',
          animation: 'spin 0.8s linear infinite',
        }}/>
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 1000, margin: '0 auto', padding: '22px 16px 120px' }}>
      <header style={{ marginBottom: 18 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
          <div>
            <h1 style={{ fontSize: 19, fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--text-primary)' }}>
              Platform Controls
            </h1>
            <p style={{ marginTop: 3, fontSize: 12, color: 'var(--text-tertiary)' }}>
              {data?.control_count ?? 0} settings · {data?.override_count ?? 0} set from this dashboard
            </p>
          </div>
          <button
            type="button"
            onClick={load}
            disabled={saving}
            style={{
              borderRadius: 10, padding: '7px 13px', fontSize: 12, cursor: saving ? 'not-allowed' : 'pointer',
              border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)',
              color: 'var(--text-secondary)', opacity: saving ? 0.5 : 1,
            }}
          >
            Refresh
          </button>
        </div>
        <p style={{ marginTop: 11, fontSize: 12, lineHeight: 1.6, color: 'var(--text-tertiary)' }}>
          Values set here are stored in the database and re-applied on every boot, taking
          precedence over the Render environment. Reset a control to hand it back to Render.
          Secrets and connection URLs are deliberately not editable here.
        </p>
      </header>

      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search settings…"
        style={{ ...FIELD, width: '100%', marginBottom: 14, padding: '9px 12px' }}
      />

      {error && <div style={BANNER('255,107,125')}><span style={{ color: '#ff6b7d' }}>{error}</span></div>}
      {notice && !error && <div style={BANNER('70,217,164')}><span style={{ color: '#46d9a4' }}>{notice}</span></div>}
      {restartKeys.length > 0 && (
        <div style={BANNER('255,189,102')}>
          <span style={{ color: '#ffbd66' }}>
            Saved, but the running process already read {restartKeys.length === 1 ? 'this value' : 'these values'} at
            startup — restart the backend to pick {restartKeys.length === 1 ? 'it' : 'them'} up:{' '}
            <code style={{ fontFamily: 'var(--font-mono)' }}>{restartKeys.join(', ')}</code>
          </span>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 11 }}>
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
          <p style={{ padding: '40px 0', textAlign: 'center', fontSize: 12, color: 'var(--text-muted)' }}>
            No settings match “{query}”.
          </p>
        )}
      </div>

      {pendingCount > 0 && (
        <div style={{
          position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 20,
          padding: '11px 16px', background: 'var(--bg-surface)',
          borderTop: '1px solid var(--border)',
        }}>
          <div style={{
            maxWidth: 1000, margin: '0 auto', display: 'flex', alignItems: 'center',
            justifyContent: 'space-between', gap: 12,
          }}>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
              {pendingCount} unsaved change{pendingCount === 1 ? '' : 's'}
            </span>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button
                type="button"
                onClick={() => setPending({})}
                disabled={saving}
                style={{
                  borderRadius: 10, padding: '7px 13px', fontSize: 12,
                  border: '1px solid var(--border)', background: 'transparent',
                  color: 'var(--text-secondary)', cursor: saving ? 'not-allowed' : 'pointer',
                  opacity: saving ? 0.5 : 1,
                }}
              >
                Discard
              </button>
              <button
                type="button"
                onClick={handleSave}
                disabled={saving}
                style={{
                  borderRadius: 10, padding: '7px 17px', fontSize: 12, fontWeight: 700,
                  border: '1px solid var(--accent)', background: 'var(--accent)', color: '#04121f',
                  cursor: saving ? 'not-allowed' : 'pointer', opacity: saving ? 0.5 : 1,
                }}
              >
                Apply
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
