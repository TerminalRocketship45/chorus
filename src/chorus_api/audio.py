"""Decode a browser recording (webm/opus, ogg, mp4/aac, wav, ...) to a 16 kHz
mono 16-bit PCM WAV file, using PyAV (`av`) only — no ffmpeg binary needed,
since `av` bundles its own FFmpeg libraries.

POST /api/analyze accepts whatever MediaRecorder produced; chorus.pipeline
expects a WAV path, so this module is the one place that bridges the two.
"""
from __future__ import annotations

import math
import wave
from pathlib import Path

import av
import numpy as np

TARGET_RATE = 16000


class UndecodableAudio(ValueError):
    """The input could not be decoded as audio at all (bad container, no audio stream)."""


class AudioTooLong(ValueError):
    """Decoded audio exceeds the duration cap."""


def decode_to_wav(
    src_path: str | Path, dst_path: str | Path, max_duration_s: float = 120.0
) -> float:
    """Decode `src_path` (any container PyAV can read) to a 16 kHz mono
    16-bit PCM WAV at `dst_path`.

    Returns the decoded duration in seconds. Raises `UndecodableAudio` if the
    file cannot be opened, has no audio stream, or decoding otherwise fails.
    Raises `AudioTooLong` as soon as the decoded audio crosses
    `max_duration_s`, without finishing the decode of a huge file.
    """
    try:
        in_container = av.open(str(src_path))
    except (av.error.FFmpegError, OSError) as exc:
        raise UndecodableAudio(f"could not open audio: {exc}") from exc

    try:
        audio_stream = next(
            (s for s in in_container.streams if s.type == "audio"), None
        )
        if audio_stream is None:
            raise UndecodableAudio("no audio stream found in upload")

        resampler = av.AudioResampler(format="s16", layout="mono", rate=TARGET_RATE)
        out_container = av.open(str(dst_path), mode="w", format="wav")
        out_stream = out_container.add_stream(
            "pcm_s16le", rate=TARGET_RATE, layout="mono"
        )
        total_samples = 0
        try:
            for frame in in_container.decode(audio_stream):
                for rframe in resampler.resample(frame):
                    total_samples += rframe.samples
                    if total_samples / TARGET_RATE > max_duration_s:
                        raise AudioTooLong(
                            f"audio exceeds {max_duration_s}s duration cap"
                        )
                    for packet in out_stream.encode(rframe):
                        out_container.mux(packet)
            for rframe in resampler.resample(None):
                total_samples += rframe.samples
                for packet in out_stream.encode(rframe):
                    out_container.mux(packet)
            for packet in out_stream.encode(None):
                out_container.mux(packet)
        finally:
            out_container.close()
        return total_samples / TARGET_RATE
    except av.error.FFmpegError as exc:
        raise UndecodableAudio(f"could not decode audio: {exc}") from exc
    finally:
        in_container.close()


#: Peak below this (dBFS) is treated as a dead microphone: nothing to transcribe.
SILENT_PEAK_DBFS = -40.0
#: Quiet-but-usable recordings are peak-normalised to this level before transcription.
NORMALIZE_TARGET_DBFS = -3.0
#: Recordings whose peak is already above this are left alone.
NORMALIZE_BELOW_DBFS = -6.0


def _read_pcm16(path: str | Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as f:
        data = np.frombuffer(f.readframes(f.getnframes()), dtype="<i2")
        return data, f.getframerate()


def wav_levels(path: str | Path) -> dict[str, float]:
    """Peak and RMS of a 16-bit mono WAV, in dBFS (-120 for digital silence)."""
    data, _ = _read_pcm16(path)
    if data.size == 0:
        return {"peak_dbfs": -120.0, "rms_dbfs": -120.0}
    x = data.astype(np.float64) / 32768.0
    peak = float(np.max(np.abs(x)))
    rms = float(np.sqrt(np.mean(x * x)))

    def db(v: float) -> float:
        return round(20 * math.log10(v), 1) if v > 1e-6 else -120.0

    return {"peak_dbfs": db(peak), "rms_dbfs": db(rms)}


def normalize_wav_peak(
    path: str | Path,
    target_dbfs: float = NORMALIZE_TARGET_DBFS,
    below_dbfs: float = NORMALIZE_BELOW_DBFS,
) -> float:
    """Raise a quiet 16-bit mono WAV in place so its peak is `target_dbfs`.

    Does nothing (returns 0.0) when the peak is already above `below_dbfs` or the
    file is silent. Returns the gain applied, in dB.
    """
    data, rate = _read_pcm16(path)
    if data.size == 0:
        return 0.0
    peak = float(np.max(np.abs(data.astype(np.float64)))) / 32768.0
    if peak <= 1e-6:
        return 0.0
    peak_db = 20 * math.log10(peak)
    if peak_db >= below_dbfs:
        return 0.0
    gain_db = target_dbfs - peak_db
    out = np.clip(data.astype(np.float64) * 10 ** (gain_db / 20), -32768, 32767).astype("<i2")
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(out.tobytes())
    return gain_db
