import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import type { Passage } from "../types/api";
import { analyze, ApiRequestError, getPassages } from "../lib/api";
import { useAppState } from "../context/AppContext";
import { extensionForMimeType, pickRecorderMimeType } from "../lib/mimeType";
import { formatElapsed } from "../lib/format";
import { MAX_RECORDING_SECONDS } from "../content/app";

type RecordingState = "loading-passage" | "idle" | "requesting-mic" | "recording" | "analyzing" | "error";

interface LocationState {
  passage?: Passage;
}

export function Read() {
  const { passageId } = useParams<{ passageId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const app = useAppState();

  const [passage, setPassage] = useState<Passage | null>((location.state as LocationState | null)?.passage ?? null);
  const [state, setState] = useState<RecordingState>(passage ? "idle" : "loading-passage");
  const [elapsed, setElapsed] = useState(0);
  const [micError, setMicError] = useState<string | null>(null);
  const [analyzeError, setAnalyzeError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const mimeTypeRef = useRef<string | undefined>(undefined);
  const timerRef = useRef<number | null>(null);
  const startedAtRef = useRef<number>(0);

  // Resolve the passage if we weren't handed it via navigation (deep link / refresh).
  // docs/api.md has no GET /api/passages/{id}, so fall back to the full list.
  useEffect(() => {
    if (passage || !passageId) return;
    let cancelled = false;
    getPassages(app.gradeBand ?? undefined)
      .then((list) => {
        if (cancelled) return;
        const found = list.find((p) => p.id === passageId);
        if (found) {
          setPassage(found);
          setState("idle");
        } else {
          setState("error");
        }
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [passage, passageId, app.gradeBand]);

  useEffect(() => {
    return () => {
      stopTimer();
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function stopTimer() {
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }

  async function startRecording() {
    setMicError(null);
    setState("requesting-mic");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mimeType = pickRecorderMimeType();
      mimeTypeRef.current = mimeType;
      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.addEventListener("dataavailable", (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      });
      recorder.addEventListener("stop", handleRecordingStopped);

      recorder.start();
      startedAtRef.current = Date.now();
      setElapsed(0);
      setState("recording");
      timerRef.current = window.setInterval(() => {
        const secs = (Date.now() - startedAtRef.current) / 1000;
        setElapsed(secs);
        if (secs >= MAX_RECORDING_SECONDS) {
          stopRecording();
        }
      }, 250);
    } catch (err) {
      setState("idle");
      if (err instanceof DOMException && (err.name === "NotAllowedError" || err.name === "SecurityError")) {
        setMicError(
          "Chorus needs microphone access to hear you read. Please allow microphone access and try again."
        );
      } else if (err instanceof DOMException && err.name === "NotFoundError") {
        setMicError("Chorus couldn't find a microphone on this device.");
      } else {
        setMicError("Chorus couldn't start recording. Please try again.");
      }
    }
  }

  function stopRecording() {
    stopTimer();
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state !== "inactive") {
      recorder.stop();
    }
    streamRef.current?.getTracks().forEach((t) => t.stop());
  }

  async function handleRecordingStopped() {
    setState("analyzing");
    setAnalyzeError(null);
    const mimeType = mimeTypeRef.current;
    const blob = new Blob(chunksRef.current, mimeType ? { type: mimeType } : undefined);
    const filename = `reading.${extensionForMimeType(mimeType)}`;

    if (!passage) {
      setAnalyzeError("Chorus lost track of the passage. Please go back and pick it again.");
      setState("error");
      return;
    }

    try {
      const result = await analyze({
        audio: blob,
        filename,
        passageId: passage.id,
        studentId: app.studentId,
        homeLanguage: app.homeLanguage,
      });
      navigate("/results", { state: { analysis: result, passage, audioBlob: blob } });
    } catch (err) {
      if (err instanceof ApiRequestError) {
        if (err.status === 413) {
          setAnalyzeError("That recording is too long or too large. Try a shorter reading.");
        } else if (err.status === 422) {
          setAnalyzeError("Chorus couldn't make out any speech in that recording. Please try again somewhere quiet.");
        } else if (err.status === 503) {
          setAnalyzeError("Chorus is busy helping other readers right now. Please try again in a minute.");
        } else {
          setAnalyzeError(err.message || "Something went wrong while scoring that reading.");
        }
      } else {
        setAnalyzeError("Something went wrong while scoring that reading. Please check your connection and try again.");
      }
      setState("error");
    }
  }

  if (state === "loading-passage") {
    return (
      <div className="page">
        <p>Loading passage…</p>
      </div>
    );
  }

  if (!passage) {
    return (
      <div className="page stack">
        <p className="error-banner">Chorus couldn't find that passage.</p>
        <button type="button" className="btn btn-primary" onClick={() => navigate("/passages")}>
          Back to passages
        </button>
      </div>
    );
  }

  return (
    <div className="page stack stack--loose">
      <div className="stack stack--tight">
        <h1>{passage.title}</h1>
        <p style={{ fontSize: "1.4rem", lineHeight: 1.7 }}>{passage.text}</p>
      </div>

      {micError && <p className="error-banner">{micError}</p>}
      {state === "error" && analyzeError && (
        <div className="stack stack--tight">
          <p className="error-banner">{analyzeError}</p>
          <button type="button" className="btn btn-primary" onClick={() => setState("idle")}>
            Try again
          </button>
        </div>
      )}

      {state === "analyzing" && (
        <div className="stack stack--tight" style={{ textAlign: "center" }} role="status" aria-live="polite">
          <p style={{ fontSize: "1.2rem" }}>Listening to your reading…</p>
          <p className="muted">This can take up to 40 seconds.</p>
        </div>
      )}

      {(state === "idle" || state === "requesting-mic" || state === "recording") && (
        <div className="stack" style={{ textAlign: "center" }}>
          <button
            type="button"
            className="record-button"
            aria-pressed={state === "recording"}
            aria-label={state === "recording" ? "Stop recording" : "Start recording"}
            disabled={state === "requesting-mic"}
            onClick={state === "recording" ? stopRecording : startRecording}
          >
            {state === "recording" ? "Stop" : state === "requesting-mic" ? "…" : "Record"}
          </button>
          {state === "recording" && (
            <p aria-live="polite" style={{ fontSize: "1.2rem" }}>
              {formatElapsed(elapsed)} / {formatElapsed(MAX_RECORDING_SECONDS)}
            </p>
          )}
          {state === "idle" && <p className="muted">Tap the button, then read the passage aloud.</p>}
        </div>
      )}
    </div>
  );
}
