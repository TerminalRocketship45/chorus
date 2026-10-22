import { useEffect, useRef, useState } from "react";
import { levelFromTimeDomain, shouldShowQuietHint } from "../lib/level";

const BARS = 5;
const WEIGHTS = [0.55, 0.8, 1, 0.8, 0.55];

declare global {
  interface Window {
    /** Dev/mock hook: when set, returns the level (0-1) instead of the microphone's. */
    __chorusMockLevel?: () => number;
  }
}

/**
 * A few calm bars that follow the microphone level while recording, and one quiet
 * hint if nothing is heard in the first seconds. Reads the same MediaStream the
 * recorder uses (Web Audio AnalyserNode); stops with the recording.
 */
export function MicMeter({ stream, active }: { stream: MediaStream | null; active: boolean }) {
  const barRefs = useRef<Array<HTMLSpanElement | null>>([]);
  const [quiet, setQuiet] = useState(false);

  useEffect(() => {
    if (!active) return;
    let ctx: AudioContext | null = null;
    let analyser: AnalyserNode | null = null;
    let data: Uint8Array | null = null;
    try {
      if (stream && !window.__chorusMockLevel) {
        const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
        if (Ctor) {
          ctx = new Ctor();
          analyser = ctx.createAnalyser();
          analyser.fftSize = 512;
          ctx.createMediaStreamSource(stream).connect(analyser);
          data = new Uint8Array(analyser.fftSize);
        }
      }
    } catch {
      analyser = null;
    }
    const started = performance.now();
    let max = 0;
    let smooth = 0;
    let raf = 0;
    let hintShown = false;
    const tick = () => {
      let level = 0;
      if (window.__chorusMockLevel) level = window.__chorusMockLevel();
      else if (analyser && data) {
        analyser.getByteTimeDomainData(data as Uint8Array<ArrayBuffer>);
        level = levelFromTimeDomain(data);
      }
      max = Math.max(max, level);
      // Speech sits around 0.05-0.3 RMS; stretch it so normal talking fills most of the bars.
      const target = Math.min(1, level * 4);
      smooth = target > smooth ? target : smooth * 0.9 + target * 0.1;
      barRefs.current.forEach((el, i) => {
        if (el) el.style.transform = `scaleY(${0.16 + 0.84 * Math.min(1, smooth * WEIGHTS[i])})`;
      });
      const wantHint = shouldShowQuietHint((performance.now() - started) / 1000, max);
      if (wantHint !== hintShown) {
        hintShown = wantHint;
        setQuiet(wantHint);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      cancelAnimationFrame(raf);
      setQuiet(false);
      void ctx?.close().catch(() => {});
    };
  }, [stream, active]);

  if (!active) return null;
  return (
    <div className="meter-wrap">
      <div className="meter" role="img" aria-label="Microphone level">
        {Array.from({ length: BARS }, (_, i) => (
          <span key={i} ref={(el) => (barRefs.current[i] = el)} className="meter__bar" />
        ))}
      </div>
      <p className="meter__hint" role="status">
        {quiet ? "We can't hear you yet — check the microphone." : ""}
      </p>
    </div>
  );
}
