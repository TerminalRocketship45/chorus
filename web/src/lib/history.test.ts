import { describe, expect, it } from "vitest";
import type { Passage, PassageProgress } from "../types/api";
import {
  buildSections,
  collectExcludeIds,
  MAX_LOCAL_PASSAGES,
  prependPassage,
  progressForPassage,
  recordLocalResult,
  rememberLocalPassage,
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

describe("list helpers", () => {
  it("prepends a new passage and moves a repeat to the top without doubling it", () => {
    const base = prependPassage(prependPassage([], p("g-1")), p("g-2"));
    expect(base.map((r) => r.passage.id)).toEqual(["g-2", "g-1"]);
    expect(prependPassage(base, p("g-1")).map((r) => r.passage.id)).toEqual(["g-1", "g-2"]);
  });

  it("caps remembered local passages", () => {
    let list: Passage[] = [];
    for (let i = 0; i < MAX_LOCAL_PASSAGES + 5; i++) list = rememberLocalPassage(list, p(`g-${i}`));
    expect(list).toHaveLength(MAX_LOCAL_PASSAGES);
    expect(list[0].id).toBe(`g-${MAX_LOCAL_PASSAGES + 4}`);
  });

  it("keeps library passages out of the library section when already in the personal list", () => {
    const personal = [{ passage: p("el-01"), read: true, attempts: 1, last_result: null }];
    const sections = buildSections(personal, [p("el-01"), p("el-02")], null);
    expect(sections.library.map((r) => r.passage.id)).toEqual(["el-02"]);
  });
});
