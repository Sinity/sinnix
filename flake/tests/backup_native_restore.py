"""Private, bounded native acceptance for one immutable archived file.

The input receipt contains expected archive identity and a complete file digest.
Only digests and diagnostics reach job output; restored bytes stay in memory.
Authentication references and PATH come from the installed archive owner.
"""

import argparse
import hashlib
import json
import os
import pwd
import re
import selectors
import shlex
import stat
import subprocess
import time
from glob import escape as glob_escape
from pathlib import Path, PurePosixPath


def load_target(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("restore input must be a regular private receipt")
        raw = handle.read(64 * 1024 + 1)
        if len(raw) > 64 * 1024:
            raise ValueError("restore receipt exceeds 64 KiB")
    return json.loads(raw)


SCOPES = {
    "realm": "borgbackup-job-realm.service",
    "persist": "borgbackup-job-persist.service",
}


def selected_target(payload, version, scope):
    if scope not in SCOPES:
        raise ValueError("restore scope must be realm or persist")
    archive = payload[version + "_archive"]
    archive_id = payload[version + "_archive_id"]
    snapshot_uuid = payload[version + "_snapshot_uuid"]
    expected_hash = payload[version + "_sha256"]
    size = payload[version + "_bytes"]
    relative = payload["relative_path"]
    path = PurePosixPath(relative)
    if (
        not relative
        or path.is_absolute()
        or ".." in path.parts
        or str(path) != relative
    ):
        raise ValueError("restore target must be one canonical archive-relative path")
    if not re.fullmatch(
        re.escape(f"{scope}-{scope}")
        + r"\.\d{8}T\d{6}[+-]\d{4}(?:-(?:coverage|producer)-v[1-9][0-9]*)?",
        archive,
    ):
        raise ValueError(f"restore target is not a named {scope} snapshot archive")
    if not all(
        re.fullmatch(r"[0-9a-f]{64}", value) for value in (archive_id, expected_hash)
    ):
        raise ValueError("restore requires complete archive and content identities")
    if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", snapshot_uuid):
        raise ValueError("restore requires the snapshot UUID")
    if type(size) is not int or not 0 < size <= 1024 * 1024:
        raise ValueError("native restore probe is limited to one file of at most 1 MiB")
    return archive, archive_id, snapshot_uuid, expected_hash, size, relative


def installed_owner(scope):
    unit = SCOPES[scope]
    start = subprocess.check_output(
        ["systemctl", "show", unit, "-p", "ExecStart", "--value"], text=True
    )
    script = Path(re.search(r"path=(\S+) ;", start)[1]).read_text()
    shell = shlex.split(script.splitlines()[0][2:])[0]
    values = {}
    for name in ("BORG_REPO", "BORG_PASSCOMMAND", "BORG_CACHE_DIR"):
        words = shlex.split(
            re.search(r"^\s*export " + name + r"=(.*)$", script, re.M)[1]
        )
        if len(words) != 1:
            raise ValueError("archive owner has a nonliteral environment binding")
        values[name] = words[0]
    declared = subprocess.check_output(
        ["systemctl", "show", unit, "-p", "Environment", "--value"], text=True
    )
    for item in shlex.split(declared):
        name, separator, value = item.partition("=")
        if separator and name in {
            "PATH",
            "HOME",
            "BORG_BASE_DIR",
            "BORG_CONFIG_DIR",
            "BORG_SECURITY_DIR",
            "BORG_KEYS_DIR",
            "BORG_RELOCATED_REPO_ACCESS_IS_OK",
            "BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK",
        }:
            values[name] = value
    user = (
        subprocess.check_output(
            ["systemctl", "show", unit, "-p", "User", "--value"], text=True
        ).strip()
        or "root"
    )
    values.setdefault("HOME", pwd.getpwnam(user).pw_dir)
    if "PATH" not in values:
        raise ValueError("installed archive owner has no declared PATH")
    if not os.environ.get("TMPDIR"):
        raise ValueError("native restore requires managed job scratch")
    values["TMPDIR"] = os.environ["TMPDIR"]
    # The child receives this only after flock has acquired the owner mutex.
    values["SINNIX_BORG_GLOBAL_LOCK_HELD"] = "1"
    return shell, values


def owner_read(shell, values, argv, seconds, output_limit):
    pipeline = 'cap="$1"; shift; "$@" | head -c "$cap"'
    command = [
        "sudo",
        "-n",
        "timeout",
        "--kill-after=5s",
        str(seconds) + "s",
        "flock",
        "-E",
        "75",
        "-n",
        "/run/lock/sinnix-borg.lock",
        "env",
        *[key + "=" + value for key, value in values.items()],
        shell,
        "-o",
        "pipefail",
        "-c",
        pipeline,
        "restore-proof",
        str(output_limit),
        *argv,
    ]
    process = subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    output = bytearray()
    diagnostic = b""
    with selectors.DefaultSelector() as selector:
        selector.register(process.stdout, selectors.EVENT_READ, "output")
        selector.register(process.stderr, selectors.EVENT_READ, "diagnostic")
        while selector.get_map():
            for key, _ in selector.select():
                block = os.read(key.fileobj.fileno(), 65536)
                if not block:
                    selector.unregister(key.fileobj)
                elif key.data == "output":
                    output.extend(block)
                else:
                    diagnostic = (diagnostic + block)[-8192:]
    status = process.wait()
    if status:
        raise RuntimeError(
            f"archive read exited {status}: {diagnostic.decode(errors='replace')}"
        )
    if len(output) >= output_limit:
        raise ValueError("archive read exceeded its retained output bound")
    return bytes(output)


def verify_target(payload, version, read, scope):
    archive, archive_id, snapshot_uuid, expected_hash, size, relative = selected_target(
        payload, version, scope
    )
    header_command = [
        "borg",
        "list",
        "--json",
        "--format",
        "{comment}",
        "--glob-archives",
        glob_escape(archive),
    ]

    def check_identity():
        headers = json.loads(read(header_command, 30, 1024 * 1024))["archives"]
        matches = [
            item for item in headers if item.get("archive", item.get("name")) == archive
        ]
        if (
            len(matches) != 1
            or matches[0].get("id") != archive_id
            or matches[0].get("comment") != "sinnix-snapshot-v1:" + snapshot_uuid
        ):
            raise ValueError("archive identity changed since the source receipt")

    check_identity()
    restored = read(
        ["borg", "extract", "--stdout", "--", "::" + archive, relative], 300, size + 1
    )
    digest = hashlib.sha256(restored).hexdigest()
    if len(restored) != size or digest != expected_hash:
        raise ValueError("restored file differs from the complete source digest")
    check_identity()
    return {
        "outcome": "ok",
        "scope": scope,
        "archive": archive,
        "archive_id": archive_id,
        "snapshot_uuid": snapshot_uuid,
        "relative_path": relative,
        "bytes": size,
        "sha256": digest,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=tuple(SCOPES), required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--version", choices=("old", "new"), required=True)
    args = parser.parse_args()
    started = time.monotonic()
    try:
        payload = load_target(args.target)
        selected_target(
            payload, args.version, args.scope
        )  # Validate before reading privileged owner state.
        shell, values = installed_owner(args.scope)
        proof = verify_target(
            payload,
            args.version,
            lambda argv, seconds, limit: owner_read(
                shell, values, argv, seconds, limit
            ),
            args.scope,
        )
        status = 0
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        RuntimeError,
        subprocess.SubprocessError,
    ) as error:
        proof = {"outcome": "error", "diagnostic": str(error)}
        status = 1
    proof["elapsed_seconds"] = time.monotonic() - started
    print(json.dumps(proof, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
