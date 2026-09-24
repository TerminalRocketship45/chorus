from chorus.types import WordStatus, WordResult, ReadingScore, Analysis


def test_word_status_values():
    assert WordStatus.CORRECT == "correct"
    assert WordStatus.SELF_CORRECTION == "self_correction"


def test_word_result_defaults():
    w = WordResult(index=0, expected="cat", heard="cat", status=WordStatus.CORRECT)
    assert w.start is None
    assert w.accent_excused is False


def test_analysis_holds_words_and_score():
    score = ReadingScore(
        accuracy=1.0, wcpm=60.0, total_words=1,
        correct_words=1, duration_s=1.0, long_pauses=0,
    )
    a = Analysis(words=[], score=score, accent_adjusted=None)
    assert a.score.wcpm == 60.0
