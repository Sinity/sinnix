"""Structural and local-reference checks for the skill validator."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = TESTS_DIR.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))
import validate_skill  # noqa: E402


class ValidateSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def write_skill(self, body: str, *, name: str = "example") -> Path:
        skill_dir = self.root / name
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            f"---\nname: {name}\ndescription: Validate a skill package\n---\n{body}",
            encoding="utf-8",
        )
        return skill_file

    def findings(self) -> list[dict[str, str]]:
        return validate_skill.validate(self.root)

    def test_valid_local_reference(self) -> None:
        skill_file = self.write_skill("[Guide](references/guide.md)\n")
        (skill_file.parent / "references").mkdir()
        (skill_file.parent / "references/guide.md").write_text("guide")

        self.assertEqual(self.findings(), [])

    def test_valid_file_fragment_reference(self) -> None:
        skill_file = self.write_skill("[Guide](references/guide.md#install)\n")
        (skill_file.parent / "references").mkdir()
        (skill_file.parent / "references/guide.md").write_text("guide")

        self.assertEqual(self.findings(), [])

    def test_valid_same_file_fragment_reference(self) -> None:
        self.write_skill("[Section](#install)\n")

        self.assertEqual(self.findings(), [])

    def test_missing_file_fragment_reference_keeps_destination(self) -> None:
        self.write_skill("[Guide](references/missing.md#install)\n")

        self.assertEqual(
            self.findings(),
            [
                {
                    "path": str(self.root / "example" / "SKILL.md"),
                    "error": "broken reference: references/missing.md#install",
                }
            ],
        )

    def test_external_url_is_not_a_local_reference(self) -> None:
        self.write_skill("[Guide](https://example.com/guide#install)\n")

        self.assertEqual(self.findings(), [])

    def test_description_and_size_limits_remain_enforced(self) -> None:
        description = " ".join(f"word{index}" for index in range(36))
        skill_file = self.root / "example"
        skill_file.mkdir()
        content = (
            f"---\nname: example\ndescription: {description}\n---\n" + "line\n" * 501
        )
        (skill_file / "SKILL.md").write_text(content, encoding="utf-8")

        errors = [finding["error"] for finding in self.findings()]
        self.assertIn("description has 36 words; limit is 35", errors)
        self.assertIn("SKILL.md exceeds 500 lines", errors)


if __name__ == "__main__":
    unittest.main()
