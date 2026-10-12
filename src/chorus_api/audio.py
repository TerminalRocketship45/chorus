"""Decode a browser recording (webm/opus, ogg, mp4/aac, wav, ...) to a 16 kHz
mono 16-bit PCM WAV file, using PyAV (`av`) only — no ffmpeg binary needed,
since `av` bundles its own FFmpeg libraries.

POST /api/analyze accepts whatever MediaRecorder produced; chorus.pipeline
expects a WAV path, so this module is the one place that bridges the two.
"""
from __future__ import annotations

from pathlib import Path

import av

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
