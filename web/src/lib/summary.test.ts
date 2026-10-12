import { describe, expect, it } from "vitest";
import { buildParentSummary } from "./summary";
import type { SessionSummary } from "../types/api";

function session(wcpm: number): SessionSummary {
  return {
    id: 1,
    passage_id: "el-01",
    passage_title: "Test Passage",
    created_at: "2026-10-01T00:00:00Z",
    score: { accuracy: 0.8, wcpm, total_words: 10, correct_words: 8, duration_s: 10, long_pauses: 0 },
    accent_adjusted: null,
    accent_ok_count: 0,
    practice_words: [],
  };
}

describe("buildParentSummary", () => {
  it("handles no sessions", () => {
    expect(buildParentSummary("Amina", [])).toBe("Amina hasn't read a passage yet.");
  });

  it("handles exactly one session", () => {
    expect(buildParentSummary("Amina", [session(52)])).toBe(
      "Amina read 1 passage. Amina's words-correct-per-minute was 52."
    );
  });

  it("reports first-to-last WCPM across several sessions, oldest first", () => {
    const summary = buildParentSummary("Amina", [session(52), session(55), session(61)]);
    expect(summary).toBe("Amina read 3 passages. Amina's words-correct-per-minute went from 52 to 61.");
  });
});
