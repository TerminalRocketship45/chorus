/**
 * Measured accent-filter results, in ONE place so they can be updated after
 * the pending GPU re-evaluation without hunting through the app.
 *
 * Source: the full speechocean762 test split (Whisper small.en, beam search 5,
 * same-sound and digit-context rules, silence filtering and volume normalisation),
 * Mandarin-L1 speakers only: 2,500 recordings,
 * 15,967 words.
 * Do not restate these numbers anywhere else in the app; import them from here.
 */
export const MEASURED_RESULT = {
  corpusName: "speechocean762",
  corpusUtterances: 2500,
  corpusWords: 15967,
  asrModel: "Whisper small.en",
  decoding: "beam search (width 5)",
  extraRules: "same-sound and digit-context rules, silence filtering and volume normalisation",
  split: "full test split",
  language: "Mandarin",

  /** Expert-correct words the recognizer wrongly flagged, before the accent filter. */
  expertCorrectWords: 14644,
  falseFlagsBaseline: 2308,
  falseFlagsBaselinePct: 15.8,
  /** Of those false flags, the ones the accent filter withdrew. */
  falseFlagsWithdrawn: 65,
  falseFlagsWithdrawnPct: 2.8,
  falseFlagsWithdrawnCiLowPct: 2.1,
  falseFlagsWithdrawnCiHighPct: 3.5,

  /** Expert-mispronounced words flagged before filtering, and how many stay flagged. */
  genuineErrorsRetained: 963,
  genuineErrorsTotal: 974,
  genuineErrorsRetainedPct: 98.9,
  genuineErrorsRetainedCiLowPct: 98.1,
  genuineErrorsRetainedCiHighPct: 99.5,
} as const;

export const MEASURED_RESULT_CONFIG =
  "Configuration: Whisper small.en speech recognition with beam search (width 5), plus " +
  "same-sound and digit-context rules, silence filtering and volume normalisation, run on the full speechocean762 test split: " +
  "2,500 recordings, 15,967 words, Mandarin-L1 speakers only.";

export const MEASURED_RESULT_HEADLINE =
  "The speech recognizer wrongly flagged 2,308 of 14,644 expert-correct words (15.8%). " +
  "The accent filter withdrew 65 of those false flags (2.8%, 95% CI 2.1%–3.5%) " +
  "while keeping 963 of 974 flagged genuine errors (98.9%, 95% CI 98.1%–99.5%).";

export const MEASURED_RESULT_WHY_SMALL =
  "The effect is small because the speech recognizer, not the accent rules, " +
  "sets the ceiling: most of what it over-flags is not accent-shaped at all " +
  "(a word the recognizer mangled, dropped, or added), so there is only a " +
  "small slice of error that an accent filter can touch in the first place.";

export const MEASURED_RESULT_REJECTED_IDEA =
  "We also tested showing the recognizer the passage text, and rejected it because it hid real reading mistakes.";

export const LANGUAGE_RULE_STATUS = {
  measured: "Mandarin is the only language checked against expert ratings, because the " +
    "only labelled corpus of non-native readers available is Mandarin-speaking.",
  rulesNotMeasured:
    "Somali and Spanish accent rules come from published linguistics research, " +
    "not from a measurement against recordings of real speakers.",
  notYet: "Hmong and Karen accent rules are not encoded yet.",
  notDiagnostic:
    "Chorus is not a diagnostic or clinical tool. It does not assess speech " +
    "disorders and is not a substitute for a teacher's own judgment.",
} as const;

export const CREDITS = [
  {
    name: "speechocean762",
    detail:
      "2,500 non-native English recordings used to measure the accent filter, " +
      "licensed CC BY 4.0 via OpenSLR.",
    url: "https://www.openslr.org/101/",
  },
  {
    name: "faster-whisper / OpenAI Whisper",
    detail: "Speech recognition (what Chorus hears you say).",
    url: "https://github.com/SYSTRAN/faster-whisper",
  },
  {
    name: "torchaudio MMS_FA",
    detail: "Forced alignment (lining up the audio with the expected words).",
    url: "https://pytorch.org/audio/stable/pipelines.html#mms-fa",
  },
] as const;

export const PIPELINE_STEPS = [
  {
    title: "Listening",
    text: "A speech recognizer (Whisper) writes down what it hears you say.",
  },
  {
    title: "Lining up the words",
    text:
      "A forced aligner lines up what you said against the passage's words, " +
      "and times each word in the recording.",
  },
  {
    title: "Finding differences",
    text:
      "Chorus compares what you said to the passage and labels each word: " +
      "read correctly, skipped, changed, or read with an extra word nearby.",
  },
  {
    title: "Checking for an accent match",
    text:
      "For a few languages, Chorus checks whether a changed word matches a " +
      "documented pattern of that language's accent in English. If it does, " +
      "the word is still shown as correct — only a teacher can see it was " +
      "an accent match, never a student.",
  },
  {
    title: "Scoring",
    text:
      "Chorus counts words read correctly per minute (WCPM) and accuracy, " +
      "both with and without the accent check.",
  },
] as const;
