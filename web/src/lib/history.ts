import type { AnalyzeResponse, Passage, PassageLastResult, PassageProgress } from "../types/api";

/**
 * Read/score marks for readers without a nickname (no student id), kept in
 * localStorage by lib/storage.ts. These helpers are pure so they can be tested
 * without a browser.
 */
export type LocalHistory = Record<string, { attempts: number; last_result: PassageLastResult }>;

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

/**
 * Progress for one passage: the server's row for a student (matched by id),
 * otherwise the local history (readers without a nickname).
 */
export function progressFor(
  passage: Passage,
  rows: PassageProgress[],
  history: LocalHistory | null
): PassageProgress {
  const row = rows.find((r) => r.passage.id === passage.id);
  if (row) return { ...row, passage };
  return history ? progressForPassage(passage, history) : { passage, read: false, attempts: 0, last_result: null };
}

/** The library list with a read mark and last score per passage; `hideId` drops the current generated passage. */
export function libraryRows(
  library: Passage[],
  rows: PassageProgress[],
  history: LocalHistory | null,
  hideId: string | null
): PassageProgress[] {
  return library.filter((p) => p.id !== hideId).map((p) => progressFor(p, rows, history));
}
