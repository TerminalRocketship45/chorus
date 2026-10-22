import type { GradeBand } from "../types/api";
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
  topic: "chorus:topic",
  generated: "chorus:generated",
  history: "chorus:history",
  localPassages: "chorus:localPassages",
} as const;

export function safeGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function safeSet(key: string, value: string): void {
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
  };
}

/** Read/score marks for readers without a nickname. */
export function loadHistory(): LocalHistory {
  const value = parseJson<unknown>(safeGet(KEYS.history), {});
  return value && typeof value === "object" && !Array.isArray(value) ? (value as LocalHistory) : {};
}

export function saveHistory(history: LocalHistory): void {
  safeSet(KEYS.history, JSON.stringify(history));
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
  safeRemove(KEYS.topic);
  safeRemove(KEYS.generated);
}
