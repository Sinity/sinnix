"""Enter a project's nix-develop environment from a cached realization.

    agentctl-devenv --input flake.nix --input flake.lock [--input nix] -- COMMAND...

``nix develop`` copies a dirty worktree into the store before it evaluates
the devShell, which costs seconds on every job run right after an edit. The
realized environment (``nix print-dev-env``) depends only on the files the
devShell evaluation reads, which the project declares as its cache inputs,
and on the working directory, which nix embeds as the build outputs' prefix.
Those, plus the nix version, key the cached script; any change re-evaluates.
The script ends by running the project's shellHook, so per-run setup that
reads other files (a dependency sync, for one) still happens every time. Each
command gets private temporary storage, removed after it exits; stop signals
are forwarded before cleanup. An uncatchable kill still needs the enclosing
job's declared scratch owner for cleanup.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from types import FrameType
from typing import Sequence

from sinnix_lib.atomic import atomic_publish

# A cache entry is ~80 KB; entries for abandoned worktrees are swept after
# this long without use.
STALE_SECONDS = 14 * 24 * 3600


class DevenvError(RuntimeError):
    """The environment could not be realized."""


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(base) / "agentctl" / "devenv"


def _input_files(path: Path, ancestors: frozenset[tuple[int, int]] = frozenset()):
    metadata = path.stat()
    if stat.S_ISREG(metadata.st_mode):
        yield path
    elif stat.S_ISDIR(metadata.st_mode):
        identity = (metadata.st_dev, metadata.st_ino)
        if identity in ancestors:
            raise DevenvError(f"directory cycle in declared input: {path}")
        # scandir propagates access and lookup failures. Path.rglob suppresses
        # them, making inaccessible inputs indistinguishable from empty ones.
        with os.scandir(path) as entries:
            for entry in entries:
                yield from _input_files(path / entry.name, ancestors | {identity})
    else:
        raise DevenvError(f"unsupported declared input type: {path}")


def _digest_path(hasher: "hashlib._Hash", root: Path, relative: str) -> None:
    path = root / relative
    try:
        path.lstat()
    except FileNotFoundError:
        hasher.update(f"absent:{relative}\0".encode())
        return
    for child in sorted(_input_files(path)):
        _digest_file(hasher, root, child)


def _digest_file(hasher: "hashlib._Hash", root: Path, path: Path) -> None:
    hasher.update(f"file:{path.relative_to(root)}\0".encode())
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            hasher.update(chunk)
    hasher.update(b"\0")


def cache_key(workdir: Path, inputs: Sequence[str], nix_version: str) -> str:
    hasher = hashlib.sha256()
    hasher.update(f"workdir:{workdir}\0nix:{nix_version}\0".encode())
    for relative in sorted(set(inputs)):
        _digest_path(hasher, workdir, relative)
    return hasher.hexdigest()


def _nix_version() -> str:
    completed = subprocess.run(
        ["nix", "--version"], capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise DevenvError(f"nix --version failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def realize(workdir: Path, inputs: Sequence[str]) -> Path:
    """Return the cached environment script for ``workdir``, realizing it on a miss."""
    directory = cache_dir()
    key = cache_key(workdir, inputs, _nix_version())
    script = directory / f"{key}.sh"
    if script.is_file():
        os.utime(script)
        return script
    completed = subprocess.run(
        ["nix", "print-dev-env", "--accept-flake-config", str(workdir)],
        cwd=workdir,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0 or not completed.stdout:
        raise DevenvError(
            "nix print-dev-env failed: "
            + completed.stderr.decode(errors="replace").strip()[-2000:]
        )
    directory.mkdir(parents=True, exist_ok=True)
    atomic_publish(script, completed.stdout, fsync=False)
    _sweep(directory)
    return script


def _sweep(directory: Path) -> None:
    cutoff = time.time() - STALE_SECONDS
    for entry in directory.glob("*.sh"):
        try:
            if entry.stat().st_mtime < cutoff:
                entry.unlink()
        except FileNotFoundError:
            continue


def _run_command(script: Path, command: Sequence[str]) -> int:
    """Own the temporary build environment until its command has exited."""
    child: subprocess.Popen[bytes] | None = None
    interrupted: int | None = None

    def forward(signum: int, _frame: FrameType | None) -> None:
        nonlocal interrupted
        interrupted = signum
        if child is not None:
            try:
                child.send_signal(signum)
            except ProcessLookupError:
                pass

    previous = {
        sig: signal.signal(sig, forward)
        for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    }
    try:
        with tempfile.TemporaryDirectory(prefix="agentctl-devenv-") as temporary:
            if interrupted is not None:
                return 128 + interrupted
            environment = dict(os.environ, TMPDIR=temporary)
            child = subprocess.Popen(
                [
                    "bash",
                    "--noprofile",
                    "--norc",
                    "-c",
                    'source "$0"; exec "$@"',
                    str(script),
                    *command,
                ],
                env=environment,
                # Preserve explicit descriptor channels, as the former exec did.
                close_fds=False,
            )
            if interrupted is not None:
                forward(interrupted, None)
            result = child.wait()
            return result if result >= 0 else 128 - result
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main(argv: Sequence[str] | None = None) -> int:
    words = list(sys.argv[1:] if argv is None else argv)
    if "--" not in words:
        print("agentctl-devenv: expected -- COMMAND", file=sys.stderr)
        return 2
    cut = words.index("--")
    options, command = words[:cut], words[cut + 1 :]
    parsed = argparse.ArgumentParser(prog="agentctl-devenv")
    parsed.add_argument("--input", action="append", required=True, dest="inputs")
    arguments = parsed.parse_args(options)
    if not command:
        print("agentctl-devenv: empty command", file=sys.stderr)
        return 2
    workdir = Path.cwd().resolve()
    try:
        script = realize(workdir, arguments.inputs)
    except (DevenvError, OSError) as error:
        print(f"agentctl-devenv: {error}", file=sys.stderr)
        return 1
    return _run_command(script, command)


if __name__ == "__main__":
    raise SystemExit(main())
