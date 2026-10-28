"""Run cache provisioning and selection with synthetic Git checkouts and Btrfs."""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROVISION, SELECTOR, DIRENV = map(Path, sys.argv[1:4])
del sys.argv[1:4]


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
                    ["bash", str(SELECTOR)], cwd=path, env=dict(self.env, **extra), text=True
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
                (opted_in / profile / "incremental/session/state").read_bytes(), b"stale"
            )
        self.assertFalse((opted_in / "tmp").exists())
        self.assertFalse((opted_in / ".rustc_info.json").exists())
        self.assertEqual(
            (target / "debug" / "deps" / "libdep.rlib").read_bytes(), b"compiled"
        )
        self.assertEqual([p.name for p in target.parent.iterdir()], ["target"])
        # An existing target is never replaced.
        (target / "debug" / "deps" / "libdep.rlib").write_bytes(b"rebuilt")
        self.assertEqual(select_in(self.root / "lane"), target)
        self.assertEqual(
            (target / "debug" / "deps" / "libdep.rlib").read_bytes(), b"rebuilt"
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


if __name__ == "__main__":
    unittest.main()
