# Chorus setup and handoff notes

## What this is

Chorus is a reading-fluency analysis engine. Given an audio recording and the passage that was meant to be read, it runs speech recognition (ASR), detects miscues (differences between the passage and what was heard), force-aligns the expected words to the audio for timing, scores accuracy and pace (WCPM), and applies an L1 filter that separates pronunciation differences explained by a reader's home language from other differences. This branch (`chorus-app`) contains the Phase 1 engine and its evaluation harness. There is no web app yet.

## Environment (CPU dev machine)

Facts about the machine this was developed on: Windows, Python 3.12.7, CPU only, torch `2.7.1+cpu`, numpy `1.26.4`.

The venv lives at `KasRep/.venv`. Its `pyvenv.cfg` records that it was created as:

```
python -m venv --system-site-packages .venv
```

using an Anaconda Python 3.12. This has two consequences.

### OpenMP clash (numpy)

With `--system-site-packages` on Anaconda, the MKL-built numpy from Anaconda and CTranslate2's bundled OpenMP runtime both load an OpenMP library, and the process aborts with:

```
OMP: Error #15: libiomp5md.dll already initialized
Fatal Python error: Aborted
```

Fix used here: a numpy installed inside the venv from PyPI, which shadows the Anaconda one:

```
.venv/Scripts/python -m pip install --force-reinstall --no-deps --ignore-installed numpy==1.26.4
```

Alternative: create the venv without `--system-site-packages` and install `requirements.txt` into it.

Check (run on this machine): `import numpy` in the venv reports version `1.26.4` and a path under `KasRep\.venv\Lib\site-packages`.

Last resort only: setting `KMP_DUPLICATE_LIB_OK=TRUE` hides the error. Intel documents this as unsafe (it can produce silently wrong numerics). It was not used here and is not recommended.

### torch

`requirements.txt` pins plain `torch==2.7.1` and `torchaudio==2.7.1`. This dev machine has `2.7.1+cpu`. A fresh Linux install from PyPI is expected to give the CUDA build, which suits a GPU machine. This was not verified (no Linux or GPU machine was available).

### Not re-verified on a clean machine

Recreating the venv from scratch (either route above) was not repeated for this document, because it would re-download torch. The numpy fix and the pins reflect the working venv; a from-scratch install is untested.

## Data and model downloads

Nothing here is committed to git. `eval/data/` and `.venv/` are in `.gitignore`.

| What | Needed by | How | Size / notes |
| --- | --- | --- | --- |
| nltk `averaged_perceptron_tagger_eng` | `g2p_en` (phoneme lookup) | `python -m nltk.downloader averaged_perceptron_tagger_eng` (required, see below) | not measured |
| nltk `cmudict` | the evaluation (real-word check on excused words) | `python -m nltk.downloader cmudict` | the evaluation checks at start and prints this command if it is missing; whether the test suite needs it was not checked (it is present here) |
| Whisper `base.en` | `transcribe` | automatic on first call, Hugging Face cache | about 75 MB (from the task notes, not measured) |
| torchaudio `MMS_FA` bundle | `align_words` | automatic on first call, torch hub cache | large; size not measured |
| speechocean762 corpus | the evaluation | `python -m eval.fetch_speechocean` | archive is 520,810,923 bytes (about 497 MiB, verified from the file on disk); the download took about 55 minutes on this machine (from the task notes). Extracts under `eval/data/speechocean762/`; the marker file `.extracted` means extraction finished |

Run these from `KasRep`.

### nltk data is a mandatory step

`g2p_en` does not fetch `averaged_perceptron_tagger_eng` itself with nltk 3.9.x. On this machine the first test run failed with `LookupError: ... taggers/averaged_perceptron_tagger_eng` until the resource was downloaded by hand (Task 5 report). Without it, the first phoneme lookup (`to_phonemes`) fails, which covers any `analyze` call, the miscue-to-L1 path and the L1 tests. Run this BEFORE the first test or evaluation run:

```
python -m nltk.downloader averaged_perceptron_tagger_eng
python -m nltk.downloader cmudict
```

`cmudict` is needed by the evaluation, which checks for it at start and stops with the command above if it is missing. Whether anything else needs it was not checked.

Where the data lands. On this machine `nltk.data.find` reports:

```
taggers/averaged_perceptron_tagger_eng -> KasRep\.venv\share\nltk_data\taggers\averaged_perceptron_tagger_eng
corpora/cmudict                        -> C:\Users\rohan\AppData\Roaming\nltk_data\corpora\cmudict
```

The tagger was downloaded with `-d .venv/share/nltk_data`, which is on `nltk.data.path`. With no `-d`, nltk's `Downloader.default_download_dir` (read in the installed nltk) uses the first existing, writable entry of `nltk.data.path`, and otherwise `%APPDATA%\nltk_data` on Windows or `~/nltk_data` elsewhere. Which one that is depends on the machine, so check with `python -c "import nltk; print(nltk.data.path)"`.

## Running things

Run all commands from `KasRep`. The examples use the Windows venv path; on Linux use `.venv/bin/python`.

The `PYTHONPATH=... command` prefixes below assume Git Bash (or a POSIX shell); they fail in PowerShell and cmd. PowerShell equivalent, verified for the `--help` command (it prints the usage text):

```
$env:PYTHONPATH="src;."; .venv\Scripts\python -m eval.evaluate_l1_filter --help
```

`pytest.ini` sets `pythonpath = src`, but only pytest reads it. Any plain `python` command that imports `chorus` needs `PYTHONPATH` set. Verified: without it, `python -m eval.evaluate_l1_filter --help` and `from chorus.pipeline import analyze` both fail with `ModuleNotFoundError: No module named 'chorus'`. The separator is `;` on Windows and `:` on Linux.

Fast tests (verified: 150 passed, 11 deselected, about 16 s):

```
.venv/Scripts/python -m pytest -m "not slow"
```

All tests including those marked `slow` (verified: 161 passed in about 88 s on this machine with models and corpus already cached; on a fresh machine they download models, and the corpus test skips itself if the corpus is absent):

```
.venv/Scripts/python -m pytest -m "slow or not slow"
```

`pytest.ini` has no `-m` filter in `addopts`, so plain `pytest` already runs everything and is equivalent to the command above.

One file (verified: 21 passed):

```
.venv/Scripts/python -m pytest tests/test_miscue.py
```

The evaluation. It writes `eval/results.json`, and caches transcripts in `eval/data/transcripts_<model>.json`, so a re-run does not call Whisper again. Only its `--help` was re-run for this document; the numbers below come from the existing `eval/results.json`:

```
PYTHONPATH="src;." .venv/Scripts/python -m eval.evaluate_l1_filter --model base.en --limit 500 --seed 0 --language mandarin
```

Options: `--model` (faster-whisper size), `--limit` (test-split utterances to sample), `--seed`, `--language` (L1 ruleset), `--results` (output path).

`analyze()` on the bundled fixture (run on this machine, models cached). The fixture is a synthetic Windows text-to-speech voice, so this shows that the pipeline runs, not accuracy on real readers:

```
PYTHONPATH=src .venv/Scripts/python -c "
from chorus.pipeline import analyze
a = analyze('tests/fixtures/the_cat_sat.wav', 'The cat sat on the mat.', language='somali')
print(a.score); print(a.accent_adjusted)
for w in a.words: print(w.expected, w.status.value, w.start, w.end)
"
```

Output:

```
ReadingScore(accuracy=1.0, wcpm=175.609756097561, total_words=6, correct_words=6, duration_s=2.05, long_pauses=0)
ReadingScore(accuracy=1.0, wcpm=175.609756097561, total_words=6, correct_words=6, duration_s=2.05, long_pauses=0)
the correct 0.12058823529411763 0.18088235294117644
cat correct 0.24117647058823527 0.4220588235294117
sat correct 0.48235294117647054 0.6833333333333332
on correct 0.7637254901960784 0.8240196078431372
the correct 0.8441176470588234 0.9245098039215686
mat correct 0.9647058823529411 1.2259803921568626
```

## Moving to the GPU machine

Copy or clone:

- The repo at this branch.
- Optionally `eval/data/transcripts_base.en.json`. It is git-ignored, keyed by utterance id, and does not depend on the machine, so it saves re-transcribing with the same model. It is valid only for `base.en`: the model name is part of the file name, and a `small.en` run uses its own `transcripts_small.en.json`.

Install: create a venv (preferably without `--system-site-packages`), run `pip install -r requirements.txt`, then run the two nltk downloads (mandatory, see the nltk section above) and fetch the corpus. A CUDA-enabled torch is needed for the GPU (see the torch note above; unverified).

Bigger evaluation. The corpus test split has 2,500 utterance ids, so 2,500 is the maximum for `--limit`:

```
PYTHONPATH="src:." .venv/bin/python -m eval.evaluate_l1_filter --model small.en --limit 2500 --seed 0 --language mandarin
```

(Use `;` instead of `:` and `.venv/Scripts/python` on Windows.) This overwrites `eval/results.json`; pass `--results some/other/path.json` to keep the current one.

### The device is hardcoded to CPU (code change needed, not in this branch)

The CPU-only assumption is hardcoded. In `src/chorus/asr.py`, line 28, inside `_get_model`:

```python
return WhisperModel(model_size, device="cpu", compute_type="int8")
```

To use a CUDA GPU this would need to become something like `device="cuda"` with a compute type such as `"float16"` (or `"int8_float16"`). These exact values were not tested. The module docstring (lines 1-9) and the `_get_model` docstring (line 25) also describe the CPU and int8 assumption, and the module docstring mentions a 2 GB GPU and says not to use the `medium` model. That change is not part of this branch.

The alignment stage runs on CPU too. `src/chorus/align.py` never selects a device: the MMS_FA model comes from `bundle.get_model()` and the waveform from `_load_audio`, and neither is moved with `.to(device)` (the only `.to(...)` call, line 45, converts dtype to float32). Putting alignment on the GPU would be a separate change, also not in this branch.

## Current measured result

From `eval/results.json` (`base.en`, seed 0, Mandarin, 500 utterances from the speechocean762 test split, 3,219 words):

| Metric | Value | 95% CI |
| --- | --- | --- |
| fp_reduction (false flags on expert-correct words that the filter withdrew) | 2.0% (14 of 700) | [1.0%, 3.2%] |
| retention (expert-mispronounced words still flagged after filtering) | 97.5% (234 of 240) | [95.4%, 99.2%] |

The CIs are bootstrap intervals (1,000 resamples).

The baseline flags 23.8% (700 of 2,936) of expert-correct words, mostly for reasons unrelated to accent, so the ASR sets the ceiling on what an accent filter can withdraw.

The `limitations` field, verbatim:

> Mandarin-L1 only (all 250 speakers of the speechocean762 corpus); ASR was base.en on CPU; one seeded sample of 500 utterances from the corpus test split. This is not a general product claim. Most baseline false flags are not accent-shaped (ASR/text mismatch such as in->into, or digits for number words), so the ASR sets the ceiling on what an accent filter can withdraw. Final-consonant deletion cannot distinguish an accent from a dropped inflection: 6 of 240 genuine errors (expert accuracy < 8.0) were excused, e.g. its->it, opened->open, looked->look.

## Known limitations and deferred items

None of these are working; do not treat them as such.

- **Epenthesis and hesitation.** `epenthesis` is loaded from the rule data (`src/chorus/l1/engine.py`; set in the Mandarin, Somali and Spanish data files) but `is_accent_variant` does not match on it. Deferred (controller ruling R6). The `HESITATION` status is defined in `src/chorus/types.py` but `detect_miscues` never assigns it; pacing is covered by `long_pauses`.
- **The accent filter is phonology-only.** It cannot tell an accent from a different real word (rock -> lock, pig -> big), or from a dropped inflection (opened -> open, looked -> look). In the measured sample, 6 of 240 genuine errors were excused.
- **Only Mandarin is `validated`** (measured against expert labels), because all 250 speakers in speechocean762 are Mandarin L1. Somali and Spanish are `shipped`: rules taken from published descriptions, not measured. Hmong and Karen are not encoded yet.
- **Number words.** Whisper renders spoken number words as digits ("two" -> "2"). `miscue.normalize` does not map digits to words, so correctly read number words are scored as substitutions. In the measured sample, 57 of the 700 baseline false flags contain a digit, and 48 are plain word -> digit renderings. Not fixed in this branch.
- **Alignment.** `align_words` rebuilds the alignment model on every call (about 2 s, from the task notes; not re-timed) and accepts only `[a-z']+` words. The pipeline aligns only alignable, non-omitted words.
- **WCPM.** `analyze` uses the whole recording duration, so leading and trailing silence lowers WCPM.
- **No voice-activity filter.** faster-whisper's `vad_filter` defaults to `False` and the code does not set it, so hallucinated words on quiet real audio would appear as insertions. This is untested on real recordings. The only spoken fixture is a synthetic Windows text-to-speech voice, which proves the plumbing only, not accuracy on children or accented readers.
- **Phase 2 does not exist.** No FastAPI service, no React onboarding (grade band, home language), no teacher or parent views, no deployment.
