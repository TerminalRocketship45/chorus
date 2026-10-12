import { describe, expect, it } from "vitest";
import { supportNote } from "./languageSupport";

describe("supportNote", () => {
  it("states the rules-not-measured note for Somali, matching the design spec wording", () => {
    expect(supportNote("Somali", "rules")).toBe(
      "Chorus uses published research about Somali pronunciation. This hasn't been tested on recordings of Somali speakers yet."
    );
  });

  it("states the measured note for Mandarin", () => {
    expect(supportNote("Mandarin Chinese", "measured")).toBe(
      "Tested against expert ratings of Mandarin Chinese speakers."
    );
  });

  it("states the not_yet note, naming the language", () => {
    expect(supportNote("Hmong", "not_yet")).toBe(
      "Chorus doesn't have Hmong sound rules yet, so your reading is scored without accent adjustment."
    );
  });

  it("has no note for not_needed", () => {
    expect(supportNote("English only", "not_needed")).toBeNull();
  });
});
