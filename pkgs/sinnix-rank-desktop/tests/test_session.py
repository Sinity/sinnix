from pathlib import Path

import pytest
from rank_core import Item as RankItem
from session import DomainSource, Item, LocalSource, Session


def displayed(session):
    return tuple(item and item.id for item in session.pair)


def test_largest_local_reopens_with_winner_and_supports_undo(tmp_path, monkeypatch):
    monkeypatch.setenv("SINNIX_RANK_ROOT", str(tmp_path / "domains"))
    folder = tmp_path / "images"
    folder.mkdir()
    for index in range(5):
        (folder / f"{index}.png").write_bytes(b"0" * (index + 1))
    source = LocalSource([folder])
    state = tmp_path / "state"
    session = Session(source, state_root=state)
    largest, second = session.pair
    assert (Path(largest.path).name, Path(second.path).name) == ("4.png", "3.png")
    with pytest.raises(RuntimeError, match="already open"):
        Session(source, state_root=state)
    session.prefer(1)
    assert session.pair[1] == second
    assert Path(session.pair[0].path).name == "2.png"
    assert len(source.comparisons()) == 1
    prior = displayed(session)
    session.close()

    resumed = Session(source, state_root=state)
    assert displayed(resumed) == prior
    assert resumed.can_undo
    resumed.undo()
    assert displayed(resumed) == (largest.id, second.id)
    assert not source.comparisons()
    resumed.skip()
    assert [Path(item.path).name for item in resumed.pair] == ["2.png", "1.png"]
    resumed.close()


def test_informative_domain_uses_existing_store_for_tie(tmp_path, monkeypatch):
    monkeypatch.setenv("SINNIX_RANK_ROOT", str(tmp_path / "domains"))
    source = DomainSource("demo")
    source.store.add_items([RankItem(str(i), f"Choice {i}", {}) for i in range(4)])
    session = Session(source, state_root=tmp_path / "state")
    initial = displayed(session)
    session.tie()
    (judgment,) = source.comparisons()
    assert tuple(judgment.set) == initial
    assert judgment.winner is None
    assert displayed(session) != initial
    session.undo()
    assert displayed(session) == initial
    assert not source.comparisons()
    session.close()


class Library:
    title = "Library fixture"
    scope = "vr"
    order = "largest"
    key = "fixture"
    can_scope = True
    can_delete = True

    def __init__(self):
        self.removed = set()
        self.attempts = []

    def load(self, scope):
        result = []
        for i in range(1, 7):
            if str(i) in self.removed:
                continue
            identity = {"id": str(i), "path": f"/grid_{i}.mp4"}
            versions = ({"id": "100", "path": "/grid_copy.mp4"},) if i == 3 else ()
            result.append(
                Item(str(i), f"Grid {i}", size=i, identity=identity, versions=versions)
            )
        imported = {"pair": {"left": "3", "right": "4"}, "seen": ["5", "6", "3", "4"]}
        return result, imported if scope == "vr" else None

    def delete(self, files):
        ids = [file["id"] for file in files]
        self.attempts.append(ids)
        result = {}
        for item_id in ids:
            if item_id == "4" and len(self.attempts) == 1:
                result[item_id] = {"removed": False, "error": "Permission denied"}
            else:
                result[item_id] = {"removed": True}
                self.removed.add(item_id)
        return result


def test_import_and_partial_delete_reopen_for_retry(tmp_path):
    library = Library()
    session = Session(library, state_root=tmp_path)
    assert displayed(session) == ("3", "4")
    with pytest.raises(ValueError, match="outside"):
        session.delete(["6"])
    session.delete(["3", "4"])
    assert "Permission denied" in session.status
    assert displayed(session) == (None, "4")
    session.close()

    resumed = Session(library, state_root=tmp_path)
    assert displayed(resumed) == (None, "4")
    resumed.delete(["4"])
    assert displayed(resumed) == ("2", "1")
    assert library.attempts == [["3", "4"], ["4"]]
    resumed.set_scope("all")
    assert displayed(resumed) == ("6", "5")
    resumed.set_scope("vr")
    assert displayed(resumed) == ("2", "1")
    resumed.close()
