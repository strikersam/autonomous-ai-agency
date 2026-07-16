"""scripts/run_patched_colibri.py

Pre-launch wrapper for JustVugg/colibri `c/openai_server.py`.

The upstream `Engine.__init__` (around line 457) calls:
    self.process = subprocess.Popen(
        [str(executable), str(cap)], env=child_env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0,
    )

It silently drops every flag passed on the command line --port --host
--model --model-id --gpu-layers --ctx-size, leaving glm.exe bound only
to the cap argument. This is the Blocker 1 root cause that prevented
this repo's colibri launcher from bringing :8081 up.

Fix (this file): monkey-patch `subprocess.Popen` BEFORE
`openai_server.py` is exec'd, so when the engine spawns glm.exe with
the buggy two-element argv we intercept it and re-prepend the outer
argv flags. Net effect: glm.exe receives `--port <Port> --host <Host>
--model <WeightsDir> --model-id <id> ...` exactly as the launcher
intended.

Usage (same shape as before):
    python scripts/run_patched_colibri.py \
        --engine  <...>  --port <P>  --host <H>  \
        --model   <...>  --model-id <id>  --cors-origin '*' [...]

Resolves to $COLIBRI_C_DIR/openai_server.py for the actual openai_server
exec (no hardcoded paths). No JustVugg/ files are touched.
"""
from __future__ import annotations

import os
import runpy
import subprocess
import sys
import threading

_real_popen = subprocess.Popen

# Flags whose values the glm.exe binary actually consumes. We forward
# these from the outer argv when we detect the upstream's 2-element
# (executable, cap) shape.
_FORWARD_FLAGS = {
    "--port",
    "--host",
    "--model",
    "--model-id",
    "--gpu-layers",
    "--ctx-size",
    "--cap",
}


def _exit_watch_delay() -> float:
    """Resolve the COLIBRI_PATCH_EXIT_WATCH delay in seconds, clamped to [0, 60].

    Operators can dial COLIBRI_PATCH_EXIT_WATCH_DELAY to balance diagnostic
    coverage vs. timer churn:
      - 0.5 s  catch instant SIGKILLs (Blocker 2 OOM during weight page-in).
      - 2.0 s  default; covers most scenarios.
      - 5.0+ s catch slower memory-fault pages or post-init crashes.
    Invalid floats fall back to the 2.0 s default.
    """
    raw = os.environ.get("COLIBRI_PATCH_EXIT_WATCH_DELAY", "2.0").strip()
    try:
        # Floor at 0.05 s so a typo (e.g. explicit 0) cannot collapse the
        # watchdog back to the pre-fix "immediate poll() returns None"
        # behaviour; the Timer deferral is the whole point of the feature.
        return max(0.05, min(float(raw), 60.0))
    except ValueError:
        return 2.0


def _patched_popen(args, *a, **kw):
    """Intercept JustVugg Engine -> glm.exe Popen and forward outer argv.

    Upstream signature: `subprocess.Popen([str(executable), str(cap)], env=child_env,
    stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)`. If we see exactly
    that 2-element shape AND the executable basename is glm(.exe) AND the upstream
    signature kwargs match AND the path-prefix guard trips AND no denylist override
    is set, prepend the operator's outer flags so glm.exe actually receives
    --port/--host/--model/--model-id.
    """
    exe_basename = (
        os.path.basename(args[0]).lower()
        if isinstance(args, list) and args and isinstance(args[0], str)
        else ""
    )
    exe_full = (
        args[0].lower()
        if isinstance(args, list) and args and isinstance(args[0], str)
        else ""
    )
    # Path-prefix guard (default): JustVugg canonical layout. Operators with a
    # flat checkout (e.g. 'glm-bin/glm.exe') can override with the env var
    # COLIBRI_PATCH_PATH_OK=<comma-separated-substrings> which REPLACES the default
    # prefix match for that operator. Both the override and the denylist are
    # case-folded for consistency.
    override_substrs = {
        tok.strip().lower()
        for tok in os.environ.get("COLIBRI_PATCH_PATH_OK", "").split(",")
        if tok.strip()
    }
    if override_substrs:
        path_ok = any(sub in exe_full for sub in override_substrs)
    else:
        path_ok = (
            "colibri" in exe_full
            or "/c/" in exe_full
            or "\\c\\" in exe_full
        )
    denylist = {
        tok.strip().lower()
        for tok in os.environ.get("COLIBRI_PATCH_DENYLIST", "").split(",")
        if tok.strip()
    }
    path_ok = path_ok and not any(tok in exe_full for tok in denylist)
    should_patch = (
        isinstance(args, list)
        and len(args) == 2
        and exe_basename in ("glm.exe", "glm")
        and path_ok
        and kw.get("stdin") is subprocess.PIPE
        and kw.get("stdout") is subprocess.PIPE
    )
    if should_patch:
        outer = [
            t
            for t in sys.argv[1:]
            if t.split("=", 1)[0] in _FORWARD_FLAGS
        ]
        if outer:
            if os.environ.get(
                "COLIBRI_PATCH_VERBOSE", ""
            ).strip().lower() in ("1", "true", "yes"):
                sys.stderr.write(
                    f"[colibri-patch] glm.exe Popen rewritten; forwarding "
                    f"{len(outer)} flags: {outer}\n"
                )
            else:
                names = [t.split("=", 1)[0] for t in outer]
                sys.stderr.write(
                    f"[colibri-patch] glm.exe Popen rewritten; forwarding "
                    f"{len(outer)} flags: {names}\n"
                )
            args = [args[0]] + outer + [args[1]]
    proc = _real_popen(args, *a, **kw)
    # Optional watchdog: when COLIBRI_PATCH_EXIT_WATCH=1, schedule a delayed
    # +2 s proc.poll() so sub-second OS SIGKILLs (Blocker 2 hardware-fatal
    # OOM during weight load) become observable in colibri-openai-err.log.
    # An immediate proc.poll() right after Popen is too soon (process is
    # still initialising) and would just return None. Default off — zero
    # behaviour change when unset.
    if (
        should_patch
        and os.environ.get("COLIBRI_PATCH_EXIT_WATCH", "").strip().lower()
        in ("1", "true", "yes")
    ):
        def _delayed_poll() -> None:
            try:
                rc = proc.poll()
            except Exception as e:
                sys.stderr.write(
                    f"[colibri-patch] glm.exe +2s poll() failed: {e}\n"
                )
                return
            sys.stderr.write(
                f"[colibri-patch] glm.exe +2s poll() returncode={rc}; pid={proc.pid}\n"
            )

        threading.Timer(_exit_watch_delay(), _delayed_poll).start()
    return proc


def _resolve_target(argv_first: str | None) -> str:
    if argv_first and (argv_first.endswith(".py") or "/" in argv_first or "\\" in argv_first):
        return argv_first
    cdir = os.environ.get("COLIBRI_C_DIR", "").strip()
    if not cdir:
        sys.exit(
            "[colibri-patch] COLIBRI_C_DIR env var is unset. Either set it "
            "in .env (D:\\...\\colibri\\c) or pass a path as the first argv."
        )
    return os.path.join(cdir, "openai_server.py")


def main() -> None:
    target = _resolve_target(sys.argv[1] if len(sys.argv) > 1 else None)
    if not os.path.isfile(target):
        sys.exit(f"[colibri-patch] openai_server.py not found at {target!r}")
    subprocess.Popen = _patched_popen  # type: ignore[assignment]
    sys.stderr.write(f"[colibri-patch] exec {target} (Popen patched)\n")
    runpy.run_path(target, run_name="__main__")


if __name__ == "__main__":
    main()
