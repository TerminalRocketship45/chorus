import numpy as np
import soundfile as sf

from chorus.tail import MAX_TAIL_SPEECH_S, implausibly_long, speech_after


def _wav(tmp_path, spans, total=6.0, sr=16000, noise=0.0005):
    rng = np.random.default_rng(0)
    x = noise * rng.standard_normal(int(total * sr))
    for a, b in spans:
        n = int((b - a) * sr)
        x[int(a * sr): int(a * sr) + n] += 0.2 * np.sin(2 * np.pi * 180 * np.arange(n) / sr)
    p = tmp_path / "t.wav"
    sf.write(p, x.astype("float32"), sr)
    return p


def test_silence_after_last_word_is_no_speech(tmp_path):
    p = _wav(tmp_path, [(0.5, 3.0)])
    assert speech_after(p, 3.0) < MAX_TAIL_SPEECH_S
    assert speech_after(p, 3.0) == 0.0


def test_continued_speech_after_last_word_is_counted(tmp_path):
    p = _wav(tmp_path, [(0.5, 3.0), (3.5, 5.5)])
    assert speech_after(p, 3.0) > 1.5 > MAX_TAIL_SPEECH_S


def test_early_alignment_end_is_covered_by_grace(tmp_path):
    p = _wav(tmp_path, [(0.5, 3.0)])
    assert speech_after(p, 2.9) < MAX_TAIL_SPEECH_S


def test_stretched_word_span_is_implausible():
    assert not implausibly_long("uncovered", 14.16, 14.74)
    assert implausibly_long("big", 1.0, 2.5)
