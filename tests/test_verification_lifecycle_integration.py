"""End-to-end verification lifecycle through the real agent loop.

What is real here: ``AgentRunner.run`` in orchestrator mode with the same
bypass token ``WorkflowOrchestrator`` sets, the executor writing files into a
git workspace, ``py_compile`` and ``pytest`` executed as real subprocesses on
that workspace, the contract/evidence decision, spec persistence logic, and the
task gate (``settle_success`` → ``rework_or_park``). What is scripted: the model
(planner, executor, step verifier, judge) and the Mongo collection. The judge is
scripted to approve every run, including the broken one, to prove an approval
cannot outrank the evidence. This does not verify a live model or a live DB.
"""
from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agent.loop import AgentRunner
from packages.config import settings
from services import spec_store
from tasks import verification as tv
from tasks.models import Task, TaskStatus

TEST_FILE = (
    "import sys, pathlib\n"
    "sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))\n"
    "from calc import add\n\n\n"
    "def test_add():\n    assert add(2, 3) == 5\n"
)
PLAN = ('{"goal":"Fix add in calc.py","steps":[{"id":1,"description":"Make add return the sum",'
        '"files":["calc.py"],"type":"edit","acceptance":"add(2, 3) == 5"}]}')
JUDGE = '{"verdict":"APPROVED","security":"PASS","correctness":"PASS","notes":"Looks correct."}'


def _field(row: dict[str, Any], key: str) -> Any:
    """Resolve a Mongo dotted key ("contract.version") against a row."""
    value: Any = row
    for part in key.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


class FakeSpecs:
    """Enough of a motor collection for spec_store: insert, find_one, $set/$push/$slice."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def insert_one(self, doc):
        self.rows.append(dict(doc))

    async def find_one(self, query):
        return next((dict(r) for r in self.rows if all(_field(r, k) == v for k, v in query.items())), None)

    async def update_one(self, query, update):
        async with self._lock:
            row = next((r for r in self.rows if all(_field(r, k) == v for k, v in query.items())), None)
            if row is None:
                return SimpleNamespace(matched_count=0)
            await asyncio.sleep(0)  # yield, so concurrent writers interleave
            for key, spec in (update.get("$push") or {}).items():
                modifier = isinstance(spec, dict) and "$each" in spec
                items = spec["$each"] if modifier else [spec]
                merged = list(row.get(key) or []) + list(items)
                limit = spec.get("$slice") if modifier else None
                row[key] = merged[limit:] if limit else merged
            row.update(update.get("$set") or {})
            return SimpleNamespace(matched_count=1)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "calc.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (root / "tests" / "test_calc.py").write_text(TEST_FILE, encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    _git(root, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init")
    return root


@pytest.fixture
def specs(monkeypatch) -> FakeSpecs:
    coll = FakeSpecs()
    monkeypatch.setattr(spec_store, "_db", lambda: SimpleNamespace(agent_specs=coll))
    monkeypatch.setattr(settings, "agent_empirical_verify_raw", "true")
    monkeypatch.setattr(settings, "verification_policy_enforced_raw", "true")
    monkeypatch.setattr(settings, "task_verification_required_raw", "true")
    monkeypatch.setenv("AGENT_SPEC_PERSIST", "true")
    monkeypatch.setenv("AGENT_SPEC_APPROVAL_REQUIRED", "false")
    return coll


def _scripted_runner(root: Path, body: str, path: str, store: Any = None) -> AgentRunner:
    runner = AgentRunner(ollama_base="http://localhost:11434", workspace_root=root, session_store=store)

    async def chat(model: str, messages: list[dict[str, str]]) -> str:
        system = messages[0]["content"] if messages else ""
        if "Planner agent" in system:
            return PLAN.replace("calc.py", path)
        if "preparing to execute one coding step" in system:
            return '{"tool":"finish","args":{"reason":"ready"}}'
        if "executing ONE step" in system:
            return f"FILE: {path}\nACTION: replace\n```python\ndef add(a, b):\n    {body}\n```"
        if "Check syntax and logic" in system:
            return '{"status":"pass","issues":[]}'
        if "code-review judge" in system:
            return JUDGE
        return "{}"

    runner._chat_text = chat  # type: ignore[method-assign]
    return runner


def _run(root: Path, body: str, monkeypatch, path: str = "calc.py", store: Any = None,
         session_id: str | None = None) -> dict[str, Any]:
    from services import workflow_orchestrator as wo

    monkeypatch.setattr(wo, "WORKFLOW_MODE", "orchestrator")
    runner = _scripted_runner(root, body, path, store)

    async def go() -> dict[str, Any]:
        token = wo._BYPASS.set(True)  # exactly what WorkflowOrchestrator._handle_execute does
        try:
            return await runner.run(instruction="Fix add in calc.py", history=[], requested_model=None,
                                    auto_commit=False, max_steps=3, session_id=session_id)
        finally:
            wo._BYPASS.reset(token)

    return asyncio.run(go())


def test_failed_attempt_is_corrected_and_then_verified(workspace, specs, monkeypatch, tmp_path):
    from agent.state import AgentSessionStore

    task = Task(owner_id="owner@example.com", title="Fix add", status=TaskStatus.IN_PROGRESS)
    store = AgentSessionStore(db_path=tmp_path / "events.db")
    session = store.create(title="verify")

    # Attempt 1: wrong fix. The real pytest run fails; the judge approves anyway.
    first = _run(workspace, "return a * b", monkeypatch, store=store, session_id=session.session_id)
    report = first["verification_report"]
    assert first["steps"][0]["status"] == "failed"
    assert report["verdict"] == "FAILED"
    unit = [c for c in report["checks"] if c["strategy"] == "unit"]
    assert unit and unit[0]["status"] == "failed" and unit[0]["exit_code"] not in (0, None)
    assert "assert" in unit[0]["output_tail"]  # real pytest output, not a narrative
    assert {f["kind"] for f in report["findings"]} >= {"implementation_defect", "contract_violation"}
    assert report["source_revision"] == _git(workspace, "rev-parse", "HEAD")
    assert report["persisted"] is True
    logged = [e for e in store.get_events(session.session_id) if e.event_type == "verification_failed"]
    assert logged and logged[0].payload["verdict"] == "FAILED"  # reaches the session retro

    tv.settle_success(task, first, actor="runtime:internal_agent")
    assert task.verification.verdict == "FAIL"
    assert task.status == TaskStatus.IN_PROGRESS and task.pending_agent_run  # sent back, bounded
    assert "assert" in task.comments[-1].body  # the next attempt reads the actual failure

    # Attempt 2: correct fix. Same real checks now pass.
    second = _run(workspace, "return a + b", monkeypatch)
    report2 = second["verification_report"]
    assert second["steps"][0]["status"] == "applied"
    assert report2["verdict"] == "VERIFIED", report2["reasons"]
    assert all(c["status"] == "passed" for c in report2["checks"])
    assert {c["criterion_id"]: c["status"] for c in report2["criteria"]} == {"step-1": "passed", "goal": "passed"}

    tv.settle_success(task, second, actor="runtime:internal_agent")
    assert task.status == TaskStatus.DONE and task.verification.verdict == "PASS"
    assert any(e.startswith("Evidence report") for e in task.verification.evidence)

    # Both runs' contracts and evidence were persisted with their specs.
    assert len(specs.rows) == 2
    assert [r["latest_verdict"] for r in specs.rows] == ["FAILED", "VERIFIED"]
    for row in specs.rows:
        assert row["contract"]["criteria"][0]["description"] == "add(2, 3) == 5"
        assert len(row["evidence_reports"]) == 1
        assert "## Verification contract" in row["markdown"]


def test_high_risk_run_is_verified_but_waits_for_a_person(workspace, specs, monkeypatch):
    (workspace / "key_store.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (workspace / "tests" / "test_key_store.py").write_text(TEST_FILE.replace("from calc", "from key_store"),
                                                         encoding="utf-8")
    result = _run(workspace, "return a + b", monkeypatch, path="key_store.py")
    report = result["verification_report"]
    assert report["verdict"] == "VERIFIED", report["reasons"]
    assert report["risk_tier"] == "high" and report["requires_human_approval"] is True

    task = Task(owner_id="owner@example.com", title="Fix key store", status=TaskStatus.IN_PROGRESS)
    tv.settle_success(task, result, actor="runtime:internal_agent")
    assert task.status == TaskStatus.IN_REVIEW and tv.HIGH_RISK_TAG in task.tags
    assert "person must approve" in task.review_reason


def test_concurrent_evidence_writes_do_not_lose_reports(specs):
    async def go() -> list[dict]:
        doc = await spec_store.persist_plan_spec(session_id="s", goal="g", steps=[], contract={"criteria": []})
        reports = [{"report_id": str(i), "verdict": "VERIFIED"} for i in range(15)]
        stored = await asyncio.gather(*(spec_store.record_evidence(doc["spec_id"], r) for r in reports))
        assert all(stored)
        return (await spec_store.get_spec(doc["spec_id"]))["evidence_reports"]

    saved = asyncio.run(go())
    assert sorted(r["report_id"] for r in saved) == sorted(str(i) for i in range(15))


def test_evidence_list_is_bounded(specs):
    async def go() -> list[dict]:
        doc = await spec_store.persist_plan_spec(session_id="s", goal="g", steps=[])
        for i in range(spec_store._MAX_REPORTS_PER_SPEC + 5):
            await spec_store.record_evidence(doc["spec_id"], {"report_id": str(i)})
        return (await spec_store.get_spec(doc["spec_id"]))["evidence_reports"]

    saved = asyncio.run(go())
    assert len(saved) == spec_store._MAX_REPORTS_PER_SPEC and saved[-1]["report_id"] == str(spec_store._MAX_REPORTS_PER_SPEC + 4)


def test_only_a_person_can_amend_a_persisted_contract(specs):
    from agent.models import AgentPlan, AgentStep
    from agent.verification_contract import build_contract

    contract = build_contract(AgentPlan(goal="g", steps=[AgentStep(id=1, description="s", files=["a.py"], type="edit")]))

    async def go():
        doc = await spec_store.persist_plan_spec(session_id="s", goal="g", steps=[], contract=contract.model_dump())
        weaker = [{"criterion_id": "goal", "description": "anything", "source": "goal"}]
        with pytest.raises(PermissionError):
            await spec_store.amend_spec_contract(doc["spec_id"], actor="agent:dev", reason="r", criteria=weaker)
        return await spec_store.amend_spec_contract(doc["spec_id"], actor="owner@example.com",
                                                    reason="narrowed", criteria=weaker)

    amended = asyncio.run(go())
    assert amended["contract"]["version"] == 2 and len(amended["contract_history"]) == 1


def test_flaky_test_is_detected_on_a_real_rerun(tmp_path: Path, monkeypatch):
    from agent import empirical_verify as ev

    monkeypatch.setattr(settings, "agent_empirical_verify_raw", "true")
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "flaky.py").write_text("X = 1\n", encoding="utf-8")
    (root / "tests" / "test_flaky.py").write_text(
        "import pathlib\n"
        "MARK = pathlib.Path(__file__).with_name('ran_once')\n\n\n"
        "def test_sometimes():\n"
        "    first = not MARK.exists()\n"
        "    MARK.write_text('x')\n"
        "    assert not first\n",
        encoding="utf-8",
    )
    outcome = ev.verify_on_host(root, ["flaky.py"], {"PATH": "/usr/bin:/bin", "TESTING": "true"})
    unit = [r for r in outcome.results if r["strategy"] == "unit"]
    assert unit[0]["status"] == "untrusted" and unit[0]["attempts"] == 2
    assert outcome.issues and "flaky" in outcome.issues[0]
    assert outcome.checks == []  # a flaky pass is never recorded as an executed check


def test_concurrent_contract_amendment_is_refused(specs):
    from agent.models import AgentPlan, AgentStep
    from agent.verification_contract import build_contract

    contract = build_contract(AgentPlan(goal="g", steps=[AgentStep(id=1, description="s", files=["a.py"], type="edit")]))
    crit = [{"criterion_id": "goal", "description": "narrowed", "source": "goal"}]

    async def go():
        doc = await spec_store.persist_plan_spec(session_id="s", goal="g", steps=[], contract=contract.model_dump())
        stale = await spec_store.get_spec(doc["spec_id"])
        await spec_store.amend_spec_contract(doc["spec_id"], actor="a@example.com", reason="first", criteria=crit)
        original_get = spec_store.get_spec

        async def stale_read(spec_id):  # the second amender read version 1 before the first wrote
            return stale

        spec_store.get_spec = stale_read
        try:
            with pytest.raises(RuntimeError, match="concurrently"):
                await spec_store.amend_spec_contract(doc["spec_id"], actor="b@example.com", reason="second", criteria=crit)
        finally:
            spec_store.get_spec = original_get
        return await spec_store.get_spec(doc["spec_id"])

    final = asyncio.run(go())
    assert final["contract"]["version"] == 2 and len(final["contract_history"]) == 1
