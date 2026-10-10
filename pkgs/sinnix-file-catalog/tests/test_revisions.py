"""Reviewed revisions preserve the evidence of earlier content."""
import hashlib
import json
import runpy
from pathlib import Path
from test_catalog import assets, import_rows, invoke, observation

SCRIPT = Path(__file__).parents[3] / "scripts" / "sinnix-file-catalog"


def test_revision_keeps_asset_and_old_inspection_but_refuses_stale_review(tmp_path):
    source = tmp_path / "note"
    source.write_text("old content")
    catalog = tmp_path / "catalog.json"
    assert import_rows(catalog, [observation(source)]).returncode == 0
    original = assets(catalog)[0]
    source.write_text("different revised content")
    identity = runpy.run_path(str(SCRIPT))["identity"](source)
    observations = tmp_path / "observations.json"
    observations.write_text(json.dumps([dict(id=original['id'], action='content_revision',
        actor='synthetic-test', basis='explicit changed-content evidence', reason='revision', expected_identity=identity)]))
    digest = hashlib.sha256(catalog.read_bytes()).hexdigest()
    result = invoke(catalog, 'observe', str(observations), '--expected-sha256', '0' * 64)
    assert result.returncode != 0 and 'stale catalog digest' in result.stderr
    assert hashlib.sha256(catalog.read_bytes()).hexdigest() == digest
    result = invoke(catalog, 'observe', str(observations), '--expected-sha256', digest)
    assert result.returncode == 0, result.stderr
    current = assets(catalog)[0]
    assert current['id'] == original['id']
    assert current['revisions'][0]['inspections'] == original['inspections']
    assert current['revisions'][0]['identity'] == original['identity']
    assert current['coverage']['inspected_count'] == 0
    assert current['current_location']['content_continuity'] == 'unverified'


def test_metadata_observation_does_not_rebind_inspection_or_manufacture_hash(tmp_path):
    source = tmp_path / "note"
    source.write_text("content")
    catalog = tmp_path / "catalog.json"
    assert import_rows(catalog, [observation(source)]).returncode == 0
    original = assets(catalog)[0]
    identity = runpy.run_path(str(SCRIPT))["identity"](source)
    observations = tmp_path / "observations.json"
    observations.write_text(json.dumps([dict(id=original['id'], action='metadata', actor='synthetic-test',
        basis='current stat only', reason='metadata refresh', expected_identity=identity)]))
    digest = hashlib.sha256(catalog.read_bytes()).hexdigest()
    result = invoke(catalog, 'observe', str(observations), '--expected-sha256', digest)
    assert result.returncode == 0, result.stderr
    current = assets(catalog)[0]
    assert current['identity'] == original['identity']
    assert current['inspections'] == original['inspections']
    assert current['current_location']['content_continuity'] == 'unverified'
    assert 'sha256' not in current['current_location']['identity']


def test_unavailable_observation_becomes_current_and_can_be_restored(tmp_path):
    source = tmp_path / "note"
    source.write_text("retained content")
    catalog = tmp_path / "catalog.json"
    assert import_rows(catalog, [observation(source)]).returncode == 0
    original = assets(catalog)[0]
    observations = tmp_path / "location-observations.json"

    def observe(action, **extra):
        observations.write_text(json.dumps([dict(
            id=original["id"], action=action, actor="synthetic-test",
            basis="reviewed current location", reason="location transition", **extra,
        )]))
        digest = hashlib.sha256(catalog.read_bytes()).hexdigest()
        result = invoke(catalog, "observe", str(observations), "--expected-sha256", digest)
        assert result.returncode == 0, result.stderr
        return assets(catalog)[0]

    identity = runpy.run_path(str(SCRIPT))["identity"](source)
    available = observe("metadata", expected_identity=identity)
    assert available["current_location"]["status"] == "available"
    source.unlink()
    unavailable = observe("unavailable")
    latest = unavailable["location_observations"][-1]
    assert latest["status"] == "missing"
    assert unavailable["current_location"] == latest
    assert unavailable["location_status"] == "missing"
    assert unavailable["identity"] == original["identity"]
    assert unavailable["inspections"] == original["inspections"]
    assert unavailable["location_observations"][:-1] == available["location_observations"]

    source.write_text("retained content")
    identity = runpy.run_path(str(SCRIPT))["identity"](source)
    restored = observe("metadata", expected_identity=identity)
    assert restored["current_location"] == restored["location_observations"][-1]
    assert restored["current_location"]["status"] == "available"
    assert restored["location_status"] == "available"
    assert restored["current_location"]["content_continuity"] == "unverified"
    assert restored["identity"] == original["identity"]
    assert restored["inspections"] == original["inspections"]
    assert restored["location_observations"][:-1] == unavailable["location_observations"]


def test_observation_receipt_digest_is_bound_before_unlock(tmp_path, monkeypatch, capsys):
    from argparse import Namespace
    from contextlib import contextmanager

    source = tmp_path / "note"
    source.write_text("content")
    catalog = tmp_path / "catalog.json"
    assert import_rows(catalog, [observation(source)]).returncode == 0
    asset = assets(catalog)[0]
    module = runpy.run_path(str(SCRIPT))["cmd_observe"].__globals__
    observations = tmp_path / "observations.json"
    observations.write_text(json.dumps([dict(
        id=asset["id"], action="metadata", actor="synthetic-test",
        basis="reviewed current metadata", reason="refresh",
        expected_identity=module["identity"](source),
    )]))
    original_lock = module["locked"]
    committed = []

    @contextmanager
    def next_writer_after_unlock(path):
        with original_lock(path):
            yield
            committed.append(path.read_bytes())
        # A second writer wins the lock before the first prints its receipt.
        with original_lock(path):
            later = json.loads(path.read_bytes())
            later["assets"][0]["tags"].append("second-writer")
            module["write_catalog"](path, later)

    monkeypatch.setitem(module, "locked", next_writer_after_unlock)
    args = Namespace(catalog=str(catalog), observations=str(observations),
                     expected_sha256=hashlib.sha256(catalog.read_bytes()).hexdigest())
    assert module["cmd_observe"](args) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["catalog_sha256"] == hashlib.sha256(committed[0]).hexdigest()
    assert receipt["catalog_sha256"] != hashlib.sha256(catalog.read_bytes()).hexdigest()
