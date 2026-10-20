"""Bounded maintenance through native owners; historical observations are retained."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

from sinnix_lib.mounts import read_payload_mounts

SCHEMA = "sinnix.fs-maintenance.v1"
UV_CACHE = Path("/realm/state/cache/uv")
VOLUMES = (
    (Path("/realm"), 15, 10),
    (Path("/outer-realm"), 10, 5),
    (Path("/neo-outer-realm"), 10, 5),
)


def capacity(path: Path, target: int, floor: int, *, info) -> dict:
    total = info.f_blocks * info.f_frsize
    available = info.f_bavail * info.f_frsize
    percent = 100 * available / total if total else 0
    return {
        "path": str(path),
        "total_bytes": total,
        "available_bytes": available,
        "available_percent": percent,
        "target_percent": target,
        "defer_below_percent": floor,
        "discretionary_work": "defer"
        if available * 100 < total * floor or not total
        else "admit",
        "target_met": bool(total) and available * 100 >= total * target,
        "forecast": {
            "status": "unavailable",
            "reason": "no comparable growth series; current free space is not a 30-day forecast",
        },
    }


def identity(path: Path) -> dict:
    if not path.is_absolute() or path.resolve(strict=True) != path:
        raise ValueError(f"maintenance root must be an existing physical path: {path}")
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode):
        raise ValueError(f"maintenance root must be a directory: {path}")
    return {"device": info.st_dev, "inode": info.st_ino, "owner": info.st_uid}


def volume_capacity(volume: Path | None = None) -> list[dict]:
    """Observe only mounted payloads, pinning the observed mount before probing."""
    policies = [row for row in VOLUMES if volume is None or row[0] == volume]
    if volume is not None and not policies:
        raise ValueError("unknown managed volume")
    try:
        mounted = read_payload_mounts()
    except (OSError, ValueError) as error:
        return [
            {"path": str(path), "status": "unavailable", "reason": str(error)}
            for path, _, _ in policies
        ]
    volumes = []
    for path, target, floor in policies:
        if path not in mounted:
            volumes.append({"path": str(path), "status": "not_mounted"})
            continue
        try:
            # O_PATH does not trigger the final automount. A concurrent unmount
            # or replacement cannot redirect the later fstatvfs to a payload
            # other than the mount observed above.
            fd = os.open(path, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC)
            try:
                fields = Path(f"/proc/self/fdinfo/{fd}").read_text().splitlines()
                ids = [
                    int(line.partition(":")[2].strip())
                    for line in fields
                    if line.startswith("mnt_id:")
                ]
                if ids != [mounted[path]]:
                    raise ValueError("payload mount changed during observation")
                row = capacity(path, target, floor, info=os.fstatvfs(fd))
                row.update(
                    status="observed", mount_id=ids[0], device=os.fstat(fd).st_dev
                )
                volumes.append(row)
            finally:
                os.close(fd)
        except (OSError, ValueError) as error:
            volumes.append(
                {"path": str(path), "status": "unavailable", "reason": str(error)}
            )
    return volumes


def admission(volume: Path | None = None) -> dict:
    volumes = volume_capacity(volume)
    blocked = [
        row["path"]
        for row in volumes
        if row.get("status") == "unavailable"
        or (
            (volume is not None or row["path"] == str(VOLUMES[0][0]))
            and row.get("status") != "observed"
        )
        or row.get("discretionary_work") == "defer"
    ]
    return {
        "schema": "sinnix.fs-admission.v1",
        "admitted": not blocked,
        "blocked": blocked,
        "volumes": volumes,
        "scope": "discretionary work only; no reservation or running-job interruption",
    }


def plan() -> dict:
    volumes = volume_capacity()
    try:
        root_identity = identity(UV_CACHE)
        action = {
            "owner": "uv",
            "operation": "cache-prune",
            "root": str(UV_CACHE),
            "identity": root_identity,
            "in_use_policy": "native refusal; force is forbidden",
        }
    except (OSError, ValueError) as error:
        action = {"owner": "uv", "status": "unavailable", "reason": str(error)}
    return {
        "schema": SCHEMA,
        "volumes": volumes,
        "actions": [action],
        "retained": [
            {
                "owner": "filesystem-index",
                "reason": "scan JSONL and generation manifests retain historical observations; no age-only retirement",
            },
            {
                "owner": "agentctl",
                "reason": "event history and consumer byte cursors require lossless preservation",
            },
            {
                "owner": "btrfs",
                "reason": "subvolume names and logical bytes do not prove exclusive extents or expendability; native coverage and pin evidence required",
            },
            {
                "owner": "genome",
                "reason": "primary, authored, paid and unique results remain protected; derived naming alone is not recreatability",
            },
        ],
        "accounting": "statvfs reports filesystem availability; it does not attribute shared extents or predict reclaimable bytes",
    }


def apply(document: dict, *, run=subprocess.run) -> dict:
    if document.get("schema") != SCHEMA:
        raise ValueError("unsupported maintenance plan")
    actions = document.get("actions")
    if not isinstance(actions, list) or len(actions) != 1:
        raise ValueError("plan must contain exactly the native cache operation")
    action = actions[0]
    if (
        action.get("owner") != "uv"
        or action.get("operation") != "cache-prune"
        or action.get("root") != str(UV_CACHE)
    ):
        raise ValueError("plan does not select the declared native cache operation")
    if identity(UV_CACHE) != action.get("identity"):
        raise ValueError("cache root identity changed since planning")
    fd = os.open(UV_CACHE, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        pinned = os.fstat(fd)
        if {
            "device": pinned.st_dev,
            "inode": pinned.st_ino,
            "owner": pinned.st_uid,
        } != action["identity"]:
            raise ValueError("cache root changed while opening")
        # Keep the exact reviewed directory open across the native operation.
        # A pathname replacement cannot redirect uv to a different directory.
        before = os.fstatvfs(fd)
        environment = {
            key: value for key, value in os.environ.items() if not key.startswith("UV_")
        }
        completed = run(
            [
                "uv",
                "--no-config",
                "--offline",
                "cache",
                "prune",
                "--cache-dir",
                f"/proc/self/fd/{fd}",
            ],
            pass_fds=(fd,),
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        after = os.fstatvfs(fd)
        return {
            "schema": SCHEMA,
            "owner": "uv",
            "operation": "cache-prune",
            "identity": action["identity"],
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "filesystem_available_delta_bytes": (after.f_bavail * after.f_frsize)
            - (before.f_bavail * before.f_frsize),
            "accounting": "global filesystem delta includes concurrent activity; native output describes cache pruning",
        }
    finally:
        os.close(fd)


def account(roots: list[Path], *, run=subprocess.run) -> dict:
    """Read native extent accounting; never infer exclusive/reclaimable bytes."""
    observed = []
    for root in roots:
        if not root.is_absolute():
            raise ValueError("accounting roots must be absolute")
        resolved = root.resolve(strict=True)
        info = resolved.stat()
        observed.append(
            {
                "requested": str(root),
                "path": str(resolved),
                "device": info.st_dev,
                "inode": info.st_ino,
            }
        )
    reports = []
    for name, arguments in (
        ("compsize", ["--bytes", "--one-file-system"]),
        ("btrfs", ["filesystem", "du", "--raw", "--summarize"]),
    ):
        executable = shutil.which(name)
        if not executable:
            raise ValueError(f"native accounting tool is unavailable: {name}")
        completed = run(
            [
                "sudo",
                "-n",
                executable,
                *arguments,
                "--",
                *[row["path"] for row in observed],
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        reports.append(
            {
                "owner": name,
                "command": [
                    executable,
                    *arguments,
                    "--",
                    *[row["path"] for row in observed],
                ],
                "exit_code": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
        )
    return {
        "schema": "sinnix.fs-accounting.v1",
        "roots": observed,
        "reports": reports,
        "complete": all(report["exit_code"] == 0 for report in reports),
        "scope": "native extent metadata; changing files are not a point-in-time snapshot",
        "accounting": "compsize counts each referenced extent once including compression; extents may be shared outside the requested set. Btrfs du reports sharing. Neither report authorizes deletion or certifies backup coverage.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="sinnix fs maintain", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan")
    admit = commands.add_parser("admission")
    admit.add_argument("--volume", type=Path, choices=[row[0] for row in VOLUMES])
    inspect = commands.add_parser("account")
    inspect.add_argument("roots", type=Path, nargs="+")
    execute = commands.add_parser("apply")
    execute.add_argument("plan", type=Path)
    execute.add_argument("--expected-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "account":
            result = account(args.roots)
        elif args.command == "admission":
            result = admission(args.volume)
            print(json.dumps(result, indent=2))
            return 0 if result["admitted"] else 1
        elif args.command == "plan":
            result = plan()
        else:
            data = args.plan.read_bytes()
            if hashlib.sha256(data).hexdigest() != args.expected_sha256:
                raise ValueError("plan digest changed")
            result = apply(json.loads(data))
        print(json.dumps(result, indent=2))
        return result.get("exit_code", 0) if result.get("complete", True) else 1
    except (OSError, ValueError) as error:
        print(f"maintenance refused: {error}", file=sys.stderr)
        return 2
