/** Formats a 0-1 accuracy fraction (per docs/api.md) as a whole-number percentage string. */
export function formatAccuracyPct(accuracy: number): string {
  return `${Math.round(accuracy * 100)}%`;
}

/** Formats words-correct-per-minute as a whole number. */
export function formatWcpm(wcpm: number): string {
  return `${Math.round(wcpm)}`;
}

/** Formats seconds (e.g. recording elapsed time) as m:ss. */
export function formatElapsed(totalSeconds: number): string {
  const safe = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(safe / 60);
  const seconds = safe % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

/** "Sharks · 62 words" subtitle for the generated passage. */
export function formatTopicMeta(topic: string, wordCount: number): string {
  return `${topic.charAt(0).toUpperCase() + topic.slice(1)} · ${wordCount} words`;
}

/** "Space · Level 2 · 62 words" style subtitle for a passage row. */
export function formatPassageMeta(topic: string, level: number, wordCount: number): string {
  const label = topic.charAt(0).toUpperCase() + topic.slice(1);
  return `${label} · Level ${level} · ${wordCount} words`;
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return "—";
  }
}

export function gradeBandLabel(band: "elementary" | "secondary"): string {
  return band === "elementary" ? "Grades 2–5" : "Grades 6–12";
}

/** Home-language codes are lowercase API codes ("somali"); show them as words. */
export function formatHomeLanguage(code: string): string {
  return code.charAt(0).toUpperCase() + code.slice(1);
}

/**
 * "You read 24 of 128 words" when the reader stopped early, else null.
 * Old saved sessions lack the fields; they count as a full read.
 */
export function formatWordsReached(score: { words_reached?: number; passage_words?: number }): string | null {
  const { words_reached: reached, passage_words: total } = score;
  if (reached === undefined || total === undefined || reached >= total) return null;
  return `You read ${reached} of ${total} words`;
}
