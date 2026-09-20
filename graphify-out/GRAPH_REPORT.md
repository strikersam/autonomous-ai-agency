# Graph Report - autonomous-ai-agency  (2026-09-20)

## Corpus Check
- 1528 files · ~2,222,388 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 54 file(s) not represented in the graph (top: (none) 16, .bat 5, .css 5)

## Summary
- 32410 nodes · 66700 edges · 1238 communities (1083 shown, 155 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 6576 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `7fd30f21`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- llm/router.py
- backend/server.py
- _fixture
- proxy.py
- TaskSpec
- test_llm_router_queue_cache.py
- CompanyGraphService
- TaskWorkflowService
- AgentJobManager
- api.js
- brain_config.py
- test_one_model_catalogue.py
- LLMRequest
- test_llm_router_resilience.py
- Task
- SelfHealingAgent
- PolicyEngine
- test_trend_scoping.py
- test_governance_sandbox.py
- test_model_router.py
- company_api.py
- test_ceo_micromanager.py
- test_governance_enforcement.py
- test_e2b_sandbox.py
- test_runtimes.py
- CompanyGraphStore
- test_llm_router_strategies.py
- Evidence
- services/background.py
- Agency
- ._dispatch_tool
- failover_chat_completion
- WebsiteScanner
- SQLiteStore
- ImprovementLoop
- LLMRouter
- MongoDBStore
- get_user_role
- test_ceo_dispatcher.py
- probe_model_liveness
- resolve_component_model
- AgentRunner
- TestExtendedCacheTTL
- PrimeAgentAdapter
- test_unit8_model_catalog.py
- Added
- V5App.jsx
- Specialist
- secrets_store.py
- test_agents.py
- SeoAuditEngine
- runtimes/api.py
- setup/api.py
- test_loop_registry.py
- KeyPool
- Changed
- WorkflowOrchestrator
- get_task_store
- RenderOpsMonitor
- HttpxFetcher
- resolve_active_brain
- seo_portfolio_bridge.py
- test_startup_warmup.py
- test_web_reach.py
- facade.py
- ai/self_heal.py
- ProviderManager
- api.ts
- build_governance_router
- Fixed
- test_sam_livekit.py
- user_research_skill.py
- detector.py
- ExecutionRequest
- FeatureMatrix
- test_provider_router.py
- engine.py
- DeterministicEngine
- test_cost_aware_routing_eval.py
- test_model_catalog.py
- WorkspaceError
- ResearchTask
- test_ceo_supervision.py
- TestClient
- validate_outbound_url
- services/seo_audit.py
- TestClient
- PerformanceAnalytics
- test_repo_connection.py
- test_procedural_memory.py
- failover_client.py
- _Response
- test_shared_state.py
- AgentJobResult
- test_knowledge_sync.py
- PersistentMemoryStore
- TokenBudget
- KnowledgeScreen.jsx
- models/seo_audit.py
- test_hermes_in_process.py
- ProviderConfig
- E2BAdapter
- test_scanner_headless.py
- direct_chat.py
- AgileSprint
- job_manager.py
- BrowserSession
- FinancialMetrics
- LogWatcher
- asyncio
- OllamaCircuitBreaker
- Page
- portfolio_intelligence.py
- Agent
- tasks/api.py
- CEOLedger
- test_integration_c4_c5_c6_d3.py
- CompanyGraph
- ToolRegistry
- ai_runner.py
- _cfg
- _llm_catalog
- Settings
- BackgroundAgent
- os
- test_vision_routing.py
- heal_signature
- test_pr_approval_gate.py
- _llm_catalog
- test_sqlite_store.py
- AgentPlan
- Command
- register_webui
- persist_plan_spec
- frontend/package.json
- test_context_rulebook.py
- TestAdapterMetadata
- workflow_orchestrator.py
- ArtifactStore
- _StubProvider
- test_response_cache.py
- test_llm_router_e2e.py
- test_trend_watcher.py
- WorkspaceManager
- InferenceCache
- checkpoint.py
- test_contracts_agency.py
- ensure_self_company
- ContextManager
- TestHarnessAdapter
- test_governance_api.py
- KimiBrowserDriver
- test_issue_intake.py
- WorkflowRun
- _cfg
- ReactScratchpad
- RepowiseIntelligence
- resolve_provider_for
- clear_cooldowns
- Event
- brain_failover.py
- ChatHistoryStore
- _step
- RewardScorer
- QuickNoteQueue
- FeatureMaturity
- telegram_bot.py
- WorkflowEngine
- PortfolioManager
- RequestQueue
- SchedulesScreen.jsx
- diagnostics.py
- test_e2b_task_wiring.py
- activation_api.py
- MCPClient
- seo_api.py
- KeyStore
- AdminIdentity
- test_llm_router_disabled.py
- TaskDispatcher
- ContextWindowManager
- _cfg
- test_e2b_data_flow.py
- test_portfolio_intelligence.py
- urllib_parse
- looks_like_secret_file
- WorkflowBuildRequest
- _run
- WindowsServiceManager
- KnowledgeGraph
- ProvidersScreen.jsx
- Workspace
- test_failover_silent_exhaustion.py
- run-claude-code.py
- test_runtime_governance.py
- NotificationDispatcher
- FreeBuffAgent
- PromptCacheManager
- TestCatalogFable51
- _job_text
- test_video_transcript.py
- PreflightReport
- WorkspaceTools
- test_audit.py
- anthropic_compat.py
- test_classify_dependabot_update.py
- compare_runtimes.py
- WorkspaceManifest
- asyncio
- test_operational_incidents.py
- langfuse_obs.py
- MetricsRegistry
- ScheduledJob
- TaskStatus
- test_agent_tool_governance.py
- ProviderRouter
- test_features_api.py
- portfolio_api.py
- Part A — CodeRabbit review fixes for this PR (do first, small)
- Docker Agent Runtimes Setup
- TaskBoardScreen.jsx
- TestRecordUsageAndStats
- AgentScheduler
- get_store
- test_verification_strategies.py
- Persistent Memory System
- test_agent_free_brain.py
- test_anthropic_router.py
- AgentSessionStore
- BudgetTracker
- v4_api.py
- AnthropicProvider
- Conflicts and Stale Facts
- Any
- JCodeAdapter
- workflow/api.py
- SeoFixer
- Workflow
- gsap.min.js
- chat_handlers.py
- DistributedRateLimiter
- test_purge_backlog.py
- TrendWatcher
- TemporalContextGraph
- llm_providers.py
- test_daily_automation_2026_05_15.py
- scrub
- test_pr923_fixes.py
- Autonomous AI Agency
- service_daemon.py
- test_background_services.py
- TestClient
- test_telegram_webhook.py
- PatternConsolidation
- test_control_plane_api.py
- OrchestratorQueue
- ContextPruner
- SettingsHub.jsx
- ref_react
- allow_paid
- test_colibri_brain_shim.py
- _Collection
- SyncService
- MultiAgentSwarm
- GitHubTools
- test_daily_2026_07_27.py
- PlaybookLibrary
- test_backend_lifespan_skips_bg_when_flag_false
- Usage
- pr_approval_gate.py
- REWRITE_PLAN.md — Phased Migration Strategy
- CEOSupervisor
- _cfg
- test_mcp_governance.py
- test_persistent_memory.py
- test_provider_enable_disable.py
- test_sam_voice.py
- AdaptiveHalter
- SecurityScanner
- test_provider_render_env.py
- agent_runtime.py
- RateLimitTracker
- test_chat_mode_regressions.py
- local_controller.py
- test_brain_failover.py
- TestDiagCommand
- test_all_providers_discovery.py
- TestDiscovery
- SpecEntry
- OutputFilter
- _resolve_brain_provider
- OrchestratorSupervisor
- Configuration Reference
- DashboardScreen.jsx
- context_rules.py
- _plan
- test_rate_limiter.py
- test_live_server.py
- _routing_candidates
- ContextCompressor
- ContextManager
- test_mcp_registry.py
- SparkProvider
- ResourceWatchdog
- Added
- test_connector_registry.py
- test_ephemeral_reaper.py
- skill_bindings.py
- test_microagents.py
- Retrospective
- app_settings.py
- Security Analysis — local-llm-server
- get_scheduler
- test_backend_server_features.py
- get_failover_manager
- Langfuse Observability Guide
- v3_models.py
- autonomous_fix.py
- probe_catalogues.py
- CheckpointStore
- OrchestratorCheckpointStore
- test_telegram_mutating_commands.py
- test_workspace_isolation.py
- SkillLibrary
- StuckDetector
- WorkspaceManager
- High-Agency Frontend Skill
- _resolve_user_github_token
- Quick-Note GitHub Issues Processing - Session Summary
- Added
- sync/service.py
- test_platform_controls.py
- switch_brain.py
- test_session_retro.py
- test_crispy_burn_in.py
- test_daily_2026_06_04.py
- test_skill_registry_boot_refresh.py
- test_autonomy_gate.py
- test_phase6_workflow.py
- AgileManager
- get_ceo_ledger
- SeoAuditReport
- register_admin_gui
- test_scheduler_hydration_bounded.py
- test_brain_availability_doctor.py
- test_ceo_router.py
- _redact_for_notification
- test_force_cleanup_conditional_delete.py
- test_commit_tracker.py
- test_rag_context.py
- ProjectScaffolder
- ScheduleStore
- test_dashboard_cache.py
- generate_context.py
- pytest
- ControlSpec
- SteeringInjector
- RuntimeHealthService
- test_claude_setup_audit.py
- decide
- sam_livekit_worker.py
- isolated_telegram_config
- test_internal_agent_did_work.py
- _captured_request_headers
- test_executive_advisory.py
- TerminalPanel
- Python Dependencies (`requirements.txt`)
- Technical Debt Register — local-llm-server
- _ensure_tasks_source_id_unique_index
- FeatureEntry
- SetupWizardPage.js
- ProviderConsole.jsx
- TrafficDirector
- webui/frontend/package.json
- keepalive.py
- CostAttributor
- _execute_skill_impl
- test_regression.py
- parametrize
- test_brain_liveness_dns_reason.py
- test_implement_agent_routing.py
- test_executive_advisory_api.py
- loop.py
- test_memory.py
- UserMemoryStore
- test_issue_triage.py
- WorkflowPhase
- SprintMetrics
- Initiative
- build_render_router
- seo_checks.py
- Deploy: FreeBuff Telegram bot (24×7)
- Claude Code + Qwen Local Setup
- traffic_director.py
- reset_cache
- system_instruction
- TestNoNvidiaFallbackIsRetired
- _Recorder
- ExecutiveAdvisory
- default_executives
- webui/router.py
- VoiceCommandInterface
- unsafe_target_reason
- Performance Analysis — local-llm-server
- test_hardware.py
- test_agent_chat_integration.py
- output_filter.py
- TestPoliciesGovernanceStableClaim
- monitor_lib.py
- APIClient
- _migration_block
- test_daily_automation_2026_08_03.py
- TestWorkflow
- _undeclared
- TestStreamableHTTPTransport
- 1. The Rules
- reset_store
- Session Handoff — 2026-06-15
- TASK 4 — End-to-end approval-gate test
- implement_agent.py
- video_transcript.py
- Company
- AgentMessageBus
- NIMConnectionPool
- Bulkhead
- test_activation_api.py
- TestClassifyPlainText
- test_service_token.py
- test_telegram_diag_endpoint.py
- v3_auth.py
- github_tools.py
- LessonStore
- Findings
- platform_controls_router.py
- Local AI Stack with Docker
- Implementation Prompt: Rich TaskBoard + Agile Sprint Integration
- Telegram Bot Setup
- CollectionLike
- audit
- _FakeSandbox
- analyze
- test_task_source_id_race.py
- test_all_features.py
- ._call
- test_v3_auth.py
- refine
- test_research_coordinator.py
- openclaw_str_e_fix.py
- SandboxHandle
- The fifteen strategies
- getBackendUrl
- test_p0_roadmap_a4_a5_b2.py
- test_north_mini_code.py
- test_webui_provider_priority.py
- _Cursor
- Screens
- _build_execution_request
- test_memory_guard.py
- ProviderCircuit
- SyntheticDataPipeline
- _process_task_callback
- _get
- test_cerebras_catalogue.py
- Path
- test_mostly_failed_steps.py
- test_v4_api.py
- ServiceDaemon
- LocalWorkspace
- HarnessEnrichment
- asyncio
- RateLimit
- AdaptivePermissions
- CoworkSession
- LocalBrainStore
- AdminScreen.jsx
- root
- Harness
- _resolve_push_token
- test_daily_digest.py
- PriorityTaskQueue
- TestLegacyRouterCacheTTL
- _make_provider
- _mock_provider_records
- _P
- RegistrySkill
- SkillRegistry
- agile_api.py
- V3 API Migration Plan — LLM Relay Platform
- Changelog
- ChatScreen.jsx
- ._order_group
- CEODispatcher
- ClaudeCodeAdapter
- Fixed
- TestAddConversationCacheBreakpoints
- test_local_controller.py
- test_openclaw_str_e_fix.py
- run_trend_analysis
- test_unit5_ui_provider_surface.py
- Fixed
- WorkspaceManager
- Skill: modularity-review
- Design Audit
- Findings
- Skill: modularity-review
- crispy_client.py
- HarnessRegistry
- is_model_available
- McpCard.jsx
- control_registry.py
- Dynamic Model Routing
- ControlsScreen.jsx
- PortfolioScreen.jsx
- AgentJobSnapshot
- infra_cost.py
- build_matrix
- ai/registry.py
- TestFailoverRegistryBaseUrls
- steering_for_task
- build_workflow.py
- context_plan_gate.py
- HybridSystem
- Page
- TestBrainFailoverModelUpdates
- test_tasks_cache_ttl_env.py
- Agent Runtime Setup
- MemoryKernel
- SamAgent
- _extract_tech_relevance
- HarnessAdapter
- Skill: fabric-patterns
- Analysis & Synthesis Instructions
- Production Readiness Assessment — local-llm-server
- SetupChecker
- Tween
- TestNormalizeResponseFormat
- Skill: fabric-patterns
- run
- db/__init__.py
- Admin Dashboard Guide
- .create
- Feature Guide
- scripts/doctor.py
- control_overrides.py
- Delegation Plan (agent-ready work packages)
- run_proxy.sh
- agency_fix.py
- LocalLLMSetup
- test_autonomy_pipeline_regressions.py
- fastapi_testclient
- test_brain_patch_service_token.py
- test_ai_insights.py
- TestSelfHealingInfrastructureClassification
- Fixed
- CostLine
- router_factory
- TestRoutes
- TestLangfuseSessionId
- validate_session_id
- Workspace
- ErrorInterceptorMiddleware
- BudgetOptimizer
- AgentsScreen.jsx
- memory_consolidation.py
- Comprehensive Skill Index (By Category)
- Agent Skill: Principal UI/UX Architect & Motion Choreographer (Awwwards-Tier)
- Component Map
- Architecture Overview — local-llm-server
- Pending Activities — Implementation Playbook
- Platform Guide — the full tour
- .submit
- Part A — Health Report
- WorkflowScreen.jsx
- sync_readme_gallery.py
- CircuitBreakerOpenError
- chat_completions
- _RedisBackend
- ._cannot_list
- TestAnthropicToolListCaching
- _override_user
- agent/workspace.py
- TestStopSlopChecker
- AIToolMetrics
- ReasoningResult
- harness_spec.py
- record_step_failures
- _first_paragraph
- cowork_session.py
- SKILL: Industrial Brutalism & Tactical Telemetry UI
- Skill: data-quality-audit
- What "Slop" Looks Like
- local_brain_router.py
- Added
- Section-by-Section Acceptance Criteria
- ResearchAgent
- Provider
- redact_connection_url
- TestEstimateTokensForMessages
- agent_readiness_audit.py
- sync_ngrok.py
- test_ci.sh
- TestRuntimeControl
- GuardrailEngine
- test_new_features_e2e.py
- test_frontend_deployment_guards.py
- test_health_endpoints.py
- test_keepalive.py
- test_openclaw_endpoints.py
- test_skill_registry.py
- test_task_brain_preflight.py
- TestRouterIntegration
- check_model_compatibility
- hermes_prompt.py
- MemoryMiddleware
- SavingsTracker
- safe_agency.py
- AITellIssue
- Skill: repowise-intelligence
- ARCHITECTURE.md — Target Architecture
- _valid_login_state
- Skill: repowise-intelligence
- The 10-Step Workflow
- Contributing to local-llm-server
- LRUCache
- CEO Micro-Management
- DeltaChunk
- Runbook — Apply the Fast Free NVIDIA Brain to Render (TASK 2)
- HealthStatus
- TestAuthAndTaskCreation
- SQLiteStore
- fabric_cli.py
- .publish
- TestStreamingDeltaReconstructor
- ManagedAgentDreams
- clear_wizard_state_cache
- test_agency_workflows_carry_the_failover_chain.py
- TestCatalogClaude5Models
- test_probe_report.py
- test_dockerfile_ships_root_modules.py
- CacheStats
- ._evict
- TestMCPServer
- test_migrate_local_brain_env.py
- TestChatHistoryStore
- test_rate_limit_backoff_survives.py
- sys
- _record_id
- _hash_component
- test_contract_enforcement.py
- .build
- CollaborationContext
- Skill: agent-harness
- Skill: checkpoint-strategy
- Process
- Skill: local-ai-query
- Skill: parallel-agents
- Skill: parallel-worktrees
- Design System: Taste Standard
- Process
- StreamingDeltaReconstructor
- test_version_consistency.py
- de
- TestTheSharedListFitsBothCallers
- Separate hosted dashboard backend (`backend/server.py`)
- Agency Core — Progress & Resume Log
- Attention Mechanisms Internals
- _push_down_where
- test_catalogue_probe.py
- test_critical_flows.py
- ._sprint
- _request
- TestAnthropicReasoningTokenExtraction
- TestBrainConfigUpdates
- DecisionsStoreTests
- test_dockerfile_ships_config_dir.py
- test_hermes_server.py
- financial_analyst.py
- test_tasks_awaiting_approval_api.py
- compilerOptions
- classify_direct_chat_intent
- validate_job_id
- _TFIDFIndex
- test_iteration_6_features.py
- StopSlopChecker
- Process
- Skill: lr-schedule-advisor
- Instructions
- Instructions
- Process
- Checks Performed
- Skill: training-stability-monitor
- _build_payload_or_500
- Skill: branch-cleanup
- Skill: perplexity — Web Research via Perplexity API
- Instructions
- Instructions
- Quick-Note Issues Processing Summary
- DirectChatSession
- _resolve_role_model
- AppShell.jsx
- TestExtendedThinkingRouting
- .failed
- SEO / GEO / AIO Audit Engine
- Traffic Distribution Across Providers
- overrides
- NvidiaProvider
- _FakePersistence
- _parse_reset_epoch
- .prune
- _deep_merge
- test_wrapper_falls_back_to_installed_model
- _is_exempt
- TestMCPClientStructuredOutput
- _StubManager
- .test_set_github_token_sqlite_string_id_does_not_500
- _run_analyze
- .set
- test_provider_state_durability.py
- TestDisabledReasonRendering
- MCPToolResult
- LLMReasoner
- AGENTS.md — Codebase Map & Operations Reference
- EdgeType
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
- check_feature
- Instructions
- Skill: graphify — Knowledge Graph Token Optimization
- Skill: platform-setup — Autonomous Agency Bootstrap
- Workspace Isolation Architecture
- Device compatibility and model picks
- Autonomy Uplift — Living Roadmap & Detailed Implementation Specs
- OpenClaw — iOS Control of the Agency (Single-Service Free-Tier Deploy)
- cleanup_stale_jobs
- rules
- OllamaManager
- strip_html
- GroqProvider
- _Budget
- _is_bedrock_model_id
- TestSwarmRoleRouting
- Agent Transparency Report
- InternalAgentAdapter
- _get_provider_policy
- _InMemoryBackend
- test_admin_local_brain_router.py
- test_compose_and_coordinate_api.py
- TestModelCostTableUpdates
- TestDecisionsBotLinks
- TestReviewRegressions
- TestSelfHealingInfrastructureNoCodeFix
- TestKillSwitchDurability
- test_providers_live_e2e.py
- test_quick_note_engine.py
- TestChatFallbackAndApproval
- Trajectory
- Instructions
- Instructions
- Process
- Instructions
- Skill: system-prompt-audit
- Skill: task-alive-updates
- Process
- Instructions
- TestRevenuePortfolio
- build_connectors_router
- Skill: agent-browser — Real Chrome Browser Automation
- Instructions
- Instructions
- Skill: dev-browser — Browser Automation via Sandboxed JS
- Instructions
- Agent Orchestration Design
- Universality: case-coverage matrix
- Quantization Internals
- TestWorkflowRun
- _overlap_score
- 467 Public Site Truth Spec
- _tokenize
- apply_overrides
- install-agents.sh
- hybrid_reasoning.py
- research_coordinator.py
- Kimi Web-Bridge Service
- .test_agency_sanctioned_in_orchestrator_mode
- _start_in_web_bot_tasks
- test_agile_api.py
- _parse_tool_calls_from_response
- test_brain_default_consistency.py
- _provider
- TestModelRegistryUpdates
- Backend changes
- _lookup_requirements
- test_task_clarification.py
- Any
- EvalHarness
- _keyword_search
- _extractive_compress
- SyncAgent
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
- AgentJobRequest
- RunnerLock
- 2. Critical Bugs & Exact Detection Signatures
- Tailored Onboarding, Editable Companies & Dynamic Roles
- Issue #467 — Section 1: Pulled State + PR Inventory
- .test_recurrences_are_reported_even_inside_cooldown
- TestRanking
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
- TestReasoningBudget
- get_data_dir
- build_tech_db.py
- ai_insights.py
- Security Policy
- UsageEvent
- test_conftest_hermetic_env.py
- main
- TestResolution
- test_empirical_verify.py
- test_event_log.py
- TestZeroAttemptDiagnostics
- test_google_provider_models.py
- _step
- TestRetrieveRelevant
- task.py
- Instructions
- Protocol: Premium Utilitarian Minimalism UI Architect
- The 5-Step Wrap-Up Ritual
- ._extract_tokens
- Brag Plan: Autonomous AI Agency (feature tour, v2)
- Hyperframes Composition Brief: Autonomous AI Agency (feature tour, v2)
- _normalize_tool_choice
- .apply_diff
- Skill: Agentic Agile
- Skill: browserbase-ui-test — Adversarial UI Testing
- Skill: financial-analyst (Agentic CFO)
- Graphiti Temporal Context Skill
- Skill: seo-audit-report
- _wfo_owned_run_or_404
- Agent Readiness Report
- Core Pillars
- 467 Golden Path — Locked Implementation Order
- orchestrator
- The Agent Roster
- TestWindowsAuth
- LLM Router — provider guide
- One command (recommended)
- ENGINEERING_STANDARDS.md — Patterns & Reference
- TestAFailedProbeIsNotASuccess
- TestExecution
- ChatResponse
- TestBigPasteThreshold
- TestSavePaste
- enrich_quick_note_issues.py
- _start_ceo_agency
- TestTheStaticFloorLeadsWithVerifiedIds
- TestDisabledProvidersAreNotFalselyReportedUnreachable
- TestTheWorkflowIsSafeAndReadOnly
- TestClaude5RegistryEntries
- TestRecordSuccess
- test_model_catalog_guard.py
- TestMongoGate
- test_render_mcp.py
- Any
- test_workflow_api_mount.py
- tts.py
- WorkspaceEscapeError
- BenchmarkReport
- _rrf
- _extract_workflow_relevance
- WorkflowTransition
- Skill: changelog-enforcer
- Skill: learn-rule
- Instructions
- la
- Command: /resume
- Skill: Agentic Portfolio Management
- Skill: changelog-enforcer
- Skill: cowork-session (Claude Cowork)
- Skill: video-context — read a video without watching it
- .daily_active_users
- autonomy_status
- ADR 003: Multi-Agent Orchestration with Plan-Execute-Verify Loop
- Documentation map
- The 8-Step Golden Path
- Issue #1356: quick-note:https://searchengineland.com/turn-seo-backlog-into-roadmap-485713
- _clean_singletons
- KV Cache Internals
- Release Procedure
- V2.0 Modernization — Runbook
- Setup
- Troubleshooting
- _get_current_user
- BrainWatchdog
- get_control
- send_digest
- run_patched_colibri.py
- ._get_checkpoint_store
- TestDashboard
- test_backend_requirements_cover_runtime_imports.py
- TestDirectChatNonBlocking
- test_probe_base_url_override_hits_the_typed_url
- .test_every_request_carries_a_real_user_agent
- test_changelog_parity_guard.py
- .log
- TestAgentLoopMCPIntegration
- test_process_quick_note_workflow.py
- TestEveryFullSuiteJobHasMongo
- TestPaidPolicyDurability
- test_scanner_deps_parity.py
- test_serve_spa_prefixes.py
- dry_clone_repo
- _safe_resolve
- stt.py
- navigation_metrics.py
- _score_turns
- Rule
- Any
- quality_checker.py
- Skill: docs-sync
- Agent: Implementer (Executor)
- Agent: Judge (Release / QA Gate)
- 4. Agent Execution Performance
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
- _reset
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
- _clean_director
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
- This repository is maintained by its own agents
- Platform Controls
- _should_fan_out
- E2BSandboxSession
- _is_brain_connection_error
- _isolate_operator_provider_state
- Runbook — Instance Activation
- test_probe_reports_dns_failure_end_to_end
- Prime Agent Runtime
- TestScannerService
- PULL_REQUEST_TEMPLATE.md
- security_fix_agent.py
- .test_specialist_service_initialization
- verify.sh
- Prompt Library
- .test_onboarding_service_initialization
- TestSanitizePasteForPreview
- submit_simple_task
- 2. Ollama Connection Handling
- WebhookSendRequest
- .process
- test_local_brain_router_smoke.py
- .get_phase_index
- .add_hook
- .stats
- RuntimeHealth
- TestRule
- TestCatalog
- TestHealthEndpoint
- captured
- TOOLS.md — Available Tools for AI Agents
- TestClear
- _patch_send_message
- classify_domain
- SIA
- Full-Output Enforcement
- summarise.sh
- ModelRegistry
- wiki_client
- AI Engineering Insights Skill
- Skill: hybrid-reasoning (Hybrid AI)
- Skill: Managed Agents Dreams
- Skill: Multi-Agent Coordinator
- Skill: Obsidian Knowledge Graph
- Multi-Agent Research Coordinator Skill
- Skill: SuperClaude Slash Commands
- Skill: SuperClaude Workflow Engine
- test_harness_spec.py
- ADR-006: Strangler Fig migration with backward-compat shims
- claude-mem Plugin — Persistent Memory for All Sessions
- LLM Router — migration guide
- What's New
- Cloudflare = the real working app
- launch-claude-code.sh
- PRD — README Marketing Refresh
- ModelRouter
- _replace
- check_changelog_parity.py
- quickstart.sh
- BackgroundServices
- test_daily_2026_06_14.py
- TestBrainFailoverModelAliases
- TestSupportMatrixDocsSync
- LogMonitor
- TestReasonsAreActionable
- TestProvidersScreen
- test_workflow_engine_run_happy_path
- TestMongoService
- TestTechSkillMap
- TestActiveStrategy
- openclaw_mobile_ui
- Music Cues: happy-beats-business-moves-vol-1-by-ende-dot-app
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
- The full agent capability roster
- Pre-Mortem Analysis: Agency Core autonomy story (Cloudflare deployment)
- gen_v4_screenshots.py
- setup-claude-code.sh script
- Report
- test_activity_feed.py
- TestWorkflowIntegration
- DockerAgentAdapter
- TestAwaitReady
- TestTheAgentRunsCurrentCode
- .update_status
- heartbeat.sh
- feature-implementer.md
- /devops-check — DevOps Agent
- /docs-update — Documentation Agent
- /qa-check — QA Agent
- Command: /review
- /security-audit — Security Agent
- pre-push
- Skill: browserbase-search — Structured Web Search
- Issue #230 — DUPLICATE
- Docker (local or any container host)
- Runtime troubleshooting
- Admin Dashboard Issues
- knowledgeGraphTab.test.js
- .chat
- governance/__init__.py
- inspect-agent-runtime.sh
- Prompt Library Changelog
- Proof
- check_rate_limit
- build_llama_cpp.ps1
- download_glm52_weights.ps1
- download_glm52_weights.sh script
- setup_colibri.ps1
- setup_colibri.sh script
- status_colibri_server.ps1
- TestMobileNavigation
- TestLegacyRouterServerFallback
- FeatureUnavailableError
- controls_app
- TestRetryDoesNotOverrideADeliberateClosure
- TestGhIsNotReAuthenticated
- RuntimeAdapter
- codebase-explorer.md
- docs-auditor.md
- risk-reviewer.md
- verification-reviewer.md
- aider_config.sh
- Credential Rotation Runbook
- Runbook: `make doctor`
- Runtime & Onboarding Issues
- render
- .__init__
- stop_colibri_server.ps1
- TestProviders
- TestWiki
- TestBackendMergesRegistryIntoTheEndpoint
- TestImplementerQueueSkipsReportOnlyIssues
- github
- graphify-refresh
- [Unreleased]
- Session Learnings
- frontend/.eslintrc.json
- fix_regression_locators.py
- ProviderRouter
- branch_cleanup.sh
- local-ai-health-check.sh
- pull-ai-models.sh
- test-anthropic.js
- .kick_inactive_editor
- .request_edit
- duplicate.sh
- hello_claude.py
- backend/__init__.py
- Xb
- Yb
- build-workflow
- commit-msg
- post-commit
- session-plan-bootstrap
- start_web_with_openclaw.sh
- frontend-redesign-prompt.md
- NEXT-SESSION-PROMPT.md
- docs/script.js
- get_tunnel_url.sh script
- prepare-commit-msg
- redact_secrets.sh
- handlers/__init__.py
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
- runtimes/adapters/__init__.py
- .__init__
- .__init__
- script.js
- setup-autostart.sh
- kimi_bridge_server/__init__.py
- setup_autostart_macos.sh
- start.sh
- stop-proxy.sh script
- stop_server.sh script
- .test_cleans_removes_double_spaces
- .test_detects_multiple_throat_clearing
- .test_detects_wh_starters
- .test_cleans_emphasis_crutches
- voice/__init__.py

## God Nodes (most connected - your core abstractions)
1. `_fixture()` - 313 edges
2. `AgentRunner` - 233 edges
3. `Task` - 223 edges
4. `TaskStatus` - 143 edges
5. `ProviderRouter` - 138 edges
6. `TaskStore` - 138 edges
7. `LLMRequest` - 124 edges
8. `Added` - 117 edges
9. `Added` - 117 edges
10. `Added` - 117 edges

## Surprising Connections (you probably didn't know these)
- `What this does not do` --references--> `allow_paid()`  [INFERRED]
  docs/llm-router/architecture.md → .github/scripts/provider_policy.py
- `Per-agent policies` --references--> `allow_paid()`  [INFERRED]
  docs/llm-router/configuration.md → .github/scripts/provider_policy.py
- `Cheap tiers` --references--> `allow_paid()`  [INFERRED]
  docs/llm-router/providers.md → .github/scripts/provider_policy.py
- `Candidate selection` --references--> `allow_paid()`  [INFERRED]
  docs/llm-router/routing.md → .github/scripts/provider_policy.py
- `Related` --references--> `allow_paid()`  [INFERRED]
  docs/runbooks/nvidia-nim-setup.md → .github/scripts/provider_policy.py

## Import Cycles
- None detected.

## Communities (1238 total, 155 thin omitted)

### Community 0 - "llm/router.py"
Cohesion: 0.02
Nodes (216): int, itertools, packages_llm, get_budget(), packages/llm/budget.py — token and cost accounting with spend alerts. Tracks…, The process-wide budget tracker., get_cache(), packages/llm/cache.py — layered caching. Five independent layers, each with its… (+208 more)

### Community 1 - "backend/server.py"
Cohesion: 0.01
Nodes (298): set_skill_registry(), admin_seed(), _agent_timeout_fallback_response(), AgentStatusEntry, AgentStatusResponse, AgentToolCallEntry, ApiKeyCreate, auth_me() (+290 more)

### Community 2 - "_fixture"
Cohesion: 0.02
Nodes (100): parse_event_stream(), Reduce a ``--mode json`` NDJSON stream to a :class:`ParsedRun`. Kept a module-…, Reset the singleton (for tests)., reset_failover_manager(), _messages_to_prompt(), Flatten an OpenAI messages list into a single string for the web UI., base_url(), mobile_page() (+92 more)

### Community 3 - "proxy.py"
Cohesion: 0.03
Nodes (163): Describes a single worker's task and constraints., WorkerSpec, set_quick_note_queue(), get_sam(), fastapi_middleware_cors, middleware, admin_control(), admin_delete_user() (+155 more)

### Community 4 - "TaskSpec"
Cohesion: 0.05
Nodes (70): abc, kimi_bridge_runtime_config(), Return Kimi bridge config for external runtimes (Hermes, Goose, Aider). Returns…, runtimes/adapters/aider.py — Aider adapter (TIER 3 — specialized). Aider…, Run aider non-interactively via `--message` flag., json_safe(), runtimes/adapters/claude_code.py — Claude Code CLI adapter (FIRST CLASS).…, runtimes/adapters/docker_agent.py — Docker-based agent runtime adapter. Spawns… (+62 more)

### Community 5 - "test_llm_router_queue_cache.py"
Cohesion: 0.06
Nodes (38): CacheManager, cosine_similarity(), payload_key(), Any, Exact-match cache key over the fields that change the answer. Routing…, Cosine similarity between two vectors, 0.0 when either is degenerate., Owns every cache layer and the policy for what may enter them., Whether a response to ``request`` may be stored. Deliberately conservative — a… (+30 more)

### Community 6 - "CompanyGraphService"
Cohesion: 0.03
Nodes (90): ApprovalPolicy, BusinessSystem, CompanyCreateRequest, CompanyGraphResponse, CompanyGraphSnapshot, CompanyResponse, CompanyUpdateRequest, Connector (+82 more)

### Community 7 - "TaskWorkflowService"
Cohesion: 0.03
Nodes (93): _apply_activity_status(), create_agent(), delete_agent(), get_agent(), _get_user(), list_agents(), list_runtime_agents(), Any (+85 more)

### Community 8 - "AgentJobManager"
Cohesion: 0.06
Nodes (29): AgentJob, AgentJobManager, heartbeat(), _now(), Any, Run a job using the provided runner and update the job's lifecycle, progress,…, Serialize the AgentJob to a JSON-serializable dictionary for external clients.…, get_agent_job_manager() (+21 more)

### Community 9 - "api.js"
Cohesion: 0.01
Nodes (45): approveGovernanceRequest(), autoRecommendCompanySkills(), chatSend(), createMcpServer(), createQuickNote(), delegateSeoFindings(), deleteMcpServer(), deleteModel() (+37 more)

### Community 10 - "brain_config.py"
Cohesion: 0.02
Nodes (146): _brain_provider_status(), _migrate_brain_to_safe_default(), Return per-provider metadata for the GET endpoint. Iterates every provider in…, Architecture (per plan §3), Files touched, Hard constraints (from the plan) — all met, Implementation — DB-persisted, UI-switchable Brain (PR #824 follow-up), New files (+138 more)

### Community 11 - "test_one_model_catalogue.py"
Cohesion: 0.06
Nodes (26): _nvidia_default(), parametrize, The platform-wide NVIDIA default must not be a retired model.…, The literal fallback used when NVIDIA_DEFAULT_MODEL is unset., A retired id may still appear elsewhere (cost tables, per-role maps); what must…, TestTheDefaultIsNotDead, _hardcoded_candidates(), parametrize (+18 more)

### Community 12 - "LLMRequest"
Cohesion: 0.03
Nodes (100): ProviderConfig, One configured endpoint. ``kind`` selects the adapter: ``openai`` (any OpenAI-…, packages_llm_providers, build_provider(), Instantiate the adapter for one provider config. Unknown kinds fall back to the…, LLMRequest, Cheap character-based token estimate (~4 chars/token). Deliberately dependency-…, A provider-neutral chat request. ``model`` is a *hint*: the router may… (+92 more)

### Community 13 - "test_llm_router_resilience.py"
Cohesion: 0.04
Nodes (62): Backoff policy for retryable failures., RetryConfig, BreakerState, Enum, str, _digest(), KeyRing, KeyState (+54 more)

### Community 14 - "Task"
Cohesion: 0.04
Nodes (69): Full task/issue document., Task, Any, One-line human explanation of why this task needs human approval. Reads risk…, Best-effort label of who will run this task once approved. Returns…, PUBLIC_URL-anchored dashboard deep link for the task detail. Returns empty…, Best-effort Telegram heads-up that a task is parked awaiting approval. Inline…, Inject auto_commit + repo context for self-repo ship-code tasks. Without… (+61 more)

### Community 15 - "SelfHealingAgent"
Cohesion: 0.06
Nodes (42): HealingEvent, _now(), Any, Translate external failure signals into improvement tasks and verify the fix…, Launch the background sweeper that resolves quiet verifying heals., Called when a CI workflow fails., Called when a GitHub issue with a bug label is opened., Called from the v4 dashboard 'Report Bug' form and the LogMonitor.… (+34 more)

### Community 16 - "PolicyEngine"
Cohesion: 0.04
Nodes (88): _egress_policy_reason(), agent/web_reach.py — Web Reach: zero-key internet access for agents. Gives…, Return why governance policy blocks *host*, or None. Runs strictly *after* the…, What changed on merge, fnmatch, ipaddress, _action_matches(), _as_list() (+80 more)

### Community 17 - "test_trend_scoping.py"
Cohesion: 0.10
Nodes (45): Issue title: the failure mode plus how hard it is recurring., _company_attr(), company_stack_tags(), extract_stack_tags(), fan_out_trend(), fan_out_trends(), is_code_change_trend(), map_trend_to_company_task() (+37 more)

### Community 18 - "test_governance_sandbox.py"
Cohesion: 0.07
Nodes (48): build_docker_run_argv(), DockerBackend, load_profiles(), Path, Build the hardened ``docker run`` argv for *profile*. Split out from the…, Runs sandboxes as hardened Docker containers. The subprocess runner is…, Load sandbox profiles from YAML, merged over the built-ins. A file may add…, Creates, tracks, reaps, and audits sandboxes. Lifecycle guarantees: * Every… (+40 more)

### Community 19 - "test_model_router.py"
Cohesion: 0.04
Nodes (99): classify_task(), _extract_recent_text(), Any, Concatenate plain text from the last *last_n* messages., Return the most likely task category for this request. Args: messages: OpenAI-…, get_registry(), Return model registry, extended with ROUTER_EXTRA_MODELS env entries.…, Tests for the dynamic model router. (+91 more)

### Community 20 - "company_api.py"
Cohesion: 0.03
Nodes (111): account_lifecycle(), AccountLifecycleResponse, auto_recommend_skills(), cancel_onboarding(), create_company(), delete_company_endpoint(), _DoctorCheck, _DoctorReport (+103 more)

### Community 21 - "test_ceo_micromanager.py"
Cohesion: 0.04
Nodes (105): services/ceo_dispatcher.py — Real CEO delegation layer. The CEO splits a…, Split the request into briefed, tier-assigned specialist sub-tasks. Returns the…, _runtime_id_for_role(), build_subtask_brief(), _coerce_subtasks(), decompose(), _env_flag(), _env_int() (+97 more)

### Community 22 - "test_governance_enforcement.py"
Cohesion: 0.03
Nodes (101): ApprovalRequest, ApprovalStatus, ApprovalStore, get_approval_store(), Any, Enum, str, Bounded, in-process store of approval requests. Uses a :class:`threading.Lock`… (+93 more)

### Community 23 - "test_e2b_sandbox.py"
Cohesion: 0.07
Nodes (47): _inject_token(), maybe_attach_e2b(), Best-effort scrub of ``token`` from ``text``., Open an E2B session and attach it as ``runner._mcp``. Single wiring line for…, Return ``(authed_url, clean_url)`` for a GitHub repo URL., _scrub_token(), _clean_e2b_env(), _FakeCommandResult (+39 more)

### Community 24 - "test_runtimes.py"
Cohesion: 0.06
Nodes (22): Return the single best adapter for *task_type*. If *preferred_runtime_id* is…, Maintains the catalogue of registered adapters and answers 'which runtimes can…, Return all adapters that can handle *task_type*, ordered by tier., RuntimeCapabilityRegistry, Any, Admin-configurable routing policy. Defaults are conservative (local-first, no…, Routes a TaskSpec to the best available runtime following the configured…, Return the last *limit* routing decisions (newest first). (+14 more)

### Community 25 - "CompanyGraphStore"
Cohesion: 0.03
Nodes (39): P1 — Close the remaining product gaps, Task 5 — Custom skills & workflows (create, not just view), Task 6 — Deeper website/repo scanning (more than "2 systems"), Task 7 — Knowledge base auto-reflect (ECC / Obsidian / graphify-style), Task 8 — Vector retrieval for the knowledge base (self-learn), KnowledgeItem, Find knowledge items matching any of the given tags., Structured knowledge about the company, systems, or processes. (+31 more)

### Community 26 - "test_llm_router_strategies.py"
Cohesion: 0.06
Nodes (57): HealthConfig, Strategy selection and degradation behaviour., Circuit breaker + health tracking thresholds., RoutingConfig, HealthTracker, _Outcome, ProviderHealth, Any (+49 more)

### Community 27 - "Evidence"
Cohesion: 0.06
Nodes (40): Evidence, Result of a website scan with detected systems and stack inference., Evidence supporting a system detection., Inferred technology stack from website/repo analysis., StackInference, WebsiteScanResult, _hostname_contains(), _hostname_matches() (+32 more)

### Community 28 - "services/background.py"
Cohesion: 0.08
Nodes (48): _now_str(), get_improvement_loop(), get_log_monitor(), set_log_monitor(), get_self_healing_agent(), set_self_healing_agent(), get_trend_watcher(), set_trend_watcher() (+40 more)

### Community 29 - "Agency"
Cohesion: 0.05
Nodes (71): Agency, AgencyCycleResult, AgentDirective, AgentRole, _build_ceo_prompt(), _collect_recent_git_context(), get_agency(), _parse_ceo_directives() (+63 more)

### Community 30 - "._dispatch_tool"
Cohesion: 0.02
Nodes (131): Any, Governance seam: judge the call, run it, audit the outcome. Deliberately a thin…, Append an event to the durable session log if a store is wired in., Lazy accessor for the SteerLM steering injector (B2)., Condense a tool result down to what belongs in an audit row. A tool result can…, Execute a named skill via SkillBindings. Called from the tool-call loop when…, Check if plan steps can run in parallel; returns result dict or None to fall…, Push commits and open a PR on GitHub. Returns the PR URL or None. Only… (+123 more)

### Community 31 - "failover_chat_completion"
Cohesion: 0.04
Nodes (102): What changes for callers, BrainFailoverExhausted, failover_chat_completion(), FailoverResult, _log_recovery(), RuntimeError, Every provider in the failover chain failed — the terminal error. Carries the…, A successful completion plus the accounting its callers need. (+94 more)

### Community 32 - "WebsiteScanner"
Cohesion: 0.03
Nodes (69): (1) & partly (4): "Something went wrong" masks the real error everywhere, NEW — (1)'s dominant real-world cause: live scanner crashes on `master` (found via CI on this PR, 2026-06-14), Root-cause findings (already investigated — do not re-derive), pytest_asyncio, main(), Post-deploy verification for the website scanner against the LIVE internet.…, Returns (url, ok, summary)., _scan_one() (+61 more)

### Community 33 - "SQLiteStore"
Cohesion: 0.03
Nodes (58): DetectedSystem, A business system detected on a company's website or in their stack., Get the most confident evidence description., Prepare a Pydantic model for SQLite storage., Prepare a SQLite row for Pydantic model., Create a new company in SQLite., Get a company by ID from SQLite., Update a company in SQLite. (+50 more)

### Community 34 - "ImprovementLoop"
Cohesion: 0.08
Nodes (34): DetectedIssue, ImprovementLoop, ImprovementLoopState, IssueCategory, IssueSeverity, _now(), Any, Enum (+26 more)

### Community 35 - "LLMRouter"
Cohesion: 0.03
Nodes (94): Fixed, count, Fixed, Embeddings, LiteLLM compatibility mode, LLM Router — local model guide, LM Studio, LocalAI (+86 more)

### Community 36 - "MongoDBStore"
Cohesion: 0.04
Nodes (46): Security, Security, MongoDBStore, Any, ObjectId, MongoDB implementation of the Company Graph store. Uses Motor (async MongoDB…, Get or create the MongoDB database connection., Convert string ID to ObjectId. (+38 more)

### Community 37 - "get_user_role"
Cohesion: 0.04
Nodes (52): compute_savings(), compute_time_series(), get_savings(), get_usage(), get_user_savings(), _period_start(), Any, BaseModel (+44 more)

### Community 38 - "test_ceo_dispatcher.py"
Cohesion: 0.03
Nodes (82): CEOResult, _decompose_into_subtasks(), get_ceo_dispatcher(), Return the shared CEODispatcher singleton., Reset the singleton (test helper)., Aggregated output from a multi-specialist execution., Decompose a request into 2-3 sub-tasks for specialist fan-out. Default…, reset_ceo_dispatcher() (+74 more)

### Community 39 - "probe_model_liveness"
Cohesion: 0.06
Nodes (39): probe_model_liveness(), ProbeResult, BaseModel, Outcome of a single (provider, model) liveness probe., Probe ``(provider, model)`` for liveness. Never raises. Returns a…, _catalogue_candidates(), _catalogue_role_preset(), _catalogue_safe_default() (+31 more)

### Community 40 - "resolve_component_model"
Cohesion: 0.03
Nodes (91): _catalog_defaults(), Resolve per-role defaults via the catalog. Returns None on import error., invalidate_brain_config_cache(), Clear the singleton's cache (used by tests + brain_policy invalidation)., Resolve the model id for a component's role on a provider. Parameters…, resolve_component_model(), Checklist, Rollout notes (+83 more)

### Community 41 - "AgentRunner"
Cohesion: 0.02
Nodes (120): AgentPhaseError, AgentRunner, Exception, Read a file safely, returning '' on error. When an E2B sandbox is attached…, Return True when no file is touched by more than one step., Raised when a named agent phase (planning, verification, etc.) fails., GATE: Golden Path steps #7-12 — the primary agent execution loop. This is the…, Set a per-session token spend cap (★3 rollout token budget). When *cap* > 0 the… (+112 more)

### Community 42 - "TestExtendedCacheTTL"
Cohesion: 0.08
Nodes (21): _breakpoint_at(), _make_provider(), _make_provider_1h(), _make_request(), _msgs(), tests/test_anthropic_conversation_caching.py — Rolling conversation cache…, Verify that build_payload propagates conversation cache breakpoints., Both the tool list and the conversation can be cached simultaneously. (+13 more)

### Community 43 - "PrimeAgentAdapter"
Cohesion: 0.05
Nodes (28): _child_env(), _kill_and_reap(), PrimeAgentAdapter, Terminate a subprocess and wait for it, ignoring races. ``asyncio.wait_for``…, Build the allowlisted environment for the CLI subprocess., Adapter for the Prime Agent / pi coding CLI., Return the path of the first available CLI binary, or None., tests/test_prime_agent_runtime.py — PrimeAgentAdapter unit tests. The event-… (+20 more)

### Community 44 - "test_unit8_model_catalog.py"
Cohesion: 0.04
Nodes (60): CatalogMirror, get_catalog(), get_model_catalog_store(), invalidate_catalog_cache(), ModelCatalogStore, Any, BaseModel, The full mirrored catalog document. (+52 more)

### Community 45 - "Added"
Cohesion: 0.04
Nodes (51): Return True only when the tool is definitively read-only and non-destructive.…, Remember a server-issued ``Mcp-Session-Id`` for subsequent requests., Added, Added, Render MCP — platform debugging and environment monitoring, 1. Coding sessions — stdio, via `.mcp.json`, 2. The running agency — Streamable HTTP against a deployed sidecar, Configuration (+43 more)

### Community 46 - "V5App.jsx"
Cohesion: 0.05
Nodes (30): API, getActivity(), V5App, HubTabs(), ActivationGate(), activityToAlert(), AlertsBell(), priorityConfig (+22 more)

### Community 47 - "Specialist"
Cohesion: 0.03
Nodes (49): What this maps to (real code, not a generic scaffold), What already exists (don't rebuild), SpecialistFamily, Find all specialists of a specific family., A specialist agent that can be provisioned for company-specific tasks., Check if this specialist can handle a task with given capabilities., Specialist, SpecialistFamily (+41 more)

### Community 48 - "secrets_store.py"
Cohesion: 0.06
Nodes (59): Finding A — `list_for_user` Mongo query diverges from the `_can_read` policy, UserRole, _can_read(), _can_write(), create_secret(), _decrypt(), delete_secret(), _encrypt() (+51 more)

### Community 49 - "test_agents.py"
Cohesion: 0.13
Nodes (20): agents/__init__.py — CRISPY multi-agent coding system., AgentProfile, _catalog_provider(), _get_defaults(), load_all_profiles(), make_architect_profile(), make_coder_profile(), make_reviewer_profile() (+12 more)

### Community 50 - "SeoAuditEngine"
Cohesion: 0.05
Nodes (38): Run a full SEO/GEO/AIO audit against a website and persist the evidence., run_seo_audit(), field_validator, A single occurrence of a check firing on a specific URL., Site-level facts discovered during the crawl., Request to run an SEO/GEO/AIO audit against a website., SeoAuditRequest, SeoIssueInstance (+30 more)

### Community 51 - "runtimes/api.py"
Cohesion: 0.05
Nodes (75): B. Make runtime activation non-blocking (`runtimes/control.py`,, _enrich_runtimes(), get_decision_log(), get_policy(), get_runtime(), list_runtimes(), _load_rich_policy(), PolicyUpdateBody (+67 more)

### Community 52 - "setup/api.py"
Cohesion: 0.07
Nodes (64): motor_motor_asyncio, complete_wizard(), _delete_wizard_state(), detect_configured_providers(), detect_hardware_for_wizard(), detect_models_for_wizard(), _detect_ollama_models(), get_setup_state() (+56 more)

### Community 53 - "test_loop_registry.py"
Cohesion: 0.04
Nodes (99): audit_drift(), _cmd_audit(), DriftReport, _grade(), load_registry(), load_registry_sync(), loop_readiness(), LoopRegistry (+91 more)

### Community 54 - "KeyPool"
Cohesion: 0.04
Nodes (38): api_keys_for(), _digest(), KeyPool, _KeyState, _PoolState, Round-robin key selection with per-key rate-limit cooldowns., Cool a single key after a 429 from it. Honours the provider's own ``Retry-…, True when every key in the pool is resting. This is the signal that the… (+30 more)

### Community 55 - "Changed"
Cohesion: 0.03
Nodes (115): _build_quick_note_instruction(), _close_github_issue(), _fetch_github_quick_notes(), _gh_repo(), _gh_token(), Close exhausted quick-note issues; dispatch Dev directives for open ones., Return the GitHub repo in 'owner/name' format. Priority: 1. GITHUB_REPOSITORY…, Return ALL open GitHub issues for this repo (not just 'quick-note' labelled).… (+107 more)

### Community 56 - "WorkflowOrchestrator"
Cohesion: 0.05
Nodes (46): Changed, Changed, Feature maturity — what's stable vs. beta, Admin API, Config Overrides, Feature Matrix, Feature Support Matrix, Gating Behavior (+38 more)

### Community 57 - "get_task_store"
Cohesion: 0.05
Nodes (64): _purge_backlog_core(), quick_notes_submit(), _QuickNoteBody, Shared purge implementation for the admin endpoint and the boot hook., Submit a quick-note URL or instruction from the dashboard FAB., Hand the 'connect & verify the repo' work to the agency's own agents. The task…, _seed_connect_task(), _blocked_retire_age_sec() (+56 more)

### Community 58 - "RenderOpsMonitor"
Cohesion: 0.04
Nodes (58): BaseModel, Response shape of ``GET /api/render/ops/status``. Declared here rather than in…, RenderOpsStatus, One deploy, normalised from whatever shape the tool returned., RenderDeploy, _latest_metric_value(), _note_recurrence(), _parse_timestamp() (+50 more)

### Community 59 - "HttpxFetcher"
Cohesion: 0.05
Nodes (29): MockTransport, browser_backend_available(), BrowserFetcher, FetchResult, HttpxFetcher, looks_blocked(), make_fetcher(), AsyncBaseTransport (+21 more)

### Community 60 - "resolve_active_brain"
Cohesion: 0.07
Nodes (53): BrainResolution, get_active_brain_sync(), get_provider_role_tags(), _host_is_openai_compatible(), invalidate_brain_cache(), _norm(), _pick_from_records(), _build() (+45 more)

### Community 61 - "seo_portfolio_bridge.py"
Cohesion: 0.05
Nodes (49): CapacityAllocation, InitiativeStatus, Enum, Agentic Portfolio Management — initiative prioritisation, capacity allocation,…, Result of fitting initiatives into a fixed capacity by WSJF priority., Total job size of initiatives that fit within capacity., Unused capacity after committing the selected initiatives., Fraction of capacity consumed (0.0–1.0). (+41 more)

### Community 62 - "test_startup_warmup.py"
Cohesion: 0.05
Nodes (38): Await one warm-up step, deferring it to the background if it overruns.…, _warmup_step(), _isolate_warmup_overflow(), asyncio, NoReturn, RuntimeError, Regression tests for the bounded startup warm-up and login bootstrap. Uvicorn…, A deferred step that fails must not leak a reference or an exception. (+30 more)

### Community 63 - "test_web_reach.py"
Cohesion: 0.05
Nodes (62): Ask the C-suite advisory layer a business question. This is the CEO's bridge…, _domain_list_reason(), _domain_matches(), _parse_domain_list(), Return True if *host* is *pattern* or a subdomain of it., Split a comma-separated env var into a normalised domain list., Return why the env-var domain policy blocks *host*, or None. Checks…, Zero-key internet access: pages, YouTube transcripts, search, RSS. Every public… (+54 more)

### Community 64 - "facade.py"
Cohesion: 0.03
Nodes (85): _get_current_user_thunk(), _get_optional_user_thunk(), Request, create_access_token(), create_refresh_token(), get_current_user(), get_optional_user(), github_callback() (+77 more)

### Community 65 - "ai/self_heal.py"
Cohesion: 0.05
Nodes (42): inspect, Any, packages/ai/self_heal.py — automatic brain self-healing. When the active brain…, One-shot self-healing pass. 1. Checks if the active brain provider is in a…, self_heal_brain_and_unblock_tasks(), _is_provider_actually_available(), Check if a provider is actually available (not just has a key). Unlike…, tests/test_langfuse_agency_wide.py — tests for PR #961 agency-wide Langfuse.… (+34 more)

### Community 66 - "ProviderManager"
Cohesion: 0.15
Nodes (19): _fake_user_auth(), Path, test_admin_can_create_anthropic_provider_via_webui_admin_api(), test_admin_can_create_provider_via_webui_admin_api(), test_ui_providers_and_workspaces_use_app_state(), default_store_paths(), JsonConfigStore, JsonStorePaths (+11 more)

### Community 67 - "api.ts"
Cohesion: 0.08
Nodes (60): adminBootstrap(), adminCreateProvider(), adminCreateWorkspace(), adminDeleteProvider(), adminDeleteWorkspace(), adminGetBrainPolicy(), adminGetProviderRoleTags(), adminHeaders() (+52 more)

### Community 68 - "build_governance_router"
Cohesion: 0.04
Nodes (65): build_governance_router(), approve(), _decide(), deny(), destroy_sandbox(), get_audit(), get_budget(), get_metrics() (+57 more)

### Community 69 - "Fixed"
Cohesion: 0.03
Nodes (81): Perform MCP handshake. Optional — tools/call works without it., _is_admin(), Check if a user has admin role. Works for both social_auth users (role in…, seed_default_providers(), Fixed, Fixed, Bug Log, Next Action (+73 more)

### Community 70 - "test_sam_livekit.py"
Cohesion: 0.05
Nodes (35): jwt, auth_headers(), livekit_env(), no_livekit_env(), _normalize_dockerfile(), parametrize, tests/test_sam_livekit.py — SAM realtime voice (LiveKit) integration. Covers: -…, Empty key/secret/identity/room must raise ValueError. (+27 more)

### Community 71 - "user_research_skill.py"
Cohesion: 0.03
Nodes (79): analyze_qualitative(), analyze_quantitative(), auto_register(), _classify_sentiment(), _extract_keywords(), plan_research(), Any, BaseModel (+71 more)

### Community 72 - "detector.py"
Cohesion: 0.10
Nodes (28): batch_compatibility(), _detect_amd_gpus(), _detect_apple_silicon_gpu(), _detect_cpu(), detect_hardware(), _detect_intel_arc_gpu(), _detect_nvidia_gpus(), _detect_ram() (+20 more)

### Community 73 - "ExecutionRequest"
Cohesion: 0.06
Nodes (39): Called by APScheduler when a cron fires. Dispatches to the orchestrator. This…, _scheduler_on_fire(), stop_orchestrator_supervisor(), ExecutionRequest, get_workflow_orchestrator(), Return the shared WorkflowOrchestrator singleton., Reset the singleton (test helper)., Canonical request to execute work through the golden path. This is the ONLY… (+31 more)

### Community 74 - "FeatureMatrix"
Cohesion: 0.05
Nodes (17): FeatureMatrix, Central support matrix — single source of truth. Loads the canonical feature…, Return True if the feature is enabled and not disabled., Return a warning string for beta/experimental features, or None., Render the matrix as a Markdown table for docs., Integration test: admin endpoint returns feature matrix JSON., TestAdminVisibility, TestConfigOverrides (+9 more)

### Community 75 - "test_provider_router.py"
Cohesion: 0.04
Nodes (53): _acquire_provider_probe(), extract_openai_text(), _normalize_nvidia_base_url(), _openai_url(), Try to acquire a distributed probe lock for *provider_id*. Returns True if this…, Release the probe lock for *provider_id*., Normalize NVIDIA base URLs to avoid double /v1 when openai_compat_url appends…, _release_provider_probe() (+45 more)

### Community 76 - "engine.py"
Cohesion: 0.06
Nodes (42): AgentRole, AgentSwarm, Any, Return the agent role responsible for *phase*., Return the AgentProfile for the agent driving *phase*., Return a JSON-serialisable summary of all agent profiles., Run a pre-gate or report phase through the correct agent. Enforces permission…, Execute a slice via the Coder agent (write-permitted). (+34 more)

### Community 77 - "DeterministicEngine"
Cohesion: 0.20
Nodes (5): DeterministicEngine, Rule-based reasoning engine for well-defined problems. Rules are evaluated in…, _make_rule(), Tests for agents.hybrid_reasoning — Hybrid AI., TestDeterministicEngine

### Community 78 - "test_cost_aware_routing_eval.py"
Cohesion: 0.06
Nodes (63): evals_cost_aware_routing, Cost-aware routing evaluation harness. Measures the cost-aware subagent routing…, main(), CLI for the cost-aware routing evaluation. python -m evals.cost_aware_routing…, ModelPrice, Model pricing for the cost-aware routing evaluation. Rates are first-party…, Per-token price for one model, in USD per 1,000,000 tokens., Override the price for a tier (e.g. a discounted or partner rate). (+55 more)

### Community 79 - "test_model_catalog.py"
Cohesion: 0.04
Nodes (74): _build_base_url_env_from_yaml(), _build_candidates_from_yaml(), _build_default_base_url_from_yaml(), _build_display_names_from_yaml(), _build_key_env_from_yaml(), _build_tier_from_yaml(), get_provider_candidates(), get_provider_display_name() (+66 more)

### Community 80 - "WorkspaceError"
Cohesion: 0.15
Nodes (8): Exception, Raise :exc:`WorkspaceAccessDeniedError` if *requesting_session_id* doesn't own…, Base class for all workspace errors., WorkspaceAccessDeniedError, WorkspaceError, WorkspaceLockError, WorkspaceNotFoundError, WorkspaceNotResumableError

### Community 81 - "ResearchTask"
Cohesion: 0.10
Nodes (10): Coordinates a multi-agent research workflow. Workflow: 1. plan(question) → list…, Decompose a research question into a default DAG. Default plan: web → docs…, Round-robin pick within a role (least-loaded first)., Execute the DAG until all tasks resolve or no progress is possible., Return the final synthesized answer, or a status report if blocked., Status counts across all tasks., A single decomposed sub-task in the research plan., Returns True when every dependency has completed. (+2 more)

### Community 82 - "test_ceo_supervision.py"
Cohesion: 0.06
Nodes (65): A subtask's full history: what it is, and every attempt at it., SubtaskRecord, _goal(), asyncio, Tests for the CEO ledger, the supervised escalation loop, and the 24x7 sweeper.…, A storage outage must never take the agency down., Two sweeping processes must not both re-drive the same goal.…, A sweeper that loses the claim reports in-flight, not redriven. (+57 more)

### Community 83 - "TestClient"
Cohesion: 0.08
Nodes (46): _auth_headers(), _build_agent_http_mock(), mock_get(), mock_post(), mock_put(), _exec(), _fake_request(), _mcp_tool_response() (+38 more)

### Community 84 - "validate_outbound_url"
Cohesion: 0.14
Nodes (25): test_git_ref_rejects_empty(), test_git_ref_rejects_flag_injection(), test_git_ref_rejects_shell_metacharacters(), test_git_ref_rejects_traversal(), test_git_ref_valid(), test_git_scheme_allows_ssh(), test_http_scheme_rejects_ssh(), test_https_public_host_allowed() (+17 more)

### Community 85 - "services/seo_audit.py"
Cohesion: 0.05
Nodes (33): bs4, csv, lxml, Aggregated report row - Screaming Frog CSV compatible., SeoIssueReportRow, analyze_page(), compute_pressure(), _count_syllables() (+25 more)

### Community 86 - "TestClient"
Cohesion: 0.10
Nodes (29): bare_repo(), _call(), _data(), git_config_env(), _is_error(), mcp_workspace_root(), Path, skipif (+21 more)

### Community 87 - "PerformanceAnalytics"
Cohesion: 0.12
Nodes (14): build_report(), PerformanceAnalytics, Compare engineering performance with vs without AI tooling. DX report findings:…, Record a PR completion., Difference in median cycle time: AI-assisted vs control. Returns negative…, Defect rate (0..1) for the requested cohort., PR throughput per cohort over the last `days` days., High-level performance summary for dashboards. (+6 more)

### Community 88 - "test_repo_connection.py"
Cohesion: 0.05
Nodes (67): Fan trends out to onboarded companies whose stack matches (G4). For each…, Completed Task Archive — June to August 2026, Phase 0 — `RepoConnection` plumbing + delivery-policy detection, Phase 1 — Plan-PR → Implementation  *(highest leverage; closes the live gap)*, Phase 2 — Review-comment resolution (Codex / CodeRabbit), Phase 3 — Quality gate + policy-conformant landing, Phase 4 — Monitor & regression guard, Phases (+59 more)

### Community 89 - "test_procedural_memory.py"
Cohesion: 0.24
Nodes (8): get_procedural_memory(), ProceduralMemoryStore, Remove all in-memory records. Returns the count removed., Return the process-wide ``ProceduralMemoryStore``, creating it if needed., In-memory skill store with optional durable persistence. Thread-safe: a single…, tests/test_procedural_memory.py — Unit tests for agent/procedural_memory.py…, store(), TestGetProceduralMemory

### Community 90 - "failover_client.py"
Cohesion: 0.03
Nodes (87): Parse an LLM tool-call response, tolerating common malformations. Handles: 1.…, Spawn a child AgentRunner for a delegated sub-task. When sub-agent configs are…, Return up to *limit* stored patterns relevant to *query*. Relevance is scored…, FailureCategory, E2: Classify a failure from its description text. Order matters:…, Classified failure types for targeted self-healing (E2)., Return the discovered model list for *provider_id*, or ``[]`` if unknown., _served_models() (+79 more)

### Community 91 - "_Response"
Cohesion: 0.07
Nodes (21): Added, Added, _get_director(), _ollama_reasoning_effort(), Any, Parse a 429/503 ``Retry-After`` header → seconds, or None. Accepts either…, Return the process TrafficDirector, or None if it is unavailable., Translate an OpenAI chat/completions payload to Bedrock Converse format. (+13 more)

### Community 92 - "test_shared_state.py"
Cohesion: 0.07
Nodes (27): claim(), cooldown_clear(), cooldown_get(), cooldown_set(), _get_backend(), incr_window(), Reset the singleton (for tests)., Try to acquire a named lock. Returns True if acquired, False if already held. (+19 more)

### Community 93 - "AgentJobResult"
Cohesion: 0.09
Nodes (14): AgentJobError, AgentJobResult, Any, BaseModel, field_validator, agent/contract.py — Typed public contract for the agent job lifecycle. Phase 1…, Structured error payload attached to a failed job., Typed result returned by a completed agent job. The ``response`` field is the… (+6 more)

### Community 94 - "test_knowledge_sync.py"
Cohesion: 0.07
Nodes (49): _api_key(), _auth_headers(), _build_digest_markdown(), create_wiki_page(), fetch_and_store(), get_knowledge_sync(), KnowledgeSync, _now_iso() (+41 more)

### Community 95 - "PersistentMemoryStore"
Cohesion: 0.07
Nodes (42): MemoryCategory, MemoryEntry, MemoryScope, PersistentMemoryStore, Any, Connection, Enum, Path (+34 more)

### Community 96 - "TokenBudget"
Cohesion: 0.07
Nodes (25): BudgetUsage, Any, Raise :class:`BudgetExceededError` if the session has exceeded its cap., Reset usage counters for *session_id* (cap is preserved)., Generate a token savings analytics report. Returns per-session statistics and…, Track and enforce per-session or per-agent token budgets. Usage:: budget =…, Set (or update) the token cap for *session_id*., Add token counts for *session_id*. If *response_text* is given and counts are… (+17 more)

### Community 97 - "KnowledgeScreen.jsx"
Cohesion: 0.03
Nodes (53): UI-first — an API is not "done", Phase 2 — Per-surface assignment in the UI (the "one place"), Phase 4 — Onboarding fixes (#593, #619, PR #623) ⏳, consultExecutives(), createCompany(), createProvider(), createWikiPage(), deleteProvider() (+45 more)

### Community 98 - "models/seo_audit.py"
Cohesion: 0.10
Nodes (22): Run the repo-aware auto-fixer against this company's workspace checkout.…, run_seo_fixes(), BaseModel, models/seo_audit.py - SEO / GEO / AIO Audit Contracts Typed Pydantic models for…, Snapshot of one crawled page with the on-page facts the checks used., Lightweight listing entry for past audits., Request to remediate auto-fixable findings in a local code repository., One concrete remediation performed (or proposed) by the fixer. (+14 more)

### Community 99 - "test_hermes_in_process.py"
Cohesion: 0.06
Nodes (32): _check_auth(), health(), Any, BaseModel, get, post, Execute a task synchronously via the InternalAgentAdapter (our brain). Response…, Body for POST /tasks — mirrors the payload HermesAdapter.execute sends. (+24 more)

### Community 100 - "ProviderConfig"
Cohesion: 0.04
Nodes (67): Record token usage for *model* (fire-and-forget, never raises). ``tag`` is a…, record_usage(), _exponential_backoff_cooldown(), is_commercial_provider(), _normalized_provider_type(), provider_access_tier(), _provider_field(), provider_sort_key() (+59 more)

### Community 101 - "E2BAdapter"
Cohesion: 0.03
Nodes (97): E2BAdapter, Any, runtimes/adapters/e2b.py — E2B Firecracker micro-VM runtime adapter. Routes…, Run ``pytest`` inside the sandbox. Returns ``(output, passed)``.…, Runtime adapter that executes tasks inside an E2B sandbox. Activation:…, Available iff config resolves AND the SDK is importable. Never raises — a…, e2b_status(), Return the E2B sandbox integration status for the ProvidersScreen badge. Does… (+89 more)

### Community 102 - "test_scanner_headless.py"
Cohesion: 0.03
Nodes (36): 5. Input Validation, _is_blocked_host(), Cheap (no-DNS) SSRF check for headless-browser subrequests. A rendered page's…, _guard(), Tests for the scanner's headless-render fallback (JS-rendered / bot-protected…, The scan flow must invoke the render fallback when static detection is empty…, BuiltWith-style off-site identification: a CNAME chain that points at a known…, A scan must never hang past its wall-clock budget — a slow/blocked domain has… (+28 more)

### Community 103 - "direct_chat.py"
Cohesion: 0.08
Nodes (50): Any, Translate technical preflight issues into a conversational assistant reply., translate_error_to_conversational(), AcceptedJob, AgentJobEnvelope, CompletedJob, DirectChatState, FailedJob (+42 more)

### Community 104 - "AgileSprint"
Cohesion: 0.06
Nodes (23): AgileSprint, An agile sprint containing user stories., Add a user story to the sprint., Remove a user story from the sprint., Total story points in the sprint., Completed story points., Return completed points history for burndown chart., Number of stories in the sprint. (+15 more)

### Community 105 - "job_manager.py"
Cohesion: 0.07
Nodes (25): make_isolated_workspace(), Path, agent/job_manager.py — Async agent job lifecycle manager. Manages agent jobs…, Create an isolated workspace directory under *root*. This is the legacy path…, _workspace_component(), _fake_user(), _FakeChatResult, _FakeResponse (+17 more)

### Community 106 - "BrowserSession"
Cohesion: 0.05
Nodes (29): BrowserAction, BrowserSession, _not_started(), PageState, Any, Which backend a start() would use: 'browserbase', 'local', or 'stub'., Evaluate a JavaScript expression in the page context., Return a summary of the current page state. (+21 more)

### Community 107 - "FinancialMetrics"
Cohesion: 0.13
Nodes (15): FinancialMetrics, Core financial metrics tracked monthly. All inputs are dollars/month. Methods…, Net monthly burn (cost minus revenue). Positive = losing money., How many months of cash remain at current burn., Gross margin = (revenue - COGS) / revenue. COGS is the sum of cost lines…, Sum of all cost lines (sanity check vs monthly_costs)., Tests for agents.financial_analyst — Agentic CFO., test_metrics_burn_rate() (+7 more)

### Community 108 - "LogWatcher"
Cohesion: 0.06
Nodes (27): _auto_file_enabled(), ErrorFingerprint, LogEntry, LogWatcher, A single error entry extracted from a log file., Generates stable fingerprints for error deduplication., Create a hash from error type, file, and normalized message pattern., Background daemon that monitors logs and creates GitHub issues for errors.… (+19 more)

### Community 109 - "asyncio"
Cohesion: 0.07
Nodes (21): _noop_async(), Any, asyncio, A probe exception must not break the Providers page., Never claim connected without measuring it., A stdio server isn't broken — the backend just can't dial it., Regression: github rendered red, sending operators after a non-bug. The…, The distinction must not swallow genuine faults. (+13 more)

### Community 110 - "OllamaCircuitBreaker"
Cohesion: 0.08
Nodes (36): _Circuit, _enabled(), _failure_threshold(), get_circuit_breaker(), OllamaCircuitBreaker, Per-model circuit breaker for Ollama backend health. Tracks consecutive failure…, Record a successful response; close the circuit., Record a 5xx error; open the circuit after threshold is reached. (+28 more)

### Community 111 - "Page"
Cohesion: 0.06
Nodes (36): _login_api(), main(), _navigate_auth_callback(), _navigate_logged_out(), Page, Navigate directly to the AuthCallback page with query params., Social login buttons on the LoginPage., Verify the login page renders. (+28 more)

### Community 112 - "portfolio_intelligence.py"
Cohesion: 0.06
Nodes (51): _bullets(), generate_backlog_retro(), generate_standup(), plan_next_sprint(), Agentic Agile — autonomous ceremonies (standup, retro, sprint planning). Where…, Render a :class:`Retrospective` as a markdown section., Derive a retrospective from the task tracker when no sprint is active. DONE /…, The result of allocating portfolio capacity into a new sprint. (+43 more)

### Community 113 - "Agent"
Cohesion: 0.06
Nodes (23): Agent, Grab Multi-Agent Support — Agent and TeamCoordinator with capability matching.…, Release a task from an agent., List all currently available agents., List agents with a capability, ordered by load., Average load across all team members., Number of agents in the team., An agent with capabilities and workload tracking. (+15 more)

### Community 114 - "tasks/api.py"
Cohesion: 0.12
Nodes (58): BackgroundTasks, add_comment(), approve_checkpoint(), approve_execution(), clarify_task(), create_task(), _current_user(), delete_task() (+50 more)

### Community 115 - "CEOLedger"
Cohesion: 0.08
Nodes (23): Attempt, _backend(), CEOLedger, GoalRecord, _now(), Any, One delegation of one subtask to one tier., One piece of work the CEO has taken ownership of. ``state`` is the supervisor's… (+15 more)

### Community 116 - "test_integration_c4_c5_c6_d3.py"
Cohesion: 0.10
Nodes (26): functools, get_current_trace_id(), get_tracer(), langfuse_metadata_with_trace(), otel_status_error(), otel_status_ok(), Portable trace context that can be passed across async boundaries., Return an OpenTelemetry tracer for the given name. (+18 more)

### Community 117 - "CompanyGraph"
Cohesion: 0.05
Nodes (22): BusinessCategory, CompanyGraph, SystemType, The complete Company Graph - canonical core model for the Autonomous AI Agency.…, Find a website by its URL., Find a repository by its URL., Find all systems of a specific type., Find specialists that can handle a task with given capabilities. (+14 more)

### Community 118 - "ToolRegistry"
Cohesion: 0.03
Nodes (42): get_tool_registry(), _infer_parameters_from_func(), Any, Path, Register a tool definition., Decorator to register a function as an agent tool. Usage::…, Remove a tool from the registry. Returns True if removed., Look up a tool by name. (+34 more)

### Community 119 - "ai_runner.py"
Cohesion: 0.08
Nodes (51): fcntl, append_checkpoint(), _build_claude_command(), cmd_audit(), cmd_changelog_check(), cmd_logs(), cmd_manifest(), cmd_resume() (+43 more)

### Community 120 - "_cfg"
Cohesion: 0.06
Nodes (21): _cfg(), _cost_table(), tests/test_daily_automation_2026_09_06.py — Daily automation tests…, Fable-tier ($10) must be more expensive than Opus-tier ($5)., Opus ($5) must be more expensive than Sonnet 5 ($2)., Sonnet 5 introductory price ($2/$10) is now the standard price (2026-09-01)., Haiku 4.5 is $1/$5 per MTok (not $0.80/$4.00 which was Haiku 3.5 pricing)., Fable 5, Fable 5.1, Opus 5, Mythos 5, Mythos 5.1 all have 1M context / 128K… (+13 more)

### Community 121 - "_llm_catalog"
Cohesion: 0.06
Nodes (20): _cost_table_src(), _llm_catalog(), tests/test_daily_automation_2026_09_19.py — Daily automation tests…, LLaMA 3.3 70B Turbo and Mixtral 8×7B v0.1 now have catalog entries., gemini-1.5-flash and gemini-1.5-pro now have catalog entries., All four Mistral API candidates now have catalog entries and cost rows., mistral-large should cost more than mistral-small., The check_model_catalog_consistency.py gate reports no drift. (+12 more)

### Community 122 - "Settings"
Cohesion: 0.05
Nodes (27): _get_settings(), Typed configuration loaded from environment variables., When True, the governance layer evaluates and audits agent actions. This is…, When True, approval-gated actions self-approve. Local dev only., ``RENDER_SERVICE_IDS`` split into a clean list (empty when unset)., When True, mutating Render MCP tools may be called. Default False., When True, agents may drive a real browser (agent/browser.py)., True when a Browserbase key is present — the low-RAM remote path. (+19 more)

### Community 123 - "BackgroundAgent"
Cohesion: 0.07
Nodes (31): BackgroundAgent, heartbeat(), BackgroundTask, _now(), Any, Enqueue *task* for processing. Returns the task (with task_id set)., Convenience: create a task and submit it in one call., Always-on worker that drains a task queue on a daemon thread. GATE: Golden Path… (+23 more)

### Community 124 - "os"
Cohesion: 0.01
Nodes (223): Browser admin UI for login, service control, key management, and diagnostics., ★7 Adaptive Loop Halting — velocity-based agent run termination. Complements…, _company_advisory_context(), agent/agency.py — Autonomous Agent Agency (CEO-driven, LLM-powered) Runs the…, Pull a compact company profile for the C-suite advisory, or None. Best-effort:…, agent/background.py — Background Agent An always-on worker thread that…, agent/browser.py — Browser Automation Controls a real browser via Playwright so…, Cached LLM Client wrapper. Drop-in wrapper around any LLM API call that… (+215 more)

### Community 125 - "test_vision_routing.py"
Cohesion: 0.12
Nodes (11): best_vision_model(), has_image_content(), ModelCapability, Model capability registry. Defines the known local models, their strengths, and…, # NOTE: suspended under US export-control directive as of 2026-06-12., Return the name of the best registered vision-capable model, or None. Prefers…, Return True if any message contains an image_url content part., Tests for vision request routing and session ID propagation. Covers: -… (+3 more)

### Community 126 - "heal_signature"
Cohesion: 0.07
Nodes (28): heal_signature(), HealState, Enum, str, Lifecycle of a heal (Autonomy Charter G2 closed loop)., Stable signature for an error/heal, used to dedup and detect recurrence.…, True when outbound Telegram sends must be suppressed. Tests must never page a…, _telegram_sends_suppressed() (+20 more)

### Community 127 - "test_pr_approval_gate.py"
Cohesion: 0.10
Nodes (11): _pr(), tests/test_pr_approval_gate.py — the green-PR Telegram approval sweep. Covers…, The card's buttons must parse to pr_merge / pr_reject with the PR number., test_card_keyboard_callback_data_parses_to_pr_actions(), TestPrIsGreen, TestRunSweep, get_check_runs(), list_open_prs() (+3 more)

### Community 128 - "_llm_catalog"
Cohesion: 0.06
Nodes (24): _brain_config_source(), _cost_tracker_source(), _llm_catalog(), tests/test_daily_automation_2026_09_18.py — Daily automation tests…, deepseek-flash catalog entry must have correct capabilities and pricing., brain_config.py hardcoded deepseek candidates must include deepseek-flash., cost_tracker.py must have deepseek-flash pricing., qwen/qwen3.8-27b must have a catalog entry with correct capabilities. (+16 more)

### Community 129 - "test_sqlite_store.py"
Cohesion: 0.05
Nodes (58): asyncio, tests/test_sqlite_store.py — Unit tests for the SQLite storage adapter. These…, The exact query shape backend/server.py's provider "Set default" uses: clear…, Unfiltered count uses the SELECT COUNT(*) fast path and must match the number…, estimated_document_count mirrors an unfiltered count_documents., db['tasks'] must work like db.tasks (motor exposes both)., TaskStore(db=SQLiteStore) must not raise 'not subscriptable'. This is the exact…, B608 guard: _Collection.__init__ must reject names outside _COLLECTIONS.… (+50 more)

### Community 130 - "AgentPlan"
Cohesion: 0.05
Nodes (45): Agent subsystem — planner / executor / verifier loop., AgentEvent, AgentPlan, AgentRunRequest, AgentSessionCreateRequest, AgentSessionMessage, AgentStep, _known_tool_names() (+37 more)

### Community 131 - "Command"
Cohesion: 0.06
Nodes (21): Command, CommandCategory, CommandDispatcher, Enum, SuperClaude Slash Commands — CommandDispatcher with registration, role gating,…, Parse and execute a slash command from raw text. Args: text: Raw command text,…, Return all enabled commands in a given category., Return all registered commands. (+13 more)

### Community 132 - "register_webui"
Cohesion: 0.10
Nodes (27): allow_paid_brain(), True only when the operator explicitly opted into a paid (Anthropic) brain.…, test_allow_paid_brain_default_false(), test_allow_paid_brain_opt_in(), _admin_out(), register_webui(), _admin_app_index(), _admin_app_spa() (+19 more)

### Community 133 - "persist_plan_spec"
Cohesion: 0.06
Nodes (43): build_spec_router(), approve_spec(), _decide(), get_spec_artifact(), list_spec_artifacts(), reject_spec(), Any, APIRouter (+35 more)

### Community 134 - "frontend/package.json"
Cohesion: 0.04
Nodes (54): browserslist, development, production, dependencies, axios, fast-uri, livekit-client, lucide-react (+46 more)

### Community 135 - "test_context_rulebook.py"
Cohesion: 0.06
Nodes (53): Module, stmt, _bound_names(), _good_result(), _guard_statements(), _load(), ModuleType, parametrize (+45 more)

### Community 136 - "TestAdapterMetadata"
Cohesion: 0.05
Nodes (21): N2. Surface Hermes (and all runtimes) status in the Doctor/Runtimes UI ⬜  (size: S, risk: low), _env_float(), HermesAdapter, Any, AsyncClient, Read a float env var, falling back to *default* on unset/garbage., Adapter for Hermes Agent — FIRST CLASS autonomous runtime., parametrize (+13 more)

### Community 137 - "workflow_orchestrator.py"
Cohesion: 0.07
Nodes (52): contextvars, BoundContext, ClassifyOutput, ExecutionResult, JudgeVerdict, MergeDecision, MonitorOutput, _orchestrator_bypass() (+44 more)

### Community 138 - "ArtifactStore"
Cohesion: 0.06
Nodes (26): TestTeamSummary, Path, tests/test_artifact_store.py — Unit tests for workflow/artifact_store.py., Verify artifacts that are stored as JSON (e.g., CheckRun results)., Writing the same (run_id, name) twice should update, not duplicate., store(), TestArtifactStoreDeletion, TestArtifactStoreJSONArtifact (+18 more)

### Community 139 - "_StubProvider"
Cohesion: 0.06
Nodes (30): _models_to_try(), Order the models to attempt on *provider*, correcting a stale catalogue. Cache-…, _mock_get(), _ok(), _handler(), asyncio, parametrize, A stale model catalogue must not be mistaken for a dead account.… (+22 more)

### Community 140 - "test_response_cache.py"
Cohesion: 0.12
Nodes (47): _cache_key(), cache_stats(), clear_cache(), get_cached(), is_cacheable(), put_cached(), Any, packages/ai/response_cache.py — LRU+TTL in-memory response cache for the… (+39 more)

### Community 141 - "test_llm_router_e2e.py"
Cohesion: 0.09
Nodes (52): _ok(), parametrize, End-to-end routing against mock providers (ADR-008). These are the tests that…, A router wired to three mock providers, with all singletons isolated., Two keys on alpha means a 429 costs a key, not the provider., The NVIDIA 410 incident, as a regression test (CLAUDE.md §7)., A 422 is the request's fault — trying five providers just adds latency., A 413 is one provider's context window, not a fact about the request. The… (+44 more)

### Community 142 - "test_trend_watcher.py"
Cohesion: 0.06
Nodes (33): _FakeClient, _FakeResp, asyncio, Tests for agent/trend_watcher.py, Ensure expanded keyword set covers key new categories., A release is scored by its notes, never the old blanket 0.95 that let five…, Only the newest release is force-surfaced; older routine patch releases in the…, A routine latest release still surfaces (our niche) but is informational — not… (+25 more)

### Community 143 - "WorkspaceManager"
Cohesion: 0.05
Nodes (20): Agent jobs created with workspace integration should have a workspace_path…, Only expired workspaces (past retention TTL) are cleaned up., Two threads creating the same session/job should not corrupt state., TestConcurrency, TestCrossSessionIsolation, TestWorkspaceCleanup, TestWorkspaceLifecycle, TestWorkspaceManifest (+12 more)

### Community 144 - "InferenceCache"
Cohesion: 0.17
Nodes (8): CachedLLMClient, Return performance metrics for this client instance., Wraps an LLM call function with inference caching. Usage: from agent.cached_llm…, InferenceCache, Pre-populate the cache with known prompt→response pairs. Useful for seeding…, Build a messages list optimized for KV/prefix caching. Best practice from…, Extract the stable prefix (system + early turns) from a message list. The…, LLM Inference Cache with exact-match and TTL support. Key design decisions…

### Community 145 - "checkpoint.py"
Cohesion: 0.14
Nodes (18): Checkpoint, checkpoint_agent_state(), _checkpointing_enabled(), cleanup_checkpoints(), _get_checkpoint_store(), Any, Durable agent checkpointing for crash-recovery and resumption. Provides…, Return the process-wide singleton CheckpointStore. (+10 more)

### Community 146 - "test_contracts_agency.py"
Cohesion: 0.05
Nodes (26): AutonomyCounter, AutonomySnapshot, AutonomyTracker, get_tracker(), Any, Return a point-in-time snapshot of all KPIs., Reset all counters (test helper)., Return the shared AutonomyTracker singleton (lazy-init). (+18 more)

### Community 147 - "ensure_self_company"
Cohesion: 0.06
Nodes (34): _count_specialists(), _create_company_directly(), ensure_self_company(), _find_self_company(), _find_stale_self_companies(), _list_companies_safe(), Self-onboarding bootstrap. On startup the platform registers *itself* as a…, List companies, skipping any that fail to deserialize. A previous deploy wrote… (+26 more)

### Community 148 - "ContextManager"
Cohesion: 0.08
Nodes (28): ContextManager, estimate_tokens(), FitResult, message_tokens(), prune(), Any, Truncate oversized tool results and drop exact duplicate turns. Tool results…, Keep system messages, the first turn, and the newest turns that fit. Returns… (+20 more)

### Community 149 - "TestHarnessAdapter"
Cohesion: 0.06
Nodes (15): get_harness_adapter(), harness_active(), harness_catalog(), #522 + #505: Reliability startup — schedule hydration, orchestrator restore,…, Return the full ECC harness catalog with capabilities. Public — no auth…, Return the currently active ECC harnesses with session metrics. Authenticated —…, _startup_reliability_hooks(), get_harness_registry() (+7 more)

### Community 150 - "test_governance_api.py"
Cohesion: 0.04
Nodes (56): Resolve the JWT signing secret, with a *stable* fallback. Bug fix: the previous…, _resolve_jwt_secret(), AuditEvent, One governed action, fully described. Field order follows the…, One-line JSON, suitable for a SIEM shipper tailing the log., Replace the process-wide gate. Tests only., reset_gate(), _client() (+48 more)

### Community 151 - "KimiBrowserDriver"
Cohesion: 0.14
Nodes (9): lifespan(), FastAPI, KimiBrowserDriver, Poll the page until the streaming response is complete, then return its text., Manages a single persistent Chromium context pointing at kimi.com., Launch a persistent Chromium context (headless by default)., Open Kimi in headed mode so the operator can log in once. After logging in,…, Submit a conversation to Kimi and return the assistant reply as plain text.… (+1 more)

### Community 152 - "test_issue_intake.py"
Cohesion: 0.08
Nodes (47): _capability_tags(), create_task_from_oldest_open_issue(), intake_issue(), _issue_labels(), issue_source_id(), map_issue_to_task(), Any, tasks/issue_intake.py — Auto issue → Task intake (Autonomy Charter G3) Turns… (+39 more)

### Community 153 - "WorkflowRun"
Cohesion: 0.06
Nodes (38): N4. Promote CRISPY from EXPERIMENTAL → stable after burn-in 🟡 (size: M, risk: medium — `risky-module-review`), engine(), _fake_artifact(), _make_engine(), tests/test_crispy_workflow.py — CRISPY workflow engine hardening tests. Tests…, Provide isolated DB + artifact + workspace paths., Create a WorkflowEngine with isolated storage., TestAbortOnFailure (+30 more)

### Community 154 - "_cfg"
Cohesion: 0.06
Nodes (18): _cfg(), tests/test_daily_automation_2026_08_25.py — Daily automation tests…, Mythos-class models should be priced above Opus 5., Fable 5 is more capable than Opus 5, so lower priority number., Verify the claude-mythos-5 entry in config/llm/models.yaml., Same underlying model — pricing must be identical., Cross-check that models known to the router registry are in models.yaml., Paid Anthropic models must have a non-zero output cost. (+10 more)

### Community 155 - "ReactScratchpad"
Cohesion: 0.06
Nodes (22): Declarative configuration for a specialized sub-agent role. Each sub-agent gets…, SubAgentConfig, build_react_prompt(), parse_react_response(), Any, Parse a ReAct-format response into structured components. Intended caller:…, Structured scratchpad that accumulates across tool calls within a step. Each…, Record a reasoning step before taking action. (+14 more)

### Community 156 - "RepowiseIntelligence"
Cohesion: 0.04
Nodes (46): Any, Path, Build symbol-level dependency graph for Python files., Build git intelligence: hotspots, ownership, co-change pairs., Run a git command and return stdout as string., Compute cyclomatic complexity for Python files. Returns 0 for non-Python files…, Extract docstrings and store as documentation., Get the latest commit hash. (+38 more)

### Community 157 - "resolve_provider_for"
Cohesion: 0.06
Nodes (38): _get_provider_policy(), Read the durable provider policy from DB, falling back to a safe default.…, Resolve the LLM endpoint for a named surface (task/chat/ceo/sdlc/…). Honours…, _prio(), resolve_provider_for(), asyncio, tests/test_provider_policy.py — Unit tests for the paid-provider kill switch.…, ProviderPolicyUpdate defaults allow_paid to False. (+30 more)

### Community 158 - "clear_cooldowns"
Cohesion: 0.05
Nodes (47): clear_cooldowns(), _dead_model_key(), _is_model_dead(), is_provider_on_cooldown(), mark_provider_failed(), Put provider_id on cooldown for *cooldown_seconds* (default:…, Return True if provider_id is currently on cooldown., Clear all cooldown entries (useful for testing). Delegates to… (+39 more)

### Community 159 - "Event"
Cohesion: 0.33
Nodes (6): Event, publish(), An event published on the bus., Subscribe to an event type., Publish an event to all subscribers., subscribe()

### Community 160 - "brain_failover.py"
Cohesion: 0.05
Nodes (54): Any, Force the next ``list_tools()`` call to fetch a fresh tool list from the…, brain_providers(), Every configured provider with its health AND its on/off state. Powers the…, Added, Added, BarChart(), CEOCyclePanel() (+46 more)

### Community 161 - "ChatHistoryStore"
Cohesion: 0.07
Nodes (25): ChatHistoryStore, Any, Connection, Delete a session and all its messages. Returns True if deleted., List sessions ordered by most recently updated., Return total session and message counts., Append a message to the session. Returns the message's sequence number.…, Append multiple messages at once. Returns number of messages appended. (+17 more)

### Community 162 - "_step"
Cohesion: 0.06
Nodes (22): _job(), parametrize, Path, quick_note(), The autonomous pipeline must not treat "I could not tell" as "yes". Every…, `--missing-ok` is correct for an unplanned issue and wrong otherwise., `continue-on-error: true` means a crash must be its own state., Waiting is not reviewing. (+14 more)

### Community 163 - "RewardScorer"
Cohesion: 0.08
Nodes (18): _nvidia_api_key(), BaseModel, Score a response against a prompt using the Nemotron reward model. Returns a…, Call the NVIDIA NIM reward endpoint and return the score. The Nemotron reward…, Parse the reward score from the model's JSON response., Result of a single reward model scoring operation., Scores agent step outputs using the Nemotron-4-340B-Reward model. The reward…, True when the reward model is configured and reachable. (+10 more)

### Community 164 - "QuickNoteQueue"
Cohesion: 0.06
Nodes (39): _fetch_text(), __init__(), _now(), process_note(), Any, Path, QuickNote, QuickNoteQueue (+31 more)

### Community 165 - "FeatureMaturity"
Cohesion: 0.07
Nodes (28): __init__.py — Feature flag/matrix package., FeatureMaturity, get_feature_matrix(), Enum, str, Feature maturity classification., Return the global FeatureMatrix singleton., Reset the singleton (useful for testing). (+20 more)

### Community 166 - "telegram_bot.py"
Cohesion: 0.03
Nodes (108): _configure(), _default(), main(), Entry point for the always-on FreeBuff Telegram bot (Render worker / Docker).…, Set an env var only when the operator hasn't already provided one., _admin_headers(), _answer_callback(), _api_headers() (+100 more)

### Community 167 - "WorkflowEngine"
Cohesion: 0.09
Nodes (25): Any, Connection, Path, PhaseType, CRISPY workflow engine — phase sequencer + gate controller. GATE: Golden Path…, Return the AgentSwarm singleton if available, else None., Append an event to the workflow event log., Create a new WorkflowRun and begin pre-gate phase execution. The run is… (+17 more)

### Community 168 - "PortfolioManager"
Cohesion: 0.05
Nodes (31): _env_github_token(), PortfolioIntelligence, Path, Assembles a PortfolioManager from live signals with WSJF scoring., PortfolioManager, Manages a portfolio of initiatives with WSJF prioritisation and roadmapping., Remove an initiative from the portfolio., Number of initiatives in the portfolio. (+23 more)

### Community 169 - "RequestQueue"
Cohesion: 0.07
Nodes (21): Deduplicator, T, Collapse concurrent identical calls onto a single execution., Execute ``factory``, or await an identical call already running. Returns…, One job waiting for a concurrency slot, ordered by (priority, arrival)., Bounded priority queue with concurrency limits and backpressure. Admission is…, Run ``job`` under the queue's concurrency limit. Raises ``QueueFull``…, Wait for a slot, yielding to higher-priority work already queued. (+13 more)

### Community 170 - "SchedulesScreen.jsx"
Cohesion: 0.17
Nodes (12): createSchedule(), pauseSchedule(), resumeSchedule(), triggerSchedule(), CAT_CONFIG, errText(), NewJobForm(), normalizeJob() (+4 more)

### Community 171 - "diagnostics.py"
Cohesion: 0.07
Nodes (46): _check_background_liveness(), _check_ci_parity(), _check_company_graph(), _check_disk(), _check_event_log_integrity(), _check_feature_matrix(), _check_github_readiness(), _check_ollama() (+38 more)

### Community 172 - "test_e2b_task_wiring.py"
Cohesion: 0.08
Nodes (40): _build_coordinator(), _FakeCompany, _FakeCompanyGraphStore, _FakeRepoConnection, _make_task(), tests/test_e2b_task_wiring.py — Task.company_id → spec.context repo_url wiring.…, No company_id → spec.context has no repo_url (legacy path)., company_id set but E2B off → spec.context unchanged (no company repo wiring). (+32 more)

### Community 173 - "activation_api.py"
Cohesion: 0.04
Nodes (92): activation_required(), ActivationResult, activate_instance(), ActivateRequest, ActivateResponse, activation_audit_log(), activation_status(), ActivationStatusResponse (+84 more)

### Community 174 - "MCPClient"
Cohesion: 0.06
Nodes (22): MCPClient, Any, Thin async MCP client with open/close circuit breaker. Thread-safe only within…, Full URL of the JSON-RPC endpoint this client posts to., Build the request headers shared by ``_rpc`` and ``notify``. ``Accept`` lists…, Attach the agent identity whose actions this client executes., Send a JSON-RPC notification (no ``id``, no response body expected). Used for…, Return the list of tools available on the MCP server. Implements tools/list TTL… (+14 more)

### Community 175 - "seo_api.py"
Cohesion: 0.08
Nodes (42): build_seo_roadmap(), delegate_seo_findings(), export_seo_audit(), get_seo_audit(), list_seo_audits(), plan_seo_sprint(), BaseModel, get (+34 more)

### Community 176 - "KeyStore"
Cohesion: 0.07
Nodes (38): 1. Authentication & Authorization, API Key Authentication, JWT / Token Auth, Category 2 — API Key Naming Confusion, TD-005 [MEDIUM] — Production Keys Have `test-key-` Prefix, _check_rate_limit(), default_keys_path(), issue_new_api_key() (+30 more)

### Community 177 - "AdminIdentity"
Cohesion: 0.05
Nodes (21): Admin Authentication, Start the FastAPI proxy server., ServiceManager, AdminAuthManager, AdminIdentity, AdminSession, AdminSessionStore, _is_truthy() (+13 more)

### Community 178 - "test_llm_router_disabled.py"
Cohesion: 0.10
Nodes (33): auto_disable(), _billing_signals(), describe(), disabled_provider_ids(), is_unfixable(), packages/llm/disabled.py — bridge to the durable provider on/off switch. The…, Provider ids currently switched off. Empty when the store is unreachable., Persist a provider as disabled, through the store that already owns it. (+25 more)

### Community 179 - "TaskDispatcher"
Cohesion: 0.04
Nodes (28): Polls for queued task work and executes it through the coordinator. Crash…, Re-queue tasks stranded by a prior crash or hard-kill., TaskDispatcher, tests/test_fixes_reliability.py — Regression tests for the batch of fixes.…, Dispatcher should track first_seen times for pending tasks., Executing a task removes it from _first_seen and logs pickup time. Uses async…, DashboardHome.js must use Promise.allSettled() not Promise.all(). Promise.all()…, TestDashboardPartialFailure (+20 more)

### Community 180 - "ContextWindowManager"
Cohesion: 0.08
Nodes (21): ContextWindowManager, get_context_window_manager(), Any, Enum, Return True if the estimated tokens exceed the model's context limit., Truncate messages to fit within the model's context window. Args: messages:…, Return the context window size for a model. Looks up the model in the…, Estimate token count for a list of messages. Uses a character-based heuristic… (+13 more)

### Community 181 - "_cfg"
Cohesion: 0.07
Nodes (12): _cfg(), _cost_table(), tests/test_daily_automation_2026_09_13.py — Daily automation tests…, 3.8 Flash should have higher priority (lower number) than 3.7 Flash., Gemini 3.x models must have pricing entries in the cost table., Kimi K2 and QwQ-32B must have catalog entries so the router includes them., CLAUDE.md must no longer reference the deprecated deepseek-r1-70b as the Groq…, Gemini 3.x models must be declared with correct capability flags. (+4 more)

### Community 182 - "test_e2b_data_flow.py"
Cohesion: 0.06
Nodes (25): services, fake_sandbox(), _FakeAsyncSandboxClass, _FakeCmdResult, _FakeCommands, _FakeFiles, _FakeSandbox, Any (+17 more)

### Community 183 - "test_portfolio_intelligence.py"
Cohesion: 0.05
Nodes (19): FakeResp, asyncio, Tests for agents/portfolio_intelligence.py — autonomous signal → initiative.…, DEFAULT_REPO was hardcoded to the stale pre-rename repo name…, fetch_github_signals must degrade gracefully (log + return empty lists) on a…, Even with a 200, a malformed/rate-limited body that isn't a list must not be…, fetch_research_alerts used asyncio.run() to await TrendWatcher().fetch(), which…, The exact scenario that crashed before the fix: called from code that is itself… (+11 more)

### Community 184 - "urllib_parse"
Cohesion: 0.07
Nodes (34): _build_curl_cffi_fetcher(), get(), get_text(), head(), _sess(), _build_pdf(), findings_block(), hr() (+26 more)

### Community 185 - "looks_like_secret_file"
Cohesion: 0.05
Nodes (59): onboarding_gate_enabled(), Async read of the gate default straight from the DB., Removed, Removed, Removed, Removed, 0. The goal (unchanged), 1. Shipped in the previous pass ✅ (recap, do not redo) (+51 more)

### Community 186 - "WorkflowBuildRequest"
Cohesion: 0.07
Nodes (32): Contract: WorkflowEngine cannot skip the gate state machine., Contract: No code path may advance past awaiting_approval unless gate.status ==…, Create a run and manually place it in awaiting_approval., Contract: Cannot approve a run in 'pending' state., Contract: Can approve a run in 'awaiting_approval' state., Contract: Rejecting a run marks it as failed., TestApprovalGateMandatory, do_approve() (+24 more)

### Community 187 - "_run"
Cohesion: 0.06
Nodes (16): ``_resolve_reply_to_decision`` returns the durable link from SQLite.\n, ``/redirect`` command: admin-only, prefix-dispatched, idempotent shape., ``/paste <abs-path>`` command: admin gate + path check + truncation., ``_handle_big_paste`` writes to disk and short-replies., ``_route_plain_text`` classifies and dispatches per the documented map., Return a Telegram nested-message-shaped dict for resolve-reply-to tests., Lower-level smoke tests for inbound_router plumbed through tih calls. These…, _run() (+8 more)

### Community 188 - "WindowsServiceManager"
Cohesion: 0.19
Nodes (6): _creationflags(), CompletedProcess, Path, Spawn a new proxy process on Linux/Mac using the current Python interpreter., ServiceState, WindowsServiceManager

### Community 189 - "KnowledgeGraph"
Cohesion: 0.08
Nodes (17): KnowledgeGraph, KnowledgeNode, Find all connected components (treating edges as undirected)., Find all nodes with a given tag., Export all edges as (source, target, edge_type) tuples., Number of nodes in the graph., Number of edges in the graph., A node in the knowledge graph representing a concept or fact. (+9 more)

### Community 190 - "ProvidersScreen.jsx"
Cohesion: 0.08
Nodes (24): Modified files, getBrainConfig(), getBrainProviders(), patchBrainConfig(), setBrainProviderEnabled(), syncProviderToRender(), testBrainModel(), BrainCard() (+16 more)

### Community 191 - "Workspace"
Cohesion: 0.08
Nodes (14): Any, Path, Run a shell command inside the workspace via an explicit shell binary., Resolve rel against root, reject path traversal., Run a subprocess. Never uses shell=True., Manages a single isolated workspace directory., Canonical root path (follows macOS /var → /private/var symlinks)., Clone repo_url into this workspace. Injects token from env if available. (+6 more)

### Community 192 - "test_failover_silent_exhaustion.py"
Cohesion: 0.06
Nodes (21): _FM, _P, Regression tests for a chain that fails silently. From a real incident:…, Reserve logic must never break the chain it is meant to protect., The incident case: providers ran, none reported a reason., The genuinely-empty chain keeps its original, correct wording., Each cause must read differently, or diagnosis is guesswork., A reserve held for an unreachable provider starves the free tier.… (+13 more)

### Community 193 - "run-claude-code.py"
Cohesion: 0.11
Nodes (13): platform, main(), OsDetector, Detect operating system and available interpreters., Return normalized OS name., Detect PowerShell (Windows) or Bash (Unix)., Print colored message., Cross-platform Claude Code launcher for local models. Auto-detects OS and runs… (+5 more)

### Community 194 - "test_runtime_governance.py"
Cohesion: 0.09
Nodes (52): governance_enabled(), True when the governance layer should run at all. A single global off switch…, _audit_dispatch(), _blocked_result(), _governance_check(), _governance_identity(), runtimes/routing.py — RuntimeRoutingPolicyEngine. Implements the 8-step routing…, Build the failed TaskResult returned when policy denies a dispatch. A result… (+44 more)

### Community 195 - "NotificationDispatcher"
Cohesion: 0.04
Nodes (46): Acceptance criteria, Design, Objective, Part B — G2: Closed-loop self-heal feedback, Tech stack / touch points, Tests, To-dos (checklist), NotificationDispatcher (+38 more)

### Community 196 - "FreeBuffAgent"
Cohesion: 0.06
Nodes (46): free_nvidia_models(), FreeBuffAgent, _nvidia_api_key(), Return the curated list of free NVIDIA NIM models FreeBuff may use., Codebuff-style coding agent pinned to free NVIDIA NIM models. FreeBuff is a…, List the free NVIDIA NIM models a user may pick (e.g. via Telegram)., True when *model* is in the curated free NVIDIA NIM set., Coerce *requested* to a free NVIDIA model. Returns *requested* when it is… (+38 more)

### Community 197 - "PromptCacheManager"
Cohesion: 0.06
Nodes (20): CacheEntry, CacheStats, get_prompt_cache(), PromptCacheManager, Any, Compute a deterministic cache key from the stable prefix. The stable prefix is…, Hash a system prompt and model for KV cache fingerprinting., Return the instance ID that has this prefix cached, or None. Performs an LRU… (+12 more)

### Community 198 - "TestCatalogFable51"
Cohesion: 0.12
Nodes (10): _cfg(), _cost_table(), tests/test_daily_automation_2026_09_04.py — Daily automation tests…, Verify that cost_tracker prices match models.yaml for the Fable family., claude-fable-5 is in the tracker and priced at the official $10/$50 rate., Verify the claude-fable-5-1 entry in config/llm/models.yaml., 5.1 is the newer release, so it should be preferred over 5.0., Must be listed in ADAPTIVE_THINKING_MODELS so temperature is suppressed. (+2 more)

### Community 199 - "_job_text"
Cohesion: 0.05
Nodes (26): _job_text(), Guards on ``.github/workflows/dependabot-auto-merge.yml``. Three separate gates…, `unknown` must be handled like `major`, never waved through., The classifier is a repo script, so the job needs a checkout., A sweep that cannot keep up with Dependabot is not a fix. Branch protection…, Daily could never catch up: ~14 PRs arrive weekly, 7 would drain., Refreshing the rest burns two CI runs each and merges none of them. Asserted…, A conflicted PR is neither BEHIND nor mergeable, so it falls through. Without… (+18 more)

### Community 200 - "test_video_transcript.py"
Cohesion: 0.05
Nodes (34): parametrize, Tests for video transcript extraction (`.github/scripts/video_transcript.py`).…, Events without `segs` carry no text and must not produce stray spaces., This format double-encodes: `&amp;#39;` must resolve to a single quote., Regex-terminated matching truncates this; brace matching must not. The blob…, A title containing a brace must not unbalance the matcher., An unfamiliar page shape must yield empties, never raise., A non-video URL must short-circuit before any request is attempted. (+26 more)

### Community 201 - "PreflightReport"
Cohesion: 0.06
Nodes (33): PreflightIssue, PreflightReport, BaseModel, doctor.py — Agent-side doctor diagnostics: environment, provider, and workspace…, test_specialized_runtime_execution(), check_all(), execute(), readiness_check() (+25 more)

### Community 202 - "WorkspaceTools"
Cohesion: 0.03
Nodes (75): CLAUDE.md — agent/, Skills worth invoking here, Testing, What this package does, Path, Return the first *lines* lines of a file. Just-in-time retrieval: the executor…, Return a lightweight index of files with line counts and sizes. This is the…, Delegate to RepowiseIntelligence for a natural-language codebase question. (+67 more)

### Community 203 - "test_audit.py"
Cohesion: 0.07
Nodes (38): AuditMessage, AuditSession, create_session(), delete_session(), get_session(), list_sessions(), Any, A single message in an audit session. (+30 more)

### Community 204 - "anthropic_compat.py"
Cohesion: 0.07
Nodes (37): _build_anthropic_response(), _emit_safely(), _finish_reason_to_stop_reason(), get_local_model(), handle_anthropic_messages(), _messages_to_openai(), _openai_choice_to_anthropic_content(), _post_anthropic_with_fallback() (+29 more)

### Community 205 - "test_classify_dependabot_update.py"
Cohesion: 0.07
Nodes (28): classify(), classify_pull_request(), compare_versions(), _component(), is_auto_mergeable(), main(), parse_version(), Return the update type for a Dependabot PR. *branch* is ``headRefName``;… (+20 more)

### Community 206 - "compare_runtimes.py"
Cohesion: 0.11
Nodes (17): compare(), main(), Any, scripts/compare_runtimes.py — head-to-head runtime comparison. Answers the…, Check an operator-supplied task file before anything executes., render(), _run_one(), RunRecord (+9 more)

### Community 207 - "WorkspaceManifest"
Cohesion: 0.08
Nodes (24): _derive_workspace_root(), WorkspaceStatusLiteral, Create an isolated workspace for a session and optional job. Creates the…, Retrieve the WorkspaceManifest for a given session and optional job. Looks up…, List all known workspaces, optionally filtered by status., Mark a workspace as active (in-use)., Pause a workspace (e.g. between agent steps)., Mark a workspace as completed. (+16 more)

### Community 208 - "asyncio"
Cohesion: 0.12
Nodes (16): _FakeMemory, asyncio, Return an async llm that yields queued replies and records calls., _recording_llm(), test_advise_consults_selected_execs_and_synthesizes(), test_advise_is_fail_soft_when_a_voice_errors(), test_advise_single_exec_needs_no_synthesis(), test_advise_unknown_role_is_dropped() (+8 more)

### Community 209 - "test_operational_incidents.py"
Cohesion: 0.02
Nodes (112): _diagnose_and_file(), _file_incident(), _format_incident(), gather_render_evidence(), get_operational_incident_tracker(), _iso_from_monotonic(), normalise(), _now() (+104 more)

### Community 210 - "langfuse_obs.py"
Cohesion: 0.16
Nodes (23): CommercialEquivalent, estimate_commercial_equivalent_usd(), get_prices(), _load_from_env(), _parse_mapping(), Any, Map each local Ollama model name to a commercial API reference price (USD per…, _base_url() (+15 more)

### Community 211 - "MetricsRegistry"
Cohesion: 0.09
Nodes (17): _Counter, _escape(), _Gauge, _Histogram, _labels(), MetricsRegistry, Any, All router metrics, renderable as Prometheus text. (+9 more)

### Community 212 - "ScheduledJob"
Cohesion: 0.03
Nodes (43): _age_seconds(), Any, Reconstruct a ScheduledJob from its as_dict() output., Fire a job immediately (webhook / manual trigger)., Enable or disable a job without deleting it., Attach a durable store and immediately rehydrate from it (#505). Called at…, Async variant of :meth:`attach_persistence` for callers already on an event…, Sync entry-point for attach_persistence(); delegates to hydrate(). With no… (+35 more)

### Community 213 - "TaskStatus"
Cohesion: 0.03
Nodes (147): agent/workflow.py — Persisted workflow state machine. Implements the Autonomous…, _env_flag(), Read a boolean env var. Accepts 'true'/'1'/'yes' (case-insensitive)., Helpers that turn scheduler and playbook activity into real tasks., Background dispatcher for task execution., tasks — Task/issue management system. Provides a lightweight task/issue tracker…, _coerce_ts(), Enum (+139 more)

### Community 214 - "test_agent_tool_governance.py"
Cohesion: 0.05
Nodes (55): Replace the process-wide store. Tests only., reset_approval_store(), AuditLog, Bounded in-memory ring buffer plus a structured log stream. The ring buffer…, Store and emit *event*. Never raises., Return the most recent events, newest first, optionally filtered., Aggregate view for the dashboard and the metrics endpoint. ``would_block`` is…, Replace the process-wide audit log. Tests only. (+47 more)

### Community 215 - "ProviderRouter"
Cohesion: 0.05
Nodes (33): build_tool_calling_router(), Return a router limited to providers that pass ``tools`` through intact. The…, ProviderRouter, Priority-ordered LLM provider fallback with health checks and retries., main(), probe_one(), Live probe — makes a tiny real API call to every configured provider. Usage (in…, _bedrock_api_response() (+25 more)

### Community 216 - "test_features_api.py"
Cohesion: 0.05
Nodes (4): _auth_override(), client(), _fake_auth(), Integration tests for all new feature API routes in proxy.py.

### Community 217 - "portfolio_api.py"
Cohesion: 0.08
Nodes (38): add_initiative(), AllocationOut, BoardOut, get_board(), get_service(), InitiativeIn, InitiativeOut, _materialize_and_log() (+30 more)

### Community 218 - "Part A — CodeRabbit review fixes for this PR (do first, small)"
Cohesion: 0.07
Nodes (28): A1 — `docs/changelog.md`: add the two autonomy docs under `### Added` ✅ trivial, A2 — `docs/telegram-bot.md`: fix broken charter links (MD + path), A3 — `docs/telegram-bot.md`: add language to fenced block (MD040), A4 — `.env.example`: use exact var name in the shortcut comment, A5 — `services/workflow_orchestrator.py`: surface notify failures at WARNING, A6 — `telegram_bot.py`: avoid double-approve in the `wfo_approve` path ⚠️ behavioural, A7 — `telegram_service.py`: escape Markdown-v1 reserved chars in approval text ⚠️ correctness, A8 — `render.yaml`: propagate Telegram vars to the worker service (+20 more)

### Community 219 - "Docker Agent Runtimes Setup"
Cohesion: 0.07
Nodes (27): Access from LLM Relay Dashboard, Access via REST API, Add More Runtimes, Advanced, Architecture, Check Service Health, Configuration, Direct HTTP Calls to Runtime (+19 more)

### Community 220 - "TaskBoardScreen.jsx"
Cohesion: 0.06
Nodes (38): Key files, addTaskComment(), approveTaskCheckpoint(), approveTaskExecution(), clarifyTask(), createSprint(), createTask(), escalateTask() (+30 more)

### Community 221 - "TestRecordUsageAndStats"
Cohesion: 0.05
Nodes (10): Tests for packages/ai/cost_tracker.py — per-model cost attribution. Covers: -…, Verify all Opus models referenced by brain_config are priced., A repeated key in a dict literal is silent: the later value wins. Found on…, TestClaudeOpusModelCoverage, TestClearStats, TestCostForTokens, TestEnvOverrides, TestGetCostTable (+2 more)

### Community 222 - "AgentScheduler"
Cohesion: 0.03
Nodes (78): gc, AgentScheduler, Register, list, trigger, and delete cron-scheduled agent jobs. Usage:: sched =…, Remove a job. Returns *True* if it existed., Delete EVERY schedule from the durable store and in-memory state. Operator…, #505: Remove a job from durable storage., APScheduler fires jobs from a background thread with no event loop. Pre-fix:…, test_scheduler_attach_main_loop_and_fire_from_thread() (+70 more)

### Community 223 - "get_store"
Cohesion: 0.07
Nodes (26): Short label for TUI display: {NAME}:{model}, _bootstrap_within_budget(), _create_bootstrap_indexes(), ensure_bootstrap(), The task store the background services should use, wiring it if needed.…, Point the feature stores at the shared database connection. Deliberately…, Create every boot index concurrently rather than one round-trip at a time.…, Idempotent bootstrap for indexes + seeded admin/providers. FastAPI startup… (+18 more)

### Community 224 - "test_verification_strategies.py"
Cohesion: 0.06
Nodes (42): agent, cross_verify(), Any, race(), Heuristic fallback score when the reward model is unavailable.…, Run *n* independent attempts at *instruction* concurrently; return the winner.…, True if any path matches the repo's risky-module trigger list., Have an independent agent re-check a completed task's changed files. Returns… (+34 more)

### Community 226 - "Persistent Memory System"
Cohesion: 0.05
Nodes (41): 1. **Semantic Memory Categorization**, 1. **Use Appropriate Scopes**, 2. **Prioritize Effectively**, 2. **Scope-Based Auto-Loading**, 3. **Priority-Based Retrieval**, 3. **Use Semantic Categories**, 4. **Cross-Tool Compatibility**, 4. **Tag Liberally** (+33 more)

### Community 227 - "test_agent_free_brain.py"
Cohesion: 0.06
Nodes (30): livenim, Resolve the free NVIDIA NIM brain from env, or ``None`` if unconfigured.…, resolve_free_nvidia_brain(), _FakeAsyncClient, _FakeResponse, _free_env(), Free-brain policy regression tests for the agent runtime (issue #656).…, The core #656 regression: an Anthropic-shaped model must NOT hit… (+22 more)

### Community 228 - "test_anthropic_router.py"
Cohesion: 0.08
Nodes (10): _make_anthropic_provider(), _payload(), Tests for Anthropic-specific router features. Covers: - Prompt caching…, Adaptive-thinking Claude models 400 on temperature / legacy thinking. The…, TestAnthropicPayloadExtendedThinking, TestAnthropicPayloadModelGuards, TestAnthropicPayloadPromptCaching, TestAnthropicToOpenAICacheUsage (+2 more)

### Community 229 - "AgentSessionStore"
Cohesion: 0.10
Nodes (16): AgentSession, AgentSessionStore, _now(), Connection, Path, Row, Safe getter for sqlite3.Row — Row supports index access but not .get()., Create a session with a caller-supplied session_id (useful for tests and… (+8 more)

### Community 230 - "BudgetTracker"
Cohesion: 0.08
Nodes (24): AlertHandler, BudgetTracker, Counter, _Dimensions, _month(), Any, Register a callback fired when a spend threshold is crossed., Fold a new key into "other" once the dimension is at its cap. (+16 more)

### Community 231 - "v4_api.py"
Cohesion: 0.11
Nodes (36): _load_improvement_state(), Any, BaseModel, get, post, Request, backend/v4_api.py — v4 Dashboard API for the Continuous Improvement Dashboard.…, Load the improvement state from disk (non-blocking). (+28 more)

### Community 232 - "AnthropicProvider"
Cohesion: 0.11
Nodes (22): Added, Fixed, Added, Fixed, AnthropicProvider, Any, AsyncClient, Translate OpenAI-shaped messages into Anthropic's system/turn split. (+14 more)

### Community 233 - "Conflicts and Stale Facts"
Cohesion: 0.07
Nodes (25): C1 — The bill of materials is wrong in both directions, C2 — Three different answers to "where do I read env vars?", C3 — Two different file-size limits, C4 — The frontend does not deploy to Vercel, C5 — The documented P0 escape hatch does not exist, C6 — `CLAUDE.md` §14.11 conflicts with §14.9, C7 — Two `§10` headings in `CLAUDE.md`, C8 — Duplicated rule sets that have already drifted (+17 more)

### Community 234 - "Any"
Cohesion: 0.09
Nodes (13): _NoOpSpan, _NoOpTracer, otel_middleware_factory(), Any, Exception, Lazy-initialised OpenTelemetry tracer provider. Only imports the OTEL SDK when…, Return a tracer for the given name. Falls back to NoOpTracer if OTEL is…, Initialise the OTEL tracer provider on first use. (+5 more)

### Community 235 - "JCodeAdapter"
Cohesion: 0.07
Nodes (21): JCodeAdapter, Any, Path, Write .jcode/mcp.json in the workspace, pointing at our proxy's MCP endpoint.…, Resolve the default executor model via the catalog (UNIT 7). Was hardcoded to…, Adapter for jcode — TIER 2 high-performance Rust coding agent., _resolve_default_executor_model(), _build_default_manager() (+13 more)

### Community 236 - "workflow/api.py"
Cohesion: 0.10
Nodes (39): approve(), build(), cancel(), _engine(), get_agent_team(), get_artifact_content(), get_events(), get_run() (+31 more)

### Community 237 - "SeoFixer"
Cohesion: 0.14
Nodes (11): _humanize_filename(), BeautifulSoup, Path, Derive readable alt text from an image path: 'img/hero-banner_2.jpg' -> 'Hero…, Applies (or proposes) automatic SEO remediations inside a repo checkout., Scan the repo, fix every enabled auto-fixable problem found., SeoFixer, repl() (+3 more)

### Community 238 - "Workflow"
Cohesion: 0.06
Nodes (24): Enum, SuperClaude Workflow Engine — Workflow, Task, and topological DAG execution.…, Return tasks whose dependencies are all satisfied., Number of tasks in the workflow., Number of completed tasks., Number of failed tasks., Executes workflows using topological ordering., Register a workflow with the engine. (+16 more)

### Community 239 - "gsap.min.js"
Cohesion: 0.05
Nodes (33): Context(), Db(), Eb(), fb(), Hc(), ia(), Ic(), ie() (+25 more)

### Community 240 - "chat_handlers.py"
Cohesion: 0.06
Nodes (56): Layer 2 — Chat Handlers (`chat_handlers.py`, 710 lines), _apply_chat_defaults(), _apply_reasoning_budget(), _emit_safely(), _extract_exact_output(), _filter_fragment(), _filter_openai_sse_line(), handle_ollama_native_chat() (+48 more)

### Community 241 - "DistributedRateLimiter"
Cohesion: 0.09
Nodes (12): DistributedRateLimiter, _LocalBucket, PersistedRequest, PersistentQueue, Any, True once a Redis connection has actually been established., Consume capacity, waiting up to ``max_wait_sec``. Returns False when capacity…, One queued request durable across a restart. (+4 more)

### Community 242 - "test_purge_backlog.py"
Cohesion: 0.07
Nodes (22): auth_headers(), FakeTaskStore, MonkeyPatch, tests/test_purge_backlog.py — 2026-07-03 crash-loop remediation. Covers: - POST…, The per-minute tick must requeue at most ONE blocked task, keep its…, Drive _maybe_boot_purge with fakes; return (purged, marker_writes). ``core``…, A failed purge must NOT record the nonce — it retries next boot., A PARTIAL purge (error markers inside the summary) must not record the nonce… (+14 more)

### Community 243 - "TrendWatcher"
Cohesion: 0.15
Nodes (15): Any, AsyncClient, Path, Fetches AI trend signals from many public sources and surfaces relevant ones., Fetch all sources in parallel; return new alerts sorted by relevance., Dispatch high-relevance alerts to the Hermes sidecar for action. Only…, TrendAlert, TrendWatcher (+7 more)

### Community 244 - "TemporalContextGraph"
Cohesion: 0.10
Nodes (14): demo_agent_tracking(), datetime, Get history of an entity between two times, Get current state of an entity (most recent fact), Query facts with pattern matching, Get source (provenance) of a specific fact, A fact at a specific point in time, Example: track agent actions over time (+6 more)

### Community 245 - "llm_providers.py"
Cohesion: 0.12
Nodes (33): _anthropic_headers(), _anthropic_payload(), _anthropic_response_text(), _auth_headers(), chat_completion_text(), _do(), list_openai_models(), LlmProviderConfig (+25 more)

### Community 246 - "test_daily_automation_2026_05_15.py"
Cohesion: 0.10
Nodes (8): _normalize_anthropic_output_format(), Translate Anthropic ``output_format`` into an Ollama ``format`` field. Modifies…, Daily automation tests — 2026-05-15 Covers three features implemented in this…, Integration tests for POST /v1/messages/count_tokens., Unit tests for _normalize_anthropic_output_format., Caller adds anthropic-beta header when _normalize returns True., TestCountTokensEndpoint, TestNormalizeAnthropicOutputFormat

### Community 247 - "scrub"
Cohesion: 0.06
Nodes (27): _luhn_ok(), True when ``digits`` (bare, no separators) satisfies the Luhn checksum., Redact SSNs and Luhn-valid payment-card numbers from a string. Runs after the…, Recursively strip secrets from an arbitrary argument structure. Fails…, Redact secret-shaped substrings, then truncate., _redact_pii(), _card(), scrub() (+19 more)

### Community 248 - "test_pr923_fixes.py"
Cohesion: 0.07
Nodes (28): FakeDB, FakeDeleteResult, FakeScheduleCollection, asyncio, tests/test_pr923_fixes.py — regression tests for PR #923 (5 production issues).…, nuclear_cleanup should keep newest job per name, delete duplicates., nuclear_cleanup should gracefully handle a DB without a schedules collection., reconcile_stranded_tasks source code must include a FAILED-task re-queue pass.… (+20 more)

### Community 249 - "Autonomous AI Agency"
Cohesion: 0.10
Nodes (20): Architecture, security, license, Autonomous AI Agency, Contributing, Don't trust it — check the proof, Everything it does, 🛡 Governance, safety & ops, Honest model economics, How the agents are governed (+12 more)

### Community 250 - "service_daemon.py"
Cohesion: 0.08
Nodes (35): fastapi_responses, mcp_server, _check_auth(), _err(), _handle_tool(), health(), mcp_dispatch(), _ok() (+27 more)

### Community 251 - "test_background_services.py"
Cohesion: 0.07
Nodes (25): Return True when the web process should also run background services., run_background_in_web(), anyio, Unit tests for services/background.py — start_background_services wiring.…, Scheduler's on_fire handler is set to TaskAutomation.handle_scheduled_job., Calling bg.stop() twice must not raise or double-stop., RUN_BACKGROUND_IN_WEB defaults to True., The constant itself must leave real margin under Render's 5s timeout. (+17 more)

### Community 252 - "TestClient"
Cohesion: 0.09
Nodes (19): MonkeyPatch, TestClient, API-key-based /api/auth/me on proxy.py (port 8000)., GET /api/auth/me with valid API key → 200 with derived profile., GET /api/auth/me with unknown key → 403., GET /api/auth/me with no header → 401., GET /api/auth/me with x-api-key header (Claude Code style) → 200., GET /api/auth/me with empty Bearer token → 401. (+11 more)

### Community 253 - "test_telegram_webhook.py"
Cohesion: 0.06
Nodes (13): client(), asyncio, tests/test_telegram_webhook.py — inbound Telegram webhook receiver. The webhook…, When every attempt fails, the last error is returned so the caller can fall…, The secret must go in the POST body, never the URL (URLs get logged)., A transient setWebhook failure (Telegram's own resolver hiccup) is retried and…, test_process_webhook_update_never_raises(), test_process_webhook_update_routes_callback_and_message() (+5 more)

### Community 254 - "PatternConsolidation"
Cohesion: 0.08
Nodes (12): DreamMemory, PatternConsolidation, Group memories into clusters by tag overlap., Jaccard similarity of tag sets., Run the full consolidation cycle., A single memory fragment captured during AI sessions. Memories start as raw…, Memories older than 24h that haven't been consolidated are stale., Identifies clusters of related DreamMemory fragments and consolidates them into… (+4 more)

### Community 255 - "test_control_plane_api.py"
Cohesion: 0.06
Nodes (17): set_scheduler(), _FakeStore, mock_runtime_manager(), tests/test_control_plane_api.py — Tests for Control Plane API endpoints. Covers…, In-memory store stub for hydrate() tests — isolates from real DB., Stale run-once jobs (run_count > 0) must be skipped during hydration., Unfired run-once jobs (run_count == 0) must be rehydrated., Jobs already in memory must not be rehydrated (dedup by job_id). (+9 more)

### Community 256 - "OrchestratorQueue"
Cohesion: 0.17
Nodes (6): OrchestratorQueue, Any, _QueueEntry, Async FIFO queue that limits concurrent orchestrator run executions.…, Enqueue a run for async execution. Returns immediately. ``fn(*args, **kwargs)``…, Enqueue a run and return a future that resolves when it completes.

### Community 257 - "ContextPruner"
Cohesion: 0.13
Nodes (23): ContextPruner, Reset the prune timer so the next call always runs the pipeline., 3-phase context window management middleware. Phase 1 — Truncate: Strips…, big_pruner(), pruner(), Tests for agent/context_pruner.py — 3-Phase Context-Pruner Middleware., A pruner with a tiny budget so tests can trigger pruning cheaply., A pruner with a large budget (tests that pruning does NOT trigger). (+15 more)

### Community 258 - "SettingsHub.jsx"
Cohesion: 0.04
Nodes (38): deleteGithubToken(), githubStatus(), listGithubRepos(), setGithubToken(), C, STATUS_META, StatusPill(), TONE_BG() (+30 more)

### Community 259 - "ref_react"
Cohesion: 0.07
Nodes (29): Removed, Removed, getMe(), login(), logout(), App(), AppRoutes(), frontend_src_app_default (+21 more)

### Community 260 - "allow_paid"
Cohesion: 0.03
Nodes (56): Example: Access your home PC models from any machine. Install: pip install…, 2. Brain policy (free cloud LLMs), 3. The Gate Matrix (core artifact), 4. Telegram gate protocol, 5. The five autonomous loops, 7. Definition of "fully autonomous" — acceptance criteria, 8. Safety invariants (carried from `agent/CLAUDE.md`), 🟢 Autonomous — run, then notify-only (+48 more)

### Community 261 - "test_colibri_brain_shim.py"
Cohesion: 0.05
Nodes (55): colibri_enabled(), colibri_provider_config(), colibri_status(), providers/colibri.py — Free local GLM-5.2 brain served by JustVugg/colibri.…, Return True iff the operator opted in via ``COLIBRI_ENABLED=true``., Cheap status snapshot for tests + admin UI., Return the ``ProviderConfig`` for the local colibri server, or ``None`` when…, _safe_priority() (+47 more)

### Community 262 - "_Collection"
Cohesion: 0.11
Nodes (15): _apply_update(), _Collection, _DeleteResult, _InsertResult, _match(), _new_id(), _now_iso(), Return True if *doc* satisfies the MongoDB-style *query*. Supports: exact… (+7 more)

### Community 263 - "SyncService"
Cohesion: 0.10
Nodes (17): sync/ — Syncthing-style workspace synchronisation service., Any, Path, A single synchronised file fragment., Orchestrates workspace synchronisation across peers. Maintains an in-memory…, Return metadata for all files in a sync folder., Read a file from a sync folder., Write a file into a sync folder, creating parent dirs as needed. (+9 more)

### Community 264 - "MultiAgentSwarm"
Cohesion: 0.04
Nodes (65): AgentConfig, build_agent_specs(), build_swarm(), build_task_specs(), coordinate_v2(), CoordinateRequestV2, CoordinateResponse, Any (+57 more)

### Community 265 - "GitHubTools"
Cohesion: 0.12
Nodes (14): GitHubTools, Any, List issues (excludes pull requests) for triage/intake pipelines., Add labels to an issue (used to mark it as triaged, preventing reprocessing)., Merge an open pull request via the GitHub API., Backwards-compat: accepts 'owner/repo' format., Backwards-compat: accepts 'owner/repo' format., Commit a single file change. Accepts 'owner/repo' format for repo_name. (+6 more)

### Community 266 - "test_daily_2026_07_27.py"
Cohesion: 0.09
Nodes (16): filter_safe_tools(), get_tool_annotations(), Typed representation of MCP tool annotations (spec 2025-11-05 §5.6.1). All…, Extract ``ToolAnnotations`` for a named tool from a ``list_tools()`` result.…, Return tools where ``readOnlyHint`` is True and ``destructiveHint`` is not…, ToolAnnotations, Tests for the 2026-07-27 daily automation run. Features covered: 1. Self-…, get_tool_annotations extracts typed hints. (+8 more)

### Community 267 - "PlaybookLibrary"
Cohesion: 0.10
Nodes (20): _now(), Playbook, PlaybookLibrary, PlaybookRun, PlaybookStep, Any, Path, Store, search, and execute named automation playbooks. Usage:: lib =… (+12 more)

### Community 268 - "test_backend_lifespan_skips_bg_when_flag_false"
Cohesion: 0.24
Nodes (7): anyio, Web lifespan delegates to start_background_services when…, RUN_BACKGROUND_IN_WEB=false: lifespan starts but background services are NOT…, test_backend_lifespan_skips_bg_when_flag_false(), test_backend_lifespan_starts_runtime_manager_and_dispatcher(), fake_ensure_bootstrap(), fake_start_background_services()

### Community 269 - "Usage"
Cohesion: 0.05
Nodes (52): collections_abc, Modules, Writing a custom adapter, packages/llm/providers/anthropic.py — Anthropic Messages API adapter. Anthropic…, classify_error(), LLMProvider, OpenAICompatible, ABC (+44 more)

### Community 270 - "pr_approval_gate.py"
Cohesion: 0.15
Nodes (25): _card_keyboard(), _card_text(), _dedupe_key(), default_run_sweep(), _gh_get(), _gh_token(), interval_sec(), load_notified() (+17 more)

### Community 271 - "REWRITE_PLAN.md — Phased Migration Strategy"
Cohesion: 0.06
Nodes (35): Already completed (pre-migration fixes), Current Status, Inventory of suspected dead code, Migration Safety Checklist, Phase 1: Foundation (Weeks 1-2), Phase 2: Provider Abstraction (Weeks 3-4), Phase 3: Auth Consolidation (Week 5), Phase 4: Scheduler Redesign (Week 6) (+27 more)

### Community 272 - "CEOSupervisor"
Cohesion: 0.09
Nodes (17): CEOSupervisor, Any, What one sweep observed and did. Returned for tests and diagnostics., Sweeps the CEO ledger and drives open goals to closure., Sweep on the configured cadence until cancelled. A failing sweep is logged and…, Inter-sweep delay, behind a method so tests can shorten it. Patching…, True when this process already has a re-drive in flight for *goal_id*., Start a re-drive of *goal*, honouring the intervention budget. Returns… (+9 more)

### Community 273 - "_cfg"
Cohesion: 0.09
Nodes (14): _skip_without_pydantic, _cfg(), _cost_table(), tests/test_daily_automation_2026_09_11.py — Daily automation tests…, Pro should be tried after Flash (lower priority number = higher preference)., The router must not exclude gemini-2.5-pro from tool-calling requests., Gemini models must have entries in the cost table., Flash is on the free tier in this deployment — tracked as $0. (+6 more)

### Community 274 - "test_mcp_governance.py"
Cohesion: 0.09
Nodes (31): get_audit_log(), Return the process-wide audit log, created on first use., _call(), client(), _engine(), Governance on the MCP HTTP surface — threat-model T11. Before this,…, Same Golden Rule guarantee as the in-process gate., No UI is attached to this surface, so holding the socket would hang it. (+23 more)

### Community 275 - "test_persistent_memory.py"
Cohesion: 0.06
Nodes (35): memory_store(), Tests for persistent memory system., Test auto-loading global memories., Test auto-loading includes workspace-specific memories., Test that auto-load respects priority ordering., Test filtering memories by category., Create a temporary database for testing., Test searching memories. (+27 more)

### Community 276 - "test_provider_enable_disable.py"
Cohesion: 0.07
Nodes (16): isolated_kv(), one_provider(), _apply(), asyncio, parametrize, Per-provider on/off switch, with auto-disable for unfixable failures only.…, The critical guard: disabling on 429 would switch off every free provider., Point the kv_store at a temp DB so tests never touch real state. (+8 more)

### Community 277 - "test_sam_voice.py"
Cohesion: 0.05
Nodes (36): agent/sam.py must call emit_agency_observation for voice commands., test_sam_py_traces_voice_commands(), asyncio, tests/test_sam_voice.py — Integration tests for SAM voice agent. Tests the SAM…, Same session_id must return the same session., SAM's system prompt must address the user as Commander., SAM's system prompt must instruct concise responses., _build_context must return a dict with expected keys. (+28 more)

### Community 278 - "AdaptiveHalter"
Cohesion: 0.09
Nodes (12): AdaptiveHalter, Any, Return current halter state for logging / telemetry., Tracks step-level progress and signals when a run should halt early. The halter…, Ratio of applied steps to steps attempted (0.0–1.0). Returns 1.0 when no steps…, Record one step outcome; return a halt reason or None to continue. ``status``…, tests/test_daily_automation_2026_07_13.py — Daily automation tests…, Unit tests for agent.adaptive_halting.AdaptiveHalter. (+4 more)

### Community 279 - "SecurityScanner"
Cohesion: 0.11
Nodes (24): _now(), Any, Path, Run all available scanners and aggregate results., Run a cross-harness security audit. Checks that the agent harness configuration…, Return True if *name* is on PATH., Return current UTC timestamp as ISO string., Run security scans and return structured findings. Usage:: scanner =… (+16 more)

### Community 280 - "test_provider_render_env.py"
Cohesion: 0.09
Nodes (25): ProviderRenderSync, Push a provider's key/base_url into the Render service environment. At least…, Write a provider's key and/or base_url to the Render service environment. This…, sync_provider_to_render(), provider_env_names(), RuntimeError, Raised when Render rejects or cannot serve an env-var write., Return ``(key_env, base_url_env)`` for a provider id, or ``None``. Sourced from… (+17 more)

### Community 281 - "agent_runtime.py"
Cohesion: 0.09
Nodes (33): _active_cloud_provider(), _candidate_ollama_bases(), _chat(), chat_completions(), _chat_with_ollama(), _chat_with_openai_compat(), ChatRequest, ChatResponse (+25 more)

### Community 282 - "RateLimitTracker"
Cohesion: 0.10
Nodes (12): get_tracker(), RateLimitTracker, Snapshot of all tracked provider quotas. Safe to call from any context., Reset all state (primarily for tests)., Return the process-singleton RateLimitTracker., In-memory tracker for per-provider rate-limit state., asyncio, _response() (+4 more)

### Community 283 - "test_chat_mode_regressions.py"
Cohesion: 0.08
Nodes (23): bson, ProviderAttempt, _auth_headers(), test_agent_status_endpoint_reports_live_progress_and_tool_calls(), fake_agent_loop(), test_agent_stream_endpoint_emits_server_sent_events(), test_chat_send_emits_langfuse_observation_for_direct_chat(), test_chat_send_keeps_complex_prompt_on_direct_path_when_agent_mode_is_off() (+15 more)

### Community 284 - "local_controller.py"
Cohesion: 0.09
Nodes (41): Fixed, Fixed, Fixed, Fixed, Fixed, Fixed, DetailsStep(), ProviderResult (+33 more)

### Community 285 - "test_brain_failover.py"
Cohesion: 0.12
Nodes (32): ProviderHealth, Circuit-breaker state for a provider., _make_manager(), tests/test_brain_failover.py — Universal multi-provider brain failover tests.…, Guards the three tests below from pinning a retired id again: if the fixture…, Status snapshot doesn't leak API keys., Make a fresh manager (bypasses the singleton for isolation)., No API keys set → no providers in the registry. (+24 more)

### Community 286 - "TestDiagCommand"
Cohesion: 0.11
Nodes (9): Drive _process_update with a /diag message and return the response. Restores…, The Operator Charter §"Telegram bot" silent-drop path MUST surface a…, Once we've warned once, subsequent silent drops must NOT spam the log., ``/diag`` behaviour under admin + non-admin + empty-allowlist states., Replace ``_send_message`` for the next ``_process_update`` call., _run(), TestDiagCommand, _fake() (+1 more)

### Community 287 - "test_all_providers_discovery.py"
Cohesion: 0.17
Nodes (34): _get(), asyncio, Verify every supported provider is correctly discovered, prioritised, and…, Check if url hostname matches expected domain (exact or subdomain)., Build a ProviderRouter from_env() with only the supplied env vars active., _router(), test_anthropic_discovery(), test_anthropic_no_base_url_required() (+26 more)

### Community 288 - "TestDiscovery"
Cohesion: 0.13
Nodes (6): Discovery must never be the reason a run dies., Silent degradation is the defect this whole module exists to end.…, Reads the provider's own catalogue; never raises into the caller., TestDiscovery, _raise(), TestFailureIsAudible

### Community 289 - "SpecEntry"
Cohesion: 0.13
Nodes (15): get_enrichment(), Return the enrichment instance for a workspace. Keyed by workspace root rather…, Rewrite the spec file, preserving any non-entry (hand-written) lines., One standing instruction plus the evidence that earned it., SpecEntry, write_entries(), Regressions for defects found in review of this module., verify=False is the internal path used for merging, and stays permissive. (+7 more)

### Community 290 - "OutputFilter"
Cohesion: 0.06
Nodes (46): filter_output(), FilterResult, OutputFilter, Filter and compress command outputs to reduce LLM token consumption. Provides…, Compact git status output — keep only changed file paths., Compact git log — one line per commit., Compact git diff — keep file headers, collapse hunks., Compact test output — keep only failures and summary. (+38 more)

### Community 291 - "_resolve_brain_provider"
Cohesion: 0.07
Nodes (27): Resolve the LLM endpoint for agent execution (module-level, #522 failover).…, _resolve_brain_provider(), Critical failover-safety test: if every free provider's base URL is excluded…, When the ONLY configured provider is a paid one (e.g. operator set…, When only Anthropic is configured AND allow_paid=False (default), the resolver…, When AGENT_LLM_BASE_URL is set, the brain resolver must return that endpoint —…, When a free cloud provider (NVIDIA NIM, etc.) is configured, the brain resolver…, _run() (+19 more)

### Community 292 - "OrchestratorSupervisor"
Cohesion: 0.16
Nodes (8): Return orchestrator queue depth, active runs, and supervisor state (#522)., workflow_orchestrator_status(), get_orchestrator_queue(), get_orchestrator_supervisor(), OrchestratorSupervisor, Any, Emit an alert to the activity feed and log., Deterministic supervisor for the orchestrator. Runs as a background coroutine.…

### Community 293 - "Configuration Reference"
Cohesion: 0.07
Nodes (27): Agent governance — identity, policy, approvals, audit, sandboxes, Agent Models, Anthropic API Compatibility / Claude Code, Authentication and Keys, Claude Code setup, Configuration Reference, Continual Harness, Dashboard (React UI on :3000, API on :8001) (+19 more)

### Community 294 - "DashboardScreen.jsx"
Cohesion: 0.08
Nodes (7): Charts, Donut(), Sparkline(), ErrorBoundary, DashboardScreen(), fmtTokens(), relTime()

### Community 295 - "context_rules.py"
Cohesion: 0.06
Nodes (51): Changing these rules, How the gate behaves, Quick-Note Context Rulebook, R10 — Use the repository's real identity **[gate]**, R11 — Name a real integration point **[gate]**, R12 — Mark epistemic status at the claim **[review]**, R1 — Ground the plan in the source before planning anything **[gate]**, R2 — Say what the artifact actually is **[gate]** (+43 more)

### Community 296 - "_plan"
Cohesion: 0.09
Nodes (16): _build_grounding_block(), Render the Source Grounding table — rulebook R1. A reader must be able to tell…, _plan(), parametrize, Path, A plan that says "do not build this" must stop the thing that builds. On…, The real thing, reconstructed from the merged plan.…, An unreadable plan is not an approved plan. (+8 more)

### Community 297 - "test_rate_limiter.py"
Cohesion: 0.09
Nodes (26): pace(), Rate limiter using virtual scheduling (GCRA-style): each caller atomically…, Block until this caller's reserved slot arrives, or *max_wait* elapses. Returns…, Proactively pace a request to *provider_id*. No-op (returns 0.0 immediately)…, Clear all token-bucket state (tests only). Does not touch the header tracker's…, reset(), TokenBucket, Tests for packages/ai/rate_limiter.py — proactive x-ratelimit-* throttling… (+18 more)

### Community 298 - "test_live_server.py"
Cohesion: 0.22
Nodes (32): check(), main(), ok(), Any, Client, Returns access token for subsequent tests., E2E smoke-test suite — runs against a live local-llm-server instance. Every…, Direct-mode chat. Passes even if no LLM backend is running (error message… (+24 more)

### Community 299 - "_routing_candidates"
Cohesion: 0.09
Nodes (16): _brain_config_source(), _llm_models(), tests/test_daily_automation_2026_09_14.py — Daily automation tests…, Primary presets (opus-5, sonnet-5) must still lead the list., Gemini 3.x models must be in the Google provider failover candidates., Each 3.x candidate must also be in config/llm/models.yaml., gemini-2.5-flash must remain the primary (probed, role preset)., Proven 2.5 models must precede unprobed 3.x ones. (+8 more)

### Community 300 - "ContextCompressor"
Cohesion: 0.11
Nodes (24): ContextCompressor, ContextStats, _estimate_tokens(), Strategy, agent/context.py — Smart Context Compression Three strategies for keeping…, Drop the oldest non-system messages until under the token threshold., Remove exact-duplicate and near-empty messages., Compress conversation history when it approaches the token limit. Usage:: cc =… (+16 more)

### Community 301 - "ContextManager"
Cohesion: 0.10
Nodes (24): ContextManager, Any, True when the history is long enough to warrant compaction., Replace the old portion of *history* with a single compaction note. The…, True when the harness should use head_file instead of read_file. When a file is…, Trim a step result so sub-agent outputs stay within ~1-2k tokens. The Anthropic…, Manages context window state for a single agent run. The Brain (LLM) stays…, Return a copy of *observations* with old tool outputs truncated. JetBrains… (+16 more)

### Community 302 - "test_mcp_registry.py"
Cohesion: 0.09
Nodes (30): get_mcp_client(), Return the module-level MCPClient. Reads MCP_SERVER_BASE_URL at call time (not…, _internal_configured(), list_specs(), MCPServerSpec, _not_dialable(), _playwright_configured(), _playwright_spec() (+22 more)

### Community 303 - "SparkProvider"
Cohesion: 0.07
Nodes (20): get_spark_provider(), NotarizeResult, Any, Return True if SPARK API key is set., Register this agent on the SPARK network. If *bsv_address* is not provided,…, Notarize content hash on the BSV blockchain. Args: content: String or bytes to…, Verify a hash against the BSV blockchain. Args: content_hash: SHA-256 hash to…, Hash content for notarization. (+12 more)

### Community 304 - "ResourceWatchdog"
Cohesion: 0.10
Nodes (19): _now(), Any, Register a resource to monitor. Returns the :class:`WatchedResource`., Stop monitoring a resource. Returns *True* if it existed., Check a single resource right now. Returns a :class:`WatchEvent` if changed., Poll resources at a fixed interval and fire *on_change* when content changes.…, ResourceWatchdog, WatchedResource (+11 more)

### Community 305 - "Added"
Cohesion: 0.03
Nodes (149): Send chat messages and return the assistant's text output. If an…, Public snapshot of live agency state (used by the LiveKit worker tools)., Gather live agency state for SAM's situational awareness., BudgetExceededError, Exception, Reset token counters for all sessions (caps preserved). Called at the start of…, Reset all budgets if the UTC calendar day has changed since last reset. Safe to…, Raised when a token spend cap is hit. (+141 more)

### Community 306 - "test_connector_registry.py"
Cohesion: 0.08
Nodes (20): Fixed, packages_integrations, _connectors(), ConnectorSpec, get_connector(), list_connectors(), Any, Execute the ``webhook`` connector: POST *payload* as JSON to *url*. Fails soft… (+12 more)

### Community 307 - "test_ephemeral_reaper.py"
Cohesion: 0.09
Nodes (31): _as_aware_utc(), _company_alive(), _company_id_for_agent(), _env_float(), ephemeral_reaper_loop(), datetime, services/ephemeral_reaper.py — destroy expired ephemeral companies. The…, Whether *company_id* still exists, cached per sweep. A lookup error returns… (+23 more)

### Community 308 - "skill_bindings.py"
Cohesion: 0.09
Nodes (25): 3. Dynamic, expandable roles (open registry, not a closed enum), BaseModel, Enum, str, services/skill_bindings.py — Runtime Skill Bindings for Specialist Agents Wires…, A runtime-callable skill that specialists can execute through the workflow…, Set the singleton SkillBindings instance (for testing)., Central registry that maps skills to specialist families and provides runtime… (+17 more)

### Community 309 - "test_microagents.py"
Cohesion: 0.15
Nodes (29): load_microagents(), match_microagents(), Microagent, microagents_block(), _parse_file(), Path, OpenHands-compatible microagents: keyword-triggered repo knowledge. OpenHands…, Parse one microagent markdown file; None when it isn't one. (+21 more)

### Community 310 - "Retrospective"
Cohesion: 0.11
Nodes (13): generate_sprint_retro(), Derive retro notes for ``sprint`` from its current metrics. Records…, Sprint retrospective notes and follow-up action items., Whether the retrospective has any recorded content., Story points added since the sprint started (scope creep). Returns 0 before the…, Record a retrospective observation (what went well / poorly)., Record a follow-up action item from the retrospective., Qualitative health signal derived from sprint metrics. (+5 more)

### Community 311 - "app_settings.py"
Cohesion: 0.14
Nodes (23): all_settings(), _as_bool(), _as_int(), ephemeral_ttl_hours(), ephemeral_ttl_hours_cached(), get_setting(), _maybe_schedule_refresh(), onboarding_gate_enabled_cached() (+15 more)

### Community 312 - "Security Analysis — local-llm-server"
Cohesion: 0.09
Nodes (20): Fable 5 — Read-Only Audit & Skill-Distillation Notes, Finding B — `/api/secrets` router is mounted with no authentication dependency, Minor, non-security, Part 0 — A caveat on how this task started, Part 1 — The audit, Suggested fixes (not applied here), The chain, What was checked and is sound (+12 more)

### Community 313 - "get_scheduler"
Cohesion: 0.05
Nodes (46): legacy_scheduler_delete(), legacy_scheduler_get(), legacy_scheduler_list(), legacy_scheduler_trigger(), _produce_scheduler_jobs(), Called by Cloudflare Cron every minute. Protected by CRON_SECRET header., Force-dedup and clean stale schedules from the durable store. Admin-only…, scheduler_force_cleanup() (+38 more)

### Community 314 - "test_backend_server_features.py"
Cohesion: 0.06
Nodes (20): _append_agent_session_message(), _build_auto_skill_guidance(), _run_agent_job(), _mask_observations(), Path, Truncate tool/observation content in older messages to prevent context bloat., _run_agent_loop(), _select_auto_skills() (+12 more)

### Community 315 - "get_failover_manager"
Cohesion: 0.06
Nodes (40): brain_failover_status(), openclaw_command(), _openclaw_instructions(), openclaw_reverse_proxy(), openclaw_status(), openclaw_websocket(), ProviderEnabledBody, api_route (+32 more)

### Community 316 - "Langfuse Observability Guide"
Cohesion: 0.06
Nodes (32): 1. Create a Langfuse project, 2. Configure credentials, 3. Optional tuning, 4. Verify the connection, Commercial savings metrics, Cost analysis dashboard, Cost dashboard, Customising Commercial Reference Prices (+24 more)

### Community 317 - "v3_models.py"
Cohesion: 0.13
Nodes (31): _get_current_user, UserResponse, delete_model(), get_activity(), get_model(), _get_ollama_model_info(), _get_ollama_models(), get_stats() (+23 more)

### Community 318 - "autonomous_fix.py"
Cohesion: 0.11
Nodes (19): _decline(), _extract_pytest_failure(), _fetch_failure_context(), _is_denied_path(), _list_target_prs(), main(), _post_comment(), _pr_head() (+11 more)

### Community 319 - "probe_catalogues.py"
Cohesion: 0.10
Nodes (36): Added, Fixed, Added, Fixed, _auth_headers(), _chat_targets(), _dump_matching(), _kind() (+28 more)

### Community 320 - "CheckpointStore"
Cohesion: 0.16
Nodes (9): CheckpointStore, Path, Persist a checkpoint to disk. Returns the file path., Return the latest checkpoint for a session, or None., Return all checkpoint files for a session, sorted by step index., Remove all checkpoints for a session., File-backed checkpoint persistence. Each session gets a directory under…, Path (+1 more)

### Community 321 - "OrchestratorCheckpointStore"
Cohesion: 0.11
Nodes (12): _NoopDB, OrchestratorCheckpointStore, Any, Restore in-flight runs at startup. Called during backend bootstrap. Returns a…, Fallback in-memory store when no DB is available., Persist orchestrator runs so they survive restarts., Persist a WorkflowRun snapshot., Load a persisted run snapshot. (+4 more)

### Community 322 - "test_telegram_mutating_commands.py"
Cohesion: 0.09
Nodes (26): _catalogue_preset(), _make_mock_response(), tests/test_telegram_mutating_commands.py — N5 acceptance: /setbrain + /merge.…, Build a mock httpx.Response., A successful /setbrain call must: 1. send the X-Service-Token header 2. PATCH…, When the backend's liveness probe fails (HTTP 422), the bot reply must surface…, 503 = backend doesn't have SERVICE_TOKEN set. The bot reply must tell the…, A successful /merge call returns the merge SHA + actor attribution so the… (+18 more)

### Community 323 - "test_workspace_isolation.py"
Cohesion: 0.16
Nodes (16): Tests for workspace isolation model (Area A). Covers: - Unique workspace path…, Security-oriented tests for workspace isolation (Area C4). Covers: - No path…, InvalidJobIdError, InvalidSessionIdError, Exception, workspace/errors.py — Structured, actionable workspace errors. Every error…, Base class for all workspace errors., WorkspaceCleanupBlockedError (+8 more)

### Community 324 - "SkillLibrary"
Cohesion: 0.11
Nodes (21): Any, Path, agent/skills.py — Skill Library Indexes and searches agent skills from local…, Discover, search, and retrieve agent skills. Usage:: lib = SkillLibrary() #…, Full-text search across name, description, and content., Register an MCP-hosted skill pack entry., Skill, SkillLibrary (+13 more)

### Community 325 - "StuckDetector"
Cohesion: 0.14
Nodes (23): Any, Canonical identity of one observation, ignoring incidental fields., Consecutive repetitions required before a pattern counts as stuck., Detects repeating patterns in a step's observation history., Return a human-readable reason when the loop looks stuck, else None., _signature(), StuckDetector, StuckThresholds (+15 more)

### Community 326 - "WorkspaceManager"
Cohesion: 0.18
Nodes (9): _normalize_path(), _now(), Any, BaseModel, Path, WorkspaceCreate, WorkspaceManager, WorkspaceRecord (+1 more)

### Community 327 - "High-Agency Frontend Skill"
Cohesion: 0.06
Nodes (30): 10. FINAL PRE-FLIGHT CHECK, 1. ACTIVE BASELINE CONFIGURATION, 2. DEFAULT ARCHITECTURE & CONVENTIONS, 3. DESIGN ENGINEERING DIRECTIVES (Bias Correction), 4. CREATIVE PROACTIVITY (Anti-Slop Implementation), 5. PERFORMANCE GUARDRAILS, 6. TECHNICAL REFERENCE (Dial Definitions), 7. AI TELLS (Forbidden Patterns) (+22 more)

### Community 328 - "_resolve_user_github_token"
Cohesion: 0.08
Nodes (35): DirectChatDoctor, Recommend skills relevant to the current task. Called from the tool-call loop…, get_skill_registry_safe(), Return the global SkillRegistry if set, else None. Used by onboarding and other…, _DoctorCheck, _DoctorReport, get_doctor_diagnostics(), get_doctor_report() (+27 more)

### Community 329 - "Quick-Note GitHub Issues Processing - Session Summary"
Cohesion: 0.06
Nodes (30): 1. Stop-Slop Quality Filter (Issue #229), 2. ECC Integration Study (Issue #266 & #230), ✅ Analysis & Comments (16 items), Architecture Alignment, Branch: `docs/ecc-adoption-analysis`, Branch: `feat/stop-slop-quality-filter`, Deliverables, ECC Patterns Adopted (+22 more)

### Community 330 - "Added"
Cohesion: 0.02
Nodes (102): Build the complete enrichment block (tools + skills). Returns empty string when…, Inject available tools + skills catalog into the system message.…, Charge sub-agent nesting depth and enforce the ``max_depth`` ceiling. Isolates…, note_phase_end(), note_phase_start(), Record that *phase* began; returns the token that ends it. Called from…, Close the invocation identified by *token*. Never raises., Cooldown + hourly cap. Caller must hold the lock. Reserves the slot on success.… (+94 more)

### Community 331 - "sync/service.py"
Cohesion: 0.10
Nodes (31): FastAPI dependency: require Power User or Admin role. Raises 403 otherwise., require_power_user(), add_peer(), get_folder_index(), get_sync_file(), get_sync_service(), list_conflicts(), list_peers() (+23 more)

### Community 332 - "test_platform_controls.py"
Cohesion: 0.10
Nodes (18): all_controls(), Every control in the catalogue, in display order., _python_sources(), Tests for the dashboard platform-controls surface. Covers the three things that…, Secrets stay environment-only per the repository constitution., Every non-test Python file in the repo, concatenated., Guards two ways this can silently not work. FastAPI defers router expansion, so…, A control for a variable nothing reads would be a dead switch in the UI. (+10 more)

### Community 333 - "switch_brain.py"
Cohesion: 0.15
Nodes (30): detect_ollama_models(), dim(), fail(), get_auth_headers(), get_brain_config(), get_ngrok_tunnel_url(), header(), info() (+22 more)

### Community 334 - "test_session_retro.py"
Cohesion: 0.13
Nodes (28): cluster_friction(), clusters_to_issues(), collect_friction_events(), FrictionCluster, FrictionEvent, judge_cluster(), Any, Return a human-readable description of the cluster. Uses *judge_fn* (an LLM-as-… (+20 more)

### Community 335 - "test_crispy_burn_in.py"
Cohesion: 0.02
Nodes (63): importlib, agency_fix(), tests/test_agency_fix.py — N3 acceptance tests for scripts/agency_fix.py. The…, An edit that produces a syntactically-broken Python file must be rejected —…, An edit that truncates a real code file to a trivial body must be rejected —…, With no issue linked, decline is just an exit-code signal — no API call., When an issue is linked but no GH_PAT/GH_TOKEN is set, the decline fails loudly…, When an issue is linked and the API call succeeds, decline_cleanly returns True… (+55 more)

### Community 336 - "test_daily_2026_06_04.py"
Cohesion: 0.08
Nodes (41): _content_block_to_text(), Convert a single Anthropic content block to a plain text string., is_anthropic_model(), True when *model* names a paid Anthropic/Bedrock-Claude model. Covers native…, _opus_model(), Reset the singleton and clear the cached model map (test helper)., Return an Opus model ID iff the operator explicitly opted into a paid brain.…, reset_router() (+33 more)

### Community 337 - "test_skill_registry_boot_refresh.py"
Cohesion: 0.11
Nodes (16): clean_task(), _install(), _NullDispatcher, _NullRuntimeManager, asyncio, Exception, The configured remote skill repos must be fetched without a human trigger.…, Remote skills are optional; a rate limit must not surface as an error. (+8 more)

### Community 338 - "test_autonomy_gate.py"
Cohesion: 0.12
Nodes (28): agent_branch_name(), assert_agent_can_merge(), assert_agent_can_write(), AutonomyViolation, is_protected_branch(), _protected_branches(), Autonomy gate — enforce 'agents propose via PR, humans merge'. The agency can…, Raised when an agent-initiated action would exceed the propose-PR policy. (+20 more)

### Community 339 - "test_phase6_workflow.py"
Cohesion: 0.14
Nodes (26): Return True if the PR exists and is open or merged; False if 404., verify_pr_exists(), _make_store(), _make_task(), asyncio, tests/test_phase6_workflow.py — Phase 6: workflow engine, safe_agency, Task…, Create a minimal Task for testing., Infinite loops: engine must stop at max_phases. (+18 more)

### Community 340 - "AgileManager"
Cohesion: 0.07
Nodes (17): AgileManager, Manages multiple agile sprints with velocity tracking., List all active sprints., Predict next sprint velocity from historical data., Number of managed sprints., Capacity & roadmap, Context: Agentic Agile + Portfolio Management, Extension ideas (not yet built) (+9 more)

### Community 341 - "get_ceo_ledger"
Cohesion: 0.17
Nodes (19): build_ceo_router(), ceo_status(), get_goal(), list_goals(), redrive_goal(), run_sweep(), Any, APIRouter (+11 more)

### Community 342 - "SeoAuditReport"
Cohesion: 0.08
Nodes (43): _expire_stale_pending_report(), Auto-fail a pending SEO audit stub that is older than…, html, io, Complete result of one audit run., SeoAuditReport, Paragraph, reportlab_lib (+35 more)

### Community 343 - "register_admin_gui"
Cohesion: 0.16
Nodes (22): Update or append a KEY=value line in the .env file., register_admin_gui(), dashboard(), diag_langfuse(), _guest_redirect(), login_page(), login_submit(), _redirect() (+14 more)

### Community 344 - "test_scheduler_hydration_bounded.py"
Cohesion: 0.09
Nodes (22): _hydrate_scheduler_bounded(), Attach durable persistence and rehydrate (#505), bounded by a budget. Without…, _BrokenScheduler, _fake_schedule_store(), _FakeStore, _FastScheduler, _HangingScheduler, _isolate_warmup_overflow() (+14 more)

### Community 345 - "test_brain_availability_doctor.py"
Cohesion: 0.10
Nodes (34): Drop the singleton (test helper)., reset_ceo_ledger(), _doctor(), _P, _patch_providers(), asyncio, Tests for the public brain-availability diagnosis and the supervisor's use of…, Minimal provider stand-in matching what the summary reads. (+26 more)

### Community 346 - "test_ceo_router.py"
Cohesion: 0.13
Nodes (27): Install (or clear) the singleton — used by startup wiring and tests., Drop the singleton (test helper)., reset_ceo_supervisor(), set_ceo_supervisor(), _make_app(), FastAPI, tests/test_ceo_router.py — auth and behaviour for /api/ceo/*. Follows the…, The happy path — the branch that actually spends provider budget. (+19 more)

### Community 347 - "_redact_for_notification"
Cohesion: 0.11
Nodes (18): Best-effort secret/email/IP redaction for outbound Telegram/webhook messages., _redact_for_notification(), _FakeResponse, _make_task(), SimpleNamespace, Regression tests for telegram_service.NotificationDispatcher._notify_webhook.…, Regression: _notify_webhook used to define _send() but never call it., Drain any daemon threads spawned by the dispatcher (webhook/telegram). Snapshot… (+10 more)

### Community 348 - "test_force_cleanup_conditional_delete.py"
Cohesion: 0.10
Nodes (14): _FlakyPersistence, _memory_store(), _orphan(), asyncio, _RaceLostPersistence, _RaceWonPersistence, tests/test_force_cleanup_conditional_delete.py Covers two changes to the…, Every removal path fails at the durable store. (+6 more)

### Community 349 - "test_commit_tracker.py"
Cohesion: 0.18
Nodes (19): CommitAttribution, CommitTracker, Path, Create git commits enriched with agent-session attribution trailers. Usage::…, Return ``--trailer`` arguments ready to append to a ``git commit`` call., Stage *files* and create an attributed commit. Returns the commit SHA on…, _init_repo(), Path (+11 more)

### Community 350 - "test_rag_context.py"
Cohesion: 0.12
Nodes (23): RAGContextBuilder, Retrieve, decay, and compress context to fit a configurable token budget.…, Tests for agent/rag_context.py — Advanced RAG context management layer. Imports…, test_builder_doc_budget_fraction(), test_builder_docs_dropped_count(), test_builder_empty_both(), test_builder_empty_documents(), test_builder_empty_history() (+15 more)

### Community 351 - "ProjectScaffolder"
Cohesion: 0.14
Nodes (19): ProjectScaffolder, Any, Path, Apply named project templates to a target directory. Usage:: s =…, Write template files into *target_dir*. Skips existing files unless…, ScaffoldResult, Template, Path (+11 more)

### Community 352 - "ScheduleStore"
Cohesion: 0.10
Nodes (19): _backend(), _json_default(), Any, Return all persisted schedule docs (for boot rehydration)., Persist (insert or update) a single schedule by job_id., Delete a persisted schedule., Fallback JSON encoder for schedule docs (datetimes, sets, etc.)., Durable schedule persistence. Backend is chosen from ``STORAGE_BACKEND``: *… (+11 more)

### Community 353 - "test_dashboard_cache.py"
Cohesion: 0.15
Nodes (13): _clear_cache(), _CollWithEstimate, _CollWithoutEstimate, _ensure_mongo_fast_count(), asyncio, tests/test_dashboard_cache.py — unit tests for the dashboard hot-path helpers…, Ensure _fast_count tries estimated_document_count() for tests. conftest.py…, test_cached_is_single_flight() (+5 more)

### Community 354 - "generate_context.py"
Cohesion: 0.14
Nodes (24): _build_caller_chain(), _build_context_doc(), _build_pr_description(), _build_todos_md(), _build_user_message(), _call_cerebras(), _call_claude(), _call_groq() (+16 more)

### Community 355 - "pytest"
Cohesion: 0.02
Nodes (63): Strip API keys, tokens, emails, IPs, and private keys from a log line., _redact_sensitive(), pytest, asyncio, Tests for app_settings — DB-persisted settings + onboarding-gate default. These…, Point db.get_store() at an isolated temp SQLite DB. Patches…, is_user_onboarding_allowed falls back to the global default for users with no…, sqlite_store() (+55 more)

### Community 356 - "ControlSpec"
Cohesion: 0.17
Nodes (14): Adding a control, packages/config/control_catalogue.py — the 109 operator-facing controls. The…, ControlGroup, ControlOption, ControlSpec, _number(), Any, packages/config/control_specs.py — the vocabulary of a platform control. The… (+6 more)

### Community 357 - "SteeringInjector"
Cohesion: 0.11
Nodes (10): Any, Inject steering instructions into the message list. Args: messages: The…, Inject steering into an OpenAI chat payload dict. Modifies and returns the…, Build the steering instruction text based on format., Build steering as natural-language quality instructions., Build steering as ChatML-formatted tokens., Build steering as Nemotron-specific steering tags., Inject steering tokens into prompts for quality-biased generation. Supports… (+2 more)

### Community 358 - "RuntimeHealthService"
Cohesion: 0.08
Nodes (13): F2 — MCP Server Exposing Proxy Capabilities [P1] [CBF / ECC], CircuitState, runtimes/health.py — RuntimeHealthService. Periodically polls all registered…, Return the last-known health for *runtime_id* (may be stale)., Return True if the runtime is available (not circuit-open)., Return health snapshots for all known runtimes., Force an immediate health check of all runtimes and return results., Attempt to start a dead runtime subprocess before re-probing. Uses the local… (+5 more)

### Community 359 - "test_claude_setup_audit.py"
Cohesion: 0.16
Nodes (23): AuditReport, _check_agents_config(), _check_claude_md_sections(), _check_hooks(), _check_skills(), _check_state(), CheckResult, main() (+15 more)

### Community 360 - "decide"
Cohesion: 0.12
Nodes (16): decide(), Decision, issue_number_from_branch(), main(), scripts/triage_orphaned_context_prs.py Decide what to do about a draft context…, Return the issue number a context branch was generated for, if any., Decide how to recover the *issue* behind an orphaned draft PR. *issue* is the…, _issue() (+8 more)

### Community 361 - "sam_livekit_worker.py"
Cohesion: 0.14
Nodes (22): livekit_agents, get_livekit_config(), LiveKitConfig, voice/livekit_config.py — LiveKit configuration (config module). Centralizes…, Resolved LiveKit + speech-provider configuration., Resolve LiveKit configuration from the environment (read fresh each call)., _build_llm(), _build_stt() (+14 more)

### Community 362 - "isolated_telegram_config"
Cohesion: 0.12
Nodes (8): isolated_telegram_config(), Snapshot+restore ``tb`` globals + ``TELEGRAM_POLLER_DISABLED``. Keyword args…, tests/test_telegram_test_utils.py Self-test suite for…, The helper's ``__exit__`` runs ``if original is _MISSING: if hasattr:…, If a tracked attr is absent under ``tb`` at scope entry, the helper snapshots…, Snapshot + restore + apply-filter semantics for the helper., Passing only ``token=`` must NOT touch ALLOWED/ADMIN/etc., TestIsolatedTelegramConfig

### Community 363 - "test_internal_agent_did_work.py"
Cohesion: 0.12
Nodes (28): _compute_did_work(), tests/test_internal_agent_did_work.py — step-success-ratio gate tests. Tests…, judge_verdict=BLOCKED → always FAILURE, even with 10/10 applied., judge_verdict=BLOCKED → always FAILURE, even with a long report., Even with unique_files, 1/22 applied → FAILURE (steps_ok gate)., With 9/10 applied + unique_files → SUCCESS., Replicate the did_work logic from internal_agent.py:509-533., 1/22 applied (4.5%) → should be FAILURE (the bug case). (+20 more)

### Community 364 - "_captured_request_headers"
Cohesion: 0.12
Nodes (14): _captured_request_headers(), _fake_post(), _make_client(), Any, tests/test_mcp_routing_headers.py — MCP 2026-07-28 Mcp-Method / Mcp-Name…, Run client.call_tool() and capture the request headers., Extra headers must not displace existing required headers., extra_headers passed to _rpc are method-specific; this tests isolation. (+6 more)

### Community 365 - "test_executive_advisory.py"
Cohesion: 0.09
Nodes (29): AdviceResult, AdvisoryMemory, _compose_context(), _format_company_context(), get_executive_advisory(), Grounding, _keywords(), _mem_key() (+21 more)

### Community 366 - "TerminalPanel"
Cohesion: 0.13
Nodes (20): _is_command_not_found(), _powershell_quote(), Any, agent/terminal.py — Terminal Panel Reads the rendered terminal output buffer —…, Try to read the pane buffer via tmux capture-pane., Return a minimal snapshot with terminal dimensions only., Capture the current terminal buffer as a :class:`TerminalSnapshot`. Usage::…, Capture the current terminal state. Never raises. (+12 more)

### Community 367 - "Python Dependencies (`requirements.txt`)"
Cohesion: 0.07
Nodes (27): AI / LLM, AI Tooling, Browser Automation, Cloud / Infrastructure, Core Web Framework, Data Processing, DEP-001 [HIGH] — No Python Lockfile, DEP-002 [HIGH] — `playwright` as a Runtime Dependency (+19 more)

### Community 368 - "Technical Debt Register — local-llm-server"
Cohesion: 0.08
Nodes (25): Category 10 — Patch Files in Root, Category 1 — God Files, Category 3 — Dual App Architecture, Category 4 — Dual Storage Backend, Category 5 — Test File Sprawl, Category 6 — Environment Variable Documentation, Category 7 — Missing Type Annotations, Category 8 — Comments and Documentation Debt (+17 more)

### Community 369 - "_ensure_tasks_source_id_unique_index"
Cohesion: 0.10
Nodes (22): _agent_provider_failure_response(), _ensure_tasks_source_id_unique_index(), _build(), _is_index_options_conflict(), Exception, True when *exc* is Mongo refusing to redefine an existing index. Mongo raises…, Add a unique **partial** index on tasks.source_id — isolated from the main…, Fall back to a direct LLM call when the agent loop cannot reach any provider.… (+14 more)

### Community 370 - "FeatureEntry"
Cohesion: 0.12
Nodes (11): Added, Added, FeatureEntry, Any, BaseModel, One entry in the support matrix., Return the feature entry if available, or raise FeatureUnavailableError., Alias for check_available() — returns the entry or raises… (+3 more)

### Community 371 - "SetupWizardPage.js"
Cohesion: 0.13
Nodes (17): completeSetup(), createSecret(), detectHardwareForSetup(), detectModelsForSetup(), getPublicPath(), getSetupState(), saveSetupStep(), setBackendUrl() (+9 more)

### Community 372 - "ProviderConsole.jsx"
Cohesion: 0.08
Nodes (19): discoverLlmModels(), getLlmProviders(), getLlmStatus(), probeLlmProviders(), reloadLlmConfig(), setLlmProviderEnabled(), setLlmStrategy(), ALIASES (+11 more)

### Community 373 - "TrafficDirector"
Cohesion: 0.11
Nodes (11): get_director(), In-process traffic distribution and budget accounting for providers., EWMA latency in ms; never-sampled providers sort first. Returning -1.0 for an…, Clear all counters (tests only)., Return the process-singleton TrafficDirector., TrafficDirector, Tests for packages/ai/traffic_director.py — traffic distribution across…, `int(0.5)` is 0, and a cap of 0 makes `in_flight >= cap` true at zero in-flight… (+3 more)

### Community 374 - "webui/frontend/package.json"
Cohesion: 0.07
Nodes (26): @types/react, @types/react-dom, typescript, vite, @vitejs/plugin-react, dependencies, react, react-dom (+18 more)

### Community 375 - "keepalive.py"
Cohesion: 0.13
Nodes (26): _check_ollama(), _check_render(), _default_ollama_base(), _default_render_url(), _env_bool(), _loaded_ollama_prefixes(), _log(), _log_path() (+18 more)

### Community 376 - "CostAttributor"
Cohesion: 0.09
Nodes (16): CostAttributor, CostReport, get_cost_attributor(), Any, Tracks and attributes LLM costs per model, phase, and provider. Usage:: attr =…, Record a single LLM call's usage., Batch record multiple usage entries. Returns number recorded., Estimate USD cost for a given model and token count. Looks up the per-model… (+8 more)

### Community 377 - "_execute_skill_impl"
Cohesion: 0.10
Nodes (26): 3. Agile REST endpoints (`backend/server.py`), _execute_skill_impl(), _get_agile_manager(), _get_portfolio_manager(), Any, Live Graphify executor — queries the codebase knowledge graph. Order of…, Live council reviewer — deterministic, rules-based multi-perspective review…, Recommend skills based on detected systems and provisioned specialists. With no… (+18 more)

### Community 378 - "test_regression.py"
Cohesion: 0.10
Nodes (22): browser_login(), main(), Full desktop regression suite., Full mobile regression suite (navigation + key page loads)., Log in through the browser UI. Returns True on success., Comprehensive Playwright Regression Suite — LLM Relay Control Plane Covers…, API Key CRUD: create, copy, list, delete., Tasks: create, list, view. (+14 more)

### Community 379 - "parametrize"
Cohesion: 0.22
Nodes (9): _assigned_names(), parametrize, Source-text assertions cannot catch a NameError. Every test above reads the…, Runs only where `openai` is installed. It is not in requirements.txt —…, Catches a rename that updates the import but misses a use site., Top-level names this module assigns, so an *import* is not miscounted., _source(), TestOneListToFix (+1 more)

### Community 380 - "test_brain_liveness_dns_reason.py"
Cohesion: 0.12
Nodes (15): _is_dns_failure(), _probe_failure_reason(), BaseException, Turn a probe exception into an operator-actionable one-line reason. A dead…, True when *exc* (or anything it wraps) is a name-resolution failure., Exception, parametrize, A dead provider hostname must be reported as a DNS failure, not a raw errno.… (+7 more)

### Community 381 - "test_implement_agent_routing.py"
Cohesion: 0.07
Nodes (18): parametrize, Tests for the provider routing in ``.github/scripts/implement_agent.py``. The…, What the loop sends, and just as importantly what it does not., Anything but NVIDIA resolves its own default_model., response_cache keys on (model, messages, temperature, max_tokens, stop) — not…, The regression itself: a model id baked into this script., The router hands back parsed JSON, not SDK objects. Rewriting the loop for…, Guards the specific slip: attribute access on a parsed-JSON dict. (+10 more)

### Community 382 - "test_executive_advisory_api.py"
Cohesion: 0.16
Nodes (14): build_executive_advisory_router(), Any, APIRouter, _make_app(), FastAPI, tests/test_executive_advisory_api.py — auth and behaviour for…, Install an advisory whose LLM is a canned reply — no network., stub_advisory() (+6 more)

### Community 383 - "loop.py"
Cohesion: 0.04
Nodes (49): _check_extra_kwargs(), _enforce_signature(), _note_phase_end(), _note_phase_start(), loop.py — AgentRunner: plan → execute → verify loop with locked tool signatures., Raise TypeError if fn's signature drifts from the locked contract (Pydantic…, Raise TypeError on unknown kwarg (runtime extra='forbid' for non-Pydantic…, Summarise a long history and compact it. Asks the planner model to write a… (+41 more)

### Community 384 - "test_memory.py"
Cohesion: 0.15
Nodes (18): _now(), Any, Path, Save and restore agent state snapshots to/from a local directory. Usage:: mem =…, Persist *state* to disk under *session_id*. Returns the file path., Load a saved snapshot. Returns the state dict or *None* if absent., Return metadata for all saved snapshots (session_id, saved_at, path)., Delete a snapshot. Returns *True* if the file existed. (+10 more)

### Community 385 - "UserMemoryStore"
Cohesion: 0.11
Nodes (11): Return a previously saved memory value, or an empty string if absent., Persist a key/value pair to the user's profile store., Connection, Path, Return all stored key/value pairs for *user_id*., Delete a memory entry. Returns ``True`` if a row was removed., Persistent key/value store scoped per user. Thread-safe; uses a single SQLite…, Upsert a memory entry for *user_id*. (+3 more)

### Community 386 - "test_issue_triage.py"
Cohesion: 0.14
Nodes (19): _match_family(), Any, services/issue_triage.py — inbound GitHub issue triage. Closes the intake gap…, Classify a single GitHub issue payload and return the routing decision. Pure…, Fetch unlabeled open issues, triage each, and route them. Returns a summary…, run_triage_cycle(), _severity_for(), triage_enabled() (+11 more)

### Community 387 - "WorkflowPhase"
Cohesion: 0.11
Nodes (17): Enum, str, Drives a Task through the execution state machine with persistence. Usage::…, Advance task through the full phase sequence. Resumes from…, Execute a single phase and advance to the next., Run the logic for ``phase`` and return the next phase. Handles both sync and…, Record a plan stub (concrete planning happens inside the agent loop)., Route to the best specialist agent by domain and capability. (+9 more)

### Community 388 - "SprintMetrics"
Cohesion: 0.11
Nodes (11): Complete the sprint and record velocity., Calculate current sprint metrics., Velocity and burndown metrics for a sprint., Percentage of story points completed., Points per day needed to complete on time., Whether the sprint is on track to complete., SprintMetrics, Tests for SprintMetrics.health signal. (+3 more)

### Community 389 - "Initiative"
Cohesion: 0.06
Nodes (20): Initiative, PortfolioMetrics, Aggregate metrics across the whole portfolio., Create and register a new initiative, returning it., Add a pre-built Initiative (e.g. from the intelligence layer)., Look up an initiative by ID., Return initiatives sorted by WSJF (highest first). Cancelled initiatives are…, Lay the prioritised backlog onto a Now/Next/Later roadmap. Each horizon holds… (+12 more)

### Community 390 - "build_render_router"
Cohesion: 0.13
Nodes (23): build_render_router(), render_deploys(), render_health(), render_logs(), render_metrics(), render_ops_scan(), render_ops_status(), render_services() (+15 more)

### Community 391 - "seo_checks.py"
Cohesion: 0.10
Nodes (14): Static definition of a single audit check (catalog entry)., SeoCheckDefinition, auto_fixable_checks(), _c(), get_check(), list_checks(), services/seo_checks.py - SEO / GEO / AIO Check Catalog The authoritative…, Return the catalog definition for a check code (raises KeyError if unknown). (+6 more)

### Community 392 - "Deploy: FreeBuff Telegram bot (24×7)"
Cohesion: 0.09
Nodes (21): Agents, Environment variables, `/freebuff <task>`, Running 24×7, Telegram phone control, 1. Create the Telegram bot, 1. Hit the diagnostic endpoint, 2. Deploy (+13 more)

### Community 393 - "Claude Code + Qwen Local Setup"
Cohesion: 0.07
Nodes (27): 1. Set environment variables, 2. Start Claude Code, 3. Verify model routing, Anthropic SDK (Python), Architecture, "Authentication error" or 401, Claude Code + Qwen Local Setup, Claude Code reports "token limit exceeded" (+19 more)

### Community 394 - "traffic_director.py"
Cohesion: 0.09
Nodes (29): Pre-call budget checks, provider_max_parallel(), provider_max_rpm(), provider_max_tpm(), _provider_positive_float(), provider_weight(), Shared parse/validate for the numeric per-provider traffic budgets. Returns…, Return the operator-configured requests/min cap for *provider*, or None if… (+21 more)

### Community 395 - "reset_cache"
Cohesion: 0.40
Nodes (4): Drop every cached list, attempt record, and dead-model mark. For tests, and for…, reset_cache(), _clear_cache(), Discovery caches in a module global — never leak it between tests.

### Community 396 - "system_instruction"
Cohesion: 0.06
Nodes (18): extract_refusal(), is_strict(), Any, Structured output normalization across LLM providers. Translates the OpenAI…, Extract the ``refusal`` string from an OpenAI-format response body. Returns the…, Return True when the caller has requested strict schema enforcement. Strict…, Return a plain-English JSON instruction for a ``response_format`` dict. Returns…, system_instruction() (+10 more)

### Community 397 - "TestNoNvidiaFallbackIsRetired"
Cohesion: 0.22
Nodes (6): The defect was never confined to one file. Eight modules independently spelled…, ``(path, model_id)`` for every literal used as the env-var fallback., A regex that silently matched nothing would pass every assertion., ``PROVIDER_CANDIDATES['nvidia']`` is tried in order, so a dead entry is a…, Planner/executor/verifier fall back to a literal when no ``AGENT_*_MODEL`` is…, TestNoNvidiaFallbackIsRetired

### Community 398 - "_Recorder"
Cohesion: 0.19
Nodes (3): Injectable stand-ins for the three GitHub operations., _Recorder, TestReconciliation

### Community 399 - "ExecutiveAdvisory"
Cohesion: 0.15
Nodes (10): ExecOpinion, ExecutiveAdvisory, One executive's answer to the question., Routes a business question to the right executives and synthesises them., Return the roles whose keywords match *question*. Falls back to a sensible…, Consult the relevant executives and return a unified recommendation. With…, get_web_reach(), Module-level singleton, mirroring `agent.capability_registry.get_tool_registry`. (+2 more)

### Community 400 - "default_executives"
Cohesion: 0.11
Nodes (19): default_executives(), Executive, One C-suite persona: its identity and the domain it answers from., Return the built-in C-suite personas., AdvisoryConsultRequest, AdvisoryResponse, consult(), list_executives() (+11 more)

### Community 401 - "webui/router.py"
Cohesion: 0.13
Nodes (21): fastapi_staticfiles, AdminCommandBody, _anthropic_chat_payload(), _anthropic_text(), BrainPolicyUpdate, _provider_headers(), _provider_kind(), ProviderReorderBody (+13 more)

### Community 402 - "VoiceCommandInterface"
Cohesion: 0.15
Nodes (14): Any, Transcribe raw PCM *audio_bytes* to text., Record then transcribe in one call., Record → transcribe → return text for hands-free agent prompting. Usage:: vc =…, Record *duration_s* seconds of audio. Returns raw PCM bytes (int16 LE, 16 kHz…, _stub_result(), TranscriptionResult, VoiceCommandInterface (+6 more)

### Community 403 - "unsafe_target_reason"
Cohesion: 0.07
Nodes (38): browse_page(), Open *url* in a real browser, return its rendered text, and close. Fail-soft:…, Register the interactive-browser capability (agent/browser.py). Unlike…, _register_browser_tools(), _browse_page_tool(), Adding a new tool, build_tool_prompt(), _load_script_module() (+30 more)

### Community 404 - "Performance Analysis — local-llm-server"
Cohesion: 0.11
Nodes (18): 1. Rate Limiter Performance, 3. Model Router Performance, 5. Backend Server Performance, 6. Frontend Performance, 7. Streaming Performance, PERF-001 [HIGH] — Synchronous Lock in Async Context, PERF-002 [MEDIUM] — Rate Bucket Key Eviction is O(n), PERF-005 [MEDIUM] — Health Check on Every Request (Without Cache Miss) (+10 more)

### Community 405 - "test_hardware.py"
Cohesion: 0.13
Nodes (12): get_compatibility_label(), GPUDevice, HardwareProfile, ModelCompatibility, ModelCompatibilityLabel, Any, Enum, str (+4 more)

### Community 406 - "test_agent_chat_integration.py"
Cohesion: 0.13
Nodes (19): LogCaptureFixture, _fake_auth(), _fake_run_result(), _make_nim_providers(), AuthContext, MonkeyPatch, Path, Integration tests for /agent/chat endpoint and AGENT_RUNNER configuration.… (+11 more)

### Community 407 - "output_filter.py"
Cohesion: 0.07
Nodes (29): _count_remaining(), _filter_curl(), _filter_docker(), _filter_generic(), _filter_git(), _filter_ls(), _filter_npm(), _filter_pip() (+21 more)

### Community 408 - "TestPoliciesGovernanceStableClaim"
Cohesion: 0.20
Nodes (5): `policies_governance` may be STABLE only while enforcement is real. The same…, Each documented ceiling must fire from its own counter alone., LLM cost/tokens and spawn depth must be chargeable onto the budget — the wiring…, The runtime-dispatch seam must consult the same gate budget, so work handed to…, TestPoliciesGovernanceStableClaim

### Community 409 - "monitor_lib.py"
Cohesion: 0.12
Nodes (37): ArgumentParser, build_parser(), cmd_autostart_install(), cmd_status(), cmd_supervise(), cmd_wait(), _configure_logging(), main() (+29 more)

### Community 410 - "APIClient"
Cohesion: 0.15
Nodes (4): APIClient, Company Graph: create, scan website, view graph, onboarding, delete., Direct API calls for fast test setup and teardown., TestCompany

### Community 411 - "_migration_block"
Cohesion: 0.15
Nodes (11): _migration_block(), parametrize, Rows this migration poisoned must be able to recover. `needs_reset` is the only…, Groq's configured ids were not in the account's catalogue at all., A role preset the rotation cannot fall back to is a single point of failure., The body of the stale-BrainConfig startup migration., A retired id may be *listed* as one to migrate off, never assigned. The…, Not restated here. A third copy is what caused the outage. (+3 more)

### Community 412 - "test_daily_automation_2026_08_03.py"
Cohesion: 0.11
Nodes (16): _load_yaml(), tests/test_daily_automation_2026_08_03.py — Daily automation (2026-08-03).…, The rotation losing every entry is the outage this series began with., brain_config.py anthropic candidates must exactly match models.yaml (order and…, brain_config.py aerolink candidates must exactly match models.yaml (order and…, test_aerolink_candidates_match_yaml(), test_anthropic_candidates_match_yaml(), test_brain_config_nvidia_candidates_are_not_empty() (+8 more)

### Community 413 - "TestWorkflow"
Cohesion: 0.08
Nodes (6): Tests for agents/workflow_engine.py — SuperClaude Workflow Engine. Uses…, Tests for WorkflowEngine., Tests for Task dataclass., TestTask, TestWorkflow, TestWorkflowEngine

### Community 414 - "_undeclared"
Cohesion: 0.10
Nodes (15): _cases(), parametrize, Path, A shell variable a workflow never sets expands to empty, and says nothing. On…, A selector that matched nothing would make every assertion vacuous., A guard that cannot fail is not a guard. These reconstruct the 2026-08-29…, The specific regression: the squash subject that reached master., Declared is not the same as non-empty — `steps.issue` can be skipped. (+7 more)

### Community 415 - "TestStreamableHTTPTransport"
Cohesion: 0.12
Nodes (12): Decode a JSON-RPC response body from either JSON or an SSE stream. Streamable-…, SSE uses CRLF on the wire; the trailing \\r must not corrupt the JSON., Existing callers pass a base URL and expect /mcp appended., Render's URL already names the endpoint, so nothing is appended., Build an httpx.Response the client can parse, with a bound request., The plain-JSON path (/mcp-internal) must be unchanged., A Streamable-HTTP reply arrives as SSE data: frames., Progress notifications precede the response; the response wins. (+4 more)

### Community 416 - "1. The Rules"
Cohesion: 0.09
Nodes (22): 1. The Rules, 2. Standing Instructions — agent discipline, 3. What this repo is, 4. Architecture reference, 5. Bill of materials, 6. Key commands, 7. Environment variables, 8. Where else to look (+14 more)

### Community 417 - "reset_store"
Cohesion: 0.07
Nodes (33): A. Prime directive, B. Wiring — where things must go, C. Security invariants, D. Risky modules, G. Conventions that are not inferable from the code, H. Tests, I. Ship gates, J. Autonomy limits (+25 more)

### Community 418 - "Session Handoff — 2026-06-15"
Cohesion: 0.08
Nodes (24): Context the next session will need, Critical environment variables, Files changed today (for code archaeology), How to resume, Key files to know, Key labels, P0 — Add a regression test for the draft-PR safety guards, P1 — Watch Run 27481814863 for issue #504 and verify end-to-end (+16 more)

### Community 419 - "TASK 4 — End-to-end approval-gate test"
Cohesion: 0.08
Nodes (23): 3.1 — Confirm env vars on the **web** service, 3.2 — Confirm single-poller guard on the **worker**, 3.3 — Verify the bot responds (human-in-the-loop), 3.4 — TASK 3 acceptance, 4.2 — Trigger an outward-facing workflow run, 4.3 — Watch the run until it pauses, 4.4 — Confirm the Telegram message arrived, 4.5 — Press ✅ Approve (+15 more)

### Community 420 - "implement_agent.py"
Cohesion: 0.08
Nodes (27): main(), _nvidia_candidates(), _openai_tools_to_anthropic(), Any, Safely insert an entry under ## [Unreleased] without touching the rest of the…, Convert OpenAI function-calling tool schemas to Anthropic tool schemas., Run the implementation agent loop using Claude Opus via Anthropic SDK. Returns…, Curated NVIDIA model ids, when NVIDIA is the provider that will answer. Needed… (+19 more)

### Community 421 - "video_transcript.py"
Cohesion: 0.11
Nodes (23): caption_tracks(), extract_player_response(), fetch_transcript(), _get(), is_video_url(), parse_json3(), parse_timedtext_xml(), Extract a usable text transcript from a video URL, without an API key. Why this… (+15 more)

### Community 422 - "Company"
Cohesion: 0.05
Nodes (29): (2) & (3): Company creation flow / non-admin gate placement, A0. Fix live scanner crashes on real-world sites (`services/scanner.py`) — do first, Agent Prompt (paste this to start the implementation session), C. Defer company persistence to a final "Confirm" step + relocate the email gate, Context — bugs reported during manual QA, E. General bug sweep, Implementation Plan, Open question for @strikersam (+21 more)

### Community 423 - "AgentMessageBus"
Cohesion: 0.12
Nodes (8): AgentMessageBus, get_agent_bus(), Remove a subscription., Return all topics that have history., Return the module-level AgentMessageBus singleton., Pub/sub message bus for inter-agent communication. Agents subscribe to topics…, asyncio, TestAgentMessageBus

### Community 424 - "NIMConnectionPool"
Cohesion: 0.07
Nodes (21): [5.0.0], Removed, Security, Security, NIMConnectionPool, Any, AsyncClient, Persistent httpx.AsyncClient pool with circuit breaker and retry logic. Manages… (+13 more)

### Community 425 - "Bulkhead"
Cohesion: 0.10
Nodes (10): Bulkhead, Any, Semaphore, Per-provider concurrency isolation., Set a provider's slot count. Safe to call before any traffic., Hold one slot for the duration of the block. Yields ``False`` when no slot…, A saturated provider must not consume another provider's capacity., test_bulkhead_isolates_one_provider_from_another() (+2 more)

### Community 426 - "test_activation_api.py"
Cohesion: 0.13
Nodes (18): _client(), TestClient, Tests for activation_api — instance status, OpenAPI schema, and role route.…, GET /api/activation/settings is PUBLIC — non-admin users need to read the…, test_change_role_rejects_invalid_role(), test_change_role_requires_authentication(), test_change_role_returns_404_for_missing_user(), test_change_role_updates_existing_user() (+10 more)

### Community 428 - "test_service_token.py"
Cohesion: 0.08
Nodes (19): tests/test_service_token.py — N5 acceptance: service-token auth surface. Tests…, Near-miss tokens must not pass (no prefix-match, no fuzzy match)., After verification, the module must NOT hold the plaintext token — only the…, The token plaintext must NEVER appear in logs. Capture every log record emitted…, The module must use hmac.compare_digest (not ==) for the comparison — timing…, The service token must only gate a narrow allowlist of endpoints — not all of…, When SERVICE_TOKEN is rotated in the env, the new token must verify (within the…, Load services.service_token fresh in each test so env-var changes take effect. (+11 more)

### Community 429 - "test_telegram_diag_endpoint.py"
Cohesion: 0.08
Nodes (21): client(), tests/test_telegram_diag_endpoint.py — /api/telegram/diag HTTP endpoint.…, The endpoint does not require authentication (it's a diagnostic tool)., When TELEGRAM_BOT_TOKEN is unset, bot_token_set is False and prefix is (unset)., The live fields show a running poller and no webhook when healthy., The exact 'card arrives but tap does nothing' state is made visible: no poll…, A failed live lookup must degrade to a diagnostic, never 500 the endpoint., Build a TestClient against the FastAPI app with controlled env. (+13 more)

### Community 430 - "v3_auth.py"
Cohesion: 0.08
Nodes (41): _get_admin_email(), _get_admin_name(), _get_admin_secret(), login(), LoginRequest, LoginResponse, BaseModel, post (+33 more)

### Community 431 - "github_tools.py"
Cohesion: 0.18
Nodes (24): get_repo(), _get_token(), _get_user(), init_workspace(), list_branches(), list_prs(), list_repos(), BaseModel (+16 more)

### Community 432 - "LessonStore"
Cohesion: 0.16
Nodes (10): LessonStore, Any, Connection, Path, SQLite-backed store of failure lessons. Thread-safe, zero deps., refine() cannot cite what the store does not return., A known signature must not license arbitrary text., The attack the signature check alone did not stop. A workspace with a… (+2 more)

### Community 433 - "Findings"
Cohesion: 0.09
Nodes (22): E2E Tests, Findings, Immediate (Current Sprint), Integration Tests, Live/External Tests (skipped in standard CI), Missing Test Areas, Sprint 1, Sprint 2 (+14 more)

### Community 434 - "platform_controls_router.py"
Cohesion: 0.15
Nodes (22): _actor(), build_platform_controls_router(), _admin(), list_controls(), reset_control(), update_controls(), ControlUpdateBody, APIRouter (+14 more)

### Community 435 - "Local AI Stack with Docker"
Cohesion: 0.08
Nodes (23): 1. Clone and configure, 2. Start the stack (GPU), 3. Start the stack (CPU only), 4. Pull models (first run), 5. Access services, CPU Only, Data Persistence, Default (GPU) (+15 more)

### Community 436 - "Implementation Prompt: Rich TaskBoard + Agile Sprint Integration"
Cohesion: 0.09
Nodes (22): 1. Task model extensions (`tasks/models.py`), 2. New task endpoint (`tasks/api.py`), 4. TaskBoardScreen upgrade (`frontend/src/v5/screens/TaskBoardScreen.jsx`), 4a. "Needs Clarification" 7th column, 4b. Right-side detail panel, 4c. Sprint view mode toggle, 4d. Create-task modal enhancements, 4e. New "New Sprint" button (Sprint view only) (+14 more)

### Community 437 - "Telegram Bot Setup"
Cohesion: 0.08
Nodes (24): Admin commands (immediate, no confirmation), Admin commands with approval required, Approval Workflow, Authorization Model, Command Reference, Debugging message delivery, Debugging proxy connection failures, Linux (systemd) (+16 more)

### Community 438 - "CollectionLike"
Cohesion: 0.12
Nodes (12): get_storage(), packages/storage/factory.py — storage backend factory. Returns the appropriate…, Return the active storage backend. During migration, this delegates to the…, Reset the storage singleton (for tests)., reset_storage(), CollectionLike, Any, Protocol (+4 more)

### Community 439 - "audit"
Cohesion: 0.05
Nodes (39): audit(), get_audit_log(), Append an audit log entry. Never logs raw secrets — only secret IDs / masked…, Return recent audit log entries, newest first. Supports filtering by user_id,…, Go deeper, Quick start, Routes, Sol Advisor (+31 more)

### Community 440 - "_FakeSandbox"
Cohesion: 0.10
Nodes (9): fake_sandbox(), _FakeAsyncSandboxClass, _FakeCommands, _FakeFiles, _FakeSandbox, _make_fake_sandbox(), Any, Mimics e2b_code_interpreter.AsyncSandbox for tests. (+1 more)

### Community 441 - "analyze"
Cohesion: 0.04
Nodes (45): Analysis, analyze(), _classify(), _failure_table(), main(), Return the exhaustion :class:`Analysis` for a run's captured *output*., scripts/analyze_exhaustion.py Decide whether a run that ran out of retries has…, The verdict plus the human-readable justification behind it. (+37 more)

### Community 442 - "test_task_source_id_race.py"
Cohesion: 0.14
Nodes (19): _is_duplicate_key_error(), Exception, Create a task. Deduplicates by source_id if set (Charter G3). If a task with…, True if *exc* is a pymongo E11000 duplicate-key error. Checked by class name…, _FakeDuplicateKeyError, _mock_mongo_db(), asyncio, Exception (+11 more)

### Community 443 - "test_all_features.py"
Cohesion: 0.02
Nodes (52): auth_headers(), client(), TestClient, Comprehensive E2E smoke-test suite — covers every menu, page, and feature of…, TestClient for the backend FastAPI app (one per module for speed)., Login once and return auth headers for the entire module., TestActivation, TestActivity (+44 more)

### Community 444 - "._call"
Cohesion: 0.18
Nodes (4): Any, A message list that exceeds the pruner's threshold should be trimmed., TestApplyReasoningBudget, TestPruneChatMessages

### Community 445 - "test_v3_auth.py"
Cohesion: 0.17
Nodes (25): _configured_v3_email(), _configured_v3_password(), asyncio, skip, TestClient, Tests for v3 API authentication., Test login endpoint returns valid tokens., Test login with invalid credentials. (+17 more)

### Community 446 - "refine"
Cohesion: 0.16
Nodes (11): _one_line(), propose_entries(), Any, Turn qualifying lessons into candidate entries. A lesson qualifies only when it…, Promote repeated lessons into the spec. Returns the entries added. No-op unless…, Collapse a value to a single trimmed line. Entries are one Markdown list item…, refine(), _lesson() (+3 more)

### Community 447 - "test_research_coordinator.py"
Cohesion: 0.11
Nodes (3): _failing_handler(), Tests for agents.research_coordinator — multi-agent research orchestration., test_agent_execute_handler_failure_marks_failed()

### Community 448 - "openclaw_str_e_fix.py"
Cohesion: 0.15
Nodes (22): Call, ExceptHandler, _find_unsafe_str_call(), find_unsafe_str_calls(), visit_ExceptHandler(), fix_file(), fix_source(), _is_broad_except() (+14 more)

### Community 449 - "SandboxHandle"
Cohesion: 0.05
Nodes (28): 1.11 Multi-Agent Governance (10 / 100 / 1000 agents), Failure behaviour, detect_backend(), E2BBackend, LocalBackend, Any, RuntimeError, Raised when no backend can provide the requested sandbox. Callers treat this… (+20 more)

### Community 450 - "The fifteen strategies"
Cohesion: 0.10
Nodes (19): adaptive *(default)*, automatic_failover, Candidate selection, context_length_optimized, cost_optimized, highest_success_rate, least_loaded, LLM Router — routing guide (+11 more)

### Community 451 - "getBackendUrl"
Cohesion: 0.19
Nodes (16): getAccessToken(), getApiUrl(), getAuthHeaders(), getBackendUrl(), { getAccessToken, getAuthHeaders, getBackendUrl }, { getBackendUrl }, buildAgentStatusUrl(), buildAgentStreamUrl() (+8 more)

### Community 452 - "test_p0_roadmap_a4_a5_b2.py"
Cohesion: 0.15
Nodes (10): IntEnum, get_steering_injector(), Return the module-level SteeringInjector singleton., PrioritizedTask, Priority, Task priority levels. Lower number = higher priority (executed first)., Wrapper around a task payload with priority ordering., TestPrioritizedTask (+2 more)

### Community 453 - "test_north_mini_code.py"
Cohesion: 0.09
Nodes (15): north_mini_code_model_for(), Return the North Mini Code model id served by *provider*, else ``None``.…, best_model_for(), Return the name of the best model for a given task category. Falls back to…, tests/test_north_mini_code.py — North Mini Code 1.0 integration. Covers the…, The switch defaults ON so North is the default post-install., The agency/Hermes execution path defaults to North via the resolver., Only high/medium/low are honoured; anything else means 'unset'. (+7 more)

### Community 454 - "test_webui_provider_priority.py"
Cohesion: 0.27
Nodes (19): _bootstrap(), Path, tests/test_webui_provider_priority.py — Priority + reorder + brain-policy…, Reset the brain_config + brain_policy singletons before each test. V2.0 Phase 2…, _reset_brain_singletons(), test_admin_reorder_endpoint_requires_auth(), test_admin_reorder_endpoint_validates_body(), test_admin_reorder_endpoint_writes_priorities() (+11 more)

### Community 455 - "_Cursor"
Cohesion: 0.12
Nodes (5): _Cursor, _PendingCursor, Async iterator wrapping a list of dicts (already decoded from JSON)., Return a _Cursor (evaluated lazily on first await/iteration)., A cursor that fetches its data lazily on first use.

### Community 456 - "Screens"
Cohesion: 0.11
Nodes (19): 🛡 Admin — users & access, 🤖 Agents — autonomous team, 💬 Chat — unified assistant, 🏢 Company — operating context, 📊 Dashboard — system overview, 🩺 Doctor — diagnostics, 🐙 GitHub — repos & PRs, 📈 Intelligence — trends & competitors (+11 more)

### Community 457 - "_build_execution_request"
Cohesion: 0.24
Nodes (13): _build_execution_request(), Any, Build a minimal ``ExecutionRequest`` for plain-text → orchestrator.execute.…, admin_user(), _auto_approve(), non_admin_user(), Auto-approve policy for Telegram plain-text → orchestrator routing. Routine…, test_admin_execute_after_approval_gates() (+5 more)

### Community 458 - "test_memory_guard.py"
Cohesion: 0.12
Nodes (21): _load_malloc_trim(), memory_guard_enabled(), memory_guard_loop(), Parse the sweep interval, flooring it and tolerating a bad value. 180s is…, True unless explicitly disabled. Default on: the whole point is that the…, Resolve glibc ``malloc_trim``. Returns None when unavailable (non-glibc)., Run one gc sweep + malloc_trim. Returns objects collected. Never raises., Sweep + trim on a fixed interval until cancelled. (+13 more)

### Community 459 - "ProviderCircuit"
Cohesion: 0.15
Nodes (8): ProviderCircuit, Attempt to move from OPEN to HALF_OPEN after recovery timeout., Check if a request can be made through this circuit., Per-provider circuit breaker state machine., TestProviderCircuit, parametrize, Counting every sub-500 as a success meant the breaker could never open for the…, TestNimPoolCountsRateLimitsAsFailures

### Community 460 - "SyntheticDataPipeline"
Cohesion: 0.07
Nodes (19): get_synthetic_pipeline(), Any, Add a step result. Returns the sample if accepted, None if filtered out., Bulk-add samples from an agent session's step results. Each step result with…, Return samples filtered by minimum reward score., Export samples in Alpaca JSONL format. Returns the path to the exported file., Export samples in ShareGPT JSONL format. Returns the path to the exported file., Export all samples as a structured JSON array. Returns the path to the exported… (+11 more)

### Community 461 - "_process_task_callback"
Cohesion: 0.07
Nodes (32): Stable Core, Feature Matrix (spec §I — demotions needed), _process_task_callback(), Handle Approve/Reject inline-button presses for task execution gates. Callback…, _escape_md_v1(), Escape Telegram Markdown-v1 reserved chars in free-text fields. Markdown-v1…, _Captured, _make_fake_task() (+24 more)

### Community 462 - "_get"
Cohesion: 0.12
Nodes (9): _get(), Contract tests for the provider on/off endpoints. ``GET /api/brain/providers``…, Silently storing a typo'd id would leave a switch nothing can turn back on., The operator has to know WHY before deciding to switch it back on. The raw…, The response reaches the browser — a leaked key would be a disclosure., The switch has to reach the dispatcher, not just the listing., TestDisabledReasonIsReadableNextToTheSwitch, TestListing (+1 more)

### Community 463 - "test_cerebras_catalogue.py"
Cohesion: 0.13
Nodes (13): _agency_catalogue(), _cerebras_block(), _names_exactly(), parametrize, The first link of the failover chain was pointed at models that do not exist.…, Whole-id match. ``llama-3.3-70b`` must not match Groq's ``-versatile``., `config/models.yaml` wins at import, so a stale Python copy is invisible., 402 means nothing was measured. Undeclared capability must read as false.… (+5 more)

### Community 464 - "Path"
Cohesion: 0.09
Nodes (12): _isolate_env(), MonkeyPatch, Path, Old log + done signal + no .incomplete = complete (caller can cleanup the log…, Pin all env-overridable paths to tmp_path for hermetic tests., TestDownloadStatus, TestIsProcessAlive, TestReadPidFile (+4 more)

### Community 465 - "test_mostly_failed_steps.py"
Cohesion: 0.12
Nodes (22): _make_result(), _make_step(), tests/test_mostly_failed_steps.py — regression test for the "21/22 failed steps…, A BLOCKED judge verdict should never be success, regardless of steps., When mostly_failed, the output should contain a clear failure summary., 0 steps → no gate (division by zero avoided, total_steps < 4)., 6 failed + 2 applied = 75% failure, 2 applied < 3 → mostly_failed., Build a mock agent result dict (the shape InternalAgentAdapter expects). (+14 more)

### Community 466 - "test_v4_api.py"
Cohesion: 0.12
Nodes (22): auth_headers(), TestClient, tests/test_v4_api.py — Tests for the v4 dashboard API endpoints., Return the test client — reuses conftest client which has bootstrap., Get auth headers by logging in as admin via the admin API., GET /v4/status returns 200 with improvement_loop and self_healing keys., GET /v4/improvements returns 200 with active and resolved lists., GET /v4/tasks returns 200 with tasks array. (+14 more)

### Community 467 - "ServiceDaemon"
Cohesion: 0.14
Nodes (8): Validate configured paths., Check if proxy is running., Check if Ollama is running., Start the proxy server., Stop the proxy server., Get current status of all services., Load saved configuration., ServiceDaemon

### Community 468 - "LocalWorkspace"
Cohesion: 0.15
Nodes (10): LocalWorkspace, Path, Manages a local git clone of a GitHub repository. Clones are stored under…, Run a git command. Never uses shell=True., Clone the repo if it doesn't exist; pull if it does., Return the current working-tree diff (staged + unstaged)., Stage files and commit. paths=None stages everything; paths=[] raises., Create and checkout a new branch from base_branch. (+2 more)

### Community 469 - "HarnessEnrichment"
Cohesion: 0.14
Nodes (9): HarnessEnrichment, Any, Build a compact catalog of available runtime skills. Discovers from…, Standing instructions from the Continual Harness spec. Deliberately uncached:…, Inject enrichment blocks into a system prompt string. Appends blocks after the…, Auto-discovers skills and tools for agent prompt injection. Usage:: enrichment…, Build a compact, token-efficient catalog of available agent tools. Discovers…, Session Log (+1 more)

### Community 470 - "asyncio"
Cohesion: 0.11
Nodes (17): asyncio, write_file must write to SANDBOX_WORKDIR/path, not the sandbox's default cwd., read_file must read from SANDBOX_WORKDIR/path., apply_diff must write to SANDBOX_WORKDIR/path., run_command must cd into SANDBOX_WORKDIR before executing., An edit (write_file) must be visible to a subsequent read_file. This is the…, An edit (apply_diff) must be visible to a subsequent read_file., GUARDRAIL: E2B_API_KEY alone (without E2B_ENABLED=true) must NOT attach. This… (+9 more)

### Community 471 - "RateLimit"
Cohesion: 0.16
Nodes (10): Cerebras provider adapter — free, fast LLM (qwen-3-coder-480b)., Groq provider adapter — free, fast LLM (deepseek-r1-distill-llama-70b)., NVIDIA NIM provider adapter — wraps the existing provider_router logic. This is…, Ollama provider adapter — local LLM inference., ABC, RateLimit, packages/ai/provider.py — Provider abstraction interface. Every LLM provider…, Provider rate limit info. (+2 more)

### Community 472 - "AdaptivePermissions"
Cohesion: 0.18
Nodes (17): AdaptivePermissions, PermissionAssessment, Any, agent/permissions.py — Adaptive Permission Classifier Reads the session…, Convenience helper — True when the inferred level is read_write or full_access., Infer permission level from a list of chat messages (session transcript).…, Analyse *messages* and return a :class:`PermissionAssessment`., _msgs() (+9 more)

### Community 473 - "CoworkSession"
Cohesion: 0.16
Nodes (3): CoworkSession, A shared AI coding session with multiple human contributors. Manages turn-…, TestCoworkSession

### Community 474 - "LocalBrainStore"
Cohesion: 0.09
Nodes (22): LocalBrainStore, _now_iso(), Any, Connection, Return the desired + last-reported state for the admin UI., Operator flips the toggle. Persists + clears any prior lease. Returns the new…, Local daemon POSTs its heartbeat. If the operator's desired_state=on AND the…, `now_iso`: ISO-8601 string marking the reader's "now" — pass it in to stay… (+14 more)

### Community 475 - "AdminScreen.jsx"
Cohesion: 0.11
Nodes (17): Changed, Changed, changeUserRole(), createApiKey(), deleteApiKey(), deleteCompany(), setUserOnboarding(), AdminOnboardingPanel() (+9 more)

### Community 476 - "root"
Cohesion: 0.25
Nodes (7): _run(), Run real validation (byte-compile + scoped pytest) on this step's changes. Opt-…, get_status(), get, Serve the launcher UI., Get current service status., root()

### Community 477 - "Harness"
Cohesion: 0.14
Nodes (16): detect_harness(), Harness, harness_context_limit(), harness_stats(), HarnessProfile, Any, Enum, Detect which AI coding tool is calling the proxy. Checks in priority order: 1.… (+8 more)

### Community 478 - "_resolve_push_token"
Cohesion: 0.17
Nodes (13): _get_ceo_dispatcher(), Execute the plan via the selected specialist(s)., Verify execution results., Return the shared CEODispatcher singleton (importable for monkeypatching)., GitHub token used to push branches / open PRs during EXECUTION (#506).…, _resolve_push_token(), _clean_env(), tests/test_orchestrator_push_token.py — #506 push/PR token resolution.… (+5 more)

### Community 479 - "test_daily_digest.py"
Cohesion: 0.06
Nodes (34): aggregate_last_24h(), build_daily_digest(), compute_cutoff(), DigestPayload, DigestSummary, format_digest_markdown(), _md_escape(), _now_utc() (+26 more)

### Community 480 - "PriorityTaskQueue"
Cohesion: 0.14
Nodes (8): get_task_queue(), PriorityTaskQueue, Stop the worker pool gracefully., Return the module-level PriorityTaskQueue singleton., Asyncio-based priority queue with backpressure and worker pool. Features: -…, Higher-priority tasks should be processed before lower-priority ones., TestPriorityTaskQueue, handler()

### Community 481 - "TestLegacyRouterCacheTTL"
Cohesion: 0.13
Nodes (10): tests/test_anthropic_prompt_cache_ttl.py — extended-TTL prompt caching on the…, 1h TTL must not add the extended beta if caching is turned off — the extended…, The OpenAI→Anthropic translator applies the configured TTL to system., No env override → the block stays ``{"type": "ephemeral"}`` — no ``ttl`` key.…, ``5m`` is the API default. Sending ``ttl: "5m"`` is legal but redundant, and…, Anthropic only accepts ``5m`` and ``1h`` today. An unknown value is an operator…, ``ANTHROPIC_PROMPT_CACHING=off`` disables the cache_control block entirely —…, The legacy adapter sets ``anthropic-beta`` on the wire. ``1h`` TTL requires the… (+2 more)

### Community 482 - "_make_provider"
Cohesion: 0.21
Nodes (7): _make_provider(), Anthropic API shape for a content refusal (HTTP 200, stop_reason=refusal)., Only "default" mode is sent — never a custom string., _refusal_response(), _request(), TestRefusalLogging, TestServerFallbackPayload

### Community 483 - "_mock_provider_records"
Cohesion: 0.12
Nodes (12): _mock_provider_records(), tests/test_orchestrator_failover.py — Provider failover, brain resolution,…, End-to-end provider failover through the WorkflowOrchestrator., First provider fails → retry picks next → llm_provenance tracks the winner., The _failed_execute key in llm_provenance records the URLs that failed., A non-retryable error (e.g. ValueError) does not trigger failover., Return an AsyncMock that returns the given provider list., A TimeoutError is retryable and should trigger provider failover. (+4 more)

### Community 484 - "_P"
Cohesion: 0.19
Nodes (8): _ids(), _P, A provider with no latency sample must be able to earn one., The safety invariant: a shuffle may not promote a paid provider ahead of the…, With every provider idle a stable sort would send the whole burst to the first…, No explicit weights: the provider that has spent less of its minute should be…, Minimal provider stand-in — the director only needs ``provider_id``., TestOrdering

### Community 485 - "RegistrySkill"
Cohesion: 0.19
Nodes (6): Any, A skill fetched from a remote or local registry., Return ranked skill recommendations based on tech stack, active workflow types,…, RegistrySkill, Tests for RegistrySkill dataclass., TestRegistrySkill

### Community 486 - "SkillRegistry"
Cohesion: 0.17
Nodes (8): Central registry that indexes local + remote skills and provides context-aware…, Fetch skills from all configured GitHub registries. Returns count added., Force-refresh remote skills, bypassing TTL. Returns count added., Update the GitHub token used for authenticated API calls., Fetch one GitHub registry and return a list of RegistrySkill objects. Handles…, SkillRegistry, SkillRegistry method signature enforcement., TestSkillRegistryContracts

### Community 487 - "agile_api.py"
Cohesion: 0.24
Nodes (18): complete_sprint(), create_sprint(), _get_mgr(), get_velocity(), list_sprints(), Any, BaseModel, get (+10 more)

### Community 488 - "V3 API Migration Plan — LLM Relay Platform"
Cohesion: 0.10
Nodes (20): Acceptance Checks, Approach, Auth Flow (v3 JWT-based), Backward Compatibility, Current State Analysis, Data Model Changes, Database/Storage, Files to Create/Modify (+12 more)

### Community 489 - "Changelog"
Cohesion: 0.13
Nodes (17): serve_spa(), Changelog, Changelog, [5.0.0], Changelog, Changelog, Removed, Any (+9 more)

### Community 490 - "ChatScreen.jsx"
Cohesion: 0.14
Nodes (8): listProviderModels(), listProviders(), AVAILABLE_AGENTS, CHAT_PHASES, HistorySidebar(), ModelPicker(), relTime(), SUGGESTIONS

### Community 491 - "._order_group"
Cohesion: 0.22
Nodes (8): Unique identifier (e.g. 'nvidia', 'cerebras')., provider_id_of(), Any, Extract a provider id from a ProviderConfig dataclass or a plain dict., Return *providers* reordered according to the active strategy. ``group_key``…, Reorder one interchangeable group of providers., Ascending sort by *score* with a random tie-break. The tie-break is the point:…, Weighted random permutation — heavier providers tend to come first. Weight…

### Community 492 - "CEODispatcher"
Cohesion: 0.20
Nodes (13): CEODispatcher, Real CEO delegation: wake runtimes, fan out, and merge results., _base_result(), Tests for CEODispatcher._maybe_cross_verify (opt-in risky-module re-check)., The _BYPASS contextvar must not leak true after cross_verify finishes, or every…, Regression: AgentRunner.run() raises immediately unless legacy mode or the…, test_cross_verify_actually_runs_under_default_orchestrator_mode(), test_cross_verify_noop_when_disabled() (+5 more)

### Community 493 - "ClaudeCodeAdapter"
Cohesion: 0.21
Nodes (16): ClaudeCodeAdapter, Any, Adapter for Claude Code CLI — FIRST CLASS autonomous coding runtime., adapter(), asyncio, Tests for runtimes/adapters/claude_code.py, test_adapter_metadata(), test_execute_binary_not_found() (+8 more)

### Community 494 - "Fixed"
Cohesion: 0.07
Nodes (29): Normalise a raw planner JSON response into a consistent plan dict. Handles: -…, Fixed, Current Sprint Tasks, Fixed, 3a. Apply the slop-gate to the sibling auto-PR scripts ✅  (size: S), Highest-priority configured provider, or ``None`` if none is set. Shares…, _select_brain(), brain_candidates() (+21 more)

### Community 495 - "TestAddConversationCacheBreakpoints"
Cohesion: 0.15
Nodes (7): Fewer than stable_back+1 messages → no breakpoint added., Exactly stable_back+1 messages → breakpoint IS added., stable_back=3 means messages[-3] gets the breakpoint., Tool-result content arrays (role=user) get cache_control on last block., #1422 item 2 — verify (no code change): when the cache frontier lands on a…, Unit tests for ``_add_conversation_cache_breakpoints`` in isolation., TestAddConversationCacheBreakpoints

### Community 496 - "test_local_controller.py"
Cohesion: 0.06
Nodes (22): _env_defaults(), _fake_http_sequence(), fake_urlopen(), _fake_subprocess_run(), _import_controller(), tests/test_local_controller.py — unit tests for the local GLM-5.2 daemon. These…, The diag output must surface binary/model errors clearly., Pins the v3 fix: after the multi-port preamble probe finds colibri serving a… (+14 more)

### Community 497 - "test_openclaw_str_e_fix.py"
Cohesion: 0.10
Nodes (7): tests/test_openclaw_str_e_fix.py Root-cause fix for PR #1486: the OpenClaw…, str(other_var) that isn't the caught exception name must not be touched., A bare `except:` binds no name, so `str(exc)` inside one can never be the…, Even a broad except shouldn't relabel a client error as a server fault., test_bare_except_cannot_be_fixed_and_is_left_untouched(), test_broad_except_but_4xx_is_left_untouched(), test_detail_not_wrapping_the_caught_exception_is_left_untouched()

### Community 498 - "run_trend_analysis"
Cohesion: 0.18
Nodes (13): Tests for trend_analysis.py — last30days-style window over TrendWatcher (issue…, TestRunTrendAnalysis, TestWindow, BaseModel, trend_analysis.py — last30days-style trend analysis (issue #493). Adapts the…, True if the ISO-ish published date falls within the last N days.…, Fetch trends via TrendWatcher, filter to a 30-day window, persist summary., Write trends/trend_summary.md (and a dated copy); return the path. (+5 more)

### Community 499 - "test_unit5_ui_provider_surface.py"
Cohesion: 0.10
Nodes (15): tests/test_unit5_ui_provider_surface.py — UNIT 5 regression tests. Verifies…, The component must call ``providerLabel(p)`` rather than indexing a 4-entry…, The dropdown shows a [free]/[paid]/[local] tier tag so the operator can tell…, The <option> tag uses providerLabel(p), not PROVIDER_LABELS[]., The operator must be able to see what a key really serves. ``candidates`` is…, The GET endpoint response must list every BrainProvider Literal entry. Before…, Providers that were filtered out before UNIT 5 are now present. ``mistral``,…, A known paid provider is reported as tier=paid (was filtered before). (+7 more)

### Community 500 - "Fixed"
Cohesion: 0.03
Nodes (78): True if browser automation is enabled and Playwright is importable., Atomically delete a run-once row only while it is still unfired. Closes the…, _autonomy_bg_cycle(), _in_container(), Background CEO cycle + task dispatch. Runs fire-and-forget., Return True when running inside a container runtime. ``/.dockerenv`` alone…, Added, Added (+70 more)

### Community 501 - "WorkspaceManager"
Cohesion: 0.12
Nodes (9): get_workspace_manager(), _parse_iso(), Create, open, and lifecycle-manage per-job isolated workspaces. All workspaces…, Acquire the exclusive async lock for *ws*. Raises :exc:`WorkspaceLockError` if…, Remove expired workspaces that are cleanup_eligible and past cleanup_after.…, Remove and recreate the tmp directory for *ws*., Return counts of workspaces by status (scans disk, sync). Call ``await…, WorkspaceManager (+1 more)

### Community 502 - "Skill: modularity-review"
Cohesion: 0.10
Nodes (19): Acceptance Checks, Applying to This Repo, Further Reading, Modularity Findings Template, Part A: Reviewing Existing Code for Modularity Problems, Part B: Designing New Modular Boundaries, Skill: modularity-review, Step 1 — Map the dependency graph (+11 more)

### Community 503 - "Design Audit"
Cohesion: 0.10
Nodes (19): Code Quality, Color and Surfaces, Component Patterns, Content, Design Audit, Fix Priority, How This Works, Iconography (+11 more)

### Community 504 - "Findings"
Cohesion: 0.10
Nodes (19): API Documentation, Architecture Documentation, DOC-001 [HIGH] — No SECURITY.md, DOC-002 [HIGH] — No CONTRIBUTING.md, DOC-003 [HIGH] — No API.md / OpenAPI Export, DOC-004 [MEDIUM] — README.md is 31KB and Needs Pruning, DOC-005 [MEDIUM] — `REVIEW_AND_FIXES.md` and `AGENCY_CORE_V5_PROGRESS.md` are Unclear, DOC-006 [MEDIUM] — No DEPLOYMENT.md at Root (+11 more)

### Community 505 - "Skill: modularity-review"
Cohesion: 0.10
Nodes (19): Acceptance Checks, Applying to This Repo, Further Reading, Modularity Findings Template, Part A: Reviewing Existing Code for Modularity Problems, Part B: Designing New Modular Boundaries, Skill: modularity-review, Step 1 — Map the dependency graph (+11 more)

### Community 506 - "crispy_client.py"
Cohesion: 0.14
Nodes (18): cmd_approve(), cmd_artifacts(), cmd_build(), cmd_events(), cmd_reject(), cmd_status(), cmd_watch(), _get() (+10 more)

### Community 507 - "HarnessRegistry"
Cohesion: 0.17
Nodes (7): HarnessMetrics, HarnessRegistry, HarnessSessionRecord, _NoopDB, Any, BaseModel, Persistent registry of harnesses and their performance history. Stores session…

### Community 508 - "is_model_available"
Cohesion: 0.14
Nodes (16): Health check and availability filtering, _enabled(), get_available_models(), invalidate_cache(), is_model_available(), Force the next call to re-probe Ollama (useful in tests)., Return True if *model* is in the Ollama tag list (or health checks off).…, Return the set of model names currently present in Ollama. Returns an empty set… (+8 more)

### Community 509 - "McpCard.jsx"
Cohesion: 0.14
Nodes (9): getRenderHealth(), getRenderOpsStatus(), runRenderOpsScan(), api, BTN, McpCard(), NOTE(), relTime() (+1 more)

### Community 510 - "control_registry.py"
Cohesion: 0.18
Nodes (16): coerce(), _coerce_choice(), _coerce_number(), _coerce_toggle(), controls_by_group(), is_controllable(), Any, packages/config/control_registry.py — the platform-control API. The public… (+8 more)

### Community 511 - "Dynamic Model Routing"
Cohesion: 0.11
Nodes (19): Architecture, Built-in Claude → local alias table, Configuring fast_response routing, Configuring model preferences, Curl example, Dynamic Model Routing, Fallback execution, How automatic selection works (+11 more)

### Community 512 - "ControlsScreen.jsx"
Cohesion: 0.15
Nodes (15): getPlatformControls(), resetPlatformControl(), setPlatformControls(), { getPlatformControls, setPlatformControls, resetPlatformControl }, secondGroup, BANNER(), ControlRow(), ControlsScreen() (+7 more)

### Community 513 - "PortfolioScreen.jsx"
Cohesion: 0.11
Nodes (12): getPortfolioBoard(), refreshPortfolio(), btnStyle, HEALTH, HORIZONS, PortfolioScreen(), SOURCE, STATUS_COLOR (+4 more)

### Community 514 - "AgentJobSnapshot"
Cohesion: 0.22
Nodes (10): AgentJobSnapshot, Complete point-in-time view of a job, safe to serialise as API response., Build a snapshot from an ``AgentJob`` dataclass instance., cancel_chat_agent_job(), get_chat_agent_job(), Resume a paused agent job for *session_id*. When the agent loop reaches a…, resume_agent_chat_job(), _ResumeRequest (+2 more)

### Community 515 - "infra_cost.py"
Cohesion: 0.15
Nodes (14): compute_request_cost(), _float_env(), get_infra_config(), InfraConfig, load_infra_config(), project_session_cost(), Local infrastructure cost model for true TCO analysis. This module computes the…, Compute infrastructure cost for a single request given its latency. (+6 more)

### Community 516 - "build_matrix"
Cohesion: 0.17
Nodes (16): build_matrix(), _families(), main(), Any, scripts/generate_specialist_skill_matrix.py — Specialist × Skill matrix.…, Map family -> sorted list of test files that mention it (quoted token)., Return one row per family, derived entirely from code., render_markdown() (+8 more)

### Community 517 - "ai/registry.py"
Cohesion: 0.16
Nodes (16): all_models(), best_model_for(), get(), ModelInfo, models_by_provider(), packages/ai/registry.py — Model Registry. Centralized registry of all models…, Register the default free-tier models., Information about a specific model. (+8 more)

### Community 518 - "TestFailoverRegistryBaseUrls"
Cohesion: 0.40
Nodes (3): Registry base URLs must produce routes the provider actually serves., brain_failover must not drift from the catalog's base URLs., TestFailoverRegistryBaseUrls

### Community 519 - "steering_for_task"
Cohesion: 0.47
Nodes (3): Return recommended steering labels for a given task category. Used by the model…, steering_for_task(), TestSteeringForTask

### Community 520 - "build_workflow.py"
Cohesion: 0.30
Nodes (19): _c(), _get(), _header(), main(), _make_headers(), _phase_icon(), _post(), _print_phases() (+11 more)

### Community 521 - "context_plan_gate.py"
Cohesion: 0.14
Nodes (18): evaluate(), evaluate_path(), main(), _parse_args(), PlanDecision, Namespace, Path, Did the planner actually retrieve the source it reasoned about? (+10 more)

### Community 522 - "HybridSystem"
Cohesion: 0.21
Nodes (4): HybridSystem, Orchestrates the deterministic engine and LLM reasoner. Strategy: 1. Try…, Fraction of queries handled deterministically., TestHybridSystem

### Community 523 - "Page"
Cohesion: 0.12
Nodes (9): Page, Agents: list, view status., Chat: send message, view sessions, delete session, agent mode toggle., Runtimes: list, health, decisions, policy., Settings, Secrets, Features, Setup, GitHub, Activation., TestAgents, TestChat, TestRuntimes (+1 more)

### Community 524 - "TestBrainFailoverModelUpdates"
Cohesion: 0.18
Nodes (3): Verify the provider registry in brain_failover contains the 2026 model set., The rotation must equal the catalogue, which the probe keeps honest., TestBrainFailoverModelUpdates

### Community 525 - "test_tasks_cache_ttl_env.py"
Cohesion: 0.21
Nodes (19): MonkeyPatch, Round-trip tests for TASKS_LIST_ALL_CACHE_TTL_SEC env-var override in…, With a lowered cap, a value above the new cap falls back to default., Reload tasks.api after injecting TASKS_LIST_ALL_CACHE_TTL_SEC=value (or unset)., Values above the 1h upper bound in _safe_ttl fall back to default. Guards the…, Value equal to the 1h upper bound is honored (boundary case)., ``TASKS_MAX_CACHE_TTL_SEC`` env var overrides the cap module-level constant., _reload_tasks_api_with_env() (+11 more)

### Community 526 - "Agent Runtime Setup"
Cohesion: 0.12
Nodes (14): 1. Register Runtimes, 2. Verify Installation, 3. Access Agents via API, Agent Runtime Setup, Agents not appearing in API responses, Initial Setup, MongoDB Connection, No agents showing after registration (+6 more)

### Community 527 - "MemoryKernel"
Cohesion: 0.19
Nodes (5): Fact, MemoryKernel, Return most relevant facts. Simple substring match on content., SQLite-backed atomic fact store with Markdown mirror., Store a new atomic fact or reinforce an existing one.

### Community 528 - "SamAgent"
Cohesion: 0.13
Nodes (14): Any, SAM voice agent — the voice-controlled interface to the agency., Process a voice command and return SAM's spoken response. Args: text: The…, Call the NVIDIA NIM LLM (free tier) for SAM's response., Rule-based fallback when the LLM is unavailable., A single voice conversation session with SAM., SamAgent, SamConversation (+6 more)

### Community 529 - "_extract_tech_relevance"
Cohesion: 0.16
Nodes (7): _extract_tech_relevance(), Dynamic extraction: finds any tech keyword mentioned in the skill content,…, TEST-003 [MEDIUM] — Placeholder Tests with `pass`, Tests for _extract_tech_relevance() word-boundary matching., Integration-style tests for the recommendation path (no I/O)., TestExtractTechRelevance, TestRecommendLogic

### Community 530 - "HarnessAdapter"
Cohesion: 0.12
Nodes (8): HarnessAdapter, HarnessSpec, Any, Adapt harness-native requests to the local-llm-server internal format. Each…, Detect which harness sent this request from headers. Check order: explicit…, Convert a harness-native request dict to the local-llm-server format., Return the recommended model for this harness., Check whether a harness supports a specific capability.

### Community 531 - "Skill: fabric-patterns"
Cohesion: 0.11
Nodes (18): 1. Ensure Pattern Directory Exists, 2. List Available Patterns, 3. Retrieve a Pattern, 4. Apply a Pattern with Variables, 5. Stitch Patterns Together, 6. Create New Patterns, Acceptance Checks, Directory Structure (+10 more)

### Community 532 - "Analysis & Synthesis Instructions"
Cohesion: 0.11
Nodes (18): 1. Define the Atmosphere, 2. Map the Color Palette, 3. Establish Typography Rules, 4. Define the Hero Section, 5. Describe Component Stylings, 6. Define Layout Principles, 7. Define Responsive Rules, 8. Encode Motion Philosophy (+10 more)

### Community 533 - "Production Readiness Assessment — local-llm-server"
Cohesion: 0.11
Nodes (18): 1. Availability & Reliability, 2. Observability, 3. Deployment Architecture, 4. Configuration & Secrets, 5. Recovery & Backup, 6. Cloudflare Worker Audit, Current State, Current State (+10 more)

### Community 534 - "SetupChecker"
Cohesion: 0.17
Nodes (9): Path, Check if setup is needed and validate environment., Check if .env file exists., Check if keys.json file exists., Check if required Python packages are installed., Return list of missing setup items., Return True if any setup is needed., Print what needs setup. (+1 more)

### Community 535 - "Tween"
Cohesion: 0.16
Nodes (24): _a(), _assertThisInitialized(), cb(), dc(), Fo(), ga(), gb(), hb() (+16 more)

### Community 536 - "TestNormalizeResponseFormat"
Cohesion: 0.07
Nodes (14): _normalize_response_format(), Translate OpenAI ``response_format`` into Ollama's ``format`` field. For…, _build_builtin_model_map(), _get_model_map(), Build the built-in alias table — Nvidia NIM models when key is set, local…, Merge built-in defaults with MODEL_MAP env overrides (lazy, cached)., Daily automation tests — 2026-05-14 Covers three features implemented in this…, Payload without 'model' field should apply normalization (no '/' → local). (+6 more)

### Community 537 - "Skill: fabric-patterns"
Cohesion: 0.11
Nodes (18): 1. Ensure Pattern Directory Exists, 2. List Available Patterns, 3. Retrieve a Pattern, 4. Apply a Pattern with Variables, 5. Stitch Patterns Together, 6. Create New Patterns, Acceptance Checks, Directory Structure (+10 more)

### Community 538 - "run"
Cohesion: 0.17
Nodes (18): CreateIssue, build_body(), _failures(), find_tracking_issue(), _gh_ops(), create_issue(), list_issues(), update_issue() (+10 more)

### Community 539 - "db/__init__.py"
Cohesion: 0.11
Nodes (11): _LazyModuleProxy, db — storage abstraction layer (V2.0 Phase 5: real code moved to…, Loads the real module on first attribute access, then replaces itself., # IMPORTANT: keep these imports LAZY (inside __getattr__) so that a Mongo-only, ADR-007: Storage backend duck-typing over formal ABC, Consequences, Context, Decision (+3 more)

### Community 540 - "Admin Dashboard Guide"
Cohesion: 0.11
Nodes (19): Accessing the Dashboard, Admin API (Programmatic Access), Admin Dashboard Guide, Dashboard — healthy state, Dashboard — key created (one-time token flash), Dashboard — Langfuse diagnostic, Dashboard Layout, Login page (+11 more)

### Community 541 - ".create"
Cohesion: 0.16
Nodes (7): _hash_component(), Any, Create and return a new workspace in READY state. Raises…, Open an existing workspace from disk. Raises :exc:`WorkspaceNotFoundError` if…, _validate_id(), WorkspaceIDError, _claim_and_create_dirs()

### Community 542 - "Feature Guide"
Cohesion: 0.11
Nodes (18): 10. Langfuse Observability, 11. Coding Agent API, 12. Browser Admin UI, 13. Telegram Remote Control Bot, 14. Tunnel — Permanent Static URL via ngrok, 15. CORS Support, 16. Streaming Support, 17. Workspace Isolation (+10 more)

### Community 543 - "scripts/doctor.py"
Cohesion: 0.27
Nodes (17): NamedTuple, Check, check_core_deps(), check_env(), check_git(), check_mongo(), check_node(), check_ollama() (+9 more)

### Community 544 - "control_overrides.py"
Cohesion: 0.14
Nodes (18): _as_int(), _control_state(), effective_value(), _policy_updates(), packages/config/control_overrides.py — DB-persisted overrides for platform…, Push the *changed* routing keys into the live runtime manager. Only the keys…, Build the ``update_policy`` kwargs for exactly the *changed* keys., The value *spec* currently resolves to, following override → env → default. (+10 more)

### Community 545 - "Delegation Plan (agent-ready work packages)"
Cohesion: 0.11
Nodes (18): Delegation Plan (agent-ready work packages), Findings, http://127.0.0.1:8899/, Page Details (worst first), Pillar Scores, `seo-fix-canonicals` - Fix Canonicals findings: 1 finding type(s) across 1 URL hit(s), `seo-fix-content` - Fix Content findings: 1 finding type(s) across 1 URL hit(s), `seo-fix-geo` - Fix GEO findings: 5 finding type(s) across 5 URL hit(s) (+10 more)

### Community 546 - "run_proxy.sh"
Cohesion: 0.11
Nodes (15): run_ollama.sh script, AIDER_BASE_URL, GOOSE_BASE_URL, HERMES_BASE_URL, LOG_LEVEL, OLLAMA_BASE, OPENCODE_BASE_URL, PROXY_PORT (+7 more)

### Community 547 - "agency_fix.py"
Cohesion: 0.04
Nodes (63): date, .github/scripts/provider_policy.py — Read the durable provider policy from the…, Reset the cached policy (test helper)., reset_cache(), Popen, build_prompt(), call_llm(), collect_context() (+55 more)

### Community 548 - "LocalLLMSetup"
Cohesion: 0.18
Nodes (7): LocalLLMSetup, Update .env file with configuration., Check if services are already running., Start the proxy server., Scan for local models., Scan the models folder for available models., Configure which models to use for agent roles.

### Community 549 - "test_autonomy_pipeline_regressions.py"
Cohesion: 0.25
Nodes (5): asyncio, Regression tests for the autonomy pipeline bugs that blocked the agency from…, # NOTE: do NOT set STORAGE_BACKEND at module level — it would pollute every, End-to-end: activate_company() on a fresh company creates all 6…, test_company_agency_activate_creates_all_schedules()

### Community 550 - "fastapi_testclient"
Cohesion: 0.05
Nodes (35): fastapi_testclient, client(), TestClient, tests/test_autonomy_status.py — public /api/autonomy/status readiness probe.…, No auth required; response carries the readiness contract keys., The probe carries the loop fleet readiness summary (loop-audit)., Without NVIDIA key AND without Ollama, the probe must report no_brain., When NVIDIA is absent but Ollama is configured, report brain as ollama. (+27 more)

### Community 551 - "test_brain_patch_service_token.py"
Cohesion: 0.18
Nodes (18): clean_store(), _clear_overrides(), _make_client_with_user(), tests/test_brain_patch_service_token.py — N5 acceptance: PATCH…, N5 acceptance: no service token + no user session → 401 (not 200)., N5 regression: the existing dashboard path (no service token, non-admin user)…, N5 regression: the existing admin dashboard path (no service token, admin user)…, Reset the brain config store + point SQLITE_DB_PATH at a tmp path. (+10 more)

### Community 552 - "test_ai_insights.py"
Cohesion: 0.18
Nodes (12): EngagementMetrics, How many distinct tools each user has touched., Track adoption and engagement across the engineering org. DX report key…, Count distinct sessions per user. A session ends when there's a gap of more…, Tests for agents.ai_insights — AI-Assisted Engineering metrics., test_engagement_dau_counts_unique_users(), test_engagement_dau_zero_when_no_events(), test_engagement_record_appends() (+4 more)

### Community 553 - "TestSelfHealingInfrastructureClassification"
Cohesion: 0.19
Nodes (4): _classify_failure correctly identifies infrastructure errors., MongoDB timeout is an infra error, not a generic timeout., MongoDB 'connection refused' is infra, not generic network., TestSelfHealingInfrastructureClassification

### Community 554 - "Fixed"
Cohesion: 0.27
Nodes (9): Convenience: the canonical text response, whether success or failure., Fixed, _get_github_token_for_user(), Fetch GitHub token for user from secrets store or environment., Fixed, MonkeyPatch, Path, test_new_scaffolds_pattern() (+1 more)

### Community 555 - "CostLine"
Cohesion: 0.18
Nodes (14): CostLine, FinancialAgent, The agentic CFO: ingests metrics + cost lines and emits recommendations.…, A single budget line item (e.g. 'GPU compute', 'API credits')., Revenue per dollar spent. Higher is better., test_agent_explain_returns_human_readable(), test_agent_holds_strategic_low_roi_lines(), test_agent_investigates_uppercase_cogs_categories() (+6 more)

### Community 556 - "router_factory"
Cohesion: 0.16
Nodes (19): _big_request(), _ok(), A conversation comfortably past the metered provider's per-minute budget.…, A 131k window behind a 4k budget is a 4k ceiling., Routing around the low ceiling beats compressing to fit it., Production's case: every reachable provider has a low ceiling. Nothing can be…, No compression tax on requests that already fit., Key scope means the sibling key gets a turn — that is the point of it. (+11 more)

### Community 557 - "TestRoutes"
Cohesion: 0.16
Nodes (7): _install_service(), Tests for agents/portfolio_api.py — the v5 portfolio board API. Loads the…, A materializer exception must not break /refresh (the board still returns), and…, Install a PortfolioService whose portfolio is fixed (no rebuild)., _seeded_manager(), TestBoardPayload, TestRoutes

### Community 558 - "TestLangfuseSessionId"
Cohesion: 0.14
Nodes (8): emit_chat_observation must accept session_id without error., When session_id is provided, it should appear in the meta dict passed to emit…, _emit_langfuse_http_sync must have session_id parameter., _emit_sdk must have session_id parameter., When session_id provided, trace body must include sessionId field., When session_id provided, trace tags must include session:<id>., TestLangfuseSessionId, fake_post()

### Community 559 - "validate_session_id"
Cohesion: 0.16
Nodes (5): TestSessionIdValidation, WorkspaceNotFoundError should not expose the base root in error messages., TestNoInternalPathLeakage, Validate and return a session ID, or raise InvalidSessionIdError., validate_session_id()

### Community 560 - "Workspace"
Cohesion: 0.18
Nodes (9): _iso_now(), _iso_offset_hours(), Enum, str, Open a workspace for resumption. Only READY or PAUSED workspaces may be…, Update *ws* status and persist the manifest., Update last_heartbeat timestamp and persist., Workspace (+1 more)

### Community 561 - "ErrorInterceptorMiddleware"
Cohesion: 0.19
Nodes (10): _dispatch_async(), _run(), ErrorInterceptorMiddleware, Any, BaseHTTPMiddleware, Exception, Request, Catch 5xx responses and auto-create fix tasks via the self-healing agent.… (+2 more)

### Community 562 - "BudgetOptimizer"
Cohesion: 0.15
Nodes (10): BudgetOptimizer, Reallocate budget across cost lines to maximize total ROI under a fixed budget…, Return a new list of CostLine objects redistributed to fit `new_budget`.…, Dollar savings if reallocated to `target_budget`., Return the bottom-n cost lines by ROI (candidates to cut)., test_optimizer_lowest_roi_lines(), test_optimizer_reallocate_favors_high_roi(), test_optimizer_reallocate_respects_total_budget() (+2 more)

### Community 563 - "AgentsScreen.jsx"
Cohesion: 0.19
Nodes (11): createAgent(), AgentCard(), AgentsScreen(), BUILTIN_AGENT_DEFS, mapBackendAgent(), NewAgentForm(), PIPELINE_MODES, relTime() (+3 more)

### Community 564 - "memory_consolidation.py"
Cohesion: 0.36
Nodes (7): ConsolidationPhase, MemoryKind, Enum, str, Dream Memory Consolidation — pattern consolidation across AI sessions. Inspired…, What kind of memory artifact this is., Current phase of the consolidation lifecycle.

### Community 565 - "Comprehensive Skill Index (By Category)"
Cohesion: 0.11
Nodes (17): 10. Domain (Modelling, Training, Infra), 1. Planning and Implementation, 2. Code Quality, Architecture, and Audits, 3. State Management and Git Flow, 4. Memory, Knowledge, and Context Tuning, 5. Research, Browsing, and External Intel, 6. Session Lifecycle and Workflow, 7. Style and Craft Polish (UI / Docs / Tone) (+9 more)

### Community 566 - "Agent Skill: Principal UI/UX Architect & Motion Choreographer (Awwwards-Tier)"
Cohesion: 0.11
Nodes (17): 1. Meta Information & Core Directive, 2. THE "ABSOLUTE ZERO" DIRECTIVE (STRICT ANTI-PATTERNS), 3. THE CREATIVE VARIANCE ENGINE, 4. HAPTIC MICRO-AESTHETICS (COMPONENT MASTERY), 5. MOTION CHOREOGRAPHY (FLUID DYNAMICS), 6. PERFORMANCE GUARDRAILS, 7. EXECUTION PROTOCOL, 8. PRE-OUTPUT CHECKLIST (+9 more)

### Community 567 - "Component Map"
Cohesion: 0.12
Nodes (15): Architecture Audit — local-llm-server, Architecture Diagram, Component Map, Layer 10 — WebUI (`webui/`), Layer 11 — Infrastructure, Layer 1 — API Proxy (`proxy.py`, 1719 lines), Layer 4 — Agent System (`agent/`), Layer 5 — Backend Server (`backend/server.py`) (+7 more)

### Community 568 - "Architecture Overview — local-llm-server"
Cohesion: 0.11
Nodes (18): `admin_auth.py` + `admin_gui.py`, `agent/`, Architecture Overview — local-llm-server, `chat_handlers.py`, Deployment, Feature Maturity Tiers, `handlers/anthropic_compat.py`, High-Level Architecture (+10 more)

### Community 569 - "Pending Activities — Implementation Playbook"
Cohesion: 0.17
Nodes (10): Definition of done (per task), How to verify the whole thing end-to-end (local, no external infra), P0 — Make autonomy real in production, P2 — ECC harness & polish, Pending Activities — Implementation Playbook, Task 10 — ECC cross-harness adapter (currently PLANNED only), Task 1 — Build the actual Kimi web-bridge service (free inference, no API key), Task 2 — Always-on Worker service (24×7 without the web process) (+2 more)

### Community 570 - "Platform Guide — the full tour"
Cohesion: 0.05
Nodes (42): 1. Clone and install, 2. Configure, 3. Start the backend, 4. Start the frontend (development), 5. Onboard your first company, 6. Connect your AI coding tools (optional), Architecture, Backfilling existing issues (+34 more)

### Community 571 - ".submit"
Cohesion: 0.16
Nodes (6): Queue, Any, Start the worker pool., Submit a task to the queue. Returns True if accepted, False if rejected due to…, Return queue introspection data for status endpoints., Subscribe to progress events for a specific task. Returns an asyncio.Queue that…

### Community 572 - "Part A — Health Report"
Cohesion: 0.11
Nodes (17): F1 — CLAUDE.md documents an architecture that no longer exists, F2 — 15 skills have no frontmatter description, F3 — Direct `os.environ` reads outside config modules, F4 — `print()` in importable production modules, F5 — graphify hook nags every session, F6 — God files, Healthy signals, P1 — Refresh CLAUDE.md and AGENTS.md to match the real architecture (+9 more)

### Community 573 - "WorkflowScreen.jsx"
Cohesion: 0.13
Nodes (15): Fixed, approveWorkflow(), buildWorkflow(), cancelWorkflow(), getWorkflowRun(), getWorkflowRuns(), rejectWorkflow(), btn() (+7 more)

### Community 574 - "sync_readme_gallery.py"
Cohesion: 0.20
Nodes (15): main(), _out_dir(), Path, Generate Web UI screenshots for README/docs. Requires: pip install playwright…, build_gallery(), GallerySection, main(), Path (+7 more)

### Community 575 - "CircuitBreakerOpenError"
Cohesion: 0.50
Nodes (4): CircuitBreakerOpenError, RuntimeError, Raised when a request is blocked by an open circuit breaker., TestCircuitBreakerOpenError

### Community 576 - "chat_completions"
Cohesion: 0.20
Nodes (14): chat_completions(), ChatCompletionRequest, _content_to_str(), _ContentPart, health(), list_models(), _Message, BaseModel (+6 more)

### Community 577 - "_RedisBackend"
Cohesion: 0.22
Nodes (5): Redis-backed shared state using SET NX / DELETE / SETEX / INCR+EXPIRE., Lazy-create the Redis client (imported on first use so a missing ``redis``…, Clear all cooldown entries (for test teardown)., Clear all probe-lock entries (for test teardown). Mirrors…, _RedisBackend

### Community 578 - "._cannot_list"
Cohesion: 0.16
Nodes (9): A refused catalogue says nothing about whether a named model answers. On…, A provider whose /models refuses but whose /chat works., No ``--model`` given: the provider's declared default is the target., Answered-but-unlistable is a different fact from unreachable. Collapsing the…, The relaxation must not turn a real failure into a pass., Nothing was asked to be called, so nothing proved the provider is up., Rule 6, re-asserted on the branch this change introduces., A call that was never sent is not evidence that anything answered.… (+1 more)

### Community 579 - "TestAnthropicToolListCaching"
Cohesion: 0.34
Nodes (3): input_schema passthrough — native Anthropic tools should not be wrapped again., AnthropicProvider.build_payload caches the tool list when prompt_caching=True…, TestAnthropicToolListCaching

### Community 580 - "_override_user"
Cohesion: 0.25
Nodes (6): _override_user(), skipif, Force backend.server.get_current_user to return ``user``., A non-admin's auto_approve=true is ignored — the run still pauses at HITL., approved_by comes from the session, not a client-supplied string., TestOrchestratorEndpointScoping

### Community 581 - "agent/workspace.py"
Cohesion: 0.29
Nodes (12): _get_workspace_lock(), _load_workspace(), BaseModel, Lock, Path, agent/workspace.py — Isolated workspace lifecycle management. Every agent…, Return the process-wide asyncio.Lock for *root*, creating it if needed., _read_manifest() (+4 more)

### Community 582 - "TestStopSlopChecker"
Cohesion: 0.11
Nodes (10): Should detect phrases case-insensitively, Should detect throat-clearing phrases, Should return no issues for clean text, Strict mode should detect passive voice, Should detect multiple types of tells in one text, Issues should have helpful suggestions, Should detect business jargon, Should remove throat-clearing phrases (+2 more)

### Community 583 - "AIToolMetrics"
Cohesion: 0.15
Nodes (10): AIToolMetrics, Per-tool quality metrics: which AI tools actually deliver value? Tracks…, Average response latency in ms for the given tool., Output tokens per input token (higher = more verbose responses). Useful for…, Event counts grouped by ToolKind., test_tool_metrics_acceptance_rate(), test_tool_metrics_acceptance_rate_unknown_tool(), test_tool_metrics_average_latency() (+2 more)

### Community 584 - "ReasoningResult"
Cohesion: 0.19
Nodes (7): Any, Attempt to reason via the fallback_handler., Route a query through the hybrid pipeline and record the result., Output from either the deterministic engine or LLM reasoner., Run rules against inputs. Returns first match, or None., ReasoningResult, TestReasoningResult

### Community 585 - "harness_spec.py"
Cohesion: 0.16
Nodes (16): build_block(), _flag(), _int_env(), _known_entry_texts(), Path, agent/harness_spec.py — the Continual Harness: a persistent, cited spec.…, Absolute path of the harness spec for a workspace., Recorded lessons as ``{signature: {acceptable text, ...}}``. The citation binds… (+8 more)

### Community 586 - "record_step_failures"
Cohesion: 0.14
Nodes (20): _get_store(), Formatted prompt block of recent lessons, or '' when none exist., Persist a lesson for every failed step in a run. Never raises., recent_lessons_block(), record_step_failures(), Configuration, Continual Harness (`agent/harness_spec.py`), Flow (+12 more)

### Community 587 - "_first_paragraph"
Cohesion: 0.12
Nodes (13): _extract_tags(), _first_paragraph(), _fmt_name(), AsyncClient, Path, Fetch a registry whose skills live in arbitrarily nested directories. Uses the…, Fetch one nested SKILL.md via raw.githubusercontent.com., Fetch a flat .md file and convert it to a RegistrySkill. (+5 more)

### Community 588 - "cowork_session.py"
Cohesion: 0.15
Nodes (9): ContributorState, Enum, str, Claude Cowork — shared AI coding sessions with real-time sync. Enables multiple…, Role within a cowork session., Current phase of a cowork session., State of a single contributor within a session., SessionPhase (+1 more)

### Community 589 - "SKILL: Industrial Brutalism & Tactical Telemetry UI"
Cohesion: 0.12
Nodes (16): 1. Skill Meta, 2.1 Swiss Industrial Print, 2.2 Tactical Telemetry & CRT Terminal, 2. Visual Archetypes, 3.1 Macro-Typography (Structural Headers), 3.2 Micro-Typography (Data & Telemetry), 3.3 Textural Contrast (Artistic Disruption), 3. Typographic Architecture (+8 more)

### Community 590 - "Skill: data-quality-audit"
Cohesion: 0.12
Nodes (16): 1. Token Length Distribution, 2. Deduplication Check, 3. Tokenizer Fertility Check, 4. Special Token Consistency, 5. Language Detection (if langdetect available), 6. Content Quality Signals, Background (Why This Matters), Checks Performed (+8 more)

### Community 591 - "What "Slop" Looks Like"
Cohesion: 0.12
Nodes (16): Acceptance Checks, Category 1 — Obvious Comments, Category 2 — Phantom Abstractions, Category 3 — Defensive Checks for Impossible Cases, Category 4 — Speculative Generality, Category 5 — Verbose Variable Names, Category 6 — Unasked-For Boilerplate, Instructions (+8 more)

### Community 592 - "local_brain_router.py"
Cohesion: 0.19
Nodes (16): get_local_brain_state(), HeartbeatBody, post_local_brain_heartbeat(), post_local_brain_toggle(), Any, BaseModel, get, post (+8 more)

### Community 593 - "Added"
Cohesion: 0.16
Nodes (13): clear_cost_attribution(), cost_table(), Return the active per-model cost table (USD per million tokens). Useful for…, Reset in-memory cost attribution counters. Admin-only., Added, Added, buildGraphElements(), clear_stats() (+5 more)

### Community 594 - "Section-by-Section Acceptance Criteria"
Cohesion: 0.12
Nodes (16): 467 Final Acceptance Criteria, §A — Company Graph + Onboarding, §B — 34 Specialist Families, §C — ECC, Obsidian, Graphify, Council Review Wiring, §D — Direct Chat as Control Center, Definition of Done, §E — Workflow Engine as Canonical Backbone + Worktree Isolation, §F — Doctor Full Check List (+8 more)

### Community 595 - "ResearchAgent"
Cohesion: 0.23
Nodes (11): Run the task and return it (mutated) with status set., A specialized agent that executes tasks of a specific role., ResearchAgent, _echo_handler(), Test handler that echoes the task question + context keys., test_agent_can_handle_matching_role(), test_agent_cannot_handle_other_roles(), test_agent_execute_success_increments_counter() (+3 more)

### Community 596 - "Provider"
Cohesion: 0.14
Nodes (10): packages.ai — provider abstraction, model registry, and failover manager., ProviderManager, packages/ai/manager.py — ProviderManager. Single entry point for all LLM calls.…, Coordinates provider selection, failover, and health., Return providers sorted by priority (lowest = highest priority)., Provider, Base interface every provider must implement. Implementations live in…, Lower = higher priority in the fallback chain. (+2 more)

### Community 597 - "redact_connection_url"
Cohesion: 0.17
Nodes (7): packages/security/redact.py — strip secrets out of strings before they reach a…, Strip embedded credentials from a connection URI before logging it. Covers both…, redact_connection_url(), Regression test: production leaked a live MongoDB password in plaintext.…, Integration coverage: the actual log lines this module emits must never carry…, TestLoggingCallSitesRedactCredentials, TestRedactConnectionUrl

### Community 598 - "TestEstimateTokensForMessages"
Cohesion: 0.15
Nodes (4): _estimate_tokens_for_messages(), Estimate input token count for an Anthropic-format message list. Uses a simple…, Unit tests for handlers.anthropic_compat._estimate_tokens_for_messages., TestEstimateTokensForMessages

### Community 599 - "agent_readiness_audit.py"
Cohesion: 0.21
Nodes (15): _grade(), main(), PillarResult, scripts/agent_readiness_audit.py — score this repo's fitness for autonomous…, ReadinessReport, run_audit(), score_build_system(), score_dev_environment() (+7 more)

### Community 600 - "sync_ngrok.py"
Cohesion: 0.24
Nodes (15): detect_ngrok_url(), dim(), fail(), header(), info(), main(), ok(), patch_platform_brain_via_switch_brain() (+7 more)

### Community 601 - "test_ci.sh"
Cohesion: 0.15
Nodes (16): ADMIN_EMAIL, ADMIN_PASSWORD, API_KEYS, cleanup(), DB_NAME, fail(), LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY (+8 more)

### Community 602 - "TestRuntimeControl"
Cohesion: 0.15
Nodes (7): Test runtime start/stop endpoints return informational payloads in remote…, Get authentication token for admin user, GET /runtimes/ should return list of runtimes, POST /runtimes/{id}/start should return non-blocking informational payload in…, POST /runtimes/stop-all should return non-blocking informational payload, PUT /runtimes/policy should work with valid auth, TestRuntimeControl

### Community 603 - "GuardrailEngine"
Cohesion: 0.09
Nodes (13): GuardrailEngine, GuardResult, Any, Configurable safety rail engine for LLM inputs and outputs. Supports: -…, Check user input against input safety rules. Returns a GuardResult with…, Check model output against output safety rules. Returns a GuardResult with…, Unified check method. direction = 'input' or 'output'., Return guardrail statistics. (+5 more)

### Community 604 - "test_new_features_e2e.py"
Cohesion: 0.08
Nodes (29): APIRequestContext, playwright_sync_api, do_login(), fail(), ok(), Page, Navigate to a page and verify it loads without errors., Browser-based E2E tests — runs with Playwright against a live LLM Relay… (+21 more)

### Community 605 - "test_frontend_deployment_guards.py"
Cohesion: 0.18
Nodes (16): SetupWizardPage must render <input type='checkbox'> for each provider toggle., Step 3 runtime config must render checkboxes for each runtime., OAuth must originate from the operator-configured backend, never a hardcoded…, index.css must override appearance:none for checkboxes/radios., The checkbox appearance override must NOT set appearance:none (that would keep…, The checkbox appearance override must use 'auto' to request native rendering.…, _read(), test_api_redirects_respect_public_and_backend_paths() (+8 more)

### Community 606 - "test_health_endpoints.py"
Cohesion: 0.15
Nodes (16): _make_fake_client(), Exception, Tests for /health, /live, and /api/health endpoints., When Ollama is down, /api/health should also return a degraded status., Return a context-manager-compatible mock for httpx.AsyncClient., Container liveness probe must always return 200., Health endpoint exists and returns a JSON body., Health endpoint includes provider states when ProviderRouter is wired in. (+8 more)

### Community 607 - "test_keepalive.py"
Cohesion: 0.23
Nodes (23): Maintenance, Maintenance, Maintenance, Maintenance, Maintenance, Maintenance, Maintenance, Path (+15 more)

### Community 608 - "test_openclaw_endpoints.py"
Cohesion: 0.12
Nodes (10): client(), tests/test_openclaw_endpoints.py — OpenClaw HTTP + WebSocket endpoint tests., After pairing, ping command returns pong., Unknown command returns error., WebSocket with wrong token is rejected (connection closed)., WebSocket with correct token pairs successfully., test_websocket_pairing_accepts_correct_token(), test_websocket_pairing_rejects_wrong_token() (+2 more)

### Community 609 - "test_skill_registry.py"
Cohesion: 0.09
Nodes (13): Holds a pre-compiled regex + the original tech name., _TechPattern, _FakeClient, _FakeResp, tests/test_skill_registry.py — Unit tests for agent/skill_registry.py, Tests for WORKFLOW_SKILL_MAP., Tests for module-level pre-compiled pattern constants., Stub httpx client for nested-registry fetch tests. (+5 more)

### Community 610 - "test_task_brain_preflight.py"
Cohesion: 0.17
Nodes (15): svc(), tasks/service.py must call emit_agency_observation for task execution., test_task_service_traces_execution(), _coordinator(), has_brain(), no_brain(), asyncio, BaseException (+7 more)

### Community 611 - "TestRouterIntegration"
Cohesion: 0.21
Nodes (7): anyio, The behaviour this whole change exists for: once the first free provider has…, No strategy and no budgets configured — behaviour is unchanged., The director must see the provider round-trip, not the round trip plus JSON…, With nowhere to route, skipping would turn a slow request into a failed one —…, TestRouterIntegration, fake_post_chat()

### Community 612 - "check_model_compatibility"
Cohesion: 0.36
Nodes (4): check_model_compatibility(), Evaluate whether *model_name* can run on *profile*., _make_profile(), TestModelCompatibility

### Community 613 - "hermes_prompt.py"
Cohesion: 0.19
Nodes (15): build_chatml_system_prompt(), format_chatml_message(), format_tool_call(), format_tool_response(), messages_to_chatml(), model_supports_chatml(), parse_tool_call_from_chatml(), Any (+7 more)

### Community 614 - "MemoryMiddleware"
Cohesion: 0.15
Nodes (11): create_memory_middleware(), MemoryMiddleware, Any, Memory middleware for automatic context injection into AI tool requests. This…, Process incoming chat request and inject memories., Extract and save learnings from model responses., Factory function to create memory middleware instance., Middleware for automatic memory loading and injection. (+3 more)

### Community 615 - "SavingsTracker"
Cohesion: 0.20
Nodes (4): Any, Track cumulative token savings across filtering operations., One-line summary of savings (rtk gain style)., SavingsTracker

### Community 616 - "safe_agency.py"
Cohesion: 0.18
Nodes (17): add_pr_comment(), _find_existing_pr(), get_branch_sha(), get_default_branch(), _headers(), Any, agent/safe_agency.py — Safe GitHub operations for the workflow engine. All…, Create a pull request. Returns the PR object dict. If a PR already exists for… (+9 more)

### Community 617 - "AITellIssue"
Cohesion: 0.17
Nodes (8): AITellIssue, Find all AI tells in text, Find throat-clearing phrases, Find emphasis crutches (weak adverbs), Find meta-commentary (text referring to itself), Find Wh-sentence starters (weak prose starters), Find basic passive voice patterns (strict mode only), Format issues as human-readable report

### Community 618 - "Skill: repowise-intelligence"
Cohesion: 0.12
Nodes (15): 1. Graph Intelligence (Dependency Graph), 2. Git Intelligence, 3. Documentation Intelligence, 4. Decision Intelligence, Acceptance Checks, Directory Structure, Example Usage, Implementation Approach (+7 more)

### Community 619 - "ARCHITECTURE.md — Target Architecture"
Cohesion: 0.12
Nodes (15): 1. Target Repository Structure, 2. Dependency Rules, 3. Provider Architecture (Target), 4. Configuration Architecture (Target), 5. Event Bus Architecture (Target), 6. Scheduler Architecture (Target), 7. Dashboard Architecture (Target), 8. Migration Principles (+7 more)

### Community 620 - "_valid_login_state"
Cohesion: 0.24
Nodes (15): Return True if a fetched oauth_states doc is a valid, unexpired login state., _valid_login_state(), _doc(), Regression tests for social-login (GitHub & Google) OAuth state handling. Bug…, MongoDB/motor returns naive UTC datetimes. Subtracting a naive datetime from an…, The login handlers must persist state via _store_login_state, not the session…, test_expired_state_rejected(), test_just_within_window_accepted() (+7 more)

### Community 621 - "Skill: repowise-intelligence"
Cohesion: 0.12
Nodes (15): 1. Graph Intelligence (Dependency Graph), 2. Git Intelligence, 3. Documentation Intelligence, 4. Decision Intelligence, Acceptance Checks, Directory Structure, Example Usage, Implementation Approach (+7 more)

### Community 622 - "The 10-Step Workflow"
Cohesion: 0.12
Nodes (15): Cross-Tool Compatibility, Quick Reference Card, Skill: session-planning — Mandatory Planning Workflow for All AI Agents, Step 10 — Close Out, Step 1 — Orient (free), Step 2 — Understand the Task, Step 3 — Load Relevant Skills, Step 4 — Research (if novel task) (+7 more)

### Community 623 - "Contributing to local-llm-server"
Cohesion: 0.12
Nodes (16): Architecture, Bug Reports, Changelog, Coding Standards, Commit Message Convention, Contributing to local-llm-server, Development Setup, Feature Requests (+8 more)

### Community 624 - "LRUCache"
Cohesion: 0.20
Nodes (6): _Entry, LRUCache, T, Live (unexpired) entries — used by the semantic layer's scan., Bounded TTL cache with LRU eviction. Thread-safe, dependency-free., _list_records()

### Community 625 - "CEO Micro-Management"
Cohesion: 0.09
Nodes (21): CEO Micro-Management, Configuration reference, Escalation, and why it terminates, Five bounds, Operator surface, Tests, The 24x7 supervisor, The anti-slop gate (+13 more)

### Community 626 - "DeltaChunk"
Cohesion: 0.23
Nodes (6): DeltaChunk, Re-emit the processed content as SSE delta chunks. Processes accumulated text…, A single SSE delta chunk with metadata., Render as an OpenAI-compatible SSE delta chunk., Return the [DONE] marker., TestDeltaChunk

### Community 627 - "Runbook — Apply the Fast Free NVIDIA Brain to Render (TASK 2)"
Cohesion: 0.18
Nodes (10): Option A — Blueprint sync (preferred), Rollback, Runbook — Apply the Fast Free NVIDIA Brain to Render (TASK 2), Security notes, Status quo — what render.yaml already pins on master, TL;DR, V.1 — liveness, V.2 — autonomy readiness (+2 more)

### Community 628 - "HealthStatus"
Cohesion: 0.14
Nodes (5): OllamaProvider, Check health of all configured providers., HealthStatus, Provider health check result., Check provider health.

### Community 629 - "TestAuthAndTaskCreation"
Cohesion: 0.17
Nodes (7): POST /api/tasks/ without agent_id should attempt auto-assignment if agents exist, Test authentication and task creation with owner assignment, Get authentication token for admin user, Return headers with Bearer token, Verify login returns a valid access token, POST /api/tasks/ should store the authenticated user as owner, not 'unknown, TestAuthAndTaskCreation

### Community 630 - "SQLiteStore"
Cohesion: 0.17
Nodes (8): Connection, Top-level store — exposes collections as attributes. Usage:: store =…, Lazily build the pool of read-only connections (idempotent)., Yield a read connection from the pool (falls back to the writer). On in-memory…, Create tables if they don't already exist., SQLiteStore, store(), test_get_store_returns_sqlite()

### Community 631 - "fabric_cli.py"
Cohesion: 0.29
Nodes (15): cmd_apply(), cmd_list(), cmd_new(), cmd_save(), cmd_show(), cmd_stitch(), _ensure_patterns_dir(), main() (+7 more)

### Community 632 - ".publish"
Cohesion: 0.14
Nodes (9): decorator(), Any, Task, Broadcast an event to all matching subscribers. Returns the number of callbacks…, Fire-and-forget publish. Creates a background task. Returns the asyncio.Task so…, Return recent events for a topic., Return bus statistics., Check if a topic matches a pattern with * and ** wildcards. (+1 more)

### Community 634 - "ManagedAgentDreams"
Cohesion: 0.06
Nodes (21): Dream, ManagedAgentDreams, Any, Extract insight statements from a batch of memories., Replay a dream's narrative by ID., Return the most recent dreams, newest first., Total number of recorded memories., Total number of consolidated dreams. (+13 more)

### Community 635 - "clear_wizard_state_cache"
Cohesion: 0.19
Nodes (10): clear_wizard_state_cache(), Override the persistence collection used for wizard state. Tests and hosted…, Clear the in-memory wizard-state cache., set_wizard_state_collection(), _FakeWizardCollection, SimpleNamespace, TestClient, _setup_client() (+2 more)

### Community 636 - "test_agency_workflows_carry_the_failover_chain.py"
Cohesion: 0.18
Nodes (12): _agency_workflows(), parametrize, Path, Every workflow that runs an agent script must carry the whole brain chain.…, Rule 6 again, on the deploy side: `sync: false`, never `value:`., A selector that matched nothing would make every assertion vacuous., Rule 6: secrets are environment-only, never written into a file., `render.yaml` is the infrastructure declaration for the backend. A key that… (+4 more)

### Community 637 - "TestCatalogClaude5Models"
Cohesion: 0.10
Nodes (11): asyncio, tests/test_daily_automation_2026_08_21.py — Daily automation tests…, Verify the workspace-id header is captured from Anthropic API responses., _parse must work without passing workspace_id (backwards compat)., chat() must read anthrophic-workspace-id from the response headers., Verify the new Claude 5 entries in config/llm/models.yaml., Verify the Anthropic provider default model was promoted to claude-sonnet-5., packages/llm/config.py env-provider fallback must also use sonnet-5. (+3 more)

### Community 638 - "test_probe_report.py"
Cohesion: 0.17
Nodes (6): tests/test_probe_report.py — the catalogue-probe drift-report step.…, report(), TestBuildBody, TestFindTrackingIssue, TestIsRetired, communicate()

### Community 639 - "test_dockerfile_ships_root_modules.py"
Cohesion: 0.17
Nodes (13): _dockerfile_text(), Regression guard: the backend image must ship every root-level Python module…, An env var set to empty string means unset, not a commit named ''., Unknown must read as unknown — a deploy check treats None as 'unverifiable' and…, True when the Dockerfile copies root .py modules wholesale (`COPY *.py ...`)., The worker's `python worker_main.py` start command needs worker_main.py., V2.0 Modernization: the image must ship `packages/` (provider_router,…, _ships_all_root_modules() (+5 more)

### Community 640 - "CacheStats"
Cohesion: 0.18
Nodes (5): CacheStats, Path, Clear all cache entries. Returns number of entries cleared., Return current cache statistics., Load persisted cache entries from disk on startup.

### Community 641 - "._evict"
Cohesion: 0.20
Nodes (6): Any, Look up a cached response for the given model + messages. Returns the cached…, Remove a specific entry from the cache., Generate a deterministic cache key. Key components: - model name (different…, Remove a single entry (must be called with lock held)., Evict oldest entries if over capacity (must be called with lock held).

### Community 643 - "test_migrate_local_brain_env.py"
Cohesion: 0.38
Nodes (15): _make_env(), CompletedProcess, Path, tests/test_migrate_local_brain_env.py - regression suite for…, _run(), test_crlf_preserved_on_untouched_lines(), test_dry_run_does_not_mutate(), test_env_path_missing_file_exits_1() (+7 more)

### Community 645 - "test_rate_limit_backoff_survives.py"
Cohesion: 0.17
Nodes (10): ProviderFallbackError, Regression guard: a rate-limit cooldown must survive, on every route.…, The anti-wedge valve must not fire for an ordinary 429 backoff — otherwise it…, The threshold must clear the widest backoff ANY registered provider can earn.…, A corrupted/absurd cooldown must still be recoverable., The honest reset: probe permitted, failure history kept., A real success must still clear the breaker — allow_probe exists so that…, The behaviour the doom loop destroyed: each 429 waits longer. With… (+2 more)

### Community 646 - "sys"
Cohesion: 0.01
Nodes (118): detect_secrets(), main(), Recover CHANGELOG.md from a Git merge conflict in its [Unreleased] block. Pre-…, _extract_unreleased_body(), _insert(), main(), Insert the Maintenance changelog section at the end of the [Unreleased] block.…, Return (body_start, body_end_exclusive, body) for the [Unreleased] block. (+110 more)

### Community 647 - "_record_id"
Cohesion: 0.25
Nodes (5): ProceduralRecord, Store a successful step pattern and return its record id. Duplicate step…, One stored skill pattern., _record_id(), TestRecordId

### Community 648 - "_hash_component"
Cohesion: 0.16
Nodes (6): TestWorkspacePathDerivation, The hash component should not be reversible to the original ID., Workspace root path should be fully resolved (no . or ..)., TestWorkspaceHashing, _hash_component(), Derive a stable, opaque directory name from a validated ID. Using a truncated…

### Community 649 - "test_contract_enforcement.py"
Cohesion: 0.17
Nodes (9): check_kwargs(), Any, agent/contract_enforcement.py — Runtime signature locking (J) Provides…, # NOTE: limit has a default so it is accepted; owner_id is keyword-only., Raise TypeError on unknown kwarg (runtime extra='forbid'). Args: kwargs: The…, # NOTE: limit is NOT locked — it is a legitimate optional param that does not, tests/test_contract_enforcement.py — Contract discipline tests (J) Tests that…, Unit tests for the check_kwargs helper. (+1 more)

### Community 650 - ".build"
Cohesion: 0.15
Nodes (13): ContextResult, MemoryTurn, Rough token estimate: 4 chars ≈ 1 token (minimum 1)., Run the full RAG pipeline and return a token-budget-respecting context.…, One turn in the conversation history., Select up to *top_k* highest-scoring turns that fit within *budget*. Returns…, A document selected by retrieval, with its compressed excerpt., Final output of the RAG pipeline. (+5 more)

### Community 651 - "CollaborationContext"
Cohesion: 0.21
Nodes (3): CollaborationContext, Shared context blob propagated to all session participants. Carries the active…, TestCollaborationContext

### Community 652 - "Skill: agent-harness"
Cohesion: 0.13
Nodes (14): Architecture, Combining with Other Skills, Key Concepts, Output Format, Purpose, Safety Rules, Skill: agent-harness, Step 1 — Define the task clearly (+6 more)

### Community 653 - "Skill: checkpoint-strategy"
Cohesion: 0.13
Nodes (14): After a Loss Spike, Aggressive (Long Runs with Stable Training), Background, Checkpoint Policy Templates, Conservative (Recommended for First Runs), Integration Points, Output Format, Purpose (+6 more)

### Community 654 - "Process"
Cohesion: 0.13
Nodes (14): Anti-Patterns, Process, Purpose, Rules, Skill: debug-tracer, Step 1: Reproduce First, Step 2: Gather Evidence, Step 3: Form Hypotheses (+6 more)

### Community 655 - "Skill: local-ai-query"
Cohesion: 0.13
Nodes (14): 1. Verify Ollama is available, 2. Choose appropriate model, 3. Send query to local model, 4. Generate embeddings (for RAG), 5. List running models, Integration with ChromaDB (RAG), Limitations, Prerequisites (+6 more)

### Community 656 - "Skill: parallel-agents"
Cohesion: 0.13
Nodes (14): Combining with Other Skills, Core Concepts (from the Modal/OpenAI Agents SDK pattern), Example — parallel approach exploration, Example — parallel research, Output Format, Phase 1 — Decompose, Phase 2 — Dispatch (simulate parallelism), Phase 3 — Aggregate (+6 more)

### Community 657 - "Skill: parallel-worktrees"
Cohesion: 0.13
Nodes (14): Acceptance Checks, Common Patterns, Concept, Constraints, Instructions, Pattern A — Test main while you implement, Pattern B — Review reference during refactor, Pattern C — Hotfix without disturbing feature work (+6 more)

### Community 658 - "Design System: Taste Standard"
Cohesion: 0.13
Nodes (14): 1. Visual Theme & Atmosphere, 2. Color Palette & Roles, 3. Typography Rules, 4. Component Stylings, 5. Hero Section, 6. Layout Principles, 7. Responsive Rules, 8. Motion & Interaction (Code-Phase Intent) (+6 more)

### Community 659 - "Process"
Cohesion: 0.13
Nodes (14): Integration with Other Skills, Process, Purpose, Rules, Skill: ticket-to-pr, Step 1: Parse the Issue, Step 2: Context Prime, Step 3: Plan the Implementation (+6 more)

### Community 660 - "StreamingDeltaReconstructor"
Cohesion: 0.18
Nodes (6): Remove a post-processing hook., Feed a raw SSE line from the upstream stream., Feed raw text (e.g., from a non-streaming response) for re-emission., Collect all emitted chunks into a list (convenience)., Accumulate SSE chunks, post-process, and re-stream as deltas. Usage:: recon =…, StreamingDeltaReconstructor

### Community 662 - "de"
Cohesion: 0.19
Nodes (14): ae(), Be(), $d(), de(), fe(), ha(), ka(), me() (+6 more)

### Community 663 - "TestTheSharedListFitsBothCallers"
Cohesion: 0.18
Nodes (6): `review_agent.py` does `for model in ...` and passes it as `model=`., `apply_review.py` does `for model, desc in ...`., Breadth now comes from discovery, not from this list. The old list held three…, apply_review.py listed the same model twice, wasting a retry., The two consumers iterate different shapes; both must keep working., TestTheSharedListFitsBothCallers

### Community 664 - "Separate hosted dashboard backend (`backend/server.py`)"
Cohesion: 0.14
Nodes (14): Agent and workflow surfaces, API Surfaces and Route Map, Built-in admin and web UI, Connectors (`/api/connectors/*`, `backend/connectors_api.py`, admin-only), Control-plane style routers mounted in the proxy, CRISPY Workflow engine (`/api/workflow/*`, `workflow/api.py`, admin-only), Executive advisory (`/api/executives/*`, `backend/executive_advisory_api.py`), Governance (`/api/governance/*`, admin-only) (+6 more)

### Community 665 - "Agency Core — Progress & Resume Log"
Cohesion: 0.13
Nodes (14): Agency Core — Progress & Resume Log, Audit (committed), Environment constraints discovered this session, How to resume (read before doing anything), Key findings (so we don't re-investigate), Open risks / must-know before merging, Phase 0 — Stabilize & quarantine (commit `713184a`, pushed), Planned CI-parity hardening (the immediate next commit) (+6 more)

### Community 666 - "Attention Mechanisms Internals"
Cohesion: 0.12
Nodes (15): x(), Attention Complexity, Attention Mechanisms Internals, Causal Masking, Flash Attention, Grouped Query Attention (GQA), Multi-Head Attention (MHA), Multi-Query Attention (MQA) (+7 more)

### Community 667 - "_push_down_where"
Cohesion: 0.18
Nodes (11): _is_pushable_scalar(), _push_down_where(), Any, Scalar values whose `str()` form matches how they were stored in the indexed…, Build a SQL ``WHERE`` suffix from the subset of *query* conditions that map…, Indexed-column equality becomes a parameterised WHERE clause., $in over an indexed column becomes a parameterised IN (...) clause., Non-indexed fields, $or, $ne, and None values are left to Python _match. (+3 more)

### Community 668 - "test_catalogue_probe.py"
Cohesion: 0.04
Nodes (39): The representative task catalogue for the routing evaluation. Tasks live in…, _check_cross_catalogue(), _check_prefer_models(), _check_presets(), _llm_declared(), _load(), main(), Any (+31 more)

### Community 669 - "test_critical_flows.py"
Cohesion: 0.26
Nodes (14): _do_login(), _http_ok(), _playwright(), Critical-flow E2E tests (Playwright) — the five journeys that must never break.…, Create a task via the REST API (the same endpoint the UI calls) and poll its…, Direct (non-agent) chat: hit the OpenAI-compatible proxy completion the same…, Best-effort login. Returns True if we end up authenticated., _require_backend() (+6 more)

### Community 670 - "._sprint"
Cohesion: 0.19
Nodes (3): Tests for agents/agile_ceremonies.py — autonomous agile ceremonies. Loads…, TestGenerateBacklogRetro, TestGenerateSprintRetro

### Community 671 - "_request"
Cohesion: 0.20
Nodes (3): `--json PATH` writes a machine-readable summary the scheduled drift-report step…, _request(), TestTheJsonSummary

### Community 672 - "TestAnthropicReasoningTokenExtraction"
Cohesion: 0.40
Nodes (3): generate() populates Usage.reasoning_tokens from output_tokens_details., Exercise the same parsing path as AnthropicProvider.generate()., TestAnthropicReasoningTokenExtraction

### Community 673 - "TestBrainConfigUpdates"
Cohesion: 0.22
Nodes (3): Verify brain_config.py changes: Google provider, updated presets., The durable property, not the id of the week. This assertion has been amended…, TestBrainConfigUpdates

### Community 674 - "DecisionsStoreTests"
Cohesion: 0.11
Nodes (6): Test-only: clears the cached singleton so the next get_decisions_store() builds…, reset_decisions_store_singleton(), DecisionsStoreTests, _fresh_store(), Smoke: create() returns a fresh dec_<hex8> per call (no error surfaces from…, Backdates the older row via raw SQLite UPDATE so it falls outside the cutoff…

### Community 675 - "test_dockerfile_ships_config_dir.py"
Cohesion: 0.14
Nodes (14): _dockerfile_text(), Regression guard: the backend image must ship ``config/``. `config/llm/*.yaml`…, The two properties that made the ungated entry expensive in production., The ceiling that #1172 added must survive in the file that ships. Sized against…, Without this COPY the router silently runs on defaults in production., A shipped directory is worthless if the files moved out of it., A .dockerignore entry would defeat the COPY without touching it., A keyless local provider must not join the chain just by existing. ``ollama``… (+6 more)

### Community 676 - "test_hermes_server.py"
Cohesion: 0.18
Nodes (7): tests/test_hermes_server.py — the agency's OWN Hermes runtime server.…, Regression: the Hermes runtime was 100% broken in orchestrator mode. The…, test_tasks_executes_via_internal_agent(), fake_execute(), test_tasks_failure_is_reported_not_crashed(), test_tasks_sets_orchestrator_bypass_across_http_hop(), capture_execute()

### Community 677 - "financial_analyst.py"
Cohesion: 0.22
Nodes (7): Enum, str, Agentic CFO — autonomous financial analyst for AI infrastructure spend.…, Per-line recommendation map., Human-readable narrative of the recommendations., Budget recommendations a financial agent can issue., Recommendation

### Community 678 - "test_tasks_awaiting_approval_api.py"
Cohesion: 0.13
Nodes (19): ExecutionLogEntry, Any, field_validator, Update the updated_at timestamp., Single entry in a task's execution log., Comment or reply on a task., TaskComment, _client() (+11 more)

### Community 679 - "compilerOptions"
Cohesion: 0.13
Nodes (14): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noEmit, resolveJsonModule (+6 more)

### Community 680 - "classify_direct_chat_intent"
Cohesion: 0.23
Nodes (12): classify_direct_chat_intent(), _contains_keyword(), detect_intent(), intent.py — Intent classification for direct chat (answer_only, execute_now,…, Return True if content contains any execution or analysis keyword., Detect the user's intent from message content., Map lower-level intents into conversation-driven action categories. Returns one…, test_classify_answer_only() (+4 more)

### Community 681 - "validate_job_id"
Cohesion: 0.19
Nodes (5): TestJobIdValidation, parametrize, TestPathTraversalPrevention, Validate and return a job ID, or raise InvalidJobIdError., validate_job_id()

### Community 682 - "_TFIDFIndex"
Cohesion: 0.16
Nodes (11): Lightweight TF-IDF index over a fixed document collection. Sparse dict vectors…, Return ``(doc_index, cosine_score)`` pairs for the top-*k* matches., Return lowercase alphanumeric tokens with stop-words removed. Numeric tokens…, _TFIDFIndex, _tokenize(), test_tfidf_empty_corpus(), test_tfidf_empty_query(), test_tfidf_finds_relevant() (+3 more)

### Community 683 - "test_iteration_6_features.py"
Cohesion: 0.20
Nodes (8): requests, socket, Test iteration 6 features: - POST /api/tasks/ auto-assigns an available agent…, Return True if we can open a TCP connection to the backend server., _server_reachable(), torch, torch_nn, torch_utils_data

### Community 684 - "StopSlopChecker"
Cohesion: 0.14
Nodes (8): Initialize checker. Args: strict: If True, also report adverbs even if not in…, Remove most obvious AI tells from text, Detect and optionally remove AI tells from text, StopSlopChecker, Should format report correctly, Should report success on clean text, Should detect weak emphasis adverbs, Should detect meta-commentary

### Community 685 - "Process"
Cohesion: 0.14
Nodes (13): 1. Read and Understand the Issue, 2. Explore the Codebase, 3. Plan the Solution, 4. Implement, 5. Test, 6. Document, 7. Commit and Push, Notes (+5 more)

### Community 686 - "Skill: lr-schedule-advisor"
Cohesion: 0.14
Nodes (13): Background (Why This Matters), Common Mistakes, Cosine with Warmup (Recommended for Pretraining), Fine-tuning vs Pretraining, Integration Points, Output Format, Peak LR Heuristics by Model Size, Purpose (+5 more)

### Community 687 - "Instructions"
Cohesion: 0.14
Nodes (13): 1 — Tests green, 2 — Changelog updated, 3 — Determine the version bump, 4 — Update changelog, 5 — Commit the changelog update, 6 — Tag the release, 7 — Verify CI on the tag, 8 — Post-release (+5 more)

### Community 688 - "Instructions"
Cohesion: 0.14
Nodes (13): Acceptance Checks, `admin_auth.py` checklist, `agent/tools.py` checklist, Escalation, Instructions, `key_store.py` checklist, `proxy.py` auth middleware checklist, Risky Modules in This Repo (+5 more)

### Community 689 - "Process"
Cohesion: 0.14
Nodes (13): 1. Decompose the Task, 2. Sequence the Skills, 3. Execute in Order, 4. Handle Failures, 5. Synthesize Output, 6. Document the Composition, Example Compositions, Notes (+5 more)

### Community 690 - "Checks Performed"
Cohesion: 0.14
Nodes (13): 1. Round-trip Consistency, 2. Numeric Tokenization, 3. Whitespace Handling, 4. Special Character Coverage, 5. Fertility by Domain, 6. Vocabulary Overlap Check (for model updates), Background, Checks Performed (+5 more)

### Community 691 - "Skill: training-stability-monitor"
Cohesion: 0.14
Nodes (13): Example Checks Performed, Gradient Norm Check, Integration Points, Key Lessons (from LLM-from-scratch practitioners), Loss Spike Detection, LR Warmup Validation, Notes, Output Format (+5 more)

### Community 692 - "_build_payload_or_500"
Cohesion: 0.18
Nodes (13): _build_payload_or_500(), _check_secret(), _expected_secret(), preview_digest_endpoint(), Any, get, post, Dry-run: same auth, returns the would-be markdown body but does NOT dispatch to… (+5 more)

### Community 693 - "Skill: branch-cleanup"
Cohesion: 0.14
Nodes (13): Acceptance Checks, Automation — post-merge hook (optional), Option A — git push (standard), Option B — GitHub API (use when `git push --delete` returns 403), Option C — Delete local tracking refs after remote deletion, Skill: branch-cleanup, Step 1 — Confirm master is up to date, Step 2 — List all remote branches (+5 more)

### Community 694 - "Skill: perplexity — Web Research via Perplexity API"
Cohesion: 0.14
Nodes (13): Applying to this Repo, How to Query, No API Key? Use WebSearch, Prerequisites, Quick query (one-shot Python call), Run inline, Skill: perplexity — Web Research via Perplexity API, Skill Steps (+5 more)

### Community 695 - "Instructions"
Cohesion: 0.14
Nodes (13): 1 — Tests green, 2 — Changelog updated, 3 — Determine the version bump, 4 — Update changelog, 5 — Commit the changelog update, 6 — Tag the release, 7 — Verify CI on the tag, 8 — Post-release (+5 more)

### Community 696 - "Instructions"
Cohesion: 0.14
Nodes (13): Acceptance Checks, `admin_auth.py` checklist, `agent/tools.py` checklist, Escalation, Instructions, `key_store.py` checklist, `proxy.py` auth middleware checklist, Risky Modules in This Repo (+5 more)

### Community 697 - "Quick-Note Issues Processing Summary"
Cohesion: 0.14
Nodes (13): 🔗 Branch References, ✅ Completed, Future Session, Immediate (Session-Aware), Issue #229 — Stop-Slop AI Quality Checker, Issue #263 — Graphiti Temporal Context, Issue #266 — ECC Multi-Harness Adapter, 💡 Key Learnings (+5 more)

### Community 698 - "DirectChatSession"
Cohesion: 0.13
Nodes (12): detect_company_id(), detect_repo_id(), DirectChatSession, handle_chat_message_with_context(), Direct chat session with Company Graph context binding., Bind a company to this chat session and load its Company Graph., Bind a repository to this chat session., Get the bound Company Graph. (+4 more)

### Community 699 - "_resolve_role_model"
Cohesion: 0.11
Nodes (17): Call-time resolver for an agent role model id. Delegates to…, _resolve_role_model(), 0. Why this exists (root cause this fixes), 1. Hard constraints (from the owner), 2. Provider strategy (the recommendation), 3. Architecture, 3a. Store — `services/brain_config_store.py` (new), 3b. Call-time resolution — `agent/loop.py` (+9 more)

### Community 700 - "AppShell.jsx"
Cohesion: 0.09
Nodes (20): Docs / changelog, Frontend changes, Goal, Implementation Plan — Onboarding-Gate Admin Setting + Ephemeral Companies, Requirements → design, Tests, getAccountLifecycle(), getOnboardingSettings() (+12 more)

### Community 701 - "TestExtendedThinkingRouting"
Cohesion: 0.20
Nodes (6): Unit tests for extended thinking detection in handle_anthropic_messages., When thinking.type == enabled, routing should use agent_plan endpoint type., No thinking param → normal chat routing, not forced to reasoning., thinking_budget_tokens should appear in routing_meta when thinking is set., Without thinking param, thinking_budget_tokens not in routing_meta., TestExtendedThinkingRouting

### Community 702 - ".failed"
Cohesion: 0.06
Nodes (29): 1. Think Before Coding, 2. Simplicity First, 3. Surgical Changes, 4. Goal-Driven Execution, Integration points in this repo, Karpathy Guidelines Skill, Agent job lifecycle, API (+21 more)

### Community 703 - "SEO / GEO / AIO Audit Engine"
Cohesion: 0.12
Nodes (16): Prefer structured data; fall back to text when unavailable., API, Architecture, Delegation plan → agent tasks, Demo from the UI, Exports — the full heavy report, Fetching bot-protected sites (`fetch_mode`), Provenance (+8 more)

### Community 704 - "Traffic Distribution Across Providers"
Cohesion: 0.11
Nodes (15): A worked example, Adding capacity: multi-key rotation, Attribution, Configuration, Failure behaviour, Observability, Provider ids contain dashes, Read this before enabling it (+7 more)

### Community 705 - "overrides"
Cohesion: 0.14
Nodes (14): @tootallnate/once, overrides, bfj, css-select, http-proxy-agent, jsonpath, nth-check, postcss (+6 more)

### Community 707 - "_FakePersistence"
Cohesion: 0.20
Nodes (6): _FakePersistence, Schedule count must stay bounded even under 50 consecutive task failures. This…, In-memory ScheduleStore stand-in (sync upsert/remove/load_all)., Creating the same schedule name twice returns the same job — no duplication., test_schedule_create_idempotent_by_name(), test_schedule_growth_bounded_under_failure_storm()

### Community 708 - "_parse_reset_epoch"
Cohesion: 0.33
Nodes (3): _parse_reset_epoch(), Convert a provider reset-time header value to a monotonic deadline. Supported…, TestParseResetEpoch

### Community 709 - ".prune"
Cohesion: 0.31
Nodes (5): Any, Walk messages backward, accumulating per-role char counts. Returns…, Wrap evicted messages into ``<historical_memory_only>`` XML. The XML block is…, Apply 3-phase pruning if the context is over budget or cache expired. Returns…, Strip ``<think>`` blocks and truncate oversized assistant/tool outputs.

### Community 710 - "_deep_merge"
Cohesion: 0.50
Nodes (3): _deep_merge(), Deep merge two dicts. Override values take precedence., TestDeepMerge

### Community 711 - "test_wrapper_falls_back_to_installed_model"
Cohesion: 0.19
Nodes (5): _load_agent_runtime_module(), test_wrapper_exposes_hermes_task_endpoints(), fake_chat_with_ollama(), test_wrapper_exposes_opencode_run_endpoint(), test_wrapper_falls_back_to_installed_model()

### Community 712 - "_is_exempt"
Cohesion: 0.29
Nodes (6): _is_exempt(), parametrize, Both `prefix:` and `prefix(scope):` must skip the changelog gate., The scoped match must require a literal `(...)`, not a bare wildcard, or words…, TestScopedPrefixesAreExempt, TestUnrelatedPrefixesAreNotExempt

### Community 713 - "TestMCPClientStructuredOutput"
Cohesion: 0.38
Nodes (4): asyncio, Tests for MCPClient.call_tool_structured() using an async mock., call_tool() (legacy) is unchanged., TestMCPClientStructuredOutput

### Community 714 - "_StubManager"
Cohesion: 0.14
Nodes (3): _apply(), Minimal stand-in for BrainFailoverManager., _StubManager

### Community 715 - ".test_set_github_token_sqlite_string_id_does_not_500"
Cohesion: 0.20
Nodes (3): MonkeyPatch, TestClient, TestGithubTokenSQLiteRegression

### Community 716 - "_run_analyze"
Cohesion: 0.20
Nodes (8): analyze_script(), Tests for the "Analyze failures" step of ``.github/workflows/nightly-…, The exact case that broke run 35414763080: a regression-output.txt with no…, Extract the exact `run: |` block of the "Analyze failures" step., Run the extracted script against a fake regression-output.txt and return the…, _run_analyze(), TestAnalyzeFailuresClassifiesRealFailures, TestAnalyzeFailuresDoesNotCrashOnNoMatch

### Community 717 - ".set"
Cohesion: 0.25
Nodes (3): CacheEntry, Store a response in the cache., Write entry to disk (must be called with lock held).

### Community 718 - "test_provider_state_durability.py"
Cohesion: 0.14
Nodes (7): fake_mongo(), _FakeCollection, _FakeDb, Operator provider state must survive a redeploy. The per-provider kill switch…, Both halves matter, and the second one is easy to drop. Redirecting…, test_conftest_isolates_operator_state_for_every_test(), TestDurabilitySignal

### Community 719 - "TestDisabledReasonRendering"
Cohesion: 0.14
Nodes (5): ``describe_disabled_reason`` is rendered next to the on/off switch. The stored…, Anthropic sends 400 for an empty balance, not 402., A reason the operator cannot read still beats no reason at all., Guards the seam: the writer and this renderer must not drift apart. Scans the…, TestDisabledReasonRendering

### Community 720 - "MCPToolResult"
Cohesion: 0.36
Nodes (4): MCPToolResult, Result from ``call_tool_structured()``. ``structured`` is populated when the…, Unit tests for agent.mcp_client.MCPToolResult., TestMCPToolResult

### Community 721 - "LLMReasoner"
Cohesion: 0.28
Nodes (6): LLMReasoner, LLM-based reasoning for ambiguous or open-ended problems., Components, handler(), TestLLMReasoner, handler()

### Community 722 - "AGENTS.md — Codebase Map & Operations Reference"
Cohesion: 0.15
Nodes (13): Agent roles, AGENTS.md — Codebase Map & Operations Reference, Architecture, Claude Code subagents (cost-aware routing), Codebase map, Deployment, File-size exceptions, Further reading (+5 more)

### Community 723 - "EdgeType"
Cohesion: 0.18
Nodes (8): EdgeType, Enum, Obsidian Knowledge Graph — KnowledgeNode and KnowledgeGraph with typed edges.…, Import edges from (source, target, edge_type) tuples., Types of relationships between knowledge nodes., Add a directed edge between two nodes., Get outgoing edges from a node as (target_id, edge_type) pairs., Get incoming edges to a node as (source_id, edge_type) pairs.

### Community 724 - "Process"
Cohesion: 0.15
Nodes (12): Output Format, Process, Purpose, Rules, Skill: auto-fix, Step 1: Discover Fix Commands, Step 2: Run Fixers (Auto-fixable), Step 3: Run Checkers (Non-auto-fixable) (+4 more)

### Community 725 - "Skill: Brain Dump"
Cohesion: 0.15
Nodes (12): Example Prompt to Trigger, Instructions, Notes, Output Format, Purpose, Skill: Brain Dump, Step 1: Capture Everything, Step 2: Categorize (+4 more)

### Community 726 - "Process"
Cohesion: 0.15
Nodes (12): Process, Purpose, Rules, Skill: context-prime, Step 1: Read Core Docs, Step 2: Map the Architecture, Step 3: Find Conventions, Step 4: Understand Data Flow (+4 more)

### Community 727 - "Instructions"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Instructions, Role 1: Security Reviewer, Role 2: Correctness Reviewer, Role 3: Performance Reviewer, Role 4: Maintainability Reviewer, Skill: council-review, Step 1 — Gather the diff (+4 more)

### Community 728 - "Skill: duplicate-thread"
Cohesion: 0.15
Nodes (12): Files, How It Works, In a Claude prompt, Integration, Manual duplication, Merging Back, meta.json Schema, Purpose (+4 more)

### Community 729 - "Skill: Email Triage"
Cohesion: 0.15
Nodes (12): Example Prompt to Trigger, Instructions, Notes, Output Format, Purpose, Skill: Email Triage, Step 1: Intake, Step 2: Triage Categories (+4 more)

### Community 730 - "Process"
Cohesion: 0.15
Nodes (12): Anti-Patterns, Process, Purpose, Rules, Skill: feature-flag, Step 1: Assess Flag Need, Step 2: Define the Flag, Step 3: Implement the Guard (+4 more)

### Community 731 - "Process"
Cohesion: 0.15
Nodes (12): 1. Review Staged and Unstaged Changes, 2. Review Commit History, 3. Validate Commit Messages, 4. Clean Up if Needed, 5. Confirm Branch State, 6. Push, Notes, Output (+4 more)

### Community 732 - "Skill: graphify — Knowledge Graph Token Optimization"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Claude's query protocol (use this instead of Read tool for exploration):, Graph Artifacts — What to Commit, How to Use the Graph (Token Savings Protocol), Installation (one-time per machine), Instead of reading raw files:, Key commands:, Relationship to repowise-intelligence Skill (+4 more)

### Community 733 - "Skill: prompt-library"
Cohesion: 0.15
Nodes (12): 1. Sync Snapshots, 2. Generate Library Index, 3. Generate TRANSPARENCY.md, 4. Update CHANGELOG.md in prompts/, 5. Commit, Directory Structure Created, Output, Purpose (+4 more)

### Community 734 - "Skill: prompt-transparency"
Cohesion: 0.15
Nodes (12): 1. Collect All Agent & Skill Definitions, 2. Extract Key Behavioral Dimensions, 3. Generate Transparency Report, 4. Flag Risks, 5. Commit the Report, Example Usage, Inspiration, Output Format (+4 more)

### Community 735 - "Skill: Research"
Cohesion: 0.15
Nodes (12): Example Prompt to Trigger, Instructions, Notes, Output Format, Purpose, Skill: Research, Step 1: Define the Research Question, Step 2: Identify Source Categories (+4 more)

### Community 736 - "Skill: scope-guard"
Cohesion: 0.15
Nodes (12): Anti-Patterns to Avoid, Output Format, Process, Purpose, Rules, Skill: scope-guard, Step 1: Define the Scope Contract, Step 2: Pre-Implementation Check (+4 more)

### Community 737 - "admin_update_task_router.py"
Cohesion: 0.22
Nodes (12): _expected_admin_secret(), _extract_admin_token(), BaseModel, backend/admin_update_task_router.py Step 1: POST…, Mount the update-task endpoint on ``app``. Idempotent: skips if a path with the…, Body for ``POST /api/workflow/orchestrator/update-task/{run_id}``.…, Resolve the admin secret from env. Order matches admin_digest_router.py:…, Inject ``additional_instructions`` into a paused or running WorkflowRun.… (+4 more)

### Community 738 - "check_feature"
Cohesion: 0.25
Nodes (9): check_feature(), get_feature(), list_features(), Any, get, post, Return the full support matrix with summary., Return a single feature entry. (+1 more)

### Community 739 - "Instructions"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Instructions, Role 1: Security Reviewer, Role 2: Correctness Reviewer, Role 3: Performance Reviewer, Role 4: Maintainability Reviewer, Skill: council-review, Step 1 — Gather the diff (+4 more)

### Community 740 - "Skill: graphify — Knowledge Graph Token Optimization"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Claude's query protocol (use this instead of Read tool for exploration):, Graph Artifacts — What to Commit, How to Use the Graph (Token Savings Protocol), Installation (one-time per machine), Instead of reading raw files:, Key commands:, Relationship to repowise-intelligence Skill (+4 more)

### Community 741 - "Skill: platform-setup — Autonomous Agency Bootstrap"
Cohesion: 0.15
Nodes (12): Ongoing autonomous operation, Phase 1 — Verify deployment health (no auth needed), Phase 2 — Login as admin, Phase 3 — Onboard the platform itself as a company, Phase 4 — Verify specialists were provisioned, Phase 5 — Configure GitHub integration, Phase 6 — Trigger first agency cycle manually, Phase 7 — Verify autonomous schedule is active (+4 more)

### Community 742 - "Workspace Isolation Architecture"
Cohesion: 0.09
Nodes (15): Configuration, Directory Layout, Error Handling, Lifecycle States, Metrics, Overview, Path Derivation, Path Safety (+7 more)

### Community 743 - "Device compatibility and model picks"
Cohesion: 0.15
Nodes (12): Acceleration at a glance, Apple Silicon: chip tier vs bandwidth (qualitative), Desktops and workstations, Device compatibility and model picks, Edge cases, How to read memory on different platforms, Laptops and all-in-ones, NVIDIA examples by VRAM (CUDA) (+4 more)

### Community 744 - "Autonomy Uplift — Living Roadmap & Detailed Implementation Specs"
Cohesion: 0.18
Nodes (10): 0. The goal (operator's words), 1. Shipped ✅, 2. In flight 🟡, 3. Pending ⬜ — detailed implementation specs, 3c. CRISPY — harden, then re-enable ✅  (size: L, risky-module-review), 3d. Phase 3 — auto-PR *quality* beyond the slop-gate ✅  (size: M), 3e. Phase 4 — reliability spine ✅  (size: M), 4. Deferred 🔭 (+2 more)

### Community 745 - "OpenClaw — iOS Control of the Agency (Single-Service Free-Tier Deploy)"
Cohesion: 0.13
Nodes (12): 1. Set env vars on the existing `local-llm-server` service, 2. Deploy, 3. Check the status, 4. Get the pairing QR, 5. Pair and verify, Alternative: Telegram bot, Architecture (single-service), Free-tier caveats (+4 more)

### Community 746 - "cleanup_stale_jobs"
Cohesion: 0.31
Nodes (8): cleanup_stale_jobs(), _is_stale(), Any, packages/scheduler/cleanup.py — schedule deduplication + stale removal.…, Remove a job from the store. Returns True on success, False on failure. Logs…, Check if a created_at timestamp is older than ttl_seconds. Handles multiple…, Remove stale run-once + stuck agency jobs from the durable store. Args: store:…, _safe_remove()

### Community 747 - "rules"
Cohesion: 0.15
Nodes (12): rules, import/no-anonymous-default-export, jsx-a11y/anchor-is-valid, jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/no-static-element-interactions, no-console, no-template-curly-in-string (+4 more)

### Community 748 - "OllamaManager"
Cohesion: 0.31
Nodes (5): OllamaManager, Manage Ollama service startup and health checks., Check if Ollama is running., Attempt to start Ollama service., Ensure Ollama is running, start if needed.

### Community 749 - "strip_html"
Cohesion: 0.22
Nodes (8): extract_real_url(), fetch(), main(), meaningful(), Drop site navigation chrome and repeated nav blocks from stripped text. A fetch…, strip_boilerplate(), strip_html(), __init__()

### Community 751 - "_Budget"
Cohesion: 0.20
Nodes (3): _Budget, Shared attempt + wall-clock budget for one logical completion. Bounds the whole…, True when free/local providers have used everything but the reserve. Only the…

### Community 752 - "_is_bedrock_model_id"
Cohesion: 0.27
Nodes (3): _is_bedrock_model_id(), Return True if model_id is an AWS Bedrock model or inference profile ID., TestIsBedrockModelId

### Community 754 - "Agent Transparency Report"
Cohesion: 0.29
Nodes (6): Agent Transparency Report, Guardrails and Limits, How to Verify This, Human Oversight Points, What Happens When an AI Works in This Repo?, What the AI Won't Do

### Community 755 - "InternalAgentAdapter"
Cohesion: 0.06
Nodes (30): Direct Chat Evolution: Seamless Assistant Architecture, Failure Recovery, Overview, Runtime Selection Policy, 3b. Hermes — **our own** Hermes server (in-repo), UI-wired ✅  (size: M), Resolve the base URL of the agency's own Hermes server. Precedence:…, resolve_hermes_base_url(), InternalAgentAdapter (+22 more)

### Community 756 - "_get_provider_policy"
Cohesion: 0.19
Nodes (12): _get_provider_policy(), ProviderPolicyUpdate, BaseModel, get, put, Read the durable provider policy, falling back to a safe default. Returns a…, Persist the provider policy and return the new state., Return the durable provider policy (single source of truth for paid-provider… (+4 more)

### Community 757 - "_InMemoryBackend"
Cohesion: 0.18
Nodes (4): _InMemoryBackend, Single-process backend using asyncio.Lock + dicts with TTL timestamps., Clear all cooldown entries (for test teardown)., Clear all probe-lock entries (for test teardown). ``cooldown_clear`` only…

### Community 758 - "test_admin_local_brain_router.py"
Cohesion: 0.15
Nodes (19): build_admin_local_brain_router(), get_admin_local_brain_state(), post_admin_local_brain_toggle(), Any, APIRouter, Construct a ready-to-mount APIRouter with the auth dependency baked in. The…, _require_admin(), _store() (+11 more)

### Community 759 - "test_compose_and_coordinate_api.py"
Cohesion: 0.19
Nodes (8): _auth_override(), AuthContext, test_coordinate_dependency_aware_tasks_block_missing_dependencies(), test_coordinate_dependency_aware_tasks_succeed_with_dependencies(), test_coordinate_legacy_workers_flow_remains_backward_compatible(), run(), test_docker_compose_has_no_circular_depends_on(), _visit()

### Community 760 - "TestModelCostTableUpdates"
Cohesion: 0.26
Nodes (3): New models are present in the cost table with sensible prices., get_cost_table() API exposes the new models with correct structure., TestModelCostTableUpdates

### Community 761 - "TestDecisionsBotLinks"
Cohesion: 0.25
Nodes (3): Decision prompts that exist *before* the orchestrator creates a run (e.g. a…, Re-sending the same Telegram message (offset rewind, bot restart re-delivery)…, TestDecisionsBotLinks

### Community 763 - "TestSelfHealingInfrastructureNoCodeFix"
Cohesion: 0.28
Nodes (5): asyncio, Infrastructure errors reach awaiting_human state without dispatching a fix., on_ci_failure with MongoDB error → awaiting_human, no fix dispatched., on_ci_failure with a code error → fix is dispatched., TestSelfHealingInfrastructureNoCodeFix

### Community 764 - "TestKillSwitchDurability"
Cohesion: 0.15
Nodes (4): The local mirror is what keeps operator intent during a Mongo outage., A restart clears every in-memory cache; the state must still be there., Never claim a switch took effect when no store accepted it. Mongo off…, TestKillSwitchDurability

### Community 765 - "test_providers_live_e2e.py"
Cohesion: 0.24
Nodes (11): _auth_headers(), _login_via_email(), Any, tests/test_providers_live_e2e.py — Live integration test for…, The /api/providers list now annotates each record with is_brain/role. The role-…, Skip the current test with a structured reason (pytest.skip is fine too)., POST /api/auth/login and return the parsed JSON body. Raises on failure., Full JWT round-trip: login → PUT → GET → cleanup. Asserts that the providers… (+3 more)

### Community 766 - "test_quick_note_engine.py"
Cohesion: 0.17
Nodes (11): _before(), Guard that the quick-note engine agents use NVIDIA NIM as the primary engine…, implement_agent.py must not spend paid credits behind the operator. This used…, Rule 2: all LLM calls go through packages/ai/router.py. A private model list in…, Nemotron first — asserted against behaviour, not file contents. This used to…, Regression: _run_baseline_pytest() ran the FULL suite (no path filter,…, test_baseline_pytest_timeout_is_generous_and_failure_is_caught(), test_implement_agent_never_escalates_to_paid() (+3 more)

### Community 767 - "TestChatFallbackAndApproval"
Cohesion: 0.22
Nodes (5): Test chat fallback behavior with commercial provider approval, Get authentication token for admin user, POST /api/chat/send endpoint should exist and accept requests, Verify ChatMessage model accepts allow_commercial_fallback_once field, TestChatFallbackAndApproval

### Community 768 - "Trajectory"
Cohesion: 0.15
Nodes (10): Any, Path, Persist trajectory as JSON and return the file path., Reload a previously saved trajectory (read-only replay)., Return a summary dict suitable for logging / leaderboards., A single action/observation pair in an agent trajectory., Complete record of one agent run against one task. Compatible with the…, Append a step and return it. (+2 more)

### Community 769 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Idempotency Rules, Instructions, Skill: cooldown-resume, Step 1 — Read the checkpoint files, Step 2 — Assess the state, Step 3 — Verify changed files are correct, Step 4 — Run tests to confirm baseline (+3 more)

### Community 770 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Current Dependencies (quick reference), Instructions, Skill: dependency-audit, Step 1 — Evaluate the new dependency, Step 2 — Pin appropriately, Step 3 — Install and verify, Step 4 — Check for conflicts (+3 more)

### Community 771 - "Process"
Cohesion: 0.17
Nodes (11): 1. Audit Existing Skills, 2. Identify Gaps, 3. Propose Improvements, 4. Implement, 5. Validate, Notes, Output, Process (+3 more)

### Community 772 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Instructions, Skill: smart-commit, Step 1 — Confirm changelog is updated, Step 2 — Run tests, Step 3 — Check for obvious issues, Step 4 — Stage your changes, Step 5 — Write a conventional commit message (+3 more)

### Community 773 - "Skill: system-prompt-audit"
Cohesion: 0.17
Nodes (11): 1. Inventory Collection, 2. Consistency Check, 3. Safety Check, 4. Generate Audit Report, 5. Exit Codes, Integration, Purpose, Related Skills (+3 more)

### Community 774 - "Skill: task-alive-updates"
Cohesion: 0.17
Nodes (11): Example Output, Files, How It Works, Implementation Rules, In a shell script / agent harness, In Claude task descriptions, Integration with parallel-agents, Purpose (+3 more)

### Community 775 - "Process"
Cohesion: 0.17
Nodes (11): 1. Read the Task Carefully, 2. Define the Boundary, 3. Identify Temptations, 4. Lock the Scope, 5. Out-of-Scope Findings, Notes, Output, Process (+3 more)

### Community 776 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Instructions, Skill: test-first-executor, Step 1 — Identify what needs testing, Step 2 — Write the test first, Step 3 — Confirm the test FAILS before implementation, Step 4 — Implement until the test passes, Step 5 — Run the full suite (+3 more)

### Community 777 - "TestRevenuePortfolio"
Cohesion: 0.22
Nodes (3): Severity -> potential revenue loss via the portfolio mechanism (PR #534 review)., Delegation packages must slot directly into agents/portfolio.py., TestRevenuePortfolio

### Community 778 - "build_connectors_router"
Cohesion: 0.38
Nodes (7): build_connectors_router(), list_connectors(), webhook_send(), Any, APIRouter, Reject anyone who is not the agency admin., _require_admin()

### Community 779 - "Skill: agent-browser — Real Chrome Browser Automation"
Cohesion: 0.17
Nodes (11): Applying to the local-llm-server Platform, Core Commands, How to Use This Skill, Installation (one-time), Skill: agent-browser — Real Chrome Browser Automation, Step 1 — Check Chrome is running with debugging, Step 2 — Navigate and snapshot, Step 3 — Interact using element refs (+3 more)

### Community 780 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Idempotency Rules, Instructions, Skill: cooldown-resume, Step 1 — Read the checkpoint files, Step 2 — Assess the state, Step 3 — Verify changed files are correct, Step 4 — Run tests to confirm baseline (+3 more)

### Community 781 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Current Dependencies (quick reference), Instructions, Skill: dependency-audit, Step 1 — Evaluate the new dependency, Step 2 — Pin appropriately, Step 3 — Install and verify, Step 4 — Check for conflicts (+3 more)

### Community 782 - "Skill: dev-browser — Browser Automation via Sandboxed JS"
Cohesion: 0.18
Nodes (10): Browser API, CLI flags, Connect to existing Chrome, Full script example (Playwright Page API), Installation, LLM usage patterns, Performance, Primary invocation styles (+2 more)

### Community 783 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Instructions, Skill: test-first-executor, Step 1 — Identify what needs testing, Step 2 — Write the test first, Step 3 — Confirm the test FAILS before implementation, Step 4 — Implement until the test passes, Step 5 — Run the full suite (+3 more)

### Community 784 - "Agent Orchestration Design"
Cohesion: 0.14
Nodes (13): Mark the trajectory as complete., Agent Orchestration Design, Execution Pathway, Four-Agent Structure, Key Invariants, OSS Inspirations (Clean-Room), Overview, Plan-First Pathway (+5 more)

### Community 785 - "Universality: case-coverage matrix"
Cohesion: 0.10
Nodes (21): A. Connection & credentials, Autonomous SDLC Loop (Agency Core, repo-agnostic), B. Provider & host, C. Delivery / branch policy  *(detected — see DeliveryPolicy)*, Companies without a connected repo (URL-only onboarding), D. CI / checks, Design principle: repo-agnostic, not GitHub-Actions-bound, Detect & respect each repo's delivery policy (+13 more)

### Community 786 - "Quantization Internals"
Cohesion: 0.17
Nodes (12): Absmax Quantization (Symmetric), Activation Quantization, AWQ (Activation-Aware Weight Quantization), Bits and Bytes (bitsandbytes), Data Types, GGUF / llama.cpp Quantization, GPTQ (Post-Training Quantization for GPT), Post-Training Quantization (PTQ) (+4 more)

### Community 788 - "_overlap_score"
Cohesion: 0.39
Nodes (3): _overlap_score(), Jaccard-style overlap normalised by query length to reward recall., TestOverlapScore

### Community 789 - "467 Public Site Truth Spec"
Cohesion: 0.17
Nodes (11): 467 Public Site Truth Spec, Architecture Page Truth, Content Rules, Current State, Feature Matrix Truth, Required: Public Site Truth Spec, Site Structure, Tier System for Features (+3 more)

### Community 790 - "_tokenize"
Cohesion: 0.39
Nodes (3): Case-fold and split text into word tokens, filtering short stopwords., _tokenize(), TestTokenize

### Community 791 - "apply_overrides"
Cohesion: 0.22
Nodes (9): apply_overrides(), Write *overrides* into ``os.environ`` and refresh dependent caches. Keys that…, Re-read every ``settings`` attribute from the updated environment. Re-runs…, _refresh_settings_singleton(), Re-running Settings.__init__ mints a new random secret when SECRET_KEY is…, test_apply_overrides_refreshes_the_settings_singleton(), test_apply_overrides_writes_only_catalogued_keys(), test_clearing_an_override_restores_the_startup_environment() (+1 more)

### Community 792 - "install-agents.sh"
Cohesion: 0.39
Nodes (11): classify_current_or_legacy(), fail(), install_missing(), path_exists(), replace_legacy_role(), report_preflight_error(), role_selected(), same_state() (+3 more)

### Community 793 - "hybrid_reasoning.py"
Cohesion: 0.36
Nodes (7): ConfidenceLevel, Enum, str, Hybrid AI — combine deterministic rule engines with LLM reasoning. Implements a…, Which reasoning path is active for a given query., Confidence label for a reasoning result., ReasoningMode

### Community 794 - "research_coordinator.py"
Cohesion: 0.36
Nodes (7): AgentRole, Enum, str, Multi-Agent Research Coordinator — orchestrate a team of specialized research…, Lifecycle states for a research task., Specialized agent roles in the research team., TaskStatus

### Community 795 - "Kimi Web-Bridge Service"
Cohesion: 0.17
Nodes (11): API, Connecting to the Main Backend, Docker, Environment Variables, `GET /health`, `GET /v1/models`, How It Works, Kimi Web-Bridge Service (+3 more)

### Community 797 - "_start_in_web_bot_tasks"
Cohesion: 0.29
Nodes (7): _keepalive_self_ping(), Run the FreeBuff Telegram bot, restarting it on unexpected exit., Ping our own public URL so a free-tier web service doesn't sleep. Render free…, Start the Telegram bot (and keep-alive) inside the web process when enabled.…, _start_in_web_bot_tasks(), _register(), _telegram_bot_supervisor()

### Community 798 - "test_agile_api.py"
Cohesion: 0.17
Nodes (3): auth_headers(), Tests for /api/agile/* endpoints., Get auth headers for the seeded admin user (matched to seed_admin email).

### Community 799 - "_parse_tool_calls_from_response"
Cohesion: 0.39
Nodes (3): _parse_tool_calls_from_response(), Parse OpenAI tool_calls from a model response. Handles: - Direct JSON…, TestParseToolCalls

### Community 800 - "test_brain_default_consistency.py"
Cohesion: 0.24
Nodes (11): _catalogue_default(), One brain default, consistent across every surface that names one. This file…, Guards every assertion below from passing vacuously on an empty string., ``packages/ai/brain.py`` is a separate copy of "the free NVIDIA model"., A default that is not the first candidate wastes the first attempt., Production env values override every default in the code. ``render.yaml``…, test_brain_default_matches_the_catalogue(), test_every_nvidia_role_preset_matches_the_catalogue() (+3 more)

### Community 801 - "_provider"
Cohesion: 0.43
Nodes (3): _provider(), SimpleNamespace, TestAuthFollowsTheProviderDeclaration

### Community 803 - "Backend changes"
Cohesion: 0.25
Nodes (7): `activation_api.py`, `app_settings.py` (new), Backend changes, `backend/company_api.py`, `db/sqlite_store.py`, `models/company_graph.py`, `services/ephemeral_reaper.py` (new) + `services/background.py`

### Community 804 - "_lookup_requirements"
Cohesion: 0.39
Nodes (3): _lookup_requirements(), Return the best-matching requirement spec for a model name., TestModelRequirements

### Community 805 - "test_task_clarification.py"
Cohesion: 0.17
Nodes (4): auth_headers(), Tests for needs_clarification status and /api/tasks/{id}/clarify endpoint., Get auth headers for an admin user., test_needs_clarification_in_enum()

### Community 806 - "Any"
Cohesion: 0.25
Nodes (7): _accumulate_usage(), _assistant_messages(), _message_text(), Any, Return assistant messages carried by an ``agent_end`` event., Concatenate the text blocks of one assistant message., Sum token and cost usage across assistant messages.

### Community 807 - "EvalHarness"
Cohesion: 0.16
Nodes (9): EvalHarness, _bounded(), EvalResult, Runs agent functions against Tasks, records Trajectories and produces…, Execute the agent on a single task and return an EvalResult., Delegate to the agent callable (sync or async)., Run multiple tasks and aggregate into a BenchmarkReport. Set concurrency > 1 to…, Outcome of running one task through the harness. (+1 more)

### Community 808 - "_keyword_search"
Cohesion: 0.20
Nodes (10): Document, _keyword_search(), Score documents by query-term coverage with a title-match boost., A single knowledge-base entry (wiki page, source document, etc.)., _doc(), test_keyword_search_empty_query(), test_keyword_search_finds_relevant(), test_keyword_search_no_match() (+2 more)

### Community 809 - "_extractive_compress"
Cohesion: 0.18
Nodes (11): _extractive_compress(), Split text into sentences on . ! ? followed by whitespace or end-of-string., Return the highest-value sentences from *text* within *max_tokens*. Each…, _split_sentences(), test_compress_empty_text(), test_compress_prefers_query_relevant_sentences(), test_compress_result_non_empty_for_non_empty_input(), test_compress_short_text_verbatim() (+3 more)

### Community 810 - "SyncAgent"
Cohesion: 0.24
Nodes (3): Background agent that periodically syncs session state across contributors.…, SyncAgent, TestSyncAgent

### Community 811 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Failure / Retry Behaviour, Instructions, Skill: implementation-planner, Step 1 — Understand the current state, Step 2 — Write the plan, Step 3 — Get implicit approval before coding, Step 4 — Implement (+2 more)

### Community 812 - "Skill: pro-workflow"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Model Selection Guide, Phase 1 — Research (Scout), Phase 2 — Plan, Phase 3 — Implement, Phase 4 — Wrap Up, Skill: pro-workflow (+2 more)

### Community 813 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Learnings File Doesn't Exist?, Skill: replay-learnings, Step 1 — Read the learnings file, Step 2 — Filter relevant learnings, Step 3 — Check recent checkpoint history, Step 4 — Surface blockers from previous session (+2 more)

### Community 814 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Skill: repo-memory-updater, Step 1 — Inventory what changed, Step 2 — Check root AGENTS.md, Step 3 — Check module AGENTS.md files, Step 4 — Update .Codex/state/, Step 5 — Commit the update (+2 more)

### Community 815 - "Skill: resource-panel"
Cohesion: 0.18
Nodes (10): Ask Claude to emit a resource panel, Automated via shell (git-based), Fields, Files, How to Use, Integration, Output Format, Purpose (+2 more)

### Community 816 - "Skill: sandboxed-exec"
Cohesion: 0.18
Nodes (10): Example — run tests in isolation, Example — validate a generated script before saving, How It Works, Output Format, Purpose, Security Notes, Skill: sandboxed-exec, Steps (for Claude to follow) (+2 more)

### Community 817 - "Workflow"
Cohesion: 0.20
Nodes (9): Acceptance checks, Fill these in, Skill: client-onboarding, Step 1 — Create the company and kick off onboarding, Step 2 — Poll progress, Step 3 — Verify specialists were provisioned, Step 4 — Confirm the 24x7 agency runtime is live, Step 5 — Note real gaps instead of pretending they're solved (+1 more)

### Community 818 - "ECC Harness Patterns Skill"
Cohesion: 0.18
Nodes (10): 1. Harness Detection & Adaptation, 2. Session Lifecycle Hooks, 3. Cross-Harness Model Selection, 4. Persistent Harness Registry, ECC Harness Patterns Skill, Files to Create/Modify, Implementation Plan, Patterns to Adopt (+2 more)

### Community 819 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Failure / Retry Behaviour, Instructions, Skill: implementation-planner, Step 1 — Understand the current state, Step 2 — Write the plan, Step 3 — Get implicit approval before coding, Step 4 — Implement (+2 more)

### Community 820 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Skill: repo-memory-updater, Step 1 — Inventory what changed, Step 2 — Check root CLAUDE.md, Step 3 — Check module CLAUDE.md files, Step 4 — Update .claude/state/, Step 5 — Commit the update (+2 more)

### Community 821 - "Stop-Slop Quality Skill"
Cohesion: 0.18
Nodes (10): AI Tells Detected, Business Jargon, Emphasis Crutches (Banned Adverbs), Implementation, Integration Points, Meta-Commentary, References, Stop-Slop Quality Skill (+2 more)

### Community 822 - "AgentJobRequest"
Cohesion: 0.10
Nodes (20): AgentJobRequest, Validated input for creating a new agent job. Passed from the API handler into…, Path, Added, Acceptance check, Agency Core — Ruthless Architecture Audit & Migration Plan, Root causes (not symptoms), Section 1 — The Brutal Truth (+12 more)

### Community 823 - "RunnerLock"
Cohesion: 0.32
Nodes (3): File-based lock to prevent duplicate concurrent sessions., Try to acquire the lock. Returns True if acquired., RunnerLock

### Community 824 - "2. Critical Bugs & Exact Detection Signatures"
Cohesion: 0.18
Nodes (10): 1. PR Analysis Summary & Evaluation Rubric, 2. Critical Bugs & Exact Detection Signatures, 3. Architectural Refactoring Architecture, Applying the rubric to open PRs, 🔴 CRITICAL — Silent Error Propagation in Agent Loop & Tool Dispatch, 🔴 CRITICAL — Unhandled Rate Limits & State Checkpointing, 🔴 CRITICAL — Unsandboxed Tool Execution & SSRF Vulnerabilities, Evaluation Rubric (+2 more)

### Community 825 - "Tailored Onboarding, Editable Companies & Dynamic Roles"
Cohesion: 0.25
Nodes (7): 1. Editable companies, anytime (not a one-shot wizard), 2. Question-driven provisioning — no cosmetic questions, 4. Agents start pre-powered, Invariants, Phases, Tailored Onboarding, Editable Companies & Dynamic Roles, The gaps to close

### Community 826 - "Issue #467 — Section 1: Pulled State + PR Inventory"
Cohesion: 0.18
Nodes (10): 1. Current Git State, 2. Open PRs (as of 2026-06-08), 3. Files Modified on consolidate/maturation-stable (vs master), 4. What Master Has (that consolidate doesn't), 5. What Is MISSING from master (0% delivered in #467), 6. Required Action Before Code, Branch: `consolidate/maturation-stable`, Issue #467 — Section 1: Pulled State + PR Inventory (+2 more)

### Community 828 - "TestRanking"
Cohesion: 0.25
Nodes (3): Nemotron first, as asked; then other instruct models., Embedding, rerank, OCR, guard and vision models cannot drive the loop., TestRanking

### Community 829 - "Deploy to Google Cloud Run"
Cohesion: 0.18
Nodes (10): 1) Admin protection (required), 2) User API keys (required), 3) LLM provider (recommended), Build + deploy (Dockerfile), Deploy to Google Cloud Run, Notes / limitations on Cloud Run, Prereqs, Required configuration (+2 more)

### Community 830 - "Key Components"
Cohesion: 0.18
Nodes (10): 1. Input Embedding, 2. Multi-Head Self-Attention, 3. Residual Connections, 4. Feed-Forward Network (FFN), 5. Layer Normalization, Decoder-Only vs Encoder-Decoder, High-Level Structure, Key Components (+2 more)

### Community 831 - "Sampling Strategies Internals"
Cohesion: 0.07
Nodes (25): ALiBi (Attention with Linear Biases), Comparison, Learned Positional Embeddings, Positional Encoding Internals, RoPE Scaling for Long Contexts, Rotary Positional Embedding (RoPE), Sinusoidal Positional Encoding (Original Transformer), Beam Search (+17 more)

### Community 832 - "LLM Router — architecture"
Cohesion: 0.04
Nodes (43): 1. `LLMRouter` is the only gateway, 2. Providers are data, not code, 3. Secrets stay in the environment, 4. Three independent failure scopes, 5. Bulkhead isolation, 6. Context is managed losslessly, 7. Configuration is six committed YAML files, 8. Backwards compatibility by shim, not by rewrite (+35 more)

### Community 833 - "Killer TODO Roadmap — local-llm-server"
Cohesion: 0.05
Nodes (42): ★1 — 3-Phase Context-Pruner Middleware [P0] [CBF], ★2 — Specialized Sub-Agents with Per-Role Cheap Models [P0] [CBF + HRM], ★3 — Reasoning Token Budget + Toggle [P0] [NVD], ★4 — Skill/Procedural Memory (agentskills.io compatible) [P1] [HRM], ★6 — Cost Analytics + FTS5 Shared Memory + Agent Constitution [P1] [AOS], ★7 — Adaptive Loop Halting (Early Exit on High Confidence) [P1] [MYT + HRM], A1 — Hermes ChatML Prompt Format for Tool Calling [P0] [HRM], A2 — Multi-Hop Reasoning Chain (ReAct / Tree-of-Thought) [P0] [HRM] (+34 more)

### Community 834 - "CI Troubleshooting Runbook"
Cohesion: 0.18
Nodes (10): A test hangs in CI but passes locally, All three CI jobs fail with "git exit code 128" in Post Checkout, CI Troubleshooting Runbook, CodeQL action version, Frontend tests fail in parallel / async timer leaks, GitHub Actions YAML block scalar — bash heredoc content at column 0, Python 3.13 compatibility status, Python test job fails — "Process completed with exit code 1", no .pytest_cache found (+2 more)

### Community 835 - "NVIDIA NIM — Free Tier Setup"
Cohesion: 0.18
Nodes (10): 1. Get your free API key, 2. Set the environment variable, 3. Restart the server, 4. Verify, How the kill switch protects you, NVIDIA NIM — Free Tier Setup, Related, Setup (5 minutes) (+2 more)

### Community 836 - "What to clean up"
Cohesion: 0.20
Nodes (9): 2. Cloudflare Worker (frontend), 3. Local development machines, 4. GitHub secrets, 5. MongoDB collections, Post-Merge Environment Cleanup Guide, Post-merge verification checklist, Rollback, What changed (informational) (+1 more)

### Community 837 - "Worker Service — Operations Runbook"
Cohesion: 0.18
Nodes (10): Architecture, Deployment on Render, Environment variables, First-time setup, Graceful shutdown, Local development, Overview, Troubleshooting (+2 more)

### Community 838 - "test_bedrock_live.py"
Cohesion: 0.25
Nodes (10): _NEEDS_CREDS, asyncio, ProviderRouter discovers Bedrock from env and completes a real chat call., Health check returns True when real credentials are loaded from env., Call Bedrock Converse API directly with boto3 — no proxy layer., Verify the configured model ID accepts a converse request without auth errors., test_bedrock_direct_boto3_ping(), test_bedrock_health_check_with_real_creds() (+2 more)

### Community 840 - "get_data_dir"
Cohesion: 0.39
Nodes (5): _atomic_write_json(), get_data_dir(), _now(), Any, Path

### Community 841 - "build_tech_db.py"
Cohesion: 0.35
Nodes (10): _as_list(), _clean(), convert(), _default_source(), _has_pattern(), main(), Any, Strip Wappalyzer's `\\;tag:...` metadata, leaving a plain regex. (+2 more)

### Community 842 - "ai_insights.py"
Cohesion: 0.33
Nodes (6): Enum, str, AI-Assisted Engineering Insights — track AI tool usage, engagement, and…, Categories of AI engineering tools tracked., ToolKind, statistics

### Community 843 - "Security Policy"
Cohesion: 0.18
Nodes (11): Authentication, Authorization, How to Report, Known Security Trade-offs, Reporting a Vulnerability, Response Timeline, Scope, Security Design (+3 more)

### Community 844 - "UsageEvent"
Cohesion: 0.29
Nodes (5): A single AI tool interaction., Record a usage event., UsageEvent, A spread of events from 3 users across 3 tools over a week., sample_events()

### Community 845 - "test_conftest_hermetic_env.py"
Cohesion: 0.18
Nodes (10): parametrize, Guards the hermeticity contract that ``tests/conftest.py`` establishes. Rule 32…, conftest must pin every hermeticity flag before backend import., The env admin address must be the one ``backend.server`` captured.…, Guards the specific landmine: a module-level ADMIN_EMAIL setdefault.…, conftest must NOT pin ``STORAGE_BACKEND=sqlite``. It looks like the obvious…, test_admin_identity_matches_the_server_module(), test_conftest_does_not_pin_storage_backend() (+2 more)

### Community 846 - "main"
Cohesion: 0.29
Nodes (6): build_review_context(), _gh(), main(), Aggregate all review feedback for the PR into a single context string., ``(model_id, label)`` pairs, for callers that log a label., resolve_candidates()

### Community 847 - "TestResolution"
Cohesion: 0.29
Nodes (3): What callers actually use: live ids when available, static otherwise., Every id that answered 410 on 2026-08-27 must be gone from it., TestResolution

### Community 848 - "test_empirical_verify.py"
Cohesion: 0.49
Nodes (10): _make_runner(), MonkeyPatch, Path, Tests for AgentRunner._empirical_verify (opt-in executable validation gate)., test_empirical_verify_disabled_by_default(), test_empirical_verify_flags_compile_failure(), test_empirical_verify_passes_clean_module_without_tests(), test_empirical_verify_runs_matching_tests_and_passes() (+2 more)

### Community 849 - "test_event_log.py"
Cohesion: 0.45
Nodes (10): Path, _store(), test_append_event_payload_roundtrips(), test_append_event_positions_are_monotonic(), test_append_event_stores_and_increments_count(), test_events_are_isolated_per_session(), test_events_survive_store_restart(), test_get_events_empty_session() (+2 more)

### Community 850 - "TestZeroAttemptDiagnostics"
Cohesion: 0.25
Nodes (4): A zero-attempt exhaustion must say WHICH of the three causes it is. Nothing…, An operator whose switches reset on deploy needs to know that here., A broken registry must not turn a failed call into a crash., TestZeroAttemptDiagnostics

### Community 851 - "test_google_provider_models.py"
Cohesion: 0.18
Nodes (7): The Google provider must only advertise models its endpoint actually serves.…, A role must never be assigned a model the picker does not list., An operator override of GEMINI_MODEL must appear in the picker. The catalog is…, The Doctor probe must target the path Gemini actually serves., test_configured_gemini_model_is_always_selectable(), test_google_role_models_are_offered_by_the_catalog(), test_liveness_probe_resolves_gemini_openai_compat_base()

### Community 852 - "_step"
Cohesion: 0.25
Nodes (5): No issue to pick up means the retry handler never runs, so the job must not go…, Order matters: the label bump and issue reopen must complete before the job…, A run that implements nothing must not look like one that shipped., _step(), TestBarrenRunIsVisible

### Community 854 - "task.py"
Cohesion: 0.18
Nodes (11): Enum, Path, str, Task definition schema for the evaluation harness. Inspired by OpenHarness'…, Score the agent's final answer. Returns (success, score)., Returns (success: bool, score: float ∈ [0, 1]). Raises NotImplementedError for…, A fully-specified evaluation task. Fields mirror the OpenHarness task schema so…, SuccessCriterion (+3 more)

### Community 855 - "Instructions"
Cohesion: 0.20
Nodes (9): Acceptance Checks, Instructions, Skill: insights, Step 1 — File change heatmap (which files change most), Step 2 — Failure pattern analysis, Step 3 — Retry analysis, Step 4 — Learnings frequency analysis, Step 5 — Produce a summary report (+1 more)

### Community 856 - "Protocol: Premium Utilitarian Minimalism UI Architect"
Cohesion: 0.20
Nodes (9): 1. Protocol Overview, 2. Absolute Negative Constraints (Banned Elements), 3. Typographic Architecture, 4. Color Palette (Warm Monochrome + Spot Pastels), 5. Component Specifications, 6. Iconography & Imagery Directives, 7. Subtle Motion & Micro-Animations, 8. Execution Protocol (+1 more)

### Community 857 - "The 5-Step Wrap-Up Ritual"
Cohesion: 0.20
Nodes (9): Acceptance Checks, Skill: wrap-up, Step 1 — Changes Audit, Step 2 — Quality Check, Step 3 — Learning Capture, Step 4 — Next Session Planning, Step 5 — One-Paragraph Summary, The 5-Step Wrap-Up Ritual (+1 more)

### Community 858 - "._extract_tokens"
Cohesion: 0.40
Nodes (3): Any, Try to extract token count from various response formats., Execute an LLM completion, using cache when available. Args: model: Model…

### Community 859 - "Brag Plan: Autonomous AI Agency (feature tour, v2)"
Cohesion: 0.20
Nodes (9): Audio, Brag Plan: Autonomous AI Agency (feature tour, v2), Duration: ~44s (9 scenes) — intentionally longer than the /brag 15-25s default, per an explicit user request for a longer video, Format: landscape — 1920x1080, Storyboard (9 scenes), The angle, Tone, Visual identity (from the project) (+1 more)

### Community 860 - "Hyperframes Composition Brief: Autonomous AI Agency (feature tour, v2)"
Cohesion: 0.20
Nodes (9): Audio, Creative Direction, Hyperframes Composition Brief: Autonomous AI Agency (feature tour, v2), Hyperframes Instructions, Objective, Output, Source Material, Storyboard (+1 more)

### Community 861 - "_normalize_tool_choice"
Cohesion: 0.31
Nodes (4): _normalize_tool_choice(), Normalize the ``tool_choice`` parameter for the upstream backend. OpenAI…, Cloud models (with / in name) should keep tool_choice as-is., TestNormalizeToolChoice

### Community 862 - ".apply_diff"
Cohesion: 0.06
Nodes (35): Security surface, Activation, Agent: Reviewer (Verifier), Blocking Conditions (must return `fail`), Handoff, Key Invariant, Non-Blocking (may return `pass` with suggestions), Output Format (+27 more)

### Community 863 - "Skill: Agentic Agile"
Cohesion: 0.20
Nodes (9): Autonomous ceremonies (`agents/agile_ceremonies.py`), Key Classes, Purpose, Related, Retrospective & health, Scheduled workflow, Skill: Agentic Agile, Testing (+1 more)

### Community 864 - "Skill: browserbase-ui-test — Adversarial UI Testing"
Cohesion: 0.20
Nodes (9): Applying to local-llm-server platform, Core philosophy, Execution pattern, Reporting, Round 1 — Core flow mapping, Round 2 — Adversarial scenarios, Round 3 — Accessibility + mobile, Skill: browserbase-ui-test — Adversarial UI Testing (+1 more)

### Community 865 - "Skill: financial-analyst (Agentic CFO)"
Cohesion: 0.20
Nodes (9): Branch, Components, Decision Rules, Purpose, Quick Start, Skill: financial-analyst (Agentic CFO), SKILL.md refresh Tue Jun  2 11:35:52 CEST 2026, Testing (+1 more)

### Community 866 - "Graphiti Temporal Context Skill"
Cohesion: 0.20
Nodes (9): 1. Agent Memory as Temporal Graph, 2. Multi-Agent Coordination, 3. Knowledge Queries, Database Schema, Files to Create, Graphiti Temporal Context Skill, Integration Opportunities, References (+1 more)

### Community 867 - "Skill: seo-audit-report"
Cohesion: 0.20
Nodes (9): How This Skill Works (Agent Instructions), Output Files, Parameters, Purpose, Quick Start, Revenue-at-Risk Disclaimer (load-bearing — always include in reports), Skill: seo-audit-report, Troubleshooting (+1 more)

### Community 868 - "_wfo_owned_run_or_404"
Cohesion: 0.33
Nodes (6): Fetch a run, enforcing per-user ownership (admins bypass). Returns 404 — not…, Approve a run paused at the ApprovalGate and resume execution., Get a single workflow orchestrator run by ID (owner or admin only)., _wfo_owned_run_or_404(), workflow_orchestrator_approve(), workflow_orchestrator_get_run()

### Community 869 - "Agent Readiness Report"
Cohesion: 0.20
Nodes (9): Agent Readiness Report, Build System — 100/100, Dev Environment — 100/100, Documentation — 100/100, Observability — 100/100, Security — 100/100, Style And Validation — 100/100, Task Discovery — 100/100 (+1 more)

### Community 870 - "Core Pillars"
Cohesion: 0.40
Nodes (5): 1. Unified Intent Orchestration, 2. Deep Sticky Memory, 3. Execution Cognition Flow, 4. Progress Humanization, Core Pillars

### Community 871 - "467 Golden Path — Locked Implementation Order"
Cohesion: 0.20
Nodes (10): 467 Golden Path — Locked Implementation Order, Agent Code (agent/ directory), Backend Code (backend/, handlers/), Golden Path Exceptions, Module-Specific Golden Paths, Skill Code (.agents/skills/), Verification, What Breaks the Golden Path (+2 more)

### Community 872 - "orchestrator"
Cohesion: 0.33
Nodes (6): B.1 — Open the service's Environment tab, B.2 — Set these five keys on each service, B.3 — Sanity-check the secrets that must NOT regress, B.4 — Trigger TASK 5 keep-alive immediately, Option B — manual per-service editor, orchestrator()

### Community 873 - "The Agent Roster"
Cohesion: 0.33
Nodes (6): 🔨 Implementer, ⚖️ Judge, 📋 Planner, 🔍 Reviewer, 🔭 Scout, The Agent Roster

### Community 875 - "LLM Router — provider guide"
Cohesion: 0.22
Nodes (8): Adding any OpenAI-compatible provider, Auth styles, Cheap tiers, Cloud providers, Free tiers, LLM Router — provider guide, Multiple keys, Premium

### Community 876 - "One command (recommended)"
Cohesion: 0.20
Nodes (10): Add a model provider (optional but recommended), Docker Compose, Flags, One command (recommended), Requirements, Run the agency locally, Troubleshooting, What comes up (+2 more)

### Community 877 - "ENGINEERING_STANDARDS.md — Patterns & Reference"
Cohesion: 0.22
Nodes (9): Architecture decision records, Authorization patterns, Commit messages, Database indexes, ENGINEERING_STANDARDS.md — Patterns & Reference, Error handling, Log levels, Performance targets (+1 more)

### Community 880 - "ChatResponse"
Cohesion: 0.15
Nodes (5): CerebrasProvider, Any, Send a chat request with automatic failover. Retry policy: 1. If ``model`` is…, ChatResponse, Standard response from a provider chat call.

### Community 883 - "enrich_quick_note_issues.py"
Cohesion: 0.36
Nodes (9): _dispatch_generation(), _fetch_open_issues(), _has_context(), _headers(), _is_quick_note(), main(), Ask the bulk context workflow to generate documents for these issues., Find quick-note issues that have no context document and queue real generation.… (+1 more)

### Community 884 - "_start_ceo_agency"
Cohesion: 0.27
Nodes (8): Start the 24×7 CEO agency loop that *proactively* generates work. Without this…, _start_ceo_agency(), tests/test_ceo_agency_startup.py — the CEO loop must actually be started. Root…, A failure constructing/starting the CEO must not crash app startup., _reset_agency_singleton(), test_ceo_agency_can_be_disabled(), test_ceo_agency_starts_by_default(), test_ceo_agency_startup_never_raises()

### Community 886 - "TestDisabledProvidersAreNotFalselyReportedUnreachable"
Cohesion: 0.17
Nodes (7): Rule 6: secrets are never logged, not even partially., Error paths print exception text — that must not carry the key., Local providers (ollama, lmstudio, vllm, localai) default to a localhost…, ``gh workflow run ... -f provider=ollama`` must still work: an operator…, TestDisabledProvidersAreNotFalselyReportedUnreachable, TestNoKeyEverReachesTheLog, _boom()

### Community 890 - "test_model_catalog_guard.py"
Cohesion: 0.29
Nodes (8): _declared(), Unit tests for scripts/check_model_catalog_consistency.py. The guard is CI's…, The shipped catalogues must pass the guard — this is what CI enforces., test_declared_folds_both_provider_spellings(), test_legacy_only_provider_is_not_a_contradiction(), test_prefer_models_must_be_declared(), test_real_contradiction_is_a_hard_failure(), test_the_real_repo_catalogues_are_consistent()

### Community 891 - "TestMongoGate"
Cohesion: 0.20
Nodes (3): Tests must never mutate a shared operational store., The storage layer's localhost default is a placeholder, not config. Treating it…, TestMongoGate

### Community 892 - "test_render_mcp.py"
Cohesion: 0.07
Nodes (21): _as_list(), _coerce_payload(), Return tool output as Python data. MCP tool results arrive either as…, Normalise a tool payload into a list of dicts. Upstream tools variously return…, _env(), _FakeInner, Any, tests/test_render_mcp.py — Render MCP integration. Covers: - MCPClient… (+13 more)

### Community 894 - "test_workflow_api_mount.py"
Cohesion: 0.20
Nodes (9): tests/test_workflow_api_mount.py — the CRISPY workflow router is mounted and…, Anonymous callers are rejected (401), never served., A signed-in non-admin is forbidden (403) — this is an admin surface., An admin reaches the mounted router and gets a well-formed list payload., A missing run returns 404 from the handler, proving the route exists (an…, test_workflow_list_forbidden_for_non_admin(), test_workflow_list_ok_for_admin(), test_workflow_list_requires_authentication() (+1 more)

### Community 895 - "tts.py"
Cohesion: 0.31
Nodes (10): concurrent_futures, _convert_to_ogg(), voice/tts.py — Text-to-Speech for the CEO voice pipeline. Converts text to an…, Convert audio to OGG Opus (Telegram voice note format) via pydub+ffmpeg., Convert text to OGG voice note bytes. Returns None on failure., _select_backend(), synthesize(), _synthesize_elevenlabs() (+2 more)

### Community 896 - "WorkspaceEscapeError"
Cohesion: 0.40
Nodes (3): Resolve *relative* inside source dir and reject traversal/symlink escapes., Resolve *relative* within *ws*.source and reject traversal/symlink escapes.…, WorkspaceEscapeError

### Community 898 - "_rrf"
Cohesion: 0.40
Nodes (5): Combine ranked lists with Reciprocal Rank Fusion., _rrf(), test_rrf_merges_two_rankings(), test_rrf_scores_descending(), test_rrf_single_ranking_preserves_order()

### Community 899 - "_extract_workflow_relevance"
Cohesion: 0.33
Nodes (4): _extract_workflow_relevance(), Return workflow types mentioned in the skill content., Tests for _extract_workflow_relevance()., TestExtractWorkflowRelevance

### Community 900 - "WorkflowTransition"
Cohesion: 0.33
Nodes (6): _append_transition(), BaseModel, Add a workflow transition to the task's history list., WorkflowTransition, test_workflow_transition_defaults(), test_workflow_transition_serialises()

### Community 901 - "Skill: changelog-enforcer"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Changelog Location, Entry Format, Examples, Hook Behaviour, Instructions, Skill: changelog-enforcer, When to Use

### Community 902 - "Skill: learn-rule"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Instructions, Learnings File Format, Skill: learn-rule, Step 1 — Identify the rule, Step 2 — Append to learnings file, Step 3 — Check if CLAUDE.md should be updated, When to Use

### Community 903 - "Instructions"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Instructions, Skill: session-handoff, Step 1 — Capture current state, Step 2 — Write the handoff document, Step 3 — Update machine-readable state, Step 4 — Confirm the handoff is self-contained, When to Use

### Community 904 - "la"
Cohesion: 0.28
Nodes (9): Aa(), Animation(), Ca(), Da(), la(), na(), Ua(), Va() (+1 more)

### Community 905 - "Command: /resume"
Cohesion: 0.40
Nodes (4): Command: /resume, References, Usage, What It Does

### Community 906 - "Skill: Agentic Portfolio Management"
Cohesion: 0.13
Nodes (12): InitiativeProgress, Delivery roll-up for a single initiative across its linked sprints., Percentage of linked sprint points completed., Aggregate delivery progress per initiative from its linked sprints. Reads each…, Key Classes, Purpose, Related, Skill actions (via SkillBindings) (+4 more)

### Community 907 - "Skill: changelog-enforcer"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Changelog Location, Entry Format, Examples, Hook Behaviour, Instructions, Skill: changelog-enforcer, When to Use

### Community 908 - "Skill: cowork-session (Claude Cowork)"
Cohesion: 0.22
Nodes (8): Branch, Components, Purpose, Quick Start, Session Roles, Skill: cowork-session (Claude Cowork), Testing, When to Use

### Community 909 - "Skill: video-context — read a video without watching it"
Cohesion: 0.22
Nodes (8): How It Works, Limits — know these before relying on it, Skill: video-context — read a video without watching it, Testing, Usage, What To Do With The Transcript, When To Use This, Why This Exists

### Community 910 - ".daily_active_users"
Cohesion: 0.40
Nodes (3): datetime, Number of unique users with at least one event on the given day., Unique users in the 7 days ending at `end` (default: now).

### Community 911 - "autonomy_status"
Cohesion: 0.40
Nodes (5): autonomy_status(), Public autonomy readiness probe — no authentication required. A live deploy…, Fire-and-forget self-bootstrap; never blocks or crashes startup., _schedule_self_bootstrap(), self_bootstrap_enabled()

### Community 912 - "ADR 003: Multi-Agent Orchestration with Plan-Execute-Verify Loop"
Cohesion: 0.22
Nodes (8): ADR 003: Multi-Agent Orchestration with Plan-Execute-Verify Loop, Alternatives Considered, Consequences, Context, Decision, Negative, Neutral, Positive

### Community 913 - "Documentation map"
Cohesion: 0.40
Nodes (5): Architecture and operations, Documentation map, Repo hygiene, Screenshots and README sync, Start here

### Community 914 - "The 8-Step Golden Path"
Cohesion: 0.22
Nodes (9): Step 1: Scout — Understand the territory, Step 2: Plan — Define the change, Step 3: Write tests first, Step 4: Implement, Step 5: Validate, Step 6: Review, Step 7: Document, Step 8: Commit and propose (+1 more)

### Community 915 - "Issue #1356: quick-note:https://searchengineland.com/turn-seo-backlog-into-roadmap-485713"
Cohesion: 0.22
Nodes (8): Architectural Notes, Context Plan — Issue #1356: quick-note:https://searchengineland.com/turn-seo-backlog-into-roadmap-485713, Decision, Issue #1356: quick-note:https://searchengineland.com/turn-seo-backlog-into-roadmap-485713, Quality Gate, Source Grounding, What the source actually is, What was considered

### Community 916 - "_clean_singletons"
Cohesion: 0.40
Nodes (5): Test hook — clear all usage accounting., reset(), Test hook — drop every cache layer., reset(), _clean_singletons()

### Community 917 - "KV Cache Internals"
Cohesion: 0.22
Nodes (9): KV Cache Internals, KV Cache with Grouped Query Attention, Memory Layout, Paged Attention (vLLM), Prefill vs Decode Phase, Quantization of KV Cache, Speculative Decoding, The Problem: Redundant Computation (+1 more)

### Community 918 - "Release Procedure"
Cohesion: 0.22
Nodes (8): Changelog Update, Commit and Tag, Post-Release Checklist, Pre-Flight, Release Procedure, Rollback, Verify CI, Version Bump

### Community 919 - "V2.0 Modernization — Runbook"
Cohesion: 0.22
Nodes (8): Adding a new provider adapter, CI, Importing new code, Module map (old → new), Removing the shims (future cleanup), Rollback, Test migration, V2.0 Modernization — Runbook

### Community 920 - "Setup"
Cohesion: 0.25
Nodes (7): 1. Get LiveKit credentials, 2. Configure the backend (Render env vars), 3. The SAM voice worker, 4. Talk to SAM, SAM Realtime Voice over LiveKit, Setup, Troubleshooting

### Community 921 - "Troubleshooting"
Cohesion: 0.04
Nodes (55): 401 Unauthorized, 403 Forbidden from remote machine, 429 Too Many Requests, Agent API Issues, Agent makes a change but doesn't verify correctly, Agent returns empty or incomplete plan, Agent workspace errors ("file not found"), Authentication Issues (+47 more)

### Community 922 - "_get_current_user"
Cohesion: 0.25
Nodes (9): _get_bearer_token(), _get_current_user(), logout(), Depends, get, Extract and validate current user from token., Get current authenticated user., Logout (token invalidation happens on frontend by clearing localStorage). (+1 more)

### Community 923 - "BrainWatchdog"
Cohesion: 0.08
Nodes (21): N1. Activate the reliability spine — wire the watchdog, schedule the digest ⬜  (size: M, risk: low), packages_ai, BrainWatchdog, Any, Reset failure counter for a provider after a successful call., Fail over to the next available provider., Send a Telegram notification about the failover., Reset the singleton (test helper). (+13 more)

### Community 924 - "get_control"
Cohesion: 0.22
Nodes (9): Of *changed*, the keys whose readers only see the new value after a restart., _restart_required(), get_control(), The spec for *key*, or ``None`` when it is not operator-controllable., The call-volume throttle is present, numeric, and defaults to the calmer free-…, A runtime an operator cannot pick from the dropdown is unreachable., test_agency_tick_minutes_throttle_exists(), test_restart_required_lists_only_non_live_controls() (+1 more)

### Community 925 - "send_digest"
Cohesion: 0.40
Nodes (4): Send the digest text via NotificationDispatcher (Telegram)., send_digest(), patch, TestSendDigest

### Community 926 - "run_patched_colibri.py"
Cohesion: 0.27
Nodes (8): runpy, _exit_watch_delay(), main(), _patched_popen(), scripts/run_patched_colibri.py Pre-launch wrapper for JustVugg/colibri…, Resolve the COLIBRI_PATCH_EXIT_WATCH delay in seconds, clamped to [0, 60].…, Intercept JustVugg Engine -> glm.exe Popen and forward outer argv. Upstream…, _resolve_target()

### Community 927 - "._get_checkpoint_store"
Cohesion: 0.20
Nodes (5): get_orchestrator_checkpoint_store(), _NoopStore, Any, List recent runs. When ``owner_id`` is provided, only runs stamped with that…, No-op checkpoint store when the real one is unavailable.

### Community 928 - "TestDashboard"
Cohesion: 0.22
Nodes (4): Run fn() and report any critical console errors., Dashboard page — stats, activity, navigation., TestDashboard, with_console_check()

### Community 929 - "test_backend_requirements_cover_runtime_imports.py"
Cohesion: 0.25
Nodes (8): _declared_packages(), parametrize, Path, Guard against the recurring "works in CI, missing in prod" dependency drift.…, Return the normalised distribution names declared in *requirements*., If the Dockerfile ever installs the root file, this guard can relax. Until then…, test_backend_requirements_declares_runtime_package(), test_dockerfile_still_installs_backend_requirements_only()

### Community 930 - "TestDirectChatNonBlocking"
Cohesion: 0.40
Nodes (3): Non-agent mode must take the direct chat path, not the agent job path., Trivial greetings must always use direct mode even if agent_mode=True., TestDirectChatNonBlocking

### Community 931 - "test_probe_base_url_override_hits_the_typed_url"
Cohesion: 0.22
Nodes (4): _FakeResp, An Ollama probe with base_url must hit THAT url's /api/tags, not the saved one., test_probe_base_url_override_hits_the_typed_url(), get()

### Community 932 - ".test_every_request_carries_a_real_user_agent"
Cohesion: 0.22
Nodes (3): ``urllib``'s default User-Agent is a 403 waiting to happen. Unset, every…, ``extra_headers`` is applied last, so a provider stays in control., TestTheProbeIdentifiesItself

### Community 933 - "test_changelog_parity_guard.py"
Cohesion: 0.22
Nodes (3): tests/test_changelog_parity_guard.py — corruption guard for the changelog gate.…, A 7-equals line under a title (Markdown setext H1) must not false-positive., test_setext_heading_underline_is_not_flagged()

### Community 934 - ".log"
Cohesion: 0.50
Nodes (3): Any, Return recent commits with agent attribution trailers parsed out., Web UI (Claude Code–style)

### Community 936 - "test_process_quick_note_workflow.py"
Cohesion: 0.25
Nodes (7): _full_suite_jobs(), job(), Tests for ``.github/workflows/process-quick-note.yml``. Two defects, one…, The context plan's own reject verdict (step 7b's plan_gate) is a second…, _runs_full_suite(), TestRetryDoesNotOverrideAPlanGateRejection, workflow_text()

### Community 937 - "TestEveryFullSuiteJobHasMongo"
Cohesion: 0.22
Nodes (6): parametrize, The invariant, stated once for the whole repo. Adding the service to two…, Guards the guard: a regex that matches nothing would pass silently., A pytest that starts a moment early reproduces the very defect the service…, TestEveryFullSuiteJobHasMongo, TestMongoIsReadyBeforeAnyPytest

### Community 938 - "TestPaidPolicyDurability"
Cohesion: 0.22
Nodes (3): This is the document the UI toggle writes via _set_provider_policy., Never enable paid spend by accident., TestPaidPolicyDurability

### Community 939 - "test_scanner_deps_parity.py"
Cohesion: 0.31
Nodes (8): _declared_packages(), Guard against the CI-vs-production dependency drift that made gucci.com (and…, Top-level module names imported anywhere in services/scanner.py., Every third-party package the scanner imports must be in the file the…, Belt-and-suspenders: the two deps whose absence caused the gucci.com production…, _scanner_imports(), test_critical_scanner_deps_explicitly_present(), test_scanner_third_party_deps_declared_in_backend_requirements()

### Community 940 - "test_serve_spa_prefixes.py"
Cohesion: 0.27
Nodes (9): backend, _prefixes(), Behavioral: GET to a path that has NO upstream handler but IS in the protected…, Regression tests for SPA catch-all prefix protection (backend/server.py). Bug…, SPA_PROTECTED_PREFIXES must be exposed at module scope (not inside an if-block)…, test_legitimate_spa_paths_are_not_blocked(), test_protected_paths_are_covered_by_prefix_tuple(), test_serve_spa_returns_non_html_for_protected_orphan_path() (+1 more)

### Community 941 - "dry_clone_repo"
Cohesion: 0.31
Nodes (5): test_dry_clone_repo_handles_missing_url(), test_dry_clone_repo_handles_subprocess_failure(), dry_clone_repo(), Validate repository access by performing a shallow, no-checkout git clone and…, Attempt a shallow, non-checkout clone into a temporary directory to validate…

### Community 942 - "_safe_resolve"
Cohesion: 0.25
Nodes (4): If a symlink inside the workspace points outside, resolve_path blocks it., TestPathSafety, Resolve *path* and verify it stays under *base_root*. Blocks symlink escape:…, _safe_resolve()

### Community 943 - "stt.py"
Cohesion: 0.36
Nodes (8): voice/stt.py — Speech-to-Text for the CEO voice pipeline. Transcribes audio…, Transcribe audio bytes to text. Returns empty string on failure., Fallback: Google Web Speech API via SpeechRecognition library., _select_backend(), transcribe(), _transcribe_google(), _transcribe_local(), _transcribe_openai()

### Community 945 - "_score_turns"
Cohesion: 0.36
Nodes (8): Score each turn by exponential recency decay combined with query relevance.…, _score_turns(), test_score_turns_empty(), test_score_turns_importance_multiplier(), test_score_turns_recency_newer_scores_higher(), test_score_turns_relevance_boosts_score(), test_score_turns_sorted_descending(), _turn()

### Community 947 - "Any"
Cohesion: 0.25
Nodes (3): Any, Apply context updates from a contributor. Only the active editor can modify…, Run one sync tick across all sessions. Actions taken: - Kick idle active…

### Community 948 - "quality_checker.py"
Cohesion: 0.32
Nodes (6): AITellType, Enum, str, Quality checker inspired by stop-slop (https://github.com/hardikpandya/stop-…, Categories of AI tells, Tests for quality checker (stop-slop inspired)

### Community 949 - "Skill: docs-sync"
Cohesion: 0.25
Nodes (7): Acceptance Checks, ADR Guidelines, AGENTS.md Update Rules, Docs to Check After Each Change Type, Instructions, Skill: docs-sync, When to Use

### Community 950 - "Agent: Implementer (Executor)"
Cohesion: 0.20
Nodes (8): Activation, Agent: Implementer (Executor), Constraints, Handoff, Preferred Model, Responsibilities, Role, Shared State

### Community 951 - "Agent: Judge (Release / QA Gate)"
Cohesion: 0.29
Nodes (7): Activation, Agent: Judge (Release / QA Gate), Enforcement, Output, Responsibilities, Role, Verdict Meanings

### Community 952 - "4. Agent Execution Performance"
Cohesion: 0.50
Nodes (4): 4. Agent Execution Performance, PERF-007 [HIGH] — Sequential Plan Steps (No Parallelism), PERF-008 [MEDIUM] — Large Context Window Growth, PERF-009 [MEDIUM] — RepowiseIntelligence Reads Files on Every Call

### Community 953 - "Skill: browserbase-browser — Real Browser Automation"
Cohesion: 0.25
Nodes (7): Applying to local-llm-server platform, Core commands, Mode selection, Setup, Skill: browserbase-browser — Real Browser Automation, Troubleshooting, Workflow pattern

### Community 954 - "Skill: docs-sync"
Cohesion: 0.25
Nodes (7): Acceptance Checks, ADR Guidelines, CLAUDE.md Update Rules, Docs to Check After Each Change Type, Instructions, Skill: docs-sync, When to Use

### Community 955 - "Skill: memory-consolidation (Dream Memory)"
Cohesion: 0.25
Nodes (7): Branch, Consolidation Lifecycle, Memory Kinds, Purpose, Quick Start, Skill: memory-consolidation (Dream Memory), Testing

### Community 956 - "GitHub Branch Protection Settings"
Cohesion: 0.25
Nodes (7): Branch name pattern: `main` (or `master`), CODEOWNERS Setup, Enabling via GitHub CLI, GitHub Branch Protection Settings, Purpose, Required Settings, Why This Can't Be Fully Repo-Enforced

### Community 957 - "ADR 001: Self-Hosted OpenAI-Compatible Proxy"
Cohesion: 0.25
Nodes (7): ADR 001: Self-Hosted OpenAI-Compatible Proxy, Consequences, Context, Decision, Negative, Neutral, Positive

### Community 958 - "ADR 002: Dynamic Model Routing with Task Classification"
Cohesion: 0.25
Nodes (7): ADR 002: Dynamic Model Routing with Task Classification, Consequences, Context, Decision, Negative, Neutral, Positive

### Community 960 - "AGENTS.md — AI Agent Configuration for local-llm-server"
Cohesion: 0.25
Nodes (7): Agent Roles, AGENTS.md — AI Agent Configuration for local-llm-server, Operating Instructions, Quick Start for Agents, Risky Paths — Require Extra Care, State Files, Workspace Purpose

### Community 961 - "Advisor Strategy — Local Proxy Handling"
Cohesion: 0.29
Nodes (6): Advisor Strategy — Local Proxy Handling, How This Proxy Handles Advisor Requests, Incoming message history (advisor blocks), Outgoing requests (tools array), Using the Real Advisor Strategy via This Proxy, What the Anthropic Advisor Strategy Is

### Community 962 - "ceo-micromanagement.md"
Cohesion: 0.25
Nodes (4): P0 behavior change, Readiness contract, Runtime model, Runtime types

### Community 963 - "Feature Maturity / Support Matrix"
Cohesion: 0.29
Nodes (7): Beta, Config Overrides, Disabled (demoted per issue #467 Section I), Enforcement, Experimental, Feature Maturity / Support Matrix, Maturity Tiers

### Community 964 - "Web UI + Admin (Claude Code–style)"
Cohesion: 0.25
Nodes (7): Acceptance checks, Approach, Files to change, Files to read first, Goal, Risks, Web UI + Admin (Claude Code–style)

### Community 965 - "467 Skill Inventory — load / wire / test status"
Cohesion: 0.25
Nodes (7): 467 Skill Inventory — load / wire / test status, Agent Specialties (not skills per se, but referenced in spec §B), Core Agency Skills (load/wire/test), Gaps Summary, Named Skills Referenced in Spec §C, Skill Registry, Test Coverage Summary

### Community 966 - "_reset"
Cohesion: 0.50
Nodes (4): _build_cost_table(), _load_env_overrides(), Parse MODEL_COST_INPUT / MODEL_COST_OUTPUT env overrides. Format:…, _reset()

### Community 967 - "Issue #362: Nvidia repo setup"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #362: Nvidia repo setup, Implementation Prompt, Issue #362: Nvidia repo setup, Relevant Files to Read First, Risk Flags, TODO List

### Community 968 - "Issue #364: quick-note:https://www.marktechpost.com/2026/06/01/meet-memory-os-a-6-layer-open-source-memory-stack-built-on-top-of-hermes-agent/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #364: quick-note:https://www.marktechpost.com/2026/06/01/meet-memory-os-a-6-layer-open-source-memory-stack-built-on-top-of-hermes-agent/, Implementation Prompt, Issue #364: quick-note:https://www.marktechpost.com/2026/06/01/meet-memory-os-a-6-layer-open-source-memory-stack-built-on-top-of-hermes-agent/, Relevant Files to Read First, Risk Flags, TODO List

### Community 969 - "Issue #378: quick-note:https://www.marktechpost.com/2026/06/02/tinyfish-launches-bigset-an-open-source-multi-agent-system-that-builds-structured-live-datasets-from-plain-english-descriptions/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #378: quick-note:https://www.marktechpost.com/2026/06/02/tinyfish-launches-bigset-an-open-source-multi-agent-system-that-builds-structured-live-datasets-from-plain-english-descriptions/, Implementation Prompt, Issue #378: quick-note:https://www.marktechpost.com/2026/06/02/tinyfish-launches-bigset-an-open-source-multi-agent-system-that-builds-structured-live-datasets-from-plain-english-descriptions/, Relevant Files to Read First, Risk Flags, TODO List

### Community 970 - "Issue #379: quick-note:https://searchengineland.com/schema-markup-optimize-agentic-web-479080"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #379: quick-note:https://searchengineland.com/schema-markup-optimize-agentic-web-479080, Implementation Prompt, Issue #379: quick-note:https://searchengineland.com/schema-markup-optimize-agentic-web-479080, Relevant Files to Read First, Risk Flags, TODO List

### Community 971 - "Issue #380: quick-note:https://cursor.com/blog/cloud-agent-lessons"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #380: quick-note:https://cursor.com/blog/cloud-agent-lessons, Implementation Prompt, Issue #380: quick-note:https://cursor.com/blog/cloud-agent-lessons, Relevant Files to Read First, Risk Flags, TODO List

### Community 972 - "Issue #381: quick-note:https://www.xda-developers.com/claude-code-with-opus-48-is-expensive-but-i-made-it-efficient-with-my-local-ai-workflow/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #381: quick-note:https://www.xda-developers.com/claude-code-with-opus-48-is-expensive-but-i-made-it-efficient-with-my-local-ai-workflow/, Implementation Prompt, Issue #381: quick-note:https://www.xda-developers.com/claude-code-with-opus-48-is-expensive-but-i-made-it-efficient-with-my-local-ai-workflow/, Relevant Files to Read First, Risk Flags, TODO List

### Community 973 - "Issue #382: quick-note:https://claude.com/blog/how-coderabbit-used-claude-to-build-an-agent-orchestration-system"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #382: quick-note:https://claude.com/blog/how-coderabbit-used-claude-to-build-an-agent-orchestration-system, Implementation Prompt, Issue #382: quick-note:https://claude.com/blog/how-coderabbit-used-claude-to-build-an-agent-orchestration-system, Relevant Files to Read First, Risk Flags, TODO List

### Community 974 - "Issue #383: quick-note:https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #383: quick-note:https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/, Implementation Prompt, Issue #383: quick-note:https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/, Relevant Files to Read First, Risk Flags, TODO List

### Community 975 - "Issue #416: feat: Self-hosted Codebuff (freebuff) on free NVIDIA models + Telegram bot phone control"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #416: feat: Self-hosted Codebuff (freebuff) on free NVIDIA models + Telegram bot phone control, Implementation Prompt, Issue #416: feat: Self-hosted Codebuff (freebuff) on free NVIDIA models + Telegram bot phone control, Relevant Files to Read First, Risk Flags, TODO List

### Community 976 - "Issue #485: [Trend Digest] Week of 2026-06-08"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #485: [Trend Digest] Week of 2026-06-08, Implementation Prompt, Issue #485: [Trend Digest] Week of 2026-06-08, Relevant Files to Read First, Risk Flags, TODO List

### Community 977 - "Issue #488: quick-note:https://github.com/cookiy-ai/user-research-skill"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #488: quick-note:https://github.com/cookiy-ai/user-research-skill, Implementation Prompt, Issue #488: quick-note:https://github.com/cookiy-ai/user-research-skill, Relevant Files to Read First, Risk Flags, TODO List

### Community 978 - "Issue #491: Implement whatever is necessary from https://github.com/BehiSecc/awesome-claude-skills"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #491: Implement whatever is necessary from https://github.com/BehiSecc/awesome-claude-skills, Implementation Prompt, Issue #491: Implement whatever is necessary from https://github.com/BehiSecc/awesome-claude-skills, Relevant Files to Read First, Risk Flags, TODO List

### Community 979 - "Issue #493: Use the https://github.com/mvanhorn/last30days-skill skill to get the trend updated"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #493: Use the https://github.com/mvanhorn/last30days-skill skill to get the trend updated, Implementation Prompt, Issue #493: Use the https://github.com/mvanhorn/last30days-skill skill to get the trend updated, Relevant Files to Read First, Risk Flags, TODO List

### Community 980 - "Issue #495: Read https://www.anthropic.com/news/claude-fable-5-mythos-5 and understand if mythos or fable can be added to the repo"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #495: Read https://www.anthropic.com/news/claude-fable-5-mythos-5 and understand if mythos or fable can be added to the repo, Implementation Prompt, Issue #495: Read https://www.anthropic.com/news/claude-fable-5-mythos-5 and understand if mythos or fable can be added to the repo, Relevant Files to Read First, Risk Flags, TODO List

### Community 981 - "Issue #504: EPIC: Autonomy hardening — live-verified defects 2026-06-10"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #504: EPIC: Autonomy hardening — live-verified defects 2026-06-10, Implementation Prompt, Issue #504: EPIC: Autonomy hardening — live-verified defects 2026-06-10, Relevant Files to Read First, Risk Flags, TODO List

### Community 982 - "Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass, Implementation Prompt, Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass, Relevant Files to Read First, Risk Flags, TODO List

### Community 983 - "_clean_director"
Cohesion: 0.50
Nodes (4): Clear director state and the cached strategy warnings (tests only)., reset(), _clean_director(), Reset the process singleton around every test.

### Community 984 - "Issue #657: quick-note:https://github.com/earendil-works/pi"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #657: quick-note:https://github.com/earendil-works/pi, Implementation Prompt, Issue #657: quick-note:https://github.com/earendil-works/pi, Relevant Files to Read First, Risk Flags, TODO List

### Community 985 - "Issue #659: quick-note:https://github.com/nex-agi/Nex-N2"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #659: quick-note:https://github.com/nex-agi/Nex-N2, Implementation Prompt, Issue #659: quick-note:https://github.com/nex-agi/Nex-N2, Relevant Files to Read First, Risk Flags, TODO List

### Community 986 - "Issue #660: quick-note:https://github.com/getsentry/sentry-for-ai"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #660: quick-note:https://github.com/getsentry/sentry-for-ai, Implementation Prompt, Issue #660: quick-note:https://github.com/getsentry/sentry-for-ai, Relevant Files to Read First, Risk Flags, TODO List

### Community 987 - "Issue #661: quick-note:https://github.com/XiaomiMiMo/MiMo-Code"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #661: quick-note:https://github.com/XiaomiMiMo/MiMo-Code, Implementation Prompt, Issue #661: quick-note:https://github.com/XiaomiMiMo/MiMo-Code, Relevant Files to Read First, Risk Flags, TODO List

### Community 988 - "Issue #664: quick-note:https://github.com/Grominet95/jarvis-OS"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #664: quick-note:https://github.com/Grominet95/jarvis-OS, Implementation Prompt, Issue #664: quick-note:https://github.com/Grominet95/jarvis-OS, Relevant Files to Read First, Risk Flags, TODO List

### Community 989 - "Issue #666: quick-note:https://github.com/porokka/jarvis-os"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #666: quick-note:https://github.com/porokka/jarvis-os, Implementation Prompt, Issue #666: quick-note:https://github.com/porokka/jarvis-os, Relevant Files to Read First, Risk Flags, TODO List

### Community 990 - "Issue #670: quick-note:https://github.com/perplexityai/bumblebee"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #670: quick-note:https://github.com/perplexityai/bumblebee, Implementation Prompt, Issue #670: quick-note:https://github.com/perplexityai/bumblebee, Relevant Files to Read First, Risk Flags, TODO List

### Community 991 - "Issue #672: quick-note:https://github.com/Chachamaru127/claude-code-harness"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #672: quick-note:https://github.com/Chachamaru127/claude-code-harness, Implementation Prompt, Issue #672: quick-note:https://github.com/Chachamaru127/claude-code-harness, Relevant Files to Read First, Risk Flags, TODO List

### Community 992 - "Issue #676: quick-note:https://github.com/WeiboAI/VibeThinker"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #676: quick-note:https://github.com/WeiboAI/VibeThinker, Implementation Prompt, Issue #676: quick-note:https://github.com/WeiboAI/VibeThinker, Relevant Files to Read First, Risk Flags, TODO List

### Community 993 - "Issue #820: quick-note:https://github.com/cobusgreyling/loop-engineering"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #820: quick-note:https://github.com/cobusgreyling/loop-engineering, Implementation Prompt, Issue #820: quick-note:https://github.com/cobusgreyling/loop-engineering, Relevant Files to Read First, Risk Flags, TODO List

### Community 994 - "This repository is maintained by its own agents"
Cohesion: 0.50
Nodes (4): A sample of what the agents shipped (all merged, all real), The numbers (verifiable via the GitHub API), This repository is maintained by its own agents, Why this matters if you're evaluating the platform

### Community 995 - "Platform Controls"
Cohesion: 0.29
Nodes (7): Across processes, API, Groups, How a value is resolved, Live vs restart-required, Platform Controls, What is deliberately **not** here

### Community 996 - "_should_fan_out"
Cohesion: 0.50
Nodes (4): _complexity_rank(), _should_fan_out(), Default threshold is 'medium' — low complexity does NOT fan out., test_should_fan_out_respects_threshold()

### Community 997 - "E2BSandboxSession"
Cohesion: 0.13
Nodes (17): MCPUnavailableError, RuntimeError, Raised when the MCP server is unreachable or the circuit is open., ★5 — Sandboxed Agent Execution (E2B / Docker micro-VM) [P1] [CHM] ✅ Delivered 2026-07-04, E2BSandboxSession, Any, Create the sandbox. Raises :class:`MCPUnavailableError` on failure., Kill the sandbox. Idempotent; never raises (best-effort cleanup). (+9 more)

### Community 998 - "_is_brain_connection_error"
Cohesion: 0.50
Nodes (4): _is_brain_connection_error(), BaseException, True if *exc* looks like an LLM-brain/endpoint connectivity failure. Such…, test_is_brain_connection_error_matches_typical_failures()

### Community 999 - "_isolate_operator_provider_state"
Cohesion: 0.50
Nodes (4): _isolate_operator_provider_state(), MonkeyPatch, Path, Keep the suite out of the developer's real operator-state database.…

### Community 1000 - "Runbook — Instance Activation"
Cohesion: 0.25
Nodes (7): Option A — disable the gate (self-hosted), Option B — self-mint a signed code with your own key, Option C — request a code (downstream user), Runbook — Instance Activation, Security notes, TL;DR — you are blocked at the activation screen, Why activation exists

### Community 1001 - "test_probe_reports_dns_failure_end_to_end"
Cohesion: 0.50
Nodes (3): asyncio, The reason must survive the real probe entry point, not just the helper., test_probe_reports_dns_failure_end_to_end()

### Community 1002 - "Prime Agent Runtime"
Cohesion: 0.25
Nodes (8): Configuration, Deploying on Render, Installation, Prime Agent Runtime, `PRIME_AGENT_TRUST_WORKSPACE`, Routing LLM traffic through our proxy, Verifying, What the adapter drives

### Community 1003 - "TestScannerService"
Cohesion: 0.50
Nodes (3): Test scanner service., Test that scanner service can be initialized., TestScannerService

### Community 1004 - "PULL_REQUEST_TEMPLATE.md"
Cohesion: 0.25
Nodes (7): Changelog, Changes, Council Review (for larger PRs), Related, Risky Module Review, Summary, Testing

### Community 1005 - "security_fix_agent.py"
Cohesion: 0.46
Nodes (7): codeql_count(), dependabot_count(), main(), Any, OpenClaw security fix helper. Lightweight CLI used by CI to check/fix…, _repo_parts(), _request()

### Community 1006 - ".test_specialist_service_initialization"
Cohesion: 0.50
Nodes (3): Test specialist service., Test that specialist service can be initialized., TestSpecialistService

### Community 1007 - "verify.sh"
Cohesion: 0.50
Nodes (6): fail(), pass(), verify.sh script, snapshot_files(), write_legacy_roles(), write_v050_roles()

### Community 1008 - "Prompt Library"
Cohesion: 0.25
Nodes (8): Agents, Commands, How This Library Is Maintained, Philosophy, Prompt Library, Skills, Transparency, What Is This?

### Community 1009 - ".test_onboarding_service_initialization"
Cohesion: 0.50
Nodes (3): Test onboarding service., Test that onboarding service can be initialized., TestOnboardingService

### Community 1011 - "submit_simple_task"
Cohesion: 0.50
Nodes (4): Submit a task to the agent planner., Submit a simple task via the tasks API., submit_simple_task(), submit_task()

### Community 1012 - "2. Ollama Connection Handling"
Cohesion: 0.67
Nodes (3): 2. Ollama Connection Handling, PERF-003 [MEDIUM] — New httpx Client Per Request, PERF-004 [MEDIUM] — No Connection Pooling for Langfuse

### Community 1013 - "WebhookSendRequest"
Cohesion: 0.67
Nodes (3): BaseModel, Body for ``POST /api/connectors/webhook/send`` (rule 11 — no raw dict in)., WebhookSendRequest

### Community 1015 - "test_local_brain_router_smoke.py"
Cohesion: 0.25
Nodes (7): Smoke test: backend/local_brain_router is mounted on the public FastAPI app.…, Importing backend.server.app must not raise AttributeError or NameError., The /api/local-brain/state GET route must be reachable via the FastAPI app.…, The local_brain_router symbol MUST be importable + prefixed correctly. Quick…, test_backend_server_app_loads_without_attributeerror(), test_local_brain_router_module_is_wired(), test_local_brain_state_route_is_mounted_on_public_app()

### Community 1019 - "RuntimeHealth"
Cohesion: 0.06
Nodes (25): AiderAdapter, Any, Adapter for Aider — TIER 3 specialized git-aware code editor., Declare ``E2B_API_KEY`` as a required env dependency. The base ``preflight``…, GooseAdapter, Any, Adapter for Goose — TIER 2 general-purpose local runtime., One runtime dependency that can be validated during preflight. (+17 more)

### Community 1024 - "TOOLS.md — Available Tools for AI Agents"
Cohesion: 0.25
Nodes (7): AI Runner Tools, API Endpoints (when proxy is running), File Tools, OpenClaw Integration, Shell / Process Tools, Skills (invoke via CLAUDE.md instructions), TOOLS.md — Available Tools for AI Agents

### Community 1028 - "classify_domain"
Cohesion: 0.29
Nodes (6): classify_domain(), Classify domain from title+description; store on task_type., Return the best-matching domain for a task title+description., parametrize, test_classify_domain(), test_classify_domain_case_insensitive()

### Community 1030 - "Full-Output Enforcement"
Cohesion: 0.29
Nodes (6): Banned Output Patterns, Baseline, Execution Process, Full-Output Enforcement, Handling Long Outputs, Quick Check

### Community 1031 - "summarise.sh"
Cohesion: 0.48
Nodes (5): bottom(), divider(), row(), summarise.sh script, top()

### Community 1033 - "ModelRegistry"
Cohesion: 0.29
Nodes (4): ModelRegistry, A centralized registry for available LLM models and their metadata. This class…, Returns a list of all registered models metadata., Retrieves a specific model's metadata by its name (case-insensitive). Returns…

### Community 1034 - "wiki_client"
Cohesion: 0.22
Nodes (10): Changed, Fixed, [v4.1.0], Changed, Fixed, [v4.1.0], RoleBadge(), TestClient (+2 more)

### Community 1037 - "AI Engineering Insights Skill"
Cohesion: 0.18
Nodes (8): Fraction of suggestions accepted for the given tool., Tools ranked by acceptance rate (highest first)., AI Engineering Insights Skill, Integration Points, Key Design Choices, Module: `agents/ai_insights.py`, References, What's Unique About the DX Report

### Community 1038 - "Skill: hybrid-reasoning (Hybrid AI)"
Cohesion: 0.33
Nodes (5): Branch, Purpose, Quick Start, Skill: hybrid-reasoning (Hybrid AI), Testing

### Community 1040 - "Skill: Managed Agents Dreams"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: Managed Agents Dreams, Testing, Usage

### Community 1041 - "Skill: Multi-Agent Coordinator"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: Multi-Agent Coordinator, Testing, Usage

### Community 1042 - "Skill: Obsidian Knowledge Graph"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: Obsidian Knowledge Graph, Testing, Usage

### Community 1043 - "Multi-Agent Research Coordinator Skill"
Cohesion: 0.29
Nodes (6): Default Plan Shape, Module: `agents/research_coordinator.py`, Multi-Agent Research Coordinator Skill, Quick-Note Issue: #238, Roles, What's Unique

### Community 1044 - "Skill: SuperClaude Slash Commands"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: SuperClaude Slash Commands, Testing, Usage

### Community 1045 - "Skill: SuperClaude Workflow Engine"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: SuperClaude Workflow Engine, Testing, Usage

### Community 1046 - "test_harness_spec.py"
Cohesion: 0.20
Nodes (8): dict, set, _AllSignatures, _AnyText, tests/test_harness_spec.py — the Continual Harness spec. Covers the property…, A mapping that accepts any entry text for any signature., Treat every citation in the spec file as recorded. These tests cover block…, trusted_citations()

### Community 1047 - "ADR-006: Strangler Fig migration with backward-compat shims"
Cohesion: 0.29
Nodes (6): ADR-006: Strangler Fig migration with backward-compat shims, Consequences, Context, Decision, Examples, Migration path

### Community 1048 - "claude-mem Plugin — Persistent Memory for All Sessions"
Cohesion: 0.29
Nodes (6): claude-mem Plugin — Persistent Memory for All Sessions, Enabling it elsewhere, How it's wired, Notes, Scope and limits, Why the source is pinned (`ref` + `sha`)

### Community 1051 - "LLM Router — migration guide"
Cohesion: 0.18
Nodes (11): 1. Verify the router sees your providers, 2. Enable on one instance, 3. Watch for a few hours, 4. Roll out or roll back, Adding the config files, Gateway mode, LLM Router — migration guide, Migrating a caller to the router directly (+3 more)

### Community 1052 - "What's New"
Cohesion: 0.29
Nodes (7): 2026-06-16, 2026-06-25, 2026-06-26, 2026-07-04, 2026-07-05, 2026-07-09, What's New

### Community 1053 - "Cloudflare = the real working app"
Cohesion: 0.29
Nodes (6): Backend (Render), Cloudflare dashboard settings to verify, Cloudflare = the real working app, How it works, Notes, Verify after deploy

### Community 1057 - "launch-claude-code.sh"
Cohesion: 0.43
Nodes (6): ANTHROPIC_API_KEY, ANTHROPIC_MODEL, log_error(), log_header(), log_success(), launch-claude-code.sh script

### Community 1059 - "PRD — README Marketing Refresh"
Cohesion: 0.29
Nodes (6): Backlog / Nice-to-Have, Files Touched, Original Problem Statement, PRD — README Marketing Refresh, User Decisions, What Was Done — 2026-04-27

### Community 1060 - "ModelRouter"
Cohesion: 0.08
Nodes (22): Layer 3 — Model Router (`router/`), F. Router invariants (`router/`), F. Router invariants (`router/`), fallback_chain, fallback_chain(), Follow the explicit chain in ``routing.yaml``, then everything else. The chain…, Adding a model, Adding a task category (+14 more)

### Community 1061 - "_replace"
Cohesion: 0.40
Nodes (5): main(), Path, Regex-replace ``pattern`` with ``repl`` in ``path``; return the match count., Bump the version across all version-bearing files; fail fast if any are missed., _replace()

### Community 1062 - "check_changelog_parity.py"
Cohesion: 0.36
Nodes (7): difflib, _blocks(), main(), normalize_text(), scripts/check_changelog_parity.py CI guard for the changelog mirror. Closes the…, Return a list of human-readable corruption issues in *content*. Detects (1) git…, scan_corruption()

### Community 1064 - "quickstart.sh"
Cohesion: 0.52
Nodes (6): die(), ensure_env(), ok(), say(), quickstart.sh script, warn()

### Community 1065 - "BackgroundServices"
Cohesion: 0.38
Nodes (4): BackgroundServices, Handle returned by ``start_background_services`` — call ``stop()`` on shutdown., Cancel the boot refresh if it is still fetching at shutdown., Shut the in-process Hermes down so port 8100 is released. Uvicorn's own…

### Community 1067 - "test_daily_2026_06_14.py"
Cohesion: 0.38
Nodes (6): Regression tests for daily-2026-06-14 improvements. Anthropic retires the…, ci-failure-autofix.yml must call the Anthropic API with claude-sonnet-4-6, as…, No GitHub Actions workflow or CI script should reference a retired Claude 4…, _read(), test_ci_autofix_workflow_uses_sonnet_4_6(), test_no_retired_claude_4_model_ids_in_workflows_or_scripts()

### Community 1069 - "TestSupportMatrixDocsSync"
Cohesion: 0.29
Nodes (4): The feature matrix can produce a markdown table for docs., Every config flag referenced in the matrix should be documented., The matrix should cover the key areas from the spec., TestSupportMatrixDocsSync

### Community 1071 - "LogMonitor"
Cohesion: 0.06
Nodes (37): _dispatch_async(), _run(), _ErrorCaptureHandler, LogMonitor, _note_recurrence(), LogRecord, Register the error capture handler on the root logger., Best-effort: hand an operational failure to the incident tracker. Import is… (+29 more)

### Community 1072 - "TestReasonsAreActionable"
Cohesion: 0.29
Nodes (4): X is not set' leaves the operator to go find out what to do., Red is reserved for real faults., A backend-served server reads as healthy, not as a warning., TestReasonsAreActionable

### Community 1073 - "TestProvidersScreen"
Cohesion: 0.43
Nodes (3): The four invented 'connected' entries must not come back. Asserts on the…, No seeding on an empty response — that is what made the page lie., TestProvidersScreen

### Community 1075 - "TestMongoService"
Cohesion: 0.29
Nodes (3): The implementer must run against the same services as the PR gate., conftest.py documents why: a sqlite pin leaks a non-daemon aiosqlite thread and…, TestMongoService

### Community 1079 - "TestActiveStrategy"
Cohesion: 0.29
Nodes (3): parametrize, A typo must not silently pick some other distribution., TestActiveStrategy

### Community 1081 - "openclaw_mobile_ui"
Cohesion: 0.33
Nodes (5): openclaw_mobile_ui(), Mobile web UI for iOS control of the agency. Open this on your iPhone, tap…, get_mobile_html(), services/openclaw_mobile.py — Mobile web UI for iOS control of the agency.…, Return the mobile web UI HTML.

### Community 1082 - "Music Cues: happy-beats-business-moves-vol-1-by-ende-dot-app"
Cohesion: 0.33
Nodes (5): Music Cues: happy-beats-business-moves-vol-1-by-ende-dot-app, Reveal Candidates, Strong Cues In Window, Use Policy, Useful Beat Grid

### Community 1083 - "/fix-bug — Bug Fix Agent"
Cohesion: 0.33
Nodes (5): Escalation, /fix-bug — Bug Fix Agent, Process, Rules, Usage

### Community 1084 - "Command: /plan"
Cohesion: 0.33
Nodes (5): Command: /plan, References, Usage, What It Does, When to Use

### Community 1085 - "pre-commit"
Cohesion: 0.60
Nodes (5): pre-commit script, _error(), _head(), _info(), _warn()

### Community 1086 - "Skill: browserbase-fetch — Lightweight Web Fetch"
Cohesion: 0.33
Nodes (5): Checking the platform health, Python snippet, Setup, Skill: browserbase-fetch — Lightweight Web Fetch, When to use vs browser

### Community 1087 - "Twitter Insights — Issue #228"
Cohesion: 0.33
Nodes (5): Action Items, Key Observations, References, Summary, Twitter Insights — Issue #228

### Community 1088 - "Twitter Insights — Issue #231"
Cohesion: 0.33
Nodes (5): Action Items, Key Observations, References, Summary, Twitter Insights — Issue #231

### Community 1089 - "OpenAI Codex CLI — Local LLM Server Config"
Cohesion: 0.33
Nodes (5): Codex Config File (`~/.codex/config.yaml`), Notes, OpenAI Codex CLI — Local LLM Server Config, Recommended Models, Setup

### Community 1090 - "ADR-001: Adopt packages/ directory structure"
Cohesion: 0.33
Nodes (5): ADR-001: Adopt packages/ directory structure, Consequences, Context, Decision, Status

### Community 1091 - "ADR-002: Centralize configuration in packages/config/"
Cohesion: 0.33
Nodes (5): ADR-002: Centralize configuration in packages/config/, Consequences, Context, Decision, Status

### Community 1092 - "ADR-003: Provider abstraction with unified interface"
Cohesion: 0.33
Nodes (5): ADR-003: Provider abstraction with unified interface, Consequences, Context, Decision, Status

### Community 1093 - "ADR-004: Event bus for loosely coupled communication"
Cohesion: 0.33
Nodes (5): ADR-004: Event bus for loosely coupled communication, Consequences, Context, Decision, Status

### Community 1094 - "ADR-005: Merge Hermes into the main backend service"
Cohesion: 0.33
Nodes (5): ADR-005: Merge Hermes into the main backend service, Consequences, Context, Decision, Status

### Community 1100 - "The full agent capability roster"
Cohesion: 0.33
Nodes (6): Agile, portfolio & product, Business & domain specialists (auto-provisioned from the URL scan), Content & knowledge, Engineering, Operations & DevOps, The full agent capability roster

### Community 1101 - "Pre-Mortem Analysis: Agency Core autonomy story (Cloudflare deployment)"
Cohesion: 0.33
Nodes (5): Elephants, named, Pre-Mortem Analysis: Agency Core autonomy story (Cloudflare deployment), Risk Registry, Summary, What was already fixed during this pre-mortem

### Community 1111 - "gen_v4_screenshots.py"
Cohesion: 0.60
Nodes (5): build_screens(), page(), Generate v4 UI screenshots for the README using HTML mockups + system…, shot(), sidebar()

### Community 1114 - "setup-claude-code.sh script"
Cohesion: 0.60
Nodes (5): log_error(), log_info(), log_success(), print_header(), setup-claude-code.sh script

### Community 1117 - "test_activity_feed.py"
Cohesion: 0.33
Nodes (3): Alerts must be non-zero: log_activity always records to an in-memory feed so…, # NOTE: do not set ADMIN_EMAIL here. This module never used it, but the, test_activity_buffer_survives_db_outage()

### Community 1121 - "TestWorkflowIntegration"
Cohesion: 0.33
Nodes (4): Tests for workflow orchestrator integration., Verify WorkflowOrchestrator correctly bypasses for internal callers., Verify InternalAgentAdapter provides agent execution for workflows., TestWorkflowIntegration

### Community 1124 - "DockerAgentAdapter"
Cohesion: 0.17
Nodes (8): DockerAgentAdapter, Any, Adapter that runs agent tasks inside isolated Docker containers., Check whether Docker is available and report the adapter's runtime health.…, asyncio, test_docker_binary_missing(), asyncio, test_docker_health_unavailable()

### Community 1128 - "TestTheAgentRunsCurrentCode"
Cohesion: 0.33
Nodes (3): The implementer ran a four-day-old copy of itself. "Create or reuse feature…, If master cannot be merged, start clean rather than proceed stale., TestTheAgentRunsCurrentCode

### Community 1132 - ".update_status"
Cohesion: 0.33
Nodes (4): _now(), WorkspaceStatusLiteral, Transition to a new status and update cleanup eligibility., Touch the last_heartbeat timestamp.

### Community 1137 - "feature-implementer.md"
Cohesion: 0.40
Nodes (4): Before you edit, Prove it, Report back, While you edit

### Community 1139 - "/devops-check — DevOps Agent"
Cohesion: 0.40
Nodes (4): Deployment Checklist, /devops-check — DevOps Agent, Steps, When to use

### Community 1140 - "/docs-update — Documentation Agent"
Cohesion: 0.40
Nodes (4): /docs-update — Documentation Agent, Documentation Standards, Steps, When to use

### Community 1141 - "/qa-check — QA Agent"
Cohesion: 0.40
Nodes (4): /qa-check — QA Agent, Steps, What NOT to do, When to use

### Community 1142 - "Command: /review"
Cohesion: 0.40
Nodes (4): Command: /review, References, Usage, What It Does

### Community 1143 - "/security-audit — Security Agent"
Cohesion: 0.40
Nodes (4): Escalation, /security-audit — Security Agent, Steps, When to use

### Community 1144 - "pre-push"
Cohesion: 0.70
Nodes (4): pre-push script, _error(), _head(), _info()

### Community 1145 - "Skill: browserbase-search — Structured Web Search"
Cohesion: 0.40
Nodes (4): Best practice: search → fetch → browse, Python snippet, Setup, Skill: browserbase-search — Structured Web Search

### Community 1146 - "Issue #230 — DUPLICATE"
Cohesion: 0.40
Nodes (4): Actions Taken, Issue #230 — DUPLICATE, References, Resolution

### Community 1149 - "Docker (local or any container host)"
Cohesion: 0.40
Nodes (4): Build, Docker (local or any container host), Provider configuration (recommended for cloud), Run (minimal)

### Community 1154 - "Runtime troubleshooting"
Cohesion: 0.33
Nodes (4): Agent mode timeout, Missing binary / task harness, Runtime troubleshooting, Workspace validation failures

### Community 1155 - "Admin Dashboard Issues"
Cohesion: 0.40
Nodes (5): Admin Dashboard Issues, Dashboard shows "KEYS_FILE not configured", New key flash banner not appearing after key creation, "Stop stack" disconnects me from the dashboard, Windows auth login fails

### Community 1158 - "knowledgeGraphTab.test.js"
Cohesion: 0.11
Nodes (19): { describe, test, expect }, fs, path, src, apiSource, { describe, test, expect }, fs, path (+11 more)

### Community 1162 - ".chat"
Cohesion: 0.40
Nodes (3): Any, Send a chat completion request., Stream a chat completion response.

### Community 1163 - "governance/__init__.py"
Cohesion: 0.40
Nodes (3): __getattr__(), Any, packages/governance — agent identity, policy, approvals, audit, sandboxes. The…

### Community 1164 - "inspect-agent-runtime.sh"
Cohesion: 0.60
Nodes (3): fail(), inspect-agent-runtime.sh script, usage()

### Community 1165 - "Prompt Library Changelog"
Cohesion: 0.40
Nodes (4): Added, Format, Prompt Library Changelog, [Unreleased]

### Community 1166 - "Proof"
Cohesion: 0.40
Nodes (5): Honesty notes (read before quoting the numbers), Proof, Reproduce any audit yourself, The self-audit (yes, we publish our own imperfect score), What's coming next in this directory

### Community 1167 - "check_rate_limit"
Cohesion: 0.60
Nodes (4): check_rate_limit(), asyncio, test_rate_limiter_concurrency(), call_limit()

### Community 1169 - "build_llama_cpp.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), W(), Warn()

### Community 1170 - "download_glm52_weights.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), Warn(), W()

### Community 1171 - "download_glm52_weights.sh script"
Cohesion: 0.70
Nodes (4): download_glm52_weights.sh script, fail(), ok(), warn()

### Community 1173 - "setup_colibri.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), Warn(), W()

### Community 1174 - "setup_colibri.sh script"
Cohesion: 0.70
Nodes (4): setup_colibri.sh script, fail(), ok(), warn()

### Community 1175 - "status_colibri_server.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), W(), Warn()

### Community 1179 - "TestMobileNavigation"
Cohesion: 0.40
Nodes (3): Mobile-specific: hamburger menu, responsive layout., Verify key pages load in mobile viewport., TestMobileNavigation

### Community 1183 - "FeatureUnavailableError"
Cohesion: 0.12
Nodes (7): 18. Feature Maturity & Support Matrix, FeatureUnavailableError, Exception, Load canonical features and apply per-feature then bulk env overrides., Apply a config override string like 'stable', 'beta', 'disabled', 'enabled',…, Raised when code attempts to use a feature that is disabled or unavailable., TestSingleton

### Community 1189 - "TestGhIsNotReAuthenticated"
Cohesion: 0.40
Nodes (3): `gh auth login --with-token` fails when GH_TOKEN is already set. gh refuses:…, Removing the login must not remove the credential., TestGhIsNotReAuthenticated

### Community 1190 - "RuntimeAdapter"
Cohesion: 0.03
Nodes (40): Fail preflight when the provider extension is configured but missing. Without…, Any, Structured, actionable preflight validation issue., Preflight result returned before a runtime task starts., Abstract base class every runtime adapter must implement. Subclasses must set…, Return a health snapshot. Must not raise; return available=False instead., Execute a task and return the result. Must handle its own timeout…, Stream output tokens/lines. Default implementation runs execute() and yields… (+32 more)

### Community 1193 - "codebase-explorer.md"
Cohesion: 0.50
Nodes (3): Hard constraints, Method, Output

### Community 1194 - "docs-auditor.md"
Cohesion: 0.50
Nodes (3): Hard constraints, Output, What to check

### Community 1195 - "risk-reviewer.md"
Cohesion: 0.50
Nodes (3): Output, Rules of evidence, What you weigh

### Community 1196 - "verification-reviewer.md"
Cohesion: 0.50
Nodes (3): Output, Rules of evidence, What you evaluate

### Community 1197 - "aider_config.sh"
Cohesion: 0.50
Nodes (3): OPENAI_API_BASE, OPENAI_API_KEY, aider_config.sh script

### Community 1204 - "Credential Rotation Runbook"
Cohesion: 0.50
Nodes (3): Credential Rotation Runbook, Guardrails already in place, What to rotate (owner action, ~10 minutes)

### Community 1205 - "Runbook: `make doctor`"
Cohesion: 0.50
Nodes (3): Roadmap, Runbook: `make doctor`, What it checks and why

### Community 1210 - "Runtime & Onboarding Issues"
Cohesion: 0.33
Nodes (5): Onboarding endpoints crash with 500, Runtime endpoints return 500 errors (decisions, health, policy), Runtime & Onboarding Issues, Website scan returns "No systems detected" for JS-rendered sites, Return health status for all registered runtimes.

### Community 1211 - "render"
Cohesion: 0.50
Nodes (3): RENDER_API_KEY, docker, render

### Community 1213 - ".__init__"
Cohesion: 0.50
Nodes (3): Any, Resolve the default executor model via the catalog (UNIT 7). Was hardcoded to…, _resolve_default_executor_model()

### Community 1214 - "stop_colibri_server.ps1"
Cohesion: 0.83
Nodes (3): Fail(), Ok(), W()

### Community 1235 - "github"
Cohesion: 0.50
Nodes (3): github, enabled, silent

### Community 1252 - "test-anthropic.js"
Cohesion: 0.50
Nodes (3): ref_anthropic_ai_sdk, { Anthropic }, client

## Knowledge Gaps
- **3066 isolated node(s):** `duplicate.sh script`, `heartbeat.sh script`, `redact_secrets.sh script`, `docker`, `RENDER_API_KEY` (+3061 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 13958 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **155 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AgentRunner` connect `AgentRunner` to `ContextPruner`, `AgentPlan`, `UserMemoryStore`, `backend/server.py`, `proxy.py`, `TaskSpec`, `MultiAgentSwarm`, `GitHubTools`, `workflow_orchestrator.py`, `PolicyEngine`, `Universality: case-coverage matrix`, `test_contracts_agency.py`, `unsafe_target_reason`, `test_ceo_micromanager.py`, `AdaptiveHalter`, `test_agent_chat_integration.py`, `test_governance_api.py`, `Agency Core — Progress & Resume Log`, `ReactScratchpad`, `._dispatch_tool`, `failover_chat_completion`, `TestAgentLoopMCPIntegration`, `PortfolioManager`, `Fixed`, `ContextManager`, `Added`, `TaskDispatcher`, `AgentJobRequest`, `Changed`, `Agent: Implementer (Executor)`, `WorkflowOrchestrator`, `test_backend_server_features.py`, `Killer TODO Roadmap — local-llm-server`, `FreeBuffAgent`, `StuckDetector`, `Fixed`, `_resolve_user_github_token`, `WorkspaceTools`, `Added`, `test_empirical_verify.py`, `Added`, `Section-by-Section Acceptance Criteria`, `LocalWorkspace`, `HarnessEnrichment`, `Issue #504: EPIC: Autonomy hardening — live-verified defects 2026-06-10`, `test_agent_tool_governance.py`, `test_repo_connection.py`, `failover_client.py`, `AdminScreen.jsx`, `root`, `.apply_diff`, `_resolve_push_token`, `TokenBudget`, `test_verification_strategies.py`, `test_agent_free_brain.py`, `pytest`, `E2BSandboxSession`, `AgentSessionStore`, `direct_chat.py`, `E2BAdapter`, `CEODispatcher`, `Fixed`, `InternalAgentAdapter`, `Fixed`, `os`, `loop.py`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Why does `ma()` connect `failover_client.py` to `la`, `HarnessEnrichment`, `de`, `gsap.min.js`?**
  _High betweenness centrality (0.023) - this node is a cross-community bridge._
- **Why does `StopSlopChecker` connect `StopSlopChecker` to `TestStopSlopChecker`, `AITellIssue`, `.test_cleans_removes_double_spaces`, `.test_detects_multiple_throat_clearing`, `.test_detects_wh_starters`, `.test_cleans_emphasis_crutches`, `quality_checker.py`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **What connects `duplicate.sh script`, `heartbeat.sh script`, `redact_secrets.sh script` to the rest of the system?**
  _3066 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `llm/router.py` be split into smaller, more focused modules?**
  _Cohesion score 0.01645623492693999 - nodes in this community are weakly interconnected._
- **Should `backend/server.py` be split into smaller, more focused modules?**
  _Cohesion score 0.01408541846419327 - nodes in this community are weakly interconnected._
- **Should `_fixture` be split into smaller, more focused modules?**
  _Cohesion score 0.01761252446183953 - nodes in this community are weakly interconnected._