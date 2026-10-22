import type { Interest } from "../types/api";

/** The fixed interest list (docs/api.md, GET /api/interests), bundled so the UI never waits on the network. */
export const INTERESTS: Interest[] = [
  { code: "animals", label: "Animals" },
  { code: "sports", label: "Sports" },
  { code: "space", label: "Space" },
  { code: "nature", label: "Nature" },
  { code: "food", label: "Food" },
  { code: "music", label: "Music" },
  { code: "art", label: "Art" },
  { code: "science", label: "Science" },
  { code: "history", label: "History" },
  { code: "adventure", label: "Adventure" },
];
