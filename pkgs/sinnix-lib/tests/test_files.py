import errno
import os

import pytest

from sinnix_lib.files import NotRegularFile, open_regular, read_regular_bytes, read_regular_text


def test_regular_file_reads_in_text_and_binary(tmp_path):
    path = tmp_path / "a.txt"
    path.write_text("ą\n")
    with open_regular(path, "r") as text:
        assert text.read() == "ą\n"
    assert read_regular_text(path) == "ą\n"
    assert read_regular_bytes(path) == "ą\n".encode()


def test_fifo_is_refused_without_waiting_for_a_writer(tmp_path):
    fifo = tmp_path / "fifo"
    os.mkfifo(fifo)
    with pytest.raises(NotRegularFile) as caught:
        with open_regular(fifo):
            pytest.fail("a FIFO was opened as a regular file")
    # Callers written against either the old ValueError or OSError contract
    # still catch it.
    assert isinstance(caught.value, ValueError)
    assert isinstance(caught.value, OSError) and caught.value.errno == errno.EINVAL


def test_byte_bound_is_enforced(tmp_path):
    path = tmp_path / "a.bin"
    path.write_bytes(b"12345")
    assert read_regular_bytes(path, max_bytes=5) == b"12345"
    with pytest.raises(ValueError, match="exceeds 4 byte bound"):
        read_regular_bytes(path, max_bytes=4)
