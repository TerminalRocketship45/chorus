import { useCallback, useEffect, useRef, useState } from "react";
import type { WordResult } from "../types/api";
import { findCurrentWord, hasTiming } from "../lib/replay";

export interface Replay {
  audio: HTMLAudioElement | null;
  playing: boolean;
  /** `index` of the word being spoken, or null. */
  current: number | null;
  /** False when the recording could not be loaded. */
  available: boolean;
  toggle: () => void;
  /** Seeks to the word's start and plays from there. Untimed words do nothing. */
  playFromWord: (word: WordResult) => void;
  seek: (seconds: number) => void;
}

/**
 * Plays the in-memory recording and follows its clock. The current word is
 * recomputed on every animation frame while playing (never a coarse interval),
 * and on seek/pause/end events otherwise. State only changes when the word does.
 */
export function useReplay(url: string | null, words: WordResult[]): Replay {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const wordsRef = useRef(words);
  wordsRef.current = words;
  const [audio, setAudio] = useState<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState<number | null>(null);
  const [available, setAvailable] = useState(url !== null);

  useEffect(() => {
    if (!url) {
      setAvailable(false);
      return;
    }
    const a = new Audio();
    a.preload = "auto";
    a.src = url;
    audioRef.current = a;
    setAudio(a);
    setAvailable(true);
    let raf = 0;

    const sync = () => {
      const idx = findCurrentWord(wordsRef.current, a.currentTime);
      setCurrent((prev) => (prev === idx ? prev : idx));
    };
    const tick = () => {
      sync();
      raf = requestAnimationFrame(tick);
    };
    const stopLoop = () => {
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
    };
    const onPlay = () => {
      setPlaying(true);
      stopLoop();
      raf = requestAnimationFrame(tick);
    };
    const onPause = () => {
      setPlaying(false);
      stopLoop();
      sync();
    };
    const onEnded = () => {
      setPlaying(false);
      stopLoop();
      setCurrent(null);
    };
    const onError = () => {
      setAvailable(false);
      setPlaying(false);
      stopLoop();
    };
    a.addEventListener("play", onPlay);
    a.addEventListener("playing", onPlay);
    a.addEventListener("pause", onPause);
    a.addEventListener("seeked", sync);
    a.addEventListener("ended", onEnded);
    a.addEventListener("error", onError);
    return () => {
      stopLoop();
      a.removeEventListener("play", onPlay);
      a.removeEventListener("playing", onPlay);
      a.removeEventListener("pause", onPause);
      a.removeEventListener("seeked", sync);
      a.removeEventListener("ended", onEnded);
      a.removeEventListener("error", onError);
      a.pause();
      a.removeAttribute("src");
      audioRef.current = null;
    };
  }, [url]);

  const toggle = useCallback(() => {
    const a = audioRef.current;
    if (!a) return;
    if (a.paused) {
      if (a.ended) a.currentTime = 0;
      a.play().catch(() => {});
    } else {
      a.pause();
    }
  }, []);

  const seek = useCallback((seconds: number) => {
    const a = audioRef.current;
    if (!a) return;
    a.currentTime = Math.max(0, seconds);
    setCurrent(findCurrentWord(wordsRef.current, a.currentTime));
  }, []);

  const playFromWord = useCallback((word: WordResult) => {
    const a = audioRef.current;
    if (!a || !hasTiming(word)) return;
    a.currentTime = word.start as number;
    setCurrent(word.index);
    a.play().catch(() => {});
  }, []);

  return { audio, playing, current, available, toggle, playFromWord, seek };
}
