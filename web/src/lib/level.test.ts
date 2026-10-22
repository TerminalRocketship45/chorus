import { describe, expect, it } from "vitest";
import { levelFromTimeDomain, shouldShowQuietHint } from "./level";

describe("mic level", () => {
  it("is zero for silence and positive for signal", () => {
    expect(levelFromTimeDomain(new Uint8Array(64).fill(128))).toBe(0);
    expect(levelFromTimeDomain(Uint8Array.from({ length: 64 }, (_, i) => (i % 2 ? 200 : 56)))).toBeGreaterThan(0.5);
    expect(levelFromTimeDomain([])).toBe(0);
  });
  it("hints only after the grace period and only if still quiet", () => {
    expect(shouldShowQuietHint(2, 0)).toBe(false);
    expect(shouldShowQuietHint(3.2, 0.001)).toBe(true);
    expect(shouldShowQuietHint(5, 0.2)).toBe(false);
  });
});
