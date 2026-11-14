import '@testing-library/jest-dom/vitest';
import { afterEach, vi } from 'vitest';
import { cleanup } from '@testing-library/react';

// Recharts (ResponsiveContainer) necesita ResizeObserver, que jsdom no implementa.
class ResizeObserverFalso {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as unknown as { ResizeObserver: unknown }).ResizeObserver = ResizeObserverFalso;

// jsdom no tiene layout: Recharts avisa que el contenedor mide 0 px. Es esperado en pruebas.
const avisoOriginal = console.warn;
console.warn = (...args: unknown[]) => {
  if (typeof args[0] === 'string' && args[0].includes('of chart should be greater than 0')) return;
  avisoOriginal(...args);
};

afterEach(() => {
  cleanup();
  sessionStorage.clear();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});
