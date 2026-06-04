# Roadmap — Next 180 Days

*Last Updated: 2026-06-04*

---

## Theme: Platform Maturity & Autonomous Scaling

### Month 4-5 — Platform Hardening

| Task | Priority | Effort |
|------|----------|--------|
| Migrate frontend from CRA to Vite | High | 3-4 days |
| Decompose `backend/server.py` (6,487 lines) | High | 5-7 days |
| Implement Redis-backed distributed rate limiting | Medium | 2 days |
| Add circuit breaker pattern to Ollama health check | Medium | 1 day |
| Add zero-downtime blue/green deployment | Medium | 2 days |
| Unify auth between proxy (port 8000) and backend (port 8001) | High | 3-4 days |
| Add parallel plan step execution in AgentRunner | Medium | 2 days |
| Implement adaptive context window management | Medium | 2 days |

### Month 5-6 — Autonomous Platform Features

| Task | Priority | Description |
|------|----------|-------------|
| **Self-healing CI** | High | Auto-fix CI failures using agent loop |
| **Dependency auto-update** | Medium | Weekly dependabot + auto-merge for patch updates |
| **Nightly security scan** | High | Automated CVE + SAST scan with issue creation |
| **Performance regression detection** | Medium | Baseline benchmarks, alert on >20% regression |
| **Coverage trend tracking** | Medium | Coverage badge + weekly report |
| **Agent telemetry dashboard** | Low | Grafana/Prometheus for agent execution metrics |

---

## Long-Term Vision (6 months)

### Multi-Tenancy
- Partition all storage by `company_id`
- Per-tenant rate limits and billing
- Tenant isolation at the agent workspace level

### Horizontal Scaling
- Replace in-memory state with Redis
- Stateless proxy instances behind load balancer
- Distributed agent execution queue

### Model Marketplace
- Dynamic model registry (add/remove models without restart)
- Model performance telemetry (latency, quality, cost per token)
- A/B testing for model routing strategies

### Developer Experience
- VSCode extension for local model selection
- CLI tool for key management
- OpenAPI-based client SDK generation

---

## Success Metrics (180 days)

- [ ] Frontend migrated to Vite (build time <5s)
- [ ] All god files decomposed (<800 lines each)
- [ ] Multi-tenant data isolation implemented
- [ ] Zero unhandled exceptions in production (Sentry)
- [ ] Coverage ≥80%
- [ ] Automated nightly security scans running
- [ ] Redis-backed rate limiting deployed
