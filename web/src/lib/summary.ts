import type { SessionSummary } from "../types/api";

/**
 * Builds the plain-language summary sentence shown at the top of a
 * student's teacher/parent view, e.g. "Amina read 4 passages. Amina's
 * words-correct-per-minute went from 52 to 61." Sessions must be oldest
 * first, as docs/api.md guarantees for GET /api/students/{id}.
 */
export function buildParentSummary(name: string, sessions: SessionSummary[]): string {
  const count = sessions.length;
  if (count === 0) {
    return `${name} hasn't read a passage yet.`;
  }
  const passageWord = count === 1 ? "passage" : "passages";
  const readSentence = `${name} read ${count} ${passageWord}.`;

  if (count === 1) {
    const wcpm = Math.round(sessions[0].score.wcpm);
    return `${readSentence} ${name}'s words-correct-per-minute was ${wcpm}.`;
  }

  const first = Math.round(sessions[0].score.wcpm);
  const last = Math.round(sessions[count - 1].score.wcpm);
  return `${readSentence} ${name}'s words-correct-per-minute went from ${first} to ${last}.`;
}
