/**
 * agency-provider.ts — routes Prime Agent's LLM traffic back through this
 * platform's own OpenAI-compatible proxy.
 *
 * The CLI has no base-URL environment variable; registering a provider from an
 * extension is the only supported way to point it at an arbitrary endpoint.
 * Without this file the CLI would fall back to whatever provider keys happen to
 * be in the environment, bypassing packages/ai/router.py — losing failover, the
 * brain watchdog, and cost accounting, and violating CLAUDE.md §3.
 *
 * Load it with:  prime-agent --extension /path/to/agency-provider.ts --provider agency
 *
 * Environment:
 *   AGENCY_PROXY_URL     Base URL of the proxy (default http://localhost:8000),
 *                        the same variable agent/agency.py already uses.
 *   PROXY_API_KEY        Bearer token. Interpolated by the CLI from "$PROXY_API_KEY"
 *                        at request time — the key itself never appears in this file.
 *   PRIME_AGENT_MODELS   Comma-separated model ids the proxy serves.
 *   PRIME_AGENT_CONTEXT_WINDOW / PRIME_AGENT_MAX_TOKENS   Optional overrides.
 */

const DEFAULT_MODELS = "meta/llama-3.3-70b-instruct";

function intFromEnv(name: string, fallback: number): number {
  const parsed = Number.parseInt(process.env[name] ?? "", 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}

export default function (pi: any): void {
  const base = (process.env.AGENCY_PROXY_URL ?? "http://localhost:8000").replace(/\/+$/, "");
  const contextWindow = intFromEnv("PRIME_AGENT_CONTEXT_WINDOW", 128000);
  const maxTokens = intFromEnv("PRIME_AGENT_MAX_TOKENS", 8192);

  const models = (process.env.PRIME_AGENT_MODELS ?? DEFAULT_MODELS)
    .split(",")
    .map((id) => id.trim())
    .filter(Boolean)
    .map((id) => ({
      id,
      name: `${id} (agency proxy)`,
      reasoning: false,
      input: ["text"] as ("text" | "image")[],
      // Cost is accounted for on the proxy side; reporting zero here keeps the
      // CLI from double-counting spend we already track.
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0 },
      contextWindow,
      maxTokens,
    }));

  pi.registerProvider("agency", {
    name: "Autonomous AI Agency (proxy)",
    baseUrl: `${base}/v1`,
    apiKey: "$PROXY_API_KEY",
    api: "openai-completions",
    authHeader: true,
    models,
  });
}
