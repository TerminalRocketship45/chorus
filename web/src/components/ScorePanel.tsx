import type { ReadingScore } from "../types/api";
import { formatAccuracyPct, formatWcpm } from "../lib/format";

interface ScorePanelProps {
  score: ReadingScore;
  accentAdjusted: ReadingScore | null;
}

/** The result summary: two quiet grouped panels, not a dashboard. */
export function ScorePanel({ score, accentAdjusted }: ScorePanelProps) {
  return (
    <>
      <div className="group summary" role="group" aria-label="Your reading in numbers">
        <div className="stat">
          <div className="stat__value num">{formatWcpm(score.wcpm)}</div>
          <div className="stat__label">words correct per minute</div>
        </div>
        <div className="stat">
          <div className="stat__value num">{formatAccuracyPct(score.accuracy)}</div>
          <div className="stat__label">accuracy</div>
        </div>
      </div>

      {accentAdjusted && (
        <section className="section" aria-labelledby="two-ways-title">
          <h2 className="section__title" id="two-ways-title" style={{ padding: "0 16px" }}>
            Two ways to count accuracy
          </h2>
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
        </section>
      )}
    </>
  );
}
