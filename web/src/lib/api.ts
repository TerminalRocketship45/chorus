import type {
  AnalyzeResponse,
  GradeBand,
  LanguageOption,
  Passage,
  Student,
  StudentDetailResponse,
  StudentListItem,
} from "../types/api";

export class ApiRequestError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      // Response body wasn't JSON; keep the generic message.
    }
    throw new ApiRequestError(res.status, detail);
  }
  return (await res.json()) as T;
}

export function getLanguages(): Promise<LanguageOption[]> {
  return request<LanguageOption[]>("/languages");
}

export function getPassages(band?: GradeBand): Promise<Passage[]> {
  const qs = band ? `?band=${encodeURIComponent(band)}` : "";
  return request<Passage[]>(`/passages${qs}`);
}

/** Throws ApiRequestError with status 404 if `id` is unknown (docs/api.md). */
export function getPassage(id: string): Promise<Passage> {
  return request<Passage>(`/passages/${encodeURIComponent(id)}`);
}

export function createStudent(body: {
  name: string;
  grade_band: GradeBand;
  home_language: string;
}): Promise<Student> {
  return request<Student>("/students", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function getStudents(): Promise<StudentListItem[]> {
  return request<StudentListItem[]>("/students");
}

export function getStudent(id: number): Promise<StudentDetailResponse> {
  return request<StudentDetailResponse>(`/students/${id}`);
}

export interface AnalyzeParams {
  audio: Blob;
  filename: string;
  passageId: string;
  studentId?: number | null;
  homeLanguage?: string | null;
}

export function analyze(params: AnalyzeParams): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("audio", params.audio, params.filename);
  form.append("passage_id", params.passageId);
  if (params.studentId != null) form.append("student_id", String(params.studentId));
  if (params.homeLanguage) form.append("home_language", params.homeLanguage);
  return request<AnalyzeResponse>("/analyze", { method: "POST", body: form });
}
