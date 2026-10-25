"""Run cache provisioning and selection with synthetic Git checkouts and Btrfs."""
import os
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile
import unittest

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
            f'#!{shutil.which("bash")}\nset -eu\n'
            'if [ "$2" = show ]; then test "${DENY_TREE_SEARCH:-0}" != 1; test -f "$3/.subvolume"; '
            'elif [ "$2" = create ]; then mkdir "$3"; touch "$3/.subvolume"; '
            'else exit 9; fi\n'
        )
        (self.bin / "stat").write_text(
            f'#!{shutil.which("bash")}\nset -eu\n'
            'if [ "$1" = -f ] && [ "$3" = %T ]; then '
            'printf "%s\\n" "${FIXTURE_FILESYSTEM:-btrfs}"; '
            'elif [ "$1" = -c ] && [ "$2" = %i ] && [ -f "$3/.subvolume" ]; then '
            'printf "%s\\n" "${FIXTURE_INODE:-256}"; '
            f'else exec "{shutil.which("stat")}" "$@"; fi\n'
        )
        # Provisioning may change only the new cache root, never its contents.
        (self.bin / "chown").write_text(f'#!{shutil.which("bash")}\nexit 0\n')
        for p in self.bin.iterdir():
            p.chmod(0o755)
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        CARGO_CACHE_ROOT=str(self.cache), CARGO_CACHE_USER="fixture",
                        SINNIX_CARGO_CACHE_ROOT=str(self.cache))
        self.env.pop("CARGO_TARGET_DIR", None)
        self.direnv = self.root / "direnvrc"
        self.direnv.write_text(DIRENV.read_text().replace("/var/cache/sinex/", str(self.root / "sinex-cache") + "/"))
        self.checkout = self.root / "checkout"
        self.checkout.mkdir()
        subprocess.run(["git", "init", "-q", str(self.checkout)], check=True)

    def run_bash(self, script, *, env=None, check=True):
        return subprocess.run(["bash", "-c", script], cwd=self.checkout,
                              env=env or self.env, text=True, capture_output=True,
                              check=check)

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
        self.assertTrue((first / "CACHEDIR.TAG").read_text().startswith(
            "Signature: 8a477f597d28d172789f06886806bc55\n"))
        self.assertTrue(first.is_relative_to(self.cache))
        self.assertEqual(self.select().stdout.strip(), str(first))
        second = self.root / "second"
        subprocess.run(["git", "-C", str(self.checkout), "-c", "user.name=Fixture", "-c",
                        "user.email=fixture@example.invalid", "commit", "-qm", "fixture", "--allow-empty"], check=True)
        subprocess.run(["git", "-C", str(self.checkout), "worktree", "add", "-q", "--detach", str(second)], check=True)
        output = subprocess.check_output(["bash", str(SELECTOR)], cwd=second,
                                         env=self.env, text=True).strip()
        self.assertNotEqual(output, str(first))
        explicit = dict(self.env, CARGO_TARGET_DIR=str(self.root / "leased"))
        self.assertEqual(self.select(env=explicit).stdout.strip(), explicit["CARGO_TARGET_DIR"])
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
        subprocess.run(["git", "-C", str(self.checkout), "-c", "user.name=Fixture", "-c",
                        "user.email=fixture@example.invalid", "commit", "-qm", "fixture",
                        "--allow-empty"], check=True)

        def worktree(name):
            path = self.root / name
            subprocess.run(["git", "-C", str(self.checkout), "worktree", "add", "-q",
                            "--detach", str(path)], check=True)
            return path

        def select_in(path):
            return Path(subprocess.check_output(["bash", str(SELECTOR)], cwd=path,
                                                env=self.env, text=True).strip())

        baseline = worktree("baseline")
        seed = select_in(baseline)
        (seed / "debug" / "deps").mkdir(parents=True)
        (seed / "debug" / "deps" / "libdep.rlib").write_bytes(b"compiled")
        subprocess.run(["git", "-C", str(self.checkout), "config", "sinnix.baselineCheckout",
                        str(baseline)], check=True)

        target = select_in(worktree("lane"))
        self.assertNotEqual(target, seed)
        self.assertEqual((target / "debug" / "deps" / "libdep.rlib").read_bytes(), b"compiled")
        self.assertEqual([p.name for p in target.parent.iterdir()], ["target"])
        # An existing target is never replaced.
        (target / "debug" / "deps" / "libdep.rlib").write_bytes(b"rebuilt")
        self.assertEqual(select_in(self.root / "lane"), target)
        self.assertEqual((target / "debug" / "deps" / "libdep.rlib").read_bytes(), b"rebuilt")

    def test_selection_needs_no_privileged_tree_search(self):
        self.provision()
        env = dict(self.env, DENY_TREE_SEARCH="1")
        denied = self.run_bash('btrfs subvolume show "$SINNIX_CARGO_CACHE_ROOT"',
                               env=env, check=False)
        self.assertNotEqual(denied.returncode, 0)
        self.assertTrue(Path(self.select(env=env).stdout.strip()).is_dir())

    def test_only_a_real_subvolume_root_is_selected(self):
        self.provision()
        for fields in [dict(FIXTURE_FILESYSTEM="tmpfs"), dict(FIXTURE_INODE="257")]:
            self.assertNotEqual(self.select(env=dict(self.env, **fields),
                                            check=False).returncode, 0)

    def test_direnv_selects_for_both_projects_and_sinex_keeps_other_owners(self):
        self.provision()
        (self.bin / "sinnix-cargo-target").write_text(f'#!{shutil.which("bash")}\nexec bash "{SELECTOR}"\n')
        (self.bin / "sinnix-cargo-target").chmod(0o755)
        for kind in ["polylogue", "sinex"]:
            script = f'''
                source "{self.direnv}"
                _sinnix_project_kind() {{ echo {kind}; }}
                _sinnix_project_root() {{ pwd; }}
                export SINEX_DEV_CACHE_ROOT="$PWD/old-cache"
                export SINEX_DEV_STATE_DIR="$PWD/test-state"
                export SINEX_STATE_DIR="$PWD/runtime-state"
                export SINEX_TEST_RESULTS_DIR="$PWD/durable-results"
                _sinnix_project_environment_setup
                printf '%s\\n' "$CARGO_TARGET_DIR" "$SINEX_TEST_RESULTS_DIR" "$SINEX_DEV_STATE_DIR"
            '''
            out = self.run_bash(script).stdout.splitlines()
            self.assertTrue(Path(out[0]).is_relative_to(self.cache))
            self.assertEqual(out[1], str(self.checkout / "durable-results"))
            self.assertEqual(out[2], str(self.checkout / "test-state"))
        # Default Sinex cache selection used to overwrite even explicit targets.
        script = f'''
            source "{self.direnv}"
            export CARGO_TARGET_DIR="$PWD/leased-target"
            export SINEX_DEV_CACHE_ROOT="$PWD/.sinex/cache"
            export SINEX_DEV_STATE_DIR="$PWD/test-state"
            export SINEX_STATE_DIR="$PWD/runtime-state"
            _sinnix_setup_sinex_dev_cache "$PWD"
            test "$CARGO_TARGET_DIR" = "$PWD/leased-target"
        '''
        self.run_bash(script)


if __name__ == "__main__":
    unittest.main()
