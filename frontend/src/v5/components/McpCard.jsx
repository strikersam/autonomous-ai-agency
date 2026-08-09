import React from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle,
  Check,
  Loader2,
  Plug,
  RefreshCw,
  Search,
  ShieldAlert,
  SlidersHorizontal,
  X,
} from 'lucide-react';
import * as api from '../../api';

/**
 * McpCard — the MCP section of the Providers screen.
 *
 * An MCP server is a provider of *capability* rather than of tokens, which is
 * why it belongs here next to the LLM providers rather than on its own screen.
 * Today the agency connects to one: the Render MCP server, which is the only
 * view it has of platform-level failures. `agent/log_monitor.py` attaches to
 * this process's root logger, so a build failure, an OOM kill, or a container
 * that died before FastAPI booted leaves no trace it can act on — the process
 * was never alive to log it. Render MCP is where those come from.
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
 * Reads: GET /api/render/health, /api/render/ops/status
 * Action: GET /api/render/ops/scan — read-only, files nothing.
 */

const CARD = 'bg-[#111111] border border-[#002FA7]/20 rounded-xl p-5 sm:p-6 mb-6';

function Pill({ tone, children }) {
  const tones = {
    ok: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
    warn: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
    bad: 'border-red-500/30 bg-red-500/10 text-red-400',
    idle: 'border-white/10 bg-white/5 text-[#777777]',
  };
  return (
    <span className={`rounded border px-2 py-0.5 text-[10px] font-medium ${tones[tone] || tones.idle}`}>
      {children}
    </span>
  );
}

/** One of the three chain stages, with the reason when it is not satisfied. */
function Stage({ label, ok, okText, badText, tone = 'bad' }) {
  return (
    <div className="flex items-start gap-2.5 py-2">
      <span className="mt-0.5 shrink-0">
        {ok ? <Check size={14} className="text-emerald-400" />
            : <X size={14} className={tone === 'warn' ? 'text-amber-400' : 'text-red-400'} />}
      </span>
      <div className="min-w-0">
        <div className="text-[12px] font-medium text-white">{label}</div>
        <div className="text-[11px] text-[#777777] mt-0.5">{ok ? okText : badText}</div>
      </div>
    </div>
  );
}

function Stat({ label, value }) {
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wider text-[#555555] font-mono">{label}</div>
      <div className="text-sm text-white mt-0.5">{value}</div>
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
  const heals = Boolean(ops?.self_heal_ready);
  const findings = scan?.findings || [];

  return (
    <div className={CARD} data-testid="mcp-card">
      <div className="flex flex-wrap items-start justify-between gap-3 mb-4">
        <div className="flex items-start gap-2.5">
          <Plug size={16} className="text-[#002FA7] mt-0.5 shrink-0" />
          <div>
            <h2 className="text-base font-semibold text-white">MCP</h2>
            <p className="text-[11px] text-[#555555] mt-0.5">
              Capability providers reached over Model Context Protocol
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={runScan}
            disabled={scanning || !configured}
            title={configured ? 'Ask Render what is wrong right now — read-only, files nothing'
                              : 'Needs RENDER_API_KEY before a scan can run'}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-[#A0A0A0] transition-colors enabled:hover:bg-white/5 disabled:opacity-40"
          >
            {scanning ? <Loader2 size={13} className="animate-spin" /> : <Search size={13} />}
            Scan now
          </button>
          <button
            onClick={refresh}
            className="rounded-lg border border-white/10 p-1.5 text-[#A0A0A0] transition-colors hover:bg-white/5"
            title="Refresh"
          >
            <RefreshCw size={13} />
          </button>
        </div>
      </div>

      {loadErr && (
        <div className="mb-4 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" /> {loadErr}
        </div>
      )}

      {/* ── Render MCP server ────────────────────────────────────────────── */}
      <div className="rounded-lg border border-white/10 bg-[#0C0C0C] p-4">
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <span className="text-[13px] font-semibold text-white">Render</span>
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
        <p className="text-[11px] text-[#777777] leading-relaxed">
          Platform-level view of the deployment: build failures, OOM kills, restarts, and error-log
          spikes. These never reach the application logs — the process was not alive to write them.
        </p>

        {/* The three stages, in dependency order. */}
        <div className="mt-3 divide-y divide-white/5">
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
            badText="Findings are detected but nothing will fix them — the improvement loop is not running. Check “Improvement loop” and “Run background services in the web process” in Platform Controls."
          />
        </div>

        {ops && (
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-4 border-t border-white/5 pt-3">
            <Stat label="Filed" value={ops.findings_filed ?? 0} />
            <Stat label="Dropped" value={ops.findings_dropped ?? 0} />
            <Stat label="Cooldowns" value={ops.active_cooldowns ?? 0} />
            <Stat label="Ticks" value={ops.ticks ?? 0} />
          </div>
        )}

        {ops?.findings_dropped > 0 && (
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-[11px] text-amber-400">
            <ShieldAlert size={13} className="mt-0.5 shrink-0" />
            <span>
              {ops.findings_dropped} finding{ops.findings_dropped === 1 ? '' : 's'} detected but never
              filed, so no repair was scheduled for {ops.findings_dropped === 1 ? 'it' : 'them'}. They
              are retried on the next tick — the cooldown is only claimed once a finding is actually filed.
            </span>
          </div>
        )}

        {health && !health.reachable && health.reason && (
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-[11px] text-red-400">
            <AlertTriangle size={13} className="mt-0.5 shrink-0" />
            <span className="break-all">MCP endpoint: {health.reason}</span>
          </div>
        )}

        {ops?.last_error && (
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-[11px] text-red-400">
            <AlertTriangle size={13} className="mt-0.5 shrink-0" />
            <span className="break-all">{ops.last_error}</span>
          </div>
        )}
      </div>

      {/* ── Scan result ──────────────────────────────────────────────────── */}
      {scanErr && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-400">
          <AlertTriangle size={14} className="mt-0.5 shrink-0" /> {scanErr}
        </div>
      )}
      {scan && (
        <div className="mt-3 rounded-lg border border-white/10 bg-[#0C0C0C] p-4" data-testid="mcp-scan-result">
          <div className="text-[11px] uppercase tracking-wider text-[#555555] font-mono mb-2">
            Scan result — read-only, nothing filed
          </div>
          {findings.length === 0 ? (
            <p className="text-xs text-emerald-400">Render reports no platform failures right now.</p>
          ) : (
            <ul className="space-y-2">
              {findings.map((f, i) => (
                <li key={f.signature || i} className="text-xs">
                  <div className="flex flex-wrap items-center gap-2">
                    <Pill tone={f.severity === 'critical' ? 'bad' : 'warn'}>{f.severity || 'issue'}</Pill>
                    <span className="text-white">{f.title}</span>
                  </div>
                  {f.service_name && (
                    <div className="text-[10px] text-[#555555] mt-0.5 font-mono">{f.kind} · {f.service_name}</div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <Link
        to="/controls"
        className="mt-4 inline-flex items-center gap-1.5 text-[11px] text-[#4477FF] hover:underline"
      >
        <SlidersHorizontal size={12} />
        Configure in Platform Controls
      </Link>
    </div>
  );
}
