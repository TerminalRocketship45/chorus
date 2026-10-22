import { useEffect, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import type { Passage } from "../types/api";
import { analyze, ApiRequestError, getPassage } from "../lib/api";
import { useAppState } from "../context/AppContext";
import { extensionForMimeType, pickRecorderMimeType } from "../lib/mimeType";
import { formatElapsed, formatPassageMeta } from "../lib/format";
import { MAX_RECORDING_SECONDS } from "../content/app";
import { recordLocalResult } from "../lib/history";
import { loadHistory, saveHistory } from "../lib/storage";
import { Screen } from "../components/Screen";
import { Icon, Spinner } from "../components/Icon";
import { MicMeter } from "../components/MicMeter";

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
  const [stream, setStream] = useState<MediaStream | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const mimeTypeRef = useRef<string | undefined>(undefined);
  const timerRef = useRef<number | null>(null);
  const startedAtRef = useRef<number>(0);

  // Resolve the passage if we weren't handed it via navigation (deep link / refresh),
  // via GET /api/passages/{id} (docs/api.md), which 404s for an unknown id.
  useEffect(() => {
    if (passage || !passageId) return;
    let cancelled = false;
    getPassage(passageId)
      .then((found) => {
        if (cancelled) return;
        setPassage(found);
        setState("idle");
      })
      .catch(() => {
        if (!cancelled) setState("error");
      });
    return () => {
      cancelled = true;
    };
  }, [passage, passageId]);

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
      const media = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = media;
      setStream(media);
      const mimeType = pickRecorderMimeType();
      mimeTypeRef.current = mimeType;
      const recorder = mimeType ? new MediaRecorder(media, { mimeType }) : new MediaRecorder(media);
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
    setStream(null);
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
      if (app.studentId === null) saveHistory(recordLocalResult(loadHistory(), passage.id, result));
      navigate("/results", { state: { analysis: result, passage, audioBlob: blob } });
    } catch (err) {
      if (err instanceof ApiRequestError) {
        if (err.status === 413) {
          setAnalyzeError("That recording is too long or too large. Try a shorter reading.");
        } else if (err.status === 422) {
          // The service words these kindly ("Chorus couldn't hear enough reading…", "Your recording was very quiet…").
          setAnalyzeError(err.message || "Chorus couldn't make out any speech in that recording. Please try again somewhere quiet.");
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

  const back = { label: "Passages", to: "/passages" };

  if (state === "loading-passage") {
    return (
      <Screen title="Passage" back={back}>
        <p className="footnote" role="status">
          Loading passage…
        </p>
      </Screen>
    );
  }

  if (!passage) {
    return (
      <Screen title="Passage" back={back}>
        <div className="notice notice--error" role="alert">
          <Icon name="warning" size={20} />
          <span>Chorus couldn't find that passage.</span>
        </div>
        <button type="button" className="btn btn--filled btn--block" onClick={() => navigate("/passages")}>
          Back to passages
        </button>
      </Screen>
    );
  }

  const showRecorder = state === "idle" || state === "requesting-mic" || state === "recording";
  const recording = state === "recording";

  const bottom = showRecorder ? (
    <div className="recorder">
      {recording && (
        <div
          className="rec-progress"
          role="progressbar"
          aria-label="Recording length"
          aria-valuemin={0}
          aria-valuemax={MAX_RECORDING_SECONDS}
          aria-valuenow={Math.floor(elapsed)}
        >
          <span style={{ width: `${Math.min(100, (elapsed / MAX_RECORDING_SECONDS) * 100)}%` }} />
        </div>
      )}
      <MicMeter stream={stream} active={recording} />
      <button
        type="button"
        className="rec-btn"
        aria-pressed={recording}
        aria-label={recording ? "Stop recording" : "Start recording"}
        disabled={state === "requesting-mic"}
        onClick={recording ? stopRecording : startRecording}
      >
        <Icon name="mic" size={30} strokeWidth={2.2} />
      </button>
      {recording ? (
        <p className="rec-time num" aria-live="polite">
          {formatElapsed(elapsed)} / {formatElapsed(MAX_RECORDING_SECONDS)}
        </p>
      ) : (
        <p className="rec-hint">Tap the button, then read the passage aloud.</p>
      )}
    </div>
  ) : undefined;

  return (
    <Screen title={passage.title} back={back} bottom={bottom}>
      <div className="title-block">
        <h1 className="large-title large-title--medium">{passage.title}</h1>
        <p className="meta-line">{formatPassageMeta(passage.topic, passage.level, passage.word_count)}</p>
      </div>
      <div className="group">
        <p className="passage-text">{passage.text}</p>
      </div>

      {micError && (
        <div className="notice notice--error" role="alert">
          <Icon name="warning" size={20} />
          <span>{micError}</span>
        </div>
      )}
      {state === "error" && analyzeError && (
        <div className="notice notice--error" role="alert">
          <Icon name="warning" size={20} />
          <div className="notice__body">
            <span>{analyzeError}</span>
            <button type="button" className="btn btn--tinted btn--compact" onClick={() => setState("idle")}>
              Try again
            </button>
          </div>
        </div>
      )}

      {state === "analyzing" && (
        <div className="busy" role="status" aria-live="polite">
          <Spinner size={28} />
          <p className="busy__title">Listening to your reading…</p>
          <p className="rec-hint">This can take up to 40 seconds.</p>
        </div>
      )}
    </Screen>
  );
}
