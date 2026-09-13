"""Native evidence filing uses task, Beads and Git observations without batches."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from agentctl import cli, evidence, launch
from agentctl.config import Config, resolve_project
from agentctl.run import outcome_path_for
from conftest import FakeBd, FakePueue

SHA = "a" * 40


def _claim(*, receipt: str, schema_version: int | None = None) -> dict:
    value = {
        "candidate_sha": SHA,
        "beads": [{"id": "fx-1", "criteria": []}],
        "unresolved": [],
        "verification": [
            {
                "command": "fixture check",
                "receipt": receipt,
                "tested_sha": SHA,
                "status": "passed",
                "coverage": {"ac_ids": ["AC-1"], "scope": "focused"},
            }
        ],
    }
    if schema_version is not None:
        value.update(
            schema_version=schema_version,
            execution="native",
            attempt=1,
            model_segments=[],
            measured_usage=None,
            beads=[
                {
                    "id": "fx-1",
                    "bead_revision": "17",
                    "acceptance_digest": "1791badcc7ac5f89d864ebf64b72eaf3b941d4e2eeb80de2c72245a1a0c9d9dc",
                    "criteria": [
                        {
                            "ac_id": "AC-1",
                            "text": "the check passes",
                            "status": "satisfied",
                            "evidence": "claimed",
                        }
                    ],
                }
            ],
        )
    return value


def _receipt_job(
    config: Config, fake_pueue: FakePueue, project, *, start_sha: str = SHA
) -> tuple[int, str]:
    queued = launch.enqueue(
        config,
        project=project,
        operation="check",
        label="fixture:check",
        group="normal",
        argv=("true",),
        working_directory=project.root,
        timeout_seconds=60,
        result_kind="exit",
        environment={},
        tree_receipt={"head": SHA, "tree": "b" * 40, "dirty": False},
    )
    fake_pueue.succeed(queued["job_id"])
    outcome = outcome_path_for(config.jobs_dir / f"{queued['reference']}.log")
    outcome.parent.mkdir(parents=True)
    outcome.write_text(
        json.dumps(
            {
                "outcome": "success",
                "exit_code": 0,
                "execution_receipt": {
                    "binding": "unchanged_endpoints",
                    "start": {
                        "head": start_sha,
                        "tree": "b" * 40,
                        "dirty": False,
                        "status": "observed",
                    },
                    "end": {
                        "head": SHA,
                        "tree": "b" * 40,
                        "dirty": False,
                        "status": "observed",
                    },
                },
            }
        )
    )
    return queued["job_id"], queued["reference"]


def _beads() -> FakeBd:
    return FakeBd(
        {
            "fx-1": {
                "id": "fx-1",
                "revision": 17,
                "metadata": {
                    "acceptance_criteria": [{"id": "AC-1", "text": "the check passes"}]
                },
            }
        }
    )


@pytest.mark.parametrize("cleaned", [False, True])
def test_file_keeps_claim_separate_from_clean_receipt_observation(
    cleaned: bool,
    config: Config,
    fake_pueue: FakePueue,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = resolve_project(config, "fixture")
    job_id, reference = _receipt_job(config, fake_pueue, project)
    if cleaned:
        launch.clean(config, job_id, reference)
    monkeypatch.setattr(evidence, "SubprocessBdReader", lambda root: _beads())
    monkeypatch.setattr(
        evidence,
        "_candidate",
        lambda project, candidate: {
            "candidate_sha": candidate,
            "checked": True,
            "eligible": True,
        },
    )
    monkeypatch.setattr(
        evidence,
        "_publication",
        lambda project, candidate: {
            "state": "published",
            "candidate_reachable": True,
            "checked": True,
        },
    )
    path = tmp_path / "native.json"
    path.write_text(json.dumps(_claim(receipt=f"agentctl://jobs/{job_id}/{reference}")))

    record = evidence.file(config, project, path)

    assert record["worker_result"]["verification"][0]["receipt"].endswith(reference)
    observation = record["verification"][0]["observation"]
    assert observation["eligible"] is True
    assert observation["queue_present"] is not cleaned
    assert observation["attempt"] == 1
    assert Path(observation["artifacts"]["outcome"]).is_file()
    assert observation["execution_receipt"]["end"] == {
        "head": SHA,
        "tree": "b" * 40,
        "dirty": False,
        "status": "observed",
    }
    assert observation["tree_receipt"] == {
        "head": SHA,
        "tree": "b" * 40,
        "dirty": False,
    }
    assert record["task_snapshot"][0]["evidence_binding"]["bead_revision"] == "17"
    assert record["task_snapshot"][0]["acceptance_criteria"] == [
        {"id": "AC-1", "text": "the check passes"}
    ]
    assert evidence.list_records(config, "fixture")["records"] == [record]


def test_v2_claim_must_match_the_current_filing_snapshot(
    config: Config,
    fake_pueue: FakePueue,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = resolve_project(config, "fixture")
    job_id, reference = _receipt_job(config, fake_pueue, project)
    monkeypatch.setattr(evidence, "SubprocessBdReader", lambda root: _beads())
    path = tmp_path / "native.json"
    claim = _claim(receipt=f"agentctl://jobs/{job_id}/{reference}", schema_version=2)
    claim["beads"][0]["bead_revision"] = "old"
    path.write_text(json.dumps(claim))

    with pytest.raises(launch.JobError, match="filing snapshot"):
        evidence.file(config, project, path)


def test_receipt_requires_the_immutable_launch_reference(
    config: Config,
    fake_pueue: FakePueue,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = resolve_project(config, "fixture")
    job_id, _reference = _receipt_job(config, fake_pueue, project)
    monkeypatch.setattr(evidence, "SubprocessBdReader", lambda root: _beads())
    path = tmp_path / "native.json"
    path.write_text(json.dumps(_claim(receipt=f"agentctl://jobs/{job_id}")))

    with pytest.raises(launch.JobError, match="launch-reference"):
        evidence.file(config, project, path)


def test_v2_native_route_rejects_a_queued_execution_claim(
    config: Config,
    fake_pueue: FakePueue,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = resolve_project(config, "fixture")
    job_id, reference = _receipt_job(config, fake_pueue, project)
    monkeypatch.setattr(evidence, "SubprocessBdReader", lambda root: _beads())
    path = tmp_path / "native.json"
    claim = _claim(receipt=f"agentctl://jobs/{job_id}/{reference}", schema_version=2)
    claim["execution"] = "queued"
    path.write_text(json.dumps(claim))

    with pytest.raises(launch.JobError, match="execution=native"):
        evidence.file(config, project, path)


def test_receipt_needs_clean_candidate_at_both_execution_endpoints(
    config: Config,
    fake_pueue: FakePueue,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project = resolve_project(config, "fixture")
    job_id, reference = _receipt_job(config, fake_pueue, project, start_sha="c" * 40)
    monkeypatch.setattr(evidence, "SubprocessBdReader", lambda root: _beads())
    monkeypatch.setattr(evidence, "_candidate", lambda project, candidate: {})
    monkeypatch.setattr(evidence, "_publication", lambda project, candidate: {})
    path = tmp_path / "native.json"
    path.write_text(json.dumps(_claim(receipt=f"agentctl://jobs/{job_id}/{reference}")))

    record = evidence.file(config, project, path)

    observation = record["verification"][0]["observation"]
    assert observation["eligible"] is False
    assert any("endpoints" in gap for gap in observation["gaps"])


def test_publication_requires_advertised_head_to_match_local_tracking_ref(
    config: Config, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = resolve_project(config, "fixture")
    monkeypatch.setattr(evidence.github, "remote_head", lambda root, branch: "b" * 40)
    calls = []

    def git(root, *arguments, **kwargs):
        calls.append(arguments)
        if arguments[0] == "rev-parse":
            return "b" * 40
        return ""

    monkeypatch.setattr(evidence.gitcmd, "git", git)
    publication = evidence._publication(project, SHA)

    assert publication["state"] == "published"
    assert publication["candidate_reachable"] is True
    assert any(call[0] == "merge-base" for call in calls)


def test_list_ignores_malformed_or_other_project_records(config: Config) -> None:
    directory = config.state_dir / "native-evidence"
    directory.mkdir(parents=True)
    (directory / "bad.json").write_text("not json")
    (directory / "other.json").write_text(
        json.dumps({"schema_version": 1, "kind": "native_evidence", "project": "other"})
    )

    listed = evidence.list_records(config, "fixture")
    assert listed["records"] == []
    assert listed["coverage"] == "partial"


def test_evidence_discover_parser_keeps_project_ref_and_limit_explicit() -> None:
    arguments = cli.parser().parse_args(
        [
            "evidence",
            "discover",
            "--bead",
            "fx-1",
            "--project",
            "fixture",
            "--ref",
            "HEAD~3",
            "--limit",
            "7",
        ]
    )

    assert arguments.evidence_verb == "discover"
    assert arguments.bead == "fx-1"
    assert arguments.project == "fixture"
    assert arguments.reference == "HEAD~3"
    assert arguments.limit == 7


@pytest.mark.parametrize("retained", [True, False])
def test_cleaned_receipt_never_substitutes_an_unrelated_reused_queue_id(
    config: Config,
    fake_pueue: FakePueue,
    retained: bool,
) -> None:
    project = resolve_project(config, "fixture")
    job_id, reference = _receipt_job(config, fake_pueue, project, start_sha="c" * 40)
    launch.clean(config, job_id, reference)
    fake_pueue.next_id = job_id
    unrelated = launch.enqueue(
        config,
        project=project,
        operation="unrelated",
        label="fixture:unrelated",
        group="normal",
        argv=("true",),
        working_directory=project.root,
        timeout_seconds=60,
        result_kind="exit",
        environment={},
    )
    fake_pueue.succeed(unrelated["job_id"])
    original_outcome = outcome_path_for(config.jobs_dir / f"{reference}.log")
    other_outcome = outcome_path_for(config.jobs_dir / f"{unrelated['reference']}.log")
    successful = json.loads(original_outcome.read_text())
    successful["execution_receipt"]["start"]["head"] = SHA
    other_outcome.write_text(json.dumps(successful))
    assert unrelated["job_id"] == job_id
    claim = {"receipt": f"agentctl://jobs/{job_id}/{reference}"}
    if not retained:
        (config.inputs_dir / f"{reference}.json").unlink()
        with pytest.raises(launch.JobError, match="does not resolve"):
            evidence._receipt_observation(config, claim, SHA, project_id="fixture")
        return
    observation = evidence._receipt_observation(
        config, claim, SHA, project_id="fixture"
    )
    assert observation["reference"] == reference
    assert observation["operation"] == "check"
    assert observation["queue_present"] is False
    assert observation["eligible"] is False
    assert observation["execution_receipt"]["start"]["head"] == "c" * 40
    assert any("endpoints" in gap for gap in observation["gaps"])


@pytest.mark.parametrize(
    "damage", ["missing-outcome", "incomplete-endpoint", "other-project"]
)
def test_cleaned_receipt_still_requires_complete_project_bound_execution_evidence(
    config: Config,
    fake_pueue: FakePueue,
    damage: str,
) -> None:
    project = resolve_project(config, "fixture")
    job_id, reference = _receipt_job(config, fake_pueue, project)
    launch.clean(config, job_id, reference)
    outcome_path = outcome_path_for(config.jobs_dir / f"{reference}.log")
    if damage == "missing-outcome":
        outcome_path.unlink()
    elif damage == "incomplete-endpoint":
        outcome = json.loads(outcome_path.read_text())
        outcome["execution_receipt"].pop("end")
        outcome_path.write_text(json.dumps(outcome))
    else:
        input_path = config.inputs_dir / f"{reference}.json"
        document = json.loads(input_path.read_text())
        document["project_id"] = "another-project"
        input_path.write_text(json.dumps(document))
    claim = {"receipt": f"agentctl://jobs/{job_id}/{reference}"}
    if damage == "other-project":
        with pytest.raises(launch.JobError, match="another project"):
            evidence._receipt_observation(config, claim, SHA, project_id="fixture")
    else:
        observation = evidence._receipt_observation(
            config, claim, SHA, project_id="fixture"
        )
        assert observation["eligible"] is False
        assert observation["gaps"]
