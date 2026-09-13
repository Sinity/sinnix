"""Calibration math and corpus-safety contracts for sinnix-speaker-verify.

These tests fail if AS-norm stops using both cohort comparisons, if the EER
threshold calculation stops balancing false accepts and rejects, or if trial
groups can reuse an enrollment/cohort file.
"""

from __future__ import annotations

import importlib.util
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path

import numpy as np
import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "sinnix-speaker-verify"
SPEC = importlib.util.spec_from_loader(
    "speaker_verify", SourceFileLoader("speaker_verify", str(SCRIPT))
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_as_norm_is_symmetric_and_changes_raw_score() -> None:
    target = np.array([1.0, 0.0])
    probe = np.array([0.8, 0.6])
    cohort = [np.array([0.0, 1.0]), np.array([-1.0, 0.0]), np.array([0.0, -1.0])]

    raw, normalized = MODULE._as_norm(target, probe, cohort)

    assert raw == pytest.approx(0.8)
    assert normalized == pytest.approx(MODULE._as_norm(probe, target, cohort)[1])
    assert normalized != pytest.approx(raw)


def test_eer_reports_balanced_operating_point() -> None:
    result = MODULE._eer([0.8, 0.9], [0.1, 0.2])

    assert result["eer"] == 0
    assert result["far"] == 0
    assert result["frr"] == 0
    assert 0.2 < result["threshold"] <= 0.8


def test_disjoint_check_rejects_reused_audio(tmp_path: Path) -> None:
    sample = tmp_path / "clip.wav"
    sample.touch()

    with pytest.raises(ValueError, match="reused"):
        MODULE._assert_disjoint({"enrollment": [sample], "genuine": [sample]})


def test_enrollment_name_rejects_path_components(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(MODULE, "STORE_DIR", tmp_path / "store")
    for name in ("../escape", "/tmp/escape", ".", ""):
        with pytest.raises(ValueError, match="basename"):
            MODULE._enrollment_path(name)


def test_enroll_publishes_private_embedding_state(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(MODULE, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(MODULE, "_load_model", lambda: object())
    monkeypatch.setattr(MODULE, "_embed", lambda _model, _audio: np.array([3.0, 4.0]))
    args = type("Args", (), {"audio": ["sample.wav"], "name": "operator"})()

    assert MODULE.cmd_enroll(args) == 0
    target = MODULE._enrollment_path("operator")
    assert json.loads(target.read_text())["centroid"] == [0.6, 0.8]
    assert target.stat().st_mode & 0o777 == 0o600
    assert not list(target.parent.glob(".*.atomic-tmp-*"))


def test_calibrate_publishes_a_private_report(monkeypatch, tmp_path: Path) -> None:
    groups = {}
    for label, count in {"enrollment": 2, "genuine": 2, "impostor": 2, "cohort": 3}.items():
        paths = []
        for index in range(count):
            path = tmp_path / label / f"{index}.wav"
            path.parent.mkdir(exist_ok=True)
            path.touch()
            paths.append(path)
        groups[label] = paths

    monkeypatch.setattr(MODULE, "_audio_files", lambda directory: groups[directory])
    monkeypatch.setattr(MODULE, "_load_model", lambda: object())

    def embedding(_model, audio):
        path = Path(audio)
        if path.parent.name == "cohort":
            return np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]][int(path.stem)])
        return np.array([-1.0, 0.0]) if path.parent.name == "impostor" else np.array([1.0, 0.0])

    monkeypatch.setattr(MODULE, "_embed", embedding)
    output = tmp_path / "report.json"
    args = type("Args", (), {**{label: label for label in groups}, "output": str(output), "max_eer": 0.5})()

    assert MODULE.cmd_calibrate(args) == 0
    assert json.loads(output.read_text())["version"] == MODULE.CALIBRATION_VERSION
    assert output.stat().st_mode & 0o777 == 0o600
    assert not list(output.parent.glob(".*.atomic-tmp-*"))
