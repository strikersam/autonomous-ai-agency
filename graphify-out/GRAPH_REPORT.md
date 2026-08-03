# Graph Report - local-llm-server  (2026-08-03)

## Corpus Check
- 1371 files · ~1,928,632 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 26871 nodes · 54384 edges · 1165 communities (1045 shown, 120 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 6056 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `de84d6fd`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ProviderConfig
- backend/server.py
- FreeBuffAgent
- AgentSessionStore
- CompanyGraphStore
- ai/router.py
- proxy.py
- AgentRunner
- company_api.py
- BackgroundAgent
- llm/router.py
- test_llm_router_queue_cache.py
- failover_chat_completion
- test_runtimes.py
- WebsiteScanner
- test_llm_router_resilience.py
- test_ceo_supervision.py
- Settings
- brain_config.py
- WorkflowOrchestrator
- ExecutionRequest
- TaskSpec
- MCPUnavailableError
- SecretRecord
- api.js
- TaskStore
- test_ceo_micromanager.py
- config.py
- MongoDBStore
- services/background.py
- skill_bindings.py
- webui/router.py
- RenderOpsMonitor
- test_llm_router_strategies.py
- get_company_graph_store
- TaskWorkflowService
- Task
- LLMRequest
- NotificationDispatcher
- MCPClient
- test_phase6_workflow.py
- workflow_orchestrator.py
- _StubProvider
- runtimes/api.py
- test_user_research_skill.py
- test_sam_livekit.py
- test_model_router.py
- test_loop_registry.py
- WorkflowRun
- test_knowledge_sync.py
- BrainWatchdog
- MultiAgentSwarm
- brain_failover.py
- test_llm_router_e2e.py
- GoalRecord
- SelfHealingAgent
- PortfolioManager
- direct_chat.py
- test_response_cache.py
- audit
- test_ceo_router.py
- workflow/api.py
- portfolio_intelligence.py
- AgentSwarm
- fmtErr
- detector.py
- test_ai_insights.py
- ResearchTask
- sync/service.py
- agency.py
- TokenBudget
- HybridSystem
- OrchestratorSupervisor
- Specialist
- test_model_catalog.py
- setup/api.py
- TestClient
- RewardScorer
- telegram_bot.py
- test_colibri_brain_shim.py
- test_repo_connection.py
- Troubleshooting
- FetchResult
- test_bedrock_provider.py
- ModelRouter
- TestClient
- FailureCategory
- Artifact
- seo_api.py
- test_brain_failover.py
- WebReach
- AgileSprint
- ChatPage.js
- FinancialMetrics
- LogWatcher
- TrafficDirector
- test_self_heal_v2.py
- WorkspaceTools
- Agent
- tasks/api.py
- useSafeData
- DetectedSystem
- SeoFixer
- StreamingDeltaReconstructor
- resolve_e2b_config
- probe_model_liveness
- test_integration_c4_c5_c6_d3.py
- run_tests
- ArtifactStore
- KnowledgeGraph
- LLMRouter
- services/seo_audit.py
- TaskIn
- ai_runner.py
- test_sqlite_store.py
- test_context_rulebook.py
- test_issue_intake.py
- ImprovementLoop
- Command
- ProvidersScreen.jsx
- WorkflowEngine
- InferenceCache
- CheckpointStore
- CoworkSession
- test_startup_warmup.py
- test_kimi_bridge_server.py
- App.js
- resolve_active_brain
- TestPayloadNormalisation
- TaskDispatcher
- ChatHistoryStore
- WorkspaceManager
- ToolRegistry
- ReactScratchpad
- E2BAdapter
- _ts_to_float
- test_telegram_freebuff.py
- api.ts
- WorkspaceManager
- AgileManager
- tests/conftest.py
- persist_plan_spec
- test_seo_audit.py
- test_trend_scoping.py
- Usage
- test_slop_gate.py
- system_instruction
- test_e2b_task_wiring.py
- activation_api.py
- MetricsRegistry
- OllamaCircuitBreaker
- fixture
- .get_workspace
- AdaptiveHalter
- render_ops.py
- diagnostics.py
- SeoAuditRequest
- SetupChecker
- PromptCacheManager
- activation.py
- test_quick_note.py
- TrendWatcher
- test_audit.py
- test_features_api.py
- test_video_transcript.py
- OnboardingScreen.jsx
- portfolio_api.py
- [Unreleased]
- Part A — CodeRabbit review fixes for this PR (do first, small)
- [Unreleased]
- Docker Agent Runtimes Setup
- TasksPage.js
- test_e2b_data_flow.py
- Persistent Memory System
- resolve_component_model
- SchedulerStore
- test_portfolio_intake.py
- AGENTS.md — Source of Truth for All AI Agents
- emit_chat_observation
- anthropic_compat.py
- test_agent_free_brain.py
- ContextWindowManager
- IssueCategory
- v4_api.py
- FeatureMatrix
- TestEstimateTokensForMessages
- distributed.py
- TestClient
- _run
- test_workspace_isolation.py
- PatternConsolidation
- getBackendUrl
- test_portfolio_intelligence.py
- ContextPruner
- V5App.jsx
- ServiceDaemon
- DigestSummary
- test_trend_watcher.py
- test_agency.py
- _Collection
- test_persistent_memory.py
- AgentJobResult
- GitHubTools
- SecurityScanner
- test_verification_strategies.py
- test_backend_server_features.py
- REWRITE_PLAN.md — Phased Migration Strategy
- test_background_services.py
- NIMConnectionPool
- run_regression
- test_all_providers_discovery.py
- report_to_markdown
- ScheduledJob
- JCodeAdapter
- test_control_plane_api.py
- agent_runtime.py
- ENGINEERING_STANDARDS.md — Coding, Security & Testing Standards
- FeatureEntry
- DashboardLayout.js
- context_rules.py
- test_rate_limiter.py
- local_controller.py
- test_live_server.py
- ContextManager
- SparkProvider
- README.md
- agents/api.py
- facade.py
- lifespan
- chat_handlers.py
- DashboardScreen.jsx
- test_daily_2026_06_04.py
- Workspace
- get_registry
- .execute
- test_microagents.py
- Security Analysis — local-llm-server
- Langfuse Observability Guide
- v3_models.py
- Screens
- TestDiagCommand
- test_purge_backlog.py
- test_telegram_mutating_commands.py
- StuckDetector
- test_unit7_catalog_propagation.py
- High-Agency Frontend Skill
- Quick-Note GitHub Issues Processing - Session Summary
- v3_auth.py
- RateLimitTracker
- TestRecordUsageAndStats
- test_sam_voice.py
- tests/test_browser.py
- openclaw_gateway.py
- KeyStore
- test_failover_silent_exhaustion.py
- switch_brain.py
- test_scheduler_hydration_bounded.py
- test_autonomy_gate.py
- FilterResult
- test_dashboard_cache.py
- test_pr923_fixes.py
- SteeringInjector
- test_claude_setup_audit.py
- test_crispy_burn_in.py
- test_internal_agent_did_work.py
- test_provider_enable_disable.py
- test_skill_registry_boot_refresh.py
- get_store
- Python Dependencies (`requirements.txt`)
- Technical Debt Register — local-llm-server
- get_skill_bindings
- llm_providers.py
- GitHubPage.js
- SetupWizardPage.js
- SeoAuditReport
- KeyPool
- RuntimeHealthService
- CostAttributor
- isolated_telegram_config
- WorkflowBuildRequest
- TestBrainFailoverModelUpdates
- test_memory.py
- analyze_qualitative
- SprintMetrics
- get_scheduler
- Deploy: FreeBuff Telegram bot (24×7)
- Claude Code + Qwen Local Setup
- get_feature_matrix
- generate_context.py
- _is_dns_failure
- test_anthropic_router.py
- test_daily_automation_2026_08_03.py
- validate_outbound_url
- webui/frontend/package.json
- LocalWorkspace
- Performance Analysis — local-llm-server
- LLM Router — troubleshooting
- AgentsScreen.jsx
- ClaudeCodeAdapter
- keepalive.py
- monitor_lib.py
- TrainingSample
- APIClient
- test_telegram_approval_e2e.py
- _get
- TestSchedulerStore
- test_service_token.py
- test_v3_auth.py
- TestWorkflow
- test_lessons.py
- test_rag_context.py
- ScheduleStore
- timedelta
- dependencies
- reset_store
- Session Handoff — 2026-06-15
- TASK 4 — End-to-end approval-gate test
- Any
- test_north_mini_code.py
- kimi_bridge_provider_config
- AgentMessageBus
- ProviderInfo
- TemporalContextGraph
- test_agency_fix.py
- TestClassifyPlainText
- get_tool_registry
- Findings
- Local AI Stack with Docker
- Configuration Reference
- Implementation Prompt: Rich TaskBoard + Agile Sprint Integration
- Telegram Bot Setup
- video_transcript.py
- PrioritizedTask
- CollectionLike
- test_monitor_lib.py
- test_output_filter.py
- test_schedule_backlog_drain.py
- test_v4_api.py
- test_workspace_security.py
- heal_signature
- CollaborationContext
- _get_provider_policy
- The fifteen strategies
- RuntimesPage.js
- ServiceManager
- _Cursor
- test_all_features.py
- test_brain_priority_scanner.py
- TestHarnessAdapter
- Path
- test_mostly_failed_steps.py
- classify_direct_chat_intent
- ._connect
- rag_context.py
- cost_tracker.py
- _resolve_user_github_token
- Harness
- DecisionsStore
- PriorityTaskQueue
- TestRenderMCPSidecarService
- _P
- test_repowise_intelligence.py
- test_voice.py
- V3 API Migration Plan — LLM Relay Platform
- SchedulesPage.js
- api_keys_for
- redact_connection_url
- test_issue_triage.py
- test_local_controller.py
- run_trend_analysis
- test_unit5_ui_provider_surface.py
- test_voice_pipeline.py
- MemoryCategory
- PersistentMemoryStore
- playbook.py
- WorkspaceError
- Skill: modularity-review
- Design Audit
- Findings
- TestNormalizeResponseFormat
- Skill: modularity-review
- crispy_client.py
- Dynamic Model Routing
- PortfolioScreen.jsx
- infra_cost.py
- output_filter.py
- compilerOptions
- GuardrailEngine
- HarnessRegistry
- test_brain_patch_service_token.py
- test_chat_mode_regressions.py
- test_tasks_cache_ttl_env.py
- test_workflow_models.py
- TestUpdateTask
- MemoryKernel
- _extract_tech_relevance
- agile_api.py
- HarnessAdapter
- Skill: fabric-patterns
- Analysis & Synthesis Instructions
- Production Readiness Assessment — local-llm-server
- Skill: fabric-patterns
- db/__init__.py
- Admin Dashboard Guide
- Implementation Plan
- Feature Guide
- ProviderConsole.jsx
- Provider
- key_pool.py
- Delegation Plan (agent-ready work packages)
- build_workflow.py
- test_p0_roadmap_b3_b4_b5.py
- SyntheticDataPipeline
- test_task_source_id_race.py
- test_company_api.py
- TestSelfHealingInfrastructureClassification
- test_fabric_patterns.py
- test_schedule_persistence.py
- validate_session_id
- ErrorInterceptorMiddleware
- github_tools.py
- ._parse_body
- .update_intelligence
- Comprehensive Skill Index (By Category)
- Agent Skill: Principal UI/UX Architect & Motion Choreographer (Awwwards-Tier)
- Component Map
- Agent State — colibri GLM-5.2 deployment (resumable)
- Architecture Overview — local-llm-server
- Pending Activities — Implementation Playbook
- Platform Guide — the full tour
- The rules
- Part A — Health Report
- apply_review.py
- ai/__init__.py
- scheduler.py
- SQLiteStore
- ._execute_with_fallback
- agency_fix.py
- sync_readme_gallery.py
- test_shared_state.py
- test_skill_executors_live.py
- LocalLLMSetup
- test_freebuff_bot.py
- test_task_brain_preflight.py
- test_openclaw_endpoints.py
- TestStopSlopChecker
- test_task_service_failed_comment.py
- handle_workflow_ide_chat
- test_contract_enforcement.py
- TestHelpers
- ._fetch_flat_skill_file
- Task
- terminal.py
- SKILL: Industrial Brutalism & Tactical Telemetry UI
- Skill: data-quality-audit
- What "Slop" Looks Like
- test_admin_local_brain_router.py
- local_brain_router.py
- Section-by-Section Acceptance Criteria
- agent_readiness_audit.py
- test_ci.sh
- test_telegram_auto_approve.py
- ProviderCircuit
- claim
- ._coerce_ts
- test_activation_api.py
- test_autonomy_status.py
- test_health_endpoints.py
- test_keepalive.py
- test_local_brain_state.py
- TestChatHistoryStore
- test_phase5_doctor.py
- TestRoutes
- test_telegram_diag_endpoint.py
- hermes_prompt.py
- MemoryMiddleware
- AITellIssue
- Skill: repowise-intelligence
- ARCHITECTURE.md — Target Architecture
- _check_storage_health
- _valid_login_state
- Skill: repowise-intelligence
- The 10-Step Workflow
- Contributing to local-llm-server
- CEO Micro-Management
- 467 Brutal Audit — File-by-File Status
- Runbook — Apply the Fast Free NVIDIA Brain to Render (TASK 2)
- SkillsScreen.jsx
- implement_agent.py
- HealthStatus
- GeminiProvider
- fabric_cli.py
- sync_ngrok.py
- GuardResult
- ManagedAgentDreams
- e2e/test_browser.py
- test_dockerfile_ships_root_modules.py
- test_frontend_deployment_guards.py
- test_glm52_brain.py
- test_langfuse_agency_wide.py
- TestBrainFailoverBackoff
- SamConversation
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
- Attention Mechanisms Internals
- issue_new_api_key
- allow_paid
- NvidiaProvider
- AdminSessionStore
- _push_down_where
- asyncio
- router/health.py
- DockerAgentAdapter
- AdminDigestRouterAuthTests
- clear_wizard_state_cache
- ._sprint
- TestModelRegistryUpdates
- DecisionsStoreTests
- test_dockerfile_ships_config_dir.py
- _run
- test_openclaw_gateway.py
- test_scanner_live.py
- test_telegram_task_callback.py
- Template
- StopSlopChecker
- Process
- Skill: lr-schedule-advisor
- Instructions
- Instructions
- Process
- Checks Performed
- Skill: training-stability-monitor
- test_new_features_e2e.py
- monitor_colibri.py
- admin_digest_router.py
- Skill: branch-cleanup
- Skill: perplexity — Web Research via Perplexity API
- Instructions
- Instructions
- Quick-Note Issues Processing Summary
- Implementation Plan — DB-persisted, UI-switchable Brain (no redeploy)
- Backend changes
- Runbook: Auto-Resume After Cooldown / Interruption
- SEO / GEO / AIO Audit Engine
- Traffic Distribution Across Providers
- devDependencies
- overrides
- mcp_server/server.py
- _parse_reset_epoch
- _RedisBackend
- cmd_autonomy
- _process_task_callback
- test_critical_flows.py
- test_regression.py
- test_autonomy_pipeline_regressions.py
- TestBrainConfigUpdates
- TestWorkspace
- TestDisabledReasonRendering
- _FakeSQLiteStore
- test_task_clarification.py
- _TFIDFIndex
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
- admin_update_task_router.py
- ProviderManager
- Instructions
- Skill: graphify — Knowledge Graph Token Optimization
- Skill: platform-setup — Autonomous Agency Bootstrap
- Workspace Isolation Architecture
- Device compatibility and model picks
- Autonomy Uplift — Living Roadmap & Detailed Implementation Specs
- OpenClaw — iOS Control of the Agency (Single-Service Free-Tier Deploy)
- rules
- ChatResponse
- Summary
- Agent Transparency Report
- update_provider_policy
- .publish
- _InMemoryBackend
- _resolve_push_token
- test_agile_api.py
- test_app_settings.py
- TestModelCostTableUpdates
- TestMCPClientStructuredOutput
- TestDecisionsBotLinks
- test_deploy_trigger_covers_image.py
- TestRuntimeControl
- TestKillSwitchDurability
- TestRouterIntegration
- verify_token
- WorkspaceManifest
- CLAUDE.md — agent/
- skill_registry.py
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
- _is_ephemeral_user
- 14. Standing Instructions — Universal Agent Discipline
- Skill: agent-browser — Real Chrome Browser Automation
- Instructions
- Instructions
- Skill: dev-browser — Browser Automation via Sandboxed JS
- Instructions
- Agent Orchestration Design
- Universality: case-coverage matrix
- Quantization Internals
- Implementation — DB-persisted, UI-switchable Brain (PR #824 follow-up)
- 2. Pending ⬜ — detailed implementation specs
- 467 Public Site Truth Spec
- Render MCP — autonomous platform debugging and environment monitoring
- TestRequireAdmin
- test_p0_roadmap_a4_a5_b2.py
- Kimi Web-Bridge Service
- test_docs_consistency.py
- TestAuthAndTaskCreation
- test_providers_live_e2e.py
- test_skill_registry.py
- validate_job_id
- EvalHarness
- SavingsTracker
- _extractive_compress
- .get_overview
- RepowiseIntelligence
- RegistrySkill
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
- CI Troubleshooting Runbook
- NVIDIA NIM — Free Tier Setup
- What to clean up
- Worker Service — Operations Runbook
- test_bedrock_live.py
- provider_max_rpm
- ._order_group
- verify_service_token
- run_proxy.sh
- Security Policy
- setup_ngrok.py
- test_empirical_verify.py
- test_event_log.py
- test_google_provider_models.py
- test_tasks_awaiting_approval_api.py
- admin_gui.py
- Instructions
- Protocol: Premium Utilitarian Minimalism UI Architect
- The 5-Step Wrap-Up Ritual
- CLAUDE.md — Master Architect Operating Manual
- Agent: Reviewer (Verifier)
- Skill: Agentic Agile
- Skill: browserbase-ui-test — Adversarial UI Testing
- Skill: financial-analyst (Agentic CFO)
- Graphiti Temporal Context Skill
- Skill: seo-audit-report
- ADR-008: LLMRouter — the single multi-provider routing gateway
- Agent Readiness Report
- Core Pillars
- 467 Golden Path — Locked Implementation Order
- LLM Router — configuration guide
- LLM Router — provider guide
- LoopsScreen.jsx
- _fake_fetch_module
- OutputFilter
- CerebrasProvider
- TestModelsEndpointAliases
- build_tech_db.py
- main
- run_bot
- _start_ceo_agency
- Dream
- test_bootstrap_source_id_index.py
- TestExtendedThinkingRouting
- TestZeroAttemptDiagnostics
- TestSessionMemory
- test_provider_state_durability.py
- test_quick_note_engine.py
- TestAnthropicPayloadStructuredOutput
- ._make_run
- synthesize
- BenchmarkReport
- _extract_workflow_relevance
- Coding Standards
- Skill: changelog-enforcer
- Skill: learn-rule
- Instructions
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
- Release Procedure
- V2.0 Modernization — Runbook
- Setup
- check_feature
- frontend/package.json
- AgentStatusPanel.tsx
- AgentStatusPanel.jsx
- ToolCallViewer.tsx
- cleanup_stale_jobs
- enrich_quick_note_issues.py
- _status_snapshot
- incr_window
- e2e/conftest.py
- admin_jwt
- test_agent_api.py
- test_backend_requirements_cover_runtime_imports.py
- test_changelog_parity_guard.py
- TestEnforcement
- fixture
- TestChatFallbackAndApproval
- test_ping.py
- FakeScheduleCollection
- TestMongoGate
- TestPaidPolicyDurability
- test_runtimes_health_endpoint.py
- test_scanner_deps_parity.py
- test_task_store_fails_loud_in_production.py
- stt.py
- navigation_metrics.py
- _score_turns
- ._run_git_command
- TrajectoryStep
- quality_checker.py
- Skill: docs-sync
- get_catalog
- Agent: Implementer (Executor)
- Agent: Judge (Release / QA Gate)
- Agent: Planner (Architect)
- Skill: browserbase-browser — Real Browser Automation
- Skill: docs-sync
- Skill: memory-consolidation (Dream Memory)
- GitHub Branch Protection Settings
- ADR 001: Self-Hosted OpenAI-Compatible Proxy
- ADR 002: Dynamic Model Routing with Task Classification
- Agent Autonomy Roadmap
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
- Setup
- TOP 6 — Highest-ROI Items (Validated by Opus Research Agent)
- SECTION A — Agent Efficiency (Hermes / AOS / MYT)
- SECTION C — Direct Chat Improvements (CBF / HRM)
- Runbook — Instance Activation
- PULL_REQUEST_TEMPLATE.md
- _get_current_user
- bus.py
- capture_screens.py
- Prompt Library
- CLAUDE.md — router/
- crispy_burn_in.py
- run_patched_colibri.py
- SessionMemory
- TestCompany
- TestAnthropicToOpenAICacheUsage
- test_compose_and_coordinate_api.py
- test_doctor_coding_brain.py
- TestAdminVisibility
- TestFeaturesAPI
- TestProviderRouter
- test_local_brain_router_smoke.py
- TestAgentLoopMCPIntegration
- test_provider_models_db_outage.py
- _FakeDb
- TestCatalog
- test_serve_spa_prefixes.py
- dry_clone_repo
- TOOLS.md — Available Tools for AI Agents
- .assess
- _keyword_search
- SIA
- Full-Output Enforcement
- summarise.sh
- updater.py
- _build_direct_chat_schedule_suggestion
- get_harness_registry
- _load_local_metrics_since
- ModelRegistry
- 4. Current Architecture (As-Is)
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
- ADR-006: Strangler Fig migration with backward-compat shims
- claude-mem Plugin — Persistent Memory for All Sessions
- Implementation plan + TO-DO (check off as you go)
- Topics Covered
- LLM Router — migration guide
- What's New
- Cloudflare = the real working app
- production
- launch-claude-code.sh
- PRD — README Marketing Refresh
- Any
- check_changelog_parity.py
- e2e_smoke.py
- BackgroundServices
- _reset_backend
- task_runner.py
- TestWindowsAuth
- test_daily_2026_06_14.py
- TestSupportMatrixDocsSync
- TestMatrixLoad
- TestGithubTokenSQLiteRegression
- sam
- test_log_monitor_storm_guard.py
- _FakeCollection
- TestTechSkillMap
- TestActiveStrategy
- test_workspace_repowise.py
- _tokenize
- ._get_last_commit
- _brain_provider_status
- sam_chat_backend
- openclaw_mobile_ui
- _wfo_owned_run_or_404
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
- The full agent capability roster
- Pre-Mortem Analysis: Agency Core autonomy story (Cloudflare deployment)
- SECTION B — NVIDIA / Cloud Model Integration (Nemotron / NVD)
- SECTION D — Deployment & Infrastructure (CHM / NVD)
- Feature Support Matrix
- RelayShowcasePage.js
- resolve_hermes_base_url
- reset
- .execute
- apply_phase1_changes.py
- _replace
- check_doc_images.py
- gen_screenshots.py
- gen_v4_screenshots.py
- setup-claude-code.sh script
- TestRuntimes
- Report
- PhaseSequenceError
- test_generate_context_standing_instructions.py
- _auth_headers
- webui/commands.py
- harness.py
- _rrf
- .build_context
- get_harness_adapter
- heartbeat.sh
- 1. What This Repo Does
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
- Rollout
- Who is this for?
- SECTION E — Autonomy & Self-Healing (AOS / MYT / ECC)
- SECTION F — Developer Experience (CBF / ECC)
- Runtime troubleshooting
- knowledgeGraphTab.test.js
- loginFlowNoTimeout.test.js
- test_company_stale_id_recovery.test.js
- worker_no_cache.test.js
- scripts/agile_ceremonies.py
- .chat
- _clean_director
- Prompt Library Changelog
- Proof
- build_llama_cpp.ps1
- download_glm52_weights.ps1
- download_glm52_weights.sh script
- _fetch_pytest_failures.py
- setup_colibri.ps1
- setup_colibri.sh script
- status_colibri_server.ps1
- TestAuth
- TestMobileNavigation
- test_v5_screens_smoke.py
- test_agent_runtime_wrapper.py
- TestSingleton
- TestWorkflowSkillMap
- worker/index.js
- _fix_restart_background
- Any
- recovery.py
- test_activity_logs.py
- _oauth_popup_html
- 10. Testing Constitution
- 5. AI Provider Architecture
- 6. Agent Architecture
- aider_config.sh
- providers.yaml
- Issue → Context → Draft PR automation
- The 24x7 agency — your agents never go idle
- Privacy, security, and cost
- Credential Rotation Runbook
- Runbook: `make doctor`
- render
- scripts
- list_available_fixes
- .execute
- _resolve_default_executor_model
- .best_for
- stop_colibri_server.ps1
- .consolidate
- start_server.sh
- check_services
- TestHealth
- TestProviders
- nvidia_live_test.py
- test_activity_feed.py
- test_iteration_6_features.py
- test_local_brain_router_actor_regression.py
- test_no_exception_detail_leaks.py
- test_skills_route_order.py
- github
- 10. CI/CD Standards
- 11. Rewrite Strategy
- 3. Repository Constitution
- 7. Scheduler Architecture
- 8. Authentication Architecture
- graphify-refresh
- [Unreleased]
- Session Learnings
- Configuration reference
- frontend/.eslintrc.json
- .get_system_by_type
- .get_phase_index
- branch_cleanup.sh
- local-ai-health-check.sh
- pull-ai-models.sh
- test_nim_models.py
- .consolidation_threshold
- test-anthropic.js
- _classify_error
- TestAgents
- TestChat
- TestDashboard
- TestDoctor
- TestFeatures
- TestGitHub
- TestSchedules
- TestSkills
- .test_create_and_delete_key
- .test_create_task
- .test_create_schedule
- test_direct_adapter_does_not_bypass
- _enable_filter
- .create_branch_compat
- maintenance_section.md
- duplicate.sh
- hello_claude.py
- backend/__init__.py
- _classify_complexity
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
1. `AgentRunner` - 298 edges
2. `AgentSessionStore` - 185 edges
3. `ProviderConfig` - 152 edges
4. `ProviderRouter` - 152 edges
5. `Task` - 151 edges
6. `AgentScheduler` - 149 edges
7. `ExecutionRequest` - 132 edges
8. `UserMemoryStore` - 130 edges
9. `Agency` - 128 edges
10. `AgentJobManager` - 119 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `_skip()`  [INFERRED]
  .github/scripts/apply_review.py → tests/test_providers_live_e2e.py
- `test_ci_allow_paid_defaults_false()` --calls--> `allow_paid()`  [INFERRED]
  tests/test_provider_policy.py → .github/scripts/provider_policy.py
- `test_ci_allow_paid_falls_back_to_env_var()` --calls--> `allow_paid()`  [INFERRED]
  tests/test_provider_policy.py → .github/scripts/provider_policy.py
- `apply_edits()` --calls--> `is_destructive_overwrite()`  [INFERRED]
  scripts/agency_fix.py → .github/scripts/slop_gate.py
- `test_new_file_is_allowed()` --calls--> `is_destructive_overwrite()`  [INFERRED]
  tests/test_slop_gate.py → .github/scripts/slop_gate.py

## Import Cycles
- None detected.

## Communities (1165 total, 120 thin omitted)

### Community 0 - "ProviderConfig"
Cohesion: 0.03
Nodes (210): Agency, get_agency(), CEO-coordinated multi-agent agency for continuous codebase management. The CEO…, set_agency(), AgentJobRequest, AgentJobSnapshot, BaseModel, agent/contract.py — Typed public contract for the agent job lifecycle. Phase 1… (+202 more)

### Community 1 - "backend/server.py"
Cohesion: 0.02
Nodes (247): admin_seed(), _agent_timeout_fallback_response(), auth_me(), auto_recommend_skills(), brain_failover_status(), _build_agent_status_snapshot(), _build_agent_stream_event(), _build_provider_router() (+239 more)

### Community 2 - "FreeBuffAgent"
Cohesion: 0.03
Nodes (184): BrowserSession, Async Playwright browser session. Usage:: session = BrowserSession() await…, True if Playwright is installed and ready to use., CommitAttribution, CommitTracker, Path, agent/commit_tracker.py — AI Commit Attribution Tags git commits with metadata…, Create git commits enriched with agent-session attribution trailers. Usage::… (+176 more)

### Community 3 - "AgentSessionStore"
Cohesion: 0.02
Nodes (147): PreflightIssue, PreflightReport, BaseModel, Agent subsystem — planner / executor / verifier loop., AgentJob, AgentJobManager, make_isolated_workspace(), _now() (+139 more)

### Community 4 - "CompanyGraphStore"
Cohesion: 0.01
Nodes (115): BusinessCategory, Get the bound Company Graph., CompanyGraph, CompanyGraphSnapshot, The complete Company Graph - canonical core model for the Autonomous AI Agency.…, Find a website by its URL., Find a repository by its URL., Find a workflow by its name. (+107 more)

### Community 5 - "ai/router.py"
Cohesion: 0.02
Nodes (156): get_tracker(), Return the process-singleton RateLimitTracker., _acquire_provider_probe(), clear_cooldowns(), _dead_model_key(), _exponential_backoff_cooldown(), get_dead_models(), _get_director() (+148 more)

### Community 6 - "proxy.py"
Cohesion: 0.02
Nodes (184): Any, Return recent commits with agent attribution trailers parsed out., free_nvidia_models(), Return the curated list of free NVIDIA NIM models FreeBuff may use., List the free NVIDIA NIM models a user may pick (e.g. via Telegram)., True when *model* is in the curated free NVIDIA NIM set., get_sam(), agent/sam.py — SAM Voice Agent (System Autonomy Manager) SAM is the voice-… (+176 more)

### Community 7 - "AgentRunner"
Cohesion: 0.02
Nodes (140): get_enrichment(), agent/harness_enrichment.py — Automatic Harness Enrichment for Agent Prompts…, AgentRunner, _check_extra_kwargs(), _enforce_signature(), _nvidia_api_key(), Any, Path (+132 more)

### Community 8 - "company_api.py"
Cohesion: 0.04
Nodes (165): account_lifecycle(), AccountLifecycleResponse, auto_recommend_skills(), cancel_onboarding(), create_company(), delete_company_endpoint(), _DoctorCheck, _DoctorReport (+157 more)

### Community 9 - "BackgroundAgent"
Cohesion: 0.02
Nodes (108): AgentRole, str, BackgroundAgent, BackgroundTask, _now(), Any, agent/background.py — Background Agent An always-on worker thread that…, Enqueue *task* for processing. Returns the task (with task_id set). (+100 more)

### Community 10 - "llm/router.py"
Cohesion: 0.03
Nodes (121): _load(), main(), int, openai_body_from_response(), Any, packages/llm/compat.py — backwards-compatible bridges to the legacy call paths.…, Whether the compat bridges should delegate to ``LLMRouter``. Reads the flag on…, Translate an OpenAI-shaped chat payload into an ``LLMRequest``. Unknown keys… (+113 more)

### Community 11 - "test_llm_router_queue_cache.py"
Cohesion: 0.02
Nodes (111): Test hook — clear all usage accounting., reset(), CacheManager, cosine_similarity(), _Entry, get_cache(), LRUCache, Any (+103 more)

### Community 12 - "failover_chat_completion"
Cohesion: 0.03
Nodes (135): _auto_disable(), _Budget, _build_request(), _describe_registry(), _disabled_ids(), failover_chat_completion(), FailoverResult, _is_billing_refusal() (+127 more)

### Community 13 - "test_runtimes.py"
Cohesion: 0.03
Nodes (62): AiderAdapter, Any, Adapter for Aider — TIER 3 specialized git-aware code editor., GooseAdapter, Any, Adapter for Goose — TIER 2 general-purpose local runtime., HermesAdapter, Adapter for Hermes Agent — FIRST CLASS autonomous runtime. (+54 more)

### Community 14 - "WebsiteScanner"
Cohesion: 0.02
Nodes (95): Evidence, Evidence supporting a system detection., main(), Returns (url, ok, summary)., _scan_one(), _content_contains_domain(), _hostname_contains(), _hostname_matches() (+87 more)

### Community 15 - "test_llm_router_resilience.py"
Cohesion: 0.03
Nodes (86): HealthConfig, Backoff policy for retryable failures., Circuit breaker + health tracking thresholds., RetryConfig, BreakerState, HealthTracker, _Outcome, ProviderHealth (+78 more)

### Community 16 - "test_ceo_supervision.py"
Cohesion: 0.04
Nodes (108): CEODispatcher, _harvest_changed_files(), _offload(), Any, Semaphore, Run a synchronous ledger call without blocking the event loop. ``CEOLedger`` is…, Extract the files a runtime touched. Returns ``(files, reported)``. Adapters…, Build an agent.coordinator.TaskSpec from a CEO SpecialistTask. (+100 more)

### Community 17 - "Settings"
Cohesion: 0.02
Nodes (93): provider_key_present(), True when the env var for *provider*'s key is set (or it's Ollama)., CatalogActiveBrain, CatalogMirror, CatalogProviderEntry, _include_router_providers(), invalidate_catalog_cache(), is_catalog_enabled() (+85 more)

### Community 18 - "brain_config.py"
Cohesion: 0.03
Nodes (111): BrainConfig, BrainConfigStore, default_brain_config(), get_brain_config(), get_brain_config_store(), invalidate_brain_config_cache(), provider_base_url(), _provider_env_value() (+103 more)

### Community 19 - "WorkflowOrchestrator"
Cohesion: 0.03
Nodes (102): CEOResult, _complexity_rank(), _decompose_into_subtasks(), _merge_changed_files(), Reset the singleton (test helper)., Aggregated output from a multi-specialist execution., Decompose a request into 2-3 sub-tasks for specialist fan-out. Default…, Collect changed_files across all specialists into a single de-duped list. (+94 more)

### Community 20 - "ExecutionRequest"
Cohesion: 0.03
Nodes (65): Called by APScheduler when a cron fires. Dispatches to the orchestrator., _scheduler_on_fire(), ExecutionRequest, get_workflow_orchestrator(), Resolve the LLM endpoint for agent execution (module-level, #522 failover).…, Return the shared WorkflowOrchestrator singleton., Reset the singleton (test helper)., Canonical request to execute work through the golden path. This is the ONLY… (+57 more)

### Community 21 - "TaskSpec"
Cohesion: 0.04
Nodes (69): runtimes/adapters/aider.py — Aider adapter (TIER 3 — specialized). Aider…, runtimes/adapters/claude_code.py — Claude Code CLI adapter (FIRST CLASS).…, runtimes/adapters/docker_agent.py — Docker-based agent runtime adapter. Spawns…, runtimes/adapters/e2b.py — E2B Firecracker micro-VM runtime adapter. Routes…, TaskResult, TaskSpec, runtimes/adapters/goose.py — Goose adapter (TIER 2). Goose…, runtimes/adapters/hermes.py — Hermes Agent adapter (FIRST CLASS). Hermes Agent… (+61 more)

### Community 22 - "MCPUnavailableError"
Cohesion: 0.04
Nodes (80): MCPUnavailableError, Raised when the MCP server is unreachable or the circuit is open., TaskResult, TaskSpec, Execute a task inside a fresh E2B sandbox. Flow: 1. Open an…, Run ``pytest`` inside the sandbox. Returns ``(output, passed)``.…, E2BSandboxSession, _inject_token() (+72 more)

### Community 23 - "SecretRecord"
Cohesion: 0.04
Nodes (88): compute_savings(), compute_time_series(), get_savings(), get_usage(), get_user_savings(), _period_start(), Any, BaseModel (+80 more)

### Community 24 - "api.js"
Cohesion: 0.02
Nodes (39): approveTaskCheckpoint(), approveTaskExecution(), createMcpServer(), createQuickNote(), createSprint(), createTask(), delegateSeoFindings(), deleteMcpServer() (+31 more)

### Community 25 - "TaskStore"
Cohesion: 0.04
Nodes (90): agent/workflow.py — Persisted workflow state machine. Implements the Autonomous…, Set the global agent store instance (e.g., with MongoDB on startup)., set_agent_store(), quick_notes_submit(), Point the feature stores at the shared database connection. Deliberately…, Submit a quick-note URL or instruction from the dashboard FAB., _wire_feature_stores(), Helpers that turn scheduler and playbook activity into real tasks. (+82 more)

### Community 26 - "test_ceo_micromanager.py"
Cohesion: 0.05
Nodes (102): services/ceo_dispatcher.py — Real CEO delegation layer. The CEO splits a…, _runtime_id_for_role(), build_subtask_brief(), _coerce_subtasks(), decompose(), _env_flag(), _env_int(), _extract_json_object() (+94 more)

### Community 27 - "config.py"
Cohesion: 0.03
Nodes (85): AgentPolicy, _apply_env_overrides(), _apply_key_env(), _build(), _coerce(), config_dir(), _env_key_names(), expand_env() (+77 more)

### Community 28 - "MongoDBStore"
Cohesion: 0.04
Nodes (53): MongoDBStore, Any, Company, ObjectId, Prepare a Pydantic model for SQLite storage., Prepare a SQLite row for Pydantic model., Create a new company in SQLite., Get a company by ID from SQLite. (+45 more)

### Community 29 - "services/background.py"
Cohesion: 0.04
Nodes (88): get_improvement_loop(), _dispatch_async(), _ErrorCaptureHandler, get_log_monitor(), LogMonitor, _note_recurrence(), Any, LogRecord (+80 more)

### Community 30 - "skill_bindings.py"
Cohesion: 0.04
Nodes (68): Status of a user story within a sprint., StoryStatus, EdgeType, Types of relationships between knowledge nodes., ConsolidationPhase, DreamMemory, MemoryKind, Enum (+60 more)

### Community 31 - "webui/router.py"
Cohesion: 0.05
Nodes (69): _bootstrap(), fixture, Path, ProviderManager, WorkspaceManager, tests/test_webui_provider_priority.py — Priority + reorder + brain-policy…, The /policy/brain endpoint must return the resolved brain + the paid policy…, The /providers/role-tags endpoint surfaces brain/sub/fallback roles consistent… (+61 more)

### Community 32 - "RenderOpsMonitor"
Cohesion: 0.05
Nodes (39): RuntimeError, One deploy, normalised from whatever shape the tool returned., Typed facade over the Render MCP server's tools. Every method returns plain…, True when there is both an API key and an endpoint to reach., Return the most recent deploy, or ``None`` when there are none., Raised when a mutating Render tool is called with writes disabled., RenderDeploy, RenderMCPClient (+31 more)

### Community 33 - "test_llm_router_strategies.py"
Cohesion: 0.05
Nodes (82): count, Strategy selection and degradation behaviour., RoutingConfig, Build and order the (provider, model) pairs that can serve ``request``., Cap the breadth of one request's search so a failure is bounded., The input ceiling this candidate will actually accept. A context window is not…, Shrink the conversation to this candidate's window if it overflows., adaptive() (+74 more)

### Community 34 - "get_company_graph_store"
Cohesion: 0.04
Nodes (71): match_specialists(), SystemType, Match specialists to a task. Returns the best specialists for the given task…, autonomy_status(), Public autonomy readiness probe — no authentication required. A live deploy…, Fire-and-forget self-bootstrap; never blocks or crashes startup., _schedule_self_bootstrap(), CompanyAgencyService (+63 more)

### Community 35 - "TaskWorkflowService"
Cohesion: 0.05
Nodes (63): ApprovalCheckpoint, Human approval gate in a task's execution., _is_brain_connection_error(), Any, BaseException, Task, TaskResult, TaskSpec (+55 more)

### Community 36 - "Task"
Cohesion: 0.04
Nodes (62): Hand the 'connect & verify the repo' work to the agency's own agents. The task…, _seed_connect_task(), Full task/issue document., Task, Best-effort label of who will run this task once approved. Returns…, PUBLIC_URL-anchored dashboard deep link for the task detail. Returns empty…, Best-effort Telegram heads-up that a task is parked awaiting approval. Inline…, One-line human explanation of why this task needs human approval. Reads risk… (+54 more)

### Community 37 - "LLMRequest"
Cohesion: 0.05
Nodes (66): ProviderConfig, One configured endpoint. ``kind`` selects the adapter: ``openai`` (any OpenAI-…, AnthropicProvider, Any, AsyncClient, Translate OpenAI-shaped messages into Anthropic's system/turn split., OpenAI carries a tool result as role="tool" with a tool_call_id; Anthropic…, OpenAI puts a tool call alongside the assistant's text; Anthropic needs… (+58 more)

### Community 38 - "NotificationDispatcher"
Cohesion: 0.04
Nodes (57): _escape_md_v1(), NotificationDispatcher, Any, Path, service_manager.py — Telegram & Notification Integration Extension Extends the…, Start the Telegram bot. Returns True if started successfully., Signal the bot to stop and wait for graceful shutdown., Run the Telegram bot long-poll loop (inline, not subprocess). (+49 more)

### Community 39 - "MCPClient"
Cohesion: 0.04
Nodes (35): get_mcp_client(), MCPClient, Any, RuntimeError, agent/mcp_client.py — Async MCP client for the mcp-server Docker container.…, Prefer structured data; fall back to text when unavailable., Thin async MCP client with open/close circuit breaker. Thread-safe only within…, Full URL of the JSON-RPC endpoint this client posts to. (+27 more)

### Community 40 - "test_phase6_workflow.py"
Cohesion: 0.04
Nodes (72): add_pr_comment(), _find_existing_pr(), get_branch_sha(), get_default_branch(), _headers(), Any, agent/safe_agency.py — Safe GitHub operations for the workflow engine. All…, Create a pull request. Returns the PR object dict. If a PR already exists for… (+64 more)

### Community 41 - "workflow_orchestrator.py"
Cohesion: 0.06
Nodes (62): get_orchestrator_checkpoint_store(), _NoopDB, OrchestratorCheckpointStore, Any, services/orchestrator_checkpoint.py — Durable step-level checkpointing Issue…, Restore in-flight runs at startup. Called during backend bootstrap. Returns a…, Fallback in-memory store when no DB is available., Persist orchestrator runs so they survive restarts. (+54 more)

### Community 42 - "_StubProvider"
Cohesion: 0.05
Nodes (53): _disable_unless_key_serves_other_models(), _models_to_try(), Order the models to attempt on *provider*, correcting a stale catalogue. Cache-…, Auto-disable *provider*, unless its key demonstrably serves other models. "No…, attempted(), cached_models(), discover_models(), _fresh_entry() (+45 more)

### Community 43 - "runtimes/api.py"
Cohesion: 0.05
Nodes (76): e2b_status(), _enrich_runtimes(), get_decision_log(), get_policy(), get_runtime(), list_runtimes(), _load_rich_policy(), PolicyUpdateBody (+68 more)

### Community 44 - "test_user_research_skill.py"
Cohesion: 0.06
Nodes (45): analyze_quantitative(), _classify_sentiment(), _extract_keywords(), plan_research(), Any, BaseModel, field_validator, QualAnalysis (+37 more)

### Community 45 - "test_sam_livekit.py"
Cohesion: 0.04
Nodes (69): Report whether the SAM realtime voice (LiveKit) transport is configured., sam_livekit_status_backend(), auth_headers(), livekit_env(), no_livekit_env(), _normalize_dockerfile(), fixture, parametrize (+61 more)

### Community 46 - "test_model_router.py"
Cohesion: 0.05
Nodes (79): classify_task(), _extract_recent_text(), Any, Task classification from request context. Classifies an incoming request into a…, Concatenate plain text from the last *last_n* messages., Return the most likely task category for this request. Args: messages: OpenAI-…, Reset the singleton and clear the cached model map (test helper)., reset_router() (+71 more)

### Community 47 - "test_loop_registry.py"
Cohesion: 0.05
Nodes (64): audit_drift(), _cmd_audit(), DriftReport, _grade(), load_registry(), load_registry_sync(), loop_readiness(), LoopRegistry (+56 more)

### Community 48 - "WorkflowRun"
Cohesion: 0.04
Nodes (41): Any, Exception, Approve a run paused at the ApprovalGate. The caller must re-invoke…, Inject additional instructions into an in-flight run (no state change). Backs…, Push a Telegram approval-gate notification when a run pauses (Charter G1).…, G5: resolve how a run should land from the company's DeliveryPolicy. Returns…, Persist first-merge consent once an operator approves a ``telegram_gate``. No-…, List recent runs. When ``owner_id`` is provided, only runs stamped with that… (+33 more)

### Community 49 - "test_knowledge_sync.py"
Cohesion: 0.06
Nodes (63): _api_key(), _auth_headers(), _build_digest_markdown(), create_wiki_page(), fetch_and_store(), get_knowledge_sync(), KnowledgeSync, _now_iso() (+55 more)

### Community 50 - "BrainWatchdog"
Cohesion: 0.04
Nodes (57): Any, packages/ai/self_heal.py — automatic brain self-healing. When the active brain…, Background tick that runs self_heal_brain_and_unblock_tasks(). Called from the…, One-shot self-healing pass. 1. Checks if the active brain provider is in a…, self_heal_brain_and_unblock_tasks(), _self_heal_tick(), BrainWatchdog, get_watchdog() (+49 more)

### Community 51 - "MultiAgentSwarm"
Cohesion: 0.07
Nodes (60): AgentConfig, build_agent_specs(), build_swarm(), build_task_specs(), coordinate_v2(), CoordinateRequestV2, CoordinateResponse, Any (+52 more)

### Community 52 - "brain_failover.py"
Cohesion: 0.05
Nodes (74): brain_providers(), Every configured provider with its health AND its on/off state. Powers the…, auto_disable(), _billing_signals(), describe(), disabled_provider_ids(), is_unfixable(), packages/llm/disabled.py — bridge to the durable provider on/off switch. The… (+66 more)

### Community 53 - "test_llm_router_e2e.py"
Cohesion: 0.05
Nodes (65): gateway_enabled(), Whether the OpenAI-compatible passthrough routes accept traffic. Off by…, build_llm_router(), Any, APIRouter, Render router chunks as OpenAI-compatible SSE., Build the ``/api/llm`` router. ``get_current_user`` is the platform's auth…, _stream_sse() (+57 more)

### Community 54 - "GoalRecord"
Cohesion: 0.05
Nodes (54): Record the goal and its sub-tasks in the ledger before any work runs. Writing…, _backend(), CEOLedger, get_ceo_ledger(), GoalRecord, _now(), Any, services/ceo_ledger.py — durable record of what the CEO is driving to closure.… (+46 more)

### Community 55 - "SelfHealingAgent"
Cohesion: 0.05
Nodes (50): HealingEvent, _now(), Any, Translate external failure signals into improvement tasks and verify the fix…, Launch the background sweeper that resolves quiet verifying heals., Called when a CI workflow fails., Called when a GitHub issue with a bug label is opened., Called from the v4 dashboard 'Report Bug' form and the LogMonitor.… (+42 more)

### Community 56 - "PortfolioManager"
Cohesion: 0.04
Nodes (35): Initiative, PortfolioManager, PortfolioMetrics, Aggregate metrics across the whole portfolio., Manages a portfolio of initiatives with WSJF prioritisation and roadmapping., Create and register a new initiative, returning it., Add a pre-built Initiative (e.g. from the intelligence layer)., Remove an initiative from the portfolio. (+27 more)

### Community 57 - "direct_chat.py"
Cohesion: 0.07
Nodes (66): Any, doctor.py — Agent-side doctor diagnostics: environment, provider, and workspace…, Translate technical preflight issues into a conversational assistant reply., translate_error_to_conversational(), ResumeRequest, AcceptedJob, AgentJobEnvelope, CompletedJob (+58 more)

### Community 58 - "test_response_cache.py"
Cohesion: 0.06
Nodes (71): _cache_key(), cache_stats(), clear_cache(), get_cached(), is_cacheable(), put_cached(), Any, packages/ai/response_cache.py — LRU+TTL in-memory response cache for the… (+63 more)

### Community 59 - "audit"
Cohesion: 0.05
Nodes (32): audit(), get_audit_log(), get_user_role(), has_permission(), is_admin(), is_power_user_or_above(), mask_dict(), mask_secret() (+24 more)

### Community 60 - "test_ceo_router.py"
Cohesion: 0.05
Nodes (54): get_ceo_dispatcher(), Return the shared CEODispatcher singleton., CEOSupervisor, _env_flag(), _env_int(), Any, services/ceo_supervisor.py — the CEO's 24x7 babysitting loop. Delegation alone…, Sweeps the CEO ledger and drives open goals to closure. (+46 more)

### Community 61 - "workflow/api.py"
Cohesion: 0.06
Nodes (61): _make_engine(), fixture, tests/test_crispy_workflow.py — CRISPY workflow engine hardening tests. Tests…, Provide isolated DB + artifact + workspace paths., Create a WorkflowEngine with isolated storage., TestAbortOnFailure, TestPhaseSequence, TestWorkspaceIsolation (+53 more)

### Community 62 - "portfolio_intelligence.py"
Cohesion: 0.05
Nodes (61): _bullets(), generate_backlog_retro(), generate_sprint_retro(), generate_standup(), plan_next_sprint(), Agentic Agile — autonomous ceremonies (standup, retro, sprint planning). Where…, Render a :class:`Retrospective` as a markdown section., Derive retro notes for ``sprint`` from its current metrics. Records… (+53 more)

### Community 63 - "AgentSwarm"
Cohesion: 0.06
Nodes (34): agents/__init__.py — CRISPY multi-agent coding system., AgentProfile, _catalog_defaults(), _catalog_provider(), _get_defaults(), load_all_profiles(), make_architect_profile(), make_coder_profile() (+26 more)

### Community 64 - "fmtErr"
Cohesion: 0.06
Nodes (49): fmtErr(), getActivity(), getCostAttribution(), getDecisionLog(), getDueSoonTasks(), getSavings(), getStats(), getUsage() (+41 more)

### Community 65 - "detector.py"
Cohesion: 0.07
Nodes (46): batch_compatibility(), check_model_compatibility(), _detect_amd_gpus(), _detect_apple_silicon_gpu(), _detect_cpu(), detect_hardware(), _detect_intel_arc_gpu(), _detect_nvidia_gpus() (+38 more)

### Community 66 - "test_ai_insights.py"
Cohesion: 0.05
Nodes (51): AIToolMetrics, build_report(), EngagementMetrics, PerformanceAnalytics, datetime, Enum, str, AI-Assisted Engineering Insights — track AI tool usage, engagement, and… (+43 more)

### Community 67 - "ResearchTask"
Cohesion: 0.06
Nodes (45): AgentRole, Enum, str, Multi-Agent Research Coordinator — orchestrate a team of specialized research…, Run the task and return it (mutated) with status set., Coordinates a multi-agent research workflow. Workflow: 1. plan(question) → list…, Decompose a research question into a default DAG. Default plan: web → docs…, Round-robin pick within a role (least-loaded first). (+37 more)

### Community 68 - "sync/service.py"
Cohesion: 0.07
Nodes (47): FastAPI dependency: require Power User or Admin role. Raises 403 otherwise., require_power_user(), sync/ — Syncthing-style workspace synchronisation service., add_peer(), get_folder_index(), get_sync_file(), get_sync_service(), list_conflicts() (+39 more)

### Community 69 - "agency.py"
Cohesion: 0.05
Nodes (39): AgencyCycleResult, AgentDirective, _build_ceo_prompt(), _build_quick_note_instruction(), _close_github_issue(), _collect_recent_git_context(), _fetch_github_quick_notes(), _gh_repo() (+31 more)

### Community 70 - "TokenBudget"
Cohesion: 0.05
Nodes (34): BudgetUsage, Any, agent/token_budget.py — Per-Session Token Spend Caps Track token usage per…, Raise :class:`BudgetExceededError` if the session has exceeded its cap., Reset usage counters for *session_id* (cap is preserved)., Reset token counters for all sessions (caps preserved). Called at the start of…, Reset all budgets if the UTC calendar day has changed since last reset. Safe to…, Generate a token savings analytics report. Returns per-session statistics and… (+26 more)

### Community 71 - "HybridSystem"
Cohesion: 0.05
Nodes (29): ConfidenceLevel, DeterministicEngine, HybridSystem, LLMReasoner, Any, Enum, str, Hybrid AI — combine deterministic rule engines with LLM reasoning. Implements a… (+21 more)

### Community 72 - "OrchestratorSupervisor"
Cohesion: 0.04
Nodes (35): Return orchestrator queue depth, active runs, and supervisor state (#522)., #522 + #505: Reliability startup — schedule hydration, orchestrator restore,…, _startup_reliability_hooks(), workflow_orchestrator_status(), codeql_count(), dependabot_count(), main(), Any (+27 more)

### Community 73 - "Specialist"
Cohesion: 0.05
Nodes (37): SpecialistFamily, Find all specialists of a specific family., Find specialists that can handle a task with given capabilities., A specialist agent that can be provisioned for company-specific tasks., Check if this specialist can handle a task with given capabilities., Specialist, SystemType, Get a specialist by ID. (+29 more)

### Community 74 - "test_model_catalog.py"
Cohesion: 0.05
Nodes (66): _build_base_url_env_from_yaml(), _build_candidates_from_yaml(), _build_default_base_url_from_yaml(), _build_display_names_from_yaml(), _build_key_env_from_yaml(), _build_presets_from_yaml(), _build_tier_from_yaml(), get_provider_candidates() (+58 more)

### Community 75 - "setup/api.py"
Cohesion: 0.07
Nodes (63): complete_wizard(), _delete_wizard_state(), detect_configured_providers(), detect_hardware_for_wizard(), detect_models_for_wizard(), _detect_ollama_models(), get_setup_state(), _get_state_file() (+55 more)

### Community 76 - "TestClient"
Cohesion: 0.10
Nodes (30): bare_repo(), _call(), _data(), git_config_env(), _is_error(), mcp_workspace_root(), fixture, Path (+22 more)

### Community 77 - "RewardScorer"
Cohesion: 0.05
Nodes (32): _infer_parameters_from_func(), Infer a basic JSON Schema from a function's signature., _inject_tool_results_as_messages(), _normalize_tool_choice(), _parse_tool_calls_from_response(), Parse OpenAI tool_calls from a model response. Handles: - Direct JSON…, Normalize the ``tool_choice`` parameter for the upstream backend. OpenAI…, Inject tool call results as follow-up messages for multi-turn execution. When… (+24 more)

### Community 78 - "telegram_bot.py"
Cohesion: 0.06
Nodes (64): all_provider_ids(), _provider_ids_from_literal(), Return every provider id recognised by the brain config system. Iterates the…, Return the provider ids allowed by the ``BrainProvider`` Literal. Reads the…, get_decisions_store(), Process-wide DecisionsStore singleton (resettable via db_path arg)., Return a Markdown-v1-safe preview string under ``max_chars``. Used by the…, sanitize_paste_for_preview() (+56 more)

### Community 79 - "test_colibri_brain_shim.py"
Cohesion: 0.05
Nodes (63): get_brain_preference(), Return the operator's brain provider preference. Values: - ``"nvidia"`` —…, colibri_enabled(), colibri_provider_config(), colibri_status(), ProviderConfig, providers/colibri.py — Free local GLM-5.2 brain served by JustVugg/colibri.…, Return True iff the operator opted in via ``COLIBRI_ENABLED=true``. (+55 more)

### Community 80 - "test_repo_connection.py"
Cohesion: 0.07
Nodes (49): DeliveryPolicy, How code lands on a repo's default branch (detected, GitHub-only for now). The…, A company's connection to a code repository (GitHub-only this pass). URL-only…, RepoConnection, attach_repo_connection(), build_repo_connection(), decide_merge(), detect_delivery_policy() (+41 more)

### Community 81 - "Troubleshooting"
Cohesion: 0.03
Nodes (64): 401 Unauthorized, 403 Forbidden from remote machine, 429 Too Many Requests, Admin Dashboard Issues, Agent API Issues, Agent makes a change but doesn't verify correctly, Agent returns empty or incomplete plan, Agent workspace errors ("file not found") (+56 more)

### Community 82 - "FetchResult"
Cohesion: 0.07
Nodes (27): MockTransport, browser_backend_available(), BrowserFetcher, FetchResult, HttpxFetcher, looks_blocked(), make_fetcher(), AsyncBaseTransport (+19 more)

### Community 83 - "test_bedrock_provider.py"
Cohesion: 0.05
Nodes (22): _is_bedrock_model_id(), Return True if model_id is an AWS Bedrock model or inference profile ID., _bedrock_api_response(), _bedrock_provider(), _mock_boto3(), Any, asyncio, ProviderConfig (+14 more)

### Community 84 - "ModelRouter"
Cohesion: 0.06
Nodes (36): Dynamic model router package. Public API:: from router import get_router,…, _build_builtin_model_map(), _default_model(), _default_reasoning_model(), ModelRouter, _nvidia_key_present(), Any, Dynamic model router. Central routing logic for all chat and agent requests.… (+28 more)

### Community 85 - "TestClient"
Cohesion: 0.08
Nodes (43): _auth_headers(), _build_agent_http_mock(), _exec(), _fake_request(), _mcp_tool_response(), _multi_step_plan(), _nim_post_factory(), _one_step_plan() (+35 more)

### Community 86 - "FailureCategory"
Cohesion: 0.05
Nodes (33): filter_safe_tools(), get_tool_annotations(), Typed representation of MCP tool annotations (spec 2025-11-05 §5.6.1). All…, Return True only when the tool is definitively read-only and non-destructive.…, Extract ``ToolAnnotations`` for a named tool from a ``list_tools()`` result.…, Return tools where ``readOnlyHint`` is True and ``destructiveHint`` is not…, ToolAnnotations, FailureCategory (+25 more)

### Community 87 - "Artifact"
Cohesion: 0.06
Nodes (38): AgentRole, Return the agent role responsible for *phase*., Return the AgentProfile for the agent driving *phase*., Run a pre-gate or report phase through the correct agent. Enforces permission…, Execute a slice via the Coder agent (write-permitted)., Review a slice via the Reviewer agent (different model from Coder). This is the…, Run verification commands via the Verifier agent. The Verifier is execution-…, Return a copy of *routing* with the profile's model injected for its role. (+30 more)

### Community 88 - "seo_api.py"
Cohesion: 0.05
Nodes (50): delegate_seo_findings(), _expire_stale_pending_report(), get_seo_audit(), list_seo_audits(), BaseModel, get, post, SEO / GEO / AIO Audit API Router Endpoints for the world-class SEO audit engine… (+42 more)

### Community 89 - "test_brain_failover.py"
Cohesion: 0.05
Nodes (49): BrainFailoverManager, get_failover_manager(), Permit one probe call without claiming the provider succeeded. This is the…, Seconds until the soonest cooling provider is probeable again. ``None`` when no…, True when a provider's cooldown window is wider than any it could legitimately…, Record a provider failure — opens the circuit breaker on threshold., Map a requested model to the provider's equivalent. If the requested model is…, Maximum number of provider attempts before giving up. (+41 more)

### Community 90 - "WebReach"
Cohesion: 0.07
Nodes (47): Decorator to register a function as an agent tool. Usage::…, Register the built-in agent tools that are always available., Register the Web Reach capability (agent/web_reach.py): zero-key internet…, _register_builtin_tools(), _register_web_reach_tools(), get_web_reach(), _load_script_module(), Any (+39 more)

### Community 91 - "AgileSprint"
Cohesion: 0.05
Nodes (24): AgileSprint, An agile sprint containing user stories., Add a user story to the sprint., Remove a user story from the sprint., Total story points in the sprint., Completed story points., Return completed points history for burndown chart., Number of stories in the sprint. (+16 more)

### Community 92 - "ChatPage.js"
Cohesion: 0.06
Nodes (49): cancelAgentChatJob(), chatSend(), deleteSession(), getAgentChatJob(), getSession(), listProviderModels(), listSessions(), resumeAgentChatJob() (+41 more)

### Community 93 - "FinancialMetrics"
Cohesion: 0.06
Nodes (46): BudgetOptimizer, CostLine, FinancialAgent, FinancialMetrics, Enum, str, Agentic CFO — autonomous financial analyst for AI infrastructure spend.…, Reallocate budget across cost lines to maximize total ROI under a fixed budget… (+38 more)

### Community 94 - "LogWatcher"
Cohesion: 0.05
Nodes (33): _auto_file_enabled(), ErrorFingerprint, LogEntry, LogWatcher, log_watcher.py — Automated log monitoring agent. Watches log files, detects…, A single error entry extracted from a log file., Generates stable fingerprints for error deduplication., Create a hash from error type, file, and normalized message pattern. (+25 more)

### Community 95 - "TrafficDirector"
Cohesion: 0.06
Nodes (34): provider_max_parallel(), provider_max_tpm(), _provider_positive_float(), provider_weight(), Shared parse/validate for the numeric per-provider traffic budgets. Returns…, Return the operator-configured tokens/min cap for *provider*. Reads…, Return the operator-configured share weight for *provider*. Reads…, Return the operator-configured in-flight request cap for *provider*. Reads… (+26 more)

### Community 96 - "test_self_heal_v2.py"
Cohesion: 0.05
Nodes (51): Reset the singleton (for tests)., reset_failover_manager(), _heal_brain_failover(), _heal_stuck_tasks(), _heal_task_duplicates(), _heal_telegram(), _heal_timestamps(), Any (+43 more)

### Community 97 - "WorkspaceTools"
Cohesion: 0.05
Nodes (36): Path, tools.py — WorkspaceTools: read/write/search and diff application (risky…, Return a previously saved memory value, or an empty string if absent., Persist a key/value pair to the user's profile store., Return the first *lines* lines of a file. Just-in-time retrieval: the executor…, Return a lightweight index of files with line counts and sizes. This is the…, Delegate to RepowiseIntelligence for a natural-language codebase question., Delegate to RepowiseIntelligence for a semantic/text codebase search. (+28 more)

### Community 98 - "Agent"
Cohesion: 0.06
Nodes (24): Agent, Grab Multi-Agent Support — Agent and TeamCoordinator with capability matching.…, Release a task from an agent., List all currently available agents., List agents with a capability, ordered by load., Average load across all team members., Number of agents in the team., An agent with capabilities and workload tracking. (+16 more)

### Community 99 - "tasks/api.py"
Cohesion: 0.12
Nodes (59): BackgroundTasks, add_comment(), approve_checkpoint(), approve_execution(), clarify_task(), create_task(), _current_user(), delete_task() (+51 more)

### Community 100 - "useSafeData"
Cohesion: 0.05
Nodes (32): API, changeUserRole(), createApiKey(), deleteApiKey(), getCompanyGraph(), setUserOnboarding(), useSafeData(), AdminOnboardingPanel() (+24 more)

### Community 101 - "DetectedSystem"
Cohesion: 0.05
Nodes (42): DetectedSystem, A business system detected on a company's website or in their stack., Get the most confident evidence description., OnboardingService, Workflow, Detect the Git provider from a repository URL. Args: repo_url: Repository URL…, Start the onboarding process for a company. Args: company_id: Company ID…, Schedule a fire-and-forget background task, keeping a strong reference.… (+34 more)

### Community 102 - "SeoFixer"
Cohesion: 0.08
Nodes (25): Request to remediate auto-fixable findings in a local code repository., One concrete remediation performed (or proposed) by the fixer., Result of a fixer run., SeoFixAction, SeoFixRequest, SeoFixResult, _humanize_filename(), BeautifulSoup (+17 more)

### Community 103 - "StreamingDeltaReconstructor"
Cohesion: 0.06
Nodes (31): PostProcessHook, get_chat_history(), Return the module-level ChatHistoryStore singleton., Enum, How to truncate messages when over the context limit., Result of a context window truncation operation., TruncationResult, TruncationStrategy (+23 more)

### Community 104 - "resolve_e2b_config"
Cohesion: 0.05
Nodes (54): Available iff config resolves AND the SDK is importable. Never raises — a…, e2b_enabled(), E2BConfig, _env_falsy(), _env_truthy(), services/e2b_config.py — Single reader of E2B sandbox environment config.…, Return ``True`` when E2B sandboxing should be activated. **EXPERIMENTAL…, Resolve the E2B sandbox config from env, or ``None`` when unconfigured. This is… (+46 more)

### Community 105 - "probe_model_liveness"
Cohesion: 0.05
Nodes (46): provider_api_key(), Return the live API key for *provider* (env-only — never persisted)., _describe_http_status(), probe_model_liveness(), _probe_ollama(), _probe_openai_compat(), ProbeResult, BaseModel (+38 more)

### Community 106 - "test_integration_c4_c5_c6_d3.py"
Cohesion: 0.06
Nodes (37): get_current_trace_id(), get_tracer(), langfuse_metadata_with_trace(), _NoOpSpan, _NoOpTracer, otel_middleware_factory(), otel_status_error(), otel_status_ok() (+29 more)

### Community 107 - "run_tests"
Cohesion: 0.07
Nodes (37): _login_api(), main(), _navigate_auth_callback(), _navigate_logged_out(), Page, Navigate directly to the AuthCallback page with query params., Social login buttons on the LoginPage., Verify the login page renders. (+29 more)

### Community 108 - "ArtifactStore"
Cohesion: 0.07
Nodes (27): fixture, Path, tests/test_artifact_store.py — Unit tests for workflow/artifact_store.py., Verify artifacts that are stored as JSON (e.g., CheckRun results)., Writing the same (run_id, name) twice should update, not duplicate., store(), TestArtifactStoreDeletion, TestArtifactStoreJSONArtifact (+19 more)

### Community 109 - "KnowledgeGraph"
Cohesion: 0.05
Nodes (24): KnowledgeGraph, KnowledgeNode, Enum, Obsidian Knowledge Graph — KnowledgeNode and KnowledgeGraph with typed edges.…, Find all connected components (treating edges as undirected)., Find all nodes with a given tag., Export all edges as (source, target, edge_type) tuples., Import edges from (source, target, edge_type) tuples. (+16 more)

### Community 110 - "LLMRouter"
Cohesion: 0.06
Nodes (33): Attempt, payload_key(), Exact-match cache key over the fields that change the answer. Routing…, text_key(), Read the environment variables named in ``env_names`` into a key list. Order is…, resolve_keys(), LLMRouter, Any (+25 more)

### Community 111 - "services/seo_audit.py"
Cohesion: 0.07
Nodes (36): BaseModel, models/seo_audit.py - SEO / GEO / AIO Audit Contracts Typed Pydantic models for…, A single occurrence of a check firing on a specific URL., Snapshot of one crawled page with the on-page facts the checks used., Aggregated report row - Screaming Frog CSV compatible., Site-level facts discovered during the crawl., An agent-delegable remediation work package derived from the findings. Findings…, Lightweight listing entry for past audits. (+28 more)

### Community 112 - "TaskIn"
Cohesion: 0.05
Nodes (41): _active_primary_provider(), is_north_mini_code_default(), True when the ``NORTH_MINI_CODE_DEFAULT`` flag is on (default ON). Reads the…, Best-effort read of the active brain's primary provider (or ``None``)., Resolve the model id to force for a code-execution run, or ``None``. Returns…, resolve_coding_model_preference(), _check_auth(), health() (+33 more)

### Community 113 - "ai_runner.py"
Cohesion: 0.07
Nodes (52): append_checkpoint(), _build_claude_command(), cmd_audit(), cmd_changelog_check(), cmd_logs(), cmd_manifest(), cmd_resume(), cmd_start() (+44 more)

### Community 114 - "test_sqlite_store.py"
Cohesion: 0.06
Nodes (56): asyncio, tests/test_sqlite_store.py — Unit tests for the SQLite storage adapter. These…, The exact query shape backend/server.py's provider "Set default" uses: clear…, Unfiltered count uses the SELECT COUNT(*) fast path and must match the number…, estimated_document_count mirrors an unfiltered count_documents., db['tasks'] must work like db.tasks (motor exposes both)., TaskStore(db=SQLiteStore) must not raise 'not subscriptable'. This is the exact…, B608 guard: all collections in _COLLECTIONS must still be instantiable. (+48 more)

### Community 115 - "test_context_rulebook.py"
Cohesion: 0.06
Nodes (54): Module, stmt, _bound_names(), _good_result(), _guard_statements(), _load(), fixture, ModuleType (+46 more)

### Community 116 - "test_issue_intake.py"
Cohesion: 0.07
Nodes (52): _capability_tags(), create_task_from_oldest_open_issue(), intake_issue(), _issue_labels(), issue_source_id(), map_issue_to_task(), Any, Task (+44 more)

### Community 117 - "ImprovementLoop"
Cohesion: 0.08
Nodes (31): DetectedIssue, ImprovementLoop, ImprovementLoopState, _now(), Any, Path, Background scanner and task dispatcher for continuous codebase improvement.…, Run a scan immediately (blocking). Returns newly detected issues. (+23 more)

### Community 118 - "Command"
Cohesion: 0.06
Nodes (22): Command, CommandCategory, CommandDispatcher, Enum, SuperClaude Slash Commands — CommandDispatcher with registration, role gating,…, Parse and execute a slash command from raw text. Args: text: Raw command text,…, Return all enabled commands in a given category., Return all registered commands. (+14 more)

### Community 119 - "ProvidersScreen.jsx"
Cohesion: 0.05
Nodes (40): createProvider(), deleteModel(), deleteProvider(), getBrainConfig(), getBrainProviders(), getLocalBrainState(), getProviderPolicy(), listModels() (+32 more)

### Community 120 - "WorkflowEngine"
Cohesion: 0.08
Nodes (30): Any, Connection, Path, PhaseType, WorkflowRun, CRISPY workflow engine — phase sequencer + gate controller. GATE: Golden Path…, Return the AgentSwarm singleton if available, else None., Append an event to the workflow event log. (+22 more)

### Community 121 - "InferenceCache"
Cohesion: 0.06
Nodes (27): CachedLLMClient, Any, Cached LLM Client wrapper. Drop-in wrapper around any LLM API call that…, Return performance metrics for this client instance., Try to extract token count from various response formats., Wraps an LLM call function with inference caching. Usage: from agent.cached_llm…, Execute an LLM completion, using cache when available. Args: model: Model…, CacheEntry (+19 more)

### Community 122 - "CheckpointStore"
Cohesion: 0.09
Nodes (27): Checkpoint, checkpoint_agent_state(), _checkpointing_enabled(), CheckpointStore, cleanup_checkpoints(), _get_checkpoint_store(), Any, Path (+19 more)

### Community 123 - "CoworkSession"
Cohesion: 0.06
Nodes (17): ContributorState, CoworkSession, Enum, str, Claude Cowork — shared AI coding sessions with real-time sync. Enables multiple…, A shared AI coding session with multiple human contributors. Manages turn-…, Request editing control. Returns True if granted. Grant rules: - Host can…, Role within a cowork session. (+9 more)

### Community 124 - "test_startup_warmup.py"
Cohesion: 0.05
Nodes (49): _bootstrap_within_budget(), Await one warm-up step, deferring it to the background if it overruns.…, The task store the background services should use, wiring it if needed.…, Run bootstrap without letting it hold a request open indefinitely. Returns…, _task_store_for_background(), _warmup_step(), defer_to_background(), Any (+41 more)

### Community 125 - "test_kimi_bridge_server.py"
Cohesion: 0.06
Nodes (37): chat_completions(), ChatCompletionRequest, _content_to_str(), _ContentPart, health(), lifespan(), list_models(), _Message (+29 more)

### Community 126 - "App.js"
Cohesion: 0.06
Nodes (32): getAccountLifecycle(), getMe(), logout(), App(), AppRoutes(), ProtectedRoute(), SetupGuard(), V5App (+24 more)

### Community 127 - "resolve_active_brain"
Cohesion: 0.07
Nodes (51): allow_paid_brain(), BrainResolution, get_active_brain_sync(), get_provider_role_tags(), _host_is_openai_compatible(), _norm(), _pick_from_records(), Any (+43 more)

### Community 128 - "TestPayloadNormalisation"
Cohesion: 0.06
Nodes (28): _as_list(), _coerce_payload(), Any, packages/integrations/render_mcp.py — Render platform access over MCP. The…, Return tool output as Python data. MCP tool results arrive either as…, Normalise a tool payload into a list of dicts. Upstream tools variously return…, Unwrap a nested envelope such as ``{"service": {...}}`` when present., Run the MCP handshake once per client instance. Streamable-HTTP servers create… (+20 more)

### Community 129 - "TaskDispatcher"
Cohesion: 0.06
Nodes (39): _env_flag(), Read a boolean env var. Accepts 'true'/'1'/'yes' (case-insensitive)., Re-queue BLOCKED tasks that have cooled down and are ready for retry., Polls for queued task work and executes it through the coordinator. Crash…, Re-queue tasks stranded by a prior crash or hard-kill., TaskDispatcher, Dispatcher should track first_seen times for pending tasks., Executing a task removes it from _first_seen and logs pickup time. Uses async… (+31 more)

### Community 130 - "ChatHistoryStore"
Cohesion: 0.07
Nodes (26): ChatHistoryStore, Any, Connection, Delete a session and all its messages. Returns True if deleted., List sessions ordered by most recently updated., Return total session and message counts., Append a message to the session. Returns the message's sequence number.…, Append multiple messages at once. Returns number of messages appended. (+18 more)

### Community 131 - "WorkspaceManager"
Cohesion: 0.05
Nodes (13): If a symlink inside the workspace points outside, resolve_path blocks it., Only expired workspaces (past retention TTL) are cleaned up., Two threads creating the same session/job should not corrupt state., TestWorkspaceLifecycle, TestWorkspaceManifest, TestWorkspaceResume, Any, First-class workspace isolation manager. Every session/job gets its own… (+5 more)

### Community 132 - "ToolRegistry"
Cohesion: 0.07
Nodes (23): Any, Path, Register a tool definition., Remove a tool from the registry. Returns True if removed., Look up a tool by name., Return all registered tools., Find tools that advertise a specific capability., Find tools matching any of the given capabilities. (+15 more)

### Community 133 - "ReactScratchpad"
Cohesion: 0.06
Nodes (22): Declarative configuration for a specialized sub-agent role. Each sub-agent gets…, SubAgentConfig, build_react_prompt(), parse_react_response(), Any, Parse a ReAct-format response into structured components. Intended caller:…, Structured scratchpad that accumulates across tool calls within a step. Each…, Record a reasoning step before taking action. (+14 more)

### Community 134 - "E2BAdapter"
Cohesion: 0.07
Nodes (39): E2BAdapter, Any, Declare ``E2B_API_KEY`` as a required env dependency. The base ``preflight``…, Runtime adapter that executes tasks inside an E2B sandbox. Activation:…, _clean_e2b_env(), _FakeAsyncSandboxClass, _FakeCommandResult, _FakeCommands (+31 more)

### Community 135 - "_ts_to_float"
Cohesion: 0.06
Nodes (37): Any, Task, TaskStatus, Create a task. Deduplicates by source_id if set (Charter G3). If a task with…, Fetch a task by ID. If owner_id is set, enforces ownership., Return the task previously created for an external ``source_id`` (e.g.…, Normalise a timestamp value to a float Unix epoch. Handles: - float / int…, Admin-only: list all tasks across all users. (+29 more)

### Community 136 - "test_telegram_freebuff.py"
Cohesion: 0.07
Nodes (47): cmd_freebuff(), _model_keyboard(), _parse_callback(), _parse_user_ids(), _process_callback(), Extract numeric Telegram user IDs from a raw env value, tolerantly. Accepts…, Resolve the ALLOWED/ADMIN Telegram user-ID sets. ``TELEGRAM_CHAT_ID`` is the…, Send a message with an inline keyboard (list of button rows). (+39 more)

### Community 137 - "api.ts"
Cohesion: 0.09
Nodes (44): adminBootstrap(), adminCreateProvider(), adminCreateWorkspace(), adminDeleteProvider(), adminDeleteWorkspace(), adminGetBrainPolicy(), adminGetProviderRoleTags(), adminHeaders() (+36 more)

### Community 138 - "WorkspaceManager"
Cohesion: 0.08
Nodes (32): _get_workspace_lock(), get_workspace_manager(), _hash_component(), _iso_now(), _iso_offset_hours(), _load_workspace(), _parse_iso(), BaseModel (+24 more)

### Community 139 - "AgileManager"
Cohesion: 0.05
Nodes (23): AgileManager, Manages multiple agile sprints with velocity tracking., List all active sprints., Predict next sprint velocity from historical data., Number of managed sprints., CapacityAllocation, InitiativeProgress, Enum (+15 more)

### Community 140 - "tests/conftest.py"
Cohesion: 0.06
Nodes (48): _get_current_user_thunk(), _get_optional_user_thunk(), Request, get_current_user(), get_optional_user(), Get user if authenticated, otherwise return None (for public endpoints)., Item, app_client() (+40 more)

### Community 141 - "persist_plan_spec"
Cohesion: 0.07
Nodes (38): build_spec_router(), Any, APIRouter, backend/spec_router.py — review/approve persisted plan specifications. Surfaces…, await_spec_approval(), _db(), _flag(), get_spec() (+30 more)

### Community 142 - "test_seo_audit.py"
Cohesion: 0.07
Nodes (24): analyze_page(), _count_syllables(), estimate_pixel_width(), flesch_reading_ease(), _host_key(), is_internal(), normalize_url(), BeautifulSoup (+16 more)

### Community 143 - "test_trend_scoping.py"
Cohesion: 0.10
Nodes (47): _company_attr(), company_stack_tags(), extract_stack_tags(), fan_out_trend(), fan_out_trends(), is_code_change_trend(), map_trend_to_company_task(), Any (+39 more)

### Community 144 - "Usage"
Cohesion: 0.08
Nodes (29): AlertHandler, BudgetTracker, Counter, _Dimensions, get_budget(), _month(), Any, packages/llm/budget.py — token and cost accounting with spend alerts. Tracks… (+21 more)

### Community 145 - "test_slop_gate.py"
Cohesion: 0.07
Nodes (44): _extract_mentioned_paths(), Pick the auto-PR model from the recommended free-cloud chain by key. Mirrors…, Extract plausible file paths from issue text., Read existing files for codebase context (max 8000 chars total)., _read_grounding_files(), _select_brain(), diff_is_sloppy(), is_destructive_overwrite() (+36 more)

### Community 146 - "system_instruction"
Cohesion: 0.07
Nodes (16): extract_refusal(), is_strict(), Any, Structured output normalization across LLM providers. Translates the OpenAI…, Extract the ``refusal`` string from an OpenAI-format response body. Returns the…, Return True when the caller has requested strict schema enforcement. Strict…, Return a plain-English JSON instruction for a ``response_format`` dict. Returns…, system_instruction() (+8 more)

### Community 147 - "test_e2b_task_wiring.py"
Cohesion: 0.08
Nodes (43): _build_coordinator(), _clean_e2b_env(), _FakeCompany, _FakeCompanyGraphStore, _FakeRepoConnection, _make_task(), fixture, Task (+35 more)

### Community 148 - "activation_api.py"
Cohesion: 0.09
Nodes (46): activate_instance(), ActivateRequest, ActivateResponse, activation_audit_log(), activation_status(), ActivationStatusResponse, _append_audit(), AuditLogEntry (+38 more)

### Community 149 - "MetricsRegistry"
Cohesion: 0.08
Nodes (23): _Counter, _escape(), _Gauge, _Histogram, _labels(), MetricsRegistry, Any, packages/llm/metrics.py — Prometheus metrics without the client library. The… (+15 more)

### Community 150 - "OllamaCircuitBreaker"
Cohesion: 0.08
Nodes (37): _Circuit, _enabled(), _failure_threshold(), get_circuit_breaker(), OllamaCircuitBreaker, Per-model circuit breaker for Ollama backend health. Tracks consecutive failure…, Record a successful response; close the circuit., Record a 5xx error; open the circuit after threshold is reached. (+29 more)

### Community 151 - "fixture"
Cohesion: 0.05
Nodes (26): fixture, skip, Test iteration 7 features: - POST /api/tasks/ auto-assigns an available agent…, Test runtime start/stop endpoints return informational payloads in remote…, POST /runtimes/{id}/start should return 200 with informational payload (not 500), POST /runtimes/stop-all should return 200 with informational payload, Test that routing policy defaults allow paid fallback only with approval, GET /runtimes/policy should show never_use_paid_providers=false and… (+18 more)

### Community 152 - ".get_workspace"
Cohesion: 0.08
Nodes (25): _derive_workspace_root(), Path, WorkspaceStatusLiteral, Create an isolated workspace for a session and optional job. Creates the…, Retrieve the WorkspaceManifest for a given session and optional job. Looks up…, List all known workspaces, optionally filtered by status., Mark a workspace as active (in-use)., Pause a workspace (e.g. between agent steps). (+17 more)

### Community 153 - "AdaptiveHalter"
Cohesion: 0.07
Nodes (17): AdaptiveHalter, Any, ★7 Adaptive Loop Halting — velocity-based agent run termination. Complements…, Return current halter state for logging / telemetry., Tracks step-level progress and signals when a run should halt early. The halter…, Ratio of applied steps to steps attempted (0.0–1.0). Returns 1.0 when no steps…, Record one step outcome; return a halt reason or None to continue. ``status``…, MCPToolResult (+9 more)

### Community 154 - "render_ops.py"
Cohesion: 0.06
Nodes (33): build_render_router(), Any, APIRouter, Exception, backend/render_router.py — Render platform view for operators and agents.…, Reject anyone who is not the agency admin., Map an MCP transport failure onto 503 rather than a 500. The distinction…, _require_admin() (+25 more)

### Community 155 - "diagnostics.py"
Cohesion: 0.08
Nodes (43): _check_background_liveness(), _check_ci_parity(), _check_company_graph(), _check_disk(), _check_event_log_integrity(), _check_feature_matrix(), _check_github_readiness(), _check_ollama() (+35 more)

### Community 156 - "SeoAuditRequest"
Cohesion: 0.05
Nodes (20): field_validator, Request to run an SEO/GEO/AIO audit against a website., SeoAuditRequest, Run an audit from synchronous code, loop-safe. Used by the skill-bindings…, Pick the fetch backend for this run (http / browser / auto)., Execute the full audit: crawl, page checks, site checks, scoring., run_audit_sync(), mock_report() (+12 more)

### Community 157 - "SetupChecker"
Cohesion: 0.07
Nodes (25): main(), OllamaManager, OsDetector, Path, Detect operating system and available interpreters., Return normalized OS name., Detect PowerShell (Windows) or Bash (Unix)., Print colored message. (+17 more)

### Community 158 - "PromptCacheManager"
Cohesion: 0.06
Nodes (20): CacheEntry, CacheStats, get_prompt_cache(), PromptCacheManager, Any, Compute a deterministic cache key from the stable prefix. The stable prefix is…, Hash a system prompt and model for KV cache fingerprinting., Return the instance ID that has this prefix cached, or None. Performs an LRU… (+12 more)

### Community 159 - "activation.py"
Cohesion: 0.08
Nodes (41): activation_required(), ActivationResult, _b64url_decode(), _b64url_encode(), _decode_jwt_unverified(), _generate_token_for_owner(), get_activation(), get_or_create_instance_id() (+33 more)

### Community 160 - "test_quick_note.py"
Cohesion: 0.08
Nodes (30): _fetch_text(), _now(), process_note(), Any, Path, QuickNote, agent/quick_note.py — iPhone Quick Note integration. Persistent URL queue +…, GET *url* and return plain text (HTML tags stripped, max *max_chars*). (+22 more)

### Community 161 - "TrendWatcher"
Cohesion: 0.13
Nodes (15): Any, AsyncClient, Path, Fetches AI trend signals from many public sources and surfaces relevant ones., Fetch all sources in parallel; return new alerts sorted by relevance., Fan trends out to onboarded companies whose stack matches (G4). For each…, Dispatch high-relevance alerts to the Hermes sidecar for action. Only…, TrendAlert (+7 more)

### Community 162 - "test_audit.py"
Cohesion: 0.07
Nodes (39): AuditMessage, AuditSession, create_session(), delete_session(), get_session(), list_sessions(), Any, Audit session management for multi-turn conversations. This module provides in-… (+31 more)

### Community 163 - "test_features_api.py"
Cohesion: 0.05
Nodes (5): _auth_override(), client(), _fake_auth(), fixture, Integration tests for all new feature API routes in proxy.py.

### Community 164 - "test_video_transcript.py"
Cohesion: 0.05
Nodes (34): fixture, parametrize, Tests for video transcript extraction (`.github/scripts/video_transcript.py`).…, Events without `segs` carry no text and must not produce stray spaces., This format double-encodes: `&amp;#39;` must resolve to a single quote., Regex-terminated matching truncates this; brace matching must not. The blob…, A title containing a brace must not unbalance the matcher., An unfamiliar page shape must yield empties, never raise. (+26 more)

### Community 165 - "OnboardingScreen.jsx"
Cohesion: 0.06
Nodes (28): createCompany(), getCompany(), getOnboardingProgress(), listSpecialists(), scanRepo(), scanWebsite(), startOnboarding(), submitOnboardingAnswers() (+20 more)

### Community 166 - "portfolio_api.py"
Cohesion: 0.09
Nodes (38): add_initiative(), AllocationOut, BoardOut, get_board(), get_service(), InitiativeIn, InitiativeOut, _materialize_and_log() (+30 more)

### Community 167 - "[Unreleased]"
Cohesion: 0.05
Nodes (42): [5.0.0], Added, Added, Added, Added, Added, Added, Added (+34 more)

### Community 168 - "Part A — CodeRabbit review fixes for this PR (do first, small)"
Cohesion: 0.05
Nodes (42): A1 — `docs/changelog.md`: add the two autonomy docs under `### Added` ✅ trivial, A2 — `docs/telegram-bot.md`: fix broken charter links (MD + path), A3 — `docs/telegram-bot.md`: add language to fenced block (MD040), A4 — `.env.example`: use exact var name in the shortcut comment, A5 — `services/workflow_orchestrator.py`: surface notify failures at WARNING, A6 — `telegram_bot.py`: avoid double-approve in the `wfo_approve` path ⚠️ behavioural, A7 — `telegram_service.py`: escape Markdown-v1 reserved chars in approval text ⚠️ correctness, A8 — `render.yaml`: propagate Telegram vars to the worker service (+34 more)

### Community 169 - "[Unreleased]"
Cohesion: 0.05
Nodes (42): [5.0.0], Added, Added, Added, Added, Added, Added, Added (+34 more)

### Community 170 - "Docker Agent Runtimes Setup"
Cohesion: 0.05
Nodes (41): 1. Register Runtimes, 2. Verify Installation, 3. Access Agents via API, Agent Runtime Setup, Agents not appearing in API responses, Initial Setup, MongoDB Connection, No agents showing after registration (+33 more)

### Community 171 - "TasksPage.js"
Cohesion: 0.06
Nodes (31): addTaskComment(), clarifyTask(), escalateTask(), fetchVelocity(), followUpTask(), updateTask(), C, COLS (+23 more)

### Community 172 - "test_e2b_data_flow.py"
Cohesion: 0.08
Nodes (32): _clean_e2b_env(), fake_sandbox(), _FakeCmdResult, _FakeCommands, _FakeFiles, _FakeSandbox, patched_async_sandbox(), Any (+24 more)

### Community 173 - "Persistent Memory System"
Cohesion: 0.05
Nodes (41): 1. **Semantic Memory Categorization**, 1. **Use Appropriate Scopes**, 2. **Prioritize Effectively**, 2. **Scope-Based Auto-Loading**, 3. **Priority-Based Retrieval**, 3. **Use Semantic Categories**, 4. **Cross-Tool Compatibility**, 4. **Tag Liberally** (+33 more)

### Community 174 - "resolve_component_model"
Cohesion: 0.06
Nodes (41): Resolve the model id for a component's role on a provider. Parameters…, Convenience: resolve all four role models for a component. Returns a dict with…, resolve_component_model(), resolve_component_role_models(), tests/test_unit6_resolve_component_model.py — UNIT 6 regression tests. Verifies…, When the DB cache is fresh AND provider matches the active primary, the DB-…, When the DB primary differs from the requested provider, the catalog preset for…, When `provider` is None, the DB primary's saved model wins. (+33 more)

### Community 175 - "SchedulerStore"
Cohesion: 0.08
Nodes (17): _MemCollection, _MemCursor, _MemDB, _MemDeleteResult, Any, services/scheduler_store.py — Durable scheduler persistence. Issue #505:…, Delete a persisted job., Return the total number of persisted jobs. (+9 more)

### Community 176 - "test_portfolio_intake.py"
Cohesion: 0.09
Nodes (35): map_initiative_to_task(), materialize_committed(), _portfolio_materialize_enabled(), portfolio_source_id(), Any, Task, tasks/portfolio_intake.py — Portfolio initiative → Task materializer. Converts…, Content-derived stable id for a portfolio initiative. Initiative UUIDs… (+27 more)

### Community 177 - "AGENTS.md — Source of Truth for All AI Agents"
Cohesion: 0.05
Nodes (41): Agent Escalation Rules, AGENTS.md — Source of Truth for All AI Agents, Alerts — What Should Wake You Up, Architecture Overview, Autonomous Maintenance Rules, Bug Triage Process, CI, Code Quality (+33 more)

### Community 178 - "emit_chat_observation"
Cohesion: 0.09
Nodes (33): observability_diag_public(), PUBLIC diagnostic endpoint for Langfuse — no auth required. Returns exactly…, CommercialEquivalent, estimate_commercial_equivalent_usd(), get_prices(), _load_from_env(), _parse_mapping(), Any (+25 more)

### Community 179 - "anthropic_compat.py"
Cohesion: 0.09
Nodes (29): _build_anthropic_response(), _emit_safely(), _finish_reason_to_stop_reason(), handle_anthropic_messages(), _messages_to_openai(), _openai_choice_to_anthropic_content(), _post_anthropic_with_fallback(), Any (+21 more)

### Community 180 - "test_agent_free_brain.py"
Cohesion: 0.05
Nodes (32): livenim, is_anthropic_model(), True when *model* names a paid Anthropic/Bedrock-Claude model. Covers native…, Resolve the free NVIDIA NIM brain from env, or ``None`` if unconfigured.…, resolve_free_nvidia_brain(), _FakeAsyncClient, _FakeResponse, _free_env() (+24 more)

### Community 181 - "ContextWindowManager"
Cohesion: 0.09
Nodes (16): ContextWindowManager, get_context_window_manager(), Any, Return True if the estimated tokens exceed the model's context limit., Truncate messages to fit within the model's context window. Args: messages:…, Return the context window size for a model. Looks up the model in the…, Estimate token count for a list of messages. Uses a character-based heuristic…, Estimate token count using tiktoken (more accurate, requires install). (+8 more)

### Community 182 - "IssueCategory"
Cohesion: 0.10
Nodes (37): IssueCategory, IssueSeverity, Enum, str, agent/improvement_loop.py — Continuous Improvement Engine Background scanner…, _file_issue(), Hand a finding to the existing ImprovementLoop intake. Returns True when the…, cluster_friction() (+29 more)

### Community 183 - "v4_api.py"
Cohesion: 0.10
Nodes (38): _get_cached_tasks(), _get_tasks_cache_lock(), _load_improvement_state(), Any, BaseModel, get, Lock, post (+30 more)

### Community 184 - "FeatureMatrix"
Cohesion: 0.09
Nodes (9): FeatureMatrix, Central support matrix — single source of truth. Loads the canonical feature…, Render the matrix as a Markdown table for docs., TestConfigOverrides, TestRegistryLoads, TestClassification, TestDisabledFeatures, TestMatrixSerialization (+1 more)

### Community 185 - "TestEstimateTokensForMessages"
Cohesion: 0.06
Nodes (13): _estimate_tokens_for_messages(), _normalize_anthropic_output_format(), Estimate input token count for an Anthropic-format message list. Uses a simple…, Translate Anthropic ``output_format`` into an Ollama ``format`` field. Modifies…, fixture, Daily automation tests — 2026-05-15 Covers three features implemented in this…, Integration tests for POST /v1/messages/count_tokens., Unit tests for _normalize_anthropic_output_format. (+5 more)

### Community 186 - "distributed.py"
Cohesion: 0.08
Nodes (20): DistributedRateLimiter, get_limiter(), get_persistent_queue(), _LocalBucket, PersistedRequest, PersistentQueue, Any, packages/llm/distributed.py — cross-instance coordination. Two facilities that… (+12 more)

### Community 187 - "TestClient"
Cohesion: 0.07
Nodes (26): backend_jwt(), proxy_client(), fixture, MonkeyPatch, TestClient, Regression test for /api/auth/me — verifies the critical endpoint on both the…, TestClient against proxy.py:app with a known API key seeded., API-key-based /api/auth/me on proxy.py (port 8000). (+18 more)

### Community 188 - "_run"
Cohesion: 0.07
Nodes (18): _patch_send_message(), tests/test_telegram_inbound.py Pytest coverage for the Step 1 inbound-routing…, ``_resolve_reply_to_decision`` returns the durable link from SQLite.\n, ``/redirect`` command: admin-only, prefix-dispatched, idempotent shape., ``/paste <abs-path>`` command: admin gate + path check + truncation., ``_handle_big_paste`` writes to disk and short-replies., ``_route_plain_text`` classifies and dispatches per the documented map., Return a Telegram nested-message-shaped dict for resolve-reply-to tests. (+10 more)

### Community 189 - "test_workspace_isolation.py"
Cohesion: 0.19
Nodes (24): Tests for workspace isolation model (Area A). Covers: - Unique workspace path…, TestConcurrency, TestCrossSessionIsolation, TestJobIdValidation, TestPathSafety, TestWorkspaceCleanup, TestWorkspaceMetrics, TestWorkspaceNotFound (+16 more)

### Community 190 - "PatternConsolidation"
Cohesion: 0.10
Nodes (9): PatternConsolidation, Group memories into clusters by tag overlap., Jaccard similarity of tag sets., Run the full consolidation cycle., Identifies clusters of related DreamMemory fragments and consolidates them into…, _make_memory(), Tests for agents.memory_consolidation — Dream Memory Consolidation., TestDreamMemory (+1 more)

### Community 191 - "getBackendUrl"
Cohesion: 0.10
Nodes (30): getAccessToken(), getApiUrl(), getAuthHeaders(), getBackendUrl(), ActivityEvent, AgentActivityFeedProps, ActivityEventRow(), AGENT_COLORS (+22 more)

### Community 192 - "test_portfolio_intelligence.py"
Cohesion: 0.06
Nodes (15): FakeResp, asyncio, Tests for agents/portfolio_intelligence.py — autonomous signal → initiative.…, DEFAULT_REPO was hardcoded to the stale pre-rename repo name…, fetch_github_signals must degrade gracefully (log + return empty lists) on a…, Even with a 200, a malformed/rate-limited body that isn't a list must not be…, fetch_research_alerts used asyncio.run() to await TrendWatcher().fetch(), which…, The exact scenario that crashed before the fix: called from code that is itself… (+7 more)

### Community 193 - "ContextPruner"
Cohesion: 0.09
Nodes (30): ContextPruner, Any, context_pruner.py — auto-generated module docstring (user-research skill scan)., Walk messages backward, accumulating per-role char counts. Returns…, Wrap evicted messages into ``<historical_memory_only>`` XML. The XML block is…, Reset the prune timer so the next call always runs the pipeline., 3-phase context window management middleware. Phase 1 — Truncate: Strips…, Apply 3-phase pruning if the context is over budget or cache expired. Returns… (+22 more)

### Community 194 - "V5App.jsx"
Cohesion: 0.06
Nodes (28): ActivationGate(), activityToAlert(), AlertsBell(), priorityConfig, _relativeTime(), typeIcon, QUEUED_NOTES, QuickNotesFAB() (+20 more)

### Community 195 - "ServiceDaemon"
Cohesion: 0.09
Nodes (26): configure(), get_status(), health(), BaseModel, get, post, Validate configured paths., Check if proxy is running. (+18 more)

### Community 196 - "DigestSummary"
Cohesion: 0.12
Nodes (24): aggregate_last_24h(), build_daily_digest(), compute_cutoff(), DigestSummary, format_digest_markdown(), _md_escape(), _now_utc(), Any (+16 more)

### Community 197 - "test_trend_watcher.py"
Cohesion: 0.09
Nodes (22): _FakeClient, asyncio, fixture, Tests for agent/trend_watcher.py, Ensure expanded keyword set covers key new categories., setup_database_moks(), test_fetch_arxiv(), test_fetch_github_trending() (+14 more)

### Community 198 - "test_agency.py"
Cohesion: 0.12
Nodes (34): _parse_ceo_directives(), agency(), asyncio, fixture, Path, Tests for agent/agency.py, With no issues, CEO should report nominal., CEO should parse valid JSON directive list from LLM response. (+26 more)

### Community 199 - "_Collection"
Cohesion: 0.11
Nodes (16): _apply_update(), _Collection, _DeleteResult, _InsertResult, _match(), _new_id(), _now_iso(), db/sqlite_store.py — Async SQLite storage backend. Provides a Motor-compatible… (+8 more)

### Community 200 - "test_persistent_memory.py"
Cohesion: 0.06
Nodes (36): memory_store(), fixture, Tests for persistent memory system., Test auto-loading global memories., Test auto-loading includes workspace-specific memories., Test that auto-load respects priority ordering., Test filtering memories by category., Create a temporary database for testing. (+28 more)

### Community 201 - "AgentJobResult"
Cohesion: 0.10
Nodes (14): AgentJobError, AgentJobResult, Any, field_validator, Structured error payload attached to a failed job., Typed result returned by a completed agent job. The ``response`` field is the…, Accept a bare string (legacy runner output) or a full dict., Build a snapshot from an ``AgentJob`` dataclass instance. (+6 more)

### Community 202 - "GitHubTools"
Cohesion: 0.15
Nodes (14): GitHubTools, Any, get, post, List issues (excludes pull requests) for triage/intake pipelines., Add labels to an issue (used to mark it as triaged, preventing reprocessing)., Merge an open pull request via the GitHub API., Backwards-compat: accepts 'owner/repo' format. (+6 more)

### Community 203 - "SecurityScanner"
Cohesion: 0.11
Nodes (26): _now(), Any, Path, agent/security_scanner.py — Security & Vulnerability Scanner Runs static…, Run all available scanners and aggregate results., Run a cross-harness security audit. Checks that the agent harness configuration…, Return True if *name* is on PATH., Return current UTC timestamp as ISO string. (+18 more)

### Community 204 - "test_verification_strategies.py"
Cohesion: 0.12
Nodes (32): cross_verify(), Any, race(), agent/verification_strategies.py — opt-in parallel patterns for high-stakes…, Heuristic fallback score when the reward model is unavailable.…, Run *n* independent attempts at *instruction* concurrently; return the winner.…, True if any path matches the repo's risky-module trigger list., Have an independent agent re-check a completed task's changed files. Returns… (+24 more)

### Community 205 - "test_backend_server_features.py"
Cohesion: 0.07
Nodes (22): _agent_provider_failure_response(), _append_agent_session_message(), _build_auto_skill_guidance(), _mask_observations(), Exception, ProviderConfig, Truncate tool/observation content in older messages to prevent context bloat., Fall back to a direct LLM call when the agent loop cannot reach any provider.… (+14 more)

### Community 206 - "REWRITE_PLAN.md — Phased Migration Strategy"
Cohesion: 0.06
Nodes (35): Already completed (pre-migration fixes), Current Status, Inventory of suspected dead code, Migration Safety Checklist, Phase 1: Foundation (Weeks 1-2), Phase 2: Provider Abstraction (Weeks 3-4), Phase 3: Auth Consolidation (Week 5), Phase 4: Scheduler Redesign (Week 6) (+27 more)

### Community 207 - "test_background_services.py"
Cohesion: 0.08
Nodes (23): Return True when the web process should also run background services., run_background_in_web(), anyio, Unit tests for services/background.py — start_background_services wiring.…, Scheduler's on_fire handler is set to TaskAutomation.handle_scheduled_job., Calling bg.stop() twice must not raise or double-stop., RUN_BACKGROUND_IN_WEB defaults to True., The constant itself must leave real margin under Render's 5s timeout. (+15 more)

### Community 208 - "NIMConnectionPool"
Cohesion: 0.08
Nodes (16): NIMConnectionPool, Any, AsyncClient, Response, Persistent httpx.AsyncClient pool with circuit breaker and retry logic. Manages…, Get or create the shared httpx.AsyncClient., Context manager for a pooled client session., Close the connection pool. (+8 more)

### Community 209 - "run_regression"
Cohesion: 0.11
Nodes (17): Page, Run fn() and report any critical console errors., Dashboard page — stats, activity, navigation., Agents: list, view status., Chat: send message, view sessions, delete session, agent mode toggle., Runtimes: list, health, decisions, policy., Settings, Secrets, Features, Setup, GitHub, Activation., GitHub integration: status, repos. (+9 more)

### Community 210 - "test_all_providers_discovery.py"
Cohesion: 0.16
Nodes (35): _get(), asyncio, ProviderRouter, Verify every supported provider is correctly discovered, prioritised, and…, Check if url hostname matches expected domain (exact or subdomain)., Build a ProviderRouter from_env() with only the supplied env vars active., _router(), test_anthropic_discovery() (+27 more)

### Community 211 - "report_to_markdown"
Cohesion: 0.10
Nodes (26): export_seo_audit(), Export a stored audit. - ``csv`` aggregated findings, Screaming Frog…, _build_curl_cffi_fetcher(), _build_pdf(), main(), _parse_args(), Namespace, Path (+18 more)

### Community 212 - "ScheduledJob"
Cohesion: 0.10
Nodes (16): _now(), Any, Register a new job. Returns the created :class:`ScheduledJob`.…, Fire a job immediately (webhook / manual trigger)., Update the display name of a job., Enable or disable a job without deleting it., Capture the FastAPI main event loop so APScheduler's background thread can…, Return the running event loop, or ``None`` when called synchronously. Used so… (+8 more)

### Community 213 - "JCodeAdapter"
Cohesion: 0.09
Nodes (12): JCodeAdapter, Any, Path, TaskResult, TaskSpec, Write .jcode/mcp.json in the workspace, pointing at our proxy's MCP endpoint.…, Resolve the default executor model via the catalog (UNIT 7). Was hardcoded to…, Adapter for jcode — TIER 2 high-performance Rust coding agent. (+4 more)

### Community 214 - "test_control_plane_api.py"
Cohesion: 0.07
Nodes (15): _FakeStore, mock_runtime_manager(), fixture, tests/test_control_plane_api.py — Tests for Control Plane API endpoints. Covers…, In-memory store stub for hydrate() tests — isolates from real DB., Stale run-once jobs (run_count > 0) must be skipped during hydration., Unfired run-once jobs (run_count == 0) must be rehydrated., Jobs already in memory must not be rehydrated (dedup by job_id). (+7 more)

### Community 215 - "agent_runtime.py"
Cohesion: 0.11
Nodes (32): _active_cloud_provider(), _candidate_ollama_bases(), _chat(), chat_completions(), _chat_with_ollama(), _chat_with_openai_compat(), ChatRequest, ChatResponse (+24 more)

### Community 216 - "ENGINEERING_STANDARDS.md — Coding, Security & Testing Standards"
Cohesion: 0.06
Nodes (33): 1. Coding Standards, 2. Logging Standards, 3. Security Standards, 4. Testing Standards, 5. CI/CD Standards, 6. Performance Standards, 7. Documentation Standards, Architecture docs (+25 more)

### Community 217 - "FeatureEntry"
Cohesion: 0.07
Nodes (14): FeatureEntry, Any, BaseModel, One entry in the support matrix., Load canonical features and apply per-feature then bulk env overrides., Apply a config override string like 'stable', 'beta', 'disabled', 'enabled',…, Return the feature entry if available, or raise FeatureUnavailableError., Return True if the feature is enabled and not disabled. (+6 more)

### Community 218 - "DashboardLayout.js"
Cohesion: 0.11
Nodes (22): createWikiPage(), deleteSource(), deleteWikiPage(), getSource(), getWikiPage(), ingestSource(), lintWiki(), listSources() (+14 more)

### Community 219 - "context_rules.py"
Cohesion: 0.11
Nodes (32): _check_constitution_echo(), _check_files_exist(), _check_grounding(), _check_hedges(), _check_project_identity(), _check_risk_flags(), _check_source_summary(), _check_todos() (+24 more)

### Community 220 - "test_rate_limiter.py"
Cohesion: 0.09
Nodes (29): pace(), Proactive rate-limit throttling for LLM providers — two complementary layers.…, Reset all state (primarily for tests)., Rate limiter using virtual scheduling (GCRA-style): each caller atomically…, Block until this caller's reserved slot arrives, or *max_wait* elapses. Returns…, Proactively pace a request to *provider_id*. No-op (returns 0.0 immediately)…, Clear all token-bucket state (tests only). Does not touch the header tracker's…, reset() (+21 more)

### Community 221 - "local_controller.py"
Cohesion: 0.12
Nodes (32): _bin_exists(), _choose_local_brain(), _default_agency_url(), _default_machine_id_file(), _env_int(), _get_or_create_machine_id(), _http_json(), _log() (+24 more)

### Community 222 - "test_live_server.py"
Cohesion: 0.22
Nodes (32): check(), main(), ok(), Any, Client, Response, Returns access token for subsequent tests., Direct-mode chat. Passes even if no LLM backend is running (error message… (+24 more)

### Community 223 - "ContextManager"
Cohesion: 0.10
Nodes (21): ContextManager, Any, True when the history is long enough to warrant compaction., Replace the old portion of *history* with a single compaction note. The…, True when the harness should use head_file instead of read_file. When a file is…, Trim a step result so sub-agent outputs stay within ~1-2k tokens. The Anthropic…, Manages context window state for a single agent run. The Brain (LLM) stays…, Return a copy of *observations* with old tool outputs truncated. JetBrains… (+13 more)

### Community 224 - "SparkProvider"
Cohesion: 0.07
Nodes (21): get_spark_provider(), NotarizeResult, Any, agent/spark_provider.py — SPARK API Integration Inspired by SPARK API (spark-…, Return True if SPARK API key is set., Register this agent on the SPARK network. If *bsv_address* is not provided,…, Notarize content hash on the BSV blockchain. Args: content: String or bytes to…, Verify a hash against the BSV blockchain. Args: content_hash: SHA-256 hash to… (+13 more)

### Community 225 - "README.md"
Cohesion: 0.11
Nodes (9): Architecture and operations, Documentation map, Repo hygiene, Screenshots and README sync, Start here, A sample of what the agents shipped (all merged, all real), The numbers (verifiable via the GitHub API), This repository is maintained by its own agents (+1 more)

### Community 226 - "agents/api.py"
Cohesion: 0.14
Nodes (31): _apply_activity_status(), create_agent(), delete_agent(), get_agent(), _get_user(), list_agents(), list_runtime_agents(), Any (+23 more)

### Community 227 - "facade.py"
Cohesion: 0.09
Nodes (29): create_access_token(), create_refresh_token(), google_callback(), create_access_token(), create_refresh_token(), get_current_user(), get_optional_user(), github_exchange_code() (+21 more)

### Community 228 - "lifespan"
Cohesion: 0.07
Nodes (22): _keepalive_self_ping(), lifespan(), _maybe_boot_purge(), _purge_backlog_core(), _purge_summary_clean(), Run the FreeBuff Telegram bot, restarting it on unexpected exit., Ping our own public URL so a free-tier web service doesn't sleep. Render free…, Start the Telegram bot (and keep-alive) inside the web process when enabled.… (+14 more)

### Community 229 - "chat_handlers.py"
Cohesion: 0.12
Nodes (31): _apply_chat_defaults(), _emit_safely(), _extract_exact_output(), _filter_fragment(), _filter_openai_sse_line(), handle_ollama_native_chat(), handle_openai_chat_completions(), _inject_default_system_prompt() (+23 more)

### Community 230 - "DashboardScreen.jsx"
Cohesion: 0.07
Nodes (9): BarChart(), Charts, Donut(), ExecutionTimeline(), Sparkline(), ErrorBoundary, DashboardScreen(), fmtTokens() (+1 more)

### Community 231 - "test_daily_2026_06_04.py"
Cohesion: 0.10
Nodes (32): _content_block_to_text(), Convert a single Anthropic content block to a plain text string., _content_block_to_text(), _fresh_router(), _make_tool(), Regression tests for daily-2026-06-04 improvements. Covers: - Claude Opus 4.8…, redacted_thinking blocks (safety-filtered chain-of-thought) must also be…, Ensure effort never leaks into the forwarded OpenAI payload. (+24 more)

### Community 232 - "Workspace"
Cohesion: 0.11
Nodes (14): Any, Path, mcp_server/workspace.py — Isolated workspace manager for the MCP server. Each…, Run a shell command inside the workspace via an explicit shell binary., Resolve rel against root, reject path traversal., Run a subprocess. Never uses shell=True., Manages a single isolated workspace directory., Canonical root path (follows macOS /var → /private/var symlinks). (+6 more)

### Community 233 - "get_registry"
Cohesion: 0.07
Nodes (22): get_registry(), Return model registry, extended with ROUTER_EXTRA_MODELS env entries.…, test_bedrock_haiku_4_5_in_registry(), test_bedrock_opus_48_in_registry(), test_bedrock_opus_4_6_v1_in_registry(), test_bedrock_opus_4_7_in_registry(), test_bedrock_sonnet_4_6_in_registry(), test_deepseek_v3_in_registry() (+14 more)

### Community 234 - ".execute"
Cohesion: 0.07
Nodes (19): _env_float(), Any, AsyncClient, Response, TaskResult, TaskSpec, Submit task to Hermes via its /tasks endpoint., Read a float env var, falling back to *default* on unset/garbage. (+11 more)

### Community 235 - "test_microagents.py"
Cohesion: 0.15
Nodes (29): load_microagents(), match_microagents(), Microagent, microagents_block(), _parse_file(), Path, OpenHands-compatible microagents: keyword-triggered repo knowledge. OpenHands…, Parse one microagent markdown file; None when it isn't one. (+21 more)

### Community 236 - "Security Analysis — local-llm-server"
Cohesion: 0.06
Nodes (30): Fable 5 — Read-Only Audit & Skill-Distillation Notes, Finding A — `list_for_user` Mongo query diverges from the `_can_read` policy, Finding B — `/api/secrets` router is mounted with no authentication dependency, How I would make the smaller model behave like me, Minor, non-security, Part 0 — A caveat on how this task started, Part 1 — The audit, Part 2 — Handing frontier skills to a smaller model (+22 more)

### Community 237 - "Langfuse Observability Guide"
Cohesion: 0.06
Nodes (32): 1. Create a Langfuse project, 2. Configure credentials, 3. Optional tuning, 4. Verify the connection, Commercial savings metrics, Cost analysis dashboard, Cost dashboard, Customising Commercial Reference Prices (+24 more)

### Community 238 - "v3_models.py"
Cohesion: 0.15
Nodes (31): _get_current_user, UserResponse, delete_model(), get_activity(), get_model(), _get_ollama_model_info(), _get_ollama_models(), get_stats() (+23 more)

### Community 239 - "Screens"
Cohesion: 0.06
Nodes (32): 🛡 Admin — users & access, 🤖 Agents — autonomous team, Architecture, security, license, Autonomous AI Agency, 💬 Chat — unified assistant, 🏢 Company — operating context, Contributing, 📊 Dashboard — system overview (+24 more)

### Community 240 - "TestDiagCommand"
Cohesion: 0.09
Nodes (12): TestCase, _GlobalsRestorer, tests/test_telegram_diag.py Regression test for the new ``/diag`` (admin)…, Drive _process_update with a /diag message and return the response. Restores…, The Operator Charter §"Telegram bot" silent-drop path MUST surface a…, Once we've warned once, subsequent silent drops must NOT spam the log., Snapshot/restore tb globals + TELEGRAM_POLLER_DISABLED env var., ``/diag`` behaviour under admin + non-admin + empty-allowlist states. (+4 more)

### Community 241 - "test_purge_backlog.py"
Cohesion: 0.09
Nodes (23): auth_headers(), FakeTaskStore, fixture, MonkeyPatch, Task, tests/test_purge_backlog.py — 2026-07-03 crash-loop remediation. Covers: - POST…, The per-minute tick must requeue at most ONE blocked task, keep its…, Drive _maybe_boot_purge with fakes; return (purged, marker_writes). ``core``… (+15 more)

### Community 242 - "test_telegram_mutating_commands.py"
Cohesion: 0.06
Nodes (22): _Captured, fixture, _make_mock_response(), fixture, tests/test_telegram_mutating_commands.py — N5 acceptance: /setbrain + /merge.…, Build a mock httpx.Response., A successful /setbrain call must: 1. send the X-Service-Token header 2. PATCH…, When the backend's liveness probe fails (HTTP 422), the bot reply must surface… (+14 more)

### Community 243 - "StuckDetector"
Cohesion: 0.13
Nodes (24): Any, Stuck detection for the agent tool loop — adapted from OpenHands. OpenHands…, Canonical identity of one observation, ignoring incidental fields., Consecutive repetitions required before a pattern counts as stuck., Detects repeating patterns in a step's observation history., Return a human-readable reason when the loop looks stuck, else None., _signature(), StuckDetector (+16 more)

### Community 244 - "test_unit7_catalog_propagation.py"
Cohesion: 0.07
Nodes (30): _nvidia_defaults(), tests/test_unit7_catalog_propagation.py — UNIT 7 regression tests. Verifies…, ``_get_defaults()`` must consult the catalog first; the hardcoded…, When NVIDIA key is set, ``_catalog_defaults()`` returns the catalog's nvidia…, ``_get_defaults()`` returns the catalog-derived defaults (not the hardcoded…, ``jcode.py`` must NOT have the stale hardcoded ``meta/llama-3.3-70b-instruct``…, ``opencode.py`` must NOT have the stale hardcoded model id inline., ``_NVIDIA_DEFAULT_MODEL`` must equal the first entry in the catalog's nvidia… (+22 more)

### Community 245 - "High-Agency Frontend Skill"
Cohesion: 0.06
Nodes (30): 10. FINAL PRE-FLIGHT CHECK, 1. ACTIVE BASELINE CONFIGURATION, 2. DEFAULT ARCHITECTURE & CONVENTIONS, 3. DESIGN ENGINEERING DIRECTIVES (Bias Correction), 4. CREATIVE PROACTIVITY (Anti-Slop Implementation), 5. PERFORMANCE GUARDRAILS, 6. TECHNICAL REFERENCE (Dial Definitions), 7. AI TELLS (Forbidden Patterns) (+22 more)

### Community 246 - "Quick-Note GitHub Issues Processing - Session Summary"
Cohesion: 0.06
Nodes (30): 1. Stop-Slop Quality Filter (Issue #229), 2. ECC Integration Study (Issue #266 & #230), ✅ Analysis & Comments (16 items), Architecture Alignment, Branch: `docs/ecc-adoption-analysis`, Branch: `feat/stop-slop-quality-filter`, Deliverables, ECC Patterns Adopted (+22 more)

### Community 247 - "v3_auth.py"
Cohesion: 0.12
Nodes (29): _get_admin_email(), _get_admin_name(), _get_admin_secret(), login(), LoginRequest, LoginResponse, BaseModel, get (+21 more)

### Community 248 - "RateLimitTracker"
Cohesion: 0.11
Nodes (10): RateLimitTracker, Sleep if remaining quota for *provider_id* is critically low. Returns the…, Snapshot of all tracked provider quotas. Safe to call from any context., In-memory tracker for per-provider rate-limit state., asyncio, _response(), TestClear, TestGetStats (+2 more)

### Community 249 - "TestRecordUsageAndStats"
Cohesion: 0.06
Nodes (6): Tests for packages/ai/cost_tracker.py — per-model cost attribution. Covers: -…, TestClearStats, TestCostForTokens, TestEnvOverrides, TestGetCostTable, TestRecordUsageAndStats

### Community 250 - "test_sam_voice.py"
Cohesion: 0.07
Nodes (30): asyncio, tests/test_sam_voice.py — Integration tests for SAM voice agent. Tests the SAM…, Same session_id must return the same session., SAM's system prompt must address the user as Commander., SAM's system prompt must instruct concise responses., _build_context must return a dict with expected keys., A hung LLM call must not block SAM — it must time out and fall back., A stalled context read must not block process_command indefinitely. (+22 more)

### Community 251 - "tests/test_browser.py"
Cohesion: 0.10
Nodes (18): BrowserAction, _env_true(), _not_started(), PageState, Any, agent/browser.py — Browser Automation Controls a real browser via Playwright so…, Evaluate a JavaScript expression in the page context., Return a summary of the current page state. (+10 more)

### Community 252 - "openclaw_gateway.py"
Cohesion: 0.09
Nodes (29): _openclaw_instructions(), openclaw_reverse_proxy(), openclaw_status(), openclaw_websocket(), api_route, websocket, Return the OpenClaw Gateway integration status + pairing QR data. The gateway…, Build the instructions string (separate function to avoid .format() brace… (+21 more)

### Community 253 - "KeyStore"
Cohesion: 0.12
Nodes (16): _check_rate_limit(), default_keys_path(), KeyRecord, KeyStore, load_key_store(), Exception, Path, RateLimitError (+8 more)

### Community 254 - "test_failover_silent_exhaustion.py"
Cohesion: 0.11
Nodes (22): Paid-tier providers admitted to the chain and not yet attempted. Empty when the…, _untried_paid(), _FM, _P, Regression tests for a chain that fails silently. From a real incident:…, Reserve logic must never break the chain it is meant to protect., The incident case: providers ran, none reported a reason., The genuinely-empty chain keeps its original, correct wording. (+14 more)

### Community 255 - "switch_brain.py"
Cohesion: 0.16
Nodes (29): detect_ollama_models(), dim(), fail(), get_auth_headers(), get_brain_config(), get_ngrok_tunnel_url(), header(), info() (+21 more)

### Community 256 - "test_scheduler_hydration_bounded.py"
Cohesion: 0.09
Nodes (23): _hydrate_scheduler_bounded(), Attach durable persistence and rehydrate (#505), bounded by a budget. Without…, _BrokenScheduler, _fake_schedule_store(), _FakeStore, _FastScheduler, _HangingScheduler, _isolate_warmup_overflow() (+15 more)

### Community 257 - "test_autonomy_gate.py"
Cohesion: 0.11
Nodes (27): agent_branch_name(), assert_agent_can_merge(), assert_agent_can_write(), AutonomyViolation, is_protected_branch(), _protected_branches(), Autonomy gate — enforce 'agents propose via PR, humans merge'. The agency can…, Raised when an agent-initiated action would exceed the propose-PR policy. (+19 more)

### Community 258 - "FilterResult"
Cohesion: 0.14
Nodes (16): filter_output(), FilterResult, OutputFilter, agent/output_filter.py — LLM Output Compression & Token Savings Inspired by…, Filter and compress command outputs to reduce LLM token consumption. Provides…, Compact git status output — keep only changed file paths., Compact git log — one line per commit., Compact git diff — keep file headers, collapse hunks. (+8 more)

### Community 259 - "test_dashboard_cache.py"
Cohesion: 0.10
Nodes (24): _cached(), cost_attribution_stats(), _fast_count(), get_stats(), legacy_scheduler_list(), _produce_scheduler_jobs(), rate_limit_stats(), Per-model cost attribution — token usage and estimated USD spend. Aggregates… (+16 more)

### Community 260 - "test_pr923_fixes.py"
Cohesion: 0.09
Nodes (27): nuclear_cleanup(), Directly delete ALL stale jobs from the DB collection. More aggressive than…, FakeDB, asyncio, tests/test_pr923_fixes.py — regression tests for PR #923 (5 production issues).…, nuclear_cleanup should keep newest job per name, delete duplicates., nuclear_cleanup should gracefully handle a DB without a schedules collection., reconcile_stranded_tasks source code must include a FAILED-task re-queue pass.… (+19 more)

### Community 261 - "SteeringInjector"
Cohesion: 0.11
Nodes (10): Any, Inject steering instructions into the message list. Args: messages: The…, Inject steering into an OpenAI chat payload dict. Modifies and returns the…, Build the steering instruction text based on format., Build steering as natural-language quality instructions., Build steering as ChatML-formatted tokens., Build steering as Nemotron-specific steering tags., Inject steering tokens into prompts for quality-biased generation. Supports… (+2 more)

### Community 262 - "test_claude_setup_audit.py"
Cohesion: 0.16
Nodes (23): AuditReport, _check_agents_config(), _check_claude_md_sections(), _check_hooks(), _check_skills(), _check_state(), CheckResult, main() (+15 more)

### Community 263 - "test_crispy_burn_in.py"
Cohesion: 0.07
Nodes (28): burn_in(), fixture, tests/test_crispy_burn_in.py — N4 follow-up: burn-in criteria evaluator. Tests…, window_days below 7 → not ready (need at least a week of evidence)., PhaseSequenceError in last_failure_reasons → not ready (workspace isolation…, Non-PhaseSequenceError failures (assertion errors, etc.) don't block promotion…, Exact threshold values meet the criteria (>=, not >)., window_days=None (no runs yet, but total_runs > 0 somehow) is treated as 0 —… (+20 more)

### Community 264 - "test_internal_agent_did_work.py"
Cohesion: 0.12
Nodes (28): _compute_did_work(), tests/test_internal_agent_did_work.py — step-success-ratio gate tests. Tests…, judge_verdict=BLOCKED → always FAILURE, even with 10/10 applied., judge_verdict=BLOCKED → always FAILURE, even with a long report., Even with unique_files, 1/22 applied → FAILURE (steps_ok gate)., With 9/10 applied + unique_files → SUCCESS., Replicate the did_work logic from internal_agent.py:509-533., 1/22 applied (4.5%) → should be FAILURE (the bug case). (+20 more)

### Community 265 - "test_provider_enable_disable.py"
Cohesion: 0.09
Nodes (16): isolated_kv(), one_provider(), asyncio, fixture, parametrize, Per-provider on/off switch, with auto-disable for unfixable failures only.…, The critical guard: disabling on 429 would switch off every free provider., Point the kv_store at a temp DB so tests never touch real state. (+8 more)

### Community 266 - "test_skill_registry_boot_refresh.py"
Cohesion: 0.12
Nodes (17): clean_task(), _install(), _NullDispatcher, _NullRuntimeManager, asyncio, Exception, fixture, The configured remote skill repos must be fetched without a human trigger.… (+9 more)

### Community 267 - "get_store"
Cohesion: 0.12
Nodes (27): all_settings(), _as_bool(), _as_int(), ephemeral_ttl_hours(), ephemeral_ttl_hours_cached(), get_setting(), _maybe_schedule_refresh(), onboarding_gate_enabled() (+19 more)

### Community 268 - "Python Dependencies (`requirements.txt`)"
Cohesion: 0.07
Nodes (27): AI / LLM, AI Tooling, Browser Automation, Cloud / Infrastructure, Core Web Framework, Data Processing, DEP-001 [HIGH] — No Python Lockfile, DEP-002 [HIGH] — `playwright` as a Runtime Dependency (+19 more)

### Community 269 - "Technical Debt Register — local-llm-server"
Cohesion: 0.07
Nodes (27): Category 10 — Patch Files in Root, Category 1 — God Files, Category 2 — API Key Naming Confusion, Category 3 — Dual App Architecture, Category 4 — Dual Storage Backend, Category 5 — Test File Sprawl, Category 6 — Environment Variable Documentation, Category 7 — Missing Type Annotations (+19 more)

### Community 270 - "get_skill_bindings"
Cohesion: 0.12
Nodes (22): get_skill(), list_skills(), List all available skills with optional filtering. Returns the skill catalog…, Get a single skill by its ID., build_matrix(), _families(), main(), Any (+14 more)

### Community 271 - "llm_providers.py"
Cohesion: 0.16
Nodes (26): _anthropic_headers(), _anthropic_payload(), _anthropic_response_text(), _auth_headers(), chat_completion_text(), list_openai_models(), normalize_base_url(), openai_compat_url() (+18 more)

### Community 272 - "GitHubPage.js"
Cohesion: 0.14
Nodes (25): authorizeGithubRepos(), createGithubPR(), deleteGithubToken(), getGithubStatus, getGithubTree(), getPlatformInfo(), githubStatus(), listGithubBranches() (+17 more)

### Community 273 - "SetupWizardPage.js"
Cohesion: 0.10
Nodes (17): completeSetup(), createSecret(), detectHardwareForSetup(), detectModelsForSetup(), getPublicPath(), getSetupState(), saveSetupStep(), setBackendUrl() (+9 more)

### Community 274 - "SeoAuditReport"
Cohesion: 0.22
Nodes (21): Complete result of one audit run., SeoAuditReport, Paragraph, _appendix_full_findings(), _appendix_worst_pages(), _appendix_wsjf_roadmap(), _cell(), _cover_page() (+13 more)

### Community 275 - "KeyPool"
Cohesion: 0.11
Nodes (11): KeyPool, Round-robin key selection with per-key rate-limit cooldowns., Clear all state (tests only)., The default configuration must be untouched by rotation., With no sibling to fall back to, withholding the key would convert a provider…, The capacity property: one spent key does not stop the provider., So the caller falls straight through to the provider-level cooldown — byte-for-…, A hostile or malformed Retry-After must not park a key indefinitely. (+3 more)

### Community 276 - "RuntimeHealthService"
Cohesion: 0.10
Nodes (10): CircuitState, Return the last-known health for *runtime_id* (may be stale)., Return True if the runtime is available (not circuit-open)., Return health snapshots for all known runtimes., Force an immediate health check of all runtimes and return results., Attempt to start a dead runtime subprocess before re-probing. Uses the local…, Reduce probe frequency for runtimes that have never come online., Async health polling service for all registered runtimes. (+2 more)

### Community 277 - "CostAttributor"
Cohesion: 0.10
Nodes (16): CostAttributor, CostReport, get_cost_attributor(), Any, Tracks and attributes LLM costs per model, phase, and provider. Usage:: attr =…, Record a single LLM call's usage., Batch record multiple usage entries. Returns number recorded., Estimate USD cost for a given model and token count. Looks up the per-model… (+8 more)

### Community 278 - "isolated_telegram_config"
Cohesion: 0.11
Nodes (12): isolated_telegram(), isolated_telegram_config(), fixture, tests/_telegram_test_utils.py Snapshot/restore helper for ``telegram_bot``…, Pytest fixture alias for ``isolated_telegram_config``. Use this in tests that…, Snapshot+restore ``tb`` globals + ``TELEGRAM_POLLER_DISABLED``. Keyword args…, tests/test_telegram_test_utils.py Self-test suite for…, The helper's ``__exit__`` runs ``if original is _MISSING: if hasattr:… (+4 more)

### Community 279 - "WorkflowBuildRequest"
Cohesion: 0.11
Nodes (21): Contract: WorkflowEngine cannot skip the gate state machine., Contract: Cannot approve a run in 'pending' state., _make_engine(), _make_run(), fixture, tests/test_crispy_run_history.py — N4 acceptance:…, Phase-level outcomes (complete/failed counts per phase_type) come from the…, Only the 5 most recent failure reasons are kept — keeps the response payload… (+13 more)

### Community 280 - "TestBrainFailoverModelUpdates"
Cohesion: 0.12
Nodes (5): tests/test_daily_automation_2026_07_10.py — Daily automation tests…, Verify the provider registry in brain_failover contains the 2026 model set., Verify Llama 4 and Claude Sonnet 5 cross-provider aliases are registered., TestBrainFailoverModelAliases, TestBrainFailoverModelUpdates

### Community 281 - "test_memory.py"
Cohesion: 0.10
Nodes (18): _now(), Any, Path, agent/memory.py — Session Memory Snapshots Persists agent session state to disk…, Persist *state* to disk under *session_id*. Returns the file path., Load a saved snapshot. Returns the state dict or *None* if absent., Return metadata for all saved snapshots (session_id, saved_at, path)., Delete a snapshot. Returns *True* if the file existed. (+10 more)

### Community 282 - "analyze_qualitative"
Cohesion: 0.12
Nodes (15): analyze_qualitative(), Extract themes, pain points, and desires from qualitative data. Args: source:…, apply_recommendations(), collect_codebase_metrics(), extract_qualitative_themes(), main(), plan_repo_scan(), Use the user research skill to scan the repo and apply recommendations. Adapts… (+7 more)

### Community 283 - "SprintMetrics"
Cohesion: 0.10
Nodes (12): Complete the sprint and record velocity., Calculate current sprint metrics., Velocity and burndown metrics for a sprint., Percentage of story points completed., Points per day needed to complete on time., Whether the sprint is on track to complete., Derive a qualitative health signal from the metrics. - COMPLETE: all points…, SprintMetrics (+4 more)

### Community 284 - "get_scheduler"
Cohesion: 0.13
Nodes (25): legacy_scheduler_toggle(), patch, get_scheduler(), create_schedule(), delete_schedule(), get_schedule(), get_schedule_runs(), list_schedules() (+17 more)

### Community 285 - "Deploy: FreeBuff Telegram bot (24×7)"
Cohesion: 0.07
Nodes (25): Agents, Environment variables, Free model set, FreeBuff — free-NVIDIA coding agent, `/freebuff <task>`, HTTP API, Running 24×7, Telegram phone control (+17 more)

### Community 286 - "Claude Code + Qwen Local Setup"
Cohesion: 0.07
Nodes (27): 1. Set environment variables, 2. Start Claude Code, 3. Verify model routing, Anthropic SDK (Python), Architecture, "Authentication error" or 401, Claude Code + Qwen Local Setup, Claude Code reports "token limit exceeded" (+19 more)

### Community 287 - "get_feature_matrix"
Cohesion: 0.12
Nodes (16): __init__.py — Feature flag/matrix package., get_feature_matrix(), Enum, features/matrix.py — Feature maturity tiers and support matrix. Single source…, Return the global FeatureMatrix singleton., Reset the singleton (useful for testing)., reset_feature_matrix(), multi_agent_swarm is BETA + enabled (was DISABLED pre-fix). The CEO dispatcher… (+8 more)

### Community 288 - "generate_context.py"
Cohesion: 0.12
Nodes (26): _build_caller_chain(), _build_context_doc(), _build_grounding_block(), _build_pr_description(), _build_todos_md(), _build_user_message(), _call_claude(), _call_mistral() (+18 more)

### Community 289 - "_is_dns_failure"
Cohesion: 0.10
Nodes (18): _is_dns_failure(), _probe_failure_reason(), BaseException, Turn a probe exception into an operator-actionable one-line reason. A dead…, True when *exc* (or anything it wraps) is a name-resolution failure., asyncio, Exception, parametrize (+10 more)

### Community 290 - "test_anthropic_router.py"
Cohesion: 0.12
Nodes (8): _make_anthropic_provider(), _payload(), ProviderConfig, Tests for Anthropic-specific router features. Covers: - Prompt caching…, TestAnthropicPayloadExtendedThinking, TestAnthropicPayloadPromptCaching, TestAuthHeadersExtendedThinking, TestAuthHeadersPromptCaching

### Community 291 - "test_daily_automation_2026_08_03.py"
Cohesion: 0.10
Nodes (14): _load_yaml(), tests/test_daily_automation_2026_08_03.py — Daily automation (2026-08-03).…, brain_config.py anthropic candidates must include every model in models.yaml., brain_config.py aerolink candidates must include every model in models.yaml., test_aerolink_candidates_match_yaml(), test_anthropic_candidates_match_yaml(), test_yaml_aerolink_candidates_contains_opus_5(), test_yaml_aerolink_judge_is_opus_5() (+6 more)

### Community 292 - "validate_outbound_url"
Cohesion: 0.14
Nodes (25): test_git_ref_rejects_empty(), test_git_ref_rejects_flag_injection(), test_git_ref_rejects_shell_metacharacters(), test_git_ref_rejects_traversal(), test_git_ref_valid(), test_git_scheme_allows_ssh(), test_http_scheme_rejects_ssh(), test_https_public_host_allowed() (+17 more)

### Community 293 - "webui/frontend/package.json"
Cohesion: 0.07
Nodes (26): @types/react, @types/react-dom, typescript, vite, @vitejs/plugin-react, dependencies, react, react-dom (+18 more)

### Community 294 - "LocalWorkspace"
Cohesion: 0.14
Nodes (15): LocalWorkspace, Path, Manages a local git clone of a GitHub repository. Clones are stored under…, Run a git command. Never uses shell=True., Clone the repo if it doesn't exist; pull if it does., Return the current working-tree diff (staged + unstaged)., Stage files and commit. paths=None stages everything; paths=[] raises., Create and checkout a new branch from base_branch. (+7 more)

### Community 295 - "Performance Analysis — local-llm-server"
Cohesion: 0.08
Nodes (25): 1. Rate Limiter Performance, 2. Ollama Connection Handling, 3. Model Router Performance, 4. Agent Execution Performance, 5. Backend Server Performance, 6. Frontend Performance, 7. Streaming Performance, PERF-001 [HIGH] — Synchronous Lock in Async Context (+17 more)

### Community 296 - "LLM Router — troubleshooting"
Cohesion: 0.08
Nodes (24): Embeddings, LiteLLM compatibility mode, LLM Router — local model guide, LM Studio, LocalAI, Ollama, Preferring local, Registering local models (+16 more)

### Community 297 - "AgentsScreen.jsx"
Cohesion: 0.13
Nodes (23): createAgent(), deleteAgent(), updateAgent(), AgentCard(), AgentForm(), AgentsPage(), cls(), normalizeAgent() (+15 more)

### Community 298 - "ClaudeCodeAdapter"
Cohesion: 0.14
Nodes (21): ClaudeCodeAdapter, json_safe(), Any, TaskResult, TaskSpec, Adapter for Claude Code CLI — FIRST CLASS autonomous coding runtime., adapter(), asyncio (+13 more)

### Community 299 - "keepalive.py"
Cohesion: 0.15
Nodes (25): _check_ollama(), _check_render(), _default_ollama_base(), _default_render_url(), _env_bool(), _loaded_ollama_prefixes(), _log(), _log_path() (+17 more)

### Community 300 - "monitor_lib.py"
Cohesion: 0.17
Nodes (25): colibri_dir(), download_log_path(), download_status(), DownloadStatus, _heartbeat_to_file(), is_process_alive(), model_dir(), monitor_log_path() (+17 more)

### Community 301 - "TrainingSample"
Cohesion: 0.10
Nodes (13): Any, Add a step result. Returns the sample if accepted, None if filtered out., Bulk-add samples from an agent session's step results. Each step result with…, Return samples filtered by minimum reward score., Export samples in Alpaca JSONL format. Returns the path to the exported file., Export samples in ShareGPT JSONL format. Returns the path to the exported file., Export all samples as a structured JSON array. Returns the path to the exported…, Return pipeline statistics. (+5 more)

### Community 302 - "APIClient"
Cohesion: 0.15
Nodes (6): APIClient, Provider CRUD: create, list, test connection, delete., Wiki pages: create, view, edit, delete, search, lint., Direct API calls for fast test setup and teardown., TestProviders, TestWiki

### Community 303 - "test_telegram_approval_e2e.py"
Cohesion: 0.12
Nodes (25): _approve_execution_via_rest(), _delete_task(), _extract_admin_token(), _login_admin(), _looks_like_admin_token(), _open_dashboard(), _poll_task_execution_approved(), Any (+17 more)

### Community 304 - "_get"
Cohesion: 0.10
Nodes (12): _get(), one_configured_provider(), fixture, Contract tests for the provider on/off endpoints. ``GET /api/brain/providers``…, Silently storing a typo'd id would leave a switch nothing can turn back on., The operator has to know WHY before deciding to switch it back on. The raw…, A registry with exactly two known providers and isolated state., The response reaches the browser — a leaked key would be a disclosure. (+4 more)

### Community 305 - "TestSchedulerStore"
Cohesion: 0.08
Nodes (12): fixture, count() returns 0 for an empty store., count() reflects the number of saved jobs., count() decreases after delete., delete_stale() keeps jobs updated recently., delete_stale() removes jobs with old updated_at., delete_stale() reads SCHEDULER_JOB_RETENTION_DAYS from env., delete_stale() returns 0 when all jobs are recent. (+4 more)

### Community 306 - "test_service_token.py"
Cohesion: 0.08
Nodes (20): fixture, tests/test_service_token.py — N5 acceptance: service-token auth surface. Tests…, Near-miss tokens must not pass (no prefix-match, no fuzzy match)., After verification, the module must NOT hold the plaintext token — only the…, The token plaintext must NEVER appear in logs. Capture every log record emitted…, The module must use hmac.compare_digest (not ==) for the comparison — timing…, The service token must only gate a narrow allowlist of endpoints — not all of…, When SERVICE_TOKEN is rotated in the env, the new token must verify (within the… (+12 more)

### Community 307 - "test_v3_auth.py"
Cohesion: 0.17
Nodes (25): _configured_v3_email(), _configured_v3_password(), asyncio, skip, TestClient, Tests for v3 API authentication., Test login endpoint returns valid tokens., Test login with invalid credentials. (+17 more)

### Community 308 - "TestWorkflow"
Cohesion: 0.08
Nodes (6): Tests for agents/workflow_engine.py — SuperClaude Workflow Engine. Uses…, Tests for WorkflowEngine., Tests for Task dataclass., TestTask, TestWorkflow, TestWorkflowEngine

### Community 309 - "test_lessons.py"
Cohesion: 0.16
Nodes (19): _get_store(), LessonStore, Any, Connection, Path, Failure lessons: turn failed runs into context for the next run. The supervisor…, Formatted prompt block of recent lessons, or '' when none exist., SQLite-backed store of failure lessons. Thread-safe, zero deps. (+11 more)

### Community 310 - "test_rag_context.py"
Cohesion: 0.14
Nodes (23): RAGContextBuilder, Retrieve, decay, and compress context to fit a configurable token budget.…, Tests for agent/rag_context.py — Advanced RAG context management layer. Imports…, test_builder_doc_budget_fraction(), test_builder_docs_dropped_count(), test_builder_empty_both(), test_builder_empty_documents(), test_builder_empty_history() (+15 more)

### Community 311 - "ScheduleStore"
Cohesion: 0.12
Nodes (16): _backend(), _json_default(), Any, agent/schedule_store.py — durable persistence for scheduled agent jobs. Fixes…, Return all persisted schedule docs (for boot rehydration)., Persist (insert or update) a single schedule by job_id., Delete a persisted schedule., Fallback JSON encoder for schedule docs (datetimes, sets, etc.). (+8 more)

### Community 312 - "timedelta"
Cohesion: 0.13
Nodes (21): PR throughput per cohort over the last `days` days., _as_aware_utc(), _env_float(), datetime, services/ephemeral_reaper.py — destroy expired ephemeral companies. The…, Treat naive datetimes as UTC so comparisons never raise., Delete all expired ephemeral companies. Returns the number deleted. A company…, Parse a positive, finite float env var (seconds), else the default. Rejects… (+13 more)

### Community 313 - "dependencies"
Cohesion: 0.08
Nodes (25): axios, fast-uri, dependencies, axios, fast-uri, livekit-client, lucide-react, react (+17 more)

### Community 314 - "reset_store"
Cohesion: 0.11
Nodes (23): Reset the store singleton (used in tests). Also resets the motor client…, reset_store(), tests/test_motor_event_loop_isolation.py — regression test for the flaky…, ``reset_store()`` must clear ``db.mongo_store._client`` and ``_db``, not just…, ``reset_store()`` must also clear the ``db._store`` wrapper (the original…, The ``client`` fixture in conftest.py must call ``reset_store()`` before…, After ``reset_store()``, the next ``MongoStore._get_db()`` call must create a…, test_client_fixture_calls_reset_store_before_lifespan() (+15 more)

### Community 315 - "Session Handoff — 2026-06-15"
Cohesion: 0.08
Nodes (24): Context the next session will need, Critical environment variables, Files changed today (for code archaeology), How to resume, Key files to know, Key labels, P0 — Add a regression test for the draft-PR safety guards, P1 — Watch Run 27481814863 for issue #504 and verify end-to-end (+16 more)

### Community 316 - "TASK 4 — End-to-end approval-gate test"
Cohesion: 0.08
Nodes (24): 3.1 — Confirm env vars on the **web** service, 3.2 — Confirm single-poller guard on the **worker**, 3.3 — Verify the bot responds (human-in-the-loop), 3.4 — TASK 3 acceptance, 4.1 — Acquire an admin session, 4.2 — Trigger an outward-facing workflow run, 4.3 — Watch the run until it pauses, 4.4 — Confirm the Telegram message arrived (+16 more)

### Community 317 - "Any"
Cohesion: 0.15
Nodes (3): Any, field_validator, Coerce unrecognised system_type values to 'custom' so the model never crashes…

### Community 318 - "test_north_mini_code.py"
Cohesion: 0.08
Nodes (15): north_mini_code_model_for(), Return the North Mini Code model id served by *provider*, else ``None``.…, tests/test_north_mini_code.py — North Mini Code 1.0 integration. Covers the…, The switch defaults ON so North is the default post-install., The agency/Hermes execution path defaults to North via the resolver., Hermes must be able to run the agency with the full Hermes-OS capacity set —…, Only high/medium/low are honoured; anything else means 'unset'., North is cost_tier=2, so it must not become the ``best_model_for`` pick for the… (+7 more)

### Community 319 - "kimi_bridge_provider_config"
Cohesion: 0.12
Nodes (18): _enabled(), kimi_bridge_provider_config(), kimi_bridge_runtime_config(), kimi_bridge_status(), _norm_env(), ProviderConfig, Free Kimi (Moonshot) **web-bridge** provider. Why this exists ---------------…, Lightweight status used by the Providers UI / Doctor. (+10 more)

### Community 320 - "AgentMessageBus"
Cohesion: 0.15
Nodes (9): AgentMessageBus, get_agent_bus(), Remove a subscription., Return all topics that have history., Return the module-level AgentMessageBus singleton., Pub/sub message bus for inter-agent communication. Agents subscribe to topics…, Decorator: subscribe a callback to a topic pattern. Supports ``*`` (single…, asyncio (+1 more)

### Community 321 - "ProviderInfo"
Cohesion: 0.09
Nodes (14): ProviderInfo, A configured LLM provider with its connection details + health state., True when the provider can accept traffic right now., anyio, Tests for packages/ai/key_pool.py — per-provider API key rotation. Rotation is…, Rotation needs the variable the key came from. Deriving it from the provider id…, No pool configured — the pre-rotation path, unchanged., Anthropic uses x-api-key, not Bearer — the override must reach it. (+6 more)

### Community 322 - "TemporalContextGraph"
Cohesion: 0.12
Nodes (14): demo_agent_tracking(), datetime, Temporal context graph inspired by Graphiti…, Get history of an entity between two times, Get current state of an entity (most recent fact), Query facts with pattern matching, Get source (provenance) of a specific fact, A fact at a specific point in time (+6 more)

### Community 323 - "test_agency_fix.py"
Cohesion: 0.08
Nodes (24): agency_fix(), fixture, tests/test_agency_fix.py — N3 acceptance tests for scripts/agency_fix.py. The…, An edit that produces a syntactically-broken Python file must be rejected —…, An edit that truncates a real code file to a trivial body must be rejected —…, With no issue linked, decline is just an exit-code signal — no API call., When an issue is linked but no GH_PAT/GH_TOKEN is set, the decline fails loudly…, When an issue is linked and the API call succeeds, decline_cleanly returns True… (+16 more)

### Community 324 - "TestClassifyPlainText"
Cohesion: 0.08
Nodes (6): tests/test_inbound_router.py Pytest coverage for…, The 3500-char default matches the design recommendation; below the delivered…, TestBigPasteThreshold, TestClassifyPlainText, TestSanitizePasteForPreview, TestSavePaste

### Community 325 - "get_tool_registry"
Cohesion: 0.12
Nodes (12): get_tool_registry(), Return the module-level ToolRegistry singleton. On first call, registers built-…, HarnessEnrichment, invalidate_enrichment_cache(), Any, Build a compact catalog of available runtime skills. Discovers from…, Build the complete enrichment block (tools + skills). Returns empty string when…, Inject enrichment blocks into a system prompt string. Appends blocks after the… (+4 more)

### Community 326 - "Findings"
Cohesion: 0.08
Nodes (23): E2E Tests, Findings, Immediate (Current Sprint), Integration Tests, Live/External Tests (skipped in standard CI), Missing Test Areas, Sprint 1, Sprint 2 (+15 more)

### Community 327 - "Local AI Stack with Docker"
Cohesion: 0.08
Nodes (23): 1. Clone and configure, 2. Start the stack (GPU), 3. Start the stack (CPU only), 4. Pull models (first run), 5. Access services, CPU Only, Data Persistence, Default (GPU) (+15 more)

### Community 328 - "Configuration Reference"
Cohesion: 0.08
Nodes (24): Agent Models, Anthropic API Compatibility / Claude Code, Authentication and Keys, Claude Code setup, Configuration Reference, Dashboard (React UI on :3000, API on :8001), Feature Flags, Feature Maturity Overrides (+16 more)

### Community 329 - "Implementation Prompt: Rich TaskBoard + Agile Sprint Integration"
Cohesion: 0.08
Nodes (23): 1. Task model extensions (`tasks/models.py`), 2. New task endpoint (`tasks/api.py`), 3. Agile REST endpoints (`backend/server.py`), 4. TaskBoardScreen upgrade (`frontend/src/v5/screens/TaskBoardScreen.jsx`), 4a. "Needs Clarification" 7th column, 4b. Right-side detail panel, 4c. Sprint view mode toggle, 4d. Create-task modal enhancements (+15 more)

### Community 330 - "Telegram Bot Setup"
Cohesion: 0.08
Nodes (24): Admin commands (immediate, no confirmation), Admin commands with approval required, Approval Workflow, Authorization Model, Command Reference, Debugging message delivery, Debugging proxy connection failures, Linux (systemd) (+16 more)

### Community 331 - "video_transcript.py"
Cohesion: 0.12
Nodes (23): caption_tracks(), extract_player_response(), fetch_transcript(), _get(), is_video_url(), parse_json3(), parse_timedtext_xml(), Extract a usable text transcript from a video URL, without an API key. Why this… (+15 more)

### Community 332 - "PrioritizedTask"
Cohesion: 0.12
Nodes (12): IntEnum, Queue, PrioritizedTask, Priority, Any, Start the worker pool., Submit a task to the queue. Returns True if accepted, False if rejected due to…, Subscribe to progress events for a specific task. Returns an asyncio.Queue that… (+4 more)

### Community 333 - "CollectionLike"
Cohesion: 0.12
Nodes (12): get_storage(), packages/storage/factory.py — storage backend factory. Returns the appropriate…, Return the active storage backend. During migration, this delegates to the…, Reset the storage singleton (for tests)., reset_storage(), CollectionLike, Any, Protocol (+4 more)

### Community 334 - "test_monitor_lib.py"
Cohesion: 0.11
Nodes (9): _isolate_env(), fixture, MonkeyPatch, tests/test_monitor_lib.py — unit tests for scripts/monitor_lib.py. Covers the…, Pin all env-overridable paths to tmp_path for hermetic tests., TestAwaitReady, TestIsProcessAlive, TestSuperviseLoopGiveUp (+1 more)

### Community 335 - "test_output_filter.py"
Cohesion: 0.08
Nodes (23): tests/test_output_filter.py — Unit tests for output_filter.py Verifies token…, pytest output with failures should preserve failure details., Deep Python traceback should collapse intermediate frames., Large curl output should be truncated with head/tail., When disabled, output should pass through (truncated to max_chars)., Empty or whitespace-only input should pass through unchanged., git log with 200 commits should be compressed., Small git status should pass through unchanged. (+15 more)

### Community 336 - "test_schedule_backlog_drain.py"
Cohesion: 0.16
Nodes (19): _FakePersistence, _one_shot(), asyncio, Why the 2026-08-01 backlog never drained, despite a fix already existing.…, A timestamp we cannot parse must not authorise a delete., The pre-existing behaviour has to survive the new branch above it., The previous failure was invisible: four digits at INFO beside two zeroes., It cleaned `db.schedules`, which on Mongo is a real but empty collection. The… (+11 more)

### Community 337 - "test_v4_api.py"
Cohesion: 0.12
Nodes (23): auth_headers(), fixture, TestClient, tests/test_v4_api.py — Tests for the v4 dashboard API endpoints., Return the test client — reuses conftest client which has bootstrap., Get auth headers by logging in as admin via the admin API., GET /v4/status returns 200 with improvement_loop and self_healing keys., GET /v4/improvements returns 200 with active and resolved lists. (+15 more)

### Community 338 - "test_workspace_security.py"
Cohesion: 0.10
Nodes (9): TestWorkspacePathDerivation, Security-oriented tests for workspace isolation (Area C4). Covers: - No path…, The hash component should not be reversible to the original ID., Workspace root path should be fully resolved (no . or ..)., TestCleanupIsolation, TestSymlinkAttackPrevention, TestWorkspaceHashing, _hash_component() (+1 more)

### Community 339 - "heal_signature"
Cohesion: 0.12
Nodes (18): heal_signature(), Stable signature for an error/heal, used to dedup and detect recurrence.…, Path, Regression tests for robustness bugs found in the autonomy-paths audit. - P1-3…, If the re-dispatch coroutine raises, the heal escalates instead of stranding., test_hermes_dispatch_noop_without_url(), test_regress_redispatch_failure_escalates(), healer() (+10 more)

### Community 340 - "CollaborationContext"
Cohesion: 0.12
Nodes (7): CollaborationContext, Any, Release control if the active editor is idle > 30s., Apply context updates from a contributor. Only the active editor can modify…, Run one sync tick across all sessions. Actions taken: - Kick idle active…, Shared context blob propagated to all session participants. Carries the active…, TestCollaborationContext

### Community 341 - "_get_provider_policy"
Cohesion: 0.11
Nodes (22): _get_provider_policy(), get_provider_policy_route(), Read the durable provider policy from DB, falling back to a safe default.…, Return the provider policy (paid-provider kill switch state)., Resolve the LLM endpoint for a named surface (task/chat/ceo/sdlc/…). Honours…, resolve_provider_for(), asyncio, Phase 3 regression test: paid providers are NEVER auto-selected when… (+14 more)

### Community 342 - "The fifteen strategies"
Cohesion: 0.09
Nodes (22): adaptive *(default)*, automatic_failover, Candidate selection, Choosing one, context_length_optimized, cost_optimized, fallback_chain, highest_success_rate (+14 more)

### Community 343 - "RuntimesPage.js"
Cohesion: 0.13
Nodes (19): getRoutingPolicy(), refreshRuntimeHealth(), runTaskOnRuntime(), startAllRuntimes(), startRuntime(), stopAllRuntimes(), stopRuntime(), updateRoutingPolicy() (+11 more)

### Community 344 - "ServiceManager"
Cohesion: 0.13
Nodes (14): get_status(), BaseModel, get, post, Start the FastAPI proxy server., Serve the launcher UI., Get current service status., root() (+6 more)

### Community 345 - "_Cursor"
Cohesion: 0.10
Nodes (7): _Cursor, _PendingCursor, Async iterator wrapping a list of dicts (already decoded from JSON)., Return a sort key that tolerates mixed float/str timestamp values. Some code…, Return a _Cursor (evaluated lazily on first await/iteration)., A cursor that fetches its data lazily on first use., _safe_sort_key()

### Community 346 - "test_all_features.py"
Cohesion: 0.09
Nodes (9): TestActivation, TestActivity, TestApiKeys, TestCompany, TestOnboarding, TestSecrets, TestSetup, TestTasks (+1 more)

### Community 347 - "test_brain_priority_scanner.py"
Cohesion: 0.11
Nodes (22): Regression tests for: brain-skip-paid, provider-priority persistence, scanner…, Critical failover-safety test: if every free provider's base URL is excluded…, When the ONLY configured provider is a paid one (e.g. operator set…, When only Anthropic is configured AND allow_paid=False (default), the resolver…, The PUT /api/providers/{id} endpoint did not persist priority edits because the…, scanner.py used to end with a bare `systems` statement at module level, which…, Priority must be an int (or None for unset) and within a sane range so a typo…, The PUT /api/providers/{id} handler does: for k, v in… (+14 more)

### Community 348 - "TestHarnessAdapter"
Cohesion: 0.09
Nodes (5): fixture, Harness detection, normalization, and registration., Harness session tracking and metrics., TestHarnessAdapter, TestHarnessRegistry

### Community 349 - "Path"
Cohesion: 0.16
Nodes (6): Path, Old log + done signal + no .incomplete = complete (caller can cleanup the log…, TestDownloadStatus, TestReadPidFile, TestSupervisorStateAtomic, _write_log()

### Community 350 - "test_mostly_failed_steps.py"
Cohesion: 0.12
Nodes (22): _make_result(), _make_step(), tests/test_mostly_failed_steps.py — regression test for the "21/22 failed steps…, A BLOCKED judge verdict should never be success, regardless of steps., When mostly_failed, the output should contain a clear failure summary., 0 steps → no gate (division by zero avoided, total_steps < 4)., 6 failed + 2 applied = 75% failure, 2 applied < 3 → mostly_failed., Build a mock agent result dict (the shape InternalAgentAdapter expects). (+14 more)

### Community 351 - "classify_direct_chat_intent"
Cohesion: 0.13
Nodes (19): classify_direct_chat_intent(), _contains_keyword(), detect_intent(), intent.py — Intent classification for direct chat (answer_only, execute_now,…, Return True if content contains any execution or analysis keyword., Detect the user's intent from message content., Map lower-level intents into conversation-driven action categories. Returns one…, classify_plain_text() (+11 more)

### Community 352 - "._connect"
Cohesion: 0.10
Nodes (10): Any, Connection, Path, Recall a specific memory entry., Auto-load relevant memories based on context. Returns memories prioritized by:…, Get all memories in a specific category., Delete a memory entry., Export all memories for a user (for backup/migration). (+2 more)

### Community 353 - "rag_context.py"
Cohesion: 0.13
Nodes (17): ContextResult, Document, MemoryTurn, agent/rag_context.py — Advanced RAG context management layer. Pipeline --------…, Rough token estimate: 4 chars ≈ 1 token (minimum 1)., A single knowledge-base entry (wiki page, source document, etc.)., Run the full RAG pipeline and return a token-budget-respecting context.…, One turn in the conversation history. (+9 more)

### Community 354 - "cost_tracker.py"
Cohesion: 0.10
Nodes (21): clear_cost_attribution(), cost_table(), Return the active per-model cost table (USD per million tokens). Useful for…, Reset in-memory cost attribution counters. Admin-only., _build_cost_table(), clear_stats(), cost_for_tokens(), get_cost_table() (+13 more)

### Community 355 - "_resolve_user_github_token"
Cohesion: 0.17
Nodes (18): Return the caller's GitHub token from EITHER place it can be stored. A token…, _resolve_user_github_token(), _FakeCollection, _FakeDB, patch_db(), asyncio, fixture, The doctor must find a GitHub token wherever the connect flow stored it.… (+10 more)

### Community 356 - "Harness"
Cohesion: 0.14
Nodes (16): detect_harness(), Harness, harness_context_limit(), harness_stats(), HarnessProfile, Any, Enum, Detect which AI coding tool is calling the proxy. Checks in priority order: 1.… (+8 more)

### Community 357 - "DecisionsStore"
Cohesion: 0.18
Nodes (7): DecisionsStore, Any, Connection, Test-only: clears the cached singleton so the next get_decisions_store() builds…, # NOTE: ``decision_id`` is NOT a SQL FOREIGN KEY here. The bot's, reset_decisions_store_singleton(), _fresh_store()

### Community 358 - "PriorityTaskQueue"
Cohesion: 0.13
Nodes (8): get_task_queue(), PriorityTaskQueue, Stop the worker pool gracefully., Return queue introspection data for status endpoints., Return the module-level PriorityTaskQueue singleton., Asyncio-based priority queue with backpressure and worker pool. Features: -…, Higher-priority tasks should be processed before lower-priority ones., TestPriorityTaskQueue

### Community 359 - "TestRenderMCPSidecarService"
Cohesion: 0.16
Nodes (11): _env(), The Go binary hardcodes :10000 and ignores $PORT, so Render must be told., In HTTP mode the token comes from the caller's header, so nothing here is…, The mux serves /mcp only; a health check there opens an SSE stream that never…, pkg/oauth fails the process at boot on a partial OAuth config., The backend must use the private-network address, not the public URL., A free service sleeps at ~15m idle; polling must stay under that., _render_yaml() (+3 more)

### Community 360 - "_P"
Cohesion: 0.19
Nodes (8): _ids(), _P, A provider with no latency sample must be able to earn one., The safety invariant: a shuffle may not promote a paid provider ahead of the…, With every provider idle a stable sort would send the whole burst to the first…, No explicit weights: the provider that has spent less of its minute should be…, Minimal provider stand-in — the director only needs ``provider_id``., TestOrdering

### Community 361 - "test_repowise_intelligence.py"
Cohesion: 0.10
Nodes (19): repowise.py — RepowiseIntelligence: context packing and dependency analysis., Test that search_codebase returns a string., Test that get_decision_flownodes returns a string., Test that update_intelligence creates the expected intelligence files., Test that get_overview returns a dictionary., Test that get_context returns a string., Test that get_risk returns a dictionary., Test that get_why returns a string. (+11 more)

### Community 362 - "test_voice.py"
Cohesion: 0.15
Nodes (13): Any, agent/voice.py — Voice Command Interface Hands-free agent interaction: record…, Transcribe raw PCM *audio_bytes* to text., Record then transcribe in one call., Record *duration_s* seconds of audio. Returns raw PCM bytes (int16 LE, 16 kHz…, _stub_result(), TranscriptionResult, Tests for agent/voice.py — Voice Command Interface (stub-mode tests). (+5 more)

### Community 363 - "V3 API Migration Plan — LLM Relay Platform"
Cohesion: 0.10
Nodes (20): Acceptance Checks, Approach, Auth Flow (v3 JWT-based), Backward Compatibility, Current State Analysis, Data Model Changes, Database/Storage, Files to Create/Modify (+12 more)

### Community 364 - "SchedulesPage.js"
Cohesion: 0.13
Nodes (15): createSchedule(), pauseSchedule(), resumeSchedule(), triggerSchedule(), C, FREQ_OPTS, FREQ_TO_CRON, NewScheduleForm() (+7 more)

### Community 365 - "api_keys_for"
Cohesion: 0.14
Nodes (9): api_keys_for(), All keys configured for *provider_id*, primary first. Thin delegate to…, parametrize, Sibling keys must be ignored until the operator explicitly opts in. Several…, A typo'd `_4` must not silently promote itself into the `_2` slot — the…, The same key twice is one budget, not two. Counting it twice would advertise…, The first-gap rule has to start at the first slot or it is not a gap rule.…, TestApiKeysFor (+1 more)

### Community 366 - "redact_connection_url"
Cohesion: 0.14
Nodes (10): packages/security/redact.py — strip secrets out of strings before they reach a…, Strip embedded credentials from a connection URI before logging it. Covers both…, redact_connection_url(), main(), Register runtime agents in the store., register_runtimes(), Regression test: production leaked a live MongoDB password in plaintext.…, Integration coverage: the actual log lines this module emits must never carry… (+2 more)

### Community 367 - "test_issue_triage.py"
Cohesion: 0.17
Nodes (19): _match_family(), Any, services/issue_triage.py — inbound GitHub issue triage. Closes the intake gap…, Classify a single GitHub issue payload and return the routing decision. Pure…, Fetch unlabeled open issues, triage each, and route them. Returns a summary…, run_triage_cycle(), _severity_for(), triage_enabled() (+11 more)

### Community 368 - "test_local_controller.py"
Cohesion: 0.17
Nodes (20): _env_defaults(), _fake_http_sequence(), _fake_subprocess_run(), _import_controller(), tests/test_local_controller.py — unit tests for the local GLM-5.2 daemon. These…, The diag output must surface binary/model errors clearly., Pins the v3 fix: after the multi-port preamble probe finds colibri serving a…, Yield a list of (status, body) tuples the daemon will see in order when it… (+12 more)

### Community 369 - "run_trend_analysis"
Cohesion: 0.19
Nodes (13): Tests for trend_analysis.py — last30days-style window over TrendWatcher (issue…, TestRunTrendAnalysis, TestWindow, BaseModel, trend_analysis.py — last30days-style trend analysis (issue #493). Adapts the…, True if the ISO-ish published date falls within the last N days.…, Fetch trends via TrendWatcher, filter to a 30-day window, persist summary., Write trends/trend_summary.md (and a dated copy); return the path. (+5 more)

### Community 370 - "test_unit5_ui_provider_surface.py"
Cohesion: 0.10
Nodes (15): tests/test_unit5_ui_provider_surface.py — UNIT 5 regression tests. Verifies…, The component must call ``providerLabel(p)`` rather than indexing a 4-entry…, The dropdown shows a [free]/[paid]/[local] tier tag so the operator can tell…, The <option> tag uses providerLabel(p), not PROVIDER_LABELS[]., The operator must be able to see what a key really serves. ``candidates`` is…, The GET endpoint response must list every BrainProvider Literal entry. Before…, Providers that were filtered out before UNIT 5 are now present. ``mistral``,…, A known paid provider is reported as tier=paid (was filtered before). (+7 more)

### Community 371 - "test_voice_pipeline.py"
Cohesion: 0.13
Nodes (15): asyncio, fixture, Tests: Voice pipeline — STT backend selection, TTS backend selection, memory…, A stalled gTTS/pyttsx3 call must not hang synthesize() forever. gTTS/pyttsx3…, TTS_SYNTHESIZE_TIMEOUT_SEC must override the default ceiling., gTTS/pyttsx3 must run on a dedicated executor, not the shared default.…, test_memory_export_markdown(), test_memory_forget() (+7 more)

### Community 372 - "MemoryCategory"
Cohesion: 0.16
Nodes (14): Memory middleware for automatic context injection into AI tool requests. This…, MemoryCategory, MemoryEntry, MemoryScope, Enum, Row, str, Enhanced persistent memory system with auto-loading across AI coding tools.… (+6 more)

### Community 373 - "PersistentMemoryStore"
Cohesion: 0.24
Nodes (19): PersistentMemoryStore, Enhanced persistent memory store with auto-loading support. Features: -…, cmd_autoload(), cmd_delete(), cmd_export(), cmd_import(), cmd_list(), cmd_recall() (+11 more)

### Community 374 - "playbook.py"
Cohesion: 0.17
Nodes (7): _now(), Playbook, PlaybookRun, PlaybookStep, Any, Path, agent/playbook.py — Automation Playbooks Pre-defined, named multi-step…

### Community 375 - "WorkspaceError"
Cohesion: 0.13
Nodes (11): Exception, Lock, Open a workspace for resumption. Only READY or PAUSED workspaces may be…, Base class for all workspace errors., _read_manifest(), WorkspaceAccessDeniedError, WorkspaceError, WorkspaceLockError (+3 more)

### Community 376 - "Skill: modularity-review"
Cohesion: 0.10
Nodes (19): Acceptance Checks, Applying to This Repo, Further Reading, Modularity Findings Template, Part A: Reviewing Existing Code for Modularity Problems, Part B: Designing New Modular Boundaries, Skill: modularity-review, Step 1 — Map the dependency graph (+11 more)

### Community 377 - "Design Audit"
Cohesion: 0.10
Nodes (19): Code Quality, Color and Surfaces, Component Patterns, Content, Design Audit, Fix Priority, How This Works, Iconography (+11 more)

### Community 378 - "Findings"
Cohesion: 0.10
Nodes (19): API Documentation, Architecture Documentation, DOC-001 [HIGH] — No SECURITY.md, DOC-002 [HIGH] — No CONTRIBUTING.md, DOC-003 [HIGH] — No API.md / OpenAPI Export, DOC-004 [MEDIUM] — README.md is 31KB and Needs Pruning, DOC-005 [MEDIUM] — `REVIEW_AND_FIXES.md` and `AGENCY_CORE_V5_PROGRESS.md` are Unclear, DOC-006 [MEDIUM] — No DEPLOYMENT.md at Root (+11 more)

### Community 379 - "TestNormalizeResponseFormat"
Cohesion: 0.10
Nodes (8): _normalize_response_format(), Translate OpenAI ``response_format`` into Ollama's ``format`` field. For…, fixture, Payload without 'model' field should apply normalization (no '/' → local)., _normalize_response_format must not mutate the input dict., Unit tests for chat_handlers._normalize_response_format., If json_schema has no 'schema' key, don't break., TestNormalizeResponseFormat

### Community 380 - "Skill: modularity-review"
Cohesion: 0.10
Nodes (19): Acceptance Checks, Applying to This Repo, Further Reading, Modularity Findings Template, Part A: Reviewing Existing Code for Modularity Problems, Part B: Designing New Modular Boundaries, Skill: modularity-review, Step 1 — Map the dependency graph (+11 more)

### Community 381 - "crispy_client.py"
Cohesion: 0.14
Nodes (18): cmd_approve(), cmd_artifacts(), cmd_build(), cmd_events(), cmd_reject(), cmd_status(), cmd_watch(), _get() (+10 more)

### Community 382 - "Dynamic Model Routing"
Cohesion: 0.10
Nodes (20): Architecture, Built-in Claude → local alias table, Configuring fast_response routing, Configuring model preferences, Curl example, Dynamic Model Routing, Fallback execution, Health check and availability filtering (+12 more)

### Community 383 - "PortfolioScreen.jsx"
Cohesion: 0.11
Nodes (12): getPortfolioBoard(), refreshPortfolio(), btnStyle, HEALTH, HORIZONS, PortfolioScreen(), SOURCE, STATUS_COLOR (+4 more)

### Community 384 - "infra_cost.py"
Cohesion: 0.15
Nodes (14): compute_request_cost(), _float_env(), get_infra_config(), InfraConfig, load_infra_config(), project_session_cost(), Local infrastructure cost model for true TCO analysis. This module computes the…, Compute infrastructure cost for a single request given its latency. (+6 more)

### Community 385 - "output_filter.py"
Cohesion: 0.10
Nodes (17): _filter_curl(), _filter_docker(), _filter_git(), _filter_ls(), _filter_npm(), _filter_pip(), _filter_pytest(), _filter_python() (+9 more)

### Community 386 - "compilerOptions"
Cohesion: 0.10
Nodes (19): DOM, DOM.Iterable, ES2022, src, vite/client, compilerOptions, isolatedModules, jsx (+11 more)

### Community 387 - "GuardrailEngine"
Cohesion: 0.16
Nodes (7): get_guardrails(), GuardrailEngine, Configurable safety rail engine for LLM inputs and outputs. Supports: -…, Load guardrail rules from a YAML or JSON config file., Compile regex patterns from the rules configuration., Return the module-level GuardrailEngine singleton., TestGuardrailEngine

### Community 388 - "HarnessRegistry"
Cohesion: 0.17
Nodes (8): HarnessMetrics, HarnessRegistry, HarnessSessionRecord, _NoopDB, Any, BaseModel, services/harness_registry.py — Persistent Harness Registry Tracks which AI…, Persistent registry of harnesses and their performance history. Stores session…

### Community 389 - "test_brain_patch_service_token.py"
Cohesion: 0.16
Nodes (19): clean_store(), _clear_overrides(), _make_client_with_user(), fixture, tests/test_brain_patch_service_token.py — N5 acceptance: PATCH…, N5 acceptance: no service token + no user session → 401 (not 200)., N5 regression: the existing dashboard path (no service token, non-admin user)…, N5 regression: the existing admin dashboard path (no service token, admin user)… (+11 more)

### Community 390 - "test_chat_mode_regressions.py"
Cohesion: 0.19
Nodes (18): _auth_headers(), test_agent_status_endpoint_reports_live_progress_and_tool_calls(), test_agent_stream_endpoint_emits_server_sent_events(), test_chat_send_emits_langfuse_observation_for_direct_chat(), test_chat_send_keeps_complex_prompt_on_direct_path_when_agent_mode_is_off(), test_chat_send_keeps_explanatory_github_pr_guidance_on_direct_path(), test_chat_send_keeps_general_docker_explanation_on_direct_path_when_no_repo_action_is_requested(), test_chat_send_persists_agent_handoff_metadata_in_session_history() (+10 more)

### Community 391 - "test_tasks_cache_ttl_env.py"
Cohesion: 0.21
Nodes (19): MonkeyPatch, Round-trip tests for TASKS_LIST_ALL_CACHE_TTL_SEC env-var override in…, With a lowered cap, a value above the new cap falls back to default., Reload tasks.api after injecting TASKS_LIST_ALL_CACHE_TTL_SEC=value (or unset)., Values above the 1h upper bound in _safe_ttl fall back to default. Guards the…, Value equal to the 1h upper bound is honored (boundary case)., ``TASKS_MAX_CACHE_TTL_SEC`` env var overrides the cap module-level constant., _reload_tasks_api_with_env() (+11 more)

### Community 392 - "test_workflow_models.py"
Cohesion: 0.13
Nodes (8): tests/test_workflow_models.py — Unit tests for workflow/models.py., TestApprovalGate, TestCheckRun, ApprovalGate, CheckRun, Any, Hard approval gate between plan and execution. The workflow engine sets…, Structured, execution-based verification result. Verifier agents produce ONLY…

### Community 393 - "TestUpdateTask"
Cohesion: 0.16
Nodes (7): _NoopCheckpointStore, WorkflowRun, tests/test_workflow_orchestrator_update_task.py Pytest coverage for…, Stand-in for the real Mongo checkpoint store., Two consecutive updates collapse: the latest instruction wins. This matches…, _run(), TestUpdateTask

### Community 394 - "MemoryKernel"
Cohesion: 0.16
Nodes (7): Fact, get_memory_kernel(), MemoryKernel, voice/memory_kernel.py — Jarvis OS-inspired Memory Kernel. Stores atomic facts…, Return most relevant facts. Simple substring match on content., SQLite-backed atomic fact store with Markdown mirror., Store a new atomic fact or reinforce an existing one.

### Community 395 - "_extract_tech_relevance"
Cohesion: 0.17
Nodes (6): _extract_tech_relevance(), Dynamic extraction: finds any tech keyword mentioned in the skill content,…, Tests for _extract_tech_relevance() word-boundary matching., Integration-style tests for the recommendation path (no I/O)., TestExtractTechRelevance, TestRecommendLogic

### Community 396 - "agile_api.py"
Cohesion: 0.25
Nodes (18): complete_sprint(), create_sprint(), _get_mgr(), get_velocity(), list_sprints(), Any, BaseModel, get (+10 more)

### Community 397 - "HarnessAdapter"
Cohesion: 0.12
Nodes (9): HarnessAdapter, HarnessSpec, Any, agents/harness_adapter.py — ECC Cross-Harness Adapter Normalises API…, Adapt harness-native requests to the local-llm-server internal format. Each…, Detect which harness sent this request from headers. Check order: explicit…, Convert a harness-native request dict to the local-llm-server format., Return the recommended model for this harness. (+1 more)

### Community 398 - "Skill: fabric-patterns"
Cohesion: 0.11
Nodes (18): 1. Ensure Pattern Directory Exists, 2. List Available Patterns, 3. Retrieve a Pattern, 4. Apply a Pattern with Variables, 5. Stitch Patterns Together, 6. Create New Patterns, Acceptance Checks, Directory Structure (+10 more)

### Community 399 - "Analysis & Synthesis Instructions"
Cohesion: 0.11
Nodes (18): 1. Define the Atmosphere, 2. Map the Color Palette, 3. Establish Typography Rules, 4. Define the Hero Section, 5. Describe Component Stylings, 6. Define Layout Principles, 7. Define Responsive Rules, 8. Encode Motion Philosophy (+10 more)

### Community 400 - "Production Readiness Assessment — local-llm-server"
Cohesion: 0.11
Nodes (18): 1. Availability & Reliability, 2. Observability, 3. Deployment Architecture, 4. Configuration & Secrets, 5. Recovery & Backup, 6. Cloudflare Worker Audit, Current State, Current State (+10 more)

### Community 401 - "Skill: fabric-patterns"
Cohesion: 0.11
Nodes (18): 1. Ensure Pattern Directory Exists, 2. List Available Patterns, 3. Retrieve a Pattern, 4. Apply a Pattern with Variables, 5. Stitch Patterns Together, 6. Create New Patterns, Acceptance Checks, Directory Structure (+10 more)

### Community 402 - "db/__init__.py"
Cohesion: 0.15
Nodes (7): _LazyModuleProxy, db — storage abstraction layer (V2.0 Phase 5: real code moved to…, Loads the real module on first attribute access, then replaces itself., # IMPORTANT: keep these imports LAZY (inside __getattr__) so that a Mongo-only, MongoStore, db/mongo_store.py — MongoDB store backed by Motor (existing implementation).…, Thin wrapper that exposes the Motor database as collection attributes.…

### Community 403 - "Admin Dashboard Guide"
Cohesion: 0.11
Nodes (19): Accessing the Dashboard, Admin API (Programmatic Access), Admin Dashboard Guide, Dashboard — healthy state, Dashboard — key created (one-time token flash), Dashboard — Langfuse diagnostic, Dashboard Layout, Login page (+11 more)

### Community 404 - "Implementation Plan"
Cohesion: 0.11
Nodes (18): (1) & partly (4): "Something went wrong" masks the real error everywhere, (2) & (3): Company creation flow / non-admin gate placement, (4): Agent provisioning "loading forever" — blocking subprocess in async path, (5): Tailored questions are hardcoded today, A0. Fix live scanner crashes on real-world sites (`services/scanner.py`) — do first, A. Fix error-message masking (`frontend/src/api.js`), Agent Prompt (paste this to start the implementation session), B. Make runtime activation non-blocking (`runtimes/control.py`, (+10 more)

### Community 405 - "Feature Guide"
Cohesion: 0.11
Nodes (19): 10. Langfuse Observability, 11. Coding Agent API, 12. Browser Admin UI, 13. Telegram Remote Control Bot, 14. Tunnel — Permanent Static URL via ngrok, 15. CORS Support, 16. Streaming Support, 17. Workspace Isolation (+11 more)

### Community 406 - "ProviderConsole.jsx"
Cohesion: 0.11
Nodes (10): ALIASES, canonicalId(), CATALOGUE, FILTERS, ADR-0008, mergeProviders(), ProviderRow(), STATE (+2 more)

### Community 407 - "Provider"
Cohesion: 0.13
Nodes (11): Cerebras provider adapter — free, fast LLM (qwen-3-coder-480b)., Ollama provider adapter — local LLM inference., packages/ai/manager.py — ProviderManager. Single entry point for all LLM calls.…, Provider, ABC, packages/ai/provider.py — Provider abstraction interface. Every LLM provider…, Base interface every provider must implement. Implementations live in…, Unique identifier (e.g. 'nvidia', 'cerebras'). (+3 more)

### Community 408 - "key_pool.py"
Cohesion: 0.13
Nodes (13): provider_api_keys(), Every API key configured for *provider*, primary first. Reads ``base_env`` then…, _digest(), get_pool(), _KeyState, _PoolState, Per-provider API key rotation — the one lever that adds capacity. Every other…, Return the next usable key, or None when every key is cooling. With one key… (+5 more)

### Community 409 - "Delegation Plan (agent-ready work packages)"
Cohesion: 0.11
Nodes (18): Delegation Plan (agent-ready work packages), Findings, http://127.0.0.1:8899/, Page Details (worst first), Pillar Scores, `seo-fix-canonicals` - Fix Canonicals findings: 1 finding type(s) across 1 URL hit(s), `seo-fix-content` - Fix Content findings: 1 finding type(s) across 1 URL hit(s), `seo-fix-geo` - Fix GEO findings: 5 finding type(s) across 5 URL hit(s) (+10 more)

### Community 410 - "build_workflow.py"
Cohesion: 0.33
Nodes (18): _c(), _get(), _header(), main(), _make_headers(), _phase_icon(), _post(), _print_phases() (+10 more)

### Community 411 - "test_p0_roadmap_b3_b4_b5.py"
Cohesion: 0.18
Nodes (12): _deep_merge(), Deep merge two dicts. Override values take precedence., CircuitBreakerOpenError, CircuitState, get_nim_pool(), Enum, RuntimeError, Raised when a request is blocked by an open circuit breaker. (+4 more)

### Community 412 - "SyntheticDataPipeline"
Cohesion: 0.17
Nodes (6): get_synthetic_pipeline(), Clear all accumulated samples., Return the module-level SyntheticDataPipeline singleton., Pipeline to generate synthetic training data from agent sessions. Usage::…, SyntheticDataPipeline, TestSyntheticDataPipeline

### Community 413 - "test_task_source_id_race.py"
Cohesion: 0.17
Nodes (18): _is_duplicate_key_error(), Exception, True if *exc* is a pymongo E11000 duplicate-key error. Checked by class name…, _FakeDuplicateKeyError, _mock_mongo_db(), asyncio, Exception, tests/test_task_source_id_race.py — TaskStore.create() concurrency safety.… (+10 more)

### Community 414 - "test_company_api.py"
Cohesion: 0.11
Nodes (14): client(), fixture, Tests for Company Graph API endpoints., Create a test client for the FastAPI app., Test Company Graph API endpoints., Test that the company API router is included., Test Doctor endpoint., Test the public doctor endpoint. (+6 more)

### Community 415 - "TestSelfHealingInfrastructureClassification"
Cohesion: 0.19
Nodes (4): _classify_failure correctly identifies infrastructure errors., MongoDB timeout is an infra error, not a generic timeout., MongoDB 'connection refused' is infra, not generic network., TestSelfHealingInfrastructureClassification

### Community 416 - "test_fabric_patterns.py"
Cohesion: 0.11
Nodes (5): MonkeyPatch, Path, Tests for scripts/fabric_cli.py and the fabric-patterns pattern engine., test_new_scaffolds_pattern(), test_save_and_show_roundtrip()

### Community 417 - "test_schedule_persistence.py"
Cohesion: 0.17
Nodes (14): _FakePersistence, tests/test_schedule_persistence.py — #505 schedules survive restart. Regression…, Populate the store directly so hydration tests don't depend on the timing of…, Regression for the production startup path: services/background.py runs inside…, The sync attach_persistence()/rehydrate() must stay safe even if called from…, In-memory stand-in for ScheduleStore (no Mongo needed in tests)., A disabled job must be registered (paused) on rehydrate so a later…, _seed() (+6 more)

### Community 418 - "validate_session_id"
Cohesion: 0.16
Nodes (5): TestSessionIdValidation, WorkspaceNotFoundError should not expose the base root in error messages., TestNoInternalPathLeakage, Validate and return a session ID, or raise InvalidSessionIdError., validate_session_id()

### Community 419 - "ErrorInterceptorMiddleware"
Cohesion: 0.18
Nodes (11): _dispatch_async(), ErrorInterceptorMiddleware, Any, BaseHTTPMiddleware, Exception, Request, Response, agent/error_interceptor.py — HTTP Error Interceptor Middleware… (+3 more)

### Community 420 - "github_tools.py"
Cohesion: 0.24
Nodes (16): get_repo(), _get_token(), _get_user(), init_workspace(), list_branches(), list_prs(), list_repos(), BaseModel (+8 more)

### Community 421 - "._parse_body"
Cohesion: 0.15
Nodes (9): Decode a JSON-RPC response body from either JSON or an SSE stream. Streamable-…, SSE uses CRLF on the wire; the trailing \\r must not corrupt the JSON., Build an httpx.Response the client can parse, with a bound request., The plain-JSON path (/mcp-internal) must be unchanged., A Streamable-HTTP reply arrives as SSE data: frames., Progress notifications precede the response; the response wins., Regression: one event may split its JSON across several data: lines. Parsing…, A stream that ends without a terminating blank line still decodes. (+1 more)

### Community 422 - ".update_intelligence"
Cohesion: 0.11
Nodes (9): Build symbol-level dependency graph for Python files., Extract docstrings and store as documentation., Mark that we have updated intelligence up to this commit., Build or update all intelligence layers., Extracts architectural decisions related to target from git history and inline…, Build file-level dependency graph based on imports., One-call RAG over documentation with confidence gating., Semantic search over documentation (we'll do keyword search for now). (+1 more)

### Community 423 - "Comprehensive Skill Index (By Category)"
Cohesion: 0.11
Nodes (17): 10. Domain (Modelling, Training, Infra), 1. Planning and Implementation, 2. Code Quality, Architecture, and Audits, 3. State Management and Git Flow, 4. Memory, Knowledge, and Context Tuning, 5. Research, Browsing, and External Intel, 6. Session Lifecycle and Workflow, 7. Style and Craft Polish (UI / Docs / Tone) (+9 more)

### Community 424 - "Agent Skill: Principal UI/UX Architect & Motion Choreographer (Awwwards-Tier)"
Cohesion: 0.11
Nodes (17): 1. Meta Information & Core Directive, 2. THE "ABSOLUTE ZERO" DIRECTIVE (STRICT ANTI-PATTERNS), 3. THE CREATIVE VARIANCE ENGINE, 4. HAPTIC MICRO-AESTHETICS (COMPONENT MASTERY), 5. MOTION CHOREOGRAPHY (FLUID DYNAMICS), 6. PERFORMANCE GUARDRAILS, 7. EXECUTION PROTOCOL, 8. PRE-OUTPUT CHECKLIST (+9 more)

### Community 425 - "Component Map"
Cohesion: 0.11
Nodes (17): Architecture Audit — local-llm-server, Architecture Diagram, Component Map, Layer 10 — WebUI (`webui/`), Layer 11 — Infrastructure, Layer 1 — API Proxy (`proxy.py`, 1719 lines), Layer 2 — Chat Handlers (`chat_handlers.py`, 710 lines), Layer 3 — Model Router (`router/`) (+9 more)

### Community 426 - "Agent State — colibri GLM-5.2 deployment (resumable)"
Cohesion: 0.11
Nodes (17): Agent State — colibri GLM-5.2 deployment (resumable), Audit verification (2026-07-16, this session), Context / Task, Converged action sequence (after colibri binding is fixed, someday), Done this session (commit `b03a6ba`), Findings (verified empirically), Follow-up fix during commit amend: UTF-8 BOM on setup_autostart.ps1, Option A — Pivot to a feasible MLX model (HIGHEST ROI) (+9 more)

### Community 427 - "Architecture Overview — local-llm-server"
Cohesion: 0.11
Nodes (18): `admin_auth.py` + `admin_gui.py`, `agent/`, Architecture Overview — local-llm-server, `chat_handlers.py`, Deployment, Feature Maturity Tiers, `handlers/anthropic_compat.py`, High-Level Architecture (+10 more)

### Community 428 - "Pending Activities — Implementation Playbook"
Cohesion: 0.11
Nodes (17): Context: what already works (do NOT redo), Definition of done (per task), How to verify the whole thing end-to-end (local, no external infra), P0 — Make autonomy real in production, P1 — Close the remaining product gaps, P2 — ECC harness & polish, Pending Activities — Implementation Playbook, Task 10 — ECC cross-harness adapter (currently PLANNED only) (+9 more)

### Community 429 - "Platform Guide — the full tour"
Cohesion: 0.11
Nodes (18): Agent runtimes, Architecture, Cloud deployment (Render + GitHub Pages), Development, Feature maturity — what's stable vs. beta, HITL approval gates — you stay in control, How it works — the 5-minute version, Learning loop — failures become context (+10 more)

### Community 430 - "The rules"
Cohesion: 0.11
Nodes (17): Changing these rules, How the gate behaves, Quick-Note Context Rulebook, R10 — Use the repository's real identity **[gate]**, R11 — Name a real integration point **[gate]**, R12 — Mark epistemic status at the claim **[review]**, R1 — Ground the plan in the source before planning anything **[gate]**, R2 — Say what the artifact actually is **[gate]** (+9 more)

### Community 431 - "Part A — Health Report"
Cohesion: 0.11
Nodes (17): F1 — CLAUDE.md documents an architecture that no longer exists, F2 — 15 skills have no frontmatter description, F3 — Direct `os.environ` reads outside config modules, F4 — `print()` in importable production modules, F5 — graphify hook nags every session, F6 — God files, Healthy signals, P1 — Refresh CLAUDE.md and AGENTS.md to match the real architecture (+9 more)

### Community 432 - "apply_review.py"
Cohesion: 0.19
Nodes (10): ApplyReviewAgent, build_review_context(), _gh(), main(), _openai_tools_to_anthropic(), Convert OpenAI function-calling tool schemas to Anthropic tool schemas., Return (result_text, should_stop)., Run using NVIDIA NIM (OpenAI-compatible). Called as fallback. (+2 more)

### Community 433 - "ai/__init__.py"
Cohesion: 0.19
Nodes (16): packages.ai — provider abstraction, model registry, and failover manager., all_models(), best_model_for(), get(), ModelInfo, models_by_provider(), packages/ai/registry.py — Model Registry. Centralized registry of all models…, Register the default free-tier models. (+8 more)

### Community 434 - "scheduler.py"
Cohesion: 0.14
Nodes (12): _age_seconds(), agent/scheduler.py — Scheduled Agent Jobs Cron-based job scheduler. Each job…, Remove a job. Returns *True* if it existed., The one retention policy for unfired one-shots, read from its owner.…, Force-dedup and clean stale schedules from both the durable store and in-memory…, Delete EVERY schedule from the durable store and in-memory state. Operator…, #505: Remove a job from durable storage., Seconds since ``created_at``. Unparseable or missing reads as brand new. Erring… (+4 more)

### Community 435 - "SQLiteStore"
Cohesion: 0.16
Nodes (10): Connection, Top-level store — exposes collections as attributes. Usage:: store =…, Lazily build the pool of read-only connections (idempotent)., Yield a read connection from the pool (falls back to the writer). On in-memory…, Create tables if they don't already exist., SQLiteStore, fixture, B608 guard: _Collection.__init__ must reject names outside _COLLECTIONS.… (+2 more)

### Community 436 - "._execute_with_fallback"
Cohesion: 0.16
Nodes (10): Any, TaskResult, TaskSpec, Selects a runtime for the given task, executes the task (including readiness…, Selects an available runtime for the given task type, preferring a specified…, Execute the given task spec on the primary runtime, attempt configured fallback…, Attempt paid escalation through ProviderManager. Routes the task to the first…, Return the last *limit* routing decisions (newest first). (+2 more)

### Community 437 - "agency_fix.py"
Cohesion: 0.20
Nodes (17): apply_edits(), build_prompt(), call_llm(), collect_context(), collect_source_files(), decline_cleanly(), extract_failing_tests(), _is_blocked() (+9 more)

### Community 438 - "sync_readme_gallery.py"
Cohesion: 0.22
Nodes (15): main(), _out_dir(), Path, Generate Web UI screenshots for README/docs. Requires: pip install playwright…, build_gallery(), GallerySection, main(), Path (+7 more)

### Community 439 - "test_shared_state.py"
Cohesion: 0.20
Nodes (11): cooldown_clear(), cooldown_get(), cooldown_set(), _get_backend(), Shared-state abstraction — in-memory (default) and Redis backends. Provides…, Put a key on cooldown for *ttl* seconds., Return True if *key* is still within its cooldown window., Clear all cooldown entries (for test teardown). (+3 more)

### Community 440 - "test_skill_executors_live.py"
Cohesion: 0.16
Nodes (17): Live Graphify executor — queries the codebase knowledge graph. Order of…, Live council reviewer — deterministic, rules-based multi-perspective review…, _run_council_review(), _run_graphify(), parametrize, tests/test_skill_executors_live.py — live graphify + council-review executors.…, Broadened secret detection catches SECRET_KEY / GITHUB_TOKEN / etc. The…, test_council_clean_diff_is_approved() (+9 more)

### Community 441 - "LocalLLMSetup"
Cohesion: 0.16
Nodes (7): LocalLLMSetup, Update .env file with configuration., Check if services are already running., Start the proxy server., Scan for local models., Scan the models folder for available models., Configure which models to use for agent roles.

### Community 442 - "test_freebuff_bot.py"
Cohesion: 0.12
Nodes (13): _fb_run(), Execute a FreeBuff task (embedded or via proxy). Shape: {result: {...}}., fixture, Tests for the always-on FreeBuff Telegram bot: embedded vs HTTP dispatch., In orchestrator mode the embedded run must set the bypass so the agent runs., Snapshot/restore os.environ — the launcher writes env vars directly., _restore_env(), test_embedded_flag() (+5 more)

### Community 443 - "test_task_brain_preflight.py"
Cohesion: 0.24
Nodes (15): fixture, svc(), _coordinator(), has_brain(), no_brain(), asyncio, BaseException, fixture (+7 more)

### Community 444 - "test_openclaw_endpoints.py"
Cohesion: 0.11
Nodes (11): client(), fixture, tests/test_openclaw_endpoints.py — OpenClaw HTTP + WebSocket endpoint tests., After pairing, ping command returns pong., Unknown command returns error., WebSocket with wrong token is rejected (connection closed)., WebSocket with correct token pairs successfully., test_websocket_pairing_accepts_correct_token() (+3 more)

### Community 445 - "TestStopSlopChecker"
Cohesion: 0.11
Nodes (10): Should detect phrases case-insensitively, Should detect throat-clearing phrases, Should return no issues for clean text, Strict mode should detect passive voice, Should detect multiple types of tells in one text, Issues should have helpful suggestions, Should detect business jargon, Should remove throat-clearing phrases (+2 more)

### Community 446 - "test_task_service_failed_comment.py"
Cohesion: 0.18
Nodes (17): coordinator(), _make_result(), mock_store(), mock_workflow(), asyncio, fixture, tests/test_task_service_failed_comment.py — verify that a FAILED TaskResult…, A FAILED TaskResult without agent_comment transitions to FAILED without… (+9 more)

### Community 447 - "handle_workflow_ide_chat"
Cohesion: 0.18
Nodes (17): _extract_last_user_message(), handle_workflow_ide_chat(), _json_response(), Any, JSONResponse, Request, StreamingResponse, workflow/ide_bridge.py — OpenAI-compatible SSE bridge for IDE clients. This… (+9 more)

### Community 448 - "test_contract_enforcement.py"
Cohesion: 0.17
Nodes (9): check_kwargs(), Any, agent/contract_enforcement.py — Runtime signature locking (J) Provides…, # NOTE: limit has a default so it is accepted; owner_id is keyword-only., Raise TypeError on unknown kwarg (runtime extra='forbid'). Args: kwargs: The…, # NOTE: limit is NOT locked — it is a legitimate optional param that does not, tests/test_contract_enforcement.py — Contract discipline tests (J) Tests that…, Unit tests for the check_kwargs helper. (+1 more)

### Community 449 - "TestHelpers"
Cohesion: 0.15
Nodes (8): _extract_tags(), _first_paragraph(), Path, Return the first non-empty, non-heading line. Skips YAML frontmatter (--- ...…, Pull hashtags and bold words from markdown as tags., Tests for module-level helper functions., Regression: frontmatter (--- ... ---) must not surface as '---'., TestHelpers

### Community 450 - "._fetch_flat_skill_file"
Cohesion: 0.21
Nodes (8): _fmt_name(), AsyncClient, Fetch skills from all configured GitHub registries. Returns count added., Force-refresh remote skills, bypassing TTL. Returns count added., Fetch one GitHub registry and return a list of RegistrySkill objects. Handles…, Fetch a registry whose skills live in arbitrarily nested directories. Uses the…, Fetch one nested SKILL.md via raw.githubusercontent.com., Fetch a flat .md file and convert it to a RegistrySkill.

### Community 451 - "Task"
Cohesion: 0.18
Nodes (11): Enum, Path, str, Task definition schema for the evaluation harness. Inspired by OpenHarness'…, Score the agent's final answer. Returns (success, score)., Returns (success: bool, score: float ∈ [0, 1]). Raises NotImplementedError for…, A fully-specified evaluation task. Fields mirror the OpenHarness task schema so…, SuccessCriterion (+3 more)

### Community 452 - "terminal.py"
Cohesion: 0.17
Nodes (10): _is_command_not_found(), _powershell_quote(), Any, agent/terminal.py — Terminal Panel Reads the rendered terminal output buffer —…, Try to read the pane buffer via tmux capture-pane., Return a minimal snapshot with terminal dimensions only., Capture the current terminal state. Never raises., Run *cmd* and capture its full output (stdout + stderr). Returns a dict with… (+2 more)

### Community 453 - "SKILL: Industrial Brutalism & Tactical Telemetry UI"
Cohesion: 0.12
Nodes (16): 1. Skill Meta, 2.1 Swiss Industrial Print, 2.2 Tactical Telemetry & CRT Terminal, 2. Visual Archetypes, 3.1 Macro-Typography (Structural Headers), 3.2 Micro-Typography (Data & Telemetry), 3.3 Textural Contrast (Artistic Disruption), 3. Typographic Architecture (+8 more)

### Community 454 - "Skill: data-quality-audit"
Cohesion: 0.12
Nodes (16): 1. Token Length Distribution, 2. Deduplication Check, 3. Tokenizer Fertility Check, 4. Special Token Consistency, 5. Language Detection (if langdetect available), 6. Content Quality Signals, Background (Why This Matters), Checks Performed (+8 more)

### Community 455 - "What "Slop" Looks Like"
Cohesion: 0.12
Nodes (16): Acceptance Checks, Category 1 — Obvious Comments, Category 2 — Phantom Abstractions, Category 3 — Defensive Checks for Impossible Cases, Category 4 — Speculative Generality, Category 5 — Verbose Variable Names, Category 6 — Unasked-For Boilerplate, Instructions (+8 more)

### Community 456 - "test_admin_local_brain_router.py"
Cohesion: 0.18
Nodes (16): build_admin_local_brain_router(), Any, APIRouter, Construct a ready-to-mount APIRouter with the auth dependency baked in. The…, _require_admin(), _make_app(), FastAPI, tests/test_admin_local_brain_router.py — auth + toggle flow for… (+8 more)

### Community 457 - "local_brain_router.py"
Cohesion: 0.19
Nodes (16): get_local_brain_state(), HeartbeatBody, post_local_brain_heartbeat(), post_local_brain_toggle(), Any, BaseModel, get, post (+8 more)

### Community 458 - "Section-by-Section Acceptance Criteria"
Cohesion: 0.12
Nodes (16): 467 Final Acceptance Criteria, §A — Company Graph + Onboarding, §B — 34 Specialist Families, §C — ECC, Obsidian, Graphify, Council Review Wiring, §D — Direct Chat as Control Center, Definition of Done, §E — Workflow Engine as Canonical Backbone + Worktree Isolation, §F — Doctor Full Check List (+8 more)

### Community 459 - "agent_readiness_audit.py"
Cohesion: 0.21
Nodes (15): _grade(), main(), PillarResult, scripts/agent_readiness_audit.py — score this repo's fitness for autonomous…, ReadinessReport, run_audit(), score_build_system(), score_dev_environment() (+7 more)

### Community 460 - "test_ci.sh"
Cohesion: 0.15
Nodes (16): ADMIN_EMAIL, ADMIN_PASSWORD, API_KEYS, cleanup(), DB_NAME, fail(), LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY (+8 more)

### Community 461 - "test_telegram_auto_approve.py"
Cohesion: 0.20
Nodes (16): is_sensitive(), True when *text* references a sensitive target (auth/keys/secrets/service…, _build_execution_request(), Any, Build a minimal ``ExecutionRequest`` for plain-text → orchestrator.execute.…, admin_user(), _auto_approve(), non_admin_user() (+8 more)

### Community 462 - "ProviderCircuit"
Cohesion: 0.17
Nodes (7): ProviderCircuit, Attempt to move from OPEN to HALF_OPEN after recovery timeout., Check if a request can be made through this circuit., Per-provider circuit breaker state machine., TestProviderCircuit, parametrize, Counting every sub-500 as a success meant the breaker could never open for the…

### Community 463 - "claim"
Cohesion: 0.18
Nodes (7): claim(), Try to acquire a named lock. Returns True if acquired, False if already held., Release a previously acquired lock., release(), TestInMemoryClaim, TestInMemoryKeyIsolation, TestRedisClaim

### Community 464 - "._coerce_ts"
Cohesion: 0.18
Nodes (8): _coerce_ts(), ExecutionLogEntry, Any, field_validator, Update the updated_at timestamp., Coerce ISO-8601 datetime strings (from DB) to float timestamps., Single entry in a task's execution log., Dict-compatible accessor. Log entries are serialized to/from dicts in many…

### Community 465 - "test_activation_api.py"
Cohesion: 0.21
Nodes (16): _client(), TestClient, Tests for activation_api — instance status, OpenAPI schema, and role route.…, GET /api/activation/settings is PUBLIC — non-admin users need to read the…, test_change_role_rejects_invalid_role(), test_change_role_requires_authentication(), test_change_role_returns_404_for_missing_user(), test_change_role_updates_existing_user() (+8 more)

### Community 466 - "test_autonomy_status.py"
Cohesion: 0.12
Nodes (16): client(), fixture, TestClient, tests/test_autonomy_status.py — public /api/autonomy/status readiness probe.…, No auth required; response carries the readiness contract keys., The probe carries the loop fleet readiness summary (loop-audit)., Without NVIDIA key AND without Ollama, the probe must report no_brain., When NVIDIA is absent but Ollama is configured, report brain as ollama. (+8 more)

### Community 467 - "test_health_endpoints.py"
Cohesion: 0.17
Nodes (16): _make_fake_client(), Exception, Tests for /health, /live, and /api/health endpoints., When Ollama is down, /api/health should also return a degraded status., Return a context-manager-compatible mock for httpx.AsyncClient., Container liveness probe must always return 200., Health endpoint exists and returns a JSON body., Health endpoint includes provider states when ProviderRouter is wired in. (+8 more)

### Community 468 - "test_keepalive.py"
Cohesion: 0.18
Nodes (16): Path, Smoke test for scripts/keepalive.py (Windows-friendly Render + Ollama keepalive…, `--diagnose` mode exits 1 when hosts are unreachable (per docstring: exit 0/1)., Reload scripts.keepalive with KEEPALIVE_LOG = log_path and clear cache., KEEPALIVE_LOG under tmp_path; log_path() ensures parent directory exists., _rotate_log_if_needed() is a no-op when file is under MAX_LOG_BYTES; truncates…, _log() writes '[YYYY-MM-DD HH:MM:SS] <line>' to KEEPALIVE_LOG., When Render + Ollama are both unreachable, run_once() returns 1. (+8 more)

### Community 469 - "test_local_brain_state.py"
Cohesion: 0.12
Nodes (11): fixture, tests/test_local_brain_state.py — regression test for the cross-machine toggle.…, Operator flips OFF — any prior lease must be dropped so a future ON doesn't…, The store must not corrupt the model listing when reading back., The 3 endpoints MUST refuse calls without SERVICE_TOKEN — confirmed by mounting…, All three endpoints must be present on the router (regression guard against…, store(), test_router_3_endpoints_are_registered() (+3 more)

### Community 471 - "test_phase5_doctor.py"
Cohesion: 0.12
Nodes (11): client(), fixture, tests/test_phase5_doctor.py Phase 5: /api/doctor endpoint tests. Coverage: -…, If RuntimeManager raises, /api/doctor still returns 200 with a warn check., If DirectChatDoctor.check_all raises, /api/doctor still returns 200., MongoStore.__getattr__ proxies any name to a Motor collection, so…, Langfuse check is always emitted (pass or warn based on env)., test_doctor_langfuse_check_present() (+3 more)

### Community 472 - "TestRoutes"
Cohesion: 0.19
Nodes (7): _install_service(), Tests for agents/portfolio_api.py — the v5 portfolio board API. Loads the…, A materializer exception must not break /refresh (the board still returns), and…, Install a PortfolioService whose portfolio is fixed (no rebuild)., _seeded_manager(), TestBoardPayload, TestRoutes

### Community 473 - "test_telegram_diag_endpoint.py"
Cohesion: 0.12
Nodes (16): client(), fixture, tests/test_telegram_diag_endpoint.py — /api/telegram/diag HTTP endpoint.…, Build a TestClient against the FastAPI app with controlled env., The /api/telegram/diag endpoint returns 200., The endpoint returns the expected config fields., The endpoint must NOT return the full bot token — only a masked prefix., The endpoint includes diagnostic hints for common failure modes. (+8 more)

### Community 474 - "hermes_prompt.py"
Cohesion: 0.19
Nodes (15): build_chatml_system_prompt(), format_chatml_message(), format_tool_call(), format_tool_response(), messages_to_chatml(), model_supports_chatml(), parse_tool_call_from_chatml(), Any (+7 more)

### Community 475 - "MemoryMiddleware"
Cohesion: 0.17
Nodes (10): create_memory_middleware(), MemoryMiddleware, Any, Process incoming chat request and inject memories., Extract and save learnings from model responses., Factory function to create memory middleware instance., Middleware for automatic memory loading and injection., Detect AI coding tool from request headers. (+2 more)

### Community 476 - "AITellIssue"
Cohesion: 0.17
Nodes (8): AITellIssue, Find all AI tells in text, Find throat-clearing phrases, Find emphasis crutches (weak adverbs), Find meta-commentary (text referring to itself), Find Wh-sentence starters (weak prose starters), Find basic passive voice patterns (strict mode only), Format issues as human-readable report

### Community 477 - "Skill: repowise-intelligence"
Cohesion: 0.12
Nodes (15): 1. Graph Intelligence (Dependency Graph), 2. Git Intelligence, 3. Documentation Intelligence, 4. Decision Intelligence, Acceptance Checks, Directory Structure, Example Usage, Implementation Approach (+7 more)

### Community 478 - "ARCHITECTURE.md — Target Architecture"
Cohesion: 0.12
Nodes (15): 1. Target Repository Structure, 2. Dependency Rules, 3. Provider Architecture (Target), 4. Configuration Architecture (Target), 5. Event Bus Architecture (Target), 6. Scheduler Architecture (Target), 7. Dashboard Architecture (Target), 8. Migration Principles (+7 more)

### Community 479 - "_check_storage_health"
Cohesion: 0.12
Nodes (10): _check_storage_health(), health(), Path, Check if the storage backend is reachable. Works with BOTH MongoDB and SQLite:…, Authenticated system status summary for the Doctor screen., system_status(), Guard the version single-source-of-truth: every place that hardcodes the…, deployed_commit() (+2 more)

### Community 480 - "_valid_login_state"
Cohesion: 0.24
Nodes (15): Return True if a fetched oauth_states doc is a valid, unexpired login state., _valid_login_state(), _doc(), Regression tests for social-login (GitHub & Google) OAuth state handling. Bug…, MongoDB/motor returns naive UTC datetimes. Subtracting a naive datetime from an…, The login handlers must persist state via _store_login_state, not the session…, test_expired_state_rejected(), test_just_within_window_accepted() (+7 more)

### Community 481 - "Skill: repowise-intelligence"
Cohesion: 0.12
Nodes (15): 1. Graph Intelligence (Dependency Graph), 2. Git Intelligence, 3. Documentation Intelligence, 4. Decision Intelligence, Acceptance Checks, Directory Structure, Example Usage, Implementation Approach (+7 more)

### Community 482 - "The 10-Step Workflow"
Cohesion: 0.12
Nodes (15): Cross-Tool Compatibility, Quick Reference Card, Skill: session-planning — Mandatory Planning Workflow for All AI Agents, Step 10 — Close Out, Step 1 — Orient (free), Step 2 — Understand the Task, Step 3 — Load Relevant Skills, Step 4 — Research (if novel task) (+7 more)

### Community 483 - "Contributing to local-llm-server"
Cohesion: 0.12
Nodes (16): Architecture, Bug Reports, Changelog, Coding Standards, Commit Message Convention, Contributing to local-llm-server, Development Setup, Feature Requests (+8 more)

### Community 484 - "CEO Micro-Management"
Cohesion: 0.12
Nodes (16): A failed drive does not abandon the goal, CEO Micro-Management, Configuration reference, Escalation, and why it terminates, Five bounds, Operator surface, Tests, The 24x7 supervisor (+8 more)

### Community 485 - "467 Brutal Audit — File-by-File Status"
Cohesion: 0.12
Nodes (15): 467 Brutal Audit — File-by-File Status, Agent System, Backend & Services, Core Proxy & Routing, Direct Chat, Feature Matrix (spec §I — demotions needed), Frontend / Public Site (spec §H — 0% delivered), GitHub Workflows (+7 more)

### Community 486 - "Runbook — Apply the Fast Free NVIDIA Brain to Render (TASK 2)"
Cohesion: 0.12
Nodes (15): B.1 — Open the service's Environment tab, B.2 — Set these five keys on each service, B.3 — Sanity-check the secrets that must NOT regress, B.4 — Trigger TASK 5 keep-alive immediately, Option A — Blueprint sync (preferred), Option B — manual per-service editor, Rollback, Runbook — Apply the Fast Free NVIDIA Brain to Render (TASK 2) (+7 more)

### Community 487 - "SkillsScreen.jsx"
Cohesion: 0.12
Nodes (12): autoRecommendCompanySkills(), deleteCompany(), discoverRemoteSkills(), listCompanies(), listCompanySkills(), CompaniesPanel(), CATEGORY_COLORS, COMMERCE_SKILLS (+4 more)

### Community 488 - "implement_agent.py"
Cohesion: 0.16
Nodes (12): main(), _openai_tools_to_anthropic(), Safely insert an entry under ## [Unreleased] without touching the rest of the…, Convert OpenAI function-calling tool schemas to Anthropic tool schemas., Run the implementation agent loop using Claude Opus via Anthropic SDK. Returns…, _read_claude_md(), _run_anthropic_agent_loop(), _run_baseline_pytest() (+4 more)

### Community 489 - "HealthStatus"
Cohesion: 0.13
Nodes (5): OllamaProvider, Provider, HealthStatus, Provider health check result., Check provider health.

### Community 490 - "GeminiProvider"
Cohesion: 0.30
Nodes (5): GeminiProvider, Any, AsyncClient, Translate an OpenAI content array into Gemini parts. Image parts are carried…, Adapter for ``POST /models/{model}:generateContent``.

### Community 491 - "fabric_cli.py"
Cohesion: 0.29
Nodes (15): cmd_apply(), cmd_list(), cmd_new(), cmd_save(), cmd_show(), cmd_stitch(), _ensure_patterns_dir(), main() (+7 more)

### Community 492 - "sync_ngrok.py"
Cohesion: 0.26
Nodes (14): detect_ngrok_url(), dim(), fail(), header(), info(), main(), ok(), patch_platform_brain_via_switch_brain() (+6 more)

### Community 493 - "GuardResult"
Cohesion: 0.16
Nodes (8): GuardResult, Any, Check user input against input safety rules. Returns a GuardResult with…, Check model output against output safety rules. Returns a GuardResult with…, Unified check method. direction = 'input' or 'output'., Return guardrail statistics., Result of a guardrail check., TestGuardResult

### Community 494 - "ManagedAgentDreams"
Cohesion: 0.22
Nodes (4): ManagedAgentDreams, Manages recording session memories and consolidating them into dreams., Tests for ManagedAgentDreams., TestManagedAgentDreams

### Community 495 - "e2e/test_browser.py"
Cohesion: 0.21
Nodes (15): base_url(), do_login(), fail(), ok(), fixture, Page, Navigate to a page and verify it loads without errors., Verify server responds to health check before running browser tests. (+7 more)

### Community 496 - "test_dockerfile_ships_root_modules.py"
Cohesion: 0.17
Nodes (13): _dockerfile_text(), Regression guard: the backend image must ship every root-level Python module…, An env var set to empty string means unset, not a commit named ''., Unknown must read as unknown — a deploy check treats None as 'unverifiable' and…, True when the Dockerfile copies root .py modules wholesale (`COPY *.py ...`)., The worker's `python worker_main.py` start command needs worker_main.py., V2.0 Modernization: the image must ship `packages/` (provider_router,…, _ships_all_root_modules() (+5 more)

### Community 497 - "test_frontend_deployment_guards.py"
Cohesion: 0.20
Nodes (15): Step 3 runtime config must render checkboxes for each runtime., index.css must override appearance:none for checkboxes/radios., The checkbox appearance override must NOT set appearance:none (that would keep…, The checkbox appearance override must use 'auto' to request native rendering.…, SetupWizardPage must render <input type='checkbox'> for each provider toggle., _read(), test_api_redirects_respect_public_and_backend_paths(), test_index_css_checkbox_override_is_not_none() (+7 more)

### Community 498 - "test_glm52_brain.py"
Cohesion: 0.12
Nodes (15): tests/test_glm52_brain.py — PR #984 Verifies GLM-5.2 (z-ai/glm-5.2) is…, packages/ai/registry.py must register z-ai/glm-5.2., GLM-5.2 must have a lower priority number (higher precedence) than…, packages/ai/brain.py DEFAULT_FREE_NVIDIA_MODEL must be z-ai/glm-5.2., packages/ai/brain_config.py SAFE_DEFAULT_MODEL must be z-ai/glm-5.2., PROVIDER_PRESETS['nvidia'] must use z-ai/glm-5.2 for all roles., render.yaml must set NVIDIA_DEFAULT_MODEL + AGENT_*_MODEL to z-ai/glm-5.2., backend/server.py must have the brain migration startup task. (+7 more)

### Community 499 - "test_langfuse_agency_wide.py"
Cohesion: 0.12
Nodes (15): tests/test_langfuse_agency_wide.py — tests for PR #961 agency-wide Langfuse.…, langfuse_obs.py must define emit_agency_observation., emit_agency_observation must be a no-op when Langfuse is not configured., tasks/service.py must call emit_agency_observation for task execution., agent/agency.py must call emit_agency_observation for CEO directives., backend/server.py scheduler_tick must call emit_agency_observation., packages/ai/self_heal.py must call emit_agency_observation., emit_agency_observation must accept all documented parameters. (+7 more)

### Community 500 - "TestBrainFailoverBackoff"
Cohesion: 0.23
Nodes (7): The anti-wedge valve must not fire for an ordinary 429 backoff — otherwise it…, The threshold must clear the widest backoff ANY registered provider can earn.…, A corrupted/absurd cooldown must still be recoverable., The honest reset: probe permitted, failure history kept., A real success must still clear the breaker — allow_probe exists so that…, The behaviour the doom loop destroyed: each 429 waits longer. With…, TestBrainFailoverBackoff

### Community 501 - "SamConversation"
Cohesion: 0.17
Nodes (9): Process a voice command and return SAM's spoken response. Args: text: The…, Call the NVIDIA NIM LLM (free tier) for SAM's response., Rule-based fallback when the LLM is unavailable., A single voice conversation session with SAM., SamConversation, add_turn must append to history and increment command_count., History must be capped at 20 entries (10 turns)., test_conversation_add_turn() (+1 more)

### Community 502 - "Skill: agent-harness"
Cohesion: 0.13
Nodes (14): Architecture, Combining with Other Skills, Key Concepts, Output Format, Purpose, Safety Rules, Skill: agent-harness, Step 1 — Define the task clearly (+6 more)

### Community 503 - "Skill: checkpoint-strategy"
Cohesion: 0.13
Nodes (14): After a Loss Spike, Aggressive (Long Runs with Stable Training), Background, Checkpoint Policy Templates, Conservative (Recommended for First Runs), Integration Points, Output Format, Purpose (+6 more)

### Community 504 - "Process"
Cohesion: 0.13
Nodes (14): Anti-Patterns, Process, Purpose, Rules, Skill: debug-tracer, Step 1: Reproduce First, Step 2: Gather Evidence, Step 3: Form Hypotheses (+6 more)

### Community 505 - "Skill: local-ai-query"
Cohesion: 0.13
Nodes (14): 1. Verify Ollama is available, 2. Choose appropriate model, 3. Send query to local model, 4. Generate embeddings (for RAG), 5. List running models, Integration with ChromaDB (RAG), Limitations, Prerequisites (+6 more)

### Community 506 - "Skill: parallel-agents"
Cohesion: 0.13
Nodes (14): Combining with Other Skills, Core Concepts (from the Modal/OpenAI Agents SDK pattern), Example — parallel approach exploration, Example — parallel research, Output Format, Phase 1 — Decompose, Phase 2 — Dispatch (simulate parallelism), Phase 3 — Aggregate (+6 more)

### Community 507 - "Skill: parallel-worktrees"
Cohesion: 0.13
Nodes (14): Acceptance Checks, Common Patterns, Concept, Constraints, Instructions, Pattern A — Test main while you implement, Pattern B — Review reference during refactor, Pattern C — Hotfix without disturbing feature work (+6 more)

### Community 508 - "Design System: Taste Standard"
Cohesion: 0.13
Nodes (14): 1. Visual Theme & Atmosphere, 2. Color Palette & Roles, 3. Typography Rules, 4. Component Stylings, 5. Hero Section, 6. Layout Principles, 7. Responsive Rules, 8. Motion & Interaction (Code-Phase Intent) (+6 more)

### Community 509 - "Process"
Cohesion: 0.13
Nodes (14): Integration with Other Skills, Process, Purpose, Rules, Skill: ticket-to-pr, Step 1: Parse the Issue, Step 2: Context Prime, Step 3: Plan the Implementation (+6 more)

### Community 510 - ".get_state"
Cohesion: 0.22
Nodes (9): _now_iso(), Any, Connection, Return the desired + last-reported state for the admin UI., Operator flips the toggle. Persists + clears any prior lease. Returns the new…, Local daemon POSTs its heartbeat. If the operator's desired_state=on AND the…, `now_iso`: ISO-8601 string marking the reader's "now" — pass it in to stay…, Reviewer fix #f: lease must strip after heartbeats stop arriving. Simulates a… (+1 more)

### Community 511 - "Skill: user-research"
Cohesion: 0.13
Nodes (14): Architecture, As a Python library, As an agent tool, Auto-Registration, Files, Purpose, Pydantic Models (extra="forbid"), Sample-Size Math (+6 more)

### Community 512 - "Agency Core — Progress & Resume Log"
Cohesion: 0.13
Nodes (14): Agency Core — Progress & Resume Log, Audit (committed), Environment constraints discovered this session, How to resume (read before doing anything), Key findings (so we don't re-investigate), Open risks / must-know before merging, Phase 0 — Stabilize & quarantine (commit `713184a`, pushed), Planned CI-parity hardening (the immediate next commit) (+6 more)

### Community 513 - "Attention Mechanisms Internals"
Cohesion: 0.13
Nodes (14): Attention Complexity, Attention Mechanisms Internals, Causal Masking, Flash Attention, Grouped Query Attention (GQA), Multi-Head Attention (MHA), Multi-Query Attention (MQA), Parameter count for MHA: (+6 more)

### Community 514 - "issue_new_api_key"
Cohesion: 0.24
Nodes (12): issue_new_api_key(), Generate a new plaintext API key, persist hash + metadata, return (plain_key,…, main(), _make_store(), fixture, Security regression tests for key_store: hashing, constant-time compare, rate…, _reset_rate_state(), test_keys_stored_as_hash_not_plaintext() (+4 more)

### Community 515 - "allow_paid"
Cohesion: 0.19
Nodes (13): allow_paid(), _fetch_policy(), .github/scripts/provider_policy.py — Read the durable provider policy from the…, Fetch the provider policy from the backend API. Never raises., Return True if paid providers (Anthropic) are allowed by policy., Reset the cached policy (test helper)., reset_cache(), _call_review_llm() (+5 more)

### Community 516 - "NvidiaProvider"
Cohesion: 0.15
Nodes (7): NvidiaProvider, Provider, NVIDIA NIM provider adapter — wraps the existing provider_router logic. This is…, NVIDIA NIM — free LLM provider (meta/llama-3.3-70b-instruct)., RateLimit, Provider rate limit info., Return the provider's rate limits.

### Community 517 - "AdminSessionStore"
Cohesion: 0.18
Nodes (4): AdminSession, AdminSessionStore, _is_truthy(), WindowsCredentialAuthenticator

### Community 518 - "_push_down_where"
Cohesion: 0.14
Nodes (14): _fully_pushable(), _is_pushable_scalar(), _push_down_where(), Any, Scalar values whose `str()` form matches how they were stored in the indexed…, Build a SQL ``WHERE`` suffix from the subset of *query* conditions that map…, True if EVERY condition in *query* is expressible in the SQL WHERE. Unlike…, Try to satisfy a sorted/paginated find entirely in SQL. Returns the decoded… (+6 more)

### Community 519 - "asyncio"
Cohesion: 0.13
Nodes (8): requires_db, asyncio, Test that storage service can be initialized., Test company CRUD operations - skipped as requires specific config., Test that scanner service can be initialized., Test that specialist service can be initialized., End-to-end against the real Mongo (CI service): the exact handler sequence…, get_company_graph must surface persisted detections, and delete_company must…

### Community 520 - "router/health.py"
Cohesion: 0.20
Nodes (14): _enabled(), get_available_models(), invalidate_cache(), is_model_available(), Ollama model availability check with TTL cache. Keeps a short-lived cache of…, Force the next call to re-probe Ollama (useful in tests)., Return True if *model* is in the Ollama tag list (or health checks off).…, Return the set of model names currently present in Ollama. Returns an empty set… (+6 more)

### Community 521 - "DockerAgentAdapter"
Cohesion: 0.17
Nodes (10): DockerAgentAdapter, Any, TaskResult, TaskSpec, Adapter that runs agent tasks inside isolated Docker containers., Check whether Docker is available and report the adapter's runtime health.…, asyncio, test_docker_binary_missing() (+2 more)

### Community 522 - "AdminDigestRouterAuthTests"
Cohesion: 0.23
Nodes (5): DigestPayload, AdminDigestRouterAuthTests, Stub for telegram_service.NotificationDispatcher used by /send., Build a FastAPI TestClient against an app shell with only the…, _StubDispatcher

### Community 523 - "clear_wizard_state_cache"
Cohesion: 0.21
Nodes (10): clear_wizard_state_cache(), Override the persistence collection used for wizard state. Tests and hosted…, Clear the in-memory wizard-state cache., set_wizard_state_collection(), _FakeWizardCollection, SimpleNamespace, TestClient, _setup_client() (+2 more)

### Community 524 - "._sprint"
Cohesion: 0.19
Nodes (3): Tests for agents/agile_ceremonies.py — autonomous agile ceremonies. Loads…, TestGenerateBacklogRetro, TestGenerateSprintRetro

### Community 526 - "DecisionsStoreTests"
Cohesion: 0.13
Nodes (3): DecisionsStoreTests, Smoke: create() returns a fresh dec_<hex8> per call (no error surfaces from…, Backdates the older row via raw SQLite UPDATE so it falls outside the cutoff…

### Community 527 - "test_dockerfile_ships_config_dir.py"
Cohesion: 0.14
Nodes (14): _dockerfile_text(), Regression guard: the backend image must ship ``config/``. `config/llm/*.yaml`…, The two properties that made the ungated entry expensive in production., The ceiling that #1172 added must survive in the file that ships. Sized against…, Without this COPY the router silently runs on defaults in production., A shipped directory is worthless if the files moved out of it., A .dockerignore entry would defeat the COPY without touching it., A keyless local provider must not join the chain just by existing. ``ollama``… (+6 more)

### Community 528 - "_run"
Cohesion: 0.42
Nodes (14): _make_env(), CompletedProcess, Path, _run(), test_crlf_preserved_on_untouched_lines(), test_dry_run_does_not_mutate(), test_env_path_missing_file_exits_1(), test_force_rewrites_canonical_already_present() (+6 more)

### Community 529 - "test_openclaw_gateway.py"
Cohesion: 0.13
Nodes (5): fixture, tests/test_openclaw_gateway.py — OpenClaw in-process WebSocket gateway tests., Dockerfile.backend does NOT install @openclaw/cli (in-process gateway now)., render_yaml(), test_dockerfile_backend_no_openclaw_cli()

### Community 530 - "test_scanner_live.py"
Cohesion: 0.23
Nodes (14): _assert_scan_contract(), asyncio, parametrize, LIVE integration tests for the website scanner — these actually hit the real…, Representative large storefronts that commonly sit behind bot protection. Same…, Directly exercise the BuiltWith fallback against the live builtwith.com.…, The invariants that must hold for any live scan, bot-protected or not., A normal, non-bot-protected site must yield real detections. This is the… (+6 more)

### Community 531 - "test_telegram_task_callback.py"
Cohesion: 0.19
Nodes (11): _parked_task(), asyncio, fixture, Task, Telegram inline-button callbacks for the task pre-execution gate. Regression:…, _Recorder, store(), test_approve_button_approves_and_requeues() (+3 more)

### Community 532 - "Template"
Cohesion: 0.22
Nodes (6): Any, Path, agent/scaffolding.py — Project Scaffolding Creates new project skeletons from…, Write template files into *target_dir*. Skips existing files unless…, ScaffoldResult, Template

### Community 533 - "StopSlopChecker"
Cohesion: 0.14
Nodes (8): Initialize checker. Args: strict: If True, also report adverbs even if not in…, Remove most obvious AI tells from text, Detect and optionally remove AI tells from text, StopSlopChecker, Should format report correctly, Should report success on clean text, Should detect weak emphasis adverbs, Should detect meta-commentary

### Community 534 - "Process"
Cohesion: 0.14
Nodes (13): 1. Read and Understand the Issue, 2. Explore the Codebase, 3. Plan the Solution, 4. Implement, 5. Test, 6. Document, 7. Commit and Push, Notes (+5 more)

### Community 535 - "Skill: lr-schedule-advisor"
Cohesion: 0.14
Nodes (13): Background (Why This Matters), Common Mistakes, Cosine with Warmup (Recommended for Pretraining), Fine-tuning vs Pretraining, Integration Points, Output Format, Peak LR Heuristics by Model Size, Purpose (+5 more)

### Community 536 - "Instructions"
Cohesion: 0.14
Nodes (13): 1 — Tests green, 2 — Changelog updated, 3 — Determine the version bump, 4 — Update changelog, 5 — Commit the changelog update, 6 — Tag the release, 7 — Verify CI on the tag, 8 — Post-release (+5 more)

### Community 537 - "Instructions"
Cohesion: 0.14
Nodes (13): Acceptance Checks, `admin_auth.py` checklist, `agent/tools.py` checklist, Escalation, Instructions, `key_store.py` checklist, `proxy.py` auth middleware checklist, Risky Modules in This Repo (+5 more)

### Community 538 - "Process"
Cohesion: 0.14
Nodes (13): 1. Decompose the Task, 2. Sequence the Skills, 3. Execute in Order, 4. Handle Failures, 5. Synthesize Output, 6. Document the Composition, Example Compositions, Notes (+5 more)

### Community 539 - "Checks Performed"
Cohesion: 0.14
Nodes (13): 1. Round-trip Consistency, 2. Numeric Tokenization, 3. Whitespace Handling, 4. Special Character Coverage, 5. Fertility by Domain, 6. Vocabulary Overlap Check (for model updates), Background, Checks Performed (+5 more)

### Community 540 - "Skill: training-stability-monitor"
Cohesion: 0.14
Nodes (13): Example Checks Performed, Gradient Norm Check, Integration Points, Key Lessons (from LLM-from-scratch practitioners), Loss Spike Detection, LR Warmup Validation, Notes, Output Format (+5 more)

### Community 541 - "test_new_features_e2e.py"
Cohesion: 0.29
Nodes (12): APIRequestContext, base_url(), do_login(), fail(), ok(), fixture, Page, Result (+4 more)

### Community 542 - "monitor_colibri.py"
Cohesion: 0.24
Nodes (13): ArgumentParser, build_parser(), cmd_autostart_install(), cmd_status(), cmd_supervise(), _configure_logging(), main(), Namespace (+5 more)

### Community 543 - "admin_digest_router.py"
Cohesion: 0.23
Nodes (13): _build_payload_or_500(), _check_secret(), _expected_secret(), preview_digest_endpoint(), Any, get, post, Dry-run: same auth, returns the would-be markdown body but does NOT dispatch to… (+5 more)

### Community 544 - "Skill: branch-cleanup"
Cohesion: 0.14
Nodes (13): Acceptance Checks, Automation — post-merge hook (optional), Option A — git push (standard), Option B — GitHub API (use when `git push --delete` returns 403), Option C — Delete local tracking refs after remote deletion, Skill: branch-cleanup, Step 1 — Confirm master is up to date, Step 2 — List all remote branches (+5 more)

### Community 545 - "Skill: perplexity — Web Research via Perplexity API"
Cohesion: 0.14
Nodes (13): Applying to this Repo, How to Query, No API Key? Use WebSearch, Prerequisites, Quick query (one-shot Python call), Run inline, Skill: perplexity — Web Research via Perplexity API, Skill Steps (+5 more)

### Community 546 - "Instructions"
Cohesion: 0.14
Nodes (13): 1 — Tests green, 2 — Changelog updated, 3 — Determine the version bump, 4 — Update changelog, 5 — Commit the changelog update, 6 — Tag the release, 7 — Verify CI on the tag, 8 — Post-release (+5 more)

### Community 547 - "Instructions"
Cohesion: 0.14
Nodes (13): Acceptance Checks, `admin_auth.py` checklist, `agent/tools.py` checklist, Escalation, Instructions, `key_store.py` checklist, `proxy.py` auth middleware checklist, Risky Modules in This Repo (+5 more)

### Community 548 - "Quick-Note Issues Processing Summary"
Cohesion: 0.14
Nodes (13): 🔗 Branch References, ✅ Completed, Future Session, Immediate (Session-Aware), Issue #229 — Stop-Slop AI Quality Checker, Issue #263 — Graphiti Temporal Context, Issue #266 — ECC Multi-Harness Adapter, 💡 Key Learnings (+5 more)

### Community 549 - "Implementation Plan — DB-persisted, UI-switchable Brain (no redeploy)"
Cohesion: 0.14
Nodes (13): 0. Why this exists (root cause this fixes), 1. Hard constraints (from the owner), 2. Provider strategy (the recommendation), 3. Architecture, 3a. Store — `services/brain_config_store.py` (new), 3b. Call-time resolution — `agent/loop.py`, 3c. Admin API — `backend/server.py`, 3d. UI — `webui/frontend/src/pages` (+ `webui/router.py` / `providers.py`) (+5 more)

### Community 550 - "Backend changes"
Cohesion: 0.14
Nodes (13): `activation_api.py`, `app_settings.py` (new), Backend changes, `backend/company_api.py`, `db/sqlite_store.py`, Docs / changelog, Frontend changes, Goal (+5 more)

### Community 551 - "Runbook: Auto-Resume After Cooldown / Interruption"
Cohesion: 0.14
Nodes (13): Commands, Cooldown Detection, Cooldown Detection Logic, Force-Resume After Stale Lock, Forcing an Abort, How It Works, Inspecting a Stuck Run, Overview (+5 more)

### Community 552 - "SEO / GEO / AIO Audit Engine"
Cohesion: 0.14
Nodes (14): API, Architecture, Delegation plan → agent tasks, Demo from the UI, Exports — the full heavy report, Fetching bot-protected sites (`fetch_mode`), Provenance, Repo-aware auto-fixing (+6 more)

### Community 553 - "Traffic Distribution Across Providers"
Cohesion: 0.14
Nodes (14): A worked example, Adding capacity: multi-key rotation, Attribution, Configuration, Failure behaviour, Observability, Pre-call budget checks, Provider ids contain dashes (+6 more)

### Community 554 - "devDependencies"
Cohesion: 0.14
Nodes (14): react-scripts, devDependencies, jsdom, react-scripts, @testing-library/dom, @testing-library/jest-dom, @testing-library/react, @testing-library/user-event (+6 more)

### Community 555 - "overrides"
Cohesion: 0.14
Nodes (14): @tootallnate/once, overrides, bfj, css-select, http-proxy-agent, jsonpath, nth-check, postcss (+6 more)

### Community 556 - "mcp_server/server.py"
Cohesion: 0.25
Nodes (13): _check_auth(), _err(), _handle_tool(), health(), mcp_dispatch(), _ok(), Any, get (+5 more)

### Community 557 - "_parse_reset_epoch"
Cohesion: 0.21
Nodes (6): _parse_reset_epoch(), _ProviderQuota, Response, Parse x-ratelimit-* headers and update per-provider quota state. Safe to call…, Convert a provider reset-time header value to a monotonic deadline. Supported…, TestParseResetEpoch

### Community 558 - "_RedisBackend"
Cohesion: 0.22
Nodes (5): Redis-backed shared state using SET NX / DELETE / SETEX / INCR+EXPIRE., Lazy-create the Redis client (imported on first use so a missing ``redis``…, Clear all cooldown entries (for test teardown)., Clear all probe-lock entries (for test teardown). Mirrors…, _RedisBackend

### Community 559 - "cmd_autonomy"
Cohesion: 0.23
Nodes (13): _backend_get(), cmd_autonomy(), cmd_loops(), _grade_icon(), GET an un-gated backend read endpoint (/api/autonomy/status, /api/loops). These…, Snapshot of the agency's autonomy: active brain, loop readiness, dispatch., Loop Engineering fleet readiness + the costliest loops, from /api/loops., tests/test_telegram_observe.py Tests for the read-only "observe from Telegram"… (+5 more)

### Community 560 - "_process_task_callback"
Cohesion: 0.34
Nodes (13): _process_task_callback(), Handle Approve/Reject inline-button presses for task execution gates. Callback…, _make_fake_task(), _patch_workflow(), Robustness tests for the Telegram inline-button callback flow., test_approve_success_clears_spinner_and_edits_message(), test_reject_success_clears_spinner_and_edits_message(), test_storage_init_failure_clears_spinner() (+5 more)

### Community 561 - "test_critical_flows.py"
Cohesion: 0.29
Nodes (13): _do_login(), _http_ok(), _playwright(), Create a task via the REST API (the same endpoint the UI calls) and poll its…, Direct (non-agent) chat: hit the OpenAI-compatible proxy completion the same…, Best-effort login. Returns True if we end up authenticated., _require_backend(), _require_proxy() (+5 more)

### Community 562 - "test_regression.py"
Cohesion: 0.14
Nodes (12): browser_login(), main(), fixture, Full desktop regression suite., Full mobile regression suite (navigation + key page loads)., Log in through the browser UI. Returns True on success., Activation: status, users., regression_base_url() (+4 more)

### Community 563 - "test_autonomy_pipeline_regressions.py"
Cohesion: 0.15
Nodes (13): asyncio, Regression tests for the autonomy pipeline bugs that blocked the agency from…, The README's zero-dependency deploy uses ``STORAGE_BACKEND=sqlite``. Pre-fix:…, The whole point of durable persistence is that schedules survive a process…, APScheduler fires jobs from a background thread with no event loop. Pre-fix:…, # NOTE: do NOT set STORAGE_BACKEND at module level — it would pollute every, The dataclass exposes ``enabled`` (bool) only — code that read ``.status``…, End-to-end: activate_company() on a fresh company creates all 6… (+5 more)

### Community 566 - "TestDisabledReasonRendering"
Cohesion: 0.14
Nodes (5): ``describe_disabled_reason`` is rendered next to the on/off switch. The stored…, Anthropic sends 400 for an empty balance, not 402., A reason the operator cannot read still beats no reason at all., Guards the seam: the writer and this renderer must not drift apart. Scans the…, TestDisabledReasonRendering

### Community 567 - "_FakeSQLiteStore"
Cohesion: 0.18
Nodes (10): _FakeSQLiteStore, asyncio, parametrize, Simulates a SQLite-style store with load_all/upsert/remove., Duplicate-named rows must collapse to newest on BOTH backends. Regression for…, Stale unfired run-once jobs (run_count==0, old created_at) must be deleted. The…, TASK_DISPATCH_CONCURRENCY=1 must prevent concurrent task execution. The…, test_dispatcher_honors_concurrency_env() (+2 more)

### Community 568 - "test_task_clarification.py"
Cohesion: 0.15
Nodes (5): auth_headers(), fixture, Tests for needs_clarification status and /api/tasks/{id}/clarify endpoint., Get auth headers for an admin user., task_id()

### Community 569 - "_TFIDFIndex"
Cohesion: 0.18
Nodes (9): Lightweight TF-IDF index over a fixed document collection. Sparse dict vectors…, Return ``(doc_index, cosine_score)`` pairs for the top-*k* matches., _TFIDFIndex, test_tfidf_empty_corpus(), test_tfidf_empty_query(), test_tfidf_finds_relevant(), test_tfidf_scores_between_0_and_1(), test_tfidf_scores_ordered_descending() (+1 more)

### Community 570 - "Process"
Cohesion: 0.15
Nodes (12): Output Format, Process, Purpose, Rules, Skill: auto-fix, Step 1: Discover Fix Commands, Step 2: Run Fixers (Auto-fixable), Step 3: Run Checkers (Non-auto-fixable) (+4 more)

### Community 571 - "Skill: Brain Dump"
Cohesion: 0.15
Nodes (12): Example Prompt to Trigger, Instructions, Notes, Output Format, Purpose, Skill: Brain Dump, Step 1: Capture Everything, Step 2: Categorize (+4 more)

### Community 572 - "Process"
Cohesion: 0.15
Nodes (12): Process, Purpose, Rules, Skill: context-prime, Step 1: Read Core Docs, Step 2: Map the Architecture, Step 3: Find Conventions, Step 4: Understand Data Flow (+4 more)

### Community 573 - "Instructions"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Instructions, Role 1: Security Reviewer, Role 2: Correctness Reviewer, Role 3: Performance Reviewer, Role 4: Maintainability Reviewer, Skill: council-review, Step 1 — Gather the diff (+4 more)

### Community 574 - "Skill: duplicate-thread"
Cohesion: 0.15
Nodes (12): Files, How It Works, In a Claude prompt, Integration, Manual duplication, Merging Back, meta.json Schema, Purpose (+4 more)

### Community 575 - "Skill: Email Triage"
Cohesion: 0.15
Nodes (12): Example Prompt to Trigger, Instructions, Notes, Output Format, Purpose, Skill: Email Triage, Step 1: Intake, Step 2: Triage Categories (+4 more)

### Community 576 - "Process"
Cohesion: 0.15
Nodes (12): Anti-Patterns, Process, Purpose, Rules, Skill: feature-flag, Step 1: Assess Flag Need, Step 2: Define the Flag, Step 3: Implement the Guard (+4 more)

### Community 577 - "Process"
Cohesion: 0.15
Nodes (12): 1. Review Staged and Unstaged Changes, 2. Review Commit History, 3. Validate Commit Messages, 4. Clean Up if Needed, 5. Confirm Branch State, 6. Push, Notes, Output (+4 more)

### Community 578 - "Skill: graphify — Knowledge Graph Token Optimization"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Claude's query protocol (use this instead of Read tool for exploration):, Graph Artifacts — What to Commit, How to Use the Graph (Token Savings Protocol), Installation (one-time per machine), Instead of reading raw files:, Key commands:, Relationship to repowise-intelligence Skill (+4 more)

### Community 579 - "Skill: prompt-library"
Cohesion: 0.15
Nodes (12): 1. Sync Snapshots, 2. Generate Library Index, 3. Generate TRANSPARENCY.md, 4. Update CHANGELOG.md in prompts/, 5. Commit, Directory Structure Created, Output, Purpose (+4 more)

### Community 580 - "Skill: prompt-transparency"
Cohesion: 0.15
Nodes (12): 1. Collect All Agent & Skill Definitions, 2. Extract Key Behavioral Dimensions, 3. Generate Transparency Report, 4. Flag Risks, 5. Commit the Report, Example Usage, Inspiration, Output Format (+4 more)

### Community 581 - "Skill: Research"
Cohesion: 0.15
Nodes (12): Example Prompt to Trigger, Instructions, Notes, Output Format, Purpose, Skill: Research, Step 1: Define the Research Question, Step 2: Identify Source Categories (+4 more)

### Community 582 - "Skill: scope-guard"
Cohesion: 0.15
Nodes (12): Anti-Patterns to Avoid, Output Format, Process, Purpose, Rules, Skill: scope-guard, Step 1: Define the Scope Contract, Step 2: Pre-Implementation Check (+4 more)

### Community 583 - "admin_update_task_router.py"
Cohesion: 0.22
Nodes (12): _expected_admin_secret(), _extract_admin_token(), BaseModel, backend/admin_update_task_router.py Step 1: POST…, Mount the update-task endpoint on ``app``. Idempotent: skips if a path with the…, Body for ``POST /api/workflow/orchestrator/update-task/{run_id}``.…, Resolve the admin secret from env. Order matches admin_digest_router.py:…, Inject ``additional_instructions`` into a paused or running WorkflowRun.… (+4 more)

### Community 584 - "ProviderManager"
Cohesion: 0.17
Nodes (8): ChatResponse, ProviderManager, Any, Provider, Coordinates provider selection, failover, and health., Return providers sorted by priority (lowest = highest priority)., Send a chat request with automatic failover. Retry policy: 1. If ``model`` is…, Check health of all configured providers.

### Community 585 - "Instructions"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Instructions, Role 1: Security Reviewer, Role 2: Correctness Reviewer, Role 3: Performance Reviewer, Role 4: Maintainability Reviewer, Skill: council-review, Step 1 — Gather the diff (+4 more)

### Community 586 - "Skill: graphify — Knowledge Graph Token Optimization"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Claude's query protocol (use this instead of Read tool for exploration):, Graph Artifacts — What to Commit, How to Use the Graph (Token Savings Protocol), Installation (one-time per machine), Instead of reading raw files:, Key commands:, Relationship to repowise-intelligence Skill (+4 more)

### Community 587 - "Skill: platform-setup — Autonomous Agency Bootstrap"
Cohesion: 0.15
Nodes (12): Ongoing autonomous operation, Phase 1 — Verify deployment health (no auth needed), Phase 2 — Login as admin, Phase 3 — Onboard the platform itself as a company, Phase 4 — Verify specialists were provisioned, Phase 5 — Configure GitHub integration, Phase 6 — Trigger first agency cycle manually, Phase 7 — Verify autonomous schedule is active (+4 more)

### Community 588 - "Workspace Isolation Architecture"
Cohesion: 0.15
Nodes (12): Configuration, Directory Layout, Error Handling, Lifecycle States, Metrics, Overview, Path Derivation, Path Safety (+4 more)

### Community 589 - "Device compatibility and model picks"
Cohesion: 0.15
Nodes (12): Acceleration at a glance, Apple Silicon: chip tier vs bandwidth (qualitative), Desktops and workstations, Device compatibility and model picks, Edge cases, How to read memory on different platforms, Laptops and all-in-ones, NVIDIA examples by VRAM (CUDA) (+4 more)

### Community 590 - "Autonomy Uplift — Living Roadmap & Detailed Implementation Specs"
Cohesion: 0.15
Nodes (12): 0. The goal (operator's words), 1. Shipped ✅, 2. In flight 🟡, 3. Pending ⬜ — detailed implementation specs, 3a. Apply the slop-gate to the sibling auto-PR scripts ✅  (size: S), 3b. Hermes — **our own** Hermes server (in-repo), UI-wired ✅  (size: M), 3c. CRISPY — harden, then re-enable ✅  (size: L, risky-module-review), 3d. Phase 3 — auto-PR *quality* beyond the slop-gate ✅  (size: M) (+4 more)

### Community 591 - "OpenClaw — iOS Control of the Agency (Single-Service Free-Tier Deploy)"
Cohesion: 0.15
Nodes (12): 1. Set env vars on the existing `local-llm-server` service, 2. Deploy, 3. Check the status, 4. Get the pairing QR, 5. Pair and verify, Alternative: Telegram bot, Architecture (single-service), Free-tier caveats (+4 more)

### Community 592 - "rules"
Cohesion: 0.15
Nodes (12): rules, import/no-anonymous-default-export, jsx-a11y/anchor-is-valid, jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/no-static-element-interactions, no-console, no-template-curly-in-string (+4 more)

### Community 593 - "ChatResponse"
Cohesion: 0.18
Nodes (5): GroqProvider, Provider, Groq provider adapter — free, fast LLM (deepseek-r1-distill-llama-70b)., ChatResponse, Standard response from a provider chat call.

### Community 594 - "Summary"
Cohesion: 0.15
Nodes (12): Checklist, Rollout notes, Summary, Test plan, UNIT 1 — Fix duplicate ceo_direct tasks ✅, UNIT 2 — Portfolio → task materializer (default ON) ✅, UNIT 3 — Config hygiene (zero behavior change) ✅, UNIT 4 — Commit model catalog `config/models.yaml` ✅ (+4 more)

### Community 595 - "Agent Transparency Report"
Cohesion: 0.15
Nodes (12): Agent Transparency Report, Guardrails and Limits, How to Verify This, Human Oversight Points, 🔨 Implementer, ⚖️ Judge, 📋 Planner, 🔍 Reviewer (+4 more)

### Community 596 - "update_provider_policy"
Cohesion: 0.19
Nodes (12): _get_provider_policy(), ProviderPolicyUpdate, BaseModel, get, put, Read the durable provider policy, falling back to a safe default. Returns a…, Persist the provider policy and return the new state., Return the durable provider policy (single source of truth for paid-provider… (+4 more)

### Community 597 - ".publish"
Cohesion: 0.17
Nodes (7): Any, Task, Broadcast an event to all matching subscribers. Returns the number of callbacks…, Fire-and-forget publish. Creates a background task. Returns the asyncio.Task so…, Return recent events for a topic., Return bus statistics., Check if a topic matches a pattern with * and ** wildcards.

### Community 598 - "_InMemoryBackend"
Cohesion: 0.18
Nodes (4): _InMemoryBackend, Single-process backend using asyncio.Lock + dicts with TTL timestamps., Clear all cooldown entries (for test teardown)., Clear all probe-lock entries (for test teardown). ``cooldown_clear`` only…

### Community 599 - "_resolve_push_token"
Cohesion: 0.22
Nodes (11): Verify execution results., GitHub token used to push branches / open PRs during EXECUTION (#506).…, _resolve_push_token(), _clean_env(), fixture, tests/test_orchestrator_push_token.py — #506 push/PR token resolution.…, test_falls_through_gh_pat_and_github_token(), test_internal_run_uses_server_token() (+3 more)

### Community 600 - "test_agile_api.py"
Cohesion: 0.15
Nodes (4): auth_headers(), fixture, Tests for /api/agile/* endpoints., Get auth headers for the seeded admin user (matched to seed_admin email).

### Community 601 - "test_app_settings.py"
Cohesion: 0.19
Nodes (11): asyncio, fixture, Tests for app_settings — DB-persisted settings + onboarding-gate default. These…, Point db.get_store() at an isolated temp SQLite DB., is_user_onboarding_allowed falls back to the global default for users with no…, sqlite_store(), test_defaults_when_unset(), test_gate_default_controls_unlisted_user() (+3 more)

### Community 602 - "TestModelCostTableUpdates"
Cohesion: 0.26
Nodes (3): New models are present in the cost table with sensible prices., get_cost_table() API exposes the new models with correct structure., TestModelCostTableUpdates

### Community 603 - "TestMCPClientStructuredOutput"
Cohesion: 0.31
Nodes (5): asyncio, Tests for MCPClient.call_tool_structured() using an async mock., call_tool() (legacy) is unchanged., list_tools() already returns raw tool dicts; outputSchema is preserved., TestMCPClientStructuredOutput

### Community 604 - "TestDecisionsBotLinks"
Cohesion: 0.21
Nodes (4): tests/test_decisions_bot_links.py Pytest coverage for the new…, Decision prompts that exist *before* the orchestrator creates a run (e.g. a…, Re-sending the same Telegram message (offset rewind, bot restart re-delivery)…, TestDecisionsBotLinks

### Community 605 - "test_deploy_trigger_covers_image.py"
Cohesion: 0.21
Nodes (12): _image_copy_sources(), Regression guard: the Render deploy trigger must cover everything the image…, `packages/` holds the AI layer — the most deploy-sensitive code there is., The health step must be able to fail. It previously polled for any 200 starting…, Top-level paths ``Dockerfile.backend`` copies into the runtime image., Top-level path prefixes in the deploy workflow's push ``paths:`` filter., The filter must take root modules wholesale, matching `COPY *.py ./`. Listing…, test_deploy_verification_cannot_pass_silently_on_failure() (+4 more)

### Community 606 - "TestRuntimeControl"
Cohesion: 0.15
Nodes (7): Test runtime start/stop endpoints return informational payloads in remote…, Get authentication token for admin user, GET /runtimes/ should return list of runtimes, POST /runtimes/{id}/start should return non-blocking informational payload in…, POST /runtimes/stop-all should return non-blocking informational payload, PUT /runtimes/policy should work with valid auth, TestRuntimeControl

### Community 607 - "TestKillSwitchDurability"
Cohesion: 0.15
Nodes (4): The local mirror is what keeps operator intent during a Mongo outage., A restart clears every in-memory cache; the state must still be there., Never claim a switch took effect when no store accepted it. Mongo off…, TestKillSwitchDurability

### Community 608 - "TestRouterIntegration"
Cohesion: 0.31
Nodes (6): anyio, The behaviour this whole change exists for: once the first free provider has…, No strategy and no budgets configured — behaviour is unchanged., The director must see the provider round-trip, not the round trip plus JSON…, With nowhere to route, skipping would turn a slow request into a failed one —…, TestRouterIntegration

### Community 609 - "verify_token"
Cohesion: 0.15
Nodes (13): Test JWT token creation and verification., Test refresh token creation and validation., Test that access token fails with refresh validation., Test refreshing access token with refresh token., test_invalid_token_type(), test_refresh_access_token(), test_refresh_token_creation(), test_token_creation_and_verification() (+5 more)

### Community 610 - "WorkspaceManifest"
Cohesion: 0.17
Nodes (8): _now(), Any, BaseModel, WorkspaceStatusLiteral, Structured manifest for an isolated workspace., Transition to a new status and update cleanup eligibility., Touch the last_heartbeat timestamp., WorkspaceManifest

### Community 611 - "CLAUDE.md — agent/"
Cohesion: 0.17
Nodes (11): Adding New Tools, `agent/loop.py` — `_commit_step()`, `agent/loop.py` — `_local_safety_check()`, `agent/tools.py` — `apply_diff()`, CLAUDE.md — agent/, Invariants — Do Not Break, Model Env Vars, Security Surface (+3 more)

### Community 612 - "skill_registry.py"
Cohesion: 0.17
Nodes (6): agent/skill_registry.py — Dynamic Skill Registry & Recommender Fetches skill…, Holds a pre-compiled regex + the original tech name., set_skill_registry(), _TechPattern, Tests for module-level pre-compiled pattern constants., TestPreCompiledPatterns

### Community 613 - "Trajectory"
Cohesion: 0.20
Nodes (7): Path, Persist trajectory as JSON and return the file path., Reload a previously saved trajectory (read-only replay)., Return a summary dict suitable for logging / leaderboards., Complete record of one agent run against one task. Compatible with the…, Mark the trajectory as complete., Trajectory

### Community 614 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Idempotency Rules, Instructions, Skill: cooldown-resume, Step 1 — Read the checkpoint files, Step 2 — Assess the state, Step 3 — Verify changed files are correct, Step 4 — Run tests to confirm baseline (+3 more)

### Community 615 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Current Dependencies (quick reference), Instructions, Skill: dependency-audit, Step 1 — Evaluate the new dependency, Step 2 — Pin appropriately, Step 3 — Install and verify, Step 4 — Check for conflicts (+3 more)

### Community 616 - "Process"
Cohesion: 0.17
Nodes (11): 1. Audit Existing Skills, 2. Identify Gaps, 3. Propose Improvements, 4. Implement, 5. Validate, Notes, Output, Process (+3 more)

### Community 617 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Instructions, Skill: smart-commit, Step 1 — Confirm changelog is updated, Step 2 — Run tests, Step 3 — Check for obvious issues, Step 4 — Stage your changes, Step 5 — Write a conventional commit message (+3 more)

### Community 618 - "Skill: system-prompt-audit"
Cohesion: 0.17
Nodes (11): 1. Inventory Collection, 2. Consistency Check, 3. Safety Check, 4. Generate Audit Report, 5. Exit Codes, Integration, Purpose, Related Skills (+3 more)

### Community 619 - "Skill: task-alive-updates"
Cohesion: 0.17
Nodes (11): Example Output, Files, How It Works, Implementation Rules, In a shell script / agent harness, In Claude task descriptions, Integration with parallel-agents, Purpose (+3 more)

### Community 620 - "Process"
Cohesion: 0.17
Nodes (11): 1. Read the Task Carefully, 2. Define the Boundary, 3. Identify Temptations, 4. Lock the Scope, 5. Out-of-Scope Findings, Notes, Output, Process (+3 more)

### Community 621 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Instructions, Skill: test-first-executor, Step 1 — Identify what needs testing, Step 2 — Write the test first, Step 3 — Confirm the test FAILS before implementation, Step 4 — Implement until the test passes, Step 5 — Run the full suite (+3 more)

### Community 622 - "LocalBrainStore"
Cohesion: 0.21
Nodes (8): BaseModel, backend/admin_local_brain_router.py — admin-session proxy for the local-brain…, _store(), ToggleBody, LocalBrainStore, backend/local_brain_store.py — DB-persisted state for the local GLM 5.2 brain.…, SQLite-backed store for the local GLM brain toggle + heartbeat., Same mirror file brain_config already uses. One file, fewer surprises.

### Community 623 - "_is_ephemeral_user"
Cohesion: 0.27
Nodes (11): _is_ephemeral_user(), True when this user's companies should be temporary (reaped after TTL).…, Best-effort auth provider for a user dict. social_auth users carry an explicit…, _resolve_provider(), Tests for company lifecycle gating — who gets ephemeral vs persistent agencies.…, test_admin_local_is_persistent(), test_github_non_admin_is_ephemeral(), test_google_non_admin_is_ephemeral() (+3 more)

### Community 624 - "14. Standing Instructions — Universal Agent Discipline"
Cohesion: 0.17
Nodes (12): 14.10 Fake Competence — the 10 Patterns, 14.11 Final Gate — run on every answer before sending, 14.1 Reading Intent, 14.2 Breaking Problems Down, 14.3 Effort Placement, 14.4 Verification, 14.5 Known vs Guessed, 14.6 Self-Attack (+4 more)

### Community 625 - "Skill: agent-browser — Real Chrome Browser Automation"
Cohesion: 0.17
Nodes (11): Applying to the local-llm-server Platform, Core Commands, How to Use This Skill, Installation (one-time), Skill: agent-browser — Real Chrome Browser Automation, Step 1 — Check Chrome is running with debugging, Step 2 — Navigate and snapshot, Step 3 — Interact using element refs (+3 more)

### Community 626 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Idempotency Rules, Instructions, Skill: cooldown-resume, Step 1 — Read the checkpoint files, Step 2 — Assess the state, Step 3 — Verify changed files are correct, Step 4 — Run tests to confirm baseline (+3 more)

### Community 627 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Current Dependencies (quick reference), Instructions, Skill: dependency-audit, Step 1 — Evaluate the new dependency, Step 2 — Pin appropriately, Step 3 — Install and verify, Step 4 — Check for conflicts (+3 more)

### Community 628 - "Skill: dev-browser — Browser Automation via Sandboxed JS"
Cohesion: 0.17
Nodes (11): Browser API, CLI flags, Connect to existing Chrome, Full script example (Playwright Page API), Installation, LLM usage patterns, Performance, Primary invocation styles (+3 more)

### Community 629 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Instructions, Skill: test-first-executor, Step 1 — Identify what needs testing, Step 2 — Write the test first, Step 3 — Confirm the test FAILS before implementation, Step 4 — Implement until the test passes, Step 5 — Run the full suite (+3 more)

### Community 630 - "Agent Orchestration Design"
Cohesion: 0.17
Nodes (12): Agent Orchestration Design, Execution Pathway, Four-Agent Structure, Key Invariants, OSS Inspirations (Clean-Room), Overview, Plan-First Pathway, Release-Readiness Pathway (+4 more)

### Community 631 - "Universality: case-coverage matrix"
Cohesion: 0.17
Nodes (12): A. Connection & credentials, B. Provider & host, C. Delivery / branch policy  *(detected — see DeliveryPolicy)*, D. CI / checks, E. Review automation & humans, F. Repo state & conflicts, G. Task origin, H. Governance / safety / HITL (+4 more)

### Community 632 - "Quantization Internals"
Cohesion: 0.17
Nodes (12): Absmax Quantization (Symmetric), Activation Quantization, AWQ (Activation-Aware Weight Quantization), Bits and Bytes (bitsandbytes), Data Types, GGUF / llama.cpp Quantization, GPTQ (Post-Training Quantization for GPT), Post-Training Quantization (PTQ) (+4 more)

### Community 633 - "Implementation — DB-persisted, UI-switchable Brain (PR #824 follow-up)"
Cohesion: 0.17
Nodes (11): Architecture (per plan §3), Files touched, Hard constraints (from the plan) — all met, Implementation — DB-persisted, UI-switchable Brain (PR #824 follow-up), Modified files, New files, Resolution precedence, Risks & mitigations (per plan §6) (+3 more)

### Community 634 - "2. Pending ⬜ — detailed implementation specs"
Cohesion: 0.17
Nodes (11): 0. The goal (unchanged), 1. Shipped in the previous pass ✅ (recap, do not redo), 2. Pending ⬜ — detailed implementation specs, 3. Deferred 🔭, 4. Operating notes (unchanged, for implementers), N1. Activate the reliability spine — wire the watchdog, schedule the digest ⬜  (size: M, risk: low), N2. Surface Hermes (and all runtimes) status in the Doctor/Runtimes UI ⬜  (size: S, risk: low), N3. Real CI-failure autofix — close the "Agency: cannot fix tests" loop (issue #398) ✅  (size: L, risk: medium) (+3 more)

### Community 635 - "467 Public Site Truth Spec"
Cohesion: 0.17
Nodes (11): 467 Public Site Truth Spec, Architecture Page Truth, Content Rules, Current State, Feature Matrix Truth, Required: Public Site Truth Spec, Site Structure, Tier System for Features (+3 more)

### Community 636 - "Render MCP — autonomous platform debugging and environment monitoring"
Cohesion: 0.17
Nodes (11): 1. Coding sessions — stdio, via `.mcp.json`, 2. The running agency — Streamable HTTP against a deployed sidecar, Configuration, Enabling it, HTTP API, If the private address does not resolve, Render MCP — autonomous platform debugging and environment monitoring, The monitoring loop (+3 more)

### Community 637 - "TestRequireAdmin"
Cohesion: 0.29
Nodes (3): Return a FastAPI dependency that checks for a specific permission., require_permission(), TestRequireAdmin

### Community 638 - "test_p0_roadmap_a4_a5_b2.py"
Cohesion: 0.26
Nodes (6): get_steering_injector(), Return recommended steering labels for a given task category. Used by the model…, Return the module-level SteeringInjector singleton., steering_for_task(), TestSteeringForTask, TestSteeringSingleton

### Community 639 - "Kimi Web-Bridge Service"
Cohesion: 0.17
Nodes (11): API, Connecting to the Main Backend, Docker, Environment Variables, `GET /health`, `GET /v1/models`, How It Works, Kimi Web-Bridge Service (+3 more)

### Community 640 - "test_docs_consistency.py"
Cohesion: 0.17
Nodes (11): parametrize, tests/test_docs_consistency.py — structural defense against narrative drift.…, browserbase / agent-browser / perplexity are MCP/CLI tools, NOT runtime skills.…, Per-task worktree isolation is implemented in…, A DISABLED feature must be enabled=False and carry a note explaining why —…, The brief: no feature may be presented as production-grade while it is still…, test_beta_or_experimental_features_carry_a_note(), test_disabled_features_are_documented_and_not_enabled() (+3 more)

### Community 641 - "TestAuthAndTaskCreation"
Cohesion: 0.17
Nodes (7): POST /api/tasks/ without agent_id should attempt auto-assignment if agents exist, Test authentication and task creation with owner assignment, Get authentication token for admin user, Return headers with Bearer token, Verify login returns a valid access token, POST /api/tasks/ should store the authenticated user as owner, not 'unknown, TestAuthAndTaskCreation

### Community 642 - "test_providers_live_e2e.py"
Cohesion: 0.27
Nodes (11): _auth_headers(), _login_via_email(), Any, tests/test_providers_live_e2e.py — Live integration test for…, The /api/providers list now annotates each record with is_brain/role. The role-…, Skip the current test with a structured reason (pytest.skip is fine too)., POST /api/auth/login and return the parsed JSON body. Raises on failure., Full JWT round-trip: login → PUT → GET → cleanup. Asserts that the providers… (+3 more)

### Community 643 - "test_skill_registry.py"
Cohesion: 0.20
Nodes (7): _FakeClient, _FakeResp, tests/test_skill_registry.py — Unit tests for agent/skill_registry.py, Stub httpx client for nested-registry fetch tests., Production regression: server started from a non-repo CWD indexed 0 local…, test_local_skills_dir_defaults_to_repo_root_not_cwd(), test_nested_registry_indexes_deeply_nested_skills()

### Community 644 - "validate_job_id"
Cohesion: 0.18
Nodes (4): parametrize, TestPathTraversalPrevention, Validate and return a job ID, or raise InvalidJobIdError., validate_job_id()

### Community 645 - "EvalHarness"
Cohesion: 0.24
Nodes (7): EvalHarness, Task, Runs agent functions against Tasks, records Trajectories and produces…, Execute the agent on a single task and return an EvalResult., Delegate to the agent callable (sync or async)., Run multiple tasks and aggregate into a BenchmarkReport. Set concurrency > 1 to…, AgentFn

### Community 646 - "SavingsTracker"
Cohesion: 0.18
Nodes (6): get_savings_summary(), Any, Get token savings summary., Track cumulative token savings across filtering operations., One-line summary of savings (rtk gain style)., SavingsTracker

### Community 647 - "_extractive_compress"
Cohesion: 0.18
Nodes (11): _extractive_compress(), Split text into sentences on . ! ? followed by whitespace or end-of-string., Return the highest-value sentences from *text* within *max_tokens*. Each…, _split_sentences(), test_compress_empty_text(), test_compress_prefers_query_relevant_sentences(), test_compress_result_non_empty_for_non_empty_input(), test_compress_short_text_verbatim() (+3 more)

### Community 648 - ".get_overview"
Cohesion: 0.24
Nodes (6): Any, Provides an architecture summary, module map, and git health., Identifies frequently changed files using git history., Guesses entry points based on file names and common patterns., Basic git health metrics., Hotspot scores and potential impact analysis.

### Community 649 - "RepowiseIntelligence"
Cohesion: 0.33
Nodes (5): Path, Returns a structural overview of the repository., Workhorse tool for packing content and metrics of target files., Get dependencies from our built intelligence., RepowiseIntelligence

### Community 650 - "RegistrySkill"
Cohesion: 0.25
Nodes (6): Any, A skill fetched from a remote or local registry., Return ranked skill recommendations based on tech stack, active workflow types,…, RegistrySkill, Tests for RegistrySkill dataclass., TestRegistrySkill

### Community 651 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Failure / Retry Behaviour, Instructions, Skill: implementation-planner, Step 1 — Understand the current state, Step 2 — Write the plan, Step 3 — Get implicit approval before coding, Step 4 — Implement (+2 more)

### Community 652 - "Skill: pro-workflow"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Model Selection Guide, Phase 1 — Research (Scout), Phase 2 — Plan, Phase 3 — Implement, Phase 4 — Wrap Up, Skill: pro-workflow (+2 more)

### Community 653 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Learnings File Doesn't Exist?, Skill: replay-learnings, Step 1 — Read the learnings file, Step 2 — Filter relevant learnings, Step 3 — Check recent checkpoint history, Step 4 — Surface blockers from previous session (+2 more)

### Community 654 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Skill: repo-memory-updater, Step 1 — Inventory what changed, Step 2 — Check root AGENTS.md, Step 3 — Check module AGENTS.md files, Step 4 — Update .Codex/state/, Step 5 — Commit the update (+2 more)

### Community 655 - "Skill: resource-panel"
Cohesion: 0.18
Nodes (10): Ask Claude to emit a resource panel, Automated via shell (git-based), Fields, Files, How to Use, Integration, Output Format, Purpose (+2 more)

### Community 656 - "Skill: sandboxed-exec"
Cohesion: 0.18
Nodes (10): Example — run tests in isolation, Example — validate a generated script before saving, How It Works, Output Format, Purpose, Security Notes, Skill: sandboxed-exec, Steps (for Claude to follow) (+2 more)

### Community 657 - "Workflow"
Cohesion: 0.18
Nodes (10): Acceptance checks, Fill these in, Skill: client-onboarding, Step 1 — Create the company and kick off onboarding, Step 2 — Poll progress, Step 3 — Verify specialists were provisioned, Step 4 — Confirm the 24x7 agency runtime is live, Step 5 — Note real gaps instead of pretending they're solved (+2 more)

### Community 658 - "ECC Harness Patterns Skill"
Cohesion: 0.18
Nodes (10): 1. Harness Detection & Adaptation, 2. Session Lifecycle Hooks, 3. Cross-Harness Model Selection, 4. Persistent Harness Registry, ECC Harness Patterns Skill, Files to Create/Modify, Implementation Plan, Patterns to Adopt (+2 more)

### Community 659 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Failure / Retry Behaviour, Instructions, Skill: implementation-planner, Step 1 — Understand the current state, Step 2 — Write the plan, Step 3 — Get implicit approval before coding, Step 4 — Implement (+2 more)

### Community 660 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Skill: repo-memory-updater, Step 1 — Inventory what changed, Step 2 — Check root CLAUDE.md, Step 3 — Check module CLAUDE.md files, Step 4 — Update .claude/state/, Step 5 — Commit the update (+2 more)

### Community 661 - "Stop-Slop Quality Skill"
Cohesion: 0.18
Nodes (10): AI Tells Detected, Business Jargon, Emphasis Crutches (Banned Adverbs), Implementation, Integration Points, Meta-Commentary, References, Stop-Slop Quality Skill (+2 more)

### Community 662 - "Agency Core — Ruthless Architecture Audit & Migration Plan"
Cohesion: 0.18
Nodes (10): Acceptance check, Agency Core — Ruthless Architecture Audit & Migration Plan, Root causes (not symptoms), Section 1 — The Brutal Truth, Section 2 — Keep / Salvage / Replace / Remove, Section 3 — The Chosen Foundation, Section 4 — The New Agency Core, Section 5 — Migration Plan (minimal chaos, all on PR, CI green at each step) (+2 more)

### Community 663 - "AUTONOMY_CHARTER.md"
Cohesion: 0.18
Nodes (6): How to add or change a loop, LOOP.md — The loops that run this agency, Maturity ladder, The five building blocks (and how this repo realises them), The three operator tools (`agent/loop_registry.py`), Why this exists

### Community 664 - "Tailored Onboarding, Editable Companies & Dynamic Roles"
Cohesion: 0.18
Nodes (10): 1. Editable companies, anytime (not a one-shot wizard), 2. Question-driven provisioning — no cosmetic questions, 3. Dynamic, expandable roles (open registry, not a closed enum), 4. Agents start pre-powered, Invariants, Phases, Tailored Onboarding, Editable Companies & Dynamic Roles, The gaps to close (+2 more)

### Community 665 - "Issue #467 — Section 1: Pulled State + PR Inventory"
Cohesion: 0.18
Nodes (10): 1. Current Git State, 2. Open PRs (as of 2026-06-08), 3. Files Modified on consolidate/maturation-stable (vs master), 4. What Master Has (that consolidate doesn't), 5. What Is MISSING from master (0% delivered in #467), 6. Required Action Before Code, Branch: `consolidate/maturation-stable`, Issue #467 — Section 1: Pulled State + PR Inventory (+2 more)

### Community 666 - "Autonomy Charter — Telegram-Gated Self-Running Agency"
Cohesion: 0.18
Nodes (11): 1. Mission & operating principles, 2. Brain policy (free cloud LLMs), 3. The Gate Matrix (core artifact), 4. Telegram gate protocol, 6. Integration gaps to wire (follow-up implementation), 7. Definition of "fully autonomous" — acceptance criteria, 8. Safety invariants (carried from `agent/CLAUDE.md`), 🟢 Autonomous — run, then notify-only (+3 more)

### Community 667 - "Context: Agentic Agile + Portfolio Management"
Cohesion: 0.18
Nodes (10): Agile improvements shipped alongside, Autonomous intelligence (`agents/portfolio_intelligence.py`), Capacity & roadmap, Context: Agentic Agile + Portfolio Management, Extension ideas (not yet built), Prioritisation model — WSJF (SAFe), Problem, The two layers (+2 more)

### Community 668 - "Deploy to Google Cloud Run"
Cohesion: 0.18
Nodes (10): 1) Admin protection (required), 2) User API keys (required), 3) LLM provider (recommended), Build + deploy (Dockerfile), Deploy to Google Cloud Run, Notes / limitations on Cloud Run, Prereqs, Required configuration (+2 more)

### Community 669 - "Key Components"
Cohesion: 0.18
Nodes (10): 1. Input Embedding, 2. Multi-Head Self-Attention, 3. Residual Connections, 4. Feed-Forward Network (FFN), 5. Layer Normalization, Decoder-Only vs Encoder-Decoder, High-Level Structure, Key Components (+2 more)

### Community 670 - "Sampling Strategies Internals"
Cohesion: 0.18
Nodes (11): Beam Search, Greedy Decoding, Logit Processors (Structured Output), Min-p Sampling, Repetition Penalty, Sampling Strategies Internals, Temperature Sampling, The Output Distribution (+3 more)

### Community 671 - "LLM Router — architecture"
Cohesion: 0.18
Nodes (11): Bulkheads, Circuit breaker, Compatibility, Configuration, Context management, LLM Router — architecture, Modules, Request lifecycle (+3 more)

### Community 672 - "Killer TODO Roadmap — local-llm-server"
Cohesion: 0.18
Nodes (10): G1 — Per-Model Cost and Latency Attribution [P1] [NVD], G2 — Request Replay for Debugging [P2] [CBF], H1 — Vision Input Support for Multimodal Models [P2] [NVD], H2 — Audio Input / Whisper Transcription [P3] [NVD], Implementation Notes, Killer TODO Roadmap — local-llm-server, Priority Summary, SECTION G — Observability (NVD / CHM) (+2 more)

### Community 673 - "CI Troubleshooting Runbook"
Cohesion: 0.18
Nodes (10): A test hangs in CI but passes locally, All three CI jobs fail with "git exit code 128" in Post Checkout, CI Troubleshooting Runbook, CodeQL action version, Frontend tests fail in parallel / async timer leaks, GitHub Actions YAML block scalar — bash heredoc content at column 0, Python 3.13 compatibility status, Python test job fails — "Process completed with exit code 1", no .pytest_cache found (+2 more)

### Community 674 - "NVIDIA NIM — Free Tier Setup"
Cohesion: 0.18
Nodes (10): 1. Get your free API key, 2. Set the environment variable, 3. Restart the server, 4. Verify, How the kill switch protects you, NVIDIA NIM — Free Tier Setup, Related, Setup (5 minutes) (+2 more)

### Community 675 - "What to clean up"
Cohesion: 0.18
Nodes (10): 1. Render (production backend + worker), 2. Cloudflare Worker (frontend), 3. Local development machines, 4. GitHub secrets, 5. MongoDB collections, Post-Merge Environment Cleanup Guide, Post-merge verification checklist, Rollback (+2 more)

### Community 676 - "Worker Service — Operations Runbook"
Cohesion: 0.18
Nodes (10): Architecture, Deployment on Render, Environment variables, First-time setup, Graceful shutdown, Local development, Overview, Troubleshooting (+2 more)

### Community 677 - "test_bedrock_live.py"
Cohesion: 0.25
Nodes (10): _NEEDS_CREDS, asyncio, ProviderRouter discovers Bedrock from env and completes a real chat call., Health check returns True when real credentials are loaded from env., Call Bedrock Converse API directly with boto3 — no proxy layer., Verify the configured model ID accepts a converse request without auth errors., test_bedrock_direct_boto3_ping(), test_bedrock_health_check_with_real_creds() (+2 more)

### Community 678 - "provider_max_rpm"
Cohesion: 0.29
Nodes (10): provider_max_rpm(), Return the operator-configured requests/min cap for *provider*, or None if…, tests/test_provider_max_rpm.py — packages/ai/brain_config.provider_max_rpm().…, inf previously parsed successfully and passed a bare `> 0` check, producing a…, test_infinite_and_nan_return_none(), test_non_numeric_returns_none(), test_provider_id_uppercased_for_lookup(), test_unset_returns_none() (+2 more)

### Community 679 - "._order_group"
Cohesion: 0.27
Nodes (7): provider_id_of(), Any, Extract a provider id from a ProviderConfig dataclass or a plain dict., Return *providers* reordered according to the active strategy. ``group_key``…, Reorder one interchangeable group of providers., Ascending sort by *score* with a random tie-break. The tie-break is the point:…, Weighted random permutation — heavier providers tend to come first. Weight…

### Community 680 - "verify_service_token"
Cohesion: 0.25
Nodes (10): _get_hashed_token(), _hash_token(), Request, services/service_token.py — Backend service-token authentication. Roadmap item…, Constant-time verification of a provided service token. Returns True when: -…, FastAPI dependency: reject unauthenticated or non-admin callers. Use as::…, SHA-256 hash the plaintext token. We compare hashes (not plaintext) so the in-…, Return the hashed service token, or None if SERVICE_TOKEN is unset. Caches the… (+2 more)

### Community 681 - "run_proxy.sh"
Cohesion: 0.18
Nodes (10): AIDER_BASE_URL, GOOSE_BASE_URL, HERMES_BASE_URL, LOG_LEVEL, OLLAMA_BASE, OPENCODE_BASE_URL, PROXY_PORT, RATE_LIMIT_RPM (+2 more)

### Community 682 - "Security Policy"
Cohesion: 0.18
Nodes (11): Authentication, Authorization, How to Report, Known Security Trade-offs, Reporting a Vulnerability, Response Timeline, Scope, Security Design (+3 more)

### Community 683 - "setup_ngrok.py"
Cohesion: 0.31
Nodes (10): _api(), authenticate_ngrok(), _find_ngrok(), get_or_create_static_domain(), main(), Return path to the ngrok binary (pyngrok location or PATH)., Update or append KEY=value in .env., rewrite_tunnel_scripts() (+2 more)

### Community 684 - "test_empirical_verify.py"
Cohesion: 0.49
Nodes (10): _make_runner(), MonkeyPatch, Path, Tests for AgentRunner._empirical_verify (opt-in executable validation gate)., test_empirical_verify_disabled_by_default(), test_empirical_verify_flags_compile_failure(), test_empirical_verify_passes_clean_module_without_tests(), test_empirical_verify_runs_matching_tests_and_passes() (+2 more)

### Community 685 - "test_event_log.py"
Cohesion: 0.45
Nodes (10): Path, _store(), test_append_event_payload_roundtrips(), test_append_event_positions_are_monotonic(), test_append_event_stores_and_increments_count(), test_events_are_isolated_per_session(), test_events_survive_store_restart(), test_get_events_empty_session() (+2 more)

### Community 686 - "test_google_provider_models.py"
Cohesion: 0.18
Nodes (7): The Google provider must only advertise models its endpoint actually serves.…, A role must never be assigned a model the picker does not list., An operator override of GEMINI_MODEL must appear in the picker. The catalog is…, The Doctor probe must target the path Gemini actually serves., test_configured_gemini_model_is_always_selectable(), test_google_role_models_are_offered_by_the_catalog(), test_liveness_probe_resolves_gemini_openai_compat_base()

### Community 687 - "test_tasks_awaiting_approval_api.py"
Cohesion: 0.40
Nodes (10): _client(), asyncio, Task, TestClient, GET /api/tasks/awaiting-approval — dashboard surface for the pre-execution…, _seed(), test_admin_sees_system_owned_gated_tasks(), test_approving_removes_task_from_awaiting_list() (+2 more)

### Community 688 - "admin_gui.py"
Cohesion: 0.24
Nodes (8): Browser admin UI for login, service control, key management, and diagnostics., Update or append a KEY=value line in the .env file., register_admin_gui(), _save_env_var(), get_output_filter(), Get or create the singleton OutputFilter instance., get_cooldown_state(), Return a snapshot of active cooldowns {provider_id: expiry_unix_timestamp}.

### Community 689 - "Instructions"
Cohesion: 0.20
Nodes (9): Acceptance Checks, Instructions, Skill: insights, Step 1 — File change heatmap (which files change most), Step 2 — Failure pattern analysis, Step 3 — Retry analysis, Step 4 — Learnings frequency analysis, Step 5 — Produce a summary report (+1 more)

### Community 690 - "Protocol: Premium Utilitarian Minimalism UI Architect"
Cohesion: 0.20
Nodes (9): 1. Protocol Overview, 2. Absolute Negative Constraints (Banned Elements), 3. Typographic Architecture, 4. Color Palette (Warm Monochrome + Spot Pastels), 5. Component Specifications, 6. Iconography & Imagery Directives, 7. Subtle Motion & Micro-Animations, 8. Execution Protocol (+1 more)

### Community 691 - "The 5-Step Wrap-Up Ritual"
Cohesion: 0.20
Nodes (9): Acceptance Checks, Skill: wrap-up, Step 1 — Changes Audit, Step 2 — Quality Check, Step 3 — Learning Capture, Step 4 — Next Session Planning, Step 5 — One-Paragraph Summary, The 5-Step Wrap-Up Ritual (+1 more)

### Community 692 - "CLAUDE.md — Master Architect Operating Manual"
Cohesion: 0.20
Nodes (10): 0. The Golden Rule, 12. Changelog Rule, 13. Autonomous Development Policy, 2. Architectural Principles, 9. Coding Rules, Before writing any code, Before you read any source file: query graphify, CLAUDE.md — Master Architect Operating Manual (+2 more)

### Community 693 - "Agent: Reviewer (Verifier)"
Cohesion: 0.20
Nodes (10): Activation, Agent: Reviewer (Verifier), Blocking Conditions (must return `fail`), Handoff, Key Invariant, Non-Blocking (may return `pass` with suggestions), Output Format, Preferred Model (+2 more)

### Community 694 - "Skill: Agentic Agile"
Cohesion: 0.20
Nodes (9): Autonomous ceremonies (`agents/agile_ceremonies.py`), Key Classes, Purpose, Related, Retrospective & health, Scheduled workflow, Skill: Agentic Agile, Testing (+1 more)

### Community 695 - "Skill: browserbase-ui-test — Adversarial UI Testing"
Cohesion: 0.20
Nodes (9): Applying to local-llm-server platform, Core philosophy, Execution pattern, Reporting, Round 1 — Core flow mapping, Round 2 — Adversarial scenarios, Round 3 — Accessibility + mobile, Skill: browserbase-ui-test — Adversarial UI Testing (+1 more)

### Community 696 - "Skill: financial-analyst (Agentic CFO)"
Cohesion: 0.20
Nodes (9): Branch, Components, Decision Rules, Purpose, Quick Start, Skill: financial-analyst (Agentic CFO), SKILL.md refresh Tue Jun  2 11:35:52 CEST 2026, Testing (+1 more)

### Community 697 - "Graphiti Temporal Context Skill"
Cohesion: 0.20
Nodes (9): 1. Agent Memory as Temporal Graph, 2. Multi-Agent Coordination, 3. Knowledge Queries, Database Schema, Files to Create, Graphiti Temporal Context Skill, Integration Opportunities, References (+1 more)

### Community 698 - "Skill: seo-audit-report"
Cohesion: 0.20
Nodes (9): How This Skill Works (Agent Instructions), Output Files, Parameters, Purpose, Quick Start, Revenue-at-Risk Disclaimer (load-bearing — always include in reports), Skill: seo-audit-report, Troubleshooting (+1 more)

### Community 699 - "ADR-008: LLMRouter — the single multi-provider routing gateway"
Cohesion: 0.20
Nodes (10): ADR-008: LLMRouter — the single multi-provider routing gateway, Comparison with OmniRoute, Consequences, Context, Differences — why a port was rejected, Incompatible components (explicitly rejected), References, Reusable components (ideas adopted) (+2 more)

### Community 700 - "Agent Readiness Report"
Cohesion: 0.20
Nodes (9): Agent Readiness Report, Build System — 100/100, Dev Environment — 100/100, Documentation — 100/100, Observability — 100/100, Security — 100/100, Style And Validation — 100/100, Task Discovery — 100/100 (+1 more)

### Community 701 - "Core Pillars"
Cohesion: 0.20
Nodes (9): 1. Unified Intent Orchestration, 2. Deep Sticky Memory, 3. Execution Cognition Flow, 4. Progress Humanization, Core Pillars, Direct Chat Evolution: Seamless Assistant Architecture, Failure Recovery, Overview (+1 more)

### Community 702 - "467 Golden Path — Locked Implementation Order"
Cohesion: 0.20
Nodes (10): 467 Golden Path — Locked Implementation Order, Agent Code (agent/ directory), Backend Code (backend/, handlers/), Golden Path Exceptions, Module-Specific Golden Paths, Skill Code (.agents/skills/), Verification, What Breaks the Golden Path (+2 more)

### Community 703 - "LLM Router — configuration guide"
Cohesion: 0.20
Nodes (10): Budgets, cache.yaml, Environment variables, health.yaml, keys.yaml, LLM Router — configuration guide, models.yaml, Per-agent policies (+2 more)

### Community 704 - "LLM Router — provider guide"
Cohesion: 0.20
Nodes (9): Adding any OpenAI-compatible provider, Auth styles, Cheap tiers, Cloud providers, Free tiers, LLM Router — provider guide, Multiple keys, Premium (+1 more)

### Community 705 - "LoopsScreen.jsx"
Cohesion: 0.24
Nodes (8): getLoops(), COST_COLOR, fmtTokens(), GATE_META, GRADE_COLOR, LEVEL_META, LoopsScreen(), ReadinessHeader()

### Community 706 - "_fake_fetch_module"
Cohesion: 0.36
Nodes (9): extract_real_url(), fetch(), main(), meaningful(), Drop site navigation chrome and repeated nav blocks from stripped text. A fetch…, strip_boilerplate(), strip_html(), _fake_fetch_module() (+1 more)

### Community 707 - "OutputFilter"
Cohesion: 0.20
Nodes (7): _count_remaining(), _filter_generic(), OutputFilter, Token-optimizing output filter for command stdout. Usage:: from output_filter…, Filter *stdout* from *command* for token efficiency. If FILTER_ENABLED is…, Generic compression for unrecognized commands., _truncate()

### Community 709 - "TestModelsEndpointAliases"
Cohesion: 0.31
Nodes (4): _get_model_map(), Merge built-in defaults with MODEL_MAP env overrides (lazy, cached)., Tests that /v1/models exposes Claude/Anthropic alias entries., TestModelsEndpointAliases

### Community 710 - "build_tech_db.py"
Cohesion: 0.40
Nodes (9): _as_list(), _clean(), convert(), _default_source(), _has_pattern(), main(), Any, Strip Wappalyzer's `\\;tag:...` metadata, leaving a plain regex. (+1 more)

### Community 711 - "main"
Cohesion: 0.29
Nodes (9): _detect_crlf(), _enumerate_matching_lines(), _eprint(), main(), Path, CRLF present if any line ends in CRLF., Yield (line_bytes, line_index) for every line in `data` containing `needle`., Pick the .env to migrate. See module docstring for resolution order. (+1 more)

### Community 712 - "run_bot"
Cohesion: 0.27
Nodes (9): _configure(), _default(), main(), Set an env var only when the operator hasn't already provided one., Call a Telegram Bot API method and return the parsed JSON (best-effort)., run_bot(), _tg_call(), TELEGRAM_POLLER_DISABLED=true makes run_bot() idle WITHOUT long-polling… (+1 more)

### Community 713 - "_start_ceo_agency"
Cohesion: 0.27
Nodes (9): Start the 24×7 CEO agency loop that *proactively* generates work. Without this…, _start_ceo_agency(), fixture, tests/test_ceo_agency_startup.py — the CEO loop must actually be started. Root…, A failure constructing/starting the CEO must not crash app startup., _reset_agency_singleton(), test_ceo_agency_can_be_disabled(), test_ceo_agency_starts_by_default() (+1 more)

### Community 714 - "Dream"
Cohesion: 0.22
Nodes (6): Dream, Return the most recent dreams, newest first., A consolidated dream built from multiple session memories., Return a brief summary of the dream., Tests for Dream dataclass., TestDream

### Community 715 - "test_bootstrap_source_id_index.py"
Cohesion: 0.27
Nodes (9): asyncio, tests/test_bootstrap_source_id_index.py — _ensure_tasks_source_id_unique_index.…, A unique-index build against a collection with pre-existing duplicate source_id…, The proactive dedup pass must run before the index-build attempt, so a first-…, If the proactive dedup pass itself fails (e.g. store not wired up yet), the…, test_dedup_failure_does_not_block_index_attempt(), test_dedup_pass_runs_before_index_build(), test_index_build_failure_does_not_raise() (+1 more)

### Community 716 - "TestExtendedThinkingRouting"
Cohesion: 0.20
Nodes (6): Unit tests for extended thinking detection in handle_anthropic_messages., When thinking.type == enabled, routing should use agent_plan endpoint type., No thinking param → normal chat routing, not forced to reasoning., thinking_budget_tokens should appear in routing_meta when thinking is set., Without thinking param, thinking_budget_tokens not in routing_meta., TestExtendedThinkingRouting

### Community 717 - "TestZeroAttemptDiagnostics"
Cohesion: 0.29
Nodes (4): A zero-attempt exhaustion must say WHICH of the three causes it is. Nothing…, An operator whose switches reset on deploy needs to know that here., A broken registry must not turn a failed call into a crash., TestZeroAttemptDiagnostics

### Community 718 - "TestSessionMemory"
Cohesion: 0.20
Nodes (3): Tests for services/managed_agents.py — Managed Agents Dreams. Uses importlib to…, Tests for SessionMemory dataclass., TestSessionMemory

### Community 719 - "test_provider_state_durability.py"
Cohesion: 0.20
Nodes (6): _live_mongo_url(), Operator provider state must survive a redeploy. The per-provider kill switch…, Return a reachable MONGO_URL, or None so the test skips., Both halves matter, and the second one is easy to drop. Redirecting…, test_conftest_isolates_operator_state_for_every_test(), TestDurabilitySignal

### Community 720 - "test_quick_note_engine.py"
Cohesion: 0.22
Nodes (7): _before(), Guard that the quick-note engine agents use NVIDIA NIM as the primary engine…, implement_agent.py uses NVIDIA NIM exclusively — the Anthropic/Opus fallback…, Regression: _run_baseline_pytest() ran the FULL suite (no path filter,…, test_baseline_pytest_timeout_is_generous_and_failure_is_caught(), test_implement_agent_nvidia_primary(), test_review_agent_nvidia_primary()

### Community 723 - "synthesize"
Cohesion: 0.36
Nodes (9): _convert_to_ogg(), voice/tts.py — Text-to-Speech for the CEO voice pipeline. Converts text to an…, Convert audio to OGG Opus (Telegram voice note format) via pydub+ffmpeg., Convert text to OGG voice note bytes. Returns None on failure., _select_backend(), synthesize(), _synthesize_elevenlabs(), _synthesize_gtts() (+1 more)

### Community 725 - "_extract_workflow_relevance"
Cohesion: 0.33
Nodes (4): _extract_workflow_relevance(), Return workflow types mentioned in the skill content., Tests for _extract_workflow_relevance()., TestExtractWorkflowRelevance

### Community 726 - "Coding Standards"
Cohesion: 0.22
Nodes (9): 1. Language & Runtime, 2. Async, 3. Data Models, 4. Logging, 5. Error Handling, 6. Security, 7. Comments, 8. File Size (+1 more)

### Community 727 - "Skill: changelog-enforcer"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Changelog Location, Entry Format, Examples, Hook Behaviour, Instructions, Skill: changelog-enforcer, When to Use

### Community 728 - "Skill: learn-rule"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Instructions, Learnings File Format, Skill: learn-rule, Step 1 — Identify the rule, Step 2 — Append to learnings file, Step 3 — Check if CLAUDE.md should be updated, When to Use

### Community 729 - "Instructions"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Instructions, Skill: session-handoff, Step 1 — Capture current state, Step 2 — Write the handoff document, Step 3 — Update machine-readable state, Step 4 — Confirm the handoff is self-contained, When to Use

### Community 730 - "prompts/README.md"
Cohesion: 0.22
Nodes (4): Command: /resume, References, Usage, What It Does

### Community 731 - "Skill: Agentic Portfolio Management"
Cohesion: 0.22
Nodes (8): Key Classes, Purpose, Related, Skill actions (via SkillBindings), Skill: Agentic Portfolio Management, Testing, Usage, WSJF

### Community 732 - "Skill: changelog-enforcer"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Changelog Location, Entry Format, Examples, Hook Behaviour, Instructions, Skill: changelog-enforcer, When to Use

### Community 733 - "Skill: cowork-session (Claude Cowork)"
Cohesion: 0.22
Nodes (8): Branch, Components, Purpose, Quick Start, Session Roles, Skill: cowork-session (Claude Cowork), Testing, When to Use

### Community 734 - "Skill: video-context — read a video without watching it"
Cohesion: 0.22
Nodes (8): How It Works, Limits — know these before relying on it, Skill: video-context — read a video without watching it, Testing, Usage, What To Do With The Transcript, When To Use This, Why This Exists

### Community 735 - "Decision"
Cohesion: 0.22
Nodes (9): 1. `LLMRouter` is the only gateway, 2. Providers are data, not code, 3. Secrets stay in the environment, 4. Three independent failure scopes, 5. Bulkhead isolation, 6. Context is managed losslessly, 7. Configuration is six committed YAML files, 8. Backwards compatibility by shim, not by rewrite (+1 more)

### Community 736 - "ADR 003: Multi-Agent Orchestration with Plan-Execute-Verify Loop"
Cohesion: 0.22
Nodes (8): ADR 003: Multi-Agent Orchestration with Plan-Execute-Verify Loop, Alternatives Considered, Consequences, Context, Decision, Negative, Neutral, Positive

### Community 737 - "Main proxy (`proxy.py`)"
Cohesion: 0.22
Nodes (9): Agent and workflow surfaces, API Surfaces and Route Map, Built-in admin and web UI, Control-plane style routers mounted in the proxy, Main proxy (`proxy.py`), Ollama-compatible, OpenAI-compatible, Separate hosted dashboard backend (`backend/server.py`) (+1 more)

### Community 738 - "Autonomous SDLC Loop (Agency Core, repo-agnostic)"
Cohesion: 0.22
Nodes (9): Autonomous SDLC Loop (Agency Core, repo-agnostic), Companies without a connected repo (URL-only onboarding), Design principle: repo-agnostic, not GitHub-Actions-bound, Detect & respect each repo's delivery policy, Integrations & intake sources (honest tiers), Reuse map (what already exists), Safety invariants (carry over from `agent/CLAUDE.md`), The gap this closes (+1 more)

### Community 739 - "The 8-Step Golden Path"
Cohesion: 0.22
Nodes (9): Step 1: Scout — Understand the territory, Step 2: Plan — Define the change, Step 3: Write tests first, Step 4: Implement, Step 5: Validate, Step 6: Review, Step 7: Document, Step 8: Commit and propose (+1 more)

### Community 740 - "PR #634 Implementation Tracker"
Cohesion: 0.22
Nodes (8): Phase 1 — Stop the bleeding + paid kill switch ✅, Phase 2 — Per-surface assignment in the UI 🔄, Phase 3 — Persistence hardening (#537, #524) ⏳, Phase 4 — Onboarding fixes (#593, #619, PR #623) ⏳, Phase 5 — Reliability (#522) ⏳, Phase 6 — Green tests + housekeeping ⏳, PR #634 Implementation Tracker, Verification checklist (final)

### Community 741 - "KV Cache Internals"
Cohesion: 0.22
Nodes (9): KV Cache Internals, KV Cache with Grouped Query Attention, Memory Layout, Paged Attention (vLLM), Prefill vs Decode Phase, Quantization of KV Cache, Speculative Decoding, The Problem: Redundant Computation (+1 more)

### Community 742 - "Release Procedure"
Cohesion: 0.22
Nodes (8): Changelog Update, Commit and Tag, Post-Release Checklist, Pre-Flight, Release Procedure, Rollback, Verify CI, Version Bump

### Community 743 - "V2.0 Modernization — Runbook"
Cohesion: 0.22
Nodes (8): Adding a new provider adapter, CI, Importing new code, Module map (old → new), Removing the shims (future cleanup), Rollback, Test migration, V2.0 Modernization — Runbook

### Community 744 - "Setup"
Cohesion: 0.22
Nodes (8): 1. Get LiveKit credentials, 2. Configure the backend (Render env vars), 3. The SAM voice worker, 4. Talk to SAM, Architecture, SAM Realtime Voice over LiveKit, Setup, Troubleshooting

### Community 745 - "check_feature"
Cohesion: 0.28
Nodes (9): check_feature(), get_feature(), list_features(), Any, get, post, Return the full support matrix with summary., Return a single feature entry. (+1 more)

### Community 746 - "frontend/package.json"
Cohesion: 0.22
Nodes (8): jest, moduleNameMapper, ^react-router$, ^react-router-dom$, name, private, proxy, version

### Community 747 - "AgentStatusPanel.tsx"
Cohesion: 0.25
Nodes (7): AgentStatus, AgentStatusPanelProps, AgentCard(), formatRelative(), ROLE_ICONS, STATUS_DOTS, STATUS_STYLES

### Community 748 - "AgentStatusPanel.jsx"
Cohesion: 0.25
Nodes (6): AgentCard(), formatRelative(), ROLE_ICONS, STATUS_DOTS, STATUS_STYLES, PHASE_LABELS

### Community 749 - "ToolCallViewer.tsx"
Cohesion: 0.25
Nodes (7): ToolCall, ToolCallViewerProps, getToolIcon(), STATUS_BADGES, STATUS_STYLES, TOOL_ICONS, ToolCallRow()

### Community 750 - "cleanup_stale_jobs"
Cohesion: 0.31
Nodes (8): cleanup_stale_jobs(), _is_stale(), Any, packages/scheduler/cleanup.py — schedule deduplication + stale removal.…, Remove a job from the store. Returns True on success, False on failure. Logs…, Check if a created_at timestamp is older than ttl_seconds. Handles multiple…, Remove stale run-once + stuck agency jobs from the durable store. Args: store:…, _safe_remove()

### Community 751 - "enrich_quick_note_issues.py"
Cohesion: 0.42
Nodes (8): _dispatch_generation(), _fetch_open_issues(), _has_context(), _headers(), _is_quick_note(), main(), Ask the bulk context workflow to generate documents for these issues., True when a context branch already exists for this issue. Checked against…

### Community 752 - "_status_snapshot"
Cohesion: 0.31
Nodes (9): cmd_wait(), Block until download completes + colibri answers /v1/models., _status_snapshot(), await_ready(), colibri_model_id(), colibri_url(), _list_models_payload(), Normalise an OAI ``/v1/models`` response into a list of model ids. (+1 more)

### Community 753 - "incr_window"
Cohesion: 0.31
Nodes (4): incr_window(), Increment a rate-limit counter. Returns the current count within the window., TestInMemoryIncrWindow, TestRedisIncrWindow

### Community 754 - "e2e/conftest.py"
Cohesion: 0.28
Nodes (8): base_url(), mobile_page(), proxy_url(), Config, fixture, pytest_configure(), conftest.py — pytest fixtures and configuration for the E2E test suite.…, A browser page pre-configured for mobile viewport (390×844 — iPhone 14).

### Community 755 - "admin_jwt"
Cohesion: 0.25
Nodes (9): auth_headers(), client(), fixture, TestClient, TestClient for the backend FastAPI app (one per module for speed)., Login once and return auth headers for the entire module., admin_jwt(), fixture (+1 more)

### Community 757 - "test_backend_requirements_cover_runtime_imports.py"
Cohesion: 0.25
Nodes (8): _declared_packages(), parametrize, Path, Guard against the recurring "works in CI, missing in prod" dependency drift.…, Return the normalised distribution names declared in *requirements*., If the Dockerfile ever installs the root file, this guard can relax. Until then…, test_backend_requirements_declares_runtime_package(), test_dockerfile_still_installs_backend_requirements_only()

### Community 758 - "test_changelog_parity_guard.py"
Cohesion: 0.22
Nodes (3): tests/test_changelog_parity_guard.py — corruption guard for the changelog gate.…, A 7-equals line under a title (Markdown setext H1) must not false-positive., test_setext_heading_underline_is_not_flagged()

### Community 760 - "fixture"
Cohesion: 0.25
Nodes (5): fixture, Test agent auto-assignment in task creation, GET /api/agents/ should return list of agents, Task with specific task_type should match agents with that type, TestAgentAutoAssignment

### Community 761 - "TestChatFallbackAndApproval"
Cohesion: 0.22
Nodes (5): Test chat fallback behavior with commercial provider approval, Get authentication token for admin user, POST /api/chat/send endpoint should exist and accept requests, Verify ChatMessage model accepts allow_commercial_fallback_once field, TestChatFallbackAndApproval

### Community 762 - "test_ping.py"
Cohesion: 0.33
Nodes (8): client(), fixture, TestClient, Tests for the /api/ping health endpoint (no auth required)., test_ping_no_auth_required(), test_ping_response_shape(), test_ping_returns_ok(), test_ping_timestamp_is_iso()

### Community 763 - "FakeScheduleCollection"
Cohesion: 0.25
Nodes (3): FakeDeleteResult, FakeScheduleCollection, Minimal async MongoDB-like collection for testing nuclear_cleanup.

### Community 764 - "TestMongoGate"
Cohesion: 0.22
Nodes (3): Tests must never mutate a shared operational store., The storage layer's localhost default is a placeholder, not config. Treating it…, TestMongoGate

### Community 765 - "TestPaidPolicyDurability"
Cohesion: 0.22
Nodes (3): This is the document the UI toggle writes via _set_provider_policy., Never enable paid spend by accident., TestPaidPolicyDurability

### Community 766 - "test_runtimes_health_endpoint.py"
Cohesion: 0.22
Nodes (8): hermes_only_manager(), fixture, tests/test_runtimes_health_endpoint.py — N2 acceptance: GET /runtimes/health…, Build a RuntimeManager with only internal_agent + Hermes registered. Mirrors…, GET /runtimes/health must include a `hermes` entry when the adapter is…, End-to-end (router level): GET /runtimes/health returns JSON with a `health`…, test_runtimes_health_endpoint_returns_hermes_via_testclient(), test_runtimes_health_includes_hermes_entry()

### Community 767 - "test_scanner_deps_parity.py"
Cohesion: 0.31
Nodes (8): _declared_packages(), Guard against the CI-vs-production dependency drift that made gucci.com (and…, Top-level module names imported anywhere in services/scanner.py., Every third-party package the scanner imports must be in the file the…, Belt-and-suspenders: the two deps whose absence caused the gucci.com production…, _scanner_imports(), test_critical_scanner_deps_explicitly_present(), test_scanner_third_party_deps_declared_in_backend_requirements()

### Community 768 - "test_task_store_fails_loud_in_production.py"
Cohesion: 0.22
Nodes (8): fresh_store_module(), fixture, Regression: prevent silent TaskStore in-memory fallback in production. The…, Force a fresh import of tasks.store so module-level state is clean., With TESTING unset (production), TaskStore(db=None) MUST raise., With TESTING=true (CI), TaskStore(db=None) MUST allow in-memory fallback., test_task_store_allows_inmemory_when_testing(), test_task_store_raises_in_production()

### Community 769 - "stt.py"
Cohesion: 0.36
Nodes (8): voice/stt.py — Speech-to-Text for the CEO voice pipeline. Transcribes audio…, Transcribe audio bytes to text. Returns empty string on failure., Fallback: Google Web Speech API via SpeechRecognition library., _select_backend(), transcribe(), _transcribe_google(), _transcribe_local(), _transcribe_openai()

### Community 770 - "navigation_metrics.py"
Cohesion: 0.32
Nodes (4): get_navigation_metrics(), NavigationMetrics, navigation_metrics.py — Navigation/usage metrics collection for agent sessions., record_content_visible()

### Community 771 - "_score_turns"
Cohesion: 0.36
Nodes (8): Score each turn by exponential recency decay combined with query relevance.…, _score_turns(), test_score_turns_empty(), test_score_turns_importance_multiplier(), test_score_turns_recency_newer_scores_higher(), test_score_turns_relevance_boosts_score(), test_score_turns_sorted_descending(), _turn()

### Community 772 - "._run_git_command"
Cohesion: 0.25
Nodes (4): Build git intelligence: hotspots, ownership, co-change pairs., Run a git command and return stdout as string., Compute cyclomatic complexity for Python files. Returns 0 for non-Python files…, Extract architectural decisions from git history and inline comments.

### Community 773 - "TrajectoryStep"
Cohesion: 0.25
Nodes (5): Any, Agent trajectory recorder – captures every step an agent takes so runs can be…, A single action/observation pair in an agent trajectory., Append a step and return it., TrajectoryStep

### Community 774 - "quality_checker.py"
Cohesion: 0.32
Nodes (6): AITellType, Enum, str, Quality checker inspired by stop-slop (https://github.com/hardikpandya/stop-…, Categories of AI tells, Tests for quality checker (stop-slop inspired)

### Community 775 - "Skill: docs-sync"
Cohesion: 0.25
Nodes (7): Acceptance Checks, ADR Guidelines, AGENTS.md Update Rules, Docs to Check After Each Change Type, Instructions, Skill: docs-sync, When to Use

### Community 776 - "get_catalog"
Cohesion: 0.25
Nodes (8): get_catalog_models_route(), Return the mirrored model catalog (advisory-only). Flag-gated by…, get_catalog(), get_model_catalog_store(), Return the process-wide ModelCatalogStore singleton., Convenience wrapper used by the GET /api/catalog/models endpoint., Convenience wrapper used by the POST sync endpoint + background loop., sync_catalog()

### Community 777 - "Agent: Implementer (Executor)"
Cohesion: 0.25
Nodes (8): Activation, Agent: Implementer (Executor), Constraints, Handoff, Preferred Model, Responsibilities, Role, Shared State

### Community 778 - "Agent: Judge (Release / QA Gate)"
Cohesion: 0.25
Nodes (7): Activation, Agent: Judge (Release / QA Gate), Enforcement, Output, Responsibilities, Role, Verdict Meanings

### Community 779 - "Agent: Planner (Architect)"
Cohesion: 0.25
Nodes (8): Activation, Agent: Planner (Architect), Failure Behaviour, Handoff, Output Format, Preferred Model, Responsibilities, Role

### Community 780 - "Skill: browserbase-browser — Real Browser Automation"
Cohesion: 0.25
Nodes (7): Applying to local-llm-server platform, Core commands, Mode selection, Setup, Skill: browserbase-browser — Real Browser Automation, Troubleshooting, Workflow pattern

### Community 781 - "Skill: docs-sync"
Cohesion: 0.25
Nodes (7): Acceptance Checks, ADR Guidelines, CLAUDE.md Update Rules, Docs to Check After Each Change Type, Instructions, Skill: docs-sync, When to Use

### Community 782 - "Skill: memory-consolidation (Dream Memory)"
Cohesion: 0.25
Nodes (7): Branch, Consolidation Lifecycle, Memory Kinds, Purpose, Quick Start, Skill: memory-consolidation (Dream Memory), Testing

### Community 783 - "GitHub Branch Protection Settings"
Cohesion: 0.25
Nodes (7): Branch name pattern: `main` (or `master`), CODEOWNERS Setup, Enabling via GitHub CLI, GitHub Branch Protection Settings, Purpose, Required Settings, Why This Can't Be Fully Repo-Enforced

### Community 784 - "ADR 001: Self-Hosted OpenAI-Compatible Proxy"
Cohesion: 0.25
Nodes (7): ADR 001: Self-Hosted OpenAI-Compatible Proxy, Consequences, Context, Decision, Negative, Neutral, Positive

### Community 785 - "ADR 002: Dynamic Model Routing with Task Classification"
Cohesion: 0.25
Nodes (7): ADR 002: Dynamic Model Routing with Task Classification, Consequences, Context, Decision, Negative, Neutral, Positive

### Community 786 - "Agent Autonomy Roadmap"
Cohesion: 0.25
Nodes (8): Agent Autonomy Roadmap, Design constraints honored, New environment variables, Proactive rate-limit pacing (free-tier reliability), The eight gaps and what closed them, Verification performed, What was already strong (verified, no changes needed), Why this document exists

### Community 787 - "AGENTS.md — AI Agent Configuration for local-llm-server"
Cohesion: 0.25
Nodes (7): Agent Roles, AGENTS.md — AI Agent Configuration for local-llm-server, Operating Instructions, Quick Start for Agents, Risky Paths — Require Extra Care, State Files, Workspace Purpose

### Community 788 - "Advisor Strategy — Local Proxy Handling"
Cohesion: 0.25
Nodes (7): Advisor Strategy — Local Proxy Handling, How This Proxy Handles Advisor Requests, Incoming message history (advisor blocks), Local Equivalent: The Planner Role, Outgoing requests (tools array), Using the Real Advisor Strategy via This Proxy, What the Anthropic Advisor Strategy Is

### Community 789 - "ceo-micromanagement.md"
Cohesion: 0.25
Nodes (4): P0 behavior change, Readiness contract, Runtime model, Runtime types

### Community 790 - "Feature Maturity / Support Matrix"
Cohesion: 0.25
Nodes (8): Beta, Config Overrides, Disabled (demoted per issue #467 Section I), Enforcement, Experimental, Feature Maturity / Support Matrix, Maturity Tiers, Stable Core

### Community 791 - "Web UI + Admin (Claude Code–style)"
Cohesion: 0.25
Nodes (7): Acceptance checks, Approach, Files to change, Files to read first, Goal, Risks, Web UI + Admin (Claude Code–style)

### Community 792 - "467 Skill Inventory — load / wire / test status"
Cohesion: 0.25
Nodes (7): 467 Skill Inventory — load / wire / test status, Agent Specialties (not skills per se, but referenced in spec §B), Core Agency Skills (load/wire/test), Gaps Summary, Named Skills Referenced in Spec §C, Skill Registry, Test Coverage Summary

### Community 793 - "Free NVIDIA brain + UI-controlled provider policy + no silent spend"
Cohesion: 0.25
Nodes (8): Decisions (locked with the owner), Design: one UI-controlled Provider Policy (single source of truth), Free NVIDIA brain + UI-controlled provider policy + no silent spend, Open-PR / issue disposition (read + acted on), Root cause of the $20 burn (verified in-repo), SELF-CONTAINED AGENT PROMPT (paste to run cold), Verification / acceptance, Why this PR exists (context)

### Community 794 - "Issue #362: Nvidia repo setup"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #362: Nvidia repo setup, Implementation Prompt, Issue #362: Nvidia repo setup, Relevant Files to Read First, Risk Flags, TODO List

### Community 795 - "Issue #364: quick-note:https://www.marktechpost.com/2026/06/01/meet-memory-os-a-6-layer-open-source-memory-stack-built-on-top-of-hermes-agent/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #364: quick-note:https://www.marktechpost.com/2026/06/01/meet-memory-os-a-6-layer-open-source-memory-stack-built-on-top-of-hermes-agent/, Implementation Prompt, Issue #364: quick-note:https://www.marktechpost.com/2026/06/01/meet-memory-os-a-6-layer-open-source-memory-stack-built-on-top-of-hermes-agent/, Relevant Files to Read First, Risk Flags, TODO List

### Community 796 - "Issue #378: quick-note:https://www.marktechpost.com/2026/06/02/tinyfish-launches-bigset-an-open-source-multi-agent-system-that-builds-structured-live-datasets-from-plain-english-descriptions/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #378: quick-note:https://www.marktechpost.com/2026/06/02/tinyfish-launches-bigset-an-open-source-multi-agent-system-that-builds-structured-live-datasets-from-plain-english-descriptions/, Implementation Prompt, Issue #378: quick-note:https://www.marktechpost.com/2026/06/02/tinyfish-launches-bigset-an-open-source-multi-agent-system-that-builds-structured-live-datasets-from-plain-english-descriptions/, Relevant Files to Read First, Risk Flags, TODO List

### Community 797 - "Issue #379: quick-note:https://searchengineland.com/schema-markup-optimize-agentic-web-479080"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #379: quick-note:https://searchengineland.com/schema-markup-optimize-agentic-web-479080, Implementation Prompt, Issue #379: quick-note:https://searchengineland.com/schema-markup-optimize-agentic-web-479080, Relevant Files to Read First, Risk Flags, TODO List

### Community 798 - "Issue #380: quick-note:https://cursor.com/blog/cloud-agent-lessons"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #380: quick-note:https://cursor.com/blog/cloud-agent-lessons, Implementation Prompt, Issue #380: quick-note:https://cursor.com/blog/cloud-agent-lessons, Relevant Files to Read First, Risk Flags, TODO List

### Community 799 - "Issue #381: quick-note:https://www.xda-developers.com/claude-code-with-opus-48-is-expensive-but-i-made-it-efficient-with-my-local-ai-workflow/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #381: quick-note:https://www.xda-developers.com/claude-code-with-opus-48-is-expensive-but-i-made-it-efficient-with-my-local-ai-workflow/, Implementation Prompt, Issue #381: quick-note:https://www.xda-developers.com/claude-code-with-opus-48-is-expensive-but-i-made-it-efficient-with-my-local-ai-workflow/, Relevant Files to Read First, Risk Flags, TODO List

### Community 800 - "Issue #382: quick-note:https://claude.com/blog/how-coderabbit-used-claude-to-build-an-agent-orchestration-system"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #382: quick-note:https://claude.com/blog/how-coderabbit-used-claude-to-build-an-agent-orchestration-system, Implementation Prompt, Issue #382: quick-note:https://claude.com/blog/how-coderabbit-used-claude-to-build-an-agent-orchestration-system, Relevant Files to Read First, Risk Flags, TODO List

### Community 801 - "Issue #383: quick-note:https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #383: quick-note:https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/, Implementation Prompt, Issue #383: quick-note:https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/, Relevant Files to Read First, Risk Flags, TODO List

### Community 802 - "Issue #416: feat: Self-hosted Codebuff (freebuff) on free NVIDIA models + Telegram bot phone control"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #416: feat: Self-hosted Codebuff (freebuff) on free NVIDIA models + Telegram bot phone control, Implementation Prompt, Issue #416: feat: Self-hosted Codebuff (freebuff) on free NVIDIA models + Telegram bot phone control, Relevant Files to Read First, Risk Flags, TODO List

### Community 803 - "Issue #485: [Trend Digest] Week of 2026-06-08"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #485: [Trend Digest] Week of 2026-06-08, Implementation Prompt, Issue #485: [Trend Digest] Week of 2026-06-08, Relevant Files to Read First, Risk Flags, TODO List

### Community 804 - "Issue #488: quick-note:https://github.com/cookiy-ai/user-research-skill"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #488: quick-note:https://github.com/cookiy-ai/user-research-skill, Implementation Prompt, Issue #488: quick-note:https://github.com/cookiy-ai/user-research-skill, Relevant Files to Read First, Risk Flags, TODO List

### Community 805 - "Issue #491: Implement whatever is necessary from https://github.com/BehiSecc/awesome-claude-skills"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #491: Implement whatever is necessary from https://github.com/BehiSecc/awesome-claude-skills, Implementation Prompt, Issue #491: Implement whatever is necessary from https://github.com/BehiSecc/awesome-claude-skills, Relevant Files to Read First, Risk Flags, TODO List

### Community 806 - "Issue #493: Use the https://github.com/mvanhorn/last30days-skill skill to get the trend updated"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #493: Use the https://github.com/mvanhorn/last30days-skill skill to get the trend updated, Implementation Prompt, Issue #493: Use the https://github.com/mvanhorn/last30days-skill skill to get the trend updated, Relevant Files to Read First, Risk Flags, TODO List

### Community 807 - "Issue #495: Read https://www.anthropic.com/news/claude-fable-5-mythos-5 and understand if mythos or fable can be added to the repo"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #495: Read https://www.anthropic.com/news/claude-fable-5-mythos-5 and understand if mythos or fable can be added to the repo, Implementation Prompt, Issue #495: Read https://www.anthropic.com/news/claude-fable-5-mythos-5 and understand if mythos or fable can be added to the repo, Relevant Files to Read First, Risk Flags, TODO List

### Community 808 - "Issue #504: EPIC: Autonomy hardening — live-verified defects 2026-06-10"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #504: EPIC: Autonomy hardening — live-verified defects 2026-06-10, Implementation Prompt, Issue #504: EPIC: Autonomy hardening — live-verified defects 2026-06-10, Relevant Files to Read First, Risk Flags, TODO List

### Community 809 - "Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass, Implementation Prompt, Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass, Relevant Files to Read First, Risk Flags, TODO List

### Community 810 - "Issue #656: Bugs"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #656: Bugs, Implementation Prompt, Issue #656: Bugs, Relevant Files to Read First, Risk Flags, TODO List

### Community 811 - "Issue #657: quick-note:https://github.com/earendil-works/pi"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #657: quick-note:https://github.com/earendil-works/pi, Implementation Prompt, Issue #657: quick-note:https://github.com/earendil-works/pi, Relevant Files to Read First, Risk Flags, TODO List

### Community 812 - "Issue #659: quick-note:https://github.com/nex-agi/Nex-N2"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #659: quick-note:https://github.com/nex-agi/Nex-N2, Implementation Prompt, Issue #659: quick-note:https://github.com/nex-agi/Nex-N2, Relevant Files to Read First, Risk Flags, TODO List

### Community 813 - "Issue #660: quick-note:https://github.com/getsentry/sentry-for-ai"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #660: quick-note:https://github.com/getsentry/sentry-for-ai, Implementation Prompt, Issue #660: quick-note:https://github.com/getsentry/sentry-for-ai, Relevant Files to Read First, Risk Flags, TODO List

### Community 814 - "Issue #661: quick-note:https://github.com/XiaomiMiMo/MiMo-Code"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #661: quick-note:https://github.com/XiaomiMiMo/MiMo-Code, Implementation Prompt, Issue #661: quick-note:https://github.com/XiaomiMiMo/MiMo-Code, Relevant Files to Read First, Risk Flags, TODO List

### Community 815 - "Issue #664: quick-note:https://github.com/Grominet95/jarvis-OS"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #664: quick-note:https://github.com/Grominet95/jarvis-OS, Implementation Prompt, Issue #664: quick-note:https://github.com/Grominet95/jarvis-OS, Relevant Files to Read First, Risk Flags, TODO List

### Community 816 - "Issue #666: quick-note:https://github.com/porokka/jarvis-os"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #666: quick-note:https://github.com/porokka/jarvis-os, Implementation Prompt, Issue #666: quick-note:https://github.com/porokka/jarvis-os, Relevant Files to Read First, Risk Flags, TODO List

### Community 817 - "Issue #670: quick-note:https://github.com/perplexityai/bumblebee"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #670: quick-note:https://github.com/perplexityai/bumblebee, Implementation Prompt, Issue #670: quick-note:https://github.com/perplexityai/bumblebee, Relevant Files to Read First, Risk Flags, TODO List

### Community 818 - "Issue #672: quick-note:https://github.com/Chachamaru127/claude-code-harness"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #672: quick-note:https://github.com/Chachamaru127/claude-code-harness, Implementation Prompt, Issue #672: quick-note:https://github.com/Chachamaru127/claude-code-harness, Relevant Files to Read First, Risk Flags, TODO List

### Community 819 - "Issue #676: quick-note:https://github.com/WeiboAI/VibeThinker"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #676: quick-note:https://github.com/WeiboAI/VibeThinker, Implementation Prompt, Issue #676: quick-note:https://github.com/WeiboAI/VibeThinker, Relevant Files to Read First, Risk Flags, TODO List

### Community 820 - "Issue #820: quick-note:https://github.com/cobusgreyling/loop-engineering"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #820: quick-note:https://github.com/cobusgreyling/loop-engineering, Implementation Prompt, Issue #820: quick-note:https://github.com/cobusgreyling/loop-engineering, Relevant Files to Read First, Risk Flags, TODO List

### Community 821 - "Positional Encoding Internals"
Cohesion: 0.25
Nodes (7): ALiBi (Attention with Linear Biases), Comparison, Learned Positional Embeddings, Positional Encoding Internals, RoPE Scaling for Long Contexts, Rotary Positional Embedding (RoPE), Sinusoidal Positional Encoding (Original Transformer)

### Community 822 - "Setup"
Cohesion: 0.25
Nodes (8): 1. Clone and install, 2. Configure, 3. Start the backend, 4. Start the frontend (development), 5. Onboard your first company, 6. Connect your AI coding tools (optional), Setup, What you need

### Community 823 - "TOP 6 — Highest-ROI Items (Validated by Opus Research Agent)"
Cohesion: 0.25
Nodes (8): ★1 — 3-Phase Context-Pruner Middleware [P0] [CBF], ★2 — Specialized Sub-Agents with Per-Role Cheap Models [P0] [CBF + HRM], ★3 — Reasoning Token Budget + Toggle [P0] [NVD], ★4 — Skill/Procedural Memory (agentskills.io compatible) [P1] [HRM], ★5 — Sandboxed Agent Execution (E2B / Docker micro-VM) [P1] [CHM] ✅ Delivered 2026-07-04, ★6 — Cost Analytics + FTS5 Shared Memory + Agent Constitution [P1] [AOS], ★7 — Adaptive Loop Halting (Early Exit on High Confidence) [P1] [MYT + HRM], TOP 6 — Highest-ROI Items (Validated by Opus Research Agent)

### Community 824 - "SECTION A — Agent Efficiency (Hermes / AOS / MYT)"
Cohesion: 0.25
Nodes (8): A1 — Hermes ChatML Prompt Format for Tool Calling [P0] [HRM], A2 — Multi-Hop Reasoning Chain (ReAct / Tree-of-Thought) [P0] [HRM], A3 — Agent Capability Registry + Dynamic Tool Discovery [P1] [AOS], A4 — Async Task Queue with Priority and Backpressure [P1] [AOS], A5 — Inter-Agent Message Bus [P1] [AOS / MYT], A6 — Shared Blackboard Memory for Swarm Agents [P1] [MYT], A7 — Agent Self-Improvement Loop [P2] [HRM / AOS], SECTION A — Agent Efficiency (Hermes / AOS / MYT)

### Community 825 - "SECTION C — Direct Chat Improvements (CBF / HRM)"
Cohesion: 0.25
Nodes (8): C1 — Structured Output / JSON Mode [P0] [CBF / HRM], C2 — Function Calling / Tool Use (OpenAI-Compatible) [P0] [CBF / HRM], C3 — Streaming with Proper Delta Reconstruction [P1] [CBF], C4 — Chat History Persistence + Retrieval [P1] [AOS / HRM], C5 — Context Window Management + Smart Truncation [P1] [CBF / HRM], C6 — Prompt Caching (Anthropic-Compatible) [P1] [HRM], C7 — Embeddings Pipeline + Vector Search [P2] [AOS / CBF], SECTION C — Direct Chat Improvements (CBF / HRM)

### Community 826 - "Runbook — Instance Activation"
Cohesion: 0.25
Nodes (7): Option A — disable the gate (self-hosted), Option B — self-mint a signed code with your own key, Option C — request a code (downstream user), Runbook — Instance Activation, Security notes, TL;DR — you are blocked at the activation screen, Why activation exists

### Community 827 - "PULL_REQUEST_TEMPLATE.md"
Cohesion: 0.25
Nodes (7): Changelog, Changes, Council Review (for larger PRs), Related, Risky Module Review, Summary, Testing

### Community 828 - "_get_current_user"
Cohesion: 0.29
Nodes (8): _get_bearer_token(), _get_current_user(), logout(), Depends, Extract and validate current user from token., Get current authenticated user., Logout (token invalidation happens on frontend by clearing localStorage)., Extract bearer token from Authorization header.

### Community 829 - "bus.py"
Cohesion: 0.32
Nodes (7): Event, publish(), packages/events/bus.py — In-process event bus. Loosely couples components via…, An event published on the bus., Subscribe to an event type., Publish an event to all subscribers., subscribe()

### Community 830 - "capture_screens.py"
Cohesion: 0.39
Nodes (7): Popen, _capture(), _login(), main(), Launch the local uvicorn server (activated, sqlite, loops off) for capture., _start_server(), _wait_up()

### Community 831 - "Prompt Library"
Cohesion: 0.25
Nodes (8): Agents, Commands, How This Library Is Maintained, Philosophy, Prompt Library, Skills, Transparency, What Is This?

### Community 832 - "CLAUDE.md — router/"
Cohesion: 0.25
Nodes (7): Adding a New Model, Adding a New Task Category, CLAUDE.md — router/, Environment Variables, Invariants — Do Not Break, Testing, What This Package Does

### Community 833 - "crispy_burn_in.py"
Cohesion: 0.36
Nodes (7): evaluate_burn_in(), fetch_status_json(), main(), Any, scripts/crispy_burn_in.py — Evaluate CRISPY burn-in criteria for promotion.…, Fetch /api/autonomy/status and return the parsed JSON., Evaluate the burn-in criteria against a ``crispy_run_history`` payload. Returns…

### Community 834 - "run_patched_colibri.py"
Cohesion: 0.36
Nodes (7): _exit_watch_delay(), main(), _patched_popen(), scripts/run_patched_colibri.py Pre-launch wrapper for JustVugg/colibri…, Resolve the COLIBRI_PATCH_EXIT_WATCH delay in seconds, clamped to [0, 60].…, Intercept JustVugg Engine -> glm.exe Popen and forward outer argv. Upstream…, _resolve_target()

### Community 835 - "SessionMemory"
Cohesion: 0.25
Nodes (5): Any, Managed Agents Dreams — session memory and dream consolidation for managed…, An individual memory snapshot from an agent session., Record a new session memory for this agent., SessionMemory

### Community 838 - "test_compose_and_coordinate_api.py"
Cohesion: 0.36
Nodes (5): _auth_override(), AuthContext, test_coordinate_dependency_aware_tasks_block_missing_dependencies(), test_coordinate_dependency_aware_tasks_succeed_with_dependencies(), test_coordinate_legacy_workers_flow_remains_backward_compatible()

### Community 839 - "test_doctor_coding_brain.py"
Cohesion: 0.32
Nodes (7): client(), _coding_brain_check(), fixture, tests/test_doctor_coding_brain.py Surfaces the North Mini Code coding-brain…, With NORTH_MINI_CODE_DEFAULT off, the check warns and says so., test_coding_brain_check_reflects_flag_off(), test_doctor_includes_coding_brain_check()

### Community 842 - "TestProviderRouter"
Cohesion: 0.25
Nodes (4): Test provider router behavior, GET /api/providers should return list of configured providers, GET /runtimes/policy should return current routing policy, TestProviderRouter

### Community 843 - "test_local_brain_router_smoke.py"
Cohesion: 0.25
Nodes (7): Smoke test: backend/local_brain_router is mounted on the public FastAPI app.…, Importing backend.server.app must not raise AttributeError or NameError., The /api/local-brain/state GET route must be reachable via the FastAPI app.…, The local_brain_router symbol MUST be importable + prefixed correctly. Quick…, test_backend_server_app_loads_without_attributeerror(), test_local_brain_router_module_is_wired(), test_local_brain_state_route_is_mounted_on_public_app()

### Community 845 - "test_provider_models_db_outage.py"
Cohesion: 0.25
Nodes (7): tests/test_provider_models_db_outage.py — GET /api/providers/{id}/models…, A DB exception during the provider lookup must not surface as a 500., A catalog provider (unified BrainConfig) with no legacy `providers` row must…, A provider_id absent from both Mongo and the predefined catalog is a genuine…, test_provider_models_falls_back_on_db_outage(), test_provider_models_truly_unknown_provider_still_404s(), test_provider_models_unregistered_provider_uses_predefined_catalog()

### Community 846 - "_FakeDb"
Cohesion: 0.25
Nodes (5): fake_mongo(), _FakeDb, isolated_state(), fixture, Temp SQLite mirror + clean caches, so no test sees another's state.

### Community 848 - "test_serve_spa_prefixes.py"
Cohesion: 0.36
Nodes (7): _prefixes(), Behavioral: GET to a path that has NO upstream handler but IS in the protected…, SPA_PROTECTED_PREFIXES must be exposed at module scope (not inside an if-block)…, test_legitimate_spa_paths_are_not_blocked(), test_protected_paths_are_covered_by_prefix_tuple(), test_serve_spa_returns_non_html_for_protected_orphan_path(), test_spa_protected_prefixes_is_module_level_constant()

### Community 849 - "dry_clone_repo"
Cohesion: 0.36
Nodes (5): test_dry_clone_repo_handles_missing_url(), test_dry_clone_repo_handles_subprocess_failure(), dry_clone_repo(), Validate repository access by performing a shallow, no-checkout git clone and…, Attempt a shallow, non-checkout clone into a temporary directory to validate…

### Community 850 - "TOOLS.md — Available Tools for AI Agents"
Cohesion: 0.25
Nodes (7): AI Runner Tools, API Endpoints (when proxy is running), File Tools, OpenClaw Integration, Shell / Process Tools, Skills (invoke via CLAUDE.md instructions), TOOLS.md — Available Tools for AI Agents

### Community 851 - ".assess"
Cohesion: 0.38
Nodes (4): PermissionAssessment, Any, Convenience helper — True when the inferred level is read_write or full_access., Analyse *messages* and return a :class:`PermissionAssessment`.

### Community 852 - "_keyword_search"
Cohesion: 0.29
Nodes (7): _keyword_search(), Score documents by query-term coverage with a title-match boost., test_keyword_search_empty_query(), test_keyword_search_finds_relevant(), test_keyword_search_no_match(), test_keyword_search_respects_k(), test_keyword_search_title_boost()

### Community 854 - "Full-Output Enforcement"
Cohesion: 0.29
Nodes (6): Banned Output Patterns, Baseline, Execution Process, Full-Output Enforcement, Handling Long Outputs, Quick Check

### Community 855 - "summarise.sh"
Cohesion: 0.48
Nodes (5): bottom(), divider(), row(), summarise.sh script, top()

### Community 856 - "updater.py"
Cohesion: 0.43
Nodes (6): _extract_unreleased_body(), _insert(), main(), Insert the Maintenance changelog section at the end of the [Unreleased] block.…, Return (body_start, body_end_exclusive, body) for the [Unreleased] block., _read_template()

### Community 857 - "_build_direct_chat_schedule_suggestion"
Cohesion: 0.33
Nodes (7): _build_direct_chat_schedule_suggestion(), _build_direct_chat_tags(), _build_direct_chat_task_suggestion(), _derive_work_item_title(), _infer_schedule_cron(), _infer_task_priority(), _looks_like_recurring_automation()

### Community 858 - "get_harness_registry"
Cohesion: 0.29
Nodes (6): harness_session_close(), harness_session_start(), Register a new harness session (called by the orchestrator on execute)., Close a harness session and aggregate its metrics., get_harness_registry(), tests/test_harness_adapter.py — Tests for ECC cross-harness adapter.

### Community 859 - "_load_local_metrics_since"
Cohesion: 0.43
Nodes (7): _load_local_metrics_since(), observability_savings(), observability_usage(), _period_cutoff(), datetime, Load local_metrics docs since cutoff. Works with both MongoDB and SQLite., _to_dt()

### Community 860 - "ModelRegistry"
Cohesion: 0.29
Nodes (4): ModelRegistry, A centralized registry for available LLM models and their metadata. This class…, Returns a list of all registered models metadata., Retrieves a specific model's metadata by its name (case-insensitive). Returns…

### Community 861 - "4. Current Architecture (As-Is)"
Cohesion: 0.29
Nodes (7): 4. Current Architecture (As-Is), Bill of Materials, Codebase Map, Current folder structure (problematic), Deployment topology, External providers, Secrets inventory

### Community 862 - "AI Engineering Insights Skill"
Cohesion: 0.29
Nodes (6): AI Engineering Insights Skill, Integration Points, Key Design Choices, Module: `agents/ai_insights.py`, References, What's Unique About the DX Report

### Community 863 - "Skill: hybrid-reasoning (Hybrid AI)"
Cohesion: 0.29
Nodes (6): Branch, Components, Purpose, Quick Start, Skill: hybrid-reasoning (Hybrid AI), Testing

### Community 864 - "Karpathy Guidelines Skill"
Cohesion: 0.29
Nodes (6): 1. Think Before Coding, 2. Simplicity First, 3. Surgical Changes, 4. Goal-Driven Execution, Integration points in this repo, Karpathy Guidelines Skill

### Community 865 - "Skill: Managed Agents Dreams"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: Managed Agents Dreams, Testing, Usage

### Community 866 - "Skill: Multi-Agent Coordinator"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: Multi-Agent Coordinator, Testing, Usage

### Community 867 - "Skill: Obsidian Knowledge Graph"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: Obsidian Knowledge Graph, Testing, Usage

### Community 868 - "Multi-Agent Research Coordinator Skill"
Cohesion: 0.29
Nodes (6): Default Plan Shape, Module: `agents/research_coordinator.py`, Multi-Agent Research Coordinator Skill, Quick-Note Issue: #238, Roles, What's Unique

### Community 869 - "Skill: SuperClaude Slash Commands"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: SuperClaude Slash Commands, Testing, Usage

### Community 870 - "Skill: SuperClaude Workflow Engine"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: SuperClaude Workflow Engine, Testing, Usage

### Community 871 - "Active Task Tracker"
Cohesion: 0.29
Nodes (6): Active Task Tracker, Bug Log, Current Sprint Tasks, Roadmap Items (from `docs/roadmap-killer-todos.md`), Session Log, Status Key

### Community 872 - "ADR-006: Strangler Fig migration with backward-compat shims"
Cohesion: 0.29
Nodes (6): ADR-006: Strangler Fig migration with backward-compat shims, Consequences, Context, Decision, Examples, Migration path

### Community 873 - "claude-mem Plugin — Persistent Memory for All Sessions"
Cohesion: 0.29
Nodes (6): claude-mem Plugin — Persistent Memory for All Sessions, Enabling it elsewhere, How it's wired, Notes, Scope and limits, Why the source is pinned (`ref` + `sha`)

### Community 874 - "Implementation plan + TO-DO (check off as you go)"
Cohesion: 0.29
Nodes (7): Implementation plan + TO-DO (check off as you go), Phase 1 — Stop the bleeding + paid kill switch (do first, ship alone if needed), Phase 2 — Per-surface assignment in the UI (the "one place"), Phase 3 — Persistence hardening (issues #537, #524), Phase 4 — Onboarding fixes (issues #593, #619; PR #623), Phase 5 — Reliability for hands-off autonomy (issue #522) [larger; may split to own PR], Phase 6 — Green the tests + housekeeping

### Community 875 - "Topics Covered"
Cohesion: 0.29
Nodes (7): 1. Architecture, 2. Tokenization, 3. Training, 4. Inference, 5. Embeddings, LLM Internals, Topics Covered

### Community 876 - "LLM Router — migration guide"
Cohesion: 0.29
Nodes (7): Adding the config files, Gateway mode, LLM Router — migration guide, Migrating a caller to the router directly, Rollback checklist, What changes for callers, What is not migrated

### Community 877 - "What's New"
Cohesion: 0.29
Nodes (7): 2026-06-16, 2026-06-25, 2026-06-26, 2026-07-04, 2026-07-05, 2026-07-09, What's New

### Community 878 - "Cloudflare = the real working app"
Cohesion: 0.29
Nodes (6): Backend (Render), Cloudflare dashboard settings to verify, Cloudflare = the real working app, How it works, Notes, Verify after deploy

### Community 879 - "production"
Cohesion: 0.29
Nodes (7): browserslist, development, production, >0.2%, last 1 chrome version, not dead, not op_mini all

### Community 880 - "launch-claude-code.sh"
Cohesion: 0.43
Nodes (6): ANTHROPIC_API_KEY, ANTHROPIC_MODEL, log_error(), log_header(), log_success(), launch-claude-code.sh script

### Community 882 - "PRD — README Marketing Refresh"
Cohesion: 0.29
Nodes (6): Backlog / Nice-to-Have, Files Touched, Original Problem Statement, PRD — README Marketing Refresh, User Decisions, What Was Done — 2026-04-27

### Community 883 - "Any"
Cohesion: 0.29
Nodes (4): Any, Actively wake every sleeping/circuit-open runtime. The default health service…, Return the active routing policy as a plain dict., Update the routing policy in-place.

### Community 884 - "check_changelog_parity.py"
Cohesion: 0.43
Nodes (6): _blocks(), main(), normalize_text(), scripts/check_changelog_parity.py CI guard for the changelog mirror. Closes the…, Return a list of human-readable corruption issues in *content*. Detects (1) git…, scan_corruption()

### Community 885 - "e2e_smoke.py"
Cohesion: 0.57
Nodes (5): _chat(), check(), _health(), _models(), _req()

### Community 886 - "BackgroundServices"
Cohesion: 0.38
Nodes (4): BackgroundServices, Handle returned by ``start_background_services`` — call ``stop()`` on shutdown., Cancel the boot refresh if it is still fetching at shutdown., Shut the in-process Hermes down so port 8100 is released. Uvicorn's own…

### Community 887 - "_reset_backend"
Cohesion: 0.33
Nodes (7): Reset the singleton (for tests)., _reset_backend(), fixture, Configure the shared_state module to use fakeredis for the test., Reset the shared-state singleton before every test., _redis_backend(), _reset_state()

### Community 888 - "task_runner.py"
Cohesion: 0.33
Nodes (6): check_health(), Submit a task to the agent planner., Submit a simple task via the tasks API., Check if the proxy is running., submit_simple_task(), submit_task()

### Community 890 - "test_daily_2026_06_14.py"
Cohesion: 0.38
Nodes (6): Regression tests for daily-2026-06-14 improvements. Anthropic retires the…, ci-failure-autofix.yml must call the Anthropic API with claude-sonnet-4-6, as…, No GitHub Actions workflow or CI script should reference a retired Claude 4…, _read(), test_ci_autofix_workflow_uses_sonnet_4_6(), test_no_retired_claude_4_model_ids_in_workflows_or_scripts()

### Community 891 - "TestSupportMatrixDocsSync"
Cohesion: 0.29
Nodes (4): The feature matrix can produce a markdown table for docs., Every config flag referenced in the matrix should be documented., The matrix should cover the key areas from the spec., TestSupportMatrixDocsSync

### Community 893 - "TestGithubTokenSQLiteRegression"
Cohesion: 0.38
Nodes (4): MonkeyPatch, TestClient, Regression test for PUT/DELETE /api/github/token returning 500 for SQLite-…, TestGithubTokenSQLiteRegression

### Community 894 - "sam"
Cohesion: 0.29
Nodes (7): agent/sam.py must call emit_agency_observation for voice commands., test_sam_py_traces_voice_commands(), fixture, Fresh SAM agent with mocked dependencies., SAM agent with all external dependencies mocked., sam(), sam_with_mocks()

### Community 895 - "test_log_monitor_storm_guard.py"
Cohesion: 0.48
Nodes (6): _fresh_monitor(), Tests for the LogMonitor self-heal storm guard. A system that is already…, test_cap_zero_disables_cap(), test_hourly_cap_suppresses_storm(), test_operational_errors_are_skipped(), test_real_code_error_creates_a_task()

### Community 898 - "TestActiveStrategy"
Cohesion: 0.29
Nodes (3): parametrize, A typo must not silently pick some other distribution., TestActiveStrategy

### Community 900 - "_tokenize"
Cohesion: 0.33
Nodes (6): Return lowercase alphanumeric tokens with stop-words removed. Numeric tokens…, _tokenize(), test_tokenize_empty(), test_tokenize_lowercases(), test_tokenize_numbers_kept(), test_tokenize_removes_stop_words()

### Community 901 - "._get_last_commit"
Cohesion: 0.33
Nodes (3): Get the latest commit hash., Get the last commit hash we processed., Check if we need to update intelligence based on new commits.

### Community 902 - "_brain_provider_status"
Cohesion: 0.33
Nodes (6): _brain_provider_status(), get_brain_policy_route(), Return per-provider metadata for the GET endpoint. Iterates every provider in…, Return the discovered model list for *provider_id*, or ``[]`` if unknown., Return the active brain config + per-provider key-present flags. The response…, _served_models()

### Community 903 - "sam_chat_backend"
Cohesion: 0.33
Nodes (6): _get_backend_sam(), Lazy-init the SAM agent for the backend deployment., Get SAM's current status., Send a voice command to SAM and get a spoken response., sam_chat_backend(), sam_status_backend()

### Community 904 - "openclaw_mobile_ui"
Cohesion: 0.33
Nodes (5): openclaw_mobile_ui(), Mobile web UI for iOS control of the agency. Open this on your iPhone, tap…, get_mobile_html(), services/openclaw_mobile.py — Mobile web UI for iOS control of the agency.…, Return the mobile web UI HTML.

### Community 905 - "_wfo_owned_run_or_404"
Cohesion: 0.33
Nodes (6): Fetch a run, enforcing per-user ownership (admins bypass). Returns 404 — not…, Approve a run paused at the ApprovalGate and resume execution., Get a single workflow orchestrator run by ID (owner or admin only)., _wfo_owned_run_or_404(), workflow_orchestrator_approve(), workflow_orchestrator_get_run()

### Community 906 - "/fix-bug — Bug Fix Agent"
Cohesion: 0.33
Nodes (5): Escalation, /fix-bug — Bug Fix Agent, Process, Rules, Usage

### Community 907 - "Command: /plan"
Cohesion: 0.33
Nodes (5): Command: /plan, References, Usage, What It Does, When to Use

### Community 908 - "pre-commit"
Cohesion: 0.60
Nodes (5): pre-commit script, _error(), _head(), _info(), _warn()

### Community 909 - "Skill: browserbase-fetch — Lightweight Web Fetch"
Cohesion: 0.33
Nodes (5): Checking the platform health, Python snippet, Setup, Skill: browserbase-fetch — Lightweight Web Fetch, When to use vs browser

### Community 910 - "Twitter Insights — Issue #228"
Cohesion: 0.33
Nodes (5): Action Items, Key Observations, References, Summary, Twitter Insights — Issue #228

### Community 911 - "Twitter Insights — Issue #231"
Cohesion: 0.33
Nodes (5): Action Items, Key Observations, References, Summary, Twitter Insights — Issue #231

### Community 912 - "OpenAI Codex CLI — Local LLM Server Config"
Cohesion: 0.33
Nodes (5): Codex Config File (`~/.codex/config.yaml`), Notes, OpenAI Codex CLI — Local LLM Server Config, Recommended Models, Setup

### Community 913 - "ADR-001: Adopt packages/ directory structure"
Cohesion: 0.33
Nodes (5): ADR-001: Adopt packages/ directory structure, Consequences, Context, Decision, Status

### Community 914 - "ADR-002: Centralize configuration in packages/config/"
Cohesion: 0.33
Nodes (5): ADR-002: Centralize configuration in packages/config/, Consequences, Context, Decision, Status

### Community 915 - "ADR-003: Provider abstraction with unified interface"
Cohesion: 0.33
Nodes (5): ADR-003: Provider abstraction with unified interface, Consequences, Context, Decision, Status

### Community 916 - "ADR-004: Event bus for loosely coupled communication"
Cohesion: 0.33
Nodes (5): ADR-004: Event bus for loosely coupled communication, Consequences, Context, Decision, Status

### Community 917 - "ADR-005: Merge Hermes into the main backend service"
Cohesion: 0.33
Nodes (5): ADR-005: Merge Hermes into the main backend service, Consequences, Context, Decision, Status

### Community 918 - "ADR-007: Storage backend duck-typing over formal ABC"
Cohesion: 0.33
Nodes (5): ADR-007: Storage backend duck-typing over formal ABC, Consequences, Context, Decision, Rationale

### Community 919 - "Phases"
Cohesion: 0.33
Nodes (6): Phase 0 — `RepoConnection` plumbing + delivery-policy detection, Phase 1 — Plan-PR → Implementation  *(highest leverage; closes the live gap)*, Phase 2 — Review-comment resolution (Codex / CodeRabbit), Phase 3 — Quality gate + policy-conformant landing, Phase 4 — Monitor & regression guard, Phases

### Community 920 - "5. The five autonomous loops"
Cohesion: 0.33
Nodes (6): 5. The five autonomous loops, Loop 1 — Self-heal from logs *(closed loop)*, Loop 2 — Feature generation, Loop 3 — Agentic SDLC (the golden path), Loop 4 — Trends contextually applied, Loop 5 — Per-onboarded-site autonomy

### Community 921 - "Master Goal Prompt — Autonomous Agency CEO"
Cohesion: 0.33
Nodes (6): Cadence & stop conditions, First-run bootstrap, Hard constraints, Master Goal Prompt — Autonomous Agency CEO, Mission, The gate contract (Telegram human-in-the-loop)

### Community 922 - "Agency Core — Operational Knowledge (verified live, 2026-06-10/11)"
Cohesion: 0.33
Nodes (5): Agency Core — Operational Knowledge (verified live, 2026-06-10/11), Architecture truths, Open backlog (epic #504), Pros of linking the GitHub repo (vs running unlinked), Runbooks

### Community 923 - "The full agent capability roster"
Cohesion: 0.33
Nodes (6): Agile, portfolio & product, Business & domain specialists (auto-provisioned from the URL scan), Content & knowledge, Engineering, Operations & DevOps, The full agent capability roster

### Community 924 - "Pre-Mortem Analysis: Agency Core autonomy story (Cloudflare deployment)"
Cohesion: 0.33
Nodes (5): Elephants, named, Pre-Mortem Analysis: Agency Core autonomy story (Cloudflare deployment), Risk Registry, Summary, What was already fixed during this pre-mortem

### Community 925 - "SECTION B — NVIDIA / Cloud Model Integration (Nemotron / NVD)"
Cohesion: 0.33
Nodes (6): B1 — Nemotron Reward Model for Agent Step Scoring [P0] [NVD], B2 — SteerLM / RLHF-Style Steering for Local Models [P1] [NVD], B3 — Synthetic Training Data Generation Pipeline [P1] [NVD], B4 — NeMo Guardrails Integration [P1] [NVD], B5 — NIM API Connection Pooling + Circuit Breaker [P1] [NVD], SECTION B — NVIDIA / Cloud Model Integration (Nemotron / NVD)

### Community 926 - "SECTION D — Deployment & Infrastructure (CHM / NVD)"
Cohesion: 0.33
Nodes (6): D1 — Helm Chart for Kubernetes Deployment [P1] [CHM], D2 — Docker Compose Production Stack [P1] [CHM], D3 — OpenTelemetry Distributed Tracing [P1] [NVD / CHM], D4 — Horizontal Scaling with Redis State Backend [P2] [CHM / AOS], D5 — Model Auto-Management (Pull, Warm, Evict) [P2] [NVD], SECTION D — Deployment & Infrastructure (CHM / NVD)

### Community 927 - "Feature Support Matrix"
Cohesion: 0.33
Nodes (6): Admin API, Config Overrides, Feature Matrix, Feature Support Matrix, Gating Behavior, Maturity Tiers

### Community 929 - "resolve_hermes_base_url"
Cohesion: 0.47
Nodes (5): Resolve the base URL of the agency's own Hermes server. Precedence:…, resolve_hermes_base_url(), tests/test_hermes_base_url.py — resolve_hermes_base_url precedence., test_default_when_unset(), test_env_wins()

### Community 930 - "reset"
Cohesion: 0.33
Nodes (5): Clear pool state (tests only)., reset(), _clean_pool(), fixture, Rotation is off by default; these tests exercise the enabled path.

### Community 931 - ".execute"
Cohesion: 0.60
Nodes (3): TaskResult, TaskSpec, Execute via OpenCode CLI: `opencode run --json <instruction>`.

### Community 932 - "apply_phase1_changes.py"
Cohesion: 0.33
Nodes (5): apply_backend_change(), apply_workflow_change(), Apply Phase 1 paid-provider kill switch changes to backend/server.py and…, Insert provider policy endpoints before @app.get('/api/models/catalog')., Modify _resolve_brain_provider to read allow_paid from the durable policy.

### Community 933 - "_replace"
Cohesion: 0.40
Nodes (5): main(), Path, Regex-replace ``pattern`` with ``repl`` in ``path``; return the match count., Bump the version across all version-bearing files; fail fast if any are missed., _replace()

### Community 934 - "check_doc_images.py"
Cohesion: 0.60
Nodes (5): check_broken_links(), check_gallery_sync(), find_duplicate_images(), _local_refs(), main()

### Community 935 - "gen_screenshots.py"
Cohesion: 0.53
Nodes (5): main(), out_path(), Path, Generate Langfuse and Telegram mockup screenshots for documentation., save_html_screenshot()

### Community 936 - "gen_v4_screenshots.py"
Cohesion: 0.60
Nodes (5): build_screens(), page(), Generate v4 UI screenshots for the README using HTML mockups + system…, shot(), sidebar()

### Community 938 - "setup-claude-code.sh script"
Cohesion: 0.60
Nodes (5): log_error(), log_info(), log_success(), print_header(), setup-claude-code.sh script

### Community 941 - "PhaseSequenceError"
Cohesion: 0.33
Nodes (4): TestPhaseSequenceError, PhaseSequenceError, Exception, Raised when a phase is attempted out of order.

### Community 942 - "test_generate_context_standing_instructions.py"
Cohesion: 0.40
Nodes (5): _load_module(), Regression test: autonomous issue-context generation must not silently truncate…, Sanity check on the fixture assumption this test relies on., test_claude_md_standing_instructions_present_past_4000_chars(), test_load_codebase_context_includes_standing_instructions()

### Community 943 - "_auth_headers"
Cohesion: 0.73
Nodes (5): _auth_headers(), TestClient, test_agent_profile_api_preserves_ui_fields(), test_backend_server_exposes_observability_savings_and_usage(), test_backend_server_exposes_schedules_routes()

### Community 944 - "webui/commands.py"
Cohesion: 0.47
Nodes (5): Any, Path, run_command(), _safe_allowlist(), validate_command()

### Community 945 - "harness.py"
Cohesion: 0.40
Nodes (3): EvalResult, Evaluation harness – runs an agent against a Task, records the Trajectory,…, Outcome of running one task through the harness.

### Community 946 - "_rrf"
Cohesion: 0.40
Nodes (5): Combine ranked lists with Reciprocal Rank Fusion., _rrf(), test_rrf_merges_two_rankings(), test_rrf_scores_descending(), test_rrf_single_ranking_preserves_order()

### Community 947 - ".build_context"
Cohesion: 0.50
Nodes (3): Any, Public snapshot of live agency state (used by the LiveKit worker tools)., Gather live agency state for SAM's situational awareness.

### Community 948 - "get_harness_adapter"
Cohesion: 0.40
Nodes (5): get_harness_adapter(), harness_active(), harness_catalog(), Return the full ECC harness catalog with capabilities. Public — no auth…, Return the currently active ECC harnesses with session metrics. Authenticated —…

### Community 950 - "1. What This Repo Does"
Cohesion: 0.40
Nodes (5): 1. What This Repo Does, Non-goals, Production deployment, Success metrics, What the platform is

### Community 951 - "/arch-review — Architecture Agent"
Cohesion: 0.40
Nodes (4): /arch-review — Architecture Agent, Key Architectural Principles, Steps, When to use

### Community 952 - "/devops-check — DevOps Agent"
Cohesion: 0.40
Nodes (4): Deployment Checklist, /devops-check — DevOps Agent, Steps, When to use

### Community 953 - "/docs-update — Documentation Agent"
Cohesion: 0.40
Nodes (4): /docs-update — Documentation Agent, Documentation Standards, Steps, When to use

### Community 954 - "/qa-check — QA Agent"
Cohesion: 0.40
Nodes (4): /qa-check — QA Agent, Steps, What NOT to do, When to use

### Community 955 - "Command: /review"
Cohesion: 0.40
Nodes (4): Command: /review, References, Usage, What It Does

### Community 956 - "/security-audit — Security Agent"
Cohesion: 0.40
Nodes (4): Escalation, /security-audit — Security Agent, Steps, When to use

### Community 957 - "pre-push"
Cohesion: 0.70
Nodes (4): pre-push script, _error(), _head(), _info()

### Community 958 - "Skill: browserbase-search — Structured Web Search"
Cohesion: 0.40
Nodes (4): Best practice: search → fetch → browse, Python snippet, Setup, Skill: browserbase-search — Structured Web Search

### Community 959 - "Issue #230 — DUPLICATE"
Cohesion: 0.40
Nodes (4): Actions Taken, Issue #230 — DUPLICATE, References, Resolution

### Community 961 - "Agent job lifecycle"
Cohesion: 0.40
Nodes (4): Agent job lifecycle, API, Progress phases, States

### Community 962 - "Docker (local or any container host)"
Cohesion: 0.40
Nodes (4): Build, Docker (local or any container host), Provider configuration (recommended for cloud), Run (minimal)

### Community 963 - "Rollout"
Cohesion: 0.40
Nodes (5): 1. Verify the router sees your providers, 2. Enable on one instance, 3. Watch for a few hours, 4. Roll out or roll back, Rollout

### Community 964 - "Who is this for?"
Cohesion: 0.40
Nodes (5): The 5-person SaaS startup that can't afford a full team yet, The digital agency running 10 client accounts, The e-commerce shop with a 10-person ops team, The professional services firm that runs on documents and tribal knowledge, Who is this for?

### Community 965 - "SECTION E — Autonomy & Self-Healing (AOS / MYT / ECC)"
Cohesion: 0.40
Nodes (5): E1 — Cross-Harness Routing (ECC Pattern) [P1] [ECC], E2 — Self-Healing Agent Loop (Detect + Repair Own Failures) [P1] [AOS / MYT], E3 — Autonomous Monitoring with Trend Watcher [P2] [AOS], E4 — Nightly Self-Evaluation + Regression Tests [P2] [HRM / AOS], SECTION E — Autonomy & Self-Healing (AOS / MYT / ECC)

### Community 966 - "SECTION F — Developer Experience (CBF / ECC)"
Cohesion: 0.40
Nodes (5): F1 — Codebuff-Style Precise Diff Application [P0] [CBF], F2 — MCP Server Exposing Proxy Capabilities [P1] [CBF / ECC], F3 — Local Dev Dashboard with Live Metrics [P2] [CBF / CHM], F4 — SDK / Client Library Generation [P2] [CBF], SECTION F — Developer Experience (CBF / ECC)

### Community 967 - "Runtime troubleshooting"
Cohesion: 0.40
Nodes (4): Agent mode timeout, Missing binary / task harness, Runtime troubleshooting, Workspace validation failures

### Community 968 - "knowledgeGraphTab.test.js"
Cohesion: 0.40
Nodes (4): { describe, test, expect }, fs, path, src

### Community 969 - "loginFlowNoTimeout.test.js"
Cohesion: 0.40
Nodes (4): apiSource, { describe, test, expect }, fs, path

### Community 970 - "test_company_stale_id_recovery.test.js"
Cohesion: 0.40
Nodes (4): { describe, test, expect }, fs, path, src

### Community 971 - "worker_no_cache.test.js"
Cohesion: 0.40
Nodes (4): { describe, test, expect }, fs, path, workerSource

### Community 972 - "scripts/agile_ceremonies.py"
Cohesion: 0.70
Nodes (4): _load(), main(), ModuleType, _write_summary()

### Community 973 - ".chat"
Cohesion: 0.40
Nodes (3): Any, Send a chat completion request., Stream a chat completion response.

### Community 974 - "_clean_director"
Cohesion: 0.40
Nodes (5): Clear director state and the cached strategy warnings (tests only)., reset(), _clean_director(), fixture, Reset the process singleton around every test.

### Community 975 - "Prompt Library Changelog"
Cohesion: 0.40
Nodes (4): Added, Format, Prompt Library Changelog, [Unreleased]

### Community 976 - "Proof"
Cohesion: 0.40
Nodes (5): Honesty notes (read before quoting the numbers), Proof, Reproduce any audit yourself, The self-audit (yes, we publish our own imperfect score), What's coming next in this directory

### Community 977 - "build_llama_cpp.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), W(), Warn()

### Community 978 - "download_glm52_weights.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), Warn(), W()

### Community 979 - "download_glm52_weights.sh script"
Cohesion: 0.70
Nodes (4): download_glm52_weights.sh script, fail(), ok(), warn()

### Community 980 - "_fetch_pytest_failures.py"
Cohesion: 0.50
Nodes (4): _gh_json(), main(), Pull the python-test failure log via gh run view --log and print the failing-…, Run a gh CLI call and parse its JSON stdout. Returns (parsed | None, stderr).

### Community 981 - "setup_colibri.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), Warn(), W()

### Community 982 - "setup_colibri.sh script"
Cohesion: 0.70
Nodes (4): setup_colibri.sh script, fail(), ok(), warn()

### Community 983 - "status_colibri_server.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), W(), Warn()

### Community 985 - "TestMobileNavigation"
Cohesion: 0.40
Nodes (3): Mobile-specific: hamburger menu, responsive layout., Verify key pages load in mobile viewport., TestMobileNavigation

### Community 986 - "test_v5_screens_smoke.py"
Cohesion: 0.50
Nodes (3): _login(), E2E UI smoke test: every v5 screen renders without errors. This is the…, test_every_v5_screen_renders_without_errors()

### Community 987 - "test_agent_runtime_wrapper.py"
Cohesion: 0.70
Nodes (4): _load_agent_runtime_module(), test_wrapper_exposes_hermes_task_endpoints(), test_wrapper_exposes_opencode_run_endpoint(), test_wrapper_falls_back_to_installed_model()

### Community 990 - "worker/index.js"
Cohesion: 0.70
Nodes (4): fetch(), needsProxy(), PROXY_PREFIXES, scheduled()

### Community 993 - "recovery.py"
Cohesion: 0.67
Nodes (3): detect_secrets(), main(), Recover CHANGELOG.md from a Git merge conflict in its [Unreleased] block. Pre-…

### Community 994 - "test_activity_logs.py"
Cohesion: 0.67
Nodes (3): clear_error_log_buffer(), _auth_headers(), test_activity_endpoint_includes_recent_error_logs()

### Community 995 - "_oauth_popup_html"
Cohesion: 0.50
Nodes (4): _oauth_popup_html(), Tiny HTML page that fires postMessage to the opener then self-closes., serve_spa(), HTMLResponse

### Community 996 - "10. Testing Constitution"
Cohesion: 0.50
Nodes (4): 10. Testing Constitution, Test rules, Test structure, Testing Expectations

### Community 997 - "5. AI Provider Architecture"
Cohesion: 0.50
Nodes (4): 5. AI Provider Architecture, Current state, Fallback chain, Provider interface contract

### Community 998 - "6. Agent Architecture"
Cohesion: 0.50
Nodes (4): 6. Agent Architecture, Agent lifecycle, Current state, Internet access (Web Reach) — use it to verify, not guess

### Community 999 - "aider_config.sh"
Cohesion: 0.50
Nodes (3): OPENAI_API_BASE, OPENAI_API_KEY, aider_config.sh script

### Community 1002 - "providers.yaml"
Cohesion: 0.50
Nodes (4): Bulkhead sizing, Per-minute token budgets, providers.yaml, Tiers

### Community 1003 - "Issue → Context → Draft PR automation"
Cohesion: 0.50
Nodes (4): Backfilling existing issues, Free-first model routing, Issue → Context → Draft PR automation, The workflows

### Community 1004 - "The 24x7 agency — your agents never go idle"
Cohesion: 0.50
Nodes (4): Nothing goes down quietly, The 24x7 agency — your agents never go idle, What runs automatically after onboarding, When something goes wrong, agents fix it — not you

### Community 1005 - "Privacy, security, and cost"
Cohesion: 0.50
Nodes (4): Privacy, security, and cost, Security posture, What it costs to run, Your data never leaves your server

### Community 1006 - "Credential Rotation Runbook"
Cohesion: 0.50
Nodes (3): Credential Rotation Runbook, Guardrails already in place, What to rotate (owner action, ~10 minutes)

### Community 1007 - "Runbook: `make doctor`"
Cohesion: 0.50
Nodes (3): Roadmap, Runbook: `make doctor`, What it checks and why

### Community 1008 - "render"
Cohesion: 0.50
Nodes (3): RENDER_API_KEY, docker, render

### Community 1009 - "scripts"
Cohesion: 0.50
Nodes (4): scripts, build, start, test

### Community 1010 - "list_available_fixes"
Cohesion: 0.50
Nodes (3): list_available_fixes(), Return all available one-click fixes., Contract: Fix list includes at least restart_ollama.

### Community 1011 - ".execute"
Cohesion: 0.50
Nodes (3): RoutingDecision, TaskResult, TaskSpec

### Community 1012 - "_resolve_default_executor_model"
Cohesion: 0.50
Nodes (3): Any, Resolve the default executor model via the catalog (UNIT 7). Was hardcoded to…, _resolve_default_executor_model()

### Community 1014 - "stop_colibri_server.ps1"
Cohesion: 0.83
Nodes (3): Fail(), Ok(), W()

### Community 1016 - "start_server.sh"
Cohesion: 0.50
Nodes (3): OLLAMA_HOST, OLLAMA_MODELS, start_server.sh script

### Community 1017 - "check_services"
Cohesion: 0.67
Nodes (3): check_services(), main(), Check if local services are running. Extends the original (proxy + Ollama)…

### Community 1022 - "test_iteration_6_features.py"
Cohesion: 0.50
Nodes (3): Test iteration 6 features: - POST /api/tasks/ auto-assigns an available agent…, Return True if we can open a TCP connection to the backend server., _server_reachable()

### Community 1024 - "test_no_exception_detail_leaks.py"
Cohesion: 0.50
Nodes (3): parametrize, tests/test_no_exception_detail_leaks.py — Guard against str(exc)/str(e) leaking…, test_no_raw_exception_detail_in_http_response()

### Community 1025 - "test_skills_route_order.py"
Cohesion: 0.67
Nodes (3): tests/test_skills_route_order.py — /api/company/skills must not be shadowed.…, _route_index(), test_static_skills_routes_precede_dynamic_company_id_route()

### Community 1026 - "github"
Cohesion: 0.50
Nodes (3): github, enabled, silent

### Community 1027 - "10. CI/CD Standards"
Cohesion: 0.67
Nodes (3): 10. CI/CD Standards, Deployment, Pipeline (22 checks)

### Community 1028 - "11. Rewrite Strategy"
Cohesion: 0.67
Nodes (3): 11. Rewrite Strategy, Phased approach, Rules

### Community 1029 - "3. Repository Constitution"
Cohesion: 0.67
Nodes (3): 3. Repository Constitution, Forbidden patterns, Required patterns

### Community 1030 - "7. Scheduler Architecture"
Cohesion: 0.67
Nodes (3): 7. Scheduler Architecture, Current state, Known issues (fixed)

### Community 1031 - "8. Authentication Architecture"
Cohesion: 0.67
Nodes (3): 8. Authentication Architecture, Auth dependency chain, Auth flows

### Community 1035 - "Configuration reference"
Cohesion: 0.67
Nodes (3): Configuration reference, Provider priority chain, Running the brain on local Ollama (via a tunnel)

### Community 1058 - "test_direct_adapter_does_not_bypass"
Cohesion: 0.67
Nodes (3): skipif, Calling the adapter directly (the /runtimes/{id}/execute path) must stay gated:…, test_direct_adapter_does_not_bypass()

### Community 1059 - "_enable_filter"
Cohesion: 0.67
Nodes (3): _enable_filter(), fixture, Ensure filter is enabled for all tests.

## Knowledge Gaps
- **3367 isolated node(s):** `duplicate.sh script`, `heartbeat.sh script`, `redact_secrets.sh script`, `docker`, `RENDER_API_KEY` (+3362 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **120 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AgentRunner` connect `AgentRunner` to `ProviderConfig`, `backend/server.py`, `FreeBuffAgent`, `AgentSessionStore`, `ReactScratchpad`, `proxy.py`, `E2BAdapter`, `ai/router.py`, `BackgroundAgent`, `failover_chat_completion`, `test_ceo_supervision.py`, `WorkflowOrchestrator`, `ExecutionRequest`, `TaskSpec`, `MCPUnavailableError`, `AdaptiveHalter`, `test_ceo_micromanager.py`, `LocalWorkspace`, `MCPClient`, `workflow_orchestrator.py`, `test_empirical_verify.py`, `WorkflowRun`, `MultiAgentSwarm`, `test_agent_free_brain.py`, `TestWorkspace`, `direct_chat.py`, `ContextPruner`, `TokenBudget`, `GitHubTools`, `TestAgentLoopMCPIntegration`, `test_backend_server_features.py`, `TestZeroAttemptDiagnostics`, `ContextManager`, `test_self_heal_v2.py`, `WorkspaceTools`, `StuckDetector`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Why does `AgentSessionStore` connect `AgentSessionStore` to `ProviderConfig`, `backend/server.py`, `FreeBuffAgent`, `proxy.py`, `AgentRunner`, `test_memory.py`, `workflow_orchestrator.py`, `test_event_log.py`, `WorkflowRun`, `WorkflowOrchestrator`, `ExecutionRequest`, `IssueCategory`, `direct_chat.py`, `diagnostics.py`?**
  _High betweenness centrality (0.018) - this node is a cross-community bridge._
- **Why does `ExecutionRequest` connect `ExecutionRequest` to `ProviderConfig`, `backend/server.py`, `test_contract_enforcement.py`, `AgentSessionStore`, `CompanyGraphStore`, `AgentRunner`, `OrchestratorSupervisor`, `workflow_orchestrator.py`, `test_telegram_auto_approve.py`, `telegram_bot.py`, `WorkflowRun`, `WorkflowOrchestrator`, `ModelRouter`, `_resolve_push_token`?**
  _High betweenness centrality (0.016) - this node is a cross-community bridge._
- **Are the 160 inferred relationships involving `AgentRunner` (e.g. with `AgentCoordinator` and `AgentSpec`) actually correct?**
  _`AgentRunner` has 160 INFERRED edges - model-reasoned connections that need verification._
- **Are the 209 inferred relationships involving `HTTPException` (e.g. with `activate_instance()` and `change_user_role()`) actually correct?**
  _`HTTPException` has 209 INFERRED edges - model-reasoned connections that need verification._
- **Are the 109 inferred relationships involving `AgentSessionStore` (e.g. with `AgentPhaseError` and `AgentRunner`) actually correct?**
  _`AgentSessionStore` has 109 INFERRED edges - model-reasoned connections that need verification._
- **Are the 73 inferred relationships involving `ProviderConfig` (e.g. with `AgentStatusEntry` and `AgentStatusResponse`) actually correct?**
  _`ProviderConfig` has 73 INFERRED edges - model-reasoned connections that need verification._