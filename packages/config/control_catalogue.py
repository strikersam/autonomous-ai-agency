"""packages/config/control_catalogue.py — the 109 operator-facing controls.

The declarative table itself: which feature switches and multi-option settings
an operator may change from the dashboard, and what each one means. The types
live in :mod:`packages.config.control_specs`; the lookup and validation API
lives in :mod:`packages.config.control_registry`, which is what callers import.

What belongs here
-----------------
Switches and *choices* — "which agent runtime", "which brain", "is the CEO loop
on". Secrets (``*_API_KEY``, tokens, passwords) and infrastructure endpoints
(``MONGO_URL``, ``*_BASE_URL``) deliberately do **not** belong here: they stay
environment-only per the repository constitution, and this table is served to
the dashboard.

Contract
--------
Every ``key`` must be a real environment variable read somewhere in the Python
source. ``tests/test_platform_controls.py`` enforces that — a control describing
a switch that no code reads would be a lie in the UI.

``default`` is the *code* default: the value the reader falls back to when the
variable is unset. It is written as the env string that produces that behaviour
so the UI, the env, and the code all agree on one representation.

``live`` records whether a change takes effect without a process restart:

* ``live=True``  — the value is re-read from ``os.environ`` (or from the
  ``settings`` singleton, which :mod:`packages.config.control_overrides`
  re-initialises in place) at each use.
* ``live=False`` — the value is captured at import time or baked into a cached
  singleton, so the dashboard shows a "restart required" badge instead of
  pretending the change already landed.

File size
---------
This module is over the 800-line limit in AGENTS.md §8, and deliberately so. It
is one flat declarative table with no logic — every executable line moved to
``control_specs.py`` and ``control_registry.py``, which are both well inside the
limit. Cutting the table at a group boundary would not reduce any reader's
working set; it would only make "where is control X declared" a two-step
question. Revisit if logic ever accumulates here, which is exactly what the
limit exists to catch.
"""

from __future__ import annotations

from packages.config.control_specs import (
    ControlGroup,
    ControlOption,
    ControlSpec,
    KIND_CHOICE,
    KIND_NUMBER,
    KIND_TOGGLE,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    _number,
    _toggle,
)

# ── Groups ────────────────────────────────────────────────────────────────────

GROUPS: tuple[ControlGroup, ...] = (
    ControlGroup(
        "agent_runtime",
        "Agent Runtimes",
        "Which execution backend runs agent work, and which runtimes are "
        "registered at all. Unavailable runtimes are skipped by the router and "
        "fall back to the internal agent — enabling one is never fatal.",
    ),
    ControlGroup(
        "brain_routing",
        "Brain & Model Routing",
        "Which LLM answers, in what order, and how aggressively results are cached.",
    ),
    ControlGroup(
        "autonomy",
        "Autonomy Loops",
        "The background engines that turn signals into work: the CEO loop, "
        "self-healing, trend watching, and self-repo shipping.",
    ),
    ControlGroup(
        "agent_loop",
        "Agent Loop Budgets",
        "Per-task limits for the plan → execute → verify loop.",
    ),
    ControlGroup(
        "governance",
        "Governance & Safety",
        "Policy evaluation, sandboxing, output filtering, and the paid-provider "
        "guard rails.",
    ),
    ControlGroup(
        "platform_ops",
        "Platform Operations",
        "Render platform monitoring and the operational-incident tracker.",
    ),
    ControlGroup(
        "integrations",
        "Integrations",
        "Telegram, voice, browser automation, and the published model catalogue.",
    ),
    ControlGroup(
        "observability",
        "Observability & Proxy",
        "Tracing plus the response-shaping switches on the OpenAI-compatible proxy.",
    ),
)


# ── Shared option sets ────────────────────────────────────────────────────────

_RUNTIME_IDS: tuple[ControlOption, ...] = (
    ControlOption("internal_agent", "Internal Agent", "In-process plan → execute → verify loop. Always registered."),
    ControlOption("hermes", "Hermes", "Hermes coding sidecar (runs in-process on Render by default)."),
    ControlOption("e2b", "E2B Sandbox", "Firecracker micro-VM sandbox. Needs E2B_API_KEY."),
    ControlOption("docker_agent", "Docker Agent", "Containerised agent. Needs a Docker socket."),
    ControlOption("goose", "Goose", "Block's Goose CLI."),
    ControlOption("aider", "Aider", "Aider CLI, repo-editing focused."),
    ControlOption("opencode", "OpenCode", "OpenCode sidecar."),
    ControlOption("claude_code", "Claude Code", "Claude Code CLI runtime."),
    ControlOption("jcode", "JCode", "JCode runtime."),
    ControlOption("openhands", "OpenHands", "OpenHands runtime."),
    ControlOption("prime_agent", "Prime Agent", "Prime Agent runtime."),
    ControlOption("task_harness", "Task Harness", "Cross-harness task adapter."),
)

_AUTO = ControlOption("", "Auto (router decides)", "Leave unset — the routing policy picks.")

_TASK_ROUTE_OPTIONS: tuple[ControlOption, ...] = (_AUTO, *_RUNTIME_IDS)


# ── The catalogue ─────────────────────────────────────────────────────────────
#
# Ordering inside a group is the display order.

_AGENT_RUNTIME: tuple[ControlSpec, ...] = (
    ControlSpec(
        key="RUNTIME_DEFAULT",
        label="Default runtime",
        group="agent_runtime",
        kind=KIND_CHOICE,
        default="internal_agent",
        help=(
            "Runtime the router prefers for any task with no task-type override. "
            "Falls back to the internal agent whenever the choice is unavailable. "
            "Unset, the code default is the internal agent — or the Docker agent "
            "when the Docker runtime is enabled."
        ),
        options=_RUNTIME_IDS,
        live=True,
        risk=RISK_MEDIUM,
    ),
    ControlSpec(
        key="RUNTIME_CODE_GENERATION",
        label="Runtime for code generation",
        group="agent_runtime",
        kind=KIND_CHOICE,
        default="",
        help="Overrides the default runtime for code-generation tasks only.",
        options=_TASK_ROUTE_OPTIONS,
        live=True,
    ),
    ControlSpec(
        key="RUNTIME_CODE_REVIEW",
        label="Runtime for code review",
        group="agent_runtime",
        kind=KIND_CHOICE,
        default="",
        help="Overrides the default runtime for code-review tasks only.",
        options=_TASK_ROUTE_OPTIONS,
        live=True,
    ),
    ControlSpec(
        key="RUNTIME_REPO_EDITING",
        label="Runtime for repo editing",
        group="agent_runtime",
        kind=KIND_CHOICE,
        default="",
        help="Overrides the default runtime for repo-editing tasks only.",
        options=_TASK_ROUTE_OPTIONS,
        live=True,
    ),
    ControlSpec(
        key="RUNTIME_GIT_OPS",
        label="Runtime for git operations",
        group="agent_runtime",
        kind=KIND_CHOICE,
        default="",
        help="Overrides the default runtime for git-operation tasks only.",
        options=_TASK_ROUTE_OPTIONS,
        live=True,
    ),
    _toggle(
        "RUNTIME_EXTERNAL_DISABLED",
        "Register no external runtimes",
        "agent_runtime",
        "false",
        "Master off-switch. When on, only the internal agent (plus anything "
        "explicitly enabled below) is registered — useful on a constrained host "
        "where health polling is unwanted.",
        risk=RISK_MEDIUM,
    ),
    _toggle(
        "RUNTIME_HERMES_ENABLED",
        "Hermes runtime",
        "agent_runtime",
        "true",
        "Register the Hermes adapter. On by default unless external runtimes are disabled.",
    ),
    _toggle(
        "RUN_HERMES_IN_PROCESS",
        "Run Hermes in this process",
        "agent_runtime",
        "true",
        "Host the Hermes server on port 8100 inside the web process, so one "
        "free-tier service covers both.",
    ),
    _toggle(
        "RUNTIME_GOOSE_ENABLED",
        "Goose runtime",
        "agent_runtime",
        "true",
        "Register the Goose adapter. On by default unless external runtimes are disabled.",
    ),
    _toggle(
        "RUNTIME_AIDER_ENABLED",
        "Aider runtime",
        "agent_runtime",
        "true",
        "Register the Aider adapter. On by default unless external runtimes are disabled.",
    ),
    _toggle("RUNTIME_OPENCODE_ENABLED", "OpenCode runtime", "agent_runtime", "false", "Register the OpenCode adapter."),
    _toggle(
        "RUNTIME_CLAUDE_CODE_ENABLED",
        "Claude Code runtime",
        "agent_runtime",
        "false",
        "Register the Claude Code adapter.",
    ),
    _toggle("RUNTIME_JCODE_ENABLED", "JCode runtime", "agent_runtime", "false", "Register the JCode adapter."),
    _toggle(
        "RUNTIME_OPENHANDS_ENABLED",
        "OpenHands runtime",
        "agent_runtime",
        "false",
        "Register the OpenHands adapter.",
    ),
    _toggle(
        "RUNTIME_PRIME_AGENT_ENABLED",
        "Prime Agent runtime",
        "agent_runtime",
        "false",
        "Register the Prime Agent adapter.",
    ),
    _toggle("RUNTIME_DOCKER_ENABLED", "Docker runtime", "agent_runtime", "false", "Register the Docker agent adapter."),
    _toggle(
        "RUNTIME_E2B_ENABLED",
        "E2B sandbox runtime",
        "agent_runtime",
        "false",
        "Register the E2B adapter explicitly. It also auto-registers whenever "
        "E2B_API_KEY is set and E2B is not switched off.",
        requires=("E2B_API_KEY",),
    ),
    _toggle(
        "TASK_HARNESS_ENABLED",
        "Task harness runtime",
        "agent_runtime",
        "false",
        "Register the cross-harness task adapter.",
    ),
    _toggle(
        "TASK_HARNESS_REQUIRED",
        "Require the task harness",
        "agent_runtime",
        "false",
        "Fail internal-agent execution rather than proceeding without the harness.",
        risk=RISK_MEDIUM,
    ),
    _toggle(
        "RUNTIME_NEVER_PAID",
        "Never use paid providers",
        "agent_runtime",
        "false",
        "Hard cost ceiling: the runtime router refuses any provider that bills.",
        live=True,
        risk=RISK_MEDIUM,
    ),
    _toggle(
        "RUNTIME_REQUIRE_APPROVAL",
        "Require approval before paid escalation",
        "agent_runtime",
        "false",
        "A human must approve before the router escalates to a paid provider.",
        live=True,
    ),
    _number(
        "RUNTIME_MAX_PAID_ESCALATIONS",
        "Max paid escalations per day",
        "agent_runtime",
        "0",
        "Ceiling on paid-provider escalations in a 24h window. 0 means none.",
        live=True,
        maximum=1000,
    ),
    _number(
        "RUNTIME_HEALTH_POLL_SEC",
        "Runtime health poll interval (s)",
        "agent_runtime",
        "30",
        "How often each registered runtime is probed for availability.",
        minimum=5,
        maximum=3600,
    ),
)

_BRAIN_ROUTING: tuple[ControlSpec, ...] = (
    ControlSpec(
        key="BRAIN_PREFERENCE",
        label="Brain preference",
        group="brain_routing",
        kind=KIND_CHOICE,
        default="nvidia",
        help="Which brain the resolver reaches for first. Local choices skip the cloud chain entirely.",
        options=(
            ControlOption("nvidia", "NVIDIA NIM (cloud, free)", "Always-on free tier. The production default."),
            ControlOption("auto", "Auto", "Let provider priority decide."),
            ControlOption("ollama", "Ollama (local)", "Prefer local inference. Needs OLLAMA_BASE."),
            ControlOption("colibri", "Colibri (local GLM)", "Local JustVugg/colibri on :8081. Needs COLIBRI_URL."),
            ControlOption("local-brain", "Local brain (llama-server)", "llama-server on :8072. Needs LOCAL_BRAIN_URL."),
        ),
        live=True,
        risk=RISK_MEDIUM,
    ),
    ControlSpec(
        key="LLM_ROUTING_STRATEGY",
        label="Provider routing strategy",
        group="brain_routing",
        kind=KIND_CHOICE,
        default="priority",
        help="How the traffic director orders candidate providers for each call.",
        options=(
            ControlOption("priority", "Strict priority", "Always try providers in configured order."),
            ControlOption("weighted-shuffle", "Weighted shuffle", "Randomised, weighted by priority."),
            ControlOption("least-busy", "Least busy", "Prefer the provider with the fewest in-flight calls."),
            ControlOption("usage-based", "Usage based", "Spread load against each provider's rate limit."),
            ControlOption("latency-based", "Latency based", "Prefer the provider that has been fastest recently."),
        ),
        live=True,
        risk=RISK_MEDIUM,
    ),
    ControlSpec(
        key="OLLAMA_REASONING_EFFORT",
        label="Ollama thinking effort",
        group="brain_routing",
        kind=KIND_CHOICE,
        default="",
        help=(
            "Pins interleaved thinking for thinking-capable Ollama models. "
            "Unset keeps Ollama's own auto-enable behaviour."
        ),
        options=(
            ControlOption("", "Auto (Ollama decides)", "Recommended — the field is not sent."),
            ControlOption("high", "High", ""),
            ControlOption("medium", "Medium", ""),
            ControlOption("low", "Low", ""),
        ),
        live=True,
    ),
    _toggle(
        "ALLOW_PAID_BRAIN",
        "Allow paid brains",
        "brain_routing",
        "false",
        "Permit the resolver to select a billed model (Anthropic / Bedrock Claude).",
        live=True,
        risk=RISK_HIGH,
        requires=("ANTHROPIC_API_KEY",),
    ),
    _toggle(
        "NORTH_MINI_CODE_DEFAULT",
        "Prefer North Mini Code for coding",
        "brain_routing",
        "true",
        "Where the active provider can serve it, the coding loop prefers "
        "north-mini-code-1.0. Providers that cannot fall back automatically.",
        live=True,
    ),
    _toggle(
        "INCLUDE_LOCAL_FALLBACK",
        "Include local fallback in the chain",
        "brain_routing",
        "false",
        "Append local Ollama to the cloud fallback chain. Off in production, where there is no local model.",
    ),
    _toggle(
        "ROUTER_HEALTH_CHECK_ENABLED",
        "Provider health checks",
        "brain_routing",
        "true",
        "Probe providers so unhealthy ones are demoted before a user call hits them.",
        live=True,
    ),
    _toggle(
        "CIRCUIT_BREAKER_ENABLED",
        "Circuit breaker",
        "brain_routing",
        "true",
        "Trip a provider out of rotation after repeated failures instead of retrying into the wall.",
    ),
    _toggle(
        "RESPONSE_CACHE_ENABLED",
        "Response cache",
        "brain_routing",
        "true",
        "Cache identical completions to cut duplicate spend and latency.",
    ),
    _toggle(
        "PROMPT_CACHE_ENABLED",
        "Prompt cache",
        "brain_routing",
        "true",
        "Reuse prefix computation across calls that share a system prompt.",
    ),
    _toggle(
        "ANTHROPIC_PROMPT_CACHING",
        "Anthropic prompt caching",
        "brain_routing",
        "true",
        "Send cache-control breakpoints on Anthropic calls.",
        requires=("ANTHROPIC_API_KEY",),
    ),
    _toggle(
        "HARNESS_ROUTING_ENABLED",
        "Harness-aware routing",
        "brain_routing",
        "true",
        "Route by which coding harness issued the request.",
    ),
    _toggle(
        "STEERLM_ENABLED",
        "SteerLM steering",
        "brain_routing",
        "false",
        "Apply SteerLM attribute steering to supported NVIDIA models.",
    ),
    _toggle(
        "KIMI_BRIDGE_ENABLED",
        "Kimi bridge provider",
        "brain_routing",
        "false",
        "Register the Kimi bridge as an extra provider.",
    ),
    ControlSpec(
        key="KIMI_BRIDGE_MODE",
        label="Kimi bridge mode",
        group="brain_routing",
        kind=KIND_CHOICE,
        default="endpoint",
        help="How the Kimi bridge reaches Kimi.",
        options=(
            ControlOption("endpoint", "HTTP endpoint", "Talk to a bridge server over HTTP. Needs KIMI_BRIDGE_URL."),
            ControlOption("browser", "Browser driver", "Drive a real browser. Also needs KIMI_BRIDGE_BROWSER=true."),
        ),
    ),
    _number(
        "PROVIDER_COOLDOWN_SECONDS",
        "Provider cooldown (s)",
        "brain_routing",
        "30",
        "How long a failed provider sits out before it is retried.",
        minimum=1,
        maximum=3600,
    ),
    _number(
        "BRAIN_WATCHDOG_MAX_FAILURES",
        "Brain watchdog failure threshold",
        "brain_routing",
        "3",
        "Consecutive failures before the watchdog fails the brain over.",
        minimum=1,
        maximum=100,
    ),
)

_AUTONOMY: tuple[ControlSpec, ...] = (
    _toggle(
        "AGENCY_CEO_ENABLED",
        "CEO orchestration loop",
        "autonomy",
        "true",
        "The CEO-coordinated multi-agent loop that decomposes and dispatches work.",
        risk=RISK_MEDIUM,
    ),
    _toggle(
        "RUN_BACKGROUND_IN_WEB",
        "Run background services in the web process",
        "autonomy",
        "true",
        "Off only when a dedicated worker process runs the loops instead. Turning "
        "this off in a single-service deployment stops all autonomy.",
        risk=RISK_HIGH,
    ),
    ControlSpec(
        key="AGENCY_WORKFLOW_MODE",
        label="Workflow mode",
        group="autonomy",
        kind=KIND_CHOICE,
        default="orchestrator",
        help="Whether the golden-path orchestrator is enforced.",
        options=(
            ControlOption("orchestrator", "Orchestrator (enforced)", "Golden path only. The default."),
            ControlOption("legacy", "Legacy (permissive)", "Allow the old parallel dispatch paths, with warnings."),
        ),
        risk=RISK_MEDIUM,
    ),
    _number(
        "AGENCY_TICK_MINUTES",
        "CEO cycle interval (minutes)",
        "autonomy",
        "15",
        "How often the CEO loop assesses state and creates work — the single "
        "biggest driver of LLM call volume. Each tick runs an assessment and can "
        "materialise tasks, each of which then plans (more calls). On a free-tier "
        "brain (rate-limited / slow), a fast 5-minute cadence self-inflicts the "
        "provider serialization behind the `planning: TimeoutError` failures — "
        "raise this to make the agency calmer and let each call get through. "
        "Recommended 15+ on the free tier; lower it once you have paid capacity. "
        "Takes effect on the next restart.",
        minimum=1,
        maximum=1440,
    ),
    _toggle("AGENCY_IMPROVEMENT_ENABLED", "Improvement loop", "autonomy", "true", "Continuous self-improvement engine."),
    _toggle("AGENCY_SELF_HEAL_ENABLED", "Self-healing loop", "autonomy", "true", "Diagnose and fix detected failures."),
    _toggle("AGENCY_LOG_MONITOR_ENABLED", "Log monitor loop", "autonomy", "true", "Watch logs and file work from them."),
    _toggle(
        "AGENCY_TREND_WATCH_ENABLED",
        "Trend watcher loop",
        "autonomy",
        "true",
        "Scheduled scan of public sources for relevant developments.",
    ),
    _toggle(
        "SELF_BOOTSTRAP_ENABLED",
        "Self-bootstrap",
        "autonomy",
        "true",
        "The platform onboards itself as a company on first boot.",
    ),
    _toggle(
        "SELF_REPO_AUTO_COMMIT_ENABLED",
        "Ship self-repo changes as PRs",
        "autonomy",
        "true",
        "Agent edits to this repo reach git as a branch + PR instead of being "
        "discarded. Direct pushes to master and self-merges stay blocked "
        "regardless of this switch.",
        risk=RISK_MEDIUM,
    ),
    _toggle(
        "PORTFOLIO_MATERIALIZE_ENABLED",
        "Materialise portfolio initiatives",
        "autonomy",
        "true",
        "Turn portfolio initiatives into executable tasks.",
    ),
    _toggle(
        "CEO_SUPERVISOR_ENABLED",
        "CEO supervisor",
        "autonomy",
        "true",
        "Sweep for stalled goals and re-drive them.",
    ),
    _toggle(
        "CEO_ESCALATION_ENABLED",
        "CEO escalation",
        "autonomy",
        "true",
        "Escalate a subtask that keeps failing instead of retrying forever.",
    ),
    _toggle(
        "CEO_LLM_DECOMPOSITION",
        "LLM task decomposition",
        "autonomy",
        "true",
        "Let the CEO use an LLM to split a directive into subtasks. On by "
        "default outside tests.",
    ),
    _toggle(
        "CEO_REQUIRE_TESTS_FOR_CODE",
        "Require tests for code subtasks",
        "autonomy",
        "true",
        "A code subtask is not accepted as done without tests.",
    ),
    _toggle("ISSUE_TRIAGE_ENABLED", "GitHub issue triage", "autonomy", "false", "Auto-triage inbound repo issues."),
    _toggle("SESSION_RETRO_ENABLED", "Session retrospectives", "autonomy", "false", "Write a retro after each session."),
    _toggle(
        "TREND_HERMES_DISPATCH_ENABLED",
        "Dispatch trend findings to Hermes",
        "autonomy",
        "false",
        "Trend-watcher findings become Hermes tasks.",
    ),
    _toggle(
        "TREND_COMPANY_SCOPING_ENABLED",
        "Scope trends per company",
        "autonomy",
        "true",
        "Filter trend findings against each company's profile.",
    ),
    _toggle("LOG_WATCHER_ENABLED", "Log watcher", "autonomy", "true", "Tail logs for error signatures."),
    _toggle("LOG_WATCHER_AUTO_FILE", "Log watcher files issues", "autonomy", "false", "File an issue on a detection."),
    _toggle(
        "LOG_WATCHER_AUTO_FIX",
        "Log watcher auto-fixes",
        "autonomy",
        "false",
        "Attempt an automatic fix on a detection.",
        risk=RISK_HIGH,
    ),
    _toggle(
        "AGENT_AUTO_PR_ENABLED",
        "Agents may open PRs",
        "autonomy",
        "false",
        "Allow the agent loop to open a pull request for its own changes.",
        risk=RISK_MEDIUM,
    ),
    _toggle(
        "REPO_ALLOW_DIRECT_PUSH",
        "Allow direct pushes",
        "autonomy",
        "false",
        "Permit pushing straight to a branch instead of via a PR. Protected "
        "branches stay blocked by the autonomy gate.",
        risk=RISK_HIGH,
    ),
    _toggle(
        "EPHEMERAL_COMPANY_REAPER_ENABLED",
        "Ephemeral company reaper",
        "autonomy",
        "true",
        "Destroy non-admin companies once their TTL expires.",
    ),
)

_AGENT_LOOP: tuple[ControlSpec, ...] = (
    _number(
        "AGENT_MAX_STEPS",
        "Max steps per task",
        "agent_loop",
        "30",
        "Hard ceiling on plan → execute → verify iterations for one task.",
        live=True,
        minimum=1,
        maximum=200,
    ),
    _number(
        "AGENT_TIME_BUDGET_S",
        "Time budget per task (s)",
        "agent_loop",
        "0",
        "Wall-clock ceiling for one task. 0 means no budget.",
        live=True,
        maximum=86400,
    ),
    _number(
        "TASK_EXECUTION_TIMEOUT_SEC",
        "Task execution timeout (s)",
        "agent_loop",
        "600",
        "How long a dispatched task may run before it is abandoned.",
        live=True,
        minimum=30,
        maximum=86400,
    ),
    _number(
        "TASK_DISPATCH_CONCURRENCY",
        "Task dispatch concurrency",
        "agent_loop",
        "5",
        "How many tasks execute at once. Keep low on a free tier.",
        minimum=1,
        maximum=64,
    ),
    _toggle(
        "TASK_QUEUE_BACKPRESSURE",
        "Queue backpressure",
        "agent_loop",
        "true",
        "Refuse new work when the queue is saturated rather than piling up.",
    ),
    _toggle(
        "AGENT_CHECKPOINT_ENABLED",
        "Step checkpointing",
        "agent_loop",
        "true",
        "Persist loop state so an interrupted task can resume.",
    ),
    _toggle(
        "AGENT_CONTEXT_WINDOW_ENABLED",
        "Context-window management",
        "agent_loop",
        "true",
        "Trim and summarise context so long tasks stay inside the model window.",
    ),
    _toggle(
        "AGENT_CHAT_HISTORY_ENABLED",
        "Carry chat history into the loop",
        "agent_loop",
        "false",
        "Feed prior conversation turns to the agent as context.",
    ),
    _toggle(
        "AGENT_EMPIRICAL_VERIFY",
        "Empirical verification",
        "agent_loop",
        "false",
        "Verify by executing the result, not just by reading it.",
    ),
    _toggle(
        "AGENT_CROSS_VERIFY_ENABLED",
        "Cross-model verification",
        "agent_loop",
        "false",
        "Have a second model check the first model's output. Doubles verify cost.",
    ),
    _toggle(
        "MEMORY_AUTOLOAD_ENABLED",
        "Autoload agent memory",
        "agent_loop",
        "true",
        "Inject relevant stored memories at the start of a run.",
    ),
)

_GOVERNANCE: tuple[ControlSpec, ...] = (
    _toggle(
        "GOVERNANCE_ENABLED",
        "Governance layer",
        "governance",
        "true",
        "Evaluate and audit agent actions. Behaviour-neutral on its own — the "
        "policy file ships in observe mode; enforcement is a separate step.",
        live=True,
        risk=RISK_MEDIUM,
    ),
    ControlSpec(
        key="GOVERNANCE_SANDBOX_BACKEND",
        label="Sandbox backend",
        group="governance",
        kind=KIND_CHOICE,
        default="auto",
        help="Where sandboxed agent actions execute.",
        options=(
            ControlOption("auto", "Auto-probe", "Try Docker, then E2B, then local. The default."),
            ControlOption("docker", "Docker", "Pin to Docker. Needs a Docker socket."),
            ControlOption("e2b", "E2B", "Pin to E2B micro-VMs. Needs E2B_API_KEY."),
            ControlOption("local", "Local", "Run in-process. No isolation — development only."),
        ),
        live=True,
        risk=RISK_MEDIUM,
    ),
    _toggle(
        "GOVERNANCE_AUTO_APPROVE",
        "Auto-approve high-risk actions",
        "governance",
        "false",
        "Skip the human approval gate. Development only — every use is audited "
        "as resolved_by=auto-approve.",
        live=True,
        risk=RISK_HIGH,
    ),
    _number(
        "GOVERNANCE_MAX_SANDBOXES",
        "Max concurrent sandboxes",
        "governance",
        "8",
        "Backpressure ceiling when many agents run at once.",
        live=True,
        minimum=1,
        maximum=256,
    ),
    _number(
        "GOVERNANCE_APPROVAL_TTL_S",
        "Approval timeout (s)",
        "governance",
        "300",
        "How long an agent waits on a human approval before the request is denied.",
        live=True,
        minimum=10,
        maximum=86400,
    ),
    _number(
        "GOVERNANCE_AUDIT_CAPACITY",
        "Audit ring-buffer size",
        "governance",
        "2000",
        "How far the dashboard can page back through the in-memory audit trail. "
        "The durable record is the structured log line.",
        live=True,
        minimum=100,
        maximum=100000,
    ),
    _toggle(
        "GUARDRAILS_ENABLED",
        "Input/output guardrails",
        "governance",
        "true",
        "Screen agent inputs and outputs against the guardrail rules.",
        risk=RISK_MEDIUM,
    ),
    _toggle(
        "OUTPUT_FILTER_ENABLED",
        "Output filter",
        "governance",
        "true",
        "Redact and truncate model output before it leaves the process.",
    ),
    _toggle(
        "STRICT_OUTBOUND",
        "Strict outbound URL guard",
        "governance",
        "false",
        "Tighten the SSRF guard on agent-initiated fetches beyond the always-on "
        "private-address rejection.",
    ),
    _toggle(
        "E2B_ENABLED",
        "E2B sandboxing",
        "governance",
        "false",
        "Explicit opt-in for E2B micro-VM sandboxes — an API key alone no longer "
        "activates them, because the host↔sandbox↔repo data flow is still "
        "experimental. Also requires E2B_API_KEY.",
        requires=("E2B_API_KEY",),
    ),
    ControlSpec(
        key="AGENT_SANDBOX_MODE",
        label="Agent sandbox mode",
        group="governance",
        kind=KIND_CHOICE,
        default="",
        help="Alternate activation signal for sandboxed execution.",
        options=(
            ControlOption("", "Default", "Follow the sandbox backend setting above."),
            ControlOption("e2b", "E2B", "Force E2B micro-VMs. Needs E2B_API_KEY."),
        ),
        requires=("E2B_API_KEY",),
    ),
    _toggle(
        "ACTIVATION_REQUIRED",
        "Require activation",
        "governance",
        "true",
        "New users need an activation record before they can use the platform. "
        "Off for self-hosted single-operator installs.",
        risk=RISK_MEDIUM,
    ),
)

_PLATFORM_OPS: tuple[ControlSpec, ...] = (
    _toggle(
        "RENDER_OPS_ENABLED",
        "Render ops loop",
        "platform_ops",
        "true",
        "Poll Render for build failures, OOM kills, and restarts — the platform "
        "view this process cannot see from its own logs. Dormant without RENDER_API_KEY.",
        live=True,
        requires=("RENDER_API_KEY",),
    ),
    _toggle(
        "RENDER_MCP_ALLOW_WRITES",
        "Allow Render write operations",
        "platform_ops",
        "false",
        "Permit mutating Render tools (trigger deploy, update environment, "
        "create resources). Default deny — a loop should not change a live "
        "service because a flag was left on.",
        live=True,
        risk=RISK_HIGH,
        requires=("RENDER_API_KEY",),
    ),
    _number(
        "RENDER_OPS_INTERVAL_SECONDS",
        "Render ops interval (s)",
        "platform_ops",
        "600",
        "How often the ops loop polls the Render API.",
        live=True,
        minimum=60,
        maximum=86400,
    ),
    _number(
        "OPS_INCIDENT_THRESHOLD",
        "Incident threshold",
        "platform_ops",
        "4",
        "Repeats of one failure signature before an incident is filed. Higher is quieter.",
        live=True,
        minimum=1,
        maximum=100,
    ),
    _number(
        "OPS_INCIDENT_WINDOW_SECONDS",
        "Incident window (s)",
        "platform_ops",
        "1800",
        "Sliding window the threshold counts within.",
        live=True,
        minimum=60,
        maximum=86400,
    ),
    _number(
        "OPS_INCIDENT_COOLDOWN_SECONDS",
        "Incident cooldown (s)",
        "platform_ops",
        "21600",
        "How long one signature stays suppressed after it is filed.",
        live=True,
        minimum=60,
        maximum=604800,
    ),
    _number(
        "OPS_INCIDENT_MAX_PER_HOUR",
        "Max incidents per hour",
        "platform_ops",
        "3",
        "Anti-storm cap on filed incidents.",
        live=True,
        minimum=1,
        maximum=100,
    ),
    _number(
        "OPS_INCIDENT_LOOKBACK_MINUTES",
        "Incident log lookback (min)",
        "platform_ops",
        "20",
        "How far back Render logs are pulled when building incident evidence.",
        live=True,
        minimum=1,
        maximum=1440,
    ),
)

_INTEGRATIONS: tuple[ControlSpec, ...] = (
    _toggle(
        "RUN_TELEGRAM_BOT",
        "Telegram bot",
        "integrations",
        "true",
        "Run the Telegram control bot inside the web process. On by default, but "
        "it only starts when TELEGRAM_BOT_TOKEN is set — so an install with no "
        "token is already dormant.",
        requires=("TELEGRAM_BOT_TOKEN",),
    ),
    _toggle(
        "TELEGRAM_POLLER_DISABLED",
        "Disable Telegram polling",
        "integrations",
        "false",
        "Stop long-polling for updates — use when a webhook delivers them instead.",
    ),
    _toggle(
        "BOT_KEEPALIVE",
        "Bot keepalive",
        "integrations",
        "true",
        "Keep the bot task alive across transient network failures.",
    ),
    _toggle(
        "FREEBUFF_EMBEDDED",
        "FreeBuff embedded bot",
        "integrations",
        "false",
        "Host the FreeBuff bot in this process.",
    ),
    _toggle(
        "FREEBUFF_UNLIMITED",
        "FreeBuff unlimited quota",
        "integrations",
        "true",
        "Lift per-user quota on the FreeBuff surface.",
    ),
    _toggle(
        "SAM_VOICE_IN_PROCESS",
        "SAM voice worker",
        "integrations",
        "false",
        "Run the LiveKit realtime voice worker in this process.",
        requires=("LIVEKIT_API_KEY",),
    ),
    _toggle(
        "BROWSER_AUTOMATION_ENABLED",
        "Browser automation",
        "integrations",
        "false",
        "Let agents drive a real browser. Needs Playwright or a remote browser service.",
        risk=RISK_MEDIUM,
    ),
    ControlSpec(
        key="SEO_BROWSER_BACKEND",
        label="SEO crawler backend",
        group="integrations",
        kind=KIND_CHOICE,
        default="",
        help="Which browser the SEO crawler uses for pages that need JavaScript.",
        options=(
            ControlOption("", "Auto-detect", "Local Playwright when installed, else Browserbase."),
            ControlOption("local", "Local Playwright", "Local Chromium."),
            ControlOption("browserbase", "Browserbase", "Remote browser. Needs BROWSERBASE_API_KEY."),
        ),
        live=True,
    ),
    _toggle(
        "FREELLM_API_MODEL_CATALOG_ENABLED",
        "Publish model catalogue",
        "integrations",
        "true",
        "Mirror the model catalogue to the DB and serve GET /api/catalog/models. "
        "Advisory only — it never changes brain routing.",
        live=True,
    ),
    _toggle(
        "FREELLM_CATALOG_INCLUDE_ROUTER",
        "Include router providers in the catalogue",
        "integrations",
        "false",
        "Widen the published catalogue to cover LLM-router providers. That "
        "document is a contract other services read, so widening it is deliberate.",
        live=True,
    ),
)

_OBSERVABILITY: tuple[ControlSpec, ...] = (
    _toggle(
        "OTEL_ENABLED",
        "OpenTelemetry tracing",
        "observability",
        "false",
        "Emit OTel spans for requests and agent steps.",
    ),
    _toggle(
        "PROXY_DEFAULT_SYSTEM_PROMPT_ENABLED",
        "Inject default system prompt",
        "observability",
        "true",
        "Prepend the platform system prompt to proxy chat requests that omit one.",
    ),
    _toggle(
        "PROXY_INJECT_STREAM_USAGE",
        "Inject usage into streams",
        "observability",
        "true",
        "Append a usage chunk to streamed responses so clients can account for tokens.",
    ),
    _toggle(
        "PROXY_STRIP_THINK_TAGS",
        "Strip <think> tags",
        "observability",
        "false",
        "Remove reasoning blocks from proxy responses before they reach the client.",
    ),
)


CONTROLS: tuple[ControlSpec, ...] = (
    _AGENT_RUNTIME
    + _BRAIN_ROUTING
    + _AUTONOMY
    + _AGENT_LOOP
    + _GOVERNANCE
    + _PLATFORM_OPS
    + _INTEGRATIONS
    + _OBSERVABILITY
)
