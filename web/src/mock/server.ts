/**
 * Dev-only fixture server for `/api/*`, used when VITE_MOCK=1 (see
 * vite.config.ts). Runs inside the Vite dev server (Node), never in the
 * browser bundle, and never in `vite build`. It exists only because the
 * FastAPI backend (docs/api.md) isn't built yet.
 */
import type { IncomingMessage, ServerResponse } from "node:http";
import {
  MOCK_ANALYZE_NO_ACCENT,
  MOCK_ANALYZE_STOPPED_EARLY,
  MOCK_TOPIC_TEXT,
  MOCK_ANALYZE_WITH_ACCENT,
  MOCK_LANGUAGES,
  MOCK_PASSAGES,
  MOCK_STUDENTS,
  MOCK_STUDENT_DETAILS,
} from "./fixtures";
import type { GradeBand, Passage, PassageProgress, Student } from "../types/api";

let nextStudentId = 1000;
let nextGeneratedId = 1;
let generateCalls = 0;

/** Passages written so far (any student or none), so GET /api/passages/g-N works. */
const generated = new Map<string, Passage>();
/** Per-student passage progress, newest first, for GET /api/students/{id}/passages. */
const studentRows = new Map<number, PassageProgress[]>();
/** Students created or patched during this dev session. */
const liveStudents = new Map<number, Student>();

const BLOCKED_TOPICS = /\b(gun|guns|weapon|weapons|bomb|drugs)\b/i;

function findPassage(id: string): Passage | undefined {
  return MOCK_PASSAGES.find((p) => p.id === id) ?? generated.get(id);
}

function findStudent(id: number): Student | undefined {
  return liveStudents.get(id) ?? MOCK_STUDENTS.find((s) => s.id === id);
}

function rowsFor(id: number): PassageProgress[] {
  let rows = studentRows.get(id);
  if (!rows) {
    rows = [];
    const detail = MOCK_STUDENT_DETAILS[id];
    if (detail) {
      // Seed from the fixture sessions: newest first, one row per passage.
      for (const session of [...detail.sessions].reverse()) {
        const passage = findPassage(session.passage_id);
        if (!passage || rows.some((r) => r.passage.id === passage.id)) continue;
        const attempts = detail.sessions.filter((x) => x.passage_id === passage.id).length;
        rows.push({
          passage,
          read: true,
          attempts,
          last_result: {
            accuracy: session.score.accuracy,
            accent_adjusted_accuracy: session.accent_adjusted ? session.accent_adjusted.accuracy : null,
            wcpm: session.score.wcpm,
            at: session.created_at,
          },
        });
      }
    }
    studentRows.set(id, rows);
  }
  return rows;
}

function sendJson(res: ServerResponse, status: number, body: unknown): void {
  const text = JSON.stringify(body);
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json");
  res.end(text);
}

function readBody(req: IncomingMessage): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("data", (chunk) => chunks.push(chunk as Buffer));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

/** Pulls one field's value out of a multipart/form-data body (mock-only; not a real parser). */
function extractMultipartField(raw: string, field: string): string | null {
  const re = new RegExp(`name="${field}"\\r\\n\\r\\n([^\\r\\n]*)`, "i");
  const match = raw.match(re);
  return match ? match[1] : null;
}

export async function handleMockRequest(
  req: IncomingMessage,
  res: ServerResponse
): Promise<boolean> {
  const method = (req.method ?? "GET").toUpperCase();
  const url = new URL(req.url ?? "/", "http://localhost");
  const path = url.pathname;

  if (method === "GET" && path === "/api/health") {
    sendJson(res, 200, { status: "ok" });
    return true;
  }

  if (method === "GET" && path === "/api/languages") {
    sendJson(res, 200, MOCK_LANGUAGES);
    return true;
  }

  if (method === "GET" && path === "/api/passages") {
    const band = url.searchParams.get("band") as GradeBand | null;
    const passages = band ? MOCK_PASSAGES.filter((p) => p.band === band) : MOCK_PASSAGES;
    sendJson(res, 200, passages);
    return true;
  }

  if (method === "GET" && /^\/api\/passages\/[^/]+$/.test(path)) {
    const id = decodeURIComponent(path.slice("/api/passages/".length));
    const found = findPassage(id);
    if (!found) {
      sendJson(res, 404, { detail: `unknown passage_id: '${id}'` });
      return true;
    }
    sendJson(res, 200, found);
    return true;
  }

  if (method === "POST" && path === "/api/passages/generate") {
    const raw = await readBody(req);
    let body: { band?: string; topic?: string; student_id?: number | null; exclude_ids?: string[] } = {};
    try {
      body = JSON.parse(raw.toString("utf-8"));
    } catch {
      sendJson(res, 400, { detail: "Body must be JSON." });
      return true;
    }
    if (body.band !== "elementary" && body.band !== "secondary") {
      sendJson(res, 400, { detail: `unknown band: '${String(body.band)}'` });
      return true;
    }
    const topic = (body.topic ?? "").trim().slice(0, 80);
    const exclude = new Set(body.exclude_ids ?? []);
    await new Promise((resolve) => setTimeout(resolve, 2000));
    let passage: Passage | null = null;

    // Unsafe or unusable topics never error: the reader gets a library passage.
    const accepted = !BLOCKED_TOPICS.test(topic);
    // Alternate: a written passage, then a no_token fallback (the server's reason codes: docs/api.md).
    const forcedFallback = accepted && generateCalls++ % 2 === 1;
    if (!accepted || forcedFallback) {
      const candidates = MOCK_PASSAGES.filter((p) => p.band === body.band && !exclude.has(p.id));
      const pick = candidates[0] ?? MOCK_PASSAGES.find((p) => p.band === body.band)!;
      passage = {
        ...pick,
        requested_topic: topic,
        topic_accepted: accepted,
        fallback_reason: accepted ? "no_token" : "topic_rejected",
      };
    } else {
      const label = topic || "animals";
      const id = `g-${nextGeneratedId++}`;
      const text = `${MOCK_TOPIC_TEXT[(nextGeneratedId - 1) % MOCK_TOPIC_TEXT.length].replace(/\{t\}/g, label)}`;
      passage = {
        id,
        title: `All About ${label.charAt(0).toUpperCase() + label.slice(1)}`,
        band: body.band,
        level: 2,
        topic: label,
        word_count: text.split(/\s+/).length,
        text,
        source: "ai",
        requested_topic: topic || null,
        topic_accepted: true,
        fallback_reason: null,
      };
      generated.set(id, passage);
    }
    if (typeof body.student_id === "number") {
      const rows = rowsFor(body.student_id);
      if (!rows.some((r) => r.passage.id === passage!.id)) {
        rows.unshift({ passage, read: false, attempts: 0, last_result: null });
      }
    }
    sendJson(res, 201, passage);
    return true;
  }

  if (method === "POST" && path === "/api/feedback") {
    await readBody(req);
    await new Promise((resolve) => setTimeout(resolve, 1500));
    sendJson(res, 200, {
      feedback:
        "Nice work getting through the whole passage. You read about 46 words correctly in a minute, and the middle of the passage was steady. Give the word brown another try, then read it once more.",
      source: "template",
    });
    return true;
  }

  if (method === "GET" && path === "/api/students") {
    const created = [...liveStudents.values()].filter((s) => !MOCK_STUDENTS.some((m) => m.id === s.id));
    sendJson(res, 200, [
      ...MOCK_STUDENTS.map((m) => ({ ...m, ...(liveStudents.get(m.id) ?? {}) })),
      ...created.map((s) => ({ ...s, session_count: 0, last_session_at: null, last_wcpm: null })),
    ]);
    return true;
  }

  if (method === "GET" && /^\/api\/students\/\d+\/passages$/.test(path)) {
    const id = Number(path.split("/")[3]);
    if (!findStudent(id)) {
      sendJson(res, 404, { detail: "Student not found." });
      return true;
    }
    sendJson(res, 200, rowsFor(id));
    return true;
  }

  if (method === "PATCH" && /^\/api\/students\/\d+$/.test(path)) {
    const id = Number(path.split("/").pop());
    const current = findStudent(id);
    if (!current) {
      sendJson(res, 404, { detail: "Student not found." });
      return true;
    }
    const raw = await readBody(req);
    let patch: Partial<Student> = {};
    try {
      patch = JSON.parse(raw.toString("utf-8"));
    } catch {
      sendJson(res, 400, { detail: "Body must be JSON." });
      return true;
    }
    const updated: Student = {
      ...current,
      ...(patch.name !== undefined ? { name: patch.name } : {}),
      ...(patch.grade_band !== undefined ? { grade_band: patch.grade_band } : {}),
      ...(patch.home_language !== undefined ? { home_language: patch.home_language } : {}),
    };
    liveStudents.set(id, updated);
    sendJson(res, 200, updated);
    return true;
  }

  if (method === "GET" && /^\/api\/students\/\d+$/.test(path)) {
    const id = Number(path.split("/").pop());
    const detail = MOCK_STUDENT_DETAILS[id];
    const live = liveStudents.get(id);
    if (!detail && !live) {
      sendJson(res, 404, { detail: "Student not found." });
      return true;
    }
    sendJson(
      res,
      200,
      detail
        ? { ...detail, student: live ?? detail.student }
        : { student: live, sessions: [], most_missed: [] }
    );
    return true;
  }

  if (method === "POST" && path === "/api/students") {
    const raw = await readBody(req);
    let payload: { name?: string; grade_band?: GradeBand; home_language?: string} = {};
    try {
      payload = JSON.parse(raw.toString("utf-8"));
    } catch {
      sendJson(res, 400, { detail: "Body must be JSON." });
      return true;
    }
    if (!payload.name || !payload.grade_band || !payload.home_language) {
      sendJson(res, 400, { detail: "name, grade_band and home_language are required." });
      return true;
    }
    const student: Student = {
      id: nextStudentId++,
      name: payload.name,
      grade_band: payload.grade_band,
      home_language: payload.home_language,
      interests: [],
      created_at: new Date().toISOString(),
    };
    liveStudents.set(student.id, student);
    sendJson(res, 201, student);
    return true;
  }

  if (method === "POST" && path === "/api/analyze") {
    const raw = await readBody(req);
    const text = raw.toString("latin1");
    const passageId = extractMultipartField(text, "passage_id");
    const homeLanguage = extractMultipartField(text, "home_language");
    const studentId = extractMultipartField(text, "student_id");

    // Simulate the error responses the real service can give, for manual
    // testing: pass a passage_id of "mock-413" / "mock-422" / "mock-503".
    if (passageId === "mock-413") {
      sendJson(res, 413, { detail: "That recording is too long or too large." });
      return true;
    }
    if (passageId === "mock-422") {
      sendJson(res, 422, { detail: "Chorus couldn't make out any speech in that recording." });
      return true;
    }
    if (passageId === "mock-503") {
      sendJson(res, 503, { detail: "Chorus is busy right now. Please try again in a moment." });
      return true;
    }

    await new Promise((resolve) => setTimeout(resolve, 400));
    if (passageId === "mock-early") {
      sendJson(res, 200, { ...MOCK_ANALYZE_STOPPED_EARLY, session_id: null });
      return true;
    }
    if (studentId && passageId) {
      const sid = Number(studentId);
      const passage = findPassage(passageId);
      if (passage) {
        const rows = rowsFor(sid);
        const f = homeLanguage === "english" ? MOCK_ANALYZE_NO_ACCENT : MOCK_ANALYZE_WITH_ACCENT;
        const prev = rows.find((r) => r.passage.id === passage.id);
        const entry: PassageProgress = {
          passage,
          read: true,
          attempts: (prev?.attempts ?? 0) + 1,
          last_result: {
            accuracy: f.score.accuracy,
            accent_adjusted_accuracy: f.accent_adjusted ? f.accent_adjusted.accuracy : null,
            wcpm: f.score.wcpm,
            at: new Date().toISOString(),
          },
        };
        studentRows.set(sid, [entry, ...rows.filter((r) => r.passage.id !== passage.id)]);
      }
    }
    const fixture = homeLanguage === "english" ? MOCK_ANALYZE_NO_ACCENT : MOCK_ANALYZE_WITH_ACCENT;
    // docs/api.md: home_language echoes the code the client sent, and is null
    // only when none was given at all; session_id is null unless a
    // student_id was given (nothing is saved without one).
    sendJson(res, 200, {
      ...fixture,
      transcript: fixture === MOCK_ANALYZE_NO_ACCENT ? "rain field on the the old red roof" : "the kwick down jumps over over the lazy dog again today",
      home_language: homeLanguage ?? null,
      session_id: studentId ? fixture.session_id : null,
    });
    return true;
  }

  return false;
}
