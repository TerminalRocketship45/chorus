"""Shared fixtures. Generates a real WAV so audio tests need no recording."""
import wave
from pathlib import Path

import numpy as np
import pytest


@pytest.fixture(scope="session")
def silence_wav(tmp_path_factory) -> Path:
    """One second of near-silence at 16 kHz mono, as a real WAV file."""
    path = tmp_path_factory.mktemp("audio") / "silence.wav"
    samples = (np.random.default_rng(0).normal(0, 1e-4, 16000) * 32767).astype(
        np.int16
    )
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(samples.tobytes())
    return path


@pytest.fixture(scope="session")
def cat_wav() -> Path:
    """A real spoken "The cat sat on the mat." (mono, 16 kHz, 16-bit) for alignment tests."""
    return Path(__file__).parent / "fixtures" / "the_cat_sat.wav"
