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
