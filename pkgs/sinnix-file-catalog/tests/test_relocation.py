"""Migration failures must not partially publish identity metadata."""

import json

from test_catalog import assets, import_rows, invoke, observation


def prepare(tmp_path, catalog, moves, *options):
    manifest = tmp_path / "moves.json"
    receipt = tmp_path / "receipt.json"
    manifest.write_text(json.dumps(moves))
    result = invoke(catalog, "prepare-relocation", str(manifest), "--output", str(receipt), *options)
    return result, receipt


def fixture(tmp_path):
    old = tmp_path / "old"
    old.mkdir()
    (old / "entry").write_text("original")
    catalog = tmp_path / "catalog.json"
    rows = [observation(old, kind="collection"), observation(old / "entry")]
    assert import_rows(catalog, rows).returncode == 0
    new = tmp_path / "new"
    return old, new, catalog, [{"source": str(old), "destination": str(new)}]


def test_descendant_relocation_preserves_ids_evidence_and_reverses(tmp_path):
    old, new, catalog, moves = fixture(tmp_path)
    original = assets(catalog)
    result, receipt = prepare(tmp_path, catalog, moves)
    assert result.returncode == 0, result.stderr
    old.rename(new)
    assert invoke(catalog, "relocate-batch", str(receipt)).returncode == 0
    for before, after in zip(original, assets(catalog)):
        assert after["id"] == before["id"]
        assert after["inspections"] == before["inspections"]
        assert after["previous_paths"] == [before["current_path"]]
    resolved = invoke(catalog, "resolve", str(old / "entry"))
    assert resolved.returncode == 0 and resolved.stdout.strip() == str(new / "entry")
    # Reversal uses the same identity checks and appends history, not a reset.
    receipt.unlink()
    result, receipt = prepare(tmp_path, catalog, [{"source": str(new), "destination": str(old)}])
    assert result.returncode == 0
    new.rename(old)
    assert invoke(catalog, "relocate-batch", str(receipt)).returncode == 0
    assert assets(catalog)[1]["current_path"] == str(old / "entry")


def test_stale_catalog_and_changed_payload_leave_metadata_intact(tmp_path):
    old, new, catalog, moves = fixture(tmp_path)
    result, receipt = prepare(tmp_path, catalog, moves)
    assert result.returncode == 0
    old.rename(new)
    (new / "entry").write_text("changed output")
    before = catalog.read_bytes()
    result = invoke(catalog, "relocate-batch", str(receipt))
    assert result.returncode != 0 and "identity mismatch" in result.stderr
    assert catalog.read_bytes() == before
    catalog.write_bytes(before + b"\n")
    changed = catalog.read_bytes()
    result = invoke(catalog, "relocate-batch", str(receipt))
    assert result.returncode != 0 and "stale catalog digest" in result.stderr
    assert catalog.read_bytes() == changed


def test_collision_and_partial_external_rename_are_refused(tmp_path):
    old, new, catalog, moves = fixture(tmp_path)
    other = tmp_path / "other"
    other.write_text("other")
    assert import_rows(catalog, [observation(other)]).returncode == 0
    result, receipt = prepare(tmp_path, catalog, [*moves, {"source": str(other), "destination": str(new / "entry")}])
    assert result.returncode != 0 and "collide" in result.stderr
    result, receipt = prepare(tmp_path, catalog, moves)
    assert result.returncode == 0
    before = catalog.read_bytes()
    result = invoke(catalog, "relocate-batch", str(receipt))
    assert result.returncode != 0 and "old address still exists" in result.stderr
    assert catalog.read_bytes() == before


def test_existing_drift_is_explicit_retained_history_not_hash_certification(tmp_path):
    old, new, catalog, moves = fixture(tmp_path)
    value = json.loads(catalog.read_text())
    value["assets"][1]["identity"]["device"] = -1
    value["assets"][1]["identity"]["sha256"] = "historical attribution"
    catalog.write_text(json.dumps(value))
    result, receipt = prepare(tmp_path, catalog, moves)
    assert result.returncode != 0 and "existing identity drift" in result.stderr
    result, receipt = prepare(tmp_path, catalog, moves, "--record-existing-drift")
    assert result.returncode == 0
    old.rename(new)
    assert invoke(catalog, "relocate-batch", str(receipt)).returncode == 0
    moved = assets(catalog)[1]
    assert "sha256" not in moved["identity"]
    assert moved["relocations"][0]["prior_catalog_identity"]["sha256"] == "historical attribution"
    assert moved["relocations"][0]["prior_identity_matches"] is False


def test_reused_historical_address_requires_explicit_asset_identity(tmp_path):
    old, new, catalog, moves = fixture(tmp_path)
    result, receipt = prepare(tmp_path, catalog, moves)
    assert result.returncode == 0
    old.rename(new)
    assert invoke(catalog, "relocate-batch", str(receipt)).returncode == 0
    old.mkdir()
    (old / "entry").write_text("different")
    assert import_rows(catalog, [observation(old / "entry")]).returncode == 0
    assert invoke(catalog, "resolve", str(old / "entry")).returncode != 0
    original_id = assets(catalog)[1]["id"]
    result = invoke(catalog, "resolve", str(old / "entry"), "--id", original_id)
    assert result.returncode == 0 and result.stdout.strip() == str(new / "entry")


def test_original_address_can_become_a_new_parent_container(tmp_path):
    old, _, catalog, _ = fixture(tmp_path)
    new = old / "repo"
    result, receipt = prepare(tmp_path, catalog, [{"source": str(old), "destination": str(new)}])
    assert result.returncode == 0
    temporary = tmp_path / "staged"
    old.rename(temporary)
    old.mkdir()
    temporary.rename(new)
    assert invoke(catalog, "relocate-batch", str(receipt)).returncode == 0
    assert invoke(catalog, "resolve", str(old / "entry")).stdout.strip() == str(new / "entry")


def test_unavailable_history_remains_unavailable_without_inventing_continuity(tmp_path):
    old, new, catalog, moves = fixture(tmp_path)
    original = assets(catalog)[1]
    (old / "entry").unlink()
    result, receipt = prepare(tmp_path, catalog, moves, "--retain-unavailable")
    assert result.returncode == 0
    old.rename(new)
    assert invoke(catalog, "relocate-batch", str(receipt)).returncode == 0
    missing = assets(catalog)[1]
    assert missing["current_path"] == original["current_path"]
    assert missing["identity"] == original["identity"]
    assert missing["location_status"] == "unavailable"
    assert invoke(catalog, "resolve", str(old / "entry")).returncode != 0
