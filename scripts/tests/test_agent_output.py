"""Native backend stdout is a result protocol, including on a cold bootstrap."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNNER = Path(
    os.environ.get(
        "AGENT_RUNNER_PATH",
        REPO / "dots/_ai/skills/agent-runtime/scripts/run_agent_prompt.sh",
    )
)
BOOTSTRAP = Path(
    os.environ.get("AGENT_BOOTSTRAP_PATH", REPO / "scripts/sinnix-agent-npm-bootstrap")
)


class NativeOutputTest(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.env = {**os.environ, "PATH": f"{self.bin}:{os.environ['PATH']}"}
        self.result = self.root / "result.json"

    def executable(self, name, body):
        # An absolute interpreter: a build sandbox has no /usr/bin/env.
        path = self.bin / name
        path.write_text(f"#!{shutil.which('bash')}\nset -eu\n" + body)
        path.chmod(0o755)

    def run_claude(self, output, exit_code=0):
        self.executable(
            "claude-full", 'printf "%s" "$FIXTURE_STDOUT"\nexit "$FIXTURE_EXIT"\n'
        )
        prompt = self.root / "prompt.md"
        prompt.write_text("Return the fixture result.")
        schema = self.root / "schema.json"
        schema.write_text('{"type":"object"}')
        return subprocess.run(
            [
                "bash",
                str(RUNNER),
                "--agent",
                "claude",
                "--workdir",
                str(self.root),
                "--prompt-file",
                str(prompt),
                "--last-file",
                str(self.result),
                "--model",
                "fixture-model",
                "--reasoning-effort",
                "high",
                "--output-schema",
                str(schema),
            ],
            env={**self.env, "FIXTURE_STDOUT": output, "FIXTURE_EXIT": str(exit_code)},
            text=True,
            capture_output=True,
            timeout=10,
        )

    def envelope(self, **fields):
        return {
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "structured_output": {"answer": "fixture"},
            **fields,
        }

    def test_successful_envelope_preserves_exact_structured_result(self):
        for payload in (self.envelope(), [{"type": "system"}, self.envelope()]):
            with self.subTest(payload=payload):
                outcome = self.run_claude(json.dumps(payload))
                self.assertEqual(outcome.returncode, 0, outcome.stderr)
                self.assertEqual(
                    json.loads(self.result.read_text()), {"answer": "fixture"}
                )

    def test_error_and_non_envelope_json_cannot_become_success(self):
        for payload in (
            self.envelope(is_error=True),
            self.envelope(subtype="error_max_turns"),
            {"structured_output": {"answer": "fiction"}},
            self.envelope(structured_output=None),
        ):
            with self.subTest(payload=payload):
                outcome = self.run_claude(json.dumps(payload))
                self.assertNotEqual(outcome.returncode, 0)
                self.assertFalse(self.result.exists())

    def test_prefixed_json_is_not_extracted_from_arbitrary_stdout(self):
        outcome = self.run_claude(
            "changed 9 packages in 7s\n" + json.dumps(self.envelope())
        )
        self.assertNotEqual(outcome.returncode, 0)
        self.assertFalse(self.result.exists())

    def test_the_last_successful_envelope_among_several_wins(self):
        """Breaks if a second envelope on stdout (a stream, a retry) loses a
        finished worker's result again."""
        first = self.envelope(structured_output={"answer": "stale"})
        for payload in (
            json.dumps([first, self.envelope()]),
            json.dumps(first) + "\n" + json.dumps(self.envelope()),
            json.dumps(self.envelope(is_error=True)) + json.dumps(self.envelope()),
        ):
            with self.subTest(payload=payload):
                self.result.unlink(missing_ok=True)
                outcome = self.run_claude(payload)
                self.assertEqual(outcome.returncode, 0, outcome.stderr)
                self.assertEqual(
                    json.loads(self.result.read_text()), {"answer": "fixture"}
                )

    def test_empty_retry_does_not_accept_a_previous_result(self):
        self.result.write_text('{"previous":"evidence"}')
        outcome = self.run_claude("")
        self.assertNotEqual(outcome.returncode, 0)
        self.assertEqual(json.loads(self.result.read_text()), {"previous": "evidence"})

    def test_backend_failure_wins_over_a_valid_envelope(self):
        outcome = self.run_claude(json.dumps(self.envelope()), exit_code=42)
        self.assertEqual(outcome.returncode, 42)
        self.assertFalse(self.result.exists())

    def test_bootstrap_diagnostics_never_enter_stdout(self):
        self.executable(
            "npm",
            'printf "changed 9 packages in 7s\\n"\nmkdir -p "$npm_config_prefix/bin"\n'
            f'printf "#!{shutil.which("bash")}\\nprintf agent-result\\n"'
            ' > "$npm_config_prefix/bin/fixture"\nchmod +x "$npm_config_prefix/bin/fixture"\n',
        )
        outcome = subprocess.run(
            [
                "bash",
                str(BOOTSTRAP),
                "fixture-agent",
                "fixture-package",
                "fixture",
                str(self.bin),
            ],
            env={**self.env, "HOME": str(self.root)},
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(outcome.returncode, 0, outcome.stderr)
        self.assertEqual(outcome.stdout, "")
        self.assertIn("changed 9 packages", outcome.stderr)
        self.assertFalse((self.root / ".local/state/fixture-agent/launch.sh").exists())
        launched = subprocess.run(
            [str(self.root / ".local/state/fixture-agent/npm/bin/fixture")],
            env={**self.env, "HOME": str(self.root)},
            text=True,
            capture_output=True,
            timeout=10,
        )
        self.assertEqual(launched.returncode, 0, launched.stderr)
        self.assertEqual(launched.stdout, "agent-result")


if __name__ == "__main__":
    unittest.main()
