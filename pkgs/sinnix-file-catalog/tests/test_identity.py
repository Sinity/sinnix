"""Stable filesystem observations must not disappear from identity checks."""
import copy
import json
import runpy
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "sinnix-file-catalog"
BASE = dict(device=1, inode=2, size=3, mtime_ns=4, mode=0o600,
            filesystem_uuid="synthetic-filesystem", btrfs_subvolume_id=256)


@pytest.mark.parametrize("field,value", [("filesystem_uuid", "other-filesystem"),
    ("btrfs_subvolume_id", 257), ("btrfs_subvolume_id", None)])
def test_audit_observes_stable_identity_differences(tmp_path, monkeypatch, capsys, field, value):
    module = runpy.run_path(str(SCRIPT))
    actual = dict(BASE)
    if value is None:
        actual.pop(field)
    else:
        actual[field] = value
    catalog = {"updated_at": "synthetic", "assets": [dict(id="fixture", kind="file",
        current_path=str(tmp_path / "fixture"), identity=dict(BASE))]}
    before = copy.deepcopy(catalog)
    namespace = module["cmd_audit"].__globals__
    monkeypatch.setitem(namespace, "load_catalog", lambda *a, **k: catalog)
    monkeypatch.setitem(namespace, "location_diagnosis", lambda *a: dict(status="available", identity=actual))
    assert module["cmd_audit"](SimpleNamespace(catalog=tmp_path / "catalog", all=True)) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["counts"] == {"identity_mismatch": 1}
    assert result["findings"][0]["differences"] == {field: {"recorded": BASE[field], "observed": value}}
    assert catalog == before


@pytest.mark.parametrize("kind", ["file", "collection"])
def test_missing_stable_evidence_is_not_a_verified_identity(kind):
    compare = runpy.run_path(str(SCRIPT))["same_identity"]
    actual = dict(BASE)
    actual.pop("btrfs_subvolume_id")
    assert not compare(BASE, actual, kind)
    assert not compare({}, {}, kind)


def test_stable_identity_allows_device_observation_drift():
    compare = runpy.run_path(str(SCRIPT))["same_identity"]
    actual = dict(BASE, device=99)
    assert compare(BASE, actual)
    legacy = {key: value for key, value in BASE.items() if key not in ("filesystem_uuid", "btrfs_subvolume_id")}
    assert not compare(legacy, dict(legacy, device=99))
    assert compare(legacy, BASE)  # New stable fields do not rewrite old evidence.
