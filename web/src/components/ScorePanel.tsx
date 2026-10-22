import type { ReadingScore } from "../types/api";
import { formatAccuracyPct, formatWcpm, formatWordsReached } from "../lib/format";

interface ScorePanelProps {
  score: ReadingScore;
  accentAdjusted: ReadingScore | null;
}

/** Words correct per minute is the headline; accuracy sits below, raw and accent-adjusted side by side. */
export function ScorePanel({ score, accentAdjusted }: ScorePanelProps) {
  const reached = formatWordsReached(score);
  return (
    <>
      <div className="group summary summary--single summary--headline" role="group" aria-label="Words correct per minute">
        <div className="stat">
          <div className="stat__value stat__value--headline num">{formatWcpm(score.wcpm)}</div>
          <div className="stat__label">words correct per minute</div>
        </div>
      </div>

      <section className="section" aria-labelledby="accuracy-title">
        <h2 className="section__title" id="accuracy-title" style={{ padding: "0 16px" }}>
          {accentAdjusted ? "Two ways to count accuracy" : "Accuracy"}
        </h2>
        {accentAdjusted ? (
          <div className="group summary" role="group" aria-label="Accuracy with and without accent adjustment">
            <div className="stat">
              <div className="stat__value num">{formatAccuracyPct(score.accuracy)}</div>
              <div className="stat__label">Every difference counted</div>
            </div>
            <div className="stat">
              <div className="stat__value num">{formatAccuracyPct(accentAdjusted.accuracy)}</div>
              <div className="stat__label">Accent differences not counted</div>
            </div>
          </div>
        ) : (
          <div className="group summary summary--single" role="group" aria-label="Accuracy">
            <div className="stat">
              <div className="stat__value num">{formatAccuracyPct(score.accuracy)}</div>
              <div className="stat__label">of words read correctly</div>
            </div>
          </div>
        )}
        {reached && (
          <p className="footnote" style={{ padding: "0 16px" }}>
            {reached}. Accuracy counts only those words.
          </p>
        )}
      </section>
    </>
  );
}
