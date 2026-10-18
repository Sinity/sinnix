"""Verify fresh recovery on the host without replacing working CLI installations."""
# @sinnix-package: skip

import argparse
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path


def runtime_for(wrapper, package_name):
    lines = wrapper.read_text().splitlines()
    for index, line in enumerate(lines):
        if "/bin/sinnix-agent-npm-bootstrap" not in line:
            continue
        parts = []
        while True:
            part = lines[index].strip()
            parts.append(part.removesuffix("\\"))
            index += 1
            if not part.endswith("\\"):
                break
        args = shlex.split(" ".join(parts))
        if len(args) == 6 and args[2] == package_name and args[3] == wrapper.name:
            return args[4]
    raise ValueError(f"No managed recovery runtime for {package_name}")


def has_holder(root):
    prefix = str(root) + os.sep
    mapped_root = os.fsencode(root).replace(b"\n", b"\\012")
    for process in Path("/proc").iterdir():
        if not process.name.isdigit():
            continue
        try:
            if process.stat().st_uid != os.getuid():
                continue
            paths = [process / "cwd", process / "exe", *(process / "fd").iterdir()]
            for path in paths:
                try:
                    target = os.readlink(path)
                    if target == str(root) or target.startswith(prefix):
                        return True
                except FileNotFoundError:
                    pass
            # Mappings keep files in use after descriptors close. Proc escapes
            # newlines in these names; bytes also preserve non-UTF8 paths.
            for line in (process / "maps").read_bytes().split(b"\n"):
                fields = line.split(None, 5)
                if len(fields) == 6 and (
                    fields[5] == mapped_root or fields[5].startswith(mapped_root + b"/")
                ):
                    return True
        except (FileNotFoundError, ProcessLookupError):
            try:
                process.stat()
            except (FileNotFoundError, ProcessLookupError):
                continue
            except OSError:
                pass
            return True  # A present process with missing metadata is uncertain.
        except OSError:
            return True  # An inaccessible same-user process is uncertain.
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    args = parser.parse_args()
    try:
        with open(
            args.inputs,
            encoding="utf-8",
            opener=lambda name, flags: os.open(name, flags | os.O_NONBLOCK),
        ) as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise ValueError("recovery inputs must be a regular file")
            inputs = json.load(handle)
        if (
            not isinstance(inputs, dict)
            or not isinstance(inputs.get("sources"), dict)
            or not inputs["sources"]
        ):
            raise ValueError("recovery inputs require a nonempty sources mapping")
        if (
            not isinstance(inputs.get("helper"), str)
            or not inputs["helper"]
            or not Path(inputs["helper"]).is_file()
        ):
            raise ValueError("recovery helper must name an available regular file")
        for name, source in inputs["sources"].items():
            if (
                not isinstance(name, str)
                or not name.strip()
                or not isinstance(source, str)
                or not source.strip()
            ):
                raise ValueError(
                    "recovery sources require nonempty package names and file paths"
                )
            if not Path(source).is_file():
                raise ValueError(
                    f"recovery source is not an available regular file: {source}"
                )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    wrappers = Path.home() / ".local/bin"
    scratch = Path(tempfile.mkdtemp(prefix="agent-recovery-", dir=os.environ["TMPDIR"]))
    print(f"Recovery verification scratch: {scratch}", flush=True)
    try:
        for name, source in sorted(inputs["sources"].items()):
            with tarfile.open(source) as archive:
                package = json.load(archive.extractfile("package/package.json"))
            if package["name"] != name:
                raise ValueError(
                    f"Recovery archive package differs: expected {name}, got {package['name']}"
                )
            bins = package["bin"]
            if isinstance(bins, str):
                bins = {name.split("/")[-1]: bins}
            candidates = []
            for binary in bins:
                wrapper = wrappers / binary
                if not wrapper.is_file():
                    continue
                try:
                    candidates.append((binary, runtime_for(wrapper, name)))
                except ValueError:
                    continue
            if len(candidates) != 1:
                raise ValueError(
                    f"Expected one managed recovery command for {name}: {candidates}"
                )
            binary, runtime = candidates[0]
            home = scratch / binary
            home.mkdir()
            temp = home / "tmp"
            temp.mkdir()
            env = {
                "HOME": str(home),
                "TMPDIR": str(temp),
                "PATH": runtime + os.pathsep + os.environ["PATH"],
                "npm_config_cache": str(scratch / "npm-cache"),
                "npm_config_update_notifier": "false",
                "npm_config_audit": "false",
                "npm_config_fund": "false",
                "DISABLE_AUTOUPDATER": "1",
                "CI": "true",
            }
            print(f"Recovering {name}@{package['version']}", flush=True)
            subprocess.run(
                ["bash", inputs["helper"], binary, name, binary, runtime, source],
                env=env,
                check=True,
                timeout=240,
            )
            installed = home / ".local/state" / binary / "npm/bin" / binary
            result = subprocess.run(
                [str(installed), "--version"],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    f"{binary} --version exited {result.returncode}: {result.stderr}"
                )
            if not re.search(
                r"(?<![\w.])" + re.escape(package["version"]) + r"(?![\w.])",
                result.stdout,
            ):
                raise ValueError(
                    f"{name} did not report expected version {package['version']}: {result.stdout}{result.stderr}"
                )
            print(f"Verified {name}: {result.stdout.strip()}", flush=True)
    except BaseException:
        print(f"Failed attempt left in caller-managed scratch: {scratch}", flush=True)
        raise
    else:
        summary = f"Verified native recovery versions: {len(inputs['sources'])}"
        if has_holder(scratch):
            print(
                f"{summary}; outputs left in caller-managed scratch because a holder is active or uncertain: {scratch}",
                flush=True,
            )
        else:
            shutil.rmtree(scratch)
            print(f"{summary}; isolated outputs removed", flush=True)


if __name__ == "__main__":
    main()
