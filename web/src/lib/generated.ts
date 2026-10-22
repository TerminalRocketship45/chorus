import type { Passage } from "../types/api";
import { safeGet, safeSet } from "./storage";

const TOPIC_KEY = "chorus:topic";
const GENERATED_KEY = "chorus:generated";
const MAX_RECENT = 20;

/** The last topic the reader typed (empty string when none). */
export function loadTopic(): string {
  return safeGet(TOPIC_KEY) ?? "";
}

export function saveTopic(topic: string): void {
  safeSet(TOPIC_KEY, topic);
}

export interface StoredGenerated {
  passage: Passage | null;
  /** Ids of recently generated passages, newest first, for exclude_ids. */
  recent: string[];
}

export function loadGenerated(): StoredGenerated {
  const raw = safeGet(GENERATED_KEY);
  if (!raw) return { passage: null, recent: [] };
  try {
    const v = JSON.parse(raw) as Partial<StoredGenerated>;
    const passage = v.passage && typeof v.passage.id === "string" ? v.passage : null;
    const recent = Array.isArray(v.recent) ? v.recent.filter((x): x is string => typeof x === "string") : [];
    return { passage, recent };
  } catch {
    return { passage: null, recent: [] };
  }
}

/** Makes `passage` the current generated one and remembers its id, newest first, capped. */
export function rememberGenerated(prev: StoredGenerated, passage: Passage): StoredGenerated {
  return { passage, recent: [passage.id, ...prev.recent.filter((id) => id !== passage.id)].slice(0, MAX_RECENT) };
}

export function saveGenerated(value: StoredGenerated): void {
  safeSet(GENERATED_KEY, JSON.stringify(value));
}
