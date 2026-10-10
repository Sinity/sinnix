"""Verify fresh recovery on the host without replacing working CLI installations."""
# @sinnix-package: skip

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tarfile
import tempfile


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
        except FileNotFoundError:
            pass
        except PermissionError:
            return True  # An inaccessible same-user process is uncertain.
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    args = parser.parse_args()
    inputs = json.loads(args.inputs.read_text())
    wrappers = Path.home() / ".local/bin"
    scratch = Path(tempfile.mkdtemp(prefix="agent-recovery-", dir=os.environ["TMPDIR"]))
    print(f"Recovery verification scratch: {scratch}", flush=True)
    try:
        for name, source in sorted(inputs["sources"].items()):
            with tarfile.open(source) as archive:
                package = json.load(archive.extractfile("package/package.json"))
            assert package["name"] == name
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
                raise ValueError(f"Expected one managed recovery command for {name}: {candidates}")
            binary, runtime = candidates[0]
            home = scratch / binary
            home.mkdir()
            temp = home / "tmp"
            temp.mkdir()
            env = {
                "HOME": str(home), "TMPDIR": str(temp),
                "PATH": runtime + os.pathsep + os.environ["PATH"],
                "npm_config_cache": str(scratch / "npm-cache"),
                "npm_config_update_notifier": "false",
                "npm_config_audit": "false", "npm_config_fund": "false",
                "DISABLE_AUTOUPDATER": "1", "CI": "true",
            }
            print(f"Recovering {name}@{package['version']}", flush=True)
            subprocess.run(
                ["bash", inputs["helper"], binary, name, binary, runtime, source],
                env=env, check=True, timeout=240,
            )
            installed = home / ".local/state" / binary / "npm/bin" / binary
            result = subprocess.run(
                [str(installed), "--version"], env=env,
                capture_output=True, text=True, timeout=30,
            )
            assert result.returncode == 0, result.stderr
            assert re.search(r"(?<![\w.])" + re.escape(package["version"]) + r"(?![\w.])", result.stdout), result.stdout + result.stderr
            print(f"Verified {name}: {result.stdout.strip()}", flush=True)
    except BaseException:
        print(f"Failed attempt retained for diagnosis: {scratch}", flush=True)
        raise
    else:
        if has_holder(scratch):
            print(f"All five versions verified; outputs retained because a holder is active or uncertain: {scratch}", flush=True)
        else:
            shutil.rmtree(scratch)
            print("All five native recovery versions verified; isolated outputs removed", flush=True)


if __name__ == "__main__":
    main()
