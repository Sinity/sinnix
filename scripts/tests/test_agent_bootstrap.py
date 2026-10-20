# @sinnix-package: skip
"""Native bootstrap preserves recoverable packages and keeps diagnostics out of stdout."""

import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BOOTSTRAP = Path(
    os.environ.get("AGENT_BOOTSTRAP_PATH", REPO / "scripts/sinnix-agent-npm-bootstrap")
)


class NativeBootstrapTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "PYTHONPATH": os.pathsep.join(
                (
                    str(REPO / "pkgs/agentctl"),
                    str(REPO / "pkgs/sinnix-lib"),
                    os.environ.get("PYTHONPATH", ""),
                )
            ),
        }
        package = {
            "name": "fixture-package",
            "version": "1.0.0",
            "bin": {"fixture": "fixture"},
        }
        lock = {
            "name": package["name"],
            "version": package["version"],
            "lockfileVersion": 3,
            "packages": {"": package},
        }
        with tarfile.open(self.root / "locked-package.tgz", "w:gz") as archive:
            for name, payload in {
                "package.json": json.dumps(package),
                "npm-shrinkwrap.json": json.dumps(lock),
            }.items():
                data = payload.encode()
                member = tarfile.TarInfo("package/" + name)
                member.size = len(data)
                member.mode = 0o644
                archive.addfile(member, io.BytesIO(data))

    def executable(self, name, body):
        # An absolute interpreter: a build sandbox has no /usr/bin/env.
        path = self.bin / name
        path.write_text(f"#!{shutil.which('bash')}\nset -eu\n" + body)
        path.chmod(0o755)

    def test_bootstrap_installs_the_declared_tarball_not_a_registry_name(self):
        self.executable(
            "npm",
            'printf "%s\\n" "$@" > "$HOME/npm-args"\n'
            f'printf "#!{shutil.which("bash")}\\nexit 0\\n"'
            ' > "$3/fixture"\n',
        )
        source = self.root / "locked-package.tgz"
        outcome = subprocess.run(
            [
                "bash",
                str(BOOTSTRAP),
                "fixture-agent",
                "fixture-package",
                "fixture",
                str(self.bin),
                str(source),
            ],
            env={**self.env, "HOME": str(self.root)},
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(outcome.returncode, 0, outcome.stderr)
        args = (self.root / "npm-args").read_text().splitlines()
        self.assertEqual(args[:2], ["ci", "--prefix"])
        self.assertEqual(args[3:], ["--global=false", "--omit=dev"])
        installed = (
            self.root
            / ".local/state/fixture-agent/npm/lib/node_modules/fixture-package"
        )
        with tarfile.open(source) as archive:
            self.assertEqual(
                (installed / "npm-shrinkwrap.json").read_bytes(),
                archive.extractfile("package/npm-shrinkwrap.json").read(),
            )

    def test_missing_tarball_does_not_retire_recoverable_package(self):
        state = self.root / ".local/state/fixture-agent"
        retired = state / "npm/lib/node_modules/.fixture-package-AbCd1234"
        retired.mkdir(parents=True)
        (retired / "recoverable.txt").write_bytes(b"retained fixture bytes")
        self.executable("npm", 'touch "$HOME/npm-called"\n')
        outcome = subprocess.run(
            [
                "bash",
                str(BOOTSTRAP),
                "fixture-agent",
                "fixture-package",
                "fixture",
                str(self.bin),
                str(self.root / "absent.tgz"),
            ],
            env={**self.env, "HOME": str(self.root)},
            capture_output=True,
            timeout=10,
        )
        self.assertNotEqual(outcome.returncode, 0)
        self.assertIn(b"locked recovery tarball is unavailable", outcome.stderr)
        self.assertEqual(
            (retired / "recoverable.txt").read_bytes(), b"retained fixture bytes"
        )
        self.assertFalse((self.root / "npm-called").exists())
        self.assertFalse((state / "npm-recovery").exists())

    def test_failed_bootstrap_preserves_retired_package_and_launcher(self):
        state = self.root / ".local/state/fixture-agent"
        retired = state / "npm/lib/node_modules/.fixture-package-AbCd1234"
        retired.mkdir(parents=True)
        (retired / "recoverable.txt").write_bytes(b"retained fixture bytes")
        launcher = state / "npm/bin/.fixture-Qwer1234"
        launcher.parent.mkdir(parents=True)
        launcher.symlink_to("/missing-fixture")
        self.executable("npm", "exit 57\n")
        outcome = subprocess.run(
            [
                "bash",
                str(BOOTSTRAP),
                "fixture-agent",
                "fixture-package",
                "fixture",
                str(self.bin),
                str(self.root / "locked-package.tgz"),
            ],
            env={**self.env, "HOME": str(self.root)},
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(outcome.returncode, 57, outcome.stderr)
        self.assertEqual(outcome.stdout, b"")
        attempts = list((state / "npm-recovery").glob("attempt.*"))
        self.assertEqual(len(attempts), 1)
        saved = attempts[0]
        self.assertEqual(
            (
                saved / "lib/node_modules/.fixture-package-AbCd1234/recoverable.txt"
            ).read_bytes(),
            b"retained fixture bytes",
        )
        self.assertEqual(
            os.readlink(saved / "bin/.fixture-Qwer1234"), "/missing-fixture"
        )
        self.assertFalse(retired.exists())
        self.assertFalse(launcher.is_symlink())
        self.assertEqual(saved.stat().st_mode & 0o777, 0o700)

    def test_bootstrap_diagnostics_never_enter_stdout(self):
        self.executable(
            "npm",
            'printf "changed 9 packages in 7s\\n"\n'
            f'printf "#!{shutil.which("bash")}\\nprintf agent-result\\n"'
            ' > "$3/fixture"\n',
        )
        outcome = subprocess.run(
            [
                "bash",
                str(BOOTSTRAP),
                "fixture-agent",
                "fixture-package",
                "fixture",
                str(self.bin),
                str(self.root / "locked-package.tgz"),
            ],
            env={**self.env, "HOME": str(self.root)},
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(outcome.returncode, 0, outcome.stderr)
        self.assertEqual(outcome.stdout, "")
        self.assertIn("changed 9 packages", outcome.stderr)
        self.assertFalse((self.root / ".local/state/fixture-agent/launch.sh").exists())
        launched = subprocess.run(
            [str(self.root / ".local/state/fixture-agent/npm/bin/fixture")],
            env={**self.env, "HOME": str(self.root)},
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(launched.returncode, 0, launched.stderr)
        self.assertEqual(launched.stdout, "agent-result")


if __name__ == "__main__":
    unittest.main()
