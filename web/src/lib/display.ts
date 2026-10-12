import type { WordDisplay } from "../types/api";

/**
 * Maps the backend's `display` field to how a word renders. This is the
 * ONLY place that decides word colour/marker, so docs/api.md's rules are
 * enforced in one spot:
 *   - `correct` and `accent_ok` render IDENTICALLY (never reveal accent_ok).
 *   - `extra_nearby` renders as correct (never as a misread) plus a caret marker.
 *   - `repeated` / `self_corrected` render as correct plus a light positive mark.
 *   - `misread` and `skipped` are the only two "not plain correct" classes.
 */
export type WordVisualClass = "correct" | "misread" | "skipped";
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

export const WORD_LEGEND: Array<{ className: WordVisualClass; marker: WordMarker; label: string }> = [
  { className: "correct", marker: "none", label: "Correct" },
  { className: "correct", marker: "extra", label: "Extra word added nearby" },
  { className: "correct", marker: "repeated", label: "Repeated" },
  { className: "correct", marker: "fixed", label: "Fixed it" },
  { className: "misread", marker: "none", label: "Tricky word" },
  { className: "skipped", marker: "none", label: "Skipped" },
];
