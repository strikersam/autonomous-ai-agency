"""``reset_store()`` must clear EVERY cached motor client, not just one.

A motor ``AsyncIOMotorClient`` binds to whichever event loop was current when it
was constructed. The function-scoped ``client`` fixture gives each test a fresh
TestClient → fresh portal → fresh event loop, so any motor client cached from an
earlier test is bound to a closed loop and raises ``RuntimeError: Event loop is
closed`` the moment it is used again.

``tests/conftest.py`` calls ``reset_store()`` before each TestClient enters its
lifespan precisely to prevent this — its docstring names
``test_auth_me_regression`` as the flake it was written for. But it only cleared
the storage-layer client. ``services.company_graph_store`` keeps its own client on
a module-level singleton, which therefore survived every reset and stayed bound to
the first test's loop for the whole session.

That failure mode is ordering-dependent by construction: the affected test passes
in isolation and fails only after enough other tests have run to create the
singleton first. This module guards the invariant structurally, so a future module
that caches a motor client cannot silently reintroduce the flake.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Modules that cache a motor client or db handle on module/instance state and so
# MUST be cleared by reset_store(). Keep in sync with the reset_store() body.
_MOTOR_CACHING_MODULES: dict[str, str] = {
    "packages/storage/mongo.py": "_client / _db module singletons",
    "services/company_graph_store.py": "_graph_store singleton holds self._client",
}


def test_reset_store_clears_the_storage_layer_client() -> None:
    from db import reset_store
    from packages.storage import mongo as ms

    ms._client = object()  # type: ignore[assignment]
    ms._db = object()  # type: ignore[assignment]

    reset_store()

    assert ms._client is None
    assert ms._db is None


def test_reset_store_clears_the_company_graph_store_singleton() -> None:
    """The regression: this singleton survived every reset."""
    from db import reset_store
    from services import company_graph_store as cgs

    sentinel = object()
    cgs._graph_store = sentinel  # type: ignore[assignment]

    reset_store()

    assert cgs._graph_store is None, (
        "company_graph_store._graph_store survived reset_store(); its motor "
        "client stays bound to a closed event loop and any later test that "
        "reaches it raises 'Event loop is closed'"
    )


def test_reset_store_drops_the_store_singleton() -> None:
    import db
    from db import reset_store

    db._store = object()  # type: ignore[assignment]
    reset_store()

    assert db._store is None


def test_reset_store_is_idempotent_and_safe_when_nothing_is_cached() -> None:
    """conftest calls this before every test, including the first."""
    from db import reset_store

    reset_store()
    reset_store()  # must not raise on already-clean state


@pytest.mark.parametrize(
    ("module_path", "why"), sorted(_MOTOR_CACHING_MODULES.items())
)
def test_every_motor_caching_module_is_handled_by_reset_store(
    module_path: str, why: str
) -> None:
    """Structural guard: reset_store must mention each motor-caching module.

    Cheap to satisfy, and it fails loudly if someone adds a third cached client
    without wiring it into the reset path — which is how this bug arose.
    """
    from db import reset_store

    source = inspect.getsource(reset_store)
    module_name = module_path.replace("/", ".").removesuffix(".py")
    leaf = module_name.rsplit(".", 1)[-1]

    assert leaf in source, (
        f"{module_path} caches a motor client ({why}) but reset_store() does not "
        f"clear it. Any test that touches it after another test created it will "
        f"hit 'Event loop is closed'."
    )


def test_no_unregistered_motor_clients_exist() -> None:
    """Find AsyncIOMotorClient construction outside the registered modules.

    Parses the AST rather than grepping so a match means a real call site.
    Scripts and one-shot utilities are excluded — they build a client, use it,
    and exit, so they never outlive a test's event loop.
    """
    excluded_prefixes = ("tests/", "scripts/", "setup/", "docker/", "_scripts/")
    offenders: list[str] = []

    for path in _REPO_ROOT.rglob("*.py"):
        rel = path.relative_to(_REPO_ROOT).as_posix()
        if rel.startswith(excluded_prefixes) or "node_modules" in rel:
            continue
        if rel in _MOTOR_CACHING_MODULES:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name == "AsyncIOMotorClient":
                    offenders.append(f"{rel}:{node.lineno}")

    assert not offenders, (
        "AsyncIOMotorClient is constructed outside the modules reset_store() "
        f"knows about: {offenders}. Either reset it in db.reset_store() and add "
        "it to _MOTOR_CACHING_MODULES here, or confirm the client cannot outlive "
        "a single event loop and add its path to excluded_prefixes."
    )
