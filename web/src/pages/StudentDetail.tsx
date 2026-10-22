import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import type { StudentDetailResponse } from "../types/api";
import { getStudent } from "../lib/api";
import { TrendChart } from "../components/TrendChart";
import { Screen } from "../components/Screen";
import { Icon } from "../components/Icon";
import { buildParentSummary } from "../lib/summary";
import { formatAccuracyPct, formatWcpm } from "../lib/format";

export function StudentDetail() {
  const { studentId } = useParams<{ studentId: string }>();
  const [detail, setDetail] = useState<StudentDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!studentId) return;
    let cancelled = false;
    getStudent(Number(studentId))
      .then((d) => {
        if (!cancelled) setDetail(d);
      })
      .catch(() => {
        if (!cancelled) setError("Chorus couldn't load that student's progress.");
      });
    return () => {
      cancelled = true;
    };
  }, [studentId]);

  const back = { label: "Students", to: "/teacher" };

  if (error) {
    return (
      <Screen title="Student" back={back}>
        <div className="notice notice--error" role="alert">
          <Icon name="warning" size={20} />
          <span>{error}</span>
        </div>
      </Screen>
    );
  }

  if (!detail) {
    return (
      <Screen title="Student" back={back}>
        <p className="footnote" role="status">
          Loading…
        </p>
      </Screen>
    );
  }

  const { student, sessions, most_missed } = detail;
  const hasAnyAccentAdjusted = sessions.some((s) => s.accent_adjusted !== null);
  const dates = sessions.map((s) => new Date(s.created_at).toLocaleDateString());

  return (
    <Screen title={student.name} large back={back}>
      <p className="lede" style={{ marginTop: -16, color: "var(--label)" }}>
        {buildParentSummary(student.name, sessions)}
      </p>

      {sessions.length === 0 ? (
        <p className="footnote">No sessions yet.</p>
      ) : (
        <>
          <section className="section" aria-labelledby="wcpm-title">
            <h2 className="section__title" id="wcpm-title" style={{ padding: "0 16px" }}>
              Words correct per minute, over time
            </h2>
            <div className="group chart">
              <TrendChart
                title="WCPM over time"
                series={[{ label: "WCPM", color: "var(--chart-1)", points: sessions.map((s) => Math.round(s.score.wcpm)) }]}
                xLabels={dates}
              />
            </div>
          </section>

          <section className="section" aria-labelledby="acc-title">
            <h2 className="section__title" id="acc-title" style={{ padding: "0 16px" }}>
              Accuracy, over time
            </h2>
            <div className="group chart">
              <TrendChart
                title="Accuracy over time"
                series={[
                  {
                    label: "Every difference counted",
                    color: "var(--chart-2)",
                    dashed: true,
                    points: sessions.map((s) => Math.round(s.score.accuracy * 100)),
                  },
                  ...(hasAnyAccentAdjusted
                    ? [
                        {
                          label: "Accent differences not counted",
                          color: "var(--chart-1)",
                          points: sessions.map((s) =>
                            s.accent_adjusted
                              ? Math.round(s.accent_adjusted.accuracy * 100)
                              : Math.round(s.score.accuracy * 100)
                          ),
                        },
                      ]
                    : []),
                ]}
                xLabels={dates}
                valueSuffix="%"
              />
            </div>
          </section>

          <section className="section" aria-labelledby="sessions-title">
            <h2 className="section__title" id="sessions-title" style={{ padding: "0 16px" }}>
              Sessions
            </h2>
            <ul className="group">
              {[...sessions].reverse().map((session) => (
                <li key={session.id}>
                  <div className="row">
                    <span className="row__body">
                      <span className="row__title row__title--strong">{session.passage_title}</span>
                      <span className="row__sub num">{new Date(session.created_at).toLocaleDateString()}</span>
                      <span className="row__sub">
                        Accent differences not counted as errors: <span className="num">{session.accent_ok_count}</span>
                      </span>
                    </span>
                    <span className="row__value">
                      <strong className="num">{formatAccuracyPct(session.score.accuracy)}</strong>
                      <span className="num">{formatWcpm(session.score.wcpm)} WCPM</span>
                    </span>
                  </div>
                </li>
              ))}
            </ul>
          </section>

          {most_missed.length > 0 && (
            <section className="section" aria-labelledby="missed-title">
              <h2 className="section__title" id="missed-title" style={{ padding: "0 16px" }}>
                Most-missed words
              </h2>
              <ul className="group">
                {most_missed.map((item) => (
                  <li key={item.word}>
                    <div className="row">
                      <span className="row__body">
                        <span className="row__title">{item.word}</span>
                      </span>
                      <span className="row__value">
                        missed {item.count} {item.count === 1 ? "time" : "times"}
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}

    </Screen>
  );
}
