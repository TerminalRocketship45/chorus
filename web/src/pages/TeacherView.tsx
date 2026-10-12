import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { StudentListItem } from "../types/api";
import { getStudents } from "../lib/api";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return "—";
  }
}

export function TeacherView() {
  const navigate = useNavigate();
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
    <div className="page page--wide stack">
      <div className="stack stack--tight">
        <h1>Students</h1>
        <p className="note">
          Demo: anyone with the link can see this list. Use first names or nicknames only.
        </p>
      </div>

      {error && <p className="error-banner">{error}</p>}
      {!students && !error && <p>Loading…</p>}
      {students && students.length === 0 && <p className="muted">No students yet.</p>}

      {students && students.length > 0 && (
        <table className="roster" aria-label="Students">
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Grade band</th>
              <th scope="col">Home language</th>
              <th scope="col">Sessions</th>
              <th scope="col">Last read</th>
              <th scope="col">Last WCPM</th>
            </tr>
          </thead>
          <tbody>
            {students.map((student) => (
              <tr
                key={student.id}
                tabIndex={0}
                onClick={() => navigate(`/teacher/${student.id}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") navigate(`/teacher/${student.id}`);
                }}
              >
                <td>{student.name}</td>
                <td>{student.grade_band === "elementary" ? "Grades 2–5" : "Grades 6–12"}</td>
                <td>{student.home_language}</td>
                <td>{student.session_count}</td>
                <td>{formatDate(student.last_session_at)}</td>
                <td>{student.last_wcpm ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
