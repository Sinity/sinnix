import subprocess

from agentctl.content_identity import content_manifest
from agentctl.run import execution_receipt


def test_dirty_content_changes_even_when_status_does_not(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    source = tmp_path / "source.py"
    source.write_text("value = 1\n")
    first = content_manifest(tmp_path)
    source.write_text("value = 2\n")
    second = content_manifest(tmp_path)
    assert first["sha256"] != second["sha256"]
    assert first["coverage"] == "complete_declared_scope"
    start = {
        "status": "observed",
        "head": "abc",
        "tree": "def",
        "dirty": True,
        "content_manifest": first,
    }
    end = {**start, "content_manifest": second}
    assert execution_receipt(start, end)["binding"] == "changed"
    assert execution_receipt(start, start)["immutable_execution_attestation"] is None


def test_content_manifest_preserves_omissions_and_link_identity(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "large").write_bytes(b"x" * 100)
    (tmp_path / "link").symlink_to("large")
    manifest = content_manifest(tmp_path, max_bytes=10)
    assert manifest["coverage"] == "partial"
    assert manifest["omissions"] == [{"path": "large", "reason": "byte limit"}]
    assert manifest["files"][0]["kind"] == "symlink"
