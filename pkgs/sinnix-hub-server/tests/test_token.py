from concurrent.futures import ThreadPoolExecutor
from itertools import count
from pathlib import Path
from threading import Barrier

import pytest

from sinnix_hub_server import server


@pytest.mark.parametrize("initial", [None, b"", b" \n\t"])
def test_initialize_or_recover_token(tmp_path, initial):
    path = tmp_path / "runtime" / "token"
    if initial is not None:
        path.parent.mkdir()
        path.write_bytes(initial)
    token = server.ensure_token(path)
    assert token
    assert path.read_text() == token + "\n"
    assert path.stat().st_mode & 0o777 == 0o600


def test_usable_token_survives_restart_without_parent_write_access(tmp_path, monkeypatch):
    path = tmp_path / "runtime" / "token"
    path.parent.mkdir()
    path.write_text("fixture-token\n")
    inode = path.stat().st_ino
    path.parent.chmod(0o500)
    monkeypatch.setattr(server.secrets, "token_urlsafe", lambda _: pytest.fail("rotated usable token"))
    try:
        assert server.ensure_token(path) == "fixture-token"
        assert path.read_bytes() == b"fixture-token\n"
        assert path.stat().st_ino == inode
        assert path.stat().st_mode & 0o777 == 0o600
    finally:
        path.parent.chmod(0o700)


@pytest.mark.parametrize("initial", [None, b" \n"])
def test_concurrent_starters_share_one_token(tmp_path, monkeypatch, initial):
    path = tmp_path / "token"
    if initial is not None:
        path.write_bytes(initial)
    sequence = count()
    monkeypatch.setattr(server.secrets, "token_urlsafe", lambda _: f"fixture-{next(sequence)}")
    barrier = Barrier(8)

    def start(_):
        barrier.wait(timeout=10)
        return server.ensure_token(path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        tokens = list(pool.map(start, range(8)))
    assert len(set(tokens)) == 1
    assert path.read_text() == tokens[0] + "\n"


def test_token_read_error_is_not_missing_state(tmp_path, monkeypatch):
    path = tmp_path / "token"
    path.write_bytes(b"\n")
    real_read = Path.read_text

    def read(candidate, *args, **kwargs):
        if candidate == path:
            raise PermissionError("synthetic denied token")
        return real_read(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read)
    monkeypatch.setattr(server, "atomic_publish", lambda *args, **kwargs: pytest.fail("published after read failure"))
    with pytest.raises(PermissionError, match="synthetic denied"):
        server.ensure_token(path)
    assert path.read_bytes() == b"\n"


def test_failed_empty_token_repair_preserves_original(tmp_path, monkeypatch):
    path = tmp_path / "token"
    path.write_bytes(b" \n")
    publish = server.atomic_publish

    def fail_replacement(*args, **kwargs):
        if not kwargs.get("exclusive"):
            raise OSError("synthetic publication failure")
        return publish(*args, **kwargs)

    monkeypatch.setattr(server, "atomic_publish", fail_replacement)
    with pytest.raises(OSError, match="synthetic publication failure"):
        server.ensure_token(path)
    assert path.read_bytes() == b" \n"


def test_exclusive_creation_respects_another_publisher(tmp_path, monkeypatch):
    path = tmp_path / "token"
    publish = server.atomic_publish

    def concurrent_publish(destination, payload, **kwargs):
        assert kwargs["exclusive"]
        publish(destination, b"fixture-winner\n", fsync=True)
        return False

    monkeypatch.setattr(server, "atomic_publish", concurrent_publish)
    assert server.ensure_token(path) == "fixture-winner"
    assert path.read_bytes() == b"fixture-winner\n"
