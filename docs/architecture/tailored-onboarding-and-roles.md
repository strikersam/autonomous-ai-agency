# Tailored Onboarding, Editable Companies & Dynamic Roles

> **Status:** Design / phased build. Goal: onboarding is a *tailored, question-driven,
> editable* experience where every answer provisions something real, agents start
> pre-powered with the right skills + workflows, and roles expand to fit the company
> instead of being a fixed list.

---

## What already exists (don't rebuild)

| Capability | Where | State |
|------------|-------|-------|
| AI-tailored onboarding questions (per detected domain + stack) | `backend/company_api.py:1093` `generate_onboarding_questions` | ✅ live (LLM, 4 questions) |
| Company edit | `backend/company_api.py:452` `PATCH /api/company/{id}` | ✅ live (basic fields) |
| Specialist auto-skill-binding | `services/specialist.py:558` `_auto_bind_skills` | ✅ live (all 34 families bound) |
| Answers → remediation tasks | `backend/company_api.py:1317` | ⚠️ partial |
| Stack detection (1,270 signatures) | `services/scanner.py` | ✅ live |

## The gaps to close

1. **Editing is not first-class.** `PATCH` updates company fields but doesn't let the
   operator add/remove roles, re-answer onboarding questions, change cadences, or
   re-provision — and there's no re-tailoring after the first pass.
2. **Answers aren't all load-bearing.** Some answers only spawn remediation tasks;
   the brief is *every* question drives a concrete provisioning decision.
3. **Roles are a closed set.** `SpecialistFamily` is a 34-value `Literal`
   (`models/company_graph.py:47`); `_get_default_capabilities`/`_get_default_tools`
   are dicts keyed by it. You cannot create "delivery manager" or expand on demand.

---

## 1. Editable companies, anytime (not a one-shot wizard)

Onboarding and editing are **the same surface**, run repeatedly:

- `PATCH /api/company/{id}` extends to mutate **roles, skills, cadences, repo
  connections, approval policy, and stored onboarding answers** — not just name/domain.
- Editing an answer **re-runs the provisioning binding** for what that answer controls
  (idempotently: add what's newly needed, retire what's no longer, never duplicate).
- `POST /{id}/onboarding/questions` can be re-invoked any time to **re-tailor** as the
  company grows or the stack changes (re-scan → new questions → diff provisioning).
- Every edit is audited and reflected on the dashboard; specialists are
  added/disabled live (`Specialist.status`), never wiped.

## 2. Question-driven provisioning — no cosmetic questions

Each generated question carries a **typed provisioning binding** so the answer *does*
something. Extend the question schema:

```python
class OnboardingQuestion(BaseModel):
    id: str
    label: str
    type: str                  # single_select | multi_select | text | bool | scale
    options: list[str] = []
    provisions: ProvisioningBinding   # what this answer controls
```

```python
class ProvisioningBinding(BaseModel):
    target: Literal["roles", "skills", "workflows", "cadences",
                    "approval_policy", "repo", "integrations", "context"]
    # e.g. answer "we ship daily to prod" -> cadences:+deploy-health, approval_policy:strict
    #      answer "we have a mobile app"   -> roles:+mobile, skills bound, workflows enabled
    rules: list[dict]          # answer value -> concrete provisioning action
```

The onboarding question generator (already LLM-driven) is prompted to emit the
`provisions` binding alongside each question, and the apply step turns answers into:
roles to provision, skills/workflows to bind, cadences to schedule, approval strictness,
repo connection prompts, and context for the Company Graph. **An answer with no binding
is rejected at generation** — that enforces "every question is load-bearing."

## 3. Dynamic, expandable roles (open registry, not a closed enum)

Replace the closed `SpecialistFamily` `Literal` with a **Role Registry**:

- The current 34 families become the **built-in seed catalog** (with their existing
  default capabilities/tools/runtime/skill bindings — unchanged behaviour).
- Roles become an **open set**: a `RoleDefinition` can be created from onboarding need
  (or operator action) at runtime, with capabilities/tools/skills/runtime defaulted
  (AI-inferred from the role name + company stack) and then **editable**.
- Seed the catalog with the standard delivery org the brief lists, mapping/adding:
  `frontend, backend, fullstack, architecture(=architect), design(=designer), ux,
  qa, agile(=scrum master), portfolio(=portfolio manager), product, devops,
  data, ml, security` — **plus a new `delivery` (delivery manager)** role.
- Skill binding works for any role: built-ins use the static map; custom roles get
  skills via the existing recommender (`skill_bindings.recommend`/`list_for_family`)
  matched on capabilities + stack, so **a freshly-created role still starts powered**.

```python
@dataclass
class RoleDefinition:
    key: str                        # "delivery", "frontend", or a custom slug
    display_name: str
    builtin: bool                   # one of the 34 seeds, or operator/AI-created
    capabilities: list[str]
    tools: list[str]
    runtime: str | None
    bound_skills: list[str]         # resolved at provision time
    workflows: list[str]            # golden-path workflows this role drives
    enabled: bool = True
```

**Migration note (phased, non-trivial):** `SpecialistFamily` is referenced widely
(`get_args`, the capability/tool dicts, `system_to_family`, tests, the Specialist×Skill
matrix gate). Phase it: (a) introduce `RoleRegistry` seeded from today's 34 + their
default dicts, keep `SpecialistFamily` as a type alias over the seed keys for
back-compat; (b) route provisioning + the matrix generator through the registry;
(c) allow custom roles; (d) relax the `Literal` to `str` validated against the registry.

## 4. Agents start pre-powered

On provision (built-in or custom): bind skills (done), attach the role's **workflows**
(golden-path participation), set the runtime, and seed role context from the scan +
answers — so a specialist is immediately able to act, not an empty shell. The
Specialist×Skill matrix CI gate (already added) keeps every role skill-bound.

---

## Phases
- **P1 — Editable everything:** extend `PATCH` + a re-provision diff; edit roles,
  answers, cadences, connections post-onboarding; live add/disable specialists.
- **P2 — Load-bearing questions:** `ProvisioningBinding` on questions; reject cosmetic
  questions at generation; apply answers → roles/skills/workflows/cadences/policy.
- **P3 — Role Registry:** seed from the 34, add `delivery`, allow custom roles with
  AI-inferred + editable capabilities/skills; relax the closed `Literal` (back-compat alias).
- **P4 — Re-tailoring:** re-scan + regenerate questions on demand; diff and apply.

## Invariants
- Editing never wipes existing specialists/data — it diffs and reconciles.
- Every onboarding question maps to a concrete provisioning action (no cosmetic Qs).
- Any provisioned role (seed or custom) is skill-bound + workflow-attached (CI-gated).
- Custom roles are namespaced per company; the 34 seeds stay globally consistent.

---

## UI-first — an API is not "done"

**Every capability must be reachable and actionable from the dashboard UI**, not only
via REST. "The endpoint exists" does not count as shipped. Verified gaps (2026-06-10):

| Capability | API | JS client | UI surface | Gap |
|------------|-----|-----------|-----------|-----|
| Edit company | `PATCH /api/company/{id}` ✅ | `updateCompany` ✅ | `CompanyScreen` is **read-only** | **wire edit** |
| Provision/add specialist | `POST /api/company/{id}/specialists` ✅ | `provisionSpecialist` ✅ | none | **wire add/role UI** |
| Edit provider priority/key/model (#508) | `PUT /api/providers/{id}` ✅ | `updateProvider` ✅ | `ProvidersScreen` only creates + set-default | **in-place edit form** |
| Connect repo (GitHub/GitLab/Bitbucket) | (Phase 0) | — | none | **connect UI + per-conn token** |
| Connect intake (Jira; coming-soon others) | (planned) | — | none | **integrations screen w/ badges** |
| Edit onboarding answers / re-tailor | partial | — | one-shot wizard | **editable + re-run** |
| Roles add/edit (Role Registry) | (Phase 3) | — | none | **role management UI** |

**Requirement:** each backend capability above ships with a UI control in the relevant
v5 screen (`CompanyScreen`, `ProvidersScreen`, `AgentsScreen`, `OnboardingScreen`, a new
**Integrations** screen). Coming-soon integrations render as **disabled options with a
"Coming soon" badge** — visible, honest, not clickable.

**Anti-drift gate (extends `tests/test_docs_consistency.py`):** for the load-bearing
capabilities, assert that an API/client function is actually referenced by a screen
component — so "API-only, no UI" fails CI the same way feature/skill drift does.
