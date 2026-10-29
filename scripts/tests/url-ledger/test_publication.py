import argparse
import fcntl
import sys

from test_commoncrawl import ledger


def test_reader_failure_propagates_and_releases_lease(tmp_path, monkeypatch):
    selected = tmp_path / "generation"
    observed = []

    def select(root):
        with (root / ".build.lock").open("a") as probe:
            try:
                fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                observed.append("protected selection")
            else:
                raise AssertionError("selection preceded the reader lease")
        return selected

    monkeypatch.setattr(ledger, "published_generation", select)
    receipt = tmp_path / "child-generation"
    command = [
        sys.executable,
        "-c",
        "import os, pathlib, sys; "
        "pathlib.Path(sys.argv[1]).write_text(os.environ['SINNIX_URL_LEDGER_GENERATION']); "
        "sys.exit(37)",
        str(receipt),
    ]
    assert (
        ledger.cmd_published(
            argparse.Namespace(derived_root=str(tmp_path), reader=command)
        )
        == 37
    )
    assert observed == ["protected selection"]
    assert receipt.read_text() == str(selected)
    with (tmp_path / ".build.lock").open("a") as probe:
        fcntl.flock(probe, fcntl.LOCK_EX | fcntl.LOCK_NB)
