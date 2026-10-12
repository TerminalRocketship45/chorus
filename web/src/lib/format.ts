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
