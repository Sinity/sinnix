import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
AUDIO = REPO / "scripts/audio"


class AudioMicTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "calls"
        self.env = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "CALL_LOG": str(self.log),
        }
        self.executable(
            "wpctl",
            'printf "%s\\n" "$*" >> "$CALL_LOG"\n'
            'case "$*" in\n'
            '  "inspect @DEFAULT_AUDIO_SOURCE@") '
            'if [ "${INSPECT_STATUS:-1}" -eq 0 ]; then echo "id 42, type PipeWire:Interface:Node"; else exit 1; fi ;;\n'
            '  "get-volume @DEFAULT_AUDIO_SOURCE@") '
            'if [ "${INSPECT_STATUS:-1}" -eq 0 ]; then echo "Volume: 0.50"; else exit 1; fi ;;\n'
            '  "set-mute @DEFAULT_AUDIO_SOURCE@ toggle") exit 0 ;;\n'
            "esac\n",
        )
        self.executable(
            "jq",
            'printf "jq %s\\n" "$*" >> "$CALL_LOG"\n'
            'printf \'{"state":"unavailable","tooltip":"No active microphone (input unplugged)"}\\n\'\n',
        )
        self.executable("notify-send", 'printf "notify %s\\n" "$*" >> "$CALL_LOG"\n')

    def executable(self, name, body):
        path = self.bin / name
        path.write_text(f"#!{shutil.which('bash')}\nset -eu\n" + body)
        path.chmod(0o755)

    def run_audio(self, command, success):
        return subprocess.run(
            ["bash", str(AUDIO), command],
            env=self.env,
            text=True,
            capture_output=True,
            check=success,
        )

    def test_missing_active_source_status_is_explicit(self):
        result = self.run_audio("mic-status", True)
        state = json.loads(result.stdout)
        self.assertEqual(state["state"], "unavailable")
        self.assertIn("input unplugged", state["tooltip"])
        calls = self.log.read_text()
        self.assertIn(
            'jq -n {text:"󰍭", tooltip:"No active microphone (input unplugged)", class:"unavailable", state:"unavailable"}',
            calls,
        )
        self.assertIn("inspect @DEFAULT_AUDIO_SOURCE@", calls)
        self.assertNotIn("set-mute", calls)

    def test_missing_active_source_toggle_notifies_and_does_not_change_mute(self):
        result = self.run_audio("mic-toggle", False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No active microphone (input unplugged)", result.stderr)
        calls = self.log.read_text()
        self.assertIn("notify Microphone unavailable", calls)
        self.assertNotIn("set-mute", calls)

    def test_active_source_toggle_uses_active_alias(self):
        subprocess.run(
            ["bash", str(AUDIO), "mic-toggle"],
            env={**self.env, "INSPECT_STATUS": "0"},
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("set-mute @DEFAULT_AUDIO_SOURCE@ toggle", self.log.read_text())


if __name__ == "__main__":
    unittest.main()
