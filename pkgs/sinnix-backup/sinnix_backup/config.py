"""The backup policy Nix writes to /etc/sinnix/backup.json, as typed values.

Nix owns every path, repository, exclusion and unit name; this module only
reads them. `coverage` objects pass through unchanged because their exact
JSON is hashed into stored archive records (see coverage.policy_identity).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path("/etc/sinnix/backup.json")


@dataclass(frozen=True)
class Repository:
    name: str
    url: str
    path: Path

    @property
    def initialized(self) -> bool:
        return (self.path / "config").exists()


@dataclass(frozen=True)
class SnapshotSource:
    """One btrbk (or initrd) snapshot stream drained into one repository."""

    label: str
    repository: str
    snapshot_directory: Path
    name_glob: str
    bind_path: Path | None
    archive_prefix: str
    replacement_suffix: str
    # The coverage policy: a dict for snapshot drains, a list of excluded
    # paths for root snapshots. Hashed verbatim into every archive record.
    coverage: Any
    # True when an archive is accepted through its recorded create command
    # (realm, genome); False when a content comparison checks it (persist).
    create_check: bool
    files_cache_suffix: str | None
    # How many of the newest local snapshots `take-snapshots` keeps, whether
    # or not the drain has archived them; None leaves deletion to the drain.
    local_snapshots: int | None

    def marker(self, state_directory: Path, kind: str) -> Path:
        """`<label>.<kind>` in the state directory (latest-archived, last-success, ...)."""
        return state_directory / f"{self.label}.{kind}"


@dataclass(frozen=True)
class Nightly:
    dump_units: tuple[str, ...]
    archive_units: tuple[str, ...]
    final_units: tuple[str, ...]
    # Sources whose pending snapshots stop the weekly integrity check.
    drain_sources: tuple[str, ...]
    verify_unit: str
    acquisition_policy: str
    # unit -> (marker path, policy hash); a fresh matching marker skips the unit.
    daily_markers: dict[str, tuple[Path, str]] = field(default_factory=dict)
    # Native successful paired-archive receipt; no separate coordinator marker.
    sinex_completion: Path | None = None


@dataclass(frozen=True)
class BackupConfig:
    state_directory: Path
    lock_path: Path
    cache_directory: Path
    hourly_cache_directory: Path
    passphrase_path: Path
    scratch_directory: Path
    lock_wait_seconds: int
    repositories: dict[str, Repository]
    sources: dict[str, SnapshotSource]
    nightly: Nightly
    # Per-job paths and settings, read by jobs.py, checks.py, maintenance.py
    # and audit.py. Kept as plain JSON: each key is documented where Nix
    # declares it (modules/backup.nix, backupConfig.jobs).
    jobs: dict[str, Any]

    def repository(self, name: str) -> Repository:
        return self.repositories[name]

    def source(self, label: str) -> SnapshotSource:
        return self.sources[label]

    def state_file(self, name: str) -> Path:
        return self.state_directory / name


def _source(label: str, raw: dict[str, Any]) -> SnapshotSource:
    return SnapshotSource(
        label=label,
        repository=raw["repository"],
        snapshot_directory=Path(raw["snapshot_directory"]),
        name_glob=raw["name_glob"],
        bind_path=Path(raw["bind_path"]) if raw["bind_path"] is not None else None,
        archive_prefix=raw["archive_prefix"],
        replacement_suffix=raw["replacement_suffix"],
        coverage=raw["coverage"],
        create_check=raw["create_check"],
        files_cache_suffix=raw["files_cache_suffix"],
        local_snapshots=raw["local_snapshots"],
    )


def parse_config(raw: dict[str, Any]) -> BackupConfig:
    nightly = raw["nightly"]
    return BackupConfig(
        state_directory=Path(raw["state_directory"]),
        lock_path=Path(raw["lock_path"]),
        cache_directory=Path(raw["cache_directory"]),
        hourly_cache_directory=Path(raw["hourly_cache_directory"]),
        passphrase_path=Path(raw["passphrase_path"]),
        scratch_directory=Path(raw["scratch_directory"]),
        lock_wait_seconds=raw["lock_wait_seconds"],
        repositories={
            name: Repository(name, entry["url"], Path(entry["path"]))
            for name, entry in raw["repositories"].items()
        },
        sources={
            label: _source(label, entry) for label, entry in raw["sources"].items()
        },
        nightly=Nightly(
            dump_units=tuple(nightly["dump_units"]),
            archive_units=tuple(nightly["archive_units"]),
            final_units=tuple(nightly["final_units"]),
            drain_sources=tuple(nightly["drain_sources"]),
            verify_unit=nightly["verify_unit"],
            acquisition_policy=nightly["acquisition_policy"],
            sinex_completion=Path(nightly["sinex_completion"])
            if nightly.get("sinex_completion")
            else None,
            daily_markers={
                unit: (Path(marker), policy)
                for unit, (marker, policy) in nightly["daily_markers"].items()
            },
        ),
        jobs=raw["jobs"],
    )


def load_config(path: Path = DEFAULT_PATH) -> BackupConfig:
    return parse_config(json.loads(Path(path).read_text()))
