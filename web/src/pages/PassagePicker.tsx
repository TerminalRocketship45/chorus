import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { Passage, PassageProgress } from "../types/api";
import { generatePassage, getPassages, getStudentPassages, ApiRequestError } from "../lib/api";
import { useAppState } from "../context/AppContext";
import {
  buildSections,
  collectExcludeIds,
  prependPassage,
  progressForPassage,
  rememberLocalPassage,
} from "../lib/history";
import { loadHistory, loadLocalPassages, saveLocalPassages } from "../lib/storage";
import { formatAccuracyPct, formatPassageMeta, formatWcpm } from "../lib/format";
import { Screen } from "../components/Screen";
import { Icon, Spinner } from "../components/Icon";

function PassageRow({ row, fresh, onOpen }: { row: PassageProgress; fresh: boolean; onOpen: (p: Passage) => void }) {
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
          <span className="row__sub">{formatPassageMeta(passage.topic, passage.level, passage.word_count)}</span>
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

export function PassagePicker() {
  const navigate = useNavigate();
  const app = useAppState();
  const { gradeBand, studentId, interests } = app;

  const [mine, setMine] = useState<PassageProgress[] | null>(null);
  const [library, setLibrary] = useState<PassageProgress[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState<string | null>(null);
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
    const history = loadHistory();
    const personal: Promise<PassageProgress[]> =
      studentId !== null
        ? getStudentPassages(studentId).catch(() => [] as PassageProgress[])
        : Promise.resolve(loadLocalPassages().map((p) => progressForPassage(p, history)));
    Promise.all([getPassages(gradeBand), personal])
      .then(([list, rows]) => {
        if (cancelled) return;
        const sections = buildSections(rows, list, studentId === null ? history : null);
        setMine(sections.mine);
        setLibrary(sections.library);
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

  async function newPassage() {
    if (!gradeBand || generating) return;
    if (interests.length === 0) {
      navigate("/interests");
      return;
    }
    setGenerating(true);
    setGenError(null);
    setAnnounce("Finding a new passage for you…");
    try {
      const excludeIds = collectExcludeIds(
        (mine ?? []).map((r) => r.passage),
        (library ?? []).map((r) => r.passage)
      );
      const passage = await generatePassage({
        band: gradeBand,
        interests,
        student_id: studentId,
        exclude_ids: excludeIds,
      });
      if (!alive.current) return;
      if (studentId === null) saveLocalPassages(rememberLocalPassage(loadLocalPassages(), passage));
      setMine((rows) => prependPassage(rows ?? [], passage));
      setLibrary((rows) => (rows ?? []).filter((r) => r.passage.id !== passage.id));
      setFreshId(passage.id);
      setAnnounce(`New passage added: ${passage.title}`);
    } catch (err) {
      if (!alive.current) return;
      setAnnounce("");
      if (err instanceof ApiRequestError && err.status === 400) {
        setGenError("Chorus couldn't use those interests. Try choosing them again.");
      } else {
        setGenError("Chorus couldn't find a new passage just now. Please try again in a moment.");
      }
    } finally {
      if (alive.current) setGenerating(false);
    }
  }

  const loading = !mine && !error;

  return (
    <Screen
      title="Passages"
      large
      back={{ label: "Home", to: "/" }}
      trailing={
        <Link to="/interests" className="navbtn" aria-label="Edit interests">
          <Icon name="tag" size={22} />
        </Link>
      }
    >
      {error && (
        <div className="notice notice--error" role="alert">
          <Icon name="warning" size={20} />
          <span>{error}</span>
        </div>
      )}

      {loading && (
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

      {mine && library && (
        <>
          <section className="section" aria-labelledby="mine-title">
            <div className="section__head">
              <h2 className="section__title" id="mine-title">
                Your passages
              </h2>
              <button
                type="button"
                className="btn btn--tinted btn--compact"
                onClick={newPassage}
                disabled={generating}
                aria-busy={generating}
              >
                {generating ? <Spinner size={18} /> : <Icon name="arrowClockwise" size={18} />}
                New passage
              </button>
            </div>

            {genError && (
              <div className="notice notice--error" role="alert">
                <Icon name="warning" size={20} />
                <span>{genError}</span>
              </div>
            )}

            {(generating || mine.length > 0) && (
              <ul className="group">
                {generating && (
                  <li>
                    <div className="row row--lead row--pending" aria-hidden="true">
                      <span className="pmark">
                        <Spinner size={20} />
                      </span>
                      <span className="row__body">
                        <span className="row__title">Finding a new passage…</span>
                        <span className="skel" style={{ width: "45%", height: 10 }} />
                      </span>
                    </div>
                  </li>
                )}
                {mine.map((row) => (
                  <PassageRow key={row.passage.id} row={row} fresh={row.passage.id === freshId} onOpen={open} />
                ))}
              </ul>
            )}

            {!generating && mine.length === 0 && (
              <p className="footnote">
                {interests.length > 0
                  ? "Tap New passage and Chorus will find one about the things you like. Ask again until you find one you like."
                  : "Choose some interests, then tap New passage."}
              </p>
            )}
            <div className="sr-only" role="status" aria-live="polite">
              {announce}
            </div>
          </section>

          {library.length > 0 && (
            <section className="section" aria-labelledby="lib-title">
              <div className="section__head">
                <h2 className="section__title" id="lib-title">
                  Library
                </h2>
              </div>
              <ul className="group">
                {library.map((row) => (
                  <PassageRow key={row.passage.id} row={row} fresh={false} onOpen={open} />
                ))}
              </ul>
            </section>
          )}
          {library.length === 0 && mine.length === 0 && !generating && (
            <p className="footnote">No library passages yet for this grade band.</p>
          )}
        </>
      )}

      <section className="section" aria-label="Reader">
        <div className="section__head">
          <h2 className="section__title">{app.studentName ? `Reading as ${app.studentName}` : "Reader"}</h2>
        </div>
        <div className="group">
          <Link to="/interests" className="row">
            <span className="row__body">
              <span className="row__title">Interests</span>
            </span>
            <span className="row__value">
              {interests.length > 0 ? `${interests.length} chosen` : "None yet"}
            </span>
            <span className="row__chev">
              <Icon name="chevronRight" size={18} strokeWidth={2.4} />
            </span>
          </Link>
          <Link to="/how-it-works" className="row">
            <span className="row__body">
              <span className="row__title">How Chorus works</span>
            </span>
            <span className="row__chev">
              <Icon name="chevronRight" size={18} strokeWidth={2.4} />
            </span>
          </Link>
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
