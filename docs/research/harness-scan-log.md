# Agent-harness scan log

Weekly scan of open-source agent-harness repos. One row per repo reviewed, so later
scans skip it. Compared against `agent/harness_spec.py`, `agent/lessons.py`,
`agent/improvement_loop.py`, `agent/stuck_detector.py` and `agent/pr_gate.py`.

| Date | Repo | URL | Takeaway | Decision |
|------|------|-----|----------|----------|
| 2026-10-19 | google-research/harness2 | https://github.com/google-research/harness2 | Propose-Probe-Compose loop edits prompts/tools/memory per task; keeps adopted harnesses plus evidence-backed lessons. Our `harness_spec.py` already does cited, evidence-backed persistence; its README demo (`harness2-demo`) runs deterministically without model credentials, but the real probe step on benchmarks needs live model runs (Vertex AI config, API costs), so adopting it is not deterministic. | skipped |
| 2026-10-19 | michaeltuszynski/harness-loop | https://github.com/michaeltuszynski/harness-loop | Run, mine failure traces, regression-gate, inject rule; promote only if no passing task breaks. Our spec promotes on repeat hits and retires on contradiction; a replay gate needs a task suite we do not have. | skipped |
| 2026-10-19 | iamabhishekmathur/LoopForge | https://github.com/iamabhishekmathur/LoopForge | Trace monitor to drafted patch to gate to PR, with confidence/evidence thresholds and rollback. Overlaps `improvement_loop.py` and `pr_gate.py`; 1 star, heavy. | skipped |
| 2026-10-19 | JinHo-von-Choi/anti-samcheonpo | https://github.com/JinHo-von-Choi/anti-samcheonpo | Hooks that hint then block on loops, test weakening, false completion. `stuck_detector.py` covers loops and `pr_gate._check_tests_not_weakened` covers weakened tests. Unadopted idea: hold source edits when one command fails twice with the same external cause (missing dependency, port conflict). | skipped |
| 2026-10-26 | vercel-labs/durable-harness | https://github.com/vercel-labs/durable-harness | Event-log durability: a crashed turn resumes from the log and a tool call that is not safe to repeat is never run twice. `checkpoint.py` restored state but did not say which executed calls must not be replayed. | adopted (`side_effecting_calls`, small helper; not wired into `loop.py`) |
| 2026-10-26 | JevAgentHarness/JevAgentHarness | https://github.com/JevAgentHarness/JevAgentHarness | Proxy that routes routine steps to a cheap model and hard steps to a strong one, and has the strong tier confirm "done". Needs a trained decision model and thresholds; our Verifier and router already gate completion. | skipped |
| 2026-10-26 | neosigmaai/auto-harness | https://github.com/neosigmaai/auto-harness | Failure-mining loop with a self-maintained regression suite and a best-score gate before each commit. Same replay-suite gap noted for harness-loop (no benchmark task suite here). | skipped |

## Not opened this run (seen in search results only, not reviewed)

LoopForge/harness-loop siblings `neosigmaai/auto-harness`, `ai-boost/awesome-harness-engineering`,
`RyanAlberts/best-of-Agent-Harnesses`, `omnigent-ai/omnigent`, `stacklok/mecatl`, `doc2harness`, `rax`.
Candidates for next week's scan. (2026-10-26: `neosigmaai/auto-harness` opened and logged above.) Also seen 2026-10-26, not opened: `EverMind-AI/Raven`, `aden-hive/hive`, `greyhaven-ai/autocontext`, `unifyai/unify-agent`, `Gloriaameng/Awesome-Agent-Harness`. No new harness2 follow-up repos turned up in a GitHub search.
