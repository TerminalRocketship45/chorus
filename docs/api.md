# Chorus HTTP API

The FastAPI service (`src/chorus_api/`) wraps `chorus.pipeline.analyze()`. In production it also
serves the built React app (`web/dist/`) at `/`; every API route lives under `/api`. In
development the Vite dev server proxies `/api` to `http://localhost:8000`.

There are no accounts or logins (out of scope per the design). Student records are first names
or nicknames only; recordings are never stored on the server.

## Display status

The engine gives one raw `status` per expected word (see `src/chorus/types.py`). The service adds
a `display` field so every client renders words the same way. Clients colour by `display`, never
by `status`.

| `display` | When | Student view shows |
| --- | --- | --- |
| `correct` | status `correct` | correct |
| `accent_ok` | status `substitution` and `accent_excused` | **correct, identical to `correct`**. Never an error, never "wrong accent". Only the teacher view may count these |
| `misread` | status `substitution`, not excused | tricky word; may show what was heard |
| `skipped` | status `omission` | skipped word |
| `extra_nearby` | status `insertion` | the word itself was read **correctly**; mark "an extra word was added nearby". Not a misread |
| `repeated` | status `repetition` | correct, with a light "repeated" mark (not an error) |
| `self_corrected` | status `self_correction` | correct, with a positive "fixed it" mark |

`hesitation` is defined in the engine but never assigned; clients may ignore it.

The practice list (`practice_words`) is the `misread` and `skipped` words only, de-duplicated, in
passage order.

## Routes

### `GET /api/health`
`{"status": "ok"}`

### `GET /api/languages`
Home languages for onboarding, in display order (Somali first: it is the featured language).

```json
[
  {"code": "somali",   "label": "Somali",           "support": "rules"},
  {"code": "spanish",  "label": "Spanish",          "support": "rules"},
  {"code": "mandarin", "label": "Mandarin Chinese", "support": "measured"},
  {"code": "hmong",    "label": "Hmong",            "support": "not_yet"},
  {"code": "karen",    "label": "Karen",            "support": "not_yet"},
  {"code": "english",  "label": "English only",     "support": "not_needed"},
  {"code": "other",    "label": "Another language", "support": "not_yet"}
]
```

`support` meanings, which the UI must state honestly:
- `measured`: accent rules checked against expert labels (Mandarin only).
- `rules`: accent rules from published research, not yet measured against labelled recordings.
- `not_yet`: no accent rules yet; the reading is scored without accent adjustment.
- `not_needed`: no accent adjustment applied.

Only `measured` and `rules` codes are passed to the engine as `language`.

### `GET /api/passages?band=elementary|secondary`
`band` optional; omitted returns both sets.

```json
[{"id": "el-01", "title": "...", "band": "elementary", "level": 1, "topic": "animals",
  "word_count": 62, "text": "..."}]
```

### `GET /api/passages/{id}`
One passage, same shape as a list item. 404 for an unknown id.

### `POST /api/students`
Body `{"name": "Amina", "grade_band": "elementary", "home_language": "somali"}` →
`201 {"id": 1, "name": "Amina", "grade_band": "elementary", "home_language": "somali", "created_at": "2026-10-11T19:30:00Z"}`

### `GET /api/students`
List for the teacher view: each student plus `session_count`, `last_session_at` (or null),
`last_wcpm` (or null).

### `GET /api/students/{id}`
```json
{"student": {...},
 "sessions": [{"id": 3, "passage_id": "el-01", "passage_title": "...", "created_at": "...",
               "score": {...ReadingScore}, "accent_adjusted": {...} | null,
               "accent_ok_count": 2, "practice_words": ["..."]}],
 "most_missed": [{"word": "through", "count": 3}]}
```
Sessions are oldest first (for the trend line). `most_missed` counts `misread` and `skipped` words
across all sessions, top 10.

### `POST /api/analyze` (multipart/form-data)
Fields: `audio` (file: webm/ogg/wav/mp4 from MediaRecorder), `passage_id` (required),
`student_id` (optional; saves a session when given), `home_language` (optional; defaults to the
student's).

```json
{"session_id": 3,
 "passage_id": "el-01",
 "home_language": "somali",
 "accent_filter_applied": true,
 "words": [{"index": 0, "expected": "the", "heard": "the", "status": "correct",
            "accent_excused": false, "display": "correct", "start": 0.12, "end": 0.18}],
 "score": {"accuracy": 0.95, "wcpm": 88.2, "total_words": 62, "correct_words": 59,
           "duration_s": 40.1, "long_pauses": 2},
 "accent_adjusted": {...same shape...} | null,
 "practice_words": ["through"]}
```

`session_id` is null when no `student_id` was given (nothing is saved). `home_language` echoes
the code the client sent (or the student's), whatever its support level, so it may be
`"english"` or `"hmong"` with `accent_filter_applied: false`; it is null only when no language
was given at all. `accuracy` is a fraction 0–1. `start`/`end` are seconds into the recording, or null for untimed
words. `accent_adjusted` is null when no accent rules apply.

Errors are `{"detail": "..."}` with: 400 bad field / unknown passage or student, 413 recording
longer than 120 s or file larger than 10 MB, 422 audio that cannot be decoded or contains no
speech, 503 when the analyzer is busy beyond the queue limit.

## Interests and AI-written passages

### `GET /api/interests`
The fixed interest list for onboarding, in display order:

```json
[{"code": "animals", "label": "Animals"}, {"code": "sports", "label": "Sports"},
 {"code": "space", "label": "Space"}, {"code": "nature", "label": "Nature"},
 {"code": "food", "label": "Food"}, {"code": "music", "label": "Music"},
 {"code": "art", "label": "Art"}, {"code": "science", "label": "Science"},
 {"code": "history", "label": "History"}, {"code": "adventure", "label": "Adventure"}]
```

### Students carry interests
`POST /api/students` accepts an optional `"interests": ["space", "animals"]` (codes from
`/api/interests`; unknown codes → 400). Every student object includes `interests` (a list, possibly
empty). `PATCH /api/students/{id}` accepts any of `name`, `grade_band`, `home_language`,
`interests` and returns the updated student.

### Passages carry a source
Every passage object gains `"source": "library" | "ai"`. AI-written passages have ids `g-<n>` and
are stored, so `GET /api/passages/g-12` and `POST /api/analyze` with `passage_id=g-12` work like
library ids. `GET /api/passages` (the list) returns library passages only.

### `POST /api/passages/generate`
Body: `{"band": "elementary", "interests": ["space"], "student_id": 1 | null,
"exclude_ids": ["g-3", "el-02"]}`. Writes a new passage for that grade band about one of the
interests, checks it (word-count range for the band; only words, no digits, hyphens or non-ASCII;
age-appropriate), and returns `201` with the passage. When the model is unavailable, out of
credit, or fails the checks after a few attempts, it returns a library passage instead (with
`"source": "library"`) that matches the band and, if possible, an interest and is not in
`exclude_ids`. It can take several seconds. 400 for an unknown band or interest.

### `GET /api/students/{id}/passages`
The passages this student generated or read, newest first:

```json
[{"passage": {...passage...}, "read": true, "attempts": 2,
  "last_result": {"accuracy": 0.94, "accent_adjusted_accuracy": 0.97, "wcpm": 71.5,
                  "at": "2026-10-21T19:30:00Z"}}]
```

`last_result` is null and `read` false for a passage generated but not yet read. Readers without a
nickname have no student id; the client keeps their read/score marks locally.

## Typed topics, AI feedback and replay (revision 2026-10-21)

Supersedes the interest chips in the UI (the `/api/interests` route and student `interests` stay
for compatibility, but the client no longer uses them).

### `POST /api/passages/generate` takes a typed topic
Body adds `"topic": "machine learning"` (free text the reader typed, trimmed, at most 80
characters; optional). When present, the passage is about that topic, written as a general,
readable passage for the grade band (not technical). When absent, it falls back to
`interests`, then to a general topic. Unsafe or unusable topics (blocklist on the topic, or the
model declines) never error: the response is a library passage. The response passage adds
`"topic": "<the typed topic or the interest used>"` and, at the top level of the passage object,
`"requested_topic": "<what the reader typed>" | null` and `"topic_accepted": true | false`.

### `POST /api/analyze` returns what was heard
The response adds `"transcript": "<the recognizer's raw text>"` so the client can show what
Chorus heard next to the passage.

### `POST /api/feedback`
Body: `{"passage_id": "...", "home_language": "somali" | null, "words": [...the analyze
response words...], "score": {...}, "accent_adjusted": {...} | null}`.
Returns `{"feedback": "<2 to 4 short sentences>", "source": "ai" | "template"}`. The comment is
encouraging, speaks to the reader ("you"), mentions words correct per minute in plain words,
names at most three practice words (only `misread`/`skipped` words), and never presents an
accent difference (`accent_ok`) or an `extra_nearby` word as a mistake, never says the reader's
accent is wrong, and makes no diagnostic claims. When the model is unavailable or its reply
breaks these rules, a template comment is returned with `"source": "template"`. Can take a few
seconds; the client requests it after showing the results.

### `POST /api/analyze`: recordings that cannot be scored (422)
Besides undecodable audio, the endpoint answers 422 with a friendly `detail` when the recording
peaks below -40 dBFS ("Your recording was very quiet..."), or when fewer than 15% of the passage's
words were heard as correct or close ("Chorus couldn't hear enough reading. Check the microphone,
move closer, and try again."). Show `detail` as is; there is no results page for these.
