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

On 500 utterances from the speechocean762 test split (Mandarin speakers,
`base.en`, 3,219 words), the accent filter withdrew 2.2% of false flags
(14 of 645; 95% CI 1.1% to 3.4%) and kept 97.5% of the words experts marked as
mispronounced (233 of 239). The effect is small: most false flags come from
the speech recogniser, not from accent, so the recogniser sets the ceiling.
This is a prototype, not a validated assessment tool.

## Notes

- Runs on free CPU hardware; the first analysis after a cold start can be slow.
- Teacher-view data is stored in a temporary database and resets whenever the
  Space restarts or sleeps. Audio is never stored.
