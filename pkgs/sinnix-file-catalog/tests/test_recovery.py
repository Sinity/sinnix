"""Exact retained copies restore logical assets without inventing continuity."""

import hashlib
import json
import runpy

import pytest
from test_catalog import SCRIPT, assets, import_rows, invoke, observation


def prepared(tmp_path):
    source = tmp_path / "original.md"
    source.write_text("Synthetic historical document.\n")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    catalog = tmp_path / "catalog.json"
    identity = runpy.run_path(str(SCRIPT))["identity"](source)
    assert (
        import_rows(
            catalog, [observation(source, identity={**identity, "sha256": digest})]
        ).returncode
        == 0
    )
    original = assets(catalog)[0]
    restored = tmp_path / "retained-copy.md"
    restored.write_bytes(source.read_bytes())
    source.unlink()
    row = {
        "id": original["id"],
        "action": "recover_copy",
        "actor": "synthetic-test",
        "basis": "Recorded full hash and retained package",
        "reason": "Recover inspected bytes",
        "new_path": str(restored),
        "expected_identity": runpy.run_path(str(SCRIPT))["identity"](restored),
    }
    return catalog, original, source, restored, row


def recover(catalog, rows, digest=None):
    observations = catalog.with_name("recovery.json")
    observations.write_text(json.dumps(rows))
    return invoke(
        catalog,
        "observe",
        str(observations),
        "--expected-sha256",
        digest or hashlib.sha256(catalog.read_bytes()).hexdigest(),
    )


def test_recovery_retains_uuid_inspections_and_original_identity(tmp_path):
    catalog, original, source, restored, row = prepared(tmp_path)
    result = recover(catalog, [row])
    assert result.returncode == 0, result.stderr
    current = assets(catalog)[0]
    assert current["id"] == original["id"]
    assert current["inspections"] == original["inspections"]
    assert current["current_path"] == str(restored)
    assert str(source) in current["previous_paths"]
    assert current["current_location"]["prior_catalog_identity"] == original["identity"]
    assert current["current_location"]["content_continuity"] == "verified_full_sha256"
    assert current["identity"]["sha256"] == original["identity"]["sha256"]
    assert not source.exists()


@pytest.mark.parametrize(
    "failure",
    [
        "stale",
        "bytes",
        "sample",
        "missing_digest",
        "metadata",
        "large_record",
        "original_exists",
        "collision",
        "symlink",
    ],
)
def test_recovery_refuses_unproved_or_conflicting_locations(tmp_path, failure):
    catalog, original, source, restored, row = prepared(tmp_path)
    digest = None
    if failure == "stale":
        digest = "0" * 64
    elif failure == "bytes":
        restored.write_text("Different historical bytes.\n")
        row["expected_identity"] = runpy.run_path(str(SCRIPT))["identity"](restored)
    elif failure == "sample":
        data = json.loads(catalog.read_bytes())
        data["assets"][0]["identity"]["fingerprint_kind"] = "sha256-head-tail-size-v1"
        catalog.write_text(json.dumps(data))
    elif failure in ("missing_digest", "large_record"):
        data = json.loads(catalog.read_bytes())
        if failure == "missing_digest":
            del data["assets"][0]["identity"]["sha256"]
        else:
            data["assets"][0]["identity"]["size"] = 8 * 1024 * 1024 + 1
        catalog.write_text(json.dumps(data))
    elif failure == "metadata":
        row["expected_identity"]["size"] += 1
    elif failure == "original_exists":
        source.write_bytes(restored.read_bytes())
    elif failure == "collision":
        assert import_rows(catalog, [observation(restored)]).returncode == 0
    elif failure == "symlink":
        link = tmp_path / "link.md"
        link.symlink_to(restored)
        row["new_path"] = str(link)
    before = catalog.read_bytes()
    result = recover(catalog, [row], digest)
    assert result.returncode != 0
    assert catalog.read_bytes() == before


def test_recovery_batch_failure_publishes_no_partial_change(tmp_path):
    catalog, original, source, restored, row = prepared(tmp_path)
    second = tmp_path / "second.md"
    second.write_text("Second synthetic document.\n")
    digest = hashlib.sha256(second.read_bytes()).hexdigest()
    identity = runpy.run_path(str(SCRIPT))["identity"](second)
    assert (
        import_rows(
            catalog, [observation(second, identity={**identity, "sha256": digest})]
        ).returncode
        == 0
    )
    asset = assets(catalog)[1]
    second.unlink()
    bad = {**row, "id": asset["id"], "new_path": str(tmp_path / "absent.md")}
    before = catalog.read_bytes()
    assert recover(catalog, [row, bad]).returncode != 0
    assert catalog.read_bytes() == before


def test_validation_distinguishes_unavailable_history_from_broken_current_path(
    tmp_path,
):
    catalog, original, source, restored, row = prepared(tmp_path)
    assert invoke(catalog, "validate").returncode != 0
    unavailable = {
        "id": original["id"],
        "action": "unavailable",
        "actor": "synthetic-test",
        "basis": "Fresh source diagnosis",
        "reason": "Retained historical record",
    }
    assert recover(catalog, [unavailable]).returncode == 0
    result = invoke(catalog, "validate")
    assert result.returncode == 0, result.stderr
    source.write_text("Newly reappearing content")
    result = invoke(catalog, "validate")
    assert (
        result.returncode != 0 and "availability observation is stale" in result.stderr
    )


def test_unavailable_history_cannot_hide_a_different_path(tmp_path):
    catalog, original, source, restored, row = prepared(tmp_path)
    unavailable = {
        "id": original["id"],
        "action": "unavailable",
        "actor": "synthetic-test",
        "basis": "Fresh source diagnosis",
        "reason": "Retained historical record",
    }
    assert recover(catalog, [unavailable]).returncode == 0
    data = json.loads(catalog.read_bytes())
    data["assets"][0]["current_location"]["path"] = str(restored)
    catalog.write_text(json.dumps(data))
    result = invoke(catalog, "validate")
    assert result.returncode != 0 and "consistent path" in result.stderr
