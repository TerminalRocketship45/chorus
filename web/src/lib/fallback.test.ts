import { describe, expect, it } from "vitest";
import { fallbackNotice } from "../pages/PassagePicker";
import type { Passage } from "../types/api";

const base: Passage = { id: "cac-01", title: "t", band: "elementary", level: 1, topic: "x", word_count: 40, text: "x", source: "library" };

describe("fallbackNotice", () => {
  it("is silent when the AI wrote the passage", () => {
    expect(fallbackNotice({ ...base, fallback_reason: null })).toBeNull();
    expect(fallbackNotice(base)).toBeNull();
  });
  it("asks for a different topic only when the topic was rejected", () => {
    expect(fallbackNotice({ ...base, fallback_reason: "topic_rejected" })).toBe("Let's pick a different topic. Here's one from the library.");
    for (const r of ["no_token", "model_declined", "model_unavailable", "invalid_output"] as const) {
      expect(fallbackNotice({ ...base, fallback_reason: r })).toBe("Couldn't write a new passage right now. Here's one from the library.");
    }
  });
});
