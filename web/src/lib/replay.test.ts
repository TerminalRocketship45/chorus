import { describe, expect, it } from "vitest";
import type { WordResult } from "../types/api";
import { findCurrentWord, HOLD_SECONDS } from "./replay";

const w = (index: number, start: number | null, end: number | null): WordResult => ({
  index,
  expected: `w${index}`,
  heard: null,
  status: "correct",
  accent_excused: false,
  display: "correct",
  start,
  end,
});

const words = [w(0, 0.1, 0.4), w(1, 0.5, 0.8), w(2, null, null), w(3, 1.0, 1.3), w(4, 3.0, 3.2)];

describe("findCurrentWord", () => {
  it("is null before the first word", () => {
    expect(findCurrentWord(words, 0.05)).toBeNull();
  });
  it("finds the word whose span contains t (start inclusive, end exclusive)", () => {
    expect(findCurrentWord(words, 0.1)).toBe(0);
    expect(findCurrentWord(words, 0.6)).toBe(1);
  });
  it("holds the previous word through a short gap", () => {
    expect(findCurrentWord(words, 0.45)).toBe(0);
    expect(findCurrentWord(words, 0.99)).toBe(1);
    expect(findCurrentWord([w(0, 0.1, 0.4)], 0.4 + HOLD_SECONDS - 0.01)).toBe(0);
  });
  it("skips untimed words", () => {
    expect(findCurrentWord(words, 0.95)).toBe(1);
    expect(findCurrentWord(words, 1.1)).toBe(3);
  });
  it("is null in a long gap and after the last word", () => {
    expect(findCurrentWord(words, 2.0)).toBeNull();
    expect(findCurrentWord(words, 3.2 + HOLD_SECONDS + 0.1)).toBeNull();
    expect(findCurrentWord(words, 3.1)).toBe(4);
  });
  it("handles no timed words", () => {
    expect(findCurrentWord([w(0, null, null)], 1)).toBeNull();
    expect(findCurrentWord([], 1)).toBeNull();
  });
});
