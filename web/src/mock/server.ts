/**
 * Dev-only fixture server for `/api/*`, used when VITE_MOCK=1 (see
 * vite.config.ts). Runs inside the Vite dev server (Node), never in the
 * browser bundle, and never in `vite build`. It exists only because the
 * FastAPI backend (docs/api.md) isn't built yet.
 */
import type { IncomingMessage, ServerResponse } from "node:http";
import {
  MOCK_ANALYZE_NO_ACCENT,
  MOCK_ANALYZE_WITH_ACCENT,
  MOCK_LANGUAGES,
  MOCK_PASSAGES,
  MOCK_STUDENTS,
  MOCK_STUDENT_DETAILS,
} from "./fixtures";
import type { GradeBand, Student } from "../types/api";

let nextStudentId = 1000;

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
    const found = MOCK_PASSAGES.find((p) => p.id === id);
    if (!found) {
      sendJson(res, 404, { detail: `unknown passage_id: '${id}'` });
      return true;
    }
    sendJson(res, 200, found);
    return true;
  }

  if (method === "GET" && path === "/api/students") {
    sendJson(res, 200, MOCK_STUDENTS);
    return true;
  }

  if (method === "GET" && /^\/api\/students\/\d+$/.test(path)) {
    const id = Number(path.split("/").pop());
    const detail = MOCK_STUDENT_DETAILS[id];
    if (!detail) {
      sendJson(res, 404, { detail: "Student not found." });
      return true;
    }
    sendJson(res, 200, detail);
    return true;
  }

  if (method === "POST" && path === "/api/students") {
    const raw = await readBody(req);
    let payload: { name?: string; grade_band?: GradeBand; home_language?: string } = {};
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
      created_at: new Date().toISOString(),
    };
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
    const fixture = homeLanguage === "english" ? MOCK_ANALYZE_NO_ACCENT : MOCK_ANALYZE_WITH_ACCENT;
    // docs/api.md: home_language echoes the code the client sent, and is null
    // only when none was given at all; session_id is null unless a
    // student_id was given (nothing is saved without one).
    sendJson(res, 200, {
      ...fixture,
      home_language: homeLanguage ?? null,
      session_id: studentId ? fixture.session_id : null,
    });
    return true;
  }

  return false;
}
