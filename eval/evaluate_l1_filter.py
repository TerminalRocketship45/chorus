"""Measure what the L1 filter buys, against expert word-level labels.

Two numbers, which must always be reported together:

  fp_reduction - of the words the experts judged correct but the unfiltered
                 baseline flagged, the share the filter withdraws.
  retention    - of the words the experts judged mispronounced, the share
                 still flagged after filtering. The guardrail: a filter that
                 excuses everything scores fp_reduction 1.0 and retention 0.0.

"Flagged" follows the shipped behaviour: a word is flagged when its real
miscue status (from ``detect_miscues``) is an error status, and the filter is
the real ``chorus.pipeline.apply_l1_filter``, not a re-implementation.

Run (from KasRep; ``pytest.ini``'s ``pythonpath = src`` applies only under
pytest, so outside pytest set PYTHONPATH yourself, ';' separates on Windows):

  PYTHONPATH="src;." .venv/Scripts/python -m eval.evaluate_l1_filter --model base.en --limit 500 --seed 0 --language mandarin

Transcripts are cached in eval/data/transcripts_<model>.json, so re-running
does not call Whisper again.
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import chorus.pipeline as pipeline
from chorus.l1.engine import load_ruleset
from chorus.miscue import normalize
from chorus.types import ERROR_STATUSES, WordResult, WordStatus

#: speechocean762 scores each word 0-10. At or above this, experts judged it correct.
EXPERT_CORRECT = 8.0

EVAL_DIR = Path(__file__).parent
CACHE_DIR = EVAL_DIR / "data"
RESULTS_PATH = EVAL_DIR / "results.json"


@dataclass
class WordRecord:
    """One expected word, what our ASR heard, and what the experts scored it."""

    expected: str
    heard: str | None
    expert_accuracy: float
    status: WordStatus | None = None
    uttid: str = ""

    def __post_init__(self) -> None:
        if self.status is None:
            if self.heard is None:
                self.status = WordStatus.OMISSION
            elif self.heard == self.expected:
                self.status = WordStatus.CORRECT
            else:
                self.status = WordStatus.SUBSTITUTION


@dataclass
class FilterMetrics:
    fp_before: int
    fp_after: int
    tp_before: int
    tp_after: int

    @property
    def fp_reduction(self) -> float:
        if not self.fp_before:
            return 0.0
        return (self.fp_before - self.fp_after) / self.fp_before

    @property
    def retention(self) -> float:
        if not self.tp_before:
            return 0.0
        return self.tp_after / self.tp_before


def is_excused(r: WordRecord, language: str) -> bool:
    """Ask the real pipeline filter whether this word would be accent-excused.

    Relies on ``apply_l1_filter`` being pure and per-word (each word is judged
    independently), so a one-word call gives the same answer as a whole-text call.
    """
    word = WordResult(index=0, expected=r.expected, heard=r.heard, status=r.status)
    return bool(pipeline.apply_l1_filter([word], language)[0].accent_excused)


def flags(r: WordRecord, language: str) -> tuple[bool, bool, bool]:
    """(flagged_before, flagged_after, excused) for one word."""
    flagged_before = r.status in ERROR_STATUSES
    excused = flagged_before and is_excused(r, language)
    return flagged_before, flagged_before and not excused, excused


def evaluate(records: list[WordRecord], language: str) -> FilterMetrics:
    """Build the before/after confusion counts for one language."""
    load_ruleset(language)  # unknown language fails loudly, as in analyze()
    fp_before = fp_after = tp_before = tp_after = 0
    for r in records:
        before, after, _ = flags(r, language)
        if r.expert_accuracy >= EXPERT_CORRECT:
            fp_before += int(before)
            fp_after += int(after)
        else:
            tp_before += int(before)
            tp_after += int(after)
    return FilterMetrics(fp_before, fp_after, tp_before, tp_after)


def _percentile(sorted_vals: list[float], q: float) -> float | None:
    if not sorted_vals:
        return None
    pos = q * (len(sorted_vals) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def bootstrap_ci(
    records: list[WordRecord], language: str, n: int = 1000, seed: int = 0
) -> dict:
    """95% percentile intervals from utterance-level resampling.

    Resamples whole utterances (by ``uttid``) with replacement, since words in
    one utterance are not independent. Resamples where a ratio's denominator is
    zero are left out of that ratio's interval; an interval that is undefined
    (no usable resample) is ``(None, None)``. Returns
    ``{"fp_reduction": (lo, hi), "retention": (lo, hi), "n_resamples_*": ...}``.
    """
    by_utt: dict[str, FilterMetrics] = {}
    groups: dict[str, list[WordRecord]] = {}
    for r in records:
        groups.setdefault(r.uttid, []).append(r)
    for uid, recs in groups.items():
        by_utt[uid] = evaluate(recs, language)
    ids = sorted(by_utt)
    rng = random.Random(seed)
    fpr: list[float] = []
    ret: list[float] = []
    if ids:
        for _ in range(n):
            picks = [by_utt[rng.choice(ids)] for _ in ids]
            m = FilterMetrics(
                sum(p.fp_before for p in picks),
                sum(p.fp_after for p in picks),
                sum(p.tp_before for p in picks),
                sum(p.tp_after for p in picks),
            )
            if m.fp_before:
                fpr.append(m.fp_reduction)
            if m.tp_before:
                ret.append(m.retention)
    fpr.sort()
    ret.sort()
    return {
        "fp_reduction": (_percentile(fpr, 0.025), _percentile(fpr, 0.975)),
        "retention": (_percentile(ret, 0.025), _percentile(ret, 0.975)),
        "n_resamples_fp_reduction": len(fpr),
        "n_resamples_retention": len(ret),
    }


# --- sampling -------------------------------------------------------------


def read_test_ids(test_dir: Path) -> list[str]:
    """Utterance ids of a Kaldi-style split directory (first column of `text`)."""
    ids = []
    for line in (test_dir / "text").read_text(encoding="utf-8").splitlines():
        if line.strip():
            ids.append(line.split(None, 1)[0])
    return ids


def sample_ids(ids: list[str], limit: int, seed: int) -> list[str]:
    """Seeded random sample of distinct ids, independent of input order."""
    pool = sorted(set(ids))
    return random.Random(seed).sample(pool, min(limit, len(pool)))


# --- record building ------------------------------------------------------


def _load_cache(path: Path | None) -> dict[str, str]:
    if path is not None and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_cache(path: Path | None, cache: dict[str, str]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(cache), encoding="utf-8")
    tmp.replace(path)


def cache_path_for(
    model: str, beam_size: int = 1, prompt_passage: bool = False,
    cache_dir: Path | None = None,
) -> Path:
    """Transcript cache file for one set of transcript-changing options.

    The default (beam 1, no prompt) keeps the legacy name
    ``transcripts_<model>.json``. Every option that changes the transcript adds
    a suffix, so configs never share a cache. ``same_sound`` is not part of the
    name: it acts after transcription.
    """
    name = f"transcripts_{model}"
    if beam_size != 1:
        name += f"_beam{beam_size}"
    if prompt_passage:
        name += "_prompt"
    return (cache_dir or CACHE_DIR) / f"{name}.json"


def build_records(
    utterances,
    audio_index: dict[str, Path],
    limit: int | None = None,
    model_size: str = "base.en",
    cache_path: Path | None = None,
    beam_size: int = 1,
    same_sound: bool = False,
    prompt_passage: bool = False,
    digit_context: bool = False,
    save_every: int = 25,
    return_info: bool = False,
):
    """Run ASR over corpus audio to get the system's opinion per word.

    Transcripts are cached by lower-cased utterance id and the cache is written
    every ``save_every`` fresh transcriptions (and on failure), so an
    interrupted run resumes. An utterance is skipped, and counted, when the
    audio is missing or when the miscue tokens cannot be paired one-to-one with
    the corpus word list (which would attach expert scores to the wrong words).
    """
    import chorus.asr as asr
    from chorus.miscue import detect_miscues

    cache = _load_cache(cache_path)
    records: list[WordRecord] = []
    skipped = 0
    reasons: list[str] = []
    fresh = 0

    def skip(reason: str) -> None:
        nonlocal skipped
        skipped += 1
        if len(reasons) < 10:
            reasons.append(reason)

    try:
        for u in utterances if limit is None else utterances[:limit]:
            key = u.uttid.lower()
            if key not in cache:
                wav = audio_index.get(key)
                if wav is None:
                    skip(f"{u.uttid}: no audio in index")
                    continue
                kw = {}
                if beam_size != 1:
                    kw["beam_size"] = beam_size
                if prompt_passage:
                    kw["initial_prompt"] = u.text
                cache[key] = asr.transcribe(wav, model_size=model_size, **kw).text
                fresh += 1
                if fresh % save_every == 0:
                    _save_cache(cache_path, cache)
            expected_tokens = normalize(u.text)
            results = detect_miscues(
                expected_tokens,
                normalize(cache[key], digit_context=expected_tokens if digit_context else None),
                **({"same_sound": True} if same_sound else {}),
            )
            if len(results) != len(u.words):
                skip(f"{u.uttid}: {len(results)} tokens vs {len(u.words)} corpus words")
                continue
            bad = None
            for res, word in zip(results, u.words):
                toks = normalize(word["text"])
                if toks != [res.expected]:
                    bad = f"{u.uttid}: token {res.expected!r} vs corpus word {word['text']!r}"
                    break
            if bad:
                skip(bad)
                continue
            for res, word in zip(results, u.words):
                records.append(
                    WordRecord(
                        expected=res.expected,
                        heard=res.heard,
                        expert_accuracy=float(word.get("accuracy", 0.0)),
                        status=res.status,
                        uttid=u.uttid,
                    )
                )
    finally:
        _save_cache(cache_path, cache)
    if return_info:
        return records, {"skipped": skipped, "skip_reasons": reasons}
    return records


# --- reporting ------------------------------------------------------------


def _ratio(num: int, den: int, pct: float) -> str:
    return f"{pct:.1%} ({num} of {den})" if den else "n/a (0 of 0)"


def _cmu_words() -> set[str]:
    """CMU pronouncing dictionary words; raises an actionable error if missing."""
    try:
        from nltk.corpus import cmudict

        return set(cmudict.dict())
    except (ImportError, LookupError) as exc:
        raise RuntimeError(
            "The CMU pronouncing dictionary is unavailable "
            f"({type(exc).__name__}). Install nltk (see requirements.txt) and run: "
            "python -m nltk.downloader cmudict"
        ) from exc


#: Digit renderings of number words, to count ASR digit-vs-word false flags.
NUMBER_DIGITS = {
    "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9",
    "ten": "10", "eleven": "11", "twelve": "12", "thirteen": "13",
    "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
    "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30",
    "forty": "40", "fifty": "50", "sixty": "60", "seventy": "70",
    "eighty": "80", "ninety": "90", "hundred": "100",
}

LIMITATIONS_TEMPLATE = (
    "Mandarin-L1 only (all 250 speakers of the speechocean762 corpus); ASR was "
    "{model} on CPU; one seeded sample of {n_utts} utterances from the corpus test "
    "split. This is not a general product claim. Most baseline false flags are not "
    "accent-shaped (ASR/text mismatch such as in->into), so the ASR sets the "
    "ceiling on what an accent filter can withdraw. Number words that Whisper "
    "renders as digits are normalised by miscue.normalize for integers 0-999 "
    "(larger or mixed tokens such as 2599 or 1st are left unchanged). Of the "
    "{fp} baseline false flags, {n_sub} are substitutions, {n_om} omissions and "
    "{n_ins} insertions; an INSERTION-status false flag is a word read "
    "correctly with an extra word nearby, which the accent filter cannot touch. "
    "Final-consonant deletion cannot distinguish an accent from a dropped "
    "inflection: {bad} of {tp} genuine errors (expert accuracy < 8.0) were "
    "excused, e.g. {examples}."
)


def summarise(records: list[WordRecord], language: str, seed: int, n_boot: int = 1000,
              model: str = "unknown") -> dict:
    m = evaluate(records, language)
    ci = bootstrap_ci(records, language, n=n_boot, seed=seed)
    per = [(r, *flags(r, language)) for r in records]
    excused = [(r, e) for r, _, _, e in per if e]
    cmu = _cmu_words()
    real = sum(1 for r, _ in excused if r.heard and r.heard.lower() in cmu)
    rng = random.Random(seed)
    sample = rng.sample(excused, min(40, len(excused)))
    fps = [r for r, b, a, e in per if b and r.expert_accuracy >= EXPERT_CORRECT]
    fp_sample = rng.sample(fps, min(10, len(fps)))
    n = len(records)
    bad_excused = [r for r, _ in excused if r.expert_accuracy < EXPERT_CORRECT]
    ex_text = ", ".join(f"{r.expected}->{r.heard}" for r in bad_excused[:3]) or "none"
    digit_fps = sum(
        1 for r in fps if r.heard is not None and r.heard == NUMBER_DIGITS.get(r.expected)
    )
    any_digit_fps = sum(
        1 for r in fps if r.heard is not None and any(c.isdigit() for c in r.heard)
    )
    n_correct = sum(r.expert_accuracy >= EXPERT_CORRECT for r in records)
    # Baseline false flags by status. Only substitutions are the kind of thing
    # the accent filter can touch; "total" always equals fp_before.
    by_status = {"substitution": 0, "omission": 0, "insertion": 0}
    for r in fps:
        by_status[r.status.value] += 1
    by_status_out = {**by_status, "total": sum(by_status.values())}
    return {
        "limitations": LIMITATIONS_TEMPLATE.format(
            model=model, n_utts=len({r.uttid for r in records}),
            bad=len(bad_excused), tp=m.tp_before, examples=ex_text,
            fp=m.fp_before, n_sub=by_status["substitution"],
            n_om=by_status["omission"], n_ins=by_status["insertion"],
        ),
        "genuine_errors_excused": len(bad_excused),
        "baseline_false_flag_rate_on_expert_correct": {
            "rate": (m.fp_before / n_correct) if n_correct else None,
            "fp": m.fp_before,
            "expert_correct": n_correct,
        },
        "false_flags_by_status": by_status_out,
        # The two digit fields below are now a regression indicator for
        # miscue.normalize: they should stay near 0 for integers 0-999.
        "digit_rendering_false_flags": digit_fps,
        "false_flags_with_any_digit_in_heard": any_digit_fps,
        "words": n,
        "utterances": len({r.uttid for r in records}),
        "counts_by_status": dict(Counter(r.status.value for r in records)),
        "expert_correct": sum(r.expert_accuracy >= EXPERT_CORRECT for r in records),
        "expert_mispronounced": sum(r.expert_accuracy < EXPERT_CORRECT for r in records),
        "heard_verbatim": sum(r.status is WordStatus.CORRECT for r in records),
        "fp_before": m.fp_before,
        "fp_after": m.fp_after,
        "tp_before": m.tp_before,
        "tp_after": m.tp_after,
        "fp_reduction": m.fp_reduction if m.fp_before else None,
        "retention": m.retention if m.tp_before else None,
        "fp_reduction_ci95": list(ci["fp_reduction"]) if m.fp_before else None,
        "retention_ci95": list(ci["retention"]) if m.tp_before else None,
        "bootstrap_resamples": {
            "fp_reduction": ci["n_resamples_fp_reduction"],
            "retention": ci["n_resamples_retention"],
            "requested": n_boot,
        },
        "baseline_flag_rate": sum(b for _, b, _, _ in per) / n,
        "filtered_flag_rate": sum(a for _, _, a, _ in per) / n,
        "excused_words": len(excused),
        "excused_heard_is_real_english_word": real,
        "excused_real_word_dictionary": "nltk cmudict",
        "excused_sample": [[r.expected, r.heard, r.expert_accuracy] for r, _ in sample],
        "false_positive_cases": [
            {
                "expected": r.expected,
                "heard": r.heard,
                "expert_accuracy": r.expert_accuracy,
                "status": r.status.value,
                "excused": is_excused(r, language),
            }
            for r in fp_sample
        ],
    }


def split_ids(split: str) -> list[str]:
    """Utterance ids of a corpus split directory (``test`` or ``train``)."""
    from eval.fetch_speechocean import DEFAULT_DEST

    return read_test_ids(next(DEFAULT_DEST.rglob(f"{split}/text")).parent)


def main(argv: list[str] | None = None) -> None:
    from eval.fetch_speechocean import build_audio_index, load_scores

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default="base.en",
                    help="faster-whisper model size, e.g. base.en or small.en")
    ap.add_argument("--limit", type=int, default=500,
                    help="number of test-split utterances to sample")
    ap.add_argument("--seed", type=int, default=0,
                    help="seed for the utterance sample, excused-word samples and bootstrap")
    ap.add_argument("--language", default="mandarin",
                    help="L1 ruleset to evaluate (learner's first language)")
    ap.add_argument("--results", type=Path, default=RESULTS_PATH,
                    help="where to write the JSON summary")
    ap.add_argument("--beam-size", type=int, default=1,
                    help="Whisper beam size (default 1 = greedy, the shipped setting)")
    ap.add_argument("--same-sound", action="store_true",
                    help="treat a heard word with the same CMU pronunciation as the "
                         "expected word (two/too) as correct")
    ap.add_argument("--prompt-passage", action="store_true",
                    help="pass the expected passage to Whisper as initial_prompt "
                         "(may hide genuine errors; check retention)")
    ap.add_argument("--digit-context", action="store_true",
                    help="read a Whisper digit run (495) digit-by-digit when the passage does")
    args = ap.parse_args(argv)

    _cmu_words()  # fail before any transcription if the dictionary is missing
    scores = {u.uttid: u for u in load_scores()}
    test_ids = split_ids("test")
    chosen = sample_ids(test_ids, args.limit, args.seed)
    audio_index = build_audio_index()
    missing_scores = [i for i in chosen if i not in scores]
    missing_audio = [i for i in chosen if i.lower() not in audio_index]
    print(f"test ids: {len(test_ids)}; sampled: {len(chosen)}; "
          f"missing from scores.json: {len(missing_scores)}; missing audio: {len(missing_audio)}")
    utterances = [scores[i] for i in chosen if i in scores]

    cache_path = cache_path_for(args.model, args.beam_size, args.prompt_passage)
    records, info = build_records(
        utterances, audio_index, model_size=args.model,
        cache_path=cache_path, return_info=True,
        beam_size=args.beam_size, same_sound=args.same_sound,
        prompt_passage=args.prompt_passage, digit_context=args.digit_context,
    )
    if not records:
        raise RuntimeError(
            f"No records were built ({info['skipped']} utterances skipped: "
            f"{info['skip_reasons']}); refusing to report an empty run."
        )

    s = summarise(records, args.language, args.seed, model=args.model)
    s.update(
        model=args.model, seed=args.seed, limit=args.limit, language=args.language,
        beam_size=args.beam_size, same_sound=args.same_sound,
        prompt_passage=args.prompt_passage, digit_context=args.digit_context,
        transcript_cache=cache_path.name,
        split="test", sampled_ids=len(chosen),
        skipped_utterances=info["skipped"], skip_reasons=info["skip_reasons"],
        missing_from_scores=len(missing_scores), missing_audio=len(missing_audio),
    )

    n = s["words"]
    print(f"model={args.model} seed={args.seed} limit={args.limit} language={args.language}")
    print(f"utterances used: {s['utterances']}; skipped: {info['skipped']} {info['skip_reasons']}")
    print(f"words: {n}; expert-correct (>=8.0): {s['expert_correct']}; "
          f"mispronounced (<8.0): {s['expert_mispronounced']}")
    print(f"status counts: {s['counts_by_status']}")
    print(f"heard verbatim: {s['heard_verbatim']} of {n} ({s['heard_verbatim'] / n:.1%})")
    print(f"flag rate before: {s['baseline_flag_rate']:.1%}  after: {s['filtered_flag_rate']:.1%}")
    print(f"fp_before={s['fp_before']} fp_after={s['fp_after']} "
          f"tp_before={s['tp_before']} tp_after={s['tp_after']}")
    if not s["fp_before"]:
        print("WARNING: fp_before == 0, false-positive reduction is UNDEFINED, not 0%.")
    if not s["tp_before"]:
        print("WARNING: tp_before == 0, retention is UNDEFINED, not 0%.")
    m = FilterMetrics(s["fp_before"], s["fp_after"], s["tp_before"], s["tp_after"])
    ci_f, ci_r = s["fp_reduction_ci95"], s["retention_ci95"]
    print("false-positive reduction: "
          + _ratio(m.fp_before - m.fp_after, m.fp_before, m.fp_reduction)
          + (f"  95% CI [{ci_f[0]:.1%}, {ci_f[1]:.1%}]" if ci_f else ""))
    print("genuine-error retention : "
          + _ratio(m.tp_after, m.tp_before, m.retention)
          + (f"  95% CI [{ci_r[0]:.1%}, {ci_r[1]:.1%}]" if ci_r else ""))
    ex = s["excused_words"]
    print(f"excused words: {ex}; heard word is real English (cmudict): "
          f"{s['excused_heard_is_real_english_word']} of {ex}")
    print("excused sample (expected, heard, expert_accuracy):")
    for t in s["excused_sample"]:
        print("  ", tuple(t))
    print("expert-correct words flagged before filtering (sample):")
    for c in s["false_positive_cases"]:
        print(f"   {c['expected']} -> {c['heard']}, {c['expert_accuracy']}, "
              f"{c['status']}, excused={c['excused']}")

    with open(args.results, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(s, indent=2) + "\n")
    print(f"wrote {args.results}")


if __name__ == "__main__":
    main()
