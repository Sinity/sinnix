"""Installed entry-point contracts across the filesystem data owners."""
import json
import os
import subprocess

import pytest


@pytest.fixture
def executable():
    return os.environ["SINNIX_FS_EXECUTABLE"]


def test_packaged_catalog_preserves_identity_and_location_evidence(executable, tmp_path):
    payload = tmp_path / "source.txt"
    payload.write_text("neutral source")
    observations = tmp_path / "observations.json"
    observations.write_text(json.dumps([{
        "current_path": str(payload), "title": "Neutral source",
        "description": "Synthetic retained source",
        "inspections": [{"method": "test", "scope": "metadata", "basis": "synthetic fixture"}],
    }]))
    catalog = tmp_path / "catalog.json"
    imported = subprocess.run([executable, "catalog", "--catalog", str(catalog), "import", str(observations)], capture_output=True, text=True)
    assert imported.returncode == 0, imported.stderr
    before = catalog.read_bytes()
    audit = subprocess.run([executable, "catalog", "--catalog", str(catalog), "audit"], capture_output=True, text=True)
    assert audit.returncode == 0, audit.stderr
    assert json.loads(audit.stdout)["counts"]["match"] == 1
    assert catalog.read_bytes() == before
    assert payload.read_text() == "neutral source"


def test_packaged_navigation_reports_a_real_missing_target(executable, tmp_path):
    document = tmp_path / "README.md"
    document.write_text("[missing](absent.txt)\n")
    manifest = tmp_path / "navigation.json"
    manifest.write_text(json.dumps({"schema_version": 1, "documents": [str(document)]}))
    result = subprocess.run([executable, "links", "--manifest", str(manifest)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "absent.txt" in result.stdout


@pytest.mark.parametrize("command", ["scan", "refresh", "status", "query", "classify", "catalog", "layout", "links"])
def test_installed_command_help_needs_no_live_store(executable, command, tmp_path):
    result = subprocess.run([executable, command, "--help"], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout
    assert list(tmp_path.iterdir()) == []
