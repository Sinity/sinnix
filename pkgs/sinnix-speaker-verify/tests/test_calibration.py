"""Calibration math and corpus-safety contracts for sinnix-speaker-verify.

These tests fail if AS-norm stops using both cohort comparisons, if the EER
threshold calculation stops balancing false accepts and rejects, or if trial
groups can reuse an enrollment/cohort file.
"""

from __future__ import annotations

import importlib.util
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
