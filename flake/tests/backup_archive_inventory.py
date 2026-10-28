"""Read one Borg archive's logical file sizes without restoring file contents."""

import argparse
import json
import subprocess
from collections import defaultdict
from pathlib import PurePosixPath

from backup_native_restore import installed_owner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--archive", required=True)
    args = parser.parse_args()
    if not args.archive or "::" in args.archive or "::" in args.repository:
        parser.error("one explicit repository and archive are required")
    shell, values = installed_owner("realm")
    values["BORG_REPO"] = args.repository
    command = [
        "sudo",
        "-n",
        "flock",
        "-n",
        "-E",
        "75",
        "/run/lock/sinnix-borg.lock",
        "env",
        *[key + "=" + value for key, value in values.items()],
        shell,
        "-c",
        'exec borg list --json-lines -- "::$1"',
        "inventory",
        args.archive,
    ]
    groups = defaultdict(int)
    files = total = entries = 0
    with subprocess.Popen(command, stdout=subprocess.PIPE, text=True) as process:
        try:
            for line in process.stdout:
                entries += 1
                if entries > 5_000_000:
                    raise ValueError(
                        "archive exceeds bounded five-million-entry census"
                    )
                item = json.loads(line)
                if item["type"] != "-":
                    continue
                size = item["size"]
                path = PurePosixPath(item["path"])
                files += 1
                total += size
                for depth in (1, 2, 3, 4):
                    if len(path.parts) >= depth:
                        groups[str(PurePosixPath(*path.parts[:depth]))] += size
            status = process.wait()
            if status:
                raise subprocess.CalledProcessError(status, command)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
    print(
        json.dumps(
            {
                "repository": args.repository,
                "archive": args.archive,
                "method": "regular-file logical sizes from archive metadata; shared chunks are not attributed",
                "files": files,
                "logical_bytes": total,
                "largest_prefixes": sorted(
                    groups.items(), key=lambda pair: pair[1], reverse=True
                )[:80],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
