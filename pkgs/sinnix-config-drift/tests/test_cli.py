import json
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
):
    proc_root = tmp_path / "root"
    for relative, value in (proc_files or {}).items():
        path = proc_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)
    manifest_path = tmp_path / "config.json"
    manifest_path.write_text(json.dumps({"sinnix": {"drift": manifest}}))
    systemctl = tmp_path / "systemctl"
    systemctl.write_text(f"#!/bin/sh\nprintf '%s\\n' {systemctl_output!r}")
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
        systemctl_output="CPUWeight=5",
    )
    by_check = {row["check"]: row for row in rows}
    assert by_check["slice:system:background.slice"]["match"] is False
    assert by_check["generation:current"]["match"] is True
    assert by_check["generation:booted"]["match"] is False
    assert by_check["generation:booted"]["reboot_required"] is True
