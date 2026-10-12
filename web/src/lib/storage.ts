import type { GradeBand } from "../types/api";

/**
 * Every localStorage access goes through here, wrapped in try/catch: private
 * browsing, blocked storage, or a full quota must never crash the app.
 */
const KEYS = {
  studentId: "chorus:studentId",
  studentName: "chorus:studentName",
  gradeBand: "chorus:gradeBand",
  homeLanguage: "chorus:homeLanguage",
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
}
