import { describe, expect, it } from "vitest";
import type { Passage, PassageProgress } from "../types/api";
import {
  libraryRows,
  collectExcludeIds,
  progressForPassage,
  recordLocalResult,
  progressFor,
} from "./history";

const p = (id: string): Passage => ({
  id,
  title: id,
  band: "elementary",
  level: 1,
  topic: "space",
  word_count: 40,
  text: "x",
  source: id.startsWith("g-") ? "ai" : "library",
});

const analysis = {
  score: { accuracy: 0.9, wcpm: 70, total_words: 10, correct_words: 9, duration_s: 8, long_pauses: 0 },
  accent_adjusted: { accuracy: 0.95, wcpm: 74, total_words: 10, correct_words: 9, duration_s: 8, long_pauses: 0 },
};

describe("collectExcludeIds", () => {
  it("merges lists, keeps first-seen order and drops duplicates", () => {
    const rows: PassageProgress[] = [{ passage: p("g-2"), read: false, attempts: 0, last_result: null }];
    const ids = collectExcludeIds(
      rows.map((r) => r.passage),
      [p("el-01"), p("g-2")],
      [p("g-1")]
    );
    expect(ids).toEqual(["g-2", "el-01", "g-1"]);
  });
  it("is empty for no passages", () => {
    expect(collectExcludeIds([], [])).toEqual([]);
  });
});

describe("local history", () => {
  it("records a result and counts attempts", () => {
    const now = new Date("2026-10-21T10:00:00Z");
    const first = recordLocalResult({}, "el-01", analysis, now);
    expect(first["el-01"].attempts).toBe(1);
    expect(first["el-01"].last_result).toEqual({
      accuracy: 0.9,
      accent_adjusted_accuracy: 0.95,
      wcpm: 70,
      at: "2026-10-21T10:00:00.000Z",
    });
    const second = recordLocalResult(first, "el-01", { ...analysis, accent_adjusted: null }, now);
    expect(second["el-01"].attempts).toBe(2);
    expect(second["el-01"].last_result.accent_adjusted_accuracy).toBeNull();
  });

  it("marks read and unread passages", () => {
    const history = recordLocalResult({}, "el-01", analysis);
    expect(progressForPassage(p("el-01"), history).read).toBe(true);
    expect(progressForPassage(p("el-02"), history)).toMatchObject({ read: false, last_result: null });
  });
});

describe("library rows", () => {
  it("marks library passages from server rows or local history and hides the generated one", () => {
    const rows: PassageProgress[] = [
      { passage: p("el-02"), read: true, attempts: 1, last_result: recordLocalResult({}, "el-02", analysis)["el-02"].last_result },
    ];
    const out = libraryRows([p("el-01"), p("el-02"), p("el-03")], rows, null, "el-03");
    expect(out.map((r) => [r.passage.id, r.read])).toEqual([["el-01", false], ["el-02", true]]);
    const local = libraryRows([p("el-01")], [], recordLocalResult({}, "el-01", analysis), null);
    expect(local[0].read).toBe(true);
  });
  it("progressFor prefers the server row", () => {
    const rows: PassageProgress[] = [{ passage: p("g-1"), read: true, attempts: 2, last_result: null }];
    expect(progressFor(p("g-1"), rows, {}).attempts).toBe(2);
  });
});
