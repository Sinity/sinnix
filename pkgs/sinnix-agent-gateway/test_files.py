from __future__ import annotations

from pathlib import Path

import pytest
from sinnix_agent_gateway.capabilities import PolicyError, Principal
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.files import FileError, HostFileService


def service(tmp_path: Path, principal_name: str) -> HostFileService:
    return HostFileService(
        GatewayConfig(state_dir=tmp_path / "state", projects={}),
        Principal.for_name(principal_name),
    )


def test_observer_reads_bounded_host_file_and_cannot_write(tmp_path: Path) -> None:
    target = tmp_path / "evidence.txt"
    target.write_text("one\ntwo\nthree\n")
    observer = service(tmp_path, "observer")

    result = observer.read("read", str(target), offset=4, max_bytes=4)

    assert result["content"] == "two\n"
    assert result["truncated"] is True
    assert len(result["sha256"]) == 64
    with pytest.raises(PolicyError):
        observer.write("replace", str(target), content="forbidden")
    assert target.read_text() == "one\ntwo\nthree\n"


def test_operator_write_uses_compare_and_swap_and_receipts(tmp_path: Path) -> None:
    target = tmp_path / "fixture.txt"
    target.write_text("before")
    operator = service(tmp_path, "operator")
    before = operator.read("stat", str(target))["sha256"]

    replaced = operator.write(
        "replace", str(target), content="after", expected_sha256=before
    )
    appended = operator.write(
        "append",
        str(target),
        content="!",
        expected_sha256=replaced["sha256"],
    )

    assert target.read_text() == "after!"
    assert appended["previous_sha256"] == replaced["sha256"]
    with pytest.raises(FileError, match="expected_sha256"):
        operator.write(
            "replace", str(target), content="lost update", expected_sha256=before
        )
    removed = operator.write("remove", str(target), expected_sha256=appended["sha256"])
    assert removed["removed"] is True
    assert not target.exists()


def test_operator_copies_and_moves_regular_files_without_replacing_destination(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.txt"
    copy = tmp_path / "copy.txt"
    moved = tmp_path / "moved.txt"
    source.write_text("gateway fixture")
    operator = service(tmp_path, "operator")
    source_hash = operator.read("stat", str(source))["sha256"]

    copied = operator.write(
        "copy", str(source), destination=str(copy), expected_sha256=source_hash
    )
    moved_result = operator.write(
        "move", str(copy), destination=str(moved), expected_sha256=source_hash
    )

    assert source.read_text() == "gateway fixture"
    assert not copy.exists()
    assert moved.read_text() == "gateway fixture"
    assert copied["destination"] == str(copy)
    assert moved_result["removed"] is True
    with pytest.raises(FileError, match="destination already exists"):
        operator.write("move", str(source), destination=str(moved))
    assert source.exists()


def test_operator_rejects_symlink_mutation(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("before")
    link = tmp_path / "target-link.txt"
    link.symlink_to(target)

    with pytest.raises(FileError, match="symlinks"):
        service(tmp_path, "operator").write("replace", str(link), content="after")

    assert target.read_text() == "before"


def test_observer_cannot_read_secret_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sinnix_agent_gateway import files

    secret_root = tmp_path / "secret-root"
    secret_root.mkdir()
    secret = secret_root / "secret.txt"
    secret.write_text("secret")
    monkeypatch.setattr(files, "_SECRET_ROOTS", (secret_root,))

    with pytest.raises(FileError, match="unavailable"):
        service(tmp_path, "observer").read("read", str(secret))


def test_list_is_bounded_and_reports_symlink(tmp_path: Path) -> None:
    directory = tmp_path / "directory"
    directory.mkdir()
    (directory / "a").write_text("a")
    (directory / "b").write_text("b")
    (directory / "link").symlink_to(directory / "a")

    observer = service(tmp_path, "observer")
    bounded = observer.read("list", str(directory), max_entries=2)
    complete = observer.read("list", str(directory), max_entries=3)

    assert [entry["name"] for entry in bounded["entries"]] == ["a", "b"]
    assert bounded["truncated"] is True
    assert complete["entries"][-1]["name"] == "link"
    assert complete["entries"][-1]["symlink"] is True


def test_same_filesystem_move_has_no_hardlink_unlink_intermediate(tmp_path, monkeypatch):
    from sinnix_agent_gateway import files
    source=tmp_path/'source';destination=tmp_path/'destination';source.write_text('payload')
    inode=source.stat().st_ino
    def forbidden(*args,**kwargs):
        raise AssertionError('a same-filesystem move must not create an extra hard link')
    monkeypatch.setattr(files.os,'link',forbidden)
    service(tmp_path,'operator').write('move',str(source),destination=str(destination))
    assert not source.exists() and destination.read_text()=='payload'
    assert destination.stat().st_ino==inode and destination.stat().st_nlink==1


def test_nonwritable_source_parent_refused_before_destination_creation(tmp_path,monkeypatch):
    from sinnix_agent_gateway import files
    source=tmp_path/'source';destination=tmp_path/'destination';source.write_text('payload')
    original=files.os.access
    monkeypatch.setattr(files.os,'access',lambda p,mode,**kw: False if Path(p)==source.parent else original(p,mode,**kw))
    with pytest.raises(FileError,match='source parent'):
        service(tmp_path,'operator').write('move',str(source),destination=str(destination))
    assert source.read_text()=='payload' and not destination.exists()


def test_atomic_move_failure_does_not_leave_a_destination(tmp_path,monkeypatch):
    import errno
    from sinnix_agent_gateway import files
    source=tmp_path/'source';destination=tmp_path/'destination';source.write_text('payload')
    def refused(*args,**kwargs):raise PermissionError(errno.EACCES,'fixture denial')
    monkeypatch.setattr(files,'rename_noreplace',refused)
    with pytest.raises(FileError,match='atomic move failed'):
        service(tmp_path,'operator').write('move',str(source),destination=str(destination))
    assert source.read_text()=='payload' and not destination.exists()


def test_cross_filesystem_unlink_failure_reports_both_preserved_objects(tmp_path,monkeypatch):
    import errno
    from sinnix_agent_gateway import files
    source=tmp_path/'source';destination=tmp_path/'destination';source.write_text('payload')
    def cross_device(*args,**kwargs):raise OSError(errno.EXDEV,'fixture crossing')
    monkeypatch.setattr(files,'rename_noreplace',cross_device)
    original=Path.unlink
    def block_source(self,*args,**kwargs):
        if self==source:raise PermissionError('fixture denied unlink')
        return original(self,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',block_source)
    with pytest.raises(FileError,match='both paths retained'):
        service(tmp_path,'operator').write('move',str(source),destination=str(destination))
    assert source.read_text()==destination.read_text()=='payload'
