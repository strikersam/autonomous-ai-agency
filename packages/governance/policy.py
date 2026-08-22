"""packages/governance/policy.py — the single place a governed action is judged.

Docker AI Governance's central claim is that controls "have to live at the
runtime layer where the agent actually executes, not as advisory rules layered
on top that a clever prompt can route around". This module is the judgement
half of that: one engine, one decision type, evaluated identically for every
control surface (tools, network, filesystem, credentials, shell, GitHub,
Docker, database, MCP, browser, memory, LLM providers). The *enforcement* half
lives in :mod:`packages.governance.enforcement`, which is the only caller that
may act on a decision.

Two properties are load-bearing, and both are tested:

**Baseline rules cannot be loosened by a group.** Docker's model layers
"team-specific rules on top of organization-wide guardrails that can't be
overridden". Here that is structural, not conventional: :meth:`PolicyEngine.evaluate`
consults ``baseline`` before any group and returns immediately on a baseline
DENY. A group cannot re-allow what the baseline denied because a group's
allow-list is never consulted on that path.

**An explicit allow-list is default-deny inside its own surface.** If a group
declares ``tools.allow`` at all, a tool absent from it is denied — otherwise an
allow-list would be decoration. A group that declares no allow-list is
unrestricted for that surface, which is what keeps existing agents working
unchanged.

Mode
----
``mode: observe`` (the default) evaluates every rule and records what *would*
have been blocked without changing behaviour; ``mode: enforce`` acts on the
verdict. Observe-first is required by this repo's Golden Rule — no user-visible
behaviour may change unless explicitly requested — and it is also the only
honest way to turn on a policy engine in a system with 34 live autonomous
loops: you cannot know a rule is correct until you have seen what it would
have caught. :meth:`PolicyDecision.effective` is the only thing enforcement
reads, so a caller cannot accidentally enforce in observe mode.

Failure behaviour
-----------------
A malformed or missing policy file falls back to the embedded
:data:`DEFAULT_POLICY` and logs an error — it does not deny everything. This
is a deliberate, documented trade-off: this engine sits in the request path of
a platform whose production deployment auto-restarts on failure, and a policy
typo that hard-denies every tool call would take the agency down while looking
like a security feature. The embedded default is a real policy with real
baseline denies, not an allow-all, so the fallback still refuses the actions
that are never legitimate. See ``docs/governance/README.md``.
"""
from __future__ import annotations

import fnmatch
import ipaddress
import logging
import posixpath
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

log = logging.getLogger("governance.policy")


class Surface(str, Enum):
    """A control surface — the kind of thing being governed.

    Mirrors Docker AI Governance's four surfaces (network, filesystem,
    credentials, MCP tools) and extends them with the surfaces this platform
    actually exposes to agents and that the audit therefore has to cover.
    """

    TOOL = "tool"
    NETWORK = "network"
    FILESYSTEM = "filesystem"
    CREDENTIAL = "credential"
    SHELL = "shell"
    GITHUB = "github"
    DOCKER = "docker"
    DATABASE = "database"
    MCP = "mcp"
    BROWSER = "browser"
    MEMORY = "memory"
    LLM_PROVIDER = "llm_provider"
    # Which execution runtime an agent may dispatch work to. Distinct from
    # DOCKER (which governs sandbox lifecycle): this governs the *choice of
    # executor* — a research agent has no business dispatching to a runtime
    # whose whole purpose is editing and committing code.
    RUNTIME = "runtime"
    # Spawning a child agent. Governs recursive delegation — the surface the
    # max_depth budget ceiling is charged against, so a runaway spawn chain is
    # a governance verdict, not only a hard-coded cap.
    AGENT = "agent"


class Decision(str, Enum):
    """The verdict for one governed action."""

    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    DENY = "deny"


class Mode(str, Enum):
    """Whether verdicts are acted on or only recorded."""

    OBSERVE = "observe"
    ENFORCE = "enforce"


@dataclass(frozen=True)
class PolicyDecision:
    """A verdict, plus everything needed to explain and audit it.

    ``rule_id`` is what makes a decision reviewable after the fact: an audit
    row that says "denied" is an incident, but one that says "denied by
    ``baseline.tool.deny[shell_exec_rm_rf]``" is a policy question with an
    owner.
    """

    decision: Decision
    surface: Surface
    action: str
    reason: str
    rule_id: str
    mode: Mode = Mode.OBSERVE
    group: str = "default"

    @property
    def effective(self) -> Decision:
        """The decision enforcement must act on.

        In observe mode this is always :attr:`Decision.ALLOW` — the verdict is
        still recorded on ``decision`` for the audit trail and the dashboard,
        but nothing is blocked. Enforcement reads *only* this property, so
        observe mode cannot be bypassed by a caller that forgets to check the
        mode.
        """
        if self.mode is Mode.ENFORCE:
            return self.decision
        return Decision.ALLOW

    @property
    def would_block(self) -> bool:
        """True when this decision blocks (or would block, in observe mode).

        This is the metric that tells an operator whether ``enforce`` is safe
        to turn on yet: a week of ``would_block`` counts at zero for a rule
        means the rule is safe to enforce.
        """
        return self.decision in (Decision.DENY, Decision.REQUIRE_APPROVAL)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "effective": self.effective.value,
            "surface": self.surface.value,
            "action": self.action,
            "reason": self.reason,
            "rule_id": self.rule_id,
            "mode": self.mode.value,
            "group": self.group,
        }


# ── Embedded default policy ──────────────────────────────────────────────────
# The fallback when config/agent_policy.yaml is missing or malformed, and the
# starting point operators edit. Every baseline entry below denies or gates an
# action that has no legitimate agent use in this repo, so the fallback is a
# real policy rather than an allow-all.
DEFAULT_POLICY: dict[str, Any] = {
    "version": 1,
    "mode": "observe",
    "baseline": {
        "tool": {
            # Destructive or self-modifying actions an autonomous loop should
            # never take unattended. `agent/autonomy_gate.py` already blocks
            # direct writes to master and agent-initiated merges; these entries
            # make the same intent visible to (and auditable by) the policy
            # engine rather than living only in that one module.
            "require_approval": [
                "github_merge_pr",
                "github_delete_*",
                "docker_*",
                "deploy_*",
            ],
        },
        "filesystem": {
            # Secrets and key material. Reading these is how a prompt-injected
            # agent turns file access into credential theft.
            "deny": [
                ".env",
                ".env.*",
                "**/.env",
                "**/.git/config",
                "**/id_rsa*",
                "**/id_ed25519*",
                "**/.ssh/**",
                "**/*.pem",
                "**/credentials.json",
            ],
        },
        "network": {
            # Cloud metadata endpoints — the classic SSRF-to-credentials
            # pivot. agent/web_reach.py already rejects private and
            # link-local targets by resolved IP; this is defence in depth at
            # the name level for callers that do not go through it.
            "deny": [
                "169.254.169.254",
                "metadata.google.internal",
                "metadata.goog",
                "*.internal",
                "localhost",
                "127.0.0.0/8",
                "169.254.0.0/16",
                "10.0.0.0/8",
                "172.16.0.0/12",
                "192.168.0.0/16",
            ],
        },
        "shell": {
            "deny": [
                "rm -rf /*",
                "*mkfs*",
                "*:(){ :|:& };:*",
                "*/etc/shadow*",
                "*curl*|*sh*",
                "*wget*|*sh*",
            ],
        },
    },
    "groups": {
        # The least-privileged group. Unnamed and unassigned agents land here.
        # It declares no allow-lists, so it restricts nothing beyond the
        # baseline — this is what preserves today's behaviour on first deploy.
        "default": {
            "limits": {
                "max_tool_calls": 200,
                "max_cost_usd": 5.0,
                "max_duration_s": 1800,
                "max_depth": 5,
                "max_retries": 10,
                # Per-tool session caps (max_calls_<tool_name>).
                # Mirrors Claude Code's per-session WebSearch cap (v2.1.212).
                "max_calls_web_search": 200,
                "max_calls_fetch_page": 200,
                "max_calls_fetch_url": 200,
                "max_calls_fetch_rss": 100,
            },
            "sandbox_profile": "development",
        },
    },
    "assignments": [],
}


def _as_list(value: Any) -> list[str]:
    """Coerce a YAML scalar-or-list field into a list of strings.

    Operators write ``deny: "*.internal"`` as often as they write a list; a
    policy file that silently ignores the scalar form would be a policy that
    silently does not apply.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v is not None]
    return []


def _normalise_path(raw: str) -> str:
    """Normalise a filesystem target for matching.

    Collapses ``..`` segments and leading ``./`` so ``a/../.env`` cannot slip
    past a rule written for ``.env``. Absolute paths keep their leading slash
    so an absolute rule and a relative rule stay distinguishable.
    """
    text = str(raw or "").strip().replace("\\", "/")
    if not text:
        return ""
    absolute = text.startswith("/")
    collapsed = posixpath.normpath(text)
    if collapsed == ".":
        return ""
    if absolute and not collapsed.startswith("/"):
        collapsed = "/" + collapsed
    return collapsed


def _path_matches(path: str, pattern: str) -> bool:
    """Match a normalised path against a glob rule.

    ``PurePosixPath.match`` handles ``**`` recursion the way operators expect
    from .gitignore-style rules; plain ``fnmatch`` is kept as a fallback so a
    rule like ``.env.*`` still matches a bare filename. Both are tried because
    each covers a case the other misses, and a missed match here is a policy
    that does not apply.
    """
    if not path or not pattern:
        return False
    if fnmatch.fnmatch(path, pattern):
        return True
    try:
        if PurePosixPath(path).match(pattern):
            return True
    except (ValueError, TypeError):  # pragma: no cover - defensive
        pass
    # A rule naming a directory covers everything beneath it.
    return path.startswith(pattern.rstrip("/") + "/") if "/" in pattern else False


def _host_matches(host: str, pattern: str) -> bool:
    """Match a hostname or IP against a domain glob or CIDR rule.

    CIDR patterns only ever match literal IPs — a hostname is *not* resolved
    here. Resolution belongs to ``agent/web_reach.py::unsafe_target_reason``,
    which already does it correctly against every resolved address including
    redirect hops; doing it a second time here would add a second, weaker
    implementation of the same check and a DNS call to every policy
    evaluation.
    """
    host = (host or "").strip().lower().rstrip(".")
    pattern = (pattern or "").strip().lower().rstrip(".")
    if not host or not pattern:
        return False
    if "/" in pattern:
        try:
            network = ipaddress.ip_network(pattern, strict=False)
        except ValueError:
            return False
        try:
            return ipaddress.ip_address(host) in network
        except ValueError:
            return False
    if fnmatch.fnmatch(host, pattern):
        return True
    # `example.com` covers `api.example.com`; `*.example.com` does not cover
    # the apex, which is why both forms exist.
    return host.endswith("." + pattern)


def _action_matches(action: str, pattern: str, surface: Surface) -> bool:
    """Dispatch to the matcher appropriate for *surface*."""
    if surface is Surface.FILESYSTEM:
        return _path_matches(_normalise_path(action), pattern)
    if surface is Surface.NETWORK:
        return _host_matches(action, pattern)
    return fnmatch.fnmatch((action or "").strip().lower(), pattern.strip().lower())


@dataclass
class GroupPolicy:
    """The resolved rules for one policy group, after ``extends`` flattening."""

    name: str
    rules: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    limits: dict[str, float] = field(default_factory=dict)
    sandbox_profile: str = "development"

    def surface_rules(self, surface: Surface) -> dict[str, list[str]]:
        return self.rules.get(surface.value, {})


class PolicyEngine:
    """Evaluates governed actions against a layered policy document.

    Thread-safe for concurrent reads: the compiled policy is replaced
    atomically on reload, never mutated in place, so an in-flight evaluation
    always sees one coherent policy version rather than a half-applied edit.
    """

    def __init__(self, document: dict[str, Any] | None = None) -> None:
        self._lock = threading.Lock()
        self._source: str = "embedded-default"
        self._compile(document or DEFAULT_POLICY)

    # ── Loading ──────────────────────────────────────────────────────────

    @classmethod
    def from_file(cls, path: str | Path) -> "PolicyEngine":
        """Load a policy document from YAML, falling back to the default.

        Never raises: see the module docstring for why a bad policy file
        degrades to the embedded default rather than denying everything.
        """
        engine = cls()
        engine.reload(path)
        return engine

    def reload(self, path: str | Path) -> bool:
        """Reload from *path*. Returns True when the file was applied."""
        p = Path(path)
        try:
            import yaml  # imported lazily: policy is optional configuration

            with p.open("r", encoding="utf-8") as fh:
                document = yaml.safe_load(fh) or {}
            if not isinstance(document, dict):
                raise ValueError(f"policy root must be a mapping, got {type(document).__name__}")
            self._compile(document)
            with self._lock:
                self._source = str(p)
            log.info("Governance policy loaded from %s (mode=%s)", p, self.mode.value)
            return True
        except FileNotFoundError:
            log.info("No governance policy at %s; using embedded default", p)
        except Exception as exc:  # noqa: BLE001 - a bad policy must not crash boot
            log.error(
                "Governance policy at %s is invalid (%s); falling back to the "
                "embedded default policy. Fix the file — the fallback is more "
                "permissive than your intent.",
                p, exc,
            )
        self._compile(DEFAULT_POLICY)
        return False

    def _compile(self, document: dict[str, Any]) -> None:
        """Flatten ``extends`` chains and index rules for O(1) surface lookup."""
        raw_mode = str(document.get("mode", "observe")).strip().lower()
        mode = Mode.ENFORCE if raw_mode == "enforce" else Mode.OBSERVE
        if raw_mode not in (Mode.OBSERVE.value, Mode.ENFORCE.value):
            log.warning("Unknown governance mode %r; defaulting to observe", raw_mode)

        baseline = self._compile_rules(document.get("baseline") or {})
        raw_groups = document.get("groups") or {}
        groups: dict[str, GroupPolicy] = {}
        for name in raw_groups:
            groups[name] = self._resolve_group(name, raw_groups, seen=set())
        if "default" not in groups:
            groups["default"] = self._resolve_group(
                "default", DEFAULT_POLICY["groups"], seen=set()
            )

        assignments = []
        for entry in document.get("assignments") or []:
            if isinstance(entry, dict) and entry.get("group"):
                assignments.append(
                    (str(entry.get("match") or entry.get("agent") or "*"), str(entry["group"]))
                )

        with self._lock:
            self._mode = mode
            self._baseline = baseline
            self._groups = groups
            self._assignments = assignments
            self._version = int(document.get("version", 1) or 1)

    def _resolve_group(
        self, name: str, raw_groups: dict[str, Any], seen: set[str]
    ) -> GroupPolicy:
        """Flatten one group's ``extends`` chain into concrete rules.

        A cycle (``a extends b extends a``) resolves to what was gathered
        before the loop closed rather than recursing forever — a config typo
        must not hang the process.
        """
        if name in seen:
            log.warning("Cyclic 'extends' in policy group %r; stopping here", name)
            return GroupPolicy(name=name)
        seen.add(name)

        raw = raw_groups.get(name) or {}
        if not isinstance(raw, dict):
            return GroupPolicy(name=name)

        parent_name = raw.get("extends")
        if parent_name and parent_name in raw_groups:
            parent = self._resolve_group(str(parent_name), raw_groups, seen)
            rules = {s: {k: list(v) for k, v in r.items()} for s, r in parent.rules.items()}
            limits = dict(parent.limits)
            sandbox_profile = parent.sandbox_profile
        else:
            rules, limits, sandbox_profile = {}, {}, "development"

        for surface, surface_rules in self._compile_rules(raw).items():
            merged = rules.setdefault(surface, {})
            for effect, patterns in surface_rules.items():
                # Child patterns append to the parent's rather than replacing
                # them: `extends` is meant to tighten, and a child that
                # replaced a parent's deny-list would be a silent loosening.
                merged[effect] = merged.get(effect, []) + patterns

        for key, value in (raw.get("limits") or {}).items():
            try:
                limits[str(key)] = float(value)
            except (TypeError, ValueError):
                log.warning("Non-numeric limit %s=%r in group %r; ignored", key, value, name)
        if raw.get("sandbox_profile"):
            sandbox_profile = str(raw["sandbox_profile"])

        return GroupPolicy(name=name, rules=rules, limits=limits, sandbox_profile=sandbox_profile)

    @staticmethod
    def _compile_rules(section: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
        """Extract ``{surface: {effect: [patterns]}}`` from a policy section.

        A *declared but empty* list is preserved rather than dropped, and the
        distinction is load-bearing. ``write: []`` means "this group may not
        write at all"; omitting ``write`` entirely means "unrestricted". If an
        empty list were discarded as falsy, the strictest rule an operator can
        express would silently become the most permissive one — a policy that
        reads as deny-all and behaves as allow-all.
        """
        compiled: dict[str, dict[str, list[str]]] = {}
        for surface in Surface:
            raw = section.get(surface.value)
            if not isinstance(raw, dict):
                continue
            effects: dict[str, list[str]] = {}
            for effect in ("deny", "require_approval", "allow", "read", "write"):
                if effect in raw:
                    effects[effect] = _as_list(raw.get(effect))
            if effects:
                compiled[surface.value] = effects
        return compiled

    # ── Introspection ────────────────────────────────────────────────────

    @property
    def mode(self) -> Mode:
        with self._lock:
            return self._mode

    @property
    def source(self) -> str:
        with self._lock:
            return self._source

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    def group_names(self) -> list[str]:
        with self._lock:
            return sorted(self._groups)

    def group_for(self, identity: Any) -> GroupPolicy:
        """Resolve which group governs *identity*.

        Precedence: the identity's own ``policy_group`` when such a group
        exists, then the first matching ``assignments`` rule, then
        ``default``. Explicit beats inferred, and something always matches.
        """
        with self._lock:
            groups = self._groups
            assignments = list(self._assignments)

        requested = getattr(identity, "policy_group", None)
        if requested and requested in groups:
            return groups[requested]

        agent_id = str(getattr(identity, "agent_id", "") or "")
        for pattern, group_name in assignments:
            if fnmatch.fnmatch(agent_id, pattern) and group_name in groups:
                return groups[group_name]
        return groups["default"]

    def limits_for(self, identity: Any) -> dict[str, float]:
        return dict(self.group_for(identity).limits)

    def sandbox_profile_for(self, identity: Any) -> str:
        return self.group_for(identity).sandbox_profile

    # ── Evaluation ───────────────────────────────────────────────────────

    def evaluate(
        self,
        surface: Surface,
        action: str,
        identity: Any = None,
        context: dict[str, Any] | None = None,
    ) -> PolicyDecision:
        """Judge one action on one surface.

        Order is the whole security model, and it is why baseline rules cannot
        be loosened by a group:

          1. ``baseline.deny``            → DENY, immediately.
          2. ``baseline.require_approval``→ REQUIRE_APPROVAL, immediately.
          3. ``group.deny``               → DENY.
          4. ``group.require_approval``   → REQUIRE_APPROVAL.
          5. ``group.allow`` present but unmatched → DENY (default-deny inside
             a declared allow-list).
          6. otherwise                    → ALLOW.

        Steps 1 and 2 return before any group rule is read, so no group can
        re-allow a baseline-denied action.
        """
        group = self.group_for(identity)
        mode = self.mode

        def verdict(decision: Decision, reason: str, rule_id: str) -> PolicyDecision:
            return PolicyDecision(
                decision=decision, surface=surface, action=action,
                reason=reason, rule_id=rule_id, mode=mode, group=group.name,
            )

        with self._lock:
            baseline_rules = self._baseline.get(surface.value, {})

        hit = self._first_match(action, baseline_rules.get("deny", []), surface)
        if hit is not None:
            return verdict(
                Decision.DENY,
                f"blocked by organization baseline rule {hit!r} — this rule cannot "
                f"be overridden by a policy group",
                f"baseline.{surface.value}.deny[{hit}]",
            )

        hit = self._first_match(action, baseline_rules.get("require_approval", []), surface)
        if hit is not None:
            return verdict(
                Decision.REQUIRE_APPROVAL,
                f"organization baseline requires human approval (rule {hit!r})",
                f"baseline.{surface.value}.require_approval[{hit}]",
            )

        group_rules = group.surface_rules(surface)

        hit = self._first_match(action, group_rules.get("deny", []), surface)
        if hit is not None:
            return verdict(
                Decision.DENY,
                f"denied by policy group {group.name!r} rule {hit!r}",
                f"group.{group.name}.{surface.value}.deny[{hit}]",
            )

        hit = self._first_match(action, group_rules.get("require_approval", []), surface)
        if hit is not None:
            return verdict(
                Decision.REQUIRE_APPROVAL,
                f"policy group {group.name!r} requires approval (rule {hit!r})",
                f"group.{group.name}.{surface.value}.require_approval[{hit}]",
            )

        allow_patterns = self._allow_patterns(group_rules, surface, context)
        if allow_patterns is not None:
            hit = self._first_match(action, allow_patterns, surface)
            if hit is None:
                return verdict(
                    Decision.DENY,
                    f"policy group {group.name!r} declares an allow-list for "
                    f"{surface.value} and {action!r} is not on it",
                    f"group.{group.name}.{surface.value}.allow[default-deny]",
                )
            return verdict(
                Decision.ALLOW,
                f"allowed by policy group {group.name!r} rule {hit!r}",
                f"group.{group.name}.{surface.value}.allow[{hit}]",
            )

        return verdict(
            Decision.ALLOW,
            f"no rule matches {action!r} on surface {surface.value}",
            f"group.{group.name}.{surface.value}.default-allow",
        )

    @staticmethod
    def _allow_patterns(
        group_rules: dict[str, list[str]],
        surface: Surface,
        context: dict[str, Any] | None,
    ) -> list[str] | None:
        """Return the applicable allow-list, or ``None`` when none is declared.

        The ``None`` vs ``[]`` distinction is the whole contract: ``None``
        means the group declared no allow-list and the surface is
        unrestricted; ``[]`` means the group declared an empty one and
        *nothing* is permitted. Returning a bare list would collapse those
        two opposite meanings into one.

        Filesystem is the one surface where the *mode* of access selects the
        list: a group may grant broad ``read`` and narrow ``write``.
        ``context={"mode": "write"}`` selects ``write``; anything else selects
        ``read``. Both fall back to a plain ``allow`` list so simple policies
        need not distinguish.
        """
        if surface is not Surface.FILESYSTEM:
            return group_rules.get("allow")
        access = str((context or {}).get("mode", "read")).lower()
        key = "write" if access == "write" else "read"
        if key in group_rules:
            return group_rules[key]
        return group_rules.get("allow")

    @staticmethod
    def _first_match(action: str, patterns: Iterable[str], surface: Surface) -> str | None:
        """Return the first pattern matching *action*, or None.

        Returns the pattern itself rather than a bool so the decision can name
        the exact rule that fired — an unexplainable denial is an outage, not
        a control.
        """
        for pattern in patterns:
            try:
                if _action_matches(action, pattern, surface):
                    return pattern
            except Exception as exc:  # noqa: BLE001 - one bad pattern must not void the rest
                log.warning("Policy pattern %r failed to evaluate: %s", pattern, exc)
        return None

    def describe(self) -> dict[str, Any]:
        """Return the effective policy for the dashboard and audit review.

        Safe to expose to an authenticated admin: a policy document names
        tools, paths, and domains — it never contains a credential value. The
        ``credential`` surface lists secret *names* an agent may see, not
        their values.
        """
        with self._lock:
            return {
                "version": self._version,
                "mode": self._mode.value,
                "source": self._source,
                "baseline": {s: dict(r) for s, r in self._baseline.items()},
                "groups": {
                    name: {
                        "rules": {s: dict(r) for s, r in g.rules.items()},
                        "limits": dict(g.limits),
                        "sandbox_profile": g.sandbox_profile,
                    }
                    for name, g in self._groups.items()
                },
                "assignments": [
                    {"match": m, "group": g} for m, g in self._assignments
                ],
            }


_ENGINE: PolicyEngine | None = None
_ENGINE_LOCK = threading.Lock()


def get_policy_engine() -> PolicyEngine:
    """Return the process-wide policy engine, loading it on first use.

    One engine per process: policy must be evaluated identically everywhere,
    and a second instance would be a second source of truth.
    """
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            from packages.config import settings

            _ENGINE = PolicyEngine.from_file(settings.governance_policy_path)
        return _ENGINE


def reset_policy_engine(engine: PolicyEngine | None = None) -> None:
    """Replace the process-wide engine. Tests only."""
    global _ENGINE
    with _ENGINE_LOCK:
        _ENGINE = engine
