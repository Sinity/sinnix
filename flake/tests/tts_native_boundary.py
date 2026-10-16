"""Run the retained vendor app's admission tests offline, with no GPU or state mounts."""

import argparse
import signal
import subprocess
import uuid
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--ports", nargs=2, type=int, required=True)
    args = parser.parse_args()
    if "@sha256:" not in args.image:
        parser.error("a digest-pinned, already retained image is required")
    root = Path(__file__).resolve().parents[2] / "pkgs/sinnix-litellm-boundary"
    name = "sinnix-tts-boundary-" + uuid.uuid4().hex

    def interrupted(number, frame):
        raise SystemExit(128 + number)

    for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(number, interrupted)
    command = [
        "sudo",
        "-n",
        "podman",
        "run",
        "--rm",
        "--pull=never",
        "--name",
        name,
        "--network=none",
        "--read-only",
        "--memory=1g",
        "--cpus=1",
        "--entrypoint=python",
        "--env=PYTHONDONTWRITEBYTECODE=1",
    ]
    for source, target in [
        (root / "tts.py", "tts.py"),
        (root / "boundary.py", "sinnix_ai_browser_boundary.py"),
        (root / "tests/verify_tts_image.py", "verify.py"),
    ]:
        command += ["--volume", f"{source}:/run/sinnix-tts/{target}:ro"]
    command += [args.image, "/run/sinnix-tts/verify.py", *map(str, args.ports)]
    try:
        return subprocess.run(command, check=False, timeout=120).returncode
    finally:
        # Only this invocation's exact disposable container is selected.
        subprocess.run(
            ["sudo", "-n", "podman", "rm", "--force", "--ignore", name],
            check=True,
            timeout=20,
            stdout=subprocess.DEVNULL,
        )


if __name__ == "__main__":
    raise SystemExit(main())
