#!/usr/bin/env python3
"""scripts/download_glm52.py — kick the GLM-5.2 GGUF download from HuggingFace.

Returns 0 on success, non-zero on error.

Reads the HF token from (in priority order):
  1. ``$HF_TOKEN`` environment variable
  2. ``logs/.hf_token`` next to the repo root (chmod 600)

Uses ``huggingface_hub.snapshot_download`` directly (NOT ``python -m`` or
console scripts) so Python-version-specific entry-point races can't break the
download.  Enable ``hf_transfer`` for multi-GB/s streaming if installed.

Args are env-only by design — this script is meant to be backgrounded via
``Start-Process`` so it doesn't block the bash / PowerShell parent.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

REPO = "openai/glm-5.2"
INCLUDE_PATTERN = "*Q4_K_M*"
LOCAL_DIR_WINDOWS = r"D:\hfkld-qg7ky\local-models\GLM-5.2"


def _resolve_token() -> str:
    raw = os.environ.get("HF_TOKEN", "").strip()
    if raw:
        return raw
    repo_root = Path(__file__).resolve().parent.parent
    fallback = repo_root / "logs" / ".hf_token"
    if fallback.is_file():
        try:
            return fallback.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise SystemExit(f"could not read HF token fallback {fallback}: {exc}") from exc
    raise SystemExit(
        "HF_TOKEN unset and logs/.hf_token fallback missing — set one of them"
    )


def _resolve_local_dir() -> Path:
    raw = os.environ.get("GLM52_LOCAL_DIR", "").strip()
    if raw:
        return Path(raw)
    return Path(LOCAL_DIR_WINDOWS)


def _log_path() -> Path:
    raw = os.environ.get(
        "GLM52_DOWNLOAD_LOG",
        r"C:\Users\swami\qwen-server\logs\glm-5.2.download.log",
    ).strip()
    p = Path(raw)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _append_log(line: str) -> None:
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{stamp}] {line}\n"
    try:
        with _log_path().open("a", encoding="utf-8") as fh:
            fh.write(msg)
    except OSError:
        pass
    print(msg, end="", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download GLM-5.2 Q4_K_M GGUF from HuggingFace into the local-models dir."
    )
    parser.add_argument(
        "--repo", default=REPO, help="HF repo (default: openai/glm-5.2)"
    )
    parser.add_argument(
        "--include", default=INCLUDE_PATTERN,
        help="Filename glob (default: *Q4_K_M*) — picks the smaller Q4 quant",
    )
    parser.add_argument(
        "--local-dir", default=None,
        help="Destination directory (default: D:\\hfkld-qg7ky\\local-models\\GLM-5.2)",
    )
    args = parser.parse_args(argv)

    try:
        token = _resolve_token()
    except SystemExit as exc:
        print(f"[FATAL] token: {exc}", file=sys.stderr)
        return 2

    local_dir = Path(args.local_dir) if args.local_dir else _resolve_local_dir()
    local_dir.mkdir(parents=True, exist_ok=True)
    _append_log(f"start repo={args.repo} include={args.include} local_dir={local_dir}")

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        _append_log(f"[FATAL] huggingface_hub import failed: {exc}")
        _append_log("[FATAL] run: python -m pip install --upgrade 'huggingface_hub>=0.24'")
        return 3

    if os.environ.get("HF_HUB_ENABLE_HF_TRANSFER") is None:
        os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"

    started = time.monotonic()
    try:
        # 2 workers: parallel SHA-256 verify without starving the
        # sequential disk I/O on a single SATA D:\ drive (code-review
        # caveat for single-file GGUF downloads).
        snapshot_download(
            repo_id=args.repo,
            local_dir=str(local_dir),
            allow_patterns=[args.include],
            token=token,
            max_workers=2,
        )
    except Exception as exc:
        _append_log(f"[FATAL] snapshot_download raised: {exc.__class__.__name__}: {exc}")
        return 1

    elapsed_s = time.monotonic() - started
    _append_log(f"OK elapsed={elapsed_s/60:.1f}min repo={args.repo} -> {local_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
