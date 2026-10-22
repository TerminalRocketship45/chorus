"""Every branch of the status -> display mapping (docs/api.md "Display status").

This is the single place the INSERTION caveat is implemented: an INSERTION
word may be one the reader read correctly (heard == expected), and it must
never come out as "misread".
"""
import pytest

from chorus.types import WordResult, WordStatus
from chorus_api.display import accent_ok_count, practice_words, word_display


def _word(status, accent_excused=False, expected="word", heard="word"):
    return WordResult(
        index=0, expected=expected, heard=heard, status=status, accent_excused=accent_excused
    )


def test_correct_displays_correct():
    assert word_display(_word(WordStatus.CORRECT)) == "correct"


def test_substitution_not_excused_displays_misread():
    w = _word(WordStatus.SUBSTITUTION, accent_excused=False, expected="cat", heard="kat")
    assert word_display(w) == "misread"


def test_substitution_excused_displays_accent_ok():
    w = _word(WordStatus.SUBSTITUTION, accent_excused=True, expected="cat", heard="kat")
    assert word_display(w) == "accent_ok"


def test_omission_displays_skipped():
    w = _word(WordStatus.OMISSION, expected="cat", heard=None)
    assert word_display(w) == "skipped"


def test_insertion_displays_extra_nearby_even_when_read_correctly():
    """INSERTION caveat: heard == expected is legal here, and must still not be 'misread'."""
    w = _word(WordStatus.INSERTION, expected="cat", heard="cat")
    assert word_display(w) == "extra_nearby"


def test_repetition_displays_repeated():
    assert word_display(_word(WordStatus.REPETITION)) == "repeated"


def test_self_correction_displays_self_corrected():
    assert word_display(_word(WordStatus.SELF_CORRECTION)) == "self_corrected"


def test_hesitation_never_shows_as_an_error():
    """hesitation is never assigned by the engine; defensively treat it as not-an-error."""
    assert word_display(_word(WordStatus.HESITATION)) == "correct"


def test_accent_excused_true_on_a_non_substitution_status_is_ignored():
    """accent_excused only matters for SUBSTITUTION; a stray True elsewhere changes nothing."""
    w = _word(WordStatus.CORRECT, accent_excused=True)
    assert word_display(w) == "correct"


def test_practice_words_is_misread_and_skipped_deduplicated_in_passage_order():
    words = [
        WordResult(index=0, expected="the", heard="the", status=WordStatus.CORRECT),
        WordResult(index=1, expected="through", heard="true", status=WordStatus.SUBSTITUTION),
        WordResult(index=2, expected="cat", heard=None, status=WordStatus.OMISSION),
        WordResult(index=3, expected="through", heard="true", status=WordStatus.SUBSTITUTION),
        WordResult(index=4, expected="mat", heard="mat", status=WordStatus.REPETITION),
    ]
    assert practice_words(words) == ["through", "cat"]


def test_practice_words_excludes_accent_excused_substitutions():
    words = [
        WordResult(
            index=0, expected="cat", heard="kat", status=WordStatus.SUBSTITUTION, accent_excused=True
        ),
    ]
    assert practice_words(words) == []


def test_practice_words_excludes_insertion_even_though_it_is_an_error_status():
    words = [
        WordResult(index=0, expected="cat", heard="cat", status=WordStatus.INSERTION),
    ]
    assert practice_words(words) == []


def test_accent_ok_count_counts_only_excused_substitutions():
    words = [
        WordResult(index=0, expected="the", heard="the", status=WordStatus.CORRECT),
        WordResult(
            index=1, expected="cat", heard="kat", status=WordStatus.SUBSTITUTION, accent_excused=True
        ),
        WordResult(
            index=2, expected="sat", heard="sut", status=WordStatus.SUBSTITUTION, accent_excused=True
        ),
        WordResult(
            index=3, expected="mat", heard="mut", status=WordStatus.SUBSTITUTION, accent_excused=False
        ),
    ]
    assert accent_ok_count(words) == 2


def test_not_reached_displays_not_reached_and_is_never_practised():
    w = _word(WordStatus.NOT_REACHED, expected="mats", heard=None)
    assert word_display(w) == "not_reached"
    assert practice_words([w]) == []
    assert accent_ok_count([w]) == 0
