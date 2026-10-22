/** Root-mean-square level (0-1) of an AnalyserNode time-domain byte buffer (128 = silence). */
export function levelFromTimeDomain(data: ArrayLike<number>): number {
  if (data.length === 0) return 0;
  let sum = 0;
  for (let i = 0; i < data.length; i++) {
    const v = (data[i] - 128) / 128;
    sum += v * v;
  }
  return Math.sqrt(sum / data.length);
}

/** Below this the mic is effectively silent. */
export const QUIET_LEVEL = 0.015;
/** Seconds of silence at the start before the hint appears. */
export const QUIET_HINT_AFTER_S = 3;

/** True when, after the grace period, the loudest level seen so far is still near silent. */
export function shouldShowQuietHint(elapsedS: number, maxLevel: number): boolean {
  return elapsedS >= QUIET_HINT_AFTER_S && maxLevel < QUIET_LEVEL;
}
