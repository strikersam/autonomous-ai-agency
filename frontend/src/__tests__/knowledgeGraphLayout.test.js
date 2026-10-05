/**
 * Company graph layout — every node must land inside the SVG canvas.
 * Regression: ring radius was 90 + i*65, so a company using 5+ categories
 * (website/repo/system/specialist/workflow/knowledge/connector) put the outer
 * rings past the 300px canvas radius and the browser clipped them.
 */
import { buildGraphElements, GRAPH_SIZE } from '../v5/screens/KnowledgeScreen';

const items = (prefix, n) => Array.from({ length: n }, (_, i) => ({ id: `${prefix}${i}`, name: `${prefix} ${i}` }));

const fullGraph = (n = 3) => ({
  company: { name: 'Acme' },
  websites: items('w', n), repos: items('r', n), systems: items('s', n),
  specialists: items('sp', n), workflows: items('wf', n), knowledge: items('k', n), connectors: items('c', n),
});

const inBounds = (nodes) => nodes.filter(n => n.type !== 'company').every(n => {
  const x = GRAPH_SIZE / 2 + n.radius * Math.cos(n.angle);
  const y = GRAPH_SIZE / 2 + n.radius * Math.sin(n.angle);
  return x >= 0 && x <= GRAPH_SIZE && y >= 0 && y <= GRAPH_SIZE;
});

test('all seven categories fit inside the canvas', () => {
  const { nodes } = buildGraphElements(fullGraph());
  expect(nodes.length).toBe(1 + 7 * 3);
  expect(inBounds(nodes)).toBe(true);
});

test('a large ring stays inside the canvas', () => {
  const { nodes } = buildGraphElements(fullGraph(40));
  expect(inBounds(nodes)).toBe(true);
});

test('a sparse graph keeps rings distinct and in order', () => {
  const { nodes } = buildGraphElements({ company: { name: 'A' }, systems: items('s', 2), specialists: items('sp', 2) });
  const r = type => nodes.find(n => n.type === type).radius;
  expect(r('specialist')).toBeGreaterThan(r('system'));
});
