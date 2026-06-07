- Update generic scanner.

## [Unreleased]

### Added
- `agent/skill_registry.py`: new dynamic SkillRegistry that indexes local `.claude/skills/` and fetches remote skill packs from GitHub registries (agency-agents, agent-skills, anthropic-skills). Provides tech-stack-aware and workflow-aware skill recommendations via `recommend()`.
- `/api/skills` REST endpoints: `GET /api/skills`, `POST /api/skills/recommend`, `GET /api/skills/recommend/auto`, `POST /api/skills/refresh`, `GET /api/skills/{id}`.
- `/api/mcp/servers` CRUD endpoints: `GET`, `POST`, `PATCH /{id}`, `DELETE /{id}` — persists MCP server configurations per user in MongoDB.

### Changed
- `ProvidersScreen` (OllamaTab): replaced mock setTimeout pull with real `api.listModels()` / `api.pullModel()` / `api.deleteModel()` calls; shows loading + error states.
- `ProvidersScreen` (MCPTab): wired to `/api/mcp/servers` — add/remove/connect persisted in DB; delete button added per server.
- `QuickNotesFAB`: replaced fake timeout with real `api.createTask()` + `api.listTasks()` so quick notes are saved as tasks and survive reload.
- `IntelligenceScreen`: competitors and keywords persisted to localStorage (with backend `PATCH /api/company/:id` fallback); company name pulled from backend instead of hardcoded "Acme Store".
- `SkillsScreen`: added Recommended and Registry tabs backed by live `/api/skills/recommend/auto` and `/api/skills` endpoints; catalogue toggles persisted to localStorage; hardcoded preview warning replaced with live tech-stack detection banner.
- `frontend/src/api.js`: added `listSkills`, `refreshSkills`, `recommendSkills`, `autoRecommendSkills`, `getSkill`, `listMcpServers`, `createMcpServer`, `updateMcpServer`, `deleteMcpServer`, `updateCompany`.

