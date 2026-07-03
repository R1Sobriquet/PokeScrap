import "@testing-library/jest-dom";

// jsdom n'implémente pas ResizeObserver (requis par recharts ResponsiveContainer).
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
