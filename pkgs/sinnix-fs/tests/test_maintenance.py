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
    result = m.capacity(
        Path("/synthetic"),
        15,
        10,
        info=SimpleNamespace(f_blocks=100, f_frsize=4096, f_bavail=4),
    )
    assert result["discretionary_work"] == "defer"
    assert result["available_bytes"] == 16384
    assert result["forecast"]["status"] == "not_requested"


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


@pytest.mark.parametrize("floor", [5, 10])
def test_exact_floor_admits_and_one_byte_below_defers(floor):
    for available, expected in [(floor, "admit"), (floor - 1, "defer")]:
        result = m.capacity(
            Path("/synthetic"),
            15,
            floor,
            info=SimpleNamespace(f_blocks=100, f_frsize=1, f_bavail=available),
        )
        assert result["discretionary_work"] == expected
        assert not result["target_met"]


def test_offline_outer_is_never_probed_but_required_root_defers(monkeypatch):
    monkeypatch.setattr(m, "read_payload_mounts", lambda: {})
    monkeypatch.setattr(
        m.os, "open", lambda *a, **k: pytest.fail("must not touch an offline mount")
    )
    decision = m.admission()
    assert not decision["admitted"]
    assert decision["blocked"] == ["/realm"]
    assert all(row["status"] == "not_mounted" for row in decision["volumes"])


def test_changed_mount_refuses_before_capacity_probe(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "VOLUMES", ((tmp_path, 15, 10),))
    monkeypatch.setattr(m, "read_payload_mounts", lambda: {tmp_path: -1})
    monkeypatch.setattr(
        m.os, "fstatvfs", lambda *a: pytest.fail("must not probe the replacement mount")
    )
    decision = m.admission()
    assert not decision["admitted"]
    assert "mount changed" in decision["volumes"][0]["reason"]


def test_unreadable_mount_table_defers_instead_of_claiming_zero(monkeypatch):
    def fail():
        raise PermissionError("synthetic mount table refusal")

    monkeypatch.setattr(m, "read_payload_mounts", fail)
    decision = m.admission()
    assert not decision["admitted"]
    assert all(row["status"] == "unavailable" for row in decision["volumes"])
    assert not any("available_bytes" in row for row in decision["volumes"])


def test_pinned_native_mount_capacity_and_admission_cli(tmp_path, monkeypatch, capsys):
    fd = m.os.open(tmp_path, m.os.O_PATH)
    try:
        mount_id = next(
            int(line.partition(":")[2])
            for line in Path(f"/proc/self/fdinfo/{fd}").read_text().splitlines()
            if line.startswith("mnt_id:")
        )
    finally:
        m.os.close(fd)
    monkeypatch.setattr(m, "VOLUMES", ((tmp_path, 15, 10),))
    monkeypatch.setattr(m, "read_payload_mounts", lambda: {tmp_path: mount_id})
    monkeypatch.setattr(
        m.os,
        "fstatvfs",
        lambda fd: SimpleNamespace(f_blocks=100, f_frsize=1, f_bavail=10),
    )
    assert m.main(["admission"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["admitted"] and not result["volumes"][0]["target_met"]
    assert result["volumes"][0]["mount_id"] == mount_id
    assert list(tmp_path.iterdir()) == []


def test_deferred_scan_creates_no_generation_or_ledger(tmp_path, monkeypatch, capsys):
    from sinnix_fs import inventory

    root = tmp_path / "index"
    monkeypatch.setattr(
        m, "admission", lambda volume: {"admitted": False, "blocked": ["/realm"]}
    )
    monkeypatch.setattr(
        inventory,
        "publish_generation",
        lambda *a, **k: pytest.fail("must not run the writer"),
    )
    assert inventory.main(["scan", "--out-dir", str(root)]) == 1
    assert not root.exists()
    assert json.loads(capsys.readouterr().err)["blocked"] == ["/realm"]


def test_unrelated_full_disk_does_not_block_selected_output_volume(monkeypatch):
    calls = []

    def observations(volume=None):
        calls.append(volume)
        assert volume == Path("/realm")
        return [{"path": "/realm", "status": "observed", "discretionary_work": "admit"}]

    monkeypatch.setattr(m, "volume_capacity", observations)
    assert m.admission(Path("/realm"))["admitted"]
    assert calls == [Path("/realm")]


def test_explicit_offline_destination_defers_without_probing(monkeypatch):
    monkeypatch.setattr(m, "read_payload_mounts", lambda: {})
    monkeypatch.setattr(
        m.os, "open", lambda *a, **k: pytest.fail("must not activate automount")
    )
    decision = m.admission(Path("/outer-realm"))
    assert not decision["admitted"] and decision["blocked"] == ["/outer-realm"]
    assert len(decision["volumes"]) == 1


@pytest.fixture
def store(monkeypatch, tmp_path):
    root = tmp_path / "store"
    root.mkdir()
    monkeypatch.setattr(m, "NIX_STORE", root)
    monkeypatch.setattr(m, "VOLUMES", ())
    monkeypatch.setattr(m.shutil, "which", lambda name: "/synthetic/bin/" + name)
    return root


def test_nix_owner_keeps_native_root_authority_and_excludes_env_override(
    store, monkeypatch
):
    plan = m.plan("nix-store")
    monkeypatch.setenv("NIX_REMOTE", "ssh://unexpected")
    monkeypatch.setenv("NIX_CONFIG", "keep-derivations = false")
    (store / "retained-root").write_text("neutral rooted payload")

    def native(command, **kwargs):
        assert command == ["/synthetic/bin/nix-store", "--store", "daemon", "--gc"]
        assert not any(key.startswith("NIX_") for key in kwargs["env"])
        return SimpleNamespace(
            returncode=1, stdout="native roots retained", stderr="native refusal"
        )

    result = m.apply(plan, run=native)
    assert result["exit_code"] == 1 and result["stderr"] == "native refusal"
    assert (store / "retained-root").read_text() == "neutral rooted payload"


def test_nix_replaced_store_or_forged_operation_refuses_before_native_call(store):
    plan = m.plan("nix-store")

    def forbidden(*args, **kwargs):
        pytest.fail("must not invoke the native owner")

    plan["actions"][0]["operation"] = "delete"
    with pytest.raises(ValueError, match="declared native Nix"):
        m.apply(plan, run=forbidden)
    plan["actions"][0]["operation"] = "gc"
    store.rename(store.with_name("retained"))
    store.mkdir()
    with pytest.raises(ValueError, match="identity changed"):
        m.apply(plan, run=forbidden)
