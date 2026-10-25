import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { StudentListItem } from "../types/api";
import { getStudents } from "../lib/api";
import { Screen } from "../components/Screen";
import { Icon } from "../components/Icon";
import { formatDate, formatHomeLanguage, formatWcpm, gradeBandLabel } from "../lib/format";

export function TeacherView() {
  const [students, setStudents] = useState<StudentListItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getStudents()
      .then((list) => {
        if (!cancelled) setStudents(list);
      })
      .catch(() => {
        if (!cancelled) setError("Chorus couldn't load the student list. Please try again.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <Screen title="Students" large back={{ label: "Home", to: "/" }}>
      {error && (
        <div className="notice notice--error" role="alert">
          <Icon name="warning" size={20} />
          <span>{error}</span>
        </div>
      )}
      {!students && !error && (
        <p className="footnote" role="status">
          Loading…
        </p>
      )}
      {students && students.length === 0 && <p className="footnote">No students yet.</p>}

      {students && students.length > 0 && (
        <ul className="group" aria-label="Students">
          {students.map((student) => (
            <li key={student.id}>
              <Link to={`/teacher/${student.id}`} className="row">
                <span className="row__body">
                  <span className="row__title row__title--strong">{student.name}</span>
                  <span className="row__sub">
                    {gradeBandLabel(student.grade_band)} · {formatHomeLanguage(student.home_language)}
                  </span>
                  <span className="row__sub num">
                    {student.session_count === 0
                      ? "No sessions yet"
                      : `${student.session_count} ${student.session_count === 1 ? "session" : "sessions"} · Last read ${formatDate(student.last_session_at)}`}
                  </span>
                </span>
                <span className="row__value">
                  <strong className="num">{student.last_wcpm === null ? "None" : formatWcpm(student.last_wcpm)}</strong>
                  <span>Last WCPM</span>
                </span>
                <span className="row__chev">
                  <Icon name="chevronRight" size={18} strokeWidth={2.4} />
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Screen>
  );
}
