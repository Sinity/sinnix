import json
import shlex
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).parents[3]
SCRIPT = ROOT / "scripts" / "sinnix-config-drift"


def run(
    tmp_path,
    manifest,
    *,
    proc_files=None,
    systemctl_output="",
    current_revision="fixture",
    booted_revision="older",
    extra_args=None,
    systemctl_log=None,
):
    proc_root = tmp_path / "root"
    for relative, value in (proc_files or {}).items():
        path = proc_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    manifest_path = tmp_path / "config.json"
    manifest_path.write_text(json.dumps({"sinnix": {"drift": manifest}}))
    systemctl = tmp_path / "systemctl"
    log = ""
    if systemctl_log is not None:
        log = "printf '%s\\n' \"$@\" > " + shlex.quote(str(systemctl_log)) + "\n"
    systemctl.write_text(
        "#!/bin/sh\n" + log + "cat <<'EOF'\n" + systemctl_output + "\nEOF\n"
    )
    systemctl.chmod(0o755)
    current = tmp_path / "current"
    booted = tmp_path / "booted"
    for root, revision in ((current, current_revision), (booted, booted_revision)):
        config_path = root / "etc/sinnix/config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps({"meta": {"configurationRevision": revision}})
        )
    output = tmp_path / "drift.jsonl"
    subprocess.run(
        [
            "python3",
            str(SCRIPT),
            "--manifest",
            str(manifest_path),
            "--proc-root",
            str(proc_root),
            "--systemctl",
            str(systemctl),
            "--current-system",
            str(current),
            "--booted-system",
            str(booted),
            "--output",
            str(output),
            *(extra_args or []),
        ],
        check=True,
    )
    return [json.loads(line) for line in output.read_text().splitlines()]


def test_sysctl_drift_and_missing_probe_are_explicit(tmp_path):
    rows = run(
        tmp_path,
        {
            "sysctls": {"vm.swappiness": 10, "vm.page-cluster": 0},
            "slices": {},
            "swap": [],
            "generation": {"revision": "fixture"},
        },
        proc_files={
            "proc/sys/vm/swappiness": "1\n",
            "proc/swaps": "Filename\ttype\tsize\tused\tpriority\n",
        },
    )
    by_check = {row["check"]: row for row in rows}
    assert by_check["sysctl:vm.swappiness"]["match"] is False
    assert by_check["sysctl:vm.page-cluster"]["status"] == "unavailable"
    assert stat.S_IMODE((tmp_path / "drift.jsonl").stat().st_mode) == 0o600


def test_generation_unknown_revision_is_always_flagged(tmp_path):
    # configurationRevision=="unknown" must be reported as a loud,
    # error-severity finding even when the manifest's own `expected` value is
    # also "unknown": both sides come from the same potentially-broken
    # evaluation, so a naive equality check would call that self-referential
    # case a match.
    rows = run(
        tmp_path,
        {
            "sysctls": {},
            "slices": {},
            "swap": [],
            "generation": {"revision": "unknown"},
        },
        proc_files={"proc/swaps": "Filename\ttype\tsize\tused\tpriority\n"},
        current_revision="unknown",
        booted_revision="unknown",
    )
    by_check = {row["check"]: row for row in rows}
    for check in ("generation:current", "generation:booted"):
        assert by_check[check]["live"] == "unknown"
        assert by_check[check]["match"] is False
        assert by_check[check]["status"] == "drifted"
        assert by_check[check]["severity"] == "error"
        assert by_check[check]["reboot_required"] is True


def test_slice_and_generation_mismatch_require_reboot(tmp_path):
    rows = run(
        tmp_path,
        {
            "sysctls": {},
            "slices": {"system": {"background": {"CPUWeight": 3}}},
            "swap": [],
            "generation": {"revision": "fixture"},
        },
        proc_files={"proc/swaps": "Filename\ttype\tsize\tused\tpriority\n"},
        systemctl_output="Id=background.slice\nCPUWeight=5\n\nId=earlyoom.service\nMainPID=0",
    )
    by_check = {row["check"]: row for row in rows}
    assert by_check["slice:system:background.slice"]["match"] is False
    assert by_check["generation:current"]["match"] is True
    assert by_check["generation:booted"]["match"] is False
    assert by_check["generation:booted"]["reboot_required"] is True


def test_noctalia_state_override_of_a_declared_key_drifts(tmp_path):
    """A settings.toml value that overrides a declared critical key is a
    drift row; a fake noctalia reproduces the merge (state wins)."""
    config_home = tmp_path / "noctalia"
    config_home.mkdir()
    (config_home / "config.toml").write_text(
        '[accessibility]\nui_scale = 1.5\n[bar.default]\nposition = "bottom"\nend = ["a", "b"]\n'
    )
    fake = tmp_path / "fake-noctalia"
    fake.write_text(
        "#!/bin/sh\n"
        'test -f "$NOCTALIA_CONFIG_HOME/noctalia/config.toml" || exit 1\n'
        "printf '%s\\n' '[accessibility]' 'ui_scale = 1.5' '[bar.default]' "
        '\'position = "top"\' \'end = ["a", "b"]\'\n'
    )
    fake.chmod(0o755)
    rows = run(
        tmp_path,
        {
            "sysctls": {},
            "slices": {},
            "swap": [],
            "generation": {"revision": "fixture"},
        },
        proc_files={"proc/swaps": "Filename\ttype\tsize\tused\tpriority\n"},
        extra_args=[
            "--noctalia",
            str(fake),
            "--noctalia-config-home",
            str(config_home),
        ],
    )
    by_check = {row["check"]: row for row in rows}
    assert by_check["noctalia:bar.default.position"]["status"] == "drifted"
    assert by_check["noctalia:bar.default.position"]["live"] == "top"
    assert by_check["noctalia:accessibility.ui_scale"]["status"] == "matched"
    assert by_check["noctalia:bar.default.end"]["status"] == "matched"
    assert (
        "noctalia:bar.default.thickness" not in by_check
    )  # undeclared keys are not checked


def test_systemd_snapshot_batches_system_slices_and_earlyoom(tmp_path):
    command_log = tmp_path / "systemctl.argv"
    rows = run(
        tmp_path,
        {
            "sysctls": {},
            "slices": {
                "system": {
                    "background": {"CPUWeight": 3},
                    "nix": {"MemoryMax": "2G"},
                }
            },
            "swap": [],
            "generation": {"revision": "fixture"},
            "earlyoom": {"freeMemThreshold": 5, "freeSwapThreshold": 10},
        },
        proc_files={"proc/swaps": "Filename\ttype\tsize\tused\tpriority\n"},
        systemctl_output=(
            "Id=background.slice\nCPUWeight=3\n\n"
            "Id=nix.slice\nMemoryMax=2147483648\n\n"
            "Id=earlyoom.service\nMainPID=0"
        ),
        systemctl_log=command_log,
    )
    by_check = {row["check"]: row for row in rows}
    assert by_check["slice:system:background.slice"]["status"] == "matched"
    assert by_check["slice:system:nix.slice"]["status"] == "matched"
    assert by_check["earlyoom"]["status"] == "unavailable"
    assert command_log.read_text().splitlines()[:5] == [
        "show",
        "background.slice",
        "nix.slice",
        "earlyoom.service",
        "-p",
    ]


def test_unavailable_systemd_snapshot_stays_explicit(tmp_path):
    rows = run(
        tmp_path,
        {
            "sysctls": {},
            "slices": {"system": {"background": {"CPUWeight": 3}}},
            "swap": [],
            "generation": {"revision": "fixture"},
        },
        proc_files={"proc/swaps": "Filename\ttype\tsize\tused\tpriority\n"},
    )
    by_check = {row["check"]: row for row in rows}
    assert by_check["slice:system:background.slice"]["status"] == "unavailable"


def test_privileged_collection_publishes_as_operator(tmp_path, monkeypatch):
    import os
    import pwd
    import runpy
    from types import SimpleNamespace

    main = runpy.run_path(str(SCRIPT))["main"]
    calls = []
    account = SimpleNamespace(pw_name="operator", pw_uid=1234, pw_gid=2345)
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    monkeypatch.setattr(pwd, "getpwnam", lambda name: account)
    monkeypatch.setattr(os, "initgroups", lambda name, gid: calls.append(("groups", name, gid)))
    monkeypatch.setattr(os, "setgid", lambda gid: calls.append(("gid", gid)))
    monkeypatch.setattr(os, "setuid", lambda uid: calls.append(("uid", uid)))
    main.__globals__["collect"] = lambda *args: calls.append(("collect",)) or []
    main.__globals__["atomic_publish"] = lambda *args, **kwargs: calls.append(("publish", kwargs["mode"]))
    manifest = tmp_path / "config.json"
    manifest.write_text("{}")
    main(["--manifest", str(manifest), "--output", str(tmp_path / "report.jsonl"), "--user-name", "operator"])
    assert calls == [("collect",), ("groups", "operator", 2345), ("gid", 2345), ("uid", 1234), ("publish", 0o600)]


def test_swap_order_does_not_change_identity(tmp_path):
    rows = run(
        tmp_path,
        {"sysctls": {}, "slices": {}, "swap": [
            {"device": "/fixture/swap", "priority": 10},
            {"device": "/dev/zram0", "priority": 100},
        ], "generation": {"revision": "fixture"}},
        proc_files={"proc/swaps": (
            "Filename Type Size Used Priority\n"
            "/dev/zram0 partition 100 0 100\n"
            "/fixture/swap file 100 0 10\n"
        )},
    )
    assert next(row for row in rows if row["check"] == "swap")["match"] is True


def test_swap_priority_difference_is_still_drift(tmp_path):
    rows = run(
        tmp_path,
        {"sysctls": {}, "slices": {}, "swap": [
            {"device": "/fixture/swap", "priority": 10},
        ], "generation": {"revision": "fixture"}},
        proc_files={"proc/swaps": "Filename Type Size Used Priority\n/fixture/swap file 100 0 -2\n"},
    )
    assert next(row for row in rows if row["check"] == "swap")["match"] is False
