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
| nltk `cmudict` | the evaluation (real-word check on excused words) | `python -m nltk.downloader cmudict` | the evaluation checks at start and prints this command if it is missing; the test suite needs it too (see below) |
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

`cmudict` is needed by the evaluation, which checks for it at start and stops with the command above if it is missing. The test suite needs it as well: `tests/test_evaluate_l1_filter.py::test_summarise_limitations_and_digit_counts` calls `summarise`, which reaches `_cmu_words()`.

So the fast suite needs the nltk data: the `_eng` tagger for every test that reaches `to_phonemes`, and `cmudict` for the evaluation tests. The tests do not skip cleanly without it; they fail.

One more thing to know: importing `g2p_en` attempts a network download of the legacy resources (`averaged_perceptron_tagger` and `cmudict`, `g2p_en/g2p.py` lines 21-28) when they are not found, before the `_eng` tagger `LookupError` appears. On an offline machine that first import can stall or print download errors; run the two downloads above first.

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

Fast tests (verified after the final fix wave: 181 passed, 11 deselected, about 15 s):

```
.venv/Scripts/python -m pytest -m "not slow"
```

All tests including those marked `slow` (verified after the final fix wave: 192 passed in about 73 s on this machine with models and corpus already cached; on a fresh machine they download models, and the corpus test skips itself if the corpus is absent):

```
.venv/Scripts/python -m pytest -m "slow or not slow"
```

`pytest.ini` has no `-m` filter in `addopts`, so plain `pytest` already runs everything and is equivalent to the command above.

One file (verified: 44 passed):

```
.venv/Scripts/python -m pytest tests/test_miscue.py
```

The evaluation. It writes `eval/results.json`, and caches transcripts in `eval/data/transcripts_<model>.json`, so a re-run does not call Whisper again. It was re-run from the transcript cache after the number-word normalisation (no Whisper call); the numbers below come from the regenerated `eval/results.json`:

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

The alignment stage runs on CPU too. `src/chorus/align.py` never selects a device: the MMS_FA model comes from `bundle.get_model()` and the waveform from `_load_audio`, and neither is moved with `.to(device)` (the only `.to(...)` call, line 48, converts dtype to float32). Putting alignment on the GPU would be a separate change, also not in this branch.

## Current measured result

From `eval/results.json` (`base.en`, seed 0, Mandarin, 500 utterances from the speechocean762 test split, 3,219 words; 0 utterances skipped):

| Metric | Value | 95% CI |
| --- | --- | --- |
| fp_reduction (false flags on expert-correct words that the filter withdrew) | 2.2% (14 of 645) | [1.1%, 3.4%] |
| retention (expert-mispronounced words still flagged after filtering) | 97.5% (233 of 239) | [95.4%, 99.2%] |

The CIs are bootstrap intervals (1,000 resamples).

The effect of the filter on this sample is small. The baseline (no filter) flags 22.0% (645 of 2,936) of expert-correct words, mostly for reasons unrelated to accent, so the ASR sets the ceiling on what an accent filter can withdraw. `false_flags_by_status` breaks those 645 baseline false flags down: 520 substitutions, 48 omissions, 77 insertions (total 645, equal to `fp_before`). Only the substitution share is the kind of thing an accent filter can touch. Overall, 27.5% of all words are flagged by the baseline and 26.8% after filtering.

Number-word normalisation changed this result. Before it, the same sample gave 14 of 700 false flags withdrawn (2.0%) and 234 of 240 genuine errors retained (97.5%); 55 baseline false flags and one genuine-error flag (expected "one", ASR "1") disappeared once digits were mapped to words. After it, `digit_rendering_false_flags` is 0 and `false_flags_with_any_digit_in_heard` is 1; these two fields now act as a regression indicator for `miscue.normalize`.

The `limitations` field, verbatim:

> Mandarin-L1 only (all 250 speakers of the speechocean762 corpus); ASR was base.en on CPU; one seeded sample of 500 utterances from the corpus test split. This is not a general product claim. Most baseline false flags are not accent-shaped (ASR/text mismatch such as in->into), so the ASR sets the ceiling on what an accent filter can withdraw. Number words that Whisper renders as digits are normalised by miscue.normalize for integers 0-999 (larger or mixed tokens such as 2599 or 1st are left unchanged). Of the 645 baseline false flags, 520 are substitutions, 48 omissions and 77 insertions; an INSERTION-status false flag is a word read correctly with an extra word nearby, which the accent filter cannot touch. Final-consonant deletion cannot distinguish an accent from a dropped inflection: 6 of 239 genuine errors (expert accuracy < 8.0) were excused, e.g. its->it, opened->open, looked->look.

### Reducing false error flags (2,500 utterances, GPU)

Seeded sample of 2,500 utterances from the speechocean762 test split (Mandarin L1, 15,967 words; 14,644 expert-correct, 1,323 expert-mispronounced), GPU, from `eval/results_*.json`. "False flags" are expert-correct words the reader was flagged on before any accent filter. "Genuine errors flagged" counts expert-mispronounced words flagged before and after the Mandarin filter. fp_reduction and retention are the accent filter's effect (bootstrap 95% CI as low-high, 1,000 resamples).

| Configuration | False flags on expert-correct words | Genuine errors flagged, before to after filter | fp_reduction (95% CI) | retention (95% CI) |
| --- | --- | --- | --- | --- |
| small.en default | 2530 of 14,644 (17.3%) | 972 to 954 of 1,323 | 2530 to 2469, 2.4% (1.8-3.1) | 98.1% (97.3-98.9) |
| small.en beam 5 | 2426 of 14,644 (16.6%) | 976 to 958 of 1,323 | 2426 to 2355, 2.9% (2.3-3.6) | 98.2% (97.3-98.9) |
| small.en beam 5 + same-sound | 2366 of 14,644 (16.2%) | 975 to 957 of 1,323 | 2366 to 2295, 3.0% (2.3-3.7) | 98.2% (97.3-98.9) |
| small.en beam 5 + same-sound + digit-context (shipped) | 2318 of 14,644 (15.8%) | 974 to 956 of 1,323 | 2318 to 2247, 3.1% (2.4-3.8) | 98.2% (97.3-98.9) |
| small.en beam 5 + same-sound + passage prompt (rejected) | 197 of 14,644 (1.3%) | 231 to 228 of 1,323 | 197 to 187, 5.1% (2.4-8.4) | 98.7% (97.1-100.0) |
| base.en default | 3251 of 14,644 (22.2%) | 1063 to 1036 of 1,323 | 3251 to 3166, 2.6% (2.1-3.2) | 97.5% (96.5-98.4) |
| base.en beam 5 + same-sound | 2981 of 14,644 (20.4%) | 1062 to 1035 of 1,323 | 2981 to 2896, 2.9% (2.3-3.4) | 97.5% (96.5-98.3) |
| base.en beam 5 + same-sound + digit-context | 2971 of 14,644 (20.3%) | 1062 to 1035 of 1,323 | 2971 to 2886, 2.9% (2.3-3.5) | 97.5% (96.5-98.3) |

- **Beam 5** decodes with a beam of five candidate transcripts instead of greedy decoding, so Whisper more often picks the word actually said. It is roughly twice as slow on CPU.
- **Same-sound** counts a heard word as correct when it has the same CMU-dictionary pronunciation as the expected word (two/too, their/there): the recogniser chose a spelling, the reader said the right sound.
- **Digit-context** reads a run of digits Whisper wrote as one number (such as 495) digit by digit when the passage has the digits spelled out that way, and as a cardinal otherwise.

Passage prompting (giving Whisper the passage as `initial_prompt`) was tested and rejected. It cuts false flags to 197, but only because it hides genuine errors: Whisper writes the expected word even when the reader said something else, and the number of genuine errors flagged falls from 976 (beam 5 alone) to 231. It stays off, and the API does not expose it.

The app defaults are small.en, beam 5, same-sound on, digit-context on (`CHORUS_ASR_MODEL`, `CHORUS_BEAM_SIZE=5`, `CHORUS_SAME_SOUND=1`, `CHORUS_DIGIT_CONTEXT=1` in the Dockerfile and `deploy/hf_gradio/app.py`; the API reads them per request). Set `CHORUS_ASR_MODEL=base.en` and/or `CHORUS_BEAM_SIZE=1` if analysis is too slow. The accent filter itself is unchanged and still withdraws only about 3% of false flags.

## Known limitations and deferred items

None of these are working; do not treat them as such.

- **Epenthesis and hesitation.** `epenthesis` is loaded from the rule data (`src/chorus/l1/engine.py`; set in the Mandarin, Somali and Spanish data files) but `is_accent_variant` does not match on it. Deferred (controller ruling R6). The `HESITATION` status is defined in `src/chorus/types.py` but `detect_miscues` never assigns it; pacing is covered by `long_pauses`.
- **The accent filter is phonology-only.** It cannot tell an accent from a different real word (rock -> lock, pig -> big), or from a dropped inflection (opened -> open, looked -> look). In the measured sample, 6 of 239 genuine errors were excused.
- **Only Mandarin is `validated`** (measured against expert labels), because all 250 speakers in speechocean762 are Mandarin L1. Somali and Spanish are `shipped`: rules taken from published descriptions, not measured. Hmong and Karen are not encoded yet.
- **Number words.** Whisper renders spoken number words as digits ("two" -> "2"). `miscue.normalize` now maps canonical integers 0 to 999 to English words on both the passage and the transcript ("21" -> "twenty one", "101" -> "one hundred one", no "and"), so they match. Larger or mixed tokens such as 2599 or 1st are left unchanged and stay untimed (the aligner takes letters and apostrophes only). Decimals and thousands separators are split by the punctuation rule first, so "3.5" reads as "three five" and "1,000" as "one" and "000".
- **INSERTION can sit on a correctly read word.** With one status per expected word, an insertion (an extra word the reader added) is recorded on an adjacent expected word only when that word was read correctly, so a word with status INSERTION can have `heard == expected`. In the measured sample, 77 of the 645 baseline false flags are of this kind (`false_flags_by_status`). A UI must not colour these as misread; render them as "extra word added nearby". The number of extra words is not represented.
- **Somali `cluster_reduction` fires on any consonant run.** The flag currently applies to any consonant run, not only word-initial s-clusters (the cited source concerns those), so it can excuse a change like "plan" -> "pan". The rule was not changed in this branch.
- **Alignment cost grows faster than the audio length, with no length guard.** Measured on this machine (CPU, alignment only, the fixture tiled to length): 10 s of audio took 4.8 s, 30 s took 9.9 s, 60 s took 21.8 s and 120 s took 63.5 s. `align_words` does one forward pass over the whole waveform, with no chunking, cap or timeout. Phase 2 needs chunking or a duration cap before accepting real recordings of arbitrary length.
- **Alignment.** `align_words` rebuilds the alignment model on every call (about 2 s, from the task notes; not re-timed) and accepts only `[a-z']+` words. The pipeline aligns only alignable, non-omitted words.
- **WCPM.** `analyze` uses the whole recording duration, so leading and trailing silence lowers WCPM.
- **No voice-activity filter.** faster-whisper's `vad_filter` defaults to `False` and the code does not set it, so hallucinated words on quiet real audio would appear as insertions. This is untested on real recordings. The only spoken fixture is a synthetic Windows text-to-speech voice, which proves the plumbing only, not accuracy on children or accented readers.
- **Phase 2 does not exist.** No FastAPI service, no React onboarding (grade band, home language), no teacher or parent views, no deployment.

## Running the FastAPI service (`chorus_api`)

Source the environment, then run uvicorn from the repo root:

```
source /lustre/smuexa01/client/users/rbankapur/chorus_scratch/env.sh
python -m uvicorn chorus_api.app:app --host 0.0.0.0 --port 8000
```

Useful env vars (all optional):

| Var | Default | Effect |
| --- | --- | --- |
| `CHORUS_DB` | `./chorus.db` | SQLite file path (students, sessions; audio is never stored) |
| `CHORUS_ASR_MODEL` | `base.en` | faster-whisper model size passed to `chorus.pipeline.analyze` |
| `CHORUS_WARMUP` | unset | set to `1` to load the Whisper and aligner models on startup, so the first real request isn't the one that pays the load cost |

`GET /api/health`, `/api/languages`, `/api/passages` need no model. `POST
/api/analyze` loads `base.en` (faster-whisper) and the MMS_FA aligner on its
first call unless `CHORUS_WARMUP=1` was set; both are cached per process
afterwards (`chorus.asr._get_model`, `chorus.align._get_model_bundle`).

If `web/dist/` exists (the built React app), `GET /` and any other
non-`/api` path serve it, with unknown paths falling back to
`web/dist/index.html` (client-side routing). Until then, only the `/api/*`
routes exist.

Login node has a 16 GB per-user memory cap: do not start a second
model-loading process (another `uvicorn` run, a `python -c "from chorus...`
smoke test, etc.) while this one is loading models, and stop the server
(`Ctrl-C`, or kill the uvicorn process) once you are done with it.

## Run the whole app locally

This builds the React frontend and serves it from the same FastAPI process
that answers `/api/*`, so there is nothing to proxy.

```
cd web
export PATH="/lustre/smuexa01/client/users/rbankapur/chorus_scratch/node/node-v22.20.0-linux-x64/bin:$PATH"
npm run build          # tsc --noEmit, then web/dist
cd ..
source /lustre/smuexa01/client/users/rbankapur/chorus_scratch/env.sh
python -m uvicorn chorus_api.app:app --port 8000
```

Then open `http://localhost:8000`. `GET /` and any other non-`/api` path
(e.g. `/read/el-01`, `/teacher`) serve `web/dist/index.html`; `/api/*` still
answers normally (see "Running the FastAPI service" above).

In VS Code Remote, the Ports panel forwards port 8000 to the browser running
on the user's own machine, not to anything on the remote host. The
microphone works there because that forwarded `localhost:8000` is the
browser's own `localhost`, which browsers treat as a secure origin (same as
`https://`) even though the traffic is plain HTTP over the tunnel — a
microphone prompt would otherwise require HTTPS.
