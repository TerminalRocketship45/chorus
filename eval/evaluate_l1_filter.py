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
"""
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import chorus.pipeline as pipeline
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
    """Ask the real pipeline filter whether this word would be accent-excused."""
    word = WordResult(index=0, expected=r.expected, heard=r.heard, status=r.status)
    return bool(pipeline.apply_l1_filter([word], language)[0].accent_excused)


def flags(r: WordRecord, language: str) -> tuple[bool, bool, bool]:
    """(flagged_before, flagged_after, excused) for one word."""
    flagged_before = r.status in ERROR_STATUSES
    excused = flagged_before and is_excused(r, language)
    return flagged_before, flagged_before and not excused, excused


def evaluate(records: list[WordRecord], language: str) -> FilterMetrics:
    """Build the before/after confusion counts for one language."""
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


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
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
    zero are left out of that ratio's interval. Returns
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


def build_records(
    utterances,
    audio_index: dict[str, Path],
    limit: int | None = None,
    model_size: str = "base.en",
    cache_path: Path | None = None,
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
                cache[key] = asr.transcribe(wav, model_size=model_size).text
                fresh += 1
                if fresh % save_every == 0:
                    _save_cache(cache_path, cache)
            expected_tokens = normalize(u.text)
            results = detect_miscues(expected_tokens, normalize(cache[key]))
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
    from nltk.corpus import cmudict

    return set(cmudict.dict())


def summarise(records: list[WordRecord], language: str, seed: int, n_boot: int = 1000) -> dict:
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
    return {
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


def main(argv: list[str] | None = None) -> None:
    from eval.fetch_speechocean import DEFAULT_DEST, build_audio_index, load_scores

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default="base.en")
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--language", default="mandarin")
    ap.add_argument("--results", type=Path, default=RESULTS_PATH)
    args = ap.parse_args(argv)

    scores = {u.uttid: u for u in load_scores()}
    test_dir = next(DEFAULT_DEST.rglob("test/text")).parent
    test_ids = read_test_ids(test_dir)
    chosen = sample_ids(test_ids, args.limit, args.seed)
    audio_index = build_audio_index()
    missing_scores = [i for i in chosen if i not in scores]
    missing_audio = [i for i in chosen if i.lower() not in audio_index]
    print(f"test ids: {len(test_ids)}; sampled: {len(chosen)}; "
          f"missing from scores.json: {len(missing_scores)}; missing audio: {len(missing_audio)}")
    utterances = [scores[i] for i in chosen if i in scores]

    cache_path = CACHE_DIR / f"transcripts_{args.model}.json"
    records, info = build_records(
        utterances, audio_index, model_size=args.model,
        cache_path=cache_path, return_info=True,
    )
    if not records:
        raise RuntimeError(
            f"No records were built ({info['skipped']} utterances skipped: "
            f"{info['skip_reasons']}); refusing to report an empty run."
        )

    s = summarise(records, args.language, args.seed)
    s.update(
        model=args.model, seed=args.seed, limit=args.limit, language=args.language,
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

    args.results.write_text(json.dumps(s, indent=2), encoding="utf-8")
    print(f"wrote {args.results}")


if __name__ == "__main__":
    main()
