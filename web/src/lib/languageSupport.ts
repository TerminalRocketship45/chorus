import type { LanguageSupport } from "../types/api";

/**
 * Honest, per-language onboarding note for a support level. Wording follows
 * the design spec's examples (Somali/rules, Mandarin/measured, Hmong/not_yet)
 * generalised to any language label. `not_needed` has no note.
 */
export function supportNote(label: string, support: LanguageSupport): string | null {
  switch (support) {
    case "rules":
      return (
        `Chorus uses published research about ${label} pronunciation. ` +
        `This hasn't been tested on recordings of ${label} speakers yet.`
      );
    case "measured":
      return `Tested against expert ratings of ${label} speakers.`;
    case "not_yet":
      return (
        `Chorus doesn't have ${label} sound rules yet, so your reading is ` +
        `scored without accent adjustment.`
      );
    case "not_needed":
      return null;
    default:
      return null;
  }
}
