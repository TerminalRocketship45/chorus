import { APP_NAME } from "../content/app";
import {
  CREDITS,
  LANGUAGE_RULE_STATUS,
  MEASURED_RESULT_CONFIG,
  MEASURED_RESULT_REJECTED_IDEA,
  MEASURED_RESULT_HEADLINE,
  MEASURED_RESULT_WHY_SMALL,
  PIPELINE_STEPS,
} from "../content/results";
import { useLocation, useNavigate } from "react-router-dom";
import { Screen } from "../components/Screen";

export function HowItWorks() {
  const navigate = useNavigate();
  const location = useLocation();
  // Return to wherever the reader came from; a direct visit goes home.
  const cameFromApp = location.key !== "default";
  return (
    <Screen title={`How ${APP_NAME} works`} large back={
        cameFromApp ? { label: "Back", onClick: () => navigate(-1) } : { label: "Home", to: "/" }
      }>
      <section className="section" aria-labelledby="pipeline-title">
        <h2 className="section__title" id="pipeline-title" style={{ padding: "0 16px" }}>
          The pipeline, in plain words
        </h2>
        <ol className="group steps-list">
          {PIPELINE_STEPS.map((step) => (
            <li key={step.title}>
              <strong>{step.title}.</strong> {step.text}
            </li>
          ))}
        </ol>
      </section>

      <section className="section" aria-labelledby="measured-title">
        <h2 className="section__title" id="measured-title" style={{ padding: "0 16px" }}>
          What we measured
        </h2>
        <div className="group prose">
          <p>{MEASURED_RESULT_HEADLINE}</p>
          <p>{MEASURED_RESULT_WHY_SMALL}</p>
          <p>{MEASURED_RESULT_CONFIG}</p>
          <p>{MEASURED_RESULT_REJECTED_IDEA}</p>
        </div>
      </section>

      <section className="section" aria-labelledby="status-title">
        <h2 className="section__title" id="status-title" style={{ padding: "0 16px" }}>
          What's measured and what isn't
        </h2>
        <ul className="group bullets">
          <li>{LANGUAGE_RULE_STATUS.measured}</li>
          <li>{LANGUAGE_RULE_STATUS.rulesNotMeasured}</li>
          <li>{LANGUAGE_RULE_STATUS.notYet}</li>
          <li>{LANGUAGE_RULE_STATUS.notDiagnostic}</li>
        </ul>
      </section>

      <section className="section" aria-labelledby="credits-title">
        <h2 className="section__title" id="credits-title" style={{ padding: "0 16px" }}>
          Credits
        </h2>
        <ul className="group bullets">
          {CREDITS.map((credit) => (
            <li key={credit.name}>
              <a href={credit.url} target="_blank" rel="noreferrer">
                {credit.name}
              </a>
              {" — "}
              {credit.detail}
            </li>
          ))}
        </ul>
      </section>
    </Screen>
  );
}
