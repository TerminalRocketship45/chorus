import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";
import { formatElapsed } from "../lib/format";
import { Icon } from "./Icon";

interface ReplayPlayerProps {
  audio: HTMLAudioElement | null;
  playing: boolean;
  /** Used while the recording's own duration is unknown (MediaRecorder files often report Infinity). */
  durationHint: number;
  onToggle: () => void;
  onSeek: (seconds: number) => void;
}

/** Play/pause plus a scrubber for the reader's own recording. Space toggles when the player has focus. */
export function ReplayPlayer({ audio, playing, durationHint, onToggle, onSeek }: ReplayPlayerProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [top, setTop] = useState(52);
  const [time, setTime] = useState(0);
  const [duration, setDuration] = useState(durationHint);

  // Stick just below the navigation bar, whatever its height (the phone frame's status bar adds to it).
  useLayoutEffect(() => {
    const bar = rootRef.current?.closest("[data-scroll-root], body")?.querySelector<HTMLElement>(".navbar");
    if (bar) setTop(bar.offsetHeight + 6);
  }, []);

  useEffect(() => {
    if (!audio) return;
    let raf = 0;
    const readDuration = () => {
      const d = audio.duration;
      setDuration(Number.isFinite(d) && d > 0 ? d : durationHint);
    };
    const read = () => setTime(Math.round(audio.currentTime * 10) / 10);
    const loop = () => {
      read();
      raf = requestAnimationFrame(loop);
    };
    if (playing) raf = requestAnimationFrame(loop);
    else read();
    readDuration();
    audio.addEventListener("durationchange", readDuration);
    audio.addEventListener("seeked", read);
    audio.addEventListener("ended", read);
    return () => {
      if (raf) cancelAnimationFrame(raf);
      audio.removeEventListener("durationchange", readDuration);
      audio.removeEventListener("seeked", read);
      audio.removeEventListener("ended", read);
    };
  }, [audio, playing, durationHint]);

  function onKeyDown(e: KeyboardEvent<HTMLDivElement>) {
    // Buttons already toggle on Space; handle it for the rest of the player (the scrubber).
    if (e.key === " " && !(e.target as HTMLElement).closest("button")) {
      e.preventDefault();
      onToggle();
    }
  }

  const shown = Math.min(time, duration);
  return (
    <div ref={rootRef} className="player" style={{ top }} role="group" aria-label="Replay your recording" onKeyDown={onKeyDown}>
      <button
        type="button"
        className="player__btn"
        aria-label={playing ? "Pause your recording" : "Play your recording"}
        onClick={onToggle}
      >
        <Icon name={playing ? "pause" : "play"} size={22} />
      </button>
      <input
        className="player__scrub"
        type="range"
        min={0}
        max={Math.max(duration, 0.1)}
        step={0.05}
        value={shown}
        aria-label="Position in your recording"
        aria-valuetext={`${formatElapsed(shown)} of ${formatElapsed(duration)}`}
        onChange={(e) => onSeek(Number(e.target.value))}
        style={{ "--fill": `${duration > 0 ? (shown / duration) * 100 : 0}%` } as React.CSSProperties}
      />
      <span className="player__time num" aria-hidden="true">
        {formatElapsed(shown)} / {formatElapsed(duration)}
      </span>
    </div>
  );
}
