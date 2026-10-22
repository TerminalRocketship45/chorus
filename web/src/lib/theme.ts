import { safeGet, safeSet } from "./storage";

/** The reader's appearance choice. "system" follows the device (prefers-color-scheme). */
export type ThemePref = "system" | "light" | "dark";

export const THEME_KEY = "chorus:theme";
export const THEME_PREFS: readonly ThemePref[] = ["system", "light", "dark"];

/** Anything unrecognised (missing, hand-edited) counts as "system". */
export function parseThemePref(raw: string | null | undefined): ThemePref {
  return raw === "light" || raw === "dark" ? raw : "system";
}

/** The theme actually shown, given the choice and what the device prefers. */
export function resolveTheme(pref: ThemePref, systemDark: boolean): "light" | "dark" {
  if (pref === "system") return systemDark ? "dark" : "light";
  return pref;
}

export function loadThemePref(): ThemePref {
  return parseThemePref(safeGet(THEME_KEY));
}

export function saveThemePref(pref: ThemePref): void {
  safeSet(THEME_KEY, pref);
}

function systemPrefersDark(): boolean {
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  } catch {
    return false;
  }
}

/**
 * Applies the choice to <html>. An explicit choice sets data-theme; "system"
 * removes it so the prefers-color-scheme rules in theme.css decide.
 */
export function applyThemePref(pref: ThemePref): void {
  const root = document.documentElement;
  if (pref === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", pref);
  const resolved = resolveTheme(pref, systemPrefersDark());
  document
    .querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')
    .forEach((m) => m.setAttribute("content", resolved === "dark" ? "#000000" : "#f2f2f7"));
}
