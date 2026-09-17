"""Exercise a gateway's installed wrapper, not the development shell's PATH.

No live services, credentials, projects or queue are accessed. The stdio server
is launched in an empty temporary home; only executable version/help probes and
an in-process pyatspi import run.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

COMMANDS = {
    "bash": "--version", "pueue": "--version", "agentctl-run": "--help",
    "git": "--version", "gh": "--version", "bd": "--version",
    "wt": "--version", "nix": "--version", "systemd-run": "--version",
    "systemctl": "--version",
}


def main(executable: str) -> None:
    executable = str(Path(executable).resolve())
    with tempfile.TemporaryDirectory(prefix="gateway-runtime-path-") as tmp:
        root = Path(tmp)
        config = root / "gateway.json"
        config.write_text(json.dumps({"stateDir": str(root / "state"), "projects": {}}))
        with (root / "stdout").open("wb") as out, (root / "stderr").open("wb") as err:
            proc = subprocess.Popen(
                [executable, "--config", str(config), "--principal", "operator", "serve"],
                env={"HOME": tmp, "PATH": "/no-inherited-tools", "LANG": "C.UTF-8"},
                cwd=tmp, stdin=subprocess.PIPE, stdout=out, stderr=err,
            )
            child_env: dict[str, str] = {}
            child_exe = ""
            wrapped = ""
            try:
                deadline = time.monotonic() + 8.0
                # Observe the final Python interpreter, not the short-lived wrapper.
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise AssertionError((root / "stderr").read_text())
                    proc_root = Path(f"/proc/{proc.pid}")
                    try:
                        exe = proc_root.joinpath("exe").resolve()
                        if "python" in exe.name:
                            fields = proc_root.joinpath("environ").read_bytes().split(b"\0")
                            child_env = {k.decode(): v.decode() for entry in fields if b"=" in entry for k, v in [entry.split(b"=", 1)]}
                            child_exe = str(exe)
                            argv = [part.decode() for part in proc_root.joinpath("cmdline").read_bytes().split(b"\0") if part]
                            wrapped = next((part for part in argv if part.endswith(".sinnix-agent-gateway-wrapped")), "")
                            break
                    except FileNotFoundError:
                        pass
                    time.sleep(0.025)
                assert child_env, "could not observe installed gateway interpreter"
                assert child_env.get("GI_TYPELIB_PATH"), "installed gateway misses GI_TYPELIB_PATH"
                assert wrapped, "could not observe the wrapped gateway interpreter"
                paths = {name: shutil.which(name, path=child_env.get("PATH", "")) for name in COMMANDS}
                missing = [name for name, path in paths.items() if path is None]
                assert not missing, f"installed gateway misses runtime tools: {missing}"
                for name, arg in COMMANDS.items():
                    probe = subprocess.run([paths[name], arg], env=child_env, cwd=tmp,
                                           capture_output=True, text=True, timeout=15)
                    assert probe.returncode == 0, f"{name}: {probe.returncode}: {probe.stderr}"
                site_dirs = re.findall(
                    r"'(/nix/store/[^']+/site-packages)'", Path(wrapped).read_text()
                )
                assert site_dirs, f"wrapped interpreter has no site-packages: {wrapped}"
                atspi_env = dict(child_env)
                atspi_env["PYTHONPATH"] = ":".join(site_dirs)
                atspi = subprocess.run(
                    [child_exe, "-c", "import pyatspi"],
                    env=atspi_env,
                    cwd=tmp,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                assert atspi.returncode == 0, f"pyatspi: {atspi.stderr}"
                print(json.dumps({"result": "pass", "tools": paths, "interpreter": child_exe}, sort_keys=True))
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: gateway-runtime-path.py INSTALLED_GATEWAY")
    main(sys.argv[1])
