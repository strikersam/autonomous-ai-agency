## Summary

Makes NVIDIA NIM cloud the default brain provider for agent execution, with a runtime toggle to switch to local Ollama.

### Changes

- **backend/server.py**: NVIDIA NIM priority -10 to 10, Ollama priority 0 to -10 (NVIDIA wins as default). Autonomy status now detects Ollama brain.
- **brain_policy.py**: Added `get_brain_preference()` from `BRAIN_PREFERENCE` env var. When "ollama", skips all cloud providers. Fixed `buil` typo.
- **webui/router.py**: `GET /admin/api/policy/brain` returns `brain_preference`. New `PATCH` endpoint toggles NVIDIA/Ollama without restart.
- **webui/providers.py**: `ensure_defaults` seeds NVIDIA priority=10, Ollama priority=0.
- **.env.example**: Documented `BRAIN_PREFERENCE`.
- **tests/test_autonomy_status.py**: Updated for Ollama brain detection.

### Toggle usage

```bash
# Switch to local Ollama (no restart needed):
curl -X PATCH http://localhost:8001/admin/api/policy/brain \
  -H "Authorization: Bearer <admin-token>" \
  -d '{"brain_preference":"ollama"}'

# Back to NVIDIA cloud:
curl -X PATCH ... -d '{"brain_preference":"nvidia"}'

# Permanent in .env:
BRAIN_PREFERENCE=ollama
```

Tests: 39/39 passing
