"""Synthetic real-Borg coverage and rendered drain regression fixtures."""

import argparse
import errno
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

PARSER = argparse.ArgumentParser()
PARSER.add_argument("--verifier", required=True)
PARSER.add_argument("--scripts")
ARGS = PARSER.parse_args()
SPEC = importlib.util.spec_from_file_location("coverage", ARGS.verifier)
COVERAGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COVERAGE)


class CoverageFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(
            prefix="backup-coverage-", dir=os.environ.get("TMPDIR")
        )
        self.root = Path(self.temp.name)
        self.env = os.environ.copy()
        os.environ.update(
            BORG_REPO=str(self.root / "repo"),
            BORG_CACHE_DIR=str(self.root / "cache"),
            BORG_SECURITY_DIR=str(self.root / "security"),
            BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK="yes",
        )
        os.environ.pop("BORG_PASSCOMMAND", None)
        self.borg("init", "--encryption=none")
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "same-name").write_text("old version")
        (self.source / "old-only").write_text("unique historical bytes")
        self.snapshot_uuid = str(uuid.uuid4())

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env)
        self.temp.cleanup()

    def borg(self, *args):
        return subprocess.check_output(["borg", *args], text=True)

    def archive(self, name="snapshot", *options):
        self.borg(
            "create",
            "--comment",
            "sinnix-snapshot-v1:" + self.snapshot_uuid,
            *options,
            "::" + name,
            str(self.source) + "/./",
        )

    def test_exact_versions_and_metadata(self):
        os.link(self.source / "same-name", self.source / "hardlink")
        (self.source / "symlink").symlink_to("same-name")
        self.archive()
        result = COVERAGE.verify(self.source, "snapshot", [])
        self.assertEqual(result["canonical_entries"], 5)
        self.assertEqual(
            len(COVERAGE.archive_identity("snapshot", self.snapshot_uuid)), 64
        )
        with self.assertRaisesRegex(ValueError, "UUID"):
            COVERAGE.archive_identity("snapshot", str(uuid.uuid4()))
        old_stat = (self.source / "same-name").stat()
        (self.source / "same-name").write_text("new version")
        # Keep size and mtime identical: only reading archived/source bytes
        # can detect this change, not a listing or metadata-only comparison.
        os.utime(
            self.source / "same-name", ns=(old_stat.st_atime_ns, old_stat.st_mtime_ns)
        )
        with self.assertRaisesRegex(ValueError, "content mismatch"):
            COVERAGE.verify(self.source, "snapshot", [])

    def test_extended_attributes(self):
        try:
            os.setxattr(
                self.source / "same-name", "user.fixture", b"synthetic\x00value"
            )
        except OSError as error:
            if error.errno == errno.ENOTSUP:
                self.skipTest("fixture filesystem does not support xattrs")
            raise
        self.archive()
        COVERAGE.verify(self.source, "snapshot", [])
        os.setxattr(self.source / "same-name", "user.fixture", b"changed")
        with self.assertRaisesRegex(ValueError, "extended metadata"):
            COVERAGE.verify(self.source, "snapshot", [])

    def test_posix_acls_compare_through_borgs_own_fields(self):
        # Borg keeps POSIX ACLs in its own acl_access/acl_default item fields
        # and emits no xattrs entry for them, so a verifier that compares raw
        # listxattr output against the archived xattrs mismatches forever on
        # any ACL'd path. The Nix build sandbox cannot create an ACL
        # ("setfacl: Operation not supported"), so the comparison is exercised
        # directly rather than through a fixture that would silently skip.
        markers, ordinary = COVERAGE.partition_acl_xattrs(
            ["system.posix_acl_access", "user.fixture", "system.posix_acl_default"]
        )
        self.assertEqual(
            markers, {b"system.posix_acl_access", b"system.posix_acl_default"}
        )
        self.assertEqual(ordinary, ["user.fixture"])
        # An archived access ACL, exactly as borg 1.4.5 dumps it.
        self.assertEqual(
            COVERAGE.archived_acl_markers(
                {
                    "acl_access": "user::rwx\nuser:sinity:rwx:1000\ngroup::r-x",
                    "acl_default": "",
                }
            ),
            {b"system.posix_acl_access"},
        )
        self.assertEqual(
            COVERAGE.archived_acl_markers({"acl_default": "user::rwx"}),
            {b"system.posix_acl_default"},
        )
        # An archive that carries no ACL must not satisfy a source that has
        # one: this is the comparison that keeps the fix from being a skip.
        self.assertEqual(COVERAGE.archived_acl_markers({}), set())

    def test_nested_subvolume_stub_mtime_is_not_coverage(self):
        # Snapshotting a subvolume replaces each nested subvolume with an
        # inode-2 stub whose mtime follows the live subvolume, not the frozen
        # snapshot: sampled seconds apart on this host it advanced with the
        # wall clock, so it can never match what Borg archived. A build sandbox
        # cannot create a btrfs subvolume, so the exemption is exercised
        # directly rather than through a fixture that would have to skip.
        self.assertEqual(
            COVERAGE.metadata_keys_for("ordinary/path", frozenset()),
            ("mode", "uid", "gid", "mtime"),
        )
        stub = ".btrfs/snapshot/persist.20260913T023000+0200"
        self.assertEqual(
            COVERAGE.metadata_keys_for(stub, frozenset({stub})),
            ("mode", "uid", "gid"),
        )
        # Ownership and mode remain compared for a stub: only the mtime is
        # meaningless, and dropping the rest would stop proving anything.
        self.assertIn("mode", COVERAGE.metadata_keys_for(stub, frozenset({stub})))
        self.assertIn("uid", COVERAGE.metadata_keys_for(stub, frozenset({stub})))

    def test_unix_sockets_are_not_coverage(self):
        # Borg dispatches on file type and skips a socket outright, so
        # requiring one to be covered makes the lane permanently unprovable
        # while waiving no bytes. A FIFO in the same directory is archived and
        # exemption: it names one file type, not "anything unusual".
        import socket as socket_module

        sock = socket_module.socket(socket_module.AF_UNIX)
        try:
            sock.bind(str(self.source / "live.sock"))
        except OSError as error:
            sock.close()
            self.skipTest(f"fixture filesystem cannot host a unix socket: {error}")
        try:
            self.archive()
            result = COVERAGE.verify(self.source, "snapshot", [])
            self.assertEqual(result["unarchivable_entries"], ["live.sock"])
            modes = COVERAGE.is_unarchivable_type
            self.assertTrue(modes(os.lstat(self.source / "live.sock").st_mode))
            # Ordinary content is untouched by the exemption: this is a
            # file-type rule, not a blanket waiver for anything unusual.
            self.assertFalse(modes(os.lstat(self.source / "same-name").st_mode))
            self.assertFalse(modes(os.lstat(self.source).st_mode))
        finally:
            sock.close()

    def test_fifos_are_covered_not_rejected(self):
        # Borg archives a FIFO (as metadata alone) but the verifier used to
        # reject the type outright, which made the realm lane unprovable over
        # a single netdata timer FIFO.
        os.mkfifo(self.source / "timer.fifo")
        self.archive()
        before = COVERAGE.verify(self.source, "snapshot", [])
        # It is covered, not exempted: the socket exemption must not have
        # swallowed it, and it counts toward the canonical entry total.
        self.assertNotIn("timer.fifo", before.get("unarchivable_entries", []))
        self.assertEqual(
            before["canonical_entries"],
            sum(1 for _ in self.source.rglob("*")) + 1,
        )
        # Its metadata is still proved: a changed mode must be caught.
        os.chmod(self.source / "timer.fifo", 0o600)
        with self.assertRaisesRegex(ValueError, "mode mismatch"):
            COVERAGE.verify(self.source, "snapshot", [])

    def test_non_utf8_filenames_are_covered(self):
        # Borg's debug JSON cannot hold a non-UTF-8 name as text and encodes it
        # as DEL plus hex. Comparing that raw against fsdecode'd walk keys never
        # matches, which stalled the realm lane on a Facebook export whose name
        # carries a Latin-1 byte.
        raw = os.fsencode(self.source) + b"/Micha\xe9 Basiura_0.json"
        try:
            with open(raw, "wb") as handle:
                handle.write(b"exported bytes")
        except (OSError, UnicodeError) as error:
            self.skipTest(f"fixture filesystem rejects the name: {error}")
        self.archive()
        result = COVERAGE.verify(self.source, "snapshot", [])
        self.assertEqual(
            result["canonical_entries"],
            sum(1 for _ in self.source.rglob("*")) + 1,
        )
        # The decode is exact, not a normalisation that would let a different
        # name pass: the surrogate-escaped form round-trips to the same bytes.
        decoded = COVERAGE.archive_path({"path": "\x7f" + raw.rsplit(b"/", 1)[1].hex()})
        self.assertEqual(os.fsencode(decoded), raw.rsplit(b"/", 1)[1])

    def test_unclassified_exclusion_is_not_coverage(self):
        hidden = self.source / "project" / "build"
        hidden.mkdir(parents=True)
        (hidden / "irreplaceable").write_text("unknown producer material")
        self.archive("glob", "--exclude", "**/build")
        with self.assertRaisesRegex(ValueError, "canonical content missing"):
            COVERAGE.verify(self.source, "glob", [])
        (hidden / ".nobackup").touch()
        self.archive("marker", "--exclude-if-present", ".nobackup")
        with self.assertRaisesRegex(ValueError, "canonical content missing"):
            COVERAGE.verify(self.source, "marker", [])

    def test_declared_scratch_and_nested_stub(self):
        scratch = self.source / "tmp"
        scratch.mkdir()
        (scratch / "derived").write_text("scratch")
        (self.source / "dedicated-subvolume-stub").mkdir()
        self.archive("scratch", "--exclude", str(scratch).lstrip("/"))
        self.assertEqual(
            COVERAGE.verify(self.source, "scratch", ["tmp"])["canonical_entries"], 4
        )

    def test_missing_old_file_and_failed_borg_read(self):
        older = self.root / "older"
        shutil.copytree(self.source, older)
        (self.source / "old-only").unlink()
        self.archive("newer")
        with self.assertRaises(ValueError):
            COVERAGE.verify(older, "newer", [])
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            COVERAGE.verify(older, "absent", [])


class DrainFixture(unittest.TestCase):
    @unittest.skipUnless(
        ARGS.scripts, "rendered Nix scripts supplied by the flake check"
    )
    def test_backlog_restart_collision_and_exclusions(self):
        scripts = json.loads(Path(ARGS.scripts).read_text())
        with tempfile.TemporaryDirectory(
            prefix="backup-drain-", dir=os.environ.get("TMPDIR")
        ) as scratch:
            root = Path(scratch)
            env = os.environ | {
                "TMPDIR": scratch,
                "BORG_SECURITY_DIR": scratch + "/security",
                "BORG_UNKNOWN_UNENCRYPTED_REPO_ACCESS_IS_OK": "yes",
            }
            for path in (
                "mock-bin",
                "logs",
                "bind",
                "repos",
                "state/borg-cache",
                "state/borg-drain",
                "realm-snapshots",
                "persist-snapshots",
                "realm-empty",
            ):
                (root / path).mkdir(parents=True, exist_ok=True)
            (root / "identities.json").write_text("{}")
            mock = """#!PYTHON
import json, os, pathlib, shutil, subprocess, sys
root=pathlib.Path(os.environ['TMPDIR']); command=pathlib.Path(sys.argv[0]).name; args=sys.argv[1:]
with (root/'logs/commands').open('a') as log: log.write(json.dumps([command,*args])+'\\n')
if command=='borg':
    if args[0]=='create' and (root/'fail-create').exists(): sys.exit(2)
    if args[0]=='debug' and (root/'fail-read').exists(): sys.exit(2)
    os.execv(REAL_BORG, [REAL_BORG,*args])
if command=='mountpoint': sys.exit(0 if (root/'logs/mounted').exists() else 1)
if command=='mount':
    source,target=args[-2:]; subprocess.run(['cp','-a',source+'/.',target],check=True); (root/'logs/mounted').touch()
elif command=='umount':
    target=pathlib.Path(args[-1]); shutil.rmtree(target); target.mkdir(); (root/'logs/mounted').unlink(missing_ok=True)
elif command=='btrfs':
    identities=json.loads((root/'identities.json').read_text())
    if args[:2]==['subvolume','show']: print('UUID: '+identities[args[2]])
    elif args[:2]==['property','get']: print('ro=true')
    elif args[:2]==['subvolume','delete']:
        assert args[2] in identities
        if (root/'fail-delete').exists(): sys.exit(1)
        shutil.rmtree(args[2])
    else: sys.exit(64)
""".replace("PYTHON", sys.executable).replace("REAL_BORG", repr(shutil.which("borg")))
            for name in ("mountpoint", "mount", "umount", "btrfs", "borg"):
                (root / "mock-bin" / name).write_text(mock)
                (root / "mock-bin" / name).chmod(0o755)
            (root / "mock-bin/git").write_text(
                "#!/bin/sh\nprintf '%s\\n' synthetic-source-git-head\n"
            )
            (root / "mock-bin/dolt").write_text(
                '#!/bin/sh\nprintf \'%s\\n\' \'{"rows":[{"commit_hash":"synthetic-dolt-commit"}]}\'\n'
            )
            for name in ("git", "dolt"):
                (root / "mock-bin" / name).chmod(0o755)
            env["PATH"] = str(root / "mock-bin") + ":" + env["PATH"]
            for script_name, script in scripts.items():
                (root / (script_name + ".sh")).write_text(script)
            for repo in (
                "borg-realm-v2",
                "borg-persist-v1",
                "borg-sinex-blobs-v1",
                "borg-polylogue-state-v1",
            ):
                subprocess.run(
                    ["borg", "init", "--encryption=none", str(root / "repos" / repo)],
                    env=env,
                    check=True,
                )

            def snapshot(name, files):
                path = root / "realm-snapshots" / name
                path.mkdir()
                for relative, data in files.items():
                    file = path / relative
                    file.parent.mkdir(parents=True, exist_ok=True)
                    file.write_text(data)
                identities = json.loads((root / "identities.json").read_text())
                identities[str(path)] = str(uuid.uuid4())
                (root / "identities.json").write_text(json.dumps(identities))
                return path

            def run(name="realm", ok=True):
                result = subprocess.run(
                    ["bash", str(root / (name + ".sh"))],
                    env=env,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    result.returncode == 0, ok, result.stdout + result.stderr
                )
                return result

            def extract(name, path):
                return subprocess.check_output(
                    [
                        "borg",
                        "extract",
                        "--stdout",
                        str(root / "repos/borg-realm-v2") + "::realm-" + name,
                        path,
                    ],
                    env=env,
                    text=True,
                )

            old = snapshot(
                "realm.20260402T010000+0000",
                {"old-only": "historical", "same-name": "old"},
            )
            new = snapshot(
                "realm.20260402T013000+0000",
                {
                    "same-name": "new",
                    "inbox/download": "canonical",
                    "tmp/scratch": "scratch",
                    "project/sinex/.beads/issues.jsonl": '{"id":"synthetic-bead"}\n',
                    "project/sinex/.beads/dolt/.dolt/HEAD": "synthetic",
                },
            )
            run()
            self.assertFalse(old.exists())
            self.assertFalse(new.exists())
            self.assertEqual(extract(old.name, "old-only"), "historical")
            self.assertEqual(extract(old.name, "same-name"), "old")
            self.assertEqual(extract(new.name, "same-name"), "new")
            commands = [
                json.loads(line)
                for line in (root / "logs/commands").read_text().splitlines()
            ]
            deleted = [
                entry[-1]
                for entry in commands
                if entry[:3] == ["btrfs", "subvolume", "delete"]
            ]
            self.assertEqual(deleted, [str(old), str(new)])

            # Direct-source jobs must keep the evaluated CAS path and exclude
            # mutable Polylogue databases. These use real Borg too.
            for relative, data in {
                "live-cas/objects/ab/cdef": "synthetic CAS",
                "live-polylogue/blob/objects/cd/ef01": "synthetic blob",
                "live-polylogue/source.db": "mutable database",
            }.items():
                file = root / relative
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(data)
            run("sinex")
            run("polylogue")
            for repo, source, excluded in (
                ("borg-sinex-blobs-v1", "live-cas/objects/ab/cdef", None),
                (
                    "borg-polylogue-state-v1",
                    "live-polylogue/blob/objects/cd/ef01",
                    "source.db",
                ),
            ):
                repo_path = str(root / "repos" / repo)
                names = subprocess.check_output(
                    ["borg", "list", "--short", repo_path], env=env, text=True
                ).splitlines()
                self.assertEqual(len(names), 1)
                entries = subprocess.check_output(
                    ["borg", "list", "--short", repo_path + "::" + names[0]],
                    env=env,
                    text=True,
                ).splitlines()
                member = next(path for path in entries if path.endswith(source))
                contents = subprocess.check_output(
                    [
                        "borg",
                        "extract",
                        "--stdout",
                        repo_path + "::" + names[0],
                        member,
                    ],
                    env=env,
                    text=True,
                )
                self.assertEqual(contents, (root / source).read_text())
                if excluded:
                    self.assertFalse(
                        any(path.endswith("/" + excluded) for path in entries)
                    )
            run("beads")
            receipt = next((root / "realm-data").rglob("borg_beads_drill.jsonl"))
            self.assertTrue(json.loads(receipt.read_text())["ok"])

            # A recent success cannot suppress new backlog. A crash after
            # archive completion leaves the UUID-bound archive reusable.
            resumed = snapshot("realm.20260402T020000+0000", {"same-name": "resumable"})
            (root / "fail-delete").touch()
            run(ok=False)
            self.assertTrue(resumed.exists())
            (root / "fail-delete").unlink()
            run()
            self.assertFalse(resumed.exists())
            self.assertEqual(extract(resumed.name, "same-name"), "resumable")

            failure = snapshot(
                "realm.20260402T021500+0000", {"unique": "survives failures"}
            )
            (root / "fail-create").touch()
            run(ok=False)
            self.assertTrue(failure.exists())
            (root / "fail-create").unlink()
            (root / "fail-read").touch()
            run(ok=False)
            self.assertTrue(failure.exists())
            (root / "fail-read").unlink()
            run()
            self.assertFalse(failure.exists())
            self.assertEqual(extract(failure.name, "unique"), "survives failures")

            gap = snapshot(
                "realm.20260402T023000+0000", {"project/build/precious": "canonical"}
            )
            later = snapshot("realm.20260402T030000+0000", {"same-name": "later"})
            result = run(ok=False)
            self.assertIn("canonical content missing", result.stderr)
            self.assertTrue(gap.exists())
            self.assertFalse(later.exists())

            collision = snapshot(
                "realm.20260402T033000+0000", {"same-name": "collision"}
            )
            repo = str(root / "repos/borg-realm-v2")
            subprocess.run(
                [
                    "borg",
                    "create",
                    repo + "::realm-" + collision.name,
                    str(collision) + "/./",
                ],
                env=env,
                check=True,
            )
            result = run(ok=False)
            self.assertIn("UUID", result.stderr)
            self.assertTrue(collision.exists())
            run("persist")
            run("missing")
            for directory in (
                "live-holder/snapshots",
                "live-holder/repo",
                "dead-holder/repos/borg-realm-v2",
            ):
                (root / directory).mkdir(parents=True, exist_ok=True)
            for repo in ("live-holder/repo", "dead-holder/repos/borg-realm-v2"):
                subprocess.run(
                    ["borg", "init", "--encryption=none", str(root / repo)],
                    env=env,
                    check=True,
                )
            with subprocess.Popen(["sleep", "60"]) as holder:
                hostname = os.uname().nodename
                live_lock = root / "live-holder/repo/lock.exclusive"
                dead_lock = root / "dead-holder/repos/borg-realm-v2/lock.exclusive"
                dead = subprocess.Popen(["true"])
                dead.wait()
                for directory, pid in ((live_lock, holder.pid), (dead_lock, dead.pid)):
                    directory.mkdir()
                    (directory / f"{hostname}@281474976710655.{pid}-0").touch()
                    os.utime(directory, (1, 1))
                try:
                    result = run("liveLock")
                    self.assertIn("refusing break-lock", result.stderr)
                    self.assertTrue(live_lock.exists())
                    run("deadLock")
                    self.assertFalse(dead_lock.exists())
                finally:
                    holder.terminate()


if __name__ == "__main__":
    unittest.main(argv=[sys.argv[0]])
