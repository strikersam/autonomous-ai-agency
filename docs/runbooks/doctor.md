# Runbook: `make doctor`

Fast environment & CI-parity diagnostics — run it first whenever something
"didn't run" or CI disagrees with your laptop.

```bash
make doctor                 # report (always exits 0)
python scripts/doctor.py --strict   # exit 1 if a hard check FAILs
```

## What it checks and why

| Check | Why it matters |
|-------|----------------|
| **python** | CI runs **3.13**. A different local version is the #1 cause of "passes locally, fails in CI". |
| **env** | `API_KEYS` + an admin secret. Missing → backend boots in *limited mode* and auth-dependent tests skip/behave differently. |
| **deps** | `fastapi`/`pydantic`/`httpx` import. FAIL means the venv isn't set up (`pip install -r requirements.txt`). |
| **mongodb** | CI provides a `mongo:7` service; locally it's usually absent. Mongo-only tests run in CI, not on the laptop — expected divergence, not a bug. |
| **ollama** | Local model routing needs Ollama on `OLLAMA_BASE`. |
| **node** | Frontend test/build job needs Node (CI uses 20). |
| **git** | Current branch + uncommitted-change count. |

## Roadmap
This is the first slice of the claw-code-style doctor described in
`docs/architecture/agency-core-audit-2026-05-22.md`. Planned additions: runtime
doctor (`/runtimes/health`), GitHub/repo doctor, dashboard/API doctor, and a
`/api/doctor` endpoint surfaced in the UI.
