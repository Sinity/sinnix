"""`sinnix-backup <command>`: one command per backup unit, plus read-only probes."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from . import audit, checks, drain, jobs, maintenance, nightly
from .borg import BorgError
from .config import DEFAULT_PATH, BackupConfig, load_config

# Each entry: command name, help text, handler(config, args) -> exit status.
UNIT_COMMANDS = {
    "nightly": ("run dumps, snapshots, archives and maintenance in sequence", lambda c, a: nightly.run_nightly(c)),
    "take-snapshots": ("take btrbk snapshots and record genome acquisitions", lambda c, a: jobs.take_snapshots(c)),
    "root-snapshots": ("archive and delete the initrd's root snapshots", lambda c, a: jobs.archive_root_snapshots(c)),
    "sinex-stores": ("archive the retained Sinex stores", lambda c, a: jobs.archive_sinex_stores(c)),
    "polylogue-dumps": ("dump Polylogue's live SQLite databases", lambda c, a: jobs.dump_polylogue_databases(c)),
    "polylogue-state": ("archive Polylogue state, its hooks and the purchased vectors", lambda c, a: jobs.archive_polylogue_state(c)),
    "hourly-persist": ("archive a fresh /persist snapshot", lambda c, a: jobs.archive_hourly_persist(c)),
    "hourly-live": ("archive Polylogue's archive database, Beads and Sinex spools", lambda c, a: jobs.archive_hourly_live(c)),
    "expire-dumps": ("expire local dumps whose archived copy restores", lambda c, a: jobs.expire_local_dumps(c)),
    "check-repositories": ("weekly repository integrity check", lambda c, a: checks.check_repositories(c)),
    "check-beads-restore": ("restore every Beads store from the latest realm archive", lambda c, a: checks.check_beads_restore(c)),
    "audit-realm": ("compare the latest realm archive's metadata and a content sample", lambda c, a: audit.audit_realm(c)),
}


def _print_json(value: object) -> None:
    print(json.dumps(value))


def _freshness(config: BackupConfig, args: argparse.Namespace) -> int:
    source = config.source(args.label)
    epoch, age = audit.freshness(
        source.marker(config.state_directory, "latest-archived"),
        config.jobs["freshness_seconds"],
        int(time.time()),
    )
    print(f"latest_archived_epoch={epoch} age_seconds={age}")
    return 0


def _acquisition_freshness(config: BackupConfig, args: argparse.Namespace) -> int:
    genome = config.jobs["genome"]
    if not audit.producer_succeeded(genome["producer_unit"]):
        raise ValueError("acquisition producer has failed or is unavailable")
    source = config.source("genome")
    _print_json(
        audit.acquisition_freshness(
            Path(genome["acquisition_inventory"]),
            source.name_glob,
            source.marker(config.state_directory, "latest-archived"),
            source.coverage,
            config.jobs["freshness_seconds"],
            genome["source"],
            genome["max_observation_age_seconds"],
        )
    )
    return 0


def _audit_status(config: BackupConfig, args: argparse.Namespace) -> int:
    settings = config.jobs["audit"]
    age = audit.audit_status(
        Path(settings["record"]),
        config.source("realm").coverage,
        settings["status_max_age_seconds"],
        mode="sampled",
    )
    print(f"independent_sampled_audit_age_seconds={age}")
    return 0


def _plan(config: BackupConfig, args: argparse.Namespace) -> int:
    print(json.dumps(drain.plan(config, args.label), indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="sinnix-backup", description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)

    def command(name: str, help_text: str) -> argparse.ArgumentParser:
        sub = commands.add_parser(name, help=help_text)
        sub.add_argument("--config", type=Path, default=DEFAULT_PATH)
        return sub

    drain_command = command("drain", "archive one source's queued snapshots, then delete archived ones")
    drain_command.add_argument("label")
    drain_command.set_defaults(handler=lambda c, a: drain.drain(c, a.label))
    plan_command = command("plan", "print what the drain would archive, read-only")
    plan_command.add_argument("label")
    plan_command.set_defaults(handler=_plan)
    for name, (help_text, handler) in UNIT_COMMANDS.items():
        command(name, help_text).set_defaults(handler=handler)
    maintain_command = command("maintain", "prune and compact the repositories")
    maintain_command.add_argument("--dry-run", action="store_true")
    maintain_command.set_defaults(handler=lambda c, a: maintenance.maintain(c, a.dry_run))
    freshness_command = command("freshness", "probe: the latest archived snapshot is within its budget")
    freshness_command.add_argument("label")
    freshness_command.set_defaults(handler=_freshness)
    command("acquisition-freshness", "probe: genome acquisitions are archived within budget").set_defaults(
        handler=_acquisition_freshness
    )
    command("audit-status", "probe: the realm coverage audit is current").set_defaults(handler=_audit_status)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    config = load_config(args.config)
    # Coverage checks index millions of paths; system units do not inherit
    # the session's TMPDIR, so default to scratch on /realm.
    os.environ.setdefault("TMPDIR", str(config.scratch_directory))
    try:
        return args.handler(config, args)
    except (ValueError, OSError, subprocess.SubprocessError, BorgError) as error:
        print(f"sinnix-backup {args.command}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
