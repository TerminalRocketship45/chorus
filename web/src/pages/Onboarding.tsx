import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { GradeBand, Interest, LanguageOption } from "../types/api";
import { createStudent, getInterests, getLanguages, ApiRequestError } from "../lib/api";
import { useAppState } from "../context/AppContext";
import { NATIVE_NAMES } from "../content/languages";
import { Screen } from "../components/Screen";
import { Icon } from "../components/Icon";

type Step = "grade" | "language" | "interests" | "name";
const ORDER: Step[] = ["grade", "language", "interests", "name"];

const BACK_LABEL: Record<Step, string> = {
  grade: "Home",
  language: "Grade",
  interests: "Language",
  name: "Interests",
};

export function Onboarding() {
  const navigate = useNavigate();
  const app = useAppState();
  const [step, setStep] = useState<Step>("grade");
  const [gradeBand, setGradeBandLocal] = useState<GradeBand | null>(app.gradeBand);
  const [languages, setLanguages] = useState<LanguageOption[] | null>(null);
  const [languageError, setLanguageError] = useState<string | null>(null);
  const [homeLanguage, setHomeLanguageLocal] = useState<string | null>(app.homeLanguage);
  const [interestList, setInterestList] = useState<Interest[] | null>(null);
  const [interestError, setInterestError] = useState<string | null>(null);
  const [interests, setInterestsLocal] = useState<string[]>(app.interests);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    if (step !== "language" || languages) return;
    let cancelled = false;
    setLanguageError(null);
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
  }, [step, languages, retry]);

  useEffect(() => {
    if (step !== "interests" || interestList) return;
    let cancelled = false;
    setInterestError(null);
    getInterests()
      .then((list) => {
        if (!cancelled) setInterestList(list);
      })
      .catch(() => {
        if (!cancelled) setInterestError("Chorus couldn't load the interests list. Please try again.");
      });
    return () => {
      cancelled = true;
    };
  }, [step, interestList, retry]);

  function goBack() {
    const i = ORDER.indexOf(step);
    if (i > 0) setStep(ORDER[i - 1]);
  }

  function chooseGradeBand(band: GradeBand) {
    setGradeBandLocal(band);
    app.setGradeBand(band);
  }

  function chooseLanguage(code: string) {
    setHomeLanguageLocal(code);
    app.setHomeLanguage(code);
  }

  function toggleInterest(code: string) {
    const next = interests.includes(code) ? interests.filter((c) => c !== code) : [...interests, code];
    setInterestsLocal(next);
    app.setInterests(next);
  }

  async function finishWithName() {
    const trimmed = name.trim();
    app.setInterests(interests);
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
        interests,
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

  const stepIndex = ORDER.indexOf(step);
  const back =
    step === "grade"
      ? { label: BACK_LABEL.grade, to: "/" }
      : { label: BACK_LABEL[step], onClick: goBack };

  const progress = (
    <div className="steps" role="img" aria-label={`Step ${stepIndex + 1} of ${ORDER.length}`}>
      {ORDER.map((s, i) => (
        <span key={s} className="steps__dot" data-done={i <= stepIndex} />
      ))}
    </div>
  );

  let bottom;
  if (step === "grade") {
    bottom = (
      <button
        type="button"
        className="btn btn--filled btn--block"
        disabled={!gradeBand}
        onClick={() => setStep("language")}
      >
        Continue
      </button>
    );
  } else if (step === "language") {
    bottom = (
      <button
        type="button"
        className="btn btn--filled btn--block"
        disabled={!homeLanguage}
        onClick={() => setStep("interests")}
      >
        Continue
      </button>
    );
  } else if (step === "interests") {
    bottom = (
      <button
        type="button"
        className="btn btn--filled btn--block"
        disabled={interests.length === 0}
        onClick={() => setStep("name")}
      >
        Continue
      </button>
    );
  } else {
    bottom = (
      <button type="button" className="btn btn--filled btn--block" disabled={saving} onClick={finishWithName}>
        {saving ? "Saving…" : name.trim() ? "Continue" : "Skip and continue"}
      </button>
    );
  }

  return (
    <Screen title="Get started" back={back} bottom={bottom}>
      {progress}

      {step === "grade" && (
        <section className="section" aria-labelledby="grade-heading">
          <div className="title-block">
            <h1 className="large-title large-title--medium" id="grade-heading">
              Who's reading today?
            </h1>
          </div>
          <div className="group" role="radiogroup" aria-labelledby="grade-heading">
            {(
              [
                ["elementary", "Grades 2–5", "Elementary passages"],
                ["secondary", "Grades 6–12", "Secondary passages"],
              ] as const
            ).map(([band, title, sub]) => (
              <button
                key={band}
                type="button"
                role="radio"
                aria-checked={gradeBand === band}
                className="row"
                onClick={() => chooseGradeBand(band)}
              >
                <span className="row__body">
                  <span className="row__title">{title}</span>
                  <span className="row__sub">{sub}</span>
                </span>
                <span className="row__check">{gradeBand === band && <Icon name="check" size={22} strokeWidth={2.6} />}</span>
              </button>
            ))}
          </div>
        </section>
      )}

      {step === "language" && (
        <section className="section" aria-labelledby="language-heading">
          <div className="title-block">
            <h1 className="large-title large-title--medium" id="language-heading">
              What language is spoken at home?
            </h1>
            <p className="lede">This helps Chorus tell an accent apart from a reading mistake.</p>
          </div>
          {languageError && (
            <div className="notice notice--error" role="alert">
              <Icon name="warning" size={20} />
              <div className="notice__body">
                <span>{languageError}</span>
                <button type="button" className="btn btn--plain" style={{ minHeight: 32, padding: 0 }} onClick={() => setRetry((n) => n + 1)}>
                  Try again
                </button>
              </div>
            </div>
          )}
          {!languages && !languageError && (
            <p className="footnote" role="status">
              Loading languages…
            </p>
          )}
          {languages && (
            <div className="group" role="radiogroup" aria-labelledby="language-heading">
              {languages.map((lang) => {
                const selected = homeLanguage === lang.code;
                const native = NATIVE_NAMES[lang.code];
                return (
                  <button
                    key={lang.code}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    className="row"
                    onClick={() => chooseLanguage(lang.code)}
                  >
                    <span className="row__body">
                      <span className="row__title">{lang.label}</span>
                    </span>
                    {native && (
                      <span className="row__native">
                        {native}
                      </span>
                    )}
                    <span className="row__check">{selected && <Icon name="check" size={22} strokeWidth={2.6} />}</span>
                  </button>
                );
              })}
            </div>
          )}
        </section>
      )}

      {step === "interests" && (
        <section className="section" aria-labelledby="interests-heading">
          <div className="title-block">
            <h1 className="large-title large-title--medium" id="interests-heading">
              What do you like to read about?
            </h1>
            <p className="lede">Pick one or more. Chorus writes passages about the things you choose.</p>
          </div>
          {interestError && (
            <div className="notice notice--error" role="alert">
              <Icon name="warning" size={20} />
              <div className="notice__body">
                <span>{interestError}</span>
                <button type="button" className="btn btn--plain" style={{ minHeight: 32, padding: 0 }} onClick={() => setRetry((n) => n + 1)}>
                  Try again
                </button>
              </div>
            </div>
          )}
          {!interestList && !interestError && (
            <p className="footnote" role="status">
              Loading…
            </p>
          )}
          {interestList && (
            <div className="chips" role="group" aria-labelledby="interests-heading">
              {interestList.map((item) => (
                <button
                  key={item.code}
                  type="button"
                  className="chip"
                  aria-pressed={interests.includes(item.code)}
                  onClick={() => toggleInterest(item.code)}
                >
                  {interests.includes(item.code) && <Icon name="check" size={16} strokeWidth={3} />}
                  {item.label}
                </button>
              ))}
            </div>
          )}
        </section>
      )}

      {step === "name" && (
        <section className="section" aria-labelledby="name-heading">
          <div className="title-block">
            <h1 className="large-title large-title--medium" id="name-heading">
              What's your first name or nickname?
            </h1>
            <p className="lede">Optional. A teacher can see your progress by this name. Skip if you'd rather not.</p>
          </div>
          <div className="group">
            <label>
              <span className="sr-only">First name or nickname</span>
              <input
                className="field"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Amina"
                maxLength={40}
                autoComplete="off"
                autoCapitalize="words"
                enterKeyHint="done"
              />
            </label>
          </div>
          {saveError && (
            <div className="notice notice--error" role="alert">
              <Icon name="warning" size={20} />
              <span>{saveError}</span>
            </div>
          )}
        </section>
      )}
    </Screen>
  );
}
