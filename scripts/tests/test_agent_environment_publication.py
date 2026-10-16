"""Failed rendering must preserve the previously verified document."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(sys.argv.pop(1))


class Publication(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="agent-doc-test-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.skills = self.root / "skills"
        self.agents = self.root / "agents"
        self.skills.mkdir()
        self.agents.mkdir()
        self.data = self.root / "data.json"
        self.data.write_text(json.dumps({"profiles": [], "servers": []}))
        self.output = self.root / "document.md"
        self.output.write_bytes(b"previous verified document\n")
        self.output.chmod(0o600)

    def render(self):
        return subprocess.run(["bash", str(SCRIPT), "--data", str(self.data),
                               "--skills-root", str(self.skills), "--agents-root", str(self.agents),
                               "--output", str(self.output)], capture_output=True, timeout=5)

    def preserved(self):
        self.assertEqual(self.output.read_bytes(), b"previous verified document\n")
        self.assertFalse(list(self.root.glob(".agent-environment.*")))

    def test_malformed_data_preserves_previous(self):
        self.data.write_text("broken json")
        self.assertNotEqual(self.render().returncode, 0)
        self.preserved()

    def test_private_output_preserves_previous(self):
        (self.skills / "example.md").write_text("---\nname: fixture\ndescription: /home/fixture/private\n---\n")
        self.assertNotEqual(self.render().returncode, 0)
        self.preserved()

    @unittest.skipIf(os.geteuid() == 0, "requires unprivileged traversal")
    def test_unavailable_inventory_preserves_previous(self):
        (self.skills / "entry.md").write_text("---\nname: fixture\ndescription: fixture\n---\n")
        self.skills.chmod(0)
        try:
            self.assertNotEqual(self.render().returncode, 0)
            self.preserved()
        finally:
            self.skills.chmod(0o700)

    def test_success_replaces_document_and_preserves_mode(self):
        self.assertEqual(self.render().returncode, 0)
        self.assertIn(b"# Sinnix agent environment", self.output.read_bytes())
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
