"""The native recovery verifier must not certify an empty or partial test as five."""
# @sinnix-package: skip

import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(
    os.environ.get(
        "RECOVERY_VERIFIER", Path(__file__).with_name("verify_agent_recovery.py")
    )
)


class RecoveryVerification(unittest.TestCase):
    def holder_fixture(self):
        loader = SourceFileLoader("recovery_holder_fixture", str(SCRIPT))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        module = importlib.util.module_from_spec(spec)
        loader.exec_module(module)
        proc = self.root / "proc"
        process = proc / "123"
        process.mkdir(parents=True)
        (process / "cwd").symlink_to(self.root)
        (process / "exe").symlink_to(sys.executable)
        (process / "fd").mkdir()
        real_path = module.Path
        module.Path = lambda path: proc if path == "/proc" else real_path(path)
        return module, process

    def test_mappings_preserve_component_and_unusual_path_identity(self):
        module, process = self.holder_fixture()
        for name in ["scratch", "scratch\nline", "scratch-\udcff"]:
            root = self.root / name
            mapped = os.fsencode(root / "payload").replace(b"\n", b"\\012")
            (process / "maps").write_bytes(b"0-1000 r--p 0 00:00 1 " + mapped + b"\n")
            self.assertTrue(module.has_holder(root))
            (process / "maps").write_bytes(
                b"0-1000 r--p 0 00:00 1 "
                + os.fsencode(str(root) + "-other/payload").replace(b"\n", b"\\012")
                + b"\n"
            )
            self.assertFalse(module.has_holder(root))

    def test_unavailable_mapping_inspection_keeps_scratch(self):
        module, process = self.holder_fixture()
        (process / "maps").write_bytes(b"")
        original = Path.read_bytes

        def unavailable(path):
            if path == process / "maps":
                raise PermissionError("fixture maps unavailable")
            return original(path)

        with patch.object(Path, "read_bytes", unavailable):
            self.assertTrue(module.has_holder(self.scratch))

    def test_missing_metadata_is_uncertain_until_process_disappears(self):
        module, process = self.holder_fixture()
        self.assertTrue(module.has_holder(self.scratch))
        shutil.rmtree(process)
        self.assertFalse(module.has_holder(self.scratch))

    @unittest.skipUnless(
        "RECOVERY_INPUTS" in os.environ, "requires the built input manifest"
    )
    def test_producer_pins_the_individual_bootstrap_artifact(self):
        inputs = json.loads(Path(os.environ["RECOVERY_INPUTS"]).read_text())
        self.assertEqual(inputs["helper"], os.environ["RECOVERY_BOOTSTRAP"])
        self.assertTrue(inputs["sources"])

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="recovery-verifier-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        (self.home / ".local/bin").mkdir(parents=True)
        self.scratch = self.root / "scratch"
        self.scratch.mkdir()
        self.helper = self.root / "helper.sh"
        bash = shutil.which("bash")
        self.assertIsNotNone(bash)
        self.helper.write_text(f"""#!{bash}
set -eu
target="$HOME/.local/state/$3/npm/bin/$3"
mkdir -p "$(dirname "$target")"
printf '#!{bash}\nprintf "fixture 1.2.3\\n"\n' > "$target"
chmod +x "$target"
""")
        self.source = self.root / "package.tgz"
        metadata = json.dumps(
            {
                "name": "fixture-agent",
                "version": "1.2.3",
                "bin": {"fixture": "index.js"},
            }
        ).encode()
        with tarfile.open(self.source, "w:gz") as archive:
            member = tarfile.TarInfo("package/package.json")
            member.size = len(metadata)
            archive.addfile(member, io.BytesIO(metadata))
        (self.home / ".local/bin/fixture").write_text(
            "/fixture/bin/sinnix-agent-npm-bootstrap fixture fixture-agent fixture /fixture/runtime /fixture/archive\n"
        )

    def run_verifier(self, manifest, holder=None, optimize=False):
        inputs = self.root / "inputs.json"
        inputs.write_text(json.dumps(manifest))
        interpreter = [sys.executable] + (["-O"] if optimize else [])
        command = [*interpreter, str(SCRIPT), "--inputs", str(inputs)]
        if holder is not None:
            # Control only the holder observation; recovery, version checking
            # and cleanup operate on real isolated files and subprocesses.
            code = """
import importlib.util,sys
from importlib.machinery import SourceFileLoader
loader=SourceFileLoader('recovery_fixture',sys.argv[1])
spec=importlib.util.spec_from_loader(loader.name,loader)
module=importlib.util.module_from_spec(spec);loader.exec_module(module)
held=sys.argv[3]=='true'
module.has_holder=lambda root: held
sys.argv=[sys.argv[1],'--inputs',sys.argv[2]]
module.main()
"""
            command = [
                *interpreter,
                "-c",
                code,
                str(SCRIPT),
                str(inputs),
                str(holder).lower(),
            ]
        return subprocess.run(
            command,
            env={**os.environ, "HOME": str(self.home), "TMPDIR": str(self.scratch)},
            capture_output=True,
            text=True,
            timeout=4,
        )

    def test_empty_and_malformed_manifests_refuse_without_scratch(self):
        for sources in [
            {},
            [],
            None,
            {"fixture-agent": ""},
            {"fixture-agent": str(self.root / "absent")},
            {"": str(self.source)},
        ]:
            with self.subTest(sources=sources):
                result = self.run_verifier(
                    {"helper": str(self.helper), "sources": sources}
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("versions verified", result.stdout)
                self.assertEqual(list(self.scratch.iterdir()), [])

    def test_missing_helper_refuses_without_scratch(self):
        result = self.run_verifier({"sources": {"fixture-agent": str(self.source)}})
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_fifo_manifest_cannot_block(self):
        inputs = self.root / "fifo"
        os.mkfifo(inputs)
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--inputs", str(inputs)],
            env={**os.environ, "HOME": str(self.home), "TMPDIR": str(self.scratch)},
            capture_output=True,
            text=True,
            timeout=2,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("regular file", result.stderr)
        self.assertEqual(list(self.scratch.iterdir()), [])

    def test_one_package_reports_one_verified_version(self):
        for holder in [False, True]:
            with self.subTest(holder=holder):
                result = self.run_verifier(
                    {
                        "helper": str(self.helper),
                        "sources": {"fixture-agent": str(self.source)},
                    },
                    holder=holder,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("Verified native recovery versions: 1", result.stdout)
                self.assertNotIn("five", result.stdout)
                self.assertEqual(len(list(self.scratch.iterdir())), int(holder))

    def test_failed_recovery_is_not_a_success_and_leaves_caller_scratch(self):
        self.helper.write_text("exit 37\n")
        result = self.run_verifier(
            {"helper": str(self.helper), "sources": {"fixture-agent": str(self.source)}}
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Verified native recovery versions:", result.stdout)
        self.assertIn("caller-managed scratch", result.stdout)
        self.assertEqual(len(list(self.scratch.iterdir())), 1)

    def test_optimized_python_still_checks_package_and_version(self):
        original = self.helper.read_text()
        for failure in ["version", "exit", "identity"]:
            with self.subTest(failure=failure):
                self.helper.write_text(original)
                if failure == "version":
                    self.helper.write_text(
                        original.replace("fixture 1.2.3", "fixture 9.8.7")
                    )
                elif failure == "exit":
                    self.helper.write_text(
                        original + '\nprintf "\\nexit 7\\n" >> "$target"\n'
                    )
                else:
                    payload = json.dumps(
                        {
                            "name": "wrong-package",
                            "version": "1.2.3",
                            "bin": {"fixture": "index.js"},
                        }
                    ).encode()
                    with tarfile.open(self.source, "w:gz") as archive:
                        member = tarfile.TarInfo("package/package.json")
                        member.size = len(payload)
                        archive.addfile(member, io.BytesIO(payload))
                result = self.run_verifier(
                    {
                        "helper": str(self.helper),
                        "sources": {"fixture-agent": str(self.source)},
                    },
                    optimize=True,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Verified native recovery versions:", result.stdout)


if __name__ == "__main__":
    unittest.main()
