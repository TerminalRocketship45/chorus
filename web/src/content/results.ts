/**
 * Measured accent-filter results, in ONE place so they can be updated after
 * the pending GPU re-evaluation without hunting through the app.
 *
 * Source: SETUP.md "Current measured result" / eval/results.json
 * (base.en, seed 0, Mandarin, 500 utterances from the speechocean762 test
 * split, 3,219 words, 0 utterances skipped). Do not restate these numbers
 * anywhere else in the app — import them from here.
 */
export const MEASURED_RESULT = {
  corpusName: "speechocean762",
  corpusUtterances: 500,
  corpusWords: 3219,
  asrModel: "base.en",
  device: "CPU",
  language: "Mandarin",

  /** False error flags on expert-correct words that the filter withdrew. */
  falseFlagsWithdrawn: 14,
  falseFlagsBaseline: 645,
  falseFlagsWithdrawnPct: 2.2,
  falseFlagsWithdrawnCiLowPct: 1.1,
  falseFlagsWithdrawnCiHighPct: 3.4,

  /** Expert-mispronounced words still flagged after filtering. */
  genuineErrorsRetained: 233,
  genuineErrorsTotal: 239,
  genuineErrorsRetainedPct: 97.5,
  genuineErrorsRetainedCiLowPct: 95.4,
  genuineErrorsRetainedCiHighPct: 99.2,

  /** Of the 645 baseline false flags, the breakdown by raw status. */
  falseFlagsByStatus: {
    substitution: 520,
    omission: 48,
    insertion: 77,
  },

  bootstrapResamples: 1000,
} as const;

export const MEASURED_RESULT_HEADLINE =
  "On 500 Mandarin-L1 recordings from the speechocean762 corpus, the accent " +
  "filter withdrew 2.2% of false error flags (14 of 645, 95% CI 1.1%–3.4%) " +
  "while keeping 97.5% of genuine errors flagged (233 of 239, 95% CI " +
  "95.4%–99.2%).";

export const MEASURED_RESULT_WHY_SMALL =
  "The effect is small because the speech recognizer, not the accent rules, " +
  "sets the ceiling: most of what it over-flags is not accent-shaped at all " +
  "(a word the recognizer mangled, dropped, or added), so there is only a " +
  "small slice of error that an accent filter can touch in the first place.";

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
      "500 non-native English utterances used to measure the accent filter, " +
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
