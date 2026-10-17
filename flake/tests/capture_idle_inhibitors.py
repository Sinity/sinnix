"""Synthetic source failures, meaningful provenance and publication acknowledgement."""

import importlib.machinery
import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import unittest
from unittest.mock import patch

if "UNIT_COMMAND" in os.environ:
    wrapper = shlex.split(os.environ["UNIT_COMMAND"])[0]
    subprocess.run([wrapper, "--help"], check=True, stdout=subprocess.DEVNULL)
    source = re.search(r"exec (/nix/store/[^\s]+)", Path(wrapper).read_text()).group(1)
else:
    source = os.environ["MONITOR_SOURCE"]
loader = importlib.machinery.SourceFileLoader("monitor", source)
spec = importlib.util.spec_from_loader(loader.name, loader)
m = importlib.util.module_from_spec(spec)
loader.exec_module(m)


class Inhibitors(unittest.TestCase):
    def state(self, clients, systemd):
        def query(cmd, expected):
            if cmd[1] == "clients":
                return {"status": "available", "value": clients}
            if cmd[1] == "activewindow":
                return {"status": "available", "value": {"class": "fixture"}}
            return {"status": "available", "value": systemd}

        with patch.object(m, "query", side_effect=query):
            return m.snapshot()

    def test_distinct_provenance(self):
        state = self.state(
            [
                {"address": "1", "class": "media", "inhibitingIdle": True},
                {"address": "2", "class": "editor", "inhibitingIdle": False},
            ],
            [
                {
                    "who": "agent",
                    "what": "idle",
                    "why": "active turn",
                    "mode": "block",
                    "pid": 2,
                    "uid": 1000,
                }
            ],
        )
        self.assertEqual(state["hyprland_clients"]["inhibitors"][0]["class"], "media")
        self.assertEqual(state["systemd_logind"]["inhibitors"][0]["why"], "active turn")
        self.assertNotIn("presence", state)
        self.assertEqual(state["other_session_dbus"]["status"], "unsupported")

    def test_empty_and_missing(self):
        self.assertEqual(self.state([], [])["hyprland_clients"]["inhibitors"], [])
        self.assertEqual(
            self.state([{}], [])["hyprland_clients"]["status"], "unavailable"
        )
        self.assertEqual(
            self.state([], [{}])["systemd_logind"]["status"], "unavailable"
        )
        with patch.object(m.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(
                m.query(["missing"], list)["reason"], "command-unavailable"
            )

    def test_malformed_inventory(self):
        for text in ("null", "{}", "[1]", "bad"):
            with patch.object(
                m.subprocess,
                "run",
                return_value=type("Result", (), {"returncode": 0, "stdout": text})(),
            ):
                self.assertEqual(
                    m.query(["fake"], list)["reason"], "malformed-response"
                )

    def test_heartbeat_and_failed_write(self):
        writes = []
        state = {"fixture": 1}
        previous, last = m.emit_if_due(state, None, 10, 0, 300, writes.append)
        previous, last = m.emit_if_due(state, previous, 309, last, 300, writes.append)
        self.assertEqual(len(writes), 1)
        m.emit_if_due(state, previous, 310, last, 300, writes.append)
        self.assertEqual(writes[-1]["event"], "heartbeat")

        def fail(payload):
            raise RuntimeError("unacknowledged")

        with self.assertRaises(RuntimeError):
            m.emit_if_due({"fixture": 2}, previous, 311, last, 300, fail)
        self.assertEqual(previous, state)


unittest.main()
