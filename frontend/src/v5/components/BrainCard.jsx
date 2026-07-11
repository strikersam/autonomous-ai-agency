/* eslint-disable no-unused-vars */
//
// BrainCard — UI half of the DB-persisted, UI-switchable brain config
// (PR #824 follow-up — docs/plans/db-brain-switcher.md).
//
// Layout sketch:
//   ┌──────────────────────────────────────────────────────────────────┐
//   │ Brain                                                            │
//   │ Provider: [ Cerebras ▾ ]   ⚠ key missing — set CEREBRAS_API_KEY  │
//   │ Planner    [ qwen-3-coder-480b  ] [Test] ✓ live                  │
//   │ Executor   [ qwen-3-coder-480b  ] [Test] ✓ live                  │
//   │ Verifier   [ llama-3.3-70b      ] [Test] ✗ 410 Gone              │
//   │ Judge      [ llama-3.3-70b      ] [Test] —                        │
//   │ [Apply]   Last applied 2026-06-26T05:14Z by admin@example.com    │
//   └──────────────────────────────────────────────────────────────────┘
//
// Hard constraint (from the plan): the Apply button calls
// PATCH /admin/api/policy/brain which probes each changed model for
// liveness before saving. If any probe fails, the server returns 422
// with a probe report — we surface the failure inline rather than
// persisting a dead model.
import React from 'react';
import * as api from '../../api';

const ROLE_LABELS = {
  planner:  'Planner',
  executor: 'Executor',
  verifier: 'Verifier',
  judge:    'Judge',
};

const ROLE_ORDER = ['planner', 'executor', 'verifier', 'judge'];

// Provider labels are now server-driven — the GET /admin/api/policy/brain
// response includes a `display_name` per provider (UNIT 5). We keep a tiny
// fallback map ONLY for the brief loading window before the server response
// arrives; once `providers` is populated, the dropdown uses display_name
// exclusively. Adding a provider to config/models.yaml + the BrainProvider
// Literal is the only change needed — no parallel UI list to keep in sync.
const PROVIDER_LABEL_FALLBACK = {
  nvidia:    'NVIDIA NIM',
  cerebras:  'Cerebras',
  groq:      'Groq',
  ollama:    'Local Ollama',
  mistral:   'Mistral',
  deepseek:  'DeepSeek',
  zhipu:     'ZhipuAI',
  zai:       'Z.ai',
  together:  'Together AI',
  dashscope: 'DashScope',
  moonshot:  'Moonshot',
  openrouter: 'OpenRouter',
  anthropic: 'Anthropic',
  aerolink:  'Aerolink',
};

function providerLabel(p) {
  if (!p) return '';
  return p.display_name || PROVIDER_LABEL_FALLBACK[p.provider_id] || p.provider_id;
}

function tierBadge(tier) {
  // tier is one of: 'free' | 'paid' | 'local' | 'unknown'
  if (tier === 'free')  return 'free';
  if (tier === 'paid')  return 'paid';
  if (tier === 'local') return 'local';
  return '';
}

function errText(e, fallback) {
  const detail = e?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object') {
    if (detail.message) return detail.message;
    return JSON.stringify(detail).slice(0, 300);
  }
  return e?.message || fallback;
}

export default function BrainCard() {
  const [config, setConfig]         = React.useState(null);
  const [providers, setProviders]   = React.useState([]);
  const [loading, setLoading]       = React.useState(true);
  const [error, setError]           = React.useState(null);

  // Editable draft — kept separate from `config` so the user can change
  // fields without immediately persisting. Apply sends the diff.
  const [draft, setDraft] = React.useState(null);

  const [applyBusy, setApplyBusy]   = React.useState(false);
  const [applyResult, setApplyResult] = React.useState(null); // {probe_report, ok}
  const [applyError, setApplyError] = React.useState(null);

  // Per-role test state: { planner: {busy, result} }
  const [testState, setTestState]   = React.useState({});

  const load = React.useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const { data } = await api.getBrainConfig();
      // Defensive: a mid-propagation deploy (or an auth redirect) can return the
      // SPA's index.html with a 200, leaving `data.config` undefined. Surface a
      // friendly "loading" state instead of throwing
      // `undefined is not an object (evaluating 'data.config.primary_provider')`.
      if (!data || !data.config) {
        setError('Brain config is still warming up (the backend returned no config yet). Retry in a moment.');
        return;
      }
      setConfig(data.config);
      setProviders(data.providers || []);
      setDraft({
        primary_provider: data.config.primary_provider,
        planner_model:    data.config.planner_model,
        executor_model:   data.config.executor_model,
        verifier_model:   data.config.verifier_model,
        judge_model:      data.config.judge_model,
        max_tokens:       data.config.max_tokens,
        ollama_base_url:  data.config.ollama_base_url || '',
      });
    } catch (e) {
      setError(errText(e, 'Could not load brain config.'));
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => { load(); }, [load]);

  const selectedProvider = draft?.primary_provider || 'nvidia';
  const providerMeta = providers.find(p => p.provider_id === selectedProvider) || {};
  const keyMissing = selectedProvider !== 'ollama' && providerMeta.key_present === false;

  const updateDraft = (field, value) => {
    setDraft(prev => ({ ...prev, [field]: value }));
    // Clear any stale apply result when the draft changes.
    setApplyResult(null);
    setApplyError(null);
  };

  const applyPresets = (providerId) => {
    const presets = providerMeta.presets || {};
    // Find presets in the providers list (the GET response includes them per
    // provider). Fall back to whatever is currently in the draft if a role
    // isn't preset for this provider.
    const meta = providers.find(p => p.provider_id === providerId) || {};
    const p = meta.presets || {};
    setDraft(prev => ({
      ...prev,
      primary_provider: providerId,
      planner_model:    p.planner    || prev.planner_model,
      executor_model:   p.executor   || prev.executor_model,
      verifier_model:   p.verifier   || prev.verifier_model,
      judge_model:      p.judge      || prev.judge_model,
    }));
    setApplyResult(null);
    setApplyError(null);
  };

  const handleTest = async (role) => {
    if (!draft) return;
    const model = draft[`${role}_model`];
    if (!model) return;
    setTestState(prev => ({ ...prev, [role]: { busy: true, result: null } }));
    try {
      // For Ollama, test against the typed-but-unsaved tunnel URL so the
      // operator can validate a new tunnel before Apply.
      const baseUrl = selectedProvider === 'ollama' ? (draft.ollama_base_url || '') : '';
      const { data } = await api.testBrainModel(selectedProvider, model, baseUrl);
      setTestState(prev => ({ ...prev, [role]: { busy: false, result: data }}));
    } catch (e) {
      setTestState(prev => ({ ...prev, [role]: { busy: false, result: { live: false, reason: errText(e, 'Test failed') }}}));
    }
  };

  const handleApply = async () => {
    if (!draft || !config) return;
    setApplyBusy(true); setApplyError(null); setApplyResult(null);
    // Build the diff — only include changed fields so we don't re-probe
    // roles the operator didn't touch.
    const patch = {};
    if (draft.primary_provider !== config.primary_provider) patch.primary_provider = draft.primary_provider;
    if (draft.planner_model    !== config.planner_model)    patch.planner_model    = draft.planner_model;
    if (draft.executor_model   !== config.executor_model)   patch.executor_model   = draft.executor_model;
    if (draft.verifier_model   !== config.verifier_model)   patch.verifier_model   = draft.verifier_model;
    if (draft.judge_model      !== config.judge_model)      patch.judge_model      = draft.judge_model;
    if (draft.max_tokens       !== config.max_tokens)       patch.max_tokens       = draft.max_tokens;
    if ((draft.ollama_base_url || '') !== (config.ollama_base_url || '')) patch.ollama_base_url = draft.ollama_base_url || '';
    if (Object.keys(patch).length === 0) {
      setApplyError('No changes to apply.');
      setApplyBusy(false);
      return;
    }
    try {
      const { data } = await api.patchBrainConfig(patch);
      setConfig(data.config);
      setApplyResult({ ok: true, probe_report: data.probe_report || [] });
    } catch (e) {
      setApplyError(errText(e, 'Apply failed.'));
      // 422 carries a structured probe_report — surface the failing roles.
      const detail = e?.response?.data?.detail;
      if (detail && typeof detail === 'object' && Array.isArray(detail.probe_report)) {
        setApplyResult({ ok: false, probe_report: detail.probe_report, failures: detail.failures || [] });
      }
    } finally {
      setApplyBusy(false);
    }
  };

  if (loading) {
    return (
      <div style={styles.card}>
        <div style={styles.header}>Brain</div>
        <div style={{ padding: 16, fontSize: 13, color: 'var(--text-muted)' }}>Loading brain config…</div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ ...styles.card, borderColor: 'rgba(255,107,125,0.30)' }}>
        <div style={styles.header}>Brain</div>
        <div style={{ padding: 16, fontSize: 13, color: '#ff6b7d' }}>{error}</div>
      </div>
    );
  }

  return (
    <div style={styles.card}>
      <div style={styles.header}>
        <span>Brain</span>
        <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', letterSpacing: '0.10em' }}>
          {config?.updated_at ? `last applied ${config.updated_at} by ${config.updated_by || 'unknown'}` : 'never applied — using safe default'}
        </span>
      </div>

      <div style={styles.body}>
        {/* Provider picker */}
        <div style={{ marginBottom: 14 }}>
          <label style={styles.label}>Primary provider</label>
          <select
            value={selectedProvider}
            onChange={(e) => applyPresets(e.target.value)}
            style={styles.select}
          >
            {providers.map(p => {
              const label = providerLabel(p);
              const tier = tierBadge(p.tier);
              const tierTag = tier ? ` [${tier}]` : '';
              const keyTag = (p.provider_id !== 'ollama' && !p.key_present) ? '  ⚠ no key' : '';
              return (
                <option key={p.provider_id} value={p.provider_id}>
                  {label}{tierTag}{keyTag}
                </option>
              );
            })}
          </select>
          {keyMissing && (
            <div style={{ marginTop: 6, fontSize: 11, color: '#ffbd66', fontFamily: 'var(--font-mono)' }}>
              ⚠ {selectedProvider.toUpperCase()}_API_KEY is not set on the server. Apply will be rejected until the key is configured.
            </div>
          )}
          {selectedProvider === 'ollama' && (
            <div style={{ marginTop: 10 }}>
              <label style={styles.label}>Ollama base URL (your tunnel)</label>
              <input
                type="text"
                value={draft?.ollama_base_url || ''}
                onChange={(e) => updateDraft('ollama_base_url', e.target.value)}
                placeholder="https://your-tunnel.trycloudflare.com  (blank = OLLAMA_BASE env / localhost)"
                style={styles.select}
              />
              <div style={{ marginTop: 6, fontSize: 11, color: '#8fb6ff', fontFamily: 'var(--font-mono)', lineHeight: 1.5 }}>
                ℹ Point the brain at your own machine — run <b>ollama serve</b>, expose it with a tunnel
                (a named Cloudflare Tunnel is best; ngrok's free URL rotates), and paste the URL here. No
                Render/env edit needed — it's saved in the DB. Test probes this URL and checks the model is
                pulled; if your machine sleeps the probe fails and Apply is blocked, so keep a cloud brain
                as the fallback.
              </div>
            </div>
          )}
          <div style={{ marginTop: 6, fontSize: 11, color: 'var(--text-tertiary)', fontFamily: 'var(--font-mono)' }}>
            base URL: {providerMeta.base_url || '—'}
          </div>
        </div>

        {/* Role model fields */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 8 }}>
          {ROLE_ORDER.map(role => {
            const fieldName = `${role}_model`;
            const ts = testState[role];
            return (
              <div key={role} style={styles.roleRow}>
                <div style={{ minWidth: 70 }}>
                  <div style={styles.roleLabel}>{ROLE_LABELS[role]}</div>
                </div>
                <input
                  type="text"
                  value={draft?.[fieldName] || ''}
                  onChange={(e) => updateDraft(fieldName, e.target.value)}
                  placeholder="provider/model-id"
                  style={styles.input}
                />
                <button
                  onClick={() => handleTest(role)}
                  disabled={ts?.busy}
                  style={styles.testBtn}
                >
                  {ts?.busy ? '…' : 'Test'}
                </button>
                <TestBadge result={ts?.result} />
              </div>
            );
          })}
        </div>

        {/* Apply / status */}
        <div style={{ marginTop: 14, display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <button
            onClick={handleApply}
            disabled={applyBusy || keyMissing}
            style={{
              ...styles.applyBtn,
              opacity: (applyBusy || keyMissing) ? 0.5 : 1,
              cursor: (applyBusy || keyMissing) ? 'not-allowed' : 'pointer',
            }}
          >
            {applyBusy ? 'Applying…' : 'Apply'}
          </button>
          {applyError && (
            <span style={{ fontSize: 12, color: '#ff6b7d', fontFamily: 'var(--font-mono)' }}>{applyError}</span>
          )}
          {applyResult?.ok && (
            <span style={{ fontSize: 12, color: '#46d9a4', fontFamily: 'var(--font-mono)' }}>
              ✓ Applied — {applyResult.probe_report.length} model(s) probed live
            </span>
          )}
          {applyResult && !applyResult.ok && Array.isArray(applyResult.failures) && applyResult.failures.length > 0 && (
            <span style={{ fontSize: 12, color: '#ff6b7d', fontFamily: 'var(--font-mono)' }}>
              ✗ Rejected — {applyResult.failures.length} model(s) failed liveness probe (config unchanged)
            </span>
          )}
        </div>

        {/* Probe report (only shown after an Apply attempt) */}
        {applyResult && Array.isArray(applyResult.probe_report) && applyResult.probe_report.length > 0 && (
          <div style={{ marginTop: 10, padding: 10, borderRadius: 8, background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}>
            <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.10em', marginBottom: 6 }}>
              Probe report
            </div>
            {applyResult.probe_report.map((p, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, fontSize: 11, fontFamily: 'var(--font-mono)', marginBottom: 3, color: p.live ? '#46d9a4' : '#ff6b7d' }}>
                <span style={{ minWidth: 70 }}>{p.role}</span>
                <span style={{ minWidth: 200, color: 'var(--text-secondary)' }}>{p.model}</span>
                <span>{p.live ? '✓ live' : `✗ ${p.reason || 'failed'}`}</span>
                {p.elapsed_ms != null && <span style={{ color: 'var(--text-muted)' }}>({p.elapsed_ms} ms)</span>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TestBadge({ result }) {
  if (!result) return <span style={{ minWidth: 80 }} />;
  if (result.live) {
    return (
      <span style={{ minWidth: 80, fontSize: 11, color: '#46d9a4', fontFamily: 'var(--font-mono)' }}>
        ✓ live{result.elapsed_ms != null ? ` · ${result.elapsed_ms}ms` : ''}
      </span>
    );
  }
  return (
    <span
      title={result.reason || 'failed'}
      style={{ minWidth: 80, fontSize: 11, color: '#ff6b7d', fontFamily: 'var(--font-mono)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
    >
      ✗ {result.reason ? result.reason.slice(0, 30) : 'failed'}
    </span>
  );
}

const styles = {
  card: {
    borderRadius: 16,
    border: '1px solid rgba(93,162,255,0.18)',
    background: 'rgba(93,162,255,0.04)',
    marginBottom: 14,
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 16px',
    borderBottom: '1px solid rgba(255,255,255,0.06)',
    fontSize: 13,
    fontWeight: 800,
    color: '#fff',
    letterSpacing: '-0.02em',
  },
  body: {
    padding: 16,
  },
  label: {
    display: 'block',
    fontSize: 10,
    fontFamily: 'var(--font-mono)',
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
    letterSpacing: '0.10em',
    marginBottom: 6,
  },
  select: {
    width: '100%',
    padding: '8px 10px',
    borderRadius: 8,
    background: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(255,255,255,0.10)',
    color: '#fff',
    fontSize: 13,
    fontFamily: 'var(--font-mono)',
    outline: 'none',
    cursor: 'pointer',
  },
  roleRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '6px 8px',
    borderRadius: 8,
    background: 'rgba(255,255,255,0.02)',
    border: '1px solid rgba(255,255,255,0.04)',
  },
  roleLabel: {
    fontSize: 11,
    fontWeight: 700,
    color: 'var(--text-secondary)',
    letterSpacing: '-0.01em',
  },
  input: {
    flex: 1,
    padding: '6px 10px',
    borderRadius: 6,
    background: 'rgba(255,255,255,0.05)',
    border: '1px solid rgba(255,255,255,0.10)',
    color: '#fff',
    fontSize: 12,
    fontFamily: 'var(--font-mono)',
    outline: 'none',
    minWidth: 0,
  },
  testBtn: {
    padding: '6px 12px',
    borderRadius: 6,
    background: 'rgba(93,162,255,0.10)',
    border: '1px solid rgba(93,162,255,0.30)',
    color: 'var(--accent)',
    fontSize: 11,
    fontWeight: 700,
    cursor: 'pointer',
    minWidth: 56,
  },
  applyBtn: {
    padding: '9px 22px',
    borderRadius: 10,
    background: 'linear-gradient(135deg, #5da2ff, #2ecc71)',
    color: '#06111f',
    fontSize: 13,
    fontWeight: 800,
    border: 'none',
    letterSpacing: '-0.02em',
  },
};
