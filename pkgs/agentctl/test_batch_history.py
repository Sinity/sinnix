"""Original run evidence stays readable independently of the execution engine."""

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from agentctl import batch_history as history


def document():
    return {
        "run_id": "fixture-20260101-000000-abcdef00",
        "project": "fixture",
        "base_commit": "a" * 40,
        "created_at": "2026-01-01T00:00:00+00:00",
        "harness": "external",
        "workers": [{"id": "fixture-a", "beads": ["fixture-a"], "attempts": [1, 2]}],
        "landing": {"candidate_sha": "b" * 40},
        "acceptance": {"original_revision": 9223372036854775807},
        "future_owner_field": {"text": "synthetic \u03bb", "missing": None},
    }


def test_original_document_and_retry_history_survive_reads(tmp_path):
    cfg = SimpleNamespace(state_dir=tmp_path)
    root = tmp_path / "runs"
    root.mkdir()
    original = document()
    path = root / (original["run_id"] + ".json")
    path.write_text(json.dumps(original))
    before = path.read_bytes()
    run = history.load(cfg, original["run_id"])
    assert run.to_dict() == original
    assert run.workers[0]["attempts"] == [1, 2]
    assert not run.live
    assert run.beads == ("fixture-a",)
    assert history.resolve_run_id(cfg, "abcdef00") == run.run_id
    run.workers[0]["attempts"].append(3)
    assert run.to_dict() == original
    assert path.read_bytes() == before


def test_corrupt_history_is_unavailable_not_a_partial_success(tmp_path):
    cfg = SimpleNamespace(state_dir=tmp_path)
    assert history.list_runs(cfg) == []
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs/broken.json").write_text("{")
    with pytest.raises(history.HistoryError, match="manifest"):
        history.list_runs(cfg)


def test_inaccessible_history_is_not_empty(tmp_path, monkeypatch):
    cfg = SimpleNamespace(state_dir=tmp_path)

    def denied(_path):
        raise PermissionError("synthetic inaccessible store")

    monkeypatch.setattr(Path, "iterdir", denied)
    with pytest.raises(history.HistoryError, match="cannot inventory"):
        history.list_runs(cfg)


def test_run_reference_cannot_select_a_different_store(tmp_path):
    with pytest.raises(history.HistoryError, match="one filename"):
        history.load(SimpleNamespace(state_dir=tmp_path), "../outside")


def test_history_import_does_not_load_an_execution_or_prompt_engine():
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).parent)}
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import agentctl.batch_history; "
            "assert not {'agentctl.config', 'agentctl.start', 'agentctl.landing', "
            "'agentctl.prompts', 'agentctl.agents'} & sys.modules.keys()",
        ],
        env=env,
        check=True,
    )


@pytest.mark.parametrize("raw", ["null", "[]", "42", '"text"', '{"workers": []}'])
def test_invalid_document_shape_has_a_history_error(tmp_path, raw):
    cfg = SimpleNamespace(state_dir=tmp_path)
    (tmp_path / "runs").mkdir()
    (tmp_path / "runs/broken.json").write_text(raw)
    with pytest.raises(history.HistoryError, match="manifest"):
        history.load(cfg, "broken")


def test_cleanup_import_does_not_load_workflow_or_prompt_engine():
    packages = Path(__file__).parent.parent
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(
            (str(packages / "agentctl"), str(packages / "sinnix-lib"))
        ),
    }
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import agentctl.worktree_cleanup; "
            "assert not {'agentctl.config', 'agentctl.manifest', 'agentctl.start', "
            "'agentctl.landing', 'agentctl.prompts', 'agentctl.agents'} & sys.modules.keys()",
        ],
        env=env,
        check=True,
    )
