---
name: model-catalogue-update
description: >
  Add, change or retire a model id in the routing catalogue. Use whenever a task
  touches config/models.yaml, config/llm/models.yaml, packages/ai/brain_config.py
  PROVIDER_CANDIDATES or presets, or packages/ai/cost_tracker.py prices — including
  the daily "new models" automation.
triggers:
  - adding a model to the catalogue or cost table
  - "new model released"
  - daily model automation
references:
  - tests/test_nvidia_default_model.py
  - tests/test_one_model_catalogue.py
  - config/models.yaml
---

# Model catalogue update

The catalogue decides what the agency routes to in production. A wrong id costs
every call that lands on it, so the rules below are not style.

1. **Check the retired list first.** `RETIRED` in `tests/test_nvidia_default_model.py`
   and the `removed …` / `(404)` / `(410)` comments in `config/models.yaml` name ids
   that failed live on this account. Do not re-add one. A vendor page saying the model
   exists is not evidence it answers here: #1695 (Nemotron 3.5 Lightning) and #1697
   (Llama 3.3 Nemotron Super 49B) both re-added retired ids from vendor docs and went red.
2. **Never duplicate a key.** Search the dict or YAML for the id before adding it;
   a duplicate silently overwrites the earlier entry (#1689).
3. **Unprobed means explicit-only.** A new id gets `priority: 99`, stays out of
   `PROVIDER_CANDIDATES` and every preset, and its cost entry says it is an estimate
   until a probe (`catalogue-probe.yml`) has seen HTTP 200 with a real completion.
4. **Mirror both configs.** `config/models.yaml` and `brain_config.py` must agree;
   `test_yaml_presets_mirror_brain_config` checks it.
5. **Prove it.** Run, and paste the summary line of:

   ```bash
   pytest -q tests/test_one_model_catalogue.py tests/test_nvidia_default_model.py tests/test_model_router.py
   ```

The pre-PR gate (`agent/pr_gate.py`) runs these suites whenever model config changes,
so an agent PR that breaks rule 1 or 2 does not open. This skill is the advisory half;
the gate is the deterministic half.
