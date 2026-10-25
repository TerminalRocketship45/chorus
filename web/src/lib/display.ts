import type { WordDisplay } from "../types/api";

/**
 * Maps the backend's `display` field to how a word renders. This is the
 * ONLY place that decides word colour/marker, so docs/api.md's rules are
 * enforced in one spot:
 *   - `correct` and `accent_ok` render IDENTICALLY (never reveal accent_ok).
 *   - `extra_nearby` renders as correct (never as a misread) plus a caret marker.
 *   - `repeated` / `self_corrected` render as correct plus a light positive mark.
 *   - `misread` and `skipped` are the only two error classes.
 *   - `not_reached` (the reader stopped before it) is plain muted text: never an error.
 */
export type WordVisualClass = "correct" | "misread" | "skipped" | "unreached";
export type WordMarker = "none" | "extra" | "repeated" | "fixed";

export interface WordVisual {
  className: WordVisualClass;
  marker: WordMarker;
  /** Screen-reader / tooltip text for the marker, or null when there isn't one. */
  markerLabel: string | null;
  /** Whether a genuine answer ("You said: X") may be shown for this word. */
  showsHeard: boolean;
}

const VISUALS: Record<WordDisplay, WordVisual> = {
  correct: { className: "correct", marker: "none", markerLabel: null, showsHeard: false },
  accent_ok: { className: "correct", marker: "none", markerLabel: null, showsHeard: false },
  misread: { className: "misread", marker: "none", markerLabel: null, showsHeard: true },
  skipped: { className: "skipped", marker: "none", markerLabel: null, showsHeard: false },
  not_reached: { className: "unreached", marker: "none", markerLabel: null, showsHeard: false },
  extra_nearby: {
    className: "correct",
    marker: "extra",
    markerLabel: "an extra word was added nearby",
    showsHeard: false,
  },
  repeated: {
    className: "correct",
    marker: "repeated",
    markerLabel: "repeated",
    showsHeard: false,
  },
  self_corrected: {
    className: "correct",
    marker: "fixed",
    markerLabel: "fixed it",
    showsHeard: false,
  },
};

export function visualForDisplay(display: WordDisplay): WordVisual {
  return VISUALS[display];
}

/** True when the reader stopped early and some words were never reached. */
export function hasUnreached(words: Array<{ display: WordDisplay }>): boolean {
  return words.some((w) => w.display === "not_reached");
}

export const WORD_LEGEND: Array<{ className: WordVisualClass; marker: WordMarker; label: string }> = [
  { className: "correct", marker: "none", label: "Correct" },
  { className: "correct", marker: "extra", label: "Extra word added nearby" },
  { className: "correct", marker: "repeated", label: "Repeated" },
  { className: "correct", marker: "fixed", label: "Fixed it" },
  { className: "misread", marker: "none", label: "Tricky word" },
  { className: "skipped", marker: "none", label: "Skipped" },
];

export const UNREACHED_LEGEND = { className: "unreached", marker: "none", label: "Not reached (you stopped before it)" } as const;

/** True when the response carries original passage text (newer analyses). */
export function hasSurface(words: readonly { surface?: string }[]): boolean {
  return words.some((w) => !!w.surface);
}

/**
 * The text to draw for a word: its original passage text when present, else the normalized
 * `expected` (old saved sessions). A word with an empty surface inside a surface-bearing
 * reading is a continuation of the previous word ("one" of "21") and draws as nothing.
 */
export function wordText(word: { expected: string; surface?: string }, surfaced: boolean): string {
  if (word.surface) return word.surface;
  return surfaced ? "" : word.expected;
}
