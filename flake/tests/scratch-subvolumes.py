"""Real Btrfs migration contract, run as root inside an isolated VM."""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

source = sys.argv[1]
spec = importlib.util.spec_from_file_location("migration", source)
migration = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migration)
run = migration.run
root = Path("/fixture")
root.mkdir()
run("truncate", "-s", "512M", "/btrfs.img")
run("mkfs.btrfs", "-f", "/btrfs.img")
run("mount", "-o", "loop", "/btrfs.img", str(root))

scratch = root / "scratch"
scratch.mkdir(mode=0o750)
(scratch / "nocow").mkdir()
run("chattr", "+C", str(scratch / "nocow"))
(scratch / "nocow" / "file").write_text("plain nocow file")
(scratch / ".hidden").write_bytes(b"original\x00payload")
os.chown(scratch / ".hidden", 1000, 100)
os.setxattr(scratch / ".hidden", "user.fixture", b"xattr")
os.link(scratch / ".hidden", scratch / "hardlink")
(scratch / "symlink").symlink_to(".hidden")
run("btrfs", "subvolume", "create", str(scratch / "cargo"))
run("chattr", "+C", str(scratch / "cargo"))
(scratch / "cargo" / "file").write_text("nocow cache")
run("btrfs", "subvolume", "create", str(scratch / "cargo" / "nested"))
(scratch / "cargo" / "nested" / "file").write_text("nested cache")
run("btrfs", "property", "set", "-ts", str(scratch / "cargo" / "nested"), "ro", "true")
run("cp", "-a", str(scratch) + "/.", "/expected")

original_mtime = scratch.stat().st_mtime_ns
migration.migrate(scratch)
assert scratch.stat().st_mtime_ns == original_mtime
assert migration.subvolume(scratch)
assert migration.subvolume(scratch / "cargo")
assert migration.subvolume(scratch / "cargo" / "nested")
run("diff", "-r", "--no-dereference", "/expected", str(scratch))
assert (scratch.stat().st_mode & 0o777) == 0o750
assert (scratch / ".hidden").stat().st_uid == 1000
assert (scratch / ".hidden").stat().st_gid == 100
assert os.getxattr(scratch / ".hidden", "user.fixture") == b"xattr"
assert (scratch / ".hidden").stat().st_ino == (scratch / "hardlink").stat().st_ino
assert (
    run(
        "btrfs", "property", "get", "-ts", str(scratch / "cargo" / "nested"), "ro"
    ).strip()
    == "ro=true"
)
assert "C" in run("lsattr", "-d", str(scratch / "cargo")).split()[0]
identity = run("btrfs", "subvolume", "show", str(scratch))
migration.migrate(scratch)
assert run("btrfs", "subvolume", "show", str(scratch)) == identity
assert not list(root.glob("*.pre-subvol-*"))
assert not list(root.glob("*.subvol-new"))

# Snapshot exclusion means an empty boundary, not the absence of the directory.
(root / "retained").write_text("canonical")
run("btrfs", "subvolume", "snapshot", "-r", str(root), str(root / "cut"))
assert not list((root / "cut" / "scratch").iterdir())
assert (root / "cut" / "retained").read_text() == "canonical"

# A mandatory reflink failure must never change the original or leave staging.
failed = root / "failed"
failed.mkdir()
(failed / "file").write_text("preserved")
original_run = migration.run


def fail_copy(*args):
    if args[0] == "cp":
        raise subprocess.CalledProcessError(1, args, stderr="injected reflink failure")
    return original_run(*args)


migration.run = fail_copy
try:
    migration.migrate(failed)
    raise AssertionError("copy failure accepted")
except subprocess.CalledProcessError:
    pass
finally:
    migration.run = original_run
assert not migration.subvolume(failed)
assert (failed / "file").read_text() == "preserved"
assert not Path(str(failed) + ".subvol-new").exists()

# Exchange failure must also leave the public original untouched.
original_exchange = migration.exchange


def fail_exchange(*args):
    raise OSError("injected exchange failure")


migration.exchange = fail_exchange
try:
    migration.migrate(failed)
    raise AssertionError("exchange failure accepted")
except OSError:
    pass
finally:
    migration.exchange = original_exchange
assert not migration.subvolume(failed)
assert (failed / "file").read_text() == "preserved"
assert not Path(str(failed) + ".subvol-new").exists()

# Bind sources elsewhere and mounts inside a target both pin the old tree.
bind = root / "bind"
bind.mkdir()
run("mount", "--bind", str(failed), str(bind))
try:
    migration.migrate(failed)
    raise AssertionError("active bind accepted")
except RuntimeError as error:
    assert "active mount" in str(error)
run("umount", str(bind))
(failed / "mounted").mkdir()
run("mount", "-t", "tmpfs", "none", str(failed / "mounted"))
try:
    migration.migrate(failed)
    raise AssertionError("nested mount accepted")
except RuntimeError as error:
    assert "active mount" in str(error)
run("umount", str(failed / "mounted"))

# Ambiguous interrupted preparations are retained for reconciliation.
staging = Path(str(failed) + ".subvol-new")
run("btrfs", "subvolume", "create", str(staging))
try:
    migration.migrate(failed)
    raise AssertionError("retained preparation accepted")
except RuntimeError as error:
    assert "retained migration artifacts" in str(error)
assert (failed / "file").read_text() == "preserved"
assert migration.subvolume(staging)
migration.migrate(root / "absent")
(root / "link").symlink_to(failed)
try:
    migration.migrate(root / "link")
    raise AssertionError("symlink accepted")
except RuntimeError:
    pass
print("scratch subvolume migration contract passed")
