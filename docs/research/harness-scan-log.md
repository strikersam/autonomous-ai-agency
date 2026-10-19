# Agent-harness scan log

Weekly scan of open-source agent-harness repos. One row per repo reviewed, so later
scans skip it. Compared against `agent/harness_spec.py`, `agent/lessons.py`,
`agent/improvement_loop.py`, `agent/stuck_detector.py` and `agent/pr_gate.py`.

| Date | Repo | URL | Takeaway | Decision |
|------|------|-----|----------|----------|
| 2026-10-19 | google-research/harness2 | https://github.com/google-research/harness2 | Propose-Probe-Compose loop edits prompts/tools/memory per task; keeps adopted harnesses plus evidence-backed lessons. Our `harness_spec.py` already does cited, evidence-backed persistence; the probe step needs live model runs, so it is not deterministic. | skipped |
| 2026-10-19 | michaeltuszynski/harness-loop | https://github.com/michaeltuszynski/harness-loop | Run, mine failure traces, regression-gate, inject rule; promote only if no passing task breaks. Our spec promotes on repeat hits and retires on contradiction; a replay gate needs a task suite we do not have. | skipped |
| 2026-10-19 | iamabhishekmathur/LoopForge | https://github.com/iamabhishekmathur/LoopForge | Trace monitor to drafted patch to gate to PR, with confidence/evidence thresholds and rollback. Overlaps `improvement_loop.py` and `pr_gate.py`; 1 star, heavy. | skipped |
| 2026-10-19 | JinHo-von-Choi/anti-samcheonpo | https://github.com/JinHo-von-Choi/anti-samcheonpo | Hooks that hint then block on loops, test weakening, false completion. `stuck_detector.py` covers loops and `pr_gate._check_tests_not_weakened` covers weakened tests. Unadopted idea: hold source edits when one command fails twice with the same external cause (missing dependency, port conflict). | skipped |

## Not opened this run (seen in search results only, not reviewed)

LoopForge/harness-loop siblings `neosigmaai/auto-harness`, `ai-boost/awesome-harness-engineering`,
`RyanAlberts/best-of-Agent-Harnesses`, `omnigent-ai/omnigent`, `stacklok/mecatl`, `doc2harness`, `rax`.
Candidates for next week's scan.
