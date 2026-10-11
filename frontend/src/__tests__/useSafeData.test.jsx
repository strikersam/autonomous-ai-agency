/**
 * useSafeData is behind every hub screen, so it decides how fast a tap feels:
 * a slow endpoint must not hold back the rest of the page, and opening a
 * screen again must show its last data at once instead of a blank spinner.
 */
import { renderHook, waitFor, act } from '@testing-library/react';
import { API } from '../api';
import { useSafeData, clearSafeDataCache } from '../v5/hooks/useSafeData';

vi.mock('../api', () => ({ API: { get: vi.fn() } }));

const later = () => { let resolve; const p = new Promise(r => { resolve = r; }); return [p, resolve]; };

beforeEach(() => { clearSafeDataCache(); API.get.mockReset(); });

test('each slot renders as soon as its own request returns', async () => {
  const [slow, finishSlow] = later();
  API.get.mockImplementation(url => (url === '/slow' ? slow : Promise.resolve({ data: { n: 1 } })));
  const { result } = renderHook(() => useSafeData(null, { fast: '/fast', slow: '/slow' }));
  await waitFor(() => expect(result.current[0].fast).toEqual({ n: 1 }));
  expect(result.current[1].fast.loading).toBe(false);
  expect(result.current[1].slow.loading).toBe(true);
  await act(async () => { finishSlow({ data: { n: 2 } }); });
  expect(result.current[0].slow).toEqual({ n: 2 });
});

test('opening a screen again shows the cached data at once, then refreshes it', async () => {
  API.get.mockResolvedValue({ data: { v: 'first' } });
  const first = renderHook(() => useSafeData(null, { a: '/a' }));
  await waitFor(() => expect(first.result.current[0].a).toEqual({ v: 'first' }));
  first.unmount();

  const [pending, finish] = later();
  API.get.mockReturnValue(pending);
  const again = renderHook(() => useSafeData(null, { a: '/a' }));
  expect(again.result.current[0].a).toEqual({ v: 'first' });
  expect(again.result.current[1].a.loading).toBe(false);
  await act(async () => { finish({ data: { v: 'second' } }); });
  expect(again.result.current[0].a).toEqual({ v: 'second' });
});

test('a failed request still blanks its slot and reports the error', async () => {
  API.get.mockRejectedValue({ response: { status: 500, statusText: 'Server Error' } });
  const { result } = renderHook(() => useSafeData(null, { a: '/a' }));
  await waitFor(() => expect(result.current[1].a.error).toBe('500 Server Error'));
  expect(result.current[0].a).toBeNull();
});

test('signing out clears the cache so the next account never sees it', async () => {
  API.get.mockResolvedValue({ data: { secret: 1 } });
  const first = renderHook(() => useSafeData(null, { a: '/a' }));
  await waitFor(() => expect(first.result.current[0].a).toEqual({ secret: 1 }));
  first.unmount();
  clearSafeDataCache();
  API.get.mockReturnValue(new Promise(() => {}));
  const next = renderHook(() => useSafeData(null, { a: '/a' }));
  expect(next.result.current[0].a).toBeNull();
  expect(next.result.current[1].a.loading).toBe(true);
});

test('transforms apply to cached data too', async () => {
  API.get.mockResolvedValue({ data: [1, 2, 3] });
  const opts = { transform: { a: d => d.length } };
  const first = renderHook(() => useSafeData(null, { a: '/a' }, opts));
  await waitFor(() => expect(first.result.current[0].a).toBe(3));
  first.unmount();
  API.get.mockReturnValue(new Promise(() => {}));
  const again = renderHook(() => useSafeData(null, { a: '/a' }, opts));
  expect(again.result.current[0].a).toBe(3);
});
