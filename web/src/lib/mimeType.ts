/**
 * Picks the best MediaRecorder mime type this browser supports. Preference
 * order: opus-in-webm (smallest, widest desktop/Android support), then
 * plain webm, then Safari's mp4/aac, then ogg. Falls back to undefined so
 * MediaRecorder uses its own default when nothing on the list is supported.
 */
const CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4",
  "audio/ogg;codecs=opus",
  "audio/ogg",
];

export function pickRecorderMimeType(
  isTypeSupported: (type: string) => boolean = defaultIsTypeSupported
): string | undefined {
  for (const candidate of CANDIDATES) {
    if (isTypeSupported(candidate)) return candidate;
  }
  return undefined;
}

function defaultIsTypeSupported(type: string): boolean {
  return typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(type);
}

/** File extension to use for the recorded blob, based on its mime type. */
export function extensionForMimeType(mimeType: string | undefined): string {
  if (!mimeType) return "webm";
  if (mimeType.includes("mp4")) return "mp4";
  if (mimeType.includes("ogg")) return "ogg";
  return "webm";
}
