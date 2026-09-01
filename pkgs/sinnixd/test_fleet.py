from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from sinnixd.fleet import read_evidence, read_fleet, render_evidence, render_fleet
from sinnixd.jobs import GenericJobSpec, GenericJobStore
from sinnixd.workspaces import WorkspaceRecord, WorkspaceStore


def _job(
    store: GenericJobStore,
    *,
    job_id: str,
    created_at: str,
    phase: str,
    terminal: bool,
    checkout: dict[str, str] | None = None,
    contract: dict[str, object] | None = None,
):
    record = store.create(
        GenericJobSpec(
            kind="declared-operation",
            command=("fixture",),
            working_directory="/tmp",
            environment={},
            timeout_seconds=60,
            project_id="sinnix",
            operation="verify",
            parameter_digest="0" * 64,
            checkout=checkout,
            contract=contract or {},
        ),
        job_id,
    )
    return replace(
        record,
        created_at=created_at,
        state={
            "phase": phase,
            "terminal": terminal,
            "observed_at": created_at,
            "systemd": {"MemoryPeak": "1234", "CPUUsageNSec": "99"},
        },
    )


def _checkout(path: Path, workspace_id: str) -> dict[str, str]:
    return {
        "project_id": "sinnix",
        "project_path": str(path),
        "checkout_id": workspace_id,
        "path": str(path),
        "git_common_dir": str(path / ".git"),
        "head": "a" * 40,
    }


def test_fleet_joins_fixtures_and_caps_gh_calls(tmp_path: Path) -> None:
    store = GenericJobStore(tmp_path / "state")
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    workspace_id = "workspace-fixture"
    workspace_store = WorkspaceStore(store.root)
    workspace_store.put(
        WorkspaceRecord(
            workspace_id=workspace_id,
            project_id="sinnix",
            name="fixture",
            path=worktree,
            branch="feature/fixture",
            base="master",
            created_at="2026-08-26T00:00:00+00:00",
            managed=True,
        )
    )
    now = datetime(2026, 8, 26, 12, tzinfo=UTC)
    active = _job(
        store,
        job_id="00000000-0000-0000-0000-000000000001",
        created_at="2026-08-26T11:55:00+00:00",
        phase="running",
        terminal=False,
        checkout=_checkout(worktree, workspace_id),
        contract={
            "bead_binding": {"bead_ref": "sinnix://projects/sinnix/beads/sinnix-byw5"}
        },
    )
    queued = _job(
        store,
        job_id="00000000-0000-0000-0000-000000000002",
        created_at="2026-08-26T11:58:00+00:00",
        phase="queued",
        terminal=False,
    )
    recent = _job(
        store,
        job_id="00000000-0000-0000-0000-000000000003",
        created_at="2026-08-26T08:00:00+00:00",
        phase="succeeded",
        terminal=True,
    )
    old = _job(
        store,
        job_id="00000000-0000-0000-0000-000000000004",
        created_at="2026-08-24T00:00:00+00:00",
        phase="succeeded",
        terminal=True,
    )
    for record in (active, queued, recent, old):
        store.save(record)
    calls: list[tuple[Path, str]] = []

    def gh(path: Path, branch: str):
        calls.append((path, branch))
        return {"number": 42, "state": "OPEN", "url": "https://example.test/pr/42"}

    payload = read_fleet(
        store,
        workspace_store=workspace_store,
        now=now,
        gh_limit=1,
        gh=gh,
    )
    assert payload["counts"] == {
        "active": 1,
        "queued": 1,
        "recent": 1,
        "shown": 3,
        "records_seen": 4,
    }
    assert [row["job_id"] for row in payload["rows"]] == [
        active.job_id,
        queued.job_id,
        recent.job_id,
    ]
    assert payload["rows"][0]["bead"].endswith("sinnix-byw5")
    assert payload["rows"][0]["pr"]["number"] == 42
    assert len(calls) == 1
    assert old.job_id not in {row["job_id"] for row in payload["rows"]}
    assert "sinnix-byw5" in render_fleet(payload)


def test_evidence_unknown_unit_is_explicitly_absent(tmp_path: Path) -> None:
    payload = read_evidence(
        GenericJobStore(tmp_path / "state"), "missing-unit", gh_limit=0
    )
    assert payload["unit_kind"] == "absent"
    assert payload["record"] is None
    assert payload["workspace"] is None
    assert payload["pr"] is None
    assert "record: -" in render_evidence(payload)
