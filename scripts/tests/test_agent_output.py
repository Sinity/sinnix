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

    def run_pi(
        self, output, exit_code=0, schema=True, extra_args=(), body=None, stdout=None
    ):
        # The fixture streams from a file: a >16 MiB payload cannot travel in an
        # environment variable (Linux caps one env string at MAX_ARG_STRLEN).
        stream = self.root / "pi-stream"
        stream.write_bytes(output if isinstance(output, bytes) else output.encode())
        self.executable(
            "pi",
            body
            or (
                'printf "%s\\n" "$@" > "$PI_ARGS"\n'
                'cat "$FIXTURE_STREAM"\n'
                'exit "$FIXTURE_EXIT"\n'
            ),
        )
        prompt = self.root / "prompt.md"
        prompt.write_text("Return the fixture result.")
        arguments = [
            "bash",
            str(RUNNER),
            "--agent",
            "pi",
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
        ]
        if schema:
            schema_file = self.root / "schema.json"
            schema_file.write_text('{"type":"object"}')
            arguments += ["--output-schema", str(schema_file)]
        arguments += list(extra_args)
        environment = {
            **self.env,
            "FIXTURE_STREAM": str(stream),
            "FIXTURE_EXIT": str(exit_code),
            "PI_ARGS": str(self.root / "pi-args"),
            "RELAY_FILE": str(stdout) if stdout else "",
        }
        if stdout is None:
            return subprocess.run(
                arguments, env=environment, capture_output=True, timeout=60
            )
        with open(stdout, "wb") as handle:
            return subprocess.run(
                arguments,
                env=environment,
                stdout=handle,
                stderr=subprocess.PIPE,
                timeout=60,
            )

    @staticmethod
    def pi_agent_end(*texts, stop_reason=None):
        messages = []
        for index, body in enumerate(texts):
            message = {
                "role": "assistant",
                "content": [{"type": "text", "text": body}],
                "stopReason": "stop",
            }
            if stop_reason is not None and index == len(texts) - 1:
                message["stopReason"] = stop_reason
                message["errorMessage"] = "fixture upstream failure"
            messages.append(message)
        return {"type": "agent_end", "messages": messages, "willRetry": False}

    @staticmethod
    def pi_line(event):
        # ensure_ascii=False reproduces JSON.stringify, which leaves U+2028,
        # U+2029 and U+0085 raw inside strings.
        return json.dumps(event, ensure_ascii=False) + "\n"

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

    def test_pi_terminal_assistant_json_becomes_structured_result(self):
        stream = self.pi_line(self.pi_agent_end("stale", '{"answer":"fixture"}'))
        outcome = self.run_pi(stream)
        self.assertEqual(outcome.returncode, 0, outcome.stderr)
        self.assertEqual(json.loads(self.result.read_text()), {"answer": "fixture"})
        argv = (self.root / "pi-args").read_text().splitlines()
        self.assertEqual(
            argv[:6], ["--mode", "json", "--model", "fixture-model", "--thinking", "high"]
        )
        self.assertTrue(argv[-1].startswith("@"))

    def test_pi_rejects_non_json_terminal_assistant_message(self):
        outcome = self.run_pi(self.pi_line(self.pi_agent_end("prose")))
        self.assertNotEqual(outcome.returncode, 0)
        self.assertFalse(self.result.exists())

    def test_pi_frames_on_newline_and_never_falls_back_to_a_stale_result(self):
        # Pi frames its event stream on LF alone. str.splitlines() additionally
        # breaks on U+2028/U+2029/U+0085, which JSON.stringify emits raw inside
        # strings: a line-splitting reader shreds this event, discards both
        # halves as unparseable, and silently returns the earlier agent_end.
        # Red when the extractor splits on anything but b"\n".
        fresh = {"answer": "fresh\u2028tail\u2029and\u0085more"}
        stream = self.pi_line(self.pi_agent_end('{"answer":"stale"}'))
        stream += self.pi_line(
            self.pi_agent_end(json.dumps(fresh, ensure_ascii=False))
        )
        self.assertIn("\u2028", stream)
        outcome = self.run_pi(stream)
        self.assertEqual(outcome.returncode, 0, outcome.stderr)
        result = json.loads(self.result.read_text())
        self.assertEqual(result, fresh)
        self.assertNotEqual(result, {"answer": "stale"})

    def test_pi_relays_events_before_the_stream_ends(self):
        # A structured pi worker must not show an empty pueue log for its whole
        # run. The fixture emits one event and refuses to finish until that
        # event has already reached the adapter's stdout, so an extractor that
        # buffers to EOF deadlocks itself. Red when the relay is not incremental.
        relay = self.root / "relayed"
        stream = self.pi_line({"type": "agent_start"})
        stream += self.pi_line(self.pi_agent_end('{"answer":"live"}'))
        body = (
            'printf "%s\\n" "$@" > "$PI_ARGS"\n'
            'head -1 "$FIXTURE_STREAM"\n'
            "for _ in $(seq 60); do\n"
            '  if [ -s "$RELAY_FILE" ]; then break; fi\n'
            "  sleep 0.05\n"
            "done\n"
            '[ -s "$RELAY_FILE" ] || exit 9\n'
            'tail -n +2 "$FIXTURE_STREAM"\n'
        )
        outcome = self.run_pi(stream, body=body, stdout=relay)
        self.assertEqual(outcome.returncode, 0, outcome.stderr)
        self.assertEqual(relay.read_bytes(), stream.encode())
        self.assertEqual(json.loads(self.result.read_text()), {"answer": "live"})

    def test_pi_relays_the_stream_and_accepts_a_transcript_over_16_mib(self):
        # A run that ended well must not fail for the size of its own log, and
        # the relay must reproduce every byte pi wrote. Red when the extractor
        # caps the total stream or buffers it until EOF without relaying.
        filler = self.pi_line({"type": "message_update", "text": "x" * 60_000})
        stream = filler * 300  # ~18 MiB
        stream += self.pi_line(self.pi_agent_end('{"answer":"after-16-mib"}'))
        self.assertGreater(len(stream.encode()), 16 * 1024 * 1024)
        outcome = self.run_pi(stream)
        self.assertEqual(outcome.returncode, 0, outcome.stderr[-400:])
        self.assertEqual(
            json.loads(self.result.read_text()), {"answer": "after-16-mib"}
        )
        self.assertEqual(outcome.stdout, stream.encode())

    def test_pi_refuses_a_single_record_over_16_mib(self):
        # The per-record bound is what keeps an unframed stream from growing
        # without limit in memory; it is separate from the total transcript
        # size. Red when the record bound is removed.
        stream = self.pi_line({"type": "message_update", "text": "x" * (17 << 20)})
        stream += self.pi_line(self.pi_agent_end('{"answer":"unreachable"}'))
        outcome = self.run_pi(stream)
        self.assertNotEqual(outcome.returncode, 0)
        self.assertIn(b"larger than 16 MiB", outcome.stderr)
        self.assertFalse(self.result.exists())

    def test_pi_last_file_holds_assistant_text_not_the_event_stream(self):
        # Without a schema every other backend writes plain assistant output to
        # the last file. Red when the pi branch tees its raw event stream there.
        stream = self.pi_line({"type": "session_header", "id": "fixture-session"})
        stream += self.pi_line(self.pi_agent_end("the final answer"))
        outcome = self.run_pi(stream, schema=False)
        self.assertEqual(outcome.returncode, 0, outcome.stderr)
        self.assertEqual(self.result.read_text(), "the final answer\n")
        self.assertNotIn("agent_end", self.result.read_text())
        self.assertEqual(outcome.stdout, stream.encode())

    def test_pi_refuses_a_terminal_turn_that_errored(self):
        # `pi --mode json` exits 0 even when the final turn errored; only the
        # message carries the outcome. Red when stopReason is ignored and the
        # partial text is shipped as a result.
        stream = self.pi_line(
            self.pi_agent_end('{"answer":"partial"}', stop_reason="error")
        )
        outcome = self.run_pi(stream)
        self.assertNotEqual(outcome.returncode, 0)
        self.assertIn(b"fixture upstream failure", outcome.stderr)
        self.assertFalse(self.result.exists())

    def test_pi_refuses_a_resume_request_it_cannot_honour(self):
        # Pi carries no session reference this adapter can hand back, so a
        # resume request must refuse instead of quietly starting fresh. Red when
        # --resume-session-id is parsed and then ignored.
        outcome = self.run_pi(
            self.pi_line(self.pi_agent_end('{"answer":"fresh-session"}')),
            extra_args=["--resume-session-id", "fixture-session"],
        )
        self.assertEqual(outcome.returncode, 2)
        self.assertIn(b"cannot resume", outcome.stderr)
        self.assertFalse(self.result.exists())
        self.assertFalse((self.root / "pi-args").exists())

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
