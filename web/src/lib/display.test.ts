import { describe, expect, it } from "vitest";
import { hasUnreached, visualForDisplay, WORD_LEGEND } from "./display";

describe("visualForDisplay", () => {
  it("renders accent_ok identically to correct (never reveal the accent excuse)", () => {
    const correct = visualForDisplay("correct");
    const accentOk = visualForDisplay("accent_ok");
    expect(accentOk.className).toBe(correct.className);
    expect(accentOk.marker).toBe(correct.marker);
    expect(accentOk.markerLabel).toBe(correct.markerLabel);
  });

  it("never classes extra_nearby as a misread, and marks it instead", () => {
    const visual = visualForDisplay("extra_nearby");
    expect(visual.className).toBe("correct");
    expect(visual.marker).toBe("extra");
    expect(visual.markerLabel).toMatch(/extra word/i);
  });

  it("marks misread words distinctly from skipped words", () => {
    const misread = visualForDisplay("misread");
    const skipped = visualForDisplay("skipped");
    expect(misread.className).toBe("misread");
    expect(misread.showsHeard).toBe(true);
    expect(skipped.className).toBe("skipped");
    expect(skipped.showsHeard).toBe(false);
    expect(misread.className).not.toBe(skipped.className);
  });

  it("shows repeated and self_corrected as correct with a positive, non-error marker", () => {
    const repeated = visualForDisplay("repeated");
    const fixed = visualForDisplay("self_corrected");
    expect(repeated.className).toBe("correct");
    expect(repeated.marker).toBe("repeated");
    expect(fixed.className).toBe("correct");
    expect(fixed.marker).toBe("fixed");
  });

  it("never shows 'heard' text for correct, accent_ok, skipped, or extra_nearby", () => {
    for (const display of ["correct", "accent_ok", "skipped", "extra_nearby", "repeated", "self_corrected"] as const) {
      expect(visualForDisplay(display).showsHeard).toBe(false);
    }
  });

  it("renders not_reached as plain muted text, never an error, with no marker or heard text", () => {
    const v = visualForDisplay("not_reached");
    expect(v.className).toBe("unreached");
    expect(v.marker).toBe("none");
    expect(v.markerLabel).toBeNull();
    expect(v.showsHeard).toBe(false);
    expect(WORD_LEGEND.some((i) => i.className === "unreached")).toBe(false);
  });

  it("detects whether any word was not reached", () => {
    expect(hasUnreached([{ display: "correct" }, { display: "not_reached" }])).toBe(true);
    expect(hasUnreached([{ display: "correct" }, { display: "skipped" }])).toBe(false);
  });
});
