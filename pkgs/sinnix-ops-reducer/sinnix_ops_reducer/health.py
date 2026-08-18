"""Inventory-driven health transitions: the sweep that watches every attested
runtime surface for staleness, failure, and recovery.

The reducer already reads the runtime inventory and already runs on a clock,
so the sweep runs here, on its own 60s tick inside the reducer's loop, with a
deduplicated transition ledger plus a desktop notification as its output. Two
properties that follow from living here rather than as a separate root
oneshot:

  * It runs IN the operator's session. A root process with no session bus
    would have to bridge every user-manager query and every liveness probe
    back into the session through sudo -- the kind of bridge that silently
    broke the PipeWire coverage probe (root cannot reach the user's pw-dump).
    Here the probes and `systemctl --user` are simply native.
  * The OnFailure fast path and the sweep share one state store by
    construction. When they kept separate keys the same unit re-notified on
    every failure and its recovery never paired with the outage
    (borgbackup-status.service, 2026-08-14).

Preserved exactly, because they are contracts other things read:
  * the ledger schema `sinnix-health-transition-v1` and its `k=v;k=v` evidence
    strings, at /run/sinnix/health-transitions.jsonl. The schema is open over
    the `status` value and every reader treats it that way (`/v1/health/lanes`
    hands the state file back verbatim; orient lists anything that is not
    "healthy"), so a new status is an additive change under the same name. The
    `capture_stale` statuses are `healthy`, `stale`, and -- added 2026-08-18 --
    `unproduced`, which means the lane's path holds no file at all: it has
    never produced, as opposed to having produced and stopped. That third
    state used to be reported as `stale`, which made a newly-declared lane and
    a dead one indistinguishable in both the ledger and the notification;
  * the state file shape at /run/sinnix/health-state.json --
    `{key: {status, pending?, streak?}}`, keyed `service:<manager>:<unit>`,
    `socket:<manager>:<unit>`, `capture:<name>`, `payload:<name>`,
    `publisher:<name>`, `mount:<path>`;
  * confirm-2 debounce, the prune that only the full sweep may run, and the
    notification rules (acknowledged silent, recovery only if the outage was
    announced, everything else critical).

The one capability that changes hands is socket recovery: `reset-failed` +
`start` on a *system* socket used to run as root and now runs as the operator,
so a polkit refusal surfaces as `recovery=failed` in the evidence rather than
as a silent success.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

from sinnix_lib.atomic_json import modify_json, read_json
from sinnix_lib.ledger import append_jsonl, utc_ts
from sinnix_lib.notify import notify_desktop
from sinnix_lib.paths import runtime_dir
from sinnix_lib.systemd import show_units

SCHEMA = "sinnix-health-transition-v1"
APP_NAME = "sinnix-health"

# How many consecutive sweeps must agree before a change is believed. The sweep
# samples on a fixed clock against a live machine, so a single disagreeing
# sample is as likely to be a race as a fault: a capture lane rotating its
# output file, an audio device between stream attachments, a publisher that has
# not finished registering since login. Every one of those self-clears within a
# sweep and none is worth a critical desktop notification. Requiring two
# agreeing samples costs one interval of latency on a real fault -- irrelevant
# for anything a human then has to go look at -- and removes the entire class.
CONFIRM_SAMPLES = 2

# Statuses that are not "healthy" but are also not a fault: the operator should
# be told once, calmly, and not paged. A lane that has never produced is either
# newly declared or has a producer that never ran -- both are worth a look and
# neither is an outage, and treating them as critical is what made the sweep's
# widening to budget-less lanes (2026-08-16) surface five simultaneous
# criticals for a condition that had been true for weeks.
CALM_STATUSES = frozenset({"unproduced"})

PAYLOAD_SAMPLE_SIZE = 50
PAYLOAD_MIN_SAMPLES = 5
SERVICE_PROPERTIES = ("Id", "ActiveState", "Type", "Result", "WantedBy")
SWEEP_INTERVAL_SECONDS = 60.0


def state_path() -> Path:
    return runtime_dir() / "health-state.json"


def ledger_path() -> Path:
    return runtime_dir() / "health-transitions.jsonl"


# --------------------------------------------------------------------------
# evidence and phrasing
# --------------------------------------------------------------------------


def evidence_field(evidence: str, key: str) -> str:
    """Evidence is a ";"-joined key=value list; pull one value out of it."""
    for part in evidence.split(";"):
        name, separator, value = part.partition("=")
        if separator and name == key:
            return value
    return ""


def humanize_duration(seconds: Any) -> str:
    try:
        value = int(seconds)
    except (TypeError, ValueError):
        return "0s"
    if value < 60:
        return f"{value}s"
    if value < 3600:
        return f"{value // 60}m"
    if value < 86400:
        return f"{value // 3600}h {(value % 3600) // 60}m"
    return f"{value // 86400}d {(value % 86400) // 3600}h"


def describe(
    type_: str, unit: str, status: str, evidence: str, previous: str = ""
) -> tuple[str, str]:
    """(title, body) a human can act on.

    The raw evidence string is a debugging carrier -- "manager=user;
    active_state=failed;type=oneshot;result=timeout;wanted_by=" tells you
    nothing at a glance about what broke or where to look -- so it stays in the
    JSONL ledger and out of the notification.

    *previous* is the status being left behind, which some phrasings need in
    order not to lie: a lane leaving `unproduced` is producing for the FIRST
    time, and calling that "recording again" tells the operator it recovered
    from an outage that never happened.
    """
    manager = evidence_field(evidence, "manager")
    key = f"{type_}:{status}"

    if key == "service_failure:healthy":
        return f"{unit} is running again", "Recovered on its own; nothing to do."
    if key == "service_failure:failed":
        result = evidence_field(evidence, "result")
        body = {
            "timeout": "Its last run hit the unit's time limit and was killed.",
            "exit-code": "Its last run exited with an error.",
            "oom-kill": "It was killed for running out of memory.",
            "signal": "It was killed by a signal.",
            "core-dump": "It was killed by a signal.",
        }.get(result, "It is not running and was not meant to be stopped.")
        scope = "--user " if manager == "user" else ""
        return f"{unit} stopped working", f"{body}\nLook: journalctl {scope}-u {unit} -e"
    if key == "service_failure:acknowledged":
        return (
            f"{unit} is down, as expected",
            "A known outage, acknowledged in the runtime inventory: "
            + evidence_field(evidence, "acknowledged_ref"),
        )
    if key == "service_failure:unknown":
        return (
            f"Cannot tell whether {unit} is healthy",
            "The sweep could not read its state, so this is neither a pass nor "
            "a failure.",
        )
    if key == "socket_failure:healthy":
        if evidence_field(evidence, "recovered") == "reset-failed+start":
            service = unit.removesuffix(".socket") + ".service"
            return (
                f"{unit} is listening again",
                "It had latched into failed and refused every connection; it was "
                "reset and restarted.\nIf this keeps happening, something behind "
                f"it is failing to activate: journalctl -u {service} -e",
            )
        return f"{unit} is listening again", "Recovered on its own; nothing to do."
    if key == "socket_failure:failed":
        result = evidence_field(evidence, "result")
        body = (
            "It hit systemd's activation rate limit and latched into failed, so "
            "its public port now refuses everything."
            if result == "trigger-limit-hit"
            else "The front-door socket is down, so nothing can reach the service "
            "behind it."
        )
        return f"{unit} is not accepting connections", f"{body}\nLook: journalctl -u {unit} -e"
    if key == "socket_failure:unknown":
        return (
            f"Cannot tell whether {unit} is listening",
            "The sweep could not read its state, so this is neither a pass nor "
            "a failure.",
        )
    if key == "capture_stale:healthy":
        age = evidence_field(evidence, "age_seconds")
        if previous == "unproduced":
            return (
                f"{unit} lane has produced for the first time",
                f"It was declared but empty; there is now a file in it, "
                f"{humanize_duration(age or 0)} old.",
            )
        return (
            f"{unit} lane is recording again",
            f"Newest file is {humanize_duration(age or 0)} old.",
        )
    if key == "capture_stale:unproduced":
        return (
            f"{unit} lane has never produced anything",
            "Its path holds no file at all, so this is not a quiet spell -- "
            "either the lane is newly declared and its producer has not run "
            "yet, or the producer has never once written.\nPath: "
            + evidence_field(evidence, "path"),
        )
    if key == "capture_stale:stale":
        age = evidence_field(evidence, "age_seconds")
        budget = evidence_field(evidence, "stale_after_seconds")
        body = f"Nothing written for {humanize_duration(age)}"
        if budget and budget != "null":
            body += f", past its {humanize_duration(budget)} budget"
        body += "."
        return (
            f"{unit} lane has gone quiet",
            body + "\nPath: " + evidence_field(evidence, "path"),
        )
    if key == "capture_payload:degenerate":
        return (
            f"{unit} lane is writing empty records",
            "It is producing files on schedule, but the fields it promises to "
            "fill are null in every recent record -- a broken producer, not a "
            "quiet hour.",
        )
    if key == "capture_payload:healthy":
        return (
            f"{unit} lane is writing real data again",
            "Recent records carry the fields the lane declares.",
        )
    if key == "publisher_liveness:healthy":
        return (
            f"{unit} lane has its source back",
            "The thing this lane observes is publishing again.",
        )
    if key == "publisher_liveness:publisher-absent":
        return (
            f"Nothing is publishing to the {unit} lane",
            "The lane and its unit are fine; the source it watches is not there, "
            "so it will stay silent until that returns.",
        )
    if key == "publisher_liveness:unknown":
        return (
            f"The {unit} liveness check could not answer",
            "The probe itself failed (exit "
            f"{evidence_field(evidence, 'probe_exit') or '?'}), so this says "
            "nothing about the lane. Fix the probe before reading anything into it.",
        )
    if type_ == "mount_capacity":
        if status == "healthy":
            return (
                f"{unit} has room again",
                f"Now at {evidence_field(evidence, 'usage_percent')}% used.",
            )
        usage = evidence_field(evidence, "usage_percent")
        warn = evidence_field(evidence, "warn_percent")
        fail = evidence_field(evidence, "fail_percent")
        body = (
            f"Past the {fail}% line where writes start to be at risk."
            if status == "failed"
            else f"Past the {warn}% warning line (fails at {fail}%)."
        )
        return f"{unit} is {usage}% full", body
    return f"{unit}: {status}", type_


# --------------------------------------------------------------------------
# the deduplicated emitter
# --------------------------------------------------------------------------


class Emitter:
    """Confirm-2 debounce, the transition ledger, and the notification rules.

    One instance per sweep; the state file is the durable part and is opened
    under a lock for every mutation, so the OnFailure fast path can write the
    same keys from another process without either side losing an update.
    """

    def __init__(
        self,
        state: Path | None = None,
        ledger: Path | None = None,
        notifier: Callable[[str, str, str], None] | None = None,
        confirm_samples: int = CONFIRM_SAMPLES,
    ) -> None:
        self.state = state or state_path()
        self.ledger = ledger or ledger_path()
        self.confirm_samples = confirm_samples
        self.notifier = notifier or self._notify
        # Every key emit() is called with, whether or not its status changed:
        # the full sweep uses this to prune keys it no longer emits, which
        # emit() alone can never do since it only touches keys it currently
        # sees.
        self.emitted_keys: list[str] = []

    @staticmethod
    def _notify(urgency: str, title: str, body: str) -> None:
        notify_desktop(title, body, urgency=urgency, app_name=APP_NAME)

    def observe(self, key: str) -> None:
        """Register a key without judging it (mid-transition units).

        Skipping the key entirely would prune it, which resets a genuine
        "failed" memory to empty and makes a crash-looping unit re-notify on
        every restart.
        """
        self.emitted_keys.append(key)

    def emit(
        self,
        key: str,
        type_: str,
        unit: str,
        status: str,
        evidence: str,
        *,
        force_confirm: bool = False,
    ) -> None:
        self.emitted_keys.append(key)
        transition: tuple[str, str] | None = None
        with modify_json(self.state, {}, mode=0o664) as document:
            entry = document.get(key)
            # Older state files hold a bare status string; read both shapes.
            if isinstance(entry, dict):
                confirmed = str(entry.get("status") or "")
                pending = str(entry.get("pending") or "")
                streak = int(entry.get("streak") or 0)
            else:
                confirmed = str(entry or "")
                pending = ""
                streak = 0

            if status == confirmed:
                # Agrees with what we believe. Drop any half-accumulated
                # candidate: a fault must be witnessed on CONSECUTIVE sweeps,
                # not merely twice ever, or a lane that blips once an hour
                # eventually pages anyway.
                if pending:
                    document[key] = {"status": status}
                return

            streak = streak + 1 if status == pending else 1
            # A key we have never seen settling into "healthy" is startup, not
            # a recovery: believe it at once and say nothing.
            if not confirmed and status == "healthy":
                streak = self.confirm_samples
            if force_confirm:
                streak = self.confirm_samples

            if streak < self.confirm_samples:
                document[key] = {
                    "status": confirmed,
                    "pending": status,
                    "streak": streak,
                }
                return

            document[key] = {"status": status}
            transition = (confirmed, status)

        if transition is None:
            return
        confirmed, status = transition
        append_jsonl(
            self.ledger,
            {
                "schema": SCHEMA,
                "ts": utc_ts(),
                "type": type_,
                "unit": unit,
                "status": status,
                "ok": status == "healthy",
                "evidence": evidence,
                "confirmed_after_samples": self.confirm_samples,
            },
            mode=0o664,
        )
        title, body = describe(type_, unit, status, evidence, confirmed)
        if status == "acknowledged":
            # Recorded in the ledger, never paged: the operator already knows,
            # and a notification for a known outage is exactly the noise the
            # acknowledgement exists to remove.
            return
        if status == "healthy":
            # Only notify a recovery if we announced the outage: an empty
            # `confirmed` means this key has never transitioned before
            # (steady-state startup), not "it came back".
            if confirmed:
                self.notifier("normal", title, body)
            return
        self.notifier("critical" if status not in CALM_STATUSES else "normal", title, body)

    def prune(self) -> None:
        """Drop any state key this run did not emit.

        Only the full sweep knows the complete current emission-key universe,
        so pruning is safe there and only there -- pruning after the OnFailure
        fast path would wipe every other lane's state on its next comparison,
        turning one failure event into a spurious transition storm.
        """
        keep = set(self.emitted_keys)
        with modify_json(self.state, {}, mode=0o664) as document:
            for key in [key for key in document if key not in keep]:
                del document[key]


# --------------------------------------------------------------------------
# the sweeps
# --------------------------------------------------------------------------


def newest_mtime(path: Path) -> float | None:
    """Newest write under *path*, which may be a single file: five of the
    borg lanes point at marker/ledger FILES, and os.walk over a file yields
    nothing -- the bash sentinel's `find` handled both shapes, and losing
    that silently read every file lane as stale (caught live 2026-08-18)."""
    try:
        if path.is_file():
            return path.stat().st_mtime
    except OSError:
        return None
    newest: float | None = None
    for root, _directories, files in os.walk(path):
        for name in files:
            try:
                stamp = os.stat(Path(root) / name).st_mtime
            except OSError:
                continue
            if newest is None or stamp > newest:
                newest = stamp
    return newest


def sweep_captures(captures: Iterable[dict[str, Any]], emitter: Emitter, now: float) -> None:
    """Every declared lane, including those with neither a cadence nor a budget.

    Those used to be filtered out, which meant the MOST broken state a lane can
    be in -- declared, wired, and never having produced a single file -- was the
    one state that raised nothing. Five lanes were in exactly that state on
    2026-08-16, four with a path that did not exist at all. An age-based verdict
    still needs a budget; "has this lane ever produced anything" needs none.

    Three outcomes, not two, because a lane's silence has three causes and only
    one of them is a fault:

      * `unproduced` -- the path holds no file. The lane has never produced, so
        there is no age to judge and no budget that could have been exceeded.
        Calm: newly-declared lanes pass through this state on their way to
        working, and a producer that has never run is a wiring question rather
        than an outage.
      * `stale` -- it produced before and has now been idle past its budget.
        This is the fault case: something that was working stopped.
      * `healthy` -- it produced recently enough, or it is an event-driven lane
        inside a generous budget with nothing to say. Indistinguishable from
        `unproduced` before this split, which is why a correctly-wired
        video-resolve lane that had simply never matched a candidate URL read
        as a dead one.
    """
    for lane in captures:
        path = str(lane.get("path") or "")
        name = str(lane.get("name") or "")
        if not path:
            continue
        newest = newest_mtime(Path(path))
        if newest is None:
            emitter.emit(
                f"capture:{name}",
                "capture_stale",
                name,
                "unproduced",
                f"path={path};reason=no-file;"
                f"path_exists={'true' if Path(path).exists() else 'false'}",
            )
            continue
        age = int(now) - int(newest)
        cadence = lane.get("expectedCadenceSeconds")
        stale_after = lane.get("expectedStaleAfterSeconds")
        stale = False
        # Cadence-driven lanes: stale once idle past twice their cadence.
        if isinstance(cadence, (int, float)) and age > cadence * 2:
            stale = True
        # Event-driven (or cadence + explicit budget) lanes: stale once idle
        # past their absolute budget, independent of any cadence check.
        if isinstance(stale_after, (int, float)) and age > stale_after:
            stale = True
        evidence = (
            f"path={path};age_seconds={age};"
            f"cadence_seconds={'null' if cadence is None else cadence};"
            f"stale_after_seconds={'null' if stale_after is None else stale_after}"
        )
        emitter.emit(
            f"capture:{name}",
            "capture_stale",
            name,
            "stale" if stale else "healthy",
            evidence,
        )


def leaf(record: Any, dotted: str) -> Any:
    value = record
    for part in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def degenerate(value: Any) -> bool:
    return value is None or value == "" or value == {} or value == []


def sweep_payloads(captures: Iterable[dict[str, Any]], emitter: Emitter) -> None:
    """A lane can write at full cadence forever with every meaningful field
    null, and every staleness check calls it healthy. A field that is
    null/empty in EVERY sampled record is the signature of a broken producer,
    not of a quiet hour -- and this is deliberately all-or-nothing, so a
    legitimately-sometimes-null field can never raise a false alarm.
    """
    for lane in captures:
        fields = lane.get("requiredPayloadFields")
        path = str(lane.get("path") or "")
        name = str(lane.get("name") or "")
        if not path or not isinstance(fields, list) or not fields:
            continue
        candidates = [
            entry
            for entry in Path(path).glob("*.jsonl")
            if entry.is_file() and not entry.name.endswith("-index.jsonl")
        ]
        if not candidates:
            continue
        newest = max(candidates, key=lambda entry: entry.stat().st_mtime)
        try:
            lines = newest.read_text(encoding="utf-8").splitlines()[-PAYLOAD_SAMPLE_SIZE:]
        except OSError:
            continue
        payloads = []
        for line in lines:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                # A record with no payload at all counts as a sampled payload
                # of null -- a producer emitting envelopes with nothing in them
                # is exactly the fault this check exists for.
                payloads.append(record.get("payload"))
        # No records yet, or too few to judge: say nothing. "Lane produced
        # nothing" is the staleness check's job on this same path.
        if len(payloads) < PAYLOAD_MIN_SAMPLES:
            continue
        dead = [
            field
            for field in fields
            if all(degenerate(leaf(payload, str(field))) for payload in payloads)
        ]
        if dead:
            emitter.emit(
                f"payload:{name}",
                "capture_payload",
                name,
                "degenerate",
                f"file={newest};samples={len(payloads)};always_empty={','.join(map(str, dead))}",
            )
        else:
            emitter.emit(
                f"payload:{name}",
                "capture_payload",
                name,
                "healthy",
                f"file={newest};samples={len(payloads)}",
            )


def run_probe(command: str, timeout: float) -> int:
    """A lane's own answer to "is the thing I observe actually present?".

    Exit 0 means present, 1 means confirmed absent, anything else -- including
    timeout's 124 -- means the probe itself could not answer, which is reported
    as unknown and never silently as healthy. Run directly in the operator's
    session: every lane declaring a probe observes a session publisher
    (PipeWire, AT-SPI), which is exactly what the sentinel's root context could
    not reach.
    """
    try:
        return subprocess.run(
            ["bash", "-c", command],
            check=False,
            capture_output=True,
            timeout=timeout,
        ).returncode
    except subprocess.TimeoutExpired:
        return 124
    except OSError:
        return 3


def sweep_probes(captures: Iterable[dict[str, Any]], emitter: Emitter) -> None:
    for lane in captures:
        probe = lane.get("livenessProbe")
        if not isinstance(probe, dict) or not probe.get("command"):
            continue
        name = str(lane.get("name") or "")
        path = str(lane.get("path") or "")
        code = run_probe(str(probe["command"]), float(probe.get("timeoutSeconds") or 5))
        if code == 0:
            emitter.emit(f"publisher:{name}", "publisher_liveness", name, "healthy", f"path={path}")
        elif code == 1:
            emitter.emit(
                f"publisher:{name}",
                "publisher_liveness",
                name,
                "publisher-absent",
                f"path={path};probe_exit={code}",
            )
        else:
            emitter.emit(
                f"publisher:{name}",
                "publisher_liveness",
                name,
                "unknown",
                f"path={path};probe_exit={code}",
            )


def mount_usage_percent(path: str) -> int:
    """df's own percentage, not a recomputation of it: the warn/fail lines were
    set against what df reports, reserved blocks and all."""
    try:
        result = subprocess.run(
            ["df", "-P", path], check=False, capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return 100
    lines = result.stdout.splitlines()
    if len(lines) < 2:
        return 100
    fields = lines[1].split()
    if len(fields) < 5:
        return 100
    try:
        return int(fields[4].rstrip("%"))
    except ValueError:
        return 100


def sweep_mounts(mounts: Iterable[dict[str, Any]], emitter: Emitter) -> None:
    for mount in mounts:
        path = str(mount.get("path") or "")
        if not path:
            continue
        warn = int(mount.get("warnPct") or 100)
        fail = int(mount.get("failPct") or 100)
        usage = mount_usage_percent(path)
        status = "healthy"
        if usage >= warn:
            status = "warning"
        if usage >= fail:
            status = "failed"
        emitter.emit(
            f"mount:{path}",
            "mount_capacity",
            path,
            status,
            f"usage_percent={usage};warn_percent={warn};fail_percent={fail}",
        )


def unit_properties(
    services: Sequence[dict[str, Any]],
    prober: Callable[[Sequence[str], bool], dict[str, dict[str, str]]] | None = None,
) -> dict[tuple[str, str], dict[str, str]]:
    """One batched `systemctl show` per manager, keyed (manager, unit).

    Batched because each per-unit query used to cost three PAM journal lines
    through sudo, ~120 records a sweep on a one-minute clock -- which made the
    sentinel the second-loudest journal producer on a wear-limited disk. The
    sudo bridge is gone (this runs in the session), the batching stays.
    """
    probe = prober or (
        lambda units, user: show_units(units, user=user, properties=SERVICE_PROPERTIES)
    )
    found: dict[tuple[str, str], dict[str, str]] = {}
    for manager in ("system", "user"):
        units = [
            str(entry["unit"])
            for entry in services
            if entry.get("unit") and str(entry.get("manager") or "system") == manager
        ]
        if not units:
            continue
        for unit, properties in probe(units, manager == "user").items():
            found[(manager, unit)] = properties
    return found


def sweep_services(
    services: Sequence[dict[str, Any]],
    properties: dict[tuple[str, str], dict[str, str]],
    emitter: Emitter,
) -> None:
    """Resting-state expectation derived from what systemd itself reports,
    never from a hardcoded unit list, which would rot the moment a new oneshot
    or on-demand backend is added:

      - a oneshot judges itself by Result -- it is SUPPOSED to go inactive once
        it finishes; ran-and-succeeded is healthy, anything else failed;
      - a unit nothing pulls in at boot/login (WantedBy empty) is on-demand by
        design, as is a declared socket-proxy backend; inactive is its correct
        resting state. "On-demand" excuses being inactive, not having crashed,
        so Result must still say the last run ended cleanly;
      - anything else that isn't active is a daemon that IS supposed to be
        running and isn't.
    """
    for entry in services:
        unit = str(entry.get("unit") or "")
        if not unit:
            continue
        manager = str(entry.get("manager") or "system")
        activation_mode = str(entry.get("activationMode") or "direct")
        acknowledged = entry.get("acknowledged") if isinstance(entry.get("acknowledged"), dict) else {}
        info = properties.get((manager, unit), {})
        active_state = info.get("ActiveState", "")
        unit_type = info.get("Type", "")
        result = info.get("Result", "")
        wanted_by = info.get("WantedBy", "")
        key = f"service:{manager}:{unit}"

        if not active_state:
            status, evidence = "unknown", f"manager={manager};probe=unreachable"
        elif active_state == "active":
            status, evidence = "healthy", f"manager={manager};active_state={active_state}"
        elif active_state == "inactive" and unit_type == "oneshot":
            status = "healthy" if result == "success" else "failed"
            evidence = (
                f"manager={manager};active_state={active_state};type=oneshot;result={result}"
            )
        elif active_state == "inactive" and (activation_mode == "socket-proxy" or not wanted_by):
            status = "healthy" if result == "success" else "failed"
            evidence = (
                f"manager={manager};active_state={active_state};"
                f"activation_mode={activation_mode};wanted_by=;on-demand;result={result}"
            )
        elif active_state in {"inactive", "failed"}:
            status = "failed"
            evidence = (
                f"manager={manager};active_state={active_state};type={unit_type};"
                f"result={result};wanted_by={wanted_by}"
            )
        elif active_state in {"activating", "deactivating", "reloading", "maintenance"}:
            # Mid-transition is not a verdict. Every timer-driven oneshot spends
            # its entire run in "activating", so scoring this state makes
            # ordinary work indistinguishable from an outage. Hold the previous
            # verdict: register the key so the prune keeps it, emit nothing.
            emitter.observe(key)
            continue
        else:
            status, evidence = "unknown", f"manager={manager};active_state={active_state}"

        # An acknowledged outage is expected, so it must not be scored as a
        # failure -- but it is deliberately NOT silenced: the surface still
        # emits, carrying its acknowledgement reference, so it appears in the
        # ledger as known-down rather than disappearing. An ack that outlives
        # its reason should be embarrassing to look at, not invisible.
        if acknowledged.get("down") is True and status == "failed":
            status = "acknowledged"
            evidence = f"{evidence};acknowledged_ref={acknowledged.get('ref') or ''}"
        emitter.emit(key, "service_failure", unit, status, evidence)


def sweep_sockets(
    sockets: Sequence[dict[str, Any]],
    properties: dict[tuple[str, str], dict[str, str]],
    emitter: Emitter,
    recover: Callable[[str, str], bool] | None = None,
) -> None:
    """A socket's healthy resting state is "listening" -- it is the front door,
    and unlike the backends behind it there is no legitimate reason for it to be
    down.

    trigger-limit-hit is why this sweep exists: systemd latches the socket into
    failed after too many activations in too short a window and never re-arms
    it, so the public port refuses every connection forever while the backend
    behind it looks perfectly healthy. Recovery is exactly `reset-failed` +
    `start` with nothing at stake, so do it -- but say so, because a socket that
    keeps needing this is reporting a real fault upstream.
    """
    heal = recover or reset_and_start
    for entry in sockets:
        unit = str(entry.get("unit") or "")
        if not unit:
            continue
        manager = str(entry.get("manager") or "system")
        info = properties.get((manager, unit), {})
        active_state = info.get("ActiveState", "")
        result = info.get("Result", "")
        if not active_state:
            status, evidence = "unknown", f"manager={manager};probe=unreachable"
        elif active_state == "active":
            status, evidence = "healthy", f"manager={manager};active_state={active_state}"
        else:
            status = "failed"
            evidence = f"manager={manager};active_state={active_state};result={result}"
            if result == "trigger-limit-hit" and manager == "system":
                if heal(manager, unit):
                    status = "healthy"
                    evidence = f"{evidence};recovered=reset-failed+start"
                else:
                    evidence = f"{evidence};recovery=failed"
        emitter.emit(f"socket:{manager}:{unit}", "socket_failure", unit, status, evidence)


def reset_and_start(manager: str, unit: str) -> bool:
    scope = ["--user"] if manager == "user" else ["--system"]
    for verb in ("reset-failed", "start"):
        try:
            result = subprocess.run(
                ["systemctl", *scope, verb, unit],
                check=False,
                capture_output=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            return False
        if result.returncode != 0:
            return False
    return True


# --------------------------------------------------------------------------
# the whole sweep, and the OnFailure fast path
# --------------------------------------------------------------------------


def observed(inventory: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    rows = inventory.get("observedServices")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict) and row.get("kind") == kind]


def captures_of(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    rows = inventory.get("captures")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def mounts_of(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    rows = inventory.get("mounts")
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def sweep(
    inventory: dict[str, Any],
    emitter: Emitter,
    now: float | None = None,
    prober: Callable[[Sequence[str], bool], dict[str, dict[str, str]]] | None = None,
) -> Emitter:
    captures = captures_of(inventory)
    services = observed(inventory, "service")
    sockets = observed(inventory, "socket")
    properties = unit_properties([*services, *sockets], prober)
    sweep_captures(captures, emitter, time.time() if now is None else now)
    sweep_payloads(captures, emitter)
    sweep_probes(captures, emitter)
    sweep_mounts(mounts_of(inventory), emitter)
    sweep_services(services, properties, emitter)
    sweep_sockets(sockets, properties, emitter)
    emitter.prune()
    return emitter


def emit_failure(
    unit: str, result: str, inventory: dict[str, Any], emitter: Emitter | None = None
) -> None:
    """The OnFailure hook's event: systemd REPORTING a failure rather than the
    sweep sampling for one.

    An OnFailure= hook fires exactly once, so requiring a second agreeing
    observation would discard the most authoritative signal there is -- hence
    force_confirm. The key is the sweep's own key, not a private one: when they
    differed, the sweep's prune deleted the fast path's key on its next run, so
    the same unit failing again always looked like a first-ever transition and
    notified again, while the recovery -- recorded by the sweep under its own
    key -- never paired with the outage the operator was told about.
    """
    if "." not in unit:
        unit = f"{unit}.service"
    manager = "system"
    for entry in observed(inventory, "service"):
        if entry.get("unit") == unit:
            manager = str(entry.get("manager") or "system")
            break
    (emitter or Emitter()).emit(
        f"service:{manager}:{unit}",
        "service_failure",
        unit,
        "failed",
        f"manager={manager};source=onfailure;result={result or 'unknown'}",
        force_confirm=True,
    )


def current_state(state: Path | None = None) -> dict[str, Any]:
    value = read_json(state or state_path(), {})
    return value if isinstance(value, dict) else {}
