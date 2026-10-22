import { beforeEach, describe, expect, it } from "vitest";
import type { Passage } from "../types/api";
import { normalizeTopic, MAX_TOPIC_LENGTH } from "./topic";

const store = new Map<string, string>();
(globalThis as unknown as { window: unknown }).window = {
  localStorage: {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  },
};
const { loadTopic, saveTopic, loadGenerated, saveGenerated, rememberGenerated } = await import("./generated");
const { clearReader } = await import("./storage");

const p = (id: string): Passage => ({
  id, title: id, band: "elementary", level: 1, topic: "sharks", word_count: 40, text: "x", source: "ai",
});

beforeEach(() => store.clear());

describe("topic persistence", () => {
  it("remembers the last topic and is empty by default", () => {
    expect(loadTopic()).toBe("");
    saveTopic("machine learning");
    expect(loadTopic()).toBe("machine learning");
  });
  it("clears with the reader", () => {
    saveTopic("sharks");
    saveGenerated(rememberGenerated({ passage: null, recent: [] }, p("g-1")));
    clearReader();
    expect(loadTopic()).toBe("");
    expect(loadGenerated().passage).toBeNull();
  });
  it("normalizes whitespace and caps length", () => {
    expect(normalizeTopic("  big   sharks ")).toBe("big sharks");
    expect(normalizeTopic("a".repeat(200))).toHaveLength(MAX_TOPIC_LENGTH);
  });
});

describe("generated passage persistence", () => {
  it("survives a reload and keeps recent ids newest first without duplicates", () => {
    let v = rememberGenerated({ passage: null, recent: [] }, p("g-1"));
    v = rememberGenerated(v, p("g-2"));
    v = rememberGenerated(v, p("g-1"));
    saveGenerated(v);
    const back = loadGenerated();
    expect(back.passage?.id).toBe("g-1");
    expect(back.recent).toEqual(["g-1", "g-2"]);
  });
  it("tolerates corrupt storage", () => {
    store.set("chorus:generated", "{nope");
    expect(loadGenerated()).toEqual({ passage: null, recent: [] });
  });
});
