import React from "react";

// ── Humanized phase labels shown to users instead of raw job metadata ─────────
const PHASE_LABELS = {
  preflight:        { label: "Inspecting repository",  icon: "🔍" },
  planning:         { label: "Planning the change",    icon: "🗺️" },
  execution:        { label: "Editing files",           icon: "⚡" },
  verification:     { label: "Verifying changes",      icon: "✅" },
  working:          { label: "Working…",               icon: "⚙️" },
  needs_approval:   { label: "Awaiting your approval", icon: "💬" },
  needs_input:      { label: "Waiting for input",      icon: "💬" },
  completed:        { label: "Done",                   icon: "✅" },
  failed:           { label: "Stopped",                icon: "❌" },
};

// ── Agent status styles ───────────────────────────────────────────────────────
const STATUS_STYLES = {
  idle:    "bg-gray-500/20 text-gray-400 border-gray-500/30",
  running: "bg-green-500/20 text-green-400 border-green-500/30 animate-pulse",
  waiting: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  error:   "bg-red-500/20 text-red-400 border-red-500/30",
  done:    "bg-blue-500/20 text-blue-400 border-blue-500/30",
};

const STATUS_DOTS = {
  idle:    "bg-gray-500",
  running: "bg-green-400 animate-pulse",
  waiting: "bg-yellow-400",
  error:   "bg-red-500",
  done:    "bg-blue-400",
};

const ROLE_ICONS = {
  planner:     "🗺️",
  implementer: "⚡",
  reviewer:    "🔍",
  judge:       "⚖️",
  scout:       "🔭",
  coordinator: "🎯",
};

// ── JobProgressPanel — shown when a job is running but agents haven't spawned ─
function JobProgressPanel({ job }) {
  if (!job) return null;

  const phase = job.phase || "working";
  const status = job.status || "running";
  const phaseInfo = PHASE_LABELS[phase] || PHASE_LABELS.working;

  // Last few progress events for the timeline
  const events = job.progress_events || [];
  const recentEvents = events.slice(-6);
  const latestMessage = recentEvents[recentEvents.length - 1]?.message || null;

  const isActive = ["queued", "running"].includes(status);
  const isFailed = status === "failed" || status === "cancelled";
  const isDone   = status === "succeeded";

  const containerStyle = isFailed
    ? "border-red-500/30 bg-red-500/5"
    : isDone
    ? "border-blue-500/30 bg-blue-500/5"
    : "border-white/10 bg-white/[0.03]";

  return (
    <div className={`rounded-lg border p-3 text-xs space-y-2 ${containerStyle}`}>
      {/* Phase header */}
      <div className="flex items-center gap-2">
        <span className="text-base leading-none">{phaseInfo.icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            {isActive && (
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse flex-shrink-0" />
            )}
            <span className="font-semibold text-white truncate">{phaseInfo.label}</span>
          </div>
          {latestMessage && (
            <div className="text-[10px] text-gray-400 truncate mt-0.5">{latestMessage}</div>
          )}
        </div>
        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium capitalize border ${
          isFailed ? "border-red-500/30 bg-red-500/10 text-red-400"
          : isDone  ? "border-blue-500/30 bg-blue-500/10 text-blue-400"
          : "border-green-500/30 bg-green-500/10 text-green-400"
        }`}>
          {isDone ? "done" : isFailed ? status : "running"}
        </span>
      </div>

      {/* Progress event timeline */}
      {recentEvents.length > 0 && (
        <div className="space-y-1 pt-1 border-t border-white/5">
          {recentEvents.map((evt, i) => (
            <div key={i} className={`flex items-start gap-1.5 ${i === recentEvents.length - 1 ? "text-gray-300" : "text-gray-600"}`}>
              <span className="w-1 h-1 rounded-full bg-current mt-1.5 flex-shrink-0" />
              <span className="text-[10px] leading-relaxed">{evt.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* Phase breadcrumb */}
      {isActive && (
        <div className="flex items-center gap-1 pt-1 border-t border-white/5">
          {["preflight", "planning", "execution", "verification"].map((p, idx) => {
            const phases = ["preflight", "planning", "execution", "verification"];
            const currentIdx = phases.indexOf(phase);
            const isCurrentPhase = p === phase;
            const isPast = phases.indexOf(p) < currentIdx;
            return (
              <React.Fragment key={p}>
                <span className={`text-[9px] font-mono uppercase tracking-wider px-1 py-0.5 rounded ${
                  isCurrentPhase ? "text-white bg-white/10"
                  : isPast ? "text-gray-500"
                  : "text-gray-700"
                }`}>
                  {PHASE_LABELS[p]?.label.split(" ")[0] || p}
                </span>
                {idx < 3 && <span className="text-gray-700 text-[9px]">›</span>}
              </React.Fragment>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── AgentCard ─────────────────────────────────────────────────────────────────
function AgentCard({ agent }) {
  const statusStyle = STATUS_STYLES[agent.status] ?? STATUS_STYLES.idle;
  const dotStyle    = STATUS_DOTS[agent.status]   ?? STATUS_DOTS.idle;
  const icon        = ROLE_ICONS[agent.role?.toLowerCase()] ?? "🤖";

  return (
    <div className={`rounded-lg border p-3 text-xs ${statusStyle}`}>
      <div className="flex items-center gap-2 mb-2">
        <span className="text-base">{icon}</span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotStyle}`} />
            <span className="font-semibold truncate">{agent.name}</span>
          </div>
          <div className="text-[10px] opacity-60 capitalize">{agent.role}</div>
        </div>
        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium capitalize border ${statusStyle}`}>
          {agent.status}
        </span>
      </div>

      {agent.current_task && (
        <div className="mb-2 p-1.5 bg-black/20 rounded text-[11px] leading-relaxed">
          {agent.current_task}
        </div>
      )}

      <div className="flex items-center justify-between opacity-60">
        {agent.last_active && <span>{formatRelative(agent.last_active)}</span>}
        {agent.messages_sent !== undefined && <span>{agent.messages_sent} msgs</span>}
      </div>

      {agent.tools_used && agent.tools_used.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {agent.tools_used.slice(-4).map((tool) => (
            <span key={tool} className="px-1.5 py-0.5 rounded bg-black/20 text-[10px] font-mono">
              {tool}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Relative time formatter ───────────────────────────────────────────────────
function formatRelative(isoString) {
  try {
    const diff = Date.now() - new Date(isoString).getTime();
    if (diff < 5000)   return "just now";
    if (diff < 60000)  return `${Math.floor(diff / 1000)}s ago`;
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    return `${Math.floor(diff / 3600000)}h ago`;
  } catch {
    return isoString;
  }
}

// ── Main component ────────────────────────────────────────────────────────────
export default function AgentStatusPanel({
  sessionId,
  agents = [],
  job = null,
  loading = false,
  error = null,
  className = "",
}) {
  const activeCount  = agents.filter((a) => a.status === "running").length;
  const waitingCount = agents.filter((a) => a.status === "waiting").length;

  // Determine whether to show the job progress panel instead of (or alongside) agents.
  // Show it when: there is an active job AND no agents have spawned yet.
  const jobIsActive = job && ["queued", "running"].includes(job.status);
  const showJobProgress = jobIsActive && agents.length === 0;
  // Show empty state only when no agents AND no active job
  const showEmpty = !loading && !error && agents.length === 0 && !showJobProgress;

  return (
    <div className={`bg-gray-950 rounded-xl border border-gray-800 overflow-hidden ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800 bg-gray-900">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-200">Agent Status</span>
          {sessionId && (
            <span className="text-xs text-gray-500 font-mono">#{sessionId.slice(0, 8)}</span>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs text-gray-500">
          {activeCount  > 0 && <span className="text-green-400">{activeCount} running</span>}
          {waitingCount > 0 && <span className="text-yellow-400">{waitingCount} waiting</span>}
          {agents.length > 0 && <span>{agents.length} agents</span>}
          {jobIsActive && agents.length === 0 && (
            <span className="text-green-400 flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse inline-block" />
              running
            </span>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="p-3">
        {loading && (
          <div className="flex items-center justify-center py-8 text-gray-600 text-sm">
            Loading agents…
          </div>
        )}
        {error && (
          <div className="flex items-center justify-center py-8 text-red-500 text-sm">
            {error}
          </div>
        )}

        {/* Job progress panel — shown when job is running but agents haven't spawned */}
        {showJobProgress && <JobProgressPanel job={job} />}

        {/* Empty state */}
        {showEmpty && (
          <div className="flex flex-col items-center justify-center py-8 text-gray-600 gap-2">
            <span className="text-2xl">🤖</span>
            <span className="text-sm">No active agents</span>
          </div>
        )}

        {/* Agent cards */}
        {agents.length > 0 && (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {agents.map((agent) => (
              <AgentCard key={agent.id} agent={agent} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
