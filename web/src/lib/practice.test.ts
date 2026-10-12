import { describe, expect, it } from "vitest";
import { dedupeWords } from "./practice";

describe("dedupeWords", () => {
  it("keeps first-seen order and drops case-insensitive repeats", () => {
    expect(dedupeWords(["through", "says", "Through", "says"])).toEqual(["through", "says"]);
  });

  it("returns an empty list unchanged", () => {
    expect(dedupeWords([])).toEqual([]);
  });
});
