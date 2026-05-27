# Agency Core v5: Transformation Progress

**Status:** 🚀 ACTIVE DEVELOPMENT  
**Branch:** `agency-core-v5-hardening`  
**Coordinator:** Sam (CompanyHelm)  
**Last Updated:** 2026-05-25

---

## 🎯 MISSION

Transform `local-llm-server` from a **multi-agent orchestration layer** into a **true autonomous agency platform** where:

1. Companies provide **minimal inputs** (website URL, repos, docs, connectors)
2. Platform **scans websites**, **infers stack**, **detects systems**
3. **Auto-provisions specialists** based on detected systems
4. **Direct Chat** becomes the **company control center**
5. **Company Graph** drives **all context-aware operations**
6. **Operator burden decreases over time**

---

## ✅ ACCOMPLISHED (Commits: c228ba9, 75b62a6)

### 🏗 Foundation
- [x] **Created working branch**: `agency-core-v5-hardening`
- [x] **Fixed `/api/doctor` 401 issue**: Added `get_optional_user()` dependency
- [x] **Enhanced CORS**: Added explicit GitHub Pages origins
- [x] **Created models directory**: `models/__init__.py`
- [x] **Created services directory**: `services/__init__.py`

### 📊 Company Graph Core
- [x] **Company Graph Pydantic Models** (63KB, 2104 lines):
  - **Core Entities**: Company, Website, Repo, BusinessSystem, Specialist, Workflow
  - **Supporting Models**: StackInference, Evidence, Connector, KnowledgeItem, ApprovalPolicy
  - **Composite Models**: CompanyGraph, CompanyGraphSnapshot
  - **Request/Response Models**: All API DTOs
  - **Scan Models**: WebsiteScanRequest/Result, RepoScanRequest, OnboardingProgress
  - **Provisioning Models**: SpecialistProvisionRequest/Result, WorkflowExecutionRequest/Result
- [x] **Storage Strategy**: MongoDB + SQLite schemas with CompanyGraphStore
- [x] **Golden Path Architecture**: Mermaid diagrams for all flows
- [x] **Integration Patterns**: Code examples for Direct Chat, Specialist Router, etc.

### 🆕 API Endpoints (backend/company_api.py)
- [x] **Company CRUD**:
  - `GET /api/company` - List companies
  - `POST /api/company` - Create company
  - `GET /api/company/{company_id}` - Get company
  - `PUT /api/company/{company_id}` - Update company
  - `DELETE /api/company/{company_id}` - Delete company
- [x] **Company Graph**:
  - `GET /api/company/{company_id}/graph` - Get company graph
- [x] **Website Scanning**:
  - `POST /api/company/{company_id}/scan/website` - Scan website
- [x] **Specialist Management**:
  - `GET /api/company/{company_id}/specialists` - List specialists
  - `POST /api/company/{company_id}/specialists` - Provision specialist
- [x] **Onboarding**:
  - `GET /api/company/{company_id}/onboarding` - Get onboarding progress
  - `POST /api/company/{company_id}/onboarding/start` - Start onboarding
- [x] **Public Doctor**:
  - `GET /api/company/doctor/public` - Public health checks

---

## 🚀 IN PROGRESS

### 📌 Current Focus: Backend Implementation

#### Services Layer (P0)
- [ ] `services/company_graph_store.py` - Storage implementation (MongoDB + SQLite)
- [ ] `services/company_graph.py` - Company Graph business logic
- [ ] `services/scanner.py` - Website and repo scanning
- [ ] `services/specialist.py` - Specialist provisioning and management
- [ ] `services/onboarding.py` - Onboarding flow orchestration

#### API Implementation (P0)
- [ ] Replace mock data with real implementations in `backend/company_api.py`
- [ ] Add authentication and authorization checks
- [ ] Add error handling and validation
- [ ] Add rate limiting and caching

#### Backend Integration (P0)
- [ ] Integrate Company Graph with `direct_chat.py`
- [ ] Integrate Company Graph with `agent/agency.py` (Specialist Router)
- [ ] Integrate stack detection with `agent/doctor.py`
- [ ] Integrate with `workflow/engine.py`

---

## ⏳ PENDING

### 🎨 Frontend (P1)
- [ ] **Fix CompanyScreen**: Wire to `/api/company` endpoint
- [ ] **Fix OnboardingScreen**: Wire to `/api/onboarding` endpoints
- [ ] **Create Public Doctor Page**: Standalone page for GitHub Pages
- [ ] **Fix Navigation**: Public vs. auth route handling
- [ ] **Rewrite GitHub Pages Site**: Replace mock shell with real content

### 🛡 CI/DevOps (P1)
- [ ] **Add SQLite test matrix** to `ci.yml`
- [ ] **Add contract tests** for frontend ↔ backend APIs
- [ ] **Add doctor endpoint tests** (auth + unauth)
- [ ] **Add route existence tests**
- [ ] **Fix deterministic builds** (use `npm ci`)
- [ ] **Standardize frontend Dockerfiles**

### 🧪 Testing (P1)
- [ ] **Unit tests** for Company Graph models
- [ ] **Integration tests** for storage services
- [ ] **API tests** for all new endpoints
- [ ] **E2E tests** for onboarding flow
- [ ] **Load tests** for performance validation

### 📚 Documentation (P2)
- [ ] **Update README.md** with Company Graph section
- [ ] **Update AGENTS.md** with new agent types
- [ ] **Add architecture diagrams** to docs/
- [ ] **Add API documentation** (auto-generated)
- [ ] **Add deployment guide**

---

## 📊 AGENT CONTRIBUTIONS

### ✅ Product Owner Agent
**Deliverables:**
- Complete **sitemap** for public website (12 top-level sections, 50+ pages)
- **3 user journeys** (New User, Existing User, Public Explorer)
- **Page-by-page content outline**
- **Navigation structure** (header, footer, sidebar)
- **CTA strategy** (Primary, Secondary, Tertiary)

**Files:**
- `github-pages-index.html` (to be rewritten)
- Future: All GitHub Pages content

### ✅ Frontend Engineer Agent
**Deliverables:**
- **`/doctor` 401 issue confirmed**: Requires `get_current_user`
- **API contract analysis**: Shape matches, auth is the issue
- **Missing screens identified**: CompanyScreen/OnboardingScreen exist but use mock data
- **GitHub Pages state**: Mock shell, no real content
- **Prioritized fixes**: 5 critical items

**Files:**
- `frontend/src/v5/screens/DoctorScreen.jsx` (needs public/private split)
- `frontend/src/v5/screens/CompanyScreen.jsx` (needs API integration)
- `frontend/src/v5/screens/OnboardingScreen.jsx` (needs API integration)

### ✅ Principal Architect Agent
**Deliverables:**
- **Pydantic Models**: All Company Graph entities (saved to `models/company_graph.py`)
- **Golden Path Architecture**: 5 Mermaid diagrams
- **Integration Plan**: Code patterns for all components
- **Storage Strategy**: MongoDB + SQLite schemas + CompanyGraphStore
- **API Endpoints**: Complete specifications for all endpoints

**Files:**
- `models/company_graph.py` (✅ SAVED)
- Future: `services/company_graph_store.py`, `services/company_graph.py`, etc.

### ✅ DevOps Agent
**Deliverables:**
- **CI Audit**: MongoDB dependency, readiness checks, SQLite fallback needed
- **CORS Analysis**: Wildcard default, needs GitHub Pages explicit config
- **Docker Analysis**: Multiple frontend Dockerfiles, inconsistent configs
- **Deployment Strategy**: Split frontend/backend, fix CORS
- **Hardening Plan**: 5 prioritized fixes

**Fixes Applied:**
- ✅ Enhanced CORS with GitHub Pages origins
- ⏳ SQLite test matrix (pending)
- ⏳ Deterministic builds (pending)

### ⏳ Nvidia Engineer Agent
**Status:** AWAITING RESPONSE  
**Expected:** Contract drift report + workflow gaps

---

## 🎯 ROADMAP TO GREEN PR

### 📅 Week 1: Core Backend (P0)
**Goal:** Company Graph foundation + API endpoints working

| Day | Task | Status | Owner |
|-----|------|--------|-------|
| Day 1 | ✅ Fix `/doctor` 401 + CORS | **DONE** | Coordinator |
| Day 1 | ✅ Company Graph models | **DONE** | Coordinator |
| Day 1 | ✅ Company API endpoints (mock) | **DONE** | Coordinator |
| Day 2 | 🔄 CompanyGraphStore implementation | **IN PROGRESS** | Coordinator |
| Day 2 | 🔄 Company Graph services | **PENDING** | Coordinator |
| Day 3 | 🔄 Replace mocks with real implementations | **PENDING** | Coordinator |
| Day 3 | 🔄 Backend integration (Direct Chat, Specialist Router) | **PENDING** | Coordinator |
| Day 4 | 🔄 Unit tests for models | **PENDING** | Coordinator |
| Day 4 | 🔄 Integration tests for storage | **PENDING** | Coordinator |
| Day 5 | 🔄 API tests | **PENDING** | Coordinator |

### 📅 Week 2: Frontend + CI (P1)
**Goal:** Public site working + CI hardened

| Day | Task | Status | Owner |
|-----|------|--------|-------|
| Day 6 | ⏳ Wire CompanyScreen to API | **PENDING** | Coordinator |
| Day 6 | ⏳ Wire OnboardingScreen to API | **PENDING** | Coordinator |
| Day 7 | ⏳ Create Public Doctor Page | **PENDING** | Coordinator |
| Day 7 | ⏳ Fix navigation (public vs. auth) | **PENDING** | Coordinator |
| Day 8 | ⏳ Rewrite GitHub Pages site | **PENDING** | Coordinator |
| Day 8 | ⏳ Add SQLite test matrix to CI | **PENDING** | Coordinator |
| Day 9 | ⏳ Add contract tests | **PENDING** | Coordinator |
| Day 9 | ⏳ Fix deterministic builds | **PENDING** | Coordinator |

### 📅 Week 3: Polish + Deploy (P2)
**Goal:** Green PR + production ready

| Day | Task | Status | Owner |
|-----|------|--------|-------|
| Day 10 | ⏳ Standardize Dockerfiles | **PENDING** | Coordinator |
| Day 10 | ⏳ Add missing endpoint tests | **PENDING** | Coordinator |
| Day 11 | ⏳ Update README + docs | **PENDING** | Coordinator |
| Day 11 | ⏳ Update AGENTS.md | **PENDING** | Coordinator |
| Day 12 | ⏳ Final QA | **PENDING** | Coordinator |
| Day 12 | ⏳ Push to GitHub | **PENDING** | Coordinator |
| Day 13 | ⏳ Ensure CI passes (green) | **PENDING** | Coordinator |

---

## 📈 METRICS

### Code Changes
```
Commits: 2
Files Changed: 6
Lines Added: 2,685
Lines Deleted: 16
Net Change: +2,669 lines
```

### Coverage
- **Models**: 100% (All Company Graph entities defined)
- **API Endpoints**: 100% (All endpoints stubbed)
- **Services**: 0% (Not yet implemented)
- **Frontend Integration**: 0% (Not yet started)
- **Tests**: 0% (Not yet written)

### Completion
- **P0 (Blockers)**: 30% ✅✅✅⏳⏳⏳⏳
- **P1 (High Priority)**: 0% ⏳⏳⏳⏳⏳⏳⏳⏳
- **P2 (Medium Priority)**: 0% ⏳⏳⏳⏳⏳⏳⏳⏳

---

## 🚨 BLOCKERS

### Current Blockers
| Blocker | Impact | Status | Resolution |
|---------|--------|--------|------------|
| **No Nvidia Engineer response** | Contract drift unknown | ⚠️ WARNING | Awaiting agent response |
| **Services not implemented** | API endpoints return mocks | ⚠️ WARNING | In progress |
| **Frontend not wired** | Screens use mock data | ⚠️ WARNING | Pending |

### Resolved Blockers
| Blocker | Impact | Status | Resolution |
|---------|--------|--------|------------|
| `/api/doctor` 401 | Public site broken | ✅ FIXED | Added `get_optional_user()` |
| CORS for GitHub Pages | Frontend can't call backend | ✅ FIXED | Added explicit origins |
| Company Graph models | No typed core model | ✅ FIXED | Created `models/company_graph.py` |

---

## 💡 KEY DECISIONS

### 1. **`/doctor` Endpoint Split**
- **Problem**: `/api/doctor` required auth, breaking public site
- **Solution**: Added `get_optional_user()` dependency
- **Impact**: `/api/doctor` now works with OR without auth
- **Future**: Consider splitting into `/api/doctor/public` + `/api/doctor`

### 2. **CORS Configuration**
- **Problem**: GitHub Pages frontend can't call Render backend
- **Solution**: Added explicit GitHub Pages origins to CORS
- **Impact**: Frontend can now call backend API
- **Security**: More secure than wildcard `*`

### 3. **Company Graph as Canonical Model**
- **Decision**: Company Graph is the single source of truth
- **Impact**: All components (Direct Chat, Specialists, Workflows) use it
- **Benefit**: Consistent context across all operations

### 4. **Storage Backend Agnostic**
- **Decision**: Support both MongoDB (primary) and SQLite (fallback)
- **Impact**: Flexible deployment, easier testing
- **Benefit**: No external dependencies required

### 5. **Immutable Pydantic Models**
- **Decision**: All models use `frozen=True` and `extra="forbid"`
- **Impact**: Prevents accidental modifications and drift
- **Benefit**: Thread-safe, catches signature bugs early

---

## 🔥 IMMEDIATE NEXT STEPS (FOR COORDINATOR)

### 1. **Implement CompanyGraphStore**
```bash
# Create services/company_graph_store.py
# Implement MongoDB and SQLite backends
# Add CRUD operations for all entities
```

### 2. **Implement Company Graph Services**
```bash
# Create services/company_graph.py
# Create services/scanner.py
# Create services/specialist.py
# Create services/onboarding.py
```

### 3. **Replace Mocks with Real Implementations**
```bash
# Update backend/company_api.py
# Remove mock data, use real services
# Add error handling and validation
```

### 4. **Integrate with Existing Components**
```bash
# Update direct_chat.py to bind Company Graph
# Update agent/agency.py to use Specialist Router
# Update agent/doctor.py for stack detection
```

### 5. **Add Tests**
```bash
# Create tests/test_company_graph.py
# Create tests/test_company_api.py
# Add to existing test suite
```

---

## 📞 CONTACT

**Coordinator:** Sam (CompanyHelm)  
**Repository:** https://github.com/strikersam/local-llm-server  
**Branch:** agency-core-v5-hardening  
**Status:** ACTIVE DEVELOPMENT

---

## 🎉 SUCCESS CRITERIA

This transformation will be **successful** when:

1. ✅ **Public website is real** (not a mock shell)
2. ✅ **`/doctor` route works** (no 401 for public users)
3. ✅ **Company onboarding is first-class** (website URL → stack inference → specialists)
4. ✅ **Company Graph is central** (drives all context-aware operations)
5. ✅ **Specialists go beyond engineering** (QA, Docs, Analytics, Ecommerce, etc.)
6. ✅ **Direct Chat is control center** (sticky company context, intent routing)
7. ✅ **Contracts are hardened** (no drift between frontend ↔ backend)
8. ✅ **CI is green** (all tests pass, no flakiness)
9. ✅ **Operator burden decreases** (automation > manual work)
10. ✅ **Product is production-grade** (reliable, maintainable, scalable)

---

**🚀 LET'S FINISH THIS.**

The foundation is **solid**. The architecture is **clear**. The agents have **delivered**. Now it's time to **execute**.

**Next: Implement the services layer and replace mocks with real code.**
