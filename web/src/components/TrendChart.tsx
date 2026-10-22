export interface TrendSeries {
  label: string;
  /** A CSS colour or var(--token). */
  color: string;
  points: number[];
  /** Dashed lines keep two series distinguishable without relying on colour. */
  dashed?: boolean;
}

interface TrendChartProps {
  title: string;
  series: TrendSeries[];
  /** Labels for each x position (e.g. session dates), same length as each series' points. */
  xLabels: string[];
  valueSuffix?: string;
}

const WIDTH = 320;
const HEIGHT = 168;
const PAD_LEFT = 34;
const PAD_RIGHT = 12;
const PAD_TOP = 14;
const PAD_BOTTOM = 28;

/** A small inline-SVG line chart. No charting library, per the project's minimal-dependency rule. */
export function TrendChart({ title, series, xLabels, valueSuffix = "" }: TrendChartProps) {
  const allValues = series.flatMap((s) => s.points);
  const rawMax = Math.max(1, ...allValues);
  const maxValue = valueSuffix === "%" ? 100 : Math.ceil(rawMax / 10) * 10;
  const minValue = 0;
  const plotWidth = WIDTH - PAD_LEFT - PAD_RIGHT;
  const plotHeight = HEIGHT - PAD_TOP - PAD_BOTTOM;
  const n = xLabels.length;

  function xFor(i: number): number {
    if (n <= 1) return PAD_LEFT + plotWidth / 2;
    return PAD_LEFT + (i / (n - 1)) * plotWidth;
  }

  function yFor(value: number): number {
    const range = maxValue - minValue || 1;
    return PAD_TOP + plotHeight - ((value - minValue) / range) * plotHeight;
  }

  if (n === 0) {
    return <p className="footnote">Not enough sessions yet for a trend chart.</p>;
  }

  const ticks = [0, maxValue / 2, maxValue];

  return (
    <figure role="group" aria-label={title} style={{ margin: 0 }}>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        width="100%"
        role="img"
        aria-label={`${title}: ${series
          .map((s) => `${s.label} from ${s.points[0]}${valueSuffix} to ${s.points[n - 1]}${valueSuffix}`)
          .join("; ")}`}
        style={{ display: "block", overflow: "visible" }}
      >
        {ticks.map((t) => (
          <g key={t}>
            <line x1={PAD_LEFT} x2={WIDTH - PAD_RIGHT} y1={yFor(t)} y2={yFor(t)} stroke="var(--chart-grid)" strokeWidth={1} />
            <text x={PAD_LEFT - 6} y={yFor(t) + 4} fontSize="11" textAnchor="end" fill="var(--label-2)">
              {Math.round(t)}
              {valueSuffix}
            </text>
          </g>
        ))}
        {series.map((s) => {
          const path = s.points.map((v, i) => `${i === 0 ? "M" : "L"} ${xFor(i)} ${yFor(v)}`).join(" ");
          return (
            <g key={s.label}>
              <path
                d={path}
                fill="none"
                stroke={s.color}
                strokeWidth={2.5}
                strokeLinejoin="round"
                strokeLinecap="round"
                strokeDasharray={s.dashed ? "5 5" : undefined}
              />
              {s.points.map((v, i) => (
                <circle key={i} cx={xFor(i)} cy={yFor(v)} r={3.5} fill="var(--surface)" stroke={s.color} strokeWidth={2} />
              ))}
            </g>
          );
        })}
        <text x={PAD_LEFT} y={HEIGHT - 6} fontSize="11" fill="var(--label-2)">
          {xLabels[0]}
        </text>
        {n > 1 && (
          <text x={WIDTH - PAD_RIGHT} y={HEIGHT - 6} fontSize="11" fill="var(--label-2)" textAnchor="end">
            {xLabels[n - 1]}
          </text>
        )}
      </svg>
      <figcaption className="chart__legend">
        {series.map((s) => (
          <span className="chart__key" key={s.label}>
            <svg width="22" height="8" aria-hidden="true">
              <line
                x1="1"
                x2="21"
                y1="4"
                y2="4"
                stroke={s.color}
                strokeWidth={2.5}
                strokeLinecap="round"
                strokeDasharray={s.dashed ? "4 4" : undefined}
              />
            </svg>
            {s.label}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
