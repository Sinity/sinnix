"""Retained outcomes remain useful after inventories outgrow inline transport."""

import hashlib
import json
import os
import tracemalloc
from pathlib import Path

import pytest
from agentctl import artifacts, launch, outcome, run
from agentctl.projects import load_project_adapter
from conftest import read_launch


def large_record(mapping=False):
    files = [
        {
            "path": f"file-{i}-\udcff.txt",
            "mode": 420,
            "kind": "file",
            "bytes": 0,
            "sha256": "a" * 64,
        }
        for i in range(15000)
    ]
    if mapping:
        files = {str(i): item for i, item in enumerate(files)}
    endpoint = {
        "status": "observed",
        "head": "b" * 40,
        "tree": "c" * 40,
        "dirty": True,
        "content_manifest": {
            "sha256": "d" * 64,
            "coverage": "complete",
            "files": files,
            "omissions": [{"path": "unavailable", "reason": "denied"}],
        },
    }
    return {
        "attempt": 1,
        "outcome": "success",
        "exit_code": 0,
        "execution_receipt": run.execution_receipt(endpoint, endpoint),
    }


@pytest.mark.parametrize("mapping", [False, True])
def test_large_retained_receipt_preserves_verdict_and_exact_inventory(
    tmp_path, mapping
):
    record = large_record(mapping)
    raw = json.dumps(record).encode()
    assert len(raw) > launch.MAX_OUTCOME_BYTES
    path = tmp_path / "outcome.json"
    path.write_bytes(raw)
    path.chmod(0o600)
    before = path.stat()
    view = launch._outcome_from_path(path)["outcome"]
    assert view["outcome"] == "success" and view["exit_code"] == 0
    assert view["execution_receipt"]["binding"] == "unchanged_endpoints"
    assert len(json.dumps(view).encode()) < launch.MAX_OUTCOME_BYTES
    for endpoint in ("start", "end"):
        manifest = view["execution_receipt"][endpoint]["content_manifest"]
        assert manifest["sha256"] == "d" * 64
        for field, count in (("files", 15000), ("omissions", 1)):
            ref = manifest[field + "_ref"]
            assert field not in manifest
            assert ref["sha256"] == hashlib.sha256(raw).hexdigest()
            assert ref["bytes"] == len(raw) and ref["entries"] == count
            source = json.loads(Path(ref["path"]).read_bytes())
            for component in ref["json_pointer"].split("/")[1:]:
                source = source[component]
            assert (
                source
                == record["execution_receipt"][endpoint]["content_manifest"][field]
            )
    assert path.read_bytes() == raw
    after = path.stat()
    assert (before.st_ino, before.st_mtime_ns, before.st_mode) == (
        after.st_ino,
        after.st_mtime_ns,
        after.st_mode,
    )


def test_streaming_does_not_retain_decoded_inventories(tmp_path):
    path = tmp_path / "outcome.json"
    raw = json.dumps(large_record()).encode()
    path.write_bytes(raw)
    # Warm parser imports before measuring working memory.
    outcome.read_outcome(path, launch.MAX_OUTCOME_BYTES)
    tracemalloc.start()
    try:
        view = outcome.read_outcome(path, launch.MAX_OUTCOME_BYTES)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert view["outcome"] == "success"
    assert peak < 3 * 1024 * 1024


@pytest.mark.parametrize("suffix", [b"broken", b" {}", b' , "outcome":"failed"}'])
def test_large_malformed_source_never_returns_partial_success(tmp_path, suffix):
    path = tmp_path / "outcome.json"
    path.write_bytes(json.dumps(large_record()).encode() + suffix)
    assert outcome.read_outcome(path, launch.MAX_OUTCOME_BYTES) is None
    path.write_bytes(path.read_bytes()[:-100])
    assert outcome.read_outcome(path, launch.MAX_OUTCOME_BYTES) is None


def test_duplicate_metadata_does_not_forge_inventory_references(tmp_path):
    path = tmp_path / "outcome.json"
    raw = json.dumps(large_record()).encode()
    path.write_bytes(raw[:-1] + b',"execution_receipt":null}')
    assert outcome.read_outcome(path, launch.MAX_OUTCOME_BYTES) is None


def test_nonregular_and_symlink_sources_are_refused(tmp_path):
    regular = tmp_path / "regular"
    regular.write_text('{"outcome":"success"}')
    link = tmp_path / "link"
    link.symlink_to(regular)
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    for path in (link, fifo, tmp_path, tmp_path / "absent"):
        assert outcome.read_outcome(path, launch.MAX_OUTCOME_BYTES) is None
    assert outcome.read_outcome(regular, launch.MAX_OUTCOME_BYTES) == {
        "outcome": "success"
    }


def test_source_changed_while_reading_is_refused(tmp_path, monkeypatch):
    path = tmp_path / "outcome.json"
    path.write_text(json.dumps(large_record()))
    original = outcome._project

    def changing(handle, source, limit):
        view = original(handle, source, limit)
        source.write_text('{"outcome":"failed"}')
        return view

    monkeypatch.setattr(outcome, "_project", changing)
    assert outcome.read_outcome(path, launch.MAX_OUTCOME_BYTES) is None


def test_archived_job_keeps_large_outcome_after_queue_removal(
    fake_pueue, config, project_root
):
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    task = fake_pueue.task(started["job_id"])
    document = read_launch(config, task)
    allocated = artifacts.begin(document, str(launch.launch_input_path(task)))
    path = run.outcome_path_for(allocated["log_path"])
    path.write_text(json.dumps(large_record()))
    fake_pueue.remove([started["job_id"]])
    view = launch.get_job(started["job_id"], config, started["reference"])
    assert view["queue_present"] is False
    assert view["phase"] == "succeeded" and view["terminal"] is True
    assert view["exit_code"] == 0 and view["attempt"] == 1
    assert view["outcome"]["execution_receipt"]["start"]["dirty"] is True
    assert view["outcome"]["outcome_ref"]["path"] == str(path)


@pytest.mark.parametrize("dirty", [False, True])
def test_large_cached_receipt_still_requires_clean_endpoints(
    fake_pueue, config, project_root, dirty
):
    project = load_project_adapter(project_root)
    started = launch.start_operation(config, project, project.operation("check"))
    task = fake_pueue.task(started["job_id"])
    document = read_launch(config, task)
    allocated = artifacts.begin(document, str(launch.launch_input_path(task)))
    record = large_record()
    for endpoint in ("start", "end"):
        record["execution_receipt"][endpoint]["dirty"] = dirty
    record["execution_evidence"] = {
        "environment_identity": hashlib.sha256(
            json.dumps(document.get("environment") or {}, sort_keys=True).encode()
        ).hexdigest()
    }
    run.outcome_path_for(allocated["log_path"]).write_text(json.dumps(record))
    fake_pueue.succeed(started["job_id"])
    result = launch.successful_cached_attempt(
        config,
        fake_pueue.task(started["job_id"]),
        {"head": "b" * 40, "tree": "c" * 40, "dirty": False},
        None,
    )
    assert (result is not None) is (not dirty)
