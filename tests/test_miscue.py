import pytest

from chorus.miscue import normalize, detect_miscues
from chorus.types import WordStatus


def statuses(expected, heard):
    return [w.status for w in detect_miscues(normalize(expected), normalize(heard))]


def test_normalize_strips_punctuation_and_case():
    assert normalize("The cat, sat!") == ["the", "cat", "sat"]


def test_perfect_read_is_all_correct():
    assert statuses("the cat sat", "the cat sat") == [WordStatus.CORRECT] * 3


def test_substitution():
    assert statuses("the cat sat", "the cot sat") == [
        WordStatus.CORRECT, WordStatus.SUBSTITUTION, WordStatus.CORRECT,
    ]


def test_omission():
    assert statuses("the cat sat", "the sat") == [
        WordStatus.CORRECT, WordStatus.OMISSION, WordStatus.CORRECT,
    ]


def test_repetition_is_not_an_error():
    # Reader says "cat" twice. Second is a repetition, not an insertion.
    out = detect_miscues(normalize("the cat sat"), normalize("the cat cat sat"))
    assert [w.status for w in out] == [
        WordStatus.CORRECT, WordStatus.REPETITION, WordStatus.CORRECT,
    ]


def test_self_correction_is_not_an_error():
    # Reader says the wrong word, then immediately the right one.
    out = detect_miscues(normalize("the cat sat"), normalize("the cot cat sat"))
    assert [w.status for w in out] == [
        WordStatus.CORRECT, WordStatus.SELF_CORRECTION, WordStatus.CORRECT,
    ]


def test_insertion_marks_adjacent_word():
    # "big" is unrelated to "cat", so it is a genuine insertion.
    assert statuses("the cat sat", "the big cat sat") == [
        WordStatus.CORRECT, WordStatus.INSERTION, WordStatus.CORRECT,
    ]


def test_heard_text_is_recorded_for_substitutions():
    out = detect_miscues(normalize("the cat"), normalize("the cot"))
    assert out[1].heard == "cot"


def test_omission_has_no_heard_text():
    out = detect_miscues(normalize("the cat sat"), normalize("the sat"))
    assert out[1].heard is None


def test_every_expected_word_appears_once():
    out = detect_miscues(normalize("a b c d e"), normalize("a x c e"))
    assert [w.expected for w in out] == ["a", "b", "c", "d", "e"]
    assert [w.index for w in out] == [0, 1, 2, 3, 4]


def test_empty_read_is_all_omissions():
    assert statuses("the cat sat", "") == [WordStatus.OMISSION] * 3


def test_repeated_wrong_attempts_stay_self_correction():
    assert statuses("the cat sat", "the cot cot cat sat") == [
        WordStatus.CORRECT, WordStatus.SELF_CORRECTION, WordStatus.CORRECT,
    ]


def test_extra_after_substitution_does_not_overwrite_it():
    out = detect_miscues(normalize("a b"), normalize("a x y"))
    assert out[1].status is WordStatus.SUBSTITUTION


def test_transposition_does_not_give_omission_heard_text():
    out = detect_miscues(normalize("a b c"), normalize("a c b"))
    for w in out:
        if w.status is WordStatus.OMISSION:
            assert w.heard is None


@pytest.mark.parametrize(
    "expected, heard",
    [
        ("the cat sat", "the cot cot cat sat"),
        ("a b", "a x y"),
        ("a b c", "a c b"),
        ("the cat sat", "the cat sat dog"),
        ("a b", "a b c d e"),
        ("the cat sat", "the cat cat sat"),
        ("a b c d", "d c b a"),
    ],
)
def test_structural_invariants(expected, heard):
    exp = normalize(expected)
    out = detect_miscues(exp, normalize(heard))
    assert [w.index for w in out] == list(range(len(exp)))
    assert [w.expected for w in out] == exp
    for w in out:
        if w.status is WordStatus.OMISSION:
            assert w.heard is None


@pytest.mark.parametrize(
    "text, tokens",
    [
        ("0", ["zero"]),
        ("4", ["four"]),
        ("12", ["twelve"]),
        ("19", ["nineteen"]),
        ("20", ["twenty"]),
        ("21", ["twenty", "one"]),
        ("99", ["ninety", "nine"]),
        ("100", ["one", "hundred"]),
        ("101", ["one", "hundred", "one"]),
        ("110", ["one", "hundred", "ten"]),
        ("999", ["nine", "hundred", "ninety", "nine"]),
        ("The 3 cats", ["the", "three", "cats"]),
    ],
)
def test_normalize_maps_small_integers_to_words(text, tokens):
    assert normalize(text) == tokens


@pytest.mark.parametrize("token", ["2599", "1000", "1st", "3rd", "000", "007", "00", "05"])
def test_normalize_leaves_other_digit_tokens_unchanged(token):
    assert normalize(token) == [token]


def test_number_words_and_digits_normalise_to_the_same_tokens():
    assert normalize("I have two cats") == normalize("I have 2 cats")


def test_spoken_number_word_matches_digit_rendering():
    out = detect_miscues(normalize("I have two cats"), normalize("I have 2 cats"))
    assert [w.status for w in out] == [WordStatus.CORRECT] * 4


def test_normalize_splits_decimals_per_part():
    assert normalize("3.5") == ["three", "five"]


# --- mark_unreached (reader stopped early) ---------------------------------


def _marked(expected, heard, tail=0.0):
    from chorus.miscue import mark_unreached

    return [w.status for w in mark_unreached(detect_miscues(normalize(expected), normalize(heard)), tail)]


def test_trailing_omissions_become_not_reached():
    s = _marked("a b c d e f", "a b c")
    assert s == [WordStatus.CORRECT] * 3 + [WordStatus.NOT_REACHED] * 3


def test_leading_and_middle_omissions_stay_errors():
    s = _marked("a b c d e f", "c e")
    assert s[:2] == [WordStatus.OMISSION] * 2
    assert s[3] == WordStatus.OMISSION
    assert s[5] == WordStatus.NOT_REACHED


def test_substitution_before_a_correct_last_word_is_fine():
    s = _marked("the cat sat on mats", "the cot sat")
    assert s[1] == WordStatus.SUBSTITUTION
    assert s[3:] == [WordStatus.NOT_REACHED] * 2


def test_silence_is_never_marked_not_reached():
    s = _marked("a b c", "")
    assert s == [WordStatus.OMISSION] * 3


def test_full_read_has_no_not_reached():
    assert WordStatus.NOT_REACHED not in _marked("a b c", "a b c")


def test_speech_after_last_word_means_recogniser_lost_the_end():
    # lots of speech after the last heard word: the omissions stay errors
    s = _marked("a b c d e f", "a b c", tail=3.0)
    assert s[3:] == [WordStatus.OMISSION] * 3
    # unknown tail (last word untimed): also conservative
    assert _marked("a b c d", "a b", tail=None)[2:] == [WordStatus.OMISSION] * 2


def test_substitution_as_last_heard_word_keeps_trailing_omissions():
    # "cot" is a substitution at the end: the recogniser's end is garbled, not a clean stop
    s = _marked("the cat sat on mats", "the cot")
    assert s[2:] == [WordStatus.OMISSION] * 3
