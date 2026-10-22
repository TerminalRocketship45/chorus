/** Pure parts of the results confetti, kept apart from the canvas so they can be tested. */

export interface ConfettiPiece {
  x: number; // start, px
  y: number; // start, px (above the top edge)
  w: number;
  h: number;
  vx: number; // px per second
  vy: number; // px per second
  rot: number;
  vr: number; // radians per second
  sway: number; // px amplitude
  swayRate: number; // rad per second
  delay: number; // seconds
  colour: number; // index into the palette
}

export const CONFETTI_COUNT = 36;
export const CONFETTI_SECONDS = 1.5;

/** True unless the reader asked the device for less motion. */
export function confettiAllowed(reducedMotion: boolean): boolean {
  return !reducedMotion;
}

export function makeConfettiPieces(count: number, width: number, rand: () => number = Math.random): ConfettiPiece[] {
  const pieces: ConfettiPiece[] = [];
  for (let i = 0; i < count; i++) {
    const size = 4 + rand() * 3;
    pieces.push({
      x: rand() * width,
      y: -12 - rand() * 40,
      w: size,
      h: size * (1.4 + rand() * 0.6),
      vx: (rand() - 0.5) * 30,
      vy: 360 + rand() * 220,
      rot: rand() * Math.PI * 2,
      vr: (rand() - 0.5) * 9,
      sway: 6 + rand() * 10,
      swayRate: 4 + rand() * 4,
      delay: rand() * 0.35,
      // weighted towards the accent: about half accent, a quarter for each muted tone
      colour: i % 4 < 2 ? 0 : i % 4 === 2 ? 1 : 2,
    });
  }
  return pieces;
}

/**
 * Remembers which history entries already played their confetti, so going back
 * to a results screen (or reloading it) never replays it. Storage is injectable
 * for tests; sessionStorage failures degrade to an in-memory set.
 */
const memory = new Set<string>();

export function claimFirstView(key: string, storage?: Pick<Storage, "getItem" | "setItem"> | null): boolean {
  const id = `chorus:celebrated:${key}`;
  if (memory.has(id)) return false;
  let store = storage;
  if (store === undefined) {
    try {
      store = window.sessionStorage;
    } catch {
      store = null;
    }
  }
  try {
    if (store && store.getItem(id)) {
      memory.add(id);
      return false;
    }
    store?.setItem(id, "1");
  } catch {
    // storage blocked: the in-memory set still guards this page load
  }
  memory.add(id);
  return true;
}

/** Test helper. */
export function resetFirstViewMemory(): void {
  memory.clear();
}
