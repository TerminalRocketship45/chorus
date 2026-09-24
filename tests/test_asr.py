import pytest

from chorus.asr import Transcript, transcribe


def test_transcript_dataclass_fields():
    t = Transcript(text="hello", duration_s=1.0)
    assert t.text == "hello"
    assert t.duration_s == 1.0


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
