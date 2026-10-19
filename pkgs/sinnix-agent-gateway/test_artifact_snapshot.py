"""Snapshot failures must release file descriptors and preserve source evidence."""

import os
from pathlib import Path

import pytest
from sinnix_agent_gateway.artifacts import ArtifactService
from sinnix_agent_gateway.config import GatewayConfig
from sinnix_agent_gateway.permissions import Principal


def service(tmp_path):
    owner = ArtifactService(
        GatewayConfig(state_dir=tmp_path / "state", projects={}),
        Principal.for_name("operator"),
    )
    directory = owner.config.state_dir / "captures" / "fixture"
    directory.mkdir()
    source = directory / "source.txt"
    source.write_bytes(b"synthetic evidence\n")
    owner.attest_capture(directory, source="fixture", target={}, files=[source])
    return owner, source


@pytest.mark.parametrize("failure", ["missing", "denied"])
def test_registration_source_open_failure_does_not_leak_descriptors(
    tmp_path, monkeypatch, failure
):
    owner, source = service(tmp_path)
    original_attestation = owner._source_is_attested
    original_open = Path.open

    if failure == "missing":

        def disappear(path):
            attested = original_attestation(path)
            path.unlink()
            return attested

        monkeypatch.setattr(owner, "_source_is_attested", disappear)
    else:

        def denied(path, *args, **kwargs):
            if path == source and args and args[0] == "rb":
                raise PermissionError("synthetic read denial")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(Path, "open", denied)

    before = len(os.listdir("/proc/self/fd"))
    for _ in range(5):
        source.write_bytes(b"synthetic evidence\n")
        with pytest.raises(OSError):
            owner.register(source, kind="fixture", owner_id="fixture")
    assert len(os.listdir("/proc/self/fd")) == before
    assert not list(owner.root.rglob(".content-*"))
    assert list(owner.root.iterdir()) == []
    if failure == "denied":
        assert source.read_bytes() == b"synthetic evidence\n"


def test_registered_snapshot_retains_bytes_and_private_mode(tmp_path):
    owner, source = service(tmp_path)
    identity = owner.register(source, kind="fixture", owner_id="fixture")
    snapshot = owner.registered_content(identity)
    assert snapshot.read_bytes() == source.read_bytes() == b"synthetic evidence\n"
    assert snapshot.stat().st_mode & 0o777 == 0o600
