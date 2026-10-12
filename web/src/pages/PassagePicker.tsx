import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { Passage } from "../types/api";
import { getPassages } from "../lib/api";
import { useAppState } from "../context/AppContext";

export function PassagePicker() {
  const navigate = useNavigate();
  const app = useAppState();
  const [passages, setPassages] = useState<Passage[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!app.gradeBand) {
      navigate("/onboarding");
      return;
    }
    let cancelled = false;
    getPassages(app.gradeBand)
      .then((list) => {
        if (!cancelled) setPassages(list);
      })
      .catch(() => {
        if (!cancelled) setError("Chorus couldn't load passages. Please try again.");
      });
    return () => {
      cancelled = true;
    };
  }, [app.gradeBand, navigate]);

  return (
    <div className="page stack">
      <div className="stack stack--tight">
        <h1>Pick a passage</h1>
        {app.studentName && <p className="muted">Reading as {app.studentName}.</p>}
      </div>

      {error && <p className="error-banner">{error}</p>}
      {!passages && !error && <p>Loading passages…</p>}

      {passages && passages.length === 0 && <p className="muted">No passages yet for this grade band.</p>}

      {passages && passages.length > 0 && (
        <div className="stack">
          {passages.map((passage) => (
            <button
              key={passage.id}
              type="button"
              className="card-button"
              onClick={() => navigate(`/read/${passage.id}`)}
            >
              <strong style={{ fontSize: "1.1rem" }}>{passage.title}</strong>
              <div className="muted">
                {passage.topic} · Level {passage.level} · {passage.word_count} words
              </div>
            </button>
          ))}
        </div>
      )}

      <button
        type="button"
        className="btn btn-secondary"
        onClick={() => {
          app.switchReader();
          navigate("/onboarding");
        }}
      >
        Switch reader
      </button>
    </div>
  );
}
