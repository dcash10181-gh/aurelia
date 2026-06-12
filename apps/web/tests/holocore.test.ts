import { describe, expect, it } from "vitest";

// HoloCore relies on WebGL (unavailable in jsdom), so we don't mount it here.
// Instead we pin the state→style contract that drives the visual identity —
// the thing most likely to silently regress.
import { HoloCompositeShader, HoloCore, STATE_STYLE } from "../src/components/HoloCore";

describe("HoloCore state contract", () => {
  it("module imports without a WebGL context", () => {
    expect(typeof HoloCore).toBe("function");
  });

  it("every state defines the full visual channel set, bloom included", () => {
    for (const s of ["idle", "thinking", "tool", "error"] as const) {
      const st = STATE_STYLE[s];
      for (const ch of ["core", "glow", "spin", "pulse", "bloom"] as const) {
        expect(typeof st[ch], `${s}.${ch}`).toBe("number");
        expect(Number.isFinite(st[ch]), `${s}.${ch} finite`).toBe(true);
      }
    }
  });

  it("bloom encodes urgency: error flares hardest, idle rests lowest", () => {
    // The glow IS the state readout — if these invert, the UI lies.
    expect(STATE_STYLE.error.bloom).toBeGreaterThan(STATE_STYLE.thinking.bloom);
    expect(STATE_STYLE.thinking.bloom).toBeGreaterThan(STATE_STYLE.idle.bloom);
    expect(STATE_STYLE.idle.bloom).toBeGreaterThan(0);
  });

  it("composite shader derives alpha from luminance (transparent-canvas contract)", () => {
    // If alpha stops tracking brightness, bloom turns the canvas into an
    // opaque black slab and erases the CSS backdrop behind it.
    expect(HoloCompositeShader.fragmentShader).toContain("gl_FragColor = vec4(col, a)");
    expect(HoloCompositeShader.uniforms.uChroma.value).toBeGreaterThan(0);
    expect(HoloCompositeShader.uniforms.uChroma.value).toBeLessThan(0.05); // subtle, not broken-monitor
  });
});
