"""Parse an explicit numeric same-daemon decision, never infer PSI from kill."""

import json
import re


def daemon_decision(text, victim_pid):
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
    for i in range(len(rows) - 3):
        block = rows[i : i + 4]
        daemon = block[0].get("_PID")
        if not daemon or any(row.get("_PID") != daemon for row in block):
            continue
        messages = [row.get("MESSAGE", "") for row in block]
        if not all(isinstance(message, str) for message in messages):
            continue
        psi = re.fullmatch(
            r"memory PSI full avg10 ([0-9.]+) >= ([0-9.]+): kills enabled again",
            messages[0],
        )
        memory = re.fullmatch(
            r"mem avail:.*?\(\s*([0-9.]+)%\), swap free:.*?\(\s*([0-9.]+)%\)",
            messages[1],
        )
        limits = re.fullmatch(
            r"low memory! at or below SIGKILL limits: mem\s+([0-9.]+)%, swap\s+([0-9.]+)%",
            messages[2],
        )
        if not (
            psi
            and memory
            and limits
            and re.match(
                rf"sending SIGKILL to process {int(victim_pid)}\s", messages[3]
            )
        ):
            continue
        full, threshold = map(float, psi.groups())
        ram, swap = map(float, memory.groups())
        if not (
            full >= threshold == 10
            and ram <= 5
            and swap <= 5
            and tuple(map(float, limits.groups())) == (5, 5)
        ):
            continue
        ticks = [int(row["__MONOTONIC_TIMESTAMP"]) for row in block]
        if ticks != sorted(ticks):
            continue
        for after in rows[i + 4 : i + 12]:
            if after.get("_PID") != daemon:
                break
            message = after.get("MESSAGE", "")
            if not isinstance(message, str) or "sending SIG" in message:
                break
            exited = re.fullmatch(
                rf"process {int(victim_pid)} exited after ([0-9.]+) seconds", message
            )
            signal_to_exit = float(exited[1]) if exited else None
            decision_to_signal = (ticks[3] - ticks[0]) / 1_000_000
            if (
                exited
                and signal_to_exit >= 0
                and decision_to_signal + signal_to_exit < 30
            ):
                return {
                    "source": "daemon_decision",
                    "daemon_pid": int(daemon),
                    "victim_pid": int(victim_pid),
                    "memory_full_avg10": full,
                    "available_percent": ram,
                    "swap_free_percent": swap,
                    "gate_to_exit_seconds": decision_to_signal + signal_to_exit,
                    "decision_to_signal_seconds": decision_to_signal,
                    "signal_to_exit_seconds": signal_to_exit,
                    "gate_to_exit_observer": "daemon_journal_clock_and_reported_exit",
                    "decision_monotonic_us": ticks[0],
                }
    return None


def validate_helper(unit, properties):
    """Check before-stop state while systemd still retains any failure."""
    assert properties["CollectMode"] == "inactive", (unit, properties)
    assert properties["Result"] == "success", (unit, properties)
    if unit == "pressure-transition.service":
        assert properties["ActiveState"] == "inactive", (unit, properties)
        assert properties["ExecMainStatus"] == "0", (unit, properties)
    elif unit == "pressure-io.service":
        assert properties["ActiveState"] in ("active", "inactive"), (unit, properties)
    else:
        assert (
            properties["ActiveState"] == "active" and int(properties["MainPID"]) > 0
        ), (unit, properties)
    return {
        key: properties[key]
        for key in ("CollectMode", "Result", "ActiveState", "MainPID", "ExecMainStatus")
    }
