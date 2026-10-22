import { useEffect, useState } from "react";
import type { AnalyzeResponse } from "../types/api";
import { getFeedback } from "../lib/api";

type State = { status: "loading" } | { status: "ready"; text: string } | { status: "failed" };

/** A short comment on the reading. Requested after the results are on screen; hidden quietly if it fails. */
export function Feedback({ analysis }: { analysis: AnalyzeResponse }) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    getFeedback({
      passage_id: analysis.passage_id,
      home_language: analysis.home_language,
      words: analysis.words,
      score: analysis.score,
      accent_adjusted: analysis.accent_adjusted,
    })
      .then((res) => {
        if (cancelled) return;
        const text = res.feedback?.trim();
        setState(text ? { status: "ready", text } : { status: "failed" });
      })
      .catch(() => {
        if (!cancelled) setState({ status: "failed" });
      });
    return () => {
      cancelled = true;
    };
  }, [analysis]);

  if (state.status === "failed") return null;

  return (
    <section className="section" aria-labelledby="feedback-title">
      <h2 className="section__title" id="feedback-title" style={{ padding: "0 16px" }}>
        Feedback
      </h2>
      <div className="group feedback" aria-busy={state.status === "loading"}>
        {state.status === "loading" ? (
          <div role="status" aria-label="Loading feedback">
            <span className="skel" style={{ width: "92%" }} />
            <span className="skel" style={{ width: "78%" }} />
            <span className="skel" style={{ width: "55%" }} />
          </div>
        ) : (
          <p>{state.text}</p>
        )}
      </div>
    </section>
  );
}
