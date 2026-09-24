import json
from pathlib import Path

import pytest

from chorus.l1.engine import load_ruleset

DATA = Path(__file__).parent.parent / "src" / "chorus" / "l1" / "data"
REQUIRED = {"language", "status", "sources"}


@pytest.mark.parametrize("lang", ["mandarin", "somali", "spanish"])
def test_file_has_required_fields(lang):
    raw = json.loads((DATA / f"{lang}.json").read_text(encoding="utf-8"))
    assert REQUIRED <= set(raw)


@pytest.mark.parametrize("lang", ["mandarin", "somali", "spanish"])
def test_substitution_targets_are_lists(lang):
    raw = json.loads((DATA / f"{lang}.json").read_text(encoding="utf-8"))
    for src, targets in raw.get("substitutions", {}).items():
        assert isinstance(targets, list), f"{lang}: {src} targets must be a list"
        assert targets, f"{lang}: {src} has no targets"


def test_mandarin_is_the_validated_language():
    # speechocean762 speakers are all Mandarin L1, so it is the only language
    # we can measure against expert labels.
    assert load_ruleset("mandarin").status == "validated"


def test_somali_and_spanish_are_shipped_not_validated():
    assert load_ruleset("somali").status == "shipped"
    assert load_ruleset("spanish").status == "shipped"


def test_somali_lacks_p_and_v():
    subs = load_ruleset("somali").substitutions
    assert "B" in subs["P"]
    assert "F" in subs["V"]


def test_somali_has_epenthesis_and_cluster_reduction():
    rules = load_ruleset("somali")
    assert rules.epenthesis is True
    assert rules.cluster_reduction is True


def test_mandarin_has_th_substitutions():
    subs = load_ruleset("mandarin").substitutions
    assert "TH" in subs
    assert "DH" in subs
