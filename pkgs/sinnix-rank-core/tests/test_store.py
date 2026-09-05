import json
import re

from rank_core.store import Item, Store, append_log


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
    assert (
        len(raw_lines) == 2
    )  # append-only: original record + delete marker survive on disk


def test_store_rejects_unknown_kind(tmp_path):
    import pytest

    store = Store(tmp_path / "domain")
    with pytest.raises(ValueError):
        store.record_comparison(["a", "b"], winner="a", kind="bogus")


def test_append_log_stamps_records_with_the_shared_utc_helper(tmp_path, monkeypatch):
    """The judgment log's ``at`` comes from ``sinnix_lib.ledger.utc_ts``.

    Comparisons are joined against ledgers other producers write, so the stamp
    is the estate's helper rather than a local copy that happens to agree
    today. A re-introduced local definition never sees the sentinel.
    """
    import rank_core.store as store_module

    monkeypatch.setattr(store_module, "utc_ts", lambda: "SENTINEL-UTC-TS")
    path = tmp_path / "log.jsonl"
    store_module.append_log(path, {"kind": "pair"})

    record = json.loads(path.read_text().splitlines()[0])
    assert record["at"] == "SENTINEL-UTC-TS"


def test_append_log_emits_second_precision_utc(tmp_path):
    path = tmp_path / "log.jsonl"
    append_log(path, {"kind": "pair"})

    record = json.loads(path.read_text().splitlines()[0])
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", record["at"])
