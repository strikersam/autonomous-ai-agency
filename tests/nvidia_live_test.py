#!/usr/bin/env python3
"""Live-test each NVIDIA NIM model candidate for availability and function calling.

This is an optional diagnostics script, NOT a pytest test. Run standalone with:
    python tests/nvidia_live_test.py

When imported by pytest (e.g. during collection), nothing executes — all logic is
guarded by `if __name__ == "__main__"`.
"""

import os
import json
import time
import sys


def test_nvidia_live_is_standalone_script():
    """pytest guard: this file is a standalone script, not a pytest test.
    Collection succeeds without running anything; the real logic lives in main()."""
    pass


def main() -> None:
    # ── Graceful skip when openai isn't available (CI doesn't install it) ──
    try:
        from openai import OpenAI
    except ImportError:
        print("SKIP: openai package not installed (run `pip install openai` to use this script)")
        sys.exit(0)

    nvidia_key = os.environ.get("NVIDIA_API_KEY", "")
    if not nvidia_key:
        print("SKIP: NVIDIA_API_KEY not set — no live endpoint to test against")
        sys.exit(0)

    client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=nvidia_key, timeout=15)

    models = [
        # Current candidates in NVIDIA_CANDIDATE_MODELS (verify these live)
        ("meta/llama-4-maverick-17b-128e-instruct", "Llama 4 Maverick (current primary)"),
        ("meta/llama-3.3-70b-instruct", "Llama 3.3 70B (tool-calling confirmed)"),
        ("nvidia/llama-3.3-nemotron-super-49b-v1", "Nemotron Super 49B"),
        ("nvidia/llama-3.1-nemotron-ultra-253b-v1", "Nemotron Ultra 253B"),
        ("qwen/qwen2.5-coder-32b-instruct", "Qwen2.5 Coder 32B"),
        # Previously listed / recommended models that were 404 or timeout
        ("qwen/qwen3-coder-480b-a35b-instruct", "Qwen3-Coder 480B (was in old list)"),
        # Additional recommended models from task brief
        ("minimax/mimo-v2-flash", "MiniMax M2.7"),
        ("mistralai/mistral-nemotron", "Mistral Nemotron"),
        ("mistralai/mistral-large-3-675b-instruct", "Mistral Large 3 675B"),
        ("moonshotai/kimi-k2-instruct", "Kimi K2 Instruct"),
    ]

    TOOLS = [{
        "type": "function",
        "function": {
            "name": "echo",
            "description": "Echo back the input",
            "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}
        }
    }]

    results = []
    for model_id, label in models:
        start = time.time()
        print(f"Testing {label} ({model_id})...", end=" ", flush=True)
        try:
            resp = client.chat.completions.create(
                model=model_id,
                max_tokens=50,
                tools=TOOLS,
                tool_choice="auto",
                messages=[{"role": "user", "content": "Say hello using the echo tool"}],
            )
            elapsed = time.time() - start
            msg = resp.choices[0].message
            has_tools = bool(msg.tool_calls)
            print(f"OK ({elapsed:.1f}s) tool_calls={has_tools}")
            results.append({"model": model_id, "label": label, "status": "OK", "elapsed": round(elapsed, 1), "tool_calls": has_tools})
        except Exception as e:
            elapsed = time.time() - start
            emsg = str(e)
            if "404" in emsg or "not found" in emsg.lower():
                status = "404_NOT_FOUND"
            elif "429" in emsg:
                status = "429_RATE_LIMITED"
            elif "timeout" in emsg.lower():
                status = "TIMEOUT"
            elif "422" in emsg:
                status = "422_UNPROCESSABLE"
            else:
                status = type(e).__name__
            print(f"FAIL: {status}")
            results.append({"model": model_id, "label": label, "status": status, "elapsed": round(elapsed, 1), "error": emsg[:200]})

    print("\n=== RESULTS ===")
    for r in results:
        print(f"  {r['status']:20s} {r['model']:55s} {r['label']}")


if __name__ == "__main__":
    main()
