/**
 * Types mirroring docs/api.md EXACTLY. Keep this file in sync with that
 * document; it is the HTTP contract and this app must not drift from it.
 */

export type GradeBand = "elementary" | "secondary";

/** How well-supported a home language's accent rules are. See docs/api.md. */
export type LanguageSupport = "measured" | "rules" | "not_yet" | "not_needed";

export interface LanguageOption {
  code: string;
  label: string;
  support: LanguageSupport;
}

export interface Passage {
  id: string;
  title: string;
  band: GradeBand;
  level: 1 | 2 | 3;
  topic: string;
  word_count: number;
  text: string;
  /** "ai" passages have ids like g-12; the UI never labels them differently. */
  source: PassageSource;
}

export type PassageSource = "library" | "ai";

export interface Interest {
  code: string;
  label: string;
}

export interface Student {
  id: number;
  name: string;
  grade_band: GradeBand;
  home_language: string;
  interests: string[];
  created_at: string;
}

export interface StudentListItem extends Student {
  session_count: number;
  last_session_at: string | null;
  last_wcpm: number | null;
}

/** Raw Running Record status per src/chorus/types.py. Clients never colour by this. */
export type WordStatus =
  | "correct"
  | "substitution"
  | "omission"
  | "insertion"
  | "repetition"
  | "self_correction"
  | "hesitation";

/**
 * Display status. Every client renders words by THIS field, never by
 * `status`. See docs/api.md "Display status" table.
 *
 * INSERTION caveat: `extra_nearby` can sit on a word that was read correctly
 * (heard === expected) — it means "an extra word was added nearby", not that
 * this word was misread. Never colour it as an error.
 */
export type WordDisplay =
  | "correct"
  | "accent_ok"
  | "misread"
  | "skipped"
  | "extra_nearby"
  | "repeated"
  | "self_corrected";

export interface WordResult {
  index: number;
  expected: string;
  heard: string | null;
  status: WordStatus;
  accent_excused: boolean;
  display: WordDisplay;
  start: number | null;
  end: number | null;
}

export interface ReadingScore {
  /** Fraction 0-1, NOT a percentage. */
  accuracy: number;
  wcpm: number;
  total_words: number;
  correct_words: number;
  duration_s: number;
  long_pauses: number;
}

export interface AnalyzeResponse {
  session_id: number | null;
  passage_id: string;
  home_language: string | null;
  accent_filter_applied: boolean;
  words: WordResult[];
  score: ReadingScore;
  /** null when no accent rules apply. */
  accent_adjusted: ReadingScore | null;
  practice_words: string[];
}

export interface SessionSummary {
  id: number;
  passage_id: string;
  passage_title: string;
  created_at: string;
  score: ReadingScore;
  accent_adjusted: ReadingScore | null;
  accent_ok_count: number;
  practice_words: string[];
}

export interface MostMissedWord {
  word: string;
  count: number;
}

export interface StudentDetailResponse {
  student: Student;
  /** Oldest first (for the trend line). */
  sessions: SessionSummary[];
  most_missed: MostMissedWord[];
}

export interface ApiErrorBody {
  detail: string;
}

/** Body for POST /api/passages/generate (docs/api.md). */
export interface GeneratePassageRequest {
  band: GradeBand;
  interests: string[];
  student_id: number | null;
  exclude_ids: string[];
}

export interface PassageLastResult {
  accuracy: number;
  accent_adjusted_accuracy: number | null;
  wcpm: number;
  at: string;
}

/** One row of GET /api/students/{id}/passages. */
export interface PassageProgress {
  passage: Passage;
  read: boolean;
  attempts: number;
  last_result: PassageLastResult | null;
}
