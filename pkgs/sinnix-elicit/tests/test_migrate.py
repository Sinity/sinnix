"""The elicitation-state move: verified, idempotent, and refused while the
drain could write.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "sinnix-elicit-migrate"

_loader = SourceFileLoader("sinnix_elicit_migrate", str(SCRIPT_PATH))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec is not None
migrate_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = migrate_mod
_loader.exec_module(migrate_mod)


@pytest.fixture()
def roots(tmp_path, monkeypatch):
    """A populated old root, an unused new root, and an inactive drain."""
    old = tmp_path / "preferences"
    new = tmp_path / "elicit"
    wallpaper = old / "wallpaper"
    wallpaper.mkdir(parents=True)
    (wallpaper / "items.json").write_text(json.dumps([{"id": "a"}, {"id": "b"}]))
    (wallpaper / "comparisons.jsonl").write_text(
        '{"id": "1", "kind": "pair", "a": "a", "b": "b", "outcome": 1.0}\n'
    )
    (wallpaper / "model.json").write_text('{"schema": "sinnix-elicit-model-v1"}')
    (old / "keybinds").mkdir()
    (old / "keybinds" / "items.json").write_text(json.dumps([{"id": "x"}]))
    monkeypatch.setattr(migrate_mod, "drain_is_active", lambda *_: False)
    return old, new


def tree(root: Path):
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def test_every_file_arrives_with_its_size_and_digest(roots, capsys):
    old, new = roots
    expected = tree(old)

    assert migrate_mod.main(["--from", str(old), "--to", str(new)]) == 0

    assert tree(new) == expected
    assert sorted(p.name for p in old.iterdir()) == []
    assert "verified 2 domain(s)" in capsys.readouterr().out


def test_a_domain_arrives_complete_or_not_at_all(roots):
    """Rename, not copy: the destination becomes visible already populated, so
    the installed producer can never find an empty domain to initialise."""
    old, new = roots
    source_inode = (old / "wallpaper").stat().st_ino

    assert migrate_mod.main(["--from", str(old), "--to", str(new)]) == 0

    assert (new / "wallpaper").stat().st_ino == source_inode


def test_re_running_verifies_instead_of_merging(roots, capsys):
    old, new = roots
    expected = tree(old)
    assert migrate_mod.main(["--from", str(old), "--to", str(new)]) == 0
    capsys.readouterr()

    # A second run with the source recreated (an interrupted first attempt
    # that had already moved one domain) must verify, not append.
    (old / "wallpaper").mkdir(parents=True)
    for name, _ in tree(new).items():
        if name.startswith("wallpaper/"):
            (old / name).write_bytes((new / name).read_bytes())

    assert migrate_mod.main(["--from", str(old), "--to", str(new)]) == 0
    assert tree(new) == expected
    assert "already at" in capsys.readouterr().out


def test_a_changed_file_at_the_destination_fails_the_run(roots, capsys):
    old, new = roots
    assert migrate_mod.main(["--from", str(old), "--to", str(new)]) == 0
    capsys.readouterr()

    (old / "wallpaper").mkdir(parents=True)
    (old / "wallpaper" / "items.json").write_text(json.dumps([{"id": "different"}]))

    assert migrate_mod.main(["--from", str(old), "--to", str(new)]) == 1
    assert "items.json changed" in capsys.readouterr().err


def test_an_extra_or_missing_file_fails_the_run(roots, capsys):
    old, new = roots
    assert migrate_mod.main(["--from", str(old), "--to", str(new)]) == 0
    capsys.readouterr()

    (old / "keybinds").mkdir(parents=True)
    (old / "keybinds" / "items.json").write_bytes(
        (new / "keybinds" / "items.json").read_bytes()
    )
    (old / "keybinds" / "stray.json").write_text("{}")

    assert migrate_mod.main(["--from", str(old), "--to", str(new)]) == 1
    err = capsys.readouterr().err
    assert "missing stray.json" in err


def test_the_move_is_refused_while_the_drain_is_active(roots, monkeypatch, capsys):
    old, new = roots
    monkeypatch.setattr(migrate_mod, "drain_is_active", lambda *_: True)

    assert migrate_mod.main(["--from", str(old), "--to", str(new)]) == 2
    assert not new.exists()
    assert tree(old)  # untouched
    assert "is active" in capsys.readouterr().err


def test_an_unanswerable_drain_probe_counts_as_active(monkeypatch):
    """A probe that cannot answer is not permission to move state."""

    def explode(*_args, **_kwargs):
        raise OSError("systemctl missing")

    monkeypatch.setattr(migrate_mod.subprocess, "run", explode)
    assert migrate_mod.drain_is_active("whatever.service") is True


def test_a_dry_run_moves_nothing(roots, capsys):
    old, new = roots
    expected = tree(old)

    assert migrate_mod.main(["--from", str(old), "--to", str(new), "--dry-run"]) == 0

    assert tree(old) == expected
    assert not new.exists()
    assert "would move 2 domain(s)" in capsys.readouterr().out


def test_an_absent_source_is_a_completed_migration(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(migrate_mod, "drain_is_active", lambda *_: False)
    assert (
        migrate_mod.main(
            ["--from", str(tmp_path / "gone"), "--to", str(tmp_path / "new")]
        )
        == 0
    )
    assert "nothing to migrate" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("status", "returncode", "refused"),
    [
        ("inactive", 3, False),
        ("failed", 3, False),
        ("active", 0, True),
        ("activating", 0, True),
        ("unknown", 4, True),
        ("", 1, True),
        ("inactive", 1, True),
    ],
)
def test_only_known_stopped_drain_permits_migration(monkeypatch, status, returncode, refused):
    from subprocess import CompletedProcess

    monkeypatch.setattr(
        migrate_mod.subprocess,
        "run",
        lambda *_args, **_kwargs: CompletedProcess([], returncode, stdout=status + "\n"),
    )
    assert migrate_mod.drain_is_active("synthetic.service") is refused


@pytest.mark.parametrize("kind", ["file-link", "dangling-link", "directory-link", "fifo"])
def test_uninventoried_objects_refuse_before_any_domain_moves(roots, tmp_path, kind, capsys):
    import os
    old, new = roots
    external = tmp_path / "external"
    external.mkdir()
    (external / "state.json").write_text('{"preserved":true}')
    entry = old / "wallpaper" / "unaccounted"
    if kind == "file-link":
        entry.symlink_to(external / "state.json")
    elif kind == "dangling-link":
        entry.symlink_to(external / "missing.json")
    elif kind == "directory-link":
        entry.symlink_to(external, target_is_directory=True)
    else:
        os.mkfifo(entry)
    original_inode = (old / "keybinds").stat().st_ino
    assert migrate_mod.main(["--from", str(old), "--to", str(new)]) == 1
    assert (old / "keybinds").stat().st_ino == original_inode
    assert not new.exists()
    assert "cannot migrate" in capsys.readouterr().err


def test_unreadable_subdirectory_is_not_an_empty_inventory(roots, monkeypatch, capsys):
    old, new = roots
    blocked = old / "wallpaper" / "blocked"
    blocked.mkdir()
    (blocked / "state.json").write_text('{"preserved":true}')
    original = migrate_mod.os.scandir
    def denied(path):
        if Path(path).name == "blocked":
            raise PermissionError("synthetic denied directory")
        return original(path)
    monkeypatch.setattr(migrate_mod.os, "scandir", denied)
    assert migrate_mod.main(["--from", str(old), "--to", str(new)]) == 1
    assert (old / "keybinds").is_dir() and not new.exists()
    assert "denied" in capsys.readouterr().err


def test_destination_link_refuses_before_moving_other_domains(roots, tmp_path, capsys):
    old, new = roots
    new.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    (new / "wallpaper").symlink_to(external, target_is_directory=True)
    assert migrate_mod.main(["--from", str(old), "--to", str(new)]) == 1
    assert (old / "keybinds").is_dir() and (old / "wallpaper").is_dir()
    assert list(external.iterdir()) == []
    assert "cannot migrate" in capsys.readouterr().err


@pytest.mark.parametrize("destination", ["same", "child", "parent"])
def test_overlapping_roots_refuse_without_moving(roots, destination, capsys):
    old, _ = roots
    target = {"same": old, "child": old / "nested", "parent": old.parent}[destination]
    before = tree(old)
    assert migrate_mod.main(["--from", str(old), "--to", str(target)]) == 1
    assert tree(old) == before
    assert "must not overlap" in capsys.readouterr().err


def test_concurrently_created_empty_destination_is_not_replaced(roots, monkeypatch, capsys):
    old, new = roots
    original = Path.mkdir
    created = {}
    def mkdir(path, *args, **kwargs):
        result = original(path, *args, **kwargs)
        if path == new:
            original(new / "keybinds")
            created["inode"] = (new / "keybinds").stat().st_ino
        return result
    monkeypatch.setattr(Path, "mkdir", mkdir)
    assert migrate_mod.main(["--from", str(old), "--to", str(new)]) == 1
    assert (new / "keybinds").stat().st_ino == created["inode"]
    assert list((new / "keybinds").iterdir()) == []
    assert (old / "keybinds" / "items.json").is_file()
    assert (old / "wallpaper").is_dir()
    assert "cannot migrate" in capsys.readouterr().err


def test_dry_run_refuses_a_conflicting_destination(roots, capsys):
    old, new = roots
    (new / "keybinds").mkdir(parents=True)
    (new / "keybinds" / "items.json").write_text('[{"id":"other"}]')
    before = tree(old)
    assert migrate_mod.main(["--from", str(old), "--to", str(new), "--dry-run"]) == 1
    assert tree(old) == before
    assert "no domains moved" in capsys.readouterr().err
