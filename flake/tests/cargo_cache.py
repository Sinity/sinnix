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
            'if [ "$2" = show ]; then test -f "$3/.subvolume"; '
            'elif [ "$2" = create ]; then mkdir "$3"; touch "$3/.subvolume"; '
            'else exit 9; fi\n'
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
