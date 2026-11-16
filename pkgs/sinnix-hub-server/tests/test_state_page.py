"""The state page and its routes, over a synthetic engine document."""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timedelta, timezone
from html import unescape
from pathlib import Path

from sinnix_hub_server import pages
from sinnix_runtime.operator_state import engine
from sinnix_runtime.operator_state.service import OperatorState

NOW = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)
MARKER = '<img src=x onerror="alert(1)">'


def stamp(minutes_ago: float) -> str:
    return engine.iso(NOW - timedelta(minutes=minutes_ago))


def document() -> dict:
    facts = {
        "projects": [{"id": "alpha", "root": "/x/alpha"}],
        "beads": {
            "alpha": {
                "human": [
                    {
                        "id": "alpha-1",
                        "title": MARKER,
                        "priority": 1,
                        "created_at": stamp(30),
                    }
                ]
            }
        },
        "jobs": {
            "groups": {},
            "jobs": [
                {
                    "task_id": 7,
                    "job_id": "job-7",
                    "attempt": 1,
                    "label": "alpha:test",
                    "project": "alpha",
                    "operation": "test",
                    "group": "normal",
                    "phase": "running",
                    "terminal": False,
                    "started_at": stamp(4),
                    "command": MARKER,
                    "expected_target": {"kind": "job", "job_id": "job-7", "attempt": 1},
                }
            ],
        },
        "git": {
            "alpha": {
                "default_branch": "origin/main",
                "commits": [
                    {"commit": "a" * 40, "at": stamp(50), "subject": MARKER},
                    {"commit": "b" * 40, "at": stamp(40), "subject": "second"},
                ],
            }
        },
        "pulls": {"alpha": {"merged": []}},
        "deployed": {
            "host_revision": "f" * 40,
            "projects": {
                "alpha": {
                    "kind": "flake-input",
                    "revision": "a" * 40,
                    "contains": {"a" * 40},
                }
            },
        },
        "job_history": {
            "recent": [
                {
                    "label": "alpha:lint",
                    "project": "alpha",
                    "task_id": 5,
                    "job_id": "job-5",
                    "attempt": 2,
                    "outcome": "failure",
                    "exit_code": 1,
                    "ended_at": stamp(3),
                    "working_directory": "/x/alpha",
                }
            ]
        },
        "limits": {
            "memory": {
                "total": 2**34,
                "available": 2**32,
                "page_cache": 2**30,
                "swap_total": 2**33,
                "swap_used": 2**31,
            }
        },
    }
    return engine.compute(facts, {}, NOW)


def test_state_page_orders_sections_and_escapes_agent_written_text() -> None:
    html = pages.render(
        "/state/", {"host": "fixture"}, None, None, operator_state=document()
    )
    order = [
        html.index(f"<h2>{title}")
        for title in (
            "Waiting on you (1)",
            "Running (1 running, 0 queued)",
            "Finished since you last looked (1)",
            "Merged, not yet live (1)",
            "Stalled or looping",
            "Limits and load",
            "Forecast",
            "Products",
            "Recent jobs",
        )
    ]
    assert order == sorted(order)
    assert "<img" not in html and html.count(unescape(MARKER)) == 0
    assert "page cache 1.0G" in html
    plain = unescape(html)
    # Cancel on the running job, retry on the failed one, nothing else.
    assert "act('interrupt','task_id',\"7\"" in plain
    assert "act('retry','task_id',\"5\"" in plain
    assert plain.count('onclick="act(') == 2
    assert f'data-generated-at="{engine.iso(NOW)}"' in html
    assert "/ops/v1/state/looked" in html and "has('peek')" in html


def test_state_page_without_a_document_still_renders() -> None:
    html = pages.render("/state/", {}, None, None)
    assert "has not produced a document" in html


def test_state_routes_serve_the_document_and_move_last_looked(
    hub_server_factory, http_get, tmp_path: Path
) -> None:
    config = tmp_path / "agentctl.json"
    config.write_text(
        json.dumps({"project_roots": [], "event_spool": str(tmp_path / "events.jsonl")})
    )
    service = OperatorState(tmp_path / "memory.json", jobs=dict, agentctl_config=config)
    base = hub_server_factory(operator_state=service)

    status, _, body = http_get(base + "/v1/state")
    state = json.loads(body)
    assert (
        status == 200
        and state["counts"]["waiting"] == 0
        and state["last_looked_at"] is None
    )
    # Reading the document or the page does not count as the operator looking.
    assert http_get(base + "/state/?peek=1")[0] == 200
    assert json.loads(http_get(base + "/v1/state")[2])["last_looked_at"] is None

    request = urllib.request.Request(
        base + "/v1/state/looked",
        data=json.dumps({"generated_at": state["generated_at"]}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        assert json.load(response) == {"last_looked_at": state["generated_at"]}
    assert (
        json.loads((tmp_path / "memory.json").read_text())["last_looked_at"]
        == state["generated_at"]
    )
    assert (
        json.loads(http_get(base + "/v1/state")[2])["last_looked_at"]
        == state["generated_at"]
    )
