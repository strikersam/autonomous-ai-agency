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
    # Path-prefix guard: only patch when the executable path looks like the
    # JustVugg canonical layout (contains 'colibri' or a '/c/' or '\c\' segment).
    # Operators with a stray glm-test.exe elsewhere in PATH are not at risk.
    denylist = {
        tok.strip()
        for tok in os.environ.get("COLIBRI_PATCH_DENYLIST", "").split(",")
        if tok.strip()
    }
    path_ok = (
        "colibri" in exe_full
        or "/c/" in exe_full
        or "\\c\\" in exe_full
    ) and not any(tok in exe_full for tok in denylist)
    if (
        isinstance(args, list)
        and len(args) == 2
        and exe_basename in ("glm.exe", "glm")
        and path_ok
        and kw.get("stdin") is subprocess.PIPE
        and kw.get("stdout") is subprocess.PIPE
    ):
        outer = [
            t
            for t in sys.argv[1:]
            if t.split("=", 1)[0] in _FORWARD_FLAGS
        ]
        if outer:
            if os.environ.get("COLIBRI_PATCH_VERBOSE", "").lower() in (
                "1", "true", "yes",
            ):
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
    return _real_popen(args, *a, **kw)


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
