"""The nightly sequence against fake systemd units and local markers only."""

from __future__ import annotations

import sys
import time

from fakes import FakeHost
from sinnix_backup import cli, markers, nightly

COORDINATOR_STEPS = [
    "machine-telemetry-sqlite-backup.service",
    "polylogue-sqlite-backup.service",
    "btrbk.service",
    "borgbackup-job-polylogue-state.service",
    "borgbackup-job-sinex-blobs.service",
    "borgbackup-job-realm.service",
    "borgbackup-job-genome.service",
    "borgbackup-job-persist.service",
    "borgbackup-root-snapshots.service",
    "borgbackup-maintenance.service",
    "borgbackup-coverage-audit-realm.service",
    "borgbackup-local-dumps.service",
]
EXPECTED_STARTS = [["start", unit] for unit in COORDINATOR_STEPS]
ARCHIVE_STARTS = EXPECTED_STARTS[3:]

# A unit that fails when the sequence holds the Borg lock while it runs.
LOCK_FREE = "import fcntl, sys\nfcntl.flock(open(sys.argv[1], 'a'), fcntl.LOCK_EX | fcntl.LOCK_NB)\n"


class Fixture:
    def __init__(self, root, fixture_config, monkeypatch, capfd):
        self.path, self.config = fixture_config
        self.host = FakeHost(root, self.config.lock_path)
        self.host.apply(monkeypatch)
        self.capfd = capfd
        for label in self.config.nightly.drain_sources:
            self.config.source(label).snapshot_directory.mkdir(
                parents=True, exist_ok=True
            )
        self.host.set_units(
            {
                unit: [sys.executable, "-c", LOCK_FREE, str(self.config.lock_path)]
                for unit in COORDINATOR_STEPS
            }
        )

    def run(self):
        """Run the sequence; return its exit status, captured output and systemctl calls."""
        log = self.host.root / "logs/commands"
        log.write_text("")
        code = cli.main(["nightly", "--config", str(self.path)])
        captured = self.capfd.readouterr()
        calls = [entry[1:] for entry in self.host.commands() if entry[0] == "systemctl"]
        return code, captured, calls


def test_sequence_from_local_markers(backup_root, fixture_config, monkeypatch, capfd):
    fixture = Fixture(backup_root, fixture_config, monkeypatch, capfd)
    config = fixture.config
    state = config.state_directory
    code, captured, calls = fixture.run()
    assert code == 0, captured.out + captured.err
    assert calls == EXPECTED_STARTS, (
        "empty retries leave an ongoing integrity check alone"
    )
    acquisition_marker = state / "coordinator.acquisition"
    acquisition_text = acquisition_marker.read_text()

    # A local acknowledgement routes scheduling without repository access;
    # the drains themselves check their archives.
    acknowledged = "realm.20260403T070000+0000"
    (config.source("realm").snapshot_directory / acknowledged).mkdir()
    latest = config.source("realm").marker(state, "latest-archived")
    latest.write_text(f"snapshot={acknowledged}\n")
    acknowledgements = latest.parent / (latest.name + ".by-snapshot")
    acknowledgements.mkdir()
    (acknowledgements / acknowledged).write_bytes(latest.read_bytes())
    code, captured, calls = fixture.run()
    assert code == 0, captured.out + captured.err
    assert calls == ARCHIVE_STARTS, (
        "acknowledged snapshots do not stop checks or open Borg from the sequence"
    )

    # A pending genome snapshot alone stops the resumable integrity check and
    # gets a drain attempt in the same run.
    (config.source("genome").snapshot_directory / "genome.20260404T070000+0000").mkdir()
    code, captured, calls = fixture.run()
    assert code == 0, captured.out + captured.err
    assert calls == [["stop", config.nightly.verify_unit]] + ARCHIVE_STARTS

    acquisition_marker.unlink()
    fixture.host.flag("fail-unit-polylogue-sqlite-backup.service").touch()
    code, captured, calls = fixture.run()
    assert code == 1, captured.out + captured.err
    assert ["start", "btrbk.service"] not in calls
    assert calls[-len(ARCHIVE_STARTS) :] == ARCHIVE_STARTS
    assert "reason=dump-failure" in captured.err

    # Daily markers are checked at each unit, not against the time the
    # sequence started, which can precede a long archive backlog by a day.
    fixture.host.flag("fail-unit-polylogue-sqlite-backup.service").unlink()
    acquisition_marker.write_text(acquisition_text)
    now = int(time.time())
    for marker, policy in config.nightly.daily_markers.values():
        marker.write_text(f"archive=synthetic\nepoch={now}\npolicy_sha256={policy}\n")
    clock_calls = []

    def clock():
        clock_calls.append(None)
        return now + (90000 if len(clock_calls) > 1 else 0)

    monkeypatch.setattr(nightly, "_now", clock)
    code, captured, calls = fixture.run()
    assert code == 0, captured.out + captured.err
    assert ["start", "btrbk.service"] not in calls
    for unit in (
        "borgbackup-job-polylogue-state.service",
        "borgbackup-job-sinex-blobs.service",
    ):
        assert ["start", unit] in calls


def test_daily_marker_skips_only_with_current_policy(
    backup_root, fixture_config, monkeypatch, capfd
):
    fixture = Fixture(backup_root, fixture_config, monkeypatch, capfd)
    unit = "borgbackup-job-polylogue-state.service"
    marker, policy = fixture.config.nightly.daily_markers[unit]
    marker.parent.mkdir(parents=True, exist_ok=True)
    now = int(time.time())
    markers.publish_marker(
        marker, f"archive=synthetic\nepoch={now}\npolicy_sha256={policy}\n"
    )
    code, captured, calls = fixture.run()
    assert code == 0, captured.out + captured.err
    assert ["start", unit] not in calls
    assert (
        f"backup_phase=coordinator unit={unit} status=skipped reason=already-fresh"
        in captured.out
    )
    markers.publish_marker(
        marker, f"archive=synthetic\nepoch={now}\npolicy_sha256={'0' * 64}\n"
    )
    code, captured, calls = fixture.run()
    assert code == 0, captured.out + captured.err
    assert ["start", unit] in calls
