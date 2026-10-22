import { beforeEach, describe, expect, it } from "vitest";
import { CONFETTI_COUNT, claimFirstView, confettiAllowed, makeConfettiPieces, resetFirstViewMemory } from "./confetti";

describe("confetti", () => {
  beforeEach(() => resetFirstViewMemory());

  it("is skipped entirely under reduced motion", () => {
    expect(confettiAllowed(true)).toBe(false);
    expect(confettiAllowed(false)).toBe(true);
  });

  it("makes a small burst starting above the top, using three palette slots", () => {
    const pieces = makeConfettiPieces(CONFETTI_COUNT, 390);
    expect(pieces.length).toBeGreaterThanOrEqual(30);
    expect(pieces.length).toBeLessThanOrEqual(40);
    expect(pieces.every((p) => p.y < 0 && p.x >= 0 && p.x <= 390)).toBe(true);
    expect(new Set(pieces.map((p) => p.colour))).toEqual(new Set([0, 1, 2]));
  });

  it("plays only the first time a history entry is viewed", () => {
    const store = new Map<string, string>();
    const storage = { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v) };
    expect(claimFirstView("abc", storage)).toBe(true);
    expect(claimFirstView("abc", storage)).toBe(false);
    resetFirstViewMemory(); // a reload keeps sessionStorage
    expect(claimFirstView("abc", storage)).toBe(false);
    expect(claimFirstView("def", storage)).toBe(true);
  });

  it("still guards a page load when storage throws", () => {
    const broken = {
      getItem: () => {
        throw new Error("blocked");
      },
      setItem: () => {
        throw new Error("blocked");
      },
    };
    expect(claimFirstView("x", broken)).toBe(true);
    expect(claimFirstView("x", broken)).toBe(false);
  });
});
