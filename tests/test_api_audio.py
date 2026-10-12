"""chorus_api.audio.decode_to_wav: any browser container -> 16 kHz mono 16-bit WAV."""
import wave

import av
import pytest

from chorus_api.audio import AudioTooLong, UndecodableAudio, decode_to_wav

CAT_WAV = "tests/fixtures/the_cat_sat.wav"


def _wav_info(path):
    with wave.open(str(path), "rb") as f:
        return f.getnchannels(), f.getframerate(), f.getsampwidth(), f.getnframes()


def test_wav_passthrough_is_resampled_to_16k_mono_16bit(tmp_path):
    out = tmp_path / "out.wav"
    duration = decode_to_wav(CAT_WAV, out)
    nchan, rate, width, nframes = _wav_info(out)
    assert (nchan, rate, width) == (1, 16000, 2)
    assert duration == pytest.approx(nframes / rate, abs=0.01)
    assert duration == pytest.approx(2.05, abs=0.05)


def test_webm_opus_round_trip_decodes(tmp_path):
    webm = tmp_path / "cat.webm"
    _wav_to_webm_opus(CAT_WAV, webm)

    out = tmp_path / "out.wav"
    duration = decode_to_wav(webm, out)
    nchan, rate, width, _ = _wav_info(out)
    assert (nchan, rate, width) == (1, 16000, 2)
    assert duration == pytest.approx(2.05, abs=0.1)


def test_undecodable_bytes_raise_undecodable_audio(tmp_path):
    bad = tmp_path / "not_audio.bin"
    bad.write_bytes(b"this is not an audio file" * 50)
    with pytest.raises(UndecodableAudio):
        decode_to_wav(bad, tmp_path / "out.wav")


def test_missing_file_raises_undecodable_audio(tmp_path):
    with pytest.raises(UndecodableAudio):
        decode_to_wav(tmp_path / "nope.webm", tmp_path / "out.wav")


def test_audio_longer_than_cap_raises_audio_too_long(tmp_path):
    long_wav = tmp_path / "long.wav"
    with wave.open(str(long_wav), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(16000)
        f.writeframes(b"\x00\x00" * 16000 * 3)  # 3 s of silence

    with pytest.raises(AudioTooLong):
        decode_to_wav(long_wav, tmp_path / "out.wav", max_duration_s=1.0)


def test_audio_under_cap_does_not_raise(tmp_path):
    out = tmp_path / "out.wav"
    decode_to_wav(CAT_WAV, out, max_duration_s=120.0)  # 2.05 s, well under cap


def _wav_to_webm_opus(src_path, dst_path) -> None:
    in_c = av.open(str(src_path))
    try:
        astream = next(s for s in in_c.streams if s.type == "audio")
        resampler = av.AudioResampler(format="s16", layout="mono", rate=48000)
        out_c = av.open(str(dst_path), mode="w", format="webm")
        out_stream = out_c.add_stream("libopus", rate=48000)
        try:
            for frame in in_c.decode(astream):
                for rframe in resampler.resample(frame):
                    for packet in out_stream.encode(rframe):
                        out_c.mux(packet)
            for rframe in resampler.resample(None):
                for packet in out_stream.encode(rframe):
                    out_c.mux(packet)
            for packet in out_stream.encode(None):
                out_c.mux(packet)
        finally:
            out_c.close()
    finally:
        in_c.close()
