# Reading Fluency Coach for Multilingual Learners — Design Spec

**Date:** 2026-09-23
**Target:** Congressional App Challenge 2026, Minnesota's 4th District (Rep. Betty McCollum)
**Hard deadline:** Monday, October 26, 2026, 12:00 PM EDT
**Team:** 3 members (2 resident in MN-04 — satisfies the "at least half" team eligibility rule)

---

## 1. Problem and thesis

69% of Minnesota 4th graders are not proficient in reading — one of the largest achievement gaps in the nation. 148,000 Minnesota students (roughly 20%) speak a heritage language at home, and MN-04 contains the largest Hmong, Somali, and Karen communities in the United States.

Existing oral-reading-fluency tools score a child's reading against a generic English acoustic model. For a student whose first language is not English, predictable L1 pronunciation transfer is scored as reading error. The student is told they are failing at reading when they are reading correctly with an accent.

Speech-language pathology already has a name for this distinction: **"difference or disorder?"** Published clinical resources frame Hmong and Somali speech development in exactly those terms.

**Thesis:** apply the difference/disorder framework to oral reading assessment.

> Do not penalize a reader for their accent. Flag only genuine reading errors.

**One-sentence purpose (for the demonstration video):**
> "[NAME] listens to a student read aloud and scores their reading accuracy, fluency, and pacing word by word — without mistaking a first-language accent for a reading mistake."

## 2. Goals

- Score a read-aloud passage for accuracy, words-correct-per-minute (WCPM), and pacing, word by word.
- Distinguish documented L1 phonological transfer from genuine reading miscues, and report both raw and accent-adjusted accuracy.
- Serve elementary readers (primary) and secondary English learners (secondary) from one codebase.
- Produce a measured, benchmarked accuracy figure against a public labeled corpus.
- Give teachers and parents a progress view.

## 3. Non-goals

- Not a diagnostic or clinical instrument. No claims about speech disorders, dyslexia, or medical conditions.
- Not a general speech-therapy tool.
- Not a replacement for a teacher's running record.
- No accent "correction." The app never tells a student their accent is wrong.
- Not fine-tuning Whisper from scratch (see §9).

## 4. Users

| User | Need |
|---|---|
| Elementary reader, grades 2–5 (primary) | Read a passage, see which words were hard, practice them |
| Secondary English learner | Same, with age-appropriate passages |
| Teacher | Class list, per-student progress, WCPM over time |
| Parent | One child's progress, plain-language summary |

## 5. Competitive context (stated honestly in the submission)

**Microsoft Reading Coach** is free, generally available, supports 81 interface/content languages, gives real-time fluency feedback, detects challenging words and reuses them in later passages, and offers teacher progress tracking. **Amira Learning** is the commercial equivalent.

Those 81 languages are interface and content languages. Neither product is tuned to separate an L1-driven accent from a reading error for a learner reading *English*. That gap is the contribution of this project, and the competitive landscape is acknowledged directly in the video rather than hidden.

## 6. Architecture

```
Audio capture (browser mic)
        |
        v
[2] ASR  ------------------->  hypothesis transcript
        |
        v
[3] Forced alignment  <------- expected passage text
        |
        v  word-level timestamps + phoneme posteriors
[4] Miscue detection  -------> per-word status
        |
        v
[5] Scoring  ----------------> accuracy %, WCPM, pacing, GOP phoneme scores
        |
        v
[6] L1-AWARE FILTER  --------> accent vs. genuine miscue   [CORE CONTRIBUTION]
        |
        v
[7] Feedback UI   [8] Passages   [9] Teacher view
        |
        v
[10] Evaluation harness (offline, against speechocean762)
```

### 6.1 Component detail

**[1] Capture.** Browser MediaRecorder. Passage rendered on screen. Records a single continuous read.

**[2] ASR.** Whisper. For elementary audio, Kid-Whisper's published fine-tuned weights (MyST WER 13.93% to 9.11% on Whisper-Small; 13.23% to 8.61% on Medium). Produces the hypothesis of what was actually said, independent of the expected text.

**[3] Forced alignment.** Aligns audio against the *expected* passage text to obtain word-level timestamps and phoneme-level posteriors. Benchmark Montreal Forced Aligner against WhisperX and pick one; MFA is documented as more accurate for word-level timestamps, WhisperX is faster.

**[4] Miscue detection.** Classify each expected word using the Running Record taxonomy teachers already use:

`correct | substitution | omission | insertion | repetition | self-correction | hesitation`

Derived by aligning the ASR hypothesis against the expected text (edit-distance alignment), plus timing gaps from [3] for hesitation.

**[5] Scoring.**
- Accuracy = correct words / total words
- WCPM = correct words / elapsed minutes (the standard ORF metric)
- Pacing = distribution of inter-word pauses, flagging pauses above a threshold
- Phoneme-level pronunciation via GOP (Goodness of Pronunciation)

**[6] L1-aware filter — the core contribution.** See §8.

**[7] Feedback UI.** Word-by-word colored transcript over the passage. Tap a word to hear a reference pronunciation and see its status. A practice list of genuinely-missed words. Accent-classified words are shown as correct, never as errors.

**[8] Passages.** Two static sets (elementary, secondary), each tagged by interest topic and difficulty level. Static JSON, no generation.

**[9] Teacher/parent view.** Per-student session history, WCPM trend, most-missed words.

**[10] Evaluation harness.** Offline. See §9.

## 7. Data assets

| Asset | Contents | Access |
|---|---|---|
| **speechocean762** | 5,000 English utterances, 250 non-native speakers (L1 Mandarin), **half are children**. Five experts labeled each utterance at sentence level (accuracy, fluency, prosody, completeness, overall; 0–10), word level (accuracy, stress, total; 0–10), and phoneme level (accuracy; 0–2) | OpenSLR. Free for commercial and non-commercial use |
| **MyST** | ~240h transcribed conversational children's speech, grades 3–5 | Public; standard child-ASR benchmark |
| **CSLU / OGI Kids** | ~50h, ~1,100 children K–grade 10 **reading words and sentences aloud** | Public |
| **L2-ARCTIC** | Non-native English with mispronunciation annotations (L1: Hindi, Korean, Mandarin, Spanish, Arabic) | Public |

**speechocean762 is the backbone.** It provides expert ground truth for the exact three dimensions being scored — accuracy, fluency, prosody — on non-native speakers, half of them children. Its limitation is that every speaker's L1 is Mandarin; this shapes the evaluation design in §9 and is stated explicitly in the submission.

### Code to build on

| Repo | Use |
|---|---|
| `ahmedadelattia/Kid-Whisper` | Children's-speech Whisper weights |
| `YuanGongND/gopt` | Transformer multi-aspect pronunciation scoring, trained on speechocean762 (ICASSP 2022) |
| `Halleck45/OpenPronounce` | wav2vec2 + DTW phoneme-level pronunciation assessment |
| `kaldi-asr/kaldi` (`egs/gop_speechocean762`) | Official GOP baseline recipe |
| `m-bain/whisperX` | Word-level timestamps via forced alignment |
| Montreal Forced Aligner | Higher-accuracy alignment baseline |

### Prior work establishing feasibility

- **FLORA** — *Human and Automated Assessment of Oral Reading Fluency*, Journal of Educational Psychology (2013). Automated WCPM within **3–4 words of human scorers** across grades and schools, on 783 one-minute recordings from 313 students. Computer ratings of expressive reading agreed with human raters **better than human raters agreed with each other.** This establishes that the core task is solved and reliable.
- *Deep Learning for Assessment of Oral Reading Fluency* (arXiv 2405.19426)
- *Automatic Assessment of Oral Reading Accuracy for Reading Diagnostics* (arXiv 2306.03444)
- *Benchmarking Children's ASR with Supervised and Self-supervised Speech Foundation Models* (arXiv 2406.10507)
- *speechocean762: An Open-Source Non-native English Speech Corpus For Pronunciation Assessment* (arXiv 2104.01378)
- Witt & Young — Goodness of Pronunciation (GOP), the foundational scoring algorithm

Known documented obstacle: children read slowly, with repetitions and false starts, and have distinct acoustic characteristics. This is why [2] uses child-adapted weights and [4] models repetition and self-correction as first-class categories rather than errors.

## 8. The L1-aware filter

For a declared L1, each phoneme-level deviation detected in [5] is checked against that language's documented transfer patterns. A deviation matching a predicted pattern is classified **accent**; anything else is a **genuine miscue**. The UI reports raw accuracy and accent-adjusted accuracy side by side.

Rules are stored as declarative data (JSON), one file per language, so adding a language requires no code change.

### Encoded patterns

Status labels below use the terminology defined in §9 (*validated* / *shipped* / *drafted*).

**Somali** — *shipped in v1.* Deepest-encoded of the four district languages.
- No word-initial consonant clusters; epenthetic vowel inserted ("stop" becomes `[sitop]` or `[istop]`)
- Syllable structure CV, CVC, V; rarely more than two consonants together, so clusters like `/str/` are reduced or broken
- Phonemes absent from Somali, yielding predictable substitutions: `/p/ /v/ /ʒ/ /tʃ/ /dʒ/ /ŋ/ /θ/ /ð/ /ɹ/`
- Geminate consonants exist in Somali but not English, producing lengthening
- Intervocalic glottal stops transfer into English
- Koffi (2011), *Pronunciation of S-Clusters in Somali-Accented English* — St. Cloud State University, a Minnesota source

**Hmong** — *drafted; stretch scope.*
- Briggs (1984): the three most frequent processes are **cluster reduction, sonorant deviation, prevocalic voicing**
- Tonal language with 6 phonemic tones

**Karen (S'gaw / Eastern Pwo)** — *drafted; stretch scope, first to cut.*
- Syllable structure CV or C1(C2)VT; no word begins with a vowel (a glottal stop always precedes)
- Final consonants are a general difficulty; epenthetic final vowel often added
- Burmese influence: `/v/ /f/ /r/ /ʒ/` absent; several English vowels missing; substantial differences in stress and intonation
- One study notes speakers produced final consonants more reliably when *reading sentences* than in spontaneous speech — directly relevant, since reading aloud is this app's task

**Spanish** — *shipped in v1.*
- Extensively documented; covered by the canonical reference below

**Mandarin** — *shipped and validated.* Encoded for validation purposes (§9), since speechocean762 speakers are all Mandarin L1.

### Note on sources

The canonical reference for L1 interference — **Swan & Smith, *Learner English: A Teacher's Guide to Interference and Other Problems*** (Cambridge; 22 chapters, each opening with phonology) — covers Spanish and Chinese but **does not cover Hmong, Somali, or Karen.** Those three are encoded from individual academic papers. That omission is itself part of the project's argument: the standard reference for predicting pronunciation interference skips the three largest immigrant language communities in this district.

## 9. Evaluation

The team will distribute the app to users but will **not** run a feedback-and-iterate loop. All correctness claims therefore rest on offline evaluation against labeled public data, not user response.

**Validation (measured).** speechocean762 provides expert phoneme-level accuracy labels on non-native speakers. With the Mandarin rule set encoded, measure on a held-out split:

- **False-positive reduction** — proportion of expert-judged-correct phonemes that a baseline flags as errors and the L1 filter correctly reclassifies as accent
- **Retention of genuine miscue detection** — proportion of expert-judged-incorrect phonemes still flagged after filtering
- Correlation of predicted vs. expert sentence-level accuracy, fluency, and prosody scores
- Baseline WCPM and word-accuracy against the corpus

**Headline claim format:**
> "On non-native readers, the L1-aware filter reduced false error flags by X% while retaining Y% of genuine miscue detection."

**Extension (documented, not measured).** Every non-Mandarin rule set — Somali and Spanish in v1, Hmong and Karen if the stretch scope in §11 is reached — is built from published phonological descriptions and is **not** validated against labeled data, because no comparable labeled corpus exists for these languages.

**Terminology, used consistently throughout this spec:**

| Term | Meaning |
|---|---|
| **Validated** | Measured against expert labels. Applies to **Mandarin only**, because speechocean762 is the only labeled non-native corpus available and all its speakers are Mandarin L1 |
| **Shipped** | Rule set present and active in v1. Applies to Mandarin, Somali, Spanish |
| **Drafted** | Rules encoded but not reviewed or shipped. Applies to Hmong and Karen unless stretch scope is reached |

The claim being made is therefore: *the method is validated on Mandarin, and extended by documented rule to other languages.* The submission and video state this distinction explicitly. Overclaiming here would be the single easiest way to lose credibility with a technical judge.

**Comparison table for the video:**

| Metric | This system | Baseline (no L1 filter) |
|---|---|---|
| False error flags on accented-correct reads | measured | measured |
| Genuine miscues retained | measured | measured |
| Sentence-score correlation vs. expert | measured | measured |

**No Whisper fine-tuning.** With 33 days, fine-tuning Whisper would consume the window. Use Kid-Whisper's weights. If a trained component is wanted, fine-tune the GOPT-style scoring head on speechocean762 — cheap, fast, and it yields a benchmarked number.

## 10. Tech stack

- **Frontend:** React web app, mobile-responsive. Browser MediaRecorder for capture.
- **Backend:** Python FastAPI. SQLite for sessions and progress.
- **ML:** PyTorch. Whisper / Kid-Whisper, wav2vec2 or MFA for alignment, GOP scoring.
- **L1 rules:** declarative JSON, one file per language.
- **Deploy:** public URL on a free tier. Judges may request a live demo; a localhost-only app risks disqualification.
- **Compute:** Colab Pro or local GPU for scoring-head training and evaluation runs. Inference must be feasible on modest hardware.

## 11. Scope

**v1 — must ship**
1. Record a passage read-aloud in the browser
2. ASR + forced alignment producing word-level output
3. Miscue classification (7 categories)
4. Accuracy %, WCPM, pacing
5. L1 filter with Somali + Spanish + Mandarin rule sets
6. Word-by-word feedback UI with tap-to-hear
7. Two static passage sets (elementary, secondary)
8. Teacher/parent progress view
9. Evaluation harness plus measured results
10. Public deployment

**Stretch — only if week 4 arrives early**
- Hmong and Karen rule sets promoted from draft to reviewed
- GOPT scoring-head fine-tune
- Interest-based passage filtering
- Offline / on-device inference

**Explicitly out of scope**
- Whisper fine-tuning
- Passage generation
- Accounts, auth, multi-school support
- Any clinical or diagnostic claim
- Native mobile apps

## 12. Schedule

| Week | Dates | Deliverable |
|---|---|---|
| 1 | Sep 23–29 | speechocean762 downloaded; OpenPronounce or GOPT running; Whisper + alignment producing word-level output on a real recording |
| 2 | Sep 30–Oct 6 | Miscue classifier; WCPM and accuracy scoring; evaluation harness scaffolded |
| 3 | Oct 7–13 | **L1 filter** — rule schema, Somali/Spanish/Mandarin rule sets, Mandarin validation run producing real numbers |
| 4 | Oct 14–20 | UI, passages, teacher view; public deployment |
| 5 | Oct 21–26 | Video, submission answers, buffer. **Submit by Oct 23** (48–72h early) |

## 13. Team split

- **ML lead** — components [2] through [6]
- **Research/data** — [10] evaluation harness, L1 rule encoding from the literature (research work, not ML coding; suits a non-ML teammate)
- **Frontend/product** — [7] through [9], passages, deployment, demonstration video

Both MN-04 teammates should appear on camera; this is their district.

## 14. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Scope: 4 L1s plus 2 age bands plus full pipeline in 33 days | High | Framework supports all four; Mandarin/Somali/Spanish ship in v1, Hmong and Karen are stretch (see §9 terminology). Karen is the first cut if needed |
| Elementary child ASR accuracy | High | Kid-Whisper weights; test on real child audio in week 1, not week 4 |
| Alignment quality on slow, disfluent child speech | Medium | Benchmark MFA against WhisperX in week 1 and commit to one |
| L1 filter hides genuine errors | Medium | Retention metric in §9 is an explicit guardrail, reported alongside false-positive reduction |
| No user iteration possible | Medium | Keep UX conventional; borrow interaction patterns that already work rather than inventing |
| Judge finds Microsoft Reading Coach | Medium | Named directly in the video, with the differentiation stated |

## 15. Submission artifacts (Congressional App Challenge)

- **Demonstration video, 1–3 minutes**, public on YouTube. Must state: every participant's name, the app name, purpose **in one clear sentence**, target audience, tools and coding languages, and a functionality showcase. Over- or under-length may be penalized. The video is the primary judging artifact — judges receive the videos and a rubric, not the app.
- **Written answers**, including the hardest technical difficulty and how it was solved. Planned answer: the L1-aware filter — separating accent from error, and the false-positive/retention tradeoff it required.
- **AI usage disclosure**, completed accurately.
- **Open-source attribution** for every dataset and repo in §7, including speechocean762's license terms and the research-use terms of any corpus used.
- **Public deployment URL**, with source code available on request.

## 16. Judging alignment

| CAC criterion | How this project scores |
|---|---|
| Quality of the idea (creativity, originality) | The accent-vs-error distinction is unaddressed by existing tools, and grounded in the district's actual population |
| Implementation (UX and design) | Word-by-word feedback over the passage; conventional, teacher-legible patterns |
| Excellence of coding | Multi-stage pipeline, a measured benchmark against expert labels, and an honest validated/extended distinction |

MN-04 precedent: every first-place winner since 2022 has been a youth-wellbeing or youth-civic app, built by a student, for students, motivated by a personal observation plus a hard statistic. The 2025 judge was a computer science senior specializing in AI/ML. The reigning winner's family has won repeatedly by publishing accuracy figures benchmarked against prior research — notably, no accuracy number was published for the 2025 winning entry.

## 17. Open decisions

1. **App name.** Unresolved. Should be plain and trustworthy — the audience includes teachers, parents, and young children.
2. **Deep-validation L1.** This spec assumes **Somali** (best-documented of the four, largest Minnesota population, and a citable Minnesota-based researcher). Confirm.
3. **Elementary vs. secondary split.** This spec assumes **one app, two passage sets** rather than two distinct modes, as the cheaper option. Confirm.
