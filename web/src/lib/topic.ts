export const MAX_TOPIC_LENGTH = 80;

/** Trims and caps a typed topic (docs/api.md: at most 80 characters). Empty means "no topic". */
export function normalizeTopic(raw: string): string {
  return raw.replace(/\s+/g, " ").trim().slice(0, MAX_TOPIC_LENGTH).trim();
}

/** "Sharks" for a topic shown in a row's subtitle. */
export function capitalizeTopic(topic: string): string {
  return topic.charAt(0).toUpperCase() + topic.slice(1);
}
