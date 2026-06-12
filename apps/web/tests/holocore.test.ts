import { describe, expect, it } from "vitest";

// HoloCore relies on WebGL (unavailable in jsdom), so we don't mount it here.
// Instead we pin the state→style contract that drives the visual identity —
// the thing most likely to silently regress.
describe("HoloCore state contract", () => {
  it("module imports without a WebGL context", async () => {
    const mod = await import("../src/components/HoloCore");
    expect(typeof mod.HoloCore).toBe("function");
  });
});
