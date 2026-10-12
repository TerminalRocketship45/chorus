import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { AnalyzeResponse, Passage, WordResult } from "../types/api";
import { WordToken } from "../components/WordToken";
import { Legend } from "../components/Legend";
import { ScorePanel } from "../components/ScorePanel";
import { visualForDisplay } from "../lib/display";

interface LocationState {
  analysis: AnalyzeResponse;
  passage: Passage;
  audioBlob: Blob | null;
}

function speak(text: string) {
  try {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "en-US";
    window.speechSynthesis.speak(utterance);
  } catch {
    // speechSynthesis isn't available on every browser/device; silently skip.
  }
}

export function Results() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as LocationState | null;

  const [selected, setSelected] = useState<WordResult | null>(null);
  const audioElRef = useRef<HTMLAudioElement | null>(null);

  const audioUrl = useMemo(() => {
    if (!state?.audioBlob) return null;
    return URL.createObjectURL(state.audioBlob);
  }, [state?.audioBlob]);

  useEffect(() => {
    return () => {
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    };
  }, [audioUrl]);

  if (!state) {
    return (
      <div className="page stack">
        <p className="error-banner">Chorus doesn't have a reading to show. Let's read one first.</p>
        <button type="button" className="btn btn-primary" onClick={() => navigate("/passages")}>
          Pick a passage
        </button>
      </div>
    );
  }

  const { analysis, passage } = state;

  function selectWord(word: WordResult) {
    setSelected(word);
    speak(word.expected);
  }

  function playHeardSlice(word: WordResult) {
    if (!audioUrl || word.start == null || word.end == null) return;
    const audio = audioElRef.current ?? new Audio();
    audioElRef.current = audio;
    audio.src = audioUrl;
    audio.currentTime = word.start;
    const duration = Math.max(0.15, word.end - word.start);
    audio.play().catch(() => {
      // Autoplay / decode issues shouldn't crash the page.
    });
    window.setTimeout(() => {
      if (!audio.paused) audio.pause();
    }, duration * 1000);
  }

  const selectedVisual = selected ? visualForDisplay(selected.display) : null;

  return (
    <div className="page page--wide stack stack--loose">
      <div className="stack stack--tight">
        <h1>{passage.title}</h1>
        <p className="muted">Here's how your reading went. Tap any word to hear it.</p>
      </div>

      <div className="card" aria-label="Your reading, word by word">
        <p style={{ fontSize: "1.25rem", lineHeight: 2.1 }}>
          {analysis.words.map((word) => (
            <WordToken key={word.index} word={word} selected={selected?.index === word.index} onSelect={selectWord} />
          ))}
        </p>
      </div>

      {selected && selectedVisual && (
        <div className="card stack stack--tight" role="status" aria-live="polite">
          <strong>{selected.expected}</strong>
          {selectedVisual.showsHeard && selected.heard && (
            <p>You said: "{selected.heard}"</p>
          )}
          {selectedVisual.markerLabel && <p className="muted">{selectedVisual.markerLabel}</p>}
          <div className="stack stack--tight" style={{ flexDirection: "row", display: "flex" }}>
            <button type="button" className="btn btn-secondary" onClick={() => speak(selected.expected)}>
              Hear it said
            </button>
            {audioUrl && selected.start != null && selected.end != null && (
              <button type="button" className="btn btn-secondary" onClick={() => playHeardSlice(selected)}>
                Hear yourself
              </button>
            )}
          </div>
        </div>
      )}

      <Legend />

      <ScorePanel score={analysis.score} accentAdjusted={analysis.accent_adjusted} />

      {analysis.practice_words.length > 0 && (
        <div className="card stack stack--tight">
          <h2 style={{ marginTop: 0 }}>Words to practice</h2>
          <p className="muted">Tap a word to hear how it sounds.</p>
          <div className="stack stack--tight" style={{ flexDirection: "row", flexWrap: "wrap", display: "flex" }}>
            {analysis.practice_words.map((word) => (
              <button key={word} type="button" className="btn btn-secondary" onClick={() => speak(word)}>
                {word}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="stack">
        <button type="button" className="btn btn-primary btn-block" onClick={() => navigate("/passages")}>
          Read another passage
        </button>
      </div>
    </div>
  );
}
