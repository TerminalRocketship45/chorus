import { memo } from "react";
import type { WordResult } from "../types/api";
import { visualForDisplay, type WordMarker } from "../lib/display";
import { Icon } from "./Icon";

/** Small drawn marks beside a word. Never the only cue: each also has an aria label. */
export function MarkerIcon({ marker }: { marker: Exclude<WordMarker, "none"> }) {
  const name = marker === "extra" ? "caretUp" : marker === "repeated" ? "arrowClockwise" : "check";
  return (
    <span className={`word__marker word__marker--${marker}`} aria-hidden="true">
      <Icon name={name} size={12} strokeWidth={3} />
    </span>
  );
}

interface WordTokenProps {
  word: WordResult;
  selected: boolean;
  /** The word being spoken in the replay. Layered over the display colouring. */
  current?: boolean;
  onSelect: (word: WordResult) => void;
}

export const WordToken = memo(function WordToken({ word, selected, current = false, onSelect }: WordTokenProps) {
  const visual = visualForDisplay(word.display);
  const classes = ["word", `word--${visual.className}`, current ? "word--current" : ""].filter(Boolean).join(" ");

  let ariaLabel = word.expected;
  if (visual.className === "misread") ariaLabel = `${word.expected}, tricky word`;
  if (visual.className === "skipped") ariaLabel = `${word.expected}, skipped`;
  if (visual.markerLabel) ariaLabel = `${word.expected}, ${visual.markerLabel}`;

  return (
    <button
      type="button"
      className={classes}
      aria-label={ariaLabel}
      aria-pressed={selected}
      data-word-index={word.index}
      onClick={() => onSelect(word)}
    >
      <span>{word.expected}</span>
      {visual.marker !== "none" && <MarkerIcon marker={visual.marker} />}
    </button>
  );
});