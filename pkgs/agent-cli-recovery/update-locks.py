"""Render flake/data/agent-cli-locks.json from the tarballs pinned in agent-cli-sources.nix.

Each CLI recovered through dependency-source.nix needs a complete npm lock for
the exact publisher tarball. This script is the lock's only writer:

    nix run .#sinnix-agent-cli-locks                     # re-render every lock
    nix run .#sinnix-agent-cli-locks -- --set NAME=VER   # bump a pin, then re-render

`--set` rewrites that package's tarball URL and SRI hash in agent-cli-sources.nix
from the npm registry before locking. Review the resulting diff like any other
dependency change; lock-source.py rejects a lock that does not match its tarball.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

SOURCES = Path("flake/data/agent-cli-sources.nix")
LOCKS = Path("flake/data/agent-cli-locks.json")
# Entries rendered through dependency-source.nix, as opposed to pi-source.nix,
# which keeps the publisher's own shrinkwrap.
ENTRY = re.compile(
    r'(?P<head>"(?P<name>[^"]+)" = import \.\./\.\./pkgs/agent-cli-recovery/dependency-source\.nix \{.*?'
    r'url = ")(?P<url>[^"]+)(?P<mid>";\s*hash = ")(?P<hash>[^"]+)(?P<tail>";)',
    re.S,
)


def registry_dist(name: str, version: str) -> tuple[str, str]:
    out = subprocess.run(
        [
            "npm",
            "view",
            f"{name}@{version}",
            "dist.tarball",
            "dist.integrity",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    dist = json.loads(out)
    return dist["dist.tarball"], dist["dist.integrity"]


def fetch(url: str, integrity: str, destination: Path) -> None:
    algorithm, digest = integrity.split("-", 1)
    if algorithm != "sha512":
        raise SystemExit(f"{url}: expected sha512 integrity, got {algorithm}")
    with urllib.request.urlopen(url) as response:
        data = response.read()
    if base64.b64encode(hashlib.sha512(data).digest()).decode() != digest:
        raise SystemExit(f"{url}: tarball does not match its pinned hash")
    destination.write_bytes(data)


def lock_for(url: str, integrity: str) -> dict:
    with tempfile.TemporaryDirectory() as scratch:
        root = Path(scratch)
        tarball = root / "package.tgz"
        fetch(url, integrity, tarball)
        with tarfile.open(tarball) as archive:
            package = json.load(archive.extractfile("package/package.json"))
        (root / "package.json").write_text(json.dumps(package))
        subprocess.run(
            [
                "npm",
                "install",
                "--package-lock-only",
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
            ],
            cwd=root,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        lock = json.loads((root / "package-lock.json").read_text())
    return {
        key: lock[key]
        for key in ("name", "version", "lockfileVersion", "requires", "packages")
        if key in lock
    }


def pin(name: str, url: str, integrity: str):
    """A substitution that rewrites only `name`'s tarball URL and hash."""

    def replace(m: re.Match[str]) -> str:
        if m.group("name") != name:
            return m.group(0)
        return f"{m.group('head')}{url}{m.group('mid')}{integrity}{m.group('tail')}"

    return replace


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--set", action="append", default=[], metavar="NAME=VERSION")
    args = parser.parse_args()
    if not SOURCES.is_file():
        raise SystemExit("run from the sinnix repository root")

    text = SOURCES.read_text()
    for item in args.set:
        name, _, version = item.rpartition("=")
        if name not in {m.group("name") for m in ENTRY.finditer(text)}:
            raise SystemExit(f"{name} is not a dependency-source entry in {SOURCES}")
        text = ENTRY.sub(pin(name, *registry_dist(name, version)), text)
    SOURCES.write_text(text)

    locks = {
        m.group("name"): lock_for(m.group("url"), m.group("hash"))
        for m in ENTRY.finditer(text)
    }
    LOCKS.write_text(json.dumps(locks, indent=2) + "\n")
    for name, lock in locks.items():
        print(f"{name} {lock['version']}: {len(lock['packages']) - 1} locked packages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
