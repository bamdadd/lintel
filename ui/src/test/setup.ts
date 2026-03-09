import '@testing-library/jest-dom/vitest';

Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserverMock;

// EventSource is not available in jsdom — provide a no-op stub so components
// that open SSE connections during tests don't throw ReferenceError.
class EventSourceStub {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSED = 2;

  readonly CONNECTING = 0;
  readonly OPEN = 1;
  readonly CLOSED = 2;

  readyState = EventSourceStub.CONNECTING;
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: ((event: Event) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;

  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  constructor(_url: string, _init?: EventSourceInit) {}

  close() {
    this.readyState = EventSourceStub.CLOSED;
  }

  addEventListener() {}
  removeEventListener() {}
  dispatchEvent() { return false; }
}

// @ts-expect-error — intentional global stub for test environment
globalThis.EventSource = EventSourceStub;
