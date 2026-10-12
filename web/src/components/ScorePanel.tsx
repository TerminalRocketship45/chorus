import type { ReadingScore } from "../types/api";
import { formatAccuracyPct, formatWcpm } from "../lib/format";

interface ScorePanelProps {
  score: ReadingScore;
  accentAdjusted: ReadingScore | null;
}

export function ScorePanel({ score, accentAdjusted }: ScorePanelProps) {
  return (
    <div className="stack">
      <div className="score-grid">
        <div className="score-tile">
          <div className="score-tile__value">{formatWcpm(score.wcpm)}</div>
          <div className="score-tile__label">words correct per minute</div>
        </div>
        <div className="score-tile">
          <div className="score-tile__value">{formatAccuracyPct(score.accuracy)}</div>
          <div className="score-tile__label">accuracy</div>
        </div>
      </div>

      {accentAdjusted && (
        <div className="card" aria-label="Accuracy with and without accent adjustment">
          <h3 style={{ marginTop: 0 }}>Two ways to count accuracy</h3>
          <div className="score-grid">
            <div className="score-tile">
              <div className="score-tile__value">{formatAccuracyPct(score.accuracy)}</div>
              <div className="score-tile__label">Every difference counted</div>
            </div>
            <div className="score-tile">
              <div className="score-tile__value">{formatAccuracyPct(accentAdjusted.accuracy)}</div>
              <div className="score-tile__label">Accent differences not counted</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
