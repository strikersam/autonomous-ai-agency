# Graph Report - local-llm-server  (2026-08-13)

## Corpus Check
- 1429 files · ~2,048,539 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 28408 nodes · 57107 edges · 1158 communities (1044 shown, 114 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 6298 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `75637039`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- backend/server.py
- ProviderConfig
- AgentScheduler
- _fixture
- company_api.py
- TaskSpec
- SQLiteStore
- FeatureMaturity
- Specialist
- proxy.py
- llm/router.py
- ScheduledJob
- FeatureMatrix
- test_llm_router_strategies.py
- PortfolioManager
- test_operational_incidents.py
- TaskHarnessAdapter
- Usage
- AgentSessionStore
- skill_bindings.py
- api.js
- LLMRequest
- TaskStore
- test_llm_router_queue_cache.py
- ProviderManager
- MCPUnavailableError
- test_ceo_micromanager.py
- RenderOpsMonitor
- SelfHealingAgent
- ExecutionRequest
- test_governance_sandbox.py
- services/background.py
- Initiative
- WorkflowRun
- ImprovementLoop
- test_unit8_model_catalog.py
- MCPClient
- KeyPool
- test_llm_router_resilience.py
- HermesAdapter
- WebsiteScanner
- resolve_active_brain
- direct_chat.py
- test_phase6_workflow.py
- KeyStore
- brain_config.py
- FreeBuffAgent
- AgentRunner
- SeoAuditRequest
- get_runtime_manager
- RenderFinding
- CompanyGraphStore
- test_failover_client_shared.py
- PrimeAgentAdapter
- test_user_research_skill.py
- CEODispatcher
- test_ceo_dispatcher.py
- Task
- MultiAgentSwarm
- test_model_router.py
- tasks/service.py
- NotificationDispatcher
- test_knowledge_sync.py
- FailureCategory
- test_runtime_governance.py
- test_startup_warmup.py
- test_ceo_supervision.py
- DashboardLayout.js
- BrainWatchdog
- TasksPage.js
- test_governance_enforcement.py
- workflow/api.py
- get_user_role
- detector.py
- AgentSwarm
- setup/api.py
- enforcement.py
- HybridSystem
- ResearchTask
- test_model_catalog.py
- brain_failover.py
- _ts_to_float
- WebReach
- resolve_e2b_config
- TestClient
- test_ai_insights.py
- test_repo_connection.py
- resolve_identity
- ModelRouter
- ProceduralMemoryStore
- Troubleshooting
- ChatPage.js
- FetchResult
- test_bedrock_provider.py
- TestClient
- ControlPlanePage.js
- SecretRecord
- test_colibri_brain_shim.py
- test_governance_api.py
- seo_api.py
- AdaptiveHalter
- FinancialMetrics
- LogWatcher
- AgileSprint
- Agent
- failover_client.py
- StreamingDeltaReconstructor
- tasks/api.py
- get_task_store
- Platform Guide — the full tour
- DetectedSystem
- SeoFixer
- Page
- TokenBudget
- KnowledgeGraph
- V5App.jsx
- ai_runner.py
- test_sqlite_store.py
- test_control_plane_api.py
- ProvidersScreen.jsx
- config.py
- probe_model_liveness
- _scanner
- RewardScorer
- Command
- CoworkSession
- _get_provider_policy
- useSafeData
- test_context_rulebook.py
- ArtifactStore
- WorkflowEngine
- CEOSupervisor
- test_provider_state_durability.py
- InferenceCache
- ToolRegistry
- CheckpointStore
- RepowiseIntelligence
- test_sam_voice.py
- Feature Guide
- _resolve_brain_provider
- test_issue_intake.py
- test_kimi_bridge_server.py
- AutonomyTracker
- ReactScratchpad
- diagnostics.py
- audit
- GoalRecord
- ChatHistoryStore
- WorkspaceManager
- api.ts
- test_telegram_freebuff.py
- AGENTS.md — Source of Truth for All AI Agents
- LLMRouter
- BackgroundAgent
- test_portfolio_intake.py
- persist_plan_spec
- CLAUDE.md — Master Architect Operating Manual
- test_response_cache.py
- telegram_bot.py
- test_agent_runner.py
- WorkspaceTools
- test_slop_gate.py
- _StubProvider
- Settings
- activation_api.py
- render_ops.py
- test_agent_tool_governance.py
- AgentProfile
- MetricsRegistry
- test_e2b_task_wiring.py
- OnboardingScreen.jsx
- OllamaCircuitBreaker
- SetupChecker
- PromptCacheManager
- test_quick_note.py
- test_trend_scoping.py
- test_audit.py
- get_failover_manager
- [Unreleased]
- [Unreleased]
- test_integration_c4_c5_c6_d3.py
- test_agent_free_brain.py
- HealthStatus
- WorkflowBuildRequest
- test_features_api.py
- test_video_transcript.py
- activation.py
- facade.py
- emit_chat_observation
- Part A — CodeRabbit review fixes for this PR (do first, small)
- Docker Agent Runtimes Setup
- anthropic_compat.py
- TestPayloadNormalisation
- RuntimeManager
- test_workspace_isolation.py
- FilterResult
- v4_api.py
- README.md
- Persistent Memory System
- resolve_component_model
- JCodeAdapter
- analyze_page
- .get_workspace
- TrendWatcher
- AgileManager
- BudgetTracker
- compare_runtimes.py
- ContextWindowManager
- Any
- test_e2b_data_flow.py
- test_trend_watcher.py
- OrchestratorSupervisor
- Kept Rules — the 44 that survive the audit
- getBackendUrl
- policy.py
- test_schedule_backlog_drain.py
- _run
- AgentJobError
- KnowledgeScreen.jsx
- TestEstimateTokensForMessages
- AuditLog
- TestClient
- PatternConsolidation
- traffic_director.py
- ServiceDaemon
- TaskDispatcher
- ContextPruner
- test_freebuff.py
- test_backend_server_features.py
- sync/service.py
- _Collection
- DecisionsStore
- GitHubTools
- PlaybookLibrary
- test_verification_strategies.py
- ApprovalStore
- REWRITE_PLAN.md — Phased Migration Strategy
- test_background_services.py
- OrchestratorQueue
- test_all_providers_discovery.py
- test_persistent_memory.py
- SpecEntry
- IssueCategory
- SecurityScanner
- get_registry
- test_anthropic_router.py
- test_llm_router_e2e.py
- report_to_markdown
- agent_runtime.py
- ENGINEERING_STANDARDS.md — Coding, Security & Testing Standards
- DashboardScreen.jsx
- context_rules.py
- test_platform_controls.py
- local_controller.py
- test_live_server.py
- ContextCompressor
- ContextManager
- loop.py
- SparkProvider
- ResourceWatchdog
- agents/api.py
- chat_handlers.py
- Workspace
- RateLimitTracker
- Screens
- test_daily_2026_06_04.py
- test_microagents.py
- Security Analysis — local-llm-server
- Langfuse Observability Guide
- v3_models.py
- v3_auth.py
- test_failover_silent_exhaustion.py
- DigestSummary
- TestDiagCommand
- StuckDetector
- High-Agency Frontend Skill
- test_ceo_router.py
- TestNormalizeResponseFormat
- Quick-Note GitHub Issues Processing - Session Summary
- test_rate_limiter.py
- CacheManager
- test_brain_failover.py
- TestRecordUsageAndStats
- test_mcp_governance.py
- test_purge_backlog.py
- tests/test_browser.py
- test_freebuff_bot.py
- fmtErr
- settings.py
- RuntimeHealthService
- switch_brain.py
- SyncService
- AgentDirective
- test_autonomy_gate.py
- test_rag_context.py
- ProjectScaffolder
- Configuration Reference
- test_p0_roadmap_a4_a5_b2.py
- ModelConfig
- test_pr923_fixes.py
- PriorityTaskQueue
- SteeringInjector
- test_phase4_runtime_resilience.py
- test_claude_setup_audit.py
- test_scheduler_hydration_bounded.py
- test_internal_agent_did_work.py
- test_schedule_growth_invariants.py
- LessonStore
- TerminalPanel
- Python Dependencies (`requirements.txt`)
- Technical Debt Register — local-llm-server
- llm_providers.py
- TrafficDirector
- BrainFailoverManager
- test_crispy_burn_in.py
- test_provider_enable_disable.py
- test_skill_registry_boot_refresh.py
- test_memory.py
- analyze_qualitative
- SprintMetrics
- Deploy: FreeBuff Telegram bot (24×7)
- Claude Code + Qwen Local Setup
- generate_context.py
- test_brain_availability_doctor.py
- _is_dns_failure
- isolated_telegram_config
- validate_outbound_url
- webui/frontend/package.json
- Performance Analysis — local-llm-server
- LLM Router — troubleshooting
- SeoAuditReport
- control_registry.py
- keepalive.py
- monitor_lib.py
- test_telegram_approval_e2e.py
- test_v3_auth.py
- TestWorkflow
- HarnessEnrichment
- test_unit7_catalog_propagation.py
- dependencies
- reset_store
- Session Handoff — 2026-06-15
- TASK 4 — End-to-end approval-gate test
- mcp_dispatch
- Any
- test_north_mini_code.py
- ClaudeCodeAdapter
- AgentMessageBus
- CompanyAgencyService
- TemporalContextGraph
- test_daily_automation_2026_08_03.py
- TestClassifyPlainText
- test_sam_livekit.py
- test_service_token.py
- github_tools.py
- app_settings.py
- Findings
- Local AI Stack with Docker
- Traffic Distribution Across Providers
- Implementation Prompt: Rich TaskBoard + Agile Sprint Integration
- Telegram Bot Setup
- SchedulesPage.js
- RuntimesPage.js
- video_transcript.py
- control_overrides.py
- distributed.py
- CollectionLike
- test_regression.py
- test_agency_fix.py
- test_output_filter.py
- test_telegram_mutating_commands.py
- test_workspace_security.py
- refine
- platform_controls_router.py
- Agent Governance Guide
- The fifteen strategies
- ServiceManager
- _Cursor
- WindowsServiceManager
- SyntheticDataPipeline
- test_all_features.py
- _get
- TestBrainConfigUpdates
- test_monitor_lib.py
- Path
- test_mostly_failed_steps.py
- test_v4_api.py
- LocalWorkspace
- classify_direct_chat_intent
- ._connect
- timedelta
- test_dashboard_cache.py
- Harness
- _process_task_callback
- test_portfolio_intelligence.py
- TestRenderMCPSidecarService
- _P
- test_voice.py
- CollaborationContext
- model_discovery.py
- _resolve_user_github_token
- V3 API Migration Plan — LLM Relay Platform
- AppShell.jsx
- PortfolioScreen.jsx
- allow_paid
- test_chat_mode_regressions.py
- system_instruction
- daily_digest.py
- GuardrailEngine
- test_issue_triage.py
- NIMConnectionPool
- weekly_digest.py
- test_local_controller.py
- run_trend_analysis
- test_unit5_ui_provider_surface.py
- MemoryCategory
- test_permissions.py
- PersistentMemoryStore
- Skill: modularity-review
- Design Audit
- Findings
- TestRenderRouter
- Skill: modularity-review
- crispy_client.py
- 4. Troubleshooting
- Docker AI Governance Audit — Final Report
- 1. Capability-by-capability
- 4. Threats
- Dynamic Model Routing
- ControlsScreen.jsx
- output_filter.py
- compilerOptions
- HarnessRegistry
- APIClient
- Page
- test_backend_runtime_bootstrap.py
- test_llm_router_tpm.py
- test_tasks_cache_ttl_env.py
- test_voice_pipeline.py
- TestUpdateTask
- MemoryKernel
- harness_spec.py
- test_loop_registry.py
- _extract_tech_relevance
- agile_api.py
- Skill: fabric-patterns
- Analysis & Synthesis Instructions
- Production Readiness Assessment — local-llm-server
- Skill: fabric-patterns
- db/__init__.py
- Admin Dashboard Guide
- Implementation Plan
- ProviderConsole.jsx
- Delegation Plan (agent-ready work packages)
- build_workflow.py
- ProviderCircuit
- test_brain_patch_service_token.py
- TestBrainFailoverModelUpdates
- test_fabric_patterns.py
- test_repowise_intelligence.py
- test_schedule_persistence.py
- TestOrchestratorEndpointScoping
- validate_session_id
- sam_livekit_worker.py
- ErrorInterceptorMiddleware
- ScheduleStore
- CapacityAllocation
- Comprehensive Skill Index (By Category)
- Agent Skill: Principal UI/UX Architect & Motion Choreographer (Awwwards-Tier)
- Component Map
- Agent State — colibri GLM-5.2 deployment (resumable)
- Architecture Overview — local-llm-server
- Pending Activities — Implementation Playbook
- The rules
- Part A — Health Report
- apply_review.py
- infra_cost.py
- build_matrix
- asyncio
- agency_fix.py
- sync_readme_gallery.py
- CircuitBreakerOpenError
- test_skill_executors_live.py
- TrainingSample
- LocalLLMSetup
- test_company_api.py
- TestStopSlopChecker
- handle_workflow_ide_chat
- TestHelpers
- SKILL: Industrial Brutalism & Tactical Telemetry UI
- Skill: data-quality-audit
- What "Slop" Looks Like
- test_admin_local_brain_router.py
- local_brain_router.py
- cost_tracker.py
- Section-by-Section Acceptance Criteria
- Migration Notes
- McpCard.jsx
- provider_max_rpm
- redact_connection_url
- SQLiteStore
- agent_readiness_audit.py
- test_ci.sh
- claim
- test_shared_state.py
- ._coerce_ts
- test_activation_api.py
- test_daily_automation_2026_07_11.py
- test_health_endpoints.py
- test_keepalive.py
- test_openclaw_endpoints.py
- TestRoutes
- hermes_prompt.py
- MemoryMiddleware
- ._fetch_flat_skill_file
- AITellIssue
- Skill: repowise-intelligence
- ARCHITECTURE.md — Target Architecture
- Skill: repowise-intelligence
- The 10-Step Workflow
- Contributing to local-llm-server
- CEO Micro-Management
- 467 Brutal Audit — File-by-File Status
- Runbook — Apply the Fast Free NVIDIA Brain to Render (TASK 2)
- implement_agent.py
- test_agent_chat_integration.py
- PersistentQueue
- fabric_cli.py
- sync_ngrok.py
- reap_expired_companies
- test_p0_roadmap_b3_b4_b5.py
- GuardResult
- ManagedAgentDreams
- shared_state.py
- _resolve_push_token
- test_autonomy_status.py
- test_brain_failover_413.py
- test_dockerfile_ships_root_modules.py
- test_frontend_deployment_guards.py
- test_glm52_brain.py
- test_langfuse_agency_wide.py
- test_local_brain_state.py
- TestMCPServer
- TestChatHistoryStore
- test_phase5_doctor.py
- test_telegram_diag_endpoint.py
- TestCheckKwargs
- audit_drift
- .build
- Skill: agent-harness
- Skill: checkpoint-strategy
- Process
- Skill: local-ai-query
- Skill: parallel-agents
- Skill: parallel-worktrees
- Design System: Taste Standard
- Process
- .get_state
- Skill: user-research
- Agency Core — Progress & Resume Log
- test_daily_2026_07_24.py
- _push_down_where
- router/health.py
- test_telegram_auto_approve.py
- clear_wizard_state_cache
- e2e/test_browser.py
- ._sprint
- TestGetCurrentTimeTool
- TestModelRegistryUpdates
- test_dockerfile_ships_config_dir.py
- _run
- test_scanner_live.py
- _TFIDFIndex
- ._resolve_path
- StopSlopChecker
- Process
- Skill: lr-schedule-advisor
- Instructions
- Instructions
- Process
- Checks Performed
- Skill: training-stability-monitor
- monitor_colibri.py
- admin_digest_router.py
- Skill: branch-cleanup
- Skill: perplexity — Web Research via Perplexity API
- Instructions
- Instructions
- Quick-Note Issues Processing Summary
- Implementation Plan — DB-persisted, UI-switchable Brain (no redeploy)
- Backend changes
- Render MCP — autonomous platform debugging and environment monitoring
- Runbook: Auto-Resume After Cooldown / Interruption
- SEO / GEO / AIO Audit Engine
- devDependencies
- overrides
- _parse_reset_epoch
- ai/registry.py
- .add_specialist
- _RedisBackend
- cmd_autonomy
- test_critical_flows.py
- test_autonomy_pipeline_regressions.py
- test_brain_priority_scanner.py
- TestWorkspace
- test_openclaw_gateway.py
- TestDisabledReasonRendering
- TestCrawl
- test_workflow_models.py
- get_tool_registry
- loop_readiness
- ._connect
- Process
- Skill: Brain Dump
- Process
- Instructions
- Skill: duplicate-thread
- Skill: Email Triage
- Process
- Process
- Skill: graphify — Knowledge Graph Token Optimization
- Skill: prompt-library
- Skill: prompt-transparency
- Skill: Research
- Skill: scope-guard
- test_new_features_e2e.py
- admin_update_task_router.py
- ProviderManager
- Instructions
- Skill: graphify — Knowledge Graph Token Optimization
- Skill: platform-setup — Autonomous Agency Bootstrap
- Device compatibility and model picks
- Autonomy Uplift — Living Roadmap & Detailed Implementation Specs
- OpenClaw — iOS Control of the Agency (Single-Service Free-Tier Deploy)
- rules
- _Budget
- Summary
- Agent Transparency Report
- update_provider_policy
- .publish
- _InMemoryBackend
- TestModelCostTableUpdates
- TestDecisionsBotLinks
- test_deploy_trigger_covers_image.py
- test_doctor_service_token_check.py
- TestRouterIntegration
- WorkspaceManifest
- CLAUDE.md — agent/
- skill_registry.py
- RegistrySkill
- Trajectory
- Instructions
- Instructions
- Process
- Instructions
- Skill: system-prompt-audit
- Skill: task-alive-updates
- Process
- Instructions
- LocalBrainStore
- .create_company
- 14. Standing Instructions — Universal Agent Discipline
- Skill: agent-browser — Real Chrome Browser Automation
- Instructions
- Instructions
- Skill: dev-browser — Browser Automation via Sandboxed JS
- Instructions
- Agent Orchestration Design
- Universality: case-coverage matrix
- Workspace Isolation Architecture
- Quantization Internals
- Implementation — DB-persisted, UI-switchable Brain (PR #824 follow-up)
- 2. Pending ⬜ — detailed implementation specs
- 467 Public Site Truth Spec
- extract_refusal
- TestRequireAdmin
- check_container_posture.py
- Kimi Web-Bridge Service
- test_agile_api.py
- test_app_settings.py
- test_providers_live_e2e.py
- test_skill_registry.py
- TestAnthropicPayloadStructuredOutput
- test_task_clarification.py
- validate_job_id
- EvalHarness
- _keyword_search
- _extractive_compress
- Instructions
- Skill: pro-workflow
- Instructions
- Instructions
- Skill: resource-panel
- Skill: sandboxed-exec
- Workflow
- ECC Harness Patterns Skill
- Instructions
- Instructions
- Stop-Slop Quality Skill
- Agency Core — Ruthless Architecture Audit & Migration Plan
- AUTONOMY_CHARTER.md
- Tailored Onboarding, Editable Companies & Dynamic Roles
- Issue #467 — Section 1: Pulled State + PR Inventory
- Autonomy Charter — Telegram-Gated Self-Running Agency
- Context: Agentic Agile + Portfolio Management
- Deploy to Google Cloud Run
- Key Components
- Sampling Strategies Internals
- LLM Router — architecture
- Killer TODO Roadmap — local-llm-server
- NVIDIA NIM — Free Tier Setup
- What to clean up
- Worker Service — Operations Runbook
- test_bedrock_live.py
- run_proxy.sh
- ._db
- setup_ngrok.py
- test_empirical_verify.py
- test_google_provider_models.py
- get_livekit_config
- test_tasks_awaiting_approval_api.py
- verify_token
- task.py
- Instructions
- Protocol: Premium Utilitarian Minimalism UI Architect
- The 5-Step Wrap-Up Ritual
- ._check_permissions
- TestNormalizeToolChoice
- Agent: Reviewer (Verifier)
- Skill: Agentic Agile
- Skill: browserbase-ui-test — Adversarial UI Testing
- Skill: financial-analyst (Agentic CFO)
- Graphiti Temporal Context Skill
- Skill: seo-audit-report
- ADR-008: LLMRouter — the single multi-provider routing gateway
- Core Pillars
- 467 Golden Path — Locked Implementation Order
- Attention Mechanisms Internals
- LLM Router — configuration guide
- LLM Router — provider guide
- CI Troubleshooting Runbook
- OutputFilter
- CerebrasProvider
- build_tech_db.py
- main
- run_bot
- Dream
- TestExtendedThinkingRouting
- TestZeroAttemptDiagnostics
- TestSessionMemory
- TestParsing
- test_quick_note_engine.py
- _FakePersistence
- TestRevenuePortfolio
- ._make_run
- synthesize
- BenchmarkReport
- rag_context.py
- _extract_workflow_relevance
- Skill: changelog-enforcer
- Skill: learn-rule
- Instructions
- Any
- prompts/README.md
- Skill: Agentic Portfolio Management
- Skill: changelog-enforcer
- Skill: cowork-session (Claude Cowork)
- Skill: video-context — read a video without watching it
- Decision
- ADR 003: Multi-Agent Orchestration with Plan-Execute-Verify Loop
- Main proxy (`proxy.py`)
- Autonomous SDLC Loop (Agency Core, repo-agnostic)
- The 8-Step Golden Path
- PR #634 Implementation Tracker
- KV Cache Internals
- Platform Controls
- Release Procedure
- V2.0 Modernization — Runbook
- Setup
- frontend/package.json
- AgentStatusPanel.tsx
- AgentStatusPanel.jsx
- ToolCallViewer.tsx
- _get_current_user
- apply_overrides
- cleanup_stale_jobs
- enrich_quick_note_issues.py
- _status_snapshot
- TestSwarmRoleRouting
- test_backend_requirements_cover_runtime_imports.py
- test_changelog_parity_guard.py
- Path
- _StubManager
- TestGithubSignalHardening
- FakeScheduleCollection
- test_scanner_deps_parity.py
- stt.py
- LoopSpec
- navigation_metrics.py
- _score_turns
- TrajectoryStep
- quality_checker.py
- Skill: docs-sync
- Agent: Implementer (Executor)
- Agent: Judge (Release / QA Gate)
- Agent: Planner (Architect)
- Skill: browserbase-browser — Real Browser Automation
- Skill: docs-sync
- Skill: memory-consolidation (Dream Memory)
- GitHub Branch Protection Settings
- ADR 001: Self-Hosted OpenAI-Compatible Proxy
- ADR 002: Dynamic Model Routing with Task Classification
- AGENTS.md — AI Agent Configuration for local-llm-server
- Advisor Strategy — Local Proxy Handling
- ceo-micromanagement.md
- Feature Maturity / Support Matrix
- Web UI + Admin (Claude Code–style)
- 467 Skill Inventory — load / wire / test status
- Free NVIDIA brain + UI-controlled provider policy + no silent spend
- Issue #362: Nvidia repo setup
- Issue #364: quick-note:https://www.marktechpost.com/2026/06/01/meet-memory-os-a-6-layer-open-source-memory-stack-built-on-top-of-hermes-agent/
- Issue #378: quick-note:https://www.marktechpost.com/2026/06/02/tinyfish-launches-bigset-an-open-source-multi-agent-system-that-builds-structured-live-datasets-from-plain-english-descriptions/
- Issue #379: quick-note:https://searchengineland.com/schema-markup-optimize-agentic-web-479080
- Issue #380: quick-note:https://cursor.com/blog/cloud-agent-lessons
- Issue #381: quick-note:https://www.xda-developers.com/claude-code-with-opus-48-is-expensive-but-i-made-it-efficient-with-my-local-ai-workflow/
- Issue #382: quick-note:https://claude.com/blog/how-coderabbit-used-claude-to-build-an-agent-orchestration-system
- Issue #383: quick-note:https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/
- Issue #416: feat: Self-hosted Codebuff (freebuff) on free NVIDIA models + Telegram bot phone control
- Issue #485: [Trend Digest] Week of 2026-06-08
- Issue #488: quick-note:https://github.com/cookiy-ai/user-research-skill
- Issue #491: Implement whatever is necessary from https://github.com/BehiSecc/awesome-claude-skills
- Issue #493: Use the https://github.com/mvanhorn/last30days-skill skill to get the trend updated
- Issue #495: Read https://www.anthropic.com/news/claude-fable-5-mythos-5 and understand if mythos or fable can be added to the repo
- Issue #504: EPIC: Autonomy hardening — live-verified defects 2026-06-10
- Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass
- Issue #656: Bugs
- Issue #657: quick-note:https://github.com/earendil-works/pi
- Issue #659: quick-note:https://github.com/nex-agi/Nex-N2
- Issue #660: quick-note:https://github.com/getsentry/sentry-for-ai
- Issue #661: quick-note:https://github.com/XiaomiMiMo/MiMo-Code
- Issue #664: quick-note:https://github.com/Grominet95/jarvis-OS
- Issue #666: quick-note:https://github.com/porokka/jarvis-os
- Issue #670: quick-note:https://github.com/perplexityai/bumblebee
- Issue #672: quick-note:https://github.com/Chachamaru127/claude-code-harness
- Issue #676: quick-note:https://github.com/WeiboAI/VibeThinker
- Issue #820: quick-note:https://github.com/cobusgreyling/loop-engineering
- Positional Encoding Internals
- TOP 6 — Highest-ROI Items (Validated by Opus Research Agent)
- SECTION A — Agent Efficiency (Hermes / AOS / MYT)
- SECTION C — Direct Chat Improvements (CBF / HRM)
- Runbook — Instance Activation
- Prime Agent Runtime
- PULL_REQUEST_TEMPLATE.md
- fetch_url.py
- Event
- capture_screens.py
- Prompt Library
- CLAUDE.md — router/
- crispy_burn_in.py
- run_patched_colibri.py
- SessionMemory
- test_compose_and_coordinate_api.py
- TestHarnessRegistry
- test_local_brain_router_smoke.py
- test_ping.py
- TestRunCoroSync
- test_provider_models_db_outage.py
- test_runtimes_health_endpoint.py
- start_in_process
- TestCatalog
- test_serve_spa_prefixes.py
- test_task_store_fails_loud_in_production.py
- dry_clone_repo
- TOOLS.md — Available Tools for AI Agents
- Task
- SIA
- Full-Output Enforcement
- summarise.sh
- updater.py
- ModelRegistry
- AI Engineering Insights Skill
- Skill: hybrid-reasoning (Hybrid AI)
- Karpathy Guidelines Skill
- Skill: Managed Agents Dreams
- Skill: Multi-Agent Coordinator
- Skill: Obsidian Knowledge Graph
- Multi-Agent Research Coordinator Skill
- Skill: SuperClaude Slash Commands
- Skill: SuperClaude Workflow Engine
- Active Task Tracker
- _AllSignatures
- ADR-006: Strangler Fig migration with backward-compat shims
- claude-mem Plugin — Persistent Memory for All Sessions
- Implementation plan + TO-DO (check off as you go)
- Topics Covered
- LLM Router — migration guide
- Cloudflare = the real working app
- production
- launch-claude-code.sh
- PRD — README Marketing Refresh
- get_control
- check_changelog_parity.py
- e2e_smoke.py
- BackgroundServices
- task_runner.py
- client
- TestDashboard
- test_daily_2026_06_14.py
- test_doctor_coding_brain.py
- test_domain_specialists.py
- TestGithubTokenSQLiteRegression
- test_schedule_store_create_index_options.py
- TestTechSkillMap
- TestActiveStrategy
- /fix-bug — Bug Fix Agent
- Command: /plan
- pre-commit
- Skill: browserbase-fetch — Lightweight Web Fetch
- Twitter Insights — Issue #228
- Twitter Insights — Issue #231
- OpenAI Codex CLI — Local LLM Server Config
- ADR-001: Adopt packages/ directory structure
- ADR-002: Centralize configuration in packages/config/
- ADR-003: Provider abstraction with unified interface
- ADR-004: Event bus for loosely coupled communication
- ADR-005: Merge Hermes into the main backend service
- ADR-007: Storage backend duck-typing over formal ABC
- Phases
- 5. The five autonomous loops
- Master Goal Prompt — Autonomous Agency CEO
- Agency Core — Operational Knowledge (verified live, 2026-06-10/11)
- Pre-Mortem Analysis: Agency Core autonomy story (Cloudflare deployment)
- SECTION B — NVIDIA / Cloud Model Integration (Nemotron / NVD)
- SECTION D — Deployment & Infrastructure (CHM / NVD)
- RelayShowcasePage.js
- resolve_hermes_base_url
- apply_phase1_changes.py
- _replace
- check_doc_images.py
- gen_screenshots.py
- gen_v4_screenshots.py
- setup-claude-code.sh script
- TestRuntimes
- Report
- TestCompany
- PhaseSequenceError
- test_generate_context_standing_instructions.py
- TestCitationBinding
- _auth_headers
- _normalize_dockerfile
- TestDelegationPlan
- test_version_consistency.py
- webui/commands.py
- harness.py
- heartbeat.sh
- loops_overview
- /arch-review — Architecture Agent
- /devops-check — DevOps Agent
- /docs-update — Documentation Agent
- /qa-check — QA Agent
- Command: /review
- /security-audit — Security Agent
- pre-push
- Skill: browserbase-search — Structured Web Search
- Issue #230 — DUPLICATE
- python_client_example.py
- Agent job lifecycle
- Docker (local or any container host)
- Variants
- Rollout
- SECTION E — Autonomy & Self-Healing (AOS / MYT / ECC)
- SECTION F — Developer Experience (CBF / ECC)
- Runtime troubleshooting
- knowledgeGraphTab.test.js
- loginFlowNoTimeout.test.js
- test_company_stale_id_recovery.test.js
- worker_no_cache.test.js
- scripts/agile_ceremonies.py
- .chat
- governance/__init__.py
- Prompt Library Changelog
- _add_colibri_shim_changelog_entry.py
- build_llama_cpp.ps1
- download_glm52_weights.ps1
- download_glm52_weights.sh script
- _fetch_pytest_failures.py
- setup_colibri.ps1
- setup_colibri.sh script
- status_colibri_server.ps1
- .get_bound_skills
- TestAuth
- TestMobileNavigation
- test_v5_screens_smoke.py
- test_agent_runtime_wrapper.py
- TestWorkflowSkillMap
- worker/index.js
- recovery.py
- aider_config.sh
- providers.yaml
- Credential Rotation Runbook
- Runbook: `make doctor`
- render
- scripts
- _clean_director
- _resolve_default_executor_model
- stop_colibri_server.ps1
- .consolidate
- start_server.sh
- check_services
- TestHealth
- TestProviders
- TestProviders
- TestWiki
- TestAgents
- nvidia_live_test.py
- test_activity_feed.py
- test_local_brain_router_actor_regression.py
- test_no_exception_detail_leaks.py
- test_skills_route_order.py
- github
- main
- graphify-refresh
- [Unreleased]
- Session Learnings
- frontend/.eslintrc.json
- .get_phase_index
- branch_cleanup.sh
- local-ai-health-check.sh
- pull-ai-models.sh
- test_nim_models.py
- .consolidation_threshold
- test-anthropic.js
- _classify_error
- TestActivation
- TestAgents
- TestApiKeys
- TestChat
- TestFeatures
- TestGitHub
- TestSchedules
- TestSkills
- TestSchedules
- test_the_reserve_is_bounded_when_read_from_the_environment
- test_direct_adapter_does_not_bypass
- test_mint_token_rejects_missing_args
- .list_workspaces
- maintenance_section.md
- duplicate.sh
- hello_claude.py
- backend/__init__.py
- build-workflow
- commit-msg
- post-commit
- session-plan-bootstrap
- start_web_with_openclaw.sh
- frontend-redesign-prompt.md
- NEXT-SESSION-PROMPT.md
- docs/script.js
- specialists-skills-matrix.md
- setupTests.js
- get_tunnel_url.sh script
- prepare-commit-msg
- nvidia_models.py
- redact_secrets.sh
- install.sh script
- models/README.md
- auth/__init__.py
- events/__init__.py
- integrations/__init__.py
- orchestration/__init__.py
- scheduler/__init__.py
- security/__init__.py
- shared/__init__.py
- storage/__init__.py
- packages/tasks/__init__.py
- telemetry/__init__.py
- providers/__init__.py
- run_ollama.sh
- run_tunnel.sh
- runtimes/adapters/__init__.py
- script.js
- insert_provider_policy.py
- setup-autostart.sh
- kimi_bridge_server/__init__.py
- .dream_count
- .memory_count
- .replay
- setup_autostart_macos.sh
- start.sh
- stop-proxy.sh script
- stop_server.sh script
- _enable_filter
- test_pytest_many_tests
- test_unknown_command_generic_filter
- test_docker_build_large
- .test_cleans_removes_double_spaces
- .test_detects_multiple_throat_clearing
- .test_detects_wh_starters
- .test_cleans_emphasis_crutches
- test_agent_schedules_stays_out_of_the_generic_sqlite_allowlist
- test_the_collection_name_comes_from_the_store_not_a_literal
- voice/__init__.py

## God Nodes (most connected - your core abstractions)
1. `AgentRunner` - 303 edges
2. `_fixture()` - 289 edges
3. `AgentSessionStore` - 185 edges
4. `AgentScheduler` - 157 edges
5. `ProviderConfig` - 152 edges
6. `ProviderRouter` - 152 edges
7. `Task` - 151 edges
8. `ExecutionRequest` - 132 edges
9. `UserMemoryStore` - 131 edges
10. `Agency` - 128 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `_skip()`  [INFERRED]
  .github/scripts/apply_review.py → tests/test_providers_live_e2e.py
- `_fake_fetch_module()` --indirect_call--> `strip_html()`  [INFERRED]
  tests/test_web_reach.py → .github/scripts/fetch_url.py
- `_fake_fetch_module()` --indirect_call--> `extract_real_url()`  [INFERRED]
  tests/test_web_reach.py → .github/scripts/fetch_url.py
- `_fake_fetch_module()` --indirect_call--> `meaningful()`  [INFERRED]
  tests/test_web_reach.py → .github/scripts/fetch_url.py
- `apply_edits()` --calls--> `is_destructive_overwrite()`  [INFERRED]
  scripts/agency_fix.py → .github/scripts/slop_gate.py

## Import Cycles
- None detected.

## Communities (1158 total, 114 thin omitted)

### Community 0 - "backend/server.py"
Cohesion: 0.01
Nodes (393): _close_github_issue(), _fetch_github_quick_notes(), get_agency(), _gh_repo(), _gh_token(), Enum, agent/agency.py — Autonomous Agent Agency (CEO-driven, LLM-powered) Runs the…, Return the GitHub repo in 'owner/name' format. Priority: 1. GITHUB_REPOSITORY… (+385 more)

### Community 1 - "ProviderConfig"
Cohesion: 0.02
Nodes (198): get_tracker(), Return the process-singleton RateLimitTracker., _acquire_provider_probe(), clear_cooldowns(), _dead_model_key(), _exponential_backoff_cooldown(), extract_openai_text(), get_dead_models() (+190 more)

### Community 2 - "AgentScheduler"
Cohesion: 0.04
Nodes (143): Agency, CEO-coordinated multi-agent agency for continuous codebase management. The CEO…, AgentJobRequest, AgentJobSnapshot, Complete point-in-time view of a job, safe to serialise as API response., Convenience: the canonical text response, whether success or failure., Validated input for creating a new agent job. Passed from the API handler into…, DirectChatDoctor (+135 more)

### Community 3 - "_fixture"
Cohesion: 0.01
Nodes (133): parse_event_stream(), Reduce a ``--mode json`` NDJSON stream to a :class:`ParsedRun`. Kept a module-…, app_client(), _clear_discovered_models(), _clear_response_cache(), client(), _isolate_brain_data_layer(), _isolate_operator_provider_state() (+125 more)

### Community 4 - "company_api.py"
Cohesion: 0.02
Nodes (162): ephemeral_ttl_hours(), Async read of the ephemeral TTL (hours) straight from the DB., account_lifecycle(), auto_recommend_skills(), cancel_onboarding(), create_company(), delete_company_endpoint(), generate_onboarding_questions() (+154 more)

### Community 5 - "TaskSpec"
Cohesion: 0.03
Nodes (123): kimi_bridge_runtime_config(), Return Kimi bridge config for external runtimes (Hermes, Goose, Aider). Returns…, TaskResult, TaskSpec, runtimes/adapters/aider.py — Aider adapter (TIER 3 — specialized). Aider…, Run aider non-interactively via `--message` flag., runtimes/adapters/claude_code.py — Claude Code CLI adapter (FIRST CLASS).…, runtimes/adapters/docker_agent.py — Docker-based agent runtime adapter. Spawns… (+115 more)

### Community 6 - "SQLiteStore"
Cohesion: 0.02
Nodes (91): Find a website by its URL., A company website with detected systems and stack inference., Website, MongoDBStore, Any, Company, ObjectId, Prepare a Pydantic model for SQLite storage. (+83 more)

### Community 7 - "FeatureMaturity"
Cohesion: 0.03
Nodes (102): PreflightReport, AgentJob, make_isolated_workspace(), _now(), Any, Path, agent/job_manager.py — Async agent job lifecycle manager. Manages agent jobs…, Run a job using the provided runner and update the job's lifecycle, progress,… (+94 more)

### Community 8 - "Specialist"
Cohesion: 0.05
Nodes (127): AccountLifecycleResponse, _DoctorCheck, _DoctorReport, OnboardingAnswersRequest, OnboardingProgressResponse, OnboardingQuestionsRequest, BaseModel, Request to generate AI-tailored onboarding questions. (+119 more)

### Community 9 - "proxy.py"
Cohesion: 0.03
Nodes (144): Any, Return recent commits with agent attribution trailers parsed out., get_sam(), agent/sam.py — SAM Voice Agent (System Autonomy Manager) SAM is the voice-…, get_skill_registry_safe(), Return the global SkillRegistry if set, else None. Used by onboarding and other…, middleware, admin_control() (+136 more)

### Community 10 - "llm/router.py"
Cohesion: 0.03
Nodes (123): _load(), main(), int, get_budget(), packages/llm/budget.py — token and cost accounting with spend alerts. Tracks…, The process-wide budget tracker., Test hook — clear all usage accounting., reset() (+115 more)

### Community 11 - "ScheduledJob"
Cohesion: 0.02
Nodes (71): _age_seconds(), _now(), Any, agent/scheduler.py — Scheduled Agent Jobs Cron-based job scheduler. Each job…, Reconstruct a ScheduledJob from its as_dict() output., Register a new job. Returns the created :class:`ScheduledJob`.…, Fire a job immediately (webhook / manual trigger)., Remove a job. Returns *True* if it existed. (+63 more)

### Community 12 - "FeatureMatrix"
Cohesion: 0.03
Nodes (47): FeatureEntry, FeatureMatrix, get_feature_matrix(), Any, BaseModel, One entry in the support matrix., Central support matrix — single source of truth. Loads the canonical feature…, Load canonical features and apply per-feature then bulk env overrides. (+39 more)

### Community 13 - "test_llm_router_strategies.py"
Cohesion: 0.03
Nodes (101): count, HealthConfig, Strategy selection and degradation behaviour., Circuit breaker + health tracking thresholds., RoutingConfig, HealthTracker, _Outcome, ProviderHealth (+93 more)

### Community 14 - "PortfolioManager"
Cohesion: 0.03
Nodes (94): AgentRole, str, Lifecycle status of a sprint., SprintStatus, add_initiative(), AllocationOut, BoardOut, get_board() (+86 more)

### Community 15 - "test_operational_incidents.py"
Cohesion: 0.02
Nodes (118): _diagnose_and_file(), _file_incident(), _format_incident(), gather_render_evidence(), get_operational_incident_tracker(), _iso_from_monotonic(), normalise(), note_phase_end() (+110 more)

### Community 16 - "TaskHarnessAdapter"
Cohesion: 0.03
Nodes (45): AiderAdapter, Any, Adapter for Aider — TIER 3 specialized git-aware code editor., GooseAdapter, Any, Adapter for Goose — TIER 2 general-purpose local runtime., OpenCodeAdapter, TaskResult (+37 more)

### Community 17 - "Usage"
Cohesion: 0.04
Nodes (59): AnthropicProvider, Any, AsyncClient, packages/llm/providers/anthropic.py — Anthropic Messages API adapter. Anthropic…, Translate OpenAI-shaped messages into Anthropic's system/turn split., OpenAI carries a tool result as role="tool" with a tool_call_id; Anthropic…, OpenAI puts a tool call alongside the assistant's text; Anthropic needs…, Anthropic's extended-thinking constraints on ``budget_tokens``: at least 1024,… (+51 more)

### Community 18 - "AgentSessionStore"
Cohesion: 0.04
Nodes (80): Agent subsystem — planner / executor / verifier loop., AgentEvent, AgentPlan, AgentSession, AgentSessionMessage, AgentStep, BaseModel, models.py — Pydantic models for agent I/O contracts. (+72 more)

### Community 19 - "skill_bindings.py"
Cohesion: 0.03
Nodes (77): Status of a user story within a sprint., StoryStatus, HarnessAdapter, HarnessSpec, Any, agents/harness_adapter.py — ECC Cross-Harness Adapter Normalises API…, Adapt harness-native requests to the local-llm-server internal format. Each…, Detect which harness sent this request from headers. Check order: explicit… (+69 more)

### Community 20 - "api.js"
Cohesion: 0.02
Nodes (39): approveGovernanceRequest(), autoRecommendCompanySkills(), createMcpServer(), delegateSeoFindings(), deleteCompany(), deleteMcpServer(), denyGovernanceRequest(), discoverLlmModels() (+31 more)

### Community 21 - "LLMRequest"
Cohesion: 0.04
Nodes (106): ProviderConfig, One configured endpoint. ``kind`` selects the adapter: ``openai`` (any OpenAI-…, OpenAICompatible, Adapter for any endpoint speaking the OpenAI chat-completions shape. Adding a…, build_provider(), ProviderConfig, Normalise a configured ``kind`` to an adapter key., Instantiate the adapter for one provider config. Unknown kinds fall back to the… (+98 more)

### Community 22 - "TaskStore"
Cohesion: 0.04
Nodes (75): _is_brain_connection_error(), Any, BaseException, Task, TaskResult, TaskSpec, TaskStatus, Best-effort label of who will run this task once approved. Returns… (+67 more)

### Community 23 - "test_llm_router_queue_cache.py"
Cohesion: 0.03
Nodes (83): cosine_similarity(), Cosine similarity between two vectors, 0.0 when either is degenerate., build_summariser(), chunk_document(), ContextManager, estimate_tokens(), FitResult, message_tokens() (+75 more)

### Community 24 - "ProviderManager"
Cohesion: 0.05
Nodes (75): _fake_user_auth(), Path, test_admin_can_create_anthropic_provider_via_webui_admin_api(), test_admin_can_create_provider_via_webui_admin_api(), test_ui_providers_and_workspaces_use_app_state(), _bootstrap(), Path, ProviderManager (+67 more)

### Community 25 - "MCPUnavailableError"
Cohesion: 0.04
Nodes (77): MCPUnavailableError, Raised when the MCP server is unreachable or the circuit is open., TaskResult, TaskSpec, Execute a task inside a fresh E2B sandbox. Flow: 1. Open an…, Run ``pytest`` inside the sandbox. Returns ``(output, passed)``.…, E2BSandboxSession, _inject_token() (+69 more)

### Community 26 - "test_ceo_micromanager.py"
Cohesion: 0.04
Nodes (99): Split the request into briefed, tier-assigned specialist sub-tasks. Returns the…, build_subtask_brief(), _coerce_subtasks(), decompose(), _env_flag(), _env_int(), _extract_json_object(), fallback_decomposition() (+91 more)

### Community 27 - "RenderOpsMonitor"
Cohesion: 0.04
Nodes (48): BaseModel, Response shape of ``GET /api/render/ops/status``. Declared here rather than in…, RenderOpsStatus, RuntimeError, packages/integrations/render_mcp.py — Render platform access over MCP. The…, One deploy, normalised from whatever shape the tool returned., Typed facade over the Render MCP server's tools. Every method returns plain…, True when there is both an API key and an endpoint to reach. (+40 more)

### Community 28 - "SelfHealingAgent"
Cohesion: 0.03
Nodes (71): heal_signature(), HealingEvent, _now(), Any, Translate external failure signals into improvement tasks and verify the fix…, Launch the background sweeper that resolves quiet verifying heals., Called when a CI workflow fails., Called when a GitHub issue with a bug label is opened. (+63 more)

### Community 29 - "ExecutionRequest"
Cohesion: 0.05
Nodes (72): Execute work through the 11-phase golden path., Called by APScheduler when a cron fires. Dispatches to the orchestrator., _scheduler_on_fire(), workflow_orchestrator_execute(), get_orchestrator_checkpoint_store(), _NoopDB, OrchestratorCheckpointStore, services/orchestrator_checkpoint.py — Durable step-level checkpointing Issue… (+64 more)

### Community 30 - "test_governance_sandbox.py"
Cohesion: 0.04
Nodes (73): build_docker_run_argv(), detect_backend(), DockerBackend, E2BBackend, load_profiles(), LocalBackend, Any, Path (+65 more)

### Community 31 - "services/background.py"
Cohesion: 0.04
Nodes (85): get_improvement_loop(), _dispatch_async(), _ErrorCaptureHandler, get_log_monitor(), LogMonitor, _note_recurrence(), Any, LogRecord (+77 more)

### Community 32 - "Initiative"
Cohesion: 0.03
Nodes (75): _bullets(), generate_backlog_retro(), generate_sprint_retro(), generate_standup(), plan_next_sprint(), Agentic Agile — autonomous ceremonies (standup, retro, sprint planning). Where…, Render a :class:`Retrospective` as a markdown section., Derive retro notes for ``sprint`` from its current metrics. Records… (+67 more)

### Community 33 - "WorkflowRun"
Cohesion: 0.04
Nodes (51): _NoopStore, Any, Exception, Approve a run paused at the ApprovalGate. The caller must re-invoke…, Inject additional instructions into an in-flight run (no state change). Backs…, Push a Telegram approval-gate notification when a run pauses (Charter G1).…, G5: resolve how a run should land from the company's DeliveryPolicy. Returns…, Persist first-merge consent once an operator approves a ``telegram_gate``. No-… (+43 more)

### Community 34 - "ImprovementLoop"
Cohesion: 0.05
Nodes (68): _build_ceo_prompt(), _collect_recent_git_context(), _parse_ceo_directives(), Return recent commits and changed files for CEO situational awareness., DetectedIssue, ImprovementLoop, ImprovementLoopState, _now() (+60 more)

### Community 35 - "test_unit8_model_catalog.py"
Cohesion: 0.03
Nodes (79): _brain_provider_status(), get_brain_policy_route(), Return per-provider metadata for the GET endpoint. Iterates every provider in…, Return the active brain config + per-provider key-present flags. The response…, all_provider_ids(), _provider_ids_from_literal(), provider_key_present(), Return every provider id recognised by the brain config system. Iterates the… (+71 more)

### Community 36 - "MCPClient"
Cohesion: 0.04
Nodes (42): MCPClient, Any, RuntimeError, Thin async MCP client with open/close circuit breaker. Thread-safe only within…, Full URL of the JSON-RPC endpoint this client posts to., Build the request headers shared by ``_rpc`` and ``notify``. ``Accept`` lists…, Propagate the calling agent's identity across the process boundary. The MCP…, Attach the agent identity whose actions this client executes. (+34 more)

### Community 37 - "KeyPool"
Cohesion: 0.03
Nodes (49): provider_api_keys(), Every API key configured for *provider*, primary first. Reads ``base_env`` then…, api_keys_for(), _digest(), get_pool(), KeyPool, _KeyState, _PoolState (+41 more)

### Community 38 - "test_llm_router_resilience.py"
Cohesion: 0.03
Nodes (65): Backoff policy for retryable failures., RetryConfig, _digest(), KeyRing, KeyState, packages/llm/keys.py — multi-key rotation with per-key health. A provider may…, Per-provider round-robin key selection with cooldowns., Return the next healthy key and its index. Returns ``(None, -1)`` when every… (+57 more)

### Community 39 - "HermesAdapter"
Cohesion: 0.03
Nodes (61): _active_primary_provider(), is_north_mini_code_default(), True when the ``NORTH_MINI_CODE_DEFAULT`` flag is on (default ON). Reads the…, Best-effort read of the active brain's primary provider (or ``None``)., Resolve the model id to force for a code-execution run, or ``None``. Returns…, resolve_coding_model_preference(), _env_float(), HermesAdapter (+53 more)

### Community 40 - "WebsiteScanner"
Cohesion: 0.04
Nodes (66): main(), Returns (url, ok, summary)., _scan_one(), _content_contains_domain(), _hostname_contains(), _hostname_matches(), _is_safe_url(), _looks_like_bot_challenge() (+58 more)

### Community 41 - "resolve_active_brain"
Cohesion: 0.04
Nodes (87): BrainResolution, get_brain_config(), provider_api_key(), Convenience wrapper used by the agent loop + brain resolver., Convenience wrapper used by the admin API endpoints., Return the live API key for *provider* (env-only — never persisted)., set_brain_config(), get_active_brain_sync() (+79 more)

### Community 42 - "direct_chat.py"
Cohesion: 0.05
Nodes (78): PreflightIssue, Any, BaseModel, doctor.py — Agent-side doctor diagnostics: environment, provider, and workspace…, Translate technical preflight issues into a conversational assistant reply., translate_error_to_conversational(), ResumeRequest, AcceptedJob (+70 more)

### Community 43 - "test_phase6_workflow.py"
Cohesion: 0.04
Nodes (73): add_pr_comment(), _find_existing_pr(), get_branch_sha(), get_default_branch(), _headers(), Any, agent/safe_agency.py — Safe GitHub operations for the workflow engine. All…, Create a pull request. Returns the PR object dict. If a PR already exists for… (+65 more)

### Community 44 - "KeyStore"
Cohesion: 0.04
Nodes (44): Browser admin UI for login, service control, key management, and diagnostics., Update or append a KEY=value line in the .env file., register_admin_gui(), _save_env_var(), _check_rate_limit(), default_keys_path(), issue_new_api_key(), KeyRecord (+36 more)

### Community 45 - "brain_config.py"
Cohesion: 0.04
Nodes (70): BrainConfig, BrainConfigStore, default_brain_config(), get_brain_config_store(), invalidate_brain_config_cache(), provider_base_url(), _provider_env_value(), provider_key_rotation_enabled() (+62 more)

### Community 46 - "FreeBuffAgent"
Cohesion: 0.13
Nodes (73): BackgroundTask, BrowserSession, Async Playwright browser session. Usage:: session = BrowserSession() await…, True if Playwright is installed and ready to use., CommitAttribution, CommitTracker, Path, agent/commit_tracker.py — AI Commit Attribution Tags git commits with metadata… (+65 more)

### Community 47 - "AgentRunner"
Cohesion: 0.05
Nodes (45): AgentRunner, Any, Path, Governance seam: judge the call, run it, audit the outcome. Deliberately a thin…, Append an event to the durable session log if a store is wired in., Summarise a long history and compact it. Asks the planner model to write a…, Send chat messages and return the assistant's text output. If an…, Call-time resolver for an agent role model id. Delegates to… (+37 more)

### Community 48 - "SeoAuditRequest"
Cohesion: 0.05
Nodes (55): BaseModel, field_validator, models/seo_audit.py - SEO / GEO / AIO Audit Contracts Typed Pydantic models for…, A single occurrence of a check firing on a specific URL., Snapshot of one crawled page with the on-page facts the checks used., Aggregated report row - Screaming Frog CSV compatible., Site-level facts discovered during the crawl., An agent-delegable remediation work package derived from the findings. Findings… (+47 more)

### Community 49 - "get_runtime_manager"
Cohesion: 0.04
Nodes (77): _enrich_runtimes(), get_decision_log(), get_policy(), get_runtime(), list_runtimes(), _load_rich_policy(), PolicyUpdateBody, Any (+69 more)

### Community 50 - "RenderFinding"
Cohesion: 0.05
Nodes (52): get_mcp_client(), Return the module-level MCPClient. Reads MCP_SERVER_BASE_URL at call time (not…, _internal_configured(), list_specs(), MCPServerSpec, _not_dialable(), _playwright_configured(), _probe_http() (+44 more)

### Community 51 - "CompanyGraphStore"
Cohesion: 0.03
Nodes (39): Find a repository by its URL., A company repository with detected technologies and metadata., Extract the owner from the full name., Extract the repository name from the full name., Repo, Add a repository to a company. Args: company_id: Company ID url: Repository URL…, Get a repository by ID., CompanyGraphStore (+31 more)

### Community 52 - "test_failover_client_shared.py"
Cohesion: 0.07
Nodes (79): failover_chat_completion(), Run one chat completion across the brain-failover chain. Tries each healthy…, _free_tier(), _hit_ids(), _many_providers(), _mixed_registry(), _openai_body(), _paid() (+71 more)

### Community 53 - "PrimeAgentAdapter"
Cohesion: 0.04
Nodes (41): _accumulate_usage(), _assistant_messages(), _iter_events(), _kill_and_reap(), _message_text(), PrimeAgentAdapter, Any, TaskSpec (+33 more)

### Community 54 - "test_user_research_skill.py"
Cohesion: 0.06
Nodes (45): analyze_quantitative(), _classify_sentiment(), _extract_keywords(), plan_research(), Any, BaseModel, field_validator, QualAnalysis (+37 more)

### Community 55 - "CEODispatcher"
Cohesion: 0.04
Nodes (64): CEODispatcher, CEOResult, _complexity_rank(), _decompose_into_subtasks(), _merge_changed_files(), _offload(), Any, Semaphore (+56 more)

### Community 56 - "test_ceo_dispatcher.py"
Cohesion: 0.05
Nodes (73): ClassifyOutput, get_ceo_fallback_stats(), PlanOutput, CLASSIFY phase: domain and task type determination., PLAN phase: structured execution plan., SELECT_SPECIALIST phase: which specialist(s) handle this work., Increment the named counter (silently ignores unknown reasons)., Return a snapshot of the CEO fallback counters. (+65 more)

### Community 57 - "Task"
Cohesion: 0.05
Nodes (55): Full task/issue document., Task, Best-effort Telegram heads-up that a task is parked awaiting approval. Inline…, Tests for task follow-up / rerun with conversation carry-over. Before this,…, The runtime reads context['conversation']; prior comments must be carried as…, test_build_spec_exposes_conversation_for_runtime(), test_follow_up_empty_message_rejected(), test_follow_up_requeues_done_task() (+47 more)

### Community 58 - "MultiAgentSwarm"
Cohesion: 0.06
Nodes (62): AgentConfig, build_agent_specs(), build_swarm(), build_task_specs(), coordinate_v2(), CoordinateRequestV2, CoordinateResponse, Any (+54 more)

### Community 59 - "test_model_router.py"
Cohesion: 0.05
Nodes (78): classify_task(), _extract_recent_text(), Any, Task classification from request context. Classifies an incoming request into a…, Concatenate plain text from the last *last_n* messages., Return the most likely task category for this request. Args: messages: OpenAI-…, Reset the singleton and clear the cached model map (test helper)., reset_router() (+70 more)

### Community 60 - "tasks/service.py"
Cohesion: 0.05
Nodes (64): Helpers that turn scheduler and playbook activity into real tasks., Background dispatcher for task execution., tasks — Task/issue management system. Provides a lightweight task/issue tracker…, ApprovalCheckpoint, Enum, str, tasks/models.py — Pydantic models for the task/issue system., Comment or reply on a task. (+56 more)

### Community 61 - "NotificationDispatcher"
Cohesion: 0.04
Nodes (49): NotificationDispatcher, Any, Path, Start the Telegram bot. Returns True if started successfully., Signal the bot to stop and wait for graceful shutdown., Run the Telegram bot long-poll loop (inline, not subprocess)., Run the bot with stop-event awareness., Routes background task results to configured notification channels. Currently… (+41 more)

### Community 62 - "test_knowledge_sync.py"
Cohesion: 0.06
Nodes (62): _api_key(), _auth_headers(), _build_digest_markdown(), create_wiki_page(), fetch_and_store(), get_knowledge_sync(), KnowledgeSync, _now_iso() (+54 more)

### Community 63 - "FailureCategory"
Cohesion: 0.05
Nodes (35): filter_safe_tools(), get_tool_annotations(), Typed representation of MCP tool annotations (spec 2025-11-05 §5.6.1). All…, Return True only when the tool is definitively read-only and non-destructive.…, Extract ``ToolAnnotations`` for a named tool from a ``list_tools()`` result.…, Return tools where ``readOnlyHint`` is True and ``destructiveHint`` is not…, ToolAnnotations, FailureCategory (+27 more)

### Community 64 - "test_runtime_governance.py"
Cohesion: 0.06
Nodes (64): Decision, str, A control surface — the kind of thing being governed. Mirrors Docker AI…, The verdict for one governed action., Surface, _audit_dispatch(), _blocked_result(), _governance_check() (+56 more)

### Community 65 - "test_startup_warmup.py"
Cohesion: 0.04
Nodes (70): Set the global agent store instance (e.g., with MongoDB on startup)., set_agent_store(), _bootstrap_within_budget(), _create_bootstrap_indexes(), ensure_bootstrap(), _ensure_tasks_source_id_unique_index(), Await one warm-up step, deferring it to the background if it overruns.…, Add a unique+sparse index on tasks.source_id — isolated from the main bootstrap… (+62 more)

### Community 66 - "test_ceo_supervision.py"
Cohesion: 0.06
Nodes (68): _harvest_changed_files(), Extract the files a runtime touched. Returns ``(files, reported)``. Adapters…, A subtask's full history: what it is, and every attempt at it., SubtaskRecord, One unit of delegated work, before it has been briefed or executed., SubtaskPlan, What one sweep observed and did. Returned for tests and diagnostics., SweepReport (+60 more)

### Community 67 - "DashboardLayout.js"
Cohesion: 0.04
Nodes (43): completeSetup(), createSecret(), detectHardwareForSetup(), detectModelsForSetup(), getMe(), getPublicPath(), getSetupState(), login() (+35 more)

### Community 68 - "BrainWatchdog"
Cohesion: 0.04
Nodes (54): Any, packages/ai/self_heal.py — automatic brain self-healing. When the active brain…, One-shot self-healing pass. 1. Checks if the active brain provider is in a…, self_heal_brain_and_unblock_tasks(), BrainWatchdog, get_watchdog(), _is_provider_actually_available(), Any (+46 more)

### Community 69 - "TasksPage.js"
Cohesion: 0.04
Nodes (60): addTaskComment(), approveTaskCheckpoint(), approveTaskExecution(), clarifyTask(), createAgent(), createQuickNote(), createSprint(), createTask() (+52 more)

### Community 70 - "test_governance_enforcement.py"
Cohesion: 0.05
Nodes (65): packages/governance/audit.py — the evidence trail for every governed action.…, Redact secret-shaped substrings, then truncate., Recursively strip secrets from an arbitrary argument structure. Fails…, scrub(), _scrub_inner(), _scrub_text(), _truncate(), BudgetTracker (+57 more)

### Community 71 - "workflow/api.py"
Cohesion: 0.06
Nodes (60): _make_engine(), tests/test_crispy_workflow.py — CRISPY workflow engine hardening tests. Tests…, Provide isolated DB + artifact + workspace paths., Create a WorkflowEngine with isolated storage., TestAbortOnFailure, TestPhaseSequence, TestWorkspaceIsolation, tmp_db() (+52 more)

### Community 72 - "get_user_role"
Cohesion: 0.06
Nodes (53): compute_savings(), compute_time_series(), get_savings(), get_usage(), get_user_savings(), _period_start(), Any, BaseModel (+45 more)

### Community 73 - "detector.py"
Cohesion: 0.06
Nodes (46): batch_compatibility(), check_model_compatibility(), _detect_amd_gpus(), _detect_apple_silicon_gpu(), _detect_cpu(), detect_hardware(), _detect_intel_arc_gpu(), _detect_nvidia_gpus() (+38 more)

### Community 74 - "AgentSwarm"
Cohesion: 0.05
Nodes (43): AgentRole, AgentSwarm, Any, Return the agent role responsible for *phase*., Return the AgentProfile for the agent driving *phase*., Return a JSON-serialisable summary of all agent profiles., Run a pre-gate or report phase through the correct agent. Enforces permission…, Execute a slice via the Coder agent (write-permitted). (+35 more)

### Community 75 - "setup/api.py"
Cohesion: 0.07
Nodes (65): is_user_onboarding_allowed(), Return True if this user may run the onboarding wizard. Resolution order: 1. If…, complete_wizard(), _delete_wizard_state(), detect_configured_providers(), detect_hardware_for_wizard(), detect_models_for_wizard(), _detect_ollama_models() (+57 more)

### Community 76 - "enforcement.py"
Cohesion: 0.05
Nodes (47): _load(), mcp_server/governance.py — governance adapter for the MCP HTTP surface. Closes…, Write the audit row for a completed (or blocked) MCP tool call., Import the governance layer once, recording why if it is absent., record(), events_from_identity(), Any, Convenience: build and record an event in one call. (+39 more)

### Community 77 - "HybridSystem"
Cohesion: 0.05
Nodes (29): ConfidenceLevel, DeterministicEngine, HybridSystem, LLMReasoner, Any, Enum, str, Hybrid AI — combine deterministic rule engines with LLM reasoning. Implements a… (+21 more)

### Community 78 - "ResearchTask"
Cohesion: 0.06
Nodes (44): AgentRole, Enum, str, Multi-Agent Research Coordinator — orchestrate a team of specialized research…, Run the task and return it (mutated) with status set., Coordinates a multi-agent research workflow. Workflow: 1. plan(question) → list…, Decompose a research question into a default DAG. Default plan: web → docs…, Round-robin pick within a role (least-loaded first). (+36 more)

### Community 79 - "test_model_catalog.py"
Cohesion: 0.05
Nodes (66): _build_base_url_env_from_yaml(), _build_candidates_from_yaml(), _build_default_base_url_from_yaml(), _build_display_names_from_yaml(), _build_key_env_from_yaml(), _build_presets_from_yaml(), _build_tier_from_yaml(), get_provider_candidates() (+58 more)

### Community 80 - "brain_failover.py"
Cohesion: 0.05
Nodes (64): auto_disable(), _billing_signals(), disabled_provider_ids(), is_unfixable(), packages/llm/disabled.py — bridge to the durable provider on/off switch. The…, Provider ids currently switched off. Empty when the store is unreachable., Persist a provider as disabled, through the store that already owns it., The one list of "you have no money" phrases, borrowed not copied. Lazy because… (+56 more)

### Community 81 - "_ts_to_float"
Cohesion: 0.04
Nodes (54): _is_duplicate_key_error(), Any, Exception, Task, TaskStatus, Create a task. Deduplicates by source_id if set (Charter G3). If a task with…, Fetch a task by ID. If owner_id is set, enforces ownership., Return the task previously created for an external ``source_id`` (e.g.… (+46 more)

### Community 82 - "WebReach"
Cohesion: 0.07
Nodes (52): Register the built-in agent tools that are always available., Register the Web Reach capability (agent/web_reach.py): zero-key internet…, _register_builtin_tools(), _register_web_reach_tools(), _egress_policy_reason(), get_web_reach(), _load_script_module(), Any (+44 more)

### Community 83 - "resolve_e2b_config"
Cohesion: 0.05
Nodes (58): Available iff config resolves AND the SDK is importable. Never raises — a…, e2b_status(), Return the E2B sandbox integration status for the ProvidersScreen badge. Does…, e2b_enabled(), E2BConfig, _env_falsy(), _env_truthy(), is_e2b_sdk_importable() (+50 more)

### Community 84 - "TestClient"
Cohesion: 0.10
Nodes (29): bare_repo(), _call(), _data(), git_config_env(), _is_error(), mcp_workspace_root(), Path, skipif (+21 more)

### Community 85 - "test_ai_insights.py"
Cohesion: 0.05
Nodes (49): AIToolMetrics, build_report(), EngagementMetrics, PerformanceAnalytics, datetime, Enum, str, AI-Assisted Engineering Insights — track AI tool usage, engagement, and… (+41 more)

### Community 86 - "test_repo_connection.py"
Cohesion: 0.07
Nodes (49): DeliveryPolicy, How code lands on a repo's default branch (detected, GitHub-only for now). The…, A company's connection to a code repository (GitHub-only this pass). URL-only…, RepoConnection, attach_repo_connection(), build_repo_connection(), decide_merge(), detect_delivery_policy() (+41 more)

### Community 87 - "resolve_identity"
Cohesion: 0.05
Nodes (53): AgentIdentity, new_session_id(), Any, packages/governance/identity.py — who is acting, and under what mandate. Docker…, Return a copy carrying extra execution context. Used when context arrives after…, Serialise for audit rows and API responses. Every field here is non-secret by…, Build an :class:`AgentIdentity` from whatever the caller knows. Total by design…, Return the stable ``agent:<slug>`` id for a human agent name. Deterministic and… (+45 more)

### Community 88 - "ModelRouter"
Cohesion: 0.06
Nodes (38): Dynamic model router package. Public API:: from router import get_router,…, _build_builtin_model_map(), _default_model(), _default_reasoning_model(), ModelRouter, _nvidia_key_present(), Any, Dynamic model router. Central routing logic for all chat and agent requests.… (+30 more)

### Community 89 - "ProceduralMemoryStore"
Cohesion: 0.05
Nodes (26): get_procedural_memory(), _overlap_score(), ProceduralMemoryStore, ProceduralRecord, Any, agent/procedural_memory.py — Skill/Procedural Memory for the agent loop (★4).…, Store a successful step pattern and return its record id. Duplicate step…, Return up to *limit* stored patterns relevant to *query*. Relevance is scored… (+18 more)

### Community 90 - "Troubleshooting"
Cohesion: 0.03
Nodes (64): 401 Unauthorized, 403 Forbidden from remote machine, 429 Too Many Requests, Admin Dashboard Issues, Agent API Issues, Agent makes a change but doesn't verify correctly, Agent returns empty or incomplete plan, Agent workspace errors ("file not found") (+56 more)

### Community 91 - "ChatPage.js"
Cohesion: 0.05
Nodes (48): cancelAgentChatJob(), chatSend(), deleteSession(), getAgentChatJob(), getSession(), listProviderModels(), listProviders(), listSessions() (+40 more)

### Community 92 - "FetchResult"
Cohesion: 0.06
Nodes (27): MockTransport, browser_backend_available(), BrowserFetcher, FetchResult, HttpxFetcher, looks_blocked(), make_fetcher(), AsyncBaseTransport (+19 more)

### Community 93 - "test_bedrock_provider.py"
Cohesion: 0.05
Nodes (22): _is_bedrock_model_id(), Return True if model_id is an AWS Bedrock model or inference profile ID., _bedrock_api_response(), _bedrock_provider(), _mock_boto3(), Any, asyncio, ProviderConfig (+14 more)

### Community 94 - "TestClient"
Cohesion: 0.08
Nodes (43): _auth_headers(), _build_agent_http_mock(), _exec(), _fake_request(), _mcp_tool_response(), _multi_step_plan(), _nim_post_factory(), _one_step_plan() (+35 more)

### Community 95 - "ControlPlanePage.js"
Cohesion: 0.06
Nodes (41): getActivity(), getCostAttribution(), getDecisionLog(), getDueSoonTasks(), getSavings(), getStats(), getUsage(), healthCheck() (+33 more)

### Community 96 - "SecretRecord"
Cohesion: 0.07
Nodes (40): str, UserRole, _can_read(), _can_write(), _decrypt(), _encrypt(), _get_master_key(), BaseModel (+32 more)

### Community 97 - "test_colibri_brain_shim.py"
Cohesion: 0.05
Nodes (60): colibri_enabled(), colibri_provider_config(), colibri_status(), ProviderConfig, providers/colibri.py — Free local GLM-5.2 brain served by JustVugg/colibri.…, Return True iff the operator opted in via ``COLIBRI_ENABLED=true``., Cheap status snapshot for tests + admin UI., Return the ``ProviderConfig`` for the local colibri server, or ``None`` when… (+52 more)

### Community 98 - "test_governance_api.py"
Cohesion: 0.06
Nodes (58): build_governance_router(), Any, APIRouter, backend/governance_router.py — read and operate the governance layer. Mounted…, Reject non-admin callers. Mirrors the RBAC check used elsewhere in this backend…, _require_admin(), get_approval_store(), get_audit_log() (+50 more)

### Community 99 - "seo_api.py"
Cohesion: 0.05
Nodes (49): delegate_seo_findings(), _expire_stale_pending_report(), get_seo_audit(), list_seo_audits(), BaseModel, get, post, SEO / GEO / AIO Audit API Router Endpoints for the world-class SEO audit engine… (+41 more)

### Community 100 - "AdaptiveHalter"
Cohesion: 0.06
Nodes (23): AdaptiveHalter, Any, ★7 Adaptive Loop Halting — velocity-based agent run termination. Complements…, Return current halter state for logging / telemetry., Tracks step-level progress and signals when a run should halt early. The halter…, Ratio of applied steps to steps attempted (0.0–1.0). Returns 1.0 when no steps…, Record one step outcome; return a halt reason or None to continue. ``status``…, MCPToolResult (+15 more)

### Community 101 - "FinancialMetrics"
Cohesion: 0.06
Nodes (46): BudgetOptimizer, CostLine, FinancialAgent, FinancialMetrics, Enum, str, Agentic CFO — autonomous financial analyst for AI infrastructure spend.…, Reallocate budget across cost lines to maximize total ROI under a fixed budget… (+38 more)

### Community 102 - "LogWatcher"
Cohesion: 0.05
Nodes (33): _auto_file_enabled(), ErrorFingerprint, LogEntry, LogWatcher, log_watcher.py — Automated log monitoring agent. Watches log files, detects…, A single error entry extracted from a log file., Generates stable fingerprints for error deduplication., Create a hash from error type, file, and normalized message pattern. (+25 more)

### Community 103 - "AgileSprint"
Cohesion: 0.05
Nodes (24): AgileSprint, An agile sprint containing user stories., Add a user story to the sprint., Remove a user story from the sprint., Total story points in the sprint., Completed story points., Return completed points history for burndown chart., Number of stories in the sprint. (+16 more)

### Community 104 - "Agent"
Cohesion: 0.05
Nodes (24): Agent, Grab Multi-Agent Support — Agent and TeamCoordinator with capability matching.…, Release a task from an agent., List all currently available agents., List agents with a capability, ordered by load., Average load across all team members., Number of agents in the team., An agent with capabilities and workload tracking. (+16 more)

### Community 105 - "failover_client.py"
Cohesion: 0.05
Nodes (54): _auto_disable(), _build_request(), _describe_registry(), _disable_unless_key_serves_other_models(), _disabled_ids(), FailoverResult, _is_billing_refusal(), _is_ollama() (+46 more)

### Community 106 - "StreamingDeltaReconstructor"
Cohesion: 0.06
Nodes (31): PostProcessHook, get_chat_history(), Return the module-level ChatHistoryStore singleton., Enum, How to truncate messages when over the context limit., Result of a context window truncation operation., TruncationResult, TruncationStrategy (+23 more)

### Community 107 - "tasks/api.py"
Cohesion: 0.12
Nodes (58): ApprovalRequest, BackgroundTasks, add_comment(), approve_checkpoint(), approve_execution(), clarify_task(), create_task(), _current_user() (+50 more)

### Community 108 - "get_task_store"
Cohesion: 0.06
Nodes (56): quick_notes_submit(), Submit a quick-note URL or instruction from the dashboard FAB., Reset the singleton (for tests)., reset_failover_manager(), Hand the 'connect & verify the repo' work to the agency's own agents. The task…, _seed_connect_task(), _heal_brain_failover(), _heal_stuck_tasks() (+48 more)

### Community 109 - "Platform Guide — the full tour"
Cohesion: 0.03
Nodes (59): 1. Clone and install, 2026-06-16, 2026-06-25, 2026-06-26, 2026-07-04, 2026-07-05, 2026-07-09, 2. Configure (+51 more)

### Community 110 - "DetectedSystem"
Cohesion: 0.05
Nodes (41): DetectedSystem, A business system detected on a company's website or in their stack., Get the most confident evidence description., OnboardingService, Workflow, Detect the Git provider from a repository URL. Args: repo_url: Repository URL…, Start the onboarding process for a company. Args: company_id: Company ID…, Schedule a fire-and-forget background task, keeping a strong reference.… (+33 more)

### Community 111 - "SeoFixer"
Cohesion: 0.08
Nodes (24): Request to remediate auto-fixable findings in a local code repository., One concrete remediation performed (or proposed) by the fixer., Result of a fixer run., SeoFixAction, SeoFixRequest, SeoFixResult, _humanize_filename(), BeautifulSoup (+16 more)

### Community 112 - "Page"
Cohesion: 0.06
Nodes (37): _login_api(), main(), _navigate_auth_callback(), _navigate_logged_out(), Page, Navigate directly to the AuthCallback page with query params., Social login buttons on the LoginPage., Verify the login page renders. (+29 more)

### Community 113 - "TokenBudget"
Cohesion: 0.06
Nodes (28): BudgetUsage, Any, agent/token_budget.py — Per-Session Token Spend Caps Track token usage per…, Raise :class:`BudgetExceededError` if the session has exceeded its cap., Reset usage counters for *session_id* (cap is preserved)., Reset token counters for all sessions (caps preserved). Called at the start of…, Reset all budgets if the UTC calendar day has changed since last reset. Safe to…, Generate a token savings analytics report. Returns per-session statistics and… (+20 more)

### Community 114 - "KnowledgeGraph"
Cohesion: 0.05
Nodes (24): KnowledgeGraph, KnowledgeNode, Enum, Obsidian Knowledge Graph — KnowledgeNode and KnowledgeGraph with typed edges.…, Find all connected components (treating edges as undirected)., Find all nodes with a given tag., Export all edges as (source, target, edge_type) tuples., Import edges from (source, target, edge_type) tuples. (+16 more)

### Community 115 - "V5App.jsx"
Cohesion: 0.04
Nodes (34): API, getLoops(), V5App, ActivationGate(), activityToAlert(), AlertsBell(), priorityConfig, _relativeTime() (+26 more)

### Community 116 - "ai_runner.py"
Cohesion: 0.07
Nodes (52): append_checkpoint(), _build_claude_command(), cmd_audit(), cmd_changelog_check(), cmd_logs(), cmd_manifest(), cmd_resume(), cmd_start() (+44 more)

### Community 117 - "test_sqlite_store.py"
Cohesion: 0.06
Nodes (56): asyncio, tests/test_sqlite_store.py — Unit tests for the SQLite storage adapter. These…, The exact query shape backend/server.py's provider "Set default" uses: clear…, Unfiltered count uses the SELECT COUNT(*) fast path and must match the number…, estimated_document_count mirrors an unfiltered count_documents., db['tasks'] must work like db.tasks (motor exposes both)., TaskStore(db=SQLiteStore) must not raise 'not subscriptable'. This is the exact…, B608 guard: all collections in _COLLECTIONS must still be instantiable. (+48 more)

### Community 118 - "test_control_plane_api.py"
Cohesion: 0.04
Nodes (35): get_public_doctor(), Public Doctor endpoint — no authentication required. Returns system-level…, get_store(), Return the active store singleton, creating it on first call., set_scheduler(), Path, Start RuntimeManager, TaskDispatcher, SCHEDULER, and self-bootstrap. Returns a…, Start the 24×7 CEO agency loop that *proactively* generates work. Without this… (+27 more)

### Community 119 - "ProvidersScreen.jsx"
Cohesion: 0.05
Nodes (40): createProvider(), deleteModel(), deleteProvider(), getBrainConfig(), getBrainProviders(), getLocalBrainState(), getProviderPolicy(), listModels() (+32 more)

### Community 120 - "config.py"
Cohesion: 0.07
Nodes (55): _apply_env_overrides(), _apply_key_env(), _build(), _coerce(), config_dir(), _env_key_names(), expand_env(), _fields_of() (+47 more)

### Community 121 - "probe_model_liveness"
Cohesion: 0.05
Nodes (44): _describe_http_status(), probe_model_liveness(), _probe_ollama(), _probe_openai_compat(), ProbeResult, BaseModel, services/brain_liveness.py — Provider liveness prober for the brain switcher.…, Probe an OpenAI-compatible provider (Cerebras / Groq / NIM / Z.ai / Aerolink). (+36 more)

### Community 122 - "_scanner"
Cohesion: 0.06
Nodes (27): _is_blocked_host(), Cheap (no-DNS) SSRF check for headless-browser subrequests. A rendered page's…, Tests for the scanner's headless-render fallback (JS-rendered / bot-protected…, The scan flow must invoke the render fallback when static detection is empty…, BuiltWith-style off-site identification: a CNAME chain that points at a known…, A scan must never hang past its wall-clock budget — a slow/blocked domain has…, Last-resort fallback that asks builtwith.com what it already knows about a…, Replace curl_cffi's AsyncSession.get with a canned response. (+19 more)

### Community 123 - "RewardScorer"
Cohesion: 0.06
Nodes (28): _infer_parameters_from_func(), Infer a basic JSON Schema from a function's signature., _inject_tool_results_as_messages(), _parse_tool_calls_from_response(), Parse OpenAI tool_calls from a model response. Handles: - Direct JSON…, Inject tool call results as follow-up messages for multi-turn execution. When…, get_reward_scorer(), _nvidia_api_key() (+20 more)

### Community 124 - "Command"
Cohesion: 0.06
Nodes (22): Command, CommandCategory, CommandDispatcher, Enum, SuperClaude Slash Commands — CommandDispatcher with registration, role gating,…, Parse and execute a slash command from raw text. Args: text: Raw command text,…, Return all enabled commands in a given category., Return all registered commands. (+14 more)

### Community 125 - "CoworkSession"
Cohesion: 0.06
Nodes (18): ContributorState, CoworkSession, Enum, str, Claude Cowork — shared AI coding sessions with real-time sync. Enables multiple…, A shared AI coding session with multiple human contributors. Manages turn-…, Request editing control. Returns True if granted. Grant rules: - Host can…, Role within a cowork session. (+10 more)

### Community 126 - "_get_provider_policy"
Cohesion: 0.05
Nodes (51): _get_provider_policy(), get_provider_policy_route(), Read the durable provider policy from DB, falling back to a safe default.…, Persist the durable provider policy and return the new state. Also writes to…, Return the provider policy (paid-provider kill switch state)., seed_default_providers(), _set_provider_policy(), _best_cloud_primary_base() (+43 more)

### Community 127 - "useSafeData"
Cohesion: 0.05
Nodes (34): changeUserRole(), createApiKey(), deleteApiKey(), setUserOnboarding(), useSafeData(), AdminOnboardingPanel(), AdminScreen(), errText() (+26 more)

### Community 128 - "test_context_rulebook.py"
Cohesion: 0.06
Nodes (53): Module, stmt, _bound_names(), _good_result(), _guard_statements(), _load(), ModuleType, parametrize (+45 more)

### Community 129 - "ArtifactStore"
Cohesion: 0.07
Nodes (25): Path, tests/test_artifact_store.py — Unit tests for workflow/artifact_store.py., Verify artifacts that are stored as JSON (e.g., CheckRun results)., Writing the same (run_id, name) twice should update, not duplicate., store(), TestArtifactStoreDeletion, TestArtifactStoreJSONArtifact, TestArtifactStoreListing (+17 more)

### Community 130 - "WorkflowEngine"
Cohesion: 0.08
Nodes (30): Any, Connection, Path, PhaseType, WorkflowRun, CRISPY workflow engine — phase sequencer + gate controller. GATE: Golden Path…, Return the AgentSwarm singleton if available, else None., Append an event to the workflow event log. (+22 more)

### Community 131 - "CEOSupervisor"
Cohesion: 0.06
Nodes (37): get_ceo_dispatcher(), Return the shared CEODispatcher singleton., Reset the singleton (test helper)., reset_ceo_dispatcher(), CEOSupervisor, _env_flag(), _env_int(), Any (+29 more)

### Community 132 - "test_provider_state_durability.py"
Cohesion: 0.04
Nodes (21): fake_mongo(), _FakeCollection, _FakeDb, isolated_state(), _live_mongo_url(), Operator provider state must survive a redeploy. The per-provider kill switch…, Tests must never mutate a shared operational store., The storage layer's localhost default is a placeholder, not config. Treating it… (+13 more)

### Community 133 - "InferenceCache"
Cohesion: 0.05
Nodes (27): CachedLLMClient, Any, Cached LLM Client wrapper. Drop-in wrapper around any LLM API call that…, Return performance metrics for this client instance., Try to extract token count from various response formats., Wraps an LLM call function with inference caching. Usage: from agent.cached_llm…, Execute an LLM completion, using cache when available. Args: model: Model…, CacheEntry (+19 more)

### Community 134 - "ToolRegistry"
Cohesion: 0.06
Nodes (24): Any, Path, Register a tool definition., Decorator to register a function as an agent tool. Usage::…, Remove a tool from the registry. Returns True if removed., Look up a tool by name., Return all registered tools., Find tools that advertise a specific capability. (+16 more)

### Community 135 - "CheckpointStore"
Cohesion: 0.09
Nodes (27): Checkpoint, checkpoint_agent_state(), _checkpointing_enabled(), CheckpointStore, cleanup_checkpoints(), _get_checkpoint_store(), Any, Path (+19 more)

### Community 136 - "RepowiseIntelligence"
Cohesion: 0.06
Nodes (27): Any, Path, Build symbol-level dependency graph for Python files., Build git intelligence: hotspots, ownership, co-change pairs., Run a git command and return stdout as string., Compute cyclomatic complexity for Python files. Returns 0 for non-Python files…, Extract docstrings and store as documentation., Get the latest commit hash. (+19 more)

### Community 137 - "test_sam_voice.py"
Cohesion: 0.04
Nodes (46): Any, Process a voice command and return SAM's spoken response. Args: text: The…, Call the NVIDIA NIM LLM (free tier) for SAM's response., Rule-based fallback when the LLM is unavailable., A single voice conversation session with SAM., SamConversation, agent/sam.py must call emit_agency_observation for voice commands., test_sam_py_traces_voice_commands() (+38 more)

### Community 138 - "Feature Guide"
Cohesion: 0.05
Nodes (37): 10. Langfuse Observability, 11. Coding Agent API, 12. Browser Admin UI, 13. Telegram Remote Control Bot, 14. Tunnel — Permanent Static URL via ngrok, 15. CORS Support, 16. Streaming Support, 17. Workspace Isolation (+29 more)

### Community 139 - "_resolve_brain_provider"
Cohesion: 0.06
Nodes (36): Resolve the LLM endpoint for agent execution (module-level, #522 failover).…, _resolve_brain_provider(), Critical failover-safety test: if every free provider's base URL is excluded…, When the ONLY configured provider is a paid one (e.g. operator set…, When only Anthropic is configured AND allow_paid=False (default), the resolver…, When AGENT_LLM_BASE_URL is set, the brain resolver must return that endpoint —…, When a free cloud provider (NVIDIA NIM, etc.) is configured, the brain resolver…, _run() (+28 more)

### Community 140 - "test_issue_intake.py"
Cohesion: 0.08
Nodes (49): _capability_tags(), create_task_from_oldest_open_issue(), intake_issue(), _issue_labels(), issue_source_id(), map_issue_to_task(), Any, Task (+41 more)

### Community 141 - "test_kimi_bridge_server.py"
Cohesion: 0.06
Nodes (36): chat_completions(), ChatCompletionRequest, _content_to_str(), _ContentPart, health(), lifespan(), list_models(), _Message (+28 more)

### Community 142 - "AutonomyTracker"
Cohesion: 0.05
Nodes (24): AutonomyCounter, AutonomySnapshot, AutonomyTracker, get_tracker(), Any, agent/kpi.py — Autonomy KPIs: evidence capture and metrics tracking. Tracks key…, Return a point-in-time snapshot of all KPIs., Reset all counters (test helper). (+16 more)

### Community 143 - "ReactScratchpad"
Cohesion: 0.06
Nodes (22): Declarative configuration for a specialized sub-agent role. Each sub-agent gets…, SubAgentConfig, build_react_prompt(), parse_react_response(), Any, Parse a ReAct-format response into structured components. Intended caller:…, Structured scratchpad that accumulates across tool calls within a step. Each…, Record a reasoning step before taking action. (+14 more)

### Community 144 - "diagnostics.py"
Cohesion: 0.07
Nodes (48): _check_background_liveness(), _check_ci_parity(), _check_company_graph(), _check_disk(), _check_event_log_integrity(), _check_feature_matrix(), _check_github_readiness(), _check_ollama() (+40 more)

### Community 145 - "audit"
Cohesion: 0.06
Nodes (26): audit(), get_audit_log(), is_admin(), is_power_user_or_above(), mask_dict(), mask_secret(), Any, Request (+18 more)

### Community 146 - "GoalRecord"
Cohesion: 0.06
Nodes (33): Attempt, _backend(), CEOLedger, get_ceo_ledger(), GoalRecord, _now(), Any, services/ceo_ledger.py — durable record of what the CEO is driving to closure.… (+25 more)

### Community 147 - "ChatHistoryStore"
Cohesion: 0.07
Nodes (25): ChatHistoryStore, Any, Connection, Delete a session and all its messages. Returns True if deleted., List sessions ordered by most recently updated., Return total session and message counts., Append a message to the session. Returns the message's sequence number.…, Append multiple messages at once. Returns number of messages appended. (+17 more)

### Community 148 - "WorkspaceManager"
Cohesion: 0.05
Nodes (13): If a symlink inside the workspace points outside, resolve_path blocks it., Only expired workspaces (past retention TTL) are cleaned up., Two threads creating the same session/job should not corrupt state., TestWorkspaceLifecycle, TestWorkspaceManifest, TestWorkspaceResume, Any, First-class workspace isolation manager. Every session/job gets its own… (+5 more)

### Community 149 - "api.ts"
Cohesion: 0.10
Nodes (44): adminBootstrap(), adminCreateProvider(), adminCreateWorkspace(), adminDeleteProvider(), adminDeleteWorkspace(), adminGetBrainPolicy(), adminGetProviderRoleTags(), adminHeaders() (+36 more)

### Community 150 - "test_telegram_freebuff.py"
Cohesion: 0.07
Nodes (46): cmd_freebuff(), _model_keyboard(), _parse_callback(), _parse_user_ids(), _process_callback(), Extract numeric Telegram user IDs from a raw env value, tolerantly. Accepts…, Resolve the ALLOWED/ADMIN Telegram user-ID sets. ``TELEGRAM_CHAT_ID`` is the…, Send a message with an inline keyboard (list of button rows). (+38 more)

### Community 151 - "AGENTS.md — Source of Truth for All AI Agents"
Cohesion: 0.04
Nodes (50): 1. Language & Runtime, 2. Async, 3. Data Models, 4. Logging, 5. Error Handling, 6. Security, 7. Comments, 8. File Size (+42 more)

### Community 152 - "LLMRouter"
Cohesion: 0.07
Nodes (28): Attempt, payload_key(), Exact-match cache key over the fields that change the answer. Routing…, describe(), The operator-facing reason string for an unfixable status., Read the environment variables named in ``env_names`` into a key list. Order is…, resolve_keys(), LLMRouter (+20 more)

### Community 153 - "BackgroundAgent"
Cohesion: 0.06
Nodes (30): BackgroundAgent, _now(), Any, agent/background.py — Background Agent An always-on worker thread that…, Enqueue *task* for processing. Returns the task (with task_id set)., Convenience: create a task and submit it in one call., Real handler — dispatches through AgentRunner when available. HARDENED (PR…, Always-on worker that drains a task queue on a daemon thread. GATE: Golden Path… (+22 more)

### Community 154 - "test_portfolio_intake.py"
Cohesion: 0.07
Nodes (40): Issue title: the failure mode plus how hard it is recurring., Stable id for a trend alert (matches ``TrendWatcher._sig`` shape)., trend_id(), map_initiative_to_task(), materialize_committed(), _portfolio_materialize_enabled(), portfolio_source_id(), Any (+32 more)

### Community 155 - "persist_plan_spec"
Cohesion: 0.07
Nodes (37): build_spec_router(), Any, APIRouter, backend/spec_router.py — review/approve persisted plan specifications. Surfaces…, await_spec_approval(), _db(), _flag(), get_spec() (+29 more)

### Community 156 - "CLAUDE.md — Master Architect Operating Manual"
Cohesion: 0.04
Nodes (49): 0. The Golden Rule, 10. CI/CD Standards, 10. Testing Constitution, 11. Rewrite Strategy, 12. Changelog Rule, 13. Autonomous Development Policy, 1. What This Repo Does, 2. Architectural Principles (+41 more)

### Community 157 - "test_response_cache.py"
Cohesion: 0.12
Nodes (47): _cache_key(), cache_stats(), clear_cache(), get_cached(), is_cacheable(), put_cached(), Any, packages/ai/response_cache.py — LRU+TTL in-memory response cache for the… (+39 more)

### Community 158 - "telegram_bot.py"
Cohesion: 0.09
Nodes (47): get_decisions_store(), Process-wide DecisionsStore singleton (resettable via db_path arg)., Return a Markdown-v1-safe preview string under ``max_chars``. Used by the…, sanitize_paste_for_preview(), _admin_headers(), _api_headers(), _check_rate_limit(), cmd_control() (+39 more)

### Community 159 - "test_agent_runner.py"
Cohesion: 0.07
Nodes (48): _make_runner(), MonkeyPatch, Path, Reproduce the exact error from the screenshot: slices present, goal absent., End-to-end: model returns CRISPY-style slices, plan should still execute., spawn_subagent creates a child AgentRunner and returns a condensed result., When all steps touch different files, run() delegates to MultiAgentSwarm., Steps sharing a file must run sequentially — _maybe_run_parallel returns None. (+40 more)

### Community 160 - "WorkspaceTools"
Cohesion: 0.06
Nodes (33): repowise.py — RepowiseIntelligence: context packing and dependency analysis., tools.py — WorkspaceTools: read/write/search and diff application (risky…, Return a previously saved memory value, or an empty string if absent., Persist a key/value pair to the user's profile store., Delegate to RepowiseIntelligence for a natural-language codebase question., Delegate to RepowiseIntelligence for a semantic/text codebase search., Delegate to RepowiseIntelligence to list architectural decision nodes., Return a high-level repository map and hotspot summary. (+25 more)

### Community 161 - "test_slop_gate.py"
Cohesion: 0.07
Nodes (44): _extract_mentioned_paths(), Pick the auto-PR model from the recommended free-cloud chain by key. Mirrors…, Extract plausible file paths from issue text., Read existing files for codebase context (max 8000 chars total)., _read_grounding_files(), _select_brain(), diff_is_sloppy(), is_destructive_overwrite() (+36 more)

### Community 162 - "_StubProvider"
Cohesion: 0.09
Nodes (24): _models_to_try(), Order the models to attempt on *provider*, correcting a stale catalogue. Cache-…, _mock_get(), _ok(), asyncio, A stale model catalogue must not be mistaken for a dead account.…, None means "could not find out" and must not read as "no models"., Otherwise every failed call re-asks a provider that is already down. (+16 more)

### Community 163 - "Settings"
Cohesion: 0.05
Nodes (22): _get_settings(), When True, the governance layer evaluates and audits agent actions. This is…, Typed configuration loaded from environment variables., When True, approval-gated actions self-approve. Local dev only., ``RENDER_SERVICE_IDS`` split into a clean list (empty when unset)., True when there is both an API key and an endpoint to reach., When True, the Render ops loop runs. On by default. Also requires…, When True, mutating Render MCP tools may be called. Default False. (+14 more)

### Community 164 - "activation_api.py"
Cohesion: 0.09
Nodes (46): activate_instance(), ActivateRequest, ActivateResponse, activation_audit_log(), activation_status(), ActivationStatusResponse, _append_audit(), AuditLogEntry (+38 more)

### Community 165 - "render_ops.py"
Cohesion: 0.05
Nodes (32): agent/mcp_client.py — Async MCP client for the mcp-server Docker container.…, _file_issue(), _latest_metric_value(), _note_recurrence(), _parse_timestamp(), Any, datetime, services/render_ops.py — autonomous Render debugging + environment monitoring.… (+24 more)

### Community 166 - "test_agent_tool_governance.py"
Cohesion: 0.08
Nodes (46): One tool selection parsed from the executor model's JSON response., ToolCall, _drive(), _enforce(), governance_on(), _observations(), Any, MonkeyPatch (+38 more)

### Community 167 - "AgentProfile"
Cohesion: 0.09
Nodes (25): agents/__init__.py — CRISPY multi-agent coding system., AgentProfile, _catalog_defaults(), _catalog_provider(), _get_defaults(), load_all_profiles(), make_architect_profile(), make_coder_profile() (+17 more)

### Community 168 - "MetricsRegistry"
Cohesion: 0.07
Nodes (23): _Counter, _escape(), _Gauge, _Histogram, _labels(), MetricsRegistry, Any, packages/llm/metrics.py — Prometheus metrics without the client library. The… (+15 more)

### Community 169 - "test_e2b_task_wiring.py"
Cohesion: 0.08
Nodes (42): _build_coordinator(), _clean_e2b_env(), _FakeCompany, _FakeCompanyGraphStore, _FakeRepoConnection, _make_task(), Task, tests/test_e2b_task_wiring.py — Task.company_id → spec.context repo_url wiring.… (+34 more)

### Community 170 - "OnboardingScreen.jsx"
Cohesion: 0.05
Nodes (30): createCompany(), getCompany(), getOnboardingProgress(), listSpecialists(), scanRepo(), scanWebsite(), startOnboarding(), submitOnboardingAnswers() (+22 more)

### Community 171 - "OllamaCircuitBreaker"
Cohesion: 0.08
Nodes (36): _Circuit, _enabled(), _failure_threshold(), get_circuit_breaker(), OllamaCircuitBreaker, Per-model circuit breaker for Ollama backend health. Tracks consecutive failure…, Record a successful response; close the circuit., Record a 5xx error; open the circuit after threshold is reached. (+28 more)

### Community 172 - "SetupChecker"
Cohesion: 0.06
Nodes (25): main(), OllamaManager, OsDetector, Path, Detect operating system and available interpreters., Return normalized OS name., Detect PowerShell (Windows) or Bash (Unix)., Print colored message. (+17 more)

### Community 173 - "PromptCacheManager"
Cohesion: 0.06
Nodes (20): CacheEntry, CacheStats, get_prompt_cache(), PromptCacheManager, Any, Compute a deterministic cache key from the stable prefix. The stable prefix is…, Hash a system prompt and model for KV cache fingerprinting., Return the instance ID that has this prefix cached, or None. Performs an LRU… (+12 more)

### Community 174 - "test_quick_note.py"
Cohesion: 0.08
Nodes (30): _fetch_text(), _now(), process_note(), Any, Path, QuickNote, agent/quick_note.py — iPhone Quick Note integration. Persistent URL queue +…, GET *url* and return plain text (HTML tags stripped, max *max_chars*). (+22 more)

### Community 175 - "test_trend_scoping.py"
Cohesion: 0.11
Nodes (43): _company_attr(), company_stack_tags(), extract_stack_tags(), fan_out_trend(), fan_out_trends(), is_code_change_trend(), map_trend_to_company_task(), Any (+35 more)

### Community 176 - "test_audit.py"
Cohesion: 0.07
Nodes (39): AuditMessage, AuditSession, create_session(), delete_session(), get_session(), list_sessions(), Any, Audit session management for multi-turn conversations. This module provides in-… (+31 more)

### Community 177 - "get_failover_manager"
Cohesion: 0.07
Nodes (35): brain_failover_status(), brain_providers(), openclaw_websocket(), websocket, Return the brain failover health snapshot. Shows every configured provider, its…, Every configured provider with its health AND its on/off state. Powers the…, WebSocket endpoint for iOS / mobile web UI pairing + command routing., describe_disabled_reason() (+27 more)

### Community 178 - "[Unreleased]"
Cohesion: 0.04
Nodes (44): [5.0.0], Added, Added, Added, Added, Added, Added, Added (+36 more)

### Community 179 - "[Unreleased]"
Cohesion: 0.04
Nodes (44): [5.0.0], Added, Added, Added, Added, Added, Added, Added (+36 more)

### Community 180 - "test_integration_c4_c5_c6_d3.py"
Cohesion: 0.07
Nodes (29): CostAttributor, CostReport, get_cost_attributor(), Any, Tracks and attributes LLM costs per model, phase, and provider. Usage:: attr =…, Record a single LLM call's usage., Batch record multiple usage entries. Returns number recorded., Estimate USD cost for a given model and token count. Looks up the per-model… (+21 more)

### Community 181 - "test_agent_free_brain.py"
Cohesion: 0.05
Nodes (35): livenim, allow_paid_brain(), is_anthropic_model(), True only when the operator explicitly opted into a paid (Anthropic) brain.…, True when *model* names a paid Anthropic/Bedrock-Claude model. Covers native…, Resolve the free NVIDIA NIM brain from env, or ``None`` if unconfigured.…, resolve_free_nvidia_brain(), _FakeAsyncClient (+27 more)

### Community 182 - "HealthStatus"
Cohesion: 0.06
Nodes (17): GroqProvider, Provider, Groq provider adapter — free, fast LLM (deepseek-r1-distill-llama-70b)., NvidiaProvider, Provider, NVIDIA NIM provider adapter — wraps the existing provider_router logic. This is…, NVIDIA NIM — free LLM provider (meta/llama-3.3-70b-instruct)., OllamaProvider (+9 more)

### Community 183 - "WorkflowBuildRequest"
Cohesion: 0.07
Nodes (30): engine(), WorkflowEngine, tests/test_contracts_agency.py — Contract tests for agency core autonomy…, Contract: WorkflowEngine cannot skip the gate state machine., Contract: No code path may advance past awaiting_approval unless gate.status ==…, Create a run and manually place it in awaiting_approval., Contract: Cannot approve a run in 'pending' state., Contract: Can approve a run in 'awaiting_approval' state. (+22 more)

### Community 184 - "test_features_api.py"
Cohesion: 0.05
Nodes (4): _auth_override(), client(), _fake_auth(), Integration tests for all new feature API routes in proxy.py.

### Community 185 - "test_video_transcript.py"
Cohesion: 0.05
Nodes (33): parametrize, Tests for video transcript extraction (`.github/scripts/video_transcript.py`).…, Events without `segs` carry no text and must not produce stray spaces., This format double-encodes: `&amp;#39;` must resolve to a single quote., Regex-terminated matching truncates this; brace matching must not. The blob…, A title containing a brace must not unbalance the matcher., An unfamiliar page shape must yield empties, never raise., A non-video URL must short-circuit before any request is attempted. (+25 more)

### Community 186 - "activation.py"
Cohesion: 0.09
Nodes (39): activation_required(), ActivationResult, _b64url_decode(), _b64url_encode(), _decode_jwt_unverified(), _generate_token_for_owner(), get_activation(), get_or_create_instance_id() (+31 more)

### Community 187 - "facade.py"
Cohesion: 0.07
Nodes (38): _get_current_user_thunk(), _get_optional_user_thunk(), Request, create_refresh_token(), get_current_user(), get_optional_user(), Get user if authenticated, otherwise return None (for public endpoints)., Item (+30 more)

### Community 188 - "emit_chat_observation"
Cohesion: 0.09
Nodes (35): observability_diag_public(), PUBLIC diagnostic endpoint for Langfuse — no auth required. Returns exactly…, CommercialEquivalent, estimate_commercial_equivalent_usd(), get_prices(), _load_from_env(), _parse_mapping(), Any (+27 more)

### Community 189 - "Part A — CodeRabbit review fixes for this PR (do first, small)"
Cohesion: 0.05
Nodes (42): A1 — `docs/changelog.md`: add the two autonomy docs under `### Added` ✅ trivial, A2 — `docs/telegram-bot.md`: fix broken charter links (MD + path), A3 — `docs/telegram-bot.md`: add language to fenced block (MD040), A4 — `.env.example`: use exact var name in the shortcut comment, A5 — `services/workflow_orchestrator.py`: surface notify failures at WARNING, A6 — `telegram_bot.py`: avoid double-approve in the `wfo_approve` path ⚠️ behavioural, A7 — `telegram_service.py`: escape Markdown-v1 reserved chars in approval text ⚠️ correctness, A8 — `render.yaml`: propagate Telegram vars to the worker service (+34 more)

### Community 190 - "Docker Agent Runtimes Setup"
Cohesion: 0.05
Nodes (41): 1. Register Runtimes, 2. Verify Installation, 3. Access Agents via API, Agent Runtime Setup, Agents not appearing in API responses, Initial Setup, MongoDB Connection, No agents showing after registration (+33 more)

### Community 191 - "anthropic_compat.py"
Cohesion: 0.09
Nodes (31): _build_anthropic_response(), _content_block_to_text(), _emit_safely(), _finish_reason_to_stop_reason(), handle_anthropic_messages(), _messages_to_openai(), _openai_choice_to_anthropic_content(), _post_anthropic_with_fallback() (+23 more)

### Community 192 - "TestPayloadNormalisation"
Cohesion: 0.07
Nodes (21): _as_list(), _coerce_payload(), Any, Return tool output as Python data. MCP tool results arrive either as…, Normalise a tool payload into a list of dicts. Upstream tools variously return…, Unwrap a nested envelope such as ``{"service": {...}}`` when present., Run the MCP handshake once per client instance. Streamable-HTTP servers create…, Call a Render MCP tool and return its decoded payload. Raises… (+13 more)

### Community 193 - "RuntimeManager"
Cohesion: 0.05
Nodes (23): DockerAgentAdapter, Any, TaskResult, TaskSpec, Adapter that runs agent tasks inside isolated Docker containers., Check whether Docker is available and report the adapter's runtime health.…, Any, RoutingDecision (+15 more)

### Community 194 - "test_workspace_isolation.py"
Cohesion: 0.17
Nodes (24): Tests for workspace isolation model (Area A). Covers: - Unique workspace path…, TestConcurrency, TestCrossSessionIsolation, TestJobIdValidation, TestPathSafety, TestWorkspaceCleanup, TestWorkspaceMetrics, TestWorkspaceNotFound (+16 more)

### Community 195 - "FilterResult"
Cohesion: 0.08
Nodes (24): filter_output(), FilterResult, get_output_filter(), get_savings_summary(), OutputFilter, Any, agent/output_filter.py — LLM Output Compression & Token Savings Inspired by…, Filter and compress command outputs to reduce LLM token consumption. Provides… (+16 more)

### Community 196 - "v4_api.py"
Cohesion: 0.10
Nodes (40): _get_cached_tasks(), _get_tasks_cache_lock(), _load_improvement_state(), Any, BaseModel, get, Lock, post (+32 more)

### Community 197 - "README.md"
Cohesion: 0.05
Nodes (29): Agent Readiness Report, Build System — 100/100, Dev Environment — 100/100, Documentation — 100/100, Observability — 100/100, Security — 100/100, Style And Validation — 100/100, Task Discovery — 100/100 (+21 more)

### Community 198 - "Persistent Memory System"
Cohesion: 0.05
Nodes (41): 1. **Semantic Memory Categorization**, 1. **Use Appropriate Scopes**, 2. **Prioritize Effectively**, 2. **Scope-Based Auto-Loading**, 3. **Priority-Based Retrieval**, 3. **Use Semantic Categories**, 4. **Cross-Tool Compatibility**, 4. **Tag Liberally** (+33 more)

### Community 199 - "resolve_component_model"
Cohesion: 0.06
Nodes (41): Resolve the model id for a component's role on a provider. Parameters…, Convenience: resolve all four role models for a component. Returns a dict with…, resolve_component_model(), resolve_component_role_models(), tests/test_unit6_resolve_component_model.py — UNIT 6 regression tests. Verifies…, When the DB cache is fresh AND provider matches the active primary, the DB-…, When the DB primary differs from the requested provider, the catalog preset for…, When `provider` is None, the DB primary's saved model wins. (+33 more)

### Community 200 - "JCodeAdapter"
Cohesion: 0.07
Nodes (19): JCodeAdapter, Any, Path, TaskResult, TaskSpec, Write .jcode/mcp.json in the workspace, pointing at our proxy's MCP endpoint.…, Resolve the default executor model via the catalog (UNIT 7). Was hardcoded to…, Adapter for jcode — TIER 2 high-performance Rust coding agent. (+11 more)

### Community 201 - "analyze_page"
Cohesion: 0.08
Nodes (19): analyze_page(), _count_syllables(), estimate_pixel_width(), flesch_reading_ease(), _host_key(), is_internal(), BeautifulSoup, Approximate SERP rendering width of ``text`` in pixels. (+11 more)

### Community 202 - ".get_workspace"
Cohesion: 0.09
Nodes (23): _derive_workspace_root(), Path, Create an isolated workspace for a session and optional job. Creates the…, Retrieve the WorkspaceManifest for a given session and optional job. Looks up…, Mark a workspace as active (in-use)., Pause a workspace (e.g. between agent steps)., Mark a workspace as completed., Mark a workspace as failed. (+15 more)

### Community 203 - "TrendWatcher"
Cohesion: 0.15
Nodes (14): Any, AsyncClient, Path, Fetches AI trend signals from many public sources and surfaces relevant ones., Fetch all sources in parallel; return new alerts sorted by relevance., Fan trends out to onboarded companies whose stack matches (G4). For each…, Dispatch high-relevance alerts to the Hermes sidecar for action. Only…, TrendAlert (+6 more)

### Community 204 - "AgileManager"
Cohesion: 0.06
Nodes (15): AgileManager, Manages multiple agile sprints with velocity tracking., List all active sprints., Predict next sprint velocity from historical data., Number of managed sprints., InitiativeProgress, Percentage of linked sprint points completed., Aggregate delivery progress per initiative from its linked sprints. Reads each… (+7 more)

### Community 205 - "BudgetTracker"
Cohesion: 0.08
Nodes (24): AlertHandler, BudgetTracker, Counter, _Dimensions, _month(), Any, Register a callback fired when a spend threshold is crossed., Fold a new key into "other" once the dimension is at its cap. (+16 more)

### Community 206 - "compare_runtimes.py"
Cohesion: 0.07
Nodes (21): compare(), main(), Any, scripts/compare_runtimes.py — head-to-head runtime comparison. Answers the…, Check an operator-supplied task file before anything executes., render(), _run_one(), RunRecord (+13 more)

### Community 207 - "ContextWindowManager"
Cohesion: 0.09
Nodes (16): ContextWindowManager, get_context_window_manager(), Any, Return True if the estimated tokens exceed the model's context limit., Truncate messages to fit within the model's context window. Args: messages:…, Return the context window size for a model. Looks up the model in the…, Estimate token count for a list of messages. Uses a character-based heuristic…, Estimate token count using tiktoken (more accurate, requires install). (+8 more)

### Community 208 - "Any"
Cohesion: 0.07
Nodes (23): get_tracer(), _NoOpSpan, _NoOpTracer, otel_middleware_factory(), otel_status_error(), otel_status_ok(), Any, Exception (+15 more)

### Community 209 - "test_e2b_data_flow.py"
Cohesion: 0.07
Nodes (30): fake_sandbox(), _FakeAsyncSandboxClass, _FakeCmdResult, _FakeCommands, _FakeFiles, _FakeSandbox, Any, asyncio (+22 more)

### Community 210 - "test_trend_watcher.py"
Cohesion: 0.08
Nodes (22): _FakeClient, _FakeResp, asyncio, Tests for agent/trend_watcher.py, Ensure expanded keyword set covers key new categories., setup_database_moks(), test_fetch_arxiv(), test_fetch_github_trending() (+14 more)

### Community 211 - "OrchestratorSupervisor"
Cohesion: 0.08
Nodes (22): Return orchestrator queue depth, active runs, and supervisor state (#522)., workflow_orchestrator_status(), codeql_count(), dependabot_count(), main(), Any, _repo_parts(), _request() (+14 more)

### Community 212 - "Kept Rules — the 44 that survive the audit"
Cohesion: 0.05
Nodes (36): C1 — The bill of materials is wrong in both directions, C2 — Three different answers to "where do I read env vars?", C3 — Two different file-size limits, C4 — The frontend does not deploy to Vercel, C5 — The documented P0 escape hatch does not exist, C6 — `CLAUDE.md` §14.11 conflicts with §14.9, C7 — Two `§10` headings in `CLAUDE.md`, C8 — Duplicated rule sets that have already drifted (+28 more)

### Community 213 - "getBackendUrl"
Cohesion: 0.10
Nodes (31): getAccessToken(), getApiUrl(), getAuthHeaders(), getBackendUrl(), getDefaultBackendUrl(), ActivityEvent, AgentActivityFeedProps, ActivityEventRow() (+23 more)

### Community 214 - "policy.py"
Cohesion: 0.07
Nodes (25): _action_matches(), _as_list(), GroupPolicy, _host_matches(), Mode, _normalise_path(), _path_matches(), Any (+17 more)

### Community 215 - "test_schedule_backlog_drain.py"
Cohesion: 0.10
Nodes (35): _every_minute_one_shot(), _FakePersistence, _one_shot(), asyncio, Why the 2026-08-01 backlog never drained, despite a fix already existing.…, A timestamp we cannot parse must not authorise a delete., An agency-directive-shaped row: cron="* * * * *", uniquely named., 2026-08-03: the 7-day fallback let a live crash loop regrow the backlog from a… (+27 more)

### Community 216 - "_run"
Cohesion: 0.07
Nodes (18): _patch_send_message(), tests/test_telegram_inbound.py Pytest coverage for the Step 1 inbound-routing…, ``_resolve_reply_to_decision`` returns the durable link from SQLite.\n, ``/redirect`` command: admin-only, prefix-dispatched, idempotent shape., ``/paste <abs-path>`` command: admin gate + path check + truncation., ``_handle_big_paste`` writes to disk and short-replies., ``_route_plain_text`` classifies and dispatches per the documented map., Return a Telegram nested-message-shaped dict for resolve-reply-to tests. (+10 more)

### Community 217 - "AgentJobError"
Cohesion: 0.09
Nodes (16): AgentJobError, AgentJobResult, Any, BaseModel, field_validator, agent/contract.py — Typed public contract for the agent job lifecycle. Phase 1…, Structured error payload attached to a failed job., Typed result returned by a completed agent job. The ``response`` field is the… (+8 more)

### Community 218 - "KnowledgeScreen.jsx"
Cohesion: 0.09
Nodes (29): createWikiPage(), deleteSource(), deleteWikiPage(), getCompanyGraph(), getSource(), getWikiPage(), ingestSource(), lintWiki() (+21 more)

### Community 219 - "TestEstimateTokensForMessages"
Cohesion: 0.06
Nodes (12): _estimate_tokens_for_messages(), _normalize_anthropic_output_format(), Estimate input token count for an Anthropic-format message list. Uses a simple…, Translate Anthropic ``output_format`` into an Ollama ``format`` field. Modifies…, Daily automation tests — 2026-05-15 Covers three features implemented in this…, Integration tests for POST /v1/messages/count_tokens., Unit tests for _normalize_anthropic_output_format., Caller adds anthropic-beta header when _normalize returns True. (+4 more)

### Community 220 - "AuditLog"
Cohesion: 0.08
Nodes (29): Replace the process-wide store. Tests only., reset_approval_store(), AuditEvent, AuditLog, One governed action, fully described. Field order follows the…, One-line JSON, suitable for a SIEM shipper tailing the log., Bounded in-memory ring buffer plus a structured log stream. The ring buffer…, Store and emit *event*. Never raises. (+21 more)

### Community 221 - "TestClient"
Cohesion: 0.07
Nodes (25): backend_jwt(), proxy_client(), MonkeyPatch, TestClient, Regression test for /api/auth/me — verifies the critical endpoint on both the…, TestClient against proxy.py:app with a known API key seeded., API-key-based /api/auth/me on proxy.py (port 8000)., GET /api/auth/me with valid API key → 200 with derived profile. (+17 more)

### Community 222 - "PatternConsolidation"
Cohesion: 0.10
Nodes (9): PatternConsolidation, Group memories into clusters by tag overlap., Jaccard similarity of tag sets., Run the full consolidation cycle., Identifies clusters of related DreamMemory fragments and consolidates them into…, _make_memory(), Tests for agents.memory_consolidation — Dream Memory Consolidation., TestDreamMemory (+1 more)

### Community 223 - "traffic_director.py"
Cohesion: 0.08
Nodes (25): provider_max_parallel(), provider_max_tpm(), Return the operator-configured tokens/min cap for *provider*. Reads…, Return the operator-configured in-flight request cap for *provider*. Reads…, Return the configured traffic-distribution strategy (lower-cased). Reads…, routing_strategy(), active_strategy(), provider_id_of() (+17 more)

### Community 224 - "ServiceDaemon"
Cohesion: 0.07
Nodes (26): configure(), get_status(), health(), BaseModel, get, post, Validate configured paths., Check if proxy is running. (+18 more)

### Community 225 - "TaskDispatcher"
Cohesion: 0.08
Nodes (23): Re-queue BLOCKED tasks that have cooled down and are ready for retry., Polls for queued task work and executes it through the coordinator. Crash…, Re-queue tasks stranded by a prior crash or hard-kill., TaskDispatcher, _make_task(), asyncio, Task, TaskStatus (+15 more)

### Community 226 - "ContextPruner"
Cohesion: 0.09
Nodes (29): ContextPruner, Any, context_pruner.py — auto-generated module docstring (user-research skill scan)., Walk messages backward, accumulating per-role char counts. Returns…, Wrap evicted messages into ``<historical_memory_only>`` XML. The XML block is…, Reset the prune timer so the next call always runs the pipeline., 3-phase context window management middleware. Phase 1 — Truncate: Strips…, Apply 3-phase pruning if the context is over budget or cache expired. Returns… (+21 more)

### Community 227 - "test_freebuff.py"
Cohesion: 0.08
Nodes (34): free_nvidia_models(), Return the curated list of free NVIDIA NIM models FreeBuff may use., True when *model* is in the curated free NVIDIA NIM set., check_rate_limit(), _enforce_rate_limit(), _is_freebuff_unlimited(), is_rate_limit_exempt(), _rate_limit_exempt_key_ids() (+26 more)

### Community 228 - "test_backend_server_features.py"
Cohesion: 0.06
Nodes (23): _agent_provider_failure_response(), _append_agent_session_message(), _build_auto_skill_guidance(), _mask_observations(), Exception, Path, ProviderConfig, Truncate tool/observation content in older messages to prevent context bloat. (+15 more)

### Community 229 - "sync/service.py"
Cohesion: 0.11
Nodes (33): FastAPI dependency: require Power User or Admin role. Raises 403 otherwise., require_power_user(), sync/ — Syncthing-style workspace synchronisation service., add_peer(), get_folder_index(), get_sync_file(), get_sync_service(), list_conflicts() (+25 more)

### Community 230 - "_Collection"
Cohesion: 0.11
Nodes (16): _apply_update(), _Collection, _DeleteResult, _InsertResult, _match(), _new_id(), _now_iso(), db/sqlite_store.py — Async SQLite storage backend. Provides a Motor-compatible… (+8 more)

### Community 231 - "DecisionsStore"
Cohesion: 0.09
Nodes (10): DecisionsStore, Any, Connection, Test-only: clears the cached singleton so the next get_decisions_store() builds…, # NOTE: ``decision_id`` is NOT a SQL FOREIGN KEY here. The bot's, reset_decisions_store_singleton(), DecisionsStoreTests, _fresh_store() (+2 more)

### Community 232 - "GitHubTools"
Cohesion: 0.13
Nodes (13): GitHubTools, Any, List issues (excludes pull requests) for triage/intake pipelines., Add labels to an issue (used to mark it as triaged, preventing reprocessing)., Merge an open pull request via the GitHub API., Backwards-compat: accepts 'owner/repo' format., Commit a single file change. Accepts 'owner/repo' format for repo_name., Backwards-compat: accepts 'owner/repo' format. (+5 more)

### Community 233 - "PlaybookLibrary"
Cohesion: 0.10
Nodes (21): _now(), Playbook, PlaybookLibrary, PlaybookRun, PlaybookStep, Any, Path, agent/playbook.py — Automation Playbooks Pre-defined, named multi-step… (+13 more)

### Community 234 - "test_verification_strategies.py"
Cohesion: 0.11
Nodes (32): cross_verify(), Any, race(), agent/verification_strategies.py — opt-in parallel patterns for high-stakes…, Heuristic fallback score when the reward model is unavailable.…, Run *n* independent attempts at *instruction* concurrently; return the winner.…, True if any path matches the repo's risky-module trigger list., Have an independent agent re-check a completed task's changed files. Returns… (+24 more)

### Community 235 - "ApprovalStore"
Cohesion: 0.08
Nodes (22): ApprovalRequest, ApprovalStatus, ApprovalStore, Any, Enum, str, packages/governance/approvals.py — human-in-the-loop for high-risk actions. The…, Bounded, in-process store of approval requests. Uses a :class:`threading.Lock`… (+14 more)

### Community 236 - "REWRITE_PLAN.md — Phased Migration Strategy"
Cohesion: 0.06
Nodes (35): Already completed (pre-migration fixes), Current Status, Inventory of suspected dead code, Migration Safety Checklist, Phase 1: Foundation (Weeks 1-2), Phase 2: Provider Abstraction (Weeks 3-4), Phase 3: Auth Consolidation (Week 5), Phase 4: Scheduler Redesign (Week 6) (+27 more)

### Community 237 - "test_background_services.py"
Cohesion: 0.08
Nodes (23): Return True when the web process should also run background services., run_background_in_web(), anyio, Unit tests for services/background.py — start_background_services wiring.…, Scheduler's on_fire handler is set to TaskAutomation.handle_scheduled_job., Calling bg.stop() twice must not raise or double-stop., RUN_BACKGROUND_IN_WEB defaults to True., The constant itself must leave real margin under Render's 5s timeout. (+15 more)

### Community 238 - "OrchestratorQueue"
Cohesion: 0.07
Nodes (15): OrchestratorQueue, Any, _QueueEntry, services/orchestrator_queue.py — Async FIFO run queue with concurrency…, Async FIFO queue that limits concurrent orchestrator run executions.…, Enqueue a run for async execution. Returns immediately. ``fn(*args, **kwargs)``…, Enqueue a run and return a future that resolves when it completes., tests/test_orchestrator_queue.py — Tests for async FIFO run queue (#522). (+7 more)

### Community 239 - "test_all_providers_discovery.py"
Cohesion: 0.16
Nodes (35): _get(), asyncio, ProviderRouter, Verify every supported provider is correctly discovered, prioritised, and…, Check if url hostname matches expected domain (exact or subdomain)., Build a ProviderRouter from_env() with only the supplied env vars active., _router(), test_anthropic_discovery() (+27 more)

### Community 240 - "test_persistent_memory.py"
Cohesion: 0.06
Nodes (35): memory_store(), Tests for persistent memory system., Test auto-loading global memories., Test auto-loading includes workspace-specific memories., Test that auto-load respects priority ordering., Test filtering memories by category., Create a temporary database for testing., Test searching memories. (+27 more)

### Community 241 - "SpecEntry"
Cohesion: 0.11
Nodes (20): get_enrichment(), Return the enrichment instance for a workspace. Keyed by workspace root rather…, build_block(), _flag(), Rewrite the spec file, preserving any non-entry (hand-written) lines., Compact prompt block of standing instructions, or '' when there are none.…, One standing instruction plus the evidence that earned it., SpecEntry (+12 more)

### Community 242 - "IssueCategory"
Cohesion: 0.12
Nodes (33): IssueCategory, IssueSeverity, Enum, str, cluster_friction(), clusters_to_issues(), collect_friction_events(), FrictionCluster (+25 more)

### Community 243 - "SecurityScanner"
Cohesion: 0.11
Nodes (25): _now(), Any, Path, agent/security_scanner.py — Security & Vulnerability Scanner Runs static…, Run all available scanners and aggregate results., Run a cross-harness security audit. Checks that the agent harness configuration…, Return True if *name* is on PATH., Return current UTC timestamp as ISO string. (+17 more)

### Community 244 - "get_registry"
Cohesion: 0.07
Nodes (23): get_registry(), Return model registry, extended with ROUTER_EXTRA_MODELS env entries.…, test_bedrock_haiku_4_5_in_registry(), test_bedrock_opus_48_in_registry(), test_bedrock_opus_4_6_v1_in_registry(), test_bedrock_opus_4_7_in_registry(), test_bedrock_sonnet_4_6_in_registry(), test_deepseek_v3_in_registry() (+15 more)

### Community 245 - "test_anthropic_router.py"
Cohesion: 0.09
Nodes (10): _make_anthropic_provider(), _payload(), ProviderConfig, Response, Tests for Anthropic-specific router features. Covers: - Prompt caching…, TestAnthropicPayloadExtendedThinking, TestAnthropicPayloadPromptCaching, TestAnthropicToOpenAICacheUsage (+2 more)

### Community 246 - "test_llm_router_e2e.py"
Cohesion: 0.14
Nodes (34): _ok(), parametrize, End-to-end routing against mock providers (ADR-008). These are the tests that…, A router wired to three mock providers, with all singletons isolated., Two keys on alpha means a 429 costs a key, not the provider., The NVIDIA 410 incident, as a regression test (CLAUDE.md §7)., A 422 is the request's fault — trying five providers just adds latency., A 413 is one provider's context window, not a fact about the request. The… (+26 more)

### Community 247 - "report_to_markdown"
Cohesion: 0.11
Nodes (26): export_seo_audit(), Export a stored audit. - ``csv`` aggregated findings, Screaming Frog…, _build_curl_cffi_fetcher(), _build_pdf(), main(), _parse_args(), Namespace, Path (+18 more)

### Community 248 - "agent_runtime.py"
Cohesion: 0.10
Nodes (32): _active_cloud_provider(), _candidate_ollama_bases(), _chat(), chat_completions(), _chat_with_ollama(), _chat_with_openai_compat(), ChatRequest, ChatResponse (+24 more)

### Community 249 - "ENGINEERING_STANDARDS.md — Coding, Security & Testing Standards"
Cohesion: 0.06
Nodes (33): 1. Coding Standards, 2. Logging Standards, 3. Security Standards, 4. Testing Standards, 5. CI/CD Standards, 6. Performance Standards, 7. Documentation Standards, Architecture docs (+25 more)

### Community 250 - "DashboardScreen.jsx"
Cohesion: 0.07
Nodes (10): BarChart(), Charts, Donut(), ExecutionTimeline(), Sparkline(), ErrorBoundary, DashboardScreen(), fmtTokens() (+2 more)

### Community 251 - "context_rules.py"
Cohesion: 0.11
Nodes (32): _check_constitution_echo(), _check_files_exist(), _check_grounding(), _check_hedges(), _check_project_identity(), _check_risk_flags(), _check_source_summary(), _check_todos() (+24 more)

### Community 252 - "test_platform_controls.py"
Cohesion: 0.08
Nodes (26): all_controls(), controls_by_group(), Every control in the catalogue, in display order., The catalogue grouped for the dashboard, groups in display order., clean_overrides(), _python_sources(), Tests for the dashboard platform-controls surface. Covers the three things that…, Secrets stay environment-only per the repository constitution. (+18 more)

### Community 253 - "local_controller.py"
Cohesion: 0.12
Nodes (32): _bin_exists(), _choose_local_brain(), _default_agency_url(), _default_machine_id_file(), _env_int(), _get_or_create_machine_id(), _http_json(), _log() (+24 more)

### Community 254 - "test_live_server.py"
Cohesion: 0.22
Nodes (32): check(), main(), ok(), Any, Client, Response, Returns access token for subsequent tests., Direct-mode chat. Passes even if no LLM backend is running (error message… (+24 more)

### Community 255 - "ContextCompressor"
Cohesion: 0.11
Nodes (24): ContextCompressor, ContextStats, _estimate_tokens(), Strategy, agent/context.py — Smart Context Compression Three strategies for keeping…, Drop the oldest non-system messages until under the token threshold., Remove exact-duplicate and near-empty messages., Compress conversation history when it approaches the token limit. Usage:: cc =… (+16 more)

### Community 256 - "ContextManager"
Cohesion: 0.10
Nodes (21): ContextManager, Any, True when the history is long enough to warrant compaction., Replace the old portion of *history* with a single compaction note. The…, True when the harness should use head_file instead of read_file. When a file is…, Trim a step result so sub-agent outputs stay within ~1-2k tokens. The Anthropic…, Manages context window state for a single agent run. The Brain (LLM) stays…, Return a copy of *observations* with old tool outputs truncated. JetBrains… (+13 more)

### Community 257 - "loop.py"
Cohesion: 0.08
Nodes (27): AgentPhaseError, _check_extra_kwargs(), _enforce_signature(), _note_phase_end(), _note_phase_start(), _nvidia_api_key(), Exception, loop.py — AgentRunner: plan → execute → verify loop with locked tool signatures. (+19 more)

### Community 258 - "SparkProvider"
Cohesion: 0.07
Nodes (21): get_spark_provider(), NotarizeResult, Any, agent/spark_provider.py — SPARK API Integration Inspired by SPARK API (spark-…, Return True if SPARK API key is set., Register this agent on the SPARK network. If *bsv_address* is not provided,…, Notarize content hash on the BSV blockchain. Args: content: String or bytes to…, Verify a hash against the BSV blockchain. Args: content_hash: SHA-256 hash to… (+13 more)

### Community 259 - "ResourceWatchdog"
Cohesion: 0.10
Nodes (20): _now(), Any, agent/watchdog.py — Resource Watchdog Monitors URLs, files, or any resource…, Register a resource to monitor. Returns the :class:`WatchedResource`., Stop monitoring a resource. Returns *True* if it existed., Check a single resource right now. Returns a :class:`WatchEvent` if changed., Poll resources at a fixed interval and fire *on_change* when content changes.…, ResourceWatchdog (+12 more)

### Community 260 - "agents/api.py"
Cohesion: 0.13
Nodes (31): _apply_activity_status(), create_agent(), delete_agent(), get_agent(), _get_user(), list_agents(), list_runtime_agents(), Any (+23 more)

### Community 261 - "chat_handlers.py"
Cohesion: 0.12
Nodes (31): _apply_chat_defaults(), _emit_safely(), _extract_exact_output(), _filter_fragment(), _filter_openai_sse_line(), handle_ollama_native_chat(), handle_openai_chat_completions(), _inject_default_system_prompt() (+23 more)

### Community 262 - "Workspace"
Cohesion: 0.10
Nodes (14): Any, Path, mcp_server/workspace.py — Isolated workspace manager for the MCP server. Each…, Run a shell command inside the workspace via an explicit shell binary., Resolve rel against root, reject path traversal., Run a subprocess. Never uses shell=True., Manages a single isolated workspace directory., Canonical root path (follows macOS /var → /private/var symlinks). (+6 more)

### Community 263 - "RateLimitTracker"
Cohesion: 0.10
Nodes (11): RateLimitTracker, Sleep if remaining quota for *provider_id* is critically low. Returns the…, Snapshot of all tracked provider quotas. Safe to call from any context., Reset all state (primarily for tests)., In-memory tracker for per-provider rate-limit state., asyncio, _response(), TestClear (+3 more)

### Community 264 - "Screens"
Cohesion: 0.06
Nodes (33): 🛡 Admin — users & access, 🤖 Agents — autonomous team, Architecture, security, license, Autonomous AI Agency, 💬 Chat — unified assistant, 🏢 Company — operating context, Contributing, 📊 Dashboard — system overview (+25 more)

### Community 265 - "test_daily_2026_06_04.py"
Cohesion: 0.10
Nodes (32): _opus_model(), Return an Opus model ID iff the operator explicitly opted into a paid brain.…, _content_block_to_text(), _fresh_router(), _make_tool(), Regression tests for daily-2026-06-04 improvements. Covers: - Claude Opus 4.8…, redacted_thinking blocks (safety-filtered chain-of-thought) must also be…, Ensure effort never leaks into the forwarded OpenAI payload. (+24 more)

### Community 266 - "test_microagents.py"
Cohesion: 0.15
Nodes (29): load_microagents(), match_microagents(), Microagent, microagents_block(), _parse_file(), Path, OpenHands-compatible microagents: keyword-triggered repo knowledge. OpenHands…, Parse one microagent markdown file; None when it isn't one. (+21 more)

### Community 267 - "Security Analysis — local-llm-server"
Cohesion: 0.06
Nodes (30): Fable 5 — Read-Only Audit & Skill-Distillation Notes, Finding A — `list_for_user` Mongo query diverges from the `_can_read` policy, Finding B — `/api/secrets` router is mounted with no authentication dependency, How I would make the smaller model behave like me, Minor, non-security, Part 0 — A caveat on how this task started, Part 1 — The audit, Part 2 — Handing frontier skills to a smaller model (+22 more)

### Community 268 - "Langfuse Observability Guide"
Cohesion: 0.06
Nodes (32): 1. Create a Langfuse project, 2. Configure credentials, 3. Optional tuning, 4. Verify the connection, Commercial savings metrics, Cost analysis dashboard, Cost dashboard, Customising Commercial Reference Prices (+24 more)

### Community 269 - "v3_models.py"
Cohesion: 0.14
Nodes (31): _get_current_user, UserResponse, delete_model(), get_activity(), get_model(), _get_ollama_model_info(), _get_ollama_models(), get_stats() (+23 more)

### Community 270 - "v3_auth.py"
Cohesion: 0.11
Nodes (30): _get_admin_email(), _get_admin_name(), _get_admin_secret(), login(), LoginRequest, LoginResponse, BaseModel, post (+22 more)

### Community 271 - "test_failover_silent_exhaustion.py"
Cohesion: 0.10
Nodes (23): Paid-tier providers admitted to the chain and not yet attempted. Empty when the…, _untried_paid(), True when the provider can accept traffic right now., _FM, _P, Regression tests for a chain that fails silently. From a real incident:…, Reserve logic must never break the chain it is meant to protect., The incident case: providers ran, none reported a reason. (+15 more)

### Community 272 - "DigestSummary"
Cohesion: 0.11
Nodes (11): DigestPayload, DigestSummary, AdminDigestRouterAuthTests, Stub for telegram_service.NotificationDispatcher used by /send., Build a FastAPI TestClient against an app shell with only the…, _StubDispatcher, DailyDigestAggregatorTests, _FakeOrchestrator (+3 more)

### Community 273 - "TestDiagCommand"
Cohesion: 0.09
Nodes (12): TestCase, _GlobalsRestorer, tests/test_telegram_diag.py Regression test for the new ``/diag`` (admin)…, Drive _process_update with a /diag message and return the response. Restores…, The Operator Charter §"Telegram bot" silent-drop path MUST surface a…, Once we've warned once, subsequent silent drops must NOT spam the log., Snapshot/restore tb globals + TELEGRAM_POLLER_DISABLED env var., ``/diag`` behaviour under admin + non-admin + empty-allowlist states. (+4 more)

### Community 274 - "StuckDetector"
Cohesion: 0.13
Nodes (24): Any, Stuck detection for the agent tool loop — adapted from OpenHands. OpenHands…, Canonical identity of one observation, ignoring incidental fields., Consecutive repetitions required before a pattern counts as stuck., Detects repeating patterns in a step's observation history., Return a human-readable reason when the loop looks stuck, else None., _signature(), StuckDetector (+16 more)

### Community 275 - "High-Agency Frontend Skill"
Cohesion: 0.06
Nodes (30): 10. FINAL PRE-FLIGHT CHECK, 1. ACTIVE BASELINE CONFIGURATION, 2. DEFAULT ARCHITECTURE & CONVENTIONS, 3. DESIGN ENGINEERING DIRECTIVES (Bias Correction), 4. CREATIVE PROACTIVITY (Anti-Slop Implementation), 5. PERFORMANCE GUARDRAILS, 6. TECHNICAL REFERENCE (Dial Definitions), 7. AI TELLS (Forbidden Patterns) (+22 more)

### Community 276 - "test_ceo_router.py"
Cohesion: 0.12
Nodes (29): build_ceo_router(), Any, APIRouter, backend/ceo_router.py — observability and manual control for the CEO. Surfaces…, Reject non-admin callers for routes that spend provider budget. Delegates to…, _require_admin(), get_ceo_supervisor(), Return the shared supervisor, constructing it on first use. (+21 more)

### Community 277 - "TestNormalizeResponseFormat"
Cohesion: 0.08
Nodes (12): _normalize_response_format(), Translate OpenAI ``response_format`` into Ollama's ``format`` field. For…, _get_model_map(), Merge built-in defaults with MODEL_MAP env overrides (lazy, cached)., Daily automation tests — 2026-05-14 Covers three features implemented in this…, Payload without 'model' field should apply normalization (no '/' → local)., _normalize_response_format must not mutate the input dict., Tests that /v1/models exposes Claude/Anthropic alias entries. (+4 more)

### Community 278 - "Quick-Note GitHub Issues Processing - Session Summary"
Cohesion: 0.06
Nodes (30): 1. Stop-Slop Quality Filter (Issue #229), 2. ECC Integration Study (Issue #266 & #230), ✅ Analysis & Comments (16 items), Architecture Alignment, Branch: `docs/ecc-adoption-analysis`, Branch: `feat/stop-slop-quality-filter`, Deliverables, ECC Patterns Adopted (+22 more)

### Community 279 - "test_rate_limiter.py"
Cohesion: 0.10
Nodes (27): pace(), Proactive rate-limit throttling for LLM providers — two complementary layers.…, Rate limiter using virtual scheduling (GCRA-style): each caller atomically…, Block until this caller's reserved slot arrives, or *max_wait* elapses. Returns…, Proactively pace a request to *provider_id*. No-op (returns 0.0 immediately)…, Clear all token-bucket state (tests only). Does not touch the header tracker's…, reset(), TokenBucket (+19 more)

### Community 280 - "CacheManager"
Cohesion: 0.10
Nodes (14): CacheManager, _Entry, LRUCache, Any, T, Live (unexpired) entries — used by the semantic layer's scan., Owns every cache layer and the policy for what may enter them., Whether a response to ``request`` may be stored. Deliberately conservative — a… (+6 more)

### Community 281 - "test_brain_failover.py"
Cohesion: 0.11
Nodes (30): _make_manager(), tests/test_brain_failover.py — Universal multi-provider brain failover tests.…, Status snapshot doesn't leak API keys., Make a fresh manager (bypasses the singleton for isolation)., No API keys set → no providers in the registry., test_429_exponential_backoff(), test_circuit_recovers_after_cooldown(), test_max_attempts() (+22 more)

### Community 282 - "TestRecordUsageAndStats"
Cohesion: 0.06
Nodes (6): Tests for packages/ai/cost_tracker.py — per-model cost attribution. Covers: -…, TestClearStats, TestCostForTokens, TestEnvOverrides, TestGetCostTable, TestRecordUsageAndStats

### Community 283 - "test_mcp_governance.py"
Cohesion: 0.11
Nodes (28): _call(), client(), _engine(), Governance on the MCP HTTP surface — threat-model T11. Before this,…, Same Golden Rule guarantee as the in-process gate., No UI is attached to this surface, so holding the socket would hang it., Headers are a hint, not a credential — and the baseline holds anyway. A caller…, A display name with an em-dash must not take out the tool call. (+20 more)

### Community 284 - "test_purge_backlog.py"
Cohesion: 0.09
Nodes (22): auth_headers(), FakeTaskStore, MonkeyPatch, Task, tests/test_purge_backlog.py — 2026-07-03 crash-loop remediation. Covers: - POST…, The per-minute tick must requeue at most ONE blocked task, keep its…, Drive _maybe_boot_purge with fakes; return (purged, marker_writes). ``core``…, A failed purge must NOT record the nonce — it retries next boot. (+14 more)

### Community 285 - "tests/test_browser.py"
Cohesion: 0.10
Nodes (18): BrowserAction, _env_true(), _not_started(), PageState, Any, agent/browser.py — Browser Automation Controls a real browser via Playwright so…, Evaluate a JavaScript expression in the page context., Return a summary of the current page state. (+10 more)

### Community 286 - "test_freebuff_bot.py"
Cohesion: 0.09
Nodes (24): List the free NVIDIA NIM models a user may pick (e.g. via Telegram)., _embedded(), _embedded_run(), _fb_models(), _fb_plan(), _fb_run(), _freebuff_max_steps(), Return the free model list (embedded or via proxy). (+16 more)

### Community 287 - "fmtErr"
Cohesion: 0.14
Nodes (27): authorizeGithubRepos(), createGithubPR(), deleteGithubToken(), fmtErr(), getGithubStatus, getGithubTree(), getPlatformInfo(), githubStatus() (+19 more)

### Community 288 - "settings.py"
Cohesion: 0.09
Nodes (18): Cerebras provider adapter — free, fast LLM (qwen-3-coder-480b)., Ollama provider adapter — local LLM inference., packages.ai — provider abstraction, model registry, and failover manager., packages/ai/manager.py — ProviderManager. Single entry point for all LLM calls.…, Provider, ABC, packages/ai/provider.py — Provider abstraction interface. Every LLM provider…, Base interface every provider must implement. Implementations live in… (+10 more)

### Community 289 - "RuntimeHealthService"
Cohesion: 0.09
Nodes (11): CircuitState, Return the last-known health for *runtime_id* (may be stale)., Return True if the runtime is available (not circuit-open)., Return health snapshots for all known runtimes., Force an immediate health check of all runtimes and return results., Attempt to start a dead runtime subprocess before re-probing. Uses the local…, Reduce probe frequency for runtimes that have never come online., Async health polling service for all registered runtimes. (+3 more)

### Community 290 - "switch_brain.py"
Cohesion: 0.16
Nodes (29): detect_ollama_models(), dim(), fail(), get_auth_headers(), get_brain_config(), get_ngrok_tunnel_url(), header(), info() (+21 more)

### Community 291 - "SyncService"
Cohesion: 0.12
Nodes (14): Any, Path, Orchestrates workspace synchronisation across peers. Maintains an in-memory…, Return metadata for all files in a sync folder., Read a file from a sync folder., Write a file into a sync folder, creating parent dirs as needed., Return True if there is a conflict (both sides modified)., Rename the local file to a .conflict copy before overwriting. (+6 more)

### Community 292 - "AgentDirective"
Cohesion: 0.10
Nodes (13): AgencyCycleResult, AgentDirective, _build_quick_note_instruction(), _now_str(), Any, Capture the FastAPI main event loop so the CEO thread can dispatch run_cycle()…, Generate directives for each onboarded company. The CEO examines each company's…, Close exhausted quick-note issues; dispatch Dev directives for open ones. (+5 more)

### Community 293 - "test_autonomy_gate.py"
Cohesion: 0.11
Nodes (27): agent_branch_name(), assert_agent_can_merge(), assert_agent_can_write(), AutonomyViolation, is_protected_branch(), _protected_branches(), Autonomy gate — enforce 'agents propose via PR, humans merge'. The agency can…, Raised when an agent-initiated action would exceed the propose-PR policy. (+19 more)

### Community 294 - "test_rag_context.py"
Cohesion: 0.12
Nodes (23): RAGContextBuilder, Retrieve, decay, and compress context to fit a configurable token budget.…, Tests for agent/rag_context.py — Advanced RAG context management layer. Imports…, test_builder_doc_budget_fraction(), test_builder_docs_dropped_count(), test_builder_empty_both(), test_builder_empty_documents(), test_builder_empty_history() (+15 more)

### Community 295 - "ProjectScaffolder"
Cohesion: 0.13
Nodes (20): ProjectScaffolder, Any, Path, agent/scaffolding.py — Project Scaffolding Creates new project skeletons from…, Apply named project templates to a target directory. Usage:: s =…, Write template files into *target_dir*. Skips existing files unless…, ScaffoldResult, Template (+12 more)

### Community 296 - "Configuration Reference"
Cohesion: 0.07
Nodes (29): Agent governance — identity, policy, approvals, audit, sandboxes, Agent Models, Anthropic API Compatibility / Claude Code, Authentication and Keys, Claude Code setup, Configuration Reference, Continual Harness, Dashboard (React UI on :3000, API on :8001) (+21 more)

### Community 297 - "test_p0_roadmap_a4_a5_b2.py"
Cohesion: 0.12
Nodes (15): IntEnum, get_steering_injector(), Return recommended steering labels for a given task category. Used by the model…, Return the module-level SteeringInjector singleton., steering_for_task(), get_task_queue(), PrioritizedTask, Priority (+7 more)

### Community 298 - "ModelConfig"
Cohesion: 0.11
Nodes (13): ModelConfig, Capability and pricing metadata for one model id., ModelRegistry, Record models found by a provider's ``/models`` endpoint. Discovered models…, Models satisfying every stated requirement, best first. Ordering is by…, The biggest-context model available — the context-overflow escape hatch., The lowest-cost model that still meets the requirements., The fastest model by declared speed tier. (+5 more)

### Community 299 - "test_pr923_fixes.py"
Cohesion: 0.09
Nodes (27): nuclear_cleanup(), Directly delete ALL stale jobs from the DB collection. More aggressive than…, FakeDB, asyncio, tests/test_pr923_fixes.py — regression tests for PR #923 (5 production issues).…, nuclear_cleanup should keep newest job per name, delete duplicates., nuclear_cleanup should gracefully handle a DB without a schedules collection., reconcile_stranded_tasks source code must include a FAILED-task re-queue pass.… (+19 more)

### Community 300 - "PriorityTaskQueue"
Cohesion: 0.11
Nodes (11): Queue, PriorityTaskQueue, Any, Start the worker pool., Stop the worker pool gracefully., Submit a task to the queue. Returns True if accepted, False if rejected due to…, Return queue introspection data for status endpoints., Subscribe to progress events for a specific task. Returns an asyncio.Queue that… (+3 more)

### Community 301 - "SteeringInjector"
Cohesion: 0.11
Nodes (10): Any, Inject steering instructions into the message list. Args: messages: The…, Inject steering into an OpenAI chat payload dict. Modifies and returns the…, Build the steering instruction text based on format., Build steering as natural-language quality instructions., Build steering as ChatML-formatted tokens., Build steering as Nemotron-specific steering tags., Inject steering tokens into prompts for quality-biased generation. Supports… (+2 more)

### Community 302 - "test_phase4_runtime_resilience.py"
Cohesion: 0.10
Nodes (28): _env_flag(), Read a boolean env var. Accepts 'true'/'1'/'yes' (case-insensitive)., _make_task(), asyncio, Task, TaskStatus, tests/test_phase4_runtime_resilience.py Phase 4: runtime resilience tests.…, Tasks in TODO or DONE status are ignored by the reconciler. (+20 more)

### Community 303 - "test_claude_setup_audit.py"
Cohesion: 0.16
Nodes (23): AuditReport, _check_agents_config(), _check_claude_md_sections(), _check_hooks(), _check_skills(), _check_state(), CheckResult, main() (+15 more)

### Community 304 - "test_scheduler_hydration_bounded.py"
Cohesion: 0.09
Nodes (22): _hydrate_scheduler_bounded(), Attach durable persistence and rehydrate (#505), bounded by a budget. Without…, _BrokenScheduler, _fake_schedule_store(), _FakeStore, _FastScheduler, _HangingScheduler, _isolate_warmup_overflow() (+14 more)

### Community 305 - "test_internal_agent_did_work.py"
Cohesion: 0.12
Nodes (28): _compute_did_work(), tests/test_internal_agent_did_work.py — step-success-ratio gate tests. Tests…, judge_verdict=BLOCKED → always FAILURE, even with 10/10 applied., judge_verdict=BLOCKED → always FAILURE, even with a long report., Even with unique_files, 1/22 applied → FAILURE (steps_ok gate)., With 9/10 applied + unique_files → SUCCESS., Replicate the did_work logic from internal_agent.py:509-533., 1/22 applied (4.5%) → should be FAILURE (the bug case). (+20 more)

### Community 306 - "test_schedule_growth_invariants.py"
Cohesion: 0.08
Nodes (19): _FakeMongoStore, _FakeSQLiteStore, asyncio, parametrize, Workstream D — Never again: dedup + growth invariants. These tests enforce…, Simulates a Mongo-style store with find/aggregate/replace_one., Simulates a SQLite-style store with load_all/upsert/remove., Duplicate-named rows must collapse to newest on BOTH backends. Regression for… (+11 more)

### Community 307 - "LessonStore"
Cohesion: 0.13
Nodes (21): _get_store(), LessonStore, Any, Connection, Path, Failure lessons: turn failed runs into context for the next run. The supervisor…, Formatted prompt block of recent lessons, or '' when none exist., SQLite-backed store of failure lessons. Thread-safe, zero deps. (+13 more)

### Community 308 - "TerminalPanel"
Cohesion: 0.13
Nodes (20): _is_command_not_found(), _powershell_quote(), Any, agent/terminal.py — Terminal Panel Reads the rendered terminal output buffer —…, Try to read the pane buffer via tmux capture-pane., Return a minimal snapshot with terminal dimensions only., Capture the current terminal buffer as a :class:`TerminalSnapshot`. Usage::…, Capture the current terminal state. Never raises. (+12 more)

### Community 309 - "Python Dependencies (`requirements.txt`)"
Cohesion: 0.07
Nodes (27): AI / LLM, AI Tooling, Browser Automation, Cloud / Infrastructure, Core Web Framework, Data Processing, DEP-001 [HIGH] — No Python Lockfile, DEP-002 [HIGH] — `playwright` as a Runtime Dependency (+19 more)

### Community 310 - "Technical Debt Register — local-llm-server"
Cohesion: 0.07
Nodes (27): Category 10 — Patch Files in Root, Category 1 — God Files, Category 2 — API Key Naming Confusion, Category 3 — Dual App Architecture, Category 4 — Dual Storage Backend, Category 5 — Test File Sprawl, Category 6 — Environment Variable Documentation, Category 7 — Missing Type Annotations (+19 more)

### Community 311 - "llm_providers.py"
Cohesion: 0.16
Nodes (26): _anthropic_headers(), _anthropic_payload(), _anthropic_response_text(), _auth_headers(), chat_completion_text(), list_openai_models(), normalize_base_url(), openai_compat_url() (+18 more)

### Community 312 - "TrafficDirector"
Cohesion: 0.11
Nodes (11): get_director(), In-process traffic distribution and budget accounting for providers., EWMA latency in ms; never-sampled providers sort first. Returning -1.0 for an…, Clear all counters (tests only)., Return the process-singleton TrafficDirector., TrafficDirector, Tests for packages/ai/traffic_director.py — traffic distribution across…, `int(0.5)` is 0, and a cap of 0 makes `in_flight >= cap` true at zero in-flight… (+3 more)

### Community 313 - "BrainFailoverManager"
Cohesion: 0.10
Nodes (15): BrainFailoverManager, Any, Permit one probe call without claiming the provider succeeded. This is the…, Seconds until the soonest cooling provider is probeable again. ``None`` when no…, True when a provider's cooldown window is wider than any it could legitimately…, Record a provider failure — opens the circuit breaker on threshold., Map a requested model to the provider's equivalent. If the requested model is…, Maximum number of provider attempts before giving up. (+7 more)

### Community 314 - "test_crispy_burn_in.py"
Cohesion: 0.07
Nodes (27): burn_in(), tests/test_crispy_burn_in.py — N4 follow-up: burn-in criteria evaluator. Tests…, window_days below 7 → not ready (need at least a week of evidence)., PhaseSequenceError in last_failure_reasons → not ready (workspace isolation…, Non-PhaseSequenceError failures (assertion errors, etc.) don't block promotion…, Exact threshold values meet the criteria (>=, not >)., window_days=None (no runs yet, but total_runs > 0 somehow) is treated as 0 —…, The --json flag lets the workflow (and tests) run offline against a saved… (+19 more)

### Community 315 - "test_provider_enable_disable.py"
Cohesion: 0.09
Nodes (15): isolated_kv(), one_provider(), asyncio, parametrize, Per-provider on/off switch, with auto-disable for unfixable failures only.…, The critical guard: disabling on 429 would switch off every free provider., Point the kv_store at a temp DB so tests never touch real state., Storage problems must degrade, not raise. (+7 more)

### Community 316 - "test_skill_registry_boot_refresh.py"
Cohesion: 0.12
Nodes (16): clean_task(), _install(), _NullDispatcher, _NullRuntimeManager, asyncio, Exception, The configured remote skill repos must be fetched without a human trigger.…, Remote skills are optional; a rate limit must not surface as an error. (+8 more)

### Community 317 - "test_memory.py"
Cohesion: 0.10
Nodes (18): _now(), Any, Path, agent/memory.py — Session Memory Snapshots Persists agent session state to disk…, Persist *state* to disk under *session_id*. Returns the file path., Load a saved snapshot. Returns the state dict or *None* if absent., Return metadata for all saved snapshots (session_id, saved_at, path)., Delete a snapshot. Returns *True* if the file existed. (+10 more)

### Community 318 - "analyze_qualitative"
Cohesion: 0.12
Nodes (15): analyze_qualitative(), Extract themes, pain points, and desires from qualitative data. Args: source:…, apply_recommendations(), collect_codebase_metrics(), extract_qualitative_themes(), main(), plan_repo_scan(), Use the user research skill to scan the repo and apply recommendations. Adapts… (+7 more)

### Community 319 - "SprintMetrics"
Cohesion: 0.10
Nodes (12): Complete the sprint and record velocity., Calculate current sprint metrics., Velocity and burndown metrics for a sprint., Percentage of story points completed., Points per day needed to complete on time., Whether the sprint is on track to complete., Derive a qualitative health signal from the metrics. - COMPLETE: all points…, SprintMetrics (+4 more)

### Community 320 - "Deploy: FreeBuff Telegram bot (24×7)"
Cohesion: 0.07
Nodes (25): Agents, Environment variables, Free model set, FreeBuff — free-NVIDIA coding agent, `/freebuff <task>`, HTTP API, Running 24×7, Telegram phone control (+17 more)

### Community 321 - "Claude Code + Qwen Local Setup"
Cohesion: 0.07
Nodes (27): 1. Set environment variables, 2. Start Claude Code, 3. Verify model routing, Anthropic SDK (Python), Architecture, "Authentication error" or 401, Claude Code + Qwen Local Setup, Claude Code reports "token limit exceeded" (+19 more)

### Community 322 - "generate_context.py"
Cohesion: 0.12
Nodes (26): _build_caller_chain(), _build_context_doc(), _build_grounding_block(), _build_pr_description(), _build_todos_md(), _build_user_message(), _call_claude(), _call_mistral() (+18 more)

### Community 323 - "test_brain_availability_doctor.py"
Cohesion: 0.16
Nodes (24): brain_availability_summary(), Non-secret answer to "can the brain answer a request right now?". Three callers…, _doctor(), _P, _patch_providers(), Tests for the public brain-availability diagnosis and the supervisor's use of…, Minimal provider stand-in matching what the summary reads., Wrongly pausing every goal is worse than one wasted re-drive. (+16 more)

### Community 324 - "_is_dns_failure"
Cohesion: 0.10
Nodes (18): _is_dns_failure(), _probe_failure_reason(), BaseException, Turn a probe exception into an operator-actionable one-line reason. A dead…, True when *exc* (or anything it wraps) is a name-resolution failure., asyncio, Exception, parametrize (+10 more)

### Community 325 - "isolated_telegram_config"
Cohesion: 0.11
Nodes (11): isolated_telegram(), isolated_telegram_config(), tests/_telegram_test_utils.py Snapshot/restore helper for ``telegram_bot``…, Pytest fixture alias for ``isolated_telegram_config``. Use this in tests that…, Snapshot+restore ``tb`` globals + ``TELEGRAM_POLLER_DISABLED``. Keyword args…, tests/test_telegram_test_utils.py Self-test suite for…, The helper's ``__exit__`` runs ``if original is _MISSING: if hasattr:…, If a tracked attr is absent under ``tb`` at scope entry, the helper snapshots… (+3 more)

### Community 326 - "validate_outbound_url"
Cohesion: 0.14
Nodes (25): test_git_ref_rejects_empty(), test_git_ref_rejects_flag_injection(), test_git_ref_rejects_shell_metacharacters(), test_git_ref_rejects_traversal(), test_git_ref_valid(), test_git_scheme_allows_ssh(), test_http_scheme_rejects_ssh(), test_https_public_host_allowed() (+17 more)

### Community 327 - "webui/frontend/package.json"
Cohesion: 0.07
Nodes (26): @types/react, @types/react-dom, typescript, vite, @vitejs/plugin-react, dependencies, react, react-dom (+18 more)

### Community 328 - "Performance Analysis — local-llm-server"
Cohesion: 0.08
Nodes (25): 1. Rate Limiter Performance, 2. Ollama Connection Handling, 3. Model Router Performance, 4. Agent Execution Performance, 5. Backend Server Performance, 6. Frontend Performance, 7. Streaming Performance, PERF-001 [HIGH] — Synchronous Lock in Async Context (+17 more)

### Community 329 - "LLM Router — troubleshooting"
Cohesion: 0.08
Nodes (24): Embeddings, LiteLLM compatibility mode, LLM Router — local model guide, LM Studio, LocalAI, Ollama, Preferring local, Registering local models (+16 more)

### Community 330 - "SeoAuditReport"
Cohesion: 0.24
Nodes (20): Complete result of one audit run., SeoAuditReport, Paragraph, _appendix_full_findings(), _appendix_worst_pages(), _appendix_wsjf_roadmap(), _cell(), _cover_page() (+12 more)

### Community 331 - "control_registry.py"
Cohesion: 0.14
Nodes (20): packages/config/control_catalogue.py — the 109 operator-facing controls. The…, coerce(), _coerce_choice(), _coerce_number(), _coerce_toggle(), Any, packages/config/control_registry.py — the platform-control API. The public…, Normalise *value* into the env string this control stores. Raises… (+12 more)

### Community 332 - "keepalive.py"
Cohesion: 0.15
Nodes (25): _check_ollama(), _check_render(), _default_ollama_base(), _default_render_url(), _env_bool(), _loaded_ollama_prefixes(), _log(), _log_path() (+17 more)

### Community 333 - "monitor_lib.py"
Cohesion: 0.17
Nodes (25): colibri_dir(), download_log_path(), download_status(), DownloadStatus, _heartbeat_to_file(), is_process_alive(), model_dir(), monitor_log_path() (+17 more)

### Community 334 - "test_telegram_approval_e2e.py"
Cohesion: 0.12
Nodes (25): _approve_execution_via_rest(), _delete_task(), _extract_admin_token(), _login_admin(), _looks_like_admin_token(), _open_dashboard(), _poll_task_execution_approved(), Any (+17 more)

### Community 335 - "test_v3_auth.py"
Cohesion: 0.17
Nodes (25): _configured_v3_email(), _configured_v3_password(), asyncio, skip, TestClient, Tests for v3 API authentication., Test login endpoint returns valid tokens., Test login with invalid credentials. (+17 more)

### Community 336 - "TestWorkflow"
Cohesion: 0.08
Nodes (6): Tests for agents/workflow_engine.py — SuperClaude Workflow Engine. Uses…, Tests for WorkflowEngine., Tests for Task dataclass., TestTask, TestWorkflow, TestWorkflowEngine

### Community 337 - "HarnessEnrichment"
Cohesion: 0.12
Nodes (10): HarnessEnrichment, Any, agent/harness_enrichment.py — Automatic Harness Enrichment for Agent Prompts…, Build a compact catalog of available runtime skills. Discovers from…, Standing instructions from the Continual Harness spec. Deliberately uncached:…, Build the complete enrichment block (tools + skills). Returns empty string when…, Inject enrichment blocks into a system prompt string. Appends blocks after the…, Auto-discovers skills and tools for agent prompt injection. Usage:: enrichment… (+2 more)

### Community 338 - "test_unit7_catalog_propagation.py"
Cohesion: 0.08
Nodes (24): _nvidia_defaults(), tests/test_unit7_catalog_propagation.py — UNIT 7 regression tests. Verifies…, ``_get_defaults()`` must consult the catalog first; the hardcoded…, When NVIDIA key is set, ``_catalog_defaults()`` returns the catalog's nvidia…, ``_get_defaults()`` returns the catalog-derived defaults (not the hardcoded…, ``jcode.py`` must NOT have the stale hardcoded ``meta/llama-3.3-70b-instruct``…, ``opencode.py`` must NOT have the stale hardcoded model id inline., ``_NVIDIA_DEFAULT_MODEL`` must equal the first entry in the catalog's nvidia… (+16 more)

### Community 339 - "dependencies"
Cohesion: 0.08
Nodes (25): axios, fast-uri, dependencies, axios, fast-uri, livekit-client, lucide-react, react (+17 more)

### Community 340 - "reset_store"
Cohesion: 0.11
Nodes (23): Reset the store singleton (used in tests). Also resets the motor client…, reset_store(), tests/test_motor_event_loop_isolation.py — regression test for the flaky…, ``reset_store()`` must clear ``db.mongo_store._client`` and ``_db``, not just…, ``reset_store()`` must also clear the ``db._store`` wrapper (the original…, The ``client`` fixture in conftest.py must call ``reset_store()`` before…, After ``reset_store()``, the next ``MongoStore._get_db()`` call must create a…, test_client_fixture_calls_reset_store_before_lifespan() (+15 more)

### Community 341 - "Session Handoff — 2026-06-15"
Cohesion: 0.08
Nodes (24): Context the next session will need, Critical environment variables, Files changed today (for code archaeology), How to resume, Key files to know, Key labels, P0 — Add a regression test for the draft-PR safety guards, P1 — Watch Run 27481814863 for issue #504 and verify end-to-end (+16 more)

### Community 342 - "TASK 4 — End-to-end approval-gate test"
Cohesion: 0.08
Nodes (24): 3.1 — Confirm env vars on the **web** service, 3.2 — Confirm single-poller guard on the **worker**, 3.3 — Verify the bot responds (human-in-the-loop), 3.4 — TASK 3 acceptance, 4.1 — Acquire an admin session, 4.2 — Trigger an outward-facing workflow run, 4.3 — Watch the run until it pauses, 4.4 — Confirm the Telegram message arrived (+16 more)

### Community 343 - "mcp_dispatch"
Cohesion: 0.12
Nodes (22): guard(), identity_from_headers(), Any, Build an AgentIdentity from the caller's ``X-Agent-*`` headers. Absent headers…, Evaluate *tool* before it runs. Returns ``(allowed, message, decision)``.…, Wall-clock timer for the audit row's ``duration_ms``., Governance posture, for the ``/health`` payload. Surfaced on the health…, status() (+14 more)

### Community 344 - "Any"
Cohesion: 0.15
Nodes (3): Any, field_validator, Coerce unrecognised system_type values to 'custom' so the model never crashes…

### Community 345 - "test_north_mini_code.py"
Cohesion: 0.08
Nodes (15): north_mini_code_model_for(), Return the North Mini Code model id served by *provider*, else ``None``.…, tests/test_north_mini_code.py — North Mini Code 1.0 integration. Covers the…, The switch defaults ON so North is the default post-install., The agency/Hermes execution path defaults to North via the resolver., Hermes must be able to run the agency with the full Hermes-OS capacity set —…, Only high/medium/low are honoured; anything else means 'unset'., North is cost_tier=2, so it must not become the ``best_model_for`` pick for the… (+7 more)

### Community 346 - "ClaudeCodeAdapter"
Cohesion: 0.14
Nodes (20): ClaudeCodeAdapter, json_safe(), Any, TaskResult, TaskSpec, Adapter for Claude Code CLI — FIRST CLASS autonomous coding runtime., adapter(), asyncio (+12 more)

### Community 347 - "AgentMessageBus"
Cohesion: 0.15
Nodes (9): AgentMessageBus, get_agent_bus(), Remove a subscription., Return all topics that have history., Return the module-level AgentMessageBus singleton., Pub/sub message bus for inter-agent communication. Agents subscribe to topics…, Decorator: subscribe a callback to a topic pattern. Supports ``*`` (single…, asyncio (+1 more)

### Community 348 - "CompanyAgencyService"
Cohesion: 0.11
Nodes (14): CompanyAgencyService, Any, SpecialistFamily, Orchestrates specialist activation, runtime startup, and 24x7 scheduling for a…, Return the best available runtime for a specialist family. Checks available…, Return the ordered runtime preferences for a specialist family., Activate a company's AI agency after onboarding completes. Steps: 1. Assign…, Deactivate a company's AI agency. Stops all company-specific schedules and… (+6 more)

### Community 349 - "TemporalContextGraph"
Cohesion: 0.10
Nodes (14): demo_agent_tracking(), datetime, Temporal context graph inspired by Graphiti…, Get history of an entity between two times, Get current state of an entity (most recent fact), Query facts with pattern matching, Get source (provenance) of a specific fact, A fact at a specific point in time (+6 more)

### Community 350 - "test_daily_automation_2026_08_03.py"
Cohesion: 0.11
Nodes (14): _load_yaml(), tests/test_daily_automation_2026_08_03.py — Daily automation (2026-08-03).…, brain_config.py anthropic candidates must exactly match models.yaml (order and…, brain_config.py aerolink candidates must exactly match models.yaml (order and…, test_aerolink_candidates_match_yaml(), test_anthropic_candidates_match_yaml(), test_yaml_aerolink_candidates_contains_opus_5(), test_yaml_aerolink_judge_is_opus_5() (+6 more)

### Community 351 - "TestClassifyPlainText"
Cohesion: 0.08
Nodes (6): tests/test_inbound_router.py Pytest coverage for…, The 3500-char default matches the design recommendation; below the delivered…, TestBigPasteThreshold, TestClassifyPlainText, TestSanitizePasteForPreview, TestSavePaste

### Community 352 - "test_sam_livekit.py"
Cohesion: 0.08
Nodes (16): auth_headers(), livekit_env(), no_livekit_env(), tests/test_sam_livekit.py — SAM realtime voice (LiveKit) integration. Covers: -…, Auth headers for the seeded admin user (same pattern as test_agile_api)., The worker module must import cleanly even when livekit-agents is absent., SamAgent.build_context (used by worker tools) must return a dict., Configure a fake LiveKit deployment via env vars. (+8 more)

### Community 353 - "test_service_token.py"
Cohesion: 0.08
Nodes (19): tests/test_service_token.py — N5 acceptance: service-token auth surface. Tests…, Near-miss tokens must not pass (no prefix-match, no fuzzy match)., After verification, the module must NOT hold the plaintext token — only the…, The token plaintext must NEVER appear in logs. Capture every log record emitted…, The module must use hmac.compare_digest (not ==) for the comparison — timing…, The service token must only gate a narrow allowlist of endpoints — not all of…, When SERVICE_TOKEN is rotated in the env, the new token must verify (within the…, Load services.service_token fresh in each test so env-var changes take effect. (+11 more)

### Community 354 - "github_tools.py"
Cohesion: 0.20
Nodes (23): get_repo(), _get_token(), _get_user(), init_workspace(), list_branches(), list_prs(), list_repos(), BaseModel (+15 more)

### Community 355 - "app_settings.py"
Cohesion: 0.14
Nodes (23): all_settings(), _as_bool(), _as_int(), ephemeral_ttl_hours_cached(), get_setting(), _maybe_schedule_refresh(), onboarding_gate_enabled(), onboarding_gate_enabled_cached() (+15 more)

### Community 356 - "Findings"
Cohesion: 0.08
Nodes (23): E2E Tests, Findings, Immediate (Current Sprint), Integration Tests, Live/External Tests (skipped in standard CI), Missing Test Areas, Sprint 1, Sprint 2 (+15 more)

### Community 357 - "Local AI Stack with Docker"
Cohesion: 0.08
Nodes (23): 1. Clone and configure, 2. Start the stack (GPU), 3. Start the stack (CPU only), 4. Pull models (first run), 5. Access services, CPU Only, Data Persistence, Default (GPU) (+15 more)

### Community 358 - "Traffic Distribution Across Providers"
Cohesion: 0.08
Nodes (22): Agent Autonomy Roadmap, Design constraints honored, New environment variables, Proactive rate-limit pacing (free-tier reliability), The eight gaps and what closed them, Verification performed, What was already strong (verified, no changes needed), Why this document exists (+14 more)

### Community 359 - "Implementation Prompt: Rich TaskBoard + Agile Sprint Integration"
Cohesion: 0.08
Nodes (23): 1. Task model extensions (`tasks/models.py`), 2. New task endpoint (`tasks/api.py`), 3. Agile REST endpoints (`backend/server.py`), 4. TaskBoardScreen upgrade (`frontend/src/v5/screens/TaskBoardScreen.jsx`), 4a. "Needs Clarification" 7th column, 4b. Right-side detail panel, 4c. Sprint view mode toggle, 4d. Create-task modal enhancements (+15 more)

### Community 360 - "Telegram Bot Setup"
Cohesion: 0.08
Nodes (24): Admin commands (immediate, no confirmation), Admin commands with approval required, Approval Workflow, Authorization Model, Command Reference, Debugging message delivery, Debugging proxy connection failures, Linux (systemd) (+16 more)

### Community 361 - "SchedulesPage.js"
Cohesion: 0.13
Nodes (18): createSchedule(), listSchedules(), pauseSchedule(), resumeSchedule(), triggerSchedule(), C, FREQ_OPTS, FREQ_TO_CRON (+10 more)

### Community 362 - "RuntimesPage.js"
Cohesion: 0.13
Nodes (20): getRoutingPolicy(), listRuntimes(), refreshRuntimeHealth(), runTaskOnRuntime(), startAllRuntimes(), startRuntime(), stopAllRuntimes(), stopRuntime() (+12 more)

### Community 363 - "video_transcript.py"
Cohesion: 0.12
Nodes (23): caption_tracks(), extract_player_response(), fetch_transcript(), _get(), is_video_url(), parse_json3(), parse_timedtext_xml(), Extract a usable text transcript from a video URL, without an API key. Why this… (+15 more)

### Community 364 - "control_overrides.py"
Cohesion: 0.12
Nodes (23): _as_int(), _control_state(), effective_value(), load_overrides(), _policy_updates(), Any, packages/config/control_overrides.py — DB-persisted overrides for platform…, Read the stored overrides. Returns ``{}`` on any storage failure. The fail-open… (+15 more)

### Community 365 - "distributed.py"
Cohesion: 0.11
Nodes (14): DistributedRateLimiter, get_limiter(), get_persistent_queue(), _LocalBucket, packages/llm/distributed.py — cross-instance coordination. Two facilities that…, True once a Redis connection has actually been established., Consume capacity, waiting up to ``max_wait_sec``. Returns False when capacity…, The process-wide distributed rate limiter. (+6 more)

### Community 366 - "CollectionLike"
Cohesion: 0.12
Nodes (12): get_storage(), packages/storage/factory.py — storage backend factory. Returns the appropriate…, Return the active storage backend. During migration, this delegates to the…, Reset the storage singleton (for tests)., reset_storage(), CollectionLike, Any, Protocol (+4 more)

### Community 367 - "test_regression.py"
Cohesion: 0.12
Nodes (19): browser_login(), main(), Full desktop regression suite., Full mobile regression suite (navigation + key page loads)., Log in through the browser UI. Returns True on success., API Key CRUD: create, copy, list, delete., Tasks: create, list, view., GitHub integration: status, repos. (+11 more)

### Community 368 - "test_agency_fix.py"
Cohesion: 0.08
Nodes (23): agency_fix(), tests/test_agency_fix.py — N3 acceptance tests for scripts/agency_fix.py. The…, An edit that produces a syntactically-broken Python file must be rejected —…, An edit that truncates a real code file to a trivial body must be rejected —…, With no issue linked, decline is just an exit-code signal — no API call., When an issue is linked but no GH_PAT/GH_TOKEN is set, the decline fails loudly…, When an issue is linked and the API call succeeds, decline_cleanly returns True…, When the API call itself fails (network error), decline_cleanly returns False… (+15 more)

### Community 369 - "test_output_filter.py"
Cohesion: 0.08
Nodes (23): tests/test_output_filter.py — Unit tests for output_filter.py Verifies token…, pytest output with failures should preserve failure details., Deep Python traceback should collapse intermediate frames., Large curl output should be truncated with head/tail., When disabled, output should pass through (truncated to max_chars)., Empty or whitespace-only input should pass through unchanged., git log with 200 commits should be compressed., Small git status should pass through unchanged. (+15 more)

### Community 370 - "test_telegram_mutating_commands.py"
Cohesion: 0.08
Nodes (17): _make_mock_response(), tests/test_telegram_mutating_commands.py — N5 acceptance: /setbrain + /merge.…, Build a mock httpx.Response., A successful /setbrain call must: 1. send the X-Service-Token header 2. PATCH…, When the backend's liveness probe fails (HTTP 422), the bot reply must surface…, 503 = backend doesn't have SERVICE_TOKEN set. The bot reply must tell the…, A successful /merge call returns the merge SHA + actor attribution so the…, When the backend refuses to merge (draft, failing CI, not mergeable), the bot… (+9 more)

### Community 371 - "test_workspace_security.py"
Cohesion: 0.10
Nodes (9): TestWorkspacePathDerivation, Security-oriented tests for workspace isolation (Area C4). Covers: - No path…, The hash component should not be reversible to the original ID., Workspace root path should be fully resolved (no . or ..)., TestCleanupIsolation, TestSymlinkAttackPrevention, TestWorkspaceHashing, _hash_component() (+1 more)

### Community 372 - "refine"
Cohesion: 0.17
Nodes (10): propose_entries(), Turn qualifying lessons into candidate entries. A lesson qualifies only when it…, Promote repeated lessons into the spec. Returns the entries added. No-op unless…, refine(), _lesson(), Regressions for defects found in review of this module., The core guarantee: no citation, no entry., TestProposal (+2 more)

### Community 373 - "platform_controls_router.py"
Cohesion: 0.11
Nodes (22): _actor(), build_platform_controls_router(), ControlUpdateBody, APIRouter, BaseModel, backend/platform_controls_router.py — admin API for the platform controls.…, A stable identifier for the audit trail on each write., One or more control changes, as ``{"updates": {"KEY": value}}``. (+14 more)

### Community 374 - "Agent Governance Guide"
Cohesion: 0.09
Nodes (23): A tool call is judged twice, Agent Governance Guide, `[]` and absent mean opposite things, API, Approvals, Architecture, Audit trail, Backends (+15 more)

### Community 375 - "The fifteen strategies"
Cohesion: 0.09
Nodes (22): adaptive *(default)*, automatic_failover, Candidate selection, Choosing one, context_length_optimized, cost_optimized, fallback_chain, highest_success_rate (+14 more)

### Community 376 - "ServiceManager"
Cohesion: 0.11
Nodes (14): get_status(), BaseModel, get, post, Start the FastAPI proxy server., Serve the launcher UI., Get current service status., root() (+6 more)

### Community 377 - "_Cursor"
Cohesion: 0.10
Nodes (7): _Cursor, _PendingCursor, Async iterator wrapping a list of dicts (already decoded from JSON)., Return a sort key that tolerates mixed float/str timestamp values. Some code…, Return a _Cursor (evaluated lazily on first await/iteration)., A cursor that fetches its data lazily on first use., _safe_sort_key()

### Community 378 - "WindowsServiceManager"
Cohesion: 0.18
Nodes (7): _creationflags(), CompletedProcess, Path, service_manager.py — auto-generated module docstring (user-research skill scan)., Spawn a new proxy process on Linux/Mac using the current Python interpreter., ServiceState, WindowsServiceManager

### Community 379 - "SyntheticDataPipeline"
Cohesion: 0.13
Nodes (8): Return samples filtered by minimum reward score., Export samples in Alpaca JSONL format. Returns the path to the exported file., Export samples in ShareGPT JSONL format. Returns the path to the exported file., Export all samples as a structured JSON array. Returns the path to the exported…, Clear all accumulated samples., Pipeline to generate synthetic training data from agent sessions. Usage::…, SyntheticDataPipeline, TestSyntheticDataPipeline

### Community 380 - "test_all_features.py"
Cohesion: 0.09
Nodes (9): TestActivity, TestCompany, TestDashboard, TestDoctor, TestOnboarding, TestSecrets, TestSetup, TestTasks (+1 more)

### Community 381 - "_get"
Cohesion: 0.12
Nodes (9): _get(), Contract tests for the provider on/off endpoints. ``GET /api/brain/providers``…, Silently storing a typo'd id would leave a switch nothing can turn back on., The operator has to know WHY before deciding to switch it back on. The raw…, The response reaches the browser — a leaked key would be a disclosure., The switch has to reach the dispatcher, not just the listing., TestDisabledReasonIsReadableNextToTheSwitch, TestListing (+1 more)

### Community 382 - "TestBrainConfigUpdates"
Cohesion: 0.14
Nodes (5): tests/test_daily_automation_2026_07_10.py — Daily automation tests…, Verify Llama 4 and Claude Sonnet 5 cross-provider aliases are registered., Verify brain_config.py changes: Google provider, updated presets., TestBrainConfigUpdates, TestBrainFailoverModelAliases

### Community 383 - "test_monitor_lib.py"
Cohesion: 0.11
Nodes (8): _isolate_env(), MonkeyPatch, tests/test_monitor_lib.py — unit tests for scripts/monitor_lib.py. Covers the…, Pin all env-overridable paths to tmp_path for hermetic tests., TestAwaitReady, TestIsProcessAlive, TestSuperviseLoopGiveUp, TestSupervisorTick

### Community 384 - "Path"
Cohesion: 0.16
Nodes (6): Path, Old log + done signal + no .incomplete = complete (caller can cleanup the log…, TestDownloadStatus, TestReadPidFile, TestSupervisorStateAtomic, _write_log()

### Community 385 - "test_mostly_failed_steps.py"
Cohesion: 0.12
Nodes (22): _make_result(), _make_step(), tests/test_mostly_failed_steps.py — regression test for the "21/22 failed steps…, A BLOCKED judge verdict should never be success, regardless of steps., When mostly_failed, the output should contain a clear failure summary., 0 steps → no gate (division by zero avoided, total_steps < 4)., 6 failed + 2 applied = 75% failure, 2 applied < 3 → mostly_failed., Build a mock agent result dict (the shape InternalAgentAdapter expects). (+14 more)

### Community 386 - "test_v4_api.py"
Cohesion: 0.12
Nodes (22): auth_headers(), TestClient, tests/test_v4_api.py — Tests for the v4 dashboard API endpoints., Return the test client — reuses conftest client which has bootstrap., Get auth headers by logging in as admin via the admin API., GET /v4/status returns 200 with improvement_loop and self_healing keys., GET /v4/improvements returns 200 with active and resolved lists., GET /v4/tasks returns 200 with tasks array. (+14 more)

### Community 387 - "LocalWorkspace"
Cohesion: 0.14
Nodes (10): LocalWorkspace, Path, Backwards-compat: accepts 'owner/repo' format., Manages a local git clone of a GitHub repository. Clones are stored under…, Run a git command. Never uses shell=True., Clone the repo if it doesn't exist; pull if it does., Return the current working-tree diff (staged + unstaged)., Stage files and commit. paths=None stages everything; paths=[] raises. (+2 more)

### Community 388 - "classify_direct_chat_intent"
Cohesion: 0.13
Nodes (19): classify_direct_chat_intent(), _contains_keyword(), detect_intent(), intent.py — Intent classification for direct chat (answer_only, execute_now,…, Return True if content contains any execution or analysis keyword., Detect the user's intent from message content., Map lower-level intents into conversation-driven action categories. Returns one…, classify_plain_text() (+11 more)

### Community 389 - "._connect"
Cohesion: 0.10
Nodes (10): Any, Connection, Path, Recall a specific memory entry., Auto-load relevant memories based on context. Returns memories prioritized by:…, Get all memories in a specific category., Delete a memory entry., Export all memories for a user (for backup/migration). (+2 more)

### Community 390 - "timedelta"
Cohesion: 0.16
Nodes (18): PR throughput per cohort over the last `days` days., Count distinct sessions per user. A session ends when there's a gap of more…, Return True if a fetched oauth_states doc is a valid, unexpired login state., _valid_login_state(), _doc(), Regression tests for social-login (GitHub & Google) OAuth state handling. Bug…, MongoDB/motor returns naive UTC datetimes. Subtracting a naive datetime from an…, The login handlers must persist state via _store_login_state, not the session… (+10 more)

### Community 391 - "test_dashboard_cache.py"
Cohesion: 0.14
Nodes (17): _cached(), _fast_count(), get_activity(), Single-flight TTL cache. Concurrent callers wait for the first producer., Count without materialising rows — prefers estimated_document_count., _clear_cache(), _CollWithEstimate, _CollWithoutEstimate (+9 more)

### Community 392 - "Harness"
Cohesion: 0.14
Nodes (16): detect_harness(), Harness, harness_context_limit(), harness_stats(), HarnessProfile, Any, Enum, Detect which AI coding tool is calling the proxy. Checks in priority order: 1.… (+8 more)

### Community 393 - "_process_task_callback"
Cohesion: 0.17
Nodes (21): _answer_callback(), _edit_message(), _process_task_callback(), _process_wfo_callback(), Handle an inline Approve/Reject button on a WorkflowOrchestrator approval-gate…, Edit an existing message's text and (optionally) its inline keyboard. Best-…, Acknowledge a callback query so Telegram stops the button's loading spinner.…, Handle Approve/Reject inline-button presses for task execution gates. Callback… (+13 more)

### Community 394 - "test_portfolio_intelligence.py"
Cohesion: 0.10
Nodes (6): Tests for agents/portfolio_intelligence.py — autonomous signal → initiative.…, DEFAULT_REPO was hardcoded to the stale pre-rename repo name…, TestBuild, TestDefaultRepoFollowUpFix, TestGithubAndResearch, TestParsing

### Community 395 - "TestRenderMCPSidecarService"
Cohesion: 0.16
Nodes (11): _env(), The Go binary hardcodes :10000 and ignores $PORT, so Render must be told., In HTTP mode the token comes from the caller's header, so nothing here is…, The mux serves /mcp only; a health check there opens an SSE stream that never…, pkg/oauth fails the process at boot on a partial OAuth config., The backend must use the private-network address, not the public URL., A free service sleeps at ~15m idle; polling must stay under that., _render_yaml() (+3 more)

### Community 396 - "_P"
Cohesion: 0.19
Nodes (8): _ids(), _P, A provider with no latency sample must be able to earn one., The safety invariant: a shuffle may not promote a paid provider ahead of the…, With every provider idle a stable sort would send the whole burst to the first…, No explicit weights: the provider that has spent less of its minute should be…, Minimal provider stand-in — the director only needs ``provider_id``., TestOrdering

### Community 397 - "test_voice.py"
Cohesion: 0.15
Nodes (13): Any, agent/voice.py — Voice Command Interface Hands-free agent interaction: record…, Transcribe raw PCM *audio_bytes* to text., Record then transcribe in one call., Record *duration_s* seconds of audio. Returns raw PCM bytes (int16 LE, 16 kHz…, _stub_result(), TranscriptionResult, Tests for agent/voice.py — Voice Command Interface (stub-mode tests). (+5 more)

### Community 398 - "CollaborationContext"
Cohesion: 0.11
Nodes (6): CollaborationContext, Any, Apply context updates from a contributor. Only the active editor can modify…, Run one sync tick across all sessions. Actions taken: - Kick idle active…, Shared context blob propagated to all session participants. Carries the active…, TestCollaborationContext

### Community 399 - "model_discovery.py"
Cohesion: 0.13
Nodes (20): Return the discovered model list for *provider_id*, or ``[]`` if unknown., _served_models(), cached_models(), discover_models(), _fresh_entry(), _models_url(), _parse_ids(), Any (+12 more)

### Community 400 - "_resolve_user_github_token"
Cohesion: 0.18
Nodes (17): Return the caller's GitHub token from EITHER place it can be stored. A token…, _resolve_user_github_token(), _FakeCollection, _FakeDB, patch_db(), asyncio, The doctor must find a GitHub token wherever the connect flow stored it.…, A diagnostics lookup must never turn into a 500. (+9 more)

### Community 401 - "V3 API Migration Plan — LLM Relay Platform"
Cohesion: 0.10
Nodes (20): Acceptance Checks, Approach, Auth Flow (v3 JWT-based), Backward Compatibility, Current State Analysis, Data Model Changes, Database/Storage, Files to Create/Modify (+12 more)

### Community 402 - "AppShell.jsx"
Cohesion: 0.12
Nodes (11): getAccountLifecycle(), AppShell(), MOBILE_MORE, MOBILE_PRIMARY, NAV_ITEMS, EphemeralBanner(), formatRemaining(), APP_LABEL (+3 more)

### Community 403 - "PortfolioScreen.jsx"
Cohesion: 0.10
Nodes (13): getPortfolioBoard(), refreshPortfolio(), btnStyle, HEALTH, HORIZONS, PortfolioScreen(), SOURCE, STATUS_COLOR (+5 more)

### Community 404 - "allow_paid"
Cohesion: 0.13
Nodes (19): allow_paid(), _fetch_policy(), .github/scripts/provider_policy.py — Read the durable provider policy from the…, Fetch the provider policy from the backend API. Never raises., Return True if paid providers (Anthropic) are allowed by policy., Reset the cached policy (test helper)., reset_cache(), _call_review_llm() (+11 more)

### Community 405 - "test_chat_mode_regressions.py"
Cohesion: 0.18
Nodes (19): ProviderResult, _auth_headers(), test_agent_status_endpoint_reports_live_progress_and_tool_calls(), test_agent_stream_endpoint_emits_server_sent_events(), test_chat_send_emits_langfuse_observation_for_direct_chat(), test_chat_send_keeps_complex_prompt_on_direct_path_when_agent_mode_is_off(), test_chat_send_keeps_explanatory_github_pr_guidance_on_direct_path(), test_chat_send_keeps_general_docker_explanation_on_direct_path_when_no_repo_action_is_requested() (+11 more)

### Community 406 - "system_instruction"
Cohesion: 0.16
Nodes (5): Return a plain-English JSON instruction for a ``response_format`` dict. Returns…, system_instruction(), system_instruction() uses stronger language when strict: true., TestSystemInstructionStrictMode, TestSystemInstruction

### Community 407 - "daily_digest.py"
Cohesion: 0.23
Nodes (18): aggregate_last_24h(), build_daily_digest(), compute_cutoff(), format_digest_markdown(), _md_escape(), _now_utc(), Any, datetime (+10 more)

### Community 408 - "GuardrailEngine"
Cohesion: 0.16
Nodes (7): get_guardrails(), GuardrailEngine, Configurable safety rail engine for LLM inputs and outputs. Supports: -…, Load guardrail rules from a YAML or JSON config file., Compile regex patterns from the rules configuration., Return the module-level GuardrailEngine singleton., TestGuardrailEngine

### Community 409 - "test_issue_triage.py"
Cohesion: 0.17
Nodes (19): _match_family(), Any, services/issue_triage.py — inbound GitHub issue triage. Closes the intake gap…, Classify a single GitHub issue payload and return the routing decision. Pure…, Fetch unlabeled open issues, triage each, and route them. Returns a summary…, run_triage_cycle(), _severity_for(), triage_enabled() (+11 more)

### Community 410 - "NIMConnectionPool"
Cohesion: 0.13
Nodes (9): NIMConnectionPool, AsyncClient, Persistent httpx.AsyncClient pool with circuit breaker and retry logic. Manages…, Get or create the shared httpx.AsyncClient., Context manager for a pooled client session., Close the connection pool., Manually reset a provider's circuit breaker to CLOSED., Compute exponential backoff delay with jitter. (+1 more)

### Community 411 - "weekly_digest.py"
Cohesion: 0.13
Nodes (15): build_digest(), _count_open_auto_prs(), _load_readiness(), Any, services/weekly_digest.py — Weekly readiness digest for Telegram. Compiles loop…, Send the digest text via NotificationDispatcher (Telegram)., Load loop readiness report from the registry., Count open PRs with the 'automated' or 'auto-pr' label via git log heuristic. (+7 more)

### Community 412 - "test_local_controller.py"
Cohesion: 0.17
Nodes (20): _env_defaults(), _fake_http_sequence(), _fake_subprocess_run(), _import_controller(), tests/test_local_controller.py — unit tests for the local GLM-5.2 daemon. These…, The diag output must surface binary/model errors clearly., Pins the v3 fix: after the multi-port preamble probe finds colibri serving a…, Yield a list of (status, body) tuples the daemon will see in order when it… (+12 more)

### Community 413 - "run_trend_analysis"
Cohesion: 0.19
Nodes (13): Tests for trend_analysis.py — last30days-style window over TrendWatcher (issue…, TestRunTrendAnalysis, TestWindow, BaseModel, trend_analysis.py — last30days-style trend analysis (issue #493). Adapts the…, True if the ISO-ish published date falls within the last N days.…, Fetch trends via TrendWatcher, filter to a 30-day window, persist summary., Write trends/trend_summary.md (and a dated copy); return the path. (+5 more)

### Community 414 - "test_unit5_ui_provider_surface.py"
Cohesion: 0.10
Nodes (15): tests/test_unit5_ui_provider_surface.py — UNIT 5 regression tests. Verifies…, The component must call ``providerLabel(p)`` rather than indexing a 4-entry…, The dropdown shows a [free]/[paid]/[local] tier tag so the operator can tell…, The <option> tag uses providerLabel(p), not PROVIDER_LABELS[]., The operator must be able to see what a key really serves. ``candidates`` is…, The GET endpoint response must list every BrainProvider Literal entry. Before…, Providers that were filtered out before UNIT 5 are now present. ``mistral``,…, A known paid provider is reported as tier=paid (was filtered before). (+7 more)

### Community 415 - "MemoryCategory"
Cohesion: 0.16
Nodes (14): Memory middleware for automatic context injection into AI tool requests. This…, MemoryCategory, MemoryEntry, MemoryScope, Enum, Row, str, Enhanced persistent memory system with auto-loading across AI coding tools.… (+6 more)

### Community 416 - "test_permissions.py"
Cohesion: 0.15
Nodes (15): PermissionAssessment, Any, agent/permissions.py — Adaptive Permission Classifier Reads the session…, Convenience helper — True when the inferred level is read_write or full_access., Analyse *messages* and return a :class:`PermissionAssessment`., _msgs(), Tests for agent/permissions.py — Adaptive Permissions., test_assessment_as_dict() (+7 more)

### Community 417 - "PersistentMemoryStore"
Cohesion: 0.24
Nodes (19): PersistentMemoryStore, Enhanced persistent memory store with auto-loading support. Features: -…, cmd_autoload(), cmd_delete(), cmd_export(), cmd_import(), cmd_list(), cmd_recall() (+11 more)

### Community 418 - "Skill: modularity-review"
Cohesion: 0.10
Nodes (19): Acceptance Checks, Applying to This Repo, Further Reading, Modularity Findings Template, Part A: Reviewing Existing Code for Modularity Problems, Part B: Designing New Modular Boundaries, Skill: modularity-review, Step 1 — Map the dependency graph (+11 more)

### Community 419 - "Design Audit"
Cohesion: 0.10
Nodes (19): Code Quality, Color and Surfaces, Component Patterns, Content, Design Audit, Fix Priority, How This Works, Iconography (+11 more)

### Community 420 - "Findings"
Cohesion: 0.10
Nodes (19): API Documentation, Architecture Documentation, DOC-001 [HIGH] — No SECURITY.md, DOC-002 [HIGH] — No CONTRIBUTING.md, DOC-003 [HIGH] — No API.md / OpenAPI Export, DOC-004 [MEDIUM] — README.md is 31KB and Needs Pruning, DOC-005 [MEDIUM] — `REVIEW_AND_FIXES.md` and `AGENCY_CORE_V5_PROGRESS.md` are Unclear, DOC-006 [MEDIUM] — No DEPLOYMENT.md at Root (+11 more)

### Community 421 - "TestRenderRouter"
Cohesion: 0.13
Nodes (15): build_render_router(), Any, APIRouter, Exception, backend/render_router.py — Render platform view for operators and agents.…, Reject anyone who is not the agency admin., Map an MCP transport failure onto 503 rather than a 500. The distinction…, _require_admin() (+7 more)

### Community 422 - "Skill: modularity-review"
Cohesion: 0.10
Nodes (19): Acceptance Checks, Applying to This Repo, Further Reading, Modularity Findings Template, Part A: Reviewing Existing Code for Modularity Problems, Part B: Designing New Modular Boundaries, Skill: modularity-review, Step 1 — Map the dependency graph (+11 more)

### Community 423 - "crispy_client.py"
Cohesion: 0.14
Nodes (18): cmd_approve(), cmd_artifacts(), cmd_build(), cmd_events(), cmd_reject(), cmd_status(), cmd_watch(), _get() (+10 more)

### Community 424 - "4. Troubleshooting"
Cohesion: 0.10
Nodes (19): 1. Which sandbox backend applies where, 2. Container hardening, 3. Supply chain, 4. Troubleshooting, 5. Scaling, Agents suddenly failing after enabling enforcement, An agent is stuck, Applying the overlay to the local stack (+11 more)

### Community 425 - "Docker AI Governance Audit — Final Report"
Cohesion: 0.10
Nodes (20): 1. Executive summary, 2. Architecture review, 3. Risk assessment, 4. Security review, 5. What was implemented, 6. Explicitly not implemented, 7. Remaining recommendations, 8. Future enhancements (+12 more)

### Community 426 - "1. Capability-by-capability"
Cohesion: 0.10
Nodes (19): 0. The finding that shapes everything else, 1.10 Least Privilege, 1.11 Multi-Agent Governance (10 / 100 / 1000 agents), 1.12 Cost Governance, 1.13 Compliance (SOC2 / ISO27001 / GDPR), 1.14 Local Development Experience, 1.1 Agent Identity, 1.2 Tool Governance (+11 more)

### Community 427 - "4. Threats"
Cohesion: 0.10
Nodes (20): 1. What makes this system different from a normal web app, 2. Assets, 3. Trust boundaries, 4. Threats, 5. Why the engine fails open but approvals fail closed, 6. Honest limits, 7. Priority follow-ups, T10 — Supply-chain compromise via base image (+12 more)

### Community 428 - "Dynamic Model Routing"
Cohesion: 0.10
Nodes (20): Architecture, Built-in Claude → local alias table, Configuring fast_response routing, Configuring model preferences, Curl example, Dynamic Model Routing, Fallback execution, Health check and availability filtering (+12 more)

### Community 429 - "ControlsScreen.jsx"
Cohesion: 0.15
Nodes (15): getPlatformControls(), resetPlatformControl(), setPlatformControls(), { getPlatformControls, setPlatformControls, resetPlatformControl }, secondGroup, BANNER(), ControlRow(), ControlsScreen() (+7 more)

### Community 430 - "output_filter.py"
Cohesion: 0.10
Nodes (17): _filter_curl(), _filter_docker(), _filter_git(), _filter_ls(), _filter_npm(), _filter_pip(), _filter_pytest(), _filter_python() (+9 more)

### Community 431 - "compilerOptions"
Cohesion: 0.10
Nodes (19): DOM, DOM.Iterable, ES2022, src, vite/client, compilerOptions, isolatedModules, jsx (+11 more)

### Community 432 - "HarnessRegistry"
Cohesion: 0.16
Nodes (8): HarnessMetrics, HarnessRegistry, HarnessSessionRecord, _NoopDB, Any, BaseModel, services/harness_registry.py — Persistent Harness Registry Tracks which AI…, Persistent registry of harnesses and their performance history. Stores session…

### Community 434 - "Page"
Cohesion: 0.15
Nodes (7): Page, Chat: send message, view sessions, delete session, agent mode toggle., Runtimes: list, health, decisions, policy., Settings, Secrets, Features, Setup, GitHub, Activation., TestChat, TestRuntimes, TestSettings

### Community 435 - "test_backend_runtime_bootstrap.py"
Cohesion: 0.11
Nodes (9): anyio, Web lifespan delegates to start_background_services when…, RUN_BACKGROUND_IN_WEB=false: lifespan starts but background services are NOT…, _StubRuntimeManager, _StubRuntimeRegistry, _StubTask, _StubTaskDispatcher, test_backend_lifespan_skips_bg_when_flag_false() (+1 more)

### Community 436 - "test_llm_router_tpm.py"
Cohesion: 0.15
Nodes (19): _big_request(), _ok(), A per-minute token budget is an input ceiling, not just a sort key. Reproduces…, A conversation comfortably past the metered provider's per-minute budget.…, A 131k window behind a 4k budget is a 4k ceiling., Routing around the low ceiling beats compressing to fit it., Production's case: every reachable provider has a low ceiling. Nothing can be…, No compression tax on requests that already fit. (+11 more)

### Community 437 - "test_tasks_cache_ttl_env.py"
Cohesion: 0.21
Nodes (19): MonkeyPatch, Round-trip tests for TASKS_LIST_ALL_CACHE_TTL_SEC env-var override in…, With a lowered cap, a value above the new cap falls back to default., Reload tasks.api after injecting TASKS_LIST_ALL_CACHE_TTL_SEC=value (or unset)., Values above the 1h upper bound in _safe_ttl fall back to default. Guards the…, Value equal to the 1h upper bound is honored (boundary case)., ``TASKS_MAX_CACHE_TTL_SEC`` env var overrides the cap module-level constant., _reload_tasks_api_with_env() (+11 more)

### Community 438 - "test_voice_pipeline.py"
Cohesion: 0.14
Nodes (14): asyncio, Tests: Voice pipeline — STT backend selection, TTS backend selection, memory…, A stalled gTTS/pyttsx3 call must not hang synthesize() forever. gTTS/pyttsx3…, TTS_SYNTHESIZE_TIMEOUT_SEC must override the default ceiling., gTTS/pyttsx3 must run on a dedicated executor, not the shared default.…, test_memory_export_markdown(), test_memory_forget(), test_memory_recall_empty() (+6 more)

### Community 439 - "TestUpdateTask"
Cohesion: 0.16
Nodes (7): _NoopCheckpointStore, WorkflowRun, tests/test_workflow_orchestrator_update_task.py Pytest coverage for…, Stand-in for the real Mongo checkpoint store., Two consecutive updates collapse: the latest instruction wins. This matches…, _run(), TestUpdateTask

### Community 440 - "MemoryKernel"
Cohesion: 0.16
Nodes (7): Fact, get_memory_kernel(), MemoryKernel, voice/memory_kernel.py — Jarvis OS-inspired Memory Kernel. Stores atomic facts…, Return most relevant facts. Simple substring match on content., SQLite-backed atomic fact store with Markdown mirror., Store a new atomic fact or reinforce an existing one.

### Community 441 - "harness_spec.py"
Cohesion: 0.16
Nodes (15): _int_env(), _known_entry_texts(), _one_line(), Any, Path, agent/harness_spec.py — the Continual Harness: a persistent, cited spec.…, Absolute path of the harness spec for a workspace., Recorded lessons as ``{signature: {acceptable text, ...}}``. The citation binds… (+7 more)

### Community 442 - "test_loop_registry.py"
Cohesion: 0.21
Nodes (16): LoopRegistry, The full fleet catalogue., loop-cost: total fleet token spend over 30 days., tests/test_loop_registry.py — Loop Engineering governance layer. Pins the…, _spec(), test_by_id_lookup(), test_cost_scales_with_tier_and_cadence(), test_drift_flags_missing_scheduled_workflow() (+8 more)

### Community 443 - "_extract_tech_relevance"
Cohesion: 0.17
Nodes (6): _extract_tech_relevance(), Dynamic extraction: finds any tech keyword mentioned in the skill content,…, Tests for _extract_tech_relevance() word-boundary matching., Integration-style tests for the recommendation path (no I/O)., TestExtractTechRelevance, TestRecommendLogic

### Community 444 - "agile_api.py"
Cohesion: 0.24
Nodes (18): complete_sprint(), create_sprint(), _get_mgr(), get_velocity(), list_sprints(), Any, BaseModel, get (+10 more)

### Community 445 - "Skill: fabric-patterns"
Cohesion: 0.11
Nodes (18): 1. Ensure Pattern Directory Exists, 2. List Available Patterns, 3. Retrieve a Pattern, 4. Apply a Pattern with Variables, 5. Stitch Patterns Together, 6. Create New Patterns, Acceptance Checks, Directory Structure (+10 more)

### Community 446 - "Analysis & Synthesis Instructions"
Cohesion: 0.11
Nodes (18): 1. Define the Atmosphere, 2. Map the Color Palette, 3. Establish Typography Rules, 4. Define the Hero Section, 5. Describe Component Stylings, 6. Define Layout Principles, 7. Define Responsive Rules, 8. Encode Motion Philosophy (+10 more)

### Community 447 - "Production Readiness Assessment — local-llm-server"
Cohesion: 0.11
Nodes (18): 1. Availability & Reliability, 2. Observability, 3. Deployment Architecture, 4. Configuration & Secrets, 5. Recovery & Backup, 6. Cloudflare Worker Audit, Current State, Current State (+10 more)

### Community 448 - "Skill: fabric-patterns"
Cohesion: 0.11
Nodes (18): 1. Ensure Pattern Directory Exists, 2. List Available Patterns, 3. Retrieve a Pattern, 4. Apply a Pattern with Variables, 5. Stitch Patterns Together, 6. Create New Patterns, Acceptance Checks, Directory Structure (+10 more)

### Community 449 - "db/__init__.py"
Cohesion: 0.15
Nodes (7): _LazyModuleProxy, db — storage abstraction layer (V2.0 Phase 5: real code moved to…, Loads the real module on first attribute access, then replaces itself., # IMPORTANT: keep these imports LAZY (inside __getattr__) so that a Mongo-only, MongoStore, db/mongo_store.py — MongoDB store backed by Motor (existing implementation).…, Thin wrapper that exposes the Motor database as collection attributes.…

### Community 450 - "Admin Dashboard Guide"
Cohesion: 0.11
Nodes (19): Accessing the Dashboard, Admin API (Programmatic Access), Admin Dashboard Guide, Dashboard — healthy state, Dashboard — key created (one-time token flash), Dashboard — Langfuse diagnostic, Dashboard Layout, Login page (+11 more)

### Community 451 - "Implementation Plan"
Cohesion: 0.11
Nodes (18): (1) & partly (4): "Something went wrong" masks the real error everywhere, (2) & (3): Company creation flow / non-admin gate placement, (4): Agent provisioning "loading forever" — blocking subprocess in async path, (5): Tailored questions are hardcoded today, A0. Fix live scanner crashes on real-world sites (`services/scanner.py`) — do first, A. Fix error-message masking (`frontend/src/api.js`), Agent Prompt (paste this to start the implementation session), B. Make runtime activation non-blocking (`runtimes/control.py`, (+10 more)

### Community 452 - "ProviderConsole.jsx"
Cohesion: 0.11
Nodes (10): ALIASES, canonicalId(), CATALOGUE, FILTERS, ADR-0008, mergeProviders(), ProviderRow(), STATE (+2 more)

### Community 453 - "Delegation Plan (agent-ready work packages)"
Cohesion: 0.11
Nodes (18): Delegation Plan (agent-ready work packages), Findings, http://127.0.0.1:8899/, Page Details (worst first), Pillar Scores, `seo-fix-canonicals` - Fix Canonicals findings: 1 finding type(s) across 1 URL hit(s), `seo-fix-content` - Fix Content findings: 1 finding type(s) across 1 URL hit(s), `seo-fix-geo` - Fix GEO findings: 5 finding type(s) across 5 URL hit(s) (+10 more)

### Community 454 - "build_workflow.py"
Cohesion: 0.33
Nodes (18): _c(), _get(), _header(), main(), _make_headers(), _phase_icon(), _post(), _print_phases() (+10 more)

### Community 455 - "ProviderCircuit"
Cohesion: 0.15
Nodes (7): ProviderCircuit, Attempt to move from OPEN to HALF_OPEN after recovery timeout., Check if a request can be made through this circuit., Per-provider circuit breaker state machine., TestProviderCircuit, parametrize, Counting every sub-500 as a success meant the breaker could never open for the…

### Community 456 - "test_brain_patch_service_token.py"
Cohesion: 0.18
Nodes (18): clean_store(), _clear_overrides(), _make_client_with_user(), tests/test_brain_patch_service_token.py — N5 acceptance: PATCH…, N5 acceptance: no service token + no user session → 401 (not 200)., N5 regression: the existing dashboard path (no service token, non-admin user)…, N5 regression: the existing admin dashboard path (no service token, admin user)…, Reset the brain config store + point SQLITE_DB_PATH at a tmp path. (+10 more)

### Community 458 - "test_fabric_patterns.py"
Cohesion: 0.11
Nodes (5): MonkeyPatch, Path, Tests for scripts/fabric_cli.py and the fabric-patterns pattern engine., test_new_scaffolds_pattern(), test_save_and_show_roundtrip()

### Community 459 - "test_repowise_intelligence.py"
Cohesion: 0.11
Nodes (18): Test that search_codebase returns a string., Test that get_decision_flownodes returns a string., Test that update_intelligence creates the expected intelligence files., Test that get_overview returns a dictionary., Test that get_context returns a string., Test that get_risk returns a dictionary., Test that get_why returns a string., Test that the RepowiseIntelligence class initializes correctly. (+10 more)

### Community 460 - "test_schedule_persistence.py"
Cohesion: 0.15
Nodes (14): _FakePersistence, tests/test_schedule_persistence.py — #505 schedules survive restart. Regression…, Populate the store directly so hydration tests don't depend on the timing of…, Regression for the production startup path: services/background.py runs inside…, The sync attach_persistence()/rehydrate() must stay safe even if called from…, In-memory stand-in for ScheduleStore (no Mongo needed in tests)., A disabled job must be registered (paused) on rehydrate so a later…, _seed() (+6 more)

### Community 461 - "TestOrchestratorEndpointScoping"
Cohesion: 0.17
Nodes (10): api_client(), _ollama_reachable(), _override_user(), skipif, tests/test_workflow_orchestrator_scoping.py — Phase 8 multi-tenant isolation.…, Force backend.server.get_current_user to return ``user``., A non-admin's auto_approve=true is ignored — the run still pauses at HITL., approved_by comes from the session, not a client-supplied string. (+2 more)

### Community 462 - "validate_session_id"
Cohesion: 0.16
Nodes (5): TestSessionIdValidation, WorkspaceNotFoundError should not expose the base root in error messages., TestNoInternalPathLeakage, Validate and return a session ID, or raise InvalidSessionIdError., validate_session_id()

### Community 463 - "sam_livekit_worker.py"
Cohesion: 0.17
Nodes (16): LiveKitConfig, voice/livekit_config.py — LiveKit configuration (config module). Centralizes…, Resolved LiveKit + speech-provider configuration., True when the LiveKit room transport itself is usable., _build_llm(), _build_stt(), _build_tts(), entrypoint() (+8 more)

### Community 464 - "ErrorInterceptorMiddleware"
Cohesion: 0.18
Nodes (11): _dispatch_async(), ErrorInterceptorMiddleware, Any, BaseHTTPMiddleware, Exception, Request, Response, agent/error_interceptor.py — HTTP Error Interceptor Middleware… (+3 more)

### Community 465 - "ScheduleStore"
Cohesion: 0.15
Nodes (10): _backend(), _json_default(), Any, agent/schedule_store.py — durable persistence for scheduled agent jobs. Fixes…, Return all persisted schedule docs (for boot rehydration)., Persist (insert or update) a single schedule by job_id., Delete a persisted schedule., Fallback JSON encoder for schedule docs (datetimes, sets, etc.). (+2 more)

### Community 466 - "CapacityAllocation"
Cohesion: 0.11
Nodes (11): CapacityAllocation, PortfolioMetrics, Result of fitting initiatives into a fixed capacity by WSJF priority., Total job size of initiatives that fit within capacity., Unused capacity after committing the selected initiatives., Fraction of capacity consumed (0.0–1.0)., Aggregate metrics across the whole portfolio., Return initiatives sorted by WSJF (highest first). Cancelled initiatives are… (+3 more)

### Community 467 - "Comprehensive Skill Index (By Category)"
Cohesion: 0.11
Nodes (17): 10. Domain (Modelling, Training, Infra), 1. Planning and Implementation, 2. Code Quality, Architecture, and Audits, 3. State Management and Git Flow, 4. Memory, Knowledge, and Context Tuning, 5. Research, Browsing, and External Intel, 6. Session Lifecycle and Workflow, 7. Style and Craft Polish (UI / Docs / Tone) (+9 more)

### Community 468 - "Agent Skill: Principal UI/UX Architect & Motion Choreographer (Awwwards-Tier)"
Cohesion: 0.11
Nodes (17): 1. Meta Information & Core Directive, 2. THE "ABSOLUTE ZERO" DIRECTIVE (STRICT ANTI-PATTERNS), 3. THE CREATIVE VARIANCE ENGINE, 4. HAPTIC MICRO-AESTHETICS (COMPONENT MASTERY), 5. MOTION CHOREOGRAPHY (FLUID DYNAMICS), 6. PERFORMANCE GUARDRAILS, 7. EXECUTION PROTOCOL, 8. PRE-OUTPUT CHECKLIST (+9 more)

### Community 469 - "Component Map"
Cohesion: 0.11
Nodes (17): Architecture Audit — local-llm-server, Architecture Diagram, Component Map, Layer 10 — WebUI (`webui/`), Layer 11 — Infrastructure, Layer 1 — API Proxy (`proxy.py`, 1719 lines), Layer 2 — Chat Handlers (`chat_handlers.py`, 710 lines), Layer 3 — Model Router (`router/`) (+9 more)

### Community 470 - "Agent State — colibri GLM-5.2 deployment (resumable)"
Cohesion: 0.11
Nodes (17): Agent State — colibri GLM-5.2 deployment (resumable), Audit verification (2026-07-16, this session), Context / Task, Converged action sequence (after colibri binding is fixed, someday), Done this session (commit `b03a6ba`), Findings (verified empirically), Follow-up fix during commit amend: UTF-8 BOM on setup_autostart.ps1, Option A — Pivot to a feasible MLX model (HIGHEST ROI) (+9 more)

### Community 471 - "Architecture Overview — local-llm-server"
Cohesion: 0.11
Nodes (18): `admin_auth.py` + `admin_gui.py`, `agent/`, Architecture Overview — local-llm-server, `chat_handlers.py`, Deployment, Feature Maturity Tiers, `handlers/anthropic_compat.py`, High-Level Architecture (+10 more)

### Community 472 - "Pending Activities — Implementation Playbook"
Cohesion: 0.11
Nodes (17): Context: what already works (do NOT redo), Definition of done (per task), How to verify the whole thing end-to-end (local, no external infra), P0 — Make autonomy real in production, P1 — Close the remaining product gaps, P2 — ECC harness & polish, Pending Activities — Implementation Playbook, Task 10 — ECC cross-harness adapter (currently PLANNED only) (+9 more)

### Community 473 - "The rules"
Cohesion: 0.11
Nodes (17): Changing these rules, How the gate behaves, Quick-Note Context Rulebook, R10 — Use the repository's real identity **[gate]**, R11 — Name a real integration point **[gate]**, R12 — Mark epistemic status at the claim **[review]**, R1 — Ground the plan in the source before planning anything **[gate]**, R2 — Say what the artifact actually is **[gate]** (+9 more)

### Community 474 - "Part A — Health Report"
Cohesion: 0.11
Nodes (17): F1 — CLAUDE.md documents an architecture that no longer exists, F2 — 15 skills have no frontmatter description, F3 — Direct `os.environ` reads outside config modules, F4 — `print()` in importable production modules, F5 — graphify hook nags every session, F6 — God files, Healthy signals, P1 — Refresh CLAUDE.md and AGENTS.md to match the real architecture (+9 more)

### Community 475 - "apply_review.py"
Cohesion: 0.17
Nodes (10): ApplyReviewAgent, build_review_context(), _gh(), main(), _openai_tools_to_anthropic(), Convert OpenAI function-calling tool schemas to Anthropic tool schemas., Return (result_text, should_stop)., Run using NVIDIA NIM (OpenAI-compatible). Called as fallback. (+2 more)

### Community 476 - "infra_cost.py"
Cohesion: 0.15
Nodes (12): _float_env(), get_infra_config(), InfraConfig, load_infra_config(), project_session_cost(), Local infrastructure cost model for true TCO analysis. This module computes the…, Estimated cost for a typical coding session and daily/monthly projections., Project costs for a typical coding session. Args: avg_session_latency_ms: Total… (+4 more)

### Community 477 - "build_matrix"
Cohesion: 0.20
Nodes (15): build_matrix(), _families(), main(), Any, Map family -> sorted list of test files that mention it (quoted token)., Return one row per family, derived entirely from code., render_markdown(), _test_evidence_index() (+7 more)

### Community 478 - "asyncio"
Cohesion: 0.11
Nodes (9): requires_db, asyncio, Test that storage service can be initialized., Test company CRUD operations - skipped as requires specific config., Test that scanner service can be initialized., Test that specialist service can be initialized., Test that onboarding service can be initialized., End-to-end against the real Mongo (CI service): the exact handler sequence… (+1 more)

### Community 479 - "agency_fix.py"
Cohesion: 0.20
Nodes (17): apply_edits(), build_prompt(), call_llm(), collect_context(), collect_source_files(), decline_cleanly(), extract_failing_tests(), _is_blocked() (+9 more)

### Community 480 - "sync_readme_gallery.py"
Cohesion: 0.22
Nodes (15): main(), _out_dir(), Path, Generate Web UI screenshots for README/docs. Requires: pip install playwright…, build_gallery(), GallerySection, main(), Path (+7 more)

### Community 481 - "CircuitBreakerOpenError"
Cohesion: 0.14
Nodes (11): CircuitBreakerOpenError, Any, Response, RuntimeError, Make an HTTP request through the pool with circuit breaker protection. Args:…, Convenience wrapper: request with automatic retry., Get or create a circuit breaker for a provider., Return circuit breaker statistics. (+3 more)

### Community 482 - "test_skill_executors_live.py"
Cohesion: 0.16
Nodes (17): Live Graphify executor — queries the codebase knowledge graph. Order of…, Live council reviewer — deterministic, rules-based multi-perspective review…, _run_council_review(), _run_graphify(), parametrize, tests/test_skill_executors_live.py — live graphify + council-review executors.…, Broadened secret detection catches SECRET_KEY / GITHUB_TOKEN / etc. The…, test_council_clean_diff_is_approved() (+9 more)

### Community 483 - "TrainingSample"
Cohesion: 0.15
Nodes (9): Any, Add a step result. Returns the sample if accepted, None if filtered out., Bulk-add samples from an agent session's step results. Each step result with…, Return pipeline statistics., A single instruction/response pair for fine-tuning., Convert to Alpaca format: {instruction, input, output}., Convert to ShareGPT format: {conversations: [{from, value}]}., TrainingSample (+1 more)

### Community 484 - "LocalLLMSetup"
Cohesion: 0.16
Nodes (7): LocalLLMSetup, Update .env file with configuration., Check if services are already running., Start the proxy server., Scan for local models., Scan the models folder for available models., Configure which models to use for agent roles.

### Community 485 - "test_company_api.py"
Cohesion: 0.11
Nodes (13): client(), Tests for Company Graph API endpoints., Create a test client for the FastAPI app., Test Company Graph API endpoints., Test that the company API router is included., Test Doctor endpoint., Test the public doctor endpoint., Regression tests for BUG-1: POST /api/company failing with `{"loc": ["body",… (+5 more)

### Community 486 - "TestStopSlopChecker"
Cohesion: 0.11
Nodes (10): Should detect phrases case-insensitively, Should detect throat-clearing phrases, Should return no issues for clean text, Strict mode should detect passive voice, Should detect multiple types of tells in one text, Issues should have helpful suggestions, Should detect business jargon, Should remove throat-clearing phrases (+2 more)

### Community 487 - "handle_workflow_ide_chat"
Cohesion: 0.18
Nodes (17): _extract_last_user_message(), handle_workflow_ide_chat(), _json_response(), Any, JSONResponse, Request, StreamingResponse, workflow/ide_bridge.py — OpenAI-compatible SSE bridge for IDE clients. This… (+9 more)

### Community 488 - "TestHelpers"
Cohesion: 0.15
Nodes (8): _extract_tags(), _first_paragraph(), Path, Return the first non-empty, non-heading line. Skips YAML frontmatter (--- ...…, Pull hashtags and bold words from markdown as tags., Tests for module-level helper functions., Regression: frontmatter (--- ... ---) must not surface as '---'., TestHelpers

### Community 489 - "SKILL: Industrial Brutalism & Tactical Telemetry UI"
Cohesion: 0.12
Nodes (16): 1. Skill Meta, 2.1 Swiss Industrial Print, 2.2 Tactical Telemetry & CRT Terminal, 2. Visual Archetypes, 3.1 Macro-Typography (Structural Headers), 3.2 Micro-Typography (Data & Telemetry), 3.3 Textural Contrast (Artistic Disruption), 3. Typographic Architecture (+8 more)

### Community 490 - "Skill: data-quality-audit"
Cohesion: 0.12
Nodes (16): 1. Token Length Distribution, 2. Deduplication Check, 3. Tokenizer Fertility Check, 4. Special Token Consistency, 5. Language Detection (if langdetect available), 6. Content Quality Signals, Background (Why This Matters), Checks Performed (+8 more)

### Community 491 - "What "Slop" Looks Like"
Cohesion: 0.12
Nodes (16): Acceptance Checks, Category 1 — Obvious Comments, Category 2 — Phantom Abstractions, Category 3 — Defensive Checks for Impossible Cases, Category 4 — Speculative Generality, Category 5 — Verbose Variable Names, Category 6 — Unasked-For Boilerplate, Instructions (+8 more)

### Community 492 - "test_admin_local_brain_router.py"
Cohesion: 0.18
Nodes (16): build_admin_local_brain_router(), Any, APIRouter, Construct a ready-to-mount APIRouter with the auth dependency baked in. The…, _require_admin(), _make_app(), FastAPI, tests/test_admin_local_brain_router.py — auth + toggle flow for… (+8 more)

### Community 493 - "local_brain_router.py"
Cohesion: 0.19
Nodes (16): get_local_brain_state(), HeartbeatBody, post_local_brain_heartbeat(), post_local_brain_toggle(), Any, BaseModel, get, post (+8 more)

### Community 494 - "cost_tracker.py"
Cohesion: 0.13
Nodes (16): cost_table(), Return the active per-model cost table (USD per million tokens). Useful for…, _build_cost_table(), cost_for_tokens(), get_cost_table(), get_stats(), _load_env_overrides(), Any (+8 more)

### Community 495 - "Section-by-Section Acceptance Criteria"
Cohesion: 0.12
Nodes (16): 467 Final Acceptance Criteria, §A — Company Graph + Onboarding, §B — 34 Specialist Families, §C — ECC, Obsidian, Graphify, Council Review Wiring, §D — Direct Chat as Control Center, Definition of Done, §E — Workflow Engine as Canonical Backbone + Worktree Isolation, §F — Doctor Full Check List (+8 more)

### Community 496 - "Migration Notes"
Cohesion: 0.12
Nodes (16): Compose secret scoping — shipped, opt-in, Container hardening overlay, Known limitations at merge, Migration Notes, Optional hardening (operator decisions), Path to enforcement, Protect the policy file from agents, Rollback (+8 more)

### Community 497 - "McpCard.jsx"
Cohesion: 0.14
Nodes (9): getRenderHealth(), getRenderOpsStatus(), runRenderOpsScan(), api, BTN, McpCard(), NOTE(), relTime() (+1 more)

### Community 498 - "provider_max_rpm"
Cohesion: 0.17
Nodes (15): provider_max_rpm(), _provider_positive_float(), provider_weight(), Shared parse/validate for the numeric per-provider traffic budgets. Returns…, Return the operator-configured requests/min cap for *provider*, or None if…, Return the operator-configured share weight for *provider*. Reads…, Selection weight for *provider_id* (see ``_weighted_shuffle``)., tests/test_provider_max_rpm.py — packages/ai/brain_config.provider_max_rpm().… (+7 more)

### Community 499 - "redact_connection_url"
Cohesion: 0.17
Nodes (7): packages/security/redact.py — strip secrets out of strings before they reach a…, Strip embedded credentials from a connection URI before logging it. Covers both…, redact_connection_url(), Regression test: production leaked a live MongoDB password in plaintext.…, Integration coverage: the actual log lines this module emits must never carry…, TestLoggingCallSitesRedactCredentials, TestRedactConnectionUrl

### Community 500 - "SQLiteStore"
Cohesion: 0.15
Nodes (9): Connection, Top-level store — exposes collections as attributes. Usage:: store =…, Lazily build the pool of read-only connections (idempotent)., Yield a read connection from the pool (falls back to the writer). On in-memory…, Create tables if they don't already exist., SQLiteStore, B608 guard: _Collection.__init__ must reject names outside _COLLECTIONS.…, store() (+1 more)

### Community 501 - "agent_readiness_audit.py"
Cohesion: 0.21
Nodes (15): _grade(), main(), PillarResult, scripts/agent_readiness_audit.py — score this repo's fitness for autonomous…, ReadinessReport, run_audit(), score_build_system(), score_dev_environment() (+7 more)

### Community 502 - "test_ci.sh"
Cohesion: 0.15
Nodes (16): ADMIN_EMAIL, ADMIN_PASSWORD, API_KEYS, cleanup(), DB_NAME, fail(), LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY (+8 more)

### Community 503 - "claim"
Cohesion: 0.18
Nodes (7): claim(), Try to acquire a named lock. Returns True if acquired, False if already held., Release a previously acquired lock., release(), TestInMemoryClaim, TestInMemoryKeyIsolation, TestRedisClaim

### Community 504 - "test_shared_state.py"
Cohesion: 0.17
Nodes (11): incr_window(), Reset the singleton (for tests)., Increment a rate-limit counter. Returns the current count within the window., _reset_backend(), Tests for the shared-state abstraction (in-memory and Redis/fakeredis backends)., Configure the shared_state module to use fakeredis for the test., Reset the shared-state singleton before every test., _redis_backend() (+3 more)

### Community 505 - "._coerce_ts"
Cohesion: 0.18
Nodes (8): _coerce_ts(), ExecutionLogEntry, Any, field_validator, Update the updated_at timestamp., Coerce ISO-8601 datetime strings (from DB) to float timestamps., Single entry in a task's execution log., Dict-compatible accessor. Log entries are serialized to/from dicts in many…

### Community 506 - "test_activation_api.py"
Cohesion: 0.21
Nodes (16): _client(), TestClient, Tests for activation_api — instance status, OpenAPI schema, and role route.…, GET /api/activation/settings is PUBLIC — non-admin users need to read the…, test_change_role_rejects_invalid_role(), test_change_role_requires_authentication(), test_change_role_returns_404_for_missing_user(), test_change_role_updates_existing_user() (+8 more)

### Community 507 - "test_daily_automation_2026_07_11.py"
Cohesion: 0.15
Nodes (16): Path, Tests for daily automation 2026-07-11: sub-agent delegation depth guard.…, The depth guard must return a dict, never raise an exception., Default depth cap matches Claude Code's 5-level limit., MAX_SUBAGENT_DEPTH must be a positive integer (safety assertion)., When _depth == MAX_SUBAGENT_DEPTH, _spawn_subagent must return an error., At depth MAX_SUBAGENT_DEPTH - 1 the spawn must be attempted (not blocked)., Child AgentRunner._depth must be parent._depth + 1. (+8 more)

### Community 508 - "test_health_endpoints.py"
Cohesion: 0.17
Nodes (16): _make_fake_client(), Exception, Tests for /health, /live, and /api/health endpoints., When Ollama is down, /api/health should also return a degraded status., Return a context-manager-compatible mock for httpx.AsyncClient., Container liveness probe must always return 200., Health endpoint exists and returns a JSON body., Health endpoint includes provider states when ProviderRouter is wired in. (+8 more)

### Community 509 - "test_keepalive.py"
Cohesion: 0.18
Nodes (16): Path, Smoke test for scripts/keepalive.py (Windows-friendly Render + Ollama keepalive…, `--diagnose` mode exits 1 when hosts are unreachable (per docstring: exit 0/1)., Reload scripts.keepalive with KEEPALIVE_LOG = log_path and clear cache., KEEPALIVE_LOG under tmp_path; log_path() ensures parent directory exists., _rotate_log_if_needed() is a no-op when file is under MAX_LOG_BYTES; truncates…, _log() writes '[YYYY-MM-DD HH:MM:SS] <line>' to KEEPALIVE_LOG., When Render + Ollama are both unreachable, run_once() returns 1. (+8 more)

### Community 510 - "test_openclaw_endpoints.py"
Cohesion: 0.12
Nodes (10): client(), tests/test_openclaw_endpoints.py — OpenClaw HTTP + WebSocket endpoint tests., After pairing, ping command returns pong., Unknown command returns error., WebSocket with wrong token is rejected (connection closed)., WebSocket with correct token pairs successfully., test_websocket_pairing_accepts_correct_token(), test_websocket_pairing_rejects_wrong_token() (+2 more)

### Community 511 - "TestRoutes"
Cohesion: 0.19
Nodes (7): _install_service(), Tests for agents/portfolio_api.py — the v5 portfolio board API. Loads the…, A materializer exception must not break /refresh (the board still returns), and…, Install a PortfolioService whose portfolio is fixed (no rebuild)., _seeded_manager(), TestBoardPayload, TestRoutes

### Community 512 - "hermes_prompt.py"
Cohesion: 0.19
Nodes (15): build_chatml_system_prompt(), format_chatml_message(), format_tool_call(), format_tool_response(), messages_to_chatml(), model_supports_chatml(), parse_tool_call_from_chatml(), Any (+7 more)

### Community 513 - "MemoryMiddleware"
Cohesion: 0.17
Nodes (10): create_memory_middleware(), MemoryMiddleware, Any, Process incoming chat request and inject memories., Extract and save learnings from model responses., Factory function to create memory middleware instance., Middleware for automatic memory loading and injection., Detect AI coding tool from request headers. (+2 more)

### Community 514 - "._fetch_flat_skill_file"
Cohesion: 0.18
Nodes (8): _fmt_name(), AsyncClient, Fetch skills from all configured GitHub registries. Returns count added., Force-refresh remote skills, bypassing TTL. Returns count added., Fetch one GitHub registry and return a list of RegistrySkill objects. Handles…, Fetch a registry whose skills live in arbitrarily nested directories. Uses the…, Fetch one nested SKILL.md via raw.githubusercontent.com., Fetch a flat .md file and convert it to a RegistrySkill.

### Community 515 - "AITellIssue"
Cohesion: 0.17
Nodes (8): AITellIssue, Find all AI tells in text, Find throat-clearing phrases, Find emphasis crutches (weak adverbs), Find meta-commentary (text referring to itself), Find Wh-sentence starters (weak prose starters), Find basic passive voice patterns (strict mode only), Format issues as human-readable report

### Community 516 - "Skill: repowise-intelligence"
Cohesion: 0.12
Nodes (15): 1. Graph Intelligence (Dependency Graph), 2. Git Intelligence, 3. Documentation Intelligence, 4. Decision Intelligence, Acceptance Checks, Directory Structure, Example Usage, Implementation Approach (+7 more)

### Community 517 - "ARCHITECTURE.md — Target Architecture"
Cohesion: 0.12
Nodes (15): 1. Target Repository Structure, 2. Dependency Rules, 3. Provider Architecture (Target), 4. Configuration Architecture (Target), 5. Event Bus Architecture (Target), 6. Scheduler Architecture (Target), 7. Dashboard Architecture (Target), 8. Migration Principles (+7 more)

### Community 518 - "Skill: repowise-intelligence"
Cohesion: 0.12
Nodes (15): 1. Graph Intelligence (Dependency Graph), 2. Git Intelligence, 3. Documentation Intelligence, 4. Decision Intelligence, Acceptance Checks, Directory Structure, Example Usage, Implementation Approach (+7 more)

### Community 519 - "The 10-Step Workflow"
Cohesion: 0.12
Nodes (15): Cross-Tool Compatibility, Quick Reference Card, Skill: session-planning — Mandatory Planning Workflow for All AI Agents, Step 10 — Close Out, Step 1 — Orient (free), Step 2 — Understand the Task, Step 3 — Load Relevant Skills, Step 4 — Research (if novel task) (+7 more)

### Community 520 - "Contributing to local-llm-server"
Cohesion: 0.12
Nodes (16): Architecture, Bug Reports, Changelog, Coding Standards, Commit Message Convention, Contributing to local-llm-server, Development Setup, Feature Requests (+8 more)

### Community 521 - "CEO Micro-Management"
Cohesion: 0.12
Nodes (16): A failed drive does not abandon the goal, CEO Micro-Management, Configuration reference, Escalation, and why it terminates, Five bounds, Operator surface, Tests, The 24x7 supervisor (+8 more)

### Community 522 - "467 Brutal Audit — File-by-File Status"
Cohesion: 0.12
Nodes (15): 467 Brutal Audit — File-by-File Status, Agent System, Backend & Services, Core Proxy & Routing, Direct Chat, Feature Matrix (spec §I — demotions needed), Frontend / Public Site (spec §H — 0% delivered), GitHub Workflows (+7 more)

### Community 523 - "Runbook — Apply the Fast Free NVIDIA Brain to Render (TASK 2)"
Cohesion: 0.12
Nodes (15): B.1 — Open the service's Environment tab, B.2 — Set these five keys on each service, B.3 — Sanity-check the secrets that must NOT regress, B.4 — Trigger TASK 5 keep-alive immediately, Option A — Blueprint sync (preferred), Option B — manual per-service editor, Rollback, Runbook — Apply the Fast Free NVIDIA Brain to Render (TASK 2) (+7 more)

### Community 524 - "implement_agent.py"
Cohesion: 0.16
Nodes (12): main(), _openai_tools_to_anthropic(), Safely insert an entry under ## [Unreleased] without touching the rest of the…, Convert OpenAI function-calling tool schemas to Anthropic tool schemas., Run the implementation agent loop using Claude Opus via Anthropic SDK. Returns…, _read_claude_md(), _run_anthropic_agent_loop(), _run_baseline_pytest() (+4 more)

### Community 525 - "test_agent_chat_integration.py"
Cohesion: 0.23
Nodes (14): LogCaptureFixture, _fake_auth(), _make_nim_providers(), AuthContext, MonkeyPatch, Path, Integration tests for /agent/chat endpoint and AGENT_RUNNER configuration.…, test_agent_chat_passes_session_store_to_runner() (+6 more)

### Community 526 - "PersistentQueue"
Cohesion: 0.19
Nodes (6): PersistedRequest, PersistentQueue, Any, One queued request durable across a restart., Durable pending-work store backed by Redis, with a memory fallback.…, Everything accepted but not completed — the restart replay set. Both stores are…

### Community 527 - "fabric_cli.py"
Cohesion: 0.29
Nodes (15): cmd_apply(), cmd_list(), cmd_new(), cmd_save(), cmd_show(), cmd_stitch(), _ensure_patterns_dir(), main() (+7 more)

### Community 528 - "sync_ngrok.py"
Cohesion: 0.26
Nodes (14): detect_ngrok_url(), dim(), fail(), header(), info(), main(), ok(), patch_platform_brain_via_switch_brain() (+6 more)

### Community 529 - "reap_expired_companies"
Cohesion: 0.21
Nodes (15): _as_aware_utc(), datetime, Treat naive datetimes as UTC so comparisons never raise., Delete all expired ephemeral companies. Returns the number deleted. A company…, reap_expired_companies(), _company(), asyncio, Tests for services.ephemeral_reaper — destroy expired ephemeral companies. Runs… (+7 more)

### Community 530 - "test_p0_roadmap_b3_b4_b5.py"
Cohesion: 0.16
Nodes (9): _deep_merge(), Deep merge two dicts. Override values take precedence., get_nim_pool(), Enum, Return the module-level NIMConnectionPool singleton., get_synthetic_pipeline(), Return the module-level SyntheticDataPipeline singleton., asyncio (+1 more)

### Community 531 - "GuardResult"
Cohesion: 0.16
Nodes (8): GuardResult, Any, Check user input against input safety rules. Returns a GuardResult with…, Check model output against output safety rules. Returns a GuardResult with…, Unified check method. direction = 'input' or 'output'., Return guardrail statistics., Result of a guardrail check., TestGuardResult

### Community 532 - "ManagedAgentDreams"
Cohesion: 0.22
Nodes (4): ManagedAgentDreams, Manages recording session memories and consolidating them into dreams., Tests for ManagedAgentDreams., TestManagedAgentDreams

### Community 533 - "shared_state.py"
Cohesion: 0.20
Nodes (10): cooldown_clear(), cooldown_get(), cooldown_set(), _get_backend(), Shared-state abstraction — in-memory (default) and Redis backends. Provides…, Put a key on cooldown for *ttl* seconds., Return True if *key* is still within its cooldown window., Clear all cooldown entries (for test teardown). (+2 more)

### Community 534 - "_resolve_push_token"
Cohesion: 0.17
Nodes (13): _get_ceo_dispatcher(), Execute the plan via the selected specialist(s)., Verify execution results., Return the shared CEODispatcher singleton (importable for monkeypatching)., GitHub token used to push branches / open PRs during EXECUTION (#506).…, _resolve_push_token(), _clean_env(), tests/test_orchestrator_push_token.py — #506 push/PR token resolution.… (+5 more)

### Community 535 - "test_autonomy_status.py"
Cohesion: 0.12
Nodes (15): client(), TestClient, tests/test_autonomy_status.py — public /api/autonomy/status readiness probe.…, No auth required; response carries the readiness contract keys., The probe carries the loop fleet readiness summary (loop-audit)., Without NVIDIA key AND without Ollama, the probe must report no_brain., When NVIDIA is absent but Ollama is configured, report brain as ollama., With an NVIDIA key the brain resolves and the secret is no longer flagged. (+7 more)

### Community 536 - "test_brain_failover_413.py"
Cohesion: 0.13
Nodes (8): _clean_env(), _FakeAsyncClient, _FakeResponse, Regression test: HTTP 413 (Payload Too Large) must fail over to the next…, Returns 413 for every call to a Groq URL, success for anything else., Groq (will 413) + Cerebras (will succeed) both configured, NVIDIA deliberately…, test_413_fails_over_to_next_provider_after_one_attempt(), _two_provider_env()

### Community 537 - "test_dockerfile_ships_root_modules.py"
Cohesion: 0.17
Nodes (13): _dockerfile_text(), Regression guard: the backend image must ship every root-level Python module…, An env var set to empty string means unset, not a commit named ''., Unknown must read as unknown — a deploy check treats None as 'unverifiable' and…, True when the Dockerfile copies root .py modules wholesale (`COPY *.py ...`)., The worker's `python worker_main.py` start command needs worker_main.py., V2.0 Modernization: the image must ship `packages/` (provider_router,…, _ships_all_root_modules() (+5 more)

### Community 538 - "test_frontend_deployment_guards.py"
Cohesion: 0.20
Nodes (15): Step 3 runtime config must render checkboxes for each runtime., index.css must override appearance:none for checkboxes/radios., The checkbox appearance override must NOT set appearance:none (that would keep…, The checkbox appearance override must use 'auto' to request native rendering.…, SetupWizardPage must render <input type='checkbox'> for each provider toggle., _read(), test_api_redirects_respect_public_and_backend_paths(), test_index_css_checkbox_override_is_not_none() (+7 more)

### Community 539 - "test_glm52_brain.py"
Cohesion: 0.12
Nodes (15): tests/test_glm52_brain.py — PR #984 Verifies GLM-5.2 (z-ai/glm-5.2) is…, packages/ai/registry.py must register z-ai/glm-5.2., GLM-5.2 must have a lower priority number (higher precedence) than…, packages/ai/brain.py DEFAULT_FREE_NVIDIA_MODEL must be z-ai/glm-5.2., packages/ai/brain_config.py SAFE_DEFAULT_MODEL must be z-ai/glm-5.2., PROVIDER_PRESETS['nvidia'] must use z-ai/glm-5.2 for all roles., render.yaml must set NVIDIA_DEFAULT_MODEL + AGENT_*_MODEL to z-ai/glm-5.2., backend/server.py must have the brain migration startup task. (+7 more)

### Community 540 - "test_langfuse_agency_wide.py"
Cohesion: 0.12
Nodes (15): tests/test_langfuse_agency_wide.py — tests for PR #961 agency-wide Langfuse.…, langfuse_obs.py must define emit_agency_observation., emit_agency_observation must be a no-op when Langfuse is not configured., tasks/service.py must call emit_agency_observation for task execution., agent/agency.py must call emit_agency_observation for CEO directives., backend/server.py scheduler_tick must call emit_agency_observation., packages/ai/self_heal.py must call emit_agency_observation., emit_agency_observation must accept all documented parameters. (+7 more)

### Community 541 - "test_local_brain_state.py"
Cohesion: 0.12
Nodes (10): tests/test_local_brain_state.py — regression test for the cross-machine toggle.…, Operator flips OFF — any prior lease must be dropped so a future ON doesn't…, The store must not corrupt the model listing when reading back., The 3 endpoints MUST refuse calls without SERVICE_TOKEN — confirmed by mounting…, All three endpoints must be present on the router (regression guard against…, store(), test_router_3_endpoints_are_registered(), test_router_endpoints_require_service_token() (+2 more)

### Community 544 - "test_phase5_doctor.py"
Cohesion: 0.12
Nodes (10): client(), tests/test_phase5_doctor.py Phase 5: /api/doctor endpoint tests. Coverage: -…, If RuntimeManager raises, /api/doctor still returns 200 with a warn check., If DirectChatDoctor.check_all raises, /api/doctor still returns 200., MongoStore.__getattr__ proxies any name to a Motor collection, so…, Langfuse check is always emitted (pass or warn based on env)., test_doctor_langfuse_check_present(), test_doctor_survives_preflight_error() (+2 more)

### Community 545 - "test_telegram_diag_endpoint.py"
Cohesion: 0.12
Nodes (15): client(), tests/test_telegram_diag_endpoint.py — /api/telegram/diag HTTP endpoint.…, Build a TestClient against the FastAPI app with controlled env., The /api/telegram/diag endpoint returns 200., The endpoint returns the expected config fields., The endpoint must NOT return the full bot token — only a masked prefix., The endpoint includes diagnostic hints for common failure modes., The endpoint does not require authentication (it's a diagnostic tool). (+7 more)

### Community 546 - "TestCheckKwargs"
Cohesion: 0.18
Nodes (8): check_kwargs(), Any, agent/contract_enforcement.py — Runtime signature locking (J) Provides…, # NOTE: limit has a default so it is accepted; owner_id is keyword-only., Raise TypeError on unknown kwarg (runtime extra='forbid'). Args: kwargs: The…, # NOTE: limit is NOT locked — it is a legitimate optional param that does not, Unit tests for the check_kwargs helper., TestCheckKwargs

### Community 547 - "audit_drift"
Cohesion: 0.18
Nodes (15): audit_drift(), load_registry(), load_registry_sync(), Path, Load and validate the registry from YAML (synchronous; for CLI/tests)., Async loader — file read runs off the event loop (async-I/O rule)., Return repo-relative paths of workflows that run on a cron schedule., Detect catalogue rot. * **missing_from_registry** — every cron-scheduled… (+7 more)

### Community 548 - ".build"
Cohesion: 0.18
Nodes (11): MemoryTurn, Rough token estimate: 4 chars ≈ 1 token (minimum 1)., Run the full RAG pipeline and return a token-budget-respecting context.…, One turn in the conversation history., Select up to *top_k* highest-scoring turns that fit within *budget*. Returns…, A document selected by retrieval, with its compressed excerpt., RetrievedDoc, _token_count() (+3 more)

### Community 549 - "Skill: agent-harness"
Cohesion: 0.13
Nodes (14): Architecture, Combining with Other Skills, Key Concepts, Output Format, Purpose, Safety Rules, Skill: agent-harness, Step 1 — Define the task clearly (+6 more)

### Community 550 - "Skill: checkpoint-strategy"
Cohesion: 0.13
Nodes (14): After a Loss Spike, Aggressive (Long Runs with Stable Training), Background, Checkpoint Policy Templates, Conservative (Recommended for First Runs), Integration Points, Output Format, Purpose (+6 more)

### Community 551 - "Process"
Cohesion: 0.13
Nodes (14): Anti-Patterns, Process, Purpose, Rules, Skill: debug-tracer, Step 1: Reproduce First, Step 2: Gather Evidence, Step 3: Form Hypotheses (+6 more)

### Community 552 - "Skill: local-ai-query"
Cohesion: 0.13
Nodes (14): 1. Verify Ollama is available, 2. Choose appropriate model, 3. Send query to local model, 4. Generate embeddings (for RAG), 5. List running models, Integration with ChromaDB (RAG), Limitations, Prerequisites (+6 more)

### Community 553 - "Skill: parallel-agents"
Cohesion: 0.13
Nodes (14): Combining with Other Skills, Core Concepts (from the Modal/OpenAI Agents SDK pattern), Example — parallel approach exploration, Example — parallel research, Output Format, Phase 1 — Decompose, Phase 2 — Dispatch (simulate parallelism), Phase 3 — Aggregate (+6 more)

### Community 554 - "Skill: parallel-worktrees"
Cohesion: 0.13
Nodes (14): Acceptance Checks, Common Patterns, Concept, Constraints, Instructions, Pattern A — Test main while you implement, Pattern B — Review reference during refactor, Pattern C — Hotfix without disturbing feature work (+6 more)

### Community 555 - "Design System: Taste Standard"
Cohesion: 0.13
Nodes (14): 1. Visual Theme & Atmosphere, 2. Color Palette & Roles, 3. Typography Rules, 4. Component Stylings, 5. Hero Section, 6. Layout Principles, 7. Responsive Rules, 8. Motion & Interaction (Code-Phase Intent) (+6 more)

### Community 556 - "Process"
Cohesion: 0.13
Nodes (14): Integration with Other Skills, Process, Purpose, Rules, Skill: ticket-to-pr, Step 1: Parse the Issue, Step 2: Context Prime, Step 3: Plan the Implementation (+6 more)

### Community 557 - ".get_state"
Cohesion: 0.22
Nodes (9): _now_iso(), Any, Connection, Return the desired + last-reported state for the admin UI., Operator flips the toggle. Persists + clears any prior lease. Returns the new…, Local daemon POSTs its heartbeat. If the operator's desired_state=on AND the…, `now_iso`: ISO-8601 string marking the reader's "now" — pass it in to stay…, Reviewer fix #f: lease must strip after heartbeats stop arriving. Simulates a… (+1 more)

### Community 558 - "Skill: user-research"
Cohesion: 0.13
Nodes (14): Architecture, As a Python library, As an agent tool, Auto-Registration, Files, Purpose, Pydantic Models (extra="forbid"), Sample-Size Math (+6 more)

### Community 559 - "Agency Core — Progress & Resume Log"
Cohesion: 0.13
Nodes (14): Agency Core — Progress & Resume Log, Audit (committed), Environment constraints discovered this session, How to resume (read before doing anything), Key findings (so we don't re-investigate), Open risks / must-know before merging, Phase 0 — Stabilize & quarantine (commit `713184a`, pushed), Planned CI-parity hardening (the immediate next commit) (+6 more)

### Community 560 - "test_daily_2026_07_24.py"
Cohesion: 0.20
Nodes (7): is_strict(), Any, Structured output normalization across LLM providers. Translates the OpenAI…, Return True when the caller has requested strict schema enforcement. Strict…, Daily automation tests — 2026-07-24. Covers three features added in this…, is_strict() detects strict: true inside json_schema., TestIsStrict

### Community 561 - "_push_down_where"
Cohesion: 0.14
Nodes (14): _fully_pushable(), _is_pushable_scalar(), _push_down_where(), Any, Scalar values whose `str()` form matches how they were stored in the indexed…, Build a SQL ``WHERE`` suffix from the subset of *query* conditions that map…, True if EVERY condition in *query* is expressible in the SQL WHERE. Unlike…, Try to satisfy a sorted/paginated find entirely in SQL. Returns the decoded… (+6 more)

### Community 562 - "router/health.py"
Cohesion: 0.20
Nodes (14): _enabled(), get_available_models(), invalidate_cache(), is_model_available(), Ollama model availability check with TTL cache. Keeps a short-lived cache of…, Force the next call to re-probe Ollama (useful in tests)., Return True if *model* is in the Ollama tag list (or health checks off).…, Return the set of model names currently present in Ollama. Returns an empty set… (+6 more)

### Community 563 - "test_telegram_auto_approve.py"
Cohesion: 0.23
Nodes (14): is_sensitive(), True when *text* references a sensitive target (auth/keys/secrets/service…, _build_execution_request(), Build a minimal ``ExecutionRequest`` for plain-text → orchestrator.execute.…, admin_user(), _auto_approve(), non_admin_user(), Auto-approve policy for Telegram plain-text → orchestrator routing. Routine… (+6 more)

### Community 564 - "clear_wizard_state_cache"
Cohesion: 0.21
Nodes (10): clear_wizard_state_cache(), Override the persistence collection used for wizard state. Tests and hosted…, Clear the in-memory wizard-state cache., set_wizard_state_collection(), _FakeWizardCollection, SimpleNamespace, TestClient, _setup_client() (+2 more)

### Community 565 - "e2e/test_browser.py"
Cohesion: 0.23
Nodes (14): base_url(), do_login(), fail(), ok(), Page, Navigate to a page and verify it loads without errors., Verify server responds to health check before running browser tests., Run full browser e2e suite. (+6 more)

### Community 566 - "._sprint"
Cohesion: 0.19
Nodes (3): Tests for agents/agile_ceremonies.py — autonomous agile ceremonies. Loads…, TestGenerateBacklogRetro, TestGenerateSprintRetro

### Community 567 - "TestGetCurrentTimeTool"
Cohesion: 0.16
Nodes (8): proxy_client(), Path, Daily automation tests — 2026-07-09. Covers: 1. Agent time-awareness:…, Minimal proxy test client with a seeded API key via env var., Integration smoke test for POST /agent/budget/reset., Unit tests for the get_current_time dispatch path in AgentRunner., TestBudgetResetEndpoint, TestGetCurrentTimeTool

### Community 569 - "test_dockerfile_ships_config_dir.py"
Cohesion: 0.14
Nodes (14): _dockerfile_text(), Regression guard: the backend image must ship ``config/``. `config/llm/*.yaml`…, The two properties that made the ungated entry expensive in production., The ceiling that #1172 added must survive in the file that ships. Sized against…, Without this COPY the router silently runs on defaults in production., A shipped directory is worthless if the files moved out of it., A .dockerignore entry would defeat the COPY without touching it., A keyless local provider must not join the chain just by existing. ``ollama``… (+6 more)

### Community 570 - "_run"
Cohesion: 0.42
Nodes (14): _make_env(), CompletedProcess, Path, _run(), test_crlf_preserved_on_untouched_lines(), test_dry_run_does_not_mutate(), test_env_path_missing_file_exits_1(), test_force_rewrites_canonical_already_present() (+6 more)

### Community 571 - "test_scanner_live.py"
Cohesion: 0.23
Nodes (14): _assert_scan_contract(), asyncio, parametrize, LIVE integration tests for the website scanner — these actually hit the real…, Representative large storefronts that commonly sit behind bot protection. Same…, Directly exercise the BuiltWith fallback against the live builtwith.com.…, The invariants that must hold for any live scan, bot-protected or not., A normal, non-bot-protected site must yield real detections. This is the… (+6 more)

### Community 572 - "_TFIDFIndex"
Cohesion: 0.16
Nodes (11): Lightweight TF-IDF index over a fixed document collection. Sparse dict vectors…, Return ``(doc_index, cosine_score)`` pairs for the top-*k* matches., Return lowercase alphanumeric tokens with stop-words removed. Numeric tokens…, _TFIDFIndex, _tokenize(), test_tfidf_empty_corpus(), test_tfidf_empty_query(), test_tfidf_finds_relevant() (+3 more)

### Community 573 - "._resolve_path"
Cohesion: 0.18
Nodes (4): Path, Return the first *lines* lines of a file. Just-in-time retrieval: the executor…, Return a lightweight index of files with line counts and sizes. This is the…, Resolve filepath relative to workspace_root, rejecting traversal attempts. Uses…

### Community 574 - "StopSlopChecker"
Cohesion: 0.14
Nodes (8): Initialize checker. Args: strict: If True, also report adverbs even if not in…, Remove most obvious AI tells from text, Detect and optionally remove AI tells from text, StopSlopChecker, Should format report correctly, Should report success on clean text, Should detect weak emphasis adverbs, Should detect meta-commentary

### Community 575 - "Process"
Cohesion: 0.14
Nodes (13): 1. Read and Understand the Issue, 2. Explore the Codebase, 3. Plan the Solution, 4. Implement, 5. Test, 6. Document, 7. Commit and Push, Notes (+5 more)

### Community 576 - "Skill: lr-schedule-advisor"
Cohesion: 0.14
Nodes (13): Background (Why This Matters), Common Mistakes, Cosine with Warmup (Recommended for Pretraining), Fine-tuning vs Pretraining, Integration Points, Output Format, Peak LR Heuristics by Model Size, Purpose (+5 more)

### Community 577 - "Instructions"
Cohesion: 0.14
Nodes (13): 1 — Tests green, 2 — Changelog updated, 3 — Determine the version bump, 4 — Update changelog, 5 — Commit the changelog update, 6 — Tag the release, 7 — Verify CI on the tag, 8 — Post-release (+5 more)

### Community 578 - "Instructions"
Cohesion: 0.14
Nodes (13): Acceptance Checks, `admin_auth.py` checklist, `agent/tools.py` checklist, Escalation, Instructions, `key_store.py` checklist, `proxy.py` auth middleware checklist, Risky Modules in This Repo (+5 more)

### Community 579 - "Process"
Cohesion: 0.14
Nodes (13): 1. Decompose the Task, 2. Sequence the Skills, 3. Execute in Order, 4. Handle Failures, 5. Synthesize Output, 6. Document the Composition, Example Compositions, Notes (+5 more)

### Community 580 - "Checks Performed"
Cohesion: 0.14
Nodes (13): 1. Round-trip Consistency, 2. Numeric Tokenization, 3. Whitespace Handling, 4. Special Character Coverage, 5. Fertility by Domain, 6. Vocabulary Overlap Check (for model updates), Background, Checks Performed (+5 more)

### Community 581 - "Skill: training-stability-monitor"
Cohesion: 0.14
Nodes (13): Example Checks Performed, Gradient Norm Check, Integration Points, Key Lessons (from LLM-from-scratch practitioners), Loss Spike Detection, LR Warmup Validation, Notes, Output Format (+5 more)

### Community 582 - "monitor_colibri.py"
Cohesion: 0.24
Nodes (13): ArgumentParser, build_parser(), cmd_autostart_install(), cmd_status(), cmd_supervise(), _configure_logging(), main(), Namespace (+5 more)

### Community 583 - "admin_digest_router.py"
Cohesion: 0.22
Nodes (13): _build_payload_or_500(), _check_secret(), _expected_secret(), preview_digest_endpoint(), Any, get, post, Dry-run: same auth, returns the would-be markdown body but does NOT dispatch to… (+5 more)

### Community 584 - "Skill: branch-cleanup"
Cohesion: 0.14
Nodes (13): Acceptance Checks, Automation — post-merge hook (optional), Option A — git push (standard), Option B — GitHub API (use when `git push --delete` returns 403), Option C — Delete local tracking refs after remote deletion, Skill: branch-cleanup, Step 1 — Confirm master is up to date, Step 2 — List all remote branches (+5 more)

### Community 585 - "Skill: perplexity — Web Research via Perplexity API"
Cohesion: 0.14
Nodes (13): Applying to this Repo, How to Query, No API Key? Use WebSearch, Prerequisites, Quick query (one-shot Python call), Run inline, Skill: perplexity — Web Research via Perplexity API, Skill Steps (+5 more)

### Community 586 - "Instructions"
Cohesion: 0.14
Nodes (13): 1 — Tests green, 2 — Changelog updated, 3 — Determine the version bump, 4 — Update changelog, 5 — Commit the changelog update, 6 — Tag the release, 7 — Verify CI on the tag, 8 — Post-release (+5 more)

### Community 587 - "Instructions"
Cohesion: 0.14
Nodes (13): Acceptance Checks, `admin_auth.py` checklist, `agent/tools.py` checklist, Escalation, Instructions, `key_store.py` checklist, `proxy.py` auth middleware checklist, Risky Modules in This Repo (+5 more)

### Community 588 - "Quick-Note Issues Processing Summary"
Cohesion: 0.14
Nodes (13): 🔗 Branch References, ✅ Completed, Future Session, Immediate (Session-Aware), Issue #229 — Stop-Slop AI Quality Checker, Issue #263 — Graphiti Temporal Context, Issue #266 — ECC Multi-Harness Adapter, 💡 Key Learnings (+5 more)

### Community 589 - "Implementation Plan — DB-persisted, UI-switchable Brain (no redeploy)"
Cohesion: 0.14
Nodes (13): 0. Why this exists (root cause this fixes), 1. Hard constraints (from the owner), 2. Provider strategy (the recommendation), 3. Architecture, 3a. Store — `services/brain_config_store.py` (new), 3b. Call-time resolution — `agent/loop.py`, 3c. Admin API — `backend/server.py`, 3d. UI — `webui/frontend/src/pages` (+ `webui/router.py` / `providers.py`) (+5 more)

### Community 590 - "Backend changes"
Cohesion: 0.14
Nodes (13): `activation_api.py`, `app_settings.py` (new), Backend changes, `backend/company_api.py`, `db/sqlite_store.py`, Docs / changelog, Frontend changes, Goal (+5 more)

### Community 591 - "Render MCP — autonomous platform debugging and environment monitoring"
Cohesion: 0.14
Nodes (13): 1. Coding sessions — stdio, via `.mcp.json`, 2. The running agency — Streamable HTTP against a deployed sidecar, Configuration, Enabling it, HTTP API, If the private address does not resolve, Playwright, Render MCP — autonomous platform debugging and environment monitoring (+5 more)

### Community 592 - "Runbook: Auto-Resume After Cooldown / Interruption"
Cohesion: 0.14
Nodes (13): Commands, Cooldown Detection, Cooldown Detection Logic, Force-Resume After Stale Lock, Forcing an Abort, How It Works, Inspecting a Stuck Run, Overview (+5 more)

### Community 593 - "SEO / GEO / AIO Audit Engine"
Cohesion: 0.14
Nodes (14): API, Architecture, Delegation plan → agent tasks, Demo from the UI, Exports — the full heavy report, Fetching bot-protected sites (`fetch_mode`), Provenance, Repo-aware auto-fixing (+6 more)

### Community 594 - "devDependencies"
Cohesion: 0.14
Nodes (14): react-scripts, devDependencies, jsdom, react-scripts, @testing-library/dom, @testing-library/jest-dom, @testing-library/react, @testing-library/user-event (+6 more)

### Community 595 - "overrides"
Cohesion: 0.14
Nodes (14): @tootallnate/once, overrides, bfj, css-select, http-proxy-agent, jsonpath, nth-check, postcss (+6 more)

### Community 596 - "_parse_reset_epoch"
Cohesion: 0.21
Nodes (6): _parse_reset_epoch(), _ProviderQuota, Response, Parse x-ratelimit-* headers and update per-provider quota state. Safe to call…, Convert a provider reset-time header value to a monotonic deadline. Supported…, TestParseResetEpoch

### Community 597 - "ai/registry.py"
Cohesion: 0.21
Nodes (13): all_models(), best_model_for(), ModelInfo, models_by_provider(), packages/ai/registry.py — Model Registry. Centralized registry of all models…, Register the default free-tier models., Information about a specific model., Register a model in the registry. (+5 more)

### Community 598 - ".add_specialist"
Cohesion: 0.14
Nodes (8): SpecialistFamily, SystemType, Add a specialist to a company. Args: company_id: Company ID name: Specialist…, Get all specialists of a specific family for a company. Args: company_id:…, Get specialists that can handle a task with given capabilities. Args:…, Generate a name for a specialist based on family., Get default capabilities for a specialist family., Get default tools for a specialist family.

### Community 599 - "_RedisBackend"
Cohesion: 0.22
Nodes (5): Redis-backed shared state using SET NX / DELETE / SETEX / INCR+EXPIRE., Lazy-create the Redis client (imported on first use so a missing ``redis``…, Clear all cooldown entries (for test teardown)., Clear all probe-lock entries (for test teardown). Mirrors…, _RedisBackend

### Community 600 - "cmd_autonomy"
Cohesion: 0.23
Nodes (13): _backend_get(), cmd_autonomy(), cmd_loops(), _grade_icon(), GET an un-gated backend read endpoint (/api/autonomy/status, /api/loops). These…, Snapshot of the agency's autonomy: active brain, loop readiness, dispatch., Loop Engineering fleet readiness + the costliest loops, from /api/loops., tests/test_telegram_observe.py Tests for the read-only "observe from Telegram"… (+5 more)

### Community 601 - "test_critical_flows.py"
Cohesion: 0.29
Nodes (13): _do_login(), _http_ok(), _playwright(), Create a task via the REST API (the same endpoint the UI calls) and poll its…, Direct (non-agent) chat: hit the OpenAI-compatible proxy completion the same…, Best-effort login. Returns True if we end up authenticated., _require_backend(), _require_proxy() (+5 more)

### Community 602 - "test_autonomy_pipeline_regressions.py"
Cohesion: 0.15
Nodes (13): asyncio, Regression tests for the autonomy pipeline bugs that blocked the agency from…, The README's zero-dependency deploy uses ``STORAGE_BACKEND=sqlite``. Pre-fix:…, The whole point of durable persistence is that schedules survive a process…, APScheduler fires jobs from a background thread with no event loop. Pre-fix:…, # NOTE: do NOT set STORAGE_BACKEND at module level — it would pollute every, The dataclass exposes ``enabled`` (bool) only — code that read ``.status``…, End-to-end: activate_company() on a fresh company creates all 6… (+5 more)

### Community 603 - "test_brain_priority_scanner.py"
Cohesion: 0.14
Nodes (13): Regression tests for: brain-skip-paid, provider-priority persistence, scanner…, The PUT /api/providers/{id} endpoint did not persist priority edits because the…, scanner.py used to end with a bare `systems` statement at module level, which…, Priority must be an int (or None for unset) and within a sane range so a typo…, The PUT /api/providers/{id} handler does: for k, v in…, The model-layer test above only proves the Pydantic field works. A FastAPI body…, Defensive check: the file must not end with a stray `systems` line. Reading…, test_provider_update_accepts_priority_field() (+5 more)

### Community 605 - "test_openclaw_gateway.py"
Cohesion: 0.14
Nodes (4): tests/test_openclaw_gateway.py — OpenClaw in-process WebSocket gateway tests., Dockerfile.backend does NOT install @openclaw/cli (in-process gateway now)., render_yaml(), test_dockerfile_backend_no_openclaw_cli()

### Community 606 - "TestDisabledReasonRendering"
Cohesion: 0.14
Nodes (5): ``describe_disabled_reason`` is rendered next to the on/off switch. The stored…, Anthropic sends 400 for an empty balance, not 402., A reason the operator cannot read still beats no reason at all., Guards the seam: the writer and this renderer must not drift apart. Scans the…, TestDisabledReasonRendering

### Community 608 - "test_workflow_models.py"
Cohesion: 0.18
Nodes (5): tests/test_workflow_models.py — Unit tests for workflow/models.py., TestCheckRun, CheckRun, Any, Structured, execution-based verification result. Verifier agents produce ONLY…

### Community 609 - "get_tool_registry"
Cohesion: 0.17
Nodes (9): get_tool_registry(), Return the module-level ToolRegistry singleton. On first call, registers built-…, _known_tool_names(), Any, field_validator, Core tools plus whatever the capability registry currently exposes. A static…, Reject names with no dispatch path, accept everything reachable., auto_register() (+1 more)

### Community 610 - "loop_readiness"
Cohesion: 0.22
Nodes (12): _cmd_audit(), DriftReport, _grade(), loop_readiness(), main(), BaseModel, Namespace, agent/loop_registry.py — Loop Engineering governance layer. This module turns… (+4 more)

### Community 611 - "._connect"
Cohesion: 0.15
Nodes (6): Connection, Path, Return all stored key/value pairs for *user_id*., Delete a memory entry. Returns ``True`` if a row was removed., Upsert a memory entry for *user_id*., Return the stored value for *key*, or ``None`` if not found.

### Community 612 - "Process"
Cohesion: 0.15
Nodes (12): Output Format, Process, Purpose, Rules, Skill: auto-fix, Step 1: Discover Fix Commands, Step 2: Run Fixers (Auto-fixable), Step 3: Run Checkers (Non-auto-fixable) (+4 more)

### Community 613 - "Skill: Brain Dump"
Cohesion: 0.15
Nodes (12): Example Prompt to Trigger, Instructions, Notes, Output Format, Purpose, Skill: Brain Dump, Step 1: Capture Everything, Step 2: Categorize (+4 more)

### Community 614 - "Process"
Cohesion: 0.15
Nodes (12): Process, Purpose, Rules, Skill: context-prime, Step 1: Read Core Docs, Step 2: Map the Architecture, Step 3: Find Conventions, Step 4: Understand Data Flow (+4 more)

### Community 615 - "Instructions"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Instructions, Role 1: Security Reviewer, Role 2: Correctness Reviewer, Role 3: Performance Reviewer, Role 4: Maintainability Reviewer, Skill: council-review, Step 1 — Gather the diff (+4 more)

### Community 616 - "Skill: duplicate-thread"
Cohesion: 0.15
Nodes (12): Files, How It Works, In a Claude prompt, Integration, Manual duplication, Merging Back, meta.json Schema, Purpose (+4 more)

### Community 617 - "Skill: Email Triage"
Cohesion: 0.15
Nodes (12): Example Prompt to Trigger, Instructions, Notes, Output Format, Purpose, Skill: Email Triage, Step 1: Intake, Step 2: Triage Categories (+4 more)

### Community 618 - "Process"
Cohesion: 0.15
Nodes (12): Anti-Patterns, Process, Purpose, Rules, Skill: feature-flag, Step 1: Assess Flag Need, Step 2: Define the Flag, Step 3: Implement the Guard (+4 more)

### Community 619 - "Process"
Cohesion: 0.15
Nodes (12): 1. Review Staged and Unstaged Changes, 2. Review Commit History, 3. Validate Commit Messages, 4. Clean Up if Needed, 5. Confirm Branch State, 6. Push, Notes, Output (+4 more)

### Community 620 - "Skill: graphify — Knowledge Graph Token Optimization"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Claude's query protocol (use this instead of Read tool for exploration):, Graph Artifacts — What to Commit, How to Use the Graph (Token Savings Protocol), Installation (one-time per machine), Instead of reading raw files:, Key commands:, Relationship to repowise-intelligence Skill (+4 more)

### Community 621 - "Skill: prompt-library"
Cohesion: 0.15
Nodes (12): 1. Sync Snapshots, 2. Generate Library Index, 3. Generate TRANSPARENCY.md, 4. Update CHANGELOG.md in prompts/, 5. Commit, Directory Structure Created, Output, Purpose (+4 more)

### Community 622 - "Skill: prompt-transparency"
Cohesion: 0.15
Nodes (12): 1. Collect All Agent & Skill Definitions, 2. Extract Key Behavioral Dimensions, 3. Generate Transparency Report, 4. Flag Risks, 5. Commit the Report, Example Usage, Inspiration, Output Format (+4 more)

### Community 623 - "Skill: Research"
Cohesion: 0.15
Nodes (12): Example Prompt to Trigger, Instructions, Notes, Output Format, Purpose, Skill: Research, Step 1: Define the Research Question, Step 2: Identify Source Categories (+4 more)

### Community 624 - "Skill: scope-guard"
Cohesion: 0.15
Nodes (12): Anti-Patterns to Avoid, Output Format, Process, Purpose, Rules, Skill: scope-guard, Step 1: Define the Scope Contract, Step 2: Pre-Implementation Check (+4 more)

### Community 625 - "test_new_features_e2e.py"
Cohesion: 0.32
Nodes (11): APIRequestContext, base_url(), do_login(), fail(), ok(), Page, Result, run_tests() (+3 more)

### Community 626 - "admin_update_task_router.py"
Cohesion: 0.22
Nodes (12): _expected_admin_secret(), _extract_admin_token(), BaseModel, backend/admin_update_task_router.py Step 1: POST…, Mount the update-task endpoint on ``app``. Idempotent: skips if a path with the…, Body for ``POST /api/workflow/orchestrator/update-task/{run_id}``.…, Resolve the admin secret from env. Order matches admin_digest_router.py:…, Inject ``additional_instructions`` into a paused or running WorkflowRun.… (+4 more)

### Community 627 - "ProviderManager"
Cohesion: 0.17
Nodes (8): ChatResponse, ProviderManager, Any, Provider, Coordinates provider selection, failover, and health., Return providers sorted by priority (lowest = highest priority)., Send a chat request with automatic failover. Retry policy: 1. If ``model`` is…, Check health of all configured providers.

### Community 628 - "Instructions"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Instructions, Role 1: Security Reviewer, Role 2: Correctness Reviewer, Role 3: Performance Reviewer, Role 4: Maintainability Reviewer, Skill: council-review, Step 1 — Gather the diff (+4 more)

### Community 629 - "Skill: graphify — Knowledge Graph Token Optimization"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Claude's query protocol (use this instead of Read tool for exploration):, Graph Artifacts — What to Commit, How to Use the Graph (Token Savings Protocol), Installation (one-time per machine), Instead of reading raw files:, Key commands:, Relationship to repowise-intelligence Skill (+4 more)

### Community 630 - "Skill: platform-setup — Autonomous Agency Bootstrap"
Cohesion: 0.15
Nodes (12): Ongoing autonomous operation, Phase 1 — Verify deployment health (no auth needed), Phase 2 — Login as admin, Phase 3 — Onboard the platform itself as a company, Phase 4 — Verify specialists were provisioned, Phase 5 — Configure GitHub integration, Phase 6 — Trigger first agency cycle manually, Phase 7 — Verify autonomous schedule is active (+4 more)

### Community 631 - "Device compatibility and model picks"
Cohesion: 0.15
Nodes (12): Acceleration at a glance, Apple Silicon: chip tier vs bandwidth (qualitative), Desktops and workstations, Device compatibility and model picks, Edge cases, How to read memory on different platforms, Laptops and all-in-ones, NVIDIA examples by VRAM (CUDA) (+4 more)

### Community 632 - "Autonomy Uplift — Living Roadmap & Detailed Implementation Specs"
Cohesion: 0.15
Nodes (12): 0. The goal (operator's words), 1. Shipped ✅, 2. In flight 🟡, 3. Pending ⬜ — detailed implementation specs, 3a. Apply the slop-gate to the sibling auto-PR scripts ✅  (size: S), 3b. Hermes — **our own** Hermes server (in-repo), UI-wired ✅  (size: M), 3c. CRISPY — harden, then re-enable ✅  (size: L, risky-module-review), 3d. Phase 3 — auto-PR *quality* beyond the slop-gate ✅  (size: M) (+4 more)

### Community 633 - "OpenClaw — iOS Control of the Agency (Single-Service Free-Tier Deploy)"
Cohesion: 0.15
Nodes (12): 1. Set env vars on the existing `local-llm-server` service, 2. Deploy, 3. Check the status, 4. Get the pairing QR, 5. Pair and verify, Alternative: Telegram bot, Architecture (single-service), Free-tier caveats (+4 more)

### Community 634 - "rules"
Cohesion: 0.15
Nodes (12): rules, import/no-anonymous-default-export, jsx-a11y/anchor-is-valid, jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/no-static-element-interactions, no-console, no-template-curly-in-string (+4 more)

### Community 635 - "_Budget"
Cohesion: 0.15
Nodes (5): _Budget, Shared attempt + wall-clock budget for one logical completion. Bounds the whole…, True when free/local providers have used everything but the reserve. Only the…, disabled(), Record auto-disable calls instead of writing operator state.

### Community 636 - "Summary"
Cohesion: 0.15
Nodes (12): Checklist, Rollout notes, Summary, Test plan, UNIT 1 — Fix duplicate ceo_direct tasks ✅, UNIT 2 — Portfolio → task materializer (default ON) ✅, UNIT 3 — Config hygiene (zero behavior change) ✅, UNIT 4 — Commit model catalog `config/models.yaml` ✅ (+4 more)

### Community 637 - "Agent Transparency Report"
Cohesion: 0.15
Nodes (12): Agent Transparency Report, Guardrails and Limits, How to Verify This, Human Oversight Points, 🔨 Implementer, ⚖️ Judge, 📋 Planner, 🔍 Reviewer (+4 more)

### Community 638 - "update_provider_policy"
Cohesion: 0.19
Nodes (12): _get_provider_policy(), ProviderPolicyUpdate, BaseModel, get, put, Read the durable provider policy, falling back to a safe default. Returns a…, Persist the provider policy and return the new state., Return the durable provider policy (single source of truth for paid-provider… (+4 more)

### Community 639 - ".publish"
Cohesion: 0.17
Nodes (7): Any, Task, Broadcast an event to all matching subscribers. Returns the number of callbacks…, Fire-and-forget publish. Creates a background task. Returns the asyncio.Task so…, Return recent events for a topic., Return bus statistics., Check if a topic matches a pattern with * and ** wildcards.

### Community 640 - "_InMemoryBackend"
Cohesion: 0.18
Nodes (4): _InMemoryBackend, Single-process backend using asyncio.Lock + dicts with TTL timestamps., Clear all cooldown entries (for test teardown)., Clear all probe-lock entries (for test teardown). ``cooldown_clear`` only…

### Community 641 - "TestModelCostTableUpdates"
Cohesion: 0.26
Nodes (3): New models are present in the cost table with sensible prices., get_cost_table() API exposes the new models with correct structure., TestModelCostTableUpdates

### Community 642 - "TestDecisionsBotLinks"
Cohesion: 0.21
Nodes (4): tests/test_decisions_bot_links.py Pytest coverage for the new…, Decision prompts that exist *before* the orchestrator creates a run (e.g. a…, Re-sending the same Telegram message (offset rewind, bot restart re-delivery)…, TestDecisionsBotLinks

### Community 643 - "test_deploy_trigger_covers_image.py"
Cohesion: 0.21
Nodes (12): _image_copy_sources(), Regression guard: the Render deploy trigger must cover everything the image…, `packages/` holds the AI layer — the most deploy-sensitive code there is., The health step must be able to fail. It previously polled for any 200 starting…, Top-level paths ``Dockerfile.backend`` copies into the runtime image., Top-level path prefixes in the deploy workflow's push ``paths:`` filter., The filter must take root modules wholesale, matching `COPY *.py ./`. Listing…, test_deploy_verification_cannot_pass_silently_on_failure() (+4 more)

### Community 644 - "test_doctor_service_token_check.py"
Cohesion: 0.23
Nodes (12): _authed_client(), clean_store(), _clear(), tests/test_doctor_service_token_check.py — N5 follow-up: doctor check for…, Reset brain config store + SQLITE_DB_PATH + SERVICE_TOKEN., Build a TestClient authenticated as admin (for /api/doctor/diagnostics)., When SERVICE_TOKEN is not set, the doctor endpoint must surface a 'warn' check…, When SERVICE_TOKEN is set, the doctor endpoint must surface a 'pass' check. (+4 more)

### Community 645 - "TestRouterIntegration"
Cohesion: 0.31
Nodes (6): anyio, The behaviour this whole change exists for: once the first free provider has…, No strategy and no budgets configured — behaviour is unchanged., The director must see the provider round-trip, not the round trip plus JSON…, With nowhere to route, skipping would turn a slow request into a failed one —…, TestRouterIntegration

### Community 646 - "WorkspaceManifest"
Cohesion: 0.17
Nodes (8): _now(), Any, BaseModel, WorkspaceStatusLiteral, Structured manifest for an isolated workspace., Transition to a new status and update cleanup eligibility., Touch the last_heartbeat timestamp., WorkspaceManifest

### Community 647 - "CLAUDE.md — agent/"
Cohesion: 0.17
Nodes (11): Adding New Tools, `agent/loop.py` — `_commit_step()`, `agent/loop.py` — `_local_safety_check()`, `agent/tools.py` — `apply_diff()`, CLAUDE.md — agent/, Invariants — Do Not Break, Model Env Vars, Security Surface (+3 more)

### Community 648 - "skill_registry.py"
Cohesion: 0.17
Nodes (6): agent/skill_registry.py — Dynamic Skill Registry & Recommender Fetches skill…, Holds a pre-compiled regex + the original tech name., set_skill_registry(), _TechPattern, Tests for module-level pre-compiled pattern constants., TestPreCompiledPatterns

### Community 649 - "RegistrySkill"
Cohesion: 0.21
Nodes (6): Any, A skill fetched from a remote or local registry., Return ranked skill recommendations based on tech stack, active workflow types,…, RegistrySkill, Tests for RegistrySkill dataclass., TestRegistrySkill

### Community 650 - "Trajectory"
Cohesion: 0.20
Nodes (7): Path, Persist trajectory as JSON and return the file path., Reload a previously saved trajectory (read-only replay)., Return a summary dict suitable for logging / leaderboards., Complete record of one agent run against one task. Compatible with the…, Mark the trajectory as complete., Trajectory

### Community 651 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Idempotency Rules, Instructions, Skill: cooldown-resume, Step 1 — Read the checkpoint files, Step 2 — Assess the state, Step 3 — Verify changed files are correct, Step 4 — Run tests to confirm baseline (+3 more)

### Community 652 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Current Dependencies (quick reference), Instructions, Skill: dependency-audit, Step 1 — Evaluate the new dependency, Step 2 — Pin appropriately, Step 3 — Install and verify, Step 4 — Check for conflicts (+3 more)

### Community 653 - "Process"
Cohesion: 0.17
Nodes (11): 1. Audit Existing Skills, 2. Identify Gaps, 3. Propose Improvements, 4. Implement, 5. Validate, Notes, Output, Process (+3 more)

### Community 654 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Instructions, Skill: smart-commit, Step 1 — Confirm changelog is updated, Step 2 — Run tests, Step 3 — Check for obvious issues, Step 4 — Stage your changes, Step 5 — Write a conventional commit message (+3 more)

### Community 655 - "Skill: system-prompt-audit"
Cohesion: 0.17
Nodes (11): 1. Inventory Collection, 2. Consistency Check, 3. Safety Check, 4. Generate Audit Report, 5. Exit Codes, Integration, Purpose, Related Skills (+3 more)

### Community 656 - "Skill: task-alive-updates"
Cohesion: 0.17
Nodes (11): Example Output, Files, How It Works, Implementation Rules, In a shell script / agent harness, In Claude task descriptions, Integration with parallel-agents, Purpose (+3 more)

### Community 657 - "Process"
Cohesion: 0.17
Nodes (11): 1. Read the Task Carefully, 2. Define the Boundary, 3. Identify Temptations, 4. Lock the Scope, 5. Out-of-Scope Findings, Notes, Output, Process (+3 more)

### Community 658 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Instructions, Skill: test-first-executor, Step 1 — Identify what needs testing, Step 2 — Write the test first, Step 3 — Confirm the test FAILS before implementation, Step 4 — Implement until the test passes, Step 5 — Run the full suite (+3 more)

### Community 659 - "LocalBrainStore"
Cohesion: 0.21
Nodes (8): BaseModel, backend/admin_local_brain_router.py — admin-session proxy for the local-brain…, _store(), ToggleBody, LocalBrainStore, backend/local_brain_store.py — DB-persisted state for the local GLM 5.2 brain.…, SQLite-backed store for the local GLM brain toggle + heartbeat., Same mirror file brain_config already uses. One file, fewer surprises.

### Community 660 - ".create_company"
Cohesion: 0.17
Nodes (7): BusinessCategory, Company, Get a company by ID. Args: company_id: Company ID Returns: Company instance or…, Update a company. Args: company_id: Company ID **kwargs: Fields to update…, List companies with optional filtering. Args: owner_id: Filter by owner ID…, Create an initial company graph for a new company. Args: company_id: Company ID…, Create a new company (idempotent — returns existing if domain matches). Checks…

### Community 661 - "14. Standing Instructions — Universal Agent Discipline"
Cohesion: 0.17
Nodes (12): 14.10 Fake Competence — the 10 Patterns, 14.11 Final Gate — run on every answer before sending, 14.1 Reading Intent, 14.2 Breaking Problems Down, 14.3 Effort Placement, 14.4 Verification, 14.5 Known vs Guessed, 14.6 Self-Attack (+4 more)

### Community 662 - "Skill: agent-browser — Real Chrome Browser Automation"
Cohesion: 0.17
Nodes (11): Applying to the local-llm-server Platform, Core Commands, How to Use This Skill, Installation (one-time), Skill: agent-browser — Real Chrome Browser Automation, Step 1 — Check Chrome is running with debugging, Step 2 — Navigate and snapshot, Step 3 — Interact using element refs (+3 more)

### Community 663 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Idempotency Rules, Instructions, Skill: cooldown-resume, Step 1 — Read the checkpoint files, Step 2 — Assess the state, Step 3 — Verify changed files are correct, Step 4 — Run tests to confirm baseline (+3 more)

### Community 664 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Current Dependencies (quick reference), Instructions, Skill: dependency-audit, Step 1 — Evaluate the new dependency, Step 2 — Pin appropriately, Step 3 — Install and verify, Step 4 — Check for conflicts (+3 more)

### Community 665 - "Skill: dev-browser — Browser Automation via Sandboxed JS"
Cohesion: 0.17
Nodes (11): Browser API, CLI flags, Connect to existing Chrome, Full script example (Playwright Page API), Installation, LLM usage patterns, Performance, Primary invocation styles (+3 more)

### Community 666 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Instructions, Skill: test-first-executor, Step 1 — Identify what needs testing, Step 2 — Write the test first, Step 3 — Confirm the test FAILS before implementation, Step 4 — Implement until the test passes, Step 5 — Run the full suite (+3 more)

### Community 667 - "Agent Orchestration Design"
Cohesion: 0.17
Nodes (12): Agent Orchestration Design, Execution Pathway, Four-Agent Structure, Key Invariants, OSS Inspirations (Clean-Room), Overview, Plan-First Pathway, Release-Readiness Pathway (+4 more)

### Community 668 - "Universality: case-coverage matrix"
Cohesion: 0.17
Nodes (12): A. Connection & credentials, B. Provider & host, C. Delivery / branch policy  *(detected — see DeliveryPolicy)*, D. CI / checks, E. Review automation & humans, F. Repo state & conflicts, G. Task origin, H. Governance / safety / HITL (+4 more)

### Community 669 - "Workspace Isolation Architecture"
Cohesion: 0.17
Nodes (12): Configuration, Directory Layout, Error Handling, Lifecycle States, Metrics, Overview, Path Derivation, Path Safety (+4 more)

### Community 670 - "Quantization Internals"
Cohesion: 0.17
Nodes (12): Absmax Quantization (Symmetric), Activation Quantization, AWQ (Activation-Aware Weight Quantization), Bits and Bytes (bitsandbytes), Data Types, GGUF / llama.cpp Quantization, GPTQ (Post-Training Quantization for GPT), Post-Training Quantization (PTQ) (+4 more)

### Community 671 - "Implementation — DB-persisted, UI-switchable Brain (PR #824 follow-up)"
Cohesion: 0.17
Nodes (11): Architecture (per plan §3), Files touched, Hard constraints (from the plan) — all met, Implementation — DB-persisted, UI-switchable Brain (PR #824 follow-up), Modified files, New files, Resolution precedence, Risks & mitigations (per plan §6) (+3 more)

### Community 672 - "2. Pending ⬜ — detailed implementation specs"
Cohesion: 0.17
Nodes (11): 0. The goal (unchanged), 1. Shipped in the previous pass ✅ (recap, do not redo), 2. Pending ⬜ — detailed implementation specs, 3. Deferred 🔭, 4. Operating notes (unchanged, for implementers), N1. Activate the reliability spine — wire the watchdog, schedule the digest ⬜  (size: M, risk: low), N2. Surface Hermes (and all runtimes) status in the Doctor/Runtimes UI ⬜  (size: S, risk: low), N3. Real CI-failure autofix — close the "Agency: cannot fix tests" loop (issue #398) ✅  (size: L, risk: medium) (+3 more)

### Community 673 - "467 Public Site Truth Spec"
Cohesion: 0.17
Nodes (11): 467 Public Site Truth Spec, Architecture Page Truth, Content Rules, Current State, Feature Matrix Truth, Required: Public Site Truth Spec, Site Structure, Tier System for Features (+3 more)

### Community 674 - "extract_refusal"
Cohesion: 0.27
Nodes (4): extract_refusal(), Extract the ``refusal`` string from an OpenAI-format response body. Returns the…, extract_refusal() surfaces model refusals from provider response bodies., TestExtractRefusal

### Community 675 - "TestRequireAdmin"
Cohesion: 0.29
Nodes (3): Return a FastAPI dependency that checks for a specific permission., require_permission(), TestRequireAdmin

### Community 676 - "check_container_posture.py"
Cohesion: 0.26
Nodes (11): check_compose(), check_policy_baseline(), check_sandbox_profiles(), _load_yaml(), main(), Any, Path, scripts/check_container_posture.py — assert the container security posture. CI… (+3 more)

### Community 677 - "Kimi Web-Bridge Service"
Cohesion: 0.17
Nodes (11): API, Connecting to the Main Backend, Docker, Environment Variables, `GET /health`, `GET /v1/models`, How It Works, Kimi Web-Bridge Service (+3 more)

### Community 678 - "test_agile_api.py"
Cohesion: 0.17
Nodes (3): auth_headers(), Tests for /api/agile/* endpoints., Get auth headers for the seeded admin user (matched to seed_admin email).

### Community 679 - "test_app_settings.py"
Cohesion: 0.21
Nodes (10): asyncio, Tests for app_settings — DB-persisted settings + onboarding-gate default. These…, Point db.get_store() at an isolated temp SQLite DB., is_user_onboarding_allowed falls back to the global default for users with no…, sqlite_store(), test_defaults_when_unset(), test_gate_default_controls_unlisted_user(), test_refresh_cache_warms_sync_readers() (+2 more)

### Community 680 - "test_providers_live_e2e.py"
Cohesion: 0.27
Nodes (11): _auth_headers(), _login_via_email(), Any, tests/test_providers_live_e2e.py — Live integration test for…, The /api/providers list now annotates each record with is_brain/role. The role-…, Skip the current test with a structured reason (pytest.skip is fine too)., POST /api/auth/login and return the parsed JSON body. Raises on failure., Full JWT round-trip: login → PUT → GET → cleanup. Asserts that the providers… (+3 more)

### Community 681 - "test_skill_registry.py"
Cohesion: 0.20
Nodes (7): _FakeClient, _FakeResp, tests/test_skill_registry.py — Unit tests for agent/skill_registry.py, Stub httpx client for nested-registry fetch tests., Production regression: server started from a non-repo CWD indexed 0 local…, test_local_skills_dir_defaults_to_repo_root_not_cwd(), test_nested_registry_indexes_deeply_nested_skills()

### Community 682 - "TestAnthropicPayloadStructuredOutput"
Cohesion: 0.29
Nodes (3): _payload(), Tests for packages/ai/structured_output.py and its integration with the…, TestAnthropicPayloadStructuredOutput

### Community 683 - "test_task_clarification.py"
Cohesion: 0.17
Nodes (3): auth_headers(), Tests for needs_clarification status and /api/tasks/{id}/clarify endpoint., Get auth headers for an admin user.

### Community 684 - "validate_job_id"
Cohesion: 0.18
Nodes (4): parametrize, TestPathTraversalPrevention, Validate and return a job ID, or raise InvalidJobIdError., validate_job_id()

### Community 685 - "EvalHarness"
Cohesion: 0.24
Nodes (7): EvalHarness, Task, Runs agent functions against Tasks, records Trajectories and produces…, Execute the agent on a single task and return an EvalResult., Delegate to the agent callable (sync or async)., Run multiple tasks and aggregate into a BenchmarkReport. Set concurrency > 1 to…, AgentFn

### Community 686 - "_keyword_search"
Cohesion: 0.20
Nodes (10): Document, _keyword_search(), Score documents by query-term coverage with a title-match boost., A single knowledge-base entry (wiki page, source document, etc.)., _doc(), test_keyword_search_empty_query(), test_keyword_search_finds_relevant(), test_keyword_search_no_match() (+2 more)

### Community 687 - "_extractive_compress"
Cohesion: 0.18
Nodes (11): _extractive_compress(), Split text into sentences on . ! ? followed by whitespace or end-of-string., Return the highest-value sentences from *text* within *max_tokens*. Each…, _split_sentences(), test_compress_empty_text(), test_compress_prefers_query_relevant_sentences(), test_compress_result_non_empty_for_non_empty_input(), test_compress_short_text_verbatim() (+3 more)

### Community 688 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Failure / Retry Behaviour, Instructions, Skill: implementation-planner, Step 1 — Understand the current state, Step 2 — Write the plan, Step 3 — Get implicit approval before coding, Step 4 — Implement (+2 more)

### Community 689 - "Skill: pro-workflow"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Model Selection Guide, Phase 1 — Research (Scout), Phase 2 — Plan, Phase 3 — Implement, Phase 4 — Wrap Up, Skill: pro-workflow (+2 more)

### Community 690 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Learnings File Doesn't Exist?, Skill: replay-learnings, Step 1 — Read the learnings file, Step 2 — Filter relevant learnings, Step 3 — Check recent checkpoint history, Step 4 — Surface blockers from previous session (+2 more)

### Community 691 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Skill: repo-memory-updater, Step 1 — Inventory what changed, Step 2 — Check root AGENTS.md, Step 3 — Check module AGENTS.md files, Step 4 — Update .Codex/state/, Step 5 — Commit the update (+2 more)

### Community 692 - "Skill: resource-panel"
Cohesion: 0.18
Nodes (10): Ask Claude to emit a resource panel, Automated via shell (git-based), Fields, Files, How to Use, Integration, Output Format, Purpose (+2 more)

### Community 693 - "Skill: sandboxed-exec"
Cohesion: 0.18
Nodes (10): Example — run tests in isolation, Example — validate a generated script before saving, How It Works, Output Format, Purpose, Security Notes, Skill: sandboxed-exec, Steps (for Claude to follow) (+2 more)

### Community 694 - "Workflow"
Cohesion: 0.18
Nodes (10): Acceptance checks, Fill these in, Skill: client-onboarding, Step 1 — Create the company and kick off onboarding, Step 2 — Poll progress, Step 3 — Verify specialists were provisioned, Step 4 — Confirm the 24x7 agency runtime is live, Step 5 — Note real gaps instead of pretending they're solved (+2 more)

### Community 695 - "ECC Harness Patterns Skill"
Cohesion: 0.18
Nodes (10): 1. Harness Detection & Adaptation, 2. Session Lifecycle Hooks, 3. Cross-Harness Model Selection, 4. Persistent Harness Registry, ECC Harness Patterns Skill, Files to Create/Modify, Implementation Plan, Patterns to Adopt (+2 more)

### Community 696 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Failure / Retry Behaviour, Instructions, Skill: implementation-planner, Step 1 — Understand the current state, Step 2 — Write the plan, Step 3 — Get implicit approval before coding, Step 4 — Implement (+2 more)

### Community 697 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Skill: repo-memory-updater, Step 1 — Inventory what changed, Step 2 — Check root CLAUDE.md, Step 3 — Check module CLAUDE.md files, Step 4 — Update .claude/state/, Step 5 — Commit the update (+2 more)

### Community 698 - "Stop-Slop Quality Skill"
Cohesion: 0.18
Nodes (10): AI Tells Detected, Business Jargon, Emphasis Crutches (Banned Adverbs), Implementation, Integration Points, Meta-Commentary, References, Stop-Slop Quality Skill (+2 more)

### Community 699 - "Agency Core — Ruthless Architecture Audit & Migration Plan"
Cohesion: 0.18
Nodes (10): Acceptance check, Agency Core — Ruthless Architecture Audit & Migration Plan, Root causes (not symptoms), Section 1 — The Brutal Truth, Section 2 — Keep / Salvage / Replace / Remove, Section 3 — The Chosen Foundation, Section 4 — The New Agency Core, Section 5 — Migration Plan (minimal chaos, all on PR, CI green at each step) (+2 more)

### Community 700 - "AUTONOMY_CHARTER.md"
Cohesion: 0.18
Nodes (6): How to add or change a loop, LOOP.md — The loops that run this agency, Maturity ladder, The five building blocks (and how this repo realises them), The three operator tools (`agent/loop_registry.py`), Why this exists

### Community 701 - "Tailored Onboarding, Editable Companies & Dynamic Roles"
Cohesion: 0.18
Nodes (10): 1. Editable companies, anytime (not a one-shot wizard), 2. Question-driven provisioning — no cosmetic questions, 3. Dynamic, expandable roles (open registry, not a closed enum), 4. Agents start pre-powered, Invariants, Phases, Tailored Onboarding, Editable Companies & Dynamic Roles, The gaps to close (+2 more)

### Community 702 - "Issue #467 — Section 1: Pulled State + PR Inventory"
Cohesion: 0.18
Nodes (10): 1. Current Git State, 2. Open PRs (as of 2026-06-08), 3. Files Modified on consolidate/maturation-stable (vs master), 4. What Master Has (that consolidate doesn't), 5. What Is MISSING from master (0% delivered in #467), 6. Required Action Before Code, Branch: `consolidate/maturation-stable`, Issue #467 — Section 1: Pulled State + PR Inventory (+2 more)

### Community 703 - "Autonomy Charter — Telegram-Gated Self-Running Agency"
Cohesion: 0.18
Nodes (11): 1. Mission & operating principles, 2. Brain policy (free cloud LLMs), 3. The Gate Matrix (core artifact), 4. Telegram gate protocol, 6. Integration gaps to wire (follow-up implementation), 7. Definition of "fully autonomous" — acceptance criteria, 8. Safety invariants (carried from `agent/CLAUDE.md`), 🟢 Autonomous — run, then notify-only (+3 more)

### Community 704 - "Context: Agentic Agile + Portfolio Management"
Cohesion: 0.18
Nodes (10): Agile improvements shipped alongside, Autonomous intelligence (`agents/portfolio_intelligence.py`), Capacity & roadmap, Context: Agentic Agile + Portfolio Management, Extension ideas (not yet built), Prioritisation model — WSJF (SAFe), Problem, The two layers (+2 more)

### Community 705 - "Deploy to Google Cloud Run"
Cohesion: 0.18
Nodes (10): 1) Admin protection (required), 2) User API keys (required), 3) LLM provider (recommended), Build + deploy (Dockerfile), Deploy to Google Cloud Run, Notes / limitations on Cloud Run, Prereqs, Required configuration (+2 more)

### Community 706 - "Key Components"
Cohesion: 0.18
Nodes (10): 1. Input Embedding, 2. Multi-Head Self-Attention, 3. Residual Connections, 4. Feed-Forward Network (FFN), 5. Layer Normalization, Decoder-Only vs Encoder-Decoder, High-Level Structure, Key Components (+2 more)

### Community 707 - "Sampling Strategies Internals"
Cohesion: 0.18
Nodes (11): Beam Search, Greedy Decoding, Logit Processors (Structured Output), Min-p Sampling, Repetition Penalty, Sampling Strategies Internals, Temperature Sampling, The Output Distribution (+3 more)

### Community 708 - "LLM Router — architecture"
Cohesion: 0.18
Nodes (11): Bulkheads, Circuit breaker, Compatibility, Configuration, Context management, LLM Router — architecture, Modules, Request lifecycle (+3 more)

### Community 709 - "Killer TODO Roadmap — local-llm-server"
Cohesion: 0.18
Nodes (10): G1 — Per-Model Cost and Latency Attribution [P1] [NVD], G2 — Request Replay for Debugging [P2] [CBF], H1 — Vision Input Support for Multimodal Models [P2] [NVD], H2 — Audio Input / Whisper Transcription [P3] [NVD], Implementation Notes, Killer TODO Roadmap — local-llm-server, Priority Summary, SECTION G — Observability (NVD / CHM) (+2 more)

### Community 710 - "NVIDIA NIM — Free Tier Setup"
Cohesion: 0.18
Nodes (10): 1. Get your free API key, 2. Set the environment variable, 3. Restart the server, 4. Verify, How the kill switch protects you, NVIDIA NIM — Free Tier Setup, Related, Setup (5 minutes) (+2 more)

### Community 711 - "What to clean up"
Cohesion: 0.18
Nodes (10): 1. Render (production backend + worker), 2. Cloudflare Worker (frontend), 3. Local development machines, 4. GitHub secrets, 5. MongoDB collections, Post-Merge Environment Cleanup Guide, Post-merge verification checklist, Rollback (+2 more)

### Community 712 - "Worker Service — Operations Runbook"
Cohesion: 0.18
Nodes (10): Architecture, Deployment on Render, Environment variables, First-time setup, Graceful shutdown, Local development, Overview, Troubleshooting (+2 more)

### Community 713 - "test_bedrock_live.py"
Cohesion: 0.25
Nodes (10): _NEEDS_CREDS, asyncio, ProviderRouter discovers Bedrock from env and completes a real chat call., Health check returns True when real credentials are loaded from env., Call Bedrock Converse API directly with boto3 — no proxy layer., Verify the configured model ID accepts a converse request without auth errors., test_bedrock_direct_boto3_ping(), test_bedrock_health_check_with_real_creds() (+2 more)

### Community 714 - "run_proxy.sh"
Cohesion: 0.18
Nodes (10): AIDER_BASE_URL, GOOSE_BASE_URL, HERMES_BASE_URL, LOG_LEVEL, OLLAMA_BASE, OPENCODE_BASE_URL, PROXY_PORT, RATE_LIMIT_RPM (+2 more)

### Community 715 - "._db"
Cohesion: 0.24
Nodes (5): Any, Restore in-flight runs at startup. Called during backend bootstrap. Returns a…, Persist a WorkflowRun snapshot., Load a persisted run snapshot., Return checkpoints for runs that were not in a terminal state.

### Community 716 - "setup_ngrok.py"
Cohesion: 0.31
Nodes (10): _api(), authenticate_ngrok(), _find_ngrok(), get_or_create_static_domain(), main(), Return path to the ngrok binary (pyngrok location or PATH)., Update or append KEY=value in .env., rewrite_tunnel_scripts() (+2 more)

### Community 717 - "test_empirical_verify.py"
Cohesion: 0.49
Nodes (10): _make_runner(), MonkeyPatch, Path, Tests for AgentRunner._empirical_verify (opt-in executable validation gate)., test_empirical_verify_disabled_by_default(), test_empirical_verify_flags_compile_failure(), test_empirical_verify_passes_clean_module_without_tests(), test_empirical_verify_runs_matching_tests_and_passes() (+2 more)

### Community 718 - "test_google_provider_models.py"
Cohesion: 0.18
Nodes (7): The Google provider must only advertise models its endpoint actually serves.…, A role must never be assigned a model the picker does not list., An operator override of GEMINI_MODEL must appear in the picker. The catalog is…, The Doctor probe must target the path Gemini actually serves., test_configured_gemini_model_is_always_selectable(), test_google_role_models_are_offered_by_the_catalog(), test_liveness_probe_resolves_gemini_openai_compat_base()

### Community 719 - "get_livekit_config"
Cohesion: 0.18
Nodes (11): SAM_LLM_* env vars must override the NVIDIA defaults (Hermes/proxy routing)., Under TESTING the in-process worker must never be eligible to start., OPT-IN: defaulting to on OOM-killed the 512MB Render instance at boot…, test_config_configured(), test_config_llm_override(), test_config_unconfigured_reports_missing(), test_in_process_flag_default_off(), test_in_process_flag_forced_off_under_testing() (+3 more)

### Community 720 - "test_tasks_awaiting_approval_api.py"
Cohesion: 0.40
Nodes (10): _client(), asyncio, Task, TestClient, GET /api/tasks/awaiting-approval — dashboard surface for the pre-execution…, _seed(), test_admin_sees_system_owned_gated_tasks(), test_approving_removes_task_from_awaiting_list() (+2 more)

### Community 721 - "verify_token"
Cohesion: 0.18
Nodes (11): Test JWT token creation and verification., Test refresh token creation and validation., Test that access token fails with refresh validation., Test refreshing access token with refresh token., test_invalid_token_type(), test_refresh_access_token(), test_refresh_token_creation(), test_token_creation_and_verification() (+3 more)

### Community 722 - "task.py"
Cohesion: 0.31
Nodes (7): Enum, str, Task definition schema for the evaluation harness. Inspired by OpenHarness'…, Returns (success: bool, score: float ∈ [0, 1]). Raises NotImplementedError for…, SuccessCriterion, SuccessCriterionType, TaskDifficulty

### Community 723 - "Instructions"
Cohesion: 0.20
Nodes (9): Acceptance Checks, Instructions, Skill: insights, Step 1 — File change heatmap (which files change most), Step 2 — Failure pattern analysis, Step 3 — Retry analysis, Step 4 — Learnings frequency analysis, Step 5 — Produce a summary report (+1 more)

### Community 724 - "Protocol: Premium Utilitarian Minimalism UI Architect"
Cohesion: 0.20
Nodes (9): 1. Protocol Overview, 2. Absolute Negative Constraints (Banned Elements), 3. Typographic Architecture, 4. Color Palette (Warm Monochrome + Spot Pastels), 5. Component Specifications, 6. Iconography & Imagery Directives, 7. Subtle Motion & Micro-Animations, 8. Execution Protocol (+1 more)

### Community 725 - "The 5-Step Wrap-Up Ritual"
Cohesion: 0.20
Nodes (9): Acceptance Checks, Skill: wrap-up, Step 1 — Changes Audit, Step 2 — Quality Check, Step 3 — Learning Capture, Step 4 — Next Session Planning, Step 5 — One-Paragraph Summary, The 5-Step Wrap-Up Ritual (+1 more)

### Community 726 - "._check_permissions"
Cohesion: 0.29
Nodes (3): Raise PermissionError if the profile lacks required permissions., PermissionError, TestSwarmPermissions

### Community 727 - "TestNormalizeToolChoice"
Cohesion: 0.31
Nodes (4): _normalize_tool_choice(), Normalize the ``tool_choice`` parameter for the upstream backend. OpenAI…, Cloud models (with / in name) should keep tool_choice as-is., TestNormalizeToolChoice

### Community 728 - "Agent: Reviewer (Verifier)"
Cohesion: 0.20
Nodes (10): Activation, Agent: Reviewer (Verifier), Blocking Conditions (must return `fail`), Handoff, Key Invariant, Non-Blocking (may return `pass` with suggestions), Output Format, Preferred Model (+2 more)

### Community 729 - "Skill: Agentic Agile"
Cohesion: 0.20
Nodes (9): Autonomous ceremonies (`agents/agile_ceremonies.py`), Key Classes, Purpose, Related, Retrospective & health, Scheduled workflow, Skill: Agentic Agile, Testing (+1 more)

### Community 730 - "Skill: browserbase-ui-test — Adversarial UI Testing"
Cohesion: 0.20
Nodes (9): Applying to local-llm-server platform, Core philosophy, Execution pattern, Reporting, Round 1 — Core flow mapping, Round 2 — Adversarial scenarios, Round 3 — Accessibility + mobile, Skill: browserbase-ui-test — Adversarial UI Testing (+1 more)

### Community 731 - "Skill: financial-analyst (Agentic CFO)"
Cohesion: 0.20
Nodes (9): Branch, Components, Decision Rules, Purpose, Quick Start, Skill: financial-analyst (Agentic CFO), SKILL.md refresh Tue Jun  2 11:35:52 CEST 2026, Testing (+1 more)

### Community 732 - "Graphiti Temporal Context Skill"
Cohesion: 0.20
Nodes (9): 1. Agent Memory as Temporal Graph, 2. Multi-Agent Coordination, 3. Knowledge Queries, Database Schema, Files to Create, Graphiti Temporal Context Skill, Integration Opportunities, References (+1 more)

### Community 733 - "Skill: seo-audit-report"
Cohesion: 0.20
Nodes (9): How This Skill Works (Agent Instructions), Output Files, Parameters, Purpose, Quick Start, Revenue-at-Risk Disclaimer (load-bearing — always include in reports), Skill: seo-audit-report, Troubleshooting (+1 more)

### Community 734 - "ADR-008: LLMRouter — the single multi-provider routing gateway"
Cohesion: 0.20
Nodes (10): ADR-008: LLMRouter — the single multi-provider routing gateway, Comparison with OmniRoute, Consequences, Context, Differences — why a port was rejected, Incompatible components (explicitly rejected), References, Reusable components (ideas adopted) (+2 more)

### Community 735 - "Core Pillars"
Cohesion: 0.20
Nodes (9): 1. Unified Intent Orchestration, 2. Deep Sticky Memory, 3. Execution Cognition Flow, 4. Progress Humanization, Core Pillars, Direct Chat Evolution: Seamless Assistant Architecture, Failure Recovery, Overview (+1 more)

### Community 736 - "467 Golden Path — Locked Implementation Order"
Cohesion: 0.20
Nodes (10): 467 Golden Path — Locked Implementation Order, Agent Code (agent/ directory), Backend Code (backend/, handlers/), Golden Path Exceptions, Module-Specific Golden Paths, Skill Code (.agents/skills/), Verification, What Breaks the Golden Path (+2 more)

### Community 737 - "Attention Mechanisms Internals"
Cohesion: 0.20
Nodes (9): Attention Complexity, Attention Mechanisms Internals, Causal Masking, Multi-Head Attention (MHA), Parameter count for MHA:, Scaled Dot-Product Attention, Step-by-step, Why Attention? (+1 more)

### Community 738 - "LLM Router — configuration guide"
Cohesion: 0.20
Nodes (10): Budgets, cache.yaml, Environment variables, health.yaml, keys.yaml, LLM Router — configuration guide, models.yaml, Per-agent policies (+2 more)

### Community 739 - "LLM Router — provider guide"
Cohesion: 0.20
Nodes (9): Adding any OpenAI-compatible provider, Auth styles, Cheap tiers, Cloud providers, Free tiers, LLM Router — provider guide, Multiple keys, Premium (+1 more)

### Community 740 - "CI Troubleshooting Runbook"
Cohesion: 0.20
Nodes (10): A test hangs in CI but passes locally, All three CI jobs fail with "git exit code 128" in Post Checkout, CI Troubleshooting Runbook, CodeQL action version, Frontend tests fail in parallel / async timer leaks, GitHub Actions YAML block scalar — bash heredoc content at column 0, Python 3.13 compatibility status, Python test job fails — "Process completed with exit code 1", no .pytest_cache found (+2 more)

### Community 741 - "OutputFilter"
Cohesion: 0.20
Nodes (7): _count_remaining(), _filter_generic(), OutputFilter, Token-optimizing output filter for command stdout. Usage:: from output_filter…, Filter *stdout* from *command* for token efficiency. If FILTER_ENABLED is…, Generic compression for unrecognized commands., _truncate()

### Community 743 - "build_tech_db.py"
Cohesion: 0.40
Nodes (9): _as_list(), _clean(), convert(), _default_source(), _has_pattern(), main(), Any, Strip Wappalyzer's `\\;tag:...` metadata, leaving a plain regex. (+1 more)

### Community 744 - "main"
Cohesion: 0.29
Nodes (9): _detect_crlf(), _enumerate_matching_lines(), _eprint(), main(), Path, CRLF present if any line ends in CRLF., Yield (line_bytes, line_index) for every line in `data` containing `needle`., Pick the .env to migrate. See module docstring for resolution order. (+1 more)

### Community 745 - "run_bot"
Cohesion: 0.27
Nodes (9): _configure(), _default(), main(), Set an env var only when the operator hasn't already provided one., Call a Telegram Bot API method and return the parsed JSON (best-effort)., run_bot(), _tg_call(), TELEGRAM_POLLER_DISABLED=true makes run_bot() idle WITHOUT long-polling… (+1 more)

### Community 746 - "Dream"
Cohesion: 0.22
Nodes (6): Dream, Return the most recent dreams, newest first., A consolidated dream built from multiple session memories., Return a brief summary of the dream., Tests for Dream dataclass., TestDream

### Community 747 - "TestExtendedThinkingRouting"
Cohesion: 0.20
Nodes (6): Unit tests for extended thinking detection in handle_anthropic_messages., When thinking.type == enabled, routing should use agent_plan endpoint type., No thinking param → normal chat routing, not forced to reasoning., thinking_budget_tokens should appear in routing_meta when thinking is set., Without thinking param, thinking_budget_tokens not in routing_meta., TestExtendedThinkingRouting

### Community 748 - "TestZeroAttemptDiagnostics"
Cohesion: 0.29
Nodes (4): A zero-attempt exhaustion must say WHICH of the three causes it is. Nothing…, An operator whose switches reset on deploy needs to know that here., A broken registry must not turn a failed call into a crash., TestZeroAttemptDiagnostics

### Community 749 - "TestSessionMemory"
Cohesion: 0.20
Nodes (3): Tests for services/managed_agents.py — Managed Agents Dreams. Uses importlib to…, Tests for SessionMemory dataclass., TestSessionMemory

### Community 750 - "TestParsing"
Cohesion: 0.22
Nodes (5): parametrize, Includes a bare 404 with an empty body (observed on NVIDIA NIM) — no…, A malformed listing must never be read as "the key serves nothing"., TestParsing, TestUnknownModelDetection

### Community 751 - "test_quick_note_engine.py"
Cohesion: 0.22
Nodes (7): _before(), Guard that the quick-note engine agents use NVIDIA NIM as the primary engine…, implement_agent.py uses NVIDIA NIM exclusively — the Anthropic/Opus fallback…, Regression: _run_baseline_pytest() ran the FULL suite (no path filter,…, test_baseline_pytest_timeout_is_generous_and_failure_is_caught(), test_implement_agent_nvidia_primary(), test_review_agent_nvidia_primary()

### Community 752 - "_FakePersistence"
Cohesion: 0.20
Nodes (6): _FakePersistence, Schedule count must stay bounded even under 50 consecutive task failures. This…, In-memory ScheduleStore stand-in (sync upsert/remove/load_all)., Creating the same schedule name twice returns the same job — no duplication., test_schedule_create_idempotent_by_name(), test_schedule_growth_bounded_under_failure_storm()

### Community 753 - "TestRevenuePortfolio"
Cohesion: 0.20
Nodes (3): Severity -> potential revenue loss via the portfolio mechanism (PR #534 review)., Delegation packages must slot directly into agents/portfolio.py., TestRevenuePortfolio

### Community 755 - "synthesize"
Cohesion: 0.36
Nodes (9): _convert_to_ogg(), voice/tts.py — Text-to-Speech for the CEO voice pipeline. Converts text to an…, Convert audio to OGG Opus (Telegram voice note format) via pydub+ffmpeg., Convert text to OGG voice note bytes. Returns None on failure., _select_backend(), synthesize(), _synthesize_elevenlabs(), _synthesize_gtts() (+1 more)

### Community 757 - "rag_context.py"
Cohesion: 0.22
Nodes (8): ContextResult, agent/rag_context.py — Advanced RAG context management layer. Pipeline --------…, Combine ranked lists with Reciprocal Rank Fusion., Final output of the RAG pipeline., _rrf(), test_rrf_merges_two_rankings(), test_rrf_scores_descending(), test_rrf_single_ranking_preserves_order()

### Community 758 - "_extract_workflow_relevance"
Cohesion: 0.33
Nodes (4): _extract_workflow_relevance(), Return workflow types mentioned in the skill content., Tests for _extract_workflow_relevance()., TestExtractWorkflowRelevance

### Community 759 - "Skill: changelog-enforcer"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Changelog Location, Entry Format, Examples, Hook Behaviour, Instructions, Skill: changelog-enforcer, When to Use

### Community 760 - "Skill: learn-rule"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Instructions, Learnings File Format, Skill: learn-rule, Step 1 — Identify the rule, Step 2 — Append to learnings file, Step 3 — Check if CLAUDE.md should be updated, When to Use

### Community 761 - "Instructions"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Instructions, Skill: session-handoff, Step 1 — Capture current state, Step 2 — Write the handoff document, Step 3 — Update machine-readable state, Step 4 — Confirm the handoff is self-contained, When to Use

### Community 762 - "Any"
Cohesion: 0.25
Nodes (4): Any, field_validator, Accept both ISO-8601 datetime strings (from DB) and float timestamps., Keep legacy backend fields and Control Plane UI fields aligned.

### Community 763 - "prompts/README.md"
Cohesion: 0.22
Nodes (4): Command: /resume, References, Usage, What It Does

### Community 764 - "Skill: Agentic Portfolio Management"
Cohesion: 0.22
Nodes (8): Key Classes, Purpose, Related, Skill actions (via SkillBindings), Skill: Agentic Portfolio Management, Testing, Usage, WSJF

### Community 765 - "Skill: changelog-enforcer"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Changelog Location, Entry Format, Examples, Hook Behaviour, Instructions, Skill: changelog-enforcer, When to Use

### Community 766 - "Skill: cowork-session (Claude Cowork)"
Cohesion: 0.22
Nodes (8): Branch, Components, Purpose, Quick Start, Session Roles, Skill: cowork-session (Claude Cowork), Testing, When to Use

### Community 767 - "Skill: video-context — read a video without watching it"
Cohesion: 0.22
Nodes (8): How It Works, Limits — know these before relying on it, Skill: video-context — read a video without watching it, Testing, Usage, What To Do With The Transcript, When To Use This, Why This Exists

### Community 768 - "Decision"
Cohesion: 0.22
Nodes (9): 1. `LLMRouter` is the only gateway, 2. Providers are data, not code, 3. Secrets stay in the environment, 4. Three independent failure scopes, 5. Bulkhead isolation, 6. Context is managed losslessly, 7. Configuration is six committed YAML files, 8. Backwards compatibility by shim, not by rewrite (+1 more)

### Community 769 - "ADR 003: Multi-Agent Orchestration with Plan-Execute-Verify Loop"
Cohesion: 0.22
Nodes (8): ADR 003: Multi-Agent Orchestration with Plan-Execute-Verify Loop, Alternatives Considered, Consequences, Context, Decision, Negative, Neutral, Positive

### Community 770 - "Main proxy (`proxy.py`)"
Cohesion: 0.22
Nodes (9): Agent and workflow surfaces, API Surfaces and Route Map, Built-in admin and web UI, Control-plane style routers mounted in the proxy, Main proxy (`proxy.py`), Ollama-compatible, OpenAI-compatible, Separate hosted dashboard backend (`backend/server.py`) (+1 more)

### Community 771 - "Autonomous SDLC Loop (Agency Core, repo-agnostic)"
Cohesion: 0.22
Nodes (9): Autonomous SDLC Loop (Agency Core, repo-agnostic), Companies without a connected repo (URL-only onboarding), Design principle: repo-agnostic, not GitHub-Actions-bound, Detect & respect each repo's delivery policy, Integrations & intake sources (honest tiers), Reuse map (what already exists), Safety invariants (carry over from `agent/CLAUDE.md`), The gap this closes (+1 more)

### Community 772 - "The 8-Step Golden Path"
Cohesion: 0.22
Nodes (9): Step 1: Scout — Understand the territory, Step 2: Plan — Define the change, Step 3: Write tests first, Step 4: Implement, Step 5: Validate, Step 6: Review, Step 7: Document, Step 8: Commit and propose (+1 more)

### Community 773 - "PR #634 Implementation Tracker"
Cohesion: 0.22
Nodes (8): Phase 1 — Stop the bleeding + paid kill switch ✅, Phase 2 — Per-surface assignment in the UI 🔄, Phase 3 — Persistence hardening (#537, #524) ⏳, Phase 4 — Onboarding fixes (#593, #619, PR #623) ⏳, Phase 5 — Reliability (#522) ⏳, Phase 6 — Green tests + housekeeping ⏳, PR #634 Implementation Tracker, Verification checklist (final)

### Community 774 - "KV Cache Internals"
Cohesion: 0.22
Nodes (9): KV Cache Internals, KV Cache with Grouped Query Attention, Memory Layout, Paged Attention (vLLM), Prefill vs Decode Phase, Quantization of KV Cache, Speculative Decoding, The Problem: Redundant Computation (+1 more)

### Community 775 - "Platform Controls"
Cohesion: 0.22
Nodes (8): Across processes, Adding a control, API, Groups, How a value is resolved, Live vs restart-required, Platform Controls, What is deliberately **not** here

### Community 776 - "Release Procedure"
Cohesion: 0.22
Nodes (8): Changelog Update, Commit and Tag, Post-Release Checklist, Pre-Flight, Release Procedure, Rollback, Verify CI, Version Bump

### Community 777 - "V2.0 Modernization — Runbook"
Cohesion: 0.22
Nodes (8): Adding a new provider adapter, CI, Importing new code, Module map (old → new), Removing the shims (future cleanup), Rollback, Test migration, V2.0 Modernization — Runbook

### Community 778 - "Setup"
Cohesion: 0.22
Nodes (8): 1. Get LiveKit credentials, 2. Configure the backend (Render env vars), 3. The SAM voice worker, 4. Talk to SAM, Architecture, SAM Realtime Voice over LiveKit, Setup, Troubleshooting

### Community 779 - "frontend/package.json"
Cohesion: 0.22
Nodes (8): jest, moduleNameMapper, ^react-router$, ^react-router-dom$, name, private, proxy, version

### Community 780 - "AgentStatusPanel.tsx"
Cohesion: 0.25
Nodes (7): AgentStatus, AgentStatusPanelProps, AgentCard(), formatRelative(), ROLE_ICONS, STATUS_DOTS, STATUS_STYLES

### Community 781 - "AgentStatusPanel.jsx"
Cohesion: 0.25
Nodes (6): AgentCard(), formatRelative(), ROLE_ICONS, STATUS_DOTS, STATUS_STYLES, PHASE_LABELS

### Community 782 - "ToolCallViewer.tsx"
Cohesion: 0.25
Nodes (7): ToolCall, ToolCallViewerProps, getToolIcon(), STATUS_BADGES, STATUS_STYLES, TOOL_ICONS, ToolCallRow()

### Community 783 - "_get_current_user"
Cohesion: 0.25
Nodes (9): _get_bearer_token(), _get_current_user(), logout(), Depends, get, Extract and validate current user from token., Get current authenticated user., Logout (token invalidation happens on frontend by clearing localStorage). (+1 more)

### Community 784 - "apply_overrides"
Cohesion: 0.22
Nodes (9): apply_overrides(), Write *overrides* into ``os.environ`` and refresh dependent caches. Keys that…, Re-read every ``settings`` attribute from the updated environment. Re-runs…, _refresh_settings_singleton(), Re-running Settings.__init__ mints a new random secret when SECRET_KEY is…, test_apply_overrides_refreshes_the_settings_singleton(), test_apply_overrides_writes_only_catalogued_keys(), test_clearing_an_override_restores_the_startup_environment() (+1 more)

### Community 785 - "cleanup_stale_jobs"
Cohesion: 0.31
Nodes (8): cleanup_stale_jobs(), _is_stale(), Any, packages/scheduler/cleanup.py — schedule deduplication + stale removal.…, Remove a job from the store. Returns True on success, False on failure. Logs…, Check if a created_at timestamp is older than ttl_seconds. Handles multiple…, Remove stale run-once + stuck agency jobs from the durable store. Args: store:…, _safe_remove()

### Community 786 - "enrich_quick_note_issues.py"
Cohesion: 0.42
Nodes (8): _dispatch_generation(), _fetch_open_issues(), _has_context(), _headers(), _is_quick_note(), main(), Ask the bulk context workflow to generate documents for these issues., True when a context branch already exists for this issue. Checked against…

### Community 787 - "_status_snapshot"
Cohesion: 0.31
Nodes (9): cmd_wait(), Block until download completes + colibri answers /v1/models., _status_snapshot(), await_ready(), colibri_model_id(), colibri_url(), _list_models_payload(), Normalise an OAI ``/v1/models`` response into a list of model ids. (+1 more)

### Community 789 - "test_backend_requirements_cover_runtime_imports.py"
Cohesion: 0.25
Nodes (8): _declared_packages(), parametrize, Path, Guard against the recurring "works in CI, missing in prod" dependency drift.…, Return the normalised distribution names declared in *requirements*., If the Dockerfile ever installs the root file, this guard can relax. Until then…, test_backend_requirements_declares_runtime_package(), test_dockerfile_still_installs_backend_requirements_only()

### Community 790 - "test_changelog_parity_guard.py"
Cohesion: 0.22
Nodes (3): tests/test_changelog_parity_guard.py — corruption guard for the changelog gate.…, A 7-equals line under a title (Markdown setext H1) must not false-positive., test_setext_heading_underline_is_not_flagged()

### Community 791 - "Path"
Cohesion: 0.22
Nodes (5): Path, Contract: Auth code with hardcoded SECRET_KEY triggers a safety issue. The…, Contract: Clean code without secrets passes safety check., Contract: Safety check only applies to Python files., Contract: Module-wide change touching too few files is flagged.

### Community 793 - "TestGithubSignalHardening"
Cohesion: 0.22
Nodes (4): FakeResp, fetch_github_signals must degrade gracefully (log + return empty lists) on a…, Even with a 200, a malformed/rate-limited body that isn't a list must not be…, TestGithubSignalHardening

### Community 794 - "FakeScheduleCollection"
Cohesion: 0.25
Nodes (3): FakeDeleteResult, FakeScheduleCollection, Minimal async MongoDB-like collection for testing nuclear_cleanup.

### Community 795 - "test_scanner_deps_parity.py"
Cohesion: 0.31
Nodes (8): _declared_packages(), Guard against the CI-vs-production dependency drift that made gucci.com (and…, Top-level module names imported anywhere in services/scanner.py., Every third-party package the scanner imports must be in the file the…, Belt-and-suspenders: the two deps whose absence caused the gucci.com production…, _scanner_imports(), test_critical_scanner_deps_explicitly_present(), test_scanner_third_party_deps_declared_in_backend_requirements()

### Community 796 - "stt.py"
Cohesion: 0.36
Nodes (8): voice/stt.py — Speech-to-Text for the CEO voice pipeline. Transcribes audio…, Transcribe audio bytes to text. Returns empty string on failure., Fallback: Google Web Speech API via SpeechRecognition library., _select_backend(), transcribe(), _transcribe_google(), _transcribe_local(), _transcribe_openai()

### Community 797 - "LoopSpec"
Cohesion: 0.29
Nodes (4): LoopSpec, field_validator, loop-cost: approximate tokens this loop spends over 30 days., A single autonomous loop in the fleet. A *loop* is a recurring, self-iterating…

### Community 799 - "_score_turns"
Cohesion: 0.36
Nodes (8): Score each turn by exponential recency decay combined with query relevance.…, _score_turns(), test_score_turns_empty(), test_score_turns_importance_multiplier(), test_score_turns_recency_newer_scores_higher(), test_score_turns_relevance_boosts_score(), test_score_turns_sorted_descending(), _turn()

### Community 800 - "TrajectoryStep"
Cohesion: 0.25
Nodes (5): Any, Agent trajectory recorder – captures every step an agent takes so runs can be…, A single action/observation pair in an agent trajectory., Append a step and return it., TrajectoryStep

### Community 801 - "quality_checker.py"
Cohesion: 0.32
Nodes (6): AITellType, Enum, str, Quality checker inspired by stop-slop (https://github.com/hardikpandya/stop-…, Categories of AI tells, Tests for quality checker (stop-slop inspired)

### Community 802 - "Skill: docs-sync"
Cohesion: 0.25
Nodes (7): Acceptance Checks, ADR Guidelines, AGENTS.md Update Rules, Docs to Check After Each Change Type, Instructions, Skill: docs-sync, When to Use

### Community 803 - "Agent: Implementer (Executor)"
Cohesion: 0.25
Nodes (8): Activation, Agent: Implementer (Executor), Constraints, Handoff, Preferred Model, Responsibilities, Role, Shared State

### Community 804 - "Agent: Judge (Release / QA Gate)"
Cohesion: 0.25
Nodes (7): Activation, Agent: Judge (Release / QA Gate), Enforcement, Output, Responsibilities, Role, Verdict Meanings

### Community 805 - "Agent: Planner (Architect)"
Cohesion: 0.25
Nodes (8): Activation, Agent: Planner (Architect), Failure Behaviour, Handoff, Output Format, Preferred Model, Responsibilities, Role

### Community 806 - "Skill: browserbase-browser — Real Browser Automation"
Cohesion: 0.25
Nodes (7): Applying to local-llm-server platform, Core commands, Mode selection, Setup, Skill: browserbase-browser — Real Browser Automation, Troubleshooting, Workflow pattern

### Community 807 - "Skill: docs-sync"
Cohesion: 0.25
Nodes (7): Acceptance Checks, ADR Guidelines, CLAUDE.md Update Rules, Docs to Check After Each Change Type, Instructions, Skill: docs-sync, When to Use

### Community 808 - "Skill: memory-consolidation (Dream Memory)"
Cohesion: 0.25
Nodes (7): Branch, Consolidation Lifecycle, Memory Kinds, Purpose, Quick Start, Skill: memory-consolidation (Dream Memory), Testing

### Community 809 - "GitHub Branch Protection Settings"
Cohesion: 0.25
Nodes (7): Branch name pattern: `main` (or `master`), CODEOWNERS Setup, Enabling via GitHub CLI, GitHub Branch Protection Settings, Purpose, Required Settings, Why This Can't Be Fully Repo-Enforced

### Community 810 - "ADR 001: Self-Hosted OpenAI-Compatible Proxy"
Cohesion: 0.25
Nodes (7): ADR 001: Self-Hosted OpenAI-Compatible Proxy, Consequences, Context, Decision, Negative, Neutral, Positive

### Community 811 - "ADR 002: Dynamic Model Routing with Task Classification"
Cohesion: 0.25
Nodes (7): ADR 002: Dynamic Model Routing with Task Classification, Consequences, Context, Decision, Negative, Neutral, Positive

### Community 812 - "AGENTS.md — AI Agent Configuration for local-llm-server"
Cohesion: 0.25
Nodes (7): Agent Roles, AGENTS.md — AI Agent Configuration for local-llm-server, Operating Instructions, Quick Start for Agents, Risky Paths — Require Extra Care, State Files, Workspace Purpose

### Community 813 - "Advisor Strategy — Local Proxy Handling"
Cohesion: 0.25
Nodes (7): Advisor Strategy — Local Proxy Handling, How This Proxy Handles Advisor Requests, Incoming message history (advisor blocks), Local Equivalent: The Planner Role, Outgoing requests (tools array), Using the Real Advisor Strategy via This Proxy, What the Anthropic Advisor Strategy Is

### Community 814 - "ceo-micromanagement.md"
Cohesion: 0.25
Nodes (4): P0 behavior change, Readiness contract, Runtime model, Runtime types

### Community 815 - "Feature Maturity / Support Matrix"
Cohesion: 0.25
Nodes (8): Beta, Config Overrides, Disabled (demoted per issue #467 Section I), Enforcement, Experimental, Feature Maturity / Support Matrix, Maturity Tiers, Stable Core

### Community 816 - "Web UI + Admin (Claude Code–style)"
Cohesion: 0.25
Nodes (7): Acceptance checks, Approach, Files to change, Files to read first, Goal, Risks, Web UI + Admin (Claude Code–style)

### Community 817 - "467 Skill Inventory — load / wire / test status"
Cohesion: 0.25
Nodes (7): 467 Skill Inventory — load / wire / test status, Agent Specialties (not skills per se, but referenced in spec §B), Core Agency Skills (load/wire/test), Gaps Summary, Named Skills Referenced in Spec §C, Skill Registry, Test Coverage Summary

### Community 818 - "Free NVIDIA brain + UI-controlled provider policy + no silent spend"
Cohesion: 0.25
Nodes (8): Decisions (locked with the owner), Design: one UI-controlled Provider Policy (single source of truth), Free NVIDIA brain + UI-controlled provider policy + no silent spend, Open-PR / issue disposition (read + acted on), Root cause of the $20 burn (verified in-repo), SELF-CONTAINED AGENT PROMPT (paste to run cold), Verification / acceptance, Why this PR exists (context)

### Community 819 - "Issue #362: Nvidia repo setup"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #362: Nvidia repo setup, Implementation Prompt, Issue #362: Nvidia repo setup, Relevant Files to Read First, Risk Flags, TODO List

### Community 820 - "Issue #364: quick-note:https://www.marktechpost.com/2026/06/01/meet-memory-os-a-6-layer-open-source-memory-stack-built-on-top-of-hermes-agent/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #364: quick-note:https://www.marktechpost.com/2026/06/01/meet-memory-os-a-6-layer-open-source-memory-stack-built-on-top-of-hermes-agent/, Implementation Prompt, Issue #364: quick-note:https://www.marktechpost.com/2026/06/01/meet-memory-os-a-6-layer-open-source-memory-stack-built-on-top-of-hermes-agent/, Relevant Files to Read First, Risk Flags, TODO List

### Community 821 - "Issue #378: quick-note:https://www.marktechpost.com/2026/06/02/tinyfish-launches-bigset-an-open-source-multi-agent-system-that-builds-structured-live-datasets-from-plain-english-descriptions/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #378: quick-note:https://www.marktechpost.com/2026/06/02/tinyfish-launches-bigset-an-open-source-multi-agent-system-that-builds-structured-live-datasets-from-plain-english-descriptions/, Implementation Prompt, Issue #378: quick-note:https://www.marktechpost.com/2026/06/02/tinyfish-launches-bigset-an-open-source-multi-agent-system-that-builds-structured-live-datasets-from-plain-english-descriptions/, Relevant Files to Read First, Risk Flags, TODO List

### Community 822 - "Issue #379: quick-note:https://searchengineland.com/schema-markup-optimize-agentic-web-479080"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #379: quick-note:https://searchengineland.com/schema-markup-optimize-agentic-web-479080, Implementation Prompt, Issue #379: quick-note:https://searchengineland.com/schema-markup-optimize-agentic-web-479080, Relevant Files to Read First, Risk Flags, TODO List

### Community 823 - "Issue #380: quick-note:https://cursor.com/blog/cloud-agent-lessons"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #380: quick-note:https://cursor.com/blog/cloud-agent-lessons, Implementation Prompt, Issue #380: quick-note:https://cursor.com/blog/cloud-agent-lessons, Relevant Files to Read First, Risk Flags, TODO List

### Community 824 - "Issue #381: quick-note:https://www.xda-developers.com/claude-code-with-opus-48-is-expensive-but-i-made-it-efficient-with-my-local-ai-workflow/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #381: quick-note:https://www.xda-developers.com/claude-code-with-opus-48-is-expensive-but-i-made-it-efficient-with-my-local-ai-workflow/, Implementation Prompt, Issue #381: quick-note:https://www.xda-developers.com/claude-code-with-opus-48-is-expensive-but-i-made-it-efficient-with-my-local-ai-workflow/, Relevant Files to Read First, Risk Flags, TODO List

### Community 825 - "Issue #382: quick-note:https://claude.com/blog/how-coderabbit-used-claude-to-build-an-agent-orchestration-system"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #382: quick-note:https://claude.com/blog/how-coderabbit-used-claude-to-build-an-agent-orchestration-system, Implementation Prompt, Issue #382: quick-note:https://claude.com/blog/how-coderabbit-used-claude-to-build-an-agent-orchestration-system, Relevant Files to Read First, Risk Flags, TODO List

### Community 826 - "Issue #383: quick-note:https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #383: quick-note:https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/, Implementation Prompt, Issue #383: quick-note:https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/, Relevant Files to Read First, Risk Flags, TODO List

### Community 827 - "Issue #416: feat: Self-hosted Codebuff (freebuff) on free NVIDIA models + Telegram bot phone control"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #416: feat: Self-hosted Codebuff (freebuff) on free NVIDIA models + Telegram bot phone control, Implementation Prompt, Issue #416: feat: Self-hosted Codebuff (freebuff) on free NVIDIA models + Telegram bot phone control, Relevant Files to Read First, Risk Flags, TODO List

### Community 828 - "Issue #485: [Trend Digest] Week of 2026-06-08"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #485: [Trend Digest] Week of 2026-06-08, Implementation Prompt, Issue #485: [Trend Digest] Week of 2026-06-08, Relevant Files to Read First, Risk Flags, TODO List

### Community 829 - "Issue #488: quick-note:https://github.com/cookiy-ai/user-research-skill"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #488: quick-note:https://github.com/cookiy-ai/user-research-skill, Implementation Prompt, Issue #488: quick-note:https://github.com/cookiy-ai/user-research-skill, Relevant Files to Read First, Risk Flags, TODO List

### Community 830 - "Issue #491: Implement whatever is necessary from https://github.com/BehiSecc/awesome-claude-skills"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #491: Implement whatever is necessary from https://github.com/BehiSecc/awesome-claude-skills, Implementation Prompt, Issue #491: Implement whatever is necessary from https://github.com/BehiSecc/awesome-claude-skills, Relevant Files to Read First, Risk Flags, TODO List

### Community 831 - "Issue #493: Use the https://github.com/mvanhorn/last30days-skill skill to get the trend updated"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #493: Use the https://github.com/mvanhorn/last30days-skill skill to get the trend updated, Implementation Prompt, Issue #493: Use the https://github.com/mvanhorn/last30days-skill skill to get the trend updated, Relevant Files to Read First, Risk Flags, TODO List

### Community 832 - "Issue #495: Read https://www.anthropic.com/news/claude-fable-5-mythos-5 and understand if mythos or fable can be added to the repo"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #495: Read https://www.anthropic.com/news/claude-fable-5-mythos-5 and understand if mythos or fable can be added to the repo, Implementation Prompt, Issue #495: Read https://www.anthropic.com/news/claude-fable-5-mythos-5 and understand if mythos or fable can be added to the repo, Relevant Files to Read First, Risk Flags, TODO List

### Community 833 - "Issue #504: EPIC: Autonomy hardening — live-verified defects 2026-06-10"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #504: EPIC: Autonomy hardening — live-verified defects 2026-06-10, Implementation Prompt, Issue #504: EPIC: Autonomy hardening — live-verified defects 2026-06-10, Relevant Files to Read First, Risk Flags, TODO List

### Community 834 - "Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass, Implementation Prompt, Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass, Relevant Files to Read First, Risk Flags, TODO List

### Community 835 - "Issue #656: Bugs"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #656: Bugs, Implementation Prompt, Issue #656: Bugs, Relevant Files to Read First, Risk Flags, TODO List

### Community 836 - "Issue #657: quick-note:https://github.com/earendil-works/pi"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #657: quick-note:https://github.com/earendil-works/pi, Implementation Prompt, Issue #657: quick-note:https://github.com/earendil-works/pi, Relevant Files to Read First, Risk Flags, TODO List

### Community 837 - "Issue #659: quick-note:https://github.com/nex-agi/Nex-N2"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #659: quick-note:https://github.com/nex-agi/Nex-N2, Implementation Prompt, Issue #659: quick-note:https://github.com/nex-agi/Nex-N2, Relevant Files to Read First, Risk Flags, TODO List

### Community 838 - "Issue #660: quick-note:https://github.com/getsentry/sentry-for-ai"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #660: quick-note:https://github.com/getsentry/sentry-for-ai, Implementation Prompt, Issue #660: quick-note:https://github.com/getsentry/sentry-for-ai, Relevant Files to Read First, Risk Flags, TODO List

### Community 839 - "Issue #661: quick-note:https://github.com/XiaomiMiMo/MiMo-Code"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #661: quick-note:https://github.com/XiaomiMiMo/MiMo-Code, Implementation Prompt, Issue #661: quick-note:https://github.com/XiaomiMiMo/MiMo-Code, Relevant Files to Read First, Risk Flags, TODO List

### Community 840 - "Issue #664: quick-note:https://github.com/Grominet95/jarvis-OS"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #664: quick-note:https://github.com/Grominet95/jarvis-OS, Implementation Prompt, Issue #664: quick-note:https://github.com/Grominet95/jarvis-OS, Relevant Files to Read First, Risk Flags, TODO List

### Community 841 - "Issue #666: quick-note:https://github.com/porokka/jarvis-os"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #666: quick-note:https://github.com/porokka/jarvis-os, Implementation Prompt, Issue #666: quick-note:https://github.com/porokka/jarvis-os, Relevant Files to Read First, Risk Flags, TODO List

### Community 842 - "Issue #670: quick-note:https://github.com/perplexityai/bumblebee"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #670: quick-note:https://github.com/perplexityai/bumblebee, Implementation Prompt, Issue #670: quick-note:https://github.com/perplexityai/bumblebee, Relevant Files to Read First, Risk Flags, TODO List

### Community 843 - "Issue #672: quick-note:https://github.com/Chachamaru127/claude-code-harness"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #672: quick-note:https://github.com/Chachamaru127/claude-code-harness, Implementation Prompt, Issue #672: quick-note:https://github.com/Chachamaru127/claude-code-harness, Relevant Files to Read First, Risk Flags, TODO List

### Community 844 - "Issue #676: quick-note:https://github.com/WeiboAI/VibeThinker"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #676: quick-note:https://github.com/WeiboAI/VibeThinker, Implementation Prompt, Issue #676: quick-note:https://github.com/WeiboAI/VibeThinker, Relevant Files to Read First, Risk Flags, TODO List

### Community 845 - "Issue #820: quick-note:https://github.com/cobusgreyling/loop-engineering"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #820: quick-note:https://github.com/cobusgreyling/loop-engineering, Implementation Prompt, Issue #820: quick-note:https://github.com/cobusgreyling/loop-engineering, Relevant Files to Read First, Risk Flags, TODO List

### Community 846 - "Positional Encoding Internals"
Cohesion: 0.25
Nodes (7): ALiBi (Attention with Linear Biases), Comparison, Learned Positional Embeddings, Positional Encoding Internals, RoPE Scaling for Long Contexts, Rotary Positional Embedding (RoPE), Sinusoidal Positional Encoding (Original Transformer)

### Community 847 - "TOP 6 — Highest-ROI Items (Validated by Opus Research Agent)"
Cohesion: 0.25
Nodes (8): ★1 — 3-Phase Context-Pruner Middleware [P0] [CBF], ★2 — Specialized Sub-Agents with Per-Role Cheap Models [P0] [CBF + HRM], ★3 — Reasoning Token Budget + Toggle [P0] [NVD], ★4 — Skill/Procedural Memory (agentskills.io compatible) [P1] [HRM], ★5 — Sandboxed Agent Execution (E2B / Docker micro-VM) [P1] [CHM] ✅ Delivered 2026-07-04, ★6 — Cost Analytics + FTS5 Shared Memory + Agent Constitution [P1] [AOS], ★7 — Adaptive Loop Halting (Early Exit on High Confidence) [P1] [MYT + HRM], TOP 6 — Highest-ROI Items (Validated by Opus Research Agent)

### Community 848 - "SECTION A — Agent Efficiency (Hermes / AOS / MYT)"
Cohesion: 0.25
Nodes (8): A1 — Hermes ChatML Prompt Format for Tool Calling [P0] [HRM], A2 — Multi-Hop Reasoning Chain (ReAct / Tree-of-Thought) [P0] [HRM], A3 — Agent Capability Registry + Dynamic Tool Discovery [P1] [AOS], A4 — Async Task Queue with Priority and Backpressure [P1] [AOS], A5 — Inter-Agent Message Bus [P1] [AOS / MYT], A6 — Shared Blackboard Memory for Swarm Agents [P1] [MYT], A7 — Agent Self-Improvement Loop [P2] [HRM / AOS], SECTION A — Agent Efficiency (Hermes / AOS / MYT)

### Community 849 - "SECTION C — Direct Chat Improvements (CBF / HRM)"
Cohesion: 0.25
Nodes (8): C1 — Structured Output / JSON Mode [P0] [CBF / HRM], C2 — Function Calling / Tool Use (OpenAI-Compatible) [P0] [CBF / HRM], C3 — Streaming with Proper Delta Reconstruction [P1] [CBF], C4 — Chat History Persistence + Retrieval [P1] [AOS / HRM], C5 — Context Window Management + Smart Truncation [P1] [CBF / HRM], C6 — Prompt Caching (Anthropic-Compatible) [P1] [HRM], C7 — Embeddings Pipeline + Vector Search [P2] [AOS / CBF], SECTION C — Direct Chat Improvements (CBF / HRM)

### Community 850 - "Runbook — Instance Activation"
Cohesion: 0.25
Nodes (7): Option A — disable the gate (self-hosted), Option B — self-mint a signed code with your own key, Option C — request a code (downstream user), Runbook — Instance Activation, Security notes, TL;DR — you are blocked at the activation screen, Why activation exists

### Community 851 - "Prime Agent Runtime"
Cohesion: 0.25
Nodes (8): Configuration, Deploying on Render, Installation, Prime Agent Runtime, `PRIME_AGENT_TRUST_WORKSPACE`, Routing LLM traffic through our proxy, Verifying, What the adapter drives

### Community 852 - "PULL_REQUEST_TEMPLATE.md"
Cohesion: 0.25
Nodes (7): Changelog, Changes, Council Review (for larger PRs), Related, Risky Module Review, Summary, Testing

### Community 853 - "fetch_url.py"
Cohesion: 0.43
Nodes (7): extract_real_url(), fetch(), main(), meaningful(), Drop site navigation chrome and repeated nav blocks from stripped text. A fetch…, strip_boilerplate(), strip_html()

### Community 854 - "Event"
Cohesion: 0.32
Nodes (7): Event, publish(), packages/events/bus.py — In-process event bus. Loosely couples components via…, An event published on the bus., Subscribe to an event type., Publish an event to all subscribers., subscribe()

### Community 855 - "capture_screens.py"
Cohesion: 0.39
Nodes (7): Popen, _capture(), _login(), main(), Launch the local uvicorn server (activated, sqlite, loops off) for capture., _start_server(), _wait_up()

### Community 856 - "Prompt Library"
Cohesion: 0.25
Nodes (8): Agents, Commands, How This Library Is Maintained, Philosophy, Prompt Library, Skills, Transparency, What Is This?

### Community 857 - "CLAUDE.md — router/"
Cohesion: 0.25
Nodes (7): Adding a New Model, Adding a New Task Category, CLAUDE.md — router/, Environment Variables, Invariants — Do Not Break, Testing, What This Package Does

### Community 858 - "crispy_burn_in.py"
Cohesion: 0.36
Nodes (7): evaluate_burn_in(), fetch_status_json(), main(), Any, scripts/crispy_burn_in.py — Evaluate CRISPY burn-in criteria for promotion.…, Fetch /api/autonomy/status and return the parsed JSON., Evaluate the burn-in criteria against a ``crispy_run_history`` payload. Returns…

### Community 859 - "run_patched_colibri.py"
Cohesion: 0.36
Nodes (7): _exit_watch_delay(), main(), _patched_popen(), scripts/run_patched_colibri.py Pre-launch wrapper for JustVugg/colibri…, Resolve the COLIBRI_PATCH_EXIT_WATCH delay in seconds, clamped to [0, 60].…, Intercept JustVugg Engine -> glm.exe Popen and forward outer argv. Upstream…, _resolve_target()

### Community 860 - "SessionMemory"
Cohesion: 0.25
Nodes (5): Any, Managed Agents Dreams — session memory and dream consolidation for managed…, An individual memory snapshot from an agent session., Record a new session memory for this agent., SessionMemory

### Community 861 - "test_compose_and_coordinate_api.py"
Cohesion: 0.36
Nodes (5): _auth_override(), AuthContext, test_coordinate_dependency_aware_tasks_block_missing_dependencies(), test_coordinate_dependency_aware_tasks_succeed_with_dependencies(), test_coordinate_legacy_workers_flow_remains_backward_compatible()

### Community 863 - "test_local_brain_router_smoke.py"
Cohesion: 0.25
Nodes (7): Smoke test: backend/local_brain_router is mounted on the public FastAPI app.…, Importing backend.server.app must not raise AttributeError or NameError., The /api/local-brain/state GET route must be reachable via the FastAPI app.…, The local_brain_router symbol MUST be importable + prefixed correctly. Quick…, test_backend_server_app_loads_without_attributeerror(), test_local_brain_router_module_is_wired(), test_local_brain_state_route_is_mounted_on_public_app()

### Community 864 - "test_ping.py"
Cohesion: 0.39
Nodes (7): client(), TestClient, Tests for the /api/ping health endpoint (no auth required)., test_ping_no_auth_required(), test_ping_response_shape(), test_ping_returns_ok(), test_ping_timestamp_is_iso()

### Community 865 - "TestRunCoroSync"
Cohesion: 0.29
Nodes (5): asyncio, fetch_research_alerts used asyncio.run() to await TrendWatcher().fetch(), which…, The exact scenario that crashed before the fix: called from code that is itself…, End-to-end: fetch_research_alerts() itself must not raise the 'asyncio.run()…, TestRunCoroSync

### Community 866 - "test_provider_models_db_outage.py"
Cohesion: 0.25
Nodes (7): tests/test_provider_models_db_outage.py — GET /api/providers/{id}/models…, A DB exception during the provider lookup must not surface as a 500., A catalog provider (unified BrainConfig) with no legacy `providers` row must…, A provider_id absent from both Mongo and the predefined catalog is a genuine…, test_provider_models_falls_back_on_db_outage(), test_provider_models_truly_unknown_provider_still_404s(), test_provider_models_unregistered_provider_uses_predefined_catalog()

### Community 867 - "test_runtimes_health_endpoint.py"
Cohesion: 0.25
Nodes (7): hermes_only_manager(), tests/test_runtimes_health_endpoint.py — N2 acceptance: GET /runtimes/health…, Build a RuntimeManager with only internal_agent + Hermes registered. Mirrors…, GET /runtimes/health must include a `hermes` entry when the adapter is…, End-to-end (router level): GET /runtimes/health returns JSON with a `health`…, test_runtimes_health_endpoint_returns_hermes_via_testclient(), test_runtimes_health_includes_hermes_entry()

### Community 868 - "start_in_process"
Cohesion: 0.25
Nodes (8): start_in_process must be a safe no-op in the test environment (conftest sets…, Flag on but LiveKit env absent → logged no-op, never raises., test_start_in_process_noop_under_testing(), test_start_in_process_noop_when_unconfigured(), Start the voice worker in a daemon thread inside this process. Called by the…, Thread body: run the LiveKit agents server on a dedicated event loop., _run_worker_thread(), start_in_process()

### Community 870 - "test_serve_spa_prefixes.py"
Cohesion: 0.36
Nodes (7): _prefixes(), Behavioral: GET to a path that has NO upstream handler but IS in the protected…, SPA_PROTECTED_PREFIXES must be exposed at module scope (not inside an if-block)…, test_legitimate_spa_paths_are_not_blocked(), test_protected_paths_are_covered_by_prefix_tuple(), test_serve_spa_returns_non_html_for_protected_orphan_path(), test_spa_protected_prefixes_is_module_level_constant()

### Community 871 - "test_task_store_fails_loud_in_production.py"
Cohesion: 0.25
Nodes (7): fresh_store_module(), Regression: prevent silent TaskStore in-memory fallback in production. The…, Force a fresh import of tasks.store so module-level state is clean., With TESTING unset (production), TaskStore(db=None) MUST raise., With TESTING=true (CI), TaskStore(db=None) MUST allow in-memory fallback., test_task_store_allows_inmemory_when_testing(), test_task_store_raises_in_production()

### Community 872 - "dry_clone_repo"
Cohesion: 0.36
Nodes (5): test_dry_clone_repo_handles_missing_url(), test_dry_clone_repo_handles_subprocess_failure(), dry_clone_repo(), Validate repository access by performing a shallow, no-checkout git clone and…, Attempt a shallow, non-checkout clone into a temporary directory to validate…

### Community 873 - "TOOLS.md — Available Tools for AI Agents"
Cohesion: 0.25
Nodes (7): AI Runner Tools, API Endpoints (when proxy is running), File Tools, OpenClaw Integration, Shell / Process Tools, Skills (invoke via CLAUDE.md instructions), TOOLS.md — Available Tools for AI Agents

### Community 874 - "Task"
Cohesion: 0.33
Nodes (4): Path, Score the agent's final answer. Returns (success, score)., A fully-specified evaluation task. Fields mirror the OpenHarness task schema so…, Task

### Community 876 - "Full-Output Enforcement"
Cohesion: 0.29
Nodes (6): Banned Output Patterns, Baseline, Execution Process, Full-Output Enforcement, Handling Long Outputs, Quick Check

### Community 877 - "summarise.sh"
Cohesion: 0.48
Nodes (5): bottom(), divider(), row(), summarise.sh script, top()

### Community 878 - "updater.py"
Cohesion: 0.43
Nodes (6): _extract_unreleased_body(), _insert(), main(), Insert the Maintenance changelog section at the end of the [Unreleased] block.…, Return (body_start, body_end_exclusive, body) for the [Unreleased] block., _read_template()

### Community 879 - "ModelRegistry"
Cohesion: 0.29
Nodes (4): ModelRegistry, A centralized registry for available LLM models and their metadata. This class…, Returns a list of all registered models metadata., Retrieves a specific model's metadata by its name (case-insensitive). Returns…

### Community 880 - "AI Engineering Insights Skill"
Cohesion: 0.29
Nodes (6): AI Engineering Insights Skill, Integration Points, Key Design Choices, Module: `agents/ai_insights.py`, References, What's Unique About the DX Report

### Community 881 - "Skill: hybrid-reasoning (Hybrid AI)"
Cohesion: 0.29
Nodes (6): Branch, Components, Purpose, Quick Start, Skill: hybrid-reasoning (Hybrid AI), Testing

### Community 882 - "Karpathy Guidelines Skill"
Cohesion: 0.29
Nodes (6): 1. Think Before Coding, 2. Simplicity First, 3. Surgical Changes, 4. Goal-Driven Execution, Integration points in this repo, Karpathy Guidelines Skill

### Community 883 - "Skill: Managed Agents Dreams"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: Managed Agents Dreams, Testing, Usage

### Community 884 - "Skill: Multi-Agent Coordinator"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: Multi-Agent Coordinator, Testing, Usage

### Community 885 - "Skill: Obsidian Knowledge Graph"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: Obsidian Knowledge Graph, Testing, Usage

### Community 886 - "Multi-Agent Research Coordinator Skill"
Cohesion: 0.29
Nodes (6): Default Plan Shape, Module: `agents/research_coordinator.py`, Multi-Agent Research Coordinator Skill, Quick-Note Issue: #238, Roles, What's Unique

### Community 887 - "Skill: SuperClaude Slash Commands"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: SuperClaude Slash Commands, Testing, Usage

### Community 888 - "Skill: SuperClaude Workflow Engine"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: SuperClaude Workflow Engine, Testing, Usage

### Community 889 - "Active Task Tracker"
Cohesion: 0.29
Nodes (6): Active Task Tracker, Bug Log, Current Sprint Tasks, Roadmap Items (from `docs/roadmap-killer-todos.md`), Session Log, Status Key

### Community 890 - "_AllSignatures"
Cohesion: 0.29
Nodes (5): dict, set, _AllSignatures, _AnyText, A mapping that accepts any entry text for any signature.

### Community 891 - "ADR-006: Strangler Fig migration with backward-compat shims"
Cohesion: 0.29
Nodes (6): ADR-006: Strangler Fig migration with backward-compat shims, Consequences, Context, Decision, Examples, Migration path

### Community 892 - "claude-mem Plugin — Persistent Memory for All Sessions"
Cohesion: 0.29
Nodes (6): claude-mem Plugin — Persistent Memory for All Sessions, Enabling it elsewhere, How it's wired, Notes, Scope and limits, Why the source is pinned (`ref` + `sha`)

### Community 893 - "Implementation plan + TO-DO (check off as you go)"
Cohesion: 0.29
Nodes (7): Implementation plan + TO-DO (check off as you go), Phase 1 — Stop the bleeding + paid kill switch (do first, ship alone if needed), Phase 2 — Per-surface assignment in the UI (the "one place"), Phase 3 — Persistence hardening (issues #537, #524), Phase 4 — Onboarding fixes (issues #593, #619; PR #623), Phase 5 — Reliability for hands-off autonomy (issue #522) [larger; may split to own PR], Phase 6 — Green the tests + housekeeping

### Community 894 - "Topics Covered"
Cohesion: 0.29
Nodes (7): 1. Architecture, 2. Tokenization, 3. Training, 4. Inference, 5. Embeddings, LLM Internals, Topics Covered

### Community 895 - "LLM Router — migration guide"
Cohesion: 0.29
Nodes (7): Adding the config files, Gateway mode, LLM Router — migration guide, Migrating a caller to the router directly, Rollback checklist, What changes for callers, What is not migrated

### Community 896 - "Cloudflare = the real working app"
Cohesion: 0.29
Nodes (6): Backend (Render), Cloudflare dashboard settings to verify, Cloudflare = the real working app, How it works, Notes, Verify after deploy

### Community 897 - "production"
Cohesion: 0.29
Nodes (7): browserslist, development, production, >0.2%, last 1 chrome version, not dead, not op_mini all

### Community 898 - "launch-claude-code.sh"
Cohesion: 0.43
Nodes (6): ANTHROPIC_API_KEY, ANTHROPIC_MODEL, log_error(), log_header(), log_success(), launch-claude-code.sh script

### Community 900 - "PRD — README Marketing Refresh"
Cohesion: 0.29
Nodes (6): Backlog / Nice-to-Have, Files Touched, Original Problem Statement, PRD — README Marketing Refresh, User Decisions, What Was Done — 2026-04-27

### Community 901 - "get_control"
Cohesion: 0.29
Nodes (7): Of *changed*, the keys whose readers only see the new value after a restart., _restart_required(), get_control(), The spec for *key*, or ``None`` when it is not operator-controllable., A runtime an operator cannot pick from the dropdown is unreachable., test_restart_required_lists_only_non_live_controls(), test_runtime_choices_cover_every_registered_adapter_id()

### Community 902 - "check_changelog_parity.py"
Cohesion: 0.43
Nodes (6): _blocks(), main(), normalize_text(), scripts/check_changelog_parity.py CI guard for the changelog mirror. Closes the…, Return a list of human-readable corruption issues in *content*. Detects (1) git…, scan_corruption()

### Community 903 - "e2e_smoke.py"
Cohesion: 0.57
Nodes (5): _chat(), check(), _health(), _models(), _req()

### Community 904 - "BackgroundServices"
Cohesion: 0.38
Nodes (4): BackgroundServices, Handle returned by ``start_background_services`` — call ``stop()`` on shutdown., Cancel the boot refresh if it is still fetching at shutdown., Shut the in-process Hermes down so port 8100 is released. Uvicorn's own…

### Community 905 - "task_runner.py"
Cohesion: 0.33
Nodes (6): check_health(), Submit a task to the agent planner., Submit a simple task via the tasks API., Check if the proxy is running., submit_simple_task(), submit_task()

### Community 906 - "client"
Cohesion: 0.29
Nodes (7): auth_headers(), client(), TestClient, TestClient for the backend FastAPI app (one per module for speed)., Login once and return auth headers for the entire module., admin_jwt(), Module-scoped so we log in once and reuse the JWT across the test.

### Community 907 - "TestDashboard"
Cohesion: 0.29
Nodes (4): Run fn() and report any critical console errors., Dashboard page — stats, activity, navigation., TestDashboard, with_console_check()

### Community 908 - "test_daily_2026_06_14.py"
Cohesion: 0.38
Nodes (6): Regression tests for daily-2026-06-14 improvements. Anthropic retires the…, ci-failure-autofix.yml must call the Anthropic API with claude-sonnet-4-6, as…, No GitHub Actions workflow or CI script should reference a retired Claude 4…, _read(), test_ci_autofix_workflow_uses_sonnet_4_6(), test_no_retired_claude_4_model_ids_in_workflows_or_scripts()

### Community 909 - "test_doctor_coding_brain.py"
Cohesion: 0.38
Nodes (6): client(), _coding_brain_check(), tests/test_doctor_coding_brain.py Surfaces the North Mini Code coding-brain…, With NORTH_MINI_CODE_DEFAULT off, the check warns and says so., test_coding_brain_check_reflects_flag_off(), test_doctor_includes_coding_brain_check()

### Community 910 - "test_domain_specialists.py"
Cohesion: 0.29
Nodes (5): parametrize, tests/test_domain_specialists.py — business/domain specialist coverage. Agency…, The system→family map sends commerce/business systems to domain families., test_commerce_systems_route_to_domain_specialists(), test_family_is_fully_specified()

### Community 911 - "TestGithubTokenSQLiteRegression"
Cohesion: 0.38
Nodes (4): MonkeyPatch, TestClient, Regression test for PUT/DELETE /api/github/token returning 500 for SQLite-…, TestGithubTokenSQLiteRegression

### Community 912 - "test_schedule_store_create_index_options.py"
Cohesion: 0.48
Nodes (6): _install_pymongo_stub(), Regression tests for the MongoDB index creation in ScheduleStore. Verifies the…, Stub pymongo so ``ScheduleStore.__init__`` resolves to ``fake_collection``.…, _restore_pymongo(), test_schedule_store_creates_index_with_background_true(), test_schedule_store_skips_index_already_present()

### Community 914 - "TestActiveStrategy"
Cohesion: 0.29
Nodes (3): parametrize, A typo must not silently pick some other distribution., TestActiveStrategy

### Community 915 - "/fix-bug — Bug Fix Agent"
Cohesion: 0.33
Nodes (5): Escalation, /fix-bug — Bug Fix Agent, Process, Rules, Usage

### Community 916 - "Command: /plan"
Cohesion: 0.33
Nodes (5): Command: /plan, References, Usage, What It Does, When to Use

### Community 917 - "pre-commit"
Cohesion: 0.60
Nodes (5): pre-commit script, _error(), _head(), _info(), _warn()

### Community 918 - "Skill: browserbase-fetch — Lightweight Web Fetch"
Cohesion: 0.33
Nodes (5): Checking the platform health, Python snippet, Setup, Skill: browserbase-fetch — Lightweight Web Fetch, When to use vs browser

### Community 919 - "Twitter Insights — Issue #228"
Cohesion: 0.33
Nodes (5): Action Items, Key Observations, References, Summary, Twitter Insights — Issue #228

### Community 920 - "Twitter Insights — Issue #231"
Cohesion: 0.33
Nodes (5): Action Items, Key Observations, References, Summary, Twitter Insights — Issue #231

### Community 921 - "OpenAI Codex CLI — Local LLM Server Config"
Cohesion: 0.33
Nodes (5): Codex Config File (`~/.codex/config.yaml`), Notes, OpenAI Codex CLI — Local LLM Server Config, Recommended Models, Setup

### Community 922 - "ADR-001: Adopt packages/ directory structure"
Cohesion: 0.33
Nodes (5): ADR-001: Adopt packages/ directory structure, Consequences, Context, Decision, Status

### Community 923 - "ADR-002: Centralize configuration in packages/config/"
Cohesion: 0.33
Nodes (5): ADR-002: Centralize configuration in packages/config/, Consequences, Context, Decision, Status

### Community 924 - "ADR-003: Provider abstraction with unified interface"
Cohesion: 0.33
Nodes (5): ADR-003: Provider abstraction with unified interface, Consequences, Context, Decision, Status

### Community 925 - "ADR-004: Event bus for loosely coupled communication"
Cohesion: 0.33
Nodes (5): ADR-004: Event bus for loosely coupled communication, Consequences, Context, Decision, Status

### Community 926 - "ADR-005: Merge Hermes into the main backend service"
Cohesion: 0.33
Nodes (5): ADR-005: Merge Hermes into the main backend service, Consequences, Context, Decision, Status

### Community 927 - "ADR-007: Storage backend duck-typing over formal ABC"
Cohesion: 0.33
Nodes (5): ADR-007: Storage backend duck-typing over formal ABC, Consequences, Context, Decision, Rationale

### Community 928 - "Phases"
Cohesion: 0.33
Nodes (6): Phase 0 — `RepoConnection` plumbing + delivery-policy detection, Phase 1 — Plan-PR → Implementation  *(highest leverage; closes the live gap)*, Phase 2 — Review-comment resolution (Codex / CodeRabbit), Phase 3 — Quality gate + policy-conformant landing, Phase 4 — Monitor & regression guard, Phases

### Community 929 - "5. The five autonomous loops"
Cohesion: 0.33
Nodes (6): 5. The five autonomous loops, Loop 1 — Self-heal from logs *(closed loop)*, Loop 2 — Feature generation, Loop 3 — Agentic SDLC (the golden path), Loop 4 — Trends contextually applied, Loop 5 — Per-onboarded-site autonomy

### Community 930 - "Master Goal Prompt — Autonomous Agency CEO"
Cohesion: 0.33
Nodes (6): Cadence & stop conditions, First-run bootstrap, Hard constraints, Master Goal Prompt — Autonomous Agency CEO, Mission, The gate contract (Telegram human-in-the-loop)

### Community 931 - "Agency Core — Operational Knowledge (verified live, 2026-06-10/11)"
Cohesion: 0.33
Nodes (5): Agency Core — Operational Knowledge (verified live, 2026-06-10/11), Architecture truths, Open backlog (epic #504), Pros of linking the GitHub repo (vs running unlinked), Runbooks

### Community 932 - "Pre-Mortem Analysis: Agency Core autonomy story (Cloudflare deployment)"
Cohesion: 0.33
Nodes (5): Elephants, named, Pre-Mortem Analysis: Agency Core autonomy story (Cloudflare deployment), Risk Registry, Summary, What was already fixed during this pre-mortem

### Community 933 - "SECTION B — NVIDIA / Cloud Model Integration (Nemotron / NVD)"
Cohesion: 0.33
Nodes (6): B1 — Nemotron Reward Model for Agent Step Scoring [P0] [NVD], B2 — SteerLM / RLHF-Style Steering for Local Models [P1] [NVD], B3 — Synthetic Training Data Generation Pipeline [P1] [NVD], B4 — NeMo Guardrails Integration [P1] [NVD], B5 — NIM API Connection Pooling + Circuit Breaker [P1] [NVD], SECTION B — NVIDIA / Cloud Model Integration (Nemotron / NVD)

### Community 934 - "SECTION D — Deployment & Infrastructure (CHM / NVD)"
Cohesion: 0.33
Nodes (6): D1 — Helm Chart for Kubernetes Deployment [P1] [CHM], D2 — Docker Compose Production Stack [P1] [CHM], D3 — OpenTelemetry Distributed Tracing [P1] [NVD / CHM], D4 — Horizontal Scaling with Redis State Backend [P2] [CHM / AOS], D5 — Model Auto-Management (Pull, Warm, Evict) [P2] [NVD], SECTION D — Deployment & Infrastructure (CHM / NVD)

### Community 936 - "resolve_hermes_base_url"
Cohesion: 0.47
Nodes (5): Resolve the base URL of the agency's own Hermes server. Precedence:…, resolve_hermes_base_url(), tests/test_hermes_base_url.py — resolve_hermes_base_url precedence., test_default_when_unset(), test_env_wins()

### Community 937 - "apply_phase1_changes.py"
Cohesion: 0.33
Nodes (5): apply_backend_change(), apply_workflow_change(), Apply Phase 1 paid-provider kill switch changes to backend/server.py and…, Insert provider policy endpoints before @app.get('/api/models/catalog')., Modify _resolve_brain_provider to read allow_paid from the durable policy.

### Community 938 - "_replace"
Cohesion: 0.40
Nodes (5): main(), Path, Regex-replace ``pattern`` with ``repl`` in ``path``; return the match count., Bump the version across all version-bearing files; fail fast if any are missed., _replace()

### Community 939 - "check_doc_images.py"
Cohesion: 0.60
Nodes (5): check_broken_links(), check_gallery_sync(), find_duplicate_images(), _local_refs(), main()

### Community 940 - "gen_screenshots.py"
Cohesion: 0.47
Nodes (5): main(), out_path(), Path, Generate Langfuse and Telegram mockup screenshots for documentation., save_html_screenshot()

### Community 941 - "gen_v4_screenshots.py"
Cohesion: 0.60
Nodes (5): build_screens(), page(), Generate v4 UI screenshots for the README using HTML mockups + system…, shot(), sidebar()

### Community 943 - "setup-claude-code.sh script"
Cohesion: 0.60
Nodes (5): log_error(), log_info(), log_success(), print_header(), setup-claude-code.sh script

### Community 947 - "PhaseSequenceError"
Cohesion: 0.33
Nodes (4): TestPhaseSequenceError, PhaseSequenceError, Exception, Raised when a phase is attempted out of order.

### Community 948 - "test_generate_context_standing_instructions.py"
Cohesion: 0.40
Nodes (5): _load_module(), Regression test: autonomous issue-context generation must not silently truncate…, Sanity check on the fixture assumption this test relies on., test_claude_md_standing_instructions_present_past_4000_chars(), test_load_codebase_context_includes_standing_instructions()

### Community 949 - "TestCitationBinding"
Cohesion: 0.47
Nodes (3): A known signature must not license arbitrary text., The attack the signature check alone did not stop. A workspace with a…, TestCitationBinding

### Community 950 - "_auth_headers"
Cohesion: 0.73
Nodes (5): _auth_headers(), TestClient, test_agent_profile_api_preserves_ui_fields(), test_backend_server_exposes_observability_savings_and_usage(), test_backend_server_exposes_schedules_routes()

### Community 951 - "_normalize_dockerfile"
Cohesion: 0.33
Nodes (6): _normalize_dockerfile(), Parse a Dockerfile into a list of active instruction lines. Strips comment…, Dockerfile.backend must COPY voice/ (server-side TTS + LiveKit token endpoints…, Dockerfile.voice is the standalone home of the heavy voice deps: it must…, test_dockerfile_ships_voice_package(), test_dockerfile_voice_builds_the_worker()

### Community 954 - "webui/commands.py"
Cohesion: 0.47
Nodes (5): Any, Path, run_command(), _safe_allowlist(), validate_command()

### Community 955 - "harness.py"
Cohesion: 0.40
Nodes (3): EvalResult, Evaluation harness – runs an agent against a Task, records the Trajectory,…, Outcome of running one task through the harness.

### Community 957 - "loops_overview"
Cohesion: 0.50
Nodes (4): loops_overview(), Full Loop Engineering fleet view for the UI: the catalogued loops plus the…, tests/test_loops_api.py — contract test for GET /api/loops. The Loops screen…, test_loops_overview_returns_fleet_and_readiness()

### Community 958 - "/arch-review — Architecture Agent"
Cohesion: 0.40
Nodes (4): /arch-review — Architecture Agent, Key Architectural Principles, Steps, When to use

### Community 959 - "/devops-check — DevOps Agent"
Cohesion: 0.40
Nodes (4): Deployment Checklist, /devops-check — DevOps Agent, Steps, When to use

### Community 960 - "/docs-update — Documentation Agent"
Cohesion: 0.40
Nodes (4): /docs-update — Documentation Agent, Documentation Standards, Steps, When to use

### Community 961 - "/qa-check — QA Agent"
Cohesion: 0.40
Nodes (4): /qa-check — QA Agent, Steps, What NOT to do, When to use

### Community 962 - "Command: /review"
Cohesion: 0.40
Nodes (4): Command: /review, References, Usage, What It Does

### Community 963 - "/security-audit — Security Agent"
Cohesion: 0.40
Nodes (4): Escalation, /security-audit — Security Agent, Steps, When to use

### Community 964 - "pre-push"
Cohesion: 0.70
Nodes (4): pre-push script, _error(), _head(), _info()

### Community 965 - "Skill: browserbase-search — Structured Web Search"
Cohesion: 0.40
Nodes (4): Best practice: search → fetch → browse, Python snippet, Setup, Skill: browserbase-search — Structured Web Search

### Community 966 - "Issue #230 — DUPLICATE"
Cohesion: 0.40
Nodes (4): Actions Taken, Issue #230 — DUPLICATE, References, Resolution

### Community 968 - "Agent job lifecycle"
Cohesion: 0.40
Nodes (4): Agent job lifecycle, API, Progress phases, States

### Community 969 - "Docker (local or any container host)"
Cohesion: 0.40
Nodes (4): Build, Docker (local or any container host), Provider configuration (recommended for cloud), Run (minimal)

### Community 970 - "Variants"
Cohesion: 0.40
Nodes (5): Flash Attention, Grouped Query Attention (GQA), Multi-Query Attention (MQA), Sliding Window Attention, Variants

### Community 971 - "Rollout"
Cohesion: 0.40
Nodes (5): 1. Verify the router sees your providers, 2. Enable on one instance, 3. Watch for a few hours, 4. Roll out or roll back, Rollout

### Community 972 - "SECTION E — Autonomy & Self-Healing (AOS / MYT / ECC)"
Cohesion: 0.40
Nodes (5): E1 — Cross-Harness Routing (ECC Pattern) [P1] [ECC], E2 — Self-Healing Agent Loop (Detect + Repair Own Failures) [P1] [AOS / MYT], E3 — Autonomous Monitoring with Trend Watcher [P2] [AOS], E4 — Nightly Self-Evaluation + Regression Tests [P2] [HRM / AOS], SECTION E — Autonomy & Self-Healing (AOS / MYT / ECC)

### Community 973 - "SECTION F — Developer Experience (CBF / ECC)"
Cohesion: 0.40
Nodes (5): F1 — Codebuff-Style Precise Diff Application [P0] [CBF], F2 — MCP Server Exposing Proxy Capabilities [P1] [CBF / ECC], F3 — Local Dev Dashboard with Live Metrics [P2] [CBF / CHM], F4 — SDK / Client Library Generation [P2] [CBF], SECTION F — Developer Experience (CBF / ECC)

### Community 974 - "Runtime troubleshooting"
Cohesion: 0.40
Nodes (4): Agent mode timeout, Missing binary / task harness, Runtime troubleshooting, Workspace validation failures

### Community 975 - "knowledgeGraphTab.test.js"
Cohesion: 0.40
Nodes (4): { describe, test, expect }, fs, path, src

### Community 976 - "loginFlowNoTimeout.test.js"
Cohesion: 0.40
Nodes (4): apiSource, { describe, test, expect }, fs, path

### Community 977 - "test_company_stale_id_recovery.test.js"
Cohesion: 0.40
Nodes (4): { describe, test, expect }, fs, path, src

### Community 978 - "worker_no_cache.test.js"
Cohesion: 0.40
Nodes (4): { describe, test, expect }, fs, path, workerSource

### Community 979 - "scripts/agile_ceremonies.py"
Cohesion: 0.60
Nodes (4): _load(), main(), ModuleType, _write_summary()

### Community 980 - ".chat"
Cohesion: 0.40
Nodes (3): Any, Send a chat completion request., Stream a chat completion response.

### Community 981 - "governance/__init__.py"
Cohesion: 0.40
Nodes (3): __getattr__(), Any, packages/governance — agent identity, policy, approvals, audit, sandboxes. The…

### Community 982 - "Prompt Library Changelog"
Cohesion: 0.40
Nodes (4): Added, Format, Prompt Library Changelog, [Unreleased]

### Community 983 - "_add_colibri_shim_changelog_entry.py"
Cohesion: 0.50
Nodes (4): main(), _normalise_crlf(), Insert a single new [Unreleased] / ### Added bullet into BOTH changelogs.…, Force LF on write (parity script tolerates either, but a stray CRLF introduced…

### Community 984 - "build_llama_cpp.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), W(), Warn()

### Community 985 - "download_glm52_weights.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), Warn(), W()

### Community 986 - "download_glm52_weights.sh script"
Cohesion: 0.70
Nodes (4): download_glm52_weights.sh script, fail(), ok(), warn()

### Community 987 - "_fetch_pytest_failures.py"
Cohesion: 0.50
Nodes (4): _gh_json(), main(), Pull the python-test failure log via gh run view --log and print the failing-…, Run a gh CLI call and parse its JSON stdout. Returns (parsed | None, stderr).

### Community 988 - "setup_colibri.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), Warn(), W()

### Community 989 - "setup_colibri.sh script"
Cohesion: 0.70
Nodes (4): setup_colibri.sh script, fail(), ok(), warn()

### Community 990 - "status_colibri_server.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), W(), Warn()

### Community 991 - ".get_bound_skills"
Cohesion: 0.40
Nodes (3): Any, Get statistics for specialists in a company. Args: company_id: Company ID…, Get the details of skills bound to a specialist. Args: specialist_id:…

### Community 993 - "TestMobileNavigation"
Cohesion: 0.40
Nodes (3): Mobile-specific: hamburger menu, responsive layout., Verify key pages load in mobile viewport., TestMobileNavigation

### Community 994 - "test_v5_screens_smoke.py"
Cohesion: 0.50
Nodes (3): _login(), E2E UI smoke test: every v5 screen renders without errors. This is the…, test_every_v5_screen_renders_without_errors()

### Community 995 - "test_agent_runtime_wrapper.py"
Cohesion: 0.70
Nodes (4): _load_agent_runtime_module(), test_wrapper_exposes_hermes_task_endpoints(), test_wrapper_exposes_opencode_run_endpoint(), test_wrapper_falls_back_to_installed_model()

### Community 998 - "worker/index.js"
Cohesion: 0.60
Nodes (4): fetch(), needsProxy(), PROXY_PREFIXES, scheduled()

### Community 999 - "recovery.py"
Cohesion: 0.67
Nodes (3): detect_secrets(), main(), Recover CHANGELOG.md from a Git merge conflict in its [Unreleased] block. Pre-…

### Community 1000 - "aider_config.sh"
Cohesion: 0.50
Nodes (3): OPENAI_API_BASE, OPENAI_API_KEY, aider_config.sh script

### Community 1003 - "providers.yaml"
Cohesion: 0.50
Nodes (4): Bulkhead sizing, Per-minute token budgets, providers.yaml, Tiers

### Community 1004 - "Credential Rotation Runbook"
Cohesion: 0.50
Nodes (3): Credential Rotation Runbook, Guardrails already in place, What to rotate (owner action, ~10 minutes)

### Community 1005 - "Runbook: `make doctor`"
Cohesion: 0.50
Nodes (3): Roadmap, Runbook: `make doctor`, What it checks and why

### Community 1006 - "render"
Cohesion: 0.50
Nodes (3): RENDER_API_KEY, docker, render

### Community 1007 - "scripts"
Cohesion: 0.50
Nodes (4): scripts, build, start, test

### Community 1008 - "_clean_director"
Cohesion: 0.50
Nodes (4): Clear director state and the cached strategy warnings (tests only)., reset(), _clean_director(), Reset the process singleton around every test.

### Community 1009 - "_resolve_default_executor_model"
Cohesion: 0.50
Nodes (3): Any, Resolve the default executor model via the catalog (UNIT 7). Was hardcoded to…, _resolve_default_executor_model()

### Community 1010 - "stop_colibri_server.ps1"
Cohesion: 0.83
Nodes (3): Fail(), Ok(), W()

### Community 1012 - "start_server.sh"
Cohesion: 0.50
Nodes (3): OLLAMA_HOST, OLLAMA_MODELS, start_server.sh script

### Community 1013 - "check_services"
Cohesion: 0.67
Nodes (3): check_services(), main(), Check if local services are running. Extends the original (proxy + Ollama)…

### Community 1022 - "test_no_exception_detail_leaks.py"
Cohesion: 0.50
Nodes (3): parametrize, tests/test_no_exception_detail_leaks.py — Guard against str(exc)/str(e) leaking…, test_no_raw_exception_detail_in_http_response()

### Community 1023 - "test_skills_route_order.py"
Cohesion: 0.67
Nodes (3): tests/test_skills_route_order.py — /api/company/skills must not be shadowed.…, _route_index(), test_static_skills_routes_precede_dynamic_company_id_route()

### Community 1024 - "github"
Cohesion: 0.50
Nodes (3): github, enabled, silent

### Community 1025 - "main"
Cohesion: 0.50
Nodes (4): main(), CLI entrypoint: ``python -m voice.sam_livekit_worker dev|start``., Fail fast with an actionable hint when optional deps are missing., _require_livekit_agents()

### Community 1048 - "test_the_reserve_is_bounded_when_read_from_the_environment"
Cohesion: 0.67
Nodes (3): parametrize, Read through the ENV, not the constant — that is where the bug lived.…, test_the_reserve_is_bounded_when_read_from_the_environment()

### Community 1049 - "test_direct_adapter_does_not_bypass"
Cohesion: 0.67
Nodes (3): skipif, Calling the adapter directly (the /runtimes/{id}/execute path) must stay gated:…, test_direct_adapter_does_not_bypass()

### Community 1050 - "test_mint_token_rejects_missing_args"
Cohesion: 0.67
Nodes (3): parametrize, Empty key/secret/identity/room must raise ValueError., test_mint_token_rejects_missing_args()

## Knowledge Gaps
- **3533 isolated node(s):** `duplicate.sh script`, `heartbeat.sh script`, `redact_secrets.sh script`, `docker`, `RENDER_API_KEY` (+3528 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **114 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_fixture()` connect `_fixture` to `ProviderConfig`, `TaskSpec`, `llm/router.py`, `ScheduledJob`, `FeatureMatrix`, `test_llm_router_strategies.py`, `test_operational_incidents.py`, `reap_expired_companies`, `AgentSessionStore`, `_resolve_push_token`, `test_autonomy_status.py`, `test_brain_failover_413.py`, `MCPUnavailableError`, `TaskStore`, `SelfHealingAgent`, `test_local_brain_state.py`, `services/background.py`, `TestChatHistoryStore`, `WorkflowRun`, `ImprovementLoop`, `test_phase5_doctor.py`, `MCPClient`, `KeyPool`, `test_llm_router_resilience.py`, `HermesAdapter`, `test_telegram_diag_endpoint.py`, `resolve_active_brain`, `test_unit8_model_catalog.py`, `KeyStore`, `brain_config.py`, `SeoAuditRequest`, `test_telegram_auto_approve.py`, `test_failover_client_shared.py`, `e2e/test_browser.py`, `TestGetCurrentTimeTool`, `Task`, `test_model_router.py`, `tasks/service.py`, `NotificationDispatcher`, `test_knowledge_sync.py`, `FailureCategory`, `test_startup_warmup.py`, `BrainWatchdog`, `workflow/api.py`, `enforcement.py`, `ResearchTask`, `brain_failover.py`, `_enable_filter`, `resolve_e2b_config`, `TestClient`, `test_ai_insights.py`, `resolve_identity`, `ModelRouter`, `ProceduralMemoryStore`, `test_openclaw_gateway.py`, `SecretRecord`, `test_colibri_brain_shim.py`, `seo_api.py`, `get_task_store`, `DetectedSystem`, `SeoFixer`, `test_new_features_e2e.py`, `test_control_plane_api.py`, `config.py`, `_Budget`, `test_context_rulebook.py`, `ArtifactStore`, `CEOSupervisor`, `test_doctor_service_token_check.py`, `test_provider_state_durability.py`, `test_sam_voice.py`, `_resolve_brain_provider`, `test_issue_intake.py`, `test_kimi_bridge_server.py`, `GoalRecord`, `ChatHistoryStore`, `test_telegram_freebuff.py`, `test_portfolio_intake.py`, `persist_plan_spec`, `test_agent_tool_governance.py`, `AgentProfile`, `test_agile_api.py`, `test_app_settings.py`, `test_e2b_task_wiring.py`, `OllamaCircuitBreaker`, `test_task_clarification.py`, `test_agent_free_brain.py`, `WorkflowBuildRequest`, `test_features_api.py`, `test_video_transcript.py`, `analyze_page`, `TrendWatcher`, `test_e2b_data_flow.py`, `test_trend_watcher.py`, `._check_permissions`, `TestEstimateTokensForMessages`, `AuditLog`, `TestClient`, `ContextPruner`, `OrchestratorQueue`, `test_persistent_memory.py`, `SpecEntry`, `IssueCategory`, `SecurityScanner`, `test_llm_router_e2e.py`, `test_platform_controls.py`, `TestSwarmRoleRouting`, `TestNormalizeResponseFormat`, `test_rate_limiter.py`, `CacheManager`, `test_mcp_governance.py`, `test_purge_backlog.py`, `test_freebuff_bot.py`, `test_scheduler_hydration_bounded.py`, `test_crispy_burn_in.py`, `test_provider_enable_disable.py`, `test_skill_registry_boot_refresh.py`, `isolated_telegram_config`, `ClaudeCodeAdapter`, `TestHarnessRegistry`, `test_ping.py`, `test_sam_livekit.py`, `test_service_token.py`, `test_runtimes_health_endpoint.py`, `test_task_store_fails_loud_in_production.py`, `test_regression.py`, `test_agency_fix.py`, `platform_controls_router.py`, `test_monitor_lib.py`, `test_v4_api.py`, `test_dashboard_cache.py`, `client`, `test_doctor_coding_brain.py`, `model_discovery.py`, `_resolve_user_github_token`, `allow_paid`, `test_llm_router_tpm.py`, `test_voice_pipeline.py`, `test_brain_patch_service_token.py`, `TestOrchestratorEndpointScoping`, `test_company_api.py`, `cost_tracker.py`, `_clean_director`, `SQLiteStore`, `test_shared_state.py`, `test_openclaw_endpoints.py`?**
  _High betweenness centrality (0.103) - this node is a cross-community bridge._
- **Why does `AgentRunner` connect `AgentRunner` to `ContextManager`, `loop.py`, `AgentScheduler`, `LocalWorkspace`, `backend/server.py`, `TaskSpec`, `proxy.py`, `test_agent_chat_integration.py`, `PortfolioManager`, `ReactScratchpad`, `AutonomyTracker`, `diagnostics.py`, `AgentSessionStore`, `StuckDetector`, `_resolve_push_token`, `Path`, `test_brain_failover_413.py`, `MCPUnavailableError`, `BackgroundAgent`, `_StubManager`, `ExecutionRequest`, `TestMCPServer`, `test_agent_runner.py`, `WorkspaceTools`, `WorkflowRun`, `MCPClient`, `test_agent_tool_governance.py`, `direct_chat.py`, `FreeBuffAgent`, `test_failover_client_shared.py`, `test_agent_free_brain.py`, `CEODispatcher`, `test_ceo_dispatcher.py`, `WorkflowBuildRequest`, `MultiAgentSwarm`, `TestGetCurrentTimeTool`, `test_empirical_verify.py`, `TestWorkspace`, `ContextPruner`, `test_governance_api.py`, `AdaptiveHalter`, `test_backend_server_features.py`, `GitHubTools`, `failover_client.py`, `TestZeroAttemptDiagnostics`, `TokenBudget`, `test_daily_automation_2026_07_11.py`, `_get_provider_policy`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Why does `LLMRequest` connect `LLMRequest` to `llm/router.py`, `test_llm_router_strategies.py`, `brain_failover.py`, `Usage`, `test_llm_router_tpm.py`, `test_llm_router_e2e.py`, `test_llm_router_queue_cache.py`, `LLMRouter`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Are the 161 inferred relationships involving `AgentRunner` (e.g. with `AgentCoordinator` and `AgentSpec`) actually correct?**
  _`AgentRunner` has 161 INFERRED edges - model-reasoned connections that need verification._
- **Are the 210 inferred relationships involving `HTTPException` (e.g. with `activate_instance()` and `change_user_role()`) actually correct?**
  _`HTTPException` has 210 INFERRED edges - model-reasoned connections that need verification._
- **Are the 109 inferred relationships involving `AgentSessionStore` (e.g. with `AgentPhaseError` and `AgentRunner`) actually correct?**
  _`AgentSessionStore` has 109 INFERRED edges - model-reasoned connections that need verification._
- **Are the 77 inferred relationships involving `AgentScheduler` (e.g. with `AgentStatusEntry` and `AgentStatusResponse`) actually correct?**
  _`AgentScheduler` has 77 INFERRED edges - model-reasoned connections that need verification._