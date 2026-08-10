# Graph Report - autonomous-ai-agency  (2026-08-10)

## Corpus Check
- 1424 files · ~2,043,114 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 28364 nodes · 57905 edges · 1215 communities (1087 shown, 128 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 6298 edges (avg confidence: 0.54)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d76de9bd`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- ExecutionRequest
- AgentScheduler
- backend/server.py
- LLMRequest
- AgentRunner
- ai/router.py
- Template
- test_runtimes.py
- company_api.py
- Task
- get_company_graph_store
- llm/router.py
- direct_chat.py
- KnowledgeGraph
- _fixture
- BrainWatchdog
- TaskSpec
- test_operational_incidents.py
- DashboardLayout.js
- test_llm_router_strategies.py
- api.js
- test_governance_sandbox.py
- test_llm_router_queue_cache.py
- BrainConfig
- KeyPool
- MongoDBStore
- test_governance_enforcement.py
- tasks/service.py
- services/background.py
- SQLiteStore
- test_e2b_sandbox.py
- test_model_router.py
- _scanner
- SelfHealingAgent
- MultiAgentSwarm
- AgileSprint
- RenderFinding
- get_registry
- test_llm_router_resilience.py
- settings.py
- AgentProfile
- test_direct_chat_async.py
- test_unit8_model_catalog.py
- render_ops.py
- FeatureMatrix
- failover_chat_completion
- test_autonomous_agency_e2e.py
- webui/router.py
- TestPayloadNormalisation
- PrimeAgentAdapter
- MCPClient
- resolve_component_model
- test_loop_registry.py
- ._db
- E2BAdapter
- get_runtime_manager
- test_knowledge_sync.py
- telegram_bot.py
- test_sam_livekit.py
- App.js
- CompanyGraphService
- Initiative
- test_repowise_intelligence.py
- SecretRecord
- setup/api.py
- detector.py
- ModelRouter
- redact_connection_url
- WorkspaceTools
- WorkspaceManager
- RenderOpsMonitor
- get_task_store
- services/seo_audit.py
- test_runtime_governance.py
- RewardScorer
- HybridSystem
- ResearchTask
- TokenBudget
- brain_config.py
- TestClient
- test_user_research_skill.py
- AgentSwarm
- FetchResult
- test_repo_connection.py
- audit
- sync/service.py
- ProceduralMemoryStore
- TaskWorkflowService
- AnthropicProvider
- failover_client.py
- TaskDispatcher
- clear_cooldowns
- resolve_e2b_config
- test_orchestrator_merge_decision.py
- TestClient
- issue_new_api_key
- test_agent_tool_governance.py
- Surface
- ControlPlanePage.js
- diagnostics.py
- AdaptiveHalter
- ToolRegistry
- FinancialMetrics
- tasks/api.py
- LogWatcher
- Agent
- CEODispatcher
- AgileManager
- test_ceo_micromanager.py
- run_tests
- cache.py
- test_brain_config_store.py
- ai_runner.py
- test_sqlite_store.py
- ReactScratchpad
- .execute
- ProvidersScreen.jsx
- SeoFixer
- TaskIn
- probe_model_liveness
- Command
- ChatPage.js
- test_context_rulebook.py
- ArtifactStore
- kimi_bridge_provider_config
- InferenceCache
- CheckpointStore
- test_governance_api.py
- useSafeData
- Usage
- test_ceo_supervision.py
- WorkflowEngine
- LLMRouter
- ImprovementLoop
- test_trend_scoping.py
- get_feature_matrix
- DigestSummary
- test_issue_intake.py
- WorkspaceManager
- test_startup_warmup.py
- _StubProvider
- config.py
- ChatHistoryStore
- api.ts
- control_overrides.py
- GoalRecord
- WebReach
- claim
- test_render_mcp.py
- .run
- V5App.jsx
- test_response_cache.py
- workspaces.py
- NvidiaProvider
- test_slop_gate.py
- AutonomyTracker
- activation_api.py
- ToolAnnotations
- test_quick_note.py
- Workspace
- MetricsRegistry
- test_integration_c4_c5_c6_d3.py
- test_e2b_task_wiring.py
- .get_workspace
- OnboardingScreen.jsx
- Settings
- OllamaCircuitBreaker
- SetupChecker
- PromptCacheManager
- cost_insights.py
- TaskDetailPanel.jsx
- TrendWatcher
- test_audit.py
- CEOSupervisor
- test_mcp_governance.py
- [Unreleased]
- [Unreleased]
- test_provider_enable_disable.py
- ApprovalStore
- TestChatHistoryStore
- test_features_api.py
- test_video_transcript.py
- Part A — CodeRabbit review fixes for this PR (do first, small)
- FilterResult
- _get_provider_policy
- Persistent Memory System
- test_colibri_provider.py
- RuntimesPage.js
- facade.py
- emit_chat_observation
- anthropic_compat.py
- test_issue_triage.py
- compare_runtimes.py
- test_portfolio_intake.py
- test_schedule_growth_invariants.py
- v4_api.py
- PatternConsolidation
- distributed.py
- OrchestratorQueue
- test_telegram_freebuff.py
- test_schedule_backlog_drain.py
- _run
- test_workspace_isolation.py
- TestAgentJobRequest
- AgentsScreen.jsx
- KnowledgeScreen.jsx
- getBackendUrl
- TestEstimateTokensForMessages
- SchedulerStore
- TestClient
- test_crispy_workflow.py
- GitHubTools
- timedelta
- validate_outbound_url
- test_daily_2026_06_04.py
- PolicyEngine
- ServiceDaemon
- ContextWindowManager
- NIMConnectionPool
- ContextPruner
- IssueCategory
- ScheduledJob
- _Collection
- StreamingDeltaReconstructor
- DecisionsStoreTests
- test_trend_watcher.py
- workflow/api.py
- PlaybookLibrary
- test_verification_strategies.py
- test_backend_server_features.py
- test_platform_controls.py
- REWRITE_PLAN.md — Phased Migration Strategy
- test_background_services.py
- test_all_providers_discovery.py
- WorkflowBuildRequest
- test_persistent_memory.py
- SecurityScanner
- Continual Harness (`agent/harness_spec.py`)
- test_freebuff_bot.py
- test_anthropic_router.py
- test_llm_router_e2e.py
- seo_api.py
- agent_runtime.py
- ENGINEERING_STANDARDS.md — Coding, Security & Testing Standards
- DashboardScreen.jsx
- context_rules.py
- TestStreamableHTTPTransport
- local_controller.py
- test_live_server.py
- test_control_plane_api.py
- test_telegram_mutating_commands.py
- test_context.py
- ContextManager
- SparkProvider
- MCPUnavailableError
- openclaw_gateway.py
- TestBrainFailoverModelUpdates
- traffic_director.py
- chat_handlers.py
- test_rate_limiter.py
- Screens
- provider_max_rpm
- test_kimi_bridge_server.py
- test_brain_failover.py
- test_microagents.py
- Security Analysis — local-llm-server
- brain_failover.py
- Langfuse Observability Guide
- v3_models.py
- DockerAgentAdapter
- test_failover_silent_exhaustion.py
- Feature Guide
- admin_gui.py
- TestDiagCommand
- run_regression
- agency.py
- SpecEntry
- StuckDetector
- High-Agency Frontend Skill
- Quick-Note GitHub Issues Processing - Session Summary
- v3_auth.py
- RateLimitTracker
- scheduler.py
- TestRecordUsageAndStats
- test_purge_backlog.py
- test_autonomy_gate.py
- tests/test_browser.py
- proxy.py
- test_terminal.py
- test_dashboard_cache.py
- SeoCheckDefinition
- mcp_dispatch
- _resolve_brain_provider
- switch_brain.py
- test_portfolio_intelligence.py
- test_rag_context.py
- _P
- AppShell.jsx
- test_version_consistency.py
- test_ceo_router.py
- Configuration Reference
- test_pr923_fixes.py
- SteeringInjector
- test_claude_setup_audit.py
- test_internal_agent_did_work.py
- agents/api.py
- WebsiteScanner
- Python Dependencies (`requirements.txt`)
- Technical Debt Register — local-llm-server
- NotificationDispatcher
- test_backend_runtime_bootstrap.py
- CircuitState
- CostAttributor
- test_crispy_burn_in.py
- test_llm_router_tpm.py
- test_schedule_persistence.py
- TestSchedulerStore
- test_skill_registry_boot_refresh.py
- SprintMetrics
- Deploy: FreeBuff Telegram bot (24×7)
- Claude Code + Qwen Local Setup
- Docker Agent Runtimes Setup
- OperationalIncident
- generate_context.py
- control_registry.py
- ._connect
- resolve_active_brain
- isolated_telegram_config
- test_scheduler_hydration_bounded.py
- webui/frontend/package.json
- LocalWorkspace
- Performance Analysis — local-llm-server
- LLM Router — troubleshooting
- test_unit5_ui_provider_surface.py
- keepalive.py
- monitor_lib.py
- analyze_page
- TrainingSample
- APIClient
- test_v3_auth.py
- TestWorkflow
- HarnessEnrichment
- .snapshot
- test_sam_voice.py
- ScheduleStore
- _valid_login_state
- dependencies
- reset_store
- Session Handoff — 2026-06-15
- TASK 4 — End-to-end approval-gate test
- Any
- DailyDigestAggregatorTests
- ClaudeCodeAdapter
- AgentMessageBus
- TemporalContextGraph
- test_telegram_approval_e2e.py
- _get
- test_daily_automation_2026_08_03.py
- TestClassifyPlainText
- test_service_token.py
- CompanyAgencyService
- Findings
- Local AI Stack with Docker
- Traffic Distribution Across Providers
- Implementation Prompt: Rich TaskBoard + Agile Sprint Integration
- Telegram Bot Setup
- SchedulesPage.js
- video_transcript.py
- PrioritizedTask
- TestRouterIntegration
- CollectionLike
- seo_report_pdf.py
- test_agency_fix.py
- test_output_filter.py
- test_workspace_security.py
- refine
- get_skill_bindings
- test_phase6_workflow.py
- model_discovery.py
- Agent Governance Guide
- The fifteen strategies
- fmtErr
- ServiceManager
- _Cursor
- test_all_features.py
- TestModelRegistryUpdates
- test_monitor_lib.py
- Path
- test_mostly_failed_steps.py
- test_v4_api.py
- classify_direct_chat_intent
- ._connect
- test_scanner_live.py
- CoworkSession
- Harness
- PriorityTaskQueue
- _process_task_callback
- BrainFailoverManager
- test_voice.py
- _resolve_user_github_token
- V3 API Migration Plan — LLM Relay Platform
- PortfolioScreen.jsx
- allow_paid
- TestSelfHealingInfrastructureClassification
- system_instruction
- scripts/doctor.py
- test_local_controller.py
- run_trend_analysis
- MemoryCategory
- test_permissions.py
- PersistentMemoryStore
- AGENTS.md — Source of Truth for All AI Agents
- Skill: modularity-review
- Design Audit
- Findings
- Skill: modularity-review
- crispy_client.py
- 4. Troubleshooting
- Docker AI Governance Audit — Final Report
- 1. Capability-by-capability
- 4. Threats
- Dynamic Model Routing
- test_unit7_catalog_propagation.py
- infra_cost.py
- output_filter.py
- compilerOptions
- TestCheckKwargs
- test_self_heal.py
- HarnessRegistry
- scrub
- test_langfuse_agency_wide.py
- test_tasks_cache_ttl_env.py
- test_voice_pipeline.py
- TestUpdateTask
- MemoryKernel
- rag_context.py
- _extract_tech_relevance
- agile_api.py
- Skill: fabric-patterns
- Analysis & Synthesis Instructions
- Production Readiness Assessment — local-llm-server
- SyncAgent
- TestNormalizeResponseFormat
- Skill: fabric-patterns
- db/__init__.py
- Admin Dashboard Guide
- Implementation Plan
- test_doctor_service_token_check.py
- ProviderConsole.jsx
- McpCard.jsx
- build_workflow.py
- SyntheticDataPipeline
- test_chat_mode_regressions.py
- test_brain_patch_service_token.py
- agent/watchdog.py
- AuditLog
- test_fabric_patterns.py
- Any
- validate_session_id
- ErrorInterceptorMiddleware
- github_tools.py
- test_lessons.py
- KeyStore
- Comprehensive Skill Index (By Category)
- Agent Skill: Principal UI/UX Architect & Motion Choreographer (Awwwards-Tier)
- Component Map
- TrafficDirector
- Agent State — colibri GLM-5.2 deployment (resumable)
- Architecture Overview — local-llm-server
- Pending Activities — Implementation Playbook
- Platform Guide — the full tour
- The rules
- Part A — Health Report
- ControlsScreen.jsx
- apply_review.py
- Specialist
- Delegation Plan (agent-ready work packages)
- agency_fix.py
- sync_readme_gallery.py
- GuardrailEngine
- LocalLLMSetup
- test_company_api.py
- TestStopSlopChecker
- test_phase4_runtime_resilience.py
- handle_workflow_ide_chat
- asyncio
- TestHelpers
- ._fetch_flat_skill_file
- test_task_service_failed_comment.py
- Task
- SKILL: Industrial Brutalism & Tactical Telemetry UI
- Skill: data-quality-audit
- What "Slop" Looks Like
- test_admin_local_brain_router.py
- local_brain_router.py
- Section-by-Section Acceptance Criteria
- TestMCPServer
- SQLiteStore
- TaskStore
- agent_readiness_audit.py
- test_ci.sh
- ProviderCircuit
- test_activation_api.py
- test_health_endpoints.py
- test_keepalive.py
- test_openclaw_endpoints.py
- TestRoutes
- OperationalIncidentTracker
- cowork_session.py
- hermes_prompt.py
- MemoryMiddleware
- test_ai_insights.py
- analyze_quantitative
- AITellIssue
- Skill: repowise-intelligence
- ARCHITECTURE.md — Target Architecture
- admin_digest_router.py
- Skill: repowise-intelligence
- The 10-Step Workflow
- Contributing to local-llm-server
- CEO Micro-Management
- 467 Brutal Audit — File-by-File Status
- Migration Notes
- Any
- Runbook — Apply the Fast Free NVIDIA Brain to Render (TASK 2)
- .start_onboarding
- implement_agent.py
- AgentSessionStore
- fabric_cli.py
- sync_ngrok.py
- test_north_mini_code.py
- GuardResult
- test_telegram_auto_approve.py
- ManagedAgentDreams
- test_autonomy_status.py
- .update_intelligence
- test_dockerfile_ships_root_modules.py
- test_frontend_deployment_guards.py
- test_glm52_brain.py
- test_local_brain_state.py
- test_phase5_doctor.py
- TestBrainFailoverBackoff
- test_telegram_diag_endpoint.py
- test_google_provider_models.py
- _keyword_search
- sam_livekit_worker.py
- CollaborationContext
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
- test_daily_2026_07_24.py
- _push_down_where
- get_store
- _build_request
- clear_wizard_state_cache
- e2e/test_browser.py
- ._sprint
- _RedisBackend
- test_dockerfile_ships_config_dir.py
- _run
- test_agent_free_brain.py
- CLAUDE.md — Master Architect Operating Manual
- StopSlopChecker
- Process
- Skill: lr-schedule-advisor
- Instructions
- Instructions
- Process
- Checks Performed
- Skill: training-stability-monitor
- monitor_colibri.py
- Skill: branch-cleanup
- Skill: perplexity — Web Research via Perplexity API
- Instructions
- Instructions
- Quick-Note Issues Processing Summary
- Implementation Plan — DB-persisted, UI-switchable Brain (no redeploy)
- Backend changes
- Runbook: Auto-Resume After Cooldown / Interruption
- SEO / GEO / AIO Audit Engine
- devDependencies
- overrides
- _parse_reset_epoch
- test_brain_priority_scanner.py
- test_onboarding_provisioning.py
- cmd_autonomy
- test_critical_flows.py
- ApprovalGate
- OutputFilter
- test_openclaw_gateway.py
- TestExtendedThinkingRouting
- router/health.py
- open_phase_report
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
- TestKillSwitchDurability
- Instructions
- Skill: graphify — Knowledge Graph Token Optimization
- Skill: platform-setup — Autonomous Agency Bootstrap
- Device compatibility and model picks
- Autonomy Uplift — Living Roadmap & Detailed Implementation Specs
- OpenClaw — iOS Control of the Agency (Single-Service Free-Tier Deploy)
- rules
- Summary
- Agent Transparency Report
- update_provider_policy
- .publish
- _InMemoryBackend
- TestModelCostTableUpdates
- TestDecisionsBotLinks
- test_deploy_trigger_covers_image.py
- test_task_source_id_race.py
- cleanup_stale_jobs
- PortfolioManager
- test_skill_executors_live.py
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
- test_bootstrap_source_id_index.py
- Workspace Isolation Architecture
- admin.py
- Skill: agent-browser — Real Chrome Browser Automation
- Instructions
- Instructions
- Skill: dev-browser — Browser Automation via Sandboxed JS
- Instructions
- Agent Orchestration Design
- Universality: case-coverage matrix
- Any
- Quantization Internals
- Implementation — DB-persisted, UI-switchable Brain (PR #824 follow-up)
- 2. Pending ⬜ — detailed implementation specs
- 467 Public Site Truth Spec
- Render MCP — autonomous platform debugging and environment monitoring
- GovernanceScreen.jsx
- TestParsing
- extract_refusal
- test_p0_roadmap_a4_a5_b2.py
- check_container_posture.py
- Kimi Web-Bridge Service
- test_regression.py
- test_agile_api.py
- test_app_settings.py
- ContributorState
- test_skill_registry.py
- TestAnthropicPayloadStructuredOutput
- test_task_clarification.py
- validate_job_id
- EvalHarness
- DecisionsStore
- _extractive_compress
- RegistrySkill
- key_store.py
- AdminDigestRouterAuthTests
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
- 14. Standing Instructions — Universal Agent Discipline
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
- FakeCollection
- run_proxy.sh
- configuration-reference.md
- setup_ngrok.py
- ._run_job
- test_empirical_verify.py
- .get_overview
- fetch_url.py
- _TFIDFIndex
- Instructions
- Protocol: Premium Utilitarian Minimalism UI Architect
- The 5-Step Wrap-Up Ritual
- security_fix_agent.py
- Agent: Reviewer (Verifier)
- Skill: Agentic Agile
- Skill: browserbase-ui-test — Adversarial UI Testing
- Skill: financial-analyst (Agentic CFO)
- Graphiti Temporal Context Skill
- Skill: seo-audit-report
- ADR-008: LLMRouter — the single multi-provider routing gateway
- Core Pillars
- 467 Golden Path — Locked Implementation Order
- LLM Router — configuration guide
- LLM Router — provider guide
- FeatureMaturity
- RepowiseIntelligence
- test_provider_state_durability.py
- build_tech_db.py
- main
- run_bot
- Dream
- _resolve_push_token
- test_doctor_coding_brain.py
- TestZeroAttemptDiagnostics
- TestSessionMemory
- test_quick_note_engine.py
- SamConversation
- ._make_run
- BenchmarkReport
- _extract_workflow_relevance
- Agent Readiness Report
- Skill: changelog-enforcer
- Skill: learn-rule
- Instructions
- test_provider_router.py
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
- Troubleshooting
- frontend/package.json
- AgentStatusPanel.tsx
- AgentStatusPanel.jsx
- ToolCallViewer.tsx
- test_bedrock_provider.py
- enrich_quick_note_issues.py
- _status_snapshot
- test_backend_requirements_cover_runtime_imports.py
- test_changelog_parity_guard.py
- ._prune
- TestWindowsAuth
- TestDisabledReasonRendering
- test_scanner_deps_parity.py
- stt.py
- test_log_monitor_storm_guard.py
- navigation_metrics.py
- _score_turns
- TrajectoryStep
- ._get_last_commit
- has_permission
- quality_checker.py
- Skill: docs-sync
- ._scan_github_repo
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
- TestRequireAdmin
- TOP 6 — Highest-ROI Items (Validated by Opus Research Agent)
- SECTION A — Agent Efficiency (Hermes / AOS / MYT)
- SECTION C — Direct Chat Improvements (CBF / HRM)
- Runbook — Instance Activation
- Prime Agent Runtime
- PULL_REQUEST_TEMPLATE.md
- get_livekit_config
- capture_screens.py
- Prompt Library
- CLAUDE.md — router/
- test_tasks_awaiting_approval_api.py
- crispy_burn_in.py
- run_patched_colibri.py
- SessionMemory
- local_brain_provider_config
- test_compose_and_coordinate_api.py
- SeoAuditRequest
- test_local_brain_router_smoke.py
- test_ping.py
- test_provider_models_db_outage.py
- test_runtimes_health_endpoint.py
- TestMongoGate
- 4. Current Architecture (As-Is)
- test_serve_spa_prefixes.py
- test_task_store_fails_loud_in_production.py
- dry_clone_repo
- TOOLS.md — Available Tools for AI Agents
- TestNormalizeToolChoice
- SIA
- Full-Output Enforcement
- summarise.sh
- updater.py
- ModelRegistry
- verify_token
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
- _FakePersistence
- Cloudflare = the real working app
- CI Troubleshooting Runbook
- 6. Agent Architecture
- production
- report_to_markdown
- get_workflow_orchestrator
- launch-claude-code.sh
- PRD — README Marketing Refresh
- ._check_permissions
- check_changelog_parity.py
- e2e_smoke.py
- Security Policy
- task_runner.py
- Page
- test_daily_2026_06_14.py
- test_event_log.py
- .team_summary
- CerebrasProvider
- cost_tracker.py
- TestGithubTokenSQLiteRegression
- _start_ceo_agency
- 10. CI/CD Standards
- TestTechSkillMap
- TestActiveStrategy
- _resolve_default_executor_model
- TestParseToolCalls
- .memory_count
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
- 1. What This Repo Does
- Pre-Mortem Analysis: Agency Core autonomy story (Cloudflare deployment)
- SECTION B — NVIDIA / Cloud Model Integration (Nemotron / NVD)
- SECTION D — Deployment & Infrastructure (CHM / NVD)
- _StubManager
- RelayShowcasePage.js
- 8. Authentication Architecture
- .execute
- test_agent_api.py
- apply_phase1_changes.py
- _replace
- check_doc_images.py
- gen_screenshots.py
- gen_v4_screenshots.py
- setup-claude-code.sh script
- TestRuntimes
- Report
- test_generate_context_standing_instructions.py
- _auth_headers
- TestGithubSignalHardening
- harness.py
- _rrf
- _get_current_user
- heartbeat.sh
- TestCatalog
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
- test_harness_spec.py
- SECTION E — Autonomy & Self-Healing (AOS / MYT / ECC)
- SECTION F — Developer Experience (CBF / ECC)
- Runtime troubleshooting
- task.py
- FakeScheduleCollection
- 10. Testing Constitution
- knowledgeGraphTab.test.js
- loginFlowNoTimeout.test.js
- test_company_stale_id_recovery.test.js
- worker_no_cache.test.js
- scripts/agile_ceremonies.py
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
- client
- TestAuth
- TestMobileNavigation
- test_v5_screens_smoke.py
- test_agent_runtime_wrapper.py
- TestWorkflowSkillMap
- worker/index.js
- 5. AI Provider Architecture
- recovery.py
- _env_int
- TestPaidPolicyDurability
- ._run_git_command
- Agent Autonomy Roadmap
- Setup
- _FakeCollection
- start_in_process
- aider_config.sh
- providers.yaml
- _known_tool_names
- What's New
- 11. Rewrite Strategy
- Credential Rotation Runbook
- Runbook: `make doctor`
- 3. Repository Constitution
- 7. Scheduler Architecture
- Model and Response Issues
- ToolCallViewer.jsx
- _decompose_into_subtasks
- render
- scripts
- Any
- CircuitBreakerOpenError
- BackgroundServices
- operational_incidents.py
- TestSupportMatrixDocsSync
- TestFeaturesAPI
- stop_colibri_server.ps1
- .consolidate
- start_server.sh
- check_services
- TestHealth
- TestProviders
- nvidia_live_test.py
- test_activity_feed.py
- test_local_brain_router_actor_regression.py
- test_no_exception_detail_leaks.py
- .replay
- github
- test_skills_route_order.py
- asyncio
- set_onboarding_service
- _FakeMongoStore
- The full agent capability roster
- .execute
- _merge_changed_files
- graphify-refresh
- [Unreleased]
- Session Learnings
- .test_create_provider
- frontend/.eslintrc.json
- _normalize_dockerfile
- .get_phase_index
- Who is this for?
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
- Proof
- _open_dashboard
- test_the_reserve_is_bounded_when_read_from_the_environment
- ._execute_via_cli
- maintenance_section.md
- duplicate.sh
- hello_claude.py
- backend/__init__.py
- test_pytest_many_tests
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
- gather_render_evidence
- Issue → Context → Draft PR automation
- setup_autostart_macos.sh
- start.sh
- stop-proxy.sh script
- stop_server.sh script
- The 24x7 agency — your agents never go idle
- test_docker_build_large
- Privacy, security, and cost
- record_usage
- .test_cleans_removes_double_spaces
- .test_detects_multiple_throat_clearing
- .test_detects_wh_starters
- .test_cleans_emphasis_crutches
- disabled
- _resolve_default_executor_model
- .execute
- .best_for
- voice/__init__.py
- probe_live_providers.py
- sam
- test_feature_stores_are_wired_on_demand_not_eagerly
- main
- _get_current_user_thunk
- Configuration reference
- .get_system_by_type
- .write_mcp_config
- test_mint_token_rejects_missing_args
- _StopLifespan
- .get_company_graph
- .primary_evidence
- .repo_owner
- .repo_name
- .__init__
- .test_models_can_be_imported
- test_curl_large_response
- test_git_log_large
- test_git_status_small
- test_ls_small
- test_session_reused
- test_sam_persona_is_concise
- test_get_sam_status

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

## Communities (1215 total, 128 thin omitted)

### Community 0 - "ExecutionRequest"
Cohesion: 0.02
Nodes (173): get_orchestrator_checkpoint_store(), _NoopDB, OrchestratorCheckpointStore, services/orchestrator_checkpoint.py — Durable step-level checkpointing Issue…, Fallback in-memory store when no DB is available., Persist orchestrator runs so they survive restarts., BoundContext, ClassifyOutput (+165 more)

### Community 1 - "AgentScheduler"
Cohesion: 0.03
Nodes (216): Agency, CEO-coordinated multi-agent agency for continuous codebase management. The CEO…, AgentJobRequest, AgentJobSnapshot, BaseModel, Complete point-in-time view of a job, safe to serialise as API response., Convenience: the canonical text response, whether success or failure., Validated input for creating a new agent job. Passed from the API handler into… (+208 more)

### Community 2 - "backend/server.py"
Cohesion: 0.01
Nodes (487): get_agency(), _gh_token(), set_agency(), get_harness_adapter(), backend/ceo_router.py — observability and manual control for the CEO. Surfaces…, Reject non-admin callers for routes that spend provider budget. Delegates to…, _require_admin(), _is_admin() (+479 more)

### Community 3 - "LLMRequest"
Cohesion: 0.03
Nodes (142): ProviderConfig, One configured endpoint. ``kind`` selects the adapter: ``openai`` (any OpenAI-…, packages/llm/providers/anthropic.py — Anthropic Messages API adapter. Anthropic…, classify_error(), LLMProvider, OpenAICompatible, ABC, Any (+134 more)

### Community 4 - "AgentRunner"
Cohesion: 0.02
Nodes (152): AgentRunner, _check_extra_kwargs(), _enforce_signature(), _note_phase_end(), _note_phase_start(), _nvidia_api_key(), Any, Path (+144 more)

### Community 5 - "ai/router.py"
Cohesion: 0.05
Nodes (51): _acquire_provider_probe(), _dead_model_key(), _exponential_backoff_cooldown(), _get_director(), is_commercial_provider(), _mark_model_dead(), _normalized_provider_type(), _notify_watchdog() (+43 more)

### Community 6 - "Template"
Cohesion: 0.26
Nodes (5): Any, Path, Write template files into *target_dir*. Skips existing files unless…, ScaffoldResult, Template

### Community 7 - "test_runtimes.py"
Cohesion: 0.03
Nodes (69): AiderAdapter, Any, Adapter for Aider — TIER 3 specialized git-aware code editor., GooseAdapter, Any, Adapter for Goose — TIER 2 general-purpose local runtime., HermesAdapter, Adapter for Hermes Agent — FIRST CLASS autonomous runtime. (+61 more)

### Community 8 - "company_api.py"
Cohesion: 0.06
Nodes (127): AccountLifecycleResponse, _DoctorCheck, _DoctorReport, OnboardingAnswersRequest, OnboardingProgressResponse, OnboardingQuestionsRequest, BaseModel, Company Graph API Router Provides all endpoints for managing companies, their… (+119 more)

### Community 9 - "Task"
Cohesion: 0.05
Nodes (57): Full task/issue document., Update the updated_at timestamp., Task, Best-effort Telegram heads-up that a task is parked awaiting approval. Inline…, Tests for task follow-up / rerun with conversation carry-over. Before this,…, The runtime reads context['conversation']; prior comments must be carried as…, test_build_spec_exposes_conversation_for_runtime(), test_follow_up_empty_message_rejected() (+49 more)

### Community 10 - "get_company_graph_store"
Cohesion: 0.03
Nodes (125): ephemeral_ttl_hours(), Async read of the ephemeral TTL (hours) straight from the DB., account_lifecycle(), auto_recommend_skills(), cancel_onboarding(), create_company(), delete_company_endpoint(), generate_onboarding_questions() (+117 more)

### Community 11 - "llm/router.py"
Cohesion: 0.04
Nodes (81): _load(), main(), int, openai_body_from_response(), Any, packages/llm/compat.py — backwards-compatible bridges to the legacy call paths.…, Whether the compat bridges should delegate to ``LLMRouter``. Reads the flag on…, Translate an OpenAI-shaped chat payload into an ``LLMRequest``. Unknown keys… (+73 more)

### Community 12 - "direct_chat.py"
Cohesion: 0.04
Nodes (97): PreflightIssue, Any, BaseModel, doctor.py — Agent-side doctor diagnostics: environment, provider, and workspace…, Translate technical preflight issues into a conversational assistant reply., translate_error_to_conversational(), agent/job_manager.py — Async agent job lifecycle manager. Manages agent jobs…, ResumeRequest (+89 more)

### Community 13 - "KnowledgeGraph"
Cohesion: 0.02
Nodes (95): Status of a user story within a sprint., StoryStatus, HarnessAdapter, HarnessSpec, Any, agents/harness_adapter.py — ECC Cross-Harness Adapter Normalises API…, Adapt harness-native requests to the local-llm-server internal format. Each…, Detect which harness sent this request from headers. Check order: explicit… (+87 more)

### Community 14 - "_fixture"
Cohesion: 0.01
Nodes (110): app_client(), _clear_discovered_models(), _clear_response_cache(), client(), _isolate_brain_data_layer(), _isolate_operator_provider_state(), non_admin_client(), MonkeyPatch (+102 more)

### Community 15 - "BrainWatchdog"
Cohesion: 0.06
Nodes (33): BrainWatchdog, get_watchdog(), _is_provider_actually_available(), Any, services/brain_watchdog.py — Brain health watchdog. Monitors the active brain…, Fail over to the next available provider., Persist the new provider in the brain config store (fire-and-forget). Uses the…, Send a Telegram notification about the failover. (+25 more)

### Community 16 - "TaskSpec"
Cohesion: 0.03
Nodes (77): kimi_bridge_runtime_config(), Return Kimi bridge config for external runtimes (Hermes, Goose, Aider). Returns…, TaskResult, TaskSpec, runtimes/adapters/aider.py — Aider adapter (TIER 3 — specialized). Aider…, Run aider non-interactively via `--message` flag., runtimes/adapters/claude_code.py — Claude Code CLI adapter (FIRST CLASS).…, runtimes/adapters/docker_agent.py — Docker-based agent runtime adapter. Spawns… (+69 more)

### Community 17 - "test_operational_incidents.py"
Cohesion: 0.06
Nodes (37): normalise(), Collapse the volatile parts of *message* so recurrences group together. ``Task…, Stable dedup key over the *normalised* message., Find agent phases that started but never finished.…, signature_for(), summarise_phases(), Recurring operational failures must diagnose and file themselves. The gap these…, The reported scenario, end to end: four real timeouts, one incident. (+29 more)

### Community 18 - "DashboardLayout.js"
Cohesion: 0.07
Nodes (33): deleteModel(), getActivity(), getCostAttribution(), getDecisionLog(), getSavings(), getStats(), getUsage(), listModels() (+25 more)

### Community 19 - "test_llm_router_strategies.py"
Cohesion: 0.04
Nodes (99): count, HealthConfig, Strategy selection and degradation behaviour., Circuit breaker + health tracking thresholds., RoutingConfig, HealthTracker, _Outcome, ProviderHealth (+91 more)

### Community 20 - "api.js"
Cohesion: 0.02
Nodes (44): approveGovernanceRequest(), approveTaskCheckpoint(), approveTaskExecution(), autoRecommendCompanySkills(), createMcpServer(), createSprint(), delegateSeoFindings(), deleteCompany() (+36 more)

### Community 21 - "test_governance_sandbox.py"
Cohesion: 0.04
Nodes (72): build_docker_run_argv(), detect_backend(), DockerBackend, E2BBackend, get_sandbox_manager(), load_profiles(), LocalBackend, Any (+64 more)

### Community 22 - "test_llm_router_queue_cache.py"
Cohesion: 0.03
Nodes (82): build_summariser(), chunk_document(), ContextManager, estimate_tokens(), FitResult, message_tokens(), prune(), Any (+74 more)

### Community 23 - "BrainConfig"
Cohesion: 0.05
Nodes (39): BrainConfig, BrainConfigStore, provider_base_url(), BaseModel, Build a ``BrainConfig`` from a Mongo doc, dropping Mongo's ``_id``., Resolve the Ollama base URL the UI controls — DB value wins over env.…, Return the OpenAI-compatible base URL for *provider* (env- and UI-aware)., The agency's active brain — provider + per-role models. Stored as a single… (+31 more)

### Community 24 - "KeyPool"
Cohesion: 0.04
Nodes (44): provider_api_keys(), Every API key configured for *provider*, primary first. Reads ``base_env`` then…, api_keys_for(), _digest(), KeyPool, _KeyState, _PoolState, Per-provider API key rotation — the one lever that adds capacity. Every other… (+36 more)

### Community 25 - "MongoDBStore"
Cohesion: 0.03
Nodes (59): CompanyGraphSnapshot, A point-in-time snapshot of a Company Graph for history and rollback., MongoDBStore, Any, Company, ObjectId, Prepare a Pydantic model for SQLite storage., Prepare a SQLite row for Pydantic model. (+51 more)

### Community 26 - "test_governance_enforcement.py"
Cohesion: 0.06
Nodes (60): BudgetTracker, classify(), GovernanceGate, _host_of(), Extract a hostname from a URL, or return a bare host unchanged., Holds live session budgets, bounded so it cannot leak. Sessions end without…, The one seam through which governed actions pass., Return the ``(surface, action)`` a tool call really represents. The *action* is… (+52 more)

### Community 27 - "tasks/service.py"
Cohesion: 0.05
Nodes (59): Helpers that turn scheduler and playbook activity into real tasks., Background dispatcher for task execution., tasks — Task/issue management system. Provides a lightweight task/issue tracker…, ApprovalCheckpoint, _coerce_ts(), Any, Enum, field_validator (+51 more)

### Community 28 - "services/background.py"
Cohesion: 0.04
Nodes (82): get_improvement_loop(), _dispatch_async(), _ErrorCaptureHandler, get_log_monitor(), LogMonitor, _note_recurrence(), Any, LogRecord (+74 more)

### Community 29 - "SQLiteStore"
Cohesion: 0.03
Nodes (48): Delete a company and all its associated data., Delete a company and all associated data from SQLite., Count total companies in SQLite., Reconstruct a Website from a SQLite row, preferring the full JSON blob (which…, Create a new website in SQLite. The full model is stored in ``data`` so scan…, Get a website by ID from SQLite., Update a website in SQLite. When ``company_id`` is omitted the existing company…, Count total companies in the store. (+40 more)

### Community 30 - "test_e2b_sandbox.py"
Cohesion: 0.06
Nodes (52): _inject_token(), Best-effort scrub of ``token`` from ``text``., Return ``(authed_url, clean_url)`` for a GitHub repo URL., _scrub_token(), _clean_e2b_env(), fake_sandbox(), _FakeCommandResult, _FakeCommands (+44 more)

### Community 31 - "test_model_router.py"
Cohesion: 0.05
Nodes (78): classify_task(), _extract_recent_text(), Any, Task classification from request context. Classifies an incoming request into a…, Concatenate plain text from the last *last_n* messages., Return the most likely task category for this request. Args: messages: OpenAI-…, Reset the singleton and clear the cached model map (test helper)., reset_router() (+70 more)

### Community 32 - "_scanner"
Cohesion: 0.06
Nodes (25): _is_blocked_host(), Cheap (no-DNS) SSRF check for headless-browser subrequests. A rendered page's…, Tests for the scanner's headless-render fallback (JS-rendered / bot-protected…, The scan flow must invoke the render fallback when static detection is empty…, BuiltWith-style off-site identification: a CNAME chain that points at a known…, A scan must never hang past its wall-clock budget — a slow/blocked domain has…, Last-resort fallback that asks builtwith.com what it already knows about a…, Replace curl_cffi's AsyncSession.get with a canned response. (+17 more)

### Community 33 - "SelfHealingAgent"
Cohesion: 0.04
Nodes (63): heal_signature(), HealingEvent, HealState, _now(), Any, Enum, str, agent/self_healing.py — Self-Healing Agent (closed-loop, Autonomy Charter G2)… (+55 more)

### Community 34 - "MultiAgentSwarm"
Cohesion: 0.07
Nodes (61): AgentConfig, build_agent_specs(), build_swarm(), build_task_specs(), coordinate_v2(), CoordinateRequestV2, CoordinateResponse, Any (+53 more)

### Community 35 - "AgileSprint"
Cohesion: 0.04
Nodes (43): _bullets(), generate_sprint_retro(), plan_next_sprint(), Agentic Agile — autonomous ceremonies (standup, retro, sprint planning). Where…, Render a :class:`Retrospective` as a markdown section., Derive retro notes for ``sprint`` from its current metrics. Records…, The result of allocating portfolio capacity into a new sprint., Render the sprint plan as markdown. (+35 more)

### Community 36 - "RenderFinding"
Cohesion: 0.05
Nodes (52): get_mcp_client(), Return the module-level MCPClient. Reads MCP_SERVER_BASE_URL at call time (not…, _internal_configured(), list_specs(), MCPServerSpec, _not_dialable(), _playwright_configured(), _probe_http() (+44 more)

### Community 37 - "get_registry"
Cohesion: 0.06
Nodes (32): best_model_for(), best_vision_model(), get_registry(), ModelCapability, Model capability registry. Defines the known local models, their strengths, and…, # NOTE: suspended under US export-control directive as of 2026-06-12., Return model registry, extended with ROUTER_EXTRA_MODELS env entries.…, Return the name of the best model for a given task category. Falls back to… (+24 more)

### Community 38 - "test_llm_router_resilience.py"
Cohesion: 0.03
Nodes (66): Backoff policy for retryable failures., RetryConfig, _digest(), get_ring(), KeyRing, KeyState, packages/llm/keys.py — multi-key rotation with per-key health. A provider may…, Per-provider round-robin key selection with cooldowns. (+58 more)

### Community 39 - "settings.py"
Cohesion: 0.05
Nodes (48): ChatResponse, Cerebras provider adapter — free, fast LLM (qwen-3-coder-480b)., Groq provider adapter — free, fast LLM (deepseek-r1-distill-llama-70b)., NVIDIA NIM provider adapter — wraps the existing provider_router logic. This is…, Ollama provider adapter — local LLM inference., packages.ai — provider abstraction, model registry, and failover manager., ProviderManager, Any (+40 more)

### Community 40 - "AgentProfile"
Cohesion: 0.07
Nodes (26): agents/__init__.py — CRISPY multi-agent coding system., AgentProfile, _catalog_defaults(), _catalog_provider(), _get_defaults(), load_all_profiles(), make_architect_profile(), make_coder_profile() (+18 more)

### Community 41 - "test_direct_chat_async.py"
Cohesion: 0.22
Nodes (14): runner(), _fake_user(), _FakeChatResult, _FakeResponse, asyncio, Path, test_agent_mode_github_preflight_missing_token(), test_agent_mode_queues_async_job() (+6 more)

### Community 42 - "test_unit8_model_catalog.py"
Cohesion: 0.03
Nodes (84): _brain_provider_status(), Return per-provider metadata for the GET endpoint. Iterates every provider in…, all_provider_ids(), provider_key_present(), Return every provider id recognised by the brain config system. Iterates the…, True when the env var for *provider*'s key is set (or it's Ollama)., CatalogActiveBrain, CatalogMirror (+76 more)

### Community 43 - "render_ops.py"
Cohesion: 0.06
Nodes (31): _file_issue(), _latest_metric_value(), _note_recurrence(), _parse_timestamp(), Any, datetime, services/render_ops.py — autonomous Render debugging + environment monitoring.…, Parse an RFC3339 timestamp from Render, tolerating a trailing ``Z``. (+23 more)

### Community 44 - "FeatureMatrix"
Cohesion: 0.04
Nodes (29): FeatureEntry, FeatureMatrix, Any, BaseModel, One entry in the support matrix., Central support matrix — single source of truth. Loads the canonical feature…, Load canonical features and apply per-feature then bulk env overrides., Apply a config override string like 'stable', 'beta', 'disabled', 'enabled',… (+21 more)

### Community 45 - "failover_chat_completion"
Cohesion: 0.07
Nodes (79): failover_chat_completion(), Run one chat completion across the brain-failover chain. Tries each healthy…, _free_tier(), _hit_ids(), _many_providers(), _mixed_registry(), _openai_body(), _paid() (+71 more)

### Community 46 - "test_autonomous_agency_e2e.py"
Cohesion: 0.04
Nodes (84): AgentRole, str, Enum, Agentic Agile — Sprint management with velocity tracking and burndown. Issue:…, Lifecycle status of a sprint., Qualitative health signal derived from sprint metrics., SprintHealth, SprintStatus (+76 more)

### Community 47 - "webui/router.py"
Cohesion: 0.06
Nodes (60): _bootstrap(), Path, ProviderManager, WorkspaceManager, tests/test_webui_provider_priority.py — Priority + reorder + brain-policy…, The /policy/brain endpoint must return the resolved brain + the paid policy…, The /providers/role-tags endpoint surfaces brain/sub/fallback roles consistent…, Reset the brain_config + brain_policy singletons before each test. V2.0 Phase 2… (+52 more)

### Community 48 - "TestPayloadNormalisation"
Cohesion: 0.06
Nodes (28): _as_list(), _coerce_payload(), Any, packages/integrations/render_mcp.py — Render platform access over MCP. The…, Return tool output as Python data. MCP tool results arrive either as…, Normalise a tool payload into a list of dicts. Upstream tools variously return…, Unwrap a nested envelope such as ``{"service": {...}}`` when present., Run the MCP handshake once per client instance. Streamable-HTTP servers create… (+20 more)

### Community 49 - "PrimeAgentAdapter"
Cohesion: 0.03
Nodes (54): _accumulate_usage(), _assistant_messages(), _child_env(), _iter_events(), _kill_and_reap(), _message_text(), parse_event_stream(), ParsedRun (+46 more)

### Community 50 - "MCPClient"
Cohesion: 0.05
Nodes (30): MCPClient, Any, RuntimeError, Thin async MCP client with open/close circuit breaker. Thread-safe only within…, Full URL of the JSON-RPC endpoint this client posts to., Build the request headers shared by ``_rpc`` and ``notify``. ``Accept`` lists…, Propagate the calling agent's identity across the process boundary. The MCP…, Attach the agent identity whose actions this client executes. (+22 more)

### Community 51 - "resolve_component_model"
Cohesion: 0.06
Nodes (41): Resolve the model id for a component's role on a provider. Parameters…, Convenience: resolve all four role models for a component. Returns a dict with…, resolve_component_model(), resolve_component_role_models(), tests/test_unit6_resolve_component_model.py — UNIT 6 regression tests. Verifies…, When the DB cache is fresh AND provider matches the active primary, the DB-…, When the DB primary differs from the requested provider, the catalog preset for…, When `provider` is None, the DB primary's saved model wins. (+33 more)

### Community 52 - "test_loop_registry.py"
Cohesion: 0.05
Nodes (64): audit_drift(), _cmd_audit(), DriftReport, _grade(), load_registry(), load_registry_sync(), loop_readiness(), LoopRegistry (+56 more)

### Community 53 - "._db"
Cohesion: 0.24
Nodes (5): Any, Restore in-flight runs at startup. Called during backend bootstrap. Returns a…, Persist a WorkflowRun snapshot., Load a persisted run snapshot., Return checkpoints for runs that were not in a terminal state.

### Community 54 - "E2BAdapter"
Cohesion: 0.06
Nodes (42): E2BAdapter, Any, TaskResult, TaskSpec, Declare ``E2B_API_KEY`` as a required env dependency. The base ``preflight``…, Execute a task inside a fresh E2B sandbox. Flow: 1. Open an…, Run ``pytest`` inside the sandbox. Returns ``(output, passed)``.…, Runtime adapter that executes tasks inside an E2B sandbox. Activation:… (+34 more)

### Community 55 - "get_runtime_manager"
Cohesion: 0.05
Nodes (74): _enrich_runtimes(), get_decision_log(), get_policy(), get_runtime(), list_runtimes(), _load_rich_policy(), PolicyUpdateBody, Any (+66 more)

### Community 56 - "test_knowledge_sync.py"
Cohesion: 0.08
Nodes (46): _api_key(), _auth_headers(), _build_digest_markdown(), create_wiki_page(), fetch_and_store(), get_knowledge_sync(), KnowledgeSync, _now_iso() (+38 more)

### Community 57 - "telegram_bot.py"
Cohesion: 0.08
Nodes (50): Return a Markdown-v1-safe preview string under ``max_chars``. Used by the…, sanitize_paste_for_preview(), _admin_headers(), _answer_callback(), _api_headers(), _check_rate_limit(), cmd_control(), cmd_cost() (+42 more)

### Community 58 - "test_sam_livekit.py"
Cohesion: 0.08
Nodes (16): auth_headers(), livekit_env(), no_livekit_env(), tests/test_sam_livekit.py — SAM realtime voice (LiveKit) integration. Covers: -…, Auth headers for the seeded admin user (same pattern as test_agile_api)., The worker module must import cleanly even when livekit-agents is absent., SamAgent.build_context (used by worker tools) must return a dict., Configure a fake LiveKit deployment via env vars. (+8 more)

### Community 59 - "App.js"
Cohesion: 0.05
Nodes (37): completeSetup(), createSecret(), detectHardwareForSetup(), detectModelsForSetup(), getDefaultBackendUrl(), getMe(), getPublicPath(), getSetupState() (+29 more)

### Community 60 - "CompanyGraphService"
Cohesion: 0.04
Nodes (36): BusinessCategory, CompanyGraphService, Company, SpecialistFamily, SystemType, Workflow, Get a company by ID. Args: company_id: Company ID Returns: Company instance or…, Update a company. Args: company_id: Company ID **kwargs: Fields to update… (+28 more)

### Community 61 - "Initiative"
Cohesion: 0.06
Nodes (45): generate_backlog_retro(), generate_standup(), Derive a retrospective from the task tracker when no sprint is active. DONE /…, Build a :class:`StandupReport` from ``.claude/state/active-tasks.md``. Reads…, Initiative, _bug_scores(), _clean(), _default_repo() (+37 more)

### Community 62 - "test_repowise_intelligence.py"
Cohesion: 0.11
Nodes (18): Test that search_codebase returns a string., Test that get_decision_flownodes returns a string., Test that update_intelligence creates the expected intelligence files., Test that get_overview returns a dictionary., Test that get_context returns a string., Test that get_risk returns a dictionary., Test that get_why returns a string., Test that the RepowiseIntelligence class initializes correctly. (+10 more)

### Community 63 - "SecretRecord"
Cohesion: 0.06
Nodes (68): Permission, Enum, str, rbac.py — Role-Based Access Control. Three-tier user model: - admin: Full…, UserRole, _can_read(), _can_write(), create_secret() (+60 more)

### Community 64 - "setup/api.py"
Cohesion: 0.08
Nodes (59): is_user_onboarding_allowed(), Return True if this user may run the onboarding wizard. Resolution order: 1. If…, complete_wizard(), _delete_wizard_state(), detect_configured_providers(), detect_hardware_for_wizard(), detect_models_for_wizard(), _detect_ollama_models() (+51 more)

### Community 65 - "detector.py"
Cohesion: 0.07
Nodes (46): batch_compatibility(), check_model_compatibility(), _detect_amd_gpus(), _detect_apple_silicon_gpu(), _detect_cpu(), detect_hardware(), _detect_intel_arc_gpu(), _detect_nvidia_gpus() (+38 more)

### Community 66 - "ModelRouter"
Cohesion: 0.05
Nodes (32): Dynamic model router package. Public API:: from router import get_router,…, _build_builtin_model_map(), _default_model(), _default_reasoning_model(), _get_model_map(), ModelRouter, _nvidia_key_present(), Any (+24 more)

### Community 67 - "redact_connection_url"
Cohesion: 0.17
Nodes (7): packages/security/redact.py — strip secrets out of strings before they reach a…, Strip embedded credentials from a connection URI before logging it. Covers both…, redact_connection_url(), Regression test: production leaked a live MongoDB password in plaintext.…, Integration coverage: the actual log lines this module emits must never carry…, TestLoggingCallSitesRedactCredentials, TestRedactConnectionUrl

### Community 68 - "WorkspaceTools"
Cohesion: 0.05
Nodes (37): repowise.py — RepowiseIntelligence: context packing and dependency analysis., Path, tools.py — WorkspaceTools: read/write/search and diff application (risky…, Return a previously saved memory value, or an empty string if absent., Persist a key/value pair to the user's profile store., Return the first *lines* lines of a file. Just-in-time retrieval: the executor…, Return a lightweight index of files with line counts and sizes. This is the…, Delegate to RepowiseIntelligence for a natural-language codebase question. (+29 more)

### Community 69 - "WorkspaceManager"
Cohesion: 0.06
Nodes (43): _get_workspace_lock(), get_workspace_manager(), _hash_component(), _iso_now(), _iso_offset_hours(), _load_workspace(), _parse_iso(), BaseModel (+35 more)

### Community 70 - "RenderOpsMonitor"
Cohesion: 0.05
Nodes (37): BaseModel, Response shape of ``GET /api/render/ops/status``. Declared here rather than in…, RenderOpsStatus, One deploy, normalised from whatever shape the tool returned., Typed facade over the Render MCP server's tools. Every method returns plain…, True when there is both an API key and an endpoint to reach., Return the most recent deploy, or ``None`` when there are none., RenderDeploy (+29 more)

### Community 71 - "get_task_store"
Cohesion: 0.04
Nodes (59): packages/ai/self_heal.py — automatic brain self-healing. When the active brain…, Reset the singleton (for tests)., reset_failover_manager(), Hand the 'connect & verify the repo' work to the agency's own agents. The task…, _seed_connect_task(), _heal_brain_failover(), _heal_stuck_tasks(), _heal_task_duplicates() (+51 more)

### Community 72 - "services/seo_audit.py"
Cohesion: 0.07
Nodes (40): BaseModel, models/seo_audit.py - SEO / GEO / AIO Audit Contracts Typed Pydantic models for…, A single occurrence of a check firing on a specific URL., Snapshot of one crawled page with the on-page facts the checks used., Aggregated report row - Screaming Frog CSV compatible., Site-level facts discovered during the crawl., An agent-delegable remediation work package derived from the findings. Findings…, Lightweight listing entry for past audits. (+32 more)

### Community 73 - "test_runtime_governance.py"
Cohesion: 0.06
Nodes (58): Replace the process-wide engine. Tests only., reset_policy_engine(), _blocked_result(), _governance_check(), _governance_identity(), Any, TaskResult, TaskSpec (+50 more)

### Community 74 - "RewardScorer"
Cohesion: 0.08
Nodes (20): get_reward_scorer(), _nvidia_api_key(), BaseModel, Score a response against a prompt using the Nemotron reward model. Returns a…, Call the NVIDIA NIM reward endpoint and return the score. The Nemotron reward…, Parse the reward score from the model's JSON response., Return the module-level RewardScorer singleton., Result of a single reward model scoring operation. (+12 more)

### Community 75 - "HybridSystem"
Cohesion: 0.05
Nodes (29): ConfidenceLevel, DeterministicEngine, HybridSystem, LLMReasoner, Any, Enum, str, Hybrid AI — combine deterministic rule engines with LLM reasoning. Implements a… (+21 more)

### Community 76 - "ResearchTask"
Cohesion: 0.06
Nodes (44): AgentRole, Enum, str, Multi-Agent Research Coordinator — orchestrate a team of specialized research…, Run the task and return it (mutated) with status set., Coordinates a multi-agent research workflow. Workflow: 1. plan(question) → list…, Decompose a research question into a default DAG. Default plan: web → docs…, Round-robin pick within a role (least-loaded first). (+36 more)

### Community 77 - "TokenBudget"
Cohesion: 0.05
Nodes (31): BudgetUsage, Any, agent/token_budget.py — Per-Session Token Spend Caps Track token usage per…, Raise :class:`BudgetExceededError` if the session has exceeded its cap., Reset usage counters for *session_id* (cap is preserved)., Reset token counters for all sessions (caps preserved). Called at the start of…, Reset all budgets if the UTC calendar day has changed since last reset. Safe to…, Generate a token savings analytics report. Returns per-session statistics and… (+23 more)

### Community 78 - "brain_config.py"
Cohesion: 0.04
Nodes (79): _build_base_url_env_from_yaml(), _build_candidates_from_yaml(), _build_default_base_url_from_yaml(), _build_display_names_from_yaml(), _build_key_env_from_yaml(), _build_presets_from_yaml(), _build_tier_from_yaml(), get_provider_candidates() (+71 more)

### Community 79 - "TestClient"
Cohesion: 0.10
Nodes (29): bare_repo(), _call(), _data(), git_config_env(), _is_error(), mcp_workspace_root(), Path, skipif (+21 more)

### Community 80 - "test_user_research_skill.py"
Cohesion: 0.05
Nodes (47): analyze_qualitative(), auto_register(), _classify_sentiment(), _extract_keywords(), plan_research(), Any, BaseModel, field_validator (+39 more)

### Community 81 - "AgentSwarm"
Cohesion: 0.05
Nodes (49): AgentRole, AgentSwarm, Return the agent role responsible for *phase*., Return the AgentProfile for the agent driving *phase*., Run a pre-gate or report phase through the correct agent. Enforces permission…, Execute a slice via the Coder agent (write-permitted)., Review a slice via the Reviewer agent (different model from Coder). This is the…, Run verification commands via the Verifier agent. The Verifier is execution-… (+41 more)

### Community 82 - "FetchResult"
Cohesion: 0.06
Nodes (27): MockTransport, browser_backend_available(), BrowserFetcher, FetchResult, HttpxFetcher, looks_blocked(), make_fetcher(), AsyncBaseTransport (+19 more)

### Community 83 - "test_repo_connection.py"
Cohesion: 0.07
Nodes (49): DeliveryPolicy, How code lands on a repo's default branch (detected, GitHub-only for now). The…, A company's connection to a code repository (GitHub-only this pass). URL-only…, RepoConnection, attach_repo_connection(), build_repo_connection(), decide_merge(), detect_delivery_policy() (+41 more)

### Community 84 - "audit"
Cohesion: 0.06
Nodes (29): audit(), get_audit_log(), get_user_role(), is_admin(), is_power_user_or_above(), mask_dict(), mask_secret(), Any (+21 more)

### Community 85 - "sync/service.py"
Cohesion: 0.07
Nodes (47): FastAPI dependency: require Power User or Admin role. Raises 403 otherwise., require_power_user(), sync/ — Syncthing-style workspace synchronisation service., add_peer(), get_folder_index(), get_sync_file(), get_sync_service(), list_conflicts() (+39 more)

### Community 86 - "ProceduralMemoryStore"
Cohesion: 0.05
Nodes (26): get_procedural_memory(), _overlap_score(), ProceduralMemoryStore, ProceduralRecord, Any, agent/procedural_memory.py — Skill/Procedural Memory for the agent loop (★4).…, Store a successful step pattern and return its record id. Duplicate step…, Return up to *limit* stored patterns relevant to *query*. Relevance is scored… (+18 more)

### Community 87 - "TaskWorkflowService"
Cohesion: 0.05
Nodes (44): _is_brain_connection_error(), Any, BaseException, Task, TaskResult, TaskSpec, TaskStatus, Best-effort label of who will run this task once approved. Returns… (+36 more)

### Community 88 - "AnthropicProvider"
Cohesion: 0.12
Nodes (16): AnthropicProvider, Any, AsyncClient, Translate OpenAI-shaped messages into Anthropic's system/turn split., OpenAI carries a tool result as role="tool" with a tool_call_id; Anthropic…, OpenAI puts a tool call alongside the assistant's text; Anthropic needs…, Anthropic's extended-thinking constraints on ``budget_tokens``: at least 1024,…, Return a system-prompt instruction that enforces JSON output. Anthropic's… (+8 more)

### Community 89 - "failover_client.py"
Cohesion: 0.05
Nodes (55): _auto_disable(), _Budget, _describe_registry(), _disable_unless_key_serves_other_models(), _disabled_ids(), FailoverResult, _is_billing_refusal(), _is_ollama() (+47 more)

### Community 90 - "TaskDispatcher"
Cohesion: 0.08
Nodes (23): Re-queue BLOCKED tasks that have cooled down and are ready for retry., Polls for queued task work and executes it through the coordinator. Crash…, Re-queue tasks stranded by a prior crash or hard-kill., TaskDispatcher, _make_task(), asyncio, Task, TaskStatus (+15 more)

### Community 91 - "clear_cooldowns"
Cohesion: 0.08
Nodes (32): clear_cooldowns(), get_dead_models(), _is_model_dead(), is_provider_on_cooldown(), mark_provider_failed(), Snapshot of active dead-model entries {provider_id/model: expiry_ts}. Also…, Put provider_id on cooldown for *cooldown_seconds* (default:…, Return True if provider_id is currently on cooldown. (+24 more)

### Community 92 - "resolve_e2b_config"
Cohesion: 0.05
Nodes (57): Available iff config resolves AND the SDK is importable. Never raises — a…, e2b_status(), Return the E2B sandbox integration status for the ProvidersScreen badge. Does…, e2b_enabled(), E2BConfig, _env_falsy(), _env_truthy(), is_e2b_sdk_importable() (+49 more)

### Community 93 - "test_orchestrator_merge_decision.py"
Cohesion: 0.24
Nodes (13): _company(), _FakeStore, orch(), Company, Tests for the G5 RepoConnection/DeliveryPolicy wiring into the orchestrator…, test_record_consent_noop_for_non_gate_decision(), test_record_consent_noop_without_decision(), test_record_consent_persists_for_first_merge() (+5 more)

### Community 94 - "TestClient"
Cohesion: 0.08
Nodes (43): _auth_headers(), _build_agent_http_mock(), _exec(), _fake_request(), _mcp_tool_response(), _multi_step_plan(), _nim_post_factory(), _one_step_plan() (+35 more)

### Community 95 - "issue_new_api_key"
Cohesion: 0.23
Nodes (12): issue_new_api_key(), Generate a new plaintext API key, persist hash + metadata, return (plain_key,…, main(), main(), _make_store(), Security regression tests for key_store: hashing, constant-time compare, rate…, _reset_rate_state(), test_keys_stored_as_hash_not_plaintext() (+4 more)

### Community 96 - "test_agent_tool_governance.py"
Cohesion: 0.08
Nodes (44): _drive(), _enforce(), governance_on(), _observations(), Any, MonkeyPatch, Path, The executor loop must not have a side door around the governance gate.… (+36 more)

### Community 97 - "Surface"
Cohesion: 0.04
Nodes (62): build_governance_router(), Any, APIRouter, backend/governance_router.py — read and operate the governance layer. Mounted…, Reject non-admin callers. Mirrors the RBAC check used elsewhere in this backend…, _require_admin(), _load(), mcp_server/governance.py — governance adapter for the MCP HTTP surface. Closes… (+54 more)

### Community 98 - "ControlPlanePage.js"
Cohesion: 0.07
Nodes (40): createQuickNote(), createTask(), getDueSoonTasks(), getTask(), listAgents(), listQuickNotes(), listRuntimes(), listSchedules() (+32 more)

### Community 99 - "diagnostics.py"
Cohesion: 0.06
Nodes (48): _check_background_liveness(), _check_ci_parity(), _check_company_graph(), _check_disk(), _check_event_log_integrity(), _check_feature_matrix(), _check_github_readiness(), _check_ollama() (+40 more)

### Community 100 - "AdaptiveHalter"
Cohesion: 0.06
Nodes (23): AdaptiveHalter, Any, ★7 Adaptive Loop Halting — velocity-based agent run termination. Complements…, Return current halter state for logging / telemetry., Tracks step-level progress and signals when a run should halt early. The halter…, Ratio of applied steps to steps attempted (0.0–1.0). Returns 1.0 when no steps…, Record one step outcome; return a halt reason or None to continue. ``status``…, MCPToolResult (+15 more)

### Community 101 - "ToolRegistry"
Cohesion: 0.06
Nodes (33): get_tool_registry(), _infer_parameters_from_func(), Any, Path, Register a tool definition., Decorator to register a function as an agent tool. Usage::…, Remove a tool from the registry. Returns True if removed., Look up a tool by name. (+25 more)

### Community 102 - "FinancialMetrics"
Cohesion: 0.06
Nodes (46): BudgetOptimizer, CostLine, FinancialAgent, FinancialMetrics, Enum, str, Agentic CFO — autonomous financial analyst for AI infrastructure spend.…, Reallocate budget across cost lines to maximize total ROI under a fixed budget… (+38 more)

### Community 103 - "tasks/api.py"
Cohesion: 0.11
Nodes (62): ApprovalRequest, BackgroundTasks, add_comment(), approve_checkpoint(), approve_execution(), clarify_task(), create_task(), _current_user() (+54 more)

### Community 104 - "LogWatcher"
Cohesion: 0.05
Nodes (33): _auto_file_enabled(), ErrorFingerprint, LogEntry, LogWatcher, log_watcher.py — Automated log monitoring agent. Watches log files, detects…, A single error entry extracted from a log file., Generates stable fingerprints for error deduplication., Create a hash from error type, file, and normalized message pattern. (+25 more)

### Community 105 - "Agent"
Cohesion: 0.06
Nodes (24): Agent, Grab Multi-Agent Support — Agent and TeamCoordinator with capability matching.…, Release a task from an agent., List all currently available agents., List agents with a capability, ordered by load., Average load across all team members., Number of agents in the team., An agent with capabilities and workload tracking. (+16 more)

### Community 106 - "CEODispatcher"
Cohesion: 0.06
Nodes (49): CEODispatcher, CEOResult, _offload(), Any, Semaphore, Run a synchronous ledger call without blocking the event loop. ``CEOLedger`` is…, Build an agent.coordinator.TaskSpec from a CEO SpecialistTask., Aggregated output from a multi-specialist execution. (+41 more)

### Community 107 - "AgileManager"
Cohesion: 0.05
Nodes (21): AgileManager, Manages multiple agile sprints with velocity tracking., List all active sprints., Predict next sprint velocity from historical data., Number of managed sprints., InitiativeProgress, PortfolioMetrics, Enum (+13 more)

### Community 108 - "test_ceo_micromanager.py"
Cohesion: 0.04
Nodes (106): _complexity_rank(), services/ceo_dispatcher.py — Real CEO delegation layer. The CEO splits a…, Split the request into briefed, tier-assigned specialist sub-tasks. Returns the…, _should_fan_out(), build_subtask_brief(), _coerce_subtasks(), decompose(), _env_flag() (+98 more)

### Community 109 - "run_tests"
Cohesion: 0.07
Nodes (37): _login_api(), main(), _navigate_auth_callback(), _navigate_logged_out(), Page, Navigate directly to the AuthCallback page with query params., Social login buttons on the LoginPage., Verify the login page renders. (+29 more)

### Community 110 - "cache.py"
Cohesion: 0.08
Nodes (26): Test hook — clear all usage accounting., reset(), CacheManager, cosine_similarity(), _Entry, get_cache(), LRUCache, Any (+18 more)

### Community 111 - "test_brain_config_store.py"
Cohesion: 0.06
Nodes (40): Call-time resolver for an agent role model id. Delegates to…, _resolve_role_model(), default_brain_config(), Synchronous call-time resolver for an agent role model id. Precedence (highest…, Async variant — refreshes the cache if stale before resolving. Used by code…, Return the safe-default brain (used on first boot + store errors)., Return the recommended default brain based on which provider keys are present.…, recommended_brain_config() (+32 more)

### Community 112 - "ai_runner.py"
Cohesion: 0.07
Nodes (52): append_checkpoint(), _build_claude_command(), cmd_audit(), cmd_changelog_check(), cmd_logs(), cmd_manifest(), cmd_resume(), cmd_start() (+44 more)

### Community 113 - "test_sqlite_store.py"
Cohesion: 0.06
Nodes (56): asyncio, tests/test_sqlite_store.py — Unit tests for the SQLite storage adapter. These…, The exact query shape backend/server.py's provider "Set default" uses: clear…, Unfiltered count uses the SELECT COUNT(*) fast path and must match the number…, estimated_document_count mirrors an unfiltered count_documents., db['tasks'] must work like db.tasks (motor exposes both)., TaskStore(db=SQLiteStore) must not raise 'not subscriptable'. This is the exact…, B608 guard: all collections in _COLLECTIONS must still be instantiable. (+48 more)

### Community 114 - "ReactScratchpad"
Cohesion: 0.06
Nodes (22): Declarative configuration for a specialized sub-agent role. Each sub-agent gets…, SubAgentConfig, build_react_prompt(), parse_react_response(), Any, Parse a ReAct-format response into structured components. Intended caller:…, Structured scratchpad that accumulates across tool calls within a step. Each…, Record a reasoning step before taking action. (+14 more)

### Community 115 - ".execute"
Cohesion: 0.07
Nodes (19): _env_float(), Any, AsyncClient, Response, TaskResult, TaskSpec, Submit task to Hermes via its /tasks endpoint., Read a float env var, falling back to *default* on unset/garbage. (+11 more)

### Community 116 - "ProvidersScreen.jsx"
Cohesion: 0.06
Nodes (34): createProvider(), deleteProvider(), getBrainConfig(), getBrainProviders(), getLocalBrainState(), getProviderPolicy(), listProviders(), patchBrainConfig() (+26 more)

### Community 117 - "SeoFixer"
Cohesion: 0.08
Nodes (22): Request to remediate auto-fixable findings in a local code repository., One concrete remediation performed (or proposed) by the fixer., SeoFixAction, SeoFixRequest, _humanize_filename(), BeautifulSoup, Path, services/seo_fixer.py - Repo-Aware SEO Auto-Fixer When a company has a code… (+14 more)

### Community 118 - "TaskIn"
Cohesion: 0.05
Nodes (40): _active_primary_provider(), is_north_mini_code_default(), True when the ``NORTH_MINI_CODE_DEFAULT`` flag is on (default ON). Reads the…, Best-effort read of the active brain's primary provider (or ``None``)., Resolve the model id to force for a code-execution run, or ``None``. Returns…, resolve_coding_model_preference(), _check_auth(), health() (+32 more)

### Community 119 - "probe_model_liveness"
Cohesion: 0.04
Nodes (62): provider_api_key(), Return the live API key for *provider* (env-only — never persisted)., _describe_http_status(), _is_dns_failure(), _probe_failure_reason(), probe_model_liveness(), _probe_ollama(), _probe_openai_compat() (+54 more)

### Community 120 - "Command"
Cohesion: 0.06
Nodes (22): Command, CommandCategory, CommandDispatcher, Enum, SuperClaude Slash Commands — CommandDispatcher with registration, role gating,…, Parse and execute a slash command from raw text. Args: text: Raw command text,…, Return all enabled commands in a given category., Return all registered commands. (+14 more)

### Community 121 - "ChatPage.js"
Cohesion: 0.06
Nodes (42): cancelAgentChatJob(), chatSend(), deleteSession(), getAgentChatJob(), getSession(), listProviderModels(), listSessions(), resumeAgentChatJob() (+34 more)

### Community 122 - "test_context_rulebook.py"
Cohesion: 0.06
Nodes (53): Module, stmt, _bound_names(), _good_result(), _guard_statements(), _load(), ModuleType, parametrize (+45 more)

### Community 123 - "ArtifactStore"
Cohesion: 0.07
Nodes (26): Path, tests/test_artifact_store.py — Unit tests for workflow/artifact_store.py., Verify artifacts that are stored as JSON (e.g., CheckRun results)., Writing the same (run_id, name) twice should update, not duplicate., store(), TestArtifactStoreDeletion, TestArtifactStoreJSONArtifact, TestArtifactStoreListing (+18 more)

### Community 124 - "kimi_bridge_provider_config"
Cohesion: 0.18
Nodes (13): _enabled(), kimi_bridge_provider_config(), kimi_bridge_status(), _norm_env(), ProviderConfig, Free Kimi (Moonshot) **web-bridge** provider. Why this exists ---------------…, Lightweight status used by the Providers UI / Doctor., Return a free, OpenAI-compatible ``ProviderConfig`` for the Kimi bridge.… (+5 more)

### Community 125 - "InferenceCache"
Cohesion: 0.06
Nodes (27): CachedLLMClient, Any, Cached LLM Client wrapper. Drop-in wrapper around any LLM API call that…, Return performance metrics for this client instance., Try to extract token count from various response formats., Wraps an LLM call function with inference caching. Usage: from agent.cached_llm…, Execute an LLM completion, using cache when available. Args: model: Model…, CacheEntry (+19 more)

### Community 126 - "CheckpointStore"
Cohesion: 0.09
Nodes (27): Checkpoint, checkpoint_agent_state(), _checkpointing_enabled(), CheckpointStore, cleanup_checkpoints(), _get_checkpoint_store(), Any, Path (+19 more)

### Community 127 - "test_governance_api.py"
Cohesion: 0.07
Nodes (47): Replace the process-wide gate. Tests only., reset_gate(), _client(), parametrize, TestClient, Tests for the governance HTTP surface and the AgentRunner integration. The…, Policy is a git-reviewed file. An HTTP mutation route would make "who changed…, The tool that makes turning on enforcement safe. (+39 more)

### Community 128 - "useSafeData"
Cohesion: 0.07
Nodes (22): changeUserRole(), createApiKey(), deleteApiKey(), setUserOnboarding(), useSafeData(), AdminOnboardingPanel(), AdminScreen(), errText() (+14 more)

### Community 129 - "Usage"
Cohesion: 0.08
Nodes (29): AlertHandler, BudgetTracker, Counter, _Dimensions, get_budget(), _month(), Any, packages/llm/budget.py — token and cost accounting with spend alerts. Tracks… (+21 more)

### Community 130 - "test_ceo_supervision.py"
Cohesion: 0.05
Nodes (85): _harvest_changed_files(), Extract the files a runtime touched. Returns ``(files, reported)``. Adapters…, Attempt, One delegation of one subtask to one tier., A subtask's full history: what it is, and every attempt at it., SubtaskRecord, _env_flag(), _env_int() (+77 more)

### Community 131 - "WorkflowEngine"
Cohesion: 0.09
Nodes (29): Any, Connection, Path, PhaseType, WorkflowRun, CRISPY workflow engine — phase sequencer + gate controller. GATE: Golden Path…, Return the AgentSwarm singleton if available, else None., Append an event to the workflow event log. (+21 more)

### Community 132 - "LLMRouter"
Cohesion: 0.06
Nodes (35): Attempt, payload_key(), Exact-match cache key over the fields that change the answer. Routing…, Read the environment variables named in ``env_names`` into a key list. Order is…, resolve_keys(), LLMRouter, Any, AsyncClient (+27 more)

### Community 133 - "ImprovementLoop"
Cohesion: 0.05
Nodes (63): _parse_ceo_directives(), DetectedIssue, ImprovementLoop, ImprovementLoopState, _now(), Any, Path, Background scanner and task dispatcher for continuous codebase improvement.… (+55 more)

### Community 134 - "test_trend_scoping.py"
Cohesion: 0.09
Nodes (50): Issue title: the failure mode plus how hard it is recurring., _company_attr(), company_stack_tags(), extract_stack_tags(), fan_out_trend(), fan_out_trends(), is_code_change_trend(), map_trend_to_company_task() (+42 more)

### Community 135 - "get_feature_matrix"
Cohesion: 0.06
Nodes (37): check_feature(), get_feature(), list_features(), Any, get, post, features/api.py — Admin API for the feature support matrix. Exposes: GET…, Return the full support matrix with summary. (+29 more)

### Community 136 - "DigestSummary"
Cohesion: 0.23
Nodes (19): aggregate_last_24h(), build_daily_digest(), compute_cutoff(), DigestSummary, format_digest_markdown(), _md_escape(), _now_utc(), Any (+11 more)

### Community 137 - "test_issue_intake.py"
Cohesion: 0.07
Nodes (50): _capability_tags(), create_task_from_oldest_open_issue(), intake_issue(), _issue_labels(), issue_source_id(), map_issue_to_task(), Any, Task (+42 more)

### Community 138 - "WorkspaceManager"
Cohesion: 0.05
Nodes (13): If a symlink inside the workspace points outside, resolve_path blocks it., Only expired workspaces (past retention TTL) are cleaned up., Two threads creating the same session/job should not corrupt state., TestWorkspaceLifecycle, TestWorkspaceManifest, TestWorkspaceResume, Any, First-class workspace isolation manager. Every session/job gets its own… (+5 more)

### Community 139 - "test_startup_warmup.py"
Cohesion: 0.08
Nodes (29): _isolate_warmup_overflow(), asyncio, Regression tests for the bounded startup warm-up and login bootstrap. Uvicorn…, A deferred step that fails must not leak a reference or an exception., The deferred-bootstrap path: nothing registered, so wire it now., Whatever triggers it, wiring must register the pair., It has to be cheap, or it cannot live outside the warm-up budget., A hanging bootstrap must not hold /api/auth/login open. (+21 more)

### Community 140 - "_StubProvider"
Cohesion: 0.09
Nodes (24): _models_to_try(), Order the models to attempt on *provider*, correcting a stale catalogue. Cache-…, _mock_get(), _ok(), asyncio, A stale model catalogue must not be mistaken for a dead account.…, None means "could not find out" and must not read as "no models"., Otherwise every failed call re-asks a provider that is already down. (+16 more)

### Community 141 - "config.py"
Cohesion: 0.03
Nodes (93): AgentPolicy, _apply_env_overrides(), _apply_key_env(), _build(), _coerce(), config_dir(), _env_key_names(), expand_env() (+85 more)

### Community 142 - "ChatHistoryStore"
Cohesion: 0.07
Nodes (25): ChatHistoryStore, Any, Connection, Delete a session and all its messages. Returns True if deleted., List sessions ordered by most recently updated., Return total session and message counts., Append a message to the session. Returns the message's sequence number.…, Append multiple messages at once. Returns number of messages appended. (+17 more)

### Community 143 - "api.ts"
Cohesion: 0.09
Nodes (44): adminBootstrap(), adminCreateProvider(), adminCreateWorkspace(), adminDeleteProvider(), adminDeleteWorkspace(), adminGetBrainPolicy(), adminGetProviderRoleTags(), adminHeaders() (+36 more)

### Community 144 - "control_overrides.py"
Cohesion: 0.08
Nodes (38): build_platform_controls_router(), APIRouter, Build the router, bound to the app's auth dependency. Takes…, _as_int(), clear_override(), _control_state(), effective_value(), load_overrides() (+30 more)

### Community 145 - "GoalRecord"
Cohesion: 0.05
Nodes (54): brain_availability_summary(), Non-secret answer to "can the brain answer a request right now?". Three callers…, _backend(), CEOLedger, GoalRecord, _now(), Any, services/ceo_ledger.py — durable record of what the CEO is driving to closure.… (+46 more)

### Community 146 - "WebReach"
Cohesion: 0.07
Nodes (50): Register the Web Reach capability (agent/web_reach.py): zero-key internet…, _register_web_reach_tools(), _egress_policy_reason(), get_web_reach(), _load_script_module(), Any, ModuleType, Response (+42 more)

### Community 147 - "claim"
Cohesion: 0.07
Nodes (28): claim(), cooldown_clear(), cooldown_get(), cooldown_set(), _get_backend(), incr_window(), Shared-state abstraction — in-memory (default) and Redis backends. Provides…, Reset the singleton (for tests). (+20 more)

### Community 148 - "test_render_mcp.py"
Cohesion: 0.07
Nodes (28): build_render_router(), Any, APIRouter, Exception, backend/render_router.py — Render platform view for operators and agents.…, Reject anyone who is not the agency admin., Map an MCP transport failure onto 503 rather than a 500. The distinction…, _require_admin() (+20 more)

### Community 149 - ".run"
Cohesion: 0.10
Nodes (34): build_spec_router(), Any, APIRouter, backend/spec_router.py — review/approve persisted plan specifications. Surfaces…, await_spec_approval(), _db(), _flag(), get_spec() (+26 more)

### Community 150 - "V5App.jsx"
Cohesion: 0.05
Nodes (30): API, getLoops(), V5App, ActivationGate(), activityToAlert(), AlertsBell(), priorityConfig, _relativeTime() (+22 more)

### Community 151 - "test_response_cache.py"
Cohesion: 0.12
Nodes (47): _cache_key(), cache_stats(), clear_cache(), get_cached(), is_cacheable(), put_cached(), Any, packages/ai/response_cache.py — LRU+TTL in-memory response cache for the… (+39 more)

### Community 152 - "workspaces.py"
Cohesion: 0.12
Nodes (11): _atomic_write_json(), default_store_paths(), get_data_dir(), _now(), Any, Path, _normalize_path(), _now() (+3 more)

### Community 153 - "NvidiaProvider"
Cohesion: 0.06
Nodes (10): GroqProvider, Provider, NvidiaProvider, Provider, NVIDIA NIM — free LLM provider (meta/llama-3.3-70b-instruct)., OllamaProvider, Provider, RateLimit (+2 more)

### Community 154 - "test_slop_gate.py"
Cohesion: 0.07
Nodes (44): _extract_mentioned_paths(), Pick the auto-PR model from the recommended free-cloud chain by key. Mirrors…, Extract plausible file paths from issue text., Read existing files for codebase context (max 8000 chars total)., _read_grounding_files(), _select_brain(), diff_is_sloppy(), is_destructive_overwrite() (+36 more)

### Community 155 - "AutonomyTracker"
Cohesion: 0.06
Nodes (24): AutonomyCounter, AutonomySnapshot, AutonomyTracker, get_tracker(), Any, agent/kpi.py — Autonomy KPIs: evidence capture and metrics tracking. Tracks key…, Return a point-in-time snapshot of all KPIs., Reset all counters (test helper). (+16 more)

### Community 156 - "activation_api.py"
Cohesion: 0.05
Nodes (87): activation_required(), ActivationResult, activate_instance(), ActivateRequest, ActivateResponse, activation_audit_log(), activation_status(), ActivationStatusResponse (+79 more)

### Community 157 - "ToolAnnotations"
Cohesion: 0.07
Nodes (22): filter_safe_tools(), get_tool_annotations(), Typed representation of MCP tool annotations (spec 2025-11-05 §5.6.1). All…, Return True only when the tool is definitively read-only and non-destructive.…, Extract ``ToolAnnotations`` for a named tool from a ``list_tools()`` result.…, Return tools where ``readOnlyHint`` is True and ``destructiveHint`` is not…, ToolAnnotations, asyncio (+14 more)

### Community 158 - "test_quick_note.py"
Cohesion: 0.08
Nodes (30): _fetch_text(), _now(), process_note(), Any, Path, QuickNote, agent/quick_note.py — iPhone Quick Note integration. Persistent URL queue +…, GET *url* and return plain text (HTML tags stripped, max *max_chars*). (+22 more)

### Community 159 - "Workspace"
Cohesion: 0.08
Nodes (15): Any, Path, mcp_server/workspace.py — Isolated workspace manager for the MCP server. Each…, Run a shell command inside the workspace via an explicit shell binary., Resolve rel against root, reject path traversal., Run a subprocess. Never uses shell=True., Manages a single isolated workspace directory., Canonical root path (follows macOS /var → /private/var symlinks). (+7 more)

### Community 160 - "MetricsRegistry"
Cohesion: 0.08
Nodes (23): _Counter, _escape(), _Gauge, _Histogram, _labels(), MetricsRegistry, Any, packages/llm/metrics.py — Prometheus metrics without the client library. The… (+15 more)

### Community 161 - "test_integration_c4_c5_c6_d3.py"
Cohesion: 0.09
Nodes (26): FailureCategory, E2: Classify a failure from its description text. Order matters:…, Classified failure types for targeted self-healing (E2)., get_current_trace_id(), get_tracer(), langfuse_metadata_with_trace(), Portable trace context that can be passed across async boundaries., Lazy-initialised OpenTelemetry tracer provider. Only imports the OTEL SDK when… (+18 more)

### Community 162 - "test_e2b_task_wiring.py"
Cohesion: 0.08
Nodes (42): _build_coordinator(), _clean_e2b_env(), _FakeCompany, _FakeCompanyGraphStore, _FakeRepoConnection, _make_task(), Task, tests/test_e2b_task_wiring.py — Task.company_id → spec.context repo_url wiring.… (+34 more)

### Community 163 - ".get_workspace"
Cohesion: 0.08
Nodes (25): _derive_workspace_root(), Path, WorkspaceStatusLiteral, Create an isolated workspace for a session and optional job. Creates the…, Retrieve the WorkspaceManifest for a given session and optional job. Looks up…, List all known workspaces, optionally filtered by status., Mark a workspace as active (in-use)., Pause a workspace (e.g. between agent steps). (+17 more)

### Community 164 - "OnboardingScreen.jsx"
Cohesion: 0.05
Nodes (30): createCompany(), getCompany(), getOnboardingProgress(), listSpecialists(), scanRepo(), scanWebsite(), startOnboarding(), submitOnboardingAnswers() (+22 more)

### Community 165 - "Settings"
Cohesion: 0.05
Nodes (20): When True, the governance layer evaluates and audits agent actions. This is…, Typed configuration loaded from environment variables., When True, approval-gated actions self-approve. Local dev only., ``RENDER_SERVICE_IDS`` split into a clean list (empty when unset)., True when there is both an API key and an endpoint to reach., When True, the Render ops loop runs. On by default. Also requires…, When True, mutating Render MCP tools may be called. Default False., Validated `reasoning_effort` for Ollama thinking models, or ``""``. Returns one… (+12 more)

### Community 166 - "OllamaCircuitBreaker"
Cohesion: 0.08
Nodes (36): _Circuit, _enabled(), _failure_threshold(), get_circuit_breaker(), OllamaCircuitBreaker, Per-model circuit breaker for Ollama backend health. Tracks consecutive failure…, Record a successful response; close the circuit., Record a 5xx error; open the circuit after threshold is reached. (+28 more)

### Community 167 - "SetupChecker"
Cohesion: 0.07
Nodes (25): main(), OllamaManager, OsDetector, Path, Detect operating system and available interpreters., Return normalized OS name., Detect PowerShell (Windows) or Bash (Unix)., Print colored message. (+17 more)

### Community 168 - "PromptCacheManager"
Cohesion: 0.06
Nodes (20): CacheEntry, CacheStats, get_prompt_cache(), PromptCacheManager, Any, Compute a deterministic cache key from the stable prefix. The stable prefix is…, Hash a system prompt and model for KV cache fingerprinting., Return the instance ID that has this prefix cached, or None. Performs an LRU… (+12 more)

### Community 169 - "cost_insights.py"
Cohesion: 0.12
Nodes (26): compute_savings(), compute_time_series(), get_savings(), get_usage(), get_user_savings(), _period_start(), Any, BaseModel (+18 more)

### Community 170 - "TaskDetailPanel.jsx"
Cohesion: 0.07
Nodes (26): addTaskComment(), clarifyTask(), escalateTask(), fetchVelocity(), followUpTask(), updateTask(), HEALTH_COLORS, HEALTH_DOTS (+18 more)

### Community 171 - "TrendWatcher"
Cohesion: 0.12
Nodes (17): Any, AsyncClient, Path, Fetches AI trend signals from many public sources and surfaces relevant ones., Fetch all sources in parallel; return new alerts sorted by relevance., Fan trends out to onboarded companies whose stack matches (G4). For each…, Dispatch high-relevance alerts to the Hermes sidecar for action. Only…, TrendAlert (+9 more)

### Community 172 - "test_audit.py"
Cohesion: 0.07
Nodes (39): AuditMessage, AuditSession, create_session(), delete_session(), get_session(), list_sessions(), Any, Audit session management for multi-turn conversations. This module provides in-… (+31 more)

### Community 173 - "CEOSupervisor"
Cohesion: 0.09
Nodes (20): get_ceo_dispatcher(), Return the shared CEODispatcher singleton., Reset the singleton (test helper)., reset_ceo_dispatcher(), CEOSupervisor, Any, Sweeps the CEO ledger and drives open goals to closure., Sweep on the configured cadence until cancelled. A failing sweep is logged and… (+12 more)

### Community 174 - "test_mcp_governance.py"
Cohesion: 0.11
Nodes (30): get_audit_log(), Return the process-wide audit log, created on first use., _call(), client(), _engine(), Governance on the MCP HTTP surface — threat-model T11. Before this,…, Same Golden Rule guarantee as the in-process gate., No UI is attached to this surface, so holding the socket would hang it. (+22 more)

### Community 175 - "[Unreleased]"
Cohesion: 0.04
Nodes (44): [5.0.0], Added, Added, Added, Added, Added, Added, Added (+36 more)

### Community 176 - "[Unreleased]"
Cohesion: 0.04
Nodes (44): [5.0.0], Added, Added, Added, Added, Added, Added, Added (+36 more)

### Community 177 - "test_provider_enable_disable.py"
Cohesion: 0.09
Nodes (15): isolated_kv(), one_provider(), asyncio, parametrize, Per-provider on/off switch, with auto-disable for unfixable failures only.…, The critical guard: disabling on 429 would switch off every free provider., Point the kv_store at a temp DB so tests never touch real state., Storage problems must degrade, not raise. (+7 more)

### Community 178 - "ApprovalStore"
Cohesion: 0.07
Nodes (29): Event, publish(), packages/events/bus.py — In-process event bus. Loosely couples components via…, An event published on the bus., Subscribe to an event type., Publish an event to all subscribers., subscribe(), ApprovalRequest (+21 more)

### Community 179 - "TestChatHistoryStore"
Cohesion: 0.07
Nodes (17): get_chat_history(), Return the module-level ChatHistoryStore singleton., get_context_window_manager(), Enum, How to truncate messages when over the context limit., Return the module-level ContextWindowManager singleton., Result of a context window truncation operation., TruncationResult (+9 more)

### Community 180 - "test_features_api.py"
Cohesion: 0.05
Nodes (4): _auth_override(), client(), _fake_auth(), Integration tests for all new feature API routes in proxy.py.

### Community 181 - "test_video_transcript.py"
Cohesion: 0.05
Nodes (33): parametrize, Tests for video transcript extraction (`.github/scripts/video_transcript.py`).…, Events without `segs` carry no text and must not produce stray spaces., This format double-encodes: `&amp;#39;` must resolve to a single quote., Regex-terminated matching truncates this; brace matching must not. The blob…, A title containing a brace must not unbalance the matcher., An unfamiliar page shape must yield empties, never raise., A non-video URL must short-circuit before any request is attempted. (+25 more)

### Community 182 - "Part A — CodeRabbit review fixes for this PR (do first, small)"
Cohesion: 0.05
Nodes (42): A1 — `docs/changelog.md`: add the two autonomy docs under `### Added` ✅ trivial, A2 — `docs/telegram-bot.md`: fix broken charter links (MD + path), A3 — `docs/telegram-bot.md`: add language to fenced block (MD040), A4 — `.env.example`: use exact var name in the shortcut comment, A5 — `services/workflow_orchestrator.py`: surface notify failures at WARNING, A6 — `telegram_bot.py`: avoid double-approve in the `wfo_approve` path ⚠️ behavioural, A7 — `telegram_service.py`: escape Markdown-v1 reserved chars in approval text ⚠️ correctness, A8 — `render.yaml`: propagate Telegram vars to the worker service (+34 more)

### Community 183 - "FilterResult"
Cohesion: 0.16
Nodes (13): FilterResult, OutputFilter, Filter and compress command outputs to reduce LLM token consumption. Provides…, Compact git status output — keep only changed file paths., Compact git log — one line per commit., Compact git diff — keep file headers, collapse hunks., Compact test output — keep only failures and summary., Deduplicate log lines and keep only unique patterns. (+5 more)

### Community 184 - "_get_provider_policy"
Cohesion: 0.05
Nodes (47): _get_provider_policy(), Read the durable provider policy from DB, falling back to a safe default.…, _nvidia_provider_chain(), ProviderConfig, TaskResult, TaskSpec, Execute a TaskSpec using the internal AgentRunner and convert the agent's…, Create an isolated execution context for a single task. Tries ``git worktree… (+39 more)

### Community 185 - "Persistent Memory System"
Cohesion: 0.05
Nodes (41): 1. **Semantic Memory Categorization**, 1. **Use Appropriate Scopes**, 2. **Prioritize Effectively**, 2. **Scope-Based Auto-Loading**, 3. **Priority-Based Retrieval**, 3. **Use Semantic Categories**, 4. **Cross-Tool Compatibility**, 4. **Tag Liberally** (+33 more)

### Community 186 - "test_colibri_provider.py"
Cohesion: 0.12
Nodes (28): colibri_enabled(), colibri_provider_config(), colibri_status(), ProviderConfig, providers/colibri.py — Free local GLM-5.2 brain served by JustVugg/colibri.…, Return True iff the operator opted in via ``COLIBRI_ENABLED=true``., Cheap status snapshot for tests + admin UI., Return the ``ProviderConfig`` for the local colibri server, or ``None`` when… (+20 more)

### Community 187 - "RuntimesPage.js"
Cohesion: 0.13
Nodes (19): getRoutingPolicy(), refreshRuntimeHealth(), runTaskOnRuntime(), startAllRuntimes(), startRuntime(), stopAllRuntimes(), stopRuntime(), updateRoutingPolicy() (+11 more)

### Community 188 - "facade.py"
Cohesion: 0.16
Nodes (19): create_refresh_token(), create_access_token(), create_refresh_token(), get_current_user(), get_optional_user(), github_exchange_code(), github_fetch_user(), google_exchange_code() (+11 more)

### Community 189 - "emit_chat_observation"
Cohesion: 0.09
Nodes (36): observability_diag_public(), PUBLIC diagnostic endpoint for Langfuse — no auth required. Returns exactly…, CommercialEquivalent, estimate_commercial_equivalent_usd(), get_prices(), _load_from_env(), _parse_mapping(), Any (+28 more)

### Community 190 - "anthropic_compat.py"
Cohesion: 0.09
Nodes (29): _build_anthropic_response(), _emit_safely(), _finish_reason_to_stop_reason(), handle_anthropic_messages(), _messages_to_openai(), _openai_choice_to_anthropic_content(), _post_anthropic_with_fallback(), Any (+21 more)

### Community 191 - "test_issue_triage.py"
Cohesion: 0.17
Nodes (19): _match_family(), Any, services/issue_triage.py — inbound GitHub issue triage. Closes the intake gap…, Classify a single GitHub issue payload and return the routing decision. Pure…, Fetch unlabeled open issues, triage each, and route them. Returns a summary…, run_triage_cycle(), _severity_for(), triage_enabled() (+11 more)

### Community 192 - "compare_runtimes.py"
Cohesion: 0.07
Nodes (21): compare(), main(), Any, scripts/compare_runtimes.py — head-to-head runtime comparison. Answers the…, Check an operator-supplied task file before anything executes., render(), _run_one(), RunRecord (+13 more)

### Community 193 - "test_portfolio_intake.py"
Cohesion: 0.09
Nodes (33): map_initiative_to_task(), materialize_committed(), _portfolio_materialize_enabled(), portfolio_source_id(), Any, Task, tasks/portfolio_intake.py — Portfolio initiative → Task materializer. Converts…, Content-derived stable id for a portfolio initiative. Initiative UUIDs… (+25 more)

### Community 194 - "test_schedule_growth_invariants.py"
Cohesion: 0.12
Nodes (17): _FakeSQLiteStore, asyncio, parametrize, Workstream D — Never again: dedup + growth invariants. These tests enforce…, Simulates a SQLite-style store with load_all/upsert/remove., Duplicate-named rows must collapse to newest on BOTH backends. Regression for…, Stale unfired run-once jobs (run_count==0, old created_at) must be deleted. The…, TASK_DISPATCH_CONCURRENCY=1 must prevent concurrent task execution. The… (+9 more)

### Community 195 - "v4_api.py"
Cohesion: 0.11
Nodes (38): _get_cached_tasks(), _get_tasks_cache_lock(), _load_improvement_state(), Any, BaseModel, get, Lock, post (+30 more)

### Community 196 - "PatternConsolidation"
Cohesion: 0.07
Nodes (17): ConsolidationPhase, DreamMemory, PatternConsolidation, Enum, str, Dream Memory Consolidation — pattern consolidation across AI sessions. Inspired…, Group memories into clusters by tag overlap., Jaccard similarity of tag sets. (+9 more)

### Community 197 - "distributed.py"
Cohesion: 0.08
Nodes (20): DistributedRateLimiter, get_limiter(), get_persistent_queue(), _LocalBucket, PersistedRequest, PersistentQueue, Any, packages/llm/distributed.py — cross-instance coordination. Two facilities that… (+12 more)

### Community 198 - "OrchestratorQueue"
Cohesion: 0.08
Nodes (12): OrchestratorQueue, Any, _QueueEntry, Async FIFO queue that limits concurrent orchestrator run executions.…, Enqueue a run for async execution. Returns immediately. ``fn(*args, **kwargs)``…, Enqueue a run and return a future that resolves when it completes., stop_orchestrator_queue(), enqueue_and_wait() callers DO await the future, so failures must still raise… (+4 more)

### Community 199 - "test_telegram_freebuff.py"
Cohesion: 0.07
Nodes (46): cmd_freebuff(), _model_keyboard(), _parse_callback(), _parse_user_ids(), _process_callback(), Extract numeric Telegram user IDs from a raw env value, tolerantly. Accepts…, Resolve the ALLOWED/ADMIN Telegram user-ID sets. ``TELEGRAM_CHAT_ID`` is the…, Send a message with an inline keyboard (list of button rows). (+38 more)

### Community 200 - "test_schedule_backlog_drain.py"
Cohesion: 0.10
Nodes (39): _every_minute_one_shot(), _FakePersistence, _one_shot(), asyncio, Why the 2026-08-01 backlog never drained, despite a fix already existing.…, A timestamp we cannot parse must not authorise a delete., An agency-directive-shaped row: cron="* * * * *", uniquely named., 2026-08-03: the 7-day fallback let a live crash loop regrow the backlog from a… (+31 more)

### Community 201 - "_run"
Cohesion: 0.07
Nodes (18): _patch_send_message(), tests/test_telegram_inbound.py Pytest coverage for the Step 1 inbound-routing…, ``_resolve_reply_to_decision`` returns the durable link from SQLite.\n, ``/redirect`` command: admin-only, prefix-dispatched, idempotent shape., ``/paste <abs-path>`` command: admin gate + path check + truncation., ``_handle_big_paste`` writes to disk and short-replies., ``_route_plain_text`` classifies and dispatches per the documented map., Return a Telegram nested-message-shaped dict for resolve-reply-to tests. (+10 more)

### Community 202 - "test_workspace_isolation.py"
Cohesion: 0.19
Nodes (24): Tests for workspace isolation model (Area A). Covers: - Unique workspace path…, TestConcurrency, TestCrossSessionIsolation, TestJobIdValidation, TestPathSafety, TestWorkspaceCleanup, TestWorkspaceMetrics, TestWorkspaceNotFound (+16 more)

### Community 203 - "TestAgentJobRequest"
Cohesion: 0.06
Nodes (18): AgentJobError, AgentJobResult, Any, field_validator, agent/contract.py — Typed public contract for the agent job lifecycle. Phase 1…, Structured error payload attached to a failed job., Typed result returned by a completed agent job. The ``response`` field is the…, Accept a bare string (legacy runner output) or a full dict. (+10 more)

### Community 204 - "AgentsScreen.jsx"
Cohesion: 0.11
Nodes (23): createAgent(), deleteAgent(), updateAgent(), AgentCard(), AgentForm(), AgentsPage(), cls(), normalizeAgent() (+15 more)

### Community 205 - "KnowledgeScreen.jsx"
Cohesion: 0.09
Nodes (29): createWikiPage(), deleteSource(), deleteWikiPage(), getCompanyGraph(), getSource(), getWikiPage(), ingestSource(), lintWiki() (+21 more)

### Community 206 - "getBackendUrl"
Cohesion: 0.10
Nodes (30): getAccessToken(), getApiUrl(), getAuthHeaders(), getBackendUrl(), ActivityEvent, AgentActivityFeedProps, ActivityEventRow(), AGENT_COLORS (+22 more)

### Community 207 - "TestEstimateTokensForMessages"
Cohesion: 0.06
Nodes (12): _estimate_tokens_for_messages(), _normalize_anthropic_output_format(), Estimate input token count for an Anthropic-format message list. Uses a simple…, Translate Anthropic ``output_format`` into an Ollama ``format`` field. Modifies…, Daily automation tests — 2026-05-15 Covers three features implemented in this…, Integration tests for POST /v1/messages/count_tokens., Unit tests for _normalize_anthropic_output_format., Caller adds anthropic-beta header when _normalize returns True. (+4 more)

### Community 208 - "SchedulerStore"
Cohesion: 0.07
Nodes (19): get_scheduler_store(), _MemCollection, _MemCursor, _MemDB, _MemDeleteResult, Any, services/scheduler_store.py — Durable scheduler persistence. Issue #505:…, Delete a persisted job. (+11 more)

### Community 209 - "TestClient"
Cohesion: 0.07
Nodes (25): backend_jwt(), proxy_client(), MonkeyPatch, TestClient, Regression test for /api/auth/me — verifies the critical endpoint on both the…, TestClient against proxy.py:app with a known API key seeded., API-key-based /api/auth/me on proxy.py (port 8000)., GET /api/auth/me with valid API key → 200 with derived profile. (+17 more)

### Community 210 - "test_crispy_workflow.py"
Cohesion: 0.07
Nodes (22): _fake_artifact(), _make_engine(), tests/test_crispy_workflow.py — CRISPY workflow engine hardening tests. Tests…, Provide isolated DB + artifact + workspace paths., Create a WorkflowEngine with isolated storage., TestAbortOnFailure, TestPhaseSequence, TestPhaseSequenceError (+14 more)

### Community 211 - "GitHubTools"
Cohesion: 0.14
Nodes (15): GitHubTools, Any, get, post, List issues (excludes pull requests) for triage/intake pipelines., Add labels to an issue (used to mark it as triaged, preventing reprocessing)., Merge an open pull request via the GitHub API., Backwards-compat: accepts 'owner/repo' format. (+7 more)

### Community 212 - "timedelta"
Cohesion: 0.12
Nodes (21): PR throughput per cohort over the last `days` days., _as_aware_utc(), _env_float(), datetime, services/ephemeral_reaper.py — destroy expired ephemeral companies. The…, Treat naive datetimes as UTC so comparisons never raise., Delete all expired ephemeral companies. Returns the number deleted. A company…, Parse a positive, finite float env var (seconds), else the default. Rejects… (+13 more)

### Community 213 - "validate_outbound_url"
Cohesion: 0.14
Nodes (25): test_git_ref_rejects_empty(), test_git_ref_rejects_flag_injection(), test_git_ref_rejects_shell_metacharacters(), test_git_ref_rejects_traversal(), test_git_ref_valid(), test_git_scheme_allows_ssh(), test_http_scheme_rejects_ssh(), test_https_public_host_allowed() (+17 more)

### Community 214 - "test_daily_2026_06_04.py"
Cohesion: 0.08
Nodes (37): _content_block_to_text(), Convert a single Anthropic content block to a plain text string., is_anthropic_model(), True when *model* names a paid Anthropic/Bedrock-Claude model. Covers native…, _opus_model(), Return an Opus model ID iff the operator explicitly opted into a paid brain.…, test_is_anthropic_model(), _content_block_to_text() (+29 more)

### Community 215 - "PolicyEngine"
Cohesion: 0.03
Nodes (68): Return the stable ``agent:<slug>`` id for a human agent name. Deterministic and…, slugify_agent(), _action_matches(), _as_list(), GroupPolicy, _host_matches(), Mode, _normalise_path() (+60 more)

### Community 216 - "ServiceDaemon"
Cohesion: 0.09
Nodes (26): configure(), get_status(), health(), BaseModel, get, post, Validate configured paths., Check if proxy is running. (+18 more)

### Community 217 - "ContextWindowManager"
Cohesion: 0.10
Nodes (14): ContextWindowManager, Any, Return True if the estimated tokens exceed the model's context limit., Truncate messages to fit within the model's context window. Args: messages:…, Return the context window size for a model. Looks up the model in the…, Estimate token count for a list of messages. Uses a character-based heuristic…, Estimate token count using tiktoken (more accurate, requires install)., Keep system prompt(s) + the last N turns within the token limit. A 'turn' is a… (+6 more)

### Community 218 - "NIMConnectionPool"
Cohesion: 0.07
Nodes (20): get_nim_pool(), NIMConnectionPool, Any, AsyncClient, Enum, Response, Persistent httpx.AsyncClient pool with circuit breaker and retry logic. Manages…, Get or create the shared httpx.AsyncClient. (+12 more)

### Community 219 - "ContextPruner"
Cohesion: 0.09
Nodes (29): ContextPruner, Any, context_pruner.py — auto-generated module docstring (user-research skill scan)., Walk messages backward, accumulating per-role char counts. Returns…, Wrap evicted messages into ``<historical_memory_only>`` XML. The XML block is…, Reset the prune timer so the next call always runs the pipeline., 3-phase context window management middleware. Phase 1 — Truncate: Strips…, Apply 3-phase pruning if the context is over budget or cache expired. Returns… (+21 more)

### Community 220 - "IssueCategory"
Cohesion: 0.12
Nodes (34): IssueCategory, IssueSeverity, Enum, str, agent/improvement_loop.py — Continuous Improvement Engine Background scanner…, cluster_friction(), clusters_to_issues(), collect_friction_events() (+26 more)

### Community 221 - "ScheduledJob"
Cohesion: 0.09
Nodes (19): _now(), Any, Reconstruct a ScheduledJob from its as_dict() output., Register a new job. Returns the created :class:`ScheduledJob`.…, Fire a job immediately (webhook / manual trigger)., Remove a job. Returns *True* if it existed., Update the display name of a job., Enable or disable a job without deleting it. (+11 more)

### Community 222 - "_Collection"
Cohesion: 0.11
Nodes (16): _apply_update(), _Collection, _DeleteResult, _InsertResult, _match(), _new_id(), _now_iso(), db/sqlite_store.py — Async SQLite storage backend. Provides a Motor-compatible… (+8 more)

### Community 223 - "StreamingDeltaReconstructor"
Cohesion: 0.09
Nodes (17): PostProcessHook, create_streaming_reconstructor(), Any, Register a post-processing hook (runs before re-streaming)., Remove a post-processing hook., Feed a raw SSE line from the upstream stream., Feed raw text (e.g., from a non-streaming response) for re-emission., Apply all registered hooks to the accumulated text. Returns the final processed… (+9 more)

### Community 224 - "DecisionsStoreTests"
Cohesion: 0.12
Nodes (5): Test-only: clears the cached singleton so the next get_decisions_store() builds…, reset_decisions_store_singleton(), DecisionsStoreTests, _fresh_store(), Smoke: create() returns a fresh dec_<hex8> per call (no error surfaces from…

### Community 225 - "test_trend_watcher.py"
Cohesion: 0.09
Nodes (21): _FakeClient, asyncio, Tests for agent/trend_watcher.py, Ensure expanded keyword set covers key new categories., setup_database_moks(), test_fetch_arxiv(), test_fetch_github_trending(), test_fetch_google_news() (+13 more)

### Community 226 - "workflow/api.py"
Cohesion: 0.12
Nodes (39): approve(), build(), cancel(), _engine(), get_agent_team(), get_artifact_content(), get_events(), get_run() (+31 more)

### Community 227 - "PlaybookLibrary"
Cohesion: 0.11
Nodes (21): _now(), Playbook, PlaybookLibrary, PlaybookRun, PlaybookStep, Any, Path, agent/playbook.py — Automation Playbooks Pre-defined, named multi-step… (+13 more)

### Community 228 - "test_verification_strategies.py"
Cohesion: 0.12
Nodes (32): cross_verify(), Any, race(), agent/verification_strategies.py — opt-in parallel patterns for high-stakes…, Heuristic fallback score when the reward model is unavailable.…, Run *n* independent attempts at *instruction* concurrently; return the winner.…, True if any path matches the repo's risky-module trigger list., Have an independent agent re-check a completed task's changed files. Returns… (+24 more)

### Community 229 - "test_backend_server_features.py"
Cohesion: 0.06
Nodes (39): _anthropic_headers(), _anthropic_payload(), _anthropic_response_text(), _auth_headers(), chat_completion_text(), list_openai_models(), normalize_base_url(), openai_compat_url() (+31 more)

### Community 230 - "test_platform_controls.py"
Cohesion: 0.06
Nodes (36): apply_overrides(), Write *overrides* into ``os.environ`` and refresh dependent caches. Keys that…, Re-read every ``settings`` attribute from the updated environment. Re-runs…, _refresh_settings_singleton(), all_controls(), Every control in the catalogue, in display order., clean_overrides(), controls_app() (+28 more)

### Community 231 - "REWRITE_PLAN.md — Phased Migration Strategy"
Cohesion: 0.06
Nodes (35): Already completed (pre-migration fixes), Current Status, Inventory of suspected dead code, Migration Safety Checklist, Phase 1: Foundation (Weeks 1-2), Phase 2: Provider Abstraction (Weeks 3-4), Phase 3: Auth Consolidation (Week 5), Phase 4: Scheduler Redesign (Week 6) (+27 more)

### Community 232 - "test_background_services.py"
Cohesion: 0.08
Nodes (23): Return True when the web process should also run background services., run_background_in_web(), anyio, Unit tests for services/background.py — start_background_services wiring.…, Scheduler's on_fire handler is set to TaskAutomation.handle_scheduled_job., Calling bg.stop() twice must not raise or double-stop., RUN_BACKGROUND_IN_WEB defaults to True., The constant itself must leave real margin under Render's 5s timeout. (+15 more)

### Community 233 - "test_all_providers_discovery.py"
Cohesion: 0.16
Nodes (35): _get(), asyncio, ProviderRouter, Verify every supported provider is correctly discovered, prioritised, and…, Check if url hostname matches expected domain (exact or subdomain)., Build a ProviderRouter from_env() with only the supplied env vars active., _router(), test_anthropic_discovery() (+27 more)

### Community 234 - "WorkflowBuildRequest"
Cohesion: 0.11
Nodes (20): Contract: WorkflowEngine cannot skip the gate state machine., Contract: Cannot approve a run in 'pending' state., _make_engine(), _make_run(), tests/test_crispy_run_history.py — N4 acceptance:…, Phase-level outcomes (complete/failed counts per phase_type) come from the…, Only the 5 most recent failure reasons are kept — keeps the response payload…, window_days is the age of the oldest run in days — used to gate the burn-in… (+12 more)

### Community 235 - "test_persistent_memory.py"
Cohesion: 0.06
Nodes (35): memory_store(), Tests for persistent memory system., Test auto-loading global memories., Test auto-loading includes workspace-specific memories., Test that auto-load respects priority ordering., Test filtering memories by category., Create a temporary database for testing., Test searching memories. (+27 more)

### Community 236 - "SecurityScanner"
Cohesion: 0.11
Nodes (25): _now(), Any, Path, agent/security_scanner.py — Security & Vulnerability Scanner Runs static…, Run all available scanners and aggregate results., Run a cross-harness security audit. Checks that the agent harness configuration…, Return True if *name* is on PATH., Return current UTC timestamp as ISO string. (+17 more)

### Community 237 - "Continual Harness (`agent/harness_spec.py`)"
Cohesion: 0.25
Nodes (7): Configuration, Continual Harness (`agent/harness_spec.py`), Flow, Reviewing what it wrote, The two rules that keep it honest, Trying it, Where it lives

### Community 238 - "test_freebuff_bot.py"
Cohesion: 0.10
Nodes (22): _embedded(), _embedded_run(), _fb_models(), _fb_plan(), _fb_run(), _freebuff_max_steps(), Return the free model list (embedded or via proxy)., Generate a read-only plan (embedded or via proxy). Shape: {model, plan}. (+14 more)

### Community 239 - "test_anthropic_router.py"
Cohesion: 0.09
Nodes (10): _make_anthropic_provider(), _payload(), ProviderConfig, Response, Tests for Anthropic-specific router features. Covers: - Prompt caching…, TestAnthropicPayloadExtendedThinking, TestAnthropicPayloadPromptCaching, TestAnthropicToOpenAICacheUsage (+2 more)

### Community 240 - "test_llm_router_e2e.py"
Cohesion: 0.14
Nodes (34): _ok(), parametrize, End-to-end routing against mock providers (ADR-008). These are the tests that…, A router wired to three mock providers, with all singletons isolated., Two keys on alpha means a 429 costs a key, not the provider., The NVIDIA 410 incident, as a regression test (CLAUDE.md §7)., A 422 is the request's fault — trying five providers just adds latency., A 413 is one provider's context window, not a fact about the request. The… (+26 more)

### Community 241 - "seo_api.py"
Cohesion: 0.10
Nodes (37): delegate_seo_findings(), _expire_stale_pending_report(), get_seo_audit(), list_seo_audits(), BaseModel, get, post, SEO / GEO / AIO Audit API Router Endpoints for the world-class SEO audit engine… (+29 more)

### Community 242 - "agent_runtime.py"
Cohesion: 0.11
Nodes (32): _active_cloud_provider(), _candidate_ollama_bases(), _chat(), chat_completions(), _chat_with_ollama(), _chat_with_openai_compat(), ChatRequest, ChatResponse (+24 more)

### Community 243 - "ENGINEERING_STANDARDS.md — Coding, Security & Testing Standards"
Cohesion: 0.06
Nodes (33): 1. Coding Standards, 2. Logging Standards, 3. Security Standards, 4. Testing Standards, 5. CI/CD Standards, 6. Performance Standards, 7. Documentation Standards, Architecture docs (+25 more)

### Community 244 - "DashboardScreen.jsx"
Cohesion: 0.07
Nodes (10): BarChart(), Charts, Donut(), ExecutionTimeline(), Sparkline(), ErrorBoundary, DashboardScreen(), fmtTokens() (+2 more)

### Community 245 - "context_rules.py"
Cohesion: 0.11
Nodes (32): _check_constitution_echo(), _check_files_exist(), _check_grounding(), _check_hedges(), _check_project_identity(), _check_risk_flags(), _check_source_summary(), _check_todos() (+24 more)

### Community 246 - "TestStreamableHTTPTransport"
Cohesion: 0.13
Nodes (12): Decode a JSON-RPC response body from either JSON or an SSE stream. Streamable-…, SSE uses CRLF on the wire; the trailing \\r must not corrupt the JSON., Existing callers pass a base URL and expect /mcp appended., Render's URL already names the endpoint, so nothing is appended., Build an httpx.Response the client can parse, with a bound request., The plain-JSON path (/mcp-internal) must be unchanged., A Streamable-HTTP reply arrives as SSE data: frames., Progress notifications precede the response; the response wins. (+4 more)

### Community 247 - "local_controller.py"
Cohesion: 0.12
Nodes (32): _bin_exists(), _choose_local_brain(), _default_agency_url(), _default_machine_id_file(), _env_int(), _get_or_create_machine_id(), _http_json(), _log() (+24 more)

### Community 248 - "test_live_server.py"
Cohesion: 0.22
Nodes (32): check(), main(), ok(), Any, Client, Response, Returns access token for subsequent tests., Direct-mode chat. Passes even if no LLM backend is running (error message… (+24 more)

### Community 249 - "test_control_plane_api.py"
Cohesion: 0.07
Nodes (14): _FakeStore, mock_runtime_manager(), tests/test_control_plane_api.py — Tests for Control Plane API endpoints. Covers…, In-memory store stub for hydrate() tests — isolates from real DB., Stale run-once jobs (run_count > 0) must be skipped during hydration., Unfired run-once jobs (run_count == 0) must be rehydrated., Jobs already in memory must not be rehydrated (dedup by job_id)., hydrate() with no store must return 0. (+6 more)

### Community 250 - "test_telegram_mutating_commands.py"
Cohesion: 0.08
Nodes (17): _make_mock_response(), tests/test_telegram_mutating_commands.py — N5 acceptance: /setbrain + /merge.…, Build a mock httpx.Response., A successful /setbrain call must: 1. send the X-Service-Token header 2. PATCH…, When the backend's liveness probe fails (HTTP 422), the bot reply must surface…, 503 = backend doesn't have SERVICE_TOKEN set. The bot reply must tell the…, A successful /merge call returns the merge SHA + actor attribution so the…, When the backend refuses to merge (draft, failing CI, not mergeable), the bot… (+9 more)

### Community 251 - "test_context.py"
Cohesion: 0.09
Nodes (22): ContextStats, _estimate_tokens(), Strategy, agent/context.py — Smart Context Compression Three strategies for keeping…, Drop the oldest non-system messages until under the token threshold., Remove exact-duplicate and near-empty messages., Return a (possibly shorter) copy of *messages* using *strategy*. ``inspect``…, Return token usage stats without modifying *messages*. (+14 more)

### Community 252 - "ContextManager"
Cohesion: 0.10
Nodes (21): ContextManager, Any, True when the history is long enough to warrant compaction., Replace the old portion of *history* with a single compaction note. The…, True when the harness should use head_file instead of read_file. When a file is…, Trim a step result so sub-agent outputs stay within ~1-2k tokens. The Anthropic…, Manages context window state for a single agent run. The Brain (LLM) stays…, Return a copy of *observations* with old tool outputs truncated. JetBrains… (+13 more)

### Community 253 - "SparkProvider"
Cohesion: 0.07
Nodes (21): get_spark_provider(), NotarizeResult, Any, agent/spark_provider.py — SPARK API Integration Inspired by SPARK API (spark-…, Return True if SPARK API key is set., Register this agent on the SPARK network. If *bsv_address* is not provided,…, Notarize content hash on the BSV blockchain. Args: content: String or bytes to…, Verify a hash against the BSV blockchain. Args: content_hash: SHA-256 hash to… (+13 more)

### Community 254 - "MCPUnavailableError"
Cohesion: 0.05
Nodes (55): MCPUnavailableError, agent/mcp_client.py — Async MCP client for the mcp-server Docker container.…, Raised when the MCP server is unreachable or the circuit is open., E2BSandboxSession, maybe_attach_e2b(), Any, services/e2b_sandbox.py — E2B Firecracker micro-VM sandbox session. Implements…, Create the sandbox. Raises :class:`MCPUnavailableError` on failure. (+47 more)

### Community 255 - "openclaw_gateway.py"
Cohesion: 0.15
Nodes (20): openclaw_websocket(), websocket, WebSocket endpoint for iOS / mobile web UI pairing + command routing., _cmd_chat(), _cmd_freebuff(), _cmd_list_files(), _cmd_read_file(), _cmd_status() (+12 more)

### Community 257 - "traffic_director.py"
Cohesion: 0.11
Nodes (19): provider_weight(), Return the operator-configured share weight for *provider*. Reads…, Return the configured traffic-distribution strategy (lower-cased). Reads…, routing_strategy(), active_strategy(), provider_id_of(), Any, Adaptive traffic distribution across LLM providers. The router… (+11 more)

### Community 258 - "chat_handlers.py"
Cohesion: 0.12
Nodes (31): _apply_chat_defaults(), _emit_safely(), _extract_exact_output(), _filter_fragment(), _filter_openai_sse_line(), handle_ollama_native_chat(), handle_openai_chat_completions(), _inject_default_system_prompt() (+23 more)

### Community 259 - "test_rate_limiter.py"
Cohesion: 0.10
Nodes (27): pace(), Proactive rate-limit throttling for LLM providers — two complementary layers.…, Rate limiter using virtual scheduling (GCRA-style): each caller atomically…, Block until this caller's reserved slot arrives, or *max_wait* elapses. Returns…, Proactively pace a request to *provider_id*. No-op (returns 0.0 immediately)…, Clear all token-bucket state (tests only). Does not touch the header tracker's…, reset(), TokenBucket (+19 more)

### Community 260 - "Screens"
Cohesion: 0.06
Nodes (33): 🛡 Admin — users & access, 🤖 Agents — autonomous team, Architecture, security, license, Autonomous AI Agency, 💬 Chat — unified assistant, 🏢 Company — operating context, Contributing, 📊 Dashboard — system overview (+25 more)

### Community 261 - "provider_max_rpm"
Cohesion: 0.13
Nodes (19): provider_max_parallel(), provider_max_rpm(), provider_max_tpm(), _provider_positive_float(), Shared parse/validate for the numeric per-provider traffic budgets. Returns…, Return the operator-configured requests/min cap for *provider*, or None if…, Return the operator-configured tokens/min cap for *provider*. Reads…, Return the operator-configured in-flight request cap for *provider*. Reads… (+11 more)

### Community 262 - "test_kimi_bridge_server.py"
Cohesion: 0.06
Nodes (36): chat_completions(), ChatCompletionRequest, _content_to_str(), _ContentPart, health(), lifespan(), list_models(), _Message (+28 more)

### Community 263 - "test_brain_failover.py"
Cohesion: 0.11
Nodes (30): _make_manager(), tests/test_brain_failover.py — Universal multi-provider brain failover tests.…, Status snapshot doesn't leak API keys., Make a fresh manager (bypasses the singleton for isolation)., No API keys set → no providers in the registry., test_429_exponential_backoff(), test_circuit_recovers_after_cooldown(), test_max_attempts() (+22 more)

### Community 264 - "test_microagents.py"
Cohesion: 0.15
Nodes (29): load_microagents(), match_microagents(), Microagent, microagents_block(), _parse_file(), Path, OpenHands-compatible microagents: keyword-triggered repo knowledge. OpenHands…, Parse one microagent markdown file; None when it isn't one. (+21 more)

### Community 265 - "Security Analysis — local-llm-server"
Cohesion: 0.06
Nodes (30): Fable 5 — Read-Only Audit & Skill-Distillation Notes, Finding A — `list_for_user` Mongo query diverges from the `_can_read` policy, Finding B — `/api/secrets` router is mounted with no authentication dependency, How I would make the smaller model behave like me, Minor, non-security, Part 0 — A caveat on how this task started, Part 1 — The audit, Part 2 — Handing frontier skills to a smaller model (+22 more)

### Community 266 - "brain_failover.py"
Cohesion: 0.05
Nodes (66): auto_disable(), _billing_signals(), describe(), disabled_provider_ids(), is_unfixable(), packages/llm/disabled.py — bridge to the durable provider on/off switch. The…, Provider ids currently switched off. Empty when the store is unreachable., Persist a provider as disabled, through the store that already owns it. (+58 more)

### Community 267 - "Langfuse Observability Guide"
Cohesion: 0.06
Nodes (32): 1. Create a Langfuse project, 2. Configure credentials, 3. Optional tuning, 4. Verify the connection, Commercial savings metrics, Cost analysis dashboard, Cost dashboard, Customising Commercial Reference Prices (+24 more)

### Community 268 - "v3_models.py"
Cohesion: 0.15
Nodes (31): _get_current_user, UserResponse, delete_model(), get_activity(), get_model(), _get_ollama_model_info(), _get_ollama_models(), get_stats() (+23 more)

### Community 269 - "DockerAgentAdapter"
Cohesion: 0.17
Nodes (10): DockerAgentAdapter, Any, TaskResult, TaskSpec, Adapter that runs agent tasks inside isolated Docker containers., Check whether Docker is available and report the adapter's runtime health.…, asyncio, test_docker_binary_missing() (+2 more)

### Community 270 - "test_failover_silent_exhaustion.py"
Cohesion: 0.10
Nodes (23): Paid-tier providers admitted to the chain and not yet attempted. Empty when the…, _untried_paid(), True when the provider can accept traffic right now., _FM, _P, Regression tests for a chain that fails silently. From a real incident:…, Reserve logic must never break the chain it is meant to protect., The incident case: providers ran, none reported a reason. (+15 more)

### Community 271 - "Feature Guide"
Cohesion: 0.11
Nodes (19): 10. Langfuse Observability, 11. Coding Agent API, 12. Browser Admin UI, 13. Telegram Remote Control Bot, 14. Tunnel — Permanent Static URL via ngrok, 15. CORS Support, 16. Streaming Support, 17. Workspace Isolation (+11 more)

### Community 272 - "admin_gui.py"
Cohesion: 0.11
Nodes (15): Browser admin UI for login, service control, key management, and diagnostics., Update or append a KEY=value line in the .env file., register_admin_gui(), _save_env_var(), filter_output(), get_output_filter(), get_savings_summary(), Any (+7 more)

### Community 273 - "TestDiagCommand"
Cohesion: 0.09
Nodes (12): TestCase, _GlobalsRestorer, tests/test_telegram_diag.py Regression test for the new ``/diag`` (admin)…, Drive _process_update with a /diag message and return the response. Restores…, The Operator Charter §"Telegram bot" silent-drop path MUST surface a…, Once we've warned once, subsequent silent drops must NOT spam the log., Snapshot/restore tb globals + TELEGRAM_POLLER_DISABLED env var., ``/diag`` behaviour under admin + non-admin + empty-allowlist states. (+4 more)

### Community 274 - "run_regression"
Cohesion: 0.14
Nodes (12): Agents: list, view status., Schedules: create, list., Chat: send message, view sessions, delete session, agent mode toggle., GitHub integration: status, repos., Activation: status, users., Run the full regression suite for a given viewport., run_regression(), TestActivation (+4 more)

### Community 275 - "agency.py"
Cohesion: 0.08
Nodes (24): AgencyCycleResult, AgentDirective, _build_ceo_prompt(), _build_quick_note_instruction(), _close_github_issue(), _collect_recent_git_context(), _fetch_github_quick_notes(), _gh_repo() (+16 more)

### Community 276 - "SpecEntry"
Cohesion: 0.11
Nodes (24): build_block(), _flag(), _int_env(), Path, agent/harness_spec.py — the Continual Harness: a persistent, cited spec.…, Absolute path of the harness spec for a workspace., Parse existing entries. Never raises — a broken file yields no entries. With…, Rewrite the spec file, preserving any non-entry (hand-written) lines. (+16 more)

### Community 277 - "StuckDetector"
Cohesion: 0.13
Nodes (24): Any, Stuck detection for the agent tool loop — adapted from OpenHands. OpenHands…, Canonical identity of one observation, ignoring incidental fields., Consecutive repetitions required before a pattern counts as stuck., Detects repeating patterns in a step's observation history., Return a human-readable reason when the loop looks stuck, else None., _signature(), StuckDetector (+16 more)

### Community 278 - "High-Agency Frontend Skill"
Cohesion: 0.06
Nodes (30): 10. FINAL PRE-FLIGHT CHECK, 1. ACTIVE BASELINE CONFIGURATION, 2. DEFAULT ARCHITECTURE & CONVENTIONS, 3. DESIGN ENGINEERING DIRECTIVES (Bias Correction), 4. CREATIVE PROACTIVITY (Anti-Slop Implementation), 5. PERFORMANCE GUARDRAILS, 6. TECHNICAL REFERENCE (Dial Definitions), 7. AI TELLS (Forbidden Patterns) (+22 more)

### Community 279 - "Quick-Note GitHub Issues Processing - Session Summary"
Cohesion: 0.06
Nodes (30): 1. Stop-Slop Quality Filter (Issue #229), 2. ECC Integration Study (Issue #266 & #230), ✅ Analysis & Comments (16 items), Architecture Alignment, Branch: `docs/ecc-adoption-analysis`, Branch: `feat/stop-slop-quality-filter`, Deliverables, ECC Patterns Adopted (+22 more)

### Community 280 - "v3_auth.py"
Cohesion: 0.12
Nodes (29): _get_admin_email(), _get_admin_name(), _get_admin_secret(), login(), LoginRequest, LoginResponse, BaseModel, get (+21 more)

### Community 281 - "RateLimitTracker"
Cohesion: 0.10
Nodes (13): get_tracker(), RateLimitTracker, Sleep if remaining quota for *provider_id* is critically low. Returns the…, Snapshot of all tracked provider quotas. Safe to call from any context., Reset all state (primarily for tests)., Return the process-singleton RateLimitTracker., In-memory tracker for per-provider rate-limit state., asyncio (+5 more)

### Community 282 - "scheduler.py"
Cohesion: 0.20
Nodes (9): _age_seconds(), agent/scheduler.py — Scheduled Agent Jobs Cron-based job scheduler. Each job…, The one retention policy for unfired one-shots, read from its owner.…, Durably remove one unfired run-once row and its in-memory mirror. Returns True…, Force-dedup and clean stale schedules from both the durable store and in-memory…, Seconds since ``created_at``. Unparseable or missing reads as brand new. Erring…, The most common ``name`` prefixes, to name the source of a backlog., _run_once_max_age_sec() (+1 more)

### Community 283 - "TestRecordUsageAndStats"
Cohesion: 0.06
Nodes (6): Tests for packages/ai/cost_tracker.py — per-model cost attribution. Covers: -…, TestClearStats, TestCostForTokens, TestEnvOverrides, TestGetCostTable, TestRecordUsageAndStats

### Community 284 - "test_purge_backlog.py"
Cohesion: 0.09
Nodes (22): auth_headers(), FakeTaskStore, MonkeyPatch, Task, tests/test_purge_backlog.py — 2026-07-03 crash-loop remediation. Covers: - POST…, The per-minute tick must requeue at most ONE blocked task, keep its…, Drive _maybe_boot_purge with fakes; return (purged, marker_writes). ``core``…, A failed purge must NOT record the nonce — it retries next boot. (+14 more)

### Community 285 - "test_autonomy_gate.py"
Cohesion: 0.11
Nodes (28): agent_branch_name(), assert_agent_can_merge(), assert_agent_can_write(), AutonomyViolation, is_protected_branch(), _protected_branches(), Autonomy gate — enforce 'agents propose via PR, humans merge'. The agency can…, Raised when an agent-initiated action would exceed the propose-PR policy. (+20 more)

### Community 286 - "tests/test_browser.py"
Cohesion: 0.10
Nodes (18): BrowserAction, _env_true(), _not_started(), PageState, Any, agent/browser.py — Browser Automation Controls a real browser via Playwright so…, Evaluate a JavaScript expression in the page context., Return a summary of the current page state. (+10 more)

### Community 287 - "proxy.py"
Cohesion: 0.02
Nodes (180): Any, Return recent commits with agent attribution trailers parsed out., free_nvidia_models(), Return the curated list of free NVIDIA NIM models FreeBuff may use., List the free NVIDIA NIM models a user may pick (e.g. via Telegram)., True when *model* is in the curated free NVIDIA NIM set., get_sam(), agent/sam.py — SAM Voice Agent (System Autonomy Manager) SAM is the voice-… (+172 more)

### Community 288 - "test_terminal.py"
Cohesion: 0.10
Nodes (18): _is_command_not_found(), _powershell_quote(), Any, agent/terminal.py — Terminal Panel Reads the rendered terminal output buffer —…, Try to read the pane buffer via tmux capture-pane., Return a minimal snapshot with terminal dimensions only., Capture the current terminal state. Never raises., Run *cmd* and capture its full output (stdout + stderr). Returns a dict with… (+10 more)

### Community 289 - "test_dashboard_cache.py"
Cohesion: 0.15
Nodes (16): _cached(), _fast_count(), Single-flight TTL cache. Concurrent callers wait for the first producer., Count without materialising rows — prefers estimated_document_count., _clear_cache(), _CollWithEstimate, _CollWithoutEstimate, _ensure_mongo_fast_count() (+8 more)

### Community 290 - "SeoCheckDefinition"
Cohesion: 0.11
Nodes (13): Return the full SEO/GEO/AIO check catalog. Static metadata only, but gated…, seo_check_catalog(), Static definition of a single audit check (catalog entry)., SeoCheckDefinition, auto_fixable_checks(), _c(), get_check(), list_checks() (+5 more)

### Community 291 - "mcp_dispatch"
Cohesion: 0.13
Nodes (22): guard(), identity_from_headers(), Any, Build an AgentIdentity from the caller's ``X-Agent-*`` headers. Absent headers…, Evaluate *tool* before it runs. Returns ``(allowed, message, decision)``.…, Wall-clock timer for the audit row's ``duration_ms``., Governance posture, for the ``/health`` payload. Surfaced on the health…, status() (+14 more)

### Community 292 - "_resolve_brain_provider"
Cohesion: 0.06
Nodes (36): Resolve the LLM endpoint for agent execution (module-level, #522 failover).…, _resolve_brain_provider(), Critical failover-safety test: if every free provider's base URL is excluded…, When the ONLY configured provider is a paid one (e.g. operator set…, When only Anthropic is configured AND allow_paid=False (default), the resolver…, When AGENT_LLM_BASE_URL is set, the brain resolver must return that endpoint —…, When a free cloud provider (NVIDIA NIM, etc.) is configured, the brain resolver…, _run() (+28 more)

### Community 293 - "switch_brain.py"
Cohesion: 0.16
Nodes (29): detect_ollama_models(), dim(), fail(), get_auth_headers(), get_brain_config(), get_ngrok_tunnel_url(), header(), info() (+21 more)

### Community 294 - "test_portfolio_intelligence.py"
Cohesion: 0.08
Nodes (11): asyncio, Tests for agents/portfolio_intelligence.py — autonomous signal → initiative.…, DEFAULT_REPO was hardcoded to the stale pre-rename repo name…, fetch_research_alerts used asyncio.run() to await TrendWatcher().fetch(), which…, The exact scenario that crashed before the fix: called from code that is itself…, End-to-end: fetch_research_alerts() itself must not raise the 'asyncio.run()…, TestBuild, TestDefaultRepoFollowUpFix (+3 more)

### Community 295 - "test_rag_context.py"
Cohesion: 0.12
Nodes (23): RAGContextBuilder, Retrieve, decay, and compress context to fit a configurable token budget.…, Tests for agent/rag_context.py — Advanced RAG context management layer. Imports…, test_builder_doc_budget_fraction(), test_builder_docs_dropped_count(), test_builder_empty_both(), test_builder_empty_documents(), test_builder_empty_history() (+15 more)

### Community 296 - "_P"
Cohesion: 0.19
Nodes (8): _ids(), _P, A provider with no latency sample must be able to earn one., The safety invariant: a shuffle may not promote a paid provider ahead of the…, With every provider idle a stable sort would send the whole burst to the first…, No explicit weights: the provider that has spent less of its minute should be…, Minimal provider stand-in — the director only needs ``provider_id``., TestOrdering

### Community 297 - "AppShell.jsx"
Cohesion: 0.13
Nodes (10): getAccountLifecycle(), MOBILE_MORE, MOBILE_PRIMARY, NAV_ITEMS, EphemeralBanner(), formatRemaining(), APP_LABEL, APP_NAME (+2 more)

### Community 299 - "test_ceo_router.py"
Cohesion: 0.16
Nodes (24): build_ceo_router(), Any, APIRouter, _make_app(), FastAPI, tests/test_ceo_router.py — auth and behaviour for /api/ceo/*. Follows the…, The happy path — the branch that actually spends provider budget., Filtering after a LIMIT silently under-reported matching goals. (+16 more)

### Community 300 - "Configuration Reference"
Cohesion: 0.07
Nodes (29): Agent governance — identity, policy, approvals, audit, sandboxes, Agent Models, Anthropic API Compatibility / Claude Code, Authentication and Keys, Claude Code setup, Configuration Reference, Continual Harness, Dashboard (React UI on :3000, API on :8001) (+21 more)

### Community 301 - "test_pr923_fixes.py"
Cohesion: 0.09
Nodes (27): nuclear_cleanup(), Directly delete ALL stale jobs from the DB collection. More aggressive than…, FakeDB, asyncio, tests/test_pr923_fixes.py — regression tests for PR #923 (5 production issues).…, nuclear_cleanup should keep newest job per name, delete duplicates., nuclear_cleanup should gracefully handle a DB without a schedules collection., reconcile_stranded_tasks source code must include a FAILED-task re-queue pass.… (+19 more)

### Community 302 - "SteeringInjector"
Cohesion: 0.11
Nodes (10): Any, Inject steering instructions into the message list. Args: messages: The…, Inject steering into an OpenAI chat payload dict. Modifies and returns the…, Build the steering instruction text based on format., Build steering as natural-language quality instructions., Build steering as ChatML-formatted tokens., Build steering as Nemotron-specific steering tags., Inject steering tokens into prompts for quality-biased generation. Supports… (+2 more)

### Community 303 - "test_claude_setup_audit.py"
Cohesion: 0.16
Nodes (23): AuditReport, _check_agents_config(), _check_claude_md_sections(), _check_hooks(), _check_skills(), _check_state(), CheckResult, main() (+15 more)

### Community 304 - "test_internal_agent_did_work.py"
Cohesion: 0.12
Nodes (28): _compute_did_work(), tests/test_internal_agent_did_work.py — step-success-ratio gate tests. Tests…, judge_verdict=BLOCKED → always FAILURE, even with 10/10 applied., judge_verdict=BLOCKED → always FAILURE, even with a long report., Even with unique_files, 1/22 applied → FAILURE (steps_ok gate)., With 9/10 applied + unique_files → SUCCESS., Replicate the did_work logic from internal_agent.py:509-533., 1/22 applied (4.5%) → should be FAILURE (the bug case). (+20 more)

### Community 305 - "agents/api.py"
Cohesion: 0.14
Nodes (31): _apply_activity_status(), create_agent(), delete_agent(), get_agent(), _get_user(), list_agents(), list_runtime_agents(), Any (+23 more)

### Community 306 - "WebsiteScanner"
Cohesion: 0.04
Nodes (55): main(), Returns (url, ok, summary)., _scan_one(), _is_safe_url(), _looks_like_bot_challenge(), Any, BeautifulSoup, Replicates builtwith.builtwith() data-driven logic natively using the… (+47 more)

### Community 307 - "Python Dependencies (`requirements.txt`)"
Cohesion: 0.07
Nodes (27): AI / LLM, AI Tooling, Browser Automation, Cloud / Infrastructure, Core Web Framework, Data Processing, DEP-001 [HIGH] — No Python Lockfile, DEP-002 [HIGH] — `playwright` as a Runtime Dependency (+19 more)

### Community 308 - "Technical Debt Register — local-llm-server"
Cohesion: 0.07
Nodes (27): Category 10 — Patch Files in Root, Category 1 — God Files, Category 2 — API Key Naming Confusion, Category 3 — Dual App Architecture, Category 4 — Dual Storage Backend, Category 5 — Test File Sprawl, Category 6 — Environment Variable Documentation, Category 7 — Missing Type Annotations (+19 more)

### Community 309 - "NotificationDispatcher"
Cohesion: 0.04
Nodes (61): NotificationDispatcher, Any, Path, service_manager.py — Telegram & Notification Integration Extension Extends the…, Start the Telegram bot. Returns True if started successfully., Signal the bot to stop and wait for graceful shutdown., Run the Telegram bot long-poll loop (inline, not subprocess)., Run the bot with stop-event awareness. (+53 more)

### Community 310 - "test_backend_runtime_bootstrap.py"
Cohesion: 0.11
Nodes (9): anyio, Web lifespan delegates to start_background_services when…, RUN_BACKGROUND_IN_WEB=false: lifespan starts but background services are NOT…, _StubRuntimeManager, _StubRuntimeRegistry, _StubTask, _StubTaskDispatcher, test_backend_lifespan_skips_bg_when_flag_false() (+1 more)

### Community 311 - "CircuitState"
Cohesion: 0.12
Nodes (6): CircuitState, Return health snapshots for all known runtimes., Force an immediate health check of all runtimes and return results., Attempt to start a dead runtime subprocess before re-probing. Uses the local…, Reduce probe frequency for runtimes that have never come online., Start the background polling loop with an immediate initial check.

### Community 312 - "CostAttributor"
Cohesion: 0.10
Nodes (16): CostAttributor, CostReport, get_cost_attributor(), Any, Tracks and attributes LLM costs per model, phase, and provider. Usage:: attr =…, Record a single LLM call's usage., Batch record multiple usage entries. Returns number recorded., Estimate USD cost for a given model and token count. Looks up the per-model… (+8 more)

### Community 313 - "test_crispy_burn_in.py"
Cohesion: 0.07
Nodes (27): burn_in(), tests/test_crispy_burn_in.py — N4 follow-up: burn-in criteria evaluator. Tests…, window_days below 7 → not ready (need at least a week of evidence)., PhaseSequenceError in last_failure_reasons → not ready (workspace isolation…, Non-PhaseSequenceError failures (assertion errors, etc.) don't block promotion…, Exact threshold values meet the criteria (>=, not >)., window_days=None (no runs yet, but total_runs > 0 somehow) is treated as 0 —…, The --json flag lets the workflow (and tests) run offline against a saved… (+19 more)

### Community 314 - "test_llm_router_tpm.py"
Cohesion: 0.15
Nodes (19): _big_request(), _ok(), A per-minute token budget is an input ceiling, not just a sort key. Reproduces…, A conversation comfortably past the metered provider's per-minute budget.…, A 131k window behind a 4k budget is a 4k ceiling., Routing around the low ceiling beats compressing to fit it., Production's case: every reachable provider has a low ceiling. Nothing can be…, No compression tax on requests that already fit. (+11 more)

### Community 315 - "test_schedule_persistence.py"
Cohesion: 0.17
Nodes (14): _FakePersistence, tests/test_schedule_persistence.py — #505 schedules survive restart. Regression…, Populate the store directly so hydration tests don't depend on the timing of…, Regression for the production startup path: services/background.py runs inside…, The sync attach_persistence()/rehydrate() must stay safe even if called from…, In-memory stand-in for ScheduleStore (no Mongo needed in tests)., A disabled job must be registered (paused) on rehydrate so a later…, _seed() (+6 more)

### Community 316 - "TestSchedulerStore"
Cohesion: 0.09
Nodes (10): count() returns 0 for an empty store., count() reflects the number of saved jobs., count() decreases after delete., delete_stale() keeps jobs updated recently., delete_stale() removes jobs with old updated_at., delete_stale() reads SCHEDULER_JOB_RETENTION_DAYS from env., delete_stale() returns 0 when all jobs are recent., Explicit retention_days arg takes precedence over env var. (+2 more)

### Community 317 - "test_skill_registry_boot_refresh.py"
Cohesion: 0.12
Nodes (16): clean_task(), _install(), _NullDispatcher, _NullRuntimeManager, asyncio, Exception, The configured remote skill repos must be fetched without a human trigger.…, Remote skills are optional; a rate limit must not surface as an error. (+8 more)

### Community 318 - "SprintMetrics"
Cohesion: 0.10
Nodes (12): Complete the sprint and record velocity., Calculate current sprint metrics., Velocity and burndown metrics for a sprint., Percentage of story points completed., Points per day needed to complete on time., Whether the sprint is on track to complete., Derive a qualitative health signal from the metrics. - COMPLETE: all points…, SprintMetrics (+4 more)

### Community 319 - "Deploy: FreeBuff Telegram bot (24×7)"
Cohesion: 0.07
Nodes (25): Agents, Environment variables, Free model set, FreeBuff — free-NVIDIA coding agent, `/freebuff <task>`, HTTP API, Running 24×7, Telegram phone control (+17 more)

### Community 320 - "Claude Code + Qwen Local Setup"
Cohesion: 0.07
Nodes (27): 1. Set environment variables, 2. Start Claude Code, 3. Verify model routing, Anthropic SDK (Python), Architecture, "Authentication error" or 401, Claude Code + Qwen Local Setup, Claude Code reports "token limit exceeded" (+19 more)

### Community 321 - "Docker Agent Runtimes Setup"
Cohesion: 0.05
Nodes (41): 1. Register Runtimes, 2. Verify Installation, 3. Access Agents via API, Agent Runtime Setup, Agents not appearing in API responses, Initial Setup, MongoDB Connection, No agents showing after registration (+33 more)

### Community 322 - "OperationalIncident"
Cohesion: 0.24
Nodes (12): _diagnose_and_file(), _file_incident(), _format_incident(), OperationalIncident, One failure mode that recurred often enough to warrant diagnosis., Attach evidence to *incident*, then hand it to the existing intake. The filing…, Register the incident through ``ImprovementLoop.register_external_issue``.…, Build the issue body: what recurred, plus the gathered evidence. (+4 more)

### Community 323 - "generate_context.py"
Cohesion: 0.12
Nodes (26): _build_caller_chain(), _build_context_doc(), _build_grounding_block(), _build_pr_description(), _build_todos_md(), _build_user_message(), _call_claude(), _call_mistral() (+18 more)

### Community 324 - "control_registry.py"
Cohesion: 0.11
Nodes (27): packages/config/control_catalogue.py — the 109 operator-facing controls. The…, coerce(), _coerce_choice(), _coerce_number(), _coerce_toggle(), controls_by_group(), get_control(), Any (+19 more)

### Community 325 - "._connect"
Cohesion: 0.12
Nodes (11): _now(), Connection, Path, Row, Safe getter for sqlite3.Row — Row supports index access but not .get()., Create a session with a caller-supplied session_id (useful for tests and…, Merge *metadata* into the session's metadata dict (in-memory only; not…, Store or clear the resume payload for a paused agent job. (+3 more)

### Community 326 - "resolve_active_brain"
Cohesion: 0.03
Nodes (113): BrainResolution, get_brain_config(), get_brain_config_store(), invalidate_brain_config_cache(), Return the process-wide ``BrainConfigStore`` singleton., Convenience wrapper used by the agent loop + brain resolver., Convenience wrapper used by the admin API endpoints., Clear the singleton's cache (used by tests + brain_policy invalidation). (+105 more)

### Community 327 - "isolated_telegram_config"
Cohesion: 0.11
Nodes (11): isolated_telegram(), isolated_telegram_config(), tests/_telegram_test_utils.py Snapshot/restore helper for ``telegram_bot``…, Pytest fixture alias for ``isolated_telegram_config``. Use this in tests that…, Snapshot+restore ``tb`` globals + ``TELEGRAM_POLLER_DISABLED``. Keyword args…, tests/test_telegram_test_utils.py Self-test suite for…, The helper's ``__exit__`` runs ``if original is _MISSING: if hasattr:…, If a tracked attr is absent under ``tb`` at scope entry, the helper snapshots… (+3 more)

### Community 328 - "test_scheduler_hydration_bounded.py"
Cohesion: 0.09
Nodes (20): _BrokenScheduler, _fake_schedule_store(), _FakeStore, _FastScheduler, _HangingScheduler, _isolate_warmup_overflow(), asyncio, NoReturn (+12 more)

### Community 329 - "webui/frontend/package.json"
Cohesion: 0.07
Nodes (26): @types/react, @types/react-dom, typescript, vite, @vitejs/plugin-react, dependencies, react, react-dom (+18 more)

### Community 330 - "LocalWorkspace"
Cohesion: 0.14
Nodes (15): LocalWorkspace, Path, Manages a local git clone of a GitHub repository. Clones are stored under…, Run a git command. Never uses shell=True., Clone the repo if it doesn't exist; pull if it does., Return the current working-tree diff (staged + unstaged)., Stage files and commit. paths=None stages everything; paths=[] raises., Create and checkout a new branch from base_branch. (+7 more)

### Community 331 - "Performance Analysis — local-llm-server"
Cohesion: 0.08
Nodes (25): 1. Rate Limiter Performance, 2. Ollama Connection Handling, 3. Model Router Performance, 4. Agent Execution Performance, 5. Backend Server Performance, 6. Frontend Performance, 7. Streaming Performance, PERF-001 [HIGH] — Synchronous Lock in Async Context (+17 more)

### Community 332 - "LLM Router — troubleshooting"
Cohesion: 0.08
Nodes (24): Embeddings, LiteLLM compatibility mode, LLM Router — local model guide, LM Studio, LocalAI, Ollama, Preferring local, Registering local models (+16 more)

### Community 333 - "test_unit5_ui_provider_surface.py"
Cohesion: 0.10
Nodes (15): tests/test_unit5_ui_provider_surface.py — UNIT 5 regression tests. Verifies…, The component must call ``providerLabel(p)`` rather than indexing a 4-entry…, The dropdown shows a [free]/[paid]/[local] tier tag so the operator can tell…, The <option> tag uses providerLabel(p), not PROVIDER_LABELS[]., The operator must be able to see what a key really serves. ``candidates`` is…, The GET endpoint response must list every BrainProvider Literal entry. Before…, Providers that were filtered out before UNIT 5 are now present. ``mistral``,…, A known paid provider is reported as tier=paid (was filtered before). (+7 more)

### Community 334 - "keepalive.py"
Cohesion: 0.15
Nodes (25): _check_ollama(), _check_render(), _default_ollama_base(), _default_render_url(), _env_bool(), _loaded_ollama_prefixes(), _log(), _log_path() (+17 more)

### Community 335 - "monitor_lib.py"
Cohesion: 0.17
Nodes (25): colibri_dir(), download_log_path(), download_status(), DownloadStatus, _heartbeat_to_file(), is_process_alive(), model_dir(), monitor_log_path() (+17 more)

### Community 336 - "analyze_page"
Cohesion: 0.16
Nodes (9): analyze_page(), BeautifulSoup, Run every page-scoped check against one HTML document (no network). Returns a…, _visible_text(), codes(), TestCleanPage, TestNewChecks, TestSpecificChecks (+1 more)

### Community 337 - "TrainingSample"
Cohesion: 0.10
Nodes (13): Any, Add a step result. Returns the sample if accepted, None if filtered out., Bulk-add samples from an agent session's step results. Each step result with…, Return samples filtered by minimum reward score., Export samples in Alpaca JSONL format. Returns the path to the exported file., Export samples in ShareGPT JSONL format. Returns the path to the exported file., Export all samples as a structured JSON array. Returns the path to the exported…, Return pipeline statistics. (+5 more)

### Community 338 - "APIClient"
Cohesion: 0.17
Nodes (4): APIClient, Company Graph: create, scan website, view graph, onboarding, delete., Direct API calls for fast test setup and teardown., TestCompany

### Community 339 - "test_v3_auth.py"
Cohesion: 0.17
Nodes (25): _configured_v3_email(), _configured_v3_password(), asyncio, skip, TestClient, Tests for v3 API authentication., Test login endpoint returns valid tokens., Test login with invalid credentials. (+17 more)

### Community 340 - "TestWorkflow"
Cohesion: 0.08
Nodes (6): Tests for agents/workflow_engine.py — SuperClaude Workflow Engine. Uses…, Tests for WorkflowEngine., Tests for Task dataclass., TestTask, TestWorkflow, TestWorkflowEngine

### Community 341 - "HarnessEnrichment"
Cohesion: 0.11
Nodes (13): get_enrichment(), HarnessEnrichment, invalidate_enrichment_cache(), Any, agent/harness_enrichment.py — Automatic Harness Enrichment for Agent Prompts…, Build a compact catalog of available runtime skills. Discovers from…, Standing instructions from the Continual Harness spec. Deliberately uncached:…, Build the complete enrichment block (tools + skills). Returns empty string when… (+5 more)

### Community 342 - ".snapshot"
Cohesion: 0.15
Nodes (8): _now(), Any, Path, agent/memory.py — Session Memory Snapshots Persists agent session state to disk…, Persist *state* to disk under *session_id*. Returns the file path., Load a saved snapshot. Returns the state dict or *None* if absent., Return metadata for all saved snapshots (session_id, saved_at, path)., Delete a snapshot. Returns *True* if the file existed.

### Community 343 - "test_sam_voice.py"
Cohesion: 0.10
Nodes (19): tests/test_sam_voice.py — Integration tests for SAM voice agent. Tests the SAM…, SAM's system prompt must address the user as Commander., SAM agent with all external dependencies mocked., get_sam() must return the same instance., Empty input must return a prompt to repeat., Whitespace-only input must be treated as empty., Fallback must return operational status when LLM is down., Fallback must acknowledge task requests. (+11 more)

### Community 344 - "ScheduleStore"
Cohesion: 0.07
Nodes (29): _backend(), _json_default(), Any, agent/schedule_store.py — durable persistence for scheduled agent jobs. Fixes…, Return all persisted schedule docs (for boot rehydration)., Persist (insert or update) a single schedule by job_id., Delete a persisted schedule., Fallback JSON encoder for schedule docs (datetimes, sets, etc.). (+21 more)

### Community 345 - "_valid_login_state"
Cohesion: 0.24
Nodes (15): Return True if a fetched oauth_states doc is a valid, unexpired login state., _valid_login_state(), _doc(), Regression tests for social-login (GitHub & Google) OAuth state handling. Bug…, MongoDB/motor returns naive UTC datetimes. Subtracting a naive datetime from an…, The login handlers must persist state via _store_login_state, not the session…, test_expired_state_rejected(), test_just_within_window_accepted() (+7 more)

### Community 346 - "dependencies"
Cohesion: 0.08
Nodes (25): axios, fast-uri, dependencies, axios, fast-uri, livekit-client, lucide-react, react (+17 more)

### Community 347 - "reset_store"
Cohesion: 0.11
Nodes (23): Reset the store singleton (used in tests). Also resets the motor client…, reset_store(), tests/test_motor_event_loop_isolation.py — regression test for the flaky…, ``reset_store()`` must clear ``db.mongo_store._client`` and ``_db``, not just…, ``reset_store()`` must also clear the ``db._store`` wrapper (the original…, The ``client`` fixture in conftest.py must call ``reset_store()`` before…, After ``reset_store()``, the next ``MongoStore._get_db()`` call must create a…, test_client_fixture_calls_reset_store_before_lifespan() (+15 more)

### Community 348 - "Session Handoff — 2026-06-15"
Cohesion: 0.08
Nodes (24): Context the next session will need, Critical environment variables, Files changed today (for code archaeology), How to resume, Key files to know, Key labels, P0 — Add a regression test for the draft-PR safety guards, P1 — Watch Run 27481814863 for issue #504 and verify end-to-end (+16 more)

### Community 349 - "TASK 4 — End-to-end approval-gate test"
Cohesion: 0.08
Nodes (24): 3.1 — Confirm env vars on the **web** service, 3.2 — Confirm single-poller guard on the **worker**, 3.3 — Verify the bot responds (human-in-the-loop), 3.4 — TASK 3 acceptance, 4.1 — Acquire an admin session, 4.2 — Trigger an outward-facing workflow run, 4.3 — Watch the run until it pauses, 4.4 — Confirm the Telegram message arrived (+16 more)

### Community 350 - "Any"
Cohesion: 0.15
Nodes (3): Any, field_validator, Coerce unrecognised system_type values to 'custom' so the model never crashes…

### Community 351 - "DailyDigestAggregatorTests"
Cohesion: 0.19
Nodes (5): DailyDigestAggregatorTests, _FakeOrchestrator, FakeRun, Forces truncation by lowering _TRUNCATE_THRESHOLD for the duration of the test…, If a custom orchestrator object is passed without list_runs, the aggregator…

### Community 352 - "ClaudeCodeAdapter"
Cohesion: 0.14
Nodes (20): ClaudeCodeAdapter, json_safe(), Any, TaskResult, TaskSpec, Adapter for Claude Code CLI — FIRST CLASS autonomous coding runtime., adapter(), asyncio (+12 more)

### Community 353 - "AgentMessageBus"
Cohesion: 0.15
Nodes (9): AgentMessageBus, get_agent_bus(), Remove a subscription., Return all topics that have history., Return the module-level AgentMessageBus singleton., Pub/sub message bus for inter-agent communication. Agents subscribe to topics…, Decorator: subscribe a callback to a topic pattern. Supports ``*`` (single…, asyncio (+1 more)

### Community 354 - "TemporalContextGraph"
Cohesion: 0.12
Nodes (14): demo_agent_tracking(), datetime, Temporal context graph inspired by Graphiti…, Get history of an entity between two times, Get current state of an entity (most recent fact), Query facts with pattern matching, Get source (provenance) of a specific fact, A fact at a specific point in time (+6 more)

### Community 355 - "test_telegram_approval_e2e.py"
Cohesion: 0.13
Nodes (24): admin_jwt(), _approve_execution_via_rest(), _delete_task(), _extract_admin_token(), _login_admin(), _looks_like_admin_token(), _poll_task_execution_approved(), Any (+16 more)

### Community 356 - "_get"
Cohesion: 0.12
Nodes (9): _get(), Contract tests for the provider on/off endpoints. ``GET /api/brain/providers``…, Silently storing a typo'd id would leave a switch nothing can turn back on., The operator has to know WHY before deciding to switch it back on. The raw…, The response reaches the browser — a leaked key would be a disclosure., The switch has to reach the dispatcher, not just the listing., TestDisabledReasonIsReadableNextToTheSwitch, TestListing (+1 more)

### Community 357 - "test_daily_automation_2026_08_03.py"
Cohesion: 0.11
Nodes (14): _load_yaml(), tests/test_daily_automation_2026_08_03.py — Daily automation (2026-08-03).…, brain_config.py anthropic candidates must exactly match models.yaml (order and…, brain_config.py aerolink candidates must exactly match models.yaml (order and…, test_aerolink_candidates_match_yaml(), test_anthropic_candidates_match_yaml(), test_yaml_aerolink_candidates_contains_opus_5(), test_yaml_aerolink_judge_is_opus_5() (+6 more)

### Community 358 - "TestClassifyPlainText"
Cohesion: 0.08
Nodes (6): tests/test_inbound_router.py Pytest coverage for…, The 3500-char default matches the design recommendation; below the delivered…, TestBigPasteThreshold, TestClassifyPlainText, TestSanitizePasteForPreview, TestSavePaste

### Community 359 - "test_service_token.py"
Cohesion: 0.08
Nodes (19): tests/test_service_token.py — N5 acceptance: service-token auth surface. Tests…, Near-miss tokens must not pass (no prefix-match, no fuzzy match)., After verification, the module must NOT hold the plaintext token — only the…, The token plaintext must NEVER appear in logs. Capture every log record emitted…, The module must use hmac.compare_digest (not ==) for the comparison — timing…, The service token must only gate a narrow allowlist of endpoints — not all of…, When SERVICE_TOKEN is rotated in the env, the new token must verify (within the…, Load services.service_token fresh in each test so env-var changes take effect. (+11 more)

### Community 360 - "CompanyAgencyService"
Cohesion: 0.11
Nodes (13): CompanyAgencyService, Any, SpecialistFamily, Orchestrates specialist activation, runtime startup, and 24x7 scheduling for a…, Return the best available runtime for a specialist family. Checks available…, Return the ordered runtime preferences for a specialist family., Deactivate a company's AI agency. Stops all company-specific schedules and…, Get the current agency health status for a company. (+5 more)

### Community 361 - "Findings"
Cohesion: 0.08
Nodes (23): E2E Tests, Findings, Immediate (Current Sprint), Integration Tests, Live/External Tests (skipped in standard CI), Missing Test Areas, Sprint 1, Sprint 2 (+15 more)

### Community 362 - "Local AI Stack with Docker"
Cohesion: 0.08
Nodes (23): 1. Clone and configure, 2. Start the stack (GPU), 3. Start the stack (CPU only), 4. Pull models (first run), 5. Access services, CPU Only, Data Persistence, Default (GPU) (+15 more)

### Community 363 - "Traffic Distribution Across Providers"
Cohesion: 0.14
Nodes (14): A worked example, Adding capacity: multi-key rotation, Attribution, Configuration, Failure behaviour, Observability, Pre-call budget checks, Provider ids contain dashes (+6 more)

### Community 364 - "Implementation Prompt: Rich TaskBoard + Agile Sprint Integration"
Cohesion: 0.08
Nodes (23): 1. Task model extensions (`tasks/models.py`), 2. New task endpoint (`tasks/api.py`), 3. Agile REST endpoints (`backend/server.py`), 4. TaskBoardScreen upgrade (`frontend/src/v5/screens/TaskBoardScreen.jsx`), 4a. "Needs Clarification" 7th column, 4b. Right-side detail panel, 4c. Sprint view mode toggle, 4d. Create-task modal enhancements (+15 more)

### Community 365 - "Telegram Bot Setup"
Cohesion: 0.08
Nodes (24): Admin commands (immediate, no confirmation), Admin commands with approval required, Approval Workflow, Authorization Model, Command Reference, Debugging message delivery, Debugging proxy connection failures, Linux (systemd) (+16 more)

### Community 366 - "SchedulesPage.js"
Cohesion: 0.13
Nodes (16): createSchedule(), pauseSchedule(), resumeSchedule(), triggerSchedule(), C, FREQ_OPTS, FREQ_TO_CRON, NewScheduleForm() (+8 more)

### Community 367 - "video_transcript.py"
Cohesion: 0.12
Nodes (23): caption_tracks(), extract_player_response(), fetch_transcript(), _get(), is_video_url(), parse_json3(), parse_timedtext_xml(), Extract a usable text transcript from a video URL, without an API key. Why this… (+15 more)

### Community 368 - "PrioritizedTask"
Cohesion: 0.12
Nodes (12): IntEnum, Queue, PrioritizedTask, Priority, Any, Start the worker pool., Submit a task to the queue. Returns True if accepted, False if rejected due to…, Subscribe to progress events for a specific task. Returns an asyncio.Queue that… (+4 more)

### Community 369 - "TestRouterIntegration"
Cohesion: 0.31
Nodes (6): anyio, The behaviour this whole change exists for: once the first free provider has…, No strategy and no budgets configured — behaviour is unchanged., The director must see the provider round-trip, not the round trip plus JSON…, With nowhere to route, skipping would turn a slow request into a failed one —…, TestRouterIntegration

### Community 370 - "CollectionLike"
Cohesion: 0.12
Nodes (12): get_storage(), packages/storage/factory.py — storage backend factory. Returns the appropriate…, Return the active storage backend. During migration, this delegates to the…, Reset the storage singleton (for tests)., reset_storage(), CollectionLike, Any, Protocol (+4 more)

### Community 371 - "seo_report_pdf.py"
Cohesion: 0.24
Nodes (18): Paragraph, _appendix_full_findings(), _appendix_worst_pages(), _appendix_wsjf_roadmap(), _cell(), _cover_page(), _executive_summary(), _findings_table() (+10 more)

### Community 372 - "test_agency_fix.py"
Cohesion: 0.08
Nodes (23): agency_fix(), tests/test_agency_fix.py — N3 acceptance tests for scripts/agency_fix.py. The…, An edit that produces a syntactically-broken Python file must be rejected —…, An edit that truncates a real code file to a trivial body must be rejected —…, With no issue linked, decline is just an exit-code signal — no API call., When an issue is linked but no GH_PAT/GH_TOKEN is set, the decline fails loudly…, When an issue is linked and the API call succeeds, decline_cleanly returns True…, When the API call itself fails (network error), decline_cleanly returns False… (+15 more)

### Community 373 - "test_output_filter.py"
Cohesion: 0.10
Nodes (19): _enable_filter(), tests/test_output_filter.py — Unit tests for output_filter.py Verifies token…, pytest output with failures should preserve failure details., Deep Python traceback should collapse intermediate frames., When disabled, output should pass through (truncated to max_chars)., Ensure filter is enabled for all tests., Empty or whitespace-only input should pass through unchanged., Unrecognized commands should get generic dedup+truncation. (+11 more)

### Community 374 - "test_workspace_security.py"
Cohesion: 0.10
Nodes (9): TestWorkspacePathDerivation, Security-oriented tests for workspace isolation (Area C4). Covers: - No path…, The hash component should not be reversible to the original ID., Workspace root path should be fully resolved (no . or ..)., TestCleanupIsolation, TestSymlinkAttackPrevention, TestWorkspaceHashing, _hash_component() (+1 more)

### Community 375 - "refine"
Cohesion: 0.15
Nodes (13): _one_line(), propose_entries(), Any, Turn qualifying lessons into candidate entries. A lesson qualifies only when it…, Promote repeated lessons into the spec. Returns the entries added. No-op unless…, Collapse a value to a single trimmed line. Entries are one Markdown list item…, refine(), _lesson() (+5 more)

### Community 376 - "get_skill_bindings"
Cohesion: 0.11
Nodes (23): get_skill(), list_skills(), List all available skills with optional filtering. Returns the skill catalog…, Get a single skill by its ID., build_matrix(), _families(), main(), Any (+15 more)

### Community 377 - "test_phase6_workflow.py"
Cohesion: 0.04
Nodes (73): add_pr_comment(), _find_existing_pr(), get_branch_sha(), get_default_branch(), _headers(), Any, agent/safe_agency.py — Safe GitHub operations for the workflow engine. All…, Create a pull request. Returns the PR object dict. If a PR already exists for… (+65 more)

### Community 378 - "model_discovery.py"
Cohesion: 0.08
Nodes (29): Return the discovered model list for *provider_id*, or ``[]`` if unknown., _served_models(), cached_models(), discover_models(), _fresh_entry(), _models_url(), _parse_ids(), Any (+21 more)

### Community 379 - "Agent Governance Guide"
Cohesion: 0.09
Nodes (23): A tool call is judged twice, Agent Governance Guide, `[]` and absent mean opposite things, API, Approvals, Architecture, Audit trail, Backends (+15 more)

### Community 380 - "The fifteen strategies"
Cohesion: 0.09
Nodes (22): adaptive *(default)*, automatic_failover, Candidate selection, Choosing one, context_length_optimized, cost_optimized, fallback_chain, highest_success_rate (+14 more)

### Community 381 - "fmtErr"
Cohesion: 0.13
Nodes (28): authorizeGithubRepos(), createGithubPR(), deleteGithubToken(), fmtErr(), getGithubStatus, getGithubTree(), getPlatformInfo(), githubStatus() (+20 more)

### Community 382 - "ServiceManager"
Cohesion: 0.13
Nodes (14): get_status(), BaseModel, get, post, Start the FastAPI proxy server., Serve the launcher UI., Get current service status., root() (+6 more)

### Community 383 - "_Cursor"
Cohesion: 0.10
Nodes (7): _Cursor, _PendingCursor, Async iterator wrapping a list of dicts (already decoded from JSON)., Return a sort key that tolerates mixed float/str timestamp values. Some code…, Return a _Cursor (evaluated lazily on first await/iteration)., A cursor that fetches its data lazily on first use., _safe_sort_key()

### Community 384 - "test_all_features.py"
Cohesion: 0.09
Nodes (9): TestActivation, TestActivity, TestApiKeys, TestCompany, TestOnboarding, TestSecrets, TestSetup, TestTasks (+1 more)

### Community 386 - "test_monitor_lib.py"
Cohesion: 0.11
Nodes (8): _isolate_env(), MonkeyPatch, tests/test_monitor_lib.py — unit tests for scripts/monitor_lib.py. Covers the…, Pin all env-overridable paths to tmp_path for hermetic tests., TestAwaitReady, TestIsProcessAlive, TestSuperviseLoopGiveUp, TestSupervisorTick

### Community 387 - "Path"
Cohesion: 0.16
Nodes (6): Path, Old log + done signal + no .incomplete = complete (caller can cleanup the log…, TestDownloadStatus, TestReadPidFile, TestSupervisorStateAtomic, _write_log()

### Community 388 - "test_mostly_failed_steps.py"
Cohesion: 0.12
Nodes (22): _make_result(), _make_step(), tests/test_mostly_failed_steps.py — regression test for the "21/22 failed steps…, A BLOCKED judge verdict should never be success, regardless of steps., When mostly_failed, the output should contain a clear failure summary., 0 steps → no gate (division by zero avoided, total_steps < 4)., 6 failed + 2 applied = 75% failure, 2 applied < 3 → mostly_failed., Build a mock agent result dict (the shape InternalAgentAdapter expects). (+14 more)

### Community 389 - "test_v4_api.py"
Cohesion: 0.12
Nodes (22): auth_headers(), TestClient, tests/test_v4_api.py — Tests for the v4 dashboard API endpoints., Return the test client — reuses conftest client which has bootstrap., Get auth headers by logging in as admin via the admin API., GET /v4/status returns 200 with improvement_loop and self_healing keys., GET /v4/improvements returns 200 with active and resolved lists., GET /v4/tasks returns 200 with tasks array. (+14 more)

### Community 390 - "classify_direct_chat_intent"
Cohesion: 0.13
Nodes (19): classify_direct_chat_intent(), _contains_keyword(), detect_intent(), intent.py — Intent classification for direct chat (answer_only, execute_now,…, Return True if content contains any execution or analysis keyword., Detect the user's intent from message content., Map lower-level intents into conversation-driven action categories. Returns one…, classify_plain_text() (+11 more)

### Community 391 - "._connect"
Cohesion: 0.10
Nodes (10): Any, Connection, Path, Recall a specific memory entry., Auto-load relevant memories based on context. Returns memories prioritized by:…, Get all memories in a specific category., Delete a memory entry., Export all memories for a user (for backup/migration). (+2 more)

### Community 392 - "test_scanner_live.py"
Cohesion: 0.23
Nodes (14): _assert_scan_contract(), asyncio, parametrize, LIVE integration tests for the website scanner — these actually hit the real…, Representative large storefronts that commonly sit behind bot protection. Same…, Directly exercise the BuiltWith fallback against the live builtwith.com.…, The invariants that must hold for any live scan, bot-protected or not., A normal, non-bot-protected site must yield real detections. This is the… (+6 more)

### Community 393 - "CoworkSession"
Cohesion: 0.16
Nodes (3): CoworkSession, A shared AI coding session with multiple human contributors. Manages turn-…, TestCoworkSession

### Community 394 - "Harness"
Cohesion: 0.14
Nodes (16): detect_harness(), Harness, harness_context_limit(), harness_stats(), HarnessProfile, Any, Enum, Detect which AI coding tool is calling the proxy. Checks in priority order: 1.… (+8 more)

### Community 395 - "PriorityTaskQueue"
Cohesion: 0.13
Nodes (8): get_task_queue(), PriorityTaskQueue, Stop the worker pool gracefully., Return queue introspection data for status endpoints., Return the module-level PriorityTaskQueue singleton., Asyncio-based priority queue with backpressure and worker pool. Features: -…, Higher-priority tasks should be processed before lower-priority ones., TestPriorityTaskQueue

### Community 396 - "_process_task_callback"
Cohesion: 0.28
Nodes (15): _process_task_callback(), Handle Approve/Reject inline-button presses for task execution gates. Callback…, _escape_md_v1(), Escape Telegram Markdown-v1 reserved chars in free-text fields. Markdown-v1…, _make_fake_task(), _patch_workflow(), Robustness tests for the Telegram inline-button callback flow., test_approve_success_clears_spinner_and_edits_message() (+7 more)

### Community 397 - "BrainFailoverManager"
Cohesion: 0.10
Nodes (15): BrainFailoverManager, Any, Permit one probe call without claiming the provider succeeded. This is the…, Seconds until the soonest cooling provider is probeable again. ``None`` when no…, True when a provider's cooldown window is wider than any it could legitimately…, Record a provider failure — opens the circuit breaker on threshold., Map a requested model to the provider's equivalent. If the requested model is…, Maximum number of provider attempts before giving up. (+7 more)

### Community 398 - "test_voice.py"
Cohesion: 0.15
Nodes (13): Any, agent/voice.py — Voice Command Interface Hands-free agent interaction: record…, Transcribe raw PCM *audio_bytes* to text., Record then transcribe in one call., Record *duration_s* seconds of audio. Returns raw PCM bytes (int16 LE, 16 kHz…, _stub_result(), TranscriptionResult, Tests for agent/voice.py — Voice Command Interface (stub-mode tests). (+5 more)

### Community 399 - "_resolve_user_github_token"
Cohesion: 0.18
Nodes (17): Return the caller's GitHub token from EITHER place it can be stored. A token…, _resolve_user_github_token(), _FakeCollection, _FakeDB, patch_db(), asyncio, The doctor must find a GitHub token wherever the connect flow stored it.…, A diagnostics lookup must never turn into a 500. (+9 more)

### Community 400 - "V3 API Migration Plan — LLM Relay Platform"
Cohesion: 0.10
Nodes (20): Acceptance Checks, Approach, Auth Flow (v3 JWT-based), Backward Compatibility, Current State Analysis, Data Model Changes, Database/Storage, Files to Create/Modify (+12 more)

### Community 401 - "PortfolioScreen.jsx"
Cohesion: 0.10
Nodes (13): getPortfolioBoard(), refreshPortfolio(), btnStyle, HEALTH, HORIZONS, PortfolioScreen(), SOURCE, STATUS_COLOR (+5 more)

### Community 402 - "allow_paid"
Cohesion: 0.13
Nodes (19): allow_paid(), _fetch_policy(), .github/scripts/provider_policy.py — Read the durable provider policy from the…, Fetch the provider policy from the backend API. Never raises., Return True if paid providers (Anthropic) are allowed by policy., Reset the cached policy (test helper)., reset_cache(), _call_review_llm() (+11 more)

### Community 403 - "TestSelfHealingInfrastructureClassification"
Cohesion: 0.19
Nodes (4): _classify_failure correctly identifies infrastructure errors., MongoDB timeout is an infra error, not a generic timeout., MongoDB 'connection refused' is infra, not generic network., TestSelfHealingInfrastructureClassification

### Community 404 - "system_instruction"
Cohesion: 0.16
Nodes (5): Return a plain-English JSON instruction for a ``response_format`` dict. Returns…, system_instruction(), system_instruction() uses stronger language when strict: true., TestSystemInstructionStrictMode, TestSystemInstruction

### Community 405 - "scripts/doctor.py"
Cohesion: 0.29
Nodes (16): NamedTuple, Check, check_core_deps(), check_env(), check_git(), check_mongo(), check_node(), check_ollama() (+8 more)

### Community 406 - "test_local_controller.py"
Cohesion: 0.17
Nodes (20): _env_defaults(), _fake_http_sequence(), _fake_subprocess_run(), _import_controller(), tests/test_local_controller.py — unit tests for the local GLM-5.2 daemon. These…, The diag output must surface binary/model errors clearly., Pins the v3 fix: after the multi-port preamble probe finds colibri serving a…, Yield a list of (status, body) tuples the daemon will see in order when it… (+12 more)

### Community 407 - "run_trend_analysis"
Cohesion: 0.19
Nodes (13): Tests for trend_analysis.py — last30days-style window over TrendWatcher (issue…, TestRunTrendAnalysis, TestWindow, BaseModel, trend_analysis.py — last30days-style trend analysis (issue #493). Adapts the…, True if the ISO-ish published date falls within the last N days.…, Fetch trends via TrendWatcher, filter to a 30-day window, persist summary., Write trends/trend_summary.md (and a dated copy); return the path. (+5 more)

### Community 408 - "MemoryCategory"
Cohesion: 0.16
Nodes (14): Memory middleware for automatic context injection into AI tool requests. This…, MemoryCategory, MemoryEntry, MemoryScope, Enum, Row, str, Enhanced persistent memory system with auto-loading across AI coding tools.… (+6 more)

### Community 409 - "test_permissions.py"
Cohesion: 0.15
Nodes (15): PermissionAssessment, Any, agent/permissions.py — Adaptive Permission Classifier Reads the session…, Convenience helper — True when the inferred level is read_write or full_access., Analyse *messages* and return a :class:`PermissionAssessment`., _msgs(), Tests for agent/permissions.py — Adaptive Permissions., test_assessment_as_dict() (+7 more)

### Community 410 - "PersistentMemoryStore"
Cohesion: 0.24
Nodes (19): PersistentMemoryStore, Enhanced persistent memory store with auto-loading support. Features: -…, cmd_autoload(), cmd_delete(), cmd_export(), cmd_import(), cmd_list(), cmd_recall() (+11 more)

### Community 411 - "AGENTS.md — Source of Truth for All AI Agents"
Cohesion: 0.04
Nodes (50): 1. Language & Runtime, 2. Async, 3. Data Models, 4. Logging, 5. Error Handling, 6. Security, 7. Comments, 8. File Size (+42 more)

### Community 412 - "Skill: modularity-review"
Cohesion: 0.10
Nodes (19): Acceptance Checks, Applying to This Repo, Further Reading, Modularity Findings Template, Part A: Reviewing Existing Code for Modularity Problems, Part B: Designing New Modular Boundaries, Skill: modularity-review, Step 1 — Map the dependency graph (+11 more)

### Community 413 - "Design Audit"
Cohesion: 0.10
Nodes (19): Code Quality, Color and Surfaces, Component Patterns, Content, Design Audit, Fix Priority, How This Works, Iconography (+11 more)

### Community 414 - "Findings"
Cohesion: 0.10
Nodes (19): API Documentation, Architecture Documentation, DOC-001 [HIGH] — No SECURITY.md, DOC-002 [HIGH] — No CONTRIBUTING.md, DOC-003 [HIGH] — No API.md / OpenAPI Export, DOC-004 [MEDIUM] — README.md is 31KB and Needs Pruning, DOC-005 [MEDIUM] — `REVIEW_AND_FIXES.md` and `AGENCY_CORE_V5_PROGRESS.md` are Unclear, DOC-006 [MEDIUM] — No DEPLOYMENT.md at Root (+11 more)

### Community 415 - "Skill: modularity-review"
Cohesion: 0.10
Nodes (19): Acceptance Checks, Applying to This Repo, Further Reading, Modularity Findings Template, Part A: Reviewing Existing Code for Modularity Problems, Part B: Designing New Modular Boundaries, Skill: modularity-review, Step 1 — Map the dependency graph (+11 more)

### Community 416 - "crispy_client.py"
Cohesion: 0.14
Nodes (18): cmd_approve(), cmd_artifacts(), cmd_build(), cmd_events(), cmd_reject(), cmd_status(), cmd_watch(), _get() (+10 more)

### Community 417 - "4. Troubleshooting"
Cohesion: 0.10
Nodes (19): 1. Which sandbox backend applies where, 2. Container hardening, 3. Supply chain, 4. Troubleshooting, 5. Scaling, Agents suddenly failing after enabling enforcement, An agent is stuck, Applying the overlay to the local stack (+11 more)

### Community 418 - "Docker AI Governance Audit — Final Report"
Cohesion: 0.10
Nodes (20): 1. Executive summary, 2. Architecture review, 3. Risk assessment, 4. Security review, 5. What was implemented, 6. Explicitly not implemented, 7. Remaining recommendations, 8. Future enhancements (+12 more)

### Community 419 - "1. Capability-by-capability"
Cohesion: 0.10
Nodes (19): 0. The finding that shapes everything else, 1.10 Least Privilege, 1.11 Multi-Agent Governance (10 / 100 / 1000 agents), 1.12 Cost Governance, 1.13 Compliance (SOC2 / ISO27001 / GDPR), 1.14 Local Development Experience, 1.1 Agent Identity, 1.2 Tool Governance (+11 more)

### Community 420 - "4. Threats"
Cohesion: 0.10
Nodes (20): 1. What makes this system different from a normal web app, 2. Assets, 3. Trust boundaries, 4. Threats, 5. Why the engine fails open but approvals fail closed, 6. Honest limits, 7. Priority follow-ups, T10 — Supply-chain compromise via base image (+12 more)

### Community 421 - "Dynamic Model Routing"
Cohesion: 0.10
Nodes (20): Architecture, Built-in Claude → local alias table, Configuring fast_response routing, Configuring model preferences, Curl example, Dynamic Model Routing, Fallback execution, Health check and availability filtering (+12 more)

### Community 422 - "test_unit7_catalog_propagation.py"
Cohesion: 0.08
Nodes (24): _nvidia_defaults(), tests/test_unit7_catalog_propagation.py — UNIT 7 regression tests. Verifies…, ``_get_defaults()`` must consult the catalog first; the hardcoded…, When NVIDIA key is set, ``_catalog_defaults()`` returns the catalog's nvidia…, ``_get_defaults()`` returns the catalog-derived defaults (not the hardcoded…, ``jcode.py`` must NOT have the stale hardcoded ``meta/llama-3.3-70b-instruct``…, ``opencode.py`` must NOT have the stale hardcoded model id inline., ``_NVIDIA_DEFAULT_MODEL`` must equal the first entry in the catalog's nvidia… (+16 more)

### Community 423 - "infra_cost.py"
Cohesion: 0.15
Nodes (14): compute_request_cost(), _float_env(), get_infra_config(), InfraConfig, load_infra_config(), project_session_cost(), Local infrastructure cost model for true TCO analysis. This module computes the…, Compute infrastructure cost for a single request given its latency. (+6 more)

### Community 424 - "output_filter.py"
Cohesion: 0.10
Nodes (17): _filter_curl(), _filter_docker(), _filter_git(), _filter_ls(), _filter_npm(), _filter_pip(), _filter_pytest(), _filter_python() (+9 more)

### Community 425 - "compilerOptions"
Cohesion: 0.10
Nodes (19): DOM, DOM.Iterable, ES2022, src, vite/client, compilerOptions, isolatedModules, jsx (+11 more)

### Community 426 - "TestCheckKwargs"
Cohesion: 0.18
Nodes (8): check_kwargs(), Any, agent/contract_enforcement.py — Runtime signature locking (J) Provides…, # NOTE: limit has a default so it is accepted; owner_id is keyword-only., Raise TypeError on unknown kwarg (runtime extra='forbid'). Args: kwargs: The…, # NOTE: limit is NOT locked — it is a legitimate optional param that does not, Unit tests for the check_kwargs helper., TestCheckKwargs

### Community 427 - "test_self_heal.py"
Cohesion: 0.11
Nodes (17): tests/test_self_heal.py — tests for PR #937 self-healing mechanism. No…, packages/ai/self_heal.py must exist and define the heal function., self_heal_brain_and_unblock_tasks must be async (called from tick handler)., backend/server.py scheduler_tick must call _self_heal_tick every tick., Admin endpoint POST /api/scheduler/self-heal must exist., 410 must mark the provider failed and fail over to the next one., 429 must record the failure so sustained rate-limiting trips failover., _DISPATCH_RETRY_LIMIT must be 5 (lowered from 10 in PR #937). (+9 more)

### Community 428 - "HarnessRegistry"
Cohesion: 0.17
Nodes (8): HarnessMetrics, HarnessRegistry, HarnessSessionRecord, _NoopDB, Any, BaseModel, services/harness_registry.py — Persistent Harness Registry Tracks which AI…, Persistent registry of harnesses and their performance history. Stores session…

### Community 429 - "scrub"
Cohesion: 0.12
Nodes (16): _phase_section(), Any, Strip credentials from text before it is written into an issue body. Failure…, Live counters, for the diagnostics endpoint and tests., The in-process phase view — authoritative, and the reason this works with no…, The Render-log view: a cross-check, and the only source for windows the process…, Run *coro* without blocking the caller, from any thread. The caller is a…, _render_section() (+8 more)

### Community 430 - "test_langfuse_agency_wide.py"
Cohesion: 0.12
Nodes (15): tests/test_langfuse_agency_wide.py — tests for PR #961 agency-wide Langfuse.…, langfuse_obs.py must define emit_agency_observation., emit_agency_observation must be a no-op when Langfuse is not configured., tasks/service.py must call emit_agency_observation for task execution., agent/agency.py must call emit_agency_observation for CEO directives., backend/server.py scheduler_tick must call emit_agency_observation., packages/ai/self_heal.py must call emit_agency_observation., emit_agency_observation must accept all documented parameters. (+7 more)

### Community 431 - "test_tasks_cache_ttl_env.py"
Cohesion: 0.21
Nodes (19): MonkeyPatch, Round-trip tests for TASKS_LIST_ALL_CACHE_TTL_SEC env-var override in…, With a lowered cap, a value above the new cap falls back to default., Reload tasks.api after injecting TASKS_LIST_ALL_CACHE_TTL_SEC=value (or unset)., Values above the 1h upper bound in _safe_ttl fall back to default. Guards the…, Value equal to the 1h upper bound is honored (boundary case)., ``TASKS_MAX_CACHE_TTL_SEC`` env var overrides the cap module-level constant., _reload_tasks_api_with_env() (+11 more)

### Community 432 - "test_voice_pipeline.py"
Cohesion: 0.14
Nodes (14): asyncio, Tests: Voice pipeline — STT backend selection, TTS backend selection, memory…, A stalled gTTS/pyttsx3 call must not hang synthesize() forever. gTTS/pyttsx3…, TTS_SYNTHESIZE_TIMEOUT_SEC must override the default ceiling., gTTS/pyttsx3 must run on a dedicated executor, not the shared default.…, test_memory_export_markdown(), test_memory_forget(), test_memory_recall_empty() (+6 more)

### Community 433 - "TestUpdateTask"
Cohesion: 0.16
Nodes (7): _NoopCheckpointStore, WorkflowRun, tests/test_workflow_orchestrator_update_task.py Pytest coverage for…, Stand-in for the real Mongo checkpoint store., Two consecutive updates collapse: the latest instruction wins. This matches…, _run(), TestUpdateTask

### Community 434 - "MemoryKernel"
Cohesion: 0.16
Nodes (7): Fact, get_memory_kernel(), MemoryKernel, voice/memory_kernel.py — Jarvis OS-inspired Memory Kernel. Stores atomic facts…, Return most relevant facts. Simple substring match on content., SQLite-backed atomic fact store with Markdown mirror., Store a new atomic fact or reinforce an existing one.

### Community 435 - "rag_context.py"
Cohesion: 0.15
Nodes (14): ContextResult, MemoryTurn, agent/rag_context.py — Advanced RAG context management layer. Pipeline --------…, Rough token estimate: 4 chars ≈ 1 token (minimum 1)., Run the full RAG pipeline and return a token-budget-respecting context.…, One turn in the conversation history., Select up to *top_k* highest-scoring turns that fit within *budget*. Returns…, A document selected by retrieval, with its compressed excerpt. (+6 more)

### Community 436 - "_extract_tech_relevance"
Cohesion: 0.17
Nodes (6): _extract_tech_relevance(), Dynamic extraction: finds any tech keyword mentioned in the skill content,…, Tests for _extract_tech_relevance() word-boundary matching., Integration-style tests for the recommendation path (no I/O)., TestExtractTechRelevance, TestRecommendLogic

### Community 437 - "agile_api.py"
Cohesion: 0.29
Nodes (16): complete_sprint(), create_sprint(), _get_mgr(), get_velocity(), list_sprints(), Any, BaseModel, get (+8 more)

### Community 438 - "Skill: fabric-patterns"
Cohesion: 0.11
Nodes (18): 1. Ensure Pattern Directory Exists, 2. List Available Patterns, 3. Retrieve a Pattern, 4. Apply a Pattern with Variables, 5. Stitch Patterns Together, 6. Create New Patterns, Acceptance Checks, Directory Structure (+10 more)

### Community 439 - "Analysis & Synthesis Instructions"
Cohesion: 0.11
Nodes (18): 1. Define the Atmosphere, 2. Map the Color Palette, 3. Establish Typography Rules, 4. Define the Hero Section, 5. Describe Component Stylings, 6. Define Layout Principles, 7. Define Responsive Rules, 8. Encode Motion Philosophy (+10 more)

### Community 440 - "Production Readiness Assessment — local-llm-server"
Cohesion: 0.11
Nodes (18): 1. Availability & Reliability, 2. Observability, 3. Deployment Architecture, 4. Configuration & Secrets, 5. Recovery & Backup, 6. Cloudflare Worker Audit, Current State, Current State (+10 more)

### Community 441 - "SyncAgent"
Cohesion: 0.19
Nodes (4): Background agent that periodically syncs session state across contributors.…, SyncAgent, Tests for agents.cowork_session — Claude Cowork., TestSyncAgent

### Community 442 - "TestNormalizeResponseFormat"
Cohesion: 0.08
Nodes (16): _normalize_response_format(), Translate OpenAI ``response_format`` into Ollama's ``format`` field. For…, Payload without 'model' field should apply normalization (no '/' → local)., _normalize_response_format must not mutate the input dict., Unit tests for chat_handlers._normalize_response_format., If json_schema has no 'schema' key, don't break., TestNormalizeResponseFormat, _convert_to_ogg() (+8 more)

### Community 443 - "Skill: fabric-patterns"
Cohesion: 0.11
Nodes (18): 1. Ensure Pattern Directory Exists, 2. List Available Patterns, 3. Retrieve a Pattern, 4. Apply a Pattern with Variables, 5. Stitch Patterns Together, 6. Create New Patterns, Acceptance Checks, Directory Structure (+10 more)

### Community 444 - "db/__init__.py"
Cohesion: 0.15
Nodes (7): _LazyModuleProxy, db — storage abstraction layer (V2.0 Phase 5: real code moved to…, Loads the real module on first attribute access, then replaces itself., # IMPORTANT: keep these imports LAZY (inside __getattr__) so that a Mongo-only, MongoStore, db/mongo_store.py — MongoDB store backed by Motor (existing implementation).…, Thin wrapper that exposes the Motor database as collection attributes.…

### Community 445 - "Admin Dashboard Guide"
Cohesion: 0.11
Nodes (19): Accessing the Dashboard, Admin API (Programmatic Access), Admin Dashboard Guide, Dashboard — healthy state, Dashboard — key created (one-time token flash), Dashboard — Langfuse diagnostic, Dashboard Layout, Login page (+11 more)

### Community 446 - "Implementation Plan"
Cohesion: 0.11
Nodes (18): (1) & partly (4): "Something went wrong" masks the real error everywhere, (2) & (3): Company creation flow / non-admin gate placement, (4): Agent provisioning "loading forever" — blocking subprocess in async path, (5): Tailored questions are hardcoded today, A0. Fix live scanner crashes on real-world sites (`services/scanner.py`) — do first, A. Fix error-message masking (`frontend/src/api.js`), Agent Prompt (paste this to start the implementation session), B. Make runtime activation non-blocking (`runtimes/control.py`, (+10 more)

### Community 447 - "test_doctor_service_token_check.py"
Cohesion: 0.23
Nodes (12): _authed_client(), clean_store(), _clear(), tests/test_doctor_service_token_check.py — N5 follow-up: doctor check for…, Reset brain config store + SQLITE_DB_PATH + SERVICE_TOKEN., Build a TestClient authenticated as admin (for /api/doctor/diagnostics)., When SERVICE_TOKEN is not set, the doctor endpoint must surface a 'warn' check…, When SERVICE_TOKEN is set, the doctor endpoint must surface a 'pass' check. (+4 more)

### Community 448 - "ProviderConsole.jsx"
Cohesion: 0.11
Nodes (10): ALIASES, canonicalId(), CATALOGUE, FILTERS, ADR-0008, mergeProviders(), ProviderRow(), STATE (+2 more)

### Community 449 - "McpCard.jsx"
Cohesion: 0.14
Nodes (9): getRenderHealth(), getRenderOpsStatus(), runRenderOpsScan(), api, BTN, McpCard(), NOTE(), relTime() (+1 more)

### Community 450 - "build_workflow.py"
Cohesion: 0.33
Nodes (18): _c(), _get(), _header(), main(), _make_headers(), _phase_icon(), _post(), _print_phases() (+10 more)

### Community 451 - "SyntheticDataPipeline"
Cohesion: 0.17
Nodes (6): get_synthetic_pipeline(), Clear all accumulated samples., Return the module-level SyntheticDataPipeline singleton., Pipeline to generate synthetic training data from agent sessions. Usage::…, SyntheticDataPipeline, TestSyntheticDataPipeline

### Community 452 - "test_chat_mode_regressions.py"
Cohesion: 0.16
Nodes (20): ProviderAttempt, ProviderResult, _auth_headers(), test_agent_status_endpoint_reports_live_progress_and_tool_calls(), test_agent_stream_endpoint_emits_server_sent_events(), test_chat_send_emits_langfuse_observation_for_direct_chat(), test_chat_send_keeps_complex_prompt_on_direct_path_when_agent_mode_is_off(), test_chat_send_keeps_explanatory_github_pr_guidance_on_direct_path() (+12 more)

### Community 453 - "test_brain_patch_service_token.py"
Cohesion: 0.18
Nodes (18): clean_store(), _clear_overrides(), _make_client_with_user(), tests/test_brain_patch_service_token.py — N5 acceptance: PATCH…, N5 acceptance: no service token + no user session → 401 (not 200)., N5 regression: the existing dashboard path (no service token, non-admin user)…, N5 regression: the existing admin dashboard path (no service token, admin user)…, Reset the brain config store + point SQLITE_DB_PATH at a tmp path. (+10 more)

### Community 454 - "agent/watchdog.py"
Cohesion: 0.15
Nodes (7): _now(), Any, agent/watchdog.py — Resource Watchdog Monitors URLs, files, or any resource…, Register a resource to monitor. Returns the :class:`WatchedResource`., Check a single resource right now. Returns a :class:`WatchEvent` if changed., WatchedResource, WatchEvent

### Community 455 - "AuditLog"
Cohesion: 0.05
Nodes (43): Replace the process-wide store. Tests only., reset_approval_store(), AuditEvent, AuditLog, packages/governance/audit.py — the evidence trail for every governed action.…, Redact secret-shaped substrings, then truncate., One governed action, fully described. Field order follows the…, One-line JSON, suitable for a SIEM shipper tailing the log. (+35 more)

### Community 456 - "test_fabric_patterns.py"
Cohesion: 0.11
Nodes (5): MonkeyPatch, Path, Tests for scripts/fabric_cli.py and the fabric-patterns pattern engine., test_new_scaffolds_pattern(), test_save_and_show_roundtrip()

### Community 457 - "Any"
Cohesion: 0.10
Nodes (14): _NoOpSpan, _NoOpTracer, otel_middleware_factory(), otel_status_error(), otel_status_ok(), Any, Exception, Create a FastAPI-compatible OTEL middleware. Usage:: from services.otel_tracing… (+6 more)

### Community 458 - "validate_session_id"
Cohesion: 0.16
Nodes (5): TestSessionIdValidation, WorkspaceNotFoundError should not expose the base root in error messages., TestNoInternalPathLeakage, Validate and return a session ID, or raise InvalidSessionIdError., validate_session_id()

### Community 459 - "ErrorInterceptorMiddleware"
Cohesion: 0.18
Nodes (11): _dispatch_async(), ErrorInterceptorMiddleware, Any, BaseHTTPMiddleware, Exception, Request, Response, agent/error_interceptor.py — HTTP Error Interceptor Middleware… (+3 more)

### Community 460 - "github_tools.py"
Cohesion: 0.24
Nodes (16): get_repo(), _get_token(), _get_user(), init_workspace(), list_branches(), list_prs(), list_repos(), BaseModel (+8 more)

### Community 461 - "test_lessons.py"
Cohesion: 0.18
Nodes (17): _known_entry_texts(), Recorded lessons as ``{signature: {acceptable text, ...}}``. The citation binds…, _get_store(), Any, Failure lessons: turn failed runs into context for the next run. The supervisor…, Formatted prompt block of recent lessons, or '' when none exist., Persist a lesson for every failed step in a run. Never raises., recent_lessons_block() (+9 more)

### Community 462 - "KeyStore"
Cohesion: 0.25
Nodes (4): KeyRecord, KeyStore, Look up a plaintext key by its SHA-256 hash. When *client_ip* is provided,…, Thread-safe JSON-backed key store.

### Community 463 - "Comprehensive Skill Index (By Category)"
Cohesion: 0.11
Nodes (17): 10. Domain (Modelling, Training, Infra), 1. Planning and Implementation, 2. Code Quality, Architecture, and Audits, 3. State Management and Git Flow, 4. Memory, Knowledge, and Context Tuning, 5. Research, Browsing, and External Intel, 6. Session Lifecycle and Workflow, 7. Style and Craft Polish (UI / Docs / Tone) (+9 more)

### Community 464 - "Agent Skill: Principal UI/UX Architect & Motion Choreographer (Awwwards-Tier)"
Cohesion: 0.11
Nodes (17): 1. Meta Information & Core Directive, 2. THE "ABSOLUTE ZERO" DIRECTIVE (STRICT ANTI-PATTERNS), 3. THE CREATIVE VARIANCE ENGINE, 4. HAPTIC MICRO-AESTHETICS (COMPONENT MASTERY), 5. MOTION CHOREOGRAPHY (FLUID DYNAMICS), 6. PERFORMANCE GUARDRAILS, 7. EXECUTION PROTOCOL, 8. PRE-OUTPUT CHECKLIST (+9 more)

### Community 465 - "Component Map"
Cohesion: 0.11
Nodes (17): Architecture Audit — local-llm-server, Architecture Diagram, Component Map, Layer 10 — WebUI (`webui/`), Layer 11 — Infrastructure, Layer 1 — API Proxy (`proxy.py`, 1719 lines), Layer 2 — Chat Handlers (`chat_handlers.py`, 710 lines), Layer 3 — Model Router (`router/`) (+9 more)

### Community 466 - "TrafficDirector"
Cohesion: 0.11
Nodes (11): get_director(), In-process traffic distribution and budget accounting for providers., EWMA latency in ms; never-sampled providers sort first. Returning -1.0 for an…, Clear all counters (tests only)., Return the process-singleton TrafficDirector., TrafficDirector, Tests for packages/ai/traffic_director.py — traffic distribution across…, `int(0.5)` is 0, and a cap of 0 makes `in_flight >= cap` true at zero in-flight… (+3 more)

### Community 467 - "Agent State — colibri GLM-5.2 deployment (resumable)"
Cohesion: 0.11
Nodes (17): Agent State — colibri GLM-5.2 deployment (resumable), Audit verification (2026-07-16, this session), Context / Task, Converged action sequence (after colibri binding is fixed, someday), Done this session (commit `b03a6ba`), Findings (verified empirically), Follow-up fix during commit amend: UTF-8 BOM on setup_autostart.ps1, Option A — Pivot to a feasible MLX model (HIGHEST ROI) (+9 more)

### Community 468 - "Architecture Overview — local-llm-server"
Cohesion: 0.11
Nodes (18): `admin_auth.py` + `admin_gui.py`, `agent/`, Architecture Overview — local-llm-server, `chat_handlers.py`, Deployment, Feature Maturity Tiers, `handlers/anthropic_compat.py`, High-Level Architecture (+10 more)

### Community 469 - "Pending Activities — Implementation Playbook"
Cohesion: 0.11
Nodes (17): Context: what already works (do NOT redo), Definition of done (per task), How to verify the whole thing end-to-end (local, no external infra), P0 — Make autonomy real in production, P1 — Close the remaining product gaps, P2 — ECC harness & polish, Pending Activities — Implementation Playbook, Task 10 — ECC cross-harness adapter (currently PLANNED only) (+9 more)

### Community 470 - "Platform Guide — the full tour"
Cohesion: 0.11
Nodes (18): Agent runtimes, Architecture, Cloud deployment (Render + GitHub Pages), Development, Feature maturity — what's stable vs. beta, HITL approval gates — you stay in control, How it works — the 5-minute version, Learning loop — failures become context (+10 more)

### Community 471 - "The rules"
Cohesion: 0.11
Nodes (17): Changing these rules, How the gate behaves, Quick-Note Context Rulebook, R10 — Use the repository's real identity **[gate]**, R11 — Name a real integration point **[gate]**, R12 — Mark epistemic status at the claim **[review]**, R1 — Ground the plan in the source before planning anything **[gate]**, R2 — Say what the artifact actually is **[gate]** (+9 more)

### Community 472 - "Part A — Health Report"
Cohesion: 0.11
Nodes (17): F1 — CLAUDE.md documents an architecture that no longer exists, F2 — 15 skills have no frontmatter description, F3 — Direct `os.environ` reads outside config modules, F4 — `print()` in importable production modules, F5 — graphify hook nags every session, F6 — God files, Healthy signals, P1 — Refresh CLAUDE.md and AGENTS.md to match the real architecture (+9 more)

### Community 473 - "ControlsScreen.jsx"
Cohesion: 0.15
Nodes (15): getPlatformControls(), resetPlatformControl(), setPlatformControls(), { getPlatformControls, setPlatformControls, resetPlatformControl }, secondGroup, BANNER(), ControlRow(), ControlsScreen() (+7 more)

### Community 474 - "apply_review.py"
Cohesion: 0.19
Nodes (10): ApplyReviewAgent, build_review_context(), _gh(), main(), _openai_tools_to_anthropic(), Convert OpenAI function-calling tool schemas to Anthropic tool schemas., Return (result_text, should_stop)., Run using NVIDIA NIM (OpenAI-compatible). Called as fallback. (+2 more)

### Community 475 - "Specialist"
Cohesion: 0.04
Nodes (46): SpecialistFamily, Find all specialists of a specific family., Find specialists that can handle a task with given capabilities., A specialist agent that can be provisioned for company-specific tasks., Check if this specialist can handle a task with given capabilities., Specialist, Create a new specialist in SQLite., Get a specialist by ID from SQLite. (+38 more)

### Community 476 - "Delegation Plan (agent-ready work packages)"
Cohesion: 0.11
Nodes (18): Delegation Plan (agent-ready work packages), Findings, http://127.0.0.1:8899/, Page Details (worst first), Pillar Scores, `seo-fix-canonicals` - Fix Canonicals findings: 1 finding type(s) across 1 URL hit(s), `seo-fix-content` - Fix Content findings: 1 finding type(s) across 1 URL hit(s), `seo-fix-geo` - Fix GEO findings: 5 finding type(s) across 5 URL hit(s) (+10 more)

### Community 477 - "agency_fix.py"
Cohesion: 0.20
Nodes (17): apply_edits(), build_prompt(), call_llm(), collect_context(), collect_source_files(), decline_cleanly(), extract_failing_tests(), _is_blocked() (+9 more)

### Community 478 - "sync_readme_gallery.py"
Cohesion: 0.22
Nodes (15): main(), _out_dir(), Path, Generate Web UI screenshots for README/docs. Requires: pip install playwright…, build_gallery(), GallerySection, main(), Path (+7 more)

### Community 479 - "GuardrailEngine"
Cohesion: 0.13
Nodes (10): _deep_merge(), get_guardrails(), GuardrailEngine, Configurable safety rail engine for LLM inputs and outputs. Supports: -…, Load guardrail rules from a YAML or JSON config file., Compile regex patterns from the rules configuration., Deep merge two dicts. Override values take precedence., Return the module-level GuardrailEngine singleton. (+2 more)

### Community 480 - "LocalLLMSetup"
Cohesion: 0.16
Nodes (7): LocalLLMSetup, Update .env file with configuration., Check if services are already running., Start the proxy server., Scan for local models., Scan the models folder for available models., Configure which models to use for agent roles.

### Community 481 - "test_company_api.py"
Cohesion: 0.11
Nodes (13): client(), Tests for Company Graph API endpoints., Create a test client for the FastAPI app., Test Company Graph API endpoints., Test that the company API router is included., Test Doctor endpoint., Test the public doctor endpoint., Regression tests for BUG-1: POST /api/company failing with `{"loc": ["body",… (+5 more)

### Community 482 - "TestStopSlopChecker"
Cohesion: 0.11
Nodes (10): Should detect phrases case-insensitively, Should detect throat-clearing phrases, Should return no issues for clean text, Strict mode should detect passive voice, Should detect multiple types of tells in one text, Issues should have helpful suggestions, Should detect business jargon, Should remove throat-clearing phrases (+2 more)

### Community 483 - "test_phase4_runtime_resilience.py"
Cohesion: 0.13
Nodes (24): _env_flag(), Read a boolean env var. Accepts 'true'/'1'/'yes' (case-insensitive)., _make_task(), asyncio, Task, TaskStatus, tests/test_phase4_runtime_resilience.py Phase 4: runtime resilience tests.…, Tasks in TODO or DONE status are ignored by the reconciler. (+16 more)

### Community 484 - "handle_workflow_ide_chat"
Cohesion: 0.18
Nodes (17): _extract_last_user_message(), handle_workflow_ide_chat(), _json_response(), Any, JSONResponse, Request, StreamingResponse, workflow/ide_bridge.py — OpenAI-compatible SSE bridge for IDE clients. This… (+9 more)

### Community 485 - "asyncio"
Cohesion: 0.12
Nodes (8): requires_db, asyncio, Test that storage service can be initialized., Test company CRUD operations - skipped as requires specific config., Test that scanner service can be initialized., Test that specialist service can be initialized., Test that onboarding service can be initialized., End-to-end against the real Mongo (CI service): the exact handler sequence…

### Community 486 - "TestHelpers"
Cohesion: 0.15
Nodes (8): _extract_tags(), _first_paragraph(), Path, Return the first non-empty, non-heading line. Skips YAML frontmatter (--- ...…, Pull hashtags and bold words from markdown as tags., Tests for module-level helper functions., Regression: frontmatter (--- ... ---) must not surface as '---'., TestHelpers

### Community 487 - "._fetch_flat_skill_file"
Cohesion: 0.21
Nodes (8): _fmt_name(), AsyncClient, Fetch skills from all configured GitHub registries. Returns count added., Force-refresh remote skills, bypassing TTL. Returns count added., Fetch one GitHub registry and return a list of RegistrySkill objects. Handles…, Fetch a registry whose skills live in arbitrarily nested directories. Uses the…, Fetch one nested SKILL.md via raw.githubusercontent.com., Fetch a flat .md file and convert it to a RegistrySkill.

### Community 488 - "test_task_service_failed_comment.py"
Cohesion: 0.18
Nodes (16): coordinator(), _make_result(), mock_store(), mock_workflow(), asyncio, tests/test_task_service_failed_comment.py — verify that a FAILED TaskResult…, A FAILED TaskResult without agent_comment transitions to FAILED without…, A FAILED TaskResult sets task.error_message to result.output. (+8 more)

### Community 489 - "Task"
Cohesion: 0.25
Nodes (5): Path, Score the agent's final answer. Returns (success, score)., Returns (success: bool, score: float ∈ [0, 1]). Raises NotImplementedError for…, A fully-specified evaluation task. Fields mirror the OpenHarness task schema so…, Task

### Community 490 - "SKILL: Industrial Brutalism & Tactical Telemetry UI"
Cohesion: 0.12
Nodes (16): 1. Skill Meta, 2.1 Swiss Industrial Print, 2.2 Tactical Telemetry & CRT Terminal, 2. Visual Archetypes, 3.1 Macro-Typography (Structural Headers), 3.2 Micro-Typography (Data & Telemetry), 3.3 Textural Contrast (Artistic Disruption), 3. Typographic Architecture (+8 more)

### Community 491 - "Skill: data-quality-audit"
Cohesion: 0.12
Nodes (16): 1. Token Length Distribution, 2. Deduplication Check, 3. Tokenizer Fertility Check, 4. Special Token Consistency, 5. Language Detection (if langdetect available), 6. Content Quality Signals, Background (Why This Matters), Checks Performed (+8 more)

### Community 492 - "What "Slop" Looks Like"
Cohesion: 0.12
Nodes (16): Acceptance Checks, Category 1 — Obvious Comments, Category 2 — Phantom Abstractions, Category 3 — Defensive Checks for Impossible Cases, Category 4 — Speculative Generality, Category 5 — Verbose Variable Names, Category 6 — Unasked-For Boilerplate, Instructions (+8 more)

### Community 493 - "test_admin_local_brain_router.py"
Cohesion: 0.18
Nodes (16): build_admin_local_brain_router(), Any, APIRouter, Construct a ready-to-mount APIRouter with the auth dependency baked in. The…, _require_admin(), _make_app(), FastAPI, tests/test_admin_local_brain_router.py — auth + toggle flow for… (+8 more)

### Community 494 - "local_brain_router.py"
Cohesion: 0.19
Nodes (16): get_local_brain_state(), HeartbeatBody, post_local_brain_heartbeat(), post_local_brain_toggle(), Any, BaseModel, get, post (+8 more)

### Community 495 - "Section-by-Section Acceptance Criteria"
Cohesion: 0.12
Nodes (16): 467 Final Acceptance Criteria, §A — Company Graph + Onboarding, §B — 34 Specialist Families, §C — ECC, Obsidian, Graphify, Council Review Wiring, §D — Direct Chat as Control Center, Definition of Done, §E — Workflow Engine as Canonical Backbone + Worktree Isolation, §F — Doctor Full Check List (+8 more)

### Community 497 - "SQLiteStore"
Cohesion: 0.17
Nodes (9): Connection, Top-level store — exposes collections as attributes. Usage:: store =…, Lazily build the pool of read-only connections (idempotent)., Yield a read connection from the pool (falls back to the writer). On in-memory…, Create tables if they don't already exist., SQLiteStore, B608 guard: _Collection.__init__ must reject names outside _COLLECTIONS.…, store() (+1 more)

### Community 498 - "TaskStore"
Cohesion: 0.04
Nodes (78): Set the global agent store instance (e.g., with MongoDB on startup)., set_agent_store(), Any, Task, TaskStatus, Create a task. Deduplicates by source_id if set (Charter G3). If a task with…, Fetch a task by ID. If owner_id is set, enforces ownership., Return the task previously created for an external ``source_id`` (e.g.… (+70 more)

### Community 499 - "agent_readiness_audit.py"
Cohesion: 0.21
Nodes (15): _grade(), main(), PillarResult, scripts/agent_readiness_audit.py — score this repo's fitness for autonomous…, ReadinessReport, run_audit(), score_build_system(), score_dev_environment() (+7 more)

### Community 500 - "test_ci.sh"
Cohesion: 0.15
Nodes (16): ADMIN_EMAIL, ADMIN_PASSWORD, API_KEYS, cleanup(), DB_NAME, fail(), LANGFUSE_HOST, LANGFUSE_PUBLIC_KEY (+8 more)

### Community 501 - "ProviderCircuit"
Cohesion: 0.17
Nodes (7): ProviderCircuit, Attempt to move from OPEN to HALF_OPEN after recovery timeout., Check if a request can be made through this circuit., Per-provider circuit breaker state machine., TestProviderCircuit, parametrize, Counting every sub-500 as a success meant the breaker could never open for the…

### Community 502 - "test_activation_api.py"
Cohesion: 0.21
Nodes (16): _client(), TestClient, Tests for activation_api — instance status, OpenAPI schema, and role route.…, GET /api/activation/settings is PUBLIC — non-admin users need to read the…, test_change_role_rejects_invalid_role(), test_change_role_requires_authentication(), test_change_role_returns_404_for_missing_user(), test_change_role_updates_existing_user() (+8 more)

### Community 503 - "test_health_endpoints.py"
Cohesion: 0.17
Nodes (16): _make_fake_client(), Exception, Tests for /health, /live, and /api/health endpoints., When Ollama is down, /api/health should also return a degraded status., Return a context-manager-compatible mock for httpx.AsyncClient., Container liveness probe must always return 200., Health endpoint exists and returns a JSON body., Health endpoint includes provider states when ProviderRouter is wired in. (+8 more)

### Community 504 - "test_keepalive.py"
Cohesion: 0.18
Nodes (16): Path, Smoke test for scripts/keepalive.py (Windows-friendly Render + Ollama keepalive…, `--diagnose` mode exits 1 when hosts are unreachable (per docstring: exit 0/1)., Reload scripts.keepalive with KEEPALIVE_LOG = log_path and clear cache., KEEPALIVE_LOG under tmp_path; log_path() ensures parent directory exists., _rotate_log_if_needed() is a no-op when file is under MAX_LOG_BYTES; truncates…, _log() writes '[YYYY-MM-DD HH:MM:SS] <line>' to KEEPALIVE_LOG., When Render + Ollama are both unreachable, run_once() returns 1. (+8 more)

### Community 505 - "test_openclaw_endpoints.py"
Cohesion: 0.12
Nodes (10): client(), tests/test_openclaw_endpoints.py — OpenClaw HTTP + WebSocket endpoint tests., After pairing, ping command returns pong., Unknown command returns error., WebSocket with wrong token is rejected (connection closed)., WebSocket with correct token pairs successfully., test_websocket_pairing_accepts_correct_token(), test_websocket_pairing_rejects_wrong_token() (+2 more)

### Community 506 - "TestRoutes"
Cohesion: 0.19
Nodes (7): _install_service(), Tests for agents/portfolio_api.py — the v5 portfolio board API. Loads the…, A materializer exception must not break /refresh (the board still returns), and…, Install a PortfolioService whose portfolio is fixed (no rebuild)., _seeded_manager(), TestBoardPayload, TestRoutes

### Community 507 - "OperationalIncidentTracker"
Cohesion: 0.13
Nodes (11): OperationalIncidentTracker, Count operational failures; diagnose and file the ones that persist. Every…, Start with no tracked signatures and no filing history., Note one operational failure. Returns True when it filed an incident. Called…, Reconcile the admission granted in ``_may_file`` with what happened. Admission…, Drop all state. Used by tests., Count one failure; return True when this crossed into an incident., Forget signatures that have gone quiet. Caller must hold the lock. A signature… (+3 more)

### Community 508 - "cowork_session.py"
Cohesion: 0.24
Nodes (7): Enum, str, Claude Cowork — shared AI coding sessions with real-time sync. Enables multiple…, Role within a cowork session., Current phase of a cowork session., SessionPhase, SessionRole

### Community 509 - "hermes_prompt.py"
Cohesion: 0.19
Nodes (15): build_chatml_system_prompt(), format_chatml_message(), format_tool_call(), format_tool_response(), messages_to_chatml(), model_supports_chatml(), parse_tool_call_from_chatml(), Any (+7 more)

### Community 510 - "MemoryMiddleware"
Cohesion: 0.17
Nodes (10): create_memory_middleware(), MemoryMiddleware, Any, Process incoming chat request and inject memories., Extract and save learnings from model responses., Factory function to create memory middleware instance., Middleware for automatic memory loading and injection., Detect AI coding tool from request headers. (+2 more)

### Community 511 - "test_ai_insights.py"
Cohesion: 0.05
Nodes (50): AIToolMetrics, build_report(), EngagementMetrics, PerformanceAnalytics, datetime, Enum, str, AI-Assisted Engineering Insights — track AI tool usage, engagement, and… (+42 more)

### Community 512 - "analyze_quantitative"
Cohesion: 0.13
Nodes (15): analyze_quantitative(), Compute descriptive statistics for a numeric series. Args: source: Where the…, apply_recommendations(), collect_codebase_metrics(), extract_qualitative_themes(), main(), plan_repo_scan(), Use the user research skill to scan the repo and apply recommendations. Adapts… (+7 more)

### Community 513 - "AITellIssue"
Cohesion: 0.17
Nodes (8): AITellIssue, Find all AI tells in text, Find throat-clearing phrases, Find emphasis crutches (weak adverbs), Find meta-commentary (text referring to itself), Find Wh-sentence starters (weak prose starters), Find basic passive voice patterns (strict mode only), Format issues as human-readable report

### Community 514 - "Skill: repowise-intelligence"
Cohesion: 0.12
Nodes (15): 1. Graph Intelligence (Dependency Graph), 2. Git Intelligence, 3. Documentation Intelligence, 4. Decision Intelligence, Acceptance Checks, Directory Structure, Example Usage, Implementation Approach (+7 more)

### Community 515 - "ARCHITECTURE.md — Target Architecture"
Cohesion: 0.12
Nodes (15): 1. Target Repository Structure, 2. Dependency Rules, 3. Provider Architecture (Target), 4. Configuration Architecture (Target), 5. Event Bus Architecture (Target), 6. Scheduler Architecture (Target), 7. Dashboard Architecture (Target), 8. Migration Principles (+7 more)

### Community 516 - "admin_digest_router.py"
Cohesion: 0.20
Nodes (15): _build_payload_or_500(), _check_secret(), _expected_secret(), preview_digest_endpoint(), Any, get, post, Dry-run: same auth, returns the would-be markdown body but does NOT dispatch to… (+7 more)

### Community 517 - "Skill: repowise-intelligence"
Cohesion: 0.12
Nodes (15): 1. Graph Intelligence (Dependency Graph), 2. Git Intelligence, 3. Documentation Intelligence, 4. Decision Intelligence, Acceptance Checks, Directory Structure, Example Usage, Implementation Approach (+7 more)

### Community 518 - "The 10-Step Workflow"
Cohesion: 0.12
Nodes (15): Cross-Tool Compatibility, Quick Reference Card, Skill: session-planning — Mandatory Planning Workflow for All AI Agents, Step 10 — Close Out, Step 1 — Orient (free), Step 2 — Understand the Task, Step 3 — Load Relevant Skills, Step 4 — Research (if novel task) (+7 more)

### Community 519 - "Contributing to local-llm-server"
Cohesion: 0.12
Nodes (16): Architecture, Bug Reports, Changelog, Coding Standards, Commit Message Convention, Contributing to local-llm-server, Development Setup, Feature Requests (+8 more)

### Community 520 - "CEO Micro-Management"
Cohesion: 0.12
Nodes (16): A failed drive does not abandon the goal, CEO Micro-Management, Configuration reference, Escalation, and why it terminates, Five bounds, Operator surface, Tests, The 24x7 supervisor (+8 more)

### Community 521 - "467 Brutal Audit — File-by-File Status"
Cohesion: 0.12
Nodes (15): 467 Brutal Audit — File-by-File Status, Agent System, Backend & Services, Core Proxy & Routing, Direct Chat, Feature Matrix (spec §I — demotions needed), Frontend / Public Site (spec §H — 0% delivered), GitHub Workflows (+7 more)

### Community 522 - "Migration Notes"
Cohesion: 0.12
Nodes (16): Compose secret scoping — shipped, opt-in, Container hardening overlay, Known limitations at merge, Migration Notes, Optional hardening (operator decisions), Path to enforcement, Protect the policy file from agents, Rollback (+8 more)

### Community 524 - "Runbook — Apply the Fast Free NVIDIA Brain to Render (TASK 2)"
Cohesion: 0.12
Nodes (15): B.1 — Open the service's Environment tab, B.2 — Set these five keys on each service, B.3 — Sanity-check the secrets that must NOT regress, B.4 — Trigger TASK 5 keep-alive immediately, Option A — Blueprint sync (preferred), Option B — manual per-service editor, Rollback, Runbook — Apply the Fast Free NVIDIA Brain to Render (TASK 2) (+7 more)

### Community 525 - ".start_onboarding"
Cohesion: 0.07
Nodes (15): Workflow, Detect the Git provider from a repository URL. Args: repo_url: Repository URL…, Start the onboarding process for a company. Args: company_id: Company ID…, Schedule a fire-and-forget background task, keeping a strong reference.…, Force-refresh the dynamic skill registry and log tech-stack recommendations.…, Activate a company's 24x7 agency runtimes in the background. Runs after…, Get the current onboarding progress for a company. Args: company_id: Company ID…, Resume onboarding from where it left off. Args: company_id: Company ID Returns:… (+7 more)

### Community 526 - "implement_agent.py"
Cohesion: 0.16
Nodes (12): main(), _openai_tools_to_anthropic(), Safely insert an entry under ## [Unreleased] without touching the rest of the…, Convert OpenAI function-calling tool schemas to Anthropic tool schemas., Run the implementation agent loop using Claude Opus via Anthropic SDK. Returns…, _read_claude_md(), _run_anthropic_agent_loop(), _run_baseline_pytest() (+4 more)

### Community 527 - "AgentSessionStore"
Cohesion: 0.03
Nodes (204): BackgroundAgent, BackgroundTask, _now(), Any, agent/background.py — Background Agent An always-on worker thread that…, Enqueue *task* for processing. Returns the task (with task_id set)., Convenience: create a task and submit it in one call., Real handler — dispatches through AgentRunner when available. HARDENED (PR… (+196 more)

### Community 528 - "fabric_cli.py"
Cohesion: 0.29
Nodes (15): cmd_apply(), cmd_list(), cmd_new(), cmd_save(), cmd_show(), cmd_stitch(), _ensure_patterns_dir(), main() (+7 more)

### Community 529 - "sync_ngrok.py"
Cohesion: 0.26
Nodes (14): detect_ngrok_url(), dim(), fail(), header(), info(), main(), ok(), patch_platform_brain_via_switch_brain() (+6 more)

### Community 530 - "test_north_mini_code.py"
Cohesion: 0.09
Nodes (13): north_mini_code_model_for(), Return the North Mini Code model id served by *provider*, else ``None``.…, tests/test_north_mini_code.py — North Mini Code 1.0 integration. Covers the…, The switch defaults ON so North is the default post-install., The agency/Hermes execution path defaults to North via the resolver., Hermes must be able to run the agency with the full Hermes-OS capacity set —…, Only high/medium/low are honoured; anything else means 'unset'., test_flag_default_is_on() (+5 more)

### Community 531 - "GuardResult"
Cohesion: 0.16
Nodes (8): GuardResult, Any, Check user input against input safety rules. Returns a GuardResult with…, Check model output against output safety rules. Returns a GuardResult with…, Unified check method. direction = 'input' or 'output'., Return guardrail statistics., Result of a guardrail check., TestGuardResult

### Community 532 - "test_telegram_auto_approve.py"
Cohesion: 0.21
Nodes (15): is_sensitive(), True when *text* references a sensitive target (auth/keys/secrets/service…, _build_execution_request(), Any, Build a minimal ``ExecutionRequest`` for plain-text → orchestrator.execute.…, admin_user(), _auto_approve(), non_admin_user() (+7 more)

### Community 533 - "ManagedAgentDreams"
Cohesion: 0.22
Nodes (4): ManagedAgentDreams, Manages recording session memories and consolidating them into dreams., Tests for ManagedAgentDreams., TestManagedAgentDreams

### Community 534 - "test_autonomy_status.py"
Cohesion: 0.12
Nodes (15): client(), TestClient, tests/test_autonomy_status.py — public /api/autonomy/status readiness probe.…, No auth required; response carries the readiness contract keys., The probe carries the loop fleet readiness summary (loop-audit)., Without NVIDIA key AND without Ollama, the probe must report no_brain., When NVIDIA is absent but Ollama is configured, report brain as ollama., With an NVIDIA key the brain resolves and the secret is no longer flagged. (+7 more)

### Community 535 - ".update_intelligence"
Cohesion: 0.11
Nodes (9): Build symbol-level dependency graph for Python files., Extract docstrings and store as documentation., Mark that we have updated intelligence up to this commit., Build or update all intelligence layers., Extracts architectural decisions related to target from git history and inline…, Build file-level dependency graph based on imports., One-call RAG over documentation with confidence gating., Semantic search over documentation (we'll do keyword search for now). (+1 more)

### Community 536 - "test_dockerfile_ships_root_modules.py"
Cohesion: 0.17
Nodes (13): _dockerfile_text(), Regression guard: the backend image must ship every root-level Python module…, An env var set to empty string means unset, not a commit named ''., Unknown must read as unknown — a deploy check treats None as 'unverifiable' and…, True when the Dockerfile copies root .py modules wholesale (`COPY *.py ...`)., The worker's `python worker_main.py` start command needs worker_main.py., V2.0 Modernization: the image must ship `packages/` (provider_router,…, _ships_all_root_modules() (+5 more)

### Community 537 - "test_frontend_deployment_guards.py"
Cohesion: 0.20
Nodes (15): Step 3 runtime config must render checkboxes for each runtime., index.css must override appearance:none for checkboxes/radios., The checkbox appearance override must NOT set appearance:none (that would keep…, The checkbox appearance override must use 'auto' to request native rendering.…, SetupWizardPage must render <input type='checkbox'> for each provider toggle., _read(), test_api_redirects_respect_public_and_backend_paths(), test_index_css_checkbox_override_is_not_none() (+7 more)

### Community 538 - "test_glm52_brain.py"
Cohesion: 0.12
Nodes (15): tests/test_glm52_brain.py — PR #984 Verifies GLM-5.2 (z-ai/glm-5.2) is…, packages/ai/registry.py must register z-ai/glm-5.2., GLM-5.2 must have a lower priority number (higher precedence) than…, packages/ai/brain.py DEFAULT_FREE_NVIDIA_MODEL must be z-ai/glm-5.2., packages/ai/brain_config.py SAFE_DEFAULT_MODEL must be z-ai/glm-5.2., PROVIDER_PRESETS['nvidia'] must use z-ai/glm-5.2 for all roles., render.yaml must set NVIDIA_DEFAULT_MODEL + AGENT_*_MODEL to z-ai/glm-5.2., backend/server.py must have the brain migration startup task. (+7 more)

### Community 539 - "test_local_brain_state.py"
Cohesion: 0.12
Nodes (10): tests/test_local_brain_state.py — regression test for the cross-machine toggle.…, Operator flips OFF — any prior lease must be dropped so a future ON doesn't…, The store must not corrupt the model listing when reading back., The 3 endpoints MUST refuse calls without SERVICE_TOKEN — confirmed by mounting…, All three endpoints must be present on the router (regression guard against…, store(), test_router_3_endpoints_are_registered(), test_router_endpoints_require_service_token() (+2 more)

### Community 540 - "test_phase5_doctor.py"
Cohesion: 0.12
Nodes (10): client(), tests/test_phase5_doctor.py Phase 5: /api/doctor endpoint tests. Coverage: -…, If RuntimeManager raises, /api/doctor still returns 200 with a warn check., If DirectChatDoctor.check_all raises, /api/doctor still returns 200., MongoStore.__getattr__ proxies any name to a Motor collection, so…, Langfuse check is always emitted (pass or warn based on env)., test_doctor_langfuse_check_present(), test_doctor_survives_preflight_error() (+2 more)

### Community 541 - "TestBrainFailoverBackoff"
Cohesion: 0.23
Nodes (7): The anti-wedge valve must not fire for an ordinary 429 backoff — otherwise it…, The threshold must clear the widest backoff ANY registered provider can earn.…, A corrupted/absurd cooldown must still be recoverable., The honest reset: probe permitted, failure history kept., A real success must still clear the breaker — allow_probe exists so that…, The behaviour the doom loop destroyed: each 429 waits longer. With…, TestBrainFailoverBackoff

### Community 542 - "test_telegram_diag_endpoint.py"
Cohesion: 0.12
Nodes (15): client(), tests/test_telegram_diag_endpoint.py — /api/telegram/diag HTTP endpoint.…, Build a TestClient against the FastAPI app with controlled env., The /api/telegram/diag endpoint returns 200., The endpoint returns the expected config fields., The endpoint must NOT return the full bot token — only a masked prefix., The endpoint includes diagnostic hints for common failure modes., The endpoint does not require authentication (it's a diagnostic tool). (+7 more)

### Community 543 - "test_google_provider_models.py"
Cohesion: 0.18
Nodes (7): The Google provider must only advertise models its endpoint actually serves.…, A role must never be assigned a model the picker does not list., An operator override of GEMINI_MODEL must appear in the picker. The catalog is…, The Doctor probe must target the path Gemini actually serves., test_configured_gemini_model_is_always_selectable(), test_google_role_models_are_offered_by_the_catalog(), test_liveness_probe_resolves_gemini_openai_compat_base()

### Community 544 - "_keyword_search"
Cohesion: 0.15
Nodes (13): Document, _keyword_search(), Return ``(doc_index, cosine_score)`` pairs for the top-*k* matches., Score documents by query-term coverage with a title-match boost., A single knowledge-base entry (wiki page, source document, etc.)., Return lowercase alphanumeric tokens with stop-words removed. Numeric tokens…, _tokenize(), _doc() (+5 more)

### Community 545 - "sam_livekit_worker.py"
Cohesion: 0.17
Nodes (16): LiveKitConfig, voice/livekit_config.py — LiveKit configuration (config module). Centralizes…, Resolved LiveKit + speech-provider configuration., True when the LiveKit room transport itself is usable., _build_llm(), _build_stt(), _build_tts(), entrypoint() (+8 more)

### Community 546 - "CollaborationContext"
Cohesion: 0.19
Nodes (4): CollaborationContext, Apply context updates from a contributor. Only the active editor can modify…, Shared context blob propagated to all session participants. Carries the active…, TestCollaborationContext

### Community 547 - "Skill: agent-harness"
Cohesion: 0.13
Nodes (14): Architecture, Combining with Other Skills, Key Concepts, Output Format, Purpose, Safety Rules, Skill: agent-harness, Step 1 — Define the task clearly (+6 more)

### Community 548 - "Skill: checkpoint-strategy"
Cohesion: 0.13
Nodes (14): After a Loss Spike, Aggressive (Long Runs with Stable Training), Background, Checkpoint Policy Templates, Conservative (Recommended for First Runs), Integration Points, Output Format, Purpose (+6 more)

### Community 549 - "Process"
Cohesion: 0.13
Nodes (14): Anti-Patterns, Process, Purpose, Rules, Skill: debug-tracer, Step 1: Reproduce First, Step 2: Gather Evidence, Step 3: Form Hypotheses (+6 more)

### Community 550 - "Skill: local-ai-query"
Cohesion: 0.13
Nodes (14): 1. Verify Ollama is available, 2. Choose appropriate model, 3. Send query to local model, 4. Generate embeddings (for RAG), 5. List running models, Integration with ChromaDB (RAG), Limitations, Prerequisites (+6 more)

### Community 551 - "Skill: parallel-agents"
Cohesion: 0.13
Nodes (14): Combining with Other Skills, Core Concepts (from the Modal/OpenAI Agents SDK pattern), Example — parallel approach exploration, Example — parallel research, Output Format, Phase 1 — Decompose, Phase 2 — Dispatch (simulate parallelism), Phase 3 — Aggregate (+6 more)

### Community 552 - "Skill: parallel-worktrees"
Cohesion: 0.13
Nodes (14): Acceptance Checks, Common Patterns, Concept, Constraints, Instructions, Pattern A — Test main while you implement, Pattern B — Review reference during refactor, Pattern C — Hotfix without disturbing feature work (+6 more)

### Community 553 - "Design System: Taste Standard"
Cohesion: 0.13
Nodes (14): 1. Visual Theme & Atmosphere, 2. Color Palette & Roles, 3. Typography Rules, 4. Component Stylings, 5. Hero Section, 6. Layout Principles, 7. Responsive Rules, 8. Motion & Interaction (Code-Phase Intent) (+6 more)

### Community 554 - "Process"
Cohesion: 0.13
Nodes (14): Integration with Other Skills, Process, Purpose, Rules, Skill: ticket-to-pr, Step 1: Parse the Issue, Step 2: Context Prime, Step 3: Plan the Implementation (+6 more)

### Community 555 - ".get_state"
Cohesion: 0.22
Nodes (9): _now_iso(), Any, Connection, Return the desired + last-reported state for the admin UI., Operator flips the toggle. Persists + clears any prior lease. Returns the new…, Local daemon POSTs its heartbeat. If the operator's desired_state=on AND the…, `now_iso`: ISO-8601 string marking the reader's "now" — pass it in to stay…, Reviewer fix #f: lease must strip after heartbeats stop arriving. Simulates a… (+1 more)

### Community 556 - "Skill: user-research"
Cohesion: 0.13
Nodes (14): Architecture, As a Python library, As an agent tool, Auto-Registration, Files, Purpose, Pydantic Models (extra="forbid"), Sample-Size Math (+6 more)

### Community 557 - "Agency Core — Progress & Resume Log"
Cohesion: 0.13
Nodes (14): Agency Core — Progress & Resume Log, Audit (committed), Environment constraints discovered this session, How to resume (read before doing anything), Key findings (so we don't re-investigate), Open risks / must-know before merging, Phase 0 — Stabilize & quarantine (commit `713184a`, pushed), Planned CI-parity hardening (the immediate next commit) (+6 more)

### Community 558 - "Attention Mechanisms Internals"
Cohesion: 0.13
Nodes (14): Attention Complexity, Attention Mechanisms Internals, Causal Masking, Flash Attention, Grouped Query Attention (GQA), Multi-Head Attention (MHA), Multi-Query Attention (MQA), Parameter count for MHA: (+6 more)

### Community 559 - "test_daily_2026_07_24.py"
Cohesion: 0.20
Nodes (7): is_strict(), Any, Structured output normalization across LLM providers. Translates the OpenAI…, Return True when the caller has requested strict schema enforcement. Strict…, Daily automation tests — 2026-07-24. Covers three features added in this…, is_strict() detects strict: true inside json_schema., TestIsStrict

### Community 560 - "_push_down_where"
Cohesion: 0.14
Nodes (14): _fully_pushable(), _is_pushable_scalar(), _push_down_where(), Any, Scalar values whose `str()` form matches how they were stored in the indexed…, Build a SQL ``WHERE`` suffix from the subset of *query* conditions that map…, True if EVERY condition in *query* is expressible in the SQL WHERE. Unlike…, Try to satisfy a sorted/paginated find entirely in SQL. Returns the decoded… (+6 more)

### Community 561 - "get_store"
Cohesion: 0.14
Nodes (23): _as_bool(), _as_int(), ephemeral_ttl_hours_cached(), get_setting(), _maybe_schedule_refresh(), onboarding_gate_enabled(), onboarding_gate_enabled_cached(), Any (+15 more)

### Community 562 - "_build_request"
Cohesion: 0.18
Nodes (7): _build_request(), Return ``(url, headers, is_anthropic_native)`` for *provider*. Anthropic's…, TestBuildRequest, Rotation needs the variable the key came from. Deriving it from the provider id…, No pool configured — the pre-rotation path, unchanged., Anthropic uses x-api-key, not Bearer — the override must reach it., TestBrainChainIntegration

### Community 563 - "clear_wizard_state_cache"
Cohesion: 0.21
Nodes (10): clear_wizard_state_cache(), Override the persistence collection used for wizard state. Tests and hosted…, Clear the in-memory wizard-state cache., set_wizard_state_collection(), _FakeWizardCollection, SimpleNamespace, TestClient, _setup_client() (+2 more)

### Community 564 - "e2e/test_browser.py"
Cohesion: 0.23
Nodes (14): base_url(), do_login(), fail(), ok(), Page, Navigate to a page and verify it loads without errors., Verify server responds to health check before running browser tests., Run full browser e2e suite. (+6 more)

### Community 566 - "_RedisBackend"
Cohesion: 0.22
Nodes (5): Redis-backed shared state using SET NX / DELETE / SETEX / INCR+EXPIRE., Lazy-create the Redis client (imported on first use so a missing ``redis``…, Clear all cooldown entries (for test teardown)., Clear all probe-lock entries (for test teardown). Mirrors…, _RedisBackend

### Community 567 - "test_dockerfile_ships_config_dir.py"
Cohesion: 0.14
Nodes (14): _dockerfile_text(), Regression guard: the backend image must ship ``config/``. `config/llm/*.yaml`…, The two properties that made the ungated entry expensive in production., The ceiling that #1172 added must survive in the file that ships. Sized against…, Without this COPY the router silently runs on defaults in production., A shipped directory is worthless if the files moved out of it., A .dockerignore entry would defeat the COPY without touching it., A keyless local provider must not join the chain just by existing. ``ollama``… (+6 more)

### Community 568 - "_run"
Cohesion: 0.42
Nodes (14): _make_env(), CompletedProcess, Path, _run(), test_crlf_preserved_on_untouched_lines(), test_dry_run_does_not_mutate(), test_env_path_missing_file_exits_1(), test_force_rewrites_canonical_already_present() (+6 more)

### Community 569 - "test_agent_free_brain.py"
Cohesion: 0.05
Nodes (32): livenim, allow_paid_brain(), True only when the operator explicitly opted into a paid (Anthropic) brain.…, Resolve the free NVIDIA NIM brain from env, or ``None`` if unconfigured.…, resolve_free_nvidia_brain(), _FakeAsyncClient, _FakeResponse, _free_env() (+24 more)

### Community 570 - "CLAUDE.md — Master Architect Operating Manual"
Cohesion: 0.20
Nodes (10): 0. The Golden Rule, 12. Changelog Rule, 13. Autonomous Development Policy, 2. Architectural Principles, 9. Coding Rules, Before writing any code, Before you read any source file: query graphify, CLAUDE.md — Master Architect Operating Manual (+2 more)

### Community 571 - "StopSlopChecker"
Cohesion: 0.14
Nodes (8): Initialize checker. Args: strict: If True, also report adverbs even if not in…, Remove most obvious AI tells from text, Detect and optionally remove AI tells from text, StopSlopChecker, Should format report correctly, Should report success on clean text, Should detect weak emphasis adverbs, Should detect meta-commentary

### Community 572 - "Process"
Cohesion: 0.14
Nodes (13): 1. Read and Understand the Issue, 2. Explore the Codebase, 3. Plan the Solution, 4. Implement, 5. Test, 6. Document, 7. Commit and Push, Notes (+5 more)

### Community 573 - "Skill: lr-schedule-advisor"
Cohesion: 0.14
Nodes (13): Background (Why This Matters), Common Mistakes, Cosine with Warmup (Recommended for Pretraining), Fine-tuning vs Pretraining, Integration Points, Output Format, Peak LR Heuristics by Model Size, Purpose (+5 more)

### Community 574 - "Instructions"
Cohesion: 0.14
Nodes (13): 1 — Tests green, 2 — Changelog updated, 3 — Determine the version bump, 4 — Update changelog, 5 — Commit the changelog update, 6 — Tag the release, 7 — Verify CI on the tag, 8 — Post-release (+5 more)

### Community 575 - "Instructions"
Cohesion: 0.14
Nodes (13): Acceptance Checks, `admin_auth.py` checklist, `agent/tools.py` checklist, Escalation, Instructions, `key_store.py` checklist, `proxy.py` auth middleware checklist, Risky Modules in This Repo (+5 more)

### Community 576 - "Process"
Cohesion: 0.14
Nodes (13): 1. Decompose the Task, 2. Sequence the Skills, 3. Execute in Order, 4. Handle Failures, 5. Synthesize Output, 6. Document the Composition, Example Compositions, Notes (+5 more)

### Community 577 - "Checks Performed"
Cohesion: 0.14
Nodes (13): 1. Round-trip Consistency, 2. Numeric Tokenization, 3. Whitespace Handling, 4. Special Character Coverage, 5. Fertility by Domain, 6. Vocabulary Overlap Check (for model updates), Background, Checks Performed (+5 more)

### Community 578 - "Skill: training-stability-monitor"
Cohesion: 0.14
Nodes (13): Example Checks Performed, Gradient Norm Check, Integration Points, Key Lessons (from LLM-from-scratch practitioners), Loss Spike Detection, LR Warmup Validation, Notes, Output Format (+5 more)

### Community 579 - "monitor_colibri.py"
Cohesion: 0.24
Nodes (13): ArgumentParser, build_parser(), cmd_autostart_install(), cmd_status(), cmd_supervise(), _configure_logging(), main(), Namespace (+5 more)

### Community 580 - "Skill: branch-cleanup"
Cohesion: 0.14
Nodes (13): Acceptance Checks, Automation — post-merge hook (optional), Option A — git push (standard), Option B — GitHub API (use when `git push --delete` returns 403), Option C — Delete local tracking refs after remote deletion, Skill: branch-cleanup, Step 1 — Confirm master is up to date, Step 2 — List all remote branches (+5 more)

### Community 581 - "Skill: perplexity — Web Research via Perplexity API"
Cohesion: 0.14
Nodes (13): Applying to this Repo, How to Query, No API Key? Use WebSearch, Prerequisites, Quick query (one-shot Python call), Run inline, Skill: perplexity — Web Research via Perplexity API, Skill Steps (+5 more)

### Community 582 - "Instructions"
Cohesion: 0.14
Nodes (13): 1 — Tests green, 2 — Changelog updated, 3 — Determine the version bump, 4 — Update changelog, 5 — Commit the changelog update, 6 — Tag the release, 7 — Verify CI on the tag, 8 — Post-release (+5 more)

### Community 583 - "Instructions"
Cohesion: 0.14
Nodes (13): Acceptance Checks, `admin_auth.py` checklist, `agent/tools.py` checklist, Escalation, Instructions, `key_store.py` checklist, `proxy.py` auth middleware checklist, Risky Modules in This Repo (+5 more)

### Community 584 - "Quick-Note Issues Processing Summary"
Cohesion: 0.14
Nodes (13): 🔗 Branch References, ✅ Completed, Future Session, Immediate (Session-Aware), Issue #229 — Stop-Slop AI Quality Checker, Issue #263 — Graphiti Temporal Context, Issue #266 — ECC Multi-Harness Adapter, 💡 Key Learnings (+5 more)

### Community 585 - "Implementation Plan — DB-persisted, UI-switchable Brain (no redeploy)"
Cohesion: 0.14
Nodes (13): 0. Why this exists (root cause this fixes), 1. Hard constraints (from the owner), 2. Provider strategy (the recommendation), 3. Architecture, 3a. Store — `services/brain_config_store.py` (new), 3b. Call-time resolution — `agent/loop.py`, 3c. Admin API — `backend/server.py`, 3d. UI — `webui/frontend/src/pages` (+ `webui/router.py` / `providers.py`) (+5 more)

### Community 586 - "Backend changes"
Cohesion: 0.14
Nodes (13): `activation_api.py`, `app_settings.py` (new), Backend changes, `backend/company_api.py`, `db/sqlite_store.py`, Docs / changelog, Frontend changes, Goal (+5 more)

### Community 587 - "Runbook: Auto-Resume After Cooldown / Interruption"
Cohesion: 0.14
Nodes (13): Commands, Cooldown Detection, Cooldown Detection Logic, Force-Resume After Stale Lock, Forcing an Abort, How It Works, Inspecting a Stuck Run, Overview (+5 more)

### Community 588 - "SEO / GEO / AIO Audit Engine"
Cohesion: 0.14
Nodes (14): API, Architecture, Delegation plan → agent tasks, Demo from the UI, Exports — the full heavy report, Fetching bot-protected sites (`fetch_mode`), Provenance, Repo-aware auto-fixing (+6 more)

### Community 589 - "devDependencies"
Cohesion: 0.14
Nodes (14): react-scripts, devDependencies, jsdom, react-scripts, @testing-library/dom, @testing-library/jest-dom, @testing-library/react, @testing-library/user-event (+6 more)

### Community 590 - "overrides"
Cohesion: 0.14
Nodes (14): @tootallnate/once, overrides, bfj, css-select, http-proxy-agent, jsonpath, nth-check, postcss (+6 more)

### Community 591 - "_parse_reset_epoch"
Cohesion: 0.21
Nodes (6): _parse_reset_epoch(), _ProviderQuota, Response, Parse x-ratelimit-* headers and update per-provider quota state. Safe to call…, Convert a provider reset-time header value to a monotonic deadline. Supported…, TestParseResetEpoch

### Community 592 - "test_brain_priority_scanner.py"
Cohesion: 0.14
Nodes (13): Regression tests for: brain-skip-paid, provider-priority persistence, scanner…, The PUT /api/providers/{id} endpoint did not persist priority edits because the…, scanner.py used to end with a bare `systems` statement at module level, which…, Priority must be an int (or None for unset) and within a sane range so a typo…, The PUT /api/providers/{id} handler does: for k, v in…, The model-layer test above only proves the Pydantic field works. A FastAPI body…, Defensive check: the file must not end with a stray `systems` line. Reading…, test_provider_update_accepts_priority_field() (+5 more)

### Community 593 - "test_onboarding_provisioning.py"
Cohesion: 0.15
Nodes (19): _ds(), _models(), _profiles(), asyncio, parametrize, End-to-end test: onboarding across all domain types provisions specialists…, Step 8 (activate_agency) must not block start_onboarding's response. Regression…, A detected system's type must show up as context on at least one agent. (+11 more)

### Community 594 - "cmd_autonomy"
Cohesion: 0.23
Nodes (13): _backend_get(), cmd_autonomy(), cmd_loops(), _grade_icon(), GET an un-gated backend read endpoint (/api/autonomy/status, /api/loops). These…, Snapshot of the agency's autonomy: active brain, loop readiness, dispatch., Loop Engineering fleet readiness + the costliest loops, from /api/loops., tests/test_telegram_observe.py Tests for the read-only "observe from Telegram"… (+5 more)

### Community 595 - "test_critical_flows.py"
Cohesion: 0.29
Nodes (13): _do_login(), _http_ok(), _playwright(), Create a task via the REST API (the same endpoint the UI calls) and poll its…, Direct (non-agent) chat: hit the OpenAI-compatible proxy completion the same…, Best-effort login. Returns True if we end up authenticated., _require_backend(), _require_proxy() (+5 more)

### Community 596 - "ApprovalGate"
Cohesion: 0.18
Nodes (7): WorkflowEngine, Create a run and manually place it in awaiting_approval., Contract: Can approve a run in 'awaiting_approval' state., Contract: Rejecting a run marks it as failed., TestApprovalGate, ApprovalGate, Hard approval gate between plan and execution. The workflow engine sets…

### Community 597 - "OutputFilter"
Cohesion: 0.20
Nodes (7): _count_remaining(), _filter_generic(), OutputFilter, Token-optimizing output filter for command stdout. Usage:: from output_filter…, Filter *stdout* from *command* for token efficiency. If FILTER_ENABLED is…, Generic compression for unrecognized commands., _truncate()

### Community 598 - "test_openclaw_gateway.py"
Cohesion: 0.14
Nodes (4): tests/test_openclaw_gateway.py — OpenClaw in-process WebSocket gateway tests., Dockerfile.backend does NOT install @openclaw/cli (in-process gateway now)., render_yaml(), test_dockerfile_backend_no_openclaw_cli()

### Community 599 - "TestExtendedThinkingRouting"
Cohesion: 0.20
Nodes (6): Unit tests for extended thinking detection in handle_anthropic_messages., When thinking.type == enabled, routing should use agent_plan endpoint type., No thinking param → normal chat routing, not forced to reasoning., thinking_budget_tokens should appear in routing_meta when thinking is set., Without thinking param, thinking_budget_tokens not in routing_meta., TestExtendedThinkingRouting

### Community 600 - "router/health.py"
Cohesion: 0.20
Nodes (14): _enabled(), get_available_models(), invalidate_cache(), is_model_available(), Ollama model availability check with TTL cache. Keeps a short-lived cache of…, Force the next call to re-probe Ollama (useful in tests)., Return True if *model* is in the Ollama tag list (or health checks off).…, Return the set of model names currently present in Ollama. Returns an empty set… (+6 more)

### Community 601 - "open_phase_report"
Cohesion: 0.13
Nodes (21): note_phase_end(), note_phase_start(), _now(), open_phase_report(), Monotonic clock, behind an indirection so tests can freeze it. Patching…, Record that *phase* began; returns the token that ends it. Called from…, Close the invocation identified by *token*. Never raises., Describe the phases currently in flight, innermost (newest) first. A phase that… (+13 more)

### Community 602 - "Process"
Cohesion: 0.15
Nodes (12): Output Format, Process, Purpose, Rules, Skill: auto-fix, Step 1: Discover Fix Commands, Step 2: Run Fixers (Auto-fixable), Step 3: Run Checkers (Non-auto-fixable) (+4 more)

### Community 603 - "Skill: Brain Dump"
Cohesion: 0.15
Nodes (12): Example Prompt to Trigger, Instructions, Notes, Output Format, Purpose, Skill: Brain Dump, Step 1: Capture Everything, Step 2: Categorize (+4 more)

### Community 604 - "Process"
Cohesion: 0.15
Nodes (12): Process, Purpose, Rules, Skill: context-prime, Step 1: Read Core Docs, Step 2: Map the Architecture, Step 3: Find Conventions, Step 4: Understand Data Flow (+4 more)

### Community 605 - "Instructions"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Instructions, Role 1: Security Reviewer, Role 2: Correctness Reviewer, Role 3: Performance Reviewer, Role 4: Maintainability Reviewer, Skill: council-review, Step 1 — Gather the diff (+4 more)

### Community 606 - "Skill: duplicate-thread"
Cohesion: 0.15
Nodes (12): Files, How It Works, In a Claude prompt, Integration, Manual duplication, Merging Back, meta.json Schema, Purpose (+4 more)

### Community 607 - "Skill: Email Triage"
Cohesion: 0.15
Nodes (12): Example Prompt to Trigger, Instructions, Notes, Output Format, Purpose, Skill: Email Triage, Step 1: Intake, Step 2: Triage Categories (+4 more)

### Community 608 - "Process"
Cohesion: 0.15
Nodes (12): Anti-Patterns, Process, Purpose, Rules, Skill: feature-flag, Step 1: Assess Flag Need, Step 2: Define the Flag, Step 3: Implement the Guard (+4 more)

### Community 609 - "Process"
Cohesion: 0.15
Nodes (12): 1. Review Staged and Unstaged Changes, 2. Review Commit History, 3. Validate Commit Messages, 4. Clean Up if Needed, 5. Confirm Branch State, 6. Push, Notes, Output (+4 more)

### Community 610 - "Skill: graphify — Knowledge Graph Token Optimization"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Claude's query protocol (use this instead of Read tool for exploration):, Graph Artifacts — What to Commit, How to Use the Graph (Token Savings Protocol), Installation (one-time per machine), Instead of reading raw files:, Key commands:, Relationship to repowise-intelligence Skill (+4 more)

### Community 611 - "Skill: prompt-library"
Cohesion: 0.15
Nodes (12): 1. Sync Snapshots, 2. Generate Library Index, 3. Generate TRANSPARENCY.md, 4. Update CHANGELOG.md in prompts/, 5. Commit, Directory Structure Created, Output, Purpose (+4 more)

### Community 612 - "Skill: prompt-transparency"
Cohesion: 0.15
Nodes (12): 1. Collect All Agent & Skill Definitions, 2. Extract Key Behavioral Dimensions, 3. Generate Transparency Report, 4. Flag Risks, 5. Commit the Report, Example Usage, Inspiration, Output Format (+4 more)

### Community 613 - "Skill: Research"
Cohesion: 0.15
Nodes (12): Example Prompt to Trigger, Instructions, Notes, Output Format, Purpose, Skill: Research, Step 1: Define the Research Question, Step 2: Identify Source Categories (+4 more)

### Community 614 - "Skill: scope-guard"
Cohesion: 0.15
Nodes (12): Anti-Patterns to Avoid, Output Format, Process, Purpose, Rules, Skill: scope-guard, Step 1: Define the Scope Contract, Step 2: Pre-Implementation Check (+4 more)

### Community 615 - "test_new_features_e2e.py"
Cohesion: 0.32
Nodes (11): APIRequestContext, base_url(), do_login(), fail(), ok(), Page, Result, run_tests() (+3 more)

### Community 616 - "TestKillSwitchDurability"
Cohesion: 0.15
Nodes (4): The local mirror is what keeps operator intent during a Mongo outage., A restart clears every in-memory cache; the state must still be there., Never claim a switch took effect when no store accepted it. Mongo off…, TestKillSwitchDurability

### Community 617 - "Instructions"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Instructions, Role 1: Security Reviewer, Role 2: Correctness Reviewer, Role 3: Performance Reviewer, Role 4: Maintainability Reviewer, Skill: council-review, Step 1 — Gather the diff (+4 more)

### Community 618 - "Skill: graphify — Knowledge Graph Token Optimization"
Cohesion: 0.15
Nodes (12): Acceptance Checks, Claude's query protocol (use this instead of Read tool for exploration):, Graph Artifacts — What to Commit, How to Use the Graph (Token Savings Protocol), Installation (one-time per machine), Instead of reading raw files:, Key commands:, Relationship to repowise-intelligence Skill (+4 more)

### Community 619 - "Skill: platform-setup — Autonomous Agency Bootstrap"
Cohesion: 0.15
Nodes (12): Ongoing autonomous operation, Phase 1 — Verify deployment health (no auth needed), Phase 2 — Login as admin, Phase 3 — Onboard the platform itself as a company, Phase 4 — Verify specialists were provisioned, Phase 5 — Configure GitHub integration, Phase 6 — Trigger first agency cycle manually, Phase 7 — Verify autonomous schedule is active (+4 more)

### Community 620 - "Device compatibility and model picks"
Cohesion: 0.15
Nodes (12): Acceleration at a glance, Apple Silicon: chip tier vs bandwidth (qualitative), Desktops and workstations, Device compatibility and model picks, Edge cases, How to read memory on different platforms, Laptops and all-in-ones, NVIDIA examples by VRAM (CUDA) (+4 more)

### Community 621 - "Autonomy Uplift — Living Roadmap & Detailed Implementation Specs"
Cohesion: 0.15
Nodes (12): 0. The goal (operator's words), 1. Shipped ✅, 2. In flight 🟡, 3. Pending ⬜ — detailed implementation specs, 3a. Apply the slop-gate to the sibling auto-PR scripts ✅  (size: S), 3b. Hermes — **our own** Hermes server (in-repo), UI-wired ✅  (size: M), 3c. CRISPY — harden, then re-enable ✅  (size: L, risky-module-review), 3d. Phase 3 — auto-PR *quality* beyond the slop-gate ✅  (size: M) (+4 more)

### Community 622 - "OpenClaw — iOS Control of the Agency (Single-Service Free-Tier Deploy)"
Cohesion: 0.15
Nodes (12): 1. Set env vars on the existing `local-llm-server` service, 2. Deploy, 3. Check the status, 4. Get the pairing QR, 5. Pair and verify, Alternative: Telegram bot, Architecture (single-service), Free-tier caveats (+4 more)

### Community 623 - "rules"
Cohesion: 0.15
Nodes (12): rules, import/no-anonymous-default-export, jsx-a11y/anchor-is-valid, jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions, jsx-a11y/no-static-element-interactions, no-console, no-template-curly-in-string (+4 more)

### Community 624 - "Summary"
Cohesion: 0.15
Nodes (12): Checklist, Rollout notes, Summary, Test plan, UNIT 1 — Fix duplicate ceo_direct tasks ✅, UNIT 2 — Portfolio → task materializer (default ON) ✅, UNIT 3 — Config hygiene (zero behavior change) ✅, UNIT 4 — Commit model catalog `config/models.yaml` ✅ (+4 more)

### Community 625 - "Agent Transparency Report"
Cohesion: 0.15
Nodes (12): Agent Transparency Report, Guardrails and Limits, How to Verify This, Human Oversight Points, 🔨 Implementer, ⚖️ Judge, 📋 Planner, 🔍 Reviewer (+4 more)

### Community 626 - "update_provider_policy"
Cohesion: 0.19
Nodes (12): _get_provider_policy(), ProviderPolicyUpdate, BaseModel, get, put, Read the durable provider policy, falling back to a safe default. Returns a…, Persist the provider policy and return the new state., Return the durable provider policy (single source of truth for paid-provider… (+4 more)

### Community 627 - ".publish"
Cohesion: 0.17
Nodes (7): Any, Task, Broadcast an event to all matching subscribers. Returns the number of callbacks…, Fire-and-forget publish. Creates a background task. Returns the asyncio.Task so…, Return recent events for a topic., Return bus statistics., Check if a topic matches a pattern with * and ** wildcards.

### Community 628 - "_InMemoryBackend"
Cohesion: 0.11
Nodes (15): _InMemoryBackend, Single-process backend using asyncio.Lock + dicts with TTL timestamps., Clear all cooldown entries (for test teardown)., Clear all probe-lock entries (for test teardown). ``cooldown_clear`` only…, _auth_headers(), _login_via_email(), Any, tests/test_providers_live_e2e.py — Live integration test for… (+7 more)

### Community 629 - "TestModelCostTableUpdates"
Cohesion: 0.26
Nodes (3): New models are present in the cost table with sensible prices., get_cost_table() API exposes the new models with correct structure., TestModelCostTableUpdates

### Community 630 - "TestDecisionsBotLinks"
Cohesion: 0.17
Nodes (5): # NOTE: ``decision_id`` is NOT a SQL FOREIGN KEY here. The bot's, tests/test_decisions_bot_links.py Pytest coverage for the new…, Decision prompts that exist *before* the orchestrator creates a run (e.g. a…, Re-sending the same Telegram message (offset rewind, bot restart re-delivery)…, TestDecisionsBotLinks

### Community 631 - "test_deploy_trigger_covers_image.py"
Cohesion: 0.21
Nodes (12): _image_copy_sources(), Regression guard: the Render deploy trigger must cover everything the image…, `packages/` holds the AI layer — the most deploy-sensitive code there is., The health step must be able to fail. It previously polled for any 200 starting…, Top-level paths ``Dockerfile.backend`` copies into the runtime image., Top-level path prefixes in the deploy workflow's push ``paths:`` filter., The filter must take root modules wholesale, matching `COPY *.py ./`. Listing…, test_deploy_verification_cannot_pass_silently_on_failure() (+4 more)

### Community 632 - "test_task_source_id_race.py"
Cohesion: 0.17
Nodes (18): _is_duplicate_key_error(), Exception, True if *exc* is a pymongo E11000 duplicate-key error. Checked by class name…, _FakeDuplicateKeyError, _mock_mongo_db(), asyncio, Exception, tests/test_task_source_id_race.py — TaskStore.create() concurrency safety.… (+10 more)

### Community 633 - "cleanup_stale_jobs"
Cohesion: 0.31
Nodes (8): cleanup_stale_jobs(), _is_stale(), Any, packages/scheduler/cleanup.py — schedule deduplication + stale removal.…, Remove a job from the store. Returns True on success, False on failure. Logs…, Check if a created_at timestamp is older than ttl_seconds. Handles multiple…, Remove stale run-once + stuck agency jobs from the durable store. Args: store:…, _safe_remove()

### Community 634 - "PortfolioManager"
Cohesion: 0.04
Nodes (31): CapacityAllocation, PortfolioManager, Result of fitting initiatives into a fixed capacity by WSJF priority., Total job size of initiatives that fit within capacity., Unused capacity after committing the selected initiatives., Fraction of capacity consumed (0.0–1.0)., Manages a portfolio of initiatives with WSJF prioritisation and roadmapping., Create and register a new initiative, returning it. (+23 more)

### Community 635 - "test_skill_executors_live.py"
Cohesion: 0.16
Nodes (17): Live Graphify executor — queries the codebase knowledge graph. Order of…, Live council reviewer — deterministic, rules-based multi-perspective review…, _run_council_review(), _run_graphify(), parametrize, tests/test_skill_executors_live.py — live graphify + council-review executors.…, Broadened secret detection catches SECRET_KEY / GITHUB_TOKEN / etc. The…, test_council_clean_diff_is_approved() (+9 more)

### Community 636 - "WorkspaceManifest"
Cohesion: 0.17
Nodes (8): _now(), Any, BaseModel, WorkspaceStatusLiteral, Structured manifest for an isolated workspace., Transition to a new status and update cleanup eligibility., Touch the last_heartbeat timestamp., WorkspaceManifest

### Community 637 - "CLAUDE.md — agent/"
Cohesion: 0.17
Nodes (11): Adding New Tools, `agent/loop.py` — `_commit_step()`, `agent/loop.py` — `_local_safety_check()`, `agent/tools.py` — `apply_diff()`, CLAUDE.md — agent/, Invariants — Do Not Break, Model Env Vars, Security Surface (+3 more)

### Community 638 - "skill_registry.py"
Cohesion: 0.17
Nodes (6): agent/skill_registry.py — Dynamic Skill Registry & Recommender Fetches skill…, Holds a pre-compiled regex + the original tech name., set_skill_registry(), _TechPattern, Tests for module-level pre-compiled pattern constants., TestPreCompiledPatterns

### Community 639 - "Trajectory"
Cohesion: 0.20
Nodes (7): Path, Persist trajectory as JSON and return the file path., Reload a previously saved trajectory (read-only replay)., Return a summary dict suitable for logging / leaderboards., Complete record of one agent run against one task. Compatible with the…, Mark the trajectory as complete., Trajectory

### Community 640 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Idempotency Rules, Instructions, Skill: cooldown-resume, Step 1 — Read the checkpoint files, Step 2 — Assess the state, Step 3 — Verify changed files are correct, Step 4 — Run tests to confirm baseline (+3 more)

### Community 641 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Current Dependencies (quick reference), Instructions, Skill: dependency-audit, Step 1 — Evaluate the new dependency, Step 2 — Pin appropriately, Step 3 — Install and verify, Step 4 — Check for conflicts (+3 more)

### Community 642 - "Process"
Cohesion: 0.17
Nodes (11): 1. Audit Existing Skills, 2. Identify Gaps, 3. Propose Improvements, 4. Implement, 5. Validate, Notes, Output, Process (+3 more)

### Community 643 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Instructions, Skill: smart-commit, Step 1 — Confirm changelog is updated, Step 2 — Run tests, Step 3 — Check for obvious issues, Step 4 — Stage your changes, Step 5 — Write a conventional commit message (+3 more)

### Community 644 - "Skill: system-prompt-audit"
Cohesion: 0.17
Nodes (11): 1. Inventory Collection, 2. Consistency Check, 3. Safety Check, 4. Generate Audit Report, 5. Exit Codes, Integration, Purpose, Related Skills (+3 more)

### Community 645 - "Skill: task-alive-updates"
Cohesion: 0.17
Nodes (11): Example Output, Files, How It Works, Implementation Rules, In a shell script / agent harness, In Claude task descriptions, Integration with parallel-agents, Purpose (+3 more)

### Community 646 - "Process"
Cohesion: 0.17
Nodes (11): 1. Read the Task Carefully, 2. Define the Boundary, 3. Identify Temptations, 4. Lock the Scope, 5. Out-of-Scope Findings, Notes, Output, Process (+3 more)

### Community 647 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Instructions, Skill: test-first-executor, Step 1 — Identify what needs testing, Step 2 — Write the test first, Step 3 — Confirm the test FAILS before implementation, Step 4 — Implement until the test passes, Step 5 — Run the full suite (+3 more)

### Community 648 - "LocalBrainStore"
Cohesion: 0.21
Nodes (8): BaseModel, backend/admin_local_brain_router.py — admin-session proxy for the local-brain…, _store(), ToggleBody, LocalBrainStore, backend/local_brain_store.py — DB-persisted state for the local GLM 5.2 brain.…, SQLite-backed store for the local GLM brain toggle + heartbeat., Same mirror file brain_config already uses. One file, fewer surprises.

### Community 649 - "test_bootstrap_source_id_index.py"
Cohesion: 0.27
Nodes (9): asyncio, tests/test_bootstrap_source_id_index.py — _ensure_tasks_source_id_unique_index.…, A unique-index build against a collection with pre-existing duplicate source_id…, The proactive dedup pass must run before the index-build attempt, so a first-…, If the proactive dedup pass itself fails (e.g. store not wired up yet), the…, test_dedup_failure_does_not_block_index_attempt(), test_dedup_pass_runs_before_index_build(), test_index_build_failure_does_not_raise() (+1 more)

### Community 650 - "Workspace Isolation Architecture"
Cohesion: 0.17
Nodes (12): Configuration, Directory Layout, Error Handling, Lifecycle States, Metrics, Overview, Path Derivation, Path Safety (+4 more)

### Community 651 - "admin.py"
Cohesion: 0.18
Nodes (5): AdminSession, AdminSessionStore, _is_truthy(), admin_auth.py — auto-generated module docstring (user-research skill scan)., WindowsCredentialAuthenticator

### Community 652 - "Skill: agent-browser — Real Chrome Browser Automation"
Cohesion: 0.17
Nodes (11): Applying to the local-llm-server Platform, Core Commands, How to Use This Skill, Installation (one-time), Skill: agent-browser — Real Chrome Browser Automation, Step 1 — Check Chrome is running with debugging, Step 2 — Navigate and snapshot, Step 3 — Interact using element refs (+3 more)

### Community 653 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Idempotency Rules, Instructions, Skill: cooldown-resume, Step 1 — Read the checkpoint files, Step 2 — Assess the state, Step 3 — Verify changed files are correct, Step 4 — Run tests to confirm baseline (+3 more)

### Community 654 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Current Dependencies (quick reference), Instructions, Skill: dependency-audit, Step 1 — Evaluate the new dependency, Step 2 — Pin appropriately, Step 3 — Install and verify, Step 4 — Check for conflicts (+3 more)

### Community 655 - "Skill: dev-browser — Browser Automation via Sandboxed JS"
Cohesion: 0.17
Nodes (11): Browser API, CLI flags, Connect to existing Chrome, Full script example (Playwright Page API), Installation, LLM usage patterns, Performance, Primary invocation styles (+3 more)

### Community 656 - "Instructions"
Cohesion: 0.17
Nodes (11): Acceptance Checks, Instructions, Skill: test-first-executor, Step 1 — Identify what needs testing, Step 2 — Write the test first, Step 3 — Confirm the test FAILS before implementation, Step 4 — Implement until the test passes, Step 5 — Run the full suite (+3 more)

### Community 657 - "Agent Orchestration Design"
Cohesion: 0.17
Nodes (12): Agent Orchestration Design, Execution Pathway, Four-Agent Structure, Key Invariants, OSS Inspirations (Clean-Room), Overview, Plan-First Pathway, Release-Readiness Pathway (+4 more)

### Community 658 - "Universality: case-coverage matrix"
Cohesion: 0.17
Nodes (12): A. Connection & credentials, B. Provider & host, C. Delivery / branch policy  *(detected — see DeliveryPolicy)*, D. CI / checks, E. Review automation & humans, F. Repo state & conflicts, G. Task origin, H. Governance / safety / HITL (+4 more)

### Community 659 - "Any"
Cohesion: 0.29
Nodes (3): Any, Release control if the active editor is idle > 30s., Run one sync tick across all sessions. Actions taken: - Kick idle active…

### Community 660 - "Quantization Internals"
Cohesion: 0.17
Nodes (12): Absmax Quantization (Symmetric), Activation Quantization, AWQ (Activation-Aware Weight Quantization), Bits and Bytes (bitsandbytes), Data Types, GGUF / llama.cpp Quantization, GPTQ (Post-Training Quantization for GPT), Post-Training Quantization (PTQ) (+4 more)

### Community 661 - "Implementation — DB-persisted, UI-switchable Brain (PR #824 follow-up)"
Cohesion: 0.17
Nodes (11): Architecture (per plan §3), Files touched, Hard constraints (from the plan) — all met, Implementation — DB-persisted, UI-switchable Brain (PR #824 follow-up), Modified files, New files, Resolution precedence, Risks & mitigations (per plan §6) (+3 more)

### Community 662 - "2. Pending ⬜ — detailed implementation specs"
Cohesion: 0.17
Nodes (11): 0. The goal (unchanged), 1. Shipped in the previous pass ✅ (recap, do not redo), 2. Pending ⬜ — detailed implementation specs, 3. Deferred 🔭, 4. Operating notes (unchanged, for implementers), N1. Activate the reliability spine — wire the watchdog, schedule the digest ⬜  (size: M, risk: low), N2. Surface Hermes (and all runtimes) status in the Doctor/Runtimes UI ⬜  (size: S, risk: low), N3. Real CI-failure autofix — close the "Agency: cannot fix tests" loop (issue #398) ✅  (size: L, risk: medium) (+3 more)

### Community 663 - "467 Public Site Truth Spec"
Cohesion: 0.17
Nodes (11): 467 Public Site Truth Spec, Architecture Page Truth, Content Rules, Current State, Feature Matrix Truth, Required: Public Site Truth Spec, Site Structure, Tier System for Features (+3 more)

### Community 664 - "Render MCP — autonomous platform debugging and environment monitoring"
Cohesion: 0.14
Nodes (13): 1. Coding sessions — stdio, via `.mcp.json`, 2. The running agency — Streamable HTTP against a deployed sidecar, Configuration, Enabling it, HTTP API, If the private address does not resolve, Playwright, Render MCP — autonomous platform debugging and environment monitoring (+5 more)

### Community 665 - "GovernanceScreen.jsx"
Cohesion: 0.18
Nodes (6): OBSERVE_STATUS, AuditTable(), BACKEND_META, DECISION_COLOR, relTime(), GovernanceScreen

### Community 666 - "TestParsing"
Cohesion: 0.22
Nodes (5): parametrize, Includes a bare 404 with an empty body (observed on NVIDIA NIM) — no…, A malformed listing must never be read as "the key serves nothing"., TestParsing, TestUnknownModelDetection

### Community 667 - "extract_refusal"
Cohesion: 0.27
Nodes (4): extract_refusal(), Extract the ``refusal`` string from an OpenAI-format response body. Returns the…, extract_refusal() surfaces model refusals from provider response bodies., TestExtractRefusal

### Community 668 - "test_p0_roadmap_a4_a5_b2.py"
Cohesion: 0.26
Nodes (6): get_steering_injector(), Return recommended steering labels for a given task category. Used by the model…, Return the module-level SteeringInjector singleton., steering_for_task(), TestSteeringForTask, TestSteeringSingleton

### Community 669 - "check_container_posture.py"
Cohesion: 0.26
Nodes (11): check_compose(), check_policy_baseline(), check_sandbox_profiles(), _load_yaml(), main(), Any, Path, scripts/check_container_posture.py — assert the container security posture. CI… (+3 more)

### Community 670 - "Kimi Web-Bridge Service"
Cohesion: 0.17
Nodes (11): API, Connecting to the Main Backend, Docker, Environment Variables, `GET /health`, `GET /v1/models`, How It Works, Kimi Web-Bridge Service (+3 more)

### Community 671 - "test_regression.py"
Cohesion: 0.13
Nodes (13): browser_login(), main(), Full desktop regression suite., Full mobile regression suite (navigation + key page loads)., Log in through the browser UI. Returns True on success., Wiki pages: create, view, edit, delete, search, lint., Tasks: create, list, view., regression_base_url() (+5 more)

### Community 672 - "test_agile_api.py"
Cohesion: 0.17
Nodes (3): auth_headers(), Tests for /api/agile/* endpoints., Get auth headers for the seeded admin user (matched to seed_admin email).

### Community 673 - "test_app_settings.py"
Cohesion: 0.21
Nodes (10): asyncio, Tests for app_settings — DB-persisted settings + onboarding-gate default. These…, Point db.get_store() at an isolated temp SQLite DB., is_user_onboarding_allowed falls back to the global default for users with no…, sqlite_store(), test_defaults_when_unset(), test_gate_default_controls_unlisted_user(), test_refresh_cache_warms_sync_readers() (+2 more)

### Community 674 - "ContributorState"
Cohesion: 0.25
Nodes (3): ContributorState, Request editing control. Returns True if granted. Grant rules: - Host can…, State of a single contributor within a session.

### Community 675 - "test_skill_registry.py"
Cohesion: 0.20
Nodes (7): _FakeClient, _FakeResp, tests/test_skill_registry.py — Unit tests for agent/skill_registry.py, Stub httpx client for nested-registry fetch tests., Production regression: server started from a non-repo CWD indexed 0 local…, test_local_skills_dir_defaults_to_repo_root_not_cwd(), test_nested_registry_indexes_deeply_nested_skills()

### Community 676 - "TestAnthropicPayloadStructuredOutput"
Cohesion: 0.29
Nodes (3): _payload(), Tests for packages/ai/structured_output.py and its integration with the…, TestAnthropicPayloadStructuredOutput

### Community 677 - "test_task_clarification.py"
Cohesion: 0.17
Nodes (3): auth_headers(), Tests for needs_clarification status and /api/tasks/{id}/clarify endpoint., Get auth headers for an admin user.

### Community 678 - "validate_job_id"
Cohesion: 0.18
Nodes (4): parametrize, TestPathTraversalPrevention, Validate and return a job ID, or raise InvalidJobIdError., validate_job_id()

### Community 679 - "EvalHarness"
Cohesion: 0.24
Nodes (7): EvalHarness, Task, Runs agent functions against Tasks, records Trajectories and produces…, Execute the agent on a single task and return an EvalResult., Delegate to the agent callable (sync or async)., Run multiple tasks and aggregate into a BenchmarkReport. Set concurrency > 1 to…, AgentFn

### Community 680 - "DecisionsStore"
Cohesion: 0.30
Nodes (3): DecisionsStore, Any, Connection

### Community 681 - "_extractive_compress"
Cohesion: 0.18
Nodes (11): _extractive_compress(), Split text into sentences on . ! ? followed by whitespace or end-of-string., Return the highest-value sentences from *text* within *max_tokens*. Each…, _split_sentences(), test_compress_empty_text(), test_compress_prefers_query_relevant_sentences(), test_compress_result_non_empty_for_non_empty_input(), test_compress_short_text_verbatim() (+3 more)

### Community 682 - "RegistrySkill"
Cohesion: 0.25
Nodes (6): Any, A skill fetched from a remote or local registry., Return ranked skill recommendations based on tech stack, active workflow types,…, RegistrySkill, Tests for RegistrySkill dataclass., TestRegistrySkill

### Community 683 - "key_store.py"
Cohesion: 0.20
Nodes (11): _check_rate_limit(), default_keys_path(), load_key_store(), Exception, Path, RateLimitError, Persistent API key store: each key maps to email + department (seat) and a…, Raised when an IP exceeds the failed-key-lookup rate limit. (+3 more)

### Community 684 - "AdminDigestRouterAuthTests"
Cohesion: 0.23
Nodes (5): DigestPayload, AdminDigestRouterAuthTests, Stub for telegram_service.NotificationDispatcher used by /send., Build a FastAPI TestClient against an app shell with only the…, _StubDispatcher

### Community 685 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Failure / Retry Behaviour, Instructions, Skill: implementation-planner, Step 1 — Understand the current state, Step 2 — Write the plan, Step 3 — Get implicit approval before coding, Step 4 — Implement (+2 more)

### Community 686 - "Skill: pro-workflow"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Model Selection Guide, Phase 1 — Research (Scout), Phase 2 — Plan, Phase 3 — Implement, Phase 4 — Wrap Up, Skill: pro-workflow (+2 more)

### Community 687 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Learnings File Doesn't Exist?, Skill: replay-learnings, Step 1 — Read the learnings file, Step 2 — Filter relevant learnings, Step 3 — Check recent checkpoint history, Step 4 — Surface blockers from previous session (+2 more)

### Community 688 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Skill: repo-memory-updater, Step 1 — Inventory what changed, Step 2 — Check root AGENTS.md, Step 3 — Check module AGENTS.md files, Step 4 — Update .Codex/state/, Step 5 — Commit the update (+2 more)

### Community 689 - "Skill: resource-panel"
Cohesion: 0.18
Nodes (10): Ask Claude to emit a resource panel, Automated via shell (git-based), Fields, Files, How to Use, Integration, Output Format, Purpose (+2 more)

### Community 690 - "Skill: sandboxed-exec"
Cohesion: 0.18
Nodes (10): Example — run tests in isolation, Example — validate a generated script before saving, How It Works, Output Format, Purpose, Security Notes, Skill: sandboxed-exec, Steps (for Claude to follow) (+2 more)

### Community 691 - "Workflow"
Cohesion: 0.18
Nodes (10): Acceptance checks, Fill these in, Skill: client-onboarding, Step 1 — Create the company and kick off onboarding, Step 2 — Poll progress, Step 3 — Verify specialists were provisioned, Step 4 — Confirm the 24x7 agency runtime is live, Step 5 — Note real gaps instead of pretending they're solved (+2 more)

### Community 692 - "ECC Harness Patterns Skill"
Cohesion: 0.18
Nodes (10): 1. Harness Detection & Adaptation, 2. Session Lifecycle Hooks, 3. Cross-Harness Model Selection, 4. Persistent Harness Registry, ECC Harness Patterns Skill, Files to Create/Modify, Implementation Plan, Patterns to Adopt (+2 more)

### Community 693 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Failure / Retry Behaviour, Instructions, Skill: implementation-planner, Step 1 — Understand the current state, Step 2 — Write the plan, Step 3 — Get implicit approval before coding, Step 4 — Implement (+2 more)

### Community 694 - "Instructions"
Cohesion: 0.18
Nodes (10): Acceptance Checks, Instructions, Skill: repo-memory-updater, Step 1 — Inventory what changed, Step 2 — Check root CLAUDE.md, Step 3 — Check module CLAUDE.md files, Step 4 — Update .claude/state/, Step 5 — Commit the update (+2 more)

### Community 695 - "Stop-Slop Quality Skill"
Cohesion: 0.18
Nodes (10): AI Tells Detected, Business Jargon, Emphasis Crutches (Banned Adverbs), Implementation, Integration Points, Meta-Commentary, References, Stop-Slop Quality Skill (+2 more)

### Community 696 - "14. Standing Instructions — Universal Agent Discipline"
Cohesion: 0.17
Nodes (12): 14.10 Fake Competence — the 10 Patterns, 14.11 Final Gate — run on every answer before sending, 14.1 Reading Intent, 14.2 Breaking Problems Down, 14.3 Effort Placement, 14.4 Verification, 14.5 Known vs Guessed, 14.6 Self-Attack (+4 more)

### Community 697 - "Agency Core — Ruthless Architecture Audit & Migration Plan"
Cohesion: 0.18
Nodes (10): Acceptance check, Agency Core — Ruthless Architecture Audit & Migration Plan, Root causes (not symptoms), Section 1 — The Brutal Truth, Section 2 — Keep / Salvage / Replace / Remove, Section 3 — The Chosen Foundation, Section 4 — The New Agency Core, Section 5 — Migration Plan (minimal chaos, all on PR, CI green at each step) (+2 more)

### Community 698 - "AUTONOMY_CHARTER.md"
Cohesion: 0.18
Nodes (6): How to add or change a loop, LOOP.md — The loops that run this agency, Maturity ladder, The five building blocks (and how this repo realises them), The three operator tools (`agent/loop_registry.py`), Why this exists

### Community 699 - "Tailored Onboarding, Editable Companies & Dynamic Roles"
Cohesion: 0.18
Nodes (10): 1. Editable companies, anytime (not a one-shot wizard), 2. Question-driven provisioning — no cosmetic questions, 3. Dynamic, expandable roles (open registry, not a closed enum), 4. Agents start pre-powered, Invariants, Phases, Tailored Onboarding, Editable Companies & Dynamic Roles, The gaps to close (+2 more)

### Community 700 - "Issue #467 — Section 1: Pulled State + PR Inventory"
Cohesion: 0.18
Nodes (10): 1. Current Git State, 2. Open PRs (as of 2026-06-08), 3. Files Modified on consolidate/maturation-stable (vs master), 4. What Master Has (that consolidate doesn't), 5. What Is MISSING from master (0% delivered in #467), 6. Required Action Before Code, Branch: `consolidate/maturation-stable`, Issue #467 — Section 1: Pulled State + PR Inventory (+2 more)

### Community 701 - "Autonomy Charter — Telegram-Gated Self-Running Agency"
Cohesion: 0.18
Nodes (11): 1. Mission & operating principles, 2. Brain policy (free cloud LLMs), 3. The Gate Matrix (core artifact), 4. Telegram gate protocol, 6. Integration gaps to wire (follow-up implementation), 7. Definition of "fully autonomous" — acceptance criteria, 8. Safety invariants (carried from `agent/CLAUDE.md`), 🟢 Autonomous — run, then notify-only (+3 more)

### Community 702 - "Context: Agentic Agile + Portfolio Management"
Cohesion: 0.18
Nodes (10): Agile improvements shipped alongside, Autonomous intelligence (`agents/portfolio_intelligence.py`), Capacity & roadmap, Context: Agentic Agile + Portfolio Management, Extension ideas (not yet built), Prioritisation model — WSJF (SAFe), Problem, The two layers (+2 more)

### Community 703 - "Deploy to Google Cloud Run"
Cohesion: 0.18
Nodes (10): 1) Admin protection (required), 2) User API keys (required), 3) LLM provider (recommended), Build + deploy (Dockerfile), Deploy to Google Cloud Run, Notes / limitations on Cloud Run, Prereqs, Required configuration (+2 more)

### Community 704 - "Key Components"
Cohesion: 0.18
Nodes (10): 1. Input Embedding, 2. Multi-Head Self-Attention, 3. Residual Connections, 4. Feed-Forward Network (FFN), 5. Layer Normalization, Decoder-Only vs Encoder-Decoder, High-Level Structure, Key Components (+2 more)

### Community 705 - "Sampling Strategies Internals"
Cohesion: 0.18
Nodes (11): Beam Search, Greedy Decoding, Logit Processors (Structured Output), Min-p Sampling, Repetition Penalty, Sampling Strategies Internals, Temperature Sampling, The Output Distribution (+3 more)

### Community 706 - "LLM Router — architecture"
Cohesion: 0.18
Nodes (11): Bulkheads, Circuit breaker, Compatibility, Configuration, Context management, LLM Router — architecture, Modules, Request lifecycle (+3 more)

### Community 707 - "Killer TODO Roadmap — local-llm-server"
Cohesion: 0.18
Nodes (10): G1 — Per-Model Cost and Latency Attribution [P1] [NVD], G2 — Request Replay for Debugging [P2] [CBF], H1 — Vision Input Support for Multimodal Models [P2] [NVD], H2 — Audio Input / Whisper Transcription [P3] [NVD], Implementation Notes, Killer TODO Roadmap — local-llm-server, Priority Summary, SECTION G — Observability (NVD / CHM) (+2 more)

### Community 708 - "NVIDIA NIM — Free Tier Setup"
Cohesion: 0.18
Nodes (10): 1. Get your free API key, 2. Set the environment variable, 3. Restart the server, 4. Verify, How the kill switch protects you, NVIDIA NIM — Free Tier Setup, Related, Setup (5 minutes) (+2 more)

### Community 709 - "What to clean up"
Cohesion: 0.18
Nodes (10): 1. Render (production backend + worker), 2. Cloudflare Worker (frontend), 3. Local development machines, 4. GitHub secrets, 5. MongoDB collections, Post-Merge Environment Cleanup Guide, Post-merge verification checklist, Rollback (+2 more)

### Community 710 - "Worker Service — Operations Runbook"
Cohesion: 0.18
Nodes (10): Architecture, Deployment on Render, Environment variables, First-time setup, Graceful shutdown, Local development, Overview, Troubleshooting (+2 more)

### Community 711 - "test_bedrock_live.py"
Cohesion: 0.25
Nodes (10): _NEEDS_CREDS, asyncio, ProviderRouter discovers Bedrock from env and completes a real chat call., Health check returns True when real credentials are loaded from env., Call Bedrock Converse API directly with boto3 — no proxy layer., Verify the configured model ID accepts a converse request without auth errors., test_bedrock_direct_boto3_ping(), test_bedrock_health_check_with_real_creds() (+2 more)

### Community 712 - "FakeCollection"
Cohesion: 0.17
Nodes (3): fake_db(), FakeCollection, FakeCursor

### Community 713 - "run_proxy.sh"
Cohesion: 0.18
Nodes (10): AIDER_BASE_URL, GOOSE_BASE_URL, HERMES_BASE_URL, LOG_LEVEL, OLLAMA_BASE, OPENCODE_BASE_URL, PROXY_PORT, RATE_LIMIT_RPM (+2 more)

### Community 714 - "configuration-reference.md"
Cohesion: 0.09
Nodes (9): Architecture and operations, Documentation map, Repo hygiene, Screenshots and README sync, Start here, A sample of what the agents shipped (all merged, all real), The numbers (verifiable via the GitHub API), This repository is maintained by its own agents (+1 more)

### Community 715 - "setup_ngrok.py"
Cohesion: 0.31
Nodes (10): _api(), authenticate_ngrok(), _find_ngrok(), get_or_create_static_domain(), main(), Return path to the ngrok binary (pyngrok location or PATH)., Update or append KEY=value in .env., rewrite_tunnel_scripts() (+2 more)

### Community 716 - "._run_job"
Cohesion: 0.24
Nodes (4): _now(), Any, Run a job using the provided runner and update the job's lifecycle, progress,…, Serialize the AgentJob to a JSON-serializable dictionary for external clients.…

### Community 717 - "test_empirical_verify.py"
Cohesion: 0.49
Nodes (10): _make_runner(), MonkeyPatch, Path, Tests for AgentRunner._empirical_verify (opt-in executable validation gate)., test_empirical_verify_disabled_by_default(), test_empirical_verify_flags_compile_failure(), test_empirical_verify_passes_clean_module_without_tests(), test_empirical_verify_runs_matching_tests_and_passes() (+2 more)

### Community 718 - ".get_overview"
Cohesion: 0.24
Nodes (6): Any, Provides an architecture summary, module map, and git health., Identifies frequently changed files using git history., Guesses entry points based on file names and common patterns., Basic git health metrics., Hotspot scores and potential impact analysis.

### Community 719 - "fetch_url.py"
Cohesion: 0.43
Nodes (7): extract_real_url(), fetch(), main(), meaningful(), Drop site navigation chrome and repeated nav blocks from stripped text. A fetch…, strip_boilerplate(), strip_html()

### Community 720 - "_TFIDFIndex"
Cohesion: 0.22
Nodes (8): Lightweight TF-IDF index over a fixed document collection. Sparse dict vectors…, _TFIDFIndex, test_tfidf_empty_corpus(), test_tfidf_empty_query(), test_tfidf_finds_relevant(), test_tfidf_scores_between_0_and_1(), test_tfidf_scores_ordered_descending(), test_tfidf_unknown_term_only()

### Community 721 - "Instructions"
Cohesion: 0.20
Nodes (9): Acceptance Checks, Instructions, Skill: insights, Step 1 — File change heatmap (which files change most), Step 2 — Failure pattern analysis, Step 3 — Retry analysis, Step 4 — Learnings frequency analysis, Step 5 — Produce a summary report (+1 more)

### Community 722 - "Protocol: Premium Utilitarian Minimalism UI Architect"
Cohesion: 0.20
Nodes (9): 1. Protocol Overview, 2. Absolute Negative Constraints (Banned Elements), 3. Typographic Architecture, 4. Color Palette (Warm Monochrome + Spot Pastels), 5. Component Specifications, 6. Iconography & Imagery Directives, 7. Subtle Motion & Micro-Animations, 8. Execution Protocol (+1 more)

### Community 723 - "The 5-Step Wrap-Up Ritual"
Cohesion: 0.20
Nodes (9): Acceptance Checks, Skill: wrap-up, Step 1 — Changes Audit, Step 2 — Quality Check, Step 3 — Learning Capture, Step 4 — Next Session Planning, Step 5 — One-Paragraph Summary, The 5-Step Wrap-Up Ritual (+1 more)

### Community 724 - "security_fix_agent.py"
Cohesion: 0.57
Nodes (6): codeql_count(), dependabot_count(), main(), Any, _repo_parts(), _request()

### Community 725 - "Agent: Reviewer (Verifier)"
Cohesion: 0.20
Nodes (10): Activation, Agent: Reviewer (Verifier), Blocking Conditions (must return `fail`), Handoff, Key Invariant, Non-Blocking (may return `pass` with suggestions), Output Format, Preferred Model (+2 more)

### Community 726 - "Skill: Agentic Agile"
Cohesion: 0.20
Nodes (9): Autonomous ceremonies (`agents/agile_ceremonies.py`), Key Classes, Purpose, Related, Retrospective & health, Scheduled workflow, Skill: Agentic Agile, Testing (+1 more)

### Community 727 - "Skill: browserbase-ui-test — Adversarial UI Testing"
Cohesion: 0.20
Nodes (9): Applying to local-llm-server platform, Core philosophy, Execution pattern, Reporting, Round 1 — Core flow mapping, Round 2 — Adversarial scenarios, Round 3 — Accessibility + mobile, Skill: browserbase-ui-test — Adversarial UI Testing (+1 more)

### Community 728 - "Skill: financial-analyst (Agentic CFO)"
Cohesion: 0.20
Nodes (9): Branch, Components, Decision Rules, Purpose, Quick Start, Skill: financial-analyst (Agentic CFO), SKILL.md refresh Tue Jun  2 11:35:52 CEST 2026, Testing (+1 more)

### Community 729 - "Graphiti Temporal Context Skill"
Cohesion: 0.20
Nodes (9): 1. Agent Memory as Temporal Graph, 2. Multi-Agent Coordination, 3. Knowledge Queries, Database Schema, Files to Create, Graphiti Temporal Context Skill, Integration Opportunities, References (+1 more)

### Community 730 - "Skill: seo-audit-report"
Cohesion: 0.20
Nodes (9): How This Skill Works (Agent Instructions), Output Files, Parameters, Purpose, Quick Start, Revenue-at-Risk Disclaimer (load-bearing — always include in reports), Skill: seo-audit-report, Troubleshooting (+1 more)

### Community 731 - "ADR-008: LLMRouter — the single multi-provider routing gateway"
Cohesion: 0.20
Nodes (10): ADR-008: LLMRouter — the single multi-provider routing gateway, Comparison with OmniRoute, Consequences, Context, Differences — why a port was rejected, Incompatible components (explicitly rejected), References, Reusable components (ideas adopted) (+2 more)

### Community 732 - "Core Pillars"
Cohesion: 0.20
Nodes (9): 1. Unified Intent Orchestration, 2. Deep Sticky Memory, 3. Execution Cognition Flow, 4. Progress Humanization, Core Pillars, Direct Chat Evolution: Seamless Assistant Architecture, Failure Recovery, Overview (+1 more)

### Community 733 - "467 Golden Path — Locked Implementation Order"
Cohesion: 0.20
Nodes (10): 467 Golden Path — Locked Implementation Order, Agent Code (agent/ directory), Backend Code (backend/, handlers/), Golden Path Exceptions, Module-Specific Golden Paths, Skill Code (.agents/skills/), Verification, What Breaks the Golden Path (+2 more)

### Community 734 - "LLM Router — configuration guide"
Cohesion: 0.20
Nodes (10): Budgets, cache.yaml, Environment variables, health.yaml, keys.yaml, LLM Router — configuration guide, models.yaml, Per-agent policies (+2 more)

### Community 735 - "LLM Router — provider guide"
Cohesion: 0.20
Nodes (9): Adding any OpenAI-compatible provider, Auth styles, Cheap tiers, Cloud providers, Free tiers, LLM Router — provider guide, Multiple keys, Premium (+1 more)

### Community 736 - "FeatureMaturity"
Cohesion: 0.08
Nodes (31): PreflightReport, AgentJob, make_isolated_workspace(), Path, Create an isolated workspace directory under *root*. This is the legacy path…, _workspace_component(), WorkspaceEscapeError, WorkspaceIDError (+23 more)

### Community 737 - "RepowiseIntelligence"
Cohesion: 0.33
Nodes (5): Path, Returns a structural overview of the repository., Workhorse tool for packing content and metrics of target files., Get dependencies from our built intelligence., RepowiseIntelligence

### Community 738 - "test_provider_state_durability.py"
Cohesion: 0.14
Nodes (10): fake_mongo(), _FakeDb, isolated_state(), _live_mongo_url(), Operator provider state must survive a redeploy. The per-provider kill switch…, Temp SQLite mirror + clean caches, so no test sees another's state., Return a reachable MONGO_URL, or None so the test skips., Both halves matter, and the second one is easy to drop. Redirecting… (+2 more)

### Community 739 - "build_tech_db.py"
Cohesion: 0.40
Nodes (9): _as_list(), _clean(), convert(), _default_source(), _has_pattern(), main(), Any, Strip Wappalyzer's `\\;tag:...` metadata, leaving a plain regex. (+1 more)

### Community 740 - "main"
Cohesion: 0.29
Nodes (9): _detect_crlf(), _enumerate_matching_lines(), _eprint(), main(), Path, CRLF present if any line ends in CRLF., Yield (line_bytes, line_index) for every line in `data` containing `needle`., Pick the .env to migrate. See module docstring for resolution order. (+1 more)

### Community 741 - "run_bot"
Cohesion: 0.27
Nodes (9): _configure(), _default(), main(), Set an env var only when the operator hasn't already provided one., Call a Telegram Bot API method and return the parsed JSON (best-effort)., run_bot(), _tg_call(), TELEGRAM_POLLER_DISABLED=true makes run_bot() idle WITHOUT long-polling… (+1 more)

### Community 742 - "Dream"
Cohesion: 0.22
Nodes (6): Dream, Return the most recent dreams, newest first., A consolidated dream built from multiple session memories., Return a brief summary of the dream., Tests for Dream dataclass., TestDream

### Community 743 - "_resolve_push_token"
Cohesion: 0.31
Nodes (9): GitHub token used to push branches / open PRs during EXECUTION (#506).…, _resolve_push_token(), _clean_env(), tests/test_orchestrator_push_token.py — #506 push/PR token resolution.…, test_falls_through_gh_pat_and_github_token(), test_internal_run_uses_server_token(), test_per_user_token_always_wins(), test_user_run_with_optin_uses_server_token() (+1 more)

### Community 744 - "test_doctor_coding_brain.py"
Cohesion: 0.38
Nodes (6): client(), _coding_brain_check(), tests/test_doctor_coding_brain.py Surfaces the North Mini Code coding-brain…, With NORTH_MINI_CODE_DEFAULT off, the check warns and says so., test_coding_brain_check_reflects_flag_off(), test_doctor_includes_coding_brain_check()

### Community 745 - "TestZeroAttemptDiagnostics"
Cohesion: 0.29
Nodes (4): A zero-attempt exhaustion must say WHICH of the three causes it is. Nothing…, An operator whose switches reset on deploy needs to know that here., A broken registry must not turn a failed call into a crash., TestZeroAttemptDiagnostics

### Community 746 - "TestSessionMemory"
Cohesion: 0.20
Nodes (3): Tests for services/managed_agents.py — Managed Agents Dreams. Uses importlib to…, Tests for SessionMemory dataclass., TestSessionMemory

### Community 747 - "test_quick_note_engine.py"
Cohesion: 0.22
Nodes (7): _before(), Guard that the quick-note engine agents use NVIDIA NIM as the primary engine…, implement_agent.py uses NVIDIA NIM exclusively — the Anthropic/Opus fallback…, Regression: _run_baseline_pytest() ran the FULL suite (no path filter,…, test_baseline_pytest_timeout_is_generous_and_failure_is_caught(), test_implement_agent_nvidia_primary(), test_review_agent_nvidia_primary()

### Community 748 - "SamConversation"
Cohesion: 0.22
Nodes (7): Process a voice command and return SAM's spoken response. Args: text: The…, A single voice conversation session with SAM., SamConversation, add_turn must append to history and increment command_count., History must be capped at 20 entries (10 turns)., test_conversation_add_turn(), test_conversation_history_capped()

### Community 751 - "_extract_workflow_relevance"
Cohesion: 0.33
Nodes (4): _extract_workflow_relevance(), Return workflow types mentioned in the skill content., Tests for _extract_workflow_relevance()., TestExtractWorkflowRelevance

### Community 752 - "Agent Readiness Report"
Cohesion: 0.20
Nodes (9): Agent Readiness Report, Build System — 100/100, Dev Environment — 100/100, Documentation — 100/100, Observability — 100/100, Security — 100/100, Style And Validation — 100/100, Task Discovery — 100/100 (+1 more)

### Community 753 - "Skill: changelog-enforcer"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Changelog Location, Entry Format, Examples, Hook Behaviour, Instructions, Skill: changelog-enforcer, When to Use

### Community 754 - "Skill: learn-rule"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Instructions, Learnings File Format, Skill: learn-rule, Step 1 — Identify the rule, Step 2 — Append to learnings file, Step 3 — Check if CLAUDE.md should be updated, When to Use

### Community 755 - "Instructions"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Instructions, Skill: session-handoff, Step 1 — Capture current state, Step 2 — Write the handoff document, Step 3 — Update machine-readable state, Step 4 — Confirm the handoff is self-contained, When to Use

### Community 756 - "test_provider_router.py"
Cohesion: 0.08
Nodes (27): _normalize_nvidia_base_url(), _openai_url(), Normalize NVIDIA base URLs to avoid double /v1 when openai_compat_url appends…, _best_cloud_primary_base(), Return the highest-priority available cloud LLM base URL. Tries free cloud…, _clear_probe_locks(), Release any stray probe locks between tests so a crashed test never gates the…, The fix must not leak the other way — paid providers stay paid. (+19 more)

### Community 757 - "prompts/README.md"
Cohesion: 0.22
Nodes (4): Command: /resume, References, Usage, What It Does

### Community 758 - "Skill: Agentic Portfolio Management"
Cohesion: 0.22
Nodes (8): Key Classes, Purpose, Related, Skill actions (via SkillBindings), Skill: Agentic Portfolio Management, Testing, Usage, WSJF

### Community 759 - "Skill: changelog-enforcer"
Cohesion: 0.22
Nodes (8): Acceptance Checks, Changelog Location, Entry Format, Examples, Hook Behaviour, Instructions, Skill: changelog-enforcer, When to Use

### Community 760 - "Skill: cowork-session (Claude Cowork)"
Cohesion: 0.22
Nodes (8): Branch, Components, Purpose, Quick Start, Session Roles, Skill: cowork-session (Claude Cowork), Testing, When to Use

### Community 761 - "Skill: video-context — read a video without watching it"
Cohesion: 0.22
Nodes (8): How It Works, Limits — know these before relying on it, Skill: video-context — read a video without watching it, Testing, Usage, What To Do With The Transcript, When To Use This, Why This Exists

### Community 762 - "Decision"
Cohesion: 0.22
Nodes (9): 1. `LLMRouter` is the only gateway, 2. Providers are data, not code, 3. Secrets stay in the environment, 4. Three independent failure scopes, 5. Bulkhead isolation, 6. Context is managed losslessly, 7. Configuration is six committed YAML files, 8. Backwards compatibility by shim, not by rewrite (+1 more)

### Community 763 - "ADR 003: Multi-Agent Orchestration with Plan-Execute-Verify Loop"
Cohesion: 0.22
Nodes (8): ADR 003: Multi-Agent Orchestration with Plan-Execute-Verify Loop, Alternatives Considered, Consequences, Context, Decision, Negative, Neutral, Positive

### Community 764 - "Main proxy (`proxy.py`)"
Cohesion: 0.22
Nodes (9): Agent and workflow surfaces, API Surfaces and Route Map, Built-in admin and web UI, Control-plane style routers mounted in the proxy, Main proxy (`proxy.py`), Ollama-compatible, OpenAI-compatible, Separate hosted dashboard backend (`backend/server.py`) (+1 more)

### Community 765 - "Autonomous SDLC Loop (Agency Core, repo-agnostic)"
Cohesion: 0.22
Nodes (9): Autonomous SDLC Loop (Agency Core, repo-agnostic), Companies without a connected repo (URL-only onboarding), Design principle: repo-agnostic, not GitHub-Actions-bound, Detect & respect each repo's delivery policy, Integrations & intake sources (honest tiers), Reuse map (what already exists), Safety invariants (carry over from `agent/CLAUDE.md`), The gap this closes (+1 more)

### Community 766 - "The 8-Step Golden Path"
Cohesion: 0.22
Nodes (9): Step 1: Scout — Understand the territory, Step 2: Plan — Define the change, Step 3: Write tests first, Step 4: Implement, Step 5: Validate, Step 6: Review, Step 7: Document, Step 8: Commit and propose (+1 more)

### Community 767 - "PR #634 Implementation Tracker"
Cohesion: 0.22
Nodes (8): Phase 1 — Stop the bleeding + paid kill switch ✅, Phase 2 — Per-surface assignment in the UI 🔄, Phase 3 — Persistence hardening (#537, #524) ⏳, Phase 4 — Onboarding fixes (#593, #619, PR #623) ⏳, Phase 5 — Reliability (#522) ⏳, Phase 6 — Green tests + housekeeping ⏳, PR #634 Implementation Tracker, Verification checklist (final)

### Community 768 - "KV Cache Internals"
Cohesion: 0.22
Nodes (9): KV Cache Internals, KV Cache with Grouped Query Attention, Memory Layout, Paged Attention (vLLM), Prefill vs Decode Phase, Quantization of KV Cache, Speculative Decoding, The Problem: Redundant Computation (+1 more)

### Community 769 - "Platform Controls"
Cohesion: 0.22
Nodes (8): Across processes, Adding a control, API, Groups, How a value is resolved, Live vs restart-required, Platform Controls, What is deliberately **not** here

### Community 770 - "Release Procedure"
Cohesion: 0.22
Nodes (8): Changelog Update, Commit and Tag, Post-Release Checklist, Pre-Flight, Release Procedure, Rollback, Verify CI, Version Bump

### Community 771 - "V2.0 Modernization — Runbook"
Cohesion: 0.22
Nodes (8): Adding a new provider adapter, CI, Importing new code, Module map (old → new), Removing the shims (future cleanup), Rollback, Test migration, V2.0 Modernization — Runbook

### Community 772 - "Setup"
Cohesion: 0.22
Nodes (8): 1. Get LiveKit credentials, 2. Configure the backend (Render env vars), 3. The SAM voice worker, 4. Talk to SAM, Architecture, SAM Realtime Voice over LiveKit, Setup, Troubleshooting

### Community 773 - "Troubleshooting"
Cohesion: 0.04
Nodes (57): 401 Unauthorized, 403 Forbidden from remote machine, 429 Too Many Requests, Admin Dashboard Issues, Agent API Issues, Agent makes a change but doesn't verify correctly, Agent returns empty or incomplete plan, Agent workspace errors ("file not found") (+49 more)

### Community 774 - "frontend/package.json"
Cohesion: 0.22
Nodes (8): jest, moduleNameMapper, ^react-router$, ^react-router-dom$, name, private, proxy, version

### Community 775 - "AgentStatusPanel.tsx"
Cohesion: 0.25
Nodes (7): AgentStatus, AgentStatusPanelProps, AgentCard(), formatRelative(), ROLE_ICONS, STATUS_DOTS, STATUS_STYLES

### Community 776 - "AgentStatusPanel.jsx"
Cohesion: 0.25
Nodes (6): AgentCard(), formatRelative(), ROLE_ICONS, STATUS_DOTS, STATUS_STYLES, PHASE_LABELS

### Community 777 - "ToolCallViewer.tsx"
Cohesion: 0.25
Nodes (7): ToolCall, ToolCallViewerProps, getToolIcon(), STATUS_BADGES, STATUS_STYLES, TOOL_ICONS, ToolCallRow()

### Community 778 - "test_bedrock_provider.py"
Cohesion: 0.05
Nodes (20): _is_bedrock_model_id(), Return True if model_id is an AWS Bedrock model or inference profile ID., _bedrock_api_response(), _bedrock_provider(), _mock_boto3(), Any, ProviderConfig, Tests for AWS Bedrock provider support in ProviderRouter. (+12 more)

### Community 779 - "enrich_quick_note_issues.py"
Cohesion: 0.42
Nodes (8): _dispatch_generation(), _fetch_open_issues(), _has_context(), _headers(), _is_quick_note(), main(), Ask the bulk context workflow to generate documents for these issues., True when a context branch already exists for this issue. Checked against…

### Community 780 - "_status_snapshot"
Cohesion: 0.31
Nodes (9): cmd_wait(), Block until download completes + colibri answers /v1/models., _status_snapshot(), await_ready(), colibri_model_id(), colibri_url(), _list_models_payload(), Normalise an OAI ``/v1/models`` response into a list of model ids. (+1 more)

### Community 781 - "test_backend_requirements_cover_runtime_imports.py"
Cohesion: 0.25
Nodes (8): _declared_packages(), parametrize, Path, Guard against the recurring "works in CI, missing in prod" dependency drift.…, Return the normalised distribution names declared in *requirements*., If the Dockerfile ever installs the root file, this guard can relax. Until then…, test_backend_requirements_declares_runtime_package(), test_dockerfile_still_installs_backend_requirements_only()

### Community 782 - "test_changelog_parity_guard.py"
Cohesion: 0.22
Nodes (3): tests/test_changelog_parity_guard.py — corruption guard for the changelog gate.…, A 7-equals line under a title (Markdown setext H1) must not false-positive., test_setext_heading_underline_is_not_flagged()

### Community 783 - "._prune"
Cohesion: 0.22
Nodes (6): _ProviderUsage, Sliding-window usage counters for one provider., Drop request/token events that have fallen out of the window., Count a request that is about to be sent to *provider_id*. Called immediately…, Record the outcome of a request started with ``record_start``. Must be called…, Count a request that was routed away from *provider_id* (diagnostics).

### Community 785 - "TestDisabledReasonRendering"
Cohesion: 0.14
Nodes (5): ``describe_disabled_reason`` is rendered next to the on/off switch. The stored…, Anthropic sends 400 for an empty balance, not 402., A reason the operator cannot read still beats no reason at all., Guards the seam: the writer and this renderer must not drift apart. Scans the…, TestDisabledReasonRendering

### Community 786 - "test_scanner_deps_parity.py"
Cohesion: 0.31
Nodes (8): _declared_packages(), Guard against the CI-vs-production dependency drift that made gucci.com (and…, Top-level module names imported anywhere in services/scanner.py., Every third-party package the scanner imports must be in the file the…, Belt-and-suspenders: the two deps whose absence caused the gucci.com production…, _scanner_imports(), test_critical_scanner_deps_explicitly_present(), test_scanner_third_party_deps_declared_in_backend_requirements()

### Community 787 - "stt.py"
Cohesion: 0.36
Nodes (8): voice/stt.py — Speech-to-Text for the CEO voice pipeline. Transcribes audio…, Transcribe audio bytes to text. Returns empty string on failure., Fallback: Google Web Speech API via SpeechRecognition library., _select_backend(), transcribe(), _transcribe_google(), _transcribe_local(), _transcribe_openai()

### Community 788 - "test_log_monitor_storm_guard.py"
Cohesion: 0.48
Nodes (6): _fresh_monitor(), Tests for the LogMonitor self-heal storm guard. A system that is already…, test_cap_zero_disables_cap(), test_hourly_cap_suppresses_storm(), test_operational_errors_are_skipped(), test_real_code_error_creates_a_task()

### Community 789 - "navigation_metrics.py"
Cohesion: 0.32
Nodes (4): get_navigation_metrics(), NavigationMetrics, navigation_metrics.py — Navigation/usage metrics collection for agent sessions., record_content_visible()

### Community 790 - "_score_turns"
Cohesion: 0.36
Nodes (8): Score each turn by exponential recency decay combined with query relevance.…, _score_turns(), test_score_turns_empty(), test_score_turns_importance_multiplier(), test_score_turns_recency_newer_scores_higher(), test_score_turns_relevance_boosts_score(), test_score_turns_sorted_descending(), _turn()

### Community 791 - "TrajectoryStep"
Cohesion: 0.25
Nodes (5): Any, Agent trajectory recorder – captures every step an agent takes so runs can be…, A single action/observation pair in an agent trajectory., Append a step and return it., TrajectoryStep

### Community 792 - "._get_last_commit"
Cohesion: 0.33
Nodes (3): Get the latest commit hash., Get the last commit hash we processed., Check if we need to update intelligence based on new commits.

### Community 794 - "quality_checker.py"
Cohesion: 0.32
Nodes (6): AITellType, Enum, str, Quality checker inspired by stop-slop (https://github.com/hardikpandya/stop-…, Categories of AI tells, Tests for quality checker (stop-slop inspired)

### Community 795 - "Skill: docs-sync"
Cohesion: 0.25
Nodes (7): Acceptance Checks, ADR Guidelines, AGENTS.md Update Rules, Docs to Check After Each Change Type, Instructions, Skill: docs-sync, When to Use

### Community 796 - "._scan_github_repo"
Cohesion: 0.12
Nodes (11): _content_contains_domain(), _hostname_contains(), _hostname_matches(), datetime, Scan a Git repository and detect its technology stack. Args: repo_url: URL of…, Detect the Git provider from a repository URL. Args: repo_url: Repository URL…, Scan a GitHub repository. Args: repo_url: GitHub repository URL scan_id: Scan…, Check if a URL or hostname exactly matches or is a subdomain of any domain.… (+3 more)

### Community 797 - "Agent: Implementer (Executor)"
Cohesion: 0.25
Nodes (8): Activation, Agent: Implementer (Executor), Constraints, Handoff, Preferred Model, Responsibilities, Role, Shared State

### Community 798 - "Agent: Judge (Release / QA Gate)"
Cohesion: 0.25
Nodes (7): Activation, Agent: Judge (Release / QA Gate), Enforcement, Output, Responsibilities, Role, Verdict Meanings

### Community 799 - "Agent: Planner (Architect)"
Cohesion: 0.25
Nodes (8): Activation, Agent: Planner (Architect), Failure Behaviour, Handoff, Output Format, Preferred Model, Responsibilities, Role

### Community 800 - "Skill: browserbase-browser — Real Browser Automation"
Cohesion: 0.25
Nodes (7): Applying to local-llm-server platform, Core commands, Mode selection, Setup, Skill: browserbase-browser — Real Browser Automation, Troubleshooting, Workflow pattern

### Community 801 - "Skill: docs-sync"
Cohesion: 0.25
Nodes (7): Acceptance Checks, ADR Guidelines, CLAUDE.md Update Rules, Docs to Check After Each Change Type, Instructions, Skill: docs-sync, When to Use

### Community 802 - "Skill: memory-consolidation (Dream Memory)"
Cohesion: 0.25
Nodes (7): Branch, Consolidation Lifecycle, Memory Kinds, Purpose, Quick Start, Skill: memory-consolidation (Dream Memory), Testing

### Community 803 - "GitHub Branch Protection Settings"
Cohesion: 0.25
Nodes (7): Branch name pattern: `main` (or `master`), CODEOWNERS Setup, Enabling via GitHub CLI, GitHub Branch Protection Settings, Purpose, Required Settings, Why This Can't Be Fully Repo-Enforced

### Community 804 - "ADR 001: Self-Hosted OpenAI-Compatible Proxy"
Cohesion: 0.25
Nodes (7): ADR 001: Self-Hosted OpenAI-Compatible Proxy, Consequences, Context, Decision, Negative, Neutral, Positive

### Community 805 - "ADR 002: Dynamic Model Routing with Task Classification"
Cohesion: 0.25
Nodes (7): ADR 002: Dynamic Model Routing with Task Classification, Consequences, Context, Decision, Negative, Neutral, Positive

### Community 806 - "AGENTS.md — AI Agent Configuration for local-llm-server"
Cohesion: 0.25
Nodes (7): Agent Roles, AGENTS.md — AI Agent Configuration for local-llm-server, Operating Instructions, Quick Start for Agents, Risky Paths — Require Extra Care, State Files, Workspace Purpose

### Community 807 - "Advisor Strategy — Local Proxy Handling"
Cohesion: 0.25
Nodes (7): Advisor Strategy — Local Proxy Handling, How This Proxy Handles Advisor Requests, Incoming message history (advisor blocks), Local Equivalent: The Planner Role, Outgoing requests (tools array), Using the Real Advisor Strategy via This Proxy, What the Anthropic Advisor Strategy Is

### Community 808 - "ceo-micromanagement.md"
Cohesion: 0.25
Nodes (4): P0 behavior change, Readiness contract, Runtime model, Runtime types

### Community 809 - "Feature Maturity / Support Matrix"
Cohesion: 0.13
Nodes (14): Beta, Config Overrides, Disabled (demoted per issue #467 Section I), Enforcement, Experimental, Feature Maturity / Support Matrix, Maturity Tiers, Stable Core (+6 more)

### Community 810 - "Web UI + Admin (Claude Code–style)"
Cohesion: 0.25
Nodes (7): Acceptance checks, Approach, Files to change, Files to read first, Goal, Risks, Web UI + Admin (Claude Code–style)

### Community 811 - "467 Skill Inventory — load / wire / test status"
Cohesion: 0.25
Nodes (7): 467 Skill Inventory — load / wire / test status, Agent Specialties (not skills per se, but referenced in spec §B), Core Agency Skills (load/wire/test), Gaps Summary, Named Skills Referenced in Spec §C, Skill Registry, Test Coverage Summary

### Community 812 - "Free NVIDIA brain + UI-controlled provider policy + no silent spend"
Cohesion: 0.25
Nodes (8): Decisions (locked with the owner), Design: one UI-controlled Provider Policy (single source of truth), Free NVIDIA brain + UI-controlled provider policy + no silent spend, Open-PR / issue disposition (read + acted on), Root cause of the $20 burn (verified in-repo), SELF-CONTAINED AGENT PROMPT (paste to run cold), Verification / acceptance, Why this PR exists (context)

### Community 813 - "Issue #362: Nvidia repo setup"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #362: Nvidia repo setup, Implementation Prompt, Issue #362: Nvidia repo setup, Relevant Files to Read First, Risk Flags, TODO List

### Community 814 - "Issue #364: quick-note:https://www.marktechpost.com/2026/06/01/meet-memory-os-a-6-layer-open-source-memory-stack-built-on-top-of-hermes-agent/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #364: quick-note:https://www.marktechpost.com/2026/06/01/meet-memory-os-a-6-layer-open-source-memory-stack-built-on-top-of-hermes-agent/, Implementation Prompt, Issue #364: quick-note:https://www.marktechpost.com/2026/06/01/meet-memory-os-a-6-layer-open-source-memory-stack-built-on-top-of-hermes-agent/, Relevant Files to Read First, Risk Flags, TODO List

### Community 815 - "Issue #378: quick-note:https://www.marktechpost.com/2026/06/02/tinyfish-launches-bigset-an-open-source-multi-agent-system-that-builds-structured-live-datasets-from-plain-english-descriptions/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #378: quick-note:https://www.marktechpost.com/2026/06/02/tinyfish-launches-bigset-an-open-source-multi-agent-system-that-builds-structured-live-datasets-from-plain-english-descriptions/, Implementation Prompt, Issue #378: quick-note:https://www.marktechpost.com/2026/06/02/tinyfish-launches-bigset-an-open-source-multi-agent-system-that-builds-structured-live-datasets-from-plain-english-descriptions/, Relevant Files to Read First, Risk Flags, TODO List

### Community 816 - "Issue #379: quick-note:https://searchengineland.com/schema-markup-optimize-agentic-web-479080"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #379: quick-note:https://searchengineland.com/schema-markup-optimize-agentic-web-479080, Implementation Prompt, Issue #379: quick-note:https://searchengineland.com/schema-markup-optimize-agentic-web-479080, Relevant Files to Read First, Risk Flags, TODO List

### Community 817 - "Issue #380: quick-note:https://cursor.com/blog/cloud-agent-lessons"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #380: quick-note:https://cursor.com/blog/cloud-agent-lessons, Implementation Prompt, Issue #380: quick-note:https://cursor.com/blog/cloud-agent-lessons, Relevant Files to Read First, Risk Flags, TODO List

### Community 818 - "Issue #381: quick-note:https://www.xda-developers.com/claude-code-with-opus-48-is-expensive-but-i-made-it-efficient-with-my-local-ai-workflow/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #381: quick-note:https://www.xda-developers.com/claude-code-with-opus-48-is-expensive-but-i-made-it-efficient-with-my-local-ai-workflow/, Implementation Prompt, Issue #381: quick-note:https://www.xda-developers.com/claude-code-with-opus-48-is-expensive-but-i-made-it-efficient-with-my-local-ai-workflow/, Relevant Files to Read First, Risk Flags, TODO List

### Community 819 - "Issue #382: quick-note:https://claude.com/blog/how-coderabbit-used-claude-to-build-an-agent-orchestration-system"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #382: quick-note:https://claude.com/blog/how-coderabbit-used-claude-to-build-an-agent-orchestration-system, Implementation Prompt, Issue #382: quick-note:https://claude.com/blog/how-coderabbit-used-claude-to-build-an-agent-orchestration-system, Relevant Files to Read First, Risk Flags, TODO List

### Community 820 - "Issue #383: quick-note:https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #383: quick-note:https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/, Implementation Prompt, Issue #383: quick-note:https://www.marktechpost.com/2026/05/29/hexo-labs-open-sources-sia-a-self-improving-agent-that-updates-both-the-harness-and-the-model-weights/, Relevant Files to Read First, Risk Flags, TODO List

### Community 821 - "Issue #416: feat: Self-hosted Codebuff (freebuff) on free NVIDIA models + Telegram bot phone control"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #416: feat: Self-hosted Codebuff (freebuff) on free NVIDIA models + Telegram bot phone control, Implementation Prompt, Issue #416: feat: Self-hosted Codebuff (freebuff) on free NVIDIA models + Telegram bot phone control, Relevant Files to Read First, Risk Flags, TODO List

### Community 822 - "Issue #485: [Trend Digest] Week of 2026-06-08"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #485: [Trend Digest] Week of 2026-06-08, Implementation Prompt, Issue #485: [Trend Digest] Week of 2026-06-08, Relevant Files to Read First, Risk Flags, TODO List

### Community 823 - "Issue #488: quick-note:https://github.com/cookiy-ai/user-research-skill"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #488: quick-note:https://github.com/cookiy-ai/user-research-skill, Implementation Prompt, Issue #488: quick-note:https://github.com/cookiy-ai/user-research-skill, Relevant Files to Read First, Risk Flags, TODO List

### Community 824 - "Issue #491: Implement whatever is necessary from https://github.com/BehiSecc/awesome-claude-skills"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #491: Implement whatever is necessary from https://github.com/BehiSecc/awesome-claude-skills, Implementation Prompt, Issue #491: Implement whatever is necessary from https://github.com/BehiSecc/awesome-claude-skills, Relevant Files to Read First, Risk Flags, TODO List

### Community 825 - "Issue #493: Use the https://github.com/mvanhorn/last30days-skill skill to get the trend updated"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #493: Use the https://github.com/mvanhorn/last30days-skill skill to get the trend updated, Implementation Prompt, Issue #493: Use the https://github.com/mvanhorn/last30days-skill skill to get the trend updated, Relevant Files to Read First, Risk Flags, TODO List

### Community 826 - "Issue #495: Read https://www.anthropic.com/news/claude-fable-5-mythos-5 and understand if mythos or fable can be added to the repo"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #495: Read https://www.anthropic.com/news/claude-fable-5-mythos-5 and understand if mythos or fable can be added to the repo, Implementation Prompt, Issue #495: Read https://www.anthropic.com/news/claude-fable-5-mythos-5 and understand if mythos or fable can be added to the repo, Relevant Files to Read First, Risk Flags, TODO List

### Community 827 - "Issue #504: EPIC: Autonomy hardening — live-verified defects 2026-06-10"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #504: EPIC: Autonomy hardening — live-verified defects 2026-06-10, Implementation Prompt, Issue #504: EPIC: Autonomy hardening — live-verified defects 2026-06-10, Relevant Files to Read First, Risk Flags, TODO List

### Community 828 - "Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass, Implementation Prompt, Issue #581: Sprint tracker: pending work after brand rename + mobile-first pass, Relevant Files to Read First, Risk Flags, TODO List

### Community 829 - "Issue #656: Bugs"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #656: Bugs, Implementation Prompt, Issue #656: Bugs, Relevant Files to Read First, Risk Flags, TODO List

### Community 830 - "Issue #657: quick-note:https://github.com/earendil-works/pi"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #657: quick-note:https://github.com/earendil-works/pi, Implementation Prompt, Issue #657: quick-note:https://github.com/earendil-works/pi, Relevant Files to Read First, Risk Flags, TODO List

### Community 831 - "Issue #659: quick-note:https://github.com/nex-agi/Nex-N2"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #659: quick-note:https://github.com/nex-agi/Nex-N2, Implementation Prompt, Issue #659: quick-note:https://github.com/nex-agi/Nex-N2, Relevant Files to Read First, Risk Flags, TODO List

### Community 832 - "Issue #660: quick-note:https://github.com/getsentry/sentry-for-ai"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #660: quick-note:https://github.com/getsentry/sentry-for-ai, Implementation Prompt, Issue #660: quick-note:https://github.com/getsentry/sentry-for-ai, Relevant Files to Read First, Risk Flags, TODO List

### Community 833 - "Issue #661: quick-note:https://github.com/XiaomiMiMo/MiMo-Code"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #661: quick-note:https://github.com/XiaomiMiMo/MiMo-Code, Implementation Prompt, Issue #661: quick-note:https://github.com/XiaomiMiMo/MiMo-Code, Relevant Files to Read First, Risk Flags, TODO List

### Community 834 - "Issue #664: quick-note:https://github.com/Grominet95/jarvis-OS"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #664: quick-note:https://github.com/Grominet95/jarvis-OS, Implementation Prompt, Issue #664: quick-note:https://github.com/Grominet95/jarvis-OS, Relevant Files to Read First, Risk Flags, TODO List

### Community 835 - "Issue #666: quick-note:https://github.com/porokka/jarvis-os"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #666: quick-note:https://github.com/porokka/jarvis-os, Implementation Prompt, Issue #666: quick-note:https://github.com/porokka/jarvis-os, Relevant Files to Read First, Risk Flags, TODO List

### Community 836 - "Issue #670: quick-note:https://github.com/perplexityai/bumblebee"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #670: quick-note:https://github.com/perplexityai/bumblebee, Implementation Prompt, Issue #670: quick-note:https://github.com/perplexityai/bumblebee, Relevant Files to Read First, Risk Flags, TODO List

### Community 837 - "Issue #672: quick-note:https://github.com/Chachamaru127/claude-code-harness"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #672: quick-note:https://github.com/Chachamaru127/claude-code-harness, Implementation Prompt, Issue #672: quick-note:https://github.com/Chachamaru127/claude-code-harness, Relevant Files to Read First, Risk Flags, TODO List

### Community 838 - "Issue #676: quick-note:https://github.com/WeiboAI/VibeThinker"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #676: quick-note:https://github.com/WeiboAI/VibeThinker, Implementation Prompt, Issue #676: quick-note:https://github.com/WeiboAI/VibeThinker, Relevant Files to Read First, Risk Flags, TODO List

### Community 839 - "Issue #820: quick-note:https://github.com/cobusgreyling/loop-engineering"
Cohesion: 0.25
Nodes (7): Architectural Notes, Context Plan — Issue #820: quick-note:https://github.com/cobusgreyling/loop-engineering, Implementation Prompt, Issue #820: quick-note:https://github.com/cobusgreyling/loop-engineering, Relevant Files to Read First, Risk Flags, TODO List

### Community 840 - "Positional Encoding Internals"
Cohesion: 0.25
Nodes (7): ALiBi (Attention with Linear Biases), Comparison, Learned Positional Embeddings, Positional Encoding Internals, RoPE Scaling for Long Contexts, Rotary Positional Embedding (RoPE), Sinusoidal Positional Encoding (Original Transformer)

### Community 841 - "TestRequireAdmin"
Cohesion: 0.33
Nodes (3): Return a FastAPI dependency that checks for a specific permission., require_permission(), TestRequireAdmin

### Community 842 - "TOP 6 — Highest-ROI Items (Validated by Opus Research Agent)"
Cohesion: 0.25
Nodes (8): ★1 — 3-Phase Context-Pruner Middleware [P0] [CBF], ★2 — Specialized Sub-Agents with Per-Role Cheap Models [P0] [CBF + HRM], ★3 — Reasoning Token Budget + Toggle [P0] [NVD], ★4 — Skill/Procedural Memory (agentskills.io compatible) [P1] [HRM], ★5 — Sandboxed Agent Execution (E2B / Docker micro-VM) [P1] [CHM] ✅ Delivered 2026-07-04, ★6 — Cost Analytics + FTS5 Shared Memory + Agent Constitution [P1] [AOS], ★7 — Adaptive Loop Halting (Early Exit on High Confidence) [P1] [MYT + HRM], TOP 6 — Highest-ROI Items (Validated by Opus Research Agent)

### Community 843 - "SECTION A — Agent Efficiency (Hermes / AOS / MYT)"
Cohesion: 0.25
Nodes (8): A1 — Hermes ChatML Prompt Format for Tool Calling [P0] [HRM], A2 — Multi-Hop Reasoning Chain (ReAct / Tree-of-Thought) [P0] [HRM], A3 — Agent Capability Registry + Dynamic Tool Discovery [P1] [AOS], A4 — Async Task Queue with Priority and Backpressure [P1] [AOS], A5 — Inter-Agent Message Bus [P1] [AOS / MYT], A6 — Shared Blackboard Memory for Swarm Agents [P1] [MYT], A7 — Agent Self-Improvement Loop [P2] [HRM / AOS], SECTION A — Agent Efficiency (Hermes / AOS / MYT)

### Community 844 - "SECTION C — Direct Chat Improvements (CBF / HRM)"
Cohesion: 0.25
Nodes (8): C1 — Structured Output / JSON Mode [P0] [CBF / HRM], C2 — Function Calling / Tool Use (OpenAI-Compatible) [P0] [CBF / HRM], C3 — Streaming with Proper Delta Reconstruction [P1] [CBF], C4 — Chat History Persistence + Retrieval [P1] [AOS / HRM], C5 — Context Window Management + Smart Truncation [P1] [CBF / HRM], C6 — Prompt Caching (Anthropic-Compatible) [P1] [HRM], C7 — Embeddings Pipeline + Vector Search [P2] [AOS / CBF], SECTION C — Direct Chat Improvements (CBF / HRM)

### Community 845 - "Runbook — Instance Activation"
Cohesion: 0.25
Nodes (7): Option A — disable the gate (self-hosted), Option B — self-mint a signed code with your own key, Option C — request a code (downstream user), Runbook — Instance Activation, Security notes, TL;DR — you are blocked at the activation screen, Why activation exists

### Community 846 - "Prime Agent Runtime"
Cohesion: 0.25
Nodes (8): Configuration, Deploying on Render, Installation, Prime Agent Runtime, `PRIME_AGENT_TRUST_WORKSPACE`, Routing LLM traffic through our proxy, Verifying, What the adapter drives

### Community 847 - "PULL_REQUEST_TEMPLATE.md"
Cohesion: 0.25
Nodes (7): Changelog, Changes, Council Review (for larger PRs), Related, Risky Module Review, Summary, Testing

### Community 848 - "get_livekit_config"
Cohesion: 0.18
Nodes (11): SAM_LLM_* env vars must override the NVIDIA defaults (Hermes/proxy routing)., Under TESTING the in-process worker must never be eligible to start., OPT-IN: defaulting to on OOM-killed the 512MB Render instance at boot…, test_config_configured(), test_config_llm_override(), test_config_unconfigured_reports_missing(), test_in_process_flag_default_off(), test_in_process_flag_forced_off_under_testing() (+3 more)

### Community 849 - "capture_screens.py"
Cohesion: 0.29
Nodes (9): Popen, _capture(), _login(), main(), Launch the local uvicorn server (activated, sqlite, loops off) for capture., _start_server(), _wait_up(), filed() (+1 more)

### Community 850 - "Prompt Library"
Cohesion: 0.25
Nodes (8): Agents, Commands, How This Library Is Maintained, Philosophy, Prompt Library, Skills, Transparency, What Is This?

### Community 851 - "CLAUDE.md — router/"
Cohesion: 0.25
Nodes (7): Adding a New Model, Adding a New Task Category, CLAUDE.md — router/, Environment Variables, Invariants — Do Not Break, Testing, What This Package Does

### Community 852 - "test_tasks_awaiting_approval_api.py"
Cohesion: 0.40
Nodes (10): _client(), asyncio, Task, TestClient, GET /api/tasks/awaiting-approval — dashboard surface for the pre-execution…, _seed(), test_admin_sees_system_owned_gated_tasks(), test_approving_removes_task_from_awaiting_list() (+2 more)

### Community 853 - "crispy_burn_in.py"
Cohesion: 0.36
Nodes (7): evaluate_burn_in(), fetch_status_json(), main(), Any, scripts/crispy_burn_in.py — Evaluate CRISPY burn-in criteria for promotion.…, Fetch /api/autonomy/status and return the parsed JSON., Evaluate the burn-in criteria against a ``crispy_run_history`` payload. Returns…

### Community 854 - "run_patched_colibri.py"
Cohesion: 0.36
Nodes (7): _exit_watch_delay(), main(), _patched_popen(), scripts/run_patched_colibri.py Pre-launch wrapper for JustVugg/colibri…, Resolve the COLIBRI_PATCH_EXIT_WATCH delay in seconds, clamped to [0, 60].…, Intercept JustVugg Engine -> glm.exe Popen and forward outer argv. Upstream…, _resolve_target()

### Community 855 - "SessionMemory"
Cohesion: 0.25
Nodes (5): Any, Managed Agents Dreams — session memory and dream consolidation for managed…, An individual memory snapshot from an agent session., Record a new session memory for this agent., SessionMemory

### Community 856 - "local_brain_provider_config"
Cohesion: 0.29
Nodes (9): local_brain_enabled(), local_brain_provider_config(), local_brain_status(), ProviderConfig, providers/local_brain.py — Free local brain served by the local llama-…, Return True iff the operator opted in via ``LOCAL_BRAIN_ENABLED=true``., Cheap status snapshot for tests + admin UI., Return the ``ProviderConfig`` for the local brain, or ``None`` when disabled.… (+1 more)

### Community 857 - "test_compose_and_coordinate_api.py"
Cohesion: 0.36
Nodes (5): _auth_override(), AuthContext, test_coordinate_dependency_aware_tasks_block_missing_dependencies(), test_coordinate_dependency_aware_tasks_succeed_with_dependencies(), test_coordinate_legacy_workers_flow_remains_backward_compatible()

### Community 858 - "SeoAuditRequest"
Cohesion: 0.04
Nodes (31): field_validator, Request to run an SEO/GEO/AIO audit against a website., SeoAuditRequest, _count_syllables(), estimate_pixel_width(), flesch_reading_ease(), normalize_url(), Approximate SERP rendering width of ``text`` in pixels. (+23 more)

### Community 859 - "test_local_brain_router_smoke.py"
Cohesion: 0.25
Nodes (7): Smoke test: backend/local_brain_router is mounted on the public FastAPI app.…, Importing backend.server.app must not raise AttributeError or NameError., The /api/local-brain/state GET route must be reachable via the FastAPI app.…, The local_brain_router symbol MUST be importable + prefixed correctly. Quick…, test_backend_server_app_loads_without_attributeerror(), test_local_brain_router_module_is_wired(), test_local_brain_state_route_is_mounted_on_public_app()

### Community 860 - "test_ping.py"
Cohesion: 0.39
Nodes (7): client(), TestClient, Tests for the /api/ping health endpoint (no auth required)., test_ping_no_auth_required(), test_ping_response_shape(), test_ping_returns_ok(), test_ping_timestamp_is_iso()

### Community 861 - "test_provider_models_db_outage.py"
Cohesion: 0.25
Nodes (7): tests/test_provider_models_db_outage.py — GET /api/providers/{id}/models…, A DB exception during the provider lookup must not surface as a 500., A catalog provider (unified BrainConfig) with no legacy `providers` row must…, A provider_id absent from both Mongo and the predefined catalog is a genuine…, test_provider_models_falls_back_on_db_outage(), test_provider_models_truly_unknown_provider_still_404s(), test_provider_models_unregistered_provider_uses_predefined_catalog()

### Community 862 - "test_runtimes_health_endpoint.py"
Cohesion: 0.25
Nodes (7): hermes_only_manager(), tests/test_runtimes_health_endpoint.py — N2 acceptance: GET /runtimes/health…, Build a RuntimeManager with only internal_agent + Hermes registered. Mirrors…, GET /runtimes/health must include a `hermes` entry when the adapter is…, End-to-end (router level): GET /runtimes/health returns JSON with a `health`…, test_runtimes_health_endpoint_returns_hermes_via_testclient(), test_runtimes_health_includes_hermes_entry()

### Community 863 - "TestMongoGate"
Cohesion: 0.20
Nodes (3): Tests must never mutate a shared operational store., The storage layer's localhost default is a placeholder, not config. Treating it…, TestMongoGate

### Community 864 - "4. Current Architecture (As-Is)"
Cohesion: 0.29
Nodes (7): 4. Current Architecture (As-Is), Bill of Materials, Codebase Map, Current folder structure (problematic), Deployment topology, External providers, Secrets inventory

### Community 865 - "test_serve_spa_prefixes.py"
Cohesion: 0.36
Nodes (7): _prefixes(), Behavioral: GET to a path that has NO upstream handler but IS in the protected…, SPA_PROTECTED_PREFIXES must be exposed at module scope (not inside an if-block)…, test_legitimate_spa_paths_are_not_blocked(), test_protected_paths_are_covered_by_prefix_tuple(), test_serve_spa_returns_non_html_for_protected_orphan_path(), test_spa_protected_prefixes_is_module_level_constant()

### Community 866 - "test_task_store_fails_loud_in_production.py"
Cohesion: 0.25
Nodes (7): fresh_store_module(), Regression: prevent silent TaskStore in-memory fallback in production. The…, Force a fresh import of tasks.store so module-level state is clean., With TESTING unset (production), TaskStore(db=None) MUST raise., With TESTING=true (CI), TaskStore(db=None) MUST allow in-memory fallback., test_task_store_allows_inmemory_when_testing(), test_task_store_raises_in_production()

### Community 867 - "dry_clone_repo"
Cohesion: 0.36
Nodes (5): test_dry_clone_repo_handles_missing_url(), test_dry_clone_repo_handles_subprocess_failure(), dry_clone_repo(), Validate repository access by performing a shallow, no-checkout git clone and…, Attempt a shallow, non-checkout clone into a temporary directory to validate…

### Community 868 - "TOOLS.md — Available Tools for AI Agents"
Cohesion: 0.25
Nodes (7): AI Runner Tools, API Endpoints (when proxy is running), File Tools, OpenClaw Integration, Shell / Process Tools, Skills (invoke via CLAUDE.md instructions), TOOLS.md — Available Tools for AI Agents

### Community 869 - "TestNormalizeToolChoice"
Cohesion: 0.31
Nodes (4): _normalize_tool_choice(), Normalize the ``tool_choice`` parameter for the upstream backend. OpenAI…, Cloud models (with / in name) should keep tool_choice as-is., TestNormalizeToolChoice

### Community 871 - "Full-Output Enforcement"
Cohesion: 0.29
Nodes (6): Banned Output Patterns, Baseline, Execution Process, Full-Output Enforcement, Handling Long Outputs, Quick Check

### Community 872 - "summarise.sh"
Cohesion: 0.48
Nodes (5): bottom(), divider(), row(), summarise.sh script, top()

### Community 873 - "updater.py"
Cohesion: 0.43
Nodes (6): _extract_unreleased_body(), _insert(), main(), Insert the Maintenance changelog section at the end of the [Unreleased] block.…, Return (body_start, body_end_exclusive, body) for the [Unreleased] block., _read_template()

### Community 874 - "ModelRegistry"
Cohesion: 0.29
Nodes (4): ModelRegistry, A centralized registry for available LLM models and their metadata. This class…, Returns a list of all registered models metadata., Retrieves a specific model's metadata by its name (case-insensitive). Returns…

### Community 875 - "verify_token"
Cohesion: 0.15
Nodes (13): Test JWT token creation and verification., Test refresh token creation and validation., Test that access token fails with refresh validation., Test refreshing access token with refresh token., test_invalid_token_type(), test_refresh_access_token(), test_refresh_token_creation(), test_token_creation_and_verification() (+5 more)

### Community 876 - "AI Engineering Insights Skill"
Cohesion: 0.29
Nodes (6): AI Engineering Insights Skill, Integration Points, Key Design Choices, Module: `agents/ai_insights.py`, References, What's Unique About the DX Report

### Community 877 - "Skill: hybrid-reasoning (Hybrid AI)"
Cohesion: 0.29
Nodes (6): Branch, Components, Purpose, Quick Start, Skill: hybrid-reasoning (Hybrid AI), Testing

### Community 878 - "Karpathy Guidelines Skill"
Cohesion: 0.29
Nodes (6): 1. Think Before Coding, 2. Simplicity First, 3. Surgical Changes, 4. Goal-Driven Execution, Integration points in this repo, Karpathy Guidelines Skill

### Community 879 - "Skill: Managed Agents Dreams"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: Managed Agents Dreams, Testing, Usage

### Community 880 - "Skill: Multi-Agent Coordinator"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: Multi-Agent Coordinator, Testing, Usage

### Community 881 - "Skill: Obsidian Knowledge Graph"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: Obsidian Knowledge Graph, Testing, Usage

### Community 882 - "Multi-Agent Research Coordinator Skill"
Cohesion: 0.29
Nodes (6): Default Plan Shape, Module: `agents/research_coordinator.py`, Multi-Agent Research Coordinator Skill, Quick-Note Issue: #238, Roles, What's Unique

### Community 883 - "Skill: SuperClaude Slash Commands"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: SuperClaude Slash Commands, Testing, Usage

### Community 884 - "Skill: SuperClaude Workflow Engine"
Cohesion: 0.29
Nodes (6): Key Classes, Purpose, Related Issues, Skill: SuperClaude Workflow Engine, Testing, Usage

### Community 885 - "Active Task Tracker"
Cohesion: 0.29
Nodes (6): Active Task Tracker, Bug Log, Current Sprint Tasks, Roadmap Items (from `docs/roadmap-killer-todos.md`), Session Log, Status Key

### Community 886 - "ADR-006: Strangler Fig migration with backward-compat shims"
Cohesion: 0.29
Nodes (6): ADR-006: Strangler Fig migration with backward-compat shims, Consequences, Context, Decision, Examples, Migration path

### Community 887 - "claude-mem Plugin — Persistent Memory for All Sessions"
Cohesion: 0.29
Nodes (6): claude-mem Plugin — Persistent Memory for All Sessions, Enabling it elsewhere, How it's wired, Notes, Scope and limits, Why the source is pinned (`ref` + `sha`)

### Community 888 - "Implementation plan + TO-DO (check off as you go)"
Cohesion: 0.29
Nodes (7): Implementation plan + TO-DO (check off as you go), Phase 1 — Stop the bleeding + paid kill switch (do first, ship alone if needed), Phase 2 — Per-surface assignment in the UI (the "one place"), Phase 3 — Persistence hardening (issues #537, #524), Phase 4 — Onboarding fixes (issues #593, #619; PR #623), Phase 5 — Reliability for hands-off autonomy (issue #522) [larger; may split to own PR], Phase 6 — Green the tests + housekeeping

### Community 889 - "Topics Covered"
Cohesion: 0.29
Nodes (7): 1. Architecture, 2. Tokenization, 3. Training, 4. Inference, 5. Embeddings, LLM Internals, Topics Covered

### Community 890 - "LLM Router — migration guide"
Cohesion: 0.29
Nodes (7): Adding the config files, Gateway mode, LLM Router — migration guide, Migrating a caller to the router directly, Rollback checklist, What changes for callers, What is not migrated

### Community 891 - "_FakePersistence"
Cohesion: 0.20
Nodes (6): _FakePersistence, Schedule count must stay bounded even under 50 consecutive task failures. This…, In-memory ScheduleStore stand-in (sync upsert/remove/load_all)., Creating the same schedule name twice returns the same job — no duplication., test_schedule_create_idempotent_by_name(), test_schedule_growth_bounded_under_failure_storm()

### Community 892 - "Cloudflare = the real working app"
Cohesion: 0.29
Nodes (6): Backend (Render), Cloudflare dashboard settings to verify, Cloudflare = the real working app, How it works, Notes, Verify after deploy

### Community 893 - "CI Troubleshooting Runbook"
Cohesion: 0.20
Nodes (10): A test hangs in CI but passes locally, All three CI jobs fail with "git exit code 128" in Post Checkout, CI Troubleshooting Runbook, CodeQL action version, Frontend tests fail in parallel / async timer leaks, GitHub Actions YAML block scalar — bash heredoc content at column 0, Python 3.13 compatibility status, Python test job fails — "Process completed with exit code 1", no .pytest_cache found (+2 more)

### Community 894 - "6. Agent Architecture"
Cohesion: 0.50
Nodes (4): 6. Agent Architecture, Agent lifecycle, Current state, Internet access (Web Reach) — use it to verify, not guess

### Community 895 - "production"
Cohesion: 0.29
Nodes (7): browserslist, development, production, >0.2%, last 1 chrome version, not dead, not op_mini all

### Community 896 - "report_to_markdown"
Cohesion: 0.11
Nodes (26): export_seo_audit(), Export a stored audit. - ``csv`` aggregated findings, Screaming Frog…, _build_curl_cffi_fetcher(), _build_pdf(), main(), _parse_args(), Namespace, Path (+18 more)

### Community 897 - "get_workflow_orchestrator"
Cohesion: 0.04
Nodes (47): _expected_admin_secret(), _extract_admin_token(), BaseModel, backend/admin_update_task_router.py Step 1: POST…, Mount the update-task endpoint on ``app``. Idempotent: skips if a path with the…, Body for ``POST /api/workflow/orchestrator/update-task/{run_id}``.…, Resolve the admin secret from env. Order matches admin_digest_router.py:…, Inject ``additional_instructions`` into a paused or running WorkflowRun.… (+39 more)

### Community 898 - "launch-claude-code.sh"
Cohesion: 0.43
Nodes (6): ANTHROPIC_API_KEY, ANTHROPIC_MODEL, log_error(), log_header(), log_success(), launch-claude-code.sh script

### Community 900 - "PRD — README Marketing Refresh"
Cohesion: 0.29
Nodes (6): Backlog / Nice-to-Have, Files Touched, Original Problem Statement, PRD — README Marketing Refresh, User Decisions, What Was Done — 2026-04-27

### Community 902 - "check_changelog_parity.py"
Cohesion: 0.43
Nodes (6): _blocks(), main(), normalize_text(), scripts/check_changelog_parity.py CI guard for the changelog mirror. Closes the…, Return a list of human-readable corruption issues in *content*. Detects (1) git…, scan_corruption()

### Community 903 - "e2e_smoke.py"
Cohesion: 0.57
Nodes (5): _chat(), check(), _health(), _models(), _req()

### Community 904 - "Security Policy"
Cohesion: 0.18
Nodes (11): Authentication, Authorization, How to Report, Known Security Trade-offs, Reporting a Vulnerability, Response Timeline, Scope, Security Design (+3 more)

### Community 905 - "task_runner.py"
Cohesion: 0.33
Nodes (6): check_health(), Submit a task to the agent planner., Submit a simple task via the tasks API., Check if the proxy is running., submit_simple_task(), submit_task()

### Community 906 - "Page"
Cohesion: 0.14
Nodes (9): Page, Run fn() and report any critical console errors., Dashboard page — stats, activity, navigation., Runtimes: list, health, decisions, policy., Settings, Secrets, Features, Setup, GitHub, Activation., TestDashboard, TestRuntimes, TestSettings (+1 more)

### Community 907 - "test_daily_2026_06_14.py"
Cohesion: 0.38
Nodes (6): Regression tests for daily-2026-06-14 improvements. Anthropic retires the…, ci-failure-autofix.yml must call the Anthropic API with claude-sonnet-4-6, as…, No GitHub Actions workflow or CI script should reference a retired Claude 4…, _read(), test_ci_autofix_workflow_uses_sonnet_4_6(), test_no_retired_claude_4_model_ids_in_workflows_or_scripts()

### Community 908 - "test_event_log.py"
Cohesion: 0.45
Nodes (10): Path, _store(), test_append_event_payload_roundtrips(), test_append_event_positions_are_monotonic(), test_append_event_stores_and_increments_count(), test_events_are_isolated_per_session(), test_events_survive_store_restart(), test_get_events_empty_session() (+2 more)

### Community 911 - "cost_tracker.py"
Cohesion: 0.25
Nodes (8): _build_cost_table(), get_stats(), _load_env_overrides(), Any, Per-model cost attribution for the LLM provider router. Maintains in-memory…, Return a JSON-serialisable snapshot of per-model cost attribution., Parse MODEL_COST_INPUT / MODEL_COST_OUTPUT env overrides. Format:…, _reset()

### Community 912 - "TestGithubTokenSQLiteRegression"
Cohesion: 0.38
Nodes (4): MonkeyPatch, TestClient, Regression test for PUT/DELETE /api/github/token returning 500 for SQLite-…, TestGithubTokenSQLiteRegression

### Community 913 - "_start_ceo_agency"
Cohesion: 0.31
Nodes (8): Start the 24×7 CEO agency loop that *proactively* generates work. Without this…, _start_ceo_agency(), tests/test_ceo_agency_startup.py — the CEO loop must actually be started. Root…, A failure constructing/starting the CEO must not crash app startup., _reset_agency_singleton(), test_ceo_agency_can_be_disabled(), test_ceo_agency_starts_by_default(), test_ceo_agency_startup_never_raises()

### Community 914 - "10. CI/CD Standards"
Cohesion: 0.67
Nodes (3): 10. CI/CD Standards, Deployment, Pipeline (22 checks)

### Community 916 - "TestActiveStrategy"
Cohesion: 0.29
Nodes (3): parametrize, A typo must not silently pick some other distribution., TestActiveStrategy

### Community 917 - "_resolve_default_executor_model"
Cohesion: 0.50
Nodes (3): Any, Resolve the default executor model via the catalog (UNIT 7). Was hardcoded to…, _resolve_default_executor_model()

### Community 918 - "TestParseToolCalls"
Cohesion: 0.39
Nodes (3): _parse_tool_calls_from_response(), Parse OpenAI tool_calls from a model response. Handles: - Direct JSON…, TestParseToolCalls

### Community 920 - "/fix-bug — Bug Fix Agent"
Cohesion: 0.33
Nodes (5): Escalation, /fix-bug — Bug Fix Agent, Process, Rules, Usage

### Community 921 - "Command: /plan"
Cohesion: 0.33
Nodes (5): Command: /plan, References, Usage, What It Does, When to Use

### Community 922 - "pre-commit"
Cohesion: 0.60
Nodes (5): pre-commit script, _error(), _head(), _info(), _warn()

### Community 923 - "Skill: browserbase-fetch — Lightweight Web Fetch"
Cohesion: 0.33
Nodes (5): Checking the platform health, Python snippet, Setup, Skill: browserbase-fetch — Lightweight Web Fetch, When to use vs browser

### Community 924 - "Twitter Insights — Issue #228"
Cohesion: 0.33
Nodes (5): Action Items, Key Observations, References, Summary, Twitter Insights — Issue #228

### Community 925 - "Twitter Insights — Issue #231"
Cohesion: 0.33
Nodes (5): Action Items, Key Observations, References, Summary, Twitter Insights — Issue #231

### Community 926 - "OpenAI Codex CLI — Local LLM Server Config"
Cohesion: 0.33
Nodes (5): Codex Config File (`~/.codex/config.yaml`), Notes, OpenAI Codex CLI — Local LLM Server Config, Recommended Models, Setup

### Community 927 - "ADR-001: Adopt packages/ directory structure"
Cohesion: 0.33
Nodes (5): ADR-001: Adopt packages/ directory structure, Consequences, Context, Decision, Status

### Community 928 - "ADR-002: Centralize configuration in packages/config/"
Cohesion: 0.33
Nodes (5): ADR-002: Centralize configuration in packages/config/, Consequences, Context, Decision, Status

### Community 929 - "ADR-003: Provider abstraction with unified interface"
Cohesion: 0.33
Nodes (5): ADR-003: Provider abstraction with unified interface, Consequences, Context, Decision, Status

### Community 930 - "ADR-004: Event bus for loosely coupled communication"
Cohesion: 0.33
Nodes (5): ADR-004: Event bus for loosely coupled communication, Consequences, Context, Decision, Status

### Community 931 - "ADR-005: Merge Hermes into the main backend service"
Cohesion: 0.33
Nodes (5): ADR-005: Merge Hermes into the main backend service, Consequences, Context, Decision, Status

### Community 932 - "ADR-007: Storage backend duck-typing over formal ABC"
Cohesion: 0.33
Nodes (5): ADR-007: Storage backend duck-typing over formal ABC, Consequences, Context, Decision, Rationale

### Community 933 - "Phases"
Cohesion: 0.33
Nodes (6): Phase 0 — `RepoConnection` plumbing + delivery-policy detection, Phase 1 — Plan-PR → Implementation  *(highest leverage; closes the live gap)*, Phase 2 — Review-comment resolution (Codex / CodeRabbit), Phase 3 — Quality gate + policy-conformant landing, Phase 4 — Monitor & regression guard, Phases

### Community 934 - "5. The five autonomous loops"
Cohesion: 0.33
Nodes (6): 5. The five autonomous loops, Loop 1 — Self-heal from logs *(closed loop)*, Loop 2 — Feature generation, Loop 3 — Agentic SDLC (the golden path), Loop 4 — Trends contextually applied, Loop 5 — Per-onboarded-site autonomy

### Community 935 - "Master Goal Prompt — Autonomous Agency CEO"
Cohesion: 0.33
Nodes (6): Cadence & stop conditions, First-run bootstrap, Hard constraints, Master Goal Prompt — Autonomous Agency CEO, Mission, The gate contract (Telegram human-in-the-loop)

### Community 936 - "Agency Core — Operational Knowledge (verified live, 2026-06-10/11)"
Cohesion: 0.33
Nodes (5): Agency Core — Operational Knowledge (verified live, 2026-06-10/11), Architecture truths, Open backlog (epic #504), Pros of linking the GitHub repo (vs running unlinked), Runbooks

### Community 937 - "1. What This Repo Does"
Cohesion: 0.40
Nodes (5): 1. What This Repo Does, Non-goals, Production deployment, Success metrics, What the platform is

### Community 938 - "Pre-Mortem Analysis: Agency Core autonomy story (Cloudflare deployment)"
Cohesion: 0.33
Nodes (5): Elephants, named, Pre-Mortem Analysis: Agency Core autonomy story (Cloudflare deployment), Risk Registry, Summary, What was already fixed during this pre-mortem

### Community 939 - "SECTION B — NVIDIA / Cloud Model Integration (Nemotron / NVD)"
Cohesion: 0.33
Nodes (6): B1 — Nemotron Reward Model for Agent Step Scoring [P0] [NVD], B2 — SteerLM / RLHF-Style Steering for Local Models [P1] [NVD], B3 — Synthetic Training Data Generation Pipeline [P1] [NVD], B4 — NeMo Guardrails Integration [P1] [NVD], B5 — NIM API Connection Pooling + Circuit Breaker [P1] [NVD], SECTION B — NVIDIA / Cloud Model Integration (Nemotron / NVD)

### Community 940 - "SECTION D — Deployment & Infrastructure (CHM / NVD)"
Cohesion: 0.33
Nodes (6): D1 — Helm Chart for Kubernetes Deployment [P1] [CHM], D2 — Docker Compose Production Stack [P1] [CHM], D3 — OpenTelemetry Distributed Tracing [P1] [NVD / CHM], D4 — Horizontal Scaling with Redis State Backend [P2] [CHM / AOS], D5 — Model Auto-Management (Pull, Warm, Evict) [P2] [NVD], SECTION D — Deployment & Infrastructure (CHM / NVD)

### Community 943 - "8. Authentication Architecture"
Cohesion: 0.67
Nodes (3): 8. Authentication Architecture, Auth dependency chain, Auth flows

### Community 944 - ".execute"
Cohesion: 0.60
Nodes (3): TaskResult, TaskSpec, Execute via OpenCode CLI: `opencode run --json <instruction>`.

### Community 946 - "apply_phase1_changes.py"
Cohesion: 0.33
Nodes (5): apply_backend_change(), apply_workflow_change(), Apply Phase 1 paid-provider kill switch changes to backend/server.py and…, Insert provider policy endpoints before @app.get('/api/models/catalog')., Modify _resolve_brain_provider to read allow_paid from the durable policy.

### Community 947 - "_replace"
Cohesion: 0.40
Nodes (5): main(), Path, Regex-replace ``pattern`` with ``repl`` in ``path``; return the match count., Bump the version across all version-bearing files; fail fast if any are missed., _replace()

### Community 948 - "check_doc_images.py"
Cohesion: 0.60
Nodes (5): check_broken_links(), check_gallery_sync(), find_duplicate_images(), _local_refs(), main()

### Community 949 - "gen_screenshots.py"
Cohesion: 0.53
Nodes (5): main(), out_path(), Path, Generate Langfuse and Telegram mockup screenshots for documentation., save_html_screenshot()

### Community 950 - "gen_v4_screenshots.py"
Cohesion: 0.60
Nodes (5): build_screens(), page(), Generate v4 UI screenshots for the README using HTML mockups + system…, shot(), sidebar()

### Community 952 - "setup-claude-code.sh script"
Cohesion: 0.60
Nodes (5): log_error(), log_info(), log_success(), print_header(), setup-claude-code.sh script

### Community 955 - "test_generate_context_standing_instructions.py"
Cohesion: 0.40
Nodes (5): _load_module(), Regression test: autonomous issue-context generation must not silently truncate…, Sanity check on the fixture assumption this test relies on., test_claude_md_standing_instructions_present_past_4000_chars(), test_load_codebase_context_includes_standing_instructions()

### Community 956 - "_auth_headers"
Cohesion: 0.73
Nodes (5): _auth_headers(), TestClient, test_agent_profile_api_preserves_ui_fields(), test_backend_server_exposes_observability_savings_and_usage(), test_backend_server_exposes_schedules_routes()

### Community 957 - "TestGithubSignalHardening"
Cohesion: 0.22
Nodes (4): FakeResp, fetch_github_signals must degrade gracefully (log + return empty lists) on a…, Even with a 200, a malformed/rate-limited body that isn't a list must not be…, TestGithubSignalHardening

### Community 958 - "harness.py"
Cohesion: 0.40
Nodes (3): EvalResult, Evaluation harness – runs an agent against a Task, records the Trajectory,…, Outcome of running one task through the harness.

### Community 959 - "_rrf"
Cohesion: 0.40
Nodes (5): Combine ranked lists with Reciprocal Rank Fusion., _rrf(), test_rrf_merges_two_rankings(), test_rrf_scores_descending(), test_rrf_single_ranking_preserves_order()

### Community 960 - "_get_current_user"
Cohesion: 0.29
Nodes (8): _get_bearer_token(), _get_current_user(), logout(), Depends, Extract and validate current user from token., Get current authenticated user., Logout (token invalidation happens on frontend by clearing localStorage)., Extract bearer token from Authorization header.

### Community 963 - "/arch-review — Architecture Agent"
Cohesion: 0.40
Nodes (4): /arch-review — Architecture Agent, Key Architectural Principles, Steps, When to use

### Community 964 - "/devops-check — DevOps Agent"
Cohesion: 0.40
Nodes (4): Deployment Checklist, /devops-check — DevOps Agent, Steps, When to use

### Community 965 - "/docs-update — Documentation Agent"
Cohesion: 0.40
Nodes (4): /docs-update — Documentation Agent, Documentation Standards, Steps, When to use

### Community 966 - "/qa-check — QA Agent"
Cohesion: 0.40
Nodes (4): /qa-check — QA Agent, Steps, What NOT to do, When to use

### Community 967 - "Command: /review"
Cohesion: 0.40
Nodes (4): Command: /review, References, Usage, What It Does

### Community 968 - "/security-audit — Security Agent"
Cohesion: 0.40
Nodes (4): Escalation, /security-audit — Security Agent, Steps, When to use

### Community 969 - "pre-push"
Cohesion: 0.70
Nodes (4): pre-push script, _error(), _head(), _info()

### Community 970 - "Skill: browserbase-search — Structured Web Search"
Cohesion: 0.40
Nodes (4): Best practice: search → fetch → browse, Python snippet, Setup, Skill: browserbase-search — Structured Web Search

### Community 971 - "Issue #230 — DUPLICATE"
Cohesion: 0.40
Nodes (4): Actions Taken, Issue #230 — DUPLICATE, References, Resolution

### Community 973 - "Agent job lifecycle"
Cohesion: 0.40
Nodes (4): Agent job lifecycle, API, Progress phases, States

### Community 974 - "Docker (local or any container host)"
Cohesion: 0.40
Nodes (4): Build, Docker (local or any container host), Provider configuration (recommended for cloud), Run (minimal)

### Community 975 - "Rollout"
Cohesion: 0.40
Nodes (5): 1. Verify the router sees your providers, 2. Enable on one instance, 3. Watch for a few hours, 4. Roll out or roll back, Rollout

### Community 976 - "test_harness_spec.py"
Cohesion: 0.10
Nodes (18): LessonStore, Connection, Path, SQLite-backed store of failure lessons. Thread-safe, zero deps., dict, set, _AllSignatures, _AnyText (+10 more)

### Community 977 - "SECTION E — Autonomy & Self-Healing (AOS / MYT / ECC)"
Cohesion: 0.40
Nodes (5): E1 — Cross-Harness Routing (ECC Pattern) [P1] [ECC], E2 — Self-Healing Agent Loop (Detect + Repair Own Failures) [P1] [AOS / MYT], E3 — Autonomous Monitoring with Trend Watcher [P2] [AOS], E4 — Nightly Self-Evaluation + Regression Tests [P2] [HRM / AOS], SECTION E — Autonomy & Self-Healing (AOS / MYT / ECC)

### Community 978 - "SECTION F — Developer Experience (CBF / ECC)"
Cohesion: 0.40
Nodes (5): F1 — Codebuff-Style Precise Diff Application [P0] [CBF], F2 — MCP Server Exposing Proxy Capabilities [P1] [CBF / ECC], F3 — Local Dev Dashboard with Live Metrics [P2] [CBF / CHM], F4 — SDK / Client Library Generation [P2] [CBF], SECTION F — Developer Experience (CBF / ECC)

### Community 979 - "Runtime troubleshooting"
Cohesion: 0.40
Nodes (4): Agent mode timeout, Missing binary / task harness, Runtime troubleshooting, Workspace validation failures

### Community 980 - "task.py"
Cohesion: 0.43
Nodes (6): Enum, str, Task definition schema for the evaluation harness. Inspired by OpenHarness'…, SuccessCriterion, SuccessCriterionType, TaskDifficulty

### Community 981 - "FakeScheduleCollection"
Cohesion: 0.25
Nodes (3): FakeDeleteResult, FakeScheduleCollection, Minimal async MongoDB-like collection for testing nuclear_cleanup.

### Community 982 - "10. Testing Constitution"
Cohesion: 0.50
Nodes (4): 10. Testing Constitution, Test rules, Test structure, Testing Expectations

### Community 983 - "knowledgeGraphTab.test.js"
Cohesion: 0.40
Nodes (4): { describe, test, expect }, fs, path, src

### Community 984 - "loginFlowNoTimeout.test.js"
Cohesion: 0.40
Nodes (4): apiSource, { describe, test, expect }, fs, path

### Community 985 - "test_company_stale_id_recovery.test.js"
Cohesion: 0.40
Nodes (4): { describe, test, expect }, fs, path, src

### Community 986 - "worker_no_cache.test.js"
Cohesion: 0.40
Nodes (4): { describe, test, expect }, fs, path, workerSource

### Community 987 - "scripts/agile_ceremonies.py"
Cohesion: 0.70
Nodes (4): _load(), main(), ModuleType, _write_summary()

### Community 988 - "governance/__init__.py"
Cohesion: 0.40
Nodes (3): __getattr__(), Any, packages/governance — agent identity, policy, approvals, audit, sandboxes. The…

### Community 989 - "Prompt Library Changelog"
Cohesion: 0.40
Nodes (4): Added, Format, Prompt Library Changelog, [Unreleased]

### Community 990 - "_add_colibri_shim_changelog_entry.py"
Cohesion: 0.50
Nodes (4): main(), _normalise_crlf(), Insert a single new [Unreleased] / ### Added bullet into BOTH changelogs.…, Force LF on write (parity script tolerates either, but a stray CRLF introduced…

### Community 991 - "build_llama_cpp.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), W(), Warn()

### Community 992 - "download_glm52_weights.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), Warn(), W()

### Community 993 - "download_glm52_weights.sh script"
Cohesion: 0.70
Nodes (4): download_glm52_weights.sh script, fail(), ok(), warn()

### Community 994 - "_fetch_pytest_failures.py"
Cohesion: 0.50
Nodes (4): _gh_json(), main(), Pull the python-test failure log via gh run view --log and print the failing-…, Run a gh CLI call and parse its JSON stdout. Returns (parsed | None, stderr).

### Community 995 - "setup_colibri.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), Warn(), W()

### Community 996 - "setup_colibri.sh script"
Cohesion: 0.70
Nodes (4): setup_colibri.sh script, fail(), ok(), warn()

### Community 997 - "status_colibri_server.ps1"
Cohesion: 0.70
Nodes (4): Fail(), Ok(), W(), Warn()

### Community 998 - "client"
Cohesion: 0.40
Nodes (5): auth_headers(), client(), TestClient, TestClient for the backend FastAPI app (one per module for speed)., Login once and return auth headers for the entire module.

### Community 1000 - "TestMobileNavigation"
Cohesion: 0.40
Nodes (3): Mobile-specific: hamburger menu, responsive layout., Verify key pages load in mobile viewport., TestMobileNavigation

### Community 1001 - "test_v5_screens_smoke.py"
Cohesion: 0.50
Nodes (3): _login(), E2E UI smoke test: every v5 screen renders without errors. This is the…, test_every_v5_screen_renders_without_errors()

### Community 1002 - "test_agent_runtime_wrapper.py"
Cohesion: 0.70
Nodes (4): _load_agent_runtime_module(), test_wrapper_exposes_hermes_task_endpoints(), test_wrapper_exposes_opencode_run_endpoint(), test_wrapper_falls_back_to_installed_model()

### Community 1004 - "worker/index.js"
Cohesion: 0.60
Nodes (4): fetch(), needsProxy(), PROXY_PREFIXES, scheduled()

### Community 1005 - "5. AI Provider Architecture"
Cohesion: 0.50
Nodes (4): 5. AI Provider Architecture, Current state, Fallback chain, Provider interface contract

### Community 1006 - "recovery.py"
Cohesion: 0.67
Nodes (3): detect_secrets(), main(), Recover CHANGELOG.md from a Git merge conflict in its [Unreleased] block. Pre-…

### Community 1008 - "TestPaidPolicyDurability"
Cohesion: 0.22
Nodes (3): This is the document the UI toggle writes via _set_provider_policy., Never enable paid spend by accident., TestPaidPolicyDurability

### Community 1009 - "._run_git_command"
Cohesion: 0.25
Nodes (4): Build git intelligence: hotspots, ownership, co-change pairs., Run a git command and return stdout as string., Compute cyclomatic complexity for Python files. Returns 0 for non-Python files…, Extract architectural decisions from git history and inline comments.

### Community 1010 - "Agent Autonomy Roadmap"
Cohesion: 0.25
Nodes (8): Agent Autonomy Roadmap, Design constraints honored, New environment variables, Proactive rate-limit pacing (free-tier reliability), The eight gaps and what closed them, Verification performed, What was already strong (verified, no changes needed), Why this document exists

### Community 1011 - "Setup"
Cohesion: 0.25
Nodes (8): 1. Clone and install, 2. Configure, 3. Start the backend, 4. Start the frontend (development), 5. Onboard your first company, 6. Connect your AI coding tools (optional), Setup, What you need

### Community 1013 - "start_in_process"
Cohesion: 0.25
Nodes (8): start_in_process must be a safe no-op in the test environment (conftest sets…, Flag on but LiveKit env absent → logged no-op, never raises., test_start_in_process_noop_under_testing(), test_start_in_process_noop_when_unconfigured(), Start the voice worker in a daemon thread inside this process. Called by the…, Thread body: run the LiveKit agents server on a dedicated event loop., _run_worker_thread(), start_in_process()

### Community 1014 - "aider_config.sh"
Cohesion: 0.50
Nodes (3): OPENAI_API_BASE, OPENAI_API_KEY, aider_config.sh script

### Community 1017 - "providers.yaml"
Cohesion: 0.50
Nodes (4): Bulkhead sizing, Per-minute token budgets, providers.yaml, Tiers

### Community 1018 - "_known_tool_names"
Cohesion: 0.29
Nodes (5): _known_tool_names(), Any, field_validator, Core tools plus whatever the capability registry currently exposes. A static…, Reject names with no dispatch path, accept everything reachable.

### Community 1019 - "What's New"
Cohesion: 0.29
Nodes (7): 2026-06-16, 2026-06-25, 2026-06-26, 2026-07-04, 2026-07-05, 2026-07-09, What's New

### Community 1020 - "11. Rewrite Strategy"
Cohesion: 0.67
Nodes (3): 11. Rewrite Strategy, Phased approach, Rules

### Community 1021 - "Credential Rotation Runbook"
Cohesion: 0.50
Nodes (3): Credential Rotation Runbook, Guardrails already in place, What to rotate (owner action, ~10 minutes)

### Community 1022 - "Runbook: `make doctor`"
Cohesion: 0.50
Nodes (3): Roadmap, Runbook: `make doctor`, What it checks and why

### Community 1023 - "3. Repository Constitution"
Cohesion: 0.67
Nodes (3): 3. Repository Constitution, Forbidden patterns, Required patterns

### Community 1024 - "7. Scheduler Architecture"
Cohesion: 0.67
Nodes (3): 7. Scheduler Architecture, Current state, Known issues (fixed)

### Community 1025 - "Model and Response Issues"
Cohesion: 0.29
Nodes (7): Model and Response Issues, Model eviction between requests, "Model not found" or 404 on model requests, Responses are empty or very short, Responses get cut off mid-sentence, `<think>...</think>` appears in responses, Very slow first response (30–90 seconds)

### Community 1026 - "ToolCallViewer.jsx"
Cohesion: 0.33
Nodes (5): getToolIcon(), STATUS_BADGES, STATUS_STYLES, TOOL_ICONS, ToolCallRow()

### Community 1027 - "_decompose_into_subtasks"
Cohesion: 0.33
Nodes (6): _decompose_into_subtasks(), Decompose a request into 2-3 sub-tasks for specialist fan-out. Default…, Default decomposition has scout → dev (dev depends on scout)., Caller can steer the dev role/runtime via hints., test_decompose_respects_caller_hints(), test_decompose_returns_scout_and_dev()

### Community 1028 - "render"
Cohesion: 0.50
Nodes (3): RENDER_API_KEY, docker, render

### Community 1029 - "scripts"
Cohesion: 0.50
Nodes (4): scripts, build, start, test

### Community 1030 - "Any"
Cohesion: 0.29
Nodes (4): Any, Actively wake every sleeping/circuit-open runtime. The default health service…, Return the active routing policy as a plain dict., Update the routing policy in-place.

### Community 1031 - "CircuitBreakerOpenError"
Cohesion: 0.50
Nodes (4): CircuitBreakerOpenError, RuntimeError, Raised when a request is blocked by an open circuit breaker., TestCircuitBreakerOpenError

### Community 1032 - "BackgroundServices"
Cohesion: 0.38
Nodes (4): BackgroundServices, Handle returned by ``start_background_services`` — call ``stop()`` on shutdown., Cancel the boot refresh if it is still fetching at shutdown., Shut the in-process Hermes down so port 8100 is released. Uvicorn's own…

### Community 1033 - "operational_incidents.py"
Cohesion: 0.13
Nodes (15): get_operational_incident_tracker(), _iso_from_monotonic(), agent/operational_incidents.py — recurring operational failures, auto-…, Drop all open-phase state. Used by tests., Current UTC wall-clock as an ISO-8601 string., Best-effort wall-clock for a monotonic timestamp taken earlier., Return the shared tracker, creating it on first use., Drop the cached tracker. Used by tests. (+7 more)

### Community 1034 - "TestSupportMatrixDocsSync"
Cohesion: 0.29
Nodes (4): The feature matrix can produce a markdown table for docs., Every config flag referenced in the matrix should be documented., The matrix should cover the key areas from the spec., TestSupportMatrixDocsSync

### Community 1036 - "stop_colibri_server.ps1"
Cohesion: 0.83
Nodes (3): Fail(), Ok(), W()

### Community 1038 - "start_server.sh"
Cohesion: 0.50
Nodes (3): OLLAMA_HOST, OLLAMA_MODELS, start_server.sh script

### Community 1039 - "check_services"
Cohesion: 0.67
Nodes (3): check_services(), main(), Check if local services are running. Extends the original (proxy + Ollama)…

### Community 1045 - "test_no_exception_detail_leaks.py"
Cohesion: 0.50
Nodes (3): parametrize, tests/test_no_exception_detail_leaks.py — Guard against str(exc)/str(e) leaking…, test_no_raw_exception_detail_in_http_response()

### Community 1047 - "github"
Cohesion: 0.50
Nodes (3): github, enabled, silent

### Community 1048 - "test_skills_route_order.py"
Cohesion: 0.67
Nodes (3): tests/test_skills_route_order.py — /api/company/skills must not be shadowed.…, _route_index(), test_static_skills_routes_precede_dynamic_company_id_route()

### Community 1049 - "asyncio"
Cohesion: 0.29
Nodes (7): asyncio, _build_context must return a dict with expected keys., A hung LLM call must not block SAM — it must time out and fall back., A stalled context read must not block process_command indefinitely., test_build_context_returns_dict(), test_call_llm_times_out_and_falls_back(), test_process_command_does_not_hang_when_context_stalls()

### Community 1052 - "The full agent capability roster"
Cohesion: 0.33
Nodes (6): Agile, portfolio & product, Business & domain specialists (auto-provisioned from the URL scan), Content & knowledge, Engineering, Operations & DevOps, The full agent capability roster

### Community 1053 - ".execute"
Cohesion: 0.33
Nodes (3): TaskResult, TaskSpec, Create a conversation in OpenHands and poll for completion.

### Community 1054 - "_merge_changed_files"
Cohesion: 0.33
Nodes (6): _merge_changed_files(), Collect changed_files across all specialists into a single de-duped list., The orchestrator's re-export wrapper delegates to the canonical helper., Duplicate file paths across specialists collapse to a single entry., test_merge_changed_files_dedupes(), test_orch_merge_changed_files_alias()

### Community 1060 - "_normalize_dockerfile"
Cohesion: 0.33
Nodes (6): _normalize_dockerfile(), Parse a Dockerfile into a list of active instruction lines. Strips comment…, Dockerfile.backend must COPY voice/ (server-side TTS + LiveKit token endpoints…, Dockerfile.voice is the standalone home of the heavy voice deps: it must…, test_dockerfile_ships_voice_package(), test_dockerfile_voice_builds_the_worker()

### Community 1062 - "Who is this for?"
Cohesion: 0.40
Nodes (5): The 5-person SaaS startup that can't afford a full team yet, The digital agency running 10 client accounts, The e-commerce shop with a 10-person ops team, The professional services firm that runs on documents and tribal knowledge, Who is this for?

### Community 1080 - "Proof"
Cohesion: 0.40
Nodes (5): Honesty notes (read before quoting the numbers), Proof, Reproduce any audit yourself, The self-audit (yes, we publish our own imperfect score), What's coming next in this directory

### Community 1081 - "_open_dashboard"
Cohesion: 0.67
Nodes (3): _open_dashboard(), Page, Open the dashboard's awaiting-approval surface. Two complementary landmines: 1.…

### Community 1082 - "test_the_reserve_is_bounded_when_read_from_the_environment"
Cohesion: 0.67
Nodes (3): parametrize, Read through the ENV, not the constant — that is where the bug lived.…, test_the_reserve_is_bounded_when_read_from_the_environment()

### Community 1130 - "gather_render_evidence"
Cohesion: 0.50
Nodes (4): gather_render_evidence(), Pull recent Render logs and summarise them for the issue body. This is the…, No RENDER_API_KEY must still file the incident — the recurrence itself is the…, test_evidence_reports_unavailable_when_render_is_not_configured()

### Community 1131 - "Issue → Context → Draft PR automation"
Cohesion: 0.50
Nodes (4): Backfilling existing issues, Free-first model routing, Issue → Context → Draft PR automation, The workflows

### Community 1138 - "The 24x7 agency — your agents never go idle"
Cohesion: 0.50
Nodes (4): Nothing goes down quietly, The 24x7 agency — your agents never go idle, What runs automatically after onboarding, When something goes wrong, agents fix it — not you

### Community 1140 - "Privacy, security, and cost"
Cohesion: 0.50
Nodes (4): Privacy, security, and cost, Security posture, What it costs to run, Your data never leaves your server

### Community 1141 - "record_usage"
Cohesion: 0.50
Nodes (4): cost_for_tokens(), Return the USD cost for (prompt_tokens, completion_tokens) on *model*. Returns…, Record token usage for *model* (fire-and-forget, never raises). ``tag`` is a…, record_usage()

### Community 1148 - "_resolve_default_executor_model"
Cohesion: 0.50
Nodes (3): Any, Resolve the default executor model via the catalog (UNIT 7). Was hardcoded to…, _resolve_default_executor_model()

### Community 1149 - ".execute"
Cohesion: 0.50
Nodes (3): RoutingDecision, TaskResult, TaskSpec

### Community 1192 - "probe_live_providers.py"
Cohesion: 0.67
Nodes (3): main(), probe_one(), ProviderRouter

### Community 1193 - "sam"
Cohesion: 0.50
Nodes (4): agent/sam.py must call emit_agency_observation for voice commands., test_sam_py_traces_voice_commands(), Fresh SAM agent with mocked dependencies., sam()

### Community 1194 - "test_feature_stores_are_wired_on_demand_not_eagerly"
Cohesion: 0.50
Nodes (4): NoReturn, Wire only what is missing — never replace a store somebody registered.…, test_feature_stores_are_wired_on_demand_not_eagerly(), _unexpected_wire()

### Community 1195 - "main"
Cohesion: 0.50
Nodes (4): main(), CLI entrypoint: ``python -m voice.sam_livekit_worker dev|start``., Fail fast with an actionable hint when optional deps are missing., _require_livekit_agents()

### Community 1196 - "_get_current_user_thunk"
Cohesion: 0.67
Nodes (3): _get_current_user_thunk(), _get_optional_user_thunk(), Request

### Community 1197 - "Configuration reference"
Cohesion: 0.67
Nodes (3): Configuration reference, Provider priority chain, Running the brain on local Ollama (via a tunnel)

### Community 1200 - "test_mint_token_rejects_missing_args"
Cohesion: 0.67
Nodes (3): parametrize, Empty key/secret/identity/room must raise ValueError., test_mint_token_rejects_missing_args()

### Community 1201 - "_StopLifespan"
Cohesion: 0.67
Nodes (3): RuntimeError, Sentinel: halt ``lifespan()`` once the startup ordering is observed., _StopLifespan

## Knowledge Gaps
- **3501 isolated node(s):** `duplicate.sh script`, `heartbeat.sh script`, `redact_secrets.sh script`, `docker`, `RENDER_API_KEY` (+3496 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **128 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `_fixture()` connect `_fixture` to `ExecutionRequest`, `AgentScheduler`, `AgentRunner`, `operational_incidents.py`, `Task`, `TestFeaturesAPI`, `direct_chat.py`, `llm/router.py`, `BrainWatchdog`, `AgentSessionStore`, `test_llm_router_strategies.py`, `test_telegram_auto_approve.py`, `test_autonomy_status.py`, `BrainConfig`, `KeyPool`, `test_local_brain_state.py`, `services/background.py`, `test_phase5_doctor.py`, `test_e2b_sandbox.py`, `test_model_router.py`, `test_telegram_diag_endpoint.py`, `SelfHealingAgent`, `tasks/service.py`, `test_llm_router_resilience.py`, `AgentProfile`, `test_direct_chat_async.py`, `test_unit8_model_catalog.py`, `failover_chat_completion`, `webui/router.py`, `PrimeAgentAdapter`, `MCPClient`, `e2e/test_browser.py`, `E2BAdapter`, `test_knowledge_sync.py`, `test_agent_free_brain.py`, `test_sam_livekit.py`, `SecretRecord`, `get_task_store`, `test_runtime_governance.py`, `ResearchTask`, `TestClient`, `test_onboarding_provisioning.py`, `test_openclaw_gateway.py`, `ProceduralMemoryStore`, `TaskWorkflowService`, `clear_cooldowns`, `resolve_e2b_config`, `test_orchestrator_merge_decision.py`, `issue_new_api_key`, `test_agent_tool_governance.py`, `Surface`, `test_new_features_e2e.py`, `cache.py`, `test_brain_config_store.py`, `SeoFixer`, `TaskIn`, `test_context_rulebook.py`, `ArtifactStore`, `disabled`, `test_ceo_supervision.py`, `ImprovementLoop`, `test_issue_intake.py`, `test_startup_warmup.py`, `config.py`, `ChatHistoryStore`, `GoalRecord`, `claim`, `ToolAnnotations`, `test_regression.py`, `test_agile_api.py`, `test_app_settings.py`, `test_e2b_task_wiring.py`, `test_task_clarification.py`, `OllamaCircuitBreaker`, `sam`, `TrendWatcher`, `test_mcp_governance.py`, `test_provider_enable_disable.py`, `TestChatHistoryStore`, `test_features_api.py`, `test_video_transcript.py`, `emit_chat_observation`, `test_portfolio_intake.py`, `OrchestratorQueue`, `test_telegram_freebuff.py`, `FakeCollection`, `TestEstimateTokensForMessages`, `SchedulerStore`, `TestClient`, `test_crispy_workflow.py`, `timedelta`, `PolicyEngine`, `ContextPruner`, `IssueCategory`, `test_trend_watcher.py`, `test_provider_state_durability.py`, `test_platform_controls.py`, `_resolve_push_token`, `test_doctor_coding_brain.py`, `WorkflowBuildRequest`, `test_persistent_memory.py`, `SecurityScanner`, `test_freebuff_bot.py`, `test_llm_router_e2e.py`, `test_provider_router.py`, `test_control_plane_api.py`, `MCPUnavailableError`, `traffic_director.py`, `test_rate_limiter.py`, `test_kimi_bridge_server.py`, `brain_failover.py`, `test_purge_backlog.py`, `test_dashboard_cache.py`, `_resolve_brain_provider`, `NotificationDispatcher`, `test_crispy_burn_in.py`, `test_llm_router_tpm.py`, `test_skill_registry_boot_refresh.py`, `resolve_active_brain`, `isolated_telegram_config`, `test_scheduler_hydration_bounded.py`, `analyze_page`, `capture_screens.py`, `test_sam_voice.py`, `SeoAuditRequest`, `test_ping.py`, `test_runtimes_health_endpoint.py`, `TestMongoGate`, `ClaudeCodeAdapter`, `test_task_store_fails_loud_in_production.py`, `test_telegram_approval_e2e.py`, `test_service_token.py`, `test_agency_fix.py`, `test_output_filter.py`, `model_discovery.py`, `get_workflow_orchestrator`, `test_monitor_lib.py`, `._check_permissions`, `test_v4_api.py`, `cost_tracker.py`, `_resolve_user_github_token`, `_start_ceo_agency`, `allow_paid`, `test_voice_pipeline.py`, `TestNormalizeResponseFormat`, `test_doctor_service_token_check.py`, `test_brain_patch_service_token.py`, `AuditLog`, `test_harness_spec.py`, `test_company_api.py`, `client`, `test_task_service_failed_comment.py`, `SQLiteStore`, `TaskStore`, `test_openclaw_endpoints.py`, `OperationalIncidentTracker`, `test_ai_insights.py`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **Why does `AgentRunner` connect `AgentRunner` to `ExecutionRequest`, `AgentScheduler`, `backend/server.py`, `direct_chat.py`, `AgentSessionStore`, `TaskSpec`, `.run`, `StuckDetector`, `AutonomyTracker`, `proxy.py`, `Workspace`, `MultiAgentSwarm`, `test_direct_chat_async.py`, `failover_chat_completion`, `test_autonomous_agency_e2e.py`, `_StubManager`, `_build_request`, `MCPClient`, `E2BAdapter`, `_get_provider_policy`, `test_agent_free_brain.py`, `WorkspaceTools`, `get_task_store`, `LocalWorkspace`, `RewardScorer`, `TokenBudget`, `test_empirical_verify.py`, `GitHubTools`, `ContextPruner`, `test_agent_tool_governance.py`, `AdaptiveHalter`, `TestZeroAttemptDiagnostics`, `CEODispatcher`, `test_ceo_micromanager.py`, `TestMCPServer`, `ReactScratchpad`, `ContextManager`, `MCPUnavailableError`, `test_governance_api.py`?**
  _High betweenness centrality (0.042) - this node is a cross-community bridge._
- **Why does `ProviderRouter` connect `AgentScheduler` to `backend/server.py`, `ai/router.py`, `test_bedrock_provider.py`, `direct_chat.py`, `system_instruction`, `TestActiveStrategy`, `NvidiaProvider`, `TestBrainFailoverBackoff`, `TestAnthropicPayloadStructuredOutput`, `settings.py`, `probe_live_providers.py`, `_P`, `test_colibri_provider.py`, `test_chat_mode_regressions.py`, `resolve_active_brain`, `test_bedrock_live.py`, `TrafficDirector`, `failover_client.py`, `clear_cooldowns`, `test_all_providers_discovery.py`, `test_anthropic_router.py`, `TestRouterIntegration`, `test_provider_router.py`, `model_discovery.py`, `kimi_bridge_provider_config`?**
  _High betweenness centrality (0.025) - this node is a cross-community bridge._
- **Are the 161 inferred relationships involving `AgentRunner` (e.g. with `AgentCoordinator` and `AgentSpec`) actually correct?**
  _`AgentRunner` has 161 INFERRED edges - model-reasoned connections that need verification._
- **Are the 210 inferred relationships involving `HTTPException` (e.g. with `activate_instance()` and `change_user_role()`) actually correct?**
  _`HTTPException` has 210 INFERRED edges - model-reasoned connections that need verification._
- **Are the 109 inferred relationships involving `AgentSessionStore` (e.g. with `AgentPhaseError` and `AgentRunner`) actually correct?**
  _`AgentSessionStore` has 109 INFERRED edges - model-reasoned connections that need verification._
- **Are the 77 inferred relationships involving `AgentScheduler` (e.g. with `AgentStatusEntry` and `AgentStatusResponse`) actually correct?**
  _`AgentScheduler` has 77 INFERRED edges - model-reasoned connections that need verification._