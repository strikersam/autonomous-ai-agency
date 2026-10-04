# Graph Report - autonomous-ai-agency  (2026-10-04)

## Corpus Check
- 1667 files · ~2,391,022 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 55 file(s) not represented in the graph (top: (none) 17, .bat 5, .css 5)

## Summary
- 35472 nodes · 73031 edges · 1370 communities (1002 shown, 368 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 7046 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4ea8b8a4`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- workflow_orchestrator.py
- typing
- TaskSpec
- LLMRequest
- test_provider_router.py
- clear_stats
- test_llm_router_queue_cache.py
- TestRuntimeControl
- proxy.py
- brain_config.py
- SQLiteStore
- company_api.py
- Usage
- api.js
- Specialist
- is_destructive_overwrite
- failover_chat_completion
- strategies.py
- sam_orchestrator.py
- test_freebuff_bot.py
- chat_handlers.py
- Changed
- types.py
- test_ceo_dispatcher.py
- Agency
- test_brain_failover.py
- SelfHealingAgent
- AnthropicProvider
- resolve_component_model
- TaskStatus
- backend/server.py
- Added
- test_governance_sandbox.py
- AppShell.jsx
- AgentScheduler
- build_governance_router
- test_e2b_sandbox.py
- agency_fix.py
- MultiAgentSwarm
- RuntimeHealthService
- test_governance_api.py
- test_platform_controls.py
- activation_api.py
- ref_react
- PolicyEngine
- Fixed
- ExecutionRequest
- test_schedule_backlog_drain.py
- MongoDBStore
- control_overrides.py
- _mock_provider_records
- failover_client.py
- test_mcp_registry.py
- get_registry
- Added
- llm/router.py
- @testing-library/react
- Added
- TestCatalogClaude5Models
- test_repo_connection.py
- make_client
- test_memory_guard.py
- test_scanner_headless.py
- HttpxFetcher
- gateway/config.py
- AgentRunner
- MCPClient
- CompanyGraphService
- WebsiteScanner
- SessionBudget
- test_governance_enforcement.py
- test_llm_router_e2e.py
- test_model_catalog.py
- DashboardScreen.jsx
- agent/workspace.py
- seo_portfolio_bridge.py
- _ts_to_float
- test_kill_switch_and_agent_budget.py
- test_cost_aware_routing_eval.py
- setup/api.py
- RenderOpsMonitor
- test_model_router.py
- RepowiseIntelligence
- control.py
- scheduler_tick_last
- detector.py
- test_web_reach.py
- facade.py
- Settings
- TaskWorkflowService
- test_startup_warmup.py
- api.ts
- Company
- frontend/package.json
- test_ceo_supervision.py
- unsafe_target_reason
- test_e2e_agent_chat.py
- pr_approval_gate.py
- telegram_bot.py
- resolve_e2b_config
- Current Sprint Tasks
- test_runtime_governance.py
- TestClient
- _StubProvider
- test_ceo_micromanager.py
- test_ceo_self_learning.py
- test_knowledge_sync.py
- FeatureMatrix
- CompanyAgencyService
- ToolRegistry
- test_free_model_speed.py
- test_trend_watcher.py
- tasks/api.py
- ProviderRouter
- SyncService
- test_sqlite_store.py
- WorkspaceManager
- services/background.py
- AgentSwarm
- PreflightReport
- ai_runner.py
- PersistentMemoryStore
- services/seo_audit.py
- _cfg
- test_direct_chat_async.py
- KeyStore
- test_autonomous_agency_e2e.py
- AgentJobRequest
- TestRenderMCPClient
- AdminAuthManager
- AgentJobManager
- _step
- _llm_catalog
- _FakeCommandResult
- LogWatcher
- test_context_rulebook.py
- system_instruction
- .tick
- test_all_features.py
- ArtifactStore
- SecurityScanner
- test_loop_registry.py
- Agent
- test_integration_c4_c5_c6_d3.py
- _llm_catalog
- diagnostics.py
- AgileSprint
- Page
- test_bedrock_provider.py
- BrowserSession
- ProceduralMemoryStore
- TokenBudget
- Command
- Troubleshooting
- BudgetTracker
- PrimeAgentAdapter
- FreeBuffAgent
- _cfg
- E2BSandboxSession
- AutonomyTracker
- test_trend_scoping.py
- AgentSessionStore
- SamAgent
- WorkspaceTools
- user_research_skill.py
- test_brain_patch_service_token.py
- portfolio_api.py
- test_llm_router_disabled.py
- gsap.min.js
- CompanyScreen.jsx
- test_verification_strategies.py
- test_sam_livekit.py
- test_spec_store.py
- 4. Threats
- local_controller.py
- test_telegram_observe.py
- SpecEntry
- QuickNote
- PatternConsolidation
- test_daily_digest.py
- WorkflowEngine
- UserRole
- FeatureMaturity
- test_response_cache.py
- test_mcp_governance.py
- BrainFailoverExhausted
- test_video_transcript.py
- TestSelfHealingInfrastructureClassification
- sam_tools.py
- test_anthropic_router.py
- TaskDetailPanel
- SetupChecker
- ManagedAgentDreams
- PromptCacheManager
- analyze_page
- test_e2b_data_flow.py
- WorkflowRun
- AdaptiveHalter
- CEOLedger
- portfolio_intelligence.py
- KnowledgeGraph
- PortfolioManager
- OllamaCircuitBreaker
- v4_api.py
- test_hermes_in_process.py
- SyntheticDataPipeline
- TestChatHandlersSessionId
- test_features_api.py
- test_telegram_webhook.py
- register_webui
- WorkspaceManifest
- test_operational_incidents.py
- test_audit.py
- llm_providers.py
- NIMConnectionPool
- Platform Guide — the full tour
- Killer TODO Roadmap — local-llm-server
- resolve_active_brain
- metrics.py
- TestSchedulerStore
- test_classify_dependabot_update.py
- test_brain_availability_doctor.py
- ContextWindowManager
- _cfg
- _run
- Implementation Plan — DB-persisted, UI-switchable Brain (no redeploy)
- test_sam_orchestrator.py
- Persistent Memory System
- test_task_run_lease.py
- get_scheduler
- _llm_catalog
- ScheduleStore
- TrendWatcher
- looks_like_secret_file
- Agent: Judge (Release / QA Gate)
- clear_cooldowns
- test_agent_tool_governance.py
- TestRecordUsageAndStats
- Workflow
- validate
- discover_models
- test_schedule_growth_invariants.py
- checkpoint_agent_state
- TestPolicyAuthoringUiStableClaim
- AgileManager
- Added
- AdminScreen.jsx
- test_daily_2026_06_04.py
- test_background_services.py
- .session_id
- GuardrailEngine
- Path
- GitHubTools
- test_agents.py
- app_settings.py
- test_provider_render_env.py
- KeyPool
- test_control_plane_api.py
- TestCatalogFable51
- test_daily_automation_2026_09_29.py
- tasks/models.py
- control_registry.py
- ImprovementLoop
- test_persistent_memory.py
- TestAddConversationCacheBreakpoints
- test_ceo_router.py
- test_agent_api.py
- Any
- LocalBrainStore
- ._call
- TestAuthAndTaskOwnership
- _normalize_tool_choice
- SeoFixRequest
- REWRITE_PLAN.md — Phased Migration Strategy
- analyze
- _cfg
- test_autonomy_triage.py
- WorkflowTransition
- set_task_store
- test_sam_voice.py
- test_ephemeral_reaper.py
- emit_chat_observation
- monitor_lib.py
- seo_api.py
- TestGroqLlama4ScoutModelDeclaration
- router_factory
- agent_runtime.py
- seo_report_pdf.py
- test_chat_mode_regressions.py
- _Collection
- WorkflowRun
- Task
- test_live_server.py
- test_all_providers_discovery.py
- test_purge_backlog.py
- CheckpointStore
- OutputFilter
- PlaybookLibrary
- TestHarnessAdapter
- ⚙️ Operations Manager Agent
- SeoFixer
- .failed
- NEXT_ACTION — updated 2026-10-04
- skill_bindings.py
- test_connector_registry.py
- ApprovalStore
- DistributedRateLimiter
- test_internal_agent_delivery.py
- test_provider_failover_integration.py
- _routing_candidates
- test_provider_enable_disable.py
- test_render_mcp.py
- _resolve_user_github_token
- LLMRouter
- test_gateway_upstream_retry.py
- test_kimi_bridge_server.py
- HarnessEnrichment
- TaskPriority
- TestSafeguardCostEntries
- test_local_controller.py
- ContextManager
- test_microagents.py
- test_backend_server_features.py
- README.md
- _resolve_push_token
- Langfuse Observability Guide
- test_agent_free_brain.py
- RateLimitTracker
- test_portfolio_drain.py
- test_workspace_isolation.py
- TestBothCataloguesAgreeOnWhatExists
- ContextCompressor
- asyncio
- agents/api.py
- get_store
- RewardScorer
- safe_agency.py
- SparkProvider
- 467 Brutal Audit — File-by-File Status
- ResourceWatchdog
- Platform Engineer Agent
- Marketing SEO Specialist
- High-Agency Frontend Skill
- test_brain_priority_scanner.py
- Quick-Note GitHub Issues Processing - Session Summary
- ProviderConsole.jsx
- v3_models.py
- switch_brain.py
- Fixed
- test_colibri_provider.py
- test_skill_registry_boot_refresh.py
- test_autonomy_gate.py
- Configuration Reference
- LessonStore
- or
- Application Security Engineer
- build_render_router
- probe_catalogues.py
- WorkflowPhase
- output_filter.py
- triage_orphaned_context_prs.py
- TaskDispatcher
- CEOSupervisor
- TestWorkflowRun
- test_force_cleanup_conditional_delete.py
- generate_context.py
- test_rag_context.py
- SkillLibrary
- StuckDetector
- UserMemoryStore
- Data Engineer Agent
- test_rate_limiter.py
- _ensure_tasks_source_id_unique_index
- FeatureEntry
- Conflicts and Stale Facts
- _FakeGitHub
- SteeringInjector
- test_claude_setup_audit.py
- AgentPlan
- Initiative
- _captured_request_headers
- ReactScratchpad
- test_phase6_workflow.py
- test_company_api.py
- AGENTS.md — Codebase Map & Operations Reference
- UX Researcher Agent Personality
- DevOps Automator Agent Personality
- Mobile App Builder Agent Personality
- Developer Agent Personality
- Analytics Reporter Agent Personality
- Support Responder Agent Personality
- Python Dependencies (`requirements.txt`)
- _fake_http_sequence
- Part A — CodeRabbit review fixes for this PR (do first, small)
- KV Cache Internals
- ModelRouter
- WorkspaceManager
- webui/frontend/package.json
- keepalive.py
- test_phase5_doctor.py
- sam_actions.py
- test_pr_approval_gate.py
- NotificationDispatcher
- _llm_catalog
- RepoConnection
- _Recorder
- test_executive_advisory_api.py
- ExecutiveAdvisory
- redact_connection_url
- ProjectScaffolder
- SprintMetrics
- UI Designer Agent Personality
- Product Sprint Prioritizer Agent
- Technical Debt Register — local-llm-server
- test_gateway_sanitizer.py
- workflow/models.py
- Claude Code + Qwen Local Setup
- Docker Agent Runtimes Setup
- heal_signature
- CEO Micro-Management
- redact_secrets
- CostAttributor
- _execute_skill_impl
- test_anthropic_refusal_fallback.py
- TestGeminiOmniCatalogEntry
- _Recorder
- TestDiagCommand
- ContextPruner
- TerminalPanel
- VoiceCommandInterface
- Frontend Developer Agent Personality
- tts.py
- get_savings
- fmtErr
- _is_dns_failure
- test_regression.py
- test_daily_automation_2026_08_03.py
- brain_failover.py
- ensure_self_company
- test_workflow_shell_vars_are_declared.py
- build_executive_advisory_router
- Part A — Health Report
- is_model_available
- test_memory.py
- Universality: case-coverage matrix
- test_keepalive.py
- Backend Architect Agent Personality
- Project Shepherd Agent Personality
- .on_task_complete
- Session Handoff — 2026-06-15
- webui/router.py
- Workspace
- SQLiteStore
- unittest_mock
- test_service_token.py
- CodeGraph
- test_commit_tracker.py
- ErrorInterceptorMiddleware
- FilterResult
- AI Engineer Agent
- Research Synthesist Agent Personality
- test_dashboard_cache.py
- _handle_command
- Local AI Stack with Docker
- 5. The five autonomous loops
- LLM Router — troubleshooting
- TASK 4 — End-to-end approval-gate test
- ENGINEERING_STANDARDS.md — Patterns & Reference
- ai/__init__.py
- CollectionLike
- Native operations
- PriorityTaskQueue
- TemporalContextGraph
- APIClient
- TestClaudeOpus55CostTracker
- test_openclaw_endpoints.py
- register_admin_gui
- github_tools.py
- secrets_store.py
- note_phase_start
- _llm_catalog
- Findings
- openclaw_str_e_fix.py
- Deploy: FreeBuff Telegram bot (24×7)
- test_fabric_patterns.py
- Workspace Isolation Architecture
- Telegram Bot Setup
- SetupWizardPage.js
- knowledgeGraphTab.test.js
- implement_agent.py
- test_north_mini_code.py
- test_key_pool.py
- TrafficDirector
- AgentMessageBus
- isolated_telegram_config
- _get
- TestCapabilitiesAreNotClaimedWithoutEvidence
- _plan
- test_mostly_failed_steps.py
- test_webui_provider_priority.py
- _client
- AdaptivePermissions
- RegistrySkill
- SkillRegistry
- CoworkSession
- FinancialMetrics
- analyze_qualitative
- compare_runtimes.py
- test_agent_chat_integration.py
- test_v4_api.py
- provider_max_rpm
- AuditLog
- _Cursor
- context_plan_gate.py
- WindowsServiceManager
- ._parse_body
- ProviderCircuit
- OrchestratorCheckpointStore
- TestCacheReadBilling
- _SlowLoginPage
- test_crispy_burn_in.py
- test_v3_auth.py
- plan_research
- LocalWorkspace
- 🧭 Product Manager Agent
- test_admin_local_brain_router.py
- Tween
- V3 API Migration Plan — LLM Relay Platform
- test_telegram_diag_endpoint.py
- test_openclaw_str_e_fix.py
- _make_mock_response
- test_unit8_model_catalog.py
- operational_incidents.py
- The fifteen strategies
- _rrf
- _extract_tech_relevance
- register_user_research_tools
- Skill: modularity-review
- Design Audit
- Findings
- la
- Skill: modularity-review
- crispy_client.py
- 4. Troubleshooting
- allow_paid
- The rules
- PortfolioScreen.jsx
- infra_cost.py
- TestRouterIntegration
- Autonomous AI Agency
- build_workflow.py
- LLM Router — migration guide
- test_gateway_hygiene.py
- TestBrainFailoverModelUpdates
- FakeResp
- TestSourceGate
- test_research_coordinator.py
- test_tasks_cache_ttl_env.py
- mcp_registry.py
- agile_api.py
- PerformanceAnalytics
- Skill: fabric-patterns
- Analysis & Synthesis Instructions
- Performance Analysis — local-llm-server
- Production Readiness Assessment — local-llm-server
- TestNormalizeResponseFormat
- Skill: fabric-patterns
- Admin Dashboard Guide
- Agent Orchestration Design
- verify_token
- ChatScreen.jsx
- ControlsScreen.jsx
- scripts/doctor.py
- Screens
- run_proxy.sh
- ServiceDaemon
- test_autonomy_status.py
- test_pr923_fixes.py
- sync_readme_gallery.py
- get_db
- sam_livekit_worker.py
- validate_session_id
- _register_code_graph_tools
- refine
- Test Automation Engineer
- Comprehensive Skill Index (By Category)
- Agent Skill: Principal UI/UX Architect & Motion Choreographer (Awwwards-Tier)
- Architecture Overview — local-llm-server
- Feature Guide
- _test_e2e_telegram_approval
- get_skill_bindings
- Delegation Plan (agent-ready work packages)
- test_task_source_id_race.py
- ._cannot_list
- _reject
- TestRefreshTokenSQLiteFallback
- TestAnthropicCacheReadFractions
- TestModelRegistryUpdates
- TestOrchestratorQueue
- _P
- TestStopSlopChecker
- _redact_for_notification
- TestUpdateTask
- ChatHistoryStore
- cowork_session.py
- HarnessAdapter
- Page
- Salesforce Architect
- SKILL: Industrial Brutalism & Tactical Telemetry UI
- Skill: data-quality-audit
- What "Slop" Looks Like
- WorkflowScreen.jsx
- Traffic Distribution Across Providers
- Separate hosted dashboard backend (`backend/server.py`)
- Section-by-Section Acceptance Criteria
- Dynamic Model Routing
- McpCard
- test_p0_roadmap_a4_a5_b2.py
- agent_readiness_audit.py
- sync_ngrok.py
- test_ci.sh
- FakeRunner
- test_shared_state.py
- LocalLLMSetup
- Fixed
- _migration_block
- TestCacheReadCostCalculations
- test_frontend_deployment_guards.py
- traffic_director.py
- test_skill_registry.py
- test_task_service_failed_comment.py
- MemoryKernel
- handle_workflow_ide_chat
- hermes_prompt.py
- MemoryMiddleware
- HybridSystem
- AITellIssue
- Skill: repowise-intelligence
- ARCHITECTURE.md — Target Architecture
- Component Map
- Security Analysis — local-llm-server
- test_social_login_oauth.py
- github_source.py
- Attention Mechanisms Internals
- Skill: repowise-intelligence
- The 10-Step Workflow
- Contributing to local-llm-server
- CompanyGraphStore
- parse_event_stream
- Agent Runtime Setup
- Runbook — Apply the Fast Free NVIDIA Brain to Render (TASK 2)
- WorkflowBuildRequest
- model_router.py
- fabric_cli.py
- TelegramBotManager
- prompt_audit.py
- .publish
- e2e/test_browser.py
- DecisionsStoreTests
- test_dockerfile_ships_root_modules.py
- TestMCPServer
- test_migrate_local_brain_env.py
- TestChatHistoryStore
- TestRoutes
- TestBrainFailoverBackoff
- sys
- _hash_component
- check_kwargs
- test_ai_insights.py
- CostLine
- Skill: Agentic Portfolio Management
- Skill: agent-harness
- Skill: checkpoint-strategy
- Process
- Skill: local-ai-query
- Skill: parallel-agents
- Skill: parallel-worktrees
- Design System: Taste Standard
- Process
- test_new_features_e2e.py
- reset_cache
- TestMCPToolsListCache
- OpenClaw — iOS Control of the Agency (Single-Service Free-Tier Deploy)
- trend_analysis.py
- TestAuthAndTaskCreation
- record_event
- check_model_catalog_consistency.py
- OperationalIncidentTracker
- OrchestratorQueue
- StreamingDeltaReconstructor
- TestRunCoroSync
- build_tool_prompt
- test_agile_api.py
- v3_auth.py
- resolve_provider_for
- test_dockerfile_ships_config_dir.py
- TestDiscovery
- QuickNoteQueue
- _process_task_callback
- compilerOptions
- test_executive_advisory.py
- Trajectory
- classify_direct_chat_intent
- TestResolveBrainProvider
- BudgetOptimizer
- Project Manager Agent Personality
- StopSlopChecker
- rag_context.py
- ResearchTask
- Process
- Skill: lr-schedule-advisor
- Instructions
- Process
- Checks Performed
- Skill: training-stability-monitor
- Skill: branch-cleanup
- Skill: perplexity — Web Research via Perplexity API
- Instructions
- Instructions
- Quick-Note Issues Processing Summary
- test_task_clarification.py
- .content
- AgentsScreen.jsx
- handle_anthropic_messages
- TestNormalizeAnthropicOutputFormat
- DeterministicEngine
- test_langfuse_agency_wide.py
- Context: Agentic Agile + Portfolio Management
- chat_completions
- NVIDIA NIM — Free Tier Setup
- test_setup_api.py
- HarnessRegistry
- test_agency_workflows_carry_the_failover_chain.py
- parametrize
- TestAnthropicToolListCaching
- TestGpt6FamilyCostEntries
- _StubManager
- _Response
- Retrospective
- yaml
- TestDisabledReasonRendering
- _start_ceo_agency
- TestTheSharedListFitsBothCallers
- InferenceCache
- AgentJobSnapshot
- AIToolMetrics
- CollaborationContext
- CEODispatcher
- TestPromptIdForwarding
- Software Architect Agent
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
- local_brain_router.py
- Instructions
- Skill: graphify — Knowledge Graph Token Optimization
- Skill: platform-setup — Autonomous Agency Bootstrap
- Agency Core — Progress & Resume Log
- Device compatibility and model picks
- V5App.jsx
- rules
- ApplyReviewAgent
- TestEstimateTokensForMessages
- _is_bedrock_model_id
- KnowledgeScreen.jsx
- _get_provider_policy
- TestSafeguard20bModelYaml
- load_tasks
- _self_heal_ready
- fetch_url.py
- TestDisabledProvidersAreNotFalselyReportedUnreachable
- _FakeAsyncClient
- test_compose_and_coordinate_api.py
- TestModelCostTableUpdates
- test_deploy_trigger_covers_image.py
- _TFIDFIndex
- TestKillSwitchDurability
- pytest
- test_quick_note_engine.py
- validate_job_id
- test_critical_flows.py
- Instructions
- Instructions
- Process
- Instructions
- Skill: system-prompt-audit
- Skill: task-alive-updates
- Process
- Instructions
- TestBrainConfigUpdates
- Skill: agent-browser — Real Chrome Browser Automation
- Instructions
- Instructions
- Instructions
- Implementation Prompt: Rich TaskBoard + Agile Sprint Integration
- Quantization Internals
- Autonomy Uplift — Living Roadmap & Detailed Implementation Specs
- process_note
- harness_spec.py
- install-agents.sh
- Instructions
- LLM Router — configuration guide
- Kimi Web-Bridge Service
- BrainCard.jsx
- SchedulesScreen.jsx
- TestLegacyRouterCacheTTL
- test_app_settings.py
- test_brain_default_consistency.py
- Runbook: Auto-Resume After Cooldown / Interruption
- .test_set_github_token_sqlite_string_id_does_not_500
- LLM Router — provider guide
- is_anthropic_base_url
- prompt_policy.py
- _encrypt
- CacheStats
- probe_model_liveness
- _is_ephemeral_user
- _first_paragraph
- AI Engineering Insights Skill
- SyncAgent
- SRE (Site Reliability Engineer) Agent
- ResearchAgent
- Instructions
- Skill: pro-workflow
- Instructions
- Instructions
- Skill: resource-panel
- Skill: sandboxed-exec
- admin_update_task_router.py
- _RedisBackend
- Skill: dev-browser — Browser Automation via Sandboxed JS
- ECC Harness Patterns Skill
- Instructions
- Instructions
- Stop-Slop Quality Skill
- ReasoningResult
- 2. Critical Bugs & Exact Detection Signatures
- Issue #467 — Section 1: Pulled State + PR Inventory
- Deploy to Google Cloud Run
- Key Components
- Sampling Strategies Internals
- test_scheduler_hydration_bounded.py
- CI Troubleshooting Runbook
- extract_refusal
- Worker Service — Operations Runbook
- _build_execution_request
- ServiceManager
- SkillsScreen.jsx
- test_bedrock_live.py
- test_tasks_reconciler_todo_requeue.py
- TestAnthropicPayloadStructuredOutput
- _push_down_where
- GitHubPolicyProbe
- _override_user
- test_harness_spec.py
- Security Policy
- .get_git_health
- TestClaudeOpusModelCoverage
- _request
- knowledge_graph.py
- TestChatFallbackAndApproval
- _build_payload_or_500
- DetectedSystem
- _list_configured_provider_records
- test_hermes_server.py
- TestDecisionsBotLinks
- mask_secret
- _extractive_compress
- TestZeroAttemptDiagnostics
- What to clean up
- TestNoNvidiaFallbackIsRetired
- _step
- flesch_reading_ease
- test_state_file_merge_drivers.py
- test_empirical_verify.py
- SavingsTracker
- gather_render_evidence
- _start_in_web_bot_tasks
- TestParsing
- financial_analyst.py
- enrich_quick_note_issues.py
- Instructions
- Protocol: Premium Utilitarian Minimalism UI Architect
- The 5-Step Wrap-Up Ritual
- Brag Plan: Autonomous AI Agency (feature tour, v2)
- de
- Hyperframes Composition Brief: Autonomous AI Agency (feature tour, v2)
- Skill: Agentic Agile
- Skill: browserbase-ui-test — Adversarial UI Testing
- Workflow
- Skill: financial-analyst (Agentic CFO)
- Graphiti Temporal Context Skill
- Skill: seo-audit-report
- Agent Readiness Report
- _tokenize
- Competitor Analysis — Autonomous AI Agency
- One command (recommended)
- test_procedural_memory.py
- test_server_autonomy_and_index_fixes.py
- autonomous_fix.py
- test_serve_spa_prefixes.py
- Runbook — Instance Activation
- RunnerLock
- SamVoiceScreen.jsx
- audit
- TestTheProducersAndTheParserCannotDrift
- run_patched_colibri.py
- test_phase4_runtime_resilience.py
- TestCountTokensEndpoint
- TestMCPClientStructuredOutput
- _routing_candidates
- DeltaChunk
- test_backend_lifespan_skips_bg_when_flag_false
- TestTheWorkflowIsSafeAndReadOnly
- _is_exempt
- TestExtendedThinkingRouting
- test_dependabot_sweep_workflow.py
- is_strict
- TestPoliciesGovernanceStableClaim
- TestWorkflow
- test_event_log.py
- _run_analyze
- TestMongoGate
- sam_router.py
- TestGPT55CostEntries
- test_workflow_api_mount.py
- _is_denied_path
- test_doctor_coding_brain.py
- BenchmarkReport
- _parse_reset_epoch
- test_model_catalog_guard.py
- TestProviderRouter
- Advisor Strategy — Local Proxy Handling
- _extract_workflow_relevance
- TestSeoApiSurface
- MCPToolResult
- LLMReasoner
- Skill: changelog-enforcer
- Skill: learn-rule
- Instructions
- AgentJobResult
- Skill: changelog-enforcer
- Skill: cowork-session (Claude Cowork)
- Skill: video-context — read a video without watching it
- ADR 003: Multi-Agent Orchestration with Plan-Execute-Verify Loop
- Issue #1356: quick-note:https://searchengineland.com/turn-seo-backlog-into-roadmap-485713
- _nvidia_default
- TestRanking
- Release Procedure
- V2.0 Modernization — Runbook
- LoopsScreen.jsx
- _Budget
- scrub
- openclaw_status
- _build_pdf
- analyze_quantitative
- record_usage_endpoint
- captured
- build_digest
- RoutingDecision
- Core Pillars
- TestSwarmRoleRouting
- .test_every_request_carries_a_real_user_agent
- _infer_parameters_from_func
- _get_current_user
- TestReviewRegressions
- TestBrainFailoverModelAliases
- WorkflowOrchestrator
- TestAgentLoopMCPIntegration
- _register_web_reach_tools
- TestEveryFullSuiteJobHasMongo
- TestPaidPolicyDurability
- oauth.py
- SECTION C — Direct Chat Improvements (CBF / HRM)
- TestDashboard
- _safe_resolve
- stt.py
- test_process_quick_note_workflow.py
- navigation_metrics.py
- test_daily_automation_2026_10_03.py
- test_tool_call_aliases.py
- hybrid_reasoning.py
- get_ceo_ledger
- quality_checker.py
- Skill: docs-sync
- _overlap_score
- Skill: browserbase-browser — Real Browser Automation
- Skill: docs-sync
- Skill: memory-consolidation (Dream Memory)
- memory_consolidation.py
- CapacityAllocation
- GitHub Branch Protection Settings
- ADR 001: Self-Hosted OpenAI-Compatible Proxy
- test_cost_attribution.py
- AGENTS.md — AI Agent Configuration for local-llm-server
- TestGPTRealtime21CostEntries
- Web UI + Admin (Claude Code–style)
- 467 Skill Inventory — load / wire / test status
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
- Runtime troubleshooting
- Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass
- begin_call
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
- research_coordinator.py
- Prime Agent Runtime
- commercial_equivalent.py
- The full agent capability roster
- PULL_REQUEST_TEMPLATE.md
- _LazyModuleProxy
- BrowserFetcher
- TestSessionMemory
- TestResolution
- FreeBuff — free-NVIDIA coding agent
- Sol Advisor
- verify.sh
- Tailored Onboarding, Editable Companies & Dynamic Roles
- run_seo_audit.py
- Setup
- test_workflow_engine_run_happy_path
- SECTION A — Agent Efficiency (Hermes / AOS / MYT)
- TestModels
- AlertsBell.jsx
- Prompt Library
- SIA.py
- test_ping.py
- TestAerolinkRolePresetsUpdated
- ._sprint
- PhaseSequenceError
- TestItIsNotBuiltForOneVendor
- _fixture
- test_local_brain_router_smoke.py
- TestFindPriorArt
- _replace
- TestReasoningBudget
- test_mcp_protocol_version.py
- _is_trivial_message
- _FakeCollection
- TestCatalog
- test_setup_detect_models_ssrf.py
- classify_domain
- dry_clone_repo
- .emit
- What's New
- _ErrorCaptureHandler
- Setup
- Model and Response Issues
- ai_insights.py
- UsageEvent
- Marketing Content Creator Agent
- Marketing Growth Hacker Agent
- Full-Output Enforcement
- summarise.sh
- TOP 6 — Highest-ROI Items (Validated by Opus Research Agent)
- build_connectors_router
- Agent Transparency Report
- _routing_presets
- ModelRegistry
- TestRetrieveRelevant
- Skill: Managed Agents Dreams
- Skill: Multi-Agent Coordinator
- Skill: Obsidian Knowledge Graph
- Multi-Agent Research Coordinator Skill
- Skill: SuperClaude Slash Commands
- Skill: SuperClaude Workflow Engine
- test_tick_endpoint_throttle.py
- ADR-006: Strangler Fig migration with backward-compat shims
- TestWorkflowEngine
- claude-mem Plugin — Persistent Memory for All Sessions
- orchestrator
- Platform Controls
- TestAFailedProbeIsNotASuccess
- Cloudflare = the real working app
- TestTask
- launch-claude-code.sh
- PRD — README Marketing Refresh
- .record_success
- quickstart.sh
- parse_react_response
- steering_for_task
- TestRunnerWorkspace
- _provider
- test_daily_2026_06_14.py
- TestIndexMode
- brain_providers
- github_oauth_callback
- Command: /plan
- TestFailuresAreData
- TestClassifyPlainText
- Skill: hybrid-reasoning (Hybrid AI)
- Pending Activities — Implementation Playbook
- TestReasonsAreActionable
- TestProvidersScreen
- SECTION B — NVIDIA / Cloud Model Integration (Nemotron / NVD)
- TestExecution
- TestMongoService
- SECTION D — Deployment & Infrastructure (CHM / NVD)
- TestCli
- TestTechSkillMap
- TestSettingsHasAnthropicEffortAttribute
- TestGroqLlama4ScoutCostEntry
- TestActiveStrategy
- TestChangelogParity
- TestSanitizePasteForPreview
- StatusPill.jsx
- Event
- The Agent Roster
- TestCitationBinding
- openclaw_mobile_ui
- Music Cues: happy-beats-business-moves-vol-1-by-ende-dot-app
- Feature Support Matrix
- /fix-bug — Bug Fix Agent
- Skill: browserbase-fetch — Lightweight Web Fetch
- TestAwaitReady
- Twitter Insights — Issue #228
- Twitter Insights — Issue #231
- OpenAI Codex CLI — Local LLM Server Config
- ADR-001: Adopt packages/ directory structure
- ADR-002: Centralize configuration in packages/config/
- ADR-003: Provider abstraction with unified interface
- ADR-004: Event bus for loosely coupled communication
- ADR-005: Merge Hermes into the main backend service
- TestMobileNavigation
- Pre-Mortem Analysis: Agency Core autonomy story (Cloudflare deployment)
- Runtime & Onboarding Issues
- TestTheStaticFloorLeadsWithVerifiedIds
- TestRecordSuccess
- TestDelegationPlan
- TestTheAgentRunsCurrentCode
- TestWorkflowWiring
- TestImageInstall
- gen_v4_screenshots.py
- test_the_reserve_is_bounded_when_read_from_the_environment
- TestModelRoleSeparation
- setup-claude-code.sh script
- _clean_phases
- Report
- Rule
- test_activity_feed.py
- TestWindowsAuth
- test_decline_cleanly_posts_comment_on_success
- TestCli
- Command: /resume
- Command: /review
- TestRouterNoDirectEnvRead
- TestProviders
- TestWiki
- SECTION E — Autonomy & Self-Healing (AOS / MYT / ECC)
- TestConfigReferenceDocumented
- TestSafeguardNotInRoutingCandidates
- TestBrainCandidates
- TestHermesKeepAlive
- root
- TestRule
- governance/__init__.py
- TestAdminEndpoints
- TestNoHardcodedModels
- TestBigPasteThreshold
- TestSavePaste
- TestBuild
- Prompt Library Changelog
- test_rate_limiter_concurrency.py
- CircuitBreakerOpenError
- create_streaming_reconstructor
- test_configured_dispatcher_does_not_hit_network
- test_agency_fix.py
- test_daily_automation_2026_09_30.py
- .update_status
- TestInternalAgentAdapterProviderChain
- heartbeat.sh
- feature-implementer.md
- /devops-check — DevOps Agent
- /docs-update — Documentation Agent
- /qa-check — QA Agent
- /security-audit — Security Agent
- Skill: browserbase-search — Structured Web Search
- Issue #230 — DUPLICATE
- llm/config.py
- test_repo_access_preflight_fails_when_git_ls_remote_fails
- Docker (local or any container host)
- test_a_failed_filing_releases_the_cooldown_so_the_next_recurrence_retries
- Documentation map
- TestRetryDoesNotOverrideADeliberateClosure
- inspect-agent-runtime.sh
- Proof
- TestGhIsNotReAuthenticated
- build_llama_cpp.ps1
- download_glm52_weights.ps1
- download_glm52_weights.sh script
- setup_colibri.ps1
- setup_colibri.sh script
- status_colibri_server.ps1
- _deep_merge
- get_cost_table
- send_digest
- TestAutonomousAgentUsesTheSharedFailover
- _InMemoryErrorLogHandler
- SECTION F — Developer Experience (CBF / ECC)
- resolve_coding_model_preference
- submit_simple_task
- test_doctor_anonymous_no_pat.py
- transport
- test_direct_adapter_does_not_bypass
- TestImplementerQueueSkipsReportOnlyIssues
- .test_concurrent_create_same_session
- .get_repository_map
- test_probe_report.py
- WebhookSendRequest
- SECTION H — Vision / Multimodal (NVD)
- _patch_send_message
- ProviderRouter
- filed
- codebase-explorer.md
- docs-auditor.md
- risk-reviewer.md
- verification-reviewer.md
- aider_config.sh
- Credential Rotation Runbook
- Runbook: `make doctor`
- render
- test-anthropic.js
- stop_colibri_server.ps1
- TestBackendMergesRegistryIntoTheEndpoint
- test_skills_route_order.py
- github
- [Unreleased]
- Session Learnings
- frontend/.eslintrc.json
- enforcement.py
- branch_cleanup.sh
- local-ai-health-check.sh
- pull-ai-models.sh
- agency_agents/README.md
- duplicate.sh
- Xb
- Yb
- completed-2026-09.md
- start_web_with_openclaw.sh
- frontend-redesign-prompt.md
- NEXT-SESSION-PROMPT.md
- docs/script.js
- get_tunnel_url.sh script
- redact_secrets.sh
- install.sh script
- models/README.md
- script.js
- setup-autostart.sh
- setup_autostart_macos.sh
- start.sh
- stop-proxy.sh script
- stop_server.sh script

## God Nodes (most connected - your core abstractions)
1. `_fixture()` - 376 edges
2. `Task` - 271 edges
3. `AgentRunner` - 251 edges
4. `TaskStatus` - 171 edges
5. `TaskStore` - 168 edges
6. `ProviderRouter` - 150 edges
7. `LLMRequest` - 131 edges
8. `TaskSpec` - 126 edges
9. `ProviderConfig` - 116 edges
10. `Added` - 115 edges

## Surprising Connections (you probably didn't know these)
- `3a. Apply the slop-gate to the sibling auto-PR scripts ✅  (size: S)` --references--> `_select_brain()`  [INFERRED]
  docs/plans/autonomy-uplift-roadmap.md → .github/scripts/autonomous_fix.py
- `What this document is for` --references--> `validate()`  [INFERRED]
  docs/QUICK_NOTE_CONTEXT_RULEBOOK.md → .github/scripts/context_rules.py
- `What this does not do` --references--> `allow_paid()`  [INFERRED]
  docs/llm-router/architecture.md → .github/scripts/provider_policy.py
- `Per-agent policies` --references--> `allow_paid()`  [INFERRED]
  docs/llm-router/configuration.md → .github/scripts/provider_policy.py
- `Cheap tiers` --references--> `allow_paid()`  [INFERRED]
  docs/llm-router/providers.md → .github/scripts/provider_policy.py

## Import Cycles
- None detected.

## Communities (1370 total, 368 thin omitted)

### Community 0 - "workflow_orchestrator.py"
Cohesion: 0.07
Nodes (17): BoundContext, ClassifyOutput, ExecutionResult, JudgeVerdict, MergeDecision, MonitorOutput, _orchestrator_bypass(), PersistOutput (+9 more)

### Community 1 - "typing"
Cohesion: 0.01
Nodes (45): code_graph_enabled(), translate_error_to_conversational(), detect_secrets(), main(), ToggleBody, start_proxy(), start_tunnel(), StatusResponse (+37 more)

### Community 2 - "TaskSpec"
Cohesion: 0.01
Nodes (127): Runtime Selection Policy, 3b. Hermes — **our own** Hermes server (in-repo), UI-wired ✅  (size: M), N2. Surface Hermes (and all runtimes) status in the Doctor/Runtimes UI ⬜  (size: S, risk: low), kimi_bridge_runtime_config(), AiderAdapter, ClaudeCodeAdapter, json_safe(), DockerAgentAdapter (+119 more)

### Community 3 - "LLMRequest"
Cohesion: 0.03
Nodes (68): Added, Added, ProviderConfig, build_provider(), resolve_kind(), LLMRequest, test_llm_gateway_openai_payload_disables_nemotron_thinking(), _anthropic_provider() (+60 more)

### Community 4 - "test_provider_router.py"
Cohesion: 0.04
Nodes (42): _acquire_provider_probe(), CommercialFallbackRequiredError, extract_openai_text(), _normalize_nvidia_base_url(), _openai_url(), ProviderFallbackError, _release_provider_probe(), _best_cloud_primary_base() (+34 more)

### Community 5 - "clear_stats"
Cohesion: 0.25
Nodes (4): clear_cost_attribution(), clear_stats(), get_stats(), test_cost_is_attributed_through_the_cost_tracker()

### Community 6 - "test_llm_router_queue_cache.py"
Cohesion: 0.02
Nodes (61): reset(), CacheManager, cosine_similarity(), _Entry, LRUCache, payload_key(), reset(), text_key() (+53 more)

### Community 8 - "proxy.py"
Cohesion: 0.03
Nodes (118): set_quick_note_queue(), admin_control(), admin_create_user(), admin_delete_user(), admin_login(), admin_logout(), admin_rotate_user(), AdminControlBody (+110 more)

### Community 9 - "brain_config.py"
Cohesion: 0.02
Nodes (61): Architecture (per plan §3), Files touched, Hard constraints (from the plan) — all met, Implementation — DB-persisted, UI-switchable Brain (PR #824 follow-up), New files, Resolution precedence, Risks & mitigations (per plan §6), Rollout / verification (per plan §5) (+53 more)

### Community 11 - "company_api.py"
Cohesion: 0.03
Nodes (72): ephemeral_ttl_hours(), account_lifecycle(), AccountLifecycleResponse, auto_recommend_skills(), cancel_onboarding(), create_company(), delete_company_endpoint(), _DoctorCheck (+64 more)

### Community 12 - "Usage"
Cohesion: 0.04
Nodes (16): Modules, Writing a custom adapter, classify_error(), LLMProvider, OpenAICompatible, retry_after_seconds(), GeminiProvider, register_adapter() (+8 more)

### Community 13 - "api.js"
Cohesion: 0.02
Nodes (55): UI-first — an API is not "done", approveGovernanceRequest(), createMcpServer(), createQuickNote(), createTask(), deleteGithubToken(), deleteMcpServer(), deleteModel() (+47 more)

### Community 14 - "Specialist"
Cohesion: 0.04
Nodes (6): Specialist, set_specialist_service(), SpecialistService, svc(), test_commerce_systems_route_to_domain_specialists(), test_family_is_fully_specified()

### Community 15 - "is_destructive_overwrite"
Cohesion: 0.10
Nodes (25): loops_overview(), seed_default_providers(), _get_cached_tasks(), _get_tasks_cache_lock(), Security, Security, Security, Security (+17 more)

### Community 16 - "failover_chat_completion"
Cohesion: 0.06
Nodes (44): failover_chat_completion(), _free_tier(), _hit_ids(), _many_providers(), _mixed_registry(), _openai_body(), _paid(), patch_chain() (+36 more)

### Community 17 - "strategies.py"
Cohesion: 0.04
Nodes (54): Preferring local, Choosing one, Costs are higher than expected, Latency got worse, HealthConfig, RoutingConfig, HealthTracker, _Outcome (+46 more)

### Community 18 - "sam_orchestrator.py"
Cohesion: 0.06
Nodes (25): build_brief(), detect_orchestration_intent(), extract_instruction(), handle_orchestration_command(), pick_up_portfolio(), portfolio_counts(), _portfolio_line(), _queue_counts() (+17 more)

### Community 19 - "test_freebuff_bot.py"
Cohesion: 0.11
Nodes (7): _restore_env(), test_embedded_flag(), test_embedded_run_bypasses_orchestrator(), test_fb_models_http_uses_proxy(), test_fb_run_embedded_dispatches_to_embedded_run(), test_fb_run_http_calls_proxy_with_commit_and_pr(), test_max_steps_clamped()

### Community 20 - "chat_handlers.py"
Cohesion: 0.06
Nodes (34): Layer 2 — Chat Handlers (`chat_handlers.py`, 710 lines), Fixed, _apply_chat_defaults(), _apply_reasoning_budget(), _emit_safely(), _extract_exact_output(), _filter_fragment(), _filter_openai_sse_line() (+26 more)

### Community 21 - "Changed"
Cohesion: 0.04
Nodes (43): _fetch_github_quick_notes(), _gh_repo(), ProviderPolicyUpdate, Changed, Changed, Completed Task Archive — June to August 2026, A0. Fix live scanner crashes on real-world sites (`services/scanner.py`) — do first, A. Fix error-message masking (`frontend/src/api.js`) (+35 more)

### Community 22 - "types.py"
Cohesion: 0.02
Nodes (74): build_router(), gateway_metrics(), consumer_label(), provider_for(), record_call(), get_budget(), get_cache(), failover_chat_completion_via_router() (+66 more)

### Community 23 - "test_ceo_dispatcher.py"
Cohesion: 0.04
Nodes (42): CEOResult, get_ceo_fallback_stats(), PlanOutput, _record_ceo_fallback(), reset_ceo_fallback_stats(), SpecialistSelection, _FakeRoutingDecision, _FakeRuntimeManager (+34 more)

### Community 24 - "Agency"
Cohesion: 0.04
Nodes (51): Agency, AgencyCycleResult, AgentDirective, AgentRole, _build_ceo_prompt(), _build_quick_note_instruction(), _close_github_issue(), _collect_recent_git_context() (+43 more)

### Community 25 - "test_brain_failover.py"
Cohesion: 0.06
Nodes (31): BrainFailoverManager, get_failover_manager(), ProviderHealth, _clean_env(), _make_manager(), test_429_exponential_backoff(), test_circuit_recovers_after_cooldown(), test_max_attempts() (+23 more)

### Community 26 - "SelfHealingAgent"
Cohesion: 0.05
Nodes (23): HealingEvent, _now(), SelfHealingAgent, _redispatch(), TestSelfHealingInfrastructureHint, TestSelfHealing, _event(), test_code_fences_stripped_for_telegram_markdown() (+15 more)

### Community 27 - "AnthropicProvider"
Cohesion: 0.04
Nodes (17): Added, Fixed, Added, Fixed, AnthropicProvider, _breakpoint_at(), _make_provider(), _make_provider_1h() (+9 more)

### Community 28 - "resolve_component_model"
Cohesion: 0.03
Nodes (40): _catalog_defaults(), invalidate_brain_config_cache(), resolve_component_model(), resolve_component_role_models(), UNIT 7 — Catalog propagation to all remaining call sites ✅, _default_reasoning_model(), _resolve_nvidia_default_model(), test_invalidate_forces_reread() (+32 more)

### Community 29 - "TaskStatus"
Cohesion: 0.03
Nodes (61): blocked_cooldown_s(), TaskStatus, _get_workflow_engine(), TaskExecutionCoordinator, get_task_store(), TaskStore, test_coordinator_timeout_records_a_lesson(), _make_task() (+53 more)

### Community 30 - "backend/server.py"
Cohesion: 0.02
Nodes (143): set_skill_registry(), _is_admin(), admin_seed(), _agent_timeout_fallback_response(), AgentStatusEntry, AgentStatusResponse, AgentToolCallEntry, ApiKeyCreate (+135 more)

### Community 31 - "Added"
Cohesion: 0.02
Nodes (89): _resolve_role_model(), _summarise_tool_result(), _timed_phase(), Added, Activation, Added, 1. Executive summary, 2. Architecture review (+81 more)

### Community 32 - "test_governance_sandbox.py"
Cohesion: 0.04
Nodes (41): 1.11 Multi-Agent Governance (10 / 100 / 1000 agents), Failure behaviour, build_docker_run_argv(), detect_backend(), DockerBackend, E2BBackend, load_profiles(), LocalBackend (+33 more)

### Community 33 - "AppShell.jsx"
Cohesion: 0.09
Nodes (29): `activation_api.py`, Backend changes, `backend/company_api.py`, `db/sqlite_store.py`, Docs / changelog, Frontend changes, Goal, Implementation Plan — Onboarding-Gate Admin Setting + Ephemeral Companies (+21 more)

### Community 34 - "AgentScheduler"
Cohesion: 0.04
Nodes (28): _age_seconds(), AgentScheduler, _now(), ScheduledJob, _top_prefixes(), test_scheduled_job_has_no_status_attribute(), test_scheduler_attach_main_loop_and_fire_from_thread(), test_scheduler_does_not_fire_or_consume_run_once_jobs_when_killed() (+20 more)

### Community 35 - "build_governance_router"
Cohesion: 0.06
Nodes (38): build_governance_router(), approve(), _decide(), deny(), destroy_sandbox(), get_audit(), get_budget(), get_metrics() (+30 more)

### Community 36 - "test_e2b_sandbox.py"
Cohesion: 0.05
Nodes (37): _inject_token(), maybe_attach_e2b(), _scrub_token(), _clean_e2b_env(), fake_sandbox(), _FakeAsyncSandboxClass, _FakeCommandResult, _FakeCommands (+29 more)

### Community 37 - "agency_fix.py"
Cohesion: 0.02
Nodes (58): build_review_context(), _gh(), main(), _fetch_models_json(), _is_chat_model(), live_model_ids(), _rank_key(), rank_models() (+50 more)

### Community 38 - "MultiAgentSwarm"
Cohesion: 0.04
Nodes (38): AgentConfig, build_agent_specs(), build_swarm(), build_task_specs(), coordinate_v2(), CoordinateRequestV2, CoordinateResponse, SwarmSummary (+30 more)

### Community 39 - "RuntimeHealthService"
Cohesion: 0.09
Nodes (4): F2 — MCP Server Exposing Proxy Capabilities [P1] [CBF / ECC], CircuitState, RuntimeHealthService, TestCircuitState

### Community 40 - "test_governance_api.py"
Cohesion: 0.07
Nodes (31): reset_gate(), _client(), _StubRunner, test_admin_can_read_status(), test_audit_endpoint_filters(), test_audit_endpoint_never_returns_a_secret(), test_audit_endpoint_returns_recorded_events(), test_budget_endpoints_require_admin() (+23 more)

### Community 41 - "test_platform_controls.py"
Cohesion: 0.04
Nodes (39): _reset_control(), _set_control(), apply_overrides(), _refresh_settings_singleton(), all_controls(), get_control(), _gate_outward_facing_enabled(), clean_overrides() (+31 more)

### Community 42 - "activation_api.py"
Cohesion: 0.04
Nodes (49): activation_required(), ActivationResult, activate_instance(), ActivateRequest, ActivateResponse, activation_audit_log(), activation_status(), ActivationStatusResponse (+41 more)

### Community 43 - "ref_react"
Cohesion: 0.07
Nodes (35): Phase 2 — Per-surface assignment in the UI (the "one place"), createProvider(), deleteProvider(), getBrainProviders(), getProviderPolicy(), setBrainProviderEnabled(), syncProviderToRender(), updateProviderPolicy() (+27 more)

### Community 44 - "PolicyEngine"
Cohesion: 0.03
Nodes (46): _egress_policy_reason(), R3 — Reach a verdict, and let that verdict be "reject" **[gate]**, _coerce_text(), new_session_id(), slugify_agent(), _action_matches(), _as_list(), Decision (+38 more)

### Community 45 - "Fixed"
Cohesion: 0.05
Nodes (31): onboarding_gate_enabled(), Added, Added, Changed, Fixed, Fixed, Fixed, Fixed (+23 more)

### Community 46 - "ExecutionRequest"
Cohesion: 0.05
Nodes (14): _scheduler_on_fire(), get_orchestrator_supervisor(), OrchestratorSupervisor, stop_orchestrator_supervisor(), ExecutionRequest, get_workflow_orchestrator(), reset_orchestrator(), test_scheduler_on_fire_is_a_coroutine() (+6 more)

### Community 47 - "test_schedule_backlog_drain.py"
Cohesion: 0.07
Nodes (20): _every_minute_one_shot(), _FakePersistence, _one_shot(), _stamp(), test_a_daily_low_priority_fix_job_is_not_caught_by_the_fast_path(), test_a_disabled_every_minute_one_shot_is_preserved(), test_a_failed_durable_delete_is_not_counted_as_expired(), test_a_fired_one_shot_is_still_removed_by_the_original_rule() (+12 more)

### Community 48 - "MongoDBStore"
Cohesion: 0.05
Nodes (4): Security, Security, MongoDBStore, TestMalformedCompanyId

### Community 49 - "control_overrides.py"
Cohesion: 0.06
Nodes (28): _get_control(), set_setting(), _actor(), build_platform_controls_router(), _admin(), list_controls(), reset_control(), update_controls() (+20 more)

### Community 50 - "_mock_provider_records"
Cohesion: 0.13
Nodes (3): _mock_provider_records(), TestOrchestratorProviderFailover, _runner_run()

### Community 51 - "failover_client.py"
Cohesion: 0.03
Nodes (39): FailureCategory, _maybe_boot_purge(), _purge_summary_clean(), ma(), Fixed, Fixed, Fixed, Fixed (+31 more)

### Community 52 - "test_mcp_registry.py"
Cohesion: 0.05
Nodes (14): _status_for(), RenderFinding, _noop_async(), _spec(), TestPlaywrightBrowserBackends, TestRenderFindingsReachTheHealer, latest_deploy(), TestStatusMeasurement (+6 more)

### Community 53 - "get_registry"
Cohesion: 0.05
Nodes (26): get_registry(), TestClaude5RegistryEntries, test_bedrock_haiku_4_5_in_registry(), test_bedrock_opus_48_in_registry(), test_bedrock_opus_4_6_v1_in_registry(), test_bedrock_opus_4_7_in_registry(), test_bedrock_sonnet_4_6_in_registry(), test_deepseek_v3_in_registry() (+18 more)

### Community 54 - "Added"
Cohesion: 0.03
Nodes (77): BudgetExceededError, _nvidia_defaults(), lifespan(), Added, Added, Added, reset_store(), Added (+69 more)

### Community 55 - "llm/router.py"
Cohesion: 0.03
Nodes (50): RetryConfig, get_limiter(), BreakerState, reset(), _digest(), get_ring(), KeyRing, KeyState (+42 more)

### Community 56 - "@testing-library/react"
Cohesion: 0.09
Nodes (30): getMe(), login(), logout(), App(), AppRoutes(), LoadingScreen(), ProtectedRoute(), V5App (+22 more)

### Community 57 - "Added"
Cohesion: 0.05
Nodes (19): Added, Added, Render MCP — platform debugging and environment monitoring, 1. Coding sessions — stdio, via `.mcp.json`, 2. The running agency — Streamable HTTP against a deployed sidecar, Configuration, Enabling it, HTTP API (+11 more)

### Community 59 - "test_repo_connection.py"
Cohesion: 0.10
Nodes (19): attach_repo_connection(), build_repo_connection(), detect_delivery_policy(), parse_repo_url(), provider_of(), UnsupportedProviderError, _FakeStore, _Probe (+11 more)

### Community 60 - "make_client"
Cohesion: 0.06
Nodes (45): consumer_id(), chat_body(), clear_dependency_overrides(), make_client(), _StubRouter, Upstream, policy_file(), test_allow_list_requires_a_match_and_deny_still_wins() (+37 more)

### Community 61 - "test_memory_guard.py"
Cohesion: 0.12
Nodes (12): _load_malloc_trim(), memory_guard_enabled(), _resolve_interval_sec(), trim_now(), test_enable_flag_parsing(), test_enabled_by_default(), test_interval_honours_a_valid_large_value(), test_interval_is_floored_never_busy_loops() (+4 more)

### Community 62 - "test_scanner_headless.py"
Cohesion: 0.04
Nodes (17): 5. Input Validation, _is_blocked_host(), _looks_like_bot_challenge(), _guard(), TestTheCostTableHasNoDuplicateKeys, _scanner(), TestBotChallengeDetection, TestBuiltWithFallback (+9 more)

### Community 63 - "HttpxFetcher"
Cohesion: 0.04
Nodes (19): browser_backend_available(), FetchResult, HttpxFetcher, looks_blocked(), make_fetcher(), ResilientFetcher, _block_then_nothing_transport(), _CountingTransport (+11 more)

### Community 64 - "gateway/config.py"
Cohesion: 0.07
Nodes (30): _flag(), max_request_bytes(), _non_negative_int(), prompt_policy_enabled(), prompt_policy_file(), proxy_cache_enabled(), _raw(), sanitizer_mode() (+22 more)

### Community 65 - "AgentRunner"
Cohesion: 0.02
Nodes (75): AgentPhaseError, AgentRunner, _run(), _check_extra_kwargs(), _enforce_signature(), _handler_params(), How I would make the smaller model behave like me, Part 2 — Handing frontier skills to a smaller model (+67 more)

### Community 66 - "MCPClient"
Cohesion: 0.08
Nodes (3): MCPClient, T11 — Governance bypass, TestMCPClient

### Community 67 - "CompanyGraphService"
Cohesion: 0.02
Nodes (10): Repo, Website, CompanyGraphService, set_company_graph_service(), TestCompanyGraphServices, TestDeleteCompanyRemovesAgents, TestGraphEndpointServiceContract, TestMongoStoreExtraFieldTolerance (+2 more)

### Community 68 - "WebsiteScanner"
Cohesion: 0.04
Nodes (29): main(), _scan_one(), _is_safe_url(), WebsiteScanner, TestScannerService, test_scanner_developer_tools(), test_scanner_modern_saas(), test_scanner_open_source_docs() (+21 more)

### Community 69 - "SessionBudget"
Cohesion: 0.10
Nodes (7): 5. What was implemented, Measurable improvements, 1.12 Cost Governance, SessionBudget, test_duration_ceiling_fires_from_elapsed_time(), test_each_session_ceiling_fires_on_its_own_dimension(), test_provider_token_shapes_are_redacted_inside_free_text()

### Community 70 - "test_governance_enforcement.py"
Cohesion: 0.06
Nodes (35): BudgetTracker, GovernanceGate, resolve_identity(), _engine(), test_a_broken_policy_engine_allows_rather_than_breaking_dispatch(), test_a_missing_limit_key_means_unlimited_not_zero(), test_a_tool_allow_list_applies_even_when_the_tool_carries_a_path(), test_approval_gate_blocks_until_a_human_approves() (+27 more)

### Community 71 - "test_llm_router_e2e.py"
Cohesion: 0.07
Nodes (59): _ok(), _request(), router_factory(), build(), test_413_fails_over_to_the_next_provider(), handler(), test_429_fails_over_to_the_next_provider(), handler() (+51 more)

### Community 72 - "test_model_catalog.py"
Cohesion: 0.04
Nodes (47): _build_base_url_env_from_yaml(), _build_default_base_url_from_yaml(), _build_display_names_from_yaml(), _build_key_env_from_yaml(), _build_tier_from_yaml(), get_provider_candidates(), get_provider_display_name(), get_provider_tier() (+39 more)

### Community 73 - "DashboardScreen.jsx"
Cohesion: 0.09
Nodes (30): Added, Added, Adding capacity: multi-key rotation, Read this before enabling it, The gain is across requests, not within one, BarChart(), Charts, Donut() (+22 more)

### Community 74 - "agent/workspace.py"
Cohesion: 0.05
Nodes (25): _get_workspace_lock(), get_workspace_manager(), _hash_component(), _iso_now(), _iso_offset_hours(), _load_workspace(), _parse_iso(), _read_manifest() (+17 more)

### Community 75 - "seo_portfolio_bridge.py"
Cohesion: 0.06
Nodes (21): plan_next_sprint(), SprintPlan, RoadmapHorizon, build_seo_roadmap(), delegation_plan_to_initiatives(), delegation_task_to_initiative(), plan_seo_sprint(), run_seo_to_agile_pipeline() (+13 more)

### Community 76 - "_ts_to_float"
Cohesion: 0.04
Nodes (42): reset_failover_manager(), _blocked_retire_age_sec(), _heal_blocked_backlog(), _heal_brain_failover(), _heal_purge_backlog(), _heal_stuck_tasks(), _heal_telegram(), _heal_timestamps() (+34 more)

### Community 77 - "test_kill_switch_and_agent_budget.py"
Cohesion: 0.05
Nodes (47): agent_scope(), AgentBudgetExceeded, _bucket(), current_agent(), ensure_agent_can_spend(), record_agent_spend(), reset(), _Spend (+39 more)

### Community 78 - "test_cost_aware_routing_eval.py"
Cohesion: 0.08
Nodes (28): main(), ModelPrice, set_price(), token_cost(), load_runs(), _money(), _parse_runs(), render_report() (+20 more)

### Community 79 - "setup/api.py"
Cohesion: 0.06
Nodes (35): is_user_onboarding_allowed(), complete_wizard(), _delete_wizard_state(), detect_configured_providers(), detect_hardware_for_wizard(), detect_models_for_wizard(), _detect_ollama_models(), get_setup_state() (+27 more)

### Community 80 - "RenderOpsMonitor"
Cohesion: 0.08
Nodes (9): RenderDeploy, RenderOpsMonitor, _FakeRender, TestOpsStatusResponseModel, TestRenderDeploy, TestRenderOpsMonitor, get_metrics(), resolve_service_ids() (+1 more)

### Community 81 - "test_model_router.py"
Cohesion: 0.05
Nodes (73): classify_task(), _extract_recent_text(), reset_router(), clear_router(), _router(), test_agent_execute_classifies_as_code_generation(), test_agent_plan_classifies_as_reasoning(), test_agent_verify_classifies_as_code_generation() (+65 more)

### Community 82 - "RepowiseIntelligence"
Cohesion: 0.09
Nodes (11): RepowiseIntelligence, test_get_answer_returns_string(), test_get_context_returns_string(), test_get_decision_flownodes_returns_string(), test_get_overview_returns_dict(), test_get_risk_returns_dict(), test_get_why_returns_string(), test_repowise_intelligence_initialization() (+3 more)

### Community 83 - "control.py"
Cohesion: 0.11
Nodes (16): B. Make runtime activation non-blocking (`runtimes/control.py`,, listSpecialists(), _find_agent_runtime_script(), _get_ollama_base(), _is_docker_unavailable(), _remote_runtime_response(), _runtime_health(), start_all_runtimes() (+8 more)

### Community 85 - "detector.py"
Cohesion: 0.06
Nodes (23): batch_compatibility(), check_model_compatibility(), _detect_amd_gpus(), _detect_apple_silicon_gpu(), _detect_cpu(), detect_hardware(), _detect_intel_arc_gpu(), _detect_nvidia_gpus() (+15 more)

### Community 86 - "test_web_reach.py"
Cohesion: 0.06
Nodes (41): _domain_list_reason(), WebReach, _fake_fetch_module(), _fake_video_module(), _fresh_search_skips(), _hanging_search_engines(), test_a_hung_backend_is_skipped_on_the_next_search(), test_build_tool_prompt_advertises_browse_page() (+33 more)

### Community 87 - "facade.py"
Cohesion: 0.04
Nodes (38): create_access_token(), create_refresh_token(), get_current_user(), get_optional_user(), github_repo_access(), github_webhook(), google_callback(), JWTUserStateMiddleware (+30 more)

### Community 88 - "Settings"
Cohesion: 0.03
Nodes (11): _get_settings(), Settings, TestSettingsAnthropicDefaultEffort, TestSettingsAnthropicThinkingBudget, TestPlaywrightSettings, TestRenderSettings, test_catalog_flag_defaults_on(), test_is_catalog_enabled_case_insensitive() (+3 more)

### Community 89 - "TaskWorkflowService"
Cohesion: 0.04
Nodes (37): AgentCreateRequest, AgentDefinition, AgentStore, AgentUpdateRequest, set_agent_store(), _task_store_for_background(), _wire_feature_stores(), main() (+29 more)

### Community 90 - "test_startup_warmup.py"
Cohesion: 0.04
Nodes (24): _bootstrap_within_budget(), _create_bootstrap_indexes(), ensure_bootstrap(), seed_default_agents(), _sync_ollama_model(), defer_to_background(), warmup_step(), _isolate_warmup_overflow() (+16 more)

### Community 91 - "api.ts"
Cohesion: 0.07
Nodes (60): adminBootstrap(), adminCreateProvider(), adminCreateWorkspace(), adminDeleteProvider(), adminDeleteWorkspace(), adminGetBrainPolicy(), adminGetProviderRoleTags(), adminHeaders() (+52 more)

### Community 92 - "Company"
Cohesion: 0.05
Nodes (7): C. Defer company persistence to a final "Confirm" step + relocate the email gate, Company, _normalize_domain(), _require_non_blank(), TestCompanyGraphModels, test_company_is_frozen_and_activity_goes_through_model_copy(), test_list_companies_returns_a_plain_list()

### Community 93 - "frontend/package.json"
Cohesion: 0.03
Nodes (66): browserslist, development, production, dependencies, axios, fast-uri, livekit-client, lucide-react (+58 more)

### Community 94 - "test_ceo_supervision.py"
Cohesion: 0.06
Nodes (47): _harvest_changed_files(), SubtaskRecord, _goal(), _Result, _RoutingDecision, _ScriptedManager, _seed_goal(), _supervisor() (+39 more)

### Community 95 - "unsafe_target_reason"
Cohesion: 0.08
Nodes (16): _load_script_module(), unsafe_target_reason(), Added, Security, Agent loop, Added, Security, Browser automation for agents (+8 more)

### Community 96 - "test_e2e_agent_chat.py"
Cohesion: 0.08
Nodes (18): _auth_headers(), _build_agent_http_mock(), mock_get(), mock_post(), mock_put(), _exec(), _fake_request(), _mcp_tool_response() (+10 more)

### Community 97 - "pr_approval_gate.py"
Cohesion: 0.12
Nodes (22): Added, Added, getTaskCounts(), listTasks(), _card_keyboard(), _card_text(), _dedupe_key(), default_run_sweep() (+14 more)

### Community 98 - "telegram_bot.py"
Cohesion: 0.03
Nodes (80): Changed, Fixed, [v4.1.0], Fixed, get_decisions_store(), sanitize_paste_for_preview(), _admin_headers(), _answer_callback() (+72 more)

### Community 99 - "resolve_e2b_config"
Cohesion: 0.05
Nodes (28): e2b_status(), e2b_enabled(), E2BConfig, _env_falsy(), _env_truthy(), is_e2b_sdk_importable(), resolve_e2b_config(), _sandbox_mode_e2b() (+20 more)

### Community 100 - "Current Sprint Tasks"
Cohesion: 0.08
Nodes (20): _clean_heading(), distill(), _heading_key(), _load(), persona_for_family(), Changed, Fixed, Active Task Tracker (+12 more)

### Community 101 - "test_runtime_governance.py"
Cohesion: 0.13
Nodes (21): _governance_check(), _governance_identity(), _decision(), _engine(), SecondAdapter, _spec(), StubAdapter, test_a_broken_governance_layer_allows_the_dispatch() (+13 more)

### Community 102 - "TestClient"
Cohesion: 0.10
Nodes (15): bare_repo(), _call(), _data(), git_config_env(), _is_error(), mcp_workspace_root(), _rpc(), TestMCPBranchAndCommit (+7 more)

### Community 103 - "_StubProvider"
Cohesion: 0.07
Nodes (10): _models_to_try(), dead_models(), _mock_get(), _ok(), _handler(), _StubProvider, TestDisableGate, TestDiscovery (+2 more)

### Community 104 - "test_ceo_micromanager.py"
Cohesion: 0.04
Nodes (65): build_subtask_brief(), _coerce_subtasks(), decompose(), _env_flag(), _env_int(), _extract_json_object(), fallback_decomposition(), get_config() (+57 more)

### Community 105 - "test_ceo_self_learning.py"
Cohesion: 0.07
Nodes (35): beliefs(), _bound(), _get_store(), learn(), learning_context(), outcome_of(), PlaybookStore, render() (+27 more)

### Community 106 - "test_knowledge_sync.py"
Cohesion: 0.07
Nodes (38): _api_key(), _auth_headers(), _build_digest_markdown(), create_wiki_page(), fetch_and_store(), get_knowledge_sync(), KnowledgeSync, _now_iso() (+30 more)

### Community 107 - "FeatureMatrix"
Cohesion: 0.04
Nodes (12): FeatureMatrix, TestSupportMatrixDocsSync, TestAdminVisibility, TestConfigOverrides, TestEnforcement, TestRegistryLoads, TestAdminVisibility, TestClassification (+4 more)

### Community 108 - "CompanyAgencyService"
Cohesion: 0.04
Nodes (14): CompanyAgencyService, _is_runtime_available_sync(), _pick_available_runtime(), set_company_agency_service(), test_company_agency_activate_creates_all_schedules(), get_company(), company(), activation() (+6 more)

### Community 109 - "ToolRegistry"
Cohesion: 0.06
Nodes (9): get_tool_registry(), ToolDef, ToolRegistry, decorator(), _inject_tool_results_as_messages(), TestInjectToolResults, TestToolDef, handler() (+1 more)

### Community 110 - "test_free_model_speed.py"
Cohesion: 0.07
Nodes (23): _nemotron_thinking_enabled(), with_nemotron_thinking_off(), _remaining_budget_s(), _explore(), _FakeClock, _run_with_budget(), fake_chat_text(), fake_plan() (+15 more)

### Community 111 - "test_trend_watcher.py"
Cohesion: 0.05
Nodes (28): _ollama_notes_actionable(), _FakeClient, _FakeResp, setup_database_moks(), test_fetch_arxiv(), test_fetch_github_trending(), test_fetch_google_news(), test_fetch_hackernews() (+20 more)

### Community 112 - "tasks/api.py"
Cohesion: 0.15
Nodes (31): add_comment(), approve_checkpoint(), approve_execution(), clarify_task(), create_task(), _current_user(), delete_task(), escalate_task() (+23 more)

### Community 113 - "ProviderRouter"
Cohesion: 0.03
Nodes (53): _catalogue_models(), _exponential_backoff_cooldown(), _extend_with_live_catalogue(), _get_director(), is_commercial_provider(), _live_models(), _notify_watchdog(), provider_access_tier() (+45 more)

### Community 114 - "SyncService"
Cohesion: 0.05
Nodes (22): require_permission(), _dep(), require_power_user(), add_peer(), get_folder_index(), get_sync_file(), get_sync_service(), list_conflicts() (+14 more)

### Community 115 - "test_sqlite_store.py"
Cohesion: 0.05
Nodes (38): test_agent_specs_collection_is_whitelisted(), test_count_documents(), test_count_documents_empty_query_fast_path(), test_delete_one(), test_delete_one_miss_returns_zero(), test_distinct(), test_estimated_document_count(), test_find_async_iteration() (+30 more)

### Community 116 - "WorkspaceManager"
Cohesion: 0.06
Nodes (10): TestCrossSessionIsolation, TestWorkspaceCleanup, TestWorkspaceLifecycle, TestWorkspaceManifest, TestWorkspaceMetrics, TestWorkspaceNotFound, TestWorkspaceResume, TestCleanupIsolation (+2 more)

### Community 117 - "services/background.py"
Cohesion: 0.05
Nodes (53): _dispatch_async(), _run(), get_log_monitor(), LogMonitor, _note_recurrence(), set_log_monitor(), _sig(), get_self_healing_agent() (+45 more)

### Community 118 - "AgentSwarm"
Cohesion: 0.06
Nodes (10): AgentSwarm, TestDualModelInvariant, TestSwarmPermissions, _fake_artifact(), TestSlice, Artifact, ModelRoutingConfig, Slice (+2 more)

### Community 119 - "PreflightReport"
Cohesion: 0.06
Nodes (19): PreflightIssue, PreflightReport, clean_store(), _clear_overrides(), _fake_user(), test_agent_runner_no_stale_kwargs(), check_all(), test_humanized_momentum_status() (+11 more)

### Community 120 - "ai_runner.py"
Cohesion: 0.08
Nodes (25): append_checkpoint(), _build_claude_command(), cmd_audit(), cmd_changelog_check(), cmd_logs(), cmd_manifest(), cmd_resume(), cmd_start() (+17 more)

### Community 121 - "PersistentMemoryStore"
Cohesion: 0.07
Nodes (14): MemoryCategory, MemoryEntry, MemoryScope, PersistentMemoryStore, cmd_autoload(), cmd_delete(), cmd_export(), cmd_import() (+6 more)

### Community 122 - "services/seo_audit.py"
Cohesion: 0.04
Nodes (23): SeoAuditRequest, SeoAuditSummary, SeoFixAction, SeoIssueInstance, SeoIssueReportRow, SeoPageAudit, SeoSiteFindings, _host_key() (+15 more)

### Community 123 - "_cfg"
Cohesion: 0.06
Nodes (8): _cfg(), _cost_table(), TestContextWindowCorrections, TestFableMythosPricingCorrection, TestHaiku45PricingCorrection, TestMythos51Catalog, TestOpusPricingCorrection, TestSonnet5PricingLocked

### Community 124 - "test_direct_chat_async.py"
Cohesion: 0.06
Nodes (21): make_isolated_workspace(), _workspace_component(), _fake_user(), _FakeChatResult, _FakeResponse, test_agent_mode_github_preflight_missing_token(), test_agent_mode_queues_async_job(), check_all() (+13 more)

### Community 125 - "KeyStore"
Cohesion: 0.07
Nodes (25): 1. Authentication & Authorization, API Key Authentication, JWT / Token Auth, Category 2 — API Key Naming Confusion, TD-005 [MEDIUM] — Production Keys Have `test-key-` Prefix, _check_rate_limit(), default_keys_path(), issue_new_api_key() (+17 more)

### Community 126 - "test_autonomous_agency_e2e.py"
Cohesion: 0.05
Nodes (22): BackgroundAgent, heartbeat(), BackgroundTask, _now(), get_tracker(), reset_tracker(), TestAgentKPITracking, TestBackgroundAgentRetryLogic (+14 more)

### Community 127 - "AgentJobRequest"
Cohesion: 0.11
Nodes (14): AgentJobRequest, Added, Acceptance check, Agency Core — Ruthless Architecture Audit & Migration Plan, Root causes (not symptoms), Section 1 — The Brutal Truth, Section 2 — Keep / Salvage / Replace / Remove, Section 3 — The Chosen Foundation (+6 more)

### Community 128 - "TestRenderMCPClient"
Cohesion: 0.10
Nodes (4): _client(), _FakeInner, TestRenderMCPClient, _flaky_initialize()

### Community 129 - "AdminAuthManager"
Cohesion: 0.12
Nodes (6): Admin Authentication, AdminAuthManager, AdminSession, AdminSessionStore, _is_truthy(), WindowsCredentialAuthenticator

### Community 130 - "AgentJobManager"
Cohesion: 0.06
Nodes (16): AgentJob, AgentJobManager, heartbeat(), _now(), get_agent_job_manager(), Runtime Integration, TestAgentJobManagerContracts, TestAgentJobLifecycle (+8 more)

### Community 131 - "_step"
Cohesion: 0.05
Nodes (10): _job(), quick_note(), _step(), TestABurnInVerdictNeedsData, TestEscalationsSayWhatActuallyFailed, TestOnlyAPassingCouncilMerges, TestReviewBotsAreCounted, TestThePlanIsRead (+2 more)

### Community 132 - "_llm_catalog"
Cohesion: 0.06
Nodes (12): _brain_config_source(), _cost_tracker_source(), _llm_catalog(), _routing_candidates(), _routing_presets(), TestDeepSeekDirectAPICatalog, TestDeepSeekFlashBrainConfig, TestDeepSeekFlashCandidates (+4 more)

### Community 133 - "_FakeCommandResult"
Cohesion: 0.20
Nodes (4): _FakeCommandResult, _FakeCommands, _FakeFiles, counting_run()

### Community 134 - "LogWatcher"
Cohesion: 0.05
Nodes (9): _auto_file_enabled(), ErrorFingerprint, LogEntry, LogWatcher, _redact_sensitive(), TestAutoFileEnabledGate, TestCreateGithubIssueRepoRequired, TestFirstScanFromBeginning (+1 more)

### Community 135 - "test_context_rulebook.py"
Cohesion: 0.06
Nodes (31): _bound_names(), _good_result(), _guard_statements(), _load(), _rule_ids(), rules(), test_ci_script_ends_with_a_newline(), test_ci_script_entrypoint_is_not_truncated() (+23 more)

### Community 136 - "system_instruction"
Cohesion: 0.13
Nodes (3): system_instruction(), TestSystemInstructionStrictMode, TestSystemInstruction

### Community 137 - ".tick"
Cohesion: 0.10
Nodes (5): _note_recurrence(), _parse_timestamp(), _report_to_healer(), _rfc3339(), _utcnow()

### Community 138 - "test_all_features.py"
Cohesion: 0.03
Nodes (21): TestActivation, TestActivity, TestAgents, TestApiKeys, TestAuth, TestChat, TestCompany, TestDashboard (+13 more)

### Community 139 - "ArtifactStore"
Cohesion: 0.06
Nodes (9): TestTeamSummary, store(), TestArtifactStoreDeletion, TestArtifactStoreJSONArtifact, TestArtifactStoreListing, TestArtifactStorePersist, TestArtifactStoreRetrieval, ArtifactStore (+1 more)

### Community 140 - "SecurityScanner"
Cohesion: 0.07
Nodes (28): first_party_imports(), import_names(), _installed_modules(), is_directly_imported(), _normalize(), _now(), _safety_finding(), SecurityFinding (+20 more)

### Community 141 - "test_loop_registry.py"
Cohesion: 0.08
Nodes (28): audit_drift(), _cmd_audit(), DriftReport, _grade(), load_registry(), load_registry_sync(), loop_readiness(), LoopRegistry (+20 more)

### Community 142 - "Agent"
Cohesion: 0.06
Nodes (4): Agent, TeamCoordinator, TestAgent, TestTeamCoordinator

### Community 143 - "test_integration_c4_c5_c6_d3.py"
Cohesion: 0.07
Nodes (18): detect_harness(), Harness, harness_context_limit(), harness_stats(), HarnessProfile, record_harness_hit(), route_for_harness(), TruncationStrategy (+10 more)

### Community 144 - "_llm_catalog"
Cohesion: 0.06
Nodes (9): _cost_table_src(), _llm_catalog(), _routing_candidates(), test_catalog_consistency_script_passes(), test_declared_id_count_increased(), TestGemini15Entries, TestMistralApiEntries, TestNvidiaNemotronEntries (+1 more)

### Community 145 - "diagnostics.py"
Cohesion: 0.06
Nodes (22): _check_background_liveness(), _check_ci_parity(), _check_company_graph(), _check_disk(), _check_event_log_integrity(), _check_feature_matrix(), _check_github_readiness(), _check_ollama() (+14 more)

### Community 146 - "AgileSprint"
Cohesion: 0.05
Nodes (10): generate_sprint_retro(), AgileSprint, SprintHealth, StoryStatus, UserStory, TestAgileSprint, TestRetrospective, TestScopeChange (+2 more)

### Community 147 - "Page"
Cohesion: 0.06
Nodes (9): _login_api(), main(), _navigate_auth_callback(), _navigate_logged_out(), run_tests(), test_social_login_browser(), TestAuthCallback, TestAuthMeEndpoint (+1 more)

### Community 148 - "test_bedrock_provider.py"
Cohesion: 0.06
Nodes (10): _bedrock_api_response(), _bedrock_provider(), _mock_boto3(), TestBedrockHealthCheck, TestBedrockResponseToOpenai, TestBedrockRoutingAffinity, TestFromEnvBedrock, TestOpenAiToBedrockConverse (+2 more)

### Community 149 - "BrowserSession"
Cohesion: 0.05
Nodes (21): browse_page(), BrowserAction, BrowserSession, _not_started(), PageState, _unsafe_reason(), _register_browser_tools(), _browse_page_tool() (+13 more)

### Community 150 - "ProceduralMemoryStore"
Cohesion: 0.19
Nodes (4): get_procedural_memory(), ProceduralMemoryStore, test_procedural_memory_redacts_before_storing(), TestGetProceduralMemory

### Community 151 - "TokenBudget"
Cohesion: 0.05
Nodes (24): BudgetUsage, TokenBudget, Activation, Agent: Implementer (Executor), Constraints, Handoff, Preferred Model, Responsibilities (+16 more)

### Community 152 - "Command"
Cohesion: 0.06
Nodes (5): Command, CommandCategory, CommandDispatcher, TestCommand, TestCommandDispatcher

### Community 153 - "Troubleshooting"
Cohesion: 0.04
Nodes (53): 401 Unauthorized, 403 Forbidden from remote machine, 429 Too Many Requests, Admin Dashboard Issues, Agent API Issues, Agent makes a change but doesn't verify correctly, Agent returns empty or incomplete plan, Agent workspace errors ("file not found") (+45 more)

### Community 154 - "BudgetTracker"
Cohesion: 0.08
Nodes (10): BudgetTracker, Counter, _Dimensions, _month(), _today(), BudgetConfig, test_budget_alerts_fire_once_per_threshold(), test_budget_is_advisory_unless_enforcement_is_on() (+2 more)

### Community 155 - "PrimeAgentAdapter"
Cohesion: 0.06
Nodes (10): _child_env(), PrimeAgentAdapter, _spec(), TestAdapterMetadata, TestBinaryResolution, TestCommandConstruction, TestFailClosed, TestPreflight (+2 more)

### Community 156 - "FreeBuffAgent"
Cohesion: 0.07
Nodes (24): free_nvidia_models(), FreeBuffAgent, _nvidia_api_key(), is_rate_limit_exempt(), _rate_limit_exempt_key_ids(), _fb_models(), TestFreeBuffAgent, test_fb_models_embedded_uses_agent() (+16 more)

### Community 157 - "_cfg"
Cohesion: 0.06
Nodes (5): _cfg(), TestCatalogCompleteness, TestCatalogFable5, TestCatalogMythos5, TestCatalogOpus48

### Community 158 - "E2BSandboxSession"
Cohesion: 0.13
Nodes (5): MCPUnavailableError, ★5 — Sandboxed Agent Execution (E2B / Docker micro-VM) [P1] [CHM] ✅ Delivered 2026-07-04, E2BSandboxSession, _resolve_sandbox_path(), test_session_open_raises_when_sdk_missing()

### Community 159 - "AutonomyTracker"
Cohesion: 0.07
Nodes (4): AutonomyCounter, AutonomySnapshot, AutonomyTracker, TestAutonomyKPIs

### Community 160 - "test_trend_scoping.py"
Cohesion: 0.09
Nodes (32): _company_attr(), company_stack_tags(), extract_stack_tags(), fan_out_trend(), fan_out_trends(), is_code_change_trend(), map_trend_to_company_task(), score_trend_for_company() (+24 more)

### Community 161 - "AgentSessionStore"
Cohesion: 0.10
Nodes (5): AgentSession, AgentSessionStore, _now(), TestAgentSessionStorePersistence, test_session_repo_context_is_sticky()

### Community 162 - "SamAgent"
Cohesion: 0.05
Nodes (27): SamAgent, SamConversation, store(), test_feed_failure_is_reported_not_raised(), test_fix_request_queues_runnable_tasks(), test_no_fixable_alerts(), test_read_request_summarises_without_creating_tasks(), test_repeat_fix_request_does_not_duplicate() (+19 more)

### Community 163 - "WorkspaceTools"
Cohesion: 0.02
Nodes (88): _register_builtin_tools(), Adding a new tool, CLAUDE.md — agent/, Security surface, Skills worth invoking here, Testing, What this package does, WorkspaceTools (+80 more)

### Community 164 - "user_research_skill.py"
Cohesion: 0.08
Nodes (19): auto_register(), _classify_sentiment(), _extract_keywords(), QualAnalysis, QualQuote, QualTheme, QuantAnalysis, QuantSegment (+11 more)

### Community 165 - "test_brain_patch_service_token.py"
Cohesion: 0.18
Nodes (9): clean_store(), _clear_overrides(), _make_client_with_user(), test_patch_brain_accepts_valid_service_token(), test_patch_brain_admin_user_path_unchanged(), test_patch_brain_non_admin_user_still_gets_403(), test_patch_brain_rejects_invalid_service_token(), test_patch_brain_rejects_no_auth_no_service_token() (+1 more)

### Community 166 - "portfolio_api.py"
Cohesion: 0.09
Nodes (14): add_initiative(), AllocationOut, BoardOut, get_board(), InitiativeIn, InitiativeOut, _materialize_and_log(), materialize_portfolio() (+6 more)

### Community 167 - "test_llm_router_disabled.py"
Cohesion: 0.09
Nodes (22): auto_disable(), _billing_signals(), describe(), disabled_provider_ids(), is_unfixable(), disabled_providers(), _ok(), _request() (+14 more)

### Community 168 - "gsap.min.js"
Cohesion: 0.05
Nodes (36): ae(), Context(), Db(), Eb(), fb(), Hc(), ia(), Ic() (+28 more)

### Community 169 - "CompanyScreen.jsx"
Cohesion: 0.09
Nodes (28): consultExecutives(), delegateSeoFindings(), getSeoAudit(), listExecutives(), listSeoAudits(), EXECS, Card(), COMPANY_ID_KEY (+20 more)

### Community 170 - "test_verification_strategies.py"
Cohesion: 0.06
Nodes (29): cross_verify(), race(), _score_attempt(), _score_result(), touches_risky_module(), Agent Autonomy Roadmap, Design constraints honored, New environment variables (+21 more)

### Community 171 - "test_sam_livekit.py"
Cohesion: 0.05
Nodes (19): auth_headers(), livekit_env(), no_livekit_env(), _normalize_dockerfile(), test_config_configured(), test_config_llm_override(), test_config_unconfigured_reports_missing(), test_dockerfile_ships_voice_package() (+11 more)

### Community 172 - "test_spec_store.py"
Cohesion: 0.07
Nodes (27): build_spec_router(), approve_spec(), _decide(), get_spec_artifact(), list_spec_artifacts(), reject_spec(), _db(), get_spec() (+19 more)

### Community 173 - "4. Threats"
Cohesion: 0.11
Nodes (18): 1. What makes this system different from a normal web app, 2. Assets, 3. Trust boundaries, 4. Threats, 5. Why the engine fails open but approvals fail closed, 6. Honest limits, 7. Priority follow-ups, T10 — Supply-chain compromise via base image (+10 more)

### Community 174 - "local_controller.py"
Cohesion: 0.13
Nodes (18): _bin_exists(), _default_agency_url(), _default_machine_id_file(), _env_int(), _get_or_create_machine_id(), _http_json(), _log(), _log_path() (+10 more)

### Community 175 - "test_telegram_observe.py"
Cohesion: 0.29
Nodes (6): _run(), test_cmd_autonomy_degrades_gracefully(), test_cmd_autonomy_formats_brain_and_readiness(), fake_get(), test_cmd_loops_formats_readiness_and_costliest(), test_cmd_loops_reports_registry_error()

### Community 176 - "SpecEntry"
Cohesion: 0.12
Nodes (8): build_block(), read_entries(), spec_path(), SpecEntry, write_entries(), TestPersistence, TestPromptBlock, TestWorkspaceBinding

### Community 177 - "QuickNote"
Cohesion: 0.18
Nodes (3): _now(), QuickNote, _make_note()

### Community 178 - "PatternConsolidation"
Cohesion: 0.08
Nodes (5): DreamMemory, PatternConsolidation, _make_memory(), TestDreamMemory, TestPatternConsolidation

### Community 179 - "test_daily_digest.py"
Cohesion: 0.06
Nodes (20): aggregate_last_24h(), build_daily_digest(), compute_cutoff(), DigestPayload, DigestSummary, format_digest_markdown(), _md_escape(), _now_utc() (+12 more)

### Community 180 - "WorkflowEngine"
Cohesion: 0.07
Nodes (22): approve(), build(), cancel(), _engine(), get_agent_team(), get_artifact_content(), get_events(), get_run() (+14 more)

### Community 181 - "UserRole"
Cohesion: 0.13
Nodes (19): Finding A — `list_for_user` Mongo query diverges from the `_can_read` policy, UserRole, _can_read(), _can_write(), SecretRecord, SecretScope, SecretsStore, SecretUpdateRequest (+11 more)

### Community 182 - "FeatureMaturity"
Cohesion: 0.05
Nodes (16): 18. Feature Maturity & Support Matrix, check_feature(), get_feature(), list_features(), FeatureMaturity, FeatureUnavailableError, get_feature_matrix(), reset_feature_matrix() (+8 more)

### Community 183 - "test_response_cache.py"
Cohesion: 0.11
Nodes (35): _cache_key(), cache_stats(), clear_cache(), get_cached(), is_cacheable(), put_cached(), _cache(), test_cache_evicts_least_recently_used() (+27 more)

### Community 184 - "test_mcp_governance.py"
Cohesion: 0.10
Nodes (19): get_audit_log(), _call(), _engine(), test_a_blocked_call_is_audited_as_blocked(), test_a_broken_policy_engine_fails_open_on_the_mcp_surface(), test_a_failing_tool_is_audited_as_an_error(), test_a_spoofed_identity_cannot_get_past_a_baseline_rule(), test_allowed_calls_still_execute_and_return_their_result() (+11 more)

### Community 185 - "BrainFailoverExhausted"
Cohesion: 0.06
Nodes (14): BrainFailoverExhausted, _FM, _P, test_attempted_providers_are_named_not_denied(), test_nothing_attempted_still_reports_nothing_configured(), test_recorded_failures_take_precedence(), test_reserve_excludes_already_tried_paid_providers(), test_reserve_ignores_a_cooling_paid_provider() (+6 more)

### Community 186 - "test_video_transcript.py"
Cohesion: 0.05
Nodes (18): test_bulk_workflow_stages_the_transcript_module(), test_caption_tracks_and_title_degrade_gracefully(), test_extract_player_response_handles_nested_braces(), test_extract_player_response_ignores_braces_inside_strings(), test_fetch_transcript_declines_non_video_urls_without_network(), test_fetch_transcript_labels_auto_generated_captions(), fake_get(), test_fetch_transcript_returns_empty_when_the_page_is_unavailable() (+10 more)

### Community 187 - "TestSelfHealingInfrastructureClassification"
Cohesion: 0.05
Nodes (8): filter_safe_tools(), get_tool_annotations(), ToolAnnotations, TestFilterSafeTools, TestGetToolAnnotations, TestSelfHealingInfrastructureClassification, TestSelfHealingInfrastructureNoCodeFix, TestToolAnnotationsIsSafeToExplore

### Community 188 - "sam_tools.py"
Cohesion: 0.09
Nodes (30): delegate_task(), outward_facing_tags(), run_triage(), _approve(), _brief(), _control_needs_confirm(), _ControlKey, _ctl_summary() (+22 more)

### Community 189 - "test_anthropic_router.py"
Cohesion: 0.08
Nodes (8): _make_anthropic_provider(), _payload(), TestAnthropicPayloadExtendedThinking, TestAnthropicPayloadModelGuards, TestAnthropicPayloadPromptCaching, TestAnthropicToOpenAICacheUsage, TestAuthHeadersExtendedThinking, TestAuthHeadersPromptCaching

### Community 190 - "TaskDetailPanel"
Cohesion: 0.07
Nodes (43): Key files, addTaskComment(), approveTaskCheckpoint(), approveTaskExecution(), clarifyTask(), createSprint(), escalateTask(), fetchSprints() (+35 more)

### Community 191 - "SetupChecker"
Cohesion: 0.06
Nodes (5): main(), OllamaManager, OsDetector, ScriptRunner, SetupChecker

### Community 192 - "ManagedAgentDreams"
Cohesion: 0.06
Nodes (5): Dream, ManagedAgentDreams, SessionMemory, TestDream, TestManagedAgentDreams

### Community 193 - "PromptCacheManager"
Cohesion: 0.06
Nodes (5): CacheEntry, CacheStats, get_prompt_cache(), PromptCacheManager, TestPromptCacheIntegration

### Community 194 - "analyze_page"
Cohesion: 0.12
Nodes (8): analyze_page(), fire(), _visible_text(), codes(), TestBadPage, TestCleanPage, TestNewChecks, TestSpecificChecks

### Community 195 - "test_e2b_data_flow.py"
Cohesion: 0.06
Nodes (20): fake_sandbox(), _FakeAsyncSandboxClass, _FakeCmdResult, _FakeCommands, _FakeFiles, _FakeSandbox, test_apply_diff_resolves_under_workdir(), test_apply_diff_then_read_sees_the_write() (+12 more)

### Community 196 - "WorkflowRun"
Cohesion: 0.07
Nodes (9): _make_engine(), TestAbortOnFailure, _test(), _tracking_run_single(), TestPhaseSequence, _extract_slices_from_plan(), _now(), Phase (+1 more)

### Community 197 - "AdaptiveHalter"
Cohesion: 0.09
Nodes (3): AdaptiveHalter, TestAdaptiveHalter, TestLoopAdaptiveHalterIntegration

### Community 198 - "CEOLedger"
Cohesion: 0.08
Nodes (10): Attempt, _backend(), CEOLedger, GoalRecord, _now(), _selection_timeout_ms(), _ledger(), test_recent_decisions_carries_verdict() (+2 more)

### Community 199 - "portfolio_intelligence.py"
Cohesion: 0.06
Nodes (28): generate_backlog_retro(), generate_standup(), InitiativeStatus, _bug_scores(), _clean(), _default_repo(), _env_github_token(), estimate_job_size() (+20 more)

### Community 200 - "KnowledgeGraph"
Cohesion: 0.08
Nodes (4): KnowledgeGraph, KnowledgeNode, TestKnowledgeGraph, TestKnowledgeNode

### Community 201 - "PortfolioManager"
Cohesion: 0.06
Nodes (8): PortfolioManager, PortfolioMetrics, TestCapacityAllocation, TestMetrics, TestPortfolioManagerCrud, TestPrioritization, TestRoadmap, TestRollup

### Community 202 - "OllamaCircuitBreaker"
Cohesion: 0.08
Nodes (25): _Circuit, _enabled(), _failure_threshold(), get_circuit_breaker(), OllamaCircuitBreaker, _recovery_timeout(), reset_circuit_breaker(), clean_breaker() (+17 more)

### Community 203 - "v4_api.py"
Cohesion: 0.11
Nodes (16): _load_improvement_state(), _run_scan_background(), _save_improvement_state(), v4_improvements(), v4_improvements_resolve(), v4_improvements_scan(), v4_quick_notes(), v4_quick_notes_submit() (+8 more)

### Community 204 - "test_hermes_in_process.py"
Cohesion: 0.06
Nodes (12): _check_auth(), health(), run_task(), TaskIn, _free_port(), hermes_enabled(), _NullDispatcher, _NullRuntimeManager (+4 more)

### Community 205 - "SyntheticDataPipeline"
Cohesion: 0.07
Nodes (5): get_synthetic_pipeline(), SyntheticDataPipeline, TrainingSample, TestSyntheticDataPipeline, TestTrainingSample

### Community 206 - "TestChatHandlersSessionId"
Cohesion: 0.07
Nodes (6): TestAnthropicCompatSessionId, TestChatHandlersSessionId, TestEmitChatObservationForwardsSessionId, TestHeaderPrecedence, TestProxySessionId, TestSessionIdDefaultsToNone

### Community 207 - "test_features_api.py"
Cohesion: 0.05
Nodes (3): _auth_override(), client(), _fake_auth()

### Community 208 - "test_telegram_webhook.py"
Cohesion: 0.05
Nodes (10): _AsyncioWithSleep, client(), _patch_bot_sleep(), test_process_webhook_update_never_raises(), test_process_webhook_update_routes_callback_and_message(), test_register_webhook_posts_secret_in_body_not_url(), test_register_webhook_retries_transient_dns_failure(), _no_sleep() (+2 more)

### Community 209 - "register_webui"
Cohesion: 0.06
Nodes (36): get_local_model(), allow_paid_brain(), get_router(), test_get_router_returns_same_instance(), run_command(), _admin_out(), _anthropic_chat_payload(), _anthropic_text() (+28 more)

### Community 211 - "test_operational_incidents.py"
Cohesion: 0.06
Nodes (22): normalise(), signature_for(), summarise_phases(), test_a_scheduled_diagnosis_is_held_until_it_completes(), _drive(), _work(), test_a_single_occurrence_files_nothing(), test_an_unfinished_phase_is_identified_as_the_stuck_call() (+14 more)

### Community 212 - "test_audit.py"
Cohesion: 0.07
Nodes (16): AuditMessage, AuditSession, create_session(), delete_session(), get_session(), list_sessions(), test_add_message(), test_clear() (+8 more)

### Community 213 - "llm_providers.py"
Cohesion: 0.12
Nodes (25): _anthropic_headers(), _anthropic_payload(), _anthropic_response_text(), _auth_headers(), chat_completion_text(), _do(), list_openai_models(), LlmProviderConfig (+17 more)

### Community 214 - "NIMConnectionPool"
Cohesion: 0.06
Nodes (12): [5.0.0], Changed, Removed, Security, [5.0.0], Changed, Removed, Security (+4 more)

### Community 215 - "Platform Guide — the full tour"
Cohesion: 0.06
Nodes (34): Architecture, Backfilling existing issues, Cloud deployment (Render + GitHub Pages), Configuration reference, Development, Free-first model routing, HITL approval gates — you stay in control, How it works — the 5-minute version (+26 more)

### Community 216 - "Killer TODO Roadmap — local-llm-server"
Cohesion: 0.25
Nodes (7): G1 — Per-Model Cost and Latency Attribution [P1] [NVD], G2 — Request Replay for Debugging [P2] [CBF], Implementation Notes, Killer TODO Roadmap — local-llm-server, Priority Summary, SECTION G — Observability (NVD / CHM), Source Projects Referenced

### Community 217 - "resolve_active_brain"
Cohesion: 0.02
Nodes (73): _migrate_brain_to_safe_default(), N1. Activate the reliability spine — wire the watchdog, schedule the digest ⬜  (size: M, risk: low), BrainResolution, BrainConfigPatch, get_brain_config(), get_brain_config_store(), set_brain_config(), get_active_brain_sync() (+65 more)

### Community 218 - "metrics.py"
Cohesion: 0.09
Nodes (9): _Counter, _escape(), _Gauge, _Histogram, _labels(), MetricsRegistry, _render_labels(), _render_value() (+1 more)

### Community 219 - "TestSchedulerStore"
Cohesion: 0.04
Nodes (6): _MemCollection, _MemCursor, _MemDB, _MemDeleteResult, SchedulerStore, TestSchedulerStore

### Community 220 - "test_classify_dependabot_update.py"
Cohesion: 0.07
Nodes (14): classify(), classify_pull_request(), compare_versions(), _component(), is_auto_mergeable(), main(), parse_version(), _commit() (+6 more)

### Community 221 - "test_brain_availability_doctor.py"
Cohesion: 0.11
Nodes (21): brain_availability_summary(), _doctor(), _P, _patch_providers(), _sup(), test_a_brain_outage_pauses_instead_of_abandoning(), test_all_healthy_reports_every_provider_usable(), test_disabled_and_cooling_are_reported_separately() (+13 more)

### Community 222 - "ContextWindowManager"
Cohesion: 0.09
Nodes (4): ContextWindowManager, TruncationResult, TestContextWindowIntegration, TestContextWindowManager

### Community 223 - "_cfg"
Cohesion: 0.08
Nodes (6): _cfg(), _cost_table(), TestClaudeMdGroqReference, TestGemini3xCatalog, TestGemini3xCostTracker, TestGroqNewModelsCatalog

### Community 224 - "_run"
Cohesion: 0.06
Nodes (9): _run(), _StubMessage(), TestBigPastePolicy, TestClassifySimpleRouting, fake_send(), TestHandlePaste, TestHandleRedirect, TestPlainTextRouting (+1 more)

### Community 225 - "Implementation Plan — DB-persisted, UI-switchable Brain (no redeploy)"
Cohesion: 0.15
Nodes (12): 0. Why this exists (root cause this fixes), 1. Hard constraints (from the owner), 2. Provider strategy (the recommendation), 3. Architecture, 3a. Store — `services/brain_config_store.py` (new), 3b. Call-time resolution — `agent/loop.py`, 3c. Admin API — `backend/server.py`, 3d. UI — `webui/frontend/src/pages` (+ `webui/router.py` / `providers.py`) (+4 more)

### Community 226 - "test_sam_orchestrator.py"
Cohesion: 0.07
Nodes (21): _as(), clean_overrides(), store(), test_admin_delegate_queues_one_task_and_dedupes(), test_avatar_endpoint_follows_the_toggle(), test_brief_reports_live_state_without_llm(), test_chat_namespaces_session_and_passes_role(), test_delegate_beats_alert_keywords() (+13 more)

### Community 227 - "Persistent Memory System"
Cohesion: 0.05
Nodes (41): 1. **Semantic Memory Categorization**, 1. **Use Appropriate Scopes**, 2. **Prioritize Effectively**, 2. **Scope-Based Auto-Loading**, 3. **Priority-Based Retrieval**, 3. **Use Semantic Categories**, 4. **Cross-Tool Compatibility**, 4. **Tag Liberally** (+33 more)

### Community 228 - "test_task_run_lease.py"
Cohesion: 0.07
Nodes (19): claim_task_run(), release_task_run(), _supports_lease(), _always_free(), _DuplicateKeyError, _FakeMongoDb, _FakeMongoLeases, _mongo_store() (+11 more)

### Community 229 - "get_scheduler"
Cohesion: 0.07
Nodes (19): _anon_tick_allowed(), autonomy_tick(), _cron_secret_ok(), legacy_scheduler_delete(), legacy_scheduler_get(), legacy_scheduler_list(), legacy_scheduler_trigger(), _produce_scheduler_jobs() (+11 more)

### Community 230 - "_llm_catalog"
Cohesion: 0.08
Nodes (7): _cost_src(), _llm_catalog(), _routing_candidates(), TestCatalogTotals, TestDashScopeCatalogEntries, TestGLMCatalogEntries, TestMoonshotCatalogEntries

### Community 231 - "ScheduleStore"
Cohesion: 0.10
Nodes (10): _backend(), _json_default(), ScheduleStore, test_schedule_store_sqlite_survives_restart(), test_schedule_store_works_with_sqlite_backend(), test_store_falls_back_to_memory_without_mongo(), _install_pymongo_stub(), _restore_pymongo() (+2 more)

### Community 232 - "TrendWatcher"
Cohesion: 0.15
Nodes (6): TrendAlert, TrendWatcher, test_cache_round_trip(), test_dispatch_injects_high_relevance(), test_dispatch_skips_low_relevance(), tmp_watcher()

### Community 233 - "looks_like_secret_file"
Cohesion: 0.08
Nodes (26): N3. Real CI-failure autofix — close the "Agency: cannot fix tests" loop (issue #398) ✅  (size: L, risk: medium), _extract_mentioned_paths(), _read_grounding_files(), is_doc_only_boilerplate(), looks_like_secret_file(), test_bare_dotenv_rejected(), test_credentials_content_rejected_regardless_of_filename(), test_doc_only_pr_rejected() (+18 more)

### Community 234 - "Agent: Judge (Release / QA Gate)"
Cohesion: 0.25
Nodes (7): Activation, Agent: Judge (Release / QA Gate), Enforcement, Output, Responsibilities, Role, Verdict Meanings

### Community 235 - "clear_cooldowns"
Cohesion: 0.07
Nodes (22): clear_cooldowns(), _dead_model_key(), _is_model_dead(), is_provider_on_cooldown(), mark_provider_failed(), clear_all_locks(), reset_cooldowns(), _failing_primary() (+14 more)

### Community 236 - "test_agent_tool_governance.py"
Cohesion: 0.06
Nodes (26): reset_approval_store(), reset_audit_log(), reset_policy_engine(), _drive(), _enforce(), governance_on(), isolated_governance(), _observations() (+18 more)

### Community 238 - "Workflow"
Cohesion: 0.06
Nodes (5): Task, TaskStatus, Workflow, dfs(), WorkflowEngine

### Community 239 - "validate"
Cohesion: 0.06
Nodes (23): apply_review_gate(), _check_constitution_echo(), _check_files_exist(), _check_grounding(), _check_hedges(), _check_prior_art(), _check_project_identity(), _check_prose_paths() (+15 more)

### Community 240 - "discover_models"
Cohesion: 0.15
Nodes (7): _served_models(), cached_models(), discover_models(), _fresh_entry(), _models_url(), _parse_ids(), _remember()

### Community 241 - "test_schedule_growth_invariants.py"
Cohesion: 0.05
Nodes (11): _FakeMongoStore, _FakePersistence, _FakeSQLiteStore, test_agency_schedules_use_stable_names(), test_dispatcher_honors_concurrency_env(), test_force_cleanup_removes_stale_unfired_run_once(), test_health_reports_schedule_count(), test_incident_fix_tests_exist() (+3 more)

### Community 242 - "checkpoint_agent_state"
Cohesion: 0.10
Nodes (14): checkpoint_agent_state(), _checkpointing_enabled(), cleanup_checkpoints(), _get_checkpoint_store(), restore_agent_state(), serve_spa(), Changelog, Changelog (+6 more)

### Community 244 - "AgileManager"
Cohesion: 0.09
Nodes (4): AgileManager, TestGenerateStandup, TestPlanNextSprint, TestAgileManager

### Community 245 - "Added"
Cohesion: 0.08
Nodes (13): _domain_matches(), _parse_domain_list(), Added, Added, TestCandidatesAreDeclaredInLlmCatalog, _hardcoded_candidates(), TestTheCatalogueIsWhatActuallyRuns, TestTheCopiesMayNotDriftFurther (+5 more)

### Community 246 - "AdminScreen.jsx"
Cohesion: 0.22
Nodes (14): changeUserRole(), createApiKey(), deleteApiKey(), deleteCompany(), setUserOnboarding(), ActivationPanel(), AdminScreen(), CompaniesPanel() (+6 more)

### Community 247 - "test_daily_2026_06_04.py"
Cohesion: 0.07
Nodes (27): _content_block_to_text(), _messages_to_openai(), _tools_to_openai(), is_anthropic_model(), _opus_model(), test_is_anthropic_model(), _content_block_to_text(), _fresh_router() (+19 more)

### Community 248 - "test_background_services.py"
Cohesion: 0.07
Nodes (16): run_background_in_web(), _StubDispatcher, _StubRegistry, _StubRuntimeManager, _StubScheduler, _StubTaskAutomation, test_hermes_readiness_wait_gives_up_within_its_budget(), test_hermes_startup_timeout_is_well_under_renders_health_check_window() (+8 more)

### Community 249 - ".session_id"
Cohesion: 0.07
Nodes (29): AcceptedJob, AgentJobEnvelope, CompletedJob, DirectChatState, FailedJob, RunningJob, AgentEventModel, AgentJobModel (+21 more)

### Community 250 - "GuardrailEngine"
Cohesion: 0.09
Nodes (4): GuardrailEngine, GuardResult, TestGuardrailEngine, TestGuardResult

### Community 251 - "Path"
Cohesion: 0.09
Nodes (8): _isolate_env(), TestDownloadStatus, TestIsProcessAlive, TestReadPidFile, TestSuperviseLoopGiveUp, TestSupervisorStateAtomic, TestSupervisorTick, _write_log()

### Community 253 - "test_agents.py"
Cohesion: 0.11
Nodes (11): AgentProfile, _catalog_provider(), _get_defaults(), load_all_profiles(), make_architect_profile(), make_coder_profile(), make_reviewer_profile(), make_scout_profile() (+3 more)

### Community 254 - "app_settings.py"
Cohesion: 0.15
Nodes (11): all_settings(), _as_bool(), _as_int(), ephemeral_ttl_hours_cached(), get_setting(), _maybe_schedule_refresh(), onboarding_gate_enabled_cached(), refresh_cache() (+3 more)

### Community 255 - "test_provider_render_env.py"
Cohesion: 0.09
Nodes (15): provider_env_names(), RenderEnvError, update_service_env_var(), _enable_render(), _FakeClient, _FakeResp, test_endpoint_success_writes_key(), test_endpoint_unknown_provider_404() (+7 more)

### Community 256 - "KeyPool"
Cohesion: 0.06
Nodes (8): _digest(), KeyPool, _KeyState, _PoolState, TestAllCooling, TestExhaustedPoolDoesNotReusePrimary, TestRotation, TestSnapshotLeaksNothing

### Community 257 - "test_control_plane_api.py"
Cohesion: 0.06
Nodes (11): set_scheduler(), _FakeStore, mock_runtime_manager(), scheduler(), schedules_client(), test_get_scheduler_raises_before_set(), test_hydrate_rehydrates_unfired_run_once_jobs(), test_hydrate_skips_duplicate_by_job_id() (+3 more)

### Community 258 - "TestCatalogFable51"
Cohesion: 0.09
Nodes (5): _cfg(), _cost_table(), TestAnthropicReasoningTokenExtraction, TestCatalogFable51, TestCostTrackerFable

### Community 259 - "test_daily_automation_2026_09_29.py"
Cohesion: 0.06
Nodes (6): llm_models(), models_yaml(), TestAerolinkRolePresetsUpdated, TestAnthropicRolePresetsUpdated, TestBrainConfigMirrorsYaml, TestSonnet55InLLMModels

### Community 260 - "tasks/models.py"
Cohesion: 0.05
Nodes (32): ApprovalCheckpoint, ApprovalRequest, ClarifyRequest, CommentAddRequest, ExecutionApprovalRequest, ExecutionLogEntry, FollowUpRequest, TaskComment (+24 more)

### Community 261 - "control_registry.py"
Cohesion: 0.10
Nodes (13): Adding a control, coerce(), _coerce_choice(), _coerce_number(), _coerce_text(), _coerce_toggle(), controls_by_group(), ControlGroup (+5 more)

### Community 262 - "ImprovementLoop"
Cohesion: 0.04
Nodes (56): DetectedIssue, get_improvement_loop(), ImprovementLoop, ImprovementLoopState, IssueCategory, IssueSeverity, _now(), The monitoring loop (+48 more)

### Community 263 - "test_persistent_memory.py"
Cohesion: 0.06
Nodes (17): memory_store(), temp_db(), test_access_count_tracking(), test_auto_load_global_memories(), test_auto_load_priority_ordering(), test_auto_load_with_workspace(), test_bulk_import(), test_delete_memory() (+9 more)

### Community 265 - "test_ceo_router.py"
Cohesion: 0.10
Nodes (23): reset_ceo_ledger(), reset_ceo_supervisor(), set_ceo_supervisor(), ledger(), _make_app(), _seed(), _supervisor(), test_admin_can_force_a_redrive() (+15 more)

### Community 266 - "test_agent_api.py"
Cohesion: 0.14
Nodes (10): test_admin_api_login_status_and_control(), test_admin_api_user_crud(), test_agent_run_returns_structured_failure(), test_agent_session_endpoints_require_and_return_state(), fake_run(), test_agent_session_run_redacts_internal_exception_details(), test_agent_session_run_reuses_bearer_key_for_same_origin_provider(), test_openai_chat_completions_exact_output_short_circuits() (+2 more)

### Community 267 - "Any"
Cohesion: 0.07
Nodes (9): _NoOpSpan, _NoOpTracer, otel_middleware_factory(), otel_status_error(), otel_status_ok(), traced(), decorator(), wrapper() (+1 more)

### Community 268 - "LocalBrainStore"
Cohesion: 0.09
Nodes (8): LocalBrainStore, _now_iso(), store(), test_lease_ttl_expires_after_grace(), test_router_3_endpoints_are_registered(), test_router_endpoints_require_service_token(), test_toggle_clears_existing_lease(), test_v1_models_round_trip_through_json()

### Community 270 - "TestAuthAndTaskOwnership"
Cohesion: 0.05
Nodes (5): TestAuthAndTaskOwnership, TestChatCommercialFallbackApproval, TestProviderConfiguration, TestRoutingPolicyDefaults, TestRuntimeRemoteControl

### Community 272 - "SeoFixRequest"
Cohesion: 0.12
Nodes (9): run_seo_fixes(), _workspace_root(), SeoFixRequest, SeoFixResult, run_fixes(), repo(), TestApply, TestDryRun (+1 more)

### Community 273 - "REWRITE_PLAN.md — Phased Migration Strategy"
Cohesion: 0.06
Nodes (35): Already completed (pre-migration fixes), Current Status, Inventory of suspected dead code, Migration Safety Checklist, Phase 1: Foundation (Weeks 1-2), Phase 2: Provider Abstraction (Weeks 3-4), Phase 3: Auth Consolidation (Week 5), Phase 4: Scheduler Redesign (Week 6) (+27 more)

### Community 274 - "analyze"
Cohesion: 0.05
Nodes (17): Analysis, analyze(), _classify(), _failure_table(), main(), extract_failures(), is_node_id(), main() (+9 more)

### Community 275 - "_cfg"
Cohesion: 0.09
Nodes (5): _cfg(), _cost_table(), TestGemini25ProCatalog, TestGeminiCostTrackerEntries, TestGoogleProviderPresetConsistency

### Community 276 - "test_autonomy_triage.py"
Cohesion: 0.09
Nodes (28): _is_trend_code_change(), _norm_title(), _open_titles(), triage_gated_tasks(), _triage_may_decide(), TriageResult, _was_auto_promoted(), _is_outward_facing() (+20 more)

### Community 277 - "WorkflowTransition"
Cohesion: 0.33
Nodes (4): _append_transition(), WorkflowTransition, test_workflow_transition_defaults(), test_workflow_transition_serialises()

### Community 278 - "set_task_store"
Cohesion: 0.10
Nodes (21): quick_notes_submit(), _QuickNoteBody, set_task_store(), task_store(), _inmem_store(), test_quick_note_creates_task(), test_quick_note_url_only_creates_task(), store() (+13 more)

### Community 279 - "test_sam_voice.py"
Cohesion: 0.05
Nodes (18): get_sam(), sam_with_mocks(), test_build_context_returns_dict(), test_call_llm_times_out_and_falls_back(), test_conversation_add_turn(), test_conversation_history_capped(), test_fallback_response_generic(), test_fallback_response_status() (+10 more)

### Community 280 - "test_ephemeral_reaper.py"
Cohesion: 0.09
Nodes (15): _as_aware_utc(), _company_alive(), _company_id_for_agent(), _env_float(), ephemeral_reaper_loop(), reap_expired_companies(), reap_orphaned_agents(), _company() (+7 more)

### Community 281 - "emit_chat_observation"
Cohesion: 0.04
Nodes (40): _evidence(), MongoLessonStore, recent_lessons_block(), record_step_failures(), Added, Session Log, Added, Hard stops on autonomous work (+32 more)

### Community 282 - "monitor_lib.py"
Cohesion: 0.12
Nodes (26): build_parser(), cmd_autostart_install(), cmd_status(), cmd_supervise(), cmd_wait(), _configure_logging(), main(), _start_colibri_fn() (+18 more)

### Community 283 - "seo_api.py"
Cohesion: 0.05
Nodes (38): build_seo_roadmap(), _expire_stale_pending_report(), get_seo_audit(), list_seo_audits(), plan_seo_sprint(), _run_audit_in_background(), run_seo_audit(), run_seo_pipeline() (+30 more)

### Community 285 - "router_factory"
Cohesion: 0.16
Nodes (13): _big_request(), _ok(), router_factory(), build(), test_a_request_within_the_budget_is_left_alone(), handler(), test_a_tpm_413_rotates_keys_before_leaving_the_provider(), handler() (+5 more)

### Community 286 - "agent_runtime.py"
Cohesion: 0.06
Nodes (29): _active_cloud_provider(), _candidate_ollama_bases(), _chat(), chat_completions(), _chat_with_ollama(), _chat_with_openai_compat(), ChatRequest, ChatResponse (+21 more)

### Community 287 - "seo_report_pdf.py"
Cohesion: 0.09
Nodes (17): compute_pressure(), loss_share_from_pressure(), _appendix_full_findings(), _appendix_worst_pages(), _appendix_wsjf_roadmap(), _cell(), _cover_page(), _executive_summary() (+9 more)

### Community 288 - "test_chat_mode_regressions.py"
Cohesion: 0.11
Nodes (20): _auth_headers(), test_agent_status_endpoint_reports_live_progress_and_tool_calls(), test_agent_stream_endpoint_emits_server_sent_events(), test_chat_send_emits_langfuse_observation_for_direct_chat(), test_chat_send_keeps_complex_prompt_on_direct_path_when_agent_mode_is_off(), test_chat_send_keeps_explanatory_github_pr_guidance_on_direct_path(), test_chat_send_keeps_general_docker_explanation_on_direct_path_when_no_repo_action_is_requested(), test_chat_send_persists_agent_handoff_metadata_in_session_history() (+12 more)

### Community 289 - "_Collection"
Cohesion: 0.11
Nodes (8): _apply_update(), _Collection, _DeleteResult, _InsertResult, _match(), _new_id(), _now_iso(), _UpdateResult

### Community 290 - "WorkflowRun"
Cohesion: 0.10
Nodes (14): WorkflowRun, TestOrchestratorCheckpointStore, _company(), _FakeStore, orch(), test_record_consent_noop_for_non_gate_decision(), test_record_consent_noop_without_decision(), test_record_consent_persists_for_first_merge() (+6 more)

### Community 291 - "Task"
Cohesion: 0.03
Nodes (40): Added, Added, TaskAutomationService, goal_ancestry_block(), inherit_goal(), Task, _escape_md_v1(), _isolate_brain_data_layer() (+32 more)

### Community 292 - "test_live_server.py"
Cohesion: 0.21
Nodes (21): check(), main(), ok(), req(), skip(), Suite, test_activation_api(), test_activity_and_stats() (+13 more)

### Community 293 - "test_all_providers_discovery.py"
Cohesion: 0.17
Nodes (30): _get(), _router(), test_anthropic_discovery(), test_anthropic_no_base_url_required(), test_bedrock_discovery(), test_bedrock_health_check(), test_cerebras_discovery(), test_deepseek_discovery() (+22 more)

### Community 294 - "test_purge_backlog.py"
Cohesion: 0.08
Nodes (13): FakeTaskStore, _run_boot_purge(), test_boot_purge_failure_does_not_store_marker(), test_boot_purge_noop_without_env(), test_boot_purge_partial_failure_does_not_store_marker(), _partial(), test_boot_purge_runs_once_for_new_nonce(), test_boot_purge_skips_already_executed_nonce() (+5 more)

### Community 295 - "CheckpointStore"
Cohesion: 0.12
Nodes (4): Checkpoint, CheckpointStore, TestCheckpointModel, TestCheckpointStore

### Community 296 - "OutputFilter"
Cohesion: 0.08
Nodes (16): OutputFilter, _enable_filter(), test_curl_large_response(), test_disabled_passthrough(), test_docker_build_large(), test_empty_input(), test_git_log_large(), test_git_status_small() (+8 more)

### Community 297 - "PlaybookLibrary"
Cohesion: 0.10
Nodes (16): _now(), Playbook, PlaybookLibrary, PlaybookRun, PlaybookStep, test_as_dict(), test_delete(), test_delete_nonexistent_returns_false() (+8 more)

### Community 298 - "TestHarnessAdapter"
Cohesion: 0.07
Nodes (8): get_harness_adapter(), harness_active(), harness_catalog(), _startup_reliability_hooks(), get_harness_registry(), start_orchestrator_supervisor(), TestHarnessAdapter, TestHarnessRegistry

### Community 299 - "⚙️ Operations Manager Agent"
Cohesion: 0.06
Nodes (33): Analyze, Balanced Scorecard Approach, BCP Framework — Key Components, Bottleneck Analysis (Theory of Constraints), Business Continuity Planning, Capacity Planning Model, Continuous Improvement Cadence, Control (+25 more)

### Community 300 - "SeoFixer"
Cohesion: 0.14
Nodes (6): _humanize_filename(), SeoFixer, repl(), repl(), _unified_diff(), TestHumanize

### Community 301 - ".failed"
Cohesion: 0.11
Nodes (16): 1. Think Before Coding, 2. Simplicity First, 3. Surgical Changes, 4. Goal-Driven Execution, Integration points in this repo, Karpathy Guidelines Skill, Agent job lifecycle, API (+8 more)

### Community 302 - "NEXT_ACTION — updated 2026-10-04"
Cohesion: 0.29
Nodes (6): Agent code work ships 2026-10-04 — branch `fix/agent-work-ships`, Bedrock live 2026-10-04, Last session (2026-10-04, daily automation), NEXT_ACTION — updated 2026-10-04, Open items for next daily run, Portfolio duplicate loop 2026-10-04 — branch `fix/portfolio-duplicate-loop`

### Community 303 - "skill_bindings.py"
Cohesion: 0.09
Nodes (8): 3. Dynamic, expandable roles (open registry, not a closed enum), RuntimeSkill, set_skill_bindings(), SkillBindings, SkillCategory, SkillInput, SkillOutput, SkillSafety

### Community 304 - "test_connector_registry.py"
Cohesion: 0.07
Nodes (13): Fixed, Fixed, _connectors(), ConnectorSpec, get_connector(), list_connectors(), send_webhook(), test_catalogue_lists_the_webhook_connector() (+5 more)

### Community 305 - "ApprovalStore"
Cohesion: 0.08
Nodes (9): ApprovalRequest, ApprovalStatus, ApprovalStore, _set_event_threadsafe(), test_an_ignored_approval_expires_denied_not_allowed(), test_approval_arguments_are_scrubbed_before_they_reach_a_reviewer(), test_approval_records_who_decided(), test_resolving_an_unknown_approval_returns_none() (+1 more)

### Community 306 - "DistributedRateLimiter"
Cohesion: 0.09
Nodes (4): DistributedRateLimiter, _LocalBucket, PersistedRequest, PersistentQueue

### Community 307 - "test_internal_agent_delivery.py"
Cohesion: 0.09
Nodes (18): assess_delivery(), clone_repo_workspace(), DeliveryOutcome, _git(), parse_github_repo(), _assess(), test_adapter_fails_task_whose_changes_never_shipped(), test_changes_without_pr_fail_with_stage() (+10 more)

### Community 308 - "test_provider_failover_integration.py"
Cohesion: 0.15
Nodes (7): reset_cooldowns(), test_failover_chain_local_windows_hf_deepseek_anthropic(), test_failover_raises_503_when_all_fail(), test_failover_skips_local_uses_windows_server(), fake_post_chat(), test_from_env_includes_windows_server(), test_provider_on_cooldown_is_skipped()

### Community 309 - "_routing_candidates"
Cohesion: 0.09
Nodes (6): _brain_config_source(), _llm_models(), _routing_candidates(), TestFable51CandidatesUpdated, TestGemini3xCandidatesUpdated, TestNoDanglingCandidates

### Community 310 - "test_provider_enable_disable.py"
Cohesion: 0.07
Nodes (10): isolated_kv(), one_provider(), _apply(), _run(), _StubManager, _StubProvider, test_transient_failures_do_not_auto_disable(), test_unfixable_failures_auto_disable() (+2 more)

### Community 311 - "test_render_mcp.py"
Cohesion: 0.11
Nodes (7): RenderOpsStatus, RenderWriteBlockedError, _env(), _render_yaml(), _service(), TestBackendWiring, TestRenderMCPSidecarService

### Community 312 - "_resolve_user_github_token"
Cohesion: 0.10
Nodes (18): get_skill_registry_safe(), _DoctorCheck, _DoctorReport, get_doctor_diagnostics(), get_doctor_report(), get_public_doctor(), _resolve_user_github_token(), workflow_orchestrator_execute() (+10 more)

### Community 313 - "LLMRouter"
Cohesion: 0.03
Nodes (32): Fixed, 1. `LLMRouter` is the only gateway, 2. Providers are data, not code, 3. Secrets stay in the environment, 4. Three independent failure scopes, 5. Bulkhead isolation, 6. Context is managed losslessly, 7. Configuration is six committed YAML files (+24 more)

### Community 314 - "test_gateway_upstream_retry.py"
Cohesion: 0.16
Nodes (19): default_retry_config(), _post_once(), post_with_retries(), _retry_after_seconds(), json_response(), _sequence(), test_attempts_are_capped_and_last_response_is_returned(), test_connect_error_is_retried_then_succeeds() (+11 more)

### Community 315 - "test_kimi_bridge_server.py"
Cohesion: 0.07
Nodes (9): KimiBrowserDriver, _messages_to_prompt(), _wait_for_reply(), auth_token(), fake_driver(), kimi_app(), test_messages_to_prompt_assistant_turn(), test_messages_to_prompt_basic() (+1 more)

### Community 317 - "TaskPriority"
Cohesion: 0.07
Nodes (33): delegate_seo_findings(), _capability_tags(), create_task_from_oldest_open_issue(), intake_issue(), _issue_labels(), issue_source_id(), map_issue_to_task(), should_intake() (+25 more)

### Community 319 - "test_local_controller.py"
Cohesion: 0.07
Nodes (12): _env_defaults(), _fake_subprocess_run(), _import_controller(), test_daemon_diagnose_returns_json_summary(), test_daemon_off_returns_idle_heartbeat(), test_daemon_on_bad_binary_marks_error_in_heartbeat(), test_daemon_picks_colibri_8081_when_only_it_listening(), test_daemon_restart_reprobes_http_port_only() (+4 more)

### Community 320 - "ContextManager"
Cohesion: 0.10
Nodes (16): ContextManager, _make_obs(), test_compact_history_replaces_old_with_summary(), test_compact_history_short_history_unchanged(), test_condense_step_result_short_result_unchanged(), test_condense_step_result_trims_long_summary(), test_condense_step_result_trims_observations(), test_mask_observations_dict_result() (+8 more)

### Community 321 - "test_microagents.py"
Cohesion: 0.15
Nodes (17): load_microagents(), match_microagents(), Microagent, microagents_block(), _parse_file(), test_block_caps_total_size(), test_block_formats_matched_agents(), test_committed_repo_microagents_parse() (+9 more)

### Community 322 - "test_backend_server_features.py"
Cohesion: 0.06
Nodes (12): _append_agent_session_message(), _build_auto_skill_guidance(), _mask_observations(), _run_agent_loop(), _select_auto_skills(), test_agent_role_models_planner_and_verifier_are_reasoning_models(), test_mask_observations_does_not_mutate_input(), test_mask_observations_leaves_short_messages_unchanged() (+4 more)

### Community 323 - "README.md"
Cohesion: 0.14
Nodes (4): A sample of what the agents shipped (all merged, all real), The numbers (verifiable via the GitHub API), This repository is maintained by its own agents, Why this matters if you're evaluating the platform

### Community 324 - "_resolve_push_token"
Cohesion: 0.11
Nodes (11): get_ceo_dispatcher(), reset_ceo_dispatcher(), _get_ceo_dispatcher(), _resolve_push_token(), test_get_ceo_dispatcher_singleton(), _clean_env(), test_falls_through_gh_pat_and_github_token(), test_internal_run_uses_server_token() (+3 more)

### Community 325 - "Langfuse Observability Guide"
Cohesion: 0.06
Nodes (32): 1. Create a Langfuse project, 2. Configure credentials, 3. Optional tuning, 4. Verify the connection, Commercial savings metrics, Cost analysis dashboard, Cost dashboard, Customising Commercial Reference Prices (+24 more)

### Community 326 - "test_agent_free_brain.py"
Cohesion: 0.07
Nodes (14): resolve_free_nvidia_brain(), _FakeAsyncClient, _FakeResponse, _free_env(), test_allow_paid_brain_default_false(), test_allow_paid_brain_opt_in(), test_chat_text_nvidia_model_uses_configured_endpoint(), test_chat_text_refuses_when_no_free_brain() (+6 more)

### Community 327 - "RateLimitTracker"
Cohesion: 0.10
Nodes (7): get_tracker(), RateLimitTracker, _response(), TestClear, TestGetStats, TestPreFlightCheck, TestUpdateFromResponse

### Community 328 - "test_portfolio_drain.py"
Cohesion: 0.06
Nodes (36): dedupe_portfolio_tasks(), DedupeResult, initiative_key(), _keeper(), map_initiative_to_task(), materialize_committed(), portfolio_key(), _portfolio_materialize_enabled() (+28 more)

### Community 329 - "test_workspace_isolation.py"
Cohesion: 0.16
Nodes (9): InvalidJobIdError, InvalidSessionIdError, WorkspaceCleanupBlockedError, WorkspaceError, WorkspaceManifestCorruptionError, WorkspaceNotFoundError, WorkspaceNotResumableError, WorkspaceOutsideRootError (+1 more)

### Community 331 - "ContextCompressor"
Cohesion: 0.11
Nodes (14): ContextCompressor, ContextStats, _estimate_tokens(), _msgs(), test_inspect_empty(), test_inspect_returns_stats(), test_inspect_strategy_does_not_modify(), test_micro_removes_duplicates() (+6 more)

### Community 332 - "asyncio"
Cohesion: 0.13
Nodes (12): _FakeMemory, _recording_llm(), test_advise_consults_selected_execs_and_synthesizes(), test_advise_is_fail_soft_when_a_voice_errors(), test_advise_single_exec_needs_no_synthesis(), test_advise_unknown_role_is_dropped(), test_answer_is_persisted_to_memory(), test_default_research_handles_search_failure() (+4 more)

### Community 333 - "agents/api.py"
Cohesion: 0.10
Nodes (15): _apply_activity_status(), create_agent(), delete_agent(), get_agent(), _get_user(), list_agents(), list_runtime_agents(), record_agent_use() (+7 more)

### Community 334 - "get_store"
Cohesion: 0.19
Nodes (7): get_store(), ADR-007: Storage backend duck-typing over formal ABC, Consequences, Context, Decision, Rationale, MongoStore

### Community 335 - "RewardScorer"
Cohesion: 0.08
Nodes (5): _nvidia_api_key(), RewardScore, RewardScorer, TestRewardScore, TestRewardScorer

### Community 336 - "safe_agency.py"
Cohesion: 0.18
Nodes (8): add_pr_comment(), _find_existing_pr(), get_branch_sha(), get_default_branch(), _headers(), safe_create_branch(), safe_create_pr(), test_safe_create_branch_existing()

### Community 337 - "SparkProvider"
Cohesion: 0.07
Nodes (5): get_spark_provider(), NotarizeResult, SparkAgentIdentity, SparkProvider, VerifyResult

### Community 338 - "467 Brutal Audit — File-by-File Status"
Cohesion: 0.06
Nodes (28): Stable Core, 467 Brutal Audit — File-by-File Status, Backend & Services, Core Proxy & Routing, Direct Chat, Feature Matrix (spec §I — demotions needed), Frontend / Public Site (spec §H — 0% delivered), GitHub Workflows (+20 more)

### Community 339 - "ResourceWatchdog"
Cohesion: 0.10
Nodes (12): _now(), ResourceWatchdog, WatchedResource, WatchEvent, test_as_dict(), test_check_once_file_change(), test_check_once_missing_file_returns_none(), test_check_once_no_change() (+4 more)

### Community 340 - "Platform Engineer Agent"
Cohesion: 0.06
Nodes (30): 🚀 Advanced Capabilities, Backstage as the Front Door, Backwards Compatibility, Build Golden Paths, Not Just Tools, 🚨 Critical Rules You Must Follow, Developer Experience Measurement, Golden Path: New Service Scaffolding, 🔄 Learning & Memory (+22 more)

### Community 341 - "Marketing SEO Specialist"
Cohesion: 0.06
Nodes (30): Advanced Capabilities, AI Search & SGE Adaptation, Algorithm Recovery, Cannibalization Audit Template, Cannibalization Audit Without GSC (Pre-Access Fallback), Cannibalization Prevention (MANDATORY before any optimization), Communication Style, Core Mission (+22 more)

### Community 342 - "High-Agency Frontend Skill"
Cohesion: 0.06
Nodes (30): 10. FINAL PRE-FLIGHT CHECK, 1. ACTIVE BASELINE CONFIGURATION, 2. DEFAULT ARCHITECTURE & CONVENTIONS, 3. DESIGN ENGINEERING DIRECTIVES (Bias Correction), 4. CREATIVE PROACTIVITY (Anti-Slop Implementation), 5. PERFORMANCE GUARDRAILS, 6. TECHNICAL REFERENCE (Dial Definitions), 7. AI TELLS (Forbidden Patterns) (+22 more)

### Community 343 - "test_brain_priority_scanner.py"
Cohesion: 0.06
Nodes (27): _preferred_provider(), ProviderUpdate, _seed_sync_update(), update_provider(), _run(), test_brain_allows_paid_when_no_free_configured(), fake_policy(), test_brain_env_override_wins_over_paid_provider() (+19 more)

### Community 344 - "Quick-Note GitHub Issues Processing - Session Summary"
Cohesion: 0.06
Nodes (30): 1. Stop-Slop Quality Filter (Issue #229), 2. ECC Integration Study (Issue #266 & #230), ✅ Analysis & Comments (16 items), Architecture Alignment, Branch: `docs/ecc-adoption-analysis`, Branch: `feat/stop-slop-quality-filter`, Deliverables, ECC Patterns Adopted (+22 more)

### Community 345 - "ProviderConsole.jsx"
Cohesion: 0.10
Nodes (29): discoverLlmModels(), getLlmProviders(), getLlmStatus(), probeLlmProviders(), reloadLlmConfig(), setLlmProviderEnabled(), setLlmStrategy(), routed (+21 more)

### Community 346 - "v3_models.py"
Cohesion: 0.13
Nodes (14): UserResponse, delete_model(), get_activity(), get_model(), _get_ollama_model_info(), _get_ollama_models(), get_stats(), list_models() (+6 more)

### Community 347 - "switch_brain.py"
Cohesion: 0.15
Nodes (18): detect_ollama_models(), dim(), fail(), get_auth_headers(), get_brain_config(), get_ngrok_tunnel_url(), header(), info() (+10 more)

### Community 348 - "Fixed"
Cohesion: 0.03
Nodes (22): _in_container(), Fixed, Fixed, _run_once_max_age_sec(), _priority_rank(), pytest_sessionfinish(), _stop_leaked_aiosqlite_workers(), backend_jwt() (+14 more)

### Community 349 - "test_colibri_provider.py"
Cohesion: 0.13
Nodes (16): colibri_enabled(), colibri_provider_config(), colibri_status(), _safe_priority(), test_provider_colibri_none_when_disabled(), test_provider_colibri_registered_when_enabled(), test_disabled_by_default(), test_enabled_returns_openai_compatible_config() (+8 more)

### Community 350 - "test_skill_registry_boot_refresh.py"
Cohesion: 0.11
Nodes (7): clean_task(), _install(), _NullDispatcher, _NullRuntimeManager, _Registry, test_startup_actually_calls_it(), TestBootRefresh

### Community 351 - "test_autonomy_gate.py"
Cohesion: 0.12
Nodes (18): agent_branch_name(), assert_agent_can_merge(), assert_agent_can_write(), AutonomyViolation, is_protected_branch(), _protected_branches(), test_agent_branch_name(), test_agent_merge_refused() (+10 more)

### Community 352 - "Configuration Reference"
Cohesion: 0.06
Nodes (32): Agent governance — identity, policy, approvals, audit, sandboxes, Agent Models, AI Gateway Hardening, Amazon Bedrock — paid brain on AWS credit, Anthropic API Compatibility / Claude Code, Anthropic provider tuning, Authentication and Keys, Claude Code setup (+24 more)

### Community 353 - "LessonStore"
Cohesion: 0.11
Nodes (10): LessonStore, record_run_success(), TestLessonStoreIntegration, _age(), store(), test_a_recurring_lesson_needs_as_many_successes_to_retire(), test_existing_store_gains_the_resolved_column(), test_partial_failed_or_empty_runs_do_not_count_as_success() (+2 more)

### Community 354 - "or"
Cohesion: 0.07
Nodes (29): 🚀 Advanced Capabilities, API Documentation Excellence, Content Operations, Content Quality & Maintenance, 🚨 Critical Rules You Must Follow, Developer Documentation, Docs-as-Code Infrastructure, Documentation Architecture (+21 more)

### Community 355 - "Application Security Engineer"
Cohesion: 0.07
Nodes (29): 🚀 Advanced Capabilities, Advanced Secure Code Review, Application Security Engineer, Code Review Standards, Compliance as Code, 🚨 Critical Rules You Must Follow, Dependency Vulnerability Management, Developer Security Education (+21 more)

### Community 356 - "build_render_router"
Cohesion: 0.13
Nodes (13): build_render_router(), render_deploys(), render_health(), render_logs(), render_metrics(), render_ops_scan(), render_ops_status(), render_services() (+5 more)

### Community 357 - "probe_catalogues.py"
Cohesion: 0.11
Nodes (18): Fixed, Status Key, Fixed, _auth_headers(), _chat_targets(), _dump_matching(), _kind(), list_models() (+10 more)

### Community 358 - "WorkflowPhase"
Cohesion: 0.11
Nodes (4): WorkflowEngine, WorkflowPhase, test_workflow_phase_is_str(), test_workflow_phases_exist()

### Community 359 - "output_filter.py"
Cohesion: 0.07
Nodes (14): _count_remaining(), _filter_curl(), _filter_docker(), _filter_generic(), _filter_git(), _filter_ls(), _filter_npm(), _filter_pip() (+6 more)

### Community 360 - "triage_orphaned_context_prs.py"
Cohesion: 0.11
Nodes (8): decide(), Decision, issue_number_from_branch(), main(), _issue(), TestBranchParsing, TestDecisions, TestWorkflowWiring

### Community 361 - "TaskDispatcher"
Cohesion: 0.09
Nodes (5): Fixed, Fixed, TaskDispatcher, TestTaskDispatcherDiagnostics, test_dispatcher_skips_a_retried_task_until_its_longer_cooldown()

### Community 362 - "CEOSupervisor"
Cohesion: 0.10
Nodes (3): CEOSupervisor, SweepReport, _flaky()

### Community 364 - "test_force_cleanup_conditional_delete.py"
Cohesion: 0.10
Nodes (9): _FlakyPersistence, _memory_store(), _orphan(), _RaceLostPersistence, _RaceWonPersistence, test_failed_delete_not_counted_on_fired_dedup_and_stuck_paths(), test_orphan_still_unfired_is_expired_via_conditional_delete(), test_orphan_that_started_firing_is_not_expired() (+1 more)

### Community 365 - "generate_context.py"
Cohesion: 0.11
Nodes (19): R1 — Ground the plan in the source before planning anything **[gate]**, apply_source_gate(), _build_caller_chain(), _build_context_doc(), _build_pr_description(), _build_todos_md(), _build_user_message(), _call_cerebras() (+11 more)

### Community 366 - "test_rag_context.py"
Cohesion: 0.10
Nodes (28): RAGContextBuilder, _score_turns(), test_builder_doc_budget_fraction(), test_builder_docs_dropped_count(), test_builder_empty_both(), test_builder_empty_documents(), test_builder_empty_history(), test_builder_hybrid_mode() (+20 more)

### Community 367 - "SkillLibrary"
Cohesion: 0.12
Nodes (13): Skill, SkillLibrary, test_as_dict(), test_empty_library(), test_extract_description_skips_yaml_frontmatter(), test_get_missing_returns_none(), test_get_skill(), test_index_local_skills() (+5 more)

### Community 368 - "StuckDetector"
Cohesion: 0.14
Nodes (15): _signature(), StuckDetector, StuckThresholds, _obs(), test_agent_runner_wires_stuck_detector(), test_alternating_needs_full_window(), test_alternating_pattern_is_stuck(), test_custom_thresholds_are_respected() (+7 more)

### Community 370 - "Data Engineer Agent"
Cohesion: 0.07
Nodes (28): 🚀 Advanced Capabilities, Advanced Lakehouse Patterns, Architecture Principles, Cloud Platform Mastery, 🚨 Critical Rules You Must Follow, Data Engineer Agent, Data Pipeline Engineering, Data Platform Architecture (+20 more)

### Community 371 - "test_rate_limiter.py"
Cohesion: 0.09
Nodes (17): pace(), reset(), TokenBucket, _reset_buckets(), test_pace_is_noop_without_env_var(), test_pace_never_raises_on_bad_input(), test_pace_noop_for_non_finite_rpm(), test_pace_noop_for_non_numeric_env_var() (+9 more)

### Community 372 - "_ensure_tasks_source_id_unique_index"
Cohesion: 0.09
Nodes (14): _agent_provider_failure_response(), _ensure_tasks_source_id_unique_index(), _build(), _is_index_options_conflict(), fake_chat_json(), test_dedup_failure_does_not_block_index_attempt(), test_dedup_pass_runs_before_index_build(), test_dup_key_failure_does_not_trigger_drop() (+6 more)

### Community 373 - "FeatureEntry"
Cohesion: 0.09
Nodes (4): Added, Added, [v4.1.0], FeatureEntry

### Community 374 - "Conflicts and Stale Facts"
Cohesion: 0.07
Nodes (25): C1 — The bill of materials is wrong in both directions, C2 — Three different answers to "where do I read env vars?", C3 — Two different file-size limits, C4 — The frontend does not deploy to Vercel, C5 — The documented P0 escape hatch does not exist, C6 — `CLAUDE.md` §14.11 conflicts with §14.9, C7 — Two `§10` headings in `CLAUDE.md`, C8 — Duplicated rule sets that have already drifted (+17 more)

### Community 377 - "test_claude_setup_audit.py"
Cohesion: 0.16
Nodes (19): AuditReport, _check_agents_config(), _check_claude_md_sections(), _check_hooks(), _check_skills(), _check_state(), CheckResult, main() (+11 more)

### Community 378 - "AgentPlan"
Cohesion: 0.05
Nodes (28): AgentEvent, AgentPlan, AgentRunRequest, AgentSessionCreateRequest, AgentSessionMessage, AgentStep, _known_tool_names(), ResumeRequest (+20 more)

### Community 379 - "Initiative"
Cohesion: 0.08
Nodes (3): Initiative, TestInitiative, TestTheFieldExists

### Community 380 - "_captured_request_headers"
Cohesion: 0.12
Nodes (6): _captured_request_headers(), _fake_post(), _make_client(), TestMcpHeadersBackwardCompatibility, TestMcpMethodHeader, TestMcpNameHeader

### Community 381 - "ReactScratchpad"
Cohesion: 0.11
Nodes (4): build_react_prompt(), ReactScratchpad, TestBuildReactPrompt, TestReactScratchpad

### Community 382 - "test_phase6_workflow.py"
Cohesion: 0.14
Nodes (19): verify_pr_exists(), _make_store(), _make_task(), test_execute_sets_workflow_classify_phase(), test_phase_judge_fail_on_error(), test_phase_judge_pass(), test_phase_summarize_done_on_success(), test_phase_summarize_failed_on_error() (+11 more)

### Community 383 - "test_company_api.py"
Cohesion: 0.12
Nodes (3): TestCompanyAPI, TestCreateCompanyValidation, TestDoctorEndpoint

### Community 384 - "AGENTS.md — Codebase Map & Operations Reference"
Cohesion: 0.07
Nodes (25): Agent roles, AGENTS.md — Codebase Map & Operations Reference, Architecture, Claude Code subagents (cost-aware routing), Codebase map, Deployment, File-size exceptions, Further reading (+17 more)

### Community 385 - "UX Researcher Agent Personality"
Cohesion: 0.07
Nodes (27): 🚀 Advanced Capabilities, Behavioral Analysis Mastery, 🚨 Critical Rules You Must Follow, Ethical Research Practices, Insight Communication, 🔄 Learning & Memory, Pattern Recognition, Provide Actionable Insights (+19 more)

### Community 386 - "DevOps Automator Agent Personality"
Cohesion: 0.07
Nodes (27): 🚀 Advanced Capabilities, Automate Infrastructure and Deployments, Automation-First Approach, CI/CD Excellence, CI/CD Pipeline Architecture, 🚨 Critical Rules You Must Follow, DevOps Automator Agent Personality, Ensure System Reliability and Scalability (+19 more)

### Community 387 - "Mobile App Builder Agent Personality"
Cohesion: 0.07
Nodes (27): = Advanced Capabilities, Android Jetpack Compose Component, Create Native and Cross-Platform Mobile Apps, =¨ Critical Rules You Must Follow, Cross-Platform Excellence, Cross-Platform React Native Component, Integrate Platform-Specific Features, iOS SwiftUI Component Example (+19 more)

### Community 388 - "Developer Agent Personality"
Cohesion: 0.07
Nodes (27): 1. Task Analysis & Planning, 2. Premium Implementation, 3. Quality Assurance, 🚀 Advanced Capabilities, Advanced FluxUI Usage, 🚨 Critical Rules You Must Follow, Developer Agent Personality, FluxUI Component Mastery (+19 more)

### Community 389 - "Analytics Reporter Agent Personality"
Cohesion: 0.07
Nodes (27): 🚀 Advanced Capabilities, Analytics Reporter Agent Personality, Business Impact Focus, Business Intelligence Excellence, 🚨 Critical Rules You Must Follow, Customer Segmentation Analysis, Data Quality First Approach, Enable Data-Driven Decision Making (+19 more)

### Community 390 - "Support Responder Agent Personality"
Cohesion: 0.07
Nodes (27): 🚀 Advanced Capabilities, 🚨 Critical Rules You Must Follow, Customer First Approach, Customer Success Integration, Customer Support Analytics Dashboard, Deliver Exceptional Multi-Channel Customer Service, Establish Support Excellence Culture, Knowledge Base Management System (+19 more)

### Community 391 - "Python Dependencies (`requirements.txt`)"
Cohesion: 0.07
Nodes (27): AI / LLM, AI Tooling, Browser Automation, Cloud / Infrastructure, Core Web Framework, Data Processing, DEP-001 [HIGH] — No Python Lockfile, DEP-002 [HIGH] — `playwright` as a Runtime Dependency (+19 more)

### Community 392 - "_fake_http_sequence"
Cohesion: 0.14
Nodes (13): Fixed, Fixed, Fixed, Fixed, _blocks(), main(), normalize_text(), scan_corruption() (+5 more)

### Community 393 - "Part A — CodeRabbit review fixes for this PR (do first, small)"
Cohesion: 0.07
Nodes (28): A1 — `docs/changelog.md`: add the two autonomy docs under `### Added` ✅ trivial, A2 — `docs/telegram-bot.md`: fix broken charter links (MD + path), A3 — `docs/telegram-bot.md`: add language to fenced block (MD040), A4 — `.env.example`: use exact var name in the shortcut comment, A5 — `services/workflow_orchestrator.py`: surface notify failures at WARNING, A6 — `telegram_bot.py`: avoid double-approve in the `wfo_approve` path ⚠️ behavioural, A7 — `telegram_service.py`: escape Markdown-v1 reserved chars in approval text ⚠️ correctness, A8 — `render.yaml`: propagate Telegram vars to the worker service (+20 more)

### Community 394 - "KV Cache Internals"
Cohesion: 0.07
Nodes (23): ALiBi (Attention with Linear Biases), Comparison, Learned Positional Embeddings, Positional Encoding Internals, RoPE Scaling for Long Contexts, Rotary Positional Embedding (RoPE), Sinusoidal Positional Encoding (Original Transformer), KV Cache Internals (+15 more)

### Community 395 - "ModelRouter"
Cohesion: 0.14
Nodes (10): ADR 002: Dynamic Model Routing with Task Classification, Consequences, Context, Decision, Negative, Neutral, Positive, ModelRouter (+2 more)

### Community 396 - "WorkspaceManager"
Cohesion: 0.08
Nodes (28): test_git_ref_rejects_empty(), test_git_ref_rejects_flag_injection(), test_git_ref_rejects_shell_metacharacters(), test_git_ref_rejects_traversal(), test_git_ref_valid(), test_git_scheme_allows_ssh(), test_http_scheme_rejects_ssh(), test_https_public_host_allowed() (+20 more)

### Community 397 - "webui/frontend/package.json"
Cohesion: 0.07
Nodes (26): @types/react, @types/react-dom, typescript, vite, @vitejs/plugin-react, dependencies, react, react-dom (+18 more)

### Community 398 - "keepalive.py"
Cohesion: 0.13
Nodes (15): _check_ollama(), _check_render(), _default_ollama_base(), _default_render_url(), _env_bool(), _loaded_ollama_prefixes(), _log(), _log_path() (+7 more)

### Community 399 - "test_phase5_doctor.py"
Cohesion: 0.11
Nodes (5): client(), test_doctor_langfuse_check_present(), test_doctor_survives_preflight_error(), test_doctor_survives_runtime_manager_error(), test_public_doctor_storage_check_uses_real_collection_count()

### Community 400 - "sam_actions.py"
Cohesion: 0.10
Nodes (14): detect_alert_intent(), fetch_alerts(), fix_alerts(), handle_alert_command(), _plural(), queue_fix_task(), SamAlert, summarize_alerts() (+6 more)

### Community 401 - "test_pr_approval_gate.py"
Cohesion: 0.10
Nodes (9): _pr(), test_card_keyboard_callback_data_parses_to_pr_actions(), TestPrIsGreen, TestRunSweep, get_check_runs(), list_open_prs(), send_card(), list_open_prs() (+1 more)

### Community 402 - "NotificationDispatcher"
Cohesion: 0.09
Nodes (24): Acceptance criteria, Design, Objective, Part B — G2: Closed-loop self-heal feedback, Tech stack / touch points, Tests, To-dos (checklist), NotificationDispatcher (+16 more)

### Community 403 - "_llm_catalog"
Cohesion: 0.09
Nodes (8): _cost_tracker_src(), _llm_catalog(), TestClaudeSonnet45CostEntry, TestGptOssMultiProviderCostEntries, TestNvidiaNimFreeTierCostEntries, TestOllamaLocalCostEntries, TestPaidModelsCostTrackerCoverage, TestTextEmbeddingSmallCostEntry

### Community 404 - "RepoConnection"
Cohesion: 0.11
Nodes (23): Phase 0 — `RepoConnection` plumbing + delivery-policy detection, Phase 1 — Plan-PR → Implementation  *(highest leverage; closes the live gap)*, Phase 2 — Review-comment resolution (Codex / CodeRabbit), Phase 3 — Quality gate + policy-conformant landing, Phase 4 — Monitor & regression guard, Phases, 6. Integration gaps to wire (follow-up implementation), Loop 3 — Agentic SDLC (the golden path) (+15 more)

### Community 405 - "_Recorder"
Cohesion: 0.09
Nodes (4): _Recorder, TestNvidiaGetsMoreThanOneCandidate, TestToolCallsSurviveTheDictShape, TestTurnPayload

### Community 406 - "test_executive_advisory_api.py"
Cohesion: 0.13
Nodes (12): AdviceResult, _make_app(), stub_advisory(), test_consult_maps_advisory_failure_to_502(), test_consult_passes_company_context(), _advise(), test_consult_rejects_empty_question(), test_consult_rejects_non_admin() (+4 more)

### Community 407 - "ExecutiveAdvisory"
Cohesion: 0.10
Nodes (8): ExecOpinion, Executive, ExecutiveAdvisory, Grounding, test_grounding_evidence_is_injected_and_recorded(), research(), test_select_falls_back_when_nothing_matches(), test_select_routes_by_domain_keyword()

### Community 408 - "redact_connection_url"
Cohesion: 0.19
Nodes (3): redact_connection_url(), TestLoggingCallSitesRedactCredentials, TestRedactConnectionUrl

### Community 409 - "ProjectScaffolder"
Cohesion: 0.14
Nodes (13): ProjectScaffolder, ScaffoldResult, Template, test_apply_cli_tool(), test_apply_fastapi_service(), test_apply_overwrites_when_flag_set(), test_apply_python_library(), test_apply_skips_existing_without_overwrite() (+5 more)

### Community 410 - "SprintMetrics"
Cohesion: 0.11
Nodes (3): SprintMetrics, TestSprintHealth, TestSprintMetrics

### Community 411 - "UI Designer Agent Personality"
Cohesion: 0.07
Nodes (26): 🚀 Advanced Capabilities, Component Library Architecture, Craft Pixel-Perfect Interfaces, Create Comprehensive Design Systems, 🚨 Critical Rules You Must Follow, Design System First Approach, Design System Mastery, Developer Collaboration (+18 more)

### Community 412 - "Product Sprint Prioritizer Agent"
Cohesion: 0.07
Nodes (26): Alignment Techniques, Capacity Planning, Continuous Improvement, Core Capabilities, Decision Framework, Kano Model Classification, Mitigation Strategies, Pre-Sprint Planning (Week Before) (+18 more)

### Community 413 - "Technical Debt Register — local-llm-server"
Cohesion: 0.08
Nodes (25): Category 10 — Patch Files in Root, Category 1 — God Files, Category 3 — Dual App Architecture, Category 4 — Dual Storage Backend, Category 5 — Test File Sprawl, Category 6 — Environment Variable Documentation, Category 7 — Missing Type Annotations, Category 8 — Comments and Documentation Debt (+17 more)

### Community 414 - "test_gateway_sanitizer.py"
Cohesion: 0.13
Nodes (14): sanitize_payload(), reset(), reset(), reset(), gateway_env(), _payload(), test_default_mode_leaves_the_upstream_body_unchanged(), test_every_role_and_non_text_payload_shapes_are_handled() (+6 more)

### Community 415 - "workflow/models.py"
Cohesion: 0.12
Nodes (4): TestApprovalGate, TestCheckRun, ApprovalGate, CheckRun

### Community 416 - "Claude Code + Qwen Local Setup"
Cohesion: 0.07
Nodes (27): 1. Set environment variables, 2. Start Claude Code, 3. Verify model routing, Anthropic SDK (Python), Architecture, "Authentication error" or 401, Claude Code + Qwen Local Setup, Claude Code reports "token limit exceeded" (+19 more)

### Community 417 - "Docker Agent Runtimes Setup"
Cohesion: 0.07
Nodes (27): Access from LLM Relay Dashboard, Access via REST API, Add More Runtimes, Advanced, Architecture, Check Service Health, Configuration, Direct HTTP Calls to Runtime (+19 more)

### Community 418 - "heal_signature"
Cohesion: 0.07
Nodes (16): heal_signature(), HealState, test_hermes_dispatch_is_a_coroutine(), test_hermes_dispatch_noop_without_url(), test_regress_redispatch_failure_escalates(), healer(), test_dedup_one_active_heal_per_signature(), test_does_not_resolve_before_window() (+8 more)

### Community 419 - "CEO Micro-Management"
Cohesion: 0.09
Nodes (20): A failed drive does not abandon the goal, CEO Micro-Management, Configuration reference, Escalation, and why it terminates, Five bounds, Operator surface, Tests, The 24x7 supervisor (+12 more)

### Community 420 - "redact_secrets"
Cohesion: 0.10
Nodes (13): _signature(), _redactor(), _luhn_ok(), _redact_pii(), _card(), redact_secrets(), TestLuhn, _dump() (+5 more)

### Community 421 - "CostAttributor"
Cohesion: 0.09
Nodes (5): CostAttributor, CostReport, get_cost_attributor(), UsageRecord, TestCostAttribution

### Community 422 - "_execute_skill_impl"
Cohesion: 0.10
Nodes (15): Feature Matrix, _execute_skill_impl(), _get_portfolio_manager(), _run_council_review(), _run_graphify(), test_council_clean_diff_is_approved(), test_council_detects_secret_variants(), test_council_empty_diff_is_blocked() (+7 more)

### Community 423 - "test_anthropic_refusal_fallback.py"
Cohesion: 0.15
Nodes (6): _make_provider(), _refusal_response(), _request(), TestLegacyRouterServerFallback, TestRefusalLogging, TestServerFallbackPayload

### Community 424 - "TestGeminiOmniCatalogEntry"
Cohesion: 0.09
Nodes (6): _cost_tracker_source(), _llm_catalog(), _routing_candidates(), TestDeepSeekNIMEntry, TestGeminiOmniCatalogEntry, TestKimiK2PricingCorrection

### Community 426 - "TestDiagCommand"
Cohesion: 0.11
Nodes (4): _run(), TestDiagCommand, _fake(), TestSilentDropRemediation

### Community 427 - "ContextPruner"
Cohesion: 0.10
Nodes (18): ContextPruner, big_pruner(), pruner(), test_phase1_handles_non_string_content(), test_phase1_preserves_short_tool_output(), test_phase1_strips_think_tags(), test_phase1_strips_unclosed_think_tag(), test_phase1_truncates_long_tool_output() (+10 more)

### Community 428 - "TerminalPanel"
Cohesion: 0.13
Nodes (12): _is_command_not_found(), _powershell_quote(), _terminal_size(), TerminalPanel, TerminalSnapshot, test_as_dict(), test_run_and_capture_echo(), test_run_and_capture_stderr() (+4 more)

### Community 429 - "VoiceCommandInterface"
Cohesion: 0.13
Nodes (9): _stub_result(), TranscriptionResult, VoiceCommandInterface, voice_status_backend(), test_as_dict(), test_listen_transcribe_without_mic(), test_stub_result(), test_transcribe_empty_audio() (+1 more)

### Community 430 - "Frontend Developer Agent Personality"
Cohesion: 0.08
Nodes (25): Accessibility and Inclusive Design, Accessibility Leadership, 🚀 Advanced Capabilities, Create Modern Web Applications, 🚨 Critical Rules You Must Follow, Editor Integration Engineering, Frontend Developer Agent Personality, 🔄 Learning & Memory (+17 more)

### Community 431 - "tts.py"
Cohesion: 0.12
Nodes (13): sam_speak_backend(), SamSpeakRequest, test_default_format_is_still_ogg_for_telegram(), test_mp3_request_passes_gtts_mp3_through(), test_speak_request_accepts_mp3_and_rejects_unknown(), _convert(), _convert_to_mp3(), _convert_to_ogg() (+5 more)

### Community 432 - "get_savings"
Cohesion: 0.16
Nodes (7): compute_savings(), compute_time_series(), get_savings(), get_usage(), get_user_savings(), _period_start(), SavingsSummary

### Community 433 - "fmtErr"
Cohesion: 0.06
Nodes (44): (1) & partly (4): "Something went wrong" masks the real error everywhere, (2) & (3): Company creation flow / non-admin gate placement, (4): Agent provisioning "loading forever" — blocking subprocess in async path, Agent Prompt (paste this to start the implementation session), Context — bugs reported during manual QA, D. Wire AI-tailored questions to the frontend (`QuestionsStep`), E. General bug sweep, Implementation Plan (+36 more)

### Community 434 - "_is_dns_failure"
Cohesion: 0.14
Nodes (4): _is_dns_failure(), _probe_failure_reason(), TestIsDnsFailure, TestProbeFailureReason

### Community 435 - "test_regression.py"
Cohesion: 0.10
Nodes (12): browser_login(), main(), regression_base_url(), run_regression(), screenshot(), test_desktop_regression(), test_mobile_regression(), TestActivation (+4 more)

### Community 436 - "test_daily_automation_2026_08_03.py"
Cohesion: 0.11
Nodes (12): _load_yaml(), test_aerolink_candidates_match_yaml(), test_anthropic_candidates_match_yaml(), test_brain_config_nvidia_candidates_are_not_empty(), test_yaml_aerolink_candidates_contains_opus_5(), test_yaml_aerolink_judge_is_opus_5(), test_yaml_aerolink_opus_5_is_first_candidate(), test_yaml_aerolink_planner_is_opus_5() (+4 more)

### Community 437 - "brain_failover.py"
Cohesion: 0.11
Nodes (13): _disabled_from_mongo(), _disabled_from_sqlite(), _is_paid_allowed_db(), _kv_connect(), _kv_path(), _mongo_db(), _mongo_enabled(), _mongo_unavailable() (+5 more)

### Community 438 - "ensure_self_company"
Cohesion: 0.06
Nodes (22): autonomy_status(), _schedule_self_bootstrap(), _count_specialists(), _create_company_directly(), ensure_self_company(), _find_self_company(), _find_stale_self_companies(), _list_companies_safe() (+14 more)

### Community 439 - "test_workflow_shell_vars_are_declared.py"
Cohesion: 0.10
Nodes (7): _cases(), test_every_shell_variable_has_a_source(), test_the_scan_sees_the_workflow_fleet(), TestTheDetectorActuallyDetects, TestTheMergeStepNamesTheIssue, _undeclared(), _workflows()

### Community 440 - "build_executive_advisory_router"
Cohesion: 0.12
Nodes (13): _company_advisory_context(), default_executives(), AdvisoryConsultRequest, AdvisoryResponse, build_executive_advisory_router(), consult(), list_executives(), ExecutiveListResponse (+5 more)

### Community 441 - "Part A — Health Report"
Cohesion: 0.11
Nodes (17): F1 — CLAUDE.md documents an architecture that no longer exists, F2 — 15 skills have no frontmatter description, F3 — Direct `os.environ` reads outside config modules, F4 — `print()` in importable production modules, F5 — graphify hook nags every session, F6 — God files, Healthy signals, P1 — Refresh CLAUDE.md and AGENTS.md to match the real architecture (+9 more)

### Community 442 - "is_model_available"
Cohesion: 0.10
Nodes (16): F. Router invariants (`router/`), F. Router invariants (`router/`), fallback_chain, Health check and availability filtering, _post_anthropic_with_fallback(), fallback_chain(), _enabled(), get_available_models() (+8 more)

### Community 443 - "test_memory.py"
Cohesion: 0.15
Nodes (9): _now(), SessionMemory, test_delete_nonexistent_returns_false(), test_delete_snapshot(), test_list_snapshots(), test_restore_missing_returns_none(), test_session_id_sanitisation(), test_snapshot_and_restore() (+1 more)

### Community 444 - "Universality: case-coverage matrix"
Cohesion: 0.10
Nodes (20): A. Connection & credentials, Autonomous SDLC Loop (Agency Core, repo-agnostic), B. Provider & host, C. Delivery / branch policy  *(detected — see DeliveryPolicy)*, Companies without a connected repo (URL-only onboarding), D. CI / checks, Design principle: repo-agnostic, not GitHub-Actions-bound, Detect & respect each repo's delivery policy (+12 more)

### Community 445 - "test_keepalive.py"
Cohesion: 0.23
Nodes (14): Maintenance, Maintenance, Maintenance, Maintenance, Maintenance, Maintenance, Maintenance, _reload_kp() (+6 more)

### Community 446 - "Backend Architect Agent Personality"
Cohesion: 0.08
Nodes (24): 🚀 Advanced Capabilities, API Contract Governance, API Design Specification, Backend Architect Agent Personality, Cloud Infrastructure Expertise, 🚨 Critical Rules You Must Follow, Data Evolution & Migration Safety, Data/Schema Engineering Excellence (+16 more)

### Community 447 - "Project Shepherd Agent Personality"
Cohesion: 0.08
Nodes (24): 🚀 Advanced Capabilities, Align Stakeholders and Manage Communications, Complex Project Orchestration, 🚨 Critical Rules You Must Follow, 🔄 Learning & Memory, Mitigate Risks and Ensure Quality Delivery, Orchestrate Complex Cross-Functional Projects, Organizational Change Leadership (+16 more)

### Community 449 - "Session Handoff — 2026-06-15"
Cohesion: 0.08
Nodes (24): Context the next session will need, Critical environment variables, Files changed today (for code archaeology), How to resume, Key files to know, Key labels, P0 — Add a regression test for the draft-PR safety guards, P1 — Watch Run 27481814863 for issue #504 and verify end-to-end (+16 more)

### Community 450 - "webui/router.py"
Cohesion: 0.04
Nodes (34): _get(), _html_links(), _search_duckduckgo(), _search_hackernews(), _search_mojeek(), _search_wikipedia(), caption_tracks(), extract_player_response() (+26 more)

### Community 451 - "Workspace"
Cohesion: 0.08
Nodes (6): _run(), _safe_path(), _validate_workspace_id(), Workspace, workspace_path(), TestWorkspace

### Community 452 - "SQLiteStore"
Cohesion: 0.11
Nodes (8): SQLiteStore, store(), test_find_exclusion_projection_drops_the_field(), test_find_inclusion_projection_keeps_only_named_fields(), test_find_one_applies_projection(), test_find_without_projection_is_unchanged(), store(), test_get_store_returns_sqlite()

### Community 453 - "unittest_mock"
Cohesion: 0.02
Nodes (46): _client(), test_change_role_rejects_invalid_role(), test_change_role_requires_authentication(), test_change_role_returns_404_for_missing_user(), test_change_role_updates_existing_user(), test_get_settings_is_public(), test_get_settings_returns_defaults(), _all() (+38 more)

### Community 454 - "test_service_token.py"
Cohesion: 0.08
Nodes (9): service_token_module(), test_hashed_token_cache_does_not_hold_plaintext(), test_mutating_endpoints_allowlist_is_narrow(), test_token_rotation_picks_up_env_change(), test_verify_service_token_does_not_log_plaintext(), test_verify_service_token_returns_false_for_near_match(), test_verify_service_token_returns_false_for_wrong_token(), test_verify_service_token_returns_false_when_unset() (+1 more)

### Community 455 - "CodeGraph"
Cohesion: 0.18
Nodes (5): _check_symbol(), _clamp(), CodeGraph, CodeGraphError, _run()

### Community 456 - "test_commit_tracker.py"
Cohesion: 0.14
Nodes (11): CommitAttribution, CommitTracker, Web UI (Claude Code–style), _init_repo(), test_attribution_timestamp_auto(), test_build_trailer_args(), test_commit_attributed(), test_commit_failure_returns_none() (+3 more)

### Community 457 - "ErrorInterceptorMiddleware"
Cohesion: 0.18
Nodes (4): _dispatch_async(), _run(), ErrorInterceptorMiddleware, _sig()

### Community 459 - "AI Engineer Agent"
Cohesion: 0.08
Nodes (23): 🚀 Advanced Capabilities, Advanced ML Architecture, AI Engineer Agent, AI Ethics and Safety, AI Ethics & Safety Implementation, AI Safety and Ethics Standards, 🚨 Critical Rules You Must Follow, Intelligent System Development (+15 more)

### Community 460 - "Research Synthesist Agent Personality"
Cohesion: 0.08
Nodes (23): 🚀 Advanced Capabilities, Citation and Source Analysis, 🚨 Critical Rules You Must Follow, Evaluate Sources Honestly, Evidence Synthesis Map, 🔄 Learning & Memory, Research Synthesist Agent Personality, Search and Scope Systematically (+15 more)

### Community 461 - "test_dashboard_cache.py"
Cohesion: 0.13
Nodes (12): _cached(), _fast_count(), _clear_cache(), _CollWithEstimate, _CollWithoutEstimate, _ensure_mongo_fast_count(), test_cached_is_single_flight(), test_cached_recomputes_after_expiry() (+4 more)

### Community 462 - "_handle_command"
Cohesion: 0.10
Nodes (10): openclaw_command(), openclaw_websocket(), _cmd_chat(), _cmd_freebuff(), _cmd_list_files(), _cmd_read_file(), _cmd_status(), _handle_command() (+2 more)

### Community 463 - "Local AI Stack with Docker"
Cohesion: 0.08
Nodes (23): 1. Clone and configure, 2. Start the stack (GPU), 3. Start the stack (CPU only), 4. Pull models (first run), 5. Access services, CPU Only, Data Persistence, Default (GPU) (+15 more)

### Community 464 - "5. The five autonomous loops"
Cohesion: 0.40
Nodes (5): 5. The five autonomous loops, Loop 1 — Self-heal from logs *(closed loop)*, Loop 2 — Feature generation, Loop 4 — Trends contextually applied, Loop 5 — Per-onboarded-site autonomy

### Community 465 - "LLM Router — troubleshooting"
Cohesion: 0.09
Nodes (21): Embeddings, LiteLLM compatibility mode, LLM Router — local model guide, LM Studio, LocalAI, Ollama, Registering local models, Sizing bulkheads (+13 more)

### Community 466 - "TASK 4 — End-to-end approval-gate test"
Cohesion: 0.08
Nodes (23): 3.1 — Confirm env vars on the **web** service, 3.2 — Confirm single-poller guard on the **worker**, 3.3 — Verify the bot responds (human-in-the-loop), 3.4 — TASK 3 acceptance, 4.2 — Trigger an outward-facing workflow run, 4.3 — Watch the run until it pauses, 4.4 — Confirm the Telegram message arrived, 4.5 — Press ✅ Approve (+15 more)

### Community 467 - "ENGINEERING_STANDARDS.md — Patterns & Reference"
Cohesion: 0.09
Nodes (12): Architecture decision records, Authorization patterns, Commit messages, Database indexes, ENGINEERING_STANDARDS.md — Patterns & Reference, Error handling, Log levels, Performance targets (+4 more)

### Community 468 - "ai/__init__.py"
Cohesion: 0.03
Nodes (16): CerebrasProvider, GroqProvider, NvidiaProvider, OllamaProvider, ProviderManager, ChatResponse, HealthStatus, Provider (+8 more)

### Community 469 - "CollectionLike"
Cohesion: 0.12
Nodes (4): get_storage(), reset_storage(), CollectionLike, StorageLike

### Community 470 - "Native operations"
Cohesion: 0.09
Nodes (21): Maintainer verification, Native operations, Read-only reviewer interpretation, Role pins and spawn contract, Runtime routing evidence, Selective route declaration, preflight, and caching, Worker packet and parent acceptance, Exact mode contracts (+13 more)

### Community 471 - "PriorityTaskQueue"
Cohesion: 0.14
Nodes (4): get_task_queue(), PriorityTaskQueue, TestPriorityTaskQueue, handler()

### Community 472 - "TemporalContextGraph"
Cohesion: 0.10
Nodes (3): demo_agent_tracking(), TemporalContextGraph, TemporalFact

### Community 474 - "TestClaudeOpus55CostTracker"
Cohesion: 0.25
Nodes (3): _cost_tracker_source(), _get_cost_tracker_price(), TestClaudeOpus55CostTracker

### Community 475 - "test_openclaw_endpoints.py"
Cohesion: 0.09
Nodes (8): admin_client(), client(), test_pairing_token_endpoints_reject_anonymous(), test_pairing_token_endpoints_reject_non_admin(), test_websocket_pairing_accepts_correct_token(), test_websocket_pairing_rejects_wrong_token(), test_websocket_ping_command(), test_websocket_unknown_command()

### Community 476 - "register_admin_gui"
Cohesion: 0.14
Nodes (19): register_admin_gui(), dashboard(), diag_langfuse(), _guest_redirect(), login_page(), login_submit(), _redirect(), save_public_url() (+11 more)

### Community 477 - "github_tools.py"
Cohesion: 0.18
Nodes (13): get_repo(), _get_token(), _get_user(), init_workspace(), list_branches(), list_prs(), list_repos(), _uid() (+5 more)

### Community 479 - "secrets_store.py"
Cohesion: 0.14
Nodes (9): create_secret(), delete_secret(), get_secret_metadata(), get_secrets_store(), _get_user(), list_secrets(), SecretCreateRequest, _uid() (+1 more)

### Community 480 - "note_phase_start"
Cohesion: 0.10
Nodes (14): _note_phase_end(), _note_phase_start(), note_phase_end(), note_phase_start(), _now(), open_phase_report(), test_a_phase_that_completed_is_no_longer_reported(), test_an_open_phase_is_reported_as_the_stall_with_its_real_duration() (+6 more)

### Community 482 - "Findings"
Cohesion: 0.09
Nodes (22): E2E Tests, Findings, Immediate (Current Sprint), Integration Tests, Live/External Tests (skipped in standard CI), Missing Test Areas, Sprint 1, Sprint 2 (+14 more)

### Community 483 - "openclaw_str_e_fix.py"
Cohesion: 0.15
Nodes (12): _find_unsafe_str_call(), find_unsafe_str_calls(), visit_ExceptHandler(), fix_file(), fix_source(), _is_broad_except(), _is_http_exception_call(), iter_target_files() (+4 more)

### Community 484 - "Deploy: FreeBuff Telegram bot (24×7)"
Cohesion: 0.09
Nodes (21): Agents, Environment variables, `/freebuff <task>`, Running 24×7, Telegram phone control, 1. Create the Telegram bot, 1. Hit the diagnostic endpoint, 2. Deploy (+13 more)

### Community 485 - "test_fabric_patterns.py"
Cohesion: 0.09
Nodes (6): Fixed, _get_github_token_for_user(), Fixed, test_new_scaffolds_pattern(), test_save_and_show_roundtrip(), echo()

### Community 486 - "Workspace Isolation Architecture"
Cohesion: 0.09
Nodes (12): Configuration, Directory Layout, Error Handling, Lifecycle States, Metrics, Overview, Path Derivation, Path Safety (+4 more)

### Community 487 - "Telegram Bot Setup"
Cohesion: 0.08
Nodes (24): Admin commands (immediate, no confirmation), Admin commands with approval required, Approval Workflow, Authorization Model, Command Reference, Debugging message delivery, Debugging proxy connection failures, Linux (systemd) (+16 more)

### Community 488 - "SetupWizardPage.js"
Cohesion: 0.09
Nodes (33): completeSetup(), createSecret(), detectHardwareForSetup(), detectModelsForSetup(), getAccessToken(), getApiUrl(), getAuthHeaders(), getBackendUrl() (+25 more)

### Community 489 - "knowledgeGraphTab.test.js"
Cohesion: 0.11
Nodes (16): { describe, test, expect }, fs, path, src, apiSource, { describe, test, expect }, fs, path (+8 more)

### Community 490 - "implement_agent.py"
Cohesion: 0.08
Nodes (13): build_tool_calling_router(), main(), _nvidia_candidates(), _openai_tools_to_anthropic(), _read_claude_md(), router_turn(), router_without(), _run_anthropic_agent_loop() (+5 more)

### Community 491 - "test_north_mini_code.py"
Cohesion: 0.09
Nodes (7): north_mini_code_model_for(), test_flag_default_is_on(), test_internal_agent_consults_coding_resolver(), test_north_does_not_displace_default_coder(), test_north_mini_code_model_for_maps_only_serving_providers(), test_north_registered_in_router_registry(), test_reasoning_effort_setting_validates_value()

### Community 492 - "test_key_pool.py"
Cohesion: 0.08
Nodes (6): api_keys_for(), reset(), _clean_pool(), TestApiKeysFor, TestDigestIsKeyed, TestRotationIsOptIn

### Community 493 - "TrafficDirector"
Cohesion: 0.11
Nodes (4): get_director(), TrafficDirector, TestAccounting, TestOverBudget

### Community 494 - "AgentMessageBus"
Cohesion: 0.12
Nodes (3): AgentMessageBus, get_agent_bus(), TestAgentMessageBus

### Community 496 - "_get"
Cohesion: 0.08
Nodes (9): reset_kv_state(), _get(), one_configured_provider(), TestDisabledReasonIsReadableNextToTheSwitch, TestListing, TestSwitch, isolated_state(), _live_mongo_url() (+1 more)

### Community 497 - "TestCapabilitiesAreNotClaimedWithoutEvidence"
Cohesion: 0.24
Nodes (3): _names_exactly(), TestCapabilitiesAreNotClaimedWithoutEvidence, TestTheAbsentIdsCannotComeBack

### Community 498 - "_plan"
Cohesion: 0.13
Nodes (4): _plan(), TestItFailsClosed, TestTheCli, TestTheRejectIsHonoured

### Community 499 - "test_mostly_failed_steps.py"
Cohesion: 0.12
Nodes (11): _make_result(), _make_step(), test_all_failed_marks_task_failed(), test_blocked_verdict_always_fails(), test_exact_75_percent_with_2_applied_fails(), test_failure_summary_in_output(), test_few_steps_not_gated(), test_majority_applied_marks_task_success() (+3 more)

### Community 500 - "test_webui_provider_priority.py"
Cohesion: 0.07
Nodes (34): AdminIdentity, _fake_user_auth(), test_admin_can_create_anthropic_provider_via_webui_admin_api(), test_admin_can_create_provider_via_webui_admin_api(), test_ui_providers_and_workspaces_use_app_state(), _bootstrap(), _reset_brain_singletons(), test_admin_policy_brain_returns_resolution_and_paid_state() (+26 more)

### Community 501 - "_client"
Cohesion: 0.13
Nodes (4): _client(), _FakeGitHub, TestAuthoringEndpoints, TestProposePolicyChange

### Community 502 - "AdaptivePermissions"
Cohesion: 0.18
Nodes (11): AdaptivePermissions, PermissionAssessment, _msgs(), test_assessment_as_dict(), test_confidence_increases_with_more_signals(), test_full_access_from_risky_signals(), test_has_write_permission_false(), test_has_write_permission_true() (+3 more)

### Community 503 - "RegistrySkill"
Cohesion: 0.16
Nodes (3): _fmt_name(), RegistrySkill, TestRegistrySkill

### Community 506 - "FinancialMetrics"
Cohesion: 0.13
Nodes (9): FinancialMetrics, test_metrics_burn_rate(), test_metrics_burn_rate_negative_when_profitable(), test_metrics_gross_margin(), test_metrics_gross_margin_zero_when_no_revenue(), test_metrics_runway_infinite_when_profitable(), test_metrics_runway_months(), test_metrics_runway_zero_when_no_cash() (+1 more)

### Community 507 - "analyze_qualitative"
Cohesion: 0.11
Nodes (14): analyze_qualitative(), Architecture, As a Python library, Auto-Registration, Files, Purpose, Sample-Size Math, See Also (+6 more)

### Community 508 - "compare_runtimes.py"
Cohesion: 0.11
Nodes (11): compare(), main(), render(), _run_one(), RunRecord, RuntimeSummary, _validate_tasks(), _immediate() (+3 more)

### Community 509 - "test_agent_chat_integration.py"
Cohesion: 0.13
Nodes (14): _fake_auth(), _fake_run_result(), _make_nim_providers(), test_agent_chat_passes_session_store_to_runner(), run(), test_agent_chat_persists_history_across_calls(), run(), test_agent_chat_result_includes_judge_verdict() (+6 more)

### Community 510 - "test_v4_api.py"
Cohesion: 0.12
Nodes (10): test_v4_improvements_resolve_nonexistent(), test_v4_improvements_returns_200(), test_v4_quick_notes_returns_200(), test_v4_quick_notes_submit_invalid(), test_v4_rejects_anonymous_callers(), test_v4_report_bug_invalid(), test_v4_scheduler_jobs_returns_200(), test_v4_status_returns_200() (+2 more)

### Community 511 - "provider_max_rpm"
Cohesion: 0.10
Nodes (12): Pre-call budget checks, provider_max_parallel(), provider_max_rpm(), provider_max_tpm(), _provider_positive_float(), provider_weight(), test_infinite_and_nan_return_none(), test_non_numeric_returns_none() (+4 more)

### Community 512 - "AuditLog"
Cohesion: 0.04
Nodes (23): _resolve_jwt_secret(), AuditEvent, AuditLog, scrub(), _scrub_inner(), TestCardRedaction, TestNestedAndEventIntegration, TestNonPIIPreserved (+15 more)

### Community 513 - "_Cursor"
Cohesion: 0.10
Nodes (3): _apply_projection(), _Cursor, _PendingCursor

### Community 514 - "context_plan_gate.py"
Cohesion: 0.12
Nodes (9): evaluate(), evaluate_path(), main(), _parse_args(), PlanDecision, read_has_source(), read_source_fetched(), read_unmet_rules() (+1 more)

### Community 515 - "WindowsServiceManager"
Cohesion: 0.19
Nodes (3): _creationflags(), ServiceState, WindowsServiceManager

### Community 517 - "ProviderCircuit"
Cohesion: 0.15
Nodes (3): ProviderCircuit, TestProviderCircuit, TestNimPoolCountsRateLimitsAsFailures

### Community 520 - "_SlowLoginPage"
Cohesion: 0.08
Nodes (4): _ExpectResponse, _Loc, _SlowLoginPage, TestBrowserLogin

### Community 521 - "test_crispy_burn_in.py"
Cohesion: 0.08
Nodes (12): test_burn_in_cli_offline_mode_exits_1_when_not_ready(), test_burn_in_cli_offline_mode_reads_json(), test_evaluate_burn_in_accepts_other_failure_types(), test_evaluate_burn_in_exact_threshold_meets(), test_evaluate_burn_in_fails_on_insufficient_runs(), test_evaluate_burn_in_fails_on_low_success_rate(), test_evaluate_burn_in_fails_on_phase_sequence_error(), test_evaluate_burn_in_fails_on_short_window() (+4 more)

### Community 522 - "test_v3_auth.py"
Cohesion: 0.19
Nodes (10): _configured_v3_email(), _configured_v3_password(), test_v3_auth_login_endpoint(), test_v3_auth_login_invalid_credentials(), test_v3_auth_logout_endpoint(), test_v3_auth_me_endpoint(), test_v3_auth_me_invalid_token(), test_v3_auth_me_missing_token() (+2 more)

### Community 523 - "plan_research"
Cohesion: 0.21
Nodes (3): plan_research(), _sample_size_for_proportion(), TestPlanResearch

### Community 525 - "🧭 Product Manager Agent"
Cohesion: 0.10
Nodes (20): 💬 Communication Style, 🎯 Core Mission, 🚨 Critical Rules, Go-to-Market Brief, 🧠 Identity & Memory, Opportunity Assessment, 🎭 Personality Highlights, Phase 1 — Discovery (+12 more)

### Community 526 - "test_admin_local_brain_router.py"
Cohesion: 0.15
Nodes (13): build_admin_local_brain_router(), get_admin_local_brain_state(), post_admin_local_brain_toggle(), _require_admin(), _store(), _make_app(), test_get_state_admin_returns_documented_shape(), test_get_state_non_admin_returns_403() (+5 more)

### Community 527 - "Tween"
Cohesion: 0.15
Nodes (25): _a(), _assertThisInitialized(), cb(), dc(), Fo(), ga(), gb(), ha() (+17 more)

### Community 528 - "V3 API Migration Plan — LLM Relay Platform"
Cohesion: 0.10
Nodes (20): Acceptance Checks, Approach, Auth Flow (v3 JWT-based), Backward Compatibility, Current State Analysis, Data Model Changes, Database/Storage, Files to Create/Modify (+12 more)

### Community 529 - "test_telegram_diag_endpoint.py"
Cohesion: 0.09
Nodes (9): test_telegram_diag_flags_dead_poller_and_set_webhook(), test_telegram_diag_has_diagnostic_hints(), test_telegram_diag_masks_token(), test_telegram_diag_no_auth_required(), test_telegram_diag_reports_healthy_poller_and_no_webhook(), test_telegram_diag_returns_200(), test_telegram_diag_returns_config_snapshot(), test_telegram_diag_survives_webhook_lookup_failure() (+1 more)

### Community 530 - "test_openclaw_str_e_fix.py"
Cohesion: 0.10
Nodes (3): test_bare_except_cannot_be_fixed_and_is_left_untouched(), test_broad_except_but_4xx_is_left_untouched(), test_detail_not_wrapping_the_caught_exception_is_left_untouched()

### Community 531 - "_make_mock_response"
Cohesion: 0.12
Nodes (14): _catalogue_preset(), _make_mock_response(), test_merge_surfaces_404_for_unknown_pr(), _fake_post(), test_merge_surfaces_422_refusal(), _fake_post(), test_merge_surfaces_success_with_sha_and_actor(), _fake_post() (+6 more)

### Community 532 - "test_unit8_model_catalog.py"
Cohesion: 0.02
Nodes (53): _brain_provider_status(), all_provider_ids(), _provider_ids_from_literal(), provider_key_present(), CatalogActiveBrain, CatalogMirror, CatalogProviderEntry, get_catalog() (+45 more)

### Community 533 - "operational_incidents.py"
Cohesion: 0.12
Nodes (12): _record_operational(), _diagnose_and_file(), _file_incident(), _format_incident(), get_operational_incident_tracker(), OperationalIncident, record_operational_error(), _render_section() (+4 more)

### Community 534 - "The fifteen strategies"
Cohesion: 0.10
Nodes (20): adaptive *(default)*, automatic_failover, Candidate selection, context_length_optimized, cost_optimized, highest_success_rate, least_loaded, LLM Router — routing guide (+12 more)

### Community 535 - "_rrf"
Cohesion: 0.20
Nodes (8): _rrf(), Already covered — no work needed, External learnings audit — 2026-09-26, Gaps still open, Shipped in this change, test_rrf_merges_two_rankings(), test_rrf_scores_descending(), test_rrf_single_ranking_preserves_order()

### Community 536 - "_extract_tech_relevance"
Cohesion: 0.16
Nodes (4): _extract_tech_relevance(), TEST-003 [MEDIUM] — Placeholder Tests with `pass`, TestExtractTechRelevance, TestRecommendLogic

### Community 537 - "register_user_research_tools"
Cohesion: 0.16
Nodes (6): register_user_research_tools(), user_research_plan_tool(), user_research_qual_tool(), user_research_quant_tool(), user_research_synthesize_tool(), TestRegistration

### Community 538 - "Skill: modularity-review"
Cohesion: 0.10
Nodes (19): Acceptance Checks, Applying to This Repo, Further Reading, Modularity Findings Template, Part A: Reviewing Existing Code for Modularity Problems, Part B: Designing New Modular Boundaries, Skill: modularity-review, Step 1 — Map the dependency graph (+11 more)

### Community 539 - "Design Audit"
Cohesion: 0.10
Nodes (19): Code Quality, Color and Surfaces, Component Patterns, Content, Design Audit, Fix Priority, How This Works, Iconography (+11 more)

### Community 540 - "Findings"
Cohesion: 0.10
Nodes (19): API Documentation, Architecture Documentation, DOC-001 [HIGH] — No SECURITY.md, DOC-002 [HIGH] — No CONTRIBUTING.md, DOC-003 [HIGH] — No API.md / OpenAPI Export, DOC-004 [MEDIUM] — README.md is 31KB and Needs Pruning, DOC-005 [MEDIUM] — `REVIEW_AND_FIXES.md` and `AGENCY_CORE_V5_PROGRESS.md` are Unclear, DOC-006 [MEDIUM] — No DEPLOYMENT.md at Root (+11 more)

### Community 541 - "la"
Cohesion: 0.28
Nodes (9): Aa(), Animation(), Ca(), Da(), la(), na(), Ua(), Va() (+1 more)

### Community 542 - "Skill: modularity-review"
Cohesion: 0.10
Nodes (19): Acceptance Checks, Applying to This Repo, Further Reading, Modularity Findings Template, Part A: Reviewing Existing Code for Modularity Problems, Part B: Designing New Modular Boundaries, Skill: modularity-review, Step 1 — Map the dependency graph (+11 more)

### Community 543 - "crispy_client.py"
Cohesion: 0.14
Nodes (9): cmd_approve(), cmd_artifacts(), cmd_build(), cmd_events(), cmd_reject(), cmd_status(), cmd_watch(), _get() (+1 more)

### Community 544 - "4. Troubleshooting"
Cohesion: 0.10
Nodes (19): 1. Which sandbox backend applies where, 2. Container hardening, 3. Supply chain, 4. Troubleshooting, 5. Scaling, Agents suddenly failing after enabling enforcement, An agent is stuck, Applying the overlay to the local stack (+11 more)

### Community 545 - "allow_paid"
Cohesion: 0.05
Nodes (39): 1. Mission & operating principles, 2. Brain policy (free cloud LLMs), 3. The Gate Matrix (core artifact), 7. Definition of "fully autonomous" — acceptance criteria, 8. Safety invariants (carried from `agent/CLAUDE.md`), 🟢 Autonomous — run, then notify-only, Autonomy Charter — Telegram-Gated Self-Running Agency, 🔵 Notify-only FYI — no action required (+31 more)

### Community 546 - "The rules"
Cohesion: 0.11
Nodes (17): Changing these rules, How the gate behaves, Quick-Note Context Rulebook, R10 — Use the repository's real identity **[gate]**, R11 — Name a real integration point **[gate]**, R12 — Mark epistemic status at the claim **[review]**, R13 — Account for what the repository already has **[gate]**, R14 — Paths cited in prose must exist **[gate]** (+9 more)

### Community 547 - "PortfolioScreen.jsx"
Cohesion: 0.15
Nodes (19): getPortfolioBoard(), refreshPortfolio(), btnStyle, HEALTH, HORIZONS, InitiativeCard(), PortfolioScreen(), SectionLabel() (+11 more)

### Community 548 - "infra_cost.py"
Cohesion: 0.15
Nodes (8): compute_request_cost(), _float_env(), get_infra_config(), InfraConfig, load_infra_config(), project_session_cost(), RequestInfraCost, SessionCostProjection

### Community 550 - "Autonomous AI Agency"
Cohesion: 0.10
Nodes (20): An AI company that runs itself, on your servers., Architecture, security, license, Autonomous AI Agency, Autonomy with a leash, Contributing, Don't trust it, check the proof, Everything it does, Honest model economics (+12 more)

### Community 551 - "build_workflow.py"
Cohesion: 0.30
Nodes (15): _c(), _get(), _header(), main(), _make_headers(), _phase_icon(), _post(), _print_phases() (+7 more)

### Community 552 - "LLM Router — migration guide"
Cohesion: 0.08
Nodes (21): ADR-008: LLMRouter — the single multi-provider routing gateway, Comparison with OmniRoute, Consequences, Context, Differences — why a port was rejected, Incompatible components (explicitly rejected), References, Reusable components (ideas adopted) (+13 more)

### Community 553 - "test_gateway_hygiene.py"
Cohesion: 0.05
Nodes (17): _BodyTooLarge, _declared_length(), GatewayHygieneMiddleware, send_wrapper(), get_request_id(), _limit_receive(), limited(), sanitize_request_id() (+9 more)

### Community 555 - "FakeResp"
Cohesion: 0.13
Nodes (7): FakeResp, TestGithubAndResearch, fake_get(), TestGithubSignalHardening, fake_get(), fake_get(), fake_get()

### Community 556 - "TestSourceGate"
Cohesion: 0.12
Nodes (4): _load(), TestImplementSideGate, TestParse, TestSourceGate

### Community 558 - "test_tasks_cache_ttl_env.py"
Cohesion: 0.21
Nodes (12): _reload_tasks_api_with_env(), test_above_cap_falls_back_to_default(), test_at_cap_is_honored(), test_cap_value_env_override_changes_module_constant(), test_default_ttl_is_eight_seconds_when_env_unset(), test_infinity_value_falls_back_to_default(), test_lower_cap_rejects_value_above_it(), test_nan_value_falls_back_to_default() (+4 more)

### Community 559 - "mcp_registry.py"
Cohesion: 0.10
Nodes (15): get_mcp_client(), _code_graph_configured(), _code_graph_spec(), _internal_configured(), list_specs(), MCPServerSpec, _not_dialable(), _playwright_configured() (+7 more)

### Community 560 - "agile_api.py"
Cohesion: 0.21
Nodes (12): complete_sprint(), create_sprint(), _get_mgr(), get_velocity(), list_sprints(), _require_auth(), _sprint_to_dict(), SprintCreateRequest (+4 more)

### Community 561 - "PerformanceAnalytics"
Cohesion: 0.12
Nodes (7): build_report(), PerformanceAnalytics, test_build_report_assembles_all_sections(), test_performance_cycle_time_delta_negative_when_ai_faster(), test_performance_cycle_time_delta_none_without_both_cohorts(), test_performance_defect_rate_filters_by_cohort(), test_performance_summary_shape()

### Community 562 - "Skill: fabric-patterns"
Cohesion: 0.11
Nodes (18): 1. Ensure Pattern Directory Exists, 2. List Available Patterns, 3. Retrieve a Pattern, 4. Apply a Pattern with Variables, 5. Stitch Patterns Together, 6. Create New Patterns, Acceptance Checks, Directory Structure (+10 more)

### Community 563 - "Analysis & Synthesis Instructions"
Cohesion: 0.11
Nodes (18): 1. Define the Atmosphere, 2. Map the Color Palette, 3. Establish Typography Rules, 4. Define the Hero Section, 5. Describe Component Stylings, 6. Define Layout Principles, 7. Define Responsive Rules, 8. Encode Motion Philosophy (+10 more)

### Community 564 - "Performance Analysis — local-llm-server"
Cohesion: 0.08
Nodes (25): 1. Rate Limiter Performance, 2. Ollama Connection Handling, 3. Model Router Performance, 4. Agent Execution Performance, 5. Backend Server Performance, 6. Frontend Performance, 7. Streaming Performance, PERF-001 [HIGH] — Synchronous Lock in Async Context (+17 more)

### Community 565 - "Production Readiness Assessment — local-llm-server"
Cohesion: 0.11
Nodes (18): 1. Availability & Reliability, 2. Observability, 3. Deployment Architecture, 4. Configuration & Secrets, 5. Recovery & Backup, 6. Cloudflare Worker Audit, Current State, Current State (+10 more)

### Community 566 - "TestNormalizeResponseFormat"
Cohesion: 0.08
Nodes (4): _normalize_response_format(), _get_model_map(), TestModelsEndpointAliases, TestNormalizeResponseFormat

### Community 567 - "Skill: fabric-patterns"
Cohesion: 0.11
Nodes (18): 1. Ensure Pattern Directory Exists, 2. List Available Patterns, 3. Retrieve a Pattern, 4. Apply a Pattern with Variables, 5. Stitch Patterns Together, 6. Create New Patterns, Acceptance Checks, Directory Structure (+10 more)

### Community 568 - "Admin Dashboard Guide"
Cohesion: 0.11
Nodes (19): Accessing the Dashboard, Admin API (Programmatic Access), Admin Dashboard Guide, Dashboard — healthy state, Dashboard — key created (one-time token flash), Dashboard — Langfuse diagnostic, Dashboard Layout, Login page (+11 more)

### Community 569 - "Agent Orchestration Design"
Cohesion: 0.05
Nodes (35): Agent Orchestration Design, Execution Pathway, Four-Agent Structure, Key Invariants, OSS Inspirations (Clean-Room), Overview, Plan-First Pathway, Release-Readiness Pathway (+27 more)

### Community 570 - "verify_token"
Cohesion: 0.12
Nodes (11): test_invalid_refresh_token(), test_invalid_token_type(), test_refresh_access_token(), test_refresh_token_creation(), test_token_creation_and_verification(), create_tokens(), _get_secret(), refresh_access_token() (+3 more)

### Community 571 - "ChatScreen.jsx"
Cohesion: 0.15
Nodes (19): chatSend(), getAgentChatJob(), getSession(), listProviderModels(), listProviders(), listSessions(), AgentPicker(), AgentProgressPanel() (+11 more)

### Community 572 - "ControlsScreen.jsx"
Cohesion: 0.18
Nodes (16): getPlatformControls(), resetPlatformControl(), setPlatformControls(), { getPlatformControls, setPlatformControls, resetPlatformControl }, secondGroup, BANNER(), ControlGroup(), ControlRow() (+8 more)

### Community 573 - "scripts/doctor.py"
Cohesion: 0.27
Nodes (15): Check, check_core_deps(), check_env(), check_git(), check_mongo(), check_node(), check_ollama(), check_python() (+7 more)

### Community 574 - "Screens"
Cohesion: 0.11
Nodes (19): 🛡 Admin — users & access, 🤖 Agents — autonomous team, 💬 Chat — unified assistant, 🏢 Company — operating context, 📊 Dashboard — system overview, 🩺 Doctor — diagnostics, 🐙 GitHub — repos & PRs, 📈 Intelligence — trends & competitors (+11 more)

### Community 575 - "run_proxy.sh"
Cohesion: 0.11
Nodes (15): run_ollama.sh script, AIDER_BASE_URL, GOOSE_BASE_URL, HERMES_BASE_URL, LOG_LEVEL, OLLAMA_BASE, OPENCODE_BASE_URL, PROXY_PORT (+7 more)

### Community 577 - "test_autonomy_status.py"
Cohesion: 0.12
Nodes (6): test_brain_configured_when_nvidia_key_present(), test_brain_configured_with_ollama_fallback(), test_loop_readiness_is_surfaced(), test_no_brain_when_nvidia_key_absent(), test_self_bootstrap_never_awaited_inline(), test_status_is_public_and_well_shaped()

### Community 578 - "test_pr923_fixes.py"
Cohesion: 0.07
Nodes (16): _deferred_startup_cleanup(), nuclear_cleanup(), FakeDB, FakeDeleteResult, FakeScheduleCollection, test_brain_resolver_has_ollama_preference_guard(), test_chat_agent_run_budget_default_is_600(), test_company_agency_create_passes_description() (+8 more)

### Community 579 - "sync_readme_gallery.py"
Cohesion: 0.20
Nodes (11): main(), _out_dir(), build_gallery(), GallerySection, main(), replace_gallery_block(), Screenshot, sync_readme_gallery() (+3 more)

### Community 580 - "get_db"
Cohesion: 0.03
Nodes (64): auth_me(), auto_recommend_skills(), brain_failover_status(), _check_storage_health(), cost_attribution_stats(), discover_remote_skills(), doctor_health(), get_active_provider() (+56 more)

### Community 581 - "sam_livekit_worker.py"
Cohesion: 0.14
Nodes (9): get_livekit_config(), LiveKitConfig, _build_llm(), _build_stt(), _build_tts(), entrypoint(), main(), _require_livekit_agents() (+1 more)

### Community 582 - "validate_session_id"
Cohesion: 0.16
Nodes (3): TestSessionIdValidation, TestNoInternalPathLeakage, validate_session_id()

### Community 583 - "_register_code_graph_tools"
Cohesion: 0.11
Nodes (11): _register_code_graph_tools(), _code_impact_tool(), _code_search_tool(), _code_trace_tool(), graph_for(), get_code_graph(), _mode(), run_query() (+3 more)

### Community 584 - "refine"
Cohesion: 0.17
Nodes (6): propose_entries(), refine(), _lesson(), TestProposal, TestRefineGate, TestReviewRegressions

### Community 585 - "Test Automation Engineer"
Cohesion: 0.11
Nodes (17): 🚀 Advanced Capabilities, CI: Sharded, Traced, Merge-Blocking (GitHub Actions), 🚨 Critical Rules You Must Follow, Deterministic Playwright Test (No Sleeps, API Setup, Role Selectors), Flake Triage Table, Framework Depth, 🔄 Learning & Memory, Suite Operations at Scale (+9 more)

### Community 586 - "Comprehensive Skill Index (By Category)"
Cohesion: 0.11
Nodes (17): 10. Domain (Modelling, Training, Infra), 1. Planning and Implementation, 2. Code Quality, Architecture, and Audits, 3. State Management and Git Flow, 4. Memory, Knowledge, and Context Tuning, 5. Research, Browsing, and External Intel, 6. Session Lifecycle and Workflow, 7. Style and Craft Polish (UI / Docs / Tone) (+9 more)

### Community 587 - "Agent Skill: Principal UI/UX Architect & Motion Choreographer (Awwwards-Tier)"
Cohesion: 0.11
Nodes (17): 1. Meta Information & Core Directive, 2. THE "ABSOLUTE ZERO" DIRECTIVE (STRICT ANTI-PATTERNS), 3. THE CREATIVE VARIANCE ENGINE, 4. HAPTIC MICRO-AESTHETICS (COMPONENT MASTERY), 5. MOTION CHOREOGRAPHY (FLUID DYNAMICS), 6. PERFORMANCE GUARDRAILS, 7. EXECUTION PROTOCOL, 8. PRE-OUTPUT CHECKLIST (+9 more)

### Community 588 - "Architecture Overview — local-llm-server"
Cohesion: 0.11
Nodes (18): `admin_auth.py` + `admin_gui.py`, `agent/`, Architecture Overview — local-llm-server, `chat_handlers.py`, Deployment, Feature Maturity Tiers, `handlers/anthropic_compat.py`, High-Level Architecture (+10 more)

### Community 589 - "Feature Guide"
Cohesion: 0.11
Nodes (18): 10. Langfuse Observability, 11. Coding Agent API, 12. Browser Admin UI, 13. Telegram Remote Control Bot, 14. Tunnel — Permanent Static URL via ngrok, 15. CORS Support, 16. Streaming Support, 17. Workspace Isolation (+10 more)

### Community 590 - "_test_e2e_telegram_approval"
Cohesion: 0.10
Nodes (10): admin_jwt(), _approve_execution_via_rest(), _delete_task(), _extract_admin_token(), _login_admin(), _looks_like_admin_token(), _poll_task_execution_approved(), _seed_requires_approval_task() (+2 more)

### Community 591 - "get_skill_bindings"
Cohesion: 0.09
Nodes (14): What already exists (don't rebuild), build_matrix(), _families(), main(), render_markdown(), _test_evidence_index(), get_skill_bindings(), test_publicly_advertised_skill_is_registered() (+6 more)

### Community 592 - "Delegation Plan (agent-ready work packages)"
Cohesion: 0.11
Nodes (18): Delegation Plan (agent-ready work packages), Findings, http://127.0.0.1:8899/, Page Details (worst first), Pillar Scores, `seo-fix-canonicals` - Fix Canonicals findings: 1 finding type(s) across 1 URL hit(s), `seo-fix-content` - Fix Content findings: 1 finding type(s) across 1 URL hit(s), `seo-fix-geo` - Fix GEO findings: 5 finding type(s) across 5 URL hit(s) (+10 more)

### Community 593 - "test_task_source_id_race.py"
Cohesion: 0.14
Nodes (9): _is_duplicate_key_error(), _FakeDuplicateKeyError, _mock_mongo_db(), test_create_recovers_from_lost_race_via_duplicate_key_error(), test_create_reraises_non_duplicate_errors(), test_create_without_source_id_reraises_duplicate_key_error(), test_is_duplicate_key_error_false_for_unrelated_error(), test_is_duplicate_key_error_matches_by_class_name() (+1 more)

### Community 595 - "_reject"
Cohesion: 0.15
Nodes (5): _reject(), TestR13PriorArt, TestR14ProsePaths, TestReviewGate, TestSourceSlug

### Community 598 - "TestModelRegistryUpdates"
Cohesion: 0.13
Nodes (3): TestModelRegistryUpdates, _load(), TestTelegramApprovalE2E

### Community 599 - "TestOrchestratorQueue"
Cohesion: 0.13
Nodes (3): TestOrchestratorQueue, _worker(), _failing()

### Community 600 - "_P"
Cohesion: 0.19
Nodes (3): _ids(), _P, TestOrdering

### Community 602 - "_redact_for_notification"
Cohesion: 0.11
Nodes (12): 4. Telegram gate protocol, _redact_for_notification(), _FakeResponse, _make_task(), TestNotifyWebhookActuallyFires, fake_post(), TestNotifyWebhookRedaction, fake_post() (+4 more)

### Community 603 - "TestUpdateTask"
Cohesion: 0.18
Nodes (3): _NoopCheckpointStore, _run(), TestUpdateTask

### Community 605 - "cowork_session.py"
Cohesion: 0.15
Nodes (3): ContributorState, SessionPhase, SessionRole

### Community 607 - "Page"
Cohesion: 0.12
Nodes (4): TestAgents, TestChat, TestRuntimes, TestSettings

### Community 608 - "Salesforce Architect"
Cohesion: 0.12
Nodes (16): 🚀 Advanced Capabilities, Agentforce Architecture, Architecture Decision Record (ADR), 🚨 Critical Rules You Must Follow, Data Model Review Checklist, Governor Limit Budget, Integration Pattern Template, Multi-Cloud Data Architecture (+8 more)

### Community 609 - "SKILL: Industrial Brutalism & Tactical Telemetry UI"
Cohesion: 0.12
Nodes (16): 1. Skill Meta, 2.1 Swiss Industrial Print, 2.2 Tactical Telemetry & CRT Terminal, 2. Visual Archetypes, 3.1 Macro-Typography (Structural Headers), 3.2 Micro-Typography (Data & Telemetry), 3.3 Textural Contrast (Artistic Disruption), 3. Typographic Architecture (+8 more)

### Community 610 - "Skill: data-quality-audit"
Cohesion: 0.12
Nodes (16): 1. Token Length Distribution, 2. Deduplication Check, 3. Tokenizer Fertility Check, 4. Special Token Consistency, 5. Language Detection (if langdetect available), 6. Content Quality Signals, Background (Why This Matters), Checks Performed (+8 more)

### Community 611 - "What "Slop" Looks Like"
Cohesion: 0.12
Nodes (16): Acceptance Checks, Category 1 — Obvious Comments, Category 2 — Phantom Abstractions, Category 3 — Defensive Checks for Impossible Cases, Category 4 — Speculative Generality, Category 5 — Verbose Variable Names, Category 6 — Unasked-For Boilerplate, Instructions (+8 more)

### Community 612 - "WorkflowScreen.jsx"
Cohesion: 0.19
Nodes (15): approveWorkflow(), buildWorkflow(), cancelWorkflow(), getWorkflowRun(), getWorkflowRuns(), rejectWorkflow(), Badge(), btn() (+7 more)

### Community 613 - "Traffic Distribution Across Providers"
Cohesion: 0.12
Nodes (11): A worked example, Attribution, Configuration, Failure behaviour, Observability, Provider ids contain dashes, Strategies, The problem this solves (+3 more)

### Community 614 - "Separate hosted dashboard backend (`backend/server.py`)"
Cohesion: 0.12
Nodes (17): Agent and workflow surfaces, AI gateway (`packages/gateway/api.py`), API Surfaces and Route Map, Built-in admin and web UI, Connectors (`/api/connectors/*`, `backend/connectors_api.py`, admin-only), Control-plane style routers mounted in the proxy, CRISPY Workflow engine (`/api/workflow/*`, `workflow/api.py`, admin-only), Executive advisory (`/api/executives/*`, `backend/executive_advisory_api.py`) (+9 more)

### Community 615 - "Section-by-Section Acceptance Criteria"
Cohesion: 0.12
Nodes (16): 467 Final Acceptance Criteria, §A — Company Graph + Onboarding, §B — 34 Specialist Families, §C — ECC, Obsidian, Graphify, Council Review Wiring, §D — Direct Chat as Control Center, Definition of Done, §E — Workflow Engine as Canonical Backbone + Worktree Isolation, §F — Doctor Full Check List (+8 more)

### Community 616 - "Dynamic Model Routing"
Cohesion: 0.06
Nodes (25): Architecture, Built-in Claude → local alias table, Configuring fast_response routing, Configuring model preferences, Curl example, Dynamic Model Routing, Fallback execution, How automatic selection works (+17 more)

### Community 617 - "McpCard"
Cohesion: 0.17
Nodes (13): getRenderHealth(), getRenderOpsStatus(), runRenderOpsScan(), api, view(), BTN, McpCard(), NOTE() (+5 more)

### Community 618 - "test_p0_roadmap_a4_a5_b2.py"
Cohesion: 0.17
Nodes (5): PrioritizedTask, Priority, TestPrioritizedTask, TestPriority, TestSteeringSingleton

### Community 619 - "agent_readiness_audit.py"
Cohesion: 0.21
Nodes (14): _grade(), main(), PillarResult, ReadinessReport, run_audit(), score_build_system(), score_dev_environment(), score_documentation() (+6 more)

### Community 620 - "sync_ngrok.py"
Cohesion: 0.24
Nodes (10): detect_ngrok_url(), dim(), fail(), header(), info(), main(), ok(), patch_platform_brain_via_switch_brain() (+2 more)

### Community 621 - "test_ci.sh"
Cohesion: 0.15
Nodes (16): ADMIN_EMAIL, ADMIN_PASSWORD, API_KEYS, cleanup(), DB_NAME, fail(), LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY (+8 more)

### Community 622 - "FakeRunner"
Cohesion: 0.18
Nodes (3): FakeRunner, runner(), TestWarmUp

### Community 623 - "test_shared_state.py"
Cohesion: 0.05
Nodes (18): claim(), cooldown_clear(), cooldown_get(), cooldown_set(), _get_backend(), incr_window(), _InMemoryBackend, release() (+10 more)

### Community 625 - "Fixed"
Cohesion: 0.06
Nodes (20): Fixed, Fixed, task(), _select_brain(), brain_candidates(), call_brain_with_failover(), build_body(), _failures() (+12 more)

### Community 626 - "_migration_block"
Cohesion: 0.15
Nodes (3): _migration_block(), TestTheCatalogueNamesOnlyProbedGroqIds, TestTheMigrationWritesOnlyLiveModels

### Community 628 - "test_frontend_deployment_guards.py"
Cohesion: 0.18
Nodes (10): _read(), test_api_redirects_respect_public_and_backend_paths(), test_index_css_checkbox_override_is_not_none(), test_index_css_checkbox_uses_auto_appearance(), test_index_css_restores_checkbox_appearance(), test_login_page_links_to_bootstrap_when_backend_is_missing(), test_oauth_origin_uses_current_backend_configuration(), test_public_bootstrap_route_exists_for_prelogin_setup() (+2 more)

### Community 629 - "traffic_director.py"
Cohesion: 0.13
Nodes (5): routing_strategy(), active_strategy(), provider_id_of(), reset(), _clean_director()

### Community 630 - "test_skill_registry.py"
Cohesion: 0.09
Nodes (7): _TechPattern, _FakeClient, _FakeResp, test_local_skills_dir_defaults_to_repo_root_not_cwd(), test_nested_registry_indexes_deeply_nested_skills(), TestPreCompiledPatterns, TestWorkflowSkillMap

### Community 631 - "test_task_service_failed_comment.py"
Cohesion: 0.21
Nodes (7): coordinator(), _make_result(), sample_task(), test_failed_result_posts_agent_comment(), test_failed_result_sets_error_message(), test_failed_result_without_comment_still_fails(), test_success_result_posts_agent_comment()

### Community 633 - "handle_workflow_ide_chat"
Cohesion: 0.15
Nodes (8): _extract_last_user_message(), handle_workflow_ide_chat(), _json_response(), _single_token_stream(), _sse_chunk(), _sse_done(), _stream_workflow_progress(), emit()

### Community 634 - "hermes_prompt.py"
Cohesion: 0.19
Nodes (7): build_chatml_system_prompt(), format_chatml_message(), format_tool_call(), format_tool_response(), messages_to_chatml(), model_supports_chatml(), parse_tool_call_from_chatml()

### Community 638 - "Skill: repowise-intelligence"
Cohesion: 0.12
Nodes (15): 1. Graph Intelligence (Dependency Graph), 2. Git Intelligence, 3. Documentation Intelligence, 4. Decision Intelligence, Acceptance Checks, Directory Structure, Example Usage, Implementation Approach (+7 more)

### Community 639 - "ARCHITECTURE.md — Target Architecture"
Cohesion: 0.12
Nodes (15): 1. Target Repository Structure, 2. Dependency Rules, 3. Provider Architecture (Target), 4. Configuration Architecture (Target), 5. Event Bus Architecture (Target), 6. Scheduler Architecture (Target), 7. Dashboard Architecture (Target), 8. Migration Principles (+7 more)

### Community 640 - "Component Map"
Cohesion: 0.12
Nodes (16): Architecture Audit — local-llm-server, Architecture Diagram, Component Map, Layer 10 — WebUI (`webui/`), Layer 11 — Infrastructure, Layer 1 — API Proxy (`proxy.py`, 1719 lines), Layer 3 — Model Router (`router/`), Layer 4 — Agent System (`agent/`) (+8 more)

### Community 641 - "Security Analysis — local-llm-server"
Cohesion: 0.10
Nodes (19): Fable 5 — Read-Only Audit & Skill-Distillation Notes, Finding B — `/api/secrets` router is mounted with no authentication dependency, Part 0 — A caveat on how this task started, Part 1 — The audit, Suggested fixes (not applied here), The chain, What was checked and is sound, 10. Cloudflare Worker Security (+11 more)

### Community 642 - "test_social_login_oauth.py"
Cohesion: 0.24
Nodes (11): _valid_login_state(), _doc(), test_expired_state_rejected(), test_just_within_window_accepted(), test_login_endpoints_do_not_depend_on_session_cookie(), test_missing_state_doc_rejected(), test_naive_created_at_does_not_raise(), test_repo_flow_state_not_usable_for_login() (+3 more)

### Community 643 - "github_source.py"
Cohesion: 0.20
Nodes (8): _decode_readme(), fetch_github_source(), is_github_source(), parse(), _q(), _readme(), _repo_summary(), _strip_readme_noise()

### Community 644 - "Attention Mechanisms Internals"
Cohesion: 0.12
Nodes (15): x(), Attention Complexity, Attention Mechanisms Internals, Causal Masking, Flash Attention, Grouped Query Attention (GQA), Multi-Head Attention (MHA), Multi-Query Attention (MQA) (+7 more)

### Community 645 - "Skill: repowise-intelligence"
Cohesion: 0.12
Nodes (15): 1. Graph Intelligence (Dependency Graph), 2. Git Intelligence, 3. Documentation Intelligence, 4. Decision Intelligence, Acceptance Checks, Directory Structure, Example Usage, Implementation Approach (+7 more)

### Community 646 - "The 10-Step Workflow"
Cohesion: 0.12
Nodes (15): Cross-Tool Compatibility, Quick Reference Card, Skill: session-planning — Mandatory Planning Workflow for All AI Agents, Step 10 — Close Out, Step 1 — Orient (free), Step 2 — Understand the Task, Step 3 — Load Relevant Skills, Step 4 — Research (if novel task) (+7 more)

### Community 647 - "Contributing to local-llm-server"
Cohesion: 0.12
Nodes (16): Architecture, Bug Reports, Changelog, Coding Standards, Commit Message Convention, Contributing to local-llm-server, Development Setup, Feature Requests (+8 more)

### Community 648 - "CompanyGraphStore"
Cohesion: 0.02
Nodes (22): Added, detect_company_id(), detect_repo_id(), DirectChatSession, handle_chat_message_with_context(), Added, buildGraphElements(), BusinessSystem (+14 more)

### Community 649 - "parse_event_stream"
Cohesion: 0.10
Nodes (6): _accumulate_usage(), _assistant_messages(), _message_text(), parse_event_stream(), ParsedRun, TestParseEventStream

### Community 650 - "Agent Runtime Setup"
Cohesion: 0.12
Nodes (14): 1. Register Runtimes, 2. Verify Installation, 3. Access Agents via API, Agent Runtime Setup, Agents not appearing in API responses, Initial Setup, MongoDB Connection, No agents showing after registration (+6 more)

### Community 651 - "Runbook — Apply the Fast Free NVIDIA Brain to Render (TASK 2)"
Cohesion: 0.18
Nodes (10): Option A — Blueprint sync (preferred), Rollback, Runbook — Apply the Fast Free NVIDIA Brain to Render (TASK 2), Security notes, Status quo — what render.yaml already pins on master, TL;DR, V.1 — liveness, V.2 — autonomy readiness (+2 more)

### Community 652 - "WorkflowBuildRequest"
Cohesion: 0.07
Nodes (16): engine(), TestApprovalGateMandatory, do_approve(), _make_engine(), _make_run(), test_crispy_run_history_aggregates_phase_outcomes(), test_crispy_run_history_caps_failure_reasons_at_5(), test_crispy_run_history_counts_run_statuses() (+8 more)

### Community 653 - "model_router.py"
Cohesion: 0.09
Nodes (11): _build_builtin_model_map(), _default_model(), _nvidia_key_present(), best_model_for(), best_vision_model(), has_image_content(), ModelCapability, test_router_default_model_returns_catalog_preset_for_ollama() (+3 more)

### Community 654 - "fabric_cli.py"
Cohesion: 0.29
Nodes (11): cmd_apply(), cmd_list(), cmd_new(), cmd_save(), cmd_show(), cmd_stitch(), _ensure_patterns_dir(), main() (+3 more)

### Community 655 - "TelegramBotManager"
Cohesion: 0.10
Nodes (6): TelegramBotManager, test_telegram_bot_manager_start_accepts_chat_id_fallback(), test_telegram_bot_manager_start_requires_allowed_or_chat_id(), test_telegram_bot_manager_start_requires_token(), test_telegram_bot_manager_status_users_configured_via_chat_id(), test_telegram_bot_manager_status_users_not_configured_without_chat_id()

### Community 656 - "prompt_audit.py"
Cohesion: 0.20
Nodes (10): audit(), _check_file_paths(), _check_model_ids(), _deliberate(), _is_path_not_model(), _load_catalogue_ids(), _load_model_ids(), _looks_like_path() (+2 more)

### Community 658 - "e2e/test_browser.py"
Cohesion: 0.19
Nodes (9): base_url(), do_login(), fail(), ok(), Result, run_tests(), test_all_pages_browser(), test_page() (+1 more)

### Community 660 - "test_dockerfile_ships_root_modules.py"
Cohesion: 0.17
Nodes (7): _dockerfile_text(), _ships_all_root_modules(), test_backend_image_ships_all_root_modules(), test_backend_image_ships_packages_dir(), test_deployed_commit_ignores_blank_values(), test_health_endpoint_commit_is_null_when_host_stamps_nothing(), test_worker_start_command_module_is_shiped()

### Community 662 - "test_migrate_local_brain_env.py"
Cohesion: 0.38
Nodes (12): _make_env(), _run(), test_crlf_preserved_on_untouched_lines(), test_dry_run_does_not_mutate(), test_env_path_missing_file_exits_1(), test_force_rewrites_canonical_already_present(), test_happy_path_migrates_broken_to_canonical(), test_idempotent_re_run_is_noop() (+4 more)

### Community 664 - "TestRoutes"
Cohesion: 0.18
Nodes (4): _install_service(), _seeded_manager(), TestBoardPayload, TestRoutes

### Community 666 - "sys"
Cohesion: 0.01
Nodes (76): _extract_unreleased_body(), _insert(), main(), _read_template(), _load(), main(), _write_summary(), _load() (+68 more)

### Community 667 - "_hash_component"
Cohesion: 0.16
Nodes (3): TestWorkspacePathDerivation, TestWorkspaceHashing, _hash_component()

### Community 669 - "test_ai_insights.py"
Cohesion: 0.18
Nodes (8): EngagementMetrics, test_engagement_dau_counts_unique_users(), test_engagement_dau_zero_when_no_events(), test_engagement_record_appends(), test_engagement_sessions_split_on_gap(), test_engagement_tool_diversity(), test_engagement_wau_window(), test_tool_metrics_token_efficiency()

### Community 670 - "CostLine"
Cohesion: 0.18
Nodes (11): CostLine, FinancialAgent, test_agent_explain_returns_human_readable(), test_agent_holds_strategic_low_roi_lines(), test_agent_investigates_uppercase_cogs_categories(), test_agent_recommends_cut_on_low_runway(), test_agent_recommends_investigate_low_margin(), test_agent_recommends_scale_for_high_roi_sales() (+3 more)

### Community 671 - "Skill: Agentic Portfolio Management"
Cohesion: 0.13
Nodes (9): InitiativeProgress, Key Classes, Purpose, Related, Skill actions (via SkillBindings), Skill: Agentic Portfolio Management, Testing, Usage (+1 more)

### Community 672 - "Skill: agent-harness"
Cohesion: 0.13
Nodes (14): Architecture, Combining with Other Skills, Key Concepts, Output Format, Purpose, Safety Rules, Skill: agent-harness, Step 1 — Define the task clearly (+6 more)

### Community 673 - "Skill: checkpoint-strategy"
Cohesion: 0.13
Nodes (14): After a Loss Spike, Aggressive (Long Runs with Stable Training), Background, Checkpoint Policy Templates, Conservative (Recommended for First Runs), Integration Points, Output Format, Purpose (+6 more)

### Community 674 - "Process"
Cohesion: 0.13
Nodes (14): Anti-Patterns, Process, Purpose, Rules, Skill: debug-tracer, Step 1: Reproduce First, Step 2: Gather Evidence, Step 3: Form Hypotheses (+6 more)

### Community 675 - "Skill: local-ai-query"
Cohesion: 0.13
Nodes (14): 1. Verify Ollama is available, 2. Choose appropriate model, 3. Send query to local model, 4. Generate embeddings (for RAG), 5. List running models, Integration with ChromaDB (RAG), Limitations, Prerequisites (+6 more)

### Community 676 - "Skill: parallel-agents"
Cohesion: 0.13
Nodes (14): Combining with Other Skills, Core Concepts (from the Modal/OpenAI Agents SDK pattern), Example — parallel approach exploration, Example — parallel research, Output Format, Phase 1 — Decompose, Phase 2 — Dispatch (simulate parallelism), Phase 3 — Aggregate (+6 more)

### Community 677 - "Skill: parallel-worktrees"
Cohesion: 0.13
Nodes (14): Acceptance Checks, Common Patterns, Concept, Constraints, Instructions, Pattern A — Test main while you implement, Pattern B — Review reference during refactor, Pattern C — Hotfix without disturbing feature work (+6 more)

### Community 678 - "Design System: Taste Standard"
Cohesion: 0.13
Nodes (14): 1. Visual Theme & Atmosphere, 2. Color Palette & Roles, 3. Typography Rules, 4. Component Stylings, 5. Hero Section, 6. Layout Principles, 7. Responsive Rules, 8. Motion & Interaction (Code-Phase Intent) (+6 more)

### Community 679 - "Process"
Cohesion: 0.13
Nodes (14): Integration with Other Skills, Process, Purpose, Rules, Skill: ticket-to-pr, Step 1: Parse the Issue, Step 2: Context Prime, Step 3: Plan the Implementation (+6 more)

### Community 680 - "test_new_features_e2e.py"
Cohesion: 0.26
Nodes (9): base_url(), do_login(), fail(), ok(), Result, run_tests(), test_api_endpoints(), test_new_features_browser() (+1 more)

### Community 683 - "OpenClaw — iOS Control of the Agency (Single-Service Free-Tier Deploy)"
Cohesion: 0.13
Nodes (12): 1. Set env vars on the existing `local-llm-server` service, 2. Deploy, 3. Check the status, 4. Get the pairing QR, 5. Pair and verify, Alternative: Telegram bot, Architecture (single-service), Free-tier caveats (+4 more)

### Community 684 - "trend_analysis.py"
Cohesion: 0.18
Nodes (7): TestRunTrendAnalysis, TestWindow, run_trend_analysis(), TrendItem, TrendReport, _within_window(), _write_summary()

### Community 686 - "record_event"
Cohesion: 0.07
Nodes (17): P1 — Close the remaining product gaps, Task 6 — Deeper website/repo scanning (more than "2 systems"), Task 7 — Knowledge base auto-reflect (ECC / Obsidian / graphify-style), Task 8 — Vector retrieval for the knowledge base (self-learn), guard(), identity_from_headers(), _load(), record() (+9 more)

### Community 687 - "check_model_catalog_consistency.py"
Cohesion: 0.22
Nodes (6): _check_cross_catalogue(), _check_prefer_models(), _check_presets(), _llm_declared(), _load(), main()

### Community 688 - "OperationalIncidentTracker"
Cohesion: 0.11
Nodes (4): _iso_from_monotonic(), OperationalIncidentTracker, _utcnow_iso(), tracker()

### Community 692 - "build_tool_prompt"
Cohesion: 0.10
Nodes (20): build_compaction_prompt(), build_execution_prompt(), build_planning_prompt(), build_tool_prompt(), build_verification_prompt(), Context Plan — Issue #1427: quick-note:https://github.com/bingreeky/JIT, Decision, How its four axes map onto what this repo already has (+12 more)

### Community 694 - "v3_auth.py"
Cohesion: 0.16
Nodes (9): _get_admin_email(), _get_admin_name(), _get_admin_secret(), login(), LoginRequest, LoginResponse, refresh(), RefreshRequest (+1 more)

### Community 695 - "resolve_provider_for"
Cohesion: 0.07
Nodes (16): _get_provider_policy(), _prio(), resolve_provider_for(), test_ci_provider_policy_failsafe(), test_get_provider_policy_returns_default_without_db(), test_provider_policy_update_defaults_to_block_paid(), test_provider_policy_update_explicit_allow(), test_resolve_provider_for_blocks_paid_when_kill_switch_off() (+8 more)

### Community 696 - "test_dockerfile_ships_config_dir.py"
Cohesion: 0.14
Nodes (7): _dockerfile_text(), test_backend_image_ships_the_config_dir(), test_config_is_not_excluded_from_the_build_context(), test_every_local_provider_is_opt_in(), test_groq_declares_its_per_minute_budget(), test_ollama_is_off_and_bounded_by_default(), test_the_config_files_the_router_reads_exist_in_the_repo()

### Community 697 - "TestDiscovery"
Cohesion: 0.13
Nodes (3): TestDiscovery, _raise(), TestFailureIsAudible

### Community 698 - "QuickNoteQueue"
Cohesion: 0.27
Nodes (12): QuickNoteQueue, test_add_creates_pending_note(), test_add_persists_to_file(), test_list_all_returns_all(), test_mark_done(), test_mark_failed(), test_next_pending_claims_note(), test_next_pending_returns_none_when_empty() (+4 more)

### Community 699 - "_process_task_callback"
Cohesion: 0.10
Nodes (20): _process_task_callback(), _make_fake_task(), _patch_workflow(), test_approve_success_clears_spinner_and_edits_message(), _approve(), test_reject_success_clears_spinner_and_edits_message(), test_storage_init_failure_clears_spinner(), test_store_get_timeout_clears_spinner() (+12 more)

### Community 700 - "compilerOptions"
Cohesion: 0.13
Nodes (14): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noEmit, resolveJsonModule (+6 more)

### Community 701 - "test_executive_advisory.py"
Cohesion: 0.12
Nodes (13): AdvisoryMemory, _compose_context(), _format_company_context(), get_executive_advisory(), _keywords(), _mem_key(), reset_executive_advisory(), test_advisory_memory_is_fail_soft_on_broken_store() (+5 more)

### Community 702 - "Trajectory"
Cohesion: 0.06
Nodes (9): EvalHarness, _bounded(), EvalResult, SuccessCriterion, SuccessCriterionType, Task, TaskDifficulty, Trajectory (+1 more)

### Community 703 - "classify_direct_chat_intent"
Cohesion: 0.23
Nodes (8): classify_direct_chat_intent(), _contains_keyword(), detect_intent(), test_classify_answer_only(), test_classify_clarify_needed(), test_classify_execute_after_approval(), test_classify_execute_now(), test_classify_plan_only()

### Community 705 - "BudgetOptimizer"
Cohesion: 0.15
Nodes (6): BudgetOptimizer, test_optimizer_lowest_roi_lines(), test_optimizer_reallocate_favors_high_roi(), test_optimizer_reallocate_respects_total_budget(), test_optimizer_reallocate_zero_budget_zeros_all(), test_optimizer_total_budget_sums_lines()

### Community 706 - "Project Manager Agent Personality"
Cohesion: 0.14
Nodes (13): 1. Specification Analysis, 2. Task List Creation, 3. Technical Stack Requirements, 🚨 Critical Rules You Must Follow, Learning from Experience, 🔄 Learning & Improvement, Project Manager Agent Personality, Realistic Scope Setting (+5 more)

### Community 708 - "rag_context.py"
Cohesion: 0.09
Nodes (17): _prefer_relevant(), ContextResult, Document, hybrid_rank(), _keyword_search(), MemoryTurn, RetrievedDoc, _token_count() (+9 more)

### Community 710 - "Process"
Cohesion: 0.14
Nodes (13): 1. Read and Understand the Issue, 2. Explore the Codebase, 3. Plan the Solution, 4. Implement, 5. Test, 6. Document, 7. Commit and Push, Notes (+5 more)

### Community 711 - "Skill: lr-schedule-advisor"
Cohesion: 0.14
Nodes (13): Background (Why This Matters), Common Mistakes, Cosine with Warmup (Recommended for Pretraining), Fine-tuning vs Pretraining, Integration Points, Output Format, Peak LR Heuristics by Model Size, Purpose (+5 more)

### Community 712 - "Instructions"
Cohesion: 0.14
Nodes (13): 1 — Tests green, 2 — Changelog updated, 3 — Determine the version bump, 4 — Update changelog, 5 — Commit the changelog update, 6 — Tag the release, 7 — Verify CI on the tag, 8 — Post-release (+5 more)

### Community 713 - "Process"
Cohesion: 0.14
Nodes (13): 1. Decompose the Task, 2. Sequence the Skills, 3. Execute in Order, 4. Handle Failures, 5. Synthesize Output, 6. Document the Composition, Example Compositions, Notes (+5 more)

### Community 714 - "Checks Performed"
Cohesion: 0.14
Nodes (13): 1. Round-trip Consistency, 2. Numeric Tokenization, 3. Whitespace Handling, 4. Special Character Coverage, 5. Fertility by Domain, 6. Vocabulary Overlap Check (for model updates), Background, Checks Performed (+5 more)

### Community 715 - "Skill: training-stability-monitor"
Cohesion: 0.14
Nodes (13): Example Checks Performed, Gradient Norm Check, Integration Points, Key Lessons (from LLM-from-scratch practitioners), Loss Spike Detection, LR Warmup Validation, Notes, Output Format (+5 more)

### Community 716 - "Skill: branch-cleanup"
Cohesion: 0.14
Nodes (13): Acceptance Checks, Automation — post-merge hook (optional), Option A — git push (standard), Option B — GitHub API (use when `git push --delete` returns 403), Option C — Delete local tracking refs after remote deletion, Skill: branch-cleanup, Step 1 — Confirm master is up to date, Step 2 — List all remote branches (+5 more)

### Community 717 - "Skill: perplexity — Web Research via Perplexity API"
Cohesion: 0.14
Nodes (13): Applying to this Repo, How to Query, No API Key? Use WebSearch, Prerequisites, Quick query (one-shot Python call), Run inline, Skill: perplexity — Web Research via Perplexity API, Skill Steps (+5 more)

### Community 718 - "Instructions"
Cohesion: 0.14
Nodes (13): 1 — Tests green, 2 — Changelog updated, 3 — Determine the version bump, 4 — Update changelog, 5 — Commit the changelog update, 6 — Tag the release, 7 — Verify CI on the tag, 8 — Post-release (+5 more)

### Community 719 - "Instructions"
Cohesion: 0.14
Nodes (13): Acceptance Checks, `admin_auth.py` checklist, `agent/tools.py` checklist, Escalation, Instructions, `key_store.py` checklist, `proxy.py` auth middleware checklist, Risky Modules in This Repo (+5 more)

### Community 720 - "Quick-Note Issues Processing Summary"
Cohesion: 0.14
Nodes (13): 🔗 Branch References, ✅ Completed, Future Session, Immediate (Session-Aware), Issue #229 — Stop-Slop AI Quality Checker, Issue #263 — Graphiti Temporal Context, Issue #266 — ECC Multi-Harness Adapter, 💡 Key Learnings (+5 more)

### Community 722 - ".content"
Cohesion: 0.12
Nodes (15): API, Architecture, Delegation plan → agent tasks, Demo from the UI, Exports — the full heavy report, Fetching bot-protected sites (`fetch_mode`), Provenance, Repo-aware auto-fixing (+7 more)

### Community 723 - "AgentsScreen.jsx"
Cohesion: 0.23
Nodes (13): createAgent(), AgentCard(), AgentsScreen(), BUILTIN_AGENT_DEFS, mapBackendAgent(), NewAgentForm(), PIPELINE_MODES, PipelinePanel() (+5 more)

### Community 724 - "handle_anthropic_messages"
Cohesion: 0.10
Nodes (11): _build_anthropic_response(), _emit_safely(), _finish_reason_to_stop_reason(), handle_anthropic_messages(), _openai_choice_to_anthropic_content(), _sse_event(), _stream_anthropic_sse(), _system_field_to_string() (+3 more)

### Community 726 - "DeterministicEngine"
Cohesion: 0.20
Nodes (3): DeterministicEngine, _make_rule(), TestDeterministicEngine

### Community 727 - "test_langfuse_agency_wide.py"
Cohesion: 0.10
Nodes (9): test_agency_py_traces_ceo_directives(), test_emit_agency_observation_accepts_all_params(), test_emit_agency_observation_exists(), test_emit_agency_observation_returns_none_when_disabled(), test_sam_py_traces_voice_commands(), test_scheduler_tick_traces(), test_self_heal_traces(), test_task_service_traces_execution() (+1 more)

### Community 728 - "Context: Agentic Agile + Portfolio Management"
Cohesion: 0.11
Nodes (9): Agile improvements shipped alongside, Capacity & roadmap, Context: Agentic Agile + Portfolio Management, Extension ideas (not yet built), Prioritisation model — WSJF (SAFe), Problem, The two layers, v5 UI surface (+1 more)

### Community 730 - "chat_completions"
Cohesion: 0.20
Nodes (8): chat_completions(), ChatCompletionRequest, _content_to_str(), _ContentPart, health(), list_models(), _Message, _verify_token()

### Community 731 - "NVIDIA NIM — Free Tier Setup"
Cohesion: 0.18
Nodes (10): 1. Get your free API key, 2. Set the environment variable, 3. Restart the server, 4. Verify, How the kill switch protects you, NVIDIA NIM — Free Tier Setup, Related, Setup (5 minutes) (+2 more)

### Community 732 - "test_setup_api.py"
Cohesion: 0.19
Nodes (6): clear_wizard_state_cache(), set_wizard_state_collection(), _FakeWizardCollection, _setup_client(), test_reset_wizard_removes_persisted_collection_state(), test_setup_state_persists_in_collection_across_cache_resets()

### Community 733 - "HarnessRegistry"
Cohesion: 0.17
Nodes (4): HarnessMetrics, HarnessRegistry, HarnessSessionRecord, _NoopDB

### Community 734 - "test_agency_workflows_carry_the_failover_chain.py"
Cohesion: 0.18
Nodes (5): _agency_workflows(), test_agency_workflow_passes_the_whole_free_chain(), test_keys_are_read_from_secrets_not_inlined(), test_the_scan_finds_agency_workflows(), TestRenderDeclaresTheChain

### Community 735 - "parametrize"
Cohesion: 0.22
Nodes (4): _assigned_names(), _source(), TestOneListToFix, TestTheNamesActuallyResolve

### Community 739 - "_Response"
Cohesion: 0.20
Nodes (5): _Response, TestCallBrainWithFailover, fake_post(), fake_post(), fake_post()

### Community 740 - "Retrospective"
Cohesion: 0.12
Nodes (5): _bullets(), retrospective_to_markdown(), StandupReport, Retrospective, TestRetrospectiveToMarkdown

### Community 741 - "yaml"
Cohesion: 0.02
Nodes (23): _env_float(), merge_step(), test_dependabot_prs_are_left_to_their_own_workflow(), _agency_catalogue(), _cerebras_block(), TestOnlyWhatTheAccountServesIsConfigured, TestTheTwoCopiesAgree, _policy_skip() (+15 more)

### Community 743 - "_start_ceo_agency"
Cohesion: 0.27
Nodes (5): _start_ceo_agency(), _reset_agency_singleton(), test_ceo_agency_can_be_disabled(), test_ceo_agency_starts_by_default(), test_ceo_agency_startup_never_raises()

### Community 745 - "InferenceCache"
Cohesion: 0.08
Nodes (3): CachedLLMClient, CacheEntry, InferenceCache

### Community 746 - "AgentJobSnapshot"
Cohesion: 0.22
Nodes (6): AgentJobSnapshot, cancel_chat_agent_job(), get_chat_agent_job(), resume_agent_chat_job(), _ResumeRequest, TestAgentJobSnapshot

### Community 747 - "AIToolMetrics"
Cohesion: 0.15
Nodes (6): AIToolMetrics, test_tool_metrics_acceptance_rate(), test_tool_metrics_acceptance_rate_unknown_tool(), test_tool_metrics_average_latency(), test_tool_metrics_kind_breakdown(), test_tool_metrics_ranking_sorted_descending()

### Community 749 - "CEODispatcher"
Cohesion: 0.05
Nodes (21): CEODispatcher, _complexity_rank(), _decompose_into_subtasks(), _offload(), _runtime_id_for_role(), _should_fan_out(), _single_specialist_task(), _spec_to_task_spec() (+13 more)

### Community 750 - "TestPromptIdForwarding"
Cohesion: 0.15
Nodes (3): TestPromptIdForwarding, fake_env_val(), fake_http()

### Community 751 - "Software Architect Agent"
Cohesion: 0.15
Nodes (12): 1. Domain Discovery, 2. Domain Modeling Guidance, 3. Architecture Selection, 4. Dependency & Boundary Rules, 5. Quality Attribute Analysis, 📋 Architecture Decision Record Template, 💬 Communication Style, 🔧 Critical Rules (+4 more)

### Community 752 - "Process"
Cohesion: 0.15
Nodes (12): Output Format, Process, Purpose, Rules, Skill: auto-fix, Step 1: Discover Fix Commands, Step 2: Run Fixers (Auto-fixable), Step 3: Run Checkers (Non-auto-fixable) (+4 more)

### Community 753 - "Skill: Brain Dump"
Cohesion: 0.15
Nodes (12): Example Prompt to Trigger, Instructions, Notes, Output Format, Purpose, Skill: Brain Dump, Step 1: Capture Everything, Step 2: Categorize (+4 more)

### Community 754 - "Process"
Cohesion: 0.15
Nodes (12): Process, Purpose, Rules, Skill: context-prime, Step 1: Read Core Docs, Step 2: Map the Architecture, Step 3: Find Conventions, Step 4: Understand Data Flow (+4 more)

### Community 755 - "Instructions"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Instructions, Role 1: Security Reviewer, Role 2: Correctness Reviewer, Role 3: Performance Reviewer, Role 4: Maintainability Reviewer, Skill: council-review, Step 1 — Gather the diff (+4 more)

### Community 756 - "Skill: duplicate-thread"
Cohesion: 0.15
Nodes (12): Files, How It Works, In a Claude prompt, Integration, Manual duplication, Merging Back, meta.json Schema, Purpose (+4 more)

### Community 757 - "Skill: Email Triage"
Cohesion: 0.15
Nodes (12): Example Prompt to Trigger, Instructions, Notes, Output Format, Purpose, Skill: Email Triage, Step 1: Intake, Step 2: Triage Categories (+4 more)

### Community 758 - "Process"
Cohesion: 0.15
Nodes (12): Anti-Patterns, Process, Purpose, Rules, Skill: feature-flag, Step 1: Assess Flag Need, Step 2: Define the Flag, Step 3: Implement the Guard (+4 more)

### Community 759 - "Process"
Cohesion: 0.15
Nodes (12): 1. Review Staged and Unstaged Changes, 2. Review Commit History, 3. Validate Commit Messages, 4. Clean Up if Needed, 5. Confirm Branch State, 6. Push, Notes, Output (+4 more)

### Community 760 - "Skill: graphify — Knowledge Graph Token Optimization"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Claude's query protocol (use this instead of Read tool for exploration):, Graph Artifacts — What to Commit, How to Use the Graph (Token Savings Protocol), Installation (one-time per machine), Instead of reading raw files:, Key commands:, Relationship to repowise-intelligence Skill (+4 more)

### Community 761 - "Skill: prompt-library"
Cohesion: 0.15
Nodes (12): 1. Sync Snapshots, 2. Generate Library Index, 3. Generate TRANSPARENCY.md, 4. Update CHANGELOG.md in prompts/, 5. Commit, Directory Structure Created, Output, Purpose (+4 more)

### Community 762 - "Skill: prompt-transparency"
Cohesion: 0.15
Nodes (12): 1. Collect All Agent & Skill Definitions, 2. Extract Key Behavioral Dimensions, 3. Generate Transparency Report, 4. Flag Risks, 5. Commit the Report, Example Usage, Inspiration, Output Format (+4 more)

### Community 763 - "Skill: Research"
Cohesion: 0.15
Nodes (12): Example Prompt to Trigger, Instructions, Notes, Output Format, Purpose, Skill: Research, Step 1: Define the Research Question, Step 2: Identify Source Categories (+4 more)

### Community 764 - "Skill: scope-guard"
Cohesion: 0.15
Nodes (12): Anti-Patterns to Avoid, Output Format, Process, Purpose, Rules, Skill: scope-guard, Step 1: Define the Scope Contract, Step 2: Pre-Implementation Check (+4 more)

### Community 765 - "local_brain_router.py"
Cohesion: 0.19
Nodes (7): get_local_brain_state(), HeartbeatBody, post_local_brain_heartbeat(), post_local_brain_toggle(), _store(), ToggleBody, _validate_state()

### Community 766 - "Instructions"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Instructions, Role 1: Security Reviewer, Role 2: Correctness Reviewer, Role 3: Performance Reviewer, Role 4: Maintainability Reviewer, Skill: council-review, Step 1 — Gather the diff (+4 more)

### Community 767 - "Skill: graphify — Knowledge Graph Token Optimization"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Claude's query protocol (use this instead of Read tool for exploration):, Graph Artifacts — What to Commit, How to Use the Graph (Token Savings Protocol), Installation (one-time per machine), Instead of reading raw files:, Key commands:, Relationship to repowise-intelligence Skill (+4 more)

### Community 768 - "Skill: platform-setup — Autonomous Agency Bootstrap"
Cohesion: 0.15
Nodes (12): Ongoing autonomous operation, Phase 1 — Verify deployment health (no auth needed), Phase 2 — Login as admin, Phase 3 — Onboard the platform itself as a company, Phase 4 — Verify specialists were provisioned, Phase 5 — Configure GitHub integration, Phase 6 — Trigger first agency cycle manually, Phase 7 — Verify autonomous schedule is active (+4 more)

### Community 769 - "Agency Core — Progress & Resume Log"
Cohesion: 0.13
Nodes (14): Agency Core — Progress & Resume Log, Audit (committed), Environment constraints discovered this session, How to resume (read before doing anything), Key findings (so we don't re-investigate), Open risks / must-know before merging, Phase 0 — Stabilize & quarantine (commit `713184a`, pushed), Planned CI-parity hardening (the immediate next commit) (+6 more)

### Community 770 - "Device compatibility and model picks"
Cohesion: 0.15
Nodes (12): Acceleration at a glance, Apple Silicon: chip tier vs bandwidth (qualitative), Desktops and workstations, Device compatibility and model picks, Edge cases, How to read memory on different platforms, Laptops and all-in-ones, NVIDIA examples by VRAM (CUDA) (+4 more)

### Community 771 - "V5App.jsx"
Cohesion: 0.06
Nodes (61): samAvatarConfig(), samChat(), NAV_ITEMS, ADMIN_CHIPS, SamAvatar(), SamPanel(), speak(), useEyeTracking() (+53 more)

### Community 772 - "rules"
Cohesion: 0.15
Nodes (12): rules, import/no-anonymous-default-export, jsx-a11y/anchor-is-valid, jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/no-static-element-interactions, no-console, no-template-curly-in-string (+4 more)

### Community 776 - "KnowledgeScreen.jsx"
Cohesion: 0.20
Nodes (16): createWikiPage(), deleteSource(), ingestSource(), ActivityRow(), actorColors, AddSourceForm(), DocCard(), GRAPH_CATEGORY_ORDER (+8 more)

### Community 777 - "_get_provider_policy"
Cohesion: 0.19
Nodes (4): _get_provider_policy(), ProviderPolicyUpdate, _set_provider_policy(), update_provider_policy()

### Community 779 - "load_tasks"
Cohesion: 0.13
Nodes (10): Caveats, CLI, Cost-aware routing evaluation, How the metric resists gaming, Method, What's here, EvalTask, load_tasks() (+2 more)

### Community 780 - "_self_heal_ready"
Cohesion: 0.13
Nodes (3): _latest_metric_value(), _self_heal_ready(), _split_memory()

### Community 781 - "fetch_url.py"
Cohesion: 0.19
Nodes (8): extract_real_url(), fetch(), _github_fetch_text(), main(), meaningful(), strip_boilerplate(), strip_html(), __init__()

### Community 783 - "TestDisabledProvidersAreNotFalselyReportedUnreachable"
Cohesion: 0.17
Nodes (3): TestDisabledProvidersAreNotFalselyReportedUnreachable, TestNoKeyEverReachesTheLog, _boom()

### Community 785 - "test_compose_and_coordinate_api.py"
Cohesion: 0.19
Nodes (6): _auth_override(), test_coordinate_dependency_aware_tasks_block_missing_dependencies(), test_coordinate_dependency_aware_tasks_succeed_with_dependencies(), test_coordinate_legacy_workers_flow_remains_backward_compatible(), test_docker_compose_has_no_circular_depends_on(), _visit()

### Community 787 - "test_deploy_trigger_covers_image.py"
Cohesion: 0.21
Nodes (6): _image_copy_sources(), test_deploy_verification_cannot_pass_silently_on_failure(), test_every_directory_in_the_image_can_trigger_a_deploy(), test_packages_dir_specifically_triggers_a_deploy(), test_root_modules_trigger_a_deploy_wholesale(), _workflow_trigger_paths()

### Community 788 - "_TFIDFIndex"
Cohesion: 0.16
Nodes (8): _TFIDFIndex, _tokenize(), test_tfidf_empty_corpus(), test_tfidf_empty_query(), test_tfidf_finds_relevant(), test_tfidf_scores_between_0_and_1(), test_tfidf_scores_ordered_descending(), test_tfidf_unknown_term_only()

### Community 790 - "pytest"
Cohesion: 0.01
Nodes (43): reset_watchdog(), _declared_packages(), test_backend_requirements_declares_runtime_package(), test_dockerfile_still_installs_backend_requirements_only(), _StubRuntimeManager, _StubRuntimeRegistry, _StubTask, _StubTaskDispatcher (+35 more)

### Community 791 - "test_quick_note_engine.py"
Cohesion: 0.17
Nodes (6): _before(), test_baseline_pytest_timeout_is_generous_and_failure_is_caught(), test_implement_agent_never_escalates_to_paid(), test_implement_agent_routes_through_the_shared_router(), test_nemotron_is_preferred_when_choosing_a_model(), test_review_agent_nvidia_primary()

### Community 792 - "validate_job_id"
Cohesion: 0.19
Nodes (3): TestJobIdValidation, TestPathTraversalPrevention, validate_job_id()

### Community 793 - "test_critical_flows.py"
Cohesion: 0.26
Nodes (10): _do_login(), _http_ok(), _playwright(), _require_backend(), _require_proxy(), test_admin_dashboard_loads(), test_chat_direct_mode_via_proxy(), test_company_onboarding_scan_flow() (+2 more)

### Community 794 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Idempotency Rules, Instructions, Skill: cooldown-resume, Step 1 — Read the checkpoint files, Step 2 — Assess the state, Step 3 — Verify changed files are correct, Step 4 — Run tests to confirm baseline (+3 more)

### Community 795 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Current Dependencies (quick reference), Instructions, Skill: dependency-audit, Step 1 — Evaluate the new dependency, Step 2 — Pin appropriately, Step 3 — Install and verify, Step 4 — Check for conflicts (+3 more)

### Community 796 - "Process"
Cohesion: 0.17
Nodes (11): 1. Audit Existing Skills, 2. Identify Gaps, 3. Propose Improvements, 4. Implement, 5. Validate, Notes, Output, Process (+3 more)

### Community 797 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Instructions, Skill: smart-commit, Step 1 — Confirm changelog is updated, Step 2 — Run tests, Step 3 — Check for obvious issues, Step 4 — Stage your changes, Step 5 — Write a conventional commit message (+3 more)

### Community 798 - "Skill: system-prompt-audit"
Cohesion: 0.17
Nodes (11): 1. Inventory Collection, 2. Consistency Check, 3. Safety Check, 4. Generate Audit Report, 5. Exit Codes, Integration, Purpose, Related Skills (+3 more)

### Community 799 - "Skill: task-alive-updates"
Cohesion: 0.17
Nodes (11): Example Output, Files, How It Works, Implementation Rules, In a shell script / agent harness, In Claude task descriptions, Integration with parallel-agents, Purpose (+3 more)

### Community 800 - "Process"
Cohesion: 0.17
Nodes (11): 1. Read the Task Carefully, 2. Define the Boundary, 3. Identify Temptations, 4. Lock the Scope, 5. Out-of-Scope Findings, Notes, Output, Process (+3 more)

### Community 801 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Instructions, Skill: test-first-executor, Step 1 — Identify what needs testing, Step 2 — Write the test first, Step 3 — Confirm the test FAILS before implementation, Step 4 — Implement until the test passes, Step 5 — Run the full suite (+3 more)

### Community 803 - "Skill: agent-browser — Real Chrome Browser Automation"
Cohesion: 0.17
Nodes (11): Applying to the local-llm-server Platform, Core Commands, How to Use This Skill, Installation (one-time), Skill: agent-browser — Real Chrome Browser Automation, Step 1 — Check Chrome is running with debugging, Step 2 — Navigate and snapshot, Step 3 — Interact using element refs (+3 more)

### Community 804 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Idempotency Rules, Instructions, Skill: cooldown-resume, Step 1 — Read the checkpoint files, Step 2 — Assess the state, Step 3 — Verify changed files are correct, Step 4 — Run tests to confirm baseline (+3 more)

### Community 805 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Current Dependencies (quick reference), Instructions, Skill: dependency-audit, Step 1 — Evaluate the new dependency, Step 2 — Pin appropriately, Step 3 — Install and verify, Step 4 — Check for conflicts (+3 more)

### Community 806 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Instructions, Skill: test-first-executor, Step 1 — Identify what needs testing, Step 2 — Write the test first, Step 3 — Confirm the test FAILS before implementation, Step 4 — Implement until the test passes, Step 5 — Run the full suite (+3 more)

### Community 807 - "Implementation Prompt: Rich TaskBoard + Agile Sprint Integration"
Cohesion: 0.08
Nodes (23): 1. Task model extensions (`tasks/models.py`), 2. New task endpoint (`tasks/api.py`), 3. Agile REST endpoints (`backend/server.py`), 4. TaskBoardScreen upgrade (`frontend/src/v5/screens/TaskBoardScreen.jsx`), 4a. "Needs Clarification" 7th column, 4b. Right-side detail panel, 4c. Sprint view mode toggle, 4d. Create-task modal enhancements (+15 more)

### Community 808 - "Quantization Internals"
Cohesion: 0.17
Nodes (12): Absmax Quantization (Symmetric), Activation Quantization, AWQ (Activation-Aware Weight Quantization), Bits and Bytes (bitsandbytes), Data Types, GGUF / llama.cpp Quantization, GPTQ (Post-Training Quantization for GPT), Post-Training Quantization (PTQ) (+4 more)

### Community 809 - "Autonomy Uplift — Living Roadmap & Detailed Implementation Specs"
Cohesion: 0.17
Nodes (11): 0. The goal (operator's words), 1. Shipped ✅, 2. In flight 🟡, 3. Pending ⬜ — detailed implementation specs, 3a. Apply the slop-gate to the sibling auto-PR scripts ✅  (size: S), 3c. CRISPY — harden, then re-enable ✅  (size: L, risky-module-review), 3d. Phase 3 — auto-PR *quality* beyond the slop-gate ✅  (size: M), 3e. Phase 4 — reliability spine ✅  (size: M) (+3 more)

### Community 810 - "process_note"
Cohesion: 0.18
Nodes (6): _fetch_text(), __init__(), process_note(), _run(), start_processor(), _loop()

### Community 811 - "harness_spec.py"
Cohesion: 0.20
Nodes (7): _flag(), _int_env(), _known_entry_texts(), _one_line(), _refine_locked(), _get_store(), _open_mongo_store()

### Community 812 - "install-agents.sh"
Cohesion: 0.39
Nodes (11): classify_current_or_legacy(), fail(), install_missing(), path_exists(), replace_legacy_role(), report_preflight_error(), role_selected(), same_state() (+3 more)

### Community 813 - "Instructions"
Cohesion: 0.14
Nodes (13): Acceptance Checks, `admin_auth.py` checklist, `agent/tools.py` checklist, Escalation, Instructions, `key_store.py` checklist, `proxy.py` auth middleware checklist, Risky Modules in This Repo (+5 more)

### Community 814 - "LLM Router — configuration guide"
Cohesion: 0.14
Nodes (14): Budgets, Bulkhead sizing, cache.yaml, Environment variables, health.yaml, keys.yaml, LLM Router — configuration guide, models.yaml (+6 more)

### Community 815 - "Kimi Web-Bridge Service"
Cohesion: 0.17
Nodes (11): API, Connecting to the Main Backend, Docker, Environment Variables, `GET /health`, `GET /v1/models`, How It Works, Kimi Web-Bridge Service (+3 more)

### Community 816 - "BrainCard.jsx"
Cohesion: 0.22
Nodes (13): Modified files, getBrainConfig(), patchBrainConfig(), testBrainModel(), BrainCard(), errText(), PROVIDER_LABEL_FALLBACK, providerLabel() (+5 more)

### Community 817 - "SchedulesScreen.jsx"
Cohesion: 0.22
Nodes (13): createSchedule(), pauseSchedule(), resumeSchedule(), triggerSchedule(), CAT_CONFIG, errText(), NewJobForm(), normalizeJob() (+5 more)

### Community 819 - "test_app_settings.py"
Cohesion: 0.21
Nodes (6): sqlite_store(), test_defaults_when_unset(), test_gate_default_controls_unlisted_user(), test_refresh_cache_warms_sync_readers(), test_set_and_get_persists(), test_ttl_roundtrip()

### Community 820 - "test_brain_default_consistency.py"
Cohesion: 0.24
Nodes (6): _catalogue_default(), test_brain_default_matches_the_catalogue(), test_every_nvidia_role_preset_matches_the_catalogue(), test_render_yaml_ships_the_same_default(), test_the_catalogue_names_a_default_at_all(), test_the_default_leads_the_rotation()

### Community 821 - "Runbook: Auto-Resume After Cooldown / Interruption"
Cohesion: 0.14
Nodes (13): Commands, Cooldown Detection, Cooldown Detection Logic, Force-Resume After Stale Lock, Forcing an Abort, How It Works, Inspecting a Stuck Run, Overview (+5 more)

### Community 823 - "LLM Router — provider guide"
Cohesion: 0.22
Nodes (8): Adding any OpenAI-compatible provider, Auth styles, Cheap tiers, Cloud providers, Free tiers, LLM Router — provider guide, Multiple keys, Premium

### Community 824 - "is_anthropic_base_url"
Cohesion: 0.18
Nodes (3): is_anthropic_base_url(), TestFailoverRegistryBaseUrls, TestIsAnthropicBaseUrl

### Community 825 - "prompt_policy.py"
Cohesion: 0.13
Nodes (13): iter_texts(), _map_content(), map_texts(), apply_prompt_policy(), _Cache, _compile(), _current_policy(), evaluate() (+5 more)

### Community 826 - "_encrypt"
Cohesion: 0.18
Nodes (4): _decrypt(), _encrypt(), _get_master_key(), TestEncryption

### Community 829 - "probe_model_liveness"
Cohesion: 0.05
Nodes (26): _describe_http_status(), probe_model_liveness(), _probe_ollama(), _probe_openai_compat(), ProbeResult, _catalogue_candidates(), _catalogue_role_preset(), _catalogue_safe_default() (+18 more)

### Community 830 - "_is_ephemeral_user"
Cohesion: 0.27
Nodes (8): _is_ephemeral_user(), _resolve_provider(), test_admin_local_is_persistent(), test_github_non_admin_is_ephemeral(), test_google_non_admin_is_ephemeral(), test_non_social_non_admin_is_persistent(), test_provider_inferred_from_user_id_prefix(), test_social_admin_is_persistent()

### Community 831 - "_first_paragraph"
Cohesion: 0.15
Nodes (3): _extract_tags(), _first_paragraph(), TestHelpers

### Community 832 - "AI Engineering Insights Skill"
Cohesion: 0.18
Nodes (6): AI Engineering Insights Skill, Integration Points, Key Design Choices, Module: `agents/ai_insights.py`, References, What's Unique About the DX Report

### Community 834 - "SRE (Site Reliability Engineer) Agent"
Cohesion: 0.18
Nodes (10): 💬 Communication Style, 🔧 Critical Rules, Golden Signals, 🔥 Incident Response Integration, 🔭 Observability Stack, 📋 SLO Framework, SRE (Site Reliability Engineer) Agent, The Three Pillars (+2 more)

### Community 835 - "ResearchAgent"
Cohesion: 0.23
Nodes (8): ResearchAgent, _echo_handler(), test_agent_can_handle_matching_role(), test_agent_cannot_handle_other_roles(), test_agent_execute_success_increments_counter(), test_agent_execute_wrong_role_marks_failed(), test_orchestrator_pick_agent_load_balances(), test_orchestrator_run_marks_blocked_when_no_agent_for_role()

### Community 836 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Failure / Retry Behaviour, Instructions, Skill: implementation-planner, Step 1 — Understand the current state, Step 2 — Write the plan, Step 3 — Get implicit approval before coding, Step 4 — Implement (+2 more)

### Community 837 - "Skill: pro-workflow"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Model Selection Guide, Phase 1 — Research (Scout), Phase 2 — Plan, Phase 3 — Implement, Phase 4 — Wrap Up, Skill: pro-workflow (+2 more)

### Community 838 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Learnings File Doesn't Exist?, Skill: replay-learnings, Step 1 — Read the learnings file, Step 2 — Filter relevant learnings, Step 3 — Check recent checkpoint history, Step 4 — Surface blockers from previous session (+2 more)

### Community 839 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Skill: repo-memory-updater, Step 1 — Inventory what changed, Step 2 — Check root AGENTS.md, Step 3 — Check module AGENTS.md files, Step 4 — Update .Codex/state/, Step 5 — Commit the update (+2 more)

### Community 840 - "Skill: resource-panel"
Cohesion: 0.18
Nodes (10): Ask Claude to emit a resource panel, Automated via shell (git-based), Fields, Files, How to Use, Integration, Output Format, Purpose (+2 more)

### Community 841 - "Skill: sandboxed-exec"
Cohesion: 0.18
Nodes (10): Example — run tests in isolation, Example — validate a generated script before saving, How It Works, Output Format, Purpose, Security Notes, Skill: sandboxed-exec, Steps (for Claude to follow) (+2 more)

### Community 842 - "admin_update_task_router.py"
Cohesion: 0.22
Nodes (6): _expected_admin_secret(), _extract_admin_token(), register(), update_workflow_task(), UpdateTaskRequest, _verify_admin_secret()

### Community 844 - "Skill: dev-browser — Browser Automation via Sandboxed JS"
Cohesion: 0.18
Nodes (10): Browser API, CLI flags, Connect to existing Chrome, Full script example (Playwright Page API), Installation, LLM usage patterns, Performance, Primary invocation styles (+2 more)

### Community 845 - "ECC Harness Patterns Skill"
Cohesion: 0.18
Nodes (10): 1. Harness Detection & Adaptation, 2. Session Lifecycle Hooks, 3. Cross-Harness Model Selection, 4. Persistent Harness Registry, ECC Harness Patterns Skill, Files to Create/Modify, Implementation Plan, Patterns to Adopt (+2 more)

### Community 846 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Failure / Retry Behaviour, Instructions, Skill: implementation-planner, Step 1 — Understand the current state, Step 2 — Write the plan, Step 3 — Get implicit approval before coding, Step 4 — Implement (+2 more)

### Community 847 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Skill: repo-memory-updater, Step 1 — Inventory what changed, Step 2 — Check root CLAUDE.md, Step 3 — Check module CLAUDE.md files, Step 4 — Update .claude/state/, Step 5 — Commit the update (+2 more)

### Community 848 - "Stop-Slop Quality Skill"
Cohesion: 0.18
Nodes (10): AI Tells Detected, Business Jargon, Emphasis Crutches (Banned Adverbs), Implementation, Integration Points, Meta-Commentary, References, Stop-Slop Quality Skill (+2 more)

### Community 850 - "2. Critical Bugs & Exact Detection Signatures"
Cohesion: 0.18
Nodes (10): 1. PR Analysis Summary & Evaluation Rubric, 2. Critical Bugs & Exact Detection Signatures, 3. Architectural Refactoring Architecture, Applying the rubric to open PRs, 🔴 CRITICAL — Silent Error Propagation in Agent Loop & Tool Dispatch, 🔴 CRITICAL — Unhandled Rate Limits & State Checkpointing, 🔴 CRITICAL — Unsandboxed Tool Execution & SSRF Vulnerabilities, Evaluation Rubric (+2 more)

### Community 851 - "Issue #467 — Section 1: Pulled State + PR Inventory"
Cohesion: 0.18
Nodes (10): 1. Current Git State, 2. Open PRs (as of 2026-06-08), 3. Files Modified on consolidate/maturation-stable (vs master), 4. What Master Has (that consolidate doesn't), 5. What Is MISSING from master (0% delivered in #467), 6. Required Action Before Code, Branch: `consolidate/maturation-stable`, Issue #467 — Section 1: Pulled State + PR Inventory (+2 more)

### Community 852 - "Deploy to Google Cloud Run"
Cohesion: 0.18
Nodes (10): 1) Admin protection (required), 2) User API keys (required), 3) LLM provider (recommended), Build + deploy (Dockerfile), Deploy to Google Cloud Run, Notes / limitations on Cloud Run, Prereqs, Required configuration (+2 more)

### Community 853 - "Key Components"
Cohesion: 0.18
Nodes (10): 1. Input Embedding, 2. Multi-Head Self-Attention, 3. Residual Connections, 4. Feed-Forward Network (FFN), 5. Layer Normalization, Decoder-Only vs Encoder-Decoder, High-Level Structure, Key Components (+2 more)

### Community 854 - "Sampling Strategies Internals"
Cohesion: 0.18
Nodes (11): Beam Search, Greedy Decoding, Logit Processors (Structured Output), Min-p Sampling, Repetition Penalty, Sampling Strategies Internals, Temperature Sampling, The Output Distribution (+3 more)

### Community 855 - "test_scheduler_hydration_bounded.py"
Cohesion: 0.09
Nodes (10): _hydrate_scheduler_bounded(), _BrokenScheduler, _fake_schedule_store(), _FakeStore, _FastScheduler, _HangingScheduler, _isolate_warmup_overflow(), test_a_hanging_hydration_does_not_block_startup() (+2 more)

### Community 856 - "CI Troubleshooting Runbook"
Cohesion: 0.18
Nodes (10): A test hangs in CI but passes locally, All three CI jobs fail with "git exit code 128" in Post Checkout, CI Troubleshooting Runbook, CodeQL action version, Frontend tests fail in parallel / async timer leaks, GitHub Actions YAML block scalar — bash heredoc content at column 0, Python 3.13 compatibility status, Python test job fails — "Process completed with exit code 1", no .pytest_cache found (+2 more)

### Community 858 - "Worker Service — Operations Runbook"
Cohesion: 0.18
Nodes (10): Architecture, Deployment on Render, Environment variables, First-time setup, Graceful shutdown, Local development, Overview, Troubleshooting (+2 more)

### Community 859 - "_build_execution_request"
Cohesion: 0.24
Nodes (10): _build_execution_request(), admin_user(), _auto_approve(), non_admin_user(), test_admin_execute_after_approval_gates(), test_admin_execute_now_routine_auto_approves(), test_admin_execute_now_sensitive_target_gates(), test_default_intent_gates() (+2 more)

### Community 861 - "SkillsScreen.jsx"
Cohesion: 0.19
Nodes (12): autoRecommendCompanySkills(), discoverRemoteSkills(), listCompanySkills(), CATEGORY_COLORS, COMMERCE_SKILLS, effortColor, effortLabel, Explain() (+4 more)

### Community 862 - "test_bedrock_live.py"
Cohesion: 0.25
Nodes (4): test_bedrock_direct_boto3_ping(), test_bedrock_health_check_with_real_creds(), test_bedrock_model_id_is_accessible(), test_provider_router_bedrock_roundtrip()

### Community 863 - "test_tasks_reconciler_todo_requeue.py"
Cohesion: 0.24
Nodes (6): _make_task(), test_reconcile_handles_mixed_tasks(), test_reconcile_requeues_unqueued_todo(), test_reconcile_skips_active_task(), test_reconcile_skips_done_task(), test_reconcile_skips_todo_already_queued()

### Community 865 - "_push_down_where"
Cohesion: 0.18
Nodes (5): _is_pushable_scalar(), _push_down_where(), test_push_down_builds_where_for_indexed_equality(), test_push_down_ignores_non_indexed_and_operators(), test_push_down_pushes_in_operator()

### Community 868 - "test_harness_spec.py"
Cohesion: 0.17
Nodes (4): get_enrichment(), _AllSignatures, _AnyText, trusted_citations()

### Community 869 - "Security Policy"
Cohesion: 0.18
Nodes (11): Authentication, Authorization, How to Report, Known Security Trade-offs, Reporting a Vulnerability, Response Timeline, Scope, Security Design (+3 more)

### Community 875 - "_build_payload_or_500"
Cohesion: 0.18
Nodes (6): _build_payload_or_500(), _check_secret(), _expected_secret(), preview_digest_endpoint(), register(), send_daily_digest_endpoint()

### Community 876 - "DetectedSystem"
Cohesion: 0.03
Nodes (27): DetectedSystem, Evidence, _hostname_contains(), _hostname_matches(), add_sys(), _match_cname(), add_sys(), add_sys() (+19 more)

### Community 877 - "_list_configured_provider_records"
Cohesion: 0.18
Nodes (8): _build_provider_router(), _builtin_provider_records(), _chat_provider_policy(), _fallback_local_provider_record(), _list_configured_provider_records(), _nvidia_nim_provider_record(), _resolve_ollama_url(), _brain_is_configured()

### Community 878 - "test_hermes_server.py"
Cohesion: 0.18
Nodes (5): test_tasks_executes_via_internal_agent(), fake_execute(), test_tasks_failure_is_reported_not_crashed(), test_tasks_sets_orchestrator_bypass_across_http_hop(), capture_execute()

### Community 880 - "mask_secret"
Cohesion: 0.24
Nodes (4): mask_dict(), _mask(), mask_secret(), TestMaskSecret

### Community 881 - "_extractive_compress"
Cohesion: 0.18
Nodes (9): _extractive_compress(), _split_sentences(), test_compress_empty_text(), test_compress_prefers_query_relevant_sentences(), test_compress_result_non_empty_for_non_empty_input(), test_compress_short_text_verbatim(), test_split_sentences_basic(), test_split_sentences_empty() (+1 more)

### Community 883 - "What to clean up"
Cohesion: 0.20
Nodes (9): 2. Cloudflare Worker (frontend), 3. Local development machines, 4. GitHub secrets, 5. MongoDB collections, Post-Merge Environment Cleanup Guide, Post-merge verification checklist, Rollback, What changed (informational) (+1 more)

### Community 886 - "flesch_reading_ease"
Cohesion: 0.20
Nodes (4): _count_syllables(), estimate_pixel_width(), flesch_reading_ease(), TestHelpers

### Community 887 - "test_state_file_merge_drivers.py"
Cohesion: 0.47
Nodes (7): _both_sides_edit(), _git(), repo(), test_both_tracker_rows_survive(), test_graph_report_takes_the_incoming_side(), test_merging_master_into_a_branch_does_not_conflict(), _write()

### Community 888 - "test_empirical_verify.py"
Cohesion: 0.49
Nodes (7): _make_runner(), test_empirical_verify_disabled_by_default(), test_empirical_verify_flags_compile_failure(), test_empirical_verify_passes_clean_module_without_tests(), test_empirical_verify_runs_matching_tests_and_passes(), test_empirical_verify_runs_matching_tests_and_reports_failure(), test_empirical_verify_skips_non_python_files()

### Community 890 - "gather_render_evidence"
Cohesion: 0.18
Nodes (4): gather_render_evidence(), _phase_section(), _schedule(), test_evidence_reports_unavailable_when_render_is_not_configured()

### Community 891 - "_start_in_web_bot_tasks"
Cohesion: 0.29
Nodes (4): _keepalive_self_ping(), _start_in_web_bot_tasks(), _register(), _telegram_bot_supervisor()

### Community 894 - "enrich_quick_note_issues.py"
Cohesion: 0.13
Nodes (12): codeql_count(), dependabot_count(), main(), _repo_parts(), _request(), _dispatch_generation(), _fetch_open_issues(), _has_context() (+4 more)

### Community 895 - "Instructions"
Cohesion: 0.20
Nodes (9): Acceptance Checks, Instructions, Skill: insights, Step 1 — File change heatmap (which files change most), Step 2 — Failure pattern analysis, Step 3 — Retry analysis, Step 4 — Learnings frequency analysis, Step 5 — Produce a summary report (+1 more)

### Community 896 - "Protocol: Premium Utilitarian Minimalism UI Architect"
Cohesion: 0.20
Nodes (9): 1. Protocol Overview, 2. Absolute Negative Constraints (Banned Elements), 3. Typographic Architecture, 4. Color Palette (Warm Monochrome + Spot Pastels), 5. Component Specifications, 6. Iconography & Imagery Directives, 7. Subtle Motion & Micro-Animations, 8. Execution Protocol (+1 more)

### Community 897 - "The 5-Step Wrap-Up Ritual"
Cohesion: 0.20
Nodes (9): Acceptance Checks, Skill: wrap-up, Step 1 — Changes Audit, Step 2 — Quality Check, Step 3 — Learning Capture, Step 4 — Next Session Planning, Step 5 — One-Paragraph Summary, The 5-Step Wrap-Up Ritual (+1 more)

### Community 898 - "Brag Plan: Autonomous AI Agency (feature tour, v2)"
Cohesion: 0.20
Nodes (9): Audio, Brag Plan: Autonomous AI Agency (feature tour, v2), Duration: ~61s (12 scenes; v3 added SAM, learning and guardrails before the outro) — intentionally longer than the /brag 15-25s default, per an explicit user request for a longer video, Format: landscape — 1920x1080, Storyboard (9 scenes), The angle, Tone, Visual identity (from the project) (+1 more)

### Community 899 - "de"
Cohesion: 0.27
Nodes (10): Be(), $d(), de(), fe(), ka(), me(), ne(), se() (+2 more)

### Community 900 - "Hyperframes Composition Brief: Autonomous AI Agency (feature tour, v2)"
Cohesion: 0.20
Nodes (9): Audio, Creative Direction, Hyperframes Composition Brief: Autonomous AI Agency (feature tour, v2), Hyperframes Instructions, Objective, Output, Source Material, Storyboard (+1 more)

### Community 901 - "Skill: Agentic Agile"
Cohesion: 0.20
Nodes (9): Autonomous ceremonies (`agents/agile_ceremonies.py`), Key Classes, Purpose, Related, Retrospective & health, Scheduled workflow, Skill: Agentic Agile, Testing (+1 more)

### Community 902 - "Skill: browserbase-ui-test — Adversarial UI Testing"
Cohesion: 0.20
Nodes (9): Applying to local-llm-server platform, Core philosophy, Execution pattern, Reporting, Round 1 — Core flow mapping, Round 2 — Adversarial scenarios, Round 3 — Accessibility + mobile, Skill: browserbase-ui-test — Adversarial UI Testing (+1 more)

### Community 903 - "Workflow"
Cohesion: 0.22
Nodes (8): Acceptance checks, Fill these in, Skill: client-onboarding, Step 1 — Create the company and kick off onboarding, Step 2 — Poll progress, Step 3 — Verify specialists were provisioned, Step 4 — Confirm the 24x7 agency runtime is live, Workflow

### Community 904 - "Skill: financial-analyst (Agentic CFO)"
Cohesion: 0.20
Nodes (9): Branch, Components, Decision Rules, Purpose, Quick Start, Skill: financial-analyst (Agentic CFO), SKILL.md refresh Tue Jun  2 11:35:52 CEST 2026, Testing (+1 more)

### Community 905 - "Graphiti Temporal Context Skill"
Cohesion: 0.20
Nodes (9): 1. Agent Memory as Temporal Graph, 2. Multi-Agent Coordination, 3. Knowledge Queries, Database Schema, Files to Create, Graphiti Temporal Context Skill, Integration Opportunities, References (+1 more)

### Community 906 - "Skill: seo-audit-report"
Cohesion: 0.20
Nodes (9): How This Skill Works (Agent Instructions), Output Files, Parameters, Purpose, Quick Start, Revenue-at-Risk Disclaimer (load-bearing — always include in reports), Skill: seo-audit-report, Troubleshooting (+1 more)

### Community 907 - "Agent Readiness Report"
Cohesion: 0.20
Nodes (9): Agent Readiness Report, Build System — 100/100, Dev Environment — 100/100, Documentation — 100/100, Observability — 100/100, Security — 100/100, Style And Validation — 100/100, Task Discovery — 100/100 (+1 more)

### Community 909 - "Competitor Analysis — Autonomous AI Agency"
Cohesion: 0.20
Nodes (9): 1. Fix the framing first: these are two different markets, 2. What this repo actually is (verified on `master`), 3. Where we already beat the competitor set — keep and market these, 4. The gaps worth closing (ranked by value ÷ effort), 5. Recommended PR sequence, Competitor Analysis — Autonomous AI Agency, Gap A — The workflow engine is built but unreachable  ← **highest leverage**, Gap B — Connector catalog is nearly empty (+1 more)

### Community 910 - "One command (recommended)"
Cohesion: 0.20
Nodes (10): Add a model provider (optional but recommended), Docker Compose, Flags, One command (recommended), Requirements, Run the agency locally, Troubleshooting, What comes up (+2 more)

### Community 911 - "test_procedural_memory.py"
Cohesion: 0.24
Nodes (4): _record_id(), store(), TestClear, TestRecordId

### Community 912 - "test_server_autonomy_and_index_fixes.py"
Cohesion: 0.20
Nodes (3): test_autonomy_bg_cycle_has_no_undefined_globals(), test_source_id_index_is_partial_not_sparse(), _undefined_globals()

### Community 913 - "autonomous_fix.py"
Cohesion: 0.16
Nodes (11): _decline(), _extract_pytest_failure(), _fetch_failure_context(), _list_target_prs(), main(), _post_comment(), _pr_head(), _prior_attempt_count() (+3 more)

### Community 914 - "test_serve_spa_prefixes.py"
Cohesion: 0.24
Nodes (5): _prefixes(), test_legitimate_spa_paths_are_not_blocked(), test_protected_paths_are_covered_by_prefix_tuple(), test_serve_spa_returns_non_html_for_protected_orphan_path(), test_spa_protected_prefixes_is_module_level_constant()

### Community 915 - "Runbook — Instance Activation"
Cohesion: 0.25
Nodes (7): Option A — disable the gate (self-hosted), Option B — self-mint a signed code with your own key, Option C — request a code (downstream user), Runbook — Instance Activation, Security notes, TL;DR — you are blocked at the activation screen, Why activation exists

### Community 917 - "SamVoiceScreen.jsx"
Cohesion: 0.24
Nodes (5): API, AudioVisualizer(), SamRing(), SamVoiceScreen(), livekit-client

### Community 918 - "audit"
Cohesion: 0.09
Nodes (11): audit(), get_audit_log(), get_user_role(), is_admin(), is_power_user_or_above(), require_authenticated(), role_label(), TestAuditLog (+3 more)

### Community 919 - "TestTheProducersAndTheParserCannotDrift"
Cohesion: 0.20
Nodes (3): prior_art_cell(), _build_grounding_block(), TestTheProducersAndTheParserCannotDrift

### Community 920 - "run_patched_colibri.py"
Cohesion: 0.27
Nodes (4): _exit_watch_delay(), main(), _patched_popen(), _resolve_target()

### Community 921 - "test_phase4_runtime_resilience.py"
Cohesion: 0.09
Nodes (15): _env_flag(), _make_task(), test_create_worktree_fallback_to_copy(), test_default_manager_registers_internal_agent_only(), test_dispatcher_reconciles_on_startup(), test_env_flag_false_variants(), test_env_flag_missing_uses_default(), test_env_flag_true_variants() (+7 more)

### Community 926 - "test_backend_lifespan_skips_bg_when_flag_false"
Cohesion: 0.24
Nodes (4): test_backend_lifespan_skips_bg_when_flag_false(), test_backend_lifespan_starts_runtime_manager_and_dispatcher(), fake_ensure_bootstrap(), fake_start_background_services()

### Community 928 - "_is_exempt"
Cohesion: 0.29
Nodes (3): _is_exempt(), TestScopedPrefixesAreExempt, TestUnrelatedPrefixesAreNotExempt

### Community 930 - "test_dependabot_sweep_workflow.py"
Cohesion: 0.05
Nodes (10): _job_text(), TestBacklogActuallyDrains, TestConflictedPullRequestsGetUnstuck, TestLockfileRepair, TestMajorBumpsStayWithHumans, TestStaleBranchHandling, TestSweepStillCannotForceAnything, TestTokenChoice (+2 more)

### Community 934 - "test_event_log.py"
Cohesion: 0.45
Nodes (9): _store(), test_append_event_payload_roundtrips(), test_append_event_positions_are_monotonic(), test_append_event_stores_and_increments_count(), test_events_are_isolated_per_session(), test_events_survive_store_restart(), test_get_events_empty_session(), test_get_events_from_position() (+1 more)

### Community 935 - "_run_analyze"
Cohesion: 0.27
Nodes (3): _run_analyze(), TestAnalyzeFailuresClassifiesRealFailures, TestAnalyzeFailuresDoesNotCrashOnNoMatch

### Community 937 - "sam_router.py"
Cohesion: 0.29
Nodes (6): _ask_llm(), _parse(), route(), RoutedAction, catalogue_prompt(), test_catalogue_prompt_lists_every_tool()

### Community 939 - "test_workflow_api_mount.py"
Cohesion: 0.20
Nodes (4): test_workflow_list_forbidden_for_non_admin(), test_workflow_list_ok_for_admin(), test_workflow_list_requires_authentication(), test_workflow_route_is_mounted_not_404()

### Community 941 - "test_doctor_coding_brain.py"
Cohesion: 0.32
Nodes (4): client(), _coding_brain_check(), test_coding_brain_check_reflects_flag_off(), test_doctor_includes_coding_brain_check()

### Community 944 - "test_model_catalog_guard.py"
Cohesion: 0.29
Nodes (6): _declared(), test_declared_folds_both_provider_spellings(), test_legacy_only_provider_is_not_a_contradiction(), test_prefer_models_must_be_declared(), test_real_contradiction_is_a_hard_failure(), test_the_real_repo_catalogues_are_consistent()

### Community 946 - "Advisor Strategy — Local Proxy Handling"
Cohesion: 0.25
Nodes (7): Advisor Strategy — Local Proxy Handling, How This Proxy Handles Advisor Requests, Incoming message history (advisor blocks), Local Equivalent: The Planner Role, Outgoing requests (tools array), Using the Real Advisor Strategy via This Proxy, What the Anthropic Advisor Strategy Is

### Community 950 - "LLMReasoner"
Cohesion: 0.28
Nodes (5): LLMReasoner, Components, handler(), TestLLMReasoner, handler()

### Community 951 - "Skill: changelog-enforcer"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Changelog Location, Entry Format, Examples, Hook Behaviour, Instructions, Skill: changelog-enforcer, When to Use

### Community 952 - "Skill: learn-rule"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Instructions, Learnings File Format, Skill: learn-rule, Step 1 — Identify the rule, Step 2 — Append to learnings file, Step 3 — Check if CLAUDE.md should be updated, When to Use

### Community 953 - "Instructions"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Instructions, Skill: session-handoff, Step 1 — Capture current state, Step 2 — Write the handoff document, Step 3 — Update machine-readable state, Step 4 — Confirm the handoff is self-contained, When to Use

### Community 954 - "AgentJobResult"
Cohesion: 0.09
Nodes (5): AgentJobError, AgentJobResult, Roadmap, TestAgentJobError, TestAgentJobResult

### Community 955 - "Skill: changelog-enforcer"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Changelog Location, Entry Format, Examples, Hook Behaviour, Instructions, Skill: changelog-enforcer, When to Use

### Community 956 - "Skill: cowork-session (Claude Cowork)"
Cohesion: 0.22
Nodes (8): Branch, Components, Purpose, Quick Start, Session Roles, Skill: cowork-session (Claude Cowork), Testing, When to Use

### Community 957 - "Skill: video-context — read a video without watching it"
Cohesion: 0.22
Nodes (8): How It Works, Limits — know these before relying on it, Skill: video-context — read a video without watching it, Testing, Usage, What To Do With The Transcript, When To Use This, Why This Exists

### Community 958 - "ADR 003: Multi-Agent Orchestration with Plan-Execute-Verify Loop"
Cohesion: 0.22
Nodes (8): ADR 003: Multi-Agent Orchestration with Plan-Execute-Verify Loop, Alternatives Considered, Consequences, Context, Decision, Negative, Neutral, Positive

### Community 959 - "Issue #1356: quick-note:https://searchengineland.com/turn-seo-backlog-into-roadmap-485713"
Cohesion: 0.22
Nodes (8): Architectural Notes, Context Plan — Issue #1356: quick-note:https://searchengineland.com/turn-seo-backlog-into-roadmap-485713, Decision, Issue #1356: quick-note:https://searchengineland.com/turn-seo-backlog-into-roadmap-485713, Quality Gate, Source Grounding, What the source actually is, What was considered

### Community 962 - "Release Procedure"
Cohesion: 0.22
Nodes (8): Changelog Update, Commit and Tag, Post-Release Checklist, Pre-Flight, Release Procedure, Rollback, Verify CI, Version Bump

### Community 963 - "V2.0 Modernization — Runbook"
Cohesion: 0.22
Nodes (8): Adding a new provider adapter, CI, Importing new code, Module map (old → new), Removing the shims (future cleanup), Rollback, Test migration, V2.0 Modernization — Runbook

### Community 964 - "LoopsScreen.jsx"
Cohesion: 0.36
Nodes (8): Badge(), COST_COLOR, fmtTokens(), GATE_META, GRADE_COLOR, LEVEL_META, LoopsScreen(), ReadinessHeader()

### Community 966 - "scrub"
Cohesion: 0.22
Nodes (4): scrub(), test_a_credential_in_the_failure_message_never_reaches_the_issue_body(), test_scrub_fails_closed_when_a_redaction_helper_is_missing(), test_scrub_keeps_the_non_secret_context_readable()

### Community 967 - "openclaw_status"
Cohesion: 0.22
Nodes (4): _openclaw_instructions(), openclaw_reverse_proxy(), openclaw_status(), is_gateway_alive()

### Community 968 - "_build_pdf"
Cohesion: 0.28
Nodes (5): _build_pdf(), findings_block(), hr(), S(), section()

### Community 969 - "analyze_quantitative"
Cohesion: 0.13
Nodes (8): analyze_quantitative(), apply_recommendations(), collect_codebase_metrics(), extract_qualitative_themes(), main(), plan_repo_scan(), synthesize_brief(), TestAnalyzeQuantitative

### Community 970 - "record_usage_endpoint"
Cohesion: 0.22
Nodes (4): record_usage(), record_usage_endpoint(), UsageRecord, UsageRecordRequest

### Community 972 - "build_digest"
Cohesion: 0.33
Nodes (3): build_digest(), _count_open_auto_prs(), TestBuildDigest

### Community 973 - "RoutingDecision"
Cohesion: 0.09
Nodes (10): drop_denied(), is_model_denied(), _apply_deny_list(), RoutingDecision, _decision(), denied(), _provider(), TestDispatch (+2 more)

### Community 974 - "Core Pillars"
Cohesion: 0.22
Nodes (8): 1. Unified Intent Orchestration, 2. Deep Sticky Memory, 3. Execution Cognition Flow, 4. Progress Humanization, Core Pillars, Direct Chat Evolution: Seamless Assistant Architecture, Failure Recovery, Overview

### Community 977 - "_infer_parameters_from_func"
Cohesion: 0.38
Nodes (3): _infer_parameters_from_func(), TestInferParameters, func()

### Community 978 - "_get_current_user"
Cohesion: 0.25
Nodes (3): _get_bearer_token(), _get_current_user(), logout()

### Community 982 - "WorkflowOrchestrator"
Cohesion: 0.03
Nodes (11): DirectChatDoctor, Changed, Changed, Feature maturity — what's stable vs. beta, bind_agent(), get_orchestrator_checkpoint_store(), _NoopStore, WorkflowOrchestrator (+3 more)

### Community 987 - "oauth.py"
Cohesion: 0.28
Nodes (3): _github_login_url(), _google_login_url(), _new_state()

### Community 988 - "SECTION C — Direct Chat Improvements (CBF / HRM)"
Cohesion: 0.25
Nodes (8): C1 — Structured Output / JSON Mode [P0] [CBF / HRM], C2 — Function Calling / Tool Use (OpenAI-Compatible) [P0] [CBF / HRM], C3 — Streaming with Proper Delta Reconstruction [P1] [CBF], C4 — Chat History Persistence + Retrieval [P1] [AOS / HRM], C5 — Context Window Management + Smart Truncation [P1] [CBF / HRM], C6 — Prompt Caching (Anthropic-Compatible) [P1] [HRM], C7 — Embeddings Pipeline + Vector Search [P2] [AOS / CBF], SECTION C — Direct Chat Improvements (CBF / HRM)

### Community 991 - "stt.py"
Cohesion: 0.36
Nodes (5): _select_backend(), transcribe(), _transcribe_google(), _transcribe_local(), _transcribe_openai()

### Community 992 - "test_process_quick_note_workflow.py"
Cohesion: 0.25
Nodes (5): _full_suite_jobs(), job(), _runs_full_suite(), TestRetryDoesNotOverrideAPlanGateRejection, workflow_text()

### Community 994 - "test_daily_automation_2026_10_03.py"
Cohesion: 0.04
Nodes (10): ct(), llm_models(), models_yaml(), TestMinistral3bCostEntries, TestMinistral3bModelYaml, TestMinistral8bCostEntries, TestMinistral8bModelYaml, TestNewMistralModelsNotInCandidates (+2 more)

### Community 998 - "get_ceo_ledger"
Cohesion: 0.12
Nodes (12): build_ceo_router(), ceo_status(), get_goal(), list_goals(), redrive_goal(), run_sweep(), _require_admin(), BackgroundServices (+4 more)

### Community 1000 - "Skill: docs-sync"
Cohesion: 0.25
Nodes (7): Acceptance Checks, ADR Guidelines, AGENTS.md Update Rules, Docs to Check After Each Change Type, Instructions, Skill: docs-sync, When to Use

### Community 1002 - "Skill: browserbase-browser — Real Browser Automation"
Cohesion: 0.25
Nodes (7): Applying to local-llm-server platform, Core commands, Mode selection, Setup, Skill: browserbase-browser — Real Browser Automation, Troubleshooting, Workflow pattern

### Community 1003 - "Skill: docs-sync"
Cohesion: 0.25
Nodes (7): Acceptance Checks, ADR Guidelines, CLAUDE.md Update Rules, Docs to Check After Each Change Type, Instructions, Skill: docs-sync, When to Use

### Community 1004 - "Skill: memory-consolidation (Dream Memory)"
Cohesion: 0.25
Nodes (7): Branch, Consolidation Lifecycle, Memory Kinds, Purpose, Quick Start, Skill: memory-consolidation (Dream Memory), Testing

### Community 1007 - "GitHub Branch Protection Settings"
Cohesion: 0.25
Nodes (7): Branch name pattern: `main` (or `master`), CODEOWNERS Setup, Enabling via GitHub CLI, GitHub Branch Protection Settings, Purpose, Required Settings, Why This Can't Be Fully Repo-Enforced

### Community 1008 - "ADR 001: Self-Hosted OpenAI-Compatible Proxy"
Cohesion: 0.25
Nodes (7): ADR 001: Self-Hosted OpenAI-Compatible Proxy, Consequences, Context, Decision, Negative, Neutral, Positive

### Community 1009 - "test_cost_attribution.py"
Cohesion: 0.09
Nodes (7): _build_cost_table(), _load_env_overrides(), _reset(), TestClearStats, TestCostForTokens, TestEnvOverrides, TestGetCostTable

### Community 1010 - "AGENTS.md — AI Agent Configuration for local-llm-server"
Cohesion: 0.25
Nodes (7): Agent Roles, AGENTS.md — AI Agent Configuration for local-llm-server, Operating Instructions, Quick Start for Agents, Risky Paths — Require Extra Care, State Files, Workspace Purpose

### Community 1012 - "Web UI + Admin (Claude Code–style)"
Cohesion: 0.25
Nodes (7): Acceptance checks, Approach, Files to change, Files to read first, Goal, Risks, Web UI + Admin (Claude Code–style)

### Community 1013 - "467 Skill Inventory — load / wire / test status"
Cohesion: 0.25
Nodes (7): 467 Skill Inventory — load / wire / test status, Agent Specialties (not skills per se, but referenced in spec §B), Core Agency Skills (load/wire/test), Gaps Summary, Named Skills Referenced in Spec §C, Skill Registry, Test Coverage Summary

### Community 1014 - "Issue #362: Nvidia repo setup"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #362: Nvidia repo setup, Implementation Prompt, Issue #362: Nvidia repo setup, Relevant Files to Read First, Risk Flags, TODO List

### Community 1015 - "Issue #364: quick-note:https://www.marktechpost.com/2026/06/01/meet-memory-os-a-6-layer-open-source-memory-stack-built-on-top-of-hermes-agent/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #364: quick-note:https://www.marktechpost.com/2026/06/01/meet-memory-os-a-6-layer-open-source-memory-stack-built-on-top-of-hermes-agent/, Implementation Prompt, Issue #364: quick-note:https://www.marktechpost.com/2026/06/01/meet-memory-os-a-6-layer-open-source-memory-stack-built-on-top-of-hermes-agent/, Relevant Files to Read First, Risk Flags, TODO List

### Community 1016 - "Issue #378: quick-note:https://www.marktechpost.com/2026/06/02/tinyfish-launches-bigset-an-open-source-multi-agent-system-that-builds-structured-live-datasets-from-plain-english-descriptions/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #378: quick-note:https://www.marktechpost.com/2026/06/02/tinyfish-launches-bigset-an-open-source-multi-agent-system-that-builds-structured-live-datasets-from-plain-english-descriptions/, Implementation Prompt, Issue #378: quick-note:https://www.marktechpost.com/2026/06/02/tinyfish-launches-bigset-an-open-source-multi-agent-system-that-builds-structured-live-datasets-from-plain-english-descriptions/, Relevant Files to Read First, Risk Flags, TODO List

### Community 1017 - "Issue #379: quick-note:https://searchengineland.com/schema-markup-optimize-agentic-web-479080"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #379: quick-note:https://searchengineland.com/schema-markup-optimize-agentic-web-479080, Implementation Prompt, Issue #379: quick-note:https://searchengineland.com/schema-markup-optimize-agentic-web-479080, Relevant Files to Read First, Risk Flags, TODO List

### Community 1018 - "Issue #380: quick-note:https://cursor.com/blog/cloud-agent-lessons"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #380: quick-note:https://cursor.com/blog/cloud-agent-lessons, Implementation Prompt, Issue #380: quick-note:https://cursor.com/blog/cloud-agent-lessons, Relevant Files to Read First, Risk Flags, TODO List

### Community 1019 - "Issue #381: quick-note:https://www.xda-developers.com/claude-code-with-opus-48-is-expensive-but-i-made-it-efficient-with-my-local-ai-workflow/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #381: quick-note:https://www.xda-developers.com/claude-code-with-opus-48-is-expensive-but-i-made-it-efficient-with-my-local-ai-workflow/, Implementation Prompt, Issue #381: quick-note:https://www.xda-developers.com/claude-code-with-opus-48-is-expensive-but-i-made-it-efficient-with-my-local-ai-workflow/, Relevant Files to Read First, Risk Flags, TODO List

### Community 1020 - "Issue #382: quick-note:https://claude.com/blog/how-coderabbit-used-claude-to-build-an-agent-orchestration-system"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #382: quick-note:https://claude.com/blog/how-coderabbit-used-claude-to-build-an-agent-orchestration-system, Implementation Prompt, Issue #382: quick-note:https://claude.com/blog/how-coderabbit-used-claude-to-build-an-agent-orchestration-system, Relevant Files to Read First, Risk Flags, TODO List

### Community 1021 - "Issue #383: quick-note:https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #383: quick-note:https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/, Implementation Prompt, Issue #383: quick-note:https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/, Relevant Files to Read First, Risk Flags, TODO List

### Community 1022 - "Issue #416: feat: Self-hosted Codebuff (freebuff) on free NVIDIA models + Telegram bot phone control"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #416: feat: Self-hosted Codebuff (freebuff) on free NVIDIA models + Telegram bot phone control, Implementation Prompt, Issue #416: feat: Self-hosted Codebuff (freebuff) on free NVIDIA models + Telegram bot phone control, Relevant Files to Read First, Risk Flags, TODO List

### Community 1023 - "Issue #485: [Trend Digest] Week of 2026-06-08"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #485: [Trend Digest] Week of 2026-06-08, Implementation Prompt, Issue #485: [Trend Digest] Week of 2026-06-08, Relevant Files to Read First, Risk Flags, TODO List

### Community 1024 - "Issue #488: quick-note:https://github.com/cookiy-ai/user-research-skill"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #488: quick-note:https://github.com/cookiy-ai/user-research-skill, Implementation Prompt, Issue #488: quick-note:https://github.com/cookiy-ai/user-research-skill, Relevant Files to Read First, Risk Flags, TODO List

### Community 1025 - "Issue #491: Implement whatever is necessary from https://github.com/BehiSecc/awesome-claude-skills"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #491: Implement whatever is necessary from https://github.com/BehiSecc/awesome-claude-skills, Implementation Prompt, Issue #491: Implement whatever is necessary from https://github.com/BehiSecc/awesome-claude-skills, Relevant Files to Read First, Risk Flags, TODO List

### Community 1026 - "Issue #493: Use the https://github.com/mvanhorn/last30days-skill skill to get the trend updated"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #493: Use the https://github.com/mvanhorn/last30days-skill skill to get the trend updated, Implementation Prompt, Issue #493: Use the https://github.com/mvanhorn/last30days-skill skill to get the trend updated, Relevant Files to Read First, Risk Flags, TODO List

### Community 1027 - "Issue #495: Read https://www.anthropic.com/news/claude-fable-5-mythos-5 and understand if mythos or fable can be added to the repo"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #495: Read https://www.anthropic.com/news/claude-fable-5-mythos-5 and understand if mythos or fable can be added to the repo, Implementation Prompt, Issue #495: Read https://www.anthropic.com/news/claude-fable-5-mythos-5 and understand if mythos or fable can be added to the repo, Relevant Files to Read First, Risk Flags, TODO List

### Community 1028 - "Runtime troubleshooting"
Cohesion: 0.33
Nodes (4): Agent mode timeout, Missing binary / task harness, Runtime troubleshooting, Workspace validation failures

### Community 1029 - "Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass, Implementation Prompt, Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass, Relevant Files to Read First, Risk Flags, TODO List

### Community 1030 - "begin_call"
Cohesion: 0.17
Nodes (4): begin_call(), current_call(), GatewayCall, _raw_key()

### Community 1031 - "Issue #657: quick-note:https://github.com/earendil-works/pi"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #657: quick-note:https://github.com/earendil-works/pi, Implementation Prompt, Issue #657: quick-note:https://github.com/earendil-works/pi, Relevant Files to Read First, Risk Flags, TODO List

### Community 1032 - "Issue #659: quick-note:https://github.com/nex-agi/Nex-N2"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #659: quick-note:https://github.com/nex-agi/Nex-N2, Implementation Prompt, Issue #659: quick-note:https://github.com/nex-agi/Nex-N2, Relevant Files to Read First, Risk Flags, TODO List

### Community 1033 - "Issue #660: quick-note:https://github.com/getsentry/sentry-for-ai"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #660: quick-note:https://github.com/getsentry/sentry-for-ai, Implementation Prompt, Issue #660: quick-note:https://github.com/getsentry/sentry-for-ai, Relevant Files to Read First, Risk Flags, TODO List

### Community 1034 - "Issue #661: quick-note:https://github.com/XiaomiMiMo/MiMo-Code"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #661: quick-note:https://github.com/XiaomiMiMo/MiMo-Code, Implementation Prompt, Issue #661: quick-note:https://github.com/XiaomiMiMo/MiMo-Code, Relevant Files to Read First, Risk Flags, TODO List

### Community 1035 - "Issue #664: quick-note:https://github.com/Grominet95/jarvis-OS"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #664: quick-note:https://github.com/Grominet95/jarvis-OS, Implementation Prompt, Issue #664: quick-note:https://github.com/Grominet95/jarvis-OS, Relevant Files to Read First, Risk Flags, TODO List

### Community 1036 - "Issue #666: quick-note:https://github.com/porokka/jarvis-os"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #666: quick-note:https://github.com/porokka/jarvis-os, Implementation Prompt, Issue #666: quick-note:https://github.com/porokka/jarvis-os, Relevant Files to Read First, Risk Flags, TODO List

### Community 1037 - "Issue #670: quick-note:https://github.com/perplexityai/bumblebee"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #670: quick-note:https://github.com/perplexityai/bumblebee, Implementation Prompt, Issue #670: quick-note:https://github.com/perplexityai/bumblebee, Relevant Files to Read First, Risk Flags, TODO List

### Community 1038 - "Issue #672: quick-note:https://github.com/Chachamaru127/claude-code-harness"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #672: quick-note:https://github.com/Chachamaru127/claude-code-harness, Implementation Prompt, Issue #672: quick-note:https://github.com/Chachamaru127/claude-code-harness, Relevant Files to Read First, Risk Flags, TODO List

### Community 1039 - "Issue #676: quick-note:https://github.com/WeiboAI/VibeThinker"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #676: quick-note:https://github.com/WeiboAI/VibeThinker, Implementation Prompt, Issue #676: quick-note:https://github.com/WeiboAI/VibeThinker, Relevant Files to Read First, Risk Flags, TODO List

### Community 1040 - "Issue #820: quick-note:https://github.com/cobusgreyling/loop-engineering"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #820: quick-note:https://github.com/cobusgreyling/loop-engineering, Implementation Prompt, Issue #820: quick-note:https://github.com/cobusgreyling/loop-engineering, Relevant Files to Read First, Risk Flags, TODO List

### Community 1042 - "Prime Agent Runtime"
Cohesion: 0.25
Nodes (8): Configuration, Deploying on Render, Installation, Prime Agent Runtime, `PRIME_AGENT_TRUST_WORKSPACE`, Routing LLM traffic through our proxy, Verifying, What the adapter drives

### Community 1043 - "commercial_equivalent.py"
Cohesion: 0.50
Nodes (5): CommercialEquivalent, estimate_commercial_equivalent_usd(), get_prices(), _load_from_env(), _parse_mapping()

### Community 1044 - "The full agent capability roster"
Cohesion: 0.33
Nodes (6): Agile, portfolio & product, Business & domain specialists (auto-provisioned from the URL scan), Content & knowledge, Engineering, Operations & DevOps, The full agent capability roster

### Community 1045 - "PULL_REQUEST_TEMPLATE.md"
Cohesion: 0.25
Nodes (7): Changelog, Changes, Council Review (for larger PRs), Related, Risky Module Review, Summary, Testing

### Community 1050 - "FreeBuff — free-NVIDIA coding agent"
Cohesion: 0.25
Nodes (7): Free model set, FreeBuff — free-NVIDIA coding agent, HTTP API, Unlimited by default, _is_freebuff_unlimited(), test_freebuff_unlimited_can_be_disabled(), test_is_freebuff_unlimited_path()

### Community 1051 - "Sol Advisor"
Cohesion: 0.25
Nodes (7): Go deeper, Quick start, Routes, Sol Advisor, Updating, What happens automatically, What you do

### Community 1052 - "verify.sh"
Cohesion: 0.50
Nodes (6): fail(), pass(), verify.sh script, snapshot_files(), write_legacy_roles(), write_v050_roles()

### Community 1053 - "Tailored Onboarding, Editable Companies & Dynamic Roles"
Cohesion: 0.25
Nodes (7): 1. Editable companies, anytime (not a one-shot wizard), 2. Question-driven provisioning — no cosmetic questions, 4. Agents start pre-powered, Invariants, Phases, Tailored Onboarding, Editable Companies & Dynamic Roles, The gaps to close

### Community 1054 - "run_seo_audit.py"
Cohesion: 0.07
Nodes (17): export_seo_audit(), _build_curl_cffi_fetcher(), get(), get_text(), head(), _sess(), main(), _parse_args() (+9 more)

### Community 1055 - "Setup"
Cohesion: 0.25
Nodes (8): 1. Clone and install, 2. Configure, 3. Start the backend, 4. Start the frontend (development), 5. Onboard your first company, 6. Connect your AI coding tools (optional), Setup, What you need

### Community 1057 - "SECTION A — Agent Efficiency (Hermes / AOS / MYT)"
Cohesion: 0.25
Nodes (8): A1 — Hermes ChatML Prompt Format for Tool Calling [P0] [HRM], A2 — Multi-Hop Reasoning Chain (ReAct / Tree-of-Thought) [P0] [HRM], A3 — Agent Capability Registry + Dynamic Tool Discovery [P1] [AOS], A4 — Async Task Queue with Priority and Backpressure [P1] [AOS], A5 — Inter-Agent Message Bus [P1] [AOS / MYT], A6 — Shared Blackboard Memory for Swarm Agents [P1] [MYT], A7 — Agent Self-Improvement Loop [P2] [HRM / AOS], SECTION A — Agent Efficiency (Hermes / AOS / MYT)

### Community 1059 - "AlertsBell.jsx"
Cohesion: 0.36
Nodes (7): getActivity(), activityToAlert(), AlertItem(), AlertsBell(), priorityConfig, _relativeTime(), typeIcon

### Community 1060 - "Prompt Library"
Cohesion: 0.25
Nodes (8): Agents, Commands, How This Library Is Maintained, Philosophy, Prompt Library, Skills, Transparency, What Is This?

### Community 1062 - "test_ping.py"
Cohesion: 0.36
Nodes (5): client(), test_ping_no_auth_required(), test_ping_response_shape(), test_ping_returns_ok(), test_ping_timestamp_is_iso()

### Community 1065 - "PhaseSequenceError"
Cohesion: 0.10
Nodes (17): Beta, Config Overrides, Disabled (demoted per issue #467 Section I), Enforcement, Experimental, Feature Maturity / Support Matrix, Maturity Tiers, 0. The goal (unchanged) (+9 more)

### Community 1067 - "_fixture"
Cohesion: 0.02
Nodes (66): app_client(), _clear_discovered_models(), _clear_response_cache(), _isolate_operator_provider_state(), _set_legacy_workflow_mode(), base_url(), mobile_page(), proxy_url() (+58 more)

### Community 1068 - "test_local_brain_router_smoke.py"
Cohesion: 0.25
Nodes (3): test_backend_server_app_loads_without_attributeerror(), test_local_brain_router_module_is_wired(), test_local_brain_state_route_is_mounted_on_public_app()

### Community 1075 - "_FakeCollection"
Cohesion: 0.25
Nodes (3): fake_mongo(), _FakeCollection, _FakeDb

### Community 1077 - "test_setup_detect_models_ssrf.py"
Cohesion: 0.40
Nodes (3): test_admin_may_probe_a_lan_ollama(), test_anonymous_probe_of_private_address_is_refused(), test_default_loopback_ollama_still_works()

### Community 1079 - "classify_domain"
Cohesion: 0.29
Nodes (3): classify_domain(), test_classify_domain(), test_classify_domain_case_insensitive()

### Community 1080 - "dry_clone_repo"
Cohesion: 0.32
Nodes (3): test_dry_clone_repo_handles_missing_url(), test_dry_clone_repo_handles_subprocess_failure(), dry_clone_repo()

### Community 1082 - "What's New"
Cohesion: 0.29
Nodes (7): 2026-06-16, 2026-06-25, 2026-06-26, 2026-07-04, 2026-07-05, 2026-07-09, What's New

### Community 1084 - "Setup"
Cohesion: 0.25
Nodes (7): 1. Get LiveKit credentials, 2. Configure the backend (Render env vars), 3. The SAM voice worker, 4. Talk to SAM, SAM Realtime Voice over LiveKit, Setup, Troubleshooting

### Community 1085 - "Model and Response Issues"
Cohesion: 0.29
Nodes (7): Model and Response Issues, Model eviction between requests, "Model not found" or 404 on model requests, Responses are empty or very short, Responses get cut off mid-sentence, `<think>...</think>` appears in responses, Very slow first response (30–90 seconds)

### Community 1088 - "Marketing Content Creator Agent"
Cohesion: 0.29
Nodes (6): Core Capabilities, Decision Framework, Identity & Role Definition, Marketing Content Creator Agent, Specialized Skills, Success Metrics

### Community 1089 - "Marketing Growth Hacker Agent"
Cohesion: 0.29
Nodes (6): Core Capabilities, Decision Framework, Identity & Role Definition, Marketing Growth Hacker Agent, Specialized Skills, Success Metrics

### Community 1090 - "Full-Output Enforcement"
Cohesion: 0.29
Nodes (6): Banned Output Patterns, Baseline, Execution Process, Full-Output Enforcement, Handling Long Outputs, Quick Check

### Community 1091 - "summarise.sh"
Cohesion: 0.48
Nodes (5): bottom(), divider(), row(), summarise.sh script, top()

### Community 1092 - "TOP 6 — Highest-ROI Items (Validated by Opus Research Agent)"
Cohesion: 0.29
Nodes (7): ★1 — 3-Phase Context-Pruner Middleware [P0] [CBF], ★2 — Specialized Sub-Agents with Per-Role Cheap Models [P0] [CBF + HRM], ★3 — Reasoning Token Budget + Toggle [P0] [NVD], ★4 — Skill/Procedural Memory (agentskills.io compatible) [P1] [HRM], ★6 — Cost Analytics + FTS5 Shared Memory + Agent Constitution [P1] [AOS], ★7 — Adaptive Loop Halting (Early Exit on High Confidence) [P1] [MYT + HRM], TOP 6 — Highest-ROI Items (Validated by Opus Research Agent)

### Community 1093 - "build_connectors_router"
Cohesion: 0.38
Nodes (4): build_connectors_router(), list_connectors(), webhook_send(), _require_admin()

### Community 1094 - "Agent Transparency Report"
Cohesion: 0.29
Nodes (6): Agent Transparency Report, Guardrails and Limits, How to Verify This, Human Oversight Points, What Happens When an AI Works in This Repo?, What the AI Won't Do

### Community 1098 - "Skill: Managed Agents Dreams"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: Managed Agents Dreams, Testing, Usage

### Community 1099 - "Skill: Multi-Agent Coordinator"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: Multi-Agent Coordinator, Testing, Usage

### Community 1100 - "Skill: Obsidian Knowledge Graph"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: Obsidian Knowledge Graph, Testing, Usage

### Community 1101 - "Multi-Agent Research Coordinator Skill"
Cohesion: 0.29
Nodes (6): Default Plan Shape, Module: `agents/research_coordinator.py`, Multi-Agent Research Coordinator Skill, Quick-Note Issue: #238, Roles, What's Unique

### Community 1102 - "Skill: SuperClaude Slash Commands"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: SuperClaude Slash Commands, Testing, Usage

### Community 1103 - "Skill: SuperClaude Workflow Engine"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: SuperClaude Workflow Engine, Testing, Usage

### Community 1105 - "ADR-006: Strangler Fig migration with backward-compat shims"
Cohesion: 0.29
Nodes (6): ADR-006: Strangler Fig migration with backward-compat shims, Consequences, Context, Decision, Examples, Migration path

### Community 1107 - "claude-mem Plugin — Persistent Memory for All Sessions"
Cohesion: 0.29
Nodes (6): claude-mem Plugin — Persistent Memory for All Sessions, Enabling it elsewhere, How it's wired, Notes, Scope and limits, Why the source is pinned (`ref` + `sha`)

### Community 1108 - "orchestrator"
Cohesion: 0.33
Nodes (6): B.1 — Open the service's Environment tab, B.2 — Set these five keys on each service, B.3 — Sanity-check the secrets that must NOT regress, B.4 — Trigger TASK 5 keep-alive immediately, Option B — manual per-service editor, orchestrator()

### Community 1109 - "Platform Controls"
Cohesion: 0.29
Nodes (7): Across processes, API, Groups, How a value is resolved, Live vs restart-required, Platform Controls, What is deliberately **not** here

### Community 1111 - "Cloudflare = the real working app"
Cohesion: 0.29
Nodes (6): Backend (Render), Cloudflare dashboard settings to verify, Cloudflare = the real working app, How it works, Notes, Verify after deploy

### Community 1113 - "launch-claude-code.sh"
Cohesion: 0.43
Nodes (6): ANTHROPIC_API_KEY, ANTHROPIC_MODEL, log_error(), log_header(), log_success(), launch-claude-code.sh script

### Community 1115 - "PRD — README Marketing Refresh"
Cohesion: 0.29
Nodes (6): Backlog / Nice-to-Have, Files Touched, Original Problem Statement, PRD — README Marketing Refresh, User Decisions, What Was Done — 2026-04-27

### Community 1117 - "quickstart.sh"
Cohesion: 0.52
Nodes (6): die(), ensure_env(), ok(), say(), quickstart.sh script, warn()

### Community 1122 - "test_daily_2026_06_14.py"
Cohesion: 0.38
Nodes (3): _read(), test_ci_autofix_workflow_uses_sonnet_4_6(), test_no_retired_claude_4_model_ids_in_workflows_or_scripts()

### Community 1124 - "brain_providers"
Cohesion: 0.33
Nodes (3): brain_providers(), describe_disabled_reason(), state_is_durable()

### Community 1125 - "github_oauth_callback"
Cohesion: 0.40
Nodes (3): github_oauth_callback(), _error(), _oauth_popup_html()

### Community 1126 - "Command: /plan"
Cohesion: 0.33
Nodes (5): Command: /plan, References, Usage, What It Does, When to Use

### Community 1129 - "Skill: hybrid-reasoning (Hybrid AI)"
Cohesion: 0.33
Nodes (5): Branch, Purpose, Quick Start, Skill: hybrid-reasoning (Hybrid AI), Testing

### Community 1130 - "Pending Activities — Implementation Playbook"
Cohesion: 0.33
Nodes (5): Definition of done (per task), How to verify the whole thing end-to-end (local, no external infra), P2 — ECC harness & polish, Pending Activities — Implementation Playbook, Task 10 — ECC cross-harness adapter (currently PLANNED only)

### Community 1133 - "SECTION B — NVIDIA / Cloud Model Integration (Nemotron / NVD)"
Cohesion: 0.33
Nodes (6): B1 — Nemotron Reward Model for Agent Step Scoring [P0] [NVD], B2 — SteerLM / RLHF-Style Steering for Local Models [P1] [NVD], B3 — Synthetic Training Data Generation Pipeline [P1] [NVD], B4 — NeMo Guardrails Integration [P1] [NVD], B5 — NIM API Connection Pooling + Circuit Breaker [P1] [NVD], SECTION B — NVIDIA / Cloud Model Integration (Nemotron / NVD)

### Community 1136 - "SECTION D — Deployment & Infrastructure (CHM / NVD)"
Cohesion: 0.33
Nodes (6): D1 — Helm Chart for Kubernetes Deployment [P1] [CHM], D2 — Docker Compose Production Stack [P1] [CHM], D3 — OpenTelemetry Distributed Tracing [P1] [NVD / CHM], D4 — Horizontal Scaling with Redis State Backend [P2] [CHM / AOS], D5 — Model Auto-Management (Pull, Warm, Evict) [P2] [NVD], SECTION D — Deployment & Infrastructure (CHM / NVD)

### Community 1145 - "StatusPill.jsx"
Cohesion: 0.47
Nodes (5): C, STATUS_META, StatusPill(), TONE_BG(), TONE_BORDER()

### Community 1146 - "Event"
Cohesion: 0.33
Nodes (3): Event, publish(), subscribe()

### Community 1147 - "The Agent Roster"
Cohesion: 0.33
Nodes (6): 🔨 Implementer, ⚖️ Judge, 📋 Planner, 🔍 Reviewer, 🔭 Scout, The Agent Roster

### Community 1150 - "Music Cues: happy-beats-business-moves-vol-1-by-ende-dot-app"
Cohesion: 0.33
Nodes (5): Music Cues: happy-beats-business-moves-vol-1-by-ende-dot-app, Reveal Candidates, Strong Cues In Window, Use Policy, Useful Beat Grid

### Community 1151 - "Feature Support Matrix"
Cohesion: 0.40
Nodes (5): Admin API, Config Overrides, Feature Support Matrix, Gating Behavior, Maturity Tiers

### Community 1152 - "/fix-bug — Bug Fix Agent"
Cohesion: 0.33
Nodes (5): Escalation, /fix-bug — Bug Fix Agent, Process, Rules, Usage

### Community 1154 - "Skill: browserbase-fetch — Lightweight Web Fetch"
Cohesion: 0.33
Nodes (5): Checking the platform health, Python snippet, Setup, Skill: browserbase-fetch — Lightweight Web Fetch, When to use vs browser

### Community 1156 - "Twitter Insights — Issue #228"
Cohesion: 0.33
Nodes (5): Action Items, Key Observations, References, Summary, Twitter Insights — Issue #228

### Community 1157 - "Twitter Insights — Issue #231"
Cohesion: 0.33
Nodes (5): Action Items, Key Observations, References, Summary, Twitter Insights — Issue #231

### Community 1158 - "OpenAI Codex CLI — Local LLM Server Config"
Cohesion: 0.33
Nodes (5): Codex Config File (`~/.codex/config.yaml`), Notes, OpenAI Codex CLI — Local LLM Server Config, Recommended Models, Setup

### Community 1159 - "ADR-001: Adopt packages/ directory structure"
Cohesion: 0.33
Nodes (5): ADR-001: Adopt packages/ directory structure, Consequences, Context, Decision, Status

### Community 1160 - "ADR-002: Centralize configuration in packages/config/"
Cohesion: 0.33
Nodes (5): ADR-002: Centralize configuration in packages/config/, Consequences, Context, Decision, Status

### Community 1161 - "ADR-003: Provider abstraction with unified interface"
Cohesion: 0.33
Nodes (5): ADR-003: Provider abstraction with unified interface, Consequences, Context, Decision, Status

### Community 1162 - "ADR-004: Event bus for loosely coupled communication"
Cohesion: 0.33
Nodes (5): ADR-004: Event bus for loosely coupled communication, Consequences, Context, Decision, Status

### Community 1163 - "ADR-005: Merge Hermes into the main backend service"
Cohesion: 0.33
Nodes (5): ADR-005: Merge Hermes into the main backend service, Consequences, Context, Decision, Status

### Community 1165 - "Pre-Mortem Analysis: Agency Core autonomy story (Cloudflare deployment)"
Cohesion: 0.33
Nodes (5): Elephants, named, Pre-Mortem Analysis: Agency Core autonomy story (Cloudflare deployment), Risk Registry, Summary, What was already fixed during this pre-mortem

### Community 1166 - "Runtime & Onboarding Issues"
Cohesion: 0.33
Nodes (4): Onboarding endpoints crash with 500, Runtime endpoints return 500 errors (decisions, health, policy), Runtime & Onboarding Issues, Website scan returns "No systems detected" for JS-rendered sites

### Community 1173 - "gen_v4_screenshots.py"
Cohesion: 0.60
Nodes (4): build_screens(), page(), shot(), sidebar()

### Community 1177 - "setup-claude-code.sh script"
Cohesion: 0.60
Nodes (5): log_error(), log_info(), log_success(), print_header(), setup-claude-code.sh script

### Community 1185 - "Command: /resume"
Cohesion: 0.40
Nodes (4): Command: /resume, References, Usage, What It Does

### Community 1186 - "Command: /review"
Cohesion: 0.40
Nodes (4): Command: /review, References, Usage, What It Does

### Community 1190 - "SECTION E — Autonomy & Self-Healing (AOS / MYT / ECC)"
Cohesion: 0.40
Nodes (5): E1 — Cross-Harness Routing (ECC Pattern) [P1] [ECC], E2 — Self-Healing Agent Loop (Detect + Repair Own Failures) [P1] [AOS / MYT], E3 — Autonomous Monitoring with Trend Watcher [P2] [AOS], E4 — Nightly Self-Evaluation + Regression Tests [P2] [HRM / AOS], SECTION E — Autonomy & Self-Healing (AOS / MYT / ECC)

### Community 1203 - "Prompt Library Changelog"
Cohesion: 0.40
Nodes (4): Added, Format, Prompt Library Changelog, [Unreleased]

### Community 1204 - "test_rate_limiter_concurrency.py"
Cohesion: 0.60
Nodes (3): check_rate_limit(), test_rate_limiter_concurrency(), call_limit()

### Community 1209 - "test_agency_fix.py"
Cohesion: 0.09
Nodes (9): test_agency_fix_loop_declines_when_llm_returns_no_edits(), test_agency_fix_loop_fixes_broken_test_via_stub_llm(), test_apply_edits_rejects_destructive_overwrite(), test_apply_edits_rejects_doc_only_boilerplate(), test_apply_edits_rejects_secrets_shaped_file(), test_apply_edits_rejects_unparseable_python(), test_decline_cleanly_no_issue_returns_true(), test_decline_cleanly_no_token_returns_false() (+1 more)

### Community 1215 - "feature-implementer.md"
Cohesion: 0.40
Nodes (4): Before you edit, Prove it, Report back, While you edit

### Community 1216 - "/devops-check — DevOps Agent"
Cohesion: 0.40
Nodes (4): Deployment Checklist, /devops-check — DevOps Agent, Steps, When to use

### Community 1217 - "/docs-update — Documentation Agent"
Cohesion: 0.40
Nodes (4): /docs-update — Documentation Agent, Documentation Standards, Steps, When to use

### Community 1218 - "/qa-check — QA Agent"
Cohesion: 0.40
Nodes (4): /qa-check — QA Agent, Steps, What NOT to do, When to use

### Community 1219 - "/security-audit — Security Agent"
Cohesion: 0.40
Nodes (4): Escalation, /security-audit — Security Agent, Steps, When to use

### Community 1221 - "Skill: browserbase-search — Structured Web Search"
Cohesion: 0.40
Nodes (4): Best practice: search → fetch → browse, Python snippet, Setup, Skill: browserbase-search — Structured Web Search

### Community 1222 - "Issue #230 — DUPLICATE"
Cohesion: 0.40
Nodes (4): Actions Taken, Issue #230 — DUPLICATE, References, Resolution

### Community 1223 - "llm/config.py"
Cohesion: 0.03
Nodes (44): AgentPolicy, _apply_env_overrides(), _apply_key_env(), _build(), _coerce(), config_dir(), _env_key_names(), expand_env() (+36 more)

### Community 1225 - "Docker (local or any container host)"
Cohesion: 0.40
Nodes (4): Build, Docker (local or any container host), Provider configuration (recommended for cloud), Run (minimal)

### Community 1226 - "test_a_failed_filing_releases_the_cooldown_so_the_next_recurrence_retries"
Cohesion: 0.40
Nodes (3): test_a_failed_filing_releases_the_cooldown_so_the_next_recurrence_retries(), _no_evidence(), test_a_successful_filing_is_counted_and_holds_its_cooldown()

### Community 1227 - "Documentation map"
Cohesion: 0.40
Nodes (5): Architecture and operations, Documentation map, Repo hygiene, Screenshots and README sync, Start here

### Community 1229 - "inspect-agent-runtime.sh"
Cohesion: 0.60
Nodes (3): fail(), inspect-agent-runtime.sh script, usage()

### Community 1230 - "Proof"
Cohesion: 0.40
Nodes (5): Honesty notes (read before quoting the numbers), Proof, Reproduce any audit yourself, The self-audit (yes, we publish our own imperfect score), What's coming next in this directory

### Community 1232 - "build_llama_cpp.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), W(), Warn()

### Community 1233 - "download_glm52_weights.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), Warn(), W()

### Community 1234 - "download_glm52_weights.sh script"
Cohesion: 0.70
Nodes (4): download_glm52_weights.sh script, fail(), ok(), warn()

### Community 1235 - "setup_colibri.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), Warn(), W()

### Community 1236 - "setup_colibri.sh script"
Cohesion: 0.70
Nodes (4): setup_colibri.sh script, fail(), ok(), warn()

### Community 1237 - "status_colibri_server.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), W(), Warn()

### Community 1244 - "SECTION F — Developer Experience (CBF / ECC)"
Cohesion: 0.50
Nodes (4): F1 — Codebuff-Style Precise Diff Application [P0] [CBF], F3 — Local Dev Dashboard with Live Metrics [P2] [CBF / CHM], F4 — SDK / Client Library Generation [P2] [CBF], SECTION F — Developer Experience (CBF / ECC)

### Community 1254 - "test_probe_report.py"
Cohesion: 0.15
Nodes (6): _fake_run(), report(), TestBuildBody, TestFindTrackingIssue, TestIsRetired, communicate()

### Community 1256 - "SECTION H — Vision / Multimodal (NVD)"
Cohesion: 0.67
Nodes (3): H1 — Vision Input Support for Multimodal Models [P2] [NVD], H2 — Audio Input / Whisper Transcription [P3] [NVD], SECTION H — Vision / Multimodal (NVD)

### Community 1269 - "codebase-explorer.md"
Cohesion: 0.50
Nodes (3): Hard constraints, Method, Output

### Community 1270 - "docs-auditor.md"
Cohesion: 0.50
Nodes (3): Hard constraints, Output, What to check

### Community 1271 - "risk-reviewer.md"
Cohesion: 0.50
Nodes (3): Output, Rules of evidence, What you weigh

### Community 1272 - "verification-reviewer.md"
Cohesion: 0.50
Nodes (3): Output, Rules of evidence, What you evaluate

### Community 1273 - "aider_config.sh"
Cohesion: 0.50
Nodes (3): OPENAI_API_BASE, OPENAI_API_KEY, aider_config.sh script

### Community 1274 - "Credential Rotation Runbook"
Cohesion: 0.50
Nodes (3): Credential Rotation Runbook, Guardrails already in place, What to rotate (owner action, ~10 minutes)

### Community 1275 - "Runbook: `make doctor`"
Cohesion: 0.50
Nodes (3): Roadmap, Runbook: `make doctor`, What it checks and why

### Community 1276 - "render"
Cohesion: 0.50
Nodes (3): RENDER_API_KEY, docker, render

### Community 1279 - "stop_colibri_server.ps1"
Cohesion: 0.83
Nodes (3): Fail(), Ok(), W()

### Community 1300 - "github"
Cohesion: 0.50
Nodes (3): github, enabled, silent

### Community 1308 - "enforcement.py"
Cohesion: 0.06
Nodes (21): Changed, Changed, 4. Security review, Deliberate design decisions, stated for review, Findings addressed during implementation, Verification status — stated precisely, BudgetExceeded, classify() (+13 more)

## Knowledge Gaps
- **3563 isolated node(s):** `duplicate.sh script`, `heartbeat.sh script`, `redact_secrets.sh script`, `docker`, `RENDER_API_KEY` (+3558 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 15319 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **368 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `AgentRunner` connect `AgentRunner` to `workflow_orchestrator.py`, `typing`, `Agency Core — Progress & Resume Log`, `TaskSpec`, `test_agent_chat_integration.py`, `CompanyGraphStore`, `proxy.py`, `LocalWorkspace`, `Competitor Analysis — Autonomous AI Agency`, `failover_chat_completion`, `RepoConnection`, `Changed`, `pytest`, `TokenBudget`, `Agency`, `emit_chat_observation`, `FreeBuff — free-NVIDIA coding agent`, `FreeBuffAgent`, `E2BSandboxSession`, `Added`, `backend/server.py`, `AgentSessionStore`, `SECTION A — Agent Efficiency (Hermes / AOS / MYT)`, `WorkspaceTools`, `build_governance_router`, `MultiAgentSwarm`, `test_governance_api.py`, `test_verification_strategies.py`, `ContextPruner`, `PolicyEngine`, `Fixed`, `build_tool_prompt`, `Added`, `BrainFailoverExhausted`, `Universality: case-coverage matrix`, `TestInternalAgentAdapterProviderChain`, `ContextManager`, `test_backend_server_features.py`, `test_e2b_data_flow.py`, `_resolve_push_token`, `AdaptiveHalter`, `test_agent_free_brain.py`, `test_kill_switch_and_agent_budget.py`, `NIMConnectionPool`, `WorkflowOrchestrator`, `TestAgentLoopMCPIntegration`, `unsafe_target_reason`, `TestRunnerWorkspace`, `test_tool_call_aliases.py`, `test_fabric_patterns.py`, `Section-by-Section Acceptance Criteria`, `test_agent_tool_governance.py`, `CEODispatcher`, `test_free_model_speed.py`, `StuckDetector`, `Fixed`, `UserMemoryStore`, `test_empirical_verify.py`, `.session_id`, `AgentPlan`, `GitHubTools`, `ReactScratchpad`, `test_autonomous_agency_e2e.py`, `AgentJobRequest`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Why does `_fixture()` connect `_fixture` to `TaskSpec`, `test_provider_router.py`, `test_llm_router_queue_cache.py`, `TestRuntimeControl`, `OrchestratorCheckpointStore`, `Specialist`, `is_destructive_overwrite`, `failover_chat_completion`, `test_freebuff_bot.py`, `test_unit8_model_catalog.py`, `Changed`, `types.py`, `Agency`, `test_brain_failover.py`, `SelfHealingAgent`, `TaskStatus`, `Added`, `allow_paid`, `test_e2b_sandbox.py`, `test_ping.py`, `test_platform_controls.py`, `test_gateway_hygiene.py`, `PolicyEngine`, `TestSourceGate`, `test_mcp_protocol_version.py`, `_mock_provider_records`, `control_overrides.py`, `_FakeCollection`, `Added`, `TestNormalizeResponseFormat`, `llm/router.py`, `make_client`, `UsageEvent`, `AgentRunner`, `_register_code_graph_tools`, `test_llm_router_e2e.py`, `_ts_to_float`, `test_kill_switch_and_agent_budget.py`, `_test_e2e_telegram_approval`, `test_tick_endpoint_throttle.py`, `test_model_router.py`, `orchestrator`, `TestModelRegistryUpdates`, `test_web_reach.py`, `TaskWorkflowService`, `test_startup_warmup.py`, `_redact_for_notification`, `ChatHistoryStore`, `resolve_e2b_config`, `TestClient`, `test_knowledge_sync.py`, `CompanyAgencyService`, `FakeRunner`, `test_shared_state.py`, `test_trend_watcher.py`, `services/background.py`, `AgentSwarm`, `PreflightReport`, `test_task_service_failed_comment.py`, `traffic_director.py`, `services/seo_audit.py`, `KeyStore`, `test_autonomous_agency_e2e.py`, `_step`, `test_context_rulebook.py`, `CompanyGraphStore`, `parse_event_stream`, `ArtifactStore`, `WorkflowBuildRequest`, `SecurityScanner`, `model_router.py`, `e2e/test_browser.py`, `TestWorkflowWiring`, `TestChatHistoryStore`, `_clean_phases`, `PrimeAgentAdapter`, `sys`, `test_trend_scoping.py`, `SamAgent`, `test_brain_patch_service_token.py`, `test_llm_router_disabled.py`, `test_new_features_e2e.py`, `reset_cache`, `test_sam_livekit.py`, `test_spec_store.py`, `TestAuthAndTaskCreation`, `OperationalIncidentTracker`, `test_agile_api.py`, `FeatureMaturity`, `UserRole`, `test_daily_automation_2026_09_30.py`, `TestSelfHealingInfrastructureClassification`, `_process_task_callback`, `test_video_transcript.py`, `analyze_page`, `test_e2b_data_flow.py`, `OllamaCircuitBreaker`, `test_hermes_in_process.py`, `test_features_api.py`, `test_telegram_webhook.py`, `test_task_clarification.py`, `TestNormalizeAnthropicOutputFormat`, `test_langfuse_agency_wide.py`, `TestSchedulerStore`, `transport`, `test_sam_orchestrator.py`, `test_task_run_lease.py`, `yaml`, `test_probe_report.py`, `_start_ceo_agency`, `TrendWatcher`, `clear_cooldowns`, `test_agent_tool_governance.py`, `filed`, `checkpoint_agent_state`, `Path`, `test_agents.py`, `test_control_plane_api.py`, `test_daily_automation_2026_09_29.py`, `tasks/models.py`, `TestEstimateTokensForMessages`, `ImprovementLoop`, `test_persistent_memory.py`, `test_ceo_router.py`, `LocalBrainStore`, `TestAuthAndTaskOwnership`, `SeoFixRequest`, `test_autonomy_triage.py`, `pytest`, `set_task_store`, `test_ephemeral_reaper.py`, `test_sam_voice.py`, `router_factory`, `WorkflowRun`, `Task`, `OutputFilter`, `TestHarnessAdapter`, `process_note`, `test_app_settings.py`, `test_provider_failover_integration.py`, `test_provider_enable_disable.py`, `_resolve_user_github_token`, `test_kimi_bridge_server.py`, `TaskPriority`, `_resolve_push_token`, `test_agent_free_brain.py`, `467 Brutal Audit — File-by-File Status`, `test_scheduler_hydration_bounded.py`, `_build_execution_request`, `Fixed`, `test_skill_registry_boot_refresh.py`, `LessonStore`, `test_harness_spec.py`, `TestChatFallbackAndApproval`, `DetectedSystem`, `test_rate_limiter.py`, `_ensure_tasks_source_id_unique_index`, `test_state_file_merge_drivers.py`, `test_phase5_doctor.py`, `test_procedural_memory.py`, `NotificationDispatcher`, `test_executive_advisory_api.py`, `TestCountTokensEndpoint`, `test_gateway_sanitizer.py`, `TestTheWorkflowIsSafeAndReadOnly`, `test_dependabot_sweep_workflow.py`, `heal_signature`, `TestMongoGate`, `ContextPruner`, `test_doctor_coding_brain.py`, `TestProviderRouter`, `test_regression.py`, `test_workflow_shell_vars_are_declared.py`, `SQLiteStore`, `unittest_mock`, `test_service_token.py`, `captured`, `test_dashboard_cache.py`, `RoutingDecision`, `TestSwarmRoleRouting`, `test_openclaw_endpoints.py`, `test_process_quick_note_workflow.py`, `test_daily_automation_2026_10_03.py`, `test_tool_call_aliases.py`, `test_key_pool.py`, `_get`, `test_cost_attribution.py`, `test_webui_provider_priority.py`, `_client`, `test_v4_api.py`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **Why does `ProviderRouter` connect `ProviderRouter` to `typing`, `test_provider_router.py`, `system_instruction`, `test_bedrock_provider.py`, `AnthropicProvider`, `backend/server.py`, `test_all_providers_discovery.py`, `TestRouterIntegration`, `test_anthropic_refusal_fallback.py`, `TestLegacyRouterCacheTTL`, `failover_client.py`, `test_provider_failover_integration.py`, `Added`, `is_anthropic_base_url`, `test_anthropic_router.py`, `webui/router.py`, `test_kill_switch_and_agent_budget.py`, `RoutingDecision`, `ai/__init__.py`, `resolve_active_brain`, `test_colibri_provider.py`, `test_bedrock_live.py`, `TestAnthropicPayloadStructuredOutput`, `Current Sprint Tasks`, `implement_agent.py`, `clear_cooldowns`, `_list_configured_provider_records`, `TrafficDirector`, `.session_id`?**
  _High betweenness centrality (0.017) - this node is a cross-community bridge._
- **What connects `duplicate.sh script`, `heartbeat.sh script`, `redact_secrets.sh script` to the rest of the system?**
  _3563 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `workflow_orchestrator.py` be split into smaller, more focused modules?**
  _Cohesion score 0.07207792207792207 - nodes in this community are weakly interconnected._
- **Should `typing` be split into smaller, more focused modules?**
  _Cohesion score 0.011643287684253047 - nodes in this community are weakly interconnected._
- **Should `TaskSpec` be split into smaller, more focused modules?**
  _Cohesion score 0.010170490483583462 - nodes in this community are weakly interconnected._