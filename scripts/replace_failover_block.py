#!/usr/bin/env python3
"""Replace the single-model failover block with the multi-model version."""
import re

with open('agent/loop.py', 'r') as f:
    content = f.read()

# Find the block from 'tried.add(provider.id)' to the final 'continue' before '# All providers exhausted'
# Use a regex to match the block
pattern = r'(            tried\.add\(provider\.id\)\n            # Resolve the model for this provider \(alias mapping\)\n            provider_model = fm\.resolve_model\(provider, model\)\n)            payload\["model"\] = provider_model\n\n            # Build the URL \+ headers for this provider\n.*?            continue\n\n        # All providers exhausted'

new_block = '''            tried.add(provider.id)
            # Resolve the model for this provider (alias mapping)
            provider_model = fm.resolve_model(provider, model)

            # Build the URL + headers for this provider
            chat_url = _openai_url(provider.base_url, "/chat/completions")
            headers = {"Content-Type": "application/json"}
            if provider.api_key:
                headers["Authorization"] = f"Bearer {provider.api_key}"

            # Try multiple models on this provider before giving up — when a
            # model returns 410 Gone (dead), try the next model. This handles
            # the case where NVIDIA_DEFAULT_MODEL points at a dead model.
            models_to_try = [provider_model] + [
                m for m in provider.models if m != provider_model
            ]
            for try_model in models_to_try[:3]:
                payload["model"] = try_model
                log.debug("brain_failover: attempt %d -> %s (model=%s)",
                           _attempt + 1, provider.id, try_model)

                call_start = time.perf_counter()
                try:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                        resp = await client.post(chat_url, json=payload, headers=headers)
                except Exception as exc:
                    last_error = f"{provider.id} network error: {exc}"
                    log.warning("brain_failover: %s network error: %s", provider.id, exc)
                    fm.record_failure(provider.id, "network_error")
                    break

                last_resp = resp
                call_ms = int((time.perf_counter() - call_start) * 1000)

                if resp.status_code < 400:
                    fm.record_success(provider.id, latency_ms=call_ms)
                    data = resp.json()
                    out_text = data["choices"][0]["message"]["content"]
                    if self.email:
                        usage = data.get("usage", {})
                        pt = int(usage.get("prompt_tokens") or 0)
                        ct = int(usage.get("completion_tokens") or 0)
                        try:
                            from langfuse_obs import emit_chat_observation
                            await asyncio.to_thread(
                                emit_chat_observation,
                                email=self.email,
                                department=self.department or "agent",
                                key_id=self.key_id,
                                model=try_model,
                                messages=messages,
                                output_text=out_text,
                                prompt_tokens=pt,
                                completion_tokens=ct,
                                latency_ms=call_ms,
                                task_name="agent-task",
                            )
                        except Exception as exc:
                            log.debug("Agent Langfuse emit failed: %s", exc)
                    return out_text

                if resp.status_code == 410:
                    log.warning("brain_failover: %s model %s 410 Gone - trying next model",
                               provider.id, try_model)
                    continue

                if resp.status_code in (429, 419):
                    last_error = f"{provider.id} {resp.status_code} rate-limited"
                    fm.record_failure(provider.id, "rate_limited", resp.status_code)
                    break

                if resp.status_code >= 500:
                    last_error = f"{provider.id} {resp.status_code} server error"
                    fm.record_failure(provider.id, "server_error", resp.status_code)
                    break

                last_error = f"{provider.id} {resp.status_code}: {resp.text[:200]}"
                log.warning("brain_failover: %s model %s returned %d - trying next model",
                           provider.id, try_model, resp.status_code)
                continue
            else:
                fm.record_failure(provider.id, "all_models_failed")
                continue

        # All providers exhausted'''

result = re.sub(pattern, new_block, content, flags=re.DOTALL, count=1)
if result == content:
    print("ERROR: pattern not found")
    # Try to find what's different
    import re as re2
    m = re2.search(r'tried\.add\(provider\.id\)', content)
    if m:
        print(f"Found 'tried.add' at position {m.start()}")
        print(f"Context: {content[m.start():m.start()+100]}")
else:
    with open('agent/loop.py', 'w') as f:
        f.write(result)
    print("SUCCESS: replacement done")
