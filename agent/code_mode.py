from __future__ import annotations

"""Code Mode for the agent tool loop — many tool calls in one model turn.

Adapted from Cloudflare's ``@cloudflare/codemode`` (MIT): instead of picking one
tool per LLM call and copying every intermediate result back through the
prompt, the model writes a short program that calls several tools, filters
their output, and returns only what the next decision needs.

Cloudflare runs model-written JavaScript in a V8 isolate. This backend has no
isolate (Render free tier, 512 MB), and ``exec`` with stripped builtins is not a
security boundary in Python. So the program is never compiled or executed:
``ast.parse`` reads it and :class:`_Interpreter` walks the tree, evaluating a
small, explicit subset of Python. Anything outside that subset — imports,
``def``/``lambda``/``class``, ``while``, ``with``, any name or attribute
starting with ``_`` — is rejected before the first node runs.

The only route out of the interpreter is ``tools.<name>(...)``, and every such
call goes through the caller's ``call_tool`` — in the agent loop that is
``AgentRunner._run_tool``, so governance, audit and MCP routing apply to each
inner call exactly as they would to a direct one. Only read-only tools that the
current tool prompt advertises are callable (rule 19): Code Mode never widens
what the agent can do, it only cuts round trips.
"""

import ast
import asyncio
import json
import logging
import operator
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

log = logging.getLogger("qwen-proxy")

ToolCaller = Callable[[str, dict[str, Any]], Awaitable[Any]]

# Inspection tools only. Anything that writes, pushes, comments, spawns or
# delegates stays a direct, one-per-turn call the model must choose explicitly.
READ_ONLY_TOOLS: frozenset[str] = frozenset({
    "get_overview", "get_context", "get_risk", "get_why",
    "file_index", "head_file", "read_file", "list_files", "search_code",
    "read_tool_output", "get_current_time",
    "fetch_url", "youtube_transcript", "web_search", "fetch_rss",
    "code_trace", "code_search", "code_impact",
    "github_get_issue", "github_list_repos", "github_list_branches",
    "github_read_repo_file", "git_status", "git_diff",
})

TOOLS_PLACEHOLDER = "<<run_code_tools>>"
_SIGNATURE_RE = re.compile(r"^- ([a-z][a-z0-9_]*)\(([^)]*)\)", re.MULTILINE)
_SPEC_WIDTH_RE = re.compile(r"\d+")
# json.dumps of a result is built in full before truncation; aliasing can make it huge.
_RENDER_CAP = 1_000_000


class CodeModeError(Exception):
    """The program is outside the supported subset or broke a limit."""


@dataclass(frozen=True)
class CodeModeLimits:
    """Hard ceilings for one ``run_code`` program."""

    max_tool_calls: int = 20
    max_ops: int = 50_000
    max_len: int = 200_000
    max_total_alloc: int = 5_000_000
    max_int_bits: int = 4096
    max_range: int = 10_000
    timeout_s: float = 90.0
    max_result_chars: int = 6000


@dataclass
class CodeModeResult:
    """What one program produced: the value, the calls it made, or the error."""

    ok: bool
    result: Any = None
    calls: list[str] = field(default_factory=list)
    printed: list[str] = field(default_factory=list)
    error: str | None = None

    def render(self, max_chars: int) -> tuple[str, bool]:
        """Serialise for the observation list; returns ``(text, truncated)``."""
        body: dict[str, Any] = {"ok": self.ok, "tool_calls": self.calls}
        if self.ok and _deep_size(self.result, _RENDER_CAP) > _RENDER_CAP:
            body["ok"] = False
            body["error"] = "result too large to return — slice, filter or count it first"
        elif self.ok:
            body["result"] = self.result
        else:
            body["error"] = self.error
        if self.printed:
            body["printed"] = self.printed[-20:]
        text = json.dumps(body, default=str, ensure_ascii=False)
        if len(text) <= max_chars:
            return text, False
        return text[:max_chars] + " …[truncated — return less, e.g. slice or filter]", True


def tool_signatures(prompt_text: str) -> dict[str, list[str]]:
    """Map each ``- name(params)`` line of a tool prompt to its parameter names."""
    signatures: dict[str, list[str]] = {}
    for name, raw in _SIGNATURE_RE.findall(prompt_text):
        params = []
        for part in raw.split(","):
            param = part.split("=", 1)[0].strip()
            if param.isidentifier():
                params.append(param)
        signatures.setdefault(name, params)
    return signatures


def callable_tools(prompt_text: str) -> dict[str, list[str]]:
    """Read-only tools the prompt advertises, with their parameter names."""
    return {
        name: params
        for name, params in tool_signatures(prompt_text).items()
        if name in READ_ONLY_TOOLS
    }


def code_mode_enabled() -> bool:
    """Read AGENT_CODE_MODE_ENABLED at call time so a Platform Controls override is live."""
    try:
        from packages.config import settings

        return settings.agent_code_mode_enabled
    except Exception as exc:  # noqa: BLE001 - an unreadable setting keeps the safe default (off)
        log.debug("AGENT_CODE_MODE_ENABLED unreadable, code mode off: %s", exc)
        return False


def holdout_percent() -> int:
    """Share of steps (0-100) kept without run_code as the phase-2 comparison group."""
    try:
        from packages.config import settings

        return max(0, min(100, int(settings.agent_code_mode_holdout_percent)))
    except Exception as exc:  # noqa: BLE001 - an unreadable setting means no holdout
        log.debug("AGENT_CODE_MODE_HOLDOUT_PERCENT unreadable, no holdout: %s", exc)
        return 0


def code_mode_active() -> bool:
    """On for this step: switched on, and the step is not in the measurement holdout."""
    from agent.code_mode_metrics import ARM_HOLDOUT, current_arm

    return code_mode_enabled() and current_arm() != ARM_HOLDOUT


_STMT_NODES = (
    ast.Module, ast.Expr, ast.Assign, ast.AugAssign, ast.If, ast.For,
    ast.Break, ast.Continue, ast.Pass,
)
_EXPR_NODES = (
    ast.Constant, ast.Name, ast.Load, ast.Store, ast.List, ast.Tuple, ast.Set,
    ast.Dict, ast.BinOp, ast.UnaryOp, ast.BoolOp, ast.Compare, ast.IfExp,
    ast.Subscript, ast.Slice, ast.Call, ast.keyword, ast.Attribute,
    ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.comprehension,
    ast.JoinedStr, ast.FormattedValue,
)
_OP_NODES = (
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.Not, ast.USub, ast.UAdd, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.In, ast.NotIn, ast.Is, ast.IsNot,
)
_ALLOWED_NODES = _STMT_NODES + _EXPR_NODES + _OP_NODES


def validate(source: str) -> ast.Module:
    """Parse *source* and reject anything outside the supported subset."""
    try:
        tree = ast.parse(source, mode="exec")
    except SyntaxError as exc:
        raise CodeModeError(f"syntax error on line {exc.lineno}: {exc.msg}") from None
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            raise CodeModeError(
                f"line {getattr(node, 'lineno', '?')}: {type(node).__name__} is not supported in run_code"
            )
        name = _node_identifier(node)
        if name is not None and name.startswith("_"):
            raise CodeModeError(f"line {getattr(node, 'lineno', '?')}: names starting with '_' are not allowed")
        if isinstance(node, ast.Constant) and not isinstance(node.value, (str, int, float, bool, type(None))):
            raise CodeModeError(f"line {node.lineno}: {type(node.value).__name__} literals are not supported")
        if isinstance(node, ast.comprehension) and node.is_async:
            raise CodeModeError("async comprehensions are not supported")
    return tree


def _node_identifier(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.keyword):
        return node.arg
    return None


class _Break(Exception):
    pass


class _Continue(Exception):
    pass


_BIN_OPS: dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_CMP_OPS: dict[type, Callable[[Any, Any], Any]] = {
    ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt,
    ast.LtE: operator.le, ast.Gt: operator.gt, ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b, ast.NotIn: lambda a, b: a not in b,
    ast.Is: operator.is_, ast.IsNot: operator.is_not,
}
_SAFE_METHODS: dict[type, frozenset[str]] = {
    str: frozenset({
        "lower", "upper", "strip", "lstrip", "rstrip", "split", "rsplit",
        "splitlines", "startswith", "endswith", "replace", "join", "find",
        "rfind", "count", "isdigit", "isalpha", "isspace", "title",
    }),
    list: frozenset({"append", "extend", "index", "count", "pop", "insert", "reverse", "sort"}),
    dict: frozenset({"get", "keys", "values", "items", "update", "pop", "setdefault"}),
    tuple: frozenset({"index", "count"}),
    set: frozenset({"add", "union", "intersection", "difference"}),
}


class _Interpreter:
    """Tree-walking evaluator for the subset accepted by :func:`validate`."""

    def __init__(
        self,
        call_tool: ToolCaller,
        tools: dict[str, list[str]],
        limits: CodeModeLimits,
    ) -> None:
        self._call_tool = call_tool
        self._tools = tools
        self._limits = limits
        self._ops = 0
        self._yielded_at = 0
        self._alloc = 0
        self._deadline = time.monotonic() + limits.timeout_s
        self.env: dict[str, Any] = {}
        self.calls: list[str] = []
        self.printed: list[str] = []
        self.last_value: Any = None

    # ── statements ────────────────────────────────────────────────────────
    async def run(self, tree: ast.Module) -> Any:
        await self._block(tree.body)
        return self.env["result"] if "result" in self.env else self.last_value

    async def _block(self, body: list[ast.stmt]) -> None:
        for stmt in body:
            await self._stmt(stmt)

    async def _stmt(self, node: ast.stmt) -> None:
        self._tick(node)
        await self._maybe_yield()
        if isinstance(node, ast.Expr):
            self.last_value = await self._eval(node.value)
        elif isinstance(node, ast.Assign):
            value = await self._eval(node.value)
            for target in node.targets:
                await self._assign(target, value)
        elif isinstance(node, ast.AugAssign):
            current = await self._eval(_as_load(node.target))
            value = self._binop(node.op, current, await self._eval(node.value), node)
            await self._assign(node.target, value)
        elif isinstance(node, ast.If):
            await self._block(node.body if await self._eval(node.test) else node.orelse)
        elif isinstance(node, ast.For):
            await self._for(node)
        elif isinstance(node, ast.Break):
            raise _Break()
        elif isinstance(node, ast.Continue):
            raise _Continue()

    async def _for(self, node: ast.For) -> None:
        broke = False
        for item in list(await self._eval(node.iter)):
            self._tick(node)
            await self._maybe_yield()
            await self._assign(node.target, item)
            try:
                await self._block(node.body)
            except _Break:
                broke = True
                break
            except _Continue:
                continue
        if not broke:
            await self._block(node.orelse)

    async def _assign(self, target: ast.expr, value: Any) -> None:
        if isinstance(target, ast.Name):
            if target.id == "tools":
                raise CodeModeError(f"line {target.lineno}: 'tools' cannot be reassigned")
            self.env[target.id] = value
        elif isinstance(target, (ast.Tuple, ast.List)):
            values = list(value)
            if len(values) != len(target.elts):
                raise CodeModeError(f"line {target.lineno}: cannot unpack {len(values)} values into {len(target.elts)}")
            for elt, item in zip(target.elts, values):
                await self._assign(elt, item)
        elif isinstance(target, ast.Subscript):
            container = await self._eval(target.value)
            if not isinstance(container, (list, dict)):
                raise CodeModeError(f"line {target.lineno}: only list and dict items can be assigned")
            container[await self._eval(target.slice)] = value
        else:
            raise CodeModeError(f"line {target.lineno}: unsupported assignment target")

    # ── expressions ───────────────────────────────────────────────────────
    async def _eval(self, node: ast.expr) -> Any:
        self._tick(node)
        handler = getattr(self, f"_e_{type(node).__name__}", None)
        if handler is None:
            raise CodeModeError(f"line {node.lineno}: {type(node).__name__} is not supported here")
        value = await handler(node)
        if not isinstance(node, (ast.Name, ast.Constant)):
            self._account(value, node)
        return self._check_size(value, node)

    async def _e_Constant(self, node: ast.Constant) -> Any:
        return node.value

    async def _e_Name(self, node: ast.Name) -> Any:
        if node.id in self.env:
            return self.env[node.id]
        if node.id in _BUILTINS:
            raise CodeModeError(f"line {node.lineno}: builtin '{node.id}' can only be called")
        raise CodeModeError(f"line {node.lineno}: name '{node.id}' is not defined")

    async def _e_List(self, node: ast.List) -> list[Any]:
        return [await self._eval(e) for e in node.elts]

    async def _e_Tuple(self, node: ast.Tuple) -> tuple[Any, ...]:
        return tuple([await self._eval(e) for e in node.elts])

    async def _e_Set(self, node: ast.Set) -> set[Any]:
        return {await self._eval(e) for e in node.elts}

    async def _e_Dict(self, node: ast.Dict) -> dict[Any, Any]:
        if any(k is None for k in node.keys):
            raise CodeModeError(f"line {node.lineno}: '**' unpacking is not supported")
        return {await self._eval(k): await self._eval(v) for k, v in zip(node.keys, node.values)}  # type: ignore[arg-type]

    async def _e_BinOp(self, node: ast.BinOp) -> Any:
        return self._binop(node.op, await self._eval(node.left), await self._eval(node.right), node)

    async def _e_UnaryOp(self, node: ast.UnaryOp) -> Any:
        value = await self._eval(node.operand)
        if isinstance(node.op, ast.Not):
            return not value
        if isinstance(node.op, ast.USub):
            return -value
        return +value

    async def _e_BoolOp(self, node: ast.BoolOp) -> Any:
        value: Any = None
        for expr in node.values:
            value = await self._eval(expr)
            if isinstance(node.op, ast.And) and not value:
                return value
            if isinstance(node.op, ast.Or) and value:
                return value
        return value

    async def _e_Compare(self, node: ast.Compare) -> bool:
        left = await self._eval(node.left)
        for op, comparator in zip(node.ops, node.comparators):
            right = await self._eval(comparator)
            if isinstance(op, (ast.In, ast.NotIn)):
                if isinstance(right, (list, tuple)):
                    self._charge_work(right, node)
            elif isinstance(left, _CONTAINER_TYPES) or isinstance(right, _CONTAINER_TYPES):
                self._charge_work(left, node)
                self._charge_work(right, node)
            if not _CMP_OPS[type(op)](left, right):
                return False
            left = right
        return True

    async def _e_IfExp(self, node: ast.IfExp) -> Any:
        return await self._eval(node.body if await self._eval(node.test) else node.orelse)

    async def _e_Subscript(self, node: ast.Subscript) -> Any:
        container = await self._eval(node.value)
        key = await self._eval(node.slice)
        try:
            return container[key]
        except (KeyError, IndexError, TypeError) as exc:
            raise CodeModeError(f"line {node.lineno}: {type(exc).__name__}: {exc}") from None

    async def _e_Slice(self, node: ast.Slice) -> slice:
        parts = [None if p is None else await self._eval(p) for p in (node.lower, node.upper, node.step)]
        return slice(*parts)

    async def _e_JoinedStr(self, node: ast.JoinedStr) -> str:
        return "".join([str(await self._eval(v)) for v in node.values])

    async def _e_FormattedValue(self, node: ast.FormattedValue) -> str:
        value = await self._eval(node.value)
        spec = await self._eval(node.format_spec) if node.format_spec else ""
        if any(int(n) > 1000 for n in _SPEC_WIDTH_RE.findall(spec)):
            raise CodeModeError(f"line {node.lineno}: format width too large")
        self._guard_serialise(value, node)
        if node.conversion == ord("r"):
            value = repr(value)
        return format(value, spec)

    async def _e_Attribute(self, node: ast.Attribute) -> Any:
        raise CodeModeError(f"line {node.lineno}: attributes can only be used as method calls, e.g. text.lower()")

    async def _e_ListComp(self, node: ast.ListComp) -> list[Any]:
        return [item async for item in self._comprehend(node.generators, node.elt)]

    async def _e_GeneratorExp(self, node: ast.GeneratorExp) -> list[Any]:
        return [item async for item in self._comprehend(node.generators, node.elt)]

    async def _e_SetComp(self, node: ast.SetComp) -> set[Any]:
        return {item async for item in self._comprehend(node.generators, node.elt)}

    async def _e_DictComp(self, node: ast.DictComp) -> dict[Any, Any]:
        pair = ast.Tuple(elts=[node.key, node.value], ctx=ast.Load(), lineno=node.lineno, col_offset=0)
        return {k: v async for k, v in self._comprehend(node.generators, pair)}

    async def _comprehend(self, generators: list[ast.comprehension], elt: ast.expr):
        """Yield *elt* for every binding; comprehension variables leak like Python 2's."""
        first, rest = generators[0], generators[1:]
        for item in list(await self._eval(first.iter)):
            self._tick(first.iter)
            await self._maybe_yield()
            await self._assign(first.target, item)
            if not all([await self._eval(cond) for cond in first.ifs]):
                continue
            if rest:
                async for value in self._comprehend(rest, elt):
                    yield value
            else:
                yield await self._eval(elt)

    async def _e_Call(self, node: ast.Call) -> Any:
        args = [await self._eval(a) for a in node.args]
        kwargs = {kw.arg: await self._eval(kw.value) for kw in node.keywords if kw.arg}
        if any(kw.arg is None for kw in node.keywords):
            raise CodeModeError(f"line {node.lineno}: '**' unpacking is not supported")
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "tools":
            return await self._tool_call(func.attr, args, kwargs, node)
        if isinstance(func, ast.Attribute):
            return self._method_call(await self._eval(func.value), func.attr, args, kwargs, node)
        if isinstance(func, ast.Name) and func.id in _BUILTINS:
            return self._builtin_call(func.id, args, kwargs, node)
        raise CodeModeError(f"line {node.lineno}: only tools.<name>(), builtins and str/list/dict methods can be called")

    # ── calls ─────────────────────────────────────────────────────────────
    async def _tool_call(self, name: str, args: list[Any], kwargs: dict[str, Any], node: ast.Call) -> Any:
        if name not in self._tools:
            allowed = ", ".join(sorted(self._tools)) or "(none)"
            raise CodeModeError(f"line {node.lineno}: tools.{name} is not callable from run_code; allowed: {allowed}")
        if len(self.calls) >= self._limits.max_tool_calls:
            raise CodeModeError(f"line {node.lineno}: more than {self._limits.max_tool_calls} tool calls in one program")
        params = self._tools[name]
        if len(args) > len(params):
            raise CodeModeError(f"line {node.lineno}: tools.{name} takes ({', '.join(params)})")
        call_args = {**dict(zip(params, args)), **kwargs}
        self.calls.append(name)
        return await self._call_tool(name, call_args)

    def _method_call(self, receiver: Any, name: str, args: list[Any], kwargs: dict[str, Any], node: ast.Call) -> Any:
        allowed = _SAFE_METHODS.get(type(receiver), frozenset())
        if isinstance(receiver, str):
            self._ops += len(receiver) // 1000
        elif name in _COMPARE_METHODS:
            self._charge_work(receiver, node)
        if name not in allowed:
            raise CodeModeError(f"line {node.lineno}: {type(receiver).__name__}.{name}() is not supported")
        if type(receiver) is list and name == "sort" and "key" in kwargs:
            raise CodeModeError(f"line {node.lineno}: sort(key=...) is not supported")
        if type(receiver) is str:
            self._precheck_str_method(receiver, name, args, node)
        result = getattr(receiver, name)(*args, **kwargs)
        if name in ("keys", "values", "items"):
            return list(result)
        return result

    def _precheck_str_method(self, text: str, name: str, args: list[Any], node: ast.Call) -> None:
        """Bound the output size of the two str methods that can multiply length."""
        estimate = 0
        if name == "replace" and len(args) >= 2 and isinstance(args[0], str) and isinstance(args[1], str):
            estimate = len(text) + text.count(args[0]) * len(args[1])
        elif name == "join" and args:
            items = list(args[0])
            estimate = sum(_deep_size(i, self._limits.max_len + 1) for i in items) + len(text) * len(items)
        if estimate > self._limits.max_len:
            raise CodeModeError(f"line {node.lineno}: {name}() result would exceed {self._limits.max_len} characters")

    def _builtin_call(self, name: str, args: list[Any], kwargs: dict[str, Any], node: ast.Call) -> Any:
        if name in _COMPARE_BUILTINS:
            for arg in args:
                self._charge_work(arg, node)
        if name in ("print", "str"):
            for arg in args:
                self._guard_serialise(arg, node)
        if name == "print":
            self.printed.append(" ".join(str(a) for a in args)[:500])
            return None
        if name == "range":
            span = range(*args)
            if len(span) > self._limits.max_range:
                raise CodeModeError(f"line {node.lineno}: range() longer than {self._limits.max_range}")
            return list(span)
        if kwargs and not (name == "sorted" and set(kwargs) <= {"reverse"}):
            raise CodeModeError(f"line {node.lineno}: {name}() does not take keyword arguments here")
        try:
            result = _BUILTINS[name](*args, **kwargs)
        except (TypeError, ValueError) as exc:
            raise CodeModeError(f"line {node.lineno}: {name}(): {exc}") from None
        return list(result) if name in ("enumerate", "zip", "reversed") else result

    # ── limits ────────────────────────────────────────────────────────────
    def _binop(self, op: ast.operator, left: Any, right: Any, node: ast.AST) -> Any:
        if isinstance(op, ast.Pow) and (not isinstance(right, (int, float)) or abs(right) > 64):
            raise CodeModeError(f"line {getattr(node, 'lineno', '?')}: exponent too large")
        if isinstance(op, ast.Mod) and isinstance(left, (str, bytes)):
            raise CodeModeError(f"line {getattr(node, 'lineno', '?')}: '%' formatting is not supported; use f-strings")
        if isinstance(op, ast.Mult):
            seq, count = (left, right) if isinstance(left, _SEQ_TYPES) else (right, left)
            if isinstance(seq, _SEQ_TYPES) and isinstance(count, int) and len(seq) * count > self._limits.max_len:
                raise CodeModeError(f"line {getattr(node, 'lineno', '?')}: repetition result too large")
        try:
            return _BIN_OPS[type(op)](left, right)
        except (TypeError, ZeroDivisionError, ValueError) as exc:
            raise CodeModeError(f"line {getattr(node, 'lineno', '?')}: {type(exc).__name__}: {exc}") from None

    def _check_size(self, value: Any, node: ast.AST) -> Any:
        if isinstance(value, _SIZED_TYPES) and len(value) > self._limits.max_len:
            raise CodeModeError(f"line {getattr(node, 'lineno', '?')}: value longer than {self._limits.max_len}")
        if isinstance(value, int) and value.bit_length() > self._limits.max_int_bits:
            raise CodeModeError(f"line {getattr(node, 'lineno', '?')}: integer too large")
        return value

    def _tick(self, node: ast.AST) -> None:
        self._ops += 1
        if self._ops > self._limits.max_ops:
            raise CodeModeError(f"line {getattr(node, 'lineno', '?')}: program exceeded {self._limits.max_ops} steps")
        # wait_for cannot interrupt synchronous work, so the walk checks the clock itself.
        if self._ops % 64 == 0 and time.monotonic() > self._deadline:
            raise asyncio.TimeoutError()

    def _charge_work(self, value: Any, node: ast.AST) -> None:
        """Bound and bill compare-heavy work by the *text* it touches, not the element count.

        Aliasing (``[long_string] * 100000``) builds a list whose sort or ``in``
        compares megabytes of text without allocating any, so both the refusal and
        the step charge use the deep size that the comparisons will actually read.
        """
        if not isinstance(value, _CONTAINER_TYPES):
            return
        size = _deep_size(value, self._limits.max_len + 1)
        if size > self._limits.max_len:
            raise CodeModeError(
                f"line {getattr(node, 'lineno', '?')}: too much text to sort or compare "
                f"(over {self._limits.max_len} characters) — filter or slice it first"
            )
        self._ops += size // 100

    async def _maybe_yield(self) -> None:
        """Give the event loop a turn: the walk is synchronous between tool calls."""
        if self._ops - self._yielded_at >= _YIELD_EVERY:
            self._yielded_at = self._ops
            await asyncio.sleep(0)

    def _account(self, value: Any, node: ast.AST) -> None:
        """Cap the total size of every value the program builds, not just each one."""
        if isinstance(value, _SIZED_TYPES):
            self._alloc += len(value)
            if self._alloc > self._limits.max_total_alloc:
                raise CodeModeError(
                    f"line {getattr(node, 'lineno', '?')}: program built more than "
                    f"{self._limits.max_total_alloc} elements in total"
                )

    def _guard_serialise(self, value: Any, node: ast.AST) -> None:
        """Refuse str()/f-string/print of a structure whose text would be huge (aliasing)."""
        if _deep_size(value, self._limits.max_len) > self._limits.max_len:
            raise CodeModeError(f"line {getattr(node, 'lineno', '?')}: value too large to turn into text")


_SEQ_TYPES = (str, bytes, list, tuple)
_CONTAINER_TYPES = (list, tuple, dict, set)
_COMPARE_METHODS = frozenset({"sort", "index", "count"})
_COMPARE_BUILTINS = frozenset({"sorted", "min", "max", "set", "sum"})
_YIELD_EVERY = 200
_SIZED_TYPES = (str, bytes, list, tuple, dict, set)


def _deep_size(value: Any, budget: int) -> int:
    """Approximate text size of *value*, counting shared references each time; stops past *budget*."""
    total = 0
    stack = [value]
    while stack and total <= budget:
        item = stack.pop()
        if isinstance(item, (str, bytes)):
            total += len(item) + 2
        elif isinstance(item, dict):
            total += 2 + len(item)
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, (list, tuple, set)):
            total += 2 + len(item)
            stack.extend(item)
        else:
            total += 8
    return total


def _as_load(target: ast.expr) -> ast.expr:
    """Re-read an augmented-assignment target as an expression."""
    if isinstance(target, ast.Name):
        return ast.Name(id=target.id, ctx=ast.Load(), lineno=target.lineno, col_offset=0)
    return target


_BUILTINS: dict[str, Callable[..., Any]] = {
    "len": len, "min": min, "max": max, "sum": sum, "sorted": sorted,
    "enumerate": enumerate, "zip": zip, "reversed": reversed,
    "str": str, "int": int, "float": float, "bool": bool,
    "list": list, "dict": dict, "set": set, "tuple": tuple,
    "abs": abs, "round": round, "any": any, "all": all,
    "parse_json": json.loads, "range": range, "print": print,
}


async def run_code(
    source: str,
    call_tool: ToolCaller,
    tools: dict[str, list[str]],
    limits: CodeModeLimits | None = None,
) -> CodeModeResult:
    """Run one Code Mode program; never raises for anything the program does."""
    limits = limits or CodeModeLimits()
    if not isinstance(source, str) or not source.strip():
        return CodeModeResult(ok=False, error="run_code needs a non-empty 'code' string")
    interp = _Interpreter(call_tool, tools, limits)
    try:
        tree = validate(source)
        value = await asyncio.wait_for(interp.run(tree), timeout=limits.timeout_s)
    except CodeModeError as exc:
        return CodeModeResult(ok=False, calls=interp.calls, printed=interp.printed, error=str(exc))
    except asyncio.TimeoutError:
        return CodeModeResult(
            ok=False, calls=interp.calls, printed=interp.printed,
            error=f"program timed out after {limits.timeout_s:.0f}s",
        )
    except (_Break, _Continue):
        return CodeModeResult(ok=False, calls=interp.calls, error="break/continue outside a loop")
    except RecursionError:
        return CodeModeResult(ok=False, calls=interp.calls, error="program nested too deeply")
    except MemoryError:
        return CodeModeResult(ok=False, calls=interp.calls, error="program ran out of memory")
    except Exception as exc:  # noqa: BLE001 - a program's own runtime error is a result, never a crash
        return CodeModeResult(
            ok=False, calls=interp.calls, printed=interp.printed,
            error=f"{type(exc).__name__}: {exc}"[:500],
        )
    return CodeModeResult(ok=True, result=value, calls=interp.calls, printed=interp.printed)


def tool_prompt_lines() -> str:
    """Advertise run_code only while an operator has Code Mode on (rule 19)."""
    if not code_mode_active():
        return ""
    return (
        "CODE MODE (several read-only tool calls in ONE response — use it when a step needs\n"
        "  more than one lookup; only the value you return comes back to you):\n"
        "- run_code(code): Run a small Python-subset program. Call tools as\n"
        "  tools.<name>(...) with the same arguments listed above, assign the answer to\n"
        "  `result`, keep it short (slice, filter, count). Supported: assignment, if/for,\n"
        "  comprehensions, f-strings, str/list/dict methods, len/sorted/min/max/sum/\n"
        "  range/enumerate/zip/parse_json/print. Not supported: import, def, lambda,\n"
        f"  while, names starting with '_'. Callable from run_code: {TOOLS_PLACEHOLDER}.\n"
    )


def fill_tool_list(prompt_text: str) -> str:
    """Name only the read-only tools this prompt really offers (a disabled tool stays hidden)."""
    if TOOLS_PLACEHOLDER not in prompt_text:
        return prompt_text
    names = ", ".join(sorted(callable_tools(prompt_text))) or "(none this step)"
    return prompt_text.replace(TOOLS_PLACEHOLDER, names)


def run_code_example() -> str:
    """One worked example for the tool prompt, or '' while Code Mode is off."""
    if not code_mode_active():
        return ""
    code = (
        "hits = tools.search_code(query='def route', limit=5)\\n"
        "result = [tools.head_file(path=h['path'], lines=30) for h in hits[:2]]"
    )
    return f'Example: {{"tool": "run_code", "args": {{"code": "{code}"}}}}\n'
