from chorus.phonemes import strip_stress, to_phonemes


def test_strip_stress_removes_digits():
    assert strip_stress("AA1") == "AA"
    assert strip_stress("S") == "S"


def test_known_word_phonemes():
    assert list(to_phonemes("stop")) == ["S", "T", "AA", "P"]


def test_phonemes_are_stress_free():
    for p in to_phonemes("banana"):
        assert not any(c.isdigit() for c in p)


def test_case_insensitive():
    assert to_phonemes("Stop") == to_phonemes("stop")


def test_returns_a_tuple_so_it_can_be_cached():
    assert isinstance(to_phonemes("zzyzx"), tuple)


def test_empty_string_returns_empty():
    assert list(to_phonemes("")) == []
