/**
 * HubTabs: ARIA tablist with arrow keys, and no scrollIntoView on mount —
 * Chrome moves its Tab starting point to a scrolled-into-view element, which
 * made the first Tab after a deep link skip the "Skip to content" link.
 */
import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import HubTabs from '../v5/components/ui/HubTabs';

const TABS = [{ id: 'a', label: 'Alpha' }, { id: 'b', label: 'Beta' }, { id: 'c', label: 'Gamma' }];

function Harness({ start = 'a' }) {
  const [tab, setTab] = React.useState(start);
  return <HubTabs tabs={TABS} active={tab} onChange={setTab} />;
}

test('mounting on a deep-linked tab never calls scrollIntoView', () => {
  const spy = vi.fn();
  const orig = Element.prototype.scrollIntoView;
  Element.prototype.scrollIntoView = spy;
  try {
    render(<Harness start="c" />);
    expect(spy).not.toHaveBeenCalled();
  } finally {
    Element.prototype.scrollIntoView = orig;
  }
});

test('arrow keys move selection and focus; only the active tab is tabbable', () => {
  render(<Harness />);
  const alpha = screen.getByRole('tab', { name: 'Alpha' });
  expect(alpha).toHaveAttribute('aria-selected', 'true');
  expect(screen.getByRole('tab', { name: 'Beta' })).toHaveAttribute('tabindex', '-1');
  fireEvent.keyDown(alpha, { key: 'ArrowRight' });
  const beta = screen.getByRole('tab', { name: 'Beta' });
  expect(beta).toHaveAttribute('aria-selected', 'true');
  expect(document.activeElement).toBe(beta);
  fireEvent.keyDown(beta, { key: 'End' });
  expect(screen.getByRole('tab', { name: 'Gamma' })).toHaveAttribute('aria-selected', 'true');
  fireEvent.keyDown(screen.getByRole('tab', { name: 'Gamma' }), { key: 'ArrowRight' });
  expect(screen.getByRole('tab', { name: 'Alpha' })).toHaveAttribute('aria-selected', 'true');
});
