"""Did the reader stop, or did the recogniser lose the end?

Words after the last word we heard may be unread because the reader stopped
(not an error) or because Whisper dropped or garbled the end of a recording in
which the reader kept talking (an error we must not hide). Only the audio can
tell: if there is essentially no speech after the last heard word, the reader
stopped.

Speech is measured as the time spent in 20 ms frames whose level is within
`REL_DB` of the recording's loud speech level (95th percentile frame level),
and above an absolute floor. Frames within `GRACE_S` of the last word's end are
ignored, since forced-alignment ends are a little early on trailing consonants.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

FRAME_S = 0.02
#: A frame is speech when within this many dB of the loud-speech level.
REL_DB = 30.0
#: ...and louder than this absolute level (dBFS), so a near-silent file has no "speech".
FLOOR_DB = -55.0
#: Ignore this long after the last heard word's end (alignment slack).
GRACE_S = 0.2
#: The reader stopped when less than this much speech follows the last heard word.
#: A stray word is ~0.3-0.5 s; two or more spoken words exceed it. See SETUP/eval notes.
MAX_TAIL_SPEECH_S = 0.75


def _load_mono(path: str | Path) -> tuple[np.ndarray, int]:
    import soundfile as sf

    x, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return x.mean(axis=1), int(sr)


def speech_after(audio_path: str | Path, after_s: float, grace_s: float = GRACE_S) -> float:
    """Seconds of speech in the recording after `after_s` (+ grace). 0.0 if none."""
    x, sr = _load_mono(audio_path)
    n = max(1, int(FRAME_S * sr))
    frames = len(x) // n
    if frames == 0:
        return 0.0
    f = x[: frames * n].reshape(frames, n)
    db = 20.0 * np.log10(np.sqrt((f.astype(np.float64) ** 2).mean(axis=1)) + 1e-9)
    thresh = max(float(np.percentile(db, 95)) - REL_DB, FLOOR_DB)
    first = int(np.ceil((after_s + grace_s) / FRAME_S))
    return float((db[first:] > thresh).sum()) * FRAME_S


#: A word's forced-alignment span is implausibly long when over this many seconds
#: plus PER_LETTER_S per letter. Such a span usually means the aligner stretched the
#: word over speech the recogniser never transcribed, so "no speech after it" proves nothing.
BASE_WORD_S = 0.4
PER_LETTER_S = 0.1


def implausibly_long(word: str, start: float, end: float) -> bool:
    return (end - start) > BASE_WORD_S + PER_LETTER_S * len(word)
