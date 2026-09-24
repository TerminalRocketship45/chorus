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


# ---- fix round 1 ----------------------------------------------------------

import json

from chorus.l1 import engine as engine_module

ARPABET = set(
    "AA AE AH AO AW AY B CH D DH EH ER EY F G HH IH IY JH K L M N NG OW OY "
    "P R S SH T TH UH UW V W Y Z ZH".split()
)


@pytest.fixture
def mandarin():
    return load_ruleset("mandarin")


@pytest.fixture
def spanish():
    return load_ruleset("spanish")


@pytest.fixture
def clean_cache():
    load_ruleset.cache_clear()
    yield
    load_ruleset.cache_clear()


def test_reverse_direction_is_not_accent(somali, mandarin):
    # Somali reads /p/ as /b/, not the other way round.
    assert is_accent_variant("bat", "pat", somali) is False
    assert is_accent_variant("sink", "think", mandarin) is False


def test_mandarin_final_consonant_deletion(mandarin):
    # meat M IY T -> me M IY : exactly the final consonant dropped.
    assert is_accent_variant("meat", "me", mandarin) is True


def test_final_deletion_requires_same_vowel(mandarin):
    # bat B AE T -> bah B AA : final consonant gone but the vowel also differs.
    assert is_accent_variant("bat", "bah", mandarin) is False


def test_somali_cluster_reduction(somali):
    # stop S T AA P -> top T AA P : one consonant dropped from an S-T cluster.
    assert is_accent_variant("stop", "top", somali) is True


def test_lone_consonant_drop_is_not_cluster_reduction(somali, mandarin):
    # meter M IY T ER -> meer M IY ER : T sits between vowels, no cluster.
    assert is_accent_variant("meter", "meer", somali) is False
    assert is_accent_variant("meter", "meer", mandarin) is False


def test_no_final_deletion_without_the_rule(spanish, somali):
    # Spanish and Somali rules here do not include final consonant deletion.
    assert spanish.final_consonant_deletion is False
    assert is_accent_variant("meat", "me", spanish) is False
    assert is_accent_variant("meat", "me", somali) is False


def test_all_rule_symbols_are_valid_arpabet():
    for lang in available_languages():
        for key, targets in load_ruleset(lang).substitutions.items():
            assert key in ARPABET, f"{lang}: bad key {key}"
            for t in targets:
                assert t in ARPABET, f"{lang}: bad target {t} for {key}"


def test_substitutions_are_read_only(somali):
    with pytest.raises(TypeError):
        somali.substitutions["P"] = ("X",)
    assert load_ruleset("somali").substitutions["P"] == ("B",)


def test_path_traversal_and_empty_names_rejected():
    with pytest.raises(KeyError):
        load_ruleset("../engine")
    with pytest.raises(KeyError):
        load_ruleset("")


def test_unknown_status_raises_value_error(tmp_path, monkeypatch, clean_cache):
    (tmp_path / "toy.json").write_text(
        json.dumps({"language": "toy", "status": "approved", "sources": ["x"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(engine_module, "_DATA_DIR", tmp_path)
    with pytest.raises(ValueError):
        load_ruleset("toy")
