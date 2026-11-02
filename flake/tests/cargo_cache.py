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

    LOCK = (
        "[[package]]\n"
        'name = "dep"\n'
        'version = "1.0.0"\n'
        'source = "registry+https://github.com/rust-lang/crates.io-index"\n'
        "\n"
        "[[package]]\n"
        'name = "member"\n'
        'version = "0.1.0"\n'
    )

    def lanes(self):
        """A repository whose worktrees select targets; returns helpers."""
        self.provision()
        # The sandbox filesystem has no reflinks; the copy itself is what
        # matters here.
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
        (self.checkout / "Cargo.lock").write_text(self.LOCK)
        subprocess.run([*git, "add", "Cargo.lock"], check=True)
        subprocess.run([*git, "commit", "-qm", "fixture"], check=True)

        def worktree(name):
            path = self.root / name
            subprocess.run(
                [*git, "worktree", "add", "-q", "--detach", str(path)], check=True
            )
            return path

        def select_in(path, **extra):
            result = subprocess.run(
                ["timeout", "10s", "bash", str(SELECTOR)],
                cwd=path,
                env=dict(self.env, **extra),
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            return Path(result.stdout.strip())

        def baseline(path):
            subprocess.run(
                [*git, "config", "sinnix.baselineCheckout", str(path)], check=True
            )

        return worktree, select_in, baseline

    @staticmethod
    def build_unit(target, unit, *, profile="debug", content=b"compiled"):
        """Write one Cargo unit's outputs, as a build does, and return them."""
        name, digest = unit.rsplit("-", 1)
        crate = name.replace("-", "_")
        root = target / profile
        (root / ".fingerprint" / unit).mkdir(parents=True)
        (root / ".fingerprint" / unit / f"lib-{crate}").write_text(digest)
        (root / "deps").mkdir(exist_ok=True)
        outputs = [
            root / "deps" / f"lib{crate}-{digest}.rlib",
            root / "deps" / f"{crate}-{digest}.d",
            root / "deps" / f"{crate}-{digest}.{crate}.0.rcgu.o",
        ]
        for output in outputs:
            output.write_bytes(content)
        os.utime(root / ".fingerprint", None)
        return [p.relative_to(target) for p in outputs]

    def test_a_new_checkout_gets_the_dependency_units_of_warm_targets(self):
        worktree, select_in, baseline = self.lanes()
        master = worktree("master")
        seed = select_in(master)
        baseline(master)
        dep = "dep-0123456789abcdef"
        outputs = self.build_unit(seed, dep)
        cross = self.build_unit(
            seed, "dep-1111111111111111", profile="aarch64-unknown-linux-gnu/debug"
        )
        # A build script's compiled program and its run output live in
        # build/<unit>/; an empty output directory keeps its mode.
        script = seed / "debug" / "build" / "dep-2222222222222222"
        (script / "out").mkdir(parents=True)
        (script / "out" / "generated.rs").write_text("generated")
        (script / "empty").mkdir(mode=0o750)
        (seed / "debug" / ".fingerprint" / "dep-2222222222222222").mkdir()
        # Path packages are fresh by mtime, so another checkout's build of
        # them is never offered; neither is state outside the units.
        member = self.build_unit(seed, "member-3333333333333333")
        (seed / "debug" / "incremental" / "member-x").mkdir(parents=True)
        (seed / "debug" / "libmember.rlib").write_bytes(b"uplifted")
        (seed / ".rustc_info.json").write_text("stale probe")
        (seed / "tmp").mkdir()
        (seed / "tmp" / "test-state").write_bytes(b"stale test state")

        target = select_in(worktree("lane"))
        self.assertNotEqual(target, seed)
        for path in [*outputs, *cross, Path("debug/build/dep-2222222222222222/out/generated.rs")]:
            self.assertEqual((target / path).read_bytes(), (seed / path).read_bytes())
        for unit in (dep, "dep-2222222222222222"):
            self.assertTrue((target / "debug" / ".fingerprint" / unit).is_dir())
        empty = target / "debug" / "build" / "dep-2222222222222222" / "empty"
        self.assertEqual(empty.stat().st_mode & 0o777, 0o750)
        for path in [
            *member,
            Path("debug/.fingerprint/member-3333333333333333"),
            Path("debug/incremental"),
            Path("debug/libmember.rlib"),
            Path(".rustc_info.json"),
            Path("tmp"),
        ]:
            self.assertFalse((target / path).exists(), path)
        self.assertTrue((target / "CACHEDIR.TAG").exists())
        self.assertEqual(
            sorted(p.name for p in target.parent.iterdir()), ["checkout", "target"]
        )

        # A unit the target already has is never replaced.
        (target / outputs[0]).write_bytes(b"rebuilt")
        os.utime(seed / "debug" / ".fingerprint", None)
        self.assertEqual(select_in(self.root / "lane"), target)
        self.assertEqual((target / outputs[0]).read_bytes(), b"rebuilt")

    def test_a_new_generation_reaches_an_existing_target(self):
        worktree, select_in, baseline = self.lanes()
        master = worktree("master")
        seed = select_in(master)
        baseline(master)
        self.build_unit(seed, "dep-0123456789abcdef")
        lane = worktree("lane")
        target = select_in(lane)
        # Master changed its flags: every dependency has a new unit hash, and
        # the baseline has built them. The lane's next selection adds them.
        outputs = self.build_unit(seed, "dep-fedcba9876543210")
        stamp = time.time() + 5
        os.utime(seed / "debug" / ".fingerprint", (stamp, stamp))
        select_in(lane)
        for path in outputs:
            self.assertTrue((target / path).exists(), path)
        # An unchanged source is not read again: a unit removed from the
        # lane stays removed until the source builds another one.
        shutil.rmtree(target / "debug" / ".fingerprint" / "dep-fedcba9876543210")
        select_in(lane)
        self.assertFalse(
            (target / "debug" / ".fingerprint" / "dep-fedcba9876543210").exists()
        )
        self.build_unit(seed, "dep-aaaaaaaaaaaaaaaa")
        os.utime(seed / "debug" / ".fingerprint", (stamp + 5, stamp + 5))
        select_in(lane)
        for unit in ("dep-fedcba9876543210", "dep-aaaaaaaaaaaaaaaa"):
            self.assertTrue((target / "debug" / ".fingerprint" / unit).is_dir())

    def test_recent_worktree_targets_add_units_the_baseline_lacks(self):
        worktree, select_in, baseline = self.lanes()
        master = worktree("master")
        self.build_unit(select_in(master), "dep-0000000000000001")
        baseline(master)
        targets = {name: select_in(worktree(name)) for name in ["old", "a", "b", "c"]}
        for i, name in enumerate(targets):
            self.build_unit(targets[name], f"dep-{i + 2:016x}")
            os.utime(targets[name] / "debug", (1_000_000_000 + i, 1_000_000_000 + i))
        target = select_in(worktree("lane"))
        have = {p.name for p in (target / "debug" / ".fingerprint").iterdir()}
        # The baseline and the three most recently built other targets.
        self.assertEqual(
            have,
            {"dep-0000000000000001", "dep-0000000000000003", "dep-0000000000000004",
             "dep-0000000000000005"},
        )

    def test_a_busy_source_is_skipped_and_merged_once_idle(self):
        worktree, select_in, baseline = self.lanes()
        master = worktree("master")
        seed = select_in(master)
        baseline(master)
        outputs = self.build_unit(seed, "dep-0123456789abcdef")
        lane = worktree("lane")
        with (seed / "debug" / ".cargo-lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            target = select_in(lane)
            self.assertTrue((target / "CACHEDIR.TAG").exists())
            self.assertFalse((target / outputs[0]).exists())
        self.assertEqual(select_in(lane), target)
        self.assertTrue((target / outputs[0]).exists())
        # Nor is a target written while its own build holds it.
        self.build_unit(seed, "dep-fedcba9876543210")
        os.utime(seed / "debug" / ".fingerprint", (time.time() + 5,) * 2)
        with (target / "debug" / ".cargo-lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            select_in(lane)
        self.assertFalse(
            (target / "debug" / ".fingerprint" / "dep-fedcba9876543210").exists()
        )
        select_in(lane)
        self.assertTrue(
            (target / "debug" / ".fingerprint" / "dep-fedcba9876543210").exists()
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
        # A new entry whose target is not yet marked is recent by its own mtime.
        fresh = self.cache / str(os.getuid()) / ("f" * 32)
        (fresh / "target").mkdir(parents=True)
        output = self.evict().stdout
        self.assertTrue(fresh.exists())
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

    def test_eviction_keeps_the_idle_master_baseline_target(self):
        self.provision()
        baseline = self.root / "baseline"
        subprocess.run(["git", "init", "-q", str(baseline)], check=True)
        subprocess.run(
            ["git", "-C", str(baseline), "config", "sinnix.baselineCheckout", str(baseline)],
            check=True,
        )
        seed = self.make_target(baseline, idle_hours=100)
        lane = self.make_target(self.checkout.resolve(), idle_hours=100)
        self.evict()
        self.assertTrue(seed.exists())
        self.assertFalse(lane.exists())
        # Filesystem pressure still removes it.
        self.evict(use_percent_per_target=10, max_use_percent=5)
        self.assertFalse(seed.exists())

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
