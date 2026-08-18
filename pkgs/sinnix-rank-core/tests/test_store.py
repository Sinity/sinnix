from rank_core.store import Item, Store


def test_store_round_trips_items_and_comparisons(tmp_path):
    store = Store(tmp_path / "domain")
    store.add_items([Item(id="a", label="Alpha"), Item(id="b", label="Beta")])
    cid = store.record_comparison(["a", "b"], winner="a", context="test")

    items = store.load_items()
    assert set(items) == {"a", "b"}
    assert items["a"].label == "Alpha"

    comparisons = store.load_comparisons()
    assert len(comparisons) == 1
    assert comparisons[0].id == cid
    assert comparisons[0].winner == "a"
    assert comparisons[0].context == "test"


def test_store_undo_tombstones_without_deleting_the_raw_line(tmp_path):
    store = Store(tmp_path / "domain")
    cid = store.record_comparison(["a", "b"], winner="a")
    store.undo(cid)

    assert store.load_comparisons() == []  # tombstoned: not in the live view
    raw_lines = store.comparisons_path.read_text().splitlines()
    assert len(raw_lines) == 2  # append-only: original record + delete marker survive on disk


def test_store_rejects_unknown_kind(tmp_path):
    import pytest

    store = Store(tmp_path / "domain")
    with pytest.raises(ValueError):
        store.record_comparison(["a", "b"], winner="a", kind="bogus")
