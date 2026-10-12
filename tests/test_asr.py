import pytest

from chorus.asr import Transcript, _resolve_compute_type, _resolve_device, transcribe


def test_transcript_dataclass_fields():
    t = Transcript(text="hello", duration_s=1.0)
    assert t.text == "hello"
    assert t.duration_s == 1.0


def test_resolve_device_explicit_cpu(monkeypatch):
    monkeypatch.setenv("CHORUS_ASR_DEVICE", "cpu")
    assert _resolve_device() == "cpu"


def test_resolve_device_explicit_cuda(monkeypatch):
    monkeypatch.setenv("CHORUS_ASR_DEVICE", "cuda")
    # Explicit "cuda" is trusted as-is; no cuda_device_count check happens.
    assert _resolve_device() == "cuda"


def test_resolve_device_explicit_is_case_insensitive(monkeypatch):
    monkeypatch.setenv("CHORUS_ASR_DEVICE", "CPU")
    assert _resolve_device() == "cpu"


def test_resolve_device_invalid_raises(monkeypatch):
    monkeypatch.setenv("CHORUS_ASR_DEVICE", "tpu")
    with pytest.raises(ValueError, match="CHORUS_ASR_DEVICE"):
        _resolve_device()


def test_resolve_device_auto_with_no_cuda(monkeypatch):
    monkeypatch.delenv("CHORUS_ASR_DEVICE", raising=False)
    assert _resolve_device(cuda_device_count=0) == "cpu"


def test_resolve_device_auto_with_cuda(monkeypatch):
    monkeypatch.delenv("CHORUS_ASR_DEVICE", raising=False)
    assert _resolve_device(cuda_device_count=1) == "cuda"


def test_resolve_device_default_is_auto(monkeypatch):
    monkeypatch.delenv("CHORUS_ASR_DEVICE", raising=False)
    # No cuda_device_count override: falls through to the lazy
    # ctranslate2.get_cuda_device_count() check. Compare against that
    # directly so this test passes on both a CPU-only and a GPU machine.
    import ctranslate2

    expected = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    assert _resolve_device() == expected


def test_resolve_compute_type_cuda_default():
    assert _resolve_compute_type("cuda") == "float16"


def test_resolve_compute_type_cpu_default():
    assert _resolve_compute_type("cpu") == "int8"


def test_resolve_compute_type_override(monkeypatch):
    monkeypatch.setenv("CHORUS_ASR_COMPUTE_TYPE", "int8_float16")
    assert _resolve_compute_type("cuda") == "int8_float16"


@pytest.mark.slow
def test_transcribe_returns_transcript(silence_wav):
    result = transcribe(silence_wav, model_size="base.en")
    assert isinstance(result, Transcript)
    assert isinstance(result.text, str)
    assert result.duration_s > 0


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        transcribe(tmp_path / "nope.wav")


def test_directory_path_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError, match="not found"):
        transcribe(tmp_path)
