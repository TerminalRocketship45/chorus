import { APP_NAME } from "../content/app";
import {
  CREDITS,
  LANGUAGE_RULE_STATUS,
  MEASURED_RESULT,
  MEASURED_RESULT_HEADLINE,
  MEASURED_RESULT_WHY_SMALL,
  PIPELINE_STEPS,
} from "../content/results";

export function HowItWorks() {
  return (
    <div className="page stack stack--loose">
      <h1>How {APP_NAME} works</h1>

      <section className="stack">
        <h2>The pipeline, in plain words</h2>
        <ol className="stack">
          {PIPELINE_STEPS.map((step) => (
            <li key={step.title}>
              <strong>{step.title}.</strong> {step.text}
            </li>
          ))}
        </ol>
      </section>

      <section className="stack card">
        <h2 style={{ marginTop: 0 }}>What we measured</h2>
        <p>{MEASURED_RESULT_HEADLINE}</p>
        <p className="muted">{MEASURED_RESULT_WHY_SMALL}</p>
        <p className="muted">
          Sample: {MEASURED_RESULT.corpusUtterances} utterances ({MEASURED_RESULT.corpusWords} words) from the{" "}
          {MEASURED_RESULT.corpusName} corpus, {MEASURED_RESULT.language}-L1 speakers, speech recognition model{" "}
          {MEASURED_RESULT.asrModel} running on {MEASURED_RESULT.device}.
        </p>
      </section>

      <section className="stack">
        <h2>What's measured and what isn't</h2>
        <ul className="stack stack--tight">
          <li>{LANGUAGE_RULE_STATUS.measured}</li>
          <li>{LANGUAGE_RULE_STATUS.rulesNotMeasured}</li>
          <li>{LANGUAGE_RULE_STATUS.notYet}</li>
          <li>{LANGUAGE_RULE_STATUS.notDiagnostic}</li>
        </ul>
      </section>

      <section className="stack">
        <h2>Credits</h2>
        <ul className="stack stack--tight">
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
    </div>
  );
}
