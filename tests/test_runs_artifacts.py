"""Durable run artifacts: redaction, size cap, integrity, owner scoping (plan phase 5)."""
from __future__ import annotations

import asyncio
import base64

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from packages.config import control_overrides
from packages.runs.artifacts import (
    ArtifactIntegrityError, ArtifactSecretRefused, ArtifactStore, ArtifactTooLarge,
)
from packages.runs.models import RunRecord
from packages.runs.store import RunStore, set_run_store
from tests._runs_backends import BACKENDS, open_pair

SECRET = "sk-" + "a1B2c3D4e5" * 4
ALICE = {"_id": "alice", "email": "alice@example.com", "role": "user"}
BOB = {"_id": "bob", "email": "bob@example.com", "role": "user"}


@pytest.fixture(autouse=True)
def _controls():
    control_overrides.apply_overrides({})
    yield
    control_overrides.apply_overrides({})


async def _setup(db):
    runs = RunStore(db)
    run = await runs.create(RunRecord(owner_id="alice", company_id="acme"))
    return runs, ArtifactStore(runs), run.run_id


@pytest.mark.parametrize("kind", BACKENDS)
def test_text_artifact_is_redacted_hashed_and_linked(kind, tmp_path):
    async def go():
        async with open_pair(kind, tmp_path) as (db, _):
            runs, arts, rid = await _setup(db)
            ref = await arts.put(rid, f"report-{SECRET}.md", f"key is {SECRET} ok",
                                 agent_id="dev", extra={"api_key": SECRET, "note": SECRET})
            assert ref.redacted is True and ref.owner_id == "alice" and ref.company_id == "acme"
            got = await arts.get(rid, ref.artifact_id)
            assert SECRET not in got.content and got.content.startswith("key is ")
            import hashlib
            assert ref.sha256 == hashlib.sha256(got.content.encode()).hexdigest()
            assert (await runs.get(rid)).artifact_refs == [ref.artifact_id]
            stored = repr(await runs.table("run_artifacts").get(ref.artifact_id))
            events = repr([e.model_dump() for e in await runs.list_events(rid)])
            assert SECRET not in stored and SECRET not in events and SECRET not in repr(ref)
            assert [r.artifact_id for r in await arts.list(rid)] == [ref.artifact_id]
    asyncio.run(go())


def test_binary_with_a_secret_is_refused_and_clean_binary_is_stored():
    async def go():
        runs, arts, rid = await _setup(None)
        with pytest.raises(ArtifactSecretRefused):
            await arts.put(rid, "blob.bin", b"\x00\x01 token " + SECRET.encode() + b"\x02",
                           mime_type="application/octet-stream")
        assert await arts.list(rid) == []
        assert (await runs.get(rid)).artifact_refs == []
        ref = await arts.put(rid, "ok.bin", b"\x00\x01\x02\xff", mime_type="application/octet-stream")
        assert ref.redacted is False and ref.encoding == "base64"
        got = await arts.get(rid, ref.artifact_id)
        assert base64.b64decode(got.content) == b"\x00\x01\x02\xff"
    asyncio.run(go())


def test_oversized_artifact_is_refused_and_the_limit_is_a_live_control():
    async def go():
        _, arts, rid = await _setup(None)
        control_overrides.apply_overrides({"RUNS_ARTIFACT_MAX_BYTES": "1024"})
        with pytest.raises(ArtifactTooLarge):
            await arts.put(rid, "big.txt", "x" * 1025)
        await arts.put(rid, "fits.txt", "x" * 1024)
    asyncio.run(go())


def test_hash_mismatch_is_detected_on_read():
    async def go():
        runs, arts, rid = await _setup(None)
        ref = await arts.put(rid, "a.txt", "original")
        doc = runs.table("run_artifacts").docs[ref.artifact_id]
        doc["content_text"] = "tampered"
        with pytest.raises(ArtifactIntegrityError):
            await arts.get(rid, ref.artifact_id)
        doc["content_text"], doc["encoding"], doc["content_b64"] = "", "base64", "!!notbase64"
        with pytest.raises(ArtifactIntegrityError):
            await arts.get(rid, ref.artifact_id)
    asyncio.run(go())


def test_artifact_of_another_run_and_unknown_run():
    async def go():
        runs, arts, rid = await _setup(None)
        other = (await runs.create(RunRecord(owner_id="alice"))).run_id
        ref = await arts.put(rid, "a.txt", "x")
        assert await arts.get(other, ref.artifact_id) is None
        with pytest.raises(KeyError):
            await arts.put("run_missing", "a.txt", "x")
    asyncio.run(go())


@pytest.fixture
def env():
    from backend.server import app, get_current_user

    runs = RunStore()
    set_run_store(runs)
    holder = {"user": ALICE}

    def _user():
        if holder["user"] is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return holder["user"]

    app.dependency_overrides[get_current_user] = _user
    c = TestClient(app, raise_server_exceptions=False)
    c.holder, c.runs = holder, runs
    yield c
    app.dependency_overrides.clear()
    set_run_store(None)


def test_endpoints_list_and_serve_redacted_content_with_owner_scoping(env):
    runs = env.runs
    rid = asyncio.run(runs.create(RunRecord(owner_id="alice"))).run_id
    ref = asyncio.run(ArtifactStore(runs).put(rid, "r.md", f"x {SECRET}", extra={"k": SECRET}))
    listing = env.get(f"/api/runs/{rid}/artifacts")
    assert listing.status_code == 200
    assert listing.json()["artifacts"] == [ref.artifact_id]
    assert listing.json()["items"][0]["sha256"] == ref.sha256
    one = env.get(f"/api/runs/{rid}/artifacts/{ref.artifact_id}")
    assert one.status_code == 200 and one.json()["integrity_ok"] is True
    assert SECRET not in listing.text and SECRET not in one.text
    assert env.get(f"/api/runs/{rid}/artifacts/art_nope").status_code == 404
    env.holder["user"] = BOB
    assert env.get(f"/api/runs/{rid}/artifacts").status_code == 404
    assert env.get(f"/api/runs/{rid}/artifacts/{ref.artifact_id}").status_code == 404
    env.holder["user"] = None
    assert env.get(f"/api/runs/{rid}/artifacts/{ref.artifact_id}").status_code == 401


def test_endpoint_reports_a_tampered_artifact_as_409(env):
    rid = asyncio.run(env.runs.create(RunRecord(owner_id="alice"))).run_id
    ref = asyncio.run(ArtifactStore(env.runs).put(rid, "a.txt", "original"))
    env.runs.table("run_artifacts").docs[ref.artifact_id]["content_text"] = "tampered"
    r = env.get(f"/api/runs/{rid}/artifacts/{ref.artifact_id}")
    assert r.status_code == 409 and "tampered" not in r.text


def test_a_secret_in_a_run_event_never_reaches_the_stored_event_or_api(env):
    rid = asyncio.run(env.runs.create(RunRecord(owner_id="alice"))).run_id
    asyncio.run(env.runs.append_event(rid, "note", {"msg": f"found {SECRET}", "api_key": SECRET}))
    stored = repr(env.runs.table("run_events").docs)
    served = env.get(f"/api/runs/{rid}/events").text
    assert SECRET not in stored and SECRET not in served


def test_secrets_in_metadata_keys_and_bytes_values_are_redacted():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefSIGNATURE123"

    async def go():
        runs, arts, rid = await _setup(None)
        extra = {jwt: "v", "nested": {f"k-{SECRET}": 1, "debug": jwt.encode(), "ok": "plain"}}
        ref = await arts.put(rid, "a.txt", "hello", extra=extra)
        stored = repr(await runs.table("run_artifacts").get(ref.artifact_id))
        got = await arts.get(rid, ref.artifact_id)
        for leaked in (jwt, SECRET):
            assert leaked not in stored and leaked not in repr(got)
        assert "plain" in stored  # ordinary values and keys survive
    asyncio.run(go())


def test_a_secret_in_a_bytes_metadata_key_is_redacted():
    jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abcdefSIGNATURE123"

    async def go():
        runs, arts, rid = await _setup(None)
        ref = await arts.put(rid, "a.txt", "hello", extra={"nested": {jwt.encode(): "value"}})
        stored = repr(await runs.table("run_artifacts").get(ref.artifact_id))
        assert jwt not in stored and jwt.encode().decode() not in stored
    asyncio.run(go())
