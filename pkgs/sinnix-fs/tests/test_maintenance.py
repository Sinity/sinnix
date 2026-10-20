"""Destructive boundaries: replaced roots and native in-use refusals stay safe."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sinnix_fs import maintenance as m


@pytest.fixture
def cache(monkeypatch, tmp_path):
    root = tmp_path / "cache"
    root.mkdir()
    monkeypatch.setattr(m, "UV_CACHE", root)
    monkeypatch.setattr(m, "VOLUMES", ())
    return root


def test_replaced_root_refuses_before_native_call(cache):
    document = m.plan()
    cache.rename(cache.with_name("retained"))
    cache.mkdir()
    with pytest.raises(ValueError, match="identity changed"):
        m.apply(document, run=lambda *a, **k: pytest.fail("must not invoke uv"))


def test_symlink_root_refuses_without_following(cache):
    document = m.plan()
    cache.rename(cache.with_name("retained"))
    cache.symlink_to(cache.with_name("retained"))
    with pytest.raises(ValueError, match="physical path"):
        m.apply(document, run=lambda *a, **k: pytest.fail("must not invoke uv"))


def test_native_refusal_is_returned_and_exact_directory_pinned(cache, monkeypatch):
    document = m.plan()
    (cache / "retained.txt").write_text("synthetic active data")
    monkeypatch.setenv("UV_NO_CACHE", "1")
    monkeypatch.setenv("UV_CACHE_DIR", "/unexpected")

    def native(command, **kwargs):
        assert command[:6] == [
            "uv",
            "--no-config",
            "--offline",
            "cache",
            "prune",
            "--cache-dir",
        ]
        assert "--force" not in command
        assert Path(command[-1]).samefile(cache)
        assert not any(key.startswith("UV_") for key in kwargs["env"])
        cache.rename(cache.with_name("moved"))
        cache.mkdir()
        assert Path(command[-1]).samefile(cache.with_name("moved"))
        return SimpleNamespace(returncode=2, stdout="", stderr="cache is in use")

    result = m.apply(document, run=native)
    assert result["exit_code"] == 2
    assert (
        cache.with_name("moved") / "retained.txt"
    ).read_text() == "synthetic active data"


def test_changed_plan_digest_refuses_before_apply(cache, tmp_path, capsys):
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(m.plan()))
    assert m.main(["apply", str(path), "--expected-sha256", "0" * 64]) == 2
    assert "digest changed" in capsys.readouterr().err


def test_floor_defers_discretionary_work_without_fabricating_forecast(monkeypatch):
    monkeypatch.setattr(
        m.os,
        "statvfs",
        lambda path: SimpleNamespace(f_blocks=100, f_frsize=4096, f_bavail=4),
    )
    result = m.capacity(Path("/synthetic"), 15, 10)
    assert result["discretionary_work"] == "defer"
    assert result["available_bytes"] == 16384
    assert result["forecast"]["status"] == "unavailable"


def test_accounting_native_failure_is_incomplete_not_zero(tmp_path, monkeypatch):
    payload = tmp_path / "synthetic.bin"
    payload.write_bytes(b"neutral")
    calls = []
    monkeypatch.setattr(m.shutil, "which", lambda name: "/synthetic/bin/" + name)

    def native(command, **kwargs):
        calls.append(command)
        assert command[:2] == ["sudo", "-n"]
        assert command[-2:] == ["--", str(payload)]
        return SimpleNamespace(
            returncode=1, stdout="partial native output", stderr="metadata unavailable"
        )

    result = m.account([payload], run=native)
    assert not result["complete"]
    assert len(calls) == 2
    assert all(row["exit_code"] == 1 for row in result["reports"])
    assert result["reports"][0]["stdout"] == "partial native output"
    assert payload.read_bytes() == b"neutral"


def test_accounting_refuses_missing_or_relative_roots_before_native_call(tmp_path):
    def native(*args, **kwargs):
        pytest.fail("must not call native owner")

    with pytest.raises(ValueError, match="absolute"):
        m.account([Path("relative")], run=native)
    with pytest.raises(FileNotFoundError):
        m.account([tmp_path / "absent"], run=native)
