"""packages/runs/artifacts.py — durable, redacted, hash checked artifacts of a run.

An artifact is the content a run produced (a report, a diff, a log). It lives in
the ``run_artifacts`` collection of the shared storage backend, one document per
artifact, with the content inline (text, or base64 for binary):

* Size is capped by ``RUNS_ARTIFACT_MAX_BYTES``; larger content is refused, never cut.
* Text goes through ``redact_text`` BEFORE it is hashed and stored, so the hash
  describes exactly what is on disk. Metadata (name, mime type, agent, extras) is
  redacted too.
* Binary content is scanned for the same secret shapes (read as latin-1); a match
  refuses the artifact, because bytes cannot be redacted without corrupting them.
  Clean binary is stored with ``redacted = False``.
* Reading recomputes the sha256 and raises ``ArtifactIntegrityError`` on a mismatch.
* The artifact id is appended to ``RunRecord.artifact_refs``; the collection stays
  the source of truth, so a lost race on the run document loses no artifact.
"""
from __future__ import annotations

import base64
import hashlib
import logging
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field

from packages.config import runs_settings
from packages.runs.redaction import redact_text, redact_value
from packages.runs.store import RunStore

log = logging.getLogger("qwen-proxy")

RUN_ARTIFACTS = "run_artifacts"
_REF_RETRIES = 5


class ArtifactError(ValueError):
    """An artifact was refused or failed a check."""


class ArtifactTooLarge(ArtifactError):
    """Content is over ``RUNS_ARTIFACT_MAX_BYTES``."""


class ArtifactSecretRefused(ArtifactError):
    """Binary content matched a secret pattern and was not stored."""


class ArtifactIntegrityError(ArtifactError):
    """The stored content no longer matches its recorded sha256."""


class ArtifactRef(BaseModel):
    """Metadata of one stored artifact (never the content)."""

    artifact_id: str
    run_id: str
    name: str
    mime_type: str
    agent_id: str | None = None
    size: int
    sha256: str
    created_at: float
    owner_id: str | None = None
    company_id: str | None = None
    retention_days: int | None = None
    redacted: bool = False
    encoding: str = "text"
    extra: dict[str, Any] = Field(default_factory=dict)


class ArtifactContent(BaseModel):
    """An artifact with its content, as served to clients."""

    ref: ArtifactRef
    content: str
    integrity_ok: bool = True


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _has_secret(data: bytes) -> bool:
    text = data.decode("latin-1")
    return redact_text(text) != text


def _ref_of(doc: dict[str, Any]) -> ArtifactRef:
    return ArtifactRef.model_validate({k: v for k, v in doc.items() if k in ArtifactRef.model_fields})


class ArtifactStore:
    """Artifacts of runs over the run store's backend."""

    def __init__(self, runs: RunStore) -> None:
        self._runs = runs
        self._table = runs.table(RUN_ARTIFACTS)

    def _prepare(self, content: str | bytes) -> tuple[bytes, dict[str, Any], bool]:
        """The bytes to hash and store, the content fields, and the redacted flag."""
        if isinstance(content, str):
            clean = redact_text(content)
            raw = clean.encode("utf-8")
            fields, redacted, encoding = {"content_text": clean}, clean != content, "text"
        else:
            raw = bytes(content)
            fields, redacted, encoding = {"content_b64": base64.b64encode(raw).decode("ascii")}, False, "base64"
        if len(raw) > runs_settings.artifact_max_bytes():
            raise ArtifactTooLarge(f"artifact is {len(raw)} bytes; the limit is "
                                   f"{runs_settings.artifact_max_bytes()}")
        if encoding == "base64" and _has_secret(raw):
            raise ArtifactSecretRefused("binary artifact contains a secret pattern; not stored")
        return raw, {**fields, "encoding": encoding}, redacted

    async def put(self, run_id: str, name: str, content: str | bytes, *,
                  mime_type: str = "text/plain", agent_id: str | None = None,
                  retention_days: int | None = None,
                  extra: dict[str, Any] | None = None) -> ArtifactRef:
        """Store *content* for the run and return its metadata. ``KeyError`` for an unknown run."""
        run = await self._runs.get(run_id)
        if run is None:
            raise KeyError(run_id)
        raw, fields, redacted = self._prepare(content)
        meta = {
            "artifact_id": f"art_{uuid.uuid4().hex}", "run_id": run_id,
            "name": redact_text(name)[:256], "mime_type": redact_text(mime_type)[:128],
            "agent_id": redact_text(agent_id) if agent_id else None,
            "size": len(raw), "sha256": _digest(raw), "created_at": time.time(),
            "owner_id": run.owner_id, "company_id": run.company_id,
            "retention_days": retention_days, "redacted": redacted,
            "extra": redact_value(dict(extra or {})),
        }
        await self._table.insert_if_absent(meta["artifact_id"], {**meta, **fields})
        await self._link(run_id, meta["artifact_id"])
        await self._runs.append_event(run_id, "artifact_stored", {
            "artifact_id": meta["artifact_id"], "name": meta["name"],
            "size": meta["size"], "sha256": meta["sha256"]}, actor=meta["agent_id"])
        return ArtifactRef.model_validate({**meta, "encoding": fields["encoding"]})

    async def _link(self, run_id: str, artifact_id: str) -> None:
        for _ in range(_REF_RETRIES):
            run = await self._runs.get(run_id)
            if run is None:
                return
            refs = [*run.artifact_refs, artifact_id]
            if await self._runs.update(run_id, {"artifact_refs": refs},
                                       expect={"updated_at": run.updated_at}):
                return
        log.warning("runs: artifact %s stored but not linked on run %s", artifact_id, run_id)

    async def list(self, run_id: str) -> list[ArtifactRef]:
        """Metadata of every artifact of the run, oldest first."""
        docs = await self._table.find({"run_id": run_id}, sort="created_at")
        return [_ref_of(d) for d in docs]

    async def get(self, run_id: str, artifact_id: str) -> ArtifactContent | None:
        """The artifact with its content, or ``None`` when it is not this run's.

        Raises ``ArtifactIntegrityError`` when the stored content fails its hash.
        """
        doc = await self._table.get(artifact_id)
        if doc is None or doc.get("run_id") != run_id:
            return None
        if doc.get("encoding") == "base64":
            content = doc.get("content_b64") or ""
            try:
                raw = base64.b64decode(content, validate=True)
            except ValueError as exc:  # binascii.Error is a ValueError
                raise ArtifactIntegrityError(f"artifact {artifact_id}: content is not valid") from exc
        else:
            content = doc.get("content_text") or ""
            raw = content.encode("utf-8")
        if _digest(raw) != doc.get("sha256") or len(raw) != doc.get("size"):
            log.error("runs: artifact %s failed its integrity check", artifact_id)
            raise ArtifactIntegrityError(f"artifact {artifact_id}: content does not match its hash")
        return ArtifactContent(ref=_ref_of(doc), content=content)
