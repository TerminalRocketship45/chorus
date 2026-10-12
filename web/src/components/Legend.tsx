import { WORD_LEGEND } from "../lib/display";

const MARKER_GLYPH: Record<string, string> = {
  extra: "➕",
  repeated: "↻",
  fixed: "✓",
};

export function Legend() {
  return (
    <ul className="legend" aria-label="What the colours and marks mean">
      {WORD_LEGEND.map((item) => (
        <li className="legend__item" key={`${item.className}-${item.marker}`}>
          <span className={`word word--${item.className}`} aria-hidden="true" style={{ cursor: "default" }}>
            word
            {item.marker !== "none" && (
              <span className={`word__marker word__marker--${item.marker}`}>
                {MARKER_GLYPH[item.marker]}
              </span>
            )}
          </span>
          <span>{item.label}</span>
        </li>
      ))}
    </ul>
  );
}
