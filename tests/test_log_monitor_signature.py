"""One recurring error line must map to one signature, whatever its timestamp.

The LogMonitor's handler formats records as ``<asctime> [LEVEL] name: message`` and
hashed that whole line, timestamp included. Every occurrence of the same error got a
new signature, so the one-hour cooldown and the healer's dedup never matched and a
single recurring line filed a fix task each time: 211 ``fix`` schedules by 2026-11-14.
"""
from __future__ import annotations

import logging

import agent.log_monitor as lm

_LINE = "{ts} [ERROR] engineio.client: packet queue is empty, aborting"


def test_the_same_error_at_two_times_has_one_signature() -> None:
    a = lm._sig("engineio.client", _LINE.format(ts="2026-11-14 06:00:04,528"))
    b = lm._sig("engineio.client", _LINE.format(ts="2026-11-14 06:16:16,930"))
    assert a == b


def test_different_errors_keep_different_signatures() -> None:
    a = lm._sig("x", "2026-11-14 06:00:04,528 [ERROR] x: first failure")
    b = lm._sig("x", "2026-11-14 06:00:04,528 [ERROR] x: second failure")
    assert a != b


def test_strip_prefix_only_removes_the_formatter_prefix() -> None:
    assert lm._strip_prefix("2026-11-14 06:00:04,528 [ERROR] a.b: boom") == "a.b: boom"
    assert lm._strip_prefix("boom at 2026-11-14 06:00:04,528 [ERROR]") == "boom at 2026-11-14 06:00:04,528 [ERROR]"
    assert lm._strip_prefix("") == ""


def test_engineio_keepalive_noise_is_ignored() -> None:
    assert "engineio.client" in lm.IGNORED_LOGGERS


def test_a_repeated_error_files_one_fix_task(monkeypatch) -> None:
    filed: list[str] = []
    monkeypatch.setattr(lm, "_dispatch_async", lambda title, desc, sig=None: filed.append(title))
    monkeypatch.setattr(lm, "_note_recurrence", lambda sig: None)
    monitor = lm.LogMonitor()
    for ts in ("2026-11-14 06:00:04,528", "2026-11-14 06:16:16,930", "2026-11-14 07:02:53,582"):
        monitor._on_log_error("some.module", "ERROR", f"{ts} [ERROR] some.module: disk exploded")
    assert len(filed) == 1
    assert "2026-11-14" not in filed[0], "the title must not carry the log timestamp"


def test_the_handler_formatter_still_prefixes_a_timestamp() -> None:
    """Guards the assumption this fix rests on: the message arrives with the prefix."""
    handler = lm._ErrorCaptureHandler(lm.LogMonitor())
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    record = logging.LogRecord("n", logging.ERROR, "f", 1, "m", None, None)
    assert lm._LINE_PREFIX.match(handler.format(record))
