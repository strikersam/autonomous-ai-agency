/**
 * ProviderConsole — one console for every provider, ranked by live health.
 *
 * Replaces what used to be five stacked, overlapping surfaces on the Providers
 * screen: a brain card, a local-brain switch, a provider-health switch, a paid
 * kill switch, a grid of configured providers, and a second grid of catalogue
 * providers. The same provider could appear in three of them, each showing a
 * different idea of its state, and the word "brain" meant something different
 * in each.
 *
 * The redesign rests on three decisions:
 *
 *   1. ONE LIST. Live routed providers, database-configured providers, and the
 *      catalogue of things you could configure are merged on identity into a
 *      single ranked table. A provider appears exactly once, and its row states
 *      plainly which of those it is.
 *
 *   2. HEALTH IS THE SORT ORDER. Whatever is actually serving traffic sits at
 *      the top, degraded providers next, idle ones below, unconfigured last.
 *      You never hunt for the row that matters.
 *
 *   3. "BRAIN" IS A ROLE, NOT A PLACE. Exactly one row carries the SERVING
 *      badge — the provider the router would pick right now — and the reason is
 *      stated next to it. Every switch that used to live in its own card is now
 *      one control in one rail.
 *
 * Data sources, all optional and independently degradable:
 *   GET /api/llm/providers   live routing state (ADR-008)
 *   GET /api/llm/status      strategy, queue, cache, budget
 *   GET /api/providers       database-persisted, editable providers
 *   CATALOGUE (static)       providers you could configure
 */
import React from 'react';
import * as api from '../../api';

/* ── Presentation constants ─────────────────────────────────────────────── */

const TIER = {
  local:    { label: 'Local',   color: '#5da2ff', hint: 'On your own hardware. No quota, no cost.' },
  free:     { label: 'Free',    color: '#46d9a4', hint: 'Free cloud tier. Rate limits apply.' },
  cheap:    { label: 'Cheap',   color: '#ffbd66', hint: 'Low-cost paid tier.' },
  premium:  { label: 'Premium', color: '#ff9b6b', hint: 'Paid. Used only as a last resort.' },
  unknown:  { label: '—',       color: '#8b93a7', hint: '' },
};

const STATE = {
  serving:      { label: 'Serving',      color: '#46d9a4', dot: '#46d9a4', rank: 0 },
  healthy:      { label: 'Healthy',      color: '#46d9a4', dot: '#46d9a4', rank: 1 },
  probing:      { label: 'Probing',      color: '#ffbd66', dot: '#ffbd66', rank: 2 },
  degraded:     { label: 'Degraded',     color: '#ffbd66', dot: '#ffbd66', rank: 3 },
  tripped:      { label: 'Tripped',      color: '#ff6b7d', dot: '#ff6b7d', rank: 4 },
  configured:   { label: 'Idle',         color: '#8b93a7', dot: '#5b6478', rank: 5 },
  unconfigured: { label: 'Not set up',   color: '#5b6478', dot: '#3a4152', rank: 6 },
};

const STRATEGY_HINT = {
  adaptive: 'Scores every provider live on success rate, 429s, load, latency, and cost.',
  priority: 'Strict configured order. Predictable, but ignores live health.',
  round_robin: 'Even rotation across all healthy providers.',
  least_loaded: 'Whichever provider has the most free capacity right now.',
  lowest_latency: 'Fastest observed p95 first.',
  highest_success_rate: 'Most reliable provider in the recent window first.',
  random: 'Uniform shuffle. Spreads load with no shared counter.',
  weighted: 'Biased random, using each provider\'s configured weight.',
  cost_optimized: 'Cheapest first. Free providers always precede paid ones.',
  context_length_optimized: 'Smallest context window that still fits the prompt.',
  token_budget_optimized: 'Whichever provider has the most quota headroom left.',
  model_capability: 'Closest capability match to what the request actually needs.',
  provider_health: 'Strict breaker state, then failure rate.',
  fallback_chain: 'Walks the explicit chain in routing.yaml, in order.',
  automatic_failover: 'Tiered degradation: local, then free, then cheap, then premium.',
};

/**
 * Providers you can configure but which the router has not seen.
 * Deliberately short: this is a "what else can I plug in" list, not a
 * competing source of truth about what is running.
 */
const CATALOGUE = [
  { id: 'cerebras',   name: 'Cerebras',      tier: 'free',    keyEnv: 'CEREBRAS_API_KEY',   note: 'Fastest free inference.' },
  { id: 'groq',       name: 'Groq',          tier: 'free',    keyEnv: 'GROQ_API_KEY',       note: 'Very fast, generous free tier.' },
  { id: 'nvidia',     name: 'NVIDIA NIM',    tier: 'free',    keyEnv: 'NVIDIA_API_KEY',     note: 'The always-on free floor.' },
  { id: 'google',     name: 'Google Gemini', tier: 'free',    keyEnv: 'GEMINI_API_KEY',     note: '1M context — the overflow escape hatch.' },
  { id: 'ollama',     name: 'Ollama',        tier: 'local',   keyEnv: null,                 note: 'Local daemon. Set OLLAMA_BASE.' },
  { id: 'lmstudio',   name: 'LM Studio',     tier: 'local',   keyEnv: null,                 note: 'Set LMSTUDIO_BASE_URL and LMSTUDIO_ENABLED.' },
  { id: 'vllm',       name: 'vLLM',          tier: 'local',   keyEnv: 'VLLM_API_KEY',       note: 'Self-hosted, batches well.' },
  { id: 'localai',    name: 'LocalAI',       tier: 'local',   keyEnv: null,                 note: 'Set LOCALAI_BASE_URL.' },
  { id: 'litellm',    name: 'LiteLLM proxy', tier: 'local',   keyEnv: 'LITELLM_API_KEY',    note: 'Front an existing LiteLLM deployment.' },
  { id: 'openrouter', name: 'OpenRouter',    tier: 'cheap',   keyEnv: 'OPENROUTER_API_KEY', note: 'Gateway to hundreds of models.' },
  { id: 'together',   name: 'Together AI',   tier: 'cheap',   keyEnv: 'TOGETHER_API_KEY',   note: 'Wide open-model catalogue.' },
  { id: 'fireworks',  name: 'Fireworks',     tier: 'cheap',   keyEnv: 'FIREWORKS_API_KEY',  note: 'Fast open-model hosting.' },
  { id: 'deepinfra',  name: 'DeepInfra',     tier: 'cheap',   keyEnv: 'DEEPINFRA_API_KEY',  note: 'Low-cost open models.' },
  { id: 'mistral',    name: 'Mistral',       tier: 'cheap',   keyEnv: 'MISTRAL_API_KEY',    note: 'Strong multilingual and code.' },
  { id: 'openai',     name: 'OpenAI',        tier: 'premium', keyEnv: 'OPENAI_API_KEY',     note: 'Paid. Requires paid access on.' },
  { id: 'azure',      name: 'Azure OpenAI',  tier: 'premium', keyEnv: 'AZURE_OPENAI_API_KEY', note: 'Needs deployment + api-version.' },
  { id: 'anthropic',  name: 'Anthropic',     tier: 'premium', keyEnv: 'ANTHROPIC_API_KEY',  note: 'Claude. Paid last resort.' },
];

/** Aliases so the same vendor from three sources collapses to one row. */
const ALIASES = {
  'nvidia-nim': 'nvidia', nim: 'nvidia', 'nvidia_nim': 'nvidia',
  gemini: 'google', 'google-gemini': 'google', googleai: 'google',
  'lm-studio': 'lmstudio', 'local-ai': 'localai',
  claude: 'anthropic', 'azure-openai': 'azure',
};

// Deliberately NOT aliased: 'openai-compatible' is the default *type* for any
// custom provider an admin adds on this page, and 'zai' is a distinct vendor.
// Mapping either would fold a self-hosted endpoint into the premium OpenAI or
// NVIDIA row and show it someone else's health.

export function canonicalId(raw) {
  const id = String(raw || '').trim().toLowerCase();
  return ALIASES[id] || id;
}

/* ── Small presentational pieces ────────────────────────────────────────── */

function StatePill({ state }) {
  const cfg = STATE[state] || STATE.unconfigured;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5, flexShrink: 0,
      fontSize: 10, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em',
      textTransform: 'uppercase', padding: '3px 8px', borderRadius: 999,
      color: cfg.color, background: `${cfg.color}12`, border: `1px solid ${cfg.color}30`,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: cfg.dot, flexShrink: 0 }} />
      {cfg.label}
    </span>
  );
}

function TierChip({ tier }) {
  const cfg = TIER[tier] || TIER.unknown;
  return (
    <span title={cfg.hint} style={{
      fontSize: 9, fontFamily: 'var(--font-mono)', letterSpacing: '0.10em',
      textTransform: 'uppercase', padding: '2px 7px', borderRadius: 999,
      color: cfg.color, background: `${cfg.color}10`, border: `1px solid ${cfg.color}25`,
    }}>{cfg.label}</span>
  );
}

/**
 * A horizontal capacity bar. Used for success rate and key health, where a
 * number alone ("0.97") reads as noise but a bar reads as "nearly full".
 */
function Meter({ value, color, width = 54, title }) {
  const pct = Math.max(0, Math.min(1, Number(value) || 0));
  return (
    <span title={title} style={{
      display: 'inline-block', width, height: 5, borderRadius: 999,
      background: 'rgba(255,255,255,0.07)', overflow: 'hidden', verticalAlign: 'middle',
    }}>
      <span style={{
        display: 'block', width: `${pct * 100}%`, height: '100%',
        background: color, borderRadius: 999, transition: 'width 0.3s ease',
      }} />
    </span>
  );
}

function StatTile({ label, value, sub, tone = '#fff' }) {
  return (
    <div style={{
      flex: '1 1 96px', minWidth: 96, padding: '9px 12px', borderRadius: 12,
      background: 'rgba(255,255,255,0.035)', border: '1px solid rgba(255,255,255,0.07)',
    }}>
      <div style={{
        fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
        textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 3,
      }}>{label}</div>
      <div style={{ fontSize: 17, fontWeight: 800, color: tone, letterSpacing: '-0.03em', lineHeight: 1.1 }}>
        {value}
      </div>
      {sub ? <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 1 }}>{sub}</div> : null}
    </div>
  );
}

/** A two-option segmented switch. Replaces a whole card that held one toggle. */
function Segmented({ label, hint, options, value, onChange, busy }) {
  return (
    <div style={{ flex: '1 1 220px', minWidth: 200 }}>
      <div style={{
        fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
        textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 5,
      }}>{label}</div>
      <div style={{
        display: 'flex', gap: 3, padding: 3, borderRadius: 10,
        background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
        opacity: busy ? 0.55 : 1,
      }}>
        {options.map(opt => {
          const active = opt.value === value;
          return (
            <button
              key={String(opt.value)}
              type="button"
              onClick={() => !busy && !active && onChange(opt.value)}
              disabled={busy}
              title={opt.hint || ''}
              style={{
                flex: 1, padding: '6px 10px', borderRadius: 8, border: 'none',
                cursor: busy || active ? 'default' : 'pointer',
                fontSize: 11.5, fontWeight: 700, letterSpacing: '-0.01em',
                background: active ? (opt.color || 'rgba(93,162,255,0.20)') : 'transparent',
                color: active ? '#06111f' : 'var(--text-muted)',
                transition: 'all 0.15s',
              }}
            >{opt.label}</button>
          );
        })}
      </div>
      {hint ? (
        <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 5, lineHeight: 1.45 }}>{hint}</div>
      ) : null}
    </div>
  );
}

/* ── Merge logic ────────────────────────────────────────────────────────── */

/**
 * Fold the three sources into one ranked list.
 *
 * The merge is the whole point of the redesign, so it is deliberately explicit:
 * every row records which sources contributed to it, and the row's state is
 * derived from the strongest evidence available (live health beats a database
 * record, which beats a catalogue entry).
 */
export function mergeProviders({ routed = [], stored = [], catalogue = CATALOGUE }) {
  const rows = new Map();

  const ensure = (id) => {
    const key = canonicalId(id);
    if (!rows.has(key)) {
      rows.set(key, {
        id: key, name: key, tier: 'unknown', state: 'unconfigured',
        sources: [], models: [], keys: [], health: null,
        successRate: null, p95: null, rateLimits: 0, inFlight: 0,
        priority: 500, keyCount: 0, baseUrl: '', kind: '', note: '',
        stored: null, available: false,
      });
    }
    return rows.get(key);
  };

  // Catalogue first — the weakest evidence, so anything else overwrites it.
  catalogue.forEach(entry => {
    const row = ensure(entry.id);
    row.name = entry.name;
    row.tier = entry.tier;
    row.note = entry.note || '';
    row.keyEnv = entry.keyEnv || null;
    row.sources.push('catalogue');
  });

  // Database-persisted providers — editable, but may not be routing.
  stored.forEach(entry => {
    const row = ensure(entry.provider_id || entry.id);
    row.name = entry.name || row.name || entry.provider_id;
    row.baseUrl = entry.base_url || row.baseUrl;
    row.kind = entry.type || row.kind;
    row.stored = entry;
    row.isDefault = !!entry.is_default;
    if (!row.sources.includes('stored')) row.sources.push('stored');
    if (row.state === 'unconfigured') row.state = 'configured';
  });

  // Live routing state — the strongest evidence, so it wins on every field.
  routed.forEach(entry => {
    const row = ensure(entry.id);
    const health = entry.health || {};
    row.name = row.name && row.name !== row.id ? row.name : entry.id;
    row.tier = entry.tier || row.tier;
    row.kind = entry.kind || row.kind;
    row.baseUrl = entry.base_url || row.baseUrl;
    row.models = Array.isArray(entry.models) ? entry.models : [];
    row.keys = Array.isArray(entry.keys) ? entry.keys : [];
    row.keyCount = entry.key_count || row.keys.length;
    row.inFlight = entry.in_flight || 0;
    row.maxConcurrency = entry.max_concurrency || 0;
    row.priority = typeof entry.priority === 'number' ? entry.priority : row.priority;
    row.health = health;
    row.available = entry.available !== false;
    row.successRate = typeof health.success_rate === 'number' ? health.success_rate : null;
    row.p95 = typeof health.p95_latency_ms === 'number' ? health.p95_latency_ms : null;
    row.rateLimits = health.total_rate_limits || 0;
    row.requests = health.total_requests || 0;
    row.lastError = health.last_error || '';
    if (!row.sources.includes('routed')) row.sources.push('routed');

    const breaker = health.state || 'closed';
    if (breaker === 'open') row.state = 'tripped';
    else if (breaker === 'half_open') row.state = 'probing';
    else if (row.successRate !== null && row.successRate < 0.85 && row.requests > 3) row.state = 'degraded';
    else row.state = 'healthy';
  });

  const list = [...rows.values()];

  // Exactly one row carries SERVING: the provider the router would pick next.
  // `routed` already arrives ranked healthiest-first from GET /api/llm/providers,
  // so the first healthy entry in that order IS the answer. Re-ranking here
  // gave a second implementation that could drift from the router's own — and
  // its `?? 1` default treated "no data yet" as a perfect 1.0 score, so an
  // untried provider outranked a measured one at 0.98.
  const servingId = routed
    .map(entry => canonicalId(entry.id))
    .find(id => rows.get(id)?.state === 'healthy');
  const serving = servingId ? rows.get(servingId) : undefined;
  if (serving) serving.state = 'serving';

  list.sort((a, b) => {
    const rank = (STATE[a.state]?.rank ?? 9) - (STATE[b.state]?.rank ?? 9);
    if (rank !== 0) return rank;
    const success = (b.successRate ?? -1) - (a.successRate ?? -1);
    if (success !== 0) return success;
    const latency = (a.p95 ?? 1e9) - (b.p95 ?? 1e9);
    if (latency !== 0) return latency;
    return a.priority - b.priority || a.id.localeCompare(b.id);
  });

  return list;
}

/* ── Row ────────────────────────────────────────────────────────────────── */

function ProviderRow({ row, expanded, onToggle, onDisable, onProbe, onEdit, onDelete, onTest, onSetRenderKey, busy }) {
  const cfg = STATE[row.state] || STATE.unconfigured;
  const isLive = row.sources.includes('routed');
  const healthyKeys = row.keys.filter(k => k.healthy).length;
  const [testMsg, setTestMsg] = React.useState('');

  // Inline key editor: writes the provider's key/base_url straight to the
  // runtime environment (Render env) via /api/providers/{id}/render-env, so an
  // operator can rotate a key from any row — not only DB-stored custom
  // providers. The live brain reads keys from env, so this is what actually
  // brings a provider online / swaps a spent key.
  const [keyOpen, setKeyOpen] = React.useState(false);
  const [keyVal, setKeyVal]   = React.useState('');
  const [urlVal, setUrlVal]   = React.useState('');
  const [keyBusy, setKeyBusy] = React.useState(false);
  const [keyMsg, setKeyMsg]   = React.useState('');

  const saveKey = async () => {
    if (!keyVal.trim() && !urlVal.trim()) { setKeyMsg('Enter a key or a base URL.'); return; }
    setKeyBusy(true); setKeyMsg('');
    const payload = {};
    if (keyVal.trim()) payload.api_key = keyVal.trim();
    if (urlVal.trim()) payload.base_url = urlVal.trim();
    try {
      const { data } = await onSetRenderKey(row.stored?.provider_id || row.id, payload);
      setKeyMsg(data?.note || 'Saved to Render.');
      setKeyVal('');
    } catch (e) {
      setKeyMsg(api.fmtErr(e?.response?.data?.detail) || e?.message || 'Save failed.');
    } finally { setKeyBusy(false); }
  };

  const runTest = async () => {
    setTestMsg('testing…');
    try {
      const { data } = await onTest(row.stored?.provider_id || row.id);
      const n = Array.isArray(data?.models) ? data.models.length : null;
      setTestMsg(n != null ? `reachable · ${n} model${n === 1 ? '' : 's'}` : 'reachable');
    } catch (e) {
      setTestMsg(api.fmtErr(e?.response?.data?.detail) || e?.message || 'test failed');
    }
  };

  return (
    <div style={{
      borderRadius: 14,
      border: `1px solid ${row.state === 'serving' ? 'rgba(70,217,164,0.30)' : 'rgba(255,255,255,0.07)'}`,
      background: row.state === 'serving' ? 'rgba(70,217,164,0.045)' : 'rgba(255,255,255,0.022)',
      overflow: 'hidden', transition: 'all 0.18s',
    }}>
      {/* Summary line — everything you need to triage, nothing you don't. */}
      <button
        type="button"
        onClick={onToggle}
        style={{
          width: '100%', display: 'flex', alignItems: 'center', gap: 12,
          padding: '11px 14px', background: 'none', border: 'none',
          cursor: 'pointer', textAlign: 'left', color: 'inherit',
        }}
      >
        <span style={{
          fontSize: 10, color: 'var(--text-muted)', flexShrink: 0, width: 9,
          transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.15s',
        }}>▸</span>

        <span style={{ flex: '2 1 170px', minWidth: 140 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' }}>
            <span style={{ fontSize: 13.5, fontWeight: 800, color: '#fff', letterSpacing: '-0.02em' }}>
              {row.name}
            </span>
            <TierChip tier={row.tier} />
            {row.state === 'serving' && (
              <span title="The provider the router would pick for the next request."
                style={{
                  fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 700,
                  letterSpacing: '0.08em', padding: '2px 7px', borderRadius: 999,
                  color: '#06111f', background: '#46d9a4',
                }}>SERVING</span>
            )}
            {row.isDefault && row.state !== 'serving' && (
              <span style={{
                fontSize: 9, fontFamily: 'var(--font-mono)', padding: '2px 6px',
                borderRadius: 999, color: '#8b93a7', border: '1px solid rgba(255,255,255,0.12)',
              }}>default</span>
            )}
          </span>
          <span style={{
            display: 'block', fontSize: 10.5, fontFamily: 'var(--font-mono)',
            color: 'var(--text-tertiary)', marginTop: 2, overflow: 'hidden',
            textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {row.baseUrl || row.note || '—'}
          </span>
        </span>

        {/* Live columns. Blank rather than zero when there is no data — a
            fabricated 0% success rate reads far worse than an honest dash. */}
        <span style={{ flex: '1 1 92px', minWidth: 84, display: 'none' }} className="pc-col" />
        <span style={{ flex: '0 0 88px', display: 'flex', flexDirection: 'column', gap: 3 }}>
          {row.successRate !== null ? (
            <>
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: cfg.color }}>
                {(row.successRate * 100).toFixed(0)}%
              </span>
              <Meter value={row.successRate} color={cfg.color}
                     title={`${row.requests || 0} requests in the rolling window`} />
            </>
          ) : (
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-tertiary)' }}>—</span>
          )}
        </span>

        <span style={{ flex: '0 0 62px', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
          {row.p95 ? `${Math.round(row.p95)}ms` : '—'}
        </span>

        <span style={{ flex: '0 0 56px', fontSize: 11, fontFamily: 'var(--font-mono)',
                       color: row.rateLimits > 0 ? '#ffbd66' : 'var(--text-tertiary)' }}
              title="HTTP 429 responses seen from this provider">
          {isLive ? `${row.rateLimits} × 429` : '—'}
        </span>

        <span style={{ flex: '0 0 58px', fontSize: 11, fontFamily: 'var(--font-mono)',
                       color: row.keyCount ? (healthyKeys === row.keys.length || !row.keys.length ? '#46d9a4' : '#ffbd66') : 'var(--text-tertiary)' }}
              title="Healthy keys of total configured">
          {row.keyCount ? `${row.keys.length ? healthyKeys : row.keyCount}/${row.keyCount} 🔑` : '—'}
        </span>

        <StatePill state={row.state} />
      </button>

      {/* Detail — only rendered when open, so a 20-row table stays cheap. */}
      {expanded && (
        <div style={{
          padding: '2px 14px 14px 35px', borderTop: '1px solid rgba(255,255,255,0.055)',
          display: 'flex', flexDirection: 'column', gap: 11,
        }}>
          {row.lastError ? (
            <div style={{
              fontSize: 11, fontFamily: 'var(--font-mono)', color: '#ff6b7d',
              background: 'rgba(255,107,125,0.07)', border: '1px solid rgba(255,107,125,0.18)',
              borderRadius: 8, padding: '7px 10px', marginTop: 11,
            }}>Last error: {row.lastError}</div>
          ) : null}

          <div style={{ display: 'flex', gap: 22, flexWrap: 'wrap', marginTop: row.lastError ? 0 : 11 }}>
            <Detail label="Adapter" value={row.kind || '—'} />
            <Detail label="Priority" value={row.priority < 500 ? row.priority : '—'} />
            <Detail label="In flight" value={row.maxConcurrency ? `${row.inFlight} / ${row.maxConcurrency}` : '—'} />
            <Detail label="Requests" value={isLive ? (row.requests ?? 0) : '—'} />
            <Detail label="Sources" value={row.sources.join(' + ')} />
            {row.keyEnv ? <Detail label="Key variable" value={row.keyEnv} mono /> : null}
          </div>

          {row.keys.length > 0 && (
            <div>
              <SectionLabel>API keys</SectionLabel>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {row.keys.map(k => (
                  <span key={k.digest} title={k.last_error || (k.healthy ? 'Healthy' : 'Cooling down')}
                    style={{
                      fontSize: 10, fontFamily: 'var(--font-mono)', padding: '3px 8px',
                      borderRadius: 999,
                      color: k.healthy ? '#46d9a4' : '#ffbd66',
                      background: k.healthy ? 'rgba(70,217,164,0.08)' : 'rgba(255,189,102,0.08)',
                      border: `1px solid ${k.healthy ? 'rgba(70,217,164,0.22)' : 'rgba(255,189,102,0.25)'}`,
                    }}>
                    #{k.index} · {k.digest} · {k.healthy ? 'ready' : `cooling ${Math.round(k.cooling_for_sec)}s`}
                    {k.rate_limits ? ` · ${k.rate_limits}×429` : ''}
                  </span>
                ))}
              </div>
            </div>
          )}

          {row.models.length > 0 && (
            <div>
              <SectionLabel>Models ({row.models.length})</SectionLabel>
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                {row.models.slice(0, 10).map(m => (
                  <span key={m} style={{
                    fontSize: 10, fontFamily: 'var(--font-mono)', padding: '3px 8px',
                    borderRadius: 6, color: 'var(--text-secondary)',
                    background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
                  }}>{m}</span>
                ))}
                {row.models.length > 10 && (
                  <span style={{ fontSize: 10, color: 'var(--text-tertiary)', alignSelf: 'center' }}>
                    +{row.models.length - 10} more
                  </span>
                )}
              </div>
            </div>
          )}

          <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', alignItems: 'center' }}>
            {isLive && (
              <>
                <RowButton onClick={() => onProbe(row.id)} disabled={busy}>Probe now</RowButton>
                <RowButton
                  onClick={() => onDisable(row.id, !row.available)}
                  disabled={busy}
                  tone={row.available ? '#ff6b7d' : '#46d9a4'}
                >{row.available ? 'Take out of rotation' : 'Restore to rotation'}</RowButton>
              </>
            )}
            {row.stored && (
              <>
                <RowButton onClick={runTest} disabled={busy}>Test</RowButton>
                <RowButton onClick={() => onEdit(row.stored)} disabled={busy}>Edit</RowButton>
                <RowButton onClick={() => onDelete(row.stored)} disabled={busy} tone="#ff6b7d">Delete</RowButton>
              </>
            )}
            {row.keyEnv && onSetRenderKey && (
              <RowButton onClick={() => setKeyOpen(o => !o)} disabled={busy || keyBusy}>
                {keyOpen ? 'Cancel' : (isLive ? 'Update key' : 'Set key')}
              </RowButton>
            )}
            {testMsg && (
              <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>{testMsg}</span>
            )}
          </div>

          {/* Inline key/base-URL editor → runtime (Render env). */}
          {keyOpen && row.keyEnv && (
            <div style={{
              display: 'flex', flexDirection: 'column', gap: 8, padding: '11px 12px',
              borderRadius: 10, border: '1px solid rgba(196,181,253,0.22)', background: 'rgba(196,181,253,0.05)',
            }}>
              <div style={{ fontSize: 10.5, color: 'var(--text-tertiary)', lineHeight: 1.45 }}>
                Writes <code style={{ fontFamily: 'var(--font-mono)', color: 'var(--accent)' }}>{row.keyEnv}</code> to the
                server environment (Render), where the live brain reads it. Takes effect on the next deploy. Admin only.
              </div>
              <input
                type="password" value={keyVal} onChange={e => setKeyVal(e.target.value)}
                placeholder={`New value for ${row.keyEnv}`}
                style={{ padding: '9px 11px', borderRadius: 9, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)', color: '#fff', fontSize: 13, fontFamily: 'var(--font-mono)', outline: 'none' }}
              />
              <input
                value={urlVal} onChange={e => setUrlVal(e.target.value)}
                placeholder="Base URL (optional)"
                style={{ padding: '9px 11px', borderRadius: 9, background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.12)', color: '#fff', fontSize: 13, fontFamily: 'var(--font-mono)', outline: 'none' }}
              />
              <div style={{ display: 'flex', gap: 7, alignItems: 'center', flexWrap: 'wrap' }}>
                <RowButton onClick={saveKey} disabled={keyBusy} tone="#c4b5fd">
                  {keyBusy ? 'Saving…' : 'Save to Render'}
                </RowButton>
                {keyMsg && (
                  <span style={{ fontSize: 11, color: /fail|error|enter|unknown|disabled|not config/i.test(keyMsg) ? '#ff6b7d' : '#46d9a4' }}>
                    {keyMsg}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function Detail({ label, value, mono }) {
  return (
    <div>
      <div style={{
        fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
        textTransform: 'uppercase', letterSpacing: '0.10em', marginBottom: 2,
      }}>{label}</div>
      <div style={{
        fontSize: 12, color: 'var(--text-secondary)', fontWeight: 600,
        fontFamily: mono ? 'var(--font-mono)' : 'inherit',
      }}>{String(value)}</div>
    </div>
  );
}

function SectionLabel({ children }) {
  return (
    <div style={{
      fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
      textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 6,
    }}>{children}</div>
  );
}

function RowButton({ children, onClick, disabled, tone }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: '5px 11px', borderRadius: 8, fontSize: 11, fontWeight: 700,
        cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
        color: tone || 'var(--text-secondary)',
        background: tone ? `${tone}10` : 'rgba(255,255,255,0.05)',
        border: `1px solid ${tone ? `${tone}30` : 'rgba(255,255,255,0.10)'}`,
        transition: 'all 0.15s',
      }}
    >{children}</button>
  );
}

/* ── Console ────────────────────────────────────────────────────────────── */

const FILTERS = [
  { id: 'all',      label: 'All' },
  { id: 'live',     label: 'Routing' },
  { id: 'problem',  label: 'Needs attention' },
  { id: 'idle',     label: 'Idle' },
  { id: 'catalog',  label: 'Not set up' },
];

export default function ProviderConsole({
  storedProviders = [],
  onEditProvider,
  onDeleteProvider,
  onTestProvider,
  onSetRenderKey,
  policy,
  onTogglePaid,
  policyBusy,
  refreshStored,
}) {
  const [status, setStatus]   = React.useState(null);
  const [routed, setRouted]   = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError]     = React.useState(null);
  const [filter, setFilter]   = React.useState('all');
  const [openId, setOpenId]   = React.useState(null);
  const [busy, setBusy]       = React.useState(false);
  const [notice, setNotice]   = React.useState('');

  const load = React.useCallback(async () => {
    try {
      const [statusRes, providersRes] = await Promise.allSettled([
        api.getLlmStatus(), api.getLlmProviders(),
      ]);
      if (statusRes.status === 'fulfilled') setStatus(statusRes.value.data);
      if (providersRes.status === 'fulfilled') setRouted(providersRes.value.data?.providers || []);
      if (statusRes.status === 'rejected' && providersRes.status === 'rejected') {
        setError('Routing layer unreachable — showing configured providers only.');
      } else {
        setError(null);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    load();
    const timer = setInterval(load, 15000);   // live enough to watch a failover
    return () => clearInterval(timer);
  }, [load]);

  const rows = React.useMemo(
    () => mergeProviders({ routed, stored: storedProviders }),
    [routed, storedProviders],
  );

  const visible = React.useMemo(() => rows.filter(row => {
    if (filter === 'all') return true;
    if (filter === 'live') return row.sources.includes('routed') && row.available;
    if (filter === 'problem') return ['tripped', 'probing', 'degraded'].includes(row.state) || row.rateLimits > 0;
    if (filter === 'idle') return row.state === 'configured';
    if (filter === 'catalog') return row.state === 'unconfigured';
    return true;
  }), [rows, filter]);

  const serving = rows.find(r => r.state === 'serving');
  const routerOn = status?.enabled !== false;
  const strategy = status?.strategy || 'adaptive';
  const strategies = status?.strategies || Object.keys(STRATEGY_HINT);
  const queue = status?.queue || {};
  const cache = status?.cache || {};
  const budget = status?.budget?.budget || {};
  const totals = status?.budget?.total || {};

  const totalRateLimits = rows.reduce((sum, r) => sum + (r.rateLimits || 0), 0);
  const liveCount = rows.filter(r => r.sources.includes('routed') && r.available).length;

  const act = async (fn, message) => {
    setBusy(true); setNotice('');
    try { await fn(); setNotice(message); await load(); }
    catch (e) { setNotice(api.fmtErr(e?.response?.data?.detail) || e?.message || 'Action failed.'); }
    finally { setBusy(false); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

      {/* ── Serving bar: what the router would pick right now, and why. ──── */}
      <div style={{
        borderRadius: 18, padding: '15px 17px',
        border: `1px solid ${serving ? 'rgba(70,217,164,0.26)' : 'rgba(255,255,255,0.09)'}`,
        background: serving
          ? 'linear-gradient(135deg, rgba(70,217,164,0.075), rgba(70,217,164,0.02))'
          : 'rgba(255,255,255,0.03)',
      }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14, flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 260px', minWidth: 240 }}>
            <div style={{
              fontSize: 9.5, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
              textTransform: 'uppercase', letterSpacing: '0.14em', marginBottom: 5,
            }}>Serving next request</div>

            {loading ? (
              <div style={{ fontSize: 15, color: 'var(--text-muted)' }}>Reading routing state…</div>
            ) : serving ? (
              <>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 9, flexWrap: 'wrap' }}>
                  <span style={{ fontSize: 22, fontWeight: 800, color: '#fff', letterSpacing: '-0.04em' }}>
                    {serving.name}
                  </span>
                  <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', color: '#46d9a4' }}>
                    {serving.models[0] || '—'}
                  </span>
                  <TierChip tier={serving.tier} />
                </div>
                <div style={{ fontSize: 11.5, color: 'var(--text-tertiary)', marginTop: 5, lineHeight: 1.5 }}>
                  Chosen by <strong style={{ color: 'var(--text-secondary)' }}>{strategy.replace(/_/g, ' ')}</strong>
                  {serving.successRate !== null && <> · {(serving.successRate * 100).toFixed(0)}% success</>}
                  {serving.p95 ? <> · {Math.round(serving.p95)}ms p95</> : null}
                  {' '}· {liveCount} provider{liveCount === 1 ? '' : 's'} in rotation behind it.
                </div>
              </>
            ) : routerOn ? (
              <div style={{ fontSize: 13, color: '#ffbd66', lineHeight: 1.5 }}>
                No provider is currently healthy. Requests will still be attempted down the
                fallback chain, but expect failures until one recovers.
              </div>
            ) : (
              <div style={{ fontSize: 12.5, color: 'var(--text-tertiary)', lineHeight: 1.55 }}>
                {status?.reason || 'The routing layer is off; the platform is using the legacy failover path.'}
              </div>
            )}
          </div>

          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', flex: '2 1 380px' }}>
            <StatTile label="In rotation" value={liveCount} sub={`${rows.length} known`} />
            <StatTile label="429s seen" value={totalRateLimits}
                      tone={totalRateLimits > 0 ? '#ffbd66' : '#fff'} sub="rolling window" />
            <StatTile label="Queue" value={queue.depth ?? 0}
                      sub={queue.max_depth ? `max ${queue.max_depth}` : ''} />
            <StatTile label="Cache" value={`${Math.round((cache.overall_hit_rate || 0) * 100)}%`} sub="hit rate" />
            <StatTile label="Spend" value={`$${(budget.spend_today_usd ?? 0).toFixed(2)}`}
                      sub={budget.daily_usd ? `of $${budget.daily_usd}/day` : 'today'} />
            <StatTile label="Tokens" value={compact(totals.total_tokens || 0)} sub="this process" />
          </div>
        </div>
      </div>

      {/* ── Control rail: every switch that used to be its own card. ─────── */}
      <div style={{
        borderRadius: 16, padding: '14px 17px',
        border: '1px solid rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.025)',
        display: 'flex', gap: 18, flexWrap: 'wrap', alignItems: 'flex-start',
      }}>
        <Segmented
          label="Paid access"
          value={!!policy?.allow_paid}
          busy={policyBusy || policy === null}
          onChange={onTogglePaid}
          hint={policy?.allow_paid
            ? 'Paid providers may be used when no free provider is reachable.'
            : 'Free and local providers only. Paid tiers are never auto-selected.'}
          options={[
            { value: false, label: 'Free only', color: '#46d9a4', hint: 'Never auto-select a paid provider.' },
            { value: true,  label: 'Paid allowed', color: '#ffbd66', hint: 'Allow paid providers as a last resort.' },
          ]}
        />

        <div style={{ flex: '1 1 240px', minWidth: 220 }}>
          <div style={{
            fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
            textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 5,
          }}>Routing strategy</div>
          <select
            value={strategy}
            disabled={busy || !routerOn}
            onChange={(e) => act(() => api.setLlmStrategy(e.target.value), `Strategy set to ${e.target.value}.`)}
            style={{
              width: '100%', padding: '8px 10px', borderRadius: 10,
              background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.10)',
              color: '#fff', fontSize: 12, fontFamily: 'var(--font-mono)',
              outline: 'none', cursor: routerOn ? 'pointer' : 'not-allowed',
              opacity: routerOn ? 1 : 0.5,
            }}
          >
            {strategies.map(s => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
          </select>
          <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 5, lineHeight: 1.45 }}>
            {STRATEGY_HINT[strategy] || 'Custom strategy.'}
          </div>
        </div>

        <div style={{ flex: '0 0 auto', display: 'flex', gap: 7, alignItems: 'center', paddingTop: 18 }}>
          <RowButton onClick={() => act(() => api.probeLlmProviders(), 'Probed every provider.')} disabled={busy || !routerOn}>
            Probe all
          </RowButton>
          <RowButton onClick={() => act(() => api.discoverLlmModels(), 'Model discovery complete.')} disabled={busy || !routerOn}>
            Discover models
          </RowButton>
          <RowButton onClick={() => act(async () => { await api.reloadLlmConfig(); refreshStored?.(); }, 'Configuration reloaded.')} disabled={busy}>
            Reload config
          </RowButton>
        </div>
      </div>

      {(notice || error) && (
        <div style={{
          fontSize: 11.5, padding: '8px 12px', borderRadius: 10,
          background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.09)',
          color: 'var(--text-secondary)',
        }}>{notice || error}</div>
      )}

      {/* ── One table. Filters instead of separate sections. ─────────────── */}
      <div>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginBottom: 10,
        }}>
          {FILTERS.map(f => {
            const active = filter === f.id;
            const count = rows.filter(r => {
              if (f.id === 'all') return true;
              if (f.id === 'live') return r.sources.includes('routed') && r.available;
              if (f.id === 'problem') return ['tripped', 'probing', 'degraded'].includes(r.state) || r.rateLimits > 0;
              if (f.id === 'idle') return r.state === 'configured';
              return r.state === 'unconfigured';
            }).length;
            return (
              <button key={f.id} type="button" onClick={() => setFilter(f.id)} style={{
                padding: '5px 13px', borderRadius: 999, fontSize: 11.5, fontWeight: 700,
                cursor: 'pointer', transition: 'all 0.15s',
                background: active ? 'rgba(93,162,255,0.16)' : 'rgba(255,255,255,0.035)',
                border: `1px solid ${active ? 'rgba(93,162,255,0.34)' : 'rgba(255,255,255,0.08)'}`,
                color: active ? '#fff' : 'var(--text-muted)',
              }}>
                {f.label} <span style={{ opacity: 0.6, fontFamily: 'var(--font-mono)', fontSize: 10 }}>{count}</span>
              </button>
            );
          })}
        </div>

        {/* Column header — the legend for the numbers in every row. */}
        <div style={{
          display: 'flex', alignItems: 'center', gap: 12, padding: '0 14px 7px 35px',
          fontSize: 9, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
          textTransform: 'uppercase', letterSpacing: '0.11em',
        }}>
          <span style={{ flex: '2 1 170px', minWidth: 140 }}>Provider</span>
          <span style={{ flex: '0 0 88px' }}>Success</span>
          <span style={{ flex: '0 0 62px' }}>p95</span>
          <span style={{ flex: '0 0 56px' }}>Limits</span>
          <span style={{ flex: '0 0 58px' }}>Keys</span>
          <span style={{ flex: '0 0 96px' }}>State</span>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {visible.length === 0 ? (
            <div style={{
              padding: 22, textAlign: 'center', borderRadius: 14,
              border: '1px dashed rgba(255,255,255,0.12)', color: 'var(--text-muted)', fontSize: 12.5,
            }}>Nothing matches this filter.</div>
          ) : visible.map(row => (
            <ProviderRow
              key={row.id}
              row={row}
              busy={busy}
              expanded={openId === row.id}
              onToggle={() => setOpenId(openId === row.id ? null : row.id)}
              onProbe={(id) => act(() => api.probeLlmProviders(id), `Probed ${id}.`)}
              onDisable={(id, enabled) => act(
                () => api.setLlmProviderEnabled(id, enabled),
                enabled ? `${id} restored to rotation.` : `${id} taken out of rotation.`,
              )}
              onEdit={onEditProvider}
              onDelete={onDeleteProvider}
              onTest={onTestProvider}
              onSetRenderKey={onSetRenderKey}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function compact(n) {
  const value = Number(n) || 0;
  if (value >= 1e9) return `${(value / 1e9).toFixed(1)}B`;
  if (value >= 1e6) return `${(value / 1e6).toFixed(1)}M`;
  if (value >= 1e3) return `${(value / 1e3).toFixed(1)}k`;
  return String(value);
}

export { CATALOGUE, STATE, TIER };
