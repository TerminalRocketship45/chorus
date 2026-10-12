import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { GradeBand, LanguageOption } from "../types/api";
import { createStudent, getLanguages, ApiRequestError } from "../lib/api";
import { useAppState } from "../context/AppContext";
import { supportNote } from "../lib/languageSupport";

type Step = "grade" | "language" | "name";

export function Onboarding() {
  const navigate = useNavigate();
  const app = useAppState();
  const [step, setStep] = useState<Step>("grade");
  const [gradeBand, setGradeBandLocal] = useState<GradeBand | null>(app.gradeBand);
  const [languages, setLanguages] = useState<LanguageOption[] | null>(null);
  const [languageError, setLanguageError] = useState<string | null>(null);
  const [homeLanguage, setHomeLanguageLocal] = useState<string | null>(app.homeLanguage);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (step !== "language" || languages) return;
    let cancelled = false;
    getLanguages()
      .then((list) => {
        if (!cancelled) setLanguages(list);
      })
      .catch(() => {
        if (!cancelled) setLanguageError("Chorus couldn't load the language list. Please try again.");
      });
    return () => {
      cancelled = true;
    };
  }, [step, languages]);

  function chooseGradeBand(band: GradeBand) {
    setGradeBandLocal(band);
    app.setGradeBand(band);
    setStep("language");
  }

  function chooseLanguage(code: string) {
    setHomeLanguageLocal(code);
    app.setHomeLanguage(code);
  }

  async function finishWithName() {
    const trimmed = name.trim();
    if (!trimmed || !gradeBand || !homeLanguage) {
      navigate("/passages");
      return;
    }
    setSaving(true);
    setSaveError(null);
    try {
      const student = await createStudent({
        name: trimmed,
        grade_band: gradeBand,
        home_language: homeLanguage,
      });
      app.setStudent(student.id, student.name);
      navigate("/passages");
    } catch (err) {
      const message =
        err instanceof ApiRequestError ? err.message : "Couldn't save that name. You can still read without saving.";
      setSaveError(message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="page page--narrow stack stack--loose">
      {step === "grade" && (
        <section className="stack" aria-labelledby="grade-heading">
          <h1 id="grade-heading">Who's reading today?</h1>
          <button
            type="button"
            className="card-button"
            aria-pressed={gradeBand === "elementary"}
            onClick={() => chooseGradeBand("elementary")}
          >
            <strong>Grades 2–5</strong>
            <div className="muted">Elementary passages</div>
          </button>
          <button
            type="button"
            className="card-button"
            aria-pressed={gradeBand === "secondary"}
            onClick={() => chooseGradeBand("secondary")}
          >
            <strong>Grades 6–12</strong>
            <div className="muted">Secondary passages</div>
          </button>
        </section>
      )}

      {step === "language" && (
        <section className="stack" aria-labelledby="language-heading">
          <h1 id="language-heading">What language is spoken at home?</h1>
          <p className="muted">This helps Chorus tell an accent apart from a reading mistake.</p>
          {languageError && <p className="error-banner">{languageError}</p>}
          {!languages && !languageError && <p>Loading languages…</p>}
          {languages && (
            <div className="stack stack--tight">
              {languages.map((lang) => {
                const note = supportNote(lang.label, lang.support);
                const selected = homeLanguage === lang.code;
                return (
                  <button
                    key={lang.code}
                    type="button"
                    className="card-button"
                    aria-pressed={selected}
                    onClick={() => chooseLanguage(lang.code)}
                  >
                    <strong>{lang.label}</strong>
                    {note && <div className="muted">{note}</div>}
                  </button>
                );
              })}
            </div>
          )}
          <button
            type="button"
            className="btn btn-primary btn-block"
            disabled={!homeLanguage}
            onClick={() => setStep("name")}
          >
            Continue
          </button>
          <button type="button" className="btn btn-secondary btn-block" onClick={() => setStep("grade")}>
            Back
          </button>
        </section>
      )}

      {step === "name" && (
        <section className="stack" aria-labelledby="name-heading">
          <h1 id="name-heading">What's your first name or nickname?</h1>
          <p className="muted">Optional. A teacher can see your progress by this name. Skip if you'd rather not.</p>
          <label className="stack stack--tight">
            <span className="sr-only">First name or nickname</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Amina"
              style={{
                minHeight: "var(--touch-target)",
                fontSize: "1.1rem",
                padding: "0 var(--space-4)",
                borderRadius: "var(--radius-sm)",
                border: "2px solid var(--color-border)",
              }}
              maxLength={40}
            />
          </label>
          {saveError && <p className="error-banner">{saveError}</p>}
          <button type="button" className="btn btn-primary btn-block" disabled={saving} onClick={finishWithName}>
            {saving ? "Saving…" : name.trim() ? "Continue" : "Skip and continue"}
          </button>
          <button type="button" className="btn btn-secondary btn-block" onClick={() => setStep("language")}>
            Back
          </button>
        </section>
      )}
    </div>
  );
}
