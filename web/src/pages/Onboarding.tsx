import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { GradeBand, LanguageOption } from "../types/api";
import { createStudent, getLanguages, ApiRequestError } from "../lib/api";
import { useAppState } from "../context/AppContext";
import { FALLBACK_LANGUAGES, NATIVE_NAMES } from "../content/languages";
import { normalizeTopic, MAX_TOPIC_LENGTH } from "../lib/topic";
import { Screen } from "../components/Screen";
import { Icon } from "../components/Icon";

type Step = "grade" | "language" | "topic" | "name";
const ORDER: Step[] = ["grade", "language", "topic", "name"];

const BACK_LABEL: Record<Step, string> = {
  grade: "Home",
  language: "Grade",
  topic: "Language",
  name: "Topic",
};

export function Onboarding() {
  const navigate = useNavigate();
  const app = useAppState();
  const [step, setStep] = useState<Step>("grade");
  const [gradeBand, setGradeBandLocal] = useState<GradeBand | null>(app.gradeBand);
  const [languages, setLanguages] = useState<LanguageOption[]>(FALLBACK_LANGUAGES);
  const [homeLanguage, setHomeLanguageLocal] = useState<string | null>(app.homeLanguage);
  const [topic, setTopicLocal] = useState<string>(app.topic);
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Use the API's list when it arrives; the bundled list is already on screen.
  useEffect(() => {
    let cancelled = false;
    getLanguages()
      .then((list) => {
        if (!cancelled && list.length > 0) setLanguages(list);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

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

  function submitTopic() {
    app.setTopic(normalizeTopic(topic));
    setStep("name");
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
        onClick={() => setStep("topic")}
      >
        Continue
      </button>
    );
  } else if (step === "topic") {
    bottom = (
      <button type="button" className="btn btn--filled btn--block" onClick={submitTopic}>
        {normalizeTopic(topic) ? "Continue" : "Skip"}
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
    <Screen title="Get started" back={back} bottom={bottom} settings={false}>
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
                ["elementary", "Grades 2 to 5", "Elementary passages"],
                ["secondary", "Grades 6 to 12", "Secondary passages"],
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
          {(
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

      {step === "topic" && (
        <section className="section" aria-labelledby="topic-heading">
          <div className="title-block">
            <h1 className="large-title large-title--medium" id="topic-heading">
              What would you like to read about?
            </h1>
          </div>
          <form
            className="group"
            onSubmit={(e) => {
              e.preventDefault();
              submitTopic();
            }}
          >
            <label>
              <span className="sr-only">Topic</span>
              <input
                className="field"
                type="text"
                value={topic}
                onChange={(e) => setTopicLocal(e.target.value)}
                placeholder="Sharks, soccer, machine learning…"
                maxLength={MAX_TOPIC_LENGTH}
                autoComplete="off"
                enterKeyHint="next"
              />
            </label>
          </form>
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
