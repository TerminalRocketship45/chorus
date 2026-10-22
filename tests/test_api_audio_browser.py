"""Browser-like recordings (webm/opus, ogg/opus, mp4/aac; mono and stereo; 48 and 44.1 kHz)
must decode to the right duration and the same waveform. Guards against a decoder bug
that would drop or garble part of a recording."""
from __future__ import annotations

import wave
from pathlib import Path

import av
import numpy as np
import pytest

from chorus_api.audio import decode_to_wav

CAT_WAV = "tests/fixtures/the_cat_sat.wav"
CLIP_60 = Path("/lustre/smuexa01/client/users/rbankapur/chorus_scratch/bench/clips/clip_60s.wav")

# (container, codec, rate, channels, muxer options)
CASES = [
    ("webm", "libopus", 48000, 1, {}),
    ("webm", "libopus", 48000, 2, {}),
    ("webm", "libopus", 48000, 1, {"live": "1"}),
    ("ogg", "libopus", 48000, 1, {}),
    ("ogg", "libopus", 48000, 2, {}),
    ("mp4", "aac", 48000, 1, {}),
    ("mp4", "aac", 44100, 1, {}),
    ("mp4", "aac", 44100, 2, {}),
    ("mp4", "aac", 48000, 2, {"movflags": "frag_keyframe+empty_moov"}),
]


def _read_wav(path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as f:
        assert f.getsampwidth() == 2
        data = np.frombuffer(f.readframes(f.getnframes()), dtype="<i2")
        if f.getnchannels() > 1:
            data = data.reshape(-1, f.getnchannels()).mean(axis=1)
        return data.astype(np.float32) / 32768.0, f.getframerate()


def _resample(x: np.ndarray, src: int, dst: int) -> np.ndarray:
    """Resample mono float via PyAV (independent of audio.py)."""
    if src == dst:
        return x
    rs = av.AudioResampler(format="fltp", layout="mono", rate=dst)
    fr = av.AudioFrame.from_ndarray(x[None, :].astype(np.float32), format="fltp", layout="mono")
    fr.sample_rate = src
    out = [f.to_ndarray()[0] for f in rs.resample(fr)] + [f.to_ndarray()[0] for f in rs.resample(None)]
    return np.concatenate(out)


def encode_like_browser(src_wav, dst, container, codec, rate, channels, options):
    x, sr = _read_wav(src_wav)
    x = _resample(x, sr, rate)
    out = av.open(str(dst), mode="w", format=container, options=options)
    stream = out.add_stream(codec, rate=rate)
    stream.layout = "stereo" if channels == 2 else "mono"
    layout = "stereo" if channels == 2 else "mono"
    arr = np.tile(x[None, :], (channels, 1)).astype(np.float32)
    frame_size = 960 if codec == "libopus" else 1024
    pts = 0
    for i in range(0, arr.shape[1], frame_size):
        chunk = arr[:, i : i + frame_size]
        fr = av.AudioFrame.from_ndarray(np.ascontiguousarray(chunk), format="fltp", layout=layout)
        fr.sample_rate = rate
        fr.pts = pts
        pts += chunk.shape[1]
        for p in stream.encode(fr):
            out.mux(p)
    for p in stream.encode(None):
        out.mux(p)
    out.close()


def _corr_at(ref: np.ndarray, got: np.ndarray, lag: int) -> float:
    a = ref[max(0, lag):]
    b = got[max(0, -lag):]
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))


def best_correlation(ref: np.ndarray, got: np.ndarray, max_lag: int = 3200) -> tuple[float, int]:
    """Max normalised correlation over lags within +-max_lag samples (codec priming delay):
    coarse search, then a sample-exact refinement."""
    coarse = max(range(-max_lag, max_lag + 1, 16), key=lambda l: _corr_at(ref, got, l))
    lag = max(range(coarse - 16, coarse + 17), key=lambda l: _corr_at(ref, got, l))
    return _corr_at(ref, got, lag), lag


def _check(src_wav, tmp_path, case):
    container, codec, rate, channels, options = case
    enc = tmp_path / f"rec.{container}"
    try:
        encode_like_browser(src_wav, enc, container, codec, rate, channels, options)
    except Exception as exc:  # encoder not in this PyAV build
        pytest.skip(f"cannot encode {container}/{codec}: {exc}")
    out = tmp_path / "out.wav"
    dur = decode_to_wav(enc, out)
    ref, sr = _read_wav(src_wav)
    ref16 = _resample(ref, sr, 16000)
    got, gsr = _read_wav(out)
    assert gsr == 16000
    src_dur = len(ref16) / 16000
    assert dur == pytest.approx(src_dur, abs=0.1), (case, dur, src_dur)
    assert len(got) / 16000 == pytest.approx(dur, abs=0.01)
    corr, lag = best_correlation(ref16, got)
    assert corr > 0.95, (case, corr, lag)


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c[0]}-{c[1]}-{c[2]}-{c[3]}ch-{'-'.join(c[4])}")
def test_browser_like_cat(tmp_path, case):
    _check(CAT_WAV, tmp_path, case)


@pytest.mark.skipif(not CLIP_60.is_file(), reason="speech clip not available")
@pytest.mark.parametrize("case", CASES, ids=lambda c: f"{c[0]}-{c[1]}-{c[2]}-{c[3]}ch-{'-'.join(c[4])}")
def test_browser_like_real_speech_60s(tmp_path, case):
    _check(CLIP_60, tmp_path, case)
