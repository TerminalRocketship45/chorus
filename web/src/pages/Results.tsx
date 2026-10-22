import { useCallback, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { AnalyzeResponse, Passage, WordResult } from "../types/api";
import { WordToken } from "../components/WordToken";
import { Legend } from "../components/Legend";
import { ScorePanel } from "../components/ScorePanel";
import { visualForDisplay } from "../lib/display";
import { Screen } from "../components/Screen";
import { Icon } from "../components/Icon";
import { Feedback } from "../components/Feedback";
import { ReplayPlayer } from "../components/ReplayPlayer";
import { useReplay } from "../hooks/useReplay";
import { hasTiming } from "../lib/replay";

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

function prefersReducedMotion(): boolean {
  try {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

/** Keeps the spoken word comfortably between the sticky bars; smooth unless the reader asked for less motion. */
function keepWordInView(index: number) {
  const el = document.querySelector<HTMLElement>(`[data-word-index="${index}"]`);
  if (!el) return;
  const root = el.closest<HTMLElement>("[data-scroll-root]");
  const box = root ? root.getBoundingClientRect() : { top: 0, bottom: window.innerHeight };
  const r = el.getBoundingClientRect();
  const top = box.top + 170; // navigation bar and the player
  const bottom = box.bottom - 110; // action bar
  if (r.top < top || r.bottom > bottom) {
    el.scrollIntoView({ block: "center", behavior: prefersReducedMotion() ? "auto" : "smooth" });
  }
}

export function Results() {
  const location = useLocation();
  const navigate = useNavigate();
  const state = location.state as LocationState | null;

  const [selected, setSelected] = useState<WordResult | null>(null);
  const [heardOpen, setHeardOpen] = useState(false);

  const blob = state?.audioBlob ?? null;
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  // Created and revoked in the same effect so a StrictMode remount never leaves a revoked URL behind.
  useEffect(() => {
    if (!blob) {
      setAudioUrl(null);
      return;
    }
    const url = URL.createObjectURL(blob);
    setAudioUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [blob]);

  const words = state?.analysis.words ?? [];
  const replay = useReplay(audioUrl, words);
  const { playFromWord, playing, current, available } = replay;
  const canReplay = available && audioUrl !== null && words.some(hasTiming);

  useEffect(() => {
    if (playing && current !== null) keepWordInView(current);
  }, [playing, current]);

  const selectWord = useCallback(
    (word: WordResult) => {
      setSelected(word);
      if (canReplay && hasTiming(word)) playFromWord(word);
      else if (!canReplay) speak(word.expected);
    },
    [canReplay, playFromWord]
  );

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
  const selectedVisual = selected ? visualForDisplay(selected.display) : null;
  const lastEnd = words.reduce((m, w) => Math.max(m, w.end ?? 0), 0);
  const durationHint = Math.max(lastEnd, analysis.score.duration_s);
  const transcript = analysis.transcript?.trim();

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
        {canReplay ? "Here's how your reading went. Play it back, or tap a word to jump to it." : "Here's how your reading went. Tap any word to hear it."}
      </p>

      <ScorePanel score={analysis.score} accentAdjusted={analysis.accent_adjusted} />

      <Feedback analysis={analysis} />

      <section className="section" aria-label="Your reading, word by word">
        {canReplay && (
          <ReplayPlayer
            audio={replay.audio}
            playing={playing}
            durationHint={durationHint}
            onToggle={replay.toggle}
            onSeek={replay.seek}
          />
        )}
        <div className="group reading" data-replay={canReplay}>
          {words.map((word) => (
            <WordToken
              key={word.index}
              word={word}
              selected={selected?.index === word.index}
              current={current === word.index}
              onSelect={selectWord}
            />
          ))}
        </div>

        {transcript && (
          <div className="group heard">
            <button
              type="button"
              className="row heard__toggle"
              aria-expanded={heardOpen}
              aria-controls="heard-text"
              onClick={() => setHeardOpen((o) => !o)}
            >
              <span className="row__body">
                <span className="row__title">What Chorus heard</span>
              </span>
              <span className="row__chev heard__chev" data-open={heardOpen}>
                <Icon name="chevronRight" size={18} strokeWidth={2.4} />
              </span>
            </button>
            {heardOpen && (
              <p className="heard__text" id="heard-text">
                {transcript}
              </p>
            )}
          </div>
        )}

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
