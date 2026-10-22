import type { GradeBand, Passage } from "../types/api";
import type { LocalHistory } from "./history";

/**
 * Every localStorage access goes through here, wrapped in try/catch: private
 * browsing, blocked storage, or a full quota must never crash the app.
 */
const KEYS = {
  studentId: "chorus:studentId",
  studentName: "chorus:studentName",
  gradeBand: "chorus:gradeBand",
  homeLanguage: "chorus:homeLanguage",
  interests: "chorus:interests",
  history: "chorus:history",
  localPassages: "chorus:localPassages",
} as const;

function safeGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Storage unavailable (private browsing, quota, etc.) — proceed without persistence.
  }
}

function safeRemove(key: string): void {
  try {
    window.localStorage.removeItem(key);
  } catch {
    // ignore
  }
}

export interface StoredReader {
  studentId: number | null;
  studentName: string | null;
  gradeBand: GradeBand | null;
  homeLanguage: string | null;
  interests: string[];
}

function parseJson<T>(raw: string | null, fallback: T): T {
  if (raw === null) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function loadStoredReader(): StoredReader {
  const studentIdRaw = safeGet(KEYS.studentId);
  const gradeBandRaw = safeGet(KEYS.gradeBand);
  return {
    studentId: studentIdRaw !== null && studentIdRaw !== "" ? Number(studentIdRaw) : null,
    studentName: safeGet(KEYS.studentName),
    gradeBand: gradeBandRaw === "elementary" || gradeBandRaw === "secondary" ? gradeBandRaw : null,
    homeLanguage: safeGet(KEYS.homeLanguage),
    interests: loadInterests(),
  };
}

export function loadInterests(): string[] {
  const value = parseJson<unknown>(safeGet(KEYS.interests), []);
  return Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];
}

export function saveInterests(codes: string[]): void {
  safeSet(KEYS.interests, JSON.stringify(codes));
}

/** Read/score marks for readers without a nickname. */
export function loadHistory(): LocalHistory {
  const value = parseJson<unknown>(safeGet(KEYS.history), {});
  return value && typeof value === "object" && !Array.isArray(value) ? (value as LocalHistory) : {};
}

export function saveHistory(history: LocalHistory): void {
  safeSet(KEYS.history, JSON.stringify(history));
}

/** Passages written for a reader without a nickname (there is no server list for them). */
export function loadLocalPassages(): Passage[] {
  const value = parseJson<unknown>(safeGet(KEYS.localPassages), []);
  return Array.isArray(value) ? (value as Passage[]) : [];
}

export function saveLocalPassages(passages: Passage[]): void {
  safeSet(KEYS.localPassages, JSON.stringify(passages));
}

export function saveGradeBand(gradeBand: GradeBand): void {
  safeSet(KEYS.gradeBand, gradeBand);
}

export function saveHomeLanguage(code: string): void {
  safeSet(KEYS.homeLanguage, code);
}

export function saveStudent(id: number, name: string): void {
  safeSet(KEYS.studentId, String(id));
  safeSet(KEYS.studentName, name);
}

/** Clears the saved reader so another student can go through onboarding. */
export function clearReader(): void {
  safeRemove(KEYS.studentId);
  safeRemove(KEYS.studentName);
  safeRemove(KEYS.gradeBand);
  safeRemove(KEYS.homeLanguage);
  safeRemove(KEYS.interests);
  safeRemove(KEYS.history);
  safeRemove(KEYS.localPassages);
}
