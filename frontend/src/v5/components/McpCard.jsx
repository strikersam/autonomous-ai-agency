import React from 'react';
import { Link } from 'react-router-dom';
import * as api from '../../api';

/**
 * McpCard — the Render section of Providers → MCP.
 *
 * An MCP server is a provider of *capability* rather than of tokens, which is
 * why it belongs here next to the LLM providers rather than on its own screen.
 * `MCPTab` lists every registered server and its measured status; this card
 * covers the one server whose job is not "expose tools" but "watch the
 * platform", and whose usefulness therefore depends on a chain rather than a
 * single reachability check.
 *
 * The Render MCP server is the only view the agency has of platform-level
 * failures. `agent/log_monitor.py` attaches to this process's root logger, so a
 * build failure, an OOM kill, or a container that died before FastAPI booted
 * leaves no trace it can act on — the process was never alive to log it.
 *
 * The card answers three questions in order, because each one only matters if
 * the previous one is true:
 *
 *   1. Is it connected?    — credentials present and the endpoint reachable.
 *   2. Is it watching?     — the ops loop enabled and ticking.
 *   3. Does it heal?       — findings reach the ImprovementLoop, which schedules
 *                            the repair. Without that last hop the monitor looks
 *                            perfectly healthy while nothing is being fixed, so
 *                            it is called out rather than implied.
 *
 * Styled with inline styles rather than Tailwind utilities, like every other v5
 * component: `.v5-root *` in the v5 theme sets `margin:0; padding:0` at equal
 * specificity to a Tailwind spacing utility and is injected after the CSS
 * bundle, so `px-4` inside this shell loses the cascade.
 *
 * Reads: GET /api/render/health, /api/render/ops/status
 * Action: GET /api/render/ops/scan — read-only, files nothing.
 */

const TONES = {
  ok: { border: '1px solid rgba(70,217,164,0.30)', background: 'rgba(70,217,164,0.10)', color: '#46d9a4' },
  warn: { border: '1px solid rgba(255,189,102,0.30)', background: 'rgba(255,189,102,0.10)', color: '#ffbd66' },
  bad: { border: '1px solid rgba(255,107,125,0.30)', background: 'rgba(255,107,125,0.10)', color: '#ff6b7d' },
  idle: { border: '1px solid rgba(255,255,255,0.10)', background: 'rgba(255,255,255,0.05)', color: 'var(--text-muted)' },
};

const NOTE = (tone) => ({
  marginTop: 11, display: 'flex', alignItems: 'flex-start', gap: 8,
  borderRadius: 10, padding: '8px 11px', fontSize: 11, lineHeight: 1.55,
  ...TONES[tone],
});

const BTN = {
  display: 'inline-flex', alignItems: 'center', gap: 6, borderRadius: 10,
  padding: '7px 12px', fontSize: 12, background: 'rgba(255,255,255,0.04)',
  border: '1px solid rgba(255,255,255,0.10)', color: 'var(--text-secondary)',
};

function Pill({ tone, children }) {
  return (
    <span style={{
      borderRadius: 6, padding: '2px 7px', fontSize: 10, fontWeight: 600,
      fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap', ...(TONES[tone] || TONES.idle),
    }}>
      {children}
    </span>
  );
}

/** One of the three chain stages, with the reason when it is not satisfied. */
function Stage({ label, ok, okText, badText, tone = 'bad' }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 10, padding: '8px 0',
      borderTop: '1px solid rgba(255,255,255,0.05)',
    }}>
      <span style={{
        marginTop: 1, flexShrink: 0, fontSize: 12,
        color: ok ? '#46d9a4' : (tone === 'warn' ? '#ffbd66' : '#ff6b7d'),
      }}>
        {ok ? '✓' : '✕'}
      </span>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>{label}</div>
        <div style={{ marginTop: 2, fontSize: 11, lineHeight: 1.55, color: 'var(--text-muted)' }}>
          {ok ? okText : badText}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <div style={{
        fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.12em',
        fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
      }}>
        {label}
      </div>
      <div style={{ marginTop: 2, fontSize: 14, color: 'var(--text-primary)' }}>{value}</div>
    </div>
  );
}

function relTime(iso) {
  if (!iso) return 'never';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return 'never';
  const diff = Date.now() - then;
  if (diff < 60_000) return `${Math.max(1, Math.round(diff / 1000))}s ago`;
  if (diff < 3_600_000) return `${Math.round(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.round(diff / 3_600_000)}h ago`;
  return `${Math.round(diff / 86_400_000)}d ago`;
}

export default function McpCard() {
  const [ops, setOps] = React.useState(null);
  const [health, setHealth] = React.useState(null);
  const [loadErr, setLoadErr] = React.useState(null);
  const [scanning, setScanning] = React.useState(false);
  const [scan, setScan] = React.useState(null);
  const [scanErr, setScanErr] = React.useState(null);

  const refresh = React.useCallback(async () => {
    try {
      const { data } = await api.getRenderOpsStatus();
      setOps(data);
      setLoadErr(null);
    } catch (e) {
      // A non-admin or a backend without the Render router: say so plainly
      // rather than rendering a card full of zeroes that look like "healthy".
      setLoadErr(api.fmtErr(e?.response?.data?.detail) || 'Could not read Render ops status.');
      setOps(null);
    }
    try {
      const { data } = await api.getRenderHealth();
      setHealth(data);
    } catch {
      setHealth(null);
    }
  }, []);

  React.useEffect(() => {
    refresh();
    const id = setInterval(refresh, 30_000);
    return () => clearInterval(id);
  }, [refresh]);

  const runScan = async () => {
    setScanning(true);
    setScanErr(null);
    setScan(null);
    try {
      const { data } = await api.runRenderOpsScan();
      setScan(data);
    } catch (e) {
      setScanErr(api.fmtErr(e?.response?.data?.detail) || 'Scan failed.');
    } finally {
      setScanning(false);
      refresh();
    }
  };

  const configured = Boolean(ops?.configured);
  const watching = Boolean(ops?.enabled) && configured;
  // Gated on `watching`, not just the backend flag: repairs are scheduled off
  // findings, and a stopped monitor produces none. Showing this green while
  // Monitoring is red would claim repairs are active with nothing feeding them.
  const heals = watching && Boolean(ops?.self_heal_ready);
  const findings = scan?.findings || [];

  return (
    <div
      data-testid="mcp-card"
      style={{
        padding: '16px 16px 18px', borderRadius: 16, marginBottom: 16,
        background: 'rgba(93,162,255,0.04)', border: '1px solid rgba(93,162,255,0.18)',
      }}
    >
      <div style={{
        display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start',
        justifyContent: 'space-between', gap: 12, marginBottom: 14,
      }}>
        <div>
          <h2 style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
            Render — platform watch
          </h2>
          <p style={{ marginTop: 2, fontSize: 11, color: 'var(--text-muted)' }}>
            The MCP server that reports deployment failures, not just tools
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <button
            onClick={runScan}
            disabled={scanning || !configured}
            title={configured ? 'Ask Render what is wrong right now — read-only, files nothing'
                              : 'Needs RENDER_API_KEY before a scan can run'}
            style={{
              ...BTN,
              cursor: scanning || !configured ? 'not-allowed' : 'pointer',
              opacity: scanning || !configured ? 0.4 : 1,
            }}
          >
            {scanning ? 'Scanning…' : 'Scan now'}
          </button>
          <button onClick={refresh} title="Refresh" style={{ ...BTN, cursor: 'pointer' }}>
            Refresh
          </button>
        </div>
      </div>

      {loadErr && <div style={{ ...NOTE('bad'), marginTop: 0, marginBottom: 14 }}>{loadErr}</div>}

      <div style={{
        borderRadius: 12, padding: 15,
        background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)',
      }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, marginBottom: 5 }}>
          <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Render</span>
          <Pill tone={configured ? 'ok' : 'idle'}>{configured ? 'Connected' : 'Not configured'}</Pill>
          {ops?.write_allowed
            ? <Pill tone="warn">Writes allowed</Pill>
            : <Pill tone="idle">Read-only</Pill>}
          {health && (
            <Pill tone={health.reachable ? 'ok' : 'bad'}>
              {health.reachable ? `Reachable · ${health.tool_count ?? 0} tools` : 'Unreachable'}
            </Pill>
          )}
        </div>
        <p style={{ fontSize: 11, lineHeight: 1.6, color: 'var(--text-muted)' }}>
          Platform-level view of the deployment: build failures, OOM kills, restarts, and error-log
          spikes. These never reach the application logs — the process was not alive to write them.
        </p>

        {/* The three stages, in dependency order. */}
        <div style={{ marginTop: 12 }}>
          <Stage
            label="Connection"
            ok={configured}
            okText="RENDER_API_KEY is set and the MCP endpoint is configured."
            badText="Set RENDER_API_KEY in the Render dashboard. Without it the monitor stays dormant."
          />
          <Stage
            label="Monitoring"
            ok={watching}
            tone="warn"
            okText={`Polling every ${ops?.interval_seconds ?? '—'}s · ${ops?.ticks ?? 0} tick${ops?.ticks === 1 ? '' : 's'} · last ${relTime(ops?.last_tick_at)}`}
            badText={configured
              ? 'Ops loop is off. Turn on “Render ops loop” in Platform Controls.'
              : 'Cannot watch until the connection above is configured.'}
          />
          <Stage
            label="Self-healing"
            ok={heals}
            tone="warn"
            okText="Findings are filed to the improvement loop, which schedules the repair task automatically."
            badText={watching
              ? "Findings are detected but nothing will fix them — the improvement loop is not running. Check “Improvement loop” and “Run background services in the web process” in Platform Controls."
              : "Nothing is being monitored, so there are no findings to repair. Fix the stage above first."}
          />
        </div>

        {ops && (
          <div style={{
            marginTop: 15, paddingTop: 12, borderTop: '1px solid rgba(255,255,255,0.05)',
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(90px, 1fr))', gap: 14,
          }}>
            <Stat label="Filed" value={ops.findings_filed ?? 0} />
            <Stat label="Dropped" value={ops.findings_dropped ?? 0} />
            <Stat label="Cooldowns" value={ops.active_cooldowns ?? 0} />
            <Stat label="Ticks" value={ops.ticks ?? 0} />
          </div>
        )}

        {ops?.findings_dropped > 0 && (
          <div style={NOTE('warn')}>
            <span>
              {ops.findings_dropped} finding{ops.findings_dropped === 1 ? '' : 's'} detected but never
              filed, so no repair was scheduled for {ops.findings_dropped === 1 ? 'it' : 'them'}. They
              are retried on the next tick — the cooldown is only claimed once a finding is actually filed.
            </span>
          </div>
        )}

        {health && !health.reachable && health.reason && (
          <div style={NOTE('bad')}>
            <span style={{ wordBreak: 'break-all' }}>MCP endpoint: {health.reason}</span>
          </div>
        )}

        {ops?.last_error && (
          <div style={NOTE('bad')}>
            <span style={{ wordBreak: 'break-all' }}>{ops.last_error}</span>
          </div>
        )}
      </div>

      {scanErr && <div style={NOTE('bad')}>{scanErr}</div>}
      {scan && (
        <div
          data-testid="mcp-scan-result"
          style={{
            marginTop: 12, borderRadius: 12, padding: 15,
            background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.08)',
          }}
        >
          <div style={{
            marginBottom: 9, fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.12em',
            fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
          }}>
            Scan result — read-only, nothing filed
          </div>
          {findings.length === 0 ? (
            <p style={{ fontSize: 12, color: '#46d9a4' }}>Render reports no platform failures right now.</p>
          ) : (
            <ul style={{ display: 'flex', flexDirection: 'column', gap: 9, listStyle: 'none' }}>
              {findings.map((f, i) => (
                <li key={f.signature || i} style={{ fontSize: 12 }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8 }}>
                    <Pill tone={f.severity === 'critical' ? 'bad' : 'warn'}>{f.severity || 'issue'}</Pill>
                    <span style={{ color: 'var(--text-primary)' }}>{f.title}</span>
                  </div>
                  {f.service_name && (
                    <div style={{
                      marginTop: 2, fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-muted)',
                    }}>
                      {f.kind} · {f.service_name}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <Link
        to="/v5/controls"
        style={{
          marginTop: 14, display: 'inline-block', fontSize: 11,
          color: 'var(--accent)', textDecoration: 'none',
        }}
      >
        Configure in Platform Controls →
      </Link>
    </div>
  );
}
