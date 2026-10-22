import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { AnalyzeResponse, Passage, WordResult } from "../types/api";
import { WordToken } from "../components/WordToken";
import { Legend } from "../components/Legend";
import { ScorePanel } from "../components/ScorePanel";
import { visualForDisplay } from "../lib/display";
import { Screen } from "../components/Screen";
import { Icon } from "../components/Icon";

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
      <Screen title="Results" back={{ label: "Passages", to: "/passages" }}>
        <div className="notice notice--error" role="alert">
          <Icon name="warning" size={20} />
          <span>Chorus doesn't have a reading to show. Let's read one first.</span>
        </div>
        <button type="button" className="btn btn--filled btn--block" onClick={() => navigate("/passages")}>
          Pick a passage
        </button>
      </Screen>
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
    <Screen
      title={passage.title}
      large
      back={{ label: "Passages", to: "/passages" }}
      bottom={
        <button type="button" className="btn btn--filled btn--block" onClick={() => navigate("/passages")}>
          Read another passage
        </button>
      }
    >
      <p className="lede" style={{ marginTop: -16 }}>
        Here's how your reading went. Tap any word to hear it.
      </p>

      <ScorePanel score={analysis.score} accentAdjusted={analysis.accent_adjusted} />

      <section className="section" aria-label="Your reading, word by word">
        <div className="group reading">
          {analysis.words.map((word) => (
            <WordToken key={word.index} word={word} selected={selected?.index === word.index} onSelect={selectWord} />
          ))}
        </div>

        {selected && selectedVisual && (
          <div className="group" role="status" aria-live="polite">
            <div className="detail">
              <strong className="detail__word">{selected.expected}</strong>
              {selectedVisual.showsHeard && selected.heard && <p>You said: "{selected.heard}"</p>}
              {selectedVisual.markerLabel && <p className="row__sub">{selectedVisual.markerLabel}</p>}
            </div>
            <div className="detail__actions">
              <button type="button" className="btn btn--tinted btn--compact" onClick={() => speak(selected.expected)}>
                <Icon name="speaker" size={18} />
                Hear it said
              </button>
              {audioUrl && selected.start != null && selected.end != null && (
                <button type="button" className="btn btn--tinted btn--compact" onClick={() => playHeardSlice(selected)}>
                  <Icon name="waveform" size={18} />
                  Hear yourself
                </button>
              )}
            </div>
          </div>
        )}
      </section>

      {analysis.practice_words.length > 0 && (
        <section className="section" aria-labelledby="practice-title">
          <h2 className="section__title" id="practice-title" style={{ padding: "0 16px" }}>
            Words to practice
          </h2>
          <div className="chips">
            {analysis.practice_words.map((word) => (
              <button key={word} type="button" className="chip chip--action" onClick={() => speak(word)}>
                <Icon name="speaker" size={16} />
                {word}
              </button>
            ))}
          </div>
          <p className="footnote">Tap a word to hear how it sounds.</p>
        </section>
      )}

      <Legend />
    </Screen>
  );
}
