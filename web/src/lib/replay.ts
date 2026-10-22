import type { WordResult } from "../types/api";

/** How long the highlight stays on a word after it ends, bridging the small gap to the next word. */
export const HOLD_SECONDS = 0.5;

/**
 * Which word is being spoken at `t` seconds into the recording, or null.
 * Words without both start and end are skipped. In a gap between two words the
 * previous word stays highlighted for up to HOLD_SECONDS, so the highlight does
 * not flicker; before the first word and after the last (plus hold) there is none.
 * Returns the word's `index` field.
 */
export function findCurrentWord(words: WordResult[], t: number): number | null {
  let best: WordResult | null = null;
  for (const w of words) {
    if (w.start == null || w.end == null || w.end < w.start) continue;
    if (w.start <= t) best = w;
    else break;
  }
  if (!best || best.end == null) return null;
  return t < best.end + HOLD_SECONDS ? best.index : null;
}

export function hasTiming(word: WordResult): boolean {
  return word.start != null && word.end != null;
}
