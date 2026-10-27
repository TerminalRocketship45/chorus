/** The app's name, in one place. */
export const APP_NAME = "Chorus";

export const APP_TAGLINE = "Hears your reading, not your accent.";

export const MAX_RECORDING_SECONDS = 120;
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10 MB, matches the 413 limit in docs/api.md

/** AI passage generation (topic step, "Generated for you", New passage). Off: library passages only. */
export const ENABLE_GENERATION = false;
