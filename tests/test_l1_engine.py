import pytest

from chorus.l1.engine import (
    RuleSet, available_languages, is_accent_variant, load_ruleset,
)


@pytest.fixture
def somali():
    return load_ruleset("somali")


def test_shipped_languages_are_available():
    langs = available_languages()
    assert {"mandarin", "somali", "spanish"} <= set(langs)


def test_ruleset_has_sources():
    # Every rule set must cite where its patterns came from.
    for lang in available_languages():
        assert load_ruleset(lang).sources, f"{lang} has no sources"


def test_unknown_language_raises():
    with pytest.raises(KeyError):
        load_ruleset("klingon")


def test_identical_words_are_not_accent_variants(somali):
    # Same word is 'correct', not 'accent' — the caller handles that case.
    assert is_accent_variant("cat", "cat", somali) is False


def test_somali_p_to_b_substitution_is_accent(somali):
    # Somali lacks /p/; 'pat' realised as 'bat' is predictable transfer.
    assert is_accent_variant("pat", "bat", somali) is True


def test_somali_v_to_f_substitution_is_accent(somali):
    # Somali lacks /v/.
    assert is_accent_variant("van", "fan", somali) is True


def test_genuine_misread_is_not_accent(somali):
    # 'cat' read as 'dog' shares no phonology — a real error.
    assert is_accent_variant("cat", "dog", somali) is False


def test_unrelated_length_mismatch_is_not_accent(somali):
    assert is_accent_variant("cat", "elephant", somali) is False


def test_spanish_ruleset_loads_and_has_substitutions():
    rules = load_ruleset("spanish")
    assert isinstance(rules, RuleSet)
    assert rules.substitutions


def test_rule_status_is_a_known_value():
    for lang in available_languages():
        assert load_ruleset(lang).status in {"validated", "shipped", "drafted"}
