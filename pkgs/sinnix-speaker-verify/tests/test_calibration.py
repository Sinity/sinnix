"""Calibration math and corpus-safety contracts for sinnix-speaker-verify.

These tests fail if AS-norm stops using both cohort comparisons, if the EER
threshold calculation stops balancing false accepts and rejects, or if trial
groups can reuse an enrollment/cohort file.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

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


@pytest.mark.parametrize("same_group", [False, True])
def test_disjoint_check_rejects_hardlinked_audio(
    tmp_path: Path, same_group: bool
) -> None:
    sample = tmp_path / "clip.wav"
    sample.touch()
    alias = tmp_path / "other-name.wav"
    alias.hardlink_to(sample)
    groups = (
        {"enrollment": [sample, alias]}
        if same_group
        else {"enrollment": [sample], "genuine": [alias]}
    )
    with pytest.raises(ValueError, match="reused"):
        MODULE._assert_disjoint(groups)


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


def _publish_synthetic_report(monkeypatch, tmp_path: Path):
    groups = {}
    for label, count in {
        "enrollment": 2,
        "genuine": 2,
        "impostor": 2,
        "cohort": 3,
    }.items():
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
        if path.parent.name == "enrollment":
            return np.array([[2.0, 0.0], [0.0, 1.0]][int(path.stem)])
        if path.parent.name == "cohort":
            return np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0]][int(path.stem)])
        return (
            np.array([-1.0, 0.0])
            if path.parent.name == "impostor"
            else np.array([1.0, 0.0])
        )

    monkeypatch.setattr(MODULE, "_embed", embedding)
    output = tmp_path / "report.json"
    args = type(
        "Args",
        (),
        {**{label: label for label in groups}, "output": str(output), "max_eer": 0.5},
    )()

    assert MODULE.cmd_calibrate(args) == 0
    assert json.loads(output.read_text())["version"] == MODULE.CALIBRATION_VERSION
    assert output.stat().st_mode & 0o777 == 0o600
    assert not list(output.parent.glob(".*.atomic-tmp-*"))
    return output, groups


def test_model_fetch_pins_the_cached_revision_even_with_existing_files(monkeypatch):
    calls = []
    sentinel = object()

    def from_hparams(**kwargs):
        calls.append(kwargs)
        return sentinel

    monkeypatch.setitem(
        sys.modules,
        "speechbrain.inference.speaker",
        SimpleNamespace(EncoderClassifier=SimpleNamespace(from_hparams=from_hparams)),
    )
    monkeypatch.setitem(
        sys.modules,
        "speechbrain.utils.fetching",
        SimpleNamespace(FetchConfig=SimpleNamespace),
    )

    assert MODULE._load_model() is sentinel
    assert len(calls) == 1
    fetch = calls[0]["fetch_config"]
    assert calls[0]["source"] == "speechbrain/spkrec-ecapa-voxceleb"
    assert fetch.revision == "0f99f2d0ebe89ac095bcc5903c4dd8f72b367286"
    assert fetch.allow_updates is True


@pytest.mark.parametrize(
    "embedding", [[0.0, 0.0], [float("nan"), 1.0], [float("inf"), 1.0]]
)
def test_invalid_enrollment_preserves_the_previous_centroid(
    monkeypatch, tmp_path, embedding
):
    monkeypatch.setattr(MODULE, "STORE_DIR", tmp_path / "store")
    monkeypatch.setattr(MODULE, "_load_model", lambda: object())
    monkeypatch.setattr(MODULE, "_embed", lambda _model, _audio: np.array(embedding))
    target = MODULE._enrollment_path("operator")
    target.parent.mkdir()
    previous = b'{"name":"operator","centroid":[1.0,0.0],"n_samples":1}'
    target.write_bytes(previous)
    target.chmod(0o600)
    args = SimpleNamespace(audio=["synthetic.wav"], name="operator")

    with pytest.raises(ValueError, match="finite non-zero norm"):
        MODULE.cmd_enroll(args)

    assert target.read_bytes() == previous
    assert target.stat().st_mode & 0o777 == 0o600


def test_score_refuses_an_unbound_report_before_loading_model(monkeypatch, tmp_path):
    store = tmp_path / "store"
    store.mkdir()
    (store / "operator.json").write_text(json.dumps({"centroid": [1.0, 0.0]}))
    report = tmp_path / "report.json"
    report.write_text(
        json.dumps(
            {
                "supports_attribution": True,
                "cohort_embeddings": [[0, 1], [-1, 0], [0, -1]],
            }
        )
    )
    monkeypatch.setattr(MODULE, "STORE_DIR", store)
    calls = []
    monkeypatch.setattr(MODULE, "_load_model", lambda: calls.append("load") or object())
    monkeypatch.setattr(MODULE, "_embed", lambda *args: np.array([0.8, 0.6]))
    args = SimpleNamespace(
        name="operator", audio="neutral.wav", calibration=str(report)
    )
    with pytest.raises(ValueError, match="calibration"):
        MODULE.cmd_score(args)
    assert calls == []


def test_calibrate_publishes_a_private_report(monkeypatch, tmp_path):
    _publish_synthetic_report(monkeypatch, tmp_path)


@pytest.fixture
def calibrated(monkeypatch, tmp_path):
    report, groups = _publish_synthetic_report(monkeypatch, tmp_path)
    monkeypatch.setattr(MODULE, "STORE_DIR", tmp_path / "store")
    MODULE.cmd_enroll(
        SimpleNamespace(
            audio=list(map(str, reversed(groups["enrollment"]))), name="operator"
        )
    )
    return report, SimpleNamespace(
        name="operator", audio=str(groups["genuine"][0]), calibration=str(report)
    )


def test_matching_report_scores_the_exact_enrollment(calibrated, capsys):
    report, args = calibrated
    payload = json.loads(report.read_text())
    enrolled = json.loads(MODULE._enrollment_path("operator").read_text())
    assert payload["centroid_sha256"] == enrolled["centroid_sha256"]
    assert payload["model"] == enrolled["model"] == MODULE._model_identity()
    capsys.readouterr()
    assert MODULE.cmd_score(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert isinstance(result["attribution_score"], float)


@pytest.mark.parametrize(
    "change",
    [
        "report_model",
        "enrollment_model",
        "centroid",
        "version",
        "method",
        "trials",
        "metric",
        "summary",
        "counts",
        "cohort",
        "max_eer",
    ],
)
def test_mismatched_or_malformed_report_refuses_before_model_load(
    calibrated, monkeypatch, change
):
    report, args = calibrated
    payload = json.loads(report.read_text())
    target = MODULE._enrollment_path("operator")
    enrolled = json.loads(target.read_text())
    if change == "report_model":
        payload["model"]["revision"] = "another-model"
    elif change == "enrollment_model":
        enrolled["model"]["revision"] = "another-model"
    elif change == "centroid":
        enrolled["centroid"] = [-1.0, 0.0]
        enrolled["centroid_sha256"] = MODULE._centroid_digest(enrolled["centroid"])
    elif change == "version":
        payload["version"] = 1
    elif change == "method":
        payload["method"] = "another-method"
    elif change == "trials":
        payload["trial_scores"]["genuine"][0] = float("nan")
    elif change == "metric":
        payload["equal_error_rate"] = 0.9
    elif change == "summary":
        payload["genuine"]["mean"] = -100.0
    elif change == "counts":
        payload["counts"]["enrollment"] = 0
    elif change == "cohort":
        payload["cohort_embeddings"][0] = [1, 0, 0]
    elif change == "max_eer":
        payload["max_eer"] = float("nan")
    report.write_text(json.dumps(payload))
    target.write_text(json.dumps(enrolled))
    before = target.read_bytes(), report.read_bytes()
    calls = []
    monkeypatch.setattr(MODULE, "_load_model", lambda: calls.append("load"))
    with pytest.raises(ValueError, match="calibration"):
        MODULE.cmd_score(args)
    assert not calls
    assert (target.read_bytes(), report.read_bytes()) == before


def test_support_flag_cannot_override_measured_trials(calibrated, capsys):
    report, args = calibrated
    payload = json.loads(report.read_text())
    genuine = impostor = [0.0, 0.1]
    stats = MODULE._eer(genuine, impostor)
    payload.update(
        trial_scores={"genuine": genuine, "impostor": impostor},
        equal_error_rate=stats["eer"],
        threshold=stats["threshold"],
        false_accept_rate=stats["far"],
        false_reject_rate=stats["frr"],
        calibration_error_brier=MODULE._brier(genuine, impostor, stats["threshold"]),
        max_eer=0.05,
        supports_attribution=True,
    )
    for label, values in (("genuine", genuine), ("impostor", impostor)):
        payload[label] = {
            "min": min(values),
            "mean": float(np.mean(values)),
            "max": max(values),
        }
    report.write_text(json.dumps(payload))
    capsys.readouterr()
    assert MODULE.cmd_score(args) == 0
    assert "attribution_score" not in json.loads(capsys.readouterr().out)


@pytest.mark.parametrize("maximum", [-0.1, 1.1, float("nan"), float("inf"), True])
def test_invalid_calibration_policy_refuses_before_model_load(monkeypatch, maximum):
    monkeypatch.setattr(MODULE, "_load_model", lambda: pytest.fail("loaded model"))
    with pytest.raises(ValueError, match="finite probability"):
        MODULE.cmd_calibrate(SimpleNamespace(max_eer=maximum))


def test_legacy_enrollment_still_scores_without_calibration(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.setattr(MODULE, "STORE_DIR", tmp_path)
    target = tmp_path / "operator.json"
    original = b'{"centroid":[1.0,0.0]}'
    target.write_bytes(original)
    monkeypatch.setattr(MODULE, "_load_model", lambda: object())
    monkeypatch.setattr(MODULE, "_embed", lambda *args: np.array([0.8, 0.6]))
    assert (
        MODULE.cmd_score(
            SimpleNamespace(name="operator", audio="synthetic.wav", calibration=None)
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["cosine_similarity"] == 0.8
    assert "attribution_score" not in result
    assert target.read_bytes() == original


@pytest.mark.parametrize("unavailable", ["directory", "file-link"])
def test_corpus_reader_refuses_unavailable_inputs(tmp_path, monkeypatch, unavailable):
    for name in ["one.wav", "two.wav"]:
        (tmp_path / name).write_bytes(b"synthetic audio")
    hidden = tmp_path / "unavailable"
    hidden.mkdir()
    (hidden / "third.wav").write_bytes(b"synthetic audio")
    if unavailable == "directory":
        hidden.chmod(0)
        expected = PermissionError
    else:
        (tmp_path / "broken.wav").symlink_to(tmp_path / "absent.wav")
        expected = FileNotFoundError
    report = tmp_path / "previous-report.json"
    previous = b'{"previous":"verified report"}'
    report.write_bytes(previous)
    inode = report.stat().st_ino
    monkeypatch.setattr(
        MODULE,
        "_load_model",
        lambda: pytest.fail("model loaded before corpus validation"),
    )
    try:
        with pytest.raises(expected):
            MODULE._audio_files(str(tmp_path))
        with pytest.raises(expected):
            MODULE.cmd_calibrate(
                SimpleNamespace(
                    max_eer=0.05,
                    enrollment=str(tmp_path),
                    genuine="unused",
                    impostor="unused",
                    cohort="unused",
                    output=str(report),
                )
            )
        assert report.read_bytes() == previous and report.stat().st_ino == inode
    finally:
        hidden.chmod(0o700)


def test_corpus_reader_preserves_file_links_without_recursing_directory_links(tmp_path):
    audio = tmp_path / "source.wav"
    audio.write_bytes(b"synthetic audio")
    (tmp_path / "alias.wav").symlink_to(audio)
    (tmp_path / "loop").symlink_to(tmp_path, target_is_directory=True)
    assert MODULE._audio_files(str(tmp_path)) == [tmp_path / "alias.wav", audio]
