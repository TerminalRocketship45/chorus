import type { AnalyzeResponse, Passage, PassageLastResult, PassageProgress } from "../types/api";

/**
 * Read/score marks for readers without a nickname (no student id), kept in
 * localStorage by lib/storage.ts. These helpers are pure so they can be tested
 * without a browser.
 */
export type LocalHistory = Record<string, { attempts: number; last_result: PassageLastResult }>;

export const MAX_LOCAL_PASSAGES = 30;

export function recordLocalResult(
  history: LocalHistory,
  passageId: string,
  analysis: Pick<AnalyzeResponse, "score" | "accent_adjusted">,
  now: Date = new Date()
): LocalHistory {
  const previous = history[passageId];
  return {
    ...history,
    [passageId]: {
      attempts: (previous?.attempts ?? 0) + 1,
      last_result: {
        accuracy: analysis.score.accuracy,
        accent_adjusted_accuracy: analysis.accent_adjusted ? analysis.accent_adjusted.accuracy : null,
        wcpm: analysis.score.wcpm,
        at: now.toISOString(),
      },
    },
  };
}

export function progressForPassage(passage: Passage, history: LocalHistory): PassageProgress {
  const entry = history[passage.id];
  return entry
    ? { passage, read: true, attempts: entry.attempts, last_result: entry.last_result }
    : { passage, read: false, attempts: 0, last_result: null };
}

/** Every passage id already shown to the reader, de-duplicated, in first-seen order. */
export function collectExcludeIds(...lists: Array<Array<{ id: string }>>): string[] {
  const seen = new Set<string>();
  const ids: string[] = [];
  for (const list of lists) {
    for (const item of list) {
      if (!seen.has(item.id)) {
        seen.add(item.id);
        ids.push(item.id);
      }
    }
  }
  return ids;
}

/** Puts a freshly written passage at the top; a repeated id moves to the top instead of doubling. */
export function prependPassage(rows: PassageProgress[], passage: Passage): PassageProgress[] {
  const existing = rows.find((row) => row.passage.id === passage.id);
  const entry: PassageProgress = existing ?? { passage, read: false, attempts: 0, last_result: null };
  return [entry, ...rows.filter((row) => row.passage.id !== passage.id)];
}

/** Newest first, no duplicates, capped so localStorage stays small. */
export function rememberLocalPassage(list: Passage[], passage: Passage): Passage[] {
  return [passage, ...list.filter((p) => p.id !== passage.id)].slice(0, MAX_LOCAL_PASSAGES);
}

/**
 * Splits what the reader sees into "your passages" (written for them or already read)
 * and the rest of the library, with no passage listed twice.
 */
export function buildSections(
  personal: PassageProgress[],
  library: Passage[],
  history: LocalHistory | null
): { mine: PassageProgress[]; library: PassageProgress[] } {
  const mineIds = new Set(personal.map((row) => row.passage.id));
  return {
    mine: personal,
    library: library
      .filter((p) => !mineIds.has(p.id))
      .map((p) => (history ? progressForPassage(p, history) : { passage: p, read: false, attempts: 0, last_result: null })),
  };
}
