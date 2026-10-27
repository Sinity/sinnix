"""Ephemeral exact desktop destinations. No title/cwd matching or job control."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import urlopen

CDP = "http://127.0.0.1:9222"


def command(args: list[str]) -> Any:
    result = subprocess.run(args, capture_output=True, text=True, timeout=3, check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def browser(path: str) -> Any:
    with urlopen(CDP + path, timeout=2) as response:
        return json.load(response)


def destinations() -> dict[str, Any]:
    rows, gaps = [], []
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
    for sock in sorted(runtime.glob("kitty-*"))[:16]:
        try:
            if not sock.is_socket():
                continue
            pid = int(sock.name.rsplit("-", 1)[1])
            start = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
            epoch = f"{Path('/proc/sys/kernel/random/boot_id').read_text().strip()}:{pid}:{start}:{sock.stat().st_ino}"
            for window in command(["kitty", "@", "--to", f"unix:{sock}", "ls"]):
                for tab in window.get("tabs", []):
                    for terminal in tab.get("windows", []):
                        pin = {
                            "kind": "terminal",
                            "endpoint": str(sock),
                            "epoch": epoch,
                            "id": str(terminal["id"]),
                        }
                        rows.append(
                            {
                                "name": str(terminal.get("title") or "Terminal")[:180],
                                "state": "observed terminal; execution state unknown",
                                "pin": pin,
                                "detail": (
                                    str(terminal.get("cwd") or "")
                                    + " · "
                                    + " ".join(
                                        str(part)
                                        for proc in terminal.get(
                                            "foreground_processes", []
                                        )
                                        for part in proc.get("cmdline", [])
                                    )
                                )[:300],
                            }
                        )
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            gaps.append(f"terminal unavailable: {sock.name}")
    if not rows:
        gaps.append("No terminal destinations observed")
    try:
        epoch = browser("/json/version")["webSocketDebuggerUrl"]
        if not isinstance(epoch, str) or not epoch:
            raise ValueError("browser incarnation unavailable")
        for tab in browser("/json/list"):
            url = str(tab.get("url", ""))
            if tab.get("type") == "page" and urlsplit(url).hostname in {
                "chatgpt.com",
                "claude.ai",
                "gemini.google.com",
            }:
                rows.append(
                    {
                        "name": str(tab.get("title") or "Conversation")[:180],
                        "state": "conversation place; remote execution unknown",
                        "detail": url,
                        "pin": {
                            "kind": "conversation",
                            "epoch": epoch,
                            "id": tab["id"],
                            "url": url,
                        },
                    }
                )
    except (OSError, ValueError, KeyError):
        gaps.append("Conversation source unavailable")
    return {"rows": rows[:40], "gaps": gaps, "omitted": max(0, len(rows) - 40)}


def focus(pin: dict[str, Any]) -> None:
    # Revalidate the whole pin against its owner immediately before focus.
    if (
        not isinstance(pin, dict)
        or not pin
        or not any(row["pin"] == pin for row in destinations()["rows"])
    ):
        raise ValueError(
            "Destination stale/unverified. Rebind explicitly to a current row."
        )
    if pin["kind"] == "terminal":
        command(
            [
                "kitty",
                "@",
                "--to",
                "unix:" + pin["endpoint"],
                "focus-window",
                "--match",
                "id:" + pin["id"],
            ]
        )
    else:
        with urlopen(CDP + "/json/activate/" + pin["id"], timeout=2) as response:
            response.read()
