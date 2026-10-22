---
title: Chorus
emoji: 🎶
colorFrom: indigo
colorTo: blue
sdk: gradio
sdk_version: 5.50.0
python_version: "3.12.12"
app_file: app.py
pinned: false
---

# Chorus

Chorus listens to a student read a passage aloud and scores accuracy, words
correct per minute and pacing word by word, without counting a first-language
accent as a reading mistake. The reading is transcribed (faster-whisper),
compared with the passage using the running-record categories teachers use,
and aligned to the audio for timing. An accent filter then withdraws flags
whose sound change the reader's home language predicts. Rules ship for
Somali, Spanish and Mandarin; only Mandarin could be measured, because the one
labelled corpus available (speechocean762) is all Mandarin-L1. The Somali and
Spanish rules come from published research and have not been measured.

## What has been measured

The one labelled corpus available is speechocean762, whose speakers are all
Mandarin-L1, so only the Mandarin rules are measured. On its full test split
(2,500 recordings, 15,967 words), with the settings this app ships (Whisper
small.en, beam search 5, same-sound and digit-context rules, silence
filtering and volume normalisation), the speech
recognizer wrongly flags 2,308 of 14,644 words the experts marked correct
(15.8%). The accent filter withdrew 65 of those false flags (2.8%, 95% CI
2.1% to 3.5%) and kept 963 of 974 flagged genuine errors (98.9%, 95% CI 98.1%
to 99.5%). The filter's effect is small: most false flags come from the speech
recognizer, not from accent. This is a prototype, not a validated assessment
tool.

## Notes

- Runs on free CPU hardware; the first analysis after a cold start can be slow.
- Teacher-view data is stored in a temporary database and resets whenever the
  Space restarts or sleeps. Audio is never stored.
