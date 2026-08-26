"""Daily, evidence-backed process-delta proposer.

This module deliberately separates observation, model judgment, and task
mutation.  A model may suggest work, but the runner only files bounded,
validated Beads proposals and never changes an existing task.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

MAX_SOURCE_BYTES = 128_000
MAX_PROMPT_BYTES = 180_000
MAX_PROPOSALS = 12
MAX_FIELD_LENGTH = 4_000
DEFAULT_MODEL = "gpt-5.6-terra"


class RetrospectiveError(ValueError):
    """The retrospective input, model output, or task boundary is invalid."""


def _day_start(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def _read_bounded(path: Path) -> str:
    try:
        with path.open("rb") as handle:
            value = handle.read(MAX_SOURCE_BYTES + 1)
    except OSError:
        return ""
    if len(value) > MAX_SOURCE_BYTES:
        value = value[:MAX_SOURCE_BYTES]
    return value.decode(errors="replace")


def _event_day(line: str, day: date) -> bool:
    try:
        event = json.loads(line)
        timestamp = event.get("timestamp", event.get("created_at"))
        if not isinstance(timestamp, str):
            return False
        parsed = datetime.fromisoformat(timestamp)
        if parsed.tzinfo is None:
            return False
        return (
            _day_start(day)
            <= parsed.astimezone(UTC)
            < _day_start(day + timedelta(days=1))
        )
    except (ValueError, TypeError, json.JSONDecodeError):
        return False


def collect_evidence(
    *,
    day: date,
    event_spool: Path,
    harvest_root: Path,
    harvest_glob: str,
    receipt_root: Path,
) -> dict[str, Any]:
    """Collect bounded, date-scoped evidence without treating it as authority."""
    event_lines = [
        line
        for line in _read_bounded(event_spool).splitlines()
        if _event_day(line, day)
    ]
    harvest: dict[str, str] = {}
    for path in sorted(harvest_root.glob(harvest_glob)):
        content = _read_bounded(path)
        if content:
            harvest[str(path)] = content
    receipts: dict[str, str] = {}
    if receipt_root.is_dir():
        for path in sorted(receipt_root.glob("**/*.json")):
            content = _read_bounded(path)
            if content and _event_day(content.splitlines()[0], day):
                receipts[str(path)] = content
    return {
        "day": day.isoformat(),
        "events": event_lines,
        "harvest_logs": harvest,
        "session_receipts": receipts,
    }


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def build_prompt(evidence: Mapping[str, Any]) -> str:
    prompt = """You are a small, conservative process-retrospective analyst.
Review ONLY the supplied evidence from one UTC day. Identify repeated or
material process failures that are evidenced by concrete events, harvest
logs, or session receipts. Suggest at most 12 independent process-delta tasks.
Do not suggest product work, personal data handling, or fixes based on guesswork.
Return JSON only, exactly: {\"proposals\":[{\"title\":string,\"description\":string,
\"type\":\"task\"|\"bug\",\"priority\":0|1|2|3|4,\"labels\":[string],
\"evidence\":[string]}]}. Each evidence item must name an observed source or
event. Evidence references must begin with events.jsonl:, harvest:, or session:.
An empty proposal list is valid.

EVIDENCE:
""" + json.dumps(evidence, sort_keys=True, ensure_ascii=True)
    if len(prompt.encode()) > MAX_PROMPT_BYTES:
        raise RetrospectiveError("retrospective prompt exceeds its bound")
    return prompt


def validate_proposals(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != {"proposals"}:
        raise RetrospectiveError("model output must contain only proposals")
    proposals = value["proposals"]
    if not isinstance(proposals, list) or len(proposals) > MAX_PROPOSALS:
        raise RetrospectiveError("model proposals exceed the bound")
    result = []
    for proposal in proposals:
        if not isinstance(proposal, dict) or set(proposal) != {
            "title",
            "description",
            "type",
            "priority",
            "labels",
            "evidence",
        }:
            raise RetrospectiveError("model proposal has an invalid shape")
        if (
            proposal["type"] not in {"task", "bug"}
            or not isinstance(proposal["priority"], int)
            or isinstance(proposal["priority"], bool)
            or proposal["priority"] not in range(5)
        ):
            raise RetrospectiveError("model proposal type or priority is invalid")
        for name in ("title", "description"):
            if (
                not isinstance(proposal[name], str)
                or not proposal[name]
                or len(proposal[name]) > MAX_FIELD_LENGTH
            ):
                raise RetrospectiveError(f"model proposal {name} is invalid")
        if any(
            not item.startswith(("events.jsonl:", "harvest:", "session:"))
            for item in proposal["evidence"]
        ):
            raise RetrospectiveError(
                "model proposal evidence is not a source reference"
            )
        for name in ("labels", "evidence"):
            values = proposal[name]
            if (
                not isinstance(values, list)
                or not values
                or len(values) > 16
                or any(
                    not isinstance(item, str)
                    or not item
                    or len(item) > MAX_FIELD_LENGTH
                    for item in values
                )
            ):
                raise RetrospectiveError(f"model proposal {name} is invalid")
        result.append(
            {
                **proposal,
                "labels": sorted(set(proposal["labels"])),
                "evidence": proposal["evidence"],
            }
        )
    return result


def run_retrospective(
    *,
    evidence: Mapping[str, Any],
    model_call: Callable[[str], str],
    task_create: Callable[[dict[str, Any]], None],
    state_path: Path,
) -> dict[str, Any]:
    prompt = build_prompt(evidence)
    try:
        decoded = json.loads(model_call(prompt))
    except (json.JSONDecodeError, OSError) as error:
        raise RetrospectiveError("retrospective model did not return JSON") from error
    proposals = validate_proposals(decoded)
    evidence_digest = _digest(evidence)
    filed = 0
    for index, proposal in enumerate(proposals):
        task_create(
            {
                "title": proposal["title"],
                "description": proposal["description"]
                + "\n\nEvidence:\n- "
                + "\n- ".join(proposal["evidence"]),
                "type": proposal["type"],
                "priority": proposal["priority"],
                "labels": ["process-retrospective", *proposal["labels"]],
                "request_id": _digest({"evidence": evidence_digest, "index": index}),
            }
        )
        filed += 1
    state_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "schema": 1,
                "day": evidence["day"],
                "evidence_sha256": evidence_digest,
                "filed": filed,
            }
        )
        + "\n"
    )
    return {"day": evidence["day"], "proposals": len(proposals), "filed": filed}


def _command_model(
    prompt: str,
    *,
    backend: str,
    model: str,
    project: str,
    checkout: str,
    executable: str,
) -> str:
    prompt_path = Path(
        os.environ.get(
            "SINNIX_RETROSPECTIVE_PROMPT",
            "/realm/tmp/work/retrospective-prompt.txt",
        )
    )
    prompt_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    prompt_path.write_text(prompt)
    started = subprocess.run(
        [
            executable,
            "agent",
            "--project",
            project,
            "--checkout",
            checkout,
            "--prompt-file",
            str(prompt_path),
            "--backend",
            backend,
            "--model",
            model,
            "--effort",
            "low",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    response = json.loads(started.stdout)
    job_id = response.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        raise RetrospectiveError("agentctl did not return a job ID")
    subprocess.run(
        [executable, "agent", "wait", job_id, "--timeout-seconds", "2700"],
        check=True,
        timeout=2750,
    )
    result = subprocess.run(
        [executable, "agent", "result", job_id, "--max-bytes", "200000"],
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    value = json.loads(result.stdout)
    output = value.get("result", result.stdout) if isinstance(value, dict) else value
    if not isinstance(output, str):
        raise RetrospectiveError("agentctl returned a non-text model result")
    return output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sinnix-retrospective")
    parser.add_argument(
        "--day",
        type=date.fromisoformat,
        default=datetime.now(UTC).date() - timedelta(days=1),
    )
    parser.add_argument(
        "--event-spool", type=Path, default=Path("/realm/state/agentctl/events.jsonl")
    )
    parser.add_argument("--harvest-root", type=Path, default=Path("/realm/tmp/work"))
    parser.add_argument("--harvest-glob", default="harvest-*.quick.log")
    parser.add_argument(
        "--receipt-root", type=Path, default=Path("/realm/state/agentctl/jobs")
    )
    parser.add_argument(
        "--state", type=Path, default=Path("/realm/state/agentctl/retrospective.json")
    )
    parser.add_argument("--agentctl", default="agentctl")
    parser.add_argument("--project", default="sinnix")
    parser.add_argument("--checkout", default="default")
    parser.add_argument("--backend", default="codex")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args(argv)
    evidence = collect_evidence(
        day=args.day,
        event_spool=args.event_spool,
        harvest_root=args.harvest_root,
        harvest_glob=args.harvest_glob,
        receipt_root=args.receipt_root,
    )

    def create(proposal: dict[str, Any]) -> None:
        subprocess.run(
            [
                args.agentctl,
                "task",
                "create",
                args.project,
                proposal["title"],
                "--description",
                proposal["description"],
                "--type",
                proposal["type"],
                "--priority",
                str(proposal["priority"]),
                *sum((["--label", label] for label in proposal["labels"]), []),
                "--request-id",
                proposal["request_id"],
            ],
            check=True,
            timeout=60,
        )

    result = run_retrospective(
        evidence=evidence,
        model_call=lambda prompt: _command_model(
            prompt,
            backend=args.backend,
            model=args.model,
            project=args.project,
            checkout=args.checkout,
            executable=args.agentctl,
        ),
        task_create=create,
        state_path=args.state,
    )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
