import type { LanguageOption } from "../types/api";

/**
 * Native-script names shown beside the English language name in onboarding.
 * Only names we are sure of; anything missing is simply omitted. No support
 * notes here: the honest per-language status lives on the How it works page.
 */
export const NATIVE_NAMES: Record<string, string> = {
  somali: "Af-Soomaali",
  spanish: "Español",
  mandarin: "中文",
  hmong: "Hmoob",
  karen: "ကညီ",
};

/** docs/api.md GET /api/languages, bundled as a silent fallback when the API is unreachable. */
export const FALLBACK_LANGUAGES: LanguageOption[] = [
  { code: "somali", label: "Somali", support: "rules" },
  { code: "spanish", label: "Spanish", support: "rules" },
  { code: "mandarin", label: "Mandarin Chinese", support: "measured" },
  { code: "hmong", label: "Hmong", support: "not_yet" },
  { code: "karen", label: "Karen", support: "not_yet" },
  { code: "english", label: "English only", support: "not_needed" },
  { code: "other", label: "Another language", support: "not_yet" },
];
