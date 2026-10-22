import type {
  AnalyzeResponse,
  LanguageOption,
  Passage,
  StudentDetailResponse,
  StudentListItem,
} from "../types/api";

/** Matches docs/api.md "GET /api/languages" exactly, including Somali-first order. */
export const MOCK_LANGUAGES: LanguageOption[] = [
  { code: "somali", label: "Somali", support: "rules" },
  { code: "spanish", label: "Spanish", support: "rules" },
  { code: "mandarin", label: "Mandarin Chinese", support: "measured" },
  { code: "hmong", label: "Hmong", support: "not_yet" },
  { code: "karen", label: "Karen", support: "not_yet" },
  { code: "english", label: "English only", support: "not_needed" },
  { code: "other", label: "Another language", support: "not_yet" },
];

export const MOCK_PASSAGES: Passage[] = [
  {
    id: "el-01",
    title: "The Quick Fox",
    band: "elementary",
    level: 1,
    topic: "animals",
    word_count: 11,
    text: "The quick brown fox jumps over the lazy dog again today.",
    source: "library",
  },
  {
    id: "el-02",
    title: "Rain on the Roof",
    band: "elementary",
    level: 2,
    topic: "weather",
    word_count: 8,
    text: "Rain fell softly on the old red roof.",
    source: "library",
  },
  {
    id: "se-01",
    title: "Renewable Energy",
    band: "secondary",
    level: 2,
    topic: "science",
    word_count: 16,
    text: "Wind turbines and solar panels now provide a growing share of the energy used in homes.",
    source: "library",
  },
  {
    id: "se-02",
    title: "The Long Walk Home",
    band: "secondary",
    level: 3,
    topic: "history",
    word_count: 15,
    text: "After the bridge washed out, the two friends walked twelve miles along the river at dusk.",
    source: "library",
  },
];

/**
 * The primary analyze fixture: exercises every WordDisplay value, including
 * `accent_ok` (quick -> accent-excused substitution), and carries a non-null
 * `accent_adjusted` score so raw-vs-adjusted UI has something to show.
 *
 * Passage: "The quick brown fox jumps over the lazy dog again today." (el-01)
 */
export const MOCK_ANALYZE_WITH_ACCENT: AnalyzeResponse = {
  session_id: 101,
  passage_id: "el-01",
  home_language: "somali",
  accent_filter_applied: true,
  words: [
    { index: 0, expected: "the", heard: "the", status: "correct", accent_excused: false, display: "correct", start: 0.1, end: 0.25 },
    { index: 1, expected: "quick", heard: "kwick", status: "substitution", accent_excused: true, display: "accent_ok", start: 0.3, end: 0.6 },
    { index: 2, expected: "brown", heard: "down", status: "substitution", accent_excused: false, display: "misread", start: 0.65, end: 0.95 },
    { index: 3, expected: "fox", heard: null, status: "omission", accent_excused: false, display: "skipped", start: null, end: null },
    { index: 4, expected: "jumps", heard: "jumps", status: "insertion", accent_excused: false, display: "extra_nearby", start: 1.0, end: 1.3 },
    { index: 5, expected: "over", heard: "over", status: "repetition", accent_excused: false, display: "repeated", start: 1.35, end: 1.6 },
    { index: 6, expected: "the", heard: "the", status: "self_correction", accent_excused: false, display: "self_corrected", start: 1.65, end: 1.8 },
    { index: 7, expected: "lazy", heard: "lazy", status: "correct", accent_excused: false, display: "correct", start: 1.85, end: 2.1 },
    { index: 8, expected: "dog", heard: "dog", status: "correct", accent_excused: false, display: "correct", start: 2.15, end: 2.35 },
    { index: 9, expected: "again", heard: "again", status: "correct", accent_excused: false, display: "correct", start: 2.4, end: 2.7 },
    { index: 10, expected: "today", heard: "today", status: "correct", accent_excused: false, display: "correct", start: 2.75, end: 3.05 },
  ],
  score: {
    accuracy: 0.636,
    wcpm: 45.7,
    total_words: 11,
    correct_words: 7,
    duration_s: 9.2,
    long_pauses: 1,
  },
  accent_adjusted: {
    accuracy: 0.727,
    wcpm: 52.2,
    total_words: 11,
    correct_words: 8,
    duration_s: 9.2,
    long_pauses: 1,
  },
  practice_words: ["brown", "fox"],
};

/**
 * Second analyze fixture: `home_language` not accent-adjusted (support
 * `not_needed`/English), so `accent_adjusted` is null and there is no
 * `accent_ok` word. Passage: "Rain fell softly on the old red roof." (el-02)
 */
export const MOCK_ANALYZE_NO_ACCENT: AnalyzeResponse = {
  session_id: 102,
  passage_id: "el-02",
  home_language: "english",
  accent_filter_applied: false,
  words: [
    { index: 0, expected: "rain", heard: "rain", status: "correct", accent_excused: false, display: "correct", start: 0.1, end: 0.35 },
    { index: 1, expected: "fell", heard: "field", status: "substitution", accent_excused: false, display: "misread", start: 0.4, end: 0.7 },
    { index: 2, expected: "softly", heard: null, status: "omission", accent_excused: false, display: "skipped", start: null, end: null },
    { index: 3, expected: "on", heard: "on", status: "insertion", accent_excused: false, display: "extra_nearby", start: 0.75, end: 0.9 },
    { index: 4, expected: "the", heard: "the", status: "repetition", accent_excused: false, display: "repeated", start: 0.95, end: 1.1 },
    { index: 5, expected: "old", heard: "old", status: "self_correction", accent_excused: false, display: "self_corrected", start: 1.15, end: 1.35 },
    { index: 6, expected: "red", heard: "red", status: "correct", accent_excused: false, display: "correct", start: 1.4, end: 1.6 },
    { index: 7, expected: "roof", heard: "roof", status: "correct", accent_excused: false, display: "correct", start: 1.65, end: 1.9 },
  ],
  score: {
    accuracy: 0.625,
    wcpm: 46.2,
    total_words: 8,
    correct_words: 5,
    duration_s: 6.5,
    long_pauses: 0,
  },
  accent_adjusted: null,
  practice_words: ["fell", "softly"],
};

export const MOCK_STUDENTS: StudentListItem[] = [
  {
    id: 1,
    name: "Amina",
    grade_band: "elementary",
    home_language: "somali",
    interests: ["animals", "space"],
    created_at: "2026-09-02T14:00:00Z",
    session_count: 4,
    last_session_at: "2026-10-09T15:32:00Z",
    last_wcpm: 61,
  },
  {
    id: 2,
    name: "Tou",
    grade_band: "elementary",
    home_language: "hmong",
    interests: ["music"],
    created_at: "2026-09-10T14:00:00Z",
    session_count: 1,
    last_session_at: "2026-09-18T16:05:00Z",
    last_wcpm: 40,
  },
  {
    id: 3,
    name: "Luis",
    grade_band: "secondary",
    home_language: "spanish",
    interests: ["sports", "science"],
    created_at: "2026-09-05T14:00:00Z",
    session_count: 2,
    last_session_at: "2026-10-05T13:20:00Z",
    last_wcpm: 95,
  },
];

export const MOCK_STUDENT_DETAILS: Record<number, StudentDetailResponse> = {
  1: {
    student: {
      id: 1,
      name: "Amina",
      grade_band: "elementary",
      home_language: "somali",
      interests: ["animals", "space"],
    created_at: "2026-09-02T14:00:00Z",
    },
    sessions: [
      {
        id: 10,
        passage_id: "el-01",
        passage_title: "The Quick Fox",
        created_at: "2026-09-04T15:00:00Z",
        score: { accuracy: 0.7, wcpm: 52, total_words: 11, correct_words: 8, duration_s: 12.7, long_pauses: 2 },
        accent_adjusted: { accuracy: 0.8, wcpm: 59, total_words: 11, correct_words: 9, duration_s: 12.7, long_pauses: 2 },
        accent_ok_count: 2,
        practice_words: ["through", "says"],
      },
      {
        id: 11,
        passage_id: "el-02",
        passage_title: "Rain on the Roof",
        created_at: "2026-09-16T15:10:00Z",
        score: { accuracy: 0.75, wcpm: 55, total_words: 8, correct_words: 6, duration_s: 8.7, long_pauses: 1 },
        accent_adjusted: { accuracy: 0.875, wcpm: 64, total_words: 8, correct_words: 7, duration_s: 8.7, long_pauses: 1 },
        accent_ok_count: 1,
        practice_words: ["through"],
      },
      {
        id: 12,
        passage_id: "el-01",
        passage_title: "The Quick Fox",
        created_at: "2026-09-29T15:20:00Z",
        score: { accuracy: 0.8, wcpm: 58, total_words: 11, correct_words: 9, duration_s: 11.4, long_pauses: 1 },
        accent_adjusted: { accuracy: 0.91, wcpm: 66, total_words: 11, correct_words: 10, duration_s: 11.4, long_pauses: 1 },
        accent_ok_count: 3,
        practice_words: ["says"],
      },
      {
        id: 13,
        passage_id: "el-02",
        passage_title: "Rain on the Roof",
        created_at: "2026-10-09T15:32:00Z",
        score: { accuracy: 0.85, wcpm: 61, total_words: 8, correct_words: 7, duration_s: 7.9, long_pauses: 0 },
        accent_adjusted: { accuracy: 1.0, wcpm: 72, total_words: 8, correct_words: 8, duration_s: 7.9, long_pauses: 0 },
        accent_ok_count: 2,
        practice_words: [],
      },
    ],
    most_missed: [
      { word: "through", count: 2 },
      { word: "says", count: 2 },
    ],
  },
  2: {
    student: {
      id: 2,
      name: "Tou",
      grade_band: "elementary",
      home_language: "hmong",
      interests: ["music"],
    created_at: "2026-09-10T14:00:00Z",
    },
    sessions: [
      {
        id: 20,
        passage_id: "el-02",
        passage_title: "Rain on the Roof",
        created_at: "2026-09-18T16:05:00Z",
        score: { accuracy: 0.63, wcpm: 40, total_words: 8, correct_words: 5, duration_s: 10.1, long_pauses: 3 },
        accent_adjusted: null,
        accent_ok_count: 0,
        practice_words: ["fell", "softly"],
      },
    ],
    most_missed: [
      { word: "fell", count: 1 },
      { word: "softly", count: 1 },
    ],
  },
  3: {
    student: {
      id: 3,
      name: "Luis",
      grade_band: "secondary",
      home_language: "spanish",
      interests: ["sports", "science"],
    created_at: "2026-09-05T14:00:00Z",
    },
    sessions: [
      {
        id: 30,
        passage_id: "se-01",
        passage_title: "Renewable Energy",
        created_at: "2026-09-20T13:00:00Z",
        score: { accuracy: 0.88, wcpm: 90, total_words: 16, correct_words: 14, duration_s: 11.3, long_pauses: 0 },
        accent_adjusted: { accuracy: 0.94, wcpm: 96, total_words: 16, correct_words: 15, duration_s: 11.3, long_pauses: 0 },
        accent_ok_count: 1,
        practice_words: ["share"],
      },
      {
        id: 31,
        passage_id: "se-02",
        passage_title: "The Long Walk Home",
        created_at: "2026-10-05T13:20:00Z",
        score: { accuracy: 0.93, wcpm: 95, total_words: 15, correct_words: 14, duration_s: 9.9, long_pauses: 0 },
        accent_adjusted: { accuracy: 1.0, wcpm: 102, total_words: 15, correct_words: 15, duration_s: 9.9, long_pauses: 0 },
        accent_ok_count: 1,
        practice_words: [],
      },
    ],
    most_missed: [{ word: "share", count: 1 }],
  },
};

/** Short stand-in texts for model-written passages; {t} is the typed topic. */
export const MOCK_TOPIC_TEXT = [
  "Today we will read about {t}. Many people find {t} interesting because there is always something new to learn. Some facts about {t} are easy to see, and others take careful study. If you look closely, you may notice small details that surprise you.",
  "Have you ever wondered about {t}? Long ago, people asked questions about {t} and wrote down what they found. Their notes help us today. Each new idea about {t} builds on the ones before it.",
];
