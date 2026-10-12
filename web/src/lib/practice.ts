/**
 * De-duplicates a word list, keeping first-seen order and ignoring case.
 * The backend already de-duplicates `practice_words` in passage order (see
 * docs/api.md), but this is used defensively anywhere a client builds its
 * own practice-style list (e.g. combining `most_missed` across sessions).
 */
export function dedupeWords(words: string[]): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const word of words) {
    const key = word.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(word);
  }
  return result;
}
