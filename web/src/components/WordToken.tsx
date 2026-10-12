import type { WordResult } from "../types/api";
import { visualForDisplay } from "../lib/display";

const MARKER_GLYPH: Record<string, string> = {
  extra: "➕", // heavy plus sign
  repeated: "↻", // clockwise open circle arrow
  fixed: "✓", // check mark
};

interface WordTokenProps {
  word: WordResult;
  selected: boolean;
  onSelect: (word: WordResult) => void;
}

export function WordToken({ word, selected, onSelect }: WordTokenProps) {
  const visual = visualForDisplay(word.display);
  const classes = ["word", `word--${visual.className}`].join(" ");

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
      onClick={() => onSelect(word)}
    >
      <span>{word.expected}</span>
      {visual.marker !== "none" && (
        <span className={`word__marker word__marker--${visual.marker}`} aria-hidden="true">
          {MARKER_GLYPH[visual.marker]}
        </span>
      )}
    </button>
  );
}
