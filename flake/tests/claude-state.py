import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("claude_state", sys.argv.pop(1))
state = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state)


class ClaudeStateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.config = self.home / ".config/claude"
        self.config.mkdir(parents=True)
        self.settings = self.config / "settings.json"
        self.managed = self.home / "managed.json"
        self.managed.write_text('{"hooks": {}}')
        self.seed = self.home / "seed.json"
        self.seed.write_text('{"model": "default"}')
        self.hook = self.home / "retired-hook.sh"

    def run_migration(self):
        state.reconcile(self.home, self.managed, self.seed, self.hook)

    def linked_settings(self, text):
        target = self.home / "private.json"
        target.write_text(text)
        self.settings.symlink_to(target)
        return target

    def test_fresh_and_idempotent(self):
        self.run_migration()
        self.assertEqual(json.loads(self.settings.read_text()), {"model": "default"})
        self.assertEqual(self.settings.stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.home / ".claude").resolve(), self.config)
        inode = self.settings.stat().st_ino
        self.run_migration()
        self.assertEqual(self.settings.stat().st_ino, inode)

    def test_global_config_migrates_without_changing_bytes(self):
        source = self.home / "persisted-global.json"
        original = b'{ "mcpServers": {}, "fixture": "unchanged" }\n'
        source.write_bytes(original)
        state.reconcile(self.home, self.managed, self.seed, self.hook, source)
        target = self.config / ".claude.json"
        self.assertEqual(target.read_bytes(), original)
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        saved = next(self.config.glob(".sinnix-migration-*/.claude.json"))
        self.assertEqual(saved.read_bytes(), original)
        self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
        # The native writer's atomic rename works inside the directory store.
        replacement = self.config / ".native-writer.tmp"
        replacement.write_text('{"fixture": "updated"}')
        os.replace(replacement, target)
        state.reconcile(self.home, self.managed, self.seed, self.hook, source)
        self.assertEqual(json.loads(target.read_text()), {"fixture": "updated"})
        self.assertEqual(saved.read_bytes(), original)

    def test_global_config_invalid_source_is_preserved(self):
        source = self.home / ".claude.json"
        for value in ("broken", "[]"):
            source.write_text(value)
            with self.assertRaises(ValueError):
                self.run_migration()
            self.assertEqual(source.read_text(), value)
            self.assertFalse((self.config / ".claude.json").exists())

    def test_global_config_failed_publication_preserves_source(self):
        source = self.home / ".claude.json"
        source.write_text('{"fixture": "keep"}')
        with patch.object(state.os, "link", side_effect=OSError("synthetic failure")):
            with self.assertRaises(OSError):
                self.run_migration()
        self.assertEqual(source.read_text(), '{"fixture": "keep"}')
        self.assertFalse((self.config / ".claude.json").exists())
        self.assertEqual(list(self.config.glob(".global-config-*")), [])
        self.assertEqual(
            next(self.config.glob(".sinnix-migration-*/.claude.json")).read_bytes(),
            source.read_bytes(),
        )

    def test_global_config_concurrent_writer_is_not_replaced(self):
        source = self.home / ".claude.json"
        source.write_text('{"fixture": "source"}')
        target = self.config / ".claude.json"

        def native_writer(temporary, destination):
            target.write_text('{"fixture": "native writer"}')
            raise FileExistsError("native writer won")

        with patch.object(state.os, "link", side_effect=native_writer):
            with self.assertRaises(FileExistsError):
                self.run_migration()
        self.assertEqual(json.loads(target.read_text()), {"fixture": "native writer"})
        self.assertEqual(json.loads(source.read_text()), {"fixture": "source"})

    def test_global_config_changing_source_refuses_publication(self):
        source = self.home / ".claude.json"
        source.write_text('{"fixture": "before"}')
        original_read = Path.read_bytes
        reads = 0

        def changed(path):
            nonlocal reads
            if path == source:
                reads += 1
                if reads == 2:
                    source.write_text('{"fixture": "after"}')
            return original_read(path)

        with patch.object(Path, "read_bytes", changed):
            with self.assertRaisesRegex(ValueError, "changed during migration"):
                self.run_migration()
        self.assertFalse((self.config / ".claude.json").exists())
        self.assertEqual(json.loads(source.read_text()), {"fixture": "after"})
        saved = next(self.config.glob(".sinnix-migration-*/.claude.json"))
        self.assertEqual(json.loads(saved.read_text()), {"fixture": "before"})

    def test_global_config_refuses_an_unexpected_link(self):
        source = self.home / ".claude.json"
        source.write_text('{"fixture": "source"}')
        target = self.config / ".claude.json"
        target.symlink_to(source)
        with self.assertRaisesRegex(ValueError, "unexpected global Claude config link"):
            self.run_migration()
        self.assertTrue(target.is_symlink())

    def test_existing_private_settings_unchanged(self):
        self.settings.write_text('{"hooks": {"private": true}, "model": "mine"}')
        original = self.settings.read_bytes()
        self.run_migration()
        self.assertEqual(self.settings.read_bytes(), original)

    def test_link_migration_preserves_original_and_private_keys(self):
        target = self.linked_settings('{"hooks": {}, "model": "mine"}')
        original = target.read_bytes()
        self.run_migration()
        self.assertFalse(self.settings.is_symlink())
        self.assertEqual(json.loads(self.settings.read_text()), {"model": "mine"})
        self.assertEqual(target.read_bytes(), original)
        backup = next(self.config.glob(".sinnix-migration-*/settings.json"))
        self.assertEqual(backup.read_bytes(), original)
        self.assertEqual(backup.stat().st_mode & 0o777, 0o600)
        self.assertEqual(backup.parent.stat().st_mode & 0o777, 0o700)

    def test_malformed_inputs_preserve_link(self):
        for text in ("broken", "[]"):
            with self.subTest(text=text):
                target = self.linked_settings(text)
                with self.assertRaises(ValueError):
                    self.run_migration()
                self.assertTrue(self.settings.is_symlink())
                self.assertEqual(target.read_text(), text)
                self.settings.unlink()
        self.linked_settings('{"model": "mine"}')
        self.managed.write_text("broken")
        with self.assertRaises(ValueError):
            self.run_migration()
        self.assertTrue(self.settings.is_symlink())

    def test_failed_replacement_preserves_link(self):
        target = self.linked_settings('{"model": "mine"}')
        with patch.object(
            state.os, "replace", side_effect=OSError("synthetic failure")
        ):
            with self.assertRaises(OSError):
                self.run_migration()
        self.assertEqual(self.settings.resolve(), target)
        self.assertEqual(list(self.config.glob(".settings-*")), [])

    def test_legacy_directory_is_not_modified(self):
        legacy = self.home / ".claude"
        legacy.mkdir()
        (legacy / "private").write_text("keep")
        with self.assertRaisesRegex(ValueError, "preserving legacy"):
            self.run_migration()
        self.assertEqual(list(legacy.iterdir()), [legacy / "private"])
        self.assertFalse(self.settings.exists())

    def test_unknown_root_link_is_preserved(self):
        legacy = self.home / ".claude"
        legacy.symlink_to("elsewhere")
        with self.assertRaisesRegex(ValueError, "unexpected Claude root"):
            self.run_migration()
        self.assertEqual(os.readlink(legacy), "elsewhere")

    def test_cleanup_only_recognized_broken_links(self):
        commands = self.config / "commands"
        commands.mkdir()
        stale = commands / "swarm.md"
        stale.symlink_to("../skills/swarm/SKILL.md")
        custom = commands / "persona.md"
        custom.symlink_to("custom-missing-target")
        regular = commands / "history-cleanup.md"
        regular.write_text("keep")
        supported = commands / "agent-orchestration.md"
        supported.symlink_to("../skills/agent-orchestration/SKILL.md")
        supported.parent.parent.joinpath("skills/agent-orchestration").mkdir(
            parents=True
        )
        supported.write_text("supported")
        hook = self.config / "hooks/sessionstart-beads-prime.sh"
        hook.parent.mkdir()
        hook.symlink_to(self.hook)
        self.run_migration()
        self.assertFalse(stale.is_symlink())
        self.assertFalse(hook.is_symlink())
        self.assertEqual(os.readlink(custom), "custom-missing-target")
        self.assertEqual(regular.read_text(), "keep")
        self.assertEqual(supported.read_text(), "supported")
        saved = next(self.config.glob(".sinnix-migration-*/commands/swarm.md"))
        self.assertEqual(os.readlink(saved), "../skills/swarm/SKILL.md")


unittest.main()
