"""Mount paths retain Linux escapes and component boundaries."""

from pathlib import Path

import pytest

from sinnix_lib.mounts import has_mounted_ancestor, read_mountpoints


def test_mountinfo_decodes_escapes_once(monkeypatch):
    raw = r"1 0 8:1 / /mnt/a\040b\011c\012d\134040 rw - ext4 /dev/fixture rw" + "\n"
    monkeypatch.setattr(Path, "read_text", lambda _: raw)
    assert read_mountpoints() == {Path("/mnt/a b\tc\nd\\040")}


@pytest.mark.parametrize("record", ["", "incomplete record\n"])
def test_mountinfo_refuses_empty_or_malformed_records(monkeypatch, record):
    monkeypatch.setattr(Path, "read_text", lambda _: record)
    with pytest.raises(ValueError, match="mountinfo"):
        read_mountpoints()


def test_mounts_do_not_cover_siblings_or_similar_names():
    mounted = {Path("/"), Path("/mnt/device"), Path("/mnt/device-peer")}
    assert has_mounted_ancestor(Path("/mnt/device/a"), Path("/mnt"), mounted)
    assert not has_mounted_ancestor(Path("/mnt/offline/a"), Path("/mnt"), mounted)
    assert not has_mounted_ancestor(Path("/mnt/device-other/a"), Path("/mnt"), mounted)
    assert not has_mounted_ancestor(Path("/mnt-other/device/a"), Path("/mnt"), mounted)


def test_automount_placeholder_does_not_prove_payload_presence(monkeypatch):
    raw = (
        "1 0 8:1 / / rw - ext4 /dev/root rw\n"
        "2 1 0:2 / /mnt/offline rw - autofs systemd-1 rw\n"
        "3 1 0:3 / /mnt/online rw - autofs systemd-1 rw\n"
        "4 3 8:2 / /mnt/online rw - ext4 /dev/fixture rw\n"
    )
    monkeypatch.setattr(Path, "read_text", lambda _: raw)
    mounted = read_mountpoints()
    assert mounted == {Path("/"), Path("/mnt/online")}
    assert not has_mounted_ancestor(Path("/mnt/offline/item"), Path("/mnt"), mounted)
    assert has_mounted_ancestor(Path("/mnt/online/item"), Path("/mnt"), mounted)
