/**
 * knowledgeGraphTab.test.js
 *
 * Verifies the Knowledge screen's "graph" tab visualizes the per-user,
 * per-company CompanyGraph (backend/company_api.py's GET /api/company and
 * GET /api/company/{id}/graph, both scoped server-side by get_company_access)
 * rather than a global/unscoped view, and that no new graph-drawing
 * dependency was introduced for it.
 *
 * Source-inspection test (same pattern as test_company_stale_id_recovery.test.js)
 * rather than full component rendering, matching this repo's existing convention
 * for these screens.
 */
const { describe, test, expect } = require('@jest/globals');

const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(
  path.join(__dirname, '..', 'v5', 'screens', 'KnowledgeScreen.jsx'),
  'utf-8'
);

describe('Knowledge screen — Company Graph tab', () => {
  test('adds a "graph" tab alongside the existing activity/docs/sources tabs', () => {
    expect(src).toMatch(/\['activity','docs','sources','graph'\]/);
    expect(src).toMatch(/tab === 'graph' && <CompanyGraphPanel\/>/);
  });

  test('loads companies and the graph through the per-user-scoped API, not a global endpoint', () => {
    expect(src).toMatch(/api\.listCompanies\(\)/);
    expect(src).toMatch(/api\.getCompanyGraph\(selectedCompanyId\)/);
  });

  test('persists the selected company via the same COMPANY_ID_KEY the Company screen uses', () => {
    expect(src).toMatch(/import \{ COMPANY_ID_KEY \} from '\.\/CompanyScreen'/);
    expect(src).toMatch(/localStorage\.setItem\(COMPANY_ID_KEY, selectedCompanyId\)/);
  });

  test('does not add a new graph-rendering dependency (plain SVG only)', () => {
    expect(src).not.toMatch(/reactflow|react-flow|cytoscape|vis-network|force-graph|d3-force/i);
    expect(src).toMatch(/<svg /);
  });
});

describe('Knowledge screen — Company Graph tab stale-ID recovery (regression)', () => {
  // Bug: a company deleted or a DB reset since COMPANY_ID_KEY was last persisted
  // caused a permanent "Couldn't load the company graph: Company <id> not found"
  // in CompanyGraphPanel, because unlike CompanyScreen.jsx (PR #962) it trusted
  // the stored ID without validating it against the live company list or
  // self-healing on a 404 from GET /api/company/{id}/graph.
  test('validates the persisted COMPANY_ID_KEY against the live company list on mount', () => {
    expect(src).toMatch(/list\.find\(c => c\.id === storedId\)/);
    expect(src).toMatch(/localStorage\.removeItem\(COMPANY_ID_KEY\)/);
  });

  test('self-heals on a 404 from getCompanyGraph instead of leaving a permanent error', () => {
    expect(src).toMatch(/e\?\.response\?\.status === 404/);
  });

  // CodeRabbit review on #1110: checking only list[0] against the failed ID
  // wrongly cleared the selection whenever list[0] itself was the 404'd
  // company, even if a perfectly good second company existed in the list.
  test('404 recovery picks the first company that differs from the failed ID, not just list[0]', () => {
    expect(src).toMatch(/list\.find\(c => c\.id !== selectedCompanyId\)/);
    expect(src).not.toMatch(/list\[0\]\.id !== selectedCompanyId/);
  });

  // Codex review on #1110: if listCompanies() itself fails while recovering
  // from a 404 (network/500/auth expiry), the empty catch swallowed that
  // error and silently cleared the graph with no explanation to the user.
  test('surfaces an error when the re-list during 404 recovery itself fails, instead of silently clearing state', () => {
    expect(src).toMatch(/catch \(listErr\) \{/);
    expect(src).toMatch(/could not be refreshed/);
  });

  // Codex review on #1110: the mount-time list-validation effect and the
  // graph-fetch effect both run concurrently on mount when a stale ID is
  // stored, so a slow 404 recovery could clobber a selection the validation
  // effect had already corrected. Guarded with a per-invocation cancel flag.
  test('cancels a stale 404-recovery invocation instead of letting it clobber a corrected selection', () => {
    expect(src).toMatch(/let cancelled = false;/);
    expect(src).toMatch(/return \(\) => \{ cancelled = true; \};/);
    expect(src).toMatch(/if \(!mounted\.current \|\| cancelled\) return;/);
  });
});

describe('Knowledge screen — CompanyGraph element builder', () => {
  test('buildGraphElements maps every CompanyGraph entity list to a node', () => {
    expect(src).toMatch(/website: graph\.websites \|\| \[\]/);
    expect(src).toMatch(/repo: graph\.repos \|\| \[\]/);
    expect(src).toMatch(/system: graph\.systems \|\| \[\]/);
    expect(src).toMatch(/specialist: graph\.specialists \|\| \[\]/);
    expect(src).toMatch(/workflow: graph\.workflows \|\| \[\]/);
    expect(src).toMatch(/knowledge: graph\.knowledge \|\| \[\]/);
    expect(src).toMatch(/connector: graph\.connectors \|\| \[\]/);
  });

  test('specialists edge to their specialized_systems, not a fabricated relationship', () => {
    expect(src).toMatch(/sp\.specialized_systems \|\| \[\]/);
  });
});
