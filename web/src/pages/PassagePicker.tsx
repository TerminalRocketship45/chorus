import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import type { Passage, PassageProgress } from "../types/api";
import { generatePassage, getPassages, getStudentPassages } from "../lib/api";
import { useAppState } from "../context/AppContext";
import { libraryRows, progressFor } from "../lib/history";
import { loadHistory } from "../lib/storage";
import { loadGenerated, rememberGenerated, saveGenerated, type StoredGenerated } from "../lib/generated";
import { MAX_TOPIC_LENGTH, normalizeTopic } from "../lib/topic";
import { formatAccuracyPct, formatPassageMeta, formatTopicMeta, formatWcpm } from "../lib/format";
import { ENABLE_GENERATION } from "../content/app";
import { Screen } from "../components/Screen";
import { Icon, Spinner } from "../components/Icon";

function PassageRow({
  row,
  fresh,
  generated,
  onOpen,
}: {
  row: PassageProgress;
  fresh: boolean;
  generated?: boolean;
  onOpen: (p: Passage) => void;
}) {
  const { passage, read, last_result } = row;
  return (
    <li>
      <button type="button" className={`row row--lead${fresh ? " row--new" : ""}`} onClick={() => onOpen(passage)}>
        <span className={`pmark ${read ? "pmark--read" : ""}`}>
          {read ? <Icon name="checkCircle" size={22} /> : <span className="pmark__dot" />}
          <span className="sr-only">{read ? "Read" : "Not read yet"}</span>
        </span>
        <span className="row__body">
          <span className="row__title row__title--strong">{passage.title}</span>
          <span className="row__sub">{generated
              ? formatTopicMeta(passage.topic, passage.word_count)
              : formatPassageMeta(passage.topic, passage.level, passage.word_count)}</span>
        </span>
        {read && last_result && (
          <span className="row__value">
            <strong className="num">{formatAccuracyPct(last_result.accuracy)}</strong>
            <span className="num">{formatWcpm(last_result.wcpm)} WCPM</span>
          </span>
        )}
        <span className="row__chev">
          <Icon name="chevronRight" size={18} strokeWidth={2.4} />
        </span>
      </button>
    </li>
  );
}

/** One short neutral line when a generate call fell back to the library, else null. */
export function fallbackNotice(passage: Passage): string | null {
  const reason = passage.fallback_reason ?? (passage.topic_accepted === false ? "topic_rejected" : null);
  if (!reason) return null;
  return reason === "topic_rejected"
    ? "Let's pick a different topic. Here's one from the library."
    : "Couldn't write a new passage right now. Here's one from the library.";
}

export function PassagePicker() {
  const navigate = useNavigate();
  const app = useAppState();
  const { gradeBand, studentId } = app;

  const [rows, setRows] = useState<PassageProgress[]>([]);
  const [library, setLibrary] = useState<Passage[] | null>(null);
  const [stored, setStored] = useState<StoredGenerated>(() => (ENABLE_GENERATION ? loadGenerated() : { passage: null, recent: [] }));
  const [topicInput, setTopicInput] = useState(app.topic);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [pendingTopic, setPendingTopic] = useState("");
  const [genError, setGenError] = useState<string | null>(null);
  const [fallback, setFallback] = useState<string | null>(null);
  const [freshId, setFreshId] = useState<string | null>(null);
  const [announce, setAnnounce] = useState("");
  const alive = useRef(true);

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);

  useEffect(() => {
    if (!gradeBand) {
      navigate("/onboarding");
      return;
    }
    let cancelled = false;
    const personal: Promise<PassageProgress[]> =
      studentId !== null
        ? getStudentPassages(studentId).catch(() => [] as PassageProgress[])
        : Promise.resolve([]);
    Promise.all([getPassages(gradeBand), personal])
      .then(([list, personalRows]) => {
        if (cancelled) return;
        setRows(personalRows);
        setLibrary(list.filter((p) => p.source !== "ai"));
        // Nothing saved on this device: a student's newest generated passage comes back from the server.
        setStored((cur) => {
          if (!ENABLE_GENERATION || cur.passage) return cur;
          const ai = personalRows.find((r) => r.passage.source === "ai");
          return ai ? rememberGenerated(cur, ai.passage) : cur;
        });
      })
      .catch(() => {
        if (!cancelled) setError("Chorus couldn't load passages. Please try again.");
      });
    return () => {
      cancelled = true;
    };
  }, [gradeBand, studentId, navigate]);

  const open = useCallback(
    (passage: Passage) => navigate(`/read/${passage.id}`, { state: { passage } }),
    [navigate]
  );

  async function newPassage(e?: FormEvent) {
    e?.preventDefault();
    if (!gradeBand || generating) return;
    const topic = normalizeTopic(topicInput);
    app.setTopic(topic);
    setTopicInput(topic);
    setPendingTopic(topic);
    setGenerating(true);
    setGenError(null);
    setFallback(null);
    setAnnounce(topic ? `Writing a passage about ${topic}…` : "Finding a passage for you…");
    try {
      const exclude = [...stored.recent, ...(library ?? []).map((p) => p.id)];
      const passage = await generatePassage({
        band: gradeBand,
        ...(topic ? { topic } : {}),
        student_id: studentId,
        exclude_ids: exclude,
      });
      if (!alive.current) return;
      const next = rememberGenerated(stored, passage);
      saveGenerated(next);
      setStored(next);
      setFreshId(passage.id);
      setFallback(fallbackNotice(passage));
      setAnnounce(`New passage ready: ${passage.title}`);
    } catch {
      if (!alive.current) return;
      setAnnounce("");
      setGenError("Chorus couldn't find a new passage just now. Please try again in a moment.");
    } finally {
      if (alive.current) setGenerating(false);
    }
  }

  const generated = ENABLE_GENERATION ? stored.passage : null;
  const history = studentId === null ? loadHistory() : null;
  const generatedRow = generated ? progressFor(generated, rows, history) : null;
  const libRows = library ? libraryRows(library, rows, history, generated?.id ?? null) : null;

  return (
    <Screen title="Passages" large back={{ label: "Home", to: "/" }}>
      {error && (
        <div className="notice notice--error" role="alert">
          <Icon name="warning" size={20} />
          <span>{error}</span>
        </div>
      )}

      {ENABLE_GENERATION && (
      <section className="section" aria-labelledby="gen-title">
        <div className="section__head">
          <h2 className="section__title" id="gen-title">
            Generated for you
          </h2>
        </div>
        <div className="group">
          {generating ? (
            <div className="row row--lead row--pending" role="status" aria-label="Writing a new passage">
              <span className="pmark">
                <Spinner size={20} />
              </span>
              <span className="row__body">
                <span className="row__title">{pendingTopic ? `Writing about ${pendingTopic}…` : "Finding a passage…"}</span>
                <span className="skel" style={{ width: "45%", height: 10 }} />
              </span>
            </div>
          ) : generatedRow ? (
            <ul className="group__list">
              <PassageRow row={generatedRow} fresh={generatedRow.passage.id === freshId} generated onOpen={open} />
            </ul>
          ) : null}
          <form className="topicbar" onSubmit={newPassage}>
            <label className="topicbar__label">
              <span className="sr-only">Topic for a new passage</span>
              <input
                className="field topicbar__field"
                type="text"
                value={topicInput}
                onChange={(e) => setTopicInput(e.target.value)}
                placeholder="Sharks, soccer, machine learning…"
                maxLength={MAX_TOPIC_LENGTH}
                autoComplete="off"
                enterKeyHint="go"
              />
            </label>
            <button type="submit" className="btn btn--tinted btn--compact" disabled={generating} aria-busy={generating}>
              {generating ? <Spinner size={18} /> : <Icon name="arrowClockwise" size={18} />}
              New passage
            </button>
          </form>
        </div>
        {!generating && fallback && (
          <p className="footnote" role="status">
            {fallback}
          </p>
        )}
        {genError && (
          <div className="notice notice--error" role="alert">
            <Icon name="warning" size={20} />
            <span>{genError}</span>
          </div>
        )}
        <div className="sr-only" role="status" aria-live="polite">
          {announce}
        </div>
      </section>
      )}

      {!libRows && !error && (
        <ul className="group" aria-label="Loading passages" role="status">
          {[0, 1, 2].map((i) => (
            <li key={i}>
              <div className="row row--pending" aria-hidden="true">
                <span className="pmark" />
                <span className="row__body">
                  <span className="skel" style={{ width: "55%" }} />
                  <span className="skel" style={{ width: "35%", height: 10 }} />
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}

      {libRows && libRows.length > 0 && (
        <section className="section" aria-labelledby="lib-title">
          <div className="section__head">
            <h2 className="section__title" id="lib-title">
              Library
            </h2>
          </div>
          <ul className="group">
            {libRows.map((row) => (
              <PassageRow key={row.passage.id} row={row} fresh={false} onOpen={open} />
            ))}
          </ul>
        </section>
      )}
      {libRows && libRows.length === 0 && <p className="footnote">No library passages yet for this grade band.</p>}

      <section className="section" aria-label="Reader">
        <div className="section__head">
          <h2 className="section__title">{app.studentName ? `Reading as ${app.studentName}` : "Reader"}</h2>
        </div>
        <div className="group">
          <button
            type="button"
            className="row row--danger"
            onClick={() => {
              app.switchReader();
              navigate("/onboarding");
            }}
          >
            <span className="row__body">
              <span className="row__title">Switch reader</span>
            </span>
          </button>
        </div>
      </section>
    </Screen>
  );
}
