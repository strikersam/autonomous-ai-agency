"""
Shared NVIDIA NIM model list — single source of truth for all autonomous agent scripts.

Live-verified 2026-06-14 against https://integrate.api.nvidia.com/v1:
  Only 3 of 10 tested models are reachable and accept tool_choice="auto".
  Nemotron Ultra 253B, Qwen2.5 Coder 32B, Qwen3-Coder 480B, MiniMax M2.7,
  Mistral Nemotron, Mistral Large 3, Kimi K2 all 404/APIStatusError/BadRequest.

Ordered for agentic/tool-calling workloads:
  1. Nemotron Super 49B — confirmed tool_calls=True, fast (~1.5s), primary
  2. Llama 4 Maverick  — fast (~0.5s), accepts tools API, quality fallback
  3. Llama 3.3 70B    — confirmed tool_calls=True, reliable last resort
"""

# List of (model_id, human_label) tuples — used by implement_agent.py and
# apply_review.py which display the label in logs.
NVIDIA_CANDIDATE_MODELS: list[tuple[str, str]] = [
    ("nvidia/nemotron-3-super-120b-a12b",      "Nemotron-3 Super 120B (primary - reasoning MoE, ~12B active/call)"),
    ("nvidia/llama-3.3-nemotron-super-49b-v1", "Nemotron Super 49B (fast dense fallback)"),
    ("meta/llama-4-maverick-17b-128e-instruct", "Llama 4 Maverick (fast fallback)"),
    ("meta/llama-3.3-70b-instruct",            "Llama 3.3 70B (reliable last resort)"),
]

# Plain list of model_id strings — used by review_agent.py which iterates
# model IDs directly (no label needed for its simpler loop).
NVIDIA_MODEL_IDS: list[str] = [model_id for model_id, _label in NVIDIA_CANDIDATE_MODELS]

# Keep old name as alias for backward compatibility
CANDIDATE_MODELS = NVIDIA_CANDIDATE_MODELS
