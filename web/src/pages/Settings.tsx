import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Screen } from "../components/Screen";
import { Sheet } from "../components/Sheet";
import { Icon } from "../components/Icon";
import { THEME_PREFS, applyThemePref, loadThemePref, saveThemePref, type ThemePref } from "../lib/theme";

const THEME_LABELS: Record<ThemePref, string> = { system: "System", light: "Light", dark: "Dark" };

export function Settings() {
  const navigate = useNavigate();
  const [theme, setTheme] = useState<ThemePref>(() => loadThemePref());
  const [sheet, setSheet] = useState(false);

  const choose = (pref: ThemePref) => {
    setTheme(pref);
    saveThemePref(pref);
    applyThemePref(pref);
  };

  const canGoBack = typeof window !== "undefined" && (window.history.state?.idx ?? 0) > 0;

  return (
    <Screen
      title="Settings"
      large
      settings={false}
      back={canGoBack ? { label: "Back", onClick: () => navigate(-1) } : { label: "Home", to: "/" }}
    >
      <section className="section" aria-labelledby="appearance-title">
        <div className="section__head">
          <h2 className="section__title" id="appearance-title">
            Appearance
          </h2>
        </div>
        <div className="group" role="radiogroup" aria-labelledby="appearance-title">
          {THEME_PREFS.map((pref) => (
            <button
              key={pref}
              type="button"
              role="radio"
              aria-checked={theme === pref}
              className="row"
              onClick={() => choose(pref)}
            >
              <span className="row__body">
                <span className="row__title">{THEME_LABELS[pref]}</span>
              </span>
              <span className="row__check">{theme === pref && <Icon name="check" size={22} strokeWidth={2.6} />}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="section" aria-labelledby="account-title">
        <div className="section__head">
          <h2 className="section__title" id="account-title">
            Account
          </h2>
        </div>
        <div className="group">
          <button type="button" className="row" onClick={() => setSheet(true)} aria-haspopup="dialog">
            <span className="row__body">
              <span className="row__title">Link parent's account</span>
            </span>
            <span className="row__chev">
              <Icon name="chevronRight" size={18} strokeWidth={2.4} />
            </span>
          </button>
        </div>
      </section>

      {sheet && (
        <Sheet title="Link parent's account" onClose={() => setSheet(false)}>
          <p>Coming soon.</p>
        </Sheet>
      )}
    </Screen>
  );
}
