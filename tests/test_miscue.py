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


import pytest  # noqa: E402


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
