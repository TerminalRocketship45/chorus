import { UNREACHED_LEGEND, WORD_LEGEND } from "../lib/display";
import { MarkerIcon } from "./WordToken";

export function Legend({ showUnreached = false }: { showUnreached?: boolean }) {
  const items = showUnreached ? [...WORD_LEGEND, UNREACHED_LEGEND] : WORD_LEGEND;
  return (
    <section className="section" aria-labelledby="legend-title">
      <h2 className="section__title" id="legend-title" style={{ padding: "0 16px" }}>
        What the marks mean
      </h2>
      <ul className="group legend" aria-label="What the colours and marks mean">
        {items.map((item) => (
          <li className="legend__item" key={`${item.className}-${item.marker}`}>
            <span className={`word word--sample word--${item.className}`} aria-hidden="true">
              word
              {item.marker !== "none" && <MarkerIcon marker={item.marker} />}
            </span>
            <span>{item.label}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
