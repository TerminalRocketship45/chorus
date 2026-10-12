import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { StudentDetailResponse } from "../types/api";
import { getStudent } from "../lib/api";
import { TrendChart } from "../components/TrendChart";
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

  if (error) {
    return (
      <div className="page stack">
        <p className="error-banner">{error}</p>
        <Link to="/teacher">Back to students</Link>
      </div>
    );
  }

  if (!detail) {
    return (
      <div className="page">
        <p>Loading…</p>
      </div>
    );
  }

  const { student, sessions, most_missed } = detail;
  const hasAnyAccentAdjusted = sessions.some((s) => s.accent_adjusted !== null);

  return (
    <div className="page page--wide stack stack--loose">
      <div className="stack stack--tight">
        <Link to="/teacher">&larr; All students</Link>
        <h1>{student.name}</h1>
        <p style={{ fontSize: "1.15rem" }}>{buildParentSummary(student.name, sessions)}</p>
      </div>

      {sessions.length === 0 ? (
        <p className="muted">No sessions yet.</p>
      ) : (
        <div className="stack">
          <div className="card">
            <h2 style={{ marginTop: 0 }}>Words correct per minute, over time</h2>
            <TrendChart
              title="WCPM over time"
              series={[{ label: "WCPM", color: "#2f6f4f", points: sessions.map((s) => Math.round(s.score.wcpm)) }]}
              xLabels={sessions.map((s) => new Date(s.created_at).toLocaleDateString())}
            />
          </div>

          <div className="card">
            <h2 style={{ marginTop: 0 }}>Accuracy, over time</h2>
            <TrendChart
              title="Accuracy over time"
              series={[
                {
                  label: "Every difference counted",
                  color: "#8a1f1f",
                  points: sessions.map((s) => Math.round(s.score.accuracy * 100)),
                },
                ...(hasAnyAccentAdjusted
                  ? [
                      {
                        label: "Accent differences not counted",
                        color: "#1f6b4d",
                        points: sessions.map((s) =>
                          s.accent_adjusted ? Math.round(s.accent_adjusted.accuracy * 100) : Math.round(s.score.accuracy * 100)
                        ),
                      },
                    ]
                  : []),
              ]}
              xLabels={sessions.map((s) => new Date(s.created_at).toLocaleDateString())}
              valueSuffix="%"
            />
          </div>

          <div className="card">
            <h2 style={{ marginTop: 0 }}>Sessions</h2>
            <table className="roster">
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Passage</th>
                  <th scope="col">WCPM</th>
                  <th scope="col">Accuracy</th>
                  <th scope="col">Accent differences not counted as errors</th>
                </tr>
              </thead>
              <tbody>
                {sessions.map((session) => (
                  <tr key={session.id} style={{ cursor: "default" }}>
                    <td>{new Date(session.created_at).toLocaleDateString()}</td>
                    <td>{session.passage_title}</td>
                    <td>{formatWcpm(session.score.wcpm)}</td>
                    <td>{formatAccuracyPct(session.score.accuracy)}</td>
                    <td>{session.accent_ok_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {most_missed.length > 0 && (
            <div className="card">
              <h2 style={{ marginTop: 0 }}>Most-missed words</h2>
              <ul>
                {most_missed.map((item) => (
                  <li key={item.word}>
                    {item.word} — missed {item.count} {item.count === 1 ? "time" : "times"}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
