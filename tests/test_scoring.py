import pytest

from chorus.scoring import score_reading, score_with_accent_excused
from chorus.types import WordResult, WordStatus


def w(i, status, start=None, end=None, excused=False):
    return WordResult(
        index=i, expected=f"w{i}", heard=f"w{i}", status=status,
        start=start, end=end, accent_excused=excused,
    )


def test_perfect_read_scores_one():
    words = [w(i, WordStatus.CORRECT) for i in range(10)]
    s = score_reading(words, duration_s=60.0)
    assert s.accuracy == 1.0
    assert s.wcpm == 10.0
    assert s.correct_words == 10


def test_errors_reduce_accuracy():
    words = [w(0, WordStatus.CORRECT), w(1, WordStatus.SUBSTITUTION)]
    s = score_reading(words, duration_s=60.0)
    assert s.accuracy == 0.5
    assert s.wcpm == 1.0


def test_repetition_and_self_correction_are_not_errors():
    words = [
        w(0, WordStatus.CORRECT),
        w(1, WordStatus.REPETITION),
        w(2, WordStatus.SELF_CORRECTION),
    ]
    s = score_reading(words, duration_s=60.0)
    assert s.accuracy == 1.0
    assert s.correct_words == 3


def test_wcpm_scales_with_duration():
    words = [w(i, WordStatus.CORRECT) for i in range(30)]
    assert score_reading(words, duration_s=30.0).wcpm == 60.0


def test_zero_duration_yields_zero_wcpm_not_crash():
    words = [w(0, WordStatus.CORRECT)]
    assert score_reading(words, duration_s=0.0).wcpm == 0.0


def test_empty_passage_yields_zero_accuracy_not_crash():
    s = score_reading([], duration_s=10.0)
    assert s.accuracy == 0.0
    assert s.total_words == 0


def test_long_pauses_counted_from_gaps():
    words = [
        w(0, WordStatus.CORRECT, start=0.0, end=0.5),
        w(1, WordStatus.CORRECT, start=2.0, end=2.5),  # 1.5s gap
        w(2, WordStatus.CORRECT, start=2.6, end=3.0),  # 0.1s gap
    ]
    assert score_reading(words, duration_s=3.0, long_pause_s=1.0).long_pauses == 1


def test_accent_excused_words_count_as_correct():
    words = [
        w(0, WordStatus.CORRECT),
        w(1, WordStatus.SUBSTITUTION, excused=True),
    ]
    raw = score_reading(words, duration_s=60.0)
    adjusted = score_with_accent_excused(words, duration_s=60.0)
    assert raw.accuracy == 0.5
    assert adjusted.accuracy == 1.0


def test_accent_excused_ignored_when_word_already_correct():
    words = [w(0, WordStatus.CORRECT, excused=True)]
    assert score_with_accent_excused(words, duration_s=60.0).accuracy == 1.0


def test_omission_with_accent_excused_stays_error():
    words = [
        w(0, WordStatus.CORRECT),
        w(1, WordStatus.OMISSION, excused=True),
    ]
    raw = score_reading(words, duration_s=60.0)
    adjusted = score_with_accent_excused(words, duration_s=60.0)
    assert raw.accuracy == 0.5
    assert adjusted.accuracy == 0.5


def test_insertion_with_accent_excused_stays_error():
    words = [
        w(0, WordStatus.CORRECT),
        w(1, WordStatus.INSERTION, excused=True),
    ]
    raw = score_reading(words, duration_s=60.0)
    adjusted = score_with_accent_excused(words, duration_s=60.0)
    assert raw.accuracy == 0.5
    assert adjusted.accuracy == 0.5


def test_hesitation_does_not_count_against_accuracy():
    words = [
        w(0, WordStatus.CORRECT),
        w(1, WordStatus.HESITATION),
        w(2, WordStatus.CORRECT),
    ]
    s = score_reading(words, duration_s=60.0)
    assert s.accuracy == 1.0
    assert s.correct_words == 3


def test_not_reached_words_leave_every_denominator():
    words = [w(i, WordStatus.CORRECT) for i in range(3)] + [
        w(i, WordStatus.NOT_REACHED) for i in range(3, 10)
    ]
    s = score_reading(words, duration_s=60.0)
    assert (s.total_words, s.words_reached, s.passage_words) == (3, 3, 10)
    assert s.accuracy == 1.0 and s.correct_words == 3 and s.wcpm == 3.0
    a = score_with_accent_excused(words, duration_s=60.0)
    assert a.accuracy == 1.0 and a.passage_words == 10


def test_reached_defaults_to_total_when_nothing_excluded():
    s = score_reading([w(0, WordStatus.CORRECT), w(1, WordStatus.OMISSION)], duration_s=60.0)
    assert (s.total_words, s.words_reached, s.passage_words) == (2, 2, 2)
