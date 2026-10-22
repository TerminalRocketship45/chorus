"""Find which recogniser settings fix a bad real recording.

    python scripts/diagnose_recording.py saved.wav --passage-id el-01
    python scripts/diagnose_recording.py saved.wav --text "The cat sat on the mat."
    python scripts/diagnose_recording.py saved.wav --text-file passage.txt --models small.en

Use a WAV saved with CHORUS_DEBUG_AUDIO_DIR (see SETUP.md), any audio PyAV can read works.
Runs the transcription under every combination of model x beam size x vad_filter and
prints levels, then the transcript and accuracy for each (same-sound and digit-context
on, as in the app). One model at a time, on the CPU unless CHORUS_ASR_DEVICE says otherwise.
"""
from __future__ import annotations

import argparse
import itertools
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chorus import asr  # noqa: E402
from chorus.miscue import detect_miscues, normalize  # noqa: E402
from chorus.scoring import score_reading  # noqa: E402
from chorus_api import passages as passages_mod  # noqa: E402
from chorus_api.audio import decode_to_wav, normalize_wav_peak, wav_levels  # noqa: E402


def run_config(wav: str, expected: list[str], model: str, beam: int, vad: bool,
               drop_hallucinations: bool) -> dict:
    t0 = time.time()
    tr = asr.transcribe(wav, model_size=model, beam_size=beam, vad_filter=vad,
                        drop_hallucinations=drop_hallucinations)
    words = detect_miscues(expected, normalize(tr.text, digit_context=expected), same_sound=True)
    score = score_reading(words, duration_s=tr.duration_s)
    return {"text": tr.text, "accuracy": score.accuracy, "wcpm": score.wcpm,
            "dropped": tr.dropped_segments, "secs": time.time() - t0}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("audio", help="saved recording (wav or any container PyAV reads)")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--passage-id", help="library or generated passage id, e.g. el-01")
    g.add_argument("--text", help="the passage text")
    g.add_argument("--text-file", help="file with the passage text")
    ap.add_argument("--models", nargs="+", default=["base.en", "small.en"])
    ap.add_argument("--beams", nargs="+", type=int, default=[1, 5])
    ap.add_argument("--drop-hallucinations", action="store_true",
                    help="also apply the no-speech segment filter (the app does)")
    ap.add_argument("--normalize", action="store_true",
                    help="peak-normalise to -3 dBFS first (the app does for quiet audio)")
    args = ap.parse_args(argv)

    if args.passage_id:
        p = passages_mod.get_passage(args.passage_id)
        if p is None:
            sys.exit(f"unknown passage id {args.passage_id!r}")
        text = p.text
    elif args.text_file:
        text = Path(args.text_file).read_text(encoding="utf-8")
    else:
        text = args.text
    expected = normalize(text)

    tmp = Path(tempfile.mkdtemp(prefix="chorus_diag_")) / "audio.wav"
    dur = decode_to_wav(args.audio, tmp)
    print(f"audio: {dur:.1f} s, levels {wav_levels(tmp)}")
    if args.normalize:
        print(f"normalised by {normalize_wav_peak(tmp):.1f} dB -> {wav_levels(tmp)}")
    print(f"passage: {len(expected)} words\n")

    for model, beam, vad in itertools.product(args.models, args.beams, (False, True)):
        r = run_config(str(tmp), expected, model, beam, vad, args.drop_hallucinations)
        print(f"== {model} beam={beam} vad={'on' if vad else 'off'}: "
              f"accuracy {r['accuracy']:.0%}, {r['wcpm']:.0f} wcpm, "
              f"{r['dropped']} segments dropped, {r['secs']:.1f}s")
        print(f"   {r['text'] or '(nothing heard)'}\n")


if __name__ == "__main__":
    main()
