#!/usr/bin/env -S python3 -I
"""Desktop notification when an attended agent session wants the operator.

One script for Claude Code and Codex; the harness name is the first argument
(`codex`; Claude Code when absent). It notifies in two cases only:

  - the session asks for permission or an answer (Claude Code `Notification`
    of type permission_prompt or elicitation_dialog, its `AskUserQuestion`
    tool, Codex `PermissionRequest`);
  - a turn ends more than LONG_TURN_SECONDS after its prompt. The prompt time
    is the modification time of a stamp written at `UserPromptSubmit`; `Stop`
    removes the stamp, so a turn without one never notifies.

Unattended runs stay silent. A run is unattended when it is an agentctl job
(its cgroup is under agent-ctl.slice), or when the harness process (the
nearest ancestor named after the harness) has no terminal on stdin and stdout,
or was started non-interactively (`claude -p`, `codex exec`). A harness that
cannot be found counts as unattended.

The toast goes through the notification daemon under the app name
`agent-attention`; dots/noctalia/config.toml gives that name no sound and lets
it through Do Not Disturb. The daemon draws below fullscreen windows, so when
the focused window is fullscreen the compositor's own notice is shown as well.

Every failure exits 0 with no output: a notification is never worth a blocked
turn. The senders are started detached and not waited for.
"""

import json
import os
import re
import subprocess
import sys
import time

LONG_TURN_SECONDS = 600
APP_NAME = "agent-attention"
TOAST_MILLISECONDS = 15000
NON_INTERACTIVE_ARGUMENTS = {"claude": {"-p", "--print"}, "codex": {"exec", "e"}}
ASKING_NOTIFICATIONS = {
    "permission_prompt": "needs permission",
    "elicitation_dialog": "asks a question",
}


def harness_process(name):
    """Pid of the nearest ancestor whose command name is the harness."""
    pid = os.getppid()
    for _ in range(16):
        with open(f"/proc/{pid}/stat", encoding="utf-8", errors="replace") as handle:
            stat = handle.read()
        command = stat[stat.index("(") + 1 : stat.rindex(")")]
        if command == name:
            return pid
        pid = int(stat[stat.rindex(")") + 2 :].split()[1])
        if pid <= 1:
            break
    return None


def on_terminal(pid, descriptor):
    target = os.readlink(f"/proc/{pid}/fd/{descriptor}")
    return target.startswith(("/dev/pts/", "/dev/tty"))


def attended(name):
    with open("/proc/self/cgroup", encoding="utf-8") as handle:
        if "/agent-ctl.slice/" in handle.read():
            return False
    pid = harness_process(name)
    if pid is None or not (on_terminal(pid, 0) and on_terminal(pid, 1)):
        return False
    with open(f"/proc/{pid}/cmdline", "rb") as handle:
        arguments = handle.read().decode("utf-8", "replace").split("\0")[1:]
    return not NON_INTERACTIVE_ARGUMENTS[name].intersection(arguments)


def stamp_path(name, session):
    runtime = os.environ["XDG_RUNTIME_DIR"]
    session = re.sub(r"[^A-Za-z0-9_-]", "_", session)[:128] or "unknown"
    return os.path.join(runtime, "sinnix-agent-turn", f"{name}-{session}")


def reason_for(name, payload):
    """Why the operator is wanted, or None. Maintains the turn stamp."""
    event = payload.get("hook_event_name")
    if event == "UserPromptSubmit":
        path = stamp_path(name, str(payload.get("session_id", "")))
        os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
        with open(path, "w", encoding="utf-8"):
            pass
        return None
    if event == "Stop":
        path = stamp_path(name, str(payload.get("session_id", "")))
        try:
            started = os.stat(path).st_mtime
        except FileNotFoundError:
            return None
        os.unlink(path)
        elapsed = time.time() - started
        if elapsed < LONG_TURN_SECONDS:
            return None
        return f"finished after {int(elapsed // 60)} min"
    if event == "Notification":
        return ASKING_NOTIFICATIONS.get(payload.get("notification_type"))
    if event == "PreToolUse" and payload.get("tool_name") == "AskUserQuestion":
        return "asks a question"
    if event == "PermissionRequest":
        tool = str(payload.get("tool_name") or "a tool")[:40]
        return f"needs permission for {tool}"
    return None


def start_detached(command):
    subprocess.Popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def focused_window_is_fullscreen():
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return False
    result = subprocess.run(
        ["hyprctl", "-j", "activewindow"],
        capture_output=True,
        text=True,
        timeout=0.05,
        check=False,
    )
    return bool(json.loads(result.stdout).get("fullscreen"))


def notify(title, reason):
    start_detached(
        [
            "notify-send",
            f"--app-name={APP_NAME}",
            "--urgency=normal",
            f"--expire-time={TOAST_MILLISECONDS}",
            "--hint=boolean:suppress-sound:true",
            title,
            reason,
        ]
    )
    try:
        fullscreen = focused_window_is_fullscreen()
    except Exception:
        return
    if fullscreen:
        start_detached(
            [
                "hyprctl",
                "notify",
                "-1",
                str(TOAST_MILLISECONDS),
                "rgb(e0af68)",
                f"fontsize:16 {title}: {reason}",
            ]
        )


def main():
    name = sys.argv[1] if len(sys.argv) > 1 else "claude"
    if name not in NON_INTERACTIVE_ARGUMENTS:
        return
    payload = json.load(sys.stdin)
    if not isinstance(payload, dict) or not attended(name):
        return
    reason = reason_for(name, payload)
    if reason is None:
        return
    project = os.path.basename(str(payload.get("cwd") or "").rstrip("/")) or "session"
    label = "Codex" if name == "codex" else "Claude Code"
    notify(f"{project} ({label})", reason)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
