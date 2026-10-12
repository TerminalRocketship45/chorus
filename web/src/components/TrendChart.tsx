interface Series {
  label: string;
  color: string;
  points: number[];
}

interface TrendChartProps {
  title: string;
  series: Series[];
  /** Labels for each x position (e.g. session dates), same length as each series' points. */
  xLabels: string[];
  valueSuffix?: string;
}

const WIDTH = 320;
const HEIGHT = 160;
const PAD_LEFT = 36;
const PAD_RIGHT = 12;
const PAD_TOP = 16;
const PAD_BOTTOM = 28;

/** A small inline-SVG line chart. No charting library, per the project's minimal-dependency rule. */
export function TrendChart({ title, series, xLabels, valueSuffix = "" }: TrendChartProps) {
  const allValues = series.flatMap((s) => s.points);
  const maxValue = Math.max(1, ...allValues);
  const minValue = Math.min(0, ...allValues);
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
    return <p className="muted">Not enough sessions yet for a trend chart.</p>;
  }

  return (
    <figure role="group" aria-label={title} style={{ margin: 0 }}>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        width="100%"
        height={HEIGHT}
        role="img"
        aria-label={`${title}: ${series
          .map((s) => `${s.label} from ${s.points[0]}${valueSuffix} to ${s.points[n - 1]}${valueSuffix}`)
          .join("; ")}`}
      >
        <line
          x1={PAD_LEFT}
          y1={PAD_TOP + plotHeight}
          x2={WIDTH - PAD_RIGHT}
          y2={PAD_TOP + plotHeight}
          stroke="currentColor"
          strokeOpacity="0.3"
        />
        {series.map((s) => {
          const path = s.points.map((v, i) => `${i === 0 ? "M" : "L"} ${xFor(i)} ${yFor(v)}`).join(" ");
          return (
            <g key={s.label}>
              <path d={path} fill="none" stroke={s.color} strokeWidth={2.5} />
              {s.points.map((v, i) => (
                <circle key={i} cx={xFor(i)} cy={yFor(v)} r={3.5} fill={s.color} />
              ))}
            </g>
          );
        })}
        <text x={PAD_LEFT} y={HEIGHT - 6} fontSize="10" fill="currentColor">
          {xLabels[0]}
        </text>
        <text x={WIDTH - PAD_RIGHT} y={HEIGHT - 6} fontSize="10" fill="currentColor" textAnchor="end">
          {xLabels[n - 1]}
        </text>
      </svg>
      <figcaption className="legend">
        {series.map((s) => (
          <span className="legend__item" key={s.label}>
            <span
              aria-hidden="true"
              style={{
                display: "inline-block",
                width: 10,
                height: 10,
                borderRadius: "50%",
                background: s.color,
              }}
            />
            {s.label}
          </span>
        ))}
      </figcaption>
    </figure>
  );
}
