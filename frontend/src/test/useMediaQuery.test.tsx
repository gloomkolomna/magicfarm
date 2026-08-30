import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useMediaQuery } from '../utils/useMediaQuery';

type Listener = (e: { matches: boolean }) => void;

function mockMatchMedia(initial: boolean) {
  let matches = initial;
  const listeners = new Set<Listener>();
  const mql = {
    get matches() { return matches; },
    addEventListener: (_: string, cb: Listener) => listeners.add(cb),
    removeEventListener: (_: string, cb: Listener) => listeners.delete(cb),
  };
  vi.stubGlobal('matchMedia', vi.fn(() => mql));
  return {
    setMatches(v: boolean) {
      matches = v;
      listeners.forEach((cb) => cb({ matches: v }));
    },
  };
}

describe('useMediaQuery', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', vi.fn(() => { throw new Error('matchMedia not mocked'); }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('возвращает начальное значение запроса', () => {
    mockMatchMedia(true);
    const { result } = renderHook(() => useMediaQuery('(max-width: 768px)'));
    expect(result.current).toBe(true);
  });

  it('реагирует на изменение media query', () => {
    const ctrl = mockMatchMedia(false);
    const { result } = renderHook(() => useMediaQuery('(max-width: 768px)'));
    expect(result.current).toBe(false);
    act(() => ctrl.setMatches(true));
    expect(result.current).toBe(true);
    act(() => ctrl.setMatches(false));
    expect(result.current).toBe(false);
  });

  it('отписывается при размонтировании', () => {
    const ctrl = mockMatchMedia(false);
    const { result, unmount } = renderHook(() => useMediaQuery('(max-width: 768px)'));
    unmount();
    act(() => ctrl.setMatches(true));
    expect(result.current).toBe(false);
  });
});
