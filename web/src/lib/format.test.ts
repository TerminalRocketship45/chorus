import { describe, expect, it } from "vitest";
import { formatAccuracyPct, formatElapsed, formatWcpm } from "./format";

describe("formatAccuracyPct", () => {
  it("converts a 0-1 fraction to a rounded whole-number percentage", () => {
    expect(formatAccuracyPct(0.636)).toBe("64%");
    expect(formatAccuracyPct(1)).toBe("100%");
    expect(formatAccuracyPct(0)).toBe("0%");
  });
});

describe("formatWcpm", () => {
  it("rounds to a whole number", () => {
    expect(formatWcpm(45.7)).toBe("46");
  });
});

describe("formatElapsed", () => {
  it("formats seconds as m:ss", () => {
    expect(formatElapsed(0)).toBe("0:00");
    expect(formatElapsed(65)).toBe("1:05");
    expect(formatElapsed(120)).toBe("2:00");
  });
});
