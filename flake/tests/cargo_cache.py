"""Run cache provisioning and selection with synthetic Git checkouts and Btrfs."""

import fcntl
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

PROVISION, SELECTOR, DIRENV, EVICT = map(Path, sys.argv[1:5])
del sys.argv[1:5]


class CargoCache(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.cache = self.root / "cache"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        (self.bin / "btrfs").write_text(
            f"#!{shutil.which('bash')}\nset -eu\n"
            'if [ "$2" = show ]; then test "${DENY_TREE_SEARCH:-0}" != 1; test -f "$3/.subvolume"; '
            'elif [ "$2" = create ]; then mkdir "$3"; touch "$3/.subvolume"; '
            "else exit 9; fi\n"
        )
        (self.bin / "stat").write_text(
            f"#!{shutil.which('bash')}\nset -eu\n"
            'if [ "$1" = -f ] && [ "$3" = %T ]; then '
            'printf "%s\\n" "${FIXTURE_FILESYSTEM:-btrfs}"; '
            'elif [ "$1" = -c ] && [ "$2" = %i ] && [ -f "$3/.subvolume" ]; then '
            'printf "%s\\n" "${FIXTURE_INODE:-256}"; '
            f'else exec "{shutil.which("stat")}" "$@"; fi\n'
        )
        # Provisioning may change only the new cache root, never its contents.
        (self.bin / "chown").write_text(f"#!{shutil.which('bash')}\nexit 0\n")
        for p in self.bin.iterdir():
            p.chmod(0o755)
        self.env = dict(
            os.environ,
            PATH=f"{self.bin}:{os.environ['PATH']}",
            CARGO_CACHE_ROOT=str(self.cache),
            CARGO_CACHE_USER="fixture",
            SINNIX_CARGO_CACHE_ROOT=str(self.cache),
        )
        self.env.pop("CARGO_TARGET_DIR", None)
        self.env.pop("CARGO_INCREMENTAL", None)
        self.direnv = self.root / "direnvrc"
        self.direnv.write_text(DIRENV.read_text())
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)

    def run_bash(self, script, *, env=None, check=True):
        return subprocess.run(
            ["bash", "-c", script],
            cwd=self.checkout,
            env=env or self.env,
            text=True,
            capture_output=True,
            check=check,
        )

    def provision(self, *, check=True):
        return self.run_bash(f'bash "{PROVISION}"', check=check)

    def select(self, *, env=None, check=True):
        return self.run_bash(f'bash "{SELECTOR}"', env=env, check=check)

    def test_provisioning_is_repeatable_and_refuses_existing_ordinary_paths(self):
        self.cache.mkdir()
        value = self.cache / "retained"
        value.write_bytes(b"must survive")
        self.assertNotEqual(self.provision(check=False).returncode, 0)
        self.assertEqual(value.read_bytes(), b"must survive")
        self.assertFalse((self.cache / ".subvolume").exists())
        value.unlink()
        self.cache.rmdir()
        self.provision()
        self.provision()
        self.assertEqual(self.cache.stat().st_mode & 0o777, 0o700)

    def test_symlink_root_is_refused_by_both_owners(self):
        other = self.root / "other"
        other.mkdir()
        (other / ".subvolume").touch()
        self.cache.symlink_to(other, target_is_directory=True)
        self.assertNotEqual(self.provision(check=False).returncode, 0)
        self.assertNotEqual(self.select(check=False).returncode, 0)
        self.assertEqual(list(other.iterdir()), [other / ".subvolume"])

    def test_unprovisioned_cache_is_not_created_by_the_selector(self):
        self.assertNotEqual(self.select(check=False).returncode, 0)
        self.assertFalse(self.cache.exists())

    def test_checkouts_are_isolated_and_explicit_targets_take_precedence(self):
        self.provision()
        first = Path(self.select().stdout.strip())
        self.assertTrue(first.is_dir())
        # Worktree cleanup retires only a tagged target.
        self.assertTrue(
            (first / "CACHEDIR.TAG")
            .read_text()
            .startswith("Signature: 8a477f597d28d172789f06886806bc55\n")
        )
        self.assertTrue(first.is_relative_to(self.cache))
        self.assertEqual(self.select().stdout.strip(), str(first))
        second = self.root / "second"
        subprocess.run(
            [
                "git",
                "-C",
                str(self.checkout),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "fixture",
                "--allow-empty",
            ],
            check=True,
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.checkout),
                "worktree",
                "add",
                "-q",
                "--detach",
                str(second),
            ],
            check=True,
        )
        output = subprocess.check_output(
            ["bash", str(SELECTOR)], cwd=second, env=self.env, text=True
        ).strip()
        self.assertNotEqual(output, str(first))
        explicit = dict(self.env, CARGO_TARGET_DIR=str(self.root / "leased"))
        self.assertEqual(
            self.select(env=explicit).stdout.strip(), explicit["CARGO_TARGET_DIR"]
        )
        self.assertFalse(Path(explicit["CARGO_TARGET_DIR"]).exists())

    def test_a_new_checkout_is_seeded_from_the_baseline_target(self):
        self.provision()
        # The sandbox filesystem has no reflinks; the copy itself is what
        # matters here.
        (self.bin / "cp").write_text(
            f'#!{shutil.which("bash")}\nargs=()\nfor a in "$@"; do '
            '[ "$a" = --reflink=always ] || args+=("$a"); done\n'
            f'exec "{shutil.which("cp")}" "${{args[@]}}"\n'
        )
        (self.bin / "cp").chmod(0o755)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.checkout),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "commit",
                "-qm",
                "fixture",
                "--allow-empty",
            ],
            check=True,
        )

        def worktree(name):
            path = self.root / name
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(self.checkout),
                    "worktree",
                    "add",
                    "-q",
                    "--detach",
                    str(path),
                ],
                check=True,
            )
            return path

        def select_in(path, **extra):
            return Path(
                subprocess.check_output(
                    ["bash", str(SELECTOR)],
                    cwd=path,
                    env=dict(self.env, **extra),
                    text=True,
                ).strip()
            )

        baseline = worktree("baseline")
        seed = select_in(baseline)
        (seed / "debug" / "deps").mkdir(parents=True)
        (seed / "debug" / "deps" / "libdep.rlib").write_bytes(b"compiled")
        subprocess.run(
            [
                "git",
                "-C",
                str(self.checkout),
                "config",
                "sinnix.baselineCheckout",
                str(baseline),
            ],
            check=True,
        )

        for profile in ("debug", "release", "aarch64-unknown-linux-gnu/debug"):
            (seed / profile / "incremental" / "session").mkdir(parents=True)
            (seed / profile / "incremental" / "session" / "state").write_bytes(b"stale")
        (seed / ".rustc_info.json").write_text("stale probe")
        (seed / "tmp").mkdir()
        (seed / "tmp" / "test-state").write_bytes(b"stale test state")
        build_output = Path("debug/build/dependency/out/incremental")
        (seed / build_output).mkdir(parents=True)
        empty_output = build_output.parent / "empty"
        (seed / empty_output).mkdir(mode=0o750)
        (seed / build_output / "artifact").write_bytes(b"needed build output")
        target = select_in(worktree("lane"))
        for profile in ("debug", "release", "aarch64-unknown-linux-gnu/debug"):
            self.assertFalse((target / profile / "incremental").exists())
        self.assertFalse((target / "tmp").exists())
        self.assertTrue((target / empty_output).is_dir())
        self.assertEqual((target / empty_output).stat().st_mode & 0o777, 0o750)
        self.assertEqual(
            (target / build_output / "artifact").read_bytes(), b"needed build output"
        )
        self.assertFalse((target / ".rustc_info.json").exists())
        self.assertTrue((target / "CACHEDIR.TAG").exists())
        self.assertTrue((target / "debug" / ".cargo-lock").exists())
        self.assertNotEqual(target, seed)
        opted_in = select_in(worktree("incremental-lane"), CARGO_INCREMENTAL="1")
        for profile in ("debug", "release", "aarch64-unknown-linux-gnu/debug"):
            self.assertEqual(
                (opted_in / profile / "incremental/session/state").read_bytes(),
                b"stale",
            )
        self.assertFalse((opted_in / "tmp").exists())
        self.assertFalse((opted_in / ".rustc_info.json").exists())
        self.assertEqual(
            (target / "debug" / "deps" / "libdep.rlib").read_bytes(), b"compiled"
        )
        self.assertEqual(
            sorted(p.name for p in target.parent.iterdir()), ["checkout", "target"]
        )
        # An existing target is never replaced.
        (target / "debug" / "deps" / "libdep.rlib").write_bytes(b"rebuilt")
        self.assertEqual(select_in(self.root / "lane"), target)
        self.assertEqual(
            (target / "debug" / "deps" / "libdep.rlib").read_bytes(), b"rebuilt"
        )

    def test_a_worktree_on_the_same_lock_seeds_before_the_baseline(self):
        import fcntl

        self.provision()
        (self.bin / "cp").write_text(
            f'#!{shutil.which("bash")}\nargs=()\nfor a in "$@"; do '
            '[ "$a" = --reflink=always ] || args+=("$a"); done\n'
            f'exec "{shutil.which("cp")}" "${{args[@]}}"\n'
        )
        (self.bin / "cp").chmod(0o755)
        git = [
            "git",
            "-C",
            str(self.checkout),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
        ]
        (self.checkout / "Cargo.lock").write_text("old resolution\n")
        subprocess.run([*git, "add", "Cargo.lock"], check=True)
        subprocess.run([*git, "commit", "-qm", "old"], check=True)

        def worktree(name):
            path = self.root / name
            subprocess.run(
                [*git, "worktree", "add", "-q", "--detach", str(path)], check=True
            )
            return path

        def select_in(path):
            result = subprocess.run(
                ["timeout", "5s", "bash", str(SELECTOR)],
                cwd=path,
                env=self.env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return Path(result.stdout.strip())

        def warm(path, artifact):
            target = select_in(path)
            (target / "debug" / "deps").mkdir(parents=True, exist_ok=True)
            (target / "debug" / "deps" / artifact).write_bytes(b"compiled")
            return target

        baseline = worktree("baseline")
        warm(baseline, "libold.rlib")
        subprocess.run(
            [*git, "config", "sinnix.baselineCheckout", str(baseline)], check=True
        )
        (self.checkout / "Cargo.lock").write_text("new resolution\n")
        subprocess.run([*git, "commit", "-qam", "new"], check=True)
        warm(worktree("idle-lane"), "libnew.rlib")
        busy = warm(worktree("busy-lane"), "libbusy.rlib")
        os.utime(busy / "debug", (2_000_000_000, 2_000_000_000))

        with (busy / "debug" / ".cargo-lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            target = select_in(worktree("new-lane"))
        # The newest same-lock target was busy, so the next one seeded it.
        self.assertTrue((target / "debug" / "deps" / "libnew.rlib").exists())
        self.assertFalse((target / "debug" / "deps" / "libbusy.rlib").exists())
        self.assertEqual(
            sorted(p.name for p in target.parent.iterdir()), ["checkout", "target"]
        )

        # No worktree shares an edited lock: the baseline seeds it.
        other = worktree("edited-lane")
        (other / "Cargo.lock").write_text("edited resolution\n")
        target = select_in(other)
        self.assertTrue((target / "debug" / "deps" / "libold.rlib").exists())
        self.assertFalse((target / "debug" / "deps" / "libnew.rlib").exists())

    def test_busy_baseline_does_not_block_a_new_target(self):
        import fcntl

        self.cache.mkdir()
        (self.cache / ".subvolume").touch()
        seed = Path(self.select().stdout.strip())
        (seed / "debug" / "deps").mkdir(parents=True)
        (seed / "debug" / "deps" / "active.rlib").write_bytes(b"in progress")
        lane = self.root / "lane"
        subprocess.run(["git", "init", "-q", str(lane)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(lane),
                "config",
                "sinnix.baselineCheckout",
                str(self.checkout),
            ],
            check=True,
        )
        with (seed / "debug" / ".cargo-lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            result = subprocess.run(
                ["timeout", "2s", "bash", str(SELECTOR)],
                cwd=lane,
                env=self.env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            target = Path(result.stdout.strip())
            self.assertNotEqual(target, seed)
            self.assertTrue((target / "CACHEDIR.TAG").exists())
            self.assertFalse((target / "debug" / "deps" / "active.rlib").exists())
            self.assertEqual(
                sorted(p.name for p in target.parent.iterdir()), ["checkout", "target"]
            )
        self.assertEqual(
            (seed / "debug" / "deps" / "active.rlib").read_bytes(), b"in progress"
        )

    def test_selection_needs_no_privileged_tree_search(self):
        self.provision()
        env = dict(self.env, DENY_TREE_SEARCH="1")
        denied = self.run_bash(
            'btrfs subvolume show "$SINNIX_CARGO_CACHE_ROOT"', env=env, check=False
        )
        self.assertNotEqual(denied.returncode, 0)
        self.assertTrue(Path(self.select(env=env).stdout.strip()).is_dir())

    def test_only_a_real_subvolume_root_is_selected(self):
        self.provision()
        for fields in [{"FIXTURE_FILESYSTEM": "tmpfs"}, {"FIXTURE_INODE": "257"}]:
            self.assertNotEqual(
                self.select(env=dict(self.env, **fields), check=False).returncode, 0
            )

    def test_direnv_incremental_default_and_opt_in_with_existing_target(self):
        for cargo in (True, False):
            manifest = self.checkout / "Cargo.toml"
            if cargo:
                manifest.touch()
            else:
                manifest.unlink()
            for explicit in (None, "1"):
                env = dict(self.env, CARGO_TARGET_DIR=str(self.root / "leased"))
                if explicit is not None:
                    env["CARGO_INCREMENTAL"] = explicit
                script = f'''
                    source "{self.direnv}"
                    _sinnix_project_environment_setup
                    printf '%s' "${{CARGO_INCREMENTAL-unset}}"
                '''
                expected = explicit or ("0" if cargo else "unset")
                self.assertEqual(self.run_bash(script, env=env).stdout, expected)

    def test_direnv_routes_cargo_checkouts_and_preserves_shell_environment(self):
        self.provision()
        (self.checkout / "Cargo.toml").touch()
        (self.bin / "sinnix-cargo-target").write_text(
            f'#!{shutil.which("bash")}\nexec bash "{SELECTOR}"\n'
        )
        (self.bin / "sinnix-cargo-target").chmod(0o755)
        # Exercise the real use_flake wrapper before and after a product shell.
        script = f'''
            use_flake() {{
                export DATABASE_URL="postgresql:///fixture"
                export PGHOST="$PWD/socket"
            }}
            source "{self.direnv}"
            use_flake
            printf '%s\\n' "$CARGO_TARGET_DIR" "$DATABASE_URL" "$PGHOST"
        '''
        out = self.run_bash(script).stdout.splitlines()
        self.assertTrue(Path(out[0]).is_relative_to(self.cache))
        self.assertEqual(
            out[1:], ["postgresql:///fixture", str(self.checkout / "socket")]
        )
        explicit = dict(self.env, CARGO_TARGET_DIR=str(self.root / "leased"))
        self.assertEqual(
            self.run_bash(script, env=explicit).stdout.splitlines()[0],
            explicit["CARGO_TARGET_DIR"],
        )

    def test_direnv_leaves_non_cargo_checkouts_alone(self):
        script = f'''
            source "{self.direnv}"
            _sinnix_project_environment_setup
            test -z "$CARGO_TARGET_DIR"
        '''
        self.run_bash(script)
        self.assertFalse(self.cache.exists())

    def test_selection_records_its_checkout_for_eviction(self):
        self.provision()
        target = Path(self.select().stdout.strip())
        marker = target.parent / "checkout"
        self.assertEqual(marker.read_text(), f"{self.checkout.resolve()}\n")

    def make_target(self, checkout, *, idle_hours, marked=True):
        name = hashlib.sha256(str(checkout).encode()).hexdigest()[:32]
        entry = self.cache / str(os.getuid()) / name
        (entry / "target" / "debug" / "deps").mkdir(parents=True)
        (entry / "target" / "debug" / ".cargo-lock").touch()
        if marked:
            (entry / "checkout").write_text(f"{checkout}\n")
        stamp = time.time() - idle_hours * 3600
        for path in [entry, *entry.rglob("*")]:
            os.utime(path, (stamp, stamp))
        return entry

    def evict(self, *, use_percent_per_target=0, max_use_percent=90):
        # Filesystem use is ten points per remaining target, so eviction under
        # pressure can be observed stopping once usage falls to the budget.
        (self.bin / "df").write_text(
            f"#!{shutil.which('bash')}\nset -eu\n"
            f'n=$(find "{self.cache}/{os.getuid()}" -mindepth 1 -maxdepth 1 -name "????????????????????????????????" | wc -l)\n'
            f'printf "Use%%\\n%s%%\\n" "$((n * {use_percent_per_target}))"\n'
        )
        (self.bin / "df").chmod(0o755)
        env = dict(
            self.env,
            SINNIX_CARGO_MAX_IDLE_SECONDS=str(72 * 3600),
            SINNIX_CARGO_MIN_IDLE_SECONDS=str(2 * 3600),
            SINNIX_CARGO_MAX_FILESYSTEM_USE_PERCENT=str(max_use_percent),
        )
        return self.run_bash(f'bash "{EVICT}"', env=env)

    def test_eviction_removes_targets_of_removed_and_long_idle_checkouts(self):
        self.provision()
        live = self.checkout.resolve()
        removed = self.root / "removed"
        kept = self.make_target(live, idle_hours=24)
        orphan = self.make_target(removed, idle_hours=3)
        recent_orphan = self.make_target(self.root / "just-removed", idle_hours=1)
        stale = self.make_target(live / "stale", idle_hours=100, marked=False)
        busy = self.make_target(self.root / "busy", idle_hours=3)
        lock = (busy / "target" / "debug" / ".cargo-lock").open()
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX)
        output = self.evict().stdout
        self.assertTrue(kept.exists())
        self.assertFalse(orphan.exists())
        self.assertTrue(recent_orphan.exists())
        self.assertFalse(stale.exists())
        self.assertTrue(busy.exists())
        self.assertIn("checkout removed", output)
        self.assertEqual(
            [
                p.name
                for p in (self.cache / str(os.getuid())).iterdir()
                if p.name.startswith(".")
            ],
            [],
        )

    def test_pressure_evicts_least_recently_used_idle_targets_first(self):
        self.provision()
        live = self.checkout.resolve()
        oldest = self.make_target(live / "a", idle_hours=50)
        older = self.make_target(live / "b", idle_hours=40)
        newer = self.make_target(live / "c", idle_hours=30)
        active = self.make_target(live / "d", idle_hours=1)
        for path in (oldest, older, newer):
            subprocess.run(
                ["git", "init", "-q", (path / "checkout").read_text().strip()],
                check=True,
            )
        self.evict(use_percent_per_target=10, max_use_percent=20)
        self.assertFalse(oldest.exists())
        self.assertFalse(older.exists())
        self.assertTrue(newer.exists())
        self.assertTrue(active.exists())


if __name__ == "__main__":
    unittest.main()
