from sinnix_deslop.filter import deslop, load_rules


def test_load_rules_parses_real_phrases_file():
    rules = load_rules()
    assert len(rules) > 10


def test_strips_stock_hedge():
    out = deslop("It's important to note that the sky is blue.")
    assert "important to note" not in out.lower()
    assert "sky is blue" in out


def test_strips_throat_clearing_opener():
    out = deslop("Certainly! Here is the answer.")
    assert not out.lower().startswith("certainly")
    assert "Here is the answer" in out


def test_replaces_delve():
    out = deslop("Let's delve into the details.")
    assert "delve" not in out.lower()
    assert "look at the details" in out.lower()


def test_strip_sentence_removes_whole_sentence():
    out = deslop("The cache is warm. I don't have personal opinions on this. The result is fast.")
    assert "personal opinions" not in out
    assert "cache is warm" in out
    assert "result is fast" in out


def test_collapses_double_spaces_left_by_removal():
    out = deslop("Please note that  the build passed.")
    assert "  " not in out


def test_leaves_clean_text_unchanged():
    text = "The build passed in 12 seconds."
    assert deslop(text) == text


def test_case_insensitive():
    out = deslop("CERTAINLY! Done.")
    assert not out.upper().startswith("CERTAINLY")
